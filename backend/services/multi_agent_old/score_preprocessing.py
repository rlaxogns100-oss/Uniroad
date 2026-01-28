"""
성적 전처리 유틸리티
- LLM이 추출한 구조화된 성적을 정규화
- Orchestration Agent -> Sub Agents 전달 시 사용
"""

from typing import Dict, Any

# ScoreConverter import
try:
    from services.scoring import ScoreConverter
except ModuleNotFoundError:
    from backend.services.scoring.score_converter import ScoreConverter


def normalize_scores_from_extracted(extracted_scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestration Agent가 추출한 구조화된 성적을 정규화
    
    Args:
        extracted_scores: {
            "국어": {"type": "등급", "value": 1, "선택과목": "화법과작문"},
            "수학": {"type": "등급", "value": 1},
            ...
        }
    
    Returns:
        정규화된 성적 딕셔너리
    """
    if not extracted_scores:
        return {"과목별_성적": {}, "선택과목": {}}
    
    normalized = {
        "과목별_성적": {},
        "선택과목": {}
    }
    
    # ScoreConverter 초기화 (2026 수능 데이터 기반 정확한 변환)
    converter = ScoreConverter()
    
    # 디폴트 선택과목 설정
    DEFAULT_KOREAN_ELECTIVE = "화법과작문"  # 국어 디폴트
    DEFAULT_MATH_ELECTIVE = "확률과통계"    # 수학 디폴트 (인문계 기준)
    DEFAULT_INQUIRY1 = "생활과윤리"         # 탐구1 디폴트 (사회탐구)
    DEFAULT_INQUIRY2 = "사회문화"           # 탐구2 디폴트 (사회탐구)
    
    # 등급별 중간 백분위 (등급 기준 범위의 중간값)
    grade_to_mid_percentile = {
        1: 98,   # 96~100% -> 중간 98%
        2: 92,   # 89~96% -> 중간 92%
        3: 83,   # 77~89% -> 중간 83%
        4: 68,   # 60~77% -> 중간 68%
        5: 50,   # 40~60% -> 중간 50%
        6: 31,   # 23~40% -> 중간 31%
        7: 17,   # 11~23% -> 중간 17%
        8: 7,    # 4~11% -> 중간 7%
        9: 2     # 0~4% -> 중간 2%
    }
    
    for subject, score_info in extracted_scores.items():
        if not isinstance(score_info, dict):
            continue
        
        score_type = score_info.get("type")
        value = score_info.get("value")
        elective = score_info.get("선택과목")
        
        if value is None:
            continue
        
        # 탐구1, 탐구2 → 디폴트 과목으로 매핑
        lookup_subject = subject
        if subject == "탐구1":
            lookup_subject = DEFAULT_INQUIRY1
        elif subject == "탐구2":
            lookup_subject = DEFAULT_INQUIRY2
        
        # 국어/수학 선택과목 디폴트 설정
        if subject == "국어" and not elective:
            elective = DEFAULT_KOREAN_ELECTIVE
        elif subject == "수학" and not elective:
            elective = DEFAULT_MATH_ELECTIVE
        
        # 선택과목 저장
        if elective and subject in ["국어", "수학"]:
            normalized["선택과목"][subject] = elective
        
        # 등급 기반 변환 (ScoreConverter 사용)
        if score_type == "등급":
            grade = int(value)
            
            # 영어/한국사는 백분위 없음 (절대평가)
            if subject in ["영어", "한국사"]:
                normalized["과목별_성적"][subject] = {
                    "등급": grade,
                    "표준점수": None,
                    "백분위": None,
                    "선택과목": elective
                }
            else:
                # 등급 -> 중간 백분위 -> 표준점수 (정확한 2026 수능 데이터 사용)
                mid_percentile = grade_to_mid_percentile.get(grade, 50)
                
                try:
                    # ScoreConverter로 정확한 표준점수 조회 (lookup_subject 사용)
                    result = converter.find_closest_by_percentile(lookup_subject, mid_percentile)
                    
                    if result:
                        normalized["과목별_성적"][subject] = {
                            "등급": grade,
                            "표준점수": result["standard_score"],
                            "백분위": result["percentile"],
                            "선택과목": elective
                        }
                    else:
                        # 변환 실패 시 백분위만 저장
                        normalized["과목별_성적"][subject] = {
                            "등급": grade,
                            "표준점수": None,
                            "백분위": mid_percentile,
                            "선택과목": elective
                        }
                except Exception as e:
                    print(f"⚠️ {subject} 등급 변환 오류 (lookup: {lookup_subject}): {e}")
                    # 변환 실패 시 백분위만 저장
                    normalized["과목별_성적"][subject] = {
                        "등급": grade,
                        "표준점수": None,
                        "백분위": mid_percentile,
                        "선택과목": elective
                    }
        
        # 표준점수 입력 시 -> 백분위, 등급 조회
        elif score_type == "표준점수":
            std_score = int(value)
            
            try:
                result = converter.find_closest_by_standard(subject, std_score)
                
                if result:
                    normalized["과목별_성적"][subject] = {
                        "등급": result["grade"],
                        "표준점수": result["standard_score"],
                        "백분위": result["percentile"],
                        "선택과목": elective
                    }
                else:
                    normalized["과목별_성적"][subject] = {
                        "등급": None,
                        "표준점수": std_score,
                        "백분위": None,
                        "선택과목": elective
                    }
            except Exception as e:
                print(f"⚠️ {subject} 표준점수 변환 오류: {e}")
                normalized["과목별_성적"][subject] = {
                    "등급": None,
                    "표준점수": std_score,
                    "백분위": None,
                    "선택과목": elective
                }
        
        # 백분위 입력 시 -> 표준점수, 등급 조회
        elif score_type == "백분위":
            percentile = int(value)
            
            try:
                # lookup_subject 사용 (탐구1/탐구2 → 디폴트 과목)
                result = converter.find_closest_by_percentile(lookup_subject, percentile)
                
                if result:
                    normalized["과목별_성적"][subject] = {
                        "등급": result["grade"],
                        "표준점수": result["standard_score"],
                        "백분위": result["percentile"],
                        "선택과목": elective
                    }
                else:
                    normalized["과목별_성적"][subject] = {
                        "등급": None,
                        "표준점수": None,
                        "백분위": percentile,
                        "선택과목": elective
                    }
            except Exception as e:
                print(f"⚠️ {subject} 백분위 변환 오류 (lookup: {lookup_subject}): {e}")
                normalized["과목별_성적"][subject] = {
                    "등급": None,
                    "표준점수": None,
                    "백분위": percentile,
                    "선택과목": elective
                }
        
        # 원점수 입력 시 -> 표준점수, 백분위, 등급 조회
        elif score_type == "원점수":
            raw_score = int(value)
            
            # 국어/수학: ScoreConverter 사용 (선택과목 필요)
            if subject in ["국어", "수학"]:
                if not elective:
                    # 선택과목 없으면 기본값 사용
                    elective = "화법과작문" if subject == "국어" else "확률과통계"
                
                try:
                    result = converter.convert_score(subject, raw_score=raw_score, elective=elective)
                    
                    if result:
                        normalized["과목별_성적"][subject] = {
                            "등급": result["grade"],
                            "표준점수": result["standard_score"],
                            "백분위": result["percentile"],
                            "선택과목": elective
                        }
                    else:
                        # 변환 실패 시 원점수만 저장
                        normalized["과목별_성적"][subject] = {
                            "등급": None,
                            "표준점수": None,
                            "백분위": None,
                            "선택과목": elective,
                            "원점수": raw_score
                        }
                except Exception as e:
                    print(f"⚠️ {subject} 원점수 변환 오류: {e}")
                    normalized["과목별_성적"][subject] = {
                        "등급": None,
                        "표준점수": None,
                        "백분위": None,
                        "선택과목": elective,
                        "원점수": raw_score
                    }
            
            # 영어: 절대평가 등급컷으로 변환
            elif subject == "영어":
                # 2026 수능 영어 등급컷 (절대평가)
                english_cuts = {
                    1: 90, 2: 80, 3: 70, 4: 60, 5: 50, 6: 40, 7: 30, 8: 20, 9: 0
                }
                
                grade = 9
                for g, cut in english_cuts.items():
                    if raw_score >= cut:
                        grade = g
                        break
                
                normalized["과목별_성적"][subject] = {
                    "등급": grade,
                    "표준점수": None,
                    "백분위": None,
                    "선택과목": None,
                    "원점수": raw_score
                }
            
            # 탐구 과목: ScoreConverter 사용 (원점수 데이터 있음)
            else:
                # 사회탐구/과학탐구 데이터 확인
                if subject in converter.social_data or subject in converter.science_data:
                    data_dict = converter.social_data if subject in converter.social_data else converter.science_data
                    subject_data = data_dict.get(subject)
                    
                    if subject_data:
                        # 탐구 과목은 50점 만점
                        # 원점수가 50을 초과하면 100점 만점 기준으로 입력된 것으로 간주하고 변환
                        actual_raw_score = raw_score
                        if raw_score > 50:
                            actual_raw_score = int(raw_score * 50 / 100)
                        
                        raw_score_str = str(actual_raw_score)
                        score_info = subject_data.get(raw_score_str)
                        
                        if score_info:
                            # 정확한 데이터 있음
                            normalized["과목별_성적"][subject] = {
                                "등급": score_info["grade"],
                                "표준점수": score_info["std"],
                                "백분위": score_info["perc"],
                                "선택과목": None,
                                "원점수": actual_raw_score
                            }
                        else:
                            # 원점수가 데이터에 없음 → 가장 가까운 값 찾기
                            available_scores = [int(s) for s in subject_data.keys()]
                            closest_score = min(available_scores, key=lambda x: abs(x - actual_raw_score))
                            score_info = subject_data[str(closest_score)]
                            
                            normalized["과목별_성적"][subject] = {
                                "등급": score_info["grade"],
                                "표준점수": score_info["std"],
                                "백분위": score_info["perc"],
                                "선택과목": None,
                                "원점수": actual_raw_score,
                                "추정됨": True,
                                "추정_기준": f"원점수 {actual_raw_score}점 → {closest_score}점 데이터로 추정"
                            }
                    else:
                        # 과목 데이터 없음
                        normalized["과목별_성적"][subject] = {
                            "등급": None,
                            "표준점수": None,
                            "백분위": None,
                            "선택과목": None,
                            "원점수": raw_score
                        }
                else:
                    # 탐구 과목이 아닌 경우 (한국사 등)
                    normalized["과목별_성적"][subject] = {
                        "등급": None,
                        "표준점수": None,
                        "백분위": None,
                        "선택과목": None,
                        "원점수": raw_score
                    }
    
    return normalized


def format_normalized_scores_for_consulting(normalized: Dict[str, Any]) -> str:
    """
    정규화된 성적을 컨설팅 agent용 텍스트로 포맷팅
    
    규칙:
    - 영어는 등급만 표시 (백분위 없음)
    - 탐구 과목은 구체적 과목명 사용
    
    Returns:
        포맷팅된 성적 텍스트
    """
    lines = []
    
    subjects = normalized.get("과목별_성적", {})
    electives = normalized.get("선택과목", {})
    
    # 과목 순서
    order = ["국어", "수학", "영어", "한국사"]
    
    # 주요 과목 먼저
    for subj in order:
        if subj in subjects:
            lines.append(_format_single_subject(subj, subjects[subj], electives))
    
    # 탐구 과목
    for subj, data in subjects.items():
        if subj not in order:
            lines.append(_format_single_subject(subj, data, electives))
    
    return "\n".join(lines) if lines else "성적 정보 없음"


def _format_single_subject(subj: str, data: Dict, electives: Dict) -> str:
    """단일 과목 포맷팅"""
    grade = data.get("등급")
    std = data.get("표준점수")
    pct = data.get("백분위")
    elective = data.get("선택과목") or electives.get(subj)
    
    # 과목명 (선택과목 포함)
    subj_name = f"{subj}({elective})" if elective else subj
    
    # 점수 포맷
    parts = []
    if grade is not None:
        parts.append(f"{grade}등급")
    
    # 영어/한국사는 등급만 표시
    if subj not in ["영어", "한국사"]:
        if std is not None:
            parts.append(f"표준점수 {std}")
        if pct is not None:
            parts.append(f"백분위 {round(pct, 1)}")
    
    score_text = " / ".join(parts) if parts else "정보 없음"
    return f"- {subj_name}: {score_text}"


def build_preprocessed_query(extracted_scores: Dict[str, Any], original_query: str) -> str:
    """
    최종 쿼리 생성: [전처리된 성적] + [원본 쿼리]
    
    Args:
        extracted_scores: Orchestration이 추출한 구조화된 성적
        original_query: 원본 쿼리
    
    Returns:
        전처리된 쿼리 문자열
    """
    if not extracted_scores:
        return original_query
    
    normalized = normalize_scores_from_extracted(extracted_scores)
    formatted = format_normalized_scores_for_consulting(normalized)
    
    return f"""[전처리된 성적]
{formatted}

[원본 쿼리]
{original_query}"""
