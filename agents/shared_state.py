from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

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

class AgentDecision(BaseModel):
    decision: str  # "CONTINUE", "RETRY", "SKIP_DOWNSTREAM", "INSERT_TASKS", "TERMINATE"
    reasoning: str
    confidence: float = 1.0
    alternative_options: List[str] = []
    next_recommended_agent: Optional[str] = None

class ExecutionTimelineEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_name: str
    action: str
    duration: float = 0.0
    message: str

class ExecutionState(BaseModel):
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
