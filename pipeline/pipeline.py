#!/usr/bin/env python3
"""
Pharma AI & Data Watch — Automated ingestion pipeline
------------------------------------------------------
Fetches new articles from:
  - NewsAPI (free — 80,000+ sources, no credit card needed)
  - PubMed (NCBI E-utilities API — free)
  - bioRxiv (preprint API — free)
  - EMA & FDA RSS feeds (regulatory news — free)
  - General AI RSS feeds (TechCrunch, MIT Tech Review, The Verge, Nature MI — free)
  - Claude Haiku (optional — cleans up raw PubMed/bioRxiv abstracts)

Usage:
  python pipeline.py                   # fetch all sources
  python pipeline.py --dry-run         # fetch and print without writing
  python pipeline.py --source newsapi  # run one source only
  python pipeline.py --source pubmed
  python pipeline.py --source biorxiv
  python pipeline.py --source regulatory
  python pipeline.py --source ainews
  python pipeline.py --auto-approve-all # approve everything above min score
"""

import sys
import json
import hashlib
import argparse
import logging
import time
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Load .env file if present (API keys)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed yet — keys must be set in environment

from urllib.parse import quote_plus
import requests
import feedparser
from dateutil import parser as dateparser

# ── Optional sources (loaded lazily so missing keys don't crash) ──────────────
try:
    from sources.newsapi_fetcher import fetch_newsapi
    _HAS_NEWSAPI = True
except ImportError:
    _HAS_NEWSAPI = False

try:
    from sources.claude_enhancer import enhance_articles
    _HAS_CLAUDE = True
except ImportError:
    _HAS_CLAUDE = False

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"

with CONFIG_FILE.open() as f:
    CONFIG = json.load(f)

OUTPUT_JSON   = (BASE_DIR / CONFIG["output"]["articles_json"]).resolve()
DRAFTS_DIR    = BASE_DIR / CONFIG["output"]["drafts_dir"]
SEEN_IDS_FILE = BASE_DIR / CONFIG["output"]["processed_ids_file"]

DRAFTS_DIR.mkdir(exist_ok=True)
SEEN_IDS_FILE.parent.mkdir(exist_ok=True)

MAX_PER_SOURCE   = CONFIG["settings"]["max_articles_per_source"]
AUTO_THRESHOLD   = CONFIG["settings"]["auto_approve_threshold"]
MIN_SCORE        = CONFIG["settings"]["min_relevance_score"]
MAX_TOTAL        = CONFIG["settings"]["max_total_articles"]
DAYS_LOOKBACK    = CONFIG["settings"]["days_lookback"]

PHARMA_KW = [k.lower() for k in CONFIG["pharma_keywords"]]
AI_KW     = [k.lower() for k in CONFIG["ai_keywords"]]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("pipeline")

# ── Helpers ───────────────────────────────────────────────────────────────────

def article_id(url: str, title: str) -> str:
    """Stable dedup ID based on URL or title hash."""
    key = url.strip() if url and url != "#" else title.strip().lower()
    return "auto-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def load_seen_ids() -> set:
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text()))
    return set()


def save_seen_ids(seen: set):
    SEEN_IDS_FILE.write_text(json.dumps(sorted(seen), indent=2))


def load_existing_articles() -> list:
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text())
        except json.JSONDecodeError:
            log.warning("articles.json is malformed — treating as empty.")
    return []


def save_articles(articles: list):
    articles_sorted = sorted(articles, key=lambda a: a.get("date", ""), reverse=True)
    articles_trimmed = articles_sorted[:MAX_TOTAL]
    OUTPUT_JSON.write_text(json.dumps(articles_trimmed, indent=2, ensure_ascii=False))
    log.info(f"Saved {len(articles_trimmed)} articles → {OUTPUT_JSON}")


def relevance_score(text: str, article_type: str = "") -> int:
    """
    Score 0-6:
      +1 per pharma keyword found (max 3)
      +1 per AI keyword found    (max 3)
    ainews type only needs AI keywords, not pharma.
    """
    t = text.lower()
    pharma_hits = sum(1 for kw in PHARMA_KW if kw in t)
    ai_hits     = sum(1 for kw in AI_KW     if kw in t)

    if article_type == "ainews":
        return min(ai_hits, 3) * 2   # 0-6, pure AI relevance
    return min(pharma_hits, 3) + min(ai_hits, 3)


def estimate_read_time(text: str) -> str:
    words = len(re.findall(r'\w+', text or ""))
    minutes = max(1, round(words / 200))
    return f"{minutes} min"


