# Codebase Structure

**Analysis Date:** 2026-04-03

## Directory Layout

```
Ml_Project/
├── .git/                                    # Git repository
├── .opencode/                               # OpenCode GSD tooling (auto-generated)
│   ├── command/                             # Slash command definitions
│   ├── get-shit-done/                       # GSD templates, workflows, references
│   └── package.json                         # Node.js metadata for GSD
├── .planning/                               # Project planning artifacts (GSD-managed)
│   └── codebase/                            # Codebase analysis documents
├── combined_dataset.csv                     # Primary dataset (~1.58M rows)
├── Idea.md                                  # Data architecture implementation plan
├── lecture and labs.txt                     # Course reference URLs (Chameleon, MLOps labs)
├── MLOps_-_Project-Presentation-Team-ChatSentry.txt   # Presentation slides content
└── MLOps-Project-Report-TeamChatSentry.txt            # Project report document
```

## Directory Purposes

**Root (`Ml_Project/`):**
- Purpose: Project root — contains planning documents, dataset, and reference materials
- Contains: Markdown docs, CSV dataset, text-based presentation/report artifacts
- Key files: `Idea.md`, `combined_dataset.csv`
- Subdirectories: `.opencode/`, `.planning/`, `.git/`

**`.planning/` (GSD-managed):**
- Purpose: Project planning state managed by the GSD workflow
- Contains: Phase plans, roadmaps, codebase analysis documents
- Key files: `codebase/ARCHITECTURE.md`, `codebase/STRUCTURE.md`
- Subdirectories: `codebase/` (codebase analysis documents)
- Generated: Yes (by GSD commands)
- Committed: Yes

**`.opencode/` (GSD tooling):**
- Purpose: OpenCode GSD installation — command definitions, templates, workflows
- Contains: Slash commands, planning templates, skill definitions
- Key files: `get-shit-done/templates/`, `command/gsd-*.md`
- Subdirectories: `command/`, `get-shit-done/`
- Generated: Yes (by GSD installer)
- Committed: Yes (source of truth for GSD)

## Key File Locations

**Dataset:**
- `combined_dataset.csv` — Merged dataset with columns: `text`, `is_suicide`, `is_toxicity` (~1.58M rows)
- Source: Jigsaw toxic comment classification (27.62 MB, 200k rows) + suicide/depression detection (166.9 MB, 230k rows)

**Design Documents:**
- `Idea.md` — Data architecture plan for Rishabh Narayan (Data specialist): MinIO setup, ingestion pipeline, online processing, batch pipeline
- `MLOps-Project-Report-TeamChatSentry.txt` — Full project report: system design, team roles, data flow, deployment architecture
- `MLOps_-_Project-Presentation-Team-ChatSentry.txt` — Presentation content: dataset description, model details, serving targets, decision matrix

**Reference:**
- `lecture and labs.txt` — Course lab URLs for Chameleon Cloud, MLOps, data platforms, LLM training, model serving

**Configuration:** Not applicable — no application code or build configuration exists yet

**Source Code:** Not applicable — no source code exists. The project is in the planning/design phase.

**Testing:** Not applicable — no tests exist yet

## Naming Conventions

**Files (Current):**
- `UPPERCASE-kebab-case.txt` — Project report/presentation artifacts
- `lowercase_snake_case.csv` — Dataset files
- `PascalCase.md` — Planning documents (e.g., `Idea.md`)

**Planned (from Idea.md references):**
- `lowercase_snake_case.py` — Python scripts (e.g., `ingest_and_expand.py`, `online_processor.py`, `compile_training_data.py`, `synthetic_traffic_generator.py`)
- `data_design_document.md` — Design documentation

**Directories (Planned, not yet created):**
- `src/` — Source code root
- `src/data/` — Data processing scripts
- `src/serving/` — FastAPI application
- `src/training/` — Model training code
- `infra/` — Infrastructure-as-code scripts
- `tests/` — Test files

## Where to Add New Code

**Project is pre-implementation. The following reflects the planned structure from `Idea.md` and the project report:**

**Data Pipeline Scripts:**
- Ingestion: `src/data/ingest_and_expand.py`
- Online processor: `src/data/online_processor.py`
- Batch pipeline: `src/data/compile_training_data.py`
- Traffic generator: `src/data/synthetic_traffic_generator.py`

**Serving Application:**
- FastAPI app: `src/serving/main.py`
- Inference logic: `src/serving/inference.py`
- Decision routing: `src/serving/router.py`

**Training:**
- Fine-tuning script: `src/training/fine_tune.py`
- Evaluation: `src/training/evaluate.py`

**Infrastructure:**
- Chameleon provisioning: `infra/provision.py` (using python-chi)
- Docker configs: `infra/docker/`
- CI/CD pipeline: `infra/ci-cd/`

**Tests (when created):**
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Load tests: `tests/load/`

**Documentation:**
- Design docs: root directory or `docs/`

## Special Directories

**`.opencode/`:**
- Purpose: GSD tooling installation
- Source: Installed by GSD package
- Committed: Yes
- Do not modify manually — managed by GSD commands

**`.planning/`:**
- Purpose: Project planning state
- Source: Generated by GSD commands (`/gsd-plan-phase`, `/gsd-execute-phase`, etc.)
- Committed: Yes
- Managed by GSD — manual edits may be overwritten

---

*Structure analysis: 2026-04-03*
*Project is in pre-implementation phase — no source code structure exists yet*
*Planned directories reflect design in Idea.md and project report*
