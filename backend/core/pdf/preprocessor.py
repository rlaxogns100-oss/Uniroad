"""
섹션 전처리 모듈
Gemini Vision 기반 PDF 섹션 전처리 및 벡터스토어 생성
"""
from PyPDF2 import PdfReader, PdfWriter
from langchain.docstore.document import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from .vision_processor import VisionProcessor
from .chunker import DocumentChunker
from config import embedding_settings as config


class SectionPreprocessor:
    """섹션 전처리를 담당하는 클래스"""

    def __init__(self, model_name: str = None):
        """
        초기화

        Args:
            model_name: LLM 모델명 (Gemini Vision 모델)
        """
        self.model_name = model_name or config.DEFAULT_LLM_MODEL
        self.vision_processor = VisionProcessor(model_name)
        self.chunker = DocumentChunker()

    def extract_pdf_section(self, pdf_path: str, start_page: int, end_page: int) -> str:
        """PDF에서 특정 페이지 범위만 추출하여 임시 파일로 저장"""
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page_num in range(start_page - 1, min(end_page, len(reader.pages))):
            writer.add_page(reader.pages[page_num])

        temp_path = f"{config.TOC_SECTIONS_DIR}/section_{start_page}_{end_page}.pdf"
        with open(temp_path, "wb") as output_file:
            writer.write(output_file)

        return temp_path

    def preprocess_section(self, section: dict, pdf_path: str) -> dict:
        """
        섹션을 전처리하여 벡터스토어 생성
        """
        try:
            self.extract_pdf_section(
                pdf_path,
                section.get("start_page", 1),
                section.get("end_page", 1)
            )
        except Exception as e:
            print(f"   ⚠️  섹션 추출 중 오류: {e}")
            return {
                "vectorstore": None,
                "documents": [],
                "table_count": 0
            }

        try:
            print(f"\n📄 [{section.get('title', '알 수 없음')}] Gemini Vision으로 마크다운 변환 시작...")
            markdown_results = self.vision_processor.convert_section_to_markdown(
                pdf_path,
                section.get('start_page', 1),
                section.get('end_page', 1)
            )

            if not markdown_results:
                print(f"   ⚠️  마크다운 변환 결과가 없습니다.")
                return {
                    "vectorstore": None,
                    "documents": [],
                    "table_count": 0
                }

            print(f"   ✅ {len(markdown_results)}개 페이지 마크다운 변환 완료")
        except Exception as e:
            print(f"   ⚠️  마크다운 변환 중 오류: {e}")
            import traceback
            print(f"   상세 오류:\n{traceback.format_exc()}")
            return {
                "vectorstore": None,
                "documents": [],
                "table_count": 0
            }

        split_docs = []
        table_count = 0

        for page_num, markdown_text in markdown_results:
            try:
                page_docs = self.chunker.chunk_markdown_with_dual_chunking(
                    markdown_text,
                    page_number=page_num
                )

                for doc in page_docs:
                    doc.metadata.update({
                        'section_title': section.get('title', '알 수 없음'),
                        'section_start': section.get('start_page', 1),
                        'section_end': section.get('end_page', 1)
                    })

                    if doc.metadata.get('type') == 'table':
                        table_count += 1

                    split_docs.append(doc)
            except Exception as e:
                print(f"   ⚠️  페이지 {page_num} Dual Chunking 처리 중 오류: {e}")
                try:
                    fallback_doc = Document(
                        page_content=markdown_text,
                        metadata={
                            'section_title': section.get('title', '알 수 없음'),
                            'section_start': section.get('start_page', 1),
                            'section_end': section.get('end_page', 1),
                            'page_number': page_num,
                            'type': 'text',
                            'chunk_type': 'page',
                            'is_table': False
                        }
                    )
                    split_docs.append(fallback_doc)
                except Exception:
                    pass

        try:
            if not split_docs:
                print(f"   ⚠️  처리할 문서가 없습니다.")
                embeddings = GoogleGenerativeAIEmbeddings(model=config.DEFAULT_EMBEDDING_MODEL)
                empty_doc = Document(page_content="", metadata={})
                vectorstore = FAISS.from_documents(documents=[empty_doc], embedding=embeddings)
            else:
                embeddings = GoogleGenerativeAIEmbeddings(model=config.DEFAULT_EMBEDDING_MODEL)
                vectorstore = FAISS.from_documents(documents=split_docs, embedding=embeddings)
        except Exception as e:
            print(f"   ⚠️  벡터스토어 생성 중 오류: {e}")
            try:
                embeddings = GoogleGenerativeAIEmbeddings(model=config.DEFAULT_EMBEDDING_MODEL)
                empty_doc = Document(page_content="", metadata={})
                vectorstore = FAISS.from_documents(documents=[empty_doc], embedding=embeddings)
            except Exception:
                vectorstore = None

        return {
            "vectorstore": vectorstore,
            "documents": split_docs if split_docs else [],
            "table_count": table_count
        }
