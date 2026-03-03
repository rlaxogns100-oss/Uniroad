"""
환산점수 공식 테스트 - 20개 테스트 케이스
엑셀 추출 데이터 검증
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.multi_agent.score_system.suneung_calculator import (
    calculate_score, _load_formulas, _load_deductions, _load_universities
)

def test_formula_calculation():
    """20개 테스트 케이스 실행"""
    formulas = _load_formulas()
    deductions = _load_deductions()
    universities = _load_universities()
    
    # 테스트용 표준점수 (1등급 수준)
    TOP_SCORES = {"korean": 134, "math": 145, "tamgu1": 70, "tamgu2": 68}
    # 테스트용 표준점수 (2등급 수준)
    MID_SCORES = {"korean": 125, "math": 135, "tamgu1": 65, "tamgu2": 63}
    # 테스트용 표준점수 (3등급 수준)
    LOW_SCORES = {"korean": 115, "math": 125, "tamgu1": 58, "tamgu2": 56}
    
    test_cases = [
        # 1. 서울대 자연A (ID 1) - 만점 600
        {"name": "서울대 자연A", "formula_id": "1", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 600},
        # 2. 연세대 자연 (ID 5) - 만점 950
        {"name": "연세대 자연", "formula_id": "5", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 950},
        # 3. 고려대 자연 (ID 9) - 만점 1000
        {"name": "고려대 자연", "formula_id": "9", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 1000},
        # 4. 서강대 자연 (ID 12) - 만점 600
        {"name": "서강대 자연", "formula_id": "12", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 600},
        # 5. 한양대 자연 (ID 26) - 만점 900
        {"name": "한양대 자연", "formula_id": "26", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 900},
        # 6. 중앙대 자연 (ID 30) - 만점 1000
        {"name": "중앙대 자연", "formula_id": "30", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 1000},
        # 7. 경희대 자연 (ID 33) - 만점 600
        {"name": "경희대 자연", "formula_id": "33", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 600},
        # 8. 이화여대 자연 (ID 88) - 만점 1000
        {"name": "이화여대 자연", "formula_id": "88", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 1000},
        # 9. 성균관대 자연가 (ID 273) - 만점 1000
        {"name": "성균관대 자연가", "formula_id": "273", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 1000},
        # 10. 충북대 통합 (ID 227) - 만점 200
        {"name": "충북대 통합", "formula_id": "227", "scores": TOP_SCORES, "eng": 1, "hist": 1, "expected_max": 200},
        
        # 11-15: 2등급 수준 테스트
        {"name": "서울대 자연A (2등급)", "formula_id": "1", "scores": MID_SCORES, "eng": 2, "hist": 2, "expected_max": 600},
        {"name": "연세대 자연 (2등급)", "formula_id": "5", "scores": MID_SCORES, "eng": 2, "hist": 2, "expected_max": 950},
        {"name": "고려대 자연 (2등급)", "formula_id": "9", "scores": MID_SCORES, "eng": 2, "hist": 2, "expected_max": 1000},
        {"name": "한양대 자연 (2등급)", "formula_id": "26", "scores": MID_SCORES, "eng": 2, "hist": 2, "expected_max": 900},
        {"name": "성균관대 자연가 (2등급)", "formula_id": "273", "scores": MID_SCORES, "eng": 2, "hist": 2, "expected_max": 1000},
        
        # 16-20: 3등급 수준 테스트
        {"name": "서울대 자연A (3등급)", "formula_id": "1", "scores": LOW_SCORES, "eng": 3, "hist": 3, "expected_max": 600},
        {"name": "연세대 자연 (3등급)", "formula_id": "5", "scores": LOW_SCORES, "eng": 3, "hist": 3, "expected_max": 950},
        {"name": "고려대 자연 (3등급)", "formula_id": "9", "scores": LOW_SCORES, "eng": 3, "hist": 3, "expected_max": 1000},
        {"name": "중앙대 자연 (3등급)", "formula_id": "30", "scores": LOW_SCORES, "eng": 3, "hist": 3, "expected_max": 1000},
        {"name": "충북대 통합 (3등급)", "formula_id": "227", "scores": LOW_SCORES, "eng": 3, "hist": 3, "expected_max": 200},
    ]
    
    print("=" * 80)
    print("환산점수 공식 테스트 (20개 케이스)")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    for i, tc in enumerate(test_cases, 1):
        formula = formulas.get(tc["formula_id"])
        if not formula:
            print(f"[{i}] {tc['name']}: ❌ 공식 없음")
            failed += 1
            continue
        
        # 가상 대학 객체 생성
        univ = {"formulaId": tc["formula_id"]}
        
        score = calculate_score(
            univ,
            tc["scores"]["korean"],
            tc["scores"]["math"],
            tc["scores"]["tamgu1"],
            tc["scores"]["tamgu2"],
            tc["eng"],
            tc["hist"]
        )
        
        if score is None:
            print(f"[{i}] {tc['name']}: ❌ 계산 실패")
            failed += 1
            continue
        
        max_score = tc["expected_max"]
        overflow = score > max_score
        overflow_pct = ((score - max_score) / max_score * 100) if overflow else 0
        
        # 결과 출력
        status = "❌ 만점초과" if overflow else "✅ 정상"
        print(f"[{i}] {tc['name']}")
        print(f"    공식: {formula['name']}, 만점: {max_score}")
        print(f"    계산점수: {score:.2f} ({status})")
        if overflow:
            print(f"    초과율: {overflow_pct:.1f}%")
            failed += 1
        else:
            passed += 1
        
        # 상세 계산 내역
        ded = deductions.get(tc["formula_id"], {})
        eng_val = ded.get("english", [0]*9)[tc["eng"]-1] if ded.get("english") else 0
        hist_val = ded.get("history", [0]*9)[tc["hist"]-1] if ded.get("history") else 0
        
        kor_score = tc["scores"]["korean"] * formula.get("koreanCoef", 0)
        math_score = tc["scores"]["math"] * formula.get("mathCoef", 0)
        tamgu_coef = formula.get("tamguCoef", 0) or 0
        tamgu_bonus = formula.get("tamguBonus", 0) or 0
        t1_score = tc["scores"]["tamgu1"] * tamgu_coef + tamgu_bonus
        t2_score = tc["scores"]["tamgu2"] * tamgu_coef + tamgu_bonus
        
        print(f"    내역: 국어={kor_score:.1f}, 수학={math_score:.1f}, 탐구1={t1_score:.1f}, 탐구2={t2_score:.1f}, 영어={eng_val}, 한국사={hist_val}")
        print()
    
    print("=" * 80)
    print(f"결과: {passed}/20 통과, {failed}/20 실패")
    print("=" * 80)
    
    return passed, failed

if __name__ == "__main__":
    test_formula_calculation()
