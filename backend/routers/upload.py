"""
파일 업로드 API 라우터
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from services.documents import (
    gemini_pdf_service as pdf_service,
    classifier_service,
    embedding_service
)
from services.supabase_client import supabase_service
import time

router = APIRouter()


@router.post("/")
async def upload_document(
    file: UploadFile = File(...)
):
    """
    PDF 문서 업로드 및 처리
    
    1. Gemini로 PDF → Markdown 변환
    2. Gemini로 요약 + 출처 자동 추출
    3. 텍스트 청킹
    4. 임베딩 생성
    5. Supabase에 저장
    """
    start_time = time.time()
    
    # 파일명을 제목으로 사용 (.pdf 제거)
    title = file.filename.replace('.pdf', '').replace('_', ' ')
    
    print(f"\n{'=' * 60}")
    print(f"📄 파일 업로드 시작: {file.filename}")
    print(f"   자동 추출 제목: {title}")
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
        
        # 1️⃣ PDF를 Supabase Storage에 저장
        print("1️⃣ PDF를 Supabase Storage에 업로드 중...")
        storage_result = supabase_service.upload_pdf_to_storage(
            file_bytes,
            file.filename
        )
        
        if storage_result:
            storage_file_name, file_url = storage_result
        else:
            print("⚠️ PDF Storage 업로드 실패 (계속 진행)")
            storage_file_name = file.filename  # 원본 파일명 사용
            file_url = ''  # None 대신 빈 문자열
        
        # 2️⃣ PDF → Markdown 변환
        print(f"2️⃣ GEMINI로 PDF → Markdown 변환 중...")
        parse_result = await pdf_service.parse_pdf(
            file_bytes,
            file.filename
            # 전체 페이지 파싱
        )
        
        markdown = parse_result['markdown']
        total_pages = parse_result['totalPages']
        
        # Markdown이 비어있으면 오류
        if not markdown or len(markdown.strip()) == 0:
            raise Exception("PDF 파싱 결과가 비어있습니다. 네트워크 연결을 확인하거나 다시 시도해주세요.")
        
        # 3️⃣ 요약 + 출처 추출 + 해시태그 추출 + 청킹
        print("3️⃣ Gemini 요약 + 출처 + 해시태그 추출 + 청킹...")
        import asyncio

        # 요약 + 출처 추출, 해시태그 추출 병렬 실행
        summary_task = classifier_service.create_summary_and_extract_source(
            markdown, 
            title, 
            max_length=500
        )
        hashtags_task = classifier_service.extract_hashtags(markdown, title)

        # 청킹은 동기 함수라서 별도 실행
        chunks = embedding_service.chunk_text(markdown, chunk_size=1200, chunk_overlap=200)

        # 요약/출처/해시태그 결과 대기
        summary_result, hashtags = await asyncio.gather(summary_task, hashtags_task)
        summary = summary_result["summary"]
        source = summary_result["source"]
        
        print(f"   ✅ 추출된 출처: {source}")
        print(f"   ✅ 추출된 해시태그: {hashtags}")
        
        # 4️⃣ Gemini 임베딩 생성 (병렬)
        print("4️⃣ Gemini 임베딩 생성 중 (병렬 처리)...")
        embeddings = await embedding_service.create_embeddings_batch(
            chunks,
            batch_size=5  # Gemini는 5개씩 병렬 처리
        )
        
        # 5️⃣ Supabase 저장
        print("5️⃣ Supabase에 저장 중...")

        # 5-1. documents_metadata 테이블에 먼저 저장 (1개만)
        print("   📝 문서 메타데이터 저장 중...")
        metadata_success = await supabase_service.insert_document_metadata(
            file_name=file.filename,  # 원본 파일명 (한글 가능)
            storage_file_name=storage_file_name,  # Storage에 저장된 UUID 파일명
            title=title,
            source=source,
            summary=summary,
            total_pages=total_pages,
            total_chunks=len(chunks),
            file_url=file_url,  # Storage URL 추가
            hashtags=hashtags  # 해시태그 추가
        )

        if not metadata_success:
            raise Exception("문서 메타데이터 저장 실패")

        print(f"   ✅ 문서 메타데이터 저장 완료")

        # 5-2. 청크 저장 (간소화된 metadata)
        print(f"   📦 청크 저장 중 ({len(chunks)}개)...")
        success_count = 0
        failed_count = 0

        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # 간소화된 metadata (fileName, chunkIndex, totalChunks만)
            metadata = {
                'fileName': file.filename,
                'chunkIndex': idx,
                'totalChunks': len(chunks)
            }

            success = await supabase_service.insert_document_chunk(
                chunk,
                embedding,
                metadata
            )

            if success:
                success_count += 1
            else:
                failed_count += 1

            # 진행률 표시
            if (idx + 1) % 10 == 0 or idx == len(chunks) - 1:
                print(f"   진행: {idx + 1}/{len(chunks)} ({(idx + 1) / len(chunks) * 100:.0f}%)")
        
        total_time = time.time() - start_time

        print(f"\n{'=' * 60}")
        print(f"🎉 처리 완료!")
        print(f"   📄 페이지: {total_pages}페이지")
        print(f"   📦 청크: {len(chunks)}개")
        print(f"   ✅ 성공: {success_count}개")
        print(f"   ❌ 실패: {failed_count}개")
        print(f"   ⏱️  총 소요시간: {total_time:.2f}초")
        print(f"   📝 요약 길이: {len(summary)}자")
        print(f"{'=' * 60}\n")

        return {
            "success": True,
            "message": "파일이 성공적으로 처리되었습니다.",
            "summary": summary,
            "stats": {
                "totalPages": total_pages,
                "chunksTotal": len(chunks),
                "chunksSuccess": success_count,
                "chunksFailed": failed_count,
                "processingTime": f"{total_time:.2f}초",
                "markdownSize": f"{len(markdown) / 1024:.2f}KB"
            },
            "preview": {
                "firstChunk": chunks[0][:500] if chunks else ""
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - start_time
        print(f"\n❌ 파일 업로드 오류 ({total_time:.2f}초 경과): {e}")
        raise HTTPException(500, f"파일 처리 중 오류가 발생했습니다: {str(e)}")

