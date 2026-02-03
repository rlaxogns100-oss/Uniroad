"""
목차 처리 모듈
PDF의 목차를 감지하고 파싱하는 클래스
"""
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from config import embedding_settings as config

logger = logging.getLogger(__name__)


class TOCProcessor:
    """목차 감지 및 파싱을 담당하는 클래스"""

    def __init__(self, model_name: str = None):
        """
        초기화

        Args:
            model_name: LLM 모델명 (기본값: config.DEFAULT_LLM_MODEL)
        """
        self.model_name = model_name or config.DEFAULT_LLM_MODEL
        self.toc_keywords = ["목차", "차례", "contents", "table of contents", "index"]

    def detect_toc_pages(self, pdf_path: str, max_pages_to_check: int = 10) -> list:
        """
        PDF의 처음 몇 페이지에서 목차 페이지를 찾는 메서드 (Gemini LLM 사용)
        """
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        # 20페이지 이상이면 처음 10페이지만 확인
        if total_pages >= 20:
            pages_to_check = min(10, total_pages)
        else:
            pages_to_check = min(max_pages_to_check, total_pages)

        toc_pages = []

        # 페이지별 텍스트 추출 (병렬 처리 전에 미리 추출)
        page_data = []
        for page_num in range(pages_to_check):
            page = reader.pages[page_num]
            page_text = page.extract_text()

            # 빈 페이지는 건너뛰기
            if not page_text or not page_text.strip():
                continue

            # 페이지 텍스트가 너무 길면 앞부분만 사용 (토큰 절약)
            if len(page_text) > 2000:
                page_text = page_text[:2000] + "..."

            page_data.append({
                "page_num": page_num,
                "page_text": page_text
            })

        def check_toc_page(page_info):
            """단일 페이지 목차 여부 판단 함수 (병렬 실행용)"""
            page_num = page_info["page_num"]
            page_text = page_info["page_text"]

            detection_prompt = ChatPromptTemplate.from_template("""
당신은 PDF 문서의 목차 페이지를 식별하는 전문가입니다.

아래는 PDF 문서의 {page_num}번째 페이지의 텍스트입니다. 이 페이지가 목차(차례, Table of Contents) 페이지인지 판단하세요.

**판단 기준:**
1. "목차", "차례", "Contents", "Table of Contents" 등의 제목이 있는가?
2. 섹션 제목과 페이지 번호가 나열되어 있는가?
3. 문서의 구조(챕터, 섹션 등)를 보여주는 목록 형태인가?

**출력 형식:**
- 목차 페이지이면: "YES"
- 목차 페이지가 아니면: "NO"
- 확실하지 않으면: "NO"

**페이지 텍스트:**
{page_text}

**판단 결과:**""")

            llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0)
            chain = detection_prompt | llm | StrOutputParser()

            try:
                response = chain.invoke({
                    "page_num": page_num + 1,
                    "page_text": page_text
                })

                response_upper = response.strip().upper()
                if "YES" in response_upper or "목차" in response_upper:
                    return {"page_num": page_num, "is_toc": True, "error": None}
                return {"page_num": page_num, "is_toc": False, "error": None}
            except Exception as e:
                page_text_lower = page_text.lower()
                for keyword in self.toc_keywords:
                    if keyword in page_text_lower:
                        return {"page_num": page_num, "is_toc": True, "error": str(e)}
                return {"page_num": page_num, "is_toc": False, "error": str(e)}

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            future_to_page = {
                executor.submit(check_toc_page, page_info): page_info
                for page_info in page_data
            }

            for future in as_completed(future_to_page):
                page_info = future_to_page[future]
                try:
                    result = future.result()
                    if result["is_toc"]:
                        toc_pages.append(result["page_num"])
                        print(f"   ✅ 페이지 {result['page_num'] + 1}: 목차 페이지로 판단됨")
                    if result["error"]:
                        print(f"   ⚠️  페이지 {result['page_num'] + 1} 분석 중 오류 (키워드 기반 fallback): {result['error']}")
                except Exception as e:
                    print(f"   ⚠️  페이지 {page_info['page_num'] + 1} 처리 중 오류: {e}")

        toc_pages.sort()
        return toc_pages

    def parse_toc_structure(self, pdf_path: str, toc_pages: list) -> list:
        """
        목차 페이지를 LLM으로 분석하여 섹션 구조를 추출하는 메서드
        """
        reader = PdfReader(pdf_path)

        # 목차 페이지 텍스트 추출
        toc_text = ""
        for page_num in toc_pages:
            page = reader.pages[page_num]
            toc_text += f"\n--- 페이지 {page_num + 1} ---\n"
            toc_text += page.extract_text()

        parse_prompt = ChatPromptTemplate.from_template("""
# 임무

제공된 텍스트는 대학 입시 모집요강의 초반 페이지(1~10페이지 내외)이다.

이 텍스트에서 '목차', '차례', 'Contents', '전형 요약' 등의 목록을 찾아 섹션 정보를 추출하라.

# 추출 규칙 (매우 중요)

1. **섹션명(Title)**: 목차에 적힌 정확한 섹션 이름을 추출하라.

2. **시작 페이지(Start Page)**: 해당 섹션이 시작되는 페이지 번호를 정수로 추출하라.

3. **종료 페이지(End Page) 추론**: 

   - 현재 섹션의 종료 페이지는 **(다음 섹션의 시작 페이지 - 1)**로 계산하라.

   - 마지막 섹션의 경우, 문서의 끝이라고 판단되면 적절한 큰 숫자(예: 999) 혹은 문맥상 파악되는 마지막 페이지를 입력하라.

4. **노이즈 제거**: 목차와 관련 없는 헤더, 푸터, 인사말 등은 무시하라.

5. **계층 구조 평탄화**: 대분류, 소분류가 섞여 있어도 가능한 평탄한 리스트(Flat List)로 반환하되, '학생부종합전형' 같은 주요 전형 구분은 반드시 별도 섹션으로 분리되어야 한다.

# 예외 처리

- 목차에 페이지 번호가 명시되지 않은 경우, 바로 앞 섹션의 페이지 범위를 참고하거나 문맥을 통해 추정하라.

- 만약 명확한 목차 패턴을 찾을 수 없다면 빈 리스트 `[]`를 반환하라.

# 출력 형식 (Strict JSON)

반드시 아래 JSON 포맷으로만 출력하고, 마크다운(```json) 태그나 부가 설명은 포함하지 마라.

[
  {{
    "section_name": "전형 일정",
    "start_page": 3,
    "end_page": 4
  }},
  {{
    "section_name": "모집 단위 및 인원",
    "start_page": 5,
    "end_page": 7
  }},
  {{
    "section_name": "학생부교과(지역균형전형)",
    "start_page": 8,
    "end_page": 12
  }}
]

**목차 텍스트:**
{toc_text}

**JSON (마크다운 없이 순수 JSON만):**
""")

        toc_parsing_model = "gemini-2.5-flash-lite"
        llm = ChatGoogleGenerativeAI(model=toc_parsing_model, temperature=0)
        chain = parse_prompt | llm | StrOutputParser()

        response = chain.invoke({"toc_text": toc_text})

        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        response = response.strip()

        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                sections = json.loads(json_str)
                if sections and len(sections) > 0:
                    formatted_sections = []
                    for section in sections:
                        formatted_section = {
                            "title": section.get("section_name", section.get("title", "")),
                            "start_page": section.get("start_page", 1),
                            "end_page": section.get("end_page", 999)
                        }
                        formatted_sections.append(formatted_section)
                    return formatted_sections
            except json.JSONDecodeError as e:
                logger.warning("JSON 파싱 오류: %s", str(e))
                logger.warning("응답 내용: %s", response[:500])

        return None

    def create_default_sections(self, pdf_path: str) -> list:
        """목차를 찾지 못했을 때 페이지 수 기반으로 기본 섹션 생성"""
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        sections_per_part = max(1, total_pages // 4)

        sections = []
        for i in range(4):
            start = i * sections_per_part + 1
            end = (i + 1) * sections_per_part if i < 3 else total_pages
            sections.append({
                "title": f"섹션 {i+1}",
                "start_page": start,
                "end_page": end
            })

        return sections

    def validate_and_fix_sections(self, sections: list, pdf_path: str) -> list:
        """섹션의 페이지 범위를 검증하고 수정"""
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        for i, section in enumerate(sections):
            section["start_page"] = max(1, min(section.get("start_page", 1), total_pages))
            if i < len(sections) - 1:
                section["end_page"] = min(
                    section.get("end_page", total_pages),
                    sections[i+1]["start_page"] - 1
                )
            else:
                section["end_page"] = min(section.get("end_page", total_pages), total_pages)

        return sections

    # 요약 생성 시 토큰 한도 회피용 상한 (Gemini 입력 한도 내)
    MAX_PAGES_FOR_SUMMARY = 50
    MAX_CHARS_FOR_SUMMARY = 100000

    def generate_document_summary(self, pdf_path: str, max_pages: int = None) -> str:
        """PDF 문서의 요약본 생성 (목차 파싱 전에 실행). 실패 시 빈 문자열 반환."""
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        if max_pages is None:
            pages_to_extract = min(total_pages, self.MAX_PAGES_FOR_SUMMARY)
            if total_pages > self.MAX_PAGES_FOR_SUMMARY:
                print(f"   📄 처음 {pages_to_extract}페이지만 사용 (요약용, 전체 {total_pages}페이지)")
            else:
                print(f"   📄 전체 {total_pages}페이지 읽는 중...")
        else:
            pages_to_extract = min(max_pages, total_pages)
            print(f"   📄 처음 {pages_to_extract}페이지 읽는 중...")

        document_text = ""

        for page_num in range(pages_to_extract):
            page = reader.pages[page_num]
            page_text = page.extract_text()
            if page_text and page_text.strip():
                document_text += f"\n--- 페이지 {page_num + 1} ---\n"
                document_text += page_text

            if len(document_text) >= self.MAX_CHARS_FOR_SUMMARY:
                document_text = document_text[: self.MAX_CHARS_FOR_SUMMARY] + "\n\n... (이하 생략, 요약용으로 앞부분만 사용)"
                print(f"   📄 요약용 텍스트 상한 도달 ({self.MAX_CHARS_FOR_SUMMARY}자), 잘라서 사용")
                break

            if (page_num + 1) % 10 == 0:
                print(f"   📄 {page_num + 1}/{pages_to_extract}페이지 읽기 완료...")

        print(f"   ✅ {pages_to_extract}페이지 읽기 완료")

        if not document_text or not document_text.strip():
            logger.warning("요약 생성: 추출된 텍스트가 없습니다 (이미지 전용 PDF일 수 있음).")
            return ""

        prompt = ChatPromptTemplate.from_template("""
다음 문서를 읽고, 문서 구조를 파악하기 위한 **요약본(목차 스타일)**을 생성하세요.

**문서 내용:**
{document_text}

**요약 규칙:**
1. 중요한 섹션만 간결하게 나열
2. 불릿 포인트 사용
3. 각 항목은 문서 내 주요 주제/전형명/정책명 중심
4. 최대 500자 내외

**요약 결과:**""")

        llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0)
        chain = prompt | llm | StrOutputParser()

        try:
            summary = chain.invoke({"document_text": document_text})
            return summary.strip() if summary else ""
        except Exception as e:
            logger.warning("문서 요약 생성 중 오류 (계속 진행): %s", str(e))
            print(f"   ⚠️  문서 요약 생성 중 오류: {e}")
            return ""

    def generate_toc_from_summary(self, pdf_path: str, summary_text: str) -> list:
        """
        목차가 없을 때 요약 기반으로 섹션을 추론하는 메서드
        """
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        prompt = ChatPromptTemplate.from_template("""
다음은 문서 요약본입니다. 요약 내용을 기반으로 섹션 구조를 추론하여 JSON으로 반환하세요.

**요약:**
{summary_text}

**규칙:**
1. 섹션명은 요약에 나온 항목을 사용
2. 페이지 범위는 균등 분할(총 {total_pages}페이지)
3. 출력은 반드시 JSON 리스트

**출력 형식 예시:**
[
  {{ "title": "전형 일정", "start_page": 1, "end_page": 5 }},
  {{ "title": "모집 단위 및 인원", "start_page": 6, "end_page": 10 }}
]
""")

        llm = ChatGoogleGenerativeAI(model=self.model_name, temperature=0)
        chain = prompt | llm | StrOutputParser()

        try:
            response = chain.invoke({
                "summary_text": summary_text,
                "total_pages": total_pages
            })
        except Exception as e:
            logger.warning("요약 기반 목차 생성 LLM 호출 오류: %s", str(e))
            return None

        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        response = response.strip()

        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                sections = json.loads(json_str)
                if sections and len(sections) > 0:
                    return sections
            except json.JSONDecodeError as e:
                logger.warning("요약 기반 목차 JSON 파싱 오류: %s", str(e))

        return None
