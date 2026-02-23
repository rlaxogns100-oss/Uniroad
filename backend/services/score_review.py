"""
Profile-agent bridge + score review helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import asyncio
import importlib
import re
import sys

from services.supabase_client import supabase_service


SUBJECT_ORDER = ["한국사", "국어", "수학", "영어", "탐구1", "탐구2", "제2외국어/한문"]


@dataclass
class ScoreCandidate:
    has_candidate: bool
    extracted_scores: Dict[str, Any]
    completed_scores: Dict[str, Any]
    title_auto: str


def _ensure_profile_agent_import_path() -> None:
    root = Path(__file__).resolve().parents[2]
    profile_backend = root / "profile-agent" / "backend"
    target = str(profile_backend)
    if target not in sys.path:
        sys.path.insert(0, target)


def _normalize_auto_title(raw: str) -> str:
    if not raw:
        return "@내성적1"
    trimmed = raw.strip()
    if not trimmed.startswith("@"):
        trimmed = f"@{trimmed}"
    return trimmed[:11]


def _has_score_value(scores: Dict[str, Any]) -> bool:
    for subject in SUBJECT_ORDER:
        entry = scores.get(subject)
        if not isinstance(entry, dict):
            continue
        for key in ("선택과목", "표준점수", "백분위", "등급"):
            value = entry.get(key)
            if value is not None and value != "" and value != "-":
                return True
    return False


def _next_score_title(existing: list[Dict[str, Any]]) -> str:
    pattern = re.compile(r"^내성적(\d+)$")
    used = set()
    for row in existing:
        name = str(row.get("name", ""))
        if name.startswith("@"):
            name = name[1:]
        match = pattern.match(name)
        if match:
            used.add(int(match.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"@내성적{n}"


def extract_score_candidate(message: str, existing_score_sets: list[Dict[str, Any]]) -> ScoreCandidate:
    """
    Run profile-agent extractor/completion in-process.
    Returns empty candidate on any bridge failure.
    """
    _ensure_profile_agent_import_path()
    try:
        extractor_module = importlib.import_module("app.agents.extractor_agent")
        completion_module = importlib.import_module("app.agents.completion_agent")
        extractor = extractor_module.ExtractorAgent()
        completion = completion_module.CompletionAgent()
        extracted = extractor.extract((message or "").strip())
        extracted_scores = extracted.get("scores", {}) if isinstance(extracted, dict) else {}
        completion_input = extracted.get("scores_for_completion", {}) if isinstance(extracted, dict) else {}
        completed_scores, _estimated = completion.complete(completion_input or {})
        has_candidate = _has_score_value(extracted_scores)
        auto_title = _next_score_title(existing_score_sets)
        return ScoreCandidate(
            has_candidate=has_candidate,
            extracted_scores=extracted_scores,
            completed_scores=completed_scores,
            title_auto=_normalize_auto_title(auto_title),
        )
    except Exception as error:  # noqa: BLE001
        print(f"⚠️ profile-agent bridge 실패: {error}")
        return ScoreCandidate(
            has_candidate=False,
            extracted_scores={},
            completed_scores={},
            title_auto="@내성적1",
        )


def to_consult_j_scores(scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert fixed score schema -> consult_jungsi schema.
    """
    converted: Dict[str, Any] = {}
    for subject, entry in (scores or {}).items():
        if not isinstance(entry, dict):
            continue
        score_type: Optional[str] = None
        score_value: Optional[int] = None
        if entry.get("표준점수") is not None:
            score_type = "표준점수"
            score_value = int(entry["표준점수"])
        elif entry.get("백분위") is not None:
            score_type = "백분위"
            score_value = int(entry["백분위"])
        elif entry.get("등급") is not None:
            score_type = "등급"
            score_value = int(entry["등급"])
        if score_type is None or score_value is None:
            continue
        payload: Dict[str, Any] = {"type": score_type, "value": score_value}
        if entry.get("등급") is not None:
            payload["등급"] = int(entry["등급"])
        if entry.get("표준점수") is not None:
            payload["표준점수"] = int(entry["표준점수"])
        if entry.get("백분위") is not None:
            payload["백분위"] = int(entry["백분위"])
        if entry.get("선택과목"):
            payload["선택과목"] = entry["선택과목"]
        converted[subject] = payload
    return converted


def parse_score_name_tokens(message: str) -> list[str]:
    tokens = re.findall(r"@([가-힣a-zA-Z0-9_]{1,10})", message or "")
    dedup: list[str] = []
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            dedup.append(token)
    return dedup


async def resolve_score_id_from_message(user_id: Optional[str], message: str) -> Optional[str]:
    if not user_id:
        return None
    score_names = parse_score_name_tokens(message)
    if not score_names:
        return None
    for name in score_names:
        row = await supabase_service.get_user_score_set_by_name(user_id, name)
        if row and row.get("id"):
            return str(row["id"])
    return None


async def run_router_and_profile_parallel(
    router_coro,
    message: str,
    existing_score_sets: list[Dict[str, Any]],
):
    profile_task = asyncio.to_thread(extract_score_candidate, message, existing_score_sets)
    return await asyncio.gather(router_coro, profile_task)
