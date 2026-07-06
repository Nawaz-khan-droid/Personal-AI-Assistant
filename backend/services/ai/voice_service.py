import os
import glob
import logging
from typing import Dict, Optional

import numpy as np

from .tts_service import tts_service

logger = logging.getLogger(__name__)

CUSTOM_VOICE_DIR = os.getenv("CUSTOM_VOICE_DIR", "custom_voices")

PRESET_VOICE_IDS = {
    "jarvis": "am_adam",
    "veronica": "af_bella",
    "michael": "am_michael",
    "heart": "af_heart",
    "george": "bm_george",
    "emma": "bf_emma",
}


class VoiceService:
    def __init__(self):
        self.active_matrix: Optional[np.ndarray] = None
        self.active_voice_id: str = "am_adam"
        os.makedirs(CUSTOM_VOICE_DIR, exist_ok=True)

    def _resolve_voice(self, voice_id: str) -> np.ndarray:
        """Look up a voice vector from Kokoro's internal voice table."""
        engine = tts_service.engine
        if engine is None:
            logger.warning("TTS engine not loaded, cannot resolve voice")
            return None

        try:
            if hasattr(engine, "get_voice_style"):
                return engine.get_voice_style(voice_id)
            if hasattr(engine, "voices"):
                voices = engine.voices
                if isinstance(voices, dict) and voice_id in voices:
                    return voices[voice_id]
                if isinstance(voices, np.ndarray):
                    return voices[voice_id]
        except Exception as e:
            logger.warning("Could not resolve voice '%s': %s", voice_id, e)
        return None

    def select_preset(self, voice_id: str):
        """Switch to a preset Kokoro voice."""
        self.active_voice_id = voice_id
        self.active_matrix = None
        logger.info("Voice switched to preset: %s", voice_id)

    def blend(self, base_id: str, mod_id: str, alpha: float) -> Optional[np.ndarray]:
        """Live linear-interpolation blend of two voices (no disk write).
        Falls back to base preset if resolution fails (TTS engine not loaded)."""
        base_vec = self._resolve_voice(base_id)
        mod_vec = self._resolve_voice(mod_id)
        if base_vec is None or mod_vec is None:
            logger.warning("Blend unavailable, falling back to preset '%s'", base_id)
            self.select_preset(base_id)
            return None
        matrix = (1.0 - alpha) * base_vec + (alpha * mod_vec)
        self.active_matrix = matrix
        self.active_voice_id = f"blend:{base_id}+{mod_id}@{alpha:.2f}"
        logger.info("Live blend computed: %s", self.active_voice_id)
        return matrix

    def save_custom(self, name: str, base_id: str, mod_id: str, alpha: float) -> Optional[str]:
        """Persist a blend as a .npy file and return its path.
        Returns None if voice vectors cannot be resolved."""
        base_vec = self._resolve_voice(base_id)
        mod_vec = self._resolve_voice(mod_id)
        if base_vec is None or mod_vec is None:
            logger.warning("Cannot save custom voice: vectors unavailable")
            return None
        matrix = (1.0 - alpha) * base_vec + (alpha * mod_vec)
        safe_name = name.strip().lower().replace(" ", "_").replace("/", "_")
        path = os.path.join(CUSTOM_VOICE_DIR, f"{safe_name}.npy")
        np.save(path, matrix)
        self.active_matrix = matrix
        self.active_voice_id = f"custom:{safe_name}"
        logger.info("Custom voice saved: %s", path)
        return path

    def load_custom(self, name: str) -> Optional[np.ndarray]:
        """Load a saved custom voice matrix."""
        safe_name = name.strip().lower().replace(" ", "_").replace("/", "_")
        path = os.path.join(CUSTOM_VOICE_DIR, f"{safe_name}.npy")
        if not os.path.isfile(path):
            logger.warning("Custom voice not found: %s", path)
            return None
        matrix = np.load(path)
        self.active_matrix = matrix
        self.active_voice_id = f"custom:{safe_name}"
        return matrix

    def list_custom(self) -> list:
        """List saved custom voice names."""
        files = glob.glob(os.path.join(CUSTOM_VOICE_DIR, "*.npy"))
        return [os.path.splitext(os.path.basename(f))[0] for f in files]

    def get_active_voice(self):
        """Return the current voice — either a string ID or numpy matrix."""
        if self.active_matrix is not None:
            return self.active_matrix
        return self.active_voice_id


voice_service = VoiceService()
