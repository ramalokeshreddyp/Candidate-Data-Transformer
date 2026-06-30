# 📄 Complete Project Documentation

This document serves as the technical reference manual for the **Multi-Source Candidate Data Transformer**. It provides details on module structure, field-by-field workflows, integration procedures, and codebase execution.

---

## 🎯 Project Objective

In candidate recruitment platforms, candidate profile data comes from multiple sources: resume parsing engines, online profiles (e.g., GitHub, LinkedIn), and manual entry via Applicant Tracking Systems (ATS) or recruiter spreadsheets. 

This project resolves the conflicts arising from inconsistent schemas, stale information, spelling variations, and differing formatting standards. It ingests disparate datasets and outputs a clean, consolidated profile with a clear, auditable trail explaining the origin and trustworthiness of every single field.

---

## 📦 System Modules & Codebase Breakdown

The project follows a modular, package-oriented architecture under the `candidate_transformer` package:

### 1. Root CLI Entrypoint
* **[pipeline.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/pipeline.py)**: A lightweight wrapper script that imports and executes the pipeline's CLI.
  ```python
  from candidate_transformer.pipeline import main
  if __name__ == "__main__":
      main()
  ```

### 2. Orchestration Package Module
* **[candidate_transformer/pipeline.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/pipeline.py)**: The actual orchestrator logic. Handles parsing command line arguments, wrapping extraction steps in defensive checks, and running merging, projection, and validation in sequence.
  * `run_pipeline(candidate_id, sources, custom_config)`: Runs extraction, merging, optional projection, and validation.
  * `main()`: Resolves files on disk from CLI args and writes results to stdout/file.

### 3. Core Merging & Projection Engine
* **[candidate_transformer/core/schema.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/schema.py)**: Defines all data transfer objects (DTOs) and configuration priors.
  * `SourceType(Enum)`: Restricts supported source types.
  * `ProvenanceEntry(dataclass)`: Model tracking the history of a single field.
  * `FieldValue(dataclass)`: Wraps an extracted data point before merge.
  * `CanonicalProfile(dataclass)`: Post-merge unified candidate record.
  * `FIELD_SOURCE_PRIORS`: Dict storing standard confidence values for fields per source.
* **[candidate_transformer/core/merge.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/merge.py)**: Reconciles all extracted `FieldValue` records into a single `CanonicalProfile`.
  * `merge_sources(candidate_id, all_values)`: Coordinates the merge logic field-by-field.
  * `_pick_winner(candidates)`: Uses confidence priors and source priority to break ties.
  * `_merge_skills(values, profile)`: Unions skills, retaining max confidence and verifying sources.
  * `_merge_experience(values, profile)`: Merges job experiences, deduplicating by company and title (wins based on details richness).
* **[candidate_transformer/core/project.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/project.py)**: Dynamic projection engine. Evaluates dotted/bracketed paths (e.g., `emails[0]`, `skills[].name`) against the merged record and applies post-processing.
* **[candidate_transformer/core/validate.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/validate.py)**: Run before output to check data types, E.164 phone correctness, and validation rules.

### 4. Extraction Module Package
* **[candidate_transformer/extractors/](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/)**: Subpackage containing parsers that translate raw data into `FieldValue` structures.
  * **[csv_extractor.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/csv_extractor.py)**: Standard recruiter CSV parser.
  * **[ats_extractor.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/ats_extractor.py)**: Translates ATS JSON fields into canonical paths.
  * **[github_extractor.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/github_extractor.py)**: Parses GitHub profiles and infers skills from repo languages.
  * **[__init__.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/__init__.py)**: Exposes the three extractors as a public subpackage interface.

### 5. Utility Helper Engine
* **[candidate_transformer/utils/normalize.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/utils/normalize.py)**: Text cleanup, email regex checks, skill canonicalization alias maps, and date normalizers.

---

## 🔄 Detailed Data Flow & Decision Tree

The diagram below details the exact lifecycle of a field value, from raw file extraction to the final consolidated profile entry.

```mermaid
graph TD
    A[Start Source Extraction] --> B[Parse Raw Record]
    B --> C{Field Present?}
    C -->|No| D[Ignore Field]
    C -->|Yes| E[Apply Normalizer - utils/normalize.py]
    E --> F{Valid Normalized Format?}
    F -->|No| G[Degrade Value to Null]
    F -->|Yes| H[Instantiate FieldValue]
    H --> I[Assign confidence from priors / discounts]
    I --> J[Emit FieldValue list]
    J --> K[Merge Engine - core/merge.py]
    K --> L{Field Type?}
    L -->|Single-Value| M{Higher Confidence Wins?}
    M -->|Yes| N[Assign to Canonical Profile]
    M -->|No/Tie| O[Tie-breaker: Source priority order]
    O --> N
    L -->|Multi-Value| P[Union and de-duplicate lists]
    P --> N
    L -->|Experience| Q[Deduplicate on company + title]
    Q --> R{Which record has more non-null fields?}
    R -->|Rich Record| S[Keep Rich Record]
    R -->|Lean Record| T[Discard / Log in Provenance]
    S --> N
    N --> U[Write Winner to Profile & Log Discarded to Provenance]
```

