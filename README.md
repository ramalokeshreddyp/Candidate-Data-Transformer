# Multi-Source Candidate Data Transformer

Built for the Eightfold Engineering Intern (Jul–Dec 2026) assignment.

## What this is

A pipeline that takes candidate data from multiple inconsistent sources
(recruiter CSV exports, ATS JSON blobs, GitHub profiles) and produces one
clean, canonical candidate profile — with every value traceable to where it
came from and how confident the pipeline is in it.

## Why it's built this way (short version — full reasoning in `design.md`)

The hard part of this problem isn't parsing CSV or calling an API. It's
deciding **who wins when two sources disagree**, and doing that decision
consistently and explainably rather than arbitrarily. I designed around one
rule: confidence is computed **per field, per source** (a recruiter CSV is
great for phone numbers, mediocre for skills; GitHub is the opposite), not
as a single trust score per source. That single decision shapes the whole
merge engine.

## Project structure

```
schema.py       - canonical profile shape, FieldValue, confidence priors
normalize.py    - phone/email/date/skill normalization (stdlib only)
extractors.py   - one function per source type, each emits FieldValue list
merge.py        - conflict resolution + confidence aggregation
project.py      - runtime-configurable output projection
validate.py     - schema validation, run before returning output
pipeline.py     - orchestration + CLI entry point
test_pipeline.py - 8 tests covering the decisions that actually mattered
sample_inputs/  - sample CSV/JSON inputs and a custom config, used below
```

## How to run it

No dependencies beyond the Python standard library.

```bash
python3 --version   # tested on 3.11, should work on 3.9+
```

### Default schema output

```bash
python3 pipeline.py \
  --candidate-id cand_001 \
  --recruiter-csv sample_inputs/recruiter.csv \
  --ats-json sample_inputs/ats.json \
  --github-profile sample_inputs/github_profile.json \
  --github-repos sample_inputs/github_repos.json
```

### Custom output config (the "required twist")

```bash
python3 pipeline.py \
  --candidate-id cand_001 \
  --recruiter-csv sample_inputs/recruiter.csv \
  --ats-json sample_inputs/ats.json \
  --github-profile sample_inputs/github_profile.json \
  --github-repos sample_inputs/github_repos.json \
  --config sample_inputs/custom_config.json
```

Same engine, same merge result underneath — only the projection step
changes shape, field names, and normalization per the config.

### Running tests

```bash
python3 test_pipeline.py
```

## What's covered

- **Structured source**: recruiter CSV (`extract_recruiter_csv`)
- **Structured source**: ATS JSON with mismatched field names (`extract_ats_json`)
- **Unstructured source**: GitHub profile + repos via REST API shape (`extract_github_profile`)

LinkedIn, resume PDF/DOCX parsing, and recruiter notes are sketched in
`design.md` but not implemented — see "What I deliberately left out" there.
The assignment requires at least one source from each group; I implemented
one structured (in fact two) and one unstructured, and prioritized making
the merge/projection engine correct over adding a fourth source type.

## Known limitations (stated honestly, not hidden)

- Country-code defaulting in phone normalization assumes India if no `+`
  prefix is present — acceptable for this exercise's scope, would need a
  real phone-number library for production.
- `years_experience` and `location` fields are defined in the schema but
  have no extractor populating them yet, since neither sample source
  reliably supplies them — they correctly come out `null` rather than guessed.
- Skill canonicalization uses a small curated alias map, not a full taxonomy.
