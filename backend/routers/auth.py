"""
인증 API 라우터
회원가입, 로그인, 로그아웃, 사용자 정보
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@router.post("/signup", response_model=AuthResponse)
async def sign_up(request: SignUpRequest):
    """
    회원가입
    """
    try:
        # Supabase Auth로 회원가입
        response = supabase_service.client.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {
                    "name": request.name or request.email.split("@")[0]
                }
            }
        })
        
        if response.user is None:
            raise HTTPException(status_code=400, detail="회원가입 실패")
        
        # 이메일 확인이 필요한 경우 session이 None일 수 있음
        if response.session is None:
            raise HTTPException(
                status_code=400, 
                detail="회원가입 완료! 이메일을 확인하여 계정을 활성화해주세요."
            )
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name"),
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"회원가입 실패: {str(e)}")


@router.post("/signin", response_model=AuthResponse)
async def sign_in(request: SignInRequest):
    """
    로그인
    """
    try:
        # Supabase Auth로 로그인
        response = supabase_service.client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
        
        if response.user is None:
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        
        if response.session is None:
            raise HTTPException(status_code=401, detail="이메일 확인이 필요합니다")
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name"),
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"로그인 실패: {str(e)}")


@router.post("/signout")
async def sign_out(user: dict = Depends(get_current_user)):
    """
    로그아웃
    """
    try:
        supabase_service.client.auth.sign_out()
        return {"message": "로그아웃 성공"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"로그아웃 실패: {str(e)}")


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보
    """
    try:
        # Supabase에서 사용자 정보 가져오기
        response = supabase_service.client.auth.get_user()
        
        if response.user is None:
            raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
        
        return {
            "id": response.user.id,
            "email": response.user.email,
            "name": response.user.user_metadata.get("name"),
            "created_at": response.user.created_at,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"사용자 정보 조회 실패: {str(e)}")


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """
    액세스 토큰 갱신
    """
    try:
        response = supabase_service.client.auth.refresh_session(refresh_token)
        
        if response.session is None:
            raise HTTPException(status_code=401, detail="토큰 갱신 실패")
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"토큰 갱신 실패: {str(e)}")

