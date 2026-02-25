from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from app.core.converter_adapter import ensure_int
from app.services.subject_codes import (
    inquiry_to_code,
    korean_to_code,
    math_to_code,
    normalize_inquiry_subject,
    normalize_korean_elective,
    normalize_math_elective,
)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    ivalue = ensure_int(value)
    if ivalue is not None:
        return str(ivalue)
    return str(value)


def to_adiga_payload(completed_scores: Dict[str, Dict[str, Any]], exam_year: int = 2026) -> Dict[str, str]:
    korean = completed_scores.get("국어", {})
    math = completed_scores.get("수학", {})
    english = completed_scores.get("영어", {})
    inquiry1 = completed_scores.get("탐구1", {})
    inquiry2 = completed_scores.get("탐구2", {})
    history = completed_scores.get("한국사", {})

    korean_elective = normalize_korean_elective(korean.get("선택과목", "화법과작문"))
    math_elective = normalize_math_elective(math.get("선택과목", "확률과통계"))
    inquiry1_name = normalize_inquiry_subject(inquiry1.get("과목명", "생활과윤리"))
    inquiry2_name = normalize_inquiry_subject(inquiry2.get("과목명", "사회문화"))

    payload = {
        "name": f"profile-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "ncxmMtstTestDayId": "94",
        "syr": str(exam_year),
        "koreanSubject": korean_to_code(korean_elective),
        "mathSubject": math_to_code(math_elective),
        "englishSubject": "S0484",
        "inquirySubject1": inquiry_to_code(inquiry1_name),
        "inquirySubject2": inquiry_to_code(inquiry2_name),
        "koreanStd": _to_str(korean.get("표준점수")),
        "koreanPrct": _to_str(korean.get("백분위")),
        "koreanGrd": _to_str(korean.get("등급")),
        "mathStd": _to_str(math.get("표준점수")),
        "mathPrct": _to_str(math.get("백분위")),
        "mathGrd": _to_str(math.get("등급")),
        "englishGrd": _to_str(english.get("등급")),
        "inquiry1Std": _to_str(inquiry1.get("표준점수")),
        "inquiry1Prct": _to_str(inquiry1.get("백분위")),
        "inquiry1Grd": _to_str(inquiry1.get("등급")),
        "inquiry2Std": _to_str(inquiry2.get("표준점수")),
        "inquiry2Prct": _to_str(inquiry2.get("백분위")),
        "inquiry2Grd": _to_str(inquiry2.get("등급")),
        "khistoryGrd": _to_str(history.get("등급") or 1),
    }
    return payload

