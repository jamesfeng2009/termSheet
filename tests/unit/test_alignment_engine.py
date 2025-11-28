"""Unit tests for the Alignment Engine.

Tests the rule-based matcher, semantic matcher, and alignment engine
functionality for TS-to-template alignment.
"""

import pytest
from ts_contract_alignment.alignment import AlignmentEngine, RuleBasedMatcher, SemanticMatcher
from ts_contract_alignment.models.extraction import ExtractedTerm, TSExtractionResult
from ts_contract_alignment.models.template import (
    AnalyzedClause,
    TemplateAnalysisResult,
    FillableSegment,
    FillableType,
)
from ts_contract_alignment.models.enums import (
    TermCategory,
    ClauseCategory,
    ActionType,
    MatchMethod,
)


class TestRuleBasedMatcher:
    """Tests for the RuleBasedMatcher class."""

    def test_match_investment_amount_to_investment_terms(self):
        """Test matching investment amount term to investment terms clause."""
        matcher = RuleBasedMatcher()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.INVESTMENT_AMOUNT,
            title="Investment Amount",
            value="USD 10,000,000",
            raw_text="The total investment amount is USD 10,000,000",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Investment Terms",
            category=ClauseCategory.INVESTMENT_TERMS,
            full_text="The investor shall invest capital in the company.",
            fillable_segments=[],
            keywords=["investment", "capital"],
            semantic_embedding=None
        )
        
        matches = matcher.match(term, [clause])
        
        assert len(matches) > 0
        assert matches[0][0].id == "clause_001"
        assert matches[0][2] > 0.5  # Confidence should be reasonable


    def test_match_by_title_exact(self):
        """Test matching by exact title match."""
        matcher = RuleBasedMatcher()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.LIQUIDATION_PREFERENCE,
            title="Liquidation Preference",
            value="1x",
            raw_text="Liquidation Preference: 1x non-participating",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Liquidation Preference",
            category=ClauseCategory.LIQUIDATION,
            full_text="Upon liquidation, preferred shareholders receive...",
            fillable_segments=[],
            keywords=["liquidation", "preference"],
            semantic_embedding=None
        )
        
        matches = matcher.match(term, [clause])
        
        assert len(matches) > 0
        assert matches[0][1] == MatchMethod.RULE_TITLE
        assert matches[0][2] >= 0.9  # High confidence for exact title match

    def test_no_match_for_unrelated_categories(self):
        """Test that unrelated categories don't match."""
        matcher = RuleBasedMatcher()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.BOARD_SEATS,
            title="Board Seats",
            value="2 seats",
            raw_text="Investor shall have 2 board seats",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        # Clause is about liquidation, not governance
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Liquidation",
            category=ClauseCategory.LIQUIDATION,
            full_text="Upon liquidation of the company...",
            fillable_segments=[],
            keywords=["liquidation"],
            semantic_embedding=None
        )
        
        matches = matcher.match(term, [clause])
        
        # Should have no matches or very low confidence
        assert len(matches) == 0 or matches[0][2] < 0.5

    def test_get_expected_clause_categories(self):
        """Test getting expected clause categories for term categories."""
        matcher = RuleBasedMatcher()
        
        # Investment amount should map to investment terms
        categories = matcher.get_expected_clause_categories(TermCategory.INVESTMENT_AMOUNT)
        assert ClauseCategory.INVESTMENT_TERMS in categories
        
        # Board seats should map to governance
        categories = matcher.get_expected_clause_categories(TermCategory.BOARD_SEATS)
        assert ClauseCategory.GOVERNANCE in categories


