import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("CollaborationBus")

class AgentMessageType(str, Enum):
    INFORMATION_REQUEST = "Information Request"
    EVIDENCE_REQUEST = "Evidence Request"
    CLARIFICATION = "Clarification"
    RECOMMENDATION = "Recommendation"
    CRITIQUE = "Critique"
    CONFIDENCE_UPDATE = "Confidence Update"
    VERIFICATION_REQUEST = "Verification Request"
    TASK_PROPOSAL = "Task Proposal"
    ESCALATION = "Escalation"
    RESPONSE = "Response"
    CONSENSUS = "Consensus"

class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender: str
    recipient: str
    message_type: AgentMessageType
    content: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentRequest(AgentMessage):
    requested_keys: List[str] = Field(default_factory=list)

class AgentResponse(AgentMessage):
    request_id: str
    data: Dict[str, Any] = Field(default_factory=dict)

class AgentQuestion(AgentMessage):
    question_text: str = ""

class AgentCritique(AgentMessage):
    target_agent: str
    target_task_id: str
    critique_points: List[str] = Field(default_factory=list)

class AgentRecommendation(AgentMessage):
    recs: List[str] = Field(default_factory=list)
    follow_up_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    alternative_interpretations: List[str] = Field(default_factory=list)

class AgentConsensus(BaseModel):
    consensus_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    topic: str
    consensus_score: float
    supporting_agents: List[str] = Field(default_factory=list)
    disagreeing_agents: List[str] = Field(default_factory=list)
    final_recommendation: str
    evidence_summary: str

class AgentNegotiationEvent(BaseModel):
    negotiation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    topic: str
    agent_a: str
    agent_b: str
    initial_confidence_a: float
    initial_confidence_b: float
    final_confidence_a: float
    final_confidence_b: float
    negotiation_log: List[str] = Field(default_factory=list)
    resolved: bool = True

class AgentCommunicationBus:
    def __init__(self, state: Any, agents_registry: Dict[str, Any]):
        self.state = state
        self.agents = agents_registry

    def send(self, message: AgentMessage) -> Any:
        logger.info(f"[BUS] Routing message: {message.sender} -> {message.recipient} | Type: {message.message_type}")
        
        # Log to ExecutionState
        if not hasattr(self.state, "agent_conversations") or self.state.agent_conversations is None:
            self.state.agent_conversations = []
        self.state.agent_conversations.append(message)

        if isinstance(message, AgentRequest):
            if not hasattr(self.state, "agent_requests") or self.state.agent_requests is None:
                self.state.agent_requests = []
            self.state.agent_requests.append(message)
            if message.message_type in [AgentMessageType.INFORMATION_REQUEST, AgentMessageType.EVIDENCE_REQUEST]:
                if not hasattr(self.state, "knowledge_requests") or self.state.knowledge_requests is None:
                    self.state.knowledge_requests = []
                self.state.knowledge_requests.append(message)

        elif isinstance(message, AgentResponse):
            if not hasattr(self.state, "agent_responses") or self.state.agent_responses is None:
                self.state.agent_responses = []
            self.state.agent_responses.append(message)

        elif isinstance(message, AgentCritique):
            if not hasattr(self.state, "agent_critiques") or self.state.agent_critiques is None:
                self.state.agent_critiques = []
            self.state.agent_critiques.append(message)

        elif message.message_type == AgentMessageType.ESCALATION:
            if not hasattr(self.state, "escalations") or self.state.escalations is None:
                self.state.escalations = []
            self.state.escalations.append(message)

        # Dispatch
        recipient = message.recipient
        if recipient == "ALL":
            # Broadcast to all agents except sender
            responses = []
            for name, agent in self.agents.items():
                if name != message.sender and hasattr(agent, "handle_message"):
                    try:
                        resp = agent.handle_message(self.state, message, self)
                        if resp:
                            if not isinstance(resp, AgentMessage):
                                logger.warning(f"Agent {name} returned raw type {type(resp)} instead of AgentMessage.")
                                continue
                            responses.append(resp)
                            self.state.agent_conversations.append(resp)
                            if isinstance(resp, AgentResponse):
                                if not hasattr(self.state, "agent_responses") or self.state.agent_responses is None:
                                    self.state.agent_responses = []
                                self.state.agent_responses.append(resp)
                    except Exception as e:
                        logger.error(f"Error delivering broadcast to agent {name}: {e}")
            return responses

        elif recipient == "Planner":
            planner = self.agents.get("PlannerAgent")
            if planner and hasattr(planner, "handle_message"):
                resp = planner.handle_message(self.state, message, self)
                if resp:
                    self.state.agent_conversations.append(resp)
                    if isinstance(resp, AgentResponse):
                        if not hasattr(self.state, "agent_responses") or self.state.agent_responses is None:
                            self.state.agent_responses = []
                        self.state.agent_responses.append(resp)
                    return resp
            return None

        else:
            agent = self.agents.get(recipient)
            if agent and hasattr(agent, "handle_message"):
                try:
                    resp = agent.handle_message(self.state, message, self)
                    if resp:
                        if not isinstance(resp, AgentMessage):
                            logger.warning(f"Agent {recipient} returned raw type {type(resp)} instead of AgentMessage.")
                            return resp
                        self.state.agent_conversations.append(resp)
                        if isinstance(resp, AgentResponse):
                            if not hasattr(self.state, "agent_responses") or self.state.agent_responses is None:
                                self.state.agent_responses = []
                            self.state.agent_responses.append(resp)
                        return resp
                except Exception as e:
                    logger.error(f"Error delivering message to agent {recipient}: {e}")
            else:
                logger.warning(f"Recipient agent '{recipient}' not found in registry.")
            return None
