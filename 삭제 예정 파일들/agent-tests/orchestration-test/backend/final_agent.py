"""
Final Agent
- Answer Structure(설계도)에 따라 Sub Agent 결과(재료)를 조립하여 최종 답변 생성
- 설계도를 그대로 따르며, 임의로 구조를 변경하지 않음
"""

import google.generativeai as genai
from typing import Dict, Any, List
import json
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Gemini API 설정 (환경 변수에서 로드)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class FinalAgent:
    """Final Agent - 최종 답변 조립"""

    def __init__(self):
        self.name = "Final Agent"
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",  # 고품질 모델 사용
        )

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
        """
        
        print("")
        print("="*80)
        print("📝 Final Agent 실행 (테스트 환경)")
        print("="*80)
        
        # 입력 데이터 검증 로그
        print(f"🔍 [입력 검증]")
        print(f"   user_question: {user_question[:100]}..." if len(user_question) > 100 else f"   user_question: {user_question}")
        print(f"   answer_structure 섹션 수: {len(answer_structure)}")
        print(f"   sub_agent_results 키: {list(sub_agent_results.keys())}")
        print(f"   notes: {notes if notes else '(없음)'}")

        # Sub Agent 결과를 정리
        print(f"   📦 [Sub Agent 결과 포맷팅 시작]")
        print(f"      받은 결과 키: {list(sub_agent_results.keys())}")
        
        results_text = self._format_sub_agent_results(sub_agent_results)

        # Answer Structure를 텍스트로 변환
        print(f"   📋 [Answer Structure 포맷팅 시작]")
        print(f"      섹션 수: {len(answer_structure)}")
        structure_text = self._format_answer_structure(answer_structure)

        # 시스템 프롬프트 구성 (prompt4 - 최적화 버전)
        all_citations = []  # 테스트 환경에서는 citations 수집 안 함
        
        print(f"📋 [프롬프트 생성: prompt4 기본]")
        
        system_prompt = f"""
당신은 대한민국 상위 1% 입시 컨설팅 리포트의 [수석 에디터]입니다.
수집된 데이터를 [모바일 환경에서 3초 안에 파악 가능한] 진단형 리포트로 재구성하십시오.

---

### 1. 편집 원칙 (Strict Guidelines)
1. **톤앤매너:** 객관적 전문가의 '진단/보고' 어조 (~입니다, ~함). 1인칭(나, 저) 사용 금지. 미사여구 및 접속사 삭제.
2. **서식 제한:**
   - Markdown 강조(**, ##) 절대 사용 금지.
   - 섹션 제목은 오직 `【제목】` 형식만 사용
   - 줄글 지양: 3줄 이상 텍스트 금지. 핵심 정보는 글머리 기호(•)로 요약(최대 3개).
   - 복잡한 데이터는 Plain Text 표(|, -)로 변환.
3. **인용(Citation):** 데이터 출처는 반드시 섹션 하단에 `<cite>` 태그로 명시.

### 2. 섹션별 작성 지침 (엄격 준수)

**[Type A] 제목 필수 (`【제목】` 포함)**
- 대상: **[fact_check], [analysis], [recommendation], [warning]**
- 규칙: 반드시 `【제목】`으로 시작하고, 그 다음 줄부터 본문 작성. 두괄식 결론 제시

**[Type B] 제목 절대 금지 (본문 바로 시작)**
- 대상: **[empathy], [encouragement], [next_step]**
- 규칙: `【공감】`, `【다음 단계】` 같은 제목을 절대 쓰지 마십시오.
- 마커(`===SECTION_START===`) 바로 다음 줄에 문장이나 리스트가 와야 합니다. 구체적 액션/공감만 짧게

### 3. 출력 프로토콜 (CRITICAL)
다음 포맷 규칙을 기계적으로 준수하십시오. (파싱을 위해 필수)
- 모든 섹션은 `===SECTION_START===`와 `===SECTION_END===`로 감싸야 함.
- **마커, 제목, 본문, cite 태그 사이에는 빈 줄(New Line)을 절대 넣지 마십시오.**
- 빡빡하게 붙여서 출력하십시오.

[올바른 출력 예시]
===SECTION_START===
【2026학년도 서울대 분석】
• 지균 선발 인원: 10명 (전년 대비 +2)
• 수능 최저: 3합 7 유지
<cite data-source="서울대 시행계획" data-url="..."></cite>
===SECTION_END===
===SECTION_START===
현재 성적으로는 상향 지원이므로 9월 모평까지 추이를 지켜봐야 합니다.
===SECTION_END===


---

[참고 문헌 (ID 매핑)]
{json.dumps(all_citations, ensure_ascii=False, indent=2)[:2000]}

---

### 수행 작업
1. **입력 데이터:** 아래 [Sub Agent 결과]를 원천 데이터로 활용 (내용 위조 금지).
2. **목차 구성:** 아래 [Answer Structure]의 순서와 의도를 100% 준수.
3. **최종 출력:** 위 [출력 프로토콜]에 맞춰 빈 줄 없이 작성.

[사용자 질문]
{user_question}

[Answer Structure]
{structure_text}

[Sub Agent 결과 (Raw Data)]
{results_text}
"""

        print(f"   프롬프트 길이: {len(system_prompt)}자")
        print(f"   📄 최종 프롬프트 미리보기:")
        print(f"   {system_prompt[:500]}...")
        print("="*80)

        try:
            response = self.model.generate_content(
                system_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 4096
                }
            )

            return {
                "status": "success",
                "final_answer": response.text,
                "metadata": {
                    "sections_count": len(answer_structure),
                    "sub_agents_used": list(sub_agent_results.keys()),
                    "notes": notes
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "final_answer": self._generate_fallback_answer(
                    user_question, answer_structure, sub_agent_results
                )
            }

    def _format_sub_agent_results(self, results: Dict[str, Any]) -> str:
        """Sub Agent 결과를 텍스트로 포맷"""
        formatted = []

        for step_key, result in results.items():
            agent_name = result.get("agent", "Unknown")
            status = result.get("status", "unknown")
            content = result.get("result", "결과 없음")
            
            print(f"      {step_key}: agent={agent_name}, status={status}, content_length={len(str(content))}자")

            formatted.append(f"""### {step_key} ({agent_name})
상태: {status}

{content}
""")

        print(f"      ✅ 포맷팅 완료: {len(formatted)}개 결과")
        return "\n---\n".join(formatted)

    def _format_answer_structure(self, structure: List[Dict]) -> str:
        """Answer Structure를 텍스트로 포맷"""
        formatted = []

        for section in structure:
            sec_num = section.get("section", "?")
            sec_type = section.get("type", "unknown")
            source = section.get("source_from", "없음")
            instruction = section.get("instruction", "")
            
            print(f"      섹션{sec_num}: type={sec_type}, source_from={source}")

            formatted.append(f"""**섹션 {sec_num}** [{sec_type}]
- 참조할 데이터: {source if source else "없음 (직접 작성)"}
- 지시사항: {instruction}""")

        print(f"      ✅ Answer Structure 포맷팅 완료")
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
                    parts.append(result[:500])  # 길이 제한
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
