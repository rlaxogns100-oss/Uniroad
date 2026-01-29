"""
Main Agent
- 사용자 질문 + 검색된 자료를 토대로 최종 답변 생성
- Model: gemini-2.0-flash
"""

import google.generativeai as genai
from typing import Dict, Any, List
import json
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ============================================================
# Main Agent 설정
# ============================================================

MAIN_CONFIG = {
    "model": "gemini-2.0-flash",
    "temperature": 0.7,  # 답변 생성에는 약간의 창의성 허용
    "max_output_tokens": 4096
}


# ============================================================
# 시스템 프롬프트
# ============================================================

MAIN_SYSTEM_PROMPT = """당신은 대한민국 최고의 입시 데이터 기반 AI 컨설턴트 [유니로드(UniRoad)]입니다.
사용자의 질문과 제공된 데이터를 분석하여, **스스로 가장 적절한 답변 구조를 설계하고** 모바일 가독성에 최적화된 답변을 작성하십시오.

## 1. 기본 원칙
- **시점:** 2026년 1월 (2026학년도 입시 진행 중)
- **톤앤매너:** 딱딱한 보고서체가 아닌, **정중하고 친절한 대화체(~해요, ~입니다)**
- **서식:**
  - **Markdown 강조(**, ##, > 등) 사용 금지.** 평문(Plain Text)만 사용.
  - 한 섹션 안에 4줄을 넘지 않을 것. 여러 가지 정보를 제시하는 경우 글머리 기호(•) 사용.
- **데이터 인용:** 근거 자료 활용 시 문장 끝에 `<cite data-source="자료명" data-url="URL">내용</cite>` 태그 필수.

## 2. 답변 구조 설계 가이드 (Planner Logic)
질문의 성격에 따라 아래 **[가용 섹션]** 중 1~5개를 선택하여 논리적인 흐름을 구성하십시오.

**[가용 섹션 목록]**
1. `empathy`: (필수 권장) 학생의 마음을 읽는 첫인사 및 공감
2. `fact_check`: 단순 데이터/수치 제공 (경쟁률, 입결 등)
3. `analysis`: 학생 점수와 데이터 간의 비교/유불리 분석
4. `recommendation`: 구체적인 전략이나 대학 추천
5. `warning`: 지원 불가 사유 또는 리스크 안내
6. `encouragement`: (필수 권장) 마무리 격려 및 응원
7. `next_step`: 다음에 확인해야 할 행동 지침

**[상황별 권장 구조]**
- **단순 정보 문의:** `empathy` → `fact_check` → `next_step`
- **합불 가능성 진단:** `empathy` → `analysis` → `recommendation` → `encouragement`
- **부정적 결과 통보:** `empathy` → `analysis` (완곡하게) → `warning` → `encouragement`
- **가벼운 인사:** `empathy` → `next_step`

## 3. 섹션별 작성 지침 (Writer Logic)

**(1) 분석형 (fact_check, analysis, recommendation, warning)**
- **형식:** 반드시 첫 줄에 `【제목】`을 적고 줄바꿈 후 본문 작성.
- **내용:** "유리하다" 같은 모호한 표현 대신, "작년 컷(392점)보다 3점 높아 안정적입니다"처럼 **수치 중심**으로 설명.

**(2) 소통형 (empathy, encouragement, next_step)**
- **형식:** `【제목】` 절대 금지. 본문만 작성.
- **내용:** 따뜻하고 진정성 있는 멘토의 말투 유지.

## 4. 자료 선별 규칙
- 제공된 functions 결과에서 **질문과 직접 관련된 정보만** 선별하여 사용하세요.
- 여러 청크가 제공되더라도, 핵심적인 내용만 추출하여 간결하게 전달하세요.
- 불필요한 정보를 나열하지 마세요. 학생이 원하는 답에 집중하세요.
- 정보가 부족하거나 없는 경우, 솔직하게 안내하고 추가 질문을 유도하세요.

## 5. 출력 프로토콜 (SYSTEM CRITICAL)
시스템 파싱을 위해 아래 형식을 기계적으로 준수하십시오.
- 섹션 시작 시: `===SECTION_START:타입명===` (예: `===SECTION_START:analysis===`)
- 섹션 종료 시: `===SECTION_END===`
- **타입명**은 위 [가용 섹션 목록]에 있는 영어 소문자 코드만 사용하십시오.

[출력 예시]
===SECTION_START:empathy===
지금 성적 때문에 고민이 많으시군요. 하지만 아직 포기하기엔 일러요. 같이 전략을 찾아봐요.
===SECTION_END===
===SECTION_START:analysis===
【고려대 경영학과 환산점수 분석】
학생의 환산점수는 687.4점입니다.
• 작년 합격 컷(680점)보다 +7.4점 높아 최초 합격 가능성이 높습니다.
• 다만 경쟁률이 3:1을 넘어가면 변수가 생길 수 있어요. <cite data-source="2025 입결" data-url="...">작년 컷 근거</cite>
===SECTION_END===
===SECTION_START:next_step===
이제 경쟁률 추이를 지켜보는 게 좋겠어요. 원서 접수 전날 다시 물어봐 주시겠어요?
===SECTION_END===
"""


# ============================================================
# Main Agent 클래스
# ============================================================

