"""
Sub Agents
- 대학별 Agent: 해당 대학 입학처 자료 조회
- 컨설팅 Agent: 전국 대학 합격 데이터 비교 분석
- 선생님 Agent: 목표 설정 및 공부 계획
"""

import google.generativeai as genai
from typing import Dict, Any
import json
import os
from dotenv import load_dotenv
from mock_database import (
    get_university_info,
    get_admission_data_by_grade,
    get_jeongsi_data_by_percentile,
    get_score_conversion_info,
    UNIVERSITY_DATA,
    ADMISSION_DATA_SUSI,
    ADMISSION_DATA_JEONGSI
)

# .env 파일 로드
load_dotenv()

# Gemini API 설정 (환경 변수에서 로드)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 설정 파일 경로
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agent_models_config.json")

# 에이전트별 모델 설정 기본값
DEFAULT_AGENT_MODEL_CONFIG = {
    "서울대 agent": "gemini-2.5-flash-lite",
    "연세대 agent": "gemini-2.5-flash-lite",
    "고려대 agent": "gemini-2.5-flash-lite",
    "성균관대 agent": "gemini-2.5-flash-lite",
    "경희대 agent": "gemini-2.5-flash-lite",
    "컨설팅 agent": "gemini-2.5-flash-lite",
    "선생님 agent": "gemini-2.5-flash-lite"
}

# 사용 가능한 모델 목록
AVAILABLE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.0-flash",
    "gemini-1.5-pro"
]

def load_agent_model_config():
    """저장된 모델 설정 로드"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️  설정 파일 로드 실패: {e}")
    return DEFAULT_AGENT_MODEL_CONFIG.copy()

def save_agent_model_config(config):
    """모델 설정 저장"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 모델 설정 저장 완료: {CONFIG_FILE}")
    except Exception as e:
        print(f"⚠️  설정 파일 저장 실패: {e}")

# 시작 시 설정 로드
AGENT_MODEL_CONFIG = load_agent_model_config()

def set_agent_model(agent_name: str, model_name: str):
    """에이전트의 모델 설정 (영구 저장)"""
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"사용할 수 없는 모델: {model_name}")
    AGENT_MODEL_CONFIG[agent_name] = model_name
    save_agent_model_config(AGENT_MODEL_CONFIG)

def get_agent_model_config():
    """현재 에이전트 모델 설정 반환"""
    return AGENT_MODEL_CONFIG.copy()

def get_available_models():
    """사용 가능한 모델 목록 반환"""
    return AVAILABLE_MODELS.copy()


class SubAgentBase:
    """Sub Agent 기본 클래스"""

    def __init__(self, name: str, description: str, model_name: str = "gemini-2.5-flash-lite"):
        self.name = name
        self.description = description
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """쿼리 실행 (하위 클래스에서 구현)"""
        raise NotImplementedError


class UniversityAgent(SubAgentBase):
    """대학별 Agent - 해당 대학 입학처 자료 조회"""

    def __init__(self, university_name: str, model_name: str = "gemini-2.5-flash-lite"):
        self.university_name = university_name
        super().__init__(
            name=f"{university_name} agent",
            description=f"{university_name} 입시 정보(입결, 모집요강, 전형별 정보)를 조회하는 에이전트",
            model_name=model_name
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """대학 정보 조회 및 쿼리에 맞게 정리"""

        # DB에서 대학 정보 조회
        db_data = get_university_info(self.university_name)

        if "error" in db_data:
            return {
                "agent": self.name,
                "status": "error",
                "result": db_data["error"]
            }

        # Gemini로 쿼리에 맞게 정보 정리
        system_prompt = f"""당신은 {self.university_name} 입시 정보를 정리하는 전문가입니다.
주어진 데이터베이스 정보를 바탕으로 사용자 질문에 맞는 정보만 추출하여 정리하세요.

## 데이터베이스 정보
{json.dumps(db_data, ensure_ascii=False, indent=2)}

## 규칙
1. 질문과 관련된 정보만 추출
2. 숫자 데이터는 정확하게 유지
3. 표 형식이 필요하면 마크다운 표 사용
4. 불필요한 설명 없이 팩트만 제공
5. JSON 형식으로 출력하지 말고, 자연어와 표로 정리"""

        try:
            response = self.model.generate_content(
                f"질문: {query}\n\n위 데이터베이스에서 관련 정보를 추출해서 정리해주세요.",
                generation_config={"temperature": 0.1}
            )

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": response.text,
                "raw_data": db_data
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e)
            }


