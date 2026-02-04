"""
임베딩 기반 PDF 처리 서비스
Streamlit 없이 core/pdf 파이프라인을 호출
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Optional, Tuple, Union

from core.pdf import TOCProcessor, SectionPreprocessor
from config import embedding_settings as config
from services.supabase_client import SupabaseUploader


def process_pdf(
    pdf_path: str,
    school_name: str,
    on_progress: Optional[Callable[[str, str], None]] = None,
    strict_mode: bool = True
) -> Union[Dict, Tuple[None, str]]:
    """
    PDF를 처리하여 processed_data 딕셔너리를 생성.
    성공 시 Dict, 실패 시 (None, 실패_사유_문자열) 반환.
    """

    def log(status: str, message: str = None):
        if on_progress:
            on_progress(status, message or status)

    try:
        log("모델 초기화 중...", "📦 모델 초기화 중...")

        model_name = config.DEFAULT_LLM_MODEL
        toc_processor = TOCProcessor(model_name)
        preprocessor = SectionPreprocessor(model_name)

        log("문서 요약 생성 중...", "✅ 모델 초기화 완료")
        log("문서 요약 생성 중...", "📝 [0단계] 문서 요약 생성 중...")

        document_summary = toc_processor.generate_document_summary(pdf_path)

        if not document_summary:
            log("문서 요약 생성 실패", "⚠️ 문서 요약 생성 실패. 계속 진행합니다.")
        else:
            log("문서 요약 생성 완료", f"✅ 문서 요약 생성 완료 ({len(document_summary)}자)")

        log("목차 페이지 감지 중...", "🔍 [1단계] 목차 페이지 감지 중...")

        toc_pages = toc_processor.detect_toc_pages(pdf_path)
        sections = None

        if not toc_pages:
            log("목차 페이지 없음", "⚠️ 목차 페이지를 찾을 수 없습니다.")
            if document_summary:
                log("요약 기반 목차 생성 중...", "📋 요약 기반 목차 생성 시도 중...")
                sections = toc_processor.generate_toc_from_summary(pdf_path, document_summary)
                if sections:
                    log("요약 기반 목차 생성 완료", f"✅ 요약 기반 목차 생성 완료: {len(sections)}개 섹션")
                else:
                    log("실패: 목차 생성 불가", "⚠️ 요약 기반 목차 생성 실패")
                    return (None, "요약 기반 목차 생성 실패")
            else:
                log("실패: 목차 생성 불가", "⚠️ 요약본도 없어 목차를 생성할 수 없습니다.")
                return (None, "요약본이 없어 목차를 생성할 수 없습니다.")
        else:
            log("목차 페이지 발견", f"✅ 목차 페이지 발견: {[p+1 for p in toc_pages]}")

            log("목차 구조 파싱 중...", "📋 [2단계] 목차 구조 파싱 중...")
            sections = toc_processor.parse_toc_structure(pdf_path, toc_pages)

            if not sections:
                log("목차 파싱 실패", "⚠️ 목차 파싱 실패.")
                if document_summary:
                    log("요약 기반 목차 생성 중...", "📋 요약 기반 목차 생성 시도 중...")
                    sections = toc_processor.generate_toc_from_summary(pdf_path, document_summary)
                    if sections:
                        log("요약 기반 목차 생성 완료", f"✅ 요약 기반 목차 생성 완료: {len(sections)}개 섹션")
                    else:
                        log("실패: 목차 생성 불가", "⚠️ 요약 기반 목차 생성 실패")
                        return (None, "요약 기반 목차 생성 실패")
                else:
                    log("실패: 목차 생성 불가", "⚠️ 요약본도 없어 목차를 생성할 수 없습니다.")
                    return (None, "요약본이 없어 목차를 생성할 수 없습니다.")

        log("페이지 범위 검증 중...", "✅ [3단계] 페이지 범위 검증 중...")
        sections = toc_processor.validate_and_fix_sections(sections, pdf_path)
        log("섹션 추출 완료", f"✅ {len(sections)}개 섹션 추출 완료")

        log(f"섹션 전처리 중... (0/{len(sections)})", f"📄 [4단계] {len(sections)}개 섹션 병렬 전처리 중...")

        section_data = {}
        all_chunks = []
        completed = 0
        total = len(sections)
        failed_sections = []

        def process_section(section):
            section_key = f"{section['start_page']}_{section['end_page']}"
            try:
                result = preprocessor.preprocess_section(section, pdf_path)
                return {
                    "section_key": section_key,
                    "result": result,
                    "section": section,
                    "error": None
                }
            except Exception as e:
                return {
                    "section_key": section_key,
                    "result": None,
                    "section": section,
                    "error": str(e)
                }

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            future_to_section = {
                executor.submit(process_section, section): idx
                for idx, section in enumerate(sections, 1)
            }

            for future in as_completed(future_to_section):
                idx = future_to_section[future]
                try:
                    data = future.result()

                    if data.get("error"):
                        error_msg = data.get("error")
                        log(f"섹션 전처리 중... ({completed}/{total})", f"❌ 섹션 {idx} 오류: {error_msg}")
                        failed_sections.append({"idx": idx, "error": error_msg, "section": data.get("section")})
                        completed += 1
                        continue

                    if not data or not data.get("result"):
                        log(f"섹션 전처리 중... ({completed}/{total})", f"❌ 섹션 {idx} 처리 결과 없음")
                        failed_sections.append({"idx": idx, "error": "결과 없음", "section": data.get("section") if data else None})
                        completed += 1
                        continue

                    section_key = data.get("section_key", f"section_{idx}")
                    result = data.get("result", {})
                    section = data.get("section", {"title": f"섹션 {idx}"})

                    documents = result.get("documents", [])
                    if not documents:
                        log(f"섹션 전처리 중... ({completed}/{total})", f"⚠️ 섹션 {idx} 청크 없음 (건너뜀)")
                        completed += 1
                        continue

                    section_data[section_key] = {
                        "vectorstore": result.get("vectorstore"),
                        "documents": documents,
                        "section": section,
                        "table_count": result.get("table_count", 0)
                    }

                    all_chunks.extend(documents)

                    completed += 1
                    table_count = result.get("table_count", 0)
                    table_info = f" (표 {table_count}개)" if table_count > 0 else ""
                    section_title = section.get("title", f"섹션 {idx}")
                    log(f"섹션 전처리 중... ({completed}/{total})",
                        f"✅ {completed}/{total} 완료: '{section_title}'{table_info} ({len(documents)}개 청크)")
                except Exception as e:
                    log(f"섹션 전처리 중... ({completed}/{total})", f"❌ 섹션 {idx} 예외 발생: {str(e)}")
                    failed_sections.append({"idx": idx, "error": str(e), "section": None})
                    completed += 1

        if strict_mode and failed_sections:
            failed_count = len(failed_sections)
            log("실패: 청크 오류 발생", f"❌ {failed_count}개 섹션에서 오류 발생 - 파일 전체 건너뜀")
            for fail in failed_sections:
                section_info = fail.get("section", {})
                section_title = section_info.get("title", f"섹션 {fail['idx']}") if section_info else f"섹션 {fail['idx']}"
                log("실패: 청크 오류 발생", f"   - {section_title}: {fail['error']}")
            first_err = failed_sections[0].get("error", "알 수 없음") if failed_sections else "알 수 없음"
            return (None, f"섹션 전처리 실패 ({failed_count}개): {first_err}")

        if not all_chunks:
            log("실패: 청크 없음", "❌ 처리된 청크가 없습니다.")
            return (None, "처리된 청크가 없습니다.")

        log("전처리 완료", f"🎉 모든 섹션 전처리 완료! ({len(sections)}개 섹션, 총 {len(all_chunks)}개 청크)")

        if failed_sections and not strict_mode:
            log("전처리 완료", f"⚠️ {len(failed_sections)}개 섹션은 건너뜀")

        return {
            "toc_sections": sections,
            "chunks": all_chunks,
            "summary": document_summary,
            "failed_sections": failed_sections if failed_sections else None
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        reason = str(e) if str(e) else type(e).__name__
        log(f"실패: {reason}", f"❌ 오류 발생: {reason}\n{tb}")
        print(f"\n❌ [process_pdf] 오류: {e}\n{tb}\n")
        return (None, reason)


def upload_to_supabase_with_file(
    school_name: str,
    file_path: str,
    processed_data: Dict,
    original_filename: str = None,
    on_progress: Optional[Callable[[str, str], None]] = None
) -> Optional[int]:
    """
    Supabase에 PDF 및 처리된 데이터 업로드
    """

    def log(status: str, message: str = None):
        if on_progress:
            on_progress(status, message or status)

    try:
        log("Supabase 업로드 중...", "📤 [5단계] Supabase에 데이터 업로드 중...")
        log("Supabase 업로드 중...", f"   섹션 수: {len(processed_data['toc_sections'])}개")
        log("Supabase 업로드 중...", f"   청크 수: {len(processed_data['chunks'])}개")

        uploader = SupabaseUploader()
        document_id = uploader.upload_to_supabase(
            school_name=school_name,
            file_path=file_path,
            processed_data=processed_data,
            original_filename=original_filename
        )

        if document_id:
            log("업로드 완료", f"   🎉 업로드 완료! 문서 ID: {document_id}")
            return document_id
        log("업로드 실패", "   ❌ 업로드 실패")
        return None
    except Exception as e:
        log(f"업로드 실패: {str(e)}", f"❌ 업로드 중 오류 발생: {str(e)}")
        return None
