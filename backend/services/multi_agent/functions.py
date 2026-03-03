"""
RAG Functions
- Supabase 기반 유사도 검색
- uniroad_recommed_1/core/rag_system.py의 search_global_raw 로직 이식
"""

import asyncio
import os
import json
import re
from threading import Lock
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv
from services.score_review import to_consult_j_scores

load_dotenv()

# GEMINI_API_KEY를 GOOGLE_API_KEY로 매핑 (langchain 호환)
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

from services.supabase_client import SupabaseService, supabase_service
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# 업로드와 동일한 임베딩 모델 사용 (768차원, DB vector(768)와 일치)
try:
    from config import embedding_settings as embedding_config
    _DEFAULT_EMBEDDING_MODEL = getattr(embedding_config, "DEFAULT_EMBEDDING_MODEL", "models/gemini-embedding-001")
except Exception:
    _DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"


def convert_5grade_to_9grade(grade_5: float) -> float:
    """
    5등급제 내신을 9등급제로 환산
    - 5등급제 1.0 → 9등급제 1.4
    - 5등급제 5.0 → 9등급제 9.0
    - 선형 보간: y = 1.4 + (x - 1.0) * 1.9
    """
    return round(1.4 + (grade_5 - 1.0) * 1.9, 2)


def parse_score_with_grade_system(score_str: str) -> Tuple[float, str]:
    """
    내신 점수 문자열을 파싱하여 (점수, 등급제) 튜플 반환
    - "2.3(5)" → (2.3, "5등급제")
    - "2.3(9)" → (2.3, "9등급제")
    - "2.3" → (2.3, "9등급제")  # 기본값
    
    5등급제인 경우 자동으로 9등급제로 환산하여 반환
    """
    score_str = str(score_str).strip()
    match = re.match(r"([\d.]+)\s*\((\d)\)", score_str)
    
    if match:
        score = float(match.group(1))
        system_indicator = match.group(2)
        
        if system_indicator == "5":
            # 5등급제 → 9등급제 환산
            converted_score = convert_5grade_to_9grade(score)
            return converted_score, "5등급제"
        else:
            # 9등급제 (또는 다른 숫자)
            return score, "9등급제"
    
    # 괄호 없으면 기본값 9등급제
    return float(score_str), "9등급제"


def _school_name_search_variants(university: str) -> List[str]:
    """검색 시 사용할 학교명 변형 목록 (업로드 시 폴더명 '연세대' vs 채팅 '연세대학교' 등 모두 매칭)"""
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


