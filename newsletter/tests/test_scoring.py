from newsletter.brief import PAPERS_SECTION, brief_candidate, group
from newsletter.draft import auto_intro, select
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
    no_fill = dict(cfg, selection=dict(cfg["selection"], fill_to_min=False))
    papers, news, runners = select(items, no_fill, use_llm=False)
    thr = cfg["selection"]["min_prefilter_score"]
    assert len(papers) <= cfg["selection"]["papers"]["max"]
    assert len(news) <= cfg["selection"]["news"]["max"]
    assert all(i["prefilter_score"] >= thr for i in papers + news)
    assert not {i["id"] for i in runners} & {i["id"] for i in papers + news}


def test_select_uses_llm_score_when_available(cfg):
    items = [make_item(id="a", category="News", prefilter_score=9, llm_score=3),
             make_item(id="b", category="News", prefilter_score=3, llm_score=9)]
    _, news, _ = select(items, dict(cfg, selection=dict(cfg["selection"], fill_to_min=False)), use_llm=True)
    assert [i["id"] for i in news] == ["b"]


def test_clinical_ml_without_medicines_link_is_dropped(cfg):
    it = make_item(title="Machine learning model predicts amputation risk in diabetes",
                   excerpt="A deep learning model was validated. Published in Frontiers in Cardiovascular Medicine.",
                   category="Scientific article")
    assert score_item(it, cfg)["excluded_reason"] == "not about medicines"


def test_ai_for_medicines_regulation_passes_both_gates(cfg):
    it = make_item(title="LLM-assisted review of marketing authorisation dossiers at a medicines agency",
                   excerpt="A large language model extracted pharmacokinetic data from clinical trial reports.")
    assert score_item(it, cfg)["excluded_reason"] is None


def test_hyphenated_compounds_match_keywords():
    assert count_hits(["artificial intelligence"], "Artificial intelligence-driven pharmacovigilance") == 1
    assert count_hits(["large language model"], "large language model-assisted ADR surveillance") == 1
    assert count_hits(["AI"], "AI-enabled review") == 1


def test_fill_to_min_tops_up_and_flags(cfg):
    items = [make_item(id="p0", category="Scientific article", prefilter_score=9.0)]
    items += [make_item(id=f"p{i}", category="Scientific article", prefilter_score=5.0) for i in range(1, 6)]
    items += [make_item(id="weak", category="Scientific article", prefilter_score=1.0)]
    papers, _, _ = select(items, dict(cfg, selection=dict(cfg["selection"], fill_to_min=True)), use_llm=False)
    assert len(papers) == cfg["selection"]["papers"]["min"]
    assert not papers[0].get("below_threshold") and all(p.get("below_threshold") for p in papers[1:])
    papers, _, _ = select(items, dict(cfg, selection=dict(cfg["selection"], fill_to_min=False)), use_llm=False)
    assert len(papers) == 1


def test_brief_candidate_sections(cfg):
    sec = lambda **kw: (brief_candidate(make_item(**kw), cfg) or {}).get("brief_section")
    assert sec(title="Hackers use AI malware in data breach at hospital network",
               excerpt="cybersecurity attack") == "Safety, security & privacy"
    assert sec(title="Deep learning predicts drug toxicity", excerpt="machine learning model",
               category="Scientific article") == PAPERS_SECTION
    assert sec(title="AI stock rally continues", excerpt="AI") is None          # exclusion
    assert sec(title="New phone camera", excerpt="nothing about AI here") is None


def test_group_caps_sections(cfg):
    items = [make_item(id=f"s{i}", brief_section="Tools & releases") for i in range(20)]
    groups = group(items, cfg)
    assert len(groups) == 1 and len(groups[0]["items"]) == cfg["in_brief"]["max_per_section"]


def test_auto_intro_is_clear(edition):
    txt = auto_intro(3, "28 Oct – 10 Nov 2026", edition["highlight"], edition["scientific_articles"],
                     edition["news"], edition["in_brief"])
    assert "edition #3" in txt and "28 Oct – 10 Nov 2026" in txt and "1 one-line notes" in txt
    assert "scientific articles" in txt and "In-brief" in txt and "EDIT ME" not in txt
