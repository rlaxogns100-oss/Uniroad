"""
consult_jungsi 정확도 테스트 스크립트

평가 항목:
1. j_scores 단계에서 선택과목(언매, 사회문화, 물리학2 등)이 올바르게 처리되는지
2. 리버스 서치 과정에서 대학별 환산점수 계산이 올바르게 되는지 (만점 초과 등)
3. 점수가 상식적으로 나오는지 (2등급대가 서울대 합격 등 비정상 케이스)
"""

import json
import sys
import os

# 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.multi_agent.score_system import (
    normalize_scores_from_extracted,
    format_for_prompt,
    run_reverse_search,
)
from services.multi_agent.score_system.suneung_calculator import (
    calculate_score,
    classify_by_cutoff,
    get_all_universities,
    _load_formulas,
)


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_1_score_conversion():
    """
    테스트 1: j_scores 단계에서 선택과목이 올바르게 처리되는지
    """
    print_section("테스트 1: 선택과목 처리 및 점수 변환")
    
    test_cases = [
        {
            "name": "기본 등급 입력 (선택과목 미지정)",
            "input": {
                "국어": {"type": "등급", "value": 2},
                "수학": {"type": "등급", "value": 2},
                "영어": {"type": "등급", "value": 1},
                "한국사": {"type": "등급", "value": 1},
                "탐구1": {"type": "등급", "value": 2},
                "탐구2": {"type": "등급", "value": 2},
            },
            "expected_defaults": {
                "국어_선택": "화법과작문",
                "수학_선택": "확률과통계",
                "탐구1_과목": "생활과윤리",
                "탐구2_과목": "사회문화",
            }
        },
        {
            "name": "선택과목 명시 (언어와매체, 미적분, 물리학2)",
            "input": {
                "국어": {"type": "표준점수", "value": 135, "선택과목": "언어와매체"},
                "수학": {"type": "표준점수", "value": 137, "선택과목": "미적분"},
                "영어": {"type": "등급", "value": 1},
                "한국사": {"type": "등급", "value": 1},
                "탐구1": {"type": "표준점수", "value": 68, "과목명": "물리학2"},
                "탐구2": {"type": "표준점수", "value": 66, "과목명": "화학2"},
            },
            "expected_subjects": {
                "국어_선택": "언어와매체",
                "수학_선택": "미적분",
                "탐구1_과목": "물리학2",
                "탐구2_과목": "화학2",
            }
        },
        {
            "name": "사탐 선택과목 (사회문화, 생활과윤리)",
            "input": {
                "국어": {"type": "등급", "value": 1},
                "수학": {"type": "등급", "value": 1},
                "영어": {"type": "등급", "value": 1},
                "한국사": {"type": "등급", "value": 1},
                "탐구1": {"type": "표준점수", "value": 70, "과목명": "사회문화"},
                "탐구2": {"type": "표준점수", "value": 71, "과목명": "생활과윤리"},
            },
            "expected_subjects": {
                "탐구1_과목": "사회문화",
                "탐구2_과목": "생활과윤리",
            }
        },
    ]
    
    results = []
    for tc in test_cases:
        print(f"\n[케이스] {tc['name']}")
        print(f"  입력: {json.dumps(tc['input'], ensure_ascii=False, indent=4)}")
        
        normalized = normalize_scores_from_extracted(tc['input'])
        print(f"\n  정규화 결과:")
        
        scores = normalized.get("과목별_성적", {})
        for subject, data in scores.items():
            print(f"    {subject}: 과목명={data.get('과목명')}, 선택과목={data.get('선택과목')}, "
                  f"등급={data.get('등급')}, 표준점수={data.get('표준점수')}, 백분위={data.get('백분위')}")
        
        # 검증
        issues = []
        
        # 표준점수가 None이 아닌지 확인 (영어, 한국사 제외)
        for subject in ["국어", "수학", "탐구1", "탐구2"]:
            if subject in scores:
                if scores[subject].get("표준점수") is None:
                    issues.append(f"{subject} 표준점수가 None")
        
        # 선택과목이 올바르게 설정되었는지 확인
        if "expected_defaults" in tc:
            for key, expected in tc["expected_defaults"].items():
                subject, field = key.split("_")
                actual = None
                if field == "선택":
                    actual = normalized.get("선택과목", {}).get(subject)
                elif field == "과목":
                    actual = scores.get(subject, {}).get("과목명")
                
                if actual != expected:
                    issues.append(f"{key}: 예상={expected}, 실제={actual}")
        
        if "expected_subjects" in tc:
            for key, expected in tc["expected_subjects"].items():
                subject, field = key.split("_")
                actual = None
                if field == "선택":
                    actual = normalized.get("선택과목", {}).get(subject) or scores.get(subject, {}).get("선택과목")
                elif field == "과목":
                    actual = scores.get(subject, {}).get("과목명")
                
                if actual != expected:
                    issues.append(f"{key}: 예상={expected}, 실제={actual}")
        
        if issues:
            print(f"\n  ❌ 문제 발견:")
            for issue in issues:
                print(f"    - {issue}")
            results.append({"name": tc["name"], "status": "FAIL", "issues": issues})
        else:
            print(f"\n  ✅ 통과")
            results.append({"name": tc["name"], "status": "PASS", "issues": []})
    
    return results


