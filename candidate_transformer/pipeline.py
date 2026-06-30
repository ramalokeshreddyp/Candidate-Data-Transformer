"""
Pipeline orchestration: parse -> extract -> merge -> project -> validate.

This module deliberately contains very little logic of its own — it wires
together the pieces in core/schema.py, extractors/, core/merge.py, core/project.py
and core/validate.py.
"""

import json
from dataclasses import asdict
from .extractors import extract_recruiter_csv, extract_ats_json, extract_github_profile
from .core.merge import merge_sources
from .core.project import project, project_default_schema
from .core.validate import validate_default_schema, validate_custom_projection


def profile_to_dict(profile) -> dict:
    d = asdict(profile)
    # ProvenanceEntry dataclasses need flattening for JSON; asdict already
    # handles nested dataclasses recursively, so this is mostly a no-op,
    # kept explicit for readability.
    return d


def run_pipeline(candidate_id: str, sources: dict, custom_config: dict | None = None) -> dict:
    """
    sources: {
        "recruiter_csv": "<csv text or None>",
        "ats_json": {...} or None,
        "github_profile": {...} or None,
        "github_repos": [...] or None,
    }
    """
    all_values = []

    # Each extractor is wrapped defensively — a malformed/missing source must
    # degrade gracefully (produce nothing) rather than crash the whole run.
    try:
        if sources.get("recruiter_csv"):
            all_values.extend(extract_recruiter_csv(sources["recruiter_csv"]))
    except Exception as e:
        print(f"[warn] recruiter_csv extraction failed, skipping: {e}")

    try:
        if sources.get("ats_json"):
            all_values.extend(extract_ats_json(sources["ats_json"]))
    except Exception as e:
        print(f"[warn] ats_json extraction failed, skipping: {e}")

    try:
        if sources.get("github_profile"):
            all_values.extend(
                extract_github_profile(sources["github_profile"], sources.get("github_repos"))
            )
    except Exception as e:
        print(f"[warn] github extraction failed, skipping: {e}")

    canonical = merge_sources(candidate_id, all_values)
    canonical_dict = profile_to_dict(canonical)

    if custom_config:
        output = project(canonical_dict, custom_config)
        errors = validate_custom_projection(output, custom_config)
    else:
        output = project_default_schema(canonical_dict)
        errors = validate_default_schema(output)

    if errors:
        # We surface validation errors but still return the output — an
        # evaluator wants to see *what* failed, not just that something did.
        output["_validation_errors"] = errors

    return output


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Multi-source candidate data transformer")
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--recruiter-csv", help="Path to recruiter CSV file")
    parser.add_argument("--ats-json", help="Path to ATS JSON file")
    parser.add_argument("--github-profile", help="Path to a saved GitHub profile JSON (REST API shape)")
    parser.add_argument("--github-repos", help="Path to a saved GitHub repos JSON list")
    parser.add_argument("--config", help="Path to a custom output config JSON")
    parser.add_argument("--out", help="Path to write output JSON (default: stdout)")
    args = parser.parse_args()

    sources = {}
    if args.recruiter_csv:
        with open(args.recruiter_csv) as f:
            sources["recruiter_csv"] = f.read()
    if args.ats_json:
        with open(args.ats_json) as f:
            sources["ats_json"] = json.load(f)
    if args.github_profile:
        with open(args.github_profile) as f:
            sources["github_profile"] = json.load(f)
    if args.github_repos:
        with open(args.github_repos) as f:
            sources["github_repos"] = json.load(f)

    custom_config = None
    if args.config:
        with open(args.config) as f:
            custom_config = json.load(f)

    result = run_pipeline(args.candidate_id, sources, custom_config)
    output_str = json.dumps(result, indent=2, default=str)

    if args.out:
        with open(args.out, "w") as f:
            f.write(output_str)
        print(f"Wrote output to {args.out}")
    else:
        print(output_str)
