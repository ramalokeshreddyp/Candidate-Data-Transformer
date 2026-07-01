# Multi-Source Candidate Data Transformer

[![Python](https://img.shields.io/badge/Python-3.9%2B-1f6feb?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-0f766e?style=for-the-badge)](https://docs.python.org/3/)
[![Tests](https://img.shields.io/badge/Tests-13%2F13%20Passing-15803d?style=for-the-badge)](tests/test_pipeline.py)
[![Design](https://img.shields.io/badge/Design-Deterministic%20and%20Explainable-7c3aed?style=for-the-badge)](architecture.md)

An end-to-end candidate profile transformation engine built for the Eightfold assignment.
The pipeline ingests conflicting multi-source candidate data, normalizes it, resolves conflicts deterministically, records provenance per decision, computes confidence, and returns one trustworthy profile.

## Project Overview

Recruiting systems receive incomplete and conflicting candidate information from multiple channels. This project solves that by enforcing a strict internal canonical record and a runtime output projection layer.

Core outcomes:

1. Deterministic merge decisions for conflicting values.
2. Transparent provenance for every selected field.
3. Confidence scoring per field-source pair.
4. Config-driven output reshaping without code changes.
5. Graceful degradation when a source is missing or malformed.

## Visual System Snapshot

```mermaid
flowchart LR
    A[Structured Sources\nRecruiter CSV / ATS JSON] --> E[Extractor Layer]
    B[Unstructured Sources\nGitHub Profile + Repos] --> E
    E --> N[Normalization]
    N --> M[Deterministic Merge Engine]
    M --> C[Canonical Profile]
    C --> P[Projection Layer\nCustom Config Optional]
    P --> V[Validation]
    V --> O[Final JSON Output]

    classDef source fill:#dbeafe,stroke:#1d4ed8,stroke-width:1px;
    classDef logic fill:#dcfce7,stroke:#166534,stroke-width:1px;
    classDef data fill:#fef3c7,stroke:#92400e,stroke-width:1px;

    class A,B source;
    class E,N,M,P,V logic;
    class C,O data;
```

## Tech Stack

| Area | Choice | Why This Choice |
|---|---|---|
| Language | Python 3.9+ | Fast iteration, excellent stdlib support |
| Dependencies | Python standard library only | No install friction, deterministic behavior, easy audit |
| CLI | argparse | Lightweight, built-in, clear execution surface |
| Data parsing | csv, json, io | Reliable parsing for required source formats |
| Modeling | dataclasses, enum | Typed and explicit canonical/internal data model |
| Validation and normalization | re, unicodedata | Predictable formatting and schema checks |
| Tests | built-in test module style | Zero extra framework overhead |

## Workflow Explanation

The runtime workflow follows a strict sequence:

1. Read candidate inputs from CLI arguments.
2. Extract candidate field values from each source.
3. Normalize values into canonical formats.
4. Merge with deterministic conflict policies.
5. Build a canonical profile as source of truth.
6. Apply optional runtime projection config.
7. Validate output shape and field constraints.
8. Emit JSON to stdout or file.

### Execution Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as pipeline.py
    participant Orchestrator as candidate_transformer/pipeline.py
    participant Extractors as extractor modules
    participant Merge as core/merge.py
    participant Project as core/project.py
    participant Validate as core/validate.py

    User->>CLI: Run command with source paths
    CLI->>Orchestrator: run_pipeline(candidate_id, sources, config)
    Orchestrator->>Extractors: Parse available sources
    Extractors-->>Orchestrator: List[FieldValue]
    Orchestrator->>Merge: merge_sources(candidate_id, values)
    Merge-->>Orchestrator: CanonicalProfile
    alt Custom config present
        Orchestrator->>Project: project(canonical_dict, config)
        Project-->>Orchestrator: Projected output
        Orchestrator->>Validate: validate_custom_projection(...)
    else Default output
        Orchestrator->>Project: project_default_schema(canonical_dict)
        Project-->>Orchestrator: Default output
        Orchestrator->>Validate: validate_default_schema(...)
    end
    Validate-->>Orchestrator: Validation errors or none
    Orchestrator-->>CLI: JSON result
    CLI-->>User: Print or write output file
```

### Merge Decision Flow

```mermaid
flowchart TD
    S[Incoming FieldValue list] --> G{Field category}
    G -->|Single value| SV[Pick highest confidence]
    SV --> T{Tie?}
    T -->|Yes| P[Apply static source priority]
    T -->|No| W[Winner selected]
    P --> W

    G -->|Multi value| MV[Union and deduplicate normalized values]
    G -->|Skills| SK[Group by skill name, keep max confidence]
    G -->|Experience| EX[Deduplicate by company plus title and keep richer entry]

    W --> PR[Write provenance]
    MV --> PR
    SK --> PR
    EX --> PR
    PR --> CP[Canonical profile]
```

## Code Structure and Folder Organization

```text
eightfold-transformer/
|-- README.md
|-- architecture.md
|-- projectdocumentation.md
|-- pipeline.py
|-- candidate_transformer/
|   |-- __init__.py
|   |-- pipeline.py
|   |-- core/
|   |   |-- __init__.py
|   |   |-- schema.py
|   |   |-- merge.py
|   |   |-- project.py
|   |   |-- validate.py
|   |-- extractors/
|   |   |-- __init__.py
|   |   |-- csv_extractor.py
|   |   |-- ats_extractor.py
|   |   |-- github_extractor.py
|   |-- utils/
|       |-- __init__.py
|       |-- normalize.py
|-- sample_inputs/
|   |-- recruiter.csv
|   |-- ats.json
|   |-- github_profile.json
|   |-- github_repos.json
|   |-- custom_config.json
|   |-- output_default.json
|   |-- output_custom_config.json
|-- tests/
    |-- __init__.py
    |-- test_pipeline.py
```

## Setup and Installation

### Prerequisites

1. Python 3.9 or newer.
2. Access to the repository directory.

### Local Setup

```bash
git clone <your-repo-url>
cd eightfold-transformer
python --version
```

No package installation is required because the project uses only standard library modules.

## Run Locally

### Default canonical output

```bash
python pipeline.py \
  --candidate-id cand_001 \
  --recruiter-csv sample_inputs/recruiter.csv \
  --ats-json sample_inputs/ats.json \
  --github-profile sample_inputs/github_profile.json \
  --github-repos sample_inputs/github_repos.json
```

### Custom output projection

```bash
python pipeline.py \
  --candidate-id cand_001 \
  --recruiter-csv sample_inputs/recruiter.csv \
  --ats-json sample_inputs/ats.json \
  --github-profile sample_inputs/github_profile.json \
  --github-repos sample_inputs/github_repos.json \
  --config sample_inputs/custom_config.json
```

### Write output to file

```bash
python pipeline.py \
  --candidate-id cand_001 \
  --recruiter-csv sample_inputs/recruiter.csv \
  --ats-json sample_inputs/ats.json \
  --github-profile sample_inputs/github_profile.json \
  --github-repos sample_inputs/github_repos.json \
  --out sample_inputs/output_default.json
```

## Usage Instructions

CLI arguments:

- --candidate-id: Required identifier for the resulting profile.
- --recruiter-csv: Path to recruiter CSV source.
- --ats-json: Path to ATS JSON source.
- --github-profile: Path to GitHub profile JSON source.
- --github-repos: Path to GitHub repositories JSON source.
- --config: Optional custom projection config.
- --out: Optional output JSON file path.

Minimum source coverage in this implementation:

1. Structured: Recruiter CSV and ATS JSON.
2. Unstructured: GitHub profile plus repositories.

## Validation and Testing

Run test suite:

```bash
python -m tests.test_pipeline
```

Current status:

1. 13 of 13 tests passing.
2. Includes end-to-end tests for default schema and custom projection.
3. Includes regression tests for E.164 config token handling and fixed links shape.

## Documentation Map

- architecture.md: high-level architecture, merge policy, confidence model, and trade-offs.
- projectdocumentation.md: module-level implementation details, integration contracts, and execution internals.

## Assignment Artifacts

1. One-page design PDF for Step 1.
2. Runnable codebase for Step 2.
3. Sample outputs in sample_inputs/output_default.json and sample_inputs/output_custom_config.json.
4. Automated tests in tests/test_pipeline.py.
