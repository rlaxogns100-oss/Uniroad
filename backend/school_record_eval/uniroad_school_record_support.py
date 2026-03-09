"""
생기부 평가 API 라우터

- prefix: /api/school-record (main.py에서 지정)
- 로그인 유저의 세특 데이터는 user_profiles.metadata.school_record 에 연동 저장
"""
import asyncio
import copy
from datetime import datetime, timezone
from io import BytesIO
import hashlib
from operator import itemgetter
import re
import os
import tempfile
import time
import json
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, HTTPException, Header, Depends, Body, UploadFile, File

try:
    import pdfplumber
    from pdfplumber.utils import cluster_objects
except Exception:
    pdfplumber = None
    cluster_objects = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

from middleware.auth import optional_auth, get_current_user
from config.config import settings
from services.supabase_client import SupabaseService
from utils.school_record_context import has_meaningful_school_record

from .models import SchoolRecordEvaluateRequest, SchoolRecordEvaluateResponse
from .service import evaluate_school_record
from .diagnose import diagnose_school_record

router = APIRouter()
MAX_SAVED_ITEMS = 50  # 유저당 최근 저장 개수
MAX_PDF_SIZE_MB = int(os.getenv("SCHOOL_RECORD_MAX_PDF_MB", "30"))
MAX_PDF_SIZE = MAX_PDF_SIZE_MB * 1024 * 1024
MIN_EXTRACTED_TEXT_CHARS = 50
PDF_WORD_X_TOLERANCE = float(os.getenv("SCHOOL_RECORD_PDF_WORD_X_TOLERANCE", "2"))
PDF_WORD_Y_TOLERANCE = float(os.getenv("SCHOOL_RECORD_PDF_WORD_Y_TOLERANCE", "2"))
PDF_LINE_CLUSTER_TOLERANCE = float(os.getenv("SCHOOL_RECORD_PDF_LINE_CLUSTER_TOLERANCE", "1.8"))
RULE_PARSER_VERSION = "v14"


def _compact(text: str) -> str:
    s = re.sub(r"\s+", "", text or "")
    # 전각 숫자 → 반각 (OCR/복사 변형 대응)
    for i, c in enumerate("０１２３４５６７８９"):
        s = s.replace(c, str(i))
    return s


def _merge_text(current: str, incoming: str) -> str:
    incoming = (incoming or "").strip()
    if not incoming:
        return current
    if not current:
        return incoming
    return f"{current}\n{incoming}"


def _extract_text_with_pdfplumber_words(file_bytes: bytes) -> Tuple[str, int]:
    """
    pdfplumber.extract_words 기반 추출.
    - extract_text의 메모리/정렬 이슈를 피하기 위해 단어 추출 후 y(top) 클러스터로 줄 복원
    """
    if pdfplumber is None or cluster_objects is None:
        return "", 0

    page_count = 0
    page_texts: List[str] = []
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                words = page.extract_words(
                    x_tolerance=PDF_WORD_X_TOLERANCE,
                    y_tolerance=PDF_WORD_Y_TOLERANCE,
                    keep_blank_chars=False,
                    use_text_flow=True,
                ) or []
                if not words:
                    continue

                line_clusters = cluster_objects(words, itemgetter("top"), PDF_LINE_CLUSTER_TOLERANCE) or []
                lines: List[str] = []
                for cluster in line_clusters:
                    if not cluster:
                        continue
                    ordered = sorted(
                        cluster,
                        key=lambda w: (float(w.get("x0", 0.0)), float(w.get("x1", 0.0))),
                    )
                    line = " ".join(
                        str(word.get("text", "")).strip()
                        for word in ordered
                        if str(word.get("text", "")).strip()
                    )
                    line = re.sub(r"\s+", " ", line).strip()
                    if line:
                        lines.append(line)

                if lines:
                    page_texts.append("\n".join(lines))
    except Exception:
        return "", page_count

    return "\n\n".join(page_texts).strip(), page_count


def _extract_text_with_pypdf2(file_bytes: bytes) -> Tuple[str, int]:
    """PyPDF2 텍스트 추출 폴백."""
    if PdfReader is None:
        return "", 0
    try:
        reader = PdfReader(BytesIO(file_bytes))
        chunks: List[str] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                chunks.append(page_text)
        text = "\n".join(chunks)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines).strip(), len(reader.pages)
    except Exception:
        return "", 0


def _extract_text_from_pdf_bytes(file_bytes: bytes) -> Tuple[str, int, str]:
    """
    PDF 텍스트 추출: pdfplumber → PyPDF2 (Gemini 미사용)
    """
    text_plumber, page_count = _extract_text_with_pdfplumber_words(file_bytes)
    if len(text_plumber.strip()) >= MIN_EXTRACTED_TEXT_CHARS:
        return text_plumber, page_count, "pdfplumber_words"

    text_pypdf2, page_count_pypdf2 = _extract_text_with_pypdf2(file_bytes)
    if page_count <= 0:
        page_count = page_count_pypdf2
    if len(text_pypdf2.strip()) >= MIN_EXTRACTED_TEXT_CHARS:
        return text_pypdf2, page_count, "pypdf2"

    # 부분 추출이라도 있으면 반환
    if text_plumber.strip():
        return text_plumber, page_count, "pdfplumber_words_partial"
    if text_pypdf2.strip():
        return text_pypdf2, page_count, "pypdf2_partial"

    return "", page_count, "none"


def _build_pdf_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _parsed_school_record_signal(parsed_school_record: Dict[str, Any]) -> Dict[str, int]:
    sections = (parsed_school_record or {}).get("sections") or {}

    attendance_rows = len(((sections.get("attendance") or {}).get("rows") or []))
    volunteer_rows = len(((sections.get("volunteerActivity") or {}).get("rows") or []))

    creative = sections.get("creativeActivity") or {}
    creative_by_grade = creative.get("by_grade") or {}
    creative_hours_by_grade = creative.get("hours_by_grade") or {}
    creative_note_count = 0
    creative_hour_count = 0
    for g in ("1", "2", "3"):
        for key in ("autonomousNotes", "clubNotes", "careerNotes"):
            if str((creative_by_grade.get(g) or {}).get(key) or "").strip():
                creative_note_count += 1
        for key in ("autonomousHours", "clubHours", "careerHours"):
            if (creative_hours_by_grade.get(g) or {}).get(key) is not None:
                creative_hour_count += 1

    academic = sections.get("academicDevelopment") or {}
    by_grade = academic.get("by_grade") or {}
    academic_note_rows = sum(len(by_grade.get(g) or []) for g in ("1", "2", "3"))
    academic_table_rows = 0
    for table_key in ("general_elective", "career_elective", "pe_arts"):
        table = academic.get(table_key) or {}
        for g in ("1", "2", "3"):
            academic_table_rows += len(((table.get(g) or {}).get("rows") or []))

    behavior_by_grade = (sections.get("behaviorOpinion") or {}).get("by_grade") or {}
    behavior_grade_count = sum(1 for g in ("1", "2", "3") if str(behavior_by_grade.get(g) or "").strip())

    return {
        "attendance_rows": attendance_rows,
        "volunteer_rows": volunteer_rows,
        "creative_note_count": creative_note_count,
        "creative_hour_count": creative_hour_count,
        "academic_note_rows": academic_note_rows,
        "academic_table_rows": academic_table_rows,
        "behavior_grade_count": behavior_grade_count,
    }


def _looks_like_school_record_template(raw_text: str) -> bool:
    compact = _compact(raw_text or "")
    return (
        "출결상황" in compact
        and "창의적체험활동상황" in compact
        and "교과학습발달상황" in compact
    )


def _should_fallback_to_rule(raw_text: str, parsed_forms: Dict[str, Any]) -> bool:
    parsed_school_record = (parsed_forms or {}).get("parsedSchoolRecord") or {}
    signal = _parsed_school_record_signal(parsed_school_record)

    # 완전 무응답 수준
    if (
        signal["attendance_rows"] == 0
        and signal["volunteer_rows"] == 0
        and signal["creative_note_count"] == 0
        and signal["academic_note_rows"] == 0
        and signal["academic_table_rows"] == 0
        and signal["behavior_grade_count"] == 0
    ):
        return True

    # 생기부 템플릿이 명확할 때 핵심 섹션 누락은 룰 파서로 폴백
    if _looks_like_school_record_template(raw_text):
        if signal["attendance_rows"] == 0:
            return True
        if (signal["academic_note_rows"] + signal["academic_table_rows"]) == 0:
            return True
        if signal["behavior_grade_count"] == 0:
            return True

    return False


def _is_cache_compatible(forms: Dict[str, Any], import_meta: Dict[str, Any]) -> bool:
    """동일 파일 캐시를 재사용해도 되는지 검증.
    - raw/parsed 데이터가 있어야 함
    - rule 파서는 현재 RULE_PARSER_VERSION과 일치해야 함
    - gemini 파서는 parserVersion=gemini면 재사용 허용
    """
    if not bool(forms.get("rawSchoolRecordText")):
        return False
    parsed = forms.get("parsedSchoolRecord")
    if not isinstance(parsed, dict) or not parsed:
        return False

    parse_method = str(import_meta.get("parse_method") or "").strip().lower()
    parser_version = str(parsed.get("parserVersion") or "").strip()

    if parse_method == "rule":
        return parser_version == RULE_PARSER_VERSION
    if parse_method == "gemini":
        if parser_version != "gemini":
            return False
        # Gemini 결과가 템플릿 대비 불완전하면 캐시 재사용하지 않고 재파싱 유도
        raw_text = str(forms.get("rawSchoolRecordText") or "")
        if _should_fallback_to_rule(raw_text, {"parsedSchoolRecord": parsed}):
            return False
        return True

    # 메타 누락된 구버전 데이터는 재파싱 유도
    return parser_version in {RULE_PARSER_VERSION, "gemini"}


def _detect_section_key(line: str) -> Optional[str]:
    compact = _compact(line)
    if not compact:
        return None
    # 파싱 비대상 구간(섹션 오염 방지)
    # NOTE: 과도한 ignore는 중간 섹션이 끊기는 원인이 되어 최소 조건만 유지한다.
    # 표 셀/서술문 오탐으로 섹션이 끊기지 않도록 heading 길이일 때만 무시한다.
    if "수상경력" in compact and len(compact) <= 40:
        return "__ignore__"
    if ("독서활동상황" in compact or ("독서활동" in compact and "상황" in compact)) and len(compact) <= 40:
        return "__ignore__"
    # 출결
    if "출결상황" in compact or ("출결" in compact and "상황" in compact):
        return "attendance"
    # 자격증·인증 (취득사항/취득상황 변형 포함)
    if "자격증및인증취득" in compact or ("자격증" in compact and ("인증" in compact or "취득" in compact)):
        return "certificates"
    if "자격증" in compact and "취득" in compact and ("사항" in compact or "상황" in compact):
        return "certificates"
    # 창의적 체험
    if "창의적체험활동상황" in compact or ("창의적" in compact and "체험" in compact):
        return "creative_activity"
    # 봉사
    if "봉사활동실적" in compact or ("봉사" in compact and "실적" in compact):
        return "volunteer_activity"
    # 행동특성·종합의견
    if "행동특성및종합의견" in compact or (("행동" in compact and "특성" in compact) and ("종합" in compact or "의견" in compact)):
        return "behavior_opinion"
    # 교과학습발달상황
    if "교과학습발달상황" in compact or ("교과" in compact and "학습" in compact and "발달" in compact):
        return "academic_development"
    if re.search(r"[123]학년.*(일반선택과목|진로선택과목|체육예술과목|체육·예술과목)", compact):
        return "academic_development"
    return None


def _detect_table_header_section_key(line: str) -> Optional[str]:
    """섹션 제목이 OCR에서 누락됐을 때 표 헤더만으로 섹션을 복원."""
    if not _is_markdown_table_line(line):
        return None
    cells = [_compact(c) for c in _split_markdown_row(line)]
    if not cells:
        return None
    joined = "".join(cells)

    if "학년" in joined and "수업일수" in joined and ("결석" in joined or "지각" in joined):
        return "attendance"
    if "구분" in joined and "명칭또는종류" in joined and ("취득년월일" in joined or "취득연월일" in joined):
        return "certificates"
    if "학년" in joined and "영역" in joined and "시간" in joined and "특기사항" in joined:
        return "creative_activity"
    if "학년" in joined and ("일자또는기간" in joined or "일자" in joined) and "활동내용" in joined:
        return "volunteer_activity"
    if "학년" in joined and "행동특성및종합의견" in joined:
        return "behavior_opinion"
    if "학기" in joined and "교과" in joined and "과목" in joined and "단위수" in joined:
        return "academic_development"
    if "과목" in joined and "세부능력및특기사항" in joined:
        return "academic_development"
    return None


def _split_school_record_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {
        "attendance": [],
        "certificates": [],
        "creative_activity": [],
        "volunteer_activity": [],
        "academic_development": [],
        "behavior_opinion": [],
    }
    current_key: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key = _detect_section_key(line) or _detect_table_header_section_key(line)
        if key:
            if key == "__ignore__":
                current_key = None
                continue
            current_key = key
            sections[key].append(line)
            continue
        if current_key:
            sections[current_key].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _extract_grade_blocks(section_text: str) -> Dict[str, str]:
    blocks: Dict[str, List[str]] = {"1": [], "2": [], "3": []}
    current_grade: Optional[str] = None
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        compact = _compact(line)
        # "1학년", "[1학년]", "1 학년 일반선택과목" 등 명시적 학년 헤더만 인정
        grade_match = re.match(r"^\[?\s*([123])\s*학년[\]\s].*$", line)
        if not grade_match:
            grade_match = re.search(r"([123])학년", compact)
        if grade_match:
            current_grade = grade_match.group(1)
            blocks[current_grade].append(line)
            continue
        if current_grade:
            blocks[current_grade].append(line)
    return {grade: "\n".join(lines).strip() for grade, lines in blocks.items()}


def _is_noise_line(line: str) -> bool:
    compact = _compact(line)
    if not compact:
        return True
    if re.search(r"반\d+번호\d+이름", compact):
        return True
    if re.search(r"\d+/\d+\d{4}년\d{1,2}월\d{1,2}일", compact):
        return True
    if re.search(r"\d{4}년\d{1,2}월\d{1,2}일\d+/\d+", compact):
        return True
    if compact in {
        "입력",
        "학년",
        "영역",
        "시간",
        "특기사항",
        "영역시간특기사항",
        "학년영역시간특기사항",
        "출결상황",
        "자격증및인증취득사항",
        "자격증및인증취득상황",
        "창의적체험활동상황",
        "봉사활동실적",
        "교과학습발달상황",
        "행동특성및종합의견",
        "구분",
        "명칭또는종류",
        "번호또는내용",
        "취득년월일",
        "발급기관",
        "일자또는기간",
        "장소또는주관기관명",
        "활동내용",
        "학기",
        "교과",
        "과목",
        "단위수",
        "원점수",
        "과목평균",
        "표준편차",
        "성취도",
        "수강자수",
        "석차등급",
        "성취도별분포비율",
        "이수단위합계",
        "세부능력및특기사항",
        "A",
        "B",
        "C",
    }:
        return True
    if "재학생만작성" in compact:
        return True
    if "대입에반영되지않으나" in compact:
        return True
    return False


def _is_empty_marker(line: str) -> bool:
    compact = _compact(line)
    if "해당사항없음" in compact:
        return True
    if "해당" in compact and "없음" in compact and len(compact) <= 20:
        return True
    return False


def _strip_markdown(text: str) -> str:
    s = str(text or "")
    s = s.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    s = re.sub(r"</?[^>]+>", "", s)
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = re.sub(r"^#+\s*", "", s.strip())
    return s.strip()


def _is_markdown_table_line(line: str) -> bool:
    s = (line or "").strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _split_markdown_row(line: str) -> List[str]:
    s = (line or "").strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [_strip_markdown(cell) for cell in s.split("|")]


def _is_markdown_separator_row(cells: List[str]) -> bool:
    if not cells:
        return False
    normalized = [re.sub(r"\s+", "", str(c or "")) for c in cells]
    return all(re.fullmatch(r":?-{2,}:?", c) for c in normalized if c) and any(c for c in normalized)


def _extract_markdown_tables(section_text: str) -> List[Dict[str, Any]]:
    lines = section_text.splitlines()
    tables: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if not _is_markdown_table_line(lines[i]):
            i += 1
            continue

        start = i
        block: List[str] = []
        while i < len(lines) and _is_markdown_table_line(lines[i]):
            block.append(lines[i].strip())
            i += 1

        if len(block) < 2:
            continue

        parsed_rows = [_split_markdown_row(ln) for ln in block]
        if not _is_markdown_separator_row(parsed_rows[1]):
            continue

        header = parsed_rows[0]
        data_rows: List[List[str]] = []
        for row in parsed_rows[2:]:
            if _is_markdown_separator_row(row):
                continue
            data_rows.append(row)

        before: List[str] = []
        j = start - 1
        while j >= 0 and len(before) < 8:
            s = lines[j].strip()
            if s:
                before.append(s)
            j -= 1
        before.reverse()

        after: List[str] = []
        j = i
        while j < len(lines) and len(after) < 6:
            s = lines[j].strip()
            if s:
                after.append(s)
            j += 1

        tables.append(
            {
                "start": start,
                "end": i - 1,
                "header": header,
                "rows": data_rows,
                "before": before,
                "after": after,
            }
        )

    return tables


