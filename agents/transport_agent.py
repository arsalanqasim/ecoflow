import logging
import time
from typing import List, Dict, Any
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult
from agents.a2a_directory import a2a_directory

logger = logging.getLogger("TransportAgent")

class TransportAgent(BaseAgent):
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="TransportAgent",
            description="Federated agent interfacing with third-party logistics (3PL) providers to verify shipping paths, carrier certifications, and fuel sources.",
            capabilities=["get_shipping_emissions", "verify_route"],
            required_inputs=["shipment_id"],
            produced_outputs=["logistics_metrics"],
            estimated_cost=0.01,
            estimated_latency=0.8
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing A2A task: {task.task_id} ({task.assigned_agent})")
        
        shipment_id = task.input_data.get("shipment_id")
        simulate_failure = task.input_data.get("simulate_failure")
        
        try:
            # 1. Discover Logistics Agent Card in Directory
            card = a2a_directory.get_agent_card("Logistics_Provider")
            if not card:
                raise ValueError("Logistics Provider not found in A2A directory.")
                
            # Log selection explainability
            state.mcp_selection_decisions.append({
                "agent_name": self.metadata.agent_name,
                "query": "Logistics Provider capability",
                "selected_tool": "a2a_endpoint:Logistics_Provider",
                "reasoning": f"Selected logistics agent {card.identity.organization_name} (Trust Score: {card.trust_metadata.initial_trust_score}) to retrieve routing emissions and carrier certifications.",
                "expected_reliability": card.trust_metadata.initial_trust_score,
                "timestamp": time.time()
            })
            
            # 2. Authenticate and retrieve data via A2A request
            payload = {
                "auth_token": "LOGISTICS_SECURE_TOKEN_2025",
                "shipment_id": shipment_id
            }
            if simulate_failure:
                payload["simulate_failure"] = simulate_failure
                
            session = a2a_directory.get_or_create_session("Logistics_Provider", state)
            session.authenticate("EcoFlow Corp", "LOGISTICS_SECURE_TOKEN_2025")
            session.permission_grants.append("READ_TRANSPORT")
            
            response = a2a_directory.send_remote_message(
                remote_org="Logistics_Provider",
                request_type="Carbon Data Request",
                payload=payload,
                state=state
            )
            
            # 3. Handle response validation
            if not response or "shipping_emissions_tCO2" not in response:
                raise ValueError("Malformed response received from Logistics Provider Agent.")
                
            state.mcp_validation_events.append({
                "tool_name": "a2a_endpoint:Logistics_Provider",
                "is_valid": True,
                "message": f"Successfully verified green transport emissions for shipment {shipment_id}",
                "timestamp": time.time()
            })
            
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"logistics_metrics": response},
                execution_time=elapsed,
                confidence=0.95
            )
            
        except Exception as e:
            logger.error(f"A2A Communication failure with Logistics Provider: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )
