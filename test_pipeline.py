"""
A few targeted tests — not exhaustive coverage, but each one exercises a
decision I had to actually make while building this, which is what the
assignment says it's evaluating.

Run with: python -m pytest test_pipeline.py -v
(or just: python test_pipeline.py, since these don't need pytest features)
"""

from schema import FieldValue, SourceType
from merge import merge_sources
from project import project, project_default_schema
from extractors import extract_recruiter_csv, extract_github_profile
from normalize import normalize_phone, normalize_date


def test_conflict_resolution_picks_highest_confidence():
    """Two sources disagree on full_name — recruiter_csv (0.85) should beat
    github (0.6)."""
    values = [
        FieldValue("full_name", "Asha Verma", SourceType.RECRUITER_CSV, "direct", 0.85),
        FieldValue("full_name", "A. Verma", SourceType.GITHUB, "direct", 0.6),
    ]
    profile = merge_sources("c1", values)
    assert profile.full_name == "Asha Verma", f"got {profile.full_name}"
    # the loser must still be recorded for auditability
    discarded = [p for p in profile.provenance if p.method.startswith("discarded")]
    assert len(discarded) == 1
    print("PASS: conflict resolution picks highest confidence, records loser")


def test_tie_broken_by_source_priority_deterministically():
    """Equal confidence -> must resolve the same way every time, not randomly."""
    values = [
        FieldValue("full_name", "Name From ATS", SourceType.ATS_JSON, "direct", 0.85),
        FieldValue("full_name", "Name From Recruiter", SourceType.RECRUITER_CSV, "direct", 0.85),
    ]
    results = {merge_sources("c1", values).full_name for _ in range(5)}
    assert len(results) == 1, "tie resolution is non-deterministic!"
    assert list(results)[0] == "Name From Recruiter"  # recruiter_csv has higher priority
    print("PASS: ties resolved deterministically by source priority")


def test_multi_value_field_keeps_both_not_just_winner():
    """Two emails from two sources should both survive — this is not a
    conflict, it's two valid facts."""
    values = [
        FieldValue("emails", "a@x.com", SourceType.RECRUITER_CSV, "direct", 0.9),
        FieldValue("emails", "b@x.com", SourceType.ATS_JSON, "direct", 0.85),
    ]
    profile = merge_sources("c1", values)
    assert set(profile.emails) == {"a@x.com", "b@x.com"}
    print("PASS: multi-value fields union correctly instead of picking one winner")


def test_garbage_csv_degrades_to_empty_not_crash():
    """A CSV with the wrong columns must not raise — and must not invent a name."""
    garbage = "foo,bar\nbaz,qux\n"
    result = extract_recruiter_csv(garbage)
    assert result == []
    print("PASS: garbage CSV produces empty extraction, no crash, no invented data")


def test_phone_normalization_e164():
    assert normalize_phone("09876543210") == "+919876543210"
    assert normalize_phone("+1 415 555 0100") == "+14155550100"
    assert normalize_phone("123") is None  # too short — must not guess
    print("PASS: phone normalization handles common formats and rejects junk")


def test_date_normalization_handles_month_name_and_year_only():
    assert normalize_date("Jan 2022") == "2022-01"
    assert normalize_date("2023") == "2023-01"
    assert normalize_date("not a date") is None
    print("PASS: date normalization covers common formats, refuses to guess on garbage")


def test_custom_projection_respects_on_missing_error():
    """If a required field is genuinely absent and on_missing=error, the
    projection must raise — silently returning null would hide a real
    pipeline failure from the caller."""
    canonical = project_default_schema({"candidate_id": "c1", "full_name": None})
    config = {
        "fields": [{"path": "full_name", "type": "string", "required": True}],
        "on_missing": "error",
    }
    try:
        project(canonical, config)
        assert False, "expected ValueError to be raised"
    except ValueError as e:
        assert "full_name" in str(e)
    print("PASS: on_missing='error' surfaces missing required fields loudly")


def test_github_skills_get_lower_confidence_than_declared_skills():
    """Inferred skills (from repo language stats) should never outrank a
    skill the candidate explicitly declared — this is a deliberate design
    choice, not an accident, so it deserves a regression test."""
    profile = {"login": "x", "name": "X", "bio": ""}
    repos = [{"language": "Python"}]
    values = extract_github_profile(profile, repos)
    skill_values = [v for v in values if v.field_name == "skills"]
    assert skill_values[0].confidence < 0.85, "inferred skill confidence too high"
    print("PASS: GitHub-inferred skills are discounted relative to declared skills")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