def test_2_score_calculation():
    """
    테스트 2: 대학별 환산점수 계산이 올바르게 되는지 (만점 초과 등)
    """
    print_section("테스트 2: 대학별 환산점수 계산 검증")
    
    universities = get_all_universities()
    formulas = _load_formulas()
    
    # 테스트 점수 세트
    test_scores = [
        {
            "name": "1등급 최상위권",
            "korean": 140,  # 국어 표준점수
            "math": 137,    # 수학 표준점수
            "tamgu1": 70,   # 탐구1 표준점수
            "tamgu2": 70,   # 탐구2 표준점수
            "english": 1,   # 영어 등급
            "history": 1,   # 한국사 등급
        },
        {
            "name": "2등급 상위권",
            "korean": 130,
            "math": 130,
            "tamgu1": 65,
            "tamgu2": 65,
            "english": 2,
            "history": 1,
        },
        {
            "name": "3등급 중상위권",
            "korean": 120,
            "math": 120,
            "tamgu1": 60,
            "tamgu2": 60,
            "english": 3,
            "history": 2,
        },
    ]
    
    results = []
    issues_found = []
    
    for score_set in test_scores:
        print(f"\n[점수 세트] {score_set['name']}")
        print(f"  국어={score_set['korean']}, 수학={score_set['math']}, "
              f"탐구1={score_set['tamgu1']}, 탐구2={score_set['tamgu2']}, "
              f"영어={score_set['english']}등급, 한국사={score_set['history']}등급")
        
        # 모든 대학에 대해 환산점수 계산
        max_score_issues = []
        calculation_errors = []
        
        for univ in universities[:100]:  # 처음 100개만 테스트
            try:
                my_score = calculate_score(
                    univ,
                    score_set["korean"],
                    score_set["math"],
                    score_set["tamgu1"],
                    score_set["tamgu2"],
                    score_set["english"],
                    score_set["history"],
                )
                
                if my_score is None:
                    continue
                
                # 공식의 maxScore 확인
                formula_id = str(univ.get("formulaId"))
                formula = formulas.get(formula_id, {})
                max_score = formula.get("maxScore", 1000)
                
                # 만점 초과 검사
                if my_score > max_score * 1.1:  # 10% 이상 초과
                    max_score_issues.append({
                        "univ": univ.get("university"),
                        "dept": univ.get("department"),
                        "my_score": my_score,
                        "max_score": max_score,
                        "formula_id": formula_id,
                    })
                
                # 음수 점수 검사
                if my_score < 0:
                    calculation_errors.append({
                        "univ": univ.get("university"),
                        "dept": univ.get("department"),
                        "my_score": my_score,
                        "error": "음수 점수",
                    })
                    
            except Exception as e:
                calculation_errors.append({
                    "univ": univ.get("university"),
                    "dept": univ.get("department"),
                    "error": str(e),
                })
        
        if max_score_issues:
            print(f"\n  ⚠️ 만점 초과 케이스 ({len(max_score_issues)}건):")
            for issue in max_score_issues[:5]:  # 처음 5개만 출력
                print(f"    - {issue['univ']} {issue['dept']}: "
                      f"점수={issue['my_score']}, 만점={issue['max_score']}")
            issues_found.extend(max_score_issues)
        
        if calculation_errors:
            print(f"\n  ❌ 계산 오류 ({len(calculation_errors)}건):")
            for err in calculation_errors[:5]:
                print(f"    - {err['univ']} {err['dept']}: {err.get('error', err.get('my_score'))}")
            issues_found.extend(calculation_errors)
        
        if not max_score_issues and not calculation_errors:
            print(f"\n  ✅ 이상 없음")
    
    # 전체 대학 검사 (1등급 점수로)
    print(f"\n[전체 대학 검사] 총 {len(universities)}개 대학/학과")
    
    score_set = test_scores[0]  # 1등급 점수
    all_max_issues = []
    
    for univ in universities:
        try:
            my_score = calculate_score(
                univ,
                score_set["korean"],
                score_set["math"],
                score_set["tamgu1"],
                score_set["tamgu2"],
                score_set["english"],
                score_set["history"],
            )
            
            if my_score is None:
                continue
            
            formula_id = str(univ.get("formulaId"))
            formula = formulas.get(formula_id, {})
            max_score = formula.get("maxScore", 1000)
            
            if my_score > max_score * 1.1:
                all_max_issues.append({
                    "univ": univ.get("university"),
                    "dept": univ.get("department"),
                    "my_score": my_score,
                    "max_score": max_score,
                })
        except:
            pass
    
    if all_max_issues:
        print(f"\n  ⚠️ 전체 중 만점 초과 케이스: {len(all_max_issues)}건")
        results.append({"name": "만점 초과 검사", "status": "WARN", "count": len(all_max_issues)})
    else:
        print(f"\n  ✅ 전체 대학 만점 초과 없음")
        results.append({"name": "만점 초과 검사", "status": "PASS", "count": 0})
    
    return results, issues_found


