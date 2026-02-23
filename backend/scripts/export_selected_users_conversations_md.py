#!/usr/bin/env python3
"""
Export full conversations for selected users into markdown.

Usage:
  ./venv/bin/python scripts/export_selected_users_conversations_md.py
  ./venv/bin/python scripts/export_selected_users_conversations_md.py --users <uuid1,uuid2,...>
"""

import argparse
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List

from dotenv import load_dotenv
from supabase import create_client


KST = timezone(timedelta(hours=9))

DEFAULT_USERS = [
    "e1ff32c2-7103-4d26-8392-7b68e605660a",
    "76fdc1c6-e5f0-47b3-b903-82a1f7bff47b",
    "a4b1a439-c040-484b-a709-ac2c5a105919",
    "1096616c-9f4b-45e0-9b92-4ff95efc9f16",
    "e4c58342-2a1d-40c9-9860-41c808cc8831",
    "0c6acc04-5f04-43e6-939c-e3f67dd1f3fd",
    "ac1499ea-418f-4ff6-b35a-1bb45b2a1358",
    "4f2c2881-e2fe-45ca-94ba-14ba40520989",
    "423dd754-e961-4e64-a185-7512ed25a020",
    "559a4d08-2db6-46b4-acb8-b0fc337aa173",
    "7e64f182-6c23-41c6-805d-55b4bcd49ace",
]

TOPIC_RULES = {
    "생기부/학종 분석": ["생기부", "학생부", "세특", "행특", "자소서", "학종", "학생부종합", "종합전형"],
    "특수전형": ["농어촌", "장애", "장애전형", "차상위", "기초생활", "기회균형", "저소득", "보훈", "국가유공자"],
    "합격 예측/지원 가능성": ["합격", "가능", "붙을", "붙을까", "추합", "소신", "적정", "안정", "컷", "입결"],
    "전형 요강/지원 조건": ["요강", "모집요강", "전형", "수시", "정시", "논술", "면접", "최저", "지원자격", "모집인원"],
    "성적/환산/컷": ["등급", "내신", "백분위", "표준점수", "점수", "환산", "표점", "모의고사"],
    "대학/학과 탐색": ["대학교", "대학", "학과", "전공", "학부", "어디 갈 수", "추천"],
    "학습 전략/공부법": ["공부", "학습", "플랜", "계획", "커리큘럼", "인강", "문제집", "노베이스", "재수"],
}

TOKEN_STOPWORDS = {
    "그리고",
    "그래서",
    "근데",
    "그냥",
    "정도",
    "이번",
    "저는",
    "내가",
    "제가",
    "해주세요",
    "알려줘",
    "알려주세요",
    "가능",
    "합격",
    "대학",
    "학과",
    "정시",
    "수시",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--users",
        type=str,
        default="",
        help="Comma separated user IDs",
    )
    return parser.parse_args()


