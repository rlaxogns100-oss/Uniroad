"""
Main Agent
- 사용자 질문 + 검색된 자료를 토대로 최종 답변 생성
- Model: gemini-3-flash-preview
"""

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
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
    "model": "gemini-3-flash-preview",  # 표 해석 능력 향상을 위해 3-flash-preview 사용
    "temperature": 0.7,  # 입시 정보는 정확성 최우선 - 완전히 결정적 답변
    "max_output_tokens": 4096,  # 기본 토큰 제한 (consult는 동적으로 증가)
    "max_output_tokens_consult": 40960,  # consult 함수 전용 토큰 제한
    "top_p": 1.0,  # temperature 0이면 무시됨
    "top_k": 1  # 가장 확률 높은 토큰만 선택 (캐싱 영향 제거)
}


# ============================================================
# 시스템 프롬프트
# ============================================================

MAIN_SYSTEM_PROMPT = """[CRITICAL] 생각, 서론, 인사말 절대 금지. 바로 ===SECTION_START:===로 시작할 것.
Do NOT output any thinking process, introduction, or pleasantries. Start DIRECTLY with ===SECTION_START:===.

당신은 대한민국 최고의 입시 데이터 기반 AI 컨설턴트 [유니로드(UniRoad)]입니다.
사용자의 질문과 제공된 데이터를 분석하여, **스스로 가장 적절한 답변 구조를 설계하고** 모바일 가독성에 최적화된 답변을 작성하십시오.

## 최상위 규칙: 모든 데이터는 반드시 주어지는 자료에 기반해서 정확하게 쓰세요. 없는 정보는 쓰지 마세요.

## 1. 기본 원칙
- **시점:** 2026년 1월 (2026학년도 입시 진행 중)
- **톤앤매너:** 딱딱한 보고서체가 아닌, **정중하고 친절한 대화체(~해요, ~입니다)**
- **서식:**
  - **볼드체 강조. 구체적인 수치, 대학명, 과 이름, 전형 이름, 입시에 관련된 특수 단어(가군, 나군 등), 이외 핵심적인 단어 및 문구눈 별 두개로 감싸서 강조 표시하세요.**
    예시: **특징:** **경영대학** 내 **경영학과**, 회계학과와 달리 2학년 전공 선택 시 **자율 선택 대상에서 제외**되며, 입학 시 전공이 확정됩니다.
  - **위 볼드체 강조 이외의 경우 Markdown 강조(**, ##, > 등) 사용 금지.** 평문(Plain Text)만 사용.
  - 한 섹션 안에 4줄을 넘지 않을 것. 여러 가지 정보를 제시하는 경우 글머리 기호(•) 사용.
- **데이터 인용:** univ, consult 함수에서 가져온 사실적 내용을 `<cite data-source="문서제목 페이지p" data-url="PDF_URL">인용 내용</cite>` 형태로 감싸세요.
  - cite 태그 안의 내용이 그대로 화면에 표시됩니다. **내용을 중복해서 쓰지 마세요.**
  - 출처가 필요한 사실적 내용(수치, 날짜, 조건 등)을 cite로 감싸세요. **청크에 포함된 출처(title)와 URL을 그대로 사용하세요.**
  - 예시:
    ❌ 잘못된 예: `• **모집인원**: **12명** <cite>모집인원은 12명입니다.</cite>` (중복됨)
    ✅ 올바른 예: `<cite data-source="2026 경희대 정시 모집요강 16p" data-url="https://...">• **모집군**: **가군**\n• **수능위주 일반전형**: **12명**</cite>`

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
- **내용:** "유리하다" 같은 모호한 표현 대신, "작년 컷(392점)보다 3점 높아 안정적입니다", "해당 대학에서 가장 낮은 컷(심리학과, 395점)보다 2점 낮아 어렵습니다."처럼 **수치 중심**으로 설명.

**(2) 소통형 (empathy, encouragement, next_step)**
- **형식:** `【제목】` 절대 금지. 본문만 작성.
- **내용:** 따뜻하고 진정성 있는 멘토의 말투 유지.


- ** 종합적인 검증이 필요한 질문은 여러 청크를 모두 참고하세요

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
<cite data-source="2025 고려대 입시결과 12p" data-url="...">• 작년 합격 컷: **680점**
• 경쟁률 분기점: **3:1**</cite>
작년 컷보다 +7.4점 높아 최초 합격 가능성이 높습니다. 다만 경쟁률이 3:1을 넘어가면 변수가 생길 수 있어요.
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
            "max_output_tokens": MAIN_CONFIG["max_output_tokens"],
            "top_p": MAIN_CONFIG.get("top_p", 1.0),
            "top_k": MAIN_CONFIG.get("top_k", 1)
        }
        # Safety Settings - BLOCK_NONE으로 설정하여 필터 지연 방지
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
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
                    # document_titles 및 document_urls 가져오기
                    doc_titles = result.get("document_titles", {})
                    doc_urls = result.get("document_urls", {})
                    
                    for i, chunk in enumerate(chunks, 1):  # 토큰 기반으로 이미 필터링됨
                        doc_id = chunk.get("document_id")
                        title = doc_titles.get(doc_id, f"문서 {doc_id}")
                        url = doc_urls.get(doc_id, "")
                        page = chunk.get("page_number", "")
                        content = chunk.get("content", "")  # 전체 내용 전달
                        
                        # 출처 정보 포함 (URL도 추가)
                        source_info = f"{title} {page}p" if page else title
                        formatted_parts.append(f"\n[청크 {i}] 출처: {source_info} | URL: {url}")
                        formatted_parts.append(content)
            
            elif key.startswith("consult_"):
                # consult 함수 결과 포맷팅 (chunk 기반 - univ와 동일 구조)
                chunks = result.get("chunks", [])
                doc_titles = result.get("document_titles", {})
                doc_urls = result.get("document_urls", {})
                
                formatted_parts.append(f"\n### [성적 분석 결과]")
                
                if not chunks:
                    formatted_parts.append("  - 분석 결과 없음")
                else:
                    for i, chunk in enumerate(chunks, 1):
                        doc_id = chunk.get("document_id")
                        title = doc_titles.get(doc_id, f"문서 {doc_id}")
                        url = doc_urls.get(doc_id, "")
                        content = chunk.get("content", "")
                        
                        # 출처 정보 포함 (URL도 추가)
                        source_info = title
                        formatted_parts.append(f"\n[청크 {i}] 출처: {source_info} | URL: {url}")
                        formatted_parts.append(content)
                
                # 타겟 정보
                target_univ = result.get("target_univ", [])
                target_major = result.get("target_major", [])
                if target_univ or target_major:
                    formatted_parts.append(f"\n**분석 대상:** 대학 [{', '.join(target_univ) if target_univ else '전체'}] / 학과 [{', '.join(target_major) if target_major else '전체'}]")
        
        return "\n".join(formatted_parts)
    
    def _extract_citations(self, function_results: Dict[str, Any]) -> List[Dict]:
        """
        function_results에서 인용 가능한 출처 정보 추출 (URL 포함)
        univ와 consult 모두 chunk 기반으로 동일하게 처리
        """
        citations = []
        
        for key, result in function_results.items():
            # univ와 consult 모두 동일한 chunk 구조로 처리
            if key.startswith("univ_") or key.startswith("consult_"):
                university = result.get("university", "")
                chunks = result.get("chunks", [])
                doc_titles = result.get("document_titles", {})
                doc_urls = result.get("document_urls", {})
                
                for chunk in chunks:
                    section_id = chunk.get("section_id")
                    document_id = chunk.get("document_id")
                    page_number = chunk.get("page_number", "")
                    
                    if section_id or document_id:
                        title = doc_titles.get(document_id, f"문서 {document_id}")
                        url = doc_urls.get(document_id, "")
                        source_info = f"{title} {page_number}p" if page_number else title
                        
                        citations.append({
                            "university": university,
                            "section_id": section_id,
                            "document_id": document_id,
                            "page_number": page_number,
                            "title": title,
                            "url": url,
                            "source": source_info
                        })
        
        return citations
    
    def _format_document_summaries(self, function_results: Dict[str, Any]) -> str:
        """
        function_results에서 document_summaries 추출하여 텍스트 생성
        Main Agent가 올바른 출처인지 판단할 수 있도록 문서 설명 제공
        """
        summaries = []
        seen_docs = set()
        
        for key, result in function_results.items():
            if key.startswith("univ_"):
                university = result.get("university", "")
                doc_summaries = result.get("document_summaries", {})
                
                for doc_id, summary in doc_summaries.items():
                    if doc_id not in seen_docs and summary:
                        # summary에서 첫 200자만 사용 (프롬프트 토큰 절약)
                        short_summary = summary[:200] + "..." if len(summary) > 200 else summary
                        summaries.append(f"• [{university}] 문서 {doc_id}: {short_summary}")
                        seen_docs.add(doc_id)
        
        return "\n".join(summaries) if summaries else "문서 설명 없음"
    
    def _post_process_sections(self, text: str) -> str:
        """
        섹션 마커 제거 및 cite 태그 정리
        원본: final_agent.py의 _post_process_sections 메서드
        """
        import re
        
        # 1. 섹션 마커 추출 및 처리
        section_pattern = r'===SECTION_START(?::\w+)?===\s*(.*?)\s*===SECTION_END==='
        sections = re.findall(section_pattern, text, re.DOTALL)
        
        if not sections:
            # 섹션 마커가 없으면 마커 패턴만 제거하고 반환
            cleaned = re.sub(r'===SECTION_(START|END)(:\w+)?===\s*', '', text)
            return cleaned.strip()
        
        # 2. 각 섹션 정리
        cleaned_sections = []
        for section in sections:
            # 연속된 줄바꿈 정리 (3개 이상 -> 2개)
            section = re.sub(r'\n{3,}', '\n\n', section)
            # 앞뒤 공백 제거
            section = section.strip()
            if section:
                cleaned_sections.append(section)
        
        # 3. 섹션들을 두 줄 간격으로 연결
        result = '\n\n'.join(cleaned_sections)
        
        # 4. 최종 정리 - 연속 공백 제거
        result = re.sub(r' {2,}', ' ', result)
        
        return result.strip()
    
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
        document_summary = self._format_document_summaries(function_results or {})
        
        # 최종 프롬프트 구성
        final_prompt = f"""
