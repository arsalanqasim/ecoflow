from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from agents.collaboration import (
    AgentMessage, AgentRequest, AgentResponse, AgentCritique,
    AgentConsensus, AgentNegotiationEvent
)

class CarbonResult(BaseModel):
    shipment_id: int
    emission_tCO2: float
    method: str
    confidence: float = 1.0

class ComplianceResult(BaseModel):
    emission_id: int
    tariff_due_eur: float
    compliance_status: str
    audit_note: str

class OptimizationResult(BaseModel):
    shipment_id: int
    original_emissions: float
    optimized_emissions: float
    alternative_carrier: str
    alternative_route: str
    savings_tCO2: float
    savings_percent: float

class SupplierResponse(BaseModel):
    supplier_id: int
    supplier_name: str
    emission_data_status: str  # "Missing", "Estimated", "Verified", "Unknown"
    reported_emissions: Optional[float] = None
    verification_source: Optional[str] = None

class Task(BaseModel):
    task_id: str
    assigned_agent: str
    dependencies: List[str] = []
    priority: int = 1
    confidence: float = 1.0
    validation_rules: List[str] = []
    expected_outputs: List[str] = []
    retry_limit: int = 3
    retry_count: int = 0
    execution_status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    input_data: Dict[str, Any] = {}
    output_data: Dict[str, Any] = {}
    error_message: Optional[str] = None
    execution_time: float = 0.0

class TaskResult(BaseModel):
    task_id: str
    execution_status: str
    output_data: Dict[str, Any] = {}
    error_message: Optional[str] = None
    execution_time: float = 0.0
    confidence: float = 1.0
    risks: List[str] = []
    recommendations: List[str] = []
    suggested_follow_up_tasks: List[Dict[str, Any]] = []
    need_planner_intervention: bool = False

class AgentDecision(BaseModel):
    decision: str  # "CONTINUE", "RETRY", "SKIP_DOWNSTREAM", "INSERT_TASKS", "TERMINATE", "SKIP"
    reasoning: str
    confidence: float = 1.0
    alternative_options: List[str] = []
    next_recommended_agent: Optional[str] = None

class Goal(BaseModel):
    goal_id: str
    user_intent: str
    desired_outcome: str
    success_criteria: List[str] = []
    current_progress: str = ""
    completion_percentage: float = 0.0
    remaining_unknowns: List[str] = []
    confidence: float = 1.0
    constraints: List[str] = []
    assumptions: List[str] = []
    risks: List[str] = []

class PlanningHypothesis(BaseModel):
    hypothesis_text: str
    assumed_steps: List[str] = []
    expected_dependencies: Dict[str, List[str]] = {}
    confidence: float = 1.0

class HypothesisRegistry(BaseModel):
    hypotheses: List[PlanningHypothesis] = []
    selected_hypothesis_index: int = 0
    discarded_hypotheses: List[PlanningHypothesis] = []

class Uncertainty(BaseModel):
    missing_information: List[str] = []
    incomplete_documents: List[str] = []
    estimated_values: List[str] = []
    low_confidence_outputs: List[str] = []
    conflicting_evidence: List[str] = []
    unknown_supplier_data: List[str] = []

class Observation(BaseModel):
    task_id: str
    result_summary: Dict[str, Any] = {}
    confidence: float = 1.0
    duration: float = 0.0
    unexpected_findings: List[str] = []
    warnings: List[str] = []
    risks: List[str] = []
    recommendations: List[str] = []
    planner_intervention_advised: bool = False
    suggested_next_action: str = ""

class DecisionJournalEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    decision: str  # "CONTINUE", "RETRY", "SKIP", "INSERT_TASKS", "TERMINATE"
    reason: str
    evidence: str
    confidence: float = 1.0
    alternative_considered: List[str] = []
    expected_outcome: str

class ExecutionTimelineEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_name: str
    action: str
    duration: float = 0.0
    message: str

class ExecutionState(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }
    
    run_id: Optional[str] = None
    
    # Runtime communication bus (not serialized/stored in DB)
    bus: Optional[Any] = Field(default=None, exclude=True)

    # Collaborative timeline models
    agent_conversations: List[Any] = Field(default_factory=list)
    agent_requests: List[Any] = Field(default_factory=list)
    agent_responses: List[Any] = Field(default_factory=list)
    agent_critiques: List[Any] = Field(default_factory=list)
    consensus_events: List[AgentConsensus] = Field(default_factory=list)
    negotiation_events: List[AgentNegotiationEvent] = Field(default_factory=list)
    knowledge_requests: List[Any] = Field(default_factory=list)
    escalations: List[Any] = Field(default_factory=list)

    # MCP session and tracing models
    mcp_session: Optional[Any] = None
    mcp_discovery_events: List[Any] = Field(default_factory=list)
    mcp_selection_decisions: List[Any] = Field(default_factory=list)
    mcp_tool_chains: List[Any] = Field(default_factory=list)
    mcp_fallback_events: List[Any] = Field(default_factory=list)
    mcp_validation_events: List[Any] = Field(default_factory=list)
    mcp_performance_metrics: Dict[str, Any] = Field(default_factory=dict)

    # A2A Session and Tracing
    a2a_sessions: Dict[str, Any] = Field(default_factory=dict)
    a2a_audit_trail: List[Any] = Field(default_factory=list)
    a2a_trust_scores: Dict[str, float] = Field(default_factory=dict)

    # Reflection & Self-Correction timeline structures
    reflection_events: List[Any] = Field(default_factory=list)
    quality_scores: Dict[str, float] = Field(default_factory=dict)
    recovery_actions: List[Any] = Field(default_factory=list)
    reflection_memory: List[Any] = Field(default_factory=list)

    user_goal: str
    uploaded_documents: List[str] = []
    current_tasks: List[Task] = []
    execution_graph: Dict[str, Any] = {"nodes": [], "edges": []}
    execution_timeline: List[ExecutionTimelineEvent] = []
    agent_decisions: List[AgentDecision] = []
    confidence_history: List[float] = []
    task_history: Dict[str, TaskResult] = {}
    planner_notes: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    overall_confidence: float = 1.0
    current_status: str = "PENDING"
    
    # Upgraded Executive Planner models
    goal_model: Optional[Goal] = None
    planning_hypothesis: Optional[HypothesisRegistry] = None
    uncertainty_model: Optional[Uncertainty] = None
    decision_journal: List[DecisionJournalEntry] = []
    observations: List[Observation] = []
    execution_strategy: str = "Maximum Accuracy"
    reasoning_iterations: int = 0
    replanning_count: int = 0
    inserted_tasks_count: int = 0
    skipped_tasks_count: int = 0
    estimated_remaining_work: str = "TBD"
    planner_learning: Dict[str, Any] = Field(default_factory=lambda: {
        "unreliable_agents": {},
        "repeated_failures": 0,
        "missing_supplier_data_counts": 0,
        "agent_latencies": {},
        "agent_costs": 0.0
    })

    # Typed worker results stored in execution state
    carbon_results: List[CarbonResult] = []
    compliance_results: List[ComplianceResult] = []
    optimization_results: List[OptimizationResult] = []
    supplier_responses: List[SupplierResponse] = []

class ExecutionReport(BaseModel):
    goal: str
    status: str
    total_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    skipped_tasks: int
    retries_count: int
    agent_costs: float = 0.0
    execution_time: float
    overall_confidence: float
    reasoning_summary: str
