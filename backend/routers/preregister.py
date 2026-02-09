"""
사전신청 API
- PRO 2개월 무료 사전신청 처리
- 전화번호당 1회만 신청 가능
- 시크릿 코드 생성 및 저장
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import Optional
import random
import re
from datetime import datetime

from services.supabase_client import SupabaseService

router = APIRouter(prefix="/api/preregister", tags=["preregister"])


class PreregisterRequest(BaseModel):
    phone: str  # 전화번호 (하이픈 포함 가능)
    grade: str  # 학년 (예비고3, N수생, 예비고2, 예비고1, 기타-학부모, 기타-교사 등)
    user_id: Optional[str] = None  # 로그인한 경우 사용자 ID
    user_name: Optional[str] = None  # 로그인한 경우 사용자 이름
    
    @validator('phone')
    def validate_phone(cls, v):
        # 숫자만 추출
        digits = re.sub(r'\D', '', v)
        if len(digits) != 11 or not digits.startswith('010'):
            raise ValueError('올바른 휴대폰 번호를 입력해주세요 (010-XXXX-XXXX)')
        return digits  # 숫자만 저장


class PreregisterResponse(BaseModel):
    success: bool
    secret_code: Optional[str] = None
    message: str


def generate_secret_code(phone: str) -> str:
    """
    시크릿 코드 생성
    형식: UR-PRO-XXXX00 (XXXX = 전화번호 뒷자리 4개, 00 = 2자리 난수)
    """
    last_four = phone[-4:]
    random_two = str(random.randint(10, 99))
    return f"UR-PRO-{last_four}{random_two}"


@router.post("", response_model=PreregisterResponse)
async def preregister(request: PreregisterRequest):
    """
    사전신청 처리
    - 전화번호당 1회만 신청 가능
    - 시크릿 코드 생성 및 반환
    """
    supabase = SupabaseService.get_client()
    
    # 1. 이미 신청한 전화번호인지 확인
    existing = supabase.table("preregistrations").select("*").eq("phone", request.phone).execute()
    
    if existing.data and len(existing.data) > 0:
        # 이미 신청한 경우 기존 코드 반환
        return PreregisterResponse(
            success=False,
            secret_code=existing.data[0].get("secret_code"),
            message="이미 신청하셨습니다. 기존 시크릿 코드를 확인해주세요."
        )
    
    # 2. 시크릿 코드 생성
    secret_code = generate_secret_code(request.phone)
    
    # 3. 코드 중복 확인 (매우 드물지만 확인)
    code_check = supabase.table("preregistrations").select("id").eq("secret_code", secret_code).execute()
    while code_check.data and len(code_check.data) > 0:
        secret_code = generate_secret_code(request.phone)
        code_check = supabase.table("preregistrations").select("id").eq("secret_code", secret_code).execute()
    
    # 4. DB에 저장
    insert_data = {
        "phone": request.phone,
        "grade": request.grade,
        "secret_code": secret_code,
        "user_id": request.user_id,
        "user_name": request.user_name,
        "created_at": datetime.now().isoformat()
    }
    
    try:
        result = supabase.table("preregistrations").insert(insert_data).execute()
        
        if result.data:
            return PreregisterResponse(
                success=True,
                secret_code=secret_code,
                message="사전신청이 완료되었습니다!"
            )
        else:
            raise HTTPException(status_code=500, detail="신청 처리 중 오류가 발생했습니다.")
    except Exception as e:
        print(f"사전신청 오류: {e}")
        raise HTTPException(status_code=500, detail="신청 처리 중 오류가 발생했습니다.")


@router.get("/check/{phone}")
async def check_preregister(phone: str):
    """
    전화번호로 사전신청 여부 확인
    """
    supabase = SupabaseService.get_client()
    
    # 숫자만 추출
    digits = re.sub(r'\D', '', phone)
    
    existing = supabase.table("preregistrations").select("secret_code", "created_at").eq("phone", digits).execute()
    
    if existing.data and len(existing.data) > 0:
        return {
            "registered": True,
            "secret_code": existing.data[0].get("secret_code"),
            "created_at": existing.data[0].get("created_at")
        }
    
    return {"registered": False}
