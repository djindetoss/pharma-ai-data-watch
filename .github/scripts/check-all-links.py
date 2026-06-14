#!/usr/bin/env python3
"""
check-all-links.py
Universal link checker for Pharma AI & Data Watch

Covers:
  1. Static HTML links  — footer, nav, pillar cards in *.html pages
  2. Pipeline RSS feeds — all feeds in pipeline/config.json
  3. Recent articles    — URLs in portal/js/articles.json (last RECENT_DAYS days)
  4. Events             — URLs in portal/data/events.json (with staleness check)

Output: /tmp/link_report.md  (read by the GitHub Actions step)
Exit 1 if any hard failures (broken static links, dead feeds, broken events).
Exit 0 if only soft warnings (stale events, some article 404s — expected).
"""

import json, re, sys, ssl, time, os, urllib.request, urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Config ─────────────────────────────────────────────────────────────────────
RECENT_DAYS       = 30    # check articles published in the last N days
MAX_ARTICLE_CHECK = 60    # max articles to HTTP-check (avoid overloading)
EVENT_STALE_DAYS  = 90    # days before an event url_verified is considered stale
TIMEOUT           = 12    # HTTP timeout (seconds)
SLEEP             = 0.25  # delay between requests

# Domains that legitimately block bots (403/401) but are accessible in browser
BOT_BLOCKED_DOMAINS = {
    'amia.org', 'aiche.org', 'nejm.org', 'thelancet.com', 'jamanetwork.com',
    'nature.com', 'science.org', 'cell.com', 'bmj.com', 'wiley.com',
    'springer.com', 'elsevier.com', 'tandfonline.com', 'sagepub.com',
    'journals.lww.com', 'karger.com', 'mdpi.com',
}

# Static links to SKIP (fonts, own site, CDN)
SKIP_PATTERNS = [
    'fonts.googleapis.com', 'fonts.gstatic.com',
    'djindetoss.github.io',
]

TODAY = date.today().isoformat()

# ── HTTP helper ────────────────────────────────────────────────────────────────
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode    = ssl.CERT_NONE

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.9',
}

def check_url(url):
    """Returns (status_code_or_error_str, final_url_after_redirect)"""
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return str(r.status), r.url
        except urllib.error.HTTPError as e:
            if method == 'HEAD':
                continue  # retry with GET
            return str(e.code), url
        except Exception as e:
            if method == 'HEAD':
                continue
            return f'ERR:{type(e).__name__}', url
    return 'ERR:UNKNOWN', url

def is_ok(status):
    return status in ('200', '201', '301', '302', '303', '307', '308')

def is_bot_blocked(status, url):
    domain = urllib.parse.urlparse(url).netloc.lstrip('www.')
    return status in ('403', '401') and any(d in domain for d in BOT_BLOCKED_DOMAINS)

import urllib.parse

# ── 1. Static HTML links ───────────────────────────────────────────────────────
def check_static_html():
    results = {'ok': [], 'broken': [], 'skipped': []}
    html_files = list((ROOT / 'portal').glob('*.html'))
    seen = set()

    for html_file in html_files:
        text = html_file.read_text(encoding='utf-8', errors='ignore')
        urls = re.findall(r'href="(https://[^"]+)"', text)
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            if any(p in url for p in SKIP_PATTERNS):
                results['skipped'].append(url)
                continue
            # Skip event URLs — covered by events.json
            if html_file.name == 'events.html':
                continue

            status, final = check_url(url)
            ok = is_ok(status) or is_bot_blocked(status, url)
            entry = {'url': url, 'status': status, 'file': html_file.name}
            if ok:
                results['ok'].append(entry)
            else:
                results['broken'].append(entry)
            time.sleep(SLEEP)

    return results

# ── 2. Pipeline RSS feeds ──────────────────────────────────────────────────────
def check_feeds():
    results = {'ok': [], 'broken': []}
    config_path = ROOT / 'pipeline' / 'config.json'
    if not config_path.exists():
        return results

    with open(config_path) as f:
        config = json.load(f)

    seen = set()
    for section in ['rss_sources', 'data_sources', 'ai_news_sources', 'event_sources']:
        v = config.get(section, {})
        if not isinstance(v, dict) or not v.get('enabled', True):
            continue
        for feed in v.get('feeds', []):
            url  = feed.get('url', '')
            name = feed.get('name', url)
            if not url or url in seen:
                continue
            seen.add(url)

            status, final = check_url(url)
            ok = is_ok(status) or is_bot_blocked(status, url)
            entry = {'name': name, 'url': url, 'status': status}
            if ok:
                results['ok'].append(entry)
            else:
                results['broken'].append(entry)
            time.sleep(SLEEP)

    return results

