from __future__ import annotations

import asyncio
import ast
import json
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from config.config import settings
from config.constants import GEMINI_FLASH_MODEL
from services.multi_agent.functions import execute_function_calls
from services.multi_agent.router_agent import RouterAgent
from school_record_eval.matching_summary import ensure_matching_summary

genai.configure(api_key=settings.GEMINI_API_KEY)


SYSTEM_PROMPT = """당신은 고교 생활기록부 분석 전용 에이전트다.

[핵심 원칙]
1) 반드시 제공된 생기부 원문/파싱 텍스트를 우선 근거로 사용한다.
2) 데이터에 없는 사실은 절대 만들지 않는다.
3) 숫자 점수화/등급화 대신, 근거 기반 서술형 보고서로 작성한다.
4) 사용자가 특정 대학(예: 중앙대) 기준을 요청하면, 함께 제공된 RAG 참고자료의 평가 항목/표현을 반영한다.
5) 세특 분석에서는 반드시 계기-심화-역량-변화(인과관계)를 점검한다.
6) 질문에 특정 대학명이 포함되면 공통 기준 설명은 출력하지 않고, 대학별 공식 기준만 사용한다.
7) 각 기준마다 "무엇이 적합했고 무엇이 미흡했는지"를 원문 근거로 제시한다.

[공통 평가기준(일반 질문일 때만 적용)]
- 학업역량: 학업성취도, 학업태도, 탐구력
- 진로역량: 전공(계열) 관련 교과 이수 노력, 전공(계열) 관련 교과 성취도, 진로 탐색 활동과 경험
- 공동체역량: 협업과 소통능력, 나눔과 배려, 성실성과 규칙준수, 리더십

[하이라이트 규칙 - 반드시 준수]
- 근거 원문은 반드시 아래 cite 태그 형식으로 감싸라:
  <cite data-source="적합|기준명|대학별 공통 기준/학교별" data-url="가능하면 URL">원문 발췌</cite>
  <cite data-source="미흡|기준명|대학별 공통 기준/학교별" data-url="가능하면 URL">원문 발췌</cite>
- 위 형식이 아니면 하이라이트로 인정되지 않는다.
- 공통 기준 근거라면 3번째 항목을 반드시 '대학별 공통 기준'으로 표기한다.
- "미흡"이 '정보 부재'인 경우도 가능한 한 관련 원문 일부를 cite로 제시하고, 정말 없으면 "원문 근거 없음(미기재)"라고 명시한다.
- 과장된 재해석 금지. 원문에 없는 활동/성과를 만들어 쓰지 말라.

[출력 형식 - 섹션 제목 고정]
아래 섹션 제목을 정확히 유지하고, 각 섹션 내용을 채워라.

# 0. 평가기준 설명
## 0-1. 공통 기준 설명
- 공통 기준 10개를 설명하고, 이번 답변에서 왜 중요한 기준인지 간단히 연결해 설명한다.
- 근거 문장은 cite 태그를 사용한다.
## 0-2. 학교별 기준 설명
- 학교별 기준이 적용되면 기준명/출처문서/적합근거/미흡근거를 정리한다.
- 학교별 기준이 없으면 "학교별 기준 미적용(요청 없음 또는 근거 문서 없음)"을 명시한다.

# 1. 기준별 적용 평가(사용자 생기부 기반)
- 각 평가기준마다 "적합한 점 / 미흡한 점"을 반드시 짝으로 제시한다.
- 가능한 한 원문 근거를 cite 태그로 삽입하여 평가 근거를 명확히 보여준다.

# 2. 전반 진단
- 생기부 전체 인상, 강점 축, 보완 축을 근거와 함께 설명

# 3. 학년별 분석
- 1학년/2학년/3학년의 변화 흐름과 일관성, 심화 정도

# 4. 핵심 역량 분석
- 학업역량, 진로역량, 공동체역량을 각각 근거 문장과 함께 설명

# 5. 단계별 상세 분석(요청한 보고서 구조 반영)
- 교과세특(과세특), 개별세특/활동기록, 비교과(출결/봉사/창체/행동특성 등)를 분리해 분석한다.
- 각 단계마다 "적합 요소 / 미흡 요소 / 보완 제안"을 근거와 함께 제시한다.
- 반드시 아래 하위 섹션을 포함한다:
  - ## 5-1. 교과세특(과세특)
  - ## 5-2. 개별세특/활동기록 (창체)
  - ## 5-3. 비교과(출결/봉사/행동특성)

[5-2 출력 스타일(강제)]
- '개조식 체크리스트'가 아니라 '리포트 문단형'으로 작성한다.
- 각 소주제는 아래 순서를 따른다.
  1) 제목 한 줄
  2) 소제목 한 줄
  3) 본문 2~4개 문단(문장 길이 충분히 길게)
- 문단은 자연스러운 서술형으로 이어 쓰고, 불필요한 표/짧은 불릿 나열을 피한다.
- 해당 소주제의 적합/미흡 근거는 문단 안에 cite 태그로 삽입한다.
- 사용자가 기대하는 "딥리서치 보고서"처럼 맥락-해석-시사점 흐름으로 쓴다.

[학년별·과목별 세특 확장 규칙(강제)]
- #5 섹션에서는 학년별/과목별 세특 평가를 충분히 길고 깊게 작성한다.
- 세특 원문에 보이는 과목 항목을 가능한 빠짐없이 다루고, 누락 과목은 "원문 근거 부족"으로 명시한다.
- 과목별 단락마다 최소 아래 5요소를 포함한다:
  1) 핵심 관찰
  2) 적합 근거(cite)
  3) 미흡 근거(cite 또는 미기재 명시)
  4) 계기-심화-역량-변화 진단
  5) 보완 제안
- 문장을 짧게 끊지 말고 설명형 문단으로 충분히 길게 작성한다.
- 세특 원문 인용은 반드시 `<cite ...>원문</cite>` 안에서만 사용하고, 원문만 단독으로 연속 나열하지 않는다.
- 각 과목 단락은 반드시 "평가/해석 문장"으로 시작하고, 원문 인용(cite)은 1~2문장 길이로 필요한 부분만 발췌한다.
- `<cite ...>`의 `data-url` 속성 값은 줄바꿈 없이 한 줄 URL로만 출력한다.

# 6. 지원 전략 제안
- 학생부종합전형 관점에서 서류 강점 활용 포인트
- 면접/자소서(또는 추가서류)에서 강조할 서술 관점
- 요청된 대학 기준이 있으면 해당 기준 중심으로 재해석

# 7. 한계와 추가 확인 포인트
- 현재 자료로 단정 어려운 지점
- 추가로 확보하면 정확도가 오를 자료

[근거 표기]
- 각 주요 주장 끝에 (근거: ...) 형태로 실제 근거를 간단히 붙인다.
- 외부 RAG 근거를 사용하면 (외부근거: 문서명/페이지) 형태로 명시한다.

[분량]
- 간결 요약이 아니라 실제 심층 보고서처럼 충분히 상세하게 작성한다.
"""

_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

MAX_RAG_CONTEXT_CHARS = 30000
MAX_HISTORY_TURNS = 8
STREAM_CHUNK_SIZE = 180
REPORT_MODE_GENERAL = "general"
REPORT_MODE_FOCUSED = "focused"
MAX_FOLLOW_UP_QUESTIONS = 4
MAX_RETRIEVAL_ROUNDS = 3
MAX_UNIVERSITY_EXPANSION = 3
MAX_QUERIES_PER_UNIVERSITY = 4
MAX_CALLS_PER_ROUND = 18
MAX_TOTAL_RETRIEVAL_CALLS = 42
MAX_PARALLEL_FUNCTION_CALLS = 10

UNIVERSITY_ALIAS_MAP: Dict[str, List[str]] = {
    "서울대학교": ["서울대학교", "서울대", "서울대학"],
    "연세대학교": ["연세대학교", "연세대", "연대"],
    "고려대학교": ["고려대학교", "고려대", "고대"],
    "중앙대학교": ["중앙대학교", "중앙대"],
    "성균관대학교": ["성균관대학교", "성균관대", "성대"],
    "한양대학교": ["한양대학교", "한양대"],
    "경희대학교": ["경희대학교", "경희대"],
    "서강대학교": ["서강대학교", "서강대"],
    "이화여자대학교": ["이화여자대학교", "이화여대", "이대"],
    "한국외국어대학교": ["한국외국어대학교", "한국외대", "외대"],
    "서울시립대학교": ["서울시립대학교", "시립대", "서울시립대"],
}

# 생기부 기반 적합 학교 추천 시 순회할 후보 대학 목록
CANDIDATE_UNIVERSITIES: List[str] = list(UNIVERSITY_ALIAS_MAP.keys())
MAX_MATCHING_SCHOOLS = 8
MATCHING_CRITERIA_QUERY = "학생부종합전형 인재상 서류평가기준 평가요소"


