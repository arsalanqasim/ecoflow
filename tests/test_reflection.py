import pytest
import time
from agents.shared_state import ExecutionState, Task, TaskResult, SupplierResponse
from agents.reflection_agent import ReflectionAgent
from agents.planner_agent import PlannerAgent

def test_reflection_quality_scoring():
    state = ExecutionState(user_goal="Test Quality Scores")
    agent = ReflectionAgent()
    
    # Setup mock task history
    state.task_history["task1"] = TaskResult(task_id="task1", execution_status="COMPLETED", confidence=0.90)
    state.task_history["task2"] = TaskResult(task_id="task2", execution_status="FAILED", confidence=0.00)
    
    # Setup mock supplier responses
    state.supplier_responses = [
        SupplierResponse(supplier_id=1, supplier_name="A Corp", emission_data_status="Verified", reported_emissions=100.0, verification_source="Audit"),
        SupplierResponse(supplier_id=2, supplier_name="B Corp", emission_data_status="Estimated", reported_emissions=200.0, verification_source="Estimate")
    ]
    
    # Run reflection calculation
    agent._calculate_quality_scores(state)
    
    # Assertions
    scores = state.quality_scores
    assert scores["Execution Quality"] == 0.50  # 1 out of 2 completed
    assert scores["Evidence Quality"] == 0.50   # 1 out of 2 verified
    assert "Overall System Quality" in scores

def test_reflection_failure_classification():
    state = ExecutionState(user_goal="Test Failure Classification")
    agent = ReflectionAgent()
    
    # Scenario: Timeout Error
    state.task_history["task_timeout"] = TaskResult(
        task_id="task_timeout",
        execution_status="FAILED",
        error_message="A2A request timed out after 5.0 seconds"
    )
    report_timeout = agent._reflect_on_task(state, "task_timeout")
    assert report_timeout.failure_classification == "Communication Error"
    assert report_timeout.failure_severity == "HIGH"
    assert report_timeout.recovery_recommendation == "Retry Task"

    # Scenario: Permission Error
    state.task_history["task_auth"] = TaskResult(
        task_id="task_auth",
        execution_status="FAILED",
        error_message="Access Denied: Required permission 'READ_SCOPE3' is not granted."
    )
    report_auth = agent._reflect_on_task(state, "task_auth")
    assert report_auth.failure_classification == "Permission Limitation"
    assert report_auth.recovery_recommendation == "Insert New Task"

def test_reflection_root_cause_analysis():
    state = ExecutionState(user_goal="Test Root Cause")
    agent = ReflectionAgent()
    
    state.task_history["t1"] = TaskResult(
        task_id="t1",
        execution_status="FAILED",
        error_message="Database lock conflict"
    )
    report = agent._reflect_on_task(state, "t1")
    assert report.immediate_cause == "Database lock conflict"
    assert report.affected_agents == ["t1"]

def test_reflection_consensus_recalibration():
    state = ExecutionState(user_goal="Test Consensus Recalibration")
    agent = ReflectionAgent()
    
    # Consensus report generated
    state.planner_learning["consensus_report"] = {
        "consensus_score": 0.90,
        "cross_validations": ["Supplier A Corp data verified."]
    }
    
    # 1. Supplier B is estimated and CA check is missing -> Expect confidence to decay to 74%
    state.supplier_responses = [
        SupplierResponse(supplier_id=1, supplier_name="Supplier A Corp", emission_data_status="Verified", reported_emissions=100.0),
        SupplierResponse(supplier_id=2, supplier_name="Supplier B Corp", emission_data_status="Estimated", reported_emissions=200.0)
    ]
    
    report1 = agent._reflect_on_consensus(state)
    assert report1.failure_classification == "Weak Evidence"
    assert report1.confidence_recalibration == 0.74
    assert report1.recovery_recommendation == "Insert New Task"
    
    # 2. Supplier B has approved certificate in ca_verification history -> Expect confidence to recalibrate to 92%
    state.task_history["ca_verification"] = TaskResult(
        task_id="ca_verification",
        execution_status="COMPLETED",
        output_data={"certification_status": {"is_certified": True, "status": "APPROVED"}}
    )
    
    report2 = agent._reflect_on_consensus(state)
    assert report2.confidence_recalibration == 0.92
    assert report2.recovery_recommendation == "Accept"

def test_recovery_planner_insertion():
    planner = PlannerAgent()
    state = ExecutionState(user_goal="Test Recovery Insertion")
    
    # Set initial task list including run_calc and run_consensus
    calc_task = Task(task_id="run_calc", assigned_agent="CarbonCalculationAgent", dependencies=["run_consensus"])
    consensus_task = Task(task_id="run_consensus", assigned_agent="SupplierAgent")
    state.current_tasks = [calc_task, consensus_task]
    state.execution_graph = {
        "nodes": ["run_calc", "run_consensus"],
        "edges": [{"from": "run_consensus", "to": "run_calc"}]
    }
    
    # Setup consensus results that trigger reflection decay
    state.supplier_responses = [
        SupplierResponse(supplier_id=1, supplier_name="Supplier A Corp", emission_data_status="Verified", reported_emissions=100.0),
        SupplierResponse(supplier_id=2, supplier_name="Supplier B Corp", emission_data_status="Estimated", reported_emissions=200.0)
    ]
    state.planner_learning["consensus_report"] = {
        "consensus_score": 0.90,
        "cross_validations": ["Supplier A Corp verified"]
    }
    
    # Execute evaluate_task_result on run_consensus
    consensus_res = TaskResult(
        task_id="run_consensus",
        execution_status="COMPLETED",
        output_data={"consensus_report": state.planner_learning["consensus_report"]}
    )
    
    decision = planner.evaluate_task_result(state, consensus_task, consensus_res)
    
    # Assertions
    assert decision.decision == "INSERT_TASKS"
    assert any(t.task_id == "ca_verification_supplier_b" for t in state.current_tasks)
    assert any(t.task_id == "run_consensus_retry" for t in state.current_tasks)
    assert state.inserted_tasks_count == 1
    
    # Confirm downstream dependencies rewired to consensus retry
    for t in state.current_tasks:
        if t.task_id == "run_calc":
            assert "run_consensus_retry" in t.dependencies
            assert "run_consensus" not in t.dependencies
