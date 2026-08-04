# AGENTS.md — DzDoc Engine

This file is the governing instruction set for every coding agent working in this repository.

## 0. Repository context and decision memory

This section records the product context and decisions already approved by the owner. Agents must not repeatedly reopen these decisions unless new measured evidence shows that a change is necessary.

### 0.1 Why this project exists

DzDoc Engine began from the need for a serious document-intelligence system that works well on Algerian documents, where one page can contain:

- Arabic right-to-left text;
- French left-to-right text;
- Latin and Arabic-Indic numbers;
- administrative tables;
- stamps, seals, signatures, logos, and handwriting;
- low-quality scans and phone photographs;
- valid native PDF text;
- missing text layers;
- or text layers that exist but contain incorrect ordering or character mappings.

Generic OCR is not enough. The project must decide when native text can be trusted, when OCR is required, which recognizer should process each region, how uncertain results should be fused, and how the final document structure should be reconstructed and validated.

The intended product is an **Algerian Arabic–French document intelligence engine and platform**, not merely a wrapper around PaddleOCR, Tesseract, a PDF parser, or a visual-language model.

### 0.2 Owner’s product and career goal

The project serves two goals simultaneously:

1. Build a genuinely useful, technically excellent product that can be deployed as:
   - a hosted web application;
   - a public API;
   - a Python or TypeScript SDK;
   - a private on-premise installation;
   - or an OEM/white-label engine.

2. Create visible, attributable technical proof that MERATI Ali Ouala Eddine designed and led a substantial Arabic–French OCR and document-AI system.

The public repository must therefore remain understandable, benchmarked, well documented, and clearly attributable to the owner. Important architectural work must not disappear inside an anonymous private implementation.

### 0.3 Future BADIS AI objective

The long-term intention is to finish and independently validate DzDoc Engine, then potentially present it to BADIS AI as:

- a technical proposal;
- a pilot;
- a licensable engine;
- an integration;
- an OEM/white-label component;
- or the basis for a deeper collaboration.

BADIS AI is a future potential partner or adopter, not the current owner or sponsor.

Agents must preserve this future option by making the software:

- independent;
- professionally documented;
- easy to evaluate;
- easy to integrate;
- white-labelable;
- horizontally scalable;
- deployable on-premise;
- and free from hardcoded company-specific assumptions.

Do not insert BADIS AI names, logos, private context, internal architecture, or claims of affiliation into product code or public marketing unless explicit written authorization is later supplied.

### 0.4 Confirmed architecture decision

The approved architecture is a **hybrid deterministic-first cascade**:

```text
Document
  ↓
Secure ingestion and fingerprinting
  ↓
Native PDF inspection and text extraction
  ↓
Language-aware native-text quality gate
  ├─ trustworthy native content → preserve it
  └─ missing, incomplete, corrupt, suspicious, or uncertain
       ↓
     render only required pages
       ↓
     bounded preprocessing variants
       ↓
     text/layout detection once
       ↓
     region-level script and language routing
       ├─ Arabic recognizer
       ├─ French/Latin recognizer
       ├─ numeric/symbol handling where justified
       └─ multiple recognizers only for uncertain regions
       ↓
     candidate fusion and deterministic validation
       ↓
     Unicode-aware reading-order reconstruction
       ↓
     guarded VLM fallback for unresolved difficult regions/pages
       ↓
     canonical typed document representation
       ↓
     JSON, Markdown, text, searchable output, and document packs
```

The architecture is confirmed. Agents may improve an implementation detail after benchmarking, but must not replace the cascade with a simplistic “send every page to one large model” design without explicit evidence and owner approval.

### 0.5 Confirmed product decisions

The following decisions are approved:

- The project remains independently owned by MERATI Ali Ouala Eddine.
- Public project-owned code uses the PolyForm Noncommercial License 1.0.0 unless a file explicitly states otherwise.
- Commercial use requires a separate written licence.
- The project is accurately described as **source-available for non-commercial use**, not OSI-approved open source.
- The engine is model-agnostic.
- Native PDF extraction is attempted before visual OCR.
- Production architecture targets one text-detection pass per page.
- Recognition happens per detected region.
- Arabic and French recognizers both run only when routing is uncertain or mixed.
- A VLM is a fallback and structural assistant, not the default path.
- Canonical JSON is the source of truth; Markdown is only an export.
- Raw model output is never destroyed.
- Arabic text is never repaired through blind string reversal.
- CPU execution is the required baseline; GPU acceleration is optional.
- The same core engine must support CLI, API worker, local/offline, and on-premise use.
- The first high-value Algerian document pack is invoices and purchase documents.
- The final product must include a polished Arabic/French document review interface.
- The implementation is executed in five large phases with verification gates.
- DZ-Bench is developed in a separate independent repository named `dz-bench`.
- Algerian Baccalaureate exam papers are a major benchmark category, subject to source and redistribution verification.
- The initial serious deployment target is a provider-neutral European VPS using Docker Compose.
- Render Free may be used for a temporary UI or lightweight demonstration, but must not be treated as the production OCR compute platform.
- Production code must not become dependent on Render, OVH, Vercel, Supabase, or another single provider.

