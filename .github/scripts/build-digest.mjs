/**
 * build-digest.mjs
 * ─────────────────────────────────────────────────────────────────
 * Pharma AI & Data Watch — Monthly digest builder
 *
 * Reads  : portal/js/articles.json   (produced by the ingestion pipeline)
 * Writes : portal/data/digests/YYYY-MM.json   (cumulative monthly digest)
 *          portal/data/digests/index.json      (digest index)
 *
 * Cost   : $0.00  — zero API calls, pure Node.js (fs + path only)
 * ─────────────────────────────────────────────────────────────────
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { join, dirname }                                        from 'path'
import { fileURLToPath }                                        from 'url'

// ── Paths ─────────────────────────────────────────────────────────
const __dirname   = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT   = join(__dirname, '..', '..')
const ARTICLES    = join(REPO_ROOT, 'portal', 'js', 'articles.json')
const DIGESTS_DIR = join(REPO_ROOT, 'portal', 'data', 'digests')
const INDEX_FILE  = join(DIGESTS_DIR, 'index.json')

mkdirSync(DIGESTS_DIR, { recursive: true })

// ── Load articles ─────────────────────────────────────────────────
const allArticles = JSON.parse(readFileSync(ARTICLES, 'utf8'))
console.log(`[digest] Loaded ${allArticles.length} articles from articles.json`)

// ── Time window ───────────────────────────────────────────────────
const now        = new Date()
const digestId   = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const weekAgo    = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
const weekAgoStr = weekAgo.toISOString().split('T')[0]

console.log(`[digest] Digest month: ${digestId} | Week since: ${weekAgoStr}`)

// ── Load existing digest for this month ───────────────────────────
const digestFile = join(DIGESTS_DIR, `${digestId}.json`)
let existingDigest = { articles: [] }
if (existsSync(digestFile)) {
  existingDigest = JSON.parse(readFileSync(digestFile, 'utf8'))
  console.log(`[digest] Existing digest: ${existingDigest.articles.length} articles`)
}
const existingIds = new Set((existingDigest.articles || []).map(a => a.id))

// ── Category classification (no LLM) ─────────────────────────────
function categorize(article) {
  const text = [
    article.title    ?? '',
    (article.tags    ?? []).join(' '),
    article.source   ?? '',
    article.excerpt  ?? '',
    article.badge    ?? '',
    article.topic    ?? '',
  ].join(' ').toLowerCase()

  // Topic field from pipeline (most reliable — set by PubMed query config)
  switch (article.topic) {
    case 'drug-discovery':  return 'PHARMA'
    case 'clinical-ai':     return 'MEDICINE'
    case 'regulatory':      return 'REGULATORY'
    case 'data-governance': return 'EU DATA'
  }

  // Keyword fallback
  if (/drug.discov|admet|molecular.dock|cheminformat|smiles|protein.fold|alphafold|rosetta|drug.design|lead.optim|generative.chem|de.novo|qsar/i.test(text))
    return 'PHARMA'
  if (/diagnos|imaging|radiolog|patholog|clinical.trial|patient|therapy|pharmacovigilance|adverse.event|rwe|real.world.evidence|ehr|emr/i.test(text))
    return 'MEDICINE'
  if (/\bema\b|fda|chmp|regulation|guideline|compliance|marketing.authoris|approval|authoriz|directive|ai.act|gdpr|mdr|ivdr|pharmacopoeia|gmp|psur|ctd|idmp|fhir|ehds|darwin/i.test(text))
    return 'REGULATORY'
  if (/sovereignty|souverain|gaia.x|cloud.europ|mistral|aleph.alpha|semiconductor|chip|asml|imec/i.test(text))
    return 'SOVEREIGNTY'
  if (/cybersec|attack|malware|phishing|deepfake|adversarial|red.team|vulnerability|threat/i.test(text))
    return 'SECURITY'
  if (/geopolit|china|usa.*eu|export.control|nato|g7|g20|military|defense/i.test(text))
    return 'GEOPOLITICS'
  if (/carbon|energy|sustainab|green.ai|environment|climate/i.test(text))
    return 'ENVIRONMENT'
  if (/ethics|bias|fairness|privacy|rights|surveillance|discriminat/i.test(text))
    return 'ETHICS'
  if (/economy|job|employ|workforce|productivity|market|startup|invest/i.test(text))
    return 'ECONOMY'
  if (/philosophy|consciousness|agi|alignment|safety|existential|sentient/i.test(text))
    return 'PHILOSOPHY'
  if (/europe|eu |european|brussels|commission|parliament|ehds/i.test(text))
    return 'EU DATA'
  if (/llm|transformer|neural.network|deep.learn|fine.tun|rag|agent|benchmark|multimodal|foundation.model|large.language/i.test(text))
    return 'TECHNICAL'
  if (/university|arxiv|preprint|\bjournal\b|nature|cell|lancet|nejm|pubmed|biorxiv|research|laboratory|institute/i.test(text) &&
      !/techcrunch|wired|venturebeat|the.verge/i.test(text))
    return 'ACADEMIC'
  return 'SCIENCE'
}

// ── Relevance scoring (no LLM) ────────────────────────────────────
function scoreRelevance(article) {
  const src = (article.source ?? '').toLowerCase()
  // Tier 1 — top peer-reviewed journals
  if (/\bnature\b|nature machine|science\b|cell\b|lancet|new england|nejm|\bpnas\b/i.test(src))
    return 'CRITICAL'
  // Tier 2 — peer-reviewed papers, official regulatory sources
  if (article.type === 'paper' || article.badge === 'Regulatory' || src === 'ema' || src === 'fda')
    return 'IMPORTANT'
  // Tier 3 — news, preprints, AI news feeds
  return 'WATCH'
}

// ── Map pipeline article → digest item ───────────────────────────
function toDigestItem(article) {
  // Truncate raw PubMed abstracts (still unprocessed sometimes)
  let summary = (article.excerpt ?? '').replace(/^\d+\.\s+\w[^.]*\.\s+\d{4}[^.]*\.\s+doi:[^\s]+\.?\s+Epub[^.]*\.\s+/i, '')
  summary = summary.replace(/\s*Author information:.*$/i, '').trim()
  if (summary.length > 800) summary = summary.slice(0, 800).replace(/\s+\S*$/, '') + '…'

  return {
    id:            article.id,
    title:         article.title,
    titleFr:       null,
    source:        article.source,
    url:           article.url,
    publishedDate: article.date,
    type:          article.type,
    category:      categorize(article),
    relevance:     scoreRelevance(article),
    summary,
    regulatoryAngle: null,
    tags:          article.tags   ?? [],
    badge:         article.badge  ?? '',
    topic:         article.topic  ?? null,
    authors:       null,
    country:       null,
    university:    null,
    lab:           null,
  }
}

// ── Select new articles ───────────────────────────────────────────
// Include: articles in the current month OR ingested in the past 7 days
const newArticles = allArticles.filter(a => {
  if (existingIds.has(a.id)) return false
  const d = a.date ?? ''
  return d.startsWith(digestId) || d >= weekAgoStr
})

console.log(`[digest] New articles to add this week: ${newArticles.length}`)

const newDigestItems = newArticles.map(toDigestItem)

// ── Merge + sort ──────────────────────────────────────────────────
const relevanceOrder = { CRITICAL: 0, IMPORTANT: 1, WATCH: 2 }
const allItems = [...(existingDigest.articles ?? []), ...newDigestItems]
allItems.sort((a, b) => {
  const r = (relevanceOrder[a.relevance] ?? 1) - (relevanceOrder[b.relevance] ?? 1)
  if (r !== 0) return r
  return (b.publishedDate ?? '').localeCompare(a.publishedDate ?? '')
})

// ── Generate month signal (template, no LLM) ──────────────────────
function generateSignal(items) {
  const catCounts = {}
  const srcCounts = {}

  for (const item of items) {
    catCounts[item.category] = (catCounts[item.category] ?? 0) + 1
    srcCounts[item.source]   = (srcCounts[item.source]   ?? 0) + 1
  }

  const dominant   = Object.entries(catCounts).sort((a, b) => b[1] - a[1])[0]
  const topSources = Object.entries(srcCounts).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([s]) => s)
  const paperCount = items.filter(i => i.type === 'paper').length

  const monthLabel = new Date(digestId + '-02').toLocaleString('en-US', { month: 'long', year: 'numeric' })

  const text = [
    `${monthLabel}: ${items.length} article${items.length > 1 ? 's' : ''} collected.`,
    dominant
      ? `Dominant topic: ${dominant[0]} (${dominant[1]} article${dominant[1] > 1 ? 's' : ''}).`
      : '',
    topSources.length
      ? `Most active sources: ${topSources.join(', ')}.`
      : '',
    paperCount > 0
      ? `${paperCount} peer-reviewed paper${paperCount > 1 ? 's' : ''} included.`
      : '',
  ].filter(Boolean).join(' ')

  return {
    monthLabel,
    totalArticles:          items.length,
    categoryCounts:         catCounts,
    dominantCategory:       dominant?.[0] ?? null,
    dominantCategoryCount:  dominant?.[1] ?? 0,
    topSources,
    paperCount,
    criticalCount:          items.filter(i => i.relevance === 'CRITICAL').length,
    importantCount:         items.filter(i => i.relevance === 'IMPORTANT').length,
    text,
    generatedAt:            now.toISOString(),
  }
}

const signal = generateSignal(allItems)
console.log(`[digest] Signal: ${signal.text}`)

// ── Write digest file ─────────────────────────────────────────────
const digest = {
  id:          digestId,
  generatedAt: now.toISOString(),
  weekStart:   weekAgoStr,
  signal,
  articles:    allItems,
}

writeFileSync(digestFile, JSON.stringify(digest, null, 2), 'utf8')
console.log(`[digest] Written ${digestFile}  (${allItems.length} articles)`)

// ── Update index.json ─────────────────────────────────────────────
let index = existsSync(INDEX_FILE) ? JSON.parse(readFileSync(INDEX_FILE, 'utf8')) : []

const entry = {
  id:            digestId,
  label:         signal.monthLabel,
  totalArticles: allItems.length,
  updatedAt:     now.toISOString(),
}
const pos = index.findIndex(e => e.id === digestId)
if (pos >= 0) {
  index[pos] = entry
} else {
  index.unshift(entry)
}
index.sort((a, b) => b.id.localeCompare(a.id))

writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2), 'utf8')
console.log(`[digest] Updated index.json  (${index.length} digest${index.length > 1 ? 's' : ''})`)
