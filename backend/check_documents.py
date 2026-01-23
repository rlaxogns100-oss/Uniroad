"""
Supabase에서 문서 목록 및 학교 정보 조회 스크립트
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# .env 파일 로드
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")
    sys.exit(1)

# Supabase 클라이언트 생성
client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("\n" + "="*80)
print("📚 데이터베이스에 저장된 문서 목록")
print("="*80)

try:
    # documents_metadata 테이블에서 문서 목록 조회
    response = client.table('documents_metadata')\
        .select('*')\
        .order('created_at', desc=True)\
        .execute()
    
    if not response.data or len(response.data) == 0:
        print("\n❌ 저장된 문서가 없습니다.")
    else:
        print(f"\n총 {len(response.data)}개의 문서가 저장되어 있습니다.\n")
        
        # 학교별로 그룹화
        schools = {}
        
        for idx, doc in enumerate(response.data, 1):
            print(f"\n{'─'*80}")
            print(f"📄 문서 {idx}")
            print(f"{'─'*80}")
            print(f"파일명: {doc.get('file_name', 'N/A')}")
            print(f"제목: {doc.get('title', 'N/A')}")
            print(f"출처: {doc.get('source', 'N/A')}")
            print(f"요약: {doc.get('summary', 'N/A')[:100]}..." if doc.get('summary') and len(doc.get('summary', '')) > 100 else f"요약: {doc.get('summary', 'N/A')}")
            print(f"총 페이지: {doc.get('total_pages', 'N/A')}")
            print(f"총 청크: {doc.get('total_chunks', 'N/A')}")
            print(f"해시태그: {doc.get('hashtags', [])}")
            print(f"업로드 시간: {doc.get('created_at', 'N/A')}")
            if doc.get('file_url'):
                print(f"파일 URL: {doc.get('file_url')}")
            
            # 학교 정보 추출 (해시태그 또는 제목/출처에서)
            hashtags = doc.get('hashtags', [])
            title = doc.get('title', '')
            source = doc.get('source', '')
            
            # 학교 이름 추출
            school_keywords = ['서울대', '연세대', '고려대', '경희대', '성균관대', '한양대', 
                             '중앙대', '이화여대', '서강대', '건국대', '동국대', 
                             '홍익대', '숙명여대', '국민대', '세종대', '단국대',
                             '아주대', '인하대', '광운대', '서울시립대', '카이스트', 'KAIST',
                             '포스텍', 'POSTECH', '유니스트', 'UNIST', '지스트', 'GIST']
            
            found_schools = set()
            
            # 해시태그에서 학교 찾기
            for tag in hashtags:
                for keyword in school_keywords:
                    if keyword in tag or keyword.lower() in tag.lower():
                        found_schools.add(keyword)
            
            # 제목과 출처에서 학교 찾기
            for keyword in school_keywords:
                if keyword in title or keyword in source:
                    found_schools.add(keyword)
            
            # 학교별로 그룹화
            if found_schools:
                for school in found_schools:
                    if school not in schools:
                        schools[school] = []
                    schools[school].append(doc.get('file_name', 'N/A'))
        
        # 학교별 요약
        if schools:
            print("\n\n" + "="*80)
            print("🏫 학교별 문서 요약")
            print("="*80 + "\n")
            
            for school, files in sorted(schools.items()):
                print(f"📌 {school}: {len(files)}개 문서")
                for file in files:
                    print(f"   - {file}")
                print()
        else:
            print("\n\n⚠️ 학교 정보를 찾을 수 없습니다.")
            print("   (해시태그나 제목/출처에 학교명이 포함되어 있지 않습니다)")
    
    # policy_documents 테이블의 청크 수 확인
    print("\n" + "="*80)
    print("📊 청크 통계")
    print("="*80)
    
    chunk_response = client.table('policy_documents').select('id', count='exact').execute()
    total_chunks = chunk_response.count if hasattr(chunk_response, 'count') else len(chunk_response.data)
    print(f"\n총 저장된 청크 수: {total_chunks}개\n")
    
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

print("="*80 + "\n")
