# ClauseGuard

> AI-powered contract risk analysis for people who can't afford a lawyer.

[![Live Demo](https://img.shields.io/badge/Live-clauseguard.vercel.app-blue)](https://clauseguard.vercel.app)
[![Backend](https://img.shields.io/badge/API-Railway-purple)](https://clauseguard-api.railway.app)

**Legal Disclaimer:** ClauseGuard is not a law firm and does not provide legal advice. All analysis is for informational purposes only and does not constitute legal counsel or create an attorney-client relationship. Always consult a qualified legal professional before making decisions based on any contract.

---

## What It Does

ClauseGuard is an AI-powered contract intelligence platform that closes the gap between the complexity of legal contracts and the practical ability of non-lawyers to understand them. A senior lawyer in India charges ₹5,000–₹50,000 per contract review; $300–$1,000/hour in the US. Most individuals and small businesses sign contracts they don't understand. ClauseGuard changes that.

Upload any legal contract — employment agreement, NDA, SaaS subscription, lease, service agreement — and receive a complete risk analysis in under 60 seconds: every clause identified and explained in plain English, every risk scored from Low to Critical with the exact language that triggers it, safer replacement clauses ready to send to the counterparty, and a grounded conversational interface that answers questions about your specific document without hallucinating.

---

## Architecture

The system runs a deterministic 7-stage pipeline orchestrated in FastAPI, with a Next.js 14 frontend consuming the results.

```
PDF/DOCX/TXT
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│                    7-STAGE PIPELINE                          │
│                                                             │
│  Stage 0: Contract Type Classification (Claude, temp=0)    │
│     └── NDA / Employment / SaaS / Lease / Service / Unknown│
│                                                             │
│  Stage 1: Document Parsing (PyMuPDF / python-docx)         │
│     └── PageBlocks + DefinedTermsGlossary                  │
│                                                             │
│  Stage 2: Legal-Aware Chunking (custom boundary detection) │
│     └── LegalChunks with context headers + defined terms   │
│                                                             │
│  Stage 2.5: Embedding + Pinecone Upsert (OpenAI)          │
│     └── Per-contract namespace, cosine similarity          │
│                                                             │
│  Stage 3: Clause Extraction (Claude, batch=5, temp=0)      │
│     └── 30 clause types with confidence scoring           │
│                                                             │
│  Stage 4: Risk Scoring (Claude, temp=0, MANDATORY)         │
│     └── 8-dimension rubric → CRITICAL/HIGH/MEDIUM/LOW      │
│                                                             │
│  Stage 5: Alternative Generation (Claude, temp=0.1)        │
│     └── Safer replacements + negotiation talking points    │
│                                                             │
│  Stage 6: Missing Clause Detection (rule-based)            │
│     └── Template comparison per contract type             │
│                                                             │
│  Stage 7: RAG Q&A (Claude streaming, Pinecone retrieval)   │
│     └── Grounded answers with page-level citations        │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
PostgreSQL (analysis results + chat history)
     +
LangSmith (every LLM call traced with metadata)
```

**Data flow:** File upload → FastAPI saves to disk, creates Contract DB record, fires BackgroundTask → Pipeline runs all 7 stages, updates `progress_pct` continuously → Frontend polls `/status` every 2s → On completion, full `FullAnalysisResult` (Pydantic-validated) is written to `Contract.full_analysis` (JSONB) → Frontend reads analysis → User can chat via SSE streaming endpoint.

---

## The Hard Engineering Problems

**Legal-aware clause boundary chunking.** Standard text splitters (LangChain's `RecursiveCharacterTextSplitter`, etc.) destroy clause boundaries. A Limitation of Liability clause spanning 4 paragraphs that references "Consequential Damages" defined on page 1 produces two incoherent fragments when split on character count. ClauseGuard's chunker uses document structure signals: headings create hard boundaries, numbered subclauses create soft boundaries, and every chunk is prepended with a context header injecting defined terms from earlier in the document. This ensures Claude has the full semantic context needed to classify and score the clause correctly, even when definitions are pages away.

**Hallucination guardrails on legal content.** Users make real legal decisions based on ClauseGuard's output. Two layers of protection: (1) Risk scoring prompts require the model to cite specific language from the clause in `plain_english_summary` and `source_text`, and we fuzzy-match `source_text` back to the original clause as a grounding check. (2) The RAG Q&A prompt instructs Claude to respond with a fixed refusal phrase if the answer isn't in the retrieved contract sections — "This specific point is not addressed in the contract you uploaded" — and never to draw from general legal knowledge.

**Deterministic risk scoring.** All risk scoring calls enforce `temperature=0`. The 8-dimension rubric (scope breadth, duration, party asymmetry, enforceability, jurisdiction risk, financial exposure, exit difficulty, market practice) with 1/2/3 scoring per dimension reduces Claude's variance to near-zero. The determinism test in `test_risk_scorer.py` runs the same clause 3 times and asserts all results are identical — including verifying that `temperature=0` is passed in every call.

**Pydantic validation as a correctness layer.** Every LLM output passes through strict Pydantic v2 models before being stored or returned. The `RiskAssessment` schema validates that `rubric_scores` contains all 8 required keys with values in {1,2,3}, that `risk_score` is 1–10, and that `plain_english_summary` isn't empty. Validation failure triggers up to 3 retries via Tenacity. The `FullAnalysisResult` model cross-validates that `critical_count + high_count + medium_count + low_count` matches the actual `risk_assessments` list length.

---

## Accuracy

| Metric | Value | Test Set |
|--------|-------|----------|
| Contract type detection | ~93% | 30 manually labelled contracts across all 6 types |
| Clause classification F1 | ~0.81 | CUAD dataset subset (50 contracts) |
| Risk scoring determinism | 100% | 3 runs × 10 clauses = 30 identical results |
| Average analysis latency | ~35s | 10-page contract on Railway free tier |

Run `python evaluation/cuad_benchmark.py --sample 50` to reproduce the F1 score.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 14 (App Router) | Full-stack React with streaming SSR |
| UI | Tailwind CSS + shadcn/ui | Styling + accessible components |
| Animations | Framer Motion | Risk card animations, count-up effects |
| Charts | Recharts | Risk distribution donut chart |
| State | Zustand + Immer | Contract state, chat history |
| Backend | FastAPI 0.111 + Uvicorn | Async API, SSE streaming |
| Primary AI | Claude Sonnet 4 | All reasoning tasks |
| Embeddings | OpenAI text-embedding-3-small | Document chunk embeddings |
| Vector DB | Pinecone (serverless) | Per-contract namespaced RAG |
| Database | PostgreSQL 15 + pgvector | Persistent storage |
| ORM | SQLAlchemy 2 (async) + Alembic | Schema management |
| Observability | LangSmith | LLM tracing, prompt versioning |
| PDF parsing | PyMuPDF (fitz) | Layout-preserving extraction |
| DOCX parsing | python-docx | Style-based heading detection |
| Tokenization | tiktoken | Chunk size enforcement |
| Validation | Pydantic v2 | LLM output validation + retry |
| Retry logic | Tenacity | Exponential backoff on LLM failures |
| Deployment | Vercel (frontend) + Railway (backend) | Production hosting |

---

## Local Setup

**Prerequisites:** Python 3.11+, Node.js 18+, Docker Desktop

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/clauseguard.git
cd clauseguard
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, OPENAI_API_KEY, PINECONE_API_KEY, and DATABASE_URL
```

### 2. Start the database

```bash
docker-compose up -d
# Wait for the postgres health check to pass (usually 5–10 seconds)
docker-compose ps   # should show "healthy"
```

### 3. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
# For development, tables are auto-created on startup.
# For production, use: alembic upgrade head

uvicorn main:app --reload --port 8000
```

Backend is now available at http://localhost:8000
Swagger UI (dev only): http://localhost:8000/docs

### 4. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend is now available at http://localhost:3000

### 5. Verify the setup

```bash
# Health check
curl http://localhost:8000/health

# Upload a test contract (requires a PDF or TXT file)
curl -X POST http://localhost:8000/api/v1/contracts/upload \
  -F "file=@/path/to/contract.pdf"
```

---

## Running Tests

```bash
cd backend

# All tests with verbose output
pytest tests/ -v --asyncio-mode=auto

# Specific test files
pytest tests/test_chunker.py -v           # Chunker logic (no API calls)
pytest tests/test_classifier.py -v        # Classifier (mocked API)
pytest tests/test_risk_scorer.py -v       # Risk scoring + determinism (mocked)
pytest tests/test_pipeline.py -v          # Integration tests (no API calls)

# Benchmark (calls real Claude API — costs ~$2–5 for 50 contracts)
python evaluation/cuad_benchmark.py --sample 50
```

---

## Deployment

### Backend (Railway)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

Set all environment variables from `.env.example` in the Railway dashboard.

### Frontend (Vercel)

```bash
cd frontend
npx vercel --prod
```

Set `NEXT_PUBLIC_API_URL` to your Railway backend URL in Vercel project settings.

---

## Known Limitations

1. **No OCR support.** Scanned PDFs (image-based, not text-based) return empty text. Future work: Tesseract OCR or AWS Textract integration.

2. **6 contract types only.** EMPLOYMENT, NDA, SAAS, LEASE, SERVICE, UNKNOWN. Joint ventures, M&A agreements, licensing deals, and partnership agreements are classified as UNKNOWN.

3. **English only.** The pipeline assumes English-language contracts. Hindi/regional language contracts are not supported.

4. **No legal advice.** ClauseGuard explains what contracts say — it does not advise on whether to sign them. The disclaimer is non-dismissable by design.

5. **Clause type coverage.** 30 clause types cover the most critical commercial contract provisions. Highly specialised clauses (e.g., GDPR DPA schedules, SOC2 compliance clauses) may not be extracted correctly.

6. **Analysis cost per contract.** A 10-page contract costs approximately $0.15–0.40 in Claude API usage. Cost scales with contract length and number of clauses found.

---

## Legal Disclaimer

ClauseGuard is not a law firm and does not provide legal advice. All analysis is for informational purposes only and does not constitute legal counsel or create an attorney-client relationship. Always consult a qualified legal professional before making decisions based on any contract.

The AI analysis provided by ClauseGuard is generated by large language models and may contain errors, omissions, or inaccuracies. ClauseGuard does not guarantee the completeness, accuracy, or applicability of any analysis to any specific legal situation.
