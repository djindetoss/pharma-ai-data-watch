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

// Take articles from the past 14 days — enough content for a weekly brief
const cutoff = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
let recent = allArticles.filter(a => a.date >= cutoff)

// If sparse (early in pipeline life), use last 30 days
if (recent.length < 15) {
  const cutoff30 = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  recent = allArticles.filter(a => a.date >= cutoff30)
}

// If still sparse, use all articles
if (recent.length < 10) recent = [...allArticles]

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

// ── Build the Haiku prompt ────────────────────────────────────────
function buildPrompt(articles) {
  const articleList = articles.map((a, i) => {
    const excerpt = cleanExcerpt(a.excerpt)
    return `${i}: "${a.title}" | ${a.source} | ${a.date}${excerpt ? ' | ' + excerpt : ''}`
  }).join('\n')

  return `You are a senior AI intelligence analyst writing the weekly briefing for European pharmaceutical and regulatory science professionals: regulatory scientists, pharma R&D directors, data coordinators, and clinical development teams.

This portal tracks 4 defined topic domains. Your briefing MUST map each article to one of these 5 sections:

SECTION DEFINITIONS:
1. "frontier"        → Frontier AI & LLMs: new model releases, AI labs (OpenAI/Anthropic/DeepMind/Meta/Mistral), LLM benchmarks, AI agents, AI safety/alignment, foundation models, AI policy/regulation globally
2. "regulatory"      → Regulatory Science: EMA, FDA, MHRA, ICH guidance, marketing authorisation, AI Act compliance, pharmacovigilance, GMP, PSUR, clinical trial regulations, EU regulatory frameworks
3. "drug-discovery"  → Drug Discovery AI: ADMET prediction, molecular docking, generative chemistry, protein folding, lead optimisation, QSAR, cheminformatics, drug design, structure-based design, antibiotic discovery
4. "clinical-ai"     → Clinical AI: AI in diagnostics, radiology/pathology AI, clinical decision support, patient outcome prediction, biomarker discovery, real-world evidence, EHR/EMR AI, clinical trial AI
5. "data-governance" → Data & Governance: EHDS, IDMP, FHIR, OMOP, Darwin EU, RWD/RWE frameworks, data standards, interoperability, FAIR data, federated learning for health data, health data governance

Analyze the articles below and write an EXHAUSTIVE expert weekly briefing. Return ONLY a valid JSON object — no markdown, no backticks, no extra text.

REQUIRED JSON STRUCTURE:
{
  "leadStory": {
    "headline": "10-14 words, declarative, punchy",
    "standfirst": "One sentence: the single most consequential development this week and why it matters",
    "body": "3-4 sentences: expert framing, context, implications for pharma/regulatory professionals. Answer 'so what?'",
    "sourceIndices": [0]
  },
  "sections": [
    {
      "id": "frontier",
      "title": "Frontier AI & LLMs",
      "icon": "🤖",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences, direct and expert", "sourceIndices": [1] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [2] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [3] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [4] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [5] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [6] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [7] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [8] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [9] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [10] }
      ]
    },
    {
      "id": "regulatory",
      "title": "Regulatory Science",
      "icon": "🏛️",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [11] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [12] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [13] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [14] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [15] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [16] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [17] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [18] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [19] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [20] }
      ]
    },
    {
      "id": "drug-discovery",
      "title": "AI in Drug Discovery",
      "icon": "🧬",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [21] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [22] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [23] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [24] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [25] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [26] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [27] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [28] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [29] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [30] }
      ]
    },
    {
      "id": "clinical-ai",
      "title": "Clinical AI",
      "icon": "🔬",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [31] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [32] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [33] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [34] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [35] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [36] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [37] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [38] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [39] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [40] }
      ]
    },
    {
      "id": "data-governance",
      "title": "Data & Governance",
      "icon": "📊",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [41] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [42] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [43] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [44] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [45] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [46] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [47] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [48] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [49] },
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [50] }
      ]
    }
  ],
  "editorNote": "1-2 sentences: the week's overarching theme — what a senior professional needs to remember"
}

RULES:
- Write as a domain expert, not a journalist. Implications first, facts second.
- NEVER start with "This week...", "In recent...", "The latest..."
- Headlines: declarative, verb-led (e.g. "LLMs Outperform Clinical AI Tools on Diagnostic Benchmarks")
- sourceIndices must be valid 0-based indices from the articles list below
- Every item must cite at least one source index
- EXHAUSTIVE COVERAGE: assign EVERY article to its most relevant section — do not leave articles uncovered
- Each section MUST have EXACTLY 10 items — the template shows 10 rows, fill them all
- Body text answers: "What does this mean for my work?"
- Drug Discovery and Clinical AI are SEPARATE sections — do not merge them

ARTICLES (index | title | source | date | excerpt):
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
