#!/usr/bin/env python3
"""Controlled tool registry for the local report agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from context_builder import build_task_context, read_agent_context_metadata
from dynamic_report_generator import find_model, load_processed, normalize_model_query
from intent_parser import ReportTask, parse_intent
from workflow_runner import (
    PROJECT_ROOT,
    build_non_run_result,
    ensure_daily_data,
    finalize_run_result,
    generate_task_report,
    inspect_data_artifacts,
)


ProgressCallback = Callable[[str, str, int], None]


@dataclass
class ToolObservation:
    summary: str
    payload: dict[str, Any]


@dataclass
class AgentTool:
    name: str
    description: str
    run: Callable[[dict[str, Any], ProgressCallback], ToolObservation]


def report_text(output_file: str | None) -> str:
    if not output_file:
        return ""
    path = PROJECT_ROOT / output_file
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def check_report_quality(result: dict[str, Any]) -> tuple[bool, list[str]]:
    task = result.get("task", {})
    output_file = result.get("output_file")
    content = report_text(output_file)
    issues: list[str] = []

    if result.get("action") != "run":
        return True, []
    if not output_file or not content.strip():
        issues.append("Generated report file is missing or empty.")
        return False, issues

    report_type = task.get("report_type")
    if report_type == "series":
        series = task.get("series")
        date = task.get("date")
        if series and date:
            try:
                data = load_processed(date)
                model = find_model(data, series)
            except Exception as exc:
                model = None
                issues.append(f"Could not validate model targeting against processed data: {exc}")
            if model:
                expected_name = model.get("name") or series
                if expected_name and expected_name not in content:
                    issues.append(f"Report body does not clearly mention the target series: {expected_name}.")
                query = normalize_model_query(series)
                actual = normalize_model_query(expected_name)
                if query and actual and query != actual:
                    issues.append(f"Series match drift detected: requested {series}, matched {expected_name}.")
                if query == "p7" and "P7+" in content.splitlines()[0]:
                    issues.append("Report title appears to have drifted from P7 to P7+.")

    if "API Key" in content or "sk-" in content:
        issues.append("Report appears to contain sensitive credential text.")
    if "Traceback" in content or "LLM HTTP" in content:
        issues.append("Report body contains internal error details.")
    return not issues, issues


def _task_summary(task: ReportTask) -> str:
    subject = task.series or task.brand or (", ".join(task.compare_series) if task.compare_series else "market")
    return f"{task.report_type}:{subject}@{task.date}"


def tool_read_context(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    progress("context", "Reading collaboration context metadata", 3)
    metadata = read_agent_context_metadata()
    state["agent_context"] = metadata
    return ToolObservation(
        summary=f"loaded {len(metadata)} context files",
        payload={"files": list(metadata.keys())},
    )


def tool_inspect_request(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    progress("plan", "Parsing the request into a candidate task", 10)
    task = parse_intent(state["prompt"], api_key=state.get("api_key"), use_llm=state["use_llm"])
    state["candidate_task"] = task
    return ToolObservation(
        summary=_task_summary(task),
        payload={"task": asdict(task)},
    )


def tool_finalize_non_run(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    progress(task.action, task.clarifying_question or task.action, 100)
    result = build_non_run_result(task, use_llm=state["use_llm"])
    state["workflow_result"] = result
    state["quality"] = {"ok": True, "issues": []}
    return ToolObservation(
        summary=f"task ended with action={task.action}",
        payload={"action": task.action, "message": result.get("message")},
    )


def tool_inspect_data(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    progress("inspect", f"Checking data availability for {task.date}", 18)
    status = inspect_data_artifacts(task.date)
    state["data_status"] = status
    return ToolObservation(
        summary=f"raw={status['raw_exists']} processed={status['processed_exists']} enriched={status['enriched_exists']}",
        payload=status,
    )


def tool_prepare_data(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    progress("prepare", "Ensuring required data artifacts exist", 24)
    status = ensure_daily_data(task, progress)
    state["data_status"] = status
    return ToolObservation(
        summary=f"prepared raw={status['raw_exists']} processed={status['processed_exists']} enriched={status['enriched_exists']}",
        payload=status,
    )


def tool_build_context(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    progress("context", "Building structured task context", 30)
    context = build_task_context(task)
    state["task_context"] = context
    return ToolObservation(
        summary=f"context ready for {task.report_type}",
        payload=context,
    )


def tool_generate_report(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    progress("workflow", "Generating the report through the whitelist path", 45)
    output, content, generation = generate_task_report(
        task,
        api_key=state.get("api_key"),
        use_llm=state["use_llm"],
        progress=progress,
    )
    state["generation_artifact"] = {
        "output": output,
        "content": content,
        "generation": generation,
    }
    return ToolObservation(
        summary=f"generated {Path(output).name}",
        payload={
            "output_name": Path(output).name,
            "size": len(content),
            "llm_used": generation.get("llm_used"),
        },
    )


def tool_validate_report(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    task: ReportTask = state["candidate_task"]
    artifact = state["generation_artifact"]
    result = finalize_run_result(
        task,
        artifact["output"],
        artifact["content"],
        artifact["generation"],
        progress=progress,
    )
    state["workflow_result"] = result
    return ToolObservation(
        summary=f"validated action={result.get('action')}",
        payload={
            "output_name": result.get("output_name"),
            "validation": result.get("validation"),
        },
    )


def tool_quality_check(state: dict[str, Any], progress: ProgressCallback) -> ToolObservation:
    progress("quality", "Checking report quality and safety boundaries", 96)
    result = state["workflow_result"]
    ok, issues = check_report_quality(result)
    notes = list(result.get("workflow_notes", []))
    risk_notes = list(result.get("risk_notes", []))
    notes.append("Background agent completed staged workflow execution and quality review.")
    risk_notes.extend(issues)
    result["workflow_notes"] = notes
    result["risk_notes"] = risk_notes
    result["quality_ok"] = ok
    result["quality_issues"] = issues

    if result.get("action") == "run" and not ok:
        result["action"] = "ask"
        result["message"] = "Quality review found issues. Confirm whether the backend agent may rerun after adjustment."
        task = result.get("task", {})
        task["action"] = "ask"
        task["clarifying_question"] = result["message"]
        task["risk_notes"] = risk_notes
        task["workflow_notes"] = notes
        result["task"] = task

    state["workflow_result"] = result
    state["quality"] = {"ok": ok, "issues": issues}
    return ToolObservation(
        summary="quality passed" if ok else "quality requires confirmation",
        payload=state["quality"],
    )


def create_tool_registry() -> dict[str, AgentTool]:
    tools = [
        AgentTool("read_context", "Read required collaboration context metadata.", tool_read_context),
        AgentTool("inspect_request", "Parse the request into a candidate report task.", tool_inspect_request),
        AgentTool("finalize_non_run", "Return a clarification or refusal result without generation.", tool_finalize_non_run),
        AgentTool("inspect_data", "Check raw, processed, and enriched data availability.", tool_inspect_data),
        AgentTool("prepare_data", "Create missing same-day data artifacts via the whitelist scripts.", tool_prepare_data),
        AgentTool("build_context", "Build structured task context for the selected task.", tool_build_context),
        AgentTool("generate_report", "Generate the report for the planned task.", tool_generate_report),
        AgentTool("validate_report", "Validate report output artifacts.", tool_validate_report),
        AgentTool("quality_check", "Validate the generated report for targeting and safety.", tool_quality_check),
    ]
    return {tool.name: tool for tool in tools}
