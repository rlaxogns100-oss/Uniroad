# 🌐 UniZ 통합 테스트 환경

## ✅ 완성!

3개의 테스트 환경을 **상단 탭으로 전환 가능한 하나의 페이지**로 통합했습니다!

## 🚀 실행 방법

### 1. 각 서버 실행

#### Orchestration Test 서버
```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ/agent-tests/orchestration-test/backend
python3 main.py
```
**포트**: 8080

#### Sub Agent Test 서버
```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ/agent-tests/sub-agent-test/backend
python3 main.py
```
**포트**: 8092

#### Final Agent Test 서버
```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ/agent-tests/final-agent-test/backend
python3 main.py
```
**포트**: 8093

### 2. 통합 페이지 열기

웹 브라우저에서:
```
file:///Users/rlaxogns100/Desktop/Projects/UniZ/agent-tests/unified-test/index.html
```

또는 Finder에서 `index.html` 파일을 더블클릭하세요!

## 📱 화면 구성

### 상단 탭 (클릭해서 전환)
- 🎯 **Orchestration Agent** - 질문 분석 & 실행 계획
- 📊 **Sub Agent** - 개별 Agent 테스트 + 프롬프트 관리
- 🚀 **Final Agent** - 전체 파이프라인 + 프롬프트 최적화

### 우측 상단
- **서버 상태 표시**: 몇 개의 서버가 실행 중인지 표시

## ⌨️ 키보드 단축키

- **Cmd/Ctrl + 1**: Orchestration Agent로 전환
- **Cmd/Ctrl + 2**: Sub Agent로 전환
- **Cmd/Ctrl + 3**: Final Agent로 전환

## ✨ 특징

### ✅ 기존 기능 100% 유지
- 프롬프트 저장/불러오기
- 데이터셋 관리
- 커스텀 프롬프트
- 모든 UI/UX 동일

### ✅ 추가 기능
- 상단 탭으로 빠른 전환
- 마지막 탭 자동 복원
- 키보드 단축키
- 서버 상태 모니터링

## 🎨 디자인

기존 테스트 환경의 디자인을 **1픽셀도 변경하지 않았습니다**!
- 기존 HTML을 iframe으로 로드
- 상단 탭만 추가
- 각 테스트는 완전히 독립적으로 작동

## 📂 파일 구조

```
agent-tests/
├── unified-test/
│   ├── index.html      # 통합 페이지 (상단 탭)
│   └── README.md       # 이 파일
├── orchestration-test/
│   └── frontend/index.html  # 기존 파일 (수정 없음)
├── sub-agent-test/
│   └── index.html           # 기존 파일 (수정 없음)
└── final-agent-test/
    └── index.html           # 기존 파일 (수정 없음)
```

## 🔧 작동 방식

1. `unified-test/index.html`이 상단 탭 UI 제공
2. 각 테스트는 iframe으로 로드
3. 탭 클릭 시 해당 iframe만 표시
4. 기존 HTML은 전혀 수정하지 않음

## 📞 문제 해결

### 페이지가 비어있음
- 각 테스트 서버가 실행 중인지 확인
- 브라우저 콘솔에서 에러 확인

### CORS 에러
- 로컬 파일로 열었을 때 발생할 수 있음
- 간단한 HTTP 서버로 실행:
  ```bash
  cd /Users/rlaxogns100/Desktop/Projects/UniZ/agent-tests/unified-test
  python3 -m http.server 8000
  ```
  그리고 `http://localhost:8000`로 접속

## 🎉 완성!

이제 **하나의 페이지**에서 탭 전환만으로 모든 테스트를 사용할 수 있습니다!

기존 테스트의 모든 기능 (프롬프트 저장/불러오기, 데이터셋 관리 등)을 그대로 사용하세요! 🚀
