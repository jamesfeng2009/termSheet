"""Semantic matcher for TS-to-template alignment.

This module implements semantic matching using sentence embeddings
to align TS terms with contract clauses when rule-based matching fails.
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from ..models.enums import MatchMethod
from ..models.extraction import ExtractedTerm
from ..models.template import AnalyzedClause


@dataclass
class SemanticMatchResult:
    """Result of semantic matching."""
    clause: AnalyzedClause
    similarity: float
    method: MatchMethod = MatchMethod.SEMANTIC


class SemanticMatcher:
    """
    Semantic matcher for TS-to-template alignment.
    
    Uses sentence embeddings to find semantically similar clauses
    for Term Sheet terms when rule-based matching fails.
    """

    def __init__(
        self,
        embedding_model: Optional[Any] = None,
        similarity_threshold: float = 0.7,
        db_connection: Optional[Any] = None
    ):
        """
        Initialize the semantic matcher.
        
        Args:
            embedding_model: Sentence-transformers model for generating embeddings.
                           If None, semantic matching will be disabled.
            similarity_threshold: Minimum similarity score for a match.
            db_connection: Optional PostgreSQL connection for pgvector queries.
        """
        self._embedding_model = embedding_model
        self._similarity_threshold = similarity_threshold
        self._db_connection = db_connection

    @property
    def is_available(self) -> bool:
        """Check if semantic matching is available."""
        return self._embedding_model is not None

    def match(
        self,
        term: ExtractedTerm,
        clauses: List[AnalyzedClause],
        max_results: int = 5
    ) -> List[Tuple[AnalyzedClause, MatchMethod, float]]:
        """
        Find matching clauses for a term using semantic similarity.
        
        Args:
            term: The extracted term to match.
            clauses: List of analyzed clauses to match against.
            max_results: Maximum number of results to return.
            
        Returns:
            List of tuples (clause, match_method, similarity) sorted by similarity.
        """
        if not self.is_available:
            return []
        
        # Generate embedding for the term
        term_embedding = self._generate_embedding(term.raw_text)
        if term_embedding is None:
            return []
        
        # If we have a database connection, use pgvector for efficient search
        if self._db_connection is not None:
            return self._match_with_pgvector(term_embedding, clauses, max_results)
        
        # Otherwise, compute similarities in memory
        return self._match_in_memory(term_embedding, clauses, max_results)


    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.
        
        Args:
            text: The text to embed.
            
        Returns:
            List of floats representing the embedding, or None if failed.
        """
        if self._embedding_model is None:
            return None
        
        try:
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except Exception:
            return None

    def _match_in_memory(
        self,
        term_embedding: List[float],
        clauses: List[AnalyzedClause],
        max_results: int
    ) -> List[Tuple[AnalyzedClause, MatchMethod, float]]:
        """
        Match using in-memory cosine similarity computation.
        
        Args:
            term_embedding: The term's embedding vector.
            clauses: List of analyzed clauses.
            max_results: Maximum number of results.
            
        Returns:
            List of matching clauses with similarity scores.
        """
        results: List[Tuple[AnalyzedClause, MatchMethod, float]] = []
        
        for clause in clauses:
            # Use pre-computed embedding if available
            if clause.semantic_embedding is not None:
                similarity = self._cosine_similarity(
                    term_embedding, clause.semantic_embedding
                )
            else:
                # Generate embedding on the fly
                clause_embedding = self._generate_embedding(clause.full_text)
                if clause_embedding is None:
                    continue
                similarity = self._cosine_similarity(term_embedding, clause_embedding)
            
            if similarity >= self._similarity_threshold:
                results.append((clause, MatchMethod.SEMANTIC, similarity))
        
        # Sort by similarity descending and limit results
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:max_results]

    def _match_with_pgvector(
        self,
        term_embedding: List[float],
        clauses: List[AnalyzedClause],
        max_results: int
    ) -> List[Tuple[AnalyzedClause, MatchMethod, float]]:
        """
        Match using PostgreSQL pgvector for efficient vector search.
        
        Args:
            term_embedding: The term's embedding vector.
            clauses: List of analyzed clauses (for ID lookup).
            max_results: Maximum number of results.
            
        Returns:
            List of matching clauses with similarity scores.
        """
        if self._db_connection is None:
            return []
        
        try:
            # Create a clause ID to clause mapping for lookup
            clause_map = {clause.id: clause for clause in clauses}
            
            # Query pgvector for similar clauses
            cursor = self._db_connection.cursor()
            
            # Convert embedding to PostgreSQL vector format
            embedding_str = "[" + ",".join(str(x) for x in term_embedding) + "]"
            
            query = """
                SELECT clause_id, 1 - (embedding <=> %s::vector) AS similarity
                FROM clause_embeddings
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            
            cursor.execute(
                query,
                (embedding_str, embedding_str, self._similarity_threshold,
                 embedding_str, max_results)
            )
            
            results: List[Tuple[AnalyzedClause, MatchMethod, float]] = []
            for row in cursor.fetchall():
                clause_id, similarity = row
                if clause_id in clause_map:
                    results.append(
                        (clause_map[clause_id], MatchMethod.SEMANTIC, similarity)
                    )
            
            cursor.close()
            return results
            
        except Exception:
            # Fall back to in-memory matching on database error
            return self._match_in_memory(term_embedding, clauses, max_results)

    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector.
            vec2: Second vector.
            
        Returns:
            Cosine similarity score (0.0 to 1.0).
        """
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

    def set_similarity_threshold(self, threshold: float) -> None:
        """
        Set the similarity threshold for matching.
        
        Args:
            threshold: New threshold value (0.0 to 1.0).
            
        Raises:
            ValueError: If threshold is not between 0.0 and 1.0.
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        self._similarity_threshold = threshold

    def get_similarity_threshold(self) -> float:
        """Get the current similarity threshold."""
        return self._similarity_threshold

    def store_clause_embeddings(
        self,
        clauses: List[AnalyzedClause],
        template_analysis_id: str
    ) -> int:
        """
        Store clause embeddings in the database for efficient search.
        
        Args:
            clauses: List of analyzed clauses to store.
            template_analysis_id: ID of the template analysis.
            
        Returns:
            Number of embeddings stored.
        """
        if self._db_connection is None or self._embedding_model is None:
            return 0
        
        stored_count = 0
        
        try:
            cursor = self._db_connection.cursor()
            
            for clause in clauses:
                # Generate embedding if not already present
                if clause.semantic_embedding is None:
                    embedding = self._generate_embedding(clause.full_text)
                    if embedding is None:
                        continue
                else:
                    embedding = clause.semantic_embedding
                
                # Convert to PostgreSQL vector format
                embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                
                insert_query = """
                    INSERT INTO clause_embeddings 
                    (template_analysis_id, clause_id, clause_text, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (template_analysis_id, clause_id) 
                    DO UPDATE SET embedding = EXCLUDED.embedding
                """
                
                cursor.execute(
                    insert_query,
                    (template_analysis_id, clause.id, clause.full_text, embedding_str)
                )
                stored_count += 1
            
            self._db_connection.commit()
            cursor.close()
            
        except Exception:
            if self._db_connection:
                self._db_connection.rollback()
        
        return stored_count
