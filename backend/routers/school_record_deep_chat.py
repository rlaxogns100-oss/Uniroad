"""
생활기록부 심층 상세 분석 채팅 라우터 (독립 모듈)
- 연동된 생기부 데이터를 컨텍스트로 사용
- academic_contents RAG 검색 결과를 추가 컨텍스트로 활용
- gemini-3.1-flash-lite-preview 기반 스트리밍 채팅
- 기존 채팅 파이프라인과 독립적으로 동작
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from fixtures.hardcoded_school_records import HARDCODED_SCHOOL_RECORDS
from middleware.auth import optional_auth_with_state
from school_record_eval.matching_summary import ensure_matching_summary
from school_record_eval.report_context import build_school_record_report_context_text
from services.supabase_client import supabase_service

router = APIRouter()

DEEP_CHAT_MODEL = os.getenv(
    "SCHOOL_RECORD_DEEP_CHAT_MODEL", "gemini-3.1-flash-lite-preview"
)

SYSTEM_PROMPT = """\
당신은 대한민국 고등학생의 학교생활기록부(생기부)를 심층적으로 분석하는 전문 AI 상담사입니다.
사용자가 연동한 생기부 데이터를 기반으로 다음과 같은 분석을 수행합니다:

1. **학업 역량 분석**: 교과학습 발달상황(세특)을 학년별·과목별로 분석하여 학업 깊이, 탐구 활동, 성장 흐름을 파악합니다.
2. **전공적합성 분석**: 지원 희망 전공(학과)과 생기부 내용의 일관성·연결성을 평가합니다.
3. **창의적 체험활동 분석**: 자율활동, 동아리활동, 진로활동의 구체성과 의미를 분석합니다.
4. **행동특성 및 종합의견 분석**: 담임 소견의 핵심 키워드와 학생 역량을 도출합니다.
5. **강점·약점 진단**: 입시 관점에서 어필 포인트와 보완이 필요한 부분을 구체적으로 제시합니다.
6. **맞춤형 전략 제안**: 학생의 상황에 맞는 학종(학생부종합전형) 전략을 제안합니다.

분석 시 항상:
- 구체적인 근거를 생기부 내용에서 인용하세요.
- 업로드된 참고자료가 제공된 경우, 해당 자료의 기준과 프레임워크를 적극 활용하세요.
- 학년별 변화와 성장 흐름을 파악하세요.
- 입시에 실질적으로 도움이 되는 실용적 조언을 하세요.
- 긍정적·건설적 톤을 유지하되, 솔직한 평가를 해주세요.
- 한국어로 답변하세요.
"""


class DeepChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


DEFAULT_REPORT_TITLE = "학교생활기록부 심층 분석"
FIXED_REPORT_INTERNAL_BRIEF = (
    "연동된 학교생활기록부를 바탕으로 학생부종합전형 기준의 정식 종합 분석 리포트를 작성한다. "
    "학생의 현재 강점과 리스크, 전공 및 대학 적합도, 우선 보완 과제가 바로 드러나야 한다."
)
FIXED_REPORT_SECTION_TITLES = [
    "생기부 항목별 근거 분석",
    "학생부종합전형 관점 종합 해석",
    "추천 대학 및 전형 전략",
    "다음 학기 실행 전략",
]
FIXED_REPORT_ANALYSIS_DIMENSIONS = [
    "학업역량",
    "전공 및 진로 연결성",
    "탐구 깊이",
    "활동 유기성",
    "공동체역량",
    "성장 가능성",
]
FIXED_REPORT_SCHOOL_RECORD_FOCUS = [
    "교과 세부능력 및 특기사항",
    "창의적 체험활동",
    "행동특성 및 종합의견",
    "학년별 성장 흐름",
    "전공 및 진로 일관성",
    "면접에서 설명 가능한 탐구 경험",
]
FIXED_REPORT_DIRECT_ANSWER_ITEM_COUNT = 5
REPORT_SEMESTER_ORDER = ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"]
REPORT_SEMESTER_LABELS = {
    "1-1": "1학년 1학기",
    "1-2": "1학년 2학기",
    "2-1": "2학년 1학기",
    "2-2": "2학년 2학기",
    "3-1": "3학년 1학기",
    "3-2": "3학년 2학기",
}
AXIS_DISPLAY_COLORS = {
    "학업역량": "#2563eb",
    "탐구 깊이": "#059669",
    "전공 연결성": "#f59e0b",
    "공동체역량": "#8b5cf6",
    "자기주도성": "#ec4899",
    "성장성": "#ef4444",
}
AXIS_STRENGTH_TITLES = {
    "학업역량": "교과 기반과 수업 이해도가 비교적 안정적으로 읽힙니다.",
    "탐구 깊이": "탐구를 단순 참여가 아니라 심화 과정으로 보여줄 여지가 있습니다.",
    "전공 연결성": "관심 계열과 실제 활동 사이의 연결성이 비교적 선명합니다.",
    "공동체역량": "협업과 책임감이 드러나는 장면이 공동체 평가와 연결됩니다.",
    "자기주도성": "학생이 직접 주제를 끌고 가는 장면이 강점 축으로 읽힙니다.",
    "성장성": "학년이 올라갈수록 서사가 정교해질 수 있는 성장 흐름이 보입니다.",
}
AXIS_WEAKNESS_TITLES = {
    "학업역량": "교과 성취와 세특의 학업 밀도를 더 선명하게 보여줄 필요가 있습니다.",
    "탐구 깊이": "탐구를 더 깊게 밀어붙인 후속 과정이 부족하게 읽힐 수 있습니다.",
    "전공 연결성": "활동과 희망 전공 사이의 연결 논리를 더 명확히 정리해야 합니다.",
    "공동체역량": "협업과 배려가 남는 사례를 더 분명하게 남길 필요가 있습니다.",
    "자기주도성": "학생이 스스로 문제를 정의한 장면이 더 구체적으로 보강돼야 합니다.",
    "성장성": "학년별 변화와 확장 흐름을 더 분명하게 연결해야 합니다.",
}
AXIS_PLAN_LIBRARY = {
    "학업역량": {
        "title": "교과 세특의 학업 밀도를 높이는 학기 운영이 필요합니다.",
        "why": "학종에서는 단순 등급보다 수업 이해, 개념 적용, 심화 질문의 흔적이 함께 읽혀야 설득력이 생깁니다.",
        "actions": [
            "다음 학기에는 핵심 과목 2개를 정해 개념 이해-심화 질문-확장 탐구가 한 흐름으로 남도록 설계하세요.",
            "수업 중 질문, 발표, 실험 해석처럼 교사가 바로 기록할 수 있는 장면을 의도적으로 만들어 두세요.",
            "세특 초안 관점에서는 결과보다 사고과정이 보이도록 탐구 노트를 정리하세요.",
        ],
        "expected_effect": "교과 기반이 선명해지면 상위권 대학에서도 학생부 해석의 신뢰도가 올라갑니다.",
    },
    "탐구 깊이": {
        "title": "한 주제를 2단계 이상 확장하는 심화 탐구가 필요합니다.",
        "why": "좋은 생기부는 관심 주제를 나열하지 않고, 왜 그 주제를 파고들었는지와 후속 확장이 함께 보여야 합니다.",
        "actions": [
            "다음 학기에는 이미 다룬 주제 하나를 골라 원인 분석-자료 조사-대안 제시까지 이어지는 후속 탐구를 설계하세요.",
            "탐구 결과만 적지 말고 참고 자료, 가설, 한계, 추가 질문을 함께 남기세요.",
            "교과 세특과 창체 활동에서 같은 주제를 다른 관점으로 반복 노출시키세요.",
        ],
        "expected_effect": "탐구 깊이가 보강되면 활동 수보다 질이 먼저 읽히는 학생부로 바뀝니다.",
    },
    "전공 연결성": {
        "title": "관심 전공과 활동의 연결 고리를 한 줄로 설명할 수 있어야 합니다.",
        "why": "학종에서는 전공명이 아니라, 학생이 왜 이 방향으로 관심을 좁혀 왔는지가 중요합니다.",
        "actions": [
            "다음 학기 시작 전에 관심 전공을 한 문장으로 정의하고, 교과와 창체에서 연결될 소재를 미리 정하세요.",
            "독서, 세특, 진로활동이 같은 문제의식을 공유하도록 주제 키워드를 통일하세요.",
            "면접에서 바로 설명 가능한 대표 활동 2개를 선정해 연결 서사를 정리하세요.",
        ],
        "expected_effect": "전공 적합도 해석이 쉬워지고, 대학별 인재상과 맞물리는 지점이 뚜렷해집니다.",
    },
    "공동체역량": {
        "title": "협업과 책임이 남는 장면을 더 명확하게 기록해야 합니다.",
        "why": "공동체역량은 봉사 시간보다도 팀 안에서 맡은 역할과 태도가 기록으로 남는지가 중요합니다.",
        "actions": [
            "다음 학기에는 팀 프로젝트나 동아리에서 맡을 역할을 먼저 정하고 결과보다 과정 기여도를 남기세요.",
            "배려, 조율, 발표 지원처럼 타인에게 영향을 준 행동을 교사가 볼 수 있는 장면으로 만드세요.",
            "행특에 반영될 수 있도록 일상적인 책임감과 협업 태도를 꾸준히 유지하세요.",
        ],
        "expected_effect": "공동체 평가에서 모범적이기만 한 학생이 아니라 기여도가 보이는 학생으로 읽힙니다.",
    },
    "자기주도성": {
        "title": "학생이 스스로 기획하고 끌고 간 흔적을 강화해야 합니다.",
        "why": "주도성은 활동 참여 여부가 아니라, 주제를 고르고 확장한 주체가 학생인지에서 갈립니다.",
        "actions": [
            "다음 학기에는 교사가 준 틀 안에서도 스스로 문제를 정의한 탐구 1개를 반드시 남기세요.",
            "활동 전후로 어떤 질문이 생겼고 어떻게 자료를 찾았는지 메모해 두세요.",
            "중간 점검 때 교사에게 피드백을 요청해 기록 포인트를 함께 조율하세요.",
        ],
        "expected_effect": "학생부 문장 안에서 수동적 참여자가 아니라 능동적 기획자로 읽히게 됩니다.",
    },
    "성장성": {
        "title": "학년별 변화와 후속 확장의 흐름을 더 분명히 연결해야 합니다.",
        "why": "성장성은 현재 수준보다도 이전 경험을 어떻게 다음 단계로 이어 왔는지를 통해 읽힙니다.",
        "actions": [
            "1학년-2학년-3학년 활동을 하나의 흐름으로 묶는 연결 메모를 먼저 작성해 두세요.",
            "이미 했던 활동을 다음 학기 세특이나 진로활동의 후속 탐구로 다시 호출하세요.",
            "학기 말에는 무엇이 바뀌었는지 스스로 정리해 다음 기록의 출발점으로 삼으세요.",
        ],
        "expected_effect": "활동이 흩어져 보이지 않고, 누적 성장 서사로 해석될 가능성이 높아집니다.",
    },
}


class DeepChatReportRequest(BaseModel):
    message: Optional[str] = None
    history: List[Dict[str, str]] = []


QUERY_ROLE_HINTS = {
    "정의": ("무엇", "뜻", "의미", "개념", "정의"),
    "배경": ("배경", "맥락", "왜", "이유"),
    "절차": ("절차", "순서", "방법", "어떻게", "단계"),
    "기준": ("기준", "판단", "평가", "근거", "요소"),
    "사례": ("사례", "예시", "예", "샘플"),
    "주의사항": ("주의", "실수", "조심", "유의"),
    "표": ("표", "도표", "정리표"),
    "체크리스트": ("체크리스트", "점검", "체크"),
}

QUERY_STOPWORDS = {
    "그리고", "또는", "에서", "대한", "관련", "내용", "설명", "분석", "정리",
    "해주세요", "해줘", "알려줘", "무엇", "어떻게", "왜", "대한민국", "학교생활기록부",
}

UNIVERSITY_RAG_HINT_KEYWORDS = (
    "학생부종합전형", "학종", "서류평가", "평가기준", "평가 기준",
    "인재상", "학업역량", "전공적합성", "발전가능성", "공동체역량",
    "진로역량", "정성평가", "면접", "적합성",
)
RECOMMENDATION_QUERY_HINTS = (
    "추천", "추천해줘", "추천해 줘", "대학 추천", "학교 추천",
    "어디", "어느 대학", "적합한 대학", "잘 맞는 대학", "지원 대학",
    "대학군", "지원 가능 대학",
)
UNIVERSITY_VARIANT_EXCLUDES = {
    "의대", "치대", "약대", "공대", "상대", "법대", "교대", "사대", "문과대", "이과대",
}
DOCUMENT_SCHOOL_NAME_CACHE: Optional[list[str]] = None
UNIVERSITY_DOCUMENT_EMBEDDER = None
UNIVERSITY_DOCUMENT_CATALOG_CACHE: Optional[list[Dict[str, Any]]] = None
UNIVERSITY_PROFILE_CACHE: Dict[str, Dict[str, Any]] = {}
NESIN_DETAIL_CACHE: Optional[list[Dict[str, Any]]] = None
NESIN_DETAIL_PATH = Path(__file__).resolve().parents[2] / "FINAL_nesin_detail_complete_31970.json"
SCHOOL_RECORD_FOCUS_KEYWORDS = (
    "의학", "의예", "생명과학", "생명공학", "뇌과학", "신경과학", "법의학",
    "화학", "물리학", "수학", "통계", "데이터", "빅데이터", "인공지능",
    "컴퓨터", "소프트웨어", "프로그래밍", "반도체", "전자", "전기전자",
    "기계", "산업공학", "경영", "경제", "심리", "교육", "사회", "정치",
    "철학", "법학", "간호", "약학", "바이오", "유전", "면역", "환경",
)

PLANNER_MODEL = os.getenv("SCHOOL_RECORD_DEEP_CHAT_PLANNER_MODEL", DEEP_CHAT_MODEL)
REPORT_WRITER_MODEL = os.getenv("SCHOOL_RECORD_DEEP_CHAT_REPORT_WRITER_MODEL", DEEP_CHAT_MODEL)
REPORT_REVIEWER_MODEL = os.getenv("SCHOOL_RECORD_DEEP_CHAT_REPORT_REVIEWER_MODEL", DEEP_CHAT_MODEL)
PLANNER_MAX_SOURCE_COUNT = 5
PLANNER_MAX_SNAPSHOT_CHARS = 7000
PLANNER_MAX_OUTPUT_TOKENS = 2048
REPORT_MAX_OUTPUT_TOKENS = 8192
REPORT_MAX_SOURCE_COUNT = 6
REPORT_MAX_SOURCE_SNIPPET_CHARS = 1200
REPORT_SECTION_MAX_OUTPUT_TOKENS = 2048
REPORT_SECTION_MAX_WORKERS = 6
REFERENCE_QUERY_MAX_WORKERS = 4
REPORT_POST_PROCESS_MAX_WORKERS = 4
REPORT_REVIEW_MAX_OUTPUT_TOKENS = 4096
SCHOOL_RECORD_EVIDENCE_MAX_CHARS = 22000
MIN_CRITERIA_EXCERPT_LINES = 3
NARRATIVE_MERGE_MAX_OUTPUT_TOKENS = 2048
ACCEPTED_CASE_MAX_CANDIDATES = 3
ACCEPTED_CASE_MAX_OUTPUT_TOKENS = 3072
ACCEPTED_CASE_MIN_EXCERPT_PAIRS = 3
ACCEPTED_CASE_MAX_EXCERPT_PAIRS = 6
FLOWCHART_MAX_OUTPUT_TOKENS = 1536

QUERY_PLAN_SYSTEM_PROMPT = """\
당신은 학교생활기록부 심층 분석을 위한 질문 구조화 플래너입니다.
역할:
1. 사용자의 질문을 '무엇을 판단해야 하는지' 기준으로 구조화합니다.
2. 학교생활기록부에서 우선 확인해야 할 근거 영역을 고릅니다.
3. 외부 참고자료 검색용 보강 쿼리를 만듭니다.

중요 규칙:
- 절대 최종 답변을 작성하지 마세요.
- 반드시 JSON만 출력하세요.
- 과장 없이 실제 질문 의도를 그대로 유지하세요.
- 생기부 분석은 학교생활기록부 근거가 우선이고, 외부 참고자료는 기준/전략 보강용이어야 합니다.

반환 JSON 스키마:
{
  "question_type": "질문 유형",
  "user_goal": "사용자가 알고 싶은 핵심",
  "refined_question": "최종 답변 생성을 위해 정제한 질문 1문장",
  "analysis_dimensions": ["평가축1", "평가축2"],
  "school_record_focus": ["우선 볼 생기부 근거1", "우선 볼 생기부 근거2"],
  "answer_sections": ["답변 섹션1", "답변 섹션2"],
  "retrieval_queries": ["외부 참고자료 재검색용 쿼리1", "쿼리2"],
  "reasoning_hint": "답변 작성 시 유의할 점"
}
"""

STRUCTURED_REPORT_SYSTEM_PROMPT = """\
당신은 대한민국 고등학생의 학교생활기록부를 분석하는 근거 중심 리포트 작성기입니다.

역할:
1. 사용자의 질문에 맞춰 답변을 섹션 단위 보고서로 작성합니다.
2. 각 섹션의 첫 부분은 반드시 '평가기준(evaluation_criteria)'이어야 합니다.
3. 평가기준은 반드시 제공된 참고자료 source_id를 근거로 사용해야 합니다.
4. 그 다음 '학생 적용 판단(student_assessment)'을 작성하고, 마지막에 '구체적인 답변(answer)'을 제시합니다.
5. answer는 생기부와 참고자료를 함께 반영하되, 학생 개인에 대한 판단은 생기부 중심으로 작성합니다.

매우 중요한 규칙:
- 반드시 JSON만 출력하세요.
- sections는 3~6개 사이로 작성하세요.
- 각 section에는 title, evaluation_criteria, student_assessment, answer, evidence 배열이 필요합니다.
- evaluation_criteria는 기준 문장 배열이며 각 항목은 text와 source_refs를 가져야 합니다.
- student_assessment는 학생에게 그 기준을 적용한 판단 배열이며 각 항목은 text와 school_record_ref_indexes를 가져야 합니다.
- evidence 배열의 각 항목은 반드시 제공된 source_id만 사용하세요.
- evidence.used_excerpt는 제공된 참고자료 원문에서 실제로 근거가 되는 부분을 최소 3줄 정도 이어서 발췌하세요.
- evidence.why_used는 그 발췌가 왜 평가기준에 쓰였는지 1~2문장으로 설명하되, 그 핵심 의미는 반드시 evaluation_criteria 또는 answer 본문에 자연스러운 설명문으로 녹여 쓰세요.
- "사용하기 위해", "제시하기 위해 사용함" 같은 메타 표현만 따로 남기지 말고, 실제 입시 원칙이나 판단 기준을 독자가 바로 이해할 수 있는 서술형 문장으로 본문에 풀어 쓰세요.
- answer에는 evaluation_criteria와 student_assessment에 없는 새로운 근거를 임의로 추가하지 마세요.
- 최종 섹션 answer는 추상적 표현만 쓰지 말고, 학생 상황에 맞는 구체적인 해석과 조언을 포함하세요.
- 생기부에 없는 사실은 지어내지 마세요.

반환 JSON 스키마:
{
  "report_title": "리포트 제목",
  "summary": "전체 평가 요약 2~4문장",
  "sections": [
    {
      "section_id": "section-1",
      "title": "섹션 제목",
      "evaluation_criteria": [
        {
          "text": "출처 기반 평가기준",
          "source_refs": ["SRC1", "SRC2"]
        }
      ],
      "student_assessment": [
        {
          "text": "이 기준을 학생 생기부에 적용한 판단",
          "school_record_ref_indexes": [1, 2]
        }
      ],
      "answer": "구체적인 평가/조언",
      "evidence": [
        {
          "source_id": "SRC1",
          "used_excerpt": "실제로 근거가 된 발췌",
          "why_used": "이 발췌를 이 섹션에 사용한 이유"
        }
      ]
    }
  ]
}
"""

SECTION_EVIDENCE_SYSTEM_PROMPT = """\
당신은 학교생활기록부 분석 리포트 작성을 위한 섹션별 근거 정리기입니다.

역할:
1. 각 섹션 제목에 맞춰 학교생활기록부에서 핵심 근거를 추출합니다.
2. 어떤 참고자료(source_id)가 그 섹션에 가장 적합한지도 함께 고릅니다.
3. 답변을 쓰지 말고, 근거만 구조화하세요.

규칙:
- 반드시 JSON만 출력하세요.
- 각 섹션마다 school_record_evidence를 3~6개 추출하세요.
- 각 근거는 quote(발췌)와 interpretation(이 근거가 의미하는 바)를 포함하세요.
- interpretation은 단순 요약이 아니라 학생 개인의 강점/한계/성장 흐름/전공 적합성에 대한 해석이어야 합니다.
- 총 글자 수, 세특 개수, 활동 개수, 기록 비중처럼 대부분 학생에게 공통적인 구조적 수치는 단독 근거로 사용하지 마세요.
- "기록이 많다", "항목 수가 많다" 같은 당연한 설명보다, 반복되는 주제, 심화 정도, 과목 간 연결성, 주도성처럼 질적 특징이 드러나는 근거를 우선 고르세요.
- quote는 가능한 한 문장 단위가 아니라 실제 생기부 문맥이 살아 있는 2~5문장 분량의 원문 발췌로 고르세요.
- preferred_source_ids는 제공된 source_id 중에서만 선택하세요.
- 생기부에 없는 내용은 절대 만들지 마세요.

반환 스키마:
{
  "sections": [
    {
      "section_id": "section-1",
      "title": "섹션 제목",
      "school_record_evidence": [
        {
          "label": "세특/창체/행특 등",
          "quote": "실제 발췌",
          "interpretation": "이 발췌가 시사하는 점"
        }
      ],
      "preferred_source_ids": ["SRC1", "SRC2"]
    }
  ]
}
"""

SECTION_WRITER_SYSTEM_PROMPT = """\
당신은 학교생활기록부 평가 리포트의 한 섹션만 깊이 있게 작성하는 전문 작성자입니다.

역할:
1. 섹션 하나에 대해서만 evaluation_criteria, student_assessment, answer를 깊이 있게 작성합니다.
2. evaluation_criteria는 2~4개 작성하고, 각 항목은 text와 source_refs를 가져야 하며 제공된 source_id만 사용하세요.
3. student_assessment는 2~4개 작성하고, 각 항목은 text와 school_record_ref_indexes를 가져야 합니다.
4. answer는 evaluation_criteria와 student_assessment를 종합하여 학생 맞춤형으로 구체적으로 작성하세요.

규칙:
- 반드시 JSON만 출력하세요.
- answer는 짧은 요약이 아니라 충분히 풍부한 문단으로 작성하세요.
- evaluation_criteria는 참고자료 기준/원칙을 설명해야 하며, student_assessment는 생기부 근거를 바탕으로 학생에게 적용한 판단이어야 합니다.
- evaluation_criteria는 "세특은 중요하다" 같은 일반론을 반복하지 말고, 이 섹션에서 실제로 판단해야 하는 기준을 구체적으로 적으세요.
- student_assessment는 근거를 다시 말하는 요약이 아니라, 그 근거가 학생에게 어떤 강점/한계/리스크/시사점을 가지는지 평가 문장으로 쓰세요.
- 총 글자 수, 세특 항목 수, 활동 개수, 기록 비중처럼 구조적으로 당연한 수치는 단독 판단 근거로 쓰지 마세요.
- "기록이 많다", "항목이 많다", "비중이 크다" 같은 표현만으로 판단하지 말고, 반드시 질적 해석(심화, 연결성, 일관성, 주도성, 전공 적합성)을 포함하세요.
- 다른 섹션에도 그대로 들어갈 수 있는 일반론을 반복하지 말고, 이 섹션 제목에만 어울리는 관점과 해석에 집중하세요.
- 이미 다른 섹션에서 말했을 법한 표현을 반복하기보다, 이 섹션이 답변 전체에서 맡는 역할이 무엇인지 분명하게 드러내세요.
- answer는 바로 학생 칭찬이나 결론으로 시작하지 말고, 먼저 이 섹션에서 쓰인 평가기준이 왜 중요한지와 입시적으로 어떤 의미가 있는지 짚은 뒤 학생 사례로 넘어가세요.
- 특히 참고자료 청크에서 드러난 판단 원리(예: 성장 서사의 중요성, 주제의 독창성, 실증 분석의 의미)를 answer의 앞부분 설명에 반영하세요.
- answer와 student_assessment에는 아래에 제공된 생기부 원문 표현을 최대한 직접 다시 호출하세요. 과목명, 활동명, 탐구 주제, 확장 흐름이 드러나게 써야 합니다.
- "이 학생은 전반적으로", "전체적으로 우수하다" 같은 포괄적 문장만 반복하지 말고, 실제 생기부 문구에서 읽히는 구체 장면을 중심으로 해석하세요.
- evidence 배열의 used_excerpt는 평가기준에 실제로 쓴 부분을 참고자료 원문에서 최소 3줄 정도 이어서 발췌하세요.
- evidence.why_used는 그 기준이 왜 이 섹션 평가기준으로 쓰였는지 설명하되, 그 의미를 evaluation_criteria.text 또는 answer에 자연스러운 설명문으로 반드시 반영하세요.
- "사용하기 위해", "근거로 삼기 위해" 같은 메타 설명만 출력하지 말고, 실제 평가 원칙을 독자가 바로 읽어 이해할 수 있는 문장으로 바꿔 쓰세요.

반환 스키마:
{
  "section_id": "section-1",
  "title": "섹션 제목",
  "evaluation_criteria": [
    {
      "text": "평가기준",
      "source_refs": ["SRC1"]
    }
  ],
  "student_assessment": [
    {
      "text": "학생 적용 판단",
      "school_record_ref_indexes": [1]
    }
  ],
  "answer": "구체적인 설명",
  "evidence": [
    {
      "source_id": "SRC1",
      "used_excerpt": "실제 근거 발췌",
      "why_used": "이 근거를 사용한 이유"
    }
  ]
}
"""

REPORT_REVIEW_SYSTEM_PROMPT = """\
당신은 학교생활기록부 평가 리포트를 더 풍부하고 전문적으로 다듬는 리뷰어입니다.

역할:
1. 이미 작성된 섹션형 리포트를 더 자세하고 전문적으로 확장합니다.
2. 근거 연결은 유지하고, evaluation_criteria와 student_assessment, answer를 더 명확하고 깊게 만듭니다.
3. summary도 더 설득력 있게 보강합니다.