def clean_html(raw: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    clean = re.sub(r'<[^>]+>', ' ', raw or "")
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:600]   # cap excerpt length


def iso_date(dt) -> str:
    """Return YYYY-MM-DD string from various date inputs."""
    if isinstance(dt, str):
        try:
            return dateparser.parse(dt).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")
    if hasattr(dt, 'strftime'):
        return dt.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def within_lookback(date_str: str) -> bool:
    try:
        dt = dateparser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=DAYS_LOOKBACK)
        return dt >= cutoff
    except Exception:
        return True   # if we can't parse, include it


# ── PubMed ────────────────────────────────────────────────────────────────────

def fetch_pubmed(dry_run=False) -> list:
    if not CONFIG["pubmed"]["enabled"]:
        return []

    base    = CONFIG["pubmed"]["base_url"]
    queries = CONFIG["pubmed"]["search_queries"]
    max_r   = CONFIG["pubmed"]["max_results_per_query"]
    results = []
    seen_pmids = set()

    # Date range
    cutoff = (datetime.now() - timedelta(days=DAYS_LOOKBACK)).strftime("%Y/%m/%d")

    for query in queries:
        try:
            log.info(f"PubMed search: {query!r}")
            search_url = (
                f"{base}/esearch.fcgi?db=pubmed"
                f"&term={quote_plus(query)}"
                f"&retmax={max_r}"
                f"&mindate={cutoff}"
                f"&datetype=edat"
                f"&retmode=json"
            )
            r = requests.get(search_url, timeout=15)
            r.raise_for_status()
            pmids = r.json().get("esearchresult", {}).get("idlist", [])

            for pmid in pmids:
                if pmid in seen_pmids:
                    continue
                seen_pmids.add(pmid)
                time.sleep(0.35)   # NCBI rate limit: ~3 req/s

                summary_url = (
                    f"{base}/esummary.fcgi?db=pubmed"
                    f"&id={pmid}&retmode=json"
                )
                sr = requests.get(summary_url, timeout=15)
                sr.raise_for_status()
                doc = sr.json().get("result", {}).get(pmid, {})
                if not doc:
                    continue

                title   = doc.get("title", "").rstrip(".")
                source  = doc.get("source", "PubMed")
                pubdate = doc.get("pubdate", "")
                authors = doc.get("authors", [])
                url     = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                # Fetch abstract
                abstract = ""
                try:
                    fetch_url = f"{base}/efetch.fcgi?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
                    ar = requests.get(fetch_url, timeout=15)
                    abstract = ar.text[:600]
                    time.sleep(0.35)
                except Exception:
                    pass

                mesh = [m.get("name", "") for m in doc.get("meshheadinglist", [])]
                tags = list({t for t in mesh if t})[: 5] or ["Pharma AI", "Drug discovery"]

                score = relevance_score(title + " " + abstract, "paper")
                if score < MIN_SCORE:
                    continue

                results.append({
                    "id": article_id(url, title),
                    "type": "paper",
                    "title": title,
                    "excerpt": clean_html(abstract) or "See full abstract on PubMed.",
                    "source": source,
                    "date": iso_date(pubdate),
                    "tags": tags,
                    "featured": False,
                    "readTime": estimate_read_time(abstract),
                    "url": url,
                    "badge": "Open Access" if doc.get("fulljournalname", "").lower() in [
                        "plos one", "nature communications", "scientific reports",
                        "bmc bioinformatics", "journal of cheminformatics"
                    ] else "PubMed",
                    "_score": score,
                    "_auto_approve": score >= AUTO_THRESHOLD,
                    "_source": "pubmed"
                })

            time.sleep(1)

        except requests.RequestException as e:
            log.warning(f"PubMed request failed for query {query!r}: {e}")

    log.info(f"PubMed: {len(results)} articles fetched")
    return results[:MAX_PER_SOURCE]


# ── bioRxiv ───────────────────────────────────────────────────────────────────

