from pydantic import BaseModel, Field


class TaskCreateResponse(BaseModel):
    task_id: str
    status: str


class EvaluateRequest(BaseModel):
    repo_url: str
    description: str | None = None
    n_competitors: int = Field(5, ge=1, le=10)


class TextEvaluateRequest(BaseModel):
    description: str
    n_competitors: int = Field(3, ge=1, le=5)


class AdvisorAskRequest(BaseModel):
    repo_url: str = ""
    question: str
    history: list[dict] | None = None
    eval_data: dict | None = None


class AdvisorAskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
