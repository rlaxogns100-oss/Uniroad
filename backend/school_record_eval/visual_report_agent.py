"""
시각 보고서 생성 에이전트

- 생기부 원문을 기반으로 4페이지 리포트 JSON 생성
- 1~4페이지를 병렬 생성하여 응답 속도와 일관성을 함께 확보
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from config.config import settings
from config.constants import GEMINI_FLASH_MODEL
from school_record_eval.report_context import build_school_record_report_context_text

_MAX_RETRIES = 2

genai.configure(api_key=settings.GEMINI_API_KEY)

_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

SUBJECT_COLORS = {
    "국어": "#F97316",
    "수학": "#EF4444",
    "영어": "#22C55E",
    "과학": "#EAB308",
    "사회": "#A855F7",
}

_MAIN_SUBJECTS = ["국어", "수학", "영어", "사회", "과학"]

_SUBJECT_GROUP_MAP: Dict[str, str] = {
    "국어": "국어", "수학": "수학", "영어": "영어",
    "한국사": "사회", "사회": "사회", "사회(역사/도)": "사회",
    "사회(역사/도덕포함)": "사회", "도덕": "사회", "역사": "사회",
    "통합사회": "사회", "과학": "과학", "통합과학": "과학",
}


def _extract_grade_data(school_record: Dict[str, Any]) -> Dict[str, Any] | None:
    """parsedSchoolRecord에서 실제 석차등급 데이터를 프로그래밍적으로 추출한다."""
    forms = school_record.get("forms") or school_record
    if not isinstance(forms, dict):
        return None

    parsed = forms.get("parsedSchoolRecord") or {}
    if not isinstance(parsed, dict):
        return None

    sections = parsed.get("sections") or {}
    if not isinstance(sections, dict):
        return None

    academic = sections.get("academicDevelopment") or {}
    if not isinstance(academic, dict):
        return None

    general = academic.get("general_elective") or {}
    if not isinstance(general, dict):
        return None

    main_grade_map: Dict[str, Dict[str, list]] = {s: {} for s in _MAIN_SUBJECTS}
    all_grades_by_sem: Dict[str, list] = {}
    all_semesters: set = set()

    for grade_num in ("1", "2", "3"):
        grade_block = general.get(grade_num)
        if not isinstance(grade_block, dict):
            continue
        rows = grade_block.get("rows")
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            semester = str(row.get("학기", "")).strip()
            if not semester:
                continue

            subject_area = str(row.get("교과", "")).strip()
            rank_str = str(row.get("석차등급", "")).strip()
            if not rank_str or rank_str.lower() in ("", "none", "null", "-"):
                continue

            try:
                rank_grade = int(rank_str)
            except (ValueError, TypeError):
                continue
            if not (1 <= rank_grade <= 9):
                continue

            semester_key = f"{grade_num}-{semester}"
            all_semesters.add(semester_key)

            all_grades_by_sem.setdefault(semester_key, []).append(rank_grade)

            main_subject = _SUBJECT_GROUP_MAP.get(subject_area)
            if not main_subject:
                continue
            main_grade_map[main_subject].setdefault(semester_key, []).append(rank_grade)

    if not all_semesters:
        return None

    sorted_semesters = sorted(
        all_semesters,
        key=lambda s: (int(s.split("-")[0]), int(s.split("-")[1])),
    )

    subjects_with_data: list[str] = []
    values: list[list[int | None]] = []

    for subj in _MAIN_SUBJECTS:
        row_values: list[int | None] = []
        has_any = False
        for sem in sorted_semesters:
            grades_list = main_grade_map[subj].get(sem, [])
            if grades_list:
                row_values.append(round(sum(grades_list) / len(grades_list)))
                has_any = True
            else:
                row_values.append(None)
        if has_any:
            subjects_with_data.append(subj)
            values.append(row_values)

    if not subjects_with_data:
        return None

    avg_all: list[float | None] = []
    avg_main: list[float | None] = []
    for col_idx, sem in enumerate(sorted_semesters):
        all_g = all_grades_by_sem.get(sem, [])
        avg_all.append(round(sum(all_g) / len(all_g), 2) if all_g else None)
        main_g = [values[r][col_idx] for r in range(len(values)) if values[r][col_idx] is not None]
        avg_main.append(round(sum(main_g) / len(main_g), 2) if main_g else None)

    return {
        "subjects": subjects_with_data,
        "semesters": sorted_semesters,
        "values": values,
        "avgAll": avg_all,
        "avgMain": avg_main,
    }

REFERENCE_STYLE_GUIDE = """
[기준 템플릿]
- 반드시 `SchoolRecordOneTimeReportPage.tsx` / `ReportKimMinseop.tsx` 수준의 정보 밀도와 시각화 구성을 따른다.
- 단순 요약이 아니라 '실제 상담용 보고서'처럼 충분한 설명량을 담아야 한다.
- 페이지별 레이아웃은 고정이며, 각 카드의 텍스트가 화면 블록을 넘치지 않도록 길이를 조절한다.

[분량 기준]
- 1페이지 요약 문단: 3문장 이상, 170~280자 권장
- text-analysis 인용문: 90~220자 권장 (실제 세특/창체 문장 일부 발췌)
- text-analysis 분석문: 140~260자 권장
- 비교 카드 accepted/student 본문: 각 180~320자 권장
- comparison highlight: 110~200자 권장

[강점/약점 품질 기준]
- 분석문은 반드시 다음 흐름을 갖는다:
  1) 무엇이 보이는지
  2) 왜 강점/약점인지
  3) 입시/전공 맥락에서 어떤 의미인지
- flowchart는 4개 노드짜리 단순 타임라인이 아니라, 최소 6개 노드로 흐름이 보이게 구성한다.
- flowchart 노드 label은 10자 이내, sub는 14자 이내로 짧게 작성한다.
- heatmap, text-analysis, flowchart, bar-chart는 예시 보고서와 같은 역할을 하도록 배치한다.

[점수 산출]
- 학업역량 가중치 3배
- 총점 = (학업역량*3 + 탐구깊이 + 진로연결성 + 공동체역량 + 창의융합역량 + 자기주도성) / 8 * 100

[금지]
- 밋밋한 한 줄 피드백
- '좋다/아쉽다'만 있고 근거가 없는 문장
- 지나치게 긴 flowchart 라벨
- JSON 외 텍스트 출력
"""

VISUAL_REPORT_SYSTEM_PROMPT = f"""당신은 고교 생활기록부를 4페이지 시각 보고서 JSON으로 변환하는 전문 에이전트다.

[핵심 원칙]
1) 제공된 생기부 원문/파싱 데이터만 근거로 사용한다.
2) 데이터에 없는 사실은 절대 만들지 않는다.
3) 레이아웃은 고정이므로, 각 필드는 블록 안에 안정적으로 들어가도록 길이를 제어한다.
4) 예시 보고서의 형식뿐 아니라 분량감과 설명 밀도도 최대한 가깝게 맞춘다.
5) 분석문은 입시 관점의 의미까지 포함한다.

{REFERENCE_STYLE_GUIDE}
"""


def _extract_student_name(school_record: Dict[str, Any]) -> str:
    forms = school_record.get("forms") or school_record
    parsed = (forms.get("parsedSchoolRecord") or {}) if isinstance(forms, dict) else {}
    sections = parsed.get("sections", {}) if isinstance(parsed, dict) else {}

    for key in ("studentInfo", "student_info", "personalInfo"):
        info = sections.get(key, {})
        if isinstance(info, dict):
            name = info.get("name") or info.get("이름") or info.get("성명")
            if isinstance(name, str) and name.strip():
                return name.strip()

    summary = (forms.get("parsedSchoolRecordSummary") or {}) if isinstance(forms, dict) else {}
    if isinstance(summary, dict):
        name = summary.get("studentName") or summary.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()

    return "학생"


def _repair_json(text: str) -> str:
    """Gemini가 반환한 깨진 JSON을 최대한 복구한다."""
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0 or open_brackets > 0:
        text = text.rstrip().rstrip(',')
        text += ']' * max(0, open_brackets)
        text += '}' * max(0, open_braces)

    text = re.sub(r'(?<=\w)"(?=\w)', '\\"', text)
    return text


def _parse_json_response(text: str) -> Dict[str, Any]:
    clean = (text or "").strip()
    if not clean:
        raise ValueError("빈 응답")

    if clean.startswith("```"):
        lines = clean.split("\n")
        start = 1
        end = len(lines)
        for i, line in enumerate(lines):
            if i == 0:
                continue
            if line.strip().startswith("```"):
                end = i
                break
        clean = "\n".join(lines[start:end]).strip()

    brace_start = clean.find("{")
    brace_end = clean.rfind("}") + 1
    if brace_start >= 0 and brace_end > brace_start:
        clean = clean[brace_start:brace_end]

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        repaired = _repair_json(clean)
        return json.loads(repaired)


async def _generate_json(prompt: str, *, max_output_tokens: int = 4096) -> Dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            model = genai.GenerativeModel(
                model_name=GEMINI_FLASH_MODEL,
                system_instruction=VISUAL_REPORT_SYSTEM_PROMPT,
            )
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15 + attempt * 0.05,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                ),
                safety_settings=_SAFETY_SETTINGS,
            )
            raw_text = getattr(response, "text", "") or ""
            if not raw_text.strip():
                candidates = getattr(response, "candidates", [])
                print(f"[VisualReport] 빈 응답 (attempt={attempt}), candidates={candidates}, feedback={getattr(response, 'prompt_feedback', None)}")
                raise ValueError("Gemini 빈 응답")
            return _parse_json_response(raw_text)
        except Exception as e:
            last_error = e
            print(f"[VisualReport] attempt {attempt}/{_MAX_RETRIES} 실패: {type(e).__name__}: {e}")
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(1)
    raise last_error  # type: ignore[misc]


def _full_report_prompt(student_name: str, context: str) -> str:
    return f"""아래 생기부 컨텍스트를 분석하여 4페이지 시각 보고서용 JSON 전체를 한 번에 생성하라.

[학생 이름]
{student_name}

[생기부 컨텍스트]
{context}

[중요]
- 프론트엔드는 이미 고정 템플릿을 갖고 있다.
- 당신은 레이아웃이 아니라 '값과 문구'만 채운다.
- 따라서 문장은 풍부하되, 각 필드는 카드/도형 안에 들어갈 수 있도록 길이를 과도하게 늘리지 마라.
- 4페이지를 각각 따로 설명하지 말고 최종 JSON 한 번만 출력한다.

