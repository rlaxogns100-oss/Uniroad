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
from token_logger import log_token_usage

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
            model_name="gemini-3-flash-preview",
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
        
        # 섹션 패턴 찾기
        section_pattern = r'===SECTION_START===(.*?)===SECTION_END==='
        
        sections = []
        for match in re.finditer(section_pattern, text, flags=re.DOTALL):
            section_content = match.group(1).strip()
            
            # 빈 섹션 스킵
            if not section_content:
                _log(f"   [후처리] 빈 섹션 발견, 스킵")
                continue
            
            # cite 태그 찾기 (data-url은 선택적)
            cite_pattern = r'<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>.*?</cite>'
            
            citations = []
            seen = set()
            
            for cite_match in re.finditer(cite_pattern, section_content, flags=re.DOTALL):
                source = cite_match.group(1)
                url = cite_match.group(2) or ""  # data-url이 없으면 빈 문자열
                key = (source, url)
                
                if key not in seen and source:  # 중복 제거 및 빈 source 제외
                    seen.add(key)
                    citations.append((source, url))
            
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
                _log(f"   [후처리] 섹션 #{len(sections)} 추가 (길이: {len(final_section)}자)")
        
        # 섹션이 없으면 원본 반환
        if not sections:
            _log("   [후처리] ⚠️ 섹션을 찾지 못함, 원본 반환")
            return text.strip()
        
        # 섹션 간 세 줄 간격으로 연결 (출처 포함 섹션 아래 빈 줄 하나 추가)
        result = '\n\n\n'.join(sections)
        
        _log("   [후처리] 처리된 섹션 수: " + str(len(sections)))
        _log("   [후처리] 최종 텍스트 길이: " + str(len(result)) + "자")
        
        return result.strip()

    async def generate_final_answer(
        self,
        user_question: str,
        answer_structure: List[Dict],
        sub_agent_results: Dict[str, Any],
        custom_prompt: str = None,
        history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Answer Structure에 따라 최종 답변 생성

        Args:
            user_question: 원래 사용자 질문
            answer_structure: Orchestration Agent가 만든 답변 구조
            sub_agent_results: Sub Agent들의 실행 결과
            custom_prompt: 커스텀 프롬프트 (선택)
            history: 대화 히스토리 (최근 10개 대화)

        Returns:
            {
                "status": str,
                "final_answer": str,
                "sources": List[str],
                "source_urls": List[str],
                "metadata": Dict
            }
        """
        _log("")
        _log("="*80)
        _log("📝 Final Agent 실행")
        _log("="*80)
        
        # history를 user_question에 병합
        user_question_with_context = self._merge_history_with_question(user_question, history)
        
        # 입력 데이터 검증 로그
        _log(f"🔍 [입력 검증]")
        _log(f"   user_question: {user_question[:100]}..." if len(user_question) > 100 else f"   user_question: {user_question}")
        _log(f"   history 대화 수: {len(history) if history else 0}")
        _log(f"   answer_structure 섹션 수: {len(answer_structure)}")
        _log(f"   sub_agent_results 키: {list(sub_agent_results.keys())}")
        _log(f"   custom_prompt 사용: {'✅ Yes' if custom_prompt else '❌ No (기본 prompt4 사용)'}")

        # Sub Agent 결과 정리 + 출처 정보 수집
        results_text, all_sources, all_source_urls, all_citations = self._format_sub_agent_results(sub_agent_results)

        # Answer Structure를 텍스트로 변환
        structure_text = self._format_answer_structure(answer_structure)

        
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

        try:
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

            # 토큰 사용량 기록
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                print(f"💰 토큰 사용량 (final_agent): {usage}")
                
                log_token_usage(
                    operation="최종답변생성",
                    prompt_tokens=getattr(usage, 'prompt_token_count', 0),
                    output_tokens=getattr(usage, 'candidates_token_count', 0),
                    total_tokens=getattr(usage, 'total_token_count', 0),
                    model="gemini-3-flash-preview",
                    details="Final Agent"
                )

            # 후처리: 섹션 마커 제거 및 cite 태그 정리
            raw_answer = response.text
            final_answer = self._post_process_sections(raw_answer)

            _log(f"   원본 답변 길이: {len(raw_answer)}자")
            _log(f"   후처리 답변 길이: {len(final_answer)}자")
            _log("="*80)

            return {
                "status": "success",
                "final_answer": final_answer,
                "raw_answer": raw_answer,  # ✅ 원본 추가
                "sources": all_sources,
                "source_urls": all_source_urls,
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
                "metadata": {}
            }

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

        Returns:
            (formatted_text, sources, source_urls, citations)
        """
        formatted = []
        all_sources = []
        all_source_urls = []
        all_citations = []

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

        return "\n---\n".join(formatted), all_sources, all_source_urls, all_citations

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
    history: List[Dict] = None
) -> Dict[str, Any]:
    """Final Agent를 통해 최종 답변 생성"""
    return await final_agent.generate_final_answer(
        user_question=user_question,
        answer_structure=answer_structure,
        sub_agent_results=sub_agent_results,
        history=history
    )
