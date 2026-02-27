"""
사용자 프로필 API 라우터
모의고사 점수 저장 및 조회, 프로필 이미지(image_url) 저장
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB


class ScoreEntry(BaseModel):
    """개별 과목 점수 - 등급, 표준점수, 백분위 모두 입력"""
    등급: Optional[int] = Field(None, description="등급 (1-9)")
    표준점수: Optional[float] = Field(None, description="표준점수")
    백분위: Optional[float] = Field(None, description="백분위")
    선택과목: Optional[str] = Field(None, description="선택과목 (국어, 수학, 탐구)")
    
    @validator('등급')
    def validate_grade(cls, v):
        if v is not None and (v < 1 or v > 9):
            raise ValueError("등급은 1-9 사이여야 합니다")
        return v
    
    @validator('표준점수', '백분위')
    def validate_score(cls, v):
        if v is not None and v < 0:
            raise ValueError("점수는 0 이상이어야 합니다")
        return v


class ProfileRequest(BaseModel):
    """프로필 저장/수정 요청"""
    scores: Dict[str, ScoreEntry] = Field(..., description="과목별 점수")
    
    @validator('scores')
    def validate_scores(cls, v):
        # 최소 1개 과목은 있어야 함
        if not v:
            raise ValueError("최소 1개 과목의 점수를 입력해야 합니다")
        
        # 허용된 과목명 확인
        allowed_subjects = ["국어", "수학", "영어", "탐구1", "탐구2", "한국사"]
        for subject in v.keys():
            if subject not in allowed_subjects:
                raise ValueError(f"허용되지 않은 과목명: {subject}. 허용: {allowed_subjects}")
        
        # 각 과목이 최소 1개 점수는 가지고 있어야 함
        for subject, score in v.items():
            if not (score.등급 or score.표준점수 or score.백분위):
                raise ValueError(f"{subject}의 점수를 최소 1개 이상 입력해주세요")
        
        return v


class ProfileResponse(BaseModel):
    """프로필 응답"""
    user_id: str
    scores: Dict[str, Any]
    created_at: str
    updated_at: str
    is_premium: Optional[bool] = None  # Polar 구독 시 metadata.is_premium
    image_url: Optional[str] = None  # user_profiles.metadata.image_url (프로필 이미지)
    display_name: Optional[str] = None  # 표시 이름 (metadata)
    bio: Optional[str] = None  # 짧은 자기소개 (metadata)
    description: Optional[str] = None  # 프로필 설명 문구 (metadata)


class ProfileUpdateRequest(BaseModel):
    """프로필 수정 요청 (이미지 URL, 이름, 소개 등)"""
    image_url: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    description: Optional[str] = None


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: dict = Depends(get_current_user)):
    """
    내 프로필 조회
    """
    try:
        profile = await supabase_service.get_user_profile(user["user_id"])
        
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        is_premium = meta.get("is_premium")
        image_url = meta.get("image_url")
        display_name = meta.get("display_name")
        bio = meta.get("bio")
        description = meta.get("description")
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": is_premium,
            "image_url": image_url,
            "display_name": display_name,
            "bio": bio,
            "description": description,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 조회 실패: {str(e)}")


@router.post("/me", response_model=ProfileResponse)
async def upsert_my_profile(
    request: ProfileRequest,
    user: dict = Depends(get_current_user)
):
    """
    프로필 생성/수정 (upsert)
    점수 데이터를 저장합니다.
    """
    try:
        # Pydantic 모델을 딕셔너리로 변환
        scores_dict = {}
        for subject, score_entry in request.scores.items():
            scores_dict[subject] = score_entry.dict(exclude_none=True)
        
        # 프로필 저장
        success = await supabase_service.upsert_user_profile(
            user["user_id"],
            scores_dict
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="프로필 저장 실패")
        
        # 저장된 프로필 다시 조회
        profile = await supabase_service.get_user_profile(user["user_id"])
        
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        is_premium = meta.get("is_premium")
        image_url = meta.get("image_url")
        display_name = meta.get("display_name")
        bio = meta.get("bio")
        description = meta.get("description")
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": is_premium,
            "image_url": image_url,
            "display_name": display_name,
            "bio": bio,
            "description": description,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 저장 실패: {str(e)}")


@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    request: ProfileUpdateRequest,
    user: dict = Depends(get_current_user)
):
    """
    프로필 수정 (image_url 등). user_profiles.metadata.image_url 에 저장.
    """
    try:
        user_id = user["user_id"]
        if request.image_url is not None:
            await supabase_service.update_user_profile_metadata(user_id, "image_url", request.image_url)
        if request.display_name is not None:
            await supabase_service.update_user_profile_metadata(user_id, "display_name", request.display_name)
        if request.bio is not None:
            await supabase_service.update_user_profile_metadata(user_id, "bio", request.bio)
        if request.description is not None:
            await supabase_service.update_user_profile_metadata(user_id, "description", request.description)
        profile = await supabase_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": meta.get("is_premium"),
            "image_url": meta.get("image_url"),
            "display_name": meta.get("display_name"),
            "bio": meta.get("bio"),
            "description": meta.get("description"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 수정 실패: {str(e)}")


@router.post("/me/avatar", response_model=ProfileResponse)
async def upload_my_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    프로필 사진 업로드. Storage에 저장 후 user_profiles.metadata.image_url 에 URL 저장.
    """
    try:
        if file.content_type not in ALLOWED_AVATAR_TYPES:
            raise HTTPException(400, "이미지 파일만 업로드 가능합니다. (jpg, png, gif, webp)")
        data = await file.read()
        if len(data) > MAX_AVATAR_SIZE:
            raise HTTPException(400, "파일 크기는 5MB 이하여야 합니다.")
        user_id = user["user_id"]
        url = supabase_service.upload_avatar_to_storage(user_id, data, file.content_type or "image/jpeg")
        if not url:
            raise HTTPException(status_code=500, detail="이미지 업로드 실패")
        await supabase_service.update_user_profile_metadata(user_id, "image_url", url)
        profile = await supabase_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": meta.get("is_premium"),
            "image_url": meta.get("image_url"),
            "display_name": meta.get("display_name"),
            "bio": meta.get("bio"),
            "description": meta.get("description"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 사진 업로드 실패: {str(e)}")


@router.delete("/me")
async def delete_my_profile(user: dict = Depends(get_current_user)):
    """
    프로필 삭제
    """
    try:
        success = await supabase_service.delete_user_profile(user["user_id"])
        
        if not success:
            raise HTTPException(status_code=500, detail="프로필 삭제 실패")
        
        return {"message": "프로필이 삭제되었습니다"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 삭제 실패: {str(e)}")


@router.get("/me/scores")
async def get_my_scores(user: dict = Depends(get_current_user)):
    """
    내 점수만 조회 (간단한 버전)
    """
    try:
        profile = await supabase_service.get_user_profile(user["user_id"])
        
        if not profile:
            return {"scores": {}}
        
        return {"scores": profile["scores"]}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"점수 조회 실패: {str(e)}")
