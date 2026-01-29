#!/usr/bin/env python3
"""
PDF 입결 데이터 파서: Gemini 3.0 Flash가 PDF를 직접 읽어 페이지별로 처리 → JSON 저장.

- data/ 내 경희_서울캠, 서강대, 서울대, 연세대 PDF 4개 처리
- data/admission_results/ 에 khu_2025.json, sogang_2025.json, snu_2025.json, yonsei_2025.json 생성
- .env 의 GEMINI_API_KEY 사용 (gemini-3-flash-preview)
- pdfplumber는 사용하지 않음. PDF 전체를 Gemini에 업로드 후 한 번에 파싱.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# 프로젝트 루트를 path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


load_env()

# Gemini API (google-generativeai)
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# --- 설정 ---
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "data" / "admission_results"
GEMINI_MODEL = "gemini-3-flash-preview"  # 3.0 Flash Preview; 없으면 gemini-2.5-flash 폴백

UNIV_CONFIGS = [
    {
        "key": "khu",
        "out_file": "khu_2025.json",
        "pdf_name": "경희_서울캠_정시_전형결과_2025.pdf",
        "univ": "경희대학교",
        "total_scale": 800,
        "type": "일반",
        "hint": "학과명은 첫 번째 칸. '최종등록자 70%' 열의 값이 500~600대 실수(800점 만점). "
                "학과명에 공학/과학/의예/약학/정보/수학/물리 포함이면 field=자연, 아니면 인문.",
    },
    {
        "key": "khu_yongin",
        "out_file": "khu_yongin_2025.json",
        "pdf_name": "경희_용인캠_정시_전형결과_2025.pdf",
        "univ": "경희대학교",
        "total_scale": 800,
        "type": "일반",
        "hint": "학과명은 첫 번째 칸. '최종등록자 70%' 열의 값이 500~600대 실수(800점 만점). "
                "학과명에 공학/과학/의예/약학/정보/수학/물리 포함이면 field=자연, 아니면 인문.",
    },
    {
        "key": "sogang",
        "out_file": "sogang_2025.json",
        "pdf_name": "서강대_정시_2025_전형결과.pdf",
        "univ": "서강대학교",
        "total_scale": 600,
        "type": "일반",
        "hint": "학과명은 '인문', '영미문화계' 등 텍스트. 70% 컷은 450~480점 대 환산점수. "
                "field는 인문/자연 구분.",
    },
    {
        "key": "snu",
        "out_file": "snu_2025.json",
        "pdf_name": "서울대_정시_전형결과.pdf",
        "univ": "서울대학교",
        "total_scale": 600,
        "type": "일반",
        "hint": "50% cut과 70% cut이 나란히 있으면 더 낮은 값 또는 뒤쪽 값을 70% 컷으로. "
                "점수 범위 380~420점 대(표준점수 총합 600점 기준).",
    },
    {
        "key": "yonsei",
        "out_file": "yonsei_2025.json",
        "pdf_name": "연세대_2025_정시전형결과.pdf",
        "univ": "연세대학교",
        "total_scale": 1000,
        "type": "일반",
        "hint": "점수 범위 700~740점 대(1000점 만점). '총점' 열 근처에 70% 컷.",
    },
]


def infer_field(major: str, univ_key: str) -> str:
    """학과명으로 인문/자연 추론."""
    if not major or not isinstance(major, str):
        return "인문"
    m = re.sub(r"\s+", " ", major).strip()
    natural_keywords = [
        "공학", "과학", "의예", "약학", "정보", "수학", "물리", "화학", "생물",
        "의예과", "치의예", "한의예", "간호", "약학과", "수의예",
    ]
    for kw in natural_keywords:
        if kw in m:
            return "자연"
    return "인문"


def clean_cell(s: str) -> str:
    if s is None:
        return ""
    return str(s).replace("\n", " ").strip()


def parse_float(s) -> float | None:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).replace(",", "").replace(" ", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _wait_for_file_active(genai_module, file_obj, max_wait_sec: int = 120) -> bool:
    """업로드된 파일이 ACTIVE 상태가 될 때까지 대기 (google-generativeai)."""
    if not hasattr(genai_module, "get_file") or not getattr(file_obj, "name", None):
        return True
    start = time.time()
    while time.time() - start < max_wait_sec:
        try:
            info = genai_module.get_file(file_obj.name)
            state = getattr(info, "state", None)
            if state is None:
                return True
            if str(state).upper() == "ACTIVE":
                return True
            if str(state).upper() == "FAILED":
                return False
        except Exception:
            pass
        time.sleep(2)
    return True


def call_gemini_with_pdf(api_key: str, pdf_path: Path, prompt: str) -> str:
    """PDF를 Gemini에 업로드 후, 모델이 페이지별로 읽고 파싱하도록 요청."""
    if genai is None:
        raise RuntimeError("google-generativeai 패키지가 필요합니다: pip install google-generativeai")
    genai.configure(api_key=api_key)
    model_name = GEMINI_MODEL
    try:
        model = genai.GenerativeModel(model_name)
    except Exception:
        model_name = "gemini-2.5-flash"
        model = genai.GenerativeModel(model_name)

    try:
        print("  PDF 업로드 중...", end=" ", flush=True)
        uploaded = genai.upload_file(str(pdf_path), mime_type="application/pdf")
        print("완료. Gemini 처리 중...", flush=True)
        _wait_for_file_active(genai, uploaded)
        # PDF + 프롬프트를 한 번에 전달 → Gemini가 전부 한 페이지씩 읽으며 처리
        response = model.generate_content([uploaded, prompt])
        if not response:
            return "[]"
        text = getattr(response, "text", None)
        if text is None and hasattr(response, "candidates") and response.candidates:
            part = response.candidates[0].content.parts[0]
            text = getattr(part, "text", None)
        return (text or "").strip() or "[]"
    except Exception as e:
        print(f"  Gemini API 오류: {e}")
        return "[]"


def extract_json_from_response(raw: str) -> list:
    """응답 텍스트에서 JSON 배열만 추출."""
    raw = raw.strip()
    # ```json ... ``` 또는 ``` ... ``` 제거
    for marker in ("```json", "```"):
        if marker in raw:
            start = raw.find(marker) + len(marker)
            end = raw.find("```", start)
            if end == -1:
                raw = raw[start:].strip()
            else:
                raw = raw[start:end].strip()
            break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 배열 시작 [ 찾아서 파싱
        start = raw.find("[")
        if start != -1:
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == "[":
                    depth += 1
                elif raw[i] == "]":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(raw[start : i + 1])
                        except json.JSONDecodeError:
                            pass
                        break
    return []


def normalize_row(row: dict, config: dict) -> dict | None:
    """한 행을 표준 스키마로 정규화. 유효하지 않으면 None."""
    univ = config["univ"]
    total_scale = config["total_scale"]
    type_ = config["type"]
    major = clean_cell(row.get("major") or row.get("학과") or row.get("전공") or row.get("학과명") or "")
    if not major or len(major) < 2:
        return None
    cut = None
    for k in ("cut_70_score", "70%", "70%컷", "최종등록자 70%", "70% cut", "cut_70"):
        if k in row and row[k] is not None:
            cut = parse_float(row[k])
            if cut is not None:
                break
    if cut is None and "cut_70_score" not in row:
        # 숫자만 있는 값 중 적정 범위 찾기
        for k, v in row.items():
            if k in ("major", "학과", "전공", "학과명", "type", "field"):
                continue
            f = parse_float(v)
            if f is None:
                continue
            if config["key"] in ("khu", "khu_yongin") and 500 <= f <= 650:
                cut = f
                break
            if config["key"] == "sogang" and 450 <= f <= 500:
                cut = f
                break
            if config["key"] == "snu" and 380 <= f <= 430:
                cut = f
                break
            if config["key"] == "yonsei" and 680 <= f <= 750:
                cut = f
                break
    if cut is None:
        return None
    recruit = int(parse_float(row.get("recruit_count") or row.get("모집") or row.get("모집인원") or 0) or 0)
    comp = parse_float(row.get("competition_rate") or row.get("경쟁률") or 0) or 0.0
    field = (row.get("field") or "").strip() or infer_field(major, config["key"])
    return {
        "univ": univ,
        "major": major,
        "recruit_count": recruit,
        "competition_rate": round(comp, 2),
        "cut_70_score": round(cut, 2),
        "total_scale": total_scale,
        "type": type_,
        "field": field if field in ("인문", "자연") else infer_field(major, config["key"]),
    }


def parse_one(config: dict, api_key: str) -> list[dict]:
    """한 대학 PDF 파싱 → 정규화된 리스트. Gemini가 PDF를 직접 읽어 페이지별로 처리."""
    pdf_path = DATA_DIR / config["pdf_name"]
    if not pdf_path.exists():
        print(f"  PDF 없음: {pdf_path}")
        return []

    prompt = f"""이 PDF는 「{config['univ']}」 정시 전형 결과 문서이다. **페이지 순서대로 전부 읽고**, 각 페이지의 표에서 입결 데이터를 행 단위로 추출하라.

