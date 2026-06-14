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
// Priority: fine-grained keywords FIRST (15 categories), topic field as fallback only.
// The topic field is too coarse (4 buckets) and would swallow 80% of articles
// into PHARMA/MEDICINE/REGULATORY/EU DATA, hiding the other 11 categories.
function categorize(article) {
  const text = [
    article.title    ?? '',
    (article.tags    ?? []).join(' '),
    article.source   ?? '',
    article.excerpt  ?? '',
    article.badge    ?? '',
    article.topic    ?? '',
  ].join(' ').toLowerCase()

  // ── 1. Specific domain keywords (highest signal, checked first) ────────────

  // Geopolitics & global governance (before EU DATA — more specific)
  if (/geopolit|\bchina\b|usa.*eu|export.control|\bnato\b|\bg7\b|\bg20\b|military|defense|us.china|taiwan|tech.war|arms.race/i.test(text))
    return 'GEOPOLITICS'

  // Digital sovereignty (before EU DATA — more specific)
  if (/sovereignty|souverain|gaia.x|cloud.europ|aleph.alpha|semiconductor|chip.sovereignty|asml|\bimec\b|strategic.autonomy|tech.independence/i.test(text))
    return 'SOVEREIGNTY'

  // Cybersecurity
  if (/cybersec|cyberattack|malware|phishing|deepfake|adversarial.attack|red.team|vulnerability|threat.actor|ransomware|data.breach/i.test(text))
    return 'SECURITY'

  // Ethics & society
  if (/\bethics\b|ethical.ai|\bbias\b|fairness|privacy.rights|surveillance|discriminat|accountability|transparency.ai|explainab|trustworthy.ai/i.test(text))
    return 'ETHICS'

  // Environment & climate
  if (/carbon.footprint|energy.consumption|sustainab|green.ai|environment|climate.change|emissions|net.zero|carbon.neutral/i.test(text))
    return 'ENVIRONMENT'

  // Economy & labour
  if (/job.loss|automation.*work|workforce|labour.market|employment.ai|productivity.gain|economic.impact|\bgdp\b|labour.market/i.test(text))
    return 'ECONOMY'

  // Industry & ecosystem (AI companies, startups, deals, product launches)
  if (/\bstartup\b|venture.capital|\bvc\b|vc.funding|series.[abcd]|funding.round|market.cap|acquisition|merger|partnership|product.launch|big.tech|openai|anthropic|google.deepmind|meta.ai|mistral|cohere|\bxai\b|hugging.face|nvidia|microsoft.ai/i.test(text))
    return 'INDUSTRY'

  // Philosophy & AI safety/alignment (before TECHNICAL — specific terms)
  if (/\bphilosophy\b|consciousness|sentien|\bagi\b|artificial.general|alignment.problem|existential.risk|ai.safety|x.risk|superintelligence/i.test(text))
    return 'PHILOSOPHY'

  // ── 2. Drug discovery (very specific scientific terms) ────────────────────
  if (/drug.discov|admet|molecular.dock|cheminformat|\bsmiles\b|protein.fold|alphafold|rosettafold|drug.design|lead.optim|generative.chem|de.novo.drug|qsar|hit.compound|virtual.screening|docking.score|scaffold|medicinal.chem/i.test(text))
    return 'PHARMA'

  // ── 3. Clinical AI & medicine ─────────────────────────────────────────────
  if (/\bdiagnos|\bimaging\b|radiolog|patholog|pharmacovigilance|adverse.event|\brwe\b|real.world.evidence|\behr\b|\bemr\b|clinical.decision|patient.outcome|medical.imaging|ct.scan|\bmri\b|ecg.ai|wearable/i.test(text))
    return 'MEDICINE'

  // ── 4. Regulatory science ─────────────────────────────────────────────────
  if (/\bema\b|\bfda\b|\bchmp\b|marketing.authoris|conditional.approval|orphan.drug|benefit.risk|\bpsur\b|\bctd\b|pharmacopoeia|\bgmp\b|\bgdp\b|\bich\b|reflection.paper|\bepar\b|regulatory.submission|dossier|post.market.surveillance/i.test(text))
    return 'REGULATORY'

  // EU policy & data frameworks (broadened — catches AI Act, EHDS, GDPR, FHIR etc.)
  if (/ai.act|eu.ai|\bghds\b|\behds\b|\bidmp\b|\bfhir\b|\bomop\b|darwin.eu|\bgdpr\b|\bmdr\b|\bivdr\b|\bndsg\b|european.health|data.space|data.governance|interoperab|data.standard|europe|european.commission|brussels|parliament.eu/i.test(text))
    return 'EU DATA'

  // Academic research (peer-reviewed, before TECHNICAL — no mainstream tech press)
  if (/\barxiv\b|preprint|\bjournal\b|\bnature\b|\bcell\b|\blancet\b|\bnejm\b|pubmed|\bbiorxiv\b|peer.review|systematic.review|meta.analysis|clinical.study|cohort/i.test(text) &&
      !/techcrunch|wired|venturebeat|the.verge|theregister|ars.technica/i.test(text))
    return 'ACADEMIC'

  // Technical AI (broad — catches LLMs, models, agents, benchmarks)
  if (/\bllm\b|large.language|transformer|\bgpt\b|\bbert\b|neural.network|deep.learn|fine.tun|\brag\b|retrieval.augment|\bagent\b|benchmark|multimodal|foundation.model|diffusion.model|generative.ai|open.source.model|model.release|inference|tokeniz/i.test(text))
    return 'TECHNICAL'

  // ── 5. Pipeline topic field as final fallback (when no keyword matched) ───
  switch (article.topic) {
    case 'drug-discovery':  return 'PHARMA'
    case 'clinical-ai':     return 'MEDICINE'
    case 'regulatory':      return 'REGULATORY'
    case 'data-governance': return 'EU DATA'
  }

  return 'SCIENCE'  // true fallback
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
