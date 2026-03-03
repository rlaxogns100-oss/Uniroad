"""
Main Agent Thinking (ReAct Pattern)
- Router Agent의 검색 결과를 분석하여 답변 또는 재질문 결정
- 재질문 시 Router에게 자연어로 추가 검색 요청
- Model: gemini-2.5-flash-preview-05-20
"""

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from typing import Dict, Any, List, Callable, Optional
import json
import os
import re
import asyncio
from dotenv import load_dotenv

from services.multi_agent.functions import execute_function_calls
from services.multi_agent.router_agent import RouterAgent

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ============================================================
# 설정
# ============================================================

THINKING_CONFIG = {
    "model": "gemini-3-flash-preview",
    "temperature": 0.7,
    "max_output_tokens": 8192,
    "max_output_tokens_large": 40960,
    "max_iterations": 3  # 최대 재질문 횟수
}


# ============================================================
# 시스템 프롬프트
# ============================================================

THINKING_SYSTEM_PROMPT = """당신은 대한민국 최고의 입시 데이터 기반 AI 컨설턴트 [유니로드(UniRoad)]입니다.

## [최우선 규칙: 재질문 판단]
검색 결과를 분석하여 **답변할지, 재질문할지** 결정하세요.

### 재질문이 필요한 경우 (===NEED_MORE_INFO===)
- 질문에서 요구한 **구체적인 수치/등급/점수**가 검색 결과에 없을 때
- 전형 목록만 있고 **세부 조건**이 없을 때
- 여러 대학/전형을 비교해야 하는데 **일부만 검색**되었을 때
- 주어진 정보가 일반적이지 않을 때(예, 고려대 2.7등급, 중앙대 4등급 등 일반적이지 않은 커트라인은 추천하기 전 해당 학교 요강을 확인하여 과학고, 기회균형, 유공자 등의 특수전형이 아닌지 확인)
- consult_susi/consult_jungsi 결과로 대학을 추천할 때, 해당 대학의 세부 전형 정보(수능최저, 반영비율, 모집인원 등)가 없으면 재질문

### 바로 답변하는 경우 (===SECTION_START===)
- 질문에 필요한 **모든 정보가 검색 결과에 있을 때**
- 단순 인사/일반 질문일 때
- 이미 2회 이상 재질문했을 때 (있는 정보로 답변)

## [consult 결과 처리 규칙]
consult_susi 또는 consult_jungsi 결과가 있을 때:
1. 추천된 대학/학과 목록을 확인
2. 각 대학의 **세부 전형 정보**(수능최저, 반영비율, 모집인원, 경쟁률 등)가 검색 결과에 있는지 확인
3. 세부 정보가 없으면 ===NEED_MORE_INFO===로 해당 대학의 입시요강을 추가 검색 요청
4. 예시: "서울대학교 경영학과 정시 반영비율과 수능최저 알려줘"
5. 이외에 학생 성적으로 갈 수 있는 대학이 없는 경우 판단하여 성적을 올려서 다시 질문

## [출력 형식]

### CASE 1: 재질문 필요
===NEED_MORE_INFO===
(Router에게 보낼 구체적인 질문 - 자연어로 작성)


===SECTION_START:empathy===
(답변 내용)
===SECTION_END===

---

===SECTION_START:fact_check===
【제목】
(답변 내용)
===SECTION_END===

---

===SECTION_START:encouragement===
(답변 내용)
===SECTION_END===

## [답변 작성 규칙 - 재질문 없이 답변할 때만 적용]

### 기본 원칙
- **시점:** 2026년 1월 (2026학년도 입시 진행 중)
- **톤앤매너:** 정중하고 친절한 대화체(~해요, ~입니다)
- **서식:**
  - **볼드체 강조**: 수치, 대학명, 학과명, 전형명, 핵심 단어는 **별 두개**로 감싸서 강조
  - Markdown 강조(##, > 등) 사용 금지. 평문만 사용.
  - 한 섹션 4줄 이내. 여러 정보는 글머리 기호(•) 사용.
- **데이터 인용:** `<cite data-source="문서제목 페이지p" data-url="PDF_URL">인용 내용</cite>` 형태로 감싸기
- **섹션 구분:** 각 섹션 사이에 반드시 빈 줄 + --- + 빈 줄 형태로 구분선 삽입

### 가용 섹션 목록
1. `empathy`: 공감 인사 (제목 없이 본문만)
2. `fact_check`: 데이터/수치 제공 (【제목】 필수)
3. `analysis`: 비교/분석 (【제목】 필수)
4. `recommendation`: 전략/추천 (【제목】 필수)
5. `warning`: 리스크 안내 (【제목】 필수)
6. `encouragement`: 마무리 격려 (제목 없이 본문만)
7. `next_step`: 다음 행동 지침 (제목 없이 본문만)

### 상황별 권장 구조
- **단순 정보 문의:** empathy → fact_check → next_step
- **합불 가능성 진단:** empathy → analysis → recommendation → encouragement
- **부정적 결과:** empathy → analysis → warning → encouragement

## [Few-shot 예시]

### 예시 1: 재질문 필요 (구체적 등급 없음)
질문: "연세대 수시 전형별 수능최저 알려줘"
검색 결과: "적용 전형: 학생부교과(추천형), 학생부종합(활동우수형)..."

===NEED_MORE_INFO===
연세대학교 학생부교과(추천형), 학생부종합(활동우수형), 학생부종합(국제형-국내고) 전형 각각의 수능최저등급 기준을 알려줘

### 예시 2: 바로 답변 (정보 충분) - 섹션 사이 구분선 필수!
질문: "연세대 수시 전형별 수능최저 알려줘"
검색 결과: "학생부교과(추천형) 인문: 국수 중 1개 포함 2개 합 4, 영어 3등급..."

===SECTION_START:empathy===
연세대 수시 전형별 수능최저를 정리해 드릴게요!
===SECTION_END===

---

===SECTION_START:fact_check===
【연세대학교 2026학년도 수시 수능최저학력기준】
• **논술전형** 수학 중 1개 포함 **2개 등급 합 5** 이내
<cite data-source="2026 연세대 수시모집요강 15p" data-url="...">
• **학생부교과(추천형)**
  - 인문: 국어, 수학 중 1개 포함 **2개 등급 합 4** 이내, 영어 **3등급**, 한국사 **4등급**
  - 자연: 수학 포함 **2개 등급 합 5** 이내, 영어 **3등급**, 한국사 **4등급**
</cite>
• **학생부종합(활동우수형)** 최저 없음.
===SECTION_END===

---

===SECTION_START:encouragement===
추가로 궁금한 전형이 있으면 말씀해 주세요!
===SECTION_END===

### 예시 3: 재질문 필요 (일부 대학만 검색됨)
질문: "SKY 경영학과 정시 반영비율 비교해줘"
검색 결과: 서울대 경영학과 반영비율만 있음

===NEED_MORE_INFO===
연세대학교 경영학과 정시 반영비율, 고려대학교 경영학과 정시 반영비율 알려줘

### 예시 4: 재질문 필요 (consult 결과만 있고 세부 전형 정보 없음)
질문: "내 성적으로 갈 수 있는 수시 대학 추천해줘"
검색 결과: consult_susi 결과로 "서울대 경영학과, 연세대 경영학과, 고려대 경영학과" 추천됨 (세부 전형 정보 없음)

===NEED_MORE_INFO===
서울대학교 경영학과 수시 전형별 수능최저와 내신 반영방법, 연세대학교 경영학과 수시 전형별 수능최저와 내신 반영방법, 고려대학교 경영학과 수시 전형별 수능최저와 내신 반영방법 알려줘

### 예시 5: 바로 답변 (consult 결과 + 세부 전형 정보 모두 있음)
질문: "내 성적으로 갈 수 있는 정시 대학 추천해줘"
검색 결과: consult_jungsi 결과 + 각 대학의 반영비율, 수능최저, 모집인원 정보 모두 있음

===SECTION_START:empathy===
성적을 분석하여 정시 지원 가능 대학을 추천해 드릴게요!
===SECTION_END===

---

===SECTION_START:analysis===
【정시 지원 가능 대학 분석】
(분석 내용...)
===SECTION_END===
"""


# ============================================================
# MainAgentThinking 클래스
# ============================================================

class MainAgentThinking:
    """ReAct 패턴 기반 Thinking Agent - Router 재질문 방식"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=THINKING_CONFIG["model"],
            system_instruction=THINKING_SYSTEM_PROMPT
        )
        self.generation_config = {
            "temperature": THINKING_CONFIG["temperature"],
            "max_output_tokens": THINKING_CONFIG["max_output_tokens"],
        }
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        # Router Agent 인스턴스
        self.router = RouterAgent()
    
    def _format_function_results(self, function_results: Dict[str, Any]) -> str:
        """functions.py 결과를 프롬프트용 텍스트로 변환"""
        if not function_results:
            return "검색된 자료가 없습니다."
        
        formatted_parts = []
        
        for key, result in function_results.items():
            if "error" in result:
                formatted_parts.append(f"[{key}] 오류: {result['error']}")
                continue
            
            if key.startswith("univ_"):
                university = result.get("university", "")
                query = result.get("query", "")
                chunks = result.get("chunks", [])
                
                formatted_parts.append(f"\n### [{university}] 검색 결과 (쿼리: {query})")
                
                if not chunks:
                    formatted_parts.append("  - 관련 자료 없음")
                else:
                    doc_titles = result.get("document_titles", {})
                    doc_urls = result.get("document_urls", {})
                    
                    for i, chunk in enumerate(chunks, 1):
                        doc_id = chunk.get("document_id")
                        title = doc_titles.get(doc_id, f"문서 {doc_id}")
                        url = doc_urls.get(doc_id, "")
                        page = chunk.get("page_number", "")
                        content = chunk.get("content", "")
                        
                        source_info = f"{title} {page}p" if page else title
                        formatted_parts.append(f"\n[청크 {i}] 출처: {source_info} | URL: {url}")
                        formatted_parts.append(content)
            
            elif key.startswith("consult_"):
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
                        
                        source_info = title
                        formatted_parts.append(f"\n[청크 {i}] 출처: {source_info} | URL: {url}")
                        formatted_parts.append(content)
                
                target_univ = result.get("target_univ", [])
                target_major = result.get("target_major", [])
                if target_univ or target_major:
                    formatted_parts.append(f"\n**분석 대상:** 대학 [{', '.join(target_univ) if target_univ else '전체'}] / 학과 [{', '.join(target_major) if target_major else '전체'}]")
        
        return "\n".join(formatted_parts)
    
    def _extract_citations(self, function_results: Dict[str, Any]) -> List[Dict]:
        """
        function_results에서 인용 가능한 출처 정보 추출
        document_id 기준으로 중복 제거 (페이지 정보는 청크 내용에서 확인 가능)
        """
        citations = []
        seen_docs = set()  # (university, document_id) 기준 중복 체크
        
        for key, result in function_results.items():
            if key.startswith("univ_") or key.startswith("consult_"):
                university = result.get("university", "")
                doc_titles = result.get("document_titles", {})
                doc_urls = result.get("document_urls", {})
                
                # document_titles 기준으로 순회 (중복 없이 문서 단위로)
                for doc_id, title in doc_titles.items():
                    # 중복 체크
                    doc_key = (university, str(doc_id))
                    if doc_key in seen_docs:
                        continue
                    seen_docs.add(doc_key)
                    
                    url = doc_urls.get(doc_id) or doc_urls.get(str(doc_id)) or ""
                    
                    citations.append({
                        "university": university,
                        "document_id": doc_id,
                        "title": title,
                        "url": url
                    })
        
        return citations
    
    def _extract_follow_up_query(self, text: str) -> Optional[str]:
        """===NEED_MORE_INFO=== 이후의 재질문 추출"""
        if "===NEED_MORE_INFO===" not in text:
            return None
        
        parts = text.split("===NEED_MORE_INFO===")
        if len(parts) > 1:
            follow_up = parts[1].strip()
            # 다음 마커가 있으면 그 전까지만
            for marker in ["===SECTION_START", "===NEED_MORE_INFO"]:
                if marker in follow_up:
                    follow_up = follow_up.split(marker)[0].strip()
            return follow_up if follow_up else None
        return None
    
    def _post_process_sections(self, text: str) -> str:
        """
        섹션 마커 제거 및 cite 태그 정리
        main_agent.py와 동일 + NEED_MORE_INFO 제거 + 구분선 형식 통일
        """
        # 0. NEED_MORE_INFO 블록 제거 (thinking 전용)
        text = re.sub(r'===NEED_MORE_INFO===.*?(?====SECTION_START|$)', '', text, flags=re.DOTALL)
        
        # 1. 섹션 마커 추출 및 처리
        section_pattern = r'===SECTION_START(?::\w+)?===\s*(.*?)\s*===SECTION_END==='
        sections = re.findall(section_pattern, text, re.DOTALL)
        
        if not sections:
            # 섹션 마커가 없으면 마커 패턴만 제거하고 반환
            cleaned = re.sub(r'===SECTION_(START|END)(:\w+)?===\s*', '', text)
            # 구분선 형식 통일: ---를 \n\n---\n\n로 변환
            cleaned = re.sub(r'\n*---\n*', '\n\n---\n\n', cleaned)
            # 연속된 줄바꿈 정리 (3개 이상 -> 2개)
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            return cleaned.strip()
        
        # 2. 각 섹션 정리
        cleaned_sections = []
        for section in sections:
            # 타이틀의 ** 볼드 마크다운 제거 (【제목】 형식에서)
            # 【**제목**】 -> 【제목】
            section = re.sub(r'【\*\*(.+?)\*\*】', r'【\1】', section)
            # **【제목】** -> 【제목】
            section = re.sub(r'\*\*【(.+?)】\*\*', r'【\1】', section)
            
            # 불완전한 마크다운 블록 정리 (```로 시작했는데 닫히지 않은 경우)
            # 열린 코드블록 개수와 닫힌 코드블록 개수 확인
            open_blocks = section.count('```')
            if open_blocks % 2 != 0:
                # 홀수면 마지막에 닫는 태그 추가
                section = section + '\n```'
            
            # 연속된 줄바꿈 정리 (3개 이상 -> 2개)
            section = re.sub(r'\n{3,}', '\n\n', section)
            # 앞뒤 공백 제거
            section = section.strip()
            if section:
                cleaned_sections.append(section)
        
        # 3. 섹션들을 섹션 마커로 연결 (프론트엔드에서 처리)
        # 일반 모드와 동일한 형식: ===SECTION_END===\n===SECTION_START===
        result = '\n===SECTION_END===\n===SECTION_START===\n'.join(cleaned_sections)
        # 첫 번째 섹션 앞에 시작 마커, 마지막 섹션 뒤에 종료 마커 추가
        if result:
            result = '===SECTION_START===\n' + result + '\n===SECTION_END==='
        
        # 4. 최종 정리 - 연속 공백 제거
        result = re.sub(r' {2,}', ' ', result)
        
        # 5. 불완전한 cite 태그 정리 (열린 태그가 닫히지 않은 경우)
        result = re.sub(r'<cite[^>]*>(?![^<]*</cite>)', '', result)
        
        return result.strip()
    
    def _merge_results(self, accumulated: Dict[str, Any], new_results: Dict[str, Any]) -> Dict[str, Any]:
        """검색 결과 병합 (누적) - chunks, document_titles, document_urls, document_summaries 모두 병합"""
        for key, value in new_results.items():
            if key in accumulated:
                # 기존 청크에 새 청크 추가 (중복 제거)
                existing_chunks = accumulated[key].get("chunks", [])
                new_chunks = value.get("chunks", [])
                
                # chunk_id 기준 중복 제거
                existing_ids = {c.get("chunk_id") for c in existing_chunks}
                for chunk in new_chunks:
                    if chunk.get("chunk_id") not in existing_ids:
                        existing_chunks.append(chunk)
                
                accumulated[key]["chunks"] = existing_chunks
                
                # document_titles 병합 (새 문서 정보 추가)
                existing_titles = accumulated[key].get("document_titles", {})
                new_titles = value.get("document_titles", {})
                existing_titles.update(new_titles)
                accumulated[key]["document_titles"] = existing_titles
                
                # document_urls 병합 (새 문서 URL 추가)
                existing_urls = accumulated[key].get("document_urls", {})
                new_urls = value.get("document_urls", {})
                existing_urls.update(new_urls)
                accumulated[key]["document_urls"] = existing_urls
                
                # document_summaries 병합
                existing_summaries = accumulated[key].get("document_summaries", {})
                new_summaries = value.get("document_summaries", {})
                existing_summaries.update(new_summaries)
                accumulated[key]["document_summaries"] = existing_summaries
            else:
                accumulated[key] = value
        
        return accumulated
    
    def generate_stream(
        self,
        message: str,
        history: List[Dict] = None,
        initial_results: Dict[str, Any] = None,
        log_callback: Callable[[str], None] = None
    ):
        """
        스트리밍 ReAct Loop 실행
        
        Args:
            message: 사용자 질문
            history: 대화 히스토리
            initial_results: Router의 1차 검색 결과
            log_callback: 로그 콜백 함수 (SSE 전송용)
        
        Yields:
            dict: {"type": "log"|"text"|"done", ...}
        """
        import time
        
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            print(msg)
        
        # 1차 쿼리/검색은 chat.py에서 이미 전송했으므로 여기서는 생략
        # (chat.py의 router_complete, search_complete 로그 사용)
        log("🧠 [Thinking Mode] 검색 결과 분석 시작...")
        
        # 히스토리 구성
        gemini_history = []
        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
                    gemini_history.append({"role": role, "parts": [content]})
        
        # 누적 검색 결과
        accumulated_results = initial_results.copy() if initial_results else {}
        max_iterations = THINKING_CONFIG["max_iterations"]
        
        for iteration in range(max_iterations):
            # iteration 0은 이미 1차 쿼리/검색이 완료된 상태이므로 분석만 진행
            log(f"\n🔄 [Iteration {iteration + 1}/{max_iterations}]")
            
            # 프롬프트 구성
            results_text = self._format_function_results(accumulated_results)
            citations = self._extract_citations(accumulated_results)
            
            prompt = f"""[사용자 질문]
{message}

