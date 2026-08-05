import uuid

import sqlalchemy as sa
from database import Base
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    api_key = Column(String(64), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    is_active = Column(Boolean, default=True, server_default=sa.text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    module = Column(String(50), nullable=False)
    model = Column(String(50), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SentimentPost(Base):
    __tablename__ = "sentiment_posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    content = Column(Text, default="")
    platform = Column(String(50), nullable=False)
    keyword = Column(String(200), nullable=False, index=True)
    publish_time = Column(String(50), default="")
    engagement = Column(Text, default="{}")
    collected_at = Column(DateTime(timezone=True), server_default=func.now())


class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("sentiment_posts.id"), unique=True, nullable=False, index=True)
    sentiment = Column(String(20), nullable=False)
    score = Column(sa.Float, default=0.5)
    reason = Column(String(200), default="")
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())


class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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
