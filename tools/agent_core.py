#!/usr/bin/env python3
"""Bounded ReAct-style controller for the local report agent."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from llm_client import chat_completion, load_llm_config


CONFIG_DIR = Path(__file__).parent.parent / "config"


@dataclass
class TraceStep:
    step: int
    decision_source: str
    thought: str
    tool: str
    observation: str


def load_agent_react_prompt() -> str:
    path = CONFIG_DIR / "agent_react_prompt.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "You are the workflow control model for a local automotive report agent. "
        "Choose exactly one next tool from the allowed tool list. "
        "Return JSON only with keys tool and thought. "
        "Do not invent tools."
    )


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    task = state.get("candidate_task")
    result = state.get("workflow_result")
    artifact = state.get("generation_artifact")
    return {
        "prompt": state["prompt"],
        "use_llm": state["use_llm"],
        "has_context": "agent_context" in state,
        "candidate_task": asdict(task) if task else None,
        "data_status": state.get("data_status"),
        "task_context": state.get("task_context"),
        "generation_artifact": {
            "ready": bool(artifact),
            "output_name": artifact["output"].name if artifact else None,
        },
        "workflow_action": result.get("action") if result else None,
        "quality": state.get("quality"),
    }


class ReactAgent:
    def __init__(self, registry: dict[str, Any], use_llm: bool, max_steps: int = 8) -> None:
        self.registry = registry
        self.use_llm = use_llm
        self.max_steps = max_steps
        self.react_prompt = load_agent_react_prompt()

    def available_tools(self, state: dict[str, Any]) -> list[str]:
        task = state.get("candidate_task")

        if "quality" in state:
            return []
        if "agent_context" not in state:
            return ["read_context"]
        if task is None:
            return ["inspect_request"]
        if task.action != "run" and "workflow_result" not in state:
            return ["finalize_non_run"]
        if state.get("data_status") is None:
            return ["inspect_data"]
        if not state["data_status"].get("processed_exists") or (
            task.date == state["data_status"].get("date") and not state["data_status"].get("raw_exists")
        ):
            return ["prepare_data"]
        if "task_context" not in state:
            return ["build_context", "prepare_data"]
        if "generation_artifact" not in state:
            return ["generate_report"]
        if "workflow_result" not in state:
            return ["validate_report"]
        return ["quality_check"]

    def fallback_tool(self, state: dict[str, Any]) -> tuple[str, str]:
        available = self.available_tools(state)
        if not available:
            return "", "workflow complete"
        return available[0], "fallback policy selected the next required tool"

    def plan_with_llm(self, state: dict[str, Any], available: list[str]) -> tuple[str, str]:
        config = load_llm_config(profile="workflow")
        if not self.use_llm or not config.ready:
            return self.fallback_tool(state)

        payload = {
            "allowed_tools": available,
            "state": summarize_state(state),
        }
        content = chat_completion(
            [
                {"role": "system", "content": self.react_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            profile="workflow",
            temperature=0.1,
            max_tokens=300,
            timeout=45,
        )
        match = re.search(r"\{.*\}", content, re.S)
        raw = json.loads(match.group(0) if match else content)
        tool = raw.get("tool")
        thought = raw.get("thought") or "workflow model selected the next tool"
        if tool not in available:
            return self.fallback_tool(state)
        return tool, thought

    def run(self, prompt: str, api_key: str | None, progress) -> dict[str, Any]:
        state: dict[str, Any] = {
            "prompt": prompt,
            "api_key": api_key,
            "use_llm": self.use_llm,
            "trace": [],
        }

        for step_number in range(1, self.max_steps + 1):
            available = self.available_tools(state)
            if not available:
                break

            source = "workflow-llm"
            try:
                tool_name, thought = self.plan_with_llm(state, available)
            except Exception as exc:
                tool_name, thought = self.fallback_tool(state)
                source = "fallback"
                state.setdefault("planner_errors", []).append(str(exc))
            else:
                if tool_name not in available:
                    tool_name, thought = self.fallback_tool(state)
                    source = "fallback"

            if source != "fallback" and thought == "fallback policy selected the next required tool":
                source = "fallback"

            observation = self.registry[tool_name].run(state, progress)
            state["trace"].append(
                TraceStep(
                    step=step_number,
                    decision_source=source,
                    thought=thought,
                    tool=tool_name,
                    observation=observation.summary,
                )
            )

        return state
