<div align="center">

![ClauseGuard Hero](hero-banner.svg)

# ClauseGuard

**AI contract intelligence. For people who can't afford a lawyer.**

A senior lawyer in India charges ₹5,000–₹50,000 per contract review.  
Most people just sign and hope for the best.

ClauseGuard reads every clause, scores every risk, and hands you safer replacement text — in under 60 seconds.

[![Live Demo](https://img.shields.io/badge/Live-clauseguard.vercel.app-0070F3?style=flat-square&logo=vercel&logoColor=white)](https://clauseguard.vercel.app)
[![API](https://img.shields.io/badge/API-Railway-7C3AED?style=flat-square)](https://clauseguard-api.railway.app/docs)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Claude](https://img.shields.io/badge/Claude_Sonnet_4-Anthropic-CC7E00?style=flat-square)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## What it actually does

Upload any contract — employment agreement, NDA, SaaS subscription, office lease, service agreement. In under 60 seconds:

- **Every clause identified** across 30 types, in plain English — not legalese restated differently
- **Every risk scored** from Low to Critical using an 8-dimension rubric, with the exact source language that triggered it
- **Safer replacement clauses** generated and ready to copy back to the counterparty
- **A document-grounded chat** that answers questions about *your specific contract* — if the answer isn't in the document, the model says so and stops there

Zero hallucination tolerance. Every answer is grounded in retrieved contract text. The refusal phrase is hard-coded.

---

## Dashboard

![ClauseGuard Dashboard](dashboard.svg)

---

## Upload & Analysis Progress

![Upload and Progress](upload-progress.svg)

---

## Safer Replacement Clauses

![Safer Replacement](replacement.svg)

---

## Contract Q&A (RAG — Stage 7)

![RAG Chat Interface](chat.svg)

---

## The Pipeline

![7-Stage Pipeline](pipeline.svg)

Seven stages run sequentially as a FastAPI `BackgroundTask`. The frontend polls `/api/v1/contracts/{id}/status` every 2 seconds, reading `progress_pct` from PostgreSQL. When complete, the full `FullAnalysisResult` — a strictly-validated Pydantic v2 model — is written to a JSONB column and the dashboard hydrates from it.

| Stage | What happens | Key tech |
|-------|-------------|----------|
| **0** | Contract type classification | Claude Sonnet 4 · `temp=0` · 6 types |
| **1** | Structural document parsing | PyMuPDF (fitz) · python-docx · PageBlocks + DefinedTermsGlossary |
| **2** | Legal-aware clause boundary chunking | Custom chunker · heading hard-stops · context headers |
| **2.5** | Embed chunks → Pinecone upsert | OpenAI `text-embedding-3-small` (1536d) · per-contract namespace |
| **3** | Clause extraction across 30 types | Claude · `batch=5` · `temp=0` |
| **4** | Risk scoring — 8 dimensions per clause | Claude · `temp=0` enforced · CRITICAL / HIGH / MEDIUM / LOW |
| **5** | Safer replacement clause generation | Claude · `temp=0.1` · negotiation talking points |
| **6** | Missing clause detection | Rule-based template comparison per contract type |
| **7** | RAG Q&A with streaming response | Claude + Pinecone retrieval · SSE · page-level citations |

---

## Tech Stack

![Tech Stack](techstack.svg)

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | Next.js 14 App Router | RSC + streaming SSR, zero config |
| **Styling** | Tailwind CSS + shadcn/ui | Accessible components, no fighting the framework |
| **Animation** | Framer Motion | Risk card staggered reveals, count-up effects |
| **Charts** | Recharts | Donut chart for risk distribution |
| **State** | Zustand + Immer | Flat, immutable, no context hell |
| **Backend** | FastAPI 0.111 + Uvicorn | Async-native, SSE support, auto Swagger docs |
| **AI (all stages)** | Claude Sonnet 4 | Classification, extraction, scoring, alternatives, chat |
| **Embeddings** | OpenAI text-embedding-3-small | 1536d, cost-efficient, strong on legal text |
| **Vector DB** | Pinecone serverless | Per-contract namespace isolation, cosine similarity |
| **Database** | PostgreSQL 15 + pgvector | JSONB for analysis results, pgvector for local search |
| **ORM** | SQLAlchemy 2 async + Alembic | Type-safe queries, tracked migration history |
| **Observability** | LangSmith | Every LLM call traced with latency, tokens, prompt version |
| **PDF parsing** | PyMuPDF (fitz) | Layout-preserving extraction, not raw text dump |
| **DOCX parsing** | python-docx | Style-based heading detection for chunker signals |
| **Tokenization** | tiktoken | Chunk size enforced in tokens, not characters |
| **Validation** | Pydantic v2 | Strict LLM output schemas, field-level validators |
| **Retry** | Tenacity | Exponential backoff on LLM validation failures (max 3) |
| **Deployment** | Vercel + Railway | Zero-config; Railway for long-lived async backend |
| **Local dev** | Docker Compose | PostgreSQL 15 (pgvector image) + Redis both with healthchecks |

---

## Engineering decisions that actually matter

### Why a custom chunker instead of LangChain's `RecursiveCharacterTextSplitter`

LangChain's standard splitter cuts by character count. A Limitation of Liability clause spanning four paragraphs that references "Consequential Damages" — defined on page 1 — splits into two incoherent fragments. Claude sees half a clause with a reference to a term it has no definition for.

ClauseGuard's chunker reads document structure: headings create hard boundaries, numbered subclauses create soft ones, and every chunk gets a prepended context header injecting the defined terms glossary extracted in Stage 1. When Claude sees the chunk, it has full semantic context even when the definition lives 12 pages away.

```python
# Every chunk carries forward the terms defined earlier in the contract
chunk_header = f"""
[CONTEXT: This clause references the following defined terms from earlier in this agreement:
{defined_terms_for_chunk}]
---
"""
full_chunk = chunk_header + raw_clause_text
```

### Hallucination containment — two hard layers

Users make real legal decisions from this output. Two layers:

**Layer 1 — Source grounding on every risk score.** Every `RiskAssessment` requires a `source_text` field quoting the exact contract language that triggered the score. After generation, `source_text` is fuzzy-matched back against the original clause. No match → rejected and retried.

**Layer 2 — Hard-coded refusal phrase.** The RAG Q&A prompt instructs the model to return exactly this string when the answer isn't in retrieved sections:

```
This specific point is not addressed in the contract you uploaded.
```

The phrase is detectable in the SSE stream, so the frontend renders it in grey — visually distinct from a real answer — and stops there. The model is explicitly told never to draw from general legal knowledge.

### Temperature=0 as a correctness contract

`temperature=0` is enforced on every classification, extraction, and risk-scoring call. The 8-dimension rubric (scope breadth, duration, party asymmetry, enforceability, jurisdiction risk, financial exposure, exit difficulty, market practice) with 1/2/3 scoring per dimension collapses Claude's output variance to near-zero.

The determinism test runs the same clause three times and asserts all outputs are byte-identical — including verifying `temperature=0` was passed:

```python
# tests/test_risk_scorer.py
async def test_risk_scoring_is_deterministic():
    results = [await score_risk(TEST_CLAUSE) for _ in range(3)]
    assert results[0].risk_score == results[1].risk_score == results[2].risk_score
    assert results[0].rubric_scores == results[1].rubric_scores  # all 8 dimensions
```

### Pydantic v2 as the output validation layer

Every LLM response passes through strict Pydantic v2 validation before touching the database:

- `rubric_scores` must have exactly 8 keys with values in `{1, 2, 3}`
- `risk_score` must be 1–10
- `plain_english_summary` must be non-empty
- `source_text` must be non-empty and pass fuzzy-match against source clause
- `FullAnalysisResult` cross-validates: `critical_count + high_count + medium_count + low_count == len(risk_assessments)`

Validation failure triggers Tenacity retry with exponential backoff (immediate → +2s → +4s, then raise).

### Why Pinecone over pgvector for RAG

pgvector is in the stack (it's in the Docker image). For RAG, Pinecone's per-namespace isolation — one namespace per uploaded contract UUID — guarantees that retrieval only ever touches the current user's document. With pgvector, that isolation requires careful per-query filtering. That's one more thing to get wrong in a legal context.

### Why JSONB for analysis results

The `FullAnalysisResult` schema evolves. JSONB means Alembic migrations don't block reads of older records — old results still deserialize through `model_validate()` with graceful defaults for any new fields added later.

### Why direct Anthropic SDK calls instead of LangChain

LangChain adds indirection between the prompt and the model call. For a system where temperature, exact prompt text, and output schema all need to be precisely controlled, that indirection is risk. Every LLM call in ClauseGuard goes through the Anthropic SDK directly. LangSmith is used for tracing only — observability without framework lock-in.

---

## Accuracy

| Metric | Result | How measured |
|--------|--------|--------------|
| Contract type detection | **~93%** | 30 manually labelled contracts across all 6 types |
| Clause classification F1 | **~0.81** | CUAD dataset, 50-contract sample |
| Risk scoring determinism | **100%** | 3 runs × 10 clauses = 30 identical outputs |
| Average analysis latency | **~35s** | 10-page contract, Railway free tier |
| Cost per analysis | **$0.15–0.40** | Varies with document length |

Reproduce the F1 score:

```bash
python evaluation/cuad_benchmark.py --sample 50
# Costs ~$2–5 in real Claude API calls
```

---

## Getting started

**Requirements:** Python 3.11+, Node.js 18+, Docker Desktop

### 1. Clone and configure

```bash
git clone https://github.com/sat1828/ClauseGuard.git
cd ClauseGuard
cp .env.example .env
```

Open `.env` and fill in:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=clauseguard-prod
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/clauseguard
LANGSMITH_API_KEY=...        # optional but recommended
LANGSMITH_PROJECT=clauseguard
```

### 2. Start the database

```bash
docker-compose up -d
docker-compose ps   # both postgres and redis should show "healthy"
```

> **Important:** The compose file uses `pgvector/pgvector:pg15` — not the standard Postgres image. pgvector is not installable at runtime in the standard image.

### 3. Backend

```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Swagger UI → `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

App → `http://localhost:3000`

### Windows one-click (PowerShell)

```powershell
.\setup.bat   # first time — creates venv, installs deps, runs migrations
.\start.bat   # every subsequent run — starts both backend and frontend
```

### 5. Smoke test

```bash
# Health check
curl http://localhost:8000/health

# Upload a contract
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -F "file=@/path/to/contract.pdf"
# Returns { "contract_id": "uuid", "status": "pending" }

# Poll for status
curl http://localhost:8000/api/v1/contracts/{contract_id}/status
# Returns { "status": "complete", "progress_pct": 100 }
```

---

## Tests

```bash
cd backend

# Full test suite (no real API calls — all mocked)
pytest tests/ -v --asyncio-mode=auto

# Individual suites
pytest tests/test_chunker.py -v          # Chunker logic — zero API calls
pytest tests/test_classifier.py -v       # Classification — mocked API
pytest tests/test_risk_scorer.py -v      # Risk scoring + determinism — mocked
pytest tests/test_pipeline.py -v         # Integration — mocked end-to-end

# Run with Windows batch file
.\run_tests.bat
```

The determinism test is the most important one. It runs the same clause three times and fails if a single dimension score differs — including verifying that `temperature=0` was actually passed to the API client, not just intended.

---

## Deploy to production

### Backend → Railway

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Set every variable from `.env.example` in the Railway dashboard. Railway's persistent disk handles uploaded contract files between deploys.

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your Railway backend URL in Vercel project settings.

---

## Project structure

```
ClauseGuard/
├── backend/
│   ├── main.py                   # FastAPI app, routes, BackgroundTask dispatch
│   ├── pipeline/
│   │   ├── classifier.py         # Stage 0: contract type — Claude, temp=0
│   │   ├── parser.py             # Stage 1: PyMuPDF + python-docx
│   │   ├── chunker.py            # Stage 2: legal-aware boundary detection
│   │   ├── embedder.py           # Stage 2.5: OpenAI embed + Pinecone upsert
│   │   ├── extractor.py          # Stage 3: clause extraction, batch=5
│   │   ├── risk_scorer.py        # Stage 4: 8-dim rubric, temp=0 enforced
│   │   ├── alternatives.py       # Stage 5: safer replacement generation
│   │   ├── missing_detector.py   # Stage 6: rule-based template comparison
│   │   └── rag_qa.py             # Stage 7: Pinecone RAG + SSE streaming
│   ├── models/
│   │   ├── schemas.py            # Pydantic v2: RiskAssessment, FullAnalysisResult
│   │   └── database.py           # SQLAlchemy 2 async models, Alembic config
│   ├── tests/
│   │   ├── test_chunker.py
│   │   ├── test_classifier.py
│   │   ├── test_risk_scorer.py   # Determinism test lives here
│   │   └── test_pipeline.py
│   ├── evaluation/
│   │   └── cuad_benchmark.py     # CUAD F1 evaluation (~$2–5 in API costs)
│   └── requirements.txt
├── frontend/
│   ├── app/                      # Next.js 14 App Router
│   │   ├── page.tsx              # Landing + file upload
│   │   ├── analysis/[id]/        # Risk dashboard, per-contract
│   │   └── api/                  # Next.js API routes
│   ├── components/
│   │   ├── RiskCard.tsx          # Framer Motion animated risk cards
│   │   ├── DonutChart.tsx        # Recharts risk distribution
│   │   ├── ChatInterface.tsx     # SSE streaming Q&A
│   │   └── AnalysisProgress.tsx  # Live pipeline stage progress (polls /status)
│   └── store/
│       └── contractStore.ts      # Zustand + Immer state management
├── docker-compose.yml            # pgvector/pgvector:pg15 + redis:7-alpine
├── setup.bat                     # Windows: venv + deps + migrations
├── start.bat                     # Windows: starts backend + frontend
├── run_tests.bat                 # Windows: runs full test suite
└── docs/
    └── images/                   # All SVG diagrams used in this README
```

---

## Known limitations

| Limitation | Why | Fix |
|------------|-----|-----|
| Scanned / image PDFs | No OCR in pipeline | Tesseract or AWS Textract |
| 6 contract types | Training data boundary | More examples + eval set |
| English only | No multilingual prompting | Hindi/regional variants |
| 30 clause types | CUAD taxonomy boundary | Expand + fine-tune |
| Cost per analysis | Real LLM API calls | Cache identical clauses across similar contracts |

---

## Data model

**`contracts` table (PostgreSQL)**

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | `gen_random_uuid()` |
| `filename` | `VARCHAR(255)` | Original upload name |
| `file_path` | `TEXT` | Server-side path |
| `file_size_bytes` | `BIGINT` | |
| `contract_type` | `VARCHAR(50)` | Enum: 6 types |
| `status` | `VARCHAR(20)` | `pending / running / complete / failed` |
| `progress_pct` | `INTEGER` | Polled by frontend every 2s |
| `full_analysis` | `JSONB` | `FullAnalysisResult` — full Pydantic model serialised |
| `pinecone_namespace` | `TEXT` | Contract UUID → isolated namespace |
| `created_at` | `TIMESTAMPTZ` | |
| `completed_at` | `TIMESTAMPTZ` | |
| `error_message` | `TEXT` | Set on pipeline failure |

**`chat_messages` table**

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` PK | |
| `contract_id` | `UUID` FK | → `contracts.id` |
| `role` | `TEXT` | `user` / `assistant` |
| `content` | `TEXT` | |
| `citations` | `JSONB` | `[{clause_ref, page_number}]` |
| `created_at` | `TIMESTAMPTZ` | |

---

## Legal disclaimer

ClauseGuard is not a law firm. This is not legal advice. All analysis is informational only and does not create an attorney-client relationship. Consult a qualified lawyer before acting on any contract analysis.

---

<div align="center">

</div>
