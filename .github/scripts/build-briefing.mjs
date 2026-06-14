/**
 * build-briefing.mjs
 * ─────────────────────────────────────────────────────────────────
 * Pharma AI & Data Watch — Weekly Expert Briefing Builder
 *
 * Reads  : portal/js/articles.json
 * Calls  : Claude Haiku 4.5  (~$0.012 per run, ~$0.05/month)
 * Writes : portal/data/briefings/YYYY-WNN.json
 *          portal/data/briefings/index.json
 *
 * Fallback: if ANTHROPIC_API_KEY not set, builds a structured
 *           briefing from article metadata alone (cost $0).
 * ─────────────────────────────────────────────────────────────────
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { join, dirname }                                        from 'path'
import { fileURLToPath }                                        from 'url'

const __dirname    = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT    = join(__dirname, '..', '..')
const ARTICLES     = join(REPO_ROOT, 'portal', 'js', 'articles.json')
const BRIEFINGS    = join(REPO_ROOT, 'portal', 'data', 'briefings')
const INDEX_FILE   = join(BRIEFINGS, 'index.json')

mkdirSync(BRIEFINGS, { recursive: true })

// ── ISO week number ───────────────────────────────────────────────
function isoWeek(d) {
  const date   = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day    = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return Math.ceil(((date - yearStart) / 86400000 + 1) / 7)
}

const now        = new Date()
const year       = now.getFullYear()
const week       = isoWeek(now)
const briefingId = `${year}-W${String(week).padStart(2, '0')}`

// Monday of current week
const dayOfWeek  = now.getDay() || 7
const monday     = new Date(now)
monday.setDate(monday.getDate() - dayOfWeek + 1)
const weekStart  = monday.toISOString().split('T')[0]
const weekEnd    = now.toISOString().split('T')[0]

console.log(`[briefing] ID: ${briefingId}  |  ${weekStart} → ${weekEnd}`)

// ── Load & filter articles ────────────────────────────────────────
const allArticles = JSON.parse(readFileSync(ARTICLES, 'utf8'))

// Exclude future-dated articles (PubMed sometimes publishes ahead-of-print)
const today = now.toISOString().split('T')[0]
const validArticles = allArticles.filter(a => !a.date || a.date <= today)

// Take articles from the past 14 days — enough content for a weekly brief
const cutoff = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
let recent = validArticles.filter(a => a.date >= cutoff)

// If sparse (early in pipeline life), use last 30 days
if (recent.length < 15) {
  const cutoff30 = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  recent = validArticles.filter(a => a.date >= cutoff30)
}

// If still sparse, use all articles
if (recent.length < 10) recent = [...validArticles]

// Score and rank articles for the briefing
function briefingScore(a) {
  let s = 0
  if (a.type === 'paper')   s += 4
  if (a.type === 'ainews')  s += 3
  if (a.type === 'news')    s += 2
  const b = a.badge || ''
  if (/regulatory/i.test(b))  s += 3
  if (/research/i.test(b))    s += 2
  if (/pubmed/i.test(b))      s += 2
  const src = (a.source || '').toLowerCase()
  if (/nature|science\b|cell\b|lancet|nejm|pnas/i.test(src)) s += 4
  if (/ema|fda|who/i.test(src))  s += 3
  if (a.featured) s += 2
  return s
}

const scored = recent.map(a => ({ ...a, _bs: briefingScore(a) }))
scored.sort((a, b) => b._bs - a._bs || b.date.localeCompare(a.date))

// Top 60 articles for the prompt (needed for 10 items × 4 sections + pharmaFocus)
const selected = scored.slice(0, 60)

console.log(`[briefing] Selected ${selected.length} articles from ${recent.length} recent`)

// ── Clean excerpt for prompt ──────────────────────────────────────
function cleanExcerpt(text, maxLen = 180) {
  if (!text) return ''
  // Strip PubMed citation headers
  let t = text
    .replace(/^\d+\.\s+\w[^.]{2,60}\.\s+\d{4}[^.]*\.\s+doi:[^\s]+\.?\s*(Epub[^.]*\.)?\s*/i, '')
    .replace(/\s*Author information:.*$/is, '')
    .replace(/\s+/g, ' ')
    .trim()
  return t.length > maxLen ? t.slice(0, maxLen).replace(/\s\S*$/, '') + '…' : t
}

