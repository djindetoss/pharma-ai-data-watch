"""Keyword pre-filter: weighted themes, AI/data gate, exclusions, source bonus.

Produces `prefilter_score` on a 0-10 scale plus the matched themes, which are
also used as fallback tags when no LLM is available.
"""
from __future__ import annotations

import re
from functools import lru_cache

# theme key → tag in the controlled vocabulary (fallback when no LLM)
THEME_TAGS = {
    "regulatory_assessment": "Regulatory assessment",
    "regulatory_guidance": "Guidelines & policy",
    "portability_sharing": "Portability & MLOps",
    "genai_regulatory_docs": "LLM / GenAI",
    "data_governance_validation": "Data governance",
}


@lru_cache(maxsize=4096)
def _pattern(keyword: str) -> re.Pattern:
    # Short all-caps acronyms (AI, EMA, PK…) are matched case-sensitively to
    # avoid hits such as "said" → "ai" or "pk" inside URLs.
    flags = 0 if (keyword.isupper() and len(keyword) <= 5) else re.I
    return re.compile(r"(?<![\w-])" + re.escape(keyword) + r"(?![\w-])", flags)


def count_hits(keywords: list[str], text: str) -> int:
    return sum(1 for kw in keywords if _pattern(kw).search(text))


def score_item(item: dict, cfg: dict) -> dict:
    """Return a dict with prefilter_score (0-10), themes, excluded_reason."""
    p = cfg["prefilter"]
    title = item.get("title") or ""
    body = f"{title} {item.get('excerpt') or ''}"
    source = item.get("source") or ""

    for kw in p.get("exclusions", []):
        if kw.lower() in title.lower():
            return {"prefilter_score": 0.0, "themes": [], "excluded_reason": f"exclusion '{kw}'"}

    if count_hits(p["ai_gate"], body) == 0:
        return {"prefilter_score": 0.0, "themes": [], "excluded_reason": "no AI/data signal"}

    raw, themes = 0.0, []
    for key, theme in p["themes"].items():
        hits = count_hits(theme["keywords"], body) + (p.get("title_multiplier", 2) - 1) * count_hits(theme["keywords"], title)
        if hits:
            raw += theme["weight"] * min(hits, p.get("hits_cap", 3))
            themes.append((key, hits))
    for name, bonus in p.get("source_bonus", {}).items():
        if name.lower() in source.lower():
            raw += bonus
            break
    for name, pen in p.get("source_penalty", {}).items():
        if name.lower() in source.lower():
            raw += pen
            break

    score10 = max(0.0, min(10.0, raw / p["normaliser"] * 10))
    themes.sort(key=lambda t: -t[1])
    return {"prefilter_score": round(score10, 2), "themes": [k for k, _ in themes], "excluded_reason": None}


def prefilter(items: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """Score all items; return those above `shortlist_floor` sorted desc, plus stats."""
    min_score = cfg["selection"]["shortlist_floor"]
    kept, reasons = [], {"exclusion": 0, "no AI/data signal": 0, "below threshold": 0}
    for it in items:
        s = score_item(it, cfg)
        it.update(s)
        it["fallback_tags"] = [THEME_TAGS[k] for k in s["themes"][:3]]
        if s["excluded_reason"]:
            reasons["exclusion" if s["excluded_reason"].startswith("exclusion") else s["excluded_reason"]] += 1
        elif s["prefilter_score"] < min_score:
            reasons["below threshold"] += 1
        else:
            kept.append(it)
    kept.sort(key=lambda x: -x["prefilter_score"])
    return kept, reasons
