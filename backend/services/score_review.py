"""
Profile-agent bridge + score review helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import asyncio
import importlib
import json
import os
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
    text = message or ""
    dedup: list[str] = []
    seen = set()

    def push(token: str) -> None:
        t = (token or "").strip()
        if not t or t in seen:
            return
        seen.add(t)
        dedup.append(t)

    # 1) @내성적6으로 / @내성적 6 같은 형태를 우선적으로 정확히 파싱
    for n in re.findall(r"@내성적\s*([0-9]{1,3})", text):
        try:
            push(f"내성적{int(n)}")
        except ValueError:
            continue

    # 2) 일반 @토큰 파싱 + 조사 제거 후보 추가
    tokens = re.findall(r"@([가-힣a-zA-Z0-9_]{1,10})", text)
    josa_suffixes = [
        "으로는", "에서는", "에게는", "이랑은", "랑은",
        "에서", "에게", "으로", "로는", "이랑", "부터", "까지",
        "은", "는", "이", "가", "을", "를", "와", "과", "도", "만", "로", "랑",
    ]
    for token in tokens:
        push(token)
        for suffix in josa_suffixes:
            if token.endswith(suffix) and len(token) > len(suffix):
                push(token[: -len(suffix)])
                break

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


# ──────────────────────────────────────────────
# 수시/내신 입력 파싱 (LLM 기반, 채팅 → school_grade_input)
# ──────────────────────────────────────────────

NAESIN_LLM_SYSTEM_PROMPT = """사용자 메시지에서 수시/내신(교과) 관련 등급만 추출하세요.

[추출 규칙]
1. 내신·수시·학종·전과목·국영수탐·국영수과·전체·학년별(고1/1학년, 고2/2학년, 고3/3학년) 등 어떤 표현이든 등급 숫자(1~9, 소수 가능)를 추론합니다.
2. 오타도 이해합니다 (예: 국여수탐 → 국영수탐, 국수영탐 → 국영수탐).
3. 학년별로 하나의 값만 있으면 (예: "1학년 3.3"):
   - 값 하나만 있으면 overall=core=그 값으로 처리
   - "국영수탐 3.3"이라고 하면 core=3.3, overall은 모르면 비워두거나 추정
4. 학기별로 다른 경우: "1-1", "1-2", "2-1", "2-2", "3-1", "3-2" 각각에 overall(전과목 평균)와 core(국영수탐 평균)를 채웁니다.
5. 값이 없는 학기는 채우지 않거나, 주어진 값들의 평균으로 채울 수 있습니다.
6. 메시지에 수시/내신 등급이 전혀 없으면 has_naesin을 false로 하고 나머지는 생략하세요.

[출력 형식 - JSON만]
{
  "has_naesin": true/false,
  "overall": 전과목 평균 (선택, 1~9),
  "core": 국영수탐 평균 (선택, 1~9),
  "semesters": {
    "1-1": {"overall": 숫자 또는 null, "core": 숫자 또는 null},
    "1-2": {"overall": 숫자 또는 null, "core": 숫자 또는 null},
    "2-1": {"overall": 숫자 또는 null, "core": 숫자 또는 null},
    "2-2": {"overall": 숫자 또는 null, "core": 숫자 또는 null},
    "3-1": {"overall": 숫자 또는 null, "core": 숫자 또는 null},
    "3-2": {"overall": 숫자 또는 null, "core": 숫자 또는 null}
  }
}

