"""
Normalization functions. Kept deliberately simple and dependency-light so the
whole pipeline runs with stdlib only — easier to audit, easier to explain.
"""

import re
import unicodedata


# A small, deliberately incomplete country-code map. Real systems would use a
# library like phonenumbers, but for this assignment scope, a defaulted-to-India
# heuristic is acceptable and I say so explicitly in the design doc rather than
# pretending it's more robust than it is.
_DEFAULT_COUNTRY_CODE = "91"  # India, since most candidates in this exercise are Indian


def normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d+]", "", raw)
    if not digits:
        return None
    if digits.startswith("+"):
        return digits
    # strip leading 0 (common in Indian numbers written as 0XXXXXXXXXX)
    digits = digits.lstrip("0")
    if len(digits) == 10:
        return f"+{_DEFAULT_COUNTRY_CODE}{digits}"
    if len(digits) > 10:
        return f"+{digits}"
    return None  # too short to be a real number — degrade to null, never invent


def normalize_email(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().lower()
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw):
        return raw
    return None


# Canonical skill map: lowercase alias -> canonical display name.
# This is intentionally a small curated set rather than a giant taxonomy —
# the assignment doesn't require enterprise-grade skill ontology, it requires
# me to demonstrate I understand *why* canonicalization matters.
_SKILL_ALIASES = {
    "js": "JavaScript", "javascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "py": "Python", "python": "Python", "python3": "Python",
    "reactjs": "React", "react.js": "React", "react": "React",
    "nodejs": "Node.js", "node.js": "Node.js", "node": "Node.js",
    "golang": "Go", "go": "Go",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "aws": "AWS", "amazon web services": "AWS",
    "django": "Django", "flask": "Flask",
    "c++": "C++", "cpp": "C++",
    "sql": "SQL",
}


def canonicalize_skill(raw: str) -> str:
    key = raw.strip().lower()
    return _SKILL_ALIASES.get(key, raw.strip().title())


def normalize_date(raw: str) -> str | None:
    """Best-effort normalization to YYYY-MM. Returns None rather than guessing
    a value we cannot support from the input."""
    if not raw:
        return None
    raw = raw.strip()
    # Already YYYY-MM or YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # "Jan 2022", "January 2022"
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
        "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{4})$", raw)
    if m:
        mon_key = m.group(1)[:3].lower()
        if mon_key in months:
            return f"{m.group(2)}-{months[mon_key]}"
    # Year only — treat as January, lower confidence is handled by caller
    m = re.match(r"^(\d{4})$", raw)
    if m:
        return f"{m.group(1)}-01"
    return None


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    # normalize unicode (curly quotes, etc.) and collapse whitespace
    raw = unicodedata.normalize("NFKC", raw)
    return re.sub(r"\s+", " ", raw).strip()
