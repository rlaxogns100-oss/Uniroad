# 생기부 평가 모듈 (school_record_eval)

백엔드와 연동되며, **별도 폴더**로 분리되어 기존 코드와 충돌 없이 동작합니다.

## 구조

```
school_record_eval/
├── __init__.py   # router 노출
├── router.py     # FastAPI 라우터 (prefix: /api/school-record)
├── service.py    # 평가 비즈니스 로직
├── models.py     # 요청/응답 Pydantic 모델
└── README.md     # 이 파일
```

## API

- `GET /api/school-record/health` — 모듈 헬스 체크
- `POST /api/school-record/evaluate` — 생기부 평가
  - Body: `{ "content": "평가할 생기부 텍스트", "options": {} }`

## 연동 위치

`backend/main.py` 에서 한 줄만 추가되어 있습니다.

```python
from school_record_eval import router as school_record_router
app.include_router(school_record_router, prefix="/api/school-record", tags=["생기부평가"])
```

## 실제 평가 로직 넣기

- `service.py` 의 `evaluate_school_record()` 에서 평가 기준·AI 호출·DB 조회 등을 구현하면 됩니다.
- `models.py` 에 필요한 요청/응답 필드를 추가할 수 있습니다.
