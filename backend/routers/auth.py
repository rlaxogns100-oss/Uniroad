"""
인증 API 라우터
회원가입, 로그인, 로그아웃, 사용자 정보
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()


class SignUpRequest(BaseModel):
    email: EmailStr = Field(..., max_length=30)
    password: str = Field(..., min_length=6, max_length=30)
    name: Optional[str] = Field(None, max_length=30)


class SignInRequest(BaseModel):
    email: EmailStr = Field(..., max_length=30)
    password: str = Field(..., max_length=30)


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
    - JWT 토큰 기반 인증이므로 서버에서는 별도 처리 불필요
    - 클라이언트에서 토큰을 삭제하면 로그아웃 완료
    - 공유 Supabase 클라이언트의 sign_out() 호출 시 다른 사용자 세션에 영향을 줄 수 있으므로 제거
    """
    # 토큰 기반 인증이므로 서버에서는 아무것도 하지 않음
    # 클라이언트에서 localStorage의 토큰을 삭제하면 로그아웃 완료
    return {"message": "로그아웃 성공"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보
    - get_current_user 미들웨어에서 JWT 토큰을 검증하고 사용자 정보를 추출
    - 공유 Supabase 클라이언트의 auth.get_user() 사용 시 동시 요청에서 
      다른 사용자 정보가 반환될 수 있으므로, 미들웨어에서 검증된 정보를 그대로 반환
    """
    # get_current_user에서 이미 JWT 토큰을 검증하고 사용자 정보를 추출했으므로
    # 공유 클라이언트를 사용하지 않고 검증된 정보를 그대로 반환
    return {
        "id": user.get("user_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "created_at": user.get("created_at"),
    }


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


class OAuthRequest(BaseModel):
    provider: str  # "google" or "kakao"
    redirect_to: Optional[str] = None


@router.post("/oauth/url")
async def get_oauth_url(request: OAuthRequest):
    """
    OAuth 로그인 URL 반환
    """
    try:
        redirect_to = request.redirect_to or "http://localhost:5173"

        response = supabase_service.client.auth.sign_in_with_oauth({
            "provider": request.provider,
            "options": {
                "redirect_to": redirect_to,
            }
        })

        return {"url": response.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth URL 생성 실패: {str(e)}")


class OAuthCallbackRequest(BaseModel):
    code: str


@router.post("/oauth/callback")
async def oauth_callback(request: OAuthCallbackRequest):
    """
    OAuth 코드를 토큰으로 교환
    """
    try:
        response = supabase_service.client.auth.exchange_code_for_session({
            "auth_code": request.code
        })

        if response.session is None:
            raise HTTPException(status_code=400, detail="토큰 교환 실패")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name") or response.user.user_metadata.get("full_name") or response.user.email.split("@")[0],
                "avatar_url": response.user.user_metadata.get("avatar_url"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth 콜백 처리 실패: {str(e)}")

