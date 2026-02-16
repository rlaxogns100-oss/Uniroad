#!/usr/bin/env python3
"""
전형별 최종 점수 산출 E2E 추출 + 재평가 루프.

목표:
- 전형별 최종 배점(예: 수능 60 + 내신 30 + 면접 10) 확인
- 각 배점 컴포넌트의 기본 입력 -> 환산 -> 최종합 흐름을 구조화
- 누락/불완전 시 피드백을 넣어 재추출을 반복
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


load_dotenv(BASE_DIR / ".env", override=False)

OUTPUT_DIR = BASE_DIR / "data" / "extraction_runs"
DEFAULT_AZURE_MODEL = os.getenv("AZURE_OPENAI_MODEL", "gpt-5.2-chat-4")
DEFAULT_AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

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


def fetch_school_documents(
    client: Any,
    school: str,
    filename_contains: str,
    doc_id: int | None,
) -> List[Dict[str, Any]]:
    if doc_id is not None:
        rows = (
            client.table("documents")
            .select("id, school_name, filename")
            .eq("id", doc_id)
            .execute()
            .data
            or []
        )
        return rows

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
            if needle and needle not in normalize_for_match(filename):
                continue
            docs.append(row)

    uniq: Dict[int, Dict[str, Any]] = {}
    for d in docs:
        uniq[int(d["id"])] = d
    return sorted(uniq.values(), key=lambda x: int(x["id"]))


def fetch_chunks_for_documents(client: Any, docs: List[Dict[str, Any]]) -> List[ChunkRow]:
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


def build_manifest(chunks: List[ChunkRow], max_items: int = 220) -> List[Dict[str, Any]]:
    keywords = [
        "전형요소 및 배점",
        "수능 성적 환산",
        "1단계",
        "2단계",
        "최종",
        "감점",
        "환산",
        "교과",
        "면접",
        "실기",
        "서류",
        "수능",
        "전형",
    ]
    seen: set[str] = set()
    items: List[Dict[str, Any]] = []
    for c in chunks:
        text = c.source_text
        if not text:
            continue
        for raw_line in text.splitlines():
            line = re.sub(r"[#>*`|]+", " ", raw_line).strip()
            line = re.sub(r"\s+", " ", line)
            if len(line) < 6 or len(line) > 140:
                continue
            if not any(k in line for k in keywords):
                continue
            key = f"{c.page_number}:{line}"
            if key in seen:
                continue
            seen.add(key)
            items.append({"page": c.page_number, "text": line})
            if len(items) >= max_items:
                return items
    return items


def get_azure_client(api_version: str) -> AzureOpenAI:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError("AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT 누락")
    return AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)


def extract_json_blob(text: str) -> Dict[str, Any]:
    candidate = (text or "").strip()
    candidate = re.sub(r"^```json\s*", "", candidate)
    candidate = re.sub(r"^```\s*", "", candidate)
    candidate = re.sub(r"\s*```$", "", candidate)
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise ValueError("JSON 객체를 찾지 못했습니다.")
    return json.loads(match.group(0))


def call_azure_json(
    client: AzureOpenAI,
    model_name: str,
    prompt: str,
    *,
    timeout: float,
    max_completion_tokens: int,
    reasoning_effort: str | None,
) -> Tuple[Dict[str, Any], str, Dict[str, int]]:
    req: Dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Return strict json only."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": max_completion_tokens,
        "timeout": timeout,
    }
    if reasoning_effort:
        req["reasoning_effort"] = reasoning_effort

    response = client.chat.completions.create(**req)
    raw = (response.choices[0].message.content or "").strip()
    obj = extract_json_blob(raw)
    usage = {
        "prompt_tokens": int(getattr(response.usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(response.usage, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(response.usage, "total_tokens", 0) or 0),
    }
    return obj, raw, usage


def make_extraction_prompt(
    university: str,
    context: str,
    feedback: List[str],
    previous_output: Dict[str, Any] | None,
) -> str:
    feedback_text = "\n".join(f"- {x}" for x in feedback[:50]) if feedback else "없음"
    prev_text = json.dumps(previous_output, ensure_ascii=False)[:50000] if previous_output else "없음"
    return f"""
역할:
너는 대학입시 전형 점수 계산 구조 추출 엔진이다. 반드시 JSON만 출력한다.

목표:
모든 정시 전형에 대해 아래 3가지를 완결해라.
1) 최종 점수 배점(컴포넌트별 할당점수)
2) 컴포넌트별 기본 입력값(raw_inputs) -> 환산 단계(conversion_steps) -> 컴포넌트 최종점(component_final_var)
3) 컴포넌트 합산으로 최종점수 산출(final_expression)

