
from typing import Dict, Any
import logging
import ast
import operator
from ..tool_registry import Tool, registry

logger = logging.getLogger(__name__)

class CalculatorTool(Tool):
    @property
    def name(self) -> str:
        return "calculate"
        
    @property
    def description(self) -> str:
        return "Perform safe mathematical calculations. Supports +, -, *, /, **."
        
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g., '2 + 2' or '(10 * 5) / 2'."
                }
            },
            "required": ["expression"]
        }
    
    def _safe_eval(self, node):
        """
        Safely evaluate an AST node.
        Only allows specific operators and literals.
        """
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.BitXor: operator.xor,
            ast.USub: operator.neg
        }

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            return operators[type(node.op)](self._safe_eval(node.left), self._safe_eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return operators[type(node.op)](self._safe_eval(node.operand))
        else:
            raise TypeError(node)

    async def execute(self, expression: str) -> str:
        try:
            # Parse the expression into an AST
            node = ast.parse(expression, mode='eval').body
            result = self._safe_eval(node)
            return str(result)
        except Exception as e:
            return f"Error evaluating expression '{expression}': {e}"

# Register the tool
registry.register(CalculatorTool())
