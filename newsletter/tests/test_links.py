from newsletter import links


def test_clean_url_strips_tracking_and_feed_params():
    assert links.clean_url("https://ascpt.onlinelibrary.wiley.com/doi/10.1002/cpt.70558?af=R") == \
        "https://ascpt.onlinelibrary.wiley.com/doi/10.1002/cpt.70558"
    assert links.clean_url("https://www.medrxiv.org/content/10.64898/x.v1?rss=1") == "https://www.medrxiv.org/content/10.64898/x.v1"
    assert links.clean_url("http://www.statnews.com/a/?utm_campaign=rss&utm_source=x#top") == "https://www.statnews.com/a/"
    assert links.clean_url("https://example.org/s?q=ai&page=2") == "https://example.org/s?q=ai&page=2"


def _fake(responses):
    return lambda url: responses[url]


def test_verify_edition_rewrites_flags_and_removes(monkeypatch, edition):
    edition["highlight"]["url"] = "https://doi.org/10.1/x?utm_source=rss"
    edition["scientific_articles"][0]["url"] = "https://dead.example/paper"
    edition["news"][0]["url"] = "https://blocked.example/news"
    edition["in_brief"][0]["items"].append(dict(edition["in_brief"][0]["items"][0], id="b2", url="https://gone.example/"))
    monkeypatch.setattr(links, "_fetch", _fake({
        "https://doi.org/10.1/x": (200, "https://publisher.example/article/x?af=R"),
        "https://dead.example/paper": (404, "https://dead.example/paper"),
        "https://blocked.example/news": (403, "https://blocked.example/news"),
        "https://example.org/b1": (200, "https://example.org/b1"),
        "https://gone.example/": ("URLError", "https://gone.example/"),
    }))
    s = links.verify_edition(edition)
    assert edition["highlight"]["url"] == "https://publisher.example/article/x"       # followed + cleaned
    assert edition["scientific_articles"][0]["link_check"].startswith("BROKEN (404)")
    assert "link_check" not in edition["news"][0]                                     # blocked ≠ broken
    assert [b["id"] for b in edition["in_brief"][0]["items"]] == ["b1"]               # dead brief removed
    assert s["broken"] == 2 and s["blocked"] == 1 and s["rewritten"] == 1


def test_redirect_to_login_page_keeps_original(monkeypatch):
    monkeypatch.setattr(links, "_fetch", lambda u: (200, "https://idp.example/login?next=x"))
    assert links.check("https://journal.example/a")["url"] == "https://journal.example/a"


def test_broken_link_blocks_validation(edition):
    from newsletter.render import find_todos
    edition["news"][0]["link_check"] = "BROKEN (404) – check or remove this item"
    assert any("broken link" in t for t in find_todos(edition))
