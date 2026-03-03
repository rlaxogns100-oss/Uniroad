import os
import sys

import pandas as pd
import streamlit as st


# 프로젝트 루트 / backend 경로를 PYTHONPATH에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")

if PROJECT_ROOT not in sys.path:
  sys.path.append(PROJECT_ROOT)
if BACKEND_ROOT not in sys.path:
  sys.path.append(BACKEND_ROOT)

# rag_lab 내부 모듈 import (패키지 인식 위해 PROJECT_ROOT를 sys.path에 추가한 뒤 import)
from rag_lab.rag_runner import RAGExperimentRunner  # type: ignore


def main() -> None:
  st.set_page_config(page_title="Uniroad RAG Lab", layout="wide")

  st.title("📚 Uniroad RAG 실험실")
  st.caption("쿼리별 RAG 검색 결과를 weight / 토큰 한도 / 문서 필터링을 바꿔가며 비교하는 도구")

  # ----- 사이드바: 파라미터 -----
  st.sidebar.header("검색 설정")

  university = st.sidebar.text_input("대학명", value="서울대학교")
  query = st.sidebar.text_area("질문(query)", value="정시 전형 결과", height=80)

  top_k = st.sidebar.slider("초기 벡터 검색 개수 (top_k)", 10, 100, 30, step=5)
  token_limit = st.sidebar.slider(
      "토큰 한도 (대략치)", 1000, 12000, 6000, step=500
  )

  st.sidebar.markdown("#### 점수 가중치")
  content_weight = st.sidebar.slider(
      "content_weight (청크 벡터 점수 비중)",
      0.0,
      1.0,
      0.6,
      0.05,
  )
  summary_weight = 1.0 - content_weight
  st.sidebar.write(
      f"summary_weight (문서 요약 벡터 비중): **{summary_weight:.2f}**"
  )

  st.sidebar.markdown("#### 문서 수준 필터링")
  use_doc_filter = st.sidebar.checkbox(
      "문서 수준 필터(doc_threshold) 사용", value=False
  )
  doc_threshold = None
  if use_doc_filter:
    doc_threshold = st.sidebar.slider(
        "doc_threshold (summary_similarity 최소값)",
        0.0,
        1.0,
        0.20,
        0.05,
    )

  st.sidebar.markdown("---")
  run_button = st.sidebar.button("RAG 검색 실행")

  if not run_button:
    st.info("왼쪽 사이드바에서 설정을 조정한 뒤 **'RAG 검색 실행'** 버튼을 눌러주세요.")
    return

  if not query.strip():
    st.warning("쿼리를 입력하세요.")
    return

  # ----- RAG 실행 -----
  with st.spinner("RAG 검색 실행 중..."):
    runner = RAGExperimentRunner()
    result = runner.run_univ_experiment(
        university=university,
        query=query,
        top_k=top_k,
        content_weight=content_weight,
        summary_weight=summary_weight,
        token_limit=token_limit,
        doc_threshold=doc_threshold,
    )

  # ----- 1. 요약 정보 -----
  st.subheader("1️⃣ 검색 요약")
  st.json(
      {
          "university": result.get("university"),
          "query": result.get("query"),
          "count": result.get("count"),
          "debug": result.get("debug"),
      }
  )

  chunks = result.get("chunks", [])
  if not chunks:
    st.warning("선택된 청크가 없습니다. (필터/threshold가 너무 높을 수도 있습니다.)")
    return

  # ----- 2. 청크 테이블 -----
  st.subheader("2️⃣ 선택된 청크 목록")

  df_rows = []
  for idx, ch in enumerate(chunks, start=1):
    df_rows.append(
        {
            "rank": idx,
            "doc_id": ch.get("document_id"),
            "page": ch.get("page_number"),
            "score": round(ch.get("score", 0.0), 4),
            "summary_score": round(ch.get("summary_score", 0.0), 4),
            "weighted": round(ch.get("weighted_score", 0.0), 4),
            "content_preview": (ch.get("content") or "")
            .replace("\n", " ")[:140],
        }
    )

  df = pd.DataFrame(df_rows)
  st.dataframe(df, use_container_width=True, height=400)

  # ----- 3. 문서별 요약 / 제목 / URL -----
  st.subheader("3️⃣ 사용된 문서 요약 / 제목 / URL")

  doc_titles = result.get("document_titles", {}) or {}
  doc_summaries = result.get("document_summaries", {}) or {}
  doc_urls = result.get("document_urls", {}) or {}

  if not doc_titles:
    st.info("사용된 문서 메타데이터가 없습니다.")
  else:
    for doc_id in sorted(doc_titles.keys()):
      title = doc_titles.get(doc_id, f"문서 {doc_id}")
      with st.expander(f"문서 {doc_id}: {title}"):
        st.markdown(f"**제목**: {title}")
        if doc_id in doc_summaries:
          st.markdown("**요약:**")
          st.write(doc_summaries[doc_id])
        if doc_id in doc_urls and doc_urls[doc_id]:
          st.markdown(f"[PDF 열기]({doc_urls[doc_id]})")

  # ----- 4. 개별 청크 내용 미리보기 -----
  st.subheader("4️⃣ 청크 내용 미리보기")

  selected_rank = st.number_input(
      "볼 청크 rank 선택 (1부터)",
      min_value=1,
      max_value=len(chunks),
      value=1,
  )
  sel = chunks[selected_rank - 1]

  st.markdown(
      f"**문서 {sel.get('document_id')} / 페이지 {sel.get('page_number')} / "
      f"score={sel.get('score'):.4f}, "
      f"summary={sel.get('summary_score'):.4f}, "
      f"weighted={sel.get('weighted_score'):.4f}**"
  )
  st.text(sel.get("content") or "")


if __name__ == "__main__":
  main()

