# Sub Agent Test

프로덕션과 100% 동일한 Sub Agent 테스트 환경입니다. **실제 DB 연결 및 Python 함수 포함**.

## ⚠️ 중요: 두 가지 실행 방식

### 1. main_simple.py (Mock 버전) - 현재 실행 중 ✅
- **목적**: UI 및 프롬프트 테스트
- **특징**: Mock 응답으로 빠른 테스트 가능
- **장점**: 의존성 충돌 없이 즉시 실행 가능
- **단점**: 실제 DB 연결 없음, 실제 점수 계산 안함
- **포트**: 8092

### 2. main.py (실제 버전) - 의존성 해결 필요
- **목적**: 프로덕션과 100% 동일한 실제 테스트
- **특징**: Supabase 연결, 실제 점수 계산 함수 사용
- **장점**: 프로덕션과 완전히 동일한 동작
- **단점**: pydantic 버전 충돌 해결 필요
- **포트**: 8092

**현재는 main_simple.py를 사용하여 UI와 프롬프트 테스트를 진행하세요!**

## 기능

- **프로덕션 동일 로직**: 메인 프로젝트의 `services/multi_agent/sub_agents.py`와 100% 동일한 구현
- **실제 DB 연결**: Supabase에서 실시간 문서 검색 (UniversityAgent)
- **실제 Python 함수**: 
  - `score_converter.py` - 점수 변환
  - `khu_score_calculator.py` - 경희대 환산
  - `snu_score_calculator.py` - 서울대 환산
  - `yonsei_score_calculator.py` - 연세대 환산
  - `korea_score_calculator.py` - 고려대 환산
  - `sogang_score_calculator.py` - 서강대 환산
- **3가지 Agent 타입 지원**:
  - 🏫 **UniversityAgent**: 대학별 입시 정보 검색
  - 📊 **ConsultingAgent**: 성적 분석 및 환산
  - 👨‍🏫 **TeacherAgent**: 학습 계획 및 조언
- **커스텀 프롬프트 지원**: ConsultingAgent와 TeacherAgent의 시스템 프롬프트 수정 가능
- **프롬프트/데이터셋 관리**: 저장 및 재사용

## 실행 방법

### 1. 의존성 설치

```bash
cd agent-tests/sub-agent-test
pip install -r requirements.txt
```

### 2. 환경 변수 설정

프로젝트 루트의 `.env` 파일에 다음 환경 변수가 설정되어 있어야 합니다:

```
GEMINI_API_KEY=your-gemini-api-key
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
```

### 3. 서버 실행

```bash
python backend/main.py
```

서버가 http://localhost:8092 에서 실행됩니다.

### 4. 테스트 UI 열기

브라우저에서 `index.html` 파일을 직접 열거나:

```bash
open index.html  # macOS
```

## Agent 타입별 사용법

### 1️⃣ UniversityAgent (대학별 Agent)

**목적**: Supabase에서 특정 대학의 입시 정보 검색

**특징**:
- 실제 Supabase DB 연결
- 해시태그 기반 문서 검색
- 요약본 분석 후 전체 내용 로드
- 시스템 프롬프트 사용하지 않음 (검색 기반)

**사용 예시**:
- Agent 타입: `university`
- 대학 선택: `서울대`
- 쿼리: `2025학년도 정시 의예과 모집 인원`

### 2️⃣ ConsultingAgent (컨설팅 Agent)

**목적**: 학생 성적 기반 합격 가능성 분석 및 점수 환산

**특징**:
- 실제 점수 변환 로직 사용
- 경희대/서울대/연세대/고려대/서강대 환산 점수 자동 계산
- 성적 정규화 (등급-표준점수-백분위)
- **커스텀 시스템 프롬프트 지원**

**사용 예시**:
- Agent 타입: `consulting`
- 쿼리: `나 11232야. 경희대 의대 갈 수 있어?`

**정규화 결과 확인**:
- 과목별 성적 (등급/표준점수/백분위)
- 경희대 환산 점수 (600점 만점)
- 서울대 환산 점수 (1000점 스케일)
- 연세대/고려대/서강대 환산 점수

