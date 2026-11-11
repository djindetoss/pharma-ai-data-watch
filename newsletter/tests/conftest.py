import copy

import pytest

from newsletter import load_config


@pytest.fixture(scope="session")
def cfg():
    return load_config()


def make_item(**kw):
    base = {"id": "x", "type": "news", "title": "Title", "excerpt": "", "source": "Src",
            "date": "2026-11-05", "url": "https://example.org/a", "tags": [], "category": "News"}
    base.update(kw)
    return base


@pytest.fixture
def edition():
    it = {"id": "a1", "title": "EMA publishes reflection paper on AI <in> the lifecycle",
          "url": "https://www.ema.europa.eu/en/news/x?a=1&b=2", "source": "EMA", "date": "2026-11-04",
          "type": "Regulatory", "tags": ["Guidelines & policy"], "summary": "A plain summary.",
          "comment": "Interesting, but let's see if it holds up.",
          "why_it_matters": "Directly relevant to assessors.", "score": 9.0, "score_reason": "test"}
    paper = dict(it, id="p1", title="LLMs to draft SmPC sections", type="Scientific article",
                 source="medRxiv", url="https://doi.org/10.1101/2026.11.01.123456")
    news = dict(it, id="n1", title="FDA pilots AI review assistant", source="FDA")
    return copy.deepcopy({
        "edition_date": "2026-11-10", "edition_number": 3,
        "period": {"start": "2026-10-28", "end": "2026-11-10"},
        "editorial": "Hello community.\n\nSecond paragraph.",
        "highlight": it, "scientific_articles": [paper], "news": [news], "runners_up": [], "stats": {},
    })