def _find_header_index(headers: List[str], include: List[str], exclude: Optional[List[str]] = None) -> int:
    exclude = exclude or []
    for idx, header in enumerate(headers):
        h = _compact(header)
        if all(tok in h for tok in include) and not any(tok in h for tok in exclude):
            return idx
    return -1


def _row_cell(cells: List[str], idx: int) -> str:
    if idx < 0 or idx >= len(cells):
        return ""
    return _strip_markdown(cells[idx])


def _is_blank_value(value: str) -> bool:
    c = _compact(value)
    return c in {"", ".", "-", "·", "—", "na", "n/a"}


def _parse_int_cell(value: str, *, dot_as_zero: bool = False) -> Optional[int]:
    value = _strip_markdown(value)
    c = _compact(value)
    if not c:
        return None
    if _is_empty_marker(value):
        return None
    if c in {".", "-", "·", "—"}:
        return 0 if dot_as_zero else None
    m = re.search(r"-?\d+(?:\.\d+)?", value)
    if not m:
        return None
    try:
        return int(float(m.group(0)))
    except Exception:
        return None


def _parse_score_avg_std(value: str) -> Tuple[str, str, str]:
    text = _strip_markdown(value)
    if not text:
        return "", "", ""
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)(?:\s*\(\s*(-?\d+(?:\.\d+)?)\s*\))?", text)
    if m:
        return m.group(1), m.group(2), m.group(3) or ""
    return text, "", ""


def _parse_ach_count(value: str) -> Tuple[str, str]:
    text = _strip_markdown(value)
    if not text:
        return "", ""
    m = re.search(r"([A-Za-z가-힣]+)\s*\(\s*([0-9.]+)\s*\)", text)
    if m:
        return m.group(1), m.group(2)
    return text, ""


def _parse_distribution_abc(value: str) -> Dict[str, str]:
    text = _strip_markdown(value)
    out = {"A": "", "B": "", "C": ""}
    for key in ("A", "B", "C"):
        matches = re.findall(rf"{key}\s*\(\s*([^)]+)\s*\)", text)
        if matches:
            # "A(266)A(38.0)"처럼 붙은 경우 성취도별 분포는 마지막 값을 사용
            out[key] = str(matches[-1]).strip()
    return out


