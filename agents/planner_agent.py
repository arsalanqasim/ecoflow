import os
import json
import logging
from typing import List, Dict, Any, Optional
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult, AgentDecision, ExecutionTimelineEvent
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger("PlannerAgent")

class PlannerAgent(BaseAgent):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            try:
                self.genai_client = genai.Client()
                logger.info("PlannerAgent initialized with Gemini Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client in PlannerAgent: {e}. Fallback logic will be used.")
                self.genai_client = None
        else:
            logger.info("PlannerAgent initialized. Using rule-based fallback plan generator (No GEMINI_API_KEY found).")
            self.genai_client = None

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="PlannerAgent",
            description="Acts as the brain of the multi-agent system, analyzing goals, constructing execution graphs (DAGs), and evaluating task results to guide execution dynamically.",
            capabilities=["plan_goal", "evaluate_task_result"],
            required_inputs=["user_goal", "agents_metadata"],
            produced_outputs=["execution_graph", "agent_decisions"],
            estimated_cost=0.05,
            estimated_latency=3.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        return TaskResult(
            task_id=task.task_id,
            execution_status="COMPLETED",
            output_data={"message": "Planner execute not typically called directly."},
            execution_time=0.0
        )

    def plan_goal(self, goal: str, agents_metadata: List[Dict[str, Any]]) -> ExecutionState:
        logger.info(f"Planning goal: '{goal}'")
        state = ExecutionState(user_goal=goal)
        
        plan_data = None
        if self.genai_client:
            plan_data = self._plan_with_llm(goal, agents_metadata)
            
        if not plan_data:
            plan_data = self._plan_fallback(goal)

        state.execution_graph = {
            "nodes": [t["task_id"] for t in plan_data["tasks"]],
            "edges": plan_data.get("edges", [])
        }
        
        for t_dict in plan_data["tasks"]:
            task = Task(
                task_id=t_dict["task_id"],
                assigned_agent=t_dict["assigned_agent"],
                dependencies=t_dict.get("dependencies", []),
                priority=t_dict.get("priority", 1),
                validation_rules=t_dict.get("validation_rules", []),
                expected_outputs=t_dict.get("expected_outputs", []),
                retry_limit=t_dict.get("retry_limit", 3),
                input_data=t_dict.get("input_data", {})
            )
            state.current_tasks.append(task)
            
        logger.info(f"Planned {len(state.current_tasks)} tasks with graph: {state.execution_graph}")
        return state

    def evaluate_task_result(self, state: ExecutionState, task: Task, result: TaskResult) -> AgentDecision:
        logger.info(f"Evaluating task result for task {task.task_id} (status: {result.execution_status})")
        
        if result.execution_status == "FAILED":
            if task.retry_count < task.retry_limit:
                decision = AgentDecision(
                    decision="RETRY",
                    reasoning=f"Task {task.task_id} failed with error: {result.error_message}. Retrying execution.",
                    confidence=0.8,
                    alternative_options=["TERMINATE"]
                )
            else:
                decision = AgentDecision(
                    decision="TERMINATE",
                    reasoning=f"Task {task.task_id} exceeded retry limit. Error: {result.error_message}.",
                    confidence=1.0,
                    alternative_options=[]
                )
            state.agent_decisions.append(decision)
            return decision

        if self.genai_client:
            decision = self._evaluate_with_llm(state, task, result)
            if decision:
                state.agent_decisions.append(decision)
                return decision

        pending = [t for t in state.current_tasks if t.execution_status in ["PENDING", "RUNNING"]]
        if len(pending) > 1:
            decision = AgentDecision(
                decision="CONTINUE",
                reasoning=f"Task {task.task_id} completed successfully. Continuing to downstream tasks.",
                confidence=1.0
            )
        else:
            decision = AgentDecision(
                decision="CONTINUE",
                reasoning=f"All scheduled tasks completed successfully. Wrapping up response.",
                confidence=1.0
            )
            
        state.agent_decisions.append(decision)
        return decision

    def _plan_with_llm(self, goal: str, agents_metadata: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        prompt = (
            f"You are the Planner Agent. Your job is to decompose the user's goal into a Directed Acyclic Graph (DAG) "
            f"of tasks using the available specialized agents. Do not perform any calculations yourself.\n\n"
            f"User Goal: {goal}\n\n"
            f"Available Agents Metadata:\n{json.dumps(agents_metadata, indent=2)}\n\n"
            f"Output a valid JSON object ONLY containing 'tasks' and 'edges'.\n"
            f"Example format:\n"
            f"{{\n"
            f"  \"tasks\": [\n"
            f"    {{\n"
            f"      \"task_id\": \"task1\",\n"
            f"      \"assigned_agent\": \"CarbonCalculationAgent\",\n"
            f"      \"dependencies\": [],\n"
            f"      \"priority\": 1,\n"
            f"      \"validation_rules\": [\"has processed_count\"],\n"
            f"      \"expected_outputs\": [\"carbon_results\"],\n"
            f"      \"retry_limit\": 3,\n"
            f"      \"input_data\": {{\n"
            f"        \"action\": \"run_calculation_cycle\"\n"
            f"      }}\n"
            f"    }}\n"
            f"  ],\n"
            f"  \"edges\": [\n"
            f"    {{\"from\": \"task1\", \"to\": \"task2\"}}\n"
            f"  ]\n"
            f"}}\n"
        )
        
        try:
            response = self.genai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            if response.text:
                data = json.loads(response.text.strip())
                if "tasks" in data:
                    return data
        except Exception as e:
            logger.warning(f"Failed to plan with LLM: {e}. Falling back.")
        return None

    def _evaluate_with_llm(self, state: ExecutionState, task: Task, result: TaskResult) -> Optional[AgentDecision]:
        prompt = (
            f"You are the Planner Agent. Evaluate this task execution result and decide if we should "
            f"CONTINUE, RETRY, SKIP, INSERT_TASKS, or TERMINATE.\n\n"
            f"User Goal: {state.user_goal}\n"
            f"Task: {json.dumps(task.dict(), indent=2)}\n"
            f"Result: {json.dumps(result.dict(), indent=2)}\n\n"
            f"Output a valid JSON object matching the AgentDecision schema. E.g.:\n"
            f"{{\n"
            f"  \"decision\": \"CONTINUE\",\n"
            f"  \"reasoning\": \"The calculations completed successfully with 15 records, proceeding to audit.\",\n"
            f"  \"confidence\": 0.95,\n"
            f"  \"alternative_options\": [],\n"
            f"  \"next_recommended_agent\": \"ComplianceAgent\"\n"
            f"}}\n"
        )
        try:
            response = self.genai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            if response.text:
                data = json.loads(response.text.strip())
                if "decision" in data:
                    return AgentDecision(
                        decision=data["decision"],
                        reasoning=data["reasoning"],
                        confidence=data.get("confidence", 1.0),
                        alternative_options=data.get("alternative_options", []),
                        next_recommended_agent=data.get("next_recommended_agent")
                    )
        except Exception as e:
            logger.warning(f"Failed to evaluate result with LLM: {e}. Falling back.")
        return None

    def _plan_fallback(self, goal: str) -> Dict[str, Any]:
        goal_lower = goal.lower()
        
        # 1. Forecasting Goal
        if "forecast" in goal_lower or "predict" in goal_lower or "future" in goal_lower:
            return {
                "tasks": [
                    {
                        "task_id": "get_historical_emissions",
                        "assigned_agent": "CarbonCalculationAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has historical_emissions"],
                        "expected_outputs": ["historical_emissions"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_historical_emissions"}
                    },
                    {
                        "task_id": "run_forecast",
                        "assigned_agent": "CarbonCalculationAgent",
                        "dependencies": ["get_historical_emissions"],
                        "priority": 2,
                        "validation_rules": ["has forecast_res"],
                        "expected_outputs": ["forecast_res"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_forecast"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["run_forecast"],
                        "priority": 3,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "get_historical_emissions", "to": "run_forecast"},
                    {"from": "run_forecast", "to": "generate_response"}
                ]
            }
            
        # 2. Top Emitter Goal
        elif "top emitter" in goal_lower or "highest emissions" in goal_lower or "top supplier" in goal_lower:
            return {
                "tasks": [
                    {
                        "task_id": "get_top_emitter",
                        "assigned_agent": "SupplierAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has supplier_name"],
                        "expected_outputs": ["supplier_name"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_top_emitter"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["get_top_emitter"],
                        "priority": 2,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "get_top_emitter", "to": "generate_response"}
                ]
            }

        # 3. CBAM Liabilities Goal
        elif "cbam" in goal_lower or "tariff" in goal_lower or "duty" in goal_lower or "liabilities" in goal_lower:
            return {
                "tasks": [
                    {
                        "task_id": "get_cbam_liabilities",
                        "assigned_agent": "ComplianceAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has cbam_liabilities_eur"],
                        "expected_outputs": ["cbam_liabilities_eur"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_cbam_liabilities"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["get_cbam_liabilities"],
                        "priority": 2,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "get_cbam_liabilities", "to": "generate_response"}
                ]
            }

        # 4. Compliance Audit Cycle Goal
        elif "audit cycle" in goal_lower or "compliance audit" in goal_lower:
            return {
                "tasks": [
                    {
                        "task_id": "run_audit",
                        "assigned_agent": "ComplianceAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has audits_created"],
                        "expected_outputs": ["audits_created"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_audit_cycle"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["run_audit"],
                        "priority": 2,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "run_audit", "to": "generate_response"}
                ]
            }

        # 5. Ingestion / Data Upload Cycle Goal
        elif "upload" in goal_lower or "process" in goal_lower or "calculate emissions" in goal_lower:
            return {
                "tasks": [
                    {
                        "task_id": "run_calc",
                        "assigned_agent": "CarbonCalculationAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has processed_count"],
                        "expected_outputs": ["processed_count"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_calculation_cycle"}
                    },
                    {
                        "task_id": "run_audit",
                        "assigned_agent": "ComplianceAgent",
                        "dependencies": ["run_calc"],
                        "priority": 2,
                        "validation_rules": ["has audits_created"],
                        "expected_outputs": ["audits_created"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_audit_cycle", "carbon_price": 80.0}
                    },
                    {
                        "task_id": "run_optimize",
                        "assigned_agent": "OptimizationAgent",
                        "dependencies": ["run_calc"],
                        "priority": 2,
                        "validation_rules": ["has optimization_results"],
                        "expected_outputs": ["optimization_results"],
                        "retry_limit": 3,
                        "input_data": {"action": "optimize_logistics"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["run_audit", "run_optimize"],
                        "priority": 3,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "run_calc", "to": "run_audit"},
                    {"from": "run_calc", "to": "run_optimize"},
                    {"from": "run_audit", "to": "generate_response"},
                    {"from": "run_optimize", "to": "generate_response"}
                ]
            }

        # 6. Default General Summary Goal
        else:
            return {
                "tasks": [
                    {
                        "task_id": "get_total_emissions",
                        "assigned_agent": "CarbonCalculationAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has total_emissions_tCO2"],
                        "expected_outputs": ["total_emissions_tCO2"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_total_emissions"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["get_total_emissions"],
                        "priority": 2,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "get_total_emissions", "to": "generate_response"}
                ]
            }
