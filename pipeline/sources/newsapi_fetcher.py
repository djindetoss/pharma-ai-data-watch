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
    # ── Topic: drug-discovery ──────────────────────────────────────────────────
    {
        "topic":       "AI in drug discovery and pharmaceutical R&D",
        "portal_topic": "drug-discovery",
        "q":           "(\"artificial intelligence\" OR \"machine learning\" OR \"deep learning\") AND (\"drug discovery\" OR \"drug design\" OR \"lead optimisation\" OR \"virtual screening\" OR ADMET OR AlphaFold OR \"molecular generation\" OR \"generative chemistry\" OR \"protein structure prediction\")",
        "type":        "news",
        "badge":       "Pharma AI",
        "sources":     None,
    },
    # ── Topic: regulatory ─────────────────────────────────────────────────────
    {
        "topic":       "EMA and FDA regulatory AI guidance",
        "portal_topic": "regulatory",
        "q":           "(\"artificial intelligence\" OR \"machine learning\") AND (\"regulatory guidance\" OR \"reflection paper\" OR \"regulatory framework\" OR \"approval pathway\" OR CHMP OR ICH OR \"regulatory science\") AND (pharmaceutical OR \"drug development\" OR medicine OR EMA OR FDA OR MHRA)",
        "type":        "news",
        "badge":       "Regulatory",
        "sources":     None,
    },
    {
        "topic":       "EU AI Act and pharma/health AI regulation",
        "portal_topic": "regulatory",
        "q":           "(\"EU AI Act\" OR \"AI Act\" OR \"AI regulation\" OR \"responsible AI\" OR \"algorithmic accountability\") AND (pharmaceutical OR \"medical device\" OR clinical OR \"drug development\" OR \"health\" OR EMA OR FDA OR \"regulatory\")",
        "type":        "news",
        "badge":       "Regulatory",
        "sources":     None,
    },
    # ── Topic: clinical-ai ────────────────────────────────────────────────────
    {
        "topic":       "Clinical trials AI and pharmacovigilance",
        "portal_topic": "clinical-ai",
        "q":           "(\"artificial intelligence\" OR \"machine learning\") AND (\"clinical trial\" OR \"adaptive trial\" OR \"decentralised trial\" OR pharmacovigilance OR \"adverse event detection\" OR \"signal detection\") AND (pharmaceutical OR \"drug development\" OR regulatory)",
        "type":        "news",
        "badge":       "Clinical AI",
        "sources":     None,
    },
    {
        "topic":       "Precision medicine, digital biomarkers and medical imaging AI",
        "portal_topic": "clinical-ai",
        "q":           "(\"artificial intelligence\" OR \"machine learning\") AND (\"precision medicine\" OR \"digital biomarker\" OR \"medical imaging\" OR \"patient stratification\" OR \"treatment response prediction\") AND (pharmaceutical OR clinical OR healthcare OR \"drug development\")",
        "type":        "news",
        "badge":       "Clinical AI",
        "sources":     None,
    },
    # ── Topic: data-governance ────────────────────────────────────────────────
    {
        "topic":       "EHDS and European health data governance",
        "portal_topic": "data-governance",
        "q":           "(\"European Health Data Space\" OR EHDS OR \"health data space\" OR TEHDAS OR \"secondary use of health data\" OR \"health data permit\" OR \"health data act\") AND (pharmaceutical OR regulatory OR EMA OR clinical OR medicine OR \"drug development\")",
        "type":        "news",
        "badge":       "Data",
        "sources":     None,
    },
    {
        "topic":       "IDMP, FHIR, OMOP and regulatory data standards",
        "portal_topic": "data-governance",
        "q":           "(IDMP OR SPOR OR FHIR OR \"HL7 FHIR\" OR \"OMOP CDM\" OR CDISC OR SDTM OR MedDRA OR \"common data model\" OR \"data standard\" OR \"data interoperability\") AND (pharmaceutical OR regulatory OR EMA OR FDA OR clinical OR healthcare OR \"drug development\")",
        "type":        "news",
        "badge":       "Data",
        "sources":     None,
    },
    {
        "topic":       "DARWIN EU, NDSG and EMA data programmes",
        "portal_topic": "data-governance",
        "q":           "(\"DARWIN EU\" OR \"network data steering\" OR NDSG OR \"EMA data\" OR \"distributed data analysis\" OR \"federated analysis\" OR \"real-world data network\" OR \"data analytics centre\") AND (pharmaceutical OR regulatory OR EMA OR clinical OR healthcare)",
        "type":        "news",
        "badge":       "Data",
        "sources":     None,
    },
    {
        "topic":       "RWD/RWE governance, data quality and interoperability",
        "portal_topic": "data-governance",
        "q":           "(\"real-world evidence\" OR \"real-world data\" OR \"data governance\" OR \"data stewardship\" OR \"data quality\" OR \"federated learning\" OR \"data interoperability\" OR \"trusted research environment\" OR \"patient registry\" OR biobank) AND (pharmaceutical OR healthcare OR regulatory OR EMA OR FDA OR \"drug development\" OR clinical)",
        "type":        "news",
        "badge":       "Data",
        "sources":     None,
    },
    # ── Events ────────────────────────────────────────────────────────────────
    {
        "topic":       "Pharma AI webinars (online events)",
        "portal_topic": None,
        "q":           "(webinar OR \"online seminar\" OR \"virtual event\") AND (\"artificial intelligence\" OR \"machine learning\" OR \"generative AI\") AND (pharmaceutical OR healthcare OR \"drug development\" OR regulatory OR biotech)",
        "type":        "webinar",
        "badge":       "Event",
        "sources":     None,
    },
    {
        "topic":       "Pharma AI conferences and summits",
        "portal_topic": None,
        "q":           "(conference OR summit OR symposium OR \"annual meeting\") AND (\"artificial intelligence\" OR \"machine learning\") AND (pharmaceutical OR \"drug discovery\" OR \"clinical trial\" OR regulatory OR \"health data\" OR biotech)",
        "type":        "seminar",
        "badge":       "Event",
        "sources":     None,
    },
    {
        "topic":       "Health data and EHDS events",
        "portal_topic": None,
        "q":           "(webinar OR conference OR workshop OR summit) AND (\"health data\" OR EHDS OR \"real-world evidence\" OR \"data governance\" OR FHIR OR interoperability) AND (pharmaceutical OR clinical OR regulatory OR medicine OR healthcare)",
        "type":        "seminar",
        "badge":       "Event",
        "sources":     None,
    },
    # ── AI news ───────────────────────────────────────────────────────────────
    {
        "topic":       "General AI breakthroughs for ainews tab",
        "portal_topic": None,
        "q":           "(\"large language model\" OR \"foundation model\" OR \"generative AI\" OR GPT OR Claude OR Gemini OR \"EU AI Act\") AND (health OR science OR regulation OR biomedical OR pharmaceutical)",
        "type":        "ainews",
        "badge":       "Tech",
        "sources":     "techcrunch.com,wired.com,nature.com,statnews.com,technologyreview.com,venturebeat.com",
    },
]

