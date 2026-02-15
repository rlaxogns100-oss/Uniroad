"""
Router Agent
- 사용자 질문 → 적절한 함수 호출 결정
- Model: gemini-2.5-flash-lite
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
# Router Agent 설정
# ============================================================

ROUTER_CONFIG = {
    "model": "gemini-2.5-flash-lite",
    "temperature": 0.0,  # 0.0 ~ 2.0 (낮을수록 일관적, 높을수록 창의적)
    "max_output_tokens": 2048
}


# ============================================================
# 함수 정의
# ============================================================

AVAILABLE_FUNCTIONS = [

]


ROUTER_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Router Agent**입니다.

## 정체성
당신의 역할은 정보 검색을 위한 json 형식의 함수 호출입니다. 당신이 찾은 정보와 대화의 맥락을 종합하여 main agent가 최종적인 답변을 생성합니다, 정확한 함수를 올바르게 호출하여 정보를 검색하세요.
단일 질문 뿐 아니라 이전 대화 히스토리 내용을 고려하여 적절하게 판단하세요.
이전 히스토리의 출력은 main_agent의 출력 형식입니다. 따라하지 말고 아래에 명시된 출력 형식을 지키세요.

## 시점 동기화
- 2026년 1월 (2026학년도 입시 종료)
- "올해" = 2026학년도
- "작년 입결" = 2025학년도
- "나 고1인데" -> 2028년도 입시, "나 18살인데" -> 2027년도 입시(나이에 맞는 입시 요강 우선 탐색)
- 입시 결과는 최신 자료만 사용(2025학년도)

## functions 목록: "univ", "consult_jungsi", "consult_susi"
학생의 질문에 답하기 위해 어떤 정보가 필요할지 정확하게 판단하여 호출할 함수를 정하세요.
 - **univ(university, query):** 특정 대학의 입시 요강 조회
 - **consult_jungsi(j_score, university, department, range):** 여러 대학의 정시 결과 조회, 정시 성적 대학별 환산, 정시 성적에 따른 합격 가능성 평가 및 대학 추천
 - **consult_susi(s_scores, university, department, junhyung):** 여러 대학의 수시 전형결과 조회(학과별, 전형별 70%컷, 경쟁률, 충원률 등)
### 구체적인 학생의 성적대와 비교할 때, 대학의 입시 결과 데이터를 조회할 때에는 consult_jungsi 또는 consult_susi 함수를 꼭 호출할 것
### 위의 function-params 관계를 고수할 것. 예를 들어 consult_susi 함수를 호출할 때 range를 넣지 말 것.


## params 목록: "university", "query", "range", "department", "junhyung", "j_scores", "s_scores"
### 기본값은 빈 배열(단, Univ 함수의 university는 1개로 고정), 언급된 대학 전부 호출(sky 공대 -> 서울대, 연세대, 고려대, 중경외시 -> 중앙대학교, 연세대학교, 고려대학교, 서울시립대학교), 최대 개수는 8개
- **university:** 대학 정식명칭 (서울대학교, 경희대학교)
- **query:** 검색 쿼리 (연도 + 학교 반드시 명시, 여러 전형이나 학과가 언급되면 모두 포함, 학교는 university와 동일하게 유지)
- **range:** 분석 범위 리스트 ('안정', '적정', '소신', '도전', '어려움' 중 하나 선택, 없으면 [] = 전체 범위)
- **department:** 학과/전공 명칭
- **junhyung:** 잠재능력우수자, 가야인재 등의 대학별 전형 이름과 교과위주, 학생부종합 등의 일반적인 전형 이름을 모두 포함.
- **j_scores:** 제시된 정시 성적
- **s_scores:** 제시된 평균 내신


### j_scores 입력 방법
 - 학생의 입력 값에 따라 과목별 '표준점수', '등급', '백분위' 중 하나로 구분하여 작성
 - 5자리 축약형(예, 11232 → 국어/수학/영어/탐구1/탐구2 등급), 6자리 축약형(예, 211332 → 한국사/국어/수학/영어/탐구1/탐구2 등급)
 - 100점이 넘는 경우는 표준점수로 인식, 1자릿수 숫자는 등급으로 인식
- 일반 과목명 (선택과목 미언급): 국어, 수학, 영어, 한국사, 탐구1, 탐구2 → 그대로 출력
- 구체적 선택과목 (명시된 경우): 화법과작문(화작), 언어와매체(언매), 미적분, 확률과통계(확통), 기하, 생명과학1(생1), 지구과학1(지1), 생활과윤리(생윤), 사회문화(사문) 등 → 과목명 그대로 출력
- 성적이 추정 가능한 경우에는 임의로 추정하여 출력: "국어 영어는 1인데 수학은 좀 못해요 -> 3등급으로 추정"

#### j_scores 출력 형식
```json
{
  "j_scores": {
    "국어": {"type": "등급", "value": 1},
    "수학": {"type": "표준점수", "value": 140},
    "영어": {"type": "등급", "value": 2},
    "한국사": {"type": "등급", "value": 1},
    "탐구1": {"type": "등급", "value": 1, "과목명": "생활과윤리"},
    "탐구2": {"type": "등급", "value": 2, "과목명": "사회문화"}
  }
}
```

### s_scores 입력 방법
  - 기본은 9등급제 내신으로 가정, 09년생, 10년생(2009년생, 2010년생)은 5등급제 내신으로 가정. 따로 언급이 없는 경우에도 히스토리를 고려하여 학생의 내신이 5등급제 기준인지 9등급제 기준인지 파악할 것.
  - 09년생, 10년생(2009년생, 2010년생)은 5등급제 내신으로 가정
  - 5등급제 내신은 "2.3(5)" 형식으로 입력 (괄호 안에 5 표기)
  - 9등급제 내신은 그냥 "2.3" 또는 "2.3(9)"로 입력
  - 예시: 5등급제 1.5등급 → "1.5(5)", 9등급제 2.0등급 → "2.0" 또는 "2.0(9)"






* type: "등급", "표준점수", "백분위"
* 탐구 과목은 키를 "탐구1", "탐구2"로 고정하고, 과목명이 언급된 경우 "과목명" 필드 추가
* 한국사는 항상 포함 (미언급 시 1등급으로 기본 추정)

## 함수 사용 예시

### 질문1: 올해 수능으로 서울대 가려면 어떻게 해?

```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": ["서울대학교"],
        "query": ["2026학년도 서울대학교 정시 모집요강", "2025학년도 서울대학교 정시 전형결과"]
      }
    }
  ]
}

```

### 질문2: 나 내신 1.4인데 1.1까지 올리면 서울대 기계공학과 갈 수 있을까?

```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": ["서울대학교"],
        "query": ["2026학년도 서울대학교 정시 모집요강", "2025학년도 서울대학교 정시 전형결과"]
      }
    },
    {
      "function": "consult_susi",
      "params": {
        "university": ["서울대학교"],
        "s_scores": ["1.1", "1.4"],
        "department": ["기계공학과", "기계공학부"]
      }
    }
  ]
}

```

### 질문3(질문 2에 이어 연속 질문 Context 유지) : 그럼 어디 갈 수 있어?

```json
{
  "function_calls": [
    {
      "function": "consult_susi",
      "params": {
        "university": [],
        "s_scores": ["1.1", "1.4"],
        "department": ["기계공학과", "기계공학부"]
      }
    }
  ]
}

```

### 질문4(복합질문): 나 11232인데 경희대 갈 수 있어? 아니면 아무 공대나 추천해 줘.

```json
{
  "function_calls": [
    {
      "function": "consult_jungsi",
      "params": {
        "j_scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "등급", "value": 1},
          "영어": {"type": "등급", "value": 2},
          "탐구1": {"type": "등급", "value": 3},
          "탐구2": {"type": "등급", "value": 2}
        },
        "university": ["경희대학교"],
        "department": [],
        "range": []
      }
    },
    {
      "function": "consult_jungsi",
      "params": {
        "j_scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "등급", "value": 1},
          "영어": {"type": "등급", "value": 2},
          "탐구1": {"type": "등급", "value": 3},
          "탐구2": {"type": "등급", "value": 2}
        },
        "university": [""],
        "department": [],
        "range": ["안정", "적정", "도전"]
      }
    },
    {
      "function": "univ",
      "params": {
        "university": ["경희대학교"],
        "query": ["2026학년도 경희대학교 정시 모집요강"]
      }
    }
  ]
}

```

```

### 질문5(이전 히스토리를 반영한 쿼리생성): 각각 수능최저 알려줘

#### 이전 대화: user: 연세대학교 수시 전형이 뭐가 있어? bot:학생부교과전형(추천형),학생부종합전형(활동우수형), 논술전형, 특기자전형

```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": ["연세대학교"],
        "query": ["2026학년도 연세대학교 학생부교과전형(추천형) 수능 최저학력기준", "2026학년도 연세대학교 학생부교과전형(추천형) 수능 최저학력기준", "2026학년도 연세대학교 논술전형 수능 최저학력기준","2026학년도 연세대학교 특기자전형 수능 최저학력기준"]
      }
    }
  ]
}

```

### 질문6: 정시로 연세대가 가기 쉬울까 고려대가 가기 쉬울까

```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": ["연세대학교"],
        "query": ["2026학년도 연세대학교 정시 모집요강", "2025학년도 연세대학교 정시 전형결과"]
      }
    }
  ]
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": ["고려대학교"],
        "query": ["2026학년도 고려대학교 정시 모집요강", "2025학년도 고려대학교 정시 전형결과"]
      }
    }
  ]
}

```




반드시 JSON만 출력하세요. 다른 텍스트 절대 금지.
"""


