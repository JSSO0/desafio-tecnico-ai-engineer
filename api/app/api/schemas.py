from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthzResponse(BaseModel):
    status: Literal["ok"] = "ok"


class HealthChecks(BaseModel):
    storage: bool
    database: bool
    llm_configured: bool


class ReadyzResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: HealthChecks
    provider: str
    model: str


class MetaResponse(BaseModel):
    provider: str
    model: str
    llm_configured: bool
    prompt_version: str
    app_version: str


class SessionCreated(BaseModel):
    access_token: str = Field(description="Token opaco. Envie em Authorization: Bearer <token>.")
    token_type: str = "bearer"
    expires_at: str
    budget_tokens: int
    session_id: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="Mensagem do cliente.")


class UsageResponse(BaseModel):
    tokens_in: int
    tokens_out: int
    tokens_total: int
    turnos: int
    budget_tokens: int
    remaining: int


class MessageOut(BaseModel):
    message_id: int
    role: str
    content: str
    guard: str | None = None
    created_at: str
    latency_ms: int | None = None


class MessagesResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]


class ErrorResponse(BaseModel):
    code: str
    message: str
