"""Document-related data models for the TS Contract Alignment System."""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .enums import DocumentType, HeadingLevel


@dataclass
class TextSegment:
    """
    Text segment with position and formatting information.
    
    Represents a contiguous piece of text within a document section,
    preserving its location, language, and formatting attributes.
    """
    id: str
    content: str
    start_pos: int
    end_pos: int
    language: str  # "zh", "en", "mixed"
    formatting: dict = field(default_factory=dict)  # bold, italic, font_size, etc.

    def __post_init__(self):
        if self.formatting is None:
            self.formatting = {}


@dataclass
class DocumentSection:
    """
    Document section structure with hierarchy support.
    
    Represents a section in a document (chapter, section, subsection, etc.)
    with support for nested children and parent references.
    """
    id: str
    title: Optional[str]
    number: Optional[str]  # "1.1", "第一条" etc.
    level: HeadingLevel
    segments: List[TextSegment] = field(default_factory=list)
    children: List["DocumentSection"] = field(default_factory=list)
    parent_id: Optional[str] = None

    def __post_init__(self):
        if self.segments is None:
            self.segments = []
        if self.children is None:
            self.children = []


@dataclass
class ParsedDocument:
    """
    Parsed document structure.
    
    Represents a fully parsed document with its hierarchical structure,
    metadata, and raw text content.
    """
    id: str
    filename: str
    doc_type: DocumentType
    sections: List[DocumentSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    raw_text: str = ""

    def __post_init__(self):
        if self.sections is None:
            self.sections = []
        if self.metadata is None:
            self.metadata = {}
