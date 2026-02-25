from __future__ import annotations

import re
from typing import Dict


KOREAN_ELECTIVE_CODE: Dict[str, str] = {
    "화법과작문": "S0913",
    "언어와매체": "S0481",
}

MATH_ELECTIVE_CODE: Dict[str, str] = {
    "확률과통계": "S0482",
    "미적분": "S0483",
    "기하": "S0909",
}

INQUIRY_SUBJECT_CODE: Dict[str, str] = {
    "생활과윤리": "S0485",
    "윤리와사상": "S0486",
    "한국지리": "S0487",
    "세계지리": "S0488",
    "동아시아사": "S0489",
    "세계사": "S0490",
    "경제": "S0491",
    "정치와법": "S0492",
    "사회문화": "S0493",
    "물리학1": "S0494",
    "화학1": "S0495",
    "생명과학1": "S0496",
    "지구과학1": "S0497",
    "물리학2": "S0498",
    "화학2": "S0499",
    "생명과학2": "S0500",
    "지구과학2": "S0501",
    "농업기초기술": "S0511",
    "공업일반": "S0512",
    "상업경제": "S0513",
    "수산해운산업기초": "S0514",
    "인간발달": "S0515",
    "성공적인직업생활": "S0516",
}

INQUIRY_ALIASES: Dict[str, str] = {
    "생윤": "생활과윤리",
    "생활과윤리": "생활과윤리",
    "윤사": "윤리와사상",
    "윤리와사상": "윤리와사상",
    "한지": "한국지리",
    "한국지리": "한국지리",
    "세지": "세계지리",
    "세계지리": "세계지리",
    "동사": "동아시아사",
    "동아시아사": "동아시아사",
    "세사": "세계사",
    "세계사": "세계사",
    "경제": "경제",
    "정법": "정치와법",
    "정치와법": "정치와법",
    "사문": "사회문화",
    "사회문화": "사회문화",
    "물1": "물리학1",
    "물리1": "물리학1",
    "물리학1": "물리학1",
    "화1": "화학1",
    "화학1": "화학1",
    "생1": "생명과학1",
    "생명1": "생명과학1",
    "생명과학1": "생명과학1",
    "지1": "지구과학1",
    "지구1": "지구과학1",
    "지구과학1": "지구과학1",
    "물2": "물리학2",
    "물리2": "물리학2",
    "물리학2": "물리학2",
    "화2": "화학2",
    "화학2": "화학2",
    "생2": "생명과학2",
    "생명2": "생명과학2",
    "생명과학2": "생명과학2",
    "지2": "지구과학2",
    "지구2": "지구과학2",
    "지구과학2": "지구과학2",
}


def _norm(value: str) -> str:
    return re.sub(r"[\s·・\-/()]", "", (value or "").strip())


def normalize_korean_elective(value: str) -> str:
    raw = _norm(value)
    if raw in {"화작", "화법과작문"}:
        return "화법과작문"
    if raw in {"언매", "언어와매체"}:
        return "언어와매체"
    return "화법과작문"


def normalize_math_elective(value: str) -> str:
    raw = _norm(value)
    if raw in {"확통", "확률과통계"}:
        return "확률과통계"
    if raw in {"미적", "미적분"}:
        return "미적분"
    if raw == "기하":
        return "기하"
    return "확률과통계"


def normalize_inquiry_subject(value: str) -> str:
    raw = _norm(value)
    if raw in INQUIRY_ALIASES:
        return INQUIRY_ALIASES[raw]
    return value or "생활과윤리"


def inquiry_to_code(subject_name: str) -> str:
    canonical = normalize_inquiry_subject(subject_name)
    normalized_key = _norm(canonical)
    return INQUIRY_SUBJECT_CODE.get(normalized_key, "S0485")


def korean_to_code(elective: str) -> str:
    canonical = normalize_korean_elective(elective)
    key = _norm(canonical)
    return KOREAN_ELECTIVE_CODE.get(key, "S0913")


def math_to_code(elective: str) -> str:
    canonical = normalize_math_elective(elective)
    key = _norm(canonical)
    return MATH_ELECTIVE_CODE.get(key, "S0482")

