"""Link verification: every link in an edition must open the page in one click.

For each URL:
  1. strip tracking / feed parameters (utm_*, ?rss=1, ?af=R…);
  2. request it and follow redirects (doi.org, feed proxies, http→https…);
  3. keep the final address when it is a real page, so the e-mail links straight
     to it;
  4. classify the result: ok, blocked (the site refuses robots but works in a
     browser: 401/403/429), or broken (404/410, DNS error, timeout…).

Broken In-brief lines are removed; broken featured items are kept but flagged
in the draft (`link_check`) so the reviewer decides.

Note: some mail clients wrap every link in their own redirect for security
(Gmail "google.com/url?q=…", Outlook "safelinks.protection.outlook.com").
That happens in the recipient's mailbox and cannot be changed by the sender;
the address in the e-mail itself is the direct one.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

log = logging.getLogger(__name__)

TIMEOUT = 15
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en",
}
# Query parameters that only track the click or the feed it came from.
TRACKING_PARAMS = {"rss", "af", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
                   "cmpid", "src", "source", "feed", "feedtype", "dgcid", "s_cid", "ito", "ncid"}
TRACKING_PREFIXES = ("utm_",)
# A redirect to one of these is not the article: keep the original address.
NOT_A_PAGE = ("consent", "login", "signin", "sign-in", "captcha", "cookie", "/auth/", "authorize",
              "/sso", "paywall", "/subscribe")
BLOCKED = {401, 403, 405, 429, 999}


def clean_url(url: str) -> str:
    """Remove tracking / feed parameters and the fragment; keep everything else."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)]
    scheme = "https" if parts.scheme == "http" else parts.scheme
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query, doseq=True), ""))


def _fetch(url: str) -> tuple[int | str, str]:
    """Return (status or error name, final URL)."""
    last: tuple[int | str, str] = ("ERR", url)
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status, r.url
        except urllib.error.HTTPError as e:
            last = (e.code, url)
        except Exception as e:  # DNS, TLS, timeout…
            last = (type(e).__name__, url)
    return last


def check(url: str) -> dict:
    """Verify one link. Returns {url, status, state, original}."""
    original = url
    cleaned = clean_url(url)
    status, final = _fetch(cleaned)
    if isinstance(status, int) and 200 <= status < 400:
        state = "ok"
        best = clean_url(final)
        if any(k in best.lower() for k in NOT_A_PAGE):
            best = cleaned
    elif isinstance(status, int) and status in BLOCKED:
        state, best = "blocked", cleaned        # works in a browser, not for robots
    else:
        state, best = "broken", cleaned
    return {"url": best, "status": status, "state": state, "original": original}


def check_many(urls: list[str], workers: int = 8) -> dict[str, dict]:
    unique = list(dict.fromkeys(urls))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(check, unique))
    return dict(zip(unique, results))


def verify_edition(edition: dict) -> dict:
    """Check every link in an edition (in place). Returns a summary for stats."""
    featured = ([edition["highlight"]] if edition.get("highlight") else []) + \
        edition.get("scientific_articles", []) + edition.get("news", [])
    briefs = [b for g in edition.get("in_brief") or [] for b in g["items"]]
    results = check_many([it["url"] for it in featured + briefs])

    summary = {"checked": len(results), "ok": 0, "blocked": 0, "broken": 0, "rewritten": 0,
               "removed_from_in_brief": []}
    for r in results.values():
        summary[r["state"]] += 1
        if r["url"] != r["original"]:
            summary["rewritten"] += 1

    for it in featured:
        r = results[it["url"]]
        it["url"] = r["url"]
        if r["state"] == "broken":
            it["link_check"] = f"BROKEN ({r['status']}) – check or remove this item"
        else:
            it.pop("link_check", None)
    for g in edition.get("in_brief") or []:
        keep = []
        for b in g["items"]:
            r = results[b["url"]]
            if r["state"] == "broken":
                summary["removed_from_in_brief"].append(f"{b['url']} ({r['status']})")
                continue
            b["url"] = r["url"]
            keep.append(b)
        g["items"] = keep
    if edition.get("in_brief"):
        edition["in_brief"] = [g for g in edition["in_brief"] if g["items"]]
    log.info("Links: %(checked)d checked, %(ok)d ok, %(blocked)d blocked by the site, "
             "%(broken)d broken, %(rewritten)d rewritten", summary)
    return summary
