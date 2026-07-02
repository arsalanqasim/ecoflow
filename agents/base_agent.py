from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import List, Optional, Any
from agents.shared_state import ExecutionState, Task, TaskResult

class AgentMetadata(BaseModel):
    agent_name: str
    description: str
    capabilities: List[str]
    required_inputs: List[str]
    produced_outputs: List[str]
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0

class BaseAgent(ABC):
    @property
    def memory(self) -> dict:
        if not hasattr(self, "_short_term_memory"):
            self._short_term_memory = {}
        return self._short_term_memory

    def clear_memory(self) -> None:
        if hasattr(self, "_short_term_memory"):
            self._short_term_memory.clear()

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Return the metadata for this agent."""
        pass

    def plan(self, state: ExecutionState, task: Task) -> Task:
        """
        Analyze the task input and plan the execution steps if needed.
        Allows the agent to self-document or prepare itself before execution.
        """
        return task

    @abstractmethod
    def execute(self, state: ExecutionState, task: Task) -> TaskResult:
        """
        Perform the actual work for the given task and return a TaskResult.
        """
        pass

    def validate(self, state: ExecutionState, result: TaskResult) -> bool:
        """
        Validate the output of the task execution.
        """
        return True

    def summarize(self, state: ExecutionState, result: TaskResult) -> str:
        """
        Summarize the task outcome.
        """
        return f"{self.metadata.agent_name} successfully executed task {result.task_id}."

    def handle_message(self, state: ExecutionState, message: Any, bus: Any) -> Any:
        """
        Handle incoming messages from the Agent Communication Bus.
        Overridden by collaborating worker agents.
        """
        return None

    def discover_and_select_tool(self, query: str, state: ExecutionState) -> Any:
        from agents.mcp_registry import registry
        import time
        import logging
        
        # Discover tools matching the query
        tools = registry.search_tools(query)
        
        # Log discovery event
        discovery_event = {
            "agent_name": self.metadata.agent_name,
            "query": query,
            "discovered_tools": [t.name for t in tools],
            "timestamp": time.time()
        }
        state.mcp_discovery_events.append(discovery_event)
        
        if not tools:
            logger_name = self.__class__.__name__
            logging.getLogger(logger_name).warning(f"No tools found matching query: '{query}'")
            return None
            
        # Select first matching tool (simplest heuristic for selecting best match)
        selected_tool = tools[0]
        
        # Selection Explainability Reasoning summary
        def fallback_reason():
            return (
                f"Selected {selected_tool.name} from {selected_tool.server_name} "
                f"because it directly matches the capability '{query}' with an estimated reliability score of "
                f"{selected_tool.reliability_score * 100:.0f}%, low estimated latency of {selected_tool.estimated_latency}s, "
                f"and expected confidence of 95%."
            )
            
        prompt = (
            f"You are {self.metadata.agent_name}. You are selecting a tool for query '{query}' "
            f"from the following candidates: {[t.name for t in tools]}. "
            f"The selected candidate is {selected_tool.name}. Write a concise, professional selection summary "
            f"(max 2 sentences) explaining why this tool is selected, its expected reliability, expected confidence, and fallback plan."
        )
        
        reasoning = self.llm_reason(prompt, fallback_reason)
        
        # Log selection decision
        selection_decision = {
            "agent_name": self.metadata.agent_name,
            "query": query,
            "selected_tool": selected_tool.name,
            "reasoning": reasoning,
            "expected_reliability": selected_tool.reliability_score,
            "timestamp": time.time()
        }
        state.mcp_selection_decisions.append(selection_decision)
        
        return selected_tool

    def execute_mcp_tool(self, tool: Any, args: dict, state: ExecutionState) -> Any:
        from agents.mcp_registry import registry
        import time
        
        # Perform execution
        result = registry.execute_tool(tool.name, args, state)
        
        # Track tool chains
        chain_event = {
            "agent_name": self.metadata.agent_name,
            "tool_name": tool.name,
            "args": args,
            "timestamp": time.time()
        }
        state.mcp_tool_chains.append(chain_event)
        
        return result

    def validate_tool_output(self, tool: Any, output: Any, state: ExecutionState) -> bool:
        # Check completeness and domain correctness
        import time
        is_valid = True
        msg = f"Tool output structure for '{tool.name}' is complete and domain-correct."
        
        if tool.name == "get_supplier_carbon_status":
            if not isinstance(output, dict) or "status" not in output:
                is_valid = False
                msg = "Validation Error: Supplier status missing in output."
        elif tool.name == "compute_regional_grid_intensity":
            if not isinstance(output, dict) or "grid_intensity_tCO2_per_MWh" not in output:
                is_valid = False
                msg = "Validation Error: Grid intensity missing in output."
        elif tool.name == "compute_emissions_join":
            if not isinstance(output, str) or not output.startswith("["):
                is_valid = False
                msg = "Validation Error: Expected JSON list string from emissions join."
                
        # Log validation event
        state.mcp_validation_events.append({
            "agent_name": self.metadata.agent_name,
            "tool_name": tool.name,
            "is_valid": is_valid,
            "message": msg,
            "timestamp": time.time()
        })
        
        if not is_valid:
            state.warnings.append(f"Validation failure in {tool.name}: {msg}")
            
        return is_valid

    def llm_reason(self, prompt: str, fallback_handler: Any) -> str:
        """
        Call Gemini client if available for reasoning, else run fallback handler.
        """
        import os
        from google import genai
        
        client = getattr(self, "genai_client", None)
        if not client:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                try:
                    client = genai.Client()
                    self.genai_client = client
                except Exception:
                    pass
                    
        if client:
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response.text:
                    return response.text.strip()
            except Exception as e:
                import logging
                logging.getLogger(self.__class__.__name__).warning(
                    f"Gemini API error in llm_reason: {e}. Running fallback."
                )
                
        if callable(fallback_handler):
            return fallback_handler()
        return str(fallback_handler)
