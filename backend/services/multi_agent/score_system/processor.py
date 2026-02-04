"""
Application Layer: 성적 전처리 및 프롬프트 생성
LLM의 Function Calling 결과를 처리하고 컨설팅 프롬프트를 생성합니다.

v2.0 변경사항:
- 개별 대학 계산기 (khu, korea, sogang, snu, yonsei) → suneung_calculator로 통합
- 86개 대학, 2158개 학과 지원
- 새로운 판정 기준: 안정/적정/소신/도전/어려움
"""
from typing import Dict, Any, Optional, Callable

from .converter import ScoreConverter
from .search_engine import run_reverse_search

# [DEPRECATED] 기존 개별 대학 계산기 - 하위 호환성을 위해 유지
# 새로운 코드는 suneung_calculator.run_suneung_search()를 사용하세요
try:
    from .calculators.khu import calculate_khu_score
    from .calculators.korea import calculate_korea_score
    from .calculators.sogang import calculate_sogang_score
    from .calculators.snu import calculate_snu_score
    from .calculators.yonsei import calculate_yonsei_score
except ImportError:
    # 계산기가 삭제된 경우 더미 함수
    def calculate_khu_score(*args, **kwargs): return {}
    def calculate_korea_score(*args, **kwargs): return {}
    def calculate_sogang_score(*args, **kwargs): return {}
    def calculate_snu_score(*args, **kwargs): return {}
    def calculate_yonsei_score(*args, **kwargs): return {}