추출할 항목:
- 학과(전공)명 → major
- 모집인원 → recruit_count (정수)
- 경쟁률 → competition_rate (실수)
- 70% 컷 점수 → cut_70_score (실수, 핵심)

규칙:
- total_scale: {config['total_scale']}, type: "{config['type']}"
- field는 학과명 기준으로 "인문" 또는 "자연"만 사용.
- {config['hint']}

출력: 반드시 JSON 배열만 출력하라. 각 요소는 "major", "recruit_count", "competition_rate", "cut_70_score", "field" 키를 가진 객체. 헤더/푸터/합계 행은 제외하고 실제 학과 데이터 행만 넣어라."""

    raw = call_gemini_with_pdf(api_key, pdf_path, prompt)
    rows = extract_json_from_response(raw)
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        n = normalize_row(r, config)
        if n:
            out.append(n)
    return out


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 .env에 없습니다.")
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    configs = UNIV_CONFIGS
    if len(sys.argv) > 1:
        only_key = sys.argv[1].strip().lower()
        if only_key.startswith("--only="):
            only_key = only_key.split("=", 1)[1]
        configs = [c for c in UNIV_CONFIGS if c["key"] == only_key]
        if not configs:
            print(f"알 수 없는 키: {sys.argv[1]}. 사용 가능: {[c['key'] for c in UNIV_CONFIGS]}")
            sys.exit(1)

    for config in configs:
        print(f"파싱 중: {config['pdf_name']} -> {config['out_file']}", flush=True)
        try:
            rows = parse_one(config, api_key)
            out_path = OUT_DIR / config["out_file"]
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
            print(f"  저장: {out_path} (행 수: {len(rows)})", flush=True)
        except Exception as e:
            print(f"  오류: {e}")
            import traceback
            traceback.print_exc()

    print("완료.")


if __name__ == "__main__":
    main()
