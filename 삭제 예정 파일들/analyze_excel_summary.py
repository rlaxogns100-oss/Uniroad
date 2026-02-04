import pandas as pd

excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"

print("=" * 100)
print("환산점수 엑셀배치표 (2026 수능실채점) 분석 요약")
print("=" * 100)

xl_file = pd.ExcelFile(excel_file)

print(f"\n시트 목록 ({len(xl_file.sheet_names)}개):")
for i, sheet_name in enumerate(xl_file.sheet_names, 1):
    print(f"  {i}. {sheet_name}")

# 주요 시트별 요약
print("\n" + "=" * 100)
print("주요 시트 분석 요약")
print("=" * 100)

# 1. 본인점수 입력 시트 - 사용자가 점수를 입력하는 시트
print("\n[1] 본인점수 입력 시트")
print("-" * 100)
df_input = pd.read_excel(excel_file, sheet_name=" 본인점수 입력 ")
print(f"- 목적: 사용자가 수능 점수를 입력하여 배치 결과를 확인하는 시트")
print(f"- 행 수: {len(df_input)}, 열 수: {len(df_input.columns)}")

# 2. 가군/나군/다군 시트 - 각 군별 배치표
for gun_name, sheet_name in [("가", "       가 군       "), ("나", "       나 군       "), ("다", "       다 군      ")]:
    df_gun = pd.read_excel(excel_file, sheet_name=sheet_name)
    print(f"\n[2-{gun_name}] {gun_name}군 배치표")
    print(f"- 목적: {gun_name}군 모집 대학/학과별 입결 및 배치 정보")
    print(f"- 행 수: {len(df_gun)}, 열 수: {len(df_gun.columns)}")
    print(f"- 데이터 항목 수 (추정): {len(df_gun) - 10}개 정도") # 헤더 제외

# 3. 변환표준점수 시트
print(f"\n[3] 변환표준점수 시트")
df_conversion = pd.read_excel(excel_file, sheet_name="변환표준점수")
print(f"- 목적: 대학별 탐구 과목 변환 표준점수 조회 테이블")
print(f"- 행 수: {len(df_conversion)}, 열 수: {len(df_conversion.columns)}")
print(f"- 백분위별 대학별 변환 점수 제공")

# 4. 환산공식 시트
print(f"\n[4] 환산공식 시트")
df_formula = pd.read_excel(excel_file, sheet_name="환산공식")
print(f"- 목적: 대학별 환산 공식 및 계산 방법 정의")
print(f"- 행 수: {len(df_formula)}, 열 수: {len(df_formula.columns)}")

# 5. 배치점수 계산기 시트
print(f"\n[5] 배치점수 계산기 시트")
df_calculator = pd.read_excel(excel_file, sheet_name="배치점수 계산기")
print(f"- 목적: 점수 계산 및 배치 분석 로직")
print(f"- 행 수: {len(df_calculator)}, 열 수: {len(df_calculator.columns)}")

# 6. 2025학년도 입결 분석 시트
print(f"\n[6] 2025학년도 입결 분석 시트")
df_2025 = pd.read_excel(excel_file, sheet_name="    2025학년도 입결 분석    ")
print(f"- 목적: 2025학년도 정시 입결 (70% 컷) 분석 데이터")
print(f"- 행 수: {len(df_2025)}, 열 수: {len(df_2025.columns)}")

print("\n" + "=" * 100)
print("파일 구조 요약")
print("=" * 100)
print("""
이 엑셀 파일은 2026학년도 수능 수험생들이 자신의 점수를 입력하여
대학별 합격 가능성을 확인할 수 있는 배치표입니다.

주요 기능:
1. 사용자 점수 입력 (본인점수 입력 시트)
2. 군별 배치표 조회 (가/나/다군 시트)
3. 대학별 변환 표준점수 조회 (변환표준점수 시트)
4. 환산 공식 및 계산 로직 (환산공식, 배치점수 계산기 시트)
5. 전년도 입결 참고 자료 (2025학년도 입결 분석 시트)

제작자: 베텔기우스 (Betelgeuse058.tistory.com)
""")

print("\n가 군 시트 상세 구조 분석")
print("=" * 100)
df_ga = pd.read_excel(excel_file, sheet_name="       가 군       ")
# 실제 데이터 헤더 찾기 (9행 근처)
print(f"\n행 9 (헤더 추정):")
print(df_ga.iloc[8].to_dict())
print(f"\n행 10-15 (실제 데이터 샘플):")
for i in range(9, min(15, len(df_ga))):
    row_data = df_ga.iloc[i]
    if pd.notna(row_data.iloc[3]) and pd.notna(row_data.iloc[4]):  # 대학명과 학과명이 있는 경우
        print(f"  행{i+1}: 대학={row_data.iloc[3]}, 학과={row_data.iloc[4]}, "
              f"계열={row_data.iloc[5]}, 안정={row_data.iloc[7] if len(row_data) > 7 else 'N/A'}")
