"""
Projection layer: takes the internal canonical profile and reshapes it
according to a runtime config, WITHOUT mutating the canonical record itself.

This separation (canonical record vs projection) is the actual point of the
"required twist." If projection logic lived inside merge.py, every new output
shape would risk corrupting the source of truth. Keeping them separate means
the canonical profile is computed once and projected many times, cheaply.
"""

import re
from typing import Any
from ..utils.normalize import normalize_phone, canonicalize_skill


def _get_path(profile_dict: dict, path: str) -> Any:
    """Resolve a dotted/bracketed path like 'emails[0]' or 'skills[].name'
    against the canonical profile dict.
    """
    # handle "skills[].name" — map over a list, pull a sub-field from each item
    list_map_match = re.match(r"^([a-zA-Z_]+)\[\]\.(.+)$", path)
    if list_map_match:
        list_field, sub_field = list_map_match.groups()
        items = profile_dict.get(list_field, []) or []
        return [item.get(sub_field) for item in items if isinstance(item, dict)]

    # handle "emails[0]" — index into a list
    index_match = re.match(r"^([a-zA-Z_]+)\[(\d+)\]$", path)
    if index_match:
        list_field, idx = index_match.groups()
        items = profile_dict.get(list_field, []) or []
        idx = int(idx)
        return items[idx] if idx < len(items) else None

    # plain field
    return profile_dict.get(path)


def _apply_normalize(value: Any, normalize: str) -> Any:
    if value is None:
        return None
    normalize_key = str(normalize).strip().lower().replace(".", "")
    if normalize_key == "e164":
        return normalize_phone(value) if isinstance(value, str) else value
    if normalize_key == "canonical":
        if isinstance(value, list):
            return [canonicalize_skill(v) for v in value]
        return canonicalize_skill(value)
    return value


def project(canonical_profile_dict: dict, config: dict) -> dict:
    """
    config shape (per the spec):
    {
      "fields": [ { "path": "...", "from": "...", "type": "...", "required": bool, "normalize": "..." }, ... ],
      "include_confidence": bool,
      "on_missing": "null" | "omit" | "error"
    }
    """
    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", False)
    fields_config = config.get("fields", [])

    output = {}
    errors = []

    for f in fields_config:
        out_path = f["path"]
        source_path = f.get("from", out_path)
        normalize_rule = f.get("normalize")
        required = f.get("required", False)

        value = _get_path(canonical_profile_dict, source_path)
        if normalize_rule and value is not None:
            value = _apply_normalize(value, normalize_rule)

        if value is None or value == [] or value == "":
            if required and on_missing == "error":
                errors.append(f"Required field '{out_path}' is missing (source: '{source_path}')")
                continue
            if on_missing == "omit":
                continue
            # default: null
            output[out_path] = None
        else:
            output[out_path] = value

    if include_confidence:
        output["overall_confidence"] = canonical_profile_dict.get("overall_confidence")
        output["provenance"] = canonical_profile_dict.get("provenance")

    if errors:
        raise ValueError("Projection validation failed: " + "; ".join(errors))

    return output


def project_default_schema(canonical_profile_dict: dict) -> dict:
    """The full default schema, no projection config applied — used when no
    custom config is supplied."""
    links = canonical_profile_dict.get("links") or {}
    return {
        "candidate_id": canonical_profile_dict.get("candidate_id"),
        "full_name": canonical_profile_dict.get("full_name"),
        "emails": canonical_profile_dict.get("emails", []),
        "phones": canonical_profile_dict.get("phones", []),
        "location": canonical_profile_dict.get("location"),
        "links": {
            "linkedin": links.get("linkedin"),
            "github": links.get("github"),
            "portfolio": links.get("portfolio"),
            "other": links.get("other", []),
        },
        "headline": canonical_profile_dict.get("headline"),
        "years_experience": canonical_profile_dict.get("years_experience"),
        "skills": canonical_profile_dict.get("skills", []),
        "experience": canonical_profile_dict.get("experience", []),
        "education": canonical_profile_dict.get("education", []),
        "provenance": canonical_profile_dict.get("provenance", []),
        "overall_confidence": canonical_profile_dict.get("overall_confidence"),
    }
