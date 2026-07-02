import pytest
import time
from datetime import datetime
from agents.shared_state import ExecutionState, Task, TaskResult, Goal, PlanningHypothesis, HypothesisRegistry
from agents.planner_agent import PlannerAgent
from agents.engine import ExecutionEngine

def test_multi_hypothesis_and_strategy():
    planner = PlannerAgent()
    agents_metadata = [
        {"agent_name": "CarbonCalculationAgent", "capabilities": ["get_historical_emissions", "run_forecast"]},
        {"agent_name": "ConversationAgent", "capabilities": ["generate_response"]}
    ]
    
    state = planner.plan_goal("forecast emissions", agents_metadata)
    
    # Verify Goal model created
    assert state.goal_model is not None
    assert state.goal_model.goal_id == "goal_forecast"
    assert "Forecast emissions" in state.goal_model.user_intent or "forecast" in state.goal_model.user_intent.lower()
    
    # Verify Hypothesis registry
    assert state.planning_hypothesis is not None
    assert len(state.planning_hypothesis.hypotheses) > 0
    assert state.planning_hypothesis.selected_hypothesis_index == 0
    
    # Verify selected strategy
    assert state.execution_strategy == "Maximum Accuracy"
    
    # Verify initial decision journal entry
    assert len(state.decision_journal) == 1
    assert state.decision_journal[0].decision == "PLAN_INITIALIZED"
    assert len(state.decision_journal[0].alternative_considered) >= 0

def test_collaborative_outputs_and_dynamic_insertion():
    planner = PlannerAgent()
    
    # Mock supplier agent returning missing supplier data recommendation
    class MockSupplierAgent:
        @property
        def metadata(self):
            from agents.base_agent import AgentMetadata
            return AgentMetadata(
                agent_name="SupplierAgent",
                description="Supplier agent",
                capabilities=["get_supplier_metrics"],
                required_inputs=[],
                produced_outputs=["supplier_responses"]
            )
        def plan(self, state, task):
            return task
        def execute(self, state, task):
            # Create a mock result where one supplier has Missing status
            from agents.shared_state import SupplierResponse
            resp = SupplierResponse(
                supplier_id=10,
                supplier_name="Uncooperative Supplier Inc.",
                emission_data_status="Missing"
            )
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"supplier_responses": [resp.dict()]},
                confidence=0.80,
                risks=["Missing raw metrics"],
                recommendations=["Run supplier verification"],
                need_planner_intervention=True
            )
        def validate(self, state, result):
            return True
        def summarize(self, state, result):
            return "Supplier logs done"

    class MockConvAgent:
        @property
        def metadata(self):
            from agents.base_agent import AgentMetadata
            return AgentMetadata(
                agent_name="ConversationAgent",
                description="NL formatter",
                capabilities=["generate_response"],
                required_inputs=[],
                produced_outputs=["final_natural_language_response"]
            )
        def plan(self, state, task):
            return task
        def execute(self, state, task):
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"answer": "NL Answer"},
                confidence=1.0
            )
        def validate(self, state, result):
            return True
        def summarize(self, state, result):
            return "NL compiled"

    agents = {
        "SupplierAgent": MockSupplierAgent(),
        "ConversationAgent": MockConvAgent()
    }
    
    engine = ExecutionEngine(planner, agents)
    
    # Trigger top emitter goal (which schedules get_top_emitter -> generate_response)
    state = planner.plan_goal("Show top supplier with highest emissions", [agents["SupplierAgent"].metadata.dict(), agents["ConversationAgent"].metadata.dict()])
    
    # Overwrite get_top_emitter task to use mock SupplierAgent
    for t in state.current_tasks:
        if t.task_id == "get_top_emitter":
            t.assigned_agent = "SupplierAgent"
            t.input_data = {"action": "get_supplier_metrics"}
            
    report = engine.run(state)
    
    # Check that a Supplier Verification task was dynamically inserted!
    assert state.inserted_tasks_count > 0
    assert any(t.task_id == "supplier_verification" for t in state.current_tasks)
    assert "Uncooperative Supplier Inc." in state.uncertainty_model.unknown_supplier_data
    
    # Verify Planner Learning recorded missing counts
    assert state.planner_learning["missing_supplier_data_counts"] > 0
    
    # Verify Decision Journal tracked the insert decision
    insert_entries = [j for j in state.decision_journal if j.decision == "INSERT_TASKS"]
    assert len(insert_entries) > 0
    assert "Uncertainty detected in supplier logs" in insert_entries[0].reason

def test_parallel_task_scheduling():
    planner = PlannerAgent()
    
    # We will create two tasks that can run in parallel
    task_runs = []
    
    class ParallelMockAgent:
        def __init__(self, name):
            self.name = name
        @property
        def metadata(self):
            from agents.base_agent import AgentMetadata
            return AgentMetadata(
                agent_name=self.name,
                description="Mock description",
                capabilities=["mock_action"],
                required_inputs=[],
                produced_outputs=["mock_output"],
                estimated_cost=0.01
            )
        def plan(self, state, task):
            return task
        def execute(self, state, task):
            t_start = time.time()
            # Sleep briefly to demonstrate parallel execution duration
            time.sleep(0.5)
            t_end = time.time()
            task_runs.append((task.task_id, t_start, t_end))
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"done": True},
                execution_time=t_end - t_start
            )
        def validate(self, state, result):
            return True
        def summarize(self, state, result):
            return "Done"

    agents = {
        "AgentA": ParallelMockAgent("AgentA"),
        "AgentB": ParallelMockAgent("AgentB")
    }
    
    engine = ExecutionEngine(planner, agents)
    
    state = ExecutionState(user_goal="Parallel execution goal")
    t1 = Task(task_id="taskA", assigned_agent="AgentA", dependencies=[])
    t2 = Task(task_id="taskB", assigned_agent="AgentB", dependencies=[])
    state.current_tasks = [t1, t2]
    
    # Setup initial dummy goal model
    state.goal_model = Goal(
        goal_id="dummy", user_intent="intent", desired_outcome="outcome", success_criteria=["criteria"]
    )
    
    t_start_all = time.time()
    report = engine.run(state)
    t_elapsed_all = time.time() - t_start_all
    
    # Verify execution finished successfully
    assert report.status == "SUCCESS"
    assert len(task_runs) == 2
    
    # If tasks ran in parallel, the total elapsed time should be close to 0.5s instead of 1.0s!
    assert t_elapsed_all < 0.9  # sync run would take 0.5 + 0.5 = 1.0s minimum.
    
    # Check start/end overlap
    runA = [tr for tr in task_runs if tr[0] == "taskA"][0]
    runB = [tr for tr in task_runs if tr[0] == "taskB"][0]
    
    # Verify overlap (one task started before the other finished)
    assert runA[1] < runB[2]
    assert runB[1] < runA[2]
