"""
임베딩 생성 & 텍스트 청킹 서비스
"""
import google.generativeai as genai
from config import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List
import asyncio


class EmbeddingService:
    """Gemini 임베딩 생성 및 텍스트 청킹"""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.embedding_model = "text-embedding-004"
        self.embedding_dimension = 768  # Gemini 임베딩 차원
    
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1200,
        chunk_overlap: int = 200
    ) -> List[str]:
        """
        텍스트를 의미 단위로 청킹
        
        Args:
            text: 원본 텍스트
            chunk_size: 청크 크기
            chunk_overlap: 중복 크기
        
        Returns:
            청크 리스트
        """
        print(f"\n📦 텍스트 청킹 시작...")
        print(f"   원본 크기: {len(text):,}자")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        
        chunks = splitter.split_text(text)
        
        print(f"   ✅ {len(chunks)}개 청크 생성")
        if len(chunks) > 0:
            print(f"   평균 크기: {sum(len(c) for c in chunks) // len(chunks):,}자\n")
        else:
            print(f"   ⚠️ 청크가 생성되지 않았습니다\n")
        
        return chunks
    
    async def create_embedding(self, text: str) -> List[float]:
        """단일 텍스트의 임베딩 생성"""
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"❌ 임베딩 생성 오류: {e}")
            raise
    
    async def create_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        여러 텍스트의 임베딩을 병렬로 생성 (Gemini)
        
        Args:
            texts: 텍스트 리스트
            batch_size: 병렬 처리 개수
        
        Returns:
            임베딩 벡터 리스트
        """
        print(f"\n⚡ Gemini 임베딩 생성 시작...")
        print(f"   총 {len(texts)}개 청크")
        print(f"   병렬 처리: {batch_size}개씩\n")
        
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            print(f"   🔄 배치 {batch_num}/{total_batches} 병렬 처리 중...")
            
            try:
                # 병렬 처리
                tasks = [self.create_embedding(text) for text in batch]
                batch_embeddings = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 예외 처리
                for idx, emb in enumerate(batch_embeddings):
                    if isinstance(emb, Exception):
                        print(f"   ⚠️ 청크 {i+idx+1} 실패, 재시도 중...")
                        try:
                            emb = await self.create_embedding(batch[idx])
                            embeddings.append(emb)
                        except:
                            embeddings.append([0.0] * self.embedding_dimension)
                    else:
                        embeddings.append(emb)
                
                print(f"   ✅ 배치 {batch_num} 완료 ({len(batch)}개)")
                
            except Exception as e:
                print(f"   ❌ 배치 {batch_num} 전체 실패: {e}")
                # 개별 처리
                for text in batch:
                    try:
                        emb = await self.create_embedding(text)
                        embeddings.append(emb)
                    except:
                        embeddings.append([0.0] * self.embedding_dimension)
        
        print(f"\n✅ 임베딩 생성 완료: {len(embeddings)}개\n")
        return embeddings


# 전역 인스턴스
embedding_service = EmbeddingService()

