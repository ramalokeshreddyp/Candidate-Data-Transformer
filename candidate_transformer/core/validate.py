"""
Validation: checked right before output is returned, never invented during
construction. A type mismatch here means the pipeline has a bug — it should
surface loudly, not get silently coerced.
"""


def validate_default_schema(profile: dict) -> list[str]:
    errors = []
    if not isinstance(profile.get("candidate_id"), str) or not profile["candidate_id"]:
        errors.append("candidate_id must be a non-empty string")
    if profile.get("full_name") is not None and not isinstance(profile["full_name"], str):
        errors.append("full_name must be a string or null")
    if not isinstance(profile.get("emails", []), list):
        errors.append("emails must be a list")
    if not isinstance(profile.get("phones", []), list):
        errors.append("phones must be a list")
    for p in profile.get("phones", []):
        if p and not p.startswith("+"):
            errors.append(f"phone '{p}' is not E.164 normalized")
    if not isinstance(profile.get("skills", []), list):
        errors.append("skills must be a list")
    for s in profile.get("skills", []):
        if not isinstance(s, dict) or "name" not in s:
            errors.append(f"skill entry malformed: {s}")
    conf = profile.get("overall_confidence")
    if conf is not None and not (0 <= conf <= 1):
        errors.append(f"overall_confidence out of [0,1] range: {conf}")
    return errors


def validate_custom_projection(output: dict, config: dict) -> list[str]:
    """Looser check for custom projections — we only verify that every
    required field per the config is actually present (already enforced at
    projection time for on_missing='error', but re-checked here in case the
    caller used 'null' and still wants a final sanity pass)."""
    errors = []
    for f in config.get("fields", []):
        if f.get("required") and f["path"] not in output:
            errors.append(f"Required field '{f['path']}' missing from projected output")
    return errors
