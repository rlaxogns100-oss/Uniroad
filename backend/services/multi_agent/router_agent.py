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
    {
        "name": "univ",
        "params": ["university", "query"],
        "description": "특정 대학의 입시 정보 검색",
        "examples": [
            {"university": "서울대학교", "query": "2026학년도 기계공학부 정시"},
            {"university": "경희대학교", "query": "2025학년도 정시 입결"}
        ]
    },
    {
        "name": "consult",
        "params": ["scores", "target_univ", "target_major", "target_range"],
        "description": "성적 기반 합격 가능성 분석 (환산점수 계산 포함)",
        "score_format": "11232 = 국1/수1/영2/탐1=3/탐2=2",
        "examples": [
            {
                "scores": {"국어": 1, "수학": 1, "영어": 2, "탐구1": 3, "탐구2": 2},
                "target_univ": ["경희대학교"],
                "target_major": ["기계공학과"],
                "target_range": ["상향"]
            },
            {
                "scores": {"국어": 1, "수학": 1, "영어": 1},
                "target_univ": [],
                "target_major": ["전자공학과", "기계공학과"],
                "target_range": []
            }
        ]
    }
]


ROUTER_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Router Agent**입니다.

## 정체성
당신이 찾은 정보와 대화의 맥락을 종합하여 main agent가 최종적인 답변을 생성합니다, 정확한 함수를 올바르게 호출하여 정보를 검색하세요.

## 시점 동기화
- 2026년 1월 (2026학년도 입시 진행 중)
- "올해" = 2026학년도
- "작년 입결" = 2025학년도
- "나 고1인데" -> 2028년도 입시, "나 18살인데" -> 2027년도 입시(나이에 맞는 입시 요강 우선 탐색)
- 입시 결과는 최신 자료만 사용(2025학년도)

## 사용 가능한 함수

### univ(university, query)
특정 대학의 입시 정보를 검색합니다.
- university: 대학 정식명칭 (서울대학교, 경희대학교)
- query: 검색 쿼리 (연도 + 전형 + 학과 명시)

예시:
- "서울대 가는 법" -> univ("서울대학교", "서울대학교 2026학년도 모집요강")
- "서울대 기계과 정시" → univ("서울대학교", "2026학년도 기계공학부 정시")
- "나 고1인데 경희대 농어촌 전형 알려줘" → univ("경희대학교", "2028 경희대학교 농어촌 전형")

### consult(scores, target_univ, target_major, target_range)
대학 입결 조회, 학생 성적 대학별 환산점수 변환, 합격 가능성 평가
학생 성적을 분석하여 합격 가능성을 평가합니다. 환산점수 계산 포함.
- scores: 성적 딕셔너리 {"국어": {"type": "등급", "value": 1}, ...}
- target_univ: 분석 대상 대학 리스트 (없으면 [])
- target_major: 관심 학과 리스트 (없으면 [])
- target_range: 분석 범위 리스트 (없으면 [] = 전체 범위)

#### 성적 입력 형식
1. 축약형 (5자리): "11232" → 국어/수학/영어/탐구1/탐구2 등급
2. 축약형 (6자리): "211332" → 한국사/국어/수학/영어/탐구1/탐구2 등급
3. 등급: "국어 1등급", "수학 2등급"
4. 표준점수: "수학 140점", "수학 표준점수 140"
5. 백분위: "국어 백분위 98"

#### 과목명 처리
- 일반 과목명 (선택과목 미언급): 국어, 수학, 영어, 한국사, 탐구1, 탐구2 → 그대로 출력
- 구체적 선택과목 (명시된 경우): 화법과작문(화작), 언어와매체(언매), 미적분, 확률과통계(확통), 기하, 생명과학1(생1), 지구과학1(지1), 생활과윤리(생윤), 사회문화(사문) 등 → 과목명 그대로 출력
- 성적이 추정 가능한 경우에는 임의로 추정하여 출력: "국어 영어는 1인데 수학은 좀 못해요 -> 3등급으로 추정"

#### 성적 출력 형식
```json
{
  "scores": {
    "국어": {"type": "등급", "value": 1},
    "수학": {"type": "표준점수", "value": 140},
    "영어": {"type": "등급", "value": 2}
  }
}
```
type: "등급", "표준점수", "백분위"

성적 예시:
- "11232" → {"국어": {"type": "등급", "value": 1}, "수학": {"type": "등급", "value": 1}, "영어": {"type": "등급", "value": 2}, "탐구1": {"type": "등급", "value": 3}, "탐구2": {"type": "등급", "value": 2}}
- "국어 화작 1등급, 수학 미적 140점" → {"화법과작문": {"type": "등급", "value": 1}, "미적분": {"type": "표준점수", "value": 140}}
- "생명과학1 2등급" → {"생명과학1": {"type": "등급", "value": 2}}