### 3️⃣ TeacherAgent (선생님 Agent)

**목적**: 학습 계획 수립 및 멘탈 관리 조언

**특징**:
- 20년 경력 입시 전문가 페르소나
- 현실적인 목표 설정 및 계획 제시
- **커스텀 시스템 프롬프트 지원**

**사용 예시**:
- Agent 타입: `teacher`
- 쿼리: `내신 2등급인데 수시로 어디까지 쓸 수 있을까요?`

## 프롬프트 수정

ConsultingAgent와 TeacherAgent는 시스템 프롬프트를 수정하여 테스트할 수 있습니다.

### 프롬프트 수정 방법

1. Agent 타입 선택
2. "📄 기본 프롬프트 불러오기" 버튼 클릭
3. 커스텀 프롬프트 텍스트 영역에서 수정
4. "🚀 Sub Agent 실행" 버튼으로 테스트
5. "💾 프롬프트 저장" 버튼으로 저장

### 프롬프트 플레이스홀더 (ConsultingAgent)

ConsultingAgent의 프롬프트는 다음 플레이스홀더를 자동으로 채웁니다:

```
{normalized_scores_text}  - 정규화된 성적
{khu_scores_text}         - 경희대 환산 점수
{snu_scores_text}         - 서울대 환산 점수
{yonsei_scores_text}      - 연세대 환산 점수
{korea_scores_text}       - 고려대 환산 점수
{sogang_scores_text}      - 서강대 환산 점수
{all_data}                - Mock DB 데이터
```

**주의**: 이 플레이스홀더들은 자동으로 채워지므로 프롬프트에 포함할 필요가 없습니다.

## 저장 기능

### 프롬프트 저장
- Agent 타입별로 프롬프트 저장
- 저장 위치: `backend/storage/prompts/`
- 파일명 형식: `{timestamp}_{agent_type}_{name}.json`

### 데이터셋 저장
- Agent 타입, 대학명(해당 시), 쿼리 저장
- 반복 테스트에 활용
- 저장 위치: `backend/storage/datasets/`
- 파일명 형식: `{timestamp}_{agent_type}_{name}.json`

## 실제 연동 확인

### UniversityAgent
- Supabase 연결 확인: 서버 실행 시 로그 확인
- 문서 검색 테스트: `서울대 2025 입결` 등으로 검색

### ConsultingAgent
- 점수 변환 확인: `나 11232야` 입력 시 정규화된 성적 표시
- 환산 점수 확인: 경희대/서울대 등 환산 점수 자동 계산 확인

### TeacherAgent
- Gemini API 연결 확인: 학습 계획 조언 생성 확인

## API 엔드포인트

- `POST /api/sub-agent` - Sub Agent 실행
- `GET /api/default-prompt/{agent_type}` - 기본 프롬프트 조회
- `GET /api/agent-types` - 지원되는 Agent 타입 목록
- `POST /api/prompts` - 프롬프트 저장
- `GET /api/prompts` - 저장된 프롬프트 목록
- `GET /api/prompts/{id}` - 프롬프트 불러오기
- `DELETE /api/prompts/{id}` - 프롬프트 삭제
- `POST /api/datasets` - 데이터셋 저장
- `GET /api/datasets` - 저장된 데이터셋 목록
- `GET /api/datasets/{id}` - 데이터셋 불러오기
- `DELETE /api/datasets/{id}` - 데이터셋 삭제

## 포트 정보

- Orchestration Agent Test: 8091
- Final Agent Test: 8090
- **Sub Agent Test: 8092**

## 주의사항

1. **Supabase 연결**: UniversityAgent 테스트 시 Supabase 환경 변수 필수
2. **점수 데이터**: ConsultingAgent는 2026 수능 기준 데이터 사용
3. **Mock DB**: 현재는 `mock_database.py`의 임시 데이터 사용 (추후 실제 DB 연동 가능)
