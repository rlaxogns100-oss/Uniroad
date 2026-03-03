"""
세특 진단 API — 4단계 필승구조 기반 분석 + 하이라이팅 인덱스 계산
"""
import json
import re
import asyncio
import difflib
from typing import Any, Dict, List, Tuple, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config.config import settings
from .agent import MODEL_NAME

genai.configure(api_key=settings.GEMINI_API_KEY)

# ============================================================================
# 프롬프트: 입학사정관 AI 컨설턴트 (4단계 + 전공계열 + 체크리스트)
# ============================================================================
DIAGNOSE_PROMPT = """
# Role: 대입 입학사정관 출신 AI 컨설턴트 (Head Consultant)

# Goal:
사용자(학생)가 입력한 '세특(세부능력 및 특기사항)' 텍스트를 분석하여, 대학의 실제 평가 기준에 맞춰 정밀 진단하고 S등급으로 업그레이드할 수 있도록 JSON으로 결과를 반환하시오.

# Critical Logic 1: [4단계 필승 구조 분석]
모든 문장을 다음 4단계 흐름으로 분해하여 평가하시오. 흐름이 끊기거나 누락된 부분을 지적하시오.
1. **계기(동기):** 수업 중 배운 개념/이론에서 시작된 구체적 호기심 (Why)
2. **심화(독서/탐구):** 호기심 해결을 위한 독서, 논문, 실험 등 자기주도적 활동 (How Deep)
3. **역량(결과):** 보고서, 산출물, 프로그램 구현 등 구체적 결과물 (What)
4. **변화(성장):** 활동 후 인식의 변화, 진로 연결성, 후속 탐구 의지 (Growth)

# Critical Logic 2: [전공 계열별 평가 기준]
희망 전공(hope_major)에 따라 다음 핵심 역량을 중점 확인하시오.
- **인문/사회/교육:** 비판적 사고력, 사회 현상 분석, 통찰력
- **자연/공학/IT:** 논리적 추론, 실험 설계, 수학적 도구/코딩 활용, 트러블슈팅
- **의학/생명/환경:** 생명 존중 윤리, 분자 수준 심층 탐구, 사회적 합의

# Critical Logic 3: [최고의 세특 체크리스트]
다음 4가지 요소가 포함되었는지 true/false로 판단하시오.
1. **actionVerbs:** '~함', '~규명함' 등 구체적 행동 동사 사용 여부
2. **concreteData:** 책 제목(저자), 실험 오차율(%), 프로그래밍 언어 등 구체적 수치/고유명사 명시 여부
3. **curriculumLink:** 교과 과정의 개념에서 파생된 수업 연계성 여부
4. **uniqueQuestion:** 남들과 다른 '나만의 탐구 질문' 개별성 여부

# 출력 규칙
- **quote**: goodPoints/reconsiderPoints에서 근거 문장을 원문에서 **그대로** 발췌 (최소 20자). 해당 없으면 "".
- **structureAnalysis**: 4단계 각각에 대해 status(ok/warn/missing), summary(한 줄 요약), detail(상세 설명 또는 보완 제안)을 반환하시오.
- **admissionComment**: 전공 적합성 관점에서 입학사정관 코멘트 2~4문장.
"""

DIAGNOSE_JSON_SCHEMA = """
응답은 반드시 아래 JSON 형식만 출력하시오. 다른 말 없이 JSON만.
{
  "structureAnalysis": {
    "계기": { "status": "ok", "summary": "수업에서 조건부 확률을 배우며 마케팅 적용에 호기심을 가짐", "detail": "" },
    "심화": { "status": "warn", "summary": "인터넷 검색 수준", "detail": "관련 도서나 논문 인용으로 심화 필요" },
    "역량": { "status": "ok", "summary": "설문조사 보고서 작성", "detail": "" },
    "변화": { "status": "missing", "summary": "누락", "detail": "통계가 의사결정에 어떻게 쓰이는지 + 후속 계획 추가 필요" }
  },
  "checklist": {
    "actionVerbs": true,
    "concreteData": false,
    "curriculumLink": true,
    "uniqueQuestion": false
  },
  "admissionComment": "전공 적합성 관점에서 현재 글의 강점과 보완점을 2~4문장으로 서술.",
  "goodPoints": [
    { "step": "계기", "label": "구체적 동기", "feedback": "설명", "quote": "원문 발췌 구절" }
  ],
  "reconsiderPoints": [
    { "step": "변화", "label": "성장 서술 부재", "feedback": "보완 제안", "quote": "" }
  ]
}
"""

