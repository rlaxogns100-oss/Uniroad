"""
생기부 PDF 추출 텍스트를 Gemini로 구조화 파싱.
- 기본 모델: gemini-3.1-flash-lite-preview. 단일 호출, response_mime_type=application/json.
- 입력 길이 제한(MAX_INPUT_CHARS)으로 토큼·지연 최소화.
- 실패 시 None → 라우터에서 규칙 기반 파서로 폴백.
- env: SCHOOL_RECORD_GEMINI_PARSE_MODEL, SCHOOL_RECORD_GEMINI_MAX_INPUT_CHARS
"""
from __future__ import annotations

import json
import logging
import re
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 상단에서 설정 로드
try:
    from config.config import settings
except Exception:
    settings = None

GEMINI_PARSE_MODEL = os.getenv("SCHOOL_RECORD_GEMINI_PARSE_MODEL", "gemini-3.1-flash-lite-preview")
MAX_INPUT_CHARS = int(os.getenv("SCHOOL_RECORD_GEMINI_MAX_INPUT_CHARS", "120000"))  # 너무 길면 잘라서 속도 유지

SYSTEM_PROMPT = """당신은 한국 고등학교 생활기록부(생기부) 원문 텍스트를 분석해 구조화된 JSON으로만 답하는 파서입니다.

[핵심 규칙 — 반드시 준수]
1. **절대 요약하지 마세요.** 모든 텍스트 필드(note, autonomousNotes, clubNotes, careerNotes, behaviorOpinion 등)는 원문에 있는 내용을 한 글자도 빠뜨리지 않고 그대로 옮겨야 합니다. 축약·의역·생략 금지.
2. **성적 표(교과학습발달상황)를 반드시 추출하세요.** 학기, 교과, 과목, 단위수, 원점수/과목평균, 표준편차, 성취도, 수강자수, 석차등급 등이 포함된 표는 general_elective/career_elective/pe_arts의 rows에 넣으세요.
3. 없거나 판단 불가한 필드는 빈 배열·빈 문자열·false·null로 두세요.
4. 반드시 유효한 JSON 하나만 출력하고, 설명이나 마크다운 없이 JSON만 출력하세요.

출력 JSON 구조:
{
  "attendance": {
    "has_no_item": false,
    "rows": [
      { "grade": "1", "수업일수": 192, "결석_질병": 0, "결석_미인정": 0, "결석_기타": 0, "지각_질병": 0, "지각_미인정": 0, "지각_기타": 0, "조퇴_질병": 0, "조퇴_미인정": 0, "조퇴_기타": 0, "결과_질병": 0, "결과_미인정": 0, "결과_기타": 0, "특기사항": "" }
    ]
  },
  "certificates": {
    "has_no_item": false,
    "items": [],
    "rows": [
      { "구분": "", "명칭또는종류": "", "번호또는내용": "", "취득년월일": "", "발급기관": "" }
    ]
  },
  "creativeActivity": {
    "by_grade": {
      "1": { "autonomousNotes": "원문 그대로 전체 복사", "clubNotes": "원문 그대로 전체 복사", "careerNotes": "원문 그대로 전체 복사" },
      "2": { "autonomousNotes": "", "clubNotes": "", "careerNotes": "" },
      "3": { "autonomousNotes": "", "clubNotes": "", "careerNotes": "" }
    },
    "hours_by_grade": {
      "1": { "autonomousHours": null, "clubHours": null, "careerHours": null },
      "2": { "autonomousHours": null, "clubHours": null, "careerHours": null },
      "3": { "autonomousHours": null, "clubHours": null, "careerHours": null }
    }
  },
  "volunteerActivity": {
    "has_no_item": false,
    "rows": [
      { "grade": "1", "일자또는기간": "", "장소또는주관기관명": "", "활동내용": "", "hours": null }
    ]
  },
  "academicDevelopment": {
    "by_grade": {
      "1": [ { "subject": "과목명", "note": "세부능력 및 특기사항 원문 전체 — 절대 요약 금지" } ],
      "2": [],
      "3": []
    },
    "general_elective": {
      "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "표준편차": "", "성취도": "", "수강자수": "", "석차등급": "" } ], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    },
    "career_elective": {
      "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "성취도": "", "수강자수": "", "성취도별분포_A": "", "성취도별분포_B": "", "성취도별분포_C": "" } ], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    },
    "pe_arts": {
      "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "성취도": "" } ], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    }
  },
  "behaviorOpinion": {
    "by_grade": { "1": "원문 그대로 전체 복사", "2": "", "3": "" }
  }
}

[필드별 규칙]
- attendance.rows: 학년(1/2/3)별 출결. 숫자 필드는 정수로.
- certificates.rows: 자격증·인증 행. items는 원문 한 줄 배열로도 채울 수 있음.
- creativeActivity: 학년별 자율/동아리/진로 특기사항(원문 전체)과 시간(숫자).
- volunteerActivity.rows: 학년, 일자 또는 기간, 장소 또는 주관기관명, 활동내용, hours(숫자).
- academicDevelopment.by_grade: 학년별 과목별 { subject, note } 배열. subject에는 반드시 실제 과목명(예: 국어, 수학, 영어, 음악, 미술 창작)만 넣고, '미분류'나 학년만 쓰지 말 것. note에는 해당 과목의 세부능력 및 특기사항 **원문 전체**를 넣을 것 — 한 글자도 빠뜨리거나 요약하지 마세요.
- academicDevelopment.general_elective: 일반선택과목 성적표. 학기·교과·과목·단위수·원점수/과목평균·표준편차·성취도·수강자수·석차등급이 있는 표에서 각 행을 rows에 넣으세요.
- academicDevelopment.career_elective: 진로선택과목 성적표. 석차등급 대신 성취도별분포(A/B/C)가 있음.
- academicDevelopment.pe_arts: 체육·예술과목 성적표. 단위수·성취도만 있음.
- behaviorOpinion.by_grade: 학년별 행동특성 및 종합의견 **원문 전체**.
"""