def parse_dt(date_text: str) -> datetime:
    if not date_text:
        return datetime.now(timezone.utc)
    text = date_text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        m = re.match(r"^(.*T\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})$", text)
        if not m:
            raise
        base, frac, tz = m.groups()
        frac = (frac + "000000")[:6]
        dt = datetime.fromisoformat(f"{base}.{frac}{tz}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_topics(text: str) -> List[str]:
    t = (text or "").lower()
    matched = []
    for topic, keywords in TOPIC_RULES.items():
        if any(k.lower() in t for k in keywords):
            matched.append(topic)
    return matched if matched else ["기타"]


def top_keywords(texts: List[str], top_n: int = 12) -> List[str]:
    counter = Counter()
    for text in texts:
        for tok in re.findall(r"[가-힣A-Za-z]{2,}", text):
            tok = tok.lower()
            if tok in TOKEN_STOPWORDS:
                continue
            if len(tok) < 2:
                continue
            counter[tok] += 1
    return [k for k, _ in counter.most_common(top_n)]


def fetch_user_messages(client, user_id: str) -> List[Dict]:
    rows = []
    offset = 0
    page_size = 1000
    while True:
        res = (
            client.table("session_chat_messages")
            .select("user_id,user_session,role,content,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        data = res.data or []
        if not data:
            break
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return rows


def build_report_for_user(user_id: str, rows: List[Dict]) -> List[str]:
    lines: List[str] = []
    user_msgs = [r for r in rows if r.get("role") == "user"]
    assistant_msgs = [r for r in rows if r.get("role") == "assistant"]
    sessions = defaultdict(list)
    for r in rows:
        sessions[r.get("user_session") or "no-session"].append(r)

    times = [parse_dt(r.get("created_at")) for r in rows]
    start_dt = min(times).astimezone(KST) if times else None
    end_dt = max(times).astimezone(KST) if times else None
    active_days = len({t.astimezone(KST).date().isoformat() for t in times})

    topic_counter = Counter()
    for r in user_msgs:
        for topic in classify_topics(r.get("content") or ""):
            topic_counter[topic] += 1

    keywords = top_keywords([r.get("content") or "" for r in user_msgs], top_n=12)

    lines.append(f"## `{user_id}`")
    lines.append("")
    lines.append(f"- 전체 메시지: **{len(rows)}건** (user {len(user_msgs)} / assistant {len(assistant_msgs)})")
    lines.append(f"- 세션 수: **{len(sessions)}개**")
    lines.append(f"- 활동일 수(KST): **{active_days}일**")
    if start_dt and end_dt:
        lines.append(f"- 대화 기간(KST): **{start_dt.strftime('%Y-%m-%d %H:%M')} ~ {end_dt.strftime('%Y-%m-%d %H:%M')}**")
    if topic_counter:
        top_topics = ", ".join([f"{k}({v})" for k, v in topic_counter.most_common(5)])
        lines.append(f"- 주요 질문 토픽: {top_topics}")
    if keywords:
        lines.append(f"- 자주 나온 키워드: {', '.join(keywords)}")
    lines.append("")
    lines.append("### 세션 요약")
    lines.append("")
    lines.append("| 세션 | 시작(KST) | 종료(KST) | user 질문 수 | assistant 응답 수 |")
    lines.append("|---|---|---|---:|---:|")
    for sid, msgs in sorted(
        sessions.items(),
        key=lambda x: parse_dt(x[1][0].get("created_at")).timestamp() if x[1] else 0,
    ):
        s_times = [parse_dt(m.get("created_at")) for m in msgs]
        start = min(s_times).astimezone(KST).strftime("%Y-%m-%d %H:%M")
        end = max(s_times).astimezone(KST).strftime("%Y-%m-%d %H:%M")
        u_cnt = sum(1 for m in msgs if m.get("role") == "user")
        a_cnt = sum(1 for m in msgs if m.get("role") == "assistant")
        lines.append(f"| `{sid}` | {start} | {end} | {u_cnt} | {a_cnt} |")
    lines.append("")

    lines.append("### 전체 대화 원문")
    lines.append("")
    for sid, msgs in sorted(
        sessions.items(),
        key=lambda x: parse_dt(x[1][0].get("created_at")).timestamp() if x[1] else 0,
    ):
        lines.append(f"#### Session `{sid}`")
        lines.append("")
        for idx, m in enumerate(msgs, 1):
            ts = parse_dt(m.get("created_at")).astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")
            role = "USER" if m.get("role") == "user" else "ASSISTANT"
            content = (m.get("content") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
            lines.append(f"{idx}. `{ts}` **{role}**")
            lines.append("")
            if content:
                lines.append(content)
            else:
                lines.append("(empty)")
            lines.append("")
        lines.append("---")
        lines.append("")

    return lines


def main() -> None:
    args = parse_args()
    users = [u.strip() for u in args.users.split(",") if u.strip()] if args.users else DEFAULT_USERS

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")

    client = create_client(url, key)

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    today = datetime.now(KST).strftime("%Y%m%d")
    out_path = os.path.join("reports", f"selected_users_full_conversations_{today}.md")

    lines: List[str] = []
    lines.append("# 특정 유저 전체 대화 정리 리포트")
    lines.append("")
    lines.append(f"- 생성 시각: {now}")
    lines.append("- 데이터 소스: `session_chat_messages`")
    lines.append("- 기준: 선택한 user_id의 `role=user/assistant` 전체 메시지")
    lines.append(f"- 대상 유저 수: **{len(users)}명**")
    lines.append("")
    lines.append("## 대상 user_id")
    lines.append("")
    for i, uid in enumerate(users, 1):
        lines.append(f"{i}. `{uid}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_msgs = 0
    for uid in users:
        rows = fetch_user_messages(client, uid)
        total_msgs += len(rows)
        lines.extend(build_report_for_user(uid, rows))
        lines.append("")

    lines.insert(6, f"- 전체 메시지 수: **{total_msgs:,}건**")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Report generated: {out_path}")
    print(f"Users: {len(users)}, Messages: {total_msgs}")


if __name__ == "__main__":
    main()
