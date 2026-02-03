"""
문서 청킹 모듈
토큰 기반 스마트 청킹 및 페이지 단위 청킹 지원
Gemini Vision 마크다운 변환 결과의 Dual Chunking 처리
"""
import re
import tiktoken
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config import embedding_settings as config


class DocumentChunker:
    """문서를 토큰 기반으로 청킹하고 overlap 메타데이터를 관리하는 클래스"""

    def __init__(
        self,
        chunk_size_tokens: int = None,
        overlap_tokens: int = None,
        separators: list = None
    ):
        self.chunk_size_tokens = chunk_size_tokens or config.CHUNK_SIZE_TOKENS
        self.overlap_tokens = overlap_tokens or config.CHUNK_OVERLAP_TOKENS
        self.separators = separators or ["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        self._token_counter = self._get_token_counter()

    def _get_token_counter(self):
        """토큰 카운터 함수 반환"""
        encoding = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            return len(encoding.encode(text))

        return count_tokens

    def chunk_with_overlap_metadata(self, text: str) -> list:
        """overlap 정보를 메타데이터로 저장하는 스마트 청킹"""
        if not text or not text.strip():
            return []

        chunks = []

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size_tokens,
            chunk_overlap=self.overlap_tokens,
            length_function=self._token_counter,
            separators=self.separators
        )

        temp_doc = Document(page_content=text)
        split_docs = text_splitter.split_documents([temp_doc])

        if not split_docs:
            return []

        for idx, doc in enumerate(split_docs):
            chunk_text = doc.page_content

            if not chunk_text or not chunk_text.strip():
                continue

            chunk_start = text.find(chunk_text[:100])
            if chunk_start == -1:
                if len(chunks) == 0:
                    chunk_start = 0
                elif len(chunks) > 0:
                    try:
                        prev_end = chunks[-1].get("end_pos", 0)
                        overlap_chars = self.overlap_tokens * 3
                        chunk_start = max(0, prev_end - overlap_chars)
                    except (IndexError, KeyError):
                        chunk_start = 0
                else:
                    chunk_start = 0

            chunk_end = chunk_start + len(chunk_text)

            overlap_prev_text = ""
            overlap_prev_start = 0
            overlap_prev_end = 0
            if len(chunks) > 0:
                try:
                    prev_chunk = chunks[-1]
                    overlap_chars = self.overlap_tokens * 3
                    prev_start = prev_chunk.get("start_pos", 0)
                    prev_end = prev_chunk.get("end_pos", 0)
                    overlap_prev_start = max(prev_start, chunk_start - overlap_chars)
                    overlap_prev_end = min(prev_end, chunk_start + overlap_chars)
                    if overlap_prev_start < overlap_prev_end and overlap_prev_end <= len(text):
                        overlap_prev_text = text[overlap_prev_start:overlap_prev_end]
                except (IndexError, KeyError, TypeError):
                    pass

            overlap_next_text = ""
            overlap_next_start = 0
            overlap_next_end = 0
            if idx < len(split_docs) - 1:
                overlap_chars = self.overlap_tokens * 3
                next_chunk_start = chunk_end - overlap_chars
                overlap_next_start = max(chunk_start, next_chunk_start)
                overlap_next_end = min(chunk_end, chunk_end + overlap_chars)
                if overlap_next_start < overlap_next_end and overlap_next_end <= len(text):
                    overlap_next_text = text[overlap_next_start:overlap_next_end]

            chunks.append({
                "content": chunk_text,
                "start_pos": chunk_start,
                "end_pos": chunk_end,
                "overlap_prev": {
                    "text": overlap_prev_text,
                    "start": overlap_prev_start,
                    "end": overlap_prev_end
                },
                "overlap_next": {
                    "text": overlap_next_text,
                    "start": overlap_next_start,
                    "end": overlap_next_end
                },
                "chunk_index": idx
            })

        return chunks

    def extract_table_summaries(self, markdown_text: str) -> list:
        """마크다운 텍스트에서 <table_summary> 태그를 추출"""
        pattern = r'<table_summary>(.*?)</table_summary>'
        matches = []

        for match in re.finditer(pattern, markdown_text, re.DOTALL):
            summary = match.group(1).strip()
            start_pos = match.start()
            end_pos = match.end()
            matches.append((summary, start_pos, end_pos))

        return matches

    def extract_table_markdown(self, markdown_text: str, summary_end_pos: int) -> str:
        """<table_summary> 태그 다음에 오는 표의 마크다운 추출"""
        remaining_text = markdown_text[summary_end_pos:]

        lines = remaining_text.split('\n')
        table_lines = []
        in_table = False

        for line in lines:
            stripped = line.strip()

            if '|' in stripped and not in_table:
                in_table = True
                table_lines.append(line)
            elif in_table:
                if '|' in stripped or stripped == '':
                    table_lines.append(line)
                else:
                    break

        return '\n'.join(table_lines).strip()

    def chunk_markdown_with_dual_chunking(self, markdown_text: str, page_number: int = 0) -> list:
        """
        Gemini Vision으로 변환된 마크다운을 Dual Chunking 전략으로 처리
        """
        documents = []

        table_summaries = self.extract_table_summaries(markdown_text)

        if not table_summaries:
            if config.CHUNK_BY_PAGE:
                doc = Document(
                    page_content=markdown_text,
                    metadata={
                        'page_number': page_number,
                        'type': 'text',
                        'chunk_type': 'page'
                    }
                )
                documents.append(doc)
            else:
                chunks = self.chunk_with_overlap_metadata(markdown_text)
                for chunk in chunks:
                    doc = Document(
                        page_content=chunk.get("content", ""),
                        metadata={
                            'page_number': page_number,
                            'type': 'text',
                            'chunk_type': 'token',
                            'chunk_index': chunk.get("chunk_index", 0),
                            **{k: v for k, v in chunk.items() if k != "content" and k != "chunk_index"}
                        }
                    )
                    documents.append(doc)
            return documents

        last_pos = 0

        for idx, (summary, start_pos, end_pos) in enumerate(table_summaries):
            if start_pos > last_pos:
                text_before = markdown_text[last_pos:start_pos].strip()
                if text_before:
                    if config.CHUNK_BY_PAGE:
                        doc = Document(
                            page_content=text_before,
                            metadata={
                                'page_number': page_number,
                                'type': 'text',
                                'chunk_type': 'page'
                            }
                        )
                        documents.append(doc)
                    else:
                        chunks = self.chunk_with_overlap_metadata(text_before)
                        for chunk in chunks:
                            doc = Document(
                                page_content=chunk.get("content", ""),
                                metadata={
                                    'page_number': page_number,
                                    'type': 'text',
                                    'chunk_type': 'token',
                                    'chunk_index': chunk.get("chunk_index", 0),
                                    **{k: v for k, v in chunk.items() if k != "content" and k != "chunk_index"}
                                }
                            )
                            documents.append(doc)

            table_markdown = self.extract_table_markdown(markdown_text, end_pos)

            context_start = max(0, start_pos - 200)
            context_end = min(len(markdown_text), end_pos + len(table_markdown) + 200)
            context_text = markdown_text[context_start:context_end]

            search_text = f"{summary}\n{context_text}"

            raw_table = markdown_text[start_pos:end_pos + len(table_markdown)]
            raw_table = re.sub(r'<table_summary>.*?</table_summary>\s*', '', raw_table, flags=re.DOTALL)

            doc = Document(
                page_content=search_text.strip(),
                metadata={
                    'page_number': page_number,
                    'type': 'table',
                    'is_table': True,
                    'summary': summary,
                    'raw_data': raw_table.strip(),
                    'table_index': idx
                }
            )
            documents.append(doc)

            last_pos = end_pos + len(table_markdown)

        if last_pos < len(markdown_text):
            text_after = markdown_text[last_pos:].strip()
            if text_after:
                if config.CHUNK_BY_PAGE:
                    doc = Document(
                        page_content=text_after,
                        metadata={
                            'page_number': page_number,
                            'type': 'text',
                            'chunk_type': 'page'
                        }
                    )
                    documents.append(doc)
                else:
                    chunks = self.chunk_with_overlap_metadata(text_after)
                    for chunk in chunks:
                        doc = Document(
                            page_content=chunk.get("content", ""),
                            metadata={
                                'page_number': page_number,
                                'type': 'text',
                                'chunk_type': 'token',
                                'chunk_index': chunk.get("chunk_index", 0),
                                **{k: v for k, v in chunk.items() if k != "content" and k != "chunk_index"}
                            }
                        )
                        documents.append(doc)

        return documents

    def merge_chunks_with_overlap(self, chunks: list) -> str:
        """overlap 정보를 사용하여 청크를 정확하게 병합"""
        if not chunks:
            return ""

        if len(chunks) == 1:
            try:
                return chunks[0].get("content", "") if isinstance(chunks[0], dict) else str(chunks[0])
            except (IndexError, KeyError, TypeError):
                return ""

        try:
            merged = chunks[0].get("content", "") if isinstance(chunks[0], dict) else str(chunks[0])
        except (IndexError, KeyError, TypeError):
            return ""

        for i in range(1, len(chunks)):
            try:
                current = chunks[i] if i < len(chunks) else None
                prev = chunks[i - 1] if i - 1 >= 0 else None

                if current is None or prev is None:
                    continue

                if not isinstance(current, dict) or not isinstance(prev, dict):
                    merged += str(current) if current else ""
                    continue

                prev_overlap_dict = prev.get("overlap_next", {})
                curr_overlap_dict = current.get("overlap_prev", {})
                prev_overlap = prev_overlap_dict.get("text", "") if isinstance(prev_overlap_dict, dict) else ""
                curr_overlap = curr_overlap_dict.get("text", "") if isinstance(curr_overlap_dict, dict) else ""

                if prev_overlap and curr_overlap:
                    if prev_overlap == curr_overlap:
                        overlap_len = len(prev_overlap)
                        current_content = current.get("content", "")
                        if len(current_content) > overlap_len:
                            merged += current_content[overlap_len:]
                        else:
                            merged += current_content
                    else:
                        if len(prev_overlap) > 0 and len(curr_overlap) > 0:
                            common_suffix = ""
                            for j in range(1, min(len(prev_overlap), len(curr_overlap)) + 1):
                                if prev_overlap[-j:] == curr_overlap[:j]:
                                    common_suffix = prev_overlap[-j:]

                            current_content = current.get("content", "")
                            if common_suffix:
                                merged += current_content[len(common_suffix):]
                            else:
                                merged += current_content
                        else:
                            merged += current.get("content", "")
                else:
                    merged += current.get("content", "")
            except Exception:
                continue

        return merged

    def extract_pages(self, pdf_path: str) -> list:
        """PDF 페이지별 텍스트 추출"""
        reader = PdfReader(pdf_path)
        pages_text = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            pages_text.append({
                "page_number": page_num,
                "text": page_text
            })

        return pages_text
