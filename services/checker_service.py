"""
Checker Service — pure Python comparison.
Gemini only reads; this service decides correct / incorrect / uncertain.
"""
import json
from typing import Dict, Any, Tuple


class CheckerService:
    """
    Compare answer_key vs student_answers.
    Returns detailed result.
    """

    @staticmethod
    def compare(
        answer_key: Dict[str, str | None],
        student_answers: Dict[str, str | None],
        question_count: int | None = None,
        points: Dict[str, float] | None = None,
    ) -> Dict[str, Any]:
        """
        answer_key: {"1": "A", "2": "C", ...}
        student_answers: {"1": "A", "2": "D", "3": null, ...}
        points: {"1": 2, "2": 1, ...} — har bir savolning bali (default 1)

        Returns:
        {
          "correct_count": int,
          "incorrect_count": int,
          "uncertain_count": int,
          "percentage": float,
          "score": float,
          "max_score": float,
          "details": {
            "1": {"student": "A", "correct": "A", "status": "correct", "points": 2},
            "2": {"student": "D", "correct": "C", "status": "incorrect", "points": 1},
            "3": {"student": null, "correct": "B", "status": "uncertain", "points": 1},
            ...
          }
        }
        """
        details = {}
        correct = 0
        incorrect = 0
        uncertain = 0
        score = 0.0
        max_score = 0.0

        # Determine all question numbers
        all_keys = set()
        if question_count:
            all_keys = {str(i) for i in range(1, question_count + 1)}
        else:
            all_keys = set(answer_key.keys()) | set(student_answers.keys())

        # Sort numerically
        sorted_keys = sorted(all_keys, key=lambda x: int(x) if x.isdigit() else 0)

        for q in sorted_keys:
            key_ans = answer_key.get(q)
            stud_ans = student_answers.get(q)

            # Normalize
            if isinstance(key_ans, str):
                key_ans = key_ans.strip().upper()
            if isinstance(stud_ans, str):
                stud_ans = stud_ans.strip().upper()

            try:
                q_point = float((points or {}).get(q, 1.0))
            except (TypeError, ValueError):
                q_point = 1.0
            if q_point <= 0:
                q_point = 1.0
            max_score += q_point

            if stud_ans is None:
                status = "uncertain"
                uncertain += 1
            elif key_ans is None:
                # No key for this question — treat as uncertain
                status = "uncertain"
                uncertain += 1
            elif stud_ans == key_ans:
                status = "correct"
                correct += 1
                score += q_point
            else:
                status = "incorrect"
                incorrect += 1

            details[q] = {
                "student": stud_ans,
                "correct": key_ans,
                "status": status,
                "points": q_point,
            }

        total = correct + incorrect + uncertain
        if total == 0:
            percentage = 0.0
        else:
            # Percentage based on answered questions that have a key
            scored = correct + incorrect
            if scored == 0:
                percentage = 0.0
            else:
                percentage = round((correct / scored) * 100, 2)

        return {
            "correct_count": correct,
            "incorrect_count": incorrect,
            "uncertain_count": uncertain,
            "percentage": percentage,
            "score": round(score, 2),
            "max_score": round(max_score, 2),
            "details": details,
            "total_questions": total,
        }

    @staticmethod
    def merge_student_pages(page_results: list[dict]) -> dict:
        """
        Merge answers from multiple pages of the same student.
        Later pages overwrite earlier ones for same question numbers.
        Name/class taken from first non-null.
        """
        merged_answers = {}
        name = None
        class_name = None

        for page in page_results:
            if page.get("name") and not name:
                name = page["name"]
            if page.get("class_name") and not class_name:
                class_name = page["class_name"]
            for q, ans in page.get("answers", {}).items():
                # Prefer non-null
                if q not in merged_answers or merged_answers[q] is None:
                    merged_answers[q] = ans
                elif ans is not None:
                    merged_answers[q] = ans

        return {
            "name": name,
            "class_name": class_name,
            "answers": merged_answers,
        }


