# 타이밍 측정 시스템 테스트 가이드

## 빠른 시작 (5분 테스트)

### 1단계: 서버 실행

**터미널 1 - 백엔드**:
```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**터미널 2 - 프론트엔드**:
```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/frontend
npm run dev
```

### 2단계: 브라우저 테스트

1. 브라우저에서 `http://localhost:5173` 접속
2. 로그인 (김도균 계정으로)
3. 질문 입력: "서울대 컴퓨터공학과 정시 입결 알려줘"
4. F12 → Console 탭에서 타이밍 로그 확인
5. `/timing-dashboard` 접속하여 시각화 확인

### 3단계: 터미널에서 로그 확인

**터미널 3 - 로그 모니터링**:
```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend/logs

# CSV 실시간 모니터링
tail -f timing_summary.csv

# 또는 JSON 상세 로그
tail -f timing_details.jsonl | jq '.'
```

---

## 상세 테스트 방법

## A. 백엔드 테스트 (터미널)

### A-1. 기본 타이밍 측정 테스트

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend

# 백엔드 서버 실행 (타이밍 로그가 콘솔에 출력됨)
python -m uvicorn main:app --reload
```

**서버 실행 후 보이는 것**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**채팅 요청 시 출력**:
```
🔵 [STREAM_REQUEST_START] test-session:서울대 컴퓨터공학과:1738000000

# ... 파이프라인 실행 로그 ...

================================================================================
⏱️  타이밍 측정 요약
================================================================================
📋 세션 ID: test-session
🆔 요청 ID: test-session:서울대 컴퓨터공학과:1738000000
⏰ 총 소요 시간: 28.45초
--------------------------------------------------------------------------------

1️⃣  Orchestration Agent: 3.21초
   - 프롬프트 생성: 0.01초
   - API 호출: 3.15초
   - 파싱: 0.05초

2️⃣  Sub Agents: 12.34초
   [서울대 agent]
      - 전체: 7.23초
      - DB 조회: 0.45초
      - LLM 호출: 6.50초
      - 후처리: 0.28초
   [컨설팅 agent]
      - 전체: 5.11초
      - DB 조회: 0.30초
      - LLM 호출: 4.65초
      - 후처리: 0.16초

3️⃣  Final Agent: 10.89초
   - 히스토리 병합: 0.01초
   - 결과 포맷팅: 0.04초
   - 구조 포맷팅: 0.01초
   - 프롬프트 조립: 0.02초
   - API 호출: 10.70초
   - 후처리: 0.11초

4️⃣  저장 및 기타: 0.21초
   - 히스토리 저장: 0.001초
   - DB 저장: 0.209초
================================================================================

🟢 [STREAM_REQUEST_END] test-session:서울대 컴퓨터공학과:1738000000
```

### A-2. CSV 로그 분석

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend/logs

# 헤더와 함께 보기
cat timing_summary.csv | column -t -s,

# 최근 10개 요청
tail -10 timing_summary.csv | column -t -s,

# 총 시간으로 정렬 (가장 느린 요청)
tail -n +2 timing_summary.csv | sort -t, -k4 -rn | head -5 | column -t -s,

# 평균 시간 계산
awk -F, 'NR>1 {sum+=$4; count++} END {print "평균:", sum/count, "초"}' timing_summary.csv
```

**출력 예시**:
```
timestamp                session_id     request_id                           total_time  orch_time  sub_agents_time  final_time  db_time  network_time
2026-01-27T10:30:15.123  test-session   test-session:서울대:1738000000      28.456      3.210      12.340           10.890      0.210    13.850
2026-01-27T10:32:45.456  test-session   test-session:연세대:1738000001      25.123      2.980      10.230           9.450       0.198    12.430
...
```

### A-3. JSON 상세 로그 분석

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend/logs

# 가장 최근 요청의 상세 정보
tail -1 timing_details.jsonl | jq '.'

# 특정 필드만 추출
tail -5 timing_details.jsonl | jq '{
  session: .session_id,
  total: .total_time,
  orch: .durations.orchestration.total,
  sub: .durations.sub_agents.total,
  final: .durations.final_agent.total
}'

# Agent별 시간 분석
tail -1 timing_details.jsonl | jq '.durations.sub_agents.agents'
```

### A-4. 병렬 vs 순차 실행 비교 테스트

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend

# 테스트 스크립트 실행
python test_timing.py
```

