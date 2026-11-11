"""Finalise a reviewed draft: assign the edition number, store the edition and
remove the draft files. Nothing is published on the web: the newsletter is
distributed by e-mail only (send_email.py)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from . import DRAFTS_DIR, EDITIONS_DIR, EDITIONS_INDEX
from .render import find_todos, load_edition

log = logging.getLogger(__name__)


def load_index() -> list[dict]:
    return json.loads(EDITIONS_INDEX.read_text(encoding="utf-8")) if EDITIONS_INDEX.exists() else []


def publish(draft_path: Path, cfg: dict, force: bool = False) -> dict:
    edition = load_edition(draft_path)
    todos = find_todos(edition)
    if todos and not force:
        raise SystemExit("Draft still contains TODO / EDIT ME markers:\n  - " + "\n  - ".join(todos)
                         + "\nEdit them or publish with --force.")

    previous = load_index()
    existing = {e["date"]: e["number"] for e in previous}
    index = [e for e in previous if e["date"] != edition["edition_date"]]  # re-validation replaces
    edition["edition_number"] = existing.get(edition["edition_date"], len(index) + 1)

    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    final_yaml = EDITIONS_DIR / f"{edition['edition_date']}.yaml"
    keep = {k: v for k, v in edition.items() if k != "runners_up"}
    final_yaml.write_text(yaml.safe_dump(keep, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")

    n_items = len(edition["scientific_articles"]) + len(edition["news"]) + (1 if edition.get("highlight") else 0)
    index.append({"number": edition["edition_number"], "date": edition["edition_date"],
                  "period": edition["period"], "items": n_items,
                  "highlight": edition["highlight"]["title"] if edition.get("highlight") else None})
    index.sort(key=lambda e: e["number"])
    EDITIONS_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # remove the draft and its rendered previews
    stem = draft_path.with_suffix("")
    for suffix in (".yaml", ".email.html", ".preview.html", ".txt", ".md"):
        p = stem.with_suffix(suffix)
        if p.exists():
            p.unlink()
    log.info("Validated edition #%d (%s)", edition["edition_number"], edition["edition_date"])
    return edition


def pending_drafts() -> list[Path]:
    return sorted(DRAFTS_DIR.glob("*.yaml"))
