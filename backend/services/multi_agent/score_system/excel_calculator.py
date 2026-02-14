"""
엑셀 환산점수 계산기 - 100% 재현
2026학년도 수능 실채점 기준
"""
import json
import os
from typing import Dict, Optional, Tuple

# 데이터 파일 경로
DATA_DIR = os.path.dirname(os.path.abspath(__file__)) + '/data'

# 전역 데이터 캐시
_formulas = None
_deductions = None
_conversion_tables = None


def load_data():
    """데이터 파일 로드"""
    global _formulas, _deductions, _conversion_tables
    
    if _formulas is None:
        with open(f'{DATA_DIR}/formulas_final.json', 'r', encoding='utf-8') as f:
            _formulas = json.load(f)
    
    if _deductions is None:
        with open(f'{DATA_DIR}/deductions_final.json', 'r', encoding='utf-8') as f:
            _deductions = json.load(f)
    
    if _conversion_tables is None:
        with open(f'{DATA_DIR}/conversion_tables_final.json', 'r', encoding='utf-8') as f:
            _conversion_tables = json.load(f)
    
    return _formulas, _deductions, _conversion_tables


def get_conversion_table_key(formula_id: str, is_science: bool) -> str:
    """
    공식 ID에 따른 변환표 키 반환
    
    변환코드:
    - 1: 서울대 (변환표 사용 안함)
    - 4: 연세대/고려대/서강대 등 (변환표 사용)
    """
    formulas, _, _ = load_data()
    formula = formulas.get(str(formula_id))
    
    if not formula:
        return None
    
    name = formula['name'].lower()
    subject_type = 'gwa' if is_science else 'sa'
    
    # 대학별 변환표 매핑
    if '연세' in name:
        return f'yonsei_{subject_type}'
    elif '고려' in name:
        return f'korea_{subject_type}'
    elif '서강' in name:
        if '자연' in name:
            return f'sogang_natural_{subject_type}'
        elif '인문' in name or '통합' in name or '적용' in name:
            return f'sogang_humanities_{subject_type}'
        else:
            return f'sogang_free_{subject_type}'
    
    return None


def convert_to_standard(percentile: int, table_key: str) -> float:
    """백분위를 변환표준점수로 변환"""
    _, _, conversion_tables = load_data()
    
    if table_key not in conversion_tables:
        return percentile  # 변환표 없으면 그대로 반환
    
    table = conversion_tables[table_key]
    
    # 정확한 백분위 값이 있으면 반환
    if str(percentile) in table:
        return table[str(percentile)]
    if percentile in table:
        return table[percentile]
    
    # 없으면 가장 가까운 값 사용
    pct_keys = sorted([int(k) for k in table.keys()], reverse=True)
    for pct in pct_keys:
        if pct <= percentile:
            return table[pct] if pct in table else table[str(pct)]
    
    return percentile