class TestSemanticMatcher:
    """Tests for the SemanticMatcher class."""

    def test_semantic_matcher_without_model(self):
        """Test that semantic matcher returns empty when no model is provided."""
        matcher = SemanticMatcher(embedding_model=None)
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.INVESTMENT_AMOUNT,
            title="Investment Amount",
            value="USD 10,000,000",
            raw_text="Investment amount is USD 10,000,000",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Investment",
            category=ClauseCategory.INVESTMENT_TERMS,
            full_text="The investment amount shall be...",
            fillable_segments=[],
            keywords=[],
            semantic_embedding=None
        )
        
        matches = matcher.match(term, [clause])
        
        assert len(matches) == 0
        assert not matcher.is_available

    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        matcher = SemanticMatcher()
        
        # Identical vectors should have similarity 1.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        assert matcher._cosine_similarity(vec1, vec2) == pytest.approx(1.0)
        
        # Orthogonal vectors should have similarity 0.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert matcher._cosine_similarity(vec1, vec2) == pytest.approx(0.0)
        
        # Opposite vectors should have similarity -1.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        assert matcher._cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_set_similarity_threshold(self):
        """Test setting similarity threshold."""
        matcher = SemanticMatcher()
        
        matcher.set_similarity_threshold(0.8)
        assert matcher.get_similarity_threshold() == 0.8
        
        with pytest.raises(ValueError):
            matcher.set_similarity_threshold(1.5)
        
        with pytest.raises(ValueError):
            matcher.set_similarity_threshold(-0.1)



