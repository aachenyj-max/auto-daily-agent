#!/usr/bin/env python3
"""Controlled background agent runner for report generation jobs."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Callable

from agent_core import ReactAgent
from context_builder import append_runtime_entry
from tool_registry import create_tool_registry


ProgressCallback = Callable[[str, str, int], None]


def run_agent_workflow(
    prompt: str,
    api_key: str | None = None,
    use_llm: bool = True,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    progress = progress or (lambda step, message, value: None)
    run_date = datetime.now().strftime("%Y-%m-%d")
    append_runtime_entry(
        f"{run_date} Backend Agent Task Start",
        [
            f"- User request: {prompt}",
            "- Execution mode: controlled Python agent with staged whitelist tools.",
        ],
    )

    registry = create_tool_registry()
    agent = ReactAgent(registry=registry, use_llm=use_llm, max_steps=8)
    state = agent.run(prompt=prompt, api_key=api_key, progress=progress)
    result = state.get("workflow_result")

    if result is None:
        raise RuntimeError("agent finished without a workflow result")

    result["agent_trace"] = [asdict(step) for step in state.get("trace", [])]
    result["agent_context"] = state.get("agent_context", {})
    result["agent_task_context"] = state.get("task_context")

    if state.get("planner_errors"):
        notes = list(result.get("risk_notes", []))
        notes.extend(f"planner fallback: {message}" for message in state["planner_errors"])
        result["risk_notes"] = notes

    quality = state.get("quality", {})
    result["quality_ok"] = quality.get("ok", result.get("quality_ok"))
    result["quality_issues"] = quality.get("issues", result.get("quality_issues", []))

    append_runtime_entry(
        f"{run_date} Backend Agent Task Complete",
        [
            f"- User request: {prompt}",
            f"- Final action: {result.get('action')}",
            f"- Output file: {result.get('output_file')}",
            f"- Quality status: {'passed' if result.get('quality_ok') else 'needs confirmation'}",
            f"- Trace steps: {len(result.get('agent_trace', []))}",
            f"- Risk notes: {'; '.join(result.get('risk_notes', [])) if result.get('risk_notes') else 'none'}",
        ],
    )
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()
    result = run_agent_workflow(args.prompt, use_llm=not args.no_llm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