[사용자 질문]
{message}

[언급된 문서 설명]
{document_summary}

[functions 결과 (Raw Data)]
{results_text}

[참고 문헌 목록]
{json.dumps(citations, ensure_ascii=False, indent=2)[:2000]}

위 자료를 바탕으로 사용자에게 최적의 답변을 생성해주세요.
"""
        
        chat = self.model.start_chat(history=gemini_history)
        
        # consult 함수 결과가 있으면 토큰 제한 증가
        has_consult = any(key.startswith("consult_") for key in (function_results or {}).keys())
        generation_config = self.generation_config.copy()
        if has_consult:
            generation_config["max_output_tokens"] = MAIN_CONFIG.get("max_output_tokens_consult", 40960)
        
        try:
            response = chat.send_message(
                final_prompt,
                generation_config=generation_config,
                safety_settings=self.safety_settings  # Safety Filter 비활성화
            )
            raw_response = response.text.strip()
            
            # 섹션 마커 제거 및 정리
            processed_response = self._post_process_sections(raw_response)
            
            result = {
                "response": processed_response,
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
    
    def generate_stream(
        self, 
        message: str, 
        history: List[Dict] = None,
        function_results: Dict[str, Any] = None
    ):
        """
        스트리밍 답변 생성 (동기 Generator)
        
        Args:
            message: 사용자 질문
            history: 기존 대화 내역
            function_results: functions.py 실행 결과
        
        Yields:
            str: 청크 단위 텍스트
        """
        import time
        
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
        document_summary = self._format_document_summaries(function_results or {})
        citations = self._extract_citations(function_results or {})
        
        # 최종 프롬프트 구성
        final_prompt = f"""
