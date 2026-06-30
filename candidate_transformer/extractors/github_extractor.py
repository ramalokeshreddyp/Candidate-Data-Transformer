from typing import List
from ..core.schema import FieldValue, SourceType, base_confidence
from ..utils.normalize import canonicalize_skill, clean_text


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
