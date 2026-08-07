import sqlalchemy as sa
from database import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    repo_url = Column(String(500), nullable=False)
    repo_full_name = Column(String(200), nullable=False)
    weighted_total = Column(sa.Float, default=0.0)
    score_positioning = Column(Integer, default=0)
    score_differentiation = Column(Integer, default=0)
    score_moat = Column(Integer, default=0)
    score_engineering = Column(Integer, default=0)
    score_sustainability = Column(Integer, default=0)
    overall_summary = Column(Text, default="")
    top_strengths = Column(Text, default="[]")
    top_weaknesses = Column(Text, default="[]")
    report_markdown = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), default="custom")
    api_key = Column(String(500), default="")
    base_url = Column(String(500), default="")
    model = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
