"""
Supabase 클라이언트 서비스
"""
from supabase import create_client, Client
from config import settings
from typing import Optional


class SupabaseService:
    """Supabase 클라이언트 관리"""
    
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """싱글톤 패턴으로 Supabase 클라이언트 반환"""
        if cls._instance is None:
            cls._instance = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
        return cls._instance
    
    @property
    def client(self) -> Client:
        """인스턴스에서 client 속성으로 접근 가능하도록"""
        return self.get_client()
    
    @classmethod
    def upload_pdf_to_storage(
        cls,
        file_bytes: bytes,
        file_name: str
    ) -> Optional[tuple]:
        """
        PDF를 Supabase Storage에 업로드
        
        Returns:
            (storage_file_name, public_url) 튜플 (성공 시) 또는 None (실패 시)
        """
        import uuid
        client = cls.get_client()
        
        try:
            # UUID로 고유한 파일명 생성 (한글 파일명 문제 회피)
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'pdf'
            storage_file_name = f"{uuid.uuid4()}.{file_extension}"
            storage_path = f"pdfs/{storage_file_name}"
            
            # 기존 파일이 있으면 삭제
            try:
                client.storage.from_('document').remove([storage_path])
            except:
                pass  # 파일이 없으면 무시
            
            # 새 파일 업로드
            client.storage.from_('document').upload(
                storage_path,
                file_bytes,
                file_options={
                    "content-type": "application/pdf",
                    "x-upsert": "true"
                }
            )
            
            # Public URL 생성
            public_url = client.storage.from_('document').get_public_url(storage_path)
            
            print(f"✅ PDF Storage 업로드 완료: {storage_path}")
            print(f"   원본 파일명: {file_name}")
            return (storage_file_name, public_url)
        except Exception as e:
            print(f"❌ PDF Storage 업로드 오류: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @classmethod
    async def insert_document_metadata(
        cls,
        file_name: str,
        storage_file_name: str,
        title: str,
        source: str,
        summary: str,
        total_pages: int,
        total_chunks: int,
        file_url: Optional[str] = None,
        hashtags: Optional[list] = None
    ) -> bool:
        """문서 메타데이터 삽입 (파일당 1개)"""
        client = cls.get_client()

        try:
            data = {
                'file_name': file_name,  # 원본 파일명 (한글 가능)
                'storage_file_name': storage_file_name,  # Storage에 저장된 UUID 파일명
                'title': title,
                'source': source,
                'summary': summary,
                'total_pages': total_pages,
                'total_chunks': total_chunks
            }
            
            # file_url이 있으면 추가
            if file_url:
                data['file_url'] = file_url
            
            # hashtags가 있으면 추가
            if hashtags:
                data['hashtags'] = hashtags
            
            response = client.table('documents_metadata').insert(data).execute()

            return True
        except Exception as e:
            print(f"❌ 문서 메타데이터 삽입 오류: {e}")
            return False

    @classmethod
    async def insert_document_chunk(
        cls,
        content: str,
        embedding: list[float],
        metadata: dict
    ) -> bool:
        """문서 청크 삽입 (간소화된 metadata)"""
        client = cls.get_client()

        try:
            # 임베딩을 PostgreSQL vector 형식으로 변환
            # [0.1, 0.2, 0.3] -> "[0.1,0.2,0.3]" (공백 없이)
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'

            response = client.table('policy_documents').insert({
                'content': content,
                'embedding': embedding_str,  # 문자열로 변환
                'metadata': metadata
            }).execute()

            return True
        except Exception as e:
            print(f"❌ 문서 청크 삽입 오류: {e}")
            return False
    
    @classmethod
    async def update_document_metadata(
        cls,
        file_name: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        hashtags: Optional[list] = None
    ) -> bool:
        """문서 메타데이터 수정"""
        client = cls.get_client()
        
        try:
            update_data = {}
            if title is not None:
                update_data['title'] = title
            if source is not None:
                update_data['source'] = source
            if hashtags is not None:
                update_data['hashtags'] = hashtags
            
            if not update_data:
                return True  # 수정할 내용 없음
            
            client.table('documents_metadata')\
                .update(update_data)\
                .eq('file_name', file_name)\
                .execute()
            
            print(f"✅ 문서 메타데이터 수정 완료: {file_name}")
            if hashtags is not None:
                print(f"   해시태그: {hashtags}")
            return True
        except Exception as e:
            print(f"❌ 문서 메타데이터 수정 오류: {e}")
            return False
    
    @classmethod
    async def get_documents(cls) -> list[dict]:
        """업로드된 문서 목록 조회 (documents_metadata 테이블에서)"""
        client = cls.get_client()

        try:
            # documents_metadata 테이블에서 직접 조회
            response = client.table('documents_metadata')\
                .select('*')\
                .order('created_at', desc=True)\
                .execute()

            if not response.data:
                return []

            # 응답 형식 맞추기
            documents = []
            for row in response.data:
                documents.append({
                    'id': row['file_name'],  # file_name을 id로 사용
                    'title': row['title'],
                    'source': row.get('source', 'Unknown'),
                    'fileName': row['file_name'],
                    'fileUrl': row.get('file_url'),  # 다운로드 URL
                    'category': '미분류',  # 나중에 추가 예정
                    'uploadedAt': row['created_at'],
                    'hashtags': row.get('hashtags', [])  # 해시태그
                })

            return documents
        except Exception as e:
            print(f"❌ 문서 목록 조회 오류: {e}")
            return []
    
    @classmethod
    async def delete_document(cls, document_id: str) -> bool:
        """
        문서 삭제 (documents_metadata + 모든 청크)
        document_id는 file_name
        """
        print(f"\n{'='*60}")
        print(f"🗑️  문서 삭제 시작")
        print(f"{'='*60}")
        print(f"파일명: {document_id}")

        client = cls.get_client()

        try:
            # 1. documents_metadata에서 문서 정보 조회
            print(f"\n1단계: 문서 메타데이터 조회 중...")
            meta_response = client.table('documents_metadata')\
                .select('*')\
                .eq('file_name', document_id)\
                .execute()

            if not meta_response.data or len(meta_response.data) == 0:
                print(f"❌ 문서를 찾을 수 없음: {document_id}")
                print(f"{'='*60}\n")
                return False

            doc_info = meta_response.data[0]
            title = doc_info.get('title', 'Unknown')
            total_chunks = doc_info.get('total_chunks', 0)

            print(f"✅ 문서 정보 확인:")
            print(f"   제목: {title}")
            print(f"   총 청크: {total_chunks}개")

            # 2. policy_documents에서 모든 청크 삭제
            print(f"\n2단계: 모든 청크 삭제 중...")
            chunks_response = client.table('policy_documents')\
                .delete()\
                .eq('metadata->>fileName', document_id)\
                .execute()

            print(f"   ✅ 청크 삭제 완료")

            # 3. Storage에서 PDF 파일 삭제
            print(f"\n3단계: Storage에서 PDF 삭제 중...")
            try:
                import urllib.parse
                encoded_file_name = urllib.parse.quote(document_id)
                storage_path = f"pdfs/{encoded_file_name}"
                client.storage.from_('document').remove([storage_path])
                print(f"   ✅ PDF 파일 삭제 완료")
            except Exception as storage_error:
                print(f"   ⚠️ PDF 파일 삭제 실패 (파일이 없을 수 있음): {storage_error}")

            # 4. documents_metadata 삭제
            print(f"\n4단계: 문서 메타데이터 삭제 중...")
            metadata_response = client.table('documents_metadata')\
                .delete()\
                .eq('file_name', document_id)\
                .execute()

            print(f"\n✅ 문서 삭제 완료!")
            print(f"   파일명: {document_id}")
            print(f"   제목: {title}")
            print(f"{'='*60}\n")
            return True

        except Exception as e:
            print(f"\n❌ 문서 삭제 오류: {e}")
            print(f"{'='*60}\n")
            import traceback
            traceback.print_exc()
            return False
    
    @classmethod
    async def insert_chat_log(
        cls,
        message: str,
        response: str,
        is_fact_mode: bool = False
    ) -> bool:
        """채팅 로그 저장"""
        client = cls.get_client()
        
        try:
            client.table('chat_logs').insert({
                'message': message,
                'response': response,
                'is_fact_mode': is_fact_mode,
                'user_id': None  # 비회원
            }).execute()
            
            return True
        except Exception as e:
            print(f"❌ 채팅 로그 저장 오류: {e}")
            return False


# 전역 인스턴스
supabase_service = SupabaseService()

