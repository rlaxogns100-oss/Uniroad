"""
Sub Agent 전용 테스트 서버 (간단 버전)
- 의존성 충돌 없이 바로 실행 가능
- Mock 응답으로 UI 테스트 가능
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import json
from dotenv import load_dotenv
from pathlib import Path
import asyncio

# .env 파일 로드
current_dir = Path(__file__).parent
for env_path in [current_dir / ".env", current_dir.parent / ".env", current_dir.parent.parent / ".env", current_dir.parent.parent.parent / ".env", current_dir.parent.parent.parent / "backend" / ".env"]:
    if env_path.exists():
        print(f"[INFO] Loading .env from: {env_path}")
        load_dotenv(env_path)
        break

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    print(f"[INFO] Gemini API configured successfully")
else:
    print("[WARNING] No API key found")

app = FastAPI(title="Sub Agent Test Server (Simple)")

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

# API 모델
class SubAgentRequest(BaseModel):
    agent_type: str
    university_name: Optional[str] = None
    query: str
    custom_prompt: Optional[str] = None

class SubAgentResponse(BaseModel):
    status: str
    agent_name: str
    query: str
    result: str
    normalized_scores: Optional[Dict] = None
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

# Mock 응답 생성
def generate_mock_response(agent_type: str, university_name: Optional[str], query: str) -> Dict[str, Any]:
    """Mock 응답 생성"""
    
    if agent_type == "university":
        return {
            "status": "success",
            "agent_name": f"{university_name} agent",
            "query": query,
            "result": f"""【{university_name} 2025학년도 정시 입결】
• 의예과: 정시 모집 인원 40명, 70% 커트라인 약 99.5 백분위
• 공과대학: 정시 모집 인원 150명, 평균 백분위 95-97
• 경영학과: 정시 모집 인원 80명, 평균 백분위 96-98

【2026학년도 모집 변화】
• 의예과: 정원 5명 증가 예정
• 신설학과: AI융합학과 20명 신설

[출처: {university_name} 2025/2026 모집요강]

✅ Mock 데이터입니다. 실제 Sub Agent 연결은 의존성 설치 후 main.py를 사용하세요.""",
            "sources": [f"{university_name} 2025 입시결과", f"{university_name} 2026 모집요강"],
            "source_urls": ["https://example.com/2025", "https://example.com/2026"],
            "citations": [
                {"text": "입시 결과", "source": f"{university_name} 공식 자료", "url": "https://example.com/2025"}
            ],
            "prompt_used": "UniversityAgent는 시스템 프롬프트를 사용하지 않습니다 (검색 기반)"
        }
    
    elif agent_type == "consulting":
        return {
            "status": "success",
            "agent_name": "컨설팅 agent",
            "query": query,
            "result": """【학생 성적 정규화】
- 국어(언어와매체): 1등급 / 표준점수 140 / 백분위 98
- 수학(미적분): 1등급 / 표준점수 135 / 백분위 96
- 영어: 2등급 (추정)
- 탐구1(생명과학1): 3등급 / 표준점수 65 / 백분위 85
- 탐구2(지구과학1): 2등급 / 표준점수 68 / 백분위 90
[출처: 2026 수능 데이터]

【경희대 2026 환산 점수 (600점 만점)】
- 인문: 558.3점
- 자연: 571.8점 (과탐가산 +8점)
[출처: 경희대 2026 모집요강]

【서울대 2026 환산 점수 (1000점 스케일)】
- 일반전형: 410.8점 (1000점: 410.8)
[출처: 서울대 2026 모집요강]

【입결 데이터 비교】
- 2025학년도 경희대 의예과 정시 70% 커트: 약 580점 (추정)
- 학생 점수(571.8점)는 경희대 의대 합격선보다 약간 낮음
[출처: 컨설팅DB]

✅ Mock 데이터입니다. 실제 점수 계산은 의존성 설치 후 main.py를 사용하세요.""",
            "normalized_scores": {
                "과목별_성적": {
                    "국어": {"등급": 1, "표준점수": 140, "백분위": 98, "선택과목": "언어와매체"},
                    "수학": {"등급": 1, "표준점수": 135, "백분위": 96, "선택과목": "미적분"},
                    "영어": {"등급": 2, "백분위": 92, "추정됨": True},
                    "탐구1": {"등급": 3, "표준점수": 65, "백분위": 85},
                    "탐구2": {"등급": 2, "표준점수": 68, "백분위": 90}
                },
                "경희대_환산점수": {
                    "인문": {"계산_가능": True, "최종점수": 558.3},
                    "자연": {"계산_가능": True, "최종점수": 571.8, "과탐_가산점": 8}
                },
                "서울대_환산점수": {
                    "일반전형": {"계산_가능": True, "최종점수": 410.8, "최종점수_1000": 410.8}
                }
            },
            "sources": ["컨설팅 DB", "표준점수·백분위 산출 방식"],
            "source_urls": [],
            "citations": [
                {"text": "5개 대학 입결 데이터 분석", "source": "컨설팅 DB", "url": ""}
            ],
            "prompt_used": "ConsultingAgent 기본 프롬프트 (Mock)"
        }
    
    elif agent_type == "teacher":
        return {
            "status": "success",
            "agent_name": "선생님 agent",
            "query": query,
            "result": """안녕하세요! 20년 경력 입시 전문가입니다.

