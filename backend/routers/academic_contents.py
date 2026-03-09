"""
학술 자료 업로드 · RAG 검색 라우터 (독립 모듈)
- 텍스트를 구조적으로 청크 분할 → Gemini 임베딩 → Supabase 저장
- 유사도 검색 + 인접 청크 윈도우 전략
"""
from __future__ import annotations

import json
import os
import re
import textwrap
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel

from middleware.auth import get_current_user, optional_auth_with_state
from services.supabase_client import supabase_service

router = APIRouter()

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768
MAX_CHUNK_CHARS = 4000
OVERLAP_CHARS = 200
EMBED_STORE_BATCH_SIZE = 50


# ─── Pydantic 모델 ───────────────────────────────────────────

class TextUploadRequest(BaseModel):
    """프론트엔드에서 텍스트를 직접 붙여넣어 업로드할 때 사용."""
    source_title: str = ""
    raw_text: str
    chunk_strategy: str = "auto"  # auto | heading | fixed


class SearchRequest(BaseModel):
    query: str
    match_count: int = 5
    context_window: int = 1


class ContentItem(BaseModel):
    source_title: str = ""
    chapter: str = ""
    part: str = ""
    sub_section: str = ""
    chunk_index: int = 0
    raw_content: str
    metadata: Dict[str, Any] = {}


class BulkUploadRequest(BaseModel):
    """Python 스크립트에서 이미 청크 분할된 데이터를 일괄 업로드."""
    items: List[ContentItem]


# ─── Gemini 생성 모델 유틸 ───────────────────────────────────


GEMINI_CLASSIFY_MODEL = os.getenv("GEMINI_CLASSIFY_MODEL", "models/gemini-2.0-flash-lite")


def _get_gemini_model():
    """표/텍스트 분류용 Gemini 모델 인스턴스 반환."""
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

    return genai.GenerativeModel(
        model_name=GEMINI_CLASSIFY_MODEL,
        generation_config={
            "temperature": 0.0,
            "max_output_tokens": 4096,
        },
    )


