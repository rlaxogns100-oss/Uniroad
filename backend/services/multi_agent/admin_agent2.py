"""
Admin Agent 2 - 테스트 평가 전용
- Router 출력 평가 (5점 만점)
- Main 답변 평가 (5점 만점)
- Model: gemini-2.5-flash-lite (빠른 평가용)
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
# 설정
# ============================================================

ADMIN2_CONFIG = {
    "model": "gemini-2.5-flash-lite",
    "temperature": 0.0,
    "max_output_tokens": 1024
}


# ============================================================
# Router 평가 프롬프트
# ============================================================

ROUTER_EVAL_PROMPT = """당신은 대학 입시 상담 시스템의 Router Agent 출력을 평가하는 평가자입니다.
아래의 [참조 기준]과 [평가 기준]을 바탕으로 Router의 출력을 엄격하게 채점하세요.

## 1. [참조 기준: 함수 및 파라미터 규격]
Router는 아래 정의된 3가지 함수 중에서만 목적에 맞게 호출할 수 있습니다.

### (1) univ(university, query)
- **목적**: 대학별 모집요강, 시행계획, 단순 정보 검색, 개별 대학 입결
- **university**: 대학 정식 명칭 (예: 서울대학교, 연세대학교)
- **query**: '연도 + 전형 + 학과'가 명시된 검색어

