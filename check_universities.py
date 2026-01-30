"""
데이터베이스에 저장된 대학별 요강 목록 조회
"""
import sys
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.supabase_client import SupabaseService
import asyncio


async def check_universities():
    """데이터베이스에 저장된 대학 목록 확인"""
    print("\n" + "="*80)
    print("📚 데이터베이스에 저장된 대학별 요강 목록")
    print("="*80 + "\n")
    
    # 문서 목록 가져오기
    documents = await SupabaseService.get_documents()
    
    if not documents:
        print("❌ 저장된 문서가 없습니다.")
        return
    
    print(f"✅ 총 {len(documents)}개의 문서가 저장되어 있습니다.\n")
    
    # 대학별로 그룹화
    university_docs = {}
    
    for doc in documents:
        title = doc.get('title', '')
        file_name = doc.get('fileName', '')
        source = doc.get('source', '')
        hashtags = doc.get('hashtags', [])
        uploaded_at = doc.get('uploadedAt', '')
        
        # 대학명 추출 (제목이나 source에서)
        university = None
        
        # 주요 대학 키워드
        universities = ['서울대', '연세대', '고려대', '서강대', '경희대', '성균관대', '한양대', '중앙대', '이화여대', '한국외대']
        
        for univ in universities:
            if univ in title or univ in source or univ in file_name:
                university = univ
                break
        
        if not university:
            university = "기타"
        
        if university not in university_docs:
            university_docs[university] = []
        
        university_docs[university].append({
            'title': title,
            'file_name': file_name,
            'source': source,
            'hashtags': hashtags,
            'uploaded_at': uploaded_at
        })
    
    # 대학별로 출력
    for university, docs in sorted(university_docs.items()):
        print(f"\n{'─'*80}")
        print(f"🏫 {university} ({len(docs)}개)")
        print(f"{'─'*80}")
        
        for i, doc in enumerate(docs, 1):
            print(f"\n  {i}. 📄 {doc['title']}")
            print(f"     파일명: {doc['file_name']}")
            print(f"     출처: {doc['source']}")
            if doc['hashtags']:
                print(f"     해시태그: {', '.join(doc['hashtags'])}")
            print(f"     업로드: {doc['uploaded_at'][:10] if doc['uploaded_at'] else 'N/A'}")
    
    print("\n" + "="*80)
    print(f"📊 요약: {len(university_docs)}개 대학의 요강이 저장되어 있습니다.")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(check_universities())
