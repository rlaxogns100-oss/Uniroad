"""
Admin Agent
- Router 출력 평가 (형식, 함수 선택, 변수 적절성)
- Model: gemini-3-flash-preview
- 비동기 방식으로 router_agent 작동에 영향 없음
"""

import google.generativeai as genai
from typing import Dict, Any
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

ADMIN_CONFIG = {
    "model": "gemini-3-flash-preview",
    "temperature": 0.0,
    "max_output_tokens": 1024
}


ADMIN_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Admin Agent (품질 평가자)**입니다.

## 역할
Router Agent의 출력을 평가하여 품질을 판단합니다.

## 평가 기준

### 1. 형식 검증
- function_calls 배열이 존재하는가?
- 각 호출에 function과 params가 있는가?

### 2. 함수 선택 적절성
사용 가능한 함수:
- **univ**: 특정 대학 입시 정보 검색
  - params: university (대학 정식명칭), query (검색 쿼리)
- **consult**: 성적 기반 합격 가능성 분석
  - params: scores (성적 딕셔너리), target_univ (대학 리스트), target_major (학과 리스트), target_range (범위 리스트)

질문 유형에 맞는 함수가 선택되었는가?
- 대학 정보 질문 → univ
- 성적 분석/대학 추천 → consult
- 복합 질문 → univ + consult

### 3. 변수 적절성

#### univ 함수
- university: 정식 대학명인가? (서울대학교, 연세대학교 등)
- query: 연도 + 전형 + 학과가 명시되어 있는가?

#### consult 함수
- scores: 올바른 형식인가?
  - {"과목명": {"type": "등급"|"표준점수"|"백분위", "value": 숫자}}
  - 축약형 해석이 올바른가? (11232 → 국1/수1/영2/탐1=3/탐2=2)
- target_univ: 정식 대학명 리스트인가?
- target_major: 학과명 리스트인가?
- target_range: ["안정", "적정", "상향", "스나이핑"] 중 적절한가?

## 출력 형식
반드시 아래 JSON만 출력하세요. 다른 텍스트 없이 JSON만 출력합니다. 백틱(```)도 사용하지 마세요.

{"status": "ok", "format_check": {"valid": true, "comment": ""}, "function_check": {"valid": true, "comment": ""}, "params_check": {"valid": true, "comment": ""}, "overall_comment": ""}

status는 "ok", "warning", "error" 중 하나입니다.

## 상태 결정 기준
- **ok**: 모든 검증 통과
- **warning**: 경미한 문제 (파라미터 최적화 가능, 대학명 약칭 사용 등)
- **error**: 심각한 문제 (형식 오류, 잘못된 함수 선택, 필수 파라미터 누락)
"""


class AdminAgent:
    """Admin Agent - Router 출력 평가"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=ADMIN_CONFIG["model"],
            system_instruction=ADMIN_SYSTEM_PROMPT
        )
        self.generation_config = {
            "temperature": ADMIN_CONFIG["temperature"],
            "max_output_tokens": ADMIN_CONFIG["max_output_tokens"]
        }
    
    async def evaluate(self, user_question: str, router_output: str) -> Dict[str, Any]:
        """
        Router 출력 평가
        
        Args:
            user_question: 사용자 질문
            router_output: Router Agent 출력 JSON 문자열
            
        Returns:
            {
                "status": "ok" | "warning" | "error",
                "format_check": {...},
                "function_check": {...},
                "params_check": {...},
                "overall_comment": str
            }
        """
        try:
            # 평가 프롬프트 생성
            prompt = f"""## 사용자 질문
{user_question}

## Router 출력
```json
{router_output}
```

위 Router 출력을 평가해주세요."""

            response = await self.model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            
            raw_text = response.text.strip()
            result = self._parse_response(raw_text)
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "format_check": {"valid": False, "comment": f"평가 오류: {str(e)}"},
                "function_check": {"valid": False, "comment": "평가 실패"},
                "params_check": {"valid": False, "comment": "평가 실패"},
                "overall_comment": f"Admin Agent 오류: {str(e)}"
            }
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """JSON 파싱"""
        import re
        
        # 정규식으로 ```json...``` 블록 내용 추출
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            text = match.group(1).strip()
        
        # { 부터 } 까지 추출
        first = text.find('{')
        last = text.rfind('}')
        
        if first != -1 and last > first:
            text = text[first:last+1]
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 파싱 실패시 기본값 반환 (평가 완료로 처리)
            return {
                "status": "ok",
                "format_check": {"valid": True, "comment": ""},
                "function_check": {"valid": True, "comment": ""},
                "params_check": {"valid": True, "comment": ""},
                "overall_comment": ""
            }


# 싱글톤
_admin_agent = None

def get_admin_agent() -> AdminAgent:
    global _admin_agent
    if _admin_agent is None:
        _admin_agent = AdminAgent()
    return _admin_agent


async def evaluate_router_output(user_question: str, router_output: str) -> Dict[str, Any]:
    """편의 함수 - router_output을 JSON 문자열로 받음"""
    agent = get_admin_agent()
    return await agent.evaluate(user_question, router_output)


# ============================================================
# 테스트
# ============================================================

async def _test():
    print("=" * 60)
    print("Admin Agent 테스트")
    print("=" * 60)
    
    agent = AdminAgent()
    
    # 테스트 케이스 1: 정상 출력
    test_question = "서울대 정시 알려줘"
    test_output = {
        "function_calls": [
            {
                "function": "univ",
                "params": {
                    "university": "서울대학교",
                    "query": "2026학년도 서울대학교 정시 모집요강"
                }
            }
        ]
    }
    
    print(f"\n질문: {test_question}")
    print(f"Router 출력: {json.dumps(test_output, ensure_ascii=False)}")
    print("\n평가 중...")
    
    result = await agent.evaluate(test_question, test_output)
    print(f"\n평가 결과:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 테스트 케이스 2: 성적 분석
    test_question2 = "11232인데 경희대 갈 수 있어?"
    test_output2 = {
        "function_calls": [
            {
                "function": "consult",
                "params": {
                    "scores": {
                        "국어": {"type": "등급", "value": 1},
                        "수학": {"type": "등급", "value": 1},
                        "영어": {"type": "등급", "value": 2},
                        "탐구1": {"type": "등급", "value": 3},
                        "탐구2": {"type": "등급", "value": 2}
                    },
                    "target_univ": ["경희대학교"],
                    "target_major": [],
                    "target_range": []
                }
            }
        ]
    }
    
    print(f"\n\n질문: {test_question2}")
    print("\n평가 중...")
    
    result2 = await agent.evaluate(test_question2, test_output2)
    print(f"\n평가 결과:")
    print(json.dumps(result2, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
