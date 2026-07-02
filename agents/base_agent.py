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

    def llm_reason(self, prompt: str, fallback_handler: Any) -> str:
        """
        Call Gemini client if available for reasoning, else run fallback handler.
        """
        import os
        from google import genai
        from google.genai.errors import APIError

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
