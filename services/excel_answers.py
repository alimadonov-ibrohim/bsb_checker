"""
Excel Answers Parser — read student answers from .xlsx / .csv files.

Pure Python + openpyxl. Does NOT solve questions — only reads what is
already written in the sheet and returns {question_number: answer_letter}.

Supported layouts (heuristic, combined):
  - "1-A", "1. A", "1) A", "1 : A", "Q1=A"   (inline in one cell)
  - two-column table: [question number] [letter]
  - vertical list: a single column of letters (row 1 = question 1)
  - horizontal grid: header row of question numbers, letters in the row below
  - a row of consecutive letters without numbers (first = question 1)

Also tries to find student name and class if the sheet has labels like
"Ism:", "Familiya:", "Sinf:".
"""
import re
import csv
from pathlib import Path

LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

INLINE = re.compile(
    r"^(?:q|savol|s|no\.?|#)?\s*(\d{1,4})\s*[.)\]:=\-]?\s*([a-zA-Z])(?:\s*|$)",
    re.IGNORECASE,
)
INT_LABEL = re.compile(r"^(?:q|savol|s|no\.?|#|t/r|tr)\s*(\d+)$", re.IGNORECASE)
PURE_INT = re.compile(r"^\d+$")
LABEL_WORDS = ("savol", "no.", "№", "t/r", "no", "#", "q")


def _norm(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v):
    """Extract a question number from a cell value."""
    s = _norm(v)
    if not s:
        return None
    m = PURE_INT.match(s)
    if m:
        return int(s)
    m = INT_LABEL.match(s)
    return int(m.group(1)) if m else None


def _letter(v):
    """Extract a single answer letter from a cell value."""
    s = _norm(v)
    if not s:
        return None
    s = s.upper()
    if s in LETTERS:
        return s
    return None


def _is_label(v):
    s = _norm(v)
    if not s:
        return False
    low = s.lower().strip()
    return any(w in low for w in LABEL_WORDS)


