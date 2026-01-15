"""
AI 기반 문서 분류 서비스 (개선 버전)
"""
from services.gemini_service import gemini_service
from models.rag_models import ClassificationResult
from config.constants import CLASSIFICATION_SAMPLE_LENGTH, SUMMARY_MAX_LENGTH
from config.logging_config import classifier_logger as logger
import json


class ClassifierService:
    """Gemini를 사용한 문서 자동 분류"""

    def __init__(self):
        """초기화"""
        logger.info("ClassifierService 초기화 완료")
    
    async def classify_document(
        self,
        text: str,
        title: str
    ) -> ClassificationResult:
        """
        문서 내용을 읽고 자동 분류

        Args:
            text: 문서 내용
            title: 문서 제목

        Returns:
            분류 결과
        """
        logger.info(f"AI 문서 분류 시작 - 제목: {title}")

        # 샘플 추출
        sample = text[:CLASSIFICATION_SAMPLE_LENGTH]
        
        prompt = f"""다음 대학 입시 관련 문서를 읽고 정확히 분류해주세요.

**문서 제목:** {title}

**문서 내용 (앞부분):**
{sample}

---

**분류 기준:**
1. **policy**: 대학입학 전형 기본사항, 모집요강, 전형 방법, 수시/정시 안내 등
2. **admission_stats**: 입시 결과, 경쟁률, 합격선, 커트라인, 성적 통계 등
3. **university_info**: 대학 소개, 학과 정보, 캠퍼스 안내, 장학금 등

**응답 형식 (JSON):**
{{
  "category": "policy" 또는 "admission_stats" 또는 "university_info",
  "confidence": 0.0~1.0 사이 값,
  "reason": "분류 이유를 한 문장으로",
  "keywords": ["주요", "키워드", "5개"]
}}

JSON만 출력하세요."""

        try:
            # Gemini 호출
            response_text = await gemini_service.generate(
                prompt,
                "당신은 대학 입시 문서 분류 전문가입니다."
            )

            # JSON 추출
            result_text = response_text
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            # Pydantic 모델로 변환
            classification = ClassificationResult(
                category=result.get('category', 'policy'),
                confidence=float(result.get('confidence', 0.8)),
                reason=result.get('reason', '자동 분류됨'),
                keywords=result.get('keywords', [])[:10]
            )

            emoji = self._get_emoji(classification.category)
            category_name = self._get_category_name(classification.category)

            logger.info(f"분류 완료 - {emoji} {category_name} (신뢰도: {classification.confidence*100:.0f}%)")
            logger.info(f"이유: {classification.reason}")
            logger.info(f"키워드: {', '.join(classification.keywords[:5])}")

            return classification

        except Exception as e:
            logger.error(f"분류 오류: {e}")
            # 기본값 반환
            return ClassificationResult(
                category='policy',
                confidence=0.5,
                reason=f'자동 분류 실패: {str(e)}',
                keywords=[]
            )
    
    def _get_emoji(self, category: str) -> str:
        """카테고리별 이모지"""
        emojis = {
            'policy': '📋',
            'admission_stats': '📊',
            'university_info': '🏫'
        }
        return emojis.get(category, '📄')
    
    def _get_category_name(self, category: str) -> str:
        """카테고리 한글명"""
        names = {
            'policy': '정책/요강 문서',
            'admission_stats': '입시 결과 통계',
            'university_info': '대학 정보'
        }
        return names.get(category, '미분류')
    
    async def create_summary_and_extract_source(
        self, 
        text: str, 
        title: str, 
        max_length: int = None
    ) -> dict:
        """
        Gemini로 목차 형식 요약본 생성 + 출처 추출
        
        Args:
            text: 원본 문서 텍스트 (전체)
            title: 문서 제목
            max_length: 최대 길이 (None이면 기본값 사용)
        
        Returns:
            {"summary": str, "source": str}
        """
        if max_length is None:
            max_length = SUMMARY_MAX_LENGTH
        
        logger.info(f"요약 + 출처 추출 시작 - 제목: {title}")
        
        prompt = f"""다음 문서를 읽고 **요약**과 **출처**를 추출하세요.

**문서 제목:** {title}

**문서 내용:**
{text[:3000]}

---

**작업 1: 요약 ({max_length}자 이내)**
- 문서에 어떤 내용이 담겨있는지 목차 형식으로 요약
- 주요 주제, 전형명, 정책명 등 나열
- 불렛 포인트 사용

**작업 2: 출처 추출**
- 문서에 명시된 발행기관/단체 찾기
- 예: "한국대학교육협의회", "교육부", "서울대학교", "대입정보포털" 등
- 출처가 명확하지 않으면 "미상"

**응답 형식 (JSON):**
{{
  "summary": "요약 내용...",
  "source": "발행기관명"
}}

JSON만 출력하세요."""
        
        try:
            response_text = await gemini_service.generate(
                prompt,
                system_instruction="당신은 문서 요약 및 출처 추출 전문가입니다."
            )
            
            # JSON 추출
            result_text = response_text
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            summary = result.get('summary', f'본 문서는 {title}에 관한 자료입니다.')
            source = result.get('source', '미상')
            
            logger.info(f"요약 완료 ({len(summary)}자)")
            logger.info(f"추출된 출처: {source}")
            
            return {
                "summary": summary,
                "source": source
            }
        
        except Exception as e:
            logger.error(f"요약/출처 추출 실패: {e}")
            return {
                "summary": f"본 문서는 '{title}'에 관한 자료입니다.",
                "source": "미상"
            }
    
    async def create_summary(self, text: str, title: str, max_length: int = None) -> str:
        """
        하위 호환성을 위한 래퍼 함수
        """
        result = await self.create_summary_and_extract_source(text, title, max_length)
        return result["summary"]
    
    async def extract_hashtags(self, text: str, title: str) -> list[str]:
        """
        Gemini로 문서 해시태그 자동 추출
        
        카테고리:
        1. 시기: #2025, #2026, #2027
        2. 출처: #정부, #대학, #[대학명]
        3. 문서 성격: #모집요강, #입결통계, #고사자료
        4. 전형 구분: #수시, #정시
        
        Returns:
            해시태그 리스트 (예: ['#2026', '#서울대', '#모집요강', '#수시'])
        """
        logger.info(f"해시태그 추출 시작 - 제목: {title}")
        
        # 샘플 추출 (앞부분 3000자)
        sample = text[:3000]
        
        prompt = f"""다음 대학 입시 문서를 읽고 **해시태그**를 추출하세요.

**문서 제목:** {title}

**문서 내용 (앞부분):**
{sample}

---

**해시태그 규칙:**

1. **연도** (⚠️ 최우선 필수! 문서에 나온 모든 연도 추출):
   - 문서에 언급된 **모든 연도**를 빠짐없이 태그로 추출
   - "2025학년도" → #2025
   - "2026학년도" → #2026
   - "2027학년도" → #2027
   - "2028학년도" → #2028
   - ⚠️ 여러 연도가 있으면 모두 태그로 추가! (예: 2026, 2027 둘 다 있으면 → #2026 #2027)
   - ⚠️ 절대 빠뜨리지 마세요!

2. **대학명** (⚠️ 최우선 필수! 문서에 나온 모든 대학 추출):
   - 문서에 언급된 **모든 대학**을 빠짐없이 태그로 추출
   - "서울대학교" → #서울대
   - "연세대학교" → #연세대
   - "고려대학교" → #고려대
   - "성균관대학교" → #성균관대
   - "한양대학교" → #한양대
   - "중앙대학교" → #중앙대
   - "경희대학교" → #경희대
   - "이화여자대학교" → #이화여대
   - 기타 대학도 동일하게 (예: "건국대학교" → #건국대)
   - ⚠️ 여러 대학이 있으면 모두 태그로 추가! (예: 서울대, 연세대, 고려대 → #서울대 #연세대 #고려대)
   - ⚠️ 절대 빠뜨리지 마세요!
   - 정부/교육부/대교협 발행 문서면 #정부 태그 추가

3. **문서 성격** (필수, 1-2개):
   - #모집요강 : 규칙 문서 (시행계획, 전형계획, 모집요강, 정책 등)
   - #입결통계 : 숫자 문서 (커트라인, 경쟁률, 점수표, 입결 등)
   - #고사자료 : 공부 문서 (논술 기출, 면접 질문, 합격 사례, 가이드북)

4. **전형 구분** (선택, 1-2개):
   - #수시 (학종, 교과, 논술 등 수시모집 관련)
   - #정시 (수능 위주 정시모집 관련)
   - 둘 다 해당되면 둘 다 붙임

---

**JSON 형식으로 출력:**
```json
{{
  "hashtags": ["#2026", "#2027", "#서울대", "#연세대", "#고려대", "#입결통계"]
}}
```

**⚠️ 중요 주의사항:**
- 연도가 여러 개면 모두 포함! (예: 2026, 2027 → #2026 #2027)
- 대학이 여러 개면 모두 포함! (예: 서울대, 연세대, 고려대 → #서울대 #연세대 #고려대)
- 해시태그는 반드시 # 기호로 시작
- 대학명은 줄임말 사용 (예: "고려대학교" → #고려대)
- 최소 3개, 최대 10개
"""
        
        try:
            # Gemini 호출 (Lite 모델)
            response = await gemini_service.generate_text_lite(prompt)
            
            # JSON 파싱
            import re
            json_match = re.search(r'\{[^}]*"hashtags"[^}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                hashtags = data.get('hashtags', [])
                
                # 검증: # 기호로 시작하는지 확인
                hashtags = [tag if tag.startswith('#') else f'#{tag}' for tag in hashtags]
                hashtags = hashtags[:250]  # 최대 250개 (다수 대학/연도 포함 가능)
                
                if len(hashtags) < 3:
                    logger.warning(f"해시태그가 {len(hashtags)}개만 추출됨 (최소 3개 권장)")
                
                logger.info(f"해시태그 추출 완료: {hashtags}")
                return hashtags
            else:
                logger.error("JSON 형식 파싱 실패")
                return self._generate_fallback_hashtags(title)
        
        except Exception as e:
            logger.error(f"해시태그 추출 실패: {e}")
            return self._generate_fallback_hashtags(title)
    
    def _generate_fallback_hashtags(self, title: str) -> list[str]:
        """
        해시태그 추출 실패 시 제목 기반 기본 태그 생성
        """
        hashtags = ['#2026', '#대학']  # 기본값
        
        # 제목에서 연도 추출
        import re
        year_match = re.search(r'(2025|2026|2027)', title)
        if year_match:
            hashtags[0] = f'#{year_match.group()}'
        
        # 제목에서 대학명 추출
        universities = ['서울대', '연세대', '고려대', '성균관대', '한양대', '중앙대', '경희대', '이화여대', '카이스트', '포스텍']
        for univ in universities:
            if univ in title:
                hashtags.append(f'#{univ}')
                break
        
        # 문서 성격 추측
        if any(word in title for word in ['요강', '모집', '전형', '계획', '정책']):
            hashtags.append('#모집요강')
        elif any(word in title for word in ['입결', '경쟁률', '커트', '합격', '통계']):
            hashtags.append('#입결통계')
        else:
            hashtags.append('#모집요강')  # 기본값
        
        logger.warning(f"Fallback 해시태그 생성: {hashtags}")
        return hashtags


# 전역 인스턴스
classifier_service = ClassifierService()

