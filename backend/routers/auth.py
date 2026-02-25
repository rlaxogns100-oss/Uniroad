"""
인증 API 라우터
회원가입, 로그인, 로그아웃, 사용자 정보
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from supabase import create_client
from config import settings
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()


def _auth_client():
    """인증 요청은 공유 클라이언트 대신 매 요청 fresh client 사용."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def _safe_name(name: Optional[str], email: Optional[str]) -> str:
    raw = (name or "").strip()
    if raw:
        return raw
    if email and "@" in email:
        return email.split("@")[0]
    return ""


def _sync_user_row(user_id: Optional[str], email: Optional[str], name: Optional[str]) -> None:
    """
    Auth 사용자 정보를 public.users 테이블에 동기화.
    - 관리자 페이지의 유저 탭이 users 테이블을 기준으로 동작하므로
      가입/로그인 시점에 id/email/name을 보정한다.
    """
    if not user_id:
        return

    payload = {
        "id": user_id,
        "email": email,
        "name": _safe_name(name, email),
    }
    try:
        supabase_service.get_admin_client().table("users").upsert(payload, on_conflict="id").execute()
    except Exception:
        # 일부 환경에서는 name 컬럼이 없을 수 있어 fallback
        fallback = {"id": user_id, "email": email}
        try:
            supabase_service.get_admin_client().table("users").upsert(fallback, on_conflict="id").execute()
        except Exception as e:
            print(f"[auth] users 동기화 실패: user_id={user_id}, error={e}")


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
        auth_client = _auth_client()
        response = auth_client.auth.sign_up({
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

        _sync_user_row(
            user_id=response.user.id,
            email=response.user.email,
            name=response.user.user_metadata.get("name") if response.user.user_metadata else request.name,
        )
        
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
        auth_client = _auth_client()
        response = auth_client.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })
        
        if response.user is None:
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")

        _sync_user_row(
            user_id=response.user.id,
            email=response.user.email,
            name=response.user.user_metadata.get("name") if response.user.user_metadata else None,
        )
        
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
    - is_premium: users 테이블에서 조회
    """
    user_id = user.get("user_id")
    _sync_user_row(
        user_id=user_id,
        email=user.get("email"),
        name=user.get("name"),
    )
    is_premium = False
    
    # users 테이블에서 is_premium 조회
    if user_id:
        try:
            result = supabase_service.client.table("users").select("is_premium").eq("id", user_id).execute()
            if result.data and len(result.data) > 0:
                is_premium = result.data[0].get("is_premium", False)
        except Exception as e:
            print(f"[auth/me] is_premium 조회 실패: {e}")
    
    return {
        "id": user.get("user_id"),
        "email": user.get("email"),
        "name": user.get("name"),
        "created_at": user.get("created_at"),
        "is_premium": is_premium,
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """
    액세스 토큰 갱신
    """
    try:
        auth_client = _auth_client()
        response = auth_client.auth.refresh_session(refresh_token)

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

        auth_client = _auth_client()
        response = auth_client.auth.sign_in_with_oauth({
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


def _parse_created_at(created_at) -> Optional[datetime]:
    """Supabase user.created_at을 datetime으로 변환 (문자열 또는 datetime)"""
    if created_at is None:
        return None
    if isinstance(created_at, datetime):
        return created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


@router.post("/oauth/callback")
async def oauth_callback(request: OAuthCallbackRequest):
    """
    OAuth 코드를 토큰으로 교환.
    is_new_user: 이번 로그인이 신규 가입(최초 1회)인 경우 True (GA4 sign_up용)
    """
    try:
        auth_client = _auth_client()
        response = auth_client.auth.exchange_code_for_session({
            "auth_code": request.code
        })

        if response.session is None:
            raise HTTPException(status_code=400, detail="토큰 교환 실패")

        user = response.user
        _sync_user_row(
            user_id=user.id,
            email=user.email,
            name=user.user_metadata.get("name") or user.user_metadata.get("full_name"),
        )
        created_at = getattr(user, "created_at", None)
        created_dt = _parse_created_at(created_at)
        now = datetime.now(timezone.utc)
        is_new_user = False
        if created_dt:
            age_seconds = (now - created_dt).total_seconds()
            is_new_user = age_seconds < 90  # 방금 생성된 사용자 = 신규 가입

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "is_new_user": is_new_user,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.user_metadata.get("name") or user.user_metadata.get("full_name") or (user.email.split("@")[0] if user.email else ""),
                "avatar_url": user.user_metadata.get("avatar_url"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth 콜백 처리 실패: {str(e)}")

