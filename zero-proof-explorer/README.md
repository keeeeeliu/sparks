# Zero-Proof Explorer

A tiny Python learning project that touches every foundation from your Phase 1 roadmap in one coherent thread.

**Goal:** Build a CLI + data analysis tool over TheCocktailDB (free API, no auth) to practice Python fluency.

**Scope:** ~150 lines across 7 stages, one or two evenings.

---

## What You'll Learn

| Foundation | Where |
|---|---|
| data types, control flow, functions | JSON parsing, loops, small functions |
| comprehensions | building ingredient lists |
| error handling | try/except around network + missing fields |
| OOP (classes) | Cocktail class bundling data + methods |
| requests, json, file I/O | API fetches, save/load dataset.json |
| venv / pip | project setup |
| **async / asyncio** | concurrent fetch (the ~7.5× speedup pattern) |
| NumPy, Pandas, Matplotlib | DataFrame, aggregations, bar chart |

---

## Stages

### Stage 1: Fetch the List
- Make one HTTP GET to TheCocktailDB
- Parse JSON, extract list of non-alcoholic cocktails
- Print how many you found
- **Learns:** requests, json, error handling

### Stage 2: Cocktail Class
- Build a class that holds a drink's name, glass type, instructions, ingredients
- Use a **comprehension** to extract ingredients from the API response
- Implement `to_dict()` and `from_dict()` for serialization
- **Learns:** OOP, list comprehensions, properties

### Stage 3: Fetch Details (Sync → Async)
- Sync version: loop through drinks, fetch each detail one-by-one (slow)
- Async version: use `httpx.AsyncClient` + `asyncio.gather()` to fetch all concurrently (fast)
- Time both versions to see the ~7.5× speedup
- **Learns:** async/await, concurrency, performance comparison

### Stage 4: Save & Reload
- Serialize cocktails to `dataset.json`
- Load them back (round-trip validation)
- **Learns:** file I/O, JSON serialization, pathlib

### Stage 5: Analyze
- Build a Pandas DataFrame: one row per (drink, ingredient) pair
- Count ingredient frequency
- Print stats: total drinks, unique ingredients, average ingredients per drink
- **Learns:** Pandas groupby, value_counts, aggregations, NumPy

### Stage 6: Chart
- Plot the top 10 ingredients as a horizontal bar chart
- Save as `chart.png`
- **Learns:** Matplotlib, visualization

### Stage 7: CLI (Optional)
- Add an interactive search loop
- User types a drink name, you show matching cocktails
- **Learns:** user input, string matching, list filtering

---

## How to Use This Folder

```
zero-proof-explorer/
  ├── explore.py           ← Your file. Fill in the TODOs.
  ├── explore_reference.py ← Fully worked version. Check here when stuck.
  ├── requirements.txt     ← pip install -r requirements.txt
  └── README.md            ← This file
```

**Workflow:**
1. Set up a virtual environment and install dependencies
2. Open `explore.py`
3. Fill in each `# TODO:` following the hints
4. If you get stuck, peek at `explore_reference.py` for that stage
5. Run: `python explore.py`

---

## Setup

```bash
cd zero-proof-explorer
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## Running It

```bash
python explore.py
```

First time will:
1. Fetch ~100+ cocktails from the API
2. Fetch all their details (async, ~10–30 seconds)
3. Save to `dataset.json`
4. Analyze ingredients in Pandas
5. Generate `chart.png`
6. Launch interactive search (type `quit` to exit)

Subsequent runs will load from `dataset.json` (much faster).

---

## How to Approach Each Stage

**Stage 1 (fetch list):**
- Read the TODO carefully
- Look at the hint
- Think: "What's the pattern for making an HTTP call with requests?"
- Check `explore_reference.py:fetch_nonalcoholic_list()` only if stuck

**Stage 2 (Cocktail class):**
- Read the TODO
- Think: "What fields do I need to store?"
- Implement `__init__`, `ingredients` property, `to_dict()`, `from_dict()`
- Test by importing in Python REPL: `from explore import Cocktail`

**Stage 3 (async):**
- Implement sync first (straightforward loop)
- Then study the async version in the reference
- Key insight: `async def`, `await`, `asyncio.gather()` run many in parallel

**Stages 4–7:**
- Follow the same pattern: read TODO, think, check reference if stuck

---

## Output Files

After running:
- `dataset.json` — ~100+ cocktails in JSON format (safe to commit, good reference)
- `chart.png` — bar chart of top ingredients (cool to show off)

---

## Tips

- Don't copy/paste from the reference. Type it. Your fingers learn.
- If a stage feels confusing, try writing a 3-line test first (e.g., fetch one drink, print its name).
- The async stage is the most conceptually heavy. Don't rush it. The reference version has comments explaining why each line exists.
- If `requests` or `httpx` calls fail, it might be a network issue. Check your internet connection.
- Pandas is powerful—once you have the DataFrame, play with `df.groupby()`, `df.sort_values()`, etc. in a REPL.

---

## Next Steps (After Phase 1)

Once you've completed this and reflected:
- This dataset is real, publishable. Add a `chart.png` to your GitHub Phase-1 heatmap.
- The `Cocktail` class and async pattern are templates you'll use in larger projects.
- Pandas + Matplotlib are now in your muscle memory—you'll reach for them in data projects.

Good luck! This is the real deal. 🍹
