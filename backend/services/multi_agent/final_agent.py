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
    print(msg)
    if _log_callback:
        _log_callback(msg)


class FinalAgent:
    """Final Agent - 최종 답변 조립"""

    def __init__(self):
        self.name = "Final Agent"
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
        )

    def _post_process_sections(self, text: str) -> str:
        """
        섹션 마커를 제거하고 각 섹션 끝에 cite 태그를 정리
        
        동작:
        1. ===SECTION_START===...===SECTION_END=== 패턴을 찾음
        2. 각 섹션 내의 모든 cite 태그에서 data-source, data-url 수집
        3. 섹션 끝에 수집한 cite 태그들을 빈 태그로 추가 (중복 제거)
        4. 섹션 마커 제거하고 섹션들을 한 줄 바꿈으로 연결
        """
        # 로그 추가
        _log("   [후처리] 원본 텍스트 길이: " + str(len(text)))
        _log("   [후처리] SECTION_START 개수: " + str(text.count("===SECTION_START===")))
        
        def process_section(match):
            section_content = match.group(1).strip()
            
            # 섹션 내의 모든 cite 태그 찾기
            cite_pattern = r'<cite\s+data-source="([^"]*?)"\s+data-url="([^"]*?)">[^<]*?</cite>'
            citations = []
            seen = set()
            
            for cite_match in re.finditer(cite_pattern, section_content):
                source = cite_match.group(1)
                url = cite_match.group(2)
                key = (source, url)
                
                if key not in seen and source:  # 중복 제거 및 빈 source 제외
                    seen.add(key)
                    citations.append((source, url))
            
            # 섹션 끝에 빈 cite 태그 추가
            if citations:
                cite_tags = '\n'.join([
                    f'<cite data-source="{source}" data-url="{url}"></cite>'
                    for source, url in citations
                ])
                # 섹션 내용 끝에 cite 태그 추가 (빈 줄 없이)
                return section_content + '\n' + cite_tags
            else:
                return section_content
        
        # 섹션 패턴 찾기 및 처리
        section_pattern = r'===SECTION_START===\s*(.*?)\s*===SECTION_END==='
        
        # 섹션들을 처리
        sections = []
        for match in re.finditer(section_pattern, text, flags=re.DOTALL):
            processed_section = process_section(match)
            if processed_section:
                sections.append(processed_section)
        
        # 섹션들을 한 줄 바꿈으로 연결 (빈 줄 없음)
        result = '\n'.join(sections)
        
        # 연속된 빈 줄 모두 제거 (2개 이상의 연속 줄바꿈을 하나로)
        while '\n\n' in result:
            result = result.replace('\n\n', '\n')
        
        # 앞뒤 공백 제거
        result = result.strip()
        
        _log("   [후처리] 처리된 섹션 수: " + str(len(sections)))
        _log("   [후처리] 최종 텍스트 길이: " + str(len(result)))
        
        return result

    async def generate_final_answer(
        self,
        user_question: str,
        answer_structure: List[Dict],
        sub_agent_results: Dict[str, Any],
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Answer Structure에 따라 최종 답변 생성

        Args:
            user_question: 원래 사용자 질문
            answer_structure: Orchestration Agent가 만든 답변 구조
            sub_agent_results: Sub Agent들의 실행 결과
            notes: Orchestration Agent의 추가 지시사항

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

        # Sub Agent 결과 정리 + 출처 정보 수집
        results_text, all_sources, all_source_urls, all_citations = self._format_sub_agent_results(sub_agent_results)

        # Answer Structure를 텍스트로 변환
        structure_text = self._format_answer_structure(answer_structure)

        _log(f"   섹션 수: {len(answer_structure)}")
        _log(f"   출처 수: {len(all_sources)}")

        # 프롬프트 가져오기 (prompt3 사용 - 참고문헌 방식)
        prompt = get_final_agent_prompt(
            "prompt3",
            user_question=user_question,
            structure_text=structure_text,
            results_text=results_text,
            notes=notes,
            all_citations=all_citations
        )

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 4096
                }
            )

            # 후처리: 섹션 마커 제거 및 cite 태그 정리
            raw_answer = response.text
            final_answer = self._post_process_sections(raw_answer)

            _log(f"   최종 답변 길이: {len(final_answer)}자")
            _log("="*80)

            return {
                "status": "success",
                "final_answer": final_answer,
                "sources": all_sources,
                "source_urls": all_source_urls,
                "metadata": {
                    "sections_count": len(answer_structure),
                    "sub_agents_used": list(sub_agent_results.keys()),
                    "notes": notes
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
    notes: str = ""
) -> Dict[str, Any]:
    """Final Agent를 통해 최종 답변 생성"""
    return await final_agent.generate_final_answer(
        user_question=user_question,
        answer_structure=answer_structure,
        sub_agent_results=sub_agent_results,
        notes=notes
    )
