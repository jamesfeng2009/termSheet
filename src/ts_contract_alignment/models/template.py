"""Template analysis data models for the TS Contract Alignment System."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FillableType(Enum):
    """Types of fillable segments in contract templates."""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    LIST = "list"


@dataclass
class FillableSegment:
    """
    Fillable segment in a contract template.
    
    Represents a location in the contract that can be filled
    with data from the Term Sheet.
    """
    id: str
    location_start: int
    location_end: int
    expected_type: FillableType
    context_before: str
    context_after: str
    current_value: Optional[str] = None


@dataclass
class AnalyzedClause:
    """
    Analyzed contract clause.
    
    Represents a clause from a contract template that has been
    analyzed for semantic category, fillable segments, and keywords.
    """
    id: str
    section_id: str
    title: str
    category: "ClauseCategory"  # Forward reference to avoid circular import
    full_text: str
    fillable_segments: List[FillableSegment] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    semantic_embedding: Optional[List[float]] = None

    def __post_init__(self):
        if self.fillable_segments is None:
            self.fillable_segments = []
        if self.keywords is None:
            self.keywords = []


@dataclass
class TemplateAnalysisResult:
    """
    Result of contract template analysis.
    
    Contains all analyzed clauses from a contract template,
    along with the structure map for preserving document layout.
    """
    document_id: str
    clauses: List[AnalyzedClause] = field(default_factory=list)
    structure_map: dict = field(default_factory=dict)  # Preserves original structure mapping
    analysis_timestamp: str = ""

    def __post_init__(self):
        if self.clauses is None:
            self.clauses = []
        if self.structure_map is None:
            self.structure_map = {}


# Import ClauseCategory here to resolve forward reference
from .enums import ClauseCategory
