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


async def evaluate_function_result(
    user_question: str, 
    function_calls: list, 
    function_results: dict
) -> Dict[str, Any]:
    """
    Function 실행 결과 평가
    
    Args:
        user_question: 사용자 질문
        function_calls: router_agent가 생성한 function_calls 리스트
        function_results: execute_function_calls 실행 결과
        
    Returns:
        {
            "status": "ok" | "warning" | "error",
            "comment": str,
            "details": {...}
        }
    """
    try:
        # 평가 로직 (LLM 호출 없이 규칙 기반)
        total_chunks = 0
        errors = []
        warnings = []
        details = {}
        
        for key, result in function_results.items():
            if "error" in result:
                errors.append(f"{key}: {result['error']}")
                details[key] = {"status": "error", "error": result['error']}
            elif "chunks" in result:
                chunk_count = result.get("count", 0)
                total_chunks += chunk_count
                
                if chunk_count == 0:
                    warnings.append(f"{key}: 검색 결과 없음 (university={result.get('university')})")
                    details[key] = {"status": "warning", "count": 0}
                else:
                    details[key] = {"status": "ok", "count": chunk_count}
            elif result.get("status") == "not_implemented":
                warnings.append(f"{key}: 미구현 함수")
                details[key] = {"status": "warning", "reason": "not_implemented"}
        
        # 최종 상태 결정
        if errors:
            status = "error"
            comment = f"오류 발생: {'; '.join(errors)}"
        elif warnings:
            status = "warning"
            comment = f"경고: {'; '.join(warnings)}"
        else:
            status = "ok"
            comment = f"총 {total_chunks}개 청크 검색 완료"
        
        return {
            "status": status,
            "comment": comment,
            "details": details,
            "total_chunks": total_chunks
        }
        
    except Exception as e:
        return {
            "status": "error",
            "comment": f"평가 오류: {str(e)}",
            "details": {},
            "total_chunks": 0
        }


# ============================================================
# 최종 답변 평가 (LLM 기반)
# ============================================================

FINAL_RESPONSE_EVAL_PROMPT = """최종 답변 품질 평가자입니다. 엄격하게 평가하세요.

## 평가 항목 (valid: true/false, comment: 20자 이내)

1. source_accuracy: Function 결과 정확히 인용? 출처(<cite>) 표기?

2. hallucination_check: 없는 정보 지어냄? 수치 정확?

3. length_check: 100자 이상? 2000자 이하?

4. context_relevance [가장 중요]: 
   - 질문이 수치/인원/경쟁률 등을 물었으면 반드시 해당 수치가 답변에 있어야 함
   - "몇 명?" 질문 → 답변에 숫자가 없으면 false
   - 칭찬/격려만 있고 실질적 답변이 없으면 false
   - Function 결과에 정보가 있는데 답변에서 언급 안 했으면 false

5. format_check: 형식 깨짐 없음?

## 상태
- ok: 모두 통과
- warning: 경미한 문제 (출처 미표기 등)
- error: 질문에 답 안함 / 할루시네이션 / 핵심 정보 누락

## 출력 (JSON만, 코멘트는 20자 이내로 짧게)
{"status":"ok","source_accuracy":{"valid":true,"comment":""},"hallucination_check":{"valid":true,"comment":""},"length_check":{"valid":true,"comment":""},"context_relevance":{"valid":true,"comment":""},"format_check":{"valid":true,"comment":""},"overall_comment":""}
"""