def _parse_creative_activity(section_text: str) -> Dict[str, Any]:
    by_grade: Dict[str, Dict[str, str]] = {
        "1": {"autonomousNotes": "", "clubNotes": "", "careerNotes": ""},
        "2": {"autonomousNotes": "", "clubNotes": "", "careerNotes": ""},
        "3": {"autonomousNotes": "", "clubNotes": "", "careerNotes": ""},
    }
    hours_by_grade: Dict[str, Dict[str, Optional[int]]] = {
        "1": {"autonomousHours": None, "clubHours": None, "careerHours": None},
        "2": {"autonomousHours": None, "clubHours": None, "careerHours": None},
        "3": {"autonomousHours": None, "clubHours": None, "careerHours": None},
    }

    # 1) OCR markdown 표 파싱 우선
    parsed_from_table = False
    for table in _extract_markdown_tables(section_text):
        headers = [_compact(h) for h in table["header"]]
        if not (
            any("학년" in h for h in headers)
            and any("영역" in h for h in headers)
            and any("시간" in h for h in headers)
            and any("특기사항" in h for h in headers)
        ):
            continue

        idx_grade = _find_header_index(table["header"], ["학년"])
        idx_area = _find_header_index(table["header"], ["영역"])
        idx_hours = _find_header_index(table["header"], ["시간"])
        idx_note = _find_header_index(table["header"], ["특기사항"])
        if min(idx_grade, idx_area, idx_hours, idx_note) < 0:
            continue

        parsed_from_table = True
        for row_cells in table["rows"]:
            joined = " ".join(row_cells)
            if _is_empty_marker(joined):
                continue

            grade_text = _row_cell(row_cells, idx_grade)
            area_text = _row_cell(row_cells, idx_area)
            hours_text = _row_cell(row_cells, idx_hours)
            note_text = _row_cell(row_cells, idx_note)
            if not area_text:
                continue

            grade_match = re.search(r"([123])", _compact(grade_text))
            if not grade_match:
                continue
            grade = grade_match.group(1)
            area_compact = _compact(area_text)

            if "자율" in area_compact:
                note_key = "autonomousNotes"
                hour_key = "autonomousHours"
            elif "동아리" in area_compact:
                note_key = "clubNotes"
                hour_key = "clubHours"
            elif "진로" in area_compact:
                note_key = "careerNotes"
                hour_key = "careerHours"
            else:
                continue

            parsed_hours = _parse_int_cell(hours_text, dot_as_zero=True)
            if parsed_hours is not None:
                hours_by_grade[grade][hour_key] = parsed_hours

            if note_text and not _is_empty_marker(note_text):
                by_grade[grade][note_key] = _merge_text(by_grade[grade][note_key], note_text)

    if parsed_from_table:
        return {"by_grade": by_grade, "hours_by_grade": hours_by_grade}

    # 2) 템플릿 기반 패턴 매칭(고정 레이아웃 가정):
    #    자율/동아리/진로 행을 순서대로 추출해 학년(1~3)에 매핑
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    marker_re = re.compile(
        r"^\s*(?:(?P<grade>[123])\s*)?(?P<area>자율활동|동아리활동|진로활동)\s*(?P<hours>\d{1,3}(?:\.\d+)?)?\s*(?P<rest>.*)$"
    )
    markers: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines):
        m = marker_re.match(line)
        if not m:
            continue
        area = m.group("area")
        if not area:
            continue
        grade = (m.group("grade") or "").strip() or None
        hours_raw = (m.group("hours") or "").strip()
        rest = (m.group("rest") or "").strip()

        # OCR 결합 보정: "54 2학기" -> "542학기"로 붙는 경우 마지막 숫자는 학기 표기일 가능성이 큼
        if hours_raw and rest.startswith("학기") and len(hours_raw) >= 2:
            term_digit = hours_raw[-1]
            if term_digit in {"1", "2"}:
                trimmed = hours_raw[:-1]
                if re.fullmatch(r"\d+(?:\.\d+)?", trimmed):
                    hours_raw = trimmed
                    rest = f"{term_digit}학기 {rest[len('학기'):].strip()}".strip()

        hours_val: Optional[int] = None
        if hours_raw:
            try:
                hours_val = int(float(hours_raw))
            except Exception:
                hours_val = None
        markers.append(
            {
                "idx": idx,
                "line": line,
                "grade": grade,
                "area": area,
                "hours": hours_val,
                "rest": rest,
            }
        )

    def _creative_keys(area_text: str) -> Tuple[str, str]:
        if "자율" in area_text:
            return "autonomousNotes", "autonomousHours"
        if "동아리" in area_text:
            return "clubNotes", "clubHours"
        return "careerNotes", "careerHours"

    if markers:
        seq_template = ["자율활동", "동아리활동", "진로활동"] * 3
        seq_score = 0
        if len(markers) >= 9:
            seq_score = sum(1 for i in range(9) if markers[i]["area"] == seq_template[i])
        use_fixed_triplet = len(markers) >= 9 and seq_score >= 6

        # 고정 템플릿에서는 영역/시간 마커가 행 중간에 끼어드는 경우가 있어
        # 인접 마커의 중간 지점을 행 경계로 사용한다.
        resolved: List[Dict[str, Any]] = []
        current_grade: Optional[str] = None
        for i, marker in enumerate(markers):
            explicit_grade = marker["grade"]
            area = marker["area"]
            note_key, hour_key = _creative_keys(area)

            if use_fixed_triplet and i < 9:
                grade = str((i // 3) + 1)
            elif explicit_grade in {"1", "2", "3"}:
                grade = explicit_grade
            else:
                if current_grade is None:
                    # 해당 영역의 시간 슬롯이 비어있는 첫 학년을 기본값으로
                    grade = next((g for g in ("1", "2", "3") if hours_by_grade[g][hour_key] is None), "1")
                else:
                    grade = current_grade
                    # 같은 학년에 같은 영역 시간이 이미 있으면 다음 학년으로 전진
                    if hours_by_grade[grade][hour_key] is not None:
                        if grade == "1" and hours_by_grade["2"][hour_key] is None:
                            grade = "2"
                        elif grade in {"1", "2"} and hours_by_grade["3"][hour_key] is None:
                            grade = "3"
            current_grade = grade

            resolved.append(
                {
                    **marker,
                    "grade_resolved": grade,
                    "note_key": note_key,
                    "hour_key": hour_key,
                }
            )

        boundaries: List[Tuple[int, int]] = []
        if resolved:
            def _looks_like_next_row_start(ln: str, next_area: str, next_grade: str) -> bool:
                s = (ln or "").strip()
                if not s:
                    return False
                c = _compact(s)
                if _is_noise_line(s):
                    return False
                if c in {"1", "2", "3"}:
                    return False
                if f"{next_grade}학기" in c:
                    return True
                if "공공기관의정보공개에관한법률" in c:
                    return True
                if next_area == "동아리활동":
                    if s.startswith("(") or "동아리" in c:
                        return True
                elif next_area == "진로활동":
                    if ("희망분야" in c) or ("진로표준화검사" in c) or ("나의꿈발표" in c):
                        return True
                elif next_area == "자율활동":
                    if ("학급자치" in c) or (f"{next_grade}학기" in c):
                        return True
                return False

            mids: List[int] = []
            for i in range(len(resolved) - 1):
                cur_idx = int(resolved[i]["idx"])
                next_idx = int(resolved[i + 1]["idx"])
                next_area = str(resolved[i + 1]["area"])
                next_grade = str(resolved[i + 1]["grade_resolved"])

                split_idx: Optional[int] = None
                for line_idx in range(cur_idx + 1, next_idx):
                    if _looks_like_next_row_start(lines[line_idx], next_area, next_grade):
                        split_idx = line_idx - 1
                        break
                if split_idx is None:
                    split_idx = (cur_idx + next_idx) // 2
                split_idx = max(cur_idx, min(split_idx, next_idx - 1))
                mids.append(split_idx)
            for i in range(len(resolved)):
                start_idx = 0 if i == 0 else mids[i - 1] + 1
                end_idx = (len(lines) - 1) if i == len(resolved) - 1 else mids[i]
                boundaries.append((start_idx, end_idx))

        assigned_any = False
        for marker, (start_idx, end_idx) in zip(resolved, boundaries):
            grade = str(marker["grade_resolved"])
            note_key = str(marker["note_key"])
            hour_key = str(marker["hour_key"])

            if marker.get("hours") is not None:
                hours_by_grade[grade][hour_key] = marker["hours"]
                assigned_any = True

            note_parts: List[str] = []
            for line_idx in range(start_idx, end_idx + 1):
                ln = lines[line_idx].strip()
                if not ln:
                    continue
                if line_idx == marker["idx"]:
                    ln = str(marker.get("rest") or "").strip()
                if not ln:
                    continue
                compact_ln = _compact(ln)
                if marker_re.match(ln):
                    continue
                if _is_noise_line(ln) or _is_empty_marker(ln):
                    continue
                if compact_ln in {"1", "2", "3"}:
                    continue
                if "창의적체험활동상황" in compact_ln:
                    continue
                if compact_ln in {"영역시간특기사항", "학년영역시간특기사항"}:
                    continue
                if compact_ln == "희망분야":
                    continue
                note_parts.append(ln)

            if note_parts:
                by_grade[grade][note_key] = _merge_text(by_grade[grade][note_key], "\n".join(note_parts))
                assigned_any = True

        if assigned_any:
            # 법령 고지문이 여러 줄로 중복 결합되는 경우 정규화
            for grade in ("1", "2", "3"):
                for key in ("autonomousNotes", "clubNotes", "careerNotes"):
                    raw_note = str(by_grade[grade].get(key) or "").strip()
                    if not raw_note:
                        continue
                    lines_dedup: List[str] = []
                    seen_lines: set[str] = set()
                    for raw_line in raw_note.splitlines():
                        ln = raw_line.strip()
                        if not ln:
                            continue
                        comp = _compact(ln)
                        if comp in seen_lines:
                            continue
                        seen_lines.add(comp)
                        lines_dedup.append(ln)
                    normalized_note = "\n".join(lines_dedup).strip()
                    compact_note = _compact(normalized_note)
                    if (
                        "공공기관의정보공개에관한법률" in compact_note
                        and "당해학년도에는제공하지않습니다" in compact_note
                        and len(compact_note) <= 260
                    ):
                        normalized_note = (
                            "해당내용은 「공공기관의 정보공개에 관한 법률」 제9조제1항제5호에 따라 "
                            "내부검토 중인 사항으로 당해학년도에는 제공하지 않습니다."
                        )
                    by_grade[grade][key] = normalized_note
            return {"by_grade": by_grade, "hours_by_grade": hours_by_grade}

    # 2) 레거시 텍스트 파서 폴백
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    current_grade: Optional[str] = None
    current_field: Optional[str] = None
    pending_hour_field: Optional[str] = None
    for idx, line in enumerate(lines):
        compact = _compact(line)
        if not compact:
            continue
        grade_match = re.search(r"([123])학년", compact)
        if grade_match:
            current_grade = grade_match.group(1)
            current_field = None
            pending_hour_field = None
            continue
        # 표 본문에서 단독 학년 숫자는 다음 영역행이 이어질 때만 학년으로 채택
        if compact in {"1", "2", "3"}:
            lookahead = " ".join(_compact(x) for x in lines[idx + 1: idx + 4])
            if any(token in lookahead for token in ("자율활동", "동아리활동", "진로활동")):
                current_grade = compact
                current_field = None
                pending_hour_field = None
            continue

        if "자율활동" in compact:
            current_field = "autonomousNotes"
            pending_hour_field = "autonomousHours"
            leading_grade = re.match(r"^\s*([123])\s*자율활동", line)
            if leading_grade:
                current_grade = leading_grade.group(1)
            hours_inline = re.search(r"자율활동\s*(\d+(?:\.\d+)?)", line)
            if current_grade and hours_inline:
                try:
                    hours_by_grade[current_grade]["autonomousHours"] = int(float(hours_inline.group(1)))
                except Exception:
                    pass
            remainder = re.sub(r"자율활동", "", line, count=1).strip(" :|-")
            remainder = re.sub(r"^\d+(?:\.\d+)?", "", remainder).strip(" :|-")
            if remainder and not _is_noise_line(remainder) and not _is_empty_marker(remainder):
                if current_grade:
                    by_grade[current_grade][current_field] = _merge_text(by_grade[current_grade][current_field], remainder)
            continue
        if "동아리활동" in compact:
            current_field = "clubNotes"
            pending_hour_field = "clubHours"
            leading_grade = re.match(r"^\s*([123])\s*동아리활동", line)
            if leading_grade:
                current_grade = leading_grade.group(1)
            hours_inline = re.search(r"동아리활동\s*(\d+(?:\.\d+)?)", line)
            if current_grade and hours_inline:
                try:
                    hours_by_grade[current_grade]["clubHours"] = int(float(hours_inline.group(1)))
                except Exception:
                    pass
            remainder = re.sub(r"동아리활동", "", line, count=1).strip(" :|-")
            remainder = re.sub(r"^\d+(?:\.\d+)?", "", remainder).strip(" :|-")
            if remainder and not _is_noise_line(remainder) and not _is_empty_marker(remainder):
                if current_grade:
                    by_grade[current_grade][current_field] = _merge_text(by_grade[current_grade][current_field], remainder)
            continue
        if "진로활동" in compact:
            current_field = "careerNotes"
            pending_hour_field = "careerHours"
            leading_grade = re.match(r"^\s*([123])\s*진로활동", line)
            if leading_grade:
                current_grade = leading_grade.group(1)
            hours_inline = re.search(r"진로활동\s*(\d+(?:\.\d+)?)", line)
            if current_grade and hours_inline:
                try:
                    hours_by_grade[current_grade]["careerHours"] = int(float(hours_inline.group(1)))
                except Exception:
                    pass
            remainder = re.sub(r"진로활동", "", line, count=1).strip(" :|-")
            remainder = re.sub(r"^\d+(?:\.\d+)?", "", remainder).strip(" :|-")
            if remainder and not _is_noise_line(remainder) and not _is_empty_marker(remainder):
                if current_grade:
                    by_grade[current_grade][current_field] = _merge_text(by_grade[current_grade][current_field], remainder)
            continue

        if current_grade and pending_hour_field and re.fullmatch(r"\d{1,4}", compact):
            hours_by_grade[current_grade][pending_hour_field] = int(compact)
            pending_hour_field = None
            continue

        if current_grade and current_field and not _is_noise_line(line) and not _is_empty_marker(line):
            by_grade[current_grade][current_field] = _merge_text(by_grade[current_grade][current_field], line)

    return {"by_grade": by_grade, "hours_by_grade": hours_by_grade}


def _infer_subject_from_note(note: str) -> str:
    """세특 본문 앞부분에서 과목명으로 쓸 수 있는 짧은 라벨 추출. 'N학년 미분류' 대신 표시용."""
    if not (note or "").strip():
        return ""
    s = (note or "").strip()
    # "국어:", "음악:", "미술 창작" 등 과목명: 또는 과목명 공백
    m = re.match(r"^([가-힣A-Za-z0-9·\s]{2,20}?)\s*[:：]\s*", s)
    if m:
        label = m.group(1).strip()
        if 2 <= len(label) <= 16 and not _is_empty_marker(label):
            return label
    # 교과/과목 흔한 이름으로 시작하는 경우
    for prefix in ("음악 연주", "음악", "미술 창작", "미술", "국어", "수학", "영어", "한국사", "통합사회", "통합과학", "과학", "기술", "체육", "한문", "제2외국어"):
        if s.startswith(prefix) or s.replace(" ", "").startswith(prefix.replace(" ", "")):
            return prefix.strip()
    # 첫 문장/구절 일부(최대 12자)를 라벨로
    first_part = re.split(r"[,.]|\s+", s, maxsplit=2)[0]
    if first_part and len(first_part) <= 12 and not re.fullmatch(r"\d+", _compact(first_part)):
        return first_part.strip()
    return ""


def _normalize_subject_match_key(text: str) -> str:
    s = _compact(text or "")
    # 과목명 매칭 시 표기 변형(중점/슬래시/괄호 등) 완화
    for ch in ("·", "ㆍ", "/", "(", ")", "[", "]"):
        s = s.replace(ch, "")
    return s


def _split_subject_prefix_line(line: str, known_subjects: Dict[str, str]) -> Tuple[str, str]:
    """세특 라인에서 '과목: 내용' 또는 '과목 내용' 접두어를 분리."""
    stripped = (line or "").strip()
    if not stripped:
        return "", ""

    m_colon = re.match(r"^([가-힣A-Za-z0-9·ㆍ\-/()ⅠⅡⅢⅣⅤ\s]{1,32})\s*[:：]\s*(.*)$", stripped)
    if m_colon:
        subject = m_colon.group(1).strip()
        rest = m_colon.group(2).strip()
        if subject and not _is_noise_line(subject) and not _is_empty_marker(subject):
            return subject, rest

    # 콜론이 없는 경우는 known subject가 선두에 오는 패턴만 허용
    for _, subject in sorted(known_subjects.items(), key=lambda x: len(x[0]), reverse=True):
        if not subject:
            continue
        if stripped == subject:
            return subject, ""
        m_prefix = re.match(rf"^{re.escape(subject)}\s+(.*)$", stripped)
        if m_prefix:
            return subject, (m_prefix.group(1) or "").strip()
    return "", ""


def _looks_like_subject_label(line: str) -> bool:
    compact = _compact(line)
    if not compact:
        return False
    if len(compact) > 24:
        return False
    if _is_noise_line(line) or _is_empty_marker(line):
        return False
    if re.fullmatch(r"\d+", compact):
        return False
    # 문장형 서술은 과목명 가능성이 낮음
    if compact.endswith(("다", "함", "음")) and len(compact) > 8:
        return False
    token_count = len(line.strip().split())
    return token_count <= 4


def _parse_academic_development(section_text: str) -> Dict[str, Any]:
    """교과학습 구간에서 세특(by_grade)만 추출. 1패스 통합 시 _parse_academic_unified 사용."""
    unified = _parse_academic_unified(section_text)
    return {"by_grade": unified["by_grade"], "raw_by_grade": unified["raw_by_grade"]}


def _parse_academic_grade_tables(section_text: str) -> Dict[str, Any]:
    """교과학습 구간에서 성적 테이블만 추출. 1패스 통합 시 _parse_academic_unified 사용."""
    unified = _parse_academic_unified(section_text)
    return {"general_elective": unified["general_elective"], "career_elective": unified["career_elective"], "pe_arts": unified["pe_arts"]}


def _find_header_exact(headers: List[str], token: str) -> int:
    target = _compact(token)
    for idx, h in enumerate(headers):
        if _compact(h) == target:
            return idx
    return -1


def _sanitize_table_value(value: str) -> str:
    value = _strip_markdown(value)
    return "" if _is_blank_value(value) else value


_SCORE_TOKEN_PATTERN = re.compile(r"-?\d+(?:\.\d+)?/-?\d+(?:\.\d+)?(?:\(-?\d+(?:\.\d+)?\))?")
_TRAILING_CREDIT_TOKEN_PATTERN = re.compile(r"^([가-힣A-Za-zⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ·ㆍ・]+)(\d+(?:\.\d+)?)$")
_ACADEMIC_SIMPLE_GROUP_PREFIXES = ("국어", "수학", "영어", "한국사", "사회", "과학", "체육", "예술", "한문")
_ROMAN_SUFFIX_TOKENS = {"Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "I", "II", "III", "IV", "V"}
_HANGUL_SUFFIX_TOKENS = {"평"}


def _normalize_row_tokens(tokens: List[str]) -> List[str]:
    """붙어있는 과목+단위수 토큰(예: Ⅰ3, 평1)을 분리."""
    normalized: List[str] = []
    for raw in tokens:
        token = str(raw or "").strip()
        if not token:
            continue
        m = _TRAILING_CREDIT_TOKEN_PATTERN.fullmatch(token)
        if m:
            head, credit = m.group(1), m.group(2)
            # 제2외국어처럼 토큰 내부 숫자는 유지
            if not re.search(r"제\d", head):
                normalized.append(head)
                normalized.append(credit)
                continue
        normalized.append(token)
    return normalized


def _is_subject_suffix_token(token: str) -> bool:
    compact = _compact(token)
    if not compact:
        return False
    if compact in _ROMAN_SUFFIX_TOKENS:
        return True
    if compact in _HANGUL_SUFFIX_TOKENS:
        return True
    return False


def _append_subject_suffix(row: Dict[str, str], suffix: str) -> None:
    subject = str(row.get("과목") or "").strip()
    token = re.sub(r"\s+", "", str(suffix or "").strip())
    if not subject or not token:
        return

    if token in _ROMAN_SUFFIX_TOKENS or token in _HANGUL_SUFFIX_TOKENS:
        row["과목"] = f"{subject}{token}"
    else:
        row["과목"] = f"{subject} {token}".strip()


def _build_candidate_with_group_anchor(pending_fragment: str, line: str) -> Optional[str]:
    """
    줄바꿈으로 분리된 행 복구:
    - 이전 줄에 과목명이 있고(pending_fragment),
    - 현재 줄이 '교과 단위수 점수...'로 시작하면
      '교과 + pending_fragment + 나머지'로 재조합한다.
    """
    fragment = str(pending_fragment or "").strip()
    if not fragment:
        return None

    tokens = _normalize_row_tokens([t for t in str(line or "").split() if t])
    if len(tokens) < 3:
        return None

    if not re.fullmatch(r"\d+(?:\.\d+)?", tokens[1]):
        return None

    third = tokens[2]
    if not (_SCORE_TOKEN_PATTERN.fullmatch(third) or third.upper() in {"P", "NP"}):
        return None

    # 현재 줄 첫 토큰이 과목 접미(예: I, Ⅱ, 평)라면 교과가 아니라 직전 과목의 일부다.
    # 예: pending='영어심화 영어 독해', line='I 3 98/65.2 ...'
    #  -> '영어심화 영어 독해 I 3 98/65.2 ...'
    if _is_subject_suffix_token(tokens[0]):
        return f"{fragment} {tokens[0]} {' '.join(tokens[1:])}".strip()

    group = tokens[0]
    tail = " ".join(tokens[1:])
    return f"{group} {fragment} {tail}".strip()


def _split_prefixed_group_token(token: str) -> Tuple[str, str]:
    for prefix in _ACADEMIC_SIMPLE_GROUP_PREFIXES:
        if token == prefix:
            return prefix, ""
        if token.startswith(prefix) and len(token) > len(prefix):
            rest = token[len(prefix):].strip()
            # 사회(역사/도덕...)처럼 괄호로 시작하는 경우는 교과 일부이므로 분리하지 않음
            if rest and rest[0] not in "(（/":
                return prefix, rest
    return "", ""


def _split_group_subject_from_head(head_parts: List[str], *, prefer_first_group: bool = False) -> Tuple[str, str]:
    parts = [str(p or "").strip() for p in head_parts if str(p or "").strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], parts[0]

    first = parts[0]
    prefix_group, glued_subject = _split_prefixed_group_token(first)
    if prefix_group:
        subject_parts = [glued_subject] if glued_subject else []
        subject_parts.extend(parts[1:])
        subject = " ".join(p for p in subject_parts if p).strip() or prefix_group
        return prefix_group, subject

    if first in _ACADEMIC_SIMPLE_GROUP_PREFIXES or first.startswith(("사회(", "사회（")):
        return first, " ".join(parts[1:]).strip() or first

    if prefer_first_group:
        return first, " ".join(parts[1:]).strip() or first

    return " ".join(parts[:-1]).strip(), parts[-1]


def _split_term_prefix(tokens: List[str], current_term: Optional[str]) -> Tuple[str, List[str]]:
    if not tokens:
        return current_term or "", []

    term = current_term or ""
    first = tokens[0]
    rest_tokens = list(tokens)

    m = re.match(r"^([12])(.+)$", first)
    if m:
        term = m.group(1)
        rest_tokens = [m.group(2)] + tokens[1:]
        return term, rest_tokens

    if first in {"1", "2"}:
        term = first
        rest_tokens = tokens[1:]
        return term, rest_tokens

    return term, rest_tokens


def _normalize_semester_term(value: str) -> Optional[str]:
    compact = _compact(value)
    if not compact:
        return None
    if "1학기" in compact:
        return "1"
    if "2학기" in compact:
        return "2"
    if re.fullmatch(r"[12]", compact):
        return compact
    if re.fullmatch(r"[123][12]", compact):
        return compact[-1]
    return None


def _normalize_group_and_subject(subject_group: str, subject: str) -> Tuple[str, str]:
    """
    줄바꿈/OCR로 교과와 과목 경계가 깨진 케이스를 복구.
    - 예: 교과='사회(역사/도덕', 과목='포함)통합사회'
    - 예: 교과='.../교', 과목='양기술·가정'
    """
    group = re.sub(r"\s+", " ", (subject_group or "").strip())
    subj = re.sub(r"\s+", " ", (subject or "").strip())

    # OCR/표 줄바꿈으로 교과/과목이 뒤집힌 케이스 복구:
    # 교과='포함)통합사회', 과목='사회(역사/도덕' -> 교과='사회(역사/도덕포함)', 과목='통합사회'
    swapped_include_match = re.match(r"^(포함[)）])\s*(.+)$", group)
    if (
        swapped_include_match
        and subj.startswith(("사회(", "사회（"))
        and "역사/도덕" in subj
        and not subj.endswith((")", "）"))
    ):
        include_token = swapped_include_match.group(1)
        swapped_subject = swapped_include_match.group(2).strip()
        if swapped_subject:
            group = f"{subj}{include_token}"
            subj = swapped_subject

    include_match = re.match(r"^(포함[)）])\s*(.+)$", subj)
    if include_match:
        include_token, rest = include_match.group(1), include_match.group(2).strip()
        group = f"{group} {include_token}".strip() if group else include_token
        subj = rest

    # 교과 시작부의 고립된 '포함)' 꼬리 정리.
    # 예: '포함) 과학' -> '과학'
    include_group_prefix = re.match(r"^(포함[)）])\s*(.+)$", group)
    if include_group_prefix:
        include_rest = include_group_prefix.group(2).strip()
        if include_rest:
            group = include_rest

    # OCR로 '교양'의 '양'이 과목 앞에 붙고, 교과 꼬리('/교')가 과목 칸으로 밀린 케이스 복구.
    # 예: 교과='양일본어I 기술·가정/제2', 과목='외국어/한문/교'
    #  -> 교과='기술·가정/제2외국어/한문/교양', 과목='일본어I'
    if (
        group.startswith("양")
        and (subj.endswith("/교") or subj == "외국어/한문/교")
    ):
        m = re.match(r"^양\s*([^\s].*?)\s+(.+)$", group)
        if m:
            moved_subject = m.group(1).strip()
            moved_group_prefix = m.group(2).strip()
            if moved_subject and moved_group_prefix:
                group = f"{moved_group_prefix}{subj}양"
                subj = moved_subject

    if subj.startswith("양") and (group.endswith("/교") or group.endswith("교")):
        group = f"{group}양"
        subj = subj[1:].strip()

    # 사회(역사/도덕포함) 교과의 열 뒤집힘/분절 보정.
    # 예:
    # - 교과='통합사회 포함)', 과목='사회(역사/도덕' -> 교과='사회(역사/도덕포함)', 과목='통합사회'
    # - 교과='사회 포함)', 과목='·문화 사회(역사/도덕' -> 교과='사회(역사/도덕포함)', 과목='사회·문화'
    social_token_match = re.search(r"사회[（(]역사/도덕", subj)
    if social_token_match:
        prefix = subj[: social_token_match.start()].strip()
        subject_from_group = re.sub(r"^포함[)）]\s*", "", group).strip()
        subject_from_group = re.sub(r"\s*포함[)）]\s*$", "", subject_from_group).strip()
        subject_from_group = re.sub(r"\s*사회[（(]역사/도덕.*$", "", subject_from_group).strip()

        if prefix:
            if prefix.startswith(("·", ".", "・", "ㆍ")) and subject_from_group:
                subject_from_group = f"{subject_from_group}{prefix}"
            elif not subject_from_group:
                subject_from_group = prefix
            elif subject_from_group == "사회":
                subject_from_group = f"{subject_from_group}{prefix}"

        if subject_from_group:
            group = "사회(역사/도덕포함)"
            subj = subject_from_group

    # 사회 계열에서 교과에만 '... 포함)'이 남고 과목이 자기 자신으로 파싱된 경우 보정.
    if (
        re.search(r"\s*포함[)）]\s*$", group)
        and "역사/도덕" not in group
    ):
        cleaned_group = re.sub(r"\s*포함[)）]\s*$", "", group).strip()
        if cleaned_group and (not subj or _compact(subj) == _compact(cleaned_group)):
            group = "사회(역사/도덕포함)"
            subj = cleaned_group

    group = group.replace("제2 외국어", "제2외국어")
    group = group.replace("/교 양", "/교양")
    group = group.replace("교 양", "교양")
    group = group.replace("・", "·")
    group = group.replace("ㆍ", "·")
    if ("사회" in group) and ("역사/도덕" in group) and ("포함" in group):
        group = "사회(역사/도덕포함)"
    group = re.sub(r"(역사/도덕)\s+(포함[)）])", r"\1\2", group)
    group = re.sub(r"(?<=[가-힣A-Za-z])[.](?=[가-힣A-Za-z])", "·", group)
    subj = subj.replace("제2 외국어", "제2외국어")
    subj = subj.replace("비 평", "비평")
    subj = subj.replace("・", "·")
    subj = subj.replace("ㆍ", "·")
    subj = re.sub(r"(?<=[가-힣A-Za-z])[.](?=[가-힣A-Za-z])", "·", subj)
    subj = re.sub(r"([가-힣A-Za-z])\s+([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ])", r"\1\2", subj)

    return group, subj


def _parse_general_plain_row(line: str, current_term: Optional[str]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    tokens = _normalize_row_tokens([t for t in line.split() if t])
    if len(tokens) < 4:
        return None, current_term

    score_idx = next((i for i, tok in enumerate(tokens) if _SCORE_TOKEN_PATTERN.fullmatch(tok)), -1)
    score = ""
    avg = ""
    std = ""
    ach = ""
    count = ""
    rank = ""
    leading: List[str] = []
    trailing: List[str] = []
    credit = ""
    pass_ach = ""
    pass_rank = ""

    if score_idx >= 2:
        credit = tokens[score_idx - 1]
        if not re.fullmatch(r"\d+(?:\.\d+)?", credit):
            return None, current_term
        leading = tokens[: score_idx - 1]
        trailing = tokens[score_idx + 1 :]
        if not leading or not trailing:
            return None, current_term
        score, avg, std = _parse_score_avg_std(tokens[score_idx])
        ach, count = _parse_ach_count(trailing[0])
        if not ach:
            return None, current_term
        for tok in trailing[1:]:
            if re.fullmatch(r"\d+(?:\.\d+)?", tok):
                rank = tok
                break
    else:
        # 3학년 일반선택의 "3 P P" 형태(성취평가 미산출/이수) 처리.
        # 관측 패턴상 첫 P/NP는 성취도, 둘째 P/NP는 석차등급으로 취급한다.
        pass_idx = next(
            (
                i
                for i in range(2, len(tokens) - 1)
                if re.fullmatch(r"\d+(?:\.\d+)?", tokens[i - 1])
                and tokens[i].upper() in {"P", "NP"}
                and tokens[i + 1].upper() in {"P", "NP"}
            ),
            -1,
        )
        if pass_idx < 2:
            return None, current_term
        credit = tokens[pass_idx - 1]
        leading = tokens[: pass_idx - 1]
        trailing = tokens[pass_idx + 2 :]
        if not leading:
            return None, current_term
        pass_ach = tokens[pass_idx].upper()
        pass_rank = tokens[pass_idx + 1].upper()
        ach = pass_ach
        rank = pass_rank
        # 일부 OCR에서 추가 토큰이 붙는 경우를 위해 보조값만 추출
        if trailing:
            ach2, count2 = _parse_ach_count(trailing[0])
            if not count and count2:
                count = count2

    term, head_parts = _split_term_prefix(leading, current_term)
    if not head_parts:
        return None, current_term
    subject_group, subject = _split_group_subject_from_head(head_parts, prefer_first_group=False)
    subject_group, subject = _normalize_group_and_subject(subject_group, subject)

    row = {
        "학기": term or "",
        "교과": subject_group,
        "과목": subject,
        "단위수": credit,
        "원점수": _sanitize_table_value(score),
        "과목평균": _sanitize_table_value(avg),
        "표준편차": _sanitize_table_value(std),
        "성취도": _sanitize_table_value(ach),
        "수강자수": _sanitize_table_value(count),
        "석차등급": _sanitize_table_value(rank),
    }
    return row, (term or current_term)


def _parse_career_plain_row(line: str, current_term: Optional[str]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    tokens = _normalize_row_tokens([t for t in line.split() if t])
    if len(tokens) < 7:
        return None, current_term

    score_idx = next((i for i, tok in enumerate(tokens) if _SCORE_TOKEN_PATTERN.fullmatch(tok)), -1)
    if score_idx < 2:
        return None, current_term

    credit = tokens[score_idx - 1]
    if not re.fullmatch(r"\d+(?:\.\d+)?", credit):
        return None, current_term

    leading = tokens[: score_idx - 1]
    trailing = tokens[score_idx + 1 :]
    if not leading or not trailing:
        return None, current_term

    ach, count = _parse_ach_count(trailing[0])
    if not ach:
        return None, current_term

    dist_text = " ".join(trailing).strip()
    dist = _parse_distribution_abc(dist_text)

    term, head_parts = _split_term_prefix(leading, current_term)
    if not head_parts:
        return None, current_term
    subject_group, subject = _split_group_subject_from_head(head_parts, prefer_first_group=True)
    subject_group, subject = _normalize_group_and_subject(subject_group, subject)

    score, avg, _std = _parse_score_avg_std(tokens[score_idx])
    row = {
        "학기": term or "",
        "교과": subject_group,
        "과목": subject,
        "단위수": credit,
        "원점수": _sanitize_table_value(score),
        "과목평균": _sanitize_table_value(avg),
        "성취도": _sanitize_table_value(ach),
        "수강자수": _sanitize_table_value(count),
        "성취도별분포_A": _sanitize_table_value(dist.get("A", "")),
        "성취도별분포_B": _sanitize_table_value(dist.get("B", "")),
        "성취도별분포_C": _sanitize_table_value(dist.get("C", "")),
    }
    return row, (term or current_term)


def _parse_pe_plain_row(line: str, current_term: Optional[str]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    tokens = _normalize_row_tokens([t for t in line.split() if t])
    if len(tokens) < 4:
        return None, current_term

    ach = tokens[-1]
    if not re.fullmatch(r"[A-Za-z가-힣][A-Za-z가-힣0-9+-]*", ach):
        return None, current_term

    credit = tokens[-2]
    if not re.fullmatch(r"\d+(?:\.\d+)?", credit):
        return None, current_term

    leading = tokens[:-2]
    if not leading:
        return None, current_term

    term, head_parts = _split_term_prefix(leading, current_term)
    if not head_parts:
        return None, current_term
    subject_group, subject = _split_group_subject_from_head(head_parts, prefer_first_group=True)
    subject_group, subject = _normalize_group_and_subject(subject_group, subject)

    row = {
        "학기": term or "",
        "교과": subject_group,
        "과목": subject,
        "단위수": credit,
        "성취도": _sanitize_table_value(ach),
    }
    return row, (term or current_term)


def _looks_like_academic_row_fragment(line: str) -> bool:
    compact = _compact(line)
    if not compact:
        return False
    if _is_noise_line(line) or _is_empty_marker(line):
        return False
    if any(
        token in compact
        for token in ("학기", "교과", "과목", "성취도", "수강자수", "석차등급", "비고", "분포비율", "이수학점합계", "세부능력", "특기사항")
    ):
        return False
    if _SCORE_TOKEN_PATTERN.search(line):
        return False
    if len(line.strip()) > 50:
        return False
    return bool(re.search(r"[가-힣A-Za-z]", line))


def _parse_academic_unified_markdown(section_text: str) -> Optional[Dict[str, Any]]:
    grade_blocks = _extract_grade_blocks(section_text)
    parsed_by_grade: Dict[str, List[Dict[str, str]]] = {"1": [], "2": [], "3": []}
    raw_by_grade: Dict[str, str] = {"1": "", "2": "", "3": ""}
    tables: Dict[str, Dict[str, Any]] = {
        "general_elective": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
        "career_elective": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
        "pe_arts": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
    }

    parsed_any = False
    saw_relevant_table = False
    for grade in ("1", "2", "3"):
        block = grade_blocks.get(grade, "")
        raw_by_grade[grade] = block
        if not block:
            continue

        for table in _extract_markdown_tables(block):
            headers = table["header"]
            headers_compact = [_compact(h) for h in headers]
            context_compact = _compact(" ".join(table.get("before", [])))

            idx_subject_note_subject = _find_header_exact(headers, "과목")
            idx_subject_note_note = _find_header_index(headers, ["세부능력", "특기사항"])
            if idx_subject_note_subject >= 0 and idx_subject_note_note >= 0:
                saw_relevant_table = True
                for row_cells in table["rows"]:
                    row_joined = " ".join(row_cells)
                    if _is_empty_marker(row_joined):
                        continue
                    subject = _sanitize_table_value(_row_cell(row_cells, idx_subject_note_subject))
                    note = _sanitize_table_value(_row_cell(row_cells, idx_subject_note_note))
                    if not note:
                        continue
                    if not subject:
                        if parsed_by_grade[grade]:
                            parsed_by_grade[grade][-1]["note"] = _merge_text(parsed_by_grade[grade][-1]["note"], note)
                        else:
                            subj = _infer_subject_from_note(note) or f"{grade}학년 미분류"
                            parsed_by_grade[grade].append({"subject": subj, "note": note})
                        parsed_any = True
                        continue

                    subject_compact = _compact(subject)
                    if subject_compact in {"학교명", "발행일자", "작성일자", "반", "번호", "이름", "-", "합계"}:
                        continue
                    if subject_compact in {"미기재"} and parsed_by_grade[grade]:
                        parsed_by_grade[grade][-1]["note"] = _merge_text(parsed_by_grade[grade][-1]["note"], note)
                        parsed_any = True
                        continue

                    parsed_by_grade[grade].append({"subject": subject, "note": note})
                    parsed_any = True
                continue

            if not (
                any("학기" in h for h in headers_compact)
                and any("교과" in h for h in headers_compact)
                and any("과목" in h for h in headers_compact)
            ):
                continue
            saw_relevant_table = True

            has_distribution = any("성취도별분포" in h for h in headers_compact) or (
                _find_header_exact(headers, "A") >= 0
                and _find_header_exact(headers, "B") >= 0
                and _find_header_exact(headers, "C") >= 0
            )
            has_rank = any("석차등급" in h for h in headers_compact)
            has_score = any("원점수" in h for h in headers_compact)
            has_std = any("표준편차" in h for h in headers_compact)

            if "진로선택과목" in context_compact or has_distribution:
                table_key = "career_elective"
            elif ("체육예술" in context_compact) or ("체육" in context_compact and "예술" in context_compact) or (not has_score and any("성취도" in h for h in headers_compact)):
                table_key = "pe_arts"
            elif "일반선택과목" in context_compact or has_rank or has_std or has_score:
                table_key = "general_elective"
            else:
                continue

            idx_term = _find_header_index(headers, ["학기"])
            idx_group = _find_header_index(headers, ["교과"])
            idx_subject = _find_header_exact(headers, "과목")
            idx_credit = _find_header_index(headers, ["단위수"])
            idx_score = _find_header_index(headers, ["원점수"])
            idx_avg = _find_header_index(headers, ["과목평균"])
            idx_std = _find_header_index(headers, ["표준편차"])
            idx_ach = _find_header_index(headers, ["성취도"], ["성취도별분포"])
            idx_count = _find_header_index(headers, ["수강자수"])
            idx_rank = _find_header_index(headers, ["석차등급"])
            idx_dist = _find_header_index(headers, ["성취도별분포"])
            idx_a = _find_header_exact(headers, "A")
            idx_b = _find_header_exact(headers, "B")
            idx_c = _find_header_exact(headers, "C")
            carry_term: Optional[str] = None

            for row_cells in table["rows"]:
                row_joined = " ".join(row_cells)
                compact_joined = _compact(row_joined)
                if _is_empty_marker(row_joined):
                    continue
                if ("이수단위합계" in compact_joined) or ("이수학점합계" in compact_joined):
                    total = _parse_int_cell(row_joined, dot_as_zero=True)
                    if total is not None:
                        tables[table_key][grade]["이수단위합계"] = total
                        parsed_any = True
                    continue

                raw_term = _sanitize_table_value(_row_cell(row_cells, idx_term))
                normalized_term = _normalize_semester_term(raw_term)
                if normalized_term:
                    carry_term = normalized_term
                    term = normalized_term
                elif carry_term:
                    term = carry_term
                else:
                    term = raw_term
                subject_group = _sanitize_table_value(_row_cell(row_cells, idx_group))
                subject = _sanitize_table_value(_row_cell(row_cells, idx_subject))
                credit = _sanitize_table_value(_row_cell(row_cells, idx_credit))
                if not any([term, subject_group, subject, credit]):
                    continue

                score = _sanitize_table_value(_row_cell(row_cells, idx_score))
                avg = _sanitize_table_value(_row_cell(row_cells, idx_avg))
                std = _sanitize_table_value(_row_cell(row_cells, idx_std))
                if idx_score >= 0 and (idx_avg < 0 or idx_std < 0):
                    score2, avg2, std2 = _parse_score_avg_std(_row_cell(row_cells, idx_score))
                    score = score or _sanitize_table_value(score2)
                    avg = avg or _sanitize_table_value(avg2)
                    std = std or _sanitize_table_value(std2)

                ach = _sanitize_table_value(_row_cell(row_cells, idx_ach))
                count = _sanitize_table_value(_row_cell(row_cells, idx_count))
                if idx_ach >= 0 and idx_count < 0:
                    ach2, count2 = _parse_ach_count(_row_cell(row_cells, idx_ach))
                    ach = ach or _sanitize_table_value(ach2)
                    count = count or _sanitize_table_value(count2)

                if table_key == "general_elective":
                    row_obj = {
                        "학기": term,
                        "교과": subject_group,
                        "과목": subject,
                        "단위수": credit,
                        "원점수": score,
                        "과목평균": avg,
                        "표준편차": std,
                        "성취도": ach,
                        "수강자수": count,
                        "석차등급": _sanitize_table_value(_row_cell(row_cells, idx_rank)),
                    }
                elif table_key == "career_elective":
                    dist_a = _sanitize_table_value(_row_cell(row_cells, idx_a))
                    dist_b = _sanitize_table_value(_row_cell(row_cells, idx_b))
                    dist_c = _sanitize_table_value(_row_cell(row_cells, idx_c))
                    if not any([dist_a, dist_b, dist_c]) and idx_dist >= 0:
                        parsed_dist = _parse_distribution_abc(_row_cell(row_cells, idx_dist))
                        dist_a = parsed_dist["A"]
                        dist_b = parsed_dist["B"]
                        dist_c = parsed_dist["C"]
                    row_obj = {
                        "학기": term,
                        "교과": subject_group,
                        "과목": subject,
                        "단위수": credit,
                        "원점수": score,
                        "과목평균": avg,
                        "성취도": ach,
                        "수강자수": count,
                        "성취도별분포_A": dist_a,
                        "성취도별분포_B": dist_b,
                        "성취도별분포_C": dist_c,
                    }
                else:
                    row_obj = {
                        "학기": term,
                        "교과": subject_group,
                        "과목": subject,
                        "단위수": credit,
                        "성취도": ach,
                    }

                if any(str(v or "").strip() for v in row_obj.values()):
                    tables[table_key][grade]["rows"].append(row_obj)
                    parsed_any = True

    if not parsed_any and not saw_relevant_table:
        return None

    return {
        "by_grade": parsed_by_grade,
        "raw_by_grade": raw_by_grade,
        "general_elective": tables["general_elective"],
        "career_elective": tables["career_elective"],
        "pe_arts": tables["pe_arts"],
    }


def _parse_academic_unified(section_text: str) -> Dict[str, Any]:
    """교과학습 구간 1패스: 학년별로 한 번만 순회하며 세특(by_grade) + 일반/진로/체육예술 테이블 + 이수단위합계 동시 추출."""
    markdown_parsed = _parse_academic_unified_markdown(section_text)
    if markdown_parsed is not None:
        return markdown_parsed

    grade_blocks = _extract_grade_blocks(section_text)
    parsed_by_grade: Dict[str, List[Dict[str, str]]] = {"1": [], "2": [], "3": []}
    raw_by_grade: Dict[str, str] = {"1": "", "2": "", "3": ""}
    tables: Dict[str, Dict[str, Any]] = {
        "general_elective": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
        "career_elective": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
        "pe_arts": {"1": {"rows": [], "이수단위합계": None}, "2": {"rows": [], "이수단위합계": None}, "3": {"rows": [], "이수단위합계": None}},
    }

    for grade in ("1", "2", "3"):
        block = grade_blocks.get(grade, "")
        raw_by_grade[grade] = block
        if not block:
            continue
        current_table: Optional[str] = None
        pending_credits_table: Optional[str] = None  # 이수단위합계 다음 줄에 숫자만 있는 경우
        table_term: Dict[str, Optional[str]] = {
            "general_elective": None,
            "career_elective": None,
            "pe_arts": None,
        }
        known_subjects: Dict[str, str] = {}
        pending_row_fragment = ""
        in_note_table = False
        current_subject: Optional[str] = None
        note_lines: List[str] = []

        def flush_note():
            nonlocal current_subject, note_lines
            if current_subject and note_lines:
                note = "\n".join(note_lines).strip()
                if note and not _is_empty_marker(note):
                    subj = current_subject.strip()
                    if subj.endswith("미분류"):
                        inferred = _infer_subject_from_note(note)
                        if inferred:
                            subj = inferred
                    parsed_by_grade[grade].append({"subject": subj, "note": note})
            current_subject = None
            note_lines = []

        def add_known_subject(subject: str) -> None:
            subj = (subject or "").strip()
            if not subj:
                return
            key = _normalize_subject_match_key(subj)
            if key and key not in known_subjects:
                known_subjects[key] = subj

        for raw_line in block.splitlines():
            line = raw_line.strip()
            compact = _compact(line)
            if not compact:
                continue
            # 이수단위합계 다음 줄에 숫자만 있는 경우
            if pending_credits_table and re.fullmatch(r"\d+(?:\.\d+)?", compact):
                try:
                    tables[pending_credits_table][grade]["이수단위합계"] = int(float(compact))
                except (ValueError, TypeError):
                    pass
                pending_credits_table = None
                continue
            if "일반선택과목" in compact:
                flush_note()
                in_note_table = False
                current_table = "general_elective"
                if table_term[current_table] is None:
                    table_term[current_table] = "1"
                pending_row_fragment = ""
                continue
            if "진로선택과목" in compact:
                flush_note()
                in_note_table = False
                current_table = "career_elective"
                if table_term[current_table] is None:
                    table_term[current_table] = "1"
                pending_row_fragment = ""
                continue
            if ("체육" in compact and "예술" in compact) or "체육예술과목" in compact:
                flush_note()
                in_note_table = False
                current_table = "pe_arts"
                if table_term[current_table] is None:
                    table_term[current_table] = "1"
                pending_row_fragment = ""
                continue
            if ("학기" in compact and "교과" in compact and "과목" in compact) and ("학점수" in compact or "단위수" in compact):
                flush_note()
                in_note_table = False
                if current_table is None:
                    current_table = "general_elective"
                if table_term[current_table] is None:
                    table_term[current_table] = "1"
                pending_row_fragment = ""
                continue
            if "세부능력및특기사항" in compact or ("세부능력" in compact and "특기사항" in compact):
                # 페이지 넘김으로 동일한 세특 헤더가 반복되는 경우는 노트를 끊지 않음
                if in_note_table:
                    continue
                flush_note()
                current_table = None
                pending_row_fragment = ""
                in_note_table = True
                continue
            if ("이수단위합계" in compact) or ("이수학점합계" in compact):
                nums = re.findall(r"\d+(?:\.\d+)?", line)
                if current_table and nums:
                    try:
                        tables[current_table][grade]["이수단위합계"] = int(float(nums[0]))
                    except (ValueError, TypeError):
                        pass
                elif current_table:
                    pending_credits_table = current_table
                current_table = None
                pending_row_fragment = ""
                continue
            if _is_empty_marker(line) or _is_noise_line(line):
                continue
            if in_note_table:
                subject_from_line, rest = _split_subject_prefix_line(line, known_subjects)
                if subject_from_line:
                    flush_note()
                    current_subject = subject_from_line
                    if rest and not _is_noise_line(rest) and not _is_empty_marker(rest):
                        note_lines.append(rest)
                    continue

                normalized_label = _normalize_subject_match_key(line)
                if _looks_like_subject_label(line) and normalized_label in known_subjects:
                    flush_note()
                    current_subject = known_subjects[normalized_label]
                else:
                    if current_subject is None:
                        current_subject = f"{grade}학년 미분류"
                    note_lines.append(line)
                continue
            if current_table:
                if re.fullmatch(r"[12]", compact):
                    table_term[current_table] = compact
                    pending_row_fragment = ""
                    continue

                # 줄바꿈으로 분리된 교과 라벨 꼬리(예: '포함)', '양')를 직전 행 교과에 합친다.
                if (
                    not pending_row_fragment
                    and re.fullmatch(r"[가-힣A-Za-z·ㆍ/()]+", compact)
                    and len(compact) <= 8
                    and tables[current_table][grade]["rows"]
                ):
                    last_row = tables[current_table][grade]["rows"][-1]
                    last_group = str(last_row.get("교과") or "").strip()
                    if last_group and (compact.endswith(")") or compact in {"양", "포함"}):
                        merged_group = re.sub(r"\s+", " ", f"{last_group} {line}").strip()
                        merged_group = merged_group.replace("제2 외국어", "제2외국어")
                        merged_group = merged_group.replace("/교 양", "/교양")
                        merged_group = merged_group.replace("교 양", "교양")
                        last_row["교과"] = merged_group
                        continue

                # 줄바꿈으로 떨어진 과목 접미 토큰(예: 'Ⅰ', '평')은 직전 과목에 붙여 복구한다.
                if (
                    not pending_row_fragment
                    and _is_subject_suffix_token(line)
                    and tables[current_table][grade]["rows"]
                ):
                    last_row = tables[current_table][grade]["rows"][-1]
                    _append_subject_suffix(last_row, line)
                    continue

                candidate = line if not pending_row_fragment else f"{pending_row_fragment} {line}"
                if pending_row_fragment:
                    anchored_candidate = _build_candidate_with_group_anchor(pending_row_fragment, line)
                    if anchored_candidate:
                        candidate = anchored_candidate
                parsed_row: Optional[Dict[str, str]] = None
                next_term: Optional[str] = table_term.get(current_table)

                if current_table == "general_elective":
                    parsed_row, next_term = _parse_general_plain_row(candidate, table_term.get(current_table))
                elif current_table == "career_elective":
                    parsed_row, next_term = _parse_career_plain_row(candidate, table_term.get(current_table))
                else:
                    parsed_row, next_term = _parse_pe_plain_row(candidate, table_term.get(current_table))

                if parsed_row is not None and any(str(v or "").strip() for v in parsed_row.values()):
                    if not str(parsed_row.get("학기") or "").strip() and table_term.get(current_table):
                        parsed_row["학기"] = str(table_term.get(current_table) or "")

                    group = str(parsed_row.get("교과") or "").strip()
                    if group:
                        group = re.sub(r"\s+", " ", group).strip()
                        group = re.sub(r"\b([12])\b(?=\s*(외국어|국어|수학|영어|한국사|사회|과학|체육|예술|기술|한문))", "", group).strip()
                        group = group.replace("제2 외국어", "제2외국어")
                        group = group.replace("/교 양", "/교양")
                        group = group.replace("교 양", "교양")
                        subject = str(parsed_row.get("과목") or "").strip()
                        group, subject = _normalize_group_and_subject(group, subject)
                        parsed_row["과목"] = subject
                        if subject == "법" and "정치와" in group:
                            parsed_row["과목"] = "정치와 법"
                            group = re.sub(r"\s*정치와\s*", " ", group).strip()
                        parsed_row["교과"] = group

                    tables[current_table][grade]["rows"].append(parsed_row)
                    add_known_subject(str(parsed_row.get("과목") or ""))
                    table_term[current_table] = next_term
                    pending_row_fragment = ""
                    continue

                if _looks_like_academic_row_fragment(line):
                    pending_row_fragment = candidate.strip()
                else:
                    pending_row_fragment = ""
        flush_note()

        # 템플릿 후처리: 중복 세특 제거 + 법령 고지문 과목명 정리
        deduped: List[Dict[str, str]] = []
        seen: set[str] = set()
        for row in parsed_by_grade[grade]:
            subject = str(row.get("subject") or "").strip()
            note = str(row.get("note") or "").strip()
            if not note:
                continue
            if subject in {"해당내용은", "미분류", f"{grade}학년 미분류"} and "공공기관의 정보공개에 관한 법률" in note:
                subject = "-"
            key = f"{_compact(subject)}::{_compact(note)}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append({"subject": subject or "-", "note": note})
        parsed_by_grade[grade] = deduped

    return {
        "by_grade": parsed_by_grade,
        "raw_by_grade": raw_by_grade,
        "general_elective": tables["general_elective"],
        "career_elective": tables["career_elective"],
        "pe_arts": tables["pe_arts"],
    }


def _parse_behavior_opinion(section_text: str) -> Dict[str, str]:
    # 1) OCR markdown 표 파싱 우선
    parsed: Dict[str, str] = {"1": "", "2": "", "3": ""}
    saw_table = False
    carry_grade: Optional[str] = None
    table_ranges: List[Tuple[int, int]] = []
    tables = _extract_markdown_tables(section_text)
    for table in tables:
        headers = [_compact(h) for h in table["header"]]
        if not (any("학년" in h for h in headers) and any("행동특성" in h and "종합의견" in h for h in headers)):
            continue
        saw_table = True
        table_ranges.append((int(table.get("start", 0)), int(table.get("end", 0))))

        idx_grade = _find_header_index(table["header"], ["학년"])
        idx_note = _find_header_index(table["header"], ["행동특성", "종합의견"])
        if min(idx_grade, idx_note) < 0:
            continue

        current_grade: Optional[str] = carry_grade
        for row in table["rows"]:
            grade_cell = _row_cell(row, idx_grade)
            note_cell = _row_cell(row, idx_note)
            grade_match = re.search(r"([123])", _compact(grade_cell))
            if grade_match:
                current_grade = grade_match.group(1)
                carry_grade = current_grade
            if _is_empty_marker(note_cell):
                continue
            if current_grade and note_cell:
                parsed[current_grade] = _merge_text(parsed[current_grade], note_cell)

    if saw_table:
        # 표 바깥으로 이어지는 문장을 마지막 학년에 이어 붙인다.
        # 전체 문서(full text) 파싱에서도 오염되지 않도록 표 주변 영역만 제한적으로 사용.
        lines = section_text.splitlines()
        covered_indices: set[int] = set()
        nearby_indices: set[int] = set()
        for start, end in table_ranges:
            for i in range(start, end + 1):
                covered_indices.add(i)
            near_start = max(0, start - 12)
            near_end = min(len(lines) - 1, end + 30)
            for i in range(near_start, near_end + 1):
                nearby_indices.add(i)

        current_grade: Optional[str] = carry_grade
        if current_grade is None:
            for g in ("3", "2", "1"):
                if parsed[g].strip():
                    current_grade = g
                    break

        for idx, raw_line in enumerate(lines):
            if idx in covered_indices or idx not in nearby_indices:
                continue
            line = raw_line.strip()
            if not line:
                continue
            compact = _compact(line)
            grade_match = re.search(r"([123])학년", compact)
            if grade_match:
                current_grade = grade_match.group(1)
                continue
            if _is_noise_line(line) or _is_empty_marker(line):
                continue
            if ("독서활동" in compact and "상황" in compact) or ("표입니다" in line) or ("기록한표" in compact):
                continue
            if line.startswith("#") or line.startswith("|"):
                continue
            if current_grade and len(compact) >= 2:
                parsed[current_grade] = _merge_text(parsed[current_grade], line)
        return parsed

    # 2) 레거시 텍스트 파서 폴백
    current_grade: Optional[str] = "1"
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        compact = _compact(line)
        if _is_noise_line(line) or _is_empty_marker(line):
            continue

        # 법령 고지문은 3학년 블록으로 귀속
        if "공공기관의정보공개에관한법률" in compact:
            current_grade = "3"
            parsed["3"] = _merge_text(parsed["3"], line)
            continue

        # 단독 숫자 학년 표시는 구분자이므로 텍스트로 추가하지 않음
        if compact in {"1", "2", "3"}:
            if compact == "3" and current_grade in {None, "1", "2"}:
                current_grade = "3"
            continue

        explicit_grade = re.match(r"^([123])학년(.*)$", compact)
        if explicit_grade:
            current_grade = explicit_grade.group(1)
            remainder = re.sub(r"^[123]학년", "", line).strip()
            if remainder:
                parsed[current_grade] = _merge_text(parsed[current_grade], remainder)
            continue

        # "1항상 ...", "22학기 ...", "3..." 형태 대응
        leading_grade = line[0] if line and line[0] in {"1", "2", "3"} else None
        if leading_grade and not re.match(r"^20\d{2}", line):
            allow_transition = (
                current_grade is None
                or (current_grade == "1" and leading_grade == "2")
                or (current_grade == "2" and leading_grade == "3")
            )
            if allow_transition:
                current_grade = leading_grade
                if re.match(r"^[123]\s*학기", line):
                    remainder = line
                else:
                    remainder = line[1:].strip()
                if remainder and not _is_noise_line(remainder):
                    parsed[current_grade] = _merge_text(parsed[current_grade], remainder)
                continue

        if current_grade:
            parsed[current_grade] = _merge_text(parsed[current_grade], line)

    if not any(v.strip() for v in parsed.values()):
        grade_blocks = _extract_grade_blocks(section_text)
        fallback_lines: List[str] = []
        for grade in ("1", "2", "3"):
            block = grade_blocks.get(grade, "")
            if not block:
                continue
            for raw_line in block.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if _is_noise_line(line) or _is_empty_marker(line):
                    continue
                if re.search(r"([123])학년", _compact(line)):
                    continue
                parsed[grade] = _merge_text(parsed[grade], line)

        if not any(v.strip() for v in parsed.values()):
            for raw_line in section_text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                if _is_noise_line(line) or _is_empty_marker(line):
                    continue
                fallback_lines.append(line)
            if fallback_lines:
                parsed["3"] = "\n".join(fallback_lines).strip()

    return parsed


def _academic_parse_score(parsed: Dict[str, Any]) -> int:
    if not isinstance(parsed, dict):
        return -1
    by_grade = parsed.get("by_grade") or {}
    ge = parsed.get("general_elective") or {}
    ce = parsed.get("career_elective") or {}
    pe = parsed.get("pe_arts") or {}

    row_count = 0
    note_count = 0
    note_chars = 0
    grade_coverage = 0
    total_credits_count = 0

    for g in ("1", "2", "3"):
        grade_has_data = False

        grade_notes = list(by_grade.get(g) or [])
        for pair in grade_notes:
            note = str((pair or {}).get("note") or "").strip()
            if note:
                note_count += 1
                note_chars += len(note)
                grade_has_data = True

        for table in (ge, ce, pe):
            info = dict(table.get(g) or {})
            rows = list(info.get("rows") or [])
            if rows:
                row_count += len(rows)
                grade_has_data = True
            if info.get("이수단위합계") is not None:
                total_credits_count += 1
                grade_has_data = True

        if grade_has_data:
            grade_coverage += 1

    return (
        (row_count * 10000)
        + (grade_coverage * 1000)
        + (note_count * 200)
        + (total_credits_count * 100)
        + min(note_chars, 20000)
    )


def _behavior_parse_score(parsed: Dict[str, str]) -> int:
    if not isinstance(parsed, dict):
        return -1
    non_empty = 0
    total_chars = 0
    for g in ("1", "2", "3"):
        text = str(parsed.get(g) or "").strip()
        if text:
            non_empty += 1
            total_chars += len(text)
    return non_empty * 1000 + total_chars


def _behavior_grade_coverage(parsed: Dict[str, str]) -> int:
    if not isinstance(parsed, dict):
        return 0
    return sum(1 for g in ("1", "2", "3") if str(parsed.get(g) or "").strip())


def _sanitize_behavior_parsed(parsed: Dict[str, str]) -> Dict[str, str]:
    cleaned: Dict[str, str] = {"1": "", "2": "", "3": ""}
    if not isinstance(parsed, dict):
        return cleaned

    banned_tokens = (
        "본증명의위변조여부",
        "교육민원음성서비스",
        "발급문서진위확인",
        "나이스대국민서비스",
        "neis.go.kr",
        "발급일로부터90일이내",
        "열람용",
        "증명서",
        "발급번호",
        "학교생활기록부사본임을증명합니다",
        "위사람의학교생활기록부사본임을증명합니다",
        "고등학교장",
        "학교생활기록부",
        "학교생활세부사항기록부",
        "인적사항",
        "주민등록번호",
        "담당부서",
        "담당자",
        "전화번호",
        "사항성명",
        "성명",
    )

    for g in ("1", "2", "3"):
        text = str(parsed.get(g) or "")
        kept_lines: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # OCR 결합으로 남는 학년 접두 숫자 제거: "1항상 ...", "3해당내용은 ..."
            if re.match(r"^[123](?!학기)[가-힣A-Za-z]", line):
                line = line[1:].strip()
                if not line:
                    continue
            compact = _compact(line)
            if _is_noise_line(line):
                continue
            if compact in {"1", "2", "3"}:
                continue
            if compact in {"학년행동특성및종합의견", "행동특성및종합의견"}:
                continue
            if "◆" in line:
                continue
            if any(tok in compact for tok in banned_tokens):
                continue
            if compact in {"인적", "사항"}:
                continue
            if "행동특성및종합의견" in compact and re.match(r"^\d+\s*[.)]?", line):
                continue
            if re.match(r"^\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일$", line):
                continue
            if re.search(r"\d{4}년\d{1,2}월\d{1,2}일\d+/\d+", compact):
                continue
            kept_lines.append(line)
        cleaned[g] = "\n".join(kept_lines).strip()
    return cleaned


def _parse_attendance_plain_row(line: str) -> Optional[Dict[str, Any]]:
    m = re.match(r"^\s*([123])\s+(.*)$", line)
    if not m:
        return None

    grade = m.group(1)
    tail = m.group(2).strip()
    if not tail:
        return None

    first_text_idx = -1
    for idx, ch in enumerate(tail):
        if re.match(r"[가-힣A-Za-z]", ch):
            first_text_idx = idx
            break

    note_text = ""
    numeric_part = tail
    if first_text_idx >= 0:
        numeric_part = tail[:first_text_idx].strip()
        note_text = tail[first_text_idx:].strip()

    numeric_part = re.sub(r"\.(?=[가-힣A-Za-z])", ". ", numeric_part)
    tokens = re.findall(r"\d+|\.", numeric_part)
    if len(tokens) < 13:
        return None

    values: List[int] = []
    for tok in tokens[:13]:
        values.append(0 if tok == "." else int(tok))

    row: Dict[str, Any] = {
        "grade": grade,
        "수업일수": values[0],
        "결석_질병": values[1],
        "결석_미인정": values[2],
        "결석_기타": values[3],
        "지각_질병": values[4],
        "지각_미인정": values[5],
        "지각_기타": values[6],
        "조퇴_질병": values[7],
        "조퇴_미인정": values[8],
        "조퇴_기타": values[9],
        "결과_질병": values[10],
        "결과_미인정": values[11],
        "결과_기타": values[12],
        "특기사항": "",
    }
    if note_text and not _is_empty_marker(note_text):
        row["특기사항"] = note_text
    return row


def _parse_attendance(section_text: str) -> Dict[str, Any]:
    """출결상황: 학년별 수업일수, 결석(질병/미인정/기타), 지각, 조퇴, 결과, 특기사항."""
    # 1) OCR markdown 표 파싱 우선
    rows: List[Dict[str, Any]] = []
    has_no_item = _is_empty_marker(section_text)
    saw_table = False

    for table in _extract_markdown_tables(section_text):
        headers = table["header"]
        headers_compact = [_compact(h) for h in headers]
        if not (
            any("학년" in h for h in headers_compact)
            and any("수업일수" in h for h in headers_compact)
            and any(("결석" in h) or ("지각" in h) for h in headers_compact)
        ):
            continue
        saw_table = True

        idx_grade = _find_header_index(headers, ["학년"])
        idx_class_days = _find_header_index(headers, ["수업일수"])
        idx_abs_ill = _find_header_index(headers, ["결석", "질병"])
        idx_abs_un = _find_header_index(headers, ["결석", "미인정"])
        idx_abs_etc = _find_header_index(headers, ["결석", "기타"])
        idx_late_ill = _find_header_index(headers, ["지각", "질병"])
        idx_late_un = _find_header_index(headers, ["지각", "미인정"])
        idx_late_etc = _find_header_index(headers, ["지각", "기타"])
        idx_early_ill = _find_header_index(headers, ["조퇴", "질병"])
        idx_early_un = _find_header_index(headers, ["조퇴", "미인정"])
        idx_early_etc = _find_header_index(headers, ["조퇴", "기타"])
        idx_res_ill = _find_header_index(headers, ["결과", "질병"])
        idx_res_un = _find_header_index(headers, ["결과", "미인정"])
        idx_res_etc = _find_header_index(headers, ["결과", "기타"])
        idx_note = _find_header_index(headers, ["특기사항"])

        for row_cells in table["rows"]:
            if _is_empty_marker(" ".join(row_cells)):
                has_no_item = True
                continue

            grade_text = _row_cell(row_cells, idx_grade)
            grade_match = re.search(r"([123])", _compact(grade_text))
            if not grade_match:
                continue
            grade = grade_match.group(1)

            row: Dict[str, Any] = {"grade": grade}
            row["수업일수"] = _parse_int_cell(_row_cell(row_cells, idx_class_days), dot_as_zero=True)
            row["결석_질병"] = _parse_int_cell(_row_cell(row_cells, idx_abs_ill), dot_as_zero=True)
            row["결석_미인정"] = _parse_int_cell(_row_cell(row_cells, idx_abs_un), dot_as_zero=True)
            row["결석_기타"] = _parse_int_cell(_row_cell(row_cells, idx_abs_etc), dot_as_zero=True)
            row["지각_질병"] = _parse_int_cell(_row_cell(row_cells, idx_late_ill), dot_as_zero=True)
            row["지각_미인정"] = _parse_int_cell(_row_cell(row_cells, idx_late_un), dot_as_zero=True)
            row["지각_기타"] = _parse_int_cell(_row_cell(row_cells, idx_late_etc), dot_as_zero=True)
            row["조퇴_질병"] = _parse_int_cell(_row_cell(row_cells, idx_early_ill), dot_as_zero=True)
            row["조퇴_미인정"] = _parse_int_cell(_row_cell(row_cells, idx_early_un), dot_as_zero=True)
            row["조퇴_기타"] = _parse_int_cell(_row_cell(row_cells, idx_early_etc), dot_as_zero=True)
            row["결과_질병"] = _parse_int_cell(_row_cell(row_cells, idx_res_ill), dot_as_zero=True)
            row["결과_미인정"] = _parse_int_cell(_row_cell(row_cells, idx_res_un), dot_as_zero=True)
            row["결과_기타"] = _parse_int_cell(_row_cell(row_cells, idx_res_etc), dot_as_zero=True)
            note = _row_cell(row_cells, idx_note)
            if note and not _is_empty_marker(note):
                row["특기사항"] = note
            else:
                row["특기사항"] = ""
            rows.append(row)

    if rows:
        has_no_item = False
        return {
            "raw_text": section_text.strip(),
            "has_no_item": False,
            "rows": rows,
        }
    if saw_table:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": True,
            "rows": [],
        }

    # 2) 레거시 텍스트 파서 폴백
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        compact = _compact(line)
        if not line or _is_noise_line(line):
            continue
        if _is_empty_marker(line):
            continue

        plain_row = _parse_attendance_plain_row(line)
        if plain_row is not None:
            rows.append(plain_row)
            continue

        grade_match = re.search(r"([123])학년", compact)
        numbers = [int(n) for n in re.findall(r"\d+", line)]
        grade = grade_match.group(1) if grade_match else None
        if not grade:
            continue
        # 구조화: 수업일수(1) + 결석3 + 지각3 + 조퇴3 + 결과3 = 13개
        row: Dict[str, Any] = {"grade": grade, "numbers": numbers}
        if len(numbers) >= 13:
            row["수업일수"] = numbers[0]
            row["결석_질병"] = numbers[1]
            row["결석_미인정"] = numbers[2]
            row["결석_기타"] = numbers[3]
            row["지각_질병"] = numbers[4]
            row["지각_미인정"] = numbers[5]
            row["지각_기타"] = numbers[6]
            row["조퇴_질병"] = numbers[7]
            row["조퇴_미인정"] = numbers[8]
            row["조퇴_기타"] = numbers[9]
            row["결과_질병"] = numbers[10]
            row["결과_미인정"] = numbers[11]
            row["결과_기타"] = numbers[12]
        # 특기사항: 숫자 뒤 남는 텍스트
        text_after = re.sub(r"[123]학년", "", line)
        for _ in range(len(numbers)):
            text_after = re.sub(r"^\s*\d+", "", text_after, count=1).strip()
        if text_after and not re.fullmatch(r"[\d\s,]+", text_after):
            row["특기사항"] = text_after.strip()
        rows.append(row)
    if rows:
        has_no_item = False
    return {
        "raw_text": section_text.strip(),
        "has_no_item": has_no_item or ("해당사항없음" in _compact(section_text)),
        "rows": rows,
    }


def _parse_certificates(section_text: str) -> Dict[str, Any]:
    """자격증·인증: 구분, 명칭 또는 종류, 번호 또는 내용, 취득년월일, 발급기관."""
    # 1) OCR markdown 표 파싱 우선
    has_no_item = _is_empty_marker(section_text)
    saw_table = False
    rows: List[Dict[str, str]] = []
    items: List[str] = []
    col_names = ["구분", "명칭또는종류", "번호또는내용", "취득년월일", "발급기관"]

    for table in _extract_markdown_tables(section_text):
        headers = [_compact(h) for h in table["header"]]
        if not (
            any("구분" in h for h in headers)
            and any("명칭" in h and "종류" in h for h in headers)
            and any("취득년월일" in h for h in headers)
        ):
            continue
        saw_table = True

        idx_kind = _find_header_index(table["header"], ["구분"])
        idx_name = _find_header_index(table["header"], ["명칭", "종류"])
        idx_no = _find_header_index(table["header"], ["번호", "내용"])
        idx_date = _find_header_index(table["header"], ["취득년월일"])
        idx_org = _find_header_index(table["header"], ["발급기관"])

        for row_cells in table["rows"]:
            joined = " ".join(row_cells)
            if _is_empty_marker(joined):
                has_no_item = True
                continue
            mapped = {
                "구분": _row_cell(row_cells, idx_kind),
                "명칭또는종류": _row_cell(row_cells, idx_name),
                "번호또는내용": _row_cell(row_cells, idx_no),
                "취득년월일": _row_cell(row_cells, idx_date),
                "발급기관": _row_cell(row_cells, idx_org),
            }
            if all(_is_blank_value(v) for v in mapped.values()):
                continue
            rows.append(mapped)
            items.append(" | ".join(v for v in mapped.values() if v))

    if rows:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": False,
            "items": items,
            "rows": rows,
        }
    if has_no_item:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": True,
            "items": [],
            "rows": [],
        }
    if saw_table:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": True,
            "items": [],
            "rows": [],
        }

    # 2) 레거시 텍스트 파서 폴백
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    meaningful = [ln for ln in lines if not _is_noise_line(ln) and not _is_empty_marker(ln)]
    rows = []
    for ln in meaningful:
        # 탭 또는 연속 공백 2개 이상으로 분리 시 5열 구조로 저장
        parts = re.split(r"\t|\s{2,}", ln, maxsplit=4)
        if len(parts) >= 5:
            rows.append(dict(zip(col_names, [p.strip() for p in parts[:5]])))
        elif len(parts) == 1 and parts[0]:
            rows.append({col_names[0]: parts[0], col_names[1]: "", col_names[2]: "", col_names[3]: "", col_names[4]: ""})
    if not rows and meaningful:
        for ln in meaningful:
            rows.append({col_names[0]: ln, col_names[1]: "", col_names[2]: "", col_names[3]: "", col_names[4]: ""})
    return {
        "raw_text": section_text.strip(),
        "has_no_item": "해당사항없음" in _compact(section_text),
        "items": meaningful,
        "rows": rows,
    }


def _parse_volunteer_activity(section_text: str) -> Dict[str, Any]:
    # 1) OCR markdown 표 파싱 우선
    has_no_item = _is_empty_marker(section_text)
    saw_table = False
    rows: List[Dict[str, Any]] = []
    for table in _extract_markdown_tables(section_text):
        headers = [_compact(h) for h in table["header"]]
        if not (
            any("학년" in h for h in headers)
            and any("일자" in h or "기간" in h for h in headers)
            and any("활동내용" in h for h in headers)
        ):
            continue
        saw_table = True

        idx_grade = _find_header_index(table["header"], ["학년"])
        idx_date = _find_header_index(table["header"], ["일자"])
        if idx_date < 0:
            idx_date = _find_header_index(table["header"], ["기간"])
        idx_place = _find_header_index(table["header"], ["장소"])
        idx_content = _find_header_index(table["header"], ["활동내용"])
        idx_hours = _find_header_index(table["header"], ["시간"])

        for row_cells in table["rows"]:
            joined = " ".join(row_cells)
            if _is_empty_marker(joined):
                has_no_item = True
                continue

            grade_cell = _row_cell(row_cells, idx_grade)
            grade_match = re.search(r"([123])", _compact(grade_cell))
            if not grade_match:
                continue

            hour_value: Optional[float] = None
            hour_cell = _row_cell(row_cells, idx_hours)
            m = re.search(r"(\d+(?:\.\d+)?)", hour_cell)
            if m:
                try:
                    hour_value = float(m.group(1))
                except Exception:
                    hour_value = None

            row = {
                "grade": grade_match.group(1),
                "일자또는기간": _row_cell(row_cells, idx_date),
                "장소또는주관기관명": _row_cell(row_cells, idx_place),
                "활동내용": _row_cell(row_cells, idx_content),
                "hours": hour_value,
                "raw_lines": [c for c in row_cells if c],
            }
            if not any(str(row.get(k) or "").strip() for k in ("일자또는기간", "장소또는주관기관명", "활동내용")):
                continue
            rows.append(row)

    if rows:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": False,
            "rows": rows,
            "items": [str(r.get("활동내용") or "") for r in rows if str(r.get("활동내용") or "").strip()],
        }
    if has_no_item:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": True,
            "rows": [],
            "items": [],
        }
    if saw_table:
        return {
            "raw_text": section_text.strip(),
            "has_no_item": True,
            "rows": [],
            "items": [],
        }

    # 2) 레거시 텍스트 파서 폴백
    lines = [ln.strip() for ln in section_text.splitlines() if ln.strip()]
    meaningful = []
    for ln in lines:
        compact = _compact(ln)
        if _is_noise_line(ln) or _is_empty_marker(ln):
            continue
        # 봉사 표 헤더 라인 제거
        if "학년" in compact and "일자또는기간" in compact and "활동내용" in compact:
            continue
        if "장소또는주관기관명" in compact and "활동내용" in compact:
            continue
        meaningful.append(ln)

    parsed_rows: List[Dict[str, Any]] = []
    current_grade: Optional[str] = None
    for line in meaningful:
        compact = _compact(line)
        if compact.startswith("학년봉사활동실적"):
            continue
        if compact.startswith("일자또는기간"):
            continue

        # 예: 1 2023.03.20. ... 또는 12023.03.20. ... (학년과 날짜가 붙어있는 형태)
        m_with_grade = re.match(r"^\s*([123])\s*(20\d{2}\.\d{2}\.\d{2}\.)\s*(.+)$", line)
        if not m_with_grade:
            m_with_grade = re.match(r"^\s*([123])(20\d{2}\.\d{2}\.\d{2}\.)\s*(.*)$", line)
        m_date_only = re.match(r"^\s*(20\d{2}\.\d{2}\.\d{2}\.)\s*(.+)$", line)
        date_only_line = False
        date_only_prev_grade = current_grade
        if m_with_grade:
            current_grade = m_with_grade.group(1)
            date_text = m_with_grade.group(2)
            body = m_with_grade.group(3).strip()
        elif m_date_only:
            date_only_line = True
            if current_grade is None:
                # 표 첫 행에서 학년이 생략되는 경우(대부분 1학년) 보정
                current_grade = "1"
            date_text = m_date_only.group(1)
            body = m_date_only.group(2).strip()
        else:
            continue

        hours_value: Optional[float] = None
        cumulative_hours: Optional[float] = None
        tail_hours = re.search(r"\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$", body)
        if tail_hours:
            try:
                hours_value = float(tail_hours.group(1))
            except Exception:
                hours_value = None
            try:
                cumulative_hours = float(tail_hours.group(2))
            except Exception:
                cumulative_hours = None
            body = body[: tail_hours.start()].strip()
        else:
            single_tail_hour = re.search(r"\s+(\d+(?:\.\d+)?)\s*$", body)
            if single_tail_hour:
                try:
                    hours_value = float(single_tail_hour.group(1))
                except Exception:
                    hours_value = None
                body = body[: single_tail_hour.start()].strip()

        # 학년 생략 + 누계시간 1로 초기화되는 첫 행은 다음 학년의 시작으로 간주
        if (
            date_only_line
            and date_only_prev_grade in {"1", "2"}
            and cumulative_hours is not None
            and int(cumulative_hours) == 1
        ):
            current_grade = str(int(date_only_prev_grade) + 1)

        place = ""
        content = body
        if body:
            parts = body.split(None, 1)
            if len(parts) == 2 and (
                parts[0].startswith("(")
                or any(parts[0].endswith(suf) for suf in ("학교", "기관", "센터", "관", "원", "청", "소", "재단", "협회", "회"))
            ):
                place = parts[0]
                content = parts[1]

        parsed_rows.append(
            {
                "grade": current_grade,
                "일자또는기간": date_text,
                "장소또는주관기관명": place,
                "활동내용": content,
                "hours": hours_value,
                "raw_lines": [line],
            }
        )

    if parsed_rows:
        has_no_item = False
        return {
            "raw_text": section_text.strip(),
            "has_no_item": False,
            "rows": parsed_rows,
            "items": [str(r.get("활동내용") or "") for r in parsed_rows if str(r.get("활동내용") or "").strip()],
        }

    rows = []
    current: Dict[str, Any] = {"grade": None, "raw_lines": []}
    for line in meaningful:
        compact = _compact(line)
        grade_match = re.search(r"([123])학년", compact)
        if grade_match:
            if current["raw_lines"]:
                rows.append(current)
            current = {"grade": grade_match.group(1), "raw_lines": []}
            remainder = re.sub(r"[123]학년", "", line).strip(" :|-")
            if remainder:
                current["raw_lines"].append(remainder)
            continue
        if compact in {"1", "2", "3"}:
            if current["raw_lines"]:
                rows.append(current)
            current = {"grade": compact, "raw_lines": []}
            continue
        current["raw_lines"].append(line)

    if current["raw_lines"]:
        rows.append(current)

    for row in rows:
        raw_lines = row.get("raw_lines") or []
        text = " ".join(raw_lines)
        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*시간", text)
        if hour_match:
            try:
                row["hours"] = float(hour_match.group(1))
            except Exception:
                row["hours"] = None
        else:
            row["hours"] = None
        # 구조화: 일자 또는 기간, 장소 또는 주관기관명, 활동내용 (휴리스틱)
        row["일자또는기간"] = ""
        row["장소또는주관기관명"] = ""
        row["활동내용"] = " ".join(raw_lines).strip() if raw_lines else ""
        if len(raw_lines) >= 1:
            row["일자또는기간"] = raw_lines[0].strip()
        if len(raw_lines) >= 2:
            row["장소또는주관기관명"] = raw_lines[1].strip()
        if len(raw_lines) >= 3:
            row["활동내용"] = " ".join(raw_lines[2:]).strip()

    # 헤더성/빈행 제거
    cleaned_rows = []
    for row in rows:
        raw_lines = [str(x).strip() for x in (row.get("raw_lines") or []) if str(x).strip()]
        if not raw_lines:
            continue
        joined = _compact(" ".join(raw_lines))
        if not joined:
            continue
        if "학년" in joined and "활동내용" in joined and "일자또는기간" in joined:
            continue
        cleaned = dict(row)
        cleaned["raw_lines"] = raw_lines
        cleaned_rows.append(cleaned)

    if cleaned_rows:
        has_no_item = False
    return {
        "raw_text": section_text.strip(),
        "has_no_item": has_no_item or ("해당사항없음" in _compact(section_text)),
        "rows": cleaned_rows,
        "items": meaningful,
    }


