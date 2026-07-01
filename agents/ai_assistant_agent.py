import logging
from agents.planner_agent import PlannerAgent
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.optimization_agent import OptimizationAgent
from agents.supplier_agent import SupplierAgent
from agents.conversation_agent import ConversationAgent
from agents.reflection_agent import ReflectionAgent
from agents.engine import ExecutionEngine

logger = logging.getLogger("AIAssistantAgent")

class AIAssistantAgent:
    """
    AIAssistantAgent acts as the primary orchestrator interface for dashboard queries.
    It routes natural language requests to the reasoning-based multi-agent execution pipeline.
    """
    def __init__(self):
        self.agent_name = "AIAssistantAgent"
        logger.info(f"{self.agent_name} initialized.")

    def process_query(self, query: str, conversation_id: str = "default") -> dict:
        logger.info(f"Processing query: '{query}' via multi-agent orchestrator.")
        
        # Instantiate worker agents
        planner = PlannerAgent()
        carbon = CarbonCalculationAgent()
        compliance = ComplianceAgent()
        optimization = OptimizationAgent()
        supplier = SupplierAgent()
        conversation = ConversationAgent()
        reflection = ReflectionAgent()

        # Build registry
        agents_registry = {
            "CarbonCalculationAgent": carbon,
            "ComplianceAgent": compliance,
            "OptimizationAgent": optimization,
            "SupplierAgent": supplier,
            "ConversationAgent": conversation,
            "ReflectionAgent": reflection
        }

        # Gather metadata for planner
        agents_metadata = [
            carbon.metadata.dict(),
            compliance.metadata.dict(),
            optimization.metadata.dict(),
            supplier.metadata.dict(),
            conversation.metadata.dict(),
            reflection.metadata.dict()
        ]

        try:
            # 1. Plan the goal (creates state and DAG)
            state = planner.plan_goal(query, agents_metadata)

            # 2. Execute tasks using the engine
            engine = ExecutionEngine(planner, agents_registry)
            report = engine.run(state)

            logger.info(f"Execution report: {report.json()}")

            # 3. Retrieve response from ConversationAgent task
            conv_task_id = "generate_response"
            conv_result = state.task_history.get(conv_task_id)

            if conv_result and conv_result.execution_status == "COMPLETED":
                output_data = conv_result.output_data
                return {
                    "answer": output_data.get("answer", "Goal executed with no summary response."),
                    "charts": output_data.get("charts", []),
                    "status": "success"
                }
            else:
                error_msg = state.errors[-1] if state.errors else "Execution failed to produce a final response."
                return {
                    "answer": f"Execution failed: {error_msg}",
                    "charts": [],
                    "status": "error"
                }

        except Exception as e:
            logger.error(f"Error in multi-agent pipeline execution: {e}")
            return {
                "answer": f"An error occurred while executing the query agent: {e}",
                "charts": [],
                "status": "error"
            }
