"""SQLAlchemy ORM models for CISCO-EN CLI Mapping Agent."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, func
)
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector

from src.config import EMBEDDING_DIM


class Base(DeclarativeBase):
    pass


class CLIMapping(Base):
    __tablename__ = "cli_mappings"

    id                  = Column(Integer, primary_key=True, autoincrement=True)

    # Classification
    tag                 = Column(String(20), nullable=False, index=True)
    functional_intent   = Column(Text, nullable=False)

    # Cisco OS columns
    cisco_ios           = Column(Text, default="")
    cisco_iosxe         = Column(Text, default="")
    cisco_nxos          = Column(Text, default="")

    # Extreme Networks OS columns
    extreme_exos        = Column(Text, default="")
    extreme_voss        = Column(Text, default="")
    extreme_slxos       = Column(Text, default="")

    # Negation / undo forms
    negation_cisco      = Column(Text, default="")
    negation_en         = Column(Text, default="")

    # Context & provenance
    notes               = Column(Text, default="")
    source_ref          = Column(String(255), default="")
    page_ref            = Column(String(100), default="")

    # RAG vector embedding
    embedding           = Column(Vector(EMBEDDING_DIM))

    # Quality
    confidence          = Column(Float, default=1.0)
    is_verified         = Column(Boolean, default=False)

    # Timestamps
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(),
                                 onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "tag":              self.tag,
            "functional_intent": self.functional_intent,
            "cisco_ios":        self.cisco_ios or "",
            "cisco_iosxe":      self.cisco_iosxe or "",
            "cisco_nxos":       self.cisco_nxos or "",
            "extreme_exos":     self.extreme_exos or "",
            "extreme_voss":     self.extreme_voss or "",
            "extreme_slxos":    self.extreme_slxos or "",
            "negation_cisco":   self.negation_cisco or "",
            "negation_en":      self.negation_en or "",
            "notes":            self.notes or "",
            "source_ref":       self.source_ref or "",
            "page_ref":         self.page_ref or "",
            "confidence":       self.confidence,
            "is_verified":      self.is_verified,
        }

    def __repr__(self) -> str:
        return f"<CLIMapping id={self.id} tag={self.tag!r} intent={self.functional_intent[:40]!r}>"


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    source_type     = Column(String(20), nullable=False)   # csv|pdf|web_crawl|ai_fill
    source_name     = Column(String(255), nullable=False)
    rows_added      = Column(Integer, default=0)
    rows_updated    = Column(Integer, default=0)
    started_at      = Column(DateTime(timezone=True), server_default=func.now())
    completed_at    = Column(DateTime(timezone=True))
    status          = Column(String(20), default="running")  # running|completed|failed
    error_message   = Column(Text)


class QueryLog(Base):
    __tablename__ = "query_log"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    query_text      = Column(Text, nullable=False)
    tag_filter      = Column(String(20))
    os_filter       = Column(String(30))
    results_count   = Column(Integer)
    top_similarity  = Column(Float)
    response_time_ms = Column(Integer)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class CrawlerURL(Base):
    __tablename__ = "crawler_urls"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    url             = Column(Text, unique=True, nullable=False)
    os_target       = Column(String(30))
    last_crawled    = Column(DateTime(timezone=True))
    status          = Column(String(20), default="pending")
    rows_produced   = Column(Integer, default=0)
    http_status     = Column(Integer)
    error_message   = Column(Text)
