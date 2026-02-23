from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=3000)


class ChatResponse(BaseModel):
    user_id: str
    extracted_scores: Dict[str, Any]
    completed_scores: Dict[str, Any]
    adiga_input: Dict[str, str]
    estimated_subjects: List[str]
    db_record: Dict[str, str]
    agent_trace: List[str]


class ProfileResponse(BaseModel):
    user_id: str
    adiga_payload: Dict[str, Any]
    extracted_scores: Dict[str, Any]
    completed_scores: Dict[str, Any]
    estimated_subjects: List[str]
    latest_message: str
    updated_at: str

