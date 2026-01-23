"""
수능 점수 변환 및 추정 방법 문서를 Supabase에 업로드
"""
import sys
import os

# .env 먼저 로드
from dotenv import load_dotenv
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv(env_path)
print(f"✅ .env 파일 로드됨: {env_path}")

# 환경변수 확인
if not os.getenv("SUPABASE_URL"):
    print(f"❌ 환경변수 SUPABASE_URL이 설정되지 않았습니다")
    print(f"   .env 파일 위치: {env_path}")
    sys.exit(1)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.supabase_client import SupabaseService

def upload_conversion_guide():
    """점수 변환 가이드 PDF를 Supabase에 업로드"""
    
    # PDF 파일 경로 (프로젝트 루트)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    pdf_path = os.path.join(project_root, "수능 점수 변환 및 추정 방법 안내.pdf")
    
    # PDF가 없으면 HTML을 찾아서 안내
    if not os.path.exists(pdf_path):
        html_path = os.path.join(project_root, "docs", "수능_점수_변환_및_추정_방법.html")
        print(f"❌ PDF 파일을 찾을 수 없습니다: {pdf_path}")
        print(f"\n💡 HTML을 PDF로 변환하세요:")
        print(f"   1. {html_path} 파일을 브라우저로 열기")
        print(f"   2. Cmd+P (Mac) 또는 Ctrl+P (Windows) 눌러 인쇄")
        print(f"   3. 'PDF로 저장' 선택")
        print(f"   4. 파일명을 '수능_점수_변환_및_추정_방법.pdf'로 저장")
        print(f"   5. docs 폴더에 저장 ({project_root}/docs/)")
        print(f"\n다시 이 스크립트를 실행하세요.")
        return None
    
    # 파일 크기 확인
    file_size = os.path.getsize(pdf_path)
    print(f"\n📄 업로드할 파일:")
    print(f"   경로: {pdf_path}")
    print(f"   크기: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    
    # PDF 읽기
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    # Supabase Storage에 업로드
    print(f"\n⬆️  Supabase Storage에 업로드 중...")
    result = SupabaseService.upload_pdf_to_storage(
        file_bytes=pdf_bytes,
        file_name="수능_점수_변환_및_추정_방법.pdf"
    )
    
    if result:
        storage_file_name, public_url = result
        print(f"\n✅ 업로드 완료!")
        print(f"\n📊 결과:")
        print(f"   Storage 파일명: {storage_file_name}")
        print(f"   Public URL: {public_url}")
        
        # URL을 파일로 저장
        url_file = os.path.join(project_root, "docs", "conversion_guide_url.txt")
        with open(url_file, 'w', encoding='utf-8') as f:
            f.write(public_url)
        print(f"\n✅ URL 저장: {url_file}")
        
        # 환경변수 파일에도 저장하도록 안내
        env_file = os.path.join(project_root, "backend", ".env")
        print(f"\n💡 .env 파일에 다음 내용을 추가하세요:")
        print(f"   SCORE_CONVERSION_GUIDE_URL={public_url}")
        print(f"\n   파일 위치: {env_file}")
        
        return public_url
    else:
        print(f"\n❌ 업로드 실패")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("수능 점수 변환 및 추정 방법 문서 업로드")
    print("=" * 60)
    
    url = upload_conversion_guide()
    
    if url:
        print(f"\n" + "=" * 60)
        print("✅ 업로드 성공!")
        print("=" * 60)
    else:
        print(f"\n" + "=" * 60)
        print("❌ 업로드 실패 또는 PDF 파일 준비 필요")
        print("=" * 60)