def _normalize_academic_subjects(parsed_school_record: Dict[str, Any]) -> None:
    """
    academicDevelopment 정규화.
    1) by_grade 항목에서 subject가 비어있거나 '미분류'면 note에서 과목명 추론
    2) 성적표 rows의 학기 병합셀/OCR 누락을 보정해 1/2학기 분리를 안정화
    """
    sections = (parsed_school_record or {}).get("sections") or {}
    acad = sections.get("academicDevelopment") or {}
    by_grade = acad.get("by_grade") or {}
    for g in ("1", "2", "3"):
        items = by_grade.get(g)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            subj = str(item.get("subject") or "").strip()
            note = str(item.get("note") or "").strip()
            if not subj or "미분류" in subj:
                inferred = _infer_subject_from_note(note)
                if inferred:
                    item["subject"] = inferred

    def _normalize_row_key(row: Dict[str, Any]) -> str:
        subject = _compact(str(row.get("과목") or ""))
        if subject:
            return f"s:{subject}"
        curriculum = _compact(str(row.get("교과") or ""))
        if curriculum:
            return f"c:{curriculum}"
        return ""

    def _normalize_table_rows(rows: List[Dict[str, Any]], table_key: str) -> None:
        if not rows:
            return

        corrected_row_indices: set[int] = set()
        for idx, row in enumerate(rows):
            before_group = str(row.get("교과") or "")
            before_subject = str(row.get("과목") or "")
            group, subject = _normalize_group_and_subject(
                before_group,
                before_subject,
            )
            row["교과"] = group
            row["과목"] = subject
            if _compact(before_group) != _compact(group) or _compact(before_subject) != _compact(subject):
                corrected_row_indices.add(idx)

            # 구버전 파싱 보정: 일반선택의 "3 P P"가 원점수/성취도로 잘못 들어간 경우
            # 원점수=P, 성취도=P(또는 NP), 석차등급 공백 -> 원점수 공백, 석차등급=P(또는 NP)
            raw_score = str(row.get("원점수") or "").strip().upper()
            ach = str(row.get("성취도") or "").strip().upper()
            rank = str(row.get("석차등급") or "").strip().upper()
            if raw_score in {"P", "NP"} and ach in {"P", "NP"} and not rank:
                row["원점수"] = ""
                row["석차등급"] = ach

        # 교과 셀이 페이지 분리로 "포함) 과학"처럼 끊긴 경우 보정
        for idx in range(1, len(rows)):
            prev = rows[idx - 1]
            cur = rows[idx]
            prev_group = str(prev.get("교과") or "").strip()
            cur_group = str(cur.get("교과") or "").strip()
            if not prev_group or not cur_group:
                continue
            if re.match(r"^포함\)\s*", cur_group) and "역사/도덕" in prev_group and not prev_group.endswith(")"):
                prev["교과"] = f"{prev_group} 포함)"
                cur["교과"] = re.sub(r"^포함\)\s*", "", cur_group).strip()

        terms: List[Optional[str]] = [_normalize_semester_term(str(row.get("학기") or "")) for row in rows]
        first_explicit_two = next((i for i, t in enumerate(terms) if t == "2"), None)

        def _has_key_overlap(boundary_idx: int) -> bool:
            if boundary_idx <= 0 or boundary_idx >= len(rows):
                return False
            before_keys = {_normalize_row_key(r) for r in rows[:boundary_idx]}
            after_keys = {_normalize_row_key(r) for r in rows[boundary_idx:]}
            before_keys.discard("")
            after_keys.discard("")
            return bool(before_keys & after_keys)

        # 1차 경계 후보: 과목(없으면 교과) 키가 처음 반복되는 지점
        seen_keys: Dict[str, int] = {}
        duplicate_boundary: Optional[int] = None
        for idx, row in enumerate(rows):
            key = _normalize_row_key(row)
            if not key:
                continue
            if key in seen_keys:
                duplicate_boundary = idx
                break
            seen_keys[key] = idx

        # 2차 경계 후보: 교과 시퀀스(예: 국어-수학-영어)가 다시 시작되는 지점
        curriculum_boundary: Optional[int] = None
        curriculum_keys = [_compact(str(r.get("교과") or "")) for r in rows]
        prefix = [k for k in curriculum_keys[:3] if k]
        if len(prefix) < 2:
            prefix = [k for k in curriculum_keys[:2] if k]
        if len(prefix) >= 2:
            window = len(prefix)
            scan_start = 2 if len(rows) <= 6 else 4
            for idx in range(scan_start, len(curriculum_keys) - window + 1):
                segment = curriculum_keys[idx : idx + window]
                if segment and segment == prefix and _has_key_overlap(idx):
                    curriculum_boundary = idx
                    break

        min_boundary_index = 2 if len(rows) <= 6 else 4
        split_boundary_candidates = [
            b for b in (duplicate_boundary, curriculum_boundary)
            if b is not None and b >= min_boundary_index
        ]
        split_boundary = min(split_boundary_candidates) if split_boundary_candidates else None

        force_duplicate_boundary = False
        if split_boundary is not None:
            should_split_from_duplicate = (
                first_explicit_two is None or first_explicit_two >= split_boundary
            )
            if (
                not should_split_from_duplicate
                and first_explicit_two is not None
                and first_explicit_two < split_boundary
            ):
                corrected_between = any(
                    first_explicit_two <= idx < split_boundary
                    for idx in corrected_row_indices
                )
                if corrected_between:
                    # 교과/과목 복구가 필요한 구간에서 학기 '2'가 먼저 등장하면
                    # 페이지 하단 잡음 숫자를 학기로 오인한 경우가 많다.
                    # 과목 반복 경계를 우선 신뢰해 1/2학기를 재분리한다.
                    should_split_from_duplicate = True
                    force_duplicate_boundary = True
            if should_split_from_duplicate:
                for idx in range(split_boundary, len(rows)):
                    rows[idx]["학기"] = "2"
                for idx in range(split_boundary):
                    if force_duplicate_boundary or not _normalize_semester_term(str(rows[idx].get("학기") or "")):
                        rows[idx]["학기"] = "1"

        # 남은 공백 학기는 앞/첫 값을 전파해 채움
        terms = [_normalize_semester_term(str(row.get("학기") or "")) for row in rows]
        current_term: Optional[str] = None
        for idx, term in enumerate(terms):
            if term:
                current_term = term
                continue
            if current_term:
                terms[idx] = current_term

        first_known_term = next((t for t in terms if t), None)
        if first_known_term:
            for idx, term in enumerate(terms):
                if term:
                    break
                terms[idx] = first_known_term

        for idx, row in enumerate(rows):
            row["학기"] = terms[idx] or "1"

    for table_key in ("general_elective", "career_elective", "pe_arts"):
        table = acad.get(table_key) or {}
        if not isinstance(table, dict):
            continue
        for g in ("1", "2", "3"):
            grade_block = table.get(g) or {}
            if not isinstance(grade_block, dict):
                continue
            rows = grade_block.get("rows")
            if not isinstance(rows, list):
                continue
            dict_rows = [row for row in rows if isinstance(row, dict)]
            _normalize_table_rows(dict_rows, table_key)


