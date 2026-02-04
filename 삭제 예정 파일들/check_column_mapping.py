import pandas as pd

excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"
df = pd.read_excel(excel_file, sheet_name="       가 군       ", header=None)

# 행 6 (0-indexed)가 헤더, 행 7부터 데이터
header_row = df.iloc[6]
print("헤더 정보 (컬럼별):")
for i in range(len(header_row)):
    if pd.notna(header_row.iloc[i]):
        print(f"컬럼 {i}: {header_row.iloc[i]}")

print("\n\n샘플 데이터 행 (행 7):")
sample_row = df.iloc[7]
for i in range(len(sample_row)):
    if pd.notna(sample_row.iloc[i]):
        print(f"컬럼 {i}: {sample_row.iloc[i]}")
