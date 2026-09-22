"""Loads configuration from .env. Single place every other module reads settings from."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and fill in the real values."
        )
    return value


class Settings:
    # API server
    api_host: str = os.environ.get("API_BACKEND_HOST", "127.0.0.1")
    api_port: int = int(os.environ.get("API_BACKEND_PORT", "5000"))
    payload_max_size: str = os.environ.get("API_PAYLOAD_MAX_SIZE", "10mb")

    # Azure OpenAI
    azure_openai_endpoint: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_deployment: str = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "")
    azure_openai_api_version: str = os.environ.get("AZURE_OPENAI_API_VERSION", "")
    azure_openai_api_key: str = os.environ.get("AZURE_OPENAI_API_KEY", "")

    # Storage
    # A relative DATABASE_PATH (e.g. the literal "./bid_coauthor.db" in .env.example) is resolved
    # against BACKEND_DIR, not the process's current working directory — otherwise launching
    # uvicorn from a different folder silently creates and uses a completely separate database
    # file, with no error, no warning, and results that look inexplicable from the API alone.
    _database_path_setting = os.environ.get("DATABASE_PATH", str(BACKEND_DIR / "bid_coauthor.db"))
    database_path: str = (
        _database_path_setting
        if Path(_database_path_setting).is_absolute()
        else str((BACKEND_DIR / _database_path_setting).resolve())
    )
    prompts_dir: Path = BACKEND_DIR / "app" / "prompts"
    data_dir: Path = BACKEND_DIR / "data"  # uploaded tender documents, kept on disk per tender

    def require_azure_openai(self) -> None:
        """Call before any LLM call. Fails fast with a clear message rather than a cryptic SDK error."""
        _require("AZURE_OPENAI_ENDPOINT")
        _require("AZURE_OPENAI_DEPLOYMENT")
        _require("AZURE_OPENAI_API_VERSION")
        _require("AZURE_OPENAI_API_KEY")


settings = Settings()