def test_3_realistic_results():
    """
    테스트 3: 점수가 상식적으로 나오는지 검증
    - 2등급대가 서울대 합격?
    - 3등급이 이화여대를 높은 점수차로 합격?
    """
    print_section("테스트 3: 상식적인 결과 검증")
    
    test_cases = [
        {
            "name": "케이스 A: 전과목 2등급 (상위권)",
            "scores": {
                "국어": {"type": "등급", "value": 2},
                "수학": {"type": "등급", "value": 2},
                "영어": {"type": "등급", "value": 2},
                "한국사": {"type": "등급", "value": 2},
                "탐구1": {"type": "등급", "value": 2},
                "탐구2": {"type": "등급", "value": 2},
            },
            "should_not_pass": ["서울대", "연세대 의예과", "고려대 의예과"],
            "reasonable_range": ["적정", "소신", "도전", "어려움"],  # 서울대는 이 범위여야 함
        },
        {
            "name": "케이스 B: 전과목 3등급 (중상위권)",
            "scores": {
                "국어": {"type": "등급", "value": 3},
                "수학": {"type": "등급", "value": 3},
                "영어": {"type": "등급", "value": 3},
                "한국사": {"type": "등급", "value": 3},
                "탐구1": {"type": "등급", "value": 3},
                "탐구2": {"type": "등급", "value": 3},
            },
            "should_not_pass": ["서울대", "연세대", "고려대", "서강대", "성균관대", "한양대"],
            "should_not_safe": ["이화여대", "중앙대", "경희대"],  # 안정 판정이면 안됨
        },
        {
            "name": "케이스 C: 전과목 1등급 (최상위권)",
            "scores": {
                "국어": {"type": "등급", "value": 1},
                "수학": {"type": "등급", "value": 1},
                "영어": {"type": "등급", "value": 1},
                "한국사": {"type": "등급", "value": 1},
                "탐구1": {"type": "등급", "value": 1},
                "탐구2": {"type": "등급", "value": 1},
            },
            "should_have_options": True,  # 지원 가능 대학이 있어야 함
        },
        {
            "name": "케이스 D: 전과목 4등급 (중위권)",
            "scores": {
                "국어": {"type": "등급", "value": 4},
                "수학": {"type": "등급", "value": 4},
                "영어": {"type": "등급", "value": 4},
                "한국사": {"type": "등급", "value": 4},
                "탐구1": {"type": "등급", "value": 4},
                "탐구2": {"type": "등급", "value": 4},
            },
            "should_not_pass": ["서울대", "연세대", "고려대", "서강대", "성균관대", "한양대", 
                               "이화여대", "중앙대", "경희대", "한국외대"],
        },
    ]
    
    results = []
    
    for tc in test_cases:
        print(f"\n[케이스] {tc['name']}")
        
        # 성적 정규화
        normalized = normalize_scores_from_extracted(tc["scores"])
        print(f"  정규화된 성적:")
        scores = normalized.get("과목별_성적", {})
        for subject in ["국어", "수학", "영어", "한국사", "탐구1", "탐구2"]:
            if subject in scores:
                data = scores[subject]
                print(f"    {subject}: 등급={data.get('등급')}, 표준점수={data.get('표준점수')}")
        
        # 리버스 서치 실행
        reverse_results = run_reverse_search(normalized)
        
        print(f"\n  리버스 서치 결과: 총 {len(reverse_results)}개 학과")
        
        # 판정별 분류
        by_range = {}
        for r in reverse_results:
            판정 = r.get("판정", "")
            # 이모지 제거
            판정_clean = 판정.replace("🟢 ", "").replace("🟡 ", "").replace("🟠 ", "").replace("🔴 ", "").replace("⚫ ", "").replace("⬇️ ", "")
            if 판정_clean not in by_range:
                by_range[판정_clean] = []
            by_range[판정_clean].append(r)
        
        print(f"  판정별 분포:")
        for 판정, items in by_range.items():
            print(f"    {판정}: {len(items)}개")
            # 대표 대학 출력
            univs = set(item["univ"] for item in items[:10])
            print(f"      예시: {', '.join(list(univs)[:5])}")
        
        # 검증
        issues = []
        
        # should_not_pass 검증: 해당 대학이 "안정" 또는 "적정"이면 안됨
        if "should_not_pass" in tc:
            for univ_name in tc["should_not_pass"]:
                for r in reverse_results:
                    if univ_name in r.get("univ", ""):
                        판정 = r.get("판정", "")
                        if "안정" in 판정 or "하향" in 판정:
                            issues.append(f"❌ {univ_name}이 '{판정}' 판정 (비정상)")
        
        # should_not_safe 검증: 해당 대학이 "안정"이면 안됨
        if "should_not_safe" in tc:
            for univ_name in tc["should_not_safe"]:
                for r in reverse_results:
                    if univ_name in r.get("univ", ""):
                        판정 = r.get("판정", "")
                        if "안정" in 판정 or "하향" in 판정:
                            issues.append(f"⚠️ {univ_name}이 '{판정}' 판정 (의심)")
        
        # should_have_options 검증
        if tc.get("should_have_options"):
            if len(reverse_results) == 0:
                issues.append("❌ 1등급인데 지원 가능 대학이 없음")
            else:
                # 안정/적정 판정이 있어야 함
                safe_count = len(by_range.get("안정", []))
                appropriate_count = len(by_range.get("적정", []))
                if safe_count + appropriate_count == 0:
                    issues.append("⚠️ 1등급인데 안정/적정 판정이 없음")
        
        if issues:
            print(f"\n  문제 발견:")
            for issue in issues:
                print(f"    {issue}")
            results.append({"name": tc["name"], "status": "FAIL", "issues": issues})
        else:
            print(f"\n  ✅ 상식적인 결과")
            results.append({"name": tc["name"], "status": "PASS", "issues": []})
    
    return results


