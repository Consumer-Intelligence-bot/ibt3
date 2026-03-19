"""
Three-tier brand name normalisation for Q1 (spontaneous awareness).

Tier 1: Exact lookup from persistent JSON (free, instant)
Tier 2: Fuzzy string matching via rapidfuzz (free, fast)
Tier 3: LLM batch matching via Anthropic API (tokens, rare)

The lookup file grows over time — new matches from Tier 2/3 are
saved back so they become Tier 1 hits on subsequent runs.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_LOOKUP_PATH = Path(__file__).resolve().parent.parent / "data" / "brand_lookup.json"

# Minimum fuzzy match score to auto-accept (0-100)
_FUZZY_AUTO_THRESHOLD = 85
# Minimum score to accept as tentative (below this → LLM)
_FUZZY_TENTATIVE_THRESHOLD = 70


def _load_lookup() -> dict[str, str | None]:
    """Load the raw→canonical brand lookup from disk."""
    if not _LOOKUP_PATH.exists():
        return {}
    try:
        data = json.loads(_LOOKUP_PATH.read_text(encoding="utf-8"))
        data.pop("_comment", None)
        return data
    except (json.JSONDecodeError, OSError):
        log.warning("Failed to load brand lookup from %s", _LOOKUP_PATH)
        return {}


def _save_lookup(lookup: dict[str, str | None]) -> None:
    """Persist the lookup to disk."""
    try:
        _LOOKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the comment
        out = {"_comment": "Maps raw Q1 typed text (lowercased) to canonical brand name. null = confirmed non-brand."}
        out.update(dict(sorted(lookup.items())))
        _LOOKUP_PATH.write_text(
            json.dumps(out, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        log.warning("Failed to save brand lookup to %s", _LOOKUP_PATH)


def _clean_raw(text: str) -> str:
    """Normalise raw typed text for matching."""
    s = str(text).strip()
    # Decode HTML entities
    s = s.replace("&amp;", "&").replace("&#39;", "'").replace("&apos;", "'")
    s = s.lower()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def _fuzzy_match(raw: str, canonical_brands: list[str]) -> tuple[str | None, int]:
    """
    Tier 2: fuzzy match against canonical brand list.
    Returns (matched_brand, score) or (None, 0).
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        log.info("rapidfuzz not installed; skipping fuzzy matching")
        return None, 0

    if not raw or not canonical_brands:
        return None, 0

    # Try token_sort_ratio (handles word reordering) and ratio (simple)
    result = process.extractOne(
        raw,
        canonical_brands,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=_FUZZY_TENTATIVE_THRESHOLD,
    )
    if result:
        return result[0], int(result[1])
    return None, 0


