import os
import sys
import json
from typing import Any, Dict, List, Optional

import numpy as np


# 프로젝트 루트 및 backend 경로를 PYTHONPATH에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_ROOT not in sys.path:
  sys.path.append(BACKEND_ROOT)

# backend 모듈 import (backend/services, backend/config 등 재사용)
from services.supabase_client import SupabaseService  # type: ignore
from config import embedding_settings as embedding_config  # type: ignore
from langchain_google_genai import GoogleGenerativeAIEmbeddings  # type: ignore


def _school_name_search_variants(university: str) -> List[str]:
  """검색 시 사용할 학교명 변형 목록 (연세대/연세대학교 등)."""
  if not university or not university.strip():
    return [university or "미분류"]
  u = university.strip()
  variants = [u]
  if u.endswith("학교"):
    short = u[:-2]  # 연세대학교 -> 연세대
    if short and short not in variants:
      variants.append(short)
  else:
    full = u + "학교"  # 연세대 -> 연세대학교
    if full not in variants:
      variants.append(full)
  return variants


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
  """코사인 유사도 계산 (0~1 근사)."""
  v1, v2 = np.array(vec1), np.array(vec2)
  dot = np.dot(v1, v2)
  n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
  return float(dot / (n1 * n2)) if n1 and n2 else 0.0