def fetch_biorxiv(dry_run=False) -> list:
    if not CONFIG["biorxiv"]["enabled"]:
        return []

    base   = CONFIG["biorxiv"]["base_url"]
    server = CONFIG["biorxiv"]["server"]
    results = []

    start_date = (datetime.now() - timedelta(days=DAYS_LOOKBACK)).strftime("%Y-%m-%d")
    end_date   = datetime.now().strftime("%Y-%m-%d")

    try:
        log.info(f"bioRxiv: fetching {start_date} → {end_date}")
        url = f"{base}/{server}/{start_date}/{end_date}/0/json"
        r   = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        papers = data.get("collection", [])

        for p in papers[:MAX_PER_SOURCE * 2]:
            title    = p.get("title", "")
            abstract = p.get("abstract", "")
            doi      = p.get("doi", "")
            biorxiv_url = f"https://doi.org/{doi}" if doi else "#"
            date     = p.get("date", "")
            category = p.get("category", "")
            authors  = p.get("authors", "")

            score = relevance_score(title + " " + abstract, "paper")
            if score < MIN_SCORE:
                continue

            tags = [category.title()] if category else ["Preprint"]
            tags += ["bioRxiv"]

            results.append({
                "id": article_id(biorxiv_url, title),
                "type": "paper",
                "title": title.rstrip("."),
                "excerpt": clean_html(abstract),
                "source": "bioRxiv",
                "date": iso_date(date),
                "tags": tags[:4],
                "featured": False,
                "readTime": estimate_read_time(abstract),
                "url": biorxiv_url,
                "badge": "Preprint",
                "_score": score,
                "_auto_approve": score >= AUTO_THRESHOLD,
                "_source": "biorxiv"
            })

        results = results[:MAX_PER_SOURCE]
        log.info(f"bioRxiv: {len(results)} relevant articles")

    except requests.RequestException as e:
        log.warning(f"bioRxiv request failed: {e}")

    return results


# ── RSS generic fetcher ───────────────────────────────────────────────────────

def fetch_rss_feed(feed_cfg: dict, article_type: str, require_pharma: bool) -> list:
    url    = feed_cfg["url"]
    name   = feed_cfg["name"]
    badge  = feed_cfg.get("badge", "")
    auto   = feed_cfg.get("auto_approve", False)
    results = []

    try:
        log.info(f"RSS [{name}]: {url}")
        parsed = feedparser.parse(url)

        if parsed.bozo and not parsed.entries:
            log.warning(f"RSS [{name}]: feed parse error — {parsed.bozo_exception}")
            return []

        for entry in parsed.entries[:MAX_PER_SOURCE]:
            title   = entry.get("title", "").strip()
            summary = clean_html(entry.get("summary", entry.get("description", "")))
            link    = entry.get("link", "#")
            pub     = entry.get("published", entry.get("updated", ""))

            if not title:
                continue

            score = relevance_score(title + " " + summary, article_type)

            # For pharma news: must have some pharma or AI relevance
            if require_pharma and score < MIN_SCORE:
                continue

            # For AI news: must have at least one AI keyword
            if article_type == "ainews" and score < 2:
                continue

            # Extract tags from entry categories
            tags = [
                t.get("term", "").strip()
                for t in entry.get("tags", [])
                if t.get("term", "").strip()
            ][:4] or [name]

            results.append({
                "id": article_id(link, title),
                "type": article_type,
                "title": title,
                "excerpt": summary or "Read the full article at the source.",
                "source": name,
                "date": iso_date(pub),
                "tags": tags,
                "featured": False,
                "readTime": estimate_read_time(summary),
                "url": link,
                "badge": badge,
                "_score": score,
                "_auto_approve": auto or score >= AUTO_THRESHOLD,
                "_source": f"rss:{name}"
            })

    except Exception as e:
        log.warning(f"RSS [{name}]: failed — {e}")

    return results[:MAX_PER_SOURCE]


def fetch_regulatory_rss(dry_run=False) -> list:
    if not CONFIG["rss_sources"]["enabled"]:
        return []
    results = []
    for feed in CONFIG["rss_sources"]["feeds"]:
        results += fetch_rss_feed(feed, feed["type"], require_pharma=True)
    return results


def fetch_ai_news_rss(dry_run=False) -> list:
    if not CONFIG["ai_news_sources"]["enabled"]:
        return []
    results = []
    for feed in CONFIG["ai_news_sources"]["feeds"]:
        results += fetch_rss_feed(feed, "ainews", require_pharma=False)
    return results


# ── Deduplication & merge ─────────────────────────────────────────────────────

def merge_and_deduplicate(
    existing: list,
    new_items: list,
    seen_ids: set,
    auto_approve_all: bool = False
) -> tuple[list, list, set]:
    """
    Returns (updated_approved, drafts, updated_seen_ids).
    - auto_approve items go straight into approved list
    - others go to drafts for human review
    """
    existing_ids = {a["id"] for a in existing}
    approved  = list(existing)
    drafts    = []

    for item in new_items:
        aid = item["id"]
        if aid in seen_ids or aid in existing_ids:
            continue   # already processed

        seen_ids.add(aid)

        if auto_approve_all or item.get("_auto_approve", False):
            # Strip internal metadata before saving
            clean = {k: v for k, v in item.items() if not k.startswith("_")}
            approved.append(clean)
            log.info(f"  ✓ Auto-approved [{item['_source']}]: {item['title'][:70]}")
        else:
            drafts.append(item)
            log.info(f"  ○ Draft [{item['_source']}]: {item['title'][:70]}")

    return approved, drafts, seen_ids


