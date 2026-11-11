#!/usr/bin/env python3
"""Send a newsletter edition by e-mail (SMTP, Python standard library only).

The message is built to survive being forwarded from a private mailbox to
Outlook:
  multipart/mixed
  ├── multipart/alternative
  │   ├── text/plain   (readable plain-text version)
  │   └── text/html    (600 px table layout, inline CSS)
  └── IncreaseNET-AI-Newsletter-YYYY-MM-DD.html   (attachment)
The newsletter is NOT published on the web: the e-mail (and its attachment) is
the only distribution channel. The logo is referenced by an absolute URL (raw
file in the repository) – no base64, no CID image, which Outlook drops on forward.

All settings come from environment variables – nothing is stored in the repo:
  SMTP_HOST, SMTP_PORT (465 = implicit TLS, otherwise STARTTLS),
  SMTP_USER, SMTP_PASSWORD (an app password), NEWSLETTER_TO, NEWSLETTER_FROM
  NEWSLETTER_TO may contain several comma-separated addresses.

Usage (from the repository root):
  python -m newsletter.send_email --edition 2026-11-10            # final edition
  python -m newsletter.send_email --draft newsletter/drafts/2026-11-10.yaml --pr-url URL
  ... --dry-run [--out path.eml]                                   # write .eml, do not send
"""
from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

if __package__ in (None, ""):          # allow `python newsletter/send_email.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "newsletter"

from newsletter import EDITIONS_DIR, PKG_DIR, load_config  # noqa: E402
from newsletter.render import attachment_name, load_edition, render_html, render_text, subject  # noqa: E402

REQUIRED = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NEWSLETTER_TO", "NEWSLETTER_FROM")


def build_message(edition: dict, cfg: dict, *, draft: bool, pr_url: str | None,
                  sender: str, recipients: str) -> EmailMessage:
    mode = "draft" if draft else "email"
    html = render_html(edition, cfg, mode, pr_url=pr_url)
    text = render_text(edition, cfg, mode, pr_url=pr_url)

    msg = EmailMessage()
    msg["Subject"] = subject(edition, cfg, draft=draft)
    msg["From"] = sender
    msg["To"] = recipients
    msg["Date"] = formatdate(localtime=True)
    domain = sender.rsplit("@", 1)[-1] if "@" in sender else "increasenet.local"
    msg["Message-ID"] = make_msgid(domain=domain)
    msg.set_content(text, subtype="plain", charset="utf-8")
    msg.add_alternative(html, subtype="html", charset="utf-8")
    # The HTML edition as a file the recipient can open, copy into Outlook or forward as is.
    msg.add_attachment(html.encode("utf-8"), maintype="text", subtype="html",
                       filename=attachment_name(edition))
    return msg


def send(msg: EmailMessage, env: dict) -> None:
    host, port = env["SMTP_HOST"], int(env["SMTP_PORT"])
    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.starttls(context=ctx)
            s.login(env["SMTP_USER"], env["SMTP_PASSWORD"])
            s.send_message(msg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--edition", help="date of a validated edition (newsletter/editions/DATE.yaml)")
    src.add_argument("--draft", type=Path, help="path to a draft YAML (sent with a [DRAFT] prefix)")
    ap.add_argument("--pr-url", help="pull request URL shown in the draft banner")
    ap.add_argument("--dry-run", action="store_true", help="write a .eml file instead of sending")
    ap.add_argument("--out", type=Path, help="output path for --dry-run (default newsletter/out/<date>.eml)")
    args = ap.parse_args(argv)

    cfg = load_config()
    path = args.draft if args.draft else EDITIONS_DIR / f"{args.edition}.yaml"
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        return 2
    edition = load_edition(path)
    draft = args.draft is not None

    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if args.dry_run:
        sender = os.environ.get("NEWSLETTER_FROM", "newsletter@example.invalid")
        rcpt = os.environ.get("NEWSLETTER_TO", "you@example.invalid")
    else:
        if missing:
            print("Missing environment variables: " + ", ".join(missing)
                  + "\nConfigure them as GitHub secrets (see newsletter/README.md).", file=sys.stderr)
            return 3
        sender, rcpt = os.environ["NEWSLETTER_FROM"], os.environ["NEWSLETTER_TO"]

    msg = build_message(edition, cfg, draft=draft, pr_url=args.pr_url, sender=sender, recipients=rcpt)

    if args.dry_run:
        out = args.out or PKG_DIR / "out" / f"{edition['edition_date']}{'-draft' if draft else ''}.eml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes(msg))
        print(f"Dry run – message written to {out}")
        return 0

    send(msg, os.environ)
    n = len([r for r in rcpt.split(",") if r.strip()])
    print(f"Sent '{msg['Subject']}' to {n} recipient(s).")   # addresses are not logged
    return 0


if __name__ == "__main__":
    sys.exit(main())
