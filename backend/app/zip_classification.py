"""Filename-based category classification for ZIP-based Data Ingestion (see
routers/zip_ingestion.py). Pure, deterministic, no LLM — a tender's document pack usually arrives
as one ZIP from the buyer, and this guesses which of the 7 Data Ingestion categories each file
inside it belongs to, from its own filename, so the user doesn't have to sort them by hand.

This is a STARTING SUGGESTION only, never auto-committed: the frontend always shows every
suggestion to the user for review before any file is actually ingested (routers/zip_ingestion.py's
commit endpoint only acts on what the user confirms), so a wrong guess here is low-stakes.

Only "strategy" (evaluation/competition/instructions) and "competition_info" (SR + a number) come
from an explicit description of a real document set. The other five categories' keywords are a
best-effort default — change CATEGORY_KEYWORD_RULES below if real file names don't match them.
"""
import re
from typing import List, Optional, Tuple

# (category_key, [regex patterns]) — tried in this order, first match wins. Patterns are matched
# case-insensitively against the filename only (not any folder path it came from inside the zip).
#
# Trailing \b is deliberately avoided: \b only matches between a word char (\w, which includes
# "_" and digits) and a non-word char. Real filenames almost always butt a keyword straight up
# against "_", a number, or no separator at all ("SR2_Award...", "Team CVs.pdf", "ISO9001.pdf"),
# so a trailing \b silently fails to match exactly the filenames this is meant to catch — keep a
# LEADING \b (to avoid matching mid-word, e.g. "subcontext" must not match "context") but never a
# trailing one.
CATEGORY_KEYWORD_RULES: List[Tuple[str, List[str]]] = [
    ("strategy", [r"evaluation", r"competition", r"instruction"]),
    ("competition_info", [r"\bsr\s*-?\s*\d+"]),  # "SR2", "SR-2", "SR 2", "SR2_Award..."
    ("context", [r"\bcontext", r"client background", r"organisation profile", r"company profile"]),
    ("credentials", [r"credential", r"case stud", r"\bcv", r"biograph"]),
    ("standards", [r"\biso", r"certificat", r"\bstandard", r"accreditation", r"quality assurance"]),
    ("propositions", [r"proposition", r"pricing", r"catalog", r"value prop"]),
    ("high_scoring_responses", [r"high scor", r"winning", r"exemplar", r"past submission", r"previous bid"]),
]


def classify_filename(filename: str) -> Optional[str]:
    """Returns the suggested category key for a filename, or None if nothing matches (left for
    manual assignment in the review step)."""
    lowered = filename.lower()
    for category, patterns in CATEGORY_KEYWORD_RULES:
        if any(re.search(pattern, lowered) for pattern in patterns):
            return category
    return None
