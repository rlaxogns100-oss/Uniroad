"""
파일 업로드 API 라우터
"""
import asyncio
import time
import tempfile
import os
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from PyPDF2 import PdfReader

from services.pdf_processor import process_pdf, upload_to_supabase_with_file

router = APIRouter()


@router.post("/")
async def upload_document(
    file: UploadFile = File(...),
    school_name: Optional[str] = Form(None)
):
    """임베딩 기반 PDF 문서 업로드 및 처리"""
    start_time = time.time()

    print(f"\n{'=' * 60}")
    print(f"📄 파일 업로드 시작: {file.filename}")
    if school_name:
        print(f"   🏫 학교: {school_name}")
    print(f"   크기: {file.size / 1024 / 1024:.2f}MB" if file.size else "   크기: Unknown")
    print(f"{'=' * 60}\n")
    
    try:
        # 파일 타입 검증
        if not file.content_type == "application/pdf":
            raise HTTPException(400, "PDF 파일만 업로드 가능합니다.")
        
        # 파일 크기 검증
        MAX_SIZE = 50 * 1024 * 1024  # 50MB
        file_bytes = await file.read()
        if len(file_bytes) > MAX_SIZE:
            raise HTTPException(400, "파일 크기는 50MB 이하여야 합니다.")
        
        # 학교명 검증 및 정규화
        if not school_name or not school_name.strip():
            raise HTTPException(400, "학교명을 입력해주세요. (예: 연세대학교, 고려대학교)")
        
        safe_school_name = school_name.strip()
        
        # 학교명이 너무 짧으면 경고
        if len(safe_school_name) < 2:
            raise HTTPException(400, "학교명이 너무 짧습니다. (최소 2글자)")
        
        # 학교명이 너무 길면 경고
        if len(safe_school_name) > 50:
            raise HTTPException(400, "학교명이 너무 깁니다. (최대 50글자)")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name

        try:
            # CPU/IO 집약적 처리라 스레드 풀에서 실행 (이벤트 루프 블로킹 방지)
            result = await asyncio.to_thread(
                process_pdf,
                tmp_path,
                safe_school_name,
                None,
                True,
            )

            if isinstance(result, tuple) and result[0] is None:
                reason = result[1] if len(result) > 1 else "PDF 처리 실패"
                raise Exception(reason)
            processed_data = result if not isinstance(result, tuple) else result[0]
            if not processed_data:
                raise Exception("PDF 처리 결과가 비어있습니다.")

            document_id = await asyncio.to_thread(
                upload_to_supabase_with_file,
                safe_school_name,
                tmp_path,
                processed_data,
                file.filename,
                None,
            )

            if not document_id:
                raise Exception("Supabase 업로드 실패")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        total_pages = len(PdfReader(BytesIO(file_bytes)).pages)
        chunks_total = len(processed_data.get("chunks", []))
        total_time = time.time() - start_time

        print(f"\n{'=' * 60}")
        print(f"🎉 처리 완료!")
        print(f"   📄 페이지: {total_pages}페이지")
        print(f"   📦 청크: {chunks_total}개")
        print(f"   ⏱️  총 소요시간: {total_time:.2f}초")
        print(f"{'=' * 60}\n")

        return {
            "success": True,
            "message": "파일이 성공적으로 처리되었습니다.",
            "stats": {
                "totalPages": total_pages,
                "chunksTotal": chunks_total,
                "chunksSuccess": chunks_total,
                "chunksFailed": 0,
                "processingTime": f"{total_time:.2f}초",
                "markdownSize": "N/A"
            },
            "preview": {
                "firstChunk": processed_data.get("chunks", [])[0].page_content[:500] if processed_data.get("chunks") else ""
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        total_time = time.time() - start_time
        msg = str(e).strip() or "파일 처리 실패 (원인 미상)"
        print(f"\n❌ 파일 업로드 오류 ({total_time:.2f}초 경과): {e}")
        traceback.print_exc()
        raise HTTPException(500, msg)