규칙:
- 반드시 JSON만 출력하세요.
- 기존 section_id, title, evidence/source_id 연결을 유지하세요.
- 새로운 source_id를 임의로 만들지 마세요.
- evaluation_criteria와 student_assessment는 섹션당 각각 2~4개 사이를 유지하세요.
- answer는 생기부와 참고자료를 바탕으로 더 풍부하게 보강하되, 근거 없는 내용을 추가하지 마세요.
- evidence.why_used에 담긴 설명은 별도 메타 문장으로 남기기보다, evaluation_criteria와 answer 본문 속 설명으로 자연스럽게 흡수하세요.
- student_assessment가 총 글자 수, 세특 개수, 활동 개수, 비중 같은 당연한 구조 지표를 반복하면 안 됩니다.
- student_assessment는 반드시 학생의 질적 특징과 입시적 의미가 드러나는 평가 문장으로 다듬으세요.
- 섹션끼리 같은 결론과 같은 설명을 반복하지 말고, 각 섹션이 서로 다른 질문에 답하는 것처럼 역할을 분리하세요.
- 겹치는 내용이 있더라도 같은 문장을 다시 쓰지 말고, 해당 섹션에서 새롭게 드러나는 의미와 차이점만 남기세요.

반환 스키마:
{
  "report_title": "리포트 제목",
  "summary": "전체 요약",
  "sections": [
    {
      "section_id": "section-1",
      "title": "섹션 제목",
      "evaluation_criteria": [
        {
          "text": "평가기준",
          "source_refs": ["SRC1"]
        }
      ],
      "student_assessment": [
        {
          "text": "학생 적용 판단",
          "school_record_ref_indexes": [1]
        }
      ],
      "answer": "보강된 답변",
      "evidence": [
        {
          "source_id": "SRC1",
          "used_excerpt": "실제 근거 발췌",
          "why_used": "이 근거를 사용한 이유"
        }
      ]
    }
  ]
}
"""

ACCEPTED_CASE_COMPARISON_SYSTEM_PROMPT = """\
당신은 학생 생기부와 합격자 생기부를 비교해 마지막 섹션을 작성하는 입시 비교 분석가입니다.

목표:
1. 현재 사용자 질문의 맥락에 맞는 비교 관점을 한 줄로 정리합니다.
2. 제공된 후보 합격자 중 참고 가치가 높은 사례를 최대 3개 선택합니다.
3. 각 사례마다 사용자 생기부 원문 발췌와 합격자 생기부 원문 발췌를 직접 비교합니다.
4. 무엇이 좋은지, 어떤 차이가 있는지, 무엇을 보완해야 하는지를 구체적으로 설명합니다.
5. 각 excerpt_pair의 pair_comment(해설)는 2~4문장으로 자세히 씁니다. 단순 요약이 아니라, 두 원문의 구체적 차이, 합격자 쪽이 강한 이유, 사용자가 보완할 수 있는 점을 구체적으로 서술합니다.

규칙:
- 반드시 제공된 발췌 원문만 사용하세요. 없는 사실을 만들지 마세요.
- 합격자 원문과 사용자 원문은 가능한 한 전체 문단 단위로 그대로 유지하세요. 중간 축약은 꼭 필요한 경우가 아니면 하지 마세요.
- 설명은 반드시 현재 질문의 맥락을 반영해야 합니다. 예: 면접 질문이면 면접 관점, 보완점 질문이면 보완 관점.
- 합격자의 전공 분야가 사용자와 다르더라도, 전공명 자체의 일치 여부를 핵심 판단 기준으로 삼지 마세요.
- 해설(pair_comment)은 전공 내용의 동일성보다 생기부의 구조, 탐구 흐름, 교과-활동-심화의 연결 방식, 후속 확장 방식에 초점을 맞춰 작성하세요.
- 사용자가 합격자 사례에서 배워야 할 것은 전공 그 자체가 아니라, 하나의 주제를 어떻게 심화하고 연결하며 서사화했는지입니다.
- pair_comment에는 가능하면 다음 세 가지가 모두 포함되어야 합니다:
  1. 사용자 기록이 현재 어떤 수준의 구조/흐름을 보이는지
  2. 합격자 기록이 어떤 방식으로 교과 개념을 심화·확장·연결하는지
  3. 사용자가 자신의 질문 및 진로 맥락 안에서 그 구조를 어떻게 가져와야 하는지
- 비교 모드(subject_excerpt_compare, grade_flow_compare, activity_story_compare, interview_evidence_compare, gap_compare, general_compare)를 따라야 합니다.
- comparison_cards는 2~3개가 가장 좋습니다.
- excerpt_pairs는 카드당 최소 3개, 많으면 6개까지 활용할 수 있습니다.
- 질문이 특정 학년/영역(예: 1학년 세특, 창체, 행특, 학년별 흐름)을 가리키면 해당 범위를 최대한 우선해서 비교하세요.
- good_points / gaps / action_tips는 각 1~3개 사이로 간결하게 작성하세요.
- 마지막 섹션이므로 section_narrative는 이 섹션을 읽는 방법을 짧게 안내하는 문장으로 작성하세요.
- 반드시 JSON만 출력하세요.

반환 형식:
{
  "section_id": "accepted-case-comparison",
  "title": "유사 합격자 비교",
  "comparison_focus": "현재 질문에 맞는 비교 관점 한 줄",
  "section_narrative": "이 비교를 어떻게 읽어야 하는지 설명",
  "comparison_cards": [
    {
      "case_id": "case_x",
      "label": "합격자 이름",
      "match_reason": "왜 이 사례를 골랐는지",
      "comparison_axis": "예: 1학년 세특 비교",
      "excerpt_pairs": [
        {
          "pair_id": "pair-1",
          "user_excerpt_label": "사용자 발췌 라벨",
          "user_excerpt": "사용자 원문 발췌",
          "accepted_excerpt_label": "합격자 발췌 라벨",
          "accepted_excerpt": "합격자 원문 발췌",
          "pair_comment": "2~4문장 해설: 전공명이 같지 않더라도 합격자 생기부의 구조·흐름·심화 방식에서 무엇을 배워야 하는지 설명하세요. 두 원문의 구체적 차이, 합격자 쪽의 학문적 유기성/확장 방식, 사용자가 자신의 질문 및 진로 맥락 안에서 어떻게 적용해야 하는지를 자세히 서술"
        }
      ],
      "good_points": ["..."],
      "gaps": ["..."],
      "action_tips": ["..."]
    }
  ]
}
"""

DIRECT_ANSWER_SYSTEM_PROMPT = """\
당신은 학교생활기록부 심층 분석 챗봇의 '질문에 대한 바로 답변' 블록만 작성하는 응답기입니다.

목표:
1. 사용자의 질문에 가장 직접적으로 답합니다.
2. 분석이나 설명에 앞서, 사용자가 원한 산출물을 먼저 제시합니다.
3. 아래에 제공된 최종 섹션들의 맥락과 결론을 반영해, 같은 흐름의 압축판처럼 답합니다.
4. 생기부와 참고자료에 근거하되, 없는 사실은 만들지 않습니다.

규칙:
- 반드시 JSON만 출력하세요.
- 사용자가 개수를 명시했다면 items 개수를 가능한 한 정확히 맞추세요.
- 사용자가 "면접 질문 10개", "보완점 3개", "대학 5개 추천"처럼 명확한 산출물을 원하면 설명보다 결과를 먼저 제시하세요.
- items는 최종 섹션의 논지와 어긋나면 안 됩니다. 아래 섹션에서 다루지 않은 낯선 방향의 항목을 임의로 만들지 마세요.
- 아래 섹션이 항목을 강/약점, 우선순위, 준비 포인트 등으로 나눠 설명했다면 direct answer도 그 맥락을 반영하세요.
- items는 짧고 직접적이어야 합니다.
- intro는 1~3문장으로 간결하게 작성하세요.
- closing은 선택 사항이며 비어 있어도 됩니다.
- analysis/sections/comparison에 대한 메타 설명은 하지 마세요.

반환 형식:
{
  "title": "질문에 대한 바로 답변",
  "answer_mode": "numbered_list",
  "intro": "사용자 질문에 대한 짧은 직접 답변",
  "items": ["항목1", "항목2"],
  "closing": "필요하면 짧은 마무리"
}
"""

FIXED_REPORT_DIRECT_ANSWER_SYSTEM_PROMPT = """\
당신은 학생부종합전형 학교생활기록부 분석 리포트의 첫 장에 들어갈 '한눈에 보는 진단' 블록만 작성하는 편집자입니다.

목표:
1. 질문에 답하는 형식이 아니라, 정식 리포트의 맨 앞 요약처럼 작성합니다.
2. 학생의 현재 상태를 강점, 리스크, 적합도, 우선 과제로 빠르게 파악할 수 있게 만듭니다.
3. 아래 최종 섹션들의 맥락과 결론을 압축해 4~6개의 핵심 진단 문장으로 정리합니다.
4. 생기부와 참고자료에 근거하되, 없는 사실은 만들지 않습니다.

규칙:
- 반드시 JSON만 출력하세요.
- intro는 1~2문장으로 학생부 전체 인상을 요약하세요.
- items는 각기 다른 역할을 가져야 합니다. 같은 말을 반복하지 마세요.
- items는 짧은 슬로건이 아니라, 입시적으로 어떤 의미가 있는지 드러나는 완성형 문장으로 작성하세요.
- items는 강점, 리스크, 전공/대학 적합도, 우선 보완 과제가 균형 있게 보이도록 구성하세요.
- closing은 선택 사항이며 비어 있어도 됩니다.

반환 형식:
{
  "title": "핵심 요약",
  "answer_mode": "numbered_list",
  "intro": "학생부 전체 인상을 요약한 짧은 문장",
  "items": ["항목1", "항목2"],
  "closing": "필요하면 짧은 마무리"
}
"""

FINAL_REPORT_SUMMARY_SYSTEM_PROMPT = """\
당신은 학교생활기록부 심층 분석 리포트의 최종 총평만 작성하는 편집자입니다.

목표:
1. 아래에 제공된 최종 리포트 전 섹션을 모두 읽고 마지막에 붙는 총평을 작성합니다.
2. 요약이 아니라 결론처럼 읽혀야 하며, 학생의 강점, 리스크, 전공/대학 적합도, 가장 중요한 보완 과제를 함께 압축합니다.
3. 학생 생기부에 실제로 드러난 특징을 바탕으로 써야 하며, 일반론을 반복하지 않습니다.

규칙:
- 반드시 JSON만 출력하세요.
- summary는 2~4문장으로 작성하세요.
- 모호한 칭찬보다 실제 생기부에서 읽히는 주제, 연결성, 심화 정도, 성장 흐름을 드러내세요.
- 아래 섹션에 없는 새로운 사실을 만들지 마세요.

반환 형식:
{
  "summary": "최종 총평 2~4문장"
}
"""

STUDENT_PROFILE_SYSTEM_PROMPT = """\
당신은 학교생활기록부를 학생부종합전형 기준으로 구조화하는 평가 프로파일러입니다.

목표:
1. 학생 생기부를 6개 축으로 구조화합니다.
2. 각 축은 1~5점의 상대 점수와 한 줄 해석을 함께 제공합니다.
3. 강점과 리스크, 가장 시급한 우선과제를 분리해 요약합니다.

규칙:
- 반드시 JSON만 출력하세요.
- 축은 학업역량, 탐구 깊이, 전공 연결성, 공동체역량, 자기주도성, 성장성만 사용하세요.
- 점수는 절대평가가 아니라 현재 학생부 안에서 읽히는 상대 강도입니다.
- 근거 없는 과장은 금지합니다.
- evidence_quotes는 생기부 문구를 짧게 발췌한 것만 넣으세요.

반환 형식:
{
  "headline": "학생부 전체를 한 줄로 요약",
  "dominant_track": "현재 가장 강하게 읽히는 계열/전공 흐름",
  "immediate_priority": "지금 가장 먼저 보완할 한 가지",
  "strengths": ["강점1", "강점2", "강점3"],
  "risks": ["리스크1", "리스크2", "리스크3"],
  "axis_scores": [
    {
      "axis": "학업역량",
      "score": 4,
      "summary": "한 줄 해석",
      "evidence_quotes": ["근거1", "근거2"]
    }
  ]
}
"""

UNIVERSITY_RECOMMENDATION_SYSTEM_PROMPT = """\
당신은 학생 생기부와 대학 문서를 함께 읽고 학생부종합전형 추천 대학 카드를 만드는 입시 전략가입니다.

목표:
1. 제공된 대학 문서 중 학생과 잘 맞는 대학만 2~4개 고릅니다.
2. 각 대학마다 왜 맞는지, 무엇이 부족한지, 어떤 전형/평가축이 핵심인지 짧고 명확하게 정리합니다.
3. 대학 문서의 표현을 근거로 추천 이유를 설명합니다.

규칙:
- 반드시 JSON만 출력하세요.
- 제공된 대학 문서에 없는 학교는 추천하지 마세요.
- fit_level은 "매우 적합", "적합", "조건부 적합" 중 하나만 사용하세요.
- matching_points와 caution_points는 각각 1~3개로 제한하세요.
- evidence_excerpt는 실제 문서 문구를 짧게 인용 또는 요약한 것으로 쓰세요.

반환 형식:
{
  "summary": "추천 대학군을 한 줄로 요약",
  "cards": [
    {
      "school_name": "대학교명",
      "admission_label": "전형 또는 대학군 설명",
      "fit_level": "적합",
      "fit_summary": "왜 맞는지 한 줄 요약",
      "matching_points": ["포인트1", "포인트2"],
      "caution_points": ["주의1", "주의2"],
      "interview_note": "면접 여부 또는 면접 관점",
      "talent_keywords": ["학업역량", "진로역량"],
      "evidence_excerpt": "대학 문서 근거",
      "evidence_source": "출처 학교명"
    }
  ]
}
"""

UNIVERSITY_PROFILE_SYSTEM_PROMPT = """\
당신은 대학 문서에서 학생부종합전형 평가 프로필만 추출하는 분석가입니다.

목표:
1. 대학별 학생부종합전형 평가요소와 인재상을 짧고 구조적으로 정리합니다.
2. 면접 여부, 강조 역량, 읽히는 인재상 키워드를 추출합니다.
3. 학생 추천 이전에 대학 자체가 무엇을 보는지 설명할 수 있어야 합니다.

규칙:
- 반드시 JSON만 출력하세요.
- 제공된 문서 범위 안에서만 판단하세요.
- evaluation_keywords는 2~5개, evaluation_summary는 1~3문장으로 제한하세요.
- interview_policy는 문서에 없으면 빈 문자열로 두세요.

반환 형식:
{
  "school_name": "대학명",
  "evaluation_keywords": ["학업역량", "진로역량"],
  "talent_summary": "이 대학이 선호하는 학생상 요약",
  "evaluation_summary": "서류평가 핵심 요약",
  "interview_policy": "면접 여부/관점",
  "evidence_excerpt": "근거 문구 요약",
  "source_title": "근거 출처"
}
"""

THREE_PAGE_FLOWCHART_SYSTEM_PROMPT = """\
당신은 학교생활기록부의 학년별 연결성을 3단계 흐름도로 요약하는 분석가입니다.

목표:
1. 1학년, 2학년, 3학년의 핵심 흐름을 각각 한 개 노드로 요약합니다.
2. 각 노드는 그 학년의 대표 문제의식, 활동 성격, 다음 학년으로 이어지는 연결 포인트가 드러나야 합니다.
3. 링크 문구는 왜 다음 학년으로 이어지는지가 보이게 작성합니다.

규칙:
- 반드시 JSON만 출력하세요.
- 노드는 최대 3개만 작성하세요.
- summary는 1~2문장, evidence_quotes는 1~2개로 제한하세요.
- 실제로 존재하는 학년만 다루세요.
- 미화하지 말고 실제로 읽히는 연결성만 정리하세요.

반환 형식:
{
  "headline": "학생부 흐름 전체를 한 줄로 요약",
  "nodes": [
    {
      "node_id": "grade-1",
      "grade": "1학년",
      "title": "학년 노드 제목",
      "summary": "이 학년의 핵심 흐름",
      "evidence_quotes": ["근거 1", "근거 2"]
    }
  ],
  "links": [
    {
      "from_node_id": "grade-1",
      "to_node_id": "grade-2",
      "label": "연결 문구"
    }
  ]
}
"""


def _cosine_similarity(a: list, b: list) -> float:
    """두 벡터의 코사인 유사도 계산."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a * norm_b > 0 else 0.0


def _tokenize_query(text: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in QUERY_STOPWORDS]


def _normalize_compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").strip().lower())


def _school_name_search_variants(university: str) -> list[str]:
    """검색 시 사용할 학교명 변형 목록."""
    if not university or not university.strip():
        return []
    u = university.strip()
    variants = [u]
    if u.endswith("대학교"):
        short = u[:-2]
        if short and short not in variants:
            variants.append(short)
    elif u.endswith("대학"):
        short = u[:-2] + "대"
        if short and short not in variants:
            variants.append(short)
    elif u.endswith("대"):
        university_name = u + "대학교"
        if university_name not in variants:
            variants.append(university_name)
    return variants


