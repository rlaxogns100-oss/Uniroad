"""
Orchestration Agent 더미 모듈
- chat.py의 set_log_callback 호출을 위한 호환성 유지
"""

# 로그 콜백 (현재는 미사용)
_log_callback = None


def set_log_callback(callback):
    """로그 콜백 설정"""
    global _log_callback
    _log_callback = callback


# chat.py에서 임포트하는 상수
AVAILABLE_AGENTS = [
    {"name": "router_agent", "description": "질문을 분석하여 적절한 함수 호출을 결정하는 에이전트"}
]
