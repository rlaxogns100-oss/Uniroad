"""
Final Agent 전용 테스트 서버
- 프로덕션과 동일한 프롬프트 사용
- user_question_with_context, structure_text, results_text, all_citations 직접 입력 가능
- 커스텀 프롬프트 및 데이터셋 저장/불러오기 지원
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import google.generativeai as genai
import os
import re
import json
from dotenv import load_dotenv
from pathlib import Path

# 프로젝트 루트의 .env 파일 로드 (여러 위치 시도)
current_dir = Path(__file__).parent
possible_env_paths = [
    current_dir / ".env",                          # 현재 디렉토리
    current_dir.parent / ".env",                   # final-agent-test/
    current_dir.parent.parent / ".env",            # agent-tests/
    current_dir.parent.parent.parent / ".env",     # UniZ/
    current_dir.parent.parent.parent / "backend" / ".env",  # UniZ/backend/
]

for env_path in possible_env_paths:
    if env_path.exists():
        print(f"[INFO] Loading .env from: {env_path}")
        load_dotenv(env_path)
        break

# Gemini API 설정 (여러 환경 변수 이름 시도)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"[INFO] Gemini API configured successfully")
else:
    print("[WARNING] No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env file")

app = FastAPI(title="Final Agent Test Server")

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
# 프로덕션과 100% 동일한 프롬프트 (prompt5 - 친절한 멘토링 버전)
# =============================================================================
DEFAULT_PROMPT_TEMPLATE = """
당신은 대한민국 최고의 입시 데이터 기반 AI 컨설턴트 [유니로드(UniRoad)]입니다.
사용자의 질문에 대해 [전문성]과 [따뜻한 멘토링]을 결합하여, 모바일에서도 읽기 편한 평문 기반의 친절한 답변을 제공하십시오.

---

### 1. 컨설팅 및 편집 원칙 (Strict Guidelines)
1. **톤앤매너 (Tone & Manner):**
   - 딱딱한 보고서체(~함, ~임) 대신, **정중하고 친절한 대화체(~해요, ~입니다)**를 사용하십시오.
   - 전문 용어는 정확히 쓰되, 설명은 이해하기 쉽게 풀어주십시오.
   - 데이터 분석은 날카롭게 하되, 사용자의 감정(불안, 기대)을 고려하여 공감하십시오.

