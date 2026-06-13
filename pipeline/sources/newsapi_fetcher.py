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

# ── Per-source editorial guide ─────────────────────────────────────────────────
# Documents what specific content is valuable (or not) per outlet.
# Used by the briefing generator and as human-readable editorial policy.

SOURCE_EDITORIAL_GUIDE = {

    # ── General AI media — high trust ─────────────────────────────────────────

    "TechCrunch": {
        "trust": "high",
        "keep": [
            "Model launches from major labs (GPT, Claude, Gemini, LLaMA, Mistral, Grok)",
            "AI startup fundraising for health/biotech/pharma (Series A+ preferred)",
            "Enterprise AI adoption in life sciences and healthcare",
            "Big tech AI strategy (Microsoft Copilot, Google Workspace AI, AWS Bedrock)",
            "OpenAI / Anthropic / DeepMind / Meta AI / xAI company milestones",
            "AI regulation US/EU coverage",
        ],
        "skip": [
            "Social media platforms without AI angle",
            "Fintech and crypto unrelated to AI",
            "General startup news (no pharma/health/AI angle)",
        ],
    },

    "TechCrunch AI": {
        "trust": "high",
        "keep": ["Same as TechCrunch — AI-section feed, all content relevant"],
        "skip": [],
    },

    "Wired": {
        "trust": "high",
        "keep": [
            "AI ethics, safety and alignment — long-form analysis",
            "Foundation model landscape analysis (new capabilities, limitations)",
            "AI in science: drug discovery, biology, materials, climate",
            "AI regulation and society impact (EU AI Act, copyright, labour)",
            "Lab culture and strategy investigations (OpenAI, Anthropic, DeepMind)",
            "AI existential risk and governance debates",
        ],
        "skip": [
            "Gadget reviews and consumer electronics without AI angle",
            "Cybersecurity articles unrelated to AI/ML security",
            "Culture and entertainment (film, music, fashion)",
        ],
    },

    "MIT Technology Review": {
        "trust": "high",
        "keep": [
            "AI safety and alignment research coverage (must-read tier)",
            "Foundation model capabilities deep-dives (reasoning, coding, multimodal)",
            "AI in scientific research (Nature-equivalent analysis)",
            "AI policy analysis: NIST AI RMF, US AI EO, EU AI Act, G7 AI",
            "Emerging AI paradigms: agents, reasoning chains, multimodal, world models",
            "Critical investigations: data sourcing, compute concentration, AI hype vs reality",
        ],
        "skip": [
            "General biotech without AI component",
            "Climate tech without AI component",
            "Consumer gadgets and device reviews",
        ],
    },

    "VentureBeat": {
        "trust": "high",
        "keep": [
            "Enterprise LLM deployment: RAG, fine-tuning, agents in production",
            "AI infrastructure: GPU supply chain, cloud AI, MLOps, inference optimization",
            "Open-source model releases (Hugging Face, Mistral, Meta LLaMA milestones)",
            "AI for healthcare/pharma enterprise use cases",
            "Agentic AI and AI developer tools announcements",
            "B2B AI platform comparisons and enterprise AI strategy",
        ],
        "skip": [
            "Marketing/SEO AI tools (low scientific signal)",
            "General SaaS without AI angle",
            "Consumer gaming",
        ],
    },

    "VentureBeat AI": {
        "trust": "high",
        "keep": ["Same as VentureBeat — AI-section feed"],
        "skip": [],
    },

    "The Verge": {
        "trust": "high",
        "keep": [
            "Consumer AI product updates (ChatGPT, Copilot, Gemini app, Claude.ai)",
            "Big tech AI competitive dynamics (Google vs Microsoft vs OpenAI vs Apple)",
            "AI hardware launches: NVIDIA chips, AI PCs, custom silicon",
            "AI policy consumer impact (copyright, privacy, deepfakes)",
            "AI creative tools and generative media",
        ],
        "skip": [
            "Gaming hardware and game releases without AI",
            "EV/auto without autonomous driving/AI",
            "General consumer electronics (headphones, cameras)",
        ],
    },

    "Ars Technica": {
        "trust": "high",
        "keep": [
            "Technical deep-dives: model architecture, training details, inference optimization",
            "AI hardware and compute: NVIDIA earnings, TPUs, custom AI chips",
            "AI law, copyright and regulatory compliance analysis",
            "Scientific AI breakthroughs with technical depth",
            "AI security vulnerabilities, prompt injection, adversarial ML",
            "AI benchmark analysis and model capability comparisons",
        ],
        "skip": [
            "Gaming hardware and game reviews",
            "General IT security without AI angle",
            "Telecoms and networking without AI",
        ],
    },

    "The Register": {
        "trust": "high",
        "keep": [
            "EU AI Act legislative calendar: votes, trilogues, implementing acts",
            "Enterprise AI cloud: AWS Bedrock, Azure AI, GCP Vertex AI deployments",
            "AI chip market and data center investment (critical for compute context)",
            "Critical/skeptical AI coverage (contrarian perspective, important for balance)",
            "AI energy consumption and sustainability data",
            "UK government AI policy (DSIT, AI Safety Institute)",
        ],
        "skip": [
            "General IT security incidents without AI",
            "Telecoms spectrum and networking",
            "Legacy hardware reviews",
        ],
    },

    # ── Science and research ──────────────────────────────────────────────────

    "Nature Machine Intelligence": {
        "trust": "critical",
        "keep": [
            "ALL peer-reviewed AI research — 100% signal, no filtering needed",
            "Priority areas: drug discovery, clinical AI, regulatory AI, protein ML",
            "Especially: AlphaFold/structure prediction, molecular generation, clinical LLMs",
        ],
        "skip": [],
    },

    "Nature.com": {
        "trust": "high",
        "keep": [
            "AI/ML papers in Nature, Nature Medicine, Nature Biotechnology",
            "AI in drug discovery and molecular biology",
            "AlphaFold and protein structure prediction updates",
            "AI benchmarks and scientific capability assessments",
            "AI in clinical research, genomics, and omics",
            "AI ethics and governance (Nature editorial positions)",
        ],
        "skip": [
            "Ecology, particle physics, climate science without AI",
            "Pure chemistry/materials without ML component",
        ],
    },

    "STAT News": {
        "trust": "critical",
        "keep": [
            "ALL content — specialized health/pharma AI, highest signal source",
            "FDA decisions on AI-enabled medical devices (510k, PMA)",
            "Clinical AI deployments: EHR AI, diagnostic AI in hospitals",
            "AI in drug discovery and biotech R&D",
            "Health AI policy and regulation",
            "Clinical trial AI (adaptive trials, patient selection, endpoints)",
        ],
        "skip": [],
    },

    "Hugging Face Blog": {
        "trust": "high",
        "keep": [
            "New model releases (especially biomedical, clinical, multilingual)",
            "Open-source AI ecosystem news (model hubs, datasets, spaces)",
            "AI safety and responsible AI tooling",
            "Benchmark updates and leaderboards",
            "Papers with code that reveal new state-of-the-art",
        ],
        "skip": [
            "General ML tutorials without new capabilities",
            "Student/beginner content without novel technical insight",
        ],
    },

    # ── Regulatory and pharma ─────────────────────────────────────────────────

    "FDA": {
        "trust": "critical",
        "keep": [
            "AI/ML-enabled medical device approvals (510k, De Novo, PMA)",
            "AI guidance documents and discussion papers",
            "Digital health framework updates (DSCSA, SaMD)",
            "Pharmacovigilance AI guidance: signal detection, adverse event reporting",
            "Real-world data use guidance",
        ],
        "skip": [
            "Drug approvals without AI component",
            "Food safety and cosmetics",
            "Enforcement actions without data/AI angle",
        ],
    },

    "FDA.gov": {
        "trust": "critical",
        "keep": ["Same as FDA"],
        "skip": ["Consumer safety alerts", "Recalls", "Generic press releases without AI"],
    },

    "EMA": {
        "trust": "critical",
        "keep": [
            "ALL AI/ML guideline documents and reflection papers",
            "DARWIN EU programme updates",
            "EHDS implementation news from EMA perspective",
            "ICH guidelines with AI implications (ICH E6, ICH M7, ICH S1)",
            "HMA/EMA joint taskforce on AI",
        ],
        "skip": [
            "Individual drug approvals without AI/data angle",
            "Veterinary medicines without data science angle",
        ],
    },

    # ── AI infrastructure and open-source ─────────────────────────────────────

    "Databricks.com": {
        "trust": "medium",
        "keep": [
            "Open-source AI/LLM releases (DBRX, Dolly, series)",
            "Mosaic AI and data lakehouse for healthcare/life sciences",
            "AI governance and responsible AI tooling",
            "Benchmarks: MMLU, BioASQ, clinical NLP",
        ],
        "skip": [
            "General data engineering and ETL tutorials",
            "BI dashboards without AI",
        ],
    },

    "GitHub": {
        "trust": "medium",
        "keep": [
            "Major open-source AI project releases (models, datasets, benchmarks)",
            "AlphaFold variants, clinical NLP repos, drug discovery ML tools",
        ],
        "skip": [
            "General coding repos without AI angle",
        ],
    },

    "IEEE": {
        "trust": "high",
        "keep": [
            "AI standards development (IEEE P3119, IEEE 7000 series on AI ethics)",
            "AI in biomedical engineering and medical devices",
            "AI safety and reliability standards",
        ],
        "skip": [
            "Electrical engineering without AI",
            "Pure hardware/circuit design",
        ],
    },
}


