"""Tests for small pipeline helpers (run: python -m pytest pipeline/tests -q)."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline as P  # noqa: E402

XML = """<PubmedArticle><Abstract>
<AbstractText Label="BACKGROUND">Pharmacovigilance &amp; <i>AI</i>.</AbstractText>
<AbstractText Label="RESULTS">Signals were detected earlier.</AbstractText>
</Abstract></PubmedArticle>"""


def test_pubmed_abstract_from_xml_keeps_only_abstract():
    assert P.pubmed_abstract_from_xml(XML) == "Pharmacovigilance & AI. Signals were detected earlier."
    assert P.pubmed_abstract_from_xml("<PubmedArticle/>") == ""


def test_pubmed_date_prefers_epub_and_never_future():
    today = datetime.now().strftime("%Y-%m-%d")
    assert P.pubmed_date({"epubdate": "2026 Oct 30", "pubdate": "2027 Jan"}) == min("2026-10-30", today)
    assert P.pubmed_date({"pubdate": "2099 Dec 11"}) == today
    assert P.pubmed_date({}) == today


def test_ai_or_data_gate_whole_words():
    assert P.has_ai_or_data_signal("A large language model-assisted review of SmPCs")
    assert P.has_ai_or_data_signal("EHDS implementing act")
    assert not P.has_ai_or_data_signal("Gene regulator storage said fragment")   # no 'ai'/'rag' substrings
    assert not P.has_ai_or_data_signal("FDA approves new antibiotic")