def _is_school_recommendation_request(message: str) -> bool:
    """생기부 기반으로 적합한 학교/전공 추천을 요청하는 쿼리인지 판별."""
    text = _clean_text(message)
    if not text or len(text) < 3:
        return False
    # 추천 요청 의도: 학교/대학/전공 + 추천·적합 관련 표현
    school_related = any(s in text for s in ("학교", "대학", "전공", "학과"))
    recommendation_signals = [
        "적합한 학교",
        "적합한 대학",
        "맞는 학교",
        "맞는 대학",
        "어울리는 학교",
        "어울리는 대학",
        "추천해줘",
        "추천해 주세요",
        "추천해주세요",
        "추천해줘요",
        "학교 추천",
        "대학 추천",
        "전공 추천",
        "어떤 학교",
        "어떤 대학",
        "갈 만한",
        "갈만한",
        "지원할 만한",
    ]
    if any(s in text for s in recommendation_signals):
        return True
    if school_related and ("추천" in text or "적합" in text):
        return True
    return False


async def _find_matching_schools(
    matching_summary: str,
    candidate_schools: List[str],
) -> List[str]:
    """
    매칭용 요약과 후보 대학 목록으로, 각 대학의 평가기준을 RAG로 가져온 뒤
    LLM으로 적합한 학교를 선정하여 반환. (기존 방식으로 상세 분석할 target_universities)
    """
    if not matching_summary or not candidate_schools:
        return []

    # 1) 각 후보 대학별로 평가기준 RAG 1회씩 호출
    calls = [
        {
            "function": "univ",
            "params": {
                "university": uni,
                "query": f"2026학년도 {uni} {MATCHING_CRITERIA_QUERY}",
            },
        }
        for uni in candidate_schools[:12]
    ]
    try:
        results = await _execute_function_calls_parallel(calls)
    except Exception as e:
        print(f"⚠️ _find_matching_schools RAG 실패: {e}")
        return []

    # 2) 대학별로 청크 텍스트 합치기 (최대 N자)
    per_school_max_chars = 1200
    school_to_criteria: Dict[str, str] = {}
    for idx, uni in enumerate(candidate_schools[:12]):
        key = f"univ_{idx}"
        data = results.get(key) if isinstance(results, dict) else {}
        chunks = (data.get("chunks") or []) if isinstance(data, dict) else []
        parts = []
        total = 0
        for c in chunks:
            if isinstance(c, dict) and c.get("content"):
                part = (c.get("content") or "").strip()
                if part and total + len(part) <= per_school_max_chars:
                    parts.append(part)
                    total += len(part)
        school_to_criteria[uni] = "\n".join(parts).strip() or "(해당 대학 평가기준 자료 없음)"

    # 3) LLM: 요약 + 대학별 기준을 보고 적합한 학교만 JSON 배열로 반환
    model = genai.GenerativeModel(model_name=GEMINI_FLASH_MODEL)
    criteria_block = "\n\n".join(
        f"[{uni}]\n{text[:800]}" for uni, text in school_to_criteria.items()
    )
    prompt = f"""다음은 한 학생의 생기부 매칭용 요약과, 여러 대학의 학생부종합 평가기준 요약입니다.
이 학생에게 **가장 적합한 대학**을 최대 {MAX_MATCHING_SCHOOLS}개 골라, 대학명만 JSON 배열로 출력하세요.
반드시 아래 [대학 목록]에 있는 정확한 대학명만 사용하고, 다른 텍스트는 출력하지 마세요.

[학생 생기부 매칭용 요약]
{matching_summary[:2000]}

[대학별 평가기준 요약]
{criteria_block[:12000]}

[대학 목록] (이 이름만 사용)
{json.dumps(candidate_schools[:12], ensure_ascii=False)}

[출력 형식] JSON 배열만, 예: ["연세대학교", "고려대학교", "중앙대학교"]
"""

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=256,
            ),
            safety_settings=_SAFETY_SETTINGS,
        )
        raw = (getattr(response, "text", None) or "").strip()
        # JSON 배열 추출
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            arr = json.loads(raw[start:end])
            if isinstance(arr, list):
                out = [x for x in arr if isinstance(x, str) and x.strip() and x in candidate_schools]
                return out[:MAX_MATCHING_SCHOOLS]
    except Exception as e:
        print(f"⚠️ _find_matching_schools LLM 파싱 실패: {e}")
    return []


def _clean_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


async def _execute_function_calls_parallel(
    function_calls: List[Dict[str, Any]],
    *,
    max_concurrency: int = MAX_PARALLEL_FUNCTION_CALLS,
) -> Dict[str, Any]:
    """
    function call을 제한된 병렬성으로 실행.
    - 결과 키는 `<function>_<원래 인덱스>` 형태로 고정해 기존 접근 방식을 유지
    - 품질 유지: 호출 내용/결과는 동일, 실행 순서만 병렬화
    """
    if not function_calls:
        return {}

    semaphore = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def _run_single(idx: int, call: Dict[str, Any]) -> Tuple[int, str, Any]:
        func_name = str((call or {}).get("function") or "call").strip() or "call"
        result_key = f"{func_name}_{idx}"
        try:
            async with semaphore:
                partial = await execute_function_calls([call])
            if isinstance(partial, dict) and partial:
                value = next(iter(partial.values()))
            else:
                value = {"error": "empty function result"}
        except Exception as e:
            value = {"error": str(e)}
        return idx, result_key, value

    gathered = await asyncio.gather(
        *[_run_single(idx, call) for idx, call in enumerate(function_calls)],
        return_exceptions=False,
    )

    out: Dict[str, Any] = {}
    for _, key, value in sorted(gathered, key=lambda x: x[0]):
        out[key] = value
    return out


def _clean_generated_text(text: Any) -> str:
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""

    # 지나친 연속 줄바꿈만 정리하고 문단/구조는 유지
    raw = re.sub(r"\n{4,}", "\n\n\n", raw)
    # 헤더가 불릿으로 깨진 경우 복원: "* ## 0-1..." -> "## 0-1..."
    raw = re.sub(r"(?m)^\s*[*-]\s*(#{1,4}\s+)", r"\1", raw)
    # 문장 끝 뒤에 섹션 마커가 붙은 경우 줄바꿈 삽입
    heading_token = r"(?:#{1,4}\s+|\d+[-–—]\d+\.\s+|\d+\.\s+[가-힣A-Za-z])"
    raw = re.sub(rf"([.!?])\s*(?={heading_token})", r"\1\n", raw)
    # cite 종료 직후 섹션 마커가 이어 붙는 경우 줄바꿈 삽입
    raw = re.sub(rf"(</cite>)\s*(?={heading_token})", r"\1\n", raw, flags=re.IGNORECASE)
    # 줄 단위로 깨진 cite 태그 복구:
    # - 줄 끝에서 끊긴 `<cite ...` 조각 제거
    # - `<cite ...>`는 있는데 `</cite>`가 없으면 해당 줄 끝에 자동 닫기
    repaired_lines: List[str] = []
    for line in raw.split("\n"):
        fixed = re.sub(r"<cite\b[^\n>]*$", "", line, flags=re.IGNORECASE)
        open_count = len(re.findall(r"<cite\b[^>]*>", fixed, flags=re.IGNORECASE))
        close_count = len(re.findall(r"</cite>", fixed, flags=re.IGNORECASE))
        if open_count > close_count:
            fixed = fixed + "</cite>"
        repaired_lines.append(fixed)
    raw = "\n".join(repaired_lines)
    # cite 오픈 태그 내부 개행/과도한 공백을 정리해 프론트 파싱 안정성 향상
    raw = re.sub(
        r"<cite\b[^>]*>",
        lambda m: re.sub(r"\s{2,}", " ", m.group(0).replace("\n", " ").replace("\r", " ")).strip(),
        raw,
        flags=re.IGNORECASE,
    )
    return raw


def _sanitize_broken_table_lines(text: str) -> str:
    """
    LLM이 잘못 생성한 깨진 markdown table 라인(| : | : | ...) 제거.
    정상 문장/정상 표 헤더는 유지하고, 의미 없는 구분자 줄만 제거한다.
    """
    if not text:
        return text
    lines = text.splitlines()
    cleaned: List[str] = []
    for line in lines:
        stripped = line.strip()
        # 예: | : | : | : | 형태의 깨진 정렬 라인 제거
        if re.match(r"^\|(?:\s*:\s*\|)+\s*$", stripped):
            continue
        # 예: | : | 또는 | : 처럼 정보 없는 라인 제거
        if re.match(r"^\|\s*[:|]+\s*\|?\s*$", stripped):
            continue
        cleaned.append(line)
    out = "\n".join(cleaned)
    out = re.sub(r"\n{4,}", "\n\n\n", out).strip()
    return out