### 0.6 Business value and positioning

Raw OCR is increasingly commoditized. The product becomes valuable by delivering:

- correct Arabic–French mixed-script handling;
- reliable native-text versus OCR routing;
- coordinates and reading order;
- tables and forms;
- field-level confidence;
- alternatives and human-review signals;
- structured Algerian document extraction;
- privacy and on-premise deployment;
- API and SDK integration;
- measurable infrastructure savings;
- and evidence-backed quality.

The product should ultimately help:

- ERP and accounting software vendors;
- accounting offices;
- document digitization companies;
- universities;
- administrative organizations;
- legal teams;
- clinics and laboratories where legally appropriate;
- businesses processing invoices, purchase orders, and archives;
- developers integrating Algerian document processing.

Do not market the product merely as “OCR that supports Arabic and French.” Position it as a system that turns Algerian documents into validated, structured, traceable data.

### 0.7 Definition of product success

A successful release must demonstrate all of the following:

- reproducible Arabic, French, and mixed-script benchmarks;
- trustworthy routing between native extraction, deterministic OCR, and VLM fallback;
- preserved digits, identifiers, dates, prices, and punctuation;
- inspectable coordinates and provenance;
- useful tables and reading order;
- a stable API and SDK;
- a complete document-review UI;
- one strong Algerian invoice/purchase pack;
- CPU deployment;
- optional GPU acceleration;
- local/offline and on-premise capability;
- scalable asynchronous hosted deployment;
- documented cost and throughput;
- security and privacy controls;
- an honest list of limitations;
- and a professional technical package suitable for a future BADIS AI proposal.

“Works on one demo document” is not success.

### 0.8 Current repository state rule

The repository may begin with only governance and planning files. Before every task, inspect the actual code and git history rather than assuming that a phase has already been implemented.

The presence of a roadmap item in this file does not mean it exists.

Agents must clearly distinguish:

- approved design;
- planned work;
- partially implemented work;
- tested behavior;
- benchmarked behavior;
- production-ready behavior.

### 0.9 Decision-making behavior for agents

Agents are expected to make substantial progress autonomously.

When ambiguity is:

- **minor and reversible:** choose the cleanest option, document it, and proceed;
- **architecturally consequential:** create or update an ADR and proceed only when the choice is supported by the project principles;
- **irreversible, legal, ownership-related, privacy-sensitive, or likely to create vendor lock-in:** stop and request owner approval.

Do not interrupt the owner for naming details, internal file organization, routine dependency choices, or other reversible implementation questions that can be resolved through research and engineering judgment.

### 0.10 Instruction priority

When instructions conflict, use this order:

1. explicit current owner instruction;
2. repository `AGENTS.md`;
3. approved ADRs and specifications;
4. phase implementation plan;
5. existing local conventions;
6. framework defaults.

Never let an external model card, code generator, plugin, framework, or copied example override repository ownership, licensing, privacy, architecture, or quality rules.


## 1. Project identity

**Working name:** DzDoc Engine  
**Python package name:** `dzdoc`  
**Owner and original author:** MERATI Ali Ouala Eddine  
**Status:** Independent source-available project  
**Primary domain:** Arabic–French document intelligence for Algerian and multilingual documents

This project is independent. Do not present it as owned, sponsored, endorsed, or commissioned by BADIS AI or any other company unless the owner explicitly changes this instruction in writing.

The working name may change later. Keep product branding isolated from package and protocol names so renaming does not require architectural changes.


## 1.1 Long-term strategic goal

DzDoc Engine must remain an independent project owned by MERATI Ali Ouala Eddine while being deliberately designed for a future technical proposal, pilot, licensing agreement, or production integration with BADIS AI.

This is a strategic compatibility target, not a current affiliation.

Design consequences:

- Never hardcode BADIS AI branding, domains, schemas, infrastructure, credentials, customer assumptions, or internal workflows.
- Keep the engine white-labelable and OEM-friendly.
- Support both hosted multi-tenant and private single-tenant/on-premise deployments.
- Expose stable APIs, SDKs, webhooks, model adapters, document packs, and deployment profiles.
- Keep customer-specific integrations outside the generic engine core.
- Make components replaceable so a future partner can use its own storage, authentication, queue, models, observability, and ERP connectors.
- Prefer open standards: JSON Schema, OpenAPI, S3-compatible storage, PostgreSQL, OCI containers, OpenTelemetry, OAuth/OIDC, and signed webhooks.
- Produce reproducible benchmark and cost reports suitable for a technical due-diligence or partnership proposal.
- Preserve clear authorship, provenance, licence boundaries, and contribution history.
- Do not claim BADIS AI endorsement, use, sponsorship, or adoption without explicit written authorization.

The future proposal should be based on measured advantages: Arabic/French accuracy, Algerian-document performance, native-text OCR avoidance, latency, infrastructure cost, explainability, privacy, and ease of integration.

## 2. Mission