# ============================================================================
# 리라이팅 프롬프트 (개선점 반영 S등급 버전 생성)
# ============================================================================
REWRITE_PROMPT = """당신은 입학사정관 출신 학생부종합전형 전문가입니다.

아래 [원문]과 [진단 결과: 잘된 점 / 보완할 점]을 바탕으로, **보완할 점을 반영한 S등급 수준의 세특**으로 한 편만 리라이팅해 주세요.

규칙:
1. 원문의 핵심 내용(사실, 데이터, 활동)은 유지하되, 보완할 점에서 지적된 부분을 구체적으로 보강하세요.
2. 4단계 필승 구조(계기→심화→역량→변화)가 자연스럽게 드러나도록 문장을 다듬으세요.
3. 잘된 점은 그대로 살리고, 부족한 단계(예: 계기/변화)가 있으면 적절한 1~2문장을 추가하세요.
4. 학생부 세특 형식(띄어쓰기, 맞춤법, 문단 길이)을 지키고, 다른 설명 없이 **리라이팅된 세특 텍스트만** 출력하세요.
5. 출력은 반드시 리라이팅된 본문만 한 줄로 이어서 작성하세요. 제목이나 "다음과 같이 수정했습니다" 같은 문구는 넣지 마세요.
"""


# ============================================================================
# 하이라이팅 인덱스 계산 (Fuzzy Matching)
# ============================================================================
def find_quote_indices(original_text: str, quote: str) -> Tuple[int, int]:
    """
    원문(original_text)에서 인용구(quote)의 시작/끝 인덱스를 찾습니다.
    정확한 매칭 실패 시 difflib을 사용한 Fuzzy Matching을 수행합니다.
    
    Returns:
        (start, end) 튜플. 찾지 못하면 (-1, -1)
    """
    if not quote or not quote.strip():
        return (-1, -1)
    
    quote = quote.strip()
    
    # 1. 정확한 매칭 시도
    start = original_text.find(quote)
    if start != -1:
        return (start, start + len(quote))
    
    # 2. 공백 정규화 후 매칭 시도
    def normalize(s: str) -> str:
        return re.sub(r'\s+', ' ', s).strip()
    
    norm_original = normalize(original_text)
    norm_quote = normalize(quote)
    
    # 정규화된 텍스트에서 찾기
    norm_start = norm_original.find(norm_quote)
    if norm_start != -1:
        # 정규화된 위치를 원본 위치로 변환
        orig_pos = 0
        norm_pos = 0
        while norm_pos < norm_start and orig_pos < len(original_text):
            if original_text[orig_pos].isspace():
                # 연속 공백 스킵
                while orig_pos < len(original_text) and original_text[orig_pos].isspace():
                    orig_pos += 1
                norm_pos += 1  # 정규화에서는 공백 1개
            else:
                orig_pos += 1
                norm_pos += 1
        
        start = orig_pos
        # 끝 위치 찾기
        quote_len = 0
        while quote_len < len(norm_quote) and orig_pos < len(original_text):
            if original_text[orig_pos].isspace():
                while orig_pos < len(original_text) and original_text[orig_pos].isspace():
                    orig_pos += 1
                quote_len += 1
            else:
                orig_pos += 1
                quote_len += 1
        
        return (start, orig_pos)
    
    # 3. Fuzzy Matching (difflib)
    matcher = difflib.SequenceMatcher(None, original_text.lower(), quote.lower())
    match = matcher.find_longest_match(0, len(original_text), 0, len(quote))
    
    # 매칭된 길이가 quote의 70% 이상이면 유효한 인용으로 간주
    if match.size >= len(quote) * 0.7:
        # 매칭 시작점에서 앞뒤로 확장하여 전체 quote 범위 추정
        start = match.a
        end = match.a + match.size
        
        # 문장 경계까지 확장 (마침표, 쉼표 등)
        while end < len(original_text) and original_text[end] not in '.,;:!?\n':
            end += 1
        if end < len(original_text) and original_text[end] in '.':
            end += 1
        
        return (start, min(end, len(original_text)))
    
    # 4. 부분 문자열 매칭 (quote의 앞부분 50%로 시도)
    if len(quote) > 20:
        partial = quote[:len(quote) // 2]
        partial_start = original_text.find(partial)
        if partial_start != -1:
            # 문장 끝까지 확장
            end = partial_start + len(quote)
            # 마침표나 줄바꿈까지 확장
            while end < len(original_text) and original_text[end] not in '.\n':
                end += 1
            if end < len(original_text):
                end += 1
            return (partial_start, min(end, len(original_text)))
    
    return (-1, -1)


def calculate_highlights(original_text: str, diagnosis_data: Dict) -> List[Dict[str, Any]]:
    """
    진단 결과에서 하이라이트 정보를 추출하고 인덱스를 계산합니다.
    
    Returns:
        highlights 배열 (type, step, label, feedback, indices, quote)
    """
    highlights = []
    
    # goodPoints 처리
    for item in diagnosis_data.get("goodPoints", []):
        quote = item.get("quote", "")
        indices = find_quote_indices(original_text, quote)
        
        highlights.append({
            "type": "good",
            "step": item.get("step", ""),
            "label": item.get("label", ""),
            "feedback": item.get("feedback", item.get("text", "")),
            "indices": list(indices),
            "quote": quote if indices[0] != -1 else ""
        })
    
    # reconsiderPoints 처리
    for item in diagnosis_data.get("reconsiderPoints", []):
        quote = item.get("quote", "")
        indices = find_quote_indices(original_text, quote) if quote else (-1, -1)
        
        highlights.append({
            "type": "bad",
            "step": item.get("step", ""),
            "label": item.get("label", ""),
            "feedback": item.get("feedback", item.get("text", "")),
            "indices": list(indices),
            "quote": quote if indices[0] != -1 else ""
        })
    
    return highlights


# ============================================================================
# Gemini API 응답 파싱
# ============================================================================
def _default_structure_analysis() -> Dict[str, Dict[str, str]]:
    """4단계 구조 분석 기본값"""
    steps = ("계기", "심화", "역량", "변화")
    return {
        s: {"status": "warn", "summary": "분석 없음", "detail": ""}
        for s in steps
    }


def _default_checklist() -> Dict[str, bool]:
    return {"actionVerbs": False, "concreteData": False, "curriculumLink": False, "uniqueQuestion": False}


def _parse_diagnosis_response(response_text: str) -> Dict[str, Any]:
    """Gemini 응답을 파싱하여 structureAnalysis, checklist, admissionComment, goodPoints, reconsiderPoints 추출"""
    try:
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned_text)
            if match:
                cleaned_text = match.group(1).strip()
        data = json.loads(cleaned_text)

        result = {
            "goodPoints": [],
            "reconsiderPoints": [],
            "structureAnalysis": _default_structure_analysis(),
            "checklist": _default_checklist(),
            "admissionComment": "",
        }

        for key in ["goodPoints", "reconsiderPoints"]:
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        result[key].append({
                            "step": item.get("step", ""),
                            "label": item.get("label", ""),
                            "feedback": item.get("feedback", item.get("text", "")),
                            "quote": item.get("quote", "") or (item.get("keywords", [""])[0] if isinstance(item.get("keywords"), list) else ""),
                        })

        if "structureAnalysis" in data and isinstance(data["structureAnalysis"], dict):
            for step in ("계기", "심화", "역량", "변화"):
                if step in data["structureAnalysis"] and isinstance(data["structureAnalysis"][step], dict):
                    s = data["structureAnalysis"][step]
                    result["structureAnalysis"][step] = {
                        "status": s.get("status", "warn"),
                        "summary": s.get("summary", ""),
                        "detail": s.get("detail", ""),
                    }

        if "checklist" in data and isinstance(data["checklist"], dict):
            for k in ("actionVerbs", "concreteData", "curriculumLink", "uniqueQuestion"):
                if k in data["checklist"]:
                    result["checklist"][k] = bool(data["checklist"][k])

        if "admissionComment" in data and isinstance(data["admissionComment"], str):
            result["admissionComment"] = data["admissionComment"].strip()

        return result

    except json.JSONDecodeError as e:
        print(f"❌ [진단] JSON 파싱 실패: {e}")
        print(f"   응답 내용: {response_text[:500]}")
        return {
            "goodPoints": [],
            "reconsiderPoints": [],
            "structureAnalysis": _default_structure_analysis(),
            "checklist": _default_checklist(),
            "admissionComment": "",
        }