# STEP 01: 출결상황, 자격증 및 인증 취득상황 (목차 기반 청킹용)
STEP01_PROMPT = """당신은 생기부 '출결상황'과 '자격증 및 인증 취득상황' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 배열·false로 두세요. 유효한 JSON만 출력하세요.
{
  "attendance": { "has_no_item": false, "rows": [ { "grade": "1", "수업일수": 192, "결석_질병": 0, "결석_미인정": 0, "결석_기타": 0, "지각_질병": 0, "지각_미인정": 0, "지각_기타": 0, "조퇴_질병": 0, "조퇴_미인정": 0, "조퇴_기타": 0, "결과_질병": 0, "결과_미인정": 0, "결과_기타": 0, "특기사항": "" } ] },
  "certificates": { "has_no_item": false, "items": [], "rows": [ { "구분": "", "명칭또는종류": "", "번호또는내용": "", "취득년월일": "", "발급기관": "" } ] }
}
attendance.rows: 학년별 출결. certificates.rows: 자격증 행."""

# STEP 02: 창의적체험활동상황, 봉사활동실적
STEP02_PROMPT = """당신은 생기부 '창의적체험활동상황'과 '봉사활동실적' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 객체·빈 배열·false로 두세요. 유효한 JSON만 출력하세요.
**절대 요약하지 마세요.** autonomousNotes, clubNotes, careerNotes는 원문에 있는 내용을 한 글자도 빠뜨리지 않고 그대로 전체 복사하세요.
{
  "creativeActivity": {
    "by_grade": { "1": { "autonomousNotes": "원문 전체 복사", "clubNotes": "원문 전체 복사", "careerNotes": "원문 전체 복사" }, "2": {}, "3": {} },
    "hours_by_grade": { "1": { "autonomousHours": null, "clubHours": null, "careerHours": null }, "2": {}, "3": {} }
  },
  "volunteerActivity": { "has_no_item": false, "rows": [ { "grade": "1", "일자또는기간": "", "장소또는주관기관명": "", "활동내용": "", "hours": null } ] }
}
volunteerActivity.rows: 학년, 일자 또는 기간, 장소, 활동내용, hours(숫자)."""

