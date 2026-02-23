from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import google.generativeai as genai
from dotenv import load_dotenv

from app.services.subject_codes import INQUIRY_ALIASES


TYPE_PRIORITY = {"등급": 1, "백분위": 2, "표준점수": 3}


class ExtractorAgent:
    """
    Gemini 2.5 Flash Lite 기반 성적 추출기.
    - 고정 JSON 폼을 강제하고 채울 수 있는 값만 채움
    - completion 단계용 입력(scores_for_completion)을 별도 생성
    """

    MODEL_NAME = "gemini-2.5-flash-lite"
    SUBJECTS = ("한국사", "국어", "수학", "영어", "탐구1", "탐구2", "제2외국어/한문")
    KOREAN_ELECTIVE_MAP = {
        "화작": "화법과작문",
        "화법과작문": "화법과작문",
        "언매": "언어와매체",
        "언어와매체": "언어와매체",
    }
    MATH_ELECTIVE_MAP = {
        "확통": "확률과통계",
        "확률과통계": "확률과통계",
        "미적": "미적분",
        "미적분": "미적분",
        "기하": "기하",
    }
    ENGLISH_ELECTIVE_MAP = {"영어": "영어", "미응시": "미응시"}
    INQUIRY_OPTIONS = {
        "한국지리",
        "윤리와사상",
        "생활과윤리",
        "사회문화",
        "정치와법",
        "경제",
        "세계사",
        "동아시아사",
        "세계지리",
        "물리학1",
        "물리학2",
        "화학1",
        "화학2",
        "생명과학1",
        "생명과학2",
        "지구과학1",
        "지구과학2",
        "미응시",
    }
    SECOND_LANGUAGE_OPTIONS = {
        "독일어1",
        "프랑스어1",
        "스페인어1",
        "중국어1",
        "일본어1",
        "러시아어1",
        "아랍어1",
        "베트남어1",
        "한문1",
        "미응시",
    }

    def __init__(self) -> None:
        profile_agent_root = Path(__file__).resolve().parents[3]
        uniroad_root = Path(__file__).resolve().parents[4]
        load_dotenv(profile_agent_root / ".env", override=False)
        load_dotenv(profile_agent_root / "backend" / ".env", override=False)
        load_dotenv(uniroad_root / "backend" / ".env", override=False)
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = None

    def extract(self, message: str) -> Dict[str, Any]:
        text = (message or "").strip()
        if not text:
            fixed = self._empty_fixed_scores()
            return {"scores": fixed, "scores_for_completion": {}, "evidences": []}

        raw = self._call_llm_for_json(text)
        return self._sanitize_output(raw)

    def _call_llm_for_json(self, message: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY 또는 GOOGLE_API_KEY 환경변수가 필요합니다.")
        if self.model is None:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.MODEL_NAME)

        prompt = f"""
너는 한국 수능 성적 정보 추출기다.
반드시 아래 JSON 객체 하나만 출력하라. 설명, 코드블록, 추가 텍스트 금지.

규칙:
1) 사용자가 명시적으로 말한 값만 채우고 값이 없으면 null로 둔다.
2) 반드시 아래 고정 폼의 출력 형식을 준수한다.
3) 선택과목은 허용 선택지 중 하나만 사용한다.
4) 축약형 등급 추정: 11433(5자리->국어,수학,영어,탐구1,탐구2) 424542(6자리 -> 한국사,수학,영어,탐구1,탐구2)
5) 숫자의 정체가 불문명한 경우 1자릿수면 등급, 3자릿수면 표준점수로 추정하고, 2자릿수면 맥락에 따라 백분위 또는 표준점수로 추정.
6) 출력은 JSON 객체만.

선택지:
- 국어 선택과목: 미응시, 화법과작문, 언어와매체
- 수학 선택과목: 미응시, 확률과통계, 기하, 미적분
- 영어 선택과목: 미응시, 영어
- 탐구 선택과목: 미응시, 한국지리, 윤리와사상, 생활과윤리, 사회문화, 정치와법, 경제, 세계사, 동아시아사, 세계지리, 물리학1, 물리학2, 화학1, 화학2, 생명과학1, 생명과학2, 지구과학1, 지구과학2
- 제2외국어/한문 선택과목: 미응시, 독일어1, 프랑스어1, 스페인어1, 중국어1, 일본어1, 러시아어1, 아랍어1, 베트남어1, 한문1

고정 폼:
{{
  "scores": {{
    "한국사": {{"등급": null}},
    "국어": {{"선택과목": null, "표준점수": null, "백분위": null, "등급": null}},
    "수학": {{"선택과목": null, "표준점수": null, "백분위": null, "등급": null}},
    "영어": {{"선택과목": null, "등급": null}},
    "탐구1": {{"선택과목": null, "표준점수": null, "백분위": null, "등급": null}},
    "탐구2": {{"선택과목": null, "표준점수": null, "백분위": null, "등급": null}},
    "제2외국어/한문": {{"선택과목": null, "표준점수": null, "백분위": null, "등급": null}}
  }},
  "evidences": []
}}

입력 문장:
{message}
""".strip()

        generation_config = genai.types.GenerationConfig(
            temperature=0.0,
            response_mime_type="application/json",
        )

        last_error: Exception | None = None
        for retry in range(3):
            try:
                response = self.model.generate_content(prompt, generation_config=generation_config)
                parsed = self._parse_json_text(response.text if response else "")
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError("LLM JSON 파싱 실패")
            except Exception as error:  # noqa: BLE001
                last_error = error
                if retry < 2:
                    time.sleep(0.8 * (retry + 1))
                    continue

        raise RuntimeError(f"Gemini 추출 실패: {last_error}") from last_error

    @staticmethod
    def _parse_json_text(raw_text: str) -> Any:
        text = (raw_text or "").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except Exception:
                return {}

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _norm(value: str) -> str:
        return re.sub(r"[\s·・\-/()]", "", (value or "").strip())

    def _normalize_korean_elective(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = self._norm(str(value))
        if raw == "미응시":
            return "미응시"
        return self.KOREAN_ELECTIVE_MAP.get(raw)

    def _normalize_math_elective(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = self._norm(str(value))
        if raw == "미응시":
            return "미응시"
        return self.MATH_ELECTIVE_MAP.get(raw)

    def _normalize_english_elective(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = self._norm(str(value))
        return self.ENGLISH_ELECTIVE_MAP.get(raw)

    def _normalize_inquiry_elective(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = self._norm(str(value))
        if raw in INQUIRY_ALIASES:
            normalized = INQUIRY_ALIASES[raw]
            if normalized in self.INQUIRY_OPTIONS:
                return normalized
        if str(value).strip() in self.INQUIRY_OPTIONS:
            return str(value).strip()
        if raw == "미응시":
            return "미응시"
        return None

    def _normalize_second_language_elective(self, value: Any) -> str | None:
        if value is None:
            return None
        candidate = str(value).strip()
        if candidate in self.SECOND_LANGUAGE_OPTIONS:
            return candidate
        raw = self._norm(candidate)
        if raw == "미응시":
            return "미응시"
        return None

    @staticmethod
    def _empty_fixed_scores() -> Dict[str, Dict[str, Any]]:
        return {
            "한국사": {"등급": None},
            "국어": {"선택과목": None, "표준점수": None, "백분위": None, "등급": None},
            "수학": {"선택과목": None, "표준점수": None, "백분위": None, "등급": None},
            "영어": {"선택과목": None, "등급": None},
            "탐구1": {"선택과목": None, "표준점수": None, "백분위": None, "등급": None},
            "탐구2": {"선택과목": None, "표준점수": None, "백분위": None, "등급": None},
            "제2외국어/한문": {"선택과목": None, "표준점수": None, "백분위": None, "등급": None},
        }

    def _sanitize_subject_entry(self, subject: str, entry: Any) -> Dict[str, Any]:
        if not isinstance(entry, dict):
            return {}

        clean: Dict[str, Any] = {}

        std = self._to_int(entry.get("표준점수"))
        if std is not None and 0 <= std <= 300:
            clean["표준점수"] = std

        prct = self._to_int(entry.get("백분위"))
        if prct is not None and 0 <= prct <= 100:
            clean["백분위"] = prct

        grd = self._to_int(entry.get("등급"))
        if grd is not None and 1 <= grd <= 9:
            clean["등급"] = grd

        if subject == "국어":
            elective = self._normalize_korean_elective(entry.get("선택과목"))
            if elective:
                clean["선택과목"] = elective
        elif subject == "수학":
            elective = self._normalize_math_elective(entry.get("선택과목"))
            if elective:
                clean["선택과목"] = elective
        elif subject == "영어":
            elective = self._normalize_english_elective(entry.get("선택과목"))
            if elective:
                clean["선택과목"] = elective
        elif subject in {"탐구1", "탐구2"}:
            inquiry = self._normalize_inquiry_elective(entry.get("선택과목") or entry.get("과목명"))
            if inquiry:
                clean["선택과목"] = inquiry
        elif subject == "제2외국어/한문":
            elective = self._normalize_second_language_elective(entry.get("선택과목"))
            if elective:
                clean["선택과목"] = elective

        primary_candidates = []
        if "등급" in clean:
            primary_candidates.append(("등급", clean["등급"]))
        if "백분위" in clean:
            primary_candidates.append(("백분위", clean["백분위"]))
        if "표준점수" in clean:
            primary_candidates.append(("표준점수", clean["표준점수"]))

        if primary_candidates:
            primary = max(primary_candidates, key=lambda pair: TYPE_PRIORITY[pair[0]])
            clean["type"] = primary[0]
            clean["value"] = primary[1]

        return clean

    def _sanitize_output(self, payload: Any) -> Dict[str, Any]:
        fixed_scores = self._empty_fixed_scores()
        completion_scores: Dict[str, Dict[str, Any]] = {}

        scores_raw = payload.get("scores", {}) if isinstance(payload, dict) else {}
        if isinstance(scores_raw, dict):
            for subject in self.SUBJECTS:
                raw_entry = scores_raw.get(subject, {})
                clean_entry = self._sanitize_subject_entry(subject, raw_entry)
                for key in ("선택과목", "표준점수", "백분위", "등급"):
                    if key in fixed_scores[subject]:
                        fixed_scores[subject][key] = clean_entry.get(key)

                if subject not in {"한국사", "국어", "수학", "영어", "탐구1", "탐구2"}:
                    continue
                if not any(clean_entry.get(key) is not None for key in ("등급", "백분위", "표준점수")):
                    continue

                completion_entry = {
                    "등급": clean_entry.get("등급"),
                    "백분위": clean_entry.get("백분위"),
                    "표준점수": clean_entry.get("표준점수"),
                    "type": clean_entry.get("type"),
                    "value": clean_entry.get("value"),
                }
                if subject in {"국어", "수학"} and clean_entry.get("선택과목"):
                    completion_entry["선택과목"] = clean_entry["선택과목"]
                if subject in {"탐구1", "탐구2"} and clean_entry.get("선택과목"):
                    completion_entry["과목명"] = clean_entry["선택과목"]
                completion_scores[subject] = completion_entry

        evidences_raw = payload.get("evidences", [])
        evidences: List[str] = []
        if isinstance(evidences_raw, list):
            evidences = [str(item).strip() for item in evidences_raw if str(item).strip()][:20]

        return {"scores": fixed_scores, "scores_for_completion": completion_scores, "evidences": evidences}