**출력 예시**:
```
🧪 타이밍 측정 시스템 테스트

테스트 선택:
1. 병렬 vs 순차 실행 비교
2. 캐시 성능 테스트
3. 모두 실행

선택 (1-3): 1

================================================================================
타이밍 측정 테스트 시작
================================================================================

1. Orchestration Agent 실행 중...
   실행 계획: 2개 Agent
   - Step 1: 서울대 agent
   - Step 2: 컨설팅 agent

2. 순차 실행 테스트...
   완료 시간: 15.67초

3. 병렬 실행 테스트...
   완료 시간: 8.23초

================================================================================
결과 비교
================================================================================
순차 실행: 15.67초
병렬 실행: 8.23초
개선율: 47.5%
절약 시간: 7.44초
================================================================================
```

### A-5. 캐시 성능 테스트

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend

# 테스트 스크립트 실행
python test_timing.py
# → 2 선택
```

**출력 예시**:
```
================================================================================
캐시 성능 테스트
================================================================================

1. 첫 번째 조회 (캐시 미스 예상)...
   완료 시간: 7.45초
   캐시 통계: 0 히트 / 5 미스

2. 두 번째 조회 (캐시 히트 예상)...
   완료 시간: 6.89초
   캐시 통계: 3 히트 / 2 미스

================================================================================
결과 비교
================================================================================
첫 번째 (캐시 미스): 7.45초
두 번째 (캐시 히트): 6.89초
개선율: 7.5%
히트율: 60.0%
================================================================================
```

### A-6. Python 대화형 테스트

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/backend
python
```

```python
# 캐시 통계 확인
from utils.document_cache import cache_stats, cache_get, cache_set, get_document_cache

stats = cache_stats()
print(f"캐시 크기: {stats['size']}/{stats['max_size']}")
print(f"히트: {stats['hits']}, 미스: {stats['misses']}")
print(f"히트율: {stats['hit_rate']}%")

# 캐시 내용 확인
cache = get_document_cache()
print(f"캐시 항목 수: {len(cache._cache)}")

# 로그 파일 통계
import pandas as pd
df = pd.read_csv('logs/timing_summary.csv')
print(df.describe())
print(f"\n평균 총 시간: {df['total_time'].mean():.2f}초")
print(f"평균 Orchestration: {df['orch_time'].mean():.2f}초")
print(f"평균 Sub Agents: {df['sub_agents_time'].mean():.2f}초")
print(f"평균 Final Agent: {df['final_time'].mean():.2f}초")
```

---

## B. 프론트엔드 테스트 (브라우저)

### B-1. 기본 타이밍 측정 테스트

1. **브라우저 열기**: `http://localhost:5173`

2. **로그인** (김도균 계정)

3. **채팅 질문**:
   - "서울대 컴퓨터공학과 정시 입결 알려줘"
   - "국어 1등급 수학 2등급으로 갈 수 있는 대학"
   - "연세대 경영학과 수시 전형"

4. **F12 (개발자 도구) 열기**

5. **Console 탭**에서 타이밍 로그 확인:
   ```
   ⏱️ 프론트엔드 타이밍 측정
   📋 세션 ID: abc123-def456
   🆔 요청 ID: abc123:서울대 컴퓨터공학과:1738000000
   ⏰ 총 소요 시간: 28450ms
   
   📊 단계별 소요 시간:
     1. 세션 준비: 5ms
     2. UI 업데이트: 12ms
     3. 요청 준비: 3ms
     4. 네트워크 대기: 1245ms
     5. 스트리밍 수신: 27050ms
     6. 파싱: 8ms
     7. 렌더링: 45ms
     8. 저장: 82ms
   ```

### B-2. LocalStorage 데이터 확인

**Application 탭**:
1. 좌측 메뉴: Storage → Local Storage → `http://localhost:5173`
2. `frontend_timing_logs` 클릭
3. Value 필드의 JSON 데이터 확인

