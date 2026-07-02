import time
import logging
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
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
        logger.info(f"Starting upgraded executive engine for goal: '{state.user_goal}'")
        
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
            
            # Sort ready tasks by priority (higher priority first)
            ready_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            # Log scheduling timeline event
            logger.info(f"Scheduling {len(ready_tasks)} ready tasks: {[t.task_id for t in ready_tasks]}")
            
            # Define helper function to execute a single task in thread pool
            def execute_single_task(t: Task) -> tuple[Task, TaskResult]:
                # Log start event
                start_event = ExecutionTimelineEvent(
                    agent_name=t.assigned_agent,
                    action="start",
                    message=f"Starting task {t.task_id} assigned to {t.assigned_agent} (Priority: {t.priority})."
                )
                state.execution_timeline.append(start_event)
                
                agent = self.agents.get(t.assigned_agent)
                if not agent:
                    return t, TaskResult(
                        task_id=t.task_id,
                        execution_status="FAILED",
                        error_message=f"Agent '{t.assigned_agent}' not registered in engine."
                    )
                try:
                    # Plan
                    t_planned = agent.plan(state, t)
                    
                    # Execute
                    t_start = time.time()
                    task_res = agent.execute(state, t_planned)
                    t_elapsed = time.time() - t_start
                    
                    if task_res.execution_time == 0.0:
                        task_res.execution_time = t_elapsed
                        
                    # Validate
                    is_valid = agent.validate(state, task_res)
                    if not is_valid:
                        task_res.execution_status = "FAILED"
                        task_res.error_message = "Output validation rules failed."
                        
                    return t_planned, task_res
                except Exception as ex:
                    return t, TaskResult(
                        task_id=t.task_id,
                        execution_status="FAILED",
                        error_message=str(ex),
                        confidence=0.0
                    )

            # 3. Schedule all ready tasks in parallel
            with ThreadPoolExecutor(max_workers=max(1, len(ready_tasks))) as executor:
                futures = [executor.submit(execute_single_task, t) for t in ready_tasks]
                batch_results = [f.result() for f in futures]

            # 4. Sequentially process outcomes and consult Planner loop
            should_terminate = False
            for t_run, t_res in batch_results:
                # Update task execution details
                t_run.execution_time = t_res.execution_time
                t_run.confidence = t_res.confidence
                
                # Active feedback loop: Ask Planner to evaluate result
                decision = self.planner.evaluate_task_result(state, t_run, t_res)
                logger.info(f"Planner decision for {t_run.task_id}: {decision.decision} - {decision.reasoning}")
                
                if decision.decision == "CONTINUE":
                    t_run.execution_status = "COMPLETED"
                    state.task_history[t_run.task_id] = t_res
                    
                    end_event = ExecutionTimelineEvent(
                        agent_name=t_run.assigned_agent,
                        action="completed",
                        duration=t_res.execution_time,
                        message=f"Task {t_run.task_id} completed successfully. Decision: CONTINUE."
                    )
                    state.execution_timeline.append(end_event)
                    
                elif decision.decision == "RETRY":
                    t_run.execution_status = "PENDING"
                    t_run.retry_count += 1
                    retries_count += 1
                    
                    retry_event = ExecutionTimelineEvent(
                        agent_name=t_run.assigned_agent,
                        action="retry",
                        message=f"Task {t_run.task_id} failed. Retrying (Attempt {t_run.retry_count})."
                    )
                    state.execution_timeline.append(retry_event)
                    
                elif decision.decision == "SKIP":
                    t_run.execution_status = "SKIPPED"
                    state.task_history[t_run.task_id] = t_res
                    
                    skip_event = ExecutionTimelineEvent(
                        agent_name=t_run.assigned_agent,
                        action="skipped",
                        message=f"Task {t_run.task_id} skipped by Planner decision."
                    )
                    state.execution_timeline.append(skip_event)
                    
                elif decision.decision == "INSERT_TASKS":
                    t_run.execution_status = "COMPLETED"
                    state.task_history[t_run.task_id] = t_res
                    
                    insert_event = ExecutionTimelineEvent(
                        agent_name="PlannerAgent",
                        action="insert_tasks",
                        message=f"Planner inserted tasks. Reason: {decision.reasoning}"
                    )
                    state.execution_timeline.append(insert_event)
                        
                elif decision.decision == "TERMINATE":
                    t_run.execution_status = "FAILED"
                    state.task_history[t_run.task_id] = t_res
                    state.current_status = "FAILED"
                    state.errors.append(f"Execution terminated on task {t_run.task_id}. Reason: {decision.reasoning}")
                    
                    term_event = ExecutionTimelineEvent(
                        agent_name=t_run.assigned_agent,
                        action="terminated",
                        message=f"Execution terminated due to failure on {t_run.task_id}."
                    )
                    state.execution_timeline.append(term_event)
                    should_terminate = True
                    break
            
            if should_terminate:
                break

        # Calculate final metrics and build report
        total_duration = time.time() - start_time
        succeeded = sum([1 for t in state.current_tasks if t.execution_status == "COMPLETED"])
        failed = sum([1 for t in state.current_tasks if t.execution_status == "FAILED"])
        skipped = sum([1 for t in state.current_tasks if t.execution_status == "SKIPPED"])
        
        avg_conf = sum(state.confidence_history) / len(state.confidence_history) if state.confidence_history else 1.0
        state.overall_confidence = avg_conf
        
        agent_costs = state.planner_learning.get("agent_costs", 0.0)
        
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
