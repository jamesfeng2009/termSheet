"""Performance optimization utilities for the TS Contract Alignment System.

This module provides performance monitoring, query optimization, and
caching utilities to ensure processing within 60 seconds for standard documents.
"""

import functools
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .audit.database import DatabaseManager


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PerformanceMetrics:
    """Performance metrics for pipeline operations."""
    
    operation_name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark the operation as finished."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error


class PerformanceMonitor:
    """
    Monitor and track performance metrics for pipeline operations.
    
    Helps identify bottlenecks and ensure processing time requirements are met.
    """
    
    def __init__(self, max_processing_time: int = 60):
        """
        Initialize the performance monitor.
        
        Args:
            max_processing_time: Maximum allowed processing time in seconds.
        """
        self.max_processing_time = max_processing_time
        self.metrics: Dict[str, list[PerformanceMetrics]] = {}
        self._operation_stack: list[PerformanceMetrics] = []
    
    def start_operation(self, operation_name: str, **metadata) -> PerformanceMetrics:
        """
        Start tracking an operation.
        
        Args:
            operation_name: Name of the operation.
            **metadata: Additional metadata to track.
            
        Returns:
            PerformanceMetrics object for this operation.
        """
        metric = PerformanceMetrics(
            operation_name=operation_name,
            metadata=metadata
        )
        self._operation_stack.append(metric)
        return metric
    
    def end_operation(
        self,
        metric: Optional[PerformanceMetrics] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        End tracking an operation.
        
        Args:
            metric: The metric to end. If None, ends the most recent operation.
            success: Whether the operation succeeded.
            error: Optional error message.
        """
        if metric is None and self._operation_stack:
            metric = self._operation_stack.pop()
        elif metric and metric in self._operation_stack:
            self._operation_stack.remove(metric)
        
        if metric:
            metric.finish(success=success, error=error)
            
            # Store in metrics history
            if metric.operation_name not in self.metrics:
                self.metrics[metric.operation_name] = []
            self.metrics[metric.operation_name].append(metric)
            
            # Log if operation took too long
            if metric.duration and metric.duration > self.max_processing_time:
                logger.warning(
                    f"Operation '{metric.operation_name}' exceeded max time: "
                    f"{metric.duration:.2f}s > {self.max_processing_time}s"
                )
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific operation.
        
        Args:
            operation_name: Name of the operation.
            
        Returns:
            Dictionary with statistics (avg, min, max, count).
        """
        if operation_name not in self.metrics:
            return {}
        
        durations = [
            m.duration for m in self.metrics[operation_name]
            if m.duration is not None
        ]
        
        if not durations:
            return {}
        
        return {
            "count": len(durations),
            "average": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
            "total": sum(durations),
            "success_rate": sum(
                1 for m in self.metrics[operation_name] if m.success
            ) / len(self.metrics[operation_name])
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tracked operations."""
        return {
            name: self.get_operation_stats(name)
            for name in self.metrics.keys()
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics.clear()
        self._operation_stack.clear()


def timed_operation(operation_name: str):
    """
    Decorator to automatically track operation performance.
    
    Args:
        operation_name: Name of the operation to track.
        
    Example:
        @timed_operation("parse_document")
        def parse_document(file_path):
            # ... parsing logic
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.debug(f"{operation_name} completed in {duration:.2f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"{operation_name} failed after {duration:.2f}s: {e}")
                raise
        return wrapper
    return decorator


class DatabaseOptimizer:
    """
    Database query optimizer for PostgreSQL + pgvector.
    
    Ensures proper indexing and query optimization for fast vector search
    and efficient data retrieval.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the database optimizer.
        
        Args:
            db_manager: Database manager instance.
        """
        self.db_manager = db_manager
    
    def ensure_indexes(self) -> None:
        """
        Ensure all required indexes exist for optimal performance.
        
        Creates indexes on:
        - Document IDs for fast lookups
        - Timestamps for time-based queries
        - Vector columns with IVFFlat or HNSW indexes
        """
        with self.db_manager.engine.connect() as conn:
            # Check if pgvector is available
            try:
                result = conn.execute(text(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                ))
                has_pgvector = result.scalar()
            except Exception:
                has_pgvector = False
            
            if not has_pgvector:
                logger.warning("pgvector extension not available, skipping vector indexes")
                return
            
            # Create vector indexes if they don't exist
            vector_indexes = [
                # IVFFlat index for clause embeddings (good for medium datasets)
                """
                CREATE INDEX IF NOT EXISTS idx_clause_embeddings_vector_ivfflat
                ON clause_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """,
                
                # IVFFlat index for term embeddings
                """
                CREATE INDEX IF NOT EXISTS idx_term_embeddings_vector_ivfflat
                ON term_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """,
            ]
            
            for index_sql in vector_indexes:
                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                    logger.info("Vector index created successfully")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"Failed to create vector index: {e}")
            
            # Create standard B-tree indexes for fast lookups
            standard_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_documents_id ON documents(id)",
                "CREATE INDEX IF NOT EXISTS idx_documents_upload_timestamp ON documents(upload_timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_audit_events_document_id ON audit_events(document_id)",
                "CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON audit_events(event_type)",
            ]
            
            for index_sql in standard_indexes:
                try:
                    conn.execute(text(index_sql))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.debug(f"Index may already exist: {e}")
    
    def optimize_vector_search(self, lists: int = 100) -> None:
        """
        Optimize vector search parameters.
        
        Args:
            lists: Number of lists for IVFFlat index (higher = more accurate but slower).
        """
        with self.db_manager.engine.connect() as conn:
            try:
                # Set effective_cache_size for better query planning
                conn.execute(text("SET effective_cache_size = '4GB'"))
                
                # Set work_mem for sorting and hashing operations
                conn.execute(text("SET work_mem = '256MB'"))
                
                # Set maintenance_work_mem for index creation
                conn.execute(text("SET maintenance_work_mem = '512MB'"))
                
                conn.commit()
                logger.info("Vector search parameters optimized")
            except Exception as e:
                conn.rollback()
                logger.warning(f"Failed to optimize vector search: {e}")
    
    def analyze_tables(self) -> None:
        """
        Run ANALYZE on all tables to update statistics for query planner.
        
        This helps PostgreSQL choose optimal query plans.
        """
        with self.db_manager.engine.connect() as conn:
            tables = [
                "documents",
                "ts_extractions",
                "template_analyses",
                "clause_embeddings",
                "term_embeddings",
                "alignments",
                "generated_contracts",
                "review_sessions",
                "audit_events",
                "version_history",
            ]
            
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    logger.debug(f"Failed to analyze table {table}: {e}")
    
    def vacuum_tables(self, full: bool = False) -> None:
        """
        Run VACUUM on all tables to reclaim storage and update statistics.
        
        Args:
            full: If True, run VACUUM FULL (more thorough but locks tables).
        """
        vacuum_cmd = "VACUUM FULL" if full else "VACUUM"
        
        with self.db_manager.engine.connect() as conn:
            # VACUUM cannot run inside a transaction block
            conn.execution_options(isolation_level="AUTOCOMMIT")
            
            tables = [
                "documents",
                "ts_extractions",
                "template_analyses",
                "clause_embeddings",
                "term_embeddings",
                "alignments",
                "generated_contracts",
                "review_sessions",
                "audit_events",
                "version_history",
            ]
            
            for table in tables:
                try:
                    conn.execute(text(f"{vacuum_cmd} {table}"))
                    logger.info(f"Vacuumed table {table}")
                except Exception as e:
                    logger.warning(f"Failed to vacuum table {table}: {e}")
    
    def get_table_sizes(self) -> Dict[str, Dict[str, Any]]:
        """
        Get size information for all tables.
        
        Returns:
            Dictionary mapping table names to size information.
        """
        with self.db_manager.engine.connect() as conn:
            query = text("""
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                                   pg_relation_size(schemaname||'.'||tablename)) AS index_size
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
            
            result = conn.execute(query)
            return {
                row[0]: {
                    "total_size": row[1],
                    "table_size": row[2],
                    "index_size": row[3],
                }
                for row in result
            }
    
    def get_index_usage(self) -> Dict[str, Dict[str, Any]]:
        """
        Get index usage statistics.
        
        Returns:
            Dictionary mapping index names to usage statistics.
        """
        with self.db_manager.engine.connect() as conn:
            query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """)
            
            result = conn.execute(query)
            return {
                row[2]: {
                    "table": row[1],
                    "scans": row[3],
                    "tuples_read": row[4],
                    "tuples_fetched": row[5],
                }
                for row in result
            }


class SimpleCache:
    """
    Simple in-memory cache for frequently accessed data.
    
    Helps reduce database queries for commonly accessed documents
    and analysis results.
    """
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialize the cache.
        
        Args:
            max_size: Maximum number of items to cache.
            ttl: Time-to-live for cache entries in seconds.
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key.
            
        Returns:
            Cached value or None if not found or expired.
        """
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        
        # Check if expired
        if time.time() - timestamp > self.ttl:
            del self._cache[key]
            return None
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key.
            value: Value to cache.
        """
        # Evict oldest entry if cache is full
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        
        self._cache[key] = (value, time.time())
    
    def invalidate(self, key: str) -> None:
        """
        Invalidate a cache entry.
        
        Args:
            key: Cache key to invalidate.
        """
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def size(self) -> int:
        """Get the current cache size."""
        return len(self._cache)


def cached(cache: SimpleCache, key_func: Callable[..., str]):
    """
    Decorator to cache function results.
    
    Args:
        cache: SimpleCache instance to use.
        key_func: Function to generate cache key from arguments.
        
    Example:
        cache = SimpleCache()
        
        @cached(cache, lambda doc_id: f"doc_{doc_id}")
        def get_document(doc_id):
            # ... expensive operation
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = key_func(*args, **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cast(T, cached_value)
            
            # Compute and cache
            logger.debug(f"Cache miss for key: {key}")
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        
        return wrapper
    return decorator
