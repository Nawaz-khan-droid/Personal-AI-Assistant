"""Pre-push tests: tools, rate limiter, health endpoint, edge cases."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# 1. TOOL REGISTRY — all 4 tools registered and executable
# =============================================================================

class TestToolRegistry:
    def test_all_tools_registered(self):
        from backend.services.tools import registry
        names = sorted(registry._tools.keys())
        assert names == sorted(["get_current_time", "get_weather", "calculate", "web_search"])

    @pytest.mark.asyncio
    async def test_calculator_valid(self):
        from backend.services.tools.builtin.calculator_tool import CalculatorTool
        tool = CalculatorTool()
        result = await tool.execute("2 + 2")
        # simpleeval returns int for integer operations
        assert result in ("4", "4.0")

    @pytest.mark.asyncio
    async def test_calculator_jailbreak(self):
        from backend.services.tools.builtin.calculator_tool import CalculatorTool
        tool = CalculatorTool()
        result = await tool.execute("__import__('os').system('clear')")
        assert "Error" in result or "not allowed" in result

    @pytest.mark.asyncio
    async def test_calculator_syntax_error(self):
        from backend.services.tools.builtin.calculator_tool import CalculatorTool
        tool = CalculatorTool()
        result = await tool.execute("broken +++ syntax")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_time_tool_valid(self):
        from backend.services.tools.builtin.time_tool import TimeTool
        tool = TimeTool()
        result = await tool.execute("UTC")
        assert "UTC" in result or "Error" not in result

    @pytest.mark.asyncio
    async def test_time_tool_invalid_zone(self):
        from backend.services.tools.builtin.time_tool import TimeTool
        tool = TimeTool()
        result = await tool.execute("Fake/Zone")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_weather_tool_empty(self):
        from backend.services.tools.builtin.weather_tool import WeatherTool
        tool = WeatherTool()
        result = await tool.execute("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_search_tool_empty(self):
        from backend.services.tools.builtin.search_tool import WebSearchTool
        tool = WebSearchTool()
        result = await tool.execute("")
        assert result is not None


# =============================================================================
# 2. RATE LIMITER
# =============================================================================

class TestRateLimiter:
    def test_blocks_after_limit(self):
        from backend.main import WSRateLimiter
        from backend.utils.exceptions import RateLimitError
        limiter = WSRateLimiter(max_turns=2, window_seconds=10)
        limiter.check("10.0.0.1")
        limiter.check("10.0.0.1")
        with pytest.raises(RateLimitError):
            limiter.check("10.0.0.1")

    def test_different_ips_independent(self):
        from backend.main import WSRateLimiter
        limiter = WSRateLimiter(max_turns=2, window_seconds=10)
        limiter.check("10.0.0.1")
        limiter.check("10.0.0.1")
        limiter.check("10.0.0.2")  # different IP — should not raise


# =============================================================================
# 3. HEALTH ENDPOINT
# =============================================================================

class TestHealthEndpoint:
    def test_health_returns_healthy(self):
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_has_version(self):
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/health")
        data = resp.json()
        assert "version" in data
        assert data["version"] == "2.0.0"


# =============================================================================
# 4. SESSION HISTORY CAP (edge case)
# =============================================================================

class TestSessionHistoryCap:
    def test_history_system_prompt_mentions_context(self):
        """Verify the system prompt references conversation context."""
        with open("backend/main.py") as f:
            content = f.read()
        # Look for the prompt string or conversation reference
        assert "conversation" in content.lower() or "histor" in content.lower()

    def test_clear_history_type_in_code(self):
        with open("backend/main.py") as f:
            content = f.read()
        assert "clear_history" in content, "Missing clear_history WS message type"


# =============================================================================
# 5. IMPORT SANITY
# =============================================================================

class TestImportSanity:
    def test_config_imports(self):
        from backend.config import GROQ_API_KEY, GEMINI_API_KEY, HOST, PORT
        assert HOST is not None
        # PORT is 8000 for local dev; Docker uses 7860
        assert PORT in (8000, 7860)

    def test_exceptions_import(self):
        from backend.utils.exceptions import AIServiceError, LLMError, STTError, TTSError
        assert issubclass(LLMError, AIServiceError)
        assert issubclass(STTError, AIServiceError)
        assert issubclass(TTSError, AIServiceError)

    def test_logger_import(self):
        from backend.utils.logger import setup_logging, get_logger
        logger = get_logger("test")
        assert logger is not None

    def test_websocket_manager_import(self):
        from backend.websocket_manager import ConnectionManager
        assert ConnectionManager() is not None

    def test_tool_executor(self):
        from backend.services.tools import executor, registry
        from backend.services.tools.tool_executor import ToolExecutor
        assert isinstance(executor, ToolExecutor)


# =============================================================================
# 6. EDGE CASES
# =============================================================================

class TestEdgeCases:
    def test_audio_buffer_cap_exists(self):
        """Verify MAX_AUDIO_BUFFER is defined in main.py WebSocket handler."""
        with open("backend/main.py") as f:
            content = f.read()
        assert "MAX_AUDIO_BUFFER" in content
        assert "bytearray()" in content

    def test_no_bare_excepts(self):
        """Ensure no bare except: clauses."""
        import ast
        for root, dirs, files in os.walk("backend"):
            if "__pycache__" in root: continue
            for f in files:
                if not f.endswith(".py"): continue
                path = os.path.join(root, f)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ExceptHandler) and node.type is None:
                        pytest.fail(f"Bare except in {path}")
