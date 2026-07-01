import time
import logging
from typing import Dict, List
from agents.base_agent import BaseAgent
from agents.shared_state import ExecutionState, Task, TaskResult, AgentDecision, ExecutionTimelineEvent, ExecutionReport
from agents.planner_agent import PlannerAgent

logger = logging.getLogger("ExecutionEngine")

class ExecutionEngine:
    def __init__(self, planner: PlannerAgent, agents: Dict[str, BaseAgent]):
        self.planner = planner
        self.agents = agents

    def run(self, state: ExecutionState) -> ExecutionReport:
        start_time = time.time()
        state.current_status = "RUNNING"
        logger.info(f"Starting execution engine for goal: '{state.user_goal}'")
        
        retries_count = 0
        
        while True:
            # 1. Identify tasks that are PENDING and have all dependencies completed in task_history
            ready_tasks = []
            for task in state.current_tasks:
                if task.execution_status == "PENDING":
                    deps_met = True
                    for dep_id in task.dependencies:
                        dep_res = state.task_history.get(dep_id)
                        if not dep_res or dep_res.execution_status != "COMPLETED":
                            deps_met = False
                            break
                    if deps_met:
                        ready_tasks.append(task)
            
            # 2. Check for completion or deadlock
            if not ready_tasks:
                active_or_pending = [t for t in state.current_tasks if t.execution_status in ["PENDING", "RUNNING"]]
                if active_or_pending:
                    state.current_status = "FAILED"
                    state.errors.append("Execution graph deadlock: some tasks have unresolved dependencies.")
                    logger.error("Execution graph deadlock detected.")
                    break
                else:
                    state.current_status = "SUCCESS"
                    logger.info("All tasks executed successfully.")
                    break
            
            # Sort by priority (higher priority first)
            ready_tasks.sort(key=lambda t: t.priority, reverse=True)
            task_to_run = ready_tasks[0]
            
            task_to_run.execution_status = "RUNNING"
            
            # Log timeline event
            start_event = ExecutionTimelineEvent(
                agent_name=task_to_run.assigned_agent,
                action="start",
                message=f"Starting task {task_to_run.task_id} assigned to {task_to_run.assigned_agent}."
            )
            state.execution_timeline.append(start_event)
            
            # Resolve target agent
            agent = self.agents.get(task_to_run.assigned_agent)
            if not agent:
                err_msg = f"Agent '{task_to_run.assigned_agent}' not registered in engine."
                task_result = TaskResult(
                    task_id=task_to_run.task_id,
                    execution_status="FAILED",
                    error_message=err_msg,
                    execution_time=0.0
                )
            else:
                try:
                    # Execute planning phase
                    task_to_run = agent.plan(state, task_to_run)
                    
                    # Execute task
                    t_start = time.time()
                    task_result = agent.execute(state, task_to_run)
                    t_elapsed = time.time() - t_start
                    
                    if task_result.execution_time == 0.0:
                        task_result.execution_time = t_elapsed
                    
                    # Validate output
                    is_valid = agent.validate(state, task_result)
                    if not is_valid:
                        task_result.execution_status = "FAILED"
                        task_result.error_message = "Output validation rules failed."
                        
                except Exception as ex:
                    task_result = TaskResult(
                        task_id=task_to_run.task_id,
                        execution_status="FAILED",
                        error_message=str(ex),
                        execution_time=time.time() - t_start,
                        confidence=0.0
                    )

            # Record task metadata back onto Task definition
            task_to_run.execution_time = task_result.execution_time
            task_to_run.confidence = task_result.confidence
            
            # 3. Active feedback loop: Ask Planner to evaluate results and determine the next step
            decision = self.planner.evaluate_task_result(state, task_to_run, task_result)
            logger.info(f"Planner decision for {task_to_run.task_id}: {decision.decision} - {decision.reasoning}")
            
            if decision.decision == "CONTINUE":
                task_to_run.execution_status = "COMPLETED"
                state.task_history[task_to_run.task_id] = task_result
                state.confidence_history.append(task_result.confidence)
                
                end_event = ExecutionTimelineEvent(
                    agent_name=task_to_run.assigned_agent,
                    action="completed",
                    duration=task_result.execution_time,
                    message=f"Task {task_to_run.task_id} completed. Decision: CONTINUE."
                )
                state.execution_timeline.append(end_event)
                
            elif decision.decision == "RETRY":
                task_to_run.execution_status = "PENDING"
                task_to_run.retry_count += 1
                retries_count += 1
                
                retry_event = ExecutionTimelineEvent(
                    agent_name=task_to_run.assigned_agent,
                    action="retry",
                    message=f"Task {task_to_run.task_id} failed. Retrying (Attempt {task_to_run.retry_count})."
                )
                state.execution_timeline.append(retry_event)
                
            elif decision.decision == "SKIP":
                task_to_run.execution_status = "SKIPPED"
                state.task_history[task_to_run.task_id] = task_result
                
                skip_event = ExecutionTimelineEvent(
                    agent_name=task_to_run.assigned_agent,
                    action="skipped",
                    message=f"Task {task_to_run.task_id} skipped by Planner decision."
                )
                state.execution_timeline.append(skip_event)
                
            elif decision.decision == "INSERT_TASKS":
                task_to_run.execution_status = "COMPLETED"
                state.task_history[task_to_run.task_id] = task_result
                
                if decision.next_recommended_agent:
                    new_task_id = f"inserted_{decision.next_recommended_agent.lower()}_{len(state.current_tasks)}"
                    new_task = Task(
                        task_id=new_task_id,
                        assigned_agent=decision.next_recommended_agent,
                        dependencies=[task_to_run.task_id],
                        input_data={"action": "run"}
                    )
                    state.current_tasks.append(new_task)
                    state.execution_graph["nodes"].append(new_task_id)
                    state.execution_graph["edges"].append({"from": task_to_run.task_id, "to": new_task_id})
                    
                    # Update ConversationAgent dependency so it runs last
                    for t in state.current_tasks:
                        if t.assigned_agent == "ConversationAgent":
                            t.dependencies.append(new_task_id)
                            state.execution_graph["edges"].append({"from": new_task_id, "to": t.task_id})
                            
                    insert_event = ExecutionTimelineEvent(
                        agent_name="PlannerAgent",
                        action="insert_tasks",
                        message=f"Dynamically inserted new task: {new_task_id} assigned to {decision.next_recommended_agent}."
                    )
                    state.execution_timeline.append(insert_event)
                    
            elif decision.decision == "TERMINATE":
                task_to_run.execution_status = "FAILED"
                state.task_history[task_to_run.task_id] = task_result
                state.current_status = "FAILED"
                state.errors.append(f"Execution terminated on task {task_to_run.task_id}. Reason: {decision.reasoning}")
                
                term_event = ExecutionTimelineEvent(
                    agent_name=task_to_run.assigned_agent,
                    action="terminated",
                    message=f"Execution terminated due to failure on {task_to_run.task_id}."
                )
                state.execution_timeline.append(term_event)
                break

        # Calculate final metrics and build report
        total_duration = time.time() - start_time
        succeeded = sum([1 for t in state.current_tasks if t.execution_status == "COMPLETED"])
        failed = sum([1 for t in state.current_tasks if t.execution_status == "FAILED"])
        skipped = sum([1 for t in state.current_tasks if t.execution_status == "SKIPPED"])
        
        avg_conf = sum(state.confidence_history) / len(state.confidence_history) if state.confidence_history else 1.0
        state.overall_confidence = avg_conf
        
        agent_costs = 0.0
        for t in state.current_tasks:
            if t.execution_status in ["COMPLETED", "FAILED"] and t.assigned_agent in self.agents:
                agent_costs += self.agents[t.assigned_agent].metadata.estimated_cost
                
        report = ExecutionReport(
            goal=state.user_goal,
            status=state.current_status,
            total_tasks=len(state.current_tasks),
            succeeded_tasks=succeeded,
            failed_tasks=failed,
            skipped_tasks=skipped,
            retries_count=retries_count,
            agent_costs=round(agent_costs, 4),
            execution_time=round(total_duration, 3),
            overall_confidence=round(avg_conf, 2),
            reasoning_summary=state.agent_decisions[-1].reasoning if state.agent_decisions else "Execution finished."
        )
        
        return report
