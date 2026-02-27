"""
생기부 매칭용 내부 요약 (학교 추천 시 사용, 사용자 비노출).
- 업로드 시 1회 생성하여 저장하거나, 최초 추천 요청 시 생성 후 저장.
- 요약본으로 후보 대학을 순회하며 적합 학교를 찾는 데 사용.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from config.config import settings
from config.constants import GEMINI_FLASH_MODEL
from school_record_eval.report_context import build_school_record_report_context_text

genai.configure(api_key=settings.GEMINI_API_KEY)

# 매칭용 요약 최대 길이 (토큰 절약)
MATCHING_SUMMARY_SOURCE_MAX_CHARS = 8000
MATCHING_SUMMARY_OUTPUT_MAX_CHARS = 1500

_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


def get_matching_summary(school_record: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    저장된 매칭용 요약이 있으면 반환. 없으면 None.
    사용자에게 노출하지 않는 내부 전용 필드.
    """
    if not isinstance(school_record, dict) or not school_record:
        return None
    forms = school_record.get("forms") or school_record
    text = (forms if isinstance(forms, dict) else {}).get("matchingSummary")
    if isinstance(text, str) and text.strip():
        return text.strip()
    text = school_record.get("matchingSummary")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


async def generate_matching_summary_from_school_record(
    school_record: Dict[str, Any],
) -> str:
    """
    생기부 전체 컨텍스트에서 매칭용 요약 텍스트를 LLM으로 생성.
    학교별 평가기준과 매칭할 때 쓸 역량·전공·강점 키워드 중심으로 압축.
    """
    full_context = build_school_record_report_context_text(
        school_record,
        max_chars=MATCHING_SUMMARY_SOURCE_MAX_CHARS,
    )
    if not full_context or len(full_context.strip()) < 100:
        return ""

    model = genai.GenerativeModel(model_name=GEMINI_FLASH_MODEL)
    prompt = f"""아래는 한 학생의 생활기록부 원문 요약/발췌입니다. 
이 내용만 보고 **대학 학생부종합전형 매칭용 내부 요약**을 작성해 주세요.
(이 요약은 사용자에게 보여주지 않고, "이 생기부에 맞는 대학"을 찾을 때만 사용합니다.)

[작성 규칙]
- 400자 이상 {MATCHING_SUMMARY_OUTPUT_MAX_CHARS}자 이내로 작성.
- 반드시 포함할 내용: (1) 희망/적합 전공 계열 (인문·사회·자연·공학·의예·예체능 등), (2) 학업역량 관련 키워드 (세특 과목, 탐구 주제, 성취), (3) 진로역량 (진로 탐색, 관련 활동), (4) 공동체역량 (창체, 봉사, 리더십 등). 
- 구체적 과목명·활동명·키워드를 나열해 주세요. 대학별 평가기준(인재상, 서류평가요소)과 매칭할 수 있도록.
- 개인 식별 정보는 제외하고 역량·활동 중심으로만.

[생기부 원문 요약/발췌]
{full_context[:MATCHING_SUMMARY_SOURCE_MAX_CHARS]}

[매칭용 내부 요약]
"""

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=1024,
            ),
            safety_settings=_SAFETY_SETTINGS,
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return ""
        if len(text) > MATCHING_SUMMARY_OUTPUT_MAX_CHARS:
            text = text[:MATCHING_SUMMARY_OUTPUT_MAX_CHARS].rsplit(".", 1)[0] + "."
        return text
    except Exception as e:
        print(f"⚠️ matching_summary 생성 실패: {e}")
        return ""


async def ensure_matching_summary(
    user_id: str,
    school_record: Dict[str, Any],
) -> str:
    """
    매칭용 요약이 있으면 반환, 없으면 생성 후 프로필에 저장하고 반환.
    """
    from services.supabase_client import SupabaseService

    existing = get_matching_summary(school_record)
    if existing:
        return existing

    summary = await generate_matching_summary_from_school_record(school_record)
    if not summary:
        return ""

    # 저장: forms.matchingSummary 및 최상위 matchingSummary 동기화
    school = dict(school_record)
    forms = dict(school.get("forms") or school)
    forms["matchingSummary"] = summary
    school["forms"] = forms
    school["matchingSummary"] = summary

    try:
        await SupabaseService.update_user_profile_school_record(user_id, school)
    except Exception as e:
        print(f"⚠️ matchingSummary 저장 실패(무시): {e}")

    return summary
