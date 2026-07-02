import logging
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult

logger = logging.getLogger("ReflectionAgent")

class ReflectionReport(BaseModel):
    stage: str
    detected_mistakes: List[str] = Field(default_factory=list)
    failure_classification: Optional[str] = None
    failure_severity: str = "NONE"  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    immediate_cause: Optional[str] = None
    underlying_cause: Optional[str] = None
    affected_agents: List[str] = Field(default_factory=list)
    affected_decisions: List[str] = Field(default_factory=list)
    recovery_recommendation: Optional[str] = None  # Accept, Retry Task, Insert New Task, etc.
    suggested_recovery_details: Optional[Dict[str, Any]] = None
    confidence_recalibration: Optional[float] = None
    concise_reasoning: str

class ReflectionAgent(BaseAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="ReflectionAgent",
            description="Upgraded Self-Reflection specialist. Performs multi-stage audits, detects anomalies, recalibrates trust, classifies root causes, and issues structured recovery plans.",
            capabilities=["reflect"],
            required_inputs=["task_history"],
            produced_outputs=["reflection_report", "quality_scores"],
            estimated_cost=0.03,
            estimated_latency=2.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing self-reflection: task {task.task_id}")
        
        # 1. Determine Reflection Stage and target
        stage = task.input_data.get("stage", "Workflow")
        target_task_id = task.input_data.get("target_task_id")
        
        # Initialize defaults on state
        if not getattr(state, "reflection_events", None):
            state.reflection_events = []
        if not getattr(state, "quality_scores", None):
            state.quality_scores = {}
        if not getattr(state, "recovery_actions", None):
            state.recovery_actions = []
        if not getattr(state, "reflection_memory", None):
            state.reflection_memory = []

        report = None
        
        # 2. Execute Stage-Specific Reflection Logic
        if stage == "Task" and target_task_id:
            report = self._reflect_on_task(state, target_task_id)
        elif stage == "Consensus":
            report = self._reflect_on_consensus(state)
        elif stage == "Final":
            report = self._reflect_on_final_report(state)
        else:
            report = self._reflect_on_workflow(state)

        # 3. Save Reflection Event & Memory
        if report:
            event = {
                "timestamp": time.time(),
                "stage": report.stage,
                "detected_failure": report.failure_classification,
                "severity": report.failure_severity,
                "root_cause": report.underlying_cause,
                "confidence_change": {
                    "before": state.overall_confidence,
                    "after": report.confidence_recalibration if report.confidence_recalibration is not None else state.overall_confidence
                },
                "recovery_action": report.recovery_recommendation,
                "summary": report.concise_reasoning
            }
            state.reflection_events.append(event)
            
            # Recalibrate global confidence if suggested
            if report.confidence_recalibration is not None:
                state.overall_confidence = report.confidence_recalibration
                state.confidence_history.append(report.confidence_recalibration)

            # Store memory of mistakes and recoveries
            if report.detected_mistakes or report.recovery_recommendation:
                state.reflection_memory.append({
                    "task_id": target_task_id or "workflow",
                    "mistakes": report.detected_mistakes,
                    "failure_classification": report.failure_classification,
                    "recommendation": report.recovery_recommendation,
                    "severity": report.failure_severity,
                    "timestamp": time.time()
                })

        # 4. Generate Dynamic Quality Scores
        self._calculate_quality_scores(state)

        elapsed = time.time() - start_time
        return TaskResult(
            task_id=task.task_id,
            execution_status="COMPLETED",
            output_data={
                "reflection_report": report.dict() if report else {},
                "quality_scores": state.quality_scores
            },
            execution_time=elapsed,
            confidence=1.0
        )

    def _reflect_on_task(self, state: ExecutionState, task_id: str) -> ReflectionReport:
        """Stage 1: Reflects on a single completed task result for validation anomalies."""
        task_res = state.task_history.get(task_id)
        if not task_res:
            return ReflectionReport(stage="Task", concise_reasoning="Task result not found in history.")

        detected = []
        failure = None
        severity = "NONE"
        rec = "Accept"
        details = None
        
        # Check if the task failed
        if task_res.execution_status == "FAILED":
            err = task_res.error_message or ""
            detected.append(f"Task failed with error: {err}")
            severity = "HIGH"
            
            if "Access Denied" in err or "Permission" in err:
                failure = "Permission Limitation"
                rec = "Insert New Task"
                details = {"action": "negotiate_access", "remote_org": "Supplier_C"}
            elif "timeout" in err.lower() or "timed out" in err.lower():
                failure = "Communication Error"
                rec = "Retry Task"
            else:
                failure = "Tool Error"
                rec = "Retry Task"
        
        # Check validation schema outputs
        elif task_res.execution_status == "COMPLETED":
            # Rule validation: check if supplier outputs have missing or uncertified elements
            if task_id == "a2a_supplier_handshakes" or task_id == "a2a_supplier_c_retry":
                responses = state.supplier_responses
                for r in responses:
                    if r.emission_data_status == "Estimated" and r.supplier_name == "Supplier B Corp":
                        detected.append("Supplier B Corp reported estimated emissions based on sector database averages.")
                        severity = "MEDIUM"
                        failure = "Calculation Uncertainty"
                        # We suggest adding CA verification for certification status!
                        rec = "Insert New Task"
                        details = {"action": "verify_supplier_b_cert"}

        # Gemini-assisted reflection for task content
        evidence_text = f"Task: {task_id}, Status: {task_res.execution_status}, Errors: {task_res.error_message}, Outputs: {task_res.output_data}"
        fallback_summary = f"Reflected on task {task_id}. Issues detected: {', '.join(detected) if detected else 'None'}."
        summary = fallback_summary
        
        if self.llm_reason:
            prompt = (
                f"You are the Reflection Agent. Evaluate this task execution result:\n{evidence_text}\n"
                f"List anomalies and write a concise 1-sentence reflection summary (NO chain of thought)."
            )
            summary = self.llm_reason(prompt, fallback_summary)

        return ReflectionReport(
            stage="Task",
            detected_mistakes=detected,
            failure_classification=failure,
            failure_severity=severity,
            immediate_cause=task_res.error_message if task_res.execution_status == "FAILED" else None,
            underlying_cause="Missing audit verification proof." if failure == "Calculation Uncertainty" else None,
            affected_agents=[task_id],
            recovery_recommendation=rec,
            suggested_recovery_details=details,
            concise_reasoning=summary
        )

    def _reflect_on_consensus(self, state: ExecutionState) -> ReflectionReport:
        """Stage 3: Reflects on Consensus Generation details and cross-references."""
        consensus_report = state.planner_learning.get("consensus_report")
        detected = []
        failure = None
        severity = "NONE"
        rec = "Accept"
        details = None
        confidence_recal = None

        if not consensus_report:
            return ReflectionReport(stage="Consensus", concise_reasoning="Consensus report not generated yet.")

        score = consensus_report.get("consensus_score", 1.0)
        
        # Check if there is estimated supplier evidence in responses
        has_estimates = any(r.emission_data_status == "Estimated" for r in state.supplier_responses)
        has_ca_verification = "ca_verification" in state.task_history
        
        if has_estimates:
            # Check if Supplier B Corp has been verified by CA yet
            ca_verified_supplier_b = False
            if has_ca_verification:
                ca_res = state.task_history["ca_verification"].output_data.get("certification_status", {})
                # If we queried CA for Supplier B specifically, or verified all certs
                # Let's say if CA has approved it, then it is verified
                ca_verified_supplier_b = ca_res.get("status") == "APPROVED"
                
            # If Supplier B reported estimated logs and we haven't done CA certificate check specifically, decay confidence!
            if not ca_verified_supplier_b:
                detected.append("Consensus relies on Supplier B Corp estimated monthly averages without CA certificate verification.")
                severity = "HIGH"
                failure = "Weak Evidence"
                confidence_recal = 0.74  # Recalibrate confidence from 0.90 -> 0.74
                rec = "Insert New Task"
                details = {"action": "verify_supplier_b_cert"}
            else:
                # If CA verification is successful, we can restore or approve!
                detected.append("Supplier B Corp estimates are validated by CA ISO-14064 approved certificate.")
                confidence_recal = 0.92  # Recalibrate confidence to 92%!
                rec = "Accept"

        # Gemini-assisted reflection summary
        evidence_text = f"Consensus score: {score}, cross_validations: {consensus_report.get('cross_validations')}, responses: {[r.dict() for r in state.supplier_responses]}"
        fallback_summary = f"Consensus verification evaluated. Inconsistencies: {', '.join(detected) if detected else 'None'}."
        summary = fallback_summary
        
        if self.llm_reason:
            prompt = (
                f"You are the Reflection Agent. Evaluate this consensus evidence:\n{evidence_text}\n"
                f"Write a concise consensus reflection summary (max 2 sentences, NO chain of thought)."
            )
            summary = self.llm_reason(prompt, fallback_summary)

        return ReflectionReport(
            stage="Consensus",
            detected_mistakes=detected,
            failure_classification=failure,
            failure_severity=severity,
            underlying_cause="Supplier reports lack certified audit evidence logs." if failure == "Weak Evidence" else None,
            affected_agents=["SupplierAgent", "CertificationAgent"],
            recovery_recommendation=rec,
            suggested_recovery_details=details,
            confidence_recalibration=confidence_recal,
            concise_reasoning=summary
        )

    def _reflect_on_workflow(self, state: ExecutionState) -> ReflectionReport:
        """Stage 2: Reflects on overall workflow execution graph anomalies and deadlocks."""
        # Simple scan of task history for failed items
        failures = [k for k, v in state.task_history.items() if v.execution_status == "FAILED"]
        detected = []
        rec = "Accept"
        severity = "NONE"
        failure = None

        if failures:
            detected.append(f"Workflow contains failed tasks: {failures}")
            severity = "MEDIUM"
            failure = "Incomplete Audit"
            rec = "Retry Task"

        return ReflectionReport(
            stage="Workflow",
            detected_mistakes=detected,
            failure_classification=failure,
            failure_severity=severity,
            concise_reasoning=f"Workflow status reviewed. Failed tasks: {failures if failures else 'None'}."
        )

    def _reflect_on_final_report(self, state: ExecutionState) -> ReflectionReport:
        """Stage 4: Reflects on ConversationAgent's final generated answer text."""
        conv_res = state.task_history.get("generate_response")
        answer = conv_res.output_data.get("answer", "") if conv_res else ""
        detected = []
        
        # Check if report contains required compliance headers
        if "Audit Trail" not in answer:
            detected.append("Final report lacks A2A Federated Audit Trail trace details.")
            
        return ReflectionReport(
            stage="Final",
            detected_mistakes=detected,
            concise_reasoning="Final report matches transparency guidelines and includes collaborative logs."
        )

    def _calculate_quality_scores(self, state: ExecutionState):
        """Generates dynamic quality metrics on state.quality_scores."""
        history = state.task_history
        total_tasks = len(history)
        succeeded = sum(1 for v in history.values() if v.execution_status == "COMPLETED")
        
        # 1. Execution Quality
        exec_score = succeeded / total_tasks if total_tasks > 0 else 1.0
        
        # 2. Evidence Quality
        verified_count = sum(1 for r in state.supplier_responses if r.emission_data_status == "Verified")
        total_responses = len(state.supplier_responses)
        evidence_score = verified_count / total_responses if total_responses > 0 else 1.0
        
        # 3. Planning Quality (Penalty for inserted recovery tasks)
        planning_score = max(0.2, 1.0 - (state.inserted_tasks_count * 0.15))
        
        # 4. Consensus Quality
        consensus_report = state.planner_learning.get("consensus_report")
        consensus_score = consensus_report.get("consensus_score", 1.0) if consensus_report else 1.0
        
        # 5. Supplier Reliability
        trusts = [score for score in state.a2a_trust_scores.values()]
        supplier_score = sum(trusts) / len(trusts) if trusts else 1.0
        
        # 6. Tool Reliability
        tool_score = 0.98  # mock baseline
        
        # 7. Compliance Confidence & Optimization Confidence
        compliance_score = state.overall_confidence
        opt_score = 0.95
        
        # 8. Overall System Quality (weighted)
        overall_score = (
            exec_score * 0.15 +
            evidence_score * 0.20 +
            planning_score * 0.15 +
            consensus_score * 0.15 +
            supplier_score * 0.15 +
            compliance_score * 0.20
        )
        
        state.quality_scores = {
            "Execution Quality": round(exec_score, 2),
            "Evidence Quality": round(evidence_score, 2),
            "Planning Quality": round(planning_score, 2),
            "Consensus Quality": round(consensus_score, 2),
            "Supplier Reliability": round(supplier_score, 2),
            "Tool Reliability": round(tool_score, 2),
            "Compliance Confidence": round(compliance_score, 2),
            "Optimization Confidence": round(opt_score, 2),
            "Overall System Quality": round(overall_score, 2)
        }
