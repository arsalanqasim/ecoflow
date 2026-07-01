import logging
from agents.planner_agent import PlannerAgent
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.optimization_agent import OptimizationAgent
from agents.supplier_agent import SupplierAgent
from agents.conversation_agent import ConversationAgent
from agents.reflection_agent import ReflectionAgent
from agents.engine import ExecutionEngine

logger = logging.getLogger("CarbonAnalysisAgent")

class CarbonAnalysisAgent:
    """
    CarbonAnalysisAgent adapter that preserves the original API interface.
    It routes calculation cycles through the multi-agent task execution engine.
    """
    def __init__(self):
        self.agent_name = "CarbonAnalysisAgent"
        logger.info(f"{self.agent_name} initialized.")

    def run_calculation_cycle(self) -> dict:
        logger.info("Executing carbon calculation cycle via multi-agent engine...")
        
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
            # Plan and execute
            state = planner.plan_goal("Run carbon calculation cycle for unprocessed shipments", agents_metadata)
            engine = ExecutionEngine(planner, agents_registry)
            report = engine.run(state)

            # Find output in completed carbon calculation task
            calc_task_res = state.task_history.get("run_calc")
            if not calc_task_res:
                # Find any calculation task
                for t_id, res in state.task_history.items():
                    if "processed_count" in res.output_data:
                        calc_task_res = res
                        break

            if calc_task_res and calc_task_res.execution_status == "COMPLETED":
                return {
                    "status": "success",
                    "processed_count": calc_task_res.output_data.get("processed_count", 0)
                }
            else:
                error_msg = state.errors[-1] if state.errors else "Calculation cycle task did not complete successfully."
                return {"status": "error", "message": error_msg}

        except Exception as e:
            logger.error(f"Error running carbon calculation multi-agent loop: {e}")
            return {"status": "error", "message": str(e)}