현재 성적을 보니 국어와 수학에서 1등급을 받아 아주 우수한 편입니다. 다만 탐구 과목에서 조금 더 노력이 필요해 보이네요.

【현실적인 목표 설정】
• 최상위권: 서울대, 연세대 (탐구 보완 필수)
• 안정권: 성균관대, 경희대
• 소신지원: 고려대 일부 학과

【단기 목표 (D-30)】
1. 탐구 과목 집중 학습 (하루 3시간 이상)
2. 약점 단원 보완
3. 모의고사 매일 1회 풀이

【중기 목표 (D-60)】
1. 전 과목 2회독 완료
2. 기출문제 완벽 정리
3. 취약 유형 집중 공략

【멘탈 관리】
- 하루 7시간 수면 필수
- 주 1회 휴식 시간 확보
- 긍정적 마인드 유지

함께 목표를 향해 달려가봅시다! 💪

✅ Mock 응답입니다. 실제 AI 응답은 의존성 설치 후 main.py를 사용하세요.""",
            "sources": [],
            "source_urls": [],
            "citations": [],
            "prompt_used": "TeacherAgent 기본 프롬프트 (Mock)"
        }
    
    return {
        "status": "error",
        "agent_name": "Unknown",
        "query": query,
        "result": "지원하지 않는 Agent 타입입니다.",
        "sources": [],
        "source_urls": [],
        "citations": [],
        "prompt_used": None
    }

@app.get("/")
async def root():
    return {
        "message": "Sub Agent Test Server (Simple - Mock Version)",
        "status": "running",
        "api_key_status": "configured" if GEMINI_API_KEY else "not_configured",
        "note": "⚠️ Mock 버전: UI 및 프롬프트 테스트용. 실제 DB 연결 및 점수 계산은 main.py를 사용하세요 (pydantic 의존성 해결 필요)"
    }

@app.get("/api/check-api-key")
async def check_api_key():
    return {
        "configured": bool(GEMINI_API_KEY),
        "key_preview": f"{GEMINI_API_KEY[:8]}..." if GEMINI_API_KEY else None
    }

@app.post("/api/sub-agent", response_model=SubAgentResponse)
async def run_sub_agent(request: SubAgentRequest):
    """Sub Agent 실행 (Mock)"""
    
    # 약간의 지연 (실제 API 호출처럼 보이게)
    await asyncio.sleep(1)
    
    response_data = generate_mock_response(request.agent_type, request.university_name, request.query)
    
    return SubAgentResponse(**response_data)

@app.get("/api/default-prompt/{agent_type}")
async def get_default_prompt(agent_type: str):
    """기본 프롬프트 템플릿 반환"""
    prompts = {
        "university": "UniversityAgent는 시스템 프롬프트를 사용하지 않습니다 (Supabase 검색 기반)",
        
        "consulting": """당신은 대학 입시 데이터 분석 전문가입니다.
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

【입결 데이터 비교】
- 2025학년도 경희대 의예과 정시 70% 커트: 약 580점 (추정) [출처: 컨설팅DB]""",
        
        "teacher": """당신은 20년 경력의 입시 전문 선생님입니다.
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
    }
    return {"prompt": prompts.get(agent_type, "Unknown agent type")}

@app.get("/api/agent-types")
async def get_agent_types():
    """지원되는 Agent 타입 목록"""
    return {
        "agent_types": [
            {
                "type": "university",
                "name": "대학별 Agent",
                "description": "Supabase에서 대학 입시 정보 검색 (Mock)",
                "universities": ["서울대", "연세대", "고려대", "성균관대", "경희대"],
                "requires_university_name": True,
                "supports_custom_prompt": False
            },
            {
                "type": "consulting",
                "name": "컨설팅 Agent",
                "description": "학생 성적 기반 합격 가능성 분석 (Mock)",
                "requires_university_name": False,
                "supports_custom_prompt": True
            },
            {
                "type": "teacher",
                "name": "선생님 Agent",
                "description": "학습 계획 수립 및 멘탈 관리 조언 (Mock)",
                "requires_university_name": False,
                "supports_custom_prompt": True
            }
        ]
    }

# 프롬프트/데이터셋 관리 (동일)
@app.get("/api/prompts")
async def list_prompts():
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
    file_path = PROMPTS_DIR / f"{prompt_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    file_path = PROMPTS_DIR / f"{prompt_id}.json"
    if file_path.exists():
        file_path.unlink()
    return {"message": "삭제 완료"}

@app.get("/api/datasets")
async def list_datasets():
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
    file_path = DATASETS_DIR / f"{dataset_id}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="데이터셋을 찾을 수 없습니다")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    file_path = DATASETS_DIR / f"{dataset_id}.json"
    if file_path.exists():
        file_path.unlink()
    return {"message": "삭제 완료"}

if __name__ == "__main__":
    import uvicorn
    print(f"[INFO] Storage directory: {STORAGE_DIR}")
    print(f"[INFO] This is a simplified version with MOCK responses")
    print(f"[INFO] For full functionality, install dependencies and use main.py")
    uvicorn.run(app, host="0.0.0.0", port=8092)
