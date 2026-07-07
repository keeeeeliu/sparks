#!/usr/bin/env python3
"""
Zero-Proof Explorer: A learning project touching every Python foundation.
Reference (fully worked) version for when you get stuck.

Stages:
1. Fetch the list
2. Cocktail class (OOP + comprehensions)
3. Fetch all details (sync → async concurrency)
4. Save & reload (file I/O + JSON)
5. Analyze in Pandas (counts, grouping)
6. Chart it (Matplotlib)
7. Optional: CLI search
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
        """Initialize from the API detail dict."""
        self.id = data.get("idDrink")
        self.name = data.get("strDrink", "Unknown")
        self.glass = data.get("strGlass", "Unknown")
        self.instructions = data.get("strInstructions", "")
        self._data = data

    @property
    def ingredients(self) -> list[str]:
        """Extract ingredient names using a comprehension.

        API returns ingredients spread across strIngredient1, strIngredient2, etc.
        This comprehension builds the list of non-empty ingredients.
        """
        return [
            self._data[f"strIngredient{i}"]
            for i in range(1, 16)
            if self._data.get(f"strIngredient{i}")
        ]

    def to_dict(self) -> dict:
        """Serialize to dict (for saving to JSON)."""
        return {
            "id": self.id,
            "name": self.name,
            "glass": self.glass,
            "instructions": self.instructions,
            "ingredients": self.ingredients,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Cocktail":
        """Deserialize from dict (when loading from JSON)."""
        # Reconstruct the API format so __init__ works
        api_data = {
            "idDrink": data["id"],
            "strDrink": data["name"],
            "strGlass": data["glass"],
            "strInstructions": data["instructions"],
        }
        for i, ing in enumerate(data["ingredients"], start=1):
            api_data[f"strIngredient{i}"] = ing
        return cls(api_data)


# ============================================================================
# STAGE 1: Fetch the list
# ============================================================================

def fetch_nonalcoholic_list() -> list[dict]:
    """Fetch all non-alcoholic cocktails from TheCocktailDB.

    Returns a list of dicts with 'strDrink' and 'idDrink'.
    """
    try:
        resp = requests.get(
            "https://www.thecocktaildb.com/api/json/v1/1/filter.php?a=Non_Alcoholic"
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("drinks"):
            print("No drinks found!")
            return []

        return data["drinks"]
    except requests.RequestException as e:
        print(f"Error fetching list: {e}")
        return []


# ============================================================================
# STAGE 3: Fetch all details (sync → async)
# ============================================================================

def fetch_details_sync(drink_id: str) -> Optional[dict]:
    """Fetch full details for one cocktail (sync version).

    Shows what we're doing, then we'll speed it up with async.
    """
    try:
        resp = requests.get(
            f"https://www.thecocktaildb.com/api/json/v1/1/lookup.php?i={drink_id}"
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("drinks"):
            return data["drinks"][0]
        return None
    except requests.RequestException as e:
        print(f"Error fetching {drink_id}: {e}")
        return None


def fetch_cocktails_sync(drink_list: list[dict]) -> list[Cocktail]:
    """Fetch all details synchronously (the slow way)."""
    cocktails = []
    for drink in drink_list:
        detail = fetch_details_sync(drink["idDrink"])
        if detail:
            cocktails.append(Cocktail(detail))
    return cocktails


async def fetch_details_async(client: httpx.AsyncClient, drink_id: str) -> Optional[dict]:
    """Fetch full details for one cocktail (async version).

    Same logic, but awaitable so we can run many concurrently.
    """
    try:
        resp = await client.get(
            f"https://www.thecocktaildb.com/api/json/v1/1/lookup.php?i={drink_id}"
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("drinks"):
            return data["drinks"][0]
        return None
    except httpx.RequestError as e:
        print(f"Error fetching {drink_id}: {e}")
        return None


async def fetch_cocktails_async(drink_list: list[dict]) -> list[Cocktail]:
    """Fetch all details concurrently using httpx.AsyncClient.

    This is the ~7.5× speedup pattern you'll use in your real app.
    """
    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_details_async(client, drink["idDrink"])
            for drink in drink_list
        ]
        # asyncio.gather runs all tasks concurrently, awaits all
        details = await asyncio.gather(*tasks)

    # Filter out None (failed requests), wrap in Cocktail
    return [Cocktail(d) for d in details if d]


# ============================================================================
# STAGE 4: Save & reload (file I/O + JSON)
# ============================================================================

def save_cocktails(cocktails: list[Cocktail], filepath: str = "dataset.json"):
    """Save cocktails to JSON file."""
    data = [c.to_dict() for c in cocktails]
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(cocktails)} cocktails to {filepath}")


def load_cocktails(filepath: str = "dataset.json") -> list[Cocktail]:
    """Load cocktails from JSON file."""
    if not Path(filepath).exists():
        print(f"{filepath} not found")
        return []

    with open(filepath, "r") as f:
        data = json.load(f)

    cocktails = [Cocktail.from_dict(d) for d in data]
    print(f"Loaded {len(cocktails)} cocktails from {filepath}")
    return cocktails


# ============================================================================
# STAGE 5: Analyze in Pandas (counts, grouping)
# ============================================================================

def analyze_ingredients(cocktails: list[Cocktail]):
    """Analyze ingredient frequency using Pandas.

    One row per (drink, ingredient) pair, then count and stats.
    """
    # Build a flat list of (drink_name, ingredient) tuples
    rows = []
    for cocktail in cocktails:
        for ing in cocktail.ingredients:
            rows.append({"drink": cocktail.name, "ingredient": ing})

    df = pd.DataFrame(rows)

    # Count occurrences of each ingredient
    ingredient_counts = df["ingredient"].value_counts()

    # Basic stats
    print(f"\nDataset: {len(cocktails)} drinks, {len(df)} (drink, ingredient) pairs")
    print(f"Unique ingredients: {len(ingredient_counts)}")
    print(f"Avg ingredients per drink: {df.groupby('drink').size().mean():.1f}")
    print(f"\nTop 10 ingredients:")
    print(ingredient_counts.head(10))

    return ingredient_counts


# ============================================================================
# STAGE 6: Chart it (Matplotlib)
# ============================================================================

def plot_top_ingredients(ingredient_counts, top_n: int = 10, filepath: str = "chart.png"):
    """Create a bar chart of the top N ingredients."""
    top = ingredient_counts.head(top_n)

    plt.figure(figsize=(12, 6))
    top.plot(kind="barh", color="steelblue")
    plt.xlabel("Count")
    plt.ylabel("Ingredient")
    plt.title(f"Top {top_n} Ingredients in Non-Alcoholic Cocktails")
    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    print(f"\nChart saved to {filepath}")
    plt.close()


# ============================================================================
# STAGE 7: Optional CLI (user input + error handling)
# ============================================================================

def search_cocktails(cocktails: list[Cocktail], query: str) -> list[Cocktail]:
    """Search cocktails by name (case-insensitive)."""
    query_lower = query.lower()
    return [c for c in cocktails if query_lower in c.name.lower()]


def cli_interactive(cocktails: list[Cocktail]):
    """Simple interactive search loop."""
    while True:
        query = input("\nSearch for a drink (or 'quit'): ").strip()
        if query.lower() == "quit":
            break

        results = search_cocktails(cocktails, query)
        if not results:
            print(f"No drinks found matching '{query}'")
            continue

        for drink in results[:5]:  # Show first 5
            print(f"  • {drink.name} ({drink.glass})")
            print(f"    Ingredients: {', '.join(drink.ingredients)}")


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