Build the best practical Arabic–French document intelligence engine for Algerian documents.

The engine must transform PDFs and document images into a canonical, inspectable document representation containing:

- text;
- coordinates;
- reading order;
- language and script;
- directionality;
- layout and block types;
- confidence and provenance;
- alternatives for uncertain recognition;
- structured fields when a document pack is applied.

The engine is not merely an OCR wrapper. Its value comes from intelligent routing, Arabic–French reconstruction, validation, explainability, benchmarking, and Algerian document specialization.

## 3. Non-negotiable principles

1. **Accuracy before feature count.**
   Never add a feature that makes evaluation less trustworthy.

2. **Benchmark before claims.**
   No accuracy, speed, memory, cost, or superiority claim may be written without reproducible evidence.

3. **Hybrid cascade, not one-model dependence.**
   Use deterministic and inexpensive stages first. Escalate only uncertain pages or regions to heavier models.

4. **Detect text once.**
   A page should normally have one text-detection pass. Route detected regions to one or more recognizers. Do not run two complete OCR pipelines merely because two languages are present, except in an explicitly marked baseline experiment.

5. **Model-agnostic boundaries.**
   Models are adapters behind stable interfaces. No upstream model may define the internal domain schema.

6. **Arabic correctness is structural, not cosmetic.**
   Never repair Arabic by blindly reversing strings. Mixed Arabic, French, Latin digits, Arabic-Indic digits, punctuation, and bidirectional runs must be handled at line or glyph-cluster level using Unicode-aware logic.

7. **Preserve evidence.**
   Keep raw model output, normalized output, coordinates, confidence, source adapter, preprocessing information, and alternatives.

8. **Privacy by default.**
   Do not upload user documents, samples, telemetry, or extracted text unless an explicit feature and consent mechanism are later approved.

9. **CPU-first baseline, optional acceleration.**
   The reference pipeline must work on a normal CPU. GPU, WebGPU, CUDA, and hosted inference are optional execution profiles.

10. **Small, testable modules.**
    Prefer focused files and explicit interfaces. Avoid god classes, hidden global state, and architecture controlled by framework conventions.

11. **No silent fallback.**
    If a stage fails, the result must record what failed, what fallback was used, and how confidence changed.

12. **No invented results.**
    Agents must never fabricate benchmark numbers, supported languages, model licences, paper results, or production readiness.

## 4. Licence and ownership rules

Project-owned source code is released under the **PolyForm Noncommercial License 1.0.0**, unless a file explicitly says otherwise.

Commercial use requires a separate written licence from:

**MERATI Ali Ouala Eddine**

Rules for agents:

- Keep the root `LICENSE.md` intact.
- Add the project copyright header only where the repository conventions require it.
- Never change the licence, owner, commercial terms, or required notice without explicit owner approval.
- Never describe this project as OSI-approved “open source.” It is source-available for non-commercial use.
- Do not copy code with an incompatible licence.
- Do not add GPL, AGPL, SSPL, Commons Clause, research-only, unknown, or custom-licensed code or dependencies without an explicit licence review.
- Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, and similarly permissive dependencies may be proposed, but they must still be recorded.
- Model code, model weights, datasets, fonts, and benchmarks each require separate licence verification.
- Prefer downloading model weights from their official source at install or runtime rather than committing them.
- Update `THIRD_PARTY_NOTICES.md` whenever a dependency, model, dataset, benchmark, or copied asset is added.
- Never commit customer documents, private documents, copyrighted benchmark files without redistribution rights, identity documents, or personal data.

## 5. Product scope

### 5.1 Core scope

The core engine must support:

- PDF and image ingestion;
- native PDF text inspection;
- page rendering;
- image preprocessing;
- layout and text detection;
- Arabic, French, and mixed-script recognition;
- script and language routing;
- confidence fusion;
- reading-order reconstruction;
- table, form, title, paragraph, list, image, stamp, signature, and unknown block types;
- canonical JSON output;
- Markdown and plain-text projections;
- reproducible evaluation;
- CLI usage;
- API integration through stable service interfaces.

### 5.2 Later scope

These are later modules, not foundation requirements:

- FastAPI service;
- TypeScript SDK;
- web application;
- authentication and billing;
- hosted asynchronous jobs;
- on-premise deployment packaging;
- searchable PDF generation;
- document-specific Algerian extraction packs;
- human-review interface;
- model training and fine-tuning.

### 5.3 Explicitly out of scope for the first milestone

- payments;
- user accounts;
- production cloud infrastructure;
- a complex dashboard;
- training a new foundation model;
- downloading multi-gigabyte models during unit tests;
- claiming production-grade accuracy;
- tightly coupling the engine to one OCR vendor.


### 5.4 Product experience and interface requirements

The final web application is part of the product, not a decorative wrapper.

It must include:

- upload and job creation;
- clear processing progress;
- long-document navigation;
- page rendering;
- OCR/layout overlays;
- block and field selection;
- source-to-result highlighting;
- editable OCR text with correction provenance;
- confidence and alternative display;
- low-confidence review queue;
- structured document results;
- exports;
- API keys and developer documentation;
- usage and job history;
- privacy, retention, and deletion controls;
- Arabic and French localization;
- correct RTL/LTR switching;
- responsive behavior;
- keyboard accessibility;
- loading, empty, failure, offline, and expiry states.

