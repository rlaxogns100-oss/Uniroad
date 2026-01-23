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
from services.score_converter import ScoreConverter
from services.school_score.khu_score_calculator import calculate_khu_score
from services.school_score.snu_score_calculator import calculate_snu_score
from services.school_score.yonsei_score_calculator import calculate_yonsei_score
from services.school_score.korea_score_calculator import calculate_korea_score
from services.school_score.sogang_score_calculator import calculate_sogang_score
from services.data_standard import (
    korean_std_score_table,
    math_std_score_table,
    social_studies_data,
    science_inquiry_data,
    major_subjects_grade_cuts,
    english_grade_data,
    history_grade_data
)
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
    
    점수 변환 기능:
    - 등급/표준점수/백분위/원점수 -> 등급-표준점수-백분위 정규화
    - 2026 수능 데이터 기준
    """

    def __init__(self, custom_system_prompt: str = None):
        super().__init__(
            name="컨설팅 agent",
            description="5개 대학 합격 데이터 비교 분석, 합격 가능성 평가",
            custom_system_prompt=custom_system_prompt
        )
        # ScoreConverter 초기화
        self.score_converter = ScoreConverter()
        
        # 2026 수능 데이터 준비
        self.score_data = {
            "국어": {
                "표준점수_테이블": {str(k): v for k, v in korean_std_score_table.items()},
                "선택과목_등급컷": major_subjects_grade_cuts.get("국어", {})
            },
            "수학": {
                "표준점수_테이블": {str(k): v for k, v in math_std_score_table.items()},
                "선택과목_등급컷": major_subjects_grade_cuts.get("수학", {})
            },
            "영어": english_grade_data,
            "한국사": history_grade_data,
            "사회탐구": social_studies_data,
            "과학탐구": science_inquiry_data
        }

    async def execute(self, query: str) -> Dict[str, Any]:
        """성적 기반 합격 가능 대학 분석"""
        _log("")
        _log("="*60)
        _log(f"📊 컨설팅 Agent 실행")
        _log("="*60)
        _log(f"쿼리: {query}")

        # 쿼리에서 성적 정보 추출 및 정규화
        raw_grade_info = self._extract_grade_from_query(query)
        _log(f"   추출된 원본 성적: {raw_grade_info}")
        
        # 점수 정규화 (등급-표준점수-백분위)
        normalized_scores = self._normalize_scores(raw_grade_info)
        _log(f"   정규화된 성적: {json.dumps(normalized_scores, ensure_ascii=False, indent=2)}")

        # 경희대 환산 점수 계산 (로컬 연산, API 호출 없음)
        khu_scores = calculate_khu_score(normalized_scores)
        normalized_scores["경희대_환산점수"] = khu_scores
        _log(f"   경희대 환산 점수 계산 완료")
        for track, score_data in khu_scores.items():
            if score_data.get("계산_가능"):
                _log(f"      {track}: {score_data['최종점수']}점 / 600점")
            else:
                _log(f"      {track}: 계산 불가 ({score_data.get('오류', 'Unknown')})")
        
        # 서울대 환산 점수 계산 (로컬 연산, API 호출 없음)
        snu_scores = calculate_snu_score(normalized_scores)
        normalized_scores["서울대_환산점수"] = snu_scores
        _log(f"   서울대 환산 점수 계산 완료")
        for track, score_data in snu_scores.items():
            if score_data.get("계산_가능"):
                _log(f"      {track}: {score_data['최종점수']}점 (1000점: {score_data.get('최종점수_1000', 'N/A')})")
            else:
                _log(f"      {track}: 계산 불가 ({score_data.get('오류', 'Unknown')})")
        
        # 연세대 환산 점수 계산 (로컬 연산, API 호출 없음)
        yonsei_scores = calculate_yonsei_score(normalized_scores)
        normalized_scores["연세대_환산점수"] = yonsei_scores
        _log(f"   연세대 환산 점수 계산 완료")
        for track, score_data in yonsei_scores.items():
            if score_data.get("계산_가능"):
                _log(f"      {track}: {score_data['최종점수']}점 / 1000점")
        
        # 고려대 환산 점수 계산 (로컬 연산, API 호출 없음)
        korea_scores = calculate_korea_score(normalized_scores)
        normalized_scores["고려대_환산점수"] = korea_scores
        _log(f"   고려대 환산 점수 계산 완료")
        for track, score_data in korea_scores.items():
            if score_data.get("계산_가능"):
                _log(f"      {track}: {score_data['최종점수']}점 / 1000점")
        
        # 서강대 환산 점수 계산 (로컬 연산, API 호출 없음)
        sogang_scores = calculate_sogang_score(normalized_scores)
        normalized_scores["서강대_환산점수"] = sogang_scores
        _log(f"   서강대 환산 점수 계산 완료")
        for track, score_data in sogang_scores.items():
            if score_data.get("계산_가능"):
                _log(f"      {track}: {score_data['최종점수']}점 ({score_data.get('적용방식', '')})")

        # ============================================================
        # Supabase에서 전형결과 문서 조회
        # ============================================================
        _log("")
        _log(f"📋 [전형결과 조회] Supabase에서 입결 데이터 검색")
        
        # 질의 분석: 정시/수시 구분 및 대학명 추출
        query_analysis = self._analyze_query(query)
        _log(f"   질의 분석: {json.dumps(query_analysis, ensure_ascii=False)}")
        
        # Supabase에서 전형결과 문서 조회
        admission_results = await self._fetch_admission_results_from_supabase(
            query_analysis, normalized_scores
        )
        
        # 기존 mock_database 데이터는 백업용으로 유지 (없으면 None)
        susi_data = None
        jeongsi_data = None
        
        # 정규화된 학생 성적과 전형결과 데이터 결합
        all_data = {
            "학생_정규화_성적": normalized_scores,
            "전형결과_데이터": admission_results,
            "질의_분석": query_analysis
        }

        # Gemini로 분석
        if self.custom_system_prompt:
            system_prompt = self.custom_system_prompt.format(
                all_data=json.dumps(all_data, ensure_ascii=False, indent=2)[:8000]
            )
            print(f"🎨 Using custom system prompt for consulting agent")
        else:
            # 정규화된 성적 정보 포맷팅
            normalized_scores_text = self._format_normalized_scores(normalized_scores)
            
            # 경희대 환산 점수 포맷팅
            khu_scores_text = self._format_khu_scores(khu_scores)
            
            # 서울대 환산 점수 포맷팅
            snu_scores_text = self._format_snu_scores(snu_scores)
            
            # 연세대 환산 점수 포맷팅
            yonsei_scores_text = self._format_yonsei_scores(yonsei_scores)
            
            # 고려대 환산 점수 포맷팅
            korea_scores_text = self._format_korea_scores(korea_scores)
            
            # 서강대 환산 점수 포맷팅
            sogang_scores_text = self._format_sogang_scores(sogang_scores)
            
            # 전형결과 데이터 포맷팅
            admission_results_text = self._format_admission_results(admission_results)
            
            # 프롬프트 길이 확인 및 제한
            _log(f"   📏 프롬프트 구성 요소 길이:")
            _log(f"      - normalized_scores_text: {len(normalized_scores_text)}자")
            _log(f"      - khu_scores_text: {len(khu_scores_text)}자")
            _log(f"      - snu_scores_text: {len(snu_scores_text)}자")
            _log(f"      - yonsei_scores_text: {len(yonsei_scores_text)}자")
            _log(f"      - korea_scores_text: {len(korea_scores_text)}자")
            _log(f"      - sogang_scores_text: {len(sogang_scores_text)}자")
            _log(f"      - admission_results_text: {len(admission_results_text)}자")
            
            # 전형결과 데이터가 너무 길면 제한 (최대 8000자)
            if len(admission_results_text) > 10000:
                _log(f"   ⚠️ 전형결과 데이터가 너무 깁니다 ({len(admission_results_text)}자). 8000자로 제한합니다.")
                admission_results_text = admission_results_text[:10000] + "\n\n... (전형결과 데이터 일부 생략)"
            
            system_prompt = f"""당신은 대학 입시 데이터 분석 전문가입니다.
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