[검색 결과 (총 {iteration + 1}차)]
{results_text}

[참고 문헌 - cite 태그 작성 시 아래 URL을 정확히 사용하세요]
{json.dumps(citations, ensure_ascii=False, indent=2)}

위 검색 결과를 분석하세요.
- 정보가 충분하면 ===SECTION_START===로 답변
- 정보가 부족하면 ===NEED_MORE_INFO===로 재질문
- 이미 {iteration + 1}회 검색했으므로, 가능하면 있는 정보로 답변하세요."""
            
            # 모델 호출
            chat = self.model.start_chat(history=gemini_history)
            
            gen_config = self.generation_config.copy()
            if any("consult" in k for k in accumulated_results.keys()):
                gen_config["max_output_tokens"] = THINKING_CONFIG["max_output_tokens_large"]
            
            try:
                response = chat.send_message(
                    prompt,
                    generation_config=gen_config,
                    safety_settings=self.safety_settings
                )
                
                if not response.candidates or not response.candidates[0].content.parts:
                    log(f"⚠️ 응답이 비어있습니다. 재시도...")
                    continue
                
                raw_text = response.text.strip()
            except Exception as e:
                log(f"❌ 모델 호출 오류: {e}")
                yield {"type": "error", "message": str(e)}
                return
            
            # 재질문 감지
            follow_up_query = self._extract_follow_up_query(raw_text)
            
            if follow_up_query and iteration < max_iterations - 1:
                log(f"🔍 재질문 감지: {follow_up_query[:100]}...")
                
                # ========================================
                # 재질문 루프: iteration별 상세 로그
                # ========================================
                next_iteration = iteration + 2  # 다음 iteration 번호 (2차 또는 3차)
                
                try:
                    loop = asyncio.new_event_loop()
                    router_result = loop.run_until_complete(
                        self.router.route(follow_up_query, history=[])
                    )
                    
                    function_calls = router_result.get("function_calls", [])
                    
                    # 쿼리 정보 추출
                    queries = []
                    for call in function_calls:
                        func_name = call.get("function", "")
                        params = call.get("params", {})
                        if func_name == "univ":
                            queries.append({
                                "type": "univ",
                                "university": params.get("university", ""),
                                "query": params.get("query", "")
                            })
                        elif func_name == "consult":
                            queries.append({
                                "type": "consult",
                                "target_univ": params.get("target_univ", [])
                            })
                    
                    # N차 쿼리 생성 완료 로그
                    yield {
                        "type": "log",
                        "content": f"추가로 {len(queries)}개의 검색 쿼리를 생성했습니다.",
                        "step": "query_complete",
                        "iteration": next_iteration,
                        "detail": {"queries": queries, "count": len(queries)}
                    }
                    log(f"   📋 {next_iteration}차 쿼리 생성: {len(function_calls)}개 함수 호출")
                    
                    # Functions 실행
                    if function_calls:
                        new_results = loop.run_until_complete(
                            execute_function_calls(function_calls)
                        )
                        
                        # 결과 누적
                        accumulated_results = self._merge_results(accumulated_results, new_results)
                        result_count = sum(len(r.get("chunks", [])) for r in new_results.values())
                        
                        # 검색 결과 상세 정보 추출
                        search_results = []
                        for key, res in new_results.items():
                            univ = res.get("university", "")
                            doc_titles = res.get("document_titles", {})
                            chunks = res.get("chunks", [])
                            if doc_titles:
                                documents = list(set(doc_titles.values()))[:5]
                                search_results.append({
                                    "university": univ,
                                    "doc_count": len(chunks),
                                    "documents": documents
                                })
                        
                        # N차 검색 완료 로그
                        yield {
                            "type": "log",
                            "content": f"{result_count}개의 관련 자료를 찾았습니다.",
                            "step": "search_complete",
                            "iteration": next_iteration,
                            "detail": {"results": search_results, "total_count": result_count}
                        }
                        log(f"   ✅ {next_iteration}차 검색 완료: {result_count}개 청크")
                    
                    loop.close()
                except Exception as e:
                    log(f"   ❌ 재질문 처리 오류: {e}")
                
                continue  # 다음 iteration
            
            # 최종 답변 생성
            if "===SECTION_START" in raw_text:
                # 답변 작성하기 로그
                yield {
                    "type": "log",
                    "content": "수집한 정보를 종합하여 답변을 작성하고 있습니다.",
                    "step": "answer_start",
                    "iteration": iteration + 1
                }
                log("✅ 답변 생성 완료")
                
                final_response = self._post_process_sections(raw_text)
                
                yield {"type": "text", "content": final_response}
                yield {
                    "type": "done",
                    "citations": citations,
                    "iterations": iteration + 1,
                    "total_chunks": sum(len(r.get("chunks", [])) for r in accumulated_results.values())
                }
                return
            
            # 마커가 없으면 그냥 출력
            log("⚠️ 마커 없음, 원본 출력")
            yield {"type": "text", "content": raw_text}
            yield {"type": "done", "citations": [], "iterations": iteration + 1}
            return
        
        # max_iterations 도달
        log("⚠️ 최대 반복 횟수 도달, 현재 결과로 답변 생성")
        yield {
            "type": "log",
            "content": "수집한 정보를 종합하여 답변을 작성하고 있습니다.",
            "step": "answer_start",
            "iteration": max_iterations
        }
        yield {"type": "text", "content": "죄송합니다. 충분한 정보를 찾지 못했습니다. 질문을 더 구체적으로 해주시겠어요?"}
        yield {"type": "done", "citations": [], "iterations": max_iterations}


# ============================================================
# 싱글톤
# ============================================================

_thinking_agent = None

def get_thinking_agent() -> MainAgentThinking:
    global _thinking_agent
    if _thinking_agent is None:
        _thinking_agent = MainAgentThinking()
    return _thinking_agent


def generate_thinking_stream(
    message: str,
    history: List[Dict] = None,
    initial_results: Dict[str, Any] = None,
    log_callback: Callable[[str], None] = None
):
    """스트리밍 편의 함수"""
    agent = get_thinking_agent()
    for chunk in agent.generate_stream(message, history, initial_results, log_callback):
        yield chunk


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Main Agent Thinking 테스트")
    print("=" * 60)
    
    # 테스트용 가짜 initial_results (1차 검색 결과 - 불완전)
    mock_initial_results = {
        "univ_0": {
            "university": "연세대학교",
            "query": "2026학년도 연세대학교 수시 수능최저",
            "chunks": [
                {
                    "chunk_id": 1,
                    "content": "수능 최저학력기준 적용 전형: 학생부교과(추천형), 학생부종합(활동우수형), 학생부종합(국제형-국내고)\n미적용 전형: 논술전형, 학생부종합(기회균형)",
                    "document_id": 100,
                    "page_number": 10
                }
            ],
            "document_titles": {100: "2026 연세대 수시모집요강"},
            "document_urls": {100: "https://example.com/yonsei.pdf"}
        }
    }
    
    test_message = "연세대 수시 전형별 수능최저 알려줘"
    
    print(f"\n질문: {test_message}")
    print("\n" + "-" * 40)
    
    for chunk in generate_thinking_stream(test_message, [], mock_initial_results):
        if chunk.get("type") == "log":
            print(f"[LOG] {chunk.get('content', '')}")
        elif chunk.get("type") == "text":
            print(f"\n[답변]\n{chunk.get('content', '')}")
        elif chunk.get("type") == "done":
            print(f"\n[완료] iterations: {chunk.get('iterations')}, chunks: {chunk.get('total_chunks')}")
        elif chunk.get("type") == "error":
            print(f"[ERROR] {chunk.get('message', '')}")