def save_drafts(drafts: list):
    if not drafts:
        return
    today     = datetime.now().strftime("%Y-%m-%d")
    draft_file = DRAFTS_DIR / f"drafts_{today}.json"

    # Merge with any existing drafts from today
    existing = []
    if draft_file.exists():
        try:
            existing = json.loads(draft_file.read_text())
        except Exception:
            pass

    existing_ids = {d["id"] for d in existing}
    merged = existing + [d for d in drafts if d["id"] not in existing_ids]
    draft_file.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    log.info(f"Saved {len(drafts)} new drafts → {draft_file}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pharma AI & Data Watch — ingestion pipeline")
    parser.add_argument("--dry-run",          action="store_true",  help="Fetch but do not write anything")
    parser.add_argument("--auto-approve-all", action="store_true",  help="Auto-approve all items above min score")
    parser.add_argument("--source", default="all",
        choices=["newsapi", "pubmed", "biorxiv", "regulatory", "ainews", "all"])
    args = parser.parse_args()

    log.info("═" * 60)
    log.info("Pharma AI & Data Watch — ingestion pipeline starting")
    log.info(f"  Source     : {args.source}")
    log.info(f"  Dry run    : {args.dry_run}")
    log.info(f"  Lookback   : {DAYS_LOOKBACK} days")
    log.info("═" * 60)

    # Load state
    existing  = load_existing_articles()
    seen_ids  = load_seen_ids()
    log.info(f"Existing articles: {len(existing)} | Already seen IDs: {len(seen_ids)}")

    # ── Fetch from all sources ────────────────────────────────────────────────
    new_items = []

    # 1. NewsAPI — broad news from 80,000+ sources (free, no credit card)
    if args.source in ("newsapi", "all") and _HAS_NEWSAPI and CONFIG.get("newsapi", {}).get("enabled"):
        new_items += fetch_newsapi(CONFIG, dry_run=args.dry_run)

    # 2. PubMed — peer-reviewed papers
    if args.source in ("pubmed", "all"):
        new_items += fetch_pubmed(dry_run=args.dry_run)

    # 3. bioRxiv — preprints
    if args.source in ("biorxiv", "all"):
        new_items += fetch_biorxiv(dry_run=args.dry_run)

    # 4. EMA / FDA RSS — regulatory news
    if args.source in ("regulatory", "all"):
        new_items += fetch_regulatory_rss(dry_run=args.dry_run)

    # 5. AI news RSS
    if args.source in ("ainews", "all"):
        new_items += fetch_ai_news_rss(dry_run=args.dry_run)

    log.info(f"Total fetched: {len(new_items)} items across all sources")

    # ── Optional: Claude excerpt enhancement ─────────────────────────────────
    if _HAS_CLAUDE and CONFIG.get("claude_enhancer", {}).get("enabled") and not args.dry_run:
        max_e = CONFIG["claude_enhancer"].get("max_articles_to_enhance", 20)
        new_items = enhance_articles(new_items, max_enhance=max_e)

    if args.dry_run:
        log.info("Dry run — no files written.")
        for item in new_items:
            status = "AUTO" if item.get("_auto_approve") else "DRAFT"
            log.info(f"  [{status}] score={item.get('_score',0)} [{item['type']}] {item['title'][:80]}")
        return

    # ── Merge, deduplicate, persist ───────────────────────────────────────────
    approved, drafts, seen_ids = merge_and_deduplicate(
        existing, new_items, seen_ids, auto_approve_all=args.auto_approve_all
    )

    save_articles(approved)
    save_drafts(drafts)
    save_seen_ids(seen_ids)

    n_new = len(approved) - len(existing)
    log.info("═" * 60)
    log.info(f"  New auto-approved : {n_new}")
    log.info(f"  Sent to drafts    : {len(drafts)}")
    log.info(f"  Total in portal   : {len(approved)}")
    if drafts:
        log.info(f"  → Run `python review.py` to review {len(drafts)} pending draft(s)")
    log.info("═" * 60)


if __name__ == "__main__":
    main()
