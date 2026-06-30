# Project 1 — Recipe & Vendor Extractor

> Status: **Not started** · Owner: Ke · Last updated: 2026-06-21

A warm-up project that turns messy, unstructured text (zero-proof cocktail recipes, vendor quotes, venue info) into **clean, validated, structured data** — and *measures* how accurate the extraction is.

It's small and fast, but it proves "production instincts": you know LLM output is unreliable by default, so you validate and evaluate it. Bonus: the structured output becomes the seed corpus for Projects 2 & 3.

---

## What this demonstrates (resume signal)
LLM API usage · structured output / function calling · **Pydantic validation** · prompt engineering · **basic evaluation** (field-level accuracy).

## Tech stack
- **Python 3.11+** (use `uv` or `venv` for env management)
- An **LLM API** (OpenAI or Anthropic) — provider-agnostic wrapper so it's swappable
- **Pydantic** for schema + validation
- Optional later: a small **FastAPI** endpoint + minimal UI

---

## Design

### Input
Raw text / HTML / PDF of:
- Zero-proof & cocktail **recipes** (e.g., Seedlip, Lyre's, Ghia spec sheets; mocktail recipe sites)
- **Vendor** quotes / venue info sheets

### Target schemas (Pydantic)
```python
class Ingredient(BaseModel):
    name: str
    quantity: float | None
    unit: str | None

class Recipe(BaseModel):
    name: str
    kind: Literal["mocktail", "cocktail"]
    abv: float          # 0.0 for zero-proof
    ingredients: list[Ingredient]
    method: list[str]   # ordered steps
    glassware: str | None
    garnish: str | None
    flavor_profile: list[str]   # e.g. ["citrus", "herbal", "bitter"]
    source: str | None

class Vendor(BaseModel):
    name: str
    category: Literal["catering", "venue", "music", "florals", "rentals", "other"]
    services: list[str]
    price_range: str | None
    capacity: int | None
    location: str | None
    lead_time_days: int | None
    contact: str | None
    portfolio_url: str | None
```

### Pipeline
1. **Load** raw input (start with plain text; add PDF/HTML parsing later).
2. **Extract** — call the LLM with the schema using structured output / function calling.
3. **Validate** — parse into the Pydantic model; on failure, run a **repair retry** (feed the validation error back to the model).
4. **Store** — write validated records as JSON (this becomes Project 2's corpus).

### Evaluation (the part that matters)
- Hand-label ~20 samples as ground truth.
- Compute **field-level accuracy**: exact match for categoricals, fuzzy match for text.
- Report a simple accuracy table per field. Track it as you improve prompts.

### Suggested folder structure
```
project-1-recipe-vendor-extractor/
  README.md            <- this file
  pyproject.toml       <- deps (pydantic, openai/anthropic, ...)
  .env.example         <- API key placeholders (never commit real keys)
  src/
    models.py          <- Pydantic schemas
    extract.py         <- extraction pipeline + repair retry
    llm.py             <- provider-agnostic LLM wrapper
    cli.py             <- `python -m src.cli --input file --type recipe`
  data/
    raw/               <- input samples
    output/            <- validated JSON
    labeled/           <- hand-labeled ground truth
  eval/
    evaluate.py        <- field-level accuracy
```

---

## Milestones
1. Env + deps + LLM wrapper + `.env.example`. Make one successful API call.
2. Define Pydantic schemas; extract one recipe end-to-end into valid JSON.
3. Add repair-retry on validation failure; batch over 100+ inputs.
4. Hand-label 20 samples; build the eval; report accuracy.
5. (Optional) FastAPI endpoint + tiny UI. Write the README results section.

## Data sources to collect
Seedlip / Lyre's / Ghia spec sheets, public mocktail recipe sites, sample vendor quote PDFs, venue listing pages.

## Next steps
- [ ] Decide LLM provider, set up env, make first API call.
- [ ] Implement `models.py` schemas.

## References
See root `AI-project-ideas.md` (Project 1 section) and `AI-engineer-roadmap.md` (Phase 2).