class MainAgent:
    """Main Agent - 최종 답변 생성"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=MAIN_CONFIG["model"],
            system_instruction=MAIN_SYSTEM_PROMPT
        )
        self.generation_config = {
            "temperature": MAIN_CONFIG["temperature"],
            "max_output_tokens": MAIN_CONFIG["max_output_tokens"]
        }
    
    def _format_function_results(self, function_results: Dict[str, Any]) -> str:
        """
        functions.py 결과를 프롬프트용 텍스트로 변환
        """
        if not function_results:
            return "검색된 자료가 없습니다."
        
        formatted_parts = []
        
        for key, result in function_results.items():
            if "error" in result:
                formatted_parts.append(f"[{key}] 오류: {result['error']}")
                continue
            
            if key.startswith("univ_"):
                # univ 함수 결과 포맷팅
                university = result.get("university", "")
                query = result.get("query", "")
                chunks = result.get("chunks", [])
                
                formatted_parts.append(f"\n### [{university}] 검색 결과 (쿼리: {query})")
                
                if not chunks:
                    formatted_parts.append("  - 관련 자료 없음")
                else:
                    for i, chunk in enumerate(chunks[:5], 1):  # 상위 5개만
                        content = chunk.get("content", "")[:500]  # 500자 제한
                        score = chunk.get("weighted_score", 0)
                        formatted_parts.append(f"\n[청크 {i}] (관련도: {score:.3f})")
                        formatted_parts.append(content)
            
            elif key.startswith("consult_"):
                # consult 함수 결과 포맷팅 (TODO: 구현 후 수정)
                formatted_parts.append(f"\n### [성적 분석 결과]")
                formatted_parts.append(json.dumps(result, ensure_ascii=False, indent=2))
        
        return "\n".join(formatted_parts)
    
    def _extract_citations(self, function_results: Dict[str, Any]) -> List[Dict]:
        """
        function_results에서 인용 가능한 출처 정보 추출
        """
        citations = []
        
        for key, result in function_results.items():
            if key.startswith("univ_"):
                university = result.get("university", "")
                chunks = result.get("chunks", [])
                
                for chunk in chunks:
                    section_id = chunk.get("section_id")
                    document_id = chunk.get("document_id")
                    
                    if section_id or document_id:
                        citations.append({
                            "university": university,
                            "section_id": section_id,
                            "document_id": document_id,
                            "page_number": chunk.get("page_number")
                        })
        
        return citations
    
    async def generate(
        self, 
        message: str, 
        history: List[Dict] = None,
        function_results: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        최종 답변 생성
        
        Args:
            message: 사용자 질문
            history: 기존 대화 내역
            function_results: functions.py 실행 결과
        
        Returns:
            {
                "response": str,  # 최종 답변 (섹션 태그 포함)
                "tokens": {"in": int, "out": int, "total": int},
                "citations": List[Dict]
            }
        """
        # 히스토리 구성
        gemini_history = []
        if history:
            for msg in history[-10:]:  # 최근 10개
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
                    gemini_history.append({"role": role, "parts": [content]})
        
        # 함수 결과 포맷팅
        results_text = self._format_function_results(function_results or {})
        citations = self._extract_citations(function_results or {})
        
        # 최종 프롬프트 구성
        final_prompt = f"""
[사용자 질문]
{message}

[functions 결과 (Raw Data)]
{results_text}

[참고 문헌 목록]
{json.dumps(citations, ensure_ascii=False, indent=2)[:2000]}

위 자료를 바탕으로 사용자에게 최적의 답변을 생성해주세요.
"""
        
        chat = self.model.start_chat(history=gemini_history)
        
        try:
            response = chat.send_message(
                final_prompt,
                generation_config=self.generation_config
            )
            raw_response = response.text.strip()
            
            result = {
                "response": raw_response,
                "citations": citations
            }
            
            # 토큰 사용량
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                result["tokens"] = {
                    "in": getattr(usage, 'prompt_token_count', 0),
                    "out": getattr(usage, 'candidates_token_count', 0),
                    "total": getattr(usage, 'total_token_count', 0)
                }
            
            return result
            
        except Exception as e:
            return {
                "response": "",
                "error": str(e),
                "citations": []
            }


# ============================================================
# 싱글톤
# ============================================================

_main_agent = None

def get_main_agent() -> MainAgent:
    global _main_agent
    if _main_agent is None:
        _main_agent = MainAgent()
    return _main_agent


async def generate_response(
    message: str, 
    history: List[Dict] = None,
    function_results: Dict[str, Any] = None
) -> Dict[str, Any]:
    """편의 함수"""
    agent = get_main_agent()
    return await agent.generate(message, history, function_results)


# ============================================================
# 테스트
# ============================================================

async def _test():
    print("=" * 60)
    print("Main Agent 테스트")
    print("=" * 60)
    
    agent = MainAgent()
    
    # 테스트용 가짜 function_results
    mock_results = {
        "univ_0": {
            "university": "고려대학교",
            "query": "2026학년도 정시 경영학과",
            "count": 2,
            "chunks": [
                {
                    "chunk_id": 1,
                    "content": "고려대학교 경영학과 2026학년도 정시 모집인원: 50명, 2025학년도 입결: 평균 690점",
                    "weighted_score": 0.85,
                    "section_id": "section_1",
                    "document_id": 100,
                    "page_number": 5
                },
                {
                    "chunk_id": 2,
                    "content": "반영비율: 국어 25%, 수학 30%, 영어 20%, 탐구 25%",
                    "weighted_score": 0.78,
                    "section_id": "section_2",
                    "document_id": 100,
                    "page_number": 6
                }
            ]
        }
    }
    
    test_message = "고려대 경영학과 정시 어떻게 해야 해요?"
    
    print(f"\n질문: {test_message}")
    print("\n답변 생성 중...")
    
    result = await agent.generate(
        message=test_message,
        history=[],
        function_results=mock_results
    )
    
    print("\n" + "=" * 40)
    print("생성된 답변:")
    print(result.get("response", ""))
    
    if "tokens" in result:
        t = result["tokens"]
        print(f"\n토큰: {t['total']} (입력 {t['in']}, 출력 {t['out']})")
    
    if "error" in result:
        print(f"오류: {result['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
