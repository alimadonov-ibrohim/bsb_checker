"""
Gemini Service — ONLY extracts answers from files.
NEVER solves tests. NEVER uses knowledge. NEVER guesses.
"""
import os
import re
import json
import asyncio
import logging
from pathlib import Path

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.7-flash,gemini-3.8-flash,"
        "gemini-flash-lite-latest,gemini-omni-flash-preview",
    ).split(",")
    if m.strip()
]

# Permissive extraction prompt — reads ANY layout, but NEVER solves/guesses.
EXTRACT_ANSWER_KEY_PROMPT = """
You are a pure OCR/extraction tool. Your ONLY job is to read the answers that are already written in the provided file(s).

The answer key may be written in ANY format, for example:
- "1-A, 2-C, 3-B"
- "1. A   2. C   3. B"
- "1) A   2) C"
- "1 A   2 C"
- a table with question numbers and answer letters
- a vertical list, one answer per line
- a continuous sequence of letters, e.g. "ABCDABCD" (first letter = question 1, second = question 2, ...)
- letters circled/underlined in a row

RULES (STRICT):
1. Extract ONLY the answers that are explicitly written or marked in the file.
2. Do NOT solve any question.
3. Do NOT use your own knowledge.
4. Do NOT guess or invent an answer for a question that has no answer.
5. If an answer is unreadable or missing, use null for that number — but still include the number.
6. If the file contains a continuous sequence of letters without numbers, number them from 1 in order.
7. Output MUST be valid JSON only. No markdown, no explanation.

Return JSON mapping question number -> answer letter:
{
  "1": "A",
  "2": "C",
  "3": "B",
  "4": "D"
}

Return pure JSON, nothing else.
"""

# Fallback used only if the first attempt returns nothing.
EXTRACT_ANSWER_KEY_FALLBACK_PROMPT = """
Read the provided file and list every answer letter that is written on it, in order.
Do NOT solve the questions. Do NOT guess. Only transcribe what is visible.

Return JSON where keys are question numbers and values are the letters found:
{"1": "A", "2": "C", "3": "B"}

If numbers are not shown, use positions 1, 2, 3, ... in reading order.
If something is unreadable use null.
Return pure JSON only.
"""

EXTRACT_STUDENT_ANSWERS_PROMPT = """
You are a pure OCR/extraction tool. Your ONLY job is to read the answers that the student has marked or written on the provided page/image.

The marks may be in ANY format: a letter next to the number (1-A, 1.A, 1)A, 1 A),
a circled/underlined/checked option, a table, or a row of letters.

RULES (STRICT):
1. Extract ONLY the answers that the student has explicitly marked/circled/written.
2. Do NOT solve any question yourself.
3. Do NOT use your knowledge of the subject.
4. Do NOT guess what the student might have meant.
5. If a question has no mark -> null.
6. If the mark is unreadable -> null and optionally "status": "uncertain".
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
Return ONLY valid JSON. No markdown fences.
"""

EXTRACT_STUDENT_ANSWERS_BATCH_PROMPT = (
    EXTRACT_STUDENT_ANSWERS_PROMPT
    + """

The user provided MULTIPLE page images. Process EACH image independently.
- Return a JSON array with EXACTLY one element per image, in the SAME order as the images.
- Element i corresponds to image i:
  {"name": "... or null", "class_name": "... or null", "answers": {"1": "A", ...}}
- Do NOT merge pages and do NOT skip elements. If a page is blank, return
  {"name": null, "class_name": null, "answers": {}} for it.
Return ONLY the JSON array. No markdown, no extra text.
"""
)