def calculate_score(
    formula_id: str,
    korean_std: float,
    korean_pct: float,
    math_std: float,
    math_pct: float,
    tamgu1_std: float,
    tamgu1_pct: float,
    tamgu2_std: float,
    tamgu2_pct: float,
    english_grade: int,
    history_grade: int,
    is_science: bool = True,  # 과탐 여부
) -> Tuple[Optional[float], Dict]:
    """
    엑셀 수식 100% 재현 계산기
    
    Args:
        formula_id: 공식 ID (1~282)
        korean_std: 국어 표준점수
        korean_pct: 국어 백분위
        math_std: 수학 표준점수
        math_pct: 수학 백분위
        tamgu1_std: 탐구1 표준점수
        tamgu1_pct: 탐구1 백분위
        tamgu2_std: 탐구2 표준점수
        tamgu2_pct: 탐구2 백분위
        english_grade: 영어 등급 (1~9)
        history_grade: 한국사 등급 (1~9)
        is_science: 과탐 여부 (True=과탐, False=사탐)
    
    Returns:
        (최종점수, 상세정보)
    """
    formulas, deductions, _ = load_data()
    
    fid = str(formula_id)
    if fid not in formulas:
        return None, {'error': f'공식 ID {fid} 없음'}
    
    formula = formulas[fid]
    deduction = deductions.get(fid, {'english': [0]*9, 'history': [0]*9})
    
    # 반영방법에 따른 점수 선택
    # 1=표준점수, 2=백분위, 4=변환표준점수, 9=등급, 12=표준점수변환
    
    # 국어 점수
    if formula['koreanType'] == 1:
        korean_score = korean_std
    elif formula['koreanType'] == 2:
        korean_score = korean_pct
    else:
        korean_score = korean_std
    
    # 수학 점수
    if formula['mathType'] == 1:
        math_score = math_std
    elif formula['mathType'] == 2:
        math_score = math_pct
    else:
        math_score = math_std
    
    # 탐구 점수 (변환표준점수 사용 여부)
    if formula['tamgu1Type'] == 4:
        # 변환표준점수 사용
        table_key = get_conversion_table_key(fid, is_science)
        if table_key:
            tamgu1_score = convert_to_standard(int(tamgu1_pct), table_key)
            tamgu2_score = convert_to_standard(int(tamgu2_pct), table_key)
        else:
            tamgu1_score = tamgu1_std
            tamgu2_score = tamgu2_std
    elif formula['tamgu1Type'] == 1:
        tamgu1_score = tamgu1_std
        tamgu2_score = tamgu2_std
    elif formula['tamgu1Type'] == 2:
        tamgu1_score = tamgu1_pct
        tamgu2_score = tamgu2_pct
    else:
        tamgu1_score = tamgu1_std
        tamgu2_score = tamgu2_std
    
    # 계수 적용
    korean_final = korean_score * formula['koreanCoef']
    math_final = math_score * formula['mathCoef']
    tamgu1_final = tamgu1_score * formula['tamgu1Coef']
    tamgu2_final = tamgu2_score * formula['tamgu2Coef']
    
    # 영어 점수 (등급별 가산/감점)
    eng_idx = max(0, min(8, english_grade - 1))
    english_final = deduction['english'][eng_idx]
    
    # 한국사 점수 (등급별 가산/감점)
    hist_idx = max(0, min(8, history_grade - 1))
    history_final = deduction['history'][hist_idx]
    
    # 최종 점수 계산
    total = korean_final + math_final + tamgu1_final + tamgu2_final + english_final + history_final
    
    details = {
        'name': formula['name'],
        'maxScore': formula['maxScore'],
        'korean': korean_final,
        'math': math_final,
        'tamgu1': tamgu1_final,
        'tamgu2': tamgu2_final,
        'english': english_final,
        'history': history_final,
        'total': total,
        'inputs': {
            'korean_std': korean_std,
            'korean_pct': korean_pct,
            'math_std': math_std,
            'math_pct': math_pct,
            'tamgu1_std': tamgu1_std,
            'tamgu1_pct': tamgu1_pct,
            'tamgu2_std': tamgu2_std,
            'tamgu2_pct': tamgu2_pct,
            'english_grade': english_grade,
            'history_grade': history_grade,
        },
        'formula': {
            'koreanCoef': formula['koreanCoef'],
            'mathCoef': formula['mathCoef'],
            'tamgu1Coef': formula['tamgu1Coef'],
            'tamgu2Coef': formula['tamgu2Coef'],
            'koreanType': formula['koreanType'],
            'mathType': formula['mathType'],
            'tamgu1Type': formula['tamgu1Type'],
            'conversionCode': formula['conversionCode'],
        }
    }
    
    return total, details


def test_formula(formula_id: str, is_science: bool = True):
    """공식 테스트"""
    # 1등급 수준 테스트 점수
    result, details = calculate_score(
        formula_id=formula_id,
        korean_std=134,
        korean_pct=96,
        math_std=145,
        math_pct=98,
        tamgu1_std=70,
        tamgu1_pct=96,
        tamgu2_std=68,
        tamgu2_pct=94,
        english_grade=1,
        history_grade=1,
        is_science=is_science,
    )
    
    return result, details


if __name__ == '__main__':
    # 테스트
    print("=== 엑셀 계산기 테스트 ===")
    print()
    
    for fid in ['1', '5', '9', '12']:
        result, details = test_formula(fid)
        print(f"[ID {fid}] {details['name']}")
        print(f"  국어: {details['korean']:.2f}")
        print(f"  수학: {details['math']:.2f}")
        print(f"  탐구1: {details['tamgu1']:.2f}")
        print(f"  탐구2: {details['tamgu2']:.2f}")
        print(f"  영어: {details['english']:.2f}")
        print(f"  한국사: {details['history']:.2f}")
        print(f"  총점: {result:.2f} / 만점: {details['maxScore']}")
        print()