// ── Pre-categorize article into 1 of 5 sections (keyword-first) ──
function preCategorize(article) {
  const text = [
    article.title    ?? '',
    (article.tags    ?? []).join(' '),
    article.excerpt  ?? '',
    article.topic    ?? '',
  ].join(' ').toLowerCase()

  // ainews type → always frontier (AI lab news feed)
  if (article.type === 'ainews') return 'frontier'

  // Drug discovery (specific lab/chem terms, checked early)
  if (/drug.discov|admet|molecular.dock|cheminformat|\bsmiles\b|protein.fold|alphafold|rosettafold|drug.design|lead.optim|generative.chem|de.novo.drug|qsar|hit.compound|virtual.screen|medicinal.chem|antibiotic.discov/i.test(text))
    return 'drug-discovery'

  // Clinical AI (diagnostics / imaging / EHR)
  if (/\bdiagnos|\bimaging\b|radiolog|patholog|clinical.decision|patient.outcome|medical.imaging|\behr\b|\bemr\b|wearable|pharmacovigilance|adverse.event.detect/i.test(text))
    return 'clinical-ai'

  // Data governance (EHDS / FHIR / OMOP / interoperability)
  if (/\behds\b|\bidmp\b|\bfhir\b|\bomop\b|darwin.eu|real.world.dat|rwd\b|interoperab|data.standard|health.data.gov|federated.learn.*health|data.space/i.test(text))
    return 'data-governance'

  // Regulatory science (EMA / FDA specific)
  if (/\bema\b|\bfda\b|\bchmp\b|\bich\b|marketing.authoris|\bpsur\b|\bctd\b|\bgmp\b|reflection.paper|post.market.surveil|epar\b|benefit.risk/i.test(text))
    return 'regulatory'

  // LLM/AI platform keywords → frontier
  if (/\bllm\b|large.language|transformer|\bgpt\b|foundation.model|ai.agent|ai.safety|openai|anthropic|deepmind|meta.ai|mistral|frontier.ai/i.test(text))
    return 'frontier'

  // topic field as final fallback (pipeline-assigned, 4 coarse buckets)
  switch (article.topic) {
    case 'drug-discovery':  return 'drug-discovery'
    case 'clinical-ai':     return 'clinical-ai'
    case 'regulatory':      return 'regulatory'
    case 'data-governance': return 'data-governance'
  }

  return 'frontier'  // generic fallback
}