def parse_points_input(text: str, question_count: int) -> dict[str, float]:
    """
    Convert user input into {"1": 2, "2": 1, ...}.

    Accepts:
      - bitta son: "2"  -> barcha savollarga 2 ball
      - ro'yxat: "2, 2, 1, 1, ..."  -> ketma-ket savollarga (soni question_count ga teng bo'ladi)
      - juftlik/diapazon: "1:2, 11-20:1, 21:3"  -> ko'rsatilmagan savollar 1 ball
    """
    text = (text or "").strip().replace(";", ",")
    if not text:
        raise ValueError("Bo‘sh qolgan. Ball kiriting.")

    tokens = [t.strip() for t in text.split(",") if t.strip()]
    if not tokens:
        raise ValueError("Ball kiriting.")

    # Bitta son — barcha savollarga bir xil
    if len(tokens) == 1 and ":" not in tokens[0]:
        try:
            v = round(float(tokens[0]), 2)
            if v <= 0:
                raise ValueError
            return {str(i): v for i in range(1, question_count + 1)}
        except ValueError:
            raise ValueError("⚠️ To‘g‘ri son kiriting (masalan: 2).")

    # Hech bir token ':' emas — ketma-ket ro‘yxat
    if all(":" not in t for t in tokens):
        vals = []
        for t in tokens:
            try:
                v = round(float(t), 2)
                if v <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError(f"⚠️ '{t}' to‘g‘ri ball emas.")
            vals.append(v)
        if len(vals) != question_count:
            raise ValueError(
                f"⚠️ {len(vals)} ta ball kiritdingiz, lekin savollar soni {question_count} ta. "
                f"Har bir savol uchun bittadan ball yozing (vergul bilan)."
            )
        return {str(i): vals[i - 1] for i in range(1, question_count + 1)}

    # "1:2", "11-20:1", "21:3" — juftlik va diapazon
    result: dict[str, float] = {}
    for tok in tokens:
        if ":" not in tok:
            raise ValueError(
                f"⚠️ '{tok}' formatda emas. Namuna: 1:2, 2:2, 3:1"
            )
        key_part, _, val_part = tok.partition(":")
        key_part = key_part.strip()
        val_part = val_part.strip().replace(" ", "")
        try:
            val = round(float(val_part), 2)
            if val <= 0:
                raise ValueError
        except ValueError:
            raise ValueError(f"⚠️ '{val_part}' to‘g‘ri ball emas.")
        qs = key_part.split("-")
        try:
            if len(qs) == 1:
                start = end = int(qs[0])
            elif len(qs) == 2:
                start, end = int(qs[0]), int(qs[1])
            else:
                raise ValueError
        except ValueError:
            raise ValueError(f"⚠️ '{key_part}' savol raqami emas (1 dan {question_count} gacha).")
        if start < 1 or end > question_count or start > end:
            raise ValueError(
                f"⚠️ Savol raqamlari 1 dan {question_count} gacha bo‘lishi kerak."
            )
        for q in range(start, end + 1):
            result[str(q)] = val

    for i in range(1, question_count + 1):
        result.setdefault(str(i), 1.0)
    return result


def normalize_points(raw_points: dict | None) -> dict[str, float]:
    """Saqlanadigan JSON ni dict ga aylantiradi; null/noto‘g‘ri bo‘lsa bo‘sh dict beradi."""
    if isinstance(raw_points, dict):
        return raw_points
    if isinstance(raw_points, str):
        try:
            return json.loads(raw_points)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def format_points_line(points: dict[str, float], question_count: int) -> str:
    """Har bir savol balini o‘qiladigan ko‘rinishda beradi (bir xil bo‘lsa qisqartiradi)."""
    if not points:
        return "Barcha savollar: 1 bal"
    values = [points.get(str(i), 1.0) for i in range(1, question_count + 1)]
    if len(set(values)) == 1:
        return f"Barcha savollar: {values[0]} bal"
    parts = []
    for i, v in enumerate(values, 1):
        parts.append(f"<b>{i}-savol:</b> {v} bal")
    return "\n".join(parts)
