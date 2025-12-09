"""Hybrid TS extractor with multi-layer extraction pipeline.

This module provides a composite Term Sheet extractor that combines
rule-based extraction, optional semantic refinement, and optional
LLM-based fallback extraction, while keeping compatibility with the
existing ITSExtractor interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models.document import ParsedDocument
from ..models.extraction import TSExtractionResult
from ..interfaces.extractor import ITSExtractor
from .ts_extractor import TSExtractor


class ISemanticRefiner(ABC):
    """Interface for semantic/ML-based refinement of TS extraction.

    Implementations can use embeddings, traditional ML models, or other
    semantic techniques to improve upon the rule-based extraction
    results produced by TSExtractor.
    """

    @abstractmethod
    def refine(
        self,
        parsed_doc: ParsedDocument,
        rule_result: TSExtractionResult,
    ) -> TSExtractionResult:
        """Refine rule-based extraction results.

        Args:
            parsed_doc: The parsed Term Sheet document.
            rule_result: Extraction result produced by the rule-based extractor.

        Returns:
            A new TSExtractionResult that may add, modify, or annotate terms
            from the rule_result.
        """
        raise NotImplementedError


class ILLMExtractor(ABC):
    """Interface for LLM-based fallback extraction.

    Implementations can call external large language models to extract
    additional terms from sections that were not confidently handled by
    the rule-based and semantic layers.
    """

    @abstractmethod
    def extract_missing_terms(
        self,
        parsed_doc: ParsedDocument,
        current_result: TSExtractionResult,
    ) -> TSExtractionResult:
        """Extract additional terms using an LLM.

        Args:
            parsed_doc: The parsed Term Sheet document.
            current_result: Current extraction result after rule-based and
                optional semantic refinement.

        Returns:
            A new TSExtractionResult that may contain additional candidate
            terms derived from the LLM, typically marked for human review.
        """
        raise NotImplementedError


class HybridTSExtractor(ITSExtractor):
    """Hybrid Term Sheet extractor with multi-layer pipeline.

    The hybrid extractor orchestrates three potential layers:

    1. Rule-based extraction (mandatory, uses TSExtractor).
    2. Semantic/ML refinement (optional, via ISemanticRefiner).
    3. LLM-based fallback extraction (optional, via ILLMExtractor).

    When semantic_refiner or llm_extractor is not provided, the
    corresponding layer is simply skipped.
    """

    def __init__(
        self,
        rule_extractor: Optional[ITSExtractor] = None,
        semantic_refiner: Optional[ISemanticRefiner] = None,
        llm_extractor: Optional[ILLMExtractor] = None,
    ) -> None:
        self._rule_extractor = rule_extractor or TSExtractor()
        self._semantic_refiner = semantic_refiner
        self._llm_extractor = llm_extractor

    def extract(self, parsed_doc: ParsedDocument) -> TSExtractionResult:
        """Run the multi-layer extraction pipeline.

        Args:
            parsed_doc: The parsed Term Sheet document.

        Returns:
            Final TSExtractionResult after applying rule-based extraction
            and any configured refinement/fallback layers.
        """
        # Layer 1: rule-based extraction (always executed)
        result = self._rule_extractor.extract(parsed_doc)

        # Layer 2: semantic refinement (optional)
        if self._semantic_refiner is not None:
            result = self._semantic_refiner.refine(parsed_doc, result)

        # Layer 3: LLM-based fallback (optional)
        if self._llm_extractor is not None:
            result = self._llm_extractor.extract_missing_terms(parsed_doc, result)

        return result

    def serialize(self, result: TSExtractionResult) -> str:
        """Delegate serialization to the underlying rule extractor if available."""
        if hasattr(self._rule_extractor, "serialize"):
            return self._rule_extractor.serialize(result)  # type: ignore[no-any-return]
        from ..models.extraction import TSExtractionResult as _TSResult

        if not isinstance(result, _TSResult):
            raise TypeError("Expected TSExtractionResult for serialization")
        return TSExtractor().serialize(result)

    def deserialize(self, json_str: str) -> TSExtractionResult:
        """Delegate deserialization to the underlying rule extractor if available."""
        if hasattr(self._rule_extractor, "deserialize"):
            return self._rule_extractor.deserialize(json_str)  # type: ignore[no-any-return]
        return TSExtractor().deserialize(json_str)