[출력 JSON 스키마]
{{
  "studentName": "{student_name}",
  "page1": {{
    "grades": {{
      "subjects": [
        {{ "name": "국어", "grades": [4,4,3,4,2], "color": "#F97316" }},
        {{ "name": "수학", "grades": [2,1,1,1,3], "color": "#EF4444" }}
      ],
      "semesters": ["1-1","1-2","2-1","2-2","3-1"],
      "avgAll": [3.2,3.0,2.1,2.6,2.75],
      "avgMain": [3.2,3.0,2.0,2.75,2.33]
    }},
    "radar": {{
      "values": [0.62,0.72,0.55,0.68,0.62,0.75],
      "labels": ["학업역량","탐구 깊이","진로 연결성","공동체역량","창의융합역량","자기주도성"],
      "totalScore": 65
    }},
    "studentType": "강점 키워드가 돋보이는",
    "studentTypeHighlight": "유형명",
    "hashtags": ["#태그1","#태그2","#태그3"],
    "summary": "3문장 이상의 요약",
    "growthSummary": "UNIROAD 한 줄 요약",
    "growthSteps": [
      {{ "title": "1-1", "desc": "기초 역량 형성", "sub": "8~16자 설명" }}
    ],
    "keyPoints": [
      {{ "label": "관심 심화", "desc": "55~95자 설명" }},
      {{ "label": "도구 습득", "desc": "55~95자 설명" }},
      {{ "label": "전공 실증", "desc": "55~95자 설명" }}
    ]
  }},
  "page2": {{
    "strengths": [
      {{
        "title": "강점 제목",
        "subtitle": "출처 영역",
        "type": "heatmap",
        "description": "1~2문장 설명",
        "data": {{
          "subjects": ["국어","수학","영어","사회","과학"],
          "semesters": ["1-1","1-2","2-1","2-2","3-1"],
          "values": [[4,4,3,4,2],[2,1,1,1,3],[3,3,2,3,2],[3,3,null,null,null],[4,4,2,3,null]]
        }}
      }},
      {{
        "title": "강점 제목",
        "subtitle": "출처 영역",
        "type": "text-analysis",
        "description": null,
        "data": {{
          "quote": "실제 원문 인용",
          "analysis": "근거-해석-입시 의미가 포함된 분석"
        }}
      }},
      {{
        "title": "강점 제목",
        "subtitle": "출처 영역",
        "type": "flowchart",
        "description": "설명",
        "data": {{
          "branchLabel": "전문 확장",
          "mergeLabel": "역량 통합",
          "nodes": [
            {{ "id": "s1", "label": "시작 노드", "sub": "짧은 설명", "type": "start" }},
            {{ "id": "s2", "label": "중간 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "s3", "label": "중간 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "s4", "label": "중간 노드", "sub": "짧은 설명", "type": "milestone" }},
            {{ "id": "s5", "label": "중간 노드", "sub": "짧은 설명", "type": "milestone" }},
            {{ "id": "s6", "label": "중간 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "s7", "label": "결과 노드", "sub": "짧은 설명", "type": "result" }}
          ]
        }}
      }}
    ]
  }},
  "page3": {{
    "weaknesses": [
      {{
        "title": "약점 제목",
        "subtitle": "출처 영역",
        "type": "bar-chart",
        "description": "설명",
        "data": {{
          "rows": [
            {{ "label": "1학년", "values": [70,30], "labels": ["감상형","실증형"] }},
            {{ "label": "2학년", "values": [45,55], "labels": ["감상형","실증형"] }},
            {{ "label": "3학년", "values": [20,80], "labels": ["감상형","실증형"] }}
          ]
        }}
      }},
      {{
        "title": "약점 제목",
        "subtitle": "출처 영역",
        "type": "text-analysis",
        "description": null,
        "data": {{
          "quote": "실제 원문 인용",
          "analysis": "무엇이 비는지 / 왜 아쉬운지 / 어떻게 보완할지"
        }}
      }},
      {{
        "title": "약점 제목",
        "subtitle": "출처 영역",
        "type": "flowchart",
        "description": "설명",
        "data": {{
          "branchLabel": "전환 지점",
          "mergeLabel": "보완 필요",
          "nodes": [
            {{ "id": "w1", "label": "시작 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "w2", "label": "중간 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "w3", "label": "중간 노드", "sub": "짧은 설명", "type": "warning" }},
            {{ "id": "w4", "label": "중간 노드", "sub": "짧은 설명", "type": "activity" }},
            {{ "id": "w5", "label": "중간 노드", "sub": "짧은 설명", "type": "missing" }},
            {{ "id": "w6", "label": "중간 노드", "sub": "짧은 설명", "type": "missing" }},
            {{ "id": "w7", "label": "결론 노드", "sub": "짧은 설명", "type": "warning" }}
          ]
        }}
      }}
    ],
    "diagnosisSummary": "핵심 진단"
  }},
  "page4": {{
    "targetMajor": "전공명",
    "comparisons": [
      {{
        "title": "탐구 깊이 비교",
        "subtitle": "세특 서술 방식",
        "accepted": {{ "label": "S대 OO학과", "text": "합격자 수준 예시" }},
        "student": {{ "text": "학생 실제 기록 기반 요약" }},
        "highlight": "차이와 보완점"
      }},
      {{
        "title": "전공 연결성 비교",
        "subtitle": "교과 간 서사 연결",
        "accepted": {{ "label": "Y대 OO학과", "text": "합격자 수준 예시" }},
        "student": {{ "text": "학생 실제 기록 기반 요약" }},
        "highlight": "차이와 보완점"
      }},
      {{
        "title": "데이터 활용 능력 비교",
        "subtitle": "탐구 방법론",
        "accepted": {{ "label": "K대 OO학과", "text": "합격자 수준 예시" }},
        "student": {{ "text": "학생 실제 기록 기반 요약" }},
        "highlight": "차이와 보완점"
      }}
    ]
  }}
}}

[필수 규칙]
1. 프론트는 고정 렌더러를 사용하므로, 당신은 값과 텍스트만 제공한다.
2. 차트 좌표, 스타일, 정렬은 프론트가 처리한다.
3. semesters는 실제 학기 수로 작성한다. 최소 4개, 최대 6개.
4. radar totalScore는 학업역량 3배 가중 공식으로 산출한다.
5. 강점/약점은 각각 3~4개, 가능하면 4개.
6. strength/weakness 모두 text-analysis 최소 2개, flowchart 최소 1개 포함.
7. flowchart는 최소 7노드, 복합 흐름 구조를 반영한다.
8. 모든 quote는 실제 생기부 문장 일부를 인용한다.
9. JSON만 출력한다.
"""


def _page1_prompt(student_name: str, context: str) -> str:
    return f"""아래 생기부 컨텍스트를 분석하여 1페이지 JSON만 생성하라.

[학생 이름]
{student_name}

[생기부 컨텍스트]
{context}

[출력 JSON 스키마]
{{
  "grades": {{
    "subjects": [
      {{ "name": "국어", "grades": [4,4,3,4,2], "color": "#F97316" }}
    ],
    "semesters": ["1-1","1-2","2-1","2-2","3-1"],
    "avgAll": [3.2,3.0,2.1,2.6,2.75],
    "avgMain": [3.2,3.0,2.0,2.75,2.33]
  }},
  "radar": {{
    "values": [0.62,0.72,0.55,0.68,0.62,0.75],
    "labels": ["학업역량","탐구 깊이","진로 연결성","공동체역량","창의융합역량","자기주도성"],
    "totalScore": 65
  }},
  "studentType": "자기주도적 탐구력과 수리·과학 융합이 돋보이는",
  "studentTypeHighlight": "융합형 탐구 학생",
  "hashtags": ["#수학·과학 융합 탐구","#자기주도 학습과 멘토링","#공학적 사고와 실험 설계"],
  "summary": "3문장 이상의 충분한 요약",
  "growthSummary": "UNIROAD 한 줄 요약",
  "growthSteps": [
    {{ "title": "1-1", "desc": "기초 역량 형성", "sub": "수학독서토론·과학캠프" }}
  ],
  "keyPoints": [
    {{ "label": "관심 심화", "desc": "55~95자 설명" }},
    {{ "label": "도구 습득", "desc": "55~95자 설명" }},
    {{ "label": "전공 실증", "desc": "55~95자 설명" }}
  ]
}}

[필수 규칙]
1. semesters는 실제 학기 수로 작성한다. 최소 4개, 최대 6개.
2. grades.subjects는 가능한 국어/수학/영어/사회/과학 중심으로 정리한다.
3. color는 다음만 사용: 국어={SUBJECT_COLORS["국어"]}, 수학={SUBJECT_COLORS["수학"]}, 영어={SUBJECT_COLORS["영어"]}, 사회={SUBJECT_COLORS["사회"]}, 과학={SUBJECT_COLORS["과학"]}.
4. radar totalScore는 학업역량 3배 가중 공식으로 산출한다.
5. summary는 강점 2개 + 보완점 1개가 보이는 3문장 이상으로 작성한다.
6. growthSteps는 각 학기별 대표 흐름을 4~10자 제목, 8~16자 부설명으로 맞춘다.
7. keyPoints는 정확히 3개다.
8. JSON만 출력한다.
"""


def _page2_prompt(student_name: str, context: str) -> str:
    return f"""아래 생기부 컨텍스트를 분석하여 2페이지(핵심 강점) JSON만 생성하라.

[학생 이름]
{student_name}

[생기부 컨텍스트]
{context}

[출력 JSON 스키마]
{{
  "strengths": [
    {{
      "title": "수학 교과 역량",
      "subtitle": "교과 성적 전반",
      "type": "heatmap",
      "description": "1~2문장",
      "data": {{
        "subjects": ["국어","수학","영어","사회","과학"],
        "semesters": ["1-1","1-2","2-1","2-2","3-1"],
        "values": [[4,4,3,4,2],[2,1,1,1,3],[3,3,2,3,2],[3,3,null,null,null],[4,4,2,3,null]]
      }}
    }},
    {{
      "title": "공학적 탐구와 실험 설계",
      "subtitle": "3학년 세특",
      "type": "text-analysis",
      "description": null,
      "data": {{
        "quote": "실제 세특/창체 원문 발췌 90~220자",
        "analysis": "140~260자 분석"
      }}
    }},
    {{
      "title": "자기주도 학습과 멘토링",
      "subtitle": "수학 멘토 활동",
      "type": "text-analysis",
      "description": null,
      "data": {{
        "quote": "실제 세특/창체 원문 발췌 90~220자",
        "analysis": "140~260자 분석"
      }}
    }},
    {{
      "title": "심화탐구흐름",
      "subtitle": "세특 전반",
      "type": "flowchart",
      "description": "120~220자 설명",
      "data": {{
        "branchLabel": "전문 확장",
        "mergeLabel": "역량 통합",
        "nodes": [
          {{ "id": "s1", "label": "수학 흥미", "sub": "기초 관심 형성", "type": "start" }},
          {{ "id": "s2", "label": "과학 확장", "sub": "실험 탐구 연결", "type": "activity" }},
          {{ "id": "s3", "label": "도구 습득", "sub": "확통·기하 활용", "type": "activity" }},
          {{ "id": "s4", "label": "주제 심화", "sub": "공학 문제 적용", "type": "milestone" }},
          {{ "id": "s5", "label": "실증 분석", "sub": "곡선·광학 탐구", "type": "milestone" }},
          {{ "id": "s6", "label": "성과 정리", "sub": "탐구 결과 구조화", "type": "activity" }},
          {{ "id": "s7", "label": "전공 적합", "sub": "공학 역량 입증", "type": "result" }}
        ]
      }}
    }}
  ]
}}

[필수 규칙]
1. 강점은 3~4개 작성하되 가능하면 4개로 작성한다.
2. heatmap 1개, text-analysis 최소 2개, flowchart 최소 1개를 반드시 포함한다.
3. text-analysis quote는 실제 기록 발췌여야 한다.
4. analysis는 근거 → 해석 → 입시 의미 순서가 보이게 쓴다.
5. flowchart 노드는 최소 7개, 가능하면 7~8개로 작성한다.
6. flowchart는 단순 일자형이 아니라 위/아래 두 갈래로 전개되는 복합 흐름처럼 쓸 것.
7. `branchLabel`, `mergeLabel`도 반드시 채운다.
8. label은 10자 이하, sub는 14자 이하로 짧게 쓴다.
9. description은 예시 보고서처럼 충분한 설명량을 유지하되 박스를 넘치지 않게 조절한다.
10. JSON만 출력한다.
"""


def _page3_prompt(student_name: str, context: str) -> str:
    return f"""아래 생기부 컨텍스트를 분석하여 3페이지(핵심 약점) JSON만 생성하라.

[학생 이름]
{student_name}

[생기부 컨텍스트]
{context}

[출력 JSON 스키마]
{{
  "weaknesses": [
    {{
      "title": "세특 서술 깊이 변화",
      "subtitle": "세특 전반",
      "type": "bar-chart",
      "description": "100~190자 설명",
      "data": {{
        "rows": [
          {{ "label": "1학년", "values": [70,30], "labels": ["감상형","실증형"] }},
          {{ "label": "2학년", "values": [45,55], "labels": ["감상형","실증형"] }},
          {{ "label": "3학년", "values": [20,80], "labels": ["감상형","실증형"] }}
        ]
      }}
    }},
    {{
      "title": "전공 연결성",
      "subtitle": "대표 세특 발췌",
      "type": "text-analysis",
      "description": null,
      "data": {{
        "quote": "실제 세특/창체 원문 발췌 90~220자",
        "analysis": "140~260자 분석"
      }}
    }},
    {{
      "title": "서술 깊이 편차",
      "subtitle": "대표 세특 발췌",
      "type": "text-analysis",
      "description": null,
      "data": {{
        "quote": "실제 세특/창체 원문 발췌 90~220자",
        "analysis": "140~260자 분석"
      }}
    }},
    {{
      "title": "진로 전환 흐름",
      "subtitle": "학년별 진로 활동",
      "type": "flowchart",
      "description": "120~220자 설명",
      "data": {{
        "branchLabel": "전환 지점",
        "mergeLabel": "보완 필요",
        "nodes": [
          {{ "id": "w1", "label": "초기 관심", "sub": "1학년 주제 시작", "type": "activity" }},
          {{ "id": "w2", "label": "관심 확장", "sub": "다른 분야 탐색", "type": "activity" }},
          {{ "id": "w3", "label": "전환 지점", "sub": "왜 바뀌는지 약함", "type": "warning" }},
          {{ "id": "w4", "label": "새 진로", "sub": "후반 주제 집중", "type": "activity" }},
          {{ "id": "w5", "label": "후속 검증", "sub": "연결 서사 부족", "type": "missing" }},
          {{ "id": "w6", "label": "공백 구간", "sub": "중간 연결 약함", "type": "missing" }},
          {{ "id": "w7", "label": "보완 필요", "sub": "한 줄 서사 정리", "type": "warning" }}
        ]
      }}
    }}
  ],
  "diagnosisSummary": "2문장 내 핵심 진단"
}}

[필수 규칙]
1. 약점은 3~4개 작성하되 가능하면 4개로 작성한다.
2. text-analysis 최소 2개, flowchart 최소 1개를 반드시 포함한다.
3. 약점 분석문은 '무엇이 비는지 / 왜 아쉬운지 / 어떻게 보완할지'가 드러나야 한다.
4. bar-chart는 실제 전반적 서술 경향을 근거로 합리적으로 추정한다.
5. flowchart 노드는 최소 7개, 가능하면 7~8개로 작성한다.
6. flowchart는 단순 일자형이 아니라 위/아래 두 갈래로 분기되는 복합 흐름처럼 쓸 것.
7. `branchLabel`, `mergeLabel`도 반드시 채운다.
8. label은 10자 이하, sub는 14자 이하.
9. diagnosisSummary는 짧지만 선명하게 쓴다.
10. JSON만 출력한다.
"""


def _page4_prompt(student_name: str, context: str) -> str:
    return f"""아래 생기부 컨텍스트를 분석하여 4페이지(합격자 비교 분석) JSON만 생성하라.

[학생 이름]
{student_name}

[생기부 컨텍스트]
{context}

[출력 JSON 스키마]
{{
  "targetMajor": "학생에게 가장 자연스러운 계열/전공명",
  "comparisons": [
    {{
      "title": "탐구 깊이 비교",
      "subtitle": "세특 서술 방식",
      "accepted": {{
        "label": "S대 OO학과",
        "text": "일반적인 합격자 수준의 우수 세특 예시 180~320자"
      }},
      "student": {{
        "text": "해당 학생의 실제 기록 기반 요약 180~320자"
      }},
      "highlight": "110~200자 비교 분석"
    }},
    {{
      "title": "전공 연결성 비교",
      "subtitle": "교과 간 서사 연결",
      "accepted": {{
        "label": "Y대 OO학과",
        "text": "일반적인 합격자 수준의 우수 세특 예시 180~320자"
      }},
      "student": {{
        "text": "해당 학생의 실제 기록 기반 요약 180~320자"
      }},
      "highlight": "110~200자 비교 분석"
    }},
    {{
      "title": "데이터 활용 능력 비교",
      "subtitle": "탐구 방법론",
      "accepted": {{
        "label": "K대 OO학과",
        "text": "일반적인 합격자 수준의 우수 세특 예시 180~320자"
      }},
      "student": {{
        "text": "해당 학생의 실제 기록 기반 요약 180~320자"
      }},
      "highlight": "110~200자 비교 분석"
    }}
  ]
}}

[필수 규칙]
1. comparisons는 정확히 3개다.
2. accepted.text는 실제 특정 학생 데이터가 아니라 '일반적인 합격자 수준의 강한 세특 예시'로 쓴다.
3. student.text는 반드시 제공된 생기부 근거만으로 작성한다.
4. highlight는 둘의 차이를 선명하게 비교하고, 학생이 무엇을 보완하면 되는지까지 드러나야 한다.
5. 각 comparison 제목은 예시 보고서처럼 명확하고 짧아야 한다.
6. JSON만 출력한다.
"""


def _apply_real_grades(
    page1: Dict[str, Any],
    page2: Dict[str, Any],
    grade_data: Dict[str, Any],
) -> None:
    """Gemini가 생성한 성적 데이터를 실제 석차등급으로 덮어쓴다."""
    subjects_list = []
    for i, subj in enumerate(grade_data["subjects"]):
        subjects_list.append({
            "name": subj,
            "grades": grade_data["values"][i],
            "color": SUBJECT_COLORS.get(subj, "#6B7280"),
        })

    page1["grades"] = {
        "subjects": subjects_list,
        "semesters": grade_data["semesters"],
        "avgAll": grade_data["avgAll"],
        "avgMain": grade_data["avgMain"],
    }

    for strength in (page2.get("strengths") or []):
        if strength.get("type") == "heatmap":
            strength["data"] = {
                "subjects": grade_data["subjects"],
                "semesters": grade_data["semesters"],
                "values": grade_data["values"],
            }
            break


async def generate_visual_report_data(
    school_record: Dict[str, Any],
    *,
    max_context_chars: int = 16000,
    prebuilt_context: str | None = None,
) -> Dict[str, Any]:
    context = prebuilt_context or build_school_record_report_context_text(
        school_record,
        max_chars=max_context_chars,
    )
    if not context or len(context.strip()) < 100:
        raise ValueError("생기부 데이터가 충분하지 않습니다.")

    student_name = _extract_student_name(school_record)
    grade_data = _extract_grade_data(school_record)

    page1_task = _generate_json(_page1_prompt(student_name, context), max_output_tokens=8192)
    page2_task = _generate_json(_page2_prompt(student_name, context), max_output_tokens=8192)
    page3_task = _generate_json(_page3_prompt(student_name, context), max_output_tokens=8192)
    page4_task = _generate_json(_page4_prompt(student_name, context), max_output_tokens=8192)

    page1, page2, page3, page4 = await asyncio.gather(
        page1_task, page2_task, page3_task, page4_task,
    )

    if grade_data:
        _apply_real_grades(page1, page2, grade_data)

    return {
        "studentName": student_name,
        "page1": page1,
        "page2": page2,
        "page3": page3,
        "page4": page4,
    }


