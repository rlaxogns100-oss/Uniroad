"""
Sub Agents
- 대학별 Agent: Supabase에서 해당 대학 해시태그 문서 검색
- 컨설팅 Agent: 임시 DB에서 입결/환산점수 데이터 조회
- 선생님 Agent: 학습 계획 및 멘탈 관리 조언
"""

import google.generativeai as genai
from typing import Dict, Any, List
import json
import os
import re
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from token_logger import log_token_usage

from services.supabase_client import supabase_service
from services.gemini_service import gemini_service
from .mock_database import (
    get_admission_data_by_grade,
    get_jeongsi_data_by_percentile,
    get_score_conversion_info,
    get_all_universities_data,
    ADMISSION_DATA_SUSI,
    ADMISSION_DATA_JEONGSI
)

# 로그 콜백 (실시간 스트리밍용)
_log_callback = None

def set_log_callback(callback):
    """로그 콜백 설정"""
    global _log_callback
    _log_callback = callback

def _log(msg: str):
    """로그 출력 및 콜백 호출"""
    if _log_callback:
        _log_callback(msg)
    else:
        print(msg)

load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class SubAgentBase:
    """Sub Agent 기본 클래스"""

    def __init__(self, name: str, description: str, custom_system_prompt: str = None):
        self.name = name
        self.description = description
        self.custom_system_prompt = custom_system_prompt
        self.model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """쿼리 실행 (하위 클래스에서 구현)"""
        raise NotImplementedError


