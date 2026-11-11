"""Build the editable draft (newsletter/drafts/YYYY-MM-DD.yaml).

collect → deduplicate → keyword pre-filter → (optional) LLM scoring → quota
selection of the featured items → (optional) LLM summaries and comments →
In-brief notes → introduction → YAML draft.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import yaml

from . import DRAFTS_DIR, EDITIONS_INDEX, links, llm
from .brief import PAPERS_SECTION, group, select_briefs
from .collect import collect
from .dedup import deduplicate
from .render import period_label
from .scoring import prefilter

log = logging.getLogger(__name__)

SUMMARY_PLACEHOLDER = "TODO: write a 2-3 sentence plain-language summary in our own words."
COMMENT_PLACEHOLDER = "TODO: add a short personal comment (1-3 sentences): what is notable, a caveat, a takeaway."
WHY_PLACEHOLDER = "TODO: explain the concrete interest for an NCA."

ITEM_FIELDS = ("id", "title", "url", "source", "date", "type", "tags", "summary",
               "comment", "why_it_matters", "score", "score_reason", "below_threshold")
# (verify_edition may add "link_check" to an item whose link is broken)


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
        "below_threshold": bool(it.get("below_threshold")),
    }
    if not out["below_threshold"]:
        del out["below_threshold"]
    return {k: out[k] for k in ITEM_FIELDS if k in out}


def select(shortlist: list[dict], cfg: dict, use_llm: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """Apply threshold + quotas. Returns (papers, news, runners_up), best first.

    With selection.fill_to_min, a thin period is topped up to the minimum with the
    best remaining shortlisted items, flagged `below_threshold` for the reviewer.
    """
    sel = cfg["selection"]
    threshold = sel["min_llm_score"] if use_llm else sel["min_prefilter_score"]
    ranked = sorted(shortlist, key=lambda it: -_final_score(it, use_llm))
    chosen = []
    for label, is_paper in (("papers", True), ("news", False)):
        quota = sel[label]
        pool = [it for it in ranked if (it["category"] == "Scientific article") == is_paper]
        keep = [it for it in pool if _final_score(it, use_llm) >= threshold][: quota["max"]]
        if len(keep) < quota["min"]:
            floor = sel.get("fill_floor", 0)
            extra = [it for it in pool if it not in keep and _final_score(it, use_llm) >= floor][: quota["min"] - len(keep)]
            if sel.get("fill_to_min", False):
                for it in extra:
                    it["below_threshold"] = True
                keep += extra
                log.info("Topped up %s with %d item(s) below threshold %.1f.", label, len(extra), threshold)
            else:
                log.warning("Only %d %s above threshold %.1f (target min %d).", len(keep), label, threshold, quota["min"])
        chosen.append(keep)
    keep_p, keep_n = chosen
    kept_ids = {it["id"] for it in keep_p + keep_n}
    runners = [it for it in ranked if it["id"] not in kept_ids][: sel.get("runners_up", 6)]
    return keep_p, keep_n, runners


def auto_intro(number: int, period: str, highlight: dict | None, papers: list[dict],
               news: list[dict], briefs: list[dict]) -> str:
    """Plain, factual introduction used when no LLM is available."""
    n_brief = sum(len(g["items"]) for g in briefs)
    parts = [f"Welcome to edition #{number} of the IncreaseNET AI Community newsletter, "
             f"covering {period}."]
    featured = len(papers) + len(news) + (1 if highlight else 0)
    parts.append(f"This time you will find {featured} featured items – "
                 f"{len(papers) + (1 if highlight and highlight['type'] == 'Scientific article' else 0)} scientific articles "
                 f"and {len(news) + (1 if highlight and highlight['type'] != 'Scientific article' else 0)} news and "
                 f"regulatory updates, each with a short comment – followed by {n_brief} one-line notes "
                 f"in the In-brief section.")
    if highlight:
        parts.append(f"The highlight of the period: {highlight['title'].rstrip('.')}.")
    if papers:
        parts.append(f"On the science side, do not miss: {papers[0]['title'].rstrip('.')}.")
    return " ".join(parts)


def digest(highlight: dict | None, papers: list[dict], news: list[dict], briefs: list[dict]) -> str:
    """Compact list of the edition's contents, given to the LLM to write the intro."""
    lines = []
    if highlight:
        lines.append(f"HIGHLIGHT [{highlight['type']}] {highlight['title']} – {highlight['summary']}")
    for it in papers:
        lines.append(f"SCIENTIFIC ARTICLE: {it['title']} – {it['summary']}")
    for it in news:
        lines.append(f"NEWS [{it['type']}]: {it['title']} – {it['summary']}")
    for g in briefs:
        for b in g["items"]:
            lines.append(f"IN BRIEF ({g['section']}): {b['note']}")
    return "\n".join(lines)