class ConsultingAgent(SubAgentBase):
    """컨설팅 Agent - 전국 대학 합격 데이터 비교 분석"""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        super().__init__(
            name="컨설팅 agent",
            description="여러 대학/전형을 비교 분석, 합격 가능성 평가",
            model_name=model_name
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """성적 기반 합격 가능 대학 분석"""

        # 전처리된 성적 확인
        actual_query = query
        preprocessed_scores_text = ""
        
        if "[전처리된 성적]" in query:
            print("✅ 전처리된 성적 감지")
            parts = query.split("[원본 쿼리]")
            if len(parts) == 2:
                preprocessed_scores_text = parts[0].replace("[전처리된 성적]", "").strip()
                actual_query = parts[1].strip()
                print(f"   전처리된 성적:\n{preprocessed_scores_text[:200]}...")
                print(f"   실제 쿼리: {actual_query}")
        
        # 쿼리에서 성적 정보 추출 시도 (fallback)
        grade_info = self._extract_grade_from_query(query)

        # DB에서 데이터 조회
        susi_data = None
        jeongsi_data = None

        if grade_info.get("내신"):
            susi_data = get_admission_data_by_grade(grade_info["내신"])

        if grade_info.get("백분위"):
            jeongsi_data = get_jeongsi_data_by_percentile(grade_info["백분위"])

        # 전체 합격 데이터도 포함
        all_data = {
            "수시_합격데이터": ADMISSION_DATA_SUSI,
            "정시_합격데이터": ADMISSION_DATA_JEONGSI,
            "학생_성적분석": {
                "수시": susi_data,
                "정시": jeongsi_data
            } if (susi_data or jeongsi_data) else None
        }

        # Gemini로 분석
        student_score_section = ""
        if preprocessed_scores_text:
            student_score_section = f"""
## 학생 성적 (정규화됨)
{preprocessed_scores_text}
"""
        
        system_prompt = f"""당신은 대학 입시 데이터 분석 전문가입니다.
질문에 답변하기 위해 필요한 팩트와 데이터만 추출하여 제공하세요.
{student_score_section}
## 가용 데이터
{json.dumps(all_data, ensure_ascii=False, indent=2)[:8000]}

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
- 2024학년도 연세대 기계공학부 정시 70% 커트라인: 백분위 95.2 [출처: 컨설팅DB]"""

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n질문: {actual_query}\n\n위 데이터에서 질문에 답변하는데 필요한 정보만 추출하세요.",
                generation_config={"temperature": 0.1, "max_output_tokens": 1024}
            )

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": response.text,
                "grade_info": grade_info,
                "raw_data": {
                    "susi_analysis": susi_data,
                    "jeongsi_analysis": jeongsi_data
                }
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e)
            }

    def _extract_grade_from_query(self, query: str) -> Dict[str, float]:
        """쿼리에서 성적 정보 추출"""
        import re
        result = {}

        # 내신 등급 추출 (예: 2.5등급, 내신 2.5)
        grade_pattern = r'(\d+\.?\d*)\s*등급|내신\s*(\d+\.?\d*)'
        match = re.search(grade_pattern, query)
        if match:
            grade = match.group(1) or match.group(2)
            result["내신"] = float(grade)

        # 백분위 추출 (예: 백분위 95, 95%)
        pct_pattern = r'백분위\s*(\d+\.?\d*)|(\d+\.?\d*)\s*%'
        match = re.search(pct_pattern, query)
        if match:
            pct = match.group(1) or match.group(2)
            result["백분위"] = float(pct)

        return result


class TeacherAgent(SubAgentBase):
    """선생님 Agent - 목표 설정 및 공부 계획"""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        super().__init__(
            name="선생님 agent",
            description="현실적인 목표 설정 및 공부 계획 수립",
            model_name=model_name
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """학습 계획 및 조언 제공"""

        system_prompt = """당신은 20년 경력의 입시 전문 선생님입니다.
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

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n학생 질문: {query}\n\n선생님으로서 조언해주세요.",
                generation_config={"temperature": 0.7}
            )

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": response.text
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e)
            }


# ============================================================
# Agent Factory
# ============================================================

def get_agent(agent_name: str) -> SubAgentBase:
    """에이전트 이름으로 에이전트 인스턴스 반환 (설정된 모델 사용)"""

    agent_name_lower = agent_name.lower()
    model_name = AGENT_MODEL_CONFIG.get(agent_name, "gemini-2.5-flash-lite")

    if "서울대" in agent_name:
        return UniversityAgent("서울대", model_name=model_name)
    elif "고려대" in agent_name:
        return UniversityAgent("고려대", model_name=model_name)
    elif "연세대" in agent_name:
        return UniversityAgent("연세대", model_name=model_name)
    elif "성균관대" in agent_name:
        return UniversityAgent("성균관대", model_name=model_name)
    elif "경희대" in agent_name:
        return UniversityAgent("경희대", model_name=model_name)
    elif "컨설팅" in agent_name:
        return ConsultingAgent(model_name=model_name)
    elif "선생님" in agent_name:
        return TeacherAgent(model_name=model_name)
    else:
        # 알 수 없는 에이전트는 기본 대학 에이전트로 처리 시도
        for univ in ["서울대", "고려대", "연세대", "성균관대", "경희대"]:
            if univ in agent_name:
                return UniversityAgent(univ, model_name=model_name)

        raise ValueError(f"알 수 없는 에이전트: {agent_name}")


async def execute_sub_agents(
    execution_plan: list,
    extracted_scores: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Execution Plan에 따라 Sub Agent들을 병렬로 실행
    
    Args:
        execution_plan: 실행 계획
        extracted_scores: Orchestration이 추출한 구조화된 성적
    """
    
    # 병렬 실행을 위한 단일 스텝 실행 함수
    async def execute_single_step(step):
        step_num = step.get("step")
        agent_name = step.get("agent")
        query = step.get("query")
        
        print(f"🚀 [Step {step_num}] {agent_name} 병렬 실행 시작")

        # 컨설팅 agent 호출 시 성적 전처리
        if "컨설팅" in agent_name and extracted_scores:
            try:
                from score_preprocessing import build_preprocessed_query
                
                print(f"📊 [Step {step_num}] 성적 전처리: {len(extracted_scores)}개 과목")
                preprocessed_query = build_preprocessed_query(extracted_scores, query)
                
                if preprocessed_query != query:
                    query = preprocessed_query
                    print(f"✅ [Step {step_num}] 전처리 완료")
                    
            except Exception as e:
                print(f"⚠️ [Step {step_num}] 성적 전처리 실패: {e}")

        try:
            agent = get_agent(agent_name)
            result = await agent.execute(query)
            print(f"✅ [Step {step_num}] {agent_name} 완료")
            return (step_num, result)
        except Exception as e:
            print(f"❌ [Step {step_num}] {agent_name} 실패: {e}")
            return (step_num, {
                "agent": agent_name,
                "status": "error",
                "result": str(e)
            })
    
    # 모든 스텝을 병렬로 실행
    print(f"\n⚡ {len(execution_plan)}개 에이전트 병렬 실행 시작")
    tasks = [execute_single_step(step) for step in execution_plan]
    step_results = await asyncio.gather(*tasks)
    
    # 결과를 딕셔너리로 변환
    results = {}
    for step_num, result in step_results:
        results[f"Step{step_num}_Result"] = result
    
    print(f"⚡ 병렬 실행 완료\n")
    
    return results
