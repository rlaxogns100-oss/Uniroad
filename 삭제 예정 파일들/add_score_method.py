import pandas as pd
import json

excel_file = "환산점수 엑셀배치표 (2026 수능실채점)(20251212).xlsx"
universities_json_path = "suneung-calculator/universities.json"

def extract_gun_data(sheet_name):
    """각 군의 데이터를 추출하는 함수"""
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    
    data = []
    for idx in range(7, len(df)):
        row = df.iloc[idx]
        
        if pd.isna(row.iloc[8]):  # university가 비어있으면 스킵
            continue
        
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
            "scoreMethod": str(row.iloc[22]) if pd.notna(row.iloc[22]) else "표점",  # ✅ 추가됨
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

# 모든 데이터 통합
all_data = ga_data + na_data + da_data

# JSON 파일로 저장
with open(universities_json_path, 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

print(f"✅ scoreMethod 필드 추가 완료!")
print(f"\n데이터 현황:")
print(f"  가군: {len(ga_data)}개")
print(f"  나군: {len(na_data)}개")
print(f"  다군: {len(da_data)}개")
print(f"  합계: {len(all_data)}개")

# scoreMethod 분포 확인
print(f"\n전체 scoreMethod 분포:")
score_methods = {}
for item in all_data:
    method = item.get('scoreMethod', '표점')
    score_methods[method] = score_methods.get(method, 0) + 1

for method, count in sorted(score_methods.items(), key=lambda x: x[1], reverse=True):
    print(f"  {method}: {count}개")

print(f"\n✅ {universities_json_path}에 저장 완료!")
