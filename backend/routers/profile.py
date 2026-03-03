"""
사용자 프로필 API 라우터
모의고사 점수 저장 및 조회, 프로필 이미지(image_url) 저장
"""
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, Tuple
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
    banner_image_url: Optional[str] = None  # user_profiles.metadata.banner_image_url (배경 이미지)
    display_name: Optional[str] = None  # 표시 이름 (metadata)
    bio: Optional[str] = None  # 짧은 자기소개 (metadata)
    description: Optional[str] = None  # 프로필 설명 문구 (metadata)


class ProfileUpdateRequest(BaseModel):
    """프로필 수정 요청 (이미지 URL, 이름, 소개 등)"""
    image_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    description: Optional[str] = None


class SchoolGradeInputRequest(BaseModel):
    """내신 성적 입력 화면 원본 JSON 저장/조회"""
    school_grade_input: Dict[str, Any] = Field(default_factory=dict)


def _parse_image_url_jsonb(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """metadata.image_url (jsonb) 파싱: { avatar?, banner? } 또는 레거시 문자열 → (avatar_url, banner_url)"""
    if raw is None:
        return (None, None)
    if isinstance(raw, dict):
        return (raw.get("avatar"), raw.get("banner"))
    if isinstance(raw, str) and raw.strip():
        return (raw, None)  # 레거시: 문자열이면 avatar로만 사용
    return (None, None)


def _build_image_url_jsonb(avatar: Optional[str], banner: Optional[str]) -> dict:
    """avatar/banner URL을 metadata.image_url jsonb 객체로 생성 (None이면 키 생략)"""
    out = {}
    if avatar:
        out["avatar"] = avatar
    if banner:
        out["banner"] = banner
    return out


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(user: dict = Depends(get_current_user)):
    """
    내 프로필 조회. metadata.image_url 은 jsonb { "avatar": "...", "banner": "..." } 형태.
    """
    try:
        profile = await supabase_service.get_user_profile(user["user_id"])
        
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        is_premium = meta.get("is_premium")
        raw_image_url = meta.get("image_url")
        image_url, banner_image_url = _parse_image_url_jsonb(raw_image_url)
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
            "banner_image_url": banner_image_url,
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
        img_avatar, img_banner = _parse_image_url_jsonb(meta.get("image_url"))
        display_name = meta.get("display_name")
        bio = meta.get("bio")
        description = meta.get("description")
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": is_premium,
            "image_url": img_avatar,
            "banner_image_url": img_banner,
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
    프로필 수정. 이미지 URL은 metadata.image_url(jsonb) { "avatar", "banner" } 에 저장.
    """
    try:
        user_id = user["user_id"]
        if request.image_url is not None or request.banner_image_url is not None:
            profile = await supabase_service.get_user_profile(user_id)
            meta = (profile or {}).get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}
            cur_avatar, cur_banner = _parse_image_url_jsonb(meta.get("image_url"))
            avatar = request.image_url if request.image_url is not None else cur_avatar
            banner = request.banner_image_url if request.banner_image_url is not None else cur_banner
            image_url_obj = _build_image_url_jsonb(avatar, banner)
            await supabase_service.update_user_profile_metadata(user_id, "image_url", image_url_obj)
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
        img_avatar, img_banner = _parse_image_url_jsonb(meta.get("image_url"))
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": meta.get("is_premium"),
            "image_url": img_avatar,
            "banner_image_url": img_banner,
            "display_name": meta.get("display_name"),
            "bio": meta.get("bio"),
            "description": meta.get("description"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 수정 실패: {str(e)}")


@router.post("/me/banner", response_model=ProfileResponse)
async def upload_my_banner(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """
    프로필 배경 이미지 업로드. Storage에 저장 후 user_profiles.metadata.banner_image_url 에 URL 저장.
    """
    try:
        if file.content_type not in ALLOWED_AVATAR_TYPES:
            raise HTTPException(400, "이미지 파일만 업로드 가능합니다. (jpg, png, gif, webp)")
        data = await file.read()
        if len(data) > MAX_AVATAR_SIZE:
            raise HTTPException(400, "파일 크기는 5MB 이하여야 합니다.")
        user_id = user["user_id"]
        url = supabase_service.upload_banner_to_storage(user_id, data, file.content_type or "image/jpeg")
        if not url:
            raise HTTPException(status_code=500, detail="배경 이미지 업로드 실패")
        profile = await supabase_service.get_user_profile(user_id)
        meta = (profile or {}).get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        cur_avatar, _ = _parse_image_url_jsonb(meta.get("image_url"))
        image_url_obj = _build_image_url_jsonb(cur_avatar, url)
        await supabase_service.update_user_profile_metadata(user_id, "image_url", image_url_obj)
        profile = await supabase_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        img_avatar, img_banner = _parse_image_url_jsonb(meta.get("image_url"))
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": meta.get("is_premium"),
            "image_url": img_avatar,
            "banner_image_url": img_banner,
            "display_name": meta.get("display_name"),
            "bio": meta.get("bio"),
            "description": meta.get("description"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"배경 이미지 업로드 실패: {str(e)}")


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
        profile = await supabase_service.get_user_profile(user_id)
        meta = (profile or {}).get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        _, cur_banner = _parse_image_url_jsonb(meta.get("image_url"))
        image_url_obj = _build_image_url_jsonb(url, cur_banner)
        await supabase_service.update_user_profile_metadata(user_id, "image_url", image_url_obj)
        profile = await supabase_service.get_user_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
        meta = profile.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        img_avatar, img_banner = _parse_image_url_jsonb(meta.get("image_url"))
        return {
            "user_id": profile["user_id"],
            "scores": profile["scores"],
            "created_at": profile["created_at"],
            "updated_at": profile["updated_at"],
            "is_premium": meta.get("is_premium"),
            "image_url": img_avatar,
            "banner_image_url": img_banner,
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


def _normalize_school_grade_input_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


@router.get("/me/school-grade-input")
async def get_my_school_grade_input(user: dict = Depends(get_current_user)):
    """
    내신 성적 입력 원본 JSON 조회
    - 저장 위치: user_profiles.metadata.school_grade_input
    """
    try:
        profile = await supabase_service.get_user_profile(user["user_id"])
        metadata = (profile or {}).get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        payload = _normalize_school_grade_input_payload(metadata.get("school_grade_input"))
        return {"school_grade_input": payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"내신 성적 입력 조회 실패: {str(e)}")


@router.post("/me/school-grade-input")
async def upsert_my_school_grade_input(
    request: SchoolGradeInputRequest,
    user: dict = Depends(get_current_user),
):
    """
    내신 성적 입력 원본 JSON 저장
    - 저장 위치: user_profiles.metadata.school_grade_input
    """
    try:
        user_id = user["user_id"]
        next_payload = _normalize_school_grade_input_payload(request.school_grade_input)
        success = await supabase_service.update_user_profile_metadata(
            user_id, "school_grade_input", next_payload
        )
        if not success:
            raise HTTPException(status_code=500, detail="내신 성적 입력 저장 실패")

        metadata = await supabase_service.get_user_profile_metadata(user_id)
        saved_payload = _normalize_school_grade_input_payload(
            (metadata or {}).get("school_grade_input")
        )
        return {"ok": True, "school_grade_input": saved_payload}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"내신 성적 입력 저장 실패: {str(e)}")