### (2) consult_jungsi(j_scores, target_univ, target_major, target_range)
- **목적**: 대학별 정시 전형 결과 조회, 대학별 정시 성적 환산, 정시 성적으로 갈 수 있는 대학 탐색 및 추정
- **j_scores 구조 (JSON)**:
  ```json
  {
    "국어": {"type": "등급", "value": 1},
    "수학": {"type": "표준점수", "value": 140},
    "영어": {"type": "등급", "value": 2},
    "한국사": {"type": "등급", "value": 1}, // 미언급 시 1등급 기본값
    "탐구1": {"type": "등급", "value": 1, "과목명": "생활과윤리"}, // 과목명 있으면 필드 추가
    "탐구2": {"type": "등급", "value": 2, "과목명": "사회문화"}
  }

target_univ: 분석 대상 대학 리스트 (없으면 [])
target_major: 관심 학과 리스트 (없으면 [])
target_range: ['안정', '적정', '소신', '도전', '어려움'] 중 선택 (없으면 [])

###(3) consult_susi(s_scores, university, junhyung, department)
목적: 대학별/학과별/전형별 수시 전형 결과 조회, 수시 성적으로 갈 수 있는 대학 탐색 및 추정
s_scores: 내신 등급 리스트 (예: [1.4, 1.1])
junhyung: 전형 명칭 (예: ["학생부종합", "네오르네상스"]). 애매하면 포괄적으로 포함.
department: 학과/전공 명칭

예시)
### univ 함수 예시: 올해 수능으로 서울대 가려면 어떻게 해?
```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": "서울대학교",
        "query": "2026학년도 서울대학교 정시 모집요강"
      }
    }
  ]
 {
      "function": "consult_jungsi",
      "params": {
        "j_scores": [],
        "target_univ": ["서울대학교"],
        "target_major": [],
        "target_range": []
      }
    },
}
```
### consult_susi 함수 예시: 나 내신 1.4인데 1.1까지 올리면 서울대 기계공학과 갈 수 있을까?
```json
{
  "function_calls": [
    {
      "function": "consult_susi",
      "params": {
        "university": ["서울대학교"],
        "s_scores": [1.4, 1.1],
        "junhyung": ["교과전형", "학생부종합전형", "일반전형"],
        "department": ["기계공학과", "기계공학부"]
      }
    }
  ]
}
```


2. [평가 기준] (각 항목 O/X 평가)
 ## intent_understanding (의도 파악)
  - 사용자의 질문이 '정시'인지 '수시'인지, 혹은 '단순 모집요강 검색'인지 정확히 파악했는가?
  - 대학, 학과, 성적 분석 요청 의도를 놓치지 않았는가?
 ## function_selection (함수 선택)
  - 질문 의도에 맞는 함수를 선택했는가? (불필요한 함수 호출 없음)
 ## query_params (쿼리/변수 정확성)
  - 대학명: '서울대'가 아닌 '서울대학교'처럼 정식 명칭을 사용했는가?
  - 필수 키: j_scores 내부의 키(국어, 수학, 탐구1, 탐구2 등)와 type, value 형식을 준수했는가?
  - 탐구과목: 탐구 과목명이 있을 경우 과목명 필드를 포함했는가?
  - 전형/학과: junhyung, target_major 등이 누락되지 않고 적절히 채워졌는가?
 ## json_format (JSON 형식)
  - function_calls 배열을 포함한 유효한 JSON 포맷인가?
  - 파싱 에러 없이 구조가 완벽한가?
 ## score_conversion (성적 환산 로직)
  - score_conversion (성적 환산 로직)
  - 축약형 해석: '11232' 같은 입력을 '국1/수1/영2/탐1=3/탐2=2'로 올바르게 분해했는가?
  - 점수 타입 구분: 100 이상은 '표준점수', 1자리는 '등급'으로 정확히 분류했는가?
  - 과목 매핑: 선택과목(화작/언매/미적/확통/사탐/과탐)을 정확한 과목명으로 변환했는가?
  - 추정 로직: "수학은 못해요" → 낮은 등급 추정 등 문맥에 맞는 값을 할당했는가?
  - 추정 로직: "수학은 못해요" → 낮은 등급 추정 등 문맥에 맞는 값을 할당했는가?

3. [출력 형식] (중요)
반드시 아래 JSON 포맷으로만 출력하세요. 다른 설명이나 텍스트를 포함하지 마세요. comment는 감점 사유가 있을 때만 한국어로 짧게 작성하고, 만점이면 빈 문자열로 둡니다.
{
  "score": 5,
  "intent_understanding": true,
  "function_selection": true,
  "query_params": true,
  "json_format": true,
  "score_conversion": true,
  "comment": ""
}
"""



# ============================================================
# Main 평가 프롬프트
# ============================================================

MAIN_EVAL_PROMPT = """
당신은 대학 입시 상담 시스템의 Main Agent 최종 답변을 평가하는 평가자입니다.
제공된 [사용자 질문], [검색된 자료(Function Result)], [최종 답변]을 비교하여 아래 기준에 따라 엄격하게 채점하세요.

답변 예시
=D13=SECTION_START:empathy===
**건축학과**를 희망하면서 **물리Ⅱ**, **미적분**, **확통**을 모두 이수한 점은 공학적 기초 역량을 증명하는 데 매우 큰 강점이에요. 특히 **주요 교과(국영수사과) 2.45등급**은 **전교과 2.7등급**보다 우수하여, 주요 과목을 집중적으로 반영하는 상위권 대학 지원 시 훨씬 유리한 고지를 점할 수 있습니다.
===SECTION_END===
===SECTION_START:analysis===
【내신 등급 및 이수 과목 분석】
학생의 성적 지표와 이수 과목은 **건축학부** 지원 시 다음과 같은 의미를 가집니다.

• **교과 역량**: **국영수과 2.43등급**은 자연계열 및 공학계열 지원의 핵심 지표입니다. **물리Ⅱ**와 **미적분** 수강은 **서울 주요 대학** 종합전형에서 '전공 적합성'과 '학업 역량' 모두에서 높은 점수를 받을 수 있는 요소입니다.
• **전형별 유불리**: **교과전형**으로는 수도권 중상위권 대학이 **적정**권이며, **종합전형**으로는 학생부 경쟁력이 뒷받침된다면 서울 상위권 대학까지 **소신/상향** 지원이 가능합니다.
<cite data-source="2025학년도 수시 전형결과 (내신닷컴)" data-url="https://www.nesin.com">• **비교 데이터**: **건국대 건축학부(종합)** 70% 컷이 **2.88**, **부산대 건축학과(교과)**가 **2.65**임을 고려할 때, 학생의 **2.4~2.7등급**은 국립대 및 수도권 주요 대학 합격권에 안정적으로 안착합니다.</cite>
===SECTION_END===
===SECTION_START:recommendation===
【유니로드 추천 대학 및 전형】
학생의 강점인 **이수 과목**과 **교과 성적**을 극대화할 수 있는 리스트입니다.

• **상향/소신 (종합전형)**: 
  - **중앙대학교 (CAU탐구형인재)**: 면접을 통해 **물리Ⅱ**와 **건축적 탐구 역량**을 어필하기 좋습니다.
  - **경희대학교 (네오르네상스)**: 생기부 내용이 좋다면 **2.4등급**대로 충분히 승산이 있습니다.
• **적정 (교과/종합)**:
  - **건국대학교 (KU자기추천)**: **건축학부**의 인기가 높지만 학생의 성적은 컷보다 우위에 있습니다.
  - **홍익대학교 (학교장추천/학교생활우수자)**: 건축으로 유명한 대학이며, **2.4등급**은 안정적인 지원권입니다.
• **안정 (교과전형)**:
  - **부산대학교/경북대학교 (지역균형/교과)**: 거점 국립대 건축학과는 합격 가능성이 매우 높으며, 향후 취업에도 유리합니다.
  - **광운대학교 (지역균형)**: **2.4등급**은 광운대 건축 정시/수시 컷을 상회하는 점수입니다.
===SECTION_END===
===SECTION_START:warning===
【지원 시 필수 체크 사항】
• **수능 최저학력기준**: **홍익대**, **중앙대(교과)**, **부산대** 등은 수능 최저 기준이 존재합니다. **3합 7**이나 **2합 5** 수준을 충족할 수 있는지 모의고사 성적을 반드시 점검해야 합니다.
<cite data-source="2026학년도 중앙대학교 입학전형시행계획(240430)_공고용 4p" data-url="https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/e6c01b9e-ba07-45e5-8596-507012e7fcdb.pdf">• **건축학부 특성**: **중앙대** 등 주요 대학은 **건축학(5년제)**과 **건축공학(4년제)**을 분리 선발하거나 통합 선발하므로, 본인이 설계(5년)와 시공/기술(4년) 중 무엇을 원하는지 명확히 해야 합니다.</cite>
===SECTION_END===
===SECTION_START:encouragement===
어려운 과목인 **물리Ⅱ**와 **미적분**을 선택해 좋은 성적을 유지한 것만으로도 입학 사정관들에게 큰 인상을 남길 거예요. **건축**에 대한 열정이 담긴 생기부와 이 성적이라면 수도권 상위권 대학의 문은 충분히 열려 있습니다. 자신감을 가지고 수능 최저 준비와 자기소개서(필요 시) 정리에 집중해 보세요!
===SECTION_END===D9



## 1. [평가 기준] (각 항목 O/X 평가)

1. **answer_relevance** (답변 적절성)
   - 대화 내용을 고려할 때 사용자의 질문 의도(합격 가능성 진단, 단순 정보 검색 등)에 맞는 답변인가?
   - 질문하지 않은 엉뚱한 대학이나 학과에 대해 설명하지는 않았는가?
   - 대화 상황에 비해 과하게 길거나 짧지는 않은가?

2. **source_based** (자료 기반 & 할루시네이션 방지)
   - **핵심**: 답변에 제시된 수치(모집인원, 점수컷, 경쟁률 등)가 반드시 [검색된 자료]에 존재하는가?
   - 자료에 없는 내용을 사실인 것처럼 꾸며내거나(Hallucination), 수치를 임의로 조작하지 않았는가?
   - 검색 결과가 '없음'일 경우, 솔직하게 정보가 부족함을 안내했는가?
   - 사용자가 성적을 입력하지 않았는데 성적을 말하는 등 function 데이터와 사용자 질문을 혼동하지 않았는가?

3. **output_format** (출력 형식 및 구조)
   - Main Agent 전용 섹션 마커(`===SECTION_START:타입===`, `===SECTION_END===`)를 사용하여 답변을 구조화했는가?
   - 가독성을 위해 불렛포인트, 볼드체 등을 적절히 사용했는가? (줄글로만 나열하지 않았는가?)

4. **citation_accuracy** (인용 표기 준수)
   - 수치나 입시 요강 데이터를 언급할 때 `<cite data-source="..." data-url="...">` 태그 형식을 시도했는가?
   - 단순한 텍스트 언급(예: "모집요강에 따르면")보다, 시스템이 요구하는 태그 형식을 갖추었는지 확인하세요.
   - 검색된 자료에 있는 출처(문서명, 페이지)를 기반으로 작성되었는가?

5. **no_confusion** (정보 혼동 없음)
   - 대학 A의 입결을 대학 B의 것으로 잘못 매칭하지 않았는가?
   - 작년(2025) 데이터와 올해(2026) 데이터를 명확히 구분하여 설명하고 있는가?
   - 학과명이나 전형명을 정확하게 기재했는가?

## 2. [평가 팁]
- **관대함 금지**: `output_format`과 `citation_accuracy`는 시스템 파싱을 위해 필수적이므로, 형식이 깨져있다면 과감하게 False(X)를 주십시오.
- **자료 부재 시**: 검색된 자료가 없어서 "정보를 찾을 수 없습니다"라고 답했다면, `answer_relevance`와 `source_based`는 True(O)입니다.

## 3. [출력 형식]
반드시 아래 JSON 포맷으로만 출력하세요. 다른 설명이나 텍스트를 포함하지 마세요.
`comment`는 감점 사유가 있을 때만 한국어로 명확히(어떤 수치가 틀렸는지, 어떤 형식이 누락됐는지) 작성하고, 만점이면 빈 문자열로 둡니다.

```json
{
  "score": 5,
  "answer_relevance": true,
  "source_based": true,
  "output_format": true,
  "citation_accuracy": true,
  "no_confusion": true,
  "comment": ""
}



