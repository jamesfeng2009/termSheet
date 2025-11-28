"""TS extraction data models for the TS Contract Alignment System."""

from dataclasses import dataclass, field
from typing import Any, List

from .enums import TermCategory


@dataclass
class ExtractedTerm:
    """
    Term extracted from a Term Sheet document.
    
    Represents a single business term extracted from a TS,
    including its category, value, source location, and confidence score.
    """
    id: str
    category: TermCategory
    title: str
    value: Any  # Can be string, number, or structured data
    raw_text: str
    source_section_id: str
    source_paragraph_id: str
    confidence: float
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TSExtractionResult:
    """
    Result of TS information extraction.
    
    Contains all extracted terms from a Term Sheet document,
    along with any sections that could not be recognized.
    """
    document_id: str
    terms: List[ExtractedTerm] = field(default_factory=list)
    unrecognized_sections: List[str] = field(default_factory=list)
    extraction_timestamp: str = ""

    def __post_init__(self):
        if self.terms is None:
            self.terms = []
        if self.unrecognized_sections is None:
            self.unrecognized_sections = []
