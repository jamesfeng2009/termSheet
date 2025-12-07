"""Diff highlighting for document modifications."""

from typing import List, Dict, Optional
from enum import Enum
import difflib

from ..models.enums import ActionType
from ..interfaces.generator import Modification


class DiffType(Enum):
    """Types of differences."""
    INSERT = "insert"
    DELETE = "delete"
    REPLACE = "replace"
    EQUAL = "equal"


class DiffSegment:
    """A segment of text with diff information."""

    def __init__(
        self,
        text: str,
        diff_type: DiffType,
        start_pos: int = 0,
        end_pos: int = 0,
    ):
        """
        Initialize a diff segment.
        
        Args:
            text: The text content.
            diff_type: The type of difference.
            start_pos: Start position in the document.
            end_pos: End position in the document.
        """
        self.text = text
        self.diff_type = diff_type
        self.start_pos = start_pos
        self.end_pos = end_pos


class DiffHighlighter:
    """
    Highlights differences between original and modified text.
    
    Provides detailed diff information with color coding for
    insertions, deletions, and replacements.
    """

    def __init__(self):
        """Initialize the diff highlighter."""
        self.color_scheme = {
            DiffType.INSERT: "#c8e6c9",  # Green
            DiffType.DELETE: "#ffcdd2",  # Red
            DiffType.REPLACE: "#fff9c4",  # Yellow
            DiffType.EQUAL: "#ffffff",   # White
        }

    def highlight_modification(self, modification: Modification) -> Dict:
        """
        Generate highlighted diff for a modification.
        
        Args:
            modification: The modification to highlight.
            
        Returns:
            Dictionary with diff segments and styling information.
        """
        original = modification.original_text
        new = modification.new_text
        action = modification.action

        if action == ActionType.INSERT:
            # Pure insertion - no original text
            return {
                'type': 'insert',
                'segments': [
                    {
                        'text': new,
                        'diff_type': DiffType.INSERT.value,
                        'color': self.color_scheme[DiffType.INSERT],
                    }
                ],
                'original_text': '',
                'new_text': new,
                'action': action.value,
                'confidence': modification.confidence,
                'source_id': modification.source_ts_paragraph_id,
            }
        elif action == ActionType.OVERRIDE:
            # Replacement - show both original and new
            segments = self._compute_diff_segments(original, new)
            return {
                'type': 'override',
                'segments': segments,
                'original_text': original,
                'new_text': new,
                'action': action.value,
                'confidence': modification.confidence,
                'source_id': modification.source_ts_paragraph_id,
            }
        else:
            # Skip or other action
            return {
                'type': 'skip',
                'segments': [],
                'original_text': original,
                'new_text': new,
                'action': action.value,
                'confidence': modification.confidence,
                'source_id': modification.source_ts_paragraph_id,
            }

    def _compute_diff_segments(self, original: str, new: str) -> List[Dict]:
        """
        Compute detailed diff segments between two texts.
        
        Args:
            original: Original text.
            new: New text.
            
        Returns:
            List of diff segments with styling.
        """
        # Use difflib to compute differences
        matcher = difflib.SequenceMatcher(None, original, new)
        segments = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                # Text is the same
                segments.append({
                    'text': original[i1:i2],
                    'diff_type': DiffType.EQUAL.value,
                    'color': self.color_scheme[DiffType.EQUAL],
                    'original': True,
                    'new': True,
                })
            elif tag == 'delete':
                # Text was deleted
                segments.append({
                    'text': original[i1:i2],
                    'diff_type': DiffType.DELETE.value,
                    'color': self.color_scheme[DiffType.DELETE],
                    'original': True,
                    'new': False,
                })
            elif tag == 'insert':
                # Text was inserted
                segments.append({
                    'text': new[j1:j2],
                    'diff_type': DiffType.INSERT.value,
                    'color': self.color_scheme[DiffType.INSERT],
                    'original': False,
                    'new': True,
                })
            elif tag == 'replace':
                # Text was replaced - show both
                segments.append({
                    'text': original[i1:i2],
                    'diff_type': DiffType.DELETE.value,
                    'color': self.color_scheme[DiffType.DELETE],
                    'original': True,
                    'new': False,
                })
                segments.append({
                    'text': new[j1:j2],
                    'diff_type': DiffType.INSERT.value,
                    'color': self.color_scheme[DiffType.INSERT],
                    'original': False,
                    'new': True,
                })

        return segments

    def generate_html_diff(self, modification: Modification) -> str:
        """
        Generate HTML representation of the diff.
        
        Args:
            modification: The modification to render.
            
        Returns:
            HTML string with styled diff.
        """
        diff_data = self.highlight_modification(modification)
        
        if diff_data['type'] == 'insert':
            return f'<span class="diff-insert" style="background-color: {self.color_scheme[DiffType.INSERT]}">{diff_data["new_text"]}</span>'
        
        elif diff_data['type'] == 'override':
            html_parts = []
            for segment in diff_data['segments']:
                if segment['diff_type'] == DiffType.DELETE.value:
                    html_parts.append(
                        f'<span class="diff-delete" style="background-color: {segment["color"]}; text-decoration: line-through;">{segment["text"]}</span>'
                    )
                elif segment['diff_type'] == DiffType.INSERT.value:
                    html_parts.append(
                        f'<span class="diff-insert" style="background-color: {segment["color"]}; font-weight: bold;">{segment["text"]}</span>'
                    )
                else:
                    html_parts.append(f'<span>{segment["text"]}</span>')
            return ''.join(html_parts)
        
        else:
            return diff_data['original_text']

    def get_modification_tooltip(self, modification: Modification) -> str:
        """
        Generate tooltip text for a modification.
        
        Args:
            modification: The modification.
            
        Returns:
            Tooltip text with modification details.
        """
        action_text = {
            ActionType.INSERT: "Insertion",
            ActionType.OVERRIDE: "Override",
            ActionType.SKIP: "Skipped",
        }.get(modification.action, "Unknown")

        confidence_pct = int(modification.confidence * 100)
        
        tooltip = f"{action_text} (Confidence: {confidence_pct}%)\n"
        tooltip += f"Source: {modification.source_ts_paragraph_id}\n"
        
        if modification.action == ActionType.OVERRIDE:
            tooltip += f"Original: {modification.original_text[:50]}...\n"
            tooltip += f"New: {modification.new_text[:50]}..."
        else:
            tooltip += f"Text: {modification.new_text[:50]}..."
        
        return tooltip

    def classify_modification_severity(self, modification: Modification) -> str:
        """
        Classify the severity of a modification for visual emphasis.
        
        Args:
            modification: The modification to classify.
            
        Returns:
            Severity level: 'low', 'medium', or 'high'.
        """
        # Low confidence modifications are high severity
        if modification.confidence < 0.6:
            return 'high'
        elif modification.confidence < 0.8:
            return 'medium'
        else:
            return 'low'

    def get_conflict_indicators(self, modifications: List[Modification]) -> List[Dict]:
        """
        Identify potential conflicts between modifications.
        
        Args:
            modifications: List of modifications to analyze.
            
        Returns:
            List of conflict indicators.
        """
        conflicts = []
        
        # Check for overlapping modifications
        for i, mod1 in enumerate(modifications):
            for mod2 in modifications[i+1:]:
                # Check if locations overlap
                if self._ranges_overlap(
                    (mod1.location_start, mod1.location_end),
                    (mod2.location_start, mod2.location_end)
                ):
                    conflicts.append({
                        'mod1_id': mod1.id,
                        'mod2_id': mod2.id,
                        'type': 'overlap',
                        'severity': 'high',
                        'message': f"Modifications {mod1.id} and {mod2.id} overlap",
                    })
        
        return conflicts

    def _ranges_overlap(self, range1: tuple, range2: tuple) -> bool:
        """Check if two ranges overlap."""
        start1, end1 = range1
        start2, end2 = range2
        return start1 < end2 and start2 < end1
