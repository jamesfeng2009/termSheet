"""Alignment Engine implementation for the TS Contract Alignment System.

This module implements the IAlignmentEngine interface to align Term Sheet
terms with contract template clauses using rule-based and semantic methods.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces.alignment import IAlignmentEngine
from ..models.alignment import AlignmentMatch, AlignmentResult
from ..models.enums import ActionType, MatchMethod, TermCategory
from ..models.extraction import ExtractedTerm, TSExtractionResult
from ..models.template import AnalyzedClause, FillableSegment, TemplateAnalysisResult
from .rule_matcher import RuleBasedMatcher
from .semantic_matcher import SemanticMatcher


class AlignmentEngine(IAlignmentEngine):
    """
    Alignment engine for TS-to-template matching.
    
    Combines rule-based and semantic matching to align Term Sheet terms
    with contract template clauses, with confidence scoring and ranking.
    """

    def __init__(
        self,
        embedding_model: Optional[Any] = None,
        db_connection: Optional[Any] = None,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize the alignment engine.
        
        Args:
            embedding_model: Optional sentence-transformers model for semantic matching.
            db_connection: Optional PostgreSQL connection for pgvector queries.
            confidence_threshold: Threshold below which matches need human review.
        """
        self._rule_matcher = RuleBasedMatcher()
        self._semantic_matcher = SemanticMatcher(
            embedding_model=embedding_model,
            similarity_threshold=0.6,
            db_connection=db_connection
        )
        self._confidence_threshold = confidence_threshold
        self._match_counter = 0
        # Optional per-category strategies configured at runtime.
        # Keys are TermCategory.value strings.
        self._action_policies: Dict[str, str] = {}
        self._review_thresholds_by_category: Dict[str, float] = {}

    def align(
        self,
        ts_result: TSExtractionResult,
        template_result: TemplateAnalysisResult,
        config: Optional[dict] = None
    ) -> AlignmentResult:
        """
        Perform alignment between TS terms and template clauses.
        
        Args:
            ts_result: Extracted terms from the Term Sheet.
            template_result: Analyzed clauses from the contract template.
            config: Optional configuration for alignment rules.
            
        Returns:
            AlignmentResult containing all matches and unmatched items.
        """
        self._match_counter = 0
        matches: List[AlignmentMatch] = []
        unmatched_terms: List[str] = []
        matched_clause_ids: set = set()
        
        # Apply configuration if provided
        if config:
            self._apply_config(config)
        
        # Process each term
        for term in ts_result.terms:
            term_matches = self._align_term(term, template_result.clauses)
            
            if term_matches:
                # Take the best match
                best_match = term_matches[0]
                matches.append(best_match)
                matched_clause_ids.add(best_match.clause_id)
            else:
                # Add to unmatched terms with suggested review point
                unmatched_terms.append(
                    self._create_unmatched_term_entry(term)
                )
        
        # Find unmatched clauses
        unmatched_clauses = [
            clause.id for clause in template_result.clauses
            if clause.id not in matched_clause_ids
        ]
        
        return AlignmentResult(
            ts_document_id=ts_result.document_id,
            template_document_id=template_result.document_id,
            matches=matches,
            unmatched_terms=unmatched_terms,
            unmatched_clauses=unmatched_clauses,
            alignment_timestamp=datetime.now(timezone.utc).isoformat()
        )


    def _align_term(
        self,
        term: ExtractedTerm,
        clauses: List[AnalyzedClause]
    ) -> List[AlignmentMatch]:
        """
        Align a single term to clauses using rule-based then semantic matching.
        
        Args:
            term: The extracted term to align.
            clauses: List of analyzed clauses.
            
        Returns:
            List of AlignmentMatch objects sorted by confidence.
        """
        matches: List[AlignmentMatch] = []
        
        # Try rule-based matching first
        rule_matches = self._rule_matcher.match(term, clauses)
        
        for clause, method, confidence in rule_matches:
            match = self._create_match(term, clause, method, confidence)
            matches.append(match)
        
        # If no good rule-based matches, try semantic matching
        if not matches or matches[0].confidence < self._confidence_threshold:
            semantic_matches = self._semantic_matcher.match(term, clauses)
            
            for clause, method, similarity in semantic_matches:
                # Avoid duplicates
                if any(m.clause_id == clause.id for m in matches):
                    continue
                match = self._create_match(term, clause, method, similarity)
                matches.append(match)
        
        # Sort all matches by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        
        return matches

    def _create_match(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause,
        method: MatchMethod,
        confidence: float
    ) -> AlignmentMatch:
        """
        Create an AlignmentMatch object.
        
        Args:
            term: The matched term.
            clause: The matched clause.
            method: The matching method used.
            confidence: The confidence score.
            
        Returns:
            AlignmentMatch object.
        """
        # Find the best fillable segment for this term
        fillable_segment = self._find_best_fillable_segment(term, clause)
        
        # Determine action type based on existing value and optional policy
        action = self._classify_action(term, clause, fillable_segment)
        
        # Determine if human review is needed. If a per-category threshold is
        # configured it takes precedence over the global threshold.
        category_name = term.category.value
        threshold = self._review_thresholds_by_category.get(
            category_name,
            self._confidence_threshold,
        )
        needs_review = confidence < threshold
        
        self._match_counter += 1
        match_id = f"match_{self._match_counter:04d}"
        
        return AlignmentMatch(
            id=match_id,
            ts_term_id=term.id,
            clause_id=clause.id,
            fillable_segment_id=fillable_segment.id if fillable_segment else None,
            match_method=method,
            confidence=confidence,
            action=action,
            needs_review=needs_review
        )

    def _find_best_fillable_segment(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> Optional[FillableSegment]:
        """
        Find the best fillable segment in a clause for a term.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            The best matching FillableSegment, or None if no suitable segment.
        """
        if not clause.fillable_segments:
            return None
        
        # Score each segment based on context and type compatibility
        best_segment = None
        best_score = 0.0
        
        for segment in clause.fillable_segments:
            score = self._score_segment_for_term(term, segment)
            if score > best_score:
                best_score = score
                best_segment = segment
        
        return best_segment if best_score > 0.3 else None

    def _score_segment_for_term(
        self,
        term: ExtractedTerm,
        segment: FillableSegment
    ) -> float:
        """
        Score how well a fillable segment matches a term.
        
        Args:
            term: The extracted term.
            segment: The fillable segment.
            
        Returns:
            Score from 0.0 to 1.0.
        """
        score = 0.0
        
        # Check type compatibility
        type_compatible = self._check_type_compatibility(term, segment)
        if type_compatible:
            score += 0.5
        
        # Check context keywords
        context = (segment.context_before + " " + segment.context_after).lower()
        term_keywords = self._get_term_keywords(term)
        
        keyword_matches = sum(1 for kw in term_keywords if kw.lower() in context)
        if term_keywords:
            score += 0.5 * (keyword_matches / len(term_keywords))
        
        return score

    def _check_type_compatibility(
        self,
        term: ExtractedTerm,
        segment: FillableSegment
    ) -> bool:
        """Check if term type is compatible with segment expected type."""
        from ..models.template import FillableType
        
        # Map term categories to expected fillable types
        category_to_types = {
            TermCategory.INVESTMENT_AMOUNT: [FillableType.CURRENCY, FillableType.NUMBER],
            TermCategory.VALUATION: [FillableType.CURRENCY, FillableType.NUMBER],
            TermCategory.PRICING: [FillableType.CURRENCY, FillableType.NUMBER],
            TermCategory.BOARD_SEATS: [FillableType.NUMBER, FillableType.TEXT],
            TermCategory.VOTING_RIGHTS: [FillableType.PERCENTAGE, FillableType.TEXT],
            TermCategory.LIQUIDATION_PREFERENCE: [FillableType.NUMBER, FillableType.PERCENTAGE],
            TermCategory.ANTI_DILUTION: [FillableType.TEXT],
            TermCategory.INFORMATION_RIGHTS: [FillableType.TEXT],
            TermCategory.CLOSING_CONDITIONS: [FillableType.TEXT, FillableType.DATE],
            TermCategory.CONDITIONS_PRECEDENT: [FillableType.TEXT, FillableType.DATE],
            TermCategory.OTHER: [FillableType.TEXT],
        }
        
        expected_types = category_to_types.get(term.category, [FillableType.TEXT])
        return segment.expected_type in expected_types

    def _get_term_keywords(self, term: ExtractedTerm) -> List[str]:
        """Get keywords associated with a term's category."""
        category_keywords = {
            TermCategory.INVESTMENT_AMOUNT: ["investment", "amount", "capital", "投资", "金额"],
            TermCategory.VALUATION: ["valuation", "value", "估值"],
            TermCategory.PRICING: ["price", "share", "价格", "股"],
            TermCategory.BOARD_SEATS: ["board", "director", "seat", "董事", "席位"],
            TermCategory.VOTING_RIGHTS: ["voting", "vote", "rights", "投票", "表决"],
            TermCategory.LIQUIDATION_PREFERENCE: ["liquidation", "preference", "清算", "优先"],
            TermCategory.ANTI_DILUTION: ["dilution", "adjustment", "稀释", "调整"],
            TermCategory.INFORMATION_RIGHTS: ["information", "reporting", "信息", "报告"],
            TermCategory.CLOSING_CONDITIONS: ["closing", "conditions", "交割", "条件"],
            TermCategory.CONDITIONS_PRECEDENT: ["precedent", "conditions", "先决", "条件"],
        }
        return category_keywords.get(term.category, [])


    def _classify_action(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause,
        fillable_segment: Optional[FillableSegment]
    ) -> ActionType:
        """
        Classify the action type for a match.
        
        Determines whether to INSERT (no existing value) or OVERRIDE
        (existing value present) based on the fillable segment.
        
        Args:
            term: The extracted term.
            clause: The matched clause.
            fillable_segment: The target fillable segment, if any.
            
        Returns:
            ActionType.INSERT or ActionType.OVERRIDE.
        """
        # Honour explicit per-category action policy when provided.
        policy = self._action_policies.get(term.category.value)
        if policy == "insert":
            return ActionType.INSERT
        if policy == "override":
            return ActionType.OVERRIDE

        # If there's a fillable segment with a current value, it's an override
        if fillable_segment and fillable_segment.current_value:
            # Check if current value is a placeholder (not a real value)
            current = fillable_segment.current_value.strip()
            
            # Placeholder patterns that indicate INSERT rather than OVERRIDE
            placeholder_patterns = [
                r'^_{2,}$',  # Underscores only
                r'^\[.*\]$',  # Bracketed placeholder
                r'^XX+$',  # XX placeholder
                r'^YYYY',  # Date placeholder
            ]
            
            import re
            is_placeholder = any(
                re.match(pattern, current) for pattern in placeholder_patterns
            )
            
            if is_placeholder:
                return ActionType.INSERT
            else:
                return ActionType.OVERRIDE
        
        # No fillable segment or no current value means INSERT
        return ActionType.INSERT

    def _create_unmatched_term_entry(self, term: ExtractedTerm) -> str:
        """
        Create an entry for an unmatched term with suggested review points.
        
        Args:
            term: The unmatched term.
            
        Returns:
            String describing the unmatched term and suggested actions.
        """
        # Get expected clause categories for this term
        expected_categories = self._rule_matcher.get_expected_clause_categories(
            term.category
        )
        
        category_names = [cat.value for cat in expected_categories]
        
        suggestion = (
            f"Term '{term.title}' (ID: {term.id}, Category: {term.category.value}) "
            f"could not be matched. Suggested review: Look for clauses in categories "
            f"{', '.join(category_names) if category_names else 'any'}. "
            f"Source: {term.source_section_id}"
        )
        
        return suggestion

    def _apply_config(self, config: dict) -> None:
        """
        Apply configuration settings.
        
        Args:
            config: Configuration dictionary.
        """
        if "confidence_threshold" in config:
            self.set_confidence_threshold(config["confidence_threshold"])
        
        if "semantic_threshold" in config:
            self._semantic_matcher.set_similarity_threshold(
                config["semantic_threshold"]
            )

        # Optional per-category action policies and review thresholds.
        if "action_policies_by_category" in config:
            self._action_policies = dict(config["action_policies_by_category"])

        if "review_thresholds_by_category" in config:
            self._review_thresholds_by_category = {
                str(k): float(v)
                for k, v in config["review_thresholds_by_category"].items()
            }

    def get_confidence_threshold(self) -> float:
        """
        Get the confidence threshold for human review flagging.
        
        Returns:
            The current confidence threshold (0.0 to 1.0).
        """
        return self._confidence_threshold

    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set the confidence threshold for human review flagging.
        
        Args:
            threshold: The new confidence threshold (0.0 to 1.0).
            
        Raises:
            ValueError: If threshold is not between 0.0 and 1.0.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._confidence_threshold = threshold

    def get_match_candidates(
        self,
        term: ExtractedTerm,
        clauses: List[AnalyzedClause],
        max_candidates: int = 5
    ) -> List[Tuple[AnalyzedClause, MatchMethod, float]]:
        """
        Get all match candidates for a term, ranked by confidence.
        
        Useful for presenting multiple options to users for review.
        
        Args:
            term: The extracted term.
            clauses: List of analyzed clauses.
            max_candidates: Maximum number of candidates to return.
            
        Returns:
            List of tuples (clause, method, confidence) sorted by confidence.
        """
        candidates: List[Tuple[AnalyzedClause, MatchMethod, float]] = []
        
        # Get rule-based matches
        rule_matches = self._rule_matcher.match(term, clauses)
        candidates.extend(rule_matches)
        
        # Get semantic matches
        semantic_matches = self._semantic_matcher.match(term, clauses)
        
        # Add semantic matches that aren't already in candidates
        existing_clause_ids = {c[0].id for c in candidates}
        for clause, method, confidence in semantic_matches:
            if clause.id not in existing_clause_ids:
                candidates.append((clause, method, confidence))
        
        # Sort by confidence and limit
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[:max_candidates]