# ── Search queries ─────────────────────────────────────────────────────────────
# Each query targets a specific content niche.
# Results are mapped to a portal article type.

SEARCH_QUERIES = [
    # ══════════════════════════════════════════════════════════════════════════
    # PHARMA & REGULATORY TOPICS
    # ══════════════════════════════════════════════════════════════════════════

    # ── Topic: drug-discovery ──────────────────────────────────────────────────
    {
        "topic":        "AI in drug discovery and pharmaceutical R&D",
        "portal_topic": "drug-discovery",
        "q":            '("artificial intelligence" OR "machine learning" OR "deep learning") AND ("drug discovery" OR "drug design" OR "lead optimisation" OR "virtual screening" OR ADMET OR AlphaFold OR "molecular generation" OR "generative chemistry" OR "protein structure prediction")',
        "type":         "news",
        "badge":        "Pharma AI",
        "sources":      None,
    },
    # ── Topic: regulatory ─────────────────────────────────────────────────────
    {
        "topic":        "EMA and FDA regulatory AI guidance",
        "portal_topic": "regulatory",
        "q":            '("artificial intelligence" OR "machine learning") AND ("regulatory guidance" OR "reflection paper" OR "regulatory framework" OR "approval pathway" OR CHMP OR ICH OR "regulatory science") AND (pharmaceutical OR "drug development" OR medicine OR EMA OR FDA OR MHRA)',
        "type":         "news",
        "badge":        "Regulatory",
        "sources":      None,
    },
    {
        "topic":        "EU AI Act and pharma/health AI regulation",
        "portal_topic": "regulatory",
        "q":            '("EU AI Act" OR "AI Act" OR "AI regulation" OR "responsible AI" OR "algorithmic accountability") AND (pharmaceutical OR "medical device" OR clinical OR "drug development" OR health OR EMA OR FDA OR regulatory)',
        "type":         "news",
        "badge":        "Regulatory",
        "sources":      None,
    },
    # ── Topic: clinical-ai ────────────────────────────────────────────────────
    {
        "topic":        "Clinical trials AI and pharmacovigilance",
        "portal_topic": "clinical-ai",
        "q":            '("artificial intelligence" OR "machine learning") AND ("clinical trial" OR "adaptive trial" OR "decentralised trial" OR pharmacovigilance OR "adverse event detection" OR "signal detection") AND (pharmaceutical OR "drug development" OR regulatory)',
        "type":         "news",
        "badge":        "Clinical AI",
        "sources":      None,
    },
    {
        "topic":        "Precision medicine, digital biomarkers and medical imaging AI",
        "portal_topic": "clinical-ai",
        "q":            '("artificial intelligence" OR "machine learning") AND ("precision medicine" OR "digital biomarker" OR "medical imaging" OR "patient stratification" OR "treatment response prediction") AND (pharmaceutical OR clinical OR healthcare OR "drug development")',
        "type":         "news",
        "badge":        "Clinical AI",
        "sources":      None,
    },
    # ── Topic: data-governance ────────────────────────────────────────────────
    {
        "topic":        "EHDS and European health data governance",
        "portal_topic": "data-governance",
        "q":            '("European Health Data Space" OR EHDS OR "health data space" OR TEHDAS OR "secondary use of health data" OR "health data permit" OR "health data act") AND (pharmaceutical OR regulatory OR EMA OR clinical OR medicine OR "drug development")',
        "type":         "news",
        "badge":        "Data",
        "sources":      None,
    },
    {
        "topic":        "IDMP, FHIR, OMOP and regulatory data standards",
        "portal_topic": "data-governance",
        "q":            '(IDMP OR SPOR OR FHIR OR "HL7 FHIR" OR "OMOP CDM" OR CDISC OR SDTM OR MedDRA OR "common data model" OR "data standard" OR "data interoperability") AND (pharmaceutical OR regulatory OR EMA OR FDA OR clinical OR healthcare OR "drug development")',
        "type":         "news",
        "badge":        "Data",
        "sources":      None,
    },
    {
        "topic":        "DARWIN EU, NDSG and EMA data programmes",
        "portal_topic": "data-governance",
        "q":            '("DARWIN EU" OR "network data steering" OR NDSG OR "EMA data" OR "distributed data analysis" OR "federated analysis" OR "real-world data network" OR "data analytics centre") AND (pharmaceutical OR regulatory OR EMA OR clinical OR healthcare)',
        "type":         "news",
        "badge":        "Data",
        "sources":      None,
    },
    {
        "topic":        "RWD/RWE governance, data quality and interoperability",
        "portal_topic": "data-governance",
        "q":            '("real-world evidence" OR "real-world data" OR "data governance" OR "data stewardship" OR "data quality" OR "federated learning" OR "data interoperability" OR "trusted research environment" OR "patient registry" OR biobank) AND (pharmaceutical OR healthcare OR regulatory OR EMA OR FDA OR "drug development" OR clinical)',
        "type":         "news",
        "badge":        "Data",
        "sources":      None,
    },
    # ── Events ────────────────────────────────────────────────────────────────
    {
        "topic":        "Pharma AI webinars (online events)",
        "portal_topic": None,
        "q":            '(webinar OR "online seminar" OR "virtual event") AND ("artificial intelligence" OR "machine learning" OR "generative AI") AND (pharmaceutical OR healthcare OR "drug development" OR regulatory OR biotech)',
        "type":         "webinar",
        "badge":        "Event",
        "sources":      None,
    },
    {
        "topic":        "Pharma AI conferences and summits",
        "portal_topic": None,
        "q":            '(conference OR summit OR symposium OR "annual meeting") AND ("artificial intelligence" OR "machine learning") AND (pharmaceutical OR "drug discovery" OR "clinical trial" OR regulatory OR "health data" OR biotech)',
        "type":         "seminar",
        "badge":        "Event",
        "sources":      None,
    },
    {
        "topic":        "Health data and EHDS events",
        "portal_topic": None,
        "q":            '(webinar OR conference OR workshop OR summit) AND ("health data" OR EHDS OR "real-world evidence" OR "data governance" OR FHIR OR interoperability) AND (pharmaceutical OR clinical OR regulatory OR medicine OR healthcare)',
        "type":         "seminar",
        "badge":        "Event",
        "sources":      None,
    },

    # ══════════════════════════════════════════════════════════════════════════
    # AI NEWS — 3 targeted queries replacing the single pharma-constrained one
    # ══════════════════════════════════════════════════════════════════════════

    # ── Query A: AI Lab & Company News ────────────────────────────────────────
    # What the major AI labs are building, releasing, and announcing.
    # Sources: tech media that cover labs in depth. No pharma constraint.
    # Keep: model releases, research papers, safety announcements, funding, API changes.
    {
        "topic":        "AI lab announcements — model releases, research, company strategy",
        "portal_topic": None,
        "q":            '(OpenAI OR Anthropic OR "Google DeepMind" OR DeepMind OR "Meta AI" OR "Mistral AI" OR Mistral OR "xAI" OR Cohere OR "Hugging Face" OR "AI lab") AND (model OR launch OR release OR paper OR research OR capability OR GPT OR Claude OR Gemini OR LLaMA OR agent OR alignment OR safety OR funding OR reasoning)',
        "type":         "ainews",
        "badge":        "AI Lab",
        "sources":      "techcrunch.com,theverge.com,wired.com,venturebeat.com,arstechnica.com,technologyreview.com,theregister.com",
        "max_results":  20,
    },

    # ── Query B: AI Frontier Technology ──────────────────────────────────────
    # Capabilities, benchmarks, agents, safety research, infrastructure.
    # Covers what AI systems can DO — not lab identity.
    # Sources: outlets that provide technical depth. No pharma constraint.
    # Keep: reasoning, multimodal, agents, benchmarks, safety/alignment, chips, compute.
    {
        "topic":        "AI frontier — reasoning, agents, multimodal, benchmarks, safety",
        "portal_topic": None,
        "q":            '("AI agent" OR "agentic AI" OR "reasoning model" OR "multimodal AI" OR "vision-language model" OR "AI safety" OR "AI alignment" OR "AI benchmark" OR "chain-of-thought" OR "AI hallucination" OR "model reliability" OR "model collapse" OR "AI accelerator" OR "inference optimization" OR "AI chip" OR "foundation model")',
        "type":         "ainews",
        "badge":        "AI Tech",
        "sources":      "techcrunch.com,theverge.com,wired.com,arstechnica.com,technologyreview.com,venturebeat.com,theregister.com,statnews.com",
        "max_results":  20,
    },

    # ── Query C: AI Policy & Global Governance ────────────────────────────────
    # Regulation, law, copyright, ethics frameworks at national/global level.
    # Broader than pharma regulation — covers the whole AI governance landscape.
    # Keep: EU AI Act (legislative calendar, implementing acts), NIST AI RMF,
    # US AI Executive Orders, G7 Hiroshima Process, GPAI, copyright/liability,
    # national AI strategies, AI safety institutes (UK, US, EU, JP, KR).
    {
        "topic":        "AI policy — regulation, law, governance, ethics at global level",
        "portal_topic": None,
        "q":            '("EU AI Act" OR "AI regulation" OR "AI governance" OR "NIST AI" OR "AI executive order" OR "G7 AI" OR GPAI OR "AI liability" OR "AI copyright" OR "AI accountability" OR "AI transparency" OR "AI audit" OR "AI risk" OR "AI safety institute" OR "trustworthy AI" OR "AI Act compliance" OR "national AI strategy")',
        "type":         "ainews",
        "badge":        "AI Policy",
        "sources":      "techcrunch.com,wired.com,arstechnica.com,technologyreview.com,theregister.com,venturebeat.com",
        "max_results":  15,
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
    "barchart.com", "tradingview.com", "stoculator.com",
    # Crypto / blockchain (high volume, zero pharma/AI signal)
    "crypto-briefing.com", "coindesk.com", "decrypt.co", "cointelegraph.com",
    "beincrypto.com", "cryptonews.com",
    # Entertainment / tabloid aggregators
    "yahoo.com", "msn.com", "huffpost.com",
    # Consumer health / natural medicine
    "naturalnews.com", "mercola.com", "healthline.com", "webmd.com",
    "everydayhealth.com", "medicalnewstoday.com",
    # Cybersecurity (unrelated to pharma data governance)
    "malwarebytes.com", "helpnetsecurity.com", "tenable.com",
    "darkreading.com", "securityweek.com", "threatpost.com",
    # Political / opinion / general news (low signal-to-noise for our topics)
    "foxnews.com", "breitbart.com", "dailymail.co.uk",
    "fairobserver.com", "opiniojuris.org",
    # Python/software package registries
    "pypi.org",
    # Personal / lifestyle / coding tutorial blogs
    "tim.blog", "kevinmd.com", "substack.com", "medium.com",
    "c-sharpcorner.com", "smashingapps.com", "marketing-tutor.com",
    # eLearning / UX / design
    "elearningindustry.com", "ixdf.org", "coursera.org",
    # Fact-checking / consumer sites
    "snopes.com", "factcheck.org",
    # SEO / marketing
    "searchenginejournal.com", "searchengineland.com",
    # General tech (not pharma focused)
    "redhat.com", "histalk2.com",
    # Regional general news (high volume, low pharma-AI relevance)
    "thechronicle.com.gh", "ewtnnews.com", "siamnews.net",
    "dou.ua", "ibtimes.com.au", "mymotherlode.com",
    # Misc low-quality
    "betalist.com", "peoplesreview.com.np",
    "wordpress.com", "bitrebels.com", "syllad.com",
    "cloudtweaks.com", "geeky-gadgets.com", "studyfinds.com",
    "internationalaccountingbulletin.com",
}

# Source names (as returned by NewsAPI) that are always blocked
_BLOCKED_SOURCE_NAMES = {
    "GlobeNewswire", "PR Newswire", "PR Newswire UK", "Business Wire",
    "EIN Presswire", "PRWeb", "OpenPR", "AccessWire",
    "Nlppeople.com", "AIjobs", "Betalist.com",
    "Yahoo Entertainment", "Yahoo Finance", "MSN",
    "Natural News", "Mercola", "WebMD", "Healthline",
    "Malwarebytes", "Help Net Security", "Tenable",
    "Fox News", "Daily Mail",
    "Search Engine Journal", "Search Engine Land",
    "Snopes", "eLearning Industry",
    "Stocktitan", "Seeking Alpha", "Benzinga",
    # Crypto — high volume, no pharma/AI value
    "Crypto Briefing", "CoinDesk", "Decrypt", "CoinTelegraph", "BeInCrypto",
    # Regional general news — consistently off-topic
    "The Punch",          # Nigerian general newspaper
    "BusinessLine",       # Indian business paper (use Financial Post queries instead)
    "The Times of India", # Indian general news
    "Antaranews.com",     # Indonesian news agency
    "Geeky Gadgets",      # Consumer tech blog
    "C-sharpcorner.com",  # Coding tutorials
    "Siamnews.net",       # Thai news
}

# ── Per-source relevance gate ──────────────────────────────────────────────────
# For sources that slip through but produce noisy content, require at least one
# of these keywords in the title. Applied ONLY to sources listed here.
# All other sources are evaluated by the global quality gate only.

_SOURCE_TITLE_GATE = {
    # Financial press: keep only when explicitly about AI or pharma
    "Financial Post": [
        "artificial intelligence", "machine learning", "AI", "pharma",
        "pharmaceutical", "drug", "biotech", "clinical", "FDA", "EMA",
    ],
    "Fortune": [
        "artificial intelligence", "machine learning", "AI",
        "pharma", "drug discovery", "biotech",
    ],
    # General tech: keep only AI-specific articles
    "ZDNet": [
        "artificial intelligence", "machine learning", "AI", "LLM",
        "generative AI", "foundation model",
    ],
    "PCMag": [
        "artificial intelligence", "machine learning", "AI", "LLM",
        "generative AI",
    ],
    "TechRadar": [
        "artificial intelligence", "machine learning", "AI", "LLM",
        "generative AI", "neural network",
    ],
    # Australian/general news
    "ABC News (AU)": [
        "artificial intelligence", "machine learning", "AI", "pharma",
        "pharmaceutical", "drug", "clinical",
    ],
    # General science
    "ScienceAlert": [
        "artificial intelligence", "machine learning", "AI", "drug",
        "pharmaceutical", "clinical", "protein", "AlphaFold",
    ],
}


def _is_blocked(title: str, source_name: str, url: str) -> bool:
    """Return True if this article should be rejected on quality grounds."""
    # Check source name blocklist
    if source_name in _BLOCKED_SOURCE_NAMES:
        return True
    # Check domain blocklist
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lstrip("www.")
        if any(blocked in domain for blocked in _BLOCKED_DOMAINS):
            return True
    except Exception:
        pass
    # Per-source title gate
    if source_name in _SOURCE_TITLE_GATE:
        t = title.lower()
        required = _SOURCE_TITLE_GATE[source_name]
        if not any(kw.lower() in t for kw in required):
            return True
    # Title pattern blocklist
    t = title.lower()
    if any(pat in t for pat in _BLOCKED_TITLE_PATTERNS):
        return True
    return False


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
    # Crypto noise
    "bitcoin", "ethereum", "crypto", "blockchain", "token", "nft",
    "defi", "web3", "cryptocurrency",
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

    days_back    = config["settings"]["days_lookback"]
    default_max  = config.get("newsapi", {}).get("max_results_per_query", 10)
    from_date    = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    all_articles = []

    for search in SEARCH_QUERIES:
        topic        = search["topic"]
        portal_topic = search.get("portal_topic")
        article_type = search["type"]
        badge        = search["badge"]
        max_per_q    = search.get("max_results", default_max)  # per-query override

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

                if not title or title == "[Removed]":
                    continue
                if not url or not url.startswith("http"):
                    continue

                excerpt = description or content
                if not excerpt:
                    continue

                # Quality gate
                if _is_blocked(title, source_name, url):
                    log.debug(f"  [blocked] {title[:60]}")
                    continue

                # For event queries, require event signal in title
                is_event_query = article_type in ("webinar", "seminar")
                if is_event_query and not _title_is_event(title):
                    continue

                effective_type = (
                    _classify_event_type(title, excerpt)
                    if is_event_query
                    else article_type
                )

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
                if portal_topic:
                    article["topic"] = portal_topic
                all_articles.append(article)
                found += 1

            log.info(f"  → {found} articles from NewsAPI for {topic!r}")

        except requests.RequestException as e:
            log.warning(f"  NewsAPI request failed for {topic!r}: {e}")

    log.info(f"NewsAPI total: {len(all_articles)} articles")
    return all_articles


# ── Tag extraction ─────────────────────────────────────────────────────────────

_KNOWN_TAGS = [
    ("EMA",              ["ema", "european medicines"]),
    ("FDA",              ["fda", "food and drug"]),
    ("Machine learning", ["machine learning"]),
    ("Deep learning",    ["deep learning", "neural network"]),
    ("LLM",              ["large language model", "llm", "gpt", "gemini", "claude", "llama"]),
    ("AI agent",         ["ai agent", "agentic ai", "autonomous agent"]),
    ("AI safety",        ["ai safety", "ai alignment", "alignment research"]),
    ("Reasoning AI",     ["reasoning model", "chain-of-thought", "o1", "o3", "o4"]),
    ("Multimodal AI",    ["multimodal", "vision-language", "image-text"]),
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
    ("OpenAI",           ["openai"]),
    ("Anthropic",        ["anthropic"]),
    ("DeepMind",         ["deepmind", "google deepmind"]),
    ("AI benchmark",     ["benchmark", "leaderboard", "mmlu", "bioasq", "helm"]),
    ("AI policy",        ["ai governance", "ai regulation", "nist ai", "gpai"]),
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
        core = word.strip(".,;:!?\"'()")
        if core.upper() in ACRONYMS:
            result.append(word)
        elif i == 0:
            result.append(word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper())
        else:
            result.append(word.lower())
    return " ".join(result)