class UniversityAgent(SubAgentBase):
    """
    대학별 Agent - Supabase에서 해당 대학 해시태그 문서 검색
    
    검색 로직:
    1. 해시태그로 1차 탐색 (#{대학명})
    2. 요약본(500자) 분석으로 적합한 문서 선별
    3. 선별된 문서의 전체 내용 로드
    4. 정보 추출 후 출처와 함께 반환
    """

    SUPPORTED_UNIVERSITIES = ["서울대", "연세대", "고려대", "성균관대", "경희대"]

    def __init__(self, university_name: str, custom_system_prompt: str = None):
        self.university_name = university_name
        super().__init__(
            name=f"{university_name} agent",
            description=f"{university_name} 입시 정보(입결, 모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트",
            custom_system_prompt=custom_system_prompt
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """대학 정보 검색 및 정리"""
        _log("")
        _log("="*60)
        _log(f"🏫 {self.name} 실행")
        _log("="*60)
        _log(f"쿼리: {query}")

        try:
            client = supabase_service.get_client()

            # ============================================================
            # 1단계: 해시태그로 1차 탐색
            # ============================================================
            _log("")
            _log(f"📋 [1단계] 해시태그 검색: #{self.university_name}")
            
            metadata_response = client.table('documents_metadata').select('*').execute()
            
            if not metadata_response.data:
                return {
                    "agent": self.name,
                    "status": "no_data",
                    "result": f"{self.university_name} 관련 문서가 없습니다.",
                    "sources": [],
                    "source_urls": [],
                    "citations": []
                }

            # 해시태그 필터링
            required_univ_tag = f"#{self.university_name}"
            
            # 추가 해시태그 추출 (연도, 전형 등)
            optional_tags = []
            year_match = re.search(r'(2024|2025|2026|2027|2028)', query)
            if year_match:
                optional_tags.append(f"#{year_match.group()}")
            
            if '수시' in query:
                optional_tags.append('#수시')
            if '정시' in query:
                optional_tags.append('#정시')
            if any(word in query for word in ['요강', '모집']):
                optional_tags.append('#모집요강')
            if any(word in query for word in ['입결', '경쟁률', '커트']):
                optional_tags.append('#입결통계')

            # 필터링
            relevant_docs = []
            for doc in metadata_response.data:
                doc_hashtags = doc.get('hashtags', []) or []
                
                # 필수 조건: 대학 태그 포함
                if required_univ_tag not in doc_hashtags:
                    continue
                
                # 점수 계산
                score = 10  # 대학 태그 일치 기본 점수
                for tag in optional_tags:
                    if tag in doc_hashtags:
                        score += 5
                
                relevant_docs.append((score, doc))
            
            # 점수순 정렬
            relevant_docs.sort(key=lambda x: x[0], reverse=True)
            relevant_docs = [doc for score, doc in relevant_docs]
            
            _log(f"   {self.university_name} 관련 문서: {len(relevant_docs)}개")
            
            if not relevant_docs:
                return {
                    "agent": self.name,
                    "status": "no_match",
                    "result": f"{self.university_name} 관련 문서를 찾지 못했습니다.",
                    "sources": [],
                    "source_urls": [],
                    "citations": []
                }

            # ============================================================
            # 2단계: 요약본 분석 (500자 이내)
            # ============================================================
            _log("")
            _log(f"📋 [2단계] 요약본 분석")
            
            docs_summary_list = []
            for idx, doc in enumerate(relevant_docs[:10], 1):  # 최대 10개
                title = doc.get('title', '제목 없음')
                summary = doc.get('summary', '요약 없음')[:500]
                hashtags = doc.get('hashtags', [])
                docs_summary_list.append(
                    f"{idx}. 제목: {title}\n   해시태그: {', '.join(hashtags) if hashtags else '없음'}\n   요약: {summary}"
                )
            
            docs_summary_text = "\n\n".join(docs_summary_list)
            
            filter_prompt = f"""다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

질문: "{query}"

문서 목록:
{docs_summary_text}

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

답변 형식:
관련 문서가 있으면: 번호만 쉼표로 구분 (예: 1, 3)
관련 문서가 없으면: 없음"""

            try:
                filter_result = await gemini_service.generate(
                    filter_prompt,
                    "문서 필터링 전문가"
                )
                
                if not filter_result.strip() or "없음" in filter_result.lower():
                    # 필터링 실패시 상위 2개 사용
                    selected_docs = relevant_docs[:2]
                else:
                    selected_indices = [int(n.strip())-1 for n in re.findall(r'\d+', filter_result)]
                    selected_docs = [relevant_docs[i] for i in selected_indices if i < len(relevant_docs)]
                    if not selected_docs:
                        selected_docs = relevant_docs[:2]
                        
            except Exception as e:
                _log(f"   ⚠️ 요약본 분석 실패: {e}")
                selected_docs = relevant_docs[:2]
            
            _log(f"   선별된 문서: {len(selected_docs)}개")

            # ============================================================
            # 3단계: 전체 내용 로드
            # ============================================================
            _log("")
            _log(f"📋 [3단계] 문서 내용 로드")
            
            full_content = ""
            sources = []
            source_urls = []
            citations = []
            
            for doc in selected_docs:
                filename = doc['file_name']
                title = doc['title']
                file_url = doc.get('file_url') or ''
                
                sources.append(title)
                source_urls.append(file_url)
                
                _log(f"   📄 {title}")
                
                # 청크 가져오기
                chunks_response = client.table('policy_documents')\
                    .select('id, content, metadata')\
                    .eq('metadata->>fileName', filename)\
                    .execute()
                
                if chunks_response.data:
                    sorted_chunks = sorted(
                        chunks_response.data,
                        key=lambda x: x.get('metadata', {}).get('chunkIndex', 0)
                    )
                    
                    full_content += f"\n\n{'='*60}\n"
                    full_content += f"📄 {title}\n"
                    full_content += f"{'='*60}\n\n"
                    
                    # 청크 정보 저장 (답변 추적용)
                    for chunk in sorted_chunks:
                        chunk_content = chunk['content']
                        full_content += chunk_content
                        full_content += "\n\n"
                        
                        # 각 청크 정보를 citations에 저장 (chunk 키로)
                        # citations는 나중에 final_agent에서 추출됨
                        chunk_info = {
                            "id": chunk.get('id'),
                            "content": chunk_content,
                            "title": title,
                            "source": doc.get('source', ''),
                            "file_url": file_url,
                            "metadata": chunk.get('metadata', {})
                        }
                        citations.append({
                            "chunk": chunk_info,
                            "source": title,  # 기존 형식 유지
                            "url": file_url
                        })

            # ============================================================
            # 4단계: 정보 추출
            # ============================================================
            _log("")
            _log(f"📋 [4단계] 정보 추출")

            # 사용 가능한 출처 목록 생성
            sources_list = "\n".join([f"- {s}" for s in sources])

            extract_prompt = f"""다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

질문: {query}

사용 가능한 출처 목록:
{sources_list}

문서 내용:
{full_content[:15000]}

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. 여러 문서에서 정보를 가져왔다면, 각 정보마다 해당 출처를 표시
5. 마지막에 "출처: 문서1, 문서2, ..." 형태로 요약하지 말고, 정보마다 개별 표시
6. JSON이 아닌 자연어로 작성"""

            try:
                extracted_info = await gemini_service.generate(
                    extract_prompt,
                    "문서 정보 추출 전문가"
                )

                # citations는 이미 청크 정보와 함께 추가되었으므로 추가 작업 불필요

            except Exception as e:
                extracted_info = f"정보 추출 실패: {e}"
            
            _log(f"   추출된 정보 길이: {len(extracted_info)}자")
            _log("="*60)

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": extracted_info,
                "sources": sources,
                "source_urls": source_urls,
                "citations": citations
            }

        except Exception as e:
            _log(f"❌ {self.name} 오류: {e}")
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e),
                "sources": [],
                "source_urls": [],
                "citations": []
            }