# ── Quality blocklist ──────────────────────────────────────────────────────────
# Sources and title patterns that reliably produce low-quality / off-topic content.

# Domains whose content is never acceptable regardless of topic
_BLOCKED_DOMAINS = {
    # Job boards
    "nlppeople.com", "aijobs.net",
    # Press release wires
    "globenewswire.com", "prnewswire.com", "prnewswire.co.uk",
    "businesswire.com", "einpresswire.com", "accesswire.com", "openpr.com",
    # Financial / stock sites
    "stocktitan.net", "finance.yahoo.com", "seekingalpha.com",
    "marketwatch.com", "investing.com", "benzinga.com", "fool.com",
    # Entertainment / tabloid aggregators
    "yahoo.com", "msn.com", "huffpost.com",
    # Consumer health / natural medicine
    "naturalnews.com", "mercola.com", "healthline.com", "webmd.com",
    "everydayhealth.com", "medicalnewstoday.com",
    # Cybersecurity (unrelated to pharma data governance)
    "malwarebytes.com", "helpnetsecurity.com", "tenable.com",
    "darkreading.com", "securityweek.com", "threatpost.com",
    # Political / opinion / general news
    "foxnews.com", "breitbart.com", "dailymail.co.uk", "theguardian.com",
    "fairobserver.com", "opiniojuris.org",
    # Python/software package registries
    "pypi.org",
    # Personal / lifestyle blogs
    "tim.blog", "kevinmd.com", "substack.com", "medium.com",
    # eLearning / UX / design
    "elearningindustry.com", "ixdf.org", "coursera.org",
    # Fact-checking / consumer sites
    "snopes.com", "factcheck.org",
    # SEO / marketing
    "searchenginejournal.com", "searchengineland.com",
    # General tech (not pharma focused) — keep for ainews only
    "redhat.com", "histalk2.com",
    # Misc low-quality
    "betalist.com", "peoplesreview.com.np",
}

# Source names (as returned by NewsAPI) that are blocked
_BLOCKED_SOURCE_NAMES = {
    "GlobeNewswire", "PR Newswire", "PR Newswire UK", "Business Wire",
    "EIN Presswire", "PRWeb", "OpenPR", "AccessWire",
    "Nlppeople.com", "AIjobs", "Betalist.com",
    "Yahoo Entertainment", "Yahoo Finance", "MSN",
    "Natural News", "Mercola", "WebMD", "Healthline",
    "Malwarebytes", "Help Net Security", "Tenable",
    "Fox News", "Daily Mail", "The Guardian",
    "Search Engine Journal", "Search Engine Land",
    "Snopes", "eLearning Industry",
    "Stocktitan", "Seeking Alpha", "Benzinga",
}

