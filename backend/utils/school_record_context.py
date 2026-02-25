from __future__ import annotations

import json
from typing import Any, Dict, Optional


DEFAULT_MAX_CONTEXT_CHARS = 12000


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return len(value.strip()) == 0
    if isinstance(value, list):
        return len(value) == 0 or all(_is_empty_value(v) for v in value)
    if isinstance(value, dict):
        return len(value) == 0 or all(_is_empty_value(v) for v in value.values())
    return False


def has_meaningful_school_record(school_record: Optional[Dict[str, Any]]) -> bool:
    """
    user_profiles.school_record(JSONB) 가 "연동됨" 상태인지 판정.
    - 기본값은 {} 이므로 단순 key 존재만으로는 판단하지 않음.
    - forms/items/parsed/raw 등 실질 데이터가 있는지 확인.
    """
    if not isinstance(school_record, dict) or not school_record:
        return False

    items = school_record.get("items")
    if isinstance(items, list) and len(items) > 0:
        return True

    forms = school_record.get("forms")
    if not isinstance(forms, dict):
        forms = {}

    # 일부 환경/레거시에서 forms 없이 바로 폼이 저장되는 경우를 대비
    if not forms:
        likely_form_keys = {
            "creativeActivity",
            "academicDev",
            "individualDev",
            "behaviorOpinion",
            "volunteerActivity",
            "parsedSchoolRecord",
            "parsedSchoolRecordSummary",
            "rawSchoolRecordText",
        }
        if any(k in school_record for k in likely_form_keys):
            forms = school_record

    for k in (
        "creativeActivity",
        "academicDev",
        "individualDev",
        "behaviorOpinion",
        "volunteerActivity",
        "parsedSchoolRecord",
        "parsedSchoolRecordSummary",
        "rawSchoolRecordText",
    ):
        if k in forms and not _is_empty_value(forms.get(k)):
            return True

    # 그 외 top-level에 의미 있는 데이터가 있는 경우
    for k, v in school_record.items():
        if k in ("forms", "items"):
            continue
        if not _is_empty_value(v):
            return True

    return False


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    # 너무 공격적인 컷을 피하기 위해 꼬리표를 붙임
    suffix = "\n...(생기부 컨텍스트 일부만 전달됨)"
    keep = max(0, max_chars - len(suffix))
    return text[:keep].rstrip() + suffix


def _stringify(value: Any, max_chars: int) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _truncate(value.strip(), max_chars)
    if isinstance(value, (int, float, bool)):
        return _truncate(str(value), max_chars)
    try:
        dumped = json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        dumped = str(value)
    return _truncate(dumped, max_chars)


