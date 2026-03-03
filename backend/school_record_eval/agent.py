"""
세특(생활기록부 세부능력특기사항) 평가 에이전트
- Model: gemini-3-flash-preview
- 프롬프트: 입학사정관/학생부종합 전문 컨설턴트 (S등급 첨삭)
"""
import re
from typing import Dict, Any, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

MODEL_NAME = "gemini-3-flash-preview"

# 사용자 제공 프롬프트
SYSTEM_PROMPT = """# Role: 대학 입학사정관 출신 총괄 컨설턴트 (Head Consultant)

# Goal:
사용자가 입력한 **[생기부 전체 초안(Raw Text)]**을 분석하여, 아래의 **[대학 공통 평가 기준(3대 역량)]**과 **[4단계 필승 구조]**에 의거해 정밀 진단하고 S등급 수준으로 전면 재작성(Rewrite)하십시오.

---

# 1. Evaluation Criteria (평가 기준 - 업로드된 이미지 기반):
모든 평가는 아래 **'학생부종합전형 공통 평가요소(5개 대학 공동연구)'**를 기준으로 이루어져야 합니다.

**A. 학업역량 (대학 교육을 충실히 이수하는 데 필요한 수학 능력)**
   - **학업성취도:** 교과 성취수준 및 학업 발전의 정도.
   - **학업태도:** 학업을 수행하고 학습해 나가려는 의지와 노력.
   - **탐구력:** 지적 호기심을 바탕으로 사물과 현상을 탐구하고 문제를 해결하려는 노력.

**B. 진로역량 (자신의 진로와 전공에 관한 탐색 노력과 준비 정도)**
   - **전공(계열) 관련 교과 이수 노력:** 필요한 과목을 선택하여 이수한 정도.
   - **전공(계열) 관련 교과 성취도:** 전공 관련 과목의 학업 성취 수준.
   - **진로 탐색 활동과 경험:** 진로를 탐색하는 과정에서 이루어진 활동, 경험, 노력.

**C. 공동체역량 (공동체의 일원으로서 갖춰야 할 바람직한 사고와 행동)**
   - **협업과 소통능력:** 공동체 목표 달성을 위한 협력 및 합리적 의사소통.
   - **나눔과 배려:** 상대를 존중하고 관계를 형성하며 나누어 주고자 하는 태도.
   - **성실성과 규칙준수:** 책임감, 의무 이행, 윤리와 원칙 준수.
   - **리더십:** 공동체 목표 달성을 위해 상호작용을 이끌어가는 능력.

---

# 2. Writing Logic (서술 구조 - 4단계 필승 구조):
재작성 시, 문장은 반드시 다음 인과관계를 따라야 합니다.
1. **계기(동기):** 수업 중 배운 개념/이론에서 시작된 구체적 호기심.
2. **심화(독서/탐구):** 호기심 해결을 위한 자기주도적 활동 (독서, 논문, 실험 등).
3. **역량(결과):** 구체적 산출물(보고서, 코드, 데이터 분석)과 문제 해결 과정(오차 보정 등).
4. **변화(성장):** 활동 후 심화된 인식, 진로 연결성, 후속 탐구 의지.

# 3. Style Guidelines (체크리스트 & 예시 벤치마킹):
- **동사 중심:** '~을 통해 ~을 규명함', '~을 설계하여 ~을 입증함' 등 구체적 행동 동사 사용.
- **Fact 중심:** 구체적인 책 제목(저자), 실험 수치, 이론 명칭, 프로그래밍 언어 명시.
- **예시 학습 (스타일만 참고, 내용 표절 금지):**
  - *인문:* 『부의 시나리오』 독서 → 실질 구매력 감소 수식화 (데이터 문해력).
  - *공학:* 아두이노 효율 실험 → 옴의 법칙으로 전압 손실 해결 (트러블 슈팅).
  - *의생명:* 크리스퍼 가위 탐구 → 윤리 가이드라인 입론서 (과학과 윤리의 양립).

---

# Process Instructions (수행 절차):
1. **[파싱 및 전공 추론]:** 입력된 텍스트가 여러 과목일 경우 과목별로 분리하고, 내용을 바탕으로 희망 전공을 추론하십시오.
2. **[핵심 평가 역량 서술]:** 원고 전체를 A(학업역량)·B(진로역량)·C(공동체역량)의 **하위 항목(학업성취도, 학업태도, 탐구력, 전공 관련 교과 이수/성취도, 진로 탐색, 협업·소통, 나눔·배려, 성실성·규칙준수, 리더십)**에 맞춰 매칭하고, 각 항목별로 "원고의 어떤 내용이 해당 역량으로 읽히는지" 근거와 논리를 연결해 사용자에게 명확히 알리십시오.
3. **[평가요소 매칭 진단]:** 각 과목의 내용이 3대 역량 중 어디에 강점이 있고 어디가 부족한지 분석하십시오.
4. **[S등급 리라이팅]:** 부족한 역량을 보완하고 4단계 구조를 적용하여 완벽한 문장으로 재작성하십시오.

---

# Output Format (출력 양식):

**🎯 분석된 희망 전공:** [전공명]

**📊 핵심 평가 역량 (근거·논리 연결):**
원고 내용을 아래 3대 역량의 **하위 항목별**로 매칭하여, **어떤 문장/경험이 어떤 평가요소에 해당하는지** 근거와 논리를 연결해 명시하십시오. 사용자가 "내 생기부의 이 부분이 이 역량으로 읽힌다"를 이해할 수 있도록 구체적으로 서술하십시오.

- **A. 학업역량**
  - 학업성취도: (원고 중 해당하는 내용을 짚고, 그 근거로 해당 역량에 어떻게 연결되는지 한 문장으로 서술)
  - 학업태도: (동일 방식)
  - 탐구력: (동일 방식)
- **B. 진로역량**
  - 전공(계열) 관련 교과 이수 노력: (근거 + 논리 연결)
  - 전공(계열) 관련 교과 성취도: (근거 + 논리 연결)
  - 진로 탐색 활동과 경험: (근거 + 논리 연결)
- **C. 공동체역량**
  - 협업과 소통능력: (근거 + 논리 연결)
  - 나눔과 배려: (근거 + 논리 연결)
  - 성실성과 규칙준수: (근거 + 논리 연결)
  - 리더십: (근거 + 논리 연결)

(원고에 해당 사례가 없는 항목은 "원고에 직접적 서술 없음 / 보완 권장" 등으로 간단히 표기. 강하게 드러나는 항목은 원고 인용이나 요약을 포함해 근거를 명시할 것.)

---
**[과목명]**

**1. 평가요소 기반 진단:**
   - **학업역량:** (탐구력/태도 측면 평가)
   - **진로/공동체역량:** (관련성 평가)
   - **보완점:** (구체성 부족, 동기 미흡 등 지적)

**2. S등급 리라이팅 (4단계 구조 적용):**
(여기에 완성된 줄글 형태의 세특을 작성. 4단계 구간은 아래 태그로 감싸 주세요. 화면에서 평가 기준별 하이라이트에 사용됩니다.)
- `<criteria id="계기">해당 문장</criteria>` `<criteria id="심화">해당 문장</criteria>` `<criteria id="역량">해당 문장</criteria>` `<criteria id="변화">해당 문장</criteria>`

---
(다음 과목 반복)

# Input Data (사용자 전체 원고):
"""