"""


# ============================================================
# TestAdminAgent 클래스
# ============================================================

class TestAdminAgent:
    """테스트 평가 전용 Admin Agent"""
    
    def __init__(self):
        self.router_model = genai.GenerativeModel(
            model_name=ADMIN2_CONFIG["model"],
            system_instruction=ROUTER_EVAL_PROMPT
        )
        self.main_model = genai.GenerativeModel(
            model_name=ADMIN2_CONFIG["model"],
            system_instruction=MAIN_EVAL_PROMPT
        )
        self.generation_config = {
            "temperature": ADMIN2_CONFIG["temperature"],
            "max_output_tokens": ADMIN2_CONFIG["max_output_tokens"],
            "response_mime_type": "application/json"
        }
    
    async def evaluate_router(
        self,
        history: str,
        question: str,
        router_output: str
    ) -> Dict[str, Any]:
        """
        Router 출력 평가 (5점 만점)
        
        Args:
            history: 이전 대화 내역
            question: 사용자 질문
            router_output: Router Agent 출력 (JSON 문자열)
            
        Returns:
            {
                "score": 0~5,
                "intent_understanding": bool,
                "function_selection": bool,
                "query_params": bool,
                "json_format": bool,
                "score_conversion": bool,
                "comment": str
            }
        """
        try:
            prompt = f"""## 이전 대화
{history if history else "없음"}