# STEP 03: 교과학습발달상황
STEP03_PROMPT = """당신은 생기부 '교과학습발달상황' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 배열·null로 두세요. 유효한 JSON만 출력하세요.
**절대 요약하지 마세요.** note(세부능력 및 특기사항)는 원문에 있는 내용을 한 글자도 빠뜨리지 않고 그대로 전체 복사하세요.
{
  "academicDevelopment": {
    "by_grade": { "1": [ { "subject": "과목명", "note": "세부능력 및 특기사항 원문 전체 — 요약 금지" } ], "2": [], "3": [] },
    "general_elective": { "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "표준편차": "", "성취도": "", "수강자수": "", "석차등급": "" } ], "이수단위합계": null }, "2": {}, "3": {} },
    "career_elective": { "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "성취도": "", "수강자수": "", "성취도별분포_A": "", "성취도별분포_B": "", "성취도별분포_C": "" } ], "이수단위합계": null }, "2": {}, "3": {} },
    "pe_arts": { "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "성취도": "" } ], "이수단위합계": null }, "2": {}, "3": {} }
  }
}
subject에는 실제 과목명만(국어, 수학, 음악, 미술 창작 등). '미분류' 사용 금지.
**중요: by_grade에는 일반선택·진로선택·체육·예술 등 세부능력 및 특기사항이 있는 모든 과목을 빠짐없이 넣어야 합니다.** 영어권 문화, 미술 창작, 운동과 건강, 경제 수학, 사회문제 탐구, 과학사, 일본어Ⅱ, 체육 등 진로선택·체육예술 과목의 세특도 반드시 포함하세요.
규칙: (1) 학기·교과·과목·단위수·원점수·과목평균·성취도 등 숫자·등급이 있는 표는 general_elective/career_elective/pe_arts의 rows에만 넣을 것. (2) '과목'과 '세부능력 및 특기사항' 두 열로 된 표(과목명+긴 서술문)는 by_grade에만 넣을 것. 성적 표 행을 by_grade에 넣지 말 것.
(3) general_elective rows: 원점수/과목평균/표준편차/석차등급이 있는 일반 선택과목. (4) career_elective rows: 석차등급 없이 성취도별분포가 있는 진로 선택과목. (5) pe_arts rows: 단위수와 성취도만 있는 체육·예술 과목."""

# STEP 03 학년별 분할 프롬프트 (병렬 최적화)
_STEP03_GRADE_TEMPLATE = """당신은 생기부 '교과학습발달상황' 중 {grade}학년 부분만 분석해 JSON으로만 답합니다. {grade}학년 외의 데이터는 무시하세요. 없으면 빈 배열·null로 두세요.
**절대 요약하지 마세요.** note(세부능력 및 특기사항)는 원문에 있는 내용을 한 글자도 빠뜨리지 않고 그대로 전체 복사하세요.
{{
  "by_grade": [ {{ "subject": "과목명", "note": "세부능력 및 특기사항 원문 전체" }} ],
  "general_elective": {{ "rows": [ {{ "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "표준편차": "", "성취도": "", "수강자수": "", "석차등급": "" }} ], "이수단위합계": null }},
  "career_elective": {{ "rows": [ {{ "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "성취도": "", "수강자수": "", "성취도별분포_A": "", "성취도별분포_B": "", "성취도별분포_C": "" }} ], "이수단위합계": null }},
  "pe_arts": {{ "rows": [ {{ "학기": "", "교과": "", "과목": "", "단위수": "", "성취도": "" }} ], "이수단위합계": null }}
}}
subject에는 실제 과목명만. by_grade에는 일반선택·진로선택·체육·예술 등 세특이 있는 모든 과목을 빠짐없이 넣으세요.
규칙: (1) 성적표 행은 general_elective/career_elective/pe_arts의 rows에만. (2) 과목명+긴 서술문은 by_grade에만.
(3) general_elective: 석차등급이 있는 과목. (4) career_elective: 성취도별분포가 있는 과목. (5) pe_arts: 단위수+성취도만 있는 체육·예술."""