def test_specific_university_scores():
    """
    특정 대학의 환산점수 상세 검증
    """
    print_section("특정 대학 환산점수 상세 검증")
    
    universities = get_all_universities()
    formulas = _load_formulas()
    
    # 주요 대학 필터
    target_univs = ["서울대", "연세대", "고려대", "서강대", "성균관대", "한양대", "이화여대", "경희대"]
    
    # 1등급 점수
    score_1 = {"korean": 140, "math": 137, "tamgu1": 70, "tamgu2": 70, "english": 1, "history": 1}
    # 2등급 점수
    score_2 = {"korean": 130, "math": 130, "tamgu1": 65, "tamgu2": 65, "english": 2, "history": 1}
    # 3등급 점수
    score_3 = {"korean": 120, "math": 120, "tamgu1": 60, "tamgu2": 60, "english": 3, "history": 2}
    
    for target in target_univs:
        print(f"\n[{target}]")
        
        # 해당 대학의 학과들 찾기
        univ_depts = [u for u in universities if target in u.get("university", "")][:5]
        
        if not univ_depts:
            print(f"  데이터 없음")
            continue
        
        for univ in univ_depts:
            dept = univ.get("department", "")
            formula_id = str(univ.get("formulaId"))
            formula = formulas.get(formula_id, {})
            max_score = formula.get("maxScore", 1000)
            
            print(f"\n  [{dept}] (공식ID: {formula_id}, 만점: {max_score})")
            print(f"    컷 점수: 안정={univ.get('safeScore')}, 적정={univ.get('appropriateScore')}, "
                  f"소신={univ.get('expectedScore')}, 도전={univ.get('challengeScore')}")
            
            for name, score in [("1등급", score_1), ("2등급", score_2), ("3등급", score_3)]:
                my_score = calculate_score(
                    univ,
                    score["korean"], score["math"],
                    score["tamgu1"], score["tamgu2"],
                    score["english"], score["history"]
                )
                
                if my_score is None:
                    print(f"    {name}: 계산 불가")
                    continue
                
                판정 = classify_by_cutoff(my_score, univ)
                print(f"    {name}: 환산점수={my_score:.2f}, 판정={판정}")


