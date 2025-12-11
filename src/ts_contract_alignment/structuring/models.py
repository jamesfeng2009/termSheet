"""Data models for legal document structuring.

These dataclasses define the in-memory representation of the
Document / Section / Clause / ClauseItem / ParagraphSpan hierarchy
used by the LegalStructuringPipeline.

The goal is to mirror the conceptual schema you described while
staying independent from any particular persistence layer (ORM / DB).
Concrete parsing, persistence, and retrieval logic will be implemented
elsewhere.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DocumentRecord:
    """Represents a single ingested document and its high-level metadata.

    This corresponds to the logical "Document" entity in the structuring
    design and is not tied to any specific storage implementation.
    """

    id: str
    name: str
    ingest_channel: str
    created_at: str
    file_ref: Dict[str, Any]
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionRecord:
    """Represents a structural section/chapter within a document.

    Sections capture the outline-level structure (e.g., chapters,
    numbered headings) but are *not* vectorized themselves.
    """

    id: str
    doc_id: str
    order_index: int
    level: int
    title: str
    loc: Dict[str, Any]


@dataclass
class ClauseRecord:
    """Represents a single clause within a document.

    Clauses are the primary units for semantic retrieval and are intended
    to be vectorized based on the `content` field. They may optionally be
    associated with a parent section.
    """

    id: str
    doc_id: str
    section_id: Optional[str]
    order_index: int
    title: Optional[str]
    lang: str
    content: str
    embedding: Optional[List[float]] = None
    loc: Dict[str, Any] = field(default_factory=dict)
    # Business role fields: CLAUSE / NON_CLAUSE, MAIN / COVER / APPENDIX / SIGN, etc.
    role: str = "CLAUSE"
    region: str = "MAIN"
    nc_type: Optional[str] = None


@dataclass
class ClauseItemRecord:
    """Represents a sub-item within a clause.

    Clause items capture fine-grained conditions such as numbered or
    lettered sub-items (e.g., "(一)", "(a)"). They can form a tree via
    `parent_item_id` and may optionally be vectorized.
    """

    id: str
    clause_id: str
    parent_item_id: Optional[str]
    order_index: int
    title: Optional[str]
    lang: str
    content: str
    embedding: Optional[List[float]] = None
    loc: Dict[str, Any] = field(default_factory=dict)
    role: str = "CLAUSE"
    region: str = "MAIN"
    nc_type: Optional[str] = None


@dataclass
class ParagraphSpanRecord:
    """Represents a raw paragraph or line span belonging to a clause or item.

    Paragraph spans are useful for faithfully reconstructing the original
    layout, running fine-grained comparisons, or performing style-aware
    processing. They are not necessarily vectorized.
    """

    id: str
    owner_type: str  # "Clause" or "ClauseItem"
    owner_id: str
    seq: int
    raw_text: str
    style: Dict[str, Any] = field(default_factory=dict)
    loc: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityIssue:
    """Represents a single quality issue found during validation.

    Examples include missing content, non-contiguous order indices, or
    excessive embedding failures.
    """

    code: str
    message: str
    severity: str  # e.g. "error" or "warning"


@dataclass
class QualityStats:
    """Aggregated statistics about the structured representation.

    These fields are intended to support automated quality checks and
    basic monitoring of structuring performance.
    """

    clause_non_empty_ratio: float
    embedding_missing_ratio: float
    order_index_continuous: bool


@dataclass
class QualityReport:
    """Validation report for a single structured document.

    The report captures whether quality checks passed, a list of
    detected issues, and basic statistics. It is produced by the
    LegalStructuringPipeline during validation.
    """

    doc_id: str
    passed: bool
    issues: List[QualityIssue] = field(default_factory=list)
    stats: Optional[QualityStats] = None
