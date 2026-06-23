from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SpeechSegment(BaseModel):
    text: str = Field(..., min_length=1)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class SpeechAnalysisRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    utterance_started_at: datetime | None = None
    utterance_ended_at: datetime | None = None
    response_requested_at: datetime | None = None
    response_started_at: datetime | None = None
    segments: list[SpeechSegment] = Field(default_factory=list)


class RepeatedExpression(BaseModel):
    expression: str
    count: int
    type: str


class SpeechPace(BaseModel):
    words_per_minute: float
    syllables_per_second: float
    label: str


class ResponseLatency(BaseModel):
    seconds: float | None
    label: str


class SpeechAnalysisResponse(BaseModel):
    transcript: str
    duration_seconds: float
    word_count: int
    syllable_count: int
    pace: SpeechPace
    repeated_expressions: list[RepeatedExpression]
    repetition_score: float
    response_latency: ResponseLatency
    flags: list[str]
    coaching_tips: list[str]


class ConversationMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class SttToLlmRequest(BaseModel):
    session_id: str = Field(default="local-session")
    turn_id: str | None = None
    stt_result: SpeechAnalysisRequest
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    child_profile: dict[str, Any] = Field(default_factory=dict)


class LlmModuleResponse(BaseModel):
    therapist_reply: str
    next_prompt: str
    coaching_cues: list[str] = Field(default_factory=list)
    model_name: str = "local-rule-model"


class SttToLlmResponse(BaseModel):
    session_id: str
    turn_id: str | None = None
    analysis: SpeechAnalysisResponse
    llm: LlmModuleResponse


class SttPipelineResponse(BaseModel):
    session_id: str
    turn_id: str
    transcript: str
    stt_model: str
    stt_time_seconds: float
    analysis: SpeechAnalysisResponse
    llm: LlmModuleResponse
    audio_url: str | None = None
    emotion: str = "neutral"
    avatar_state: str = "speaking"


class SessionTurn(BaseModel):
    session_id: str
    turn_id: str
    transcript: str
    analysis: SpeechAnalysisResponse
    llm: LlmModuleResponse
    stt_model: str | None = None
    stt_time_seconds: float | None = None
    created_at: datetime


class SessionLogResponse(BaseModel):
    session_id: str
    turns: list[SessionTurn]


class WebSocketTurnRequest(BaseModel):
    transcript: str = Field(..., min_length=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    response_requested_at: datetime | None = None
    response_started_at: datetime | None = None
    turn_id: str | None = None


class SessionCreateRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    child_id: str = Field(default="anonymous", min_length=1)


class SessionEndRequest(BaseModel):
    status: str = Field(default="completed", pattern="^(completed|interrupted)$")


class SessionResponse(BaseModel):
    session_id: str
    child_id: str
    scenario_id: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str


class WebSocketTurnPayload(BaseModel):
    text: str = Field(..., min_length=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    response_time_ms: int | None = Field(default=None, ge=0)


class WebSocketClientEvent(BaseModel):
    type: str = Field(pattern="^end_utterance$")
    session_id: str
    turn_id: int
    payload: WebSocketTurnPayload