def _sanitize_prompt_leakage(text: str) -> str:
    """
    모델이 내부 지시문/체크리스트/자기점검 문구를 그대로 출력한 경우 정리.
    """
    if not text:
        return text

    out = str(text)
    # 헤더가 불릿으로 깨진 경우 복원: "* # 0. ..." -> "# 0. ..."
    out = re.sub(r"(?m)^\s*[*-]\s*(#{1,4}\s+)", r"\1", out)

    banned_patterns = [
        r"(?im)^\s*think\s*$",
        r"(?im)^\s*[*-]?\s*Check\s*:\s*.*$",
        r"(?im)^\s*[*-]?\s*Self-?Correction.*$",
        r"(?im)^\s*당신은 고교 생활기록부 분석 전용 에이전트.*$",
        r"(?im)^\s*제공된 .*생활기록부.*보고서.*작성.*$",
        r"(?im)^\s*\[작성 지침\].*$",
        r"(?im)^\s*\[출력 모드\].*$",
        r"(?im)^\s*\[필수 섹션 - 제목 고정\].*$",
        r"(?im)^\s*[*-]\s*cite 태그 형식.*$",
        r"(?im)^\s*[*-]\s*섹션 제목 고정.*$",
    ]
    for pattern in banned_patterns:
        out = re.sub(pattern, "", out)

    # 내부 지시성 불릿 라인 정리
    noisy_line_signals = [
        "공통 기준 설명 제외",
        "숫자 점수화 대신",
        "계기-심화-역량-변화",
        "서울대 공식 기준(RAG 자료) 반영",
        "cite 태그 형식 준수",
    ]
    cleaned_lines: List[str] = []
    for line in out.splitlines():
        raw = line.strip()
        if not raw:
            cleaned_lines.append(line)
            continue
        if any(signal in raw for signal in noisy_line_signals) and raw.startswith(("*", "-", "•")):
            continue
        cleaned_lines.append(line)

    out = "\n".join(cleaned_lines)
    out = re.sub(r"\n{4,}", "\n\n\n", out).strip()
    return out


def _detect_report_mode(message: str) -> str:
    text = _clean_text(message)
    if not text:
        return REPORT_MODE_GENERAL

    focused_signals = [
        "면접",
        "예상질문",
        "예상 질문",
        "질문 리스트",
        "답변 포인트",
        "답변 전략",
        "자소서",
        "자기소개서",
        "지원동기",
        "1분 자기소개",
        "대학별",
        "전형별",
        "특정 과목",
        "한 과목",
        "한 활동",
        "창체만",
        "공통 기준 빼고",
    ]
    if any(signal in text for signal in focused_signals):
        return REPORT_MODE_FOCUSED

    general_signals = [
        "전반",
        "전체",
        "종합",
        "공통 기준",
        "학년별",
        "심층 보고서",
        "전체 평가",
        "전체 분석",
    ]
    if any(signal in text for signal in general_signals):
        return REPORT_MODE_GENERAL

    return REPORT_MODE_GENERAL


def _build_mode_output_instructions(mode: str, target_universities: List[str] | None = None) -> str:
    has_university_focus = bool(target_universities)

    if has_university_focus and mode == REPORT_MODE_FOCUSED:
        return """[출력 모드]
집중형 모드(특정 대학 지정)로 작성한다.

[필수 섹션 - 제목 고정]
# 0. 학교별 평가기준 설명
- 지정 대학의 공식 인재상/평가요소/전형 핵심만 설명한다.
- 공통 기준 설명은 출력하지 않는다.

# 1. 대학별 기준 적용 평가(이번 질문 범위)
- 각 대학마다 적합/미흡을 짝으로 제시하고 cite 근거를 붙인다.

# 2. 요청 주제 집중 분석
- 사용자가 요구한 목적(예: 면접 대비)을 대학별 기준 중심으로 분석한다.

# 3. 실행안 및 다음 액션
- 대학별로 바로 실행 가능한 서류/면접 액션을 분리해 제시한다.
"""

    if has_university_focus:
        return """[출력 모드]
전체형 모드(특정 대학 지정)로 작성한다.

[필수 섹션 - 제목 고정]
# 0. 학교별 평가기준 설명
# 1. 대학별 기준 적용 평가(사용자 생기부 기반)
# 2. 대학별 비교 분석
# 3. 학년별 분석
# 4. 단계별 상세 분석(요청한 보고서 구조 반영)
## 4-1. 교과세특(과세특)
## 4-2. 개별세특/활동기록 (창체)
## 4-3. 비교과(출결/봉사/행동특성)
# 5. 대학별 지원 전략 제안
# 6. 한계와 추가 확인 포인트

[강제]
- 공통 기준 설명은 출력하지 않는다.
- markdown 표 형식('|', '|---|')은 사용하지 않는다.
- #2 '대학별 비교 분석'은 표 대신 소제목+문단/불릿으로 작성한다.
- 프롬프트 문장/체크리스트/자기점검(Check, Self-Correction)/'think' 문자열은 출력하지 않는다.
"""

    if mode == REPORT_MODE_FOCUSED:
        return """[출력 모드]
집중형 모드(면접/세부 요청)로 작성한다.

[필수 섹션 - 제목 고정]
# 0. 평가기준 설명(이번 답변 적용 기준)
- 공통/학교별 기준 중 이번 요청과 직접 관련된 항목만 간단히 설명한다.

# 1. 기준별 적용 평가(이번 질문 범위)
- 각 기준마다 적합/미흡을 짝으로 제시하고 cite 근거를 붙인다.

# 2. 요청 주제 집중 분석
- 사용자가 요구한 세부 목적(예: 면접 대비)을 중심으로 심층 분석한다.
- 불필요한 전반 개요는 생략한다.

# 3. 실행안 및 다음 액션
- 바로 실행 가능한 답변/연습/보완안 중심으로 정리한다.

[주의]
- 아래 전체형 섹션은 출력하지 않는다:
  '# 2. 전반 진단', '# 3. 학년별 분석', '# 5. 단계별 상세 분석(요청한 보고서 구조 반영)' 등
- 프롬프트 문장/체크리스트/자기점검(Check, Self-Correction)/'think' 문자열은 출력하지 않는다.
"""

    return """[출력 모드]
전체형 모드(전반 생기부 분석)로 작성한다.

[필수 섹션 - 제목 고정]
# 0. 평가기준 설명
# 1. 기준별 적용 평가(사용자 생기부 기반)
# 2. 전반 진단
# 3. 학년별 분석
# 4. 핵심 역량 분석
# 5. 단계별 상세 분석(요청한 보고서 구조 반영)
## 5-1. 교과세특(과세특)
## 5-2. 개별세특/활동기록 (창체)
## 5-3. 비교과(출결/봉사/행동특성)
# 6. 지원 전략 제안
# 7. 한계와 추가 확인 포인트

[출력 금지]
- 프롬프트 문장/체크리스트/자기점검(Check, Self-Correction)/'think' 문자열
"""


def _parse_follow_up_questions(raw_text: str) -> List[str]:
    text = (raw_text or "").strip()
    if not text:
        return []

    def _sanitize_question(item: Any) -> str:
        q = str(item or "").strip()
        q = re.sub(r'^[\s"\']+', "", q)
        q = re.sub(r'[\s"\']+$', "", q)
        q = re.sub(r"^\[+", "", q).strip()
        q = re.sub(r"\]+$", "", q).strip()
        q = re.sub(r"^,+", "", q).strip()
        q = re.sub(r",+$", "", q).strip()
        q = re.sub(r'^[\s"\']+', "", q)
        q = re.sub(r'[\s"\']+$', "", q)
        q = re.sub(r'^\\+"+', "", q).strip()
        if not q:
            return ""
        if q.startswith(("질문", "Q1", "Q2", "Q3", "Q4")) and ":" in q:
            q = q.split(":", 1)[1].strip()
        if not q.endswith("?"):
            q = q.rstrip(".") + "?"
        return q

    # 1) JSON 배열 우선 파싱
    try:
        parsed = json.loads(text)
    except Exception:
        try:
            parsed = ast.literal_eval(text)
        except Exception:
            parsed = None
    try:
        if isinstance(parsed, list):
            cleaned = [_sanitize_question(x) for x in parsed]
            out = []
            seen = set()
            for item in cleaned:
                if not item:
                    continue
                if item in seen:
                    continue
                seen.add(item)
                out.append(item)
                if len(out) >= MAX_FOLLOW_UP_QUESTIONS:
                    break
            return out
    except Exception:
        pass

    # 2) 줄 단위 파싱 폴백
    out: List[str] = []
    seen = set()
    for line in text.splitlines():
        line = re.sub(r"^\s*[-*•\d\)\.\]]+\s*", "", line).strip()
        line = _sanitize_question(line)
        if not line:
            continue
        if len(line) < 2:
            continue
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
        if len(out) >= MAX_FOLLOW_UP_QUESTIONS:
            break
    return out