def _classify_blocks_with_gemini(blocks: List[str]) -> List[Dict[str, str]]:
    """텍스트 블록 리스트를 Gemini로 table/text 분류.

    Args:
        blocks: 분류할 텍스트 블록 리스트 (빈 줄 기준으로 분리된 조각들)

    Returns:
        각 블록의 type("table" 또는 "text")를 담은 리스트
        예: [{"type": "text"}, {"type": "table"}, ...]
    """
    if not blocks:
        return []

    # 블록이 너무 많으면 배치 처리 (Gemini 토큰 제한 고려)
    BATCH_SIZE = 30
    MAX_BLOCK_CHARS = 3000  # 블록당 최대 문자 수

    all_results: List[Dict[str, str]] = []

    for batch_start in range(0, len(blocks), BATCH_SIZE):
        batch_blocks = blocks[batch_start : batch_start + BATCH_SIZE]
        batch_indices = list(range(batch_start, batch_start + len(batch_blocks)))

        # 프롬프트 구성
        system_prompt = """당신은 텍스트 분류기입니다. 입력된 각 블록이 "표(table)"인지 "일반 텍스트(text)"인지 판단하세요.

**판단 기준:**
- **table**: 마크다운 표(|로 구분), 탭으로 구분된 표, 제목이 붙은 표, 표 형식의 데이터 목록
- **text**: 일반 문단, 제목, 설명, 서론/결론 등

**출력 형식 (JSON):**
{"results": [{"index": 0, "type": "table"}, {"index": 1, "type": "text"}, ...]}

**주의:**
- 표가 포함된 블록은 무조건 "table"로 분류
- 표와 텍스트가 섞여 있으면 표가 있으면 "table"
- JSON만 출력, 다른 설명 금지"""

        # 블록 내용 추가 (너무 긴 블록은 잘라서)
        blocks_text = []
        for i, block in enumerate(batch_blocks):
            display_block = block[:MAX_BLOCK_CHARS] + "...(중략)" if len(block) > MAX_BLOCK_CHARS else block
            # JSON escape 처리
            display_block = display_block.replace("\"", "\\\"").replace("\n", "\\n")
            blocks_text.append(f"[BLOCK {batch_indices[i]}]\n{display_block}\n---")

        user_prompt = f"아래 블록들을 분류하세요:\n\n" + "\n".join(blocks_text)

        try:
            model = _get_gemini_model()
            response = model.generate_content(
                f"{system_prompt}\n\n{user_prompt}",
                request_options={"timeout": 60.0},
            )

            response_text = response.text.strip()

            # JSON 파싱 시도
            try:
                # 코드 블록 마크다운 제거
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                data = json.loads(response_text)
                results = data.get("results", [])

                # 인덱스 정렬 및 검증
                batch_results = []
                for i in range(len(batch_blocks)):
                    found = next((r for r in results if r.get("index") == batch_indices[i]), None)
                    if found and found.get("type") in ("table", "text"):
                        batch_results.append({"type": found["type"]})
                    else:
                        # 기본값: 탭이나 |가 많으면 table, 아니면 text
                        block_lower = batch_blocks[i].lower()
                        is_table = (
                            block_lower.count("|") >= 4 or
                            block_lower.count("\t") >= 2 or
                            "---" in batch_blocks[i] or
                            block_lower.count(":---") > 0
                        )
                        batch_results.append({"type": "table" if is_table else "text"})

                all_results.extend(batch_results)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Gemini 응답 파싱 실패: {e}, fallback to rule-based")
                # 파싱 실패 시 규칙 기반 폴백
                for block in batch_blocks:
                    block_lower = block.lower()
                    is_table = (
                        block_lower.count("|") >= 4 or
                        block_lower.count("\t") >= 2 or
                        "---" in block or
                        block_lower.count(":---") > 0
                    )
                    all_results.append({"type": "table" if is_table else "text"})

        except Exception as e:
            print(f"⚠️ Gemini API 오류: {e}, fallback to rule-based")
            # API 실패 시 규칙 기반 폴백
            for block in batch_blocks:
                block_lower = block.lower()
                is_table = (
                    block_lower.count("|") >= 4 or
                    block_lower.count("\t") >= 2 or
                    "---" in block or
                    block_lower.count(":---") > 0
                )
                all_results.append({"type": "table" if is_table else "text"})

    return all_results


# ─── 임베딩 유틸 ─────────────────────────────────────────────

def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Gemini text-embedding-004 로 텍스트 리스트를 임베딩."""
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

    embeddings: List[List[float]] = []
    batch_size = 20
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=batch,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768,
        )
        if isinstance(result["embedding"][0], list):
            embeddings.extend(result["embedding"])
        else:
            embeddings.append(result["embedding"])

    return embeddings


def _embed_query(text: str) -> List[float]:
    """검색 쿼리를 임베딩."""
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

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=768,
    )
    return result["embedding"]


# ─── 청크 분할 ───────────────────────────────────────────────

_HEADING_RE = re.compile(
    r"^(?:"
    r"#{1,4}\s+"                       # Markdown headings
    r"|Part\s+\d+"                     # Part 1, Part 2 ...
    r"|제?\s*\d+\s*(?:장|절|편|부|항)"  # 제1장, 1절, ...
    r"|(?:Chapter|Section)\s+\d+"      # English
    r"|\d+\.\s+"                       # 1. 2. 3. ...
    r")",
    re.MULTILINE | re.IGNORECASE,
)


def _split_by_headings(text: str) -> List[Dict[str, str]]:
    """제목/헤딩 기반으로 텍스트 분할."""
    positions = [m.start() for m in _HEADING_RE.finditer(text)]
    if not positions:
        return [{"heading": "", "body": text}]
    if positions[0] != 0:
        positions.insert(0, 0)

    chunks: List[Dict[str, str]] = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        segment = text[start:end].strip()
        if not segment:
            continue
        first_line_end = segment.find("\n")
        if first_line_end > 0:
            heading = segment[:first_line_end].strip()
            body = segment[first_line_end:].strip()
        else:
            heading = segment
            body = ""
        chunks.append({"heading": heading, "body": body or heading})
    return chunks


def _split_fixed(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    """고정 길이 + 오버랩 분할."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ─── 표 감지 및 듀얼 청킹 유틸 ──────────────────────────────────

