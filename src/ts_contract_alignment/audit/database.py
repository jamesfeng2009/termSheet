"""Database connection management for the audit system."""

import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def get_database_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Build PostgreSQL database URL from parameters or environment variables.
    
    Args:
        host: Database host (default: from POSTGRES_HOST env or 'localhost')
        port: Database port (default: from POSTGRES_PORT env or 5432)
        database: Database name (default: from POSTGRES_DB env or 'ts_contract_alignment')
        user: Database user (default: from POSTGRES_USER env or 'postgres')
        password: Database password (default: from POSTGRES_PASSWORD env or 'postgres')
    
    Returns:
        PostgreSQL connection URL string.
    """
    host = host or os.environ.get("POSTGRES_HOST", "localhost")
    port = port or int(os.environ.get("POSTGRES_PORT", "5432"))
    database = database or os.environ.get("POSTGRES_DB", "ts_contract_alignment")
    user = user or os.environ.get("POSTGRES_USER", "postgres")
    password = password or os.environ.get("POSTGRES_PASSWORD", "postgres")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


class DatabaseManager:
    """
    Database connection manager with connection pooling.
    
    Handles database connections, session management, and schema initialization.
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        echo: bool = False,
    ):
        """
        Initialize the database manager.
        
        Args:
            database_url: PostgreSQL connection URL. If None, built from env vars.
            pool_size: Number of connections to keep in the pool.
            max_overflow: Maximum overflow connections beyond pool_size.
            echo: If True, log all SQL statements.
        """
        self._database_url = database_url or get_database_url()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._echo = echo

    @property
    def engine(self) -> Engine:
        """Get or create the database engine."""
        if self._engine is None:
            # SQLite doesn't support pool_size and max_overflow parameters
            if self._database_url.startswith("sqlite"):
                self._engine = create_engine(
                    self._database_url,
                    echo=self._echo,
                )
            else:
                self._engine = create_engine(
                    self._database_url,
                    pool_size=self._pool_size,
                    max_overflow=self._max_overflow,
                    echo=self._echo,
                    pool_pre_ping=True,  # Enable connection health checks
                )
        return self._engine
    
    @property
    def session_factory(self) -> sessionmaker:
        """Get or create the session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup.
        
        Yields:
            SQLAlchemy Session object.
            
        Example:
            with db_manager.get_session() as session:
                session.add(some_object)
                session.commit()
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def init_database(self, enable_pgvector: bool = True) -> None:
        """
        Initialize the database schema.
        
        Creates all tables defined in the models and optionally enables pgvector.
        
        Args:
            enable_pgvector: If True, enable the pgvector extension.
        """
        if enable_pgvector:
            with self.engine.connect() as conn:
                try:
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                    conn.commit()
                except Exception:
                    # pgvector might not be available, continue without it
                    conn.rollback()
        
        Base.metadata.create_all(self.engine)
    
    def drop_all_tables(self) -> None:
        """Drop all tables. Use with caution!"""
        Base.metadata.drop_all(self.engine)
    
    def close(self) -> None:
        """Close the database engine and release all connections."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
    
    def health_check(self) -> bool:
        """
        Check if the database connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
