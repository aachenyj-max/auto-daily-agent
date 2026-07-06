#!/usr/bin/env python3
"""Local frontend + workflow API server."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from workflow_runner import PROJECT_ROOT, run_workflow


HOST = "127.0.0.1"
PORT = 8080
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
RUN_LOCK = threading.Lock()


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


def run_job(job_id: str, prompt: str, api_key: str | None, use_llm: bool) -> None:
    def progress(step: str, message: str, progress_value: int) -> None:
        set_job(job_id, status="running", step=step, message=message, progress=progress_value)

    acquired = RUN_LOCK.acquire(blocking=False)
    if not acquired:
        set_job(job_id, status="failed", step="queued", message="已有生成任务正在运行，请稍后再试", error="workflow busy")
        return
    try:
        result = run_workflow(prompt, api_key=api_key, use_llm=use_llm, progress=progress)
        set_job(
            job_id,
            status="done",
            step="done",
            message="报告已生成",
            progress=100,
            result=result,
            output_file=result["output_file"],
            output_name=result["output_name"],
            parsed_task=result["task"],
            error=None,
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

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/reports/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self.send_json({"error": "请输入生成需求"}, status=400)
                return
            job_id = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            with JOBS_LOCK:
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "step": "queued",
                    "message": "任务已创建",
                    "progress": 0,
                    "prompt": prompt,
                    "created_at": now_text(),
                    "updated_at": now_text(),
                    "parsed_task": None,
                    "output_file": None,
                    "output_name": None,
                    "error": None,
                }
            thread = threading.Thread(
                target=run_job,
                args=(job_id, prompt, payload.get("api_key"), bool(payload.get("use_llm"))),
                daemon=True,
            )
            thread.start()
            self.send_json({"job_id": job_id, "status": "queued"})
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
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
        super().do_GET()


def main() -> None:
    with ThreadingHTTPServer((HOST, PORT), WorkflowHandler) as httpd:
        print(f"服务已启动：http://{HOST}:{PORT}/frontend/")
        print("生成 API：POST /api/reports/generate")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")


if __name__ == "__main__":
    main()
