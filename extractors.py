"""
Source extractors. Each extractor takes raw source-specific input and emits a
list of FieldValue objects (field, value, source, method, confidence) — it does
NOT write into the canonical profile directly. That separation matters: the
merge step is the only place that decides who wins, so extractors stay simple
and testable in isolation.
"""

import csv
import json
import io
from typing import List
from schema import FieldValue, SourceType, base_confidence
from normalize import normalize_phone, normalize_email, canonicalize_skill, clean_text


def extract_recruiter_csv(csv_text: str) -> List[FieldValue]:
    """Structured source. Expected columns: name, email, phone, current_company, title.
    Missing or malformed columns degrade gracefully — we never crash on a bad CSV.
    """
    out: List[FieldValue] = []
    if not csv_text or not csv_text.strip():
        return out

    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # Defensive .get() everywhere — a CSV missing a column should not crash the run.
        name = clean_text(row.get("name", "") or "")
        email = normalize_email(row.get("email", "") or "")
        phone = normalize_phone(row.get("phone", "") or "")
        company = clean_text(row.get("current_company", "") or "")
        title = clean_text(row.get("title", "") or "")

        if name:
            out.append(FieldValue("full_name", name, SourceType.RECRUITER_CSV, "direct",
                                   base_confidence("full_name", "recruiter_csv")))
        if email:
            out.append(FieldValue("emails", email, SourceType.RECRUITER_CSV, "direct",
                                   base_confidence("emails", "recruiter_csv")))
        if phone:
            out.append(FieldValue("phones", phone, SourceType.RECRUITER_CSV, "normalized",
                                   base_confidence("phones", "recruiter_csv")))
        if title and company:
            # Treat as a single current-experience entry; confidence is moderate
            # because recruiter CSVs are frequently stale on title/company.
            out.append(FieldValue(
                "experience",
                {"company": company, "title": title, "start": None, "end": None, "summary": ""},
                SourceType.RECRUITER_CSV, "direct",
                base_confidence("experience", "recruiter_csv") - 0.1  # extra discount: this is a snapshot, not a history
            ))
        # only break out of the loop after the first row that has a name —
        # this extractor is single-candidate-per-call by design (one CSV row
        # set belongs to one candidate in this assignment's scope)
        break

    return out


def extract_ats_json(blob: dict) -> List[FieldValue]:
    """Semi-structured source with non-matching field names. This is the
    'translate someone else's schema into mine' problem — the realistic part
    of integration work.
    """
    out: List[FieldValue] = []
    if not blob:
        return out

    # ATS systems love inconsistent naming. Map known variants defensively.
    name = clean_text(blob.get("candidateName") or blob.get("full_name") or blob.get("name") or "")
    email = normalize_email(blob.get("contactEmail") or blob.get("email") or "")
    company = clean_text(blob.get("employer") or blob.get("current_company") or "")
    title = clean_text(blob.get("currentTitle") or blob.get("title") or "")

    if name:
        out.append(FieldValue("full_name", name, SourceType.ATS_JSON, "direct",
                               base_confidence("full_name", "ats_json")))
    if email:
        out.append(FieldValue("emails", email, SourceType.ATS_JSON, "direct",
                               base_confidence("emails", "ats_json")))
    if title and company:
        out.append(FieldValue(
            "experience",
            {"company": company, "title": title, "start": None, "end": None, "summary": ""},
            SourceType.ATS_JSON, "direct", base_confidence("experience", "ats_json")
        ))

    return out


def extract_github_profile(profile_json: dict, repos_json: list | None = None) -> List[FieldValue]:
    """Unstructured-ish source via public REST API shape.
    name, bio, public repo languages -> inferred skills.

    Design choice: I treat repo languages as *inferred* skills with explicitly
    lower confidence than a self-reported skill, because "I have a repo with
    some JS in it" is weaker evidence than "I listed this on my resume."
    """
    out: List[FieldValue] = []
    if not profile_json:
        return out

    name = clean_text(profile_json.get("name") or "")
    bio = clean_text(profile_json.get("bio") or "")
    login = profile_json.get("login")

    if name:
        out.append(FieldValue("full_name", name, SourceType.GITHUB, "direct",
                               base_confidence("full_name", "github")))
    if bio:
        out.append(FieldValue("headline", bio, SourceType.GITHUB, "direct",
                               base_confidence("headline", "github")))
    if login:
        out.append(FieldValue("links", f"https://github.com/{login}", SourceType.GITHUB, "direct",
                               base_confidence("links", "github")))

    if repos_json:
        langs = set()
        for repo in repos_json:
            lang = repo.get("language")
            if lang:
                langs.add(lang)
        for lang in langs:
            out.append(FieldValue(
                "skills", canonicalize_skill(lang), SourceType.GITHUB, "inferred-from-repos",
                base_confidence("skills", "github") - 0.15  # inferred, not declared — discount it
            ))

    return out