def _read_rows(path: str) -> list[list]:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".xls":
        raise ValueError(
            "Eski .xls formati qo‘llab-quvvatlanmaydi. Iltimos faylni "
            "Excel'da 'Save As' → .xlsx qilib saqlang."
        )
    if suffix == ".csv":
        with open(p, newline="", encoding="utf-8-sig", errors="replace") as f:
            return [row for row in csv.reader(f)]
    from openpyxl import load_workbook

    wb = load_workbook(p, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(list(row))
    return rows


def _find_name_class(rows: list[list]):
    """Look for labels like Ism/Familiya/Sinf and take the neighbouring value."""
    labels = {
        "ism": "name",
        "familiya": "name",
        "f.i.sh": "name",
        "fish": "name",
        "f.io": "name",
        "f.i.o": "name",
        "o‘quvchi": "name",
        "oquvchi": "name",
        "talaba": "name",
        "name": "name",
        "surname": "name",
        "sinf": "class",
        "sınıf": "class",
        "class": "class",
        "sinfi": "class",
    }
    name = None
    klass = None
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            s = _norm(v)
            if not s:
                continue
            key = s.lower().strip(" :.-—")
            kind = None
            for lab, k in labels.items():
                if lab in key:
                    kind = k
                    break
            if not kind:
                continue
            val = None
            # try right neighbour
            for step in (1, 2):
                if c + step < len(row):
                    nr = _norm(row[c + step])
                    if nr and not _is_label(nr) and _int(nr) is None and _letter(nr) is None:
                        val = nr
                        break
            # try below
            if val is None:
                for step in (1, 2):
                    if r + step < len(rows):
                        nr = _norm(rows[r + step][c]) if c < len(rows[r + step]) else None
                        if nr and not _is_label(nr) and _int(nr) is None and _letter(nr) is None:
                            val = nr
                            break
            if val:
                if kind == "name" and not name:
                    name = val
                elif kind == "class" and not klass:
                    klass = val
    return (name, klass)


def _map_two_column_rows(rows: list[list]) -> dict:
    """Numeric cell followed by a letter in the same row (a table of Q -> answer)."""
    out = {}
    for row in rows:
        vals = [_norm(v) for v in row]
        for i in range(len(vals) - 1):
            q = _int(vals[i])
            if q is None:
                continue
            # answer in the next cell, or next non-empty cell
            for j in range(i + 1, min(i + 3, len(vals))):
                ans = _letter(vals[j])
                if ans:
                    if q not in out:
                        out[q] = ans
                    break
    return out


def _map_single_column(rows: list[list], max_questions: int = 200) -> dict:
    """A column of consecutive letters (row index => question number)."""
    out = {}
    for col in range(len(rows[0])):
        letters = []
        for r, row in enumerate(rows):
            if col >= len(row):
                continue
            s = _norm(row[col])
            if _is_label(s):
                continue
            ans = _letter(s)
            if ans:
                letters.append((r, ans))
        if len(letters) < 2:
            continue
        # find the column with the most letters
        if len(letters) > len(out):
            out = {str(i + 1): a for i, (_, a) in enumerate(letters)}
    return out


def _map_header_grid(rows: list[list]) -> dict:
    """Header row of question numbers 1..N with letters directly below."""
    for r in range(len(rows) - 1):
        header = rows[r]
        numerics = {}
        for c, v in enumerate(header):
            q = _int(v)
            if q is not None and not _is_label(v):
                numerics[c] = q
        if not numerics:
            continue
        seq = sorted(numerics.items())
        # require consecutive 1..N
        expected = list(range(1, len(seq) + 1))
        actual = [q for _, q in seq]
        if actual != expected:
            continue
        below = rows[r + 1]
        out = {}
        for c, q in seq:
            ans = _letter(below[c]) if c < len(below) else None
            if ans:
                out[str(q)] = ans
        if out:
            return out
    return {}


def _is_personal_label(v):
    s = (str(v) or "").strip(" :.—-").lower()
    return any(
        w in s
        for w in ("ism", "familiya", "fish", "sinf", "class", "talaba",
                  "oquvchi", "o‘quvchi", "sinfi", "surname", "name")
    )


def _map_inline(rows: list[list]) -> dict:
    out = {}
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            s = _norm(v)
            if not s:
                continue
            m = INLINE.match(s)
            if not m:
                continue
            # Skip cells right next to a personal label, e.g. "Sinf: 9-A".
            left = _norm(row[c - 1]) if c - 1 >= 0 else None
            above = _norm(rows[r - 1][c]) if r - 1 >= 0 and c < len(rows[r - 1]) else None
            if _is_personal_label(left) or _is_personal_label(above):
                continue
            q = int(m.group(1))
            ans = m.group(2).upper()
            if q not in out and ans in LETTERS:
                out[q] = ans
    return out


def _map_row_letters(rows: list[list], min_letters: int = 3) -> dict:
    """A single row of consecutive answer letters (first cell = question 1)."""
    best = {}
    for row in rows:
        letters = [_letter(v) for v in row]
        if len(letters) < min_letters:
            continue
        out = {str(i + 1): a for i, a in enumerate(letters) if a}
        if len(out) > len(best):
            best = out
    return best


def _map_header_label_grid(rows: list[list]) -> dict:
    """Grid where first row = 'Savol' and the row below (or same row answers)."""
    for r in range(len(rows) - 1):
        header = rows[r]
        has_label = any(_is_label(v) for c, v in enumerate(header) if v)
        if not has_label:
            continue
        below = rows[r + 1]
        out = {}
        # columns: number in header -> letter below
        numerics = {}
        for c, v in enumerate(header):
            q = _int(v)
            if q is not None:
                numerics[c] = q
        if len(numerics) >= 1:
            # case where header contains 'Savol' at col0 and questions at other cols
            seq = sorted(numerics.items())
            if [q for _, q in seq] == list(range(1, len(seq) + 1)):
                for c, q in seq:
                    ans = _letter(below[c]) if c < len(below) else None
                    if ans:
                        out[str(q)] = ans
                if out:
                    return out
    return {}


def parse_student_excel(path: str) -> dict:
    """
    Parse a student-answer spread sheet.

    Returns:
    {
      "name": str | None,
      "class_name": str | None,
      "answers": {"1": "A", "2": "C", ...}
    }
    """
    rows = _read_rows(path)
    if not rows:
        return {"name": None, "class_name": None, "answers": {}}

    name, klass = _find_name_class(rows)

    combined = {}
    combined.update(_map_inline(rows))
    combined.update(_map_two_column_rows(rows))
    combined.update(_map_header_grid(rows))
    combined.update(_map_header_label_grid(rows))
    # Row/column-of-letters fallbacks misalign when the sheet also has question
    # numbers, so only use them when nothing else produced answers.
    if not combined:
        has_numbers = any(_int(v) is not None for row in rows for v in row)
        if not has_numbers:
            combined.update(_map_row_letters(rows))
            combined.update(_map_single_column(rows))

    answers = {
        str(q): a
        for q, a in sorted(combined.items(), key=lambda kv: int(str(kv[0])) if str(kv[0]).isdigit() else 0)
        if str(q).isdigit() and 1 <= int(q) <= 400 and a
    }

    return {"name": name, "class_name": klass, "answers": answers}