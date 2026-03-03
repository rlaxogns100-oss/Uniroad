"""
생기부 평가 비즈니스 로직

- 세특(세부능력특기사항) 평가: Gemini 3.0 Flash Preview 에이전트 (입학사정관/S등급 첨삭 프롬프트)
"""
import asyncio
from typing import Dict, Any
from .models import SchoolRecordEvaluateRequest
from .agent import get_seteuk_eval_agent


async def evaluate_school_record(request: SchoolRecordEvaluateRequest) -> Dict[str, Any]:
    """
    희망 전공·교과목·세특 초안을 받아 종합 등급, 벤치마킹 분석, S등급 리라이팅을 반환합니다.
    """
    content = (request.content or "").strip()
    if not content:
        return {
            "success": False,
            "message": "세특 초안을 입력해 주세요.",
            "result": None,
            "scores": None,
        }

    agent = get_seteuk_eval_agent()
    hope_major = (request.hope_major or "").strip()
    eval_result = await asyncio.to_thread(
        agent.evaluate,
        hope_major,
        content,
    )

    return {
        "success": True,
        "message": eval_result.get("grade", "").split("\n")[0][:80] if eval_result.get("grade") else "세특 평가가 완료되었습니다.",
        "result": {
            "feedback": eval_result.get("feedback"),
            "grade": eval_result.get("grade"),
            "benchmark": eval_result.get("benchmark"),
            "rewrite": eval_result.get("rewrite"),
        },
        "scores": None,
    }