def _llm_batch_match(
    unmatched: list[str],
    canonical_brands: list[str],
) -> dict[str, str | None]:
    """
    Tier 3: LLM batch matching for entries that fuzzy matching couldn't resolve.
    Returns {raw_text: canonical_brand_or_None}.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("No ANTHROPIC_API_KEY; skipping LLM brand matching")
        return {}

    if not unmatched:
        return {}

    try:
        import anthropic
    except ImportError:
        return {}

    # Batch into groups of 200 to keep token usage low
    brand_list = ", ".join(canonical_brands)
    results = {}

    for i in range(0, len(unmatched), 200):
        batch = unmatched[i:i + 200]
        entries = "\n".join(f"- {raw}" for raw in batch)

        prompt = (
            f"You are matching raw typed brand names to a canonical list of UK insurance brands.\n\n"
            f"Canonical brands:\n{brand_list}\n\n"
            f"For each raw entry below, return the closest canonical brand name, or \"UNKNOWN\" "
            f"if it's not a real insurance brand (e.g. gibberish, PCW names, generic words).\n\n"
            f"Raw entries:\n{entries}\n\n"
            f"Return ONLY a JSON object mapping each raw entry to the canonical name or \"UNKNOWN\". "
            f"Example: {{\"avva\": \"Aviva\", \"xxx\": \"UNKNOWN\"}}"
        )

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # Strip markdown fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3].strip()
            parsed = json.loads(text)
            for raw, matched in parsed.items():
                if matched == "UNKNOWN" or matched is None:
                    results[raw] = None
                elif matched in canonical_brands:
                    results[raw] = matched
                else:
                    results[raw] = None
            log.info("LLM matched %d/%d entries", len(results), len(batch))
        except Exception:
            log.exception("LLM brand matching failed for batch %d", i)

    return results


def normalise_q1_brands(
    df_q1: pd.DataFrame,
    canonical_brands: list[str] | None = None,
) -> pd.DataFrame:
    """
    Normalise Q1 spontaneous awareness answers to canonical brand names.

    Parameters
    ----------
    df_q1 : DataFrame
        Q1 rows from AllOtherData with at least UniqueID and Answer columns.
    canonical_brands : list[str], optional
        Reference brand list. If None, derived from Q2 column names.

    Returns DataFrame with original columns plus:
        - RawAnswer: the original typed text
        - Brand: the normalised canonical brand name (or None for non-brands)
        - MatchTier: 'lookup', 'fuzzy', 'llm', or 'unmatched'
    """
    if df_q1.empty:
        return df_q1.assign(RawAnswer="", Brand=None, MatchTier="")

    if canonical_brands is None:
        canonical_brands = []

    lookup = _load_lookup()
    lookup_updated = False

    raw_answers = df_q1["Answer"].astype(str).str.strip()
    cleaned = raw_answers.apply(_clean_raw)

    brands = pd.Series([None] * len(df_q1), index=df_q1.index)
    tiers = pd.Series([""] * len(df_q1), index=df_q1.index)

    # Tier 1: exact lookup
    for idx, raw in cleaned.items():
        if not raw or raw in ("", "nan", "none"):
            brands[idx] = None
            tiers[idx] = "lookup"
            continue
        if raw in lookup:
            brands[idx] = lookup[raw]
            tiers[idx] = "lookup"

    # Collect unmatched for Tier 2
    unmatched_mask = tiers == ""
    unmatched_raw = cleaned[unmatched_mask].unique().tolist()
    log.info("Tier 1 lookup: %d matched, %d unmatched unique entries",
             (~unmatched_mask).sum(), len(unmatched_raw))

    # Tier 2: fuzzy matching
    fuzzy_results = {}
    still_unmatched = []

    if unmatched_raw and canonical_brands:
        for raw in unmatched_raw:
            matched, score = _fuzzy_match(raw, canonical_brands)
            if matched and score >= _FUZZY_AUTO_THRESHOLD:
                fuzzy_results[raw] = matched
                lookup[raw] = matched
                lookup_updated = True
            elif matched and score >= _FUZZY_TENTATIVE_THRESHOLD:
                fuzzy_results[raw] = matched
                lookup[raw] = matched
                lookup_updated = True
            else:
                still_unmatched.append(raw)

        # Apply fuzzy results
        for idx, raw in cleaned[unmatched_mask].items():
            if raw in fuzzy_results:
                brands[idx] = fuzzy_results[raw]
                tiers[idx] = "fuzzy"

    log.info("Tier 2 fuzzy: %d matched, %d still unmatched",
             len(fuzzy_results), len(still_unmatched))

    # Tier 3: LLM for remaining
    if still_unmatched and canonical_brands:
        llm_results = _llm_batch_match(still_unmatched, canonical_brands)
        for raw, matched in llm_results.items():
            lookup[raw] = matched
            lookup_updated = True

        # Apply LLM results
        remaining_mask = tiers == ""
        for idx, raw in cleaned[remaining_mask].items():
            if raw in llm_results:
                brands[idx] = llm_results[raw]
                tiers[idx] = "llm"

        log.info("Tier 3 LLM: %d matched", len(llm_results))

    # Mark anything still unmatched
    still_empty = tiers == ""
    tiers[still_empty] = "unmatched"

    # Save updated lookup
    if lookup_updated:
        _save_lookup(lookup)
        log.info("Brand lookup updated: %d entries", len(lookup))

    result = df_q1.copy()
    result["RawAnswer"] = raw_answers.values
    result["Brand"] = brands.values
    result["MatchTier"] = tiers.values
    return result


def get_match_stats(df_matched: pd.DataFrame) -> dict:
    """Summary statistics for brand matching quality."""
    if df_matched.empty or "MatchTier" not in df_matched.columns:
        return {}
    total = len(df_matched)
    by_tier = df_matched["MatchTier"].value_counts().to_dict()
    matched = total - by_tier.get("unmatched", 0) - df_matched["Brand"].isna().sum()
    return {
        "total_entries": total,
        "matched": int(matched),
        "match_rate": matched / total if total > 0 else 0,
        "by_tier": by_tier,
        "unique_brands_found": df_matched["Brand"].dropna().nunique(),
        "unmatched_unique": df_matched[df_matched["MatchTier"] == "unmatched"]["RawAnswer"].nunique(),
    }