target_range 옵션:
- ["안정"]: 합격 확률 높은 대학/학과만, 일반적인 대학 추천 시, 안정적인 대학 추천 시 적용
- ["적정"]: 합격 가능성 있는 대학/학과만, 일반적인 대학 추천 시 적용
- ["상향"]: 도전적인 대학/학과만, 일반적인 대학 추천 시, 도전적인 대학 추천 시 적용
- ["스나이핑"]: 최상위 목표 대학/학과만, 최상위 목표 대학 추천 시 적용
- []: 빈 배열 = 모든 범위 (기본값), score가 주어지지 않으면 항상 빈 배열

예시:
- "나 11232인데 경희대 갈 수 있어?" → consult(scores, ["경희대학교"], [], [])
- "11112로 기계공학 어디 갈까?" → consult(scores, [], ["기계공학"], [적정, 안정, 상향])
- "적정 대학 추천해줘" → consult(scores, [], [], ["적정"])
- "상향으로 서울대 연세대 가능해?" → consult(scores, ["서울대학교", "연세대학교"], [], ["상향"])

## 출력 형식
반드시 JSON만 출력하세요. 다른 텍스트 절대 금지.

### 단일 함수 호출 예시 (올해 수능으로 서울대 가려면 어떻게 해?)
```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": "서울대학교",
        "query": "2026학년도 서울대학교 정시 모집요강", "2025학년도 서울대학교 정시 입결"
      }
    }
  ]
}
```

### 성적 분석 예시 (나 11232인데 경희대 갈 수 있어?)
```json
{
  "function_calls": [
    {
      "function": "consult",
      "params": {
        "scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "등급", "value": 1},
          "영어": {"type": "등급", "value": 2},
          "탐구1": {"type": "등급", "value": 3},
          "탐구2": {"type": "등급", "value": 2}
        },
        "target_univ": ["경희대학교"],
        "target_major": [],
        "target_range": []
      }
    },
    {
      "function": "univ",
      "params": {
        "university": "경희대학교",
        "query": "2026학년도 경희대학교 정시 모집요강"
      }
    }
  ]
}
```

### 적정 대학 추천 예시 (11112인데 적정 대학 추천해줘)
```json
{
  "function_calls": [
    {
      "function": "consult",
      "params": {
        "scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "등급", "value": 1},
          "영어": {"type": "등급", "value": 1},
          "탐구1": {"type": "등급", "value": 1},
          "탐구2": {"type": "등급", "value": 2}
        },
        "target_univ": [],
        "target_major": [],
        "target_range": ["적정"]
      }
    }
  ]
}
```

## 판단 규칙
1. **대학명 정규화**: 서울대 → 서울대학교, 고대 → 고려대학교
2. **연도 명시**: 항상 "XXXX학년도" 포함
3. **성적 질문**: 성적 + 특정 대학 언급 시 consult + univ 동시 호출
4. **대학명 언급 없는 막연한 질문에는 consult 호출**:  
    - "내 성적으로 어디 갈 수 있어?" → consult(scores, [], [], [안정, 적정, 상향])
    - "메디컬 가려면 공부 얼마나 해야 해?" → consult(scores, [], ['의예과', '치예과', '한의예과', '수의예과', '약학과'], [])
5. **비교 질문**: 여러 대학 비교 시 각각 univ 호출
6. **기본값은 빈 배열**: target_univ, target_major, target_range 모두 명시 안되면 []
7. **정확한 의도 파악**: 
    - "그래도 어디까진 확실히 될까?" -> consult(scores, [], [], ["적정", "안정"]), 
    - "어디까지 갈 수 있을까?" -> consult(scores, [], [], ["상향", "스나이핑"])
8. 애매하면 포괄적으로 정보 가져오기(어짜피 main agent에서 정보 선별, 단 최대 호출 수 3개로 제한)
    - "수도권 공대 중에 2등급이 갈 곳 알려줘" -> consult(scores, [], [공학], ["적정", "안정"]) (수도권은 변수 설정이 안 되지만, 모든 공대에 대해서 조사하면 main agent가 선별), 
    - "SKY 중에 공대 1000명 넘게 뽑는 곳 알려줘 -> 서울대, 연세대, 고려대 전부 호출

"""


class RouterAgent:
    """Router Agent"""
    
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=ROUTER_CONFIG["model"],
            system_instruction=ROUTER_SYSTEM_PROMPT
        )
        self.generation_config = {
            "temperature": ROUTER_CONFIG["temperature"],
            "max_output_tokens": ROUTER_CONFIG["max_output_tokens"]
        }
    
    async def route(self, message: str, history: List[Dict] = None) -> Dict[str, Any]:
        """
        질문 라우팅
        
        Returns:
            {"function_calls": [{"function": str, "params": dict}]}
        """
        # 히스토리 구성
        gemini_history = []
        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                if content:
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

def get_router() -> RouterAgent:
    global _router
    if _router is None:
        _router = RouterAgent()
    return _router


async def route_query(message: str, history: List[Dict] = None) -> Dict[str, Any]:
    """편의 함수"""
    router = get_router()
    return await router.route(message, history)


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