# 정규식 기반 표 감지 (Gemini 폴백용)
_MD_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_MD_TABLE_SEP_RE = re.compile(
    r"^\s*\|[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)*\|?\s*$"
)
_TSV_MIN_TABS = 2


def _is_md_table_line(line: str) -> bool:
    """마크다운 표 행 또는 구분선인지 판별."""
    s = line.strip()
    if not s:
        return False
    return bool(_MD_TABLE_ROW_RE.match(s)) or bool(_MD_TABLE_SEP_RE.match(s))


def _is_tsv_table_line(line: str) -> bool:
    """탭 구분 표 행인지 판별 (탭 2개 이상)."""
    return "\t" in line and line.count("\t") >= _TSV_MIN_TABS


def _detect_segments(text: str) -> List[Dict[str, Any]]:
    """텍스트를 text / table 세그먼트로 분리 (정규식 기반, Gemini 폴백용).

    연속된 마크다운 표 행 또는 TSV 행을 하나의 table 세그먼트로 묶고,
    나머지를 text 세그먼트로 분리한다.
    """
    lines = text.split("\n")
    segments: List[Dict[str, Any]] = []
    buf: List[str] = []
    buf_type = "text"

    def flush():
        nonlocal buf, buf_type
        content = "\n".join(buf).strip()
        if content:
            segments.append({"type": buf_type, "content": content})
        buf = []
        buf_type = "text"

    for i, line in enumerate(lines):
        is_tbl = _is_md_table_line(line) or _is_tsv_table_line(line)

        if is_tbl:
            if buf_type != "table":
                flush()
                buf_type = "table"
            buf.append(line)
        else:
            if buf_type == "table":
                # 빈 줄 뒤에 바로 표 행이 이어지면 표 내부 공백으로 간주
                if not line.strip() and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if _is_md_table_line(next_line) or _is_tsv_table_line(next_line):
                        buf.append(line)
                        continue
                flush()
                buf.append(line)
            else:
                buf.append(line)

    flush()
    return segments


def _split_into_blocks(text: str, max_block_chars: int = 8000) -> List[str]:
    """텍스트를 빈 줄 기준으로 블록 분할.

    너무 긴 블록은 문장/줄 경계를 존중하며 청크로 나눈다.
    """
    # 연속된 빈 줄로 분리
    raw_blocks = re.split(r"\n{2,}", text.strip())
    blocks: List[str] = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        if len(block) <= max_block_chars:
            blocks.append(block)
        else:
            # 긴 블록은 줄 단위로 나눠서 청크
            lines = block.split("\n")
            current_chunk: List[str] = []
            current_len = 0

            for line in lines:
                line_len = len(line) + 1  # 개행 포함
                if current_len + line_len > max_block_chars and current_chunk:
                    blocks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_len = line_len
                else:
                    current_chunk.append(line)
                    current_len += line_len

            if current_chunk:
                blocks.append("\n".join(current_chunk))

    return [b for b in blocks if b.strip()]


def _detect_segments_with_gemini(text: str) -> List[Dict[str, Any]]:
    """Gemini로 표/텍스트 분류하여 세그먼트 분리 (권장 방식).

    1. 빈 줄 기준으로 블록 분할
    2. Gemini로 각 블록이 table인지 text인지 분류
    3. 인접한 같은 타입 블록을 하나의 세그먼트로 병합

    Args:
        text: 분석할 원문 텍스트

    Returns:
        [{"type": "text"|"table", "content": "..."}, ...]
    """
    blocks = _split_into_blocks(text)
    if not blocks:
        return []

    # Gemini로 분류
    classifications = _classify_blocks_with_gemini(blocks)

    # 같은 타입의 연속된 블록을 병합
    segments: List[Dict[str, Any]] = []
    current_type: Optional[str] = None
    current_content_parts: List[str] = []

    for i, block in enumerate(blocks):
        block_type = classifications[i]["type"] if i < len(classifications) else "text"

        if block_type == current_type:
            current_content_parts.append(block)
        else:
            # 이전 세그먼트 저장
            if current_type and current_content_parts:
                merged = "\n\n".join(current_content_parts)
                segments.append({"type": current_type, "content": merged})
            # 새 세그먼트 시작
            current_type = block_type
            current_content_parts = [block]

    # 마지막 세그먼트 저장
    if current_type and current_content_parts:
        merged = "\n\n".join(current_content_parts)
        segments.append({"type": current_type, "content": merged})

    return segments


