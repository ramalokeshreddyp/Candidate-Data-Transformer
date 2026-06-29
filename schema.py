"""
Canonical candidate profile schema and confidence scoring.

Design note: confidence is computed per-field, not per-source. A source can be
highly reliable for one field (e.g. recruiter CSV for phone) and unreliable for
another (e.g. a CSV row with a stale title vs a fresh GitHub bio). This avoids
the common mistake of trusting an entire source uniformly.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class SourceType(str, Enum):
    RECRUITER_CSV = "recruiter_csv"
    ATS_JSON = "ats_json"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    RESUME = "resume"
    RECRUITER_NOTES = "recruiter_notes"


# Base reliability per source, per field family. This is a starting prior —
# not gospel. A recruiter CSV is usually authoritative for contact info
# (someone typed it in deliberately) but unreliable for skills (rarely
# updated, often copy-pasted from an old req). GitHub is the opposite:
# untrustworthy for "current company" (people forget to update bios) but
# excellent ground truth for technical skills (inferred from actual repos).
FIELD_SOURCE_PRIORS = {
    "full_name":        {"recruiter_csv": 0.85, "ats_json": 0.85, "linkedin": 0.9, "resume": 0.8, "github": 0.6},
    "emails":           {"recruiter_csv": 0.9,  "ats_json": 0.85, "resume": 0.7,  "github": 0.4, "linkedin": 0.3},
    "phones":           {"recruiter_csv": 0.9,  "ats_json": 0.8,  "resume": 0.6},
    "location":         {"linkedin": 0.85, "resume": 0.7, "recruiter_csv": 0.5, "ats_json": 0.5, "github": 0.4},
    "headline":         {"linkedin": 0.9,  "github": 0.6, "resume": 0.5},
    "years_experience":  {"resume": 0.75, "linkedin": 0.7, "ats_json": 0.5},
    "skills":           {"github": 0.85, "resume": 0.7, "linkedin": 0.6, "recruiter_notes": 0.4},
    "experience":       {"linkedin": 0.85, "resume": 0.8, "ats_json": 0.6},
    "education":        {"resume": 0.85, "linkedin": 0.8},
    "links":            {"recruiter_csv": 0.7, "linkedin": 0.9, "github": 0.9},
}

DEFAULT_PRIOR = 0.5


def base_confidence(field_name: str, source: str) -> float:
    return FIELD_SOURCE_PRIORS.get(field_name, {}).get(source, DEFAULT_PRIOR)


@dataclass
class ProvenanceEntry:
    field: str
    source: str
    method: str  # e.g. "direct", "regex-extracted", "inferred", "merged"
    confidence: float


@dataclass
class FieldValue:
    """A single candidate value for a field, before merge.

    field_name is explicit (not inferred from value shape) — early in
    building this I tried guessing the target field from the value's shape
    (string with '@' = email, etc.) and it broke the moment a name happened
    to look unusual. Explicit tagging at the extractor is more code but it's
    the difference between "probably works" and "deterministically correct."
    """
    field_name: str
    value: Any
    source: SourceType
    method: str
    confidence: float


@dataclass
class CanonicalProfile:
    candidate_id: str
    full_name: Optional[str] = None
    emails: list = field(default_factory=list)
    phones: list = field(default_factory=list)
    location: Optional[dict] = None
    links: dict = field(default_factory=dict)
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    education: list = field(default_factory=list)
    provenance: list = field(default_factory=list)
    overall_confidence: float = 0.0