Visual direction:

- minimal;
- premium;
- serious;
- calm;
- technically credible;
- document-focused;
- excellent typography;
- no generic AI gradients or decorative clutter;
- no fake metrics;
- no inert controls;
- no excessive card grids;
- white-labelable without redesigning the interface.

For frontend creation, agents should use the installed design and browser-verification skills when available. Visual concept approval and implementation fidelity are mandatory for major UI work.


## 6. Hybrid reference architecture

The intended processing cascade is:

```text
Document input
  ↓
Safe ingestion and document fingerprinting
  ↓
PDF inspection / native-text extraction
  ↓
Native text quality gate
  ├─ reliable → preserve native text and layout evidence
  └─ absent, corrupt, suspicious, or incomplete
       ↓
     render only required pages
       ↓
     image preprocessing variants
       ↓
     layout and text detection once
       ↓
     region-level script/language routing
       ├─ Arabic recognizer
       ├─ Latin/French recognizer
       ├─ numeric/symbol recognizer when justified
       └─ multiple recognizers only for uncertain regions
       ↓
     candidate fusion and language-aware validation
       ↓
     reading-order and document reconstruction
       ↓
     deterministic document validators
       ↓
     lightweight VLM fallback for unresolved regions/pages only
       ↓
     canonical document representation
       ↓
     JSON / Markdown / text / document-pack outputs
```

The VLM is an escalation layer, not the default OCR path.

## 7. Required architectural boundaries

Implement stable protocols or abstract interfaces for the following capabilities:

- `DocumentLoader`
- `PdfInspector`
- `PageRenderer`
- `ImagePreprocessor`
- `LayoutDetector`
- `TextDetector`
- `ScriptClassifier`
- `TextRecognizer`
- `CandidateFusion`
- `ReadingOrderResolver`
- `DocumentValidator`
- `VlmFallback`
- `DocumentPack`
- `Exporter`
- `BenchmarkRunner`

Each adapter must declare:

- adapter name and version;
- upstream project and model;
- licence identifier;
- supported scripts/languages;
- supported execution providers;
- expected input format;
- output coordinate system;
- confidence semantics;
- required model assets;
- known limitations.

Core domain code must not import PaddleOCR, ONNX Runtime, Transformers, OpenCV, PDFium, or another heavy vendor library directly. Vendor imports belong in adapters.

## 8. Canonical document model

The canonical model is the source of truth. Markdown is only a projection.

At minimum, model these concepts:

- `Document`
- `Page`
- `Block`
- `TextLine`
- `TextSpan`
- `Table`
- `TableCell`
- `BoundingBox`
- `Polygon`
- `LanguageTag`
- `ScriptTag`
- `TextDirection`
- `Confidence`
- `Provenance`
- `RecognitionCandidate`
- `ProcessingWarning`
- `ProcessingError`
- `DocumentField`
- `ValidationResult`

Every recognized textual unit should be able to preserve:

```text
raw_text
normalized_text
search_text
language
script
direction
bbox or polygon
page_index
reading_order_index
confidence
source_adapter
source_model
preprocessing_variant
alternatives
warnings
```

Coordinates must use one documented canonical coordinate system. Adapters are responsible for conversion.

Schemas must be versioned. A future internal refactor must not silently break API consumers.

## 9. Arabic, French, and bidirectional text requirements

### 9.1 Preserve three forms

- `raw_text`: unchanged source or model output;
- `normalized_text`: conservative display-safe normalization;
- `search_text`: optional aggressive normalization for matching and retrieval.

Never overwrite raw evidence.

### 9.2 Display normalization

Default display normalization should be conservative:

- prefer NFC;
- preserve Arabic letters, diacritics, digits, punctuation, and meaningful joining characters unless a verified repair requires otherwise;
- strip or transform bidi control characters only through a documented operation;
- record every repair as provenance or a warning.

### 9.3 Search normalization

Search normalization may optionally:

- remove tatweel;
- remove selected diacritics;
- fold selected Arabic orthographic variants;
- normalize Arabic-Indic and Latin digits;
- lowercase French;
- normalize apostrophes and whitespace.

It must never replace display text.

### 9.4 Reading order

- Resolve direction at block and line level.
- Preserve LTR runs such as French terms, identifiers, URLs, dates, decimal values, and digit sequences inside RTL lines.
- Preserve Arabic-Indic digit order.
- Use Unicode bidirectional concepts rather than naive character reversal.
- Tests must cover mixed lines such as Arabic labels with French values and vice versa.

### 9.5 Language routing

Routing is evidence-based, using some combination of:

- Unicode script proportions;
- recognizer confidence;
- lightweight script classifier;
- lexicon plausibility;
- character error signals;
- number/date/identifier validity;
- document context;
- neighboring regions.