def _build_forms_from_pdf_text(extracted_text: str) -> Dict[str, Any]:
    section_texts = _split_school_record_sections(extracted_text)
    creative_parsed = _parse_creative_activity(section_texts.get("creative_activity", ""))
    volunteer_parsed = _parse_volunteer_activity(section_texts.get("volunteer_activity", ""))
    academic_section_text = section_texts.get("academic_development", "")
    academic_from_section = _parse_academic_unified(academic_section_text)
    academic_from_full = _parse_academic_unified(extracted_text)
    academic_unified = academic_from_section
    section_score = _academic_parse_score(academic_from_section)
    full_score = _academic_parse_score(academic_from_full)
    # 학업 구간이 분리되어 있으면 해당 구간만 신뢰한다.
    # 전체 문서 폴백은 뒤쪽 행동특성/종합의견 문장이 세특으로 섞이는 오염을 만들 수 있다.
    has_academic_section_text = bool(str(academic_section_text or "").strip())
    if not has_academic_section_text and section_score <= 0 and full_score > 0:
        academic_unified = academic_from_full
    elif not has_academic_section_text and section_score < 5000 and full_score > (section_score * 2):
        academic_unified = academic_from_full
    academic_parsed = {"by_grade": academic_unified["by_grade"], "raw_by_grade": academic_unified["raw_by_grade"]}
    academic_tables_parsed = {"general_elective": academic_unified["general_elective"], "career_elective": academic_unified["career_elective"], "pe_arts": academic_unified["pe_arts"]}
    behavior_section_text = section_texts.get("behavior_opinion", "")
    behavior_from_section = _sanitize_behavior_parsed(_parse_behavior_opinion(behavior_section_text))
    behavior_from_full = _sanitize_behavior_parsed(_parse_behavior_opinion(extracted_text))
    behavior_parsed = behavior_from_section
    section_cov = _behavior_grade_coverage(behavior_from_section)
    full_cov = _behavior_grade_coverage(behavior_from_full)
    if section_cov == 0 and full_cov > 0:
        behavior_parsed = behavior_from_full
    attendance_parsed = _parse_attendance(section_texts.get("attendance", ""))
    certificate_parsed = _parse_certificates(section_texts.get("certificates", ""))

    creative_form = {
        "byGrade": {
            "1": dict(creative_parsed["by_grade"]["1"]),
            "2": dict(creative_parsed["by_grade"]["2"]),
            "3": dict(creative_parsed["by_grade"]["3"]),
        }
    }

    academic_form: Dict[str, Any] = {"byGrade": {}}
    individual_form: Dict[str, Any] = {"showInputs": True, "byGrade": {}}
    for grade in ("1", "2", "3"):
        pairs = list(academic_parsed["by_grade"].get(grade, []))
        subjects: List[str] = []
        notes: List[str] = []
        individual_chunks: List[str] = []

        for pair in pairs:
            subject = str(pair.get("subject") or "").strip() or "과목"
            note = str(pair.get("note") or "").strip()
            if not note:
                continue
            individual_chunks.append(f"[{subject}]\n{note}")
            if len(subjects) < 3:
                subjects.append(subject)
                notes.append(note)

        subjects = (subjects + ["", "", ""])[:3]
        notes = (notes + ["", "", ""])[:3]

        academic_form["byGrade"][grade] = {"subjects": subjects, "notes": notes}
        individual_form["byGrade"][grade] = {"content": "\n\n".join(individual_chunks).strip()}

    behavior_form = {
        "showInputs": True,
        "opinions": [
            behavior_parsed.get("1", ""),
            behavior_parsed.get("2", ""),
            behavior_parsed.get("3", ""),
        ],
    }

    volunteer_form = {
        "rows": volunteer_parsed.get("rows") or [],
        "hasNoItem": bool(volunteer_parsed.get("has_no_item")),
    }

    parsed_school_record = {
        "parserVersion": RULE_PARSER_VERSION,
        "sections": {
            "attendance": attendance_parsed,
            "certificates": certificate_parsed,
            "creativeActivity": {
                "raw_text": section_texts.get("creative_activity", ""),
                "by_grade": creative_parsed["by_grade"],
                "hours_by_grade": creative_parsed["hours_by_grade"],
            },
            "volunteerActivity": volunteer_parsed,
            "academicDevelopment": {
                "raw_text": section_texts.get("academic_development", ""),
                "by_grade": academic_parsed["by_grade"],
                "raw_by_grade": academic_parsed["raw_by_grade"],
                "general_elective": academic_tables_parsed["general_elective"],
                "career_elective": academic_tables_parsed["career_elective"],
                "pe_arts": academic_tables_parsed["pe_arts"],
            },
            "behaviorOpinion": {
                "raw_text": section_texts.get("behavior_opinion", ""),
                "by_grade": behavior_parsed,
            },
        },
    }

    academic_note_count = sum(
        len([
            1
            for pair in academic_parsed["by_grade"].get(g, [])
            if str(pair.get("note") or "").strip()
        ])
        for g in ("1", "2", "3")
    )

    parse_summary = {
        "section_chars": {
            "attendance": len(section_texts.get("attendance", "")),
            "certificates": len(section_texts.get("certificates", "")),
            "creative_activity": len(section_texts.get("creative_activity", "")),
            "volunteer_activity": len(section_texts.get("volunteer_activity", "")),
            "academic_development": len(section_texts.get("academic_development", "")),
            "behavior_opinion": len(section_texts.get("behavior_opinion", "")),
        },
        "academic_note_count": academic_note_count,
        "creative_note_count": sum(
            1
            for grade in ("1", "2", "3")
            for key in ("autonomousNotes", "clubNotes", "careerNotes")
            if str(creative_parsed["by_grade"][grade].get(key) or "").strip()
        ),
        "behavior_grade_count": sum(
            1 for grade in ("1", "2", "3") if str(behavior_parsed.get(grade) or "").strip()
        ),
        "volunteer_item_count": len(volunteer_parsed.get("rows") or []),
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


def _build_parsed_preview(parsed_school_record: Dict[str, Any]) -> Dict[str, Any]:
    sections = dict((parsed_school_record or {}).get("sections") or {})
    acad = sections.get("academicDevelopment") or {}
    return {
        "parserVersion": parsed_school_record.get("parserVersion", RULE_PARSER_VERSION),
        "sections": {
            "attendance": {
                "has_no_item": bool(((sections.get("attendance") or {}).get("has_no_item"))),
                "rows": list(((sections.get("attendance") or {}).get("rows") or [])),
            },
            "certificates": {
                "has_no_item": bool(((sections.get("certificates") or {}).get("has_no_item"))),
                "items": list(((sections.get("certificates") or {}).get("items") or [])),
                "rows": list(((sections.get("certificates") or {}).get("rows") or [])),
            },
            "creativeActivity": {
                "by_grade": dict(((sections.get("creativeActivity") or {}).get("by_grade") or {})),
                "hours_by_grade": dict(((sections.get("creativeActivity") or {}).get("hours_by_grade") or {})),
            },
            "volunteerActivity": {
                "has_no_item": bool(((sections.get("volunteerActivity") or {}).get("has_no_item"))),
                "rows": list(((sections.get("volunteerActivity") or {}).get("rows") or [])),
            },
            "academicDevelopment": {
                "by_grade": dict(acad.get("by_grade") or {}),
                "general_elective": dict(acad.get("general_elective") or {}),
                "career_elective": dict(acad.get("career_elective") or {}),
                "pe_arts": dict(acad.get("pe_arts") or {}),
            },
            "behaviorOpinion": {
                "by_grade": dict(((sections.get("behaviorOpinion") or {}).get("by_grade") or {})),
            },
        },
    }


def _merge_forms_from_parsed_preview(
    parsed_preview: Dict[str, Any],
    existing_forms: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    forms = dict(existing_forms or {})
    preview = dict(parsed_preview or {})
    sections = dict(preview.get("sections") or {})

    existing_parsed_school_record = dict(forms.get("parsedSchoolRecord") or {})
    existing_sections = dict(existing_parsed_school_record.get("sections") or {})

    attendance_rows = list(((sections.get("attendance") or {}).get("rows") or []))
    attendance_has_no_item = bool(((sections.get("attendance") or {}).get("has_no_item"))
    )

    certificate_rows = list(((sections.get("certificates") or {}).get("rows") or []))
    certificate_items = list(((sections.get("certificates") or {}).get("items") or []))
    certificate_has_no_item = bool(((sections.get("certificates") or {}).get("has_no_item"))
    )

    creative_section = dict(sections.get("creativeActivity") or {})
    creative_by_grade = dict(creative_section.get("by_grade") or {})
    creative_hours_by_grade = dict(creative_section.get("hours_by_grade") or {})

    volunteer_section = dict(sections.get("volunteerActivity") or {})
    volunteer_rows = list(volunteer_section.get("rows") or [])
    volunteer_has_no_item = bool(volunteer_section.get("has_no_item"))

    academic_section = dict(sections.get("academicDevelopment") or {})
    academic_by_grade = dict(academic_section.get("by_grade") or {})
    general_elective = dict(academic_section.get("general_elective") or {})
    career_elective = dict(academic_section.get("career_elective") or {})
    pe_arts = dict(academic_section.get("pe_arts") or {})

    behavior_by_grade = dict(((sections.get("behaviorOpinion") or {}).get("by_grade") or {}))

    parser_version = str(
        preview.get("parserVersion")
        or (forms.get("parsedSchoolRecord") or {}).get("parserVersion")
        or RULE_PARSER_VERSION
    )

    # 기존 parsedSchoolRecord가 있으면 raw_text/raw_by_grade 등 누락 없이 유지하면서 수정값만 덮어쓰기
    parsed_school_record = dict(existing_parsed_school_record or {})
    parsed_school_record["parserVersion"] = parser_version
    parsed_school_record.setdefault("sections", {})
    ps_sections = dict(parsed_school_record.get("sections") or {})

    ps_att = dict(ps_sections.get("attendance") or {})
    ps_att["has_no_item"] = attendance_has_no_item
    ps_att["rows"] = attendance_rows
    ps_sections["attendance"] = ps_att

    ps_cert = dict(ps_sections.get("certificates") or {})
    ps_cert["has_no_item"] = certificate_has_no_item
    ps_cert["items"] = certificate_items
    ps_cert["rows"] = certificate_rows
    ps_sections["certificates"] = ps_cert

    ps_creative = dict(ps_sections.get("creativeActivity") or {})
    ps_creative["by_grade"] = creative_by_grade
    ps_creative["hours_by_grade"] = creative_hours_by_grade
    ps_sections["creativeActivity"] = ps_creative

    ps_vol = dict(ps_sections.get("volunteerActivity") or {})
    ps_vol["has_no_item"] = volunteer_has_no_item
    ps_vol["rows"] = volunteer_rows
    ps_sections["volunteerActivity"] = ps_vol

    ps_acad = dict(ps_sections.get("academicDevelopment") or {})
    ps_acad["by_grade"] = academic_by_grade
    ps_acad["general_elective"] = general_elective
    ps_acad["career_elective"] = career_elective
    ps_acad["pe_arts"] = pe_arts
    # raw_by_grade/raw_text는 기존 값 유지
    if "raw_by_grade" not in ps_acad:
        ps_acad["raw_by_grade"] = dict((existing_sections.get("academicDevelopment") or {}).get("raw_by_grade") or {})
    if "raw_text" not in ps_acad:
        ps_acad["raw_text"] = str((existing_sections.get("academicDevelopment") or {}).get("raw_text") or "")
    ps_sections["academicDevelopment"] = ps_acad

    ps_behavior = dict(ps_sections.get("behaviorOpinion") or {})
    ps_behavior["by_grade"] = behavior_by_grade
    if "raw_text" not in ps_behavior:
        ps_behavior["raw_text"] = str((existing_sections.get("behaviorOpinion") or {}).get("raw_text") or "")
    ps_sections["behaviorOpinion"] = ps_behavior

    parsed_school_record["sections"] = ps_sections

    # UI 폼 호환 구조도 함께 갱신
    creative_form_by_grade: Dict[str, Dict[str, Any]] = {}
    for g in ("1", "2", "3"):
        notes = dict(creative_by_grade.get(g) or {})
        hours = dict(creative_hours_by_grade.get(g) or {})
        creative_form_by_grade[g] = {
            "autonomousNotes": str(notes.get("autonomousNotes") or ""),
            "clubNotes": str(notes.get("clubNotes") or ""),
            "careerNotes": str(notes.get("careerNotes") or ""),
            "autonomousHours": hours.get("autonomousHours"),
            "clubHours": hours.get("clubHours"),
            "careerHours": hours.get("careerHours"),
        }
    forms["creativeActivity"] = {
        "showInputs": True,
        "grade": 1,
        "autonomousNotes": creative_form_by_grade["1"]["autonomousNotes"],
        "clubNotes": creative_form_by_grade["1"]["clubNotes"],
        "careerNotes": creative_form_by_grade["1"]["careerNotes"],
        "byGrade": creative_form_by_grade,
    }

    def _notes_and_subjects(rows: Any) -> tuple[list[str], list[str]]:
        rows_list = list(rows or [])
        subjects = [str((r or {}).get("subject") or "") for r in rows_list]
        notes = [str((r or {}).get("note") or "") for r in rows_list]
        return subjects, notes

    academic_form_by_grade: Dict[str, Dict[str, Any]] = {}
    for g in ("1", "2", "3"):
        subjects, notes = _notes_and_subjects(academic_by_grade.get(g) or [])
        academic_form_by_grade[g] = {"subjects": subjects, "notes": notes}
    forms["academicDev"] = {
        "showInputs": True,
        "grade": 1,
        "subjects": academic_form_by_grade["1"]["subjects"][:3],
        "notes": academic_form_by_grade["1"]["notes"][:3],
        "byGrade": academic_form_by_grade,
    }

    individual_by_grade: Dict[str, Dict[str, Any]] = {}
    for g in ("1", "2", "3"):
        _, notes = _notes_and_subjects(academic_by_grade.get(g) or [])
        content = "\n".join([n for n in notes if str(n).strip()])
        individual_by_grade[g] = {"notes": notes, "content": content}
    forms["individualDev"] = {
        "showInputs": True,
        "grade": 1,
        "notes": individual_by_grade["1"]["notes"][:3],
        "byGrade": individual_by_grade,
    }

    behavior_opinions = [str(behavior_by_grade.get(g) or "") for g in ("1", "2", "3")]
    forms["behaviorOpinion"] = {
        "showInputs": True,
        "grade": 1,
        "opinions": behavior_opinions,
    }

    forms["volunteerActivity"] = {"rows": volunteer_rows}
    forms["parsedSchoolRecord"] = parsed_school_record

    academic_note_count = sum(
        len([1 for pair in (academic_by_grade.get(g) or []) if str((pair or {}).get("note") or "").strip()])
        for g in ("1", "2", "3")
    )
    forms["parsedSchoolRecordSummary"] = {
        "section_chars": {
            "attendance": len(json.dumps(sections.get("attendance") or {}, ensure_ascii=False)),
            "certificates": len(json.dumps(sections.get("certificates") or {}, ensure_ascii=False)),
            "creative_activity": len(json.dumps(sections.get("creativeActivity") or {}, ensure_ascii=False)),
            "volunteer_activity": len(json.dumps(sections.get("volunteerActivity") or {}, ensure_ascii=False)),
            "academic_development": len(json.dumps(sections.get("academicDevelopment") or {}, ensure_ascii=False)),
            "behavior_opinion": len(json.dumps(sections.get("behaviorOpinion") or {}, ensure_ascii=False)),
        },
        "academic_note_count": academic_note_count,
        "creative_note_count": sum(
            1
            for g in ("1", "2", "3")
            for k in ("autonomousNotes", "clubNotes", "careerNotes")
            if str((creative_by_grade.get(g) or {}).get(k) or "").strip()
        ),
        "behavior_grade_count": sum(1 for g in ("1", "2", "3") if str(behavior_by_grade.get(g) or "").strip()),
        "volunteer_item_count": len(volunteer_rows),
    }

    return forms


@router.get("/health")
async def health():
    """생기부 평가 모듈 헬스 체크"""
    return {"status": "ok", "module": "school_record_eval"}


@router.post("/evaluate", response_model=SchoolRecordEvaluateResponse)
async def evaluate(
    request: SchoolRecordEvaluateRequest,
    authorization: Optional[str] = Header(None),
):
    """
    생기부 텍스트를 평가합니다.
    로그인한 경우 결과를 user_profiles.metadata.school_record 에 저장합니다.
    """
    try:
        result = await evaluate_school_record(request)
        user = await optional_auth(authorization)
        if user and result.get("success") and result.get("result"):
            user_id = user.get("user_id")
            if user_id:
                school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
                school = dict(school_loaded or {})
                items = list(school.get("items") or [])
                items.append({
                    "content": (request.content or "")[:30000],
                    "hope_major": (request.hope_major or "").strip(),
                    "result": result.get("result"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                school["items"] = items[-MAX_SAVED_ITEMS:]
                await SupabaseService.update_user_profile_school_record(user_id, school)
        return SchoolRecordEvaluateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생기부 평가 처리 중 오류: {str(e)}")


@router.post("/diagnose")
async def diagnose(body: dict = Body(...)):
    """
    세특 초안을 4단계 필승구조 + 전공계열 + 체크리스트 기준으로 진단합니다.
    body: { "content": "세특 텍스트", "hope_major": "희망 전공(선택)" }
    returns: success, original_text, highlights, goodPoints, reconsiderPoints, writing_direction,
             structure_analysis, checklist, admission_comment, error
    """
    try:
        content = (body.get("content") or "").strip()
        hope_major = (body.get("hope_major") or "").strip() or None
        result = await diagnose_school_record(content, hope_major=hope_major)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_school_records(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 user_profiles.metadata.school_record 목록을 반환합니다.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
    items = school.get("items") or []
    return {"items": items}


@router.get("/status")
async def get_school_record_status(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 생기부 연동 상태만 반환합니다.
    - linked: user_profiles.school_record(또는 metadata.school_record) 에 의미 있는 데이터가 있으면 True
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    linked = has_meaningful_school_record(dict(school_loaded or {}))
    return {"linked": linked}


@router.get("/forms")
async def get_school_record_forms(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 생기부 폼 데이터를 반환합니다.
    user_profiles.metadata.school_record.forms
    구분: 창의적체험활동상황, 과목별세부능력및특기사항, 개인별세부능력및특기사항, 행동특성 및 종합의견
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
    forms = school.get("forms") if isinstance(school.get("forms"), dict) else {}
    if not forms:
        forms = {}
    for key in (
        "creativeActivity",
        "academicDev",
        "individualDev",
        "behaviorOpinion",
        "volunteerActivity",
        "parsedSchoolRecord",
        "parsedSchoolRecordSummary",
        "rawSchoolRecordText",
        "pdfImportMeta",
    ):
        if key not in forms and key in school:
            forms[key] = school.get(key)

    parsed_school_record = forms.get("parsedSchoolRecord")
    raw_text = str(forms.get("rawSchoolRecordText") or "")
    import_meta = dict(forms.get("pdfImportMeta") or {})
    parse_method = str(import_meta.get("parse_method") or "").strip().lower()
    parser_version = (
        str((parsed_school_record or {}).get("parserVersion") or "")
        if isinstance(parsed_school_record, dict)
        else ""
    )
    should_rebuild_from_raw = (
        bool(raw_text.strip())
        and parse_method != "gemini"
        and (
            not isinstance(parsed_school_record, dict)
            or not parsed_school_record
            or parser_version != RULE_PARSER_VERSION
        )
    )
    mutated = False
    if should_rebuild_from_raw:
        rebuilt_forms = _build_forms_from_pdf_text(raw_text)
        rebuilt_parsed = rebuilt_forms.get("parsedSchoolRecord") or {}
        _normalize_academic_subjects(rebuilt_parsed)
        forms["creativeActivity"] = rebuilt_forms.get("creativeActivity") or {}
        forms["academicDev"] = rebuilt_forms.get("academicDev") or {}
        forms["individualDev"] = rebuilt_forms.get("individualDev") or {}
        forms["behaviorOpinion"] = rebuilt_forms.get("behaviorOpinion") or {}
        forms["volunteerActivity"] = rebuilt_forms.get("volunteerActivity") or {}
        forms["parsedSchoolRecord"] = rebuilt_parsed
        forms["parsedSchoolRecordSummary"] = rebuilt_forms.get("parseSummary") or {}
        parsed_school_record = rebuilt_parsed
        mutated = True

    if isinstance(parsed_school_record, dict) and parsed_school_record:
        before = json.dumps(parsed_school_record, ensure_ascii=False, sort_keys=True)
        _normalize_academic_subjects(parsed_school_record)
        after = json.dumps(parsed_school_record, ensure_ascii=False, sort_keys=True)
        if before != after:
            forms["parsedSchoolRecord"] = parsed_school_record
            mutated = True
    if mutated:
        school["forms"] = forms
        school["parsedSchoolRecord"] = copy.deepcopy(forms.get("parsedSchoolRecord") or {})
        school["parsedSchoolRecordSummary"] = copy.deepcopy(forms.get("parsedSchoolRecordSummary") or {})
        school["saved_at"] = datetime.now(timezone.utc).isoformat()
        await SupabaseService.update_user_profile_school_record(user_id, school)
    return {"forms": forms}


@router.post("/forms")
async def save_school_record_forms(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    생기부 폼 데이터를 저장합니다. (병합)
    body: { "creativeActivity"?, "academicDev"?, "individualDev"?, "behaviorOpinion"? }
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
    existing_forms = dict(school.get("forms") or {})
    for key in (
        "creativeActivity",
        "academicDev",
        "individualDev",
        "behaviorOpinion",
        "volunteerActivity",
        "parsedSchoolRecord",
        "parsedSchoolRecordSummary",
        "pdfImportMeta",
        "rawSchoolRecordText",
    ):
        if key in body and body[key] is not None:
            existing_forms[key] = body[key]
    school["forms"] = existing_forms
    await SupabaseService.update_user_profile_school_record(user_id, school)
    return {"ok": True, "forms": existing_forms}


@router.post("/forms/save-parsed")
async def save_parsed_school_record(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    프론트에서 편집된 parsedPreview를 기준으로 생기부 전체 구조를 저장합니다.
    저장 대상:
    - user_profiles.school_record (JSONB)
    - user_profiles.metadata.school_record (호환용)
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")

    parsed_preview = body.get("parsedPreview")
    if not isinstance(parsed_preview, dict) or not isinstance(parsed_preview.get("sections"), dict):
        raise HTTPException(status_code=400, detail="parsedPreview.sections is required")

    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")

    school = dict(school_loaded or {})
    existing_forms = dict(school.get("forms") or {})
    merged_forms = _merge_forms_from_parsed_preview(parsed_preview, existing_forms)

    # 있으면 덮어쓰기 (없으면 기존 유지)
    for opt_key in ("pdfImportMeta", "rawSchoolRecordText", "parsedSchoolRecordSummary"):
        if opt_key in body and body[opt_key] is not None:
            merged_forms[opt_key] = body[opt_key]

    # PDF에서 파싱된 정보 전부가 user_profiles.school_record(JSONB)에 들어가도록 forms + 최상위 동기화
    school["forms"] = merged_forms
    school["pdfImportMeta"] = copy.deepcopy(merged_forms.get("pdfImportMeta") or {})
    school["rawSchoolRecordText"] = merged_forms.get("rawSchoolRecordText") or ""
    school["parsedSchoolRecord"] = copy.deepcopy(merged_forms.get("parsedSchoolRecord") or {})
    school["parsedSchoolRecordSummary"] = copy.deepcopy(merged_forms.get("parsedSchoolRecordSummary") or {})
    school["saved_at"] = datetime.now(timezone.utc).isoformat()

    ok = await SupabaseService.update_user_profile_school_record(user_id, school)
    if not ok:
        raise HTTPException(status_code=500, detail="Profile save failed")

    return {
        "ok": True,
        "message": "생활기록부 저장이 완료되었습니다.",
        "meta": merged_forms.get("pdfImportMeta") or {},
        "summary": merged_forms.get("parsedSchoolRecordSummary") or {},
        "parsedPreview": _build_parsed_preview(merged_forms.get("parsedSchoolRecord") or {}),
    }


@router.post("/forms/upload-pdf")
async def upload_school_record_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    정부24/카카오 전자문서지갑에서 저장한 생기부 PDF를 업로드하여
    user_profiles.metadata.school_record.forms에 연동 저장합니다.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    started_at = time.perf_counter()

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail=f"파일 크기는 {MAX_PDF_SIZE_MB}MB 이하여야 합니다.")
    file_hash = _build_pdf_file_hash(file_bytes)

    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")

    school = dict(school_loaded or {})
    forms = dict(school.get("forms") or {})

    existing_import_meta = dict(forms.get("pdfImportMeta") or {})
    existing_hash = str(existing_import_meta.get("file_hash") or "")
    has_cached_parse = _is_cache_compatible(forms, existing_import_meta)
    if existing_hash and existing_hash == file_hash and has_cached_parse:
        cached_meta = dict(existing_import_meta)
        cached_meta["filename"] = filename or cached_meta.get("filename") or "school_record.pdf"
        cached_meta["uploaded_at"] = datetime.now(timezone.utc).isoformat()
        forms["pdfImportMeta"] = cached_meta
        school["forms"] = forms
        school["pdfImportMeta"] = forms.get("pdfImportMeta") or {}
        school["rawSchoolRecordText"] = forms.get("rawSchoolRecordText") or ""
        school["parsedSchoolRecord"] = forms.get("parsedSchoolRecord") or {}
        school["parsedSchoolRecordSummary"] = forms.get("parsedSchoolRecordSummary") or {}
        await SupabaseService.update_user_profile_school_record(user_id, school)
        total_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            "ok": True,
            "message": "동일한 PDF가 이미 파싱되어 캐시 결과를 사용했습니다.",
            "meta": cached_meta,
            "summary": forms.get("parsedSchoolRecordSummary") or {},
            "parsedPreview": _build_parsed_preview(forms.get("parsedSchoolRecord") or {}),
            "timings": {
                "cache_hit": True,
                "total_ms": total_ms,
            },
        }

    extract_started_at = time.perf_counter()
    try:
        extracted, page_count, extraction_method = _extract_text_from_pdf_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF 텍스트 추출 실패: {str(e)}")
    extract_ms = int((time.perf_counter() - extract_started_at) * 1000)

    if page_count <= 0:
        raise HTTPException(
            status_code=400,
            detail="PDF 페이지를 읽을 수 없습니다. 파일이 손상되었거나 지원되지 않는 형식인지 확인해 주세요.",
        )
    if len(extracted.strip()) < MIN_EXTRACTED_TEXT_CHARS:
        raise HTTPException(
            status_code=400,
            detail="텍스트를 거의 추출하지 못했습니다. 텍스트 선택 가능한 PDF이거나 선명한 스캔본인지 확인해 주세요.",
        )

    parse_started_at = time.perf_counter()
    raw_text = extracted
    parse_method = "rule"
    parsed_forms = _build_forms_from_pdf_text(raw_text)
    _normalize_academic_subjects(parsed_forms.get("parsedSchoolRecord") or {})
    parse_ms = int((time.perf_counter() - parse_started_at) * 1000)
    total_ms = int((time.perf_counter() - started_at) * 1000)

    # 심층분석에서 바로 활용할 수 있도록 원문 전체 텍스트 저장
    forms["rawSchoolRecordText"] = raw_text
    forms["pdfImportMeta"] = {
        "filename": filename,
        "char_count": len(raw_text),
        "page_count": page_count,
        "extraction_method": extraction_method,
        "parse_method": parse_method,
        "file_hash": file_hash,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "timings_ms": {
            "extract_ms": extract_ms,
            "parse_ms": parse_ms,
            "total_ms": total_ms,
        },
    }

    # PDF 파싱 결과 전부를 user_profiles.school_record(JSONB)에 저장 (deep copy로 전체 구조 보존)
    full_parsed = copy.deepcopy(parsed_forms["parsedSchoolRecord"])
    full_summary = copy.deepcopy(parsed_forms["parseSummary"])
    forms["creativeActivity"] = parsed_forms["creativeActivity"]
    forms["academicDev"] = parsed_forms["academicDev"]
    forms["individualDev"] = parsed_forms["individualDev"]
    forms["behaviorOpinion"] = parsed_forms["behaviorOpinion"]
    forms["volunteerActivity"] = parsed_forms["volunteerActivity"]
    forms["parsedSchoolRecord"] = full_parsed
    forms["parsedSchoolRecordSummary"] = full_summary

    school["forms"] = forms
    school["pdfImportMeta"] = copy.deepcopy(forms["pdfImportMeta"])
    school["rawSchoolRecordText"] = raw_text
    school["parsedSchoolRecord"] = full_parsed
    school["parsedSchoolRecordSummary"] = full_summary
    await SupabaseService.update_user_profile_school_record(user_id, school)

    return {
        "ok": True,
        "message": "생기부 PDF를 전체 파싱하여 연동했습니다.",
        "meta": forms.get("pdfImportMeta"),
        "summary": parsed_forms["parseSummary"],
        "parsedPreview": _build_parsed_preview(parsed_forms["parsedSchoolRecord"]),
        "timings": {
            "cache_hit": False,
            "extract_ms": extract_ms,
            "parse_ms": parse_ms,
            "total_ms": total_ms,
        },
    }
