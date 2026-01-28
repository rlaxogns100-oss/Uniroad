"""
토큰 사용량 로깅 유틸리티
backend/logs/token_usage.csv에 모든 토큰 사용량 기록
"""
import csv
import os
from datetime import datetime
from typing import Optional
import threading

# backend/logs 디렉토리 경로
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BACKEND_DIR, "logs")
TOKEN_LOG_FILE = os.path.join(LOGS_DIR, "token_usage.csv")

# logs 디렉토리가 없으면 생성
os.makedirs(LOGS_DIR, exist_ok=True)

# 스레드 안전을 위한 락
_lock = threading.Lock()

def init_token_log():
    """토큰 로그 파일 초기화 (헤더 생성)"""
    if not os.path.exists(TOKEN_LOG_FILE):
        with open(TOKEN_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'operation',
                'model',
                'prompt_tokens',
                'output_tokens',
                'total_tokens',
                'details'
            ])

def log_token_usage(
    operation: str,
    prompt_tokens: int,
    output_tokens: int,
    total_tokens: int,
    model: str = "gemini",
    details: str = ""
):
    """
    토큰 사용량 기록
    
    Args:
        operation: 작업 유형 (예: "PDF파싱", "대화생성", "오케스트레이션" 등)
        prompt_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
        total_tokens: 총 토큰 수
        model: 모델 이름
        details: 추가 상세 정보 (선택)
    """
    with _lock:
        # 파일이 없으면 초기화
        if not os.path.exists(TOKEN_LOG_FILE):
            init_token_log()
        
        # 현재 시간
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # CSV에 추가
        with open(TOKEN_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                operation,
                model,
                prompt_tokens,
                output_tokens,
                total_tokens,
                details
            ])

def get_token_summary():
    """
    토큰 사용량 요약 통계 반환
    
    Returns:
        dict: 총 토큰, 작업별 토큰 등
    """
    if not os.path.exists(TOKEN_LOG_FILE):
        return {"total_tokens": 0, "by_operation": {}}
    
    total = 0
    by_operation = {}
    
    with open(TOKEN_LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tokens = int(row['total_tokens'])
            total += tokens
            
            op = row['operation']
            if op not in by_operation:
                by_operation[op] = 0
            by_operation[op] += tokens
    
    return {
        "total_tokens": total,
        "by_operation": by_operation
    }

# 초기화
init_token_log()
