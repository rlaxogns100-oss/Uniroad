"""
Main Entry Point
통합 실행 및 테스트 코드
"""
import json

from app import process_consult_call, normalize_scores_from_extracted


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("수능 점수 변환 및 입시 컨설팅 시스템")
    print("=" * 60)
    
    # 테스트 케이스 1: 등급만 입력
    print("\n>>> 테스트 케이스 1: 등급만 입력")
    print("-" * 60)
    input_params_1 = {
        "scores": {
            "국어": {"type": "등급", "value": 1},      # 1등급만 입력 -> 표점/백분위 추론 필요
            "수학": {"type": "등급", "value": 2},      # 2등급만 입력
            "탐구1": {"type": "등급", "value": 3},     # 탐구 과목명 없음 -> 디폴트(생윤) 적용
            "영어": {"type": "등급", "value": 1}       # 절대평가
        },
        "target_univ": ["경희대학교"],
        "target_major": ["경영학과"]
    }
    
    print(f"입력 데이터:\n{json.dumps(input_params_1, ensure_ascii=False, indent=2)}")
    
    print("\n>>> 정규화된 성적 데이터:")
    normalized_1 = normalize_scores_from_extracted(input_params_1["scores"])
    print(json.dumps(normalized_1, ensure_ascii=False, indent=2))
    
    print("\n>>> 생성된 컨설팅 프롬프트:")
    result_1 = process_consult_call(input_params_1)
    print(result_1)
    
    # 테스트 케이스 2: 표준점수 입력
    print("\n\n" + "=" * 60)
    print(">>> 테스트 케이스 2: 표준점수 입력")
    print("-" * 60)
    input_params_2 = {
        "scores": {
            "국어": {"type": "표준점수", "value": 135},
            "수학": {"type": "표준점수", "value": 133}
        },
        "target_univ": ["서울대학교"],
        "target_major": ["컴퓨터공학과"]
    }
    
    print(f"입력 데이터:\n{json.dumps(input_params_2, ensure_ascii=False, indent=2)}")
    
    print("\n>>> 정규화된 성적 데이터:")
    normalized_2 = normalize_scores_from_extracted(input_params_2["scores"])
    print(json.dumps(normalized_2, ensure_ascii=False, indent=2))
    
    print("\n>>> 생성된 컨설팅 프롬프트:")
    result_2 = process_consult_call(input_params_2)
    print(result_2)
    
    # 테스트 케이스 3: 원점수 입력
    print("\n\n" + "=" * 60)
    print(">>> 테스트 케이스 3: 원점수 입력")
    print("-" * 60)
    input_params_3 = {
        "scores": {
            "생활과윤리": {"type": "원점수", "value": 47},
            "사회문화": {"type": "원점수", "value": 45}
        },
        "target_univ": ["고려대학교"],
        "target_major": ["경제학과"]
    }
    
    print(f"입력 데이터:\n{json.dumps(input_params_3, ensure_ascii=False, indent=2)}")
    
    print("\n>>> 정규화된 성적 데이터:")
    normalized_3 = normalize_scores_from_extracted(input_params_3["scores"])
    print(json.dumps(normalized_3, ensure_ascii=False, indent=2))
    
    print("\n>>> 생성된 컨설팅 프롬프트:")
    result_3 = process_consult_call(input_params_3)
    print(result_3)
    
    # 테스트 케이스 4: 리버스 서치 (파싱된 입결 데이터 기반, target_univ 비움)
    print("\n\n" + "=" * 60)
    print(">>> 테스트 케이스 4: 리버스 서치 (data/admission_results/*.json 기반)")
    print("-" * 60)
    input_params_4 = {
        "scores": {
            "국어": {"type": "등급", "value": 1},
            "수학": {"type": "등급", "value": 2},
            "영어": {"type": "등급", "value": 1},
            "한국사": {"type": "등급", "value": 1},
            "탐구1": {"type": "등급", "value": 2, "과목명": "생활과윤리"},
            "탐구2": {"type": "등급", "value": 2, "과목명": "사회문화"},
        },
        "target_univ": [],
        "target_major": [],
        "query": "어디 갈 수 있어?",
    }
    print("입력: 전 과목 등급 입력, target_univ 비움 → 리버스 서치 실행")
    result_4 = process_consult_call(input_params_4)
    # 리버스 서치 표만 앞부분 출력
    if "지원 가능 대학 및 학과 분석" in result_4:
        start = result_4.find("### 지원 가능")
        end = result_4.find("\n\n1. 학생 성적", start) if start >= 0 else -1
        section = result_4[start:end] if end > start else result_4[start : start + 1500]
        print("\n>>> 리버스 서치 섹션 (일부):")
        print(section[:2000] + ("..." if len(section) > 2000 else ""))
    else:
        print(result_4[:1500])
    
    print("\n" + "=" * 60)
    print("모든 테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

