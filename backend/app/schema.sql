-- Bid Co-Author POC schema.
-- Mirrors the "Holds" panel of the approved workflow diagram: normalised register per tender,
-- questions/flags, elements/limits/weightings, this tender's scoring bands, and full run history.

CREATE TABLE IF NOT EXISTS tenders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_name    TEXT NOT NULL,
    contract_reference  TEXT,
    purchasing_authority TEXT,
    procedure_type      TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Uploaded tender documents. Kept on disk (see app/data/); this row is just enough to find the
-- file again when Decomposition needs to re-parse it for table/weight extraction.
CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id         INTEGER NOT NULL REFERENCES tenders(id),
    file_path         TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    uploaded_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id     INTEGER NOT NULL REFERENCES tenders(id),
    title         TEXT NOT NULL,
    question_text TEXT NOT NULL,
    category      TEXT NOT NULL CHECK (category IN ('sq', 'pass_fail', 'scored')),
    source_ref    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- kind: preamble | constraint | word_limit | diagram_limit | weight | theme
-- extraction_method: rule | llm  -- which layer produced this candidate (see Decomposition agent)
CREATE TABLE IF NOT EXISTS elements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id       INTEGER NOT NULL REFERENCES questions(id),
    kind              TEXT NOT NULL CHECK (
                          kind IN ('preamble', 'constraint', 'word_limit', 'diagram_limit', 'weight', 'theme')
                      ),
    value_text        TEXT NOT NULL,
    source_quote      TEXT,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN ('rule', 'llm')),
    locked            INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- This tender's own scoring matrix. band_value in {0,25,50,75,100}; descriptor_text is used
