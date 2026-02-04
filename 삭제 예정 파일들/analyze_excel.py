import pandas as pd
import sys

# 엑셀 파일 읽기
excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"

try:
    # 엑셀 파일 로드
    xl_file = pd.ExcelFile(excel_file)
    
    print("=" * 80)
    print(f"엑셀 파일 분석: {excel_file}")
    print("=" * 80)
    
    # 시트 목록 출력
    print(f"\n시트 목록 ({len(xl_file.sheet_names)}개):")
    for i, sheet_name in enumerate(xl_file.sheet_names, 1):
        print(f"  {i}. {sheet_name}")
    
    # 각 시트의 기본 정보 출력
    print("\n" + "=" * 80)
    print("각 시트 상세 정보:")
    print("=" * 80)
    
    for sheet_name in xl_file.sheet_names[:5]:  # 처음 5개 시트만 상세 분석
        print(f"\n시트명: {sheet_name}")
        print("-" * 80)
        
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        print(f"  - 행 수: {len(df)}")
        print(f"  - 열 수: {len(df.columns)}")
        print(f"  - 컬럼: {list(df.columns)[:10]}")  # 처음 10개 컬럼
        
        if len(df.columns) > 10:
            print(f"    ... 외 {len(df.columns) - 10}개 컬럼")
        
        print("\n  - 상위 5행 데이터:")
        print(df.head(5).to_string())
        print()
    
    if len(xl_file.sheet_names) > 5:
        print(f"\n... 외 {len(xl_file.sheet_names) - 5}개 시트")
    
except Exception as e:
    print(f"오류 발생: {e}")
    import traceback
    traceback.print_exc()
