import pytest
from agents.shared_state import ExecutionState, Task, TaskResult, AgentDecision
from agents.planner_agent import PlannerAgent
from agents.engine import ExecutionEngine
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.supplier_agent import SupplierAgent
from agents.optimization_agent import OptimizationAgent
from agents.conversation_agent import ConversationAgent

def test_models_instantiation():
    task = Task(
        task_id="task_1",
        assigned_agent="CarbonCalculationAgent",
        dependencies=[],
        priority=1,
        validation_rules=["rule_1"],
        expected_outputs=["output_1"],
        retry_limit=3,
        input_data={"action": "calculate"}
    )
    assert task.task_id == "task_1"
    assert task.execution_status == "PENDING"
    assert task.retry_count == 0

    state = ExecutionState(user_goal="Test Goal")
    assert state.user_goal == "Test Goal"
    assert len(state.current_tasks) == 0
    assert state.current_status == "PENDING"

def test_planner_agent_fallback_planning():
    planner = PlannerAgent()
    
    # Test forecast query planning
    state = planner.plan_goal("forecast future carbon emissions", [])
    assert len(state.current_tasks) == 3
    assert state.current_tasks[0].task_id == "get_historical_emissions"
    assert state.current_tasks[1].task_id == "run_forecast"
    assert state.current_tasks[2].task_id == "generate_response"
    assert "get_historical_emissions" in state.execution_graph["nodes"]
    assert {"from": "get_historical_emissions", "to": "run_forecast"} in state.execution_graph["edges"]

    # Test top supplier query planning
    state2 = planner.plan_goal("Show top supplier with highest emissions", [])
    assert len(state2.current_tasks) == 2
    assert state2.current_tasks[0].task_id == "get_top_emitter"
    assert state2.current_tasks[1].task_id == "generate_response"

def test_planner_agent_evaluation():
    planner = PlannerAgent()
    state = ExecutionState(user_goal="forecast emissions")
    
    task = Task(task_id="run_forecast", assigned_agent="CarbonCalculationAgent")
    
    # 1. Success evaluation
    result_success = TaskResult(
        task_id="run_forecast",
        execution_status="COMPLETED",
        output_data={"forecast_res": []}
    )
    decision1 = planner.evaluate_task_result(state, task, result_success)
    assert decision1.decision == "CONTINUE"

    # 2. Failure and retry evaluation
    result_failed = TaskResult(
        task_id="run_forecast",
        execution_status="FAILED",
        error_message="Test failure"
    )
    task.retry_limit = 3
    task.retry_count = 0
    decision2 = planner.evaluate_task_result(state, task, result_failed)
    assert decision2.decision == "RETRY"

    # 3. Exceeded retry limit evaluation
    task.retry_count = 3
    decision3 = planner.evaluate_task_result(state, task, result_failed)
    assert decision3.decision == "TERMINATE"

def test_execution_engine_routing_and_skipping():
    planner = PlannerAgent()
    
    # Create simple mock worker agents
    class MockAgent1:
        @property
        def metadata(self):
            from agents.base_agent import AgentMetadata
            return AgentMetadata(
                agent_name="MockAgent1",
                description="Mock description",
                capabilities=["mock_action"],
                required_inputs=[],
                produced_outputs=["mock_output"],
                estimated_cost=0.01
            )
        def plan(self, state, task):
            return task
        def execute(self, state, task):
            return TaskResult(task_id=task.task_id, execution_status="COMPLETED", output_data={"val": 42}, execution_time=0.1)
        def validate(self, state, result):
            return True
        def summarize(self, state, result):
            return "Mock 1 done"

    class MockAgent2:
        @property
        def metadata(self):
            from agents.base_agent import AgentMetadata
            return AgentMetadata(
                agent_name="MockAgent2",
                description="Mock description 2",
                capabilities=["mock_action_2"],
                required_inputs=["mock_output"],
                produced_outputs=["final_response"],
                estimated_cost=0.02
            )
        def plan(self, state, task):
            return task
        def execute(self, state, task):
            return TaskResult(task_id=task.task_id, execution_status="COMPLETED", output_data={"answer": "Final answers!"}, execution_time=0.2)
        def validate(self, state, result):
            return True
        def summarize(self, state, result):
            return "Mock 2 done"

    agents = {
        "MockAgent1": MockAgent1(),
        "MockAgent2": MockAgent2()
    }
    
    engine = ExecutionEngine(planner, agents)
    
    state = ExecutionState(user_goal="Run mock engine")
    task1 = Task(task_id="task1", assigned_agent="MockAgent1", dependencies=[])
    task2 = Task(task_id="task2", assigned_agent="MockAgent2", dependencies=["task1"])
    state.current_tasks = [task1, task2]
    state.execution_graph = {"nodes": ["task1", "task2"], "edges": [{"from": "task1", "to": "task2"}]}
    
    report = engine.run(state)
    
    assert report.status == "SUCCESS"
    assert report.total_tasks == 2
    assert report.succeeded_tasks == 2
    assert state.task_history["task1"].output_data["val"] == 42
    assert state.task_history["task2"].output_data["answer"] == "Final answers!"
    assert len(state.execution_timeline) == 4 # start and completed for both tasks
