"""Template Analyzer implementation for the TS Contract Alignment System.

This module implements the ITemplateAnalyzer interface to analyze contract
templates, classify clauses, detect fillable segments, and generate embeddings.
"""

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces.analyzer import ITemplateAnalyzer
from ..models.document import DocumentSection, ParsedDocument, TextSegment
from ..models.enums import ClauseCategory
from ..models.template import (
    AnalyzedClause,
    FillableSegment,
    FillableType,
    TemplateAnalysisResult,
)
from .clause_patterns import ClausePatternMatcher


class TemplateAnalyzer(ITemplateAnalyzer):
    """
    Contract template analyzer.
    
    Analyzes contract templates to identify clauses, classify them by
    semantic category, detect fillable segments, and generate embeddings.
    """

    def __init__(self, embedding_model: Optional[Any] = None):
        """
        Initialize the template analyzer.
        
        Args:
            embedding_model: Optional sentence-transformers model for embeddings.
                           If None, embeddings will not be generated.
        """
        self._pattern_matcher = ClausePatternMatcher()
        self._embedding_model = embedding_model
        self._clause_counter = 0
        self._segment_counter = 0

    def analyze(self, parsed_doc: ParsedDocument) -> TemplateAnalysisResult:
        """
        Analyze a parsed contract template document.
        
        Args:
            parsed_doc: The parsed contract template document.
            
        Returns:
            TemplateAnalysisResult containing analyzed clauses and structure.
        """
        self._clause_counter = 0
        self._segment_counter = 0
        
        clauses: List[AnalyzedClause] = []
        structure_map: Dict[str, Any] = {
            "document_id": parsed_doc.id,
            "filename": parsed_doc.filename,
            "section_hierarchy": [],
        }
        
        # Process all sections recursively
        for section in parsed_doc.sections:
            section_clauses, section_structure = self._process_section(section)
            clauses.extend(section_clauses)
            structure_map["section_hierarchy"].append(section_structure)
        
        return TemplateAnalysisResult(
            document_id=parsed_doc.id,
            clauses=clauses,
            structure_map=structure_map,
            analysis_timestamp=datetime.utcnow().isoformat()
        )


    def _process_section(
        self, section: DocumentSection
    ) -> Tuple[List[AnalyzedClause], Dict[str, Any]]:
        """
        Process a document section and create analyzed clauses.
        
        Args:
            section: The document section to process.
            
        Returns:
            Tuple of (list of analyzed clauses, structure map for section).
        """
        clauses: List[AnalyzedClause] = []
        
        # Build structure map for this section
        structure = {
            "section_id": section.id,
            "title": section.title,
            "number": section.number,
            "level": section.level.value,
            "children": [],
        }
        
        # Get combined text for classification
        section_text = self._get_section_text(section)
        
        # Only create clause if section has meaningful content
        if section_text.strip():
            clause = self._create_clause_from_section(section, section_text)
            if clause:
                clauses.append(clause)
                structure["clause_id"] = clause.id
        
        # Process child sections recursively
        for child in section.children:
            child_clauses, child_structure = self._process_section(child)
            clauses.extend(child_clauses)
            structure["children"].append(child_structure)
        
        return clauses, structure

    def _get_section_text(self, section: DocumentSection) -> str:
        """Get combined text from a section."""
        parts = []
        if section.title:
            parts.append(section.title)
        for segment in section.segments:
            parts.append(segment.content)
        return " ".join(parts)

    def _create_clause_from_section(
        self, section: DocumentSection, section_text: str
    ) -> Optional[AnalyzedClause]:
        """
        Create an AnalyzedClause from a document section.
        
        Args:
            section: The document section.
            section_text: Combined text from the section.
            
        Returns:
            AnalyzedClause or None if section is empty.
        """
        if not section_text.strip():
            return None
        
        # Classify the clause
        category, confidence = self._pattern_matcher.classify(
            section_text, section.title
        )
        
        # Extract keywords
        keywords = self._pattern_matcher.extract_keywords(section_text, category)
        
        # Detect fillable segments
        fillable_segments = self._detect_fillable_segments(section)
        
        # Generate semantic embedding if model available
        embedding = self._generate_embedding(section_text)
        
        clause_id = self._generate_clause_id()
        
        return AnalyzedClause(
            id=clause_id,
            section_id=section.id,
            title=section.title or f"Clause {clause_id}",
            category=category,
            full_text=section_text,
            fillable_segments=fillable_segments,
            keywords=keywords,
            semantic_embedding=embedding
        )

    def _generate_clause_id(self) -> str:
        """Generate a unique clause ID."""
        self._clause_counter += 1
        return f"clause_{self._clause_counter:04d}"

    def _generate_segment_id(self) -> str:
        """Generate a unique fillable segment ID."""
        self._segment_counter += 1
        return f"fill_{self._segment_counter:04d}"

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate semantic embedding for text.
        
        Args:
            text: The text to embed.
            
        Returns:
            List of floats representing the embedding, or None if no model.
        """
        if self._embedding_model is None:
            return None
        
        try:
            # sentence-transformers encode method
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except Exception:
            return None

    def _detect_fillable_segments(
        self, section: DocumentSection
    ) -> List[FillableSegment]:
        """
        Detect fillable segments in a section.
        
        Identifies placeholder-like patterns and generic values that
        can be filled with data from the Term Sheet.
        
        Args:
            section: The document section to analyze.
            
        Returns:
            List of detected fillable segments.
        """
        segments: List[FillableSegment] = []
        
        for text_segment in section.segments:
            detected = self._find_fillable_patterns(text_segment)
            segments.extend(detected)
        
        return segments


    def _find_fillable_patterns(
        self, text_segment: TextSegment
    ) -> List[FillableSegment]:
        """
        Find fillable patterns in a text segment.
        
        Detects various placeholder patterns including:
        - Bracketed placeholders: [amount], [date], etc.
        - Underscores: ____, ______
        - Generic values: "XX", "___"
        - Currency placeholders: $[amount], USD [amount]
        - Date placeholders: [date], YYYY-MM-DD
        - Percentage placeholders: [%], ___%
        
        Args:
            text_segment: The text segment to analyze.
            
        Returns:
            List of detected fillable segments.
        """
        segments: List[FillableSegment] = []
        content = text_segment.content
        
        # Define patterns for different fillable types
        patterns = [
            # Currency patterns
            (r'\$\s*\[[\w\s]+\]', FillableType.CURRENCY),
            (r'(?:USD|RMB|CNY|EUR|¥|\$)\s*_{2,}', FillableType.CURRENCY),
            (r'(?:USD|RMB|CNY|EUR|¥|\$)\s*\[[\w\s]+\]', FillableType.CURRENCY),
            (r'\[(?:amount|金额|投资金额|价格)\]', FillableType.CURRENCY),
            
            # Percentage patterns
            (r'_{2,}\s*%', FillableType.PERCENTAGE),
            (r'\[[\w\s]*(?:percentage|percent|比例|%)\s*\]', FillableType.PERCENTAGE),
            (r'XX\.?X*\s*%', FillableType.PERCENTAGE),
            
            # Date patterns
            (r'\[(?:date|日期|签署日期|生效日期)\]', FillableType.DATE),
            (r'_{2,}年_{2,}月_{2,}日', FillableType.DATE),
            (r'YYYY[-/]MM[-/]DD', FillableType.DATE),
            (r'\d{4}[-/]__[-/]__', FillableType.DATE),
            
            # Number patterns
            (r'\[(?:number|数量|股数|shares)\]', FillableType.NUMBER),
            (r'_{2,}\s*(?:shares|股|份)', FillableType.NUMBER),
            
            # Generic bracketed placeholders
            (r'\[[\w\s\u4e00-\u9fff]+\]', FillableType.TEXT),
            
            # Underscore placeholders
            (r'_{3,}', FillableType.TEXT),
            
            # XX placeholders
            (r'(?<!\w)XX+(?!\w)', FillableType.TEXT),
        ]
        
        for pattern, fillable_type in patterns:
            for match in re.finditer(pattern, content):
                # Calculate absolute positions
                start = text_segment.start_pos + match.start()
                end = text_segment.start_pos + match.end()
                
                # Get context
                context_start = max(0, match.start() - 30)
                context_end = min(len(content), match.end() + 30)
                context_before = content[context_start:match.start()].strip()
                context_after = content[match.end():context_end].strip()
                
                # Get current value (the matched placeholder text)
                current_value = match.group(0)
                
                segment = FillableSegment(
                    id=self._generate_segment_id(),
                    location_start=start,
                    location_end=end,
                    expected_type=fillable_type,
                    context_before=context_before,
                    context_after=context_after,
                    current_value=current_value
                )
                segments.append(segment)
        
        # Remove duplicates (overlapping matches)
        segments = self._remove_overlapping_segments(segments)
        
        return segments

    def _remove_overlapping_segments(
        self, segments: List[FillableSegment]
    ) -> List[FillableSegment]:
        """Remove overlapping fillable segments, keeping the more specific ones."""
        if not segments:
            return segments
        
        # Sort by start position, then by length (shorter = more specific)
        sorted_segments = sorted(
            segments, 
            key=lambda s: (s.location_start, s.location_end - s.location_start)
        )
        
        result: List[FillableSegment] = []
        for segment in sorted_segments:
            # Check if this segment overlaps with any existing segment
            overlaps = False
            for existing in result:
                if (segment.location_start < existing.location_end and 
                    segment.location_end > existing.location_start):
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(segment)
        
        return result


    def serialize(self, result: TemplateAnalysisResult) -> str:
        """
        Serialize a TemplateAnalysisResult to JSON string.
        
        Args:
            result: The analysis result to serialize.
            
        Returns:
            JSON string representation of the analysis result.
        """
        return json.dumps(
            self._result_to_dict(result),
            ensure_ascii=False,
            indent=2
        )

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
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
        
        return self._dict_to_result(data)

    def _result_to_dict(self, result: TemplateAnalysisResult) -> Dict[str, Any]:
        """Convert TemplateAnalysisResult to dictionary."""
        return {
            "document_id": result.document_id,
            "clauses": [self._clause_to_dict(c) for c in result.clauses],
            "structure_map": result.structure_map,
            "analysis_timestamp": result.analysis_timestamp,
        }

    def _dict_to_result(self, data: Dict[str, Any]) -> TemplateAnalysisResult:
        """Convert dictionary to TemplateAnalysisResult."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for TemplateAnalysisResult")
        
        if "document_id" not in data:
            raise ValueError("Missing required field 'document_id'")
        
        return TemplateAnalysisResult(
            document_id=data["document_id"],
            clauses=[self._dict_to_clause(c) for c in data.get("clauses", [])],
            structure_map=data.get("structure_map", {}),
            analysis_timestamp=data.get("analysis_timestamp", ""),
        )

    def _clause_to_dict(self, clause: AnalyzedClause) -> Dict[str, Any]:
        """Convert AnalyzedClause to dictionary."""
        return {
            "id": clause.id,
            "section_id": clause.section_id,
            "title": clause.title,
            "category": clause.category.value,
            "full_text": clause.full_text,
            "fillable_segments": [
                self._segment_to_dict(s) for s in clause.fillable_segments
            ],
            "keywords": clause.keywords,
            "semantic_embedding": clause.semantic_embedding,
        }

    def _dict_to_clause(self, data: Dict[str, Any]) -> AnalyzedClause:
        """Convert dictionary to AnalyzedClause."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for AnalyzedClause")
        
        required_fields = ["id", "section_id", "title", "category", "full_text"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in AnalyzedClause")
        
        return AnalyzedClause(
            id=data["id"],
            section_id=data["section_id"],
            title=data["title"],
            category=ClauseCategory(data["category"]),
            full_text=data["full_text"],
            fillable_segments=[
                self._dict_to_segment(s) for s in data.get("fillable_segments", [])
            ],
            keywords=data.get("keywords", []),
            semantic_embedding=data.get("semantic_embedding"),
        )

    def _segment_to_dict(self, segment: FillableSegment) -> Dict[str, Any]:
        """Convert FillableSegment to dictionary."""
        return {
            "id": segment.id,
            "location_start": segment.location_start,
            "location_end": segment.location_end,
            "expected_type": segment.expected_type.value,
            "context_before": segment.context_before,
            "context_after": segment.context_after,
            "current_value": segment.current_value,
        }

    def _dict_to_segment(self, data: Dict[str, Any]) -> FillableSegment:
        """Convert dictionary to FillableSegment."""
        if not isinstance(data, dict):
            raise ValueError("Expected dictionary for FillableSegment")
        
        required_fields = [
            "id", "location_start", "location_end", "expected_type",
            "context_before", "context_after"
        ]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in FillableSegment")
        
        return FillableSegment(
            id=data["id"],
            location_start=data["location_start"],
            location_end=data["location_end"],
            expected_type=FillableType(data["expected_type"]),
            context_before=data["context_before"],
            context_after=data["context_after"],
            current_value=data.get("current_value"),
        )
