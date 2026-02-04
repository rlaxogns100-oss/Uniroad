import pandas as pd
import json
import os

excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"
universities_json_path = "suneung-calculator/universities.json"

# 엑셀에서 각 군 데이터 추출
print("=" * 100)
print("엑셀 데이터 추출 시작")
print("=" * 100)

def extract_gun_data(sheet_name):
    """각 군의 데이터를 추출하는 함수"""
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    
    # 헤더 행은 행 6 (0-indexed)
    # 데이터는 행 7부터 시작
    
    data = []
    for idx in range(7, len(df)):
        row = df.iloc[idx]
        
        # 컬럼 구조:
        # 0: ID (가1, 가2 등)
        # 1: sequence
        # 2: college_code
        # 3: college_seq
        # 4: dept_seq
        # 5: gun
        # 6: university
        # 7: department
        # 8: track
        # 9: available
        # 10: english_deduction
        # 11: english_deduction_pct
        # 12: history_lang_deduction
        # 13: probability
        # 14: safe_score
        # 15: appropriate_score (적정)
        # 16: expected_score (예상컷)
        # 17: challenge_score (도전)
        # 18: risky_score (위험 - 3% 이하)
        
        if pd.isna(row.iloc[8]):  # university가 비어있으면 스킵
            continue
        
        # 컬럼 매핑:
        # 2: ID (가1, 가2 등)
        # 4: formulaId
        # 7: gun
        # 8: university
        # 9: department
        # 10: track
        # 12: englishDeduction
        # 14: historyForeignDeduction
        # 16: risky_score (환산점수)
        # 17: safeScore (안정 90%)
        # 18: appropriateScore (적정 70%)
        # 19: expectedScore (예상컷 40%)
        # 20: challengeScore (도전 10%)
        # 21: risky_score_2 (3% 이하)
        # 22: scoreMethod
        # 23: tamguMethod
        # 24: koreanRatio
        # 25: mathRatio
        # 26: tamguRatio
        
        entry = {
            "id": str(row.iloc[2]) if pd.notna(row.iloc[2]) else "",
            "formulaId": int(row.iloc[4]) if pd.notna(row.iloc[4]) else 0,
            "gun": str(row.iloc[7]) if pd.notna(row.iloc[7]) else "",
            "university": str(row.iloc[8]) if pd.notna(row.iloc[8]) else "",
            "department": str(row.iloc[9]) if pd.notna(row.iloc[9]) else "",
            "track": str(row.iloc[10]) if pd.notna(row.iloc[10]) else "",
            "englishDeduction": float(row.iloc[12]) if pd.notna(row.iloc[12]) else 0,
            "historyForeignDeduction": float(row.iloc[14]) if pd.notna(row.iloc[14]) else 0,
            "safeScore": float(row.iloc[17]) if pd.notna(row.iloc[17]) else 0,
            "appropriateScore": float(row.iloc[18]) if pd.notna(row.iloc[18]) else 0,
            "expectedScore": float(row.iloc[19]) if pd.notna(row.iloc[19]) else 0,
            "challengeScore": float(row.iloc[20]) if pd.notna(row.iloc[20]) else 0,
            "scoreMethod": str(row.iloc[22]) if pd.notna(row.iloc[22]) else "표점",
            "tamguMethod": str(row.iloc[23]) if pd.notna(row.iloc[23]) else "변표",
            "koreanRatio": float(row.iloc[24]) if pd.notna(row.iloc[24]) else 0,
            "mathRatio": float(row.iloc[25]) if pd.notna(row.iloc[25]) else 0,
            "tamguRatio": float(row.iloc[26]) if pd.notna(row.iloc[26]) else 0,
        }
        
        data.append(entry)
    
    return data

# 각 군별 데이터 추출
ga_data = extract_gun_data("       가 군       ")
na_data = extract_gun_data("       나 군       ")
da_data = extract_gun_data("       다 군      ")

print(f"\n추출된 데이터:")
print(f"  가군: {len(ga_data)}개")
print(f"  나군: {len(na_data)}개")
print(f"  다군: {len(da_data)}개")
print(f"  전체: {len(ga_data) + len(na_data) + len(da_data)}개")

# 모든 데이터 통합
all_data = ga_data + na_data + da_data

# 샘플 데이터 확인
print("\n\n가군 샘플 데이터 (처음 5개):")
for i, item in enumerate(ga_data[:5]):
    print(f"\n{i+1}. {item['university']} - {item['department']}")
    print(f"   ID: {item['id']}, formulaId: {item['formulaId']}")
    print(f"   안정: {item['safeScore']}, 적정: {item['appropriateScore']}, 예상: {item['expectedScore']}, 도전: {item['challengeScore']}")

# JSON 파일로 저장
output_path = universities_json_path
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f"\n\n✅ {output_path}에 {len(all_data)}개의 대학/학과 데이터 저장 완료!")
