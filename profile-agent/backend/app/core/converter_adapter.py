from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional


GRADE_TO_MID_PERCENTILE = {
    1: 98,
    2: 92,
    3: 83,
    4: 68,
    5: 50,
    6: 31,
    7: 17,
    8: 7,
    9: 2,
}


def _load_converter():
    # profile-agent/backend/app/core -> uniroad/backend
    uniroad_backend = Path(__file__).resolve().parents[4] / "backend"
    if str(uniroad_backend) not in sys.path:
        sys.path.insert(0, str(uniroad_backend))

    from services.scoring.score_converter import ScoreConverter

    return ScoreConverter()


_CONVERTER = _load_converter()


def get_converter():
    return _CONVERTER


def percentile_to_grade(percentile: float) -> int:
    if percentile >= 96:
        return 1
    if percentile >= 89:
        return 2
    if percentile >= 77:
        return 3
    if percentile >= 60:
        return 4
    if percentile >= 40:
        return 5
    if percentile >= 23:
        return 6
    if percentile >= 11:
        return 7
    if percentile >= 4:
        return 8
    return 9


def ensure_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def convert_score(
    lookup_subject: str,
    score_type: str,
    value: Any,
) -> Dict[str, Optional[int]]:
    converter = get_converter()
    out: Dict[str, Optional[int]] = {"등급": None, "표준점수": None, "백분위": None}

    if score_type == "등급":
        grade = ensure_int(value)
        if grade is None:
            return out
        out["등급"] = grade
        percentile = GRADE_TO_MID_PERCENTILE.get(grade, 50)
        result = converter.find_closest_by_percentile(lookup_subject, percentile)
        out["백분위"] = int(result["percentile"]) if result else percentile
        out["표준점수"] = int(result["standard_score"]) if result else None
        return out

    if score_type == "표준점수":
        std_score = ensure_int(value)
        if std_score is None:
            return out
        out["표준점수"] = std_score
        result = converter.find_closest_by_standard(lookup_subject, std_score)
        out["등급"] = int(result["grade"]) if result else None
        out["백분위"] = int(result["percentile"]) if result else None
        return out

    if score_type == "백분위":
        percentile = ensure_int(value)
        if percentile is None:
            return out
        out["백분위"] = percentile
        result = converter.find_closest_by_percentile(lookup_subject, percentile)
        out["등급"] = int(result["grade"]) if result else None
        out["표준점수"] = int(result["standard_score"]) if result else None
        return out

    return out

