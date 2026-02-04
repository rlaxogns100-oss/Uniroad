"""
리버스 서치 엔진: 사용자 환산 점수와 입결 데이터를 비교해 지원 가능 대학·학과 리스트 반환.

v2.0: suneung_calculator 통합 (86개 대학, 2158개 학과 지원)
"""
from typing import Dict, Any, List, Optional
import json
import os
import glob

from .config import ClassificationLabel
from .suneung_calculator import run_suneung_search, classify_by_cutoff


# ============================================================
# 새로운 판정 함수 (컷 점수 기반)
# ============================================================
def classify_by_cutoffs(my_score: float, univ: Dict) -> str:
    """
    컷 점수 기준 판정 (새로운 기준)
    
    판정 기준:
    - 안정: 내 점수 >= safeScore
    - 적정: 내 점수 >= appropriateScore
    - 소신: 내 점수 >= expectedScore
    - 도전: 내 점수 >= challengeScore
    - 어려움: 내 점수 < challengeScore
    """
    safe = univ.get("safeScore") or univ.get("safe_score")
    appropriate = univ.get("appropriateScore") or univ.get("appropriate_score")
    expected = univ.get("expectedScore") or univ.get("expected_score")
    challenge = univ.get("challengeScore") or univ.get("challenge_score")
    
    if safe and my_score >= safe:
        return ClassificationLabel.SAFE
    if appropriate and my_score >= appropriate:
        return ClassificationLabel.APPROPRIATE
    if expected and my_score >= expected:
        return ClassificationLabel.EXPECTED
    if challenge and my_score >= challenge:
        return ClassificationLabel.CHALLENGE
    return ClassificationLabel.DIFFICULT


# ============================================================
# 메인 함수 (새로운 통합 버전)
# ============================================================
def run_reverse_search(
    normalized_scores: Dict[str, Any],
    target_range: List[str] = None,
    target_univ: List[str] = None,
    target_major: List[str] = None,
    target_gun: str = None,
) -> List[Dict[str, Any]]:
    """
    normalized_scores를 입력받아, 지원 가능 학과 리스트를 반환.
    
    v2.0: suneung_calculator 사용 (86개 대학, 2158개 학과 지원)
    
    Args:
        normalized_scores: 정규화된 성적 데이터
        target_range: 필터링할 판정 목록 (예: ["안정", "적정", "소신"])
        target_univ: 특정 대학 필터 (예: ["경북대", "부산대"])
        target_major: 특정 학과 필터 (예: ["컴퓨터공학"])
        target_gun: 군 필터 (예: "가", "나", "다")
    
    Returns:
        결과 리스트
    """
    # suneung_calculator 사용
    results = run_suneung_search(
        normalized_scores=normalized_scores,
        target_univ=target_univ,
        target_major=target_major,
        target_range=target_range,
        target_gun=target_gun,
    )
    
    # 결과 포맷 변환 (기존 형식과 호환)
    formatted_results = []
    for r in results:
        # 이모지 추가된 판정 레이블로 변환
        판정_text = r.get("판정", "")
        if 판정_text == "안정":
            판정_label = ClassificationLabel.SAFE
        elif 판정_text == "적정":
            판정_label = ClassificationLabel.APPROPRIATE
        elif 판정_text == "소신":
            판정_label = ClassificationLabel.EXPECTED
        elif 판정_text == "도전":
            판정_label = ClassificationLabel.CHALLENGE
        else:
            판정_label = ClassificationLabel.DIFFICULT
        
        formatted_results.append({
            "univ": r.get("univ", ""),
            "major": r.get("major", ""),
            "gun": r.get("gun", ""),
            "type": "정시",  # 기본값
            "field": r.get("track", ""),
            "track": r.get("track", ""),
            "my_score": r.get("my_score"),
            "safe_score": r.get("safe_score"),
            "appropriate_score": r.get("appropriate_score"),
            "expected_score": r.get("expected_score"),
            "challenge_score": r.get("challenge_score"),
            # 기존 호환용
            "cut_70_score": r.get("expected_score"),  # 예상컷을 70% 컷으로 매핑
            "판정": 판정_label,
        })
    
    return formatted_results


# ============================================================
# 기존 함수들 (하위 호환성 유지)
# ============================================================
def _get_admission_data_dir() -> str:
    """data/admission_results 절대 경로 반환 (deprecated)"""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "data", "admission_results")


def _load_admission_data(data_dir: str) -> List[Dict[str, Any]]:
    """입결 JSON 파일들을 로드하여 전체 row 리스트 반환 (deprecated)"""
    all_rows = []
    pattern = os.path.join(data_dir, "*.json")
    
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                rows = json.load(f)
            if isinstance(rows, list):
                all_rows.extend(rows)
        except (json.JSONDecodeError, OSError):
            continue
            
    return all_rows