## 사용자 질문
{question}

## Router 출력
```json
{router_output}
```

위 Router 출력을 평가해주세요."""

            response = await self.router_model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            
            result = self._parse_response(response.text.strip())
            return self._normalize_router_result(result)
            
        except Exception as e:
            return {
                "score": 0,
                "intent_understanding": False,
                "function_selection": False,
                "query_params": False,
                "json_format": False,
                "score_conversion": False,
                "comment": f"평가 오류: {str(e)}"
            }
    
    async def evaluate_main(
        self,
        history: str,
        question: str,
        router_output: str,
        function_result: str,
        final_answer: str
    ) -> Dict[str, Any]:
        """
        Main 답변 평가 (5점 만점)
        
        Args:
            history: 이전 대화 내역
            question: 사용자 질문
            router_output: Router Agent 출력
            function_result: Function 실행 결과
            final_answer: Main Agent 최종 답변
            
        Returns:
            {
                "score": 0~5,
                "answer_relevance": bool,
                "source_based": bool,
                "output_format": bool,
                "citation_accuracy": bool,
                "no_confusion": bool,
                "comment": str
            }
        """
        try:
            # Function 결과 요약 (토큰 절약)
            func_summary = self._summarize_function_result(function_result)
            
            prompt = f"""## 이전 대화
{history if history else "없음"}

