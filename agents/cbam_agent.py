import logging
from agents.planner_agent import PlannerAgent
from agents.carbon_calc_agent import CarbonCalculationAgent
from agents.compliance_agent import ComplianceAgent
from agents.optimization_agent import OptimizationAgent
from agents.supplier_agent import SupplierAgent
from agents.conversation_agent import ConversationAgent
from agents.reflection_agent import ReflectionAgent
from agents.engine import ExecutionEngine

logger = logging.getLogger("CBAMAuditAgent")

class CBAMAuditAgent:
    """
    CBAMAuditAgent adapter that preserves the original API interface.
    It routes compliance audits through the multi-agent task execution engine.
    """
    def __init__(self):
        self.agent_name = "CBAMAuditAgent"
        logger.info(f"{self.agent_name} initialized.")

    def run_audit_cycle(self, carbon_price: float = 80.0) -> dict:
        logger.info("Executing CBAM compliance audit cycle via multi-agent engine...")
        
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
            state = planner.plan_goal("Run compliance audit cycle for emissions", agents_metadata)
            
            # Pass carbon_price parameter dynamically into the compliance task's input_data
            for task in state.current_tasks:
                if task.assigned_agent == "ComplianceAgent":
                    task.input_data["carbon_price"] = carbon_price
                    
            engine = ExecutionEngine(planner, agents_registry)
            report = engine.run(state)

            # Find output in completed compliance audit task
            audit_task_res = state.task_history.get("run_audit")
            if not audit_task_res:
                # Find any compliance task
                for t_id, res in state.task_history.items():
                    if "audits_created" in res.output_data:
                        audit_task_res = res
                        break

            if audit_task_res and audit_task_res.execution_status == "COMPLETED":
                return {
                    "status": "success",
                    "audits_created": audit_task_res.output_data.get("audits_created", 0)
                }
            else:
                error_msg = state.errors[-1] if state.errors else "Compliance audit cycle task did not complete successfully."
                return {"status": "error", "message": error_msg}

        except Exception as e:
            logger.error(f"Error running compliance audit multi-agent loop: {e}")
            return {"status": "error", "message": str(e)}
