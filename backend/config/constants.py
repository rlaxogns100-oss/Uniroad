"""
상수 정의
"""

# 파일 업로드 설정
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# 텍스트 청킹 설정
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# 임베딩 설정
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSION = 768  # Gemini 임베딩 차원
BATCH_SIZE = 5  # Gemini 병렬 처리 개수

# 요약 설정
SUMMARY_MAX_LENGTH = 500
CLASSIFICATION_SAMPLE_LENGTH = 2000

# Gemini 모델
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"  # 대화/판단용 (고품질)
GEMINI_LITE_MODEL = "gemini-2.5-flash-lite"    # 문서 처리용 (고속)
