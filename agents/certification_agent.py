import logging
import time
from typing import List, Dict, Any
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult
from agents.a2a_directory import a2a_directory

logger = logging.getLogger("CertificationAgent")

class CertificationAgent(BaseAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="CertificationAgent",
            description="Federated agent interfacing with external Certification Authorities to verify supplier ISO status and validate carbon footprints.",
            capabilities=["verify_supplier_certification", "validate_carbon_declaration"],
            required_inputs=["supplier_name"],
            produced_outputs=["certification_status"],
            estimated_cost=0.01,
            estimated_latency=1.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing A2A task: {task.task_id} ({task.assigned_agent})")
        
        supplier_name = task.input_data.get("supplier_name", "")
        simulate_failure = task.input_data.get("simulate_failure")
        
        try:
            # 1. Discover the Certification Agent Card in the Directory
            card = a2a_directory.get_agent_card("Certification_Authority")
            if not card:
                raise ValueError("Certification Authority not found in A2A directory.")
                
            # Log selection explainability
            state.mcp_selection_decisions.append({
                "agent_name": self.metadata.agent_name,
                "query": "Certification Authority capability",
                "selected_tool": "a2a_endpoint:Certification_Authority",
                "reasoning": f"Selected remote agent {card.identity.organization_name} (Trust Score: {card.trust_metadata.initial_trust_score}) to verify standard compliance and certifications.",
                "expected_reliability": card.trust_metadata.initial_trust_score,
                "timestamp": time.time()
            })
            
            # 2. Authenticate and retrieve data via A2A request
            payload = {
                "auth_token": "CERT_SECURE_TOKEN_2025",
                "supplier_name": supplier_name
            }
            if simulate_failure:
                payload["simulate_failure"] = simulate_failure
                
            session = a2a_directory.get_or_create_session("Certification_Authority", state)
            
            # Ensure session is authenticated with appropriate permission
            session.authenticate("EcoFlow Corp", "CERT_SECURE_TOKEN_2025")
            session.permission_grants.append("READ_CERTIFICATION")
            
            response = a2a_directory.send_remote_message(
                remote_org="Certification_Authority",
                request_type="Verification Request",
                payload=payload,
                state=state
            )
            
            # 3. Handle response validation
            if not response or "status" not in response:
                raise ValueError("Malformed response received from remote Certification Agent.")
                
            state.mcp_validation_events.append({
                "tool_name": "a2a_endpoint:Certification_Authority",
                "is_valid": True,
                "message": f"Successfully verified certification status for supplier: {supplier_name}",
                "timestamp": time.time()
            })
            
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"certification_status": response},
                execution_time=elapsed,
                confidence=1.0 if response.get("is_certified") else 0.5
            )
            
        except Exception as e:
            logger.error(f"A2A Communication failure with Certification Agent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )
