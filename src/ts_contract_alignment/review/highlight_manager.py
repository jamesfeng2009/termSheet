"""Highlighting and scroll synchronization for review interface."""

from typing import Dict, List, Optional, Tuple


class HighlightManager:
    """
    Manages linked highlighting and scroll synchronization.
    
    Tracks relationships between TS terms and contract clauses
    to enable interactive highlighting and navigation.
    """

    def __init__(self):
        """Initialize the highlight manager."""
        self.term_to_clause_map: Dict[str, str] = {}
        self.clause_to_term_map: Dict[str, str] = {}
        self.term_positions: Dict[str, Tuple[int, int]] = {}
        self.clause_positions: Dict[str, Tuple[int, int]] = {}

    def build_mapping(self, modifications: List) -> None:
        """
        Build bidirectional mapping between terms and clauses.
        
        Args:
            modifications: List of Modification objects linking terms to clauses.
        """
        self.term_to_clause_map.clear()
        self.clause_to_term_map.clear()

        for mod in modifications:
            term_id = mod.source_ts_paragraph_id
            clause_id = mod.match_id

            self.term_to_clause_map[term_id] = clause_id
            self.clause_to_term_map[clause_id] = term_id

    def set_term_position(self, term_id: str, start: int, end: int) -> None:
        """
        Set the position of a term in the document.
        
        Args:
            term_id: The term identifier.
            start: Start position in the document.
            end: End position in the document.
        """
        self.term_positions[term_id] = (start, end)

    def set_clause_position(self, clause_id: str, start: int, end: int) -> None:
        """
        Set the position of a clause in the document.
        
        Args:
            clause_id: The clause identifier.
            start: Start position in the document.
            end: End position in the document.
        """
        self.clause_positions[clause_id] = (start, end)

    def get_linked_clause(self, term_id: str) -> Optional[str]:
        """
        Get the clause ID linked to a term.
        
        Args:
            term_id: The term identifier.
            
        Returns:
            Clause ID if linked, None otherwise.
        """
        return self.term_to_clause_map.get(term_id)

    def get_linked_term(self, clause_id: str) -> Optional[str]:
        """
        Get the term ID linked to a clause.
        
        Args:
            clause_id: The clause identifier.
            
        Returns:
            Term ID if linked, None otherwise.
        """
        return self.clause_to_term_map.get(clause_id)

    def get_term_position(self, term_id: str) -> Optional[Tuple[int, int]]:
        """
        Get the position of a term.
        
        Args:
            term_id: The term identifier.
            
        Returns:
            Tuple of (start, end) positions if found, None otherwise.
        """
        return self.term_positions.get(term_id)

    def get_clause_position(self, clause_id: str) -> Optional[Tuple[int, int]]:
        """
        Get the position of a clause.
        
        Args:
            clause_id: The clause identifier.
            
        Returns:
            Tuple of (start, end) positions if found, None otherwise.
        """
        return self.clause_positions.get(clause_id)

    def calculate_scroll_offset(
        self,
        source_position: Tuple[int, int],
        target_position: Tuple[int, int],
        viewport_height: int = 800,
    ) -> int:
        """
        Calculate scroll offset to center target in viewport.
        
        Args:
            source_position: Current position (start, end).
            target_position: Target position (start, end).
            viewport_height: Height of the viewport in pixels.
            
        Returns:
            Scroll offset in pixels.
        """
        target_start, target_end = target_position
        target_center = (target_start + target_end) // 2
        
        # Center the target in the viewport
        scroll_offset = max(0, target_center - viewport_height // 2)
        return scroll_offset

    def get_highlight_data(self, element_id: str, element_type: str) -> Dict:
        """
        Get highlighting data for an element.
        
        Args:
            element_id: The element identifier.
            element_type: Either 'term' or 'clause'.
            
        Returns:
            Dictionary with highlighting information.
        """
        if element_type == 'term':
            linked_clause = self.get_linked_clause(element_id)
            position = self.get_term_position(element_id)
            return {
                'element_id': element_id,
                'element_type': 'term',
                'linked_id': linked_clause,
                'linked_type': 'clause' if linked_clause else None,
                'position': position,
                'has_link': linked_clause is not None,
            }
        elif element_type == 'clause':
            linked_term = self.get_linked_term(element_id)
            position = self.get_clause_position(element_id)
            return {
                'element_id': element_id,
                'element_type': 'clause',
                'linked_id': linked_term,
                'linked_type': 'term' if linked_term else None,
                'position': position,
                'has_link': linked_term is not None,
            }
        else:
            raise ValueError(f"Invalid element_type: {element_type}")

    def get_all_links(self) -> List[Dict]:
        """
        Get all term-clause links.
        
        Returns:
            List of dictionaries with link information.
        """
        links = []
        for term_id, clause_id in self.term_to_clause_map.items():
            links.append({
                'term_id': term_id,
                'clause_id': clause_id,
                'term_position': self.get_term_position(term_id),
                'clause_position': self.get_clause_position(clause_id),
            })
        return links
