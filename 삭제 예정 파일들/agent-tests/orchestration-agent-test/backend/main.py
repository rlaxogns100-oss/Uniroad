"""
Orchestration Agent 전용 테스트 서버
- 프로덕션과 동일한 로직 사용
- 커스텀 시스템 프롬프트 지원
- 프롬프트/데이터셋 저장/불러오기 지원
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
from pathlib import Path
import sys

# 프로젝트 루트의 .env 파일 로드
current_dir = Path(__file__).parent
possible_env_paths = [
    current_dir / ".env",
    current_dir.parent / ".env",
    current_dir.parent.parent / ".env",
    current_dir.parent.parent.parent / ".env",
    current_dir.parent.parent.parent / "backend" / ".env",
]

for env_path in possible_env_paths:
    if env_path.exists():
        print(f"[INFO] Loading .env from: {env_path}")
        load_dotenv(env_path)
        break

# 메인 프로젝트 경로 추가 (orchestration_agent import용)
backend_path = current_dir.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"[INFO] Gemini API configured successfully")
else:
    print("[WARNING] No API key found. Set GEMINI_API_KEY in .env file")

app = FastAPI(title="Orchestration Agent Test Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 저장 디렉토리 설정
STORAGE_DIR = current_dir / "storage"
PROMPTS_DIR = STORAGE_DIR / "prompts"
DATASETS_DIR = STORAGE_DIR / "datasets"

PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 프로덕션과 100% 동일한 시스템 프롬프트
# =============================================================================

# 가용 에이전트 목록 (프로덕션과 동일)
AVAILABLE_AGENTS = [
    {
        "name": "서울대 agent",
        "description": "서울대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "연세대 agent",
        "description": "연세대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "고려대 agent",
        "description": "고려대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "성균관대 agent",
        "description": "성균관대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "경희대 agent",
        "description": "경희대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "컨설팅 agent",
        "description": "5개 대학(서울대/연세대/고려대/성균관대/경희대) 합격 데이터 비교 분석, 학생 성적 기반 합격 가능성 평가 및 대학 추천, 정시 점수 환산"
    },
    {
        "name": "선생님 agent",
        "description": "현실적인 목표 설정 및 공부 계획 수립, 멘탈 관리 조언, 학습 전략"
    },
]

def format_agents_for_prompt() -> str:
    """에이전트 목록을 프롬프트용 문자열로 포맷"""
    result = []
    for agent in AVAILABLE_AGENTS:
        result.append(f"- **{agent['name']}**: {agent['description']}")
    return "\n".join(result)

DEFAULT_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Orchestration Agent (총괄 설계자 & PD)**입니다.

## 기본 설정
- **현재 시점:** 2026년 1월 (2026학년도 정시 진행 중)
- **검색 기준:** 사용자가 "작년 입결/결과"를 물으면 반드시 **[2025학년도]** 키워드로 쿼리를 생성하세요. (2026학년도는 결과 미확정, 2024학년도는 재작년임)

## 즉시 처리 규칙 (Immediate Processing)
아래 상황에서는 하위 Agent를 호출하지 않고, **당신이 직접 JSON의 'direct_response' 필드에 답변을 작성**하여 즉시 응답합니다.

1. **간단한 인사 및 잡담**:
   - 예: "안녕", "반가워", "너 누구야?"
   - 대응: 2026학년도 입시 파트너로서 친절하게 인사하고 성적 입력을 유도.

2. **정보가 심각하게 부족한 상담 요청**:
   - 기준: **국어, 수학, 영어, 탐구** 중 언급된 과목이 **2개 이하**인 경우.
   - 상황: "국어 1등급인데 대학 어디 가?", "나 수학 96점이야"
   - 대응: **"추가 정보 요청"**. 합격 예측을 위해서는 최소한 국/수/영/탐 등급이 필요함을 설명하고 입력을 유도.

## 학생의 입력 성적 처리 규칙

학생이 성적을 축약 형식으로 입력하는 경우 (예: "나 11232야", "13425"), 반드시 아래 규칙에 따라 풀어서 표현하세요:

1. **숫자 순서 해석**:
   - 첫 번째 숫자: 국어 등급
   - 두 번째 숫자: 수학 등급
   - 세 번째 숫자: 영어 등급
   - 네 번째 숫자: 탐구1 등급
   - 다섯 번째 숫자: 탐구2 등급

2. **풀어쓰기 형식** (반드시 "탐구1", "탐구2"로 명시):
   - 예시 1: "나 11232야" → "국어 1등급, 수학 1등급, 영어 2등급, 탐구1 3등급, 탐구2 2등급"
   - 예시 2: "13425" → "국어 1등급, 수학 3등급, 영어 4등급, 탐구1 2등급, 탐구2 5등급"
   - ❌ 틀린 예: "탐구 3등급, 탐구 2등급" (이렇게 쓰면 안 됨!)
   - ✅ 올바른 예: "탐구1 3등급, 탐구2 2등급" (반드시 탐구1, 탐구2로 구분)

3. **컨설팅 agent에게 전달할 쿼리 작성 시**:
   - 반드시 위 형식으로 풀어쓴 성적을 포함하여 쿼리를 작성하세요.
   - 예: "국어 1등급, 수학 1등급, 영어 2등급, 탐구1 3등급, 탐구2 2등급일 때의 예상 표준점수대 산출 및 2025학년도 입결 기준 서울대, 연세대, 고려대, 성균관대, 경희대 합격 가능성 분석"

## 역할
학생의 질문을 분석하여 세 가지를 결정합니다:
1. **Execution Plan**: 어떤 Sub Agent를 어떤 순서로 호출할지
2. **Answer Structure**: 최종 답변이 어떤 구조로 구성될지
3. **Extracted Scores**: 컨설팅 agent 호출 시 성적 정보 구조화 (조건부)

## 가용 에이전트 목록
{agents}

## 에이전트 역할
- 특정 대학이 언급되면 해당 대학 agent 호출
- 공부 계획, 멘탈 관리 질문은 선생님 agent 호출
- 합격 가능성, 대학 추천, 점수 환산 질문은 컨설팅 agent 호출

## 성적 정보 추출 규칙 (매우 중요!)
**컨설팅 agent를 호출할 계획이고, 사용자 질문에 성적 정보가 포함된 경우에만** `extracted_scores` 필드를 생성하세요.

### 생성 조건
- ✅ 컨설팅 agent 호출 예정 + 성적 정보 있음 → extracted_scores 생성
- ❌ 선생님/대학 agent만 호출 → extracted_scores 생성하지 않음
- ❌ 성적 정보 없음 → extracted_scores 생성하지 않음

### 지원 입력 형식
- 축약형: "나 11232야" → 순서: 국어/수학/영어/탐구1/탐구2 등급
- 등급: "국어 1등급", "수학 2등급"
- 표준점수: "국어 표준점수 140", "수학 140점" (100 이상은 표준점수)
- 백분위: "국어 백분위 98"
- 원점수: "국어 92점" (100점 만점, 100 미만)
- 자연어: "국어가 1등급이고 수학도 1등급인데요"

### 과목명 규칙
- **주요 과목**: 국어, 수학, 영어, 한국사
- **선택과목**: 선택과목이 언급되면 포함 (화법과작문, 언어와매체, 확률과통계, 미적분, 기하)
- **탐구 과목**: 반드시 구체적 과목명으로 추출
  - 사회탐구: 생활과윤리, 윤리와사상, 한국지리, 세계지리, 동아시아사, 세계사, 경제, 정치와법, 사회문화
  - 과학탐구: 물리학1, 물리학2, 화학1, 화학2, 생명과학1, 생명과학2, 지구과학1, 지구과학2

### 탐구 과목 추론 규칙
사용자가 구체적 탐구 과목을 말하지 않은 경우:
- 수학 선택과목이 "확률과통계"면 → 인문계로 추론 (생활과윤리, 사회문화)
- 수학 선택과목이 "미적분" 또는 "기하"면 → 자연계로 추론 (생명과학1, 지구과학1)
- 수학 선택과목 정보 없으면 → 인문계 기본값 (생활과윤리, 사회문화)

### 출력 형식
```json
"extracted_scores": {{
  "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
  "수학": {{"type": "표준점수", "value": 140, "선택과목": "미적분"}},
  "영어": {{"type": "등급", "value": 2}},
  "생명과학1": {{"type": "등급", "value": 3}},
  "지구과학1": {{"type": "등급", "value": 2}}
}}
```
- type: "등급", "표준점수", "백분위", "원점수" 중 하나
- value: 숫자 (등급은 1-9, 표준점수는 50-150, 백분위는 0-100)
- 선택과목: 국어/수학만 해당, 없으면 생략

## 답변 구조 섹션 타입
- `empathy`: 학생의 마음에 공감하는 따뜻한 위로 (1-2문장)
- `fact_check`: 정량적 데이터/팩트 제공 (입결, 경쟁률 등) - 출처 필요
- `analysis`: 학생 상황과 데이터 비교 분석 - 출처 필요
- `recommendation`: 구체적인 추천/제안
- `next_step`: 추가 질문 유도 또는 다음 단계 안내
- `warning`: 주의사항이나 리스크 안내
- `encouragement`: 격려와 응원 (1-2문장)

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

### 즉시 처리 시 (Immediate Processing)
```json
{{
  "user_intent": "사용자 의도 요약",
  "direct_response": "즉시 응답할 답변 내용 (2-3문장)",
  "execution_plan": [],
  "answer_structure": []
}}
```

### 컨설팅 agent 호출 시 (성적 포함)
```json
{{
  "user_intent": "사용자 의도 요약",
  "extracted_scores": {{
    "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
    "수학": {{"type": "등급", "value": 1, "선택과목": "확률과통계"}},
    "영어": {{"type": "등급", "value": 2}},
    "생활과윤리": {{"type": "등급", "value": 3}},
    "사회문화": {{"type": "등급", "value": 2}}
  }},
  "execution_plan": [
    {{
      "step": 1,
      "agent": "컨설팅 agent",
      "query": "2025학년도 입결 기준 서울대 합격 가능성 분석"
    }}
  ],
  "answer_structure": [...]
}}
```

### 다른 agent 호출 시 (성적 없음)
```json
{{
  "user_intent": "사용자 의도 요약",
  "execution_plan": [
    {{
      "step": 1,
      "agent": "서울대 agent",
      "query": "2026학년도 정시 모집요강 정보"
    }}
  ],
  "answer_structure": [...]
}}
```

## 규칙
1. 모호한 질문이라도 최선의 계획을 세우세요
2. answer_structure는 최소 2개, 최대 5개 섹션으로 구성
3. empathy 섹션은 항상 첫 번째에 배치
4. fact_check나 analysis가 있으면 반드시 해당 데이터를 가져올 execution_plan이 있어야 함
5. source_from은 execution_plan의 step 번호와 매칭되어야 함 (예: "Step1_Result")
6. agent 필드에는 가용 에이전트 목록에 있는 에이전트 이름만 사용
7. **extracted_scores는 컨설팅 agent 호출 시에만 생성** (다른 경우 필드 자체를 생략)

## 간결성 원칙 (매우 중요!)
- **불필요한 agent 호출 금지**: 간단한 질문에 여러 agent를 호출하지 마세요. 질문의 복잡도에 비례하여 최소한의 agent만 호출하세요.
- **불필요한 섹션 생성 금지**: 단순 인사나 가벼운 질문에 5개 섹션을 모두 채우지 마세요. 필요한 섹션만 간결하게 구성하세요.
- 간단한 질문 = 1~2개 agent, 2~3개 섹션
- 복잡한 비교/분석 질문 = 2개 이상 agent, 3~4개 섹션

## 대학 매칭 규칙
- 특정 대학이 언급되면 해당 대학 agent 호출
- "서울대 연대 고대 비교" 같은 경우 여러 대학 agent 호출
- 합격 가능성, 대학 추천, 점수 환산 질문은 컨설팅 agent 호출
- 공부 계획, 멘탈 관리 질문은 선생님 agent 호출
"""

def parse_orchestration_response(response_text: str) -> Dict[str, Any]:
    """Gemini 응답에서 JSON 추출 및 파싱"""
    import re
    try:
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            json_str = response_text.strip()

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {
            "error": "JSON 파싱 실패",
            "raw_response": response_text,
            "parse_error": str(e)
        }

# =============================================================================
# API 모델
# =============================================================================
class OrchestrationRequest(BaseModel):
    user_question: str
    conversation_history: Optional[List[Dict]] = []
    custom_prompt: Optional[str] = None

class OrchestrationResponse(BaseModel):
    status: str
    user_intent: str
    execution_plan: List[Dict]
    answer_structure: List[Dict]
    direct_response: Optional[str] = None
    raw_response: str
    prompt_used: str
    prompt_length: int
    # 성적 전처리 관련 추가 필드
    extracted_scores: Optional[Dict] = None
    preprocessed_queries: Optional[List[Dict]] = None  # 각 컨설팅 agent 쿼리에 대한 전처리 결과

class SavePromptRequest(BaseModel):
    name: str
    prompt: str
    description: Optional[str] = ""

class SaveDatasetRequest(BaseModel):
    name: str
    user_question: str
    conversation_history: str
    description: Optional[str] = ""

# =============================================================================
# API 엔드포인트
# =============================================================================
@app.get("/")
async def root():
    api_status = "configured" if GEMINI_API_KEY else "not_configured"
    return {
        "message": "Orchestration Agent Test Server",
        "status": "running",
        "api_key_status": api_status
    }

