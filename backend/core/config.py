from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

DEMO_DIR = Path(__file__).resolve().parents[1]
load_dotenv(DEMO_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    cala_api_key: str = os.getenv("CALA_API_KEY", "")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    gemini_fast_model: str = os.getenv("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
    llm_provider: str = os.getenv("LLM_PROVIDER", "").lower()
    cache_dir: Path = Path(os.getenv("CALA_CACHE_DIR", str(DEMO_DIR / "cache")))

    def __post_init__(self):
        provider = self.llm_provider or ("gemini" if self.gemini_api_key else ("nvidia" if self.nvidia_api_key else "codex"))
        if provider not in {"nvidia", "gemini", "codex", "claude"}:
            raise ValueError("LLM_PROVIDER must be gemini, nvidia, codex, or claude")
        object.__setattr__(self, "llm_provider", provider)


settings = Settings()