Do not force every region into exactly one language. `mixed`, `unknown`, and alternatives are valid outcomes.

## 10. Native PDF text policy

Native text is cheaper and may be more accurate than OCR, but it is not automatically trustworthy.

The quality gate should inspect:

- text presence and coverage;
- replacement and control character ratios;
- font and `ToUnicode` signals when available;
- script consistency;
- line order plausibility;
- Arabic/French lexical plausibility;
- repeated or phantom text;
- suspicious glyph substitutions;
- page-image versus text-layer agreement when escalation is justified.

For early milestones, Arabic native text must be treated cautiously. If order or encoding confidence is insufficient, route the affected page or region to OCR.

Never reject a text layer solely because Arabic presentation forms are present. Normalize and evaluate them correctly.

## 11. Candidate fusion

Candidate fusion must be independently testable.

A recognition candidate may be scored using:

- recognizer confidence;
- script consistency;
- language plausibility;
- layout consistency;
- expected character class;
- number/date/checksum validity;
- agreement with other recognizers;
- document-pack expectations;
- corruption penalties.

Do not hide the scoring formula inside an adapter.

When top candidates are close:

- preserve alternatives;
- reduce confidence;
- emit a review warning;
- do not pretend certainty.

Thresholds must live in typed configuration, not scattered magic numbers.

## 12. VLM fallback policy

A visual-language model may run only when a deterministic trigger fires, such as:

- unresolved low-confidence page;
- difficult table;
- complex form;
- handwriting;
- unusual orientation;
- text overlapping stamps;
- severe degradation;
- reading-order conflict;
- deterministic validators disagreeing.

Requirements:

- VLM output is untrusted input and must be schema-validated.
- Keep the prompt, model version, decoding parameters, and output provenance.
- Never allow a VLM to silently overwrite high-confidence deterministic output.
- Prefer region-level fallback over full-document fallback.
- Make VLM use optional and disable it in the default unit-test profile.
- Do not add a new VLM because it is popular; add it through a benchmarked adapter.

## 13. Initial technology choices

Unless an approved architecture decision changes them:

- Python 3.12+
- `uv` for environment and dependency management
- `pydantic` v2 for versioned schemas
- `numpy`
- `Pillow`
- `opencv-python-headless` only in adapters/preprocessing
- `onnxruntime` or `onnxruntime-gpu` through adapters
- `pytest`
- `hypothesis` where property-based testing is valuable
- `ruff` for linting and formatting
- `mypy` or `pyright` for strict type checking
- `typer` for the CLI
- `structlog` or standard structured logging
- `orjson` only if benchmarks justify it
- FastAPI later, outside the engine core

Prefer pure functions in routing, validation, normalization, and scoring code.

Do not introduce Kubernetes, Kafka, Celery, Redis, a vector database, or microservices in the core repository without measured need.

## 14. Expected repository structure

```text
.
├── AGENTS.md
├── README.md
├── LICENSE.md
├── COMMERCIAL-LICENSE.md
├── THIRD_PARTY_NOTICES.md
├── CONTRIBUTING.md
├── SECURITY.md
├── pyproject.toml
├── uv.lock
├── Makefile
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── research/
│   └── benchmarks/
├── src/
│   └── dzdoc/
│       ├── core/
│       ├── ingestion/
│       ├── routing/
│       ├── preprocessing/
│       ├── layout/
│       ├── recognition/
│       ├── validation/
│       ├── reconstruction/
│       ├── exporters/
│       ├── document_packs/
│       └── adapters/
├── apps/
│   ├── cli/
│   └── api/
├── sdk/
│   ├── python/
│   └── typescript/
├── benchmarks/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── fixtures/
└── scripts/
```

Do not create empty architecture theatre. A directory should exist only when it contains an implemented boundary, an imminent milestone, or required documentation.


## 14.1 Multi-repository boundary

DzDoc is intentionally split into two independent repositories.

### Repository A — `dzdoc-engine`

This repository owns the OCR/document-intelligence product: model adapters, routing, fusion, canonical document output, API, SDKs, workers, deployment, UI, and commercial/on-premise integrations.

### Repository B — `dz-bench`

This repository owns independent evaluation: dataset manifests, synthetic fixtures, Algerian Baccalaureate exam evaluation, annotation tooling, metrics, reports, and leaderboards. It must be capable of evaluating DzDoc and competing systems without importing private DzDoc internals.

### Integration contract

The repositories communicate only through versioned public artifacts:

- benchmark manifest JSON Schema;
- ground-truth JSON Schema;
- prediction JSON Schema;
- report JSON Schema;
- dataset revision identifiers;
- model/system metadata;
- file checksums;
- CLI or HTTP evaluation contracts.

Recommended flow:

```text
dz-bench exports an evaluation bundle
        ↓
dzdoc-engine processes it and writes predictions
        ↓
dz-bench scores those predictions and produces reports
```

Do not vendor the full benchmark corpus into `dzdoc-engine`. Do not make `dz-bench` depend on private engine modules. Dataset and document licences remain separate from benchmark-code licensing.

### Algerian Baccalaureate exams