class RAGFunctions:
    """RAG 검색 함수 클래스"""
    
    _instance = None
    
    def __init__(self):
        self.supabase = SupabaseService.get_client()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=_DEFAULT_EMBEDDING_MODEL,
            request_timeout=60,
        )
        # 반복 질의/문서 조회를 줄이기 위한 경량 인메모리 캐시
        self._query_embedding_cache: Dict[str, List[float]] = {}
        self._query_embedding_cache_limit = 256
        self._document_info_cache: Dict[int, Dict[str, Any]] = {}
        self._document_info_cache_limit = 6000
        self._cache_lock = Lock()
    
    @classmethod
    def get_instance(cls):
        """싱글톤 인스턴스"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _supabase_search_rpc(
        self,
        query_embedding: List[float],
        school_name: str,
        top_k: int = 30
    ) -> List[Dict]:
        """RPC만 호출 (쿼리 임베딩은 외부에서 한 번만 생성). 학교명 하나에 대해 검색."""
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
        documents = []
        for row in response.data:
            page_content = row.get("raw_data") or row.get("content", "")
            documents.append({
                "page_content": page_content,
                "metadata": {
                    "chunk_id": row.get("id"),
                    "page_number": row.get("page_number", 0),
                    "score": row.get("similarity", 0.0),
                    "chunk_type": row.get("chunk_type", "text"),
                    "section_id": row.get("section_id"),
                    "document_id": row.get("document_id"),
                }
            })
        return documents

    def _supabase_search(
        self, 
        query: str, 
        school_name: str, 
        top_k: int = 30
    ) -> Tuple[List[Dict], List[float]]:
        """
        Step 1-2: Supabase RPC로 벡터 검색 (단일 학교명).
        Returns:
            Tuple[documents, query_embedding] - 문서 리스트와 쿼리 임베딩 (재사용 위해)
        """
        query_embedding = self.embeddings.embed_query(query)
        documents = self._supabase_search_rpc(query_embedding, school_name, top_k)
        return documents, query_embedding
    
    def _get_document_info(self, document_ids: List[int]) -> Dict[int, Dict]:
        """
        Step 3: documents 테이블에서 embedding_summary와 summary 조회
        - 실시간 임베딩 계산 없이 DB에 저장된 벡터 사용
        - Supabase는 vector 타입을 문자열로 반환하므로 json.loads() 필요
        
        Returns:
            {doc_id: {"embedding": [...], "summary": "문서 설명"}}
        """
        if not document_ids:
            return {}
        
        try:
            unique_ids = list(dict.fromkeys(doc_id for doc_id in document_ids if doc_id is not None))
            result: Dict[int, Dict[str, Any]] = {}
            missing_ids: List[int] = []

            with self._cache_lock:
                for doc_id in unique_ids:
                    cached = self._document_info_cache.get(doc_id)
                    if cached is None:
                        missing_ids.append(doc_id)
                    else:
                        result[doc_id] = cached

            if missing_ids:
                response = (
                    self.supabase.table("documents")
                    .select("id, embedding_summary, summary, filename, file_url")
                    .in_("id", missing_ids)
                    .execute()
                )

                for doc in response.data:
                    emb_str = doc.get("embedding_summary")
                    summary = doc.get("summary", "")
                    filename = doc.get("filename", "")
                    title = filename.replace(".pdf", "").replace(".PDF", "") if filename else ""
                    file_url = doc.get("file_url", "")

                    embedding = None
                    if emb_str:
                        if isinstance(emb_str, str):
                            embedding = json.loads(emb_str)
                        else:
                            embedding = emb_str

                    normalized = {
                        "embedding": embedding,
                        "summary": summary,
                        "title": title,
                        "file_url": file_url,
                    }
                    doc_id = doc.get("id")
                    if doc_id is None:
                        continue
                    result[doc_id] = normalized
                    with self._cache_lock:
                        self._document_info_cache[doc_id] = normalized

                with self._cache_lock:
                    if len(self._document_info_cache) > self._document_info_cache_limit:
                        overflow = len(self._document_info_cache) - self._document_info_cache_limit
                        for stale_key in list(self._document_info_cache.keys())[:overflow]:
                            self._document_info_cache.pop(stale_key, None)

            return result
        except Exception as e:
            print(f"⚠️ Document 정보 조회 실패: {e}")
            return {}

    def _get_query_embedding_cached(self, query: str) -> List[float]:
        key = str(query or "").strip()
        with self._cache_lock:
            cached = self._query_embedding_cache.get(key)
        if cached is not None:
            return cached

        embedding = self.embeddings.embed_query(key)
        with self._cache_lock:
            existing = self._query_embedding_cache.get(key)
            if existing is not None:
                return existing
            if len(self._query_embedding_cache) >= self._query_embedding_cache_limit:
                oldest_key = next(iter(self._query_embedding_cache))
                self._query_embedding_cache.pop(oldest_key, None)
            self._query_embedding_cache[key] = embedding
        return embedding
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        코사인 유사도 계산
        원본: uniroad_recommed_1/core/rag_system.py (323-332줄)
        """
        vec1, vec2 = np.array(vec1), np.array(vec2)
        dot_product = np.dot(vec1, vec2)
        norm1, norm2 = np.linalg.norm(vec1), np.linalg.norm(vec2)
        return float(dot_product / (norm1 * norm2)) if norm1 and norm2 else 0.0
    
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        토큰 수 추정 (한글/영어 혼합 고려)
        - 한글 1자 ≈ 2토큰
        - 영어 1단어 ≈ 1토큰
        - 간단한 휴리스틱: 문자 수 / 2 (한글 위주 텍스트)
        """
        return max(1, len(text) // 2)
    
    async def univ(
        self, 
        university: str, 
        query: str,
        top_k: int = 30,
        content_weight: float = 0.6,
        summary_weight: float = 0.4
    ) -> Dict[str, Any]:
        """
        univ 함수 - 대학 입시 정보 RAG 검색
        원본: uniroad_recommed_1/core/rag_system.py search_global_raw() (243-394줄)
        
        Input:
            university: "고려대학교"
            query: "정시 전형"
        
        Output:
            {
                "chunks": [...],  # 상위 10개 청크
                "count": 10,
                "university": "고려대학교",
                "query": "정시 전형"
            }
        """
        print(f"🔍 전역 검색: '{query}' (학교: {university})")
        
        # 쿼리 임베딩 1회 생성 (동일 질의는 캐시 재사용)
        query_embedding = await asyncio.to_thread(self._get_query_embedding_cached, query)
        # 학교명 변형으로 검색 (연세대/연세대학교 등 업로드 폴더명·채팅 정식명 모두 매칭)
        all_documents = []
        seen_chunk_ids = set()
        school_variants = _school_name_search_variants(university)
        docs_per_variant = await asyncio.gather(
            *[
                asyncio.to_thread(self._supabase_search_rpc, query_embedding, school_name, top_k)
                for school_name in school_variants
            ],
            return_exceptions=True,
        )
        for docs in docs_per_variant:
            if isinstance(docs, Exception):
                print(f"⚠️ 학교명 변형 검색 실패: {docs}")
                continue
            for doc in docs:
                cid = doc["metadata"].get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    all_documents.append(doc)
        documents = all_documents
        
        if not documents:
            print("⚠️ 검색 결과 없음")
            return {"chunks": [], "count": 0, "university": university, "query": query}
        
        print(f"✅ 초기 검색: {len(documents)}개 문서")
        
        # Step 3: document_id로 문서 정보 조회 (embedding + summary)
        doc_ids = [d["metadata"].get("document_id") for d in documents if d["metadata"].get("document_id")]
        document_info = await asyncio.to_thread(self._get_document_info, doc_ids)
        
        # Step 4: 쿼리 임베딩은 Step 1-2에서 재사용 (중복 제거)
        
        # Step 5: 가중 평균 유사도 계산
        scored_chunks = []
        for doc in documents:
            meta = doc["metadata"]
            content_similarity = meta.get("score", 0.0)
            
            # Summary 유사도 계산 (DB에서 가져온 임베딩 직접 사용)
            summary_similarity = 0.0
            doc_id = meta.get("document_id")
            if doc_id and doc_id in document_info:
                doc_info = document_info[doc_id]
                if doc_info.get("embedding"):
                    summary_similarity = self._cosine_similarity(query_embedding, doc_info["embedding"])
            
            # 가중 평균
            weighted = (content_similarity * content_weight) + (summary_similarity * summary_weight)
            
            scored_chunks.append({
                "doc": doc,
                "weighted_score": weighted,
                "content_score": content_similarity,
                "summary_score": summary_similarity
            })
        
        # Step 6: 정렬 후 토큰 기반 선택 (6,000 토큰 한도)
        scored_chunks.sort(key=lambda x: x["weighted_score"], reverse=True)
        
        TOKEN_LIMIT = 6000
        selected_chunks = []
        total_tokens = 0
        
        for item in scored_chunks:
            content = item["doc"]["page_content"]
            chunk_tokens = self._estimate_tokens(content)
            
            if total_tokens + chunk_tokens > TOKEN_LIMIT:
                break
            
            selected_chunks.append(item)
            total_tokens += chunk_tokens
        
        print(f"📊 토큰 기반 선택: {len(selected_chunks)}개 청크 ({total_tokens} 토큰)")
        
        # Step 7: 결과 포맷팅
        results = []
        for item in selected_chunks:
            doc = item["doc"]
            meta = doc["metadata"]
            
            if not meta.get("chunk_id"):
                continue
            
            results.append({
                "chunk_id": meta.get("chunk_id"),
                "section_id": meta.get("section_id"),
                "document_id": meta.get("document_id"),
                "page_number": meta.get("page_number"),
                "chunk_type": meta.get("chunk_type"),
                "content": doc["page_content"],
                "score": meta.get("score", 0.0),
                "weighted_score": item["weighted_score"]
            })
        
        # document_summaries, document_titles, document_urls 추출 (결과에 포함된 문서들만)
        used_doc_ids = set(r["document_id"] for r in results if r.get("document_id"))
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
            "document_urls": document_urls
        }


async def execute_function_calls(function_calls: List[Dict], user_id: str = None) -> Dict[str, Any]:
    """
    router_agent의 function_calls 실행
    
    Input:
        [{"function": "univ", "params": {"university": "고려대학교", "query": "정시"}}]
    
    Output:
        {
            "univ_0": {"chunks": [...], "count": 10, ...},
            "univ_1": {"chunks": [...], "count": 5, ...}
        }
    """
    rag = RAGFunctions.get_instance()
    results = {}
    
    for idx, call in enumerate(function_calls):
        func_name = call.get("function")
        params = call.get("params", {})
        
        try:
            if func_name == "univ":
                # university와 query 파라미터 처리 (리스트 또는 문자열)
                university_param = params.get("university", "")
                query_param = params.get("query", "")
                
                # university: 리스트면 첫 번째 요소, 문자열이면 그대로
                if isinstance(university_param, list):
                    university = university_param[0] if university_param else ""
                else:
                    university = university_param
                
                # query: 리스트면 공백으로 조인, 문자열이면 그대로
                if isinstance(query_param, list):
                    query = " ".join(query_param)
                else:
                    query = query_param
                
                result = await rag.univ(
                    university=university,
                    query=query
                )
                results[f"univ_{idx}"] = result
            
            elif func_name == "consult_jungsi":
                # Score System 통합: 성적 정규화 및 대학별 환산
                # v2.0: suneung_calculator 사용 (86개 대학, 2158개 학과 지원)
                from services.multi_agent.score_system import (
                    normalize_scores_from_extracted,
                    format_for_prompt,
                    run_reverse_search,
                )
                
                # 토큰 추정 함수
                def estimate_tokens(text: str) -> int:
                    return max(1, len(text) // 2)
                
                CONSULT_TOKEN_LIMIT = 40960  # consult_jungsi는 40960 토큰
                
                # 1. router_agent의 j_scores 형식 변환
                # 간단 형식: {"국어": 1, "수학": 2} → 표준 형식: {"국어": {"type": "등급", "value": 1}}
                raw_scores = params.get("j_scores", {})
                score_id = params.get("score_id")
                loaded_score_name = None
                if score_id:
                    try:
                        score_row = await supabase_service.get_user_score_set_by_id(
                            str(score_id), user_id=user_id
                        )
                        if score_row and score_row.get("scores"):
                            raw_scores = to_consult_j_scores(score_row.get("scores") or {})
                            score_name = (score_row.get("name") or "").strip()
                            if score_name:
                                loaded_score_name = f"@{score_name}"
                    except Exception as e:
                        print(f"⚠️ score_id 조회 실패: {e}")
                converted_scores = {}
                
                for key, val in raw_scores.items():
                    if isinstance(val, dict):
                        # 이미 표준 형식인 경우
                        converted_scores[key] = val
                    elif isinstance(val, (int, float)):
                        # 숫자만 있는 경우 → 등급으로 간주
                        converted_scores[key] = {"type": "등급", "value": int(val)}
                    else:
                        converted_scores[key] = {"type": "등급", "value": val}
                
                # 2. 성적 정규화
                normalized = normalize_scores_from_extracted(converted_scores)
                score_text = format_for_prompt(normalized)
                
                # 3. 파라미터 추출 (Router Agent는 university/department/range로 보냄)
                target_univ = params.get("university", []) or params.get("target_univ", []) or []
                target_major = params.get("department", []) or params.get("target_major", []) or []
                target_range = params.get("range", []) or params.get("target_range", []) or []
                
                # 4. 리버스 서치 (86개 대학, 2158개 학과 지원)
                # 새로운 판정 기준: 안정, 적정, 소신, 도전, 어려움
                reverse_results = []
                user_message = params.get("user_message", "") or params.get("query", "")
                run_reverse = True  # 항상 리버스 서치 실행 (86개 대학 전체)
                
                if run_reverse:
                    try:
                        reverse_results = run_reverse_search(
                            normalized_scores=normalized,
                            target_range=target_range,
                            target_univ=target_univ if target_univ else None,
                            target_major=target_major if target_major else None,
                        )
                    except Exception as e:
                        print(f"⚠️ 리버스 서치 오류: {e}")
                
                # 5. chunk 기반 결과 생성 (판정별 분리)
                chunks = []
                total_tokens = 0
                
                # 청크 1: 성적 분석 (score_conversion)
                score_content = f"**학생 성적 분석**\n{score_text}"
                
                score_tokens = estimate_tokens(score_content)
                if score_tokens <= CONSULT_TOKEN_LIMIT:
                    chunks.append({
                        "document_id": "score_conversion",
                        "chunk_id": "score_analysis",
                        "section_id": "score_analysis",
                        "chunk_type": "score_analysis",
                        "content": score_content,
                        "page_number": ""
                    })
                    total_tokens += score_tokens
                else:
                    # 토큰 초과 시 잘라서 포함
                    truncated_len = CONSULT_TOKEN_LIMIT * 2  # 토큰 * 2 = 대략 문자 수
                    chunks.append({
                        "document_id": "score_conversion",
                        "chunk_id": "score_analysis",
                        "section_id": "score_analysis",
                        "chunk_type": "score_analysis",
                        "content": score_content[:truncated_len] + "\n...(생략)",
                        "page_number": ""
                    })
                    total_tokens = CONSULT_TOKEN_LIMIT
                
                # 청크 2~N: 판정별 분리된 결과 (안정, 적정, 소신, 도전, 어려움, 하향)
                if reverse_results:
                    # 판정별로 그룹핑
                    from collections import defaultdict
                    by_range = defaultdict(list)
                    for r in reverse_results:
                        # 이모지 제거하고 판정명만 추출
                        판정_raw = r.get("판정", "")
                        if "안정" in 판정_raw:
                            by_range["안정"].append(r)
                        elif "적정" in 판정_raw:
                            by_range["적정"].append(r)
                        elif "소신" in 판정_raw:
                            by_range["소신"].append(r)
                        elif "도전" in 판정_raw:
                            by_range["도전"].append(r)
                        elif "어려움" in 판정_raw:
                            by_range["어려움"].append(r)
                        elif "하향" in 판정_raw:
                            by_range["하향"].append(r)
                    
                    # 판정 순서대로 청크 생성
                    range_order = ["안정", "적정", "소신", "도전", "어려움", "하향"]
                    range_labels = {
                        "안정": "🟢 안정",
                        "적정": "🟡 적정", 
                        "소신": "🟠 소신",
                        "도전": "🔴 도전",
                        "어려움": "⚫ 어려움",
                        "하향": "⬇️ 하향"
                    }
                    
                    remaining_tokens = CONSULT_TOKEN_LIMIT - total_tokens
                    
                    for range_name in range_order:
                        range_items = by_range.get(range_name, [])
                        if not range_items:
                            continue
                        
                        table_header = f"**{range_labels[range_name]} 지원 가능 대학 ({len(range_items)}개)**\n| 대학 | 학과 | 군 | 계열 | 내 점수 | 안정컷 | 적정컷 | 소신컷 | 도전컷 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
                        table_rows = []
                        
                        header_tokens = estimate_tokens(table_header)
                        current_tokens = header_tokens
                        
                        for r in range_items:
                            row = "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                                r.get("univ", ""),
                                r.get("major", ""),
                                r.get("gun", ""),
                                r.get("track", "") or r.get("field", ""),
                                r.get("my_score", ""),
                                r.get("safe_score", "") if r.get("safe_score") else "—",
                                r.get("appropriate_score", "") if r.get("appropriate_score") else "—",
                                r.get("expected_score", "") if r.get("expected_score") else "—",
                                r.get("challenge_score", "") if r.get("challenge_score") else "—",
                            )
                            row_tokens = estimate_tokens(row)
                            
                            if current_tokens + row_tokens <= remaining_tokens:
                                table_rows.append(row)
                                current_tokens += row_tokens
                            else:
                                break  # 토큰 제한 도달
                        
                        if table_rows:
                            range_content = table_header + "\n" + "\n".join(table_rows)
                            chunks.append({
                                "document_id": f"admission_results_{range_name}",
                                "chunk_id": f"reverse_search_{range_name}",
                                "section_id": f"reverse_search_{range_name}",
                                "chunk_type": f"reverse_search_{range_name}",
                                "content": range_content,
                                "page_number": "",
                                "range": range_name,
                                "count": len(range_items)
                            })
                            total_tokens += current_tokens
                            remaining_tokens -= current_tokens
                
                # 출처 정보
                document_titles = {
                    "score_conversion": "2026 수능 표준점수 및 백분위 산출 방식",
                    "admission_results": "2026학년도 정시 배치표 (86개 대학)"
                }
                document_urls = {
                    "score_conversion": "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/5d5c4455-bf58-4ef5-9e7f-a82d602aaa51.pdf",
                    "admission_results": "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/b26bc045-e96b-4d3a-acb2-ac677633c685.pdf"
                }
                
                results[f"consult_jungsi_{idx}"] = {
                    "chunks": chunks,
                    "count": len(chunks),
                    "university": "",
                    "query": "정시 성적 분석",
                    "document_titles": document_titles,
                    "document_urls": document_urls,
                    "target_univ": target_univ,
                    "target_major": target_major,
                    "total_tokens": total_tokens,
                    "total_universities": 86,
                    "total_departments": len(reverse_results),
                    "loaded_score_name": loaded_score_name,
                }
            
            elif func_name == "consult_susi":
                # 수시 전형결과 조회 (JSON 기반)
                result = await _execute_consult_susi(params)
                results[f"consult_susi_{idx}"] = result
            
            else:
                results[f"{func_name}_{idx}"] = {"error": f"Unknown function: {func_name}"}
        
        except Exception as e:
            results[f"{func_name}_{idx}"] = {"error": str(e)}
    
    return results


# ============================================================
# consult_susi 함수 구현
# ============================================================

# 수시 데이터 캐시 (싱글톤)
_SUSI_DATA_CACHE = None

def _load_susi_data() -> List[Dict]:
    """
    수시 전형결과 JSON 데이터 로드 (캐싱)
    """
    global _SUSI_DATA_CACHE
    if _SUSI_DATA_CACHE is not None:
        return _SUSI_DATA_CACHE
    
    # JSON 파일 경로 (프로젝트 루트 기준)
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    json_path = os.path.join(project_root, "FINAL_nesin_detail_complete_31970.json")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            _SUSI_DATA_CACHE = json.load(f)
        print(f"✅ 수시 데이터 로드 완료: {len(_SUSI_DATA_CACHE)}개 항목")
        return _SUSI_DATA_CACHE
    except Exception as e:
        print(f"⚠️ 수시 데이터 로드 실패: {e}")
        return []


def _normalize_junhyung(junhyung: str) -> List[str]:
    """
    전형명 정규화 - 다양한 형태의 전형명을 비교 가능한 키워드로 변환
    
    예시:
    - "[교과]가야인재" -> ["교과", "가야인재"]
    - "교과위주" -> ["교과"]
    - "학생부종합전형" -> ["학생부종합", "종합"]
    """
    if not junhyung:
        return []
    
    keywords = []
    
    # 대괄호 안의 내용 추출 (예: [교과], [종합])
    import re
    bracket_match = re.search(r'\[([^\]]+)\]', junhyung)
    if bracket_match:
        keywords.append(bracket_match.group(1))
    
    # 대괄호 제거 후 나머지 부분
    clean_name = re.sub(r'\[[^\]]+\]', '', junhyung).strip()
    if clean_name:
        keywords.append(clean_name)
    
    # 일반적인 전형 유형 키워드 매핑
    junhyung_lower = junhyung.lower()
    
    if "교과" in junhyung_lower:
        keywords.append("교과")
        keywords.append("교과위주")
        keywords.append("교과전형")
    if "종합" in junhyung_lower:
        keywords.append("종합")
        keywords.append("학생부종합")
        keywords.append("학생부종합전형")
    if "일반" in junhyung_lower:
        keywords.append("일반")
        keywords.append("일반전형")
        keywords.append("일반학생")
    if "지역인재" in junhyung_lower:
        keywords.append("지역인재")
    if "농어촌" in junhyung_lower:
        keywords.append("농어촌")
    if "특성화" in junhyung_lower:
        keywords.append("특성화")
    if "기초생활" in junhyung_lower:
        keywords.append("기초생활")
    
    return list(set(keywords))


def _match_junhyung(data_jeonhyung: str, data_type: str, search_junhyungs: List[str]) -> bool:
    """
    전형명 매칭 - jeonhyung(JSON 형식)과 전형_유형 두 가지 모두 비교
    
    Args:
        data_jeonhyung: JSON의 jeonhyung 필드 (예: "[교과]가야인재")
        data_type: JSON의 전형_유형 필드 (예: "교과위주")
        search_junhyungs: 검색할 전형명 리스트 (예: ["교과전형", "학생부종합전형"])
    """
    if not search_junhyungs:
        return True  # 전형 조건 없으면 모두 매칭
    
    # 데이터의 전형 키워드 추출
    data_keywords = _normalize_junhyung(data_jeonhyung)
    if data_type:
        data_keywords.extend(_normalize_junhyung(data_type))
    data_keywords = [k.lower() for k in data_keywords]
    
    # 검색 전형의 키워드 추출
    for search_j in search_junhyungs:
        search_keywords = _normalize_junhyung(search_j)
        search_keywords = [k.lower() for k in search_keywords]
        
        # 하나라도 매칭되면 True
        for sk in search_keywords:
            for dk in data_keywords:
                if sk in dk or dk in sk:
                    return True
    
    return False


def _get_cut_score(item: Dict) -> Tuple[Optional[float], str]:
    """
    70%컷 우선, 없으면 80%컷, 없으면 90%컷 반환
    
    Returns:
        (점수, 컷 종류) - 예: (3.88, "70%컷")
    """
    cut_70 = item.get("내신등급_70%")
    cut_80 = item.get("내신등급_80%")
    cut_90 = item.get("내신등급_90%")
    
    if cut_70 is not None:
        try:
            return float(cut_70), "70%컷"
        except (ValueError, TypeError):
            pass
    
    if cut_80 is not None:
        try:
            return float(cut_80), "80%컷"
        except (ValueError, TypeError):
            pass
    
    if cut_90 is not None:
        try:
            return float(cut_90), "90%컷"
        except (ValueError, TypeError):
            pass
    
    return None, ""


async def _execute_consult_susi(params: Dict) -> Dict[str, Any]:
    """
    수시 전형결과 조회 함수
    
    Args:
        params: {
            "s_scores": [1.4, 1.1],  # 현재 내신, 목표 내신
            "university": ["서울대학교"],
            "junhyung": ["교과전형", "학생부종합전형"],
            "department": ["기계공학과"]
        }
    
    Returns:
        {
            "chunks": [...],
            "count": N,
            "query": "수시 전형결과 조회",
            ...
        }
    """
    # 파라미터 추출
    s_scores = params.get("s_scores", [])
    universities = params.get("university", [])
    junhyungs = params.get("junhyung", [])
    departments = params.get("department", [])
    
    # 리스트가 아닌 경우 리스트로 변환
    if not isinstance(universities, list):
        universities = [universities] if universities else []
    if not isinstance(junhyungs, list):
        junhyungs = [junhyungs] if junhyungs else []
    if not isinstance(departments, list):
        departments = [departments] if departments else []
    
    # 내신 점수 파싱 (5등급제 → 9등급제 자동 환산 포함)
    current_score = None
    target_score = None
    current_grade_system = "9등급제"
    target_grade_system = "9등급제"
    
    if s_scores:
        if isinstance(s_scores, list):
            if len(s_scores) >= 1 and s_scores[0]:
                current_score, current_grade_system = parse_score_with_grade_system(s_scores[0])
            if len(s_scores) >= 2 and s_scores[1]:
                target_score, target_grade_system = parse_score_with_grade_system(s_scores[1])
        else:
            current_score, current_grade_system = parse_score_with_grade_system(s_scores)
    
    # 디버그 로그: 5등급제 환산 여부 출력
    if current_grade_system == "5등급제" or target_grade_system == "5등급제":
        print(f"📊 5등급제 → 9등급제 환산 적용됨")
        if current_score and current_grade_system == "5등급제":
            print(f"   현재 내신: {s_scores[0] if isinstance(s_scores, list) else s_scores} → {current_score} (9등급제)")
        if target_score and target_grade_system == "5등급제":
            print(f"   목표 내신: {s_scores[1]} → {target_score} (9등급제)")
    
    # 비교할 내신 점수 결정 (목표 내신 우선, 없으면 현재 내신)
    compare_score = target_score if target_score else current_score
    
    # 데이터 로드
    susi_data = _load_susi_data()
    if not susi_data:
        return {
            "chunks": [],
            "count": 0,
            "query": "수시 전형결과 조회",
            "error": "수시 데이터를 로드할 수 없습니다."
        }
    
    # 필터링
    filtered_results = []
    
    for item in susi_data:
        # 대학 필터
        if universities:
            item_univ = item.get("university", "")
            matched = False
            for u in universities:
                # 정확한 매칭 우선
                if u == item_univ:
                    matched = True
                    break
                
                # 캠퍼스 표기 처리 (예: "서울대학교" -> "서울대학교(서울)" 매칭)
                if item_univ.startswith(u + "(") or item_univ.startswith(u.replace("학교", "") + "("):
                    matched = True
                    break
                
                # 약칭 -> 정식명칭 매칭 (예: "서울대" -> "서울대학교")
                if not u.endswith("학교"):
                    full_name = u + "학교"
                    if full_name == item_univ or item_univ.startswith(full_name + "("):
                        matched = True
                        break
                
                # 정식명칭 -> 약칭 매칭 (예: "서울대학교" -> "서울대")
                if u.endswith("학교"):
                    short_name = u[:-2]  # "학교" 제거
                    # 정확히 약칭+학교 형태인지 확인 (남서울대학교 != 서울대학교)
                    if item_univ == u or item_univ.startswith(u + "("):
                        matched = True
                        break
                
            if not matched:
                continue
        
        # 전형 필터 (jeonhyung과 전형_유형 모두 비교)
        if junhyungs:
            if not _match_junhyung(
                item.get("jeonhyung", ""),
                item.get("전형_유형", ""),
                junhyungs
            ):
                continue
        
        # 학과 필터
        if departments:
            item_dept = item.get("department", "")
            matched = False
            for d in departments:
                if d in item_dept or item_dept in d:
                    matched = True
                    break
            if not matched:
                continue
        
        # 컷 점수 가져오기
        cut_score, cut_type = _get_cut_score(item)
        
        # 결과에 추가
        filtered_results.append({
            "university": item.get("university", ""),
            "department": item.get("department", ""),
            "jeonhyung": item.get("jeonhyung", ""),
            "전형_유형": item.get("전형_유형", ""),
            "모집인원": item.get("모집인원", ""),
            "2025_경쟁률": item.get("2025_경쟁률", ""),
            "2024_경쟁률": item.get("2024_경쟁률", ""),
            "충원현황": item.get("충원현황", ""),
            "내신등급_70%": item.get("내신등급_70%"),
            "내신등급_80%": item.get("내신등급_80%"),
            "내신등급_90%": item.get("내신등급_90%"),
            "cut_score": cut_score,
            "cut_type": cut_type,
            "url": item.get("url", ""),
        })
    
    # 내신 점수가 있으면 비슷한 순으로 정렬
    if compare_score is not None:
        # 컷 점수가 있는 항목만 정렬 대상
        with_cut = [r for r in filtered_results if r["cut_score"] is not None]
        without_cut = [r for r in filtered_results if r["cut_score"] is None]
        
        # 내신 점수와 컷 점수의 차이가 작은 순으로 정렬
        with_cut.sort(key=lambda x: abs(x["cut_score"] - compare_score))
        
        filtered_results = with_cut + without_cut
    
    # 토큰 제한 적용 (최대 100개 결과)
    MAX_RESULTS = 100
    filtered_results = filtered_results[:MAX_RESULTS]
    
    # 청크 생성
    chunks = []
    
    # 청크 1: 검색 조건 요약
    condition_parts = []
    if universities:
        condition_parts.append(f"대학: {', '.join(universities)}")
    if junhyungs:
        condition_parts.append(f"전형: {', '.join(junhyungs)}")
    if departments:
        condition_parts.append(f"학과: {', '.join(departments)}")
    if current_score:
        condition_parts.append(f"현재 내신: {current_score}")
    if target_score:
        condition_parts.append(f"목표 내신: {target_score}")
    
    condition_text = "**수시 전형결과 검색 조건**\n" + "\n".join(condition_parts) if condition_parts else "**수시 전형결과 검색** (전체)"
    
    chunks.append({
        "document_id": "susi_search_condition",
        "chunk_id": "search_condition",
        "section_id": "search_condition",
        "chunk_type": "search_condition",
        "content": condition_text,
        "page_number": ""
    })
    
    # 청크 2: 검색 결과 테이블
    if filtered_results:
        table_header = "**수시 전형결과**\n| 대학 | 학과 | 전형 | 전형유형 | 모집인원 | 2025경쟁률 | 충원 | 70%컷 | 80%컷 | 90%컷 | 판정 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
        table_rows = []
        
        for r in filtered_results:
            # 판정 계산
            judgment = ""
            if compare_score is not None and r["cut_score"] is not None:
                diff = compare_score - r["cut_score"]
                if diff <= -0.5:
                    judgment = "안정"
                elif diff <= 0:
                    judgment = "적정"
                elif diff <= 0.3:
                    judgment = "소신"
                elif diff <= 0.5:
                    judgment = "도전"
                else:
                    judgment = "어려움"
            
            row = "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                r["university"],
                r["department"],
                r["jeonhyung"],
                r["전형_유형"],
                r["모집인원"] or "-",
                r["2025_경쟁률"] or "-",
                r["충원현황"] or "-",
                r["내신등급_70%"] if r["내신등급_70%"] else "-",
                r["내신등급_80%"] if r["내신등급_80%"] else "-",
                r["내신등급_90%"] if r["내신등급_90%"] else "-",
                judgment
            )
            table_rows.append(row)
        
        result_content = table_header + "\n" + "\n".join(table_rows)
        chunks.append({
            "document_id": "susi_results",
            "chunk_id": "susi_table",
            "section_id": "susi_table",
            "chunk_type": "susi_results",
            "content": result_content,
            "page_number": ""
        })
    
    # 출처 정보
    document_titles = {
        "susi_search_condition": "수시 전형결과 검색 조건",
        "susi_results": "2025학년도 수시 전형결과 (자체 DB)"
    }
    document_urls = {
        "susi_search_condition": "",
        "susi_results": ""
    }
    
    return {
        "chunks": chunks,
        "count": len(filtered_results),
        "query": "수시 전형결과 조회",
        "document_titles": document_titles,
        "document_urls": document_urls,
        "universities": universities,
        "junhyungs": junhyungs,
        "departments": departments,
        "s_scores": s_scores,
        "total_results": len(filtered_results),
    }