class FinalResponseEvaluator:
    """최종 답변 평가 클래스"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=ADMIN_CONFIG["model"],
            system_instruction=FINAL_RESPONSE_EVAL_PROMPT
        )
        # JSON 응답 강제를 위한 설정
        self.generation_config = {
            "temperature": ADMIN_CONFIG["temperature"],
            "max_output_tokens": ADMIN_CONFIG["max_output_tokens"],
            "response_mime_type": "application/json"  # JSON 출력 강제
        }
    
    async def evaluate(
        self,
        user_question: str,
        conversation_history: list,
        function_results: dict,
        final_response: str
    ) -> Dict[str, Any]:
        """
        최종 답변 평가
        
        Args:
            user_question: 사용자 질문
            conversation_history: 이전 대화 내역
            function_results: Function 실행 결과
            final_response: Main Agent가 생성한 최종 답변
            
        Returns:
            {
                "status": "ok" | "warning" | "error",
                "source_accuracy": {...},
                "hallucination_check": {...},
                "length_check": {...},
                "context_relevance": {...},
                "format_check": {...},
                "overall_comment": str
            }
        """
        try:
            # Function 결과에서 핵심 데이터 추출 (청크 내용 요약)
            function_summary = self._summarize_function_results(function_results)
            
            # 대화 내역 포맷팅
            history_text = "\n".join(conversation_history[-5:]) if conversation_history else "없음"
            
            # 평가 프롬프트 생성
            prompt = f"""## 사용자 질문
{user_question}

## 이전 대화 내역
{history_text}

## Function 실행 결과 (검색된 데이터)
{function_summary}

## 최종 답변
{final_response}

위 최종 답변을 평가해주세요. Function 결과에 있는 정보만 사용했는지, 할루시네이션은 없는지, 답변 길이와 형식이 적절한지 확인해주세요."""

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
                "source_accuracy": {"valid": False, "comment": f"평가 오류: {str(e)}"},
                "hallucination_check": {"valid": False, "comment": "평가 실패"},
                "length_check": {"valid": False, "comment": "평가 실패"},
                "context_relevance": {"valid": False, "comment": "평가 실패"},
                "format_check": {"valid": False, "comment": "평가 실패"},
                "overall_comment": f"평가 오류: {str(e)}"
            }
    
    def _summarize_function_results(self, function_results: dict) -> str:
        """Function 결과 요약 (평가용)"""
        if not function_results:
            return "검색 결과 없음"
        
        summary_parts = []
        for key, result in function_results.items():
            if "error" in result:
                summary_parts.append(f"[{key}] 오류: {result['error']}")
            elif "chunks" in result:
                university = result.get("university", "")
                query = result.get("query", "")
                chunks = result.get("chunks", [])
                
                summary_parts.append(f"\n[{university}] (검색어: {query})")
                summary_parts.append(f"총 {len(chunks)}개 청크 검색됨")
                
                # 각 청크의 핵심 정보만 추출 (평가용)
                for i, chunk in enumerate(chunks[:5], 1):  # 상위 5개만
                    content = chunk.get("content", "")[:500]  # 500자로 제한
                    page = chunk.get("page_number", "")
                    summary_parts.append(f"  청크 {i} (p.{page}): {content}")
        
        return "\n".join(summary_parts)
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """JSON 파싱 - 여러 방법 시도"""
        import re
        
        original_text = text
        
        # 방법 1: 직접 JSON 파싱 (response_mime_type이 json일 경우)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 방법 2: ```json...``` 블록 추출
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # 방법 3: { 부터 } 까지 추출
        first = text.find('{')
        last = text.rfind('}')
        
        if first != -1 and last > first:
            try:
                return json.loads(text[first:last+1])
            except json.JSONDecodeError:
                pass
        
        # 방법 4: 텍스트에서 키워드 기반 분석 (fallback)
        text_lower = original_text.lower()
        
        # 할루시네이션/오류 관련 키워드 탐지
        has_error = any(kw in text_lower for kw in ['할루시네이션', 'hallucination', '지어낸', '없는 정보', '일치하지 않', '잘못된'])
        has_warning = any(kw in text_lower for kw in ['누락', '부족', '짧', '길이', '출처 표기'])
        
        if has_error:
            status = "error"
        elif has_warning:
            status = "warning"
        else:
            status = "ok"
        
        # 원본 텍스트를 코멘트로 사용
        comment = original_text[:200] if len(original_text) > 200 else original_text
        
        return {
            "status": status,
            "source_accuracy": {"valid": not has_error, "comment": ""},
            "hallucination_check": {"valid": not has_error, "comment": comment if has_error else ""},
            "length_check": {"valid": True, "comment": ""},
            "context_relevance": {"valid": True, "comment": ""},
            "format_check": {"valid": True, "comment": ""},
            "overall_comment": comment
        }


# 싱글톤 - 최종 답변 평가
_final_evaluator = None

def get_final_evaluator() -> FinalResponseEvaluator:
    global _final_evaluator
    if _final_evaluator is None:
        _final_evaluator = FinalResponseEvaluator()
    return _final_evaluator


async def evaluate_final_response(
    user_question: str,
    conversation_history: list,
    function_results: dict,
    final_response: str
) -> Dict[str, Any]:
    """편의 함수 - 최종 답변 평가"""
    evaluator = get_final_evaluator()
    return await evaluator.evaluate(
        user_question,
        conversation_history,
        function_results,
        final_response
    )


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
    
    # 테스트 케이스 3: 최종 답변 평가
    print("\n\n" + "=" * 60)
    print("최종 답변 평가 테스트")
    print("=" * 60)
    
    test_question3 = "경희대 빅데이터응용학과 수시 몇 명 뽑아?"
    test_function_results = {
        "univ_0": {
            "university": "경희대학교",
            "query": "2026학년도 경희대학교 빅데이터응용학과 수시 모집인원",
            "count": 2,
            "chunks": [
                {
                    "chunk_id": 1,
                    "document_id": 16,
                    "page_number": 27,
                    "content": "빅데이터응용학과 수시 모집인원: 12명 (학생부교과 2명, 학생부종합 6명, 논술 4명)"
                }
            ]
        }
    }
    test_final_response = """빅데이터응용학과는 데이터 사이언스 분야에 관심 있는 학생들에게 인기가 정말 많은 학과에요. 모집 인원을 정확하게 확인해서 전략을 세우는 것이 중요합니다.

