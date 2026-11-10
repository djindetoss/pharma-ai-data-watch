from html.parser import HTMLParser

from newsletter.render import find_todos, period_label, render_archive, render_html, render_markdown, render_text, subject

VOID = {"meta", "link", "img", "br", "hr", "input", "col", "area", "base", "source", "wbr"}


class TagBalance(HTMLParser):
    """Minimal well-formedness check: every non-void tag is closed in order."""

    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.tags = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}>, open: {self.stack[-3:]}")
        else:
            self.stack.pop()


def parse(html):
    p = TagBalance()
    p.feed(html)
    p.close()
    return p


def test_email_html_is_valid_and_outlook_safe(edition, cfg):
    html = render_html(edition, cfg, "email")
    p = parse(html)
    assert not p.errors and not p.stack, (p.errors, p.stack)
    names = [t for t, _ in p.tags]
    assert "script" not in names
    assert not any(t == "link" and a.get("rel") == "stylesheet" for t, a in p.tags), "no external CSS/fonts"
    assert any(t == "table" and a.get("width") == "600" for t, a in p.tags)
    imgs = [a for t, a in p.tags if t == "img"]
    assert imgs and all(a["src"].startswith("https://djindetoss.github.io/") for a in imgs)
    assert "base64" not in html and "cid:" not in html
    assert "View this edition online" in html
    assert "https://djindetoss.github.io/pharma-ai-data-watch/newsletter/2026-11-10.html" in html
    assert "Why it matters for NCAs" in html and "Highlight of the period" in html
    assert "&lt;in&gt;" in html, "titles are HTML-escaped"
    assert cfg["colors"]["primary"] in html


def test_draft_mode_shows_banner_and_pr_link(edition, cfg):
    html = render_html(edition, cfg, "draft", pr_url="https://github.com/o/r/pull/7")
    assert "DRAFT" in html and "https://github.com/o/r/pull/7" in html


def test_web_mode_links_archive(edition, cfg):
    html = render_html(edition, cfg, "web")
    assert not parse(html).errors
    assert "All editions" in html and 'rel="canonical"' in html


def test_text_and_markdown(edition, cfg):
    txt = render_text(edition, cfg)
    assert "HIGHLIGHT OF THE PERIOD" in txt and "View this edition online:" in txt
    assert "<" not in txt.replace("<in>", "")
    md = render_markdown(edition, cfg)
    assert md.startswith("![IncreaseNET](https://") and "## Scientific articles" in md


def test_subject_and_period(edition, cfg):
    assert period_label(edition["period"]) == "28 Oct – 10 Nov 2026"
    assert subject(edition, cfg) == "IncreaseNET AI Community – Newsletter #3 (28 Oct – 10 Nov 2026)"
    assert subject(edition, cfg, draft=True).startswith("[DRAFT] ")


def test_find_todos(edition):
    assert find_todos(edition) == []
    edition["news"][0]["summary"] = "TODO: write"
    edition["editorial"] = "[EDIT ME]"
    assert len(find_todos(edition)) == 2


def test_archive_renders(cfg):
    html = render_archive([{"number": 1, "date": "2026-11-10", "period": {"start": "2026-10-28", "end": "2026-11-10"},
                            "items": 8, "highlight": "X"}], cfg)
    assert not parse(html).errors and "2026-11-10.html" in html