절대 규칙:
- 문서에 없는 값 추론 금지 (모르면 null)
- 전형 누락 금지
- 모든 conversion step에 source_page, evidence_text 필수
- JSON 외 텍스트 금지
- 이전 반복에서 이미 추출된 전형(track)은 삭제하지 말고 유지한 상태에서 누락만 보강

이전 반복에서 발견된 오류/누락:
{feedback_text}

이전 출력(JSON 일부):
{prev_text}

출력 스키마:
{{
  "university": "{university}",
  "year": 2026,
  "admission_type": "정시",
  "tracks": [
    {{
      "track_id": "string",
      "track_name": "string",
      "unit_or_major": "string|null",
      "stage_model": "single|two_stage|multi_stage|other",
      "total_points": 100,
      "components": [
        {{
          "component_id": "string",
          "component_name": "수능|교과|면접|실기|서류|기타",
          "allocated_points": 60,
          "raw_inputs": ["string"],
          "component_final_var": "string",
          "conversion_steps": [
            {{
              "step_id": "string",
              "step_name": "string",
              "formula_type": "absolute|relative_minmax|piecewise|grade_map|stage_weight|table_result",
              "expression": "string|null",
              "piecewise": [{{"if":"string","value":"string"}}],
              "grade_map": {{"key":"value"}},
              "variables": ["string"],
              "requires_runtime_data": true,
              "runtime_keys": ["string"],
              "cannot_compute_reason": "string|null",
              "source_page": 0,
              "evidence_text": "string"
            }}
          ],
          "source_page": 0,
          "evidence_text": "string"
        }}
      ],
      "final_expression": "string",
      "source_page": 0,
      "evidence_text": "string"
    }}
  ]
}}

문맥:
{context}
""".strip()


def merge_tracks_no_regression(
    previous_output: Dict[str, Any] | None,
    current_output: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(previous_output, dict):
        return current_output
    prev_tracks = previous_output.get("tracks", [])
    curr_tracks = current_output.get("tracks", [])
    if not isinstance(prev_tracks, list) or not isinstance(curr_tracks, list):
        return current_output

    def key_of(track: Dict[str, Any]) -> str:
        tid = str(track.get("track_id") or "").strip()
        tname = str(track.get("track_name") or "").strip()
        unit = str(track.get("unit_or_major") or "").strip()
        return tid or f"{tname}|{unit}"

    existing = {key_of(t): t for t in curr_tracks if isinstance(t, dict)}
    merged = list(curr_tracks)
    for t in prev_tracks:
        if not isinstance(t, dict):
            continue
        k = key_of(t)
        if not k:
            continue
        if k not in existing:
            merged.append(t)
    current_output["tracks"] = merged
    return current_output


def make_completeness_prompt(manifest: List[Dict[str, Any]], extracted: Dict[str, Any]) -> str:
    return f"""
역할:
너는 추출 결과 완결성 검증기다. 반드시 JSON만 출력한다.

검증 기준:
1) 문맥에 존재하는 정시 전형이 tracks에 모두 포함되었는가
2) 각 track에 최종 배점(components.allocated_points)과 final_expression이 있는가
3) 각 component에 raw_inputs + conversion_steps가 존재하는가
4) conversion step별 source_page/evidence_text가 있는가
5) 분기식/감점표 등 핵심 계산 규칙 누락이 있는가

출력 스키마:
{{
  "is_complete": true,
  "missing_items": [
    {{
      "type": "track|component|conversion|allocation|final_expression|evidence|formula",
      "track_name": "string|null",
      "detail": "string",
      "severity": "high|medium|low"
    }}
  ],
  "notes": ["string"]
}}

문맥 요약(manifest):
{json.dumps(manifest, ensure_ascii=False)}