def build_draft(cfg: dict, end: date, window_days: int | None = None, no_llm: bool = False,
                check_links: bool = True) -> tuple[dict, dict]:
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

    # In brief: everything else worth a line (broader scope), grouped by theme.
    candidates = select_briefs(items, cfg, exclude_ids={it["id"] for it in retained})
    stats["in_brief_candidates"] = len(candidates)
    if use_llm and candidates:
        sections = [PAPERS_SECTION] + list(cfg["in_brief"]["sections"].keys())
        notes = llm.write_briefs(candidates, cfg, sections)
        kept = []
        for it in candidates:
            n = notes.get(it["id"])
            if n and n["keep"]:
                it["brief_section"], it["brief_note"] = n["section"], n["note"]
                kept.append(it)
        candidates = kept
    briefs = group(candidates, cfg)

    sel = cfg["selection"]
    stats["thresholds"] = {
        "mode": "LLM" if use_llm else "keyword pre-filter only",
        "shortlist_floor": sel["shortlist_floor"],
        "final_threshold": sel["min_llm_score"] if use_llm else sel["min_prefilter_score"],
        "papers_quota": sel["papers"], "news_quota": sel["news"],
    }
    stats["retained"] = {"total": len(retained), "papers": len([i for i in retained if i["category"] == "Scientific article"]),
                         "news_regulatory": len([i for i in retained if i["category"] != "Scientific article"]),
                         "below_threshold": len([i for i in retained if i.get("below_threshold")]),
                         "in_brief": sum(len(g["items"]) for g in briefs)}

    number = next_edition_number()
    h_item = _to_draft_item(highlight, use_llm) if highlight else None
    p_items = [_to_draft_item(it, use_llm) for it in papers]
    n_items = [_to_draft_item(it, use_llm) for it in news]
    editorial = None
    if use_llm and retained:
        try:
            editorial = llm.write_intro(digest(h_item, p_items, n_items, briefs), cfg)
        except Exception as exc:  # the intro is not worth failing the whole draft
            log.warning("Introduction not written by the LLM (%s); using the automatic one.", exc)
    if not editorial:
        editorial = auto_intro(number, period_label({"start": stats["period_start"], "end": stats["period_end"]}),
                               h_item, p_items, n_items, briefs)

    draft = {
        "edition_date": end.isoformat(),
        "edition_number": number,
        "period": {"start": stats["period_start"], "end": stats["period_end"]},
        "editorial": editorial,
        "highlight": h_item,
        "scientific_articles": p_items,
        "news": n_items,
        "in_brief": briefs,
        "runners_up": [_to_draft_item(it, use_llm) for it in runners],
        "stats": stats,
    }
    if check_links:
        stats["links"] = links.verify_edition(draft)
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
#  - in_brief: one line per item ("note"); delete, edit or move lines freely
#  - items with "below_threshold: true" were added to reach the minimum: check them
#  - every link was opened and replaced by its final address; "link_check: BROKEN"
#    marks a dead link (validation is refused until it is fixed or the item removed)
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