def _fallback_follow_up_questions(mode: str) -> List[str]:
    if mode == REPORT_MODE_FOCUSED:
        return [
            "내 생기부 기준으로 실제 면접에서 가장 먼저 나올 질문 5개만 뽑아줄래?",
            "방금 분석에서 미흡하다고 본 항목을 면접 답변으로 어떻게 방어하면 좋을까?",
            "지원 대학 기준에 맞춰 1분 자기소개를 근거 문장 중심으로 만들어줄래?",
            "오늘부터 4주 동안 면접 대비를 하려면 주차별로 무엇을 준비해야 할까?",
        ]
    return [
        "내 생기부에서 가장 경쟁력 있는 전공/학과 조합 3개를 근거와 함께 추천해줄래?",
        "이번 분석 기준으로 약점 3가지를 3개월 안에 보완하는 실행계획을 짜줄래?",
        "세특을 계기-심화-역량-변화 구조로 다시 쓰려면 어떤 과목부터 손보는 게 좋을까?",
        "면접에서 이어질 꼬리질문을 내 실제 활동 근거 중심으로 만들어줄래?",
    ]


def _complete_follow_up_questions(questions: List[str], mode: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for q in (questions or []) + _fallback_follow_up_questions(mode):
        text = _clean_text(q)
        if not text:
            continue
        if not text.endswith("?"):
            text = text.rstrip(".") + "?"
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= MAX_FOLLOW_UP_QUESTIONS:
            break
    return out


async def _generate_follow_up_questions(
    *,
    message: str,
    report_text: str,
    mode: str,
) -> List[str]:
    model = genai.GenerativeModel(model_name=GEMINI_FLASH_MODEL)
    prompt = f"""아래 사용자 질문과 보고서를 참고해, 사용자가 바로 이어서 물어보면 좋은 '꼬리 질문' 4개를 만드세요.

[사용자 질문]
{_clean_text(message)}

[보고서 일부]
{(report_text or "")[:3000]}

[작성 조건]
- 한국어 질문문 정확히 4개
- GPT의 추천 질문처럼 짧고 자연스럽게
- 보고서에 등장한 대학/과목/활동 키워드를 반드시 반영
- 서로 중복되지 않게
- 과도하게 일반론적인 질문(예: FTA, 거시경제 일반론) 금지
- 반드시 JSON 배열 문자열만 출력 (예: ["질문1?", "질문2?", ...])
"""
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=512,
            ),
            safety_settings=_SAFETY_SETTINGS,
        )
        parsed = _parse_follow_up_questions(_clean_generated_text(getattr(response, "text", "")))
        if parsed:
            return _complete_follow_up_questions(parsed[:MAX_FOLLOW_UP_QUESTIONS], mode)
    except Exception:
        pass
    return _complete_follow_up_questions([], mode)


def _append_follow_up_section(report_text: str, questions: List[str]) -> str:
    q = [item.strip() for item in (questions or []) if str(item).strip()]
    if not q:
        return report_text
    lines = ["## 답변 후 꼬리 질문", ""]
    for idx, item in enumerate(q[:MAX_FOLLOW_UP_QUESTIONS], start=1):
        lines.append(f"{idx}. {item}")
    return f"{(report_text or '').rstrip()}\n\n" + "\n".join(lines)


async def _generate_subject_deep_dive(
    *,
    message: str,
    school_record_context: str,
    mode: str,
) -> str:
    model = genai.GenerativeModel(model_name=GEMINI_FLASH_MODEL)
    prompt = f"""아래 생기부 컨텍스트를 바탕으로 학년별·과목별 세특 확장 분석을 작성하세요.

[사용자 질문]
{_clean_text(message)}

[분석 모드]
{mode}

[생기부 컨텍스트]
{school_record_context}

[출력 형식 - 그대로]
## 부록 A. 학년별 과목 세특 확장 평가
### 1학년
#### 과목명
(긴 설명형 문단, 적합/미흡 근거 cite 포함)

### 2학년
#### 과목명
(긴 설명형 문단, 적합/미흡 근거 cite 포함)

### 3학년
#### 과목명
(긴 설명형 문단, 적합/미흡 근거 cite 포함)

[강제 규칙]
- 가능한 과목을 빠짐없이 포함한다.
- 과목별로 최소 4문장 이상 작성한다.
- 각 과목 단락에 적합/미흡 근거를 모두 포함한다.
- 근거는 가능한 한 아래 형식으로 삽입:
  <cite data-source="적합|기준명|대학별 공통 기준/학교별" data-url="">원문 발췌</cite>
  <cite data-source="미흡|기준명|대학별 공통 기준/학교별" data-url="">원문 발췌</cite>
- 공통 기준 근거는 3번째 항목을 반드시 '대학별 공통 기준'으로 표기한다.
- 설명이 짧아지지 않도록 깊이 있게 서술한다.
- 원문 인용은 cite 안에만 넣고, 원문만 단독으로 이어붙이지 말고 반드시 해석/평가 문장과 섞어 작성한다.
- `data-url` 속성은 줄바꿈 없는 한 줄 URL만 사용한다.
"""
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=8192,
            ),
            safety_settings=_SAFETY_SETTINGS,
        )
        text = _clean_generated_text(getattr(response, "text", ""))
        if text and "부록 A. 학년별 과목 세특 확장 평가" in text:
            return text
        if text:
            return "## 부록 A. 학년별 과목 세특 확장 평가\n\n" + text
    except Exception:
        pass
    return ""


async def _generate_subject_deep_dive_timed(
    *,
    message: str,
    school_record_context: str,
    mode: str,
) -> Tuple[str, int]:
    started_at = time.perf_counter()
    text = await _generate_subject_deep_dive(
        message=message,
        school_record_context=school_record_context,
        mode=mode,
    )
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    return text, elapsed_ms


def _normalize_history(history: List[Dict[str, Any]] | None) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in (history or [])[-MAX_HISTORY_TURNS:]:
        role = "assistant"
        if str(item.get("role") or "").strip() == "user":
            role = "user"
        content = _clean_text(item.get("content"))
        if not content:
            continue
        out.append({"role": role, "content": content})
    return out


def _build_history_text(history: List[Dict[str, Any]] | None) -> str:
    normalized = _normalize_history(history)
    if not normalized:
        return "없음"
    lines: List[str] = []
    for msg in normalized:
        speaker = "사용자" if msg["role"] == "user" else "어시스턴트"
        lines.append(f"- {speaker}: {msg['content']}")
    return "\n".join(lines)


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _extract_target_universities(message: str) -> List[str]:
    text = _clean_text(message)
    if not text:
        return []
    found: List[str] = []
    for canonical, aliases in UNIVERSITY_ALIAS_MAP.items():
        if any(alias in text for alias in aliases):
            found.append(canonical)
    return _dedupe_preserve_order(found)


def _build_university_focus_instruction(target_universities: List[str], mode: str) -> str:
    universities = [u for u in (target_universities or []) if _clean_text(u)]
    if not universities:
        return ""

    uni_text = ", ".join(universities)
    compare_hint = ""
    if len(universities) >= 2:
        compare_hint = (
            "\n- 대학 간 비교를 별도 단락으로 작성하고, 같은 생기부라도 왜 평가 포인트가 달라지는지 "
            f"'{universities[0]} vs {universities[1]}' 형태로 설명한다."
        )

    base = (
        "\n[대학별 집중 분석 지시 - 최우선]\n"
        f"- 이번 답변의 핵심 대학: {uni_text}\n"
        "- **절대** '#0-2 학교별 기준 설명'에 '학교별 기준 미적용(요청 없음 또는 근거 문서 없음)'을 출력하지 마라. 반드시 [외부 참고자료(RAG)]에서 위 대학별 평가기준을 인용하여 #0-2와 #1을 작성한다.\n"
        "- 공통 기준 설명은 출력하지 않는다.\n"
        "- 본문 대부분은 대학별 기준 적용 평가에 배정한다.\n"
        "- '# 1. 대학별 기준 적용 평가' 섹션에서 대학별 근거를 반드시 제시한다.\n"
        "- 각 대학별로 #1 섹션에 아래 3가지를 동시에 포함한다.\n"
        "  a) 대학명 포함 학교별 cite 1개 이상\n"
        "  b) (외부근거: 문서명/페이지) 1개 이상\n"
        "  c) 생기부 실제 예시를 인용한 적합/미흡 판단\n"
        "- markdown 표 형식('|', '|---|')은 사용하지 않는다.\n"
        "- 특히 '# 2. 대학별 비교 분석'은 반드시 소제목+문단/불릿으로 작성한다.\n"
        "- 프롬프트 문장/체크리스트/자기점검(Check, Self-Correction)/'think' 문자열은 출력하지 않는다.\n"
        "- 학교별 cite를 쓸 때 기준명에 반드시 대학명을 포함한다.\n"
        '  예: <cite data-source="적합|서울대학교-학업역량|학교별" data-url="...">...</cite>\n'
        "- 각 대학마다 최소 1개 이상 외부근거(문서명/페이지)를 명시한다.\n"
        "- 각 대학마다 아래 4가지를 반드시 모두 포함한다.\n"
        "  1) 공식 평가기준/인재상/전형 키워드(외부근거 기반)\n"
        "  2) 해당 대학 기준에서의 적합 근거(cite)\n"
        "  3) 해당 대학 기준에서의 미흡 근거(cite 또는 미기재 명시)\n"
        "  4) 지원 전략(서류/면접에서 강조할 포인트)\n"
        "- 외부 기준 문서를 찾지 못하면 '#1 섹션'에 '{대학명} 공식 기준 근거 문서 미확보'를 명시한다.\n"
        f"{compare_hint}\n"
    )

    if mode == REPORT_MODE_FOCUSED:
        base += (
            "- 집중형 모드에서는 대학별 분석을 먼저 제시하고, 실행 가능한 면접/서류 액션을 뒤에 배치한다.\n"
        )
    else:
        base += (
            "- 전체형 모드에서는 #0(학교별 평가기준), #1(대학별 기준 적용), #2(대학별 비교), #5(대학별 지원 전략)에서 "
            "대학별 내용을 명시적으로 분리해 작성한다.\n"
        )
    return base