## 사용자 질문
{question}

## Function 실행 결과 (검색된 데이터)
{func_summary}

## 최종 답변
{final_answer}

위 최종 답변을 평가해주세요."""

            response = await self.main_model.generate_content_async(
                prompt,
                generation_config=self.generation_config
            )
            
            result = self._parse_response(response.text.strip())
            return self._normalize_main_result(result)
            
        except Exception as e:
            return {
                "score": 0,
                "answer_relevance": False,
                "source_based": False,
                "output_format": False,
                "citation_accuracy": False,
                "no_confusion": False,
                "comment": f"평가 오류: {str(e)}"
            }
    
    async def evaluate_pipeline(
        self,
        history: str,
        question: str,
        router_output: str,
        function_result: str,
        final_answer: str
    ) -> Dict[str, Any]:
        """
        Pipeline 전체 평가 (10점 만점 = Router 5점 + Main 5점)
        """
        router_eval = await self.evaluate_router(history, question, router_output)
        main_eval = await self.evaluate_main(history, question, router_output, function_result, final_answer)
        
        return {
            "total_score": router_eval["score"] + main_eval["score"],
            "router_score": router_eval["score"],
            "main_score": main_eval["score"],
            "router_eval": router_eval,
            "main_eval": main_eval
        }
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """JSON 파싱"""
        import re
        
        # ```json...``` 블록 추출
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
            return {}
    
    def _normalize_router_result(self, result: Dict) -> Dict[str, Any]:
        """Router 평가 결과 정규화"""
        criteria = [
            "intent_understanding",
            "function_selection", 
            "query_params",
            "json_format",
            "score_conversion"
        ]
        
        normalized = {
            "comment": result.get("comment", "")
        }
        
        score = 0
        for c in criteria:
            val = result.get(c, False)
            if isinstance(val, bool):
                normalized[c] = val
            else:
                normalized[c] = str(val).lower() in ["true", "o", "1", "yes"]
            if normalized[c]:
                score += 1
        
        # score는 항상 true 개수로 강제
        normalized["score"] = score
        return normalized
    
    def _normalize_main_result(self, result: Dict) -> Dict[str, Any]:
        """Main 평가 결과 정규화"""
        criteria = [
            "answer_relevance",
            "source_based",
            "output_format",
            "citation_accuracy",
            "no_confusion"
        ]
        
        normalized = {
            "comment": result.get("comment", "")
        }
        
        score = 0
        for c in criteria:
            val = result.get(c, False)
            if isinstance(val, bool):
                normalized[c] = val
            else:
                normalized[c] = str(val).lower() in ["true", "o", "1", "yes"]
            if normalized[c]:
                score += 1
        
        # score는 항상 true 개수로 강제
        normalized["score"] = score
        return normalized
    
    def _summarize_function_result(self, function_result: str) -> str:
        """Function 결과 요약 (토큰 절약)"""
        if not function_result:
            return "검색 결과 없음"
        
        try:
            # JSON 파싱 시도
            if isinstance(function_result, str):
                data = json.loads(function_result)
            else:
                data = function_result
            
            summary_parts = []
            for key, result in data.items():
                if "error" in result:
                    summary_parts.append(f"[{key}] 오류: {result['error']}")
                elif "chunks" in result:
                    chunks = result.get("chunks", [])
                    university = result.get("university", "")
                    query = result.get("query", "")
                    
                    summary_parts.append(f"\n[{university}] (검색어: {query})")
                    summary_parts.append(f"총 {len(chunks)}개 청크")
                    
                    # 상위 3개 청크만 요약
                    for i, chunk in enumerate(chunks[:3], 1):
                        content = chunk.get("content", "")[:300]
                        summary_parts.append(f"  청크 {i}: {content}...")
            
            return "\n".join(summary_parts) if summary_parts else function_result[:2000]
            
        except (json.JSONDecodeError, TypeError):
            # 파싱 실패시 원본 일부 반환
            return str(function_result)[:2000]


# ============================================================
# 싱글톤
# ============================================================

_test_admin_agent = None

def get_test_admin_agent() -> TestAdminAgent:
    global _test_admin_agent
    if _test_admin_agent is None:
        _test_admin_agent = TestAdminAgent()
    return _test_admin_agent


# ============================================================
# 편의 함수
# ============================================================

async def evaluate_router(history: str, question: str, router_output: str) -> Dict[str, Any]:
    """Router 평가 편의 함수"""
    agent = get_test_admin_agent()
    return await agent.evaluate_router(history, question, router_output)


async def evaluate_main(
    history: str,
    question: str,
    router_output: str,
    function_result: str,
    final_answer: str
) -> Dict[str, Any]:
    """Main 평가 편의 함수"""
    agent = get_test_admin_agent()
    return await agent.evaluate_main(history, question, router_output, function_result, final_answer)


async def evaluate_pipeline(
    history: str,
    question: str,
    router_output: str,
    function_result: str,
    final_answer: str
) -> Dict[str, Any]:
    """Pipeline 평가 편의 함수"""
    agent = get_test_admin_agent()
    return await agent.evaluate_pipeline(history, question, router_output, function_result, final_answer)


# ============================================================
# 테스트
# ============================================================

async def _test():
    print("=" * 60)
    print("Admin Agent 2 테스트")
    print("=" * 60)
    
    agent = TestAdminAgent()
    
    # 테스트 데이터
    test_history = ""
    test_question = "서울대 정시 알려줘"
    test_router_output = json.dumps({
        "function_calls": [
            {
                "function": "univ",
                "params": {
                    "university": "서울대학교",
                    "query": "2026학년도 서울대학교 정시 모집요강"
                }
            }
        ]
    }, ensure_ascii=False)
    
    print(f"\n질문: {test_question}")
    print(f"Router 출력: {test_router_output}")
    print("\nRouter 평가 중...")
    
    router_result = await agent.evaluate_router(test_history, test_question, test_router_output)
    print(f"\nRouter 평가 결과:")
    print(json.dumps(router_result, ensure_ascii=False, indent=2))
    
    # Main 평가 테스트
    test_function_result = json.dumps({
        "univ_0": {
            "university": "서울대학교",
            "query": "2026학년도 정시",
            "count": 2,
            "chunks": [
                {"content": "서울대학교 2026학년도 정시 모집인원: 1,500명", "page_number": 5}
            ]
        }
    }, ensure_ascii=False)
    
    test_final_answer = """===SECTION_START:empathy===
서울대학교 정시에 관심이 있으시군요!
===SECTION_END===
===SECTION_START:fact_check===
【2026학년도 서울대학교 정시 모집요강】
<cite data-source="2026 서울대 정시 모집요강 5p" data-url="https://...">
• **모집인원**: **1,500명**
</cite>
===SECTION_END==="""
    
    print("\nMain 평가 중...")
    main_result = await agent.evaluate_main(
        test_history, test_question, test_router_output, test_function_result, test_final_answer
    )
    print(f"\nMain 평가 결과:")
    print(json.dumps(main_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