def normalize_scores_from_extracted(extracted_scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM의 Function Calling 결과(scores)를 받아 ScoreConverter를 통해 완전한 데이터로 변환.
    
    탐구 과목명 미입력 시 디폴트는 사탐(사회탐구): 탐구1=생활과윤리, 탐구2=사회문화.
    """
    converter = ScoreConverter()
    normalized = {"과목별_성적": {}, "선택과목": {}}
    
    defaults = {
        "국어": "화법과작문",
        "수학": "확률과통계",
        "탐구1": "생활과윤리",
        "탐구2": "사회문화",
    }

    for key, info in extracted_scores.items():
        # 1. 과목명 결정
        subject_name = key
        if key in ["탐구1", "탐구2"]:
            subject_name = info.get("과목명") or defaults.get(key, key)
        
        # 2. 선택과목 결정 (국어/수학)
        elective = info.get("선택과목")
        if key in ["국어", "수학"] and not elective:
            elective = defaults.get(key)
            normalized["선택과목"][key] = elective

        # 3. 값 추출
        val_type = info.get("type")
        val_value = info.get("value")

        # 4. ScoreConverter를 이용한 데이터 채우기
        processed_data = {}
        
        # 절대평가는 제외
        if key in ["영어", "한국사"]:
            normalized["과목별_성적"][key] = {
                "과목명": key,
                "등급": val_value,
                "표준점수": None,
                "백분위": None
            }
            continue

        # 국/수/탐 변환 로직
        try:
            if val_type == "등급":
                processed_data = converter.estimate_score_by_grade(subject_name, val_value, elective)
            
            elif val_type == "표준점수":
                processed_data = converter.get_score_by_standard(subject_name, val_value, elective)
                if not processed_data:
                    processed_data = converter.estimate_score_by_grade(subject_name, 1, elective)
                    processed_data["note"] = "표준점수조회실패_추정값"
            
            elif val_type == "원점수":
                processed_data = converter.get_score_by_raw(subject_name, val_value, elective)
                if not processed_data:
                    processed_data = converter.estimate_score_by_grade(subject_name, 1, elective)
                    processed_data["note"] = "원점수조회실패_추정값"
            
            elif val_type == "백분위":
                processed_data = converter.find_closest_by_percentile(subject_name, val_value, elective)
                if not processed_data:
                    processed_data = converter.estimate_score_by_grade(subject_name, 1, elective)
                    processed_data["note"] = "백분위조회실패_추정값"
            
            # 결과 저장
            if processed_data:
                normalized["과목별_성적"][key] = {
                    "과목명": subject_name,
                    "선택과목": elective,
                    "등급": processed_data.get("grade"),
                    "표준점수": processed_data.get("standard_score"),
                    "백분위": processed_data.get("percentile"),
                    "원점수": processed_data.get("raw"),
                    "비고": processed_data.get("note", "")
                }
            else:
                normalized["과목별_성적"][key] = {
                    "과목명": subject_name,
                    "선택과목": elective,
                    "등급": val_value if val_type == "등급" else None,
                    "표준점수": None,
                    "백분위": None,
                    "비고": "데이터없음"
                }
                
        except Exception as e:
            print(f"Error processing {key}: {e}")
            normalized["과목별_성적"][key] = {
                "과목명": subject_name,
                "선택과목": elective,
                "등급": None,
                "표준점수": None,
                "백분위": None,
                "비고": f"처리오류: {str(e)}"
            }
            
    return normalized


def format_for_prompt(normalized_data: Dict[str, Any]) -> str:
    """정규화된 데이터를 텍스트 리스트로 변환"""
    lines = []
    scores = normalized_data["과목별_성적"]
    
    order = ["국어", "수학", "영어", "한국사", "탐구1", "탐구2"]
    for k in order:
        if k in scores:
            d = scores[k]
            name = f"{d['과목명']}"
            if d.get('선택과목'):
                name = f"{d['과목명']}({d['선택과목']})"
            
            parts = [f"{name}: {d['등급']}등급" if d.get('등급') else f"{name}: 등급정보없음"]
            
            if d.get('표준점수'):
                parts.append(f"표준점수 {d['표준점수']}")
            if d.get('백분위'):
                parts.append(f"백분위 {d['백분위']}")
            if d.get('원점수'):
                parts.append(f"원점수 {d['원점수']}")
            if d.get('비고'):
                parts.append(f"[{d['비고']}]")
            
            lines.append(f"- {' | '.join(parts)}")
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 대학별 정시 환산 점수 산출
# ---------------------------------------------------------------------------

def _calc_khu_converted_score(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """경희대 2026 정시"""
    track_results = calculate_khu_score(normalized_data)
    return {"대학명": "경희대학교", "계열별": track_results}


def _calc_korea_converted_score(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """고려대 2026 정시"""
    full = calculate_korea_score(normalized_data)
    return {"대학명": "고려대학교", "계열별": full["계열별"]}


def _calc_sogang_converted_score(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """서강대 2026 정시"""
    track_results = calculate_sogang_score(normalized_data)
    return {"대학명": "서강대학교", "계열별": track_results}


def _calc_snu_converted_score(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """서울대 2026 정시"""
    track_results = calculate_snu_score(normalized_data)
    return {"대학명": "서울대학교", "계열별": track_results}


def _calc_yonsei_converted_score(normalized_data: Dict[str, Any]) -> Dict[str, Any]:
    """연세대 2026 정시"""
    track_results = calculate_yonsei_score(normalized_data)
    return {"대학명": "연세대학교", "계열별": track_results}


def _format_univ_converted_section(calc_result: Dict[str, Any]) -> str:
    """대학별 환산 점수 딕셔너리를 프롬프트용 텍스트로 포맷"""
    univ_name = calc_result.get("대학명", "")

    if "계열별" in calc_result:
        lines = []
        for track, data in calc_result["계열별"].items():
            if "고려대" in univ_name:
                lines.append(f"【{data.get('모집단위', track)}】")
                if not data.get("계산_가능"):
                    lines.append(f"  계산 불가: {data.get('오류', '—')}")
                else:
                    lines.append(f"  국어 표준점수: {data.get('국어_표준점수', '—')}")
                    lines.append(f"  수학 표준점수: {data.get('수학_표준점수', '—')}")
                    lines.append(f"  탐구 변환합계: {data.get('탐구_변환합계', '—')}")
                    lines.append(f"  영어 감점: {data.get('영어_감점', '—')}")
                    lines.append(f"  한국사 감점: {data.get('한국사_감점', '—')}")
                    lines.append(f"  원점수: {data.get('원점수', '—')}")
                    lines.append(f"  **최종점수**: {data.get('최종점수', '—')} / 1000")
            elif "서강대" in univ_name:
                lines.append(f"【{data.get('모집단위', track)}】")
                if not data.get("계산_가능"):
                    lines.append(f"  계산 불가: {data.get('오류', '—')}")
                else:
                    lines.append(f"  국어 표준점수: {data.get('국어_표준점수', '—')}")
                    lines.append(f"  수학 표준점수: {data.get('수학_표준점수', '—')}")
                    lines.append(f"  탐구1 변환점수: {data.get('탐구1_변환점수', '—')}")
                    lines.append(f"  탐구2 변환점수: {data.get('탐구2_변환점수', '—')}")
                    lines.append(f"  탐구 합계: {data.get('탐구_합계', '—')}")
                    lines.append(f"  영어 가산: {data.get('영어_가산', '—')}")
                    lines.append(f"  한국사 가산: {data.get('한국사_가산', '—')}")
                    lines.append(f"  A형 (수학가중): {data.get('A형_점수', '—')}")
                    lines.append(f"  B형 (국어가중): {data.get('B형_점수', '—')}")
                    lines.append(f"  적용방식: {data.get('적용방식', '—')}")
                    lines.append(f"  **최종점수**: {data.get('최종점수', '—')}")
            elif "연세대" in univ_name:
                lines.append(f"【{data.get('모집단위', track)}】")
                if not data.get("계산_가능"):
                    lines.append(f"  계산 불가: {data.get('오류', '—')}")
                else:
                    lines.append(f"  국어 표준점수: {data.get('국어_표준점수', '—')}")
                    if data.get("수학_표준점수") is not None:
                        lines.append(f"  수학 표준점수: {data.get('수학_표준점수')}")
                    if data.get("탐구1_변환점수") is not None:
                        lines.append(f"  탐구1 변환점수: {data.get('탐구1_변환점수')}")
                    if data.get("탐구2_변환점수") is not None:
                        lines.append(f"  탐구2 변환점수: {data.get('탐구2_변환점수')}")
                    if data.get("탐구_합계") is not None:
                        lines.append(f"  탐구 합계: {data.get('탐구_합계')}")
                    lines.append(f"  영어 점수: {data.get('영어_점수', '—')}")
                    lines.append(f"  한국사 감점: {data.get('한국사_감점', '—')}")
                    if data.get("탐구_가산"):
                        lines.append(f"  탐구 가산: {data.get('탐구_가산')}")
                    lines.append(f"  **최종점수**: {data.get('최종점수', '—')} / 1000")
            elif "서울대" in univ_name:
                lines.append(f"【{data.get('모집단위', track)}】")
                if not data.get("계산_가능"):
                    lines.append(f"  계산 불가: {data.get('오류', '—')}")
                else:
                    lines.append(f"  환산공식: {data.get('환산공식', '—')}")
                    lines.append(f"  국어 표준점수: {data.get('국어_표준점수', '—')}")
                    if data.get("수학_표준점수") is not None:
                        lines.append(f"  수학 표준점수: {data.get('수학_표준점수')}")
                    lines.append(f"  탐구1 표준점수: {data.get('탐구1_표준점수', '—')}")
                    lines.append(f"  탐구2 표준점수: {data.get('탐구2_표준점수', '—')}")
                    if data.get("과탐_가산점", 0) > 0:
                        lines.append(f"  과탐 가산점: +{data['과탐_가산점']}점")
                    total_d = (data.get("수학_감점") or 0) + (data.get("영어_감점") or 0) + (data.get("한국사_감점") or 0)
                    if total_d < 0:
                        lines.append(f"  수학/영어/한국사 감점: {data.get('수학_감점', 0)} / {data.get('영어_감점', 0)} / {data.get('한국사_감점', 0)}")
                    if data.get("raw_score") is not None:
                        lines.append(f"  Raw Score: {data.get('raw_score')}")
                    lines.append(f"  최종점수: {data.get('최종점수', '—')}")
                    if data.get("최종점수_1000") is not None:
                        lines.append(f"  **1000점 스케일**: {data.get('최종점수_1000')}점 (수능비율 {data.get('수능비율', '—')}%)")
            else:
                # 경희대 스타일
                lines.append(f"【{track} 계열】")
                if not data.get("계산_가능"):
                    lines.append(f"  계산 불가: {data.get('오류', '—')}")
                else:
                    lines.append(f"  국어 표준점수: {data.get('국어_표준점수', '—')}")
                    if data.get("수학_표준점수") is not None:
                        lines.append(f"  수학 표준점수: {data.get('수학_표준점수')}")
                    lines.append(f"  탐구1 변환표준점수: {data.get('탐구1_변환표준점수', '—')}")
                    if data.get("탐구2_변환표준점수") is not None:
                        lines.append(f"  탐구2 변환표준점수: {data.get('탐구2_변환표준점수')}")
                    if data.get("과탐_가산점", 0) > 0:
                        lines.append(f"  과탐 가산점: +{data['과탐_가산점']}점")
                    lines.append(f"  기본점수 (600점): {data.get('기본점수_600', '—')}")
                    lines.append(f"  영어 감점: {data.get('영어_감점', '—')}")
                    lines.append(f"  한국사 감점: {data.get('한국사_감점', '—')}")
                    lines.append(f"  **최종점수**: {data.get('최종점수', '—')} / 600")
            lines.append("")
        return "\n".join(lines).strip()

    # 기존 단일 결과 포맷
    lines = []
    lines.append(f"- 국어 표준점수: {calc_result.get('국어_표준점수', '—')}")
    lines.append(f"- 수학 표준점수: {calc_result.get('수학_표준점수', '—')}")
    lines.append(f"- 탐구1 (백분위→변환표준점수): {calc_result.get('탐구1_백분위', '—')} → {calc_result.get('탐구1_변환표준점수', '—')}")
    lines.append(f"- 탐구2 (백분위→변환표준점수): {calc_result.get('탐구2_백분위', '—')} → {calc_result.get('탐구2_변환표준점수', '—')}")
    lines.append(f"- 영어 등급/감점: {calc_result.get('영어_등급', '—')}등급 / {calc_result.get('영어_감점', '—')}")
    lines.append(f"- 한국사 등급/감점: {calc_result.get('한국사_등급', '—')}등급 / {calc_result.get('한국사_감점', '—')}")
    lines.append(f"- **환산총점**: {calc_result.get('환산총점', '—')}")
    return "\n".join(lines)


# [DEPRECATED] 대학명(또는 키워드) → 환산 점수 계산 함수 등록
# 새로운 코드는 suneung_calculator.run_suneung_search()를 사용하세요 (86개 대학 지원)
UNIV_CONVERTED_CALCULATORS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "경희대": _calc_khu_converted_score,
    "경희대학교": _calc_khu_converted_score,
    "KHU": _calc_khu_converted_score,
    "고려대": _calc_korea_converted_score,
    "고려대학교": _calc_korea_converted_score,
    "Korea": _calc_korea_converted_score,
    "서강대": _calc_sogang_converted_score,
    "서강대학교": _calc_sogang_converted_score,
    "Sogang": _calc_sogang_converted_score,
    "서울대": _calc_snu_converted_score,
    "서울대학교": _calc_snu_converted_score,
    "SNU": _calc_snu_converted_score,
    "연세대": _calc_yonsei_converted_score,
    "연세대학교": _calc_yonsei_converted_score,
    "Yonsei": _calc_yonsei_converted_score,
}


def get_univ_converted_sections(
    normalized_data: Dict[str, Any],
    target_univ_list: list,
) -> str:
    """
    target_univ 목록에 대해 등록된 대학별 환산 점수를 계산하고,
    프롬프트에 넣을 '[대학명 환산 점수]' 섹션 문자열을 반환합니다.
    """
    sections = []
    seen = set()
    for univ in target_univ_list or []:
        if not univ or not isinstance(univ, str):
            continue
        for key, calc_fn in UNIV_CONVERTED_CALCULATORS.items():
            if key in univ and key not in seen:
                seen.add(key)
                calc_result = calc_fn(normalized_data)
                section_title = f"[{calc_result.get('대학명', key)} 환산 점수]"
                sections.append(f"{section_title}\n{_format_univ_converted_section(calc_result)}")
                break
    return "\n\n".join(sections) if sections else ""


def process_consult_call(params: Dict[str, Any]) -> str:
    """
    [Main Entry Point]
    LLM의 tool_calls 파라미터를 받아 최종 컨설팅 프롬프트 생성
    """
    # 1. 성적 처리
    raw_scores = params.get("scores", {})
    normalized = normalize_scores_from_extracted(raw_scores)
    score_text = format_for_prompt(normalized)

    # 2. 타겟 정보 처리
    targets = params.get("target_univ", []) or []
    majors = params.get("target_major", []) or []

    # 2-1. target_univ가 없거나 리버스 서치 필요 시 실행
    user_message = (params.get("user_message") or params.get("query") or "").strip()
    run_reverse = not targets or "어디 갈 수 있어" in user_message
    reverse_section = ""
    if run_reverse:
        reverse_results = run_reverse_search(normalized)
        if reverse_results:
            lines = ["| 대학 | 학과 | 전형 | 계열 | 70% 점수 컷 | 내 점수 | 판정 | 모집 | 경쟁률 |"]
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            for r in reverse_results:
                lines.append(
                    "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                        r.get("univ", ""),
                        r.get("major", ""),
                        r.get("type", ""),
                        r.get("field", ""),
                        r.get("cut_70_score", ""),
                        r.get("my_score", ""),
                        r.get("판정", ""),
                        r.get("recruit_count") if r.get("recruit_count") is not None else "—",
                        r.get("competition_rate") if r.get("competition_rate") is not None else "—",
                    )
                )
            reverse_section = "\n\n### 지원 가능 대학 및 학과 분석 (리버스 서치)\n\n" + "\n".join(lines) + "\n\n"

    # 3. 대학별 환산 점수
    univ_converted_sections = get_univ_converted_sections(normalized, targets)

    # 4. 프롬프트 생성
    prompt = f"""
[SYSTEM] 입시 컨설팅 요청
{reverse_section}
1. 학생 성적 분석 결과 (추정치 포함)

{score_text}
"""
    if univ_converted_sections:
        prompt += f"""

{univ_converted_sections}
"""
    prompt += f"""

2. 상담 요청

- 희망 대학: {', '.join(targets) if targets else '미정'}
- 희망 전공: {', '.join(majors) if majors else '미정'}

3. 임무

위 성적을 바탕으로 정시 지원 전략을 수립하세요.
"""
    if univ_converted_sections:
        prompt += """대학별 환산 점수가 제시된 경우, 단순 표준점수 합이 아닌 해당 대학 환산 점수를 기준으로 합격 가능성을 판정하고,
"""
    prompt += """각 과목의 표준점수와 백분위를 고려하여 지원 전략을 제시해주세요.
"""
    return prompt