[사용자 질문]
{message}

[언급된 문서 설명]
{document_summary}

[functions 결과 (Raw Data)]
{results_text}

[참고 문헌 목록]
{json.dumps(citations, ensure_ascii=False, indent=2)[:2000]}

위 자료를 바탕으로 사용자에게 최적의 답변을 생성해주세요.
"""
        
        chat = self.model.start_chat(history=gemini_history)
        
        # consult 함수 결과가 있으면 토큰 제한 증가
        has_consult = any(key.startswith("consult_") for key in (function_results or {}).keys())
        generation_config = self.generation_config.copy()
        if has_consult:
            generation_config["max_output_tokens"] = MAIN_CONFIG.get("max_output_tokens_consult", 40960)
        
        try:
            # 스트리밍 모드로 호출
            start_time = time.time()
            first_chunk_time = None
            
            response = chat.send_message(
                final_prompt,
                generation_config=generation_config,
                safety_settings=self.safety_settings,  # Safety Filter 비활성화
                stream=True  # 스트리밍 활성화
            )
            
            full_response = ""
            for chunk in response:
                if chunk.text:
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        print(f"⚡ 첫 청크 도착: {(first_chunk_time - start_time):.3f}초")
                    
                    full_response += chunk.text
                    yield chunk.text
            
            total_time = time.time() - start_time
            print(f"✅ 스트리밍 완료: 총 {total_time:.3f}초, 응답 {len(full_response)}자")
            
        except Exception as e:
            print(f"❌ 스트리밍 오류: {e}")
            yield f"오류가 발생했습니다: {str(e)}"


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


def generate_response_stream(
    message: str, 
    history: List[Dict] = None,
    function_results: Dict[str, Any] = None
):
    """스트리밍 편의 함수 (동기 Generator)"""
    agent = get_main_agent()
    for chunk in agent.generate_stream(message, history, function_results):
        yield chunk


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
