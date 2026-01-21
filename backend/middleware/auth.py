"""
JWT 인증 미들웨어
Supabase Auth JWT 토큰 검증
"""
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import os
from dotenv import load_dotenv
from services.supabase_client import supabase_service

load_dotenv()

security = HTTPBearer()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    print("⚠️ SUPABASE_JWT_SECRET not set. Using default (not secure for production)")
    SUPABASE_JWT_SECRET = "your-jwt-secret"


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    JWT 토큰 검증 (Supabase 클라이언트 사용)
    
    Returns:
        dict: 디코딩된 토큰 페이로드 (user_id 포함)
    
    Raises:
        HTTPException: 토큰이 유효하지 않을 경우
    """
    token = credentials.credentials
    
    try:
        # Supabase 클라이언트로 토큰 검증
        # supabase_service.client를 사용하면 세션이 공유될 수 있으므로 새 클라이언트 생성
        from supabase import create_client
        from config import settings
        
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        
        # 토큰으로 사용자 정보 가져오기
        response = client.auth.get_user(token)
        
        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid token: no user")
        
        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "role": response.user.app_metadata.get("role", "authenticated"),
        }
    
    except Exception as e:
        # Supabase 클라이언트 검증 실패 시 JWT 직접 검증 시도
        try:
            # 토큰 헤더 확인 (검증 없이)
            header = jwt.get_unverified_header(token)
            alg = header.get("alg", "HS256")
            
            # 알고리즘이 허용된 것인지 확인
            allowed_algorithms = ["HS256", "RS256"]
            if alg not in allowed_algorithms:
                raise HTTPException(status_code=401, detail=f"Invalid token: Algorithm '{alg}' is not allowed. Allowed: {allowed_algorithms}")
            
            # JWT 직접 검증
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=[alg],
                audience="authenticated"
            )
            
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token: no user ID")
            
            return {
                "user_id": user_id,
                "email": payload.get("email"),
                "role": payload.get("role", "authenticated"),
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as jwt_error:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(jwt_error)}")
        except Exception as jwt_error:
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    현재 로그인한 사용자 정보 가져오기
    
    FastAPI Depends에서 사용:
    @app.get("/protected")
    def protected_route(user: dict = Depends(get_current_user)):
        return {"user_id": user["user_id"]}
    """
    return verify_token(credentials)


async def optional_auth(authorization: Optional[str] = None) -> Optional[dict]:
    """
    선택적 인증 (로그인 안 해도 됨)
    
    로그인한 경우 사용자 정보 반환, 아니면 None
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    try:
        token = authorization.split(" ")[1]
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "role": payload.get("role"),
        }
    except:
        return None

