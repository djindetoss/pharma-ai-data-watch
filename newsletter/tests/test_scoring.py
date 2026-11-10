from newsletter.draft import select
from newsletter.scoring import count_hits, prefilter, score_item

from .conftest import make_item


def test_acronyms_are_case_sensitive_words():
    assert count_hits(["AI"], "New AI tool") == 1
    assert count_hits(["AI"], "she said hello") == 0
    assert count_hits(["EMA"], "the Ema river") == 0


def test_regulatory_ai_item_scores_high(cfg):
    it = make_item(title="EMA reflection paper on AI in the medicinal product lifecycle",
                   excerpt="The EMA guidance addresses machine learning validation for regulatory assessment.",
                   source="EMA")
    s = score_item(it, cfg)
    assert s["excluded_reason"] is None
    assert s["prefilter_score"] >= cfg["selection"]["min_prefilter_score"]
    assert "regulatory_guidance" in s["themes"]


def test_item_without_ai_signal_is_dropped(cfg):
    it = make_item(title="EMA recommends approval of new antibiotic", excerpt="CHMP opinion.", source="EMA")
    assert score_item(it, cfg)["excluded_reason"] == "no AI/data signal"


def test_exclusion_in_title(cfg):
    it = make_item(title="AI startup raises $50m in funding round", excerpt="machine learning regulatory")
    assert score_item(it, cfg)["excluded_reason"].startswith("exclusion")


def test_tech_press_is_penalised(cfg):
    base = dict(title="LLM used to summarise clinical trial protocols",
                excerpt="A large language model drafted clinical trial summaries.")
    a = score_item(make_item(source="medRxiv", **base), cfg)["prefilter_score"]
    b = score_item(make_item(source="The Verge", **base), cfg)["prefilter_score"]
    assert a > b


def test_prefilter_sorts_descending(cfg):
    items = [make_item(id="low", title="AI in telecom", excerpt="AI"),
             make_item(id="high", title="FDA draft guidance on AI for regulatory decision-making",
                       excerpt="machine learning model validation credibility framework", source="FDA")]
    kept, _ = prefilter(items, cfg)
    assert kept and kept[0]["id"] == "high"


def test_select_respects_threshold_and_quotas(cfg):
    items = [make_item(id=f"p{i}", category="Scientific article", prefilter_score=9 - i * 0.5) for i in range(12)]
    items += [make_item(id=f"n{i}", category="News", prefilter_score=8 - i) for i in range(8)]
    papers, news, runners = select(items, cfg, use_llm=False)
    thr = cfg["selection"]["min_prefilter_score"]
    assert len(papers) <= cfg["selection"]["papers"]["max"]
    assert len(news) <= cfg["selection"]["news"]["max"]
    assert all(i["prefilter_score"] >= thr for i in papers + news)
    assert not {i["id"] for i in runners} & {i["id"] for i in papers + news}


def test_select_uses_llm_score_when_available(cfg):
    items = [make_item(id="a", category="News", prefilter_score=9, llm_score=3),
             make_item(id="b", category="News", prefilter_score=3, llm_score=9)]
    _, news, _ = select(items, cfg, use_llm=True)
    assert [i["id"] for i in news] == ["b"]
