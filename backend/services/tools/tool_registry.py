
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class Tool(ABC):
    """Base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        pass
        
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        pass
        
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass

class ToolRegistry:
    """
    Registry for managing available tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        
    def register(self, tool: Tool):
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered. Overwriting.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
        
    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)
        
    def list_tools(self) -> List[Dict[str, Any]]:
        """Return list of tool definitions for LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in self._tools.values()
        ]

# Global registry instance
registry = ToolRegistry()