def _extract_table_header(table_text: str):
    """표에서 헤더 블록(헤더행 + 구분선)과 데이터 행을 분리.

    Returns: (header_block: str, data_lines: List[str])
    """
    lines = [l for l in table_text.strip().split("\n") if l.strip()]
    if not lines:
        return "", []

    sep_idx = -1
    for i, line in enumerate(lines):
        if bool(_MD_TABLE_SEP_RE.match(line.strip())):
            sep_idx = i
            break

    if sep_idx >= 0:
        header_block = "\n".join(lines[: sep_idx + 1])
        data_lines = lines[sep_idx + 1:]
        return header_block, data_lines

    return lines[0], lines[1:]


def _split_table_with_header(
    table_text: str,
    max_chars: int = MAX_CHUNK_CHARS,
) -> List[str]:
    """큰 표를 헤더를 반복 삽입하며 행 단위로 분할."""
    if len(table_text) <= max_chars:
        return [table_text]

    header_block, data_lines = _extract_table_header(table_text)
    if not data_lines:
        return _split_fixed(table_text, max_chars)

    header_len = len(header_block) + 1
    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = header_len

    for line in data_lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current_lines:
            chunks.append(header_block + "\n" + "\n".join(current_lines))
            current_lines = []
            current_len = header_len
        current_lines.append(line)
        current_len += line_len

    if current_lines:
        chunks.append(header_block + "\n" + "\n".join(current_lines))

    return chunks or [table_text]


def _parse_table_cells(table_text: str):
    """표 텍스트에서 (headers, data_rows) 추출.

    Returns: (headers: List[str], data_rows: List[List[str]])
    """
    lines = [l for l in table_text.strip().split("\n") if l.strip()]
    if not lines:
        return [], []

    headers: List[str] = []
    data_rows: List[List[str]] = []
    is_md = "|" in lines[0]

    if is_md:
        sep_idx = -1
        for i, line in enumerate(lines):
            if bool(_MD_TABLE_SEP_RE.match(line.strip())):
                sep_idx = i
                break

        header_line_idx = max(0, sep_idx - 1) if sep_idx >= 1 else 0
        headers = [h.strip() for h in lines[header_line_idx].split("|") if h.strip()]

        start = (sep_idx + 1) if sep_idx >= 0 else 1
        for line in lines[start:]:
            if bool(_MD_TABLE_SEP_RE.match(line.strip())):
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if cells:
                data_rows.append(cells)
    else:
        # TSV
        headers = [p.strip() for p in lines[0].split("\t") if p.strip()]
        for line in lines[1:]:
            cells = [c.strip() for c in line.split("\t")]
            if any(c for c in cells):
                data_rows.append(cells)

    return headers, data_rows


