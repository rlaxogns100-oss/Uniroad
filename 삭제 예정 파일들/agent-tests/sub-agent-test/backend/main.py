"""
Sub Agent 전용 테스트 서버
- 프로덕션과 동일한 로직 사용 (실제 DB 연결)
- UniversityAgent, ConsultingAgent, TeacherAgent 지원
- 커스텀 시스템 프롬프트 지원
- 프롬프트/데이터셋 저장/불러오기 지원
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
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

# 메인 프로젝트 경로 추가 (services import용)
backend_path = current_dir.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# API 키 확인
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    print(f"[INFO] Gemini API configured successfully")
else:
    print("[WARNING] No API key found. Set GEMINI_API_KEY in .env file")

# Sub Agents import (실제 프로덕션 코드)
from services.multi_agent.sub_agents import (
    UniversityAgent,
    ConsultingAgent,
    TeacherAgent
)

app = FastAPI(title="Sub Agent Test Server")

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
# Agent 타입별 기본 프롬프트
# =============================================================================

# UniversityAgent는 시스템 프롬프트가 없음 (검색 기반)
UNIVERSITY_AGENT_INFO = """
UniversityAgent는 시스템 프롬프트를 사용하지 않습니다.
Supabase에서 해시태그 기반으로 문서를 검색하고, Gemini로 요약 및 정보 추출만 수행합니다.
"""

# ConsultingAgent 기본 시스템 프롬프트
CONSULTING_AGENT_DEFAULT_PROMPT = """당신은 대학 입시 데이터 분석 전문가입니다.
사용자의 성적을 '2026 수능 데이터' 기준으로 표준화하여 분석하고, 팩트 기반의 분석 결과만 제공하세요.

## 학생의 정규화된 성적 (등급-표준점수-백분위)
{normalized_scores_text}

## 경희대 2026 환산 점수 (600점 만점)
{khu_scores_text}

## 서울대 2026 환산 점수 (1000점 스케일)
{snu_scores_text}

## 연세대 2026 환산 점수 (1000점 만점)
{yonsei_scores_text}

## 고려대 2026 환산 점수 (1000점 환산)
{korea_scores_text}

## 서강대 2026 환산 점수
{sogang_scores_text}

## 가용 입결 데이터
{all_data}

## 출력 규칙 (필수)
1. **성적 정규화 결과 먼저 제시**: 학생의 입력을 등급-표준점수-백분위로 변환한 결과를 명시
2. 추정된 과목이 있으면 "(추정)" 표시
3. 질문에 필요한 핵심 데이터만 간결하게 제시
4. 수치 데이터는 정확하게 표기
5. 각 정보 뒤에 [출처: 컨설팅DB] 형식으로 출처 표시
6. JSON이 아닌 자연어로 출력
7. 격려나 조언은 하지 말고 오직 데이터만 제공
8. "합격가능", "도전가능" 같은 판단은 하지 말고 사실만 나열
9. 마크다운 문법(**, *, #, ##, ###) 절대 사용 금지
10. 글머리 기호는 - 또는 • 만 사용

## 출력 형식 예시
【학생 성적 정규화】
- 국어(언어와매체): 1등급 / 표준점수 140 / 백분위 98
- 수학(미적분): 2등급 / 표준점수 128 / 백분위 92
- 영어: 2등급 (추정)
[출처: 2026 수능 데이터]

【경희대 2026 환산 점수】
- 인문: 558.3점
- 사회: 562.1점
- 자연: 571.8점 (과탐가산 +8점)
- 예술체육: 548.2점
[출처: 경희대 2026 모집요강]

【서울대 2026 환산 점수 (1000점 스케일)】
- 일반전형: 410.8점 (1000점: 410.8)
- 순수미술: 276.0점 (1000점: 700점 기준)
[출처: 서울대 2026 모집요강]

【연세대 2026 환산 점수 (1000점 만점)】
- 인문: 856.2점, 자연: 872.1점
[출처: 연세대 2026 모집요강]

【고려대 2026 환산 점수 (1000점 환산)】
- 인문: 725.3점, 자연: 698.5점
[출처: 고려대 2026 모집요강]

【서강대 2026 환산 점수】
- 인문: 486.2점 (B형), 자연: 492.1점 (A형)
[출처: 서강대 2026 모집요강]

【입결 데이터 비교】
- 2025학년도 경희대 의예과 정시 70% 커트: 약 580점 (추정) [출처: 컨설팅DB]
- 2024학년도 서울대 기계공학부 수시 일반전형 70% 커트라인: 내신 1.5등급 [출처: 컨설팅DB]"""

# TeacherAgent 기본 시스템 프롬프트
TEACHER_AGENT_DEFAULT_PROMPT = """당신은 20년 경력의 입시 전문 선생님입니다.
학생의 상황을 파악하고 현실적이면서도 희망을 잃지 않는 조언을 해주세요.

## 조언 원칙
1. 현실적인 목표 설정 (무리한 목표는 지적)
2. 구체적인 시간표와 계획 제시
3. 멘탈 관리 조언 포함
4. 단기/중기/장기 목표 구분
5. 포기하지 않도록 격려하되, 거짓 희망은 주지 않기

## 출력 형식
- 자연어로 친근하게 작성
- 필요시 리스트나 표 사용
- 존댓말 사용"""

# =============================================================================
# API 모델
# =============================================================================
class SubAgentRequest(BaseModel):
    agent_type: str  # "university", "consulting", "teacher"
    university_name: Optional[str] = None  # UniversityAgent 전용
    query: str
    custom_prompt: Optional[str] = None

class SubAgentResponse(BaseModel):
    status: str
    agent_name: str
    query: str
    result: str
    normalized_scores: Optional[Dict] = None  # ConsultingAgent 전용
    sources: List[str]
    source_urls: List[str]
    citations: List[Dict]
    prompt_used: Optional[str] = None

class SavePromptRequest(BaseModel):
    agent_type: str
    name: str
    prompt: str
    description: Optional[str] = ""

class SaveDatasetRequest(BaseModel):
    agent_type: str
    university_name: Optional[str] = None
    name: str
    query: str
    description: Optional[str] = ""

# =============================================================================
# API 엔드포인트
# =============================================================================
@app.get("/")
async def root():
    api_status = "configured" if GEMINI_API_KEY else "not_configured"
    return {
        "message": "Sub Agent Test Server",
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

@app.post("/api/sub-agent", response_model=SubAgentResponse)
async def run_sub_agent(request: SubAgentRequest):
    """Sub Agent 실행"""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY를 설정하세요."
        )
    
    try:
        agent = None
        prompt_used = None
        
        # Agent 타입에 따라 생성
        if request.agent_type == "university":
            if not request.university_name:
                raise HTTPException(status_code=400, detail="university_name이 필요합니다")
            
            agent = UniversityAgent(
                university_name=request.university_name,
                custom_system_prompt=request.custom_prompt
            )
            prompt_used = "UniversityAgent는 시스템 프롬프트를 사용하지 않습니다 (검색 기반)"
            
        elif request.agent_type == "consulting":
            agent = ConsultingAgent(
                custom_system_prompt=request.custom_prompt
            )
            prompt_used = request.custom_prompt if request.custom_prompt else CONSULTING_AGENT_DEFAULT_PROMPT
            
        elif request.agent_type == "teacher":
            agent = TeacherAgent(
                custom_system_prompt=request.custom_prompt
            )
            prompt_used = request.custom_prompt if request.custom_prompt else TEACHER_AGENT_DEFAULT_PROMPT
            
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 agent_type입니다")
        
        # Agent 실행
        result = await agent.execute(request.query)
        
        return SubAgentResponse(
            status=result.get("status", "unknown"),
            agent_name=result.get("agent", ""),
            query=result.get("query", request.query),
            result=result.get("result", ""),
            normalized_scores=result.get("normalized_scores"),
            sources=result.get("sources", []),
            source_urls=result.get("source_urls", []),
            citations=result.get("citations", []),
            prompt_used=prompt_used
        )
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/default-prompt/{agent_type}")
async def get_default_prompt(agent_type: str):
    """기본 프롬프트 템플릿 반환"""
    if agent_type == "university":
        return {"prompt": UNIVERSITY_AGENT_INFO}
    elif agent_type == "consulting":
        return {"prompt": CONSULTING_AGENT_DEFAULT_PROMPT}
    elif agent_type == "teacher":
        return {"prompt": TEACHER_AGENT_DEFAULT_PROMPT}
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 agent_type입니다")

@app.get("/api/agent-types")
async def get_agent_types():
    """지원되는 Agent 타입 목록"""
    return {
        "agent_types": [
            {
                "type": "university",
                "name": "대학별 Agent",
                "description": "Supabase에서 대학 입시 정보 검색",
                "universities": ["서울대", "연세대", "고려대", "성균관대", "경희대"],
                "requires_university_name": True,
                "supports_custom_prompt": False
            },
            {
                "type": "consulting",
                "name": "컨설팅 Agent",
                "description": "학생 성적 기반 합격 가능성 분석 및 점수 환산",
                "requires_university_name": False,
                "supports_custom_prompt": True
            },
            {
                "type": "teacher",
                "name": "선생님 Agent",
                "description": "학습 계획 수립 및 멘탈 관리 조언",
                "requires_university_name": False,
                "supports_custom_prompt": True
            }
        ]
    }

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
                    "agent_type": data.get("agent_type", ""),
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
    
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request.agent_type}_{safe_name}"
    file_path = PROMPTS_DIR / f"{file_id}.json"
    
    data = {
        "agent_type": request.agent_type,
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
                    "agent_type": data.get("agent_type", ""),
                    "university_name": data.get("university_name", ""),
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
    
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request.agent_type}_{safe_name}"
    file_path = DATASETS_DIR / f"{file_id}.json"
    
    data = {
        "agent_type": request.agent_type,
        "university_name": request.university_name,
        "name": request.name,
        "query": request.query,
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
    uvicorn.run(app, host="0.0.0.0", port=8092)
