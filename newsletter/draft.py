"""Build the editable draft (newsletter/drafts/YYYY-MM-DD.yaml).

collect → deduplicate → keyword pre-filter → (optional) LLM scoring → quota
selection → (optional) LLM summaries → YAML draft.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import yaml

from . import DRAFTS_DIR, EDITIONS_INDEX, llm
from .collect import collect
from .dedup import deduplicate
from .scoring import prefilter

log = logging.getLogger(__name__)

EDITORIAL_PLACEHOLDER = (
    "Welcome to this edition of the IncreaseNET AI Community newsletter. "
    "[EDIT ME: two or three sentences from the AI working group – upcoming meetings, "
    "a theme of the period, a call for contributions.]"
)
SUMMARY_PLACEHOLDER = "TODO: write a 2-3 sentence plain-language summary in our own words."
COMMENT_PLACEHOLDER = "TODO: add a short personal comment (1-3 sentences): what is notable, a caveat, a takeaway."
WHY_PLACEHOLDER = "TODO: explain the concrete interest for an NCA."

ITEM_FIELDS = ("id", "title", "url", "source", "date", "type", "tags", "summary",
               "comment", "why_it_matters", "score", "score_reason")


def next_edition_number() -> int:
    if EDITIONS_INDEX.exists():
        return len(json.loads(EDITIONS_INDEX.read_text(encoding="utf-8"))) + 1
    return 1


def _final_score(it: dict, use_llm: bool) -> float:
    return float(it["llm_score"]) if use_llm and it.get("llm_score") is not None else it["prefilter_score"]


def _to_draft_item(it: dict, use_llm: bool) -> dict:
    out = {
        "id": it["id"],
        "title": it["title"].strip(),
        "url": it["url"],
        "source": it.get("source", ""),
        "date": it.get("date", ""),
        "type": it["category"],
        "tags": it.get("tags_llm") or it.get("fallback_tags") or [],
        "summary": it.get("summary") or SUMMARY_PLACEHOLDER,
        "comment": it.get("comment") or COMMENT_PLACEHOLDER,
        "why_it_matters": it.get("why_it_matters") or WHY_PLACEHOLDER,
        "score": round(_final_score(it, use_llm), 1),
        "score_reason": it.get("llm_reason") or f"keyword pre-filter (themes: {', '.join(it.get('themes', [])) or '–'})",
    }
    return {k: out[k] for k in ITEM_FIELDS}


def select(shortlist: list[dict], cfg: dict, use_llm: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """Apply threshold + quotas. Returns (papers, news, runners_up), best first."""
    sel = cfg["selection"]
    threshold = sel["min_llm_score"] if use_llm else sel["min_prefilter_score"]
    ranked = sorted(shortlist, key=lambda it: -_final_score(it, use_llm))
    papers = [it for it in ranked if it["category"] == "Scientific article"]
    news = [it for it in ranked if it["category"] != "Scientific article"]
    keep_p = [it for it in papers if _final_score(it, use_llm) >= threshold][: sel["papers"]["max"]]
    keep_n = [it for it in news if _final_score(it, use_llm) >= threshold][: sel["news"]["max"]]
    kept_ids = {it["id"] for it in keep_p + keep_n}
    runners = [it for it in ranked if it["id"] not in kept_ids][: sel.get("runners_up", 6)]
    for label, got, quota in (("papers", keep_p, sel["papers"]), ("news", keep_n, sel["news"])):
        if len(got) < quota["min"]:
            log.warning("Only %d %s above threshold %.1f (target min %d) – keeping the edition short "
                        "rather than adding weak items.", len(got), label, threshold, quota["min"])
    return keep_p, keep_n, runners


def build_draft(cfg: dict, end: date, window_days: int | None = None, no_llm: bool = False) -> tuple[dict, dict]:
    items, stats = collect(cfg, end, window_days)
    items, n_dupes = deduplicate(items, cfg["selection"]["title_similarity"])
    stats["duplicates_removed"] = n_dupes
    stats["after_dedup"] = len(items)

    candidates, reasons = prefilter(items, cfg)
    stats["prefilter_dropped"] = reasons
    stats["prefilter_passed"] = len(candidates)
    shortlist = candidates[: cfg["selection"]["shortlist_size"]]
    stats["shortlist"] = len(shortlist)

    use_llm = (not no_llm) and llm.available(cfg)
    stats["llm_used"] = use_llm
    if use_llm:
        stats["llm_model"] = cfg["llm"]["model"]
        scores = llm.score_items(shortlist, cfg)
        for it in shortlist:
            it["llm_score"], it["llm_reason"] = scores.get(it["id"], (0, "not scored"))

    papers, news, runners = select(shortlist, cfg, use_llm)
    retained = papers + news
    if use_llm and retained:
        texts = llm.write_items(retained, cfg)
        for it in retained:
            t = texts.get(it["id"], {})
            it["summary"], it["comment"] = t.get("summary"), t.get("comment")
            it["why_it_matters"], it["tags_llm"] = t.get("why_it_matters"), t.get("tags")

    # Highlight = best retained item overall; it is shown once, in its own section.
    # Ties go to regulatory items (most directly actionable for NCAs).
    highlight = max(retained, key=lambda it: (_final_score(it, use_llm), it["category"] == "Regulatory")) if retained else None
    if highlight:
        papers = [it for it in papers if it is not highlight]
        news = [it for it in news if it is not highlight]

    sel = cfg["selection"]
    stats["thresholds"] = {
        "mode": "LLM" if use_llm else "keyword pre-filter only",
        "shortlist_floor": sel["shortlist_floor"],
        "final_threshold": sel["min_llm_score"] if use_llm else sel["min_prefilter_score"],
        "papers_quota": sel["papers"], "news_quota": sel["news"],
    }
    stats["retained"] = {"total": len(retained), "papers": len([i for i in retained if i["category"] == "Scientific article"]),
                         "news_regulatory": len([i for i in retained if i["category"] != "Scientific article"])}

    draft = {
        "edition_date": end.isoformat(),
        "edition_number": next_edition_number(),
        "period": {"start": stats["period_start"], "end": stats["period_end"]},
        "editorial": EDITORIAL_PLACEHOLDER,
        "highlight": _to_draft_item(highlight, use_llm) if highlight else None,
        "scientific_articles": [_to_draft_item(it, use_llm) for it in papers],
        "news": [_to_draft_item(it, use_llm) for it in news],
        "runners_up": [_to_draft_item(it, use_llm) for it in runners],
        "stats": stats,
    }
    return draft, stats


DRAFT_HEADER = """\
# ─────────────────────────────────────────────────────────────────────────────
# IncreaseNET AI Community – Newsletter DRAFT
#
# Edit freely, then re-render with:  python -m newsletter render {path}
#  - remove an item: delete its block (from "- id:" to the next "- id:")
#  - reorder: move blocks; the order here is the order in the newsletter
#  - promote a runner-up: move its block into scientific_articles or news
#  - highlight: replace the block, or set it to null for no highlight
#  - edit editorial / summary / comment / why_it_matters / tags as you like
#  - "runners_up" and "stats" are never rendered
#  - lines still containing "TODO" or "EDIT ME" are flagged when rendering
# ─────────────────────────────────────────────────────────────────────────────
"""


def save_draft(draft: dict) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFTS_DIR / f"{draft['edition_date']}.yaml"
    body = yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(DRAFT_HEADER.format(path=path.relative_to(DRAFTS_DIR.parent.parent)) + body, encoding="utf-8")
    return path
