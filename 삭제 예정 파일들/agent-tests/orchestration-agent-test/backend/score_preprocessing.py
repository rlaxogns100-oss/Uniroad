"""
성적 전처리 유틸리티
- LLM이 추출한 구조화된 성적을 정규화
"""

from typing import Dict, Any


def normalize_scores_from_extracted(extracted_scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestration Agent가 추출한 구조화된 성적을 정규화
    """
    if not extracted_scores:
        return {"과목별_성적": {}, "선택과목": {}}
    
    normalized = {
        "과목별_성적": {},
        "선택과목": {}
    }
    
    # 등급별 대략적인 백분위
    grade_to_percentile = {
        1: 98, 2: 92, 3: 83, 4: 68, 5: 50,
        6: 31, 7: 17, 8: 7, 9: 2
    }
    
    for subject, score_info in extracted_scores.items():
        if not isinstance(score_info, dict):
            continue
        
        score_type = score_info.get("type")
        value = score_info.get("value")
        elective = score_info.get("선택과목")
        
        if value is None:
            continue
        
        # 선택과목 저장
        if elective and subject in ["국어", "수학"]:
            normalized["선택과목"][subject] = elective
        
        # 등급 기반 변환
        if score_type == "등급":
            grade = int(value)
            percentile = grade_to_percentile.get(grade, 50)
            
            # 영어/한국사는 백분위 없음
            if subject in ["영어", "한국사"]:
                normalized["과목별_성적"][subject] = {
                    "등급": grade,
                    "표준점수": None,
                    "백분위": None,
                    "선택과목": elective
                }
            else:
                # 간단한 표준점수 추정
                if subject in ["국어", "수학"]:
                    std_score = 145 - (grade - 1) * 5
                else:
                    std_score = 70 - (grade - 1) * 3
                
                normalized["과목별_성적"][subject] = {
                    "등급": grade,
                    "표준점수": std_score,
                    "백분위": percentile,
                    "선택과목": elective
                }
        
        elif score_type in ["표준점수", "백분위"]:
            normalized["과목별_성적"][subject] = {
                "등급": None,
                "표준점수": int(value) if score_type == "표준점수" else None,
                "백분위": int(value) if score_type == "백분위" else None,
                "선택과목": elective
            }
    
    return normalized


def format_normalized_scores_for_consulting(normalized: Dict[str, Any]) -> str:
    """정규화된 성적을 텍스트로 포맷팅"""
    lines = []
    
    subjects = normalized.get("과목별_성적", {})
    electives = normalized.get("선택과목", {})
    
    order = ["국어", "수학", "영어", "한국사"]
    
    for subj in order:
        if subj in subjects:
            lines.append(_format_single_subject(subj, subjects[subj], electives))
    
    for subj, data in subjects.items():
        if subj not in order:
            lines.append(_format_single_subject(subj, data, electives))
    
    return "\n".join(lines) if lines else "성적 정보 없음"


def _format_single_subject(subj: str, data: Dict, electives: Dict) -> str:
    grade = data.get("등급")
    std = data.get("표준점수")
    pct = data.get("백분위")
    elective = data.get("선택과목") or electives.get(subj)
    
    subj_name = f"{subj}({elective})" if elective else subj
    
    parts = []
    if grade is not None:
        parts.append(f"{grade}등급")
    
    if subj not in ["영어", "한국사"]:
        if std is not None:
            parts.append(f"표준점수 {std}")
        if pct is not None:
            parts.append(f"백분위 {round(pct, 1)}")
    
    score_text = " / ".join(parts) if parts else "정보 없음"
    return f"- {subj_name}: {score_text}"


def build_preprocessed_query(extracted_scores: Dict[str, Any], original_query: str) -> str:
    """최종 쿼리 생성"""
    if not extracted_scores:
        return original_query
    
    normalized = normalize_scores_from_extracted(extracted_scores)
    formatted = format_normalized_scores_for_consulting(normalized)
    
    return f"""[전처리된 성적]
{formatted}

[원본 쿼리]
{original_query}"""