**Console에서 조회**:
```javascript
// 모든 로그 가져오기
const logs = JSON.parse(localStorage.getItem('frontend_timing_logs'))

// 테이블로 보기
console.table(logs.map(log => ({
  시간: new Date(log.timestamp).toLocaleTimeString(),
  총시간: `${log.total_time_ms.toFixed(0)}ms`,
  네트워크: `${log.durations_ms.network_wait.toFixed(0)}ms`,
  스트리밍: `${log.durations_ms.streaming.toFixed(0)}ms`,
  렌더링: `${log.durations_ms.rendering.toFixed(0)}ms`
})))

// 평균 계산
const avg = logs.reduce((acc, log) => ({
  total: acc.total + log.total_time_ms,
  network: acc.network + log.durations_ms.network_wait,
  streaming: acc.streaming + log.durations_ms.streaming
}), { total: 0, network: 0, streaming: 0 })

console.log('평균 시간:')
console.log(`  총: ${(avg.total / logs.length).toFixed(0)}ms`)
console.log(`  네트워크: ${(avg.network / logs.length).toFixed(0)}ms`)
console.log(`  스트리밍: ${(avg.streaming / logs.length).toFixed(0)}ms`)

// 가장 느린 요청 찾기
const slowest = logs.reduce((max, log) => 
  log.total_time_ms > max.total_time_ms ? log : max
)
console.log('가장 느린 요청:', slowest.total_time_ms.toFixed(0), 'ms')

// 가장 빠른 요청 찾기
const fastest = logs.reduce((min, log) => 
  log.total_time_ms < min.total_time_ms ? log : min
)
console.log('가장 빠른 요청:', fastest.total_time_ms.toFixed(0), 'ms')
```

### B-3. 타이밍 대시보드 사용

1. **접속**: `http://localhost:5173/timing-dashboard`

2. **통계 카드 확인**:
   - 총 요청 수
   - 평균 총 시간 (최소/최대)
   - 평균 네트워크 대기 (최소/최대)

3. **테이블에서 확인**:
   - 시간순 정렬
   - 각 요청의 단계별 시간
   - "보기" 버튼으로 상세 정보

4. **상세 모달**:
   - 기본 정보
   - 단계별 바 차트 (퍼센트 표시)

5. **기능 테스트**:
   - "새로고침" 버튼: 데이터 다시 로드
   - "로그 삭제" 버튼: 모든 데이터 삭제

### B-4. 네트워크 탭에서 SSE 스트림 확인

1. **Network 탭** 열기
2. **채팅 질문** 입력
3. **stream 요청** 클릭
4. **Preview** 또는 **Response** 탭에서 실시간 데이터 확인:
   ```
   data: {"type":"log","message":"🎯 Orchestration Agent 실행"}
   data: {"type":"log","message":"🤖 Sub Agents 실행"}
   data: {"type":"log","message":"📝 Final Agent 실행"}
   data: {"type":"result","data":{...}}
   ```

### B-5. Performance 탭에서 렌더링 성능 확인

1. **Performance 탭** 열기
2. **Record 시작** (빨간 원)
3. **채팅 질문** 입력 및 답변 대기
4. **Record 중지**
5. **Flame Chart** 확인:
   - Scripting: JavaScript 실행 시간
   - Rendering: 레이아웃/페인트
   - Painting: 실제 그리기

---

## C. 통합 테스트 시나리오

### 시나리오 1: 기본 플로우 테스트

**목적**: 전체 시스템이 정상 작동하는지 확인

1. 백엔드 + 프론트엔드 서버 실행
2. 브라우저에서 질문 3개 입력
3. 터미널에서 CSV 로그 확인
4. 대시보드에서 통계 확인

**예상 결과**:
- 3개 요청의 타이밍 로그가 CSV에 기록됨
- 대시보드에 3개 요청 표시
- 콘솔에 타이밍 요약 출력

### 시나리오 2: 병렬 실행 효과 검증

**목적**: 병렬 실행이 실제로 성능을 개선하는지 확인

1. `test_timing.py` 실행 (옵션 1)
2. 순차 vs 병렬 시간 비교
3. 개선율 30% 이상 확인

**예상 결과**:
- 병렬 실행이 순차보다 빠름
- 개선율: 40-60%
- 절약 시간: 5-10초

### 시나리오 3: 캐시 효과 검증

**목적**: 캐시가 반복 조회를 빠르게 하는지 확인

1. 같은 대학에 대해 질문 2번 (예: "서울대 입결")
2. 첫 번째와 두 번째 요청 시간 비교
3. 캐시 통계 확인

