"""
Writable path helpers.

Local development uses the project folders (./temp, ./uploads).
Serverless platforms (Vercel, AWS Lambda) expose a read-only project
filesystem, so the only writable location is the system temp dir (/tmp).
"""
import os
import tempfile
from pathlib import Path


def _is_serverless() -> bool:
    return any(
        os.getenv(name)
        for name in ("VERCEL", "VERCEL_ENV", "AWS_LAMBDA_FUNCTION_NAME")
    )


def _base_dir() -> Path:
    return Path(tempfile.gettempdir()) if _is_serverless() else Path(".")


def _resolve(env_name: str, default_name: str) -> Path:
    configured = os.getenv(env_name)
    base = _base_dir()
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else base / path
    return base / default_name


def temp_dir() -> Path:
    return _resolve("TEMP_DIR", "temp")


def uploads_dir() -> Path:
    return _resolve("UPLOADS_DIR", "uploads")