class TestAlignmentEngine:
    """Tests for the AlignmentEngine class."""

    def test_align_single_term(self):
        """Test aligning a single term to a matching clause."""
        engine = AlignmentEngine()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.INVESTMENT_AMOUNT,
            title="Investment Amount",
            value="USD 10,000,000",
            raw_text="The total investment amount is USD 10,000,000",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=[term],
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Investment Terms",
            category=ClauseCategory.INVESTMENT_TERMS,
            full_text="The investor shall invest capital in the company.",
            fillable_segments=[],
            keywords=["investment", "capital"],
            semantic_embedding=None
        )
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=[clause],
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        assert len(result.matches) == 1
        assert result.matches[0].ts_term_id == "term_001"
        assert result.matches[0].clause_id == "clause_001"
        assert len(result.unmatched_terms) == 0

    def test_align_with_unmatched_term(self):
        """Test alignment when a term cannot be matched."""
        engine = AlignmentEngine()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.ANTI_DILUTION,
            title="Anti-Dilution",
            value="Weighted average",
            raw_text="Anti-dilution protection: weighted average",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=[term],
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        # Clause is about definitions, not anti-dilution
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Definitions",
            category=ClauseCategory.DEFINITIONS,
            full_text="The following terms shall have the meanings set forth below.",
            fillable_segments=[],
            keywords=["definitions", "terms"],
            semantic_embedding=None
        )
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=[clause],
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        # Term should be unmatched
        assert len(result.unmatched_terms) == 1
        assert "Anti-Dilution" in result.unmatched_terms[0]

    def test_action_classification_insert(self):
        """Test that INSERT action is classified for placeholder values."""
        engine = AlignmentEngine()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.INVESTMENT_AMOUNT,
            title="Investment Amount",
            value="USD 10,000,000",
            raw_text="Investment amount: USD 10,000,000",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=[term],
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Investment Terms",
            category=ClauseCategory.INVESTMENT_TERMS,
            full_text="The investor shall invest [amount] in the company.",
            fillable_segments=[
                FillableSegment(
                    id="fill_001",
                    location_start=25,
                    location_end=33,
                    expected_type=FillableType.CURRENCY,
                    context_before="invest",
                    context_after="in the company",
                    current_value="[amount]"  # Placeholder
                )
            ],
            keywords=["investment"],
            semantic_embedding=None
        )
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=[clause],
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        assert len(result.matches) == 1
        assert result.matches[0].action == ActionType.INSERT

    def test_action_classification_override(self):
        """Test that OVERRIDE action is classified for existing values."""
        engine = AlignmentEngine()
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.INVESTMENT_AMOUNT,
            title="Investment Amount",
            value="USD 10,000,000",
            raw_text="Investment amount: USD 10,000,000",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.9,
            metadata={}
        )
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=[term],
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Investment Terms",
            category=ClauseCategory.INVESTMENT_TERMS,
            full_text="The investor shall invest USD 5,000,000 in the company.",
            fillable_segments=[
                FillableSegment(
                    id="fill_001",
                    location_start=25,
                    location_end=38,
                    expected_type=FillableType.CURRENCY,
                    context_before="invest",
                    context_after="in the company",
                    current_value="USD 5,000,000"  # Existing value
                )
            ],
            keywords=["investment"],
            semantic_embedding=None
        )
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=[clause],
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        assert len(result.matches) == 1
        assert result.matches[0].action == ActionType.OVERRIDE

    def test_confidence_threshold(self):
        """Test confidence threshold setting and getting."""
        engine = AlignmentEngine(confidence_threshold=0.8)
        
        assert engine.get_confidence_threshold() == 0.8
        
        engine.set_confidence_threshold(0.6)
        assert engine.get_confidence_threshold() == 0.6
        
        with pytest.raises(ValueError):
            engine.set_confidence_threshold(1.5)

    def test_needs_review_flag(self):
        """Test that low confidence matches are flagged for review."""
        engine = AlignmentEngine(confidence_threshold=0.9)
        
        term = ExtractedTerm(
            id="term_001",
            category=TermCategory.OTHER,
            title="Other Term",
            value="Some value",
            raw_text="Some other term with value",
            source_section_id="sec_001",
            source_paragraph_id="para_001",
            confidence=0.5,
            metadata={}
        )
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=[term],
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        clause = AnalyzedClause(
            id="clause_001",
            section_id="sec_001",
            title="Miscellaneous",
            category=ClauseCategory.MISCELLANEOUS,
            full_text="Other provisions and terms.",
            fillable_segments=[],
            keywords=["other"],
            semantic_embedding=None
        )
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=[clause],
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        # Match should be flagged for review due to low confidence
        if result.matches:
            assert result.matches[0].needs_review is True

    def test_multiple_terms_alignment(self):
        """Test aligning multiple terms to multiple clauses."""
        engine = AlignmentEngine()
        
        terms = [
            ExtractedTerm(
                id="term_001",
                category=TermCategory.INVESTMENT_AMOUNT,
                title="Investment Amount",
                value="USD 10,000,000",
                raw_text="Investment amount: USD 10,000,000",
                source_section_id="sec_001",
                source_paragraph_id="para_001",
                confidence=0.9,
                metadata={}
            ),
            ExtractedTerm(
                id="term_002",
                category=TermCategory.BOARD_SEATS,
                title="Board Seats",
                value="2 seats",
                raw_text="Board seats: 2 seats for investor",
                source_section_id="sec_002",
                source_paragraph_id="para_002",
                confidence=0.9,
                metadata={}
            ),
        ]
        
        ts_result = TSExtractionResult(
            document_id="ts_doc_001",
            terms=terms,
            unrecognized_sections=[],
            extraction_timestamp="2024-01-01T00:00:00"
        )
        
        clauses = [
            AnalyzedClause(
                id="clause_001",
                section_id="sec_001",
                title="Investment Terms",
                category=ClauseCategory.INVESTMENT_TERMS,
                full_text="The investor shall invest capital.",
                fillable_segments=[],
                keywords=["investment", "capital"],
                semantic_embedding=None
            ),
            AnalyzedClause(
                id="clause_002",
                section_id="sec_002",
                title="Board Composition",
                category=ClauseCategory.GOVERNANCE,
                full_text="The board shall consist of directors.",
                fillable_segments=[],
                keywords=["board", "directors"],
                semantic_embedding=None
            ),
        ]
        
        template_result = TemplateAnalysisResult(
            document_id="template_doc_001",
            clauses=clauses,
            structure_map={},
            analysis_timestamp="2024-01-01T00:00:00"
        )
        
        result = engine.align(ts_result, template_result)
        
        assert len(result.matches) == 2
        assert len(result.unmatched_terms) == 0