---

## ⚖️ Evaluation: Pros, Cons, & Trade-offs

Here is a transparent breakdown of the current implementation's engineering design trade-offs:

### Advantages & Pros
* **Highly Modular**: Splitting extractors, core merging, utility cleaners, and CLI runners into package folders prevents tight coupling and makes scaling clean.
* **Traceable**: Detailed provenance logging (`provenance` key) lets upstream applications see exactly *why* a particular piece of candidate info won.
* **Zero Dependencies**: Uses only standard Python libraries, making it run in milliseconds with zero setup overhead and a minimal memory footprint.

### Disadvantages & Cons
* **Basic Text Processing**: The normalization patterns rely on simple regex checks. In a production system, complex global phone parsing would require a library like Google's `libphonenumber`, and skill matching would benefit from a vector database or semantic taxonomy.
* **Simplified Date Parsing**: The date normalize method handles standard formats like `Jan 2022` or `2022` but would struggle with complex natural-language strings (e.g., "three years ago", "Present").
* **Single-Node Execution**: The current design merges data in memory. Scaling this to process millions of candidates simultaneously would require porting the merge rules to distributed engines (e.g., Apache Spark or dbt/SQL pipelines).

---

## 🛠️ Developer Integration Guide: Adding a New Data Source

To extend the system and add a new input source (e.g., a LinkedIn PDF profile or a Resume Parser output):

### Step 1: Register the Source Type
Add your new source identifier to the `SourceType` enum in **[schema.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/schema.py)**:
```python
class SourceType(str, Enum):
    # ... existing sources
    LINKEDIN_PDF = "linkedin_pdf"
```

### Step 2: Define Base Confidence Priors
In **[schema.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/core/schema.py)**, add appropriate confidence values for your fields in the `FIELD_SOURCE_PRIORS` dictionary:
```python
FIELD_SOURCE_PRIORS = {
    "full_name":        {"recruiter_csv": 0.85, "linkedin_pdf": 0.90, ...},
    "emails":           {"recruiter_csv": 0.90, "linkedin_pdf": 0.80, ...},
    # ...
}
```

### Step 3: Implement the Extractor
Create a new extractor parser module file under **[candidate_transformer/extractors/](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/)**, e.g., `linkedin_extractor.py`. The parser must accept raw input and return `FieldValue` items:
```python
from typing import List
from ..core.schema import FieldValue, SourceType, base_confidence
from ..utils.normalize import normalize_email, clean_text

def extract_linkedin_pdf(pdf_parsed_dict: dict) -> List[FieldValue]:
    out = []
    name = clean_text(pdf_parsed_dict.get("name", ""))
    email = normalize_email(pdf_parsed_dict.get("email", ""))
    
    if name:
        out.append(FieldValue(
            field_name="full_name",
            value=name,
            source=SourceType.LINKEDIN_PDF,
            method="direct",
            confidence=base_confidence("full_name", "linkedin_pdf")
        ))
    if email:
        out.append(FieldValue(
            field_name="emails",
            value=email,
            source=SourceType.LINKEDIN_PDF,
            method="direct",
            confidence=base_confidence("emails", "linkedin_pdf")
        ))
    return out
```

### Step 4: Expose and Wire the Extractor
Expose your new extractor function in **[candidate_transformer/extractors/__init__.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/extractors/__init__.py)**:
```python
from .linkedin_extractor import extract_linkedin_pdf
```
Then, update `run_pipeline` in **[candidate_transformer/pipeline.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/candidate_transformer/pipeline.py)** to include your new extractor within a protective try-except block:
```python
    try:
        if sources.get("linkedin_pdf"):
            all_values.extend(extract_linkedin_pdf(sources["linkedin_pdf"]))
    except Exception as e:
        print(f"[warn] linkedin_pdf extraction failed, skipping: {e}")
```

### Step 5: Add a Unit Test
Add a test function in **[tests/test_pipeline.py](file:///c:/Users/lokes/Desktop/eightfold-transformer/tests/test_pipeline.py)** to verify that your parser, confidence priors, and merge rules work as intended.