@app.get("/api/check-api-key")
async def check_api_key():
    """API 키 상태 확인"""
    return {
        "configured": bool(GEMINI_API_KEY),
        "key_preview": f"{GEMINI_API_KEY[:8]}..." if GEMINI_API_KEY else None
    }

@app.post("/api/orchestration", response_model=OrchestrationResponse)
async def run_orchestration(request: OrchestrationRequest):
    """Orchestration Agent 실행"""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY를 설정하세요."
        )
    
    try:
        # 프롬프트 생성
        if request.custom_prompt and request.custom_prompt.strip():
            system_prompt = request.custom_prompt.format(
                agents=format_agents_for_prompt()
            )
        else:
            system_prompt = DEFAULT_SYSTEM_PROMPT.format(
                agents=format_agents_for_prompt()
            )
        
        # Gemini 모델 생성
        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=system_prompt
        )
        
        # 대화 이력 구성
        gemini_history = []
        if request.conversation_history:
            for msg in request.conversation_history:
                role = "user" if msg.get("role") == "user" else "model"
                content = msg.get("content", "")
                gemini_history.append({
                    "role": role,
                    "parts": [content]
                })
        
        # Gemini 호출
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(request.user_question)
        
        raw_response = response.text.strip()
        
        # JSON 파싱
        result = parse_orchestration_response(raw_response)
        
        if "error" in result:
            return OrchestrationResponse(
                status="error",
                user_intent=result.get("raw_response", "")[:100],
                execution_plan=[],
                answer_structure=[],
                raw_response=result.get("raw_response", ""),
                prompt_used=system_prompt,
                prompt_length=len(system_prompt)
            )
        
        # extracted_scores가 있으면 성적 전처리 수행
        extracted_scores = result.get("extracted_scores")
        preprocessed_queries = None
        
        if extracted_scores:
            from score_preprocessing import build_preprocessed_query
            
            preprocessed_queries = []
            execution_plan = result.get("execution_plan", [])
            
            for step in execution_plan:
                agent_name = step.get("agent", "")
                original_query = step.get("query", "")
                
                # 컨설팅 agent 호출인 경우 전처리
                if "컨설팅" in agent_name:
                    preprocessed = build_preprocessed_query(extracted_scores, original_query)
                    preprocessed_queries.append({
                        "step": step.get("step"),
                        "agent": agent_name,
                        "original_query": original_query,
                        "preprocessed_query": preprocessed
                    })
                else:
                    preprocessed_queries.append({
                        "step": step.get("step"),
                        "agent": agent_name,
                        "original_query": original_query,
                        "preprocessed_query": None  # 컨설팅이 아니면 전처리 안 함
                    })
        
        return OrchestrationResponse(
            status="success",
            user_intent=result.get("user_intent", ""),
            execution_plan=result.get("execution_plan", []),
            answer_structure=result.get("answer_structure", []),
            direct_response=result.get("direct_response"),
            raw_response=raw_response,
            prompt_used=system_prompt,
            prompt_length=len(system_prompt),
            extracted_scores=extracted_scores,
            preprocessed_queries=preprocessed_queries
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/default-prompt")
async def get_default_prompt():
    """기본 프롬프트 템플릿 반환"""
    return {"prompt": DEFAULT_SYSTEM_PROMPT}

@app.get("/api/agents")
async def get_agents():
    """가용 에이전트 목록 조회"""
    return {"agents": AVAILABLE_AGENTS}

# =============================================================================
# 프롬프트 저장/불러오기
# =============================================================================
@app.get("/api/prompts")
async def list_prompts():
    """저장된 프롬프트 목록"""
    prompts = []
    for file in PROMPTS_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                prompts.append({
                    "id": file.stem,
                    "name": data.get("name", file.stem),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at", "")
                })
        except:
            pass
    return {"prompts": sorted(prompts, key=lambda x: x.get("created_at", ""), reverse=True)}

@app.post("/api/prompts")
async def save_prompt(request: SavePromptRequest):
    """프롬프트 저장"""
    from datetime import datetime
    
    safe_name = "".join(c for c in request.name if c.isalnum() or c in ('-', '_', ' ')).strip()
    if not safe_name:
        safe_name = f"prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    file_path = PROMPTS_DIR / f"{file_id}.json"
    
    data = {
        "name": request.name,
        "prompt": request.prompt,
        "description": request.description,
        "created_at": datetime.now().isoformat()
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {"id": file_id, "message": "저장 완료"}

@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """프롬프트 불러오기"""
    file_path = PROMPTS_DIR / f"{prompt_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    """프롬프트 삭제"""
    file_path = PROMPTS_DIR / f"{prompt_id}.json"
    if file_path.exists():
        file_path.unlink()
    return {"message": "삭제 완료"}

# =============================================================================
# 데이터셋 저장/불러오기
# =============================================================================
@app.get("/api/datasets")
async def list_datasets():
    """저장된 데이터셋 목록"""
    datasets = []
    for file in DATASETS_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                datasets.append({
                    "id": file.stem,
                    "name": data.get("name", file.stem),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at", "")
                })
        except:
            pass
    return {"datasets": sorted(datasets, key=lambda x: x.get("created_at", ""), reverse=True)}

@app.post("/api/datasets")
async def save_dataset(request: SaveDatasetRequest):
    """데이터셋 저장"""
    from datetime import datetime
    
    safe_name = "".join(c for c in request.name if c.isalnum() or c in ('-', '_', ' ')).strip()
    if not safe_name:
        safe_name = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    file_path = DATASETS_DIR / f"{file_id}.json"
    
    data = {
        "name": request.name,
        "user_question": request.user_question,
        "conversation_history": request.conversation_history,
        "description": request.description,
        "created_at": datetime.now().isoformat()
    }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {"id": file_id, "message": "저장 완료"}

@app.get("/api/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """데이터셋 불러오기"""
    file_path = DATASETS_DIR / f"{dataset_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="데이터셋을 찾을 수 없습니다")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """데이터셋 삭제"""
    file_path = DATASETS_DIR / f"{dataset_id}.json"
    if file_path.exists():
        file_path.unlink()
    return {"message": "삭제 완료"}

if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] Storage directory: {STORAGE_DIR}")
    print(f"[INFO] Prompts directory: {PROMPTS_DIR}")
    print(f"[INFO] Datasets directory: {DATASETS_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8091)
