from typing import List
from ..core.schema import FieldValue, SourceType, base_confidence
from ..utils.normalize import normalize_email, clean_text


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
