#!/usr/bin/env python3
"""
Zero-Proof Explorer: A learning project touching every Python foundation.

Stages:
1. Fetch the list
2. Cocktail class (OOP + comprehensions)
3. Fetch all details (sync → async concurrency)
4. Save & reload (file I/O + JSON)
5. Analyze in Pandas (counts, grouping)
6. Chart it (Matplotlib)
7. Optional: CLI search

Your task: fill in the TODOs in this file using explore_reference.py as a guide.
If you get stuck on a stage, check the reference version.
"""

import json
import asyncio
import time
from pathlib import Path
from typing import Optional

import requests
import httpx
import pandas as pd
import matplotlib.pyplot as plt


# ============================================================================
# STAGE 2: Cocktail class (OOP + comprehensions)
# ============================================================================

class Cocktail:
    """A single non-alcoholic cocktail with its details and ingredients."""

    def __init__(self, data: dict):
        # TODO: Store the API data dict. You'll need to extract:
        #   - id, name, glass, instructions
        # Hint: use data.get("key", "default") for safe access
        pass

    @property
    def ingredients(self) -> list[str]:
        """Extract ingredient names using a comprehension.

        The API returns ingredients as strIngredient1, strIngredient2, etc.
        Build and return a list of non-empty ingredient strings.

        Hint: use a list comprehension that loops through range(1, 16)
        and checks data.get(f"strIngredient{i}") for each number.
        """
        # TODO: Extract and return ingredients
        pass

    def to_dict(self) -> dict:
        """Serialize to dict for saving to JSON."""
        # TODO: Return a dict with keys: id, name, glass, instructions, ingredients
        pass

    @classmethod
    def from_dict(cls, data: dict) -> "Cocktail":
        """Deserialize from dict when loading from JSON.

        You need to reconstruct the API format so __init__ works.
        Build a dict with idDrink, strDrink, strGlass, strInstructions,
        and strIngredient1, strIngredient2, etc.
        """
        # TODO: Reconstruct API-format dict and return cls(api_data)
        pass


# ============================================================================
# STAGE 1: Fetch the list
# ============================================================================

def fetch_nonalcoholic_list() -> list[dict]:
    """Fetch all non-alcoholic cocktails from TheCocktailDB.

    URL: https://www.thecocktaildb.com/api/json/v1/1/filter.php?a=Non_Alcoholic

    Returns a list of dicts with 'strDrink' and 'idDrink'.
    Use try/except to catch requests.RequestException.
    """
    # TODO: Make the GET request, check for errors, and return data["drinks"]
    # Hint: requests.get() → resp.raise_for_status() → resp.json()
    pass


# ============================================================================
# STAGE 3: Fetch all details (sync → async)
# ============================================================================

def fetch_details_sync(drink_id: str) -> Optional[dict]:
    """Fetch full details for one cocktail (sync version).

    URL: https://www.thecocktaildb.com/api/json/v1/1/lookup.php?i={drink_id}

    This is slow; we'll speed it up with async later.
    Use try/except to handle errors gracefully.
    """
    # TODO: Fetch and return data["drinks"][0] or None if not found
    pass


def fetch_cocktails_sync(drink_list: list[dict]) -> list[Cocktail]:
    """Fetch all details synchronously (the slow way)."""
    # TODO: Loop through drink_list, call fetch_details_sync for each,
    # wrap in Cocktail, and return the list
    pass


async def fetch_details_async(client: httpx.AsyncClient, drink_id: str) -> Optional[dict]:
    """Fetch full details for one cocktail (async version).

    Same as fetch_details_sync but uses await so we can run many concurrently.
    Hint: use await client.get(...), handle httpx.RequestError
    """
    # TODO: Same as sync, but with await and httpx instead of requests
    pass


async def fetch_cocktails_async(drink_list: list[dict]) -> list[Cocktail]:
    """Fetch all details concurrently.

    Use httpx.AsyncClient, create tasks for each drink, and run them
    all in parallel with asyncio.gather(*tasks).

    Hint: open a context manager (async with), create tasks, gather, filter None.
    """
    # TODO: Create async client, set up tasks with fetch_details_async,
    # use asyncio.gather to run concurrently, wrap results in Cocktail
    pass


# ============================================================================
# STAGE 4: Save & reload (file I/O + JSON)
# ============================================================================

def save_cocktails(cocktails: list[Cocktail], filepath: str = "dataset.json"):
    """Save cocktails to JSON file.

    Convert each Cocktail to dict, then json.dump to file.
    """
    # TODO: Convert cocktails to dicts, open file, json.dump
    # Hint: [c.to_dict() for c in cocktails], then open with "w" mode
    pass


def load_cocktails(filepath: str = "dataset.json") -> list[Cocktail]:
    """Load cocktails from JSON file.

    Check if file exists (use Path(filepath).exists()).
    If it exists, open and json.load, then convert each dict to Cocktail.
    """
    # TODO: Check file exists, load JSON, convert to Cocktail objects
    # Hint: use Cocktail.from_dict(d) for each loaded dict
    pass


# ============================================================================
# STAGE 5: Analyze in Pandas (counts, grouping)
# ============================================================================

def analyze_ingredients(cocktails: list[Cocktail]):
    """Analyze ingredient frequency using Pandas.

    Create one row per (drink, ingredient) pair, count occurrences,
    and print some basic stats.

    Hint: build a list of dicts with "drink" and "ingredient" keys,
    then pd.DataFrame(rows). Use value_counts() and groupby().
    """
    # TODO: Build rows, create DataFrame, analyze with value_counts, groupby, size
    # Print: number of drinks, pairs, unique ingredients, avg ingredients per drink
    # Print: top 10 ingredients
    # Return ingredient_counts for the chart
    pass


# ============================================================================
# STAGE 6: Chart it (Matplotlib)
# ============================================================================

def plot_top_ingredients(ingredient_counts, top_n: int = 10, filepath: str = "chart.png"):
    """Create a bar chart of the top N ingredients.

    Use .head(top_n), then plt.figure, .plot(kind="barh"), labels, title,
    tight_layout, savefig, close.
    """
    # TODO: Extract top N, create horizontal bar chart, save to PNG
    pass


# ============================================================================
# STAGE 7: Optional CLI (user interaction + error handling)
# ============================================================================

def search_cocktails(cocktails: list[Cocktail], query: str) -> list[Cocktail]:
    """Search cocktails by name (case-insensitive)."""
    # TODO: Filter cocktails where query (lowercased) appears in name
    pass


def cli_interactive(cocktails: list[Cocktail]):
    """Simple interactive search loop.

    Loop: ask user for a search term, show results.
    Exit on 'quit'.
    """
    # TODO: while loop, input(), search_cocktails, print results
    # Hint: print first 5 results with name, glass, ingredients
    pass


# ============================================================================
# Main flow
# ============================================================================

def main():
    """Run the full pipeline: fetch → save → analyze → chart → optional CLI."""

    # ---- STAGE 1: Fetch list ----
    print("Fetching non-alcoholic cocktail list...")
    drink_list = fetch_nonalcoholic_list()
    print(f"Found {len(drink_list)} cocktails")

    # ---- STAGE 3: Fetch details (compare sync vs async) ----
    print("\n--- Sync fetch (for comparison) ---")
    start = time.time()
    cocktails_sync = fetch_cocktails_sync(drink_list[:5])  # Just first 5 to save time
    sync_time = time.time() - start
    print(f"Sync (5 drinks): {sync_time:.2f}s")

    print("\n--- Async fetch (the fast way) ---")
    start = time.time()
    cocktails = asyncio.run(fetch_cocktails_async(drink_list))
    async_time = time.time() - start
    print(f"Async (all {len(cocktails)} drinks): {async_time:.2f}s")

    if sync_time > 0 and async_time > 0:
        print(f"Speedup on first 5: ~{(sync_time / async_time):.1f}×")

    # ---- STAGE 4: Save ----
    save_cocktails(cocktails)

    # ---- Reload to show file I/O works ----
    cocktails = load_cocktails()

    # ---- STAGE 5: Analyze ----
    ingredient_counts = analyze_ingredients(cocktails)

    # ---- STAGE 6: Chart ----
    plot_top_ingredients(ingredient_counts)

    # ---- STAGE 7: Optional CLI ----
    print("\n" + "="*60)
    print("Interactive search (type 'quit' to exit)")
    print("="*60)
    cli_interactive(cocktails)

    print("\nDone!")


if __name__ == "__main__":
    main()
