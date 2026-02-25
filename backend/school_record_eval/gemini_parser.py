"""
생기부 PDF 추출 텍스트를 Gemini로 구조화 파싱.
- 기본 모델: gemini-2.5-flash-preview. 단일 호출, response_mime_type=application/json.
- 입력 길이 제한(MAX_INPUT_CHARS)으로 토큼·지연 최소화.
- 실패 시 None → 라우터에서 규칙 기반 파서로 폴백.
- env: SCHOOL_RECORD_GEMINI_PARSE_MODEL, SCHOOL_RECORD_GEMINI_MAX_INPUT_CHARS
"""
from __future__ import annotations

import json
import re
import os
from typing import Any, Dict, List, Optional

# 상단에서 설정 로드
try:
    from config.config import settings
except Exception:
    settings = None

GEMINI_PARSE_MODEL = os.getenv("SCHOOL_RECORD_GEMINI_PARSE_MODEL", "gemini-2.5-flash-preview")
MAX_INPUT_CHARS = int(os.getenv("SCHOOL_RECORD_GEMINI_MAX_INPUT_CHARS", "120000"))  # 너무 길면 잘라서 속도 유지

SYSTEM_PROMPT = """당신은 한국 고등학교 생활기록부(생기부) 원문 텍스트를 분석해 구조화된 JSON으로만 답하는 파서입니다.
주어진 텍스트에서 아래 키에 맞게 데이터를 추출하세요. 없거나 판단 불가면 빈 배열·빈 문자열·false로 두세요.
반드시 유효한 JSON 하나만 출력하고, 설명이나 마크다운 없이 JSON만 출력하세요.

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
      "1": { "autonomousNotes": "", "clubNotes": "", "careerNotes": "" },
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
      "1": [ { "subject": "과목명", "note": "세부능력 및 특기사항 내용" } ],
      "2": [],
      "3": []
    },
    "general_elective": {
      "1": { "rows": [ { "학기": "", "교과": "", "과목": "", "단위수": "", "원점수": "", "과목평균": "", "표준편차": "", "성취도": "", "수강자수": "", "석차등급": "" } ], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    },
    "career_elective": {
      "1": { "rows": [], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    },
    "pe_arts": {
      "1": { "rows": [], "이수단위합계": null },
      "2": { "rows": [], "이수단위합계": null },
      "3": { "rows": [], "이수단위합계": null }
    }
  },
  "behaviorOpinion": {
    "by_grade": { "1": "", "2": "", "3": "" }
  }
}

- attendance.rows: 학년(1/2/3)별 출결. 숫자 필드는 정수로.
- certificates.rows: 자격증·인증 행. items는 원문 한 줄 배열로도 채울 수 있음.
- creativeActivity: 학년별 자율/동아리/진로 특기사항과 시간(숫자).
- volunteerActivity.rows: 학년, 일자 또는 기간, 장소 또는 주관기관명, 활동내용, hours(숫자).
- academicDevelopment.by_grade: 학년별 과목별 { subject, note } 배열. subject에는 반드시 실제 과목명(예: 국어, 수학, 영어, 음악, 미술, 미술 창작, 음악 연주)만 넣고, '미분류'나 학년만 쓰지 말 것. note는 해당 과목의 세부능력 및 특기사항 본문.
- behaviorOpinion.by_grade: 학년별 행동특성 및 종합의견 문자열.
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
{
  "creativeActivity": {
    "by_grade": { "1": { "autonomousNotes": "", "clubNotes": "", "careerNotes": "" }, "2": {}, "3": {} },
    "hours_by_grade": { "1": { "autonomousHours": null, "clubHours": null, "careerHours": null }, "2": {}, "3": {} }
  },
  "volunteerActivity": { "has_no_item": false, "rows": [ { "grade": "1", "일자또는기간": "", "장소또는주관기관명": "", "활동내용": "", "hours": null } ] }
}
volunteerActivity.rows: 학년, 일자 또는 기간, 장소, 활동내용, hours(숫자)."""

# STEP 03: 교과학습발달상황
STEP03_PROMPT = """당신은 생기부 '교과학습발달상황' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 배열·null로 두세요. 유효한 JSON만 출력하세요.
{
  "academicDevelopment": {
    "by_grade": { "1": [ { "subject": "과목명", "note": "세부능력 및 특기사항" } ], "2": [], "3": [] },
    "general_elective": { "1": { "rows": [], "이수단위합계": null }, "2": {}, "3": {} },
    "career_elective": { "1": { "rows": [], "이수단위합계": null }, "2": {}, "3": {} },
    "pe_arts": { "1": { "rows": [], "이수단위합계": null }, "2": {}, "3": {} }
  }
}
subject에는 실제 과목명만(국어, 수학, 음악, 미술 창작 등). '미분류' 사용 금지.
규칙: (1) 학기·교과·과목·단위수·원점수·과목평균·성취도 등 숫자·등급이 있는 표는 general_elective/career_elective/pe_arts의 rows에만 넣을 것. (2) '과목'과 '세부능력 및 특기사항' 두 열로 된 표(과목명+긴 서술문)는 by_grade에만 넣을 것. 성적 표 행을 by_grade에 넣지 말 것."""

# STEP 04: 행동특성 및 종합의견
STEP04_PROMPT = """당신은 생기부 '행동특성 및 종합의견' 원문만 분석해 JSON으로만 답합니다. 없으면 빈 문자열로 두세요. 유효한 JSON만 출력하세요.
{
  "behaviorOpinion": { "by_grade": { "1": "", "2": "", "3": "" } }
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
    for g in ("1", "2", "3"):
        if g not in ge:
            ge[g] = {"rows": [], "이수단위합계": None}
        if g not in ce:
            ce[g] = {"rows": [], "이수단위합계": None}
        if g not in pe:
            pe[g] = {"rows": [], "이수단위합계": None}
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
    """응답 텍스트에서 JSON 블록만 추출."""
    text = (text or "").strip()
    # ```json ... ``` 제거
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    # 첫 { 부터 마지막 } 까지
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _call_gemini_json(system_prompt: str, user_text: str) -> Optional[Dict[str, Any]]:
    """공통: Gemini 호출 후 JSON만 파싱해 반환. 실패 시 None."""
    api_key = (settings and getattr(settings, "GEMINI_API_KEY", None)) or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    text = (user_text or "").strip()
    if not text:
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
            f"다음 생기부 원문을 위 지시대로 JSON만 출력하세요.\n\n[생기부 원문]\n{text}",
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        if not response or not response.text:
            return None
        return _extract_json_from_text(response.text)
    except Exception:
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
    empty = {}
    merged = {
        "attendance": empty,
        "certificates": empty,
        "creativeActivity": empty,
        "volunteerActivity": empty,
        "academicDevelopment": empty,
        "behaviorOpinion": empty,
    }
    if step01:
        merged.update({k: v for k, v in step01.items() if k in merged})
    if step02:
        merged.update({k: v for k, v in step02.items() if k in merged})
    if step03:
        merged.update({k: v for k, v in step03.items() if k in merged})
    if step04:
        merged.update({k: v for k, v in step04.items() if k in merged})
    sections = _normalize_sections(merged)
    return _build_forms_from_sections(sections)
