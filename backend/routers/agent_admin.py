"""
Agent Admin Router
- 에이전트 관리 API
- 프롬프트 버전 관리
- 에이전트 단일/연결 실행
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import os
from datetime import datetime

# Multi-agent imports
from services.multi_agent.orchestration_agent import (
    run_orchestration_agent,
    AVAILABLE_AGENTS,
    ORCHESTRATION_SYSTEM_PROMPT
)
from services.multi_agent.sub_agents import (
    get_agent,
    execute_sub_agents,
    UniversityAgent,
    ConsultingAgent,
    TeacherAgent
)
from services.multi_agent.final_agent import generate_final_answer
from services.multi_agent.agent_prompts import (
    FINAL_AGENT_PROMPTS,
    get_final_agent_prompt
)

router = APIRouter()

# 프롬프트 버전 저장 경로
PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "prompts")
os.makedirs(PROMPTS_DIR, exist_ok=True)

# 에이전트 정의 (UI용)
AGENT_DEFINITIONS = {
    "orchestration": {
        "id": "orchestration",
        "name": "Orchestration Agent",
        "description": "사용자 질문 분석, 실행 계획 수립, 답변 구조 설계",
        "type": "orchestration",
        "color": "#6366f1",
        "inputs": ["user_message", "chat_history"],
        "outputs": ["execution_plan", "answer_structure"]
    },
    "final": {
        "id": "final",
        "name": "Final Agent",
        "description": "Sub Agent 결과를 종합하여 최종 답변 생성",
        "type": "final",
        "color": "#10b981",
        "inputs": ["user_question", "answer_structure", "sub_agent_results"],
        "outputs": ["final_answer"]
    },
    "seoul": {
        "id": "seoul",
        "name": "서울대 Agent",
        "description": "서울대학교 입시 정보 검색",
        "type": "university",
        "color": "#ef4444",
        "inputs": ["query"],
        "outputs": ["result", "sources"]
    },
    "yonsei": {
        "id": "yonsei",
        "name": "연세대 Agent",
        "description": "연세대학교 입시 정보 검색",
        "type": "university",
        "color": "#3b82f6",
        "inputs": ["query"],
        "outputs": ["result", "sources"]
    },
    "korea": {
        "id": "korea",
        "name": "고려대 Agent",
        "description": "고려대학교 입시 정보 검색",
        "type": "university",
        "color": "#dc2626",
        "inputs": ["query"],
        "outputs": ["result", "sources"]
    },
    "skku": {
        "id": "skku",
        "name": "성균관대 Agent",
        "description": "성균관대학교 입시 정보 검색",
        "type": "university",
        "color": "#059669",
        "inputs": ["query"],
        "outputs": ["result", "sources"]
    },
    "kyunghee": {
        "id": "kyunghee",
        "name": "경희대 Agent",
        "description": "경희대학교 입시 정보 검색",
        "type": "university",
        "color": "#7c3aed",
        "inputs": ["query"],
        "outputs": ["result", "sources"]
    },
    "consulting": {
        "id": "consulting",
        "name": "컨설팅 Agent",
        "description": "합격 데이터 분석, 합격 가능성 평가",
        "type": "consulting",
        "color": "#f59e0b",
        "inputs": ["query"],
        "outputs": ["result", "grade_info"]
    },
    "teacher": {
        "id": "teacher",
        "name": "선생님 Agent",
        "description": "학습 계획 및 멘탈 관리 조언",
        "type": "teacher",
        "color": "#ec4899",
        "inputs": ["query"],
        "outputs": ["result"]
    }
}


# ============================================================
# Pydantic Models
# ============================================================

class AgentExecuteRequest(BaseModel):
    agent_id: str
    inputs: Dict[str, Any]

class PipelineExecuteRequest(BaseModel):
    nodes: List[Dict[str, Any]]  # {agent_id, inputs}
    connections: List[Dict[str, Any]]  # {from_node, from_output, to_node, to_input}

class PromptSaveRequest(BaseModel):
    agent_id: str
    prompt_key: str
    content: str
    name: Optional[str] = None
    description: Optional[str] = None

class PromptVersionInfo(BaseModel):
    version_id: str
    name: str
    description: str
    created_at: str
    content: str


# ============================================================
# Agent Endpoints
# ============================================================

@router.get("/agents")
async def get_agents():
    """모든 에이전트 목록 조회"""
    return {
        "agents": list(AGENT_DEFINITIONS.values())
    }


@router.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str):
    """특정 에이전트 상세 정보"""
    if agent_id not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    agent = AGENT_DEFINITIONS[agent_id]
    
    # 현재 사용 중인 프롬프트 가져오기
    current_prompt = get_current_prompt(agent_id)
    
    return {
        "agent": agent,
        "current_prompt": current_prompt
    }


@router.post("/agents/{agent_id}/execute")
async def execute_agent(agent_id: str, request: AgentExecuteRequest):
    """단일 에이전트 실행"""
    if agent_id not in AGENT_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    try:
        result = await execute_single_agent(agent_id, request.inputs)
        return {
            "status": "success",
            "agent_id": agent_id,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipeline/execute")
async def execute_pipeline(request: PipelineExecuteRequest):
    """파이프라인 실행 (연결된 에이전트들) - Orchestration execution_plan 기반"""
    try:
        print("\n" + "="*80)
        print("🚀 PIPELINE EXECUTION REQUEST")
        print("="*80)
        print(f"📦 Nodes: {len(request.nodes)}")
        for node in request.nodes:
            print(f"   - {node.get('node_id', '?')}: agent={node.get('agent_id', '?')}, inputs={list(node.get('inputs', {}).keys())}")
            if node.get('inputs'):
                for k, v in node.get('inputs', {}).items():
                    v_str = str(v)[:100] if v else 'None'
                    print(f"      {k} = {v_str}")
        print(f"🔗 Connections: {len(request.connections)}")
        for conn in request.connections:
            print(f"   - {conn.get('from_node', '?')}.{conn.get('from_output', '?')} → {conn.get('to_node', '?')}.{conn.get('to_input', '?')}")
        print("="*80)
        
        results = {}
        node_outputs = {}
        orchestration_result = None
        agents_to_execute = set()  # execution_plan에서 실행할 에이전트
        
        # 노드 정렬 (의존성 순서대로)
        sorted_nodes = topological_sort(request.nodes, request.connections)
        
        for node in sorted_nodes:
            agent_id = node["agent_id"]
            node_id = node.get("node_id", agent_id)
            
            # Orchestration 먼저 실행
            if agent_id == "orchestration":
                inputs = dict(node.get("inputs", {}))
                for conn in request.connections:
                    if conn["to_node"] == node_id:
                        from_output = node_outputs.get(conn["from_node"], {}).get(conn["from_output"])
                        if from_output is not None:
                            inputs[conn["to_input"]] = from_output
                
                # user_message가 없으면 이 orchestration 노드 스킵
                user_message = inputs.get("user_message", "") or inputs.get("query", "")
                if not user_message or not str(user_message).strip():
                    print(f"⏭️  Skip orchestration {node_id}: no user_message")
                    results[node_id] = {
                        "status": "skipped",
                        "result": "입력 메시지 없음"
                    }
                    continue
                
                result = await execute_single_agent(agent_id, inputs)
                results[node_id] = result
                node_outputs[node_id] = result if isinstance(result, dict) else {"result": result}
                orchestration_result = result
                
                # execution_plan 파싱하여 실행할 에이전트 결정
                if isinstance(result, dict) and "execution_plan" in result:
                    for step in result["execution_plan"]:
                        agent_name = step.get("agent", "").lower()
                        # 에이전트 이름 매칭
                        for aid, adef in AGENT_DEFINITIONS.items():
                            if aid != "orchestration" and aid != "final":
                                if agent_name in adef["name"].lower() or adef["name"].lower() in agent_name:
                                    # 파이프라인에 있는 노드 찾기
                                    for n in sorted_nodes:
                                        if n["agent_id"] == aid:
                                            agents_to_execute.add(n.get("node_id", aid))
                continue
            
            # Final Agent는 항상 마지막에 실행
            if agent_id == "final":
                inputs = dict(node.get("inputs", {}))
                sub_agent_results = {}
                
                # 연결된 입력 수집
                for conn in request.connections:
                    if conn["to_node"] == node_id:
                        from_node_id = conn["from_node"]
                        from_output_key = conn["from_output"]
                        to_input_key = conn["to_input"]
                        
                        if to_input_key == "sub_agent_results":
                            # Sub agent 전체 결과를 가져옴 (result 필드만이 아니라 전체 dict)
                            from_node = next((n for n in sorted_nodes if n.get("node_id") == from_node_id), None)
                            if from_node and from_node["agent_id"] not in ["orchestration", "final"]:
                                step_key = f"Step{len(sub_agent_results) + 1}"
                                # 전체 결과 dict를 가져옴
                                full_result = node_outputs.get(from_node_id, {})
                                sub_agent_results[step_key] = full_result
                                print(f"   📥 {step_key}: {type(full_result).__name__} with keys: {list(full_result.keys()) if isinstance(full_result, dict) else 'N/A'}")
                        else:
                            # answer_structure 같은 다른 입력
                            from_output = node_outputs.get(from_node_id, {}).get(from_output_key)
                            if from_output is not None:
                                inputs[to_input_key] = from_output
                
                # sub_agent_results 추가
                if sub_agent_results:
                    inputs["sub_agent_results"] = sub_agent_results
                
                print(f"🔹 Final Agent inputs: {list(inputs.keys())}")
                print(f"   sub_agent_results: {list(sub_agent_results.keys())}")
                
                result = await execute_single_agent(agent_id, inputs)
                results[node_id] = result
                node_outputs[node_id] = result if isinstance(result, dict) else {"result": result}
                continue
            
            # Sub Agents - execution_plan에 있는 것만 실행
            if node_id not in agents_to_execute:
                print(f"⏭️  Skip: {node_id} (not in execution_plan)")
                results[node_id] = {
                    "agent": AGENT_DEFINITIONS.get(agent_id, {}).get("name", agent_id),
                    "status": "skipped",
                    "result": "Orchestration에서 이 에이전트를 호출하지 않음"
                }
                continue
            
            # 입력값 준비
            inputs = dict(node.get("inputs", {}))
            for conn in request.connections:
                if conn["to_node"] == node_id:
                    from_output = node_outputs.get(conn["from_node"], {}).get(conn["from_output"])
                    if from_output is not None:
                        # execution_plan -> query 변환
                        if conn["from_output"] == "execution_plan" and conn["to_input"] == "query":
                            if isinstance(from_output, list) and len(from_output) > 0:
                                target_agent_name = AGENT_DEFINITIONS.get(agent_id, {}).get("name", "")
                                query_found = False
                                for step in from_output:
                                    if isinstance(step, dict) and step.get("agent", "").lower() in target_agent_name.lower():
                                        inputs[conn["to_input"]] = str(step.get("query", ""))
                                        print(f"✅ {node_id} query: {step.get('query')}")
                                        query_found = True
                                        break
                                if not query_found and len(from_output) > 0:
                                    inputs[conn["to_input"]] = str(from_output[0].get("query", ""))
                            else:
                                inputs[conn["to_input"]] = str(from_output) if from_output else ""
                        else:
                            inputs[conn["to_input"]] = from_output
            
            # 에이전트 실행
            print(f"🔹 Executing: {node_id} with inputs: {inputs}")
            result = await execute_single_agent(agent_id, inputs)
            results[node_id] = result
            
            # 출력 저장
            if isinstance(result, dict):
                node_outputs[node_id] = result
            else:
                node_outputs[node_id] = {"result": result}
        
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Prompt Management Endpoints
# ============================================================

@router.get("/prompts/{agent_id}")
async def get_prompts(agent_id: str):
    """에이전트의 프롬프트 목록 조회"""
    prompts = []
    
    # 기본 프롬프트 정보
    if agent_id == "orchestration":
        prompts.append({
            "key": "system",
            "name": "Orchestration System Prompt",
            "current_version": "default",
            "versions": get_prompt_versions(agent_id, "system")
        })
    elif agent_id == "final":
        for key in ["prompt1", "prompt2", "prompt3", "prompt4"]:
            prompts.append({
                "key": key,
                "name": f"Final Agent {key.upper()}",
                "current_version": "prompt4" if key == "prompt4" else "default",
                "versions": get_prompt_versions(agent_id, key)
            })
    else:
        prompts.append({
            "key": "system",
            "name": f"{AGENT_DEFINITIONS.get(agent_id, {}).get('name', agent_id)} Prompt",
            "current_version": "default",
            "versions": get_prompt_versions(agent_id, "system")
        })
    
    return {"prompts": prompts}


@router.get("/prompts/{agent_id}/{prompt_key}")
async def get_prompt_content(agent_id: str, prompt_key: str, version: Optional[str] = None):
    """특정 프롬프트 내용 조회"""
    if version and version != "default":
        # 저장된 버전 조회
        version_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, f"{version}.json")
        if os.path.exists(version_path):
            with open(version_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
    
    # 기본 프롬프트 반환
    content = get_current_prompt(agent_id, prompt_key)
    return {
        "version_id": "default",
        "name": "기본 프롬프트",
        "description": "코드에 정의된 기본 프롬프트",
        "content": content,
        "created_at": None
    }


@router.post("/prompts/{agent_id}/{prompt_key}")
async def save_prompt(agent_id: str, prompt_key: str, request: PromptSaveRequest):
    """새 프롬프트 버전 저장 및 활성화"""
    version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_dir = os.path.join(PROMPTS_DIR, agent_id, prompt_key)
    os.makedirs(version_dir, exist_ok=True)
    
    version_data = {
        "version_id": version_id,
        "name": request.name or f"버전 {version_id}",
        "description": request.description or "",
        "content": request.content,
        "created_at": datetime.now().isoformat()
    }
    
    version_path = os.path.join(version_dir, f"{version_id}.json")
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(version_data, f, ensure_ascii=False, indent=2)
    
    # 저장과 동시에 활성 버전으로 설정
    active_path = os.path.join(version_dir, "active.json")
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump({"version_id": version_id}, f)
    
    print(f"✅ Saved and activated prompt: {agent_id}/{prompt_key} -> {version_id}")
    
    return {
        "status": "success",
        "version_id": version_id,
        "message": f"프롬프트 버전 {version_id} 저장 및 활성화됨"
    }


@router.put("/prompts/{agent_id}/{prompt_key}/{version_id}")
async def update_prompt(agent_id: str, prompt_key: str, version_id: str, request: PromptSaveRequest):
    """기존 프롬프트 버전 덮어쓰기"""
    version_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, f"{version_id}.json")
    
    if not os.path.exists(version_path):
        return {"status": "error", "message": "버전을 찾을 수 없습니다"}
    
    # 기존 데이터 읽기
    with open(version_path, "r", encoding="utf-8") as f:
        version_data = json.load(f)
    
    # 업데이트
    version_data["content"] = request.content
    version_data["name"] = request.name or version_data.get("name", f"버전 {version_id}")
    version_data["updated_at"] = datetime.now().isoformat()
    
    # 저장
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(version_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Updated prompt: {agent_id}/{prompt_key}/{version_id}")
    
    return {
        "status": "success",
        "message": f"프롬프트 {version_id} 업데이트됨"
    }


@router.put("/prompts/{agent_id}/{prompt_key}/active")
async def set_active_prompt(agent_id: str, prompt_key: str, version_id: str):
    """활성 프롬프트 버전 설정"""
    active_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, "active.json")
    
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump({"version_id": version_id}, f)
    
    print(f"✅ Activated prompt: {agent_id}/{prompt_key} -> {version_id}")
    
    return {
        "status": "success",
        "message": f"활성 버전이 {version_id}로 설정됨"
    }


@router.delete("/prompts/{agent_id}/{prompt_key}/{version_id}")
async def delete_prompt(agent_id: str, prompt_key: str, version_id: str):
    """저장된 프롬프트 버전 삭제"""
    version_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, f"{version_id}.json")
    
    if not os.path.exists(version_path):
        raise HTTPException(status_code=404, detail="해당 프롬프트 버전을 찾을 수 없습니다")
    
    # 현재 활성 버전인지 확인
    active_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, "active.json")
    if os.path.exists(active_path):
        with open(active_path, "r", encoding="utf-8") as f:
            active_data = json.load(f)
            if active_data.get("version_id") == version_id:
                # 활성 버전을 default로 되돌림
                with open(active_path, "w", encoding="utf-8") as f_write:
                    json.dump({"version_id": "default"}, f_write)
                print(f"⚠️ Deleted active version, reset to default")
    
    # 파일 삭제
    os.remove(version_path)
    print(f"🗑️ Deleted prompt: {agent_id}/{prompt_key}/{version_id}")
    
    return {
        "status": "success",
        "message": f"프롬프트 버전 {version_id}가 삭제되었습니다"
    }


# ============================================================
# Helper Functions
# ============================================================

def get_current_prompt(agent_id: str, prompt_key: str = "system") -> str:
    """현재 사용 중인 프롬프트 반환"""
    # 먼저 활성 버전 확인
    active_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, "active.json")
    if os.path.exists(active_path):
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            version_id = data.get("active_version")
            if version_id and version_id != "default":
                version_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, f"{version_id}.json")
                if os.path.exists(version_path):
                    with open(version_path, "r", encoding="utf-8") as vf:
                        return json.load(vf).get("content", "")
    
    # 기본 프롬프트 반환
    if agent_id == "orchestration":
        return ORCHESTRATION_SYSTEM_PROMPT
    elif agent_id == "final":
        try:
            # Final Agent 프롬프트는 파라미터가 필요하므로 기본값으로 호출
            return get_final_agent_prompt(
                prompt_key,
                user_question="[사용자 질문]",
                structure_text="[답변 구조]",
                results_text="[Sub Agent 결과]",
                all_citations=[]
            )
        except Exception as e:
            return f"프롬프트를 불러올 수 없습니다: {str(e)}"
    else:
        # Sub agent 실제 시스템 프롬프트
        agent_prompts = {
            "seoul": """대학 정보 검색 에이전트 - 서울대학교

