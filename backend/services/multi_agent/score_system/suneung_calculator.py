"""
Suneung Calculator: 86개 대학 통합 환산점수 계산기
- suneung-calculator의 로직을 백엔드로 이식
- 2158개 학과, 267개 공식 지원
"""

import json
import os
from typing import Dict, Any, List, Optional

# 데이터 파일 경로
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 싱글톤 캐시
_universities_cache: Optional[List[Dict]] = None
_formulas_cache: Optional[Dict] = None
_deductions_cache: Optional[Dict] = None


def _load_universities() -> List[Dict]:
    """universities.json 로드 (캐시)"""
    global _universities_cache
    if _universities_cache is None:
        filepath = os.path.join(DATA_DIR, "universities.json")
        with open(filepath, "r", encoding="utf-8") as f:
            _universities_cache = json.load(f)
    return _universities_cache


def _load_formulas() -> Dict:
    """formulas_extracted.json 로드 (캐시)"""
    global _formulas_cache
    if _formulas_cache is None:
        filepath = os.path.join(DATA_DIR, "formulas_extracted.json")
        with open(filepath, "r", encoding="utf-8") as f:
            _formulas_cache = json.load(f)
    return _formulas_cache


def _load_deductions() -> Dict:
    """deduction_tables.json 로드 (캐시)"""
    global _deductions_cache
    if _deductions_cache is None:
        filepath = os.path.join(DATA_DIR, "deduction_tables.json")
        with open(filepath, "r", encoding="utf-8") as f:
            _deductions_cache = json.load(f)
    return _deductions_cache


def calculate_score(
    univ: Dict,
    korean: float,
    math: float,
    tamgu1: float,
    tamgu2: float,
    english: int,
    history: int,
) -> Optional[float]:
    """
    대학별 환산점수 계산
    
    Args:
        univ: 대학/학과 정보 (universities.json의 한 항목)
        korean: 국어 표준점수
        math: 수학 표준점수
        tamgu1: 탐구1 표준점수
        tamgu2: 탐구2 표준점수
        english: 영어 등급 (1-9)
        history: 한국사 등급 (1-9)
    
    Returns:
        환산점수 (float) 또는 None (공식 없음)
    """
    formulas = _load_formulas()
    deductions = _load_deductions()
    
    formula_id = str(univ.get("formulaId"))
    formula = formulas.get(formula_id)
    
    if not formula:
        return None
    
    # 기본 점수 계산 (타입 안전성 확보)
    try:
        korean_coef = float(formula.get("koreanCoef", 0))
        math_coef = float(formula.get("mathCoef", 0))
        
        # tamguCoef가 '자동'인 경우 처리
        tamgu_coef_raw = formula.get("tamguCoef", 0)
        if tamgu_coef_raw == '자동':
            # '자동'인 경우 계산 불가, 0으로 처리 또는 스킵
            tamgu_coef = 0.0
        else:
            tamgu_coef = float(tamgu_coef_raw)
        
        tamgu_bonus = float(formula.get("tamguBonus", 0))
    except (ValueError, TypeError) as e:
        # 변환 실패 시 None 반환
        return None
    
    korean_score = korean * korean_coef
    math_score = math * math_coef
    tamgu1_score = tamgu1 * tamgu_coef + tamgu_bonus
    tamgu2_score = tamgu2 * tamgu_coef + tamgu_bonus
    
    # 영어/한국사 점수 (타입 안전성 확보)
    deduction = deductions.get(formula_id, {})
    english_score = float(deduction.get("englishDeduction", 0))
    
    history_deductions = deduction.get("historyDeductions", [])
    if history_deductions and 1 <= history <= 9:
        history_score = float(history_deductions[history - 1])
    else:
        history_score = 0.0
    
    # 고정 보너스 (타입 안전성 확보)
    fixed_bonus = float(deduction.get("fixedBonus", 0) or 0)
    
    total = korean_score + math_score + tamgu1_score + tamgu2_score + english_score + history_score + fixed_bonus
    
    return round(total, 2)


def classify_by_cutoff(my_score: float, univ: Dict) -> str:
    """
    컷 점수 기준 판정
    
    판정 기준:
    - 안정: 내 점수 >= safeScore
    - 적정: 내 점수 >= appropriateScore
    - 소신: 내 점수 >= expectedScore
    - 도전: 내 점수 >= challengeScore
    - 어려움: 내 점수 < challengeScore
    """
    safe = univ.get("safeScore")
    appropriate = univ.get("appropriateScore")
    expected = univ.get("expectedScore")
    challenge = univ.get("challengeScore")
    
    if safe and my_score >= safe:
        return "안정"
    if appropriate and my_score >= appropriate:
        return "적정"
    if expected and my_score >= expected:
        return "소신"
    if challenge and my_score >= challenge:
        return "도전"
    return "어려움"