STEP03_GRADE1_PROMPT = _STEP03_GRADE_TEMPLATE.format(grade="1")
STEP03_GRADE2_PROMPT = _STEP03_GRADE_TEMPLATE.format(grade="2")
STEP03_GRADE3_PROMPT = _STEP03_GRADE_TEMPLATE.format(grade="3")

# STEP 04: 행동특성 및 종합의견
STEP04_PROMPT = """당신은 생기부 '행동특성 및 종합의견' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 문자열로 두세요. 유효한 JSON만 출력하세요.
**절대 요약하지 마세요.** 행동특성 및 종합의견은 원문에 있는 내용을 한 글자도 빠뜨리지 않고 그대로 전체 복사하세요.
{
  "behaviorOpinion": { "by_grade": { "1": "원문 전체 복사", "2": "원문 전체 복사", "3": "원문 전체 복사" } }
}"""


def _normalize_sections(gemini_json: Dict[str, Any]) -> Dict[str, Any]:
    """Gemini 응답을 우리 sections 형식으로 정규화."""
    sections: Dict[str, Any] = {}
    # attendance
    att = gemini_json.get("attendance") or {}
    sections["attendance"] = {
        "has_no_item": bool(att.get("has_no_item")),
        "rows": list(att.get("rows") or []),
    }
    # certificates
    cert = gemini_json.get("certificates") or {}
    sections["certificates"] = {
        "has_no_item": bool(cert.get("has_no_item")),
        "items": list(cert.get("items") or []),
        "rows": list(cert.get("rows") or []),
    }
    # creativeActivity
    creative = gemini_json.get("creativeActivity") or {}
    by_grade = creative.get("by_grade") or {}
    hours_by_grade = creative.get("hours_by_grade") or {}
    for g in ("1", "2", "3"):
        if g not in by_grade:
            by_grade[g] = {"autonomousNotes": "", "clubNotes": "", "careerNotes": ""}
        if g not in hours_by_grade:
            hours_by_grade[g] = {"autonomousHours": None, "clubHours": None, "careerHours": None}
    sections["creativeActivity"] = {"by_grade": by_grade, "hours_by_grade": hours_by_grade}
    # volunteerActivity
    vol = gemini_json.get("volunteerActivity") or {}
    sections["volunteerActivity"] = {
        "has_no_item": bool(vol.get("has_no_item")),
        "rows": list(vol.get("rows") or []),
    }
    # academicDevelopment
    acad = gemini_json.get("academicDevelopment") or {}
    by_grade_acad = acad.get("by_grade") or {}
    for g in ("1", "2", "3"):
        if g not in by_grade_acad:
            by_grade_acad[g] = []
    ge = acad.get("general_elective") or {}
    ce = acad.get("career_elective") or {}
    pe = acad.get("pe_arts") or {}
    _default_grade_rows = {"rows": [], "이수단위합계": None}
    for table in (ge, ce, pe):
        for g in ("1", "2", "3"):
            entry = table.get(g)
            if not isinstance(entry, dict):
                table[g] = dict(_default_grade_rows)
            else:
                if "rows" not in entry:
                    entry["rows"] = []
                if "이수단위합계" not in entry:
                    entry["이수단위합계"] = None
    sections["academicDevelopment"] = {
        "by_grade": by_grade_acad,
        "general_elective": ge,
        "career_elective": ce,
        "pe_arts": pe,
    }
    # behaviorOpinion
    beh = gemini_json.get("behaviorOpinion") or {}
    by_grade_beh = beh.get("by_grade") or {}
    for g in ("1", "2", "3"):
        if g not in by_grade_beh:
            by_grade_beh[g] = ""
    sections["behaviorOpinion"] = {"by_grade": by_grade_beh}
    return sections


