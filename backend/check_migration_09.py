#!/usr/bin/env python3
"""
09_create_documents_tables.sql 적용 여부 확인
backend/.env의 SUPABASE_URL, SUPABASE_KEY로 접속해 documents 등 테이블 존재 여부만 확인.
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
for p in [BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"]:
    if p.exists():
        from dotenv import load_dotenv
        load_dotenv(p, override=True)
        break

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
if not url or not key:
    print("❌ SUPABASE_URL 또는 SUPABASE_KEY가 없습니다. backend/.env를 확인하세요.")
    sys.exit(1)

def main():
    from supabase import create_client
    client = create_client(url, key)

    checks = [
        ("documents", "id"),
        ("document_sections", "id"),
        ("document_chunks", "id"),
    ]
    ok = 0
    for table, col in checks:
        try:
            r = client.table(table).select(col).limit(1).execute()
            print(f"   ✅ {table}: 존재함")
            ok += 1
        except Exception as e:
            print(f"   ❌ {table}: 확인 실패 - {e}")
    if ok == len(checks):
        print("\n✅ 09 마이그레이션 적용된 것으로 보입니다. (documents, document_sections, document_chunks 존재)")
        return 0
    print("\n⚠️  일부 테이블이 없습니다. Supabase 대시보드에서 09_create_documents_tables.sql 을 실행하거나,")
    print("   run_migration_09.py 를 DATABASE_URL 설정 후 실행하세요.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
