from newsletter.collect import _host_excluded


def test_ema_domain_excluded():
    d = ["ema.europa.eu"]
    assert _host_excluded("https://www.ema.europa.eu/en/news/x", d)
    assert _host_excluded("https://ema.europa.eu/x", d)
    assert not _host_excluded("https://www.statnews.com/2026/ema-ai-paper", d)
    assert not _host_excluded("https://notema.europa.eu/x", d)
    assert not _host_excluded("https://health.ec.europa.eu/x", d)
