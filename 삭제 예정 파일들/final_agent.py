"""
Final Agent
- Answer Structure(설계도)에 따라 Sub Agent 결과(재료)를 조립하여 최종 답변 생성
- 출처가 있는 정보는 <cite> 태그로 감싸서 표시
- 볼드 타이틀은 【】 기호로 표시
"""

import google.generativeai as genai
from typing import Dict, Any, List
import os
import re
from dotenv import load_dotenv
from .agent_prompts import get_final_agent_prompt
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from utils.token_logger import log_token_usage

load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 로그 콜백 (실시간 스트리밍용)
_log_callback = None

def set_log_callback(callback):
    """로그 콜백 설정"""
    global _log_callback
    _log_callback = callback

def _log(msg: str):
    """로그 출력 및 콜백 호출"""
    if _log_callback:
        _log_callback(msg)
    else:
        print(msg)


class FinalAgent:
    """Final Agent - 최종 답변 조립"""

    def __init__(self):
        self.name = "Final Agent"
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
        )

    def _post_process_sections(self, text: str) -> str:
        """
        섹션 마커를 제거하고 각 섹션 끝에 cite 태그를 정리
        
        동작:
        1. ===SECTION_START===...===SECTION_END=== 패턴을 찾음
        2. 각 섹션 내의 모든 cite 태그에서 data-source, data-url 수집
        3. 섹션 끝에 수집한 cite 태그들을 빈 태그로 추가 (중복 제거)
        4. 섹션 마커 제거하고 섹션들을 세 줄 바꿈으로 연결 (출처 포함 섹션 간 여백)
        """
        # 로그 추가
        _log("   [후처리] 원본 텍스트 길이: " + str(len(text)))
        _log("   [후처리] SECTION_START 개수: " + str(text.count("===SECTION_START===")))
        _log("   [후처리] SECTION_END 개수: " + str(text.count("===SECTION_END===")))
        
        # 디버깅: 원본 텍스트에 cite 태그가 몇 개나 있는지 확인
        all_cite_pattern = r'<cite[^>]*>'
        original_cite_count = len(re.findall(all_cite_pattern, text))
        _log(f"   [후처리] 원본에 있는 cite 태그 수: {original_cite_count}개")
        
        # 섹션 패턴 찾기
        section_pattern = r'===SECTION_START===(.*?)===SECTION_END==='
        
        sections = []
        for idx, match in enumerate(re.finditer(section_pattern, text, flags=re.DOTALL), 1):
            section_content = match.group(1).strip()
            
            # 빈 섹션 스킵
            if not section_content:
                _log(f"   [후처리] 섹션 #{idx}: 빈 섹션 발견, 스킵")
                continue
            
            # cite 태그 찾기 (data-url은 선택적)
            cite_pattern = r'<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>.*?</cite>'
            
            citations = []
            seen_documents = set()  # ✅ 같은 PDF 문서명 추적
            
            # 이 섹션에서 발견된 모든 cite 태그 수집
            cite_matches = list(re.finditer(cite_pattern, section_content, flags=re.DOTALL))
            _log(f"   [후처리] 섹션 #{idx}: cite 태그 {len(cite_matches)}개 발견")
            
            for cite_match in cite_matches:
                source = cite_match.group(1)
                url = cite_match.group(2) or ""  # data-url이 없으면 빈 문자열
                
                if not source:  # 빈 source 제외
                    continue
                
                # ✅ PDF 문서명 추출 (url 또는 source에서)
                doc_name = self._extract_document_name(url, source)
                
                # ✅ 같은 문서명이면 스킵 (섹션 내 중복 제거)
                if doc_name in seen_documents:
                    _log(f"   [후처리] 섹션 #{idx}: 중복 스킵 (문서: {doc_name}) → {source[:50]}...")
                    continue
                
                # ✅ 첫 번째 것만 추가
                seen_documents.add(doc_name)
                citations.append((source, url))
                _log(f"   [후처리] 섹션 #{idx}: 추가 (문서: {doc_name}) → {source[:50]}...")
            
            _log(f"   [후처리] 섹션 #{idx}: 중복 제거 후 {len(citations)}개 citation (같은 문서당 1개)")
            
            # 본문에서 cite 태그 모두 제거
            section_content_clean = re.sub(cite_pattern, '', section_content, flags=re.DOTALL)
            section_content_clean = section_content_clean.strip()
            
            # 섹션 끝에 cite 태그 추가
            if citations:
                cite_tags = '\n'.join([
                    f'<cite data-source="{source}" data-url="{url}"></cite>'
                    for source, url in citations
                ])
                final_section = section_content_clean + '\n' + cite_tags
            else:
                final_section = section_content_clean
            
            # 최종 확인: 빈 섹션이 아닌 경우에만 추가
            if final_section.strip():
                sections.append(final_section)
                _log(f"   [후처리] 섹션 #{idx} 완료 (본문: {len(section_content_clean)}자, cite: {len(citations)}개)")
        
        # 섹션이 없으면 원본 반환
        if not sections:
            _log("   [후처리] ⚠️ 섹션을 찾지 못함, 원본 반환")
            _log("   [후처리] 💡 LLM이 SECTION_START/END 마커를 안 넣었을 가능성 높음")
            return text.strip()
        
        # 섹션 간 세 줄 간격으로 연결 (출처 포함 섹션 아래 빈 줄 하나 추가)
        result = '\n\n\n'.join(sections)
        
        # 최종 결과에 있는 cite 태그 개수 확인
        final_cite_count = len(re.findall(all_cite_pattern, result))
        _log("   [후처리] 처리된 섹션 수: " + str(len(sections)))
        _log(f"   [후처리] 최종 cite 태그 수: {final_cite_count}개 (원본 {original_cite_count}개)")
        _log("   [후처리] 최종 텍스트 길이: " + str(len(result)) + "자")
        
        return result.strip()

    async def generate_final_answer(
        self,
        user_question: str,
        answer_structure: List[Dict],
        sub_agent_results: Dict[str, Any],
        custom_prompt: str = None,
        history: List[Dict] = None,
        timing_logger = None
    ) -> Dict[str, Any]:
        """
        Answer Structure에 따라 최종 답변 생성

        Args:
            user_question: 원래 사용자 질문
            answer_structure: Orchestration Agent가 만든 답변 구조
            sub_agent_results: Sub Agent들의 실행 결과
            custom_prompt: 커스텀 프롬프트 (선택)
            history: 대화 히스토리 (최근 10개 대화)
            timing_logger: 타이밍 로거 (선택)

        Returns:
            {
                "status": str,
                "final_answer": str,
                "sources": List[str],
                "source_urls": List[str],
                "metadata": Dict
            }
        """
        import time
        
        # 초상세 타이밍: Final Agent 시작
        final_timing = None
        llm_call = None
        if timing_logger:
            final_timing = timing_logger.start_final_agent()
        
        _log("")
        _log("="*80)
        _log("📝 Final Agent 실행")
        _log("="*80)
        
        # history를 user_question에 병합
        user_question_with_context = self._merge_history_with_question(user_question, history)
        
        if timing_logger:
            timing_logger.mark("final_history_merged")
        
        # 입력 데이터 검증 로그
        _log(f"🔍 [입력 검증]")
        _log(f"   user_question: {user_question[:100]}..." if len(user_question) > 100 else f"   user_question: {user_question}")
        _log(f"   history 대화 수: {len(history) if history else 0}")
        _log(f"   answer_structure 섹션 수: {len(answer_structure)}")
        _log(f"   sub_agent_results 키: {list(sub_agent_results.keys())}")
        _log(f"   custom_prompt 사용: {'✅ Yes' if custom_prompt else '❌ No (기본 prompt4 사용)'}")

        # Sub Agent 결과 정리 + 출처 정보 수집
        results_text, all_sources, all_source_urls, all_citations, all_chunks = self._format_sub_agent_results(sub_agent_results)
        
        if timing_logger:
            timing_logger.mark("final_results_formatted")

        # Answer Structure를 텍스트로 변환
        structure_text = self._format_answer_structure(answer_structure)
        
        if timing_logger:
            timing_logger.mark("final_structure_formatted")

        
        # 🔍 테스트 환경용 복사 가능한 데이터 출력
        import json as _json
        _log(f"")
        _log("=" * 80)
        _log("📋 [Final Agent 입력 데이터 - 테스트 환경에 복사 가능]")
        _log("=" * 80)
        
        # JSON 형식으로 출력 (복사해서 테스트 환경에 바로 사용 가능)
        test_data = {
            "user_question_with_context": user_question_with_context,
            "structure_text": structure_text,
            "results_text": results_text,
            "all_citations": all_citations
        }
        
        _log(f"\n--- 1. user_question_with_context ---")
        _log(user_question_with_context)
        _log(f"\n--- 2. structure_text ---")
        _log(structure_text)
        _log(f"\n--- 3. results_text ---")
        _log(results_text)
        _log(f"\n--- 4. all_citations (JSON) ---")
        _log(_json.dumps(all_citations, ensure_ascii=False, indent=2))
        _log("=" * 80)
        
        if timing_logger:
            timing_logger.mark("final_prompt_ready")

        # 프롬프트 가져오기
        if custom_prompt:
            _log(f"🎨 [커스텀 프롬프트 사용] 길이: {len(custom_prompt)}자")
            prompt = custom_prompt.format(
                user_question=user_question_with_context,
                structure_text=structure_text,
                results_text=results_text,
                all_citations="\n".join([str(c) for c in all_citations])
            )
        else:
            _log(f"📋 [기본 프롬프트 사용: prompt5]")
            prompt = get_final_agent_prompt(
                "prompt5",
                user_question=user_question_with_context,
                structure_text=structure_text,
                results_text=results_text,
                all_citations=all_citations
            )
        
        _log(f"   최종 프롬프트 길이: {len(prompt)}자")
        
        if timing_logger:
            timing_logger.mark("final_prompt_ready")

        try:
            # 초상세 타이밍: LLM 호출 시작
            if final_timing:
                llm_call = final_timing.start_llm_call("final_main", "gemini-2.5-flash-lite")
                llm_call.mark("prompt_ready")
                llm_call.set_metadata("prompt_length", len(prompt))
            
            if timing_logger:
                timing_logger.mark("final_api_sent")
            if llm_call:
                llm_call.mark("api_request_sent")
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 4096
                },
                request_options=genai.types.RequestOptions(
                    retry=None,
                    timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
                )
            )
            
            if timing_logger:
                timing_logger.mark("final_api_received")
            if llm_call:
                llm_call.mark("api_response_received")
                llm_call.set_metadata("response_length", len(response.text))

            # 토큰 사용량 기록
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                print(f"💰 토큰 사용량 (final_agent): {usage}")
                
                if llm_call:
                    llm_call.set_metadata("token_count", getattr(usage, 'total_token_count', 0))
                
                log_token_usage(
                    operation="최종답변생성",
                    prompt_tokens=getattr(usage, 'prompt_token_count', 0),
                    output_tokens=getattr(usage, 'candidates_token_count', 0),
                    total_tokens=getattr(usage, 'total_token_count', 0),
                    model="gemini-2.5-flash-lite",
                    details="Final Agent"
                )

            # 후처리: 섹션 마커 제거 및 cite 태그 정리
            raw_answer = response.text
            if llm_call:
                llm_call.mark("response_parsed")
            
            final_answer = self._post_process_sections(raw_answer)
            
            if timing_logger:
                timing_logger.mark("final_parsed")
            if llm_call:
                llm_call.mark("call_complete")

            # ⚠️ 환산점수가 포함된 응답이면 무조건 "수능 점수 변환 및 추정 방법" cite 태그 추가
            SCORE_GUIDE_URL = os.getenv(
                "SCORE_CONVERSION_GUIDE_URL",
                "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/efe55407-d51c-4cab-8c20-aabb2445ac2b.pdf"
            )
            if "환산" in final_answer and "수능 점수 변환 및 추정 방법" not in final_answer:
                final_answer += f'\n\n<cite data-source="수능 점수 변환 및 추정 방법" data-url="{SCORE_GUIDE_URL}"></cite>'
                all_sources.append("수능 점수 변환 및 추정 방법")
                all_source_urls.append(SCORE_GUIDE_URL)
                _log(f"   ✅ 환산점수 감지 → 점수 변환 방법 cite 태그 강제 추가")

            # 답변에서 실제 인용된 출처만 추출 (cite 태그 기반)
            used_chunks = []
            if all_chunks:
                used_chunks = self._extract_cited_chunks_only(final_answer, all_chunks)
            
            if timing_logger:
                timing_logger.mark("final_postprocessed")

            _log(f"   원본 답변 길이: {len(raw_answer)}자")
            _log(f"   후처리 답변 길이: {len(final_answer)}자")
            _log(f"   실제 인용된 청크 수: {len(used_chunks)}개 (중복 제거됨)")
            _log("="*80)

            # 초상세 타이밍: Final Agent 완료
            if final_timing:
                final_timing.complete()

            return {
                "status": "success",
                "final_answer": final_answer,
                "raw_answer": raw_answer,  # ✅ 원본 추가
                "sources": all_sources,
                "source_urls": all_source_urls,
                "used_chunks": used_chunks,  # 사용된 청크 추가
                "metadata": {
                    "sections_count": len(answer_structure),
                    "sub_agents_used": list(sub_agent_results.keys()),
                    "history_count": len(history) if history else 0
                }
            }

        except Exception as e:
            _log(f"❌ Final Agent 오류: {e}")
            return {
                "status": "error",
                "error": str(e),
                "final_answer": self._generate_fallback_answer(
                    user_question, answer_structure, sub_agent_results
                ),
                "sources": all_sources,
                "source_urls": all_source_urls,
                "used_chunks": [],
                "metadata": {}
            }

    def _extract_cited_chunks_only(self, answer: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        답변에서 <cite> 태그로 실제 인용된 출처만 추출합니다.
        ✅ 같은 PDF 문서는 1개만 반환 (중복 제거)
        
        Args:
            answer: 생성된 답변 (cite 태그 포함)
            chunks: 청크 목록 (citation 객체 리스트)
            
        Returns:
            실제 인용된 청크 목록 (같은 PDF당 1개씩만)
        """
        if not chunks or not answer:
            return []
        
        # 답변에서 <cite> 태그 파싱
        cite_pattern = r'<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>.*?</cite>'
        cited_sources = set()
        
        for match in re.finditer(cite_pattern, answer, flags=re.DOTALL):
            source = match.group(1)
            if source:
                cited_sources.add(source)
        
        if not cited_sources:
            _log(f"   ⚠️ 답변에 <cite> 태그가 없습니다. 출처 없이 답변 생성됨.")
            return []
        
        _log(f"   📋 답변에서 인용된 출처: {len(cited_sources)}개")
        for idx, source in enumerate(cited_sources, 1):
            _log(f"      {idx}. {source[:80]}...")
        
        # 인용된 출처에 해당하는 청크만 찾기 (같은 PDF 문서당 1개만!)
        cited_chunks = []
        seen_documents = set()  # ✅ 중복 제거용
        
        for item in chunks:
            # ✅ citation 구조 처리: { "chunk": {...}, "source": "...", "url": "..." }
            if isinstance(item, dict) and "chunk" in item:
                chunk = item["chunk"]
                citation_source = item.get("source", "")
                citation_url = item.get("url", "")
            else:
                chunk = item
                citation_source = ""
                citation_url = ""
            
            chunk_title = chunk.get('title', '')
            chunk_source = chunk.get('source', '')
            chunk_file_url = chunk.get('file_url', '')
            
            # ✅ 문서명 추출 (중복 체크용)
            doc_name = self._extract_document_name(chunk_file_url, chunk_title)
            
            # ✅ 이미 같은 문서가 있으면 스킵
            if doc_name in seen_documents:
                _log(f"      ⏭️ 중복 스킵: {doc_name}")
                continue
            
            # 청크의 출처가 cited_sources에 있는지 확인
            for cited_source in cited_sources:
                if (cited_source in chunk_title or 
                    chunk_title in cited_source or
                    cited_source in chunk_source or
                    chunk_source in cited_source or
                    cited_source in citation_source or
                    citation_source in cited_source):
                    
                    cited_chunks.append(chunk)
                    seen_documents.add(doc_name)
                    _log(f"      ✅ 선택: {doc_name}")
                    break
        
        _log(f"   ✅ 실제 인용된 청크: {len(cited_chunks)}개 (같은 PDF당 1개)")
        _log(f"   ⏭️ 스킵된 중복: {len(chunks) - len(cited_chunks)}개")
        return cited_chunks
    
    def _extract_document_name(self, file_url: str, title: str) -> str:
        """
        청크에서 문서명 추출 (같은 문서 구별용)
        
        Args:
            file_url: 파일 URL
            title: 청크 제목
            
        Returns:
            문서 고유 식별자 (파일명 또는 제목 기반)
        """
        # 1. file_url에서 PDF 파일명 추출 시도
        if file_url and '.pdf' in file_url.lower():
            # URL에서 파일명만 추출 (마지막 / 이후 부분)
            filename = file_url.split('/')[-1]
            # ?query 파라미터 제거
            filename = filename.split('?')[0]
            return filename
        
        # 2. title에서 문서 구별 (연도 + 학교 + 캠퍼스 + 전형 등으로 구별)
        # 예: "경희대 용인캠퍼스 2025학년도 정시 전형결과"
        if title:
            # 불필요한 공백 제거 및 정규화
            normalized_title = re.sub(r'\s+', '_', title.strip())
            return normalized_title[:100]  # 최대 100자로 제한
        
        # 3. 둘 다 없으면 기본값 (거의 없는 경우)
        return "unknown_document"

    def _find_relevant_chunks(self, answer: str, chunks: List[Dict[str, Any]], max_chunks: int = 3) -> List[Dict[str, Any]]:
        """
        답변 내용과 관련된 청크를 키워드 일치도로 찾습니다.
        문서에 참고해서 답변한 내용의 키워드와 청크의 키워드 일치도 점수가 높은 상위 3개만 반환합니다.
        
        Args:
            answer: 생성된 답변
            chunks: 검색된 모든 청크 목록
            max_chunks: 반환할 최대 청크 수 (기본값: 3)
            
        Returns:
            관련 청크 목록 (키워드 일치도 점수 순으로 정렬, 상위 3개)
        """
        if not chunks or not answer:
            return []
        
        answer_lower = answer.lower()
        
        # 답변에서 의미있는 키워드 추출 (2글자 이상, 불용어 제외)
        stopwords = {'것', '수', '있', '없', '그', '이', '저', '때', '등', '및', '또', '또한', '또는', '그리고', '하지만', '그러나', '따라서', '그래서', '그런데', '그런', '이런', '저런', '이렇게', '그렇게', '저렇게', '이것', '그것', '저것', '이것은', '그것은', '저것은', '이것이', '그것이', '저것이', '이것을', '그것을', '저것을', '이것에', '그것에', '저것에', '이것의', '그것의', '저것의', '이것으로', '그것으로', '저것으로', '이것에서', '그것에서', '저것에서', '이것까지', '그것까지', '저것까지', '이것과', '그것과', '저것과', '이것만', '그것만', '저것만', '이것도', '그것도', '저것도', '이것부터', '그것부터', '저것부터', '이것까지', '그것까지', '저것까지'}
        
        # 답변에서 키워드 추출 (2글자 이상 단어, 불용어 제외)
        answer_words = set()
        for word in re.findall(r'\b\w{2,}\b', answer_lower):
            if word not in stopwords and len(word) >= 2:
                answer_words.add(word)
        
        # 답변에서 구체적인 수치 추출 (경쟁률, 등급, 백분위 등)
        # 예: "19.3:1", "3.33등급", "13.1:1", "2.19등급" 등
        numbers_pattern = r'\d+\.?\d*[:\d]*'
        answer_numbers = set(re.findall(numbers_pattern, answer))
        
        # 핵심 키워드 목록 (입시 관련 중요 키워드)
        important_keywords = ['경쟁률', '등급', '컷', '백분위', '전형', '모집', '인원', '충원', '물리', '응용물리', '학과', '전형', '수시', '정시', '학생부', '내신', '성적', '합격', '지원', '입시', '대학', '캠퍼스']
        
        # 대학명 및 학과명 키워드
        university_keywords = ['서울대', '연세대', '고려대', '경희대', '성균관대', '한양대', '중앙대', '이화여대', '건국대', '동국대', '홍익대', '숙명여대', '국민대', '숭실대', '세종대', '단국대', '인하대', '아주대', '카이스트', '포스텍']
        
        # 각 청크와의 키워드 일치도 계산
        chunk_scores = []
        for chunk in chunks:
            chunk_content = chunk.get('content', '')
            chunk_content_lower = chunk_content.lower()
            
            # 청크에서 키워드 추출 (2글자 이상, 불용어 제외)
            chunk_words = set()
            for word in re.findall(r'\b\w{2,}\b', chunk_content_lower):
                if word not in stopwords and len(word) >= 2:
                    chunk_words.add(word)
            
            score = 0.0
            
            # 1. 구체적인 수치 매칭 (가장 중요) - 매우 높은 가중치
            chunk_numbers = set(re.findall(numbers_pattern, chunk_content))
            matching_numbers = answer_numbers & chunk_numbers
            if matching_numbers:
                # 수치가 일치하면 매우 높은 점수 (수치가 정확히 일치하는 것이 가장 중요)
                score += len(matching_numbers) * 50.0
                
                # 실제로 사용된 수치가 많을수록 더 높은 점수
                for num in matching_numbers:
                    # 답변과 청크에서 해당 수치 주변 텍스트도 비교
                    num_idx_answer = answer_lower.find(num)
                    num_idx_chunk = chunk_content_lower.find(num)
                    
                    if num_idx_answer >= 0 and num_idx_chunk >= 0:
                        # 수치 주변 30자 추출
                        num_context_answer = answer_lower[max(0, num_idx_answer-30):num_idx_answer+len(num)+30]
                        num_context_chunk = chunk_content_lower[max(0, num_idx_chunk-30):num_idx_chunk+len(num)+30]
                        
                        if num_context_answer and num_context_chunk:
                            # 주변 텍스트도 유사하면 추가 점수
                            context_words_answer = set(re.findall(r'\b\w{2,}\b', num_context_answer))
                            context_words_chunk = set(re.findall(r'\b\w{2,}\b', num_context_chunk))
                            common_context = context_words_answer & context_words_chunk
                            score += len(common_context) * 3.0
            
            # 2. 공통 키워드 매칭 (키워드 일치도)
            common_words = answer_words & chunk_words
            if common_words:
                # 키워드 일치도 점수 계산
                # - 공통 키워드 수
                # - 공통 키워드 비율 (답변 기준)
                # - 공통 키워드 비율 (청크 기준)
                common_count = len(common_words)
                answer_ratio = common_count / max(len(answer_words), 1)
                chunk_ratio = common_count / max(len(chunk_words), 1)
                
                # 키워드 일치도 점수 (가중 평균)
                keyword_match_score = (common_count * 2.0) + (answer_ratio * 10.0) + (chunk_ratio * 10.0)
                score += keyword_match_score
            
            # 3. 핵심 키워드 보너스 (입시 관련 중요 키워드)
            important_matches = sum(1 for kw in important_keywords if kw in chunk_content_lower and kw in answer_lower)
            score += important_matches * 5.0
            
            # 4. 대학명/학과명 매칭 보너스
            for univ in university_keywords:
                if univ in answer_lower and univ in chunk_content_lower:
                    score += 10.0
            
            # 5. 답변에 <cite> 태그가 있고, 해당 출처가 청크의 문서와 일치하면 추가 점수
            cite_pattern = r'<cite[^>]*data-source="([^"]*)"[^>]*>'
            cited_sources = set(re.findall(cite_pattern, answer))
            chunk_title = chunk.get('title', '').lower()
            for cited_source in cited_sources:
                if cited_source.lower() in chunk_title or chunk_title in cited_source.lower():
                    score += 20.0  # 출처가 명시적으로 일치하면 매우 높은 점수
            
            # 점수가 0보다 큰 청크만 추가
            if score > 0:
                chunk_scores.append((score, chunk))
        
        # 키워드 일치도 점수 순으로 정렬
        chunk_scores.sort(key=lambda x: x[0], reverse=True)
        
        # 상위 3개 청크만 반환 (점수가 높은 것만)
        relevant_chunks = [chunk for score, chunk in chunk_scores[:max_chunks] if score > 0]
        
        # 로그 출력
        if relevant_chunks:
            _log(f"   📊 키워드 일치도 점수:")
            for idx, (score, chunk) in enumerate(chunk_scores[:3], 1):
                chunk_title = chunk.get('title', '제목 없음')
                _log(f"      {idx}. {chunk_title[:50]}... (점수: {score:.2f})")
        
        return relevant_chunks

    def _merge_history_with_question(self, user_question: str, history: List[Dict] = None) -> str:
        """
        대화 히스토리를 사용자 질문에 병합
        
        Args:
            user_question: 현재 사용자 질문
            history: 대화 히스토리 리스트 [{role: str, content: str}, ...]
            
        Returns:
            맥락이 포함된 질문 문자열
        """
        if not history or len(history) == 0:
            return user_question
        
        # 최근 10개 대화로 제한 (20개 메시지 = user + assistant 쌍)
        recent_history = history[-20:] if len(history) > 20 else history
        
        # 히스토리 포맷팅
        history_lines = []
        for msg in recent_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                history_lines.append(f"[User] {content}")
            elif role == "assistant":
                # 답변은 너무 길면 잘라서 표시
                truncated = content[:300] + "..." if len(content) > 300 else content
                history_lines.append(f"[Assistant] {truncated}")
        
        if not history_lines:
            return user_question
        
        _log(f"   📜 [대화 맥락 병합] {len(recent_history)}개 메시지 포함")
        
        return f"""## 이전 대화 맥락
{chr(10).join(history_lines)}

## 현재 질문
{user_question}"""

    def _format_sub_agent_results(self, results: Dict[str, Any]) -> tuple:
        """
        Sub Agent 결과를 텍스트로 포맷하고 출처 정보 수집
        ⚠️ 중복 제거는 _post_process_sections에서 섹션별로 처리

        Returns:
            (formatted_text, sources, source_urls, citations, all_chunks)
        """
        formatted = []
        all_sources = []
        all_source_urls = []
        all_citations = []
        all_chunks = []  # 모든 청크 정보 (중복 제거 안 함)

        for step_key, result in results.items():
            agent_name = result.get("agent", "Unknown")
            status = result.get("status", "unknown")
            content = result.get("result", "결과 없음")
            sources = result.get("sources", [])
            source_urls = result.get("source_urls", [])
            citations = result.get("citations", [])

            # 출처 정보 수집
            all_sources.extend(sources)
            all_source_urls.extend(source_urls)
            all_citations.extend(citations)
            
            # 청크 정보 수집 (모두 수집, 섹션별 중복 제거는 나중에)
            for citation in citations:
                if isinstance(citation, dict) and "chunk" in citation:
                    all_chunks.append(citation)  # citation 전체 저장 { chunk, source, url }

            # 출처 정보를 결과에 포함
            source_info = ""
            if sources:
                source_info = f"\n[사용 가능한 출처: {', '.join(sources)}]"
                if source_urls:
                    for i, (src, url) in enumerate(zip(sources, source_urls)):
                        source_info += f"\n  - {src}: {url}"

            formatted.append(f"""### {step_key} ({agent_name})
상태: {status}

{content}
{source_info}
""")

        # 청크 수집 요약
        total_citations = len(all_citations)
        collected_chunks = len(all_chunks)
        _log(f"   📊 청크 수집 요약: {total_citations}개 citation → {collected_chunks}개 청크 (모두 수집, 섹션별 중복 제거는 나중에)")
        
        return "\n---\n".join(formatted), all_sources, all_source_urls, all_citations, all_chunks

    def _format_answer_structure(self, structure: List[Dict]) -> str:
        """Answer Structure를 텍스트로 포맷"""
        formatted = []

        for section in structure:
            sec_num = section.get("section", "?")
            sec_type = section.get("type", "unknown")
            title = section.get("title", "")
            source = section.get("source_from", "없음")
            instruction = section.get("instruction", "")
            
            formatted.append(f"""**섹션 {sec_num}** [{sec_type}]
- 타이틀: {title if title else "(타이틀 없음)"}
- 참조할 데이터: {source if source else "없음 (직접 작성)"}
- 지시사항: {instruction}""")

        return "\n\n".join(formatted)

    def _generate_fallback_answer(
        self,
        question: str,
        structure: List[Dict],
        results: Dict[str, Any]
    ) -> str:
        """오류 시 기본 답변 생성"""
        parts = []

        for section in structure:
            sec_type = section.get("type", "")
            instruction = section.get("instruction", "")
            source = section.get("source_from")

            if sec_type == "empathy":
                parts.append("질문해 주셔서 감사합니다. 입시 준비가 쉽지 않으시죠.")
            elif source and source in results:
                result = results[source].get("result", "")
                if result:
                    parts.append(result[:500])
            else:
                parts.append(instruction)

        return "\n\n".join(parts) if parts else "죄송합니다. 답변 생성 중 오류가 발생했습니다."


# 싱글톤 인스턴스
final_agent = FinalAgent()


async def generate_final_answer(
    user_question: str,
    answer_structure: List[Dict],
    sub_agent_results: Dict[str, Any],
    history: List[Dict] = None,
    timing_logger = None
) -> Dict[str, Any]:
    """Final Agent를 통해 최종 답변 생성"""
    return await final_agent.generate_final_answer(
        user_question=user_question,
        answer_structure=answer_structure,
        sub_agent_results=sub_agent_results,
        history=history,
        timing_logger=timing_logger
    )
