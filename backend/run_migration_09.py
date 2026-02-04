#!/usr/bin/env python3
"""
09_create_documents_tables.sql 마이그레이션 실행
환경 변수 DATABASE_URL (Supabase Connection string) 필요.
Supabase 대시보드 → Settings → Database → Connection string (URI) 에서 확인.
"""
import os
import sys
from pathlib import Path

# backend 기준 경로
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATHS = [BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"]
for p in ENV_PATHS:
    if p.exists():
        from dotenv import load_dotenv
        load_dotenv(p, override=True)
        break

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL이 설정되지 않았습니다.")
    print("   Supabase 대시보드 → Project Settings → Database → Connection string (URI)")
    print("   에서 연결 문자열을 복사한 뒤, .env에 다음처럼 추가하세요:")
    print("   DATABASE_URL=postgresql://postgres.[ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres")
    sys.exit(1)

SQL_FILE = BACKEND_DIR / "migrations" / "09_create_documents_tables.sql"
if not SQL_FILE.exists():
    print(f"❌ SQL 파일 없음: {SQL_FILE}")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 필요: pip install psycopg2-binary")
    sys.exit(1)

def main():
    sql = SQL_FILE.read_text(encoding="utf-8")
    # pgvector 확장 등은 슈퍼유저 권한이 필요할 수 있음. Connection string은 보통 postgres 역할
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute(sql)
        print("✅ 마이그레이션 09_create_documents_tables.sql 실행 완료")
    except Exception as e:
        print(f"❌ 마이그레이션 실행 오류: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
