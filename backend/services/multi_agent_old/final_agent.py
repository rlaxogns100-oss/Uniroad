"""
Final Agent 더미 모듈
- chat.py의 set_log_callback 호출을 위한 호환성 유지
"""

# 로그 콜백 (현재는 미사용)
_log_callback = None


def set_log_callback(callback):
    """로그 콜백 설정"""
    global _log_callback
    _log_callback = callback
