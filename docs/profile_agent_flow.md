# Profile Agent 흐름 정리

## 개요

사용자가 채팅 메시지에 성적 정보를 포함하면, **Profile Agent**가 이를 감지하여 성적 입력 카드를 표시한다.  
Router Agent와 **병렬로 실행**되며, 성적이 확인되면 해당 성적 기반으로 답변을 생성한다.

---

## 전체 흐름 다이어그램

```
사용자 메시지 입력
    │
    ▼
_prepare_score_review_gate()
    ├──→ Router Agent (async)    ─┐ 병렬 실행
    └──→ Profile Agent (thread)  ─┘ (asyncio.gather)
    │
    ▼
 분기 결정:
    ├─ 성적 없음 (has_candidate=false) → "pass" → 일반 채팅 파이프라인
    ├─ @멘션으로 기존 성적 참조       → "pass" → score_id 포함하여 진행
    ├─ skip_session 플래그 설정됨     → "auto" → 자동 저장 후 score_id로 진행
    └─ 성적 감지, 리뷰 필요          → "review" → score_review_required 이벤트 전송
    │
    ▼ (review인 경우)
프론트엔드: 성적 검토 카드 표시
    │
    ▼
사용자 액션:
    ├─ "확인" → 성적 저장 → 원래 질문 자동 재전송 (score_id 포함) → 답변 생성
    ├─ "수정" → 성적 수정 후 "확인"
    └─ "다시 묻지 않기" → 세션 스킵 플래그 설정 → 카드 제거
```

---

## 백엔드

### 1. `_prepare_score_review_gate()` — 게이트 함수

**파일**: `backend/routers/chat.py` (line 183~246)

사용자 메시지를 받아 성적 리뷰가 필요한지 판단하는 핵심 함수.

**실행 순서**:

1. `score_id_override` (프론트엔드 `activeScoreId`) 있으면 → `"pass"` 반환 (게이트 건너뜀)
2. 메시지 내 `@멘션`으로 기존 성적 참조 → `resolve_score_id_from_message()` → `"pass"`
3. 세션 스킵 플래그 확인 → `get_session_skip_score_review()`
4. **Router Agent + Profile Agent 병렬 실행** → `run_router_and_profile_parallel()`
5. `candidate.has_candidate == false` → `"pass"` (성적 미감지)
6. `skip_session == true` → 자동 저장 → `"auto"`
7. 그 외 → pending 레코드 생성 → `"review"` 반환

```python
router_coro = route_query(message, history, user_id=user_id)
router_output, candidate = await run_router_and_profile_parallel(
    router_coro=router_coro,
    message=message,
    existing_score_sets=existing,
)
```

### 2. `run_router_and_profile_parallel()` — 병렬 실행

**파일**: `backend/services/score_review.py` (line 165~171)

```python
async def run_router_and_profile_parallel(router_coro, message, existing_score_sets):
    profile_task = asyncio.to_thread(extract_score_candidate, message, existing_score_sets)
    return await asyncio.gather(router_coro, profile_task)
```

- **Router Agent**: async 코루틴으로 실행 (`route_query()`)
- **Profile Agent**: 동기 함수이므로 `asyncio.to_thread()`로 별도 스레드에서 실행
- `asyncio.gather()`로 **두 작업이 동시에** 실행되어 대기 시간 절감

### 3. `extract_score_candidate()` — 성적 추출

**파일**: `backend/services/score_review.py` (line 74~104)

1. `ExtractorAgent.extract(message)` → 메시지에서 원시 성적 추출
2. `CompletionAgent.complete(...)` → 누락된 과목 보완
3. `_has_score_value()` → 유효한 성적이 있는지 검증
4. `_next_score_title()` → 자동 제목 생성 (예: `@내성적1`, `@내성적2`)

**반환**: `ScoreCandidate(has_candidate, extracted_scores, completed_scores, title_auto)`

### 4. SSE 이벤트 전송

**파일**: `backend/routers/chat.py` (line 943~958)

`gate_mode == "review"`일 때 SSE 이벤트로 프론트엔드에 전달:

```python
review_event = {
    "type": "score_review_required",
    "pending_id": gate.get("pending_id"),
    "title_auto": gate.get("title_auto"),
    "scores": gate.get("scores", {}),
    "constraints": {
        "title_max_length": 10,
        "standard_score": {"min": 0, "max": 200},
        "percentile": {"min": 0, "max": 100},
        "grade": {"min": 1, "max": 9},
    },
    "actions": ["edit", "approve", "skip_session"],
}
yield f"data: {json.dumps(review_event, ensure_ascii=False)}\n\n"
return  # 파이프라인 중단, 사용자 액션 대기
```