## 전형결과 데이터 (2025학년도 입결 정보)
{admission_results_text}

## 출력 규칙 (필수 - 반드시 준수)
1. **반드시 3개 섹션 모두 포함**: 
   - 【학생 성적 정규화】
   - 【대학별 환산 점수】 (질문에 언급된 대학 또는 정시인 경우 5개 대학 모두)
   - 【2025학년도 전형결과 비교】 (학생 환산 점수와 실제 합격 점수 비교)
2. **환산 점수 먼저 명확히 제시**: 질문에 언급된 대학의 환산 점수를 먼저 보여주세요
3. **전형결과 데이터와 비교**: 환산 점수와 전형결과 문서의 실제 점수/등급을 비교하세요
4. **구체적인 학과 정보 제공**: 전형결과 데이터에서 해당 환산 점수로 합격한 학과와 그 점수를 구체적으로 제시하세요
5. 추정된 과목이 있으면 "(추정)" 표시
6. 수치 데이터는 정확하게 표기 (점수, 등급, 백분위 등)
7. JSON이 아닌 자연어로 출력
8. "합격가능", "도전가능", "거리가 있다" 같은 판단이나 평가는 하지 말고 오직 사실과 데이터만 제공
9. 마크다운 문법(**, *, #, ##, ###) 절대 사용 금지
10. 글머리 기호는 - 또는 • 만 사용
11. **출처 표시는 생략** (citation 비활성화)

## 출력 형식 예시

예시 1: "서울대 어디 갈 수 있을까?"
【학생 성적 정규화】
- 국어(언어와매체): 2등급 / 표준점수 132 / 백분위 92
- 수학(확률과통계): 2등급 / 표준점수 128 / 백분위 89
- 영어: 2등급 / 백분위 82
- 탐구1: 3등급 / 표준점수 57 / 백분위 83
- 탐구2: 3등급 / 표준점수 58 / 백분위 85

【서울대 2026 환산 점수】
- 일반전형: 375.5점 (1000점: 375.5)

【2025학년도 서울대 정시 전형결과 비교】
- 학생 환산 점수: 375.5점
- 전형결과 데이터에서 확인된 실제 합격 점수:
  • 공과대학 기계공학부: 최종합격자 평균 380.2점
  • 공과대학 전기정보공학부: 최종합격자 평균 385.1점
  • 인문대학 국어국문학과: 최종합격자 평균 372.8점

예시 2: "23231로 어디 갈 수 있어?" (정시)
【학생 성적 정규화】
- 국어: 2등급, 수학: 3등급, 영어: 2등급, 탐구1: 3등급, 탐구2: 1등급

【5개 대학 환산 점수】
- 경희대 인문: 420.5점 / 600점
- 서울대 일반전형: 360.2점
- 연세대 인문: 720.3점 / 1000점
- 고려대 인문: 650.1점 / 1000점
- 서강대 인문: 480.5점 (B형)

【2025학년도 정시 전형결과 비교】
- 경희대 (학생: 420.5점):
  • 경영대학 경영학과: 최종합격자 평균 415.2점
  • 인문대학 국어국문학과: 최종합격자 평균 410.8점
- 서울대 (학생: 360.2점):
  • 인문대학 국어국문학과: 최종합격자 평균 355.1점
- 연세대 (학생: 720.3점):
  • 문과대학 국어국문학과: 최종합격자 평균 715.2점

## 중요 지침 (반드시 준수)
- **반드시 3개 섹션 모두 포함**: 【학생 성적 정규화】, 【대학별 환산 점수】, 【2025학년도 전형결과 비교】
- 환산 점수를 먼저 명확히 제시하세요
- 전형결과 데이터에서 실제 점수와 비교하세요
- 구체적인 학과명과 점수를 제시하세요
- 판단이나 평가는 하지 말고 사실만 나열하세요
- 전형결과 데이터가 없으면 "전형결과 데이터 없음"이라고만 표시하세요
- 출처 표시는 생략하세요 (citation 비활성화)"""

        # 최종 프롬프트 구성
        final_prompt = f"{system_prompt}\n\n질문: {query}\n\n위 예시 형식을 정확히 따라서 답변하세요. 반드시 다음 3가지 섹션을 모두 포함해야 합니다:\n1. 【학생 성적 정규화】\n2. 【대학별 환산 점수】\n3. 【2025학년도 전형결과 비교】"
        
        _log(f"   📏 최종 프롬프트 길이: {len(final_prompt)}자")
        
        # 프롬프트가 너무 길면 경고
        if len(final_prompt) > 30000:
            _log(f"   ⚠️ 프롬프트가 매우 깁니다 ({len(final_prompt)}자). Gemini가 처리하지 못할 수 있습니다.")
        
        try:
            response = self.model.generate_content(
                final_prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 20000},
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

            # finish_reason 확인 (디버깅)
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, 'finish_reason', None)
                safety_ratings = getattr(candidate, 'safety_ratings', [])
                _log(f"   🔍 finish_reason: {finish_reason}")
                _log(f"   🔍 safety_ratings: {safety_ratings}")
                
                if finish_reason and finish_reason != 1:  # 1 = STOP (정상 종료)
                    _log(f"   ⚠️ 비정상 종료 감지: finish_reason={finish_reason}")
                    if 'SAFETY' in str(finish_reason):
                        _log(f"   ⚠️ 안전 필터링으로 차단됨")
                    if 'MAX_TOKENS' in str(finish_reason):
                        _log(f"   ⚠️ 최대 토큰 수 도달 (하지만 39토큰만 생성됨 - 이상함)")

            result_text = response.text
            
            # 응답 길이 확인
            _log(f"   📝 응답 텍스트 길이: {len(result_text)}자")
            if len(result_text) < 100:
                _log(f"   ⚠️ 응답이 너무 짧습니다! 실제 내용: {result_text[:200]}")
            
            # citations 구성 - Final Agent로 전달하지 않음 (비활성화)
            # citations는 Final Agent에서 사용하지 않으므로 아예 전달하지 않음

            _log(f"   분석 완료")
            _log("="*60)

            # sources 목록 구성
            sources = []
            if admission_results and admission_results.get("sources"):
                sources.extend(admission_results["sources"])
            if normalized_scores and normalized_scores.get("과목별_성적"):
                sources.append("표준점수·백분위 산출 방식")
            
            return {
                "agent": self.name,
                "status": "success",
                "query": query,
                "result": result_text,
                "grade_info": raw_grade_info,
                "normalized_scores": normalized_scores,  # 정규화된 성적 추가
                "sources": sources,
                "source_urls": []
                # citations는 Final Agent로 전달하지 않음 (비활성화)
            }

        except Exception as e:
            _log(f"   ❌ 컨설팅 Agent 오류: {e}")
            return {
                "agent": self.name,
                "status": "error",
                "result": str(e),
                "grade_info": raw_grade_info,
                "normalized_scores": normalized_scores,
                "sources": [],
                "source_urls": [],
                "citations": []
            }

    def _extract_grade_from_query(self, query: str) -> Dict[str, Any]:
        """
        쿼리에서 성적 정보 추출
        
        지원 형식:
        - "등급 132" -> 국어 1등급, 영어 3등급, 수학 2등급
        - "국어 90점 수학 미적분 85점"
        - "국어 1등급 수학 표준점수 130"
        - "국어 언어와매체 92점"
        """
        result = {
            "raw_input": query,
            "subjects": {},
            "내신": None,
            "선택과목_추론": {}
        }

        # 1. "등급 XXX" 패턴 처리 (예: "등급 132", "13425", "나 13425야")
        # 숫자만 3~5자리인 패턴 찾기
        compact_pattern = r'등급\s*(\d{3,5})|(\d{3,5})\s*등급|(?:나|저)\s*(\d{3,5})|(\d{3,5})(?:야|이야|입니다|요)'
        match = re.search(compact_pattern, query)
        if match:
            grade_str = match.group(1) or match.group(2) or match.group(3) or match.group(4)
            if grade_str and len(grade_str) >= 3:
                # 국/수/영 또는 국/수/영/탐1/탐2
                subjects_order = ["국어", "수학", "영어", "탐구1", "탐구2"]
                for i, char in enumerate(grade_str):
                    if i < len(subjects_order):
                        result["subjects"][subjects_order[i]] = {
                            "type": "등급",
                            "value": int(char)
                        }
        
        # 숫자만 있는 경우도 처리 (예: 메시지에서 "13425" 같은 숫자만)
        # 단, 표준점수/백분위 키워드가 없는 경우에만
        if not result["subjects"] and "표준점수" not in query and "백분위" not in query and "점" not in query:
            standalone_pattern = r'\b(\d{3,5})\b'
            matches = re.findall(standalone_pattern, query)
            for grade_str in matches:
                # 연도가 아닌지 확인 (2024, 2025, 2026 등)
                # 그리고 100 이상인 숫자는 표준점수일 가능성이 높으므로 제외
                if not (2020 <= int(grade_str) <= 2030) and int(grade_str) < 100:
                    subjects_order = ["국어", "수학", "영어", "탐구1", "탐구2"]
                    for i, char in enumerate(grade_str):
                        if i < len(subjects_order):
                            result["subjects"][subjects_order[i]] = {
                                "type": "등급",
                                "value": int(char)
                            }
                    break

        # 2. 과목별 성적 추출
        subject_keywords = {
            "국어": ["국어", "국"],
            "수학": ["수학", "수"],
            "영어": ["영어", "영"],
            "한국사": ["한국사", "한사"],
            "탐구1": ["탐구1"],
            "탐구2": ["탐구2"],
            # 탐구 과목
            "사회문화": ["사회문화", "사문"],
            "생활과윤리": ["생활과윤리", "생윤"],
            "윤리와사상": ["윤리와사상", "윤사"],
            "한국지리": ["한국지리", "한지"],
            "세계지리": ["세계지리", "세지"],
            "동아시아사": ["동아시아사", "동아시아"],
            "세계사": ["세계사"],
            "정치와법": ["정치와법", "정법"],
            "경제": ["경제"],
            "물리학1": ["물리학1", "물리1", "물1"],
            "물리학2": ["물리학2", "물리2", "물2"],
            "화학1": ["화학1", "화1"],
            "화학2": ["화학2", "화2"],
            "생명과학1": ["생명과학1", "생명1", "생1"],
            "생명과학2": ["생명과학2", "생명2", "생2"],
            "지구과학1": ["지구과학1", "지구1", "지1"],
            "지구과학2": ["지구과학2", "지구2", "지2"],
        }

        # 선택과목 키워드
        elective_keywords = {
            "화법과작문": ["화법과작문", "화작"],
            "언어와매체": ["언어와매체", "언매"],
            "확률과통계": ["확률과통계", "확통"],
            "미적분": ["미적분", "미적"],
            "기하": ["기하"],
        }

        # 선택과목 추출
        detected_electives = {}
        for elective, keywords in elective_keywords.items():
            for kw in keywords:
                if kw in query:
                    if elective in ["화법과작문", "언어와매체"]:
                        detected_electives["국어"] = elective
                    else:
                        detected_electives["수학"] = elective
                    break
        
        result["선택과목_추론"] = detected_electives

        # 각 과목별 점수 추출
        for subject, keywords in subject_keywords.items():
            if subject in result["subjects"]:
                continue  # 이미 추출된 과목은 스킵
                
            for kw in keywords:
                # 등급 패턴 (먼저 체크)
                grade_pattern = rf'{kw}\s*(\d)\s*등급|{kw}\s*등급\s*(\d)'
                match = re.search(grade_pattern, query)
                if match and subject not in result["subjects"]:
                    grade = match.group(1) or match.group(2)
                    result["subjects"][subject] = {
                        "type": "등급",
                        "value": int(grade)
                    }
                    break
                
                # 표준점수 패턴 (표준점수, 표점 명시)
                std_pattern = rf'{kw}\s*(?:표준점수|표점)\s*(\d{{2,3}})'
                match = re.search(std_pattern, query)
                if match and subject not in result["subjects"]:
                    value = int(match.group(1))
                    result["subjects"][subject] = {"type": "표준점수", "value": value}
                    break
                
                # 백분위 패턴
                pct_pattern = rf'{kw}\s*백분위\s*(\d{{1,3}})'
                match = re.search(pct_pattern, query)
                if match and subject not in result["subjects"]:
                    result["subjects"][subject] = {
                        "type": "백분위",
                        "value": int(match.group(1))
                    }
                    break
                
                # 원점수 패턴 (XX점)
                raw_pattern = rf'{kw}\s+(?:\w+\s+)?(\d{{2,3}})\s*점'
                match = re.search(raw_pattern, query)
                if match and subject not in result["subjects"]:
                    value = int(match.group(1))
                    result["subjects"][subject] = {"type": "원점수", "value": value}
                    break
                
                # ✅ 새로 추가: "국어 138" 같은 패턴 (점/표준점수 없이 숫자만)
                # 100 이상이면 표준점수로 간주
                simple_pattern = rf'{kw}\s+(\d{{2,3}})(?:\s|,|$)'
                match = re.search(simple_pattern, query)
                if match and subject not in result["subjects"]:
                    value = int(match.group(1))
                    if value >= 100:  # 표준점수로 간주
                        result["subjects"][subject] = {"type": "표준점수", "value": value}
                    elif value <= 9:  # 등급으로 간주
                        result["subjects"][subject] = {"type": "등급", "value": value}
                    else:  # 10-99: 백분위로 간주
                        result["subjects"][subject] = {"type": "백분위", "value": value}
                    break

        # 3. "탐구 X등급" 패턴 추가 처리 (탐구1, 탐구2가 아직 추출되지 않은 경우)
        if "탐구1" not in result["subjects"] or "탐구2" not in result["subjects"]:
            # "탐구" 키워드 뒤에 등급이 오는 패턴을 모두 찾기
            inquiry_pattern = r'탐구\s*(\d)\s*등급|탐구\s*등급\s*(\d)'
            inquiry_matches = re.finditer(inquiry_pattern, query)
            
            inquiry_grades = []
            for match in inquiry_matches:
                grade_val = match.group(1) or match.group(2)
                inquiry_grades.append(int(grade_val))
            
            # 발견된 탐구 등급을 순서대로 탐구1, 탐구2에 할당
            if len(inquiry_grades) >= 1 and "탐구1" not in result["subjects"]:
                result["subjects"]["탐구1"] = {
                    "type": "등급",
                    "value": inquiry_grades[0]
                }
            if len(inquiry_grades) >= 2 and "탐구2" not in result["subjects"]:
                result["subjects"]["탐구2"] = {
                    "type": "등급",
                    "value": inquiry_grades[1]
                }
        
        # ✅ 새로 추가: "탐구 60/60", "탐구 70 65" 같은 패턴 처리
        if "탐구1" not in result["subjects"] or "탐구2" not in result["subjects"]:
            # 탐구 뒤에 숫자 두 개 (슬래시나 공백으로 구분)
            inquiry_dual_pattern = r'탐구\s*(\d{1,3})\s*[/,\s]\s*(\d{1,3})'
            match = re.search(inquiry_dual_pattern, query)
            if match:
                val1, val2 = int(match.group(1)), int(match.group(2))
                
                # 값의 크기에 따라 표준점수/백분위/등급 구분
                def infer_type(v):
                    if v >= 100:
                        return "표준점수"
                    elif v >= 50:  # 50-99는 표준점수일 가능성 높음 (탐구)
                        return "표준점수"
                    elif v <= 9:
                        return "등급"
                    else:  # 10-49는 백분위로 추정
                        return "백분위"
                
                if "탐구1" not in result["subjects"]:
                    result["subjects"]["탐구1"] = {"type": infer_type(val1), "value": val1}
                if "탐구2" not in result["subjects"]:
                    result["subjects"]["탐구2"] = {"type": infer_type(val2), "value": val2}
        
        # ✅ 새로 추가: "탐구1 60, 탐구2 60" 패턴
        if "탐구1" not in result["subjects"]:
            match = re.search(r'탐구1\s*(\d{1,3})', query)
            if match:
                val = int(match.group(1))
                result["subjects"]["탐구1"] = {
                    "type": "표준점수" if val >= 50 else ("등급" if val <= 9 else "백분위"),
                    "value": val
                }
        if "탐구2" not in result["subjects"]:
            match = re.search(r'탐구2\s*(\d{1,3})', query)
            if match:
                val = int(match.group(1))
                result["subjects"]["탐구2"] = {
                    "type": "표준점수" if val >= 50 else ("등급" if val <= 9 else "백분위"),
                    "value": val
                }

        # 4. 내신 등급 추출
        grade_pattern = r'내신\s*(\d+\.?\d*)\s*등급?|(\d+\.?\d*)\s*등급\s*내신'
        match = re.search(grade_pattern, query)
        if match:
            grade = match.group(1) or match.group(2)
            result["내신"] = float(grade)

        # 5. 선택과목 기본값 추론
        if "국어" not in result.get("선택과목_추론", {}):
            result["선택과목_추론"]["국어"] = "화법과작문"  # 기본값
        if "수학" not in result.get("선택과목_추론", {}):
            result["선택과목_추론"]["수학"] = "확률과통계"  # 기본값
        
        # 수학 선택과목에 따른 탐구 추론
        math_elective = result["선택과목_추론"].get("수학", "확률과통계")
        if math_elective == "확률과통계":
            result["선택과목_추론"]["탐구_추론"] = "인문계 (사회문화/생활과윤리)"
        else:
            result["선택과목_추론"]["탐구_추론"] = "자연계 (지구과학1/생명과학1)"

        return result
    
    def _normalize_scores(self, raw_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        추출된 성적을 등급-표준점수-백분위로 정규화
        
        Args:
            raw_info: _extract_grade_from_query에서 추출한 정보
            
        Returns:
            정규화된 성적 정보
        """
        normalized = {
            "과목별_성적": {},
            "추정_과목": [],
            "선택과목": raw_info.get("선택과목_추론", {})
        }
        
        subjects_data = raw_info.get("subjects", {})
        electives = raw_info.get("선택과목_추론", {})
        
        for subject, score_info in subjects_data.items():
            score_type = score_info.get("type")
            value = score_info.get("value")
            
            converted = None
            
            try:
                if subject in ["국어", "수학"]:
                    elective = electives.get(subject)
                    
                    if score_type == "등급":
                        # 등급 -> 해당 등급 중간 백분위의 표준점수 사용
                        converted = self._convert_grade_to_scores(subject, value)
                    elif score_type == "표준점수":
                        converted = self.score_converter.convert_score(subject, standard_score=value)
                        if converted:
                            _log(f"   {subject} 표준점수 {value} -> 등급 {converted.get('grade')}, 백분위 {converted.get('percentile')}")
                    elif score_type == "백분위":
                        converted = self.score_converter.convert_score(subject, percentile=value)
                    elif score_type == "원점수" and elective:
                        converted = self.score_converter.convert_score(
                            subject, raw_score=value, elective=elective
                        )
                        if converted:
                            _log(f"   {subject}({elective}) 원점수 {value} -> 표준점수 {converted.get('standard_score')}, 등급 {converted.get('grade')}")
                
                elif subject == "영어":
                    # 영어는 절대평가
                    if score_type == "등급":
                        grade_data = english_grade_data.get(value, {})
                        converted = {
                            "standard_score": None,
                            "percentile": 100 - grade_data.get("ratio", 50),
                            "grade": value
                        }
                    elif score_type == "원점수":
                        # 원점수 -> 등급 변환
                        for grade, data in english_grade_data.items():
                            if value >= data.get("raw_cut", 0):
                                converted = {
                                    "standard_score": None,
                                    "percentile": 100 - data.get("ratio", 50),
                                    "grade": grade
                                }
                                break
                
                elif subject in self.score_converter.social_data:
                    if score_type == "등급":
                        converted = self._convert_grade_to_scores(subject, value)
                    elif score_type == "표준점수":
                        converted = self.score_converter.convert_score(subject, standard_score=value)
                    elif score_type == "백분위":
                        converted = self.score_converter.convert_score(subject, percentile=value)
                
                elif subject in self.score_converter.science_data:
                    if score_type == "등급":
                        converted = self._convert_grade_to_scores(subject, value)
                    elif score_type == "표준점수":
                        converted = self.score_converter.convert_score(subject, standard_score=value)
                    elif score_type == "백분위":
                        converted = self.score_converter.convert_score(subject, percentile=value)
                
                elif subject in ["탐구1", "탐구2"]:
                    # 탐구 과목이 특정되지 않은 경우
                    if score_type == "등급":
                        converted = self._convert_grade_to_scores("탐구_기본", value)
                    elif score_type == "표준점수":
                        # 탐구 표준점수 -> 백분위 추정 (사회탐구/과학탐구 평균 기준)
                        # 탐구 표준점수 범위: 약 20~70, 만점 70 기준
                        # 표준점수가 높을수록 높은 백분위
                        if value >= 70:
                            pct = 99
                        elif value >= 67:
                            pct = 97
                        elif value >= 65:
                            pct = 95
                        elif value >= 63:
                            pct = 92
                        elif value >= 60:
                            pct = 88
                        elif value >= 58:
                            pct = 84
                        elif value >= 55:
                            pct = 78
                        elif value >= 52:
                            pct = 70
                        elif value >= 50:
                            pct = 62
                        elif value >= 47:
                            pct = 52
                        elif value >= 44:
                            pct = 40
                        elif value >= 40:
                            pct = 28
                        else:
                            pct = 15
                        
                        converted = {
                            "grade": 1 if pct >= 96 else (2 if pct >= 89 else (3 if pct >= 77 else 4)),
                            "standard_score": value,
                            "percentile": pct
                        }
                        _log(f"   {subject} 표준점수 {value} -> 백분위 {pct} (추정)")
                    elif score_type == "백분위":
                        # 백분위 -> 표준점수 추정
                        if value >= 99:
                            std = 70
                        elif value >= 95:
                            std = 65
                        elif value >= 90:
                            std = 62
                        elif value >= 85:
                            std = 59
                        elif value >= 80:
                            std = 57
                        elif value >= 70:
                            std = 53
                        elif value >= 60:
                            std = 50
                        else:
                            std = 45
                        
                        converted = {
                            "grade": 1 if value >= 96 else (2 if value >= 89 else (3 if value >= 77 else 4)),
                            "standard_score": std,
                            "percentile": value
                        }
                        _log(f"   {subject} 백분위 {value} -> 표준점수 {std} (추정)")
                
            except Exception as e:
                _log(f"   ⚠️ {subject} 변환 오류: {e}")
                converted = None
            
            if converted:
                normalized["과목별_성적"][subject] = {
                    "원본_입력": score_info,
                    "등급": converted.get("grade"),
                    "표준점수": converted.get("standard_score"),
                    "백분위": converted.get("percentile"),
                    "선택과목": electives.get(subject) if subject in ["국어", "수학"] else None
                }
            else:
                # 변환 실패 시 원본 저장
                normalized["과목별_성적"][subject] = {
                    "원본_입력": score_info,
                    "등급": value if score_type == "등급" else None,
                    "표준점수": value if score_type == "표준점수" else None,
                    "백분위": value if score_type == "백분위" else None,
                    "변환_실패": True
                }
        
        # 미입력 과목 추정 (다른 과목들의 평균 백분위 기준)
        normalized = self._estimate_missing_subjects(normalized)
        
        return normalized
    
    def _convert_grade_to_scores(self, subject: str, grade: int) -> Dict[str, Any]:
        """
        등급을 표준점수/백분위로 변환 (보수적 접근 - 해당 등급 중간값 사용)
        
        등급별 백분위 기준:
        - 1등급: 96~100% -> 중간 98%
        - 2등급: 89~96% -> 중간 92.5%
        - 3등급: 77~89% -> 중간 83%
        - 4등급: 60~77% -> 중간 68.5%
        - 5등급: 40~60% -> 중간 50%
        - 6등급: 23~40% -> 중간 31.5%
        - 7등급: 11~23% -> 중간 17%
        - 8등급: 4~11% -> 중간 7.5%
        - 9등급: 0~4% -> 중간 2%
        """
        grade_to_mid_percentile = {
            1: 98,
            2: 92,
            3: 83,
            4: 68,
            5: 50,
            6: 31,
            7: 17,
            8: 7,
            9: 2
        }
        
        mid_percentile = grade_to_mid_percentile.get(grade, 50)
        
        # 해당 백분위에서 가장 가까운 표준점수 찾기
        result = self.score_converter.find_closest_by_percentile(subject, mid_percentile)
        
        if result:
            result["grade"] = grade  # 원래 등급 유지
            return result
        
        # 탐구 기본값
        if subject == "탐구_기본":
            # 사회탐구 기본값 (사회문화 기준)
            std_estimate = 50 + (mid_percentile - 50) * 0.2  # 대략적 추정
            return {
                "grade": grade,
                "standard_score": round(std_estimate),
                "percentile": mid_percentile
            }
        
        return {
            "grade": grade,
            "standard_score": None,
            "percentile": mid_percentile
        }
    
    def _estimate_missing_subjects(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        """
        미입력 과목을 다른 과목들의 평균 백분위로 추정
        """
        subjects = normalized.get("과목별_성적", {})
        
        # 입력된 과목들의 평균 백분위 계산
        percentiles = []
        for subj, data in subjects.items():
            pct = data.get("백분위")
            if pct is not None:
                percentiles.append(pct)
        
        if not percentiles:
            return normalized
        
        avg_percentile = sum(percentiles) / len(percentiles)
        
        # 필수 과목 확인
        required = ["국어", "수학", "영어"]
        for subj in required:
            if subj not in subjects:
                # 평균 백분위로 추정
                if subj in ["국어", "수학"]:
                    estimated = self.score_converter.find_closest_by_percentile(subj, int(avg_percentile))
                    if estimated:
                        normalized["과목별_성적"][subj] = {
                            "원본_입력": None,
                            "등급": estimated.get("grade"),
                            "표준점수": estimated.get("standard_score"),
                            "백분위": estimated.get("percentile"),
                            "추정됨": True
                        }
                        normalized["추정_과목"].append(subj)
                elif subj == "영어":
                    # 영어 등급 추정
                    if avg_percentile >= 97:
                        est_grade = 1
                    elif avg_percentile >= 83:
                        est_grade = 2
                    elif avg_percentile >= 56:
                        est_grade = 3
                    elif avg_percentile >= 32:
                        est_grade = 4
                    else:
                        est_grade = 5
                    
                    normalized["과목별_성적"][subj] = {
                        "원본_입력": None,
                        "등급": est_grade,
                        "표준점수": None,
                        "백분위": avg_percentile,
                        "추정됨": True
                    }
                    normalized["추정_과목"].append(subj)
        
        return normalized
    
    def _calculate_average_percentile(self, normalized: Dict[str, Any]) -> float:
        """정규화된 성적에서 평균 백분위 계산"""
        subjects = normalized.get("과목별_성적", {})
        
        percentiles = []
        for subj, data in subjects.items():
            pct = data.get("백분위")
            if pct is not None:
                percentiles.append(pct)
        
        if not percentiles:
            return None
        
        return sum(percentiles) / len(percentiles)
    
    def _format_normalized_scores(self, normalized: Dict[str, Any]) -> str:
        """정규화된 성적을 텍스트로 포맷팅"""
        lines = []
        
        subjects = normalized.get("과목별_성적", {})
        electives = normalized.get("선택과목", {})
        estimated = normalized.get("추정_과목", [])
        
        for subj, data in subjects.items():
            grade = data.get("등급")
            std = data.get("표준점수")
            pct = data.get("백분위")
            elective = data.get("선택과목") or electives.get(subj)
            is_estimated = data.get("추정됨", False) or subj in estimated
            
            # 과목명 포맷
            if elective:
                subj_name = f"{subj}({elective})"
            else:
                subj_name = subj
            
            # 점수 포맷
            parts = []
            if grade is not None:
                parts.append(f"{grade}등급")
            if std is not None:
                parts.append(f"표준점수 {std}")
            elif subj == "영어":
                parts.append("표준점수 없음(절대평가)")
            if pct is not None:
                parts.append(f"백분위 {round(pct, 1)}")
            
            score_text = " / ".join(parts) if parts else "정보 없음"
            
            if is_estimated:
                score_text += " (추정)"
            
            lines.append(f"- {subj_name}: {score_text}")
        
        if not lines:
            return "성적 정보가 입력되지 않았습니다."
        
        return "\n".join(lines)
    
    def _format_khu_scores(self, khu_scores: Dict[str, Any]) -> str:
        """경희대 환산 점수를 텍스트로 포맷팅"""
        lines = []
        
        for track in ["인문", "사회", "자연", "예술체육"]:
            score_data = khu_scores.get(track, {})
            
            if not score_data.get("계산_가능"):
                lines.append(f"- {track}: 계산 불가 ({score_data.get('오류', '데이터 부족')})")
                continue
            
            final_score = score_data.get("최종점수", 0)
            base_score = score_data.get("기본점수_600", 0)
            eng_ded = score_data.get("영어_감점", 0)
            hist_ded = score_data.get("한국사_감점", 0)
            bonus = score_data.get("과탐_가산점", 0)
            
            score_info = f"{final_score:.1f}점"
            
            # 세부 정보 추가
            details = []
            if bonus > 0:
                details.append(f"과탐가산 +{bonus}점")
            if eng_ded != 0:
                details.append(f"영어 {eng_ded:+.1f}점")
            if hist_ded != 0:
                details.append(f"한국사 {hist_ded:+.1f}점")
            
            if details:
                score_info += f" ({', '.join(details)})"
            
            lines.append(f"- {track}: {score_info}")
        
        if not lines:
            return "경희대 환산 점수 계산 불가"
        
        result = "\n".join(lines)
        result += "\n[출처: 경희대 2026 모집요강]"
        
        return result
    
    def _format_snu_scores(self, snu_scores: Dict[str, Any]) -> str:
        """서울대 환산 점수를 텍스트로 포맷팅"""
        lines = []
        
        # 주요 모집단위만 표시 (일반/순수미술/디자인/체육)
        main_tracks = ["일반전형", "순수미술", "디자인", "체육교육"]
        music_tracks = ["성악", "작곡", "음악학"]
        
        # 1. 주요 모집단위
        for track in main_tracks:
            score_data = snu_scores.get(track, {})
            
            if not score_data.get("계산_가능"):
                lines.append(f"- {score_data.get('모집단위', track)}: 계산 불가")
                continue
            
            final_score = score_data.get("최종점수", 0)
            final_1000 = score_data.get("최종점수_1000", final_score)
            bonus = score_data.get("과탐_가산점", 0)
            
            # 감점 정보
            math_ded = score_data.get("수학_감점", 0)
            eng_ded = score_data.get("영어_감점", 0)
            hist_ded = score_data.get("한국사_감점", 0)
            total_ded = math_ded + eng_ded + hist_ded
            
            score_info = f"{final_score:.1f}점 (1000점: {final_1000:.1f})"
            
            details = []
            if bonus > 0:
                details.append(f"과탐가산 +{bonus}점")
            if total_ded < -0.1:
                details.append(f"감점 {total_ded:.1f}점")
            
            if details:
                score_info += f" ({', '.join(details)})"
            
            track_name = track if track == "일반전형" else score_data.get('모집단위', track).replace("사범대학 ", "").replace("미술대학 - ", "")
            lines.append(f"- {track_name}: {score_info}")
        
        # 2. 음악대학 (특수 환산)
        music_line_parts = []
        for track in music_tracks:
            score_data = snu_scores.get(track, {})
            if score_data.get("계산_가능"):
                final_score = score_data.get("최종점수", 0)
                final_1000 = score_data.get("최종점수_1000", final_score)
                track_short = track
                music_line_parts.append(f"{track_short} {final_1000:.1f}점")
        
        if music_line_parts:
            lines.append(f"- 음악대학: {', '.join(music_line_parts)}")
        
        if not lines:
            return "서울대 환산 점수 계산 불가"
        
        result = "\n".join(lines)
        result += "\n[출처: 서울대 2026 모집요강]"
        
        return result
    
    def _format_yonsei_scores(self, yonsei_scores: Dict[str, Any]) -> str:
        """연세대 환산 점수를 텍스트로 포맷팅"""
        lines = []
        
        main_tracks = ["인문", "자연", "의약", "통합"]
        for track in main_tracks:
            score_data = yonsei_scores.get(track, {})
            
            if not score_data.get("계산_가능"):
                continue
            
            final_score = score_data.get("최종점수", 0)
            bonus = score_data.get("탐구_가산")
            
            score_info = f"{final_score:.1f}점"
            if bonus:
                score_info += f" ({bonus})"
            
            lines.append(f"- {track}: {score_info}")
        
        if not lines:
            return "연세대 환산 점수 계산 불가"
        
        result = "\n".join(lines)
        result += "\n[출처: 연세대 2026 모집요강]"
        
        return result
    
    def _format_korea_scores(self, korea_scores: Dict[str, Any]) -> str:
        """고려대 환산 점수를 텍스트로 포맷팅"""
        lines = []
        
        for track in ["인문", "자연"]:
            score_data = korea_scores.get(track, {})
            
            if not score_data.get("계산_가능"):
                continue
            
            final_score = score_data.get("최종점수", 0)
            raw_score = score_data.get("원점수", 0)
            eng_ded = score_data.get("영어_감점", 0)
            
            score_info = f"{final_score:.1f}점"
            if eng_ded < 0:
                score_info += f" (영어 {eng_ded:.0f}점)"
            
            lines.append(f"- {track}: {score_info}")
        
        if not lines:
            return "고려대 환산 점수 계산 불가"
        
        result = "\n".join(lines)
        result += "\n[출처: 고려대 2026 모집요강]"
        
        return result
    
    def _format_sogang_scores(self, sogang_scores: Dict[str, Any]) -> str:
        """서강대 환산 점수를 텍스트로 포맷팅"""
        lines = []
        
        for track in ["인문", "자연", "자유전공"]:
            score_data = sogang_scores.get(track, {})
            
            if not score_data.get("계산_가능"):
                continue
            
            final_score = score_data.get("최종점수", 0)
            method = score_data.get("적용방식", "")
            
            method_short = ""
            if "A형" in method:
                method_short = "수학가중"
            elif "B형" in method:
                method_short = "국어가중"
            
            score_info = f"{final_score:.1f}점"
            if method_short:
                score_info += f" ({method_short})"
            
            lines.append(f"- {track}: {score_info}")
        
        if not lines:
            return "서강대 환산 점수 계산 불가"
        
        result = "\n".join(lines)
        result += "\n[출처: 서강대 2026 모집요강]"
        
        return result
    
    def _analyze_query(self, query: str) -> Dict[str, Any]:
        """
        질의 분석: 정시/수시 구분 및 대학명 추출
        
        Returns:
            {
                "admission_type": "정시" | "수시" | "both" | None,
                "universities": ["서울대", "경희대", ...],
                "campus": {"경희대": "서울캠" | "용인캠" | None, ...},
                "year": "2025" | None
            }
        """
        result = {
            "admission_type": None,
            "universities": [],
            "campus": {},
            "year": None
        }
        
        query_lower = query.lower()
        
        # 연도 추출
        year_match = re.search(r'(2024|2025|2026|2027|2028)', query)
        if year_match:
            result["year"] = year_match.group(1)
        
        # 정시/수시 구분
        if any(word in query for word in ['정시', '정시모집', '정시전형']):
            result["admission_type"] = "정시"
        elif any(word in query for word in ['수시', '수시모집', '수시전형']):
            result["admission_type"] = "수시"
        elif any(word in query for word in ['등급', '커트', '입결', '합격', '갈 수', '갈수', '가능']):
            # 등급 관련 질문은 정시일 가능성이 높음
            result["admission_type"] = "정시"
        else:
            result["admission_type"] = "both"  # 명시되지 않으면 둘 다
        
        # 대학명 추출
        universities = ["서울대", "연세대", "고려대", "성균관대", "경희대", "서강대", 
                       "한양대", "중앙대", "이화여대", "건국대", "동국대", "홍익대"]
        
        for univ in universities:
            if univ in query:
                result["universities"].append(univ)
                
                # 경희대 캠퍼스 구분
                if univ == "경희대":
                    if any(word in query for word in ['용인', '용인캠', '국제캠']):
                        result["campus"][univ] = "용인캠"
                    elif any(word in query for word in ['서울', '서울캠']):
                        result["campus"][univ] = "서울캠"
                    else:
                        result["campus"][univ] = None  # 명시 안되면 둘 다
        
        # 대학명이 없으면 주요 대학 모두 검색
        if not result["universities"]:
            result["universities"] = ["서울대", "연세대", "고려대", "서강대", "경희대"]
        
        return result
    
    async def _fetch_admission_results_from_supabase(
        self, 
        query_analysis: Dict[str, Any],
        normalized_scores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Supabase에서 전형결과 문서 조회
        
        Args:
            query_analysis: _analyze_query 결과
            normalized_scores: 정규화된 성적
            
        Returns:
            {
                "수시": {...},
                "정시": {...},
                "sources": [...],
                "citations": [...]
            }
        """
        try:
            client = supabase_service.get_client()
            
            # documents_metadata에서 전형결과 문서 조회
            metadata_response = client.table('documents_metadata').select('*').execute()
            
            if not metadata_response.data:
                return {
                    "수시": {},
                    "정시": {},
                    "sources": [],
                    "citations": []
                }
            
            admission_type = query_analysis.get("admission_type", "both")
            universities = query_analysis.get("universities", [])
            year = query_analysis.get("year", "2025")
            campus_info = query_analysis.get("campus", {})
            
            # 디버깅: 전체 문서 수 확인
            _log(f"   전체 문서 수: {len(metadata_response.data)}개")
            
            # 디버깅: 전형결과 관련 문서 샘플 확인
            sample_docs = []
            for doc in metadata_response.data[:5]:  # 처음 5개만
                docu_cat = doc.get('docu_cat', '') or ''
                title = doc.get('title', '') or ''
                hashtags = doc.get('hashtags', []) or []
                sample_docs.append({
                    "title": title[:50],
                    "docu_cat": docu_cat[:50] if docu_cat else "(없음)",
                    "hashtags": hashtags[:3] if hashtags else []
                })
            _log(f"   문서 샘플 (처음 5개): {json.dumps(sample_docs, ensure_ascii=False, indent=2)}")
            
            # 전형결과 문서 필터링
            # 정시일 경우: 5개 대학만 (경희대학교, 고려대학교, 서울대학교, 연세대학교, 서강대학교)
            # 수시일 경우: 모든 대학
            target_universities = {
                "경희대학교": "경희대",
                "고려대학교": "고려대",
                "서울대학교": "서울대",
                "연세대학교": "연세대",
                "서강대학교": "서강대"
            }
            
            relevant_docs = []
            
            for doc in metadata_response.data:
                source = doc.get('source', '') or ''
                docu_cat = doc.get('docu_cat', '') or ''
                title = doc.get('title', '') or ''
                
                # 1단계: docu_cat이 "전형결과"로 끝나는지 확인
                docu_cat_ends_with = docu_cat.strip().endswith('전형결과')
                if not docu_cat_ends_with:
                    continue
                
                # 2단계: docu_cat에서 전형 유형(수시/정시) 추출
                doc_type = None
                if '수시' in docu_cat:
                    doc_type = '수시'
                elif '정시' in docu_cat:
                    doc_type = '정시'
                
                # 전형 유형을 찾지 못했으면 스킵
                if not doc_type:
                    _log(f"   ⚠️ 전형 유형을 찾을 수 없음: {docu_cat}")
                    continue
                
                # 3단계: 정시일 경우 source 칼럼으로 5개 대학만 필터링
                if doc_type == '정시':
                    if source not in target_universities:
                        continue  # 정시는 5개 대학만
                    doc_univ_normalized = target_universities[source]
                else:
                    # 수시일 경우: source에서 대학명 추출 (모든 대학 포함)
                    # source가 있으면 사용, 없으면 docu_cat에서 추출
                    if source and source in target_universities:
                        doc_univ_normalized = target_universities[source]
                    else:
                        # source가 없거나 매핑에 없으면 docu_cat에서 추출 시도
                        # 예: "2025년 한양대 수시 전형결과" -> 한양대
                        univ_match = re.search(r'([가-힣]+대(?:학교)?)', docu_cat)
                        if univ_match:
                            doc_univ_raw = univ_match.group(1)
                            doc_univ_normalized = doc_univ_raw.replace("대학교", "").replace("학교", "")
                        else:
                            # 대학명을 찾을 수 없으면 source 그대로 사용
                            doc_univ_normalized = source.replace("대학교", "").replace("학교", "") if source else "알수없음"
                
                _log(f"   ✓ 전형결과 문서 발견: {source} ({doc_type}) - {docu_cat[:60]}")
                
                # 4단계: 캠퍼스 정보 확인 (경희대 등)
                doc_campus = None
                if "용인" in docu_cat or "용인" in title or "국제캠" in docu_cat or "국제캠" in title:
                    doc_campus = "용인캠"
                elif "서울" in docu_cat or "서울" in title or "서울캠" in docu_cat or "서울캠" in title:
                    doc_campus = "서울캠"
                
                # 5단계: 질의 분석 결과와 비교
                # 대학명 매칭 (명시 안 되면 모든 대학 포함)
                matched = False
                if not universities:
                    matched = True  # 대학명이 명시되지 않았으면 모든 대학 포함
                else:
                    for req_univ in universities:
                        if req_univ == doc_univ_normalized or req_univ in doc_univ_normalized or doc_univ_normalized in req_univ:
                            matched = True
                            _log(f"   ✓ 대학명 매칭: {req_univ} <-> {doc_univ_normalized}")
                            break
                
                # 전형 유형 필터링
                if matched:
                    if admission_type == "both" or admission_type == doc_type:
                        # 캠퍼스 필터링 (경희대 등)
                        if doc_univ_normalized in campus_info:
                            required_campus = campus_info[doc_univ_normalized]
                            if required_campus is None or doc_campus == required_campus:
                                relevant_docs.append({
                                    "doc": doc,
                                    "university": doc_univ_normalized,
                                    "type": doc_type,
                                    "campus": doc_campus
                                })
                        else:
                            relevant_docs.append({
                                "doc": doc,
                                "university": doc_univ_normalized,
                                "type": doc_type,
                                "campus": doc_campus
                            })
            
            _log(f"   발견된 전형결과 문서: {len(relevant_docs)}개")
            
            # 디버깅: 매칭 실패 시 정보 출력
            if len(relevant_docs) == 0:
                _log(f"   ⚠️ 전형결과 문서를 찾지 못했습니다.")
                _log(f"   검색 조건: admission_type={admission_type}, universities={universities}, year={year}")
                # 전형결과 관련 키워드가 있는 문서 찾기
                potential_docs = []
                for doc in metadata_response.data:
                    docu_cat = doc.get('docu_cat', '') or ''
                    title = doc.get('title', '') or ''
                    search_text = (docu_cat + " " + title).lower()
                    if any(kw in search_text for kw in ['전형결과', '입결', '커트']):
                        potential_docs.append({
                            "title": title[:60],
                            "docu_cat": docu_cat[:60] if docu_cat else "(없음)"
                        })
                if potential_docs:
                    _log(f"   전형결과 관련 문서 후보 ({len(potential_docs)}개):")
                    for pd in potential_docs[:3]:  # 최대 3개만
                        _log(f"      - {pd['title']} (docu_cat: {pd['docu_cat']})")
            
            # 문서 내용 로드 및 정리
            admission_results = {
                "수시": {},
                "정시": {},
                "sources": [],
                "citations": []
            }
            
            for item in relevant_docs:
                doc = item["doc"]
                univ = item["university"]
                doc_type = item["type"]
                campus = item.get("campus")
                
                filename = doc['file_name']
                title = doc['title']
                file_url = doc.get('file_url') or ''
                docu_cat = doc.get('docu_cat', '') or ''
                
                # docu_cat에서 연도 추출 (없으면 기본값 사용)
                doc_year = year
                year_match = re.search(r'(\d{4})년', docu_cat or title)
                if year_match:
                    doc_year = year_match.group(1)
                
                # 출처 추가
                source_name = f"{doc_year}년 {univ}"
                if campus:
                    source_name += f" {campus}"
                source_name += f" {doc_type} 전형결과"
                
                admission_results["sources"].append(source_name)
                
                _log(f"   📄 {source_name}")
                
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
                    
                    # 청크 내용 합치기
                    full_content = ""
                    for chunk in sorted_chunks:
                        full_content += chunk['content'] + "\n\n"
                        
                        # citations 추가
                        chunk_info = {
                            "id": chunk.get('id'),
                            "content": chunk['content'],
                            "title": title,
                            "source": doc.get('source', ''),
                            "file_url": file_url,
                            "metadata": chunk.get('metadata', {})
                        }
                        admission_results["citations"].append({
                            "chunk": chunk_info,
                            "source": source_name,
                            "url": file_url
                        })
                    
                    # 대학별로 데이터 저장
                    univ_key = univ
                    if campus:
                        univ_key = f"{univ}_{campus}"
                    
                    if univ_key not in admission_results[doc_type]:
                        admission_results[doc_type][univ_key] = {
                            "university": univ,
                            "campus": campus,
                            "type": doc_type,
                            "content": full_content[:20000],  # 최대 20000자
                            "title": title,
                            "file_url": file_url
                        }
                    else:
                        # 이미 있으면 내용 추가
                        admission_results[doc_type][univ_key]["content"] += "\n\n" + full_content[:20000]
            
            return admission_results
            
        except Exception as e:
            _log(f"   ⚠️ Supabase 조회 오류: {e}")
            return {
                "수시": {},
                "정시": {},
                "sources": [],
                "citations": []
            }
    
    def _format_admission_results(self, admission_results: Dict[str, Any]) -> str:
        """전형결과 데이터를 텍스트로 포맷팅"""
        if not admission_results or not admission_results.get("sources"):
            return "전형결과 데이터가 없습니다."
        
        lines = []
        
        # 수시 데이터
        susi_data = admission_results.get("수시", {})
        if susi_data:
            lines.append("【수시 전형결과】")
            for univ_key, data in susi_data.items():
                univ = data.get("university", "")
                campus = data.get("campus", "")
                content = data.get("content", "")[:5000]  # 최대 5000자
                
                univ_name = univ
                if campus:
                    univ_name += f" {campus}"
                
                lines.append(f"\n{univ_name}:")
                lines.append(content[:5000])  # 내용 일부만 표시
                lines.append(f"[출처: {data.get('title', '')}]")
        
        # 정시 데이터
        jeongsi_data = admission_results.get("정시", {})
        if jeongsi_data:
            lines.append("\n【정시 전형결과】")
            for univ_key, data in jeongsi_data.items():
                univ = data.get("university", "")
                campus = data.get("campus", "")
                content = data.get("content", "")[:5000]  # 최대 5000자
                
                univ_name = univ
                if campus:
                    univ_name += f" {campus}"
                
                lines.append(f"\n{univ_name}:")
                lines.append(content[:5000])  # 내용 일부만 표시
                lines.append(f"[출처: {data.get('title', '')}]")
        
        if not lines:
            return "전형결과 데이터가 없습니다."
        
        return "\n".join(lines)


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