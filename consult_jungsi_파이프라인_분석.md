# consult_jungsi 점수 환산 및 평가 파이프라인 분석

## 1. 개요

`consult_jungsi`는 정시 입시 상담을 위한 핵심 함수로, 학생의 수능 성적을 입력받아 **86개 대학, 2158개 학과**에 대한 환산점수를 계산하고 합격 가능성을 평가합니다.

---

## 2. 전체 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        consult_jungsi 파이프라인                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [1단계] 입력 성적 변환                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  j_scores (간단 형식)  →  표준 형식으로 변환                            │   │
│  │  {"국어": 1}  →  {"국어": {"type": "등급", "value": 1}}               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↓                                              │
│  [2단계] 성적 정규화 (normalize_scores_from_extracted)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ScoreConverter를 통해 등급/표준점수/백분위 상호 변환                    │   │
│  │  - 등급만 입력 → 표준점수/백분위 추정                                   │   │
│  │  - 표준점수 입력 → 등급/백분위 조회                                     │   │
│  │  - 백분위 입력 → 표준점수/등급 역추적                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↓                                              │
│  [3단계] 리버스 서치 (run_reverse_search)                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  86개 대학 × 2158개 학과에 대해:                                       │   │
│  │  1. 대학별 환산점수 계산 (calculate_score)                             │   │
│  │  2. 컷 점수 기준 판정 (classify_by_cutoff)                             │   │
│  │  3. 필터링 및 정렬                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              ↓                                              │
│  [4단계] 결과 포맷팅                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  판정별 그룹핑 (안정/적정/소신/도전/어려움/하향)                          │   │
│  │  마크다운 테이블 형식으로 출력                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 상세 단계별 분석

### 3.1 [1단계] 입력 성적 변환

**위치**: `functions.py` 382-396줄

```python
# 간단 형식: {"국어": 1, "수학": 2} 
# → 표준 형식: {"국어": {"type": "등급", "value": 1}}

raw_scores = params.get("j_scores", {})
converted_scores = {}

for key, val in raw_scores.items():
    if isinstance(val, dict):
        # 이미 표준 형식인 경우
        converted_scores[key] = val
    elif isinstance(val, (int, float)):
        # 숫자만 있는 경우 → 등급으로 간주
        converted_scores[key] = {"type": "등급", "value": int(val)}
```

**지원하는 입력 형식**:
| 입력 타입 | 예시 | 변환 결과 |
|----------|------|----------|
| 등급 (숫자) | `{"국어": 1}` | `{"type": "등급", "value": 1}` |
| 표준점수 | `{"국어": {"type": "표준점수", "value": 131}}` | 그대로 유지 |
| 백분위 | `{"국어": {"type": "백분위", "value": 98}}` | 그대로 유지 |
| 원점수 | `{"국어": {"type": "원점수", "value": 95}}` | 그대로 유지 |

---

### 3.2 [2단계] 성적 정규화 (normalize_scores_from_extracted)

**위치**: `processor.py` 32-132줄

이 단계에서는 `ScoreConverter` 클래스를 사용하여 입력된 성적을 완전한 데이터로 변환합니다.

#### 3.2.1 변환 로직

```python
def normalize_scores_from_extracted(extracted_scores: Dict[str, Any]) -> Dict[str, Any]:
    converter = ScoreConverter()
    normalized = {"과목별_성적": {}, "선택과목": {}}
    
    # 기본 선택과목 (미입력 시)
    defaults = {
        "국어": "화법과작문",
        "수학": "확률과통계",
        "탐구1": "생활과윤리",
        "탐구2": "사회문화",
    }
```

#### 3.2.2 입력 타입별 처리

| 입력 타입 | 처리 함수 | 설명 |
|----------|----------|------|
| 등급 | `estimate_score_by_grade()` | 등급 중간 백분위로 표준점수 추정 |
| 표준점수 | `get_score_by_standard()` | 표준점수로 등급/백분위 조회 |
| 원점수 | `get_score_by_raw()` | 원점수로 표준점수/등급/백분위 조회 |
| 백분위 | `find_closest_by_percentile()` | 백분위로 표준점수/등급 역추적 |

#### 3.2.3 등급별 대표 백분위 (추정용)

**위치**: `converter.py` 27-29줄

```python
self.grade_median_percentile = {
    1: 98, 2: 92, 3: 83, 4: 68, 5: 50, 6: 31, 7: 17, 8: 7, 9: 2
}
```

| 등급 | 대표 백분위 | 설명 |
|-----|-----------|------|
| 1등급 | 98 | 상위 4% 중간값 |
| 2등급 | 92 | 4~11% 중간값 |
| 3등급 | 83 | 11~23% 중간값 |
| 4등급 | 68 | 23~40% 중간값 |
| 5등급 | 50 | 40~60% 중간값 |
| 6등급 | 31 | 60~77% 중간값 |
| 7등급 | 17 | 77~89% 중간값 |
| 8등급 | 7 | 89~96% 중간값 |
| 9등급 | 2 | 96~100% 중간값 |

#### 3.2.4 출력 형식

```python
{
    "과목별_성적": {
        "국어": {
            "과목명": "국어",
            "선택과목": "화법과작문",
            "등급": 2,
            "표준점수": 131,
            "백분위": 92,
            "원점수": None,
            "비고": ""
        },
        "수학": {...},
        "영어": {"등급": 1, "표준점수": None, "백분위": None},  # 절대평가
        "한국사": {"등급": 1, "표준점수": None, "백분위": None},  # 절대평가
        "탐구1": {...},
        "탐구2": {...}
    },
    "선택과목": {
        "국어": "화법과작문",
        "수학": "확률과통계"
    }
}
```

---

### 3.3 [3단계] 리버스 서치 (run_reverse_search)

**위치**: `search_engine.py` 48-114줄, `suneung_calculator.py` 156-269줄

#### 3.3.1 대학별 환산점수 계산 (calculate_score)

**위치**: `suneung_calculator.py` 50-121줄

```python
def calculate_score(
    univ: Dict,           # 대학/학과 정보
    korean: float,        # 국어 표준점수
    math: float,          # 수학 표준점수
    tamgu1: float,        # 탐구1 표준점수
    tamgu2: float,        # 탐구2 표준점수
    english: int,         # 영어 등급 (1-9)
    history: int,         # 한국사 등급 (1-9)
) -> Optional[float]:
```

**환산 공식 구조** (`formulas_extracted.json`):

```json
{
  "5": {
    "id": 5,
    "name": "연세대 자연",
    "maxScore": 950,
    "koreanCoef": 1.0555555555555554,    // 국어 계수
    "mathCoef": 1.583333333333333,        // 수학 계수
    "tamguCoef": 1.583333333333333,       // 탐구 계수
    "tamguBonus": 3.038574999999999,      // 탐구 보너스
    "koreanRatio": 0.2222222222222222,    // 국어 반영비율
    "mathRatio": 0.3333333333333333,      // 수학 반영비율
    "tamguRatio": 0.3333333333333333      // 탐구 반영비율
  }
}
```

**환산점수 계산 공식**:

```python
# 기본 점수 계산
korean_score = korean * korean_coef
math_score = math * math_coef
tamgu1_score = tamgu1 * tamgu_coef + tamgu_bonus
tamgu2_score = tamgu2 * tamgu_coef + tamgu_bonus

# 영어/한국사 점수 (감점 또는 가산)
english_score = deduction["englishDeduction"]
history_score = deduction["historyDeductions"][history - 1]

# 고정 보너스
fixed_bonus = deduction.get("fixedBonus", 0)

# 최종 환산점수
total = korean_score + math_score + tamgu1_score + tamgu2_score 
        + english_score + history_score + fixed_bonus
```

**영어/한국사 감점표 예시** (`deduction_tables.json`):

```json
{
  "5": {
    "name": "연세대 자연",
    "englishDeduction": 0,
    "historyDeductions": [
      105.56,  // 1등급
      100.28,  // 2등급
      92.36,   // 3등급
      79.17,   // 4등급
      63.33,   // 5등급
      42.22,   // 6등급
      26.39,   // 7등급
      13.19,   // 8등급
      5.28     // 9등급
    ]
  }
}
```

#### 3.3.2 컷 점수 기준 판정 (classify_by_cutoff)

**위치**: `suneung_calculator.py` 124-153줄

```python
def classify_by_cutoff(my_score: float, univ: Dict) -> str:
    safe = univ.get("safeScore")           # 안정컷
    appropriate = univ.get("appropriateScore")  # 적정컷
    expected = univ.get("expectedScore")   # 소신컷 (예상컷)
    challenge = univ.get("challengeScore") # 도전컷
```

**판정 기준표**:

| 판정 | 조건 | 이모지 | 설명 |
|-----|------|-------|------|
| **하향** | `my_score >= safeScore * 1.01` | ⬇️ | 안정컷 대비 1% 이상 초과 (과도한 하향 지원) |
| **안정** | `my_score >= safeScore` | 🟢 | 안정컷 이상 (1% 미만 초과) |
| **적정** | `my_score >= appropriateScore` | 🟡 | 적정컷 이상 |
| **소신** | `my_score >= expectedScore` | 🟠 | 소신컷(예상컷) 이상 |
| **도전** | `my_score >= challengeScore` | 🔴 | 도전컷 이상 |
| **어려움** | `my_score < challengeScore` | ⚫ | 도전컷 미만 |

**판정 로직 상세**:

```python
if safe and my_score >= safe:
    # 하향 판정: safeScore 대비 1% 이상 초과하면 하향
    excess_ratio = (my_score - safe) / safe if safe > 0 else 0
    if excess_ratio >= 0.01:  # 1% 이상 초과
        return "하향"
    return "안정"
if appropriate and my_score >= appropriate:
    return "적정"
if expected and my_score >= expected:
    return "소신"
if challenge and my_score >= challenge:
    return "도전"
return "어려움"
```

#### 3.3.3 컷 점수 데이터 구조 (universities.json)

```json
{
  "id": "가1",
  "formulaId": 5,
  "gun": "가",
  "university": "연세대",
  "department": "시스템반도체공학과",
  "track": "자연",
  "safeScore": 670.259,        // 안정컷
  "appropriateScore": 669.463, // 적정컷
  "expectedScore": 668.39,     // 소신컷 (예상컷)
  "challengeScore": 663.419,   // 도전컷
  "scoreMethod": "표점",
  "tamguMethod": "변표",
  "koreanRatio": 0.25,
  "mathRatio": 0.38,
  "tamguRatio": 0.38
}
```

#### 3.3.4 필터링 옵션

```python
def run_suneung_search(
    normalized_scores: Dict[str, Any],
    target_univ: Optional[List[str]] = None,   # 대학 필터
    target_major: Optional[List[str]] = None,  # 학과 필터
    target_range: Optional[List[str]] = None,  # 판정 필터
    target_gun: Optional[str] = None,          # 군 필터 (가/나/다)
) -> List[Dict[str, Any]]:
```

**필터링 규칙**:
- `target_range`가 없으면 기본적으로 "하향" 제외
- 대학명 정규화: "경북대학교" → "경북대" 매칭
- 학과명 유연한 매칭: "컴퓨터공학과" → "컴퓨터"로 변환

---

### 3.4 [4단계] 결과 포맷팅

**위치**: `functions.py` 423-556줄

#### 3.4.1 청크 구조

```python
chunks = []

# 청크 1: 성적 분석
chunks.append({
    "document_id": "score_conversion",
    "chunk_id": "score_analysis",
    "chunk_type": "score_analysis",
    "content": "**학생 성적 분석**\n..."
})

# 청크 2~N: 판정별 분리된 결과
for range_name in ["안정", "적정", "소신", "도전", "어려움", "하향"]:
    chunks.append({
        "document_id": f"admission_results_{range_name}",
        "chunk_id": f"reverse_search_{range_name}",
        "chunk_type": f"reverse_search_{range_name}",
        "content": "**🟢 안정 지원 가능 대학 (N개)**\n| 대학 | 학과 | ... |",
        "range": range_name,
        "count": len(range_items)
    })
```

#### 3.4.2 출력 테이블 형식

```markdown
**🟢 안정 지원 가능 대학 (15개)**
| 대학 | 학과 | 군 | 계열 | 내 점수 | 안정컷 | 적정컷 | 소신컷 | 도전컷 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 연세대 | 시스템반도체공학과 | 가 | 자연 | 672.5 | 670.26 | 669.46 | 668.39 | 663.42 |
```

#### 3.4.3 토큰 제한

```python
CONSULT_TOKEN_LIMIT = 40960  # consult_jungsi는 40960 토큰

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2)  # 한글 1자 ≈ 2토큰
```

---

## 4. 데이터 소스

### 4.1 파일 구조

```
score_system/
├── data/
│   ├── universities.json        # 86개 대학, 2158개 학과 정보 + 컷 점수
│   ├── formulas_extracted.json  # 267개 환산 공식
│   ├── deduction_tables.json    # 영어/한국사 감점표
│   ├── standard.py              # 수능 표준점수/백분위 변환표
│   └── admission_results/       # 대학별 입결 데이터 (deprecated)
│       ├── yonsei_2025.json
│       ├── korea_2025.json
│       └── ...
```

### 4.2 데이터 통계

| 항목 | 수량 |
|-----|-----|
| 지원 대학 수 | 86개 |
| 지원 학과 수 | 2,158개 |
| 환산 공식 수 | 267개 |
| 군 분류 | 가/나/다 |

---

## 5. 판정 기준 상세

### 5.1 컷 점수 정의

| 컷 종류 | 영문명 | 의미 |
|--------|-------|------|
| 안정컷 | safeScore | 합격 가능성 매우 높음 (상위권 합격선) |
| 적정컷 | appropriateScore | 합격 가능성 높음 (중상위권 합격선) |
| 소신컷 | expectedScore | 합격 가능성 보통 (예상 합격선) |
| 도전컷 | challengeScore | 합격 가능성 낮음 (하위권 합격선) |

### 5.2 판정 흐름도

```
                    내 점수
                       │
                       ▼
            ┌─────────────────────┐
            │ safeScore * 1.01 이상? │
            └─────────────────────┘
                   │ Yes      │ No
                   ▼          ▼
              ⬇️ 하향    ┌─────────────────┐
                        │ safeScore 이상?  │
                        └─────────────────┘
                              │ Yes    │ No
                              ▼        ▼
                         🟢 안정  ┌─────────────────────┐
                                 │ appropriateScore 이상? │
                                 └─────────────────────┘
                                       │ Yes    │ No
                                       ▼        ▼
                                  🟡 적정  ┌─────────────────┐
                                          │ expectedScore 이상? │
                                          └─────────────────┘
                                                │ Yes    │ No
                                                ▼        ▼
                                           🟠 소신  ┌─────────────────┐
                                                   │ challengeScore 이상? │
                                                   └─────────────────┘
                                                         │ Yes    │ No
                                                         ▼        ▼
                                                    🔴 도전   ⚫ 어려움
```

---

## 6. 정확도 관련 주의사항

### 6.1 추정값 사용 시

- **등급만 입력된 경우**: 등급별 대표 백분위를 사용하여 표준점수를 추정
- 추정값은 `비고` 필드에 "등급기반추정" 또는 "단순추정"으로 표시됨

### 6.2 데이터 한계

1. **컷 점수 데이터**: 2025학년도 기준 (2026학년도 예측값)
2. **환산 공식**: 대학별 공식 변경 시 업데이트 필요
3. **탐구 변환표**: 일부 대학은 자체 변환표 사용

### 6.3 계산 불가 케이스

- `tamguCoef`가 '자동'인 경우 → 0으로 처리
- 공식이 없는 대학/학과 → `None` 반환

---

## 7. 관련 파일 목록

| 파일 | 역할 |
|-----|------|
| `functions.py` | consult_jungsi 메인 실행 로직 |
| `processor.py` | 성적 정규화 및 프롬프트 생성 |
| `converter.py` | ScoreConverter 클래스 (점수 변환) |
| `suneung_calculator.py` | 대학별 환산점수 계산 |
| `search_engine.py` | 리버스 서치 엔진 |
| `config.py` | 판정 기준 및 상수 정의 |
| `data/universities.json` | 대학/학과 정보 + 컷 점수 |
| `data/formulas_extracted.json` | 환산 공식 |
| `data/deduction_tables.json` | 영어/한국사 감점표 |
| `data/standard.py` | 수능 표준점수/백분위 변환표 |

---

## 8. 정확도 테스트 결과 (2026-02-12)

### 8.1 테스트 결과 요약

| 테스트 항목 | 결과 | 상세 |
|------------|------|------|
| 선택과목 처리 | ✅ PASS | 3/3 케이스 통과 |
| 환산점수 계산 | ⚠️ WARN | **893개 만점 초과 케이스 발견** |
| 상식적 결과 | ❌ FAIL | 2/4 케이스 실패 |

### 8.2 발견된 주요 문제

#### (1) 만점 초과 문제 (893개 케이스)

| 초과율 | 케이스 수 | 예시 |
|--------|----------|------|
| 400% 이상 | ~50개 | 충북대 (만점 200, 실제 1004점) |
| 100~400% | ~200개 | 순천향대 의예 등 |
| 10~100% | ~300개 | 연세대 미래캠퍼스 등 |
| 1~10% | ~343개 | 이화여대, 한양대 등 |

**원인**: `formulas_extracted.json`의 `maxScore` 값이 실제 계산 결과와 불일치

#### (2) 비정상 판정 문제

| 등급 | 대학 | 판정 | 문제 |
|-----|------|------|------|
| 3등급 | 연세대 (미래캠) | 🟢 안정 | 3등급이 연세대 안정? |
| 3등급 | 한양대 (ERICA) | 🟢 안정 | 환산점수 과대 산출 |
| 4등급 | 고려대 (세종) | 🟢 안정 | 4등급이 고려대 안정? |
| 4등급 | 성균관대 | 🟢 안정 | 환산점수 과대 산출 |

**원인**: 
1. 환산 공식의 계수가 과도하게 높음
2. 컷 점수 데이터가 실제보다 낮게 설정됨

### 8.3 긴급 수정 필요 사항

1. **maxScore 검증**: `formulas_extracted.json`의 모든 공식 검증
2. **만점 초과 방지**: 환산점수 계산 시 만점 클램핑 로직 추가
3. **컷 점수 검증**: `universities.json`의 컷 점수가 maxScore 범위 내인지 확인

### 8.4 테스트 스크립트

테스트 스크립트 위치: `backend/services/multi_agent/score_system/test_consult_jungsi.py`

```bash
cd backend && python3 -m services.multi_agent.score_system.test_consult_jungsi
```

상세 테스트 결과: `consult_jungsi_테스트_결과_보고서.md` 참조
