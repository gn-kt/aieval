from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    api_key: str
    is_active: bool


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str
    rate_limit_remaining: int | None = None


class SourceItem(BaseModel):
    file: str
    chunk: int
    score: float


class RAGResult(BaseModel):
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Any = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


class TaskListItem(BaseModel):
    task_id: str
    question: str
    status: str
    created_at: str | None = None


class PaginatedTasksResponse(BaseModel):
    items: list[TaskListItem]
    total: int
    page: int
    size: int
    pages: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ChatMessage(BaseModel):
    role: str
    content: str


class SessionResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


class EvaluateRequest(BaseModel):
    repo_url: str
    description: str | None = None
    n_competitors: int = Field(5, ge=1, le=10)


class DimensionScore(BaseModel):
    name: str
    name_en: str
    weight: float
    score: int
    max_score: int
    evidence: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    scores: dict[str, DimensionScore]
    weighted_total: float
    overall_summary: str
    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)
    veto: dict = Field(default_factory=dict)
    project_meta: dict = Field(default_factory=dict)
    competitors_meta: list[dict] = Field(default_factory=list)
    report_markdown: str = ""


class EvaluateResponse(TaskCreateResponse):
    pass


class AdvisorAskRequest(BaseModel):
    repo_url: str = ""
    question: str
    history: list[dict] | None = None
    eval_data: dict | None = None


class AdvisorAskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)


class TextEvaluateRequest(BaseModel):
    description: str
    n_competitors: int = Field(3, ge=1, le=5)
