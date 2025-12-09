"""Simple semantic refiner example for TS extraction.

This module provides a minimal ISemanticRefiner implementation that
illustrates how a semantic/ML layer could refine rule-based extraction
results. It does *not* perform real semantic modeling; instead, it uses
simple heuristics based on term confidence, raw text length, and
keyword hints to adjust confidence scores and add metadata flags.
"""

from __future__ import annotations

from typing import Iterable

from .hybrid_extractor import ISemanticRefiner
from ..models.document import ParsedDocument
from ..models.extraction import TSExtractionResult, ExtractedTerm
from ..models.enums import TermCategory


class SimpleSemanticRefiner(ISemanticRefiner):
    """A minimal semantic refiner using lightweight heuristics.

    This refiner is intended as a demonstration of how the semantic
    layer in the hybrid extraction pipeline could work. It:

    - Scans existing ExtractedTerm objects produced by the rule-based
      extractor.
    - Identifies low-confidence terms.
    - Applies simple heuristics (section length and basic keyword
      presence) to slightly adjust confidence and annotate metadata.

    It does not add or remove terms; it only annotates and, in some
    cases, nudges confidence values upward or downward within a safe
    range.
    """

    def __init__(self, low_confidence_threshold: float = 0.4, high_confidence_cap: float = 0.9):
        self._low_conf_threshold = low_confidence_threshold
        self._high_conf_cap = high_confidence_cap

    def refine(self, parsed_doc: ParsedDocument, rule_result: TSExtractionResult) -> TSExtractionResult:
        refined_terms: list[ExtractedTerm] = []

        for term in rule_result.terms:
            refined_terms.append(self._refine_term(term))

        return TSExtractionResult(
            document_id=rule_result.document_id,
            terms=refined_terms,
            unrecognized_sections=rule_result.unrecognized_sections,
            extraction_timestamp=rule_result.extraction_timestamp,
        )

    def _refine_term(self, term: ExtractedTerm) -> ExtractedTerm:
        """Apply simple heuristics to refine a single term.

        Heuristics:
        - If confidence is below the low-confidence threshold but the
          raw text is reasonably long and contains category-related
          keywords, slightly increase confidence.
        - Add metadata flags indicating that the term has been processed
          by the semantic refiner and whether confidence was adjusted.
        """
        metadata = dict(term.metadata or {})
        metadata.setdefault("semantic_refined", True)

        updated_confidence = term.confidence
        adjusted = False

        # Heuristic: promote low-confidence terms when the raw text is
        # non-trivial and contains indicative keywords for the category.
        if term.confidence < self._low_conf_threshold:
            raw_text = term.raw_text or ""
            if self._is_informative_text(raw_text) and self._has_category_hints(term.category, raw_text):
                boost = 0.15
                updated_confidence = min(self._high_conf_cap, term.confidence + boost)
                adjusted = True

        if adjusted:
            metadata["semantic_confidence_adjusted"] = True
            metadata["semantic_original_confidence"] = term.confidence
            metadata["semantic_adjusted_confidence"] = updated_confidence
        else:
            metadata.setdefault("semantic_confidence_adjusted", False)

        return ExtractedTerm(
            id=term.id,
            category=term.category,
            title=term.title,
            value=term.value,
            raw_text=term.raw_text,
            source_section_id=term.source_section_id,
            source_paragraph_id=term.source_paragraph_id,
            confidence=updated_confidence,
            metadata=metadata,
        )

    def _is_informative_text(self, text: str) -> bool:
        """Check if text is long enough to be considered informative."""
        stripped = text.strip()
        # Require a minimal length to avoid promoting very short fragments.
        return len(stripped) >= 30

    def _has_category_hints(self, category: TermCategory, text: str) -> bool:
        """Check for simple keyword hints related to the term category."""
        text_lower = text.lower()

        hints: dict[TermCategory, Iterable[str]] = {
            TermCategory.INVESTMENT_AMOUNT: ["investment", "amount", "capital", "投资", "金额"],
            TermCategory.VALUATION: ["valuation", "pre-money", "post-money", "估值"],
            TermCategory.PRICING: ["price", "per share", "股价", "价格"],
            TermCategory.BOARD_SEATS: ["board", "director", "seat", "董事"],
            TermCategory.VOTING_RIGHTS: ["voting", "vote", "表决", "投票"],
            TermCategory.LIQUIDATION_PREFERENCE: ["liquidation", "preference", "清算", "优先"],
            TermCategory.ANTI_DILUTION: ["anti-dilution", "dilution", "反稀释", "反摊薄"],
            TermCategory.INFORMATION_RIGHTS: ["information", "report", "信息", "报告"],
            TermCategory.CLOSING_CONDITIONS: ["closing", "condition", "交割", "条件"],
            TermCategory.CONDITIONS_PRECEDENT: ["condition precedent", "先决", "前提"],
        }

        for hint in hints.get(category, []):
            if hint.lower() in text_lower:
                return True
        return False
