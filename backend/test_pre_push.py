"""Pre-push tests: tools, config, TTS/STT imports."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


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
        assert result in ("4", "4.0")


class TestConfig:
    def test_config_loads(self):
        from backend import config
        assert hasattr(config, "GROQ_API_KEY")
        assert hasattr(config, "LIVEKIT_URL")

    def test_livekit_defaults(self):
        from backend import config
        assert config.LIVEKIT_API_KEY == "devkey"
        assert config.LIVEKIT_API_SECRET == "secret"


class TestImports:
    def test_livekit_stt_imports(self):
        from backend.services.ai.livekit_stt import MoonshineSTT, MoonshineOptions
        assert MoonshineSTT is not None

    def test_livekit_tts_imports(self):
        from backend.services.ai.livekit_tts import KokoroTTS, KokoroOptions
        assert KokoroTTS is not None

    def test_main_imports(self):
        import backend.main
        assert hasattr(backend.main, "prewarm")
        assert hasattr(backend.main, "entrypoint")