def _find_missing_university_mentions(text: str, target_universities: List[str]) -> List[str]:
    out = (text or "").strip()
    if not target_universities:
        return []
    missing: List[str] = []
    for uni in target_universities:
        if _clean_text(uni) and uni not in out:
            missing.append(uni)
    return missing


def _build_university_alias_regex(university: str) -> str:
    aliases = UNIVERSITY_ALIAS_MAP.get(university, [university])
    escaped = [re.escape(_clean_text(alias)) for alias in aliases if _clean_text(alias)]
    if not escaped:
        escaped = [re.escape(_clean_text(university))]
    escaped = sorted(set(escaped), key=len, reverse=True)
    return "(?:" + "|".join(escaped) + ")"


def _extract_top_level_section(text: str, section_no: int) -> str:
    raw = text or ""
    start_match = re.search(rf"(?m)^#\s*{section_no}\.\s+.*$", raw)
    if not start_match:
        return ""

    start = start_match.start()
    tail = raw[start_match.end() :]
    next_match = re.search(r"(?m)^#\s*\d+\.\s+.*$", tail)
    end = start_match.end() + next_match.start() if next_match else len(raw)
    return raw[start:end].strip()


def _count_target_university_chunks(
    function_results: Dict[str, Any],
    target_universities: List[str],
) -> Dict[str, int]:
    counts: Dict[str, int] = {uni: 0 for uni in (target_universities or [])}
    if not counts:
        return counts

    for value in (function_results or {}).values():
        if not isinstance(value, dict):
            continue
        uni = _clean_text(value.get("university"))
        if uni not in counts:
            continue
        chunks = value.get("chunks")
        if isinstance(chunks, list):
            counts[uni] += len(chunks)
    return counts


def _find_university_evidence_gaps(
    text: str,
    target_universities: List[str],
    university_chunk_counts: Dict[str, int],
) -> Dict[str, List[str]]:
    if not target_universities:
        return {}
    out = text or ""
    section_zero = _extract_top_level_section(out, 0)
    section_one = _extract_top_level_section(out, 1)
    top_sections_text = f"{section_zero}\n\n{section_one}".strip()

    gaps: Dict[str, List[str]] = {}
    for uni in target_universities:
        alias_regex = _build_university_alias_regex(uni)
        has_uni_in_section_one = re.search(alias_regex, section_one) is not None
        has_school_cite_in_section_one = (
            re.search(
                rf'data-source="(?:적합|미흡)\|[^"]*{alias_regex}[^"]*\|학교별"',
                section_one,
            )
            is not None
        )
        has_external_in_section_one = (
            re.search(
                rf"(?:외부근거[^\\n)]{{0,200}}{alias_regex}|{alias_regex}[^\\n)]{{0,200}}외부근거)",
                section_one,
            )
            is not None
        )
        has_doc_unavailable_notice = (
            re.search(
                rf"(?:{alias_regex}[^\\n]{{0,80}}공식 기준 근거 문서 미확보|공식 기준 근거 문서 미확보[^\\n]{{0,80}}{alias_regex})",
                top_sections_text,
            )
            is not None
        )

        reasons: List[str] = []
        if not has_uni_in_section_one:
            reasons.append("#1 섹션에 대학명 명시")

        if university_chunk_counts.get(uni, 0) > 0:
            if not has_school_cite_in_section_one:
                reasons.append("#1 섹션에 대학명 포함 학교별 cite")
            if not has_external_in_section_one:
                reasons.append("#1 섹션에 외부근거(문서명/페이지)")
        elif not has_doc_unavailable_notice:
            reasons.append("#1 섹션에 공식 기준 근거 문서 미확보 명시")

        if reasons:
            gaps[uni] = reasons
    return gaps


def _collect_rag_material(function_results: Dict[str, Any]) -> Tuple[str, List[str], List[str], List[Dict[str, Any]]]:
    lines: List[str] = []
    sources: List[str] = []
    source_urls: List[str] = []
    used_chunks: List[Dict[str, Any]] = []
    seen_chunk_keys = set()
    total_chars = 0
    stop = False

    for value in (function_results or {}).values():
        if stop or not isinstance(value, dict):
            continue
        chunks = value.get("chunks") if isinstance(value.get("chunks"), list) else []
        document_titles = value.get("document_titles") if isinstance(value.get("document_titles"), dict) else {}
        document_urls = value.get("document_urls") if isinstance(value.get("document_urls"), dict) else {}
        base_university = _clean_text(value.get("university")) or "문서"

        for idx, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, dict):
                continue
            content = _clean_text(chunk.get("content"))
            if not content:
                continue

            document_id = chunk.get("document_id")
            chunk_id = chunk.get("chunk_id")
            title = _clean_text(document_titles.get(document_id)) or base_university
            url = _clean_text(document_urls.get(document_id) or chunk.get("file_url"))
            page = chunk.get("page_number")
            chunk_key = (
                f"{document_id}|{chunk_id}"
                if chunk_id not in (None, "")
                else f"{document_id}|{page}|{content[:120]}"
            )
            if chunk_key in seen_chunk_keys:
                continue
            seen_chunk_keys.add(chunk_key)

            source_label = f"{title} {page}p".strip() if page not in (None, "", 0) else title
            snippet = content[:700]
            block = (
                f"[근거 {len(lines) + 1}] 출처: {source_label}\n"
                f"URL: {url or '-'}\n"
                f"내용: {snippet}"
            )
            if total_chars + len(block) > MAX_RAG_CONTEXT_CHARS:
                stop = True
                break

            lines.append(block)
            total_chars += len(block)

            if url.startswith("http"):
                sources.append(source_label)
                source_urls.append(url)

            used_chunks.append(
                {
                    "id": str(chunk_id or f"chunk_{len(used_chunks) + 1}"),
                    "content": snippet,
                    "title": title,
                    "source": source_label,
                    "file_url": url,
                    "metadata": {
                        "page_number": page,
                        "document_id": document_id,
                        "chunk_index": idx,
                    },
                }
            )

    deduped_pairs: List[Tuple[str, str]] = []
    seen_pair = set()
    for source, url in zip(sources, source_urls):
        key = f"{source}|{url}"
        if key in seen_pair:
            continue
        seen_pair.add(key)
        deduped_pairs.append((source, url))

    deduped_sources = [item[0] for item in deduped_pairs]
    deduped_urls = [item[1] for item in deduped_pairs]
    rag_text = "\n\n".join(lines).strip() or "없음"

    return rag_text, deduped_sources, deduped_urls, used_chunks


def _build_router_query(message: str) -> str:
    message = _clean_text(message)
    target_universities = _extract_target_universities(message)
    extra = ""
    if target_universities:
        lines = [
            "",
            "[대학별 우선 검색]",
            "- 아래 대학의 학생부종합전형 기준 문서를 우선 조회하세요.",
        ]
        for uni in target_universities:
            lines.append(f"- {uni}: 인재상, 서류평가요소, 면접평가요소, 전형 가이드북")
        extra = "\n".join(lines)

    return (
        f"{message}\n\n"
        "[지시]\n"
        "- 질문에서 특정 대학/전형 기준이 암시되면 해당 대학 공식 가이드/전형자료를 조회할 함수 호출을 생성하세요.\n"
        "- 생기부 서술형 분석을 보강할 수 있는 근거 문서를 우선적으로 탐색하세요."
        f"{extra}"
    )


