"""
리버스 서치 엔진: 사용자 환산 점수와 입결 데이터를 비교해 지원 가능 대학·학과 리스트 반환.

data/admission_results/ 내 모든 *.json 파일을 동적 로드하며, 대학별 계산기와 스케일을 적용해
cut_70_score와 비교하고 [안정/적정/소신/상향] 판정을 붙여 반환합니다.
"""
from typing import Dict, Any, List, Optional
import json
import os
import glob

from app.config import THRESHOLDS, ClassificationLabel
from app.score_extractors import (
    extract_score_for_comparison,
    get_extractor,
    SnuExtractor,
)
from app.calculators import (
    calculate_korea_score,
    calculate_khu_score,
    calculate_sogang_score,
    calculate_snu_score,
    calculate_yonsei_score,
)


# ============================================================
# 대학별 계산기 레지스트리
# ============================================================
UNIV_CALCULATOR_MAP = {
    "고려대학교": calculate_korea_score,
    "경희대학교": calculate_khu_score,
    "서강대학교": calculate_sogang_score,
    "서울대학교": calculate_snu_score,
    "연세대학교": calculate_yonsei_score,
}


# ============================================================
# 유틸리티 함수
# ============================================================
def _get_admission_data_dir() -> str:
    """data/admission_results 절대 경로 반환"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "admission_results")


def classify_score(my_score: float, cut: float) -> str:
    """
    내 점수 vs 70% 컷 비교하여 판정 반환.
    
    판정 기준 (config.THRESHOLDS 참조):
    - 내 점수 >= 컷: 안정
    - 내 점수 >= 컷 - 4: 적정
    - 내 점수 >= 컷 - 8: 소신
    - 그 외: 상향
    """
    if my_score >= cut - THRESHOLDS.SAFE:
        return ClassificationLabel.SAFE
    if my_score >= cut - THRESHOLDS.MODERATE:
        return ClassificationLabel.MODERATE
    if my_score >= cut - THRESHOLDS.RISKY:
        return ClassificationLabel.RISKY
    return ClassificationLabel.REACH


def _load_admission_data(data_dir: str) -> List[Dict[str, Any]]:
    """입결 JSON 파일들을 로드하여 전체 row 리스트 반환"""
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


def _calculate_all_scores(
    normalized_scores: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """모든 대학의 환산 점수를 계산하여 캐시로 반환"""
    cache = {}
    for univ_name, calc_fn in UNIV_CALCULATOR_MAP.items():
        try:
            result = calc_fn(normalized_scores)
            if isinstance(result, dict):
                cache[univ_name] = result
        except Exception:
            continue
    return cache


def _build_result_item(
    row: Dict[str, Any],
    my_score: float,
    판정: str,
    univ: str,
    score_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """결과 아이템 딕셔너리 생성"""
    item = {
        "univ": univ,
        "major": row.get("major", ""),
        "type": row.get("type", "일반"),
        "field": row.get("field", ""),
        "cut_70_score": row.get("cut_70_score"),
        "total_scale": row.get("total_scale"),
        "my_score": my_score,
        "판정": 판정,
        "recruit_count": row.get("recruit_count"),
        "competition_rate": row.get("competition_rate"),
    }
    
    # 50% 컷이 있으면 포함
    cut_50 = row.get("cut_50_score")
    if cut_50 is not None:
        item["cut_50_score"] = cut_50
    
    # 서울대: 최종점수(raw) 추가
    if univ == "서울대학교":
        extractor = get_extractor(univ)
        if isinstance(extractor, SnuExtractor):
            raw_final = extractor.get_raw_final_score(score_cache[univ])
            if raw_final is not None:
                item["최종점수"] = raw_final
    
    return item


# ============================================================
# 메인 함수
# ============================================================
def run_reverse_search(normalized_scores: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    normalized_scores를 입력받아, 입결 데이터와 비교한 지원 가능 학과 리스트를 반환.

    처리 흐름:
    1. data/admission_results/*.json을 glob으로 모두 로드
    2. 각 대학에 대해 UNIV_CALCULATOR_MAP으로 환산 점수 계산 (캐싱)
    3. 각 row의 type/field/total_scale에 맞게 내 점수 추출 및 스케일 맞춤
    4. cut_70_score와 비교하여 [안정/적정/소신/상향] 판정
    
    Args:
        normalized_scores: 정규화된 점수 딕셔너리
        
    Returns:
        지원 가능 학과 리스트 (각 항목에 판정 포함)
    """
    data_dir = _get_admission_data_dir()
    if not os.path.isdir(data_dir):
        return []

    # 1. 대학별 환산 점수 캐시 생성
    score_cache = _calculate_all_scores(normalized_scores)
    
    # 2. 입결 데이터 로드
    all_rows = _load_admission_data(data_dir)
    
    # 3. 각 row 처리
    results = []
    for row in all_rows:
        if not isinstance(row, dict):
            continue
            
        univ = row.get("univ")
        if not univ or univ not in score_cache:
            continue
            
        cut = row.get("cut_70_score")
        if cut is None:
            continue

        # 점수 추출 (추출기 사용)
        my_score = extract_score_for_comparison(univ, score_cache[univ], row)
        if my_score is None:
            continue

        # 판정
        판정 = classify_score(my_score, cut)
        
        # 결과 아이템 생성
        item = _build_result_item(row, my_score, 판정, univ, score_cache)
        results.append(item)

    return results
