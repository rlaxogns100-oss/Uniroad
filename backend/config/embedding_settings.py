"""
임베딩 기반 PDF 처리 설정
환경 변수 및 기본 설정값 관리
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드 (backend/.env 또는 프로젝트 루트 .env)
_backend_dir = Path(__file__).resolve().parent.parent
_load_paths = [_backend_dir / ".env", _backend_dir.parent / ".env"]
for _p in _load_paths:
    if _p.exists():
        load_dotenv(dotenv_path=_p, override=True)
        break
else:
    load_dotenv(override=True)

# API Key 설정
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    os.environ["GOOGLE_API_KEY"] = gemini_key

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
if UPSTAGE_API_KEY:
    os.environ["UPSTAGE_API_KEY"] = UPSTAGE_API_KEY

# 기본 모델 설정 (임베딩_기반과 동일)
DEFAULT_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-3-flash-preview")
DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"  # 3072차원

# 청킹 설정
CHUNK_SIZE_TOKENS = 800
CHUNK_OVERLAP_TOKENS = 150
CHUNK_BY_PAGE = True

# 검색 설정
TOP_K_PER_SECTION = 30
TOP_K_FINAL = 10

# 재시도 설정
DEFAULT_MAX_RETRIES = 3

# 병렬 처리 설정
MAX_WORKERS = 4

# 캐시 디렉토리 (backend/.cache)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(BASE_DIR, ".cache")
FILES_DIR = os.path.join(CACHE_DIR, "files")
EMBEDDINGS_DIR = os.path.join(CACHE_DIR, "embeddings")
TOC_SECTIONS_DIR = os.path.join(CACHE_DIR, "toc_sections")

# 캐시 디렉토리 생성
for dir_path in [CACHE_DIR, FILES_DIR, EMBEDDINGS_DIR, TOC_SECTIONS_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
