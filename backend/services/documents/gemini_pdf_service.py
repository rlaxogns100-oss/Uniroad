"""
Gemini PDF 파싱 서비스 (5페이지씩 병렬 처리)
저렴하고 빠른 PDF → Markdown 변환
"""
import google.generativeai as genai
from config import settings
from config.logging_config import setup_logger
import asyncio
from typing import Optional, List
import tempfile
import os
import time
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from utils.token_logger import log_token_usage

logger = setup_logger('gemini_pdf')


class GeminiPDFService:
    """Gemini를 사용한 PDF 파싱 (5페이지씩 병렬 처리)"""

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Lite 모델 사용 (빠르고 저렴)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        logger.info("✅ GeminiPDFService 초기화 완료: gemini-2.5-flash-lite")
    
    def _remove_repetitions(self, text: str, min_length: int = 100) -> str:
        """
        반복되는 패턴 제거 (Gemini hallucination 방지)
        
        Args:
            text: 원본 텍스트
            min_length: 최소 반복 길이
        
        Returns:
            반복 제거된 텍스트
        """
        if len(text) < min_length * 3:
            return text
        
        # 긴 반복 패턴 찾기 (100자 이상)
        import re
        
        # 같은 문장/표가 연속으로 3번 이상 반복되는 패턴 제거
        # 예: "AAA" → "A"
        pattern = r'(.{' + str(min_length) + r',}?)(\1{2,})'
        
        original_len = len(text)
        text = re.sub(pattern, r'\1', text, flags=re.DOTALL)
        
        if len(text) < original_len:
            logger.info(f"   🔧 반복 패턴 제거: {original_len:,}자 → {len(text):,}자")
        
        return text

    async def _parse_pdf_chunk(
        self,
        pdf_bytes: bytes,
        chunk_id: int,
        start_page: int,
        end_page: int
    ) -> tuple:
        """
        PDF 청크를 Gemini로 파싱 (단일 청크 처리)

        Args:
            pdf_bytes: PDF 파일 바이트
            chunk_id: 청크 ID (로깅용)
            start_page: 시작 페이지 (1부터 시작, 표시용)
            end_page: 끝 페이지

        Returns:
            (chunk_id, markdown_text, usage_metadata)
        """
        try:
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_path = tmp_file.name

            try:
                # PDF 파일 업로드
                logger.info(f"   📤 청크 {chunk_id} 업로드 시작...")
                upload_start = time.time()
                uploaded_file = genai.upload_file(tmp_path)
                upload_time = time.time() - upload_start
                logger.info(f"   ✅ 청크 {chunk_id} 업로드 완료 ({upload_time:.2f}초)")
                
                # Markdown 변환 프롬프트
                prompt = """이 PDF 문서를 Markdown 형식으로 정확하게 변환해주세요.

⚠️ 중요 규칙:
1. 모든 텍스트를 정확히 추출하세요
2. 표(table)는 Markdown 표 형식으로 변환하세요
3. 제목, 리스트 등 구조를 유지하세요
4. 한국어를 정확하게 인식하세요
5. 불필요한 설명은 추가하지 말고 변환만 하세요
6. **절대 같은 내용을 반복하지 마세요** (표도 한 번만!)
7. **각 페이지 내용은 한 번만 출력하세요**

변환된 Markdown:"""

                # Gemini로 변환 (Retry 로직 포함)
                logger.info(f"   🤖 청크 {chunk_id} Gemini 처리 시작...")
                gen_start = time.time()
                
                max_retries = 3
                retry_delays = [2, 4, 8]
                
                for attempt in range(max_retries):
                    try:
                        response = await asyncio.to_thread(
                            self.model.generate_content,
                            [uploaded_file, prompt]
                        )
                        break  # 성공하면 루프 탈출
                    except Exception as e:
                        error_msg = str(e)
                        if ("503" in error_msg or "429" in error_msg or "overloaded" in error_msg.lower() or "rate limit" in error_msg.lower()):
                            if attempt < max_retries - 1:
                                delay = retry_delays[attempt]
                                logger.warning(f"   ⚠️ 청크 {chunk_id} Rate Limit (시도 {attempt + 1}/{max_retries}) → {delay}초 후 재시도")
                                await asyncio.sleep(delay)
                                continue
                            else:
                                logger.error(f"   ❌ 청크 {chunk_id} 최대 재시도 초과")
                                raise
                        else:
                            raise
                
                gen_time = time.time() - gen_start
                logger.info(f"   ✅ 청크 {chunk_id} Gemini 처리 완료 ({gen_time:.2f}초)")
                
                # 토큰 사용량 기록
                usage_metadata = None
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    usage_metadata = {
                        'prompt_tokens': getattr(usage, 'prompt_token_count', 0),
                        'candidates_tokens': getattr(usage, 'candidates_token_count', 0),
                        'total_tokens': getattr(usage, 'total_token_count', 0)
                    }
                    print(f"   💰 청크 {chunk_id} 토큰 사용량: {usage}")
                    logger.info(f"   💰 청크 {chunk_id} 토큰 사용량 - "
                              f"입력: {usage_metadata['prompt_tokens']}, "
                              f"출력: {usage_metadata['candidates_tokens']}, "
                              f"총합: {usage_metadata['total_tokens']}")
                    
                    # CSV에 기록
                    log_token_usage(
                        operation="PDF파싱_청크",
                        prompt_tokens=usage_metadata['prompt_tokens'],
                        output_tokens=usage_metadata['candidates_tokens'],
                        total_tokens=usage_metadata['total_tokens'],
                        model="gemini-2.5-flash-lite",
                        details=f"청크 {chunk_id} (페이지 {start_page}-{end_page})"
                    )
                
                markdown = response.text.strip()
                
                # 길이 제한 (비정상적으로 긴 결과 방지)
                MAX_CHUNK_LENGTH = 50000  # 50,000자 제한
                if len(markdown) > MAX_CHUNK_LENGTH:
                    logger.warning(f"   ⚠️ 청크 {chunk_id} 결과가 너무 김 ({len(markdown):,}자) → {MAX_CHUNK_LENGTH:,}자로 자름")
                    markdown = markdown[:MAX_CHUNK_LENGTH]
                
                # 반복 패턴 제거 (같은 텍스트가 3번 이상 반복되면 제거)
                markdown = self._remove_repetitions(markdown)
                
                # 업로드된 파일 삭제
                try:
                    genai.delete_file(uploaded_file.name)
                except:
                    pass
                
                logger.info(f"   ✅ 청크 {chunk_id} 완료 (페이지 {start_page}-{end_page}, {len(markdown)}자)")
                return (chunk_id, markdown, usage_metadata)

            finally:
                # 임시 파일 삭제
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"   ❌ 청크 {chunk_id} 실패: {e}")
            return (chunk_id, "", None)

    async def parse_pdf(
        self,
        file_bytes: bytes,
        filename: str,
        max_pages: Optional[int] = None,
        pages_per_chunk: int = 5  # 5페이지씩 처리 (API 호출 최적화)
    ) -> dict:
        """
        PDF를 Markdown으로 변환 (5페이지씩 병렬 처리)

        Args:
            file_bytes: PDF 파일 바이트
            filename: 파일명
            max_pages: 최대 처리 페이지 (테스트용)
            pages_per_chunk: 청크당 페이지 수 (기본 5페이지)

        Returns:
            {
                'markdown': str,
                'totalPages': int,
                'processingTime': float
            }
        """
        from pypdf import PdfReader, PdfWriter

        start_time = time.time()

        logger.info(f"🚀 Gemini PDF 파싱 시작: {filename}")
        logger.info(f"📦 파일 크기: {len(file_bytes) / 1024 / 1024:.2f}MB")

        try:
            # 임시 파일로 저장 (페이지 수 확인용)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name

            try:
                # 페이지 수 확인
                reader = PdfReader(tmp_path)
                total_pages = len(reader.pages)

                # 테스트 모드
                if max_pages and max_pages < total_pages:
                    total_pages = max_pages
                    logger.info(f"⚠️  테스트 모드: {max_pages}페이지만 처리")

                logger.info(f"📄 총 {total_pages}페이지 → {pages_per_chunk}페이지씩 병렬 처리")

                # 페이지 청크로 분할
                chunks: List[tuple] = []
                for i in range(0, total_pages, pages_per_chunk):
                    start = i
                    end = min(i + pages_per_chunk - 1, total_pages - 1)
                    chunk_id = i // pages_per_chunk + 1
                    
                    # 청크용 PDF 생성
                    writer = PdfWriter()
                    for page_num in range(start, end + 1):
                        writer.add_page(reader.pages[page_num])
                    
                    # 바이트로 변환
                    chunk_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    writer.write(chunk_tmp)
                    chunk_tmp.close()
                    
                    with open(chunk_tmp.name, 'rb') as f:
                        chunk_bytes = f.read()
                    
                    os.unlink(chunk_tmp.name)
                    
                    chunks.append((chunk_bytes, chunk_id, start + 1, end + 1))

                logger.info(f"⚡ {len(chunks)}개 청크 병렬 처리 시작...")

                # 병렬 처리 (최대 10개씩 배치)
                max_concurrent = 10
                all_results = []
                
                for batch_start in range(0, len(chunks), max_concurrent):
                    batch = chunks[batch_start:batch_start + max_concurrent]
                    batch_num = batch_start // max_concurrent + 1
                    total_batches = (len(chunks) + max_concurrent - 1) // max_concurrent
                    
                    logger.info(f"   🔄 배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 청크)...")
                    
                    tasks = [
                        self._parse_pdf_chunk(chunk_bytes, chunk_id, start, end)
                        for chunk_bytes, chunk_id, start, end in batch
                    ]
                    
                    batch_results = await asyncio.gather(*tasks)
                    all_results.extend(batch_results)

                # 결과 정렬 및 병합
                all_results.sort(key=lambda x: x[0])  # chunk_id로 정렬
                markdown = "\n\n".join([text for _, text, _ in all_results if text])
                
                # 토큰 사용량 집계
                total_prompt_tokens = 0
                total_candidates_tokens = 0
                total_tokens = 0
                
                for _, _, usage in all_results:
                    if usage:
                        total_prompt_tokens += usage.get('prompt_tokens', 0)
                        total_candidates_tokens += usage.get('candidates_tokens', 0)
                        total_tokens += usage.get('total_tokens', 0)

            finally:
                # 임시 파일 삭제
                os.unlink(tmp_path)

            processing_time = time.time() - start_time

            logger.info(f"✅ 파싱 완료!")
            logger.info(f"📝 결과 크기: {len(markdown) / 1024:.2f}KB")
            logger.info(f"⏱️  처리 시간: {processing_time:.2f}초 ({len(chunks)}개 청크 병렬)")
            
            # 총 토큰 사용량 출력
            if total_tokens > 0:
                print(f"\n{'=' * 60}")
                print(f"💰 총 토큰 사용량 (PDF 파싱)")
                print(f"   입력 토큰: {total_prompt_tokens:,}")
                print(f"   출력 토큰: {total_candidates_tokens:,}")
                print(f"   총 토큰: {total_tokens:,}")
                print(f"{'=' * 60}\n")
                
                logger.info(f"💰 총 토큰 사용량 - 입력: {total_prompt_tokens:,}, 출력: {total_candidates_tokens:,}, 총합: {total_tokens:,}")
                
                # CSV에 총합 기록
                log_token_usage(
                    operation="PDF파싱_총합",
                    prompt_tokens=total_prompt_tokens,
                    output_tokens=total_candidates_tokens,
                    total_tokens=total_tokens,
                    model="gemini-2.5-flash-lite",
                    details=f"{filename} ({total_pages}페이지, {len(chunks)}청크)"
                )

            return {
                'markdown': markdown,
                'totalPages': total_pages,
                'processingTime': processing_time,
                'tokenUsage': {
                    'promptTokens': total_prompt_tokens,
                    'candidatesTokens': total_candidates_tokens,
                    'totalTokens': total_tokens
                }
            }

        except Exception as e:
            logger.error(f"❌ Gemini PDF 파싱 오류: {e}")
            raise Exception(f"PDF 파싱 실패: {str(e)}")


# 전역 인스턴스
gemini_pdf_service = GeminiPDFService()
