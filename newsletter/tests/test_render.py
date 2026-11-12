from html.parser import HTMLParser

from newsletter.render import find_todos, period_label, render_html, render_markdown, render_text, subject

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
    assert imgs and all(a["src"] == cfg["logo_url"] and a["src"].startswith("https://") for a in imgs)
    assert "base64" not in html and "cid:" not in html
    # e-mail only: no link to a web version / GitHub Pages
    assert "github.io" not in html and "View this edition online" not in html
    assert "IncreaseNET-AI-Newsletter-2026-11-10.html" in html, "points to the attachment as fallback"
    assert "Why it matters for NCAs" in html and "Highlight of the period" in html
    assert "let&#39;s see if it holds up" in html, "comment is rendered (and escaped)"
    assert "&lt;in&gt;" in html, "titles are HTML-escaped"
    assert cfg["colors"]["primary"] in html


def test_draft_mode_shows_banner_and_pr_link(edition, cfg):
    html = render_html(edition, cfg, "draft", pr_url="https://github.com/o/r/pull/7")
    assert "DRAFT" in html and "https://github.com/o/r/pull/7" in html


def test_text_and_markdown(edition, cfg):
    txt = render_text(edition, cfg)
    assert "let's see if it holds up" in txt and "let's see if it holds up" in render_markdown(edition, cfg)
    assert "HIGHLIGHT OF THE PERIOD" in txt and "attached HTML file" in txt and "github.io" not in txt
    assert "<" not in txt.replace("<in>", "").replace("<again>", "")
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
    edition["scientific_articles"][0]["comment"] = "TODO: comment"
    assert len(find_todos(edition)) == 3


def test_item_without_comment_renders(edition, cfg):
    del edition["news"][0]["comment"]
    html = render_html(edition, cfg, "email")
    assert html.count("let&#39;s see if it holds up") == 2  # highlight + paper only



def test_featured_items_are_numbered_and_in_brief_rendered(edition, cfg):
    html = render_html(edition, cfg, "email")
    assert "#1</span>" in html and "#2</span>" in html and "#3</span>" in html
    assert "In brief" in html and "A chatbot leaked data &lt;again&gt;." in html and "https://example.org/b1" in html
    txt = render_text(edition, cfg)
    assert "#3 [Regulatory] FDA pilots AI review assistant" in txt and "IN BRIEF" in txt and "(Heise)" in txt
    assert "## In brief" in render_markdown(edition, cfg)


def test_edition_without_in_brief_still_renders(edition, cfg):
    del edition["in_brief"]
    assert "In brief" not in render_html(edition, cfg, "email")


def test_full_address_is_visible_for_every_link(edition, cfg):
    import re
    html = render_html(edition, cfg, "email")
    for url in re.findall(r'href="([^"]+)"', html):
        assert f">{url}</a>" in html, f"address not shown as text: {url}"
