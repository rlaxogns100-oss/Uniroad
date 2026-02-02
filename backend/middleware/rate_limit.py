"""
Rate Limiting 미들웨어
일일 API 사용량 제한 (로그인 유저 50회, 게스트 10회)
"""
from typing import Optional, Tuple
from datetime import date
from services.supabase_client import supabase_service
from config.constants import RATE_LIMIT_REGISTERED_USER, RATE_LIMIT_GUEST
from config.logging_config import setup_logger

logger = setup_logger('rate_limit')


async def check_and_increment_usage(
    user_id: Optional[str],
    ip_address: str
) -> Tuple[bool, int, int]:
    """
    사용량 체크 및 증가
    
    Args:
        user_id: 로그인 사용자 ID (로그인한 경우)
        ip_address: 요청 IP 주소
    
    Returns:
        (is_allowed, current_count, limit)
        - is_allowed: 요청 허용 여부
        - current_count: 현재 사용 횟수
        - limit: 제한 횟수
    """
    try:
        today = date.today()
        
        # 로그인 유저인지 게스트인지에 따라 제한값 결정
        if user_id:
            limit = RATE_LIMIT_REGISTERED_USER
            identifier_field = "user_id"
            identifier_value = user_id
        else:
            limit = RATE_LIMIT_GUEST
            identifier_field = "ip_address"
            identifier_value = ip_address
        
        # 오늘 날짜의 사용량 조회
        response = supabase_service.client.table("usage_tracking")\
            .select("id, chat_count, last_reset_date")\
            .eq(identifier_field, identifier_value)\
            .eq("last_reset_date", str(today))\
            .execute()
        
        if response.data and len(response.data) > 0:
            # 기존 레코드가 있음
            record = response.data[0]
            record_id = record["id"]
            current_count = record["chat_count"]
            
            # 날짜가 바뀌었는지 체크 (이중 안전장치)
            last_reset = record["last_reset_date"]
            if str(last_reset) != str(today):
                # 날짜가 바뀜 → 카운트 리셋
                logger.info(f"날짜 변경 감지 ({identifier_field}={identifier_value}): {last_reset} → {today}, 카운트 리셋")
                current_count = 0
                
                # 레코드 업데이트
                supabase_service.client.table("usage_tracking")\
                    .update({
                        "chat_count": 1,
                        "last_reset_date": str(today)
                    })\
                    .eq("id", record_id)\
                    .execute()
                
                logger.info(f"✅ Rate Limit 허용 ({identifier_field}={identifier_value}): 1/{limit} (리셋됨)")
                return (True, 1, limit)
            
            # 제한 체크
            if current_count >= limit:
                logger.warning(f"❌ Rate Limit 초과 ({identifier_field}={identifier_value}): {current_count}/{limit}")
                return (False, current_count, limit)
            
            # 카운트 증가
            new_count = current_count + 1
            supabase_service.client.table("usage_tracking")\
                .update({"chat_count": new_count})\
                .eq("id", record_id)\
                .execute()
            
            logger.info(f"✅ Rate Limit 허용 ({identifier_field}={identifier_value}): {new_count}/{limit}")
            return (True, new_count, limit)
        
        else:
            # 신규 레코드 생성
            insert_data = {
                "chat_count": 1,
                "last_reset_date": str(today)
            }
            
            if user_id:
                insert_data["user_id"] = user_id
            else:
                insert_data["ip_address"] = ip_address
            
            supabase_service.client.table("usage_tracking")\
                .insert(insert_data)\
                .execute()
            
            logger.info(f"✅ Rate Limit 허용 ({identifier_field}={identifier_value}): 1/{limit} (신규)")
            return (True, 1, limit)
    
    except Exception as e:
        logger.error(f"Rate Limit 체크 오류: {e}")
        # 오류 시 일단 허용 (서비스 중단 방지)
        return (True, 0, limit if user_id else RATE_LIMIT_GUEST)


def get_client_ip(request) -> str:
    """
    요청에서 실제 클라이언트 IP 추출
    
    Nginx 프록시를 거치는 경우:
    1. X-Real-IP 헤더 (Nginx가 설정)
    2. X-Forwarded-For 헤더의 첫 번째 IP
    3. 직접 연결된 클라이언트 IP
    
    Args:
        request: FastAPI Request 객체
    
    Returns:
        클라이언트 IP 주소
    """
    # 1. X-Real-IP 헤더 (Nginx에서 설정)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 2. X-Forwarded-For 헤더 (프록시 체인)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 첫 번째 IP가 실제 클라이언트 IP
        return forwarded_for.split(",")[0].strip()
    
    # 3. 직접 연결 (개발 환경)
    if request.client:
        return request.client.host
    
    # 4. 최후의 수단
    return "unknown"
