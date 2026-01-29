"""
수능 점수 → 입시 컨설팅 & 리버스 서치 (Streamlit)
"""
import streamlit as st
import pandas as pd
from typing import Dict, Any, List, Optional

from app.processor import process_consult_call, normalize_scores_from_extracted
from app.search_engine import run_reverse_search
from app.config import DISPLAY_COLUMNS


# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="수능 입시 리버스 서치", 
    page_icon="📊", 
    layout="wide"
)


# ============================================================
# 입력 폼 컴포넌트
# ============================================================
def render_score_input_form() -> Dict[str, Dict[str, Any]]:
    """성적 입력 폼을 렌더링하고 입력값을 딕셔너리로 반환"""
    st.subheader("1. 성적 입력")
    st.caption("등급(1~9) 또는 표준점수를 입력하세요. 미입력 시 기본값이 적용됩니다.")
    
    # 국어, 수학, 영어
    cols = st.columns(3)
    
    with cols[0]:
        st.markdown("**국어**")
        kor_type = st.selectbox("국어 입력 방식", ["등급", "표준점수"], key="kor_type")
        max_val = 150 if kor_type == "표준점수" else 9
        kor_val = st.number_input("국어 값", min_value=0, max_value=max_val, value=1, key="kor_val")
        
    with cols[1]:
        st.markdown("**수학**")
        math_type = st.selectbox("수학 입력 방식", ["등급", "표준점수"], key="math_type")
        max_val = 150 if math_type == "표준점수" else 9
        math_val = st.number_input("수학 값", min_value=0, max_value=max_val, value=1, key="math_val")
        
    with cols[2]:
        st.markdown("**영어**")
        eng_grade = st.number_input("영어 등급 (1~9)", min_value=1, max_value=9, value=1, key="eng")

    # 한국사, 탐구1, 탐구2
    cols2 = st.columns(3)
    
    with cols2[0]:
        st.markdown("**한국사**")
        hist_grade = st.number_input("한국사 등급 (1~9)", min_value=1, max_value=9, value=1, key="hist")
        
    with cols2[1]:
        st.markdown("**탐구1**")
        inq1_type = st.selectbox("탐구1 입력 방식", ["등급", "표준점수", "원점수"], key="inq1_type")
        inq1_val = st.number_input("탐구1 값", min_value=0, max_value=100, value=1, key="inq1_val")
        
    with cols2[2]:
        st.markdown("**탐구2**")
        inq2_type = st.selectbox("탐구2 입력 방식", ["등급", "표준점수", "원점수"], key="inq2_type")
        inq2_val = st.number_input("탐구2 값", min_value=0, max_value=100, value=1, key="inq2_val")

    # 점수 딕셔너리 구성
    return {
        "국어": {"type": kor_type, "value": int(kor_val)},
        "수학": {"type": math_type, "value": int(math_val)},
        "영어": {"type": "등급", "value": int(eng_grade)},
        "한국사": {"type": "등급", "value": int(hist_grade)},
        "탐구1": {
            "type": inq1_type, 
            "value": float(inq1_val) if inq1_type == "원점수" else int(inq1_val), 
            "과목명": "생활과윤리"
        },
        "탐구2": {
            "type": inq2_type, 
            "value": float(inq2_val) if inq2_type == "원점수" else int(inq2_val), 
            "과목명": "사회문화"
        },
    }


def render_target_input_form() -> tuple[List[str], List[str]]:
    """희망 대학/전공 입력 폼을 렌더링하고 리스트로 반환"""
    st.subheader("2. 희망 대학·전공 (선택)")
    st.caption("비워두면 '지원 가능한 모든 대학·학과' 리버스 서치 결과가 표시됩니다.")
    
    target_univ_text = st.text_input(
        "희망 대학 (쉼표 구분, 예: 고려대학교, 연세대학교)", 
        placeholder="비워두면 전체 리버스 서치"
    )
    target_major_text = st.text_input(
        "희망 전공 (쉼표 구분)", 
        placeholder="예: 경영학과, 경제학과"
    )
    
    targets = [x.strip() for x in target_univ_text.split(",") if x.strip()] if target_univ_text else []
    majors = [x.strip() for x in target_major_text.split(",") if x.strip()] if target_major_text else []
    
    return targets, majors


# ============================================================
# 결과 표시 컴포넌트
# ============================================================
def format_results_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """결과 리스트를 포맷팅된 DataFrame으로 변환"""
    df = pd.DataFrame(results)
    
    # 컬럼명 변경
    column_renames = {
        "cut_70_score": "70% 점수 컷",
        "cut_50_score": "50% 점수 컷",
        "my_score": "내 점수",
        "판정": "판정",
        "recruit_count": "모집",
        "competition_rate": "경쟁률",
    }
    df = df.rename(columns=column_renames)
    
    return df


def get_display_columns(df: pd.DataFrame) -> List[str]:
    """표시할 컬럼 순서 결정"""
    display_cols = [
        "univ", "major", "type", "field", 
        "70% 점수 컷", "50% 점수 컷", "내 점수", 
        "판정", "모집", "경쟁률"
    ]
    
    # 최종점수 컬럼이 있으면 '내 점수' 뒤에 추가
    if "최종점수" in df.columns:
        idx = display_cols.index("내 점수") + 1
        display_cols.insert(idx, "최종점수")
    
    # 실제 존재하는 컬럼만 필터링
    return [c for c in display_cols if c in df.columns]


def render_results(results: List[Dict[str, Any]]) -> None:
    """결과를 화면에 표시"""
    if not results:
        st.info("입력한 성적 기준으로 매칭되는 입결 데이터가 없습니다. (계열/전형 확인)")
        return
        
    st.subheader("📋 지원 가능 대학·학과 (리버스 서치)")
    
    df = format_results_dataframe(results)
    display_cols = get_display_columns(df)
    
    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
    )


def render_prompt_expander(prompt: str) -> None:
    """컨설팅 프롬프트를 expander로 표시"""
    with st.expander("📄 전체 컨설팅 프롬프트 (LLM 입력용)"):
        st.text(prompt)


# ============================================================
# 메인 애플리케이션
# ============================================================
def main():
    st.title("📊 수능 성적 입시 컨설팅 & 리버스 서치")
    st.caption("성적을 입력하면 지원 가능 대학·학과(안정/적정/소신/상향)를 한눈에 볼 수 있습니다.")

    # 입력 폼
    scores = render_score_input_form()
    targets, majors = render_target_input_form()

    # 실행 버튼
    if st.button("🔄 리버스 서치 & 컨설팅 프롬프트 생성", type="primary"):
        params = {
            "scores": scores, 
            "target_univ": targets, 
            "target_major": majors
        }

        try:
            # 점수 정규화 및 리버스 서치
            normalized = normalize_scores_from_extracted(scores)
            results = run_reverse_search(normalized)
            
            # 결과 표시
            render_results(results)
            
            # 컨설팅 프롬프트
            prompt = process_consult_call(params)
            render_prompt_expander(prompt)
            
        except Exception as e:
            st.error(f"오류: {e}")
            raise


if __name__ == "__main__":
    main()
