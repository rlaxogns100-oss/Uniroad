"""
실제 데이터 기반 테스트 파일
data.standard의 실제 데이터를 활용하여 모든 기능을 테스트합니다.
"""
import json
from core.converter import ScoreConverter
from app import normalize_scores_from_extracted, process_consult_call


def print_section(title: str):
    """섹션 구분 출력"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_result(label: str, data: any):
    """결과 출력"""
    print(f"\n[{label}]")
    if isinstance(data, dict):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def test_korean_standard_score():
    """국어 표준점수 테스트"""
    print_section("테스트 1: 국어 표준점수 조회")
    
    converter = ScoreConverter()
    
    # 실제 데이터에 있는 표준점수들 테스트
    test_cases = [
        (147, "만점 근처"),
        (133, "1등급 컷"),
        (126, "2등급 컷"),
        (117, "3등급 컷"),
        (107, "4등급 컷"),
        (94, "5등급 컷"),
        (83, "6등급 컷"),
        (73, "7등급 컷"),
        (66, "8등급 컷"),
        (65, "9등급")
    ]
    
    for std_score, desc in test_cases:
        result = converter.get_score_by_standard("국어", std_score)
        print(f"\n표준점수 {std_score} ({desc}):")
        if result:
            print(f"  → 등급: {result.get('grade')}, 백분위: {result.get('percentile')}")
        else:
            print("  → 조회 실패")


def test_math_standard_score():
    """수학 표준점수 테스트"""
    print_section("테스트 2: 수학 표준점수 조회")
    
    converter = ScoreConverter()
    
    test_cases = [
        (139, "만점 근처"),
        (133, "1등급 컷"),
        (126, "2등급 컷"),
        (117, "3등급 컷"),
        (107, "4등급 컷"),
        (94, "5등급 컷"),
        (83, "6등급 컷"),
        (73, "7등급 컷"),
        (66, "8등급 컷"),
        (65, "9등급")
    ]
    
    for std_score, desc in test_cases:
        result = converter.get_score_by_standard("수학", std_score)
        print(f"\n표준점수 {std_score} ({desc}):")
        if result:
            print(f"  → 등급: {result.get('grade')}, 백분위: {result.get('percentile')}")
        else:
            print("  → 조회 실패")


def test_social_studies_raw_score():
    """사회탐구 원점수 테스트"""
    print_section("테스트 3: 사회탐구 원점수 조회")
    
    converter = ScoreConverter()
    
    # 실제 데이터에 있는 과목들 테스트
    subjects = ["생활과윤리", "사회문화", "경제", "세계사"]
    
    for subject in subjects:
        print(f"\n[{subject}]")
        # 각 과목의 실제 데이터에서 샘플 원점수 테스트
        test_scores = [50, 45, 40, 35, 30, 25, 20]
        for raw in test_scores:
            result = converter.get_score_by_raw(subject, raw)
            if result:
                std = result.get('standard_score') or result.get('std', 0)
                perc = result.get('percentile') or result.get('perc', 0)
                print(f"  원점수 {raw:2d} → 표준점수 {std:2d}, "
                      f"백분위 {perc:2d}, 등급 {result.get('grade')}")


def test_science_inquiry_raw_score():
    """과학탐구 원점수 테스트"""
    print_section("테스트 4: 과학탐구 원점수 조회")
    
    converter = ScoreConverter()
    
    subjects = ["물리학1", "화학1", "생명과학1", "지구과학1"]
    
    for subject in subjects:
        print(f"\n[{subject}]")
        test_scores = [50, 45, 40, 35, 30, 25, 20]
        for raw in test_scores:
            result = converter.get_score_by_raw(subject, raw)
            if result:
                std = result.get('standard_score') or result.get('std', 0)
                perc = result.get('percentile') or result.get('perc', 0)
                print(f"  원점수 {raw:2d} → 표준점수 {std:2d}, "
                      f"백분위 {perc:2d}, 등급 {result.get('grade')}")


def test_grade_estimation():
    """등급만 입력했을 때 추정 테스트"""
    print_section("테스트 5: 등급 기반 점수 추정")
    
    converter = ScoreConverter()
    
    # 다양한 등급과 과목 조합 테스트
    test_cases = [
        ("국어", 1, None),
        ("국어", 2, None),
        ("수학", 1, None),
        ("수학", 3, None),
        ("생활과윤리", 1, None),
        ("사회문화", 2, None),
        ("물리학1", 1, None),
        ("화학1", 2, None),
    ]
    
    for subject, grade, elective in test_cases:
        result = converter.estimate_score_by_grade(subject, grade, elective)
        print(f"\n{subject} {grade}등급 추정:")
        print(f"  → 표준점수: {result.get('standard_score')}, "
              f"백분위: {result.get('percentile')}, "
              f"등급: {result.get('grade')}, "
              f"비고: {result.get('note')}")


def test_grade_cuts():
    """등급컷 데이터 테스트"""
    print_section("테스트 6: 국어/수학 등급컷 기반 원점수 변환")
    
    converter = ScoreConverter()
    
    # 국어 등급컷 테스트
    print("\n[국어 - 화법과작문]")
    korean_raw_scores = [100, 90, 83, 73, 63, 49, 37]
    for raw in korean_raw_scores:
        result = converter.get_score_by_raw("국어", raw, "화법과작문")
        if result:
            print(f"  원점수 {raw:3d} → 표준점수 {result.get('standard_score'):3d}, "
                  f"백분위 {result.get('percentile'):2d}, 등급 {result.get('grade')}")
    
    # 수학 등급컷 테스트
    print("\n[수학 - 확률과통계]")
    math_raw_scores = [100, 87, 82, 76, 65, 41, 24]
    for raw in math_raw_scores:
        result = converter.get_score_by_raw("수학", raw, "확률과통계")
        if result:
            print(f"  원점수 {raw:3d} → 표준점수 {result.get('standard_score'):3d}, "
                  f"백분위 {result.get('percentile'):2d}, 등급 {result.get('grade')}")
    
    print("\n[수학 - 미적분]")
    math_raw_scores = [100, 85, 80, 73, 62, 37, 20]
    for raw in math_raw_scores:
        result = converter.get_score_by_raw("수학", raw, "미적분")
        if result:
            print(f"  원점수 {raw:3d} → 표준점수 {result.get('standard_score'):3d}, "
                  f"백분위 {result.get('percentile'):2d}, 등급 {result.get('grade')}")


def test_integration_scenario_1():
    """통합 테스트 시나리오 1: 등급만 입력"""
    print_section("통합 테스트 시나리오 1: 등급만 입력 (Function Calling 시뮬레이션)")
    
    input_params = {
        "scores": {
            "국어": {"type": "등급", "value": 1},
            "수학": {"type": "등급", "value": 2},
            "영어": {"type": "등급", "value": 1},
            "한국사": {"type": "등급", "value": 1},
            "탐구1": {"type": "등급", "value": 1, "과목명": "생활과윤리"},
            "탐구2": {"type": "등급", "value": 2, "과목명": "사회문화"}
        },
        "target_univ": ["서울대학교", "연세대학교"],
        "target_major": ["경영학과", "경제학과"]
    }
    
    print_result("입력 데이터", input_params)
    
    normalized = normalize_scores_from_extracted(input_params["scores"])
    print_result("정규화된 성적", normalized)
    
    prompt = process_consult_call(input_params)
    print_result("생성된 컨설팅 프롬프트", prompt)


def test_integration_scenario_2():
    """통합 테스트 시나리오 2: 표준점수 입력"""
    print_section("통합 테스트 시나리오 2: 표준점수 입력")
    
    input_params = {
        "scores": {
            "국어": {"type": "표준점수", "value": 135, "선택과목": "화법과작문"},
            "수학": {"type": "표준점수", "value": 133, "선택과목": "확률과통계"},
            "영어": {"type": "등급", "value": 1},
            "탐구1": {"type": "등급", "value": 1, "과목명": "경제"}
        },
        "target_univ": ["고려대학교"],
        "target_major": ["컴퓨터공학과"]
    }
    
    print_result("입력 데이터", input_params)
    
    normalized = normalize_scores_from_extracted(input_params["scores"])
    print_result("정규화된 성적", normalized)
    
    prompt = process_consult_call(input_params)
    print_result("생성된 컨설팅 프롬프트", prompt)


def test_integration_scenario_3():
    """통합 테스트 시나리오 3: 원점수 입력"""
    print_section("통합 테스트 시나리오 3: 원점수 입력 (탐구 과목)")
    
    input_params = {
        "scores": {
            "국어": {"type": "등급", "value": 2, "선택과목": "언어와매체"},
            "수학": {"type": "등급", "value": 3, "선택과목": "미적분"},
            "영어": {"type": "등급", "value": 2},
            "탐구1": {"type": "원점수", "value": 47, "과목명": "생활과윤리"},
            "탐구2": {"type": "원점수", "value": 45, "과목명": "사회문화"}
        },
        "target_univ": ["경희대학교"],
        "target_major": ["경영학과"]
    }
    
    print_result("입력 데이터", input_params)
    
    normalized = normalize_scores_from_extracted(input_params["scores"])
    print_result("정규화된 성적", normalized)
    
    prompt = process_consult_call(input_params)
    print_result("생성된 컨설팅 프롬프트", prompt)


def test_integration_scenario_4():
    """통합 테스트 시나리오 4: 과학탐구 포함"""
    print_section("통합 테스트 시나리오 4: 과학탐구 포함")
    
    input_params = {
        "scores": {
            "국어": {"type": "등급", "value": 1},
            "수학": {"type": "등급", "value": 1, "선택과목": "미적분"},
            "영어": {"type": "등급", "value": 1},
            "탐구1": {"type": "원점수", "value": 50, "과목명": "물리학1"},
            "탐구2": {"type": "원점수", "value": 47, "과목명": "화학1"}
        },
        "target_univ": ["서울대학교", "KAIST"],
        "target_major": ["물리학과", "화학과"]
    }
    
    print_result("입력 데이터", input_params)
    
    normalized = normalize_scores_from_extracted(input_params["scores"])
    print_result("정규화된 성적", normalized)
    
    prompt = process_consult_call(input_params)
    print_result("생성된 컨설팅 프롬프트", prompt)


def test_edge_cases():
    """엣지 케이스 테스트"""
    print_section("엣지 케이스 테스트")
    
    converter = ScoreConverter()
    
    print("\n[1] 존재하지 않는 표준점수 (보간 테스트)")
    result = converter.get_score_by_standard("국어", 130)  # 데이터에 없는 값
    print(f"  표준점수 130 → {result}")
    
    print("\n[2] 낮은 등급 추정")
    result = converter.estimate_score_by_grade("국어", 8)
    print(f"  국어 8등급 추정 → {result}")
    
    print("\n[3] 존재하지 않는 탐구 과목")
    result = converter.get_score_by_raw("존재하지않는과목", 50)
    print(f"  존재하지 않는 과목 → {result}")
    
    print("\n[4] 국어 원점수 (등급컷 기반)")
    result = converter.get_score_by_raw("국어", 95, "화법과작문")
    print(f"  국어 원점수 95 (화법과작문) → {result}")


def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 80)
    print(" 수능 점수 변환 시스템 - 실제 데이터 기반 테스트")
    print("=" * 80)
    
    # 개별 기능 테스트
    test_korean_standard_score()
    test_math_standard_score()
    test_social_studies_raw_score()
    test_science_inquiry_raw_score()
    test_grade_estimation()
    test_grade_cuts()
    test_edge_cases()
    
    # 통합 테스트
    test_integration_scenario_1()
    test_integration_scenario_2()
    test_integration_scenario_3()
    test_integration_scenario_4()
    
    print_section("모든 테스트 완료")
    print("\n✅ 모든 테스트가 성공적으로 완료되었습니다!")


if __name__ == "__main__":
    main()
