"""Render a draft/edition YAML into e-mail HTML, plain text and Markdown (e-mail only, no web page)."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import PKG_DIR, REPO_ROOT

TEMPLATES = PKG_DIR / "templates"
TODO_RE = re.compile(r"\bTODO\b|EDIT ME")
SECTIONS = ("highlight", "scientific_articles", "news")


def load_edition(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for key in ("scientific_articles", "news"):
        data[key] = data.get(key) or []
    return data


def fmt_date(iso: str) -> str:
    d = date.fromisoformat(str(iso))
    return f"{d.day} {d.strftime('%b')} {d.year}"


def period_label(period: dict) -> str:
    s, e = date.fromisoformat(str(period["start"])), date.fromisoformat(str(period["end"]))
    if s.year == e.year:
        return f"{s.day} {s.strftime('%b')} – {e.day} {e.strftime('%b')} {e.year}"
    return f"{fmt_date(s.isoformat())} – {fmt_date(e.isoformat())}"


def subject(edition: dict, cfg: dict, draft: bool = False) -> str:
    s = f"{cfg['title']} #{edition['edition_number']} ({period_label(edition['period'])})"
    return f"[DRAFT] {s}" if draft else s


def attachment_name(edition: dict) -> str:
    return f"IncreaseNET-AI-Newsletter-{edition['edition_date']}.html"


def find_todos(edition: dict) -> list[str]:
    """Return human-readable locations of remaining TODO / EDIT ME markers."""
    issues = []
    if TODO_RE.search(edition.get("editorial") or ""):
        issues.append("editorial")
    items = ([edition["highlight"]] if edition.get("highlight") else []) + edition["scientific_articles"] + edition["news"]
    for it in items:
        for field in ("summary", "comment", "why_it_matters"):
            if TODO_RE.search(str(it.get(field) or "")):
                issues.append(f"{field} of '{it['title'][:60]}'")
    return issues


def urls(cfg: dict, edition: dict) -> dict:
    return {"logo": cfg["logo_url"]}


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "j2"], default_for_string=False),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["fmt_date"] = fmt_date
    return env


def context(edition: dict, cfg: dict, mode: str, pr_url: str | None = None, logo_url: str | None = None) -> dict:
    u = urls(cfg, edition)
    if logo_url:
        u["logo"] = logo_url
    return {"e": edition, "cfg": cfg, "c": cfg["colors"], "u": u, "mode": mode,
            "pr_url": pr_url, "period": period_label(edition["period"]),
            "attachment": attachment_name(edition),
            "subject": subject(edition, cfg, draft=(mode == "draft"))}


def render_html(edition: dict, cfg: dict, mode: str = "email", **kw) -> str:
    """mode: 'email' (final e-mail) or 'draft' (e-mail with DRAFT banner)."""
    tpl = "email.html.j2"
    return _env().get_template(tpl).render(**context(edition, cfg, mode, **kw))


def render_text(edition: dict, cfg: dict, mode: str = "email", **kw) -> str:
    env = _env()
    env.autoescape = False
    return env.get_template("newsletter.txt.j2").render(**context(edition, cfg, mode, **kw))


def render_markdown(edition: dict, cfg: dict) -> str:
    env = _env()
    env.autoescape = False
    return env.get_template("newsletter.md.j2").render(**context(edition, cfg, "email"))


def render_draft_outputs(yaml_path: Path, cfg: dict, pr_url: str | None = None) -> dict[str, Path]:
    """Render a draft next to its YAML: .email.html, .preview.html (local logo), .txt, .md."""
    edition = load_edition(yaml_path)
    stem = yaml_path.with_suffix("")
    local_logo = "../assets/increasenet-logo.png"  # relative to newsletter/drafts/
    out = {
        "email": stem.with_suffix(".email.html"),
        "preview": stem.with_suffix(".preview.html"),
        "text": stem.with_suffix(".txt"),
        "markdown": stem.with_suffix(".md"),
    }
    out["email"].write_text(render_html(edition, cfg, "draft", pr_url=pr_url), encoding="utf-8")
    out["preview"].write_text(render_html(edition, cfg, "draft", pr_url=pr_url, logo_url=local_logo), encoding="utf-8")
    out["text"].write_text(render_text(edition, cfg, "draft", pr_url=pr_url), encoding="utf-8")
    out["markdown"].write_text(render_markdown(edition, cfg), encoding="utf-8")
    return out


def relpath(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)
