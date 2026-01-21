# 데이터베이스 마이그레이션

Supabase PostgreSQL 데이터베이스 스키마 마이그레이션 파일들입니다.

## 📋 실행 순서

**Supabase Dashboard > SQL Editor**에서 순서대로 실행하세요.

### 1️⃣ 최초 설치 (초기 셋업)

```sql
-- 01_initial_setup.sql
```
- pgvector 확장 활성화
- `policy_documents` 테이블 생성 (벡터 검색용)
- `match_documents()` 함수 생성 (1536차원)
- 벡터 인덱스 생성

### 2️⃣ 문서 메타데이터 테이블 추가

```sql
-- 02_create_metadata_table.sql
```
- `documents_metadata` 테이블 생성
- 파일당 1개 레코드 (제목, 출처, 요약 등)
- 인덱스 생성

### 3️⃣ 해시태그 기능 추가

```sql
-- 03_add_hashtags.sql
```
- `hashtags` 컬럼 추가 (TEXT[] 배열)
- GIN 인덱스 생성 (빠른 검색)
- 예: `['#2028', '#서울대', '#모집요강', '#수시']`

### 4️⃣ Storage 파일명 관리

```sql
-- 04_add_storage_name.sql
```
- `storage_file_name` 컬럼 추가
- Supabase Storage에 저장된 UUID 파일명 관리

### 5️⃣ 파일 다운로드 URL 추가

```sql
-- 05_add_file_url.sql
```
- `file_url` 컬럼 추가
- PDF 다운로드 공개 URL 저장

---

## 🧪 테스트 데이터

```sql
-- sample_data.sql (선택사항)
```
- 개발/테스트용 샘플 데이터
- 실제 운영 환경에서는 사용 안 함

---

## ⚠️ 주의사항

1. **순서대로 실행**: 파일 번호 순서를 지켜야 합니다
2. **한 번만 실행**: 이미 실행한 마이그레이션은 다시 실행하지 마세요
3. **백업 권장**: 중요한 데이터가 있다면 실행 전 백업하세요

---

## 🗄️ 현재 DB 스키마

### `policy_documents` (벡터 검색용)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | Primary Key |
| content | TEXT | 청크 텍스트 |
| embedding | VECTOR(1536) | 임베딩 벡터 (OpenAI) |
| metadata | JSONB | 메타데이터 (fileName, chunkIndex 등) |
| created_at | TIMESTAMP | 생성 시각 |

### `documents_metadata` (문서 정보)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| file_name | TEXT | Primary Key (원본 파일명) |
| storage_file_name | TEXT | Storage UUID 파일명 |
| title | TEXT | 문서 제목 |
| source | TEXT | 출처 (예: "대입정보포털") |
| summary | TEXT | 요약 (목차 형식) |
| hashtags | TEXT[] | 해시태그 배열 |
| file_url | TEXT | 다운로드 URL |
| total_pages | INTEGER | 총 페이지 수 |
| total_chunks | INTEGER | 총 청크 수 |
| created_at | TIMESTAMP | 업로드 시각 |

---

## 🔍 검색 함수

```sql
-- 벡터 유사도 검색
SELECT * FROM match_documents(
  query_embedding := '[0.1, 0.2, ...]'::vector(1536),
  match_threshold := 0.78,
  match_count := 5
);
```
