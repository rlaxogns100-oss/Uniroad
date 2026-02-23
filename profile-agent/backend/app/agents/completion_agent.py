from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Any, Dict, List, Tuple

from app.core.converter_adapter import (
    GRADE_TO_MID_PERCENTILE,
    convert_score,
    ensure_int,
    percentile_to_grade,
)
from app.services.subject_codes import (
    normalize_inquiry_subject,
    normalize_korean_elective,
    normalize_math_elective,
)


class CompletionAgent:
    """
    누락 과목 보완/추정 에이전트.
    router-agent.py / score_preprocessing.py의 규칙을 따라
    평균 백분위 기반으로 필수 과목을 보완한다.
    """

    REQUIRED_SUBJECTS = ["국어", "수학", "영어", "한국사", "탐구1", "탐구2"]

    DEFAULTS = {
        "국어_선택과목": "화법과작문",
        "수학_선택과목": "확률과통계",
        "영어_선택과목": "영어",
        "탐구1_과목명": "생활과윤리",
        "탐구2_과목명": "윤리와사상",
    }

    def complete(self, extracted_scores: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
        scores = deepcopy(extracted_scores or {})
        estimated_subjects: List[str] = []

        self._apply_defaults(scores)

        for subject in list(scores.keys()):
            scores[subject] = self._enrich_subject(subject, scores[subject])

        avg_percentile = self._calculate_avg_percentile(scores)

        for subject in self.REQUIRED_SUBJECTS:
            if subject in scores:
                continue
            scores[subject] = self._estimate_subject(subject, avg_percentile)
            estimated_subjects.append(subject)

        # 한국사 기본 추정 규칙 (미언급 시 1등급)
        if "한국사" not in scores:
            scores["한국사"] = {
                "type": "등급",
                "value": 1,
                "등급": 1,
                "표준점수": None,
                "백분위": None,
                "추정됨": True,
                "추정_기준": "미언급 기본값",
            }
            estimated_subjects.append("한국사")

        self._apply_defaults(scores)
        return scores, estimated_subjects

    def _apply_defaults(self, scores: Dict[str, Dict[str, Any]]) -> None:
        if "국어" in scores:
            scores["국어"]["선택과목"] = normalize_korean_elective(
                scores["국어"].get("선택과목", self.DEFAULTS["국어_선택과목"])
            )
        if "수학" in scores:
            scores["수학"]["선택과목"] = normalize_math_elective(
                scores["수학"].get("선택과목", self.DEFAULTS["수학_선택과목"])
            )
        if "영어" in scores:
            scores["영어"]["선택과목"] = scores["영어"].get("선택과목", self.DEFAULTS["영어_선택과목"])
        if "탐구1" in scores:
            scores["탐구1"]["과목명"] = normalize_inquiry_subject(
                scores["탐구1"].get("과목명", self.DEFAULTS["탐구1_과목명"])
            )
        if "탐구2" in scores:
            scores["탐구2"]["과목명"] = normalize_inquiry_subject(
                scores["탐구2"].get("과목명", self.DEFAULTS["탐구2_과목명"])
            )

    def _enrich_subject(self, subject: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        enriched = deepcopy(entry)

        score_type, value = self._resolve_primary_score(enriched)
        if score_type is None or value is None:
            return enriched

        enriched["type"] = score_type
        enriched["value"] = ensure_int(value)

        if subject in {"영어", "한국사"}:
            grade = ensure_int(value)
            enriched["등급"] = grade
            enriched["표준점수"] = None
            enriched["백분위"] = None
            return enriched

        lookup_subject = self._lookup_subject(subject, enriched)
        converted = convert_score(lookup_subject, score_type, value)

        if score_type == "등급":
            enriched["등급"] = ensure_int(value)
            enriched["백분위"] = converted.get("백분위") or GRADE_TO_MID_PERCENTILE.get(
                ensure_int(value) or 3, 83
            )
            enriched["표준점수"] = converted.get("표준점수")
        elif score_type == "표준점수":
            enriched["표준점수"] = ensure_int(value)
            enriched["등급"] = enriched.get("등급") or converted.get("등급")
            enriched["백분위"] = enriched.get("백분위") or converted.get("백분위")
        elif score_type == "백분위":
            enriched["백분위"] = ensure_int(value)
            enriched["등급"] = enriched.get("등급") or converted.get("등급")
            enriched["표준점수"] = enriched.get("표준점수") or converted.get("표준점수")

        return enriched

    def _resolve_primary_score(self, entry: Dict[str, Any]) -> Tuple[str | None, Any]:
        if entry.get("type") and entry.get("value") is not None:
            return entry["type"], entry["value"]

        if entry.get("표준점수") is not None:
            return "표준점수", entry["표준점수"]
        if entry.get("백분위") is not None:
            return "백분위", entry["백분위"]
        if entry.get("등급") is not None:
            return "등급", entry["등급"]
        return None, None

    def _lookup_subject(self, subject: str, entry: Dict[str, Any]) -> str:
        if subject == "탐구1":
            return normalize_inquiry_subject(entry.get("과목명", self.DEFAULTS["탐구1_과목명"]))
        if subject == "탐구2":
            return normalize_inquiry_subject(entry.get("과목명", self.DEFAULTS["탐구2_과목명"]))
        return subject

    @staticmethod
    def _calculate_avg_percentile(scores: Dict[str, Dict[str, Any]]) -> float | None:
        percentiles: List[int] = []
        for subject, score in scores.items():
            if subject in {"영어", "한국사"}:
                continue
            value = ensure_int(score.get("백분위"))
            if value is not None:
                percentiles.append(value)
        if not percentiles:
            return None
        return float(mean(percentiles))

    def _estimate_subject(self, subject: str, avg_percentile: float | None) -> Dict[str, Any]:
        base_percentile = int(round(avg_percentile)) if avg_percentile is not None else 83

        if subject == "한국사":
            return {
                "type": "등급",
                "value": 1,
                "등급": 1,
                "표준점수": None,
                "백분위": None,
                "추정됨": True,
                "추정_기준": "미언급 기본값",
            }

        if subject == "영어":
            grade = percentile_to_grade(base_percentile)
            return {
                "type": "등급",
                "value": grade,
                "등급": grade,
                "표준점수": None,
                "백분위": None,
                "추정됨": True,
                "추정_기준": f"평균 백분위 {base_percentile} 기반",
            }

        template: Dict[str, Any] = {"type": "백분위", "value": base_percentile, "추정됨": True}
        if subject == "탐구1":
            template["과목명"] = self.DEFAULTS["탐구1_과목명"]
        if subject == "탐구2":
            template["과목명"] = self.DEFAULTS["탐구2_과목명"]
        if subject == "국어":
            template["선택과목"] = self.DEFAULTS["국어_선택과목"]
        if subject == "수학":
            template["선택과목"] = self.DEFAULTS["수학_선택과목"]

        enriched = self._enrich_subject(subject, template)
        enriched["추정됨"] = True
        enriched["추정_기준"] = f"평균 백분위 {base_percentile} 기반"
        return enriched

