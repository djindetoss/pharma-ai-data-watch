from newsletter.dedup import deduplicate, extract_doi, normalise_url

from .conftest import make_item


def test_extract_doi_from_url():
    assert extract_doi({"url": "https://doi.org/10.1101/2026.11.01.123456v1?x=1"}) == "10.1101/2026.11.01.123456v1"
    assert extract_doi({"url": "https://example.org/no-doi"}) is None


def test_normalise_url_strips_tracking_www_and_slash():
    a = normalise_url("https://www.ema.europa.eu/en/news/item/?utm_source=rss&id=3")
    b = normalise_url("http://ema.europa.eu/en/news/item?id=3")
    assert a == b


def test_same_doi_different_urls_is_duplicate():
    items = [make_item(id="1", url="https://doi.org/10.1101/2026.10.30.1234", title="Alpha study"),
             make_item(id="2", url="https://www.biorxiv.org/content/10.1101/2026.10.30.1234", title="Completely different title")]
    kept, n = deduplicate(items)
    assert n == 1 and len(kept) == 1


def test_same_url_is_duplicate():
    items = [make_item(id="1", url="https://x.org/a?utm_medium=e"), make_item(id="2", url="https://www.x.org/a/", title="Other")]
    assert deduplicate(items)[1] == 1


def test_near_identical_titles_are_duplicates_and_richest_kept():
    items = [make_item(id="news", url="https://a.org/1", title="EMA publishes AI reflection paper", excerpt="short"),
             make_item(id="paper", url="https://b.org/2", title="EMA publishes the AI reflection paper!",
                       excerpt="a much longer excerpt", category="Scientific article")]
    kept, n = deduplicate(items)
    assert n == 1 and kept[0]["id"] == "paper"


def test_distinct_items_are_kept():
    items = [make_item(id="1", url="https://a.org/1", title="FDA guidance on AI in drug development"),
             make_item(id="2", url="https://a.org/2", title="EHDS implementing act on data quality labels")]
    assert deduplicate(items)[1] == 0