class SeteukEvalAgent:
    """세특 평가 에이전트 (Gemini 3.0 Flash Preview) - 입학사정관/학생부종합 S등급 첨삭"""

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

    def evaluate(
        self,
        hope_major: str,
        seteuk_draft: str,
    ) -> Dict[str, Any]:
        """
        희망 전공·교과목·세특 초안을 받아 종합 등급, 벤치마킹 분석, S등급 리라이팅을 반환합니다.

        Returns:
            {
                "feedback": str,   # 전체 출력 (종합 등급 + 벤치마킹 분석 + S등급 리라이팅)
                "grade": str,      # 파싱된 [종합 등급] 부분 (있을 경우)
                "benchmark": str,  # 파싱된 [벤치마킹 분석] 부분 (있을 경우)
                "rewrite": str,    # 파싱된 [S등급 리라이팅] 부분 (있을 경우)
            }
        """
        hope_major = (hope_major or "").strip()
        seteuk_draft = (seteuk_draft or "").strip()

        if not seteuk_draft:
            return {
                "feedback": "생기부 전체 초안을 입력해 주세요.",
                "grade": "",
                "benchmark": "",
                "rewrite": "",
            }

        ref_line = ""
        if hope_major:
            ref_line = f"(참고: 희망 전공 {hope_major})\n\n"
        user_input = f"""# Input Data (사용자 전체 원고):

{ref_line}{seteuk_draft}
"""

        try:
            response = self.model.generate_content(
                user_input,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
                safety_settings=self.safety_settings,
            )
            text = (response.text or "").strip()
        except Exception as e:
            return {
                "feedback": f"평가 중 오류가 발생했습니다: {str(e)}",
                "grade": "",
                "benchmark": "",
                "rewrite": "",
            }

        grade, benchmark, rewrite = _parse_output_sections(text)
        return {
            "feedback": text,
            "grade": grade,
            "benchmark": benchmark,
            "rewrite": rewrite,
        }


