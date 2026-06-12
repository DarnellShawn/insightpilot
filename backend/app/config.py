"""Environment-based configuration. No secrets in code."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def _load_dotenv() -> None:
    """Load backend/.env into os.environ (real env vars take precedence).

    Tiny built-in parser so we don't need python-dotenv as a dependency.
    """
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


class Settings(BaseModel):
    app_name: str = "InsightPilot API"
    version: str = "0.1.0"

    anthropic_api_key: str | None = None
    report_model: str = "claude-fable-5"
    report_max_tokens: int = 8000

    # Upload guardrails — keeps memory bounded since processing is in-memory.
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB
    max_rows: int = 500_000

    allowed_origins: list[str] = ["*"]

    @property
    def report_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    origins = os.getenv("ALLOWED_ORIGINS", "*")
    # Remove ALL whitespace — a key copied from a console that displays it
    # wrapped across multiple lines carries embedded newlines, which produce an
    # invalid HTTP header that surfaces as a connection error. API keys never
    # legitimately contain whitespace.
    api_key = "".join((os.getenv("ANTHROPIC_API_KEY") or "").split()) or None
    return Settings(
        anthropic_api_key=api_key,
        report_model=os.getenv("REPORT_MODEL", "claude-fable-5"),
        report_max_tokens=int(os.getenv("REPORT_MAX_TOKENS", "8000")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
        allowed_origins=[o.strip() for o in origins.split(",") if o.strip()],
    )
