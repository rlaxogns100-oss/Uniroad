# Final Agent Test

Final Agent 전용 테스트 환경입니다. 프로덕션과 100% 동일한 프롬프트를 사용하며, 다른 에이전트 호출 없이 프롬프트 최적화에 집중할 수 있습니다.

## 기능

- **직접 입력**: user_question_with_context, structure_text, results_text, all_citations를 직접 입력
- **프로덕션 동일 프롬프트**: 본 프로젝트의 prompt4와 100% 동일한 프롬프트 사용
- **실제 말풍선 UI**: 본 프로젝트와 동일한 채팅 말풍선 디자인으로 결과 확인
- **Raw 출력 확인**: Gemini가 생성한 원본 텍스트 확인 가능
- **프롬프트 확인**: 실제로 전달된 프롬프트 전문 확인 가능

## 실행 방법

### 1. 백엔드 서버 시작

```bash
cd agent-tests/final-agent-test/backend
pip install -r ../requirements.txt
python main.py
```

서버가 http://localhost:8090 에서 실행됩니다.

### 2. 프론트엔드 열기

브라우저에서 `index.html` 파일을 직접 열거나:

```bash
cd agent-tests/final-agent-test
open index.html  # macOS
# 또는
python -m http.server 8091  # 로컬 서버로 실행
```

## 입력 필드 설명

1. **user_question_with_context**: 사용자 질문 + 맥락 (이전 대화 포함)
2. **structure_text**: Orchestration Agent가 생성한 Answer Structure
3. **results_text**: Sub Agent들의 실행 결과 (Raw Data)
4. **all_citations**: 출처 정보 JSON 배열

## API 엔드포인트

- `GET /` - 서버 상태 확인
- `POST /api/final-agent` - Final Agent 실행
- `GET /api/default-prompt` - 기본 프롬프트 템플릿 조회

## 테스트 시나리오

1. "📝 예시 데이터 불러오기" 버튼 클릭
2. 데이터 확인 및 필요시 수정
3. "🚀 Final Agent 실행" 버튼 클릭
4. 결과 확인 (후처리 결과, Raw 출력, 사용된 프롬프트)

## 주의사항

- `.env` 파일에 `GEMINI_API_KEY`가 설정되어 있어야 합니다
- 본 프로젝트의 `.env` 파일을 그대로 사용합니다 (상위 디렉토리 참조)
