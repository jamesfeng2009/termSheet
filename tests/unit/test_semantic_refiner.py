"""Unit tests for SimpleSemanticRefiner.

This test module verifies the basic heuristic behaviour of
SimpleSemanticRefiner:

- Low-confidence terms with informative text and category-specific
  keywords get a small confidence boost and appropriate metadata.
- High-confidence terms or terms without hints are left unchanged
  (except for semantic metadata flags).
"""

from __future__ import annotations

from datetime import datetime

from ts_contract_alignment.extractors.semantic_refiner import SimpleSemanticRefiner
from ts_contract_alignment.models.enums import TermCategory
from ts_contract_alignment.models.extraction import ExtractedTerm, TSExtractionResult


def _make_term(
    *,
    category: TermCategory,
    confidence: float,
    raw_text: str,
    value: str | None = None,
) -> ExtractedTerm:
    """Helper to construct a minimal ExtractedTerm for testing."""
    return ExtractedTerm(
        id="term_test",
        category=category,
        title=f"{category.value} term",
        value=value or raw_text,
        raw_text=raw_text,
        source_section_id="sec_1",
        source_paragraph_id="para_1",
        confidence=confidence,
        metadata={},
    )


def _make_result(term: ExtractedTerm) -> TSExtractionResult:
    return TSExtractionResult(
        document_id="doc_test",
        terms=[term],
        unrecognized_sections=[],
        extraction_timestamp=datetime.utcnow().isoformat(),
    )


def test_simple_semantic_refiner_boosts_low_confidence_term_with_hints() -> None:
    """Low-confidence term with informative text and hints should be boosted."""
    # Text is long enough and contains investment amount hints.
    raw_text = (
        "The total investment amount shall be RMB 10,000,000 and will be "
        "contributed by the Investor in one tranche. 投资金额为1000万元人民币。"
    )
    term = _make_term(
        category=TermCategory.INVESTMENT_AMOUNT,
        confidence=0.3,
        raw_text=raw_text,
    )
    result = _make_result(term)

    refiner = SimpleSemanticRefiner(low_confidence_threshold=0.4, high_confidence_cap=0.9)

    refined = refiner.refine(parsed_doc=None, rule_result=result)  # type: ignore[arg-type]
    assert len(refined.terms) == 1
    refined_term = refined.terms[0]

    # Confidence should be boosted but capped.
    assert refined_term.confidence > term.confidence
    assert refined_term.confidence <= 0.9

    # Metadata flags should indicate adjustment.
    assert refined_term.metadata.get("semantic_refined") is True
    assert refined_term.metadata.get("semantic_confidence_adjusted") is True
    assert refined_term.metadata.get("semantic_original_confidence") == term.confidence
    assert refined_term.metadata.get("semantic_adjusted_confidence") == refined_term.confidence


def test_simple_semantic_refiner_does_not_adjust_high_confidence_term() -> None:
    """High-confidence term should not be adjusted by the refiner."""
    raw_text = "Investment amount: RMB 10,000,000. 投资金额为1000万元人民币。"
    term = _make_term(
        category=TermCategory.INVESTMENT_AMOUNT,
        confidence=0.8,
        raw_text=raw_text,
    )
    result = _make_result(term)

    refiner = SimpleSemanticRefiner(low_confidence_threshold=0.4, high_confidence_cap=0.9)

    refined = refiner.refine(parsed_doc=None, rule_result=result)  # type: ignore[arg-type]
    refined_term = refined.terms[0]

    # Confidence should remain unchanged.
    assert refined_term.confidence == term.confidence

    # Metadata should still indicate that semantic refinement ran, but no adjustment.
    assert refined_term.metadata.get("semantic_refined") is True
    assert refined_term.metadata.get("semantic_confidence_adjusted") is False


def test_simple_semantic_refiner_does_not_boost_without_hints() -> None:
    """Low-confidence term without category hints should not be boosted."""
    # Intentionally keep the text short and free of category-specific
    # hints such as "investment", "amount", "capital", "投资", or "金额".
    raw_text = "General boilerplate clause."
    term = _make_term(
        category=TermCategory.INVESTMENT_AMOUNT,
        confidence=0.3,
        raw_text=raw_text,
    )
    result = _make_result(term)

    refiner = SimpleSemanticRefiner(low_confidence_threshold=0.4, high_confidence_cap=0.9)

    refined = refiner.refine(parsed_doc=None, rule_result=result)  # type: ignore[arg-type]
    refined_term = refined.terms[0]

    # Confidence should not change because there are no hints and text is short.
    assert refined_term.confidence == term.confidence
    assert refined_term.metadata.get("semantic_refined") is True
    assert refined_term.metadata.get("semantic_confidence_adjusted") is False
