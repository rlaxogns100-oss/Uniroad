#!/usr/bin/env python3
"""
대학교 문서 청크에서 정시 전형별 점수 환산법을 추출하는 스크립트.

요구사항 반영:
- Azure OpenAI 모델 사용 (기본: gpt-5-mini)
- 재처리/백업 모델 없음
- 청크 점수선택 없음 (대상 문서 청크 전체 사용)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from openai import AzureOpenAI


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.supabase_client import SupabaseService  # noqa: E402

# backend/.env 명시 로드
load_dotenv(BASE_DIR / ".env", override=False)

DEFAULT_AZURE_MODEL = os.getenv("AZURE_OPENAI_MODEL", "gpt-5-mini")
DEFAULT_AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
OUTPUT_DIR = BASE_DIR / "data" / "extraction_runs"

FORMULA_TYPE_ENUM = [
    "absolute",
    "relative_minmax",
    "piecewise",
    "grade_map",
    "stage_weight",
    "table_result",
]


@dataclass
class ChunkRow:
    id: int
    document_id: int
    chunk_type: str
    page_number: int
    content: str
    raw_data: str
    filename: str
    school_name: str

    @property
    def source_text(self) -> str:
        if self.chunk_type == "table" and self.raw_data:
            return self.raw_data
        return self.content or self.raw_data or ""


def normalize_school_variants(school: str) -> List[str]:
    base = school.strip()
    if not base:
        return []
    variants = [base]
    if base.endswith("학교"):
        short = base[:-2]
        if short:
            variants.append(short)
    else:
        variants.append(base + "학교")
    return list(dict.fromkeys(variants))


def normalize_for_match(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower().strip()


def fetch_school_documents(client: Any, school: str, filename_contains: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    needle = normalize_for_match(filename_contains)

    for variant in normalize_school_variants(school):
        rows = (
            client.table("documents")
            .select("id, school_name, filename")
            .eq("school_name", variant)
            .execute()
            .data
            or []
        )
        for row in rows:
            filename = str(row.get("filename") or "")
            normalized_filename = normalize_for_match(filename)
            if needle and needle not in normalized_filename:
                continue
            docs.append(row)

    uniq: Dict[int, Dict[str, Any]] = {}
    for d in docs:
        uniq[int(d["id"])] = d
    return sorted(uniq.values(), key=lambda x: int(x["id"]))


def fetch_chunks_for_documents(client: Any, docs: List[Dict[str, Any]]) -> List[ChunkRow]:
    if not docs:
        return []

    rows: List[ChunkRow] = []
    for d in docs:
        doc_id = int(d["id"])
        chunk_rows = (
            client.table("document_chunks")
            .select("id, document_id, chunk_type, page_number, content, raw_data")
            .eq("document_id", doc_id)
            .order("page_number", desc=False)
            .order("id", desc=False)
            .execute()
            .data
            or []
        )
        for c in chunk_rows:
            rows.append(
                ChunkRow(
                    id=int(c["id"]),
                    document_id=int(c["document_id"]),
                    chunk_type=str(c.get("chunk_type") or ""),
                    page_number=int(c.get("page_number") or 0),
                    content=str(c.get("content") or ""),
                    raw_data=str(c.get("raw_data") or ""),
                    filename=str(d.get("filename") or ""),
                    school_name=str(d.get("school_name") or ""),
                )
            )
    return rows


def build_context(chunks: List[ChunkRow]) -> Tuple[str, List[int]]:
    lines: List[str] = []
    used_ids: List[int] = []
    for c in chunks:
        text = c.source_text.strip()
        if not text:
            continue
        lines.append(
            f"[chunk_id={c.id} doc_id={c.document_id} school={c.school_name} "
            f"file={c.filename} page={c.page_number} chunk_type={c.chunk_type}]\n{text}\n"
        )
        used_ids.append(c.id)
    return "\n".join(lines), used_ids


def make_extraction_prompt(university: str, filename_contains: str, context: str) -> str:
    return f"""
너는 대학 정시 환산공식 추출기다.
아래 문맥(원문 청크)에서 "정시 전형별 점수 환산법"만 구조화해서 JSON만 출력하라.

중요:
- 추론 금지, 문서에 없는 값은 null
- 입시결과(합격선/경쟁률) 표는 이번 출력에서 제외
- 반드시 근거 페이지와 근거 원문(evidence_text)을 넣어라

JSON 스키마:
{{
  "university": "{university}",
  "document_scope": "{filename_contains}",
  "rules": [
    {{
      "rule_id": "string",
      "admission_type": "정시",
      "track": "string|null",
      "unit_or_major": "string|null",
      "stage": "1단계|2단계|최종|null",
      "formula_type": "absolute|relative_minmax|piecewise|grade_map|stage_weight|table_result",
      "expression": "string|null",
      "piecewise": [{{"if":"string","value":"string"}}],
      "grade_map": {{"1": 0, "2": 0.5}},
      "variables": ["string"],
      "requires_runtime_data": true,
      "runtime_keys": ["cohort_max","cohort_min"],
      "source_page": 0,
      "evidence_text": "string"
    }}
  ]
}}