def _count_function_chunks(function_results: Dict[str, Any]) -> int:
    total = 0
    for value in (function_results or {}).values():
        if not isinstance(value, dict):
            continue
        chunks = value.get("chunks")
        if isinstance(chunks, list):
            total += len(chunks)
    return total


def _normalize_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    text = _clean_text(value)
    return [text] if text else []


def _normalize_function_calls(raw_calls: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw_calls, list):
        return out
    for item in raw_calls:
        if not isinstance(item, dict):
            continue
        fn = _clean_text(item.get("function"))
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        if not fn:
            continue
        out.append({"function": fn, "params": params})
    return out


def _call_signature(call: Dict[str, Any]) -> str:
    fn = _clean_text(call.get("function"))
    params = call.get("params") if isinstance(call.get("params"), dict) else {}
    return json.dumps({"function": fn, "params": params}, ensure_ascii=False, sort_keys=True)


def _extract_universities_from_calls(function_calls: List[Dict[str, Any]]) -> List[str]:
    universities: List[str] = []
    for call in function_calls:
        if _clean_text(call.get("function")) != "univ":
            continue
        params = call.get("params") if isinstance(call.get("params"), dict) else {}
        universities.extend(_normalize_text_list(params.get("university")))
    return _dedupe_preserve_order(universities)


def _build_forced_university_calls(universities: List[str], round_index: int) -> List[Dict[str, Any]]:
    """
    특정 대학이 질문에 명시된 경우, Router 결과와 별개로 해당 대학 공식 기준 문서를 강제 조회.
    """
    if not universities:
        return []

    query_sets = {
        1: [
            "학생부종합전형 인재상",
            "학생부종합전형 서류평가 기준",
            "학생부종합전형 면접평가 기준",
        ],
        2: [
            "학생부종합전형 가이드북",
            "평가요소 및 세부 평가항목",
            "서류평가 정성평가 기준",
        ],
        3: [
            "학업역량 진로역량 공동체역량 평가 관점",
            "면접 기출 및 평가 포인트",
            "제출서류 기반 평가 유의사항",
        ],
    }
    selected_queries = query_sets.get(round_index, query_sets[1])

    calls: List[Dict[str, Any]] = []
    for uni in universities[:MAX_UNIVERSITY_EXPANSION]:
        for q in selected_queries[:MAX_QUERIES_PER_UNIVERSITY]:
            calls.append(
                {
                    "function": "univ",
                    "params": {
                        "university": [uni],
                        "query": [f"2026학년도 {uni} {q}"],
                    },
                }
            )
    return calls