### 5. 성적 승인/스킵 API

| 엔드포인트 | 동작 |
|---|---|
| `POST /chat/v2/score-review/approve` | pending → approved, `user_score_sets`에 저장, `score_id` 반환 |
| `POST /chat/v2/score-review/skip-session` | pending → skipped, `chat_session_flags`에 skip 플래그 설정 |
| `GET /chat/v2/score-sets/suggest` | `@멘션` 자동완성용 성적 목록 조회 |
| `GET /chat/v2/score-sets/by-name` | 이름으로 성적 조회 (칩 클릭 시 보기용) |

---

## 프론트엔드

### 1. SSE 이벤트 수신

**파일**: `frontend/src/api/client.ts` (line 372~374)

```typescript
} else if (event.type === 'score_review_required') {
    onScoreReviewRequired?.(event as ScoreReviewRequiredEvent)
    return  // 스트리밍 종료
}
```

### 2. 이벤트 핸들러

**파일**: `frontend/src/pages/ChatPage.tsx`

`onScoreReviewRequiredCallback`: 스트리밍 중인 봇 메시지를 성적 검토 카드로 교체

```typescript
setMessages((prev) => prev.map(msg =>
    msg.id === streamingBotMessageId
        ? { ...msg, text: '', isStreaming: false, scoreReview: { pendingId, titleAuto, scores } }
        : msg
))
```

### 3. 사용자 액션 처리

#### "확인" (Approve)

1. `approveScoreReview()` API 호출 → `score_id` 수신
2. 원래 사용자 질문 찾기 (이전 메시지에서 검색)
3. 성적 카드를 스트리밍 메시지로 교체
4. `sendMessageStream()` 재호출: 원래 질문 + `score_id` → 답변 스트리밍

#### "다시 묻지 않기" (Skip Session)

1. `skipScoreReviewSession()` API 호출
2. 세션에 skip 플래그 설정 → 이후 같은 세션에서는 성적 카드 안 뜸

### 4. 성적 검토 카드 UI

**파일**: `frontend/src/components/ChatMessage.tsx` (line 537~670)

- 조건: `!isUser && scoreReview` 일 때 렌더링
- 제목 입력 (`@` 자동 프리픽스, 최대 10자)
- 성적 테이블: 한국사, 국어, 수학, 영어, 탐구1, 탐구2, 제2외국어/한문
- 각 과목: 선택과목 (드롭다운), 표준점수 (0~200), 백분위 (0~100), 등급 (1~9)
- 버튼: 수정 / 확인 / 다시 묻지 않기

### 5. `@멘션` 자동완성

**파일**: `frontend/src/pages/ChatPage.tsx`

1. 사용자가 `@` 입력 → `getMentionContext()` → caret 위치에서 `@쿼리` 추출
2. `useEffect`에서 `suggestScoreSets()` 디바운스 호출
3. 드롭다운 렌더링 → 키보드/클릭으로 선택
4. `applyScoreSuggestion()` → 입력값 업데이트 + `activeScoreId` 설정

---

## Supabase 테이블

| 테이블 | 용도 |
|---|---|
| `user_score_sets` | 저장된 성적표 (이름, 과목별 점수, 소유자) |
| `chat_score_pending` | 성적 리뷰 대기 레코드 (status: review_required → approved/skipped) |
| `chat_session_flags` | 세션별 플래그 (skip_score_review 등) |

---

## 핵심 설계 결정

1. **병렬 실행**: Router Agent와 Profile Agent를 `asyncio.gather()`로 동시 실행하여 응답 지연 최소화
2. **게이트 패턴**: 성적 리뷰는 메인 파이프라인(orchestration → sub agents → final agent) 실행 전에 판단
3. **자동 재전송**: 성적 확인 후 하드코딩 메시지 없이 원래 질문을 score_id와 함께 재전송하여 즉시 답변 생성
4. **세션 레벨 스킵**: "다시 묻지 않기"로 같은 세션 내 반복 리뷰 방지
5. **@멘션 우선**: 메시지에 `@성적명`이 있으면 리뷰 없이 해당 성적 직접 사용
6. **조건부 score_id 전달**: `@멘션`이 없는 메시지에는 `activeScoreId`를 전달하지 않아 새 성적 감지 가능
