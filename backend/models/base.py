import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, Integer, DateTime, ForeignKey, JSON, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


# 1. Relational Lane: Master Pull Request Tracking
class PR(Base):
    __tablename__ = "prs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    github_pr_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False) # 'pending', 'analyzed', 'merged'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    findings: Mapped[List["Finding"]] = relationship("Finding", back_populates="pr", cascade="all, delete-orphan")
    events: Mapped[List["AgentEvent"]] = relationship("AgentEvent", back_populates="pr", cascade="all, delete-orphan")


# 2. Relational Lane: AI Review Comments
class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pr_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prs.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)   # 'low', 'medium', 'high', 'critical'
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # 'security', 'bug', 'performance'
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pr: Mapped["PR"] = relationship("PR", back_populates="findings")


# 3. Vector Lane: Code Snippets Scoped PER-REPO
class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repo_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)  # Primary Tenant
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Distinguishes a chunk taken from a PR diff vs. a full-repo baseline
    # scan of the file's complete content. Needed because a diff chunk and
    # a full-file chunk for the same file+sha are different content, not
    # duplicates of each other.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="pr_diff")

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_sha: Mapped[str] = mapped_column(String(40), nullable=False, index=True)    # Git Fingerprint
    
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(768), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Uniqueness guarantee for exact file chunk version -- now scoped
        # by `source` too.
        UniqueConstraint("repo_name", "file_path", "source", "chunk_index", "file_sha", name="uq_repo_file_source_chunk_sha"),
        # Speed up filtered retrieval
        Index("ix_code_chunks_repo_path", "repo_name", "file_path"),
        # HNSW Index for approximate nearest neighbor search
        Index(
            "code_chunks_embedding_hnsw_idx",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 24, "ef_construction": 128},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# 4. Time-Series Lane: Agent Audit Logs
class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pr_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False) # 'webhook_received', 'vector_search_done'
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pr: Mapped["PR"] = relationship("PR", back_populates="events")

    __table_args__ = (
        Index("ix_agent_events_pr_created", "pr_id", "created_at"),
        Index("agent_events_created_at_brin_idx", created_at, postgresql_using="brin"),
    )
