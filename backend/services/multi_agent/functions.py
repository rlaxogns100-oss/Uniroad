"""
RAG Functions
- Supabase 기반 유사도 검색
- uniroad_recommed_1/core/rag_system.py의 search_global_raw 로직 이식
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# GEMINI_API_KEY를 GOOGLE_API_KEY로 매핑 (langchain 호환)
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

from services.supabase_client import SupabaseService
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# 업로드와 동일한 임베딩 모델 사용 (768차원, DB vector(768)와 일치)
try:
    from config import embedding_settings as embedding_config
    _DEFAULT_EMBEDDING_MODEL = getattr(embedding_config, "DEFAULT_EMBEDDING_MODEL", "models/text-embedding-004")
except Exception:
    _DEFAULT_EMBEDDING_MODEL = "models/text-embedding-004"


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
            unique_ids = list(set(document_ids))
            response = self.supabase.table("documents").select("id, embedding_summary, summary, filename, file_url").in_("id", unique_ids).execute()
            
            result = {}
            for doc in response.data:
                emb_str = doc.get("embedding_summary")
                summary = doc.get("summary", "")
                # filename에서 PDF 확장자 제거하여 title로 사용
                filename = doc.get("filename", "")
                title = filename.replace(".pdf", "").replace(".PDF", "") if filename else ""
                file_url = doc.get("file_url", "")  # PDF 다운로드 URL
                
                embedding = None
                if emb_str:
                    # vector 타입 → 문자열 → 리스트 변환
                    if isinstance(emb_str, str):
                        embedding = json.loads(emb_str)
                    else:
                        embedding = emb_str
                
                result[doc["id"]] = {
                    "embedding": embedding,
                    "summary": summary,
                    "title": title,
                    "file_url": file_url
                }
            return result
        except Exception as e:
            print(f"⚠️ Document 정보 조회 실패: {e}")
            return {}
    
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
        
        # 쿼리 임베딩 1회 생성 (업로드와 동일한 모델: text-embedding-004, 768차원)
        query_embedding = self.embeddings.embed_query(query)
        # 학교명 변형으로 검색 (연세대/연세대학교 등 업로드 폴더명·채팅 정식명 모두 매칭)
        all_documents = []
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
            print("⚠️ 검색 결과 없음")
            return {"chunks": [], "count": 0, "university": university, "query": query}
        
        print(f"✅ 초기 검색: {len(documents)}개 문서")
        
        # Step 3: document_id로 문서 정보 조회 (embedding + summary)
        doc_ids = [d["metadata"].get("document_id") for d in documents if d["metadata"].get("document_id")]
        document_info = self._get_document_info(doc_ids)
        
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


async def execute_function_calls(function_calls: List[Dict]) -> Dict[str, Any]:
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
                result = await rag.univ(
                    university=params.get("university", ""),
                    query=params.get("query", "")
                )
                results[f"univ_{idx}"] = result
            
            elif func_name == "consult":
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
                
                CONSULT_TOKEN_LIMIT = 40960  # consult는 40960 토큰
                
                # 1. router_agent의 scores 형식 변환
                # 간단 형식: {"국어": 1, "수학": 2} → 표준 형식: {"국어": {"type": "등급", "value": 1}}
                raw_scores = params.get("scores", {})
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
                
                # 3. 파라미터 추출
                target_univ = params.get("target_univ", []) or []
                target_major = params.get("target_major", []) or []
                target_range = params.get("target_range", []) or []
                
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
                
                # 5. chunk 기반 결과 생성 (토큰 제한 적용)
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
                
                # 청크 2: 리버스 서치 결과 (admission_results)
                # 새로운 테이블 형식: 대학 | 학과 | 군 | 계열 | 내 점수 | 안정컷 | 적정컷 | 소신컷 | 도전컷 | 판정
                if reverse_results:
                    table_header = "**지원 가능 대학 분석 (86개 대학, 2158개 학과)**\n| 대학 | 학과 | 군 | 계열 | 내 점수 | 안정컷 | 적정컷 | 소신컷 | 도전컷 | 판정 |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
                    table_rows = []
                    
                    remaining_tokens = CONSULT_TOKEN_LIMIT - total_tokens
                    header_tokens = estimate_tokens(table_header)
                    current_tokens = header_tokens
                    
                    for r in reverse_results:
                        row = "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                            r.get("univ", ""),
                            r.get("major", ""),
                            r.get("gun", ""),
                            r.get("track", "") or r.get("field", ""),
                            r.get("my_score", ""),
                            r.get("safe_score", "") if r.get("safe_score") else "—",
                            r.get("appropriate_score", "") if r.get("appropriate_score") else "—",
                            r.get("expected_score", "") if r.get("expected_score") else "—",
                            r.get("challenge_score", "") if r.get("challenge_score") else "—",
                            r.get("판정", ""),
                        )
                        row_tokens = estimate_tokens(row)
                        
                        if current_tokens + row_tokens <= remaining_tokens:
                            table_rows.append(row)
                            current_tokens += row_tokens
                        else:
                            break  # 토큰 제한 도달
                    
                    if table_rows:
                        reverse_content = table_header + "\n" + "\n".join(table_rows)
                        chunks.append({
                            "document_id": "admission_results",
                            "chunk_id": "reverse_search",
                            "section_id": "reverse_search",
                            "chunk_type": "reverse_search",
                            "content": reverse_content,
                            "page_number": ""
                        })
                        total_tokens += current_tokens
                
                # 출처 정보
                document_titles = {
                    "score_conversion": "2026 수능 표준점수 및 백분위 산출 방식",
                    "admission_results": "2026학년도 정시 배치표 (86개 대학)"
                }
                document_urls = {
                    "score_conversion": "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/5d5c4455-bf58-4ef5-9e7f-a82d602aaa51.pdf",
                    "admission_results": "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/b26bc045-e96b-4d3a-acb2-ac677633c685.pdf"
                }
                
                results[f"consult_{idx}"] = {
                    "chunks": chunks,
                    "count": len(chunks),
                    "university": "",
                    "query": "성적 분석",
                    "document_titles": document_titles,
                    "document_urls": document_urls,
                    "target_univ": target_univ,
                    "target_major": target_major,
                    "total_tokens": total_tokens,
                    "total_universities": 86,
                    "total_departments": len(reverse_results),
                }
            
            else:
                results[f"{func_name}_{idx}"] = {"error": f"Unknown function: {func_name}"}
        
        except Exception as e:
            results[f"{func_name}_{idx}"] = {"error": str(e)}
    
    return results