2. **서식 제한 (Formatting):**
   - **Markdown 강조(**, ##, >, - 등) 절대 사용 금지.** 모든 텍스트는 평문(Plain Text)으로 작성하십시오.
   - 섹션 제목은 오직 `【제목】` 형식만 사용하십시오.
   - 줄글이 4줄 이상 넘어가지 않도록 끊고, 핵심 정보는 글머리 기호(•)로 요약하십시오. (최대 3개)

3. **인용(Citation):**
   - 데이터의 신뢰도를 위해 근거가 되는 부분 하단에는 반드시 `<cite>` 태그를 포함하십시오.

---

### 2. 섹션별 작성 전략 (Persona Switching)

**[Type A] 팩트 체크 및 분석 (Fact Check & Analysis)**
- **역할:** 냉철한 데이터 분석가
- **규칙:** 반드시 `【제목】`으로 시작하십시오. 그 다음 줄부터 본문을 작성하십시오.
- **내용:** 수집된 데이터를 비교/대조하고, 그 수치가 갖는 의미(유불리, 특징)를 친절하게 해석해주십시오.

**[Type B] 공감 및 격려 (Empathy & Encouragement)**
- **역할:** 따뜻한 입시 멘토
- **규칙:** 제목을 절대 붙이지 마십시오. 마커(`===SECTION_START===`) 다음 줄에 바로 본문을 시작하십시오.
- **내용:** 학생의 상황에 깊이 공감하고, 긴장을 풀어줄 수 있는 진정성 있는 말을 건네십시오.

**[Type C] 다음 단계 및 제언 (Next Step)**
- **역할:** 길잡이 (Navigator)
- **규칙:** 제목을 절대 붙이지 마십시오. 마커(`===SECTION_START===`) 다음 줄에 바로 본문을 시작하십시오.
- **내용:** 구체적으로 무엇을 더 확인해야 하는지, 어떤 전략을 짜야 하는지 행동 지침(Action Item)을 명확히 제안하십시오.

---

### 3. 출력 프로토콜 (SYSTEM CRITICAL)
시스템 파싱을 위해 아래 포맷 규칙을 기계적으로 준수하십시오.
- 모든 섹션은 `===SECTION_START===`와 `===SECTION_END===`로 감싸야 합니다.
- **마커, 제목, 본문, cite 태그 사이에는 빈 줄(New Line)을 절대 넣지 마십시오.**
- 빡빡하게 붙여서 출력하십시오.

[올바른 출력 예시]
===SECTION_START===
현재 성적 추이를 보면 걱정이 많으시겠지만, 아직 기회는 충분히 열려 있어요. 함께 전략을 세워봐요.
===SECTION_END===
===SECTION_START===
【2026학년도 의예과 모집 비교】
• 서울대: 정시 모집군이 변경될 가능성이 있으니 1월 확정안을 꼭 확인해야 해요.
• 경희대: 정원이 110명으로 확대되어 합격 가능성이 높아졌습니다.
<cite data-source="2026 대학입학전형계획" data-url="..."></cite>
===SECTION_END===

---

### 수행 작업
1. **입력 데이터:** 아래 [Sub Agent 결과]를 바탕으로 답변을 구성하십시오. 없는 사실을 지어내지 마십시오.
2. **목차 구성:** [Answer Structure]의 의도를 파악하여 유연하게 대처하십시오.
3. **최종 출력:** 위 [출력 프로토콜]에 맞춰 빈 줄 없이 작성하십시오.

===

[사용자 질문]
{user_question}

[Answer Structure]
{structure_text}

[Sub Agent 결과 (Raw Data)]
{results_text}

---

[참고 문헌 (ID 매핑)]
{all_citations}
"""


def post_process_sections(text: str) -> str:
    """섹션 마커 제거 및 cite 태그 정리"""
    section_pattern = r'===SECTION_START===(.*?)===SECTION_END==='
    
    sections = []
    for match in re.finditer(section_pattern, text, flags=re.DOTALL):
        section_content = match.group(1).strip()
        if not section_content:
            continue
        
        # cite 태그 찾기 (data-url은 선택적)
        cite_pattern = r'<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>.*?</cite>'
        citations = []
        seen = set()
        
        for cite_match in re.finditer(cite_pattern, section_content, flags=re.DOTALL):
            source = cite_match.group(1)
            url = cite_match.group(2) or ""  # data-url이 없으면 빈 문자열
            key = (source, url)
            if key not in seen and source:
                seen.add(key)
                citations.append((source, url))
        
        section_content_clean = re.sub(cite_pattern, '', section_content, flags=re.DOTALL)
        section_content_clean = section_content_clean.strip()
        
        if citations:
            cite_tags = '\n'.join([
                f'<cite data-source="{source}" data-url="{url}"></cite>'
                for source, url in citations
            ])
            final_section = section_content_clean + '\n' + cite_tags
        else:
            final_section = section_content_clean
        
        if final_section.strip():
            sections.append(final_section)
    
    if not sections:
        return text.strip()
    
    # 섹션 간 세 줄 간격으로 연결 (출처 포함 섹션 아래 빈 줄 하나 추가)
    return '\n\n\n'.join(sections).strip()


# =============================================================================
# API 모델
# =============================================================================
class FinalAgentRequest(BaseModel):
    user_question_with_context: str
    structure_text: str
    results_text: str
    all_citations: str  # JSON 문자열로 받음
    custom_prompt: Optional[str] = None  # 커스텀 프롬프트 (선택)


class FinalAgentResponse(BaseModel):
    status: str
    raw_answer: str
    processed_answer: str
    prompt_used: str
    prompt_length: int
    raw_length: int
    processed_length: int


class SavePromptRequest(BaseModel):
    name: str
    prompt: str
    description: Optional[str] = ""


class SaveDatasetRequest(BaseModel):
    name: str
    user_question_with_context: str
    structure_text: str
    results_text: str
    all_citations: str
    description: Optional[str] = ""


# =============================================================================
# API 엔드포인트
# =============================================================================
@app.get("/")
async def root():
    api_status = "configured" if GEMINI_API_KEY else "not_configured"
    return {
        "message": "Final Agent Test Server",
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


@app.post("/api/final-agent", response_model=FinalAgentResponse)
async def run_final_agent(request: FinalAgentRequest):
    """Final Agent 실행"""
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500, 
            detail="API 키가 설정되지 않았습니다. .env 파일에 GEMINI_API_KEY 또는 GOOGLE_API_KEY를 설정하세요."
        )
    
    try:
        # all_citations JSON 파싱
        try:
            citations = json.loads(request.all_citations) if request.all_citations.strip() else []
        except json.JSONDecodeError:
            citations = []
        
        citations_text = json.dumps(citations, ensure_ascii=False, indent=2)[:2000]
        
        # 프롬프트 생성
        if request.custom_prompt and request.custom_prompt.strip():
            # 커스텀 프롬프트 사용
            prompt = request.custom_prompt.format(
                user_question=request.user_question_with_context,
                structure_text=request.structure_text,
                results_text=request.results_text,
                all_citations=citations_text
            )
        else:
            # 기본 프롬프트 사용
            prompt = DEFAULT_PROMPT_TEMPLATE.format(
                user_question=request.user_question_with_context,
                structure_text=request.structure_text,
                results_text=request.results_text,
                all_citations=citations_text
            )
        
        # Gemini 호출 (프로덕션과 동일한 모델)
        model = genai.GenerativeModel(model_name="gemini-3-flash-preview")
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 4096
            }
        )
        
        raw_answer = response.text
        processed_answer = post_process_sections(raw_answer)
        
        return FinalAgentResponse(
            status="success",
            raw_answer=raw_answer,
            processed_answer=processed_answer,
            prompt_used=prompt,
            prompt_length=len(prompt),
            raw_length=len(raw_answer),
            processed_length=len(processed_answer)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/default-prompt")
async def get_default_prompt():
    """기본 프롬프트 템플릿 반환"""
    return {"prompt": DEFAULT_PROMPT_TEMPLATE}


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
    
    # 파일명 생성 (안전한 문자만)
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
    
    # 파일명 생성
    safe_name = "".join(c for c in request.name if c.isalnum() or c in ('-', '_', ' ')).strip()
    if not safe_name:
        safe_name = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    file_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    file_path = DATASETS_DIR / f"{file_id}.json"
    
    data = {
        "name": request.name,
        "user_question_with_context": request.user_question_with_context,
        "structure_text": request.structure_text,
        "results_text": request.results_text,
        "all_citations": request.all_citations,
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
    uvicorn.run(app, host="0.0.0.0", port=8090)
