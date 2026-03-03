"""
Supabase 클라이언트 서비스
"""
from supabase import create_client, Client
from config import settings
from config import embedding_settings as embedding_config
from typing import Optional, Dict, Any, List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
import os


class SupabaseService:
    """Supabase 클라이언트 관리"""
    
    _instance: Optional[Client] = None
    _admin_instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """싱글톤 패턴으로 Supabase 클라이언트 반환 (일반 사용자)"""
        if cls._instance is None:
            cls._instance = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
        return cls._instance
    
    @classmethod
    def get_admin_client(cls) -> Client:
        """관리자 권한 Supabase 클라이언트 반환 (서비스 역할 키)"""
        if cls._admin_instance is None:
            # 서비스 역할 키가 있으면 사용, 없으면 일반 키 사용
            service_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
            cls._admin_instance = create_client(
                settings.SUPABASE_URL,
                service_key
            )
        return cls._admin_instance
    
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
    def upload_avatar_to_storage(cls, user_id: str, file_bytes: bytes, content_type: str) -> Optional[str]:
        """
        프로필 이미지를 Storage에 업로드 (document/avatars/).
        Returns: public URL 또는 None
        """
        import uuid
        client = cls.get_client()
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "gif" in content_type:
            ext = "gif"
        elif "webp" in content_type:
            ext = "webp"
        storage_name = f"{user_id}_{uuid.uuid4().hex[:12]}.{ext}"
        storage_path = f"avatars/{storage_name}"
        try:
            client.storage.from_("document").upload(
                storage_path,
                file_bytes,
                file_options={"content-type": content_type, "x-upsert": "true"}
            )
            public_url = client.storage.from_("document").get_public_url(storage_path)
            print(f"✅ Avatar Storage 업로드 완료: {storage_path}")
            return public_url
        except Exception as e:
            print(f"❌ Avatar Storage 업로드 오류: {e}")
            return None

    @classmethod
    def upload_banner_to_storage(cls, user_id: str, file_bytes: bytes, content_type: str) -> Optional[str]:
        """
        프로필 배경 이미지를 Storage에 업로드 (document/banners/).
        Returns: public URL 또는 None
        """
        import uuid
        client = cls.get_client()
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "gif" in content_type:
            ext = "gif"
        elif "webp" in content_type:
            ext = "webp"
        storage_name = f"{user_id}_{uuid.uuid4().hex[:12]}.{ext}"
        storage_path = f"banners/{storage_name}"
        try:
            client.storage.from_("document").upload(
                storage_path,
                file_bytes,
                file_options={"content-type": content_type, "x-upsert": "true"}
            )
            public_url = client.storage.from_("document").get_public_url(storage_path)
            print(f"✅ Banner Storage 업로드 완료: {storage_path}")
            return public_url
        except Exception as e:
            print(f"❌ Banner Storage 업로드 오류: {e}")
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
        hashtags: Optional[list] = None,
        school_name: Optional[str] = None
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
            
            # school_name이 있으면 추가
            if school_name:
                data['school_name'] = school_name
            
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
        """documents.metadata JSON을 수정"""
        client = cls.get_client()

        try:
            response = client.table('documents')\
                .select('metadata')\
                .eq('id', int(file_name))\
                .execute()

            if not response.data:
                return False

            metadata = response.data[0].get('metadata', {}) or {}
            if title is not None:
                metadata['title'] = title
            if source is not None:
                metadata['source'] = source
            if hashtags is not None:
                metadata['hashtags'] = hashtags

            client.table('documents')\
                .update({'metadata': metadata})\
                .eq('id', int(file_name))\
                .execute()

            print(f"✅ 문서 메타데이터 수정 완료: {file_name}")
            return True
        except Exception as e:
            print(f"❌ 문서 메타데이터 수정 오류: {e}")
            return False
    
    @classmethod
    async def get_documents(cls) -> list[dict]:
        """업로드된 문서 목록 조회 (documents 테이블에서)"""
        client = cls.get_client()

        try:
            response = client.table('documents')\
                .select('id, school_name, filename, summary, file_url, metadata')\
                .order('id', desc=True)\
                .execute()

            if not response.data:
                return []

            # 응답 형식 맞추기
            documents = []
            for row in response.data:
                metadata = row.get('metadata', {}) or {}
                title = metadata.get('title') or row.get('filename', '')
                documents.append({
                    'id': str(row['id']),
                    'title': title if title else row.get('filename', ''),
                    'source': metadata.get('source', 'Unknown'),
                    'fileName': row.get('filename', ''),
                    'fileUrl': row.get('file_url'),
                    'category': '미분류',
                    'uploadedAt': metadata.get('uploaded_at', ''),
                    'hashtags': metadata.get('hashtags', []),
                    'schoolName': row.get('school_name')
                })

            return documents
        except Exception as e:
            print(f"❌ 문서 목록 조회 오류: {e}")
            return []
    
    @classmethod
    async def delete_document(cls, document_id: str) -> bool:
        """
        문서 삭제 (documents + document_sections + document_chunks)
        document_id는 documents.id
        """
        print(f"\n{'='*60}")
        print(f"🗑️  문서 삭제 시작")
        print(f"{'='*60}")
        print(f"파일명: {document_id}")

        client = cls.get_client()

        try:
            # 1. documents에서 문서 정보 조회
            print(f"\n1단계: 문서 메타데이터 조회 중...")
            meta_response = client.table('documents')\
                .select('id, filename, file_url')\
                .eq('id', int(document_id))\
                .execute()

            if not meta_response.data or len(meta_response.data) == 0:
                print(f"❌ 문서를 찾을 수 없음: {document_id}")
                print(f"{'='*60}\n")
                return False

            doc_info = meta_response.data[0]
            title = doc_info.get('filename', 'Unknown')

            print(f"✅ 문서 정보 확인:")
            print(f"   제목: {title}")
            # 2. document_chunks에서 모든 청크 삭제
            print(f"\n2단계: 모든 청크 삭제 중...")
            client.table('document_chunks')\
                .delete()\
                .eq('document_id', int(document_id))\
                .execute()

            print(f"   ✅ 청크 삭제 완료")

            # 3. document_sections 삭제
            print(f"\n3단계: 문서 섹션 삭제 중...")
            client.table('document_sections')\
                .delete()\
                .eq('document_id', int(document_id))\
                .execute()

            # 4. documents 삭제
            print(f"\n4단계: 문서 메타데이터 삭제 중...")
            client.table('documents')\
                .delete()\
                .eq('id', int(document_id))\
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
    
    @classmethod
    async def get_user_profile(cls, user_id: str) -> Optional[dict]:
        """사용자 프로필 조회"""
        client = cls.get_client()
        
        try:
            response = client.table('user_profiles')\
                .select('*')\
                .eq('user_id', user_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ 프로필 조회 오류: {e}")
            return None
    
    @classmethod
    async def upsert_user_profile(cls, user_id: str, scores: dict) -> bool:
        """사용자 프로필 생성/수정 (upsert)"""
        client = cls.get_client()
        
        try:
            # upsert: user_id가 있으면 update, 없으면 insert
            response = client.table('user_profiles')\
                .upsert({
                    'user_id': user_id,
                    'scores': scores
                })\
                .execute()
            
            print(f"✅ 프로필 저장 완료: user_id={user_id}")
            return True
        except Exception as e:
            print(f"❌ 프로필 저장 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @classmethod
    async def delete_user_profile(cls, user_id: str) -> bool:
        """사용자 프로필 삭제"""
        client = cls.get_client()
        
        try:
            response = client.table('user_profiles')\
                .delete()\
                .eq('user_id', user_id)\
                .execute()
            
            print(f"✅ 프로필 삭제 완료: user_id={user_id}")
            return True
        except Exception as e:
            print(f"❌ 프로필 삭제 오류: {e}")
            return False

    @classmethod
    async def get_user_profile_metadata(cls, user_id: str) -> Optional[dict]:
        """user_profiles의 metadata만 조회 (서버/RLS bypass용 admin client)"""
        client = cls.get_admin_client()
        try:
            r = (
                client.table("user_profiles")
                .select("metadata")
                .eq("user_id", user_id)
                .execute()
            )
            if r.data and len(r.data) > 0:
                return r.data[0].get("metadata") or {}
            return {}
        except Exception as e:
            print(f"❌ get_user_profile_metadata 오류: {e}")
            return None

    @classmethod
    async def update_user_profile_metadata(
        cls, user_id: str, metadata_key: str, metadata_value: Any
    ) -> bool:
        """
        user_profiles.metadata의 특정 키만 병합 업데이트 (나머지 metadata 유지).
        예: metadata_key='school_record', metadata_value={ 'items': [...] }
        """
        if not user_id or not metadata_key:
            return False
        client = cls.get_admin_client()
        try:
            existing = (
                client.table("user_profiles")
                .select("user_id, scores, metadata")
                .eq("user_id", user_id)
                .execute()
            )
            meta = {}
            if existing.data and len(existing.data) > 0:
                row = existing.data[0]
                meta = dict(row.get("metadata") or {})
                meta[metadata_key] = metadata_value
                client.table("user_profiles").update({"metadata": meta}).eq(
                    "user_id", user_id
                ).execute()
            else:
                meta = {metadata_key: metadata_value}
                client.table("user_profiles").insert(
                    {"user_id": user_id, "scores": {}, "metadata": meta}
                ).execute()
            return True
        except Exception as e:
            print(f"❌ update_user_profile_metadata 오류: {e}")
            return False

    @staticmethod
    def _is_empty_json_value(val: Any) -> bool:
        """JSONB merge에서 '비어있음'으로 간주할 값 판정."""
        if val is None:
            return True
        if isinstance(val, str):
            return val.strip() == ""
        if isinstance(val, (dict, list)):
            return len(val) == 0
        return False

    @classmethod
    def _deep_merge_prefer_left(cls, left: Any, right: Any) -> Any:
        """
        left 값을 우선으로 두고, left가 비었을 때만 right로 채우는 deep merge.
        - dict: 키 단위로 재귀 병합
        - list: left가 비어있으면 right 사용
        - scalar: left가 비어있으면 right 사용
        """
        if isinstance(left, dict) and isinstance(right, dict):
            merged: Dict[str, Any] = {}
            keys = set(right.keys()) | set(left.keys())
            for k in keys:
                lv = left.get(k) if k in left else None
                rv = right.get(k) if k in right else None
                if k in left:
                    if isinstance(lv, dict) and isinstance(rv, dict):
                        merged[k] = cls._deep_merge_prefer_left(lv, rv)
                    elif isinstance(lv, list) and isinstance(rv, list):
                        merged[k] = rv if (len(lv) == 0 and len(rv) > 0) else lv
                    else:
                        merged[k] = rv if (cls._is_empty_json_value(lv) and not cls._is_empty_json_value(rv)) else lv
                else:
                    merged[k] = rv
            return merged

        if isinstance(left, list) and isinstance(right, list):
            return right if (len(left) == 0 and len(right) > 0) else left

        return right if (cls._is_empty_json_value(left) and not cls._is_empty_json_value(right)) else left

    @classmethod
    def _normalize_school_record_payload(cls, value: Any) -> Dict[str, Any]:
        school = dict(value or {})
        if not school:
            return {}

        forms_raw = school.get("forms")
        forms = dict(forms_raw) if isinstance(forms_raw, dict) else {}

        # top-level만 채워진 레거시/부분 저장 케이스를 forms로 보강
        for key in (
            "creativeActivity",
            "academicDev",
            "individualDev",
            "behaviorOpinion",
            "volunteerActivity",
            "parsedSchoolRecord",
            "parsedSchoolRecordSummary",
            "rawSchoolRecordText",
            "pdfImportMeta",
        ):
            top_val = school.get(key)
            form_val = forms.get(key)
            if cls._is_empty_json_value(form_val) and not cls._is_empty_json_value(top_val):
                forms[key] = top_val

        if forms:
            school["forms"] = forms

        # forms에만 있는 핵심 데이터는 top-level에도 동기화해서 조회 경로를 단일화
        for key in ("parsedSchoolRecord", "parsedSchoolRecordSummary", "rawSchoolRecordText", "pdfImportMeta"):
            top_val = school.get(key)
            form_val = forms.get(key)
            if cls._is_empty_json_value(top_val) and not cls._is_empty_json_value(form_val):
                school[key] = form_val

        return school

    @classmethod
    async def get_user_profile_school_record(cls, user_id: str) -> Optional[dict]:
        """
        user_profiles.school_record(JSONB) 조회.
        - school_record를 우선 사용하고 metadata.school_record는 누락값 보완 용도로 병합
        """
        if not user_id:
            return None

        client = cls.get_admin_client()
        try:
            r = (
                client.table("user_profiles")
                .select("school_record, metadata")
                .eq("user_id", user_id)
                .execute()
            )

            if r.data and len(r.data) > 0:
                row = r.data[0] or {}
                col_val = row.get("school_record")
                col_school = cls._normalize_school_record_payload(col_val if isinstance(col_val, dict) else {})
                meta = row.get("metadata") or {}
                meta_school_val = meta.get("school_record")
                meta_school = cls._normalize_school_record_payload(
                    meta_school_val if isinstance(meta_school_val, dict) else {}
                )

                merged = cls._normalize_school_record_payload(
                    cls._deep_merge_prefer_left(col_school, meta_school)
                )

                # 조회 시점 동기화(백필): school_record와 metadata.school_record를 같은 값으로 맞춘다.
                needs_sync = (
                    (not meta_school and bool(col_school))
                    or (bool(meta_school) and not bool(col_school))
                    or (bool(merged) and (merged != meta_school or merged != col_school))
                )
                if needs_sync:
                    try:
                        await cls.update_user_profile_school_record(user_id, merged)
                    except Exception as sync_err:
                        print(f"⚠️ school_record 동기화 실패(무시): {sync_err}")

                return merged
            return {}
        except Exception as e:
            print(f"❌ get_user_profile_school_record 오류(컬럼 fallback): {e}")
            meta = await cls.get_user_profile_metadata(user_id)
            if meta is None:
                return None
            return dict(meta.get("school_record") or {})

    @classmethod
    async def update_user_profile_school_record(cls, user_id: str, school_record: Any) -> bool:
        """
        user_profiles.school_record(JSONB) + metadata.school_record 동시 업데이트.
        """
        if not user_id:
            return False

        client = cls.get_admin_client()
        school_payload = cls._normalize_school_record_payload(school_record)

        try:
            existing = (
                client.table("user_profiles")
                .select("user_id, scores, metadata")
                .eq("user_id", user_id)
                .execute()
            )

            if existing.data and len(existing.data) > 0:
                row = existing.data[0] or {}
                meta = dict(row.get("metadata") or {})
                meta["school_record"] = school_payload
                client.table("user_profiles").update(
                    {"school_record": school_payload, "metadata": meta}
                ).eq("user_id", user_id).execute()
            else:
                meta = {"school_record": school_payload}
                client.table("user_profiles").insert(
                    {
                        "user_id": user_id,
                        "scores": {},
                        "metadata": meta,
                        "school_record": school_payload,
                    }
                ).execute()
            return True
        except Exception as e:
            print(f"❌ update_user_profile_school_record 오류: {e}")
            return False

    @staticmethod
    def _normalize_score_name(name: str) -> str:
        raw = (name or "").strip()
        if raw.startswith("@"):
            raw = raw[1:]
        normalized = raw[:10] if raw else "내성적1"
        return normalized

    @classmethod
    async def upsert_user_score_set(
        cls,
        user_id: str,
        name: str,
        scores: Dict[str, Any],
        source_message: Optional[str] = None,
        title_auto_generated: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """성적 세트 upsert (user_id + name unique)."""
        client = cls.get_admin_client()
        try:
            score_name = cls._normalize_score_name(name)
            payload = {
                "user_id": user_id,
                "name": score_name,
                "scores": scores or {},
                "source_message": source_message,
                "title_auto_generated": title_auto_generated,
            }
            response = (
                client.table("user_score_sets")
                .upsert(payload, on_conflict="user_id,name")
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ upsert_user_score_set 오류: {e}")
            return None

    @classmethod
    async def get_user_score_set_by_id(
        cls, score_set_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            query = client.table("user_score_sets").select("*").eq("id", score_set_id)
            if user_id:
                query = query.eq("user_id", user_id)
            response = query.limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ get_user_score_set_by_id 오류: {e}")
            return None

    @classmethod
    async def get_user_score_set_by_name(
        cls, user_id: str, name: str
    ) -> Optional[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            score_name = cls._normalize_score_name(name)
            response = (
                client.table("user_score_sets")
                .select("*")
                .eq("user_id", user_id)
                .eq("name", score_name)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ get_user_score_set_by_name 오류: {e}")
            return None

    @classmethod
    async def list_user_score_sets(
        cls,
        user_id: str,
        keyword: str = "",
        limit: int = 8,
        include_scores: bool = False,
    ) -> List[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            select_cols = "id,name,updated_at"
            if include_scores:
                select_cols = f"{select_cols},scores"
            query = (
                client.table("user_score_sets")
                .select(select_cols)
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .limit(limit)
            )
            if keyword:
                query = query.ilike("name", f"%{keyword.replace('@', '')}%")
            response = query.execute()
            return response.data or []
        except Exception as e:
            print(f"❌ list_user_score_sets 오류: {e}")
            return []

    @classmethod
    async def update_user_score_set_by_id(
        cls,
        user_id: str,
        score_set_id: str,
        name: str,
        scores: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            score_name = cls._normalize_score_name(name)
            response = (
                client.table("user_score_sets")
                .update(
                    {
                        "name": score_name,
                        "scores": scores or {},
                    }
                )
                .eq("id", score_set_id)
                .eq("user_id", user_id)
                .execute()
            )
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ update_user_score_set_by_id 오류: {e}")
            return None

    @classmethod
    async def delete_user_score_set_by_id(cls, user_id: str, score_set_id: str) -> bool:
        client = cls.get_admin_client()
        try:
            client.table("user_score_sets").delete().eq("id", score_set_id).eq(
                "user_id", user_id
            ).execute()
            return True
        except Exception as e:
            print(f"❌ delete_user_score_set_by_id 오류: {e}")
            return False

    @classmethod
    async def create_chat_score_pending(
        cls,
        user_id: Optional[str],
        session_id: str,
        raw_message: str,
        router_output: Dict[str, Any],
        candidate_scores: Dict[str, Any],
        title_auto: str,
    ) -> Optional[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "raw_message": raw_message,
                "router_output": router_output or {},
                "candidate_scores": candidate_scores or {},
                "title_auto": cls._normalize_score_name(title_auto),
                "status": "review_required",
            }
            response = client.table("chat_score_pending").insert(payload).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ create_chat_score_pending 오류: {e}")
            return None

    @classmethod
    async def get_chat_score_pending(
        cls, pending_id: str, session_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        client = cls.get_admin_client()
        try:
            query = client.table("chat_score_pending").select("*").eq("id", pending_id)
            if session_id:
                query = query.eq("session_id", session_id)
            response = query.limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"❌ get_chat_score_pending 오류: {e}")
            return None

    @classmethod
    async def resolve_chat_score_pending(
        cls, pending_id: str, status: str, score_set_id: Optional[str] = None
    ) -> bool:
        client = cls.get_admin_client()
        try:
            payload: Dict[str, Any] = {"status": status}
            if score_set_id:
                payload["score_set_id"] = score_set_id
            client.table("chat_score_pending").update(payload).eq("id", pending_id).execute()
            return True
        except Exception as e:
            print(f"❌ resolve_chat_score_pending 오류: {e}")
            return False

    @classmethod
    async def set_session_skip_score_review(
        cls, session_id: str, user_id: Optional[str], skip: bool
    ) -> bool:
        client = cls.get_admin_client()
        try:
            user_key = user_id or "guest"
            payload = {
                "session_id": session_id,
                "user_id": user_key,
                "skip_score_review": bool(skip),
            }
            client.table("chat_session_flags").upsert(
                payload, on_conflict="session_id,user_id"
            ).execute()
            return True
        except Exception as e:
            print(f"❌ set_session_skip_score_review 오류: {e}")
            return False

    @classmethod
    async def get_session_skip_score_review(
        cls, session_id: str, user_id: Optional[str]
    ) -> bool:
        client = cls.get_admin_client()
        try:
            user_key = user_id or "guest"
            query = client.table("chat_session_flags").select("skip_score_review").eq(
                "session_id", session_id
            ).eq("user_id", user_key)
            response = query.limit(1).execute()
            if response.data:
                return bool(response.data[0].get("skip_score_review"))
            return False
        except Exception as e:
            print(f"❌ get_session_skip_score_review 오류: {e}")
            return False

    @classmethod
    async def insert_chat_score_link(
        cls,
        session_id: str,
        score_set_id: str,
        score_name: str,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
    ) -> bool:
        client = cls.get_admin_client()
        try:
            payload = {
                "session_id": session_id,
                "user_message_id": user_message_id,
                "assistant_message_id": assistant_message_id,
                "score_set_id": score_set_id,
                "score_name": cls._normalize_score_name(score_name),
            }
            client.table("chat_score_links").insert(payload).execute()
            return True
        except Exception as e:
            print(f"❌ insert_chat_score_link 오류: {e}")
            return False


class SupabaseUploader:
    """Supabase에 문서 데이터를 업로드하는 클래스"""

    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL") or settings.SUPABASE_URL
        supabase_key = os.getenv("SUPABASE_KEY") or settings.SUPABASE_KEY

        if not supabase_url or not supabase_key:
            raise ValueError(
                "Supabase 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정하세요."
            )

        self.supabase: Client = create_client(supabase_url, supabase_key)

        embedding_model = embedding_config.DEFAULT_EMBEDDING_MODEL
        embedding_kwargs = {
            "request_timeout": 600,
            "batch_size": 100,
            "max_retries": 10,
            "retry_delay": 15
        }
        if embedding_model:
            embedding_kwargs["model"] = embedding_model

        self.embeddings = GoogleGenerativeAIEmbeddings(**embedding_kwargs)

    def upload_to_supabase(
        self,
        school_name: str,
        file_path: str,
        processed_data: Dict[str, Any],
        original_filename: str = None
    ) -> Optional[int]:
        """전처리된 PDF 데이터를 Supabase에 업로드"""
        try:
            if not processed_data:
                raise ValueError("processed_data가 비어있습니다.")

            toc_sections = processed_data.get("toc_sections", [])
            chunks = processed_data.get("chunks", [])
            summary = processed_data.get("summary", "")

            summary_embedding = None
            if summary:
                summary_embedding = self._generate_summary_embedding(summary)

            if not chunks:
                print("⚠️  업로드할 청크가 없습니다.")
                return None

            filename = original_filename if original_filename else os.path.basename(file_path)

            print(f"\n📤 Supabase 업로드 시작: {school_name} - {filename}")
            print(f"   섹션 수: {len(toc_sections)}개")
            print(f"   청크 수: {len(chunks)}개")
            if summary:
                print(f"   요약: 있음 ({len(summary)}자)")

            file_url = processed_data.get("file_url")
            if file_url:
                print("\n[Step 0] Storage 업로드 건너뜀 (이미 업로드됨)")
                print(f"   📎 파일 URL: {file_url}")
            else:
                print("\n[Step 0] PDF 파일을 Storage에 업로드 중...")
                file_url = self._upload_to_storage(school_name, filename, file_path)
                if file_url:
                    print(f"   📎 파일 URL: {file_url}")

            print("\n[Step 1] documents 테이블에 문서 등록 중...")
            document_id = self._insert_document(
                school_name,
                filename,
                file_path,
                summary,
                summary_embedding,
                file_url,
            )
            if not document_id:
                raise Exception("문서 등록 실패")
            print(f"   ✅ 문서 등록 완료 (ID: {document_id})")

            print("\n[Step 2] document_sections 테이블에 섹션 등록 중...")
            section_map = self._insert_sections(document_id, toc_sections)
            print(f"   ✅ 섹션 등록 완료 ({len(section_map)}개 섹션)")

            print("\n[Step 3] 임베딩 생성 중...")
            embeddings_list = self._generate_embeddings(chunks)
            print(f"   ✅ 임베딩 생성 완료 ({len(embeddings_list)}개)")

            print("\n[Step 4] document_chunks 테이블에 청크 등록 중...")
            chunks_inserted = self._insert_chunks(
                document_id,
                section_map,
                chunks,
                embeddings_list
            )
            print(f"   ✅ 청크 등록 완료 ({chunks_inserted}개)")

            print(f"\n🎉 Supabase 업로드 완료! (문서 ID: {document_id})")
            return document_id

        except Exception as e:
            print(f"\n❌ Supabase 업로드 중 오류 발생: {str(e)}")
            import traceback
            print(f"상세 오류:\n{traceback.format_exc()}")
            return None

    def _upload_to_storage(
        self,
        school_name: str,
        filename: str,
        file_path: str,
        bucket_name: str = "document"
    ) -> Optional[str]:
        """PDF 파일을 Supabase Storage에 업로드하고 public URL 반환"""
        try:
            import uuid
            import hashlib

            school_hash = hashlib.md5(school_name.encode('utf-8')).hexdigest()[:8]
            safe_school = f"school_{school_hash}"

            file_uuid = str(uuid.uuid4())
            safe_filename = f"{file_uuid}.pdf"

            storage_path = f"{safe_school}/{safe_filename}"

            print(f"   📄 원본 파일명: {filename}")
            print(f"   📁 Storage 경로: {storage_path}")
            print(f"   📄 로컬 파일 경로: {file_path}")

            with open(file_path, "rb") as f:
                file_data = f.read()

            print(f"   📦 파일 크기: {len(file_data)} bytes")

            try:
                self.supabase.storage.from_(bucket_name).remove([storage_path])
                print(f"   🗑️ 기존 파일 삭제 완료")
            except Exception as del_e:
                print(f"   ℹ️ 기존 파일 없음 또는 삭제 실패: {del_e}")

            self.supabase.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_data,
                file_options={"content-type": "application/pdf"}
            )

            file_url = self.supabase.storage.from_(bucket_name).get_public_url(storage_path)

            print(f"   ✅ Storage 업로드 완료: {storage_path}")
            print(f"   🔗 File URL: {file_url}")
            return file_url
        except Exception as e:
            import traceback
            print(f"   ⚠️ Storage 업로드 실패 (계속 진행): {str(e)}")
            print(f"   상세 오류:\n{traceback.format_exc()}")
            return None

    def _insert_document(
        self,
        school_name: str,
        filename: str,
        file_path: str,
        summary: str = "",
        summary_embedding: Optional[List[float]] = None,
        file_url: Optional[str] = None,
    ) -> Optional[int]:
        """documents 테이블에 문서 등록"""
        try:
            metadata = {
                "file_path": file_path,
                "uploaded_at": str(os.path.getmtime(file_path)) if os.path.exists(file_path) else None
            }

            insert_data = {
                "school_name": school_name,
                "filename": filename,
                "metadata": metadata
            }

            if summary:
                insert_data["summary"] = summary
            if summary_embedding:
                # pgvector: 문자열 "[x,y,z,...]" 형식으로 전달
                insert_data["embedding_summary"] = "[" + ",".join(map(str, summary_embedding)) + "]"
            if file_url:
                insert_data["file_url"] = file_url

            response = self.supabase.table("documents").insert(insert_data).execute()

            if response.data:
                return response.data[0].get("id")
            return None
        except Exception as e:
            print(f"   ⚠️ documents 테이블 삽입 실패: {str(e)}")
            return None

    def _insert_sections(self, document_id: int, sections: List[dict]) -> Dict[str, int]:
        """document_sections 테이블에 섹션 등록"""
        section_map = {}

        try:
            for section in sections:
                section_name = section.get("title", "알 수 없음")
                page_start = section.get("start_page", 1)
                page_end = section.get("end_page", 1)

                response = self.supabase.table("document_sections").insert(
                    {
                        "document_id": document_id,
                        "section_name": section_name,
                        "page_start": page_start,
                        "page_end": page_end
                    }
                ).execute()

                if response.data:
                    section_id = response.data[0].get("id")
                    section_key = f"{page_start}_{page_end}"
                    section_map[section_key] = section_id
        except Exception as e:
            print(f"   ⚠️ document_sections 삽입 실패: {str(e)}")

        return section_map

    def _generate_summary_embedding(self, summary: str) -> Optional[List[float]]:
        """요약 임베딩 생성"""
        try:
            return self.embeddings.embed_query(summary)
        except Exception as e:
            print(f"   ⚠️ 요약 임베딩 생성 실패: {str(e)}")
            return None

    def _generate_embeddings(self, chunks: List[Document]) -> List[List[float]]:
        """청크 임베딩 생성 (배치)"""
        texts = [doc.page_content for doc in chunks]
        return self.embeddings.embed_documents(texts)

    def _insert_chunks(
        self,
        document_id: int,
        section_map: Dict[str, int],
        chunks: List[Document],
        embeddings_list: List[List[float]],
        batch_size: int = 100
    ) -> int:
        """document_chunks 테이블에 청크 등록 (배치)"""
        inserted = 0
        batch = []

        for idx, (doc, embedding) in enumerate(zip(chunks, embeddings_list), start=1):
            metadata = doc.metadata or {}

            page_number = metadata.get("page_number", 0)
            chunk_type = metadata.get("type", "text")
            raw_data = metadata.get("raw_data")

            section_key = f"{metadata.get('section_start', 0)}_{metadata.get('section_end', 0)}"
            section_id = section_map.get(section_key)

            # pgvector: 문자열 "[x,y,z,...]" 형식으로 전달
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"
            batch.append({
                "document_id": document_id,
                "section_id": section_id,
                "content": doc.page_content,
                "raw_data": raw_data,
                "embedding": embedding_str,
                "page_number": page_number,
                "chunk_type": chunk_type
            })

            if len(batch) >= batch_size or idx == len(chunks):
                try:
                    response = self.supabase.table("document_chunks").insert(batch).execute()
                    if response.data:
                        inserted += len(response.data)
                except Exception as e:
                    print(f"   ⚠️ 청크 배치 삽입 실패: {str(e)}")
                batch = []

        return inserted


# 전역 인스턴스
supabase_service = SupabaseService()

