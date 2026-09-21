"""
Vercel serverless entry point.
Handles: Admin panel + API + Telegram webhook.
Note: Long PDF processing may hit Vercel timeout limits.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# Re-export FastAPI app for Vercel
from backend.main import app  # noqa: E402
