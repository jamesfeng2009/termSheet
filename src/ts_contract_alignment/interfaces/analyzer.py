"""Template analyzer interface for the TS Contract Alignment System."""

from abc import ABC, abstractmethod

from ..models.document import ParsedDocument
from ..models.template import TemplateAnalysisResult


class ITemplateAnalyzer(ABC):
    """
    Abstract interface for contract template analysis.
    
    Implementations of this interface handle analysis of contract
    templates to identify clauses, fillable segments, and semantic categories.
    """

    @abstractmethod
    def analyze(self, parsed_doc: ParsedDocument) -> TemplateAnalysisResult:
        """
        Analyze a parsed contract template document.
        
        Args:
            parsed_doc: The parsed contract template document.
            
        Returns:
            TemplateAnalysisResult containing analyzed clauses and structure.
        """
        pass

    @abstractmethod
    def serialize(self, result: TemplateAnalysisResult) -> str:
        """
        Serialize a TemplateAnalysisResult to JSON string.
        
        Args:
            result: The analysis result to serialize.
            
        Returns:
            JSON string representation of the analysis result.
        """
        pass

    @abstractmethod
    def deserialize(self, json_str: str) -> TemplateAnalysisResult:
        """
        Deserialize a JSON string to a TemplateAnalysisResult.
        
        Args:
            json_str: JSON string to deserialize.
            
        Returns:
            TemplateAnalysisResult reconstructed from the JSON.
            
        Raises:
            ValueError: If the JSON is invalid or malformed.
        """
        pass
