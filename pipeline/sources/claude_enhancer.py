"""
Claude excerpt enhancer (optional)
------------------------------------
Uses the Anthropic API to improve article excerpts and extract better tags
for articles fetched from PubMed or RSS (where raw text can be noisy).

Only runs when ANTHROPIC_API_KEY is set. Falls back gracefully if not.
Batches requests to minimise API calls.
"""

import os
import json
import logging

log = logging.getLogger("pipeline.claude_enhancer")


def enhance_articles(articles: list, max_enhance: int = 20) -> list:
    """
    For each article, optionally improve the excerpt and tags using Claude.
    Returns the list with enhanced items in place.
    Only processes articles that come from PubMed or bioRxiv (raw abstracts).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        log.info("ANTHROPIC_API_KEY not set — skipping Claude enhancement.")
        return articles

    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed — skipping enhancement.")
        return articles

    client = anthropic.Anthropic(api_key=api_key)

    # Only enhance PubMed / bioRxiv articles (raw abstracts need cleaning)
    to_enhance = [
        a for a in articles
        if a.get("_source", "").startswith(("pubmed", "biorxiv"))
        and len(a.get("excerpt", "")) > 50
    ][:max_enhance]

    if not to_enhance:
        return articles

    log.info(f"Claude enhancer: improving {len(to_enhance)} article excerpts…")

    for article in to_enhance:
        try:
            prompt = f"""You are a scientific editor for a professional pharma AI intelligence portal.

Given this article abstract/excerpt, rewrite it as a 2-3 sentence clear, accurate, professional summary
suitable for a non-specialist expert audience (regulatory scientists, data coordinators, pharma R&D directors).

Rules:
- Keep all factual claims exactly as stated in the source — do NOT add or change facts
- Remove jargon where possible but keep essential technical terms
- Sentence case only (no ALL CAPS except acronyms)
- Return ONLY a JSON object: {{"excerpt": "...", "tags": ["Tag1", "Tag2", "Tag3", "Tag4"]}}

Title: {article['title']}
Source abstract: {article['excerpt'][:800]}"""

            response = client.messages.create(
                model="claude-haiku-4-5",   # fast and cheap for this task
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            if "excerpt" in data and len(data["excerpt"]) > 20:
                article["excerpt"] = data["excerpt"]
            if "tags" in data and isinstance(data["tags"], list):
                article["tags"] = data["tags"][:4]

        except Exception as e:
            log.debug(f"  Enhancement skipped for '{article['title'][:50]}': {e}")

    log.info("Claude enhancement complete.")
    return articles
