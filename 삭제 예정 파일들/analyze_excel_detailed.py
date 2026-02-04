import pandas as pd
import numpy as np

# 엑셀 파일 읽기
excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"

print("=" * 100)
print("상세 시트 분석")
print("=" * 100)

# 1. 변환표준점수 시트 분석
print("\n[1] 변환표준점수 시트")
print("-" * 100)
df_conversion = pd.read_excel(excel_file, sheet_name="변환표준점수", header=None)
print(f"행 수: {len(df_conversion)}, 열 수: {len(df_conversion.columns)}")
print("\n상위 20행:")
print(df_conversion.head(20).to_string())

# 2. 환산공식 시트 분석
print("\n\n[2] 환산공식 시트")
print("-" * 100)
df_formula = pd.read_excel(excel_file, sheet_name="환산공식", header=None)
print(f"행 수: {len(df_formula)}, 열 수: {len(df_formula.columns)}")
print("\n상위 30행:")
print(df_formula.head(30).to_string())

# 3. 배치점수 계산기 시트 분석
print("\n\n[3] 배치점수 계산기 시트")
print("-" * 100)
df_calculator = pd.read_excel(excel_file, sheet_name="배치점수 계산기", header=None)
print(f"행 수: {len(df_calculator)}, 열 수: {len(df_calculator.columns)}")
print("\n상위 30행:")
print(df_calculator.head(30).to_string())

# 4. 가 군 시트의 실제 데이터 부분 확인
print("\n\n[4] 가 군 시트 - 실제 데이터 부분")
print("-" * 100)
df_ga = pd.read_excel(excel_file, sheet_name="       가 군       ", header=None)
# 헤더를 찾기 위해 '대학명' 또는 유사한 문자열이 있는 행을 찾음
for i in range(min(20, len(df_ga))):
    row_str = ' '.join([str(x) for x in df_ga.iloc[i].values if pd.notna(x)])
    if '대학' in row_str or '학과' in row_str:
        print(f"\n헤더 가능 행 (행 {i}):")
        print(df_ga.iloc[i].to_string())
        
        if i < len(df_ga) - 1:
            print(f"\n데이터 시작 (행 {i+1}부터 10행):")
            print(df_ga.iloc[i+1:i+11].to_string())
        break