def build_school_record_context_text(
    school_record: Optional[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """
    LLM 프롬프트에 넣을 "생기부 컨텍스트" 텍스트 생성.
    - 너무 긴 생기부를 그대로 넣지 않기 위해 섹션별/전체 길이를 제한한다.
    - 구조화된 텍스트(학년별 요약) 우선, 없으면 요약/파싱 결과를 사용한다.
    """
    if not has_meaningful_school_record(school_record):
        return ""

    school_record = dict(school_record or {})
    forms = school_record.get("forms")
    if not isinstance(forms, dict):
        forms = {}
    if not forms:
        # 레거시/직접 저장 케이스
        forms = school_record

    lines: list[str] = []
    lines.append(
        "아래는 사용자가 연동한 학교생활기록부(생기부) 데이터입니다. "
        "이 데이터에 근거해 답변을 개인화하되, 데이터에 없는 사실은 임의로 만들지 마세요."
    )

    summary = forms.get("parsedSchoolRecordSummary") or school_record.get("parsedSchoolRecordSummary")
    if summary and not _is_empty_value(summary):
        lines.append("")
        lines.append("[생기부 요약]")
        lines.append(_stringify(summary, 2500))

    creative = forms.get("creativeActivity") or {}
    if isinstance(creative, dict) and not _is_empty_value(creative):
        by_grade = creative.get("byGrade") if isinstance(creative.get("byGrade"), dict) else {}
        lines.append("")
        lines.append("[창의적체험활동상황]")
        for g in ("1", "2", "3"):
            gg = by_grade.get(g) or {}
            if not isinstance(gg, dict) or _is_empty_value(gg):
                continue
            auton = gg.get("autonomousNotes")
            club = gg.get("clubNotes")
            career = gg.get("careerNotes")
            lines.append(f"- {g}학년")
            if auton and not _is_empty_value(auton):
                lines.append(f"  자율: {_stringify(auton, 900)}")
            if club and not _is_empty_value(club):
                lines.append(f"  동아리: {_stringify(club, 900)}")
            if career and not _is_empty_value(career):
                lines.append(f"  진로: {_stringify(career, 900)}")

    academic = forms.get("academicDev") or {}
    if isinstance(academic, dict) and not _is_empty_value(academic):
        by_grade = academic.get("byGrade") if isinstance(academic.get("byGrade"), dict) else {}
        lines.append("")
        lines.append("[과목별세부능력및특기사항(세특)]")
        for g in ("1", "2", "3"):
            gg = by_grade.get(g) or {}
            if not isinstance(gg, dict) or _is_empty_value(gg):
                continue
            subjects = gg.get("subjects") if isinstance(gg.get("subjects"), list) else []
            notes = gg.get("notes") if isinstance(gg.get("notes"), list) else []
            if not subjects and not notes:
                continue
            lines.append(f"- {g}학년")
            for idx in range(max(len(subjects), len(notes))):
                subj = subjects[idx] if idx < len(subjects) else f"과목{idx+1}"
                note = notes[idx] if idx < len(notes) else ""
                if _is_empty_value(note):
                    continue
                lines.append(f"  {subj}: {_stringify(note, 900)}")

    individual = forms.get("individualDev") or {}
    if isinstance(individual, dict) and not _is_empty_value(individual):
        by_grade = individual.get("byGrade") if isinstance(individual.get("byGrade"), dict) else {}
        lines.append("")
        lines.append("[개인별세부능력및특기사항]")
        for g in ("1", "2", "3"):
            gg = by_grade.get(g) or {}
            if not isinstance(gg, dict) or _is_empty_value(gg):
                continue
            content = gg.get("content") or gg.get("notes")
            if _is_empty_value(content):
                continue
            lines.append(f"- {g}학년: {_stringify(content, 1200)}")

    behavior = forms.get("behaviorOpinion") or {}
    if isinstance(behavior, dict) and not _is_empty_value(behavior):
        opinions = behavior.get("opinions") if isinstance(behavior.get("opinions"), list) else None
        if opinions and not _is_empty_value(opinions):
            lines.append("")
            lines.append("[행동특성 및 종합의견]")
            for idx, op in enumerate(opinions[:3], start=1):
                if _is_empty_value(op):
                    continue
                lines.append(f"- {idx}학년: {_stringify(op, 1200)}")

    parsed = forms.get("parsedSchoolRecord") or school_record.get("parsedSchoolRecord") or {}
    if isinstance(parsed, dict) and not _is_empty_value(parsed):
        # forms 기반 텍스트가 거의 없을 때만 섹션 일부를 추가
        if len("\n".join(lines)) < 1500:
            sections = parsed.get("sections") if isinstance(parsed.get("sections"), dict) else {}
            if sections and not _is_empty_value(sections):
                lines.append("")
                lines.append("[파싱된 생기부 원문(일부)]")
                for k in ("creative", "subject", "individual", "behavior"):
                    v = sections.get(k)
                    if _is_empty_value(v):
                        continue
                    lines.append(f"- {k}: {_stringify(v, 1500)}")

    return _truncate("\n".join(lines).strip(), max_chars)

