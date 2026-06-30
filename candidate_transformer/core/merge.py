"""
Merge engine. This is the part of the assignment that actually requires
judgment, not just plumbing.

Policy (stated explicitly so it's auditable, not implicit in code):
  - Single-value fields (full_name, headline): the FieldValue with the
    highest confidence wins outright. Ties are broken by a fixed source-
    priority order (declared below), never silently/randomly — determinism
    matters more than getting the tiebreak "right" in some abstract sense.
  - Multi-value fields (emails, phones, skills): union, deduplicated. We do
    not throw away a second email just because one source had it first —
    a candidate having two emails is normal, not a conflict to resolve.
  - experience: deduplicated by (company, title). When two entries collide,
    the richer one (more non-null attributes) wins; the loser is still
    recorded in provenance so a human can see what was discarded and why.
  - overall_confidence is the mean of confidence scores for values that
    actually won a slot in the final profile — not an average across every
    candidate value, which would punish profiles with more conflicting
    sources even when the merge resolved them correctly.

We never invent a value. If no source supports a field, it stays null and
that absence is itself information, not a bug to paper over.
"""

from collections import defaultdict
from typing import List
from .schema import FieldValue, ProvenanceEntry, CanonicalProfile

SOURCE_PRIORITY = ["recruiter_csv", "ats_json", "linkedin", "resume", "github", "recruiter_notes"]


def _priority_index(source: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _pick_winner(candidates: List[FieldValue]) -> FieldValue:
    return sorted(candidates, key=lambda c: (-c.confidence, _priority_index(c.source.value)))[0]


def _merge_single_value(field_name: str, values: List[FieldValue], profile: CanonicalProfile):
    if not values:
        return
    winner = _pick_winner(values)
    setattr(profile, field_name, winner.value)
    profile.provenance.append(ProvenanceEntry(field_name, winner.source.value, winner.method, winner.confidence))
    for v in values:
        if v is not winner:
            profile.provenance.append(
                ProvenanceEntry(field_name, v.source.value, f"discarded:{v.method}", v.confidence)
            )


def _merge_multi_value_strings(field_name: str, values: List[FieldValue], profile: CanonicalProfile):
    seen = set()
    merged = []
    for v in sorted(values, key=lambda c: -c.confidence):
        if v.value in seen:
            continue
        seen.add(v.value)
        merged.append(v.value)
        profile.provenance.append(ProvenanceEntry(field_name, v.source.value, v.method, v.confidence))
    setattr(profile, field_name, merged)


def _merge_skills(values: List[FieldValue], profile: CanonicalProfile):
    skill_map = {}
    for v in sorted(values, key=lambda c: -c.confidence):
        name = v.value
        if name not in skill_map:
            skill_map[name] = {"name": name, "confidence": v.confidence, "sources": []}
        skill_map[name]["confidence"] = max(skill_map[name]["confidence"], v.confidence)
        skill_map[name]["sources"].append(v.source.value)
        profile.provenance.append(ProvenanceEntry("skills", v.source.value, v.method, v.confidence))
    profile.skills = list(skill_map.values())


def _merge_experience(values: List[FieldValue], profile: CanonicalProfile):
    by_key = {}
    for v in sorted(values, key=lambda c: -c.confidence):
        entry = v.value
        key = (entry.get("company", "").lower(), entry.get("title", "").lower())
        if key not in by_key:
            by_key[key] = entry
            profile.provenance.append(ProvenanceEntry("experience", v.source.value, v.method, v.confidence))
        else:
            existing_richness = sum(1 for x in by_key[key].values() if x)
            new_richness = sum(1 for x in entry.values() if x)
            if new_richness > existing_richness:
                by_key[key] = entry
            profile.provenance.append(
                ProvenanceEntry("experience", v.source.value, f"merged-duplicate:{v.method}", v.confidence)
            )
    profile.experience = list(by_key.values())


def _merge_links(values: List[FieldValue], profile: CanonicalProfile):
    links = {"other": []}
    for v in sorted(values, key=lambda c: -c.confidence):
        url = v.value
        if "github.com" in url and "github" not in links:
            links["github"] = url
        elif "linkedin.com" in url and "linkedin" not in links:
            links["linkedin"] = url
        elif url not in links.get("other", []):
            links["other"].append(url)
        profile.provenance.append(ProvenanceEntry("links", v.source.value, v.method, v.confidence))
    if not links["other"]:
        del links["other"]
    profile.links = links


def merge_sources(candidate_id: str, all_values: List[FieldValue]) -> CanonicalProfile:
    profile = CanonicalProfile(candidate_id=candidate_id)
    by_field = defaultdict(list)
    for v in all_values:
        by_field[v.field_name].append(v)

    if "full_name" in by_field:
        _merge_single_value("full_name", by_field["full_name"], profile)
    if "headline" in by_field:
        _merge_single_value("headline", by_field["headline"], profile)
    if "emails" in by_field:
        _merge_multi_value_strings("emails", by_field["emails"], profile)
    if "phones" in by_field:
        _merge_multi_value_strings("phones", by_field["phones"], profile)
    if "skills" in by_field:
        _merge_skills(by_field["skills"], profile)
    if "experience" in by_field:
        _merge_experience(by_field["experience"], profile)
    if "links" in by_field:
        _merge_links(by_field["links"], profile)

    won_confidences = [p.confidence for p in profile.provenance if not p.method.startswith(("discarded", "merged-duplicate"))]
    profile.overall_confidence = round(sum(won_confidences) / len(won_confidences), 3) if won_confidences else 0.0

    return profile