# ── 3. Recent articles ─────────────────────────────────────────────────────────
def check_articles():
    results = {'ok': [], 'broken': [], 'skipped': []}
    articles_path = ROOT / 'portal' / 'js' / 'articles.json'
    if not articles_path.exists():
        return results

    with open(articles_path) as f:
        articles = json.load(f)

    cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    recent = [a for a in articles if (a.get('date') or '') >= cutoff and a.get('url')]
    recent.sort(key=lambda a: a.get('date', ''), reverse=True)
    recent = recent[:MAX_ARTICLE_CHECK]

    for art in recent:
        url   = art.get('url', '')
        title = art.get('title', url)[:80]
        src   = art.get('source', '')

        # Skip known paywalled/bot-blocked academic domains
        domain = urllib.parse.urlparse(url).netloc.lstrip('www.')
        if is_bot_blocked('403', url):
            results['skipped'].append({'url': url, 'title': title, 'reason': 'bot-blocked domain'})
            continue

        status, final = check_url(url)
        ok = is_ok(status)
        # Treat academic 403/401 as OK (paywall, not broken)
        if not ok and status in ('403', '401'):
            ok = True

        entry = {'url': url, 'title': title, 'source': src, 'status': status,
                 'date': art.get('date', '')}
        if ok:
            results['ok'].append(entry)
        else:
            results['broken'].append(entry)
        time.sleep(SLEEP)

    return results

# ── 4. Events ──────────────────────────────────────────────────────────────────
def check_events():
    results = {'ok': [], 'broken': [], 'stale': []}
    events_path = ROOT / 'portal' / 'data' / 'events.json'
    if not events_path.exists():
        return results

    with open(events_path) as f:
        events = json.load(f)

    seen = set()
    for ev in events:
        url      = ev.get('url', '')
        ev_id    = ev.get('id', '?')
        title    = ev.get('title', '')[:80]
        verified = ev.get('url_verified', '')

        # Staleness check
        try:
            vdate = date.fromisoformat(verified)
            days  = (date.today() - vdate).days
            if days > EVENT_STALE_DAYS:
                results['stale'].append({
                    'id': ev_id, 'title': title, 'url': url,
                    'days': days, 'url_verified': verified
                })
        except Exception:
            results['stale'].append({
                'id': ev_id, 'title': title, 'url': url,
                'days': 9999, 'url_verified': verified or 'MISSING'
            })

        if not url or url in seen:
            continue
        seen.add(url)

        status, final = check_url(url)
        ok = is_ok(status) or is_bot_blocked(status, url)
        entry = {'id': ev_id, 'title': title, 'url': url, 'status': status}
        if ok:
            results['ok'].append(entry)
        else:
            results['broken'].append(entry)
        time.sleep(SLEEP)

    return results

# ── Build report ───────────────────────────────────────────────────────────────
def fmt_table(rows, cols):
    """Simple markdown table"""
    header = '| ' + ' | '.join(cols) + ' |'
    sep    = '|' + '|'.join(['---'] * len(cols)) + '|'
    lines  = [header, sep]
    for row in rows:
        lines.append('| ' + ' | '.join(str(row.get(c, '')) for c in cols) + ' |')
    return '\n'.join(lines)