Algerian BAC exam papers are a major real-document benchmark family because they combine Arabic, French and other Latin-script languages, mathematics, physics/chemistry notation, tables, diagrams, numbered exercises, headers, page structure, and variable scan quality.

BAC coverage belongs in `dz-bench`, not in the engine repository. Unless redistribution permission is explicit, store only source metadata, canonical URLs, checksums, downloader instructions, and locally generated ground truth. Default to reference-only treatment when rights are unclear.


## 15. Engineering workflow for agents

For every task:

1. Read this file and the relevant architecture decision records.
2. Inspect the current repository before proposing changes.
3. State the task scope and assumptions.
4. Identify licences and model/data implications.
5. Write or update tests first for behavior changes.
6. Implement the smallest coherent change.
7. Run formatting, linting, type checking, and relevant tests.
8. Run only the smallest meaningful benchmark needed.
9. Update documentation and third-party notices when applicable.
10. Report exact files changed, commands run, and remaining limitations.

Do not:

- make unrelated refactors;
- rewrite stable modules without evidence;
- conceal failing tests;
- weaken tests to make implementation pass;
- disable type checking broadly;
- add `# type: ignore` without a precise reason;
- add global mutable model sessions to core domain code;
- publish packages, push branches, create releases, upload artifacts, or change repository visibility unless explicitly instructed;
- commit secrets, access tokens, private documents, or model credentials.

When a decision is uncertain, choose a reversible default and record it in an ADR rather than embedding an undocumented assumption.


## 15.1 Installed skill and plugin usage

When relevant skills are installed in the working environment, agents should use them rather than improvising weaker workflows.

Recommended process skills:

- `superpowers:using-git-worktrees` for isolated feature execution;
- `superpowers:writing-plans` for large phases;
- `superpowers:test-driven-development` for behavior changes;
- `superpowers:subagent-driven-development` for parallel independent tasks;
- `superpowers:requesting-code-review` before phase completion;
- `superpowers:verification-before-completion` before any success claim.

Recommended research and repository tools:

- GitHub connector and CLI for upstream source, releases, issues, licences, and repository work;
- Context7 for current official library documentation;
- Hugging Face tools for model cards, datasets, revisions, and model assets.

Recommended frontend skills:

- `build-web-apps:frontend-app-builder`;
- `build-web-apps:frontend-testing-debugging`;
- `build-web-apps:react-best-practices`;
- `build-web-apps:shadcn`;
- browser verification tools such as `vercel:agent-browser-verify`.

Recommended data and infrastructure skills:

- `supabase:supabase-postgres-best-practices` for standard PostgreSQL design review;
- security review skills for ingestion, APIs, tenancy, and deployment.

Skill usage does not relax project requirements. Generated work must still be reviewed, tested, benchmarked, and verified.


## 16. Test strategy

### 16.1 Test layers

- **Unit tests:** normalization, routing, geometry, fusion, validation, schemas.
- **Contract tests:** every adapter against its interface.
- **Integration tests:** small local models or mocked sessions.
- **Regression tests:** every discovered Arabic/French/layout bug receives a permanent fixture.
- **Benchmark tests:** accuracy, latency, memory, and routing decisions.
- **Security tests:** malformed PDFs/images, path traversal, decompression bombs, oversized pages, and invalid model output.

### 16.2 Fixture rules

- Prefer generated, synthetic, public-domain, permissively licensed, or explicitly authorized fixtures.
- Redact real documents before use and verify redistribution rights.
- Never store real identity numbers, addresses, signatures, account details, medical details, or customer information.
- Keep large benchmark assets outside the Git repository with a reproducible manifest and checksums.
- Unit tests must not access the internet.
- Unit tests must not download model weights.
- Heavy tests must be opt-in and clearly marked.

### 16.3 Essential regression cases

At minimum, preserve tests for:

- Arabic-only lines;
- French-only lines;
- separate Arabic and French regions;
- Arabic and French in one line;
- Latin digits inside Arabic;
- Arabic-Indic digits;
- decimal and thousands separators;
- dates and identifiers;
- diacritics and tatweel;
- Arabic ligatures;
- right-to-left tables;
- mixed-direction tables;
- rotated pages;
- low-resolution scans;
- shadows, blur, skew, and compression;
- stamps crossing text;
- native PDFs with good text layers;
- native PDFs with broken ordering;
- native PDFs with plausible but incorrect character mappings.

## 17. Benchmarking rules

The project benchmark suite may be called **DZ-Bench** as a working name.

Measure:

- character error rate;
- word error rate;
- normalized edit distance;
- reading-order accuracy;
- block detection precision/recall/F1;
- table structure accuracy;
- script-routing accuracy;
- native-text acceptance false-positive rate;
- native-text rejection false-positive rate;
- field extraction exact match and normalized match;
- latency per page;
- peak memory;
- pages per minute;
- percentage of pages avoiding OCR;
- percentage of regions escalated to multiple recognizers;
- percentage escalated to VLM;
- estimated cost per 1,000 pages for each deployment profile.

Benchmark reports must include:

- hardware;
- operating system;
- model and dependency versions;
- execution provider;
- dataset revision;
- page count and category distribution;
- warm-up policy;
- concurrency;
- exact command;
- confidence intervals or repeated-run variability where useful.

Never optimize only for the aggregate score. Report Arabic, French, mixed, tables, forms, degraded scans, and native PDFs separately.

## 18. Security and privacy

Treat every document as hostile and sensitive.

Required safeguards:

- validate MIME type and file signature;
- limit file size, page count, dimensions, and render resolution;
- limit processing time and memory;
- isolate temporary files;
- use randomized temporary paths;
- remove temporary files after processing;
- prevent path traversal;
- avoid shell interpolation;
- disable outbound network access in the local processing profile;
- never log document text by default;
- redact identifiers in error reports;
- record hashes rather than document contents where possible;
- document every optional telemetry event before adding telemetry.

API work must later include rate limits, authentication, signed job identifiers, upload expiry, and explicit retention rules.


## 18.1 Scalability and production integration requirements

The engine core must remain usable in-process, but production interfaces must support scaling without redesigning recognition logic.

Required production characteristics:

- stateless API nodes;
- asynchronous, idempotent jobs;
- content-addressed document and page artifacts;
- page-level and region-level work units;
- bounded retries and explicit dead-letter states;
- separate CPU and GPU worker capabilities;
- model sessions loaded once per worker and reused safely;
- configurable batching and concurrency;
- backpressure and per-tenant quotas;
- S3-compatible object storage;
- PostgreSQL-compatible metadata storage;
- optional Redis-compatible queue or cache behind an interface;
- signed uploads and short-lived downloads;
- webhooks with signatures, retry policy, and idempotency keys;
- OpenTelemetry traces, metrics, and structured logs;
- local Docker Compose profile;
- production OCI images;
- future Kubernetes/Helm support only after the containerized service is stable;
- offline/on-premise mode with no required outbound network access after assets are installed;
- model asset manifests with exact versions, checksums, licences, and reproducible download commands.

Do not put database, queue, HTTP, tenancy, or cloud-provider concerns into recognition and reconstruction modules. The same engine must run in CLI tests, local desktop experiments, API workers, and future partner infrastructure.


## 18.2 Initial deployment strategy

The initial production-capable deployment should be simple and inexpensive:

```text
Caddy or equivalent edge proxy
├── web application
├── FastAPI API
├── CPU OCR worker
├── PostgreSQL
├── Redis/Valkey-compatible queue
└── S3-compatible object storage or local object storage abstraction
```

Preferred initial characteristics:

- one European VPS with sufficient RAM for the web/API stack and one CPU worker;
- Docker Compose;
- persistent volumes;
- HTTPS;
- backups;
- explicit document retention;
- no required Kubernetes;
- no permanently running GPU.

Scale-out path:

```text
stateless API nodes
  ↓
shared PostgreSQL + object storage + queue
  ↓
independent CPU worker pool
  ↓
GPU/VLM workers only for escalated tasks
```

Render Free and similar free sleeping services are acceptable only for a temporary frontend, documentation site, or lightweight demonstration. The OCR engine, model loading, PDF rendering, and background processing require predictable CPU, memory, storage, and job execution.

Deployment code must remain portable. Provider-specific configuration belongs in optional deployment adapters or documentation.


## 19. Logging and observability

Use structured events.

Every processing run should be traceable through:

- document fingerprint;
- pipeline version;
- configuration profile;
- adapter/model versions;
- page and region timings;
- routing decisions;
- warnings;
- fallbacks;
- confidence changes;
- final status.

Do not log raw OCR text or images by default.

## 20. Configuration

Configuration must be typed, validated, and serializable.

Use explicit profiles such as:

- `cpu-minimal`
- `cpu-quality`
- `gpu-throughput`
- `offline-private`
- `benchmark`
- `test-fake`

Configuration should control:

- model adapters;
- thresholds;
- render DPI;
- preprocessing variants;
- batching;
- execution provider;
- fallback policy;
- languages;
- timeouts;
- memory limits.

Environment variables may select configuration but should not contain undocumented behavior.

## 21. Documentation requirements

Keep these documents current:

- `README.md`: truthful user-facing overview and quick start;
- `docs/architecture/system.md`: current architecture;
- `docs/decisions/`: ADRs for consequential choices;
- `docs/research/model-registry.md`: candidate models, licences, evidence, and status;
- `docs/benchmarks/`: reproducible results;
- `THIRD_PARTY_NOTICES.md`: external software, models, and datasets;
- `SECURITY.md`: disclosure and secure processing policy.

Separate:

- **measured fact**
- **research claim**
- **design hypothesis**
- **planned feature**

Do not present a planned feature as implemented.

## 22. Model registry requirements

Every candidate model needs an entry containing:

- identifier;
- upstream repository or paper;
- model card;
- licence;
- parameter count and asset size;
- languages/scripts;
- task;
- runtime;
- supported providers;
- expected memory;
- benchmark evidence;
- known failure modes;
- approval state: `research`, `experimental`, `supported`, or `rejected`.

