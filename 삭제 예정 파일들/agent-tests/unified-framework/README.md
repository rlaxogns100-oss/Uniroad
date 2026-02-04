# Agent Testing Framework

대학 입시 상담 Multi-Agent 시스템의 통합 테스트 프레임워크입니다.

## 주요 기능

- ✅ **개별 에이전트 테스트**: Orchestration, Sub Agents, Final Agent 각각 테스트
- ✅ **파이프라인 테스트**: 전체 에이전트 연결 테스트
- ✅ **N회 반복 실행**: 안정성 및 성능 검증 (기본 10회)
- ✅ **구간별 모델 선택**: 각 에이전트마다 다른 LLM 모델 사용 가능
- ✅ **Temperature 제어**: 각 에이전트의 창의력 지수 개별 설정
- ✅ **프롬프트 커스터마이징**: 실시간 프롬프트 수정 및 버전 관리
- ✅ **데이터셋 관리**: 테스트 시나리오 저장/불러오기
- ✅ **Excel 보고서**: 상세한 테스트 결과 엑셀 다운로드
- ✅ **실시간 로그**: 테스트 진행 상황 실시간 모니터링

## 로컬 실행

### 1. Backend 실행

```bash
cd backend
pip3 install -r requirements.txt

# .env 파일 생성
echo "GEMINI_API_KEY=your_key_here" > .env

# 서버 시작
python3 -m uvicorn main:app --host 0.0.0.0 --port 8095 --reload
```

### 2. Frontend 실행

브라우저에서 `index.html` 열기:
```bash
open index.html
```

또는 간단한 HTTP 서버:
```bash
python3 -m http.server 8080
# 브라우저에서 http://localhost:8080 접속
```

## 프로덕션 배포

### 빠른 배포 (AWS)

1. **서버 초기 설정**: [SETUP_SERVER.md](./SETUP_SERVER.md) 참고
2. **배포 스크립트 실행**:
   ```bash
   # deploy.sh에서 SERVER 변수를 실제 IP로 수정
   nano deploy.sh
   
   # 배포
   ./deploy.sh
   ```

3. **접속**: https://uni2road.com/agent-test

### 상세 가이드

- 📖 [서버 초기 설정 가이드](./SETUP_SERVER.md)
- 📖 [배포 가이드](./DEPLOYMENT.md)

## 프로젝트 구조

```
unified-framework/
├── index.html              # Frontend UI
├── backend/
│   ├── main.py            # FastAPI 서버
│   ├── test_core/         # 테스트 실행 로직
│   ├── test_utils/        # Excel 출력 등
│   └── storage/           # 데이터셋/프롬프트 저장소
├── deploy.sh              # 배포 스크립트
├── nginx.conf             # Nginx 설정 예제
├── DEPLOYMENT.md          # 배포 가이드
└── SETUP_SERVER.md        # 서버 초기 설정 가이드
```

## 사용법

### 1. 에이전트 선택

상단 탭에서 테스트할 에이전트 선택:
- **Orchestration**: 사용자 질문 분석 및 실행 계획 수립
- **Sub Agents**: RAG 기반 대학 정보 검색
- **Final**: 최종 답변 생성
- **Pipeline**: 전체 흐름 통합 테스트

### 2. 테스트 데이터 입력

- **직접 입력**: 텍스트 영역에 JSON 형태로 입력
- **예시 로드**: "예시" 버튼으로 샘플 데이터 로드
- **불러오기**: 저장된 데이터셋 불러오기

### 3. 모델 및 설정

- **모델 선택**: 각 에이전트별 LLM 모델 선택 (gemini-2.5-flash-lite, gemini-3-flash-preview 등)
- **Temperature**: 창의력 지수 조절 (0.0 ~ 2.0)
- **반복 횟수**: 테스트 실행 횟수 설정
- **병렬 실행**: 순차 또는 병렬 실행 모드 선택

### 4. 프롬프트 커스터마이징

- 프롬프트 박스 클릭 → 에디터 열림
- 수정 후 "적용" 버튼
- "저장하기"로 버전 관리 가능

### 5. 실행 및 결과

- **실행** 버튼 클릭
- 실시간 로그로 진행 상황 확인
- 결과 테이블에서 각 실행 결과 확인
- **Excel 다운로드**로 상세 보고서 저장

## API 엔드포인트

### 테스트 API

- `POST /test/orchestration` - Orchestration Agent 테스트
- `POST /test/sub` - Sub Agents 테스트
- `POST /test/final` - Final Agent 테스트
- `POST /test/pipeline` - 전체 파이프라인 테스트

### 관리 API

- `GET /datasets` - 데이터셋 목록
- `POST /datasets` - 데이터셋 저장
- `DELETE /datasets/{id}` - 데이터셋 삭제
- `GET /prompts` - 프롬프트 목록
- `POST /prompts` - 프롬프트 저장
- `DELETE /prompts/{id}` - 프롬프트 삭제

### 기타

- `GET /health` - 서버 상태 확인
- `POST /export/excel` - Excel 파일 생성 및 다운로드

## 개발

### 로컬 개발 환경

```bash
# Backend 개발 모드 (자동 재시작)
cd backend
python3 -m uvicorn main:app --reload --port 8095

# Frontend는 브라우저에서 index.html 열기
```

### 코드 수정 후 배포

```bash
# Git commit/push 후
./deploy.sh
```

## 트러블슈팅

### CORS 에러

- Backend CORS는 모든 origin 허용 (`allow_origins=["*"]`)
- 브라우저 콘솔에서 실제 요청 URL 확인

### API 호출 실패

1. Backend 서버가 실행 중인지 확인:
   ```bash
   curl http://localhost:8095/health
   ```

2. 포트 확인:
   ```bash
   netstat -an | grep 8095
   ```

### Excel 다운로드 안 됨

- 브라우저 팝업 차단 해제
- 콘솔 에러 메시지 확인

## 라이선스

Internal Use Only

## 문의

기술 지원: [이슈 트래커](https://github.com/your-org/uniroad/issues)
