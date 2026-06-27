# Data source documentation ("data cards")

This folder characterizes the **external data sources** the project depends on — their
schema, field coverage, reliability, access quirks, and **known gotchas**.

This follows the industry practice of **data cards / "Datasheets for Datasets"**
(Gebru et al., 2018; Google Data Cards, 2022): document a data source's provenance and
caveats so downstream users don't rediscover its quirks the hard way.

### How this differs from the other docs
- **ADRs (`docs/decisions/`)** record *decisions* ("we chose X because…").
- **Data cards (here)** record *facts about a data source* ("field Y is only 30% populated
  and is unreliable"). ADRs cite data cards as evidence.
- **`PROGRESS.md`** tracks operational status.

### Principle: claims must be reproducible
Every quantitative claim here should be re-runnable. The numbers in `livewhale.md` are
reproduced by [`scripts/profile_livewhale.py`](../../scripts/profile_livewhale.py) — run it
to verify, don't just trust the doc.

### Cards
- [`livewhale.md`](livewhale.md) — Brown's LiveWhale events calendar (`events.brown.edu`).