No model becomes the default until it beats or complements the current baseline on relevant DZ-Bench categories.

## 23. Document packs

Document packs are optional layers over the generic engine.

A pack may define:

- document classifier;
- expected fields;
- field aliases in Arabic and French;
- spatial hints;
- validators;
- normalization;
- confidence rules;
- output schema;
- evaluation fixtures.

A document pack must never inject its assumptions into the generic OCR core.

Potential future packs include:

- Algerian invoices;
- purchase orders;
- university transcripts;
- diplomas;
- administrative forms;
- employment files;
- legal documents.

Identity and medical document packs require additional privacy and legal review.

## 24. Five-phase delivery roadmap

The implementation is organized into five large, reviewable phases. A capable agent may use subagents and parallel work inside a phase, but the next phase must not begin until the current phase has fresh verification evidence.

### Phase 1 — Engine foundation, secure ingestion, native PDF intelligence, and benchmark integration

Deliver:

- repository and Python package foundation;
- canonical schemas and adapter contracts;
- fake end-to-end pipeline;
- CLI and exporters;
- CI, linting, strict typing, tests, and security fixtures;
- architecture and licensing documentation;
- integration with the independent `dz-bench` repository through versioned schemas and CLI contracts;
- secure PDF/image ingestion;
- page rendering boundaries;
- multiple native PDF extraction candidates;
- language-aware native-text quality gate;
- per-page routing to OCR;
- no production OCR or VLM weights yet.

Exit condition:

The architecture is coherent, tested, licence-aware, reproducible, and compatible with the independent `dz-bench` evaluation contract.

### Phase 2 — Complete deterministic Arabic–French OCR engine

Deliver:

- researched model registry;
- reproducible model asset management;
- image preprocessing and geometry tracking;
- one text-detection pass per page;
- Arabic recognition;
- French/Latin recognition;
- script routing;
- selective dual recognition;
- candidate fusion;
- Unicode-aware bidi reconstruction;
- layout, tables, forms, and reading order;
- canonical JSON and user-facing exports;
- real-model DZ-Bench results;
- CPU baseline and optional GPU provider.

Exit condition:

A real PDF or image can be processed end-to-end by the deterministic engine with inspectable results, reproducible weights, tests, and measured quality.

### Phase 3 — Advanced document intelligence, guarded VLM fallback, and invoice pack

Deliver:

- current VLM research tournament;
- licence and reproducibility review;
- measured VLM selection or explicit rejection;
- deterministic escalation triggers;
- region-level guarded fallback;
- schema validation and hallucination controls;
- `invoice-dz` pack;
- field-level confidence and evidence;
- arithmetic, identifier, date, tax, and total validators;
- JSON, CSV, and Excel outputs;
- comparative benchmarks.

Exit condition:

Difficult documents improve measurably without making the VLM the default, and one Algerian document pack provides commercially useful structured extraction.

### Phase 4 — Scalable API, workers, storage, SDKs, security, and deployment

Deliver:

- FastAPI;
- PostgreSQL and migrations;
- queue abstraction;
- object storage abstraction;
- asynchronous idempotent jobs;
- CPU/GPU worker separation;
- page fan-out and aggregation;
- API keys and tenant boundaries;
- signed uploads and webhooks;
- retention and deletion;
- metrics, tracing, logs, and usage;
- Python and TypeScript SDKs;
- Docker Compose;
- CPU, GPU, hosted, and on-premise profiles;
- load, security, recovery, and deployment tests.

Exit condition:

The engine works as a real API and can scale from one VPS to independent worker pools without changing core recognition logic.

### Phase 5 — Complete product UI, release campaign, and BADIS-ready proposal

Deliver:

- approved visual system;
- complete Arabic/French web product;
- upload, processing, review, correction, field extraction, export, usage, API, and administration experiences;
- correct RTL/LTR and accessibility;
- authentication through a replaceable boundary;
- white-label configuration;
- full-system quality campaign;
- release candidate;
- benchmark, cost, architecture, privacy, security, and deployment documentation;
- demo;
- professional future BADIS AI proposal and pilot package.

Exit condition:

A verified, deployable, presentable product exists with honest limitations, reproducible evidence, and clear independent ownership.

## 25. Definition of done

A task is done only when:

- behavior is implemented;
- relevant tests pass;
- public interfaces are typed;
- errors are explicit;
- licence impact was checked;
- documentation is updated;
- no unsupported claim was introduced;
- verification commands and results are reported;
- limitations are stated honestly.

“Code written” is not “done.”

## 26. Phase execution boundary

Agents must work only on the phase explicitly requested by the owner or the active phase plan.

Within an active phase, agents may implement substantial related work and use subagents. They must not silently begin the next phase.

Before proceeding to the next phase, provide:

- exact commits;
- changed-file summary;
- test and benchmark commands;
- fresh output and exit status;
- licence and notice updates;
- security findings;
- measured limitations;
- recommended next step.

The first agent in a new repository must begin with **Phase 1**.