// ── Build the Haiku prompt ────────────────────────────────────────
// Articles are PRE-CLASSIFIED by section before sending to Claude.
// This ensures correct section assignment regardless of article order.
function buildPrompt(articles) {
  // 1. Group articles by section (pre-classification)
  const SECTIONS = ['frontier', 'regulatory', 'drug-discovery', 'clinical-ai', 'data-governance']
  const groups   = Object.fromEntries(SECTIONS.map(s => [s, []]))

  articles.forEach((a, i) => {
    const sec = preCategorize(a)
    groups[sec].push(i)
  })

  // 2. Build article list with [SECTION] tag prefix so Claude sees the assignment
  const articleList = articles.map((a, i) => {
    const sec     = preCategorize(a)
    const excerpt = cleanExcerpt(a.excerpt)
    return `[${sec.toUpperCase()}] ${i}: "${a.title}" | ${a.source} | ${a.date}${excerpt ? ' | ' + excerpt : ''}`
  }).join('\n')

  // 3. Summarise index assignments for Claude
  const assignmentSummary = SECTIONS.map(sec => {
    const ids = groups[sec]
    return `  ${sec.padEnd(16)}: [${ids.join(', ')}]  (${ids.length} articles pre-assigned)`
  }).join('\n')

  return `You are a senior AI intelligence analyst writing the weekly briefing for European pharmaceutical and regulatory science professionals: regulatory scientists, pharma R&D directors, data coordinators, and clinical development teams.

════════════════════════════════════════
PRE-CLASSIFIED ARTICLE INDICES BY SECTION
(derived from keyword analysis — use ONLY the indices shown for each section)
════════════════════════════════════════
${assignmentSummary}

SECTION DEFINITIONS:
1. "frontier"        → Frontier AI & LLMs: model releases, AI labs (OpenAI/Anthropic/DeepMind/Meta/Mistral), LLM benchmarks, AI agents, AI safety/alignment, foundation models, AI policy globally
2. "regulatory"      → Regulatory Science: EMA, FDA, ICH guidance, marketing authorisation, pharmacovigilance, GMP, PSUR, clinical trial regulations, EU regulatory frameworks
3. "drug-discovery"  → Drug Discovery AI: ADMET, molecular docking, generative chemistry, protein folding, lead optimisation, QSAR, cheminformatics, antibiotic discovery
4. "clinical-ai"     → Clinical AI: diagnostics, radiology/pathology AI, clinical decision support, patient outcome prediction, biomarker discovery, EHR/EMR AI
5. "data-governance" → Data & Governance: EHDS, IDMP, FHIR, OMOP, Darwin EU, RWD/RWE frameworks, data standards, interoperability, federated learning for health data

════════════════════════════════════════
WRITING RULES
════════════════════════════════════════
- CRITICAL: each section MUST use ONLY the article indices pre-assigned to it above
- If a section has fewer than 10 pre-assigned articles, fill remaining items using the NEAREST thematically adjacent indices
- Each section MUST have EXACTLY 10 items
- Write as a domain expert: implications first, facts second
- NEVER start headline or body with "This week", "In recent", "The latest", "Recently"
- Headlines: 8-10 words, declarative, verb-led (e.g. "AlphaFold 3 Accelerates ADMET Screening by 40%")
- Body: 2-3 sentences answering "What does this mean for my work?"
- sourceIndices: use valid 0-based indices from the list below
- Drug Discovery and Clinical AI are SEPARATE sections — never merge them

Return ONLY valid JSON — no markdown, no backticks, no commentary before or after:

{
  "leadStory": {
    "headline": "10-14 words, declarative, punchy",
    "standfirst": "One sentence: the single most consequential development this week and why it matters for pharma/regulatory professionals",
    "body": "3-4 sentences: expert framing, implications, what changes for practitioners",
    "sourceIndices": [BEST_INDEX]
  },
  "sections": [
    {
      "id": "frontier",
      "title": "Frontier AI & LLMs",
      "icon": "🤖",
      "items": [
        { "headline": "8-10 words, verb-led", "body": "2-3 expert sentences", "sourceIndices": [FRONTIER_IDX] },
        "... (exactly 10 items, using ONLY pre-assigned frontier indices)"
      ]
    },
    {
      "id": "regulatory",
      "title": "Regulatory Science",
      "icon": "🏛️",
      "items": [
        "... (exactly 10 items, using ONLY pre-assigned regulatory indices)"
      ]
    },
    {
      "id": "drug-discovery",
      "title": "AI in Drug Discovery",
      "icon": "🧬",
      "items": [
        "... (exactly 10 items, using ONLY pre-assigned drug-discovery indices)"
      ]
    },
    {
      "id": "clinical-ai",
      "title": "Clinical AI",
      "icon": "🔬",
      "items": [
        "... (exactly 10 items, using ONLY pre-assigned clinical-ai indices)"
      ]
    },
    {
      "id": "data-governance",
      "title": "Data & Governance",
      "icon": "📊",
      "items": [
        "... (exactly 10 items, using ONLY pre-assigned data-governance indices)"
      ]
    }
  ],
  "editorNote": "1-2 sentences: the week's overarching theme — what a senior pharma professional needs to remember"
}

════════════════════════════════════════
ARTICLES — format: [SECTION] index: "title" | source | date | excerpt
════════════════════════════════════════
${articleList}`
}

