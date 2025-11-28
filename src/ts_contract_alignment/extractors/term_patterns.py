"""Term pattern matching for TS extraction.

This module provides pattern-based term identification for extracting
business terms from Term Sheet documents.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models.enums import TermCategory


@dataclass
class TermPattern:
    """Pattern definition for term extraction."""
    category: TermCategory
    keywords_en: List[str]
    keywords_zh: List[str]
    value_patterns: List[str]  # Regex patterns for extracting values
    priority: int = 0  # Higher priority patterns are checked first


class TermPatternMatcher:
    """
    Pattern-based term matcher for TS documents.
    
    Uses keyword matching and regex patterns to identify and categorize
    business terms in Term Sheet documents.
    """

    def __init__(self):
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> List[TermPattern]:
        """Build the list of term patterns for extraction."""
        return [
            # Investment Amount patterns
            TermPattern(
                category=TermCategory.INVESTMENT_AMOUNT,
                keywords_en=[
                    "investment amount", "total investment", "aggregate investment",
                    "funding amount", "capital contribution", "subscription amount",
                    "purchase price", "investment size"
                ],
                keywords_zh=[
                    "投资金额", "投资总额", "认购金额", "出资金额", "投资额",
                    "融资金额", "认购总额", "投资款"
                ],
                value_patterns=[
                    r"(?:USD|US\$|\$|RMB|CNY|¥|€|EUR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|万|亿))?",
                    r"[\d,]+(?:\.\d+)?\s*(?:USD|US\$|RMB|CNY|万|亿|million|billion)",
                ],
                priority=10
            ),
            # Valuation patterns
            TermPattern(
                category=TermCategory.VALUATION,
                keywords_en=[
                    "pre-money valuation", "post-money valuation", "valuation",
                    "company valuation", "enterprise value", "valuation cap"
                ],
                keywords_zh=[
                    "投前估值", "投后估值", "估值", "公司估值", "企业价值"
                ],
                value_patterns=[
                    r"(?:USD|US\$|\$|RMB|CNY|¥|€|EUR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|万|亿))?",
                    r"[\d,]+(?:\.\d+)?\s*(?:USD|US\$|RMB|CNY|万|亿|million|billion)",
                ],
                priority=9
            ),
            # Pricing patterns
            TermPattern(
                category=TermCategory.PRICING,
                keywords_en=[
                    "price per share", "share price", "conversion price",
                    "issue price", "subscription price", "purchase price per share"
                ],
                keywords_zh=[
                    "每股价格", "股价", "转换价格", "发行价格", "认购价格"
                ],
                value_patterns=[
                    r"(?:USD|US\$|\$|RMB|CNY|¥)\s*[\d,]+(?:\.\d+)?(?:\s*per\s*share)?",
                    r"[\d,]+(?:\.\d+)?\s*(?:元|美元)(?:/股)?",
                ],
                priority=8
            ),
            # Closing Conditions patterns
            TermPattern(
                category=TermCategory.CLOSING_CONDITIONS,
                keywords_en=[
                    "closing conditions", "conditions to closing", "closing",
                    "completion conditions", "conditions for completion"
                ],
                keywords_zh=[
                    "交割条件", "完成条件", "交割", "成交条件"
                ],
                value_patterns=[],
                priority=7
            ),
            # Conditions Precedent patterns
            TermPattern(
                category=TermCategory.CONDITIONS_PRECEDENT,
                keywords_en=[
                    "conditions precedent", "cp", "preconditions",
                    "prior conditions", "prerequisite conditions"
                ],
                keywords_zh=[
                    "先决条件", "前提条件", "先行条件"
                ],
                value_patterns=[],
                priority=7
            ),
            # Board Seats patterns
            TermPattern(
                category=TermCategory.BOARD_SEATS,
                keywords_en=[
                    "board seat", "board seats", "board composition",
                    "board of directors", "director appointment", "board representation"
                ],
                keywords_zh=[
                    "董事席位", "董事会席位", "董事会组成", "董事任命", "董事会"
                ],
                value_patterns=[
                    r"\d+\s*(?:seat|seats|director|directors|名|位)",
                ],
                priority=6
            ),
            # Voting Rights patterns
            TermPattern(
                category=TermCategory.VOTING_RIGHTS,
                keywords_en=[
                    "voting rights", "voting power", "vote", "voting",
                    "shareholder voting", "protective provisions"
                ],
                keywords_zh=[
                    "投票权", "表决权", "投票", "股东投票", "保护性条款"
                ],
                value_patterns=[
                    r"\d+(?:\.\d+)?%",
                ],
                priority=6
            ),
            # Liquidation Preference patterns
            TermPattern(
                category=TermCategory.LIQUIDATION_PREFERENCE,
                keywords_en=[
                    "liquidation preference", "liquidation", "preference",
                    "liquidation rights", "distribution preference",
                    "participating preferred", "non-participating"
                ],
                keywords_zh=[
                    "清算优先权", "清算", "优先权", "清算分配", "优先清算权"
                ],
                value_patterns=[
                    r"\d+(?:\.\d+)?[xX]",
                    r"\d+(?:\.\d+)?%",
                ],
                priority=5
            ),
            # Anti-Dilution patterns
            TermPattern(
                category=TermCategory.ANTI_DILUTION,
                keywords_en=[
                    "anti-dilution", "antidilution", "dilution protection",
                    "weighted average", "full ratchet", "broad-based"
                ],
                keywords_zh=[
                    "反稀释", "反摊薄", "稀释保护", "加权平均", "完全棘轮"
                ],
                value_patterns=[],
                priority=5
            ),
            # Information Rights patterns
            TermPattern(
                category=TermCategory.INFORMATION_RIGHTS,
                keywords_en=[
                    "information rights", "reporting", "financial statements",
                    "inspection rights", "audit rights", "access to information"
                ],
                keywords_zh=[
                    "信息权", "知情权", "财务报表", "检查权", "审计权", "信息获取"
                ],
                value_patterns=[],
                priority=4
            ),
        ]

    def match_category(self, text: str) -> Tuple[Optional[TermCategory], float]:
        """
        Match text to a term category.
        
        Args:
            text: The text to analyze.
            
        Returns:
            Tuple of (matched category, confidence score).
            Returns (None, 0.0) if no match found.
        """
        text_lower = text.lower()
        best_match: Optional[TermCategory] = None
        best_score = 0.0
        
        for pattern in sorted(self._patterns, key=lambda p: -p.priority):
            score = self._calculate_match_score(text_lower, text, pattern)
            if score > best_score:
                best_score = score
                best_match = pattern.category
        
        return (best_match, best_score) if best_score > 0.3 else (None, 0.0)

    def _calculate_match_score(
        self, text_lower: str, text_original: str, pattern: TermPattern
    ) -> float:
        """Calculate match score for a pattern against text."""
        score = 0.0
        matches = 0
        
        # Check English keywords
        for keyword in pattern.keywords_en:
            if keyword.lower() in text_lower:
                matches += 1
                score += 0.4
        
        # Check Chinese keywords
        for keyword in pattern.keywords_zh:
            if keyword in text_original:
                matches += 1
                score += 0.4
        
        # Check value patterns
        for value_pattern in pattern.value_patterns:
            if re.search(value_pattern, text_original, re.IGNORECASE):
                score += 0.2
        
        # Normalize score
        if matches > 0:
            score = min(1.0, score)
        
        return score

    def extract_value(
        self, text: str, category: TermCategory
    ) -> Optional[str]:
        """
        Extract the value from text for a given category.
        
        Args:
            text: The text to extract value from.
            category: The term category to extract value for.
            
        Returns:
            Extracted value string, or None if not found.
        """
        pattern = next(
            (p for p in self._patterns if p.category == category), None
        )
        if not pattern or not pattern.value_patterns:
            return None
        
        for value_pattern in pattern.value_patterns:
            match = re.search(value_pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        return None

    def get_category_keywords(self, category: TermCategory) -> List[str]:
        """Get all keywords for a category."""
        pattern = next(
            (p for p in self._patterns if p.category == category), None
        )
        if not pattern:
            return []
        return pattern.keywords_en + pattern.keywords_zh