def _estimate_tokens(text: str) -> int:
  """
  토큰 수 대략 추정.

  기존 RAGFunctions와 동일하게 한글 위주 텍스트 기준으로 len(text) // 2 사용.
  """
  return max(1, len(text) // 2)


class RAGExperimentRunner:
  """
  기존 RAGFunctions.univ() 구조를 재사용하되,
  - content_weight / summary_weight
  - token_limit
  - 문서 수준 필터링(doc_threshold)
  등을 파라미터로 바꿔가며 실험할 수 있는 러너.
  """

  def __init__(self) -> None:
    # Supabase 클라이언트
    self.supabase = SupabaseService.get_client()

    # 업로드/본번에서 사용하는 것과 동일한 임베딩 모델 사용
    embedding_model = getattr(
        embedding_config,
        "DEFAULT_EMBEDDING_MODEL",
        "models/gemini-embedding-001",
    )
    self.embeddings = GoogleGenerativeAIEmbeddings(
        model=embedding_model,
        request_timeout=60,
    )

  # ---------- Supabase 검색 관련 내부 유틸 ----------

  def _supabase_search_rpc(
      self,
      query_embedding: List[float],
      school_name: str,
      top_k: int = 30,
  ) -> List[Dict[str, Any]]:
    """match_document_chunks RPC만 호출 (학교명 하나에 대해 검색)."""
    rpc_params = {
        "filter_school_name": school_name,
        "filter_section_id": None,
        "match_count": top_k,
        "match_threshold": 0.0,
        "query_embedding": query_embedding,
    }
    response = self.supabase.rpc("match_document_chunks", rpc_params).execute()
    if not response.data:
      return []

    docs: List[Dict[str, Any]] = []
    for row in response.data:
      page_content = row.get("raw_data") or row.get("content", "")
      docs.append(
          {
              "page_content": page_content,
              "metadata": {
                  "chunk_id": row.get("id"),
                  "page_number": row.get("page_number", 0),
                  "score": row.get("similarity", 0.0),
                  "chunk_type": row.get("chunk_type", "text"),
                  "section_id": row.get("section_id"),
                  "document_id": row.get("document_id"),
              },
          }
      )
    return docs

  def _get_document_info(self, document_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """
    documents 테이블에서 summary / title / URL / summary_embedding 조회.

    반환 형태:
      {doc_id: {"embedding": [...], "summary": str, "title": str, "file_url": str}}
    """
    if not document_ids:
      return {}

    try:
      unique_ids = list(set(document_ids))
      response = (
          self.supabase.table("documents")
          .select("id, embedding_summary, summary, filename, file_url")
          .in_("id", unique_ids)
          .execute()
      )

      result: Dict[int, Dict[str, Any]] = {}
      for doc in response.data:
        emb_str = doc.get("embedding_summary")
        summary = doc.get("summary", "")
        filename = doc.get("filename", "")
        title = (
            filename.replace(".pdf", "").replace(".PDF", "")
            if filename
            else ""
        )
        file_url = doc.get("file_url", "")

        embedding = None
        if emb_str:
          if isinstance(emb_str, str):
            embedding = json.loads(emb_str)
          else:
            embedding = emb_str

        result[doc["id"]] = {
            "embedding": embedding,
            "summary": summary,
            "title": title,
            "file_url": file_url,
        }
      return result
    except Exception as e:  # pragma: no cover - 디버그 로그
      print(f"⚠️ Document 정보 조회 실패: {e}")
      return {}

  # ---------- 공개 실험용 메서드 ----------

  def run_univ_experiment(
      self,
      university: str,
      query: str,
      top_k: int = 30,
      content_weight: float = 0.6,
      summary_weight: float = 0.4,
      token_limit: int = 6000,
      doc_threshold: Optional[float] = None,
  ) -> Dict[str, Any]:
    """
    대학 입시 정보 RAG 검색(univ)을 실험용으로 실행.

    Args:
      university: "서울대학교" 등
      query: "정시 전형 결과" 등
      top_k: 초기 벡터 검색 개수
      content_weight: 청크 벡터 점수 가중치
      summary_weight: 문서 summary 임베딩 점수 가중치
      token_limit: 선택할 청크의 총 추정 토큰 상한
      doc_threshold: 문서 summary_similarity 최소값 (None이면 문서 수준 필터링 비활성)
    """
    print(f"🔍 RAG 실험: '{query}' (학교: {university})")

    # 1) 쿼리 임베딩
    query_embedding = self.embeddings.embed_query(query)

    # 2) 학교명 변형 기반 초기 검색
    all_documents: List[Dict[str, Any]] = []
    seen_chunk_ids = set()
    for school_name in _school_name_search_variants(university):
      docs = self._supabase_search_rpc(query_embedding, school_name, top_k)
      for doc in docs:
        cid = doc["metadata"].get("chunk_id")
        if cid and cid not in seen_chunk_ids:
          seen_chunk_ids.add(cid)
          all_documents.append(doc)

    documents = all_documents
    if not documents:
      return {
          "chunks": [],
          "count": 0,
          "university": university,
          "query": query,
          "debug": {"reason": "no_documents"},
      }

    # 3) 문서 정보 조회
    doc_ids = [
        d["metadata"].get("document_id")
        for d in documents
        if d["metadata"].get("document_id")
    ]
    document_info = self._get_document_info(doc_ids)

    # 3-1) (옵션) 문서 수준 summary score 계산 및 필터링
    doc_summary_scores: Dict[int, float] = {}
    for d in documents:
      meta = d["metadata"]
      doc_id = meta.get("document_id")
      if not doc_id or doc_id not in document_info:
        continue
      emb = document_info[doc_id].get("embedding")
      if not emb:
        continue
      sim = _cosine_similarity(query_embedding, emb)
      current = doc_summary_scores.get(doc_id)
      if current is None or sim > current:
        doc_summary_scores[doc_id] = sim

    valid_doc_ids = set(document_info.keys())
    if doc_threshold is not None:
      valid_doc_ids = {
          doc_id
          for doc_id, score in doc_summary_scores.items()
          if score >= doc_threshold
      }
      print(
          f"📚 문서 수준 필터링: {len(valid_doc_ids)}개 문서 통과 "
          f"(threshold={doc_threshold})"
      )

    # 4) 청크별 가중 점수 계산
    scored_chunks: List[Dict[str, Any]] = []
    for d in documents:
      meta = d["metadata"]
      doc_id = meta.get("document_id")

      # 문서 수준 필터링 적용
      if doc_threshold is not None and doc_id not in valid_doc_ids:
        continue

      content_similarity = meta.get("score", 0.0)

      summary_similarity = 0.0
      if doc_id and doc_id in document_info:
        doc_info = document_info[doc_id]
        if doc_info.get("embedding"):
          summary_similarity = _cosine_similarity(
              query_embedding, doc_info["embedding"]
          )

      weighted = (
          content_similarity * content_weight
          + summary_similarity * summary_weight
      )

      scored_chunks.append(
          {
              "doc": d,
              "weighted_score": weighted,
              "content_score": content_similarity,
              "summary_score": summary_similarity,
          }
      )

    if not scored_chunks:
      return {
          "chunks": [],
          "count": 0,
          "university": university,
          "query": query,
          "debug": {"reason": "no_scored_chunks_after_filter"},
      }

    # 5) 정렬 + 토큰 한도 내에서 선택
    scored_chunks.sort(key=lambda x: x["weighted_score"], reverse=True)

    selected_chunks: List[Dict[str, Any]] = []
    total_tokens = 0
    for item in scored_chunks:
      content = item["doc"]["page_content"]
      chunk_tokens = _estimate_tokens(content)
      if total_tokens + chunk_tokens > token_limit:
        break
      selected_chunks.append(item)
      total_tokens += chunk_tokens

    # 6) 최종 포맷 + 문서 메타데이터 정리
    results: List[Dict[str, Any]] = []
    for item in selected_chunks:
      doc = item["doc"]
      meta = doc["metadata"]
      if not meta.get("chunk_id"):
        continue
      results.append(
          {
              "chunk_id": meta.get("chunk_id"),
              "section_id": meta.get("section_id"),
              "document_id": meta.get("document_id"),
              "page_number": meta.get("page_number"),
              "chunk_type": meta.get("chunk_type"),
              "content": doc["page_content"],
              "score": meta.get("score", 0.0),
              "weighted_score": item["weighted_score"],
              "content_score": item["content_score"],
              "summary_score": item["summary_score"],
          }
      )

    used_doc_ids = {
        r["document_id"] for r in results if r.get("document_id") is not None
    }
    document_summaries = {
        doc_id: info.get("summary", "")
        for doc_id, info in document_info.items()
        if doc_id in used_doc_ids and info.get("summary")
    }
    document_titles = {
        doc_id: info.get("title", f"문서 {doc_id}")
        for doc_id, info in document_info.items()
        if doc_id in used_doc_ids
    }
    document_urls = {
        doc_id: info.get("file_url", "")
        for doc_id, info in document_info.items()
        if doc_id in used_doc_ids
    }

    return {
        "chunks": results,
        "count": len(results),
        "university": university,
        "query": query,
        "document_summaries": document_summaries,
        "document_titles": document_titles,
        "document_urls": document_urls,
        "debug": {
            "total_candidates": len(documents),
            "total_selected": len(results),
            "token_limit": token_limit,
            "used_tokens_estimate": total_tokens,
            "doc_summary_scores": doc_summary_scores,
        },
    }


