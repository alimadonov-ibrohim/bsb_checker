"""
Gemini Service — ONLY extracts answers from files.
NEVER solves tests. NEVER uses knowledge. NEVER guesses.
"""
import os
import json
import asyncio
import logging
from typing import Optional
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Strict extraction prompt — NO solving, NO guessing
EXTRACT_ANSWER_KEY_PROMPT = """
You are a pure OCR/extraction tool. Your ONLY job is to read the answers that are already written in the provided file(s).

RULES (STRICT):
1. Extract ONLY the answers that are explicitly written or marked in the file.
2. Do NOT solve any question.
3. Do NOT use your own knowledge.
4. Do NOT guess or invent any answer.
5. If an answer is unclear or not present → put null for that question.
6. Output MUST be valid JSON only. No markdown, no explanation.

Expected format of answers in file (examples):
1-A
2. C
3) B
4 - D
5: A

Return JSON exactly like this:
{
  "1": "A",
  "2": "C",
  "3": "B",
  "4": "D",
  "5": "A"
}

If a question number has no clear answer mark:
{
  "5": null
}

If you are uncertain about a specific answer:
{
  "5": null,
  "status": "uncertain"
}

Only include question numbers that appear in the file.
Return pure JSON, nothing else.
"""

EXTRACT_STUDENT_ANSWERS_PROMPT = """
You are a pure OCR/extraction tool. Your ONLY job is to read the answers that the student has marked or written on the provided page/image.

RULES (STRICT):
1. Extract ONLY the answers that the student has explicitly marked/circled/written.
2. Do NOT solve any question yourself.
3. Do NOT use your knowledge of the subject.
4. Do NOT guess what the student might have meant.
5. If a question has no mark → null.
6. If the mark is unreadable → null and optionally "status": "uncertain".
7. Also try to extract student name, surname, class if visible (fields like "Ism:", "Familiya:", "Sinf:").

Return pure JSON only:
{
  "name": "Ali Valiyev" or null,
  "class_name": "9-A" or null,
  "answers": {
    "1": "A",
    "2": "C",
    "3": null,
    "4": "D"
  }
}

If name cannot be found, set "name": null.
If any answer is uncertain, you may put "status": "uncertain" inside that answer value object, but prefer simple null.

Return ONLY valid JSON. No markdown fences.
"""


class GeminiService:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL
        self.max_retries = 3
        self.retry_delay = 2.0

    async def _upload_file(self, file_path: str):
        """Upload file to Gemini Files API."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return await self.client.aio.files.upload(file=str(path))

    async def _generate_with_retry(self, contents, prompt: str) -> str:
        last_error = None
        payload = [prompt] + (contents if isinstance(contents, list) else [contents])
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=payload,
                    config=config,
                )
                return response.text.strip()
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini attempt {attempt}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
        raise RuntimeError(f"Gemini failed after {self.max_retries} retries: {last_error}")

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        # Remove possible markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON: {text[:500]}")
            raise ValueError(f"Invalid JSON from Gemini: {e}")

    async def extract_answer_key(self, file_paths: list[str]) -> dict:
        """
        Extract answer key from TXT / PDF / images.
        Returns: {"1": "A", "2": "C", ...} or with nulls.
        """
        uploaded = []
        try:
            for fp in file_paths:
                uploaded.append(await self._upload_file(fp))

            raw = await self._generate_with_retry(uploaded, EXTRACT_ANSWER_KEY_PROMPT)
            data = self._parse_json(raw)

            # Normalize: only keep string answers or null
            result = {}
            for k, v in data.items():
                if k == "status":
                    continue
                key = str(k)
                if v is None or (isinstance(v, dict) and v.get("status") == "uncertain"):
                    result[key] = None
                elif isinstance(v, str):
                    result[key] = v.strip().upper()
                else:
                    result[key] = None
            return result
        finally:
            # Cleanup uploaded files on Gemini side is optional; local files cleaned by caller
            pass

    async def extract_student_answers(self, file_path: str) -> dict:
        """
        Extract student answers + optional name/class from a single page/image/PDF page.
        Returns:
        {
          "name": str | None,
          "class_name": str | None,
          "answers": {"1": "A", "2": null, ...}
        }
        """
        uploaded = await self._upload_file(file_path)
        raw = await self._generate_with_retry([uploaded], EXTRACT_STUDENT_ANSWERS_PROMPT)
        data = self._parse_json(raw)

        answers_raw = data.get("answers", data)  # fallback if model returns flat
        if not isinstance(answers_raw, dict):
            answers_raw = {}

        answers = {}
        for k, v in answers_raw.items():
            if k in ("name", "class_name", "status"):
                continue
            key = str(k)
            if v is None:
                answers[key] = None
            elif isinstance(v, dict):
                answers[key] = None  # uncertain
            elif isinstance(v, str):
                answers[key] = v.strip().upper()
            else:
                answers[key] = None

        return {
            "name": data.get("name") if data.get("name") else None,
            "class_name": data.get("class_name") if data.get("class_name") else None,
            "answers": answers,
        }

    async def extract_from_text(self, text_content: str) -> dict:
        """For plain TXT answer keys."""
        prompt = EXTRACT_ANSWER_KEY_PROMPT + f"\n\nText content:\n{text_content}"
        raw = await self._generate_with_retry([], prompt)
        data = self._parse_json(raw)
        result = {}
        for k, v in data.items():
            if k == "status":
                continue
            key = str(k)
            if v is None:
                result[key] = None
            elif isinstance(v, str):
                result[key] = v.strip().upper()
            else:
                result[key] = None
        return result