추출 결과:
{json.dumps(extracted, ensure_ascii=False)}
""".strip()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def validate_structural(obj: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(obj, dict):
        return ["top_not_object"]
    for k in ["university", "tracks"]:
        if k not in obj:
            errs.append(f"missing_key:{k}")

    tracks = obj.get("tracks", [])
    if not isinstance(tracks, list) or not tracks:
        errs.append("tracks_empty")
        return errs

    for ti, t in enumerate(tracks):
        if not isinstance(t, dict):
            errs.append(f"track_{ti}_not_object")
            continue
        for k in ["track_id", "track_name", "components", "final_expression", "source_page", "evidence_text"]:
            if k not in t:
                errs.append(f"track_{ti}_missing_{k}")
        components = t.get("components", [])
        if not isinstance(components, list) or not components:
            errs.append(f"track_{ti}_components_empty")
            continue
        total_points = t.get("total_points")
        sum_points = 0.0
        for ci, c in enumerate(components):
            if not isinstance(c, dict):
                errs.append(f"track_{ti}_component_{ci}_not_object")
                continue
            for ck in ["component_id", "component_name", "allocated_points", "raw_inputs", "component_final_var", "conversion_steps", "source_page", "evidence_text"]:
                if ck not in c:
                    errs.append(f"track_{ti}_component_{ci}_missing_{ck}")
            ap = c.get("allocated_points")
            if not _is_number(ap):
                errs.append(f"track_{ti}_component_{ci}_allocated_points_not_number")
            else:
                sum_points += float(ap)
            if not isinstance(c.get("raw_inputs"), list) or not c.get("raw_inputs"):
                errs.append(f"track_{ti}_component_{ci}_raw_inputs_empty")
            if not isinstance(c.get("conversion_steps"), list) or not c.get("conversion_steps"):
                errs.append(f"track_{ti}_component_{ci}_conversion_steps_empty")
            if not c.get("component_final_var"):
                errs.append(f"track_{ti}_component_{ci}_final_var_empty")

            steps = c.get("conversion_steps", [])
            for si, s in enumerate(steps):
                if not isinstance(s, dict):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_not_object")
                    continue
                ft = s.get("formula_type")
                if ft not in FORMULA_TYPE_ENUM:
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_invalid_formula_type")
                if not s.get("source_page"):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_source_page_missing")
                if not s.get("evidence_text"):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_evidence_missing")
                if ft in ["absolute", "relative_minmax", "stage_weight", "table_result"] and not s.get("expression"):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_expression_missing")
                if ft == "piecewise" and not isinstance(s.get("piecewise"), list):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_piecewise_missing")
                if ft == "grade_map" and not isinstance(s.get("grade_map"), dict):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_grade_map_missing")
                if s.get("requires_runtime_data") and not isinstance(s.get("runtime_keys"), list):
                    errs.append(f"track_{ti}_component_{ci}_step_{si}_runtime_keys_missing")

        if _is_number(total_points) and total_points is not None:
            if abs(sum_points - float(total_points)) > 1.0:
                errs.append(f"track_{ti}_allocated_sum_mismatch:{sum_points}!={total_points}")

        final_expr = str(t.get("final_expression") or "")
        for c in components:
            var = str(c.get("component_final_var") or "")
            if var and var not in final_expr:
                errs.append(f"track_{ti}_final_expression_missing_var:{var}")
    return errs


def run_pipeline(
    school: str,
    filename_contains: str,
    doc_id: int | None,
    azure_model: str,
    azure_api_version: str,
    max_iterations: int,
    timeout: float,
    max_completion_tokens: int,
    reasoning_effort: str | None,
) -> Dict[str, Any]:
    client = SupabaseService.get_client()
    docs = fetch_school_documents(client, school, filename_contains, doc_id)
    if not docs:
        raise RuntimeError(
            f"대상 문서를 찾지 못했습니다. school={school}, filename_contains={filename_contains}, doc_id={doc_id}"
        )
    chunks = fetch_chunks_for_documents(client, docs)
    context, used_chunk_ids = build_context(chunks)
    if not context:
        raise RuntimeError("문서 청크 컨텍스트가 비어 있습니다.")

    manifest = build_manifest(chunks)
    azure_client = get_azure_client(api_version=azure_api_version)

    feedback: List[str] = []
    previous_output: Dict[str, Any] | None = None
    final_output: Dict[str, Any] = {"university": school, "tracks": []}
    final_structural_errors: List[str] = []
    final_completeness: Dict[str, Any] = {"is_complete": False, "missing_items": [], "notes": []}
    iterations: List[Dict[str, Any]] = []

    for i in range(1, max_iterations + 1):
        iter_info: Dict[str, Any] = {"iteration": i}

        extraction_prompt = make_extraction_prompt(school, context, feedback, previous_output)
        try:
            extracted, raw_extract, extract_usage = call_azure_json(
                azure_client,
                azure_model,
                extraction_prompt,
                timeout=timeout,
                max_completion_tokens=max_completion_tokens,
                reasoning_effort=reasoning_effort,
            )
            final_output = merge_tracks_no_regression(previous_output, extracted)
            iter_info["extract_usage"] = extract_usage
            iter_info["extract_raw_len"] = len(raw_extract)
        except Exception as e:  # noqa: BLE001
            final_output = {"university": school, "tracks": []}
            final_structural_errors = [f"extract_failed:{e}"]
            final_completeness = {"is_complete": False, "missing_items": [], "notes": ["extraction failed"]}
            iterations.append(
                {
                    **iter_info,
                    "status": "FAIL",
                    "structural_errors_count": len(final_structural_errors),
                    "completeness_missing_count": 0,
                }
            )
            break

        structural_errors = validate_structural(final_output)
        completeness_prompt = make_completeness_prompt(manifest, final_output)
        completeness_missing: List[Dict[str, Any]] = []
        completeness_notes: List[str] = []
        is_complete = False
        try:
            completeness_obj, raw_check, check_usage = call_azure_json(
                azure_client,
                azure_model,
                completeness_prompt,
                timeout=timeout,
                max_completion_tokens=4096,
                reasoning_effort=reasoning_effort,
            )
            iter_info["check_usage"] = check_usage
            iter_info["check_raw_len"] = len(raw_check)
            is_complete = bool(completeness_obj.get("is_complete"))
            completeness_missing = completeness_obj.get("missing_items", []) or []
            completeness_notes = completeness_obj.get("notes", []) or []
        except Exception as e:  # noqa: BLE001
            completeness_missing = [
                {
                    "type": "validation",
                    "track_name": None,
                    "detail": f"completeness_check_failed:{e}",
                    "severity": "high",
                }
            ]
            completeness_notes = ["completeness check failed"]

        final_structural_errors = structural_errors
        final_completeness = {
            "is_complete": is_complete and not completeness_missing,
            "missing_items": completeness_missing,
            "notes": completeness_notes,
        }

        iter_status = "PASS" if (not structural_errors and final_completeness["is_complete"]) else "RETRY"
        iterations.append(
            {
                **iter_info,
                "status": iter_status,
                "tracks_count": len(final_output.get("tracks", [])) if isinstance(final_output, dict) else 0,
                "structural_errors_count": len(structural_errors),
                "completeness_missing_count": len(completeness_missing),
            }
        )

        if iter_status == "PASS":
            break

        feedback = []
        feedback.extend(structural_errors[:40])
        for m in completeness_missing[:40]:
            if isinstance(m, dict):
                feedback.append(f"{m.get('type')}|{m.get('track_name')}|{m.get('detail')}")
            else:
                feedback.append(str(m))
        previous_output = final_output

    status = "PASS" if (not final_structural_errors and final_completeness.get("is_complete")) else "FAIL"
    return {
        "school": school,
        "filename_contains": filename_contains,
        "doc_id": doc_id,
        "documents_found": len(docs),
        "document_ids": [int(d["id"]) for d in docs],
        "chunks_found": len(chunks),
        "chunks_used": len(used_chunk_ids),
        "context_chars": len(context),
        "manifest_items": len(manifest),
        "model": azure_model,
        "api_version": azure_api_version,
        "max_iterations": max_iterations,
        "status": status,
        "iterations": iterations,
        "reports": {
            "structural_errors": final_structural_errors,
            "completeness": final_completeness,
        },
        "result": final_output,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="전형별 최종점수 E2E 재평가 루프 추출")
    parser.add_argument("--school", required=True, help="대학명")
    parser.add_argument("--filename-contains", default="정시모집", help="파일명 필터")
    parser.add_argument("--doc-id", type=int, default=None, help="documents.id 직접 지정")
    parser.add_argument("--azure-model", default=DEFAULT_AZURE_MODEL, help="Azure 배포명")
    parser.add_argument("--azure-api-version", default=DEFAULT_AZURE_API_VERSION, help="Azure API 버전")
    parser.add_argument("--max-iterations", type=int, default=3, help="최대 재평가 반복 횟수")
    parser.add_argument("--timeout", type=float, default=300.0, help="호출 타임아웃(초)")
    parser.add_argument("--max-completion-tokens", type=int, default=16384, help="최대 출력 토큰")
    parser.add_argument(
        "--reasoning-effort",
        default="minimal",
        choices=["minimal", "low", "medium", "high", "none"],
        help="reasoning_effort (none이면 미전달)",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"e2e_eval_{args.school}_{timestamp}.json"

    reasoning_effort = None if args.reasoning_effort == "none" else args.reasoning_effort
    payload = run_pipeline(
        school=args.school,
        filename_contains=args.filename_contains,
        doc_id=args.doc_id,
        azure_model=args.azure_model,
        azure_api_version=args.azure_api_version,
        max_iterations=args.max_iterations,
        timeout=args.timeout,
        max_completion_tokens=args.max_completion_tokens,
        reasoning_effort=reasoning_effort,
    )
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "status": payload["status"],
                "school": payload["school"],
                "document_ids": payload["document_ids"],
                "chunks_used": payload["chunks_used"],
                "context_chars": payload["context_chars"],
                "manifest_items": payload["manifest_items"],
                "model": payload["model"],
                "iterations": payload["iterations"],
                "final_structural_errors": payload["reports"]["structural_errors"][:20],
                "final_missing_items": payload["reports"]["completeness"].get("missing_items", [])[:20],
                "tracks_count": len(payload["result"].get("tracks", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