# ============================================================================
# 리라이팅 (개선점 반영 S등급 버전 생성)
# ============================================================================
async def _generate_rewritten_version(
    original_text: str,
    good_points: List[Dict[str, Any]],
    reconsider_points: List[Dict[str, Any]],
) -> str:
    """진단 결과를 바탕으로 보완점을 반영한 리라이팅 버전을 생성합니다."""
    if not original_text or len(original_text.strip()) < 30:
        return original_text

    good_summary = "\n".join(
        f"- [{p.get('step', '')}] {p.get('label', '')}: {p.get('feedback', '')}"
        for p in good_points
    ) if good_points else "(없음)"
    reconsider_summary = "\n".join(
        f"- [{p.get('step', '')}] {p.get('label', '')}: {p.get('feedback', '')}"
        for p in reconsider_points
    ) if reconsider_points else "(없음)"

    prompt = f"""[원문]
{original_text}

[잘된 점]
{good_summary}

[보완할 점]
{reconsider_summary}

위 보완할 점을 반영하여 S등급 수준으로 리라이팅한 세특만 출력하세요. 다른 말 없이 리라이팅된 본문만 작성하세요."""

    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        response = await asyncio.to_thread(
            model.generate_content,
            REWRITE_PROMPT + "\n\n" + prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=2048,
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            },
        )
        rewritten = (response.text or "").strip()
        # 불필요한 접두 문구 제거
        for prefix in ("리라이팅 결과:", "수정본:", "다음과 같습니다.", "---"):
            if rewritten.startswith(prefix):
                rewritten = rewritten[len(prefix):].strip()
        return rewritten if rewritten else original_text
    except Exception as e:
        print(f"⚠️ [리라이팅 실패] {e}")
        return original_text