def main():
    print("\n" + "=" * 80)
    print("  consult_jungsi 정확도 테스트")
    print("=" * 80)
    
    all_results = []
    
    # 테스트 1: 선택과목 처리
    results_1 = test_1_score_conversion()
    all_results.extend(results_1)
    
    # 테스트 2: 환산점수 계산
    results_2, issues_2 = test_2_score_calculation()
    all_results.extend(results_2)
    
    # 테스트 3: 상식적인 결과
    results_3 = test_3_realistic_results()
    all_results.extend(results_3)
    
    # 특정 대학 상세 검증
    test_specific_university_scores()
    
    # 최종 요약
    print_section("최종 요약")
    
    pass_count = sum(1 for r in all_results if r.get("status") == "PASS")
    fail_count = sum(1 for r in all_results if r.get("status") == "FAIL")
    warn_count = sum(1 for r in all_results if r.get("status") == "WARN")
    
    print(f"\n총 {len(all_results)}개 테스트")
    print(f"  ✅ PASS: {pass_count}")
    print(f"  ❌ FAIL: {fail_count}")
    print(f"  ⚠️ WARN: {warn_count}")
    
    if fail_count > 0:
        print("\n실패한 테스트:")
        for r in all_results:
            if r.get("status") == "FAIL":
                print(f"  - {r['name']}")
                for issue in r.get("issues", []):
                    print(f"    {issue}")
    
    return all_results


if __name__ == "__main__":
    main()
