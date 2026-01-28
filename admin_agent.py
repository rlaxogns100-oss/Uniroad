"""
Admin Agent - Router 출력 평가 에이전트
- Model: gemini-3-flash-preview
- 역할: Router Agent의 출력을 평가하고 이상 여부 판단
"""

import google.generativeai as genai
from typing import Dict, Any, Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ============================================================
# Admin Agent 설정
# ============================================================

ADMIN_AGENT_CONFIG = {
    "model": "gemini-3-flash-preview",
    "temperature": 0.0,
    "max_output_tokens": 1024
}


# ============================================================
# 평가 프롬프트
# ============================================================

EVALUATION_PROMPT = """당신은 입시 상담 AI의 품질 관리 담당자입니다.
Router Agent의 출력을 평가하고 이상 여부를 판단해주세요.

## 평가 기준

### 1. JSON 형식 검증
- Router 출력이 올바른 JSON 형식인지
- 필수 필드(function, params)가 있는지

### 2. 함수 선택 적절성
- 사용자 질문에 맞는 함수가 선택되었는지
- 사용 가능한 함수: univ, consult, teacher, general_chat
  - univ: 특정 대학 입시 정보 검색
  - consult: 성적 기반 합격 가능성 분석
  - teacher: 학습 조언, 멘탈 관리
  - general_chat: 일반 대화

### 3. 파라미터 적절성
- 함수에 필요한 파라미터가 올바르게 추출되었는지
- 성적 정보가 있다면 올바른 형식으로 파싱되었는지

### 4. 소요시간
- 3초 초과: 경고
- 6초 초과: 오류

## 입력 정보
- 사용자 질문: {user_question}
- Router 출력: {router_output}
- 소요시간: {elapsed_time}초

## 출력 형식 (JSON)
{{
  "status": "ok" | "warning" | "error",
  "reason": "평가 이유 (간단히)",
  "details": {{
    "json_valid": true/false,
    "function_appropriate": true/false,
    "params_correct": true/false,
    "time_ok": true/false
  }}
}}

JSON만 출력하세요."""


class AdminAgent:
    """Admin Agent - Router 출력 평가"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=ADMIN_AGENT_CONFIG["model"],
            generation_config={
                "temperature": ADMIN_AGENT_CONFIG["temperature"],
                "max_output_tokens": ADMIN_AGENT_CONFIG["max_output_tokens"],
            }
        )
    
    async def evaluate(
        self,
        user_question: str,
        router_output: Dict[str, Any],
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        Router 출력 평가
        
        Args:
            user_question: 사용자 질문
            router_output: Router Agent 출력 (JSON)
            elapsed_time: 소요 시간 (초)
        
        Returns:
            평가 결과 {status, reason, details}
        """
        try:
            # 프롬프트 생성
            prompt = EVALUATION_PROMPT.format(
                user_question=user_question,
                router_output=json.dumps(router_output, ensure_ascii=False, indent=2),
                elapsed_time=f"{elapsed_time:.2f}"
            )
            
            # Gemini 호출
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # JSON 파싱
            # 코드 블록 제거
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1])
            
            result = json.loads(result_text)
            
            return {
                "status": result.get("status", "ok"),
                "reason": result.get("reason", ""),
                "details": result.get("details", {})
            }
            
        except json.JSONDecodeError as e:
            print(f"❌ Admin Agent JSON 파싱 오류: {e}")
            return {
                "status": "error",
                "reason": f"평가 결과 파싱 실패: {str(e)}",
                "details": {}
            }
        except Exception as e:
            print(f"❌ Admin Agent 오류: {e}")
            return {
                "status": "error",
                "reason": f"평가 중 오류: {str(e)}",
                "details": {}
            }
    
    def quick_validate(
        self,
        router_output: Dict[str, Any],
        elapsed_time: float
    ) -> Dict[str, Any]:
        """
        빠른 검증 (LLM 호출 없이)
        - JSON 형식 검증
        - 소요시간 검증
        """
        status = "ok"
        reasons = []
        details = {
            "json_valid": True,
            "function_appropriate": True,  # LLM 없이는 판단 불가
            "params_correct": True,  # LLM 없이는 판단 불가
            "time_ok": True
        }
        
        # JSON 형식 검증
        if not isinstance(router_output, dict):
            status = "error"
            reasons.append("Router 출력이 딕셔너리가 아님")
            details["json_valid"] = False
        elif "function" not in router_output:
            status = "warning"
            reasons.append("function 필드 없음")
            details["json_valid"] = False
        
        # 소요시간 검증
        if elapsed_time > 60:
            status = "error"
            reasons.append(f"소요시간 {elapsed_time:.1f}초 (60초 초과)")
            details["time_ok"] = False
        elif elapsed_time > 30:
            if status == "ok":
                status = "warning"
            reasons.append(f"소요시간 {elapsed_time:.1f}초 (30초 초과)")
            details["time_ok"] = False
        
        return {
            "status": status,
            "reason": ", ".join(reasons) if reasons else "정상",
            "details": details
        }


# 싱글톤 인스턴스
admin_agent = AdminAgent()
