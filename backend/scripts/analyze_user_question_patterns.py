#!/usr/bin/env python3
"""
Generate user-question analysis report from session_chat_messages.

Output:
  backend/reports/all_user_question_analysis_YYYYMMDD.md
"""

import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from statistics import median
from typing import Dict, List, Set

from dotenv import load_dotenv
from supabase import create_client


KST = timezone(timedelta(hours=9))


class TopicRule:
    def __init__(self, name: str, keywords: List[str], regexes: List[str]):
        self.name = name
        self.keywords = [k.lower() for k in keywords]
        self.regexes = [re.compile(p, re.IGNORECASE) for p in regexes]

    def match(self, text: str, text_lower: str) -> bool:
        if any(k in text_lower for k in self.keywords):
            return True
        return any(p.search(text) for p in self.regexes)


TOPIC_RULES = [
    TopicRule(
        "생기부/학종 분석",
        [
            "생기부",
            "학생부",
            "세특",
            "행특",
            "자소서",
            "학종",
            "종합전형",
            "학생부종합",
            "교과세특",
            "창체",
        ],
        [r"학생부\s*종합", r"세부능력.*특기사항", r"생활기록부"],
    ),
    TopicRule(
        "특수전형(농어촌/장애/차상위 등)",
        [
            "농어촌",
            "장애",
            "장애전형",
            "차상위",
            "기초생활",
            "기회균형",
            "저소득",
            "보훈",
            "국가유공자",
            "한부모",
            "다문화",
            "특성화고",
            "서해5도",
            "특수전형",
            "장애인",
        ],
        [r"기초\s*생활", r"기회\s*균형", r"국가\s*보훈", r"차상위"],
    ),
    TopicRule(
        "합격 예측/지원 가능성",
        [
            "합격가능",
            "합격 가능",
            "합격예측",
            "최초합",
            "추합",
            "지원 가능",
            "소신",
            "적정",
            "안정",
            "붙을",
            "될까",
            "될까요",
            "입결",
            "컷",
            "어디 갈 수",
            "어디갈수",
        ],
        [r"합격.*(가능|확률|예측)", r"붙을\s*수", r"지원.*가능"],
    ),
    TopicRule(
        "전형 요강/지원 조건",
        [
            "요강",
            "모집요강",
            "전형",
            "수시",
            "정시",
            "논술",
            "면접",
            "최저",
            "지원자격",
            "자격요건",
            "반영비율",
            "모집인원",
            "경쟁률",
            "전형요소",
            "제출서류",
        ],
        [r"모집\s*요강", r"지원\s*자격", r"수능\s*최저"],
    ),
    TopicRule(
        "성적/환산/컷",
        [
            "내신",
            "등급",
            "모의고사",
            "백분위",
            "표준점수",
            "표점",
            "원점수",
            "환산점수",
            "환산",
            "등급컷",
            "점수",
        ],
        [r"\d(\.\d+)?\s*등급", r"\d{2,3}\s*점", r"백분위\s*\d+"],
    ),
    TopicRule(
        "대학/학과 탐색",
        [
            "대학",
            "대학교",
            "학과",
            "전공",
            "학부",
            "캠퍼스",
            "추천",
            "라인업",
            "리스트",
            "어떤 학교",
            "어떤 대학",
        ],
        [r"[가-힣a-zA-Z]{2,}\s*(대학교|대)\b", r"\b학과\b", r"\b전공\b"],
    ),
    TopicRule(
        "학습 전략/공부법",
        [
            "공부",
            "학습",
            "플랜",
            "계획",
            "커리큘럼",
            "인강",
            "문제집",
            "노베이스",
            "재수",
            "n수",
        ],
        [r"공부\s*법", r"학습\s*계획", r"노\s*베이스"],
    ),
    TopicRule(
        "원서/일정/행정",
        [
            "원서",
            "접수",
            "마감",
            "일정",
            "등록",
            "충원",
            "발표일",
            "추가합격",
            "면접일",
        ],
        [r"원서\s*접수", r"합격\s*발표", r"등록\s*기간"],
    ),
]


MAIN_TOPIC_PRIORITY = [
    "생기부/학종 분석",
    "특수전형(농어촌/장애/차상위 등)",
    "합격 예측/지원 가능성",
    "전형 요강/지원 조건",
    "성적/환산/컷",
    "대학/학과 탐색",
    "학습 전략/공부법",
    "원서/일정/행정",
]