- overall이나 core 중 하나만 있으면 다른 하나도 같은 값으로 간주합니다.
- semesters에 값이 있으면 우선 사용합니다.
- semesters가 비어 있으면 overall과 core로 6학기 동일 적용합니다."""

RAW_SCORE_BY_CLASS_RANK = {
    1: 96, 2: 92, 3: 88, 4: 84, 5: 80, 6: 76, 7: 72, 8: 68, 9: 64,
}

SEMESTER_KEYS = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"]

DEFAULT_SUBJECTS = [
    {"trackType": "일반선택", "curriculum": "국어",              "subject": "국어",       "credits": "4"},
    {"trackType": "일반선택", "curriculum": "수학",              "subject": "수학",       "credits": "4"},
    {"trackType": "일반선택", "curriculum": "영어",              "subject": "영어",       "credits": "4"},
    {"trackType": "일반선택", "curriculum": "한국사",            "subject": "한국사",     "credits": "3"},
    {"trackType": "일반선택", "curriculum": "사회(역사/도덕포함)", "subject": "통합사회",   "credits": "3"},
    {"trackType": "일반선택", "curriculum": "과학",              "subject": "통합과학",   "credits": "3"},
    {"trackType": "일반선택", "curriculum": "과학",              "subject": "과학탐구실험", "credits": "1"},
    {"trackType": "일반선택", "curriculum": "기술·가정",         "subject": "기술·가정",  "credits": "3"},
    {"trackType": "진로선택",  "curriculum": "예술",             "subject": "음악 연주",  "credits": "2"},
    {"trackType": "일반선택", "curriculum": "체육",              "subject": "체육",       "credits": "2"},
]

CORE_CURRICULUMS = {"국어", "수학", "영어", "한국사", "과학", "사회(역사/도덕포함)", "통합사회", "통합과학"}


@dataclass
class NaesinCandidate:
    has_candidate: bool
    overall_average: float
    core_average: float
    school_grade_input: Dict[str, Any]


def _allocate_grades(count: int, target_sum: int) -> list[int]:
    """count명에 target_sum 합이 되도록 1~9 정수 등급 배열 생성."""
    if count <= 0:
        return []
    base = max(1, min(9, target_sum // count))
    remainder = target_sum - base * count
    grades: list[int] = []
    if remainder > 0 and base < 9:
        high = min(9, base + 1)
        for i in range(remainder):
            grades.append(high)
        for i in range(remainder, count):
            grades.append(base)
    else:
        for _ in range(count):
            grades.append(base)
    return grades


def _is_valid_grade(v: float) -> bool:
    return 0 < v <= 9


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """텍스트에서 첫 번째 '{' ~ 마지막 '}' 사이를 JSON으로 파싱."""
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


def _parse_naesin_with_llm(message: str) -> Optional[Dict[str, tuple]]:
    """
    LLM으로 사용자 메시지에서 수시/내신 등급을 추출해 학기별 (overall, core) 맵 반환.
    실패 시 None.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    text = (message or "").strip()
    if not text:
        return None
    max_chars = 4000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[이하 생략]"
    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=os.getenv("GEMINI_NAESIN_MODEL", "gemini-2.0-flash"),
            system_instruction=NAESIN_LLM_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            f"다음 사용자 메시지에서 수시/내신 등급을 추출해 지정한 JSON만 출력하세요.\n\n[메시지]\n{text}",
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                max_output_tokens=1024,
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
        data = _extract_json_from_text(response.text)
        if not data or not data.get("has_naesin"):
            return None

        semester_map: Dict[str, tuple] = {}
        semesters_raw = data.get("semesters")
        if semesters_raw and isinstance(semesters_raw, dict):
            for sk in SEMESTER_KEYS:
                entry = semesters_raw.get(sk)
                if isinstance(entry, dict):
                    ov = entry.get("overall")
                    co = entry.get("core")
                    if ov is not None or co is not None:
                        try:
                            o = float(ov) if ov is not None else float(co)
                            c = float(co) if co is not None else float(ov)
                            if _is_valid_grade(o) and _is_valid_grade(c):
                                semester_map[sk] = (round(o, 2), round(c, 2))
                        except (TypeError, ValueError):
                            pass
            if semester_map:
                existing_vals = list(semester_map.values())
                fallback = (
                    round(sum(v[0] for v in existing_vals) / len(existing_vals), 2),
                    round(sum(v[1] for v in existing_vals) / len(existing_vals), 2),
                )
                for sk in SEMESTER_KEYS:
                    semester_map.setdefault(sk, fallback)
                return semester_map

        ov = data.get("overall")
        co = data.get("core")
        if ov is not None or co is not None:
            try:
                o = float(ov) if ov is not None else float(co)
                c = float(co) if co is not None else float(ov)
                if o is None:
                    o = c
                if c is None:
                    c = o
                if _is_valid_grade(o) and _is_valid_grade(c):
                    return {sk: (round(o, 2), round(c, 2)) for sk in SEMESTER_KEYS}
            except (TypeError, ValueError):
                pass
    except Exception:  # noqa: BLE001
        pass
    return None


def _parse_naesin_with_rules(message: str) -> Optional[Dict[str, tuple]]:
    """
    LLM 실패/미사용 환경에서도 동작하는 간단 규칙 파서.
    - 5~6자리 등급 연속 입력: 12111, 1 2 1 1 1, 1/2/1/1/1 등
    - 내신/수시 + 단일 등급 입력: "내신 2.3"
    """
    text = (message or "").strip()
    if not text:
        return None

    # 예: "12111", "1 2 1 1 1", "1/2/1/1/1"
    compact_grade_pattern = re.compile(r"(?:^|[^0-9])([1-9](?:[\s,./|-]*[1-9]){4,5})(?:[^0-9]|$)")
    m = compact_grade_pattern.search(text)
    if m:
        digits = [int(ch) for ch in re.findall(r"[1-9]", m.group(1))]
        if 5 <= len(digits) <= 6:
            avg = round(sum(digits) / len(digits), 2)
            return {sk: (avg, avg) for sk in SEMESTER_KEYS}

    # 예: "내신 2.4", "수시 3"
    single_grade_pattern = re.compile(r"(?:내신|수시|학종|교과)[^\d]{0,8}([1-9](?:\.\d+)?)")
    m2 = single_grade_pattern.search(text)
    if m2:
        try:
            g = float(m2.group(1))
            if _is_valid_grade(g):
                g = round(g, 2)
                return {sk: (g, g) for sk in SEMESTER_KEYS}
        except (TypeError, ValueError):
            pass

    return None


def _fmt_grade(v: float) -> str:
    return str(v) if v != int(v) else str(int(v))


