# System Architecture and Design

This document explains the architecture and engineering decisions for the Multi-Source Candidate Data Transformer.
It covers system structure, merge policies, confidence scoring, projection design, data flow, and practical trade-offs.

## Main Idea and Objective

Objective: transform noisy, conflicting, and partially missing candidate data from multiple source types into one canonical and explainable profile.

The architecture is designed to guarantee:

1. Deterministic output for identical inputs.
2. Clear provenance for every selected value.
3. Runtime-configurable output shape without touching merge logic.
4. Graceful handling of malformed or missing sources.

## Design Principles

1. Separation of concerns.
2. Deterministic conflict resolution.
3. Defensive parsing and robustness.
4. Auditable transformations over opaque heuristics.
5. Canonical-first design, projection-second design.

## Architecture Overview

```mermaid
graph LR
    S1[Recruiter CSV] --> EX[Extractors]
    S2[ATS JSON] --> EX
    S3[GitHub Profile and Repos] --> EX

    EX --> N[Normalization Utilities]
    N --> FV[FieldValue Stream]
    FV --> MG[Merge Engine]
    MG --> CP[Canonical Profile]
    CP --> PR[Projection Layer]
    CFG[Runtime Config] --> PR
    PR --> VL[Validation]
    VL --> OUT[Output JSON]

    classDef source fill:#e0f2fe,stroke:#0369a1,stroke-width:1px;
    classDef process fill:#dcfce7,stroke:#166534,stroke-width:1px;
    classDef data fill:#fff7ed,stroke:#9a3412,stroke-width:1px;

    class S1,S2,S3,CFG source;
    class EX,N,MG,PR,VL process;
    class FV,CP,OUT data;
```

## Canonical Output Schema

The internal canonical profile is the source of truth and remains stable across output formats.

| Field | Type | Notes |
|---|---|---|
| candidate_id | string | required identifier |
| full_name | string or null | single-value winner field |
| emails | string[] | normalized lowercase |
| phones | string[] | E.164 format |
| location | object or null | city, region, country |
| links | object | linkedin, github, portfolio, other[] |
| headline | string or null | profile summary text |
| years_experience | number or null | optional |
| skills | object[] | name, confidence, sources[] |
| experience | object[] | company, title, start, end, summary |
| education | object[] | institution, degree, field, end_year |
| provenance | object[] | field, source, method, confidence |
| overall_confidence | number | aggregate score in [0,1] |

## Normalization Standards

1. Phone: E.164 format.
2. Email: lowercase and regex-validated.
3. Dates: normalized to YYYY-MM where possible.
4. Skills: alias-to-canonical mapping.
5. Text: unicode normalization and whitespace cleanup.

## Merge and Conflict-Resolution Policy

### Single-value fields

Policy:

1. Highest confidence wins.
2. If confidence ties, apply fixed source-priority order.
3. Non-winning values remain visible in provenance as discarded decisions.

### Multi-value fields

Policy:

1. Union values across sources.
2. Deduplicate normalized values.
3. Keep provenance for each retained value.

### Skills

Policy:

1. Group by canonical skill name.
2. Keep max confidence among contributors.
3. Record contributing sources list.

### Experience

Policy:

1. Deduplicate by company plus title key.
2. If collision occurs, select richer record based on non-null attributes.
3. Record duplicate merges in provenance.

### Merge decision visualization

```mermaid
flowchart TD
    IN[Field candidates] --> K{Field kind}
    K -->|Single| S1[Choose max confidence]
    S1 --> T{Tie?}
    T -->|Yes| S2[Apply static source priority]
    T -->|No| SW[Winner]
    S2 --> SW

    K -->|Multi| M1[Union normalized values]
    K -->|Skills| SK1[Aggregate by canonical name]
    K -->|Experience| E1[Deduplicate by company plus title]
    E1 --> E2[Pick richer entry]

    SW --> P[Write provenance]
    M1 --> P
    SK1 --> P
    E2 --> P
    P --> OUT[Canonical profile updated]
```

## Confidence Model

Confidence is assigned per field-source pair using base priors and method-specific discounts.

Example strategy:

1. Directly declared values use base field-source prior.
2. Inferred values are discounted.
3. Aggregate overall confidence is computed from accepted decisions only.

### Confidence pipeline

```mermaid
flowchart LR
    B[Base prior by field and source] --> M[Method adjustment]
    M --> F[Final field confidence]
    F --> A[Accepted by merge]
    A --> O[Overall confidence aggregation]
```

## Runtime Custom-Output Config Design

The projection layer supports dynamic schema reshaping at runtime through config controls:

1. Select a subset of output fields.
2. Map output field from canonical path with from.
3. Apply per-field normalization.
4. Include or exclude confidence and provenance.
5. Configure missing-value behavior as null, omit, or error.

Why this architecture is important:

1. Canonical integrity remains untouched by presentation changes.
2. New client payloads can be supported by config, not merge rewrites.
3. Validation can be applied per projected schema contract.

```mermaid
graph TD
    C[Canonical profile] --> P[Projection engine]
    G[Config: fields, from, normalize, on_missing] --> P
    P --> R[Reshaped output]
    R --> V[Custom projection validation]
```

## Workflow and Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as pipeline.py
    participant OR as run_pipeline
    participant EX as extractors
    participant MG as merge_sources
    participant PJ as project or default project
    participant VL as validators

    User->>CLI: Execute command with file paths
    CLI->>OR: Build source payloads
    OR->>EX: Extract fields defensively
    EX-->>OR: FieldValue list
    OR->>MG: Merge and score
    MG-->>OR: Canonical profile
    OR->>PJ: Apply projection
    PJ-->>OR: Output payload
    OR->>VL: Validate payload
    VL-->>OR: Error list or empty
    OR-->>CLI: Final result with optional validation metadata
```

## Problem-Solving Approach

1. Isolate extraction from decision logic.
2. Normalize before merge to avoid false conflicts.
3. Encode merge policies explicitly and deterministically.
4. Treat unknown values as null rather than fabricating data.
5. Keep configuration-driven output transformation separate from canonical model.

## Key Components and Integration Details

1. Extractors integrate each source by mapping external fields into FieldValue records.
2. Merge engine integrates all FieldValue records into one canonical profile.
3. Projector integrates runtime config with canonical paths.
4. Validators integrate schema checks before final output.

## Advantages, Benefits, Pros, and Cons

### Advantages

1. Deterministic and explainable output.
2. Strong auditability through provenance.
3. Clear separation between data truth and output shape.
4. Low operational complexity due to zero external dependencies.

### Limitations

1. Rule-based normalization can miss complex natural-language cases.
2. Confidence priors are heuristic and need empirical tuning at scale.
3. In-memory processing is suitable for assignment scale but not distributed-scale ingest.

## Edge Cases and Handling Strategy

1. Missing source file: skip source, continue processing.
2. Malformed source payload: catch extraction exception, continue processing.
3. Conflicting values with equal confidence: resolve by source priority.
4. Ambiguous date text: return null, do not invent.
5. Required projected field missing with on_missing=error: raise explicit projection error.

## Future Evolution

1. Add resume and LinkedIn extractors.
2. Replace heuristic phone parsing with robust regional parsing library.
3. Introduce external skill taxonomy for higher canonicalization quality.
4. Add batch processing mode for large candidate sets.
