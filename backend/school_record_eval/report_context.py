from __future__ import annotations

import json
from typing import Any, Dict, Optional


DEFAULT_REPORT_MAX_CONTEXT_CHARS = 60000


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


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
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


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if _is_empty_value(value):
            continue
        return str(value).strip()
    return ""


def build_school_record_report_context_text(
    school_record: Optional[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_REPORT_MAX_CONTEXT_CHARS,
) -> str:
    """
    생기부 전용 심층 보고서 에이전트용 컨텍스트.
    기존 공용 컨텍스트와 분리된 전용 빌더.
    """
    if not isinstance(school_record, dict) or not school_record:
        return ""

    school_record = dict(school_record or {})
    forms = _as_dict(school_record.get("forms"))
    if not forms:
        forms = school_record

    per_note_chars = min(12000, max(2500, max_chars // 5))
    per_block_chars = min(20000, max(4000, max_chars // 3))

    lines: list[str] = []
    lines.append(
        "아래는 user_profiles.school_record에서 가져온 실제 생기부 텍스트입니다. "
        "가능한 모든 항목(학년별/과목별/비교과)을 빠짐없이 근거로 사용해 분석하세요. "
        "데이터에 없는 사실은 임의로 만들지 마세요."
    )
    lines.append(
        "세특 평가는 각 항목의 실제 문장을 바탕으로 계기-심화-역량-변화 흐름을 검토하세요."
    )

    summary = forms.get("parsedSchoolRecordSummary") or school_record.get("parsedSchoolRecordSummary")
    if summary and not _is_empty_value(summary):
        lines.append("")
        lines.append("[생기부 요약]")
        lines.append(_stringify(summary, per_block_chars))

    parsed = _as_dict(forms.get("parsedSchoolRecord") or school_record.get("parsedSchoolRecord"))
    sections = _as_dict(parsed.get("sections"))

    academic_rows_total = 0
    academic = _as_dict(sections.get("academicDevelopment"))
    academic_by_grade = _as_dict(academic.get("by_grade"))
    if academic_by_grade:
        lines.append("")
        lines.append("[과목별세부능력및특기사항(세특) 원문]")
        for grade in ("1", "2", "3"):
            rows = _as_list(academic_by_grade.get(grade))
            if not rows:
                continue
            lines.append(f"- {grade}학년 ({len(rows)}건)")
            for idx, row in enumerate(rows, start=1):
                row_dict = _as_dict(row)
                subject = _first_non_empty(row_dict.get("subject"), row_dict.get("과목"), f"과목{idx}")
                note = _first_non_empty(row_dict.get("note"), row_dict.get("내용"), row_dict.get("세특"))
                if not note:
                    continue
                academic_rows_total += 1
                lines.append(f"  [{idx}] {subject}")
                lines.append(f"    {_stringify(note, per_note_chars)}")

    if academic:
        for block_key, label in (
            ("general_elective", "교과학습발달상황-일반선택"),
            ("career_elective", "교과학습발달상황-진로선택"),
            ("pe_arts", "교과학습발달상황-체육예술"),
        ):
            block = _as_dict(academic.get(block_key))
            if not block:
                continue
            lines.append("")
            lines.append(f"[{label}]")
            for grade in ("1", "2", "3"):
                grade_block = _as_dict(block.get(grade))
                rows = _as_list(grade_block.get("rows"))
                if not rows:
                    continue
                lines.append(f"- {grade}학년 ({len(rows)}건)")
                for idx, row in enumerate(rows, start=1):
                    lines.append(f"  [{idx}] {_stringify(row, 1800)}")

    creative = _as_dict(sections.get("creativeActivity"))
    creative_by_grade = _as_dict(creative.get("by_grade"))
    creative_hours_by_grade = _as_dict(creative.get("hours_by_grade"))
    if creative_by_grade or creative_hours_by_grade:
        lines.append("")
        lines.append("[창의적체험활동상황]")
        for grade in ("1", "2", "3"):
            note_block = _as_dict(creative_by_grade.get(grade))
            hour_block = _as_dict(creative_hours_by_grade.get(grade))
            if _is_empty_value(note_block) and _is_empty_value(hour_block):
                continue
            lines.append(f"- {grade}학년")
            if not _is_empty_value(note_block):
                for key, value in note_block.items():
                    if _is_empty_value(value):
                        continue
                    lines.append(f"  {key}: {_stringify(value, per_note_chars)}")
            if not _is_empty_value(hour_block):
                lines.append(f"  시간/시수: {_stringify(hour_block, 2000)}")

    behavior = _as_dict(sections.get("behaviorOpinion"))
    behavior_by_grade = _as_dict(behavior.get("by_grade"))
    if behavior_by_grade:
        lines.append("")
        lines.append("[행동특성 및 종합의견 원문]")
        for grade in ("1", "2", "3"):
            opinion = behavior_by_grade.get(grade)
            if _is_empty_value(opinion):
                continue
            lines.append(f"- {grade}학년: {_stringify(opinion, per_note_chars)}")

    attendance = _as_dict(sections.get("attendance"))
    attendance_rows = _as_list(attendance.get("rows"))
    if attendance_rows:
        lines.append("")
        lines.append("[출결사항]")
        for idx, row in enumerate(attendance_rows, start=1):
            lines.append(f"- [{idx}] {_stringify(row, 1800)}")

    volunteer = _as_dict(sections.get("volunteerActivity"))
    volunteer_rows = _as_list(volunteer.get("rows"))
    if volunteer_rows:
        lines.append("")
        lines.append("[봉사활동]")
        for idx, row in enumerate(volunteer_rows, start=1):
            lines.append(f"- [{idx}] {_stringify(row, 1800)}")

    certificates = _as_dict(sections.get("certificates"))
    cert_rows = _as_list(certificates.get("rows"))
    cert_items = _as_list(certificates.get("items"))
    if cert_rows or cert_items:
        lines.append("")
        lines.append("[자격증 및 인증 취득사항]")
        for idx, row in enumerate(cert_rows or cert_items, start=1):
            lines.append(f"- [{idx}] {_stringify(row, 1600)}")

    academic_legacy = _as_dict(forms.get("academicDev"))
    legacy_by_grade = _as_dict(academic_legacy.get("byGrade"))
    if legacy_by_grade and academic_rows_total == 0:
        lines.append("")
        lines.append("[과목별세부능력및특기사항(레거시 forms)]")
        for grade in ("1", "2", "3"):
            grade_block = _as_dict(legacy_by_grade.get(grade))
            subjects = _as_list(grade_block.get("subjects"))
            notes = _as_list(grade_block.get("notes"))
            if not subjects and not notes:
                continue
            lines.append(f"- {grade}학년")
            for idx in range(max(len(subjects), len(notes))):
                subject = subjects[idx] if idx < len(subjects) else f"과목{idx + 1}"
                note = notes[idx] if idx < len(notes) else ""
                if _is_empty_value(note):
                    continue
                lines.append(f"  [{idx + 1}] {subject}: {_stringify(note, per_note_chars)}")

    raw_text = _first_non_empty(forms.get("rawSchoolRecordText"), school_record.get("rawSchoolRecordText"))
    if raw_text:
        current_text = "\n".join(lines).strip()
        remaining = max_chars - len(current_text) - 64
        if remaining > 1200:
            lines.append("")
            lines.append("[생기부 원문 텍스트(raw)]")
            lines.append(_truncate(raw_text, remaining))

    return _truncate("\n".join(lines).strip(), max_chars)
