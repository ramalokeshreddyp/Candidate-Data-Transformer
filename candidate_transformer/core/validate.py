"""
Validation: checked right before output is returned, never invented during
construction. A type mismatch here means the pipeline has a bug — it should
surface loudly, not get silently coerced.
"""

import re

def validate_default_schema(profile: dict) -> list[str]:
    errors = []
    
    # candidate_id validation
    if not isinstance(profile.get("candidate_id"), str) or not profile["candidate_id"]:
        errors.append("candidate_id must be a non-empty string")
        
    # full_name validation
    if profile.get("full_name") is not None and not isinstance(profile["full_name"], str):
        errors.append("full_name must be a string or null")
        
    # emails validation
    if not isinstance(profile.get("emails", []), list):
        errors.append("emails must be a list")
    else:
        for email in profile.get("emails", []):
            if not isinstance(email, str):
                errors.append(f"email '{email}' must be a string")
                
    # phones validation
    if not isinstance(profile.get("phones", []), list):
        errors.append("phones must be a list")
    else:
        for p in profile.get("phones", []):
            if not isinstance(p, str):
                errors.append(f"phone '{p}' must be a string")
            elif p and not p.startswith("+"):
                errors.append(f"phone '{p}' is not E.164 normalized")
                
    # location validation
    loc = profile.get("location")
    if loc is not None:
        if not isinstance(loc, dict):
            errors.append("location must be a dictionary")
        else:
            allowed_keys = {"city", "region", "country"}
            for k in loc.keys():
                if k not in allowed_keys:
                    errors.append(f"location key '{k}' is invalid; must be city, region, or country")
            country = loc.get("country")
            if country is not None:
                if not isinstance(country, str) or len(country) != 2 or not country.isupper():
                    errors.append(f"location country '{country}' must be a 2-character ISO-3166 alpha-2 uppercase string")

    # links validation
    links = profile.get("links")
    if links is not None:
        if not isinstance(links, dict):
            errors.append("links must be a dictionary")
        else:
            allowed_keys = {"linkedin", "github", "portfolio", "other"}
            for k in links.keys():
                if k not in allowed_keys:
                    errors.append(f"links key '{k}' is invalid; must be linkedin, github, portfolio, or other")
            if "other" in links and not isinstance(links["other"], list):
                errors.append("links['other'] must be a list of strings")

    # headline validation
    if profile.get("headline") is not None and not isinstance(profile["headline"], str):
        errors.append("headline must be a string or null")

    # years_experience validation
    years_exp = profile.get("years_experience")
    if years_exp is not None and not isinstance(years_exp, (int, float)):
        errors.append("years_experience must be a number or null")

    # skills validation
    if not isinstance(profile.get("skills", []), list):
        errors.append("skills must be a list")
    else:
        for s in profile.get("skills", []):
            if not isinstance(s, dict) or "name" not in s:
                errors.append(f"skill entry malformed: {s}")
            else:
                if not isinstance(s.get("name"), str):
                    errors.append(f"skill name must be a string: {s}")
                if "confidence" in s and not isinstance(s["confidence"], (int, float)):
                    errors.append(f"skill confidence must be a number: {s}")
                if "sources" in s and not isinstance(s["sources"], list):
                    errors.append(f"skill sources must be a list: {s}")

    # experience validation
    if not isinstance(profile.get("experience", []), list):
        errors.append("experience must be a list")
    else:
        for exp in profile.get("experience", []):
            if not isinstance(exp, dict):
                errors.append(f"experience entry must be a dictionary: {exp}")
                continue
            required_keys = {"company", "title", "start", "end", "summary"}
            for k in required_keys:
                if k not in exp:
                    errors.append(f"experience entry missing required key '{k}': {exp}")
            for dkey in ["start", "end"]:
                val = exp.get(dkey)
                if val is not None:
                    if not isinstance(val, str) or not re.match(r"^\d{4}-\d{2}$", val):
                        errors.append(f"experience date '{dkey}': '{val}' must be in YYYY-MM format")

    # education validation
    if not isinstance(profile.get("education", []), list):
        errors.append("education must be a list")
    else:
        for edu in profile.get("education", []):
            if not isinstance(edu, dict):
                errors.append(f"education entry must be a dictionary: {edu}")
                continue
            required_keys = {"institution", "degree", "field", "end_year"}
            for k in required_keys:
                if k not in edu:
                    errors.append(f"education entry missing required key '{k}': {edu}")

    # provenance validation
    if not isinstance(profile.get("provenance", []), list):
        errors.append("provenance must be a list")
    else:
        for prov in profile.get("provenance", []):
            if not isinstance(prov, dict):
                errors.append(f"provenance entry must be a dictionary: {prov}")
                continue
            required_keys = {"field", "source", "method"}
            for k in required_keys:
                if k not in prov:
                    errors.append(f"provenance entry missing required key '{k}': {prov}")

    # overall_confidence validation
    conf = profile.get("overall_confidence")
    if conf is not None and not (0 <= conf <= 1):
        errors.append(f"overall_confidence out of [0,1] range: {conf}")

    return errors


def validate_custom_projection(output: dict, config: dict) -> list[str]:
    """Looser check for custom projections — we only verify that every
    required field per the config is actually present."""
    errors = []
    for f in config.get("fields", []):
        if f.get("required") and f["path"] not in output:
            errors.append(f"Required field '{f['path']}' missing from projected output")
    return errors
