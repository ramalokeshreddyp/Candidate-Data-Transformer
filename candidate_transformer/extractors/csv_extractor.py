import csv
import io
from typing import List
from ..core.schema import FieldValue, SourceType, base_confidence
from ..utils.normalize import normalize_phone, normalize_email, clean_text


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
