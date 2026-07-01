"""
A suite of targeted unit tests verifying merge, conflict resolution,
normalization, validation, and projection.
"""

from candidate_transformer.core.schema import FieldValue, SourceType
from candidate_transformer.core.merge import merge_sources
from candidate_transformer.core.project import project, project_default_schema
from candidate_transformer.extractors import extract_recruiter_csv, extract_github_profile
from candidate_transformer.utils.normalize import normalize_phone, normalize_date


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


def test_custom_projection_accepts_e164_with_dot_notation():
    canonical = {
        "phones": ["09876543210"],
        "overall_confidence": 0.5,
        "provenance": [],
    }
    config = {
        "fields": [
            {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E.164"}
        ],
        "on_missing": "null",
    }
    projected = project(canonical, config)
    assert projected["phone"] == "+919876543210"
    print("PASS: custom projection accepts E.164 normalize token")


def test_default_projection_has_fixed_links_shape():
    projected = project_default_schema({"candidate_id": "c1", "links": {"github": "https://github.com/x"}})
    links = projected["links"]
    assert set(links.keys()) == {"linkedin", "github", "portfolio", "other"}
    assert links["github"] == "https://github.com/x"
    assert links["other"] == []
    print("PASS: default projection emits fixed links shape")


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


def test_validation_detects_malformed_location_country():
    from candidate_transformer.core.validate import validate_default_schema
    profile = {
        "candidate_id": "c1",
        "location": {"city": "Bangalore", "country": "india"}  # lowercase, should be 2 uppercase chars
    }
    errors = validate_default_schema(profile)
    assert any("country" in err for err in errors), f"expected country error, got: {errors}"
    print("PASS: validate_default_schema detects malformed location country")


def test_validation_detects_malformed_experience_date():
    from candidate_transformer.core.validate import validate_default_schema
    profile = {
        "candidate_id": "c1",
        "experience": [{
            "company": "X",
            "title": "Y",
            "start": "2022/01",  # wrong format, should be YYYY-MM
            "end": None,
            "summary": ""
        }]
    }
    errors = validate_default_schema(profile)
    assert any("start" in err for err in errors), f"expected start date error, got: {errors}"
    print("PASS: validate_default_schema detects malformed experience date format")


def test_pipeline_end_to_end():
    from candidate_transformer.pipeline import run_pipeline
    
    sources = {
        "recruiter_csv": "name,email,phone,current_company,title\nAlice Cooper,alice@cooper.com,9876543210,AliceCorp,Tech Lead",
        "ats_json": {
            "candidateName": "Alice Cooper",
            "contactEmail": "alice.work@cooper.com",
            "employer": "AliceCorp Ltd",
            "currentTitle": "Principal Tech Lead"
        },
        "github_profile": {
            "login": "alice-cooper",
            "name": "A. Cooper",
            "bio": "Tech lead. Python, Docker."
        },
        "github_repos": [
            {"language": "Python"},
            {"language": "Go"}
        ]
    }
    
    # 1. Test Default Schema end-to-end
    result = run_pipeline("cand_999", sources)
    
    assert result["candidate_id"] == "cand_999"
    assert result["full_name"] == "Alice Cooper"
    assert set(result["emails"]) == {"alice@cooper.com", "alice.work@cooper.com"}
    assert result["phones"] == ["+919876543210"]
    assert result["headline"] == "Tech lead. Python, Docker."
    
    skills = {s["name"] for s in result["skills"]}
    assert "Python" in skills
    assert "Go" in skills
    assert len(result["provenance"]) > 0
    assert "_validation_errors" not in result
    
    # 2. Test Custom Projection config end-to-end
    custom_config = {
        "fields": [
            { "path": "full_name", "type": "string", "required": True },
            { "path": "primary_email", "from": "emails[0]", "type": "string", "required": True },
            { "path": "first_skill", "from": "skills[0].name", "type": "string" }
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    projected = run_pipeline("cand_999", sources, custom_config)
    assert projected["full_name"] == "Alice Cooper"
    assert projected["primary_email"] in {"alice@cooper.com", "alice.work@cooper.com"}
    assert "first_skill" in projected
    assert "overall_confidence" in projected
    assert "_validation_errors" not in projected
    
    print("PASS: end-to-end pipeline run (default & custom projection)")


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


