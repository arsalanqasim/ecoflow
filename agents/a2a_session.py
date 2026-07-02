import uuid
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class A2AMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    recipient: str
    request_type: str  # "Carbon Data Request", "Evidence Request", "Negotiate", etc.
    payload: Dict[str, Any]
    timestamp: float = Field(default_factory=time.time)

class RemoteAgentSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    remote_org: str
    auth_state: str = "UNAUTHENTICATED"  # UNAUTHENTICATED, AUTHENTICATED, EXPIRED
    permission_grants: List[str] = Field(default_factory=list)
    negotiation_state: str = "IDLE"  # IDLE, INITIATED, NEGOTIATING, COUNTER_PROPOSING, AGREED, DISAGREED
    conversation_history: List[A2AMessage] = Field(default_factory=list)
    failures_count: int = 0
    retries_count: int = 0
    created_at: float = Field(default_factory=time.time)
    auth_token: Optional[str] = None
    
    def authenticate(self, client_org: str, auth_token: str) -> bool:
        if auth_token == "EXPIRED_TOKEN":
            self.auth_state = "EXPIRED"
            self.auth_token = auth_token
            return False
        elif auth_token == "INVALID_TOKEN":
            self.auth_state = "UNAUTHENTICATED"
            self.auth_token = None
            return False
        else:
            self.auth_state = "AUTHENTICATED"
            self.auth_token = auth_token
            # Default base permissions granted on successful auth
            if "READ_EMISSIONS" not in self.permission_grants:
                self.permission_grants.append("READ_EMISSIONS")
            return True

    def check_permission(self, permission: str) -> bool:
        if self.auth_state == "EXPIRED":
            raise ConnectionRefusedError("Authentication Expired: Token has expired.")
        if self.auth_state != "AUTHENTICATED":
            raise ConnectionRefusedError("Authentication Required: Session is unauthenticated.")
        return permission in self.permission_grants

    def log_message(self, sender: str, recipient: str, request_type: str, payload: Dict[str, Any]):
        msg = A2AMessage(
            sender=sender,
            recipient=recipient,
            request_type=request_type,
            payload=payload
        )
        self.conversation_history.append(msg)
        return msg