-- verbatim in Scoring Agent prompts, never paraphrased by the model.
CREATE TABLE IF NOT EXISTS scoring_bands (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id      INTEGER NOT NULL REFERENCES tenders(id),
    band_value     INTEGER NOT NULL CHECK (band_value IN (0, 25, 50, 75, 100)),
    descriptor_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id    INTEGER NOT NULL REFERENCES questions(id),
    version_number INTEGER NOT NULL,
    content_text   TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- status: addressed | asserted_only | missing | unverified
-- verified: 1 if the quote passed the deterministic substring check, 0 if it was downgraded
CREATE TABLE IF NOT EXISTS completeness_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id    INTEGER NOT NULL REFERENCES drafts(id),
    element_id  INTEGER NOT NULL REFERENCES elements(id),
    status      TEXT NOT NULL CHECK (status IN ('addressed', 'asserted_only', 'missing', 'unverified')),
    quote       TEXT,
    rationale   TEXT,
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- pass_number: '1' | '2' | '3' | 'moderator'
CREATE TABLE IF NOT EXISTS scoring_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id    INTEGER NOT NULL REFERENCES drafts(id),
    pass_number TEXT NOT NULL,
    band_value  INTEGER NOT NULL CHECK (band_value IN (0, 25, 50, 75, 100)),
    rationale   TEXT,
    temperature REAL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- confidence: high | low -- computed from inter-pass agreement, never self-reported by the model
CREATE TABLE IF NOT EXISTS scoring_summary (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id     INTEGER NOT NULL REFERENCES drafts(id),
    final_band   INTEGER NOT NULL CHECK (final_band IN (0, 25, 50, 75, 100)),
    confidence   TEXT NOT NULL CHECK (confidence IN ('high', 'low')),
    used_moderator INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The audit trail: every LLM call, from every agent, logged through the single llm_client gateway.
CREATE TABLE IF NOT EXISTS llm_call_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    agent               TEXT NOT NULL,
    prompt_file         TEXT NOT NULL,
    prompt_version_hash TEXT NOT NULL,
    model_deployment    TEXT NOT NULL,
    tokens_in           INTEGER,
    tokens_out          INTEGER,
    latency_ms          INTEGER,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- check_type: word_count | diagram_count | cross_reference | pass_fail_section
-- cross_reference and pass_fail_section are best-effort heuristics, not exhaustive validation —
-- see app/agents/deterministic_checks.py.
CREATE TABLE IF NOT EXISTS deterministic_check_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id   INTEGER NOT NULL REFERENCES drafts(id),
    check_type TEXT NOT NULL CHECK (check_type IN ('word_count', 'diagram_count', 'cross_reference', 'pass_fail_section')),
    passed     INTEGER NOT NULL,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Versioned clarification responses. Resolving one into the locked register is a human action
-- (re-run the idempotent /decompose) — this table stores and surfaces them, it does not attempt
-- automated conflict resolution against existing elements.
CREATE TABLE IF NOT EXISTS clarifications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id      INTEGER NOT NULL REFERENCES tenders(id),
    question_id    INTEGER REFERENCES questions(id),
    content_text   TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Generic per-tender configuration, e.g. rule_key='scoring_confidence_spread_steps'. Read by
-- routers at call time; agent functions keep their own hardcoded defaults so they still work
-- with no rules configured.
CREATE TABLE IF NOT EXISTS business_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id   INTEGER NOT NULL REFERENCES tenders(id),
    rule_key    TEXT NOT NULL,
    rule_value  TEXT NOT NULL,
    description TEXT,
    UNIQUE (tender_id, rule_key)
);

-- Evaluation methodology extracted from "Strategy and Context" uploads. Not every such document
-- discusses methodology — a document with nothing relevant simply gets no row here, matching the
-- no-fabrication standard used everywhere else (see app/agents/methodology.py).
CREATE TABLE IF NOT EXISTS evaluation_methodology (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id      INTEGER NOT NULL REFERENCES tenders(id),
    source_document TEXT NOT NULL,
    content_text   TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Relational record of what's in the Chroma vector store, for provenance queries that don't
-- need to go through the vector DB. source_document is a human-readable label (filename), not a
-- foreign key — evidence can be uploaded before or independently of a `documents` row.
-- category is purely a UI grouping label (the Data Ingestion screen's six categories) — it does
-- not affect retrieval, which still queries across all of a tender's evidence.
CREATE TABLE IF NOT EXISTS evidence_chunks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id       INTEGER NOT NULL REFERENCES tenders(id),
    source_document TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'general',
    chunk_text      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recommendation agent output. Capped at 3 rows per draft by the agent itself, ranked.
CREATE TABLE IF NOT EXISTS recommendations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id         INTEGER NOT NULL REFERENCES drafts(id),
    rank             INTEGER NOT NULL,
    element_id       INTEGER REFERENCES elements(id),
    fix_summary      TEXT NOT NULL,
    evidence_pointer TEXT,
    word_budget      INTEGER,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Benchmark (offline): historical, already-scored answers used to validate the Completeness and
-- Scoring agents before trusting them live. No new agent logic — these run through the existing
-- agents unchanged.
CREATE TABLE IF NOT EXISTS benchmark_cases (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tender_id            INTEGER NOT NULL REFERENCES tenders(id),
    question_id          INTEGER NOT NULL REFERENCES questions(id),
    historical_draft_text TEXT NOT NULL,
    known_band           INTEGER NOT NULL CHECK (known_band IN (0, 25, 50, 75, 100)),
    outcome_notes        TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Theme Review agent output (see app/agents/theme_review.py) — the seven-prompt expert critique
-- from the Bid Response Review Skills toolkit. List/object fields are JSON-encoded text; a POC
-- with a handful of short lists per row doesn't need child tables for this.
CREATE TABLE IF NOT EXISTS theme_reviews (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id                 INTEGER NOT NULL REFERENCES drafts(id),
    theme                    TEXT NOT NULL,
    theme_fit                TEXT NOT NULL,
    evaluator_summary        TEXT NOT NULL,
    strengths                TEXT NOT NULL,  -- JSON array of strings
    gaps                     TEXT NOT NULL,  -- JSON array of strings
    prioritised_improvements TEXT NOT NULL,  -- JSON array of {priority, description}
    suggested_wording        TEXT NOT NULL,  -- JSON array of strings
    evidence_required        TEXT NOT NULL,  -- JSON array of strings
    improved_answer_plan     TEXT NOT NULL,
    score_compliance         INTEGER NOT NULL,
    score_practicality       INTEGER NOT NULL,
    score_evidence           INTEGER NOT NULL,
    score_client_specificity INTEGER NOT NULL,
    score_evaluator_confidence INTEGER NOT NULL,
    created_at                TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS benchmark_results (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    benchmark_case_id  INTEGER NOT NULL REFERENCES benchmark_cases(id),
    predicted_band     INTEGER NOT NULL CHECK (predicted_band IN (0, 25, 50, 75, 100)),
    predicted_confidence TEXT NOT NULL CHECK (predicted_confidence IN ('high', 'low')),
    band_delta         INTEGER NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
