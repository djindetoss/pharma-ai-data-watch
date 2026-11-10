"""Command-line entry point.

  python -m newsletter draft   [--end YYYY-MM-DD] [--days 14] [--no-llm]
  python -m newsletter render  newsletter/drafts/YYYY-MM-DD.yaml [--pr-url URL]
  python -m newsletter publish newsletter/drafts/YYYY-MM-DD.yaml [--force]
  python -m newsletter publish --pending          # every draft in newsletter/drafts/
  python -m newsletter due                        # exit 0 if an edition is due, 1 otherwise
  python -m newsletter archive                    # rebuild portal/newsletter/index.html
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from . import load_config
from .draft import build_draft, save_draft
from .publish import load_index, pending_drafts, publish, write_archive
from .render import find_todos, load_edition, relpath, render_draft_outputs


def _gh_output(**kv) -> None:
    """Expose values to later GitHub Actions steps."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def cmd_draft(args, cfg) -> int:
    end = date.fromisoformat(args.end) if args.end else date.today()
    draft, stats = build_draft(cfg, end, args.days, no_llm=args.no_llm)
    path = save_draft(draft)
    outputs = render_draft_outputs(path, cfg)
    print("\n" + "─" * 64)
    print(f"Draft written: {relpath(path)}")
    for kind, p in outputs.items():
        print(f"  {kind:9} {relpath(p)}")
    print("─" * 64)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    _gh_output(draft_path=relpath(path), edition_date=draft["edition_date"])
    return 0


def cmd_render(args, cfg) -> int:
    outputs = render_draft_outputs(Path(args.path), cfg, pr_url=args.pr_url)
    for kind, p in outputs.items():
        print(f"{kind:9} {relpath(p)}")
    todos = find_todos(load_edition(Path(args.path)))
    if todos:
        print("\n⚠ Still to edit:\n  - " + "\n  - ".join(todos))
    return 0


def cmd_publish(args, cfg) -> int:
    paths = pending_drafts() if args.pending else [Path(args.path)]
    if not paths:
        print("No pending draft.")
        _gh_output(published="")
        return 0
    done = [publish(p, cfg, force=args.force)["edition_date"] for p in paths]
    print("Published: " + ", ".join(done))
    _gh_output(published=" ".join(done))
    return 0


def cmd_due(args, cfg) -> int:
    freq = cfg["schedule"]["frequency_days"]
    index = load_index()
    if pending_drafts():
        print("A draft is already pending – not due.")
        return 1
    if not index:
        print("No edition yet – due.")
        return 0
    last = max(date.fromisoformat(e["date"]) for e in index)
    # 1-day tolerance so a weekly cron at the same hour does not slip a week
    due = date.today() >= last + timedelta(days=freq - 1)
    print(f"Last edition {last}, frequency {freq} days → {'due' if due else 'not due'}.")
    return 0 if due else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="python -m newsletter", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("draft", help="build a new draft")
    p.add_argument("--end", help="last day of the period (default today)")
    p.add_argument("--days", type=int, help="window length (default config schedule.window_days)")
    p.add_argument("--no-llm", action="store_true", help="keyword pre-filter only")
    p = sub.add_parser("render", help="re-render a draft after editing")
    p.add_argument("path")
    p.add_argument("--pr-url")
    p = sub.add_parser("publish", help="publish a reviewed draft")
    p.add_argument("path", nargs="?")
    p.add_argument("--pending", action="store_true")
    p.add_argument("--force", action="store_true", help="publish even if TODO markers remain")
    sub.add_parser("due", help="is a new edition due?")
    sub.add_parser("archive", help="rebuild the archive page")
    args = ap.parse_args(argv)
    cfg = load_config()
    if args.cmd == "publish" and not (args.pending or args.path):
        ap.error("publish needs a draft path or --pending")
    if args.cmd == "archive":
        print(relpath(write_archive(cfg)))
        return 0
    return {"draft": cmd_draft, "render": cmd_render, "publish": cmd_publish, "due": cmd_due}[args.cmd](args, cfg)


if __name__ == "__main__":
    sys.exit(main())