## 역할
서울대학교 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트

## 검색 로직
1. 해시태그로 1차 탐색 (#서울대)
2. 요약본(500자) 분석으로 적합한 문서 선별
3. 선별된 문서의 전체 내용 로드
4. 정보 추출 후 출처와 함께 반환

## 문서 필터링 프롬프트
다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

## 정보 추출 프롬프트
다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. 여러 문서에서 정보를 가져왔다면, 각 정보마다 해당 출처를 표시
5. 마지막에 "출처: 문서1, 문서2, ..." 형태로 요약하지 말고, 정보마다 개별 표시
6. JSON이 아닌 자연어로 작성""",
            "yonsei": """대학 정보 검색 에이전트 - 연세대학교

## 역할
연세대학교 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트

## 검색 로직
1. 해시태그로 1차 탐색 (#연세대)
2. 요약본(500자) 분석으로 적합한 문서 선별
3. 선별된 문서의 전체 내용 로드
4. 정보 추출 후 출처와 함께 반환

## 문서 필터링 프롬프트
다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

## 정보 추출 프롬프트
다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. 여러 문서에서 정보를 가져왔다면, 각 정보마다 해당 출처를 표시
5. JSON이 아닌 자연어로 작성""",
            "korea": """대학 정보 검색 에이전트 - 고려대학교

## 역할
고려대학교 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트

## 검색 로직
1. 해시태그로 1차 탐색 (#고려대)
2. 요약본(500자) 분석으로 적합한 문서 선별
3. 선별된 문서의 전체 내용 로드
4. 정보 추출 후 출처와 함께 반환

## 문서 필터링 프롬프트
다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

## 정보 추출 프롬프트
다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. JSON이 아닌 자연어로 작성""",
            "skku": """대학 정보 검색 에이전트 - 성균관대학교

## 역할
성균관대학교 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트

## 검색 로직
1. 해시태그로 1차 탐색 (#성균관대)
2. 요약본(500자) 분석으로 적합한 문서 선별
3. 선별된 문서의 전체 내용 로드
4. 정보 추출 후 출처와 함께 반환

## 문서 필터링 프롬프트
다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

## 정보 추출 프롬프트
다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. JSON이 아닌 자연어로 작성""",
            "kyunghee": """대학 정보 검색 에이전트 - 경희대학교

## 역할
경희대학교 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트

## 검색 로직
1. 해시태그로 1차 탐색 (#경희대)
2. 요약본(500자) 분석으로 적합한 문서 선별
3. 선별된 문서의 전체 내용 로드
4. 정보 추출 후 출처와 함께 반환

## 문서 필터링 프롬프트
다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

## 정보 추출 프롬프트
다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. JSON이 아닌 자연어로 작성""",
            "consulting": """당신은 대학 입시 데이터 분석 전문가입니다.
질문에 답변하기 위해 필요한 팩트와 데이터만 추출하여 제공하세요.

## 가용 데이터
5개 대학(서울대/연세대/고려대/성균관대/경희대)의 입결 데이터:
- 수시: 학생부교과, 학생부종합 전형별 내신 커트라인
- 정시: 백분위 기반 커트라인

## 출력 규칙 (필수)
1. 질문에 필요한 핵심 데이터만 간결하게 제시
2. 수치 데이터는 정확하게 표기
3. 각 정보 뒤에 [출처: 컨설팅DB] 형식으로 출처 표시
4. JSON이 아닌 자연어로 출력
5. 격려나 조언은 하지 말고 오직 데이터만 제공
6. "합격가능", "도전가능" 같은 판단은 하지 말고 사실만 나열
7. 마크다운 문법(**, *, #, ##, ###) 절대 사용 금지
8. 글머리 기호는 - 또는 • 만 사용

예시:
- 2024학년도 서울대 기계공학부 수시 일반전형 70% 커트라인: 내신 1.5등급 [출처: 컨설팅DB]
- 2024학년도 연세대 기계공학부 정시 70% 커트라인: 백분위 95.2 [출처: 컨설팅DB]""",
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
        return agent_prompts.get(agent_id, f"{AGENT_DEFINITIONS.get(agent_id, {}).get('name', agent_id)}의 기본 시스템 프롬프트")


def get_prompt_versions(agent_id: str, prompt_key: str) -> List[Dict]:
    """프롬프트 버전 목록 조회"""
    versions = [{
        "version_id": "default",
        "name": "기본 프롬프트",
        "description": "코드에 정의된 기본 프롬프트",
        "created_at": None
    }]
    
    version_dir = os.path.join(PROMPTS_DIR, agent_id, prompt_key)
    if os.path.exists(version_dir):
        for filename in os.listdir(version_dir):
            if filename.endswith(".json") and filename != "active.json":
                filepath = os.path.join(version_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    versions.append({
                        "version_id": data.get("version_id"),
                        "name": data.get("name"),
                        "description": data.get("description", ""),
                        "created_at": data.get("created_at")
                    })
    
    return versions


def get_active_prompt(agent_id: str, prompt_key: str) -> Optional[str]:
    """활성 프롬프트 불러오기"""
    active_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, "active.json")
    if os.path.exists(active_path):
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                active_data = json.load(f)
                version_id = active_data.get("version_id")
                
            # 버전 파일 읽기
            version_path = os.path.join(PROMPTS_DIR, agent_id, prompt_key, f"{version_id}.json")
            if os.path.exists(version_path):
                with open(version_path, "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                    print(f"✅ Loaded active prompt for {agent_id}/{prompt_key}: {version_id}")
                    return version_data.get("content")
        except Exception as e:
            print(f"⚠️ Failed to load active prompt: {e}")
    return None


async def execute_single_agent(agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """단일 에이전트 실행"""
    
    if agent_id == "orchestration":
        # Orchestration Agent
        message = inputs.get("user_message", "")
        history = inputs.get("chat_history", [])
        
        # 저장된 프롬프트 확인
        custom_prompt = get_active_prompt(agent_id, "system")
        if custom_prompt:
            # 커스텀 프롬프트로 실행
            from services.multi_agent.orchestration_agent import run_orchestration_agent_with_prompt
            result = await run_orchestration_agent_with_prompt(message, history, custom_prompt)
        else:
            # 기본 프롬프트로 실행
            result = await run_orchestration_agent(message, history)
        return result
    
    elif agent_id == "final":
        # Final Agent
        user_question = inputs.get("user_question", "")
        answer_structure = inputs.get("answer_structure", [])
        sub_agent_results_raw = inputs.get("sub_agent_results", {})
        
        # sub_agent_results 형식 정규화
        # 파이프라인에서 전달되는 형식이 dict일 수 있으므로 {"Step1": {...}} 형식으로 변환
        if isinstance(sub_agent_results_raw, dict):
            # 이미 "Step1", "Step2" 같은 키가 있는지 확인
            if any(key.startswith("Step") for key in sub_agent_results_raw.keys()):
                sub_agent_results = sub_agent_results_raw
            else:
                # 단일 결과인 경우 Step1로 wrapping
                if "agent" in sub_agent_results_raw or "result" in sub_agent_results_raw:
                    sub_agent_results = {"Step1": sub_agent_results_raw}
                else:
                    sub_agent_results = sub_agent_results_raw
        else:
            sub_agent_results = {}
        
        # 저장된 프롬프트 확인 (현재 활성화된 prompt_key 확인)
        custom_prompt = None
        for key in ["prompt1", "prompt2", "prompt3", "prompt4"]:
            active_prompt = get_active_prompt(agent_id, key)
            if active_prompt:
                custom_prompt = active_prompt
                print(f"✅ Using active prompt: {key}")
                break
        
        if custom_prompt:
            # 커스텀 프롬프트로 실행
            from services.multi_agent.final_agent import final_agent
            result = await final_agent.generate_final_answer(
                user_question=user_question,
                answer_structure=answer_structure,
                sub_agent_results=sub_agent_results,
                custom_prompt=custom_prompt,
                history=[]  # 관리자 페이지는 맥락 없음
            )
        else:
            # 기본 프롬프트로 실행
            result = await generate_final_answer(
                user_question=user_question,
                answer_structure=answer_structure,
                sub_agent_results=sub_agent_results,
                history=[]  # 관리자 페이지는 맥락 없음
            )
        return result
    
    elif agent_id in ["seoul", "yonsei", "korea", "skku", "kyunghee"]:
        # University Agents
        university_map = {
            "seoul": "서울대",
            "yonsei": "연세대",
            "korea": "고려대",
            "skku": "성균관대",
            "kyunghee": "경희대"
        }
        university = university_map[agent_id]
        
        # 저장된 프롬프트 확인
        custom_prompt = get_active_prompt(agent_id, "system")
        agent = UniversityAgent(university, custom_prompt)
        
        query = inputs.get("query", "")
        result = await agent.execute(query)
        return result
    
    elif agent_id == "consulting":
        # Consulting Agent
        custom_prompt = get_active_prompt(agent_id, "system")
        agent = ConsultingAgent(custom_prompt)
        query = inputs.get("query", "")
        result = await agent.execute(query)
        return result
    
    elif agent_id == "teacher":
        # Teacher Agent
        custom_prompt = get_active_prompt(agent_id, "system")
        agent = TeacherAgent(custom_prompt)
        query = inputs.get("query", "")
        result = await agent.execute(query)
        return result
    
    else:
        raise ValueError(f"Unknown agent: {agent_id}")


def topological_sort(nodes: List[Dict], connections: List[Dict]) -> List[Dict]:
    """노드를 의존성 순서대로 정렬"""
    # 노드 ID를 키로 하는 딕셔너리 생성
    node_dict = {n.get("node_id", n["agent_id"]): n for n in nodes}
    
    # 각 노드의 의존성 계산
    dependencies = {n.get("node_id", n["agent_id"]): set() for n in nodes}
    for conn in connections:
        to_node = conn["to_node"]
        from_node = conn["from_node"]
        if to_node in dependencies:
            dependencies[to_node].add(from_node)
    
    # 위상 정렬
    sorted_nodes = []
    visited = set()
    
    def visit(node_id):
        if node_id in visited:
            return
        visited.add(node_id)
        for dep in dependencies.get(node_id, []):
            if dep in node_dict:
                visit(dep)
        sorted_nodes.append(node_dict[node_id])
    
    for node_id in node_dict:
        visit(node_id)
    
    return sorted_nodes
