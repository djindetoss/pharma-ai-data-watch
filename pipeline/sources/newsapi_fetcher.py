"""
NewsAPI — free news aggregation source
---------------------------------------
Uses the NewsAPI.org free developer tier (1,000 requests/day)
to search 80,000+ news sources for pharma AI and general AI news.

Free tier: https://newsapi.org/register
- No credit card required
- Up to 1,000 requests/day
- Articles from the past 30 days

API docs: https://newsapi.org/docs/endpoints/everything
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta

import requests
from dateutil import parser as dateparser

log = logging.getLogger("pipeline.newsapi")

NEWSAPI_BASE = "https://newsapi.org/v2/everything"

# ── Search queries ─────────────────────────────────────────────────────────────
# Each query targets a specific content niche.
# Results are mapped to a portal article type.

SEARCH_QUERIES = [
    {
        "topic":  "AI in drug discovery and pharmaceutical R&D",
        "q":      "(\"artificial intelligence\" OR \"machine learning\") AND (\"drug discovery\" OR \"drug development\" OR \"pharmaceutical\" OR \"biopharma\")",
        "type":   "news",
        "badge":  "Pharma AI",
        "sources": None,   # search all sources
    },
    {
        "topic":  "EMA, FDA and regulatory AI guidance",
        "q":      "(EMA OR FDA OR \"regulatory agency\") AND (\"artificial intelligence\" OR \"machine learning\") AND (drug OR medicine OR pharmaceutical)",
        "type":   "news",
        "badge":  "Regulatory",
        "sources": None,
    },
    {
        "topic":  "Clinical trials AI and real-world evidence",
        "q":      "(\"clinical trial\" OR \"real-world evidence\" OR pharmacovigilance) AND (\"artificial intelligence\" OR \"machine learning\" OR AI)",
        "type":   "news",
        "badge":  "Clinical AI",
        "sources": None,
    },
    {
        "topic":  "EHDS, health data governance and IDMP",
        "q":      "(\"European Health Data Space\" OR EHDS OR IDMP OR FHIR) AND (health OR medicine OR pharmaceutical)",
        "type":   "news",
        "badge":  "Policy",
        "sources": None,
    },
    {
        "topic":  "Pharma AI conferences, webinars and seminars",
        "q":      "(webinar OR conference OR seminar OR congress OR symposium OR workshop) AND (\"artificial intelligence\" OR \"machine learning\") AND (pharmaceutical OR regulatory OR \"drug development\" OR \"clinical trial\" OR healthcare)",
        "type":   "seminar",   # will be further refined to webinar/seminar by event detection
        "badge":  "Event",
        "sources": None,
    },
    {
        "topic":  "General AI breakthroughs for ainews tab",
        "q":      "(\"large language model\" OR \"foundation model\" OR \"generative AI\" OR GPT OR Claude OR Gemini OR \"EU AI Act\") AND (health OR science OR regulation OR biomedical)",
        "type":   "ainews",
        "badge":  "Tech",
        "sources": "techcrunch.com,thenextweb.com,wired.com,theverge.com,nature.com",
    },
]

# Words that signal a webinar (online event) vs in-person seminar
_WEBINAR_SIGNALS = {"webinar", "web seminar", "online seminar", "virtual seminar", "virtual event", "online event"}
_EVENT_SIGNALS   = {"conference", "congress", "symposium", "summit", "workshop", "seminar",
                    "short course", "masterclass", "save the date", "call for abstracts",
                    "abstract submission", "register now", "registration open"}


def _classify_event_type(title: str, excerpt: str) -> str:
    """Refine 'seminar' into 'webinar' or 'seminar' based on content signals."""
    text = (title + " " + excerpt).lower()
    if any(s in text for s in _WEBINAR_SIGNALS):
        return "webinar"
    if any(s in text for s in _EVENT_SIGNALS):
        return "seminar"
    return "seminar"  # default for event queries


def _article_id(url: str, title: str) -> str:
    key = url.strip() if url else title.strip().lower()
    return "nws-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def _iso_date(date_str: str) -> str:
    """Parse ISO 8601 date from NewsAPI and return YYYY-MM-DD."""
    try:
        return dateparser.parse(date_str).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _estimate_read_time(text: str) -> str:
    words = len((text or "").split())
    return f"{max(1, round(words / 200))} min"


def _clean(text: str, max_len: int = 500) -> str:
    """Trim and clean a text field."""
    if not text:
        return ""
    text = text.replace("[+", "").replace(" chars]", "").strip()
    return text[:max_len]


def fetch_newsapi(config: dict, dry_run: bool = False) -> list:
    """
    Run all search queries through NewsAPI and return a flat list
    of article dicts ready for the pipeline deduplication step.
    """
    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        log.warning("NEWSAPI_KEY not set — skipping NewsAPI source.")
        return []

    days_back  = config["settings"]["days_lookback"]
    max_per_q  = config.get("newsapi", {}).get("max_results_per_query", 10)
    from_date  = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    all_articles = []

    for search in SEARCH_QUERIES:
        topic        = search["topic"]
        article_type = search["type"]
        badge        = search["badge"]

        log.info(f"NewsAPI search: {topic!r}")

        if dry_run:
            log.info(f"  [dry-run] would query: {search['q'][:80]}…")
            continue

        params = {
            "q":        search["q"],
            "from":     from_date,
            "language": "en",
            "sortBy":   "publishedAt",
            "pageSize": max_per_q,
            "apiKey":   api_key,
        }
        if search.get("sources"):
            params["domains"] = search["sources"]

        try:
            resp = requests.get(NEWSAPI_BASE, params=params, timeout=15)

            if resp.status_code == 401:
                log.error("NewsAPI: invalid API key. Check NEWSAPI_KEY in .env")
                break
            if resp.status_code == 426:
                log.warning("NewsAPI: free tier limit reached for this query, skipping.")
                continue
            resp.raise_for_status()

            data     = resp.json()
            articles = data.get("articles", [])
            found    = 0

            for art in articles:
                title       = (art.get("title") or "").strip()
                description = _clean(art.get("description") or "")
                content     = _clean(art.get("content") or "")
                url         = (art.get("url") or "").strip()
                published   = art.get("publishedAt", "")
                source_name = (art.get("source") or {}).get("name", "NewsAPI")

                # Skip articles with no useful content
                if not title or title == "[Removed]":
                    continue
                if not url or not url.startswith("http"):
                    continue

                # Use description as excerpt; fall back to truncated content
                excerpt = description or content
                if not excerpt:
                    continue

                # Refine event type (webinar vs seminar) from content
                effective_type = (
                    _classify_event_type(title, excerpt)
                    if article_type == "seminar"
                    else article_type
                )

                # Auto-extract simple tags from title
                tags = _extract_tags(title + " " + excerpt, effective_type)

                all_articles.append({
                    "id":           _article_id(url, title),
                    "type":         effective_type,
                    "title":        _sentence_case(title),
                    "excerpt":      excerpt,
                    "source":       source_name,
                    "date":         _iso_date(published),
                    "tags":         tags,
                    "featured":     False,
                    "readTime":     _estimate_read_time(excerpt),
                    "url":          url,
                    "badge":        badge,
                    "_score":       3,
                    "_auto_approve": True,
                    "_source":      f"newsapi:{topic}",
                })
                found += 1

            log.info(f"  → {found} articles from NewsAPI for {topic!r}")

        except requests.RequestException as e:
            log.warning(f"  NewsAPI request failed for {topic!r}: {e}")

    log.info(f"NewsAPI total: {len(all_articles)} articles")
    return all_articles


# ── Helpers ───────────────────────────────────────────────────────────────────

_KNOWN_TAGS = [
    ("EMA",              ["ema", "european medicines"]),
    ("FDA",              ["fda", "food and drug"]),
    ("Machine learning", ["machine learning"]),
    ("Deep learning",    ["deep learning", "neural network"]),
    ("LLM",              ["large language model", "llm", "gpt", "gemini", "claude", "llama"]),
    ("Drug discovery",   ["drug discovery", "drug design"]),
    ("Clinical trials",  ["clinical trial"]),
    ("Pharmacovigilance",["pharmacovigilance", "adverse event", "drug safety"]),
    ("Generative AI",    ["generative ai", "diffusion model"]),
    ("EU AI Act",        ["eu ai act", "ai act"]),
    ("EHDS",             ["ehds", "health data space"]),
    ("AlphaFold",        ["alphafold"]),
    ("Regulatory",       ["regulatory", "regulation", "compliance"]),
    ("Biotech",          ["biotech", "biopharma", "biopharmaceutical"]),
    ("RWE",              ["real-world evidence", "real world evidence", "rwe"]),
    ("Data governance",  ["data governance", "idmp", "fhir"]),
]


def _extract_tags(text: str, article_type: str) -> list:
    """Extract up to 4 relevant tags from text based on keyword matching."""
    t = text.lower()
    tags = [label for label, kws in _KNOWN_TAGS if any(kw in t for kw in kws)]
    if not tags:
        tags = ["AI news"] if article_type == "ainews" else ["Pharma AI"]
    return tags[:4]


def _sentence_case(title: str) -> str:
    """
    Convert a title to sentence case.
    Preserves acronyms (all-caps words of 2-5 letters) and proper nouns
    that follow known patterns.
    """
    ACRONYMS = {
        "EMA", "FDA", "WHO", "EU", "AI", "ML", "LLM", "GPT", "API",
        "EHDS", "IDMP", "FHIR", "CHMP", "PRIME", "RWE", "NLP",
        "GNN", "ADMET", "SBDD", "CTD", "ICH", "EHR", "NCBI",
        "UK", "US", "EU", "UN", "CEO", "CTO", "R&D", "NIH",
    }
    if not title:
        return title

    words = title.split()
    result = []
    for i, word in enumerate(words):
        # Strip punctuation for checking
        core = word.strip(".,;:!?\"'()")
        if core.upper() in ACRONYMS:
            result.append(word)       # keep acronym as-is
        elif i == 0:
            result.append(word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper())
        else:
            result.append(word.lower())
    return " ".join(result)