class GeminiService:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL
        self.models = [GEMINI_MODEL] + [
            m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL
        ]
        self.max_retries = 3
        self.retry_delay = 2.0

    async def _upload_file(self, file_path: str):
        """Upload file to Gemini Files API."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        return await self.client.aio.files.upload(file=str(path))

    async def _generate_with_retry(self, contents, prompt: str) -> str:
        """Generate content, retrying and rotating through models on failure."""
        payload = [prompt] + (contents if isinstance(contents, list) else [contents])
        config = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        errors = []
        for model in self.models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model,
                        contents=payload,
                        config=config,
                    )
                    return (response.text or "").strip()
                except Exception as e:
                    msg = str(e)
                    errors.append(f"{model}: {msg[:160]}")
                    logger.warning(
                        f"Gemini model={model} attempt {attempt}/{self.max_retries} "
                        f"failed: {msg[:200]}"
                    )
                    # Quota / model-not-found / bad-request -> switch model immediately
                    if any(code in msg for code in ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND", "400")):
                        break
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * attempt)
        raise RuntimeError("Gemini failed on all models: " + " | ".join(errors[-3:]))

    def _parse_json(self, text: str) -> dict:
        text = (text or "").strip()
        # Remove possible markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to recover the first JSON object in the text
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error(f"Failed to parse Gemini JSON: {text[:500]}")
            return {}

    def _normalize_answer_map(self, data) -> dict:
        """Turn any parsed structure into {question_number: letter|null}."""
        if isinstance(data, dict) and isinstance(data.get("answers"), dict):
            data = data["answers"]
        result = {}
        if not isinstance(data, dict):
            return result
        for k, v in data.items():
            if k in ("status", "name", "class_name", "answers"):
                continue
            key = str(k).strip()
            if not key.isdigit():
                digits = "".join(ch for ch in key if ch.isdigit())
                if not digits:
                    continue
                key = digits
            if v is None:
                result[key] = None
            elif isinstance(v, dict):
                inner = v.get("answer") or v.get("value") or v.get("letter")
                result[key] = self._clean_letter(inner)
            elif isinstance(v, (list, tuple)):
                result[key] = self._clean_letter(v[0]) if v else None
            else:
                result[key] = self._clean_letter(v)
        return result

    @staticmethod
    def _clean_letter(value) -> str | None:
        if value is None:
            return None
        text = str(value).strip().upper()
        if not text:
            return None
        letters = [c for c in text if "A" <= c <= "Z"]
        return letters[0] if letters else None

    async def _extract_with_prompts(self, contents, primary: str, fallback: str) -> dict:
        raw = await self._generate_with_retry(contents, primary)
        result = self._normalize_answer_map(self._parse_json(raw))
        if not result:
            logger.warning(f"Answer key empty on first pass, retrying. raw={raw[:300]!r}")
            raw = await self._generate_with_retry(contents, fallback)
            result = self._normalize_answer_map(self._parse_json(raw))
            if not result:
                logger.error(f"Answer key still empty. raw={raw[:300]!r}")
        return result

    async def extract_answer_key(self, file_paths: list[str]) -> dict:
        """
        Extract answer key from TXT / PDF / images.
        Returns: {"1": "A", "2": "C", ...} or with nulls.
        """
        uploaded = [await self._upload_file(fp) for fp in file_paths]
        return await self._extract_with_prompts(
            uploaded, EXTRACT_ANSWER_KEY_PROMPT, EXTRACT_ANSWER_KEY_FALLBACK_PROMPT
        )

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

        answers = self._normalize_answer_map(data)

        return {
            "name": data.get("name") if isinstance(data, dict) and data.get("name") else None,
            "class_name": data.get("class_name") if isinstance(data, dict) and data.get("class_name") else None,
            "answers": answers,
        }

    async def extract_from_text(self, text_content: str) -> dict:
        """For plain TXT answer keys."""
        prompt = EXTRACT_ANSWER_KEY_PROMPT + f"\n\nText content:\n{text_content}"
        fallback = EXTRACT_ANSWER_KEY_FALLBACK_PROMPT + f"\n\nText content:\n{text_content}"
        return await self._extract_with_prompts([], prompt, fallback)

    async def extract_student_answers_batch(self, file_paths: list[str]) -> list[dict]:
        """
        Read multiple pages in ONE Gemini request.
        Returns a list aligned with file_paths:
        [
          {"name": ..., "class_name": ..., "answers": {...}},
          ...
        ]
        """
        uploaded = [await self._upload_file(fp) for fp in file_paths]
        raw = await self._generate_with_retry(
            uploaded, EXTRACT_STUDENT_ANSWERS_BATCH_PROMPT
        )
        data = self._parse_json(raw)

        items = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for k in ("students", "pages", "results", "answers"):
                if isinstance(data.get(k), list):
                    items = data[k]
                    break

        if not isinstance(items, list):
            raise ValueError(
                f"Batch response is not a list; raw={raw[:300]!r}"
            )

        out = []
        for it in items[: len(file_paths)]:
            if isinstance(it, dict):
                out.append(
                    {
                        "name": it.get("name") or None,
                        "class_name": it.get("class_name") or None,
                        "answers": self._normalize_answer_map(it),
                    }
                )
            else:
                out.append({"name": None, "class_name": None, "answers": {}})

        while len(out) < len(file_paths):
            out.append({"name": None, "class_name": None, "answers": {}})

        return out