def _build_semester_rows(
    semester_key: str, overall: float, core: float,
) -> list[Dict[str, Any]]:
    """학기 하나에 대한 과목별 행 생성."""
    import random

    n_total = len(DEFAULT_SUBJECTS)
    core_indices = [
        i for i, s in enumerate(DEFAULT_SUBJECTS)
        if s["curriculum"] in CORE_CURRICULUMS
    ]
    non_core_indices = [i for i in range(n_total) if i not in core_indices]
    n_core = len(core_indices)
    n_non_core = len(non_core_indices)

    sum_total = round(overall * n_total)
    sum_core = round(core * n_core)
    sum_non_core = sum_total - sum_core if n_non_core > 0 else 0

    core_grades = _allocate_grades(n_core, sum_core)
    non_core_grades = _allocate_grades(n_non_core, sum_non_core)

    rows: list[Dict[str, Any]] = []
    ci, ni = 0, 0
    for i, subj in enumerate(DEFAULT_SUBJECTS):
        is_core = i in core_indices
        grade = core_grades[ci] if is_core else non_core_grades[ni]
        grade = max(1, min(9, grade))
        if is_core:
            ci += 1
        else:
            ni += 1
        raw_score = RAW_SCORE_BY_CLASS_RANK.get(grade, 80)
        uid = f"{semester_key}-{i}-{random.randint(1000, 9999)}"
        rows.append({
            "id": uid,
            "trackType": subj["trackType"],
            "curriculum": subj["curriculum"],
            "subject": subj["subject"],
            "credits": subj["credits"],
            "classRank": str(grade),
            "rawScore": str(raw_score),
            "avgScore": "",
            "stdDev": "",
            "studentCount": "",
            "achievement": "선택",
            "distA": "",
            "distB": "",
            "distC": "",
        })
    return rows


def _build_naesin_candidate(
    semester_map: Dict[str, tuple],
) -> NaesinCandidate:
    """학기별 (overall, core) 맵 → NaesinCandidate + school_grade_input 생성."""
    semester_averages: Dict[str, Any] = {}
    semesters: Dict[str, Any] = {}

    for sk in SEMESTER_KEYS:
        ov, co = semester_map[sk]
        semester_averages[sk] = {"overall": _fmt_grade(ov), "core": _fmt_grade(co)}
        semesters[sk] = _build_semester_rows(sk, ov, co)

    all_ov = [semester_map[sk][0] for sk in SEMESTER_KEYS]
    all_co = [semester_map[sk][1] for sk in SEMESTER_KEYS]
    overall_avg = round(sum(all_ov) / len(all_ov), 2)
    core_avg = round(sum(all_co) / len(all_co), 2)

    school_grade_input: Dict[str, Any] = {
        "semesters": semesters,
        "gradeSummary": {
            "overallAverage": _fmt_grade(overall_avg),
            "coreAverage": _fmt_grade(core_avg),
            "semesterAverages": semester_averages,
        },
        "hasReportCardData": False,
        "extracurricular": {
            "attendance": {
                "1": {"absence": "", "tardy": "", "earlyLeave": "", "result": ""},
                "2": {"absence": "", "tardy": "", "earlyLeave": "", "result": ""},
                "3": {"absence": "", "tardy": "", "earlyLeave": "", "result": ""},
            },
            "volunteerHours": {"1": "", "2": "", "3": ""},
        },
        "recordUpload": {"fileName": "", "summary": ""},
    }

    return NaesinCandidate(
        has_candidate=True,
        overall_average=overall_avg,
        core_average=core_avg,
        school_grade_input=school_grade_input,
    )


def build_school_grade_input_from_card(
    overall_average: str,
    core_average: str,
    semester_averages: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    """
    내신 카드에서 수정된 값(문자열)으로 school_grade_input 구조를 생성.
    프론트엔드 continue-after-naesin 요청의 grade_summary에 대응.
    """
    def parse_grade(s: Any) -> float:
        if s is None or s == "":
            return 2.5
        try:
            v = float(s)
            return round(max(1.0, min(9.0, v)), 2)
        except (TypeError, ValueError):
            return 2.5

    ov_global = parse_grade(overall_average)
    co_global = parse_grade(core_average)
    semester_map: Dict[str, tuple] = {}
    for sk in SEMESTER_KEYS:
        sa = semester_averages.get(sk) or {}
        ov = parse_grade(sa.get("overall")) if sa.get("overall") not in (None, "") else ov_global
        co = parse_grade(sa.get("core")) if sa.get("core") not in (None, "") else co_global
        semester_map[sk] = (ov, co)
    candidate = _build_naesin_candidate(semester_map)
    return candidate.school_grade_input


def extract_naesin_candidate(message: str) -> NaesinCandidate:
    """채팅 메시지에서 수시/내신 등급을 LLM으로 추출해 school_grade_input 구조를 생성."""
    empty = NaesinCandidate(
        has_candidate=False,
        overall_average=0.0,
        core_average=0.0,
        school_grade_input={},
    )
    if not message:
        return empty

    semester_map = _parse_naesin_with_llm(message)
    if not semester_map:
        return empty

    return _build_naesin_candidate(semester_map)
