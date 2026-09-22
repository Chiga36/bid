# Bid Co-Author (POC)

Covers the whole workflow diagram: all eight agents/stages — **Ingestion**, **Decomposition**,
**Completeness**, **Scoring**, **Deterministic checks**, the **decision gate**,
**Recommendation**, and **Theme Review** (the seven-prompt expert critique from the Bid Response
Review Skills toolkit, selected automatically by each question's own Decomposition-classified
theme) — plus **evaluation-methodology extraction**, **clarification responses**, **business
rules**, the offline **Benchmark** harness, and a React frontend (`frontend/`) covering the five
reference screens. No Docker anywhere — both halves are plain Python/Node projects so the whole
folder can be copied to another machine and run with a fresh virtual environment and
`npm install`.

Built and tested against **Python 3.12/3.13** and **Node 22**. Document extraction is
deliberately not Docling or any other local ML/OCR pipeline — `app/document_extraction.py` does
plain, deterministic text extraction (`python-docx`/`openpyxl`/`pypdf`, no model weights, no
network calls), and all real document *understanding* (identifying questions, evaluation
methodology, etc.) happens via the configured Azure OpenAI deployment instead. This is a
deliberate choice, not an oversight — see `app/document_extraction.py`'s docstring.

## Frontend

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

(On Windows PowerShell/cmd, use `copy .env.example .env` instead of `cp`.)

Opens on `http://127.0.0.1:5173`. Needs the backend running on `127.0.0.1:5000` (see Setup/Run
below — start the backend first) — CORS is already configured for this origin in `app/main.py`.
Two honesty notes, both explained in the plan file: the "Co-author Coach" panel on Response
Builder exposes the *real* agents (Decompose, Lock, Deterministic checks, Completeness, Score,
Recommendation, Gate, Expert theme review) rather than the reference mockup's original button
labels, which didn't all correspond to something the backend does; and Agent Skills is read-only (it shows the live
content of `app/prompts/*.txt`), since prompts aren't DB-backed or editable via the API in this
build. On Data Ingestion, every one of the six upload categories is optional — nothing blocks
"Execute" on an empty category.

## What's here / what isn't

Built: tender + document upload (plain-text extraction + a real LLM-powered Ingestion agent that
identifies questions, replacing an earlier heading-heuristic stub), Decomposition (rule-based
limits/weights + verbatim-only LLM extraction, informed by extracted evaluation methodology),
the human verification gate (lock endpoint), Deterministic checks (word/diagram-count,
best-effort cross-reference and pass/fail checks — no LLM), Completeness (closed-book,
per-element, quote-verified, scoped to real content requirements only), Scoring (three-pass
ensemble + computed confidence + conditional moderator, with a per-tender confidence threshold
overridable via business rules), the "top band, no findings" decision gate, versioned
clarification responses, a per-tender business-rules table, evidence ingestion + evaluation
methodology extraction + Recommendation (ChromaDB similarity search, capped at 3 ranked
evidence-pointer fixes, informed by evaluation methodology), the offline Benchmark harness (runs
a historical case through the same Completeness/Scoring path and compares the predicted band to
the known one), and Theme Review — the seven-prompt expert critique from the Bid Response Review
Skills toolkit (`strengths`/`gaps`/`Critical`-`High`-`Medium`-`Low` prioritised improvements/
suggested wording/evidence required/improved answer plan/five 1-5 scores), automatically selected
by whichever of the seven themes Decomposition already classified the question against. Every LLM
call, from every agent, is logged to SQLite for audit.

Deliberately not here yet: vision-based extraction for scanned/image-only PDFs (no text layer to read without OCR
or a vision-capable model call — not yet built either way).

## Setup

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

