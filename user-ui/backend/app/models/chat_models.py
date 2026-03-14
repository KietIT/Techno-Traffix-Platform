"""
Chat Models - Data structures for chat request/response.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class MessageRole(Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """Represents a single chat message."""

    role: MessageRole
    content: str
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        return cls(
            role=MessageRole(data.get("role", "user")),
            content=data.get("content", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
        )


@dataclass
class ChatRequest:
    """Request payload for chat endpoint."""

    message: str
    session_id: Optional[str] = None
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    location: Optional[Dict[str, float]] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate the request payload."""
        if not self.message or not self.message.strip():
            return False, "Message cannot be empty"

        if len(self.message) > 2000:
            return False, "Message too long (max 2000 characters)"

        return True, None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatRequest":
        location = data.get("location")
        if location and isinstance(location, dict):
            lat = location.get("lat")
            lng = location.get("lng")
            if lat is not None and lng is not None:
                location = {"lat": float(lat), "lng": float(lng)}
            else:
                location = None
        else:
            location = None

        return cls(
            message=data.get("message", ""),
            session_id=data.get("session_id"),
            chat_history=data.get("chat_history", []),
            location=location,
        )


@dataclass
class SourceReference:
    """Reference to a source used in the response."""

    id: str
    content: str
    source: str
    category: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "category": self.category,
            "relevance_score": self.relevance_score,
            "metadata": self.metadata,
        }


@dataclass
class ChatResponse:
    """Response payload for chat endpoint."""

    content: str
    is_ai_generated: bool
    topic_valid: bool
    session_id: Optional[str] = None
    sources: List[SourceReference] = field(default_factory=list)
    category: Optional[str] = None
    confidence: float = 1.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "is_ai_generated": self.is_ai_generated,
            "topic_valid": self.topic_valid,
            "session_id": self.session_id,
            "sources": [s.to_dict() for s in self.sources] if self.sources else [],
            "category": self.category,
            "confidence": self.confidence,
            "error": self.error,
        }

    @classmethod
    def error_response(cls, error_message: str) -> "ChatResponse":
        """Create an error response."""
        return cls(
            content="Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại sau.",
            is_ai_generated=False,
            topic_valid=False,
            error=error_message,
        )

    @classmethod
    def off_topic_response(cls, message: str, category: str = "off_topic") -> "ChatResponse":
        """Create a response for off-topic messages."""
        return cls(content=message, is_ai_generated=False, topic_valid=False, category=category)


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        return result
