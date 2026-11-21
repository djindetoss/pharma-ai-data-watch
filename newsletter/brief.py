"""'In brief' section: many short one-line notes grouped by theme.

The featured items stay strictly within the medicines scope. The In-brief part
is broader on purpose: AI news useful to medicines regulators (health AI,
regulation and law, research practice, safety and privacy, new tools), one
line each, so the newsletter gives a complete picture of the period.

Without an LLM the note is the item title (never the abstract) and the section
is chosen from keywords; with an LLM the note is rewritten in our own words and
the model may move or drop items.
"""
from __future__ import annotations

from .scoring import count_hits

PAPERS_SECTION = "More scientific articles"


def _body(it: dict) -> str:
    return f"{it.get('title') or ''} {it.get('excerpt') or ''}"


def brief_candidate(it: dict, cfg: dict) -> dict | None:
    """Return {brief_score, brief_section} or None if the item is not suitable."""
    p, b = cfg["prefilter"], cfg["in_brief"]
    title = (it.get("title") or "").lower()
    if any(kw.lower() in title for kw in p.get("exclusions", []) + b.get("extra_exclusions", [])):
        return None
    body = _body(it)
    if count_hits(p["ai_gate"], body) == 0:
        return None

    if it.get("category") == "Scientific article":
        # papers must still be about health / medicines to be listed
        if count_hits(b["sections"]["Medicines & health"], body) == 0:
            return None
        section, hits = PAPERS_SECTION, count_hits(b["sections"]["Medicines & health"], body)
    else:
        best = [(count_hits(kws, body), -i, name) for i, (name, kws) in enumerate(b["sections"].items())]
        hits, _, section = max(best)
        if hits == 0:
            return None
        if it.get("category") == "Regulatory":
            section = "Regulation, policy & legal"

    score = min(hits, 4) + (3 if count_hits(p.get("medicines_gate", []), body) else 0)
    for name, pen in p.get("source_penalty", {}).items():
        if name.lower() in (it.get("source") or "").lower():
            score += pen / 2
            break
    return {"brief_score": score, "brief_section": section}


def select_briefs(items: list[dict], cfg: dict, exclude_ids: set[str]) -> list[dict]:
    """Best candidates (more than needed: the LLM may drop some), best first."""
    b = cfg["in_brief"]
    out = []
    for it in items:
        if it["id"] in exclude_ids:
            continue
        c = brief_candidate(it, cfg)
        if c and c["brief_score"] >= b.get("min_score", 2):
            it.update(c)
            out.append(it)
    out.sort(key=lambda it: -it["brief_score"])
    return out[: b.get("candidates", 60)]


def group(items: list[dict], cfg: dict) -> list[dict]:
    """Cap per section and overall; return [{section, items:[...]}] in config order."""
    b = cfg["in_brief"]
    order = [PAPERS_SECTION] + list(b["sections"].keys())
    buckets: dict[str, list[dict]] = {s: [] for s in order}
    total = 0
    for it in items:
        sec = it.get("brief_section")
        cap = b.get("max_papers", 12) if sec == PAPERS_SECTION else b.get("max_per_section", 8)
        if sec not in buckets or len(buckets[sec]) >= cap:
            continue
        if total >= b.get("max_total", 40):
            break
        buckets[sec].append(it)
        total += 1
    return [{"section": s, "items": [_to_brief(it) for it in buckets[s]]} for s in order if buckets[s]]


def _to_brief(it: dict) -> dict:
    return {
        "id": it["id"],
        "note": (it.get("brief_note") or it["title"]).strip(),
        "title": it["title"].strip(),
        "url": it["url"],
        "source": it.get("source", ""),
        "date": it.get("date", ""),
    }
