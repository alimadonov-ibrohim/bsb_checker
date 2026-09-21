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
    ) -> Dict[str, Any]:
        """
        answer_key: {"1": "A", "2": "C", ...}
        student_answers: {"1": "A", "2": "D", "3": null, ...}

        Returns:
        {
          "correct_count": int,
          "incorrect_count": int,
          "uncertain_count": int,
          "percentage": float,
          "score": float,
          "details": {
            "1": {"student": "A", "correct": "A", "status": "correct"},
            "2": {"student": "D", "correct": "C", "status": "incorrect"},
            "3": {"student": null, "correct": "B", "status": "uncertain"},
            ...
          }
        }
        """
        details = {}
        correct = 0
        incorrect = 0
        uncertain = 0

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
            else:
                status = "incorrect"
                incorrect += 1

            details[q] = {
                "student": stud_ans,
                "correct": key_ans,
                "status": status,
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

        # Score = correct answers (1 point each by default)
        score = float(correct)

        return {
            "correct_count": correct,
            "incorrect_count": incorrect,
            "uncertain_count": uncertain,
            "percentage": percentage,
            "score": score,
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