def _get_document_school_names() -> list[str]:
    global DOCUMENT_SCHOOL_NAME_CACHE
    if DOCUMENT_SCHOOL_NAME_CACHE is not None:
        return DOCUMENT_SCHOOL_NAME_CACHE

    try:
        client = supabase_service.get_admin_client()
        response = client.table("documents").select("school_name").execute()
        school_names = []
        seen = set()
        for row in response.data or []:
            name = str(row.get("school_name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            school_names.append(name)
        DOCUMENT_SCHOOL_NAME_CACHE = school_names
        return school_names
    except Exception as e:
        print(f"⚠️ [deep_chat] 대학 문서 school_name 조회 실패: {e}")
        DOCUMENT_SCHOOL_NAME_CACHE = []
        return []


def _extract_target_universities(query: str) -> list[str]:
    normalized_query = _normalize_compact_text(query)
    if not normalized_query:
        return []

    matched: list[tuple[int, str]] = []
    seen = set()

    for school_name in _get_document_school_names():
        variants = [school_name, *_school_name_search_variants(school_name)]
        normalized_variants = [
            _normalize_compact_text(variant)
            for variant in variants
            if variant and variant not in UNIVERSITY_VARIANT_EXCLUDES
        ]
        longest = 0
        for variant in normalized_variants:
            if not variant or variant in UNIVERSITY_VARIANT_EXCLUDES:
                continue
            if variant in normalized_query:
                longest = max(longest, len(variant))
        if longest and school_name not in seen:
            seen.add(school_name)
            matched.append((longest, school_name))

    matched.sort(key=lambda item: (-item[0], item[1]))
    return [school_name for _, school_name in matched[:3]]


def _build_university_rag_query(query: str, universities: list[str]) -> str:
    school_terms = " ".join(universities[:2])
    hint_terms = " ".join(UNIVERSITY_RAG_HINT_KEYWORDS)
    return f"{query.strip()} {school_terms} {hint_terms}".strip()


def _get_university_document_embedder():
    global UNIVERSITY_DOCUMENT_EMBEDDER
    if UNIVERSITY_DOCUMENT_EMBEDDER is not None:
        return UNIVERSITY_DOCUMENT_EMBEDDER

    from config import embedding_settings as embedding_config
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    embedding_model = (
        getattr(embedding_config, "DEFAULT_EMBEDDING_MODEL", "")
        or "models/gemini-embedding-001"
    )
    UNIVERSITY_DOCUMENT_EMBEDDER = GoogleGenerativeAIEmbeddings(
        model=embedding_model,
        request_timeout=600,
        batch_size=100,
        max_retries=10,
        retry_delay=15,
    )
    return UNIVERSITY_DOCUMENT_EMBEDDER


def _embed_university_document_query(text: str) -> list[float]:
    embedder = _get_university_document_embedder()
    return list(embedder.embed_query(text))


def _is_vector_dimension_mismatch_error(error: Exception) -> bool:
    return "different vector dimensions" in str(error or "").lower()


def _build_university_query_embeddings(text: str) -> list[list[float]]:
    embeddings: list[list[float]] = []

    primary_embedding = _embed_university_document_query(text)
    if primary_embedding:
        embeddings.append(primary_embedding)

    try:
        from routers.academic_contents import _embed_query

        fallback_embedding = _embed_query(text)
        if fallback_embedding and len(fallback_embedding) != len(primary_embedding):
            embeddings.append(fallback_embedding)
    except Exception:
        pass

    return embeddings


def _get_university_document_catalog() -> list[Dict[str, Any]]:
    global UNIVERSITY_DOCUMENT_CATALOG_CACHE
    if UNIVERSITY_DOCUMENT_CATALOG_CACHE is not None:
        return UNIVERSITY_DOCUMENT_CATALOG_CACHE

    client = supabase_service.get_admin_client()
    result = (
        client.table("documents")
        .select("id, school_name, filename, summary, embedding_summary")
        .execute()
    )

    catalog: list[Dict[str, Any]] = []
    for row in result.data or []:
        school_name = str(row.get("school_name") or "").strip()
        if not school_name:
            continue

        embedding = row.get("embedding_summary")
        if isinstance(embedding, str):
            try:
                embedding = json.loads(embedding)
            except Exception:
                embedding = None
        if not isinstance(embedding, list):
            embedding = None

        filename = str(row.get("filename") or "").strip()
        summary = str(row.get("summary") or "").strip()
        catalog.append({
            "id": row.get("id"),
            "school_name": school_name,
            "filename": filename,
            "summary": summary,
            "embedding_summary": embedding,
            "text_blob": " ".join(part for part in [school_name, filename, summary] if part).lower(),
        })

    UNIVERSITY_DOCUMENT_CATALOG_CACHE = catalog
    return catalog


def _document_text_overlap_score(query_tokens: list[str], text_blob: str) -> float:
    if not query_tokens or not text_blob:
        return 0.0
    overlap = sum(1 for token in query_tokens if token in text_blob)
    return min(1.0, overlap / max(len(query_tokens), 4))


def _rank_recommendation_schools(
    query_embeddings: list[list[float]],
    rag_query: str,
    limit: int,
) -> list[str]:
    catalog = _get_university_document_catalog()
    if not catalog:
        return []

    query_tokens = _tokenize_query(rag_query)
    school_scores: dict[str, float] = {}

    for doc in catalog:
        score = 0.0
        text_overlap = _document_text_overlap_score(query_tokens, doc.get("text_blob", ""))
        score += text_overlap * 0.35

        doc_embedding = doc.get("embedding_summary")
        if doc_embedding:
            summary_similarity = max(
                (
                    _cosine_similarity(query_emb, doc_embedding)
                    for query_emb in query_embeddings
                    if len(query_emb) == len(doc_embedding)
                ),
                default=0.0,
            )
            score += summary_similarity * 0.65

        school_name = doc["school_name"]
        previous = school_scores.get(school_name, float("-inf"))
        if score > previous:
            school_scores[school_name] = score

    ranked = sorted(
        school_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [school_name for school_name, _ in ranked[:limit]]


def _collect_university_chunk_rows(
    query_embeddings: list[list[float]],
    universities: list[str],
    candidate_count: int,
    use_variants: bool = True,
) -> tuple[list[Dict[str, Any]], Optional[Exception]]:
    client = supabase_service.get_admin_client()
    last_error: Optional[Exception] = None

    for query_emb in query_embeddings:
        collected_rows: Dict[Any, Dict[str, Any]] = {}
        try:
            for university in universities:
                school_names = (
                    _school_name_search_variants(university) or [university]
                    if use_variants
                    else [university]
                )
                for school_name in school_names:
                    result = client.rpc(
                        "match_document_chunks",
                        {
                            "query_embedding": query_emb,
                            "match_threshold": 0.0,
                            "match_count": candidate_count,
                            "filter_school_name": school_name,
                            "filter_section_id": None,
                        },
                    ).execute()
                    for row in result.data or []:
                        row_id = row.get("id")
                        if row_id is None:
                            continue
                        previous = collected_rows.get(row_id)
                        if previous is None or float(row.get("similarity", 0.0) or 0.0) > float(previous.get("similarity", 0.0) or 0.0):
                            collected_rows[row_id] = row
        except Exception as e:
            last_error = e
            if _is_vector_dimension_mismatch_error(e):
                continue
            return [], e

        normalized_rows = _normalize_university_document_rows(list(collected_rows.values()))
        if normalized_rows:
            return normalized_rows, None

    return [], last_error


def _is_university_recommendation_query(query: str) -> bool:
    text = str(query or "").strip()
    if not text:
        return False
    return any(hint in text for hint in RECOMMENDATION_QUERY_HINTS)


def _extract_school_record_focus_terms(school_record_context: str, limit: int = 6) -> list[str]:
    text = str(school_record_context or "")
    if not text:
        return []

    candidates: list[str] = []
    for match in re.finditer(r"희망분야\s*:\s*([^\)\n]+)", text):
        raw = str(match.group(1) or "").strip()
        parts = [part.strip() for part in re.split(r"[,/·]", raw) if part.strip()]
        for part in parts:
            if part not in candidates:
                candidates.append(part)
                if len(candidates) >= limit:
                    return candidates

    scored: list[tuple[int, str]] = []
    lowered = text.lower()
    for keyword in SCHOOL_RECORD_FOCUS_KEYWORDS:
        count = lowered.count(keyword.lower())
        if count <= 0:
            continue
        scored.append((count, keyword))
    scored.sort(key=lambda item: (-item[0], item[1]))

    for _, keyword in scored:
        if keyword not in candidates:
            candidates.append(keyword)
        if len(candidates) >= limit:
            break
    return candidates


def _is_fixed_report_mode(answer_plan: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(answer_plan, dict):
        return False
    return str(answer_plan.get("report_mode") or "").strip() == "fixed_report"


def _get_report_title(answer_plan: Optional[Dict[str, Any]]) -> str:
    if isinstance(answer_plan, dict):
        title = str(answer_plan.get("report_title") or "").strip()
        if title:
            return title
    return DEFAULT_REPORT_TITLE


def _get_direct_answer_title(answer_plan: Optional[Dict[str, Any]]) -> str:
    if isinstance(answer_plan, dict):
        title = str(answer_plan.get("direct_answer_title") or "").strip()
        if title:
            return title
    if _is_fixed_report_mode(answer_plan):
        return "핵심 요약"
    return "핵심 요약"


def _get_generation_task_label(answer_plan: Optional[Dict[str, Any]]) -> str:
    return "리포트 브리프" if _is_fixed_report_mode(answer_plan) else "사용자 질문"


def _get_generation_task_text(user_message: str, answer_plan: Optional[Dict[str, Any]]) -> str:
    if _is_fixed_report_mode(answer_plan):
        return str((answer_plan or {}).get("report_brief") or FIXED_REPORT_INTERNAL_BRIEF).strip()
    return str(user_message or "").strip()


def _build_fixed_report_retrieval_queries(school_record_context: str) -> list[str]:
    focus_terms = _extract_school_record_focus_terms(school_record_context, limit=4)
    focus_query = " ".join(focus_terms).strip()

    queries = [
        "학생부종합전형 서류평가 학업역량 진로역량 공동체역량 평가 기준",
        "학생부종합전형 세특 창체 행특 성장 흐름 보완 전략",
        "학생부종합전형 적합 대학 추천 인재상 서류평가",
    ]
    if focus_query:
        queries.insert(
            1,
            " ".join(
                [
                    focus_query,
                    "학생부종합전형",
                    "전공 적합성",
                    "탐구 심화",
                    "세특 평가 기준",
                ]
            ).strip(),
        )
        queries.append(
            " ".join(
                [
                    focus_query,
                    "적합 대학 추천",
                    "학생부종합전형",
                    "인재상",
                    "면접",
                    "서류평가",
                ]
            ).strip()
        )

    normalized_queries: list[str] = []
    seen = set()
    for query in queries:
        text = str(query or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized_queries.append(text)
        if len(normalized_queries) >= 4:
            break
    return normalized_queries


def _collect_reference_sources_for_queries(
    *,
    queries: list[str],
    school_record_context: str,
    match_count: int = 4,
) -> list[Dict[str, Any]]:
    normalized_queries: list[str] = []
    seen_queries = set()
    for query in queries:
        normalized_query = str(query or "").strip()
        if not normalized_query or normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)
        normalized_queries.append(normalized_query)

    if not normalized_queries:
        return []

    ordered_selected_rows: list[Dict[str, Any]] = []
    seen_ids = set()

    selected_rows_by_index: Dict[int, list[Dict[str, Any]]] = {}
    max_workers = min(REFERENCE_QUERY_MAX_WORKERS, len(normalized_queries))
    if max_workers <= 1:
        for idx, query in enumerate(normalized_queries):
            _, selected_rows = _retrieve_reference_rag_rows(
                query,
                school_record_context=school_record_context,
                match_count=match_count,
            )
            selected_rows_by_index[idx] = selected_rows
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    _retrieve_reference_rag_rows,
                    query,
                    school_record_context=school_record_context,
                    match_count=match_count,
                ): idx
                for idx, query in enumerate(normalized_queries)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    _, selected_rows = future.result()
                except Exception as error:
                    print(f"⚠️ [deep_chat] 참고자료 병렬 검색 실패(query-{idx + 1}): {error}")
                    selected_rows = []
                selected_rows_by_index[idx] = selected_rows

    for idx in range(len(normalized_queries)):
        for row in selected_rows_by_index.get(idx, []):
            row_id = row.get("id")
            if row_id in seen_ids:
                continue
            seen_ids.add(row_id)
            ordered_selected_rows.append(row)

    return _build_sources_meta(ordered_selected_rows[: max(REPORT_MAX_SOURCE_COUNT + 2, 8)])


def _build_fixed_report_plan(school_record_context: str) -> Dict[str, Any]:
    focus_terms = _extract_school_record_focus_terms(school_record_context, limit=6)
    retrieval_queries = _build_fixed_report_retrieval_queries(school_record_context)
    return {
        "report_mode": "fixed_report",
        "question_type": "학생부종합전형 종합 리포트",
        "user_goal": "연동된 생기부를 학생부종합전형 기준으로 종합 진단하고 전공 및 대학 적합도를 정리한다.",
        "report_title": DEFAULT_REPORT_TITLE,
        "report_brief": FIXED_REPORT_INTERNAL_BRIEF,
        "direct_answer_title": "핵심 요약",
        "refined_question": FIXED_REPORT_INTERNAL_BRIEF,
        "analysis_dimensions": list(FIXED_REPORT_ANALYSIS_DIMENSIONS),
        "school_record_focus": focus_terms or list(FIXED_REPORT_SCHOOL_RECORD_FOCUS),
        "answer_sections": list(FIXED_REPORT_SECTION_TITLES),
        "retrieval_queries": retrieval_queries,
        "reasoning_hint": (
            "채팅 답변처럼 질문에 응답하지 말고, 진단서처럼 읽히는 리포트를 작성한다. "
            "강점, 리스크, 적합도, 실행 전략이 각각 다른 역할을 맡도록 구분한다."
        ),
    }


def _prepare_fixed_report_generation_context(
    *,
    school_record_context: str,
) -> Dict[str, Any]:
    answer_plan = _build_fixed_report_plan(school_record_context)
    sources_meta = _collect_reference_sources_for_queries(
        queries=answer_plan.get("retrieval_queries", []),
        school_record_context=school_record_context,
    )
    return {
        "answer_plan": answer_plan,
        "sources_meta": sources_meta,
    }


def _build_recommendation_rag_query(query: str, school_record_context: str) -> str:
    focus_terms = " ".join(_extract_school_record_focus_terms(school_record_context))
    hint_terms = " ".join(
        (
            "학생부종합전형",
            "인재상",
            "서류평가",
            "학업역량",
            "전공적합성",
            "발전가능성",
            "공동체역량",
            "잘 맞는 학생",
        )
    )
    return " ".join(part for part in [query.strip(), focus_terms, hint_terms] if part).strip()


def _infer_university_chunk_role(raw_content: str) -> str:
    text = str(raw_content or "")
    if any(keyword in text for keyword in ("인재상", "평가기준", "평가 기준", "서류평가")):
        return "기준"
    if any(keyword in text for keyword in ("학업역량", "전공적합성", "발전가능성", "공동체역량", "진로역량")):
        return "기준"
    if any(keyword in text for keyword in ("면접", "질문", "유의사항")):
        return "주의사항"
    if any(keyword in text for keyword in ("예시", "사례")):
        return "사례"
    return ""


def _extract_university_chunk_keywords(raw_content: str) -> list[str]:
    text = str(raw_content or "")
    keywords = [
        keyword
        for keyword in UNIVERSITY_RAG_HINT_KEYWORDS
        if keyword in text
    ]
    deduped = []
    seen = set()
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        deduped.append(keyword)
        if len(deduped) >= 6:
            break
    return deduped


def _infer_query_roles(query: str) -> set[str]:
    lowered = query.lower()
    matched = set()
    for role, hints in QUERY_ROLE_HINTS.items():
        if any(hint in lowered for hint in hints):
            matched.add(role)
    return matched


def _keyword_overlap_score(query_tokens: list[str], row: Dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    keywords = [str(k).lower() for k in (row.get("chunk_keywords") or []) if str(k).strip()]
    if not keywords:
        return 0.0
    overlap = sum(1 for token in query_tokens if any(token in kw or kw in token for kw in keywords))
    return min(1.0, overlap / max(len(query_tokens), 3))


def _heading_match_score(query_tokens: list[str], row: Dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    heading_text = " ".join(
        [
            str(row.get("source_title", "")),
            str(row.get("chapter", "")),
            str(row.get("part", "")),
            str(row.get("sub_section", "")),
            str(row.get("chunk_title", "")),
            " ".join(row.get("heading_path") or []),
        ]
    ).lower()
    if not heading_text.strip():
        return 0.0
    overlap = sum(1 for token in query_tokens if token in heading_text)
    return min(1.0, overlap / max(len(query_tokens), 3))


def _summary_match_score(query_tokens: list[str], row: Dict[str, Any]) -> float:
    if not query_tokens:
        return 0.0
    summary_text = " ".join(
        [
            str(row.get("chunk_summary", "")),
            str(row.get("document_summary", "")),
        ]
    ).lower()
    if not summary_text.strip():
        return 0.0
    overlap = sum(1 for token in query_tokens if token in summary_text)
    return min(1.0, overlap / max(len(query_tokens), 3))


def _role_match_score(query_roles: set[str], row: Dict[str, Any]) -> float:
    if not query_roles:
        return 0.0
    chunk_role = str(row.get("chunk_role", "")).strip()
    return 1.0 if chunk_role and chunk_role in query_roles else 0.0


def _row_group_key(row: Dict[str, Any]) -> str:
    document_id = row.get("document_id")
    if document_id:
        return f"doc:{document_id}"
    return f"title:{row.get('source_title', '')}"


def _truncate_text(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 12)].rstrip() + "\n...(중략)"


def _non_empty_lines(text: str) -> list[str]:
    return [line.rstrip() for line in str(text or "").splitlines() if line.strip()]


def _normalize_text_for_compare(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(text or "").lower())


_META_VERB_SUFFIX = (
    r"(?:을|를)?\s*"
    r"(?:원칙|점|내용|기준|근거|사실|사항)?\s*"
    r"(?:을|를)?\s*"
    r"(?:제시|설명|강조|보여주기?|나타내기?|뒷받침|활용|인용)?\s*"
    r"(?:하기|하고자)?\s*"
    r"(?:위해|위하여)?\s*"
    r"(?:사용함|사용했습니다|사용하였습니다|사용되었습니다|활용함|활용했습니다|활용하였습니다|인용함|인용했습니다)"
    r"[.!]?$"
)


def _strip_meta_suffix(text: str) -> str:
    cleaned = re.sub(_META_VERB_SUFFIX, "", text).strip()
    cleaned = re.sub(
        r"\s*(?:을|를)?\s*(?:근거로|기준으로)\s*(?:삼기|삼고자)\s*(?:위해)?\s*"
        r"(?:사용함|사용했습니다|사용하였습니다|활용함|활용했습니다|활용하였습니다)"
        r"[.!]?$",
        "",
        cleaned,
    ).strip()
    return cleaned


def _rewrite_why_used_as_body_text(text: str) -> str:
    body_text = str(text or "").strip()
    if not body_text:
        return ""

    replacements = [
        (r"(.+?)하다는\s+(?:원칙|점|내용).*$", r"\1합니다."),
        (r"(.+?)라는\s+(?:원칙|점|내용).*$", r"\1입니다."),
        (r"(.+?)임을\s+(?:강조|설명|제시).*$", r"\1입니다."),
        (r"(.+?)다는\s+(?:것을|점을)\s+(?:강조|설명|제시).*$", r"\1합니다."),
    ]

    for pattern, replacement in replacements:
        rewritten = re.sub(pattern, replacement, body_text)
        if rewritten != body_text:
            body_text = rewritten.strip()
            break
    else:
        body_text = _strip_meta_suffix(body_text)

    if body_text and body_text[-1] not in ".!?":
        body_text += "."
    return body_text


def _merge_supporting_statements_into_text(
    text: str,
    statements: list[str],
) -> str:
    base_text = str(text or "").strip()
    merged_text = base_text
    merged_normalized = _normalize_text_for_compare(base_text)

    for statement in statements:
        statement_text = _rewrite_why_used_as_body_text(statement)
        if not statement_text:
            continue
        statement_normalized = _normalize_text_for_compare(statement_text)
        if not statement_normalized:
            continue
        if statement_normalized in merged_normalized or merged_normalized in statement_normalized:
            continue
        merged_text = f"{statement_text} {merged_text}".strip() if merged_text else statement_text
        merged_normalized = _normalize_text_for_compare(merged_text)

    return merged_text


def _split_korean_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=다\.)\s+|(?<=요\.)\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _is_generic_metric_sentence(text: str) -> bool:
    sentence = str(text or "").strip()
    if not sentence:
        return False

    metric_pattern = re.search(
        r"(\d[\d,]*\s*자|\d[\d,]*\s*건|\d[\d,]*개의|\d[\d,]*개|\d[\d,]*%\s*|분량|비중|글자 수|항목 수)",
        sentence,
    )
    context_pattern = re.search(r"(세특|기록|학업 관련 기록|창체|활동)", sentence)
    qualitative_pattern = re.search(
        r"(반복되는 주제|심화|연결성|일관성|주도성|전공 적합성|문제의식|탐구 흐름|성장 흐름|서사)",
        sentence,
    )
    generic_pattern = re.search(
        r"(강력한 학업적 자산|정량적 기반|풍부한 활동 잠재력|압도적인 비중|고르게 .*이루어졌)",
        sentence,
    )

    if metric_pattern and context_pattern and not qualitative_pattern:
        return True
    if generic_pattern:
        return True
    return False


def _remove_generic_metric_sentences(text: str) -> str:
    sentences = _split_korean_sentences(text)
    if not sentences:
        return str(text or "").strip()

    filtered = [sentence for sentence in sentences if not _is_generic_metric_sentence(sentence)]
    if filtered:
        return " ".join(filtered).strip()
    return str(text or "").strip()


def _sentence_tokens_for_compare(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[0-9A-Za-z가-힣]+", str(text or "").lower())
        if len(token) >= 2
    }


def _are_sentences_overlapping(a: str, b: str) -> bool:
    normalized_a = _normalize_text_for_compare(a)
    normalized_b = _normalize_text_for_compare(b)
    if not normalized_a or not normalized_b:
        return False
    if normalized_a == normalized_b:
        return True
    if min(len(normalized_a), len(normalized_b)) >= 18 and (
        normalized_a in normalized_b or normalized_b in normalized_a
    ):
        return True

    tokens_a = _sentence_tokens_for_compare(a)
    tokens_b = _sentence_tokens_for_compare(b)
    if not tokens_a or not tokens_b:
        return False

    common = tokens_a & tokens_b
    if len(common) < 4:
        return False

    min_overlap = len(common) / max(1, min(len(tokens_a), len(tokens_b)))
    max_overlap = len(common) / max(1, max(len(tokens_a), len(tokens_b)))
    return min_overlap >= 0.8 or (len(common) >= 6 and max_overlap >= 0.7)


def _dedupe_sentences(text: str, seen_sentences: Optional[list[str]] = None) -> str:
    original = str(text or "").strip()
    sentences = _split_korean_sentences(original)
    if not sentences:
        return original

    kept: list[str] = []
    compare_pool = list(seen_sentences or [])
    for sentence in sentences:
        if any(_are_sentences_overlapping(sentence, existing) for existing in compare_pool):
            continue
        kept.append(sentence)
        compare_pool.append(sentence)

    return " ".join(kept).strip() if kept else original


def _dedupe_overlapping_sections(sections: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    seen_narrative_sentences: list[str] = []
    for section in sections:
        narrative = str(section.get("section_narrative") or "").strip()
        answer = str(section.get("answer") or "").strip()

        if narrative:
            deduped_narrative = _dedupe_sentences(narrative, seen_narrative_sentences)
            section["section_narrative"] = deduped_narrative
            seen_narrative_sentences.extend(_split_korean_sentences(deduped_narrative))

        if answer:
            section["answer"] = _dedupe_sentences(answer)

    return sections


def _expand_excerpt_to_min_lines(
    excerpt: str,
    source_text: str,
    min_lines: int = MIN_CRITERIA_EXCERPT_LINES,
) -> str:
    excerpt = str(excerpt or "").strip()
    source_text = str(source_text or "").strip()
    if not excerpt:
        return excerpt

    excerpt_lines = _non_empty_lines(excerpt)
    if len(excerpt_lines) >= min_lines:
        return excerpt

    source_lines = _non_empty_lines(source_text)
    if len(source_lines) < min_lines:
        return excerpt

    normalized_excerpt = " ".join(excerpt_lines)
    if not normalized_excerpt:
        return excerpt

    match_index = None
    for idx, line in enumerate(source_lines):
        if normalized_excerpt in line or line in normalized_excerpt:
            match_index = idx
            break

    if match_index is None:
        for idx in range(len(source_lines)):
            window = " ".join(source_lines[idx : idx + min_lines])
            if normalized_excerpt in window:
                match_index = idx
                break

    if match_index is None:
        return "\n".join(source_lines[:min_lines])

    start = max(0, match_index - 1)
    end = min(len(source_lines), start + min_lines)
    start = max(0, end - min_lines)
    expanded_lines = source_lines[start:end]
    return "\n".join(expanded_lines) if len(expanded_lines) >= min_lines else excerpt


def _normalize_str_list(value: Any, limit: int) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []
    normalized = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _extract_json_dict(text: str) -> Optional[Dict[str, Any]]:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _rerank_rows(rows: list[Dict[str, Any]], query: str, match_count: int) -> list[Dict[str, Any]]:
    query_tokens = _tokenize_query(query)
    query_roles = _infer_query_roles(query)

    primary_rows = [row for row in rows if not row.get("is_context")]
    if not primary_rows:
        return []

    scored_rows = []
    for row in primary_rows:
        similarity = float(row.get("similarity", 0.0) or 0.0)
        keyword_score = _keyword_overlap_score(query_tokens, row)
        heading_score = _heading_match_score(query_tokens, row)
        summary_score = _summary_match_score(query_tokens, row)
        role_score = _role_match_score(query_roles, row)
        final_score = (
            similarity * 0.68
            + keyword_score * 0.12
            + heading_score * 0.10
            + summary_score * 0.06
            + role_score * 0.04
        )
        enriched = dict(row)
        enriched["rerank_score"] = round(final_score, 4)
        scored_rows.append(enriched)

    scored_rows.sort(
        key=lambda row: (
            row.get("rerank_score", 0.0),
            row.get("similarity", 0.0),
        ),
        reverse=True,
    )

    selected: list[Dict[str, Any]] = []
    per_document: dict[str, int] = {}
    for row in scored_rows:
        doc_key = _row_group_key(row)
        if per_document.get(doc_key, 0) >= 2:
            continue
        selected.append(row)
        per_document[doc_key] = per_document.get(doc_key, 0) + 1
        if len(selected) >= match_count:
            break

    return selected or scored_rows[:match_count]


def _collect_context_rows(
    all_rows: list[Dict[str, Any]],
    selected_rows: list[Dict[str, Any]],
    context_window: int,
) -> list[Dict[str, Any]]:
    if not selected_rows:
        return []

    selected_ids = {row.get("id") for row in selected_rows}
    selected_keys = {
        (_row_group_key(row), int(row.get("chunk_index", 0)))
        for row in selected_rows
    }

    final_rows = list(selected_rows)
    for row in all_rows:
        if row.get("id") in selected_ids:
            continue
        group_key = _row_group_key(row)
        idx = int(row.get("chunk_index", 0))
        if any(
            group_key == selected_group and abs(idx - selected_idx) <= context_window
            for selected_group, selected_idx in selected_keys
        ):
            enriched = dict(row)
            enriched["is_context"] = True
            final_rows.append(enriched)

    final_rows.sort(key=lambda row: (_row_group_key(row), int(row.get("chunk_index", 0))))
    return final_rows


def _build_rag_context(rows: list[Dict[str, Any]]) -> str:
    parts = []
    for row in rows:
        raw_content = str(row.get("raw_content", "")).strip()
        if not raw_content:
            continue
        path = " > ".join(row.get("heading_path") or [])
        section_path = path or " > ".join(
            [p for p in [row.get("chapter", ""), row.get("part", ""), row.get("sub_section", "")] if p]
        )
        keywords = ", ".join(row.get("chunk_keywords") or [])
        score_label = ""
        if not row.get("is_context"):
            score_label = f"\n[관련도]\n벡터 유사도 {round(float(row.get('similarity', 0.0) or 0.0) * 100)}%"
        parts.append(
            "\n".join(
                [
                    f"[출처]\n{row.get('source_title', '')}",
                    f"[문서 요약]\n{row.get('document_summary', '')}".strip(),
                    f"[경로]\n{section_path or '(루트)'}",
                    f"[청크 제목]\n{row.get('chunk_title', '')}".strip(),
                    f"[청크 설명]\n{row.get('chunk_summary', '')}".strip(),
                    f"[청크 역할]\n{row.get('chunk_role', '')}".strip(),
                    f"[핵심 키워드]\n{keywords}".strip(),
                    f"[원문]\n{raw_content}",
                ]
            ).strip()
            + score_label
        )
    return "\n\n---\n\n".join(part for part in parts if part.strip())


def _dedupe_rows_by_id(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    deduped: list[Dict[str, Any]] = []
    seen_ids = set()
    for row in rows:
        row_id = row.get("id")
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        deduped.append(row)
    return deduped


def _fallback_search(query_emb: list, candidate_count: int, context_window: int) -> list:
    """IVFFlat 인덱스가 소량 데이터에서 실패할 때 Python 측 폴백 검색."""
    try:
        client = supabase_service.get_admin_client()
        all_rows = (
            client.table("academic_contents")
            .select(
                "id, document_id, source_title, chapter, part, sub_section, chunk_index, "
                "chunk_title, chunk_summary, chunk_role, chunk_keywords, heading_path, "
                "raw_content, retrieval_text, metadata, embedding"
            )
            .execute()
        )
        data = all_rows.data or []
        if not data:
            return []

        import json as _json
        for row in data:
            emb = row.get("embedding")
            if isinstance(emb, str):
                row["_emb"] = _json.loads(emb)
            elif isinstance(emb, list):
                row["_emb"] = emb
            else:
                row["_emb"] = None

        scored = []
        for row in data:
            if row["_emb"] is None:
                continue
            sim = _cosine_similarity(query_emb, row["_emb"])
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:candidate_count]

        top_indices = {}
        for sim, row in top:
            key = (_row_group_key(row), row["chunk_index"])
            top_indices[key] = sim

        results = []
        for sim, row in top:
            results.append({
                "id": row["id"],
                "document_id": row.get("document_id"),
                "source_title": row.get("source_title", ""),
                "chapter": row.get("chapter", ""),
                "part": row.get("part", ""),
                "sub_section": row.get("sub_section", ""),
                "chunk_index": row.get("chunk_index", 0),
                "chunk_title": row.get("chunk_title", ""),
                "chunk_summary": row.get("chunk_summary", ""),
                "chunk_role": row.get("chunk_role", ""),
                "chunk_keywords": row.get("chunk_keywords", []) or [],
                "heading_path": row.get("heading_path", []) or [],
                "document_summary": "",
                "raw_content": row.get("raw_content", ""),
                "retrieval_text": row.get("retrieval_text", ""),
                "metadata": row.get("metadata", {}),
                "similarity": sim,
                "is_context": False,
            })

        if context_window > 0:
            for sim, row in top:
                group_key = _row_group_key(row)
                ci = row["chunk_index"]
                for other in data:
                    if (
                        _row_group_key(other) == group_key
                        and abs(other["chunk_index"] - ci) <= context_window
                        and other["id"] != row["id"]
                        and (_row_group_key(other), other["chunk_index"]) not in top_indices
                    ):
                        results.append({
                            "id": other["id"],
                            "document_id": other.get("document_id"),
                            "source_title": other.get("source_title", ""),
                            "chapter": other.get("chapter", ""),
                            "part": other.get("part", ""),
                            "sub_section": other.get("sub_section", ""),
                            "chunk_index": other.get("chunk_index", 0),
                            "chunk_title": other.get("chunk_title", ""),
                            "chunk_summary": other.get("chunk_summary", ""),
                            "chunk_role": other.get("chunk_role", ""),
                            "chunk_keywords": other.get("chunk_keywords", []) or [],
                            "heading_path": other.get("heading_path", []) or [],
                            "document_summary": "",
                            "raw_content": other.get("raw_content", ""),
                            "retrieval_text": other.get("retrieval_text", ""),
                            "metadata": other.get("metadata", {}),
                            "similarity": 0.0,
                            "is_context": True,
                        })

        seen_ids = set()
        deduped = []
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                deduped.append(r)

        return deduped
    except Exception as e:
        print(f"⚠️ [deep_chat] 폴백 검색 실패: {e}")
        return []


def _fetch_university_document_maps(
    document_ids: list[int],
    section_ids: list[int],
) -> tuple[Dict[int, Dict[str, Any]], Dict[int, str]]:
    client = supabase_service.get_admin_client()
    document_map: Dict[int, Dict[str, Any]] = {}
    section_map: Dict[int, str] = {}

    if document_ids:
        try:
            result = (
                client.table("documents")
                .select("id, school_name, filename, summary, file_url, metadata")
                .in_("id", document_ids)
                .execute()
            )
            for row in result.data or []:
                doc_id = row.get("id")
                if doc_id is None:
                    continue
                document_map[int(doc_id)] = row
        except Exception as e:
            print(f"⚠️ [deep_chat] documents 메타 조회 실패: {e}")

    if section_ids:
        try:
            result = (
                client.table("document_sections")
                .select("id, section_name")
                .in_("id", section_ids)
                .execute()
            )
            for row in result.data or []:
                section_id = row.get("id")
                if section_id is None:
                    continue
                section_map[int(section_id)] = str(row.get("section_name") or "").strip()
        except Exception as e:
            print(f"⚠️ [deep_chat] document_sections 조회 실패: {e}")

    return document_map, section_map


def _normalize_university_document_rows(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    document_ids = sorted({int(row["document_id"]) for row in rows if row.get("document_id") is not None})
    section_ids = sorted({int(row["section_id"]) for row in rows if row.get("section_id") is not None})
    document_map, section_map = _fetch_university_document_maps(document_ids, section_ids)

    normalized_rows: list[Dict[str, Any]] = []
    for row in rows:
        document_id = row.get("document_id")
        section_id = row.get("section_id")
        page_number = int(row.get("page_number") or 0)
        raw_content = str(row.get("raw_data") or row.get("content") or "").strip()
        if not raw_content:
            continue

        document_info = document_map.get(int(document_id)) if document_id is not None else {}
        school_name = str(document_info.get("school_name") or "").strip()
        filename = str(document_info.get("filename") or "").strip()
        file_title = filename.replace(".pdf", "").replace(".PDF", "") if filename else school_name
        section_name = section_map.get(int(section_id), "") if section_id is not None else ""
        source_title = " / ".join(part for part in [school_name, file_title] if part)
        chunk_title = section_name or (f"{file_title} {page_number}p" if file_title and page_number else file_title)
        heading_path = [part for part in [school_name, section_name] if part]
        chunk_keywords = _extract_university_chunk_keywords(raw_content)
        metadata = {
            "source_type": "university_document",
            "school_name": school_name,
            "file_url": document_info.get("file_url") or "",
            "filename": filename,
        }

        normalized_rows.append({
            "id": row.get("id"),
            "document_id": document_id,
            "source_title": source_title or school_name or file_title,
            "chapter": section_name or school_name,
            "part": f"{page_number}페이지" if page_number else "",
            "sub_section": "",
            "chunk_index": page_number,
            "chunk_title": chunk_title,
            "chunk_summary": "",
            "chunk_role": _infer_university_chunk_role(raw_content),
            "chunk_keywords": chunk_keywords,
            "heading_path": heading_path,
            "document_summary": str(document_info.get("summary") or "").strip(),
            "raw_content": raw_content,
            "retrieval_text": raw_content,
            "metadata": metadata,
            "similarity": float(row.get("similarity", 0.0) or 0.0),
            "is_context": False,
        })

    return normalized_rows


def _retrieve_university_document_rows(
    query: str,
    universities: list[str],
    match_count: int = 3,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    if not universities:
        return [], []

    try:
        rag_query = _build_university_rag_query(query, universities)
        query_embeddings = _build_university_query_embeddings(rag_query)
    except Exception as e:
        print(f"⚠️ [deep_chat] 대학 문서 쿼리 임베딩 실패: {e}")
        return [], []

    if not query_embeddings:
        return [], []

    candidate_count = max(match_count * 4, 10)
    normalized_rows, last_error = _collect_university_chunk_rows(
        query_embeddings=query_embeddings,
        universities=universities,
        candidate_count=candidate_count,
        use_variants=True,
    )
    if normalized_rows:
        selected_rows = _rerank_rows(normalized_rows, query, max(match_count, 2))
        return selected_rows, selected_rows

    if last_error:
        print(f"⚠️ [deep_chat] 대학 문서 검색 실패: {last_error}")
    return [], []


def _retrieve_recommendation_university_rows(
    query: str,
    school_record_context: str,
    match_count: int = 4,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    try:
        rag_query = _build_recommendation_rag_query(query, school_record_context)
        query_embeddings = _build_university_query_embeddings(rag_query)
    except Exception as e:
        print(f"⚠️ [deep_chat] 추천 대학 쿼리 임베딩 실패: {e}")
        return [], []

    if not query_embeddings:
        return [], []

    shortlisted_schools = _rank_recommendation_schools(
        query_embeddings=query_embeddings,
        rag_query=rag_query,
        limit=max(match_count + 2, 5),
    )
    if not shortlisted_schools:
        return [], []

    normalized_rows, last_error = _collect_university_chunk_rows(
        query_embeddings=query_embeddings,
        universities=shortlisted_schools,
        candidate_count=max(match_count, 4),
        use_variants=False,
    )
    if normalized_rows:
        reranked = _rerank_rows(normalized_rows, rag_query, max(match_count * 3, 12))
        diversified: list[Dict[str, Any]] = []
        seen_schools: set[str] = set()

        for row in reranked:
            school_name = str(row.get("metadata", {}).get("school_name") or "").strip()
            if school_name and school_name in seen_schools:
                continue
            if school_name:
                seen_schools.add(school_name)
            diversified.append(row)
            if len(diversified) >= max(match_count, 4):
                break

        return diversified, diversified

    if last_error:
        print(f"⚠️ [deep_chat] 추천 대학 문서 검색 실패: {last_error}")
    return [], []


def _merge_reference_rows(
    query: str,
    academic_final_rows: list[Dict[str, Any]],
    academic_selected_rows: list[Dict[str, Any]],
    university_selected_rows: list[Dict[str, Any]],
    match_count: int,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    if not university_selected_rows:
        return academic_final_rows, academic_selected_rows

    target_count = max(match_count, 4)
    reserved_university_rows = _rerank_rows(
        university_selected_rows,
        query,
        min(2, len(university_selected_rows)),
    )
    all_candidates = _dedupe_rows_by_id(academic_selected_rows + university_selected_rows)
    reranked_candidates = _rerank_rows(all_candidates, query, max(target_count * 2, len(all_candidates)))

    selected_rows: list[Dict[str, Any]] = []
    seen_ids = set()

    for row in reserved_university_rows:
        row_id = row.get("id")
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        selected_rows.append(row)

    for row in reranked_candidates:
        row_id = row.get("id")
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        selected_rows.append(row)
        if len(selected_rows) >= target_count:
            break

    final_rows = _dedupe_rows_by_id(academic_final_rows + selected_rows)
    final_rows.sort(key=lambda row: (_row_group_key(row), int(row.get("chunk_index", 0))))
    return final_rows, selected_rows[:target_count]


def _retrieve_reference_rag_rows(
    query: str,
    school_record_context: str = "",
    match_count: int = 3,
    context_window: int = 1,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    academic_final_rows, academic_selected_rows = _retrieve_academic_rag_rows(
        query=query,
        match_count=match_count,
        context_window=context_window,
    )
    universities = _extract_target_universities(query)
    if universities:
        university_final_rows, university_selected_rows = _retrieve_university_document_rows(
            query=query,
            universities=universities,
            match_count=min(max(match_count, 2), 4),
        )
    elif _is_university_recommendation_query(query):
        university_final_rows, university_selected_rows = _retrieve_recommendation_university_rows(
            query=query,
            school_record_context=school_record_context,
            match_count=min(max(match_count, 4), 6),
        )
    else:
        university_final_rows, university_selected_rows = [], []
    return _merge_reference_rows(
        query=query,
        academic_final_rows=academic_final_rows,
        academic_selected_rows=academic_selected_rows,
        university_selected_rows=university_selected_rows or university_final_rows,
        match_count=match_count,
    )


def _build_sources_meta(selected_rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    sources_meta = []
    seen = set()
    for row in selected_rows:
        key = (_row_group_key(row), row.get("chapter"), row.get("chunk_index"))
        if key in seen:
            continue
        seen.add(key)
        sources_meta.append({
            "document_id": row.get("document_id"),
            "source_title": row.get("source_title", ""),
            "chapter": row.get("chapter", ""),
            "part": row.get("part", ""),
            "sub_section": row.get("sub_section", ""),
            "chunk_index": row.get("chunk_index", 0),
            "similarity": round(row.get("similarity", 0), 3),
            "rerank_score": round(row.get("rerank_score", 0), 3),
            "chunk_title": row.get("chunk_title", ""),
            "chunk_summary": row.get("chunk_summary", ""),
            "chunk_role": row.get("chunk_role", ""),
            "chunk_keywords": row.get("chunk_keywords", []) or [],
            "heading_path": row.get("heading_path", []) or [],
            "document_summary": row.get("document_summary", ""),
            "raw_content": row.get("raw_content", ""),
            "source_type": row.get("metadata", {}).get("source_type", "academic_contents"),
            "school_name": row.get("metadata", {}).get("school_name", ""),
            "file_url": row.get("metadata", {}).get("file_url", ""),
        })
    return sources_meta


def _build_planning_school_record_snapshot(
    school_record: Dict[str, Any],
    school_record_context: str,
) -> str:
    forms = school_record.get("forms") if isinstance(school_record, dict) else {}
    summary = None
    if isinstance(forms, dict):
        summary = forms.get("parsedSchoolRecordSummary")
    if not summary and isinstance(school_record, dict):
        summary = school_record.get("parsedSchoolRecordSummary")

    if summary:
        try:
            dumped = json.dumps(summary, ensure_ascii=False, indent=2)
            return _truncate_text(dumped, PLANNER_MAX_SNAPSHOT_CHARS)
        except Exception:
            pass
    return _truncate_text(school_record_context, PLANNER_MAX_SNAPSHOT_CHARS)


def _format_sources_for_planning(sources_meta: list[Dict[str, Any]]) -> str:
    if not sources_meta:
        return "(참고자료 후보 없음)"

    lines = []
    for idx, src in enumerate(sources_meta[:PLANNER_MAX_SOURCE_COUNT], start=1):
        path = " > ".join(src.get("heading_path") or []) or " > ".join(
            [p for p in [src.get("chapter", ""), src.get("part", ""), src.get("sub_section", "")] if p]
        )
        keywords = ", ".join((src.get("chunk_keywords") or [])[:5])
        lines.append(
            "\n".join(
                [
                    f"[후보 {idx}]",
                    f"- 출처: {src.get('source_title', '')}",
                    f"- 경로: {path or '(루트)'}",
                    f"- 청크 제목: {src.get('chunk_title', '')}",
                    f"- 청크 요약: {_truncate_text(src.get('chunk_summary', ''), 280)}",
                    f"- 키워드: {keywords}",
                    f"- 원문 발췌: {_truncate_text(src.get('raw_content', ''), 340)}",
                ]
            )
        )
    return "\n\n".join(lines)


def _format_history_for_planning(history: List[Dict[str, str]]) -> str:
    lines = []
    for msg in history[-6:]:
        role = "사용자" if msg.get("role") == "user" else "어시스턴트"
        content = _truncate_text(msg.get("content", ""), 240)
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(이전 대화 없음)"


def _configure_gemini():
    """google.generativeai 설정 후 모듈 반환."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        try:
            from config.config import get_settings

            api_key = get_settings().GEMINI_API_KEY
        except Exception:
            pass
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")

    genai.configure(api_key=api_key)
    return genai


def _generate_json_with_gemini(
    *,
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    max_output_tokens: int = PLANNER_MAX_OUTPUT_TOKENS,
) -> Optional[Dict[str, Any]]:
    try:
        genai = _configure_gemini()
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
            ),
            request_options={"timeout": 60.0},
        )
        return _extract_json_dict(getattr(response, "text", ""))
    except Exception as e:
        print(f"⚠️ [deep_chat] Gemini JSON 생성 실패: {e}")
        return None


NARRATIVE_MERGE_SYSTEM_PROMPT = """\
당신은 학교생활기록부 분석 리포트의 한 섹션을 하나의 매끄러운 문단으로 다듬는 작성자입니다.

입력으로 [평가기준], [학생 적용 판단], [구체적 답변] 세 블록이 주어집니다.
이 세 부분을 구분감 없이 하나의 자연스러운 문단으로 통합해 주세요.

규칙:
- 가능하면 다음 순서를 지키세요: 1) 이 섹션의 평가기준이 왜 중요한지 설명 2) 그 기준이 학생부종합전형/면접에서 왜 의미가 큰지 설명 3) 학생의 실제 활동과 특징을 그 기준에 연결 4) 최종 강점/시사점 정리.
- 첫 문장은 학생 칭찬이나 결론으로 바로 시작하지 말고, 먼저 해당 평가기준의 의미와 중요성을 설명하세요.
- "왜 성장 서사가 중요한지", "왜 신선한 주제 선정과 실증 분석이 주목받는지"처럼 참고자료에서 얻은 판단 원리를 먼저 드러낸 뒤, 그다음 학생 사례를 붙이세요.
- 불필요한 반복을 제거하고, 논리적으로 이어지도록 문장을 연결하세요.
- "평가기준에 따르면", "학생 적용 판단에서" 같은 메타 표현을 쓰지 마세요.
- 내용은 빠짐없이 담되, 독자가 한 번에 읽을 수 있는 매끄러운 글로 만드세요.
- 반드시 JSON만 출력하고, 키는 "narrative" 하나만 사용하세요.
예: {"narrative": "통합된 문단 전체 내용"}
"""


def _build_section_narrative(
    criteria_texts: list[str],
    assessment_texts: list[str],
    answer: str,
) -> str:
    """평가기준·학생 적용 판단·답변을 하나의 매끄러운 문단으로 통합."""
    parts = []
    if criteria_texts:
        parts.append("[평가기준]\n" + "\n".join(criteria_texts))
    if assessment_texts:
        parts.append("[학생 적용 판단]\n" + "\n".join(assessment_texts))
    if (answer or "").strip():
        parts.append("[구체적 답변]\n" + answer.strip())
    if not parts:
        return ""

    user_prompt = "\n\n".join(parts)
    out = _generate_json_with_gemini(
        system_prompt=NARRATIVE_MERGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=NARRATIVE_MERGE_MAX_OUTPUT_TOKENS,
    )
    narrative = (out or {}).get("narrative") if isinstance(out, dict) else None
    if isinstance(narrative, str) and narrative.strip():
        return narrative.strip()
    return (answer or "").strip()


def _build_answer_plan(
    *,
    query: str,
    history: List[Dict[str, str]],
    school_record: Dict[str, Any],
    school_record_context: str,
    initial_sources_meta: list[Dict[str, Any]],
) -> Dict[str, Any]:
    school_snapshot = _build_planning_school_record_snapshot(
        school_record, school_record_context
    )
    planning_prompt = "\n\n".join(
        [
            "[최근 대화]",
            _format_history_for_planning(history),
            "[현재 사용자 질문]",
            query.strip(),
            "[생기부 요약/스냅샷]",
            school_snapshot,
            "[1차 검색 후보]",
            _format_sources_for_planning(initial_sources_meta),
            (
                "[작업 지시]\n"
                "1. 이 질문이 요구하는 분석 유형을 파악하세요.\n"
                "2. 생기부에서 우선 확인해야 할 근거 영역을 고르세요.\n"
                "3. 외부 참고자료 재검색에 가장 적합한 정제 질문을 만드세요.\n"
                "4. 최종 답변이 어떤 섹션으로 구성되어야 하는지 정리하세요.\n"
                "반드시 JSON만 출력하세요."
            ),
        ]
    )

    raw_plan = _generate_json_with_gemini(
        system_prompt=QUERY_PLAN_SYSTEM_PROMPT,
        user_prompt=planning_prompt,
        model_name=PLANNER_MODEL,
    ) or {}

    refined_question = str(raw_plan.get("refined_question") or "").strip() or query.strip()
    retrieval_queries = _normalize_str_list(raw_plan.get("retrieval_queries"), 3)
    if refined_question and refined_question not in retrieval_queries:
        retrieval_queries.insert(0, refined_question)

    return {
        "question_type": str(raw_plan.get("question_type") or "일반 분석").strip() or "일반 분석",
        "user_goal": str(raw_plan.get("user_goal") or query).strip() or query,
        "refined_question": refined_question,
        "analysis_dimensions": _normalize_str_list(raw_plan.get("analysis_dimensions"), 6),
        "school_record_focus": _normalize_str_list(raw_plan.get("school_record_focus"), 6),
        "answer_sections": _normalize_str_list(raw_plan.get("answer_sections"), 6),
        "retrieval_queries": retrieval_queries[:3] or [query.strip()],
        "reasoning_hint": str(raw_plan.get("reasoning_hint") or "").strip(),
    }


def _format_answer_plan(answer_plan: Optional[Dict[str, Any]]) -> str:
    if not answer_plan:
        return ""

    lines = [
        f"[질문 유형]\n{answer_plan.get('question_type', '')}",
        f"[사용자 의도]\n{answer_plan.get('user_goal', '')}",
        f"[정제된 질문]\n{answer_plan.get('refined_question', '')}",
    ]

    dimensions = "\n".join(f"- {item}" for item in answer_plan.get("analysis_dimensions", []))
    focus = "\n".join(f"- {item}" for item in answer_plan.get("school_record_focus", []))
    sections = "\n".join(f"- {item}" for item in answer_plan.get("answer_sections", []))
    retrieval_queries = "\n".join(f"- {item}" for item in answer_plan.get("retrieval_queries", []))

    if dimensions:
        lines.append(f"[우선 평가축]\n{dimensions}")
    if focus:
        lines.append(f"[우선 확인할 생기부 근거]\n{focus}")
    if sections:
        lines.append(f"[답변 구성]\n{sections}")
    if retrieval_queries:
        lines.append(f"[참고자료 재검색 쿼리]\n{retrieval_queries}")
    if answer_plan.get("reasoning_hint"):
        lines.append(f"[작성 힌트]\n{answer_plan.get('reasoning_hint', '')}")

    return "\n\n".join(part for part in lines if part.strip())


def _get_source_path(row: Dict[str, Any]) -> str:
    path = " > ".join(row.get("heading_path") or [])
    if path:
        return path
    return " > ".join(
        [p for p in [row.get("chapter", ""), row.get("part", ""), row.get("sub_section", "")] if p]
    )


def _prepare_report_sources(
    sources_meta: list[Dict[str, Any]],
) -> tuple[str, Dict[str, Dict[str, Any]]]:
    if not sources_meta:
        return "(참고자료 없음)", {}

    source_lookup: Dict[str, Dict[str, Any]] = {}
    blocks = []
    for idx, src in enumerate(sources_meta[:REPORT_MAX_SOURCE_COUNT], start=1):
        source_id = f"SRC{idx}"
        source_lookup[source_id] = dict(src)
        source_path = _get_source_path(src)
        keywords = ", ".join((src.get("chunk_keywords") or [])[:6])
        blocks.append(
            "\n".join(
                [
                    f"[{source_id}]",
                    f"- 출처: {src.get('source_title', '')}",
                    f"- 경로: {source_path or '(루트)'}",
                    f"- 청크 제목: {src.get('chunk_title', '')}",
                    f"- 청크 역할: {src.get('chunk_role', '')}",
                    f"- 청크 요약: {_truncate_text(str(src.get('chunk_summary', '') or ''), 320)}",
                    f"- 핵심 키워드: {keywords}",
                    f"- 원문 발췌: {_truncate_text(str(src.get('raw_content', '') or ''), REPORT_MAX_SOURCE_SNIPPET_CHARS)}",
                ]
            )
        )
    return "\n\n".join(blocks), source_lookup


def _format_source_subset(
    source_lookup: Dict[str, Dict[str, Any]],
    allowed_source_ids: list[str],
) -> str:
    blocks = []
    for source_id in allowed_source_ids:
        src = source_lookup.get(source_id)
        if not src:
            continue
        source_path = _get_source_path(src)
        keywords = ", ".join((src.get("chunk_keywords") or [])[:6])
        blocks.append(
            "\n".join(
                [
                    f"[{source_id}]",
                    f"- 출처: {src.get('source_title', '')}",
                    f"- 경로: {source_path or '(루트)'}",
                    f"- 청크 제목: {src.get('chunk_title', '')}",
                    f"- 청크 역할: {src.get('chunk_role', '')}",
                    f"- 청크 요약: {_truncate_text(str(src.get('chunk_summary', '') or ''), 320)}",
                    f"- 핵심 키워드: {keywords}",
                    f"- 원문 발췌: {_truncate_text(str(src.get('raw_content', '') or ''), REPORT_MAX_SOURCE_SNIPPET_CHARS)}",
                ]
            )
        )
    return "\n\n".join(blocks) if blocks else "(참고자료 없음)"


def _normalize_student_profile(raw_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_profile, dict):
        return None

    axis_order = [
        "학업역량",
        "탐구 깊이",
        "전공 연결성",
        "공동체역량",
        "자기주도성",
        "성장성",
    ]
    axis_lookup: Dict[str, Dict[str, Any]] = {}
    for item in raw_profile.get("axis_scores") or []:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis") or "").strip()
        if axis not in axis_order or axis in axis_lookup:
            continue
        try:
            score = int(item.get("score"))
        except Exception:
            score = 0
        score = max(0, min(score, 5))
        axis_lookup[axis] = {
            "axis": axis,
            "score": score,
            "summary": str(item.get("summary") or "").strip(),
            "evidence_quotes": _normalize_str_list(item.get("evidence_quotes"), 2),
        }

    axis_scores = [
        axis_lookup.get(
            axis,
            {
                "axis": axis,
                "score": 0,
                "summary": "",
                "evidence_quotes": [],
            },
        )
        for axis in axis_order
    ]

    profile = {
        "headline": str(raw_profile.get("headline") or "").strip(),
        "dominant_track": str(raw_profile.get("dominant_track") or "").strip(),
        "immediate_priority": str(raw_profile.get("immediate_priority") or "").strip(),
        "strengths": _normalize_str_list(raw_profile.get("strengths"), 3),
        "risks": _normalize_str_list(raw_profile.get("risks"), 3),
        "axis_scores": axis_scores,
    }
    has_content = any(
        [
            profile["headline"],
            profile["dominant_track"],
            profile["immediate_priority"],
            profile["strengths"],
            profile["risks"],
            any(item.get("summary") or item.get("score") for item in axis_scores),
        ]
    )
    return profile if has_content else None


def _normalize_university_recommendations(raw_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_payload, dict):
        return None

    normalized_cards = []
    for idx, card in enumerate(raw_payload.get("cards") or [], start=1):
        if not isinstance(card, dict):
            continue
        school_name = str(card.get("school_name") or "").strip()
        fit_summary = str(card.get("fit_summary") or "").strip()
        if not school_name or not fit_summary:
            continue
        fit_level = str(card.get("fit_level") or "적합").strip()
        if fit_level not in {"매우 적합", "적합", "조건부 적합"}:
            fit_level = "적합"
        normalized_cards.append(
            {
                "card_id": f"university-card-{idx}",
                "school_name": school_name,
                "admission_label": str(card.get("admission_label") or "").strip(),
                "fit_level": fit_level,
                "fit_summary": fit_summary,
                "matching_points": _normalize_str_list(card.get("matching_points"), 3),
                "caution_points": _normalize_str_list(card.get("caution_points"), 3),
                "interview_note": str(card.get("interview_note") or "").strip(),
                "talent_keywords": _normalize_str_list(card.get("talent_keywords"), 4),
                "evidence_excerpt": str(card.get("evidence_excerpt") or "").strip(),
                "evidence_source": str(card.get("evidence_source") or "").strip(),
            }
        )

    if not normalized_cards:
        return None

    return {
        "summary": str(raw_payload.get("summary") or "").strip(),
        "cards": normalized_cards,
    }


def _load_nesin_detail_data() -> list[Dict[str, Any]]:
    global NESIN_DETAIL_CACHE
    if NESIN_DETAIL_CACHE is not None:
        return NESIN_DETAIL_CACHE
    try:
        with NESIN_DETAIL_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            NESIN_DETAIL_CACHE = []
            return NESIN_DETAIL_CACHE
        normalized = []
        for row in data:
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            try:
                enriched["grade"] = float(row.get("grade"))
            except Exception:
                try:
                    enriched["grade"] = float(row.get("내신등급_70%"))
                except Exception:
                    enriched["grade"] = None
            normalized.append(enriched)
        NESIN_DETAIL_CACHE = normalized
        return normalized
    except Exception as error:
        print(f"⚠️ [deep_chat] nesin detail 로드 실패: {error}")
        NESIN_DETAIL_CACHE = []
        return NESIN_DETAIL_CACHE


def _extract_user_grade_summary(user_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    metadata = user_metadata if isinstance(user_metadata, dict) else {}
    school_grade_input = metadata.get("school_grade_input") or {}
    if not isinstance(school_grade_input, dict):
        return None
    grade_summary = school_grade_input.get("gradeSummary") or {}
    if not isinstance(grade_summary, dict):
        return None

    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except Exception:
            return None

    overall_average = _to_float(grade_summary.get("overallAverage") or grade_summary.get("overall_average"))
    core_average = _to_float(grade_summary.get("coreAverage") or grade_summary.get("core_average"))
    semester_raw = grade_summary.get("semesterAverages") or grade_summary.get("semester_averages") or {}
    semester_averages: Dict[str, float] = {}
    if isinstance(semester_raw, dict):
        for key, value in semester_raw.items():
            numeric = _to_float(value)
            if numeric is not None:
                semester_averages[str(key)] = numeric

    if overall_average is None and core_average is None and not semester_averages:
        return None
    return {
        "overall_average": overall_average,
        "core_average": core_average,
        "semester_averages": semester_averages,
    }


def _extract_school_grade_input_payload(user_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    metadata = user_metadata if isinstance(user_metadata, dict) else {}
    payload = metadata.get("school_grade_input") or {}
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except Exception:
        return None


def _build_three_page_grade_chart(
    user_metadata: Optional[Dict[str, Any]],
    user_grade_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    school_grade_input = _extract_school_grade_input_payload(user_metadata)
    grade_summary = school_grade_input.get("gradeSummary") or {}
    grade_summary = grade_summary if isinstance(grade_summary, dict) else {}
    semester_averages = grade_summary.get("semesterAverages") or grade_summary.get("semester_averages") or {}
    semester_averages = semester_averages if isinstance(semester_averages, dict) else {}

    semesters = []
    overall_values: list[Optional[float]] = []
    core_values: list[Optional[float]] = []
    for semester_key in REPORT_SEMESTER_ORDER:
        label = REPORT_SEMESTER_LABELS.get(semester_key, semester_key)
        raw_semester = semester_averages.get(semester_key) or {}
        raw_semester = raw_semester if isinstance(raw_semester, dict) else {}
        overall = _safe_float(raw_semester.get("overall"))
        core = _safe_float(raw_semester.get("core"))
        semesters.append({"key": semester_key, "label": label})
        overall_values.append(overall)
        core_values.append(core)

    has_series = any(value is not None for value in overall_values + core_values)
    if not has_series and isinstance(user_grade_summary, dict):
        overall_average = _safe_float(user_grade_summary.get("overall_average"))
        core_average = _safe_float(user_grade_summary.get("core_average"))
        if overall_average is not None or core_average is not None:
            semesters = [{"key": "current", "label": "현재 평균"}]
            overall_values = [overall_average]
            core_values = [core_average]
            has_series = True

    if not has_series:
        return None

    summary_parts = []
    valid_core = [(idx, value) for idx, value in enumerate(core_values) if isinstance(value, (int, float))]
    valid_overall = [(idx, value) for idx, value in enumerate(overall_values) if isinstance(value, (int, float))]
    trend_values = valid_core or valid_overall
    if len(trend_values) >= 2:
        first_idx, first_value = trend_values[0]
        last_idx, last_value = trend_values[-1]
        delta = round(float(last_value) - float(first_value), 2)
        if delta <= -0.2:
            trend_phrase = "개선되는 흐름"
        elif delta >= 0.2:
            trend_phrase = "하락 압력이 있는 흐름"
        else:
            trend_phrase = "큰 변동 없이 유지되는 흐름"
        summary_parts.append(
            f"{semesters[first_idx]['label']} 대비 {semesters[last_idx]['label']}의 평균 흐름은 {trend_phrase}입니다."
        )
    overall_average = _safe_float((user_grade_summary or {}).get("overall_average"))
    core_average = _safe_float((user_grade_summary or {}).get("core_average"))
    if overall_average is not None or core_average is not None:
        summary_parts.append(
            "현재 평균은 "
            f"전체 {round(float(overall_average), 2) if overall_average is not None else '-'} / "
            f"국영수탐 {round(float(core_average), 2) if core_average is not None else '-'} 수준입니다."
        )

    return {
        "title": "학기별 내신 추이",
        "summary": " ".join(summary_parts).strip(),
        "semesters": semesters,
        "series": [
            {
                "key": "overall",
                "label": "전체 내신",
                "color": "#2563eb",
                "values": overall_values,
            },
            {
                "key": "core",
                "label": "국영수탐 내신",
                "color": "#111827",
                "values": core_values,
            },
        ],
    }


def _build_axis_score_chart(student_profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(student_profile, dict):
        return None
    slices = []
    total_score = 0.0
    axis_scores = student_profile.get("axis_scores") or []
    for item in axis_scores:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis") or "").strip()
        if not axis:
            continue
        score = max(0.0, min(float(item.get("score") or 0.0), 5.0))
        total_score += score
        slices.append(
            {
                "axis": axis,
                "score": round(score, 2),
                "summary": str(item.get("summary") or "").strip(),
                "evidence_quotes": _normalize_str_list(item.get("evidence_quotes"), 2),
                "color": AXIS_DISPLAY_COLORS.get(axis, "#6b7280"),
            }
        )
    if not slices:
        return None
    denominator = total_score if total_score > 0 else float(len(slices))
    for item in slices:
        item["ratio"] = round(float(item["score"]) / denominator, 4) if denominator > 0 else 0.0

    sorted_axes = sorted(slices, key=lambda item: float(item.get("score", 0.0)), reverse=True)
    top_axes = [str(item.get("axis") or "").strip() for item in sorted_axes[:2] if str(item.get("axis") or "").strip()]
    low_axes = [str(item.get("axis") or "").strip() for item in sorted(slices, key=lambda item: float(item.get("score", 0.0)))[:2] if str(item.get("axis") or "").strip()]
    summary = ""
    if top_axes:
        summary = f"현재 학생부는 {', '.join(top_axes)} 축이 먼저 읽힙니다."
        if low_axes:
            summary += f" 반대로 {', '.join(low_axes)} 축은 다음 학기 보완 우선순위로 잡는 편이 좋습니다."

    return {
        "title": "6요소 진단 점수",
        "total_score": round(total_score, 2),
        "summary": summary,
        "slices": slices,
    }


def _build_axis_diagnostic_items(
    student_profile: Optional[Dict[str, Any]],
    *,
    mode: str,
) -> list[Dict[str, Any]]:
    if not isinstance(student_profile, dict):
        return []
    axis_scores = [
        item
        for item in (student_profile.get("axis_scores") or [])
        if isinstance(item, dict) and str(item.get("axis") or "").strip()
    ]
    if not axis_scores:
        return []

    reverse = mode == "strength"
    sorted_scores = sorted(
        axis_scores,
        key=lambda item: float(item.get("score") or 0.0),
        reverse=reverse,
    )
    selected = sorted_scores[:3]
    if not reverse:
        selected = sorted_scores[:3]

    diagnostics = []
    for item in selected:
        axis = str(item.get("axis") or "").strip()
        score = max(0.0, min(float(item.get("score") or 0.0), 5.0))
        diagnostics.append(
            {
                "axis": axis,
                "score": round(score, 2),
                "title": (
                    AXIS_STRENGTH_TITLES.get(axis, "")
                    if mode == "strength"
                    else AXIS_WEAKNESS_TITLES.get(axis, "")
                ),
                "description": str(item.get("summary") or "").strip(),
                "evidence_quotes": _normalize_str_list(item.get("evidence_quotes"), 2),
                "color": AXIS_DISPLAY_COLORS.get(axis, "#6b7280"),
            }
        )
    return diagnostics


def _build_strength_block(student_profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(student_profile, dict):
        return None
    items = _build_axis_diagnostic_items(student_profile, mode="strength")
    if not items:
        return None
    top_axes = ", ".join(item["axis"] for item in items[:2] if item.get("axis"))
    headline = str(student_profile.get("headline") or "").strip()
    if top_axes:
        headline = headline or f"현재 학생부는 {top_axes} 축에서 상대적으로 강점이 먼저 읽힙니다."
    return {
        "headline": headline,
        "items": items,
    }


def _build_weakness_block(student_profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(student_profile, dict):
        return None
    items = _build_axis_diagnostic_items(student_profile, mode="weakness")
    if not items:
        return None
    low_axes = ", ".join(item["axis"] for item in items[:2] if item.get("axis"))
    headline = str(student_profile.get("immediate_priority") or "").strip()
    if low_axes:
        headline = headline or f"다음 학기에는 {low_axes} 축을 먼저 보완하는 방식으로 학생부를 설계하는 편이 좋습니다."
    return {
        "headline": headline,
        "items": items,
    }


def _build_next_semester_plan(student_profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    weakness_items = _build_axis_diagnostic_items(student_profile, mode="weakness")
    if not weakness_items:
        return None

    action_cards = []
    for idx, item in enumerate(weakness_items, start=1):
        axis = str(item.get("axis") or "").strip()
        template = AXIS_PLAN_LIBRARY.get(axis)
        if not template:
            continue
        priority = "최우선" if idx == 1 or float(item.get("score") or 0.0) <= 2.0 else "보완"
        action_cards.append(
            {
                "axis": axis,
                "priority": priority,
                "current_score": item.get("score"),
                "title": template["title"],
                "why": template["why"],
                "actions": template["actions"],
                "expected_effect": template["expected_effect"],
            }
        )

    if not action_cards:
        return None

    immediate_priority = ""
    if isinstance(student_profile, dict):
        immediate_priority = str(student_profile.get("immediate_priority") or "").strip()
    return {
        "headline": immediate_priority or "낮게 읽히는 축을 기준으로 다음 학기 활동과 세특을 재설계하는 것이 좋습니다.",
        "action_cards": action_cards,
    }


def _score_story_snippet(snippet: Dict[str, Any], focus_terms: list[str]) -> float:
    text = str(snippet.get("text") or "")
    score = 0.0
    for term in focus_terms:
        if term and term in text:
            score += 2.0
    record_type = str(snippet.get("record_type") or "")
    if record_type in {"진로활동", "세특"}:
        score += 1.6
    elif record_type in {"동아리활동", "자율활동"}:
        score += 1.2
    elif record_type == "행특":
        score += 0.7
    score += min(len(text) / 320.0, 1.5)
    return score


def _normalize_flowchart_payload(raw_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_payload, dict):
        return None
    nodes = []
    seen_ids = set()
    for raw_node in raw_payload.get("nodes") or []:
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("node_id") or "").strip()
        grade = str(raw_node.get("grade") or "").strip()
        title = str(raw_node.get("title") or "").strip()
        summary = str(raw_node.get("summary") or "").strip()
        if not node_id or node_id in seen_ids or not grade or not summary:
            continue
        seen_ids.add(node_id)
        nodes.append(
            {
                "node_id": node_id,
                "grade": grade,
                "title": title or grade,
                "summary": summary,
                "evidence_quotes": _normalize_str_list(raw_node.get("evidence_quotes"), 2),
            }
        )
    if not nodes:
        return None
    links = []
    for raw_link in raw_payload.get("links") or []:
        if not isinstance(raw_link, dict):
            continue
        from_node_id = str(raw_link.get("from_node_id") or "").strip()
        to_node_id = str(raw_link.get("to_node_id") or "").strip()
        label = str(raw_link.get("label") or "").strip()
        if not from_node_id or not to_node_id or not label:
            continue
        links.append(
            {
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "label": label,
            }
        )
    return {
        "headline": str(raw_payload.get("headline") or "").strip(),
        "nodes": nodes[:3],
        "links": links[:2],
    }


def _build_flowchart_fallback(
    school_record: Dict[str, Any],
    school_record_context: str,
    student_profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    snippets = _extract_user_school_record_snippets(school_record, school_record_context)
    focus_terms = _extract_focus_terms_from_profile(school_record_context, student_profile)
    grouped: Dict[str, list[Dict[str, Any]]] = {"1": [], "2": [], "3": []}
    for snippet in snippets:
        grade = str(snippet.get("grade") or "").strip()
        if grade in grouped:
            grouped[grade].append(snippet)

    nodes = []
    titles = {
        "1": "관심사 탐색과 기반 형성",
        "2": "심화 탐구와 연결 확장",
        "3": "전공 수렴과 완성도 점검",
    }
    for grade in ("1", "2", "3"):
        grade_snippets = grouped.get(grade) or []
        if not grade_snippets:
            continue
        grade_snippets.sort(key=lambda item: _score_story_snippet(item, focus_terms), reverse=True)
        selected = grade_snippets[:2]
        summary_parts = []
        evidence_quotes = []
        for snippet in selected:
            text = str(snippet.get("text") or "").strip()
            if not text:
                continue
            summary_parts.append(_truncate_text(text, 120))
            evidence_quotes.append(_truncate_text(text, 80))
        summary = " ".join(summary_parts).strip()
        nodes.append(
            {
                "node_id": f"grade-{grade}",
                "grade": f"{grade}학년",
                "title": titles.get(grade, f"{grade}학년 흐름"),
                "summary": summary or f"{grade}학년 기록에서 핵심 활동이 확인됩니다.",
                "evidence_quotes": evidence_quotes[:2],
            }
        )
    if not nodes:
        return None

    links = []
    for idx in range(len(nodes) - 1):
        from_node = nodes[idx]
        to_node = nodes[idx + 1]
        if idx == 0:
            label = "초기 관심사를 교과·창체 탐구로 확장하는 흐름"
        else:
            label = "누적된 활동을 전공 서사와 후속 탐구로 수렴하는 흐름"
        links.append(
            {
                "from_node_id": from_node["node_id"],
                "to_node_id": to_node["node_id"],
                "label": label,
            }
        )
    headline = ""
    if isinstance(student_profile, dict):
        headline = str(student_profile.get("dominant_track") or "").strip()
    return {
        "headline": headline or "학년이 올라갈수록 관심사를 심화하고 연결하는 흐름이 확인됩니다.",
        "nodes": nodes[:3],
        "links": links[:2],
    }


def _build_three_page_flowchart(
    *,
    school_record: Dict[str, Any],
    school_record_context: str,
    student_profile: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    snippets = _extract_user_school_record_snippets(school_record, school_record_context)
    grade_blocks = []
    for grade in ("1", "2", "3"):
        grade_snippets = [
            snippet
            for snippet in snippets
            if str(snippet.get("grade") or "").strip() == grade
        ][:4]
        if not grade_snippets:
            continue
        joined = "\n".join(
            f"- {snippet.get('label', '')}: {_truncate_text(str(snippet.get('text') or ''), 240)}"
            for snippet in grade_snippets
        )
        grade_blocks.append(f"[{grade}학년 후보 근거]\n{joined}")
    if not grade_blocks:
        return None

    prompt = "\n\n".join(
        [
            "[학생부 전체 요약]",
            _truncate_text(school_record_context, 4500),
            "[학생 평가 프로필 요약]",
            _truncate_text(
                "\n".join(
                    [
                        str((student_profile or {}).get("headline") or ""),
                        str((student_profile or {}).get("dominant_track") or ""),
                    ]
                ),
                600,
            ),
            *grade_blocks,
        ]
    )
    raw_payload = _generate_json_with_gemini(
        system_prompt=THREE_PAGE_FLOWCHART_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=FLOWCHART_MAX_OUTPUT_TOKENS,
    )
    normalized = _normalize_flowchart_payload(raw_payload or {})
    if normalized:
        return normalized
    return _build_flowchart_fallback(
        school_record=school_record,
        school_record_context=school_record_context,
        student_profile=student_profile,
    )


def _build_three_page_comparison_page(report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(report, dict):
        return None
    cards = []
    for section in report.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for raw_card in section.get("comparison_cards") or []:
            if not isinstance(raw_card, dict):
                continue
            cards.append(
                {
                    "card_id": str(raw_card.get("card_id") or "").strip(),
                    "label": str(raw_card.get("label") or "").strip(),
                    "match_reason": str(raw_card.get("match_reason") or "").strip(),
                    "comparison_axis": str(raw_card.get("comparison_axis") or "").strip(),
                    "excerpt_pairs": [
                        {
                            "pair_id": str(pair.get("pair_id") or "").strip(),
                            "user_excerpt_label": str(pair.get("user_excerpt_label") or "").strip(),
                            "user_excerpt": str(pair.get("user_excerpt") or "").strip(),
                            "accepted_excerpt_label": str(pair.get("accepted_excerpt_label") or "").strip(),
                            "accepted_excerpt": str(pair.get("accepted_excerpt") or "").strip(),
                            "pair_comment": str(pair.get("pair_comment") or "").strip(),
                        }
                        for pair in (raw_card.get("excerpt_pairs") or [])[:2]
                        if isinstance(pair, dict)
                        and str(pair.get("user_excerpt") or "").strip()
                        and str(pair.get("accepted_excerpt") or "").strip()
                    ],
                    "good_points": _normalize_str_list(raw_card.get("good_points"), 3),
                    "gaps": _normalize_str_list(raw_card.get("gaps"), 3),
                    "action_tips": _normalize_str_list(raw_card.get("action_tips"), 3),
                }
            )
            if len(cards) >= 3:
                break
        if len(cards) >= 3:
            break
    if not cards:
        return None
    headline = "유사 합격자와 비교하면 닮은 축은 보이지만, 차이를 만드는 세부 밀도와 후속 확장에서 승부가 갈립니다."
    return {
        "headline": headline,
        "cards": cards[:3],
    }


def _build_three_page_report(
    *,
    report: Dict[str, Any],
    school_record: Dict[str, Any],
    school_record_context: str,
    student_profile: Optional[Dict[str, Any]],
    user_metadata: Optional[Dict[str, Any]],
    user_grade_summary: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(report, dict):
        return None

    grade_chart = _build_three_page_grade_chart(user_metadata, user_grade_summary)
    score_chart = _build_axis_score_chart(student_profile)
    strength_block = _build_strength_block(student_profile)
    weakness_block = _build_weakness_block(student_profile)
    next_semester_plan = _build_next_semester_plan(student_profile)
    flowchart = _build_three_page_flowchart(
        school_record=school_record,
        school_record_context=school_record_context,
        student_profile=student_profile,
    )
    comparison_page = _build_three_page_comparison_page(report)

    if not any([grade_chart, score_chart, strength_block, weakness_block, next_semester_plan, flowchart, comparison_page]):
        return None

    return {
        "page1": {
            "grade_chart": grade_chart,
            "score_chart": score_chart,
            "strength_block": strength_block,
            "flowchart": flowchart,
        },
        "page2": {
            "weakness_block": weakness_block,
            "next_semester_plan": next_semester_plan,
        },
        "page3": comparison_page,
    }


def _normalize_school_name_key(name: str) -> str:
    compact = re.sub(r"\s+", "", str(name or "").strip())
    compact = re.sub(r"대학교$", "대", compact)
    compact = re.sub(r"대학$", "대", compact)
    return compact


def _extract_focus_terms_from_profile(
    school_record_context: str,
    student_profile: Optional[Dict[str, Any]],
) -> list[str]:
    candidates = _extract_school_record_focus_terms(school_record_context, limit=6)
    if isinstance(student_profile, dict):
        dominant_track = str(student_profile.get("dominant_track") or "").strip()
        headline = str(student_profile.get("headline") or "").strip()
        for text in (dominant_track, headline):
            for token in re.findall(r"[0-9A-Za-z가-힣]{2,}", text):
                if token not in candidates:
                    candidates.append(token)
                if len(candidates) >= 8:
                    return candidates[:8]
    return candidates[:8]


def _extract_keyword_excerpt(raw_text: str, keywords: list[str], max_chars: int = 220) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    lines = _non_empty_lines(text)
    for line in lines:
        if any(keyword in line for keyword in keywords):
            return _truncate_text(line, max_chars)
    return _truncate_text(lines[0] if lines else text, max_chars)


def _build_university_axis_weights(keywords: list[str], joined_text: str) -> Dict[str, float]:
    weights = {
        "학업역량": 1.0,
        "탐구 깊이": 1.0,
        "전공 연결성": 1.0,
        "공동체역량": 1.0,
        "자기주도성": 1.0,
        "성장성": 1.0,
    }
    keyword_set = set(keywords)
    text = str(joined_text or "")

    if keyword_set & {"학업역량", "학업성취도"} or "학업" in text:
        weights["학업역량"] += 1.4
    if keyword_set & {"탐구력", "학업역량"} or any(token in text for token in ("탐구", "심화", "주제")):
        weights["탐구 깊이"] += 1.2
    if keyword_set & {"전공적합성", "진로역량"} or any(token in text for token in ("전공", "진로", "관련 교과")):
        weights["전공 연결성"] += 1.4
    if keyword_set & {"공동체역량", "리더십"} or any(token in text for token in ("협업", "소통", "배려", "봉사", "공동체")):
        weights["공동체역량"] += 1.3
    if keyword_set & {"자기주도성"} or any(token in text for token in ("자기주도", "주도적", "스스로", "주도성")):
        weights["자기주도성"] += 1.2
    if keyword_set & {"발전가능성", "성장역량"} or any(token in text for token in ("발전가능성", "성장", "변화")):
        weights["성장성"] += 1.3

    return weights


def _normalize_university_profile(raw_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_profile, dict):
        return None
    school_name = str(raw_profile.get("school_name") or "").strip()
    if not school_name:
        return None
    return {
        "school_name": school_name,
        "evaluation_keywords": _normalize_str_list(raw_profile.get("evaluation_keywords"), 5),
        "talent_summary": str(raw_profile.get("talent_summary") or "").strip(),
        "evaluation_summary": str(raw_profile.get("evaluation_summary") or "").strip(),
        "interview_policy": str(raw_profile.get("interview_policy") or "").strip(),
        "evidence_excerpt": str(raw_profile.get("evidence_excerpt") or "").strip(),
        "source_title": str(raw_profile.get("source_title") or "").strip(),
        "axis_weights": raw_profile.get("axis_weights") or {},
    }


def _build_university_profile_from_sources(
    school_name: str,
    source_rows: list[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    cache_key = _normalize_school_name_key(school_name)
    cached = UNIVERSITY_PROFILE_CACHE.get(cache_key)
    if cached:
        return cached
    if not source_rows:
        return None

    joined_text = "\n".join(
        _truncate_text(str(row.get("raw_content") or ""), 1200)
        for row in source_rows[:4]
        if str(row.get("raw_content") or "").strip()
    )
    if not joined_text.strip():
        return None

    keywords = []
    for keyword in (
        "학업역량",
        "학업성취도",
        "탐구력",
        "전공적합성",
        "진로역량",
        "공동체역량",
        "발전가능성",
        "성장역량",
        "자기주도성",
        "리더십",
    ):
        if keyword in joined_text and keyword not in keywords:
            keywords.append(keyword)
    if not keywords:
        keywords = _normalize_str_list(
            [item for row in source_rows for item in (row.get("chunk_keywords") or [])],
            5,
        )

    evidence_excerpt = ""
    for row in source_rows:
        evidence_excerpt = _extract_keyword_excerpt(
            str(row.get("raw_content") or ""),
            keywords or ["학생부종합전형", "서류평가", "면접"],
        )
        if evidence_excerpt:
            break

    interview_policy = ""
    if "면접" in joined_text or "MMI" in joined_text:
        interview_policy = _extract_keyword_excerpt(joined_text, ["면접", "MMI"], 180)

    talent_summary_keywords = ", ".join(keywords[:3]) if keywords else "학종 정성평가 요소"
    profile = _normalize_university_profile(
        {
            "school_name": school_name,
            "evaluation_keywords": keywords,
            "talent_summary": f"{school_name}는 {talent_summary_keywords}를 중심으로 학생부를 읽는 경향이 강합니다.",
            "evaluation_summary": _truncate_text(
                evidence_excerpt or joined_text,
                220,
            ),
            "interview_policy": interview_policy,
            "evidence_excerpt": evidence_excerpt,
            "source_title": str(source_rows[0].get("source_title") or school_name).strip(),
            "axis_weights": _build_university_axis_weights(keywords, joined_text),
        }
    )
    if profile:
        UNIVERSITY_PROFILE_CACHE[cache_key] = profile
    return profile


def _build_target_university_profiles(target_universities: list[str]) -> list[Dict[str, Any]]:
    profiles: list[Dict[str, Any]] = []
    for school_name in target_universities:
        _, selected_rows = _retrieve_university_document_rows(
            query=f"{school_name} 학생부종합전형 인재상 서류평가 기준 면접",
            universities=[school_name],
            match_count=3,
        )
        profile = _build_university_profile_from_sources(school_name, selected_rows)
        if profile:
            profiles.append(profile)
    return profiles


def _pick_best_nesin_row_for_school(
    school_name: str,
    focus_terms: list[str],
) -> Optional[Dict[str, Any]]:
    normalized_school = _normalize_school_name_key(school_name)
    candidates = []
    for row in _load_nesin_detail_data():
        row_school = _normalize_school_name_key(str(row.get("university") or ""))
        if row_school != normalized_school:
            continue
        grade = row.get("grade")
        if not isinstance(grade, (int, float)):
            continue
        department = str(row.get("department") or "").strip()
        focus_bonus = 0
        if any(term and term in department for term in focus_terms):
            focus_bonus = 1
        candidates.append((focus_bonus, float(grade), row))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]


def _build_grade_support_for_school(
    school_name: str,
    user_grade_summary: Optional[Dict[str, Any]],
    focus_terms: list[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(user_grade_summary, dict):
        return None
    user_grade = user_grade_summary.get("core_average") or user_grade_summary.get("overall_average")
    if not isinstance(user_grade, (int, float)):
        return None

    row = _pick_best_nesin_row_for_school(school_name, focus_terms)
    if not row:
        return None

    cutoff = row.get("grade")
    if not isinstance(cutoff, (int, float)):
        return None

    gap = float(user_grade) - float(cutoff)
    if gap <= -0.3:
        label = "안정권"
    elif gap <= 0.15:
        label = "적정권"
    elif gap <= 0.5:
        label = "상향권"
    else:
        label = "도전권"

    return {
        "label": label,
        "user_grade": round(float(user_grade), 2),
        "cutoff_grade": round(float(cutoff), 2),
        "department": str(row.get("department") or "").strip(),
        "admission_type": str(row.get("jeonhyung") or "").strip(),
        "source_url": str(row.get("url") or "").strip(),
    }


def _build_accepted_case_similarity_hints(
    *,
    school_record: Dict[str, Any],
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    candidates = _build_accepted_case_candidates(
        user_message=_get_generation_task_text("", answer_plan),
        school_record=school_record,
        school_record_context=school_record_context,
        answer_plan=answer_plan,
    )
    hints = []
    for candidate in candidates[:3]:
        score = float(candidate.get("_candidate_score", 0.0) or 0.0)
        hints.append(
            {
                "label": str(candidate.get("label") or "").strip(),
                "match_reason": str(candidate.get("meta", {}).get("주요_특징") or "").strip(),
                "similarity_score": round(score, 3),
            }
        )
    return hints


def _fit_level_from_score(score: float) -> str:
    if score >= 4.15:
        return "매우 적합"
    if score >= 3.35:
        return "적합"
    return "조건부 적합"


def _build_university_recommendation_cards(
    *,
    student_profile: Optional[Dict[str, Any]],
    university_profiles: list[Dict[str, Any]],
    user_grade_summary: Optional[Dict[str, Any]],
    focus_terms: list[str],
) -> Optional[Dict[str, Any]]:
    if not isinstance(student_profile, dict) or not university_profiles:
        return None

    axis_scores = {
        str(item.get("axis") or "").strip(): float(item.get("score") or 0)
        for item in (student_profile.get("axis_scores") or [])
        if isinstance(item, dict)
    }
    if not axis_scores:
        return None

    cards = []
    for idx, profile in enumerate(university_profiles, start=1):
        weights = profile.get("axis_weights") or {}
        weighted_total = 0.0
        weight_sum = 0.0
        axis_deltas = []
        for axis, score in axis_scores.items():
            weight = float(weights.get(axis, 1.0) or 1.0)
            weighted_total += score * weight
            weight_sum += weight
            axis_deltas.append((score * weight, axis, score, weight))
        if weight_sum <= 0:
            continue
        fit_score = weighted_total / weight_sum
        axis_deltas.sort(reverse=True)
        top_axes = [axis for _, axis, _, _ in axis_deltas[:2]]
        low_axes = sorted(
            ((score, axis) for axis, score in axis_scores.items()),
            key=lambda item: item[0],
        )
        caution_axis = low_axes[0][1] if low_axes else ""

        matching_points = []
        for axis in top_axes:
            if axis == "학업역량":
                matching_points.append("교과와 세특에서 드러나는 학업 기반이 이 대학의 기본 평가축과 잘 맞습니다.")
            elif axis == "탐구 깊이":
                matching_points.append("탐구를 단순 활동이 아니라 심화 과정으로 보여줄 수 있다는 점이 강점으로 읽힙니다.")
            elif axis == "전공 연결성":
                matching_points.append("관심 계열과 활동 사이의 연결성이 비교적 선명해 전공 적합성 해석이 가능합니다.")
            elif axis == "공동체역량":
                matching_points.append("창체와 행특에서 읽히는 협업·책임감 요소가 공동체 평가와 맞닿아 있습니다.")
            elif axis == "자기주도성":
                matching_points.append("스스로 주제를 잡고 확장하는 흐름이 자기주도성 평가에서 유리하게 작동할 수 있습니다.")
            elif axis == "성장성":
                matching_points.append("학년이 올라갈수록 탐구와 서사가 정교해지는 성장 흐름을 만들 여지가 있습니다.")
        matching_points = _normalize_str_list(matching_points, 3)

        caution_points = []
        if caution_axis == "학업역량":
            caution_points.append("교과 성취와 세특의 학업 밀도를 더 선명하게 보여줘야 상위권 대학에서 설득력이 높아집니다.")
        elif caution_axis == "탐구 깊이":
            caution_points.append("탐구가 흥미 수준에 머무르지 않도록 주제의 심화와 후속 확장이 더 필요합니다.")
        elif caution_axis == "전공 연결성":
            caution_points.append("전공과 직접 연결되는 활동의 논리와 누적성이 더 선명해야 합니다.")
        elif caution_axis == "공동체역량":
            caution_points.append("협업, 배려, 책임감이 드러나는 공동체 근거를 더 명확히 남길 필요가 있습니다.")
        elif caution_axis == "자기주도성":
            caution_points.append("학생이 직접 문제를 설정하고 끌고 간 장면을 더 구체적으로 보여줘야 합니다.")
        elif caution_axis == "성장성":
            caution_points.append("학년별 변화와 후속 확장의 흐름을 더 분명하게 정리해야 성장성이 살아납니다.")

        grade_support = _build_grade_support_for_school(
            profile.get("school_name", ""),
            user_grade_summary,
            focus_terms,
        )
        if grade_support:
            caution_points.append(
                f"교과 보조 판정 기준으로는 {grade_support['department']} {grade_support['admission_type']}가 {grade_support['label']} 수준입니다."
            )
        caution_points = _normalize_str_list(caution_points, 3)

        fit_summary = (
            f"{profile.get('school_name', '')}는 "
            f"{', '.join(profile.get('evaluation_keywords') or ['학생부종합전형'])}을 중시하는 편이라 "
            f"현재 학생부의 {', '.join(top_axes) if top_axes else '핵심 축'}과 비교적 잘 맞습니다."
        )
        cards.append(
            {
                "card_id": f"university-card-{idx}",
                "school_name": profile.get("school_name", ""),
                "admission_label": "학생부종합전형 기준 추천",
                "fit_level": _fit_level_from_score(fit_score),
                "fit_summary": fit_summary,
                "matching_points": matching_points,
                "caution_points": caution_points,
                "interview_note": profile.get("interview_policy", ""),
                "talent_keywords": profile.get("evaluation_keywords", []),
                "evidence_excerpt": profile.get("evidence_excerpt", ""),
                "evidence_source": profile.get("source_title", ""),
                "fit_score": round(fit_score, 2),
                "grade_support": grade_support,
            }
        )

    cards.sort(key=lambda item: float(item.get("fit_score", 0.0) or 0.0), reverse=True)
    if not cards:
        return None

    summary = "학생부종합전형 기준으로는 학생부의 핵심 축과 대학 평가축이 맞물리는 학교를 우선 추천하고, 내신 정보는 교과 전형 보조 판단으로만 함께 표시했습니다."
    return {
        "summary": summary,
        "cards": cards[:4],
    }


def _build_student_profile_summary(
    *,
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    prompt = "\n\n".join(
        [
            f"[{_get_generation_task_label(answer_plan)}]",
            _get_generation_task_text("", answer_plan),
            "[학생 생기부 요약]",
            _truncate_text(school_record_context, 7000),
            (
                "[작업 지시]\n"
                "이 학생의 생기부를 6개 축으로 구조화한 학생 평가 프로필 JSON을 작성하세요.\n"
                "강점, 리스크, 즉시 보완 우선과제를 분리하고, 각 축은 점수와 짧은 해석을 함께 제시하세요.\n"
                "반드시 학생 생기부에 직접 드러난 내용만 근거로 판단하고, 참고자료나 합격 사례의 표현을 학생의 강점/보완점처럼 옮겨 쓰지 마세요."
            ),
        ]
    )
    raw_profile = _generate_json_with_gemini(
        system_prompt=STUDENT_PROFILE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
    )
    return _normalize_student_profile(raw_profile or {})


def _build_university_recommendation_summary(
    *,
    school_record: Dict[str, Any],
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
    student_profile: Optional[Dict[str, Any]],
    user_grade_summary: Optional[Dict[str, Any]],
    matching_summary: str,
) -> tuple[Optional[Dict[str, Any]], list[Dict[str, Any]]]:
    recommendation_query = (
        matching_summary.strip()
        or _build_recommendation_rag_query("학생부종합전형 적합 대학 추천", school_record_context)
    )
    target_universities: list[str] = []
    if recommendation_query:
        try:
            query_embeddings = _build_university_query_embeddings(recommendation_query)
            target_universities = _rank_recommendation_schools(
                query_embeddings=query_embeddings,
                rag_query=recommendation_query,
                limit=6,
            )
        except Exception as error:
            print(f"⚠️ [deep_chat] 적합 대학 랭킹 실패: {error}")

    if not target_universities:
        target_universities = _get_document_school_names()[:4]

    university_profiles = _build_target_university_profiles(target_universities[:4])
    focus_terms = _extract_focus_terms_from_profile(school_record_context, student_profile)
    recommendations = _build_university_recommendation_cards(
        student_profile=student_profile,
        university_profiles=university_profiles,
        user_grade_summary=user_grade_summary,
        focus_terms=focus_terms,
    )
    return recommendations, university_profiles


def _build_section_outline(answer_plan: Optional[Dict[str, Any]]) -> list[Dict[str, str]]:
    titles = []
    if isinstance(answer_plan, dict):
        titles = _normalize_str_list(answer_plan.get("answer_sections"), 6)
    if not titles:
        titles = ["종합 평가", "학업 역량", "전공 적합성", "보완 전략"]
    return [
        {
            "section_id": f"section-{idx}",
            "title": title,
        }
        for idx, title in enumerate(titles[:6], start=1)
    ]


def _build_section_stream_payload(
    *,
    section_result: Dict[str, Any],
    section_index: int,
    total_sections: int,
) -> Dict[str, Any]:
    answer = re.sub(r"\s+", " ", str(section_result.get("answer") or "")).strip()
    if not answer:
        raw_assessment = section_result.get("student_assessment") or []
        if isinstance(raw_assessment, list):
            for item in raw_assessment:
                if not isinstance(item, dict):
                    continue
                answer = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
                if answer:
                    break

    return {
        "type": "section",
        "section": {
            "section_id": str(section_result.get("section_id") or "").strip(),
            "title": str(section_result.get("title") or "").strip(),
            "preview": _truncate_text(answer, 280),
        },
        "section_index": section_index + 1,
        "total_sections": total_sections,
    }


def _build_plain_text_from_report(report: Dict[str, Any]) -> str:
    parts = []
    title = str(report.get("report_title", "")).strip()
    summary = str(report.get("summary", "")).strip()
    direct_answer = report.get("direct_answer") if isinstance(report.get("direct_answer"), dict) else {}
    if title:
        parts.append(title)
    if summary:
        parts.append(summary)
    if direct_answer:
        direct_parts = []
        direct_title = str(direct_answer.get("title", "")).strip()
        direct_intro = str(direct_answer.get("intro", "")).strip()
        direct_items = [
            str(item).strip()
            for item in (direct_answer.get("items") or [])
            if str(item).strip()
        ]
        direct_closing = str(direct_answer.get("closing", "")).strip()
        if direct_title:
            direct_parts.append(f"## {direct_title}")
        if direct_intro:
            direct_parts.append(direct_intro)
        if direct_items:
            direct_parts.append(
                "\n".join(f"{idx}. {item}" for idx, item in enumerate(direct_items, start=1))
            )
        if direct_closing:
            direct_parts.append(direct_closing)
        if direct_parts:
            parts.append("\n\n".join(direct_parts))

    for section in report.get("sections", []):
        if str(section.get("section_id") or "").strip() == "accepted-case-comparison":
            continue
        section_title = str(section.get("title", "")).strip()
        section_narrative = str(section.get("section_narrative", "")).strip()
        comparison_focus = str(section.get("comparison_focus", "")).strip()
        comparison_cards = section.get("comparison_cards", []) or []
        evaluation_criteria = section.get("evaluation_criteria", []) or []
        student_assessment = section.get("student_assessment", []) or []
        answer = str(section.get("answer", "")).strip()
        if section_title:
            parts.append(f"## {section_title}")
        if section_narrative:
            parts.append(section_narrative)
        if comparison_focus:
            parts.append(f"[비교 관점]\n{comparison_focus}")
        if isinstance(comparison_cards, list) and comparison_cards:
            card_parts = []
            for idx, card in enumerate(comparison_cards, start=1):
                if not isinstance(card, dict):
                    continue
                lines = [f"[사례 {idx}] {str(card.get('label', '')).strip()}"]
                match_reason = str(card.get("match_reason", "")).strip()
                if match_reason:
                    lines.append(f"[선정 이유]\n{match_reason}")
                comparison_axis = str(card.get("comparison_axis", "")).strip()
                if comparison_axis:
                    lines.append(f"[비교 축]\n{comparison_axis}")
                excerpt_pairs = card.get("excerpt_pairs") or []
                if isinstance(excerpt_pairs, list):
                    for pair_idx, pair in enumerate(excerpt_pairs, start=1):
                        if not isinstance(pair, dict):
                            continue
                        user_excerpt = str(pair.get("user_excerpt", "")).strip()
                        accepted_excerpt = str(pair.get("accepted_excerpt", "")).strip()
                        if not user_excerpt or not accepted_excerpt:
                            continue
                        lines.append(
                            f"[원문 비교 {pair_idx} | {str(pair.get('user_excerpt_label', '')).strip() or '사용자 발췌'}]\n{user_excerpt}"
                        )
                        lines.append(
                            f"[합격자 대응 원문 {pair_idx} | {str(pair.get('accepted_excerpt_label', '')).strip() or '합격자 발췌'}]\n{accepted_excerpt}"
                        )
                        pair_comment = str(pair.get("pair_comment", "")).strip()
                        if pair_comment:
                            lines.append(f"[비교 해설 {pair_idx}]\n{pair_comment}")
                for key, label in (
                    ("good_points", "좋은 점"),
                    ("gaps", "차이점/부족한 점"),
                    ("action_tips", "보완 포인트"),
                ):
                    values = [
                        str(item).strip()
                        for item in (card.get(key) or [])
                        if str(item).strip()
                    ]
                    if values:
                        lines.append(f"[{label}]\n" + "\n".join(f"- {item}" for item in values))
                card_parts.append("\n".join(lines))
            if card_parts:
                parts.append("\n\n".join(card_parts))
        else:
            if evaluation_criteria:
                criteria_text = "\n".join(
                    f"- {str(item.get('text', '')).strip()}"
                    for item in evaluation_criteria
                    if isinstance(item, dict) and str(item.get("text", "")).strip()
                )
                if criteria_text:
                    parts.append(f"[평가기준]\n{criteria_text}")
            if student_assessment:
                assessment_text = "\n".join(
                    f"- {str(item.get('text', '')).strip()}"
                    for item in student_assessment
                    if isinstance(item, dict) and str(item.get("text", "")).strip()
                )
                if assessment_text:
                    parts.append(f"[학생 적용 판단]\n{assessment_text}")
            if answer:
                parts.append(f"[답변]\n{answer}")

    return "\n\n".join(part for part in parts if part.strip())


def _normalize_structured_report(
    raw_report: Dict[str, Any],
    *,
    answer_plan: Optional[Dict[str, Any]],
    source_lookup: Dict[str, Dict[str, Any]],
    section_evidence_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    sections_raw = raw_report.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None

    fallback_titles = (
        answer_plan.get("answer_sections", []) if isinstance(answer_plan, dict) else []
    ) or []

    normalized_sections = []
    evidence_catalog: Dict[str, Dict[str, Any]] = {}

    for section_idx, raw_section in enumerate(sections_raw, start=1):
        if not isinstance(raw_section, dict):
            continue

        section_id = str(raw_section.get("section_id") or f"section-{section_idx}").strip()
        title = str(
            raw_section.get("title")
            or (fallback_titles[section_idx - 1] if section_idx - 1 < len(fallback_titles) else f"섹션 {section_idx}")
        ).strip()
        answer = str(raw_section.get("answer") or "").strip()

        section_criteria_evidence_refs = []
        source_id_to_evidence_id: Dict[str, str] = {}
        source_id_to_why_used: Dict[str, str] = {}
        seen_source_ids = set()
        raw_evidence = raw_section.get("evidence")
        if isinstance(raw_evidence, list):
            for evidence_idx, item in enumerate(raw_evidence, start=1):
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("source_id") or "").strip()
                if not source_id or source_id in seen_source_ids or source_id not in source_lookup:
                    continue
                seen_source_ids.add(source_id)
                src = source_lookup[source_id]
                used_excerpt = _expand_excerpt_to_min_lines(
                    item.get("used_excerpt") or "",
                    src.get("raw_content", "") or "",
                )
                evidence_id = f"{section_id}-e{evidence_idx}"
                evidence_catalog[evidence_id] = {
                    "evidence_id": evidence_id,
                    "source_id": source_id,
                    "source_type": src.get("source_type", "academic_contents"),
                    "source_title": src.get("source_title", ""),
                    "source_path": _get_source_path(src),
                    "chunk_title": src.get("chunk_title", ""),
                    "chunk_index": src.get("chunk_index", 0),
                    "chunk_role": src.get("chunk_role", ""),
                    "chunk_summary": src.get("chunk_summary", ""),
                    "document_summary": src.get("document_summary", ""),
                    "used_excerpt": used_excerpt,
                    "why_used": str(item.get("why_used") or "").strip(),
                    "evidence_type": "evaluation_criteria",
                }
                section_criteria_evidence_refs.append(evidence_id)
                source_id_to_evidence_id[source_id] = evidence_id
                source_id_to_why_used[source_id] = str(item.get("why_used") or "").strip()

        school_record_evidence_refs = []
        school_record_index_to_evidence_id: Dict[int, str] = {}
        section_evidence = (section_evidence_map or {}).get(section_id, {})
        school_record_evidence = section_evidence.get("school_record_evidence", []) or []
        for sr_idx, item in enumerate(school_record_evidence, start=1):
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote") or "").strip()
            if not quote:
                continue
            evidence_id = f"{section_id}-sr{sr_idx}"
            evidence_catalog[evidence_id] = {
                "evidence_id": evidence_id,
                "evidence_type": "school_record",
                "label": str(item.get("label") or f"생기부 근거 {sr_idx}").strip(),
                "used_excerpt": quote,
                "why_used": str(item.get("interpretation") or "").strip(),
            }
            school_record_evidence_refs.append(evidence_id)
            school_record_index_to_evidence_id[sr_idx] = evidence_id

        evaluation_criteria = []
        raw_evaluation_criteria = raw_section.get("evaluation_criteria")
        if isinstance(raw_evaluation_criteria, list):
            for criterion_idx, item in enumerate(raw_evaluation_criteria, start=1):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                source_refs = _normalize_str_list(item.get("source_refs"), 4)
                linked_evidence_refs = [
                    source_id_to_evidence_id[source_id]
                    for source_id in source_refs
                    if source_id in source_id_to_evidence_id
                ]
                supporting_statements = [
                    source_id_to_why_used[source_id]
                    for source_id in source_refs
                    if source_id in source_id_to_why_used
                ]
                if not text:
                    continue
                text = _strip_meta_suffix(text)
                text = _remove_generic_metric_sentences(text)
                if text and text[-1] not in ".!?":
                    text += "."
                text = _merge_supporting_statements_into_text(text, supporting_statements)
                text = _remove_generic_metric_sentences(text)
                evaluation_criteria.append(
                    {
                        "criterion_id": f"{section_id}-c{criterion_idx}",
                        "text": text,
                        "evidence_refs": linked_evidence_refs,
                    }
                )

        student_assessment = []
        raw_student_assessment = raw_section.get("student_assessment")
        if isinstance(raw_student_assessment, list):
            for assessment_idx, item in enumerate(raw_student_assessment, start=1):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                ref_indexes = item.get("school_record_ref_indexes")
                if isinstance(ref_indexes, list):
                    indexes = [
                        int(idx)
                        for idx in ref_indexes
                        if isinstance(idx, (int, float)) or (isinstance(idx, str) and idx.isdigit())
                    ]
                else:
                    indexes = []
                linked_evidence_refs = [
                    school_record_index_to_evidence_id[idx]
                    for idx in indexes
                    if idx in school_record_index_to_evidence_id
                ]
                if not text:
                    continue
                text = _remove_generic_metric_sentences(text)
                if not text:
                    continue
                student_assessment.append(
                    {
                        "assessment_id": f"{section_id}-a{assessment_idx}",
                        "text": text,
                        "school_record_refs": linked_evidence_refs,
                    }
                )

        section_supporting_statements = [
            evidence_catalog[evidence_id].get("why_used", "")
            for evidence_id in section_criteria_evidence_refs
            if evidence_id in evidence_catalog
        ]
        answer = _strip_meta_suffix(answer)
        answer = _remove_generic_metric_sentences(answer)
        if answer and answer[-1] not in ".!?":
            answer += "."
        answer = _merge_supporting_statements_into_text(answer, section_supporting_statements)
        answer = _remove_generic_metric_sentences(answer)

        if not title or (not evaluation_criteria and not student_assessment and not answer):
            continue

        criteria_texts = [
            str(c.get("text", "")).strip()
            for c in evaluation_criteria
            if isinstance(c, dict) and str(c.get("text", "")).strip()
        ]
        assessment_texts = [
            str(a.get("text", "")).strip()
            for a in student_assessment
            if isinstance(a, dict) and str(a.get("text", "")).strip()
        ]
        section_narrative = _build_section_narrative(criteria_texts, assessment_texts, answer)

        normalized_sections.append(
            {
                "section_id": section_id,
                "title": title,
                "evaluation_criteria": evaluation_criteria,
                "student_assessment": student_assessment,
                "answer": answer,
                "section_narrative": section_narrative,
                "criteria_evidence_refs": section_criteria_evidence_refs,
                "school_record_evidence_refs": school_record_evidence_refs,
            }
        )

    if not normalized_sections:
        return None

    normalized_sections = _dedupe_overlapping_sections(normalized_sections)

    report = {
        "report_title": str(raw_report.get("report_title") or _get_report_title(answer_plan)).strip(),
        "summary": str(raw_report.get("summary") or "").strip(),
        "sections": normalized_sections,
        "evidence_catalog": evidence_catalog,
    }
    report["plain_text"] = _build_plain_text_from_report(report)
    return report


def _extract_requested_item_count(query: str) -> int:
    text = str(query or "").strip()
    if not text:
        return 0
    match = re.search(r"(\d{1,2})\s*개", text)
    if not match:
        return 0
    try:
        count = int(match.group(1))
    except Exception:
        return 0
    return max(0, min(count, 20))


def _normalize_direct_answer_block(
    raw_block: Dict[str, Any],
    *,
    default_title: str = "질문에 대한 바로 답변",
) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_block, dict):
        return None
    title = str(raw_block.get("title") or default_title).strip() or default_title
    answer_mode = str(raw_block.get("answer_mode") or "bullets").strip() or "bullets"
    intro = str(raw_block.get("intro") or "").strip()
    items = _normalize_str_list(raw_block.get("items"), 20)
    closing = str(raw_block.get("closing") or "").strip()
    if not intro and not items and not closing:
        return None
    return {
        "title": title,
        "answer_mode": answer_mode,
        "intro": intro,
        "items": items,
        "closing": closing,
    }


def _format_sections_for_direct_answer(report: Dict[str, Any]) -> str:
    sections = report.get("sections") if isinstance(report, dict) else []
    if not isinstance(sections, list):
        return "(최종 섹션 없음)"

    blocks = []
    for idx, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        if str(section.get("section_id") or "").strip() == "accepted-case-comparison":
            continue

        title = str(section.get("title") or f"섹션 {idx}").strip()
        narrative = str(section.get("section_narrative") or "").strip()
        answer = str(section.get("answer") or "").strip()
        criteria = [
            str(item.get("text") or "").strip()
            for item in (section.get("evaluation_criteria") or [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        assessments = [
            str(item.get("text") or "").strip()
            for item in (section.get("student_assessment") or [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]

        body = narrative or answer
        if not body:
            merged = criteria[:2] + assessments[:2]
            body = " ".join(item for item in merged if item)

        if not body:
            continue

        blocks.append(
            "\n".join(
                [
                    f"[섹션 {idx}] {title}",
                    _truncate_text(body, 900),
                ]
            )
        )

    return "\n\n".join(blocks) if blocks else "(최종 섹션 없음)"


def _build_final_report_summary(
    *,
    user_message: str,
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
    report: Dict[str, Any],
) -> str:
    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    sections_text = _format_sections_for_direct_answer(report)

    student_profile = report.get("student_profile") if isinstance(report.get("student_profile"), dict) else {}
    profile_lines = []
    if isinstance(student_profile, dict):
        for key in ("headline", "dominant_track", "immediate_priority"):
            value = str(student_profile.get(key) or "").strip()
            if value:
                profile_lines.append(value)

    recommendation_summary = ""
    university_recommendations = (
        report.get("university_recommendations")
        if isinstance(report.get("university_recommendations"), dict)
        else {}
    )
    if isinstance(university_recommendations, dict):
        recommendation_summary = str(university_recommendations.get("summary") or "").strip()

    prompt = "\n\n".join(
        [
            f"[현재 {task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            "[사용자 생기부 요약]",
            _truncate_text(school_record_context, 4500),
            "[학생 평가 프로필 요약]",
            _truncate_text("\n".join(profile_lines), 800) if profile_lines else "(프로필 요약 없음)",
            "[추천 대학 요약]",
            recommendation_summary or "(추천 대학 요약 없음)",
            "[최종 섹션 요약]",
            sections_text,
            (
                "[작업 지시]\n"
                "위의 최종 리포트 전체를 모두 훑고, 맨 앞에 들어갈 총평 summary만 2~4문장으로 작성하세요.\n"
                "참고자료나 대학/합격사례 비교에서 나온 표현을 학생 자체 특성처럼 옮겨 쓰지 말고, 학생 생기부에 직접 드러난 강점과 보완점을 중심으로 요약하세요."
            ),
        ]
    )

    raw_payload = _generate_json_with_gemini(
        system_prompt=FINAL_REPORT_SUMMARY_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=PLANNER_MODEL,
        max_output_tokens=768,
    )
    if isinstance(raw_payload, dict):
        return str(raw_payload.get("summary") or "").strip()
    return ""


def _build_direct_answer_block(
    *,
    user_message: str,
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
    report: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    is_fixed_report = _is_fixed_report_mode(answer_plan)
    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    default_title = _get_direct_answer_title(answer_plan)
    requested_item_count = 0 if is_fixed_report else _extract_requested_item_count(user_message)
    target_item_count = (
        requested_item_count if requested_item_count > 0 else FIXED_REPORT_DIRECT_ANSWER_ITEM_COUNT if is_fixed_report else 0
    )
    sections_text = _format_sections_for_direct_answer(report)
    if is_fixed_report:
        task_instruction = "\n".join(
            [
                "[작업 지시]",
                "분석 섹션보다 먼저 보여줄 '한눈에 보는 진단' 블록만 작성하세요.",
                "이 블록은 질문에 대한 응답이 아니라 정식 리포트 첫 페이지의 요약입니다.",
                f"items는 {target_item_count}개 내외로 작성하고, 각 항목은 강점, 리스크, 전공/대학 적합도, 우선 보완 과제가 고르게 드러나게 쓰세요.",
                "intro는 1~2문장으로 학생부 전체 인상을 요약하되, 바로 위의 최종 총평 summary와 모순되지 않게 쓰세요.",
            ]
        )
    else:
        task_instruction = "\n".join(
            [
                "[작업 지시]",
                "분석 섹션보다 먼저 보여줄 '질문에 대한 바로 답변' 블록만 작성하세요.",
                "반드시 위 최종 섹션들의 맥락과 결론을 따라가며, 그 내용의 압축판처럼 답하세요.",
                "사용자가 개수를 명시했다면 items 개수를 가능한 정확히 맞추고, 각 항목은 질문에 직접 답하는 완성형 문장으로 쓰세요.",
                "개수를 명시하지 않았다면 가장 직접적인 핵심 답을 2~5개 이내로 정리하세요.",
            ]
        )
    prompt = "\n\n".join(
        [
            f"[현재 {task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            f"[명시 요청 개수]\n{target_item_count or 0}",
            "[사용자 생기부 요약]",
            _truncate_text(school_record_context, 5000),
            "[최종 총평]",
            str(report.get("summary") or "").strip() or "(총평 없음)",
            "[최종 섹션 요약]",
            sections_text,
            (
                task_instruction
                + "\n학생 생기부에 직접 드러난 근거를 중심으로 답하고, 참고자료나 합격 사례의 문장을 학생 전략처럼 재서술하지 마세요."
            ),
        ]
    )

    raw_block = _generate_json_with_gemini(
        system_prompt=FIXED_REPORT_DIRECT_ANSWER_SYSTEM_PROMPT if is_fixed_report else DIRECT_ANSWER_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
    )
    normalized = _normalize_direct_answer_block(raw_block or {}, default_title=default_title)
    if normalized:
        normalized["title"] = default_title
        if target_item_count > 0 and normalized.get("items"):
            normalized["items"] = normalized["items"][:target_item_count]
        return normalized

    fallback_items = []
    if target_item_count > 0:
        section_summaries = []
        for section in report.get("sections", []) if isinstance(report, dict) else []:
            if not isinstance(section, dict):
                continue
            if str(section.get("section_id") or "").strip() == "accepted-case-comparison":
                continue
            title = str(section.get("title") or "").strip()
            body = str(section.get("section_narrative") or section.get("answer") or "").strip()
            if title and body:
                section_summaries.append(f"{title}: {_truncate_text(body, 120)}")
        if section_summaries:
            fallback_items = [
                section_summaries[idx % len(section_summaries)]
                for idx in range(target_item_count)
            ]
        else:
            fallback_items = [
                f"요청한 형식에 맞춰 항목 {idx}를 구체적으로 정리해야 합니다."
                for idx in range(1, target_item_count + 1)
            ]
    return {
        "title": default_title,
        "answer_mode": "numbered_list" if fallback_items else "paragraph",
        "intro": (
            "학생부 전체를 학생부종합전형 기준으로 압축해 보면, 현재 서류의 경쟁력과 보완 우선순위가 비교적 분명하게 드러납니다."
            if is_fixed_report
            else str((answer_plan or {}).get("refined_question") or user_message).strip()
        ),
        "items": fallback_items,
        "closing": "",
    }


_SUBJECT_GROUP_DEFS: dict[str, list[str]] = {
    "국어": ["국어", "문학", "화법과작문", "화작", "언어와매체", "언매", "독서", "실용국어", "심화국어"],
    "수학": [
        "수학", "수학I", "수학1", "수학II", "수학2", "수학Ⅰ", "수학Ⅱ",
        "미적분", "확률과통계", "확통", "기하", "실용수학", "경제수학", "인공지능수학",
    ],
    "영어": ["영어", "영어I", "영어1", "영어II", "영어2", "영어Ⅰ", "영어Ⅱ", "영어회화", "영어독해와작문", "실용영어"],
    "과학": [
        "과학", "통합과학", "물리학", "물리학I", "물리학1", "물리학II", "물리학2", "물리학Ⅰ", "물리학Ⅱ", "물리",
        "화학", "화학I", "화학1", "화학II", "화학2", "화학Ⅰ", "화학Ⅱ",
        "생명과학", "생명과학I", "생명과학1", "생명과학II", "생명과학2", "생명과학Ⅰ", "생명과학Ⅱ", "생명", "생1", "생2",
        "지구과학", "지구과학I", "지구과학1", "지구과학II", "지구과학2", "지구과학Ⅰ", "지구과학Ⅱ", "지구", "지1", "지2",
        "과학탐구실험",
    ],
    "사회": [
        "사회", "통합사회", "한국사", "한국지리", "세계지리", "동아시아사", "세계사",
        "경제", "정치와법", "사회문화", "사문", "생활과윤리", "생윤", "윤리와사상", "윤사",
    ],
    "체육": ["체육", "운동과건강", "스포츠생활"],
    "음악": ["음악", "음악연주", "음악감상과비평"],
    "미술": ["미술", "미술창작", "미술감상과비평"],
    "기술가정": ["기술", "가정", "기술가정", "정보", "프로그래밍"],
    "한문": ["한문"],
    "제2외국어": ["일본어", "중국어", "프랑스어", "독일어", "스페인어", "러시아어", "아랍어", "베트남어", "제2외국어"],
}

_SUBJECT_TO_GROUP: dict[str, str] = {}
for _grp, _subjects in _SUBJECT_GROUP_DEFS.items():
    for _subj in _subjects:
        _SUBJECT_TO_GROUP[_subj] = _grp
        _norm = re.sub(r'[\s·ㆍ/()[\]]+', '', _subj)
        if _norm != _subj:
            _SUBJECT_TO_GROUP[_norm] = _grp


_SUBJECT_PREFIX_STRIP = re.compile(r'^(심화|고급|기본|실용|일반)\s*')


def _get_subject_group(area: str, text: str = "") -> str:
    """과목명(area) 또는 세특 본문(text)에서 과목 그룹 추론. 비 교과(창체 등)는 ''."""
    a = (area or "").strip()
    if a in _SUBJECT_TO_GROUP:
        return _SUBJECT_TO_GROUP[a]
    norm = re.sub(r'[\s·ㆍ/()[\]]+', '', a)
    roman_map = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III"}
    for old_r, new_r in roman_map.items():
        norm = norm.replace(old_r, new_r)
    if norm in _SUBJECT_TO_GROUP:
        return _SUBJECT_TO_GROUP[norm]
    for subj, grp in sorted(_SUBJECT_TO_GROUP.items(), key=lambda x: len(x[0]), reverse=True):
        if norm.startswith(re.sub(r'\s', '', subj)):
            return grp
    stripped = _SUBJECT_PREFIX_STRIP.sub('', a).strip()
    if stripped and stripped != a:
        result = _get_subject_group(stripped)
        if result:
            return result
    if a in ("세특", "") and text:
        return _infer_subject_group_from_text(text)
    return ""


def _infer_subject_group_from_text(text: str) -> str:
    """세특 본문 앞부분에서 과목 그룹을 추론 (area가 '세특'으로 불분명할 때)."""
    s = (text or "").strip()[:300]
    m = re.match(r'^([가-힣A-Za-z0-9Ⅰ-Ⅴ\s]{2,16}?)\s*[:：]\s*', s)
    if m:
        label = m.group(1).strip()
        grp = _get_subject_group(label)
        if grp:
            return grp
    _TEXT_KEYWORD_GROUPS = {
        "수학": ["수학적", "함수", "미적분", "방정식", "확률", "통계", "기하학", "벡터", "행렬", "미분", "적분"],
        "과학": ["물리", "화학적", "반응식", "원소", "유전", "세포", "DNA", "지질", "천체", "전자기"],
        "국어": [],
        "영어": [],
        "체육": ["체육", "스포츠", "건강체력", "운동 기능", "체력 측정"],
        "음악": ["음악", "악기", "연주", "악보"],
        "미술": ["미술", "작품", "드로잉", "소묘"],
    }
    first_80 = s[:80]
    for grp, kws in _TEXT_KEYWORD_GROUPS.items():
        if any(kw in first_80 for kw in kws):
            return grp
    return ""


def _score_text_overlap(tokens: list[str], text: str) -> float:
    if not tokens:
        return 0.0
    text_lower = str(text or "").lower()
    if not text_lower.strip():
        return 0.0
    overlap = sum(1 for token in tokens if token in text_lower)
    return overlap / max(len(tokens), 4)


def _extract_grade_scope_from_query(query: str) -> list[str]:
    text = str(query or "")
    mapping = {
        "1": ("1학년", "고1"),
        "2": ("2학년", "고2"),
        "3": ("3학년", "고3"),
    }
    grades = []
    for grade, hints in mapping.items():
        if any(hint in text for hint in hints):
            grades.append(grade)
    return grades


def _extract_record_scope_from_query(query: str) -> list[str]:
    text = str(query or "")
    scopes: list[str] = []
    if any(keyword in text for keyword in ("세특", "과세특", "교과 세특", "과목 세특", "세부능력")):
        scopes.append("세특")
    if any(keyword in text for keyword in ("창체", "창의적체험활동")):
        scopes.append("창체")
    if "행특" in text or "행동특성" in text or "종합의견" in text:
        scopes.append("행특")
    for activity_name in ("자율활동", "동아리활동", "진로활동"):
        if activity_name in text:
            scopes.append(activity_name)
    deduped = []
    seen = set()
    for scope in scopes:
        if scope in seen:
            continue
        seen.add(scope)
        deduped.append(scope)
    return deduped


def _infer_accepted_case_comparison_mode(
    user_message: str,
    answer_plan: Optional[Dict[str, Any]],
) -> str:
    text = " ".join(
        part
        for part in [
            str(user_message or "").strip(),
            str((answer_plan or {}).get("refined_question") or "").strip(),
            " ".join((answer_plan or {}).get("analysis_dimensions") or []),
            " ".join((answer_plan or {}).get("school_record_focus") or []),
        ]
        if str(part).strip()
    )
    grades = _extract_grade_scope_from_query(text)
    scopes = _extract_record_scope_from_query(text)
    if any(keyword in text for keyword in ("학년별", "성장 흐름", "흐름", "변화", "연도별")):
        return "grade_flow_compare"
    if "세특" in scopes:
        return "subject_excerpt_compare"
    if any(scope in scopes for scope in ("창체", "자율활동", "동아리활동", "진로활동")):
        return "activity_story_compare"
    if any(keyword in text for keyword in ("면접", "질문", "예상 질문")):
        return "interview_evidence_compare"
    if any(keyword in text for keyword in ("보완", "부족", "약점", "개선", "아쉬운")):
        return "gap_compare"
    if grades:
        return "grade_flow_compare"
    return "general_compare"


def _build_comparison_axis_label(
    comparison_mode: str,
    grade_scope: list[str],
    record_scope: list[str],
) -> str:
    grade_text = ", ".join(f"{grade}학년" for grade in grade_scope)
    if comparison_mode == "subject_excerpt_compare":
        return f"{grade_text + ' ' if grade_text else ''}세특 직접 비교".strip()
    if comparison_mode == "grade_flow_compare":
        return f"{grade_text + ' ' if grade_text else ''}학년별 흐름 비교".strip()
    if comparison_mode == "activity_story_compare":
        scope_text = ", ".join(record_scope) if record_scope else "창체/활동"
        return f"{grade_text + ' ' if grade_text else ''}{scope_text} 비교".strip()
    if comparison_mode == "interview_evidence_compare":
        return "면접 근거 원문 비교"
    if comparison_mode == "gap_compare":
        return "보완점 중심 원문 비교"
    return "유사 맥락 원문 비교"


def _determine_excerpt_pair_target_count(
    user_message: str,
    comparison_mode: str,
    relevant_count: int,
) -> int:
    text = str(user_message or "")
    if any(keyword in text for keyword in ("전부", "전체", "모두", "최대한")):
        return min(max(relevant_count, ACCEPTED_CASE_MIN_EXCERPT_PAIRS), ACCEPTED_CASE_MAX_EXCERPT_PAIRS)
    if comparison_mode in ("subject_excerpt_compare", "grade_flow_compare"):
        return min(max(relevant_count, ACCEPTED_CASE_MIN_EXCERPT_PAIRS), ACCEPTED_CASE_MAX_EXCERPT_PAIRS)
    if comparison_mode == "interview_evidence_compare":
        return min(max(relevant_count, ACCEPTED_CASE_MIN_EXCERPT_PAIRS), 5)
    return min(max(relevant_count, ACCEPTED_CASE_MIN_EXCERPT_PAIRS), 4)


def _normalize_record_scope_match(scope: str, record_type: str) -> bool:
    if scope == "창체":
        return record_type in {"창체", "자율활동", "동아리활동", "진로활동"}
    if scope == "행특":
        return record_type == "행특"
    if scope == "세특":
        return record_type == "세특"
    return record_type == scope


def _snippet_scope_score(
    snippet: Dict[str, Any],
    *,
    query_tokens: list[str],
    grade_scope: list[str],
    record_scope: list[str],
    comparison_mode: str,
) -> float:
    score = _score_text_overlap(query_tokens, str(snippet.get("text", "")))
    score += _score_text_overlap(query_tokens, str(snippet.get("label", ""))) * 0.6

    grade = str(snippet.get("grade") or "")
    record_type = str(snippet.get("record_type") or "")
    source_kind = str(snippet.get("source_kind") or "")
    text = str(snippet.get("text") or "")

    if grade_scope:
        score += 1.6 if grade in grade_scope else -0.3
    if record_scope:
        matched_scope = any(_normalize_record_scope_match(scope, record_type) for scope in record_scope)
        score += 1.6 if matched_scope else -0.3

    if comparison_mode == "subject_excerpt_compare" and record_type == "세특":
        score += 1.2
    elif comparison_mode == "grade_flow_compare" and grade:
        score += 1.0
    elif comparison_mode == "activity_story_compare" and record_type in {"창체", "자율활동", "동아리활동", "진로활동"}:
        score += 1.2
    elif comparison_mode == "interview_evidence_compare":
        if any(keyword in text for keyword in ("탐구", "발표", "토론", "실험", "프로젝트", "질문", "설명")):
            score += 1.0
    elif comparison_mode == "gap_compare" and source_kind == "comment":
        score += 1.2

    return score


def _rank_scoped_snippets(
    snippets: list[Dict[str, Any]],
    *,
    query_tokens: list[str],
    grade_scope: list[str],
    record_scope: list[str],
    comparison_mode: str,
) -> list[Dict[str, Any]]:
    scored = [
        (
            _snippet_scope_score(
                snippet,
                query_tokens=query_tokens,
                grade_scope=grade_scope,
                record_scope=record_scope,
                comparison_mode=comparison_mode,
            ),
            snippet,
        )
        for snippet in snippets
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [snippet for score, snippet in scored if score > -0.5]


def _select_relevant_user_snippets(
    snippets: list[Dict[str, Any]],
    *,
    query_tokens: list[str],
    grade_scope: list[str],
    record_scope: list[str],
    comparison_mode: str,
    user_message: str,
) -> list[Dict[str, Any]]:
    ranked = _rank_scoped_snippets(
        snippets,
        query_tokens=query_tokens,
        grade_scope=grade_scope,
        record_scope=record_scope,
        comparison_mode=comparison_mode,
    )
    if not ranked:
        return []

    strict = [
        snippet
        for snippet in ranked
        if (not grade_scope or str(snippet.get("grade") or "") in grade_scope)
        and (
            not record_scope
            or any(
                _normalize_record_scope_match(scope, str(snippet.get("record_type") or ""))
                for scope in record_scope
            )
        )
    ]
    base = strict or ranked
    target_count = _determine_excerpt_pair_target_count(user_message, comparison_mode, len(base))
    selected = list(base[:target_count])

    if len(selected) < ACCEPTED_CASE_MIN_EXCERPT_PAIRS:
        for snippet in ranked:
            if snippet in selected:
                continue
            selected.append(snippet)
            if len(selected) >= ACCEPTED_CASE_MIN_EXCERPT_PAIRS:
                break
    return selected[:target_count]


def _infer_accepted_record_type(area: str, source_kind: str) -> str:
    if source_kind == "comment":
        return "코멘트"
    normalized_area = str(area or "").strip()
    if normalized_area in {"자율활동", "동아리활동", "진로활동"}:
        return normalized_area
    if normalized_area:
        return "세특"
    return "기타"


def _build_excerpt_pairs_for_case(
    *,
    case_snippets: list[Dict[str, Any]],
    user_selected_snippets: list[Dict[str, Any]],
    query_tokens: list[str],
    grade_scope: list[str],
    record_scope: list[str],
    comparison_mode: str,
    target_count: int,
) -> list[Dict[str, Any]]:
    """사용자 스니펫과 동일한 과목/기록유형의 합격자 스니펫을 직접 매칭."""
    if not case_snippets or not user_selected_snippets:
        return []

    excerpt_pairs: list[Dict[str, Any]] = []
    used_case_indexes: set[int] = set()

    for pair_idx, user_snippet in enumerate(user_selected_snippets[:target_count], start=1):
        u_rtype = str(user_snippet.get("record_type") or "").strip()
        u_grade = str(user_snippet.get("grade") or "").strip()
        u_area = str(user_snippet.get("area") or "").strip()
        u_group = _get_subject_group(u_area, str(user_snippet.get("text") or ""))

        best_idx: Optional[int] = None
        best_score = float("-inf")

        for idx, cs in enumerate(case_snippets):
            if idx in used_case_indexes:
                continue
            c_rtype = str(cs.get("record_type") or "").strip()
            c_grade = str(cs.get("grade") or "").strip()
            c_area = str(cs.get("area") or "").strip()

            if u_rtype == "세특":
                if c_rtype != "세특":
                    continue
                c_group = _get_subject_group(c_area, str(cs.get("text") or ""))
                if u_group and c_group and c_group != u_group:
                    continue
                score = 0.0
                if u_group and c_group and c_group == u_group:
                    score += 5.0
                if u_grade and c_grade and u_grade == c_grade:
                    score += 2.0
                score += _score_text_overlap(
                    _tokenize_query(str(user_snippet.get("text") or "")),
                    str(cs.get("text") or ""),
                )
            elif u_rtype in ("자율활동", "동아리활동", "진로활동", "창체"):
                if c_rtype not in ("자율활동", "동아리활동", "진로활동", "창체"):
                    continue
                score = 0.0
                if u_rtype == c_rtype:
                    score += 3.0
                if u_grade and c_grade and u_grade == c_grade:
                    score += 2.0
            elif u_rtype == "행특":
                if c_rtype != "행특":
                    continue
                score = 0.0
                if u_grade and c_grade and u_grade == c_grade:
                    score += 2.0
            else:
                score = _score_text_overlap(
                    _tokenize_query(str(user_snippet.get("text") or "")),
                    str(cs.get("text") or ""),
                )

            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            continue

        used_case_indexes.add(best_idx)
        accepted_snippet = case_snippets[best_idx]
        excerpt_pairs.append({
            "pair_id": f"pair-{pair_idx}",
            "user_excerpt_label": str(user_snippet.get("label") or "사용자 발췌").strip(),
            "user_excerpt": str(user_snippet.get("text") or "").strip(),
            "accepted_excerpt_label": str(accepted_snippet.get("label") or "합격자 발췌").strip(),
            "accepted_excerpt": str(accepted_snippet.get("text") or "").strip(),
            "pair_comment": "",
            "_match_score": round(best_score, 4),
        })

    return excerpt_pairs


def _extract_user_school_record_snippets(
    school_record: Dict[str, Any],
    school_record_context: str,
) -> list[Dict[str, Any]]:
    snippets: list[Dict[str, Any]] = []
    forms = school_record.get("forms") if isinstance(school_record, dict) else {}
    forms = forms if isinstance(forms, dict) else {}
    parsed = forms.get("parsedSchoolRecord") or school_record.get("parsedSchoolRecord") or {}
    sections = parsed.get("sections") if isinstance(parsed, dict) else {}
    sections = sections if isinstance(sections, dict) else {}

    academic = sections.get("academicDevelopment") if isinstance(sections, dict) else {}
    academic = academic if isinstance(academic, dict) else {}
    academic_by_grade = academic.get("by_grade") if isinstance(academic, dict) else {}
    academic_by_grade = academic_by_grade if isinstance(academic_by_grade, dict) else {}
    for grade in ("1", "2", "3"):
        for row in academic_by_grade.get(grade) or []:
            if not isinstance(row, dict):
                continue
            subject = str(row.get("subject") or row.get("과목") or "").strip() or "세특"
            note = str(row.get("note") or row.get("내용") or row.get("세특") or "").strip()
            if not note:
                continue
            snippets.append({
                "label": f"{grade}학년 세특 / {subject}",
                "text": note,
                "grade": grade,
                "record_type": "세특",
                "area": subject,
            })

    creative = sections.get("creativeActivity") if isinstance(sections, dict) else {}
    creative = creative if isinstance(creative, dict) else {}
    creative_by_grade = creative.get("by_grade") if isinstance(creative, dict) else {}
    creative_by_grade = creative_by_grade if isinstance(creative_by_grade, dict) else {}
    for grade in ("1", "2", "3"):
        note_block = creative_by_grade.get(grade)
        if not isinstance(note_block, dict):
            continue
        for key, value in note_block.items():
            note = str(value or "").strip()
            if not note:
                continue
            snippets.append({
                "label": f"{grade}학년 창체 / {key}",
                "text": note,
                "grade": grade,
                "record_type": key if key in {"자율활동", "동아리활동", "진로활동"} else "창체",
                "area": key,
            })

    behavior = sections.get("behaviorOpinion") if isinstance(sections, dict) else {}
    behavior = behavior if isinstance(behavior, dict) else {}
    behavior_by_grade = behavior.get("by_grade") if isinstance(behavior, dict) else {}
    behavior_by_grade = behavior_by_grade if isinstance(behavior_by_grade, dict) else {}
    for grade in ("1", "2", "3"):
        opinion = str(behavior_by_grade.get(grade) or "").strip()
        if not opinion:
            continue
        snippets.append({
            "label": f"{grade}학년 행동특성 및 종합의견",
            "text": opinion,
            "grade": grade,
            "record_type": "행특",
            "area": "행동특성 및 종합의견",
        })

    if not snippets and school_record_context.strip():
        for idx, block in enumerate(
            [part.strip() for part in school_record_context.split("\n\n") if part.strip()][1:7],
            start=1,
        ):
            snippets.append({
                "label": f"생기부 원문 {idx}",
                "text": block,
                "grade": "",
                "record_type": "기타",
                "area": "",
            })
    return snippets[:60]


def _extract_accepted_case_snippets(case_id: str, case_data: Dict[str, Any]) -> list[Dict[str, str]]:
    snippets: list[Dict[str, Any]] = []
    for activity in case_data.get("activities") or []:
        if not isinstance(activity, dict):
            continue
        text = str(activity.get("내용") or "").strip()
        if not text:
            continue
        grade = str(activity.get("학년") or "").strip()
        area = str(activity.get("영역") or "").strip()
        display_area = area
        if area == "세특":
            inferred_group = _infer_subject_group_from_text(text)
            if inferred_group:
                display_area = f"세특 / {inferred_group} 계열"
        label = " / ".join(part for part in [f"{grade}학년" if grade else "", display_area] if part)
        snippets.append({
            "case_id": case_id,
            "label": label or "합격자 활동",
            "text": text,
            "grade": grade,
            "record_type": _infer_accepted_record_type(area, "activity"),
            "area": area,
            "source_kind": "activity",
        })
    for comment in case_data.get("comments") or []:
        if not isinstance(comment, dict):
            continue
        text = str(comment.get("내용") or "").strip()
        if not text:
            continue
        label = str(comment.get("구분") or "").strip() or "합격자 코멘트"
        snippets.append({
            "case_id": case_id,
            "label": f"코멘트 / {label}",
            "text": text,
            "grade": "",
            "record_type": "코멘트",
            "area": label,
            "source_kind": "comment",
        })
    return snippets


def _build_accepted_case_candidates(
    *,
    user_message: str,
    school_record: Dict[str, Any],
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    user_snippets = _extract_user_school_record_snippets(school_record, school_record_context)
    if not user_snippets:
        return []

    comparison_mode = _infer_accepted_case_comparison_mode(user_message, answer_plan)
    grade_scope = _extract_grade_scope_from_query(
        " ".join(
            [
                str(user_message or ""),
                str((answer_plan or {}).get("refined_question") or ""),
            ]
        )
    )
    record_scope = _extract_record_scope_from_query(
        " ".join(
            [
                str(user_message or ""),
                " ".join((answer_plan or {}).get("school_record_focus") or []),
            ]
        )
    )
    focus_terms = _extract_school_record_focus_terms(school_record_context, limit=8)
    query_context = " ".join(
        part
        for part in [
            user_message,
            str((answer_plan or {}).get("refined_question") or "").strip(),
            " ".join((answer_plan or {}).get("analysis_dimensions") or []),
            " ".join((answer_plan or {}).get("school_record_focus") or []),
            " ".join(focus_terms),
        ]
        if str(part).strip()
    )
    query_tokens = _tokenize_query(query_context)
    if not query_tokens:
        query_tokens = _tokenize_query(user_message)

    user_selected_snippets = _select_relevant_user_snippets(
        user_snippets,
        query_tokens=query_tokens,
        grade_scope=grade_scope,
        record_scope=record_scope,
        comparison_mode=comparison_mode,
        user_message=user_message,
    )
    if not user_selected_snippets:
        return []

    target_count = _determine_excerpt_pair_target_count(
        user_message,
        comparison_mode,
        len(user_selected_snippets),
    )

    ranked_cases: list[tuple[float, str, Dict[str, Any], list[Dict[str, str]]]] = []
    for case_id, case_data in HARDCODED_SCHOOL_RECORDS.items():
        if not isinstance(case_data, dict):
            continue
        personal_info = case_data.get("personal_info") or {}
        snippets = _extract_accepted_case_snippets(case_id, case_data)
        searchable_text = " ".join(
            [
                str(personal_info.get("대상") or ""),
                str(personal_info.get("주요_특징") or ""),
                str(personal_info.get("총평") or ""),
                " ".join(snippet.get("text", "") for snippet in snippets[:12]),
            ]
        )
        case_score = _score_text_overlap(query_tokens, searchable_text)
        if focus_terms:
            case_score += _score_text_overlap(focus_terms, searchable_text) * 0.5
        if case_score <= 0:
            continue
        ranked_cases.append((case_score, case_id, case_data, snippets))

    ranked_cases.sort(key=lambda item: item[0], reverse=True)
    selected_cases = ranked_cases[: max(ACCEPTED_CASE_MAX_CANDIDATES * 2, 6)]
    candidates: list[Dict[str, Any]] = []

    def _process_one_case(entry):
        _, case_id, case_data, case_snippets_local = entry
        excerpt_pairs = _build_excerpt_pairs_for_case(
            case_snippets=case_snippets_local,
            user_selected_snippets=user_selected_snippets,
            query_tokens=query_tokens,
            grade_scope=grade_scope,
            record_scope=record_scope,
            comparison_mode=comparison_mode,
            target_count=target_count,
        )
        if not excerpt_pairs:
            return None

        personal_info = case_data.get("personal_info") or {}
        case_label = str(personal_info.get("대상") or case_id).strip() or case_id
        pair_score = sum(float(pair.get("_match_score", 0.0) or 0.0) for pair in excerpt_pairs) / max(len(excerpt_pairs), 1)
        return {
            "case_id": case_id,
            "label": case_label,
            "comparison_mode": comparison_mode,
            "comparison_axis": _build_comparison_axis_label(comparison_mode, grade_scope, record_scope),
            "_candidate_score": pair_score + _score_text_overlap(query_tokens, case_label),
            "meta": {
                "주요_특징": str(personal_info.get("주요_특징") or "").strip(),
                "총평": str(personal_info.get("총평") or "").strip(),
            },
            "excerpt_pairs": [
                {
                    key: value
                    for key, value in pair.items()
                    if key != "_match_score"
                }
                for pair in excerpt_pairs
            ],
            "accepted_comment_excerpt": _truncate_text(
                next(
                    (
                        snippet.get("text", "")
                        for snippet in case_snippets_local
                        if str(snippet.get("label", "")).startswith("코멘트 / ")
                    ),
                    str(personal_info.get("총평") or ""),
                ),
                500,
            ),
        }

    with ThreadPoolExecutor(max_workers=min(len(selected_cases), 4)) as executor:
        futures = {executor.submit(_process_one_case, entry): entry for entry in selected_cases}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    candidates.append(result)
            except Exception:
                pass

    candidates.sort(key=lambda item: float(item.get("_candidate_score", 0.0) or 0.0), reverse=True)
    return candidates[:ACCEPTED_CASE_MAX_CANDIDATES]


def _normalize_accepted_case_comparison_section(
    raw_section: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    comparison_cards = []
    for idx, card in enumerate(raw_section.get("comparison_cards") or [], start=1):
        if not isinstance(card, dict):
            continue
        label = str(card.get("label") or "").strip()
        excerpt_pairs = []
        for pair_idx, pair in enumerate(card.get("excerpt_pairs") or [], start=1):
            if not isinstance(pair, dict):
                continue
            user_excerpt = str(pair.get("user_excerpt") or "").strip()
            accepted_excerpt = str(pair.get("accepted_excerpt") or "").strip()
            if not user_excerpt or not accepted_excerpt:
                continue
            excerpt_pairs.append(
                {
                    "pair_id": str(pair.get("pair_id") or f"pair-{pair_idx}").strip() or f"pair-{pair_idx}",
                    "user_excerpt_label": str(pair.get("user_excerpt_label") or "사용자 발췌").strip(),
                    "user_excerpt": user_excerpt,
                    "accepted_excerpt_label": str(pair.get("accepted_excerpt_label") or "합격자 발췌").strip(),
                    "accepted_excerpt": accepted_excerpt,
                    "pair_comment": str(pair.get("pair_comment") or "").strip(),
                }
            )
        if not label or not excerpt_pairs:
            continue
        comparison_cards.append(
            {
                "card_id": f"accepted-case-card-{idx}",
                "case_id": str(card.get("case_id") or "").strip(),
                "label": label,
                "match_reason": str(card.get("match_reason") or "").strip(),
                "comparison_axis": str(card.get("comparison_axis") or "").strip(),
                "excerpt_pairs": excerpt_pairs,
                "good_points": _normalize_str_list(card.get("good_points"), 3),
                "gaps": _normalize_str_list(card.get("gaps"), 3),
                "action_tips": _normalize_str_list(card.get("action_tips"), 3),
            }
        )

    if not comparison_cards:
        return None

    section_narrative = str(raw_section.get("section_narrative") or "").strip()
    if not section_narrative:
        section_narrative = "현재 질문의 맥락에 맞춰, 사용자 생기부와 가장 참고 가치가 높은 합격자 생기부 원문을 직접 비교했습니다."

    return {
        "section_id": "accepted-case-comparison",
        "title": str(raw_section.get("title") or "유사 합격자 비교").strip() or "유사 합격자 비교",
        "comparison_focus": str(raw_section.get("comparison_focus") or "").strip(),
        "section_narrative": section_narrative,
        "comparison_cards": comparison_cards,
        "evaluation_criteria": [],
        "student_assessment": [],
        "answer": "",
        "criteria_evidence_refs": [],
        "school_record_evidence_refs": [],
    }


def _build_accepted_case_comparison_section(
    *,
    user_message: str,
    school_record: Dict[str, Any],
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    candidates = _build_accepted_case_candidates(
        user_message=user_message,
        school_record=school_record,
        school_record_context=school_record_context,
        answer_plan=answer_plan,
    )
    if not candidates:
        return None

    pair_lookup: Dict[tuple[str, str], Dict[str, str]] = {}
    prompt_candidates = []
    for candidate in candidates:
        case_id = str(candidate.get("case_id") or "").strip()
        compact_pairs = []
        for pair in candidate.get("excerpt_pairs") or []:
            if not isinstance(pair, dict):
                continue
            pair_id = str(pair.get("pair_id") or "").strip()
            if case_id and pair_id:
                pair_lookup[(case_id, pair_id)] = {
                    "user_excerpt": str(pair.get("user_excerpt") or "").strip(),
                    "accepted_excerpt": str(pair.get("accepted_excerpt") or "").strip(),
                }
            compact_pairs.append(
                {
                    **pair,
                    "user_excerpt": _truncate_text(str(pair.get("user_excerpt") or ""), 900),
                    "accepted_excerpt": _truncate_text(str(pair.get("accepted_excerpt") or ""), 900),
                }
            )
        prompt_candidates.append(
            {
                **candidate,
                "excerpt_pairs": compact_pairs,
            }
        )

    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    prompt = "\n\n".join(
        [
            f"[현재 {task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            "[사용자 생기부 요약]",
            _truncate_text(school_record_context, 5000),
            "[비교 후보]",
            json.dumps(prompt_candidates, ensure_ascii=False, indent=2),
            (
                "[작업 지시]\n"
                "제공된 후보를 바탕으로 마지막 섹션 '유사 합격자 비교'를 작성하세요.\n"
                "사용자 질문의 맥락을 반영해 comparison_focus를 먼저 정하고, 2~3개의 comparison_cards를 골라 구체적으로 비교하세요.\n"
                "각 comparison_card에는 comparison_axis와 excerpt_pairs를 포함해야 하며, excerpt_pairs는 최소 3개 이상 사용하세요.\n"
                "반드시 사용자 원문과 합격자 원문을 가능한 한 전체 문단 단위로 그대로 보여주세요. 중간 축약은 꼭 필요한 경우가 아니면 하지 마세요. "
                "각 excerpt_pair의 pair_comment(해설)는 2~4문장으로 자세히 작성하세요: 두 원문의 구체적 차이, 합격자 쪽이 강한 이유, 사용자가 보완할 수 있는 점을 구체적으로 서술하되, "
                "합격자의 전공이 사용자와 다를 수 있으므로 전공 자체의 차이를 지적하는 데 그치지 말고, 합격자 생기부의 구조, 흐름, 학문적 유기성, 교과-활동-심화의 연결 방식을 사용자가 자신의 질문 맥락에서 어떻게 배워와야 하는지 설명하세요. "
                "즉 '무슨 전공을 했는가'보다 '어떻게 기록을 연결하고 심화했는가'를 중심으로 서술하고, 카드 마지막에 좋은 점/차이점/보완점을 분리해 설명하세요."
            ),
        ]
    )

    raw_section = _generate_json_with_gemini(
        system_prompt=ACCEPTED_CASE_COMPARISON_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=ACCEPTED_CASE_MAX_OUTPUT_TOKENS,
    )
    if isinstance(raw_section, dict):
        normalized = _normalize_accepted_case_comparison_section(raw_section)
        if normalized:
            for card in normalized.get("comparison_cards") or []:
                if not isinstance(card, dict):
                    continue
                case_id = str(card.get("case_id") or "").strip()
                for pair in card.get("excerpt_pairs") or []:
                    if not isinstance(pair, dict):
                        continue
                    pair_id = str(pair.get("pair_id") or "").strip()
                    original_pair = pair_lookup.get((case_id, pair_id))
                    if original_pair:
                        pair["user_excerpt"] = original_pair.get("user_excerpt", pair.get("user_excerpt", ""))
                        pair["accepted_excerpt"] = original_pair.get(
                            "accepted_excerpt",
                            pair.get("accepted_excerpt", ""),
                        )
            return normalized

    fallback_cards = []
    for idx, candidate in enumerate(candidates[:2], start=1):
        fallback_cards.append(
            {
                "card_id": f"accepted-case-card-{idx}",
                "case_id": candidate.get("case_id", ""),
                "label": candidate.get("label", ""),
                "match_reason": candidate.get("meta", {}).get("주요_특징", ""),
                "comparison_axis": candidate.get("comparison_axis", ""),
                "excerpt_pairs": candidate.get("excerpt_pairs", []),
                "good_points": [],
                "gaps": [],
                "action_tips": [],
            }
        )

    if not fallback_cards:
        return None

    return {
        "section_id": "accepted-case-comparison",
        "title": "유사 합격자 비교",
        "comparison_focus": str((answer_plan or {}).get("question_type") or "").strip(),
        "section_narrative": "현재 질문의 맥락에 맞춰, 사용자 생기부와 가장 참고 가치가 높은 합격자 생기부 원문을 직접 비교했습니다.",
        "comparison_cards": fallback_cards,
        "evaluation_criteria": [],
        "student_assessment": [],
        "answer": "",
        "criteria_evidence_refs": [],
        "school_record_evidence_refs": [],
    }


def _extract_section_evidence(
    *,
    user_message: str,
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
    section_outline: list[Dict[str, str]],
    sources_text: str,
) -> Dict[str, Dict[str, Any]]:
    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    prompt = "\n\n".join(
        [
            f"[{task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            "[섹션 목록]",
            "\n".join(f"- {section['section_id']}: {section['title']}" for section in section_outline),
            "[학교생활기록부 컨텍스트]",
            _truncate_text(school_record_context, SCHOOL_RECORD_EVIDENCE_MAX_CHARS),
            "[참고자료 후보]",
            sources_text,
            (
                "[작업 지시]\n"
                "각 섹션마다 학교생활기록부에서 핵심 근거를 뽑고, 가장 관련 있는 source_id를 고르세요.\n"
                "답변은 쓰지 말고 근거만 JSON으로 출력하세요."
            ),
        ]
    )

    result = _generate_json_with_gemini(
        system_prompt=SECTION_EVIDENCE_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=PLANNER_MODEL,
        max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
    ) or {}

    normalized: Dict[str, Dict[str, Any]] = {}
    sections = result.get("sections")
    if not isinstance(sections, list):
        return normalized

    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "").strip()
        if not section_id:
            continue
        school_record_evidence = []
        raw_evidence = section.get("school_record_evidence")
        if isinstance(raw_evidence, list):
            for item in raw_evidence[:6]:
                if not isinstance(item, dict):
                    continue
                quote = str(item.get("quote") or "").strip()
                interpretation = str(item.get("interpretation") or "").strip()
                label = str(item.get("label") or "").strip()
                if not quote:
                    continue
                school_record_evidence.append(
                    {
                        "label": label,
                        "quote": quote,
                        "interpretation": interpretation,
                    }
                )
        preferred_source_ids = _normalize_str_list(section.get("preferred_source_ids"), REPORT_MAX_SOURCE_COUNT)
        normalized[section_id] = {
            "school_record_evidence": school_record_evidence,
            "preferred_source_ids": preferred_source_ids,
        }
    return normalized


def _write_section_report(
    *,
    user_message: str,
    answer_plan: Optional[Dict[str, Any]],
    section: Dict[str, str],
    section_evidence: Dict[str, Any],
    source_lookup: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    preferred_source_ids = [
        source_id for source_id in section_evidence.get("preferred_source_ids", []) if source_id in source_lookup
    ]
    if not preferred_source_ids:
        preferred_source_ids = list(source_lookup.keys())[:3]

    school_record_evidence = section_evidence.get("school_record_evidence", []) or []
    school_evidence_text = "\n".join(
        [
            f"- [{idx}] {item.get('label', '생기부 근거')}: {item.get('quote', '')} / 해석: {item.get('interpretation', '')}"
            for idx, item in enumerate(school_record_evidence, start=1)
        ]
    ) or "(추출된 생기부 근거 없음)"

    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    prompt = "\n\n".join(
        [
            f"[{task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            f"[작성할 섹션]\n{section.get('section_id')}: {section.get('title')}",
            "[생기부 핵심 근거]",
            school_evidence_text,
            "[이 섹션에서 사용할 참고자료]",
            _format_source_subset(source_lookup, preferred_source_ids),
            (
                "[작성 지시]\n"
                "이 섹션만 깊이 있게 작성하세요.\n"
                "평가기준(evaluation_criteria)은 2~4개 작성하고, 각 항목은 source_refs를 포함해야 합니다.\n"
                "학생 적용 판단(student_assessment)은 2~4개 작성하고, 각 항목은 school_record_ref_indexes를 포함해야 합니다.\n"
                "answer는 구체적이고 풍부하게 작성하세요.\n"
                "다만 다른 섹션에도 그대로 들어갈 수 있는 일반적인 설명은 줄이고, 이 섹션 제목에서만 다뤄야 할 포인트를 중심으로 쓰세요.\n"
                "answer의 앞부분에서는 먼저 이 섹션의 평가기준이 왜 중요한지, 왜 면접/학종에서 의미가 큰지를 설명하고, 그다음 학생 사례와 강점을 연결하세요.\n"
                "아래 생기부 핵심 근거에 있는 원문 표현, 과목명, 활동명, 탐구 주제를 되도록 직접 다시 호출해 학생 맞춤형으로 쓰세요.\n"
                "student_assessment와 answer는 반드시 생기부 근거 번호를 실제로 참조한 해석처럼 읽혀야 하며, 추상적인 일반론만 반복하면 안 됩니다."
            ),
        ]
    )

    raw_section = _generate_json_with_gemini(
        system_prompt=SECTION_WRITER_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_WRITER_MODEL,
        max_output_tokens=REPORT_SECTION_MAX_OUTPUT_TOKENS,
    )
    if not isinstance(raw_section, dict):
        return None
    raw_section["section_id"] = section.get("section_id")
    raw_section["title"] = str(raw_section.get("title") or section.get("title") or "").strip()
    return raw_section


def _review_structured_report(
    *,
    raw_report: Dict[str, Any],
    user_message: str,
    answer_plan: Optional[Dict[str, Any]],
    school_record_context: str,
    source_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    task_label = _get_generation_task_label(answer_plan)
    task_text = _get_generation_task_text(user_message, answer_plan)
    prompt = "\n\n".join(
        [
            f"[{task_label}]",
            task_text,
            "[답변 설계]",
            _format_answer_plan(answer_plan) or "(설계 정보 없음)",
            "[학교생활기록부 컨텍스트 요약]",
            _truncate_text(school_record_context, 9000),
            "[참고자료 목록]",
            _format_source_subset(source_lookup, list(source_lookup.keys())),
            "[현재 리포트(JSON)]",
            json.dumps(raw_report, ensure_ascii=False, indent=2),
            (
                "[리뷰 지시]\n"
                "현재 리포트를 더 풍부하고 전문적으로 보강하세요.\n"
                "section_id/title/evidence.source_id 연결은 유지하고, summary와 각 섹션 answer를 더 충실하게 만드세요.\n"
                "평가기준(evaluation_criteria)과 학생 적용 판단(student_assessment)의 구조는 유지하세요.\n"
                "섹션 간에 중복되는 설명이 많다면 반복 문장을 줄이고, 각 섹션의 역할이 분명해지도록 차별화하세요."
            ),
        ]
    )

    reviewed = _generate_json_with_gemini(
        system_prompt=REPORT_REVIEW_SYSTEM_PROMPT,
        user_prompt=prompt,
        model_name=REPORT_REVIEWER_MODEL,
        max_output_tokens=REPORT_REVIEW_MAX_OUTPUT_TOKENS,
    )
    return reviewed if isinstance(reviewed, dict) else raw_report


def _build_structured_report(
    *,
    user_message: str,
    school_record: Dict[str, Any],
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]],
    sources_meta: list[Dict[str, Any]],
    user_metadata: Optional[Dict[str, Any]] = None,
    user_grade_summary: Optional[Dict[str, Any]] = None,
    matching_summary: str = "",
    on_section_completed: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
) -> Optional[Dict[str, Any]]:
    sources_text, source_lookup = _prepare_report_sources(sources_meta)
    section_outline = _build_section_outline(answer_plan)
    section_evidence_map = _extract_section_evidence(
        user_message=user_message,
        school_record_context=school_record_context,
        answer_plan=answer_plan,
        section_outline=section_outline,
        sources_text=sources_text,
    )

    indexed_sections = list(enumerate(section_outline))
    max_workers = min(REPORT_SECTION_MAX_WORKERS, len(indexed_sections))
    raw_sections_by_index: Dict[int, Dict[str, Any]] = {}

    if max_workers <= 1:
        for section_index, section in indexed_sections:
            section_result = _write_section_report(
                user_message=user_message,
                answer_plan=answer_plan,
                section=section,
                section_evidence=section_evidence_map.get(section["section_id"], {}),
                source_lookup=source_lookup,
            )
            if section_result:
                raw_sections_by_index[section_index] = section_result
                if on_section_completed:
                    on_section_completed(
                        _build_section_stream_payload(
                            section_result=section_result,
                            section_index=section_index,
                            total_sections=len(indexed_sections),
                        ),
                        section_index,
                        len(indexed_sections),
                    )
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    _write_section_report,
                    user_message=user_message,
                    answer_plan=answer_plan,
                    section=section,
                    section_evidence=section_evidence_map.get(section["section_id"], {}),
                    source_lookup=source_lookup,
                ): section_index
                for section_index, section in indexed_sections
            }
            for future in as_completed(future_map):
                section_index = future_map[future]
                try:
                    section_result = future.result()
                except Exception as e:
                    print(f"⚠️ [deep_chat] 섹션 작성 실패(section-{section_index + 1}): {e}")
                    continue
                if section_result:
                    raw_sections_by_index[section_index] = section_result
                    if on_section_completed:
                        on_section_completed(
                            _build_section_stream_payload(
                                section_result=section_result,
                                section_index=section_index,
                                total_sections=len(indexed_sections),
                            ),
                            section_index,
                            len(indexed_sections),
                        )

    raw_sections = [
        raw_sections_by_index[idx]
        for idx in sorted(raw_sections_by_index.keys())
    ]

    if not raw_sections:
        return None

    initial_report = {
        "report_title": _get_report_title(answer_plan),
        "summary": "",
        "sections": raw_sections,
    }
    raw_report = (
        initial_report
        if _is_fixed_report_mode(answer_plan)
        else _review_structured_report(
            raw_report=initial_report,
            user_message=user_message,
            answer_plan=answer_plan,
            school_record_context=school_record_context,
            source_lookup=source_lookup,
        )
    )
    report = _normalize_structured_report(
        raw_report,
        answer_plan=answer_plan,
        source_lookup=source_lookup,
        section_evidence_map=section_evidence_map,
    )
    if not report:
        return None

    student_profile = None
    comparison_section = None
    if _is_fixed_report_mode(answer_plan):
        with ThreadPoolExecutor(max_workers=REPORT_POST_PROCESS_MAX_WORKERS) as executor:
            future_map = {
                executor.submit(
                    _build_student_profile_summary,
                    school_record_context=school_record_context,
                    answer_plan=answer_plan,
                ): "student_profile",
                executor.submit(
                    _build_accepted_case_comparison_section,
                    user_message=user_message,
                    school_record=school_record,
                    school_record_context=school_record_context,
                    answer_plan=answer_plan,
                ): "comparison_section",
            }
            for future in as_completed(future_map):
                task_name = future_map[future]
                try:
                    result = future.result()
                except Exception as error:
                    print(f"⚠️ [deep_chat] 후처리 병렬 작업 실패({task_name}): {error}")
                    result = None
                if task_name == "student_profile":
                    student_profile = result if isinstance(result, dict) else None
                elif task_name == "comparison_section":
                    comparison_section = result if isinstance(result, dict) else None

        if student_profile:
            report["student_profile"] = student_profile
        if isinstance(user_grade_summary, dict) and user_grade_summary:
            report["grade_summary"] = user_grade_summary
    else:
        comparison_section = _build_accepted_case_comparison_section(
            user_message=user_message,
            school_record=school_record,
            school_record_context=school_record_context,
            answer_plan=answer_plan,
        )
    if comparison_section:
        report["sections"].append(comparison_section)
    if _is_fixed_report_mode(answer_plan):
        three_page_report = None
        final_summary = ""
        university_recommendations = None
        university_profiles: list[Dict[str, Any]] = []
        direct_answer = None
        with ThreadPoolExecutor(max_workers=REPORT_POST_PROCESS_MAX_WORKERS + 1) as executor:
            three_page_future = executor.submit(
                _build_three_page_report,
                report=report,
                school_record=school_record,
                school_record_context=school_record_context,
                student_profile=student_profile,
                user_metadata=user_metadata,
                user_grade_summary=user_grade_summary,
            )
            final_summary_future = executor.submit(
                _build_final_report_summary,
                user_message=user_message,
                school_record_context=school_record_context,
                answer_plan=answer_plan,
                report=report,
            )
            uni_rec_future = executor.submit(
                _build_university_recommendation_summary,
                school_record=school_record,
                school_record_context=school_record_context,
                answer_plan=answer_plan,
                student_profile=student_profile,
                user_grade_summary=user_grade_summary,
                matching_summary=matching_summary,
            )

            def _direct_answer_after_summary():
                summary_result = final_summary_future.result()
                summary_str = str(summary_result or "").strip()
                report_for_da = {**report, "summary": summary_str}
                return _build_direct_answer_block(
                    user_message=user_message,
                    school_record_context=school_record_context,
                    answer_plan=answer_plan,
                    report=report_for_da,
                )

            direct_answer_future = executor.submit(_direct_answer_after_summary)

            for future, task_name in [
                (three_page_future, "three_page_report"),
                (final_summary_future, "final_summary"),
                (uni_rec_future, "university_recommendations"),
                (direct_answer_future, "direct_answer"),
            ]:
                try:
                    result = future.result()
                except Exception as error:
                    print(f"⚠️ [deep_chat] 후처리 병렬 작업 실패({task_name}): {error}")
                    result = None
                if task_name == "three_page_report":
                    three_page_report = result if isinstance(result, dict) else None
                elif task_name == "final_summary":
                    final_summary = str(result or "").strip()
                elif task_name == "university_recommendations":
                    if isinstance(result, tuple) and len(result) == 2:
                        university_recommendations, university_profiles = result
                elif task_name == "direct_answer":
                    direct_answer = result if isinstance(result, dict) else None
        if university_profiles:
            report["university_profiles"] = university_profiles
        if university_recommendations:
            report["university_recommendations"] = university_recommendations
        if three_page_report:
            report["three_page_report"] = three_page_report
        if final_summary:
            report["summary"] = final_summary
        if direct_answer:
            report["direct_answer"] = direct_answer
    else:
        final_summary = _build_final_report_summary(
            user_message=user_message,
            school_record_context=school_record_context,
            answer_plan=answer_plan,
            report=report,
        )
        if final_summary:
            report["summary"] = final_summary
        direct_answer = _build_direct_answer_block(
            user_message=user_message,
            school_record_context=school_record_context,
            answer_plan=answer_plan,
            report=report,
        )
        if direct_answer:
            report["direct_answer"] = direct_answer
    report["plain_text"] = _build_plain_text_from_report(report)
    return report


def _retrieve_academic_rag_rows(
    query: str,
    match_count: int = 3,
    context_window: int = 1,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """academic_contents에서 검색된 최종 행과 선택 행 반환."""
    try:
        from routers.academic_contents import _embed_query
        query_emb = _embed_query(query)
    except Exception as e:
        print(f"⚠️ [deep_chat] RAG 쿼리 임베딩 실패: {e}")
        return [], []

    try:
        client = supabase_service.get_admin_client()
        candidate_count = max(match_count * 3, 8)
        result = client.rpc(
            "match_academic_contents",
            {
                "query_embedding": query_emb,
                "match_count": candidate_count,
                "context_window": context_window,
            },
        ).execute()

        rows = result.data or []

        if not rows:
            print("ℹ️ [deep_chat] RPC 결과 없음 → Python 폴백 검색 시도")
            rows = _fallback_search(query_emb, candidate_count, context_window)

        if not rows:
            return [], []

        selected_rows = _rerank_rows(rows, query, match_count)
        final_rows = _collect_context_rows(rows, selected_rows, context_window)
        return final_rows, selected_rows
    except Exception as e:
        print(f"⚠️ [deep_chat] RAG 검색 실패(무시): {e}")
        return [], []


def _search_academic_rag(query: str, match_count: int = 3, context_window: int = 1) -> tuple[str, list]:
    """academic_contents에서 유사도 검색 + 인접 청크를 가져와 (텍스트, 메타데이터) 반환."""
    final_rows, selected_rows = _retrieve_academic_rag_rows(
        query=query,
        match_count=match_count,
        context_window=context_window,
    )
    if not final_rows:
        return "", []
    return _build_rag_context(final_rows), _build_sources_meta(selected_rows)


def _build_gemini_contents(
    history: List[Dict[str, str]],
    user_message: str,
    school_record_context: str,
    answer_plan: Optional[Dict[str, Any]] = None,
    rag_context: str = "",
) -> list:
    """Gemini API에 보낼 contents 배열 구성."""
    contents = []

    context_msg = (
        "아래는 사용자가 연동한 학교생활기록부 데이터입니다. "
        "이 데이터를 기반으로 분석해 주세요.\n\n"
        f"{school_record_context}"
    )
    if answer_plan:
        context_msg += (
            "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "아래는 현재 질문을 더 정확히 답하기 위해 재구조화한 분석 계획입니다. "
            "이 계획을 따라 먼저 생기부를 진단하고, 그다음 참고자료를 보조적으로 활용하세요.\n\n"
            f"{_format_answer_plan(answer_plan)}"
    )
    if rag_context:
        context_msg += (
            "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "아래는 분석에 참고할 수 있는 학술·입시 자료입니다:\n\n"
            f"{rag_context}"
        )
    contents.append({"role": "user", "parts": [{"text": context_msg}]})
    contents.append({
        "role": "model",
        "parts": [{"text": "네, 생기부 데이터와 참고자료를 확인했습니다. 무엇이든 분석해 드리겠습니다."}],
    })

    for msg in history[-20:]:
        role = "user" if msg.get("role") == "user" else "model"
        text = msg.get("content", "")
        if text.strip():
            contents.append({"role": role, "parts": [{"text": text}]})

    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


def _get_gemini_model():
    """google.generativeai 모델 인스턴스 반환."""
    genai = _configure_gemini()

    return genai.GenerativeModel(
        model_name=DEEP_CHAT_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 8192,
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok", "model": DEEP_CHAT_MODEL}


def _prepare_deep_chat_generation_context(
    *,
    message: str,
    history: List[Dict[str, str]],
    school_record: Dict[str, Any],
    school_record_context: str,
) -> Dict[str, Any]:
    initial_final_rows, initial_selected_rows = _retrieve_reference_rag_rows(
        message,
        school_record_context=school_record_context,
    )
    initial_sources_meta = _build_sources_meta(initial_selected_rows)

    answer_plan = _build_answer_plan(
        query=message,
        history=history,
        school_record=school_record,
        school_record_context=school_record_context,
        initial_sources_meta=initial_sources_meta,
    )

    refined_query = (
        str(answer_plan.get("refined_question") or "").strip() or message.strip()
    )
    final_rows = initial_final_rows
    selected_rows = initial_selected_rows

    if refined_query and refined_query != message.strip():
        refined_final_rows, refined_selected_rows = _retrieve_reference_rag_rows(
            refined_query,
            school_record_context=school_record_context,
        )
        if refined_selected_rows:
            final_rows = refined_final_rows
            selected_rows = refined_selected_rows

    rag_context = _build_rag_context(final_rows) if final_rows else ""
    sources_meta = _build_sources_meta(selected_rows)
    contents = _build_gemini_contents(
        history,
        message,
        school_record_context,
        answer_plan,
        rag_context,
    )

    return {
        "answer_plan": answer_plan,
        "sources_meta": sources_meta,
        "contents": contents,
    }


@router.post("/report")
async def generate_deep_chat_report(
    request: DeepChatReportRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """연동 생기부 기반 종합 리포트 생성."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)

    if auth_failed or not user:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다. 로그인 후 다시 시도해 주세요.",
        )

    user_id = user["user_id"]
    school_record = await supabase_service.get_user_profile_school_record(user_id)
    school_record_dict = dict(school_record or {})
    school_record_context = build_school_record_report_context_text(school_record_dict)

    if not school_record_context or len(school_record_context.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail="연동된 생기부 데이터가 없습니다. 먼저 생기부를 연동해 주세요.",
        )

    async def _safe_matching_summary():
        try:
            return await ensure_matching_summary(user_id, school_record_dict)
        except Exception as error:
            print(f"⚠️ [deep_chat] matchingSummary 생성 실패(무시): {error}")
            return ""

    generation_context, user_metadata, matching_summary = await asyncio.gather(
        asyncio.to_thread(
            lambda: _prepare_fixed_report_generation_context(
                school_record_context=school_record_context,
            )
        ),
        supabase_service.get_user_profile_metadata(user_id),
        _safe_matching_summary(),
    )
    user_grade_summary = _extract_user_grade_summary(user_metadata)
    report_brief = _get_generation_task_text(
        str(request.message or "").strip(),
        generation_context["answer_plan"],
    )
    structured_report = _build_structured_report(
        user_message=report_brief,
        school_record=school_record_dict,
        school_record_context=school_record_context,
        answer_plan=generation_context["answer_plan"],
        sources_meta=generation_context["sources_meta"],
        user_metadata=user_metadata,
        user_grade_summary=user_grade_summary,
        matching_summary=matching_summary,
    )
    if not structured_report:
        raise HTTPException(
            status_code=500,
            detail="리포트 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        )

    return {
        "report": structured_report,
        "sources": generation_context["sources_meta"],
    }


def generate_deep_school_record_stream(
    message: str,
    history: List[Dict[str, str]],
    school_record: Dict[str, Any],
    school_record_context: str,
):
    """기존 채팅 라우터에서도 재사용할 수 있는 생기부 심층 분석 이벤트 generator."""
    def generate():
        start = time.time()
        full_response = ""
        try:
            yield {
                "type": "status",
                "step": "school_record_plan_start",
                "message": "질문을 구조화하고 있습니다.",
            }
            generation_context = _prepare_deep_chat_generation_context(
                message=message,
                history=history,
                school_record=school_record,
                school_record_context=school_record_context,
            )
            answer_plan = generation_context["answer_plan"]
            sources_meta = generation_context["sources_meta"]
            contents = generation_context["contents"]
            section_outline = _build_section_outline(answer_plan)

            yield {
                "type": "status",
                "step": "school_record_plan_complete",
                "message": "구조화된 질문과 답변 계획을 정리했습니다.",
                "detail": {
                    "refined_question": str((answer_plan or {}).get("refined_question") or "").strip(),
                    "section_count": len(section_outline),
                    "source_count": len(sources_meta),
                },
            }
            yield {"type": "sources", "sources": sources_meta}
            if answer_plan:
                yield {"type": "answer_plan", "answer_plan": answer_plan}
            if section_outline:
                yield {"type": "section_outline", "sections": section_outline}
                yield {
                    "type": "status",
                    "step": "school_record_sections_start",
                    "message": "섹션별 분석 초안을 작성하고 있습니다.",
                    "detail": {
                        "sections": [
                            {"section_id": item.get("section_id"), "title": item.get("title")}
                            for item in section_outline
                        ]
                    },
                }

            progress_queue: Queue[Dict[str, Any]] = Queue()

            def _on_section_completed(
                section_event: Dict[str, Any],
                section_index: int,
                total_sections: int,
            ) -> None:
                progress_queue.put(section_event)
                progress_queue.put(
                    {
                        "type": "status",
                        "step": "school_record_section_complete",
                        "message": f"{section_index + 1}번째 섹션 초안이 준비되었습니다.",
                        "detail": {
                            "section_index": section_index + 1,
                            "total_sections": total_sections,
                            "title": str((section_event.get("section") or {}).get("title") or "").strip(),
                        },
                    }
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    _build_structured_report,
                    user_message=message,
                    school_record=school_record,
                    school_record_context=school_record_context,
                    answer_plan=answer_plan,
                    sources_meta=sources_meta,
                    on_section_completed=_on_section_completed,
                )

                while True:
                    try:
                        yield progress_queue.get(timeout=0.1)
                    except Empty:
                        pass

                    if future.done():
                        break

                while not progress_queue.empty():
                    try:
                        yield progress_queue.get_nowait()
                    except Empty:
                        break

                structured_report = future.result()
            if structured_report:
                yield {
                    "type": "status",
                    "step": "school_record_report_finalizing",
                    "message": "최종 요약과 구조화된 답변을 마무리하고 있습니다.",
                }
                full_response = structured_report.get("plain_text", "") or ""
                yield {"type": "report", "report": structured_report}
                elapsed = round((time.time() - start) * 1000)
                yield {
                    "type": "done",
                    "response": full_response,
                    "timing": {"total_ms": elapsed},
                    "model": DEEP_CHAT_MODEL,
                    "sources": sources_meta,
                }
                return

            model = _get_gemini_model()
            response = model.generate_content(contents, stream=True)

            for chunk in response:
                text = chunk.text if hasattr(chunk, "text") else ""
                if text:
                    full_response += text
                    yield {"type": "chunk", "text": text}

            elapsed = round((time.time() - start) * 1000)
            yield {
                "type": "done",
                "response": full_response,
                "timing": {"total_ms": elapsed},
                "model": DEEP_CHAT_MODEL,
                "sources": sources_meta,
            }

        except Exception as e:
            print(f"❌ [deep_chat] 스트리밍 오류: {e}")
            yield {"type": "error", "message": str(e)}

    return generate()


@router.post("/stream")
async def deep_chat_stream(
    request: DeepChatRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """연동 생기부 기반 심층 분석 스트리밍 채팅."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)

    if auth_failed or not user:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다. 로그인 후 다시 시도해 주세요.",
        )

    user_id = user["user_id"]

    school_record = await supabase_service.get_user_profile_school_record(user_id)
    school_record_context = build_school_record_report_context_text(
        dict(school_record or {})
    )

    if not school_record_context or len(school_record_context.strip()) < 30:
        raise HTTPException(
            status_code=400,
            detail="연동된 생기부 데이터가 없습니다. 먼저 생기부를 연동해 주세요.",
        )

    school_record_dict = dict(school_record or {})
    def generate_sse():
        for event in generate_deep_school_record_stream(
            message=request.message,
            history=request.history,
            school_record=school_record_dict,
            school_record_context=school_record_context,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
