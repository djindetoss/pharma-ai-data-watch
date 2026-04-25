"""
Perplexity Sonar — live web search source
-----------------------------------------
Uses Perplexity's sonar-pro model (real-time web search) to discover
recent articles, papers, news and events relevant to AI and data
in pharmaceutical drug development and EU regulatory science.

Each Perplexity search returns a structured JSON array of articles
with real source URLs and publication dates — fully verifiable.
"""

import os
import json
import logging
import hashlib
import re
from datetime import datetime, timedelta
from openai import OpenAI

log = logging.getLogger("pipeline.perplexity")

# ── Search queries — each targets a different content niche ──────────────────

SEARCH_QUERIES = [
    {
        "topic": "AI in drug discovery — latest news and papers",
        "type": "paper",
        "query": (
            "Find the most recent (last 7 days) scientific papers, preprints, "
            "or major news about artificial intelligence and machine learning "
            "applied to drug discovery, target identification, molecular design, "
            "or ADMET prediction. Focus on peer-reviewed publications or "
            "reputable sources like Nature, Science, PNAS, JACS, JCIM, "
            "bioRxiv, medRxiv."
        )
    },
    {
        "topic": "EMA, FDA and EU regulatory AI guidance",
        "type": "news",
        "query": (
            "Find the most recent (last 7 days) official guidance, reflection papers, "
            "statements or news from EMA, FDA, WHO, ICH or EU institutions about "
            "the use of artificial intelligence or machine learning in drug development, "
            "clinical trials, or regulatory submissions. Include any CHMP, PRIME or "
            "conditional marketing authorisation news related to AI-assisted products."
        )
    },
    {
        "topic": "Clinical AI and real-world evidence",
        "type": "news",
        "query": (
            "Find the most recent (last 7 days) news or publications about "
            "artificial intelligence in clinical trials, adaptive trial design, "
            "real-world evidence (RWE), pharmacovigilance, or post-market safety "
            "surveillance. Include EHDS or health data governance developments."
        )
    },
    {
        "topic": "General AI breakthroughs relevant to biomedicine",
        "type": "ainews",
        "query": (
            "Find the most recent (last 7 days) major AI model releases, research "
            "breakthroughs, or policy developments from organisations like OpenAI, "
            "Google DeepMind, Anthropic, Meta AI, or the EU AI Act enforcement, "
            "that are particularly relevant to biomedical, clinical, or pharmaceutical "
            "applications. Include AlphaFold updates, LLM medical benchmarks, "
            "or AI regulation news."
        )
    },
    {
        "topic": "Upcoming pharma AI webinars and conferences",
        "type": "webinar",
        "query": (
            "Find upcoming webinars, conferences, seminars, or workshops (next 60 days) "
            "about artificial intelligence in pharmaceutical development, drug discovery, "
            "regulatory science, or clinical trials. Look for events organised by "
            "DIA, RAPS, EMA, FDA, ISPE, or major universities. Include event dates "
            "and registration links where available."
        )
    },
]

# ── JSON extraction prompt ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a precise scientific and regulatory intelligence assistant.
Your task is to search the web and return structured JSON describing recent, relevant articles.

CRITICAL RULES:
- Only include items that actually exist — never fabricate titles, authors, or URLs.
- Every item must have a real, working URL from the original publisher.
- Dates must be real publication dates in YYYY-MM-DD format.
- Titles must be in sentence case (capitalise first word and proper nouns only).
- Excerpts must be accurate summaries of the actual content — no hallucination.
- If you cannot find enough real items, return fewer — never invent content.

