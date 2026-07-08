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
from llm_client import load_llm_config
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
            if report_id not in {"list", "generate", "archive", "restore", "followup", "latest", "sync"}:
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
