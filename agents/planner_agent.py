import os
import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import (
    ExecutionState, Task, TaskResult, AgentDecision, ExecutionTimelineEvent,
    Goal, PlanningHypothesis, HypothesisRegistry, Uncertainty, Observation, DecisionJournalEntry
)
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
            description="Acts as the continuously reasoning brain of the multi-agent system, formulating hypotheses, managing uncertainty, and evaluating progress.",
            capabilities=["plan_goal", "evaluate_task_result"],
            required_inputs=["user_goal", "agents_metadata"],
            produced_outputs=["execution_graph", "agent_decisions", "decision_journal"],
            estimated_cost=0.08,
            estimated_latency=4.0
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
        state.reasoning_iterations += 1

        plan_data = None
        if self.genai_client:
            plan_data = self._plan_with_llm(goal, agents_metadata)
            
        if not plan_data:
            plan_data = self._plan_fallback(goal, agents_metadata)

        # 1. Establish Goal Model
        g_data = plan_data.get("goal_model", {})
        state.goal_model = Goal(
            goal_id=g_data.get("goal_id", "goal_01"),
            user_intent=g_data.get("user_intent", goal),
            desired_outcome=g_data.get("desired_outcome", "Satisfied user query with verified data"),
            success_criteria=g_data.get("success_criteria", ["Complete execution of planned tasks"]),
            completion_percentage=0.0,
            remaining_unknowns=g_data.get("remaining_unknowns", []),
            confidence=1.0,
            constraints=g_data.get("constraints", []),
            assumptions=g_data.get("assumptions", []),
            risks=g_data.get("risks", [])
        )

        # 2. Establish Competing Hypotheses & Strategy
        hyp_data = plan_data.get("planning_hypothesis", {})
        hyp_list = []
        for h in hyp_data.get("hypotheses", []):
            hyp_list.append(PlanningHypothesis(
                hypothesis_text=h.get("hypothesis_text", ""),
                assumed_steps=h.get("assumed_steps", []),
                expected_dependencies=h.get("expected_dependencies", {}),
                confidence=h.get("confidence", 1.0)
            ))
            
        state.planning_hypothesis = HypothesisRegistry(
            hypotheses=hyp_list,
            selected_hypothesis_index=hyp_data.get("selected_hypothesis_index", 0),
            discarded_hypotheses=[
                PlanningHypothesis(
                    hypothesis_text=dh.get("hypothesis_text", ""),
                    assumed_steps=dh.get("assumed_steps", []),
                    expected_dependencies=dh.get("expected_dependencies", {}),
                    confidence=dh.get("confidence", 1.0)
                ) for dh in hyp_data.get("discarded_hypotheses", [])
            ]
        )
        
        state.execution_strategy = plan_data.get("execution_strategy", "Maximum Accuracy")

        # 3. Establish Uncertainty Model
        state.uncertainty_model = Uncertainty(
            missing_information=[],
            incomplete_documents=[],
            estimated_values=[],
            low_confidence_outputs=[],
            conflicting_evidence=[],
            unknown_supplier_data=[]
        )

        # 4. Generate Task Graph
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
            
        # Log initial decision
        initial_decision = DecisionJournalEntry(
            timestamp=datetime.now().isoformat(),
            decision="PLAN_INITIALIZED",
            reason="Formulated initial hypotheses and generated task DAG matching the user's intent.",
            evidence=f"User Goal: {goal}",
            confidence=1.0,
            alternative_considered=[h.hypothesis_text for h in state.planning_hypothesis.discarded_hypotheses],
            expected_outcome="Resolve emissions metrics using chosen strategy: " + state.execution_strategy
        )
        state.decision_journal.append(initial_decision)
        
        logger.info(f"Planned {len(state.current_tasks)} tasks with strategy: {state.execution_strategy}")
        return state

    def _update_agent_reputation(self, state: ExecutionState, task: Task, result: TaskResult):
        # A2A Trust score initialization
        if not hasattr(state, "a2a_trust_scores") or state.a2a_trust_scores is None:
            state.a2a_trust_scores = {}
        if not state.a2a_trust_scores:
            state.a2a_trust_scores["Supplier_A"] = 0.98
            state.a2a_trust_scores["Supplier_B"] = 0.85
            state.a2a_trust_scores["Supplier_C"] = 0.75
            state.a2a_trust_scores["Certification_Authority"] = 1.0
            state.a2a_trust_scores["Logistics_Provider"] = 0.95

        # Trust decay and evaluation rules based on execution
        if task.assigned_agent == "SupplierAgent":
            remote_org = task.input_data.get("remote_org")
            if remote_org in state.a2a_trust_scores:
                current_trust = state.a2a_trust_scores[remote_org]
                if result.execution_status == "FAILED":
                    state.a2a_trust_scores[remote_org] = max(0.1, current_trust - 0.15)
                elif result.confidence < 0.80:
                    state.a2a_trust_scores[remote_org] = max(0.1, current_trust - 0.05)

        if not state.planner_learning:
            state.planner_learning = {}
        if "agent_reputation" not in state.planner_learning:
            state.planner_learning["agent_reputation"] = {}
            
        reputation = state.planner_learning["agent_reputation"]
        agent_name = task.assigned_agent
        
        if agent_name not in reputation:
            reputation[agent_name] = {
                "accuracy": 1.0,
                "helpfulness": 1.0,
                "confidence_calibration": 1.0,
                "failed_recommendations": 0,
                "successful_recommendations": 0,
                "response_latency": 0.0,
                "total_runs": 0
            }
            
        rep = reputation[agent_name]
        rep["total_runs"] += 1
        runs = rep["total_runs"]
        
        # Update latency
        rep["response_latency"] = ((rep["response_latency"] * (runs - 1)) + result.execution_time) / runs
        
        # Update accuracy
        success_val = 1.0 if result.execution_status == "COMPLETED" else 0.0
        rep["accuracy"] = ((rep["accuracy"] * (runs - 1)) + success_val) / runs
        
        # Update helpfulness
        help_val = 1.0 if not result.need_planner_intervention else 0.5
        if result.recommendations:
            help_val = min(1.0, help_val + 0.1)
        rep["helpfulness"] = ((rep["helpfulness"] * (runs - 1)) + help_val) / runs
        
        # Confidence calibration
        calibration_error = abs(result.confidence - success_val)
        calibration_score = max(0.0, 1.0 - calibration_error)
        rep["confidence_calibration"] = ((rep["confidence_calibration"] * (runs - 1)) + calibration_score) / runs
        
        # Recommendations tracking
        if result.execution_status == "COMPLETED" and result.recommendations:
            rep["successful_recommendations"] += len(result.recommendations)
        elif result.execution_status == "FAILED" and result.recommendations:
            rep["failed_recommendations"] += len(result.recommendations)

    def evaluate_task_result(self, state: ExecutionState, task: Task, result: TaskResult) -> AgentDecision:
        logger.info(f"Executive evaluation for task {task.task_id} (status: {result.execution_status})")
        state.reasoning_iterations += 1
        
        # 1. Compile Observation
        observation = Observation(
            task_id=task.task_id,
            result_summary=result.output_data,
            confidence=result.confidence,
            duration=result.execution_time,
            unexpected_findings=result.output_data.get("unexpected_findings", []) + ([result.error_message] if result.error_message else []),
            warnings=result.output_data.get("warnings", []),
            risks=result.risks,
            recommendations=result.recommendations,
            planner_intervention_advised=result.need_planner_intervention or (result.execution_status == "FAILED"),
            suggested_next_action=result.output_data.get("suggested_next_action", "")
        )
        state.observations.append(observation)

        # Update reputation
        self._update_agent_reputation(state, task, result)

        # 2. Accumulate Learning
        if result.execution_status == "FAILED":
            if state.planner_learning:
                state.planner_learning["repeated_failures"] = state.planner_learning.get("repeated_failures", 0) + 1
                agent_fail = state.planner_learning.get("unreliable_agents", {})
                agent_fail[task.assigned_agent] = agent_fail.get(task.assigned_agent, 0) + 1
                state.planner_learning["unreliable_agents"] = agent_fail
        
        if state.planner_learning:
            state.planner_learning["agent_costs"] = state.planner_learning.get("agent_costs", 0.0) + self._estimate_cost(task.assigned_agent)

        # Look for missing data logs (uncooperative suppliers / missing status)
        if task.assigned_agent == "SupplierAgent" and "supplier_responses" in result.output_data:
            for s_resp in result.output_data["supplier_responses"]:
                if s_resp.get("emission_data_status") in ["Missing", "Unknown"]:
                    if state.planner_learning:
                        state.planner_learning["missing_supplier_data_counts"] = state.planner_learning.get("missing_supplier_data_counts", 0) + 1
                    supplier_name = s_resp.get("supplier_name", "Unknown")
                    if state.uncertainty_model:
                        if supplier_name not in state.uncertainty_model.unknown_supplier_data:
                            state.uncertainty_model.unknown_supplier_data.append(supplier_name)
                            state.uncertainty_model.missing_information.append(f"Emissions logs missing for supplier {supplier_name}")

        # 3. Propagate Confidence
        state.confidence_history.append(result.confidence)
        # Global confidence is rolling average of task history
        if state.confidence_history:
            state.overall_confidence = sum(state.confidence_history) / len(state.confidence_history)

        # If LLM is available, perform reasoning-based replanning
        llm_decision = None
        if self.genai_client:
            llm_decision = self._evaluate_with_llm(state, task, result)
            
        if llm_decision:
            return llm_decision

        # Fallback Replanning Logic
        decision_str = "CONTINUE"
        reasoning = f"Task {task.task_id} completed successfully. Proceeding with execution graph."
        alternative_options = ["TERMINATE"]
        next_recommended = None

        if result.execution_status == "FAILED":
            # Check for Access Denied / Permission Denied to trigger replanning/negotiation
            if "Access Denied" in str(result.error_message) or "Permission" in str(result.error_message):
                remote_org = task.input_data.get("remote_org")
                if remote_org == "Supplier_C" and not any(t.task_id == "supplier_c_negotiation" for t in state.current_tasks):
                    decision_str = "INSERT_TASKS"
                    next_recommended = "SupplierAgent"
                    reasoning = "Access Denied by Supplier C. Triggering A2A negotiation to request monthly average fallbacks."
                    state.inserted_tasks_count += 1
                    
                    negotiate_task = Task(
                        task_id="supplier_c_negotiation",
                        assigned_agent="SupplierAgent",
                        dependencies=[task.task_id],
                        priority=3,
                        validation_rules=["has negotiation_result"],
                        expected_outputs=["negotiation_status"],
                        input_data={"action": "negotiate_access", "remote_org": "Supplier_C"}
                    )
                    state.current_tasks.append(negotiate_task)
                    
                    retry_task = Task(
                        task_id="a2a_supplier_c_retry",
                        assigned_agent="SupplierAgent",
                        dependencies=["supplier_c_negotiation"],
                        priority=4,
                        validation_rules=["has supplier_responses"],
                        expected_outputs=["supplier_responses"],
                        input_data={"action": "query_supplier", "remote_org": "Supplier_C"}
                    )
                    state.current_tasks.append(retry_task)
                    
                    state.execution_graph["nodes"].append("supplier_c_negotiation")
                    state.execution_graph["nodes"].append("a2a_supplier_c_retry")
                    state.execution_graph["edges"].append({"from": task.task_id, "to": "supplier_c_negotiation"})
                    state.execution_graph["edges"].append({"from": "supplier_c_negotiation", "to": "a2a_supplier_c_retry"})
                    
                    for t in state.current_tasks:
                        if t.task_id == "run_consensus":
                            if "a2a_supplier_handshakes" in t.dependencies:
                                t.dependencies.remove("a2a_supplier_handshakes")
                            t.dependencies.append("a2a_supplier_c_retry")
                            state.execution_graph["edges"].append({"from": "a2a_supplier_c_retry", "to": "run_consensus"})
                            
                    result.execution_status = "COMPLETED"
                    return AgentDecision(
                        decision=decision_str,
                        reasoning=reasoning,
                        next_recommended_agent=next_recommended
                    )

            if task.retry_count < task.retry_limit:
                decision_str = "RETRY"
                reasoning = f"Task {task.task_id} failed. Retrying (Attempt {task.retry_count + 1}). Error: {result.error_message}"
            else:
                decision_str = "TERMINATE"
                reasoning = f"Task {task.task_id} exceeded retry limit. Terminal failure."
                state.errors.append(reasoning)
        else:
            # Check for dynamic task insertions based on uncertainty / findings
            
            # Dynamic 1: Missing Supplier data -> Insert Verification Task
            if state.uncertainty_model and state.uncertainty_model.unknown_supplier_data and not any(t.task_id == "supplier_verification" for t in state.current_tasks):
                decision_str = "INSERT_TASKS"
                next_recommended = "SupplierAgent"
                reasoning = "Uncertainty detected in supplier logs. Inserting Supplier Verification Task to resolve data gaps."
                state.inserted_tasks_count += 1
                
                # Create the verification task
                verification_task = Task(
                    task_id="supplier_verification",
                    assigned_agent="SupplierAgent",
                    dependencies=[task.task_id],
                    priority=4,  # High priority to verify early
                    validation_rules=["has verified_logs"],
                    expected_outputs=["verified_status"],
                    input_data={"action": "get_supplier_metrics", "verify_mode": True}
                )
                state.current_tasks.append(verification_task)
                state.execution_graph["nodes"].append("supplier_verification")
                state.execution_graph["edges"].append({"from": task.task_id, "to": "supplier_verification"})
                
                # Make ConversationAgent depend on it
                for t in state.current_tasks:
                    if t.assigned_agent == "ConversationAgent":
                        t.dependencies.append("supplier_verification")
                        state.execution_graph["edges"].append({"from": "supplier_verification", "to": t.task_id})

            # Dynamic 2: Confidence drops too low -> Insert Reflection Task
            elif state.overall_confidence < 0.82 and not any(t.task_id == "planner_reflection" for t in state.current_tasks):
                decision_str = "INSERT_TASKS"
                next_recommended = "ReflectionAgent"
                reasoning = f"Overall confidence fell to {state.overall_confidence:.2f}. Inserting Reflection Task for quality assurance."
                state.inserted_tasks_count += 1
                
                reflection_task = Task(
                    task_id="planner_reflection",
                    assigned_agent="ReflectionAgent",
                    dependencies=[task.task_id],
                    priority=5,
                    input_data={"action": "reflect", "confidence_history": state.confidence_history}
                )
                state.current_tasks.append(reflection_task)
                state.execution_graph["nodes"].append("planner_reflection")
                state.execution_graph["edges"].append({"from": task.task_id, "to": "planner_reflection"})
                
                for t in state.current_tasks:
                    if t.assigned_agent == "ConversationAgent":
                        t.dependencies.append("planner_reflection")
                        state.execution_graph["edges"].append({"from": "planner_reflection", "to": t.task_id})

            # Dynamic 3: Upload cycle processed 0 records -> Skip downstream tasks and terminate early
            elif task.task_id == "run_calc" and result.output_data.get("processed_count") == 0:
                decision_str = "CONTINUE"
                reasoning = "Calculations processed 0 new records. Planner decides to skip downstream auditing and optimizations."
                
                # Mark downstream audit and optimization tasks as SKIPPED
                for t in state.current_tasks:
                    if t.task_id in ["run_audit", "run_optimize"]:
                        t.execution_status = "SKIPPED"
                        state.skipped_tasks_count += 1
                        state.task_history[t.task_id] = TaskResult(
                            task_id=t.task_id,
                            execution_status="SKIPPED",
                            output_data={"message": "Skipped because no new carbon records were processed."}
                        )

        # Update Goal completion percentage
        completed_tasks = len([t for t in state.current_tasks if t.execution_status == "COMPLETED" or t.execution_status == "SKIPPED"])
        total_tasks = len(state.current_tasks)
        if total_tasks > 0 and state.goal_model:
            state.goal_model.completion_percentage = round((completed_tasks / total_tasks) * 100.0, 2)
            
        if state.goal_model and state.goal_model.completion_percentage >= 100.0 and decision_str == "CONTINUE":
            state.goal_model.current_progress = "Success criteria satisfied."
            logger.info("Goal completion evaluated: 100% completed.")

        # Log decision to Decision Journal
        alts = alternative_options
        if state.planning_hypothesis and state.planning_hypothesis.discarded_hypotheses:
            alts.extend([h.hypothesis_text for h in state.planning_hypothesis.discarded_hypotheses])
            
        journal_entry = DecisionJournalEntry(
            timestamp=datetime.now().isoformat(),
            decision=decision_str,
            reason=reasoning,
            evidence=f"Observation of task {task.task_id} completed with confidence {result.confidence:.2f}.",
            confidence=state.overall_confidence,
            alternative_considered=alts,
            expected_outcome=f"Advance goal progress. Current progress: {state.goal_model.completion_percentage if state.goal_model else 0.0}%"
        )
        state.decision_journal.append(journal_entry)

        decision_obj = AgentDecision(
            decision=decision_str,
            reasoning=reasoning,
            confidence=state.overall_confidence,
            alternative_options=alternative_options,
            next_recommended_agent=next_recommended
        )
        state.agent_decisions.append(decision_obj)
        return decision_obj

    def _plan_with_llm(self, goal: str, agents_metadata: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        prompt = (
            f"You are the Executive Planner. Decompose the goal into a DAG task graph matching agent capabilities. "
            f"Formulate multiple competing planning hypotheses (assigning confidence to each), select the best strategy "
            f"(Fast Path, Deep Audit, Maximum Accuracy, Minimal Cost, etc.) by trade-off analysis of cost vs latency.\n\n"
            f"User Goal: {goal}\n\n"
            f"Available Agents Metadata:\n{json.dumps(agents_metadata, indent=2)}\n\n"
            f"Output a valid JSON object matching this schema:\n"
            f"{{\n"
            f"  \"goal_model\": {{\n"
            f"    \"goal_id\": \"goal_uuid\",\n"
            f"    \"user_intent\": \"intent description\",\n"
            f"    \"desired_outcome\": \"outcome description\",\n"
            f"    \"success_criteria\": [\"criteria1\", \"criteria2\"],\n"
            f"    \"remaining_unknowns\": [\"unknown1\"],\n"
            f"    \"constraints\": [\"constraint1\"],\n"
            f"    \"assumptions\": [\"assumption1\"],\n"
            f"    \"risks\": [\"risk1\"]\n"
            f"  }},\n"
            f"  \"planning_hypothesis\": {{\n"
            f"    \"hypotheses\": [\n"
            f"      {{\n"
            f"        \"hypothesis_text\": \"H1 text\",\n"
            f"        \"assumed_steps\": [\"step1\", \"step2\"],\n"
            f"        \"expected_dependencies\": {{\"step2\": [\"step1\"]}},\n"
            f"        \"confidence\": 0.95\n"
            f"      }}\n"
            f"    ],\n"
            f"    \"selected_hypothesis_index\": 0,\n"
            f"    \"discarded_hypotheses\": [\n"
            f"      {{\n"
            f"        \"hypothesis_text\": \"H2 text\",\n"
            f"        \"assumed_steps\": [\"step1\"],\n"
            f"        \"expected_dependencies\": {{}},\n"
            f"        \"confidence\": 0.60\n"
            f"      }}\n"
            f"    ]\n"
            f"  }},\n"
            f"  \"execution_strategy\": \"Maximum Accuracy\",\n"
            f"  \"tasks\": [\n"
            f"    {{\n"
            f"      \"task_id\": \"task1\",\n"
            f"      \"assigned_agent\": \"AgentNameMatchedByCapability\",\n"
            f"      \"dependencies\": [],\n"
            f"      \"priority\": 3,\n"
            f"      \"validation_rules\": [\"rule1\"],\n"
            f"      \"expected_outputs\": [\"output1\"],\n"
            f"      \"retry_limit\": 3,\n"
            f"      \"input_data\": {{\"action\": \"action_name\"}}\n"
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
            f"You are the Executive Planner. Analyze the latest collaborative task result observation, "
            f"update uncertainty levels and planner learning experiences, and decide what to do next.\n\n"
            f"User Goal: {state.user_goal}\n"
            f"Task: {json.dumps(task.dict(), indent=2)}\n"
            f"Result: {json.dumps(result.dict(), indent=2)}\n"
            f"Current state information (timeline, uncertainty, decisions): {json.dumps(state.dict(exclude={'current_tasks', 'observations', 'decision_journal', 'carbon_results', 'compliance_results', 'optimization_results', 'supplier_responses'}), indent=2)}\n\n"
            f"Output a valid JSON object matching this schema:\n"
            f"{{\n"
            f"  \"decision\": \"CONTINUE / RETRY / SKIP / INSERT_TASKS / TERMINATE\",\n"
            f"  \"reasoning\": \"explanation of why this decision was taken\",\n"
            f"  \"confidence\": 0.95,\n"
            f"  \"alternative_options\": [\"alt1\", \"alt2\"],\n"
            f"  \"next_recommended_agent\": \"AgentNameOrNone\",\n"
            f"  \"decision_journal_entry\": {{\n"
            f"    \"reason\": \"journal reason\",\n"
            f"    \"evidence\": \"journal evidence\",\n"
            f"    \"expected_outcome\": \"expected outcome\"\n"
            f"  }},\n"
            f"  \"inserted_tasks\": [\n"
            f"     {{\n"
            f"       \"task_id\": \"new_task\",\n"
            f"       \"assigned_agent\": \"AgentName\",\n"
            f"       \"dependencies\": [\"dep1\"],\n"
            f"       \"priority\": 2,\n"
            f"       \"input_data\": {{}}\n"
            f"     }}\n"
            f"  ],\n"
            f"  \"skipped_tasks\": [\"task_id_to_skip\"],\n"
            f"  \"reprioritized_tasks\": {{\"task_id\": 5}}\n"
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
                
                # Apply dynamic DAG updates from LLM
                for new_t in data.get("inserted_tasks", []):
                    task_obj = Task(
                        task_id=new_t["task_id"],
                        assigned_agent=new_t["assigned_agent"],
                        dependencies=new_t.get("dependencies", []),
                        priority=new_t.get("priority", 1),
                        input_data=new_t.get("input_data", {})
                    )
                    state.current_tasks.append(task_obj)
                    if state.execution_graph:
                        if task_obj.task_id not in state.execution_graph.get("nodes", []):
                            state.execution_graph.get("nodes", []).append(task_obj.task_id)
                        for dep in task_obj.dependencies:
                            state.execution_graph.get("edges", []).append({"from": dep, "to": task_obj.task_id})
                    state.inserted_tasks_count += 1
                
                for skip_id in data.get("skipped_tasks", []):
                    for t in state.current_tasks:
                        if t.task_id == skip_id:
                            t.execution_status = "SKIPPED"
                            state.skipped_tasks_count += 1
                            state.task_history[skip_id] = TaskResult(
                                task_id=skip_id,
                                execution_status="SKIPPED",
                                output_data={"message": "Skipped by LLM planner decision."}
                            )

                for t_id, prio in data.get("reprioritized_tasks", {}).items():
                    for t in state.current_tasks:
                        if t.task_id == t_id:
                            t.priority = prio

                # Log to Decision Journal
                j_data = data.get("decision_journal_entry", {})
                
                alts = data.get("alternative_options", [])
                if state.planning_hypothesis and state.planning_hypothesis.discarded_hypotheses:
                    alts.extend([h.hypothesis_text for h in state.planning_hypothesis.discarded_hypotheses])
                    
                journal_entry = DecisionJournalEntry(
                    timestamp=datetime.now().isoformat(),
                    decision=data["decision"],
                    reason=j_data.get("reason", data["reasoning"]),
                    evidence=j_data.get("evidence", f"LLM evaluation of task {task.task_id}"),
                    confidence=data.get("confidence", state.overall_confidence),
                    alternative_considered=alts,
                    expected_outcome=j_data.get("expected_outcome", "Satisfy goal")
                )
                state.decision_journal.append(journal_entry)

                completed_tasks = len([t for t in state.current_tasks if t.execution_status == "COMPLETED" or t.execution_status == "SKIPPED"])
                if state.goal_model:
                    state.goal_model.completion_percentage = round((completed_tasks / len(state.current_tasks)) * 100.0, 2)

                decision_obj = AgentDecision(
                    decision=data["decision"],
                    reasoning=data["reasoning"],
                    confidence=data.get("confidence", state.overall_confidence),
                    alternative_options=data.get("alternative_options", []),
                    next_recommended_agent=data.get("next_recommended_agent")
                )
                state.agent_decisions.append(decision_obj)
                return decision_obj
        except Exception as e:
            logger.warning(f"Failed to parse LLM evaluation: {e}. Falling back.")
        return None

    def _plan_fallback(self, goal: str, agents_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        goal_lower = goal.lower()
        
        # Capability Match Helper
        def find_agent(cap: str) -> str:
            for meta in agents_metadata:
                if cap in meta.get("capabilities", []):
                    return meta["agent_name"]
            # Map fallback names
            mapping = {
                "get_historical_emissions": "CarbonCalculationAgent",
                "run_forecast": "CarbonCalculationAgent",
                "get_top_emitter": "SupplierAgent",
                "get_cbam_liabilities": "ComplianceAgent",
                "run_calculation_cycle": "CarbonCalculationAgent",
                "run_audit_cycle": "ComplianceAgent",
                "optimize_logistics": "OptimizationAgent",
                "generate_response": "ConversationAgent"
            }
            return mapping.get(cap, "CarbonCalculationAgent")

        # 1. Forecasting Goal
        if "forecast" in goal_lower or "predict" in goal_lower or "future" in goal_lower:
            return {
                "goal_model": {
                    "goal_id": "goal_forecast",
                    "user_intent": "Forecast future Scope 3 emissions",
                    "desired_outcome": "Generate 4-month emissions forecast and compile NL response",
                    "success_criteria": ["Emissions forecast generated", "NL response generated"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Retrieve historical monthly emissions and run linear regression forecast.",
                            "assumed_steps": ["get_historical_emissions", "run_forecast", "generate_response"],
                            "expected_dependencies": {"run_forecast": ["get_historical_emissions"]},
                            "confidence": 0.95
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": [
                        {
                            "hypothesis_text": "H2: Run raw shipment forecasting using estimated trends.",
                            "assumed_steps": ["run_forecast", "generate_response"],
                            "expected_dependencies": {},
                            "confidence": 0.50
                        }
                    ]
                },
                "execution_strategy": "Maximum Accuracy",
                "tasks": [
                    {
                        "task_id": "get_historical_emissions",
                        "assigned_agent": find_agent("get_historical_emissions"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has historical_emissions"],
                        "expected_outputs": ["historical_emissions"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_historical_emissions"}
                    },
                    {
                        "task_id": "run_forecast",
                        "assigned_agent": find_agent("run_forecast"),
                        "dependencies": ["get_historical_emissions"],
                        "priority": 2,
                        "validation_rules": ["has forecast_res"],
                        "expected_outputs": ["forecast_res"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_forecast"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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
                "goal_model": {
                    "goal_id": "goal_top_emitter",
                    "user_intent": "Identify the top emitting supplier",
                    "desired_outcome": "Determine highest emitting supplier and compliance status",
                    "success_criteria": ["Top emitting supplier identified"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Fetch supplier emissions metrics and generate answer.",
                            "assumed_steps": ["get_top_emitter", "generate_response"],
                            "expected_dependencies": {},
                            "confidence": 0.98
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "execution_strategy": "Fast Path",
                "tasks": [
                    {
                        "task_id": "get_top_emitter",
                        "assigned_agent": find_agent("get_top_emitter"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has supplier_name"],
                        "expected_outputs": ["supplier_name"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_top_emitter"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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
                "goal_model": {
                    "goal_id": "goal_cbam",
                    "user_intent": "Check border adjustment tariff liabilities",
                    "desired_outcome": "Calculate sum of CBAM tariffs due",
                    "success_criteria": ["CBAM liabilities compiled"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Query compliance audits table for total tariff due.",
                            "assumed_steps": ["get_cbam_liabilities", "generate_response"],
                            "expected_dependencies": {},
                            "confidence": 0.99
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "execution_strategy": "Minimal Cost",
                "tasks": [
                    {
                        "task_id": "get_cbam_liabilities",
                        "assigned_agent": find_agent("get_cbam_liabilities"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has cbam_liabilities_eur"],
                        "expected_outputs": ["cbam_liabilities_eur"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_cbam_liabilities"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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
                "goal_model": {
                    "goal_id": "goal_audit_cycle",
                    "user_intent": "Execute compliance audit cycle",
                    "desired_outcome": "Audit new emissions logs and save results",
                    "success_criteria": ["Compliance audit records updated"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Run audit cycle on unaudited emissions records.",
                            "assumed_steps": ["run_audit", "generate_response"],
                            "expected_dependencies": {},
                            "confidence": 0.95
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "execution_strategy": "Maximum Accuracy",
                "tasks": [
                    {
                        "task_id": "run_audit",
                        "assigned_agent": find_agent("run_audit_cycle"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has audits_created"],
                        "expected_outputs": ["audits_created"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_audit_cycle"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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

        # 5. Ingestion / Data Upload Goal (Non-A2A)
        elif "upload" in goal_lower or "process" in goal_lower or ("calculate emissions" in goal_lower and "a2a" not in goal_lower and "federat" not in goal_lower):
            return {
                "goal_model": {
                    "goal_id": "goal_upload_cycle",
                    "user_intent": "Process uploaded shipment CSV",
                    "desired_outcome": "Calculate emissions, run CBAM audits, suggest optimizations",
                    "success_criteria": ["Data ingested", "Emissions calculated", "CBAM audits done"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Run sequential calculation cycle, then run audits and optimizations in parallel.",
                            "assumed_steps": ["run_calc", "run_audit", "run_optimize", "generate_response"],
                            "expected_dependencies": {
                                "run_audit": ["run_calc"],
                                "run_optimize": ["run_calc"],
                                "generate_response": ["run_audit", "run_optimize"]
                            },
                            "confidence": 0.95
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": [
                        {
                            "hypothesis_text": "H2: Process calc and audit in single batch, skipping optimization.",
                            "assumed_steps": ["run_calc", "run_audit", "generate_response"],
                            "expected_dependencies": {"run_audit": ["run_calc"]},
                            "confidence": 0.70
                        }
                    ]
                },
                "execution_strategy": "Deep Audit",
                "tasks": [
                    {
                        "task_id": "run_calc",
                        "assigned_agent": find_agent("run_calculation_cycle"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has processed_count"],
                        "expected_outputs": ["processed_count"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_calculation_cycle"}
                    },
                    {
                        "task_id": "run_audit",
                        "assigned_agent": find_agent("run_audit_cycle"),
                        "dependencies": ["run_calc"],
                        "priority": 2,
                        "validation_rules": ["has audits_created"],
                        "expected_outputs": ["audits_created"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_audit_cycle", "carbon_price": 80.0}
                    },
                    {
                        "task_id": "run_optimize",
                        "assigned_agent": find_agent("optimize_logistics"),
                        "dependencies": ["run_calc"],
                        "priority": 2,
                        "validation_rules": ["has optimization_results"],
                        "expected_outputs": ["optimization_results"],
                        "retry_limit": 3,
                        "input_data": {"action": "optimize_logistics"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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

        # 5.5. Federated A2A Multi-Agent Collaboration Goal
        elif "a2a" in goal_lower or "federate" in goal_lower:
            return {
                "goal_model": {
                    "goal_id": "goal_a2a_federation",
                    "user_intent": "Execute federated supplier carbon audits",
                    "desired_outcome": "Authenticate with remote suppliers, negotiate access, cross-validate evidence with cert authority and logistics, and perform consensus audits",
                    "success_criteria": ["All remote supplier sessions executed", "Trust scores applied", "Consensus verified"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Connect with remote organizations, authenticate, negotiate Supplier C block, cross-validate evidence, and run calculations.",
                            "assumed_steps": ["discover_cards", "a2a_supplier_handshakes", "run_consensus", "run_calc", "run_audit", "run_optimize", "generate_response"],
                            "expected_dependencies": {
                                "a2a_supplier_handshakes": ["discover_cards"],
                                "run_consensus": ["a2a_supplier_handshakes"],
                                "run_calc": ["run_consensus"],
                                "run_audit": ["run_calc"],
                                "run_optimize": ["run_calc"],
                                "generate_response": ["run_audit", "run_optimize"]
                            },
                            "confidence": 0.98
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "execution_strategy": "A2A Federated Protocol",
                "tasks": [
                    {
                        "task_id": "discover_cards",
                        "assigned_agent": "SupplierAgent",
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": [],
                        "expected_outputs": ["discovered_agent_cards"],
                        "retry_limit": 3,
                        "input_data": {"action": "discover_cards"}
                    },
                    {
                        "task_id": "a2a_supplier_handshakes",
                        "assigned_agent": "SupplierAgent",
                        "dependencies": ["discover_cards"],
                        "priority": 2,
                        "validation_rules": ["has supplier_responses"],
                        "expected_outputs": ["supplier_responses"],
                        "retry_limit": 3,
                        "input_data": {"action": "a2a_supplier_handshakes"}
                    },
                    {
                        "task_id": "run_consensus",
                        "assigned_agent": "SupplierAgent",
                        "dependencies": ["a2a_supplier_handshakes"],
                        "priority": 3,
                        "validation_rules": ["has consensus_report"],
                        "expected_outputs": ["consensus_report"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_consensus"}
                    },
                    {
                        "task_id": "run_calc",
                        "assigned_agent": "CarbonCalculationAgent",
                        "dependencies": ["run_consensus"],
                        "priority": 4,
                        "validation_rules": ["has processed_count"],
                        "expected_outputs": ["processed_count"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_calculation_cycle"}
                    },
                    {
                        "task_id": "run_audit",
                        "assigned_agent": "ComplianceAgent",
                        "dependencies": ["run_calc"],
                        "priority": 5,
                        "validation_rules": ["has audits_created"],
                        "expected_outputs": ["audits_created"],
                        "retry_limit": 3,
                        "input_data": {"action": "run_audit_cycle", "carbon_price": 80.0}
                    },
                    {
                        "task_id": "run_optimize",
                        "assigned_agent": "OptimizationAgent",
                        "dependencies": ["run_calc"],
                        "priority": 5,
                        "validation_rules": ["has optimization_results"],
                        "expected_outputs": ["optimization_results"],
                        "retry_limit": 3,
                        "input_data": {"action": "optimize_logistics"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": "ConversationAgent",
                        "dependencies": ["run_audit", "run_optimize"],
                        "priority": 6,
                        "validation_rules": ["has answer"],
                        "expected_outputs": ["answer"],
                        "retry_limit": 3,
                        "input_data": {"action": "generate_response"}
                    }
                ],
                "edges": [
                    {"from": "discover_cards", "to": "a2a_supplier_handshakes"},
                    {"from": "a2a_supplier_handshakes", "to": "run_consensus"},
                    {"from": "run_consensus", "to": "run_calc"},
                    {"from": "run_calc", "to": "run_audit"},
                    {"from": "run_calc", "to": "run_optimize"},
                    {"from": "run_audit", "to": "generate_response"},
                    {"from": "run_optimize", "to": "generate_response"}
                ]
            }

        # 6. Default General Summary Goal
        else:
            return {
                "goal_model": {
                    "goal_id": "goal_default",
                    "user_intent": "General summary metrics request",
                    "desired_outcome": "Provide current total emissions summary",
                    "success_criteria": ["Total Scope 3 emissions returned"],
                    "remaining_unknowns": []
                },
                "planning_hypothesis": {
                    "hypotheses": [
                        {
                            "hypothesis_text": "H1: Retrieve total emissions metrics from db.",
                            "assumed_steps": ["get_total_emissions", "generate_response"],
                            "expected_dependencies": {},
                            "confidence": 0.99
                        }
                    ],
                    "selected_hypothesis_index": 0,
                    "discarded_hypotheses": []
                },
                "execution_strategy": "Fast Path",
                "tasks": [
                    {
                        "task_id": "get_total_emissions",
                        "assigned_agent": find_agent("get_total_emissions"),
                        "dependencies": [],
                        "priority": 1,
                        "validation_rules": ["has total_emissions_tCO2"],
                        "expected_outputs": ["total_emissions_tCO2"],
                        "retry_limit": 3,
                        "input_data": {"action": "get_total_emissions"}
                    },
                    {
                        "task_id": "generate_response",
                        "assigned_agent": find_agent("generate_response"),
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

    def _estimate_cost(self, agent_name: str) -> float:
        costs = {
            "PlannerAgent": 0.05,
            "CarbonCalculationAgent": 0.01,
            "ComplianceAgent": 0.02,
            "OptimizationAgent": 0.02,
            "SupplierAgent": 0.01,
            "ConversationAgent": 0.01,
            "ReflectionAgent": 0.03
        }
        return costs.get(agent_name, 0.0)
