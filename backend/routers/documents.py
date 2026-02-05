"""
문서 관리 API 라우터
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.supabase_client import supabase_service
from typing import Optional

router = APIRouter()


class UpdateDocumentRequest(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    hashtags: Optional[list] = None


async def _get_documents_list():
    """문서 목록 조회 공통 로직"""
    try:
        documents = await supabase_service.get_documents()
        return {"documents": documents}
    except Exception as e:
        raise HTTPException(500, f"문서 목록 조회 실패: {str(e)}")


@router.get("/")
@router.get("")  # 슬래시 없이 /api/documents 호출 시 307 방지
async def get_documents():
    """업로드된 문서 목록 조회"""
    return await _get_documents_list()


@router.patch("/{document_id}")
async def update_document(document_id: str, request: UpdateDocumentRequest):
    """문서 제목/출처/해시태그 수정"""
    try:
        success = await supabase_service.update_document_metadata(
            file_name=document_id,
            title=request.title,
            source=request.source,
            hashtags=request.hashtags
        )
        if success:
            return {"success": True, "message": "문서가 수정되었습니다."}
        else:
            raise HTTPException(500, "문서 수정 실패")
    except Exception as e:
        raise HTTPException(500, f"문서 수정 실패: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """문서 삭제"""
    try:
        success = await supabase_service.delete_document(document_id)
        if success:
            return {"success": True, "message": "문서가 삭제되었습니다."}
        else:
            raise HTTPException(500, "문서 삭제 실패")
    except Exception as e:
        raise HTTPException(500, f"문서 삭제 실패: {str(e)}")