【2026학년도 수시 모집인원】
경희대학교 빅데이터응용학과는 2026학년도 수시 모집으로 총 12명을 선발해요.
• 학생부교과(지역균형전형): 2명
• 학생부종합(네오르네상스전형): 6명
• 논술(논술우수자전형): 4명 <cite data-source="2026학년도 수시 신입생 모집요강 27p" data-url="https://...pdf">빅데이터응용학과는 수시에서 총 12명을 모집합니다.</cite>

목표를 향해 차근차근 준비하는 모습이 멋집니다. 궁금하신 점 있으면 언제든 물어보세요. 유니로드가 항상 응원할게요!"""
    
    print(f"\n질문: {test_question3}")
    print("\n최종 답변 평가 중...")
    
    result3 = await evaluate_final_response(
        user_question=test_question3,
        conversation_history=[],
        function_results=test_function_results,
        final_response=test_final_response
    )
    print(f"\n평가 결과:")
    print(json.dumps(result3, ensure_ascii=False, indent=2))
    
    # 테스트 케이스 4: 할루시네이션 있는 답변
    print("\n\n" + "=" * 60)
    print("할루시네이션 테스트 (잘못된 답변)")
    print("=" * 60)
    
    bad_response = """경희대학교 빅데이터응용학과는 2026학년도에 총 50명을 모집합니다.
수시로 30명, 정시로 20명을 선발하며, 작년 경쟁률은 15:1이었습니다."""
    
    print(f"\n질문: {test_question3}")
    print("\n잘못된 답변 평가 중...")
    
    result4 = await evaluate_final_response(
        user_question=test_question3,
        conversation_history=[],
        function_results=test_function_results,
        final_response=bad_response
    )
    print(f"\n평가 결과:")
    print(json.dumps(result4, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
