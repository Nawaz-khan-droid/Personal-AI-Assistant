
import asyncio
import logging
import json
from typing import Dict, Any, Optional
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)

class ToolExecutor:
    """
    Securely executes tools with error handling and logging.
    """
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        
    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Execute a tool by name with arguments.
        """
        tool = self.registry.get_tool(tool_name)
        
        if not tool:
            error_msg = f"Tool '{tool_name}' not found."
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
            
        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
        
        try:
            # TODO: Add timeout handling here
            result = await tool.execute(**tool_args)
            
            # Ensure result is a string
            if not isinstance(result, str):
                result = json.dumps(result)
                
            logger.info(f"Tool {tool_name} execution successful.")
            return result
            
        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

# Global executor instance (initialized with global registry)
from .tool_registry import registry
executor = ToolExecutor(registry)