class RouterAgent:
    """Router Agent"""
    
    def __init__(self, system_prompt: str = None):
        prompt = system_prompt if system_prompt else ROUTER_SYSTEM_PROMPT
        self.model = genai.GenerativeModel(
            model_name=ROUTER_CONFIG["model"],
            system_instruction=prompt
        )
        self.system_prompt = prompt  # 현재 사용 중인 프롬프트 저장
        self.generation_config = {
            "temperature": ROUTER_CONFIG["temperature"],
            "max_output_tokens": ROUTER_CONFIG["max_output_tokens"],
            "response_mime_type": "application/json"  # JSON 출력 강제
        }
    
    def _clean_history_content(self, content: str) -> str:
        """
        히스토리에서 main_agent 스타일 마커 제거
        Router가 main_agent 형식을 모방하지 않도록 방지
        """
        import re
        # ===SECTION_START:xxx=== 및 ===SECTION_END=== 제거
        content = re.sub(r'===SECTION_START[^=]*===\s*', '', content)
        content = re.sub(r'===SECTION_END===\s*', '', content)
        # <cite> 태그 제거 (내용은 유지)
        content = re.sub(r'<cite[^>]*>', '', content)
        content = re.sub(r'</cite>', '', content)
        return content.strip()
    
    async def route(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        질문 라우팅
        
        Returns:
            {"function_calls": [{"function": str, "params": dict}]}
        """
        # 히스토리 구성 (main_agent 스타일 마커 제거)
        gemini_history = []
        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
                    # main_agent 스타일 마커 제거
                    if role == "model":
                        content = self._clean_history_content(content)
                    gemini_history.append({"role": role, "parts": [content]})
        
        chat = self.model.start_chat(history=gemini_history)
        
        try:
            response = chat.send_message(
                message,
                generation_config=self.generation_config
            )
            raw_text = response.text.strip()
            result = self._parse_response(raw_text)
            result["raw_response"] = raw_text
            
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
                "function_calls": [],
                "error": str(e),
                "raw_response": ""
            }
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """JSON 파싱 (복구 로직 포함)"""
        original_text = text
        
        try:
            # JSON 블록 추출
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            parsed = json.loads(text)
            
            if "function_calls" not in parsed:
                parsed["function_calls"] = []
            
            return parsed
            
        except json.JSONDecodeError as e:
            # 복구 시도 1: 잘못된 params 구조 수정 (key 없는 값 제거)
            try:
                import re
                # "query": "값1",\n"값2" 패턴을 "query": "값1" 로 수정
                fixed_text = re.sub(
                    r'("query"\s*:\s*"[^"]*")\s*,?\s*\n\s*"[^"]*"(?=\s*\})',
                    r'\1',
                    text
                )
                if fixed_text != text:
                    parsed = json.loads(fixed_text)
                    if "function_calls" not in parsed:
                        parsed["function_calls"] = []
                    parsed["_recovered"] = True
                    return parsed
            except:
                pass
            
            # 복구 시도 2: function_calls 배열만 추출
            try:
                import re
                match = re.search(r'"function_calls"\s*:\s*\[(.*?)\]', text, re.DOTALL)
                if match:
                    # 간단한 구조로 재구성
                    func_match = re.search(
                        r'"function"\s*:\s*"(\w+)".*?"university"\s*:\s*"([^"]*)".*?"query"\s*:\s*"([^"]*)"',
                        match.group(1), re.DOTALL
                    )
                    if func_match:
                        return {
                            "function_calls": [{
                                "function": func_match.group(1),
                                "params": {
                                    "university": func_match.group(2),
                                    "query": func_match.group(3)
                                }
                            }],
                            "_recovered": True
                        }
            except:
                pass
            
            return {
                "function_calls": [],
                "parse_error": str(e),
                "raw_text": original_text[:500]
            }


# 싱글톤
_router = None
_custom_prompt = None  # 프론트에서 설정한 커스텀 프롬프트

def get_router() -> RouterAgent:
    global _router
    if _router is None:
        _router = RouterAgent()
    return _router


def set_router_prompt(prompt: str) -> None:
    """프론트엔드에서 프롬프트 동적 변경"""
    global _router, _custom_prompt
    _custom_prompt = prompt
    # 새 프롬프트로 라우터 재생성
    _router = RouterAgent(system_prompt=prompt)


def get_router_prompt() -> str:
    """현재 사용 중인 프롬프트 반환"""
    global _custom_prompt
    return _custom_prompt if _custom_prompt else ROUTER_SYSTEM_PROMPT


def reset_router_prompt() -> None:
    """기본 프롬프트로 리셋"""
    global _router, _custom_prompt
    _custom_prompt = None
    _router = RouterAgent()


async def route_query(message: str, history: List[Dict] = None, user_id: str = None) -> Dict[str, Any]:
    """
    편의 함수 (프로필 점수 자동 보완 포함)
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리
        user_id: 사용자 ID (프로필 점수 조회용, optional)
    """
    router = get_router()
    result = await router.route(message, history)
    
    # consult 호출인데 scores가 없으면 프로필에서 가져오기
    if user_id:
        await _fill_scores_from_profile(result, user_id)
    
    return result


async def _fill_scores_from_profile(result: Dict[str, Any], user_id: str) -> None:
    """
    consult_jungsi 함수 호출에 j_scores가 없으면 프로필에서 가져와서 채우기
    
    조건:
    - consult_jungsi 함수가 호출되었고
    - j_scores 파라미터가 비어있거나 없을 때만
    
    프로필 점수 변환:
    - 표준점수 우선, 없으면 백분위, 없으면 등급
    - {"국어": {"등급": 1, "표준점수": 140, "백분위": 95, "선택과목": "화작"}}
      -> {"국어": {"type": "표준점수", "value": 140, "선택과목": "화작"}}
    """
    function_calls = result.get("function_calls", [])
    
    for call in function_calls:
        if call.get("function") == "consult_jungsi":
            params = call.get("params", {})
            scores = params.get("j_scores", {})
            
            # j_scores가 비어있으면 프로필에서 가져오기
            if not scores or len(scores) == 0:
                try:
                    from services.supabase_client import supabase_service
                    profile = await supabase_service.get_user_profile(user_id)
                    
                    if profile and profile.get("scores"):
                        profile_scores = profile["scores"]
                        print(f"📊 프로필 원본 점수: {profile_scores}")
                        # 프로필 점수를 consult_jungsi 함수 형식으로 변환
                        converted_scores = _convert_profile_scores_to_consult_format(profile_scores)
                        print(f"🔄 변환된 점수: {converted_scores}")
                        params["j_scores"] = converted_scores
                        print(f"✅ 프로필에서 점수 자동 보완 완료: {list(converted_scores.keys())}")
                    else:
                        print("⚠️ 프로필에 저장된 점수 없음")
                except Exception as e:
                    print(f"⚠️ 프로필 점수 조회 실패: {e}")


def _convert_profile_scores_to_consult_format(profile_scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    프로필 점수를 consult 함수 형식으로 변환
    
    Input (프로필):
        {"국어": {"등급": 1, "표준점수": 140, "백분위": 95, "선택과목": "화작"}}
    
    Output (consult):
        {"국어": {"type": "표준점수", "value": 140, "등급": 1, "백분위": 95, "선택과목": "화작"}}
    
    우선순위: 표준점수 > 백분위 > 등급 (type과 value 결정용)
    하지만 입력된 모든 점수 정보를 함께 전달
    """
    converted = {}
    
    for subject, score_data in profile_scores.items():
        if not isinstance(score_data, dict):
            continue
        
        # 우선순위에 따라 type과 value 결정 (메인 점수)
        score_type = None
        score_value = None
        
        if score_data.get("표준점수") is not None:
            score_type = "표준점수"
            score_value = score_data["표준점수"]
        elif score_data.get("백분위") is not None:
            score_type = "백분위"
            score_value = score_data["백분위"]
        elif score_data.get("등급") is not None:
            score_type = "등급"
            score_value = score_data["등급"]
        
        if score_type and score_value is not None:
            converted[subject] = {
                "type": score_type,
                "value": score_value
            }
            
            # 다른 점수 정보도 모두 추가 (있으면)
            if score_data.get("등급") is not None:
                converted[subject]["등급"] = score_data["등급"]
            if score_data.get("표준점수") is not None:
                converted[subject]["표준점수"] = score_data["표준점수"]
            if score_data.get("백분위") is not None:
                converted[subject]["백분위"] = score_data["백분위"]
            
            # 선택과목 추가 (있으면)
            if score_data.get("선택과목"):
                converted[subject]["선택과목"] = score_data["선택과목"]
    
    return converted


# ============================================================
# 테스트
# ============================================================

async def _test():
    print("=" * 60)
    print("Router Agent 테스트")
    print("=" * 60)
    print("종료: quit\n")
    
    router = RouterAgent()
    
    while True:
        try:
            user_input = input("질문: ").strip()
            
            if not user_input or user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            print("\n라우팅 중...")
            result = await router.route(user_input)
            
            print("\n" + "=" * 40)
            
            calls = result.get('function_calls', [])
            if calls:
                print(f"함수 호출 ({len(calls)}개):\n")
                for i, call in enumerate(calls, 1):
                    print(f"[{i}] {call.get('function')}()")
                    for key, value in call.get('params', {}).items():
                        if isinstance(value, dict):
                            print(f"    {key}:")
                            for k, v in value.items():
                                print(f"      {k}: {v}")
                        else:
                            print(f"    {key}: {value}")
                    print()
            else:
                print("함수 호출 없음")
            
            if "tokens" in result:
                t = result["tokens"]
                print(f"토큰: {t['total']} (입력 {t['in']}, 출력 {t['out']})")
            
            if "error" in result:
                print(f"오류: {result['error']}")
            
            print("-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n종료")
            break
        except Exception as e:
            print(f"오류: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
