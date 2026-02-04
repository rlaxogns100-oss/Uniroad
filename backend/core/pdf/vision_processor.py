"""
Gemini Vision 기반 PDF 처리 모듈
PDF 페이지를 이미지로 변환하여 Gemini Vision으로 마크다운 변환
"""
import os
import time
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz  # PyMuPDF
from PIL import Image
import google.generativeai as genai
from config import embedding_settings as config


class VisionProcessor:
    """Gemini Vision을 사용하여 PDF 페이지를 마크다운으로 변환하는 클래스"""

    def __init__(self, model_name: str = None):
        """
        초기화

        Args:
            model_name: Gemini Vision 모델명 (기본값: gemini-2.0-flash-exp)
        """
        # Vision 전용 모델 (임베딩_기반과 동일)
        vision_model = os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview")
        self.model_name = model_name or vision_model

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되지 않았습니다.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def convert_page_to_image(self, pdf_path: str, page_num: int, dpi: int = 200) -> Optional[Image.Image]:
        """PDF의 특정 페이지를 고화질 이미지로 변환"""
        try:
            doc = fitz.open(pdf_path)
            if page_num < 0 or page_num >= len(doc):
                print(f"   ⚠️  페이지 번호 {page_num}가 유효 범위를 벗어났습니다.")
                doc.close()
                return None

            page = doc[page_num]

            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            doc.close()
            return img
        except Exception as e:
            print(f"   ⚠️  페이지 {page_num + 1} 이미지 변환 중 오류: {e}")
            return None

    def convert_page_to_markdown(self, pdf_path: str, page_num: int, max_retries: int = 3) -> Optional[str]:
        """PDF의 특정 페이지를 Gemini Vision으로 마크다운으로 변환"""
        img = self.convert_page_to_image(pdf_path, page_num)
        if img is None:
            return None

        system_prompt = """너는 입시 모집요강 문서를 디지털화하는 전문가다. 이미지를 분석하여 완벽한 Markdown 포맷으로 변환하라.

[규칙]
1. 문서의 헤더(#), 리스트(-), 강조(**) 등 레이아웃 구조를 Markdown 문법으로 정확히 표현하라.
2. 표(Table)는 반드시 Markdown Table 문법으로 변환하라. 선이 없는 표라도 내용이 표 형식이면 표로 변환하라.
3. **[핵심]** 모든 표의 바로 윗줄에는 반드시 `<table_summary>표의 요약 설명</table_summary>` 태그를 삽입하라. 
   (예: <table_summary>2026학년도 수시모집 간호학과 모집인원 표입니다.</table_summary>)
4. 머리말, 꼬리말, 페이지 번호는 내용에서 제외하라.
5. 표가 아닌 일반 텍스트는 줄바꿈을 정리하여 자연스럽게 이어지도록 하라."""

        for attempt in range(max_retries):
            try:
                response = self.model.generate_content([system_prompt, img])

                if response and response.text:
                    markdown_text = response.text.strip()
                    return markdown_text
                print(f"   ⚠️  페이지 {page_num + 1} 변환 결과가 비어있습니다.")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
            except Exception as e:
                print(f"   ⚠️  페이지 {page_num + 1} Gemini Vision 호출 중 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None

        return None

    def convert_section_to_markdown(self, pdf_path: str, start_page: int, end_page: int, max_workers: int = 4) -> list:
        """PDF의 특정 페이지 범위를 모두 마크다운으로 변환 (병렬 처리)"""
        results = []

        start_idx = start_page - 1
        end_idx = end_page

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_page = {
                executor.submit(self.convert_page_to_markdown, pdf_path, page_num): page_num
                for page_num in range(start_idx, end_idx)
            }

            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    markdown = future.result()
                    if markdown:
                        results.append((page_num + 1, markdown))
                        print(f"   ✅ 페이지 {page_num + 1} 변환 완료")
                    else:
                        print(f"   ⚠️  페이지 {page_num + 1} 변환 실패")
                except Exception as e:
                    print(f"   ⚠️  페이지 {page_num + 1} 변환 중 오류: {e}")

        results.sort(key=lambda x: x[0])
        return results
