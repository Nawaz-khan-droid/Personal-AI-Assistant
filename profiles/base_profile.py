from abc import ABC, abstractmethod
from typing import List, Callable


class BaseProfile(ABC):
    """
    Abstract Base Class defining the identity structure for JARVIS Assistant profiles.
    Enforces the Open-Closed and Dependency Inversion Principles for Phase 2 scaling.
    """

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        Returns the system prompt / instructions defining the agent's persona.
        """
        pass

    @property
    @abstractmethod
    def greeting_message(self) -> str:
        """
        Returns the initialization greeting spoken by the agent upon connecting.
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[Callable]:
        """
        Returns a list of Python functions decorated with @llm.ai_callable to expose to the LLM agent.
        """
        pass
