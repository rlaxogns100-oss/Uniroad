"""
Score System: 수능 점수 변환 및 대학별 환산점수 계산

v2.0: suneung_calculator 통합 (86개 대학, 2158개 학과 지원)
"""
from .converter import ScoreConverter
from .processor import (
    normalize_scores_from_extracted,
    format_for_prompt,
    process_consult_call,
    get_univ_converted_sections,
)
from .suneung_calculator import (
    calculate_score,
    classify_by_cutoff,
    run_suneung_search,
    get_all_universities,
    get_university_count,
)
from .search_engine import run_reverse_search

__all__ = [
    # 기존 함수
    "ScoreConverter",
    "normalize_scores_from_extracted",
    "format_for_prompt",
    "process_consult_call",
    "get_univ_converted_sections",
    # 새로운 통합 계산기
    "calculate_score",
    "classify_by_cutoff",
    "run_suneung_search",
    "run_reverse_search",
    "get_all_universities",
    "get_university_count",
]