def _build_forms_from_sections(sections: Dict[str, Any]) -> Dict[str, Any]:
    """sections로부터 creativeActivity, academicDev, individualDev, behaviorOpinion, volunteerActivity, parsedSchoolRecord, parseSummary 생성."""
    creative = sections.get("creativeActivity") or {}
    by_grade_c = creative.get("by_grade") or {}
    hours_by_grade = creative.get("hours_by_grade") or {}
    creative_form = {
        "byGrade": {
            "1": dict(by_grade_c.get("1") or {}),
            "2": dict(by_grade_c.get("2") or {}),
            "3": dict(by_grade_c.get("3") or {}),
        }
    }

    acad = sections.get("academicDevelopment") or {}
    by_grade_a = acad.get("by_grade") or {}
    academic_form: Dict[str, Any] = {"byGrade": {}}
    individual_form: Dict[str, Any] = {"showInputs": True, "byGrade": {}}
    for grade in ("1", "2", "3"):
        pairs = list(by_grade_a.get(grade) or [])
        subjects: List[str] = []
        notes: List[str] = []
        individual_chunks: List[str] = []
        for pair in pairs:
            subj = str(pair.get("subject") or "").strip() or "과목"
            note = str(pair.get("note") or "").strip()
            if note:
                individual_chunks.append(f"[{subj}]\n{note}")
            if len(subjects) < 3:
                subjects.append(subj)
                notes.append(note)
        subjects = (subjects + ["", "", ""])[:3]
        notes = (notes + ["", "", ""])[:3]
        academic_form["byGrade"][grade] = {"subjects": subjects, "notes": notes}
        individual_form["byGrade"][grade] = {"content": "\n\n".join(individual_chunks).strip()}

    beh = sections.get("behaviorOpinion") or {}
    by_grade_b = beh.get("by_grade") or {}
    behavior_form = {
        "showInputs": True,
        "opinions": [
            by_grade_b.get("1", ""),
            by_grade_b.get("2", ""),
            by_grade_b.get("3", ""),
        ],
    }

    vol = sections.get("volunteerActivity") or {}
    volunteer_form = {
        "rows": list(vol.get("rows") or []),
        "hasNoItem": bool(vol.get("has_no_item")),
    }

    parsed_school_record = {
        "parserVersion": "gemini",
        "sections": {
            "attendance": sections.get("attendance") or {},
            "certificates": sections.get("certificates") or {},
            "creativeActivity": sections.get("creativeActivity") or {},
            "volunteerActivity": sections.get("volunteerActivity") or {},
            "academicDevelopment": sections.get("academicDevelopment") or {},
            "behaviorOpinion": sections.get("behaviorOpinion") or {},
        },
    }

    academic_note_count = sum(
        len([p for p in (by_grade_a.get(g) or []) if str(p.get("note") or "").strip()])
        for g in ("1", "2", "3")
    )
    parse_summary = {
        "section_chars": {},
        "academic_note_count": academic_note_count,
        "creative_note_count": sum(
            1
            for g in ("1", "2", "3")
            for key in ("autonomousNotes", "clubNotes", "careerNotes")
            if str((by_grade_c.get(g) or {}).get(key) or "").strip()
        ),
        "behavior_grade_count": sum(1 for g in ("1", "2", "3") if str(by_grade_b.get(g) or "").strip()),
        "volunteer_item_count": len(volunteer_form["rows"]),
    }

    return {
        "creativeActivity": creative_form,
        "academicDev": academic_form,
        "individualDev": individual_form,
        "behaviorOpinion": behavior_form,
        "volunteerActivity": volunteer_form,
        "parsedSchoolRecord": parsed_school_record,
        "parseSummary": parse_summary,
    }


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """응답 텍스트에서 JSON 블록만 추출. list가 오면 첫 dict를 반환."""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()

    def _ensure_dict(obj: Any) -> Optional[Dict[str, Any]]:
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    return item
        return None

    try:
        return _ensure_dict(json.loads(text))
    except (json.JSONDecodeError, ValueError):
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return _ensure_dict(json.loads(text[start : end + 1]))
    except (json.JSONDecodeError, ValueError):
        return None


