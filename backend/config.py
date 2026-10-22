"""Configuration module — loads settings from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=False)


class Settings:
    """Application settings loaded from environment variables."""

    # LLM Settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "").strip()
    
    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    OLLAMA_FAST_MODEL: str = os.getenv("OLLAMA_FAST_MODEL", "qwen2.5:3b")
    
    # Rate Limiting
    RATE_LIMIT_RPM: int = int(os.getenv("RATE_LIMIT_RPM", "10"))
    
    # Demo Mode
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

    # Whisper STT Tuning
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    WHISPER_THREADS: int = int(os.getenv("WHISPER_THREADS", "4"))

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Cleanup & Limits
    CLEANUP_AFTER_HOURS: int = int(os.getenv("CLEANUP_AFTER_HOURS", "24"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    MAX_VIDEO_DURATION_MIN: int = int(os.getenv("MAX_VIDEO_DURATION_MIN", "180"))

    # Paths
    PROJECT_ROOT: Path = PROJECT_ROOT
    TEMP_DIR: Path = PROJECT_ROOT / "temp"
    JOBS_DIR: Path = TEMP_DIR / "jobs"
    CACHE_DIR: Path = PROJECT_ROOT / ".cache"
    TRANSCRIPT_CACHE_DIR: Path = CACHE_DIR / "transcripts"
    TEMPLATES_DIR: Path = PROJECT_ROOT / "templates"

    # Allowed file extensions
    ALLOWED_EXTENSIONS: set = {".mp4", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}

    @classmethod
    def ensure_dirs(cls):
        """Create necessary working and cache directories."""
        cls.TEMP_DIR.mkdir(exist_ok=True, parents=True)
        cls.JOBS_DIR.mkdir(exist_ok=True, parents=True)
        cls.CACHE_DIR.mkdir(exist_ok=True, parents=True)
        cls.TRANSCRIPT_CACHE_DIR.mkdir(exist_ok=True, parents=True)


settings = Settings()
settings.ensure_dirs()


def get_settings() -> Settings:
    """Return application settings instance."""
    return settings