출력 규칙:
- JSON 외 텍스트 금지
- 동일한 전형이라도 공식/감점표/단계환산은 rule을 분리
- 최고/최저 점수 필요 공식은 requires_runtime_data=true
- 반드시 RFC 8259 strict JSON으로 출력
- evidence_text 값에는 큰따옴표(")를 넣지 말고 작은따옴표(')로 치환
- 줄바꿈은 \\n 이스케이프로만 표현

문맥:
{context}
""".strip()


def extract_json_blob(text: str) -> Dict[str, Any]:
    candidate = text.strip()
    candidate = re.sub(r"^```json\\s*", "", candidate)
    candidate = re.sub(r"^```\\s*", "", candidate)
    candidate = re.sub(r"\\s*```$", "", candidate)
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise ValueError("JSON 객체를 찾을 수 없습니다.")
    return json.loads(match.group(0))


def validate_output(obj: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(obj, dict):
        return ["최상위 JSON이 객체가 아닙니다."]
    for key in ["university", "document_scope", "rules"]:
        if key not in obj:
            errs.append(f"missing_key:{key}")

    rules = obj.get("rules", [])
    if not isinstance(rules, list):
        errs.append("rules_not_list")
        return errs

    if len(rules) == 0:
        errs.append("rules_empty")

    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errs.append(f"rule_{i}_not_object")
            continue
        for k in [
            "rule_id",
            "admission_type",
            "formula_type",
            "requires_runtime_data",
            "source_page",
            "evidence_text",
        ]:
            if k not in rule:
                errs.append(f"rule_{i}_missing_{k}")
        if rule.get("admission_type") != "정시":
            errs.append(f"rule_{i}_admission_type_not_jungsi")
        if rule.get("formula_type") not in FORMULA_TYPE_ENUM:
            errs.append(f"rule_{i}_invalid_formula_type")
    return errs


def get_azure_client(api_version: str) -> AzureOpenAI:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError(
            "AZURE_OPENAI_API_KEY 또는 AZURE_OPENAI_ENDPOINT가 없습니다. backend/.env를 확인하세요."
        )
    return AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)


def call_model(
    azure_client: AzureOpenAI,
    model_name: str,
    prompt: str,
    *,
    timeout: float,
    max_completion_tokens: int,
) -> str:
    response = azure_client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an extraction engine. "
                    "Return strict JSON only with no markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=max_completion_tokens,
        timeout=timeout,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError(
            f"empty_response:finish_reason={response.choices[0].finish_reason}"
        )
    return text


def run_pipeline(
    school: str,
    filename_contains: str,
    azure_model: str,
    azure_api_version: str,
    timeout: float,
    max_completion_tokens: int,
) -> Dict[str, Any]:
    azure_client = get_azure_client(api_version=azure_api_version)
    client = SupabaseService.get_client()

    docs = fetch_school_documents(client, school, filename_contains=filename_contains)
    if not docs:
        raise RuntimeError(
            f"대상 문서를 찾지 못했습니다. school={school}, filename_contains={filename_contains}"
        )

    chunks = fetch_chunks_for_documents(client, docs)
    context, used_chunk_ids = build_context(chunks)
    if not context:
        raise RuntimeError("대상 문서에서 읽을 청크가 없습니다.")

    prompt = make_extraction_prompt(school, filename_contains, context)
    raw_output = call_model(
        azure_client,
        azure_model,
        prompt,
        timeout=timeout,
        max_completion_tokens=max_completion_tokens,
    )
    parsed: Dict[str, Any] | None = None
    errors: List[str] = []
    parse_error: str | None = None
    try:
        parsed = extract_json_blob(raw_output)
        errors = validate_output(parsed)
    except Exception as e:  # noqa: BLE001
        parse_error = str(e)
        errors = [f"json_parse_failed:{parse_error}"]
        parsed = {"university": school, "document_scope": filename_contains, "rules": []}

    return {
        "school": school,
        "filename_contains": filename_contains,
        "documents_found": len(docs),
        "document_ids": [int(d["id"]) for d in docs],
        "chunks_found": len(chunks),
        "chunks_used": len(used_chunk_ids),
        "context_chars": len(context),
        "model": azure_model,
        "api_version": azure_api_version,
        "json_parse_error": parse_error,
        "validation_errors": errors,
        "raw_output": raw_output,
        "result": parsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="정시 환산공식 추출 (Azure OpenAI)")
    parser.add_argument("--school", default="서울대학교", help="대학명")
    parser.add_argument(
        "--filename-contains",
        default="정시모집",
        help="documents.filename 포함 문자열",
    )
    parser.add_argument("--azure-model", default=DEFAULT_AZURE_MODEL, help="Azure 배포명")
    parser.add_argument(
        "--azure-api-version",
        default=DEFAULT_AZURE_API_VERSION,
        help="Azure OpenAI API 버전",
    )
    parser.add_argument("--timeout", type=float, default=300.0, help="모델 호출 타임아웃(초)")
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=16384,
        help="Azure max_completion_tokens",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"extract_{args.school}_{timestamp}.json"

    payload = run_pipeline(
        school=args.school,
        filename_contains=args.filename_contains,
        azure_model=args.azure_model,
        azure_api_version=args.azure_api_version,
        timeout=args.timeout,
        max_completion_tokens=args.max_completion_tokens,
    )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "school": payload["school"],
                "filename_contains": payload["filename_contains"],
                "documents_found": payload["documents_found"],
                "document_ids": payload["document_ids"],
                "chunks_found": payload["chunks_found"],
                "chunks_used": payload["chunks_used"],
                "context_chars": payload["context_chars"],
                "model": payload["model"],
                "api_version": payload["api_version"],
                "validation_errors_head": payload["validation_errors"][:10],
                "rules_count": len(payload["result"].get("rules", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