def _call_gemini_json(system_prompt: str, user_text: str) -> Optional[Dict[str, Any]]:
    """공통: Gemini 호출 후 JSON만 파싱해 반환. 실패 시 None."""
    api_key = (settings and getattr(settings, "GEMINI_API_KEY", None)) or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("생기부 Gemini 파싱 실패: API 키 없음 (GEMINI_API_KEY, GOOGLE_API_KEY)")
        return None
    text = (user_text or "").strip()
    if not text:
        logger.warning("생기부 Gemini 파싱 실패: 입력 텍스트 없음")
        return None
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "\n\n[이하 생략]"
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=GEMINI_PARSE_MODEL,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            f"다음 생기부 원문을 위 지시대로 JSON만 출력하세요. 모든 텍스트 필드는 원문 그대로 전체를 넣으세요. 절대 요약·축약하지 마세요.\n\n[생기부 원문]\n{text}",
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                max_output_tokens=65536,
                response_mime_type="application/json",
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        if not response:
            logger.warning("생기부 Gemini 파싱 실패: response 객체 없음")
            return None
        if not response.text:
            block_reason = getattr(response, "prompt_feedback", None)
            logger.warning(
                "생기부 Gemini 파싱 실패: 응답 텍스트 없음 (블록/필터 가능). prompt_feedback=%s",
                block_reason,
            )
            return None
        parsed = _extract_json_from_text(response.text)
        if parsed is None:
            logger.warning(
                "생기부 Gemini 파싱 실패: JSON 파싱 실패. 응답 길이=%d, 앞 200자=%s",
                len(response.text),
                (response.text[:200] + "..." if len(response.text) > 200 else response.text),
            )
            return None
        return parsed
    except Exception as e:
        logger.exception("생기부 Gemini 파싱 실패: API 예외. %s", e)
        return None