def run_suneung_search(
    normalized_scores: Dict[str, Any],
    target_univ: Optional[List[str]] = None,
    target_major: Optional[List[str]] = None,
    target_range: Optional[List[str]] = None,
    target_gun: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    통합 환산점수 계산 및 지원 가능 대학 검색
    
    Args:
        normalized_scores: 정규화된 성적 데이터
            {
                "과목별_성적": {
                    "국어": {"표준점수": 131, "등급": 2, ...},
                    "수학": {"표준점수": 140, ...},
                    "영어": {"등급": 1},
                    "한국사": {"등급": 1},
                    "탐구1": {"표준점수": 68, ...},
                    "탐구2": {"표준점수": 65, ...}
                }
            }
        target_univ: 특정 대학 필터 (예: ["경북대", "부산대"])
        target_major: 특정 학과 필터 (예: ["컴퓨터공학"])
        target_range: 판정 필터 (예: ["안정", "적정"])
        target_gun: 군 필터 (예: "가", "나", "다")
    
    Returns:
        결과 리스트
    """
    universities = _load_universities()
    
    # 점수 추출
    scores = normalized_scores.get("과목별_성적", {})
    
    korean = scores.get("국어", {}).get("표준점수") or 0
    math = scores.get("수학", {}).get("표준점수") or 0
    tamgu1 = scores.get("탐구1", {}).get("표준점수") or 0
    tamgu2 = scores.get("탐구2", {}).get("표준점수") or 0
    english = scores.get("영어", {}).get("등급") or 1
    history = scores.get("한국사", {}).get("등급") or 1
    
    results = []
    
    for univ in universities:
        # 필터 적용
        if target_gun and univ.get("gun") != target_gun:
            continue
        
        if target_univ:
            univ_name = univ.get("university", "")
            # 대학명 정규화: "경북대학교" → "경북대" 매칭
            matched = False
            for target in target_univ:
                # "학교" 제거 후 비교
                target_normalized = target.replace("학교", "")
                if target_normalized in univ_name or univ_name in target:
                    matched = True
                    break
            if not matched:
                continue
        
        if target_major:
            dept = univ.get("department", "")
            # 학과명 유연한 매칭: "컴퓨터공학과" → "컴퓨터"로 변환
            matched = False
            for target in target_major:
                # "과", "부", "학과" 제거 후 핵심 키워드 추출
                target_normalized = target.replace("공학과", "").replace("학과", "").replace("학부", "").replace("과", "")
                if target_normalized in dept or target in dept:
                    matched = True
                    break
            if not matched:
                continue
        
        # 점수 계산
        my_score = calculate_score(univ, korean, math, tamgu1, tamgu2, english, history)
        if my_score is None:
            continue
        
        # 판정
        판정 = classify_by_cutoff(my_score, univ)
        
        # 판정 필터
        if target_range and 판정 not in target_range:
            continue
        
        results.append({
            "univ": univ.get("university", ""),
            "major": univ.get("department", ""),
            "gun": univ.get("gun", ""),
            "track": univ.get("track", ""),
            "my_score": my_score,
            "safe_score": univ.get("safeScore"),
            "appropriate_score": univ.get("appropriateScore"),
            "expected_score": univ.get("expectedScore"),
            "challenge_score": univ.get("challengeScore"),
            "판정": 판정,
            "formula_id": univ.get("formulaId"),
        })
    
    # 점수 높은 순 정렬
    results.sort(key=lambda x: (
        ["안정", "적정", "소신", "도전", "어려움"].index(x["판정"]),
        -x["my_score"]
    ))
    
    return results


def get_all_universities() -> List[Dict]:
    """전체 대학 목록 반환"""
    return _load_universities()


def get_university_count() -> Dict[str, int]:
    """대학/학과 통계"""
    universities = _load_universities()
    
    unique_univs = set(u.get("university") for u in universities)
    gun_counts = {}
    for u in universities:
        gun = u.get("gun", "기타")
        gun_counts[gun] = gun_counts.get(gun, 0) + 1
    
    return {
        "total_departments": len(universities),
        "unique_universities": len(unique_univs),
        "by_gun": gun_counts,
    }
