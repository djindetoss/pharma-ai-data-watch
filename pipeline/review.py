#!/usr/bin/env python3
"""
Pharma AI & Data Watch — Draft review tool
------------------------------------------
Interactive CLI to review articles that were fetched by pipeline.py
but did not meet the auto-approve threshold.

Usage:
  python review.py                  # review today's draft file
  python review.py --file drafts/drafts_2026-04-22.json
  python review.py --approve-all    # approve all drafts without reviewing
  python review.py --reject-all     # discard all drafts

Controls:
  a / y  → approve and add to portal
  r / n  → reject (discard)
  s      → skip (leave in draft for later)
  e      → edit title or excerpt before approving
  q      → quit and save progress
"""

import sys
import json
import argparse
import textwrap
from datetime import datetime
from pathlib import Path

BASE_DIR     = Path(__file__).parent
CONFIG_FILE  = BASE_DIR / "config.json"

with CONFIG_FILE.open() as f:
    CONFIG = json.load(f)

OUTPUT_JSON = (BASE_DIR / CONFIG["output"]["articles_json"]).resolve()
DRAFTS_DIR  = BASE_DIR / CONFIG["output"]["drafts_dir"]

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BLUE   = "\033[34m"

def c(color, text): return f"{color}{text}{RESET}"
def hr(char="─", n=70): return char * n


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            print(c(RED, f"Error: {path} is not valid JSON."))
    return []


def save_json(path: Path, data: list):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def find_latest_draft() -> Path | None:
    files = sorted(DRAFTS_DIR.glob("drafts_*.json"), reverse=True)
    return files[0] if files else None


def display_article(article: dict, index: int, total: int):
    print()
    print(c(BOLD, hr("═")))
    print(c(CYAN, f"  Article {index}/{total}"))
    print(hr())
    print(c(BOLD, f"  Type   : ") + article.get("type", "?").upper())
    print(c(BOLD, f"  Source : ") + article.get("source", "?"))
    print(c(BOLD, f"  Date   : ") + article.get("date", "?"))
    print(c(BOLD, f"  Score  : ") + str(article.get("_score", "?")))
    print(c(BOLD, f"  Badge  : ") + article.get("badge", "—"))
    print()
    print(c(YELLOW, "  TITLE"))
    print(textwrap.fill(article.get("title", ""), width=70, initial_indent="  ", subsequent_indent="  "))
    print()
    print(c(YELLOW, "  EXCERPT"))
    print(textwrap.fill(article.get("excerpt", ""), width=70, initial_indent="  ", subsequent_indent="  "))
    print()
    print(c(YELLOW, "  URL"))
    print(f"  {article.get('url', '#')}")
    print()
    print(c(YELLOW, "  TAGS"))
    print("  " + ", ".join(article.get("tags", [])))
    print()
    print(hr())
    print(c(DIM, "  [a]pprove   [r]eject   [s]kip   [e]dit   [q]uit"))
    print(hr())


def prompt_edit(article: dict) -> dict:
    print(c(CYAN, "\n  Edit mode — press Enter to keep current value\n"))

    new_title = input(f"  Title [{article['title'][:60]}...]: ").strip()
    if new_title:
        article["title"] = new_title

    new_excerpt = input(f"  Excerpt (current length {len(article['excerpt'])} chars — retype or Enter): ").strip()
    if new_excerpt:
        article["excerpt"] = new_excerpt

    new_badge = input(f"  Badge [{article.get('badge', '')}]: ").strip()
    if new_badge:
        article["badge"] = new_badge

    new_tags = input(f"  Tags (comma-separated) [{', '.join(article.get('tags', []))}]: ").strip()
    if new_tags:
        article["tags"] = [t.strip() for t in new_tags.split(",") if t.strip()]

    featured = input("  Featured? [y/N]: ").strip().lower()
    article["featured"] = (featured == "y")

    return article


def clean_for_export(article: dict) -> dict:
    """Remove internal pipeline metadata before writing to articles.json."""
    return {k: v for k, v in article.items() if not k.startswith("_")}


# ── Main ──────────────────────────────────────────────────────────────────────

