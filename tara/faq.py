"""Loads TeaTrail's FAQ sheet (Category, Question, Answer) from Google Sheets."""

import csv
import io
import urllib.request
from pathlib import Path

FAQ_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1bf4cNECDbar3tUeJn2-F64gahDJ001sGDtcDrv8V7Hc/export?format=csv"
)

# The last sheet that loaded successfully is saved here, so Tara still works
# if Google Sheets can't be reached when she starts.
CACHE_FILE = Path(__file__).resolve().parent.parent / ".faq_cache.csv"


def _parse(text: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        category = (row.get("Category") or "").strip()
        question = (row.get("Question") or "").strip()
        answer = (row.get("Answer") or "").strip()
        if category and question and answer:
            rows.append({"category": category, "question": question, "answer": answer})
    return rows


def load_faqs() -> list[dict]:
    """Downloads the FAQ sheet. Falls back to the last saved copy if offline."""
    try:
        with urllib.request.urlopen(FAQ_CSV_URL, timeout=15) as resp:
            text = resp.read().decode("utf-8")
        rows = _parse(text)
        if not rows:
            raise ValueError("The FAQ sheet has no rows with Category, Question and Answer.")
        CACHE_FILE.write_text(text, encoding="utf-8")
        return rows
    except Exception as err:  # network error, sign-in page, empty sheet...
        if CACHE_FILE.exists():
            print(f"[tara] Couldn't load the FAQ sheet ({err}). Using the saved copy.")
            return _parse(CACHE_FILE.read_text(encoding="utf-8"))
        raise RuntimeError(
            "Couldn't load the TeaTrail FAQ sheet. Check your internet and that the "
            "sheet is shared as 'Anyone with the link'."
        ) from err


def faqs_as_text(rows: list[dict]) -> str:
    """Formats the rows so the category sits right next to each answer."""
    return "\n\n".join(
        f"[{i}] Category: {r['category']}\nQ: {r['question']}\nA: {r['answer']}"
        for i, r in enumerate(rows, start=1)
    )
