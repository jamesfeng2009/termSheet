"""Enumerations for the TS Contract Alignment System."""

from enum import Enum


class DocumentType(Enum):
    """Document format types supported by the system."""
    WORD = "docx"
    PDF = "pdf"


class HeadingLevel(Enum):
    """Heading hierarchy levels in documents."""
    TITLE = 0
    CHAPTER = 1
    SECTION = 2
    SUBSECTION = 3
    PARAGRAPH = 4


class TermCategory(Enum):
    """Categories of terms extracted from Term Sheets."""
    INVESTMENT_AMOUNT = "investment_amount"
    VALUATION = "valuation"
    PRICING = "pricing"
    CLOSING_CONDITIONS = "closing_conditions"
    CONDITIONS_PRECEDENT = "conditions_precedent"
    BOARD_SEATS = "board_seats"
    VOTING_RIGHTS = "voting_rights"
    LIQUIDATION_PREFERENCE = "liquidation_preference"
    ANTI_DILUTION = "anti_dilution"
    INFORMATION_RIGHTS = "information_rights"
    OTHER = "other"


class ClauseCategory(Enum):
    """Categories of clauses in contract templates."""
    DEFINITIONS = "definitions"
    INVESTMENT_TERMS = "investment_terms"
    GOVERNANCE = "governance"
    LIQUIDATION = "liquidation"
    ANTI_DILUTION = "anti_dilution"
    INFORMATION_RIGHTS = "information_rights"
    REPRESENTATIONS = "representations"
    COVENANTS = "covenants"
    CLOSING = "closing"
    MISCELLANEOUS = "miscellaneous"


class ActionType(Enum):
    """Types of actions for alignment operations."""
    INSERT = "insert"
    OVERRIDE = "override"
    SKIP = "skip"


class MatchMethod(Enum):
    """Methods used for matching TS terms to contract clauses."""
    RULE_TITLE = "rule_title"
    RULE_NUMBER = "rule_number"
    RULE_KEYWORD = "rule_keyword"
    SEMANTIC = "semantic"
    TEMPLATE_MEMORY = "template_memory"