# ============================================================================
# 메인 진단 함수
# ============================================================================
async def diagnose_school_record(content: str, hope_major: Optional[str] = None) -> Dict[str, Any]:
    """
    세특 원문을 4단계 필승구조 + 전공계열 + 체크리스트로 진단하고 하이라이팅·리라이팅을 반환합니다.
    hope_major: 희망 전공(계열) — 전공 적합성 코멘트에 반영됩니다.
    """
    content = (content or "").strip()
    hope_major = (hope_major or "").strip()

    empty_extra = {
        "structure_analysis": _default_structure_analysis(),
        "checklist": _default_checklist(),
        "admission_comment": "",
    }

    if not content:
        return {
            "success": False,
            "error": "내용을 입력해 주세요.",
            "structure_analysis": empty_extra["structure_analysis"],
            "checklist": empty_extra["checklist"],
            "admission_comment": "",
        }

    if len(content) < 30:
        return {
            "success": True,
            "original_text": content,
            "highlights": [],
            "goodPoints": [],
            "reconsiderPoints": [{
                "step": "전체",
                "label": "내용 부족",
                "feedback": "내용이 너무 짧아 진단하기 어렵습니다. 4단계(계기, 심화, 역량, 변화)를 포함하여 구체적으로 작성해 주세요.",
                "quote": ""
            }],
            "rewritten_version": content,
            "structure_analysis": empty_extra["structure_analysis"],
            "checklist": empty_extra["checklist"],
            "admission_comment": "",
            "error": None
        }

    user_message = DIAGNOSE_JSON_SCHEMA + "\n\n아래 세특 원문을 분석하여 위 형식의 JSON만 출력하시오.\n\n[세특 원문]\n" + content
    if hope_major:
        user_message += "\n\n[희망 전공]\n" + hope_major

    try:
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=DIAGNOSE_PROMPT
        )
        response = await asyncio.to_thread(
            model.generate_content,
            user_message,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="application/json"
            ),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        parsed_data = _parse_diagnosis_response(response.text)
        highlights = calculate_highlights(content, parsed_data)
        rewritten_version = await _generate_rewritten_version(
            content,
            parsed_data["goodPoints"],
            parsed_data["reconsiderPoints"],
        )
        print(f"✅ [진단 완료] structureAnalysis/checklist/admissionComment 포함, rewritten: {len(rewritten_version)}자")
        return {
            "success": True,
            "original_text": content,
            "highlights": highlights,
            "goodPoints": parsed_data["goodPoints"],
            "reconsiderPoints": parsed_data["reconsiderPoints"],
            "rewritten_version": rewritten_version,
            "structure_analysis": parsed_data["structureAnalysis"],
            "checklist": parsed_data["checklist"],
            "admission_comment": parsed_data["admissionComment"],
            "error": None
        }
    except Exception as e:
        print(f"❌ [진단 시스템 오류] {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "original_text": content,
            "highlights": [],
            "goodPoints": [],
            "reconsiderPoints": [],
            "rewritten_version": "",
            "structure_analysis": empty_extra["structure_analysis"],
            "checklist": empty_extra["checklist"],
            "admission_comment": "",
            "error": "AI 진단 서버와 통신 중 오류가 발생했습니다."
        }


# ============================================================================
# 동기 버전 (기존 API 호환용)
# ============================================================================
def run_diagnose(content: str, hope_major: Optional[str] = None) -> Dict[str, Any]:
    """동기 버전 진단 함수 (기존 API 호환)"""
    return asyncio.run(diagnose_school_record(content, hope_major=hope_major))
