"""
애플리케이션 계층: 성적 정규화, 대학별 환산, 컨설팅 프롬프트 생성
"""
from .processor import (
    normalize_scores_from_extracted,
    format_for_prompt,
    process_consult_call,
    get_univ_converted_sections,
)

__all__ = [
    "normalize_scores_from_extracted",
    "format_for_prompt",
    "process_consult_call",
    "get_univ_converted_sections",
]