(`cp .env.example .env` if you're in a bash shell instead of PowerShell/cmd.)

Edit `.env` and fill in your real `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`,
`AZURE_OPENAI_API_VERSION`, and `AZURE_OPENAI_API_KEY`. The deterministic-guardrail tests (below)
don't need these; every endpoint that actually calls the model does — Ingestion, Decomposition's
prose half, Completeness, Scoring, Recommendation, and evaluation-methodology extraction.

If `pip install` times out partway through on a slow connection, retry with a longer timeout:
`pip install --timeout 300 --retries 5 -r requirements.txt`.

## Run

```
uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000/docs` — that's the whole test harness for this project, no separate
client needed. **Stop the server (Ctrl+C, or kill the process) before copying, zipping, or moving
the project folder** — an active process holds a lock on its log/db files on Windows and file
operations will fail while it's running.

## First run checklist

1. Upload a real tender document under `POST /tenders/{id}/documents` and sanity-check the
   returned questions look right, or add/fix one manually with `POST /tenders/{id}/questions` —
   the Ingestion agent is real LLM extraction now, but still worth eyeballing on the first
   document from a new source, the same way you'd sanity-check any new LLM prompt against real
   input before trusting it.
2. Drive the core flow by hand in this order: `POST /tenders` → `POST /tenders/{id}/scoring-bands`
   (your five band descriptors) → `POST /tenders/{id}/documents` (upload a real ITT — a sample is
   provided, see below) → `POST /questions/{id}/decompose` → eyeball the candidate elements via
   `GET /questions/{id}/elements` → `POST /questions/{id}/lock` → `POST /questions/{id}/drafts`
   (paste a draft answer) → `POST /drafts/{id}/completeness` → `POST /drafts/{id}/score`.
3. Then the newer pieces: `POST /drafts/{id}/deterministic-checks` → `GET /drafts/{id}/gate` →
   upload a case study/CV via `POST /tenders/{id}/evidence` → `POST /drafts/{id}/recommendations`
   (confirm it never returns more than 3, and that `evidence_pointer` points at retrieved
   evidence rather than inventing any). For evaluation methodology, upload a document under
   category `strategy_and_context` that discusses how the buyer evaluates responses. Try
   `POST /drafts/{id}/theme-review` too — needs the question to be decomposed and locked first
   (that's where its theme comes from). For Benchmark: `POST /tenders/{id}/benchmark/cases` with
   a real historical answer and its known band, then `POST /benchmark/cases/{id}/run` and check
   `band_delta`.
4. Inspect `backend/bid_coauthor.db` directly (e.g. `sqlite3 bid_coauthor.db "select * from llm_call_log"`)
   to confirm every model call was logged with its prompt file and version hash.

A sample tender document is provided at `sample-data/sample-itt.docx` — name your tender
"Technology and Data Services 2027-2032" to match its content when testing with it.

## Tests

```
pytest
```

All test files need no Azure OpenAI credentials — they test deterministic wrapper logic (regex/
table extraction, quote verification, confidence calculation, the decision gate, the benchmark
band-delta arithmetic, the ingestion chunking/verbatim guard, the methodology-context formatter,
the theme-to-prompt-file mapping), not the model itself:

- `tests/test_decomposition_rules.py`
- `tests/test_completeness_verification.py`
- `tests/test_scoring_confidence.py`
- `tests/test_deterministic_checks.py`
- `tests/test_gate.py`
- `tests/test_benchmark_comparison.py`
- `tests/test_ingestion_extraction.py`
- `tests/test_methodology_extraction.py`
- `tests/test_theme_review_selection.py`
- `tests/test_methodology_extraction.py`

## Moving this to another laptop

Copy the whole `bid-co-author` folder (or clone it, if you put it in git) — **stop both the
backend and frontend dev servers first** (see the note under Run). On the new machine:

- Backend: `python -m venv .venv`, activate it, `pip install -r requirements.txt`, copy your
  `.env` over (it's gitignored — copy it by hand).
- Frontend: `npm install` inside `frontend/`, copy `frontend/.env` over if you customised it
  (also gitignored).

`bid_coauthor.db` and anything under `backend/data/` (including the Chroma evidence store) travel
with the folder automatically since they're plain files, not a service. Nothing here needs
Docker, a database server, or any other install. Note: `chromadb`'s default embedding model
downloads on first use, so the first evidence upload on a new machine needs internet access even
though everything else runs fully offline.
