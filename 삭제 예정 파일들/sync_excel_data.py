import pandas as pd
import json
from collections import defaultdict

# 엑셀 파일 로드
excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"

# 가군 데이터 추출
print("=" * 100)
print("가군 데이터 추출 및 분석")
print("=" * 100)

df_ga = pd.read_excel(excel_file, sheet_name="       가 군       ")

# 실제 데이터 시작 행 찾기 (헤더 확인)
# 행 8에 연번, 행 9에 실제 데이터가 시작되는 것으로 보임
data_rows = []
for idx in range(8, len(df_ga)):
    row = df_ga.iloc[idx]
    # 연번(첫번째 수치 컬럼)이 있는 경우만 데이터로 인식
    if pd.notna(row.iloc[1]) and isinstance(row.iloc[1], (int, float)):
        try:
            seqnum = int(row.iloc[1]) if not pd.isna(row.iloc[1]) else None
            if seqnum and seqnum < 1000:  # 연번으로 보이는 숫자만
                data_rows.append(idx)
        except:
            pass

print(f"\n데이터 시작 행: {data_rows[0] if data_rows else '찾을 수 없음'}")
print(f"총 데이터 행 수: {len(data_rows)}")

# 각 행의 실제 컬럼 확인
if data_rows:
    sample_row = df_ga.iloc[data_rows[0]]
    print(f"\n첫 번째 데이터 행 (행 {data_rows[0]+1}):")
    for col_idx, val in enumerate(sample_row.head(30)):
        if pd.notna(val):
            print(f"  컬럼 {col_idx}: {val}")

# 헤더 구조 파악
print(f"\n행 8 (헤더 추정):")
for col_idx, val in enumerate(df_ga.iloc[8].head(30)):
    if pd.notna(val):
        print(f"  컬럼 {col_idx}: {val}")

# 가군 데이터 정리
ga_data = []
if data_rows:
    for idx in data_rows[:10]:  # 처음 10개만 테스트
        row = df_ga.iloc[idx]
        try:
            # 각 컬럼의 의미 파악
            entry = {
                'sequence': int(row.iloc[0]) if pd.notna(row.iloc[0]) else None,
                'college_seq': int(row.iloc[1]) if pd.notna(row.iloc[1]) else None,
                'gun': row.iloc[2] if pd.notna(row.iloc[2]) else None,
                'university': row.iloc[3] if pd.notna(row.iloc[3]) else None,
                'department': row.iloc[4] if pd.notna(row.iloc[4]) else None,
                'track': row.iloc[5] if pd.notna(row.iloc[5]) else None,
                'english_deduction': row.iloc[11] if pd.notna(row.iloc[11]) else 0,
                'safe_score': row.iloc[15] if pd.notna(row.iloc[15]) else None,
                'appropriate_score': row.iloc[16] if pd.notna(row.iloc[16]) else None,
                'expected_score': row.iloc[17] if pd.notna(row.iloc[17]) else None,
                'challenge_score': row.iloc[18] if pd.notna(row.iloc[18]) else None,
                'risky_score': row.iloc[19] if pd.notna(row.iloc[19]) else None,
            }
            ga_data.append(entry)
        except Exception as e:
            print(f"오류 (행 {idx+1}): {e}")

print(f"\n\n추출된 가군 데이터 (샘플 10개):")
for i, item in enumerate(ga_data[:10]):
    print(f"\n{i+1}. {item.get('university')} - {item.get('department')}")
    print(f"   계열: {item.get('track')}, 안정: {item.get('safe_score')}, 적정: {item.get('appropriate_score')}")
