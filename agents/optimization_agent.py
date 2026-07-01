import os
import logging
import time
from typing import List
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult, OptimizationResult
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger("OptimizationAgent")

class OptimizationAgent(BaseAgent):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            try:
                self.genai_client = genai.Client()
                logger.info("OptimizationAgent initialized with Gemini Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client in OptimizationAgent: {e}. Fallback templates will be used.")
                self.genai_client = None
        else:
            logger.info("OptimizationAgent initialized. Using template rule-based logic (No GEMINI_API_KEY found).")
            self.genai_client = None

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="OptimizationAgent",
            description="Consumes carbon footprint results and generates logistics alternative optimization routes and methods to reduce emissions.",
            capabilities=["optimize_logistics"],
            required_inputs=["carbon_results"],
            produced_outputs=["optimization_results"],
            estimated_cost=0.02,
            estimated_latency=2.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing task: {task.task_id} ({task.assigned_agent})")
        
        try:
            # We can read from the state's carbon results
            carbon_results = state.carbon_results
            if not carbon_results:
                elapsed = time.time() - start_time
                return TaskResult(
                    task_id=task.task_id,
                    execution_status="COMPLETED",
                    output_data={"optimization_results": [], "message": "No carbon results to optimize."},
                    execution_time=elapsed,
                    confidence=1.0
                )

            optimization_results = []
            
            # Formulate optimization recommendation for top emitters or shipments
            # For simplicity, optimize the first 5 emitters or sum them
            for cr in carbon_results[:5]:
                # Propose road -> rail, or air -> sea, saving 40% emissions
                original = cr.emission_tCO2
                optimized = original * 0.6  # 40% savings
                savings_t = original - optimized
                
                opt_res = OptimizationResult(
                    shipment_id=cr.shipment_id,
                    original_emissions=original,
                    optimized_emissions=optimized,
                    alternative_carrier="GreenFreight Eco-Rail",
                    alternative_route="Direct Rail Transit Corridor",
                    savings_tCO2=round(savings_t, 2),
                    savings_percent=40.0
                )
                optimization_results.append(opt_res)

            # Generate optimization text summary using Gemini if available
            summary = self.generate_optimization_summary(optimization_results)
            state.optimization_results.extend(optimization_results)
            
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={
                    "optimization_results": [r.dict() for r in optimization_results],
                    "optimization_summary": summary
                },
                execution_time=elapsed,
                confidence=0.9
            )

        except Exception as e:
            logger.error(f"Error executing OptimizationAgent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )

    def generate_optimization_summary(self, results: List[OptimizationResult]) -> str:
        if not results:
            return "No optimizations proposed."
            
        total_savings = sum([r.savings_tCO2 for r in results])
        
        prompt = (
            f"Write a concise logistics optimization summary (max 3 sentences) suggesting alternatives "
            f"to reduce emissions. Total potential savings: {total_savings:.2f} tCO2 across {len(results)} shipments "
            f"by transitioning to alternative carriers like GreenFreight Eco-Rail."
        )

        if self.genai_client:
            try:
                response = self.genai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response.text:
                    return response.text.strip()
            except APIError as api_err:
                logger.warning(f"Gemini API returned error in OptimizationAgent: {api_err}. Falling back to template.")
            except Exception as e:
                logger.warning(f"Failed to call Gemini API in OptimizationAgent: {e}. Falling back to template.")

        return (
            f"Decarbonization target identified: Transitioning shipments to eco-rail corridors is estimated "
            f"to save approximately {total_savings:.2f} tCO2 (a 40% reduction). Recommendation: Re-route long-haul "
            f"segments through GreenFreight Eco-Rail networks."
        )