class ConsultingAgent(SubAgentBase):
    """
    컨설팅 Agent - 임시 DB에서 입결/환산점수 데이터 조회
    5개 대학(서울대/연세대/고려대/성균관대/경희대) 데이터 사용
    """

    def __init__(self, custom_system_prompt: str = None):
        super().__init__(
            name="컨설팅 agent",
            description="5개 대학 합격 데이터 비교 분석, 합격 가능성 평가",
            custom_system_prompt=custom_system_prompt
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """성적 기반 합격 가능 대학 분석"""
        _log("")
        _log("="*60)
        _log(f"📊 컨설팅 Agent 실행")
        _log("="*60)
        _log(f"쿼리: {query}")

        # 쿼리에서 성적 정보 추출
        grade_info = self._extract_grade_from_query(query)
        _log(f"   추출된 성적: {grade_info}")

        # DB에서 데이터 조회
        susi_data = None
        jeongsi_data = None

        if grade_info.get("내신"):
            susi_data = get_admission_data_by_grade(grade_info["내신"])

        if grade_info.get("백분위"):
            jeongsi_data = get_jeongsi_data_by_percentile(grade_info["백분위"])

        # 전체 데이터 포함
        all_data = get_all_universities_data()
        all_data["학생_성적분석"] = {
            "수시": susi_data,
            "정시": jeongsi_data
        } if (susi_data or jeongsi_data) else None

        # Gemini로 분석
        if self.custom_system_prompt:
            system_prompt = self.custom_system_prompt.format(
                all_data=json.dumps(all_data, ensure_ascii=False, indent=2)[:8000]
            )
            print(f"🎨 Using custom system prompt for consulting agent")
        else:
            system_prompt = f"""당신은 대학 입시 데이터 분석 전문가입니다.
질문에 답변하기 위해 필요한 팩트와 데이터만 추출하여 제공하세요.

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
                f"{system_prompt}\n\n질문: {query}\n\n위 데이터에서 질문에 답변하는데 필요한 정보만 추출하세요.",
                generation_config={"temperature": 0.1, "max_output_tokens": 1024},
                request_options=genai.types.RequestOptions(
                    retry=None,
                    timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
                )
            )

            # 토큰 사용량 기록
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                print(f"💰 토큰 사용량 ({self.name}): {usage}")
                
                log_token_usage(
                    operation="입결비교에이전트",
                    prompt_tokens=getattr(usage, 'prompt_token_count', 0),
                    output_tokens=getattr(usage, 'candidates_token_count', 0),
                    total_tokens=getattr(usage, 'total_token_count', 0),
                    model="gemini-3-flash-preview",
                    details=self.name
                )

            result_text = response.text
            
            # citations 구성
            citations = [{
                "text": "5개 대학 입결 데이터 분석",
                "source": "컨설팅 DB (서울대/연세대/고려대/성균관대/경희대)",
                "url": ""
            }]

            _log(f"   분석 완료")
            _log("="*60)

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": result_text,
                "grade_info": grade_info,
                "sources": ["컨설팅 DB"],
                "source_urls": [],
                "citations": citations
            }

        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e),
                "sources": [],
                "source_urls": [],
                "citations": []
            }

    def _extract_grade_from_query(self, query: str) -> Dict[str, float]:
        """쿼리에서 성적 정보 추출"""
        result = {}

        # 내신 등급 추출
        grade_pattern = r'(\d+\.?\d*)\s*등급|내신\s*(\d+\.?\d*)'
        match = re.search(grade_pattern, query)
        if match:
            grade = match.group(1) or match.group(2)
            result["내신"] = float(grade)

        # 백분위 추출
        pct_pattern = r'백분위\s*(\d+\.?\d*)|(\d+\.?\d*)\s*%'
        match = re.search(pct_pattern, query)
        if match:
            pct = match.group(1) or match.group(2)
            result["백분위"] = float(pct)

        return result


class TeacherAgent(SubAgentBase):
    """선생님 Agent - 학습 계획 및 멘탈 관리 조언"""

    def __init__(self, custom_system_prompt: str = None):
        super().__init__(
            name="선생님 agent",
            description="현실적인 목표 설정 및 공부 계획 수립, 멘탈 관리",
            custom_system_prompt=custom_system_prompt
        )

    async def execute(self, query: str) -> Dict[str, Any]:
        """학습 계획 및 조언 제공"""
        _log("")
        _log("="*60)
        _log(f"👨‍🏫 선생님 Agent 실행")
        _log("="*60)
        _log(f"쿼리: {query}")

        if self.custom_system_prompt:
            system_prompt = self.custom_system_prompt
            print(f"🎨 Using custom system prompt for teacher agent")
        else:
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
                generation_config={"temperature": 0.7},
                request_options=genai.types.RequestOptions(
                    retry=None,
                    timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
                )
            )

            # 토큰 사용량 기록
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                print(f"💰 토큰 사용량 ({self.name}): {usage}")
                
                log_token_usage(
                    operation="선생님에이전트",
                    prompt_tokens=getattr(usage, 'prompt_token_count', 0),
                    output_tokens=getattr(usage, 'candidates_token_count', 0),
                    total_tokens=getattr(usage, 'total_token_count', 0),
                    model="gemini-3-flash-preview",
                    details=self.name
                )

            _log(f"   조언 완료")
            _log("="*60)

            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": response.text,
                "sources": [],
                "source_urls": [],
                "citations": []
            }

        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e),
                "sources": [],
                "source_urls": [],
                "citations": []
            }


# ============================================================
# Agent Factory
# ============================================================

def get_agent(agent_name: str) -> SubAgentBase:
    """에이전트 이름으로 에이전트 인스턴스 반환"""
    agent_name_lower = agent_name.lower()

    # 대학별 Agent
    for univ in UniversityAgent.SUPPORTED_UNIVERSITIES:
        if univ in agent_name:
            return UniversityAgent(univ)

    # 컨설팅 Agent
    if "컨설팅" in agent_name or "컨설턴트" in agent_name:
        return ConsultingAgent()

    # 선생님 Agent
    if "선생님" in agent_name or "선생" in agent_name:
        return TeacherAgent()

    raise ValueError(f"알 수 없는 에이전트: {agent_name}")


async def execute_sub_agents(execution_plan: list) -> Dict[str, Any]:
    """
    Execution Plan에 따라 Sub Agent들 실행
    
    Args:
        execution_plan: Orchestration Agent가 생성한 실행 계획
        
    Returns:
        {
            "Step1_Result": {...},
            "Step2_Result": {...},
            ...
        }
    """
    results = {}

    for step in execution_plan:
        step_num = step.get("step")
        agent_name = step.get("agent")
        query = step.get("query")

        _log(f"   Step {step_num}: {agent_name}")
        _log(f"   Query: {query}")

        try:
            agent = get_agent(agent_name)
            result = await agent.execute(query)
            results[f"Step{step_num}_Result"] = result
            
            status_icon = "✅" if result.get('status') == 'success' else "❌"
            _log(f"   {status_icon} Status: {result.get('status')}")
            sources_count = len(result.get('sources', []))
            if sources_count > 0:
                _log(f"   출처: {sources_count}개")
            
        except Exception as e:
            _log(f"   ❌ Error: {e}")
            results[f"Step{step_num}_Result"] = {
                "agent": agent_name,
                "status": "error",
                "result": str(e),
                "sources": [],
                "source_urls": [],
                "citations": []
            }

    return results