# Title patterns that indicate low-quality / off-topic content
_BLOCKED_TITLE_PATTERNS = [
    # Market research reports
    "market report", "market research", "market size", "market opportunit",
    "market forecast", "cagr", " bn market", "billion market",
    "research report 20", "global market", "market analysis report",
    # Job postings
    "job opening", "we are hiring", "now hiring", "career opportunit",
    "is hiring", "open position",
    # Financial / stock noise
    "stock alert", "price target", "earnings call", "quarterly result",
    "fiscal year", "revenue grew", "investor relation",
    "pt increased", "raises $", " ipo ", "valuation",
    # Software package releases
    "added to pypi", "released on pypi", "version 0.", "version 1.",
    "version 2.", "version 3.", "changelog",
    # Corporate / political noise
    "stepping down as ceo", "appointed as ceo", "names new ceo",
    "hosts blast", "weight loss trick", "on sale for $",
    # General off-topic patterns
    "monday morning update", "weekly roundup", "week in review",
    "top stories", "news digest",
]

# Unambiguous online event signals → webinar
_WEBINAR_SIGNALS = {"webinar", "web seminar", "online seminar", "virtual seminar",
                    "virtual event", "online event", "live online", "livestream", "live stream"}
# Unambiguous in-person / formal event signals → seminar
_SEMINAR_SIGNALS = {"annual conference", "annual congress", "annual symposium",
                    "annual summit", "annual meeting", "conference registration",
                    "register now", "registration open", "call for abstracts",
                    "abstract submission", "save the date", "early bird",
                    "register today", "tickets available", "join us for"}


def _is_blocked(title: str, source_name: str, url: str) -> bool:
    """Return True if this article should be rejected on quality grounds."""
    # Check source name
    if source_name in _BLOCKED_SOURCE_NAMES:
        return True
    # Check domain
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lstrip("www.")
        if any(blocked in domain for blocked in _BLOCKED_DOMAINS):
            return True
    except Exception:
        pass
    # Check title patterns
    t = title.lower()
    if any(pat in t for pat in _BLOCKED_TITLE_PATTERNS):
        return True
    return False


def _classify_event_type(title: str, excerpt: str) -> str:
    """Classify as 'webinar' (online) or 'seminar' (in-person/formal) based on content."""
    text = (title + " " + excerpt).lower()
    if any(s in text for s in _WEBINAR_SIGNALS):
        return "webinar"
    if any(s in text for s in _SEMINAR_SIGNALS):
        return "seminar"
    return "seminar"  # default for event queries


# Title-level event words — the article title must contain one of these
# to be accepted as an event (prevents false positives from body-text matches)
_TITLE_EVENT_WORDS = [
    "webinar", "conference", "summit", "symposium", "congress",
    "workshop", "seminar", "masterclass", "short course",
    "annual meeting", "register", "registration", "call for abstracts",
    "save the date", "join us", "expo ", " expo", "forum",
]


def _title_is_event(title: str) -> bool:
    """Return True if the article title clearly announces an event."""
    t = title.lower()
    return any(w in t for w in _TITLE_EVENT_WORDS)


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
        portal_topic = search.get("portal_topic")   # explicit topic for JS filter
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

                # ── Quality gate: block low-value sources and titles ──────────
                if _is_blocked(title, source_name, url):
                    log.debug(f"  [blocked] {title[:60]}")
                    continue

                # For event-type queries, require the TITLE to clearly signal an event.
                # This prevents "I went to a conference" or "earnings call" articles
                # from being classified as events just because they match the query.
                is_event_query = article_type in ("webinar", "seminar")
                if is_event_query and not _title_is_event(title):
                    continue

                # Refine event type (webinar vs seminar) from title + content
                effective_type = (
                    _classify_event_type(title, excerpt)
                    if is_event_query
                    else article_type
                )

                # Auto-extract simple tags from title
                tags = _extract_tags(title + " " + excerpt, effective_type)

                article = {
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
                }
                # Attach explicit topic so the JS filter can match exactly
                if portal_topic:
                    article["topic"] = portal_topic
                all_articles.append(article)
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
    ("HDA",              ["health data agency", "health data authority"]),
    ("NDSG",             ["network data steering group", "ndsg"]),
    ("DARWIN EU",        ["darwin eu", "darwin-eu", "data analysis and real-world"]),
    ("AlphaFold",        ["alphafold"]),
    ("Regulatory",       ["regulatory", "regulation", "compliance"]),
    ("Biotech",          ["biotech", "biopharma", "biopharmaceutical"]),
    ("RWE",              ["real-world evidence", "real world evidence", "rwe"]),
    ("RWD",              ["real-world data", "real world data", "rwd"]),
    ("IDMP",             ["idmp"]),
    ("FHIR",             ["fhir", "hl7"]),
    ("Federated data",   ["federated learning", "federated data", "federated analysis"]),
    ("Data governance",  ["data governance", "data steward", "secondary use of health"]),
    ("Health data",      ["health data", "patient data", "clinical data"]),
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