def _summarize_table(
    table_text: str,
    heading: str = "",
    preceding_context: str = "",
) -> str:
    """표의 자연어 요약 생성 (임베딩 검색 품질 향상용 듀얼 청크).

    컬럼명, 행 수, 샘플 데이터, 주요 컬럼 고유 값 목록을 포함하여
    벡터 검색 시 의미 기반 매칭이 잘 되도록 한다.
    """
    headers, data_rows = _parse_table_cells(table_text)
    if not headers and not data_rows:
        return ""

    parts: List[str] = []

    if heading:
        parts.append(f"[표 제목] {heading}")
    if preceding_context:
        ctx = preceding_context.strip()
        if len(ctx) > 200:
            ctx = ctx[-200:]
        parts.append(f"[선행 맥락] {ctx}")

    if headers:
        parts.append(f"[컬럼({len(headers)}개)] {', '.join(headers)}")
    parts.append(f"[데이터 행 수] {len(data_rows)}개")

    sample_n = min(5, len(data_rows))
    if sample_n > 0:
        parts.append("[샘플 데이터]")
        for row in data_rows[:sample_n]:
            if headers:
                pairs = [
                    f"{headers[j]}={cell}"
                    for j, cell in enumerate(row)
                    if j < len(headers)
                ]
                parts.append(f"  {', '.join(pairs)}")
            else:
                parts.append(f"  {', '.join(row)}")
        if len(data_rows) > sample_n:
            parts.append(f"  ... 외 {len(data_rows) - sample_n}개 행")

    # 주요 컬럼 고유 값 목록 (검색 히트율 향상)
    if headers and data_rows:
        for col_idx in range(min(len(headers), 3)):
            vals: set = set()
            for row in data_rows:
                if col_idx < len(row) and row[col_idx].strip():
                    vals.add(row[col_idx].strip())
            if 1 < len(vals) <= 20:
                parts.append(
                    f"[{headers[col_idx]} 전체 목록] {', '.join(sorted(vals))}"
                )

    return "\n".join(parts)


# ─── 듀얼 청킹 (텍스트 + 표) ────────────────────────────────────


def _chunk_text_block(
    text: str, source_title: str, start_idx: int,
) -> List[ContentItem]:
    """텍스트 블록을 헤딩 기반 + 고정 길이 분할 (표가 아닌 구간용)."""
    heading_chunks = _split_by_headings(text)
    items: List[ContentItem] = []
    idx = start_idx

    for hc in heading_chunks:
        body = hc["body"]
        heading = hc["heading"]

        if len(body) <= MAX_CHUNK_CHARS:
            items.append(ContentItem(
                source_title=source_title,
                chapter=heading,
                part="",
                sub_section="",
                chunk_index=idx,
                raw_content=body,
                metadata={"heading": heading, "content_type": "text"},
            ))
            idx += 1
        else:
            sub_chunks = _split_fixed(body)
            for si, sc in enumerate(sub_chunks):
                items.append(ContentItem(
                    source_title=source_title,
                    chapter=heading,
                    part=f"chunk_{si + 1}",
                    sub_section="",
                    chunk_index=idx,
                    raw_content=sc,
                    metadata={
                        "heading": heading,
                        "sub_chunk": si + 1,
                        "content_type": "text",
                    },
                ))
                idx += 1

    return items


def _chunk_table_block(
    table_text: str,
    source_title: str,
    heading: str,
    preceding_context: str,
    start_idx: int,
) -> List[ContentItem]:
    """표 블록 → 원문 청크 + 요약 청크 (듀얼 청킹).

    1) 원문 표: 큰 표는 헤더를 반복 삽입하여 행 단위 분할
    2) 요약 청크: 컬럼명·행 수·샘플·고유값 목록을 자연어로 정리
    """
    items: List[ContentItem] = []
    idx = start_idx
    table_start_idx = idx

    table_chunks = _split_table_with_header(table_text)
    for ti, tc in enumerate(table_chunks):
        items.append(ContentItem(
            source_title=source_title,
            chapter=heading,
            part=f"table_part_{ti + 1}" if len(table_chunks) > 1 else "",
            sub_section="",
            chunk_index=idx,
            raw_content=tc,
            metadata={
                "content_type": "table",
                "table_part": ti + 1,
                "table_total_parts": len(table_chunks),
                "heading": heading,
            },
        ))
        idx += 1

    summary = _summarize_table(
        table_text, heading=heading, preceding_context=preceding_context,
    )
    if summary and len(summary.strip()) > 20:
        items.append(ContentItem(
            source_title=source_title,
            chapter=heading,
            part="table_summary",
            sub_section="",
            chunk_index=idx,
            raw_content=summary,
            metadata={
                "content_type": "table_summary",
                "table_raw_chunk_indices": list(
                    range(table_start_idx, table_start_idx + len(table_chunks))
                ),
                "heading": heading,
            },
        ))
        idx += 1

    return items


