"""
관리자 계정 필터링 유틸리티
- 관리자 계정을 로그, GA4, 분석에서 제외
"""

# 관리자 계정 목록
ADMIN_ACCOUNTS = {
    'herry0515@naver.com',  # 김도균
    '김도균',  # 이름으로도 확인
}

def is_admin_account(user_id: str = None, email: str = None, name: str = None) -> bool:
    """
    관리자 계정 여부 확인
    
    Args:
        user_id: 사용자 ID (UUID)
        email: 이메일
        name: 사용자 이름
    
    Returns:
        bool: 관리자 계정이면 True
    """
    if email and email in ADMIN_ACCOUNTS:
        return True
    if name and name in ADMIN_ACCOUNTS:
        return True
    return False


def should_skip_logging(user_id: str = None, email: str = None, name: str = None) -> bool:
    """
    로깅을 건너뛸지 여부 결정
    - 관리자 계정은 로깅하지 않음
    
    Args:
        user_id: 사용자 ID
        email: 이메일
        name: 사용자 이름
    
    Returns:
        bool: 로깅을 건너뛰면 True
    """
    return is_admin_account(user_id, email, name)
