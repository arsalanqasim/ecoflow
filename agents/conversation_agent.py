import os
import logging
import time
from typing import List
from agents.base_agent import BaseAgent, AgentMetadata
from agents.shared_state import ExecutionState, Task, TaskResult
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger("ConversationAgent")

class ConversationAgent(BaseAgent):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            try:
                self.genai_client = genai.Client()
                logger.info("ConversationAgent initialized with Gemini Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client in ConversationAgent: {e}. Fallback templates will be used.")
                self.genai_client = None
        else:
            logger.info("ConversationAgent initialized. Using template responses (No GEMINI_API_KEY found).")
            self.genai_client = None

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            agent_name="ConversationAgent",
            description="Responsible ONLY for translating structured agent outputs and metrics into friendly, conversational natural language responses.",
            capabilities=["generate_response"],
            required_inputs=["task_history"],
            produced_outputs=["final_natural_language_response"],
            estimated_cost=0.01,
            estimated_latency=1.0
        )

    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        start_time = time.time()
        logger.info(f"Executing task: {task.task_id} ({task.assigned_agent})")
        
        try:
            # Gather inputs from previous task outputs or shared state
            history = state.task_history
            goal = state.user_goal
            
            # Deterministic fallbacks to match exact testing/original patterns
            answer = ""
            charts = []
            
            # Look at executed tasks to build response
            top_emitter_task = history.get("get_top_emitter")
            forecast_task = history.get("run_forecast") or history.get("get_historical_emissions")
            cbam_task = history.get("get_cbam_liabilities")
            total_emissions_task = history.get("get_total_emissions")
            
            # 1. Top Emitter Response
            if top_emitter_task and top_emitter_task.execution_status == "COMPLETED" and "top_emitting_supplier" in top_emitter_task.output_data:
                data = top_emitter_task.output_data
                supplier_name = data.get("supplier_name", "Unknown")
                total_emissions = data.get("total_emissions", 0.0)
                compliance_status = data.get("compliance_status", "UNKNOWN")
                
                if supplier_name is None:
                    answer = "No supplier emissions calculations have been computed yet."
                else:
                    answer = (
                        f"The supplier with the highest Scope 3 carbon footprint is **{supplier_name}** "
                        f"with a total of **{total_emissions:.2f} tCO2** emitted. "
                        f"Current compliance status: **{compliance_status}**."
                    )
            
            # 2. Forecasting Response
            elif forecast_task and forecast_task.execution_status == "COMPLETED" and "forecast_res" in forecast_task.output_data:
                forecast_res = forecast_task.output_data["forecast_res"]
                
                answer = "Here is the Scope 3 emissions forecast for the next 4 months based on historical shipment logs:\n"
                for entry in forecast_res:
                    answer += f"- **{entry['date']}**: {entry['predicted_emission_tCO2']:.2f} tCO2\n"
                
                charts = [{
                    "type": "forecast",
                    "data": forecast_res
                }]
                
            # 3. CBAM Liabilities Response
            elif cbam_task and cbam_task.execution_status == "COMPLETED" and "cbam_liabilities_eur" in cbam_task.output_data:
                sum_tariff = cbam_task.output_data["cbam_liabilities_eur"]
                answer = (
                    f"The total audited border adjustment (CBAM) tariff liability for imported shipments is "
                    f"**€{sum_tariff:,.2f}**. This matches current EU import tariff carbon pricing constraints."
                )
                
            # 4. Default Summary Response
            elif total_emissions_task and total_emissions_task.execution_status == "COMPLETED" and "total_emissions_tCO2" in total_emissions_task.output_data:
                sum_emissions = total_emissions_task.output_data["total_emissions_tCO2"]
                answer = (
                    f"Welcome! I am your EcoFlow sustainability assistant. "
                    f"Currently, we are tracking a total of **{sum_emissions:.2f} tCO2** of Scope 3 emissions "
                    f"across your supply chain network. Ask me about 'forecasting future emissions', "
                    f"'highest emitting supplier', or 'total CBAM liabilities' for deeper audit details!"
                )
            
            # Use Gemini to polish the response if the client is initialized, but preserve exact values
            if self.genai_client and answer:
                try:
                    prompt = (
                        f"Rewrite the following response to make it more natural and engaging while preserving "
                        f"ALL numbers, names, and markdown formatting. DO NOT change the values or critical facts.\n\n"
                        f"Original Answer:\n{answer}"
                    )
                    response = self.genai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    if response.text:
                        answer = response.text.strip()
                except APIError as api_err:
                    logger.warning(f"Gemini API returned error in ConversationAgent: {api_err}. Using fallback.")
                except Exception as e:
                    logger.warning(f"Failed to call Gemini API in ConversationAgent: {e}. Using fallback.")

            if not answer:
                answer = "Goal execution completed. Please check task results for details."

            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="COMPLETED",
                output_data={"answer": answer, "charts": charts},
                execution_time=elapsed,
                confidence=1.0
            )

        except Exception as e:
            logger.error(f"Error executing ConversationAgent: {e}")
            elapsed = time.time() - start_time
            return TaskResult(
                task_id=task.task_id,
                execution_status="FAILED",
                error_message=str(e),
                execution_time=elapsed,
                confidence=0.0
            )