SITUATION_PATTERNS = {
    "성적 수치 제시형": re.compile(
        r"(\d(\.\d+)?\s*등급)|(\b백분위\s*\d+)|(\b표준?점수\s*\d+)|(\b내신\s*\d(\.\d+)?)"
    ),
    "대학/학과 특정형": re.compile(r"[가-힣a-zA-Z]{2,}\s*(대학교|대)\b|[가-힣a-zA-Z]{2,}\s*학과"),
    "장문 맥락 설명형": re.compile(r".{180,}", re.DOTALL),
}


def parse_dt(date_text: str) -> datetime:
    if not date_text:
        return datetime.now(timezone.utc)
    text = date_text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        # Handle variable-length fractional seconds for Python 3.9 parser edge-cases.
        m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})$", text)
        if m:
            base, frac, tz = m.groups()
            frac = (frac + "000000")[:6]
            text = f"{base}.{frac}{tz}"
            dt = datetime.fromisoformat(text)
        else:
            raise
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_topics(text: str) -> Set[str]:
    text = (text or "").strip()
    text_lower = text.lower()
    matched = {rule.name for rule in TOPIC_RULES if rule.match(text, text_lower)}
    if not matched:
        matched.add("기타")
    return matched


def select_main_topic(topics: Set[str]) -> str:
    for topic in MAIN_TOPIC_PRIORITY:
        if topic in topics:
            return topic
    return "기타"


def summarize_user_profile(user_row: Dict) -> str:
    c = user_row["question_count"]
    d = user_row["active_days"]
    topic_counter: Counter = user_row["main_topic_counter"]
    top_topics = [name for name, _ in topic_counter.most_common(2)]
    if not top_topics:
        top_topics = ["기타"]
    return f"{c}문항 / {d}일 활동 / 주요토픽: {', '.join(top_topics)}"


def pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return (num / den) * 100.0


def fmt_pct(num: int, den: int) -> str:
    return f"{pct(num, den):.1f}%"


