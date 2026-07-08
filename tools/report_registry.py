#!/usr/bin/env python3
"""Managed report index for list, archive, and follow-up workflows."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from intent_parser import ReportTask


PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
MANAGED_REPORTS_DIR = PROJECT_ROOT / "data" / "managed_reports"
INDEX_FILE = MANAGED_REPORTS_DIR / "index.json"

REPORT_TYPES = {"market", "brand", "series", "compare", "filtered"}
REPORT_STATUSES = {"active", "archived"}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def empty_index() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "reports": [],
    }


def ensure_index_file() -> None:
    MANAGED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        save_report_index(empty_index())


def load_report_index() -> dict[str, Any]:
    ensure_index_file()
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return empty_index()
    data.setdefault("version", 1)
    data.setdefault("updated_at", None)
    reports = data.get("reports")
    data["reports"] = reports if isinstance(reports, list) else []
    return data


def save_report_index(index: dict[str, Any]) -> dict[str, Any]:
    ensure_index_file()
    payload = {
        "version": index.get("version", 1),
        "updated_at": iso_now(),
        "reports": index.get("reports", []),
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def slugify(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "report"


def derive_report_type(file_name: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", file_name):
        return "market"
    for prefix, report_type in (
        ("brand-", "brand"),
        ("series-", "series"),
        ("compare-", "compare"),
        ("filtered-", "filtered"),
    ):
        if file_name.startswith(prefix):
            return report_type
    return "market"


def is_report_artifact(file_name: str) -> bool:
    if not file_name.endswith(".md"):
        return False
    if file_name == "README.md":
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", file_name):
        return True
    return bool(
        re.fullmatch(r"(brand|series|compare|filtered)-.+-20\d{2}-\d{2}-\d{2}(?:-followup-\d{6})?\.md", file_name)
        or re.fullmatch(r"(brand|series|compare|filtered)-.+-20\d{2}-\d{2}-\d{2}\.md", file_name)
        or re.fullmatch(r".+-followup-\d{6}\.md", file_name)
    )


def extract_date(value: str) -> str | None:
    match = re.search(r"20\d{2}-\d{2}-\d{2}", value)
    return match.group(0) if match else None


def read_title_excerpt(path: Path) -> tuple[str, str, int]:
    if not path.exists():
        return path.stem, "", 0
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = path.stem
    excerpt_parts: list[str] = []
    for line in lines:
        if line.startswith("#"):
            title = line.lstrip("#").strip() or title
            continue
        if line.startswith(">"):
            continue
        if line == "---":
            break
        excerpt_parts.append(line)
        if sum(len(part) for part in excerpt_parts) >= 180:
            break
    excerpt = " ".join(excerpt_parts)
    excerpt = re.sub(r"\s+", " ", excerpt).strip()[:220]
    return title, excerpt, len(text)


def summarize_filters(filters: dict[str, Any] | None) -> list[str]:
    if not isinstance(filters, dict):
        return []
    items: list[str] = []
    for key in ("body_type", "energy_type", "price_min", "price_max"):
        value = filters.get(key)
        if value is None or value == "":
            continue
        items.append(f"{key}:{value}")
    return items


def build_scope(task_data: dict[str, Any] | None, file_name: str, report_type: str) -> dict[str, Any]:
    task_data = task_data or {}
    compare_series = task_data.get("compare_series") if isinstance(task_data.get("compare_series"), list) else []
    filters = task_data.get("filters") if isinstance(task_data.get("filters"), dict) else {}
    scope = {
        "brands": [task_data["brand"]] if task_data.get("brand") else [],
        "series": [task_data["series"]] if task_data.get("series") else [],
        "comparison_pairs": compare_series[:2] if report_type == "compare" else [],
        "filters": summarize_filters(filters),
    }
    if report_type == "compare" and not scope["series"]:
        scope["series"] = compare_series[:]
    if report_type == "filtered" and not scope["filters"]:
        stem = Path(file_name).stem
        parts = stem.split("-")
        scope["filters"] = parts[1:-1] if len(parts) > 2 else []
    return scope


def report_id_for(file_name: str, report_type: str, date: str | None) -> str:
    stem = Path(file_name).stem
    return f"rpt_{date or 'unknown'}_{report_type}_{slugify(stem)}"


def build_report_record_from_file(
    path: Path,
    existing: dict[str, Any] | None = None,
    task_data: dict[str, Any] | None = None,
    generation: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    existing = existing or {}
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    file_name = path.name
    report_type = derive_report_type(file_name)
    date = extract_date(file_name)
    title, excerpt, word_count = read_title_excerpt(path)
    created_at = existing.get("created_at") or iso_now()
    updated_at = iso_now()
    file_stat = path.stat()
    conversation = deepcopy(existing.get("conversation", {}))
    conversation.setdefault("continuable", True)
    conversation.setdefault("last_followup_at", None)
    conversation.setdefault("followup_count", 0)
    if task_data and task_data.get("source_prompt") and not conversation.get("base_prompt"):
        conversation["base_prompt"] = task_data["source_prompt"]
    elif not conversation.get("base_prompt"):
        conversation["base_prompt"] = title

    status = existing.get("status", "active")
    if status not in REPORT_STATUSES:
        status = "active"

    record = {
        "report_id": existing.get("report_id") or report_id_for(file_name, report_type, date),
        "file_name": file_name,
        "file_path": relative_path,
        "report_type": report_type if report_type in REPORT_TYPES else "market",
        "date": date,
        "title": title,
        "status": status,
        "deleted_at": existing.get("deleted_at"),
        "archived_reason": existing.get("archived_reason"),
        "created_at": created_at,
        "updated_at": updated_at,
        "file_mtime": datetime.fromtimestamp(file_stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "source": {
            "entry": (source or {}).get("entry") or existing.get("source", {}).get("entry") or "workflow_server",
            "job_id": (source or {}).get("job_id") or existing.get("source", {}).get("job_id"),
            "generator": (source or {}).get("generator") or existing.get("source", {}).get("generator") or "dynamic_report_generator",
            "llm_used": bool((generation or {}).get("llm_used", existing.get("source", {}).get("llm_used", False))),
        },
        "scope": build_scope(task_data or existing.get("task"), file_name, report_type),
        "conversation": conversation,
        "summary": {
            "excerpt": excerpt,
            "word_count": word_count,
        },
        "task": task_data or existing.get("task"),
    }
    return record


def index_by_report_id(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for record in index.get("reports", []):
        report_id = record.get("report_id")
        if report_id:
            mapping[report_id] = record
    return mapping


def index_by_file_name(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for record in index.get("reports", []):
        file_name = record.get("file_name")
        if file_name:
            mapping[file_name] = record
    return mapping


def sync_report_index_from_output() -> dict[str, Any]:
    index = load_report_index()
    existing_by_name = index_by_file_name(index)
    synced: list[dict[str, Any]] = []
    for path in sorted(OUTPUT_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not is_report_artifact(path.name):
            continue
        existing = existing_by_name.get(path.name)
        synced.append(build_report_record_from_file(path, existing=existing))
    index["reports"] = synced
    return save_report_index(index)


def upsert_report_record(
    file_path: str,
    task_data: dict[str, Any] | None = None,
    generation: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = load_report_index()
    by_name = index_by_file_name(index)
    path = PROJECT_ROOT / file_path
    existing = by_name.get(path.name)
    record = build_report_record_from_file(path, existing=existing, task_data=task_data, generation=generation, source=source)
    reports = [item for item in index.get("reports", []) if item.get("file_name") != path.name]
    reports.insert(0, record)
    index["reports"] = reports
    save_report_index(index)
    return record


def get_report_record(report_id: str) -> dict[str, Any] | None:
    index = sync_report_index_from_output()
    return index_by_report_id(index).get(report_id)


def matches_keyword(record: dict[str, Any], keyword: str) -> bool:
    haystack = " ".join(
        [
            record.get("title", ""),
            record.get("file_name", ""),
            " ".join(record.get("scope", {}).get("brands", [])),
            " ".join(record.get("scope", {}).get("series", [])),
            " ".join(record.get("scope", {}).get("filters", [])),
            record.get("summary", {}).get("excerpt", ""),
        ]
    ).lower()
    return keyword.lower() in haystack


def list_report_records(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    index = sync_report_index_from_output()
    records = index.get("reports", [])

    status = filters.get("status")
    report_type = filters.get("report_type")
    keyword = str(filters.get("keyword") or "").strip()
    brand = str(filters.get("brand") or "").strip()
    series = str(filters.get("series") or "").strip()
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    page = max(1, int(filters.get("page") or 1))
    page_size = max(1, min(100, int(filters.get("page_size") or 20)))

    filtered: list[dict[str, Any]] = []
    for record in records:
        if status and record.get("status") != status:
            continue
        if report_type and record.get("report_type") != report_type:
            continue
        if date_from and record.get("date") and record["date"] < date_from:
            continue
        if date_to and record.get("date") and record["date"] > date_to:
            continue
        if brand and brand not in " ".join(record.get("scope", {}).get("brands", [])):
            continue
        if series and series not in " ".join(record.get("scope", {}).get("series", [])):
            continue
        if keyword and not matches_keyword(record, keyword):
            continue
        filtered.append(record)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": filtered[start:end],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }


def archive_reports(report_ids: list[str], reason: str | None = None) -> int:
    if not report_ids:
        return 0
    index = load_report_index()
    count = 0
    for record in index.get("reports", []):
        if record.get("report_id") not in report_ids:
            continue
        record["status"] = "archived"
        record["deleted_at"] = iso_now()
        record["archived_reason"] = reason or "manual archive"
        record["updated_at"] = iso_now()
        count += 1
    save_report_index(index)
    return count


def restore_reports(report_ids: list[str]) -> int:
    if not report_ids:
        return 0
    index = load_report_index()
    count = 0
    for record in index.get("reports", []):
        if record.get("report_id") not in report_ids:
            continue
        record["status"] = "active"
        record["deleted_at"] = None
        record["archived_reason"] = None
        record["updated_at"] = iso_now()
        count += 1
    save_report_index(index)
    return count


def increment_followup(report_id: str) -> None:
    index = load_report_index()
    for record in index.get("reports", []):
        if record.get("report_id") != report_id:
            continue
        conversation = record.setdefault("conversation", {})
        conversation["followup_count"] = int(conversation.get("followup_count") or 0) + 1
        conversation["last_followup_at"] = iso_now()
        record["updated_at"] = iso_now()
        break
    save_report_index(index)


def build_followup_prompt(record: dict[str, Any], message: str) -> str:
    title = record.get("title") or record.get("file_name") or "当前报告"
    date = record.get("date") or "unknown date"
    scope = record.get("scope", {})
    scope_parts: list[str] = []
    if scope.get("brands"):
        scope_parts.append(f"品牌：{'、'.join(scope['brands'])}")
    if scope.get("series"):
        scope_parts.append(f"车型：{'、'.join(scope['series'])}")
    if scope.get("comparison_pairs"):
        scope_parts.append(f"对比：{'、'.join(scope['comparison_pairs'])}")
    if scope.get("filters"):
        scope_parts.append(f"筛选：{'、'.join(scope['filters'])}")
    scope_text = "；".join(scope_parts) if scope_parts else "无"
    base_prompt = record.get("conversation", {}).get("base_prompt") or title
    excerpt = record.get("summary", {}).get("excerpt") or ""
    return (
        f"基于已生成报告继续分析。\n"
        f"原报告标题：{title}\n"
        f"原报告日期：{date}\n"
        f"原报告类型：{record.get('report_type')}\n"
        f"原始任务：{base_prompt}\n"
        f"报告范围：{scope_text}\n"
        f"报告摘要：{excerpt}\n"
        f"新的补充要求：{message}\n"
        f"请延续原报告上下文生成新的受控日报任务，不要脱离上述日期和对象。"
    )


def build_followup_task(record: dict[str, Any], message: str) -> ReportTask:
    task_data = record.get("task") or {}
    report_type = task_data.get("report_type") or record.get("report_type") or "market"
    compare_series = task_data.get("compare_series") if isinstance(task_data.get("compare_series"), list) else []
    filters = deepcopy(task_data.get("filters")) if isinstance(task_data.get("filters"), dict) else {}
    prompt = build_followup_prompt(record, message)
    return ReportTask(
        action="run",
        report_type=report_type,
        date=task_data.get("date") or record.get("date") or datetime.now().strftime("%Y-%m-%d"),
        brand=task_data.get("brand"),
        series=task_data.get("series"),
        compare_series=compare_series,
        filters=filters,
        focus=[message],
        source_prompt=prompt,
        workflow_notes=["follow-up request based on managed report context"],
    )
