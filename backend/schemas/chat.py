"""Chat Request/Response Schemas"""

from typing import List, Literal

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_history: List[ChatTurn] = Field(default_factory=list)