**예상 결과**:
- 두 번째 요청이 더 빠름 (DB 조회 시간 단축)
- 캐시 히트율 증가
- 로그에 "✅ 캐시 히트" 메시지

### 시나리오 4: 부하 테스트

**목적**: 연속 요청 시 성능 확인

```bash
# 10개 요청 연속 전송
for i in {1..10}; do
  curl -X POST "http://localhost:8000/api/chat/stream" \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"서울대 $i\", \"session_id\": \"test-$i\"}" &
done
wait

# 결과 확인
tail -10 backend/logs/timing_summary.csv | column -t -s,
```

**예상 결과**:
- 10개 요청 모두 처리됨
- 평균 시간이 크게 증가하지 않음
- 캐시 효과로 후반 요청이 더 빠를 수 있음

---

## D. 트러블슈팅

### 문제 1: 로그 파일이 생성되지 않음

**원인**: `backend/logs/` 디렉토리가 없음

**해결**:
```bash
mkdir -p backend/logs
```

### 문제 2: 프론트엔드 타이밍이 기록되지 않음

**원인**: LocalStorage 제한 또는 브라우저 지원 문제

**해결**:
```javascript
// Console에서 확인
console.log('LocalStorage 사용 가능:', typeof localStorage !== 'undefined')
console.log('performance.now 지원:', typeof performance.now === 'function')

// 수동으로 저장 테스트
localStorage.setItem('test', 'value')
console.log(localStorage.getItem('test'))
```

### 문제 3: 대시보드 404 에러

**원인**: 라우터 설정 누락

**해결**: `App.tsx`에 라우트가 추가되었는지 확인
```typescript
<Route path="/timing-dashboard" element={<TimingDashboard />} />
```

### 문제 4: 캐시가 작동하지 않음

**확인**:
```python
from utils.document_cache import cache_stats
stats = cache_stats()
print(stats)  # hits와 misses 확인
```

### 문제 5: 타이밍이 부정확함

**원인**: 시스템 시간 동기화 문제

**해결**:
- 백엔드: `time.time()` 사용 확인
- 프론트엔드: `performance.now()` 사용 확인

---

## E. 성능 기준

### 정상 범위
- **총 시간**: 15-40초 (평균 25-30초)
- **Orchestration**: 2-5초
- **Sub Agents** (병렬): 5-15초
- **Final Agent**: 5-15초
- **DB 조회** (캐시 미스): 0.5-2초
- **DB 조회** (캐시 히트): 0.01-0.1초

### 주의 필요
- 총 시간 > 60초
- Orchestration > 10초
- Sub Agents > 30초
- Final Agent > 20초

### 최적화 필요
- 총 시간 > 90초
- 반복 조회인데 캐시 히트 안 됨
- 병렬 실행인데 순차만큼 느림

---

## F. 데이터 내보내기

### CSV to Excel
```bash
# LibreOffice/Excel로 열기
open backend/logs/timing_summary.csv
```

### JSON to CSV
```bash
cd backend/logs

# jq로 JSON을 CSV로 변환
jq -r '[.timestamp, .session_id, .total_time, .durations.orchestration.total, .durations.sub_agents.total, .durations.final_agent.total] | @csv' timing_details.jsonl > timing_export.csv
```

### 프론트엔드 데이터 내보내기
```javascript
// Console에서 실행
const logs = JSON.parse(localStorage.getItem('frontend_timing_logs'))
const csv = logs.map(log => 
  [log.timestamp, log.session_id, log.total_time_ms, 
   log.durations_ms.network_wait, log.durations_ms.streaming].join(',')
).join('\n')
console.log(csv)
// 복사해서 파일로 저장
```

---

## 요약: 5분 빠른 체크리스트

- [ ] 백엔드 서버 실행 확인
- [ ] 프론트엔드 서버 실행 확인
- [ ] 브라우저에서 질문 1개 입력
- [ ] F12 Console에서 타이밍 로그 확인
- [ ] `timing_summary.csv` 파일 생성 확인
- [ ] `/timing-dashboard` 접속 확인
- [ ] 캐시 통계 확인 (Python)
- [ ] 병렬 실행 테스트 (`test_timing.py`)

모든 항목이 체크되면 타이밍 측정 시스템이 정상 작동하는 것입니다! ✅