def _call_gemini_json_with_pdf(
    system_prompt: str, pdf_bytes: bytes, max_tokens: int = 65536
) -> Optional[Dict[str, Any]]:
    """PDF 바이너리를 Gemini에 직접 전달해 JSON 파싱. 스캔본 PDF 지원."""
    api_key = (settings and getattr(settings, "GEMINI_API_KEY", None)) or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("생기부 Gemini PDF 파싱 실패: API 키 없음")
        return None
    if not pdf_bytes:
        logger.warning("생기부 Gemini PDF 파싱 실패: PDF 바이너리 없음")
        return None
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=GEMINI_PARSE_MODEL,
            system_instruction=system_prompt,
        )

        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_bytes,
        }

        response = model.generate_content(
            [
                pdf_part,
                "이 생활기록부 PDF를 분석해 위 지시대로 JSON만 출력하세요. 모든 텍스트 필드는 원문 그대로 전체를 넣으세요. 절대 요약·축약하지 마세요. 성적표(교과학습발달상황)의 모든 행도 빠짐없이 추출하세요.",
            ],
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        if not response:
            logger.warning("생기부 Gemini PDF 파싱 실패: response 객체 없음")
            return None
        if not response.text:
            block_reason = getattr(response, "prompt_feedback", None)
            logger.warning(
                "생기부 Gemini PDF 파싱 실패: 응답 텍스트 없음. prompt_feedback=%s",
                block_reason,
            )
            return None
        parsed = _extract_json_from_text(response.text)
        if parsed is None:
            logger.warning(
                "생기부 Gemini PDF 파싱 실패: JSON 파싱 실패. 응답 길이=%d",
                len(response.text),
            )
            return None
        return parsed
    except Exception as e:
        logger.exception("생기부 Gemini PDF 파싱 실패: API 예외. %s", e)
        return None


def parse_school_record_with_gemini(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    생기부 원문 텍스트를 Gemini로 파싱해 forms 형식으로 반환.
    실패 시 None (호출 측에서 규칙 기반 파서로 폴백).
    """
    data = _call_gemini_json(SYSTEM_PROMPT, raw_text)
    if not data:
        return None
    sections = _normalize_sections(data)
    return _build_forms_from_sections(sections)


def _merge_grade_results(g1: Optional[Dict], g2: Optional[Dict], g3: Optional[Dict]) -> Dict[str, Any]:
    """학년별 교과학습 결과를 STEP03 형식으로 머지."""
    merged: Dict[str, Any] = {
        "academicDevelopment": {
            "by_grade": {"1": [], "2": [], "3": []},
            "general_elective": {
                "1": {"rows": [], "이수단위합계": None},
                "2": {"rows": [], "이수단위합계": None},
                "3": {"rows": [], "이수단위합계": None},
            },
            "career_elective": {
                "1": {"rows": [], "이수단위합계": None},
                "2": {"rows": [], "이수단위합계": None},
                "3": {"rows": [], "이수단위합계": None},
            },
            "pe_arts": {
                "1": {"rows": [], "이수단위합계": None},
                "2": {"rows": [], "이수단위합계": None},
                "3": {"rows": [], "이수단위합계": None},
            },
        }
    }
    acad = merged["academicDevelopment"]
    for grade, data in [("1", g1), ("2", g2), ("3", g3)]:
        if not data:
            continue
        acad["by_grade"][grade] = data.get("by_grade", [])
        for table in ("general_elective", "career_elective", "pe_arts"):
            tbl = data.get(table) or {}
            if isinstance(tbl, dict):
                acad[table][grade] = {
                    "rows": tbl.get("rows", []),
                    "이수단위합계": tbl.get("이수단위합계"),
                }
    return merged


def parse_school_record_pdf_with_gemini(
    pdf_bytes: bytes, extracted_text: str = ""
) -> Optional[Dict[str, Any]]:
    """
    PDF를 Gemini로 파싱 (병렬 6-STEP, 하이브리드).

    텍스트 PDF: STEP01/02/04는 텍스트 기반(빠름), STEP03은 PDF 직접(정확)
    스캔본 PDF: 전부 PDF 직접 전달
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    start = time.time()
    has_text = len((extracted_text or "").strip()) >= 200

    futures_map: Dict[Any, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        if has_text:
            # 텍스트 PDF → 단순 섹션은 텍스트, 교과학습만 PDF
            futures_map[executor.submit(_call_gemini_json, STEP01_PROMPT, extracted_text)] = "step01"
            futures_map[executor.submit(_call_gemini_json, STEP02_PROMPT, extracted_text)] = "step02"
            futures_map[executor.submit(_call_gemini_json, STEP04_PROMPT, extracted_text)] = "step04"
        else:
            # 스캔본 → 전부 PDF
            futures_map[executor.submit(_call_gemini_json_with_pdf, STEP01_PROMPT, pdf_bytes, 4096)] = "step01"
            futures_map[executor.submit(_call_gemini_json_with_pdf, STEP02_PROMPT, pdf_bytes, 16384)] = "step02"
            futures_map[executor.submit(_call_gemini_json_with_pdf, STEP04_PROMPT, pdf_bytes, 8192)] = "step04"

        # 교과학습(STEP03)은 항상 PDF 직접 → 세특 누락 방지
        futures_map[executor.submit(_call_gemini_json_with_pdf, STEP03_GRADE1_PROMPT, pdf_bytes, 16384)] = "step03_g1"
        futures_map[executor.submit(_call_gemini_json_with_pdf, STEP03_GRADE2_PROMPT, pdf_bytes, 16384)] = "step03_g2"
        futures_map[executor.submit(_call_gemini_json_with_pdf, STEP03_GRADE3_PROMPT, pdf_bytes, 16384)] = "step03_g3"

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        for future in as_completed(futures_map):
            name = futures_map[future]
            try:
                results[name] = future.result()
            except Exception as e:
                logger.warning("생기부 병렬 파싱 %s 실패: %s", name, e)
                results[name] = None

    elapsed = time.time() - start
    success_count = sum(1 for v in results.values() if v is not None)
    mode = "hybrid" if has_text else "pdf_only"
    logger.info("생기부 병렬 파싱 완료 [%s]: %d/6 성공, %.1f초", mode, success_count, elapsed)

    if success_count == 0:
        logger.warning("생기부 병렬 파싱 전부 실패 → 단일 호출 폴백")
        data = _call_gemini_json_with_pdf(SYSTEM_PROMPT, pdf_bytes)
        if not data:
            return None
        sections = _normalize_sections(data)
        return _build_forms_from_sections(sections)

    step03_merged = _merge_grade_results(
        results.get("step03_g1"),
        results.get("step03_g2"),
        results.get("step03_g3"),
    )

    return build_forms_from_step_results(
        results.get("step01"),
        results.get("step02"),
        step03_merged,
        results.get("step04"),
    )


# --- 목차(STEP 01~04) 기반 청킹 + 병렬 추출용 (각각 부분 JSON 반환) ---

def parse_step01_with_gemini(text: str) -> Optional[Dict[str, Any]]:
    """STEP 01: 출결상황, 자격증 및 인증 취득상황. 반환: {"attendance": ..., "certificates": ...} 또는 None."""
    return _call_gemini_json(STEP01_PROMPT, text)


def parse_step02_with_gemini(text: str) -> Optional[Dict[str, Any]]:
    """STEP 02: 창의적체험활동상황, 봉사활동실적. 반환: {"creativeActivity": ..., "volunteerActivity": ...} 또는 None."""
    return _call_gemini_json(STEP02_PROMPT, text)


def parse_step03_with_gemini(text: str) -> Optional[Dict[str, Any]]:
    """STEP 03: 교과학습발달상황. 반환: {"academicDevelopment": ...} 또는 None."""
    return _call_gemini_json(STEP03_PROMPT, text)


def parse_step04_with_gemini(text: str) -> Optional[Dict[str, Any]]:
    """STEP 04: 행동특성 및 종합의견. 반환: {"behaviorOpinion": ...} 또는 None."""
    return _call_gemini_json(STEP04_PROMPT, text)


def build_forms_from_step_results(
    step01: Optional[Dict[str, Any]],
    step02: Optional[Dict[str, Any]],
    step03: Optional[Dict[str, Any]],
    step04: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    STEP 01~04 병렬 파싱 결과(부분 JSON)를 머지한 뒤 sections 정규화 및 forms 생성.
    일부가 None이어도 빈 값으로 채워서 반환.
    """
    merged = {
        "attendance": {},
        "certificates": {},
        "creativeActivity": {},
        "volunteerActivity": {},
        "academicDevelopment": {},
        "behaviorOpinion": {},
    }
    for step in (step01, step02, step03, step04):
        if not step or not isinstance(step, dict):
            continue
        merged.update({k: v for k, v in step.items() if k in merged})
    sections = _normalize_sections(merged)
    return _build_forms_from_sections(sections)
