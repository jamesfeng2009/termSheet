"""Legal structuring pipeline implementation (initial in-memory version).

This module defines the high-level interface for the
LegalStructuringPipeline, which is responsible for turning raw
legal/contract documents (and clause summary documents) into a
normalized, searchable structure:

    Document -> Section -> Clause -> ClauseItem -> ParagraphSpan

The current implementation operates purely in memory and is intended as
an incremental first step. It uses the existing ParsedDocument
structure as input and derives simple Section/Clause/ParagraphSpan
records from it. Persistence and production-grade rule logic will be
added in later iterations.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.document import DocumentSection, ParsedDocument, TextSegment
from .models import (
    ClauseItemRecord,
    ClauseRecord,
    DocumentRecord,
    ParagraphSpanRecord,
    QualityIssue,
    QualityReport,
    QualityStats,
    SectionRecord,
)


@dataclass
class StructuringConfig:
    """Configuration options for the LegalStructuringPipeline.

    This config object is intentionally minimal at this stage. It will be
    extended as concrete structuring rules (e.g., heading patterns,
    sub-item markers, role/region classification policies) are
    implemented.
    """

    enable_vectorization: bool = True
    max_doc_length: int = 200_000
    policies: Optional[Dict[str, Any]] = None


class LegalStructuringPipeline:
    """Pipeline for legal document structuring.

    Responsibilities:

    - Ingest raw files or ParsedDocument instances.
    - Detect and build the structural hierarchy:
      Document -> Section -> Clause -> ClauseItem -> ParagraphSpan.
    - Optionally vectorize clause and clause item content.
    - Perform basic quality checks and produce a QualityReport.

    At this stage only the public interface is defined; internal
    implementation details will be added later.
    """

    def __init__(
        self,
        config: Optional[StructuringConfig] = None,
        # Dependencies such as db_manager, embedding_model, or
        # configuration manager can be threaded in here later.
        **_: Any,
    ) -> None:
        """Initialize the structuring pipeline.

        Args:
            config: Optional configuration object. When omitted, a
                default StructuringConfig will be used.
            **_: Placeholder for future dependencies (e.g., database
                manager, embedding model, configuration manager).
        """

        self.config = config or StructuringConfig()

        # In-memory stores for the initial prototype implementation.
        # These allow vectorize_document and validate_document to operate
        # on the results of ingest_parsed without requiring a database.
        self._documents: Dict[str, DocumentRecord] = {}
        self._sections: Dict[str, List[SectionRecord]] = {}
        self._clauses: Dict[str, List[ClauseRecord]] = {}
        self._items: Dict[str, List[ClauseItemRecord]] = {}
        self._spans: Dict[str, List[ParagraphSpanRecord]] = {}

    def ingest_document(self, file_path: str, meta: Dict[str, Any]) -> DocumentRecord:
        """Ingest a document from a file path.

        This method is expected to:

        - Load and parse the file into an internal ParsedDocument.
        - Derive the Document / Section / Clause / ClauseItem /
          ParagraphSpan hierarchy.
        - Persist the resulting records to storage.

        Currently this method is a placeholder and must be implemented in
        a later iteration.
        """

        raise NotImplementedError("ingest_document is not yet implemented")

    def ingest_parsed(
        self,
        parsed: ParsedDocument,
        meta: Dict[str, Any],
    ) -> DocumentRecord:
        """Ingest a document starting from an existing ParsedDocument.

        This variant assumes that parsing from the raw file has already
        been performed by DocumentParser or another upstream component.

        Currently this method implements a simple, in-memory mapping from
        ParsedDocument to Section/Clause/ParagraphSpan records. The
        logic is intentionally conservative and can be refined as
        structuring rules mature.
        """

        # Create or update the in-memory DocumentRecord for this parsed
        # document. We intentionally trust the ParsedDocument.id as the
        # stable identifier at this stage.
        doc_id = parsed.id
        document = DocumentRecord(
            id=doc_id,
            name=parsed.filename,
            ingest_channel=str(meta.get("ingest_channel", "unknown")),
            created_at=str(
                meta.get("created_at")
                or datetime.utcnow().isoformat(timespec="seconds")
            ),
            file_ref=dict(meta.get("file_ref", {})),
            checksum=str(meta.get("checksum", "")),
            metadata=dict(meta.get("metadata", {})),
        )
        self._documents[doc_id] = document

        sections: List[SectionRecord] = []
        clauses: List[ClauseRecord] = []
        spans: List[ParagraphSpanRecord] = []

        section_index = 1
        clause_index = 1
        span_index = 1

        for section in parsed.sections:
            # Derive a SectionRecord for every DocumentSection.
            section_id = f"{doc_id}-sec-{section_index}"

            section_start, section_end = self._compute_section_span(section)
            section_loc: Dict[str, Any] = {
                "char_span": [section_start, section_end],
                "level": getattr(section.level, "value", int(section.level)),
            }

            section_record = SectionRecord(
                id=section_id,
                doc_id=doc_id,
                order_index=section_index,
                level=int(section_loc["level"]),
                title=section.title or section.number or "",
                loc=section_loc,
            )
            sections.append(section_record)
            section_index += 1

            # For the initial version we treat the whole section body as a
            # single ClauseRecord by concatenating all text segments.
            clause_id = f"{doc_id}-cl-{clause_index}"
            clause_content, clause_lang = self._collect_section_text(section)

            clause_loc: Dict[str, Any] = {
                "char_span": [section_start, section_end],
                "section_id": section_id,
            }

            clause_record = ClauseRecord(
                id=clause_id,
                doc_id=doc_id,
                section_id=section_id,
                order_index=clause_index,
                title=section.title or section.number,
                lang=clause_lang,
                content=clause_content,
                loc=clause_loc,
            )
            clauses.append(clause_record)
            clause_index += 1

            # Create a ParagraphSpanRecord for each TextSegment so that
            # callers can later reconstruct the original layout or run
            # fine-grained comparisons.
            for seg in section.segments:
                span_id = f"{clause_id}-span-{span_index}"
                span_record = ParagraphSpanRecord(
                    id=span_id,
                    owner_type="Clause",
                    owner_id=clause_id,
                    seq=span_index,
                    raw_text=seg.content,
                    style=dict(seg.formatting or {}),
                    loc={"char_span": [seg.start_pos, seg.end_pos]},
                )
                spans.append(span_record)
                span_index += 1

        self._sections[doc_id] = sections
        self._clauses[doc_id] = clauses
        self._spans[doc_id] = spans
        # Clause items are not derived in this first iteration and remain
        # empty until more advanced structuring rules are implemented.
        self._items.setdefault(doc_id, [])

        return document

    def vectorize_document(self, doc_id: str) -> None:
        """Create embeddings for a structured document.

        This method is expected to compute vector representations for
        clause and clause item content and persist them via the
        underlying storage/embedding backend.

        The current implementation does *not* call any external
        embedding service. Instead, it assigns a simple, deterministic
        placeholder vector based on content length so that downstream
        quality checks and experiments can proceed without a full
        vectorization pipeline.
        """

        if doc_id not in self._documents:
            raise ValueError(f"Document '{doc_id}' has not been ingested")

        clauses = self._clauses.get(doc_id, [])
        items = self._items.get(doc_id, [])

        for clause in clauses:
            if clause.content:
                # Simple placeholder: one-dimensional vector equal to the
                # content length. This should be replaced with a real
                # embedding in a future iteration.
                clause.embedding = [float(len(clause.content))]
            else:
                clause.embedding = None

        for item in items:
            if item.content:
                item.embedding = [float(len(item.content))]
            else:
                item.embedding = None

    def validate_document(self, doc_id: str) -> QualityReport:
        """Run quality checks on a structured document.

        Quality checks are expected to include, for example:

        - Continuity and uniqueness of order_index values.
        - Non-empty content ratios for clauses.
        - Embedding coverage when vectorization is enabled.

        The current implementation performs basic structural and
        embedding coverage checks on the in-memory records produced by
        ingest_parsed and (optionally) vectorize_document.
        """

        if doc_id not in self._documents:
            raise ValueError(f"Document '{doc_id}' has not been ingested")

        clauses = self._clauses.get(doc_id, [])
        items = self._items.get(doc_id, [])

        issues: List[QualityIssue] = []

        total_clauses = len(clauses)
        non_empty_clauses = sum(1 for c in clauses if c.content.strip())

        # Include clause items when assessing embedding coverage, as both
        # may be used for semantic retrieval.
        all_units = clauses + items
        total_units = len(all_units)
        missing_embeddings = sum(1 for u in all_units if u.embedding is None)

        if total_clauses == 0:
            clause_non_empty_ratio = 0.0
        else:
            clause_non_empty_ratio = non_empty_clauses / total_clauses

        if total_units == 0:
            embedding_missing_ratio = 0.0
        else:
            embedding_missing_ratio = missing_embeddings / total_units

        # Check that clause order_index values are continuous starting at 1.
        indices = sorted(c.order_index for c in clauses)
        order_index_continuous = indices == list(range(1, len(indices) + 1))

        # Populate issues based on the basic quality thresholds described
        # in the structuring requirements.
        if total_clauses == 0:
            issues.append(
                QualityIssue(
                    code="NO_CLAUSES",
                    message="No clauses were produced for the document.",
                    severity="error",
                )
            )
        elif clause_non_empty_ratio < 0.95:
            issues.append(
                QualityIssue(
                    code="CLAUSE_CONTENT_RATIO_LOW",
                    message=(
                        "Non-empty clause content ratio below 95%: "
                        f"{clause_non_empty_ratio:.3f}"
                    ),
                    severity="warning",
                )
            )

        if not order_index_continuous:
            issues.append(
                QualityIssue(
                    code="NON_CONTIGUOUS_ORDER_INDEX",
                    message="Clause order_index values are not contiguous.",
                    severity="warning",
                )
            )

        if self.config.enable_vectorization and embedding_missing_ratio > 0.01:
            issues.append(
                QualityIssue(
                    code="EMBEDDING_MISSING_RATIO_HIGH",
                    message=(
                        "Embedding missing ratio above 1%: "
                        f"{embedding_missing_ratio:.3f}"
                    ),
                    severity="warning",
                )
            )

        stats = QualityStats(
            clause_non_empty_ratio=clause_non_empty_ratio,
            embedding_missing_ratio=embedding_missing_ratio,
            order_index_continuous=order_index_continuous,
        )

        passed = not any(issue.severity == "error" for issue in issues)

        return QualityReport(
            doc_id=doc_id,
            passed=passed,
            issues=issues,
            stats=stats,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_section_span(section: DocumentSection) -> tuple[int, int]:
        """Compute an approximate character span for a section.

        This helper inspects the section's text segments and returns a
        (start, end) character offset pair. When no segments are
        available, it falls back to (0, 0).
        """

        if not section.segments:
            return 0, 0

        start = min(seg.start_pos for seg in section.segments)
        end = max(seg.end_pos for seg in section.segments)
        return start, end

    @staticmethod
    def _collect_section_text(section: DocumentSection) -> tuple[str, str]:
        """Concatenate all text segments in a section.

        Returns a tuple of (content, language), where language is
        derived from the first available TextSegment. This is a
        conservative first implementation that can be refined later.
        """

        if not section.segments:
            return "", "mixed"

        contents: List[str] = []
        language = section.segments[0].language or "mixed"

        for seg in section.segments:
            if seg.content:
                contents.append(seg.content)

        return "\n".join(contents), language
