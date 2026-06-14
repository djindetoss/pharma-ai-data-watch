/**
 * build-sitemap.mjs
 * Generates portal/sitemap.xml from:
 *   - Static HTML pages
 *   - Recent articles in portal/js/articles.json (last 90 days)
 *
 * Run: node .github/scripts/build-sitemap.mjs
 */

import { readFileSync, writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import path from 'path'

const __dir  = path.dirname(fileURLToPath(import.meta.url))
const ROOT   = path.resolve(__dir, '../..')
const BASE   = 'https://djindetoss.github.io/pharma-ai-data-watch'
const TODAY  = new Date().toISOString().split('T')[0]
const CUTOFF = new Date(Date.now() - 90 * 864e5).toISOString().split('T')[0]

// ── Static pages ───────────────────────────────────────────────────────────────
const STATIC = [
  { loc: '/',              priority: '1.0', changefreq: 'daily'   },
  { loc: '/events.html',   priority: '0.9', changefreq: 'weekly'  },
  { loc: '/briefing.html', priority: '0.8', changefreq: 'weekly'  },
  { loc: '/digest.html',   priority: '0.7', changefreq: 'monthly' },
]

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function urlEntry({ loc, lastmod, priority, changefreq }) {
  return [
    '  <url>',
    `    <loc>${esc(BASE + loc)}</loc>`,
    lastmod    ? `    <lastmod>${esc(lastmod)}</lastmod>` : null,
    changefreq ? `    <changefreq>${changefreq}</changefreq>` : null,
    priority   ? `    <priority>${priority}</priority>` : null,
    '  </url>',
  ].filter(Boolean).join('\n')
}

// ── Load recent articles ───────────────────────────────────────────────────────
let articles = []
try {
  articles = JSON.parse(readFileSync(path.join(ROOT, 'portal/js/articles.json'), 'utf8'))
} catch { /* articles.json may not exist on first run */ }

const recentArticles = articles
  .filter(a => a.url && a.date && a.date >= CUTOFF && a.url.startsWith('http'))
  .sort((a, b) => b.date.localeCompare(a.date))
  .slice(0, 500)   // sitemap limit guard

// ── Build XML ─────────────────────────────────────────────────────────────────
const entries = [
  ...STATIC.map(p => urlEntry({ ...p, lastmod: TODAY })),
  ...recentArticles.map(a => urlEntry({
    loc:        a.url,
    lastmod:    a.date,
    priority:   '0.5',
    changefreq: 'never',
  })),
]

const xml = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...entries,
  '</urlset>',
  '',   // trailing newline
].join('\n')

const out = path.join(ROOT, 'portal/sitemap.xml')
writeFileSync(out, xml, 'utf8')
console.log(`✅ sitemap.xml generated — ${STATIC.length} static + ${recentArticles.length} article URLs → ${out}`)
