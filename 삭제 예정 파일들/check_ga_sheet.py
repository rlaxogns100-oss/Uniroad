import pandas as pd
import json

excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"

# 가군 시트 직접 확인
df_ga = pd.read_excel(excel_file, sheet_name="       가 군       ", header=None)

print("=" * 100)
print("가군 시트 구조 상세 분석")
print("=" * 100)
print(f"\n시트 크기: {df_ga.shape}")
print(f"\n첫 20행 확인:")
print(df_ga.iloc[:20, :15])

# NaN이 아닌 데이터가 있는 첫 행 찾기
for i in range(len(df_ga)):
    row_data = df_ga.iloc[i]
    non_null = row_data.dropna()
    if len(non_null) > 5:
        print(f"\n행 {i}: {non_null.head(15).to_list()}")
        if i > 30:
            break
