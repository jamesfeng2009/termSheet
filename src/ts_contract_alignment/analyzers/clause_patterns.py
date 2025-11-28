"""Clause pattern matching for contract template analysis.

This module provides pattern-based clause classification for analyzing
contract templates and identifying semantic categories.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models.enums import ClauseCategory


@dataclass
class ClausePattern:
    """Pattern definition for clause classification."""
    category: ClauseCategory
    keywords_en: List[str]
    keywords_zh: List[str]
    title_patterns: List[str]  # Regex patterns for matching clause titles
    priority: int = 0  # Higher priority patterns are checked first


class ClausePatternMatcher:
    """
    Pattern-based clause classifier for contract templates.
    
    Uses keyword matching and regex patterns to classify contract
    clauses into semantic categories.
    """

    def __init__(self):
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> List[ClausePattern]:
        """Build the list of clause patterns for classification."""
        return [
            # Definitions patterns
            ClausePattern(
                category=ClauseCategory.DEFINITIONS,
                keywords_en=[
                    "definition", "definitions", "defined terms", "interpretation",
                    "glossary", "meaning", "shall mean", "means"
                ],
                keywords_zh=[
                    "定义", "释义", "术语", "解释", "含义", "指"
                ],
                title_patterns=[
                    r"(?i)^definitions?$",
                    r"(?i)^defined\s+terms?$",
                    r"(?i)^interpretation$",
                    r"^释义$", r"^定义$"
                ],
                priority=10
            ),
            # Investment Terms patterns
            ClausePattern(
                category=ClauseCategory.INVESTMENT_TERMS,
                keywords_en=[
                    "investment", "subscription", "purchase", "shares", "equity",
                    "capital", "funding", "securities", "stock", "consideration",
                    "price per share", "valuation", "investment amount"
                ],
                keywords_zh=[
                    "投资", "认购", "购买", "股份", "股权", "出资", "融资",
                    "证券", "股票", "对价", "每股价格", "估值", "投资金额"
                ],
                title_patterns=[
                    r"(?i)investment",
                    r"(?i)subscription",
                    r"(?i)purchase\s+of\s+shares",
                    r"投资", r"认购", r"出资"
                ],
                priority=9
            ),

            # Governance patterns
            ClausePattern(
                category=ClauseCategory.GOVERNANCE,
                keywords_en=[
                    "board", "director", "directors", "governance", "voting",
                    "shareholder", "meeting", "quorum", "resolution", "consent",
                    "board seat", "board composition", "voting rights"
                ],
                keywords_zh=[
                    "董事", "董事会", "治理", "投票", "股东", "会议",
                    "法定人数", "决议", "同意", "董事席位", "表决权"
                ],
                title_patterns=[
                    r"(?i)board",
                    r"(?i)governance",
                    r"(?i)director",
                    r"(?i)voting",
                    r"董事", r"治理", r"投票"
                ],
                priority=8
            ),
            # Liquidation patterns
            ClausePattern(
                category=ClauseCategory.LIQUIDATION,
                keywords_en=[
                    "liquidation", "dissolution", "winding up", "preference",
                    "distribution", "proceeds", "liquidation preference",
                    "participating", "non-participating"
                ],
                keywords_zh=[
                    "清算", "解散", "清盘", "优先权", "分配", "收益",
                    "清算优先权", "参与分配"
                ],
                title_patterns=[
                    r"(?i)liquidation",
                    r"(?i)dissolution",
                    r"(?i)winding\s+up",
                    r"清算", r"解散"
                ],
                priority=8
            ),
            # Anti-Dilution patterns
            ClausePattern(
                category=ClauseCategory.ANTI_DILUTION,
                keywords_en=[
                    "anti-dilution", "antidilution", "dilution", "adjustment",
                    "weighted average", "full ratchet", "broad-based",
                    "conversion price adjustment"
                ],
                keywords_zh=[
                    "反稀释", "反摊薄", "稀释", "调整", "加权平均",
                    "完全棘轮", "转换价格调整"
                ],
                title_patterns=[
                    r"(?i)anti-?dilution",
                    r"(?i)dilution\s+protection",
                    r"反稀释", r"反摊薄"
                ],
                priority=7
            ),
            # Information Rights patterns
            ClausePattern(
                category=ClauseCategory.INFORMATION_RIGHTS,
                keywords_en=[
                    "information", "reporting", "financial statements", "audit",
                    "inspection", "access", "records", "books", "accounts",
                    "quarterly", "annual", "budget"
                ],
                keywords_zh=[
                    "信息", "报告", "财务报表", "审计", "检查", "访问",
                    "记录", "账簿", "账目", "季度", "年度", "预算", "知情权"
                ],
                title_patterns=[
                    r"(?i)information\s+rights?",
                    r"(?i)reporting",
                    r"(?i)financial\s+statements?",
                    r"信息权", r"知情权", r"报告"
                ],
                priority=7
            ),
            # Representations patterns
            ClausePattern(
                category=ClauseCategory.REPRESENTATIONS,
                keywords_en=[
                    "representation", "representations", "warranty", "warranties",
                    "represent", "warrant", "covenants", "undertaking"
                ],
                keywords_zh=[
                    "陈述", "保证", "声明", "担保", "承诺"
                ],
                title_patterns=[
                    r"(?i)representations?\s*(and|&)?\s*warrant",
                    r"(?i)representations?$",
                    r"(?i)warrant",
                    r"陈述", r"保证", r"声明"
                ],
                priority=6
            ),
            # Covenants patterns
            ClausePattern(
                category=ClauseCategory.COVENANTS,
                keywords_en=[
                    "covenant", "covenants", "undertaking", "obligation",
                    "agreement", "promise", "commitment", "shall", "must"
                ],
                keywords_zh=[
                    "承诺", "义务", "约定", "协议", "保证", "必须"
                ],
                title_patterns=[
                    r"(?i)covenants?$",
                    r"(?i)undertakings?$",
                    r"(?i)obligations?$",
                    r"承诺", r"义务"
                ],
                priority=5
            ),
            # Closing patterns
            ClausePattern(
                category=ClauseCategory.CLOSING,
                keywords_en=[
                    "closing", "completion", "conditions precedent", "cp",
                    "conditions", "closing conditions", "deliverables",
                    "closing date", "completion date"
                ],
                keywords_zh=[
                    "交割", "完成", "先决条件", "条件", "交割条件",
                    "交付物", "交割日", "完成日"
                ],
                title_patterns=[
                    r"(?i)closing",
                    r"(?i)completion",
                    r"(?i)conditions?\s+precedent",
                    r"交割", r"完成", r"先决条件"
                ],
                priority=6
            ),
            # Miscellaneous patterns
            ClausePattern(
                category=ClauseCategory.MISCELLANEOUS,
                keywords_en=[
                    "miscellaneous", "general", "notices", "governing law",
                    "jurisdiction", "amendment", "waiver", "severability",
                    "entire agreement", "counterparts", "confidentiality"
                ],
                keywords_zh=[
                    "杂项", "一般条款", "通知", "适用法律", "管辖",
                    "修订", "弃权", "可分割性", "完整协议", "副本", "保密"
                ],
                title_patterns=[
                    r"(?i)miscellaneous",
                    r"(?i)general\s+provisions?",
                    r"(?i)governing\s+law",
                    r"(?i)notices?$",
                    r"杂项", r"一般条款", r"通知"
                ],
                priority=3
            ),
        ]

    def classify(self, text: str, title: Optional[str] = None) -> Tuple[ClauseCategory, float]:
        """
        Classify text into a clause category.
        
        Args:
            text: The clause text to analyze.
            title: Optional clause title for better matching.
            
        Returns:
            Tuple of (matched category, confidence score).
            Returns (MISCELLANEOUS, 0.3) if no strong match found.
        """
        text_lower = text.lower()
        best_match: ClauseCategory = ClauseCategory.MISCELLANEOUS
        best_score = 0.0
        
        for pattern in sorted(self._patterns, key=lambda p: -p.priority):
            score = self._calculate_match_score(text_lower, text, title, pattern)
            if score > best_score:
                best_score = score
                best_match = pattern.category
        
        # Return MISCELLANEOUS with low confidence if no good match
        if best_score < 0.3:
            return (ClauseCategory.MISCELLANEOUS, 0.3)
        
        return (best_match, best_score)

    def _calculate_match_score(
        self, 
        text_lower: str, 
        text_original: str, 
        title: Optional[str],
        pattern: ClausePattern
    ) -> float:
        """Calculate match score for a pattern against text."""
        score = 0.0
        matches = 0
        
        # Check title patterns first (highest weight)
        if title:
            for title_pattern in pattern.title_patterns:
                if re.search(title_pattern, title):
                    score += 0.5
                    matches += 1
                    break  # Only count title match once
        
        # Check English keywords
        for keyword in pattern.keywords_en:
            if keyword.lower() in text_lower:
                matches += 1
                score += 0.15
        
        # Check Chinese keywords
        for keyword in pattern.keywords_zh:
            if keyword in text_original:
                matches += 1
                score += 0.15
        
        # Normalize score
        if matches > 0:
            score = min(1.0, score)
        
        return score

    def get_category_keywords(self, category: ClauseCategory) -> List[str]:
        """Get all keywords for a category."""
        pattern = next(
            (p for p in self._patterns if p.category == category), None
        )
        if not pattern:
            return []
        return pattern.keywords_en + pattern.keywords_zh

    def extract_keywords(self, text: str, category: ClauseCategory) -> List[str]:
        """
        Extract matching keywords from text for a given category.
        
        Args:
            text: The text to extract keywords from.
            category: The clause category to match keywords for.
            
        Returns:
            List of keywords found in the text.
        """
        pattern = next(
            (p for p in self._patterns if p.category == category), None
        )
        if not pattern:
            return []
        
        found_keywords = []
        text_lower = text.lower()
        
        for keyword in pattern.keywords_en:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        for keyword in pattern.keywords_zh:
            if keyword in text:
                found_keywords.append(keyword)
        
        return found_keywords
