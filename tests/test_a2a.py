import pytest
import time
from agents.shared_state import ExecutionState
from agents.agent_cards import AGENT_CARDS
from agents.a2a_directory import a2a_directory
from agents.consensus_engine import RemoteConsensusEngine
from agents.shared_state import SupplierResponse, TaskResult

def test_a2a_agent_discovery():
    # Verify Directory registers all five agents
    assert len(a2a_directory.list_agent_cards()) == 5
    
    # Check Supplier A Card details
    card = a2a_directory.get_agent_card("Supplier_A")
    assert card is not None
    assert card.identity.organization_name == "Supplier A Corp"
    assert card.identity.jurisdiction == "FR"
    assert "READ_EMISSIONS" in card.security_policies.required_permissions
    assert card.trust_metadata.initial_trust_score == 0.98
    assert card.health.status == "ACTIVE"

def test_a2a_permission_failures():
    state = ExecutionState(user_goal="Test A2A auth and permissions")
    
    # Try sending message without auth token -> Should raise ConnectionRefusedError (Unauthenticated)
    with pytest.raises(ConnectionRefusedError, match="Authentication Required"):
        a2a_directory.send_remote_message("Supplier_A", "Carbon Data Request", {}, state)
        
    # Authenticate with invalid token -> Should fail
    with pytest.raises(ConnectionRefusedError, match="Authentication Required"):
        a2a_directory.send_remote_message("Supplier_A", "Carbon Data Request", {"auth_token": "INVALID_TOKEN"}, state)
        
    # Try querying Supplier C without negotiation -> Should raise PermissionError (READ_SCOPE3 is required but missing)
    with pytest.raises(PermissionError, match="Access Denied"):
        a2a_directory.send_remote_message("Supplier_C", "Carbon Data Request", {"auth_token": "TOK_C"}, state)
        
    # Verify failures logged to audit trail
    assert any(e.get("type") == "A2A_FAILURE" and e.get("error") == "PermissionDenied" for e in state.a2a_audit_trail)

def test_a2a_negotiation():
    state = ExecutionState(user_goal="Test Supplier C negotiation")
    
    # 1. First query fails
    with pytest.raises(PermissionError, match="Access Denied"):
        a2a_directory.send_remote_message("Supplier_C", "Carbon Data Request", {"auth_token": "TOK_C_INIT"}, state)
        
    # 2. Propose negotiation
    negotiation_res = a2a_directory.send_remote_message("Supplier_C", "Negotiate", {}, state)
    assert negotiation_res.get("status") == "Negotiated"
    assert "READ_SCOPE3" in negotiation_res.get("granted_permissions")
    
    # 3. Second query succeeds
    query_res = a2a_directory.send_remote_message("Supplier_C", "Carbon Data Request", {}, state)
    assert query_res.get("disclosure_type") == "Estimated"
    assert query_res.get("emissions_tCO2") == 450.0

def test_a2a_trust_engine():
    # Verify trust model initialized on state in planner agent helper
    from agents.planner_agent import PlannerAgent
    from agents.shared_state import Task, TaskResult
    
    planner = PlannerAgent()
    state = ExecutionState(user_goal="Test trust scores")
    
    # Initialize scores
    task = Task(task_id="t1", assigned_agent="SupplierAgent", input_data={"remote_org": "Supplier_B"})
    res_success = TaskResult(task_id="t1", execution_status="COMPLETED", confidence=0.75)
    
    planner._update_agent_reputation(state, task, res_success)
    assert state.a2a_trust_scores["Supplier_B"] < 0.85 # trust decayed because of lower confidence estimate
    
    # Check failure triggers larger decay
    task_fail = Task(task_id="t2", assigned_agent="SupplierAgent", input_data={"remote_org": "Supplier_C"})
    res_fail = TaskResult(task_id="t2", execution_status="FAILED", error_message="Access Denied")
    
    planner._update_agent_reputation(state, task_fail, res_fail)
    assert state.a2a_trust_scores["Supplier_C"] < 0.75

def test_a2a_consensus_cross_validation():
    state = ExecutionState(user_goal="Test remote consensus cross validation")
    
    # Setup mock validation responses in task_history and state
    state.supplier_responses.append(SupplierResponse(
        supplier_id=1,
        supplier_name="Supplier A Corp",
        emission_data_status="Verified",
        reported_emissions=150.0,
        verification_source="Annual Audit"
    ))
    
    # Mock CA verification approved
    state.task_history["ca_verification"] = TaskResult(
        task_id="ca_verification",
        execution_status="COMPLETED",
        output_data={"certification_status": {"is_certified": True, "status": "APPROVED"}}
    )
    
    # Mock Transport verified
    state.task_history["transport_verification"] = TaskResult(
        task_id="transport_verification",
        execution_status="COMPLETED",
        output_data={"logistics_metrics": {"route_verified": True, "fuel_source": "Biodiesel"}}
    )
    
    engine = RemoteConsensusEngine()
    consensus = engine.generate_consensus(state)
    
    assert consensus["consensus_score"] == 1.0
    assert consensus["final_recommendation"] == "Approve carbon compliance filing"

def test_a2a_timeouts_failures():
    state = ExecutionState(user_goal="Test simulated timeout failures")
    
    # Trigger offline error
    with pytest.raises(ConnectionError, match="is offline"):
        a2a_directory.send_remote_message("Supplier_A", "Carbon Data Request", {"auth_token": "TOK", "simulate_failure": "OFFLINE"}, state)
        
    # Trigger timeout error
    with pytest.raises(TimeoutError, match="failed to respond"):
        a2a_directory.send_remote_message("Supplier_B", "Carbon Data Request", {"auth_token": "TOK", "simulate_failure": "TIMEOUT"}, state)
        
    # Trigger version mismatch
    with pytest.raises(ValueError, match="A2A Protocol Mismatch"):
        a2a_directory.send_remote_message("Supplier_C", "Carbon Data Request", {"auth_token": "TOK", "simulate_failure": "VERSION_MISMATCH"}, state)