def review(draft_file: Path, approve_all: bool = False, reject_all: bool = False):
    drafts   = load_json(draft_file)
    approved = load_json(OUTPUT_JSON)
    existing_ids = {a["id"] for a in approved}

    if not drafts:
        print(c(GREEN, "No drafts to review. Everything is up to date."))
        return

    print(c(BOLD, f"\nReviewing {len(drafts)} draft(s) from {draft_file.name}\n"))

    remaining = []
    n_approved = 0
    n_rejected = 0
    n_skipped  = 0

    for i, article in enumerate(drafts, 1):
        if article["id"] in existing_ids:
            # Already in portal (approved in a previous session)
            continue

        if approve_all:
            approved.append(clean_for_export(article))
            n_approved += 1
            print(c(GREEN, f"  ✓ Auto-approved: {article['title'][:70]}"))
            continue

        if reject_all:
            n_rejected += 1
            print(c(RED, f"  ✗ Rejected: {article['title'][:70]}"))
            continue

        # ── Interactive review ──────────────────────────────────────
        display_article(article, i, len(drafts))

        while True:
            try:
                choice = input("  → ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"

            if choice in ("a", "y", "approve"):
                approved.append(clean_for_export(article))
                existing_ids.add(article["id"])
                n_approved += 1
                print(c(GREEN, "  ✓ Approved"))
                break

            elif choice in ("r", "n", "reject"):
                n_rejected += 1
                print(c(RED, "  ✗ Rejected"))
                break

            elif choice in ("s", "skip"):
                remaining.append(article)
                n_skipped += 1
                print(c(YELLOW, "  ○ Skipped (kept in draft)"))
                break

            elif choice in ("e", "edit"):
                article = prompt_edit(article)
                approved.append(clean_for_export(article))
                existing_ids.add(article["id"])
                n_approved += 1
                print(c(GREEN, "  ✓ Edited and approved"))
                break

            elif choice in ("q", "quit"):
                remaining += drafts[i - 1:]
                print(c(YELLOW, "\n  Quitting review early — progress saved."))
                break

            else:
                print(c(DIM, "  Unknown input. Use a / r / s / e / q"))

        else:
            continue
        if choice in ("q", "quit"):
            break

    # Sort approved: newest first
    approved.sort(key=lambda a: a.get("date", ""), reverse=True)
    approved = approved[:CONFIG["settings"]["max_total_articles"]]

    # Write portal articles
    save_json(OUTPUT_JSON, approved)

    # Update draft file with skipped items only
    save_json(draft_file, remaining)

    # Summary
    print()
    print(c(BOLD, hr("═")))
    print(c(GREEN,  f"  ✓ Approved : {n_approved}"))
    print(c(RED,    f"  ✗ Rejected : {n_rejected}"))
    print(c(YELLOW, f"  ○ Skipped  : {n_skipped}"))
    print(c(BOLD,   f"  Portal now has {len(approved)} articles"))
    print(hr("═"))
    print()


def main():
    parser = argparse.ArgumentParser(description="Pharma AI & Data Watch — draft review tool")
    parser.add_argument("--file",        type=Path, help="Specific draft file to review (default: latest)")
    parser.add_argument("--approve-all", action="store_true", help="Approve all drafts without reviewing")
    parser.add_argument("--reject-all",  action="store_true", help="Reject all drafts")
    parser.add_argument("--list",        action="store_true", help="List all draft files with counts")
    args = parser.parse_args()

    if args.list:
        files = sorted(DRAFTS_DIR.glob("drafts_*.json"), reverse=True)
        if not files:
            print("No draft files found.")
        for f in files:
            try:
                count = len(json.loads(f.read_text()))
                print(f"  {f.name}  —  {count} draft(s)")
            except Exception:
                print(f"  {f.name}  —  (unreadable)")
        return

    draft_file = args.file or find_latest_draft()

    if draft_file is None:
        print(c(GREEN, "No draft files found in drafts/. Run pipeline.py first."))
        sys.exit(0)

    if not draft_file.exists():
        print(c(RED, f"File not found: {draft_file}"))
        sys.exit(1)

    review(draft_file, approve_all=args.approve_all, reject_all=args.reject_all)


if __name__ == "__main__":
    main()
