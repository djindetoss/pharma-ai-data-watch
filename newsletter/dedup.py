"""Deduplication: same DOI, same (normalised) URL, or near-identical titles."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s?#&]+)", re.I)
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
             "ref", "rss", "cmpid", "fbclid", "gclid"}
_STOP = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with", "by", "at", "from", "is", "are"}


def extract_doi(item: dict) -> str | None:
    for field in ("doi", "url"):
        m = DOI_RE.search(item.get(field) or "")
        if m:
            return m.group(1).rstrip(".").lower()
    return None


def normalise_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k.lower() not in _TRACKING))
    path = parts.path.rstrip("/")
    return f"{host}{path}" + (f"?{query}" if query else "")


def normalise_title(title: str) -> str:
    t = re.sub(r"[^\w\s]", " ", (title or "").lower())
    return " ".join(w for w in t.split() if w not in _STOP)


def _richness(item: dict) -> tuple:
    """Which duplicate to keep: papers first, then longer excerpt, then earlier date."""
    return (item.get("category") == "Scientific article", len(item.get("excerpt") or ""),
            -int((item.get("date") or "0").replace("-", "") or 0))


def deduplicate(items: list[dict], title_threshold: float = 0.88) -> tuple[list[dict], int]:
    kept: list[dict] = []
    keys_doi: dict[str, int] = {}
    keys_url: dict[str, int] = {}
    titles: list[str] = []

    for it in items:
        doi, url, title = extract_doi(it), normalise_url(it.get("url", "")), normalise_title(it.get("title", ""))
        dup_idx = None
        if doi and doi in keys_doi:
            dup_idx = keys_doi[doi]
        elif url and url in keys_url:
            dup_idx = keys_url[url]
        else:
            for i, t in enumerate(titles):
                if t and title and SequenceMatcher(None, t, title).ratio() >= title_threshold:
                    dup_idx = i
                    break
        if dup_idx is None:
            kept.append(it)
            titles.append(title)
            idx = len(kept) - 1
        else:
            idx = dup_idx
            if _richness(it) > _richness(kept[idx]):
                kept[idx] = it
                titles[idx] = title
        if doi:
            keys_doi[doi] = idx
        if url:
            keys_url[url] = idx
    return kept, len(items) - len(kept)