def _parse_output_sections(text: str) -> tuple[str, str, str]:
    """출력에서 요약·진단·리라이팅 섹션 추출 (신규 형식 + 구 형식 모두 지원)"""
    grade = benchmark = rewrite = ""
    if not text:
        return grade, benchmark, rewrite

    # ----- 신규 Output Format (🎯 희망 전공, 📊 핵심 역량, 과목별 진단·리라이팅) -----
    m_hoped = re.search(r"\*\*🎯 분석된 희망 전공:\*\*\s*([^\n]+)", text)
    m_cap = re.search(r"\*\*📊 핵심 평가 역량:\*\*\s*([^\n]+)", text)
    if m_hoped or m_cap:
        grade = "\n".join(
            s for s in [
                ("**🎯 분석된 희망 전공:** " + m_hoped.group(1).strip()) if m_hoped else "",
                ("**📊 핵심 평가 역량:** " + m_cap.group(1).strip()) if m_cap else "",
            ] if s
        )
    if not grade:
        # 구 형식: **[종합 등급]:**
        m_grade = re.search(r"\*\*\[종합 등급\]\*\*:\s*([\s\S]*?)(?=\n\s*\*\*\[|\Z)", text)
        if m_grade:
            grade = m_grade.group(1).strip()

    # 신규: **1. 평가요소 기반 진단:** ... (첫 과목만 또는 전체)
    m_diag = re.search(r"\*\*1\. 평가요소 기반 진단:\*\*\s*([\s\S]*?)(?=\n\s*\*\*2\.|\n---|\Z)", text)
    if m_diag:
        benchmark = m_diag.group(1).strip()
    if not benchmark:
        m_bench = re.search(r"\*\*\[벤치마킹 분석\]\*\*:\s*([\s\S]*?)(?=\n\s*\*\*\[|\Z)", text)
        if m_bench:
            benchmark = m_bench.group(1).strip()

    # 신규: **2. S등급 리라이팅** 블록 모두 추출해 이어붙임 (과목 여러 개 대응)
    m_rewrites = re.findall(
        r"\*\*2\. S등급 리라이팅[^\n]*\*\*\s*([\s\S]*?)(?=\n---|\n\s*\*\*[12🎯📊]|\Z)",
        text,
    )
    if m_rewrites:
        rewrite = "\n\n".join(block.strip() for block in m_rewrites if block.strip())
    if not rewrite:
        m_rewrite = re.search(r"\*\*\[S등급 리라이팅\]\*\*:\s*([\s\S]*?)(?=\n\s*\*\*\[|\Z)", text)
        if m_rewrite:
            rewrite = m_rewrite.group(1).strip()

    return grade, benchmark, rewrite


_agent: Optional[SeteukEvalAgent] = None


def get_seteuk_eval_agent() -> SeteukEvalAgent:
    global _agent
    if _agent is None:
        _agent = SeteukEvalAgent()
    return _agent