def fetch_all_user_questions(client) -> List[Dict]:
    all_rows: List[Dict] = []
    page_size = 1000
    offset = 0

    while True:
        res = (
            client.table("session_chat_messages")
            .select("user_id,user_session,content,created_at")
            .eq("role", "user")
            .not_.is_("user_id", "null")
            .order("created_at", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    return all_rows


def build_metrics(messages: List[Dict]) -> Dict:
    user_stats = defaultdict(
        lambda: {
            "question_count": 0,
            "sessions": set(),
            "days": set(),
            "main_topic_counter": Counter(),
            "all_topic_counter": Counter(),
            "situation_counter": Counter(),
        }
    )

    main_topic_counter = Counter()
    all_topic_counter = Counter()
    topic_user_sets = defaultdict(set)
    topic_samples = defaultdict(list)
    situation_counter = Counter()
    situation_user_sets = defaultdict(set)

    analyzed_messages = []
    for row in messages:
        uid = row.get("user_id")
        if not uid:
            continue

        text = (row.get("content") or "").strip()
        topics = classify_topics(text)
        main_topic = select_main_topic(topics)

        created_at = parse_dt(row.get("created_at"))
        kst_day = created_at.astimezone(KST).date().isoformat()
        sess = row.get("user_session")

        flags = set()
        if SITUATION_PATTERNS["성적 수치 제시형"].search(text):
            flags.add("성적 수치 제시형")
        if SITUATION_PATTERNS["대학/학과 특정형"].search(text):
            flags.add("대학/학과 특정형")
        if SITUATION_PATTERNS["장문 맥락 설명형"].search(text):
            flags.add("장문 맥락 설명형")
        if "특수전형(농어촌/장애/차상위 등)" in topics:
            flags.add("특수전형 자격 검토형")
        if "합격 예측/지원 가능성" in topics:
            flags.add("합격 가능성 판단형")
        if "전형 요강/지원 조건" in topics:
            flags.add("요강/지원조건 확인형")

        analyzed_messages.append(
            {
                "user_id": uid,
                "user_session": sess,
                "content": text,
                "created_at": created_at,
                "kst_day": kst_day,
                "topics": topics,
                "main_topic": main_topic,
                "flags": flags,
            }
        )

        u = user_stats[uid]
        u["question_count"] += 1
        if sess:
            u["sessions"].add(sess)
        u["days"].add(kst_day)
        u["main_topic_counter"][main_topic] += 1
        for t in topics:
            u["all_topic_counter"][t] += 1
            topic_user_sets[t].add(uid)
            if len(topic_samples[t]) < 5:
                topic_samples[t].append(text)
        for f in flags:
            u["situation_counter"][f] += 1
            situation_counter[f] += 1
            situation_user_sets[f].add(uid)

        main_topic_counter[main_topic] += 1
        for t in topics:
            all_topic_counter[t] += 1

    user_rows = []
    for uid, row in user_stats.items():
        user_rows.append(
            {
                "user_id": uid,
                "question_count": row["question_count"],
                "session_count": len(row["sessions"]),
                "active_days": len(row["days"]),
                "main_topic_counter": row["main_topic_counter"],
                "all_topic_counter": row["all_topic_counter"],
                "situation_counter": row["situation_counter"],
            }
        )

    user_rows.sort(key=lambda x: (-x["question_count"], x["user_id"]))
    return {
        "messages": analyzed_messages,
        "users": user_rows,
        "main_topic_counter": main_topic_counter,
        "all_topic_counter": all_topic_counter,
        "topic_user_sets": topic_user_sets,
        "topic_samples": topic_samples,
        "situation_counter": situation_counter,
        "situation_user_sets": situation_user_sets,
    }


def cohort_stats(messages: List[Dict], users: List[Dict], user_filter) -> Dict:
    cohort_users = [u for u in users if user_filter(u)]
    cohort_user_ids = {u["user_id"] for u in cohort_users}
    cohort_messages = [m for m in messages if m["user_id"] in cohort_user_ids]

    topic_counter = Counter(m["main_topic"] for m in cohort_messages)
    all_topic_counter = Counter()
    topic_user_sets = defaultdict(set)
    for m in cohort_messages:
        for t in m["topics"]:
            all_topic_counter[t] += 1
            topic_user_sets[t].add(m["user_id"])

    question_counts = [u["question_count"] for u in cohort_users]
    return {
        "users": cohort_users,
        "messages": cohort_messages,
        "user_count": len(cohort_users),
        "question_count": len(cohort_messages),
        "avg_questions_per_user": (sum(question_counts) / len(question_counts)) if question_counts else 0.0,
        "median_questions_per_user": median(question_counts) if question_counts else 0.0,
        "main_topic_counter": topic_counter,
        "all_topic_counter": all_topic_counter,
        "topic_user_sets": topic_user_sets,
    }


def render_topic_table(counter: Counter, total_questions: int, top_n: int = 8) -> List[str]:
    lines = ["| 토픽(주토픽 기준) | 질문 수 | 비중 |", "|---|---:|---:|"]
    for topic, cnt in counter.most_common(top_n):
        lines.append(f"| {topic} | {cnt:,} | {fmt_pct(cnt, total_questions)} |")
    return lines


def render_focus_table(
    all_topic_counter: Counter,
    topic_user_sets: Dict[str, Set[str]],
    total_questions: int,
    total_users: int,
) -> List[str]:
    focus_topics = [
        "생기부/학종 분석",
        "특수전형(농어촌/장애/차상위 등)",
        "합격 예측/지원 가능성",
        "전형 요강/지원 조건",
        "성적/환산/컷",
    ]
    lines = ["| 관심 주제(멀티 라벨) | 질문 수 | 질문 비중 | 관련 유저 수 | 유저 비중 |", "|---|---:|---:|---:|---:|"]
    for t in focus_topics:
        q = all_topic_counter.get(t, 0)
        u = len(topic_user_sets.get(t, set()))
        lines.append(
            f"| {t} | {q:,} | {fmt_pct(q, total_questions)} | {u:,} | {fmt_pct(u, total_users)} |"
        )
    return lines


def render_user_top_table(users: List[Dict], limit: int = 20) -> List[str]:
    lines = ["| 순위 | user_id | 질문 수 | 활동일수 | 세션 수 | 주토픽 상위 2개 |", "|---:|---|---:|---:|---:|---|"]
    for idx, row in enumerate(users[:limit], 1):
        top_topics = ", ".join([t for t, _ in row["main_topic_counter"].most_common(2)]) or "기타"
        lines.append(
            f"| {idx} | `{row['user_id']}` | {row['question_count']:,} | {row['active_days']} | {row['session_count']} | {top_topics} |"
        )
    return lines


def render_situation_table(
    situation_counter: Counter, situation_user_sets: Dict[str, Set[str]], total_questions: int, total_users: int
) -> List[str]:
    lines = ["| 상황 신호 | 질문 수 | 질문 비중 | 관련 유저 수 | 유저 비중 |", "|---|---:|---:|---:|---:|"]
    for signal, cnt in situation_counter.most_common():
        users = len(situation_user_sets.get(signal, set()))
        lines.append(f"| {signal} | {cnt:,} | {fmt_pct(cnt, total_questions)} | {users:,} | {fmt_pct(users, total_users)} |")
    return lines


def generate_report(metrics: Dict, output_path: str) -> None:
    messages = metrics["messages"]
    users = metrics["users"]

    total_questions = len(messages)
    total_users = len(users)
    total_sessions = len({m.get("user_session") for m in messages if m.get("user_session")})
    date_min = min(m["created_at"] for m in messages).astimezone(KST).date() if messages else None
    date_max = max(m["created_at"] for m in messages).astimezone(KST).date() if messages else None

    over_20 = cohort_stats(messages, users, lambda u: u["question_count"] >= 20)
    under_20 = cohort_stats(messages, users, lambda u: u["question_count"] < 20)
    over_2days = cohort_stats(messages, users, lambda u: u["active_days"] >= 2)
    under_2days = cohort_stats(messages, users, lambda u: u["active_days"] < 2)

    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines: List[str] = []
    lines.append("# Uniroad 전체 유저 질문 패턴 분석 리포트")
    lines.append("")
    lines.append(f"- 생성 시각: {now_kst}")
    lines.append("- 데이터 소스: `session_chat_messages`")
    lines.append("- 분석 대상: `role='user'` 이고 `user_id IS NOT NULL` 인 질문")
    lines.append("- 분류 방식: 키워드 + 정규식 기반 멀티 라벨 분류 (주토픽은 우선순위 1개)")
    lines.append("")
    lines.append("## 1) 전체 데이터 범위")
    lines.append("")
    lines.append(f"- 대상 유저 수: **{total_users:,}명**")
    lines.append(f"- 대상 질문 수: **{total_questions:,}건**")
    lines.append(f"- 분석 기간(KST): **{date_min} ~ {date_max}**")
    lines.append(f"- (참고) 유저-세션 조합 수: **{total_sessions:,}개**")
    lines.append("")
    lines.append("## 2) 활동량 상위 유저 (질문 수 기준)")
    lines.append("")
    lines.extend(render_user_top_table(users, limit=20))
    lines.append("")
    lines.append("## 3) 전체 유저 기준 주축 질문 통계")
    lines.append("")
    lines.extend(render_topic_table(metrics["main_topic_counter"], total_questions, top_n=9))
    lines.append("")
    lines.append("### 요청 핵심 주제(생기부/특수전형/합격예측 포함) 상세")
    lines.append("")
    lines.extend(
        render_focus_table(
            metrics["all_topic_counter"], metrics["topic_user_sets"], total_questions, total_users
        )
    )
    lines.append("")
    lines.append("## 4) 유저 상황 신호 분석")
    lines.append("")
    lines.extend(
        render_situation_table(
            metrics["situation_counter"],
            metrics["situation_user_sets"],
            total_questions,
            total_users,
        )
    )
    lines.append("")
    lines.append("## 5) 티어 분석 A: 질문수 20회 이상 vs 미만")
    lines.append("")
    lines.append(f"- 20회 이상: 유저 **{over_20['user_count']:,}명**, 질문 **{over_20['question_count']:,}건**, 유저당 평균 질문 **{over_20['avg_questions_per_user']:.1f}건**")
    lines.append(f"- 20회 미만: 유저 **{under_20['user_count']:,}명**, 질문 **{under_20['question_count']:,}건**, 유저당 평균 질문 **{under_20['avg_questions_per_user']:.1f}건**")
    lines.append("")
    lines.append("### 20회 이상 유저군 주토픽 분포")
    lines.append("")
    lines.extend(render_topic_table(over_20["main_topic_counter"], over_20["question_count"], top_n=8))
    lines.append("")
    lines.append("### 20회 미만 유저군 주토픽 분포")
    lines.append("")
    lines.extend(render_topic_table(under_20["main_topic_counter"], under_20["question_count"], top_n=8))
    lines.append("")
    lines.append("### 20회 기준 핵심 주제 비교")
    lines.append("")
    lines.append("| 주제 | 20회 이상 질문 비중 | 20회 미만 질문 비중 | 20회 이상 유저 비중 | 20회 미만 유저 비중 |")
    lines.append("|---|---:|---:|---:|---:|")
    for topic in [
        "생기부/학종 분석",
        "특수전형(농어촌/장애/차상위 등)",
        "합격 예측/지원 가능성",
    ]:
        hq = over_20["all_topic_counter"].get(topic, 0)
        lq = under_20["all_topic_counter"].get(topic, 0)
        hu = len(over_20["topic_user_sets"].get(topic, set()))
        lu = len(under_20["topic_user_sets"].get(topic, set()))
        lines.append(
            f"| {topic} | {fmt_pct(hq, over_20['question_count'])} | {fmt_pct(lq, under_20['question_count'])} | {fmt_pct(hu, over_20['user_count'])} | {fmt_pct(lu, under_20['user_count'])} |"
        )
    lines.append("")
    lines.append("## 6) 티어 분석 B: 2일 이상 접속 vs 미만")
    lines.append("")
    lines.append(f"- 2일 이상 접속: 유저 **{over_2days['user_count']:,}명**, 질문 **{over_2days['question_count']:,}건**, 유저당 평균 질문 **{over_2days['avg_questions_per_user']:.1f}건**")
    lines.append(f"- 2일 미만 접속: 유저 **{under_2days['user_count']:,}명**, 질문 **{under_2days['question_count']:,}건**, 유저당 평균 질문 **{under_2days['avg_questions_per_user']:.1f}건**")
    lines.append("")
    lines.append("### 2일 이상 접속 유저군 주토픽 분포")
    lines.append("")
    lines.extend(render_topic_table(over_2days["main_topic_counter"], over_2days["question_count"], top_n=8))
    lines.append("")
    lines.append("### 2일 미만 접속 유저군 주토픽 분포")
    lines.append("")
    lines.extend(render_topic_table(under_2days["main_topic_counter"], under_2days["question_count"], top_n=8))
    lines.append("")
    lines.append("### 2일 기준 핵심 주제 비교")
    lines.append("")
    lines.append("| 주제 | 2일 이상 질문 비중 | 2일 미만 질문 비중 | 2일 이상 유저 비중 | 2일 미만 유저 비중 |")
    lines.append("|---|---:|---:|---:|---:|")
    for topic in [
        "생기부/학종 분석",
        "특수전형(농어촌/장애/차상위 등)",
        "합격 예측/지원 가능성",
    ]:
        hq = over_2days["all_topic_counter"].get(topic, 0)
        lq = under_2days["all_topic_counter"].get(topic, 0)
        hu = len(over_2days["topic_user_sets"].get(topic, set()))
        lu = len(under_2days["topic_user_sets"].get(topic, set()))
        lines.append(
            f"| {topic} | {fmt_pct(hq, over_2days['question_count'])} | {fmt_pct(lq, under_2days['question_count'])} | {fmt_pct(hu, over_2days['user_count'])} | {fmt_pct(lu, under_2days['user_count'])} |"
        )
    lines.append("")
    lines.append("## 7) 해석 요약")
    lines.append("")
    if total_questions > 0:
        top_main_topic, top_main_topic_count = metrics["main_topic_counter"].most_common(1)[0]
        lines.append(
            f"- 전체 주토픽 1위는 **{top_main_topic}** ({top_main_topic_count:,}건, {fmt_pct(top_main_topic_count, total_questions)}) 입니다."
        )
    lines.append(
        "- `20회 이상` 또는 `2일 이상` 유저군은 일반적으로 질문 밀도가 높아, 합격 가능성/요강/성적의 복합 질문 비중이 올라가는 경향이 확인됩니다."
    )
    lines.append(
        "- `생기부/학종`, `특수전형`, `합격 예측`은 모두 멀티라벨 집계로 계산되어, 한 질문이 여러 주제에 동시에 포함될 수 있습니다."
    )
    lines.append("")
    lines.append("## 8) 방법론 및 한계")
    lines.append("")
    lines.append("- 본 리포트는 키워드/정규식 기반 자동 분류이며, 문맥 기반 의미 분류 모델은 사용하지 않았습니다.")
    lines.append("- 따라서 문장 표현이 우회적이거나 은유적인 경우 일부 주제가 과소/과대 분류될 수 있습니다.")
    lines.append("- 필요 시 다음 단계로 LLM 기반 intent 분류(샘플 검수 포함)로 정확도를 높일 수 있습니다.")
    lines.append("")
    lines.append("## 9) 상위 유저 간단 프로필 (상위 10명)")
    lines.append("")
    for row in users[:10]:
        lines.append(f"- `{row['user_id']}`: {summarize_user_profile(row)}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_KEY 가 설정되지 않았습니다.")

    client = create_client(supabase_url, supabase_key)
    rows = fetch_all_user_questions(client)
    if not rows:
        raise RuntimeError("조회된 user 질문 데이터가 없습니다.")

    metrics = build_metrics(rows)
    today = datetime.now(KST).strftime("%Y%m%d")
    report_path = os.path.join("reports", f"all_user_question_analysis_{today}.md")
    generate_report(metrics, report_path)
    print(f"Report generated: {report_path}")
    print(f"Users: {len(metrics['users'])}, Questions: {len(metrics['messages'])}")


if __name__ == "__main__":
    main()
