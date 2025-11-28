"""Alignment engine interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models.alignment import AlignmentResult
from ..models.extraction import TSExtractionResult
from ..models.template import TemplateAnalysisResult


class IAlignmentEngine(ABC):
    """
    Abstract interface for TS-to-template alignment.
    
    Implementations of this interface handle matching of Term Sheet
    terms to contract template clauses using rule-based and semantic methods.
    """

    @abstractmethod
    def align(
        self,
        ts_result: TSExtractionResult,
        template_result: TemplateAnalysisResult,
        config: Optional[dict] = None,
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
        pass

    @abstractmethod
    def get_confidence_threshold(self) -> float:
        """
        Get the confidence threshold for human review flagging.
        
        Returns:
            The current confidence threshold (0.0 to 1.0).
        """
        pass

    @abstractmethod
    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set the confidence threshold for human review flagging.
        
        Args:
            threshold: The new confidence threshold (0.0 to 1.0).
            
        Raises:
            ValueError: If threshold is not between 0.0 and 1.0.
        """
        pass
