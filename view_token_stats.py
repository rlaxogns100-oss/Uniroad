#!/usr/bin/env python3
"""
토큰 사용량 통계 확인 스크립트
"""
import csv
import os
from collections import defaultdict

TOKEN_LOG_FILE = "token_usage.csv"

def view_stats():
    """토큰 사용량 통계 출력"""
    
    if not os.path.exists(TOKEN_LOG_FILE):
        print("❌ token_usage.csv 파일이 없습니다.")
        print("   파일 업로드나 채팅을 진행하면 자동으로 생성됩니다.")
        return
    
    # 통계 수집
    total_tokens = 0
    total_prompt = 0
    total_output = 0
    by_operation = defaultdict(lambda: {"count": 0, "tokens": 0, "prompt": 0, "output": 0})
    by_model = defaultdict(lambda: {"count": 0, "tokens": 0})
    records = []
    
    with open(TOKEN_LOG_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tokens = int(row['total_tokens'])
            prompt = int(row['prompt_tokens'])
            output = int(row['output_tokens'])
            operation = row['operation']
            model = row['model']
            
            total_tokens += tokens
            total_prompt += prompt
            total_output += output
            
            by_operation[operation]["count"] += 1
            by_operation[operation]["tokens"] += tokens
            by_operation[operation]["prompt"] += prompt
            by_operation[operation]["output"] += output
            
            by_model[model]["count"] += 1
            by_model[model]["tokens"] += tokens
            
            records.append(row)
    
    # 출력
    print("=" * 80)
    print("📊 토큰 사용량 통계")
    print("=" * 80)
    print(f"\n💰 전체 사용량")
    print(f"   총 호출 횟수: {len(records):,}회")
    print(f"   입력 토큰: {total_prompt:,}")
    print(f"   출력 토큰: {total_output:,}")
    print(f"   총 토큰: {total_tokens:,}")
    
    print(f"\n📋 작업별 사용량")
    print("-" * 80)
    for op, stats in sorted(by_operation.items(), key=lambda x: x[1]["tokens"], reverse=True):
        print(f"   {op:20s}: {stats['tokens']:>8,} 토큰 ({stats['count']:>3}회) "
              f"[입력: {stats['prompt']:>6,} / 출력: {stats['output']:>6,}]")
    
    print(f"\n🤖 모델별 사용량")
    print("-" * 80)
    for model, stats in sorted(by_model.items(), key=lambda x: x[1]["tokens"], reverse=True):
        print(f"   {model:25s}: {stats['tokens']:>8,} 토큰 ({stats['count']:>3}회)")
    
    print(f"\n📝 최근 10개 기록")
    print("-" * 80)
    for record in records[-10:]:
        print(f"   [{record['timestamp']}] {record['operation']:15s} - "
              f"{int(record['total_tokens']):>6,} 토큰 ({record['model']})")
        if record['details']:
            print(f"      └ {record['details']}")
    
    print("\n" + "=" * 80)
    print(f"📁 파일 위치: {os.path.abspath(TOKEN_LOG_FILE)}")
    print("=" * 80)

if __name__ == "__main__":
    view_stats()