def _auto_chunk(
    raw_text: str,
    source_title: str,
    use_gemini: bool = True,
) -> List[ContentItem]:
    """듀얼 청킹: 표 감지 → 원문 + 요약 이중 저장, 텍스트는 헤딩+고정 분할.

    Args:
        raw_text: 분석할 원문 텍스트
        source_title: 자료 제목
        use_gemini: True면 Gemini로 표/텍스트 분류, False면 정규식 기반 (폴백용)

    1. 텍스트를 text / table 세그먼트로 분리 (Gemini 또는 정규식)
    2. text 세그먼트: 기존 헤딩 기반 + 고정 길이 청킹
    3. table 세그먼트: 원문 보존(헤더 반복 분할) + 자연어 요약 청크 추가
    """
    # 세그먼트 분리 (Gemini 우선, 실패 시 정규식 폴백)
    if use_gemini:
        try:
            segments = _detect_segments_with_gemini(raw_text)
        except Exception as e:
            print(f"⚠️ Gemini 분류 실패, 정규식 폴백: {e}")
            segments = _detect_segments(raw_text)
    else:
        segments = _detect_segments(raw_text)

    has_table = any(s["type"] == "table" for s in segments)

    if not has_table:
        return _chunk_text_block(raw_text, source_title, start_idx=0)

    items: List[ContentItem] = []
    idx = 0
    last_heading = ""
    prev_text_tail = ""

    for seg in segments:
        if seg["type"] == "text":
            text_items = _chunk_text_block(
                seg["content"], source_title, start_idx=idx,
            )
            items.extend(text_items)
            idx += len(text_items)
            for ti in reversed(text_items):
                if ti.chapter:
                    last_heading = ti.chapter
                    break
            prev_text_tail = seg["content"].strip()[-300:]

        elif seg["type"] == "table":
            table_items = _chunk_table_block(
                table_text=seg["content"],
                source_title=source_title,
                heading=last_heading,
                preceding_context=prev_text_tail,
                start_idx=idx,
            )
            items.extend(table_items)
            idx += len(table_items)

    return items or _chunk_text_block(raw_text, source_title, start_idx=0)


def _decode_uploaded_text(raw_bytes: bytes) -> str:
    """업로드된 bytes를 안전하게 문자열로 디코딩."""
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(
        status_code=400,
        detail="파일 인코딩을 해석할 수 없습니다. UTF-8(.md/.txt) 파일로 다시 저장해 주세요.",
    )


def _store_academic_content(
    raw_text: str,
    source_title: str,
    user_id: str,
) -> Dict[str, Any]:
    """텍스트를 청킹/임베딩 후 DB에 저장.

    전체 청크의 임베딩/DB row를 한 번에 메모리에 올리지 않고 배치 처리해
    대용량 md/txt 업로드 시 메모리 피크를 낮춘다.
    """
    items = _auto_chunk(raw_text, source_title)
    if not items:
        raise HTTPException(status_code=400, detail="청크 분할 결과가 없습니다.")

    client = supabase_service.get_admin_client()
    inserted = 0
    total_chars = 0

    for batch_start in range(0, len(items), EMBED_STORE_BATCH_SIZE):
        batch_items = items[batch_start : batch_start + EMBED_STORE_BATCH_SIZE]
        texts_to_embed = [item.raw_content for item in batch_items]

        try:
            embeddings = _embed_texts(texts_to_embed)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"임베딩 실패: {e}")

        rows = []
        for item, emb in zip(batch_items, embeddings):
            rows.append({
                "source_title": item.source_title,
                "chapter": item.chapter,
                "part": item.part,
                "sub_section": item.sub_section,
                "chunk_index": item.chunk_index,
                "raw_content": item.raw_content,
                "metadata": {**item.metadata, "uploaded_by": user_id},
                "embedding": emb,
            })
            total_chars += len(item.raw_content)

        try:
            client.table("academic_contents").insert(rows).execute()
            inserted += len(rows)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"DB 저장 실패 (batch {batch_start // EMBED_STORE_BATCH_SIZE}): {e}",
            )

    return {
        "ok": True,
        "source_title": source_title,
        "chunk_count": inserted,
        "total_chars": total_chars,
    }