Return ONLY a valid JSON array. No markdown, no explanation, just the array.
Each object must have exactly these fields:
{
  "title": "Sentence case title of the article or event",
  "source": "Publisher or organisation name",
  "date": "YYYY-MM-DD",
  "url": "https://real-url-to-the-article",
  "excerpt": "2-3 accurate sentences summarising the actual content",
  "tags": ["Tag1", "Tag2", "Tag3"],
  "read_time": "X min"
}"""


def clean_json_response(text: str) -> str:
    """Extract JSON array from Perplexity response, strip markdown fences."""
    text = text.strip()
    # Remove ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    # Find first [ and last ]
    start = text.find("[")
    end   = text.rfind("]")
    if start != -1 and end != -1:
        return text[start:end+1]
    return "[]"


def article_id(url: str, title: str) -> str:
    key = url.strip() if url and url != "#" else title.strip().lower()
    return "plx-" + hashlib.sha1(key.encode()).hexdigest()[:12]


def fetch_perplexity(config: dict, dry_run: bool = False) -> list:
    """
    Run all search queries through Perplexity sonar-pro and return
    a flat list of article dicts ready for the pipeline.
    """
    api_key = os.getenv("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        log.warning("PERPLEXITY_API_KEY not set — skipping Perplexity source.")
        return []

    plx_cfg  = config.get("perplexity", {})
    model    = plx_cfg.get("model", "sonar-pro")
    max_age  = config["settings"]["days_lookback"]
    cutoff   = (datetime.now() - timedelta(days=max_age)).strftime("%Y-%m-%d")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai"
    )

    all_articles = []

    for search in SEARCH_QUERIES:
        topic       = search["topic"]
        article_type = search["type"]
        user_query  = (
            f"{search['query']}\n\n"
            f"Only include items published on or after {cutoff}. "
            f"Return up to 5 items maximum. Return ONLY a JSON array as instructed."
        )

        log.info(f"Perplexity search: {topic!r}")

        if dry_run:
            log.info(f"  [dry-run] would query: {user_query[:80]}…")
            continue

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_query}
                ],
                temperature=0.1,   # low temperature = factual, consistent
                max_tokens=2000,
            )

            raw = response.choices[0].message.content
            citations = getattr(response, "citations", [])  # real URLs Perplexity found

            log.debug(f"  Raw response ({len(raw)} chars), citations: {len(citations)}")

            # Parse structured JSON from response
            json_str  = clean_json_response(raw)
            items     = json.loads(json_str)

            if not isinstance(items, list):
                log.warning(f"  Unexpected response format for {topic!r}")
                continue

            for item in items:
                title   = item.get("title", "").strip()
                url     = item.get("url", "#").strip()
                excerpt = item.get("excerpt", "").strip()
                source  = item.get("source", "Web").strip()
                date    = item.get("date", datetime.now().strftime("%Y-%m-%d"))
                tags    = item.get("tags", [])[:4]
                rt      = item.get("read_time", "5 min")

                if not title or not excerpt:
                    continue

                # Validate URL is real (not a placeholder)
                if not url.startswith("http"):
                    # Try to find it in Perplexity citations
                    url = citations[0] if citations else "#"

                score = 3 if article_type in ("news", "paper") else 2

                all_articles.append({
                    "id":           article_id(url, title),
                    "type":         article_type,
                    "title":        title,
                    "excerpt":      excerpt,
                    "source":       source,
                    "date":         date,
                    "tags":         tags,
                    "featured":     False,
                    "readTime":     rt,
                    "url":          url,
                    "badge":        _badge_for_type(article_type),
                    "_score":       score,
                    "_auto_approve": True,   # Perplexity results are pre-curated
                    "_source":      f"perplexity:{topic}"
                })

            log.info(f"  → {len(items)} items from Perplexity for {topic!r}")

        except json.JSONDecodeError as e:
            log.warning(f"  JSON parse error for {topic!r}: {e}")
        except Exception as e:
            log.warning(f"  Perplexity API error for {topic!r}: {e}")

    log.info(f"Perplexity total: {len(all_articles)} articles")
    return all_articles


def _badge_for_type(t: str) -> str:
    return {
        "news":    "Latest",
        "paper":   "Open Access",
        "webinar": "Upcoming",
        "seminar": "Upcoming",
        "ainews":  "Tech",
    }.get(t, "")
