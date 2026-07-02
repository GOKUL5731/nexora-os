"""
Conversation Context Module
Tracks multi-turn conversation context for better understanding
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class ConversationTurn:
    """Represents a single turn in a conversation"""
    user_input: str
    system_response: str
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)
    sentiment: Optional[str] = None
    intent: Optional[str] = None


@dataclass(slots=True)
class ConversationContext:
    """Manages conversation context"""
    session_id: str
    turns: deque[ConversationTurn] = field(default_factory=lambda: deque(maxlen=20))
    current_topic: Optional[str] = None
    entities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    
    def add_turn(self, user_input: str, system_response: str, context: dict[str, Any] = None) -> None:
        """Add a conversation turn"""
        turn = ConversationTurn(
            user_input=user_input,
            system_response=system_response,
            timestamp=time.time(),
            context=context or {},
            sentiment=context.get("sentiment") if context else None,
            intent=context.get("intent") if context else None
        )
        self.turns.append(turn)
        self.last_active = time.time()
    
    def get_recent_turns(self, count: int = 5) -> list[ConversationTurn]:
        """Get recent conversation turns"""
        return list(self.turns)[-count:]
    
    def get_context_summary(self) -> dict[str, Any]:
        """Get summary of conversation context"""
        return {
            "session_id": self.session_id,
            "turn_count": len(self.turns),
            "current_topic": self.current_topic,
            "entities": self.entities,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "recent_turns": [
                {
                    "user_input": turn.user_input,
                    "system_response": turn.system_response,
                    "timestamp": turn.timestamp,
                    "sentiment": turn.sentiment,
                    "intent": turn.intent
                }
                for turn in self.get_recent_turns(3)
            ]
        }
    
    def update_topic(self, topic: str) -> None:
        """Update current conversation topic"""
        self.current_topic = topic
        self.last_active = time.time()
    
    def add_entity(self, key: str, value: Any) -> None:
        """Add an entity to context"""
        self.entities[key] = value
        self.last_active = time.time()
    
    def get_entity(self, key: str, default: Any = None) -> Any:
        """Get an entity from context"""
        return self.entities.get(key, default)
    
    def clear_entities(self) -> None:
        """Clear all entities"""
        self.entities.clear()
        self.last_active = time.time()


class ContextManager:
    """Manages multiple conversation contexts"""
    
    def __init__(self, max_sessions: int = 100) -> None:
        """
        Initialize context manager
        
        Args:
            max_sessions: Maximum number of active sessions
        """
        self.max_sessions = max_sessions
        self.sessions: dict[str, ConversationContext] = {}
        self.current_session: Optional[str] = None
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new conversation session
        
        Args:
            session_id: Optional session ID (will generate if not provided)
            
        Returns:
            Session ID
        """
        import uuid
        if session_id is None:
            session_id = uuid.uuid4().hex
        
        if session_id in self.sessions:
            return session_id
        
        # Remove oldest session if at capacity
        if len(self.sessions) >= self.max_sessions:
            oldest = min(self.sessions.items(), key=lambda x: x[1].created_at)[0]
            del self.sessions[oldest]
        
        self.sessions[session_id] = ConversationContext(session_id=session_id)
        self.current_session = session_id
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationContext]:
        """Get a conversation session"""
        return self.sessions.get(session_id)
    
    def set_current_session(self, session_id: str) -> bool:
        """Set the current active session"""
        if session_id in self.sessions:
            self.current_session = session_id
            return True
        return False
    
    def get_current_session(self) -> Optional[ConversationContext]:
        """Get the current active session"""
        if self.current_session:
            return self.sessions.get(self.current_session)
        return None
    
    def add_turn(self, user_input: str, system_response: str, context: dict[str, Any] = None, session_id: str = None) -> None:
        """Add a turn to a conversation session"""
        target_session = session_id or self.current_session
        
        if target_session is None:
            target_session = self.create_session()
        
        if target_session not in self.sessions:
            self.create_session(target_session)
        
        self.sessions[target_session].add_turn(user_input, system_response, context)
    
    def get_context_for_response(self, session_id: str = None) -> dict[str, Any]:
        """Get context for generating a response"""
        target_session = session_id or self.current_session
        
        if target_session is None or target_session not in self.sessions:
            return {}
        
        session = self.sessions[target_session]
        recent_turns = session.get_recent_turns(5)
        
        return {
            "session_id": session.session_id,
            "current_topic": session.current_topic,
            "entities": session.entities,
            "recent_conversation": [
                {
                    "user": turn.user_input,
                    "assistant": turn.system_response,
                    "sentiment": turn.sentiment,
                    "intent": turn.intent
                }
                for turn in recent_turns
            ],
            "turn_count": len(session.turns)
        }
    
    def cleanup_old_sessions(self, max_age_hours: float = 24.0) -> int:
        """
        Clean up old sessions
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of sessions cleaned up
        """
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        to_remove = []
        
        for session_id, session in self.sessions.items():
            if now - session.last_active > max_age_seconds:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            del self.sessions[session_id]
            if self.current_session == session_id:
                self.current_session = None
        
        return len(to_remove)
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions"""
        return [session.get_context_summary() for session in self.sessions.values()]


# Global context manager instance
global_context_manager = ContextManager()


def add_conversation_turn(user_input: str, system_response: str, context: dict[str, Any] = None) -> None:
    """Add a conversation turn using the global manager"""
    global_context_manager.add_turn(user_input, system_response, context)


def get_conversation_context() -> dict[str, Any]:
    """Get conversation context using the global manager"""
    return global_context_manager.get_context_for_response()


def create_conversation_session(session_id: str = None) -> str:
    """Create a conversation session using the global manager"""
    return global_context_manager.create_session(session_id)