# ─── 엔드포인트 ──────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/upload-text")
async def upload_text(
    request: TextUploadRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """프론트엔드에서 텍스트를 붙여넣어 업로드."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    raw_text = request.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")

    source_title = request.source_title.strip() or f"직접입력_{int(time.time())}"
    return _store_academic_content(raw_text, source_title, user["user_id"])


@router.post("/upload-file")
async def upload_file(
    http_request: Request,
    file: UploadFile = File(...),
    source_title: str = Form(""),
    authorization: Optional[str] = Header(None),
):
    """마크다운/텍스트 파일(.md/.txt)을 업로드."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    filename = (file.filename or "").strip()
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".md", ".txt"}:
        raise HTTPException(status_code=400, detail=".md 또는 .txt 파일만 업로드할 수 있습니다.")

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    await file.seek(0)
    if file_size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일이 너무 큽니다. 5MB 이하 파일만 업로드해 주세요.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="파일 내용이 비어있습니다.")

    raw_text = _decode_uploaded_text(raw_bytes).strip()
    del raw_bytes
    if not raw_text:
        raise HTTPException(status_code=400, detail="텍스트가 비어있습니다.")

    stem = os.path.splitext(os.path.basename(filename))[0]
    resolved_title = source_title.strip() or stem or f"파일업로드_{int(time.time())}"
    return _store_academic_content(raw_text, resolved_title, user["user_id"])


@router.post("/bulk-upload")
async def bulk_upload(
    request: BulkUploadRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """Python 스크립트에서 이미 분할된 청크를 일괄 업로드."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    if not request.items:
        raise HTTPException(status_code=400, detail="items가 비어있습니다.")

    texts_to_embed = [item.raw_content for item in request.items]
    try:
        embeddings = _embed_texts(texts_to_embed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"임베딩 실패: {e}")

    client = supabase_service.get_admin_client()
    rows = []
    for item, emb in zip(request.items, embeddings):
        rows.append({
            "source_title": item.source_title,
            "chapter": item.chapter,
            "part": item.part,
            "sub_section": item.sub_section,
            "chunk_index": item.chunk_index,
            "raw_content": item.raw_content,
            "metadata": {**item.metadata, "uploaded_by": user["user_id"]},
            "embedding": emb,
        })

    batch_size = 50
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table("academic_contents").insert(batch).execute()
            inserted += len(batch)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"DB 저장 실패 (batch {i // batch_size}): {e}",
            )

    return {
        "ok": True,
        "inserted_count": inserted,
        "total_chars": sum(len(r["raw_content"]) for r in rows),
    }


@router.post("/search")
async def search_contents(
    request: SearchRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """유사도 검색 + 인접 청크 윈도우."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="검색어가 비어있습니다.")

    try:
        query_emb = _embed_query(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"쿼리 임베딩 실패: {e}")

    client = supabase_service.get_admin_client()

    try:
        result = client.rpc(
            "match_academic_contents",
            {
                "query_embedding": query_emb,
                "match_count": request.match_count,
                "context_window": request.context_window,
            },
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 실패: {e}")

    return {"ok": True, "results": result.data or []}


@router.get("/list")
async def list_sources(
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """업로드된 source_title 목록."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    client = supabase_service.get_admin_client()
    try:
        result = (
            client.table("academic_contents")
            .select("source_title, count", count="exact")
            .order("created_at", desc=True)
            .execute()
        )
        titles_seen: dict = {}
        for row in result.data or []:
            t = row.get("source_title", "")
            if t not in titles_seen:
                titles_seen[t] = 0
            titles_seen[t] += 1
        sources = [{"source_title": k, "chunk_count": v} for k, v in titles_seen.items()]
    except Exception:
        sources = []

    return {"ok": True, "sources": sources}


@router.delete("/delete/{source_title}")
async def delete_source(
    source_title: str,
    http_request: Request,
    authorization: Optional[str] = Header(None),
):
    """특정 source_title의 모든 청크 삭제."""
    auth_header = authorization or (
        http_request.headers.get("authorization") if http_request else None
    )
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    client = supabase_service.get_admin_client()
    try:
        client.table("academic_contents").delete().eq("source_title", source_title).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"삭제 실패: {e}")

    return {"ok": True, "deleted_source": source_title}
