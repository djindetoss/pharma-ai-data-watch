"""Collect candidate items for an edition from the daily pipeline output.

portal/js/articles.json is a rolling file (older items are trimmed), so when
`source.use_git_history` is on we also read the versions of that file
committed during the window and take the union. This needs a full git
history (actions/checkout with fetch-depth: 0).
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from . import REPO_ROOT

log = logging.getLogger(__name__)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True,
                          capture_output=True, text=True, timeout=120).stdout


def _history_versions(rel_path: str, since: date) -> list[list[dict]]:
    """One version of the file per day since `since` (last commit of each day)."""
    try:
        out = _git("log", f"--since={since.isoformat()}", "--format=%H %ci", "--", rel_path)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        log.warning("git history unavailable (%s) – using current file only", e)
        return []
    per_day: dict[str, str] = {}
    for line in out.splitlines():          # newest first → keep first seen per day
        sha, day = line.split()[:2]
        per_day.setdefault(day, sha)
    versions = []
    for sha in per_day.values():
        try:
            versions.append(json.loads(_git("show", f"{sha}:{rel_path}")))
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            log.warning("skipping %s: %s", sha[:8], e)
    return versions


# Papers reaching the pipeline through NewsAPI/RSS are typed "news"/"ainews";
# a scholarly URL is a more reliable signal.
SCHOLARLY_URL = re.compile(
    r"doi\.org/|journals\.plos\.org|nature\.com/articles|medrxiv\.org|biorxiv\.org|arxiv\.org/abs|"
    r"frontiersin\.org|sciencedirect\.com|link\.springer\.com|onlinelibrary\.wiley\.com|bmj\.com|"
    r"thelancet\.com|jamanetwork\.com|mdpi\.com|pubmed\.ncbi|ncbi\.nlm\.nih\.gov/pmc|academic\.oup\.com",
    re.I)


def classify(item: dict) -> str:
    """Map pipeline types to newsletter categories."""
    t = item.get("type")
    if t == "paper" or SCHOLARLY_URL.search(item.get("url") or ""):
        return "Scientific article"
    # badges set by the curated regulatory/policy RSS feeds (NewsAPI items may
    # carry topic=regulatory but are generic press, so topic is not used)
    if item.get("badge") in ("Regulatory", "Policy", "AI Policy"):
        return "Regulatory"
    return "News"


def collect(cfg: dict, end: date, window_days: int | None = None) -> tuple[list[dict], dict]:
    """Return (items in window, stats)."""
    window_days = window_days or cfg["schedule"]["window_days"]
    start = end - timedelta(days=window_days)
    rel = cfg["source"]["articles_json"]
    current = json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))

    versions = [current]
    if cfg["source"].get("use_git_history", True):
        versions += _history_versions(rel, start - timedelta(days=1))

    # The current file wins. From older versions we only take items that are
    # older than the oldest item still in the current file, i.e. items that
    # were trimmed for age. Newer items missing from the current file were
    # removed on purpose (off-topic clean-ups) and must not come back.
    by_id: dict[str, dict] = {it["id"]: it for it in current}
    oldest_current = min((it.get("date", "") for it in current), default="")
    for version in versions[1:]:
        for it in version:
            if it.get("date", "") < oldest_current:
                by_id.setdefault(it["id"], it)

    excluded_types = set(cfg["source"].get("exclude_types", []))
    items = []
    for it in by_id.values():
        d = it.get("date", "")
        if not (start.isoformat() < d <= end.isoformat()):
            continue
        if it.get("type") in excluded_types:
            continue
        it = dict(it)
        it["category"] = classify(it)
        items.append(it)

    stats = {
        "period_start": (start + timedelta(days=1)).isoformat(),
        "period_end": end.isoformat(),
        "versions_read": len(versions),
        "unique_items_seen": len(by_id),
        "collected": len(items),
    }
    log.info("Collected %d items in window %s → %s (%d file versions)",
             len(items), stats["period_start"], end, len(versions))
    return items, stats
