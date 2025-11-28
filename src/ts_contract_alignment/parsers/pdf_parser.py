"""PDF document parser implementation."""

import re
import uuid
from pathlib import Path
from typing import Optional

import pdfplumber
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

from ..models.document import DocumentSection, ParsedDocument, TextSegment
from ..models.enums import DocumentType, HeadingLevel
from .exceptions import DocumentCorruptedError, ParseError, UnsupportedFormatError
from .language_detector import detect_language


class PDFDocumentParser:
    """
    Parser for PDF documents.
    
    Uses PyPDF2 for basic extraction and pdfplumber for
    layout analysis and advanced text extraction.
    """

    # Chinese heading patterns
    CHINESE_HEADING_PATTERNS = [
        (re.compile(r'^第[一二三四五六七八九十百千]+[章篇]'), HeadingLevel.CHAPTER),
        (re.compile(r'^第[一二三四五六七八九十百千]+[条节]'), HeadingLevel.SECTION),
        (re.compile(r'^[一二三四五六七八九十]+[、.]'), HeadingLevel.SECTION),
        (re.compile(r'^\([一二三四五六七八九十]+\)'), HeadingLevel.SUBSECTION),
        (re.compile(r'^[（(][0-9]+[)）]'), HeadingLevel.PARAGRAPH),
    ]

    # Numbered heading patterns
    NUMBERED_HEADING_PATTERNS = [
        (re.compile(r'^(\d+)\s*[.、]?\s*(.*)'), HeadingLevel.CHAPTER),
        (re.compile(r'^(\d+\.\d+)\s*[.、]?\s*(.*)'), HeadingLevel.SECTION),
        (re.compile(r'^(\d+\.\d+\.\d+)\s*[.、]?\s*(.*)'), HeadingLevel.SUBSECTION),
    ]

    def __init__(self):
        self._current_position = 0

    def parse(self, file_path: str) -> ParsedDocument:
        """
        Parse a PDF document and return its structured representation.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            ParsedDocument containing the structured content.
            
        Raises:
            FileNotFoundError: If the file does not exist.
            UnsupportedFormatError: If the file is not a PDF.
            DocumentCorruptedError: If the document is corrupted.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if path.suffix.lower() != ".pdf":
            raise UnsupportedFormatError(
                message=f"Unsupported file format: {path.suffix}",
                file_path=file_path,
                location="file extension"
            )
        
        self._current_position = 0
        
        # Try to open with PyPDF2 first for validation
        try:
            pdf_reader = PdfReader(file_path)
            page_count = len(pdf_reader.pages)
        except PdfReadError as e:
            raise DocumentCorruptedError(
                message="PDF file is corrupted or encrypted",
                file_path=file_path,
                location="file header",
                details={"original_error": str(e)}
            )
        except Exception as e:
            raise ParseError(
                message=f"Failed to open PDF: {str(e)}",
                file_path=file_path,
                details={"original_error": str(e)}
            )
        
        # Use pdfplumber for detailed extraction
        try:
            with pdfplumber.open(file_path) as pdf:
                raw_text = self._extract_raw_text(pdf)
                sections = self._parse_sections(pdf)
                metadata = self._extract_metadata(pdf, path, page_count)
        except Exception as e:
            raise ParseError(
                message=f"Failed to parse PDF content: {str(e)}",
                file_path=file_path,
                details={"original_error": str(e)}
            )
        
        return ParsedDocument(
            id=str(uuid.uuid4()),
            filename=path.name,
            doc_type=DocumentType.PDF,
            sections=sections,
            metadata=metadata,
            raw_text=raw_text
        )

    def _extract_raw_text(self, pdf: pdfplumber.PDF) -> str:
        """Extract all text content from the PDF."""
        text_parts = []
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    def _extract_metadata(self, pdf: pdfplumber.PDF, path: Path, page_count: int) -> dict:
        """Extract document metadata."""
        metadata = {
            "page_count": page_count,
            "word_count": self._count_words(pdf),
            "file_size": path.stat().st_size if path.exists() else 0,
        }
        
        # Extract PDF metadata if available
        if pdf.metadata:
            if pdf.metadata.get("Title"):
                metadata["title"] = pdf.metadata["Title"]
            if pdf.metadata.get("Author"):
                metadata["author"] = pdf.metadata["Author"]
            if pdf.metadata.get("CreationDate"):
                metadata["created"] = pdf.metadata["CreationDate"]
            if pdf.metadata.get("ModDate"):
                metadata["modified"] = pdf.metadata["ModDate"]
        
        return metadata

    def _count_words(self, pdf: pdfplumber.PDF) -> int:
        """Count total words in the PDF."""
        total = 0
        for page in pdf.pages:
            text = page.extract_text() or ""
            # English words
            english_words = len(re.findall(r'[a-zA-Z]+', text))
            # Chinese characters
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            total += english_words + chinese_chars
        return total

    def _parse_sections(self, pdf: pdfplumber.PDF) -> list[DocumentSection]:
        """Parse PDF into hierarchical sections."""
        sections = []
        current_section_stack: list[DocumentSection] = []
        pending_segments: list[TextSegment] = []
        
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if not page_text:
                continue
            
            # Split page into lines/paragraphs
            lines = self._split_into_paragraphs(page_text)
            
            for line in lines:
                if not line.strip():
                    continue
                
                heading_info = self._detect_heading(line, page)
                
                if heading_info:
                    level, number, title = heading_info
                    
                    # Save pending segments
                    if pending_segments and current_section_stack:
                        current_section_stack[-1].segments.extend(pending_segments)
                        pending_segments = []
                    elif pending_segments:
                        root_section = self._create_section(
                            title=None,
                            number=None,
                            level=HeadingLevel.PARAGRAPH,
                            segments=pending_segments
                        )
                        sections.append(root_section)
                        pending_segments = []
                    
                    # Create new section
                    new_section = self._create_section(
                        title=title,
                        number=number,
                        level=level
                    )
                    
                    # Find appropriate parent
                    while current_section_stack and current_section_stack[-1].level.value >= level.value:
                        current_section_stack.pop()
                    
                    if current_section_stack:
                        new_section.parent_id = current_section_stack[-1].id
                        current_section_stack[-1].children.append(new_section)
                    else:
                        sections.append(new_section)
                    
                    current_section_stack.append(new_section)
                else:
                    # Regular text - create segment
                    segment = self._create_text_segment(line, page_num)
                    pending_segments.append(segment)
        
        # Handle remaining segments
        if pending_segments:
            if current_section_stack:
                current_section_stack[-1].segments.extend(pending_segments)
            else:
                root_section = self._create_section(
                    title=None,
                    number=None,
                    level=HeadingLevel.PARAGRAPH,
                    segments=pending_segments
                )
                sections.append(root_section)
        
        return sections

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs based on line breaks and spacing."""
        # Split on double newlines or significant whitespace
        paragraphs = re.split(r'\n\s*\n', text)
        
        result = []
        for para in paragraphs:
            # Further split on single newlines if they appear to be separate items
            lines = para.split('\n')
            current_para = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_para:
                        result.append(' '.join(current_para))
                        current_para = []
                elif self._is_likely_heading(line):
                    if current_para:
                        result.append(' '.join(current_para))
                        current_para = []
                    result.append(line)
                else:
                    current_para.append(line)
            
            if current_para:
                result.append(' '.join(current_para))
        
        return [p for p in result if p.strip()]

    def _is_likely_heading(self, text: str) -> bool:
        """Check if text is likely a heading based on patterns."""
        text = text.strip()
        
        # Check Chinese patterns
        for pattern, _ in self.CHINESE_HEADING_PATTERNS:
            if pattern.match(text):
                return True
        
        # Check numbered patterns
        for pattern, _ in self.NUMBERED_HEADING_PATTERNS:
            if pattern.match(text):
                return True
        
        return False

    def _detect_heading(
        self, 
        text: str, 
        page: pdfplumber.page.Page
    ) -> Optional[tuple[HeadingLevel, Optional[str], str]]:
        """
        Detect if text is a heading and extract its components.
        
        Returns:
            Tuple of (level, number, title) if heading, None otherwise.
        """
        text = text.strip()
        if not text or len(text) > 200:  # Headings are typically short
            return None
        
        # Check Chinese heading patterns
        for pattern, level in self.CHINESE_HEADING_PATTERNS:
            match = pattern.match(text)
            if match:
                number = match.group(0)
                title = text[len(number):].strip() or text
                return (level, number, title)
        
        # Check numbered heading patterns
        for pattern, level in self.NUMBERED_HEADING_PATTERNS:
            match = pattern.match(text)
            if match:
                number = match.group(1)
                title = match.group(2).strip() if len(match.groups()) > 1 else text
                return (level, number, title or text)
        
        return None

    def _create_section(
        self,
        title: Optional[str],
        number: Optional[str],
        level: HeadingLevel,
        segments: Optional[list[TextSegment]] = None
    ) -> DocumentSection:
        """Create a new DocumentSection."""
        return DocumentSection(
            id=str(uuid.uuid4()),
            title=title,
            number=number,
            level=level,
            segments=segments or [],
            children=[],
            parent_id=None
        )

    def _create_text_segment(self, text: str, page_num: int) -> TextSegment:
        """Create a TextSegment from text content."""
        start_pos = self._current_position
        end_pos = start_pos + len(text)
        self._current_position = end_pos + 1
        
        language = detect_language(text)
        
        return TextSegment(
            id=str(uuid.uuid4()),
            content=text,
            start_pos=start_pos,
            end_pos=end_pos,
            language=language,
            formatting={
                "page_number": page_num,
                "bold": False,
                "italic": False,
                "font_size": 12,
            }
        )
