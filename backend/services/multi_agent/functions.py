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


class RAGFunctions:
    """RAG 검색 함수 클래스"""
    
    _instance = None
    
    def __init__(self):
        self.supabase = SupabaseService.get_client()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            request_timeout=600,
        )
    
    @classmethod
    def get_instance(cls):
        """싱글톤 인스턴스"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _supabase_search(
        self, 
        query: str, 
        school_name: str, 
        top_k: int = 30
    ) -> Tuple[List[Dict], List[float]]:
        """
        Step 1-2: Supabase RPC로 벡터 검색
        원본: uniroad_recommed_1/core/searcher.py (72-168줄)
        
        Returns:
            Tuple[documents, query_embedding] - 문서 리스트와 쿼리 임베딩 (재사용 위해)
        """
        # 쿼리 임베딩 생성 (재사용을 위해 반환)
        query_embedding = self.embeddings.embed_query(query)
        
        # RPC 호출
        rpc_params = {
            "filter_school_name": school_name,
            "filter_section_id": None,  # 전역 검색
            "match_count": top_k,
            "match_threshold": 0.0,
            "query_embedding": query_embedding,
        }
        
        response = self.supabase.rpc("match_document_chunks", rpc_params).execute()
        
        if not response.data:
            return [], query_embedding
        
        # Document 형태로 변환
        documents = []
        for row in response.data:
            # Context Swap: raw_data 우선 사용
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
        
        return documents, query_embedding
    
    def _get_summary_embeddings(self, document_ids: List[int]) -> Dict[int, List[float]]:
        """
        Step 3: documents 테이블에서 embedding_summary 조회
        - 실시간 임베딩 계산 없이 DB에 저장된 벡터 사용
        - Supabase는 vector 타입을 문자열로 반환하므로 json.loads() 필요
        """
        if not document_ids:
            return {}
        
        try:
            unique_ids = list(set(document_ids))
            response = self.supabase.table("documents").select("id, embedding_summary").in_("id", unique_ids).execute()
            
            result = {}
            for doc in response.data:
                emb_str = doc.get("embedding_summary")
                if emb_str:
                    # vector 타입 → 문자열 → 리스트 변환
                    if isinstance(emb_str, str):
                        result[doc["id"]] = json.loads(emb_str)
                    else:
                        result[doc["id"]] = emb_str
            return result
        except Exception as e:
            print(f"⚠️ Summary 임베딩 조회 실패: {e}")
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
        
        # Step 1-2: Supabase 벡터 검색 (30개) + 쿼리 임베딩 재사용
        documents, query_embedding = self._supabase_search(query, university, top_k)
        
        if not documents:
            print("⚠️ 검색 결과 없음")
            return {"chunks": [], "count": 0, "university": university, "query": query}
        
        print(f"✅ 초기 검색: {len(documents)}개 문서")
        
        # Step 3: document_id로 summary 임베딩 조회 (DB에서 미리 계산된 벡터)
        doc_ids = [d["metadata"].get("document_id") for d in documents if d["metadata"].get("document_id")]
        summary_embeddings = self._get_summary_embeddings(doc_ids)
        
        # Step 4: 쿼리 임베딩은 Step 1-2에서 재사용 (중복 제거)
        
        # Step 5: 가중 평균 유사도 계산
        scored_chunks = []
        for doc in documents:
            meta = doc["metadata"]
            content_similarity = meta.get("score", 0.0)
            
            # Summary 유사도 계산 (DB에서 가져온 임베딩 직접 사용)
            summary_similarity = 0.0
            doc_id = meta.get("document_id")
            if doc_id and doc_id in summary_embeddings:
                summary_embedding = summary_embeddings[doc_id]
                summary_similarity = self._cosine_similarity(query_embedding, summary_embedding)
            
            # 가중 평균
            weighted = (content_similarity * content_weight) + (summary_similarity * summary_weight)
            
            scored_chunks.append({
                "doc": doc,
                "weighted_score": weighted,
                "content_score": content_similarity,
                "summary_score": summary_similarity
            })
        
        # Step 6: 정렬 후 상위 10개
        scored_chunks.sort(key=lambda x: x["weighted_score"], reverse=True)
        top_10 = scored_chunks[:10]
        
        print(f"📊 가중 평균 계산 완료: 상위 10개 선택")
        
        # Step 7: 결과 포맷팅
        results = []
        for item in top_10:
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
        
        return {
            "chunks": results,
            "count": len(results),
            "university": university,
            "query": query
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
                # TODO: consult 함수 구현
                results[f"consult_{idx}"] = {"status": "not_implemented"}
            
            else:
                results[f"{func_name}_{idx}"] = {"error": f"Unknown function: {func_name}"}
        
        except Exception as e:
            results[f"{func_name}_{idx}"] = {"error": str(e)}
    
    return results
