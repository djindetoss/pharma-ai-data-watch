"""Optional LLM stage (Anthropic API).

Two calls per edition:
  1. score_items  – rates every shortlisted item 0-10 for the community, with a
                    one-line justification;
  2. write_items  – for the retained items only, writes an original plain-
                    language summary, a "Why it matters for NCAs" line and tags.

Both use structured outputs (JSON schema) so the response is always parseable.
If ANTHROPIC_API_KEY is absent, `available()` is False and the pipeline runs
with the keyword pre-filter only.
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)

AUDIENCE = """\
You are the editor of the "IncreaseNET AI Community" newsletter. IncreaseNET is a
European Joint Action of medicines regulators. The readers are about 45 colleagues
from 18 European National Competent Authorities (NCAs): regulatory assessors, data
scientists, IT and regulatory-policy staff. Their AI expertise varies from beginner
to expert. They want few items, each genuinely useful to a regulatory agency.

Scope: ONLY artificial intelligence and data topics linked to the development,
evaluation and supervision of MEDICINES (medicinal products), and relevant to the work
of a medicines regulator. Within that scope, priority themes in order:
1. AI used in the regulatory assessment of medicines (EMA, FDA, HMA, MHRA, national
   agencies), or by regulators in their own processes.
2. Regulatory reflections, guidelines and position papers on AI or data in the
   medicines lifecycle (EMA reflection paper, EU AI Act as it applies to medicines,
   EHDS, FDA guidance, ICH, good machine learning practice).
3. Sharing and portability of AI solutions between medicines regulators or along the
   medicines lifecycle (MLOps, containers, open source, interoperability).
4. LLMs and generative AI applied to medicines documents and processes (dossiers,
   SmPC, PK/modelling, clinical trials, pharmacovigilance).
5. Data governance, data quality, real-world data and model validation for medicines
   development and regulatory decision-making.

Out of scope (score 0-3 whatever their quality): clinical prediction or diagnosis
models with no link to medicines development or regulation, medical-device-only
topics, hospital/IT news, AI policy outside health, consumer tech, AI business news,
funding and job posts.
"""

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def write_schema(tags: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "summary": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string", "enum": tags}},
                    },
                    "required": ["id", "summary", "why_it_matters", "tags"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def available(cfg: dict) -> bool:
    return bool(cfg.get("llm", {}).get("enabled", True) and os.environ.get("ANTHROPIC_API_KEY"))


def _payload(items: list[dict], max_chars: int) -> str:
    return json.dumps([
        {"id": it["id"], "title": it.get("title", ""), "source": it.get("source", ""),
         "date": it.get("date", ""), "category": it.get("category", ""),
         "excerpt": (it.get("excerpt") or "")[:max_chars]}
        for it in items
    ], ensure_ascii=False, indent=1)


def _call(cfg: dict, system: str, user: str, schema: dict) -> dict:
    import anthropic  # imported lazily: not needed without an API key

    client = anthropic.Anthropic()
    llm = cfg["llm"]
    # Server-side fallback: if the model declines a request on policy grounds,
    # the API re-runs it on a fallback model inside the same call.
    response = client.beta.messages.create(
        model=llm["model"],
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": llm.get("effort", "medium"),
                       "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"LLM refused the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("LLM output truncated (max_tokens)")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def score_items(items: list[dict], cfg: dict) -> dict[str, tuple[int, str]]:
    """Return {id: (score 0-10, reason)}."""
    system = AUDIENCE + """
Rate each item from 0 to 10 for how useful it is to this community:
 9-10  must-read for NCAs (new regulatory guidance/position on AI or data for medicines,
       AI used by a medicines regulator, major cross-agency initiative);
 7-8   clearly relevant to one priority theme, with concrete takeaways;
 5-6   relevant background, but indirect or narrow;
 0-4   outside the medicines scope above, promotional, or too thin to be useful.
Judge only from the title, source and excerpt given; do not assume facts not stated.
Give a one-sentence reason (max 25 words) for each score. Return every id exactly once."""
    data = _call(cfg, system, "Items to rate:\n" + _payload(items, cfg["llm"]["max_excerpt_chars"]), SCORE_SCHEMA)
    out = {}
    for row in data["items"]:
        out[row["id"]] = (max(0, min(10, int(row["score"]))), row["reason"].strip())
    missing = {it["id"] for it in items} - out.keys()
    if missing:
        log.warning("LLM did not score %d item(s): %s", len(missing), sorted(missing))
    return out


def write_items(items: list[dict], cfg: dict) -> dict[str, dict]:
    """Return {id: {summary, why_it_matters, tags}} for the retained items."""
    tags = cfg["tags"]
    system = AUDIENCE + """
For each item write, in British English:
- "summary": 2 to 3 sentences, in your own words, in plain language that a regulator
  with no AI background understands. Say what was done or announced and the main
  result. Do NOT copy or closely paraphrase sentences from the excerpt, do not quote,
  and do not add facts that are not in the excerpt. Explain unavoidable jargon briefly.
- "why_it_matters": one sentence (max 35 words) on the concrete interest for a national
  competent authority (assessment practice, guidance to follow, reusable tool, data or
  validation lesson). Be specific, not generic; no hype.
- "tags": 1 to 3 tags from the allowed list.
Return every id exactly once."""
    data = _call(cfg, system, "Items:\n" + _payload(items, cfg["llm"]["max_excerpt_chars"]), write_schema(tags))
    return {row["id"]: {"summary": row["summary"].strip(),
                        "why_it_matters": row["why_it_matters"].strip(),
                        "tags": row["tags"][:3]} for row in data["items"]}
