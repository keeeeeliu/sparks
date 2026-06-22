# Project 2 — Zero-Proof Menu & Event RAG Assistant

> Status: **Not started** · Owner: Ke · Last updated: 2026-06-21 · Depends on: Project 1 (data)

A deployed, grounded chat assistant over a real corpus of **zero-proof recipes, flavor-pairing principles, and event-planning playbooks**. Done right — hybrid search, reranking, enforced citations, and a real evaluation framework.

**This is the employability unlock: once this is live, start applying for jobs.**

*Example query:* "Suggest a sophisticated alcohol-free menu for a 50-person autumn garden wedding, with a sparkling option and one zero-proof signature cocktail."

---

## What this demonstrates (resume signal)
Embeddings · vector DB · chunking strategy · **hybrid retrieval (BM25 + vector)** · **reranking** · enforced citations · **RAG evaluation methodology** (the rare, high-value skill) · deployment.

## Tech stack
- **Backend:** Python + **FastAPI**
- **Vector DB:** start with **Chroma** (easy local) → migrate to **pgvector** (Postgres) for production
- **Embeddings:** an embedding model (OpenAI / open-source)
- **Reranker:** cross-encoder (e.g., `sentence-transformers`) or a hosted rerank API
- **Eval:** **RAGAS** and/or **promptfoo**
- **Frontend:** simple chat UI (Streamlit to start is fine, Next.js if you want polish)
- **Deploy:** Render/Railway/Fly (backend) + Vercel (frontend if Next.js)

---

## Design

### Corpus (reuse Project 1 output)
- Validated recipes JSON from Project 1
- Flavor-pairing notes / principles
- Event-planning playbooks (timelines, portions, hosting tips)

### Ingestion pipeline
1. Load documents → **chunk** (experiment: size/overlap dramatically affects quality).
2. **Embed** chunks → store in vector DB.
3. Build a **keyword index (BM25)** over the same chunks for hybrid search.

### Retrieval + answer
1. Query → **hybrid retrieve** (BM25 + vector), merge results.
2. **Rerank** with a cross-encoder → take top-k.
3. LLM generates the answer **with enforced citations** (each claim ties to a source chunk).
4. Stream the response to the UI.

### Evaluation (do not skip — this is the differentiator)
- Build a **golden Q/A set** (~20-30 realistic questions).
- Metrics via RAGAS: **faithfulness / groundedness / answer relevance / context precision**.
- Track scores as you tune chunking, retrieval, and reranking. Be able to say "here's my eval framework, not vibes."
- Write up *why RAG over fine-tuning* (freshness + control + cost).

### Suggested folder structure
```
project-2-zeroproof-rag-assistant/
  README.md
  pyproject.toml
  .env.example
  backend/
    ingest.py        <- chunk + embed + index
    retrieve.py      <- hybrid search + rerank
    answer.py        <- LLM answer with citations
    api.py           <- FastAPI /chat (streaming)
  eval/
    golden_set.json  <- Q/A ground truth
    run_eval.py      <- RAGAS metrics
  frontend/          <- chat UI
  data/              <- corpus (incl. Project 1 output)
```

---

## Milestones
1. Ingest a small corpus into Chroma; basic vector retrieval working.
2. Add BM25 + hybrid merge; add cross-encoder reranking.
3. LLM answer with enforced citations; FastAPI streaming endpoint.
4. Build golden set + RAGAS eval; tune chunking/retrieval against scores.
5. Chat frontend; deploy live. Write README with eval results + RAG-vs-fine-tuning rationale.
6. Share with a few real users (sober-curious / wedding-planning communities) for feedback.

## Next steps
- [ ] Finish Project 1 so there's data to ingest.
- [ ] Stand up Chroma + a first retrieval test.

## References
See root `AI-project-ideas.md` (Project 2 section) and `AI-engineer-roadmap.md` (Phase 3).
