"""Rule-based matcher for TS-to-template alignment.

This module implements rule-based matching using clause titles,
section numbers, and keywords to align TS terms with contract clauses.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..models.enums import ClauseCategory, MatchMethod, TermCategory
from ..models.extraction import ExtractedTerm
from ..models.template import AnalyzedClause


@dataclass
class MatchRule:
    """Rule definition for matching TS terms to contract clauses."""
    name: str
    term_categories: List[TermCategory]
    clause_categories: List[ClauseCategory]
    keywords_en: List[str]
    keywords_zh: List[str]
    priority: int  # Higher priority rules are applied first
    base_confidence: float  # Base confidence score for this rule


class RuleBasedMatcher:
    """
    Rule-based matcher for TS-to-template alignment.
    
    Uses predefined rules based on titles, section numbers, and keywords
    to match Term Sheet terms to contract template clauses.
    """

    def __init__(self):
        self._rules = self._build_rules()
        self._category_mapping = self._build_category_mapping()

    def _build_rules(self) -> List[MatchRule]:
        """Build the list of matching rules."""
        return [
            # Investment Amount -> Investment Terms
            MatchRule(
                name="investment_amount_to_terms",
                term_categories=[TermCategory.INVESTMENT_AMOUNT],
                clause_categories=[ClauseCategory.INVESTMENT_TERMS],
                keywords_en=[
                    "investment", "amount", "subscription", "purchase",
                    "capital", "funding", "consideration"
                ],
                keywords_zh=["投资", "金额", "认购", "出资", "对价"],
                priority=10,
                base_confidence=0.85
            ),
            # Valuation -> Investment Terms
            MatchRule(
                name="valuation_to_terms",
                term_categories=[TermCategory.VALUATION],
                clause_categories=[ClauseCategory.INVESTMENT_TERMS],
                keywords_en=[
                    "valuation", "pre-money", "post-money", "enterprise value"
                ],
                keywords_zh=["估值", "投前", "投后", "企业价值"],
                priority=10,
                base_confidence=0.85
            ),
            # Pricing -> Investment Terms
            MatchRule(
                name="pricing_to_terms",
                term_categories=[TermCategory.PRICING],
                clause_categories=[ClauseCategory.INVESTMENT_TERMS],
                keywords_en=[
                    "price", "share price", "conversion price", "issue price"
                ],
                keywords_zh=["价格", "股价", "转换价格", "发行价格"],
                priority=10,
                base_confidence=0.85
            ),
            # Board Seats -> Governance
            MatchRule(
                name="board_seats_to_governance",
                term_categories=[TermCategory.BOARD_SEATS],
                clause_categories=[ClauseCategory.GOVERNANCE],
                keywords_en=[
                    "board", "director", "seat", "composition", "appointment"
                ],
                keywords_zh=["董事", "席位", "任命", "组成"],
                priority=9,
                base_confidence=0.85
            ),
            # Voting Rights -> Governance
            MatchRule(
                name="voting_rights_to_governance",
                term_categories=[TermCategory.VOTING_RIGHTS],
                clause_categories=[ClauseCategory.GOVERNANCE],
                keywords_en=[
                    "voting", "vote", "rights", "shareholder", "protective"
                ],
                keywords_zh=["投票", "表决", "权利", "股东", "保护"],
                priority=9,
                base_confidence=0.85
            ),
            # Liquidation Preference -> Liquidation
            MatchRule(
                name="liquidation_pref_to_liquidation",
                term_categories=[TermCategory.LIQUIDATION_PREFERENCE],
                clause_categories=[ClauseCategory.LIQUIDATION],
                keywords_en=[
                    "liquidation", "preference", "distribution", "proceeds"
                ],
                keywords_zh=["清算", "优先", "分配", "收益"],
                priority=9,
                base_confidence=0.90
            ),
            # Anti-Dilution -> Anti-Dilution
            MatchRule(
                name="anti_dilution_to_anti_dilution",
                term_categories=[TermCategory.ANTI_DILUTION],
                clause_categories=[ClauseCategory.ANTI_DILUTION],
                keywords_en=[
                    "anti-dilution", "dilution", "adjustment", "ratchet", "weighted"
                ],
                keywords_zh=["反稀释", "稀释", "调整", "棘轮", "加权"],
                priority=9,
                base_confidence=0.90
            ),
            # Information Rights -> Information Rights
            MatchRule(
                name="info_rights_to_info_rights",
                term_categories=[TermCategory.INFORMATION_RIGHTS],
                clause_categories=[ClauseCategory.INFORMATION_RIGHTS],
                keywords_en=[
                    "information", "reporting", "financial", "audit", "inspection"
                ],
                keywords_zh=["信息", "报告", "财务", "审计", "检查"],
                priority=8,
                base_confidence=0.85
            ),
            # Closing Conditions -> Closing
            MatchRule(
                name="closing_conditions_to_closing",
                term_categories=[TermCategory.CLOSING_CONDITIONS],
                clause_categories=[ClauseCategory.CLOSING],
                keywords_en=[
                    "closing", "completion", "conditions", "deliverables"
                ],
                keywords_zh=["交割", "完成", "条件", "交付"],
                priority=8,
                base_confidence=0.85
            ),
            # Conditions Precedent -> Closing
            MatchRule(
                name="conditions_precedent_to_closing",
                term_categories=[TermCategory.CONDITIONS_PRECEDENT],
                clause_categories=[ClauseCategory.CLOSING],
                keywords_en=[
                    "conditions precedent", "preconditions", "prior conditions"
                ],
                keywords_zh=["先决条件", "前提条件"],
                priority=8,
                base_confidence=0.85
            ),
        ]

    def _build_category_mapping(self) -> Dict[TermCategory, List[ClauseCategory]]:
        """Build direct mapping from term categories to clause categories."""
        return {
            TermCategory.INVESTMENT_AMOUNT: [ClauseCategory.INVESTMENT_TERMS],
            TermCategory.VALUATION: [ClauseCategory.INVESTMENT_TERMS],
            TermCategory.PRICING: [ClauseCategory.INVESTMENT_TERMS],
            TermCategory.CLOSING_CONDITIONS: [ClauseCategory.CLOSING],
            TermCategory.CONDITIONS_PRECEDENT: [ClauseCategory.CLOSING],
            TermCategory.BOARD_SEATS: [ClauseCategory.GOVERNANCE],
            TermCategory.VOTING_RIGHTS: [ClauseCategory.GOVERNANCE],
            TermCategory.LIQUIDATION_PREFERENCE: [ClauseCategory.LIQUIDATION],
            TermCategory.ANTI_DILUTION: [ClauseCategory.ANTI_DILUTION],
            TermCategory.INFORMATION_RIGHTS: [ClauseCategory.INFORMATION_RIGHTS],
            TermCategory.OTHER: [ClauseCategory.MISCELLANEOUS],
        }


    def match(
        self,
        term: ExtractedTerm,
        clauses: List[AnalyzedClause]
    ) -> List[Tuple[AnalyzedClause, MatchMethod, float]]:
        """
        Find matching clauses for a term using rule-based matching.
        
        Args:
            term: The extracted term to match.
            clauses: List of analyzed clauses to match against.
            
        Returns:
            List of tuples (clause, match_method, confidence) sorted by confidence.
        """
        candidates: List[Tuple[AnalyzedClause, MatchMethod, float]] = []
        
        for clause in clauses:
            match_result = self._match_term_to_clause(term, clause)
            if match_result:
                method, confidence = match_result
                candidates.append((clause, method, confidence))
        
        # Sort by confidence descending
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates

    def _match_term_to_clause(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> Optional[Tuple[MatchMethod, float]]:
        """
        Try to match a term to a clause using all available rules.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            Tuple of (match_method, confidence) if matched, None otherwise.
        """
        # Try title matching first (highest priority)
        title_confidence = self._match_by_title(term, clause)
        if title_confidence > 0.5:
            return (MatchMethod.RULE_TITLE, title_confidence)
        
        # Try section number matching
        number_confidence = self._match_by_number(term, clause)
        if number_confidence > 0.5:
            return (MatchMethod.RULE_NUMBER, number_confidence)
        
        # Try keyword matching
        keyword_confidence = self._match_by_keyword(term, clause)
        if keyword_confidence > 0.5:
            return (MatchMethod.RULE_KEYWORD, keyword_confidence)
        
        # Try category-based matching
        category_confidence = self._match_by_category(term, clause)
        if category_confidence > 0.4:
            return (MatchMethod.RULE_KEYWORD, category_confidence)
        
        return None

    def _match_by_title(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> float:
        """
        Match term to clause by comparing titles.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            Confidence score (0.0 to 1.0).
        """
        if not term.title or not clause.title:
            return 0.0
        
        term_title_lower = term.title.lower()
        clause_title_lower = clause.title.lower()
        
        # Exact match
        if term_title_lower == clause_title_lower:
            return 0.95
        
        # Check if term title is contained in clause title or vice versa
        if term_title_lower in clause_title_lower:
            return 0.85
        if clause_title_lower in term_title_lower:
            return 0.80
        
        # Check for significant word overlap
        term_words = set(re.findall(r'\w+', term_title_lower))
        clause_words = set(re.findall(r'\w+', clause_title_lower))
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'for', 'on', 'with'}
        term_words -= stop_words
        clause_words -= stop_words
        
        if not term_words or not clause_words:
            return 0.0
        
        overlap = len(term_words & clause_words)
        union = len(term_words | clause_words)
        
        if union > 0:
            jaccard = overlap / union
            if jaccard > 0.5:
                return 0.6 + (jaccard * 0.3)
        
        return 0.0

    def _match_by_number(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> float:
        """
        Match term to clause by section numbers.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            Confidence score (0.0 to 1.0).
        """
        # Extract section numbers from term's raw text
        term_numbers = self._extract_section_numbers(term.raw_text)
        
        # Get clause section ID which may contain numbers
        clause_numbers = self._extract_section_numbers(clause.section_id)
        
        if not term_numbers or not clause_numbers:
            return 0.0
        
        # Check for matching section numbers
        for term_num in term_numbers:
            for clause_num in clause_numbers:
                if term_num == clause_num:
                    return 0.75
                # Check if one is a prefix of the other (e.g., "1" matches "1.1")
                if term_num.startswith(clause_num) or clause_num.startswith(term_num):
                    return 0.65
        
        return 0.0

    def _extract_section_numbers(self, text: str) -> List[str]:
        """Extract section numbers from text."""
        # Match patterns like "1", "1.1", "1.1.1", "第一条", "Article 1"
        patterns = [
            r'\b(\d+(?:\.\d+)*)\b',  # 1, 1.1, 1.1.1
            r'(?:Article|Section|Clause)\s*(\d+)',  # Article 1
            r'第([一二三四五六七八九十百]+)条',  # 第一条
        ]
        
        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            numbers.extend(matches)
        
        return numbers


    def _match_by_keyword(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> float:
        """
        Match term to clause by keyword overlap.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            Confidence score (0.0 to 1.0).
        """
        # Find applicable rules for this term category
        applicable_rules = [
            rule for rule in self._rules
            if term.category in rule.term_categories
        ]
        
        if not applicable_rules:
            return 0.0
        
        best_confidence = 0.0
        term_text_lower = term.raw_text.lower()
        clause_text_lower = clause.full_text.lower()
        
        for rule in applicable_rules:
            # Check if clause category matches rule's expected categories
            if clause.category not in rule.clause_categories:
                continue
            
            # Count keyword matches
            keyword_matches = 0
            total_keywords = len(rule.keywords_en) + len(rule.keywords_zh)
            
            for keyword in rule.keywords_en:
                if keyword.lower() in clause_text_lower:
                    keyword_matches += 1
            
            for keyword in rule.keywords_zh:
                if keyword in clause.full_text:
                    keyword_matches += 1
            
            if total_keywords > 0 and keyword_matches > 0:
                keyword_ratio = keyword_matches / total_keywords
                confidence = rule.base_confidence * (0.5 + 0.5 * keyword_ratio)
                best_confidence = max(best_confidence, confidence)
        
        return best_confidence

    def _match_by_category(
        self,
        term: ExtractedTerm,
        clause: AnalyzedClause
    ) -> float:
        """
        Match term to clause by category mapping.
        
        Args:
            term: The extracted term.
            clause: The analyzed clause.
            
        Returns:
            Confidence score (0.0 to 1.0).
        """
        expected_categories = self._category_mapping.get(term.category, [])
        
        if clause.category in expected_categories:
            # Base confidence for category match
            base_confidence = 0.6
            
            # Boost confidence if there's keyword overlap
            term_text_lower = term.raw_text.lower()
            clause_keywords_lower = [k.lower() for k in clause.keywords]
            
            keyword_boost = 0.0
            for keyword in clause_keywords_lower:
                if keyword in term_text_lower:
                    keyword_boost += 0.05
            
            return min(0.8, base_confidence + keyword_boost)
        
        return 0.0

    def get_rules_for_category(self, category: TermCategory) -> List[MatchRule]:
        """Get all rules applicable to a term category."""
        return [
            rule for rule in self._rules
            if category in rule.term_categories
        ]

    def get_expected_clause_categories(
        self, term_category: TermCategory
    ) -> List[ClauseCategory]:
        """Get expected clause categories for a term category."""
        return self._category_mapping.get(term_category, [])