def _expand_univ_calls(function_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expanded: List[Dict[str, Any]] = []
    for call in function_calls:
        fn = _clean_text(call.get("function"))
        params = call.get("params") if isinstance(call.get("params"), dict) else {}
        if fn != "univ":
            expanded.append({"function": fn, "params": params})
            continue

        universities = _normalize_text_list(params.get("university"))[:MAX_UNIVERSITY_EXPANSION]
        queries = _normalize_text_list(params.get("query"))[:MAX_QUERIES_PER_UNIVERSITY]
        if not universities:
            universities = [""]
        if not queries:
            queries = ["학생부종합전형 평가기준"]

        for university in universities:
            for query in queries:
                expanded.append(
                    {
                        "function": "univ",
                        "params": {
                            "university": [university] if university else [""],
                            "query": [query],
                        },
                    }
                )
    return expanded


def _build_retrieval_round_query(message: str, round_index: int, universities: List[str]) -> str:
    base = _clean_text(message)
    if round_index <= 1:
        return _build_router_query(base)

    uni_text = ", ".join(universities[:MAX_UNIVERSITY_EXPANSION]) if universities else "질문 관련 대학"
    if round_index == 2:
        expanded = (
            f"{base}\n\n"
            "[추가 확장 검색 지시]\n"
            f"- 1차 결과의 대학({uni_text}) 중심으로 학생부종합전형 평가요소/인재상/서류평가 기준 문서를 추가 확보하세요.\n"
            "- 대학 공식 입학처 가이드북, 전형 안내, 면접평가 기준을 우선하세요.\n"
            "- 가능한 경우 문서 페이지 근거를 확보할 수 있는 형태로 호출하세요."
        )
        return _build_router_query(expanded)

    expanded = (
        f"{base}\n\n"
        "[재질의 확장 지시]\n"
        f"- 대학({uni_text}) 기준으로 누락되기 쉬운 항목(교과세특/창체/비교과/면접/전공적합)을 재검색하세요.\n"
        "- 기존과 중복되지 않는 근거를 우선 확보하세요.\n"
        "- 학생부종합, 평가기준, 가이드북, 입학사정관, 서류평가 키워드를 활용하세요."
    )
    return _build_router_query(expanded)


async def _run_multi_round_retrieval(
    *,
    message: str,
    history: List[Dict[str, Any]] | None,
    target_universities: List[str] | None = None,
) -> Dict[str, Any]:
    router = RouterAgent()
    all_results: Dict[str, Any] = {}
    round_details: List[Dict[str, Any]] = []
    round_router_outputs: List[Dict[str, Any]] = []
    first_router_output: Dict[str, Any] = {}

    seen_call_signatures = set()
    discovered_universities: List[str] = _dedupe_preserve_order(target_universities or [])
    total_unique_calls = 0
    router_ms_total = 0
    function_ms_total = 0
    history_input = history or []

    for round_index in range(1, MAX_RETRIEVAL_ROUNDS + 1):
        query_for_round = _build_retrieval_round_query(message, round_index, discovered_universities)

        route_start = time.perf_counter()
        router_output = await router.route(query_for_round, history_input)
        router_ms_total += int((time.perf_counter() - route_start) * 1000)
        if round_index == 1:
            first_router_output = router_output if isinstance(router_output, dict) else {}
        round_router_outputs.append(router_output if isinstance(router_output, dict) else {})

        raw_calls = _normalize_function_calls((router_output or {}).get("function_calls"))
        expanded_calls = _expand_univ_calls(raw_calls)
        forced_calls = _build_forced_university_calls(discovered_universities, round_index)
        if forced_calls:
            expanded_calls = forced_calls + expanded_calls
        if round_index == 1:
            discovered_universities = _dedupe_preserve_order(
                list(discovered_universities) + _extract_universities_from_calls(expanded_calls)
            )

        round_calls: List[Dict[str, Any]] = []
        for call in expanded_calls:
            signature = _call_signature(call)
            if signature in seen_call_signatures:
                continue
            seen_call_signatures.add(signature)
            round_calls.append(call)
            total_unique_calls += 1
            if len(round_calls) >= MAX_CALLS_PER_ROUND or total_unique_calls >= MAX_TOTAL_RETRIEVAL_CALLS:
                break

        round_results: Dict[str, Any] = {}
        if round_calls:
            function_start = time.perf_counter()
            round_results = await _execute_function_calls_parallel(round_calls)
            function_ms_total += int((time.perf_counter() - function_start) * 1000)
            for key, value in (round_results or {}).items():
                all_results[f"r{round_index}_{key}"] = value

        round_chunk_count = _count_function_chunks(round_results)
        round_details.append(
            {
                "round": round_index,
                "raw_calls": len(raw_calls),
                "expanded_calls": len(expanded_calls),
                "executed_calls": len(round_calls),
                "retrieved_chunks": round_chunk_count,
            }
        )

        # 1차에서 호출이 없으면 추가 라운드를 진행해도 수확 가능성이 낮아 조기 종료
        if round_index == 1 and not round_calls:
            break
        # 추가 라운드에서 신규 호출이 더 이상 없거나 총량 한도 도달 시 종료
        if round_index > 1 and not round_calls:
            break
        if total_unique_calls >= MAX_TOTAL_RETRIEVAL_CALLS:
            break

    return {
        "router_output": first_router_output,
        "router_round_outputs": round_router_outputs,
        "function_results": all_results,
        "round_details": round_details,
        "router_ms": router_ms_total,
        "function_ms": function_ms_total,
        "rounds": len(round_details),
        "unique_calls": total_unique_calls,
    }


async def _generate_report_text(
    *,
    message: str,
    history: List[Dict[str, Any]] | None,
    school_record_context: str,
    rag_context: str,
    mode: str,
    target_universities: List[str] | None = None,
    extra_instruction: str = "",
    previous_draft: str = "",
) -> str:
    prompt = f"""[사용자 요청]
{_clean_text(message)}

[최근 대화]
{_build_history_text(history)}

[학생 생활기록부 컨텍스트]
{school_record_context}

[외부 참고자료(RAG)]
{rag_context}

[작성 지침]
- 보고서는 충분히 길고 구체적으로 작성하세요.
- 각 문단은 근거를 반드시 포함하세요.
- 근거가 약한 내용은 추정이라고 표시하지 말고, '확인 필요'로 명시하세요.

{_build_mode_output_instructions(mode, target_universities)}
{extra_instruction}
"""

    if previous_draft:
        prompt += f"""
[이전 초안(형식 보정 대상)]
{previous_draft}
"""

    model = genai.GenerativeModel(
        model_name=GEMINI_FLASH_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    response = await asyncio.to_thread(
        model.generate_content,
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.25,
            max_output_tokens=8192,
        ),
        safety_settings=_SAFETY_SETTINGS,
    )
    text = _clean_generated_text(getattr(response, "text", ""))
    if text:
        sanitized = _sanitize_broken_table_lines(text)
        sanitized = _sanitize_prompt_leakage(sanitized)
        return sanitized
    return "생기부 전용 보고서를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."


def _required_sections_for_mode(mode: str, target_universities: List[str] | None = None) -> List[str]:
    has_university_focus = bool(target_universities)

    if has_university_focus and mode == REPORT_MODE_FOCUSED:
        return [
            "# 0. 학교별 평가기준 설명",
            "# 1. 대학별 기준 적용 평가(이번 질문 범위)",
            "# 2. 요청 주제 집중 분석",
            "# 3. 실행안 및 다음 액션",
        ]

    if has_university_focus:
        return [
            "# 0. 학교별 평가기준 설명",
            "# 1. 대학별 기준 적용 평가(사용자 생기부 기반)",
            "# 2. 대학별 비교 분석",
            "# 3. 학년별 분석",
            "# 4. 단계별 상세 분석(요청한 보고서 구조 반영)",
            "## 4-1. 교과세특(과세특)",
            "## 4-2. 개별세특/활동기록 (창체)",
            "## 4-3. 비교과(출결/봉사/행동특성)",
            "# 5. 대학별 지원 전략 제안",
            "# 6. 한계와 추가 확인 포인트",
        ]

    if mode == REPORT_MODE_FOCUSED:
        return [
            "# 0. 평가기준 설명(이번 답변 적용 기준)",
            "# 1. 기준별 적용 평가(이번 질문 범위)",
            "# 2. 요청 주제 집중 분석",
            "# 3. 실행안 및 다음 액션",
        ]
    return [
        "# 0. 평가기준 설명",
        "# 1. 기준별 적용 평가(사용자 생기부 기반)",
        "# 2. 전반 진단",
        "# 3. 학년별 분석",
        "# 4. 핵심 역량 분석",
        "# 5. 단계별 상세 분석(요청한 보고서 구조 반영)",
        "## 5-1. 교과세특(과세특)",
        "## 5-2. 개별세특/활동기록 (창체)",
        "## 5-3. 비교과(출결/봉사/행동특성)",
        "# 6. 지원 전략 제안",
        "# 7. 한계와 추가 확인 포인트",
    ]


def _find_missing_sections(
    text: str,
    mode: str,
    target_universities: List[str] | None = None,
) -> List[str]:
    required = _required_sections_for_mode(mode, target_universities)
    out = (text or "").strip()
    if not out:
        return required
    return [h for h in required if h not in out]


async def _generate_report_with_repair(
    *,
    message: str,
    history: List[Dict[str, Any]] | None,
    school_record_context: str,
    rag_context: str,
    mode: str,
    focus_instruction: str = "",
    target_universities: List[str] | None = None,
    university_chunk_counts: Dict[str, int] | None = None,
) -> Tuple[str, int]:
    text = await _generate_report_text(
        message=message,
        history=history,
        school_record_context=school_record_context,
        rag_context=rag_context,
        mode=mode,
        target_universities=target_universities,
        extra_instruction=focus_instruction,
    )

    max_repairs = 2 if (target_universities or []) else 1
    repair_attempts = 0

    while True:
        missing = _find_missing_sections(text, mode, target_universities)
        missing_universities = _find_missing_university_mentions(text, target_universities or [])
        evidence_gaps = _find_university_evidence_gaps(
            text,
            target_universities or [],
            university_chunk_counts or {},
        )
        if not missing and not missing_universities and not evidence_gaps:
            return text, repair_attempts
        if repair_attempts >= max_repairs:
            return text, repair_attempts

        repair_lines: List[str] = [
            "",
            "[형식/근거 보정 지시 - 최우선]",
            "아래 누락 지시를 모두 반영해 전체 답변을 다시 작성하세요.",
        ]
        if missing:
            repair_lines.append("- 누락 섹션 보정:")
            repair_lines.extend(f"  - {section}" for section in missing)
        if missing_universities:
            repair_lines.append("- 대학별 분석 누락 보정:")
            repair_lines.extend(f"  - {uni}" for uni in missing_universities)
        if evidence_gaps:
            repair_lines.append("- 대학별 문서 근거 보정(#1 섹션 필수):")
            for uni, reasons in evidence_gaps.items():
                joined = ", ".join(reasons)
                repair_lines.append(f"  - {uni}: {joined}")

        repair_lines.append(
            "- 대학명이 포함된 질문에서는 공통 기준 인용으로 대체하지 말고, 해당 대학 문서 외부근거를 반드시 제시하세요."
        )
        if focus_instruction:
            repair_lines.append(focus_instruction)
        repair_instruction = "\n".join(repair_lines)

        text = await _generate_report_text(
            message=message,
            history=history,
            school_record_context=school_record_context,
            rag_context=rag_context,
            mode=mode,
            target_universities=target_universities,
            extra_instruction=repair_instruction,
            previous_draft=text,
        )
        repair_attempts += 1


async def generate_school_record_report(
    *,
    message: str,
    history: List[Dict[str, Any]] | None,
    school_record_context: str,
    school_record: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    report_mode = _detect_report_mode(message)
    target_universities = _extract_target_universities(message)

    # 생기부 기반 적합 학교 추천 요청인데 대학명이 없으면: 매칭용 요약으로 적합 학교 선정 후 기존 방식으로 상세 분석
    if (
        not target_universities
        and school_record
        and user_id
        and _is_school_recommendation_request(message)
    ):
        try:
            matching_summary = await ensure_matching_summary(user_id, school_record)
            if matching_summary:
                target_universities = await _find_matching_schools(
                    matching_summary, CANDIDATE_UNIVERSITIES
                )
                print(f"📋 [적합학교추천] matching_summary_len={len(matching_summary)}, target_universities={target_universities}")
                if not target_universities:
                    target_universities = CANDIDATE_UNIVERSITIES[:5]
                    print(f"📋 [적합학교추천] 매칭 결과 없음 → fallback 대학 사용: {target_universities}")
            else:
                target_universities = CANDIDATE_UNIVERSITIES[:5]
                print(f"📋 [적합학교추천] 매칭용 요약 없음 → fallback 대학 사용: {target_universities}")
        except Exception as e:
            print(f"⚠️ [적합학교추천] 매칭 단계 예외: {e}")
            target_universities = CANDIDATE_UNIVERSITIES[:5]

    focus_instruction = _build_university_focus_instruction(target_universities, report_mode)
    retrieval_result = await _run_multi_round_retrieval(
        message=message,
        history=history,
        target_universities=target_universities,
    )
    router_output = retrieval_result.get("router_output", {}) or {}
    function_results = retrieval_result.get("function_results", {}) or {}
    round_details = retrieval_result.get("round_details", []) or []
    router_round_outputs = retrieval_result.get("router_round_outputs", []) or []
    router_ms = int(retrieval_result.get("router_ms", 0) or 0)
    function_ms = int(retrieval_result.get("function_ms", 0) or 0)
    university_chunk_counts = _count_target_university_chunks(function_results, target_universities)

    rag_context, sources, source_urls, used_chunks = _collect_rag_material(function_results)

    deep_dive_task = asyncio.create_task(
        _generate_subject_deep_dive_timed(
            message=message,
            school_record_context=school_record_context,
            mode=report_mode,
        )
    )

    llm_start = time.perf_counter()
    response_text, repair_attempts = await _generate_report_with_repair(
        message=message,
        history=history,
        school_record_context=school_record_context,
        rag_context=rag_context,
        mode=report_mode,
        focus_instruction=focus_instruction,
        target_universities=target_universities,
        university_chunk_counts=university_chunk_counts,
    )
    llm_ms = int((time.perf_counter() - llm_start) * 1000)

    follow_up_start = time.perf_counter()
    (deep_dive_text, deep_dive_ms), follow_up_questions = await asyncio.gather(
        deep_dive_task,
        _generate_follow_up_questions(
            message=message,
            report_text=response_text,
            mode=report_mode,
        ),
    )
    if deep_dive_text:
        response_text = f"{response_text.rstrip()}\n\n{deep_dive_text}"
    response_text = _append_follow_up_section(response_text, follow_up_questions)
    follow_up_ms = int((time.perf_counter() - follow_up_start) * 1000)

    return {
        "response": response_text,
        "router_output": router_output,
        "router_round_outputs": router_round_outputs,
        "function_results": function_results,
        "sources": _dedupe_preserve_order(sources),
        "source_urls": _dedupe_preserve_order(source_urls),
        "used_chunks": used_chunks,
        "follow_up_questions": follow_up_questions,
        "timing": {
            "router_ms": router_ms,
            "function_ms": function_ms,
            "llm_ms": llm_ms,
            "deep_dive_ms": deep_dive_ms,
            "follow_up_ms": follow_up_ms,
            "retrieved_chunks": _count_function_chunks(function_results),
            "retrieval_rounds": int(retrieval_result.get("rounds", 0) or 0),
            "retrieval_unique_calls": int(retrieval_result.get("unique_calls", 0) or 0),
            "retrieval_round_details": round_details,
            "target_universities": target_universities,
            "target_university_chunk_counts": university_chunk_counts,
            "mode": "school_record_dedicated_agent",
            "report_mode": report_mode,
            "repair_attempts": repair_attempts,
        },
    }


def _iter_text_chunks(text: str, chunk_size: int = STREAM_CHUNK_SIZE) -> Iterable[str]:
    clean = text or ""
    if not clean:
        return
    for idx in range(0, len(clean), chunk_size):
        yield clean[idx : idx + chunk_size]


def generate_school_record_report_stream(
    *,
    message: str,
    history: List[Dict[str, Any]] | None,
    school_record_context: str,
    school_record: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
):
    report_mode = _detect_report_mode(message)
    target_universities = _extract_target_universities(message)

    focus_instruction = _build_university_focus_instruction(target_universities, report_mode)
    started_at = time.perf_counter()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 생기부 기반 적합 학교 추천 요청: 매칭용 요약으로 적합 학교 선정
    if (
        not target_universities
        and school_record
        and user_id
        and _is_school_recommendation_request(message)
    ):
        yield {
            "type": "status",
            "step": "school_record_matching",
            "message": "📋 생기부 요약으로 적합한 대학을 찾는 중...",
            "detail": {},
        }
        try:
            matching_summary = loop.run_until_complete(
                ensure_matching_summary(user_id, school_record)
            )
            if matching_summary:
                target_universities = loop.run_until_complete(
                    _find_matching_schools(matching_summary, CANDIDATE_UNIVERSITIES)
                )
                print(f"📋 [적합학교추천/스트림] matching_summary_len={len(matching_summary)}, target_universities={target_universities}")
                if not target_universities:
                    target_universities = CANDIDATE_UNIVERSITIES[:5]
                    print(f"📋 [적합학교추천/스트림] 매칭 결과 없음 → fallback: {target_universities}")
            else:
                target_universities = CANDIDATE_UNIVERSITIES[:5]
                print(f"📋 [적합학교추천/스트림] 매칭용 요약 없음 → fallback: {target_universities}")
            focus_instruction = _build_university_focus_instruction(
                target_universities, report_mode
            )
            if target_universities:
                yield {
                    "type": "status",
                    "step": "school_record_matching_done",
                    "message": f"✅ 적합 대학 {len(target_universities)}개 선정됨. 해당 대학 기준으로 상세 분석합니다.",
                    "detail": {"target_universities": target_universities},
                }
        except Exception as e:
            print(f"⚠️ 스트림 매칭 단계 실패(무시): {e}")
            target_universities = CANDIDATE_UNIVERSITIES[:5]
            focus_instruction = _build_university_focus_instruction(
                target_universities, report_mode
            )

    try:
        yield {
            "type": "status",
            "step": "school_record_router",
            "message": "🔎 생기부 전용 에이전트가 대학/전형 기준 자료를 다회 검색하는 중...",
            "detail": {
                "report_mode": report_mode,
                "target_universities": target_universities,
            },
        }
        retrieval_result = loop.run_until_complete(
            _run_multi_round_retrieval(
                message=message,
                history=history,
                target_universities=target_universities,
            )
        )
        router_output = retrieval_result.get("router_output", {}) or {}
        function_results: Dict[str, Any] = retrieval_result.get("function_results", {}) or {}
        round_details = retrieval_result.get("round_details", []) or []
        rounds = int(retrieval_result.get("rounds", 0) or 0)
        unique_calls = int(retrieval_result.get("unique_calls", 0) or 0)
        total_chunks = _count_function_chunks(function_results)
        university_chunk_counts = _count_target_university_chunks(function_results, target_universities)
        if total_chunks > 0:
            yield {
                "type": "status",
                "step": "school_record_retrieval_complete",
                "message": f"✅ 외부 근거 수집 완료 ({rounds}라운드, 호출 {unique_calls}회, 청크 {total_chunks}개)",
                "detail": {
                    "rounds": rounds,
                    "unique_calls": unique_calls,
                    "retrieved_chunks": total_chunks,
                    "target_university_chunk_counts": university_chunk_counts,
                },
            }
        else:
            yield {
                "type": "status",
                "step": "school_record_retrieval_skip",
                "message": "ℹ️ 외부 문서 검색 없이 생기부 원문 중심으로 분석합니다.",
                "detail": {
                    "rounds": rounds,
                    "unique_calls": unique_calls,
                    "retrieved_chunks": total_chunks,
                },
            }

        if round_details:
            detail_lines = [
                f"{d.get('round')}차: 호출 {d.get('executed_calls', 0)}개 / 청크 {d.get('retrieved_chunks', 0)}개"
                for d in round_details
            ]
            yield {
                "type": "status",
                "step": "school_record_retrieval_rounds",
                "message": " · ".join(detail_lines),
                "detail": {
                    "round_details": round_details,
                },
            }

        rag_context, sources, source_urls, used_chunks = _collect_rag_material(function_results)

        deep_dive_task = loop.create_task(
            _generate_subject_deep_dive_timed(
                message=message,
                school_record_context=school_record_context,
                mode=report_mode,
            )
        )

        yield {
            "type": "status",
            "step": "school_record_report",
            "message": (
                "🧠 생기부 전용 에이전트가 "
                + ("집중형 보고서" if report_mode == REPORT_MODE_FOCUSED else "전체형 보고서")
                + "를 작성하는 중..."
            ),
            "detail": {
                "report_mode": report_mode,
                "target_universities": target_universities,
            },
        }

        llm_start = time.perf_counter()
        response_text, repair_attempts = loop.run_until_complete(
            _generate_report_with_repair(
                message=message,
                history=history,
                school_record_context=school_record_context,
                rag_context=rag_context,
                mode=report_mode,
                focus_instruction=focus_instruction,
                target_universities=target_universities,
                university_chunk_counts=university_chunk_counts,
            )
        )
        llm_ms = int((time.perf_counter() - llm_start) * 1000)
        yield {
            "type": "status",
            "step": "school_record_deep_dive",
            "message": "🧩 학년/과목별 확장 분석 + 꼬리 질문을 병렬 생성하는 중...",
        }
        follow_up_start = time.perf_counter()

        async def _parallel_post_process():
            return await asyncio.gather(
                deep_dive_task,
                _generate_follow_up_questions(
                    message=message,
                    report_text=response_text,
                    mode=report_mode,
                ),
            )

        (deep_dive_text, deep_dive_ms), follow_up_questions = loop.run_until_complete(
            _parallel_post_process()
        )
        if deep_dive_text:
            response_text = f"{response_text.rstrip()}\n\n{deep_dive_text}"
        response_text = _append_follow_up_section(response_text, follow_up_questions)
        follow_up_ms = int((time.perf_counter() - follow_up_start) * 1000)

        for part in _iter_text_chunks(response_text):
            yield {"type": "chunk", "text": part}

        total_ms = int((time.perf_counter() - started_at) * 1000)
        yield {
            "type": "done",
            "response": response_text,
            "timing": {
                "llm_ms": llm_ms,
                "deep_dive_ms": deep_dive_ms,
                "total_ms": total_ms,
                "retrieved_chunks": _count_function_chunks(function_results),
                "retrieval_rounds": rounds,
                "retrieval_unique_calls": unique_calls,
                "retrieval_round_details": round_details,
                "target_universities": target_universities,
                "target_university_chunk_counts": university_chunk_counts,
                "mode": "school_record_dedicated_agent",
                "report_mode": report_mode,
                "repair_attempts": repair_attempts,
            },
            "router_output": router_output,
            "router_round_outputs": retrieval_result.get("router_round_outputs", []) or [],
            "function_results": function_results,
            "sources": _dedupe_preserve_order(sources),
            "source_urls": _dedupe_preserve_order(source_urls),
            "used_chunks": used_chunks,
            "follow_up_questions": follow_up_questions,
        }
    except Exception as e:
        yield {"type": "error", "message": f"생기부 전용 에이전트 오류: {e}"}
    finally:
        try:
            loop.close()
        finally:
            asyncio.set_event_loop(None)
