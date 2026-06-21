"""Odysseus configuration — env vars, constants, provider catalog."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("ODYSSEUS_DATA_DIR", str(BASE_DIR / "data")))


class Settings(BaseSettings):
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 7000
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = [
        "http://localhost:7000",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:7000",
        "http://127.0.0.1:3000",
        "https://vr-deploy.vercel.app",
        "https://vr-video-app.vercel.app",
        "*",
    ]

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'odysseus.db'}"

    # Auth
    AUTH_ENABLED: bool = True
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRY_HOURS: int = 24

    # LLM
    DEFAULT_MODEL: str = "ollama/llama3.2:latest"
    AI_GATEWAY_URL: str = "http://localhost:3005"
    OPENROUTER_API_KEY: str = ""
    TOGETHER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    XAI_API_KEY: str = ""
    VERCEL_OIDC_TOKEN: str = ""

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Provider catalog: name -> (base_url, env_key, curated_models)
    # Only light models (< 6GB) are included
    LLM_PROVIDERS: dict = {
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "env_key": "",  # No API key needed for local Ollama
            "models": [
                "llama3.2:latest",           # 1.9GB - default
                "moondream:latest",          # 1.6GB - vision
                "rafw007/bielik-codex:latest",  # 5.7GB - coding
            ],
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "env_key": "OPENROUTER_API_KEY",
            "models": [
                "openrouter/auto",           # auto-selects best model
                "google/gemini-2.0-flash",   # free tier
                "meta-llama/llama-3.1-8b-instruct",  # free tier
                "qwen/qwen-2.5-7b-instruct",  # free tier
            ],
        },
        "together": {
            "base_url": "https://api.together.xyz/v1",
            "env_key": "TOGETHER_API_KEY",
            "models": [
                "meta-llama/Llama-3.1-8B-Instruct-Turbo",  # 8B, fast
                "deepseek-ai/DeepSeek-R1",                   # reasoning
            ],
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "env_key": "OPENAI_API_KEY",
            "models": ["gpt-4o-mini", "gpt-3.5-turbo"],
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com",
            "env_key": "ANTHROPIC_API_KEY",
            "models": ["claude-3-haiku"],
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "env_key": "GOOGLE_API_KEY",
            "models": ["gemini-2.0-flash"],
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "env_key": "DEEPSEEK_API_KEY",
            "models": ["deepseek-r1"],
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "env_key": "GROQ_API_KEY",
            "models": ["llama-3.1-8b-instant"],
        },
        "mistral": {
            "base_url": "https://api.mistral.ai/v1",
            "env_key": "MISTRAL_API_KEY",
            "models": ["mistral-small"],
        },
        "xai": {
            "base_url": "https://api.x.ai/v1",
            "env_key": "XAI_API_KEY",
            "models": ["grok-3-mini"],
        },
    }

    # Video library
    VIDEO_DATA_DIR: str = str(DATA_DIR / "video")
    VIDEO_DB_PATH: str = str(DATA_DIR / "video" / "videos.db")
    VR_DATABASE_PATH: str = str(DATA_DIR / "video" / "videos.db")
    VR_BACKEND_DIR: str = str(BASE_DIR.parent / "Desktop" / "vr video" / "backend")
    THUMBNAIL_DIR: str = str(DATA_DIR / "video" / "thumbs")
    FACE_MODEL_DIR: str = str(DATA_DIR / "video" / "models")

    # Orchestrator
    ORCHESTRATOR_DB_PATH: str = str(DATA_DIR / "orchestrator.db")
    MAX_CONCURRENT_TASKS: int = 5
    TASK_TIMEOUT_SECONDS: int = 300

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
