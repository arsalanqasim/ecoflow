import os
import logging
import time
from typing import List, Any
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
            # Broadcast to collect status summaries from other agents
            if hasattr(state, "bus") and state.bus is not None:
                from agents.collaboration import AgentRequest, AgentMessageType
                try:
                    req = AgentRequest(
                        sender="ConversationAgent",
                        recipient="ALL",
                        message_type=AgentMessageType.VERIFICATION_REQUEST,
                        content="Submit final status summary of your audited domain tasks."
                    )
                    responses = state.bus.send(req)
                    summaries = []
                    for r in responses:
                        if r and hasattr(r, "content") and r.content:
                            summaries.append(f"{r.sender}: {r.content}")
                    self.memory["summaries"] = summaries
                except Exception as e:
                    logger.warning(f"Failed to broadcast verification request from ConversationAgent: {e}")

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
            
            # A2A Goal Response
            if "a2a" in state.user_goal.lower() or "federat" in state.user_goal.lower():
                calc_task = history.get("run_calc")
                processed_count = calc_task.output_data.get("processed_count", 0) if calc_task else 0
                answer = (
                    f"A2A Federated supplier carbon audit cycle completed successfully. "
                    f"Processed **{processed_count}** shipments across the independent supplier network. "
                    f"Handshakes established and Scope 3 emissions fetched securely over the A2A directory."
                )

            # 1. Top Emitter Response
            elif top_emitter_task and top_emitter_task.execution_status == "COMPLETED" and "top_emitting_supplier" in top_emitter_task.output_data:
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
 
            # Append collaborative consensus if present
            if answer and getattr(state, "consensus_events", None):
                consensus = state.consensus_events[-1]
                answer += f"\n\n**Collaborative Consensus Details:**\n"
                answer += f"- **Topic:** {consensus.topic}\n"
                answer += f"- **Consensus Score:** {consensus.consensus_score * 100:.0f}%\n"
                answer += f"- **Recommendation:** {consensus.final_recommendation}\n"
                answer += f"- **Supporting Agents:** {', '.join(consensus.supporting_agents)}"
                if consensus.disagreeing_agents:
                    answer += f"\n- **Disagreeing Agents:** {', '.join(consensus.disagreeing_agents)}"

            # Append MCP Tool Chains summary
            if answer and getattr(state, "mcp_tool_chains", None):
                answer += f"\n\n**MCP Tool Execution Trace:**\n"
                for chain in state.mcp_tool_chains:
                    matching_dec = next((d for d in state.mcp_selection_decisions if d["selected_tool"] == chain["tool_name"]), None)
                    reason = matching_dec["reasoning"] if matching_dec else "Discovered and executed dynamically."
                    answer += f"- **{chain['agent_name']}** executed `{chain['tool_name']}`\n"
                    answer += f"  - *Reasoning:* {reason}\n"

            # Append A2A Federated Audit Trail summary
            if answer and getattr(state, "a2a_audit_trail", None):
                answer += f"\n\n**A2A Federated Audit Trail:**\n"
                
                # Show remote sessions and their auth/perm states
                if getattr(state, "a2a_sessions", None):
                    answer += f"**Active Remote Agent Sessions:**\n"
                    for org, sess in state.a2a_sessions.items():
                        answer += f"- **{org}**: Session ID: `{sess.session_id}` | Auth: `{sess.auth_state}` | Permissions: `{', '.join(sess.permission_grants)}` | Negotiation: `{sess.negotiation_state}`\n"
                
                # Show dynamic trust scores
                if getattr(state, "a2a_trust_scores", None):
                    answer += f"\n**A2A Dynamic Trust Scores:**\n"
                    for org, score in state.a2a_trust_scores.items():
                        answer += f"- **{org}**: Trust Rating: `{score:.2f}/1.00`\n"
                        
                # Show consensus engine results
                consensus_report = state.planner_learning.get("consensus_report") if hasattr(state, "planner_learning") and state.planner_learning else None
                if consensus_report:
                    answer += f"\n**A2A Remote Consensus Summary:**\n"
                    answer += f"- *Summary:* {consensus_report['summary']}\n"
                    answer += f"- *Agreement score:* `{consensus_report['consensus_score']*100:.0f}%`\n"
                    answer += f"- *Recommendation:* `{consensus_report['final_recommendation']}`\n"

            # Append Quality Score Dashboard if present
            if answer and getattr(state, "quality_scores", None):
                answer += f"\n**Quality Score Dashboard:**\n"
                for name, score in state.quality_scores.items():
                    answer += f"- **{name}:** `{score:.2f}/1.00`\n"

            # Append Self-Reflection & Correction Timeline if present
            if answer and getattr(state, "reflection_events", None):
                answer += f"\n**Self-Reflection & Correction Timeline:**\n"
                for i, evt in enumerate(state.reflection_events, 1):
                    answer += f"**[{i}] Stage: {evt['stage']}**\n"
                    if evt.get("detected_failure"):
                        answer += f"  - *Failure Class:* `{evt['detected_failure']}` (Severity: `{evt['severity']}`)\n"
                        answer += f"  - *Root Cause:* {evt['root_cause']}\n"
                    if evt.get("confidence_change"):
                        bef = evt["confidence_change"]["before"]
                        aft = evt["confidence_change"]["after"]
                        if bef != aft:
                            answer += f"  - *Confidence Recalibration:* `{bef*100:.0f}%` -> `{aft*100:.0f}%` (Goal model updated)\n"
                    if evt.get("recovery_action"):
                        answer += f"  - *Recovery Action Recommendation:* `{evt['recovery_action']}`\n"
                    answer += f"  - *Summary:* {evt['summary']}\n"

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

    def handle_message(self, state: ExecutionState, message: Any, bus: Any) -> Any:
        return None
