#!/usr/bin/env python3
"""Local frontend + workflow API server."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from agent_runner import run_agent_workflow
from llm_client import chat_completion, load_llm_config
from report_registry import (
    archive_reports,
    build_followup_prompt,
    get_report_record,
    increment_followup,
    is_report_artifact,
    list_report_records,
    restore_reports,
    sync_report_index_from_output,
    upsert_report_record,
)
from workflow_runner import PROJECT_ROOT


HOST = ""
PORT = 8000
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()


def llm_status_payload() -> dict:
    workflow = load_llm_config(profile="workflow").public_status()
    report = load_llm_config(profile="report").public_status()
    return {
        "configured": report["configured"],
        "has_api_key": report["has_api_key"],
        "api_base": report["api_base"],
        "model": report["model"],
        "profile": "report",
        "workflow": workflow,
        "report": report,
    }


def report_greeting_template(report: dict | None = None, mode: str = "new") -> str:
    if mode == "new" or not report:
        return "告诉我你想生成哪类日报：品牌、车型、对比、价格筛选或市场总览。"

    title = str(report.get("title") or report.get("file_name") or "当前报告")
    report_type = str(report.get("report_type") or "").lower()
    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    brands = [str(item) for item in scope.get("brands", []) if item]
    series = [str(item) for item in scope.get("series", []) if item]
    subject = " vs ".join(series[:2]) or "、".join(brands[:2]) or title

    if report_type == "brand":
        return f"当前基于「{subject}」品牌日报。你可以继续追问销量结构、车型表现、价格区间或购买建议。"
    if report_type == "series":
        return f"当前基于「{subject}」车型报告。你可以继续追问配置差异、价格走势、竞品对比或购买建议。"
    if report_type == "compare":
        return f"当前基于「{subject}」对比报告。你可以继续追问优劣势、适合人群、价格配置或最终推荐。"
    if report_type == "filtered":
        return "当前基于筛选报告。你可以继续收窄预算、车身类型、能源形式或品牌范围。"
    if report_type == "market":
        return "当前基于市场总览日报。你可以继续追问细分市场、品牌排名、价格带变化或购买窗口。"
    return f"当前基于「{title}」。你可以继续追问关键结论、风险点、车型对比或购买建议。"


def report_greeting_payload(report: dict | None = None, mode: str = "new") -> dict:
    fallback = report_greeting_template(report, mode=mode)
    if mode == "new" or not report:
        return {"greeting": fallback, "llm_used": False, "fallback_reason": "rule template"}

    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    context = {
        "title": report.get("title"),
        "report_type": report.get("report_type"),
        "date": report.get("date"),
        "scope": {
            "brands": scope.get("brands", []),
            "series": scope.get("series", []),
            "filters": scope.get("filters", {}),
        },
        "excerpt": summary.get("excerpt", ""),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是汽车日报工作台的本地任务助手。请根据报告元数据生成一句中文开场白，"
                "用于空聊天窗口。要求：30到60字；直接说明当前基于什么报告；给出可继续追问的方向；"
                "不要寒暄，不要使用Markdown，不要编造元数据之外的车型或品牌。"
            ),
        },
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]
    try:
        greeting = chat_completion(
            messages,
            profile="workflow",
            temperature=0.2,
            max_tokens=160,
            timeout=20,
            retries=0,
        ).strip().strip('"').strip("'")
        if not greeting:
            raise RuntimeError("empty greeting")
        return {"greeting": greeting, "llm_used": True, "fallback_reason": None}
    except Exception as exc:
        return {"greeting": fallback, "llm_used": False, "fallback_reason": str(exc)}


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def set_job(job_id: str, **updates) -> None:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.update(updates)
        job["updated_at"] = now_text()


def get_job(job_id: str) -> dict | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def run_job(job_id: str, prompt: str, use_llm: bool, source_report_id: str | None = None) -> None:
    def progress(step: str, message: str, progress_value: int) -> None:
        set_job(job_id, status="running", step=step, message=message, progress=progress_value)

    existing_output_backup: dict[str, str] = {}
    if source_report_id:
        for path in (PROJECT_ROOT / "output").glob("*.md"):
            if not is_report_artifact(path.name):
                continue
            relative_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            existing_output_backup[relative_path] = path.read_text(encoding="utf-8")

    acquired = RUN_LOCK.acquire(blocking=False)
    if not acquired:
        set_job(
            job_id,
            status="failed",
            step="queued",
            message="Another workflow job is already running. Please try again later.",
            error="workflow busy",
        )
        return

    try:
        result = run_agent_workflow(prompt, api_key=None, use_llm=use_llm, progress=progress)
        action = result.get("action", "run")
        common_payload = {
            "result": result,
            "parsed_task": result.get("task"),
            "workflow_notes": result.get("workflow_notes", []),
            "risk_notes": result.get("risk_notes", []),
            "generation": result.get("generation", {}),
            "quality_ok": result.get("quality_ok"),
            "quality_issues": result.get("quality_issues", []),
            "source_report_id": source_report_id,
            "error": None,
        }

        if action == "ask":
            set_job(
                job_id,
                status="needs_input",
                step="ask",
                message=result.get("message") or "More information is required before generation can continue.",
                progress=100,
                output_file=None,
                output_name=None,
                **common_payload,
            )
            return

        if action == "refuse":
            set_job(
                job_id,
                status="refused",
                step="refuse",
                message=result.get("message") or "The request exceeded workflow safety boundaries.",
                progress=100,
                output_file=None,
                output_name=None,
                **common_payload,
            )
            return

        generation = result.get("generation", {})
        message = "Report generated."
        if not generation.get("llm_used"):
            message = "Report generated with rule fallback."

        if source_report_id and result.get("output_file"):
            output_file = result["output_file"]
            output_path = PROJECT_ROOT / output_file
            if output_file in existing_output_backup and output_path.exists():
                generated_text = output_path.read_text(encoding="utf-8")
                output_path.write_text(existing_output_backup[output_file], encoding="utf-8")
                followup_name = f"{output_path.stem}-followup-{datetime.now().strftime('%H%M%S')}{output_path.suffix}"
                followup_path = output_path.with_name(followup_name)
                followup_path.write_text(generated_text, encoding="utf-8")
                result["output_file"] = str(followup_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                result["output_name"] = followup_path.name
                message = "Follow-up report generated."

        report_record = None
        if result.get("output_file"):
            report_record = upsert_report_record(
                result["output_file"],
                task_data=result.get("task"),
                generation=generation,
                source={
                    "entry": "workflow_server",
                    "job_id": job_id,
                    "generator": "dynamic_report_generator",
                },
            )
            if source_report_id:
                increment_followup(source_report_id)

        set_job(
            job_id,
            status="done",
            step="done",
            message=message,
            progress=100,
            output_file=result.get("output_file"),
            output_name=result.get("output_name"),
            report_record=report_record,
            **common_payload,
        )
    except Exception as exc:
        set_job(job_id, status="failed", step="error", message=str(exc), progress=100, error=str(exc))
    finally:
        RUN_LOCK.release()


class WorkflowHandler(SimpleHTTPRequestHandler):
    server_version = "AutoDailyWorkflow/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def create_job(self, prompt: str, use_llm: bool, source_report_id: str | None = None) -> dict:
        job_id = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        with JOBS_LOCK:
            JOBS[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "step": "queued",
                "message": "Job created.",
                "progress": 0,
                "prompt": prompt,
                "created_at": now_text(),
                "updated_at": now_text(),
                "parsed_task": None,
                "output_file": None,
                "output_name": None,
                "error": None,
                "source_report_id": source_report_id,
            }

        thread = threading.Thread(
            target=run_job,
            args=(job_id, prompt, use_llm, source_report_id),
            daemon=True,
        )
        thread.start()
        return {"job_id": job_id, "status": "queued"}

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()

            if parsed.path == "/api/reports/generate":
                prompt = str(payload.get("prompt") or "").strip()
                if not prompt:
                    self.send_json({"error": "Prompt is required."}, status=400)
                    return
                self.send_json(self.create_job(prompt, bool(payload.get("use_llm", True))))
                return

            if parsed.path == "/api/reports/archive":
                report_ids = payload.get("report_ids")
                if not isinstance(report_ids, list) or not report_ids:
                    self.send_json({"error": "report_ids is required."}, status=400)
                    return
                updated = archive_reports([str(item) for item in report_ids], str(payload.get("reason") or "").strip() or None)
                self.send_json({"ok": True, "updated": updated})
                return

            if parsed.path == "/api/reports/restore":
                report_ids = payload.get("report_ids")
                if not isinstance(report_ids, list) or not report_ids:
                    self.send_json({"error": "report_ids is required."}, status=400)
                    return
                updated = restore_reports([str(item) for item in report_ids])
                self.send_json({"ok": True, "updated": updated})
                return

            if parsed.path == "/api/reports/followup":
                report_id = str(payload.get("report_id") or "").strip()
                message = str(payload.get("message") or "").strip()
                if not report_id or not message:
                    self.send_json({"error": "report_id and message are required."}, status=400)
                    return
                report = get_report_record(report_id)
                if not report:
                    self.send_json({"error": "report not found"}, status=404)
                    return
                prompt = build_followup_prompt(report, message)
                self.send_json(self.create_job(prompt, bool(payload.get("use_llm", True)), source_report_id=report_id))
                return

            if parsed.path == "/api/reports/greeting":
                mode = str(payload.get("mode") or "new").strip() or "new"
                report_id = str(payload.get("report_id") or "").strip()
                report = get_report_record(report_id) if report_id else None
                if report_id and not report:
                    self.send_json({"error": "report not found"}, status=404)
                    return
                self.send_json(report_greeting_payload(report, mode=mode))
                return

            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path.startswith("/api/reports/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            job = get_job(job_id)
            if not job:
                self.send_json({"error": "job not found"}, status=404)
                return
            self.send_json(job)
            return

        if path == "/api/reports/latest":
            files = sorted((PROJECT_ROOT / "output").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            self.send_json({"reports": [p.name for p in files[:20]]})
            return

        if path == "/api/reports/list":
            filters = {
                "status": query.get("status", [None])[0],
                "report_type": query.get("report_type", [None])[0],
                "date_from": query.get("date_from", [None])[0],
                "date_to": query.get("date_to", [None])[0],
                "keyword": query.get("keyword", [None])[0],
                "brand": query.get("brand", [None])[0],
                "series": query.get("series", [None])[0],
                "page": query.get("page", [1])[0],
                "page_size": query.get("page_size", [20])[0],
            }
            self.send_json(list_report_records(filters))
            return

        if path == "/api/reports/sync":
            self.send_json(sync_report_index_from_output())
            return

        if path.startswith("/api/reports/") and path.count("/") == 3:
            report_id = path.rsplit("/", 1)[-1]
            if report_id not in {"list", "generate", "archive", "restore", "followup", "greeting", "latest", "sync"}:
                report = get_report_record(report_id)
                if not report:
                    self.send_json({"error": "report not found"}, status=404)
                    return
                self.send_json({"report": report})
                return

        if path == "/api/llm/status":
            self.send_json(llm_status_payload())
            return

        super().do_GET()


def main() -> None:
    sync_report_index_from_output()
    with ReusableThreadingHTTPServer((HOST, PORT), WorkflowHandler) as httpd:
        print(f"Local workbench server: http://127.0.0.1:{PORT}/frontend/")
        print("Generation API: POST /api/reports/generate")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