// ── Call Claude Haiku ─────────────────────────────────────────────
async function generateWithClaude(articles) {
  const apiKey = process.env.ANTHROPIC_API_KEY?.trim()
  if (!apiKey) {
    console.log('[briefing] ANTHROPIC_API_KEY not set — using fallback generator')
    return null
  }

  const prompt = buildPrompt(articles)
  console.log(`[briefing] Calling Claude Haiku (~${Math.round(prompt.length / 4)} tokens input)…`)

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method:  'POST',
    headers: {
      'Content-Type':      'application/json',
      'x-api-key':         apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model:      'claude-haiku-4-5',
      max_tokens: 8192,
      messages:   [{ role: 'user', content: prompt }],
    }),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Anthropic API error ${res.status}: ${err.slice(0, 200)}`)
  }

  const data    = await res.json()
  const raw     = data.content?.[0]?.text?.trim() ?? ''
  const tokens  = data.usage ?? {}
  console.log(`[briefing] Haiku response: ${raw.length} chars | tokens in=${tokens.input_tokens} out=${tokens.output_tokens}`)

  // Strip markdown fences if present
  const json = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()

  try {
    return JSON.parse(json)
  } catch (e) {
    // Try to extract JSON from the response
    const match = json.match(/\{[\s\S]+\}/)
    if (match) return JSON.parse(match[0])
    throw new Error(`Could not parse Haiku JSON response: ${e.message}\nRaw: ${raw.slice(0, 300)}`)
  }
}

// ── Fallback: template-based briefing (no LLM, $0) ───────────────
function generateFallback(articles) {
  console.log('[briefing] Generating fallback briefing from metadata…')

  const byType = { paper: [], ainews: [], news: [], seminar: [] }
  for (const a of articles) (byType[a.type] || byType.news).push(a)

  const byTopic = {}
  for (const a of articles) {
    const t = a.topic || 'general'
    ;(byTopic[t] = byTopic[t] || []).push(a)
  }

  // Lead = highest scored article
  const lead = articles[0]

  function makeItem(a, idx) {
    return {
      headline: a.title.length > 80 ? a.title.slice(0, 78) + '…' : a.title,
      body:     cleanExcerpt(a.excerpt, 250) || `See the full article at ${a.source}.`,
      sourceIndices: [idx],
    }
  }

  const ainewsArticles      = articles.filter(a => a.type === 'ainews').slice(0, 10)
  const regulatoryArticles  = articles.filter(a => a.topic === 'regulatory').slice(0, 10)
  const drugDiscoveryArts   = articles.filter(a => a.topic === 'drug-discovery').slice(0, 10)
  const clinicalAiArts      = articles.filter(a => a.topic === 'clinical-ai').slice(0, 10)
  const dataGovArts         = articles.filter(a => a.topic === 'data-governance').slice(0, 10)

  function idxOf(a) { return articles.indexOf(a) }

  return {
    leadStory: {
      headline:     lead.title.slice(0, 80),
      standfirst:   `${lead.source} reports on what may be the most significant AI development this week in the pharma and regulatory space.`,
      body:         cleanExcerpt(lead.excerpt, 400) || lead.title,
      sourceIndices: [0],
    },
    sections: [
      {
        id:    'frontier',
        title: 'Frontier AI & LLMs',
        icon:  '🤖',
        items: ainewsArticles.map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'regulatory',
        title: 'Regulatory Science',
        icon:  '🏛️',
        items: regulatoryArticles.map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'drug-discovery',
        title: 'AI in Drug Discovery',
        icon:  '🧬',
        items: drugDiscoveryArts.map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'clinical-ai',
        title: 'Clinical AI',
        icon:  '🔬',
        items: clinicalAiArts.map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'data-governance',
        title: 'Data & Governance',
        icon:  '📊',
        items: dataGovArts.map(a => makeItem(a, idxOf(a))),
      },
    ].filter(s => s.items.length > 0),
    editorNote: `${articles.length} sources analysed this week across regulatory, drug discovery, clinical AI, and data governance channels. Pipeline-generated summary — no AI editorial layer.`,
  }
}

// ── Resolve source indices → full source objects ──────────────────
function resolveSources(content, articles) {
  function resolve(indices) {
    return (indices || []).map(i => {
      const a = articles[i]
      if (!a) return null
      return { title: a.title, source: a.source, url: a.url, date: a.date, type: a.type }
    }).filter(Boolean)
  }

  function processItem(item) {
    return { ...item, sources: resolve(item.sourceIndices) }
  }

  return {
    ...content,
    leadStory: {
      ...content.leadStory,
      sources: resolve(content.leadStory?.sourceIndices),
    },
    sections: (content.sections || []).map(s => ({
      ...s,
      items: (s.items || []).map(processItem),
    })),
    ...(content.pharmaFocus ? {
      pharmaFocus: {
        ...content.pharmaFocus,
        items: (content.pharmaFocus?.items || []).map(processItem),
      }
    } : {}),
  }
}

// ── Main ──────────────────────────────────────────────────────────
let raw
try {
  raw = await generateWithClaude(selected)
} catch (e) {
  console.warn(`[briefing] Claude call failed: ${e.message} — using fallback`)
  raw = null
}

if (!raw) raw = generateFallback(selected)

const resolved = resolveSources(raw, selected)

// All sources cited in the briefing (deduped)
const usedUrls = new Set()
const allSources = []
function collectSources(sources) {
  for (const s of sources || []) {
    if (s && !usedUrls.has(s.url)) {
      usedUrls.add(s.url)
      allSources.push(s)
    }
  }
}
collectSources(resolved.leadStory?.sources)
for (const sec of resolved.sections || []) {
  for (const item of sec.items || []) collectSources(item.sources)
}
for (const item of resolved.pharmaFocus?.items || []) collectSources(item.sources)


// Week label in French
const monthEn = monday.toLocaleString('en-US', { month: 'long' })
const weekLabel = `Week ${week} — ${monthEn} ${monday.getDate()}, ${year}`

// Final briefing object
const briefing = {
  id:          briefingId,
  weekLabel,
  weekStart,
  weekEnd:     weekEnd,
  generatedAt: now.toISOString(),
  meta: {
    articlesAnalyzed: selected.length,
    model:            process.env.ANTHROPIC_API_KEY ? 'claude-haiku-4-5' : 'fallback',
  },
  leadStory:   resolved.leadStory,
  sections:    resolved.sections,
  pharmaFocus: resolved.pharmaFocus,
  editorNote:  resolved.editorNote || '',
  allSources,
}

const briefingFile = join(BRIEFINGS, `${briefingId}.json`)
writeFileSync(briefingFile, JSON.stringify(briefing, null, 2), 'utf8')
console.log(`[briefing] Written ${briefingFile}`)

// Update index
let index = existsSync(INDEX_FILE) ? JSON.parse(readFileSync(INDEX_FILE, 'utf8')) : []
const storiesCount = (resolved.sections || []).reduce((n, s) => n + (s.items?.length || 0), 0)
  + (resolved.pharmaFocus?.items?.length || 0)
const entry = {
  id:           briefingId,
  weekLabel,
  weekStart,
  generatedAt:  now.toISOString(),
  sourcesCount: allSources.length,
  storiesCount,
  model:        briefing.meta.model,
}
const pos = index.findIndex(e => e.id === briefingId)
if (pos >= 0) index[pos] = entry; else index.unshift(entry)
index.sort((a, b) => b.id.localeCompare(a.id))
writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2), 'utf8')
console.log(`[briefing] Updated index.json (${index.length} briefing${index.length > 1 ? 's' : ''})`)