def main():
    print('🔍 Checking static HTML links...')
    html_res = check_static_html()

    print('📡 Checking pipeline feeds...')
    feed_res = check_feeds()

    print('📰 Checking recent articles...')
    art_res = check_articles()

    print('🗓️ Checking events...')
    ev_res = check_events()

    # ── Compose report ─────────────────────────────────────────────────────────
    sections = []
    hard_fail = False

    # 1. Static HTML
    if html_res['broken']:
        hard_fail = True
        rows = [{'Page': e['file'], 'Status': e['status'], 'URL': e['url']}
                for e in html_res['broken']]
        sections.append(
            f"## ❌ Static page links — {len(html_res['broken'])} broken\n"
            + fmt_table(rows, ['Page', 'Status', 'URL'])
        )
    else:
        sections.append(
            f"## ✅ Static page links — all {len(html_res['ok'])} OK"
        )

    # 2. Pipeline feeds
    if feed_res['broken']:
        hard_fail = True
        rows = [{'Feed': e['name'], 'Status': e['status'], 'URL': e['url']}
                for e in feed_res['broken']]
        sections.append(
            f"## ❌ Pipeline RSS feeds — {len(feed_res['broken'])} broken "
            f"/ {len(feed_res['ok']) + len(feed_res['broken'])} total\n"
            + fmt_table(rows, ['Feed', 'Status', 'URL'])
        )
    else:
        sections.append(
            f"## ✅ Pipeline RSS feeds — all {len(feed_res['ok'])} OK"
        )

    # 3. Articles
    if art_res['broken']:
        rows = [{'Date': e['date'], 'Source': e['source'],
                 'Status': e['status'], 'Title': e['title'][:60]}
                for e in art_res['broken']]
        sections.append(
            f"## ⚠️ Recent articles — {len(art_res['broken'])} broken URLs "
            f"(last {RECENT_DAYS} days, {len(art_res['ok'])} OK, "
            f"{len(art_res['skipped'])} skipped/paywalled)\n"
            + fmt_table(rows, ['Date', 'Source', 'Status', 'Title'])
            + "\n\n*Article link rot is expected — news sites delete old URLs. "
            "Consider updating or removing these articles from `articles.json`.*"
        )
    else:
        sections.append(
            f"## ✅ Recent articles — {len(art_res['ok'])} OK "
            f"({len(art_res['skipped'])} skipped/paywalled, last {RECENT_DAYS} days)"
        )

    # 4. Events
    ev_broken = ev_res['broken']
    ev_stale  = ev_res['stale']
    if ev_broken:
        hard_fail = True
        rows = [{'ID': e['id'], 'Status': e['status'], 'URL': e['url']}
                for e in ev_broken]
        sections.append(
            f"## ❌ Events — {len(ev_broken)} broken links\n"
            + fmt_table(rows, ['ID', 'Status', 'URL'])
            + "\n\n*Fix: update `portal/data/events.json` and run "
            "`node .github/scripts/build-events.mjs`*"
        )
    else:
        sections.append(
            f"## ✅ Events — all {len(ev_res['ok'])} URLs OK"
        )
    if ev_stale:
        rows = [{'ID': e['id'], 'Days': e['days'],
                 'Last verified': e['url_verified'], 'URL': e['url']}
                for e in ev_stale]
        sections.append(
            f"## ⏰ Events — {len(ev_stale)} links not re-verified in {EVENT_STALE_DAYS}+ days\n"
            + fmt_table(rows, ['ID', 'Days', 'Last verified', 'URL'])
        )

    # ── Summary line ───────────────────────────────────────────────────────────
    summary = (
        f"**Checked {TODAY}** — "
        f"HTML: {len(html_res['ok'])} ✅ / {len(html_res['broken'])} ❌ | "
        f"Feeds: {len(feed_res['ok'])} ✅ / {len(feed_res['broken'])} ❌ | "
        f"Articles (last {RECENT_DAYS}d): {len(art_res['ok'])} ✅ / "
        f"{len(art_res['broken'])} ❌ / {len(art_res['skipped'])} ⏭️ | "
        f"Events: {len(ev_res['ok'])} ✅ / {len(ev_broken)} ❌ / {len(ev_stale)} ⏰"
    )

    report = f"# 🔗 Site-wide link check — {TODAY}\n\n{summary}\n\n" + \
             '\n\n'.join(sections)

    # Write report
    out = os.environ.get('LINK_REPORT_PATH', '/tmp/link_report.md')
    Path(out).write_text(report, encoding='utf-8')
    print(report)

    # Write GitHub Actions outputs
    gho = os.environ.get('GITHUB_OUTPUT', '')
    if gho:
        counts = {
            'html_broken':  len(html_res['broken']),
            'feed_broken':  len(feed_res['broken']),
            'art_broken':   len(art_res['broken']),
            'ev_broken':    len(ev_broken),
            'ev_stale':     len(ev_stale),
            'hard_fail':    'true' if hard_fail else 'false',
            'has_issue':    'true' if (hard_fail or ev_stale or art_res['broken']) else 'false',
        }
        with open(gho, 'a') as f:
            for k, v in counts.items():
                f.write(f"{k}={v}\n")

    sys.exit(1 if hard_fail else 0)


if __name__ == '__main__':
    main()
