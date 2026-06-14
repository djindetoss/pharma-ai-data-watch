/**
 * build-rss.mjs
 * ─────────────────────────────────────────────────────────────────
 * Pharma AI & Data Watch — RSS 2.0 feed generator
 *
 * Reads  : portal/js/articles.json
 * Writes : portal/feed.xml   (RSS 2.0, max 50 most recent articles)
 *
 * Cost   : $0.00 — no API calls
 * ─────────────────────────────────────────────────────────────────
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs'
import { join, dirname }                           from 'path'
import { fileURLToPath }                           from 'url'

const __dirname  = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT  = join(__dirname, '..', '..')
const ARTICLES   = join(REPO_ROOT, 'portal', 'js', 'articles.json')
const FEED_OUT   = join(REPO_ROOT, 'portal', 'feed.xml')

const SITE_URL   = 'https://djindetoss.github.io/pharma-ai-data-watch'
const FEED_TITLE = 'Pharma AI & Data Watch'
const FEED_DESC  = 'Curated AI, pharma, and regulatory science intelligence — updated weekly.'
const MAX_ITEMS  = 50

function escXml(str) {
  return (str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

function rfcDate(iso) {
  if (!iso) return new Date().toUTCString()
  try { return new Date(iso).toUTCString() } catch { return new Date().toUTCString() }
}

const today = new Date().toISOString().split('T')[0]
const allArticles = JSON.parse(readFileSync(ARTICLES, 'utf8'))

// Filter: valid dates only, sorted by date desc, top 50
const articles = allArticles
  .filter(a => a.url && a.url !== '#' && (!a.date || a.date <= today))
  .sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
  .slice(0, MAX_ITEMS)

console.log(`[rss] Generating feed with ${articles.length} articles…`)

const items = articles.map(a => {
  const excerpt = (a.excerpt ?? '').replace(/\s+/g, ' ').trim().slice(0, 300)
  const cats    = (a.tags ?? []).slice(0, 3).map(t => `    <category>${escXml(t)}</category>`).join('\n')
  return `  <item>
    <title>${escXml(a.title)}</title>
    <link>${escXml(a.url)}</link>
    <guid isPermaLink="${a.url.startsWith('http') ? 'true' : 'false'}">${escXml(a.url)}</guid>
    <pubDate>${rfcDate(a.date)}</pubDate>
    <source url="${SITE_URL}/feed.xml">${escXml(FEED_TITLE)}</source>
    <description>${escXml(excerpt)}</description>
${cats ? cats + '\n' : ''}  </item>`
}).join('\n')

const now  = new Date().toUTCString()
const xml  = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escXml(FEED_TITLE)}</title>
    <link>${SITE_URL}/</link>
    <description>${escXml(FEED_DESC)}</description>
    <language>en-GB</language>
    <lastBuildDate>${now}</lastBuildDate>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>${SITE_URL}/og-image.png</url>
      <title>${escXml(FEED_TITLE)}</title>
      <link>${SITE_URL}/</link>
    </image>
${items}
  </channel>
</rss>`

writeFileSync(FEED_OUT, xml, 'utf8')
console.log(`[rss] Written ${FEED_OUT}  (${articles.length} items, ${xml.length} bytes)`)
