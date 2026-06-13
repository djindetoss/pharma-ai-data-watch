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

// Top 40 articles for the prompt
const selected = scored.slice(0, 40)

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

Analyze the articles below and write an expert weekly briefing. Return ONLY a valid JSON object — no markdown, no backticks, no extra text.

REQUIRED JSON STRUCTURE:
{
  "leadStory": {
    "headline": "10-14 words, declarative, punchy",
    "standfirst": "One sentence: the single most consequential AI development this week and why it matters",
    "body": "3-4 sentences: expert framing, context, implications for pharma/regulatory professionals. Answer 'so what?'",
    "sourceIndices": [0]
  },
  "sections": [
    {
      "id": "frontier",
      "title": "Frontier AI & Foundation Models",
      "icon": "🤖",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences, direct and expert", "sourceIndices": [1, 2] }
      ]
    },
    {
      "id": "regulatory",
      "title": "Regulatory & Policy",
      "icon": "🏛️",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [3] }
      ]
    },
    {
      "id": "research",
      "title": "Research Spotlight",
      "icon": "🔬",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [4, 5] }
      ]
    },
    {
      "id": "industry",
      "title": "Industry & Ecosystem",
      "icon": "🏢",
      "items": [
        { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [6] }
      ]
    }
  ],
  "pharmaFocus": {
    "headline": "Pharma & Drug Development — What It Means",
    "standfirst": "One sentence: the most important takeaway for drug development and EU regulatory science this week",
    "items": [
      { "headline": "8-10 words", "body": "2-3 sentences on implications for drug R&D, regulatory submissions, or clinical AI", "sourceIndices": [7, 8] },
      { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [9] },
      { "headline": "8-10 words", "body": "2-3 sentences", "sourceIndices": [10] }
    ]
  },
  "editorNote": "1-2 sentences: the week's overarching theme — what a senior professional needs to remember"
}

RULES:
- Write as a domain expert, not a journalist. Implications first, facts second.
- NEVER start with "This week...", "In recent...", "The latest..."
- Headlines: declarative, verb-led (e.g. "LLMs Outperform Clinical AI Tools on Diagnostic Benchmarks")
- sourceIndices must be valid 0-based indices from the articles list below
- Every item must cite at least one source
- pharmaFocus: 3 items minimum, all must relate to drug development, regulatory science, or clinical AI
- Each section: 2-4 items
- Body text answers: "What does this mean for my work?"

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
      max_tokens: 2500,
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

  const leadIdx = 0
  const regulatoryArticles = articles.filter(a => a.topic === 'regulatory' || /regulatory/i.test(a.badge || '')).slice(0, 4)
  const researchArticles   = articles.filter(a => a.type === 'paper').slice(0, 4)
  const ainewsArticles     = articles.filter(a => a.type === 'ainews').slice(0, 4)
  const pharmaArticles     = articles.filter(a => ['drug-discovery', 'clinical-ai'].includes(a.topic)).slice(0, 4)
  const industryArticles   = articles.filter(a => !['regulatory'].includes(a.topic) && a.type === 'news').slice(0, 3)

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
        title: 'Frontier AI & Foundation Models',
        icon:  '🤖',
        items: ainewsArticles.slice(0, 3).map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'regulatory',
        title: 'Regulatory & Policy',
        icon:  '🏛️',
        items: regulatoryArticles.slice(0, 3).map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'research',
        title: 'Research Spotlight',
        icon:  '🔬',
        items: researchArticles.slice(0, 3).map(a => makeItem(a, idxOf(a))),
      },
      {
        id:    'industry',
        title: 'Industry & Ecosystem',
        icon:  '🏢',
        items: industryArticles.slice(0, 3).map(a => makeItem(a, idxOf(a))),
      },
    ].filter(s => s.items.length > 0),
    pharmaFocus: {
      headline:   'Pharma & Drug Development — What It Means',
      standfirst: 'Key developments in AI-driven drug discovery, clinical AI, and EU regulatory science.',
      items:      pharmaArticles.slice(0, 4).map(a => makeItem(a, idxOf(a))),
    },
    editorNote: `${articles.length} sources analysed this week across regulatory, research, and industry channels. Pipeline-generated summary — no AI editorial layer.`,
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
    pharmaFocus: {
      ...content.pharmaFocus,
      items: (content.pharmaFocus?.items || []).map(processItem),
    },
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
const monthFr = monday.toLocaleString('fr-FR', { month: 'long' })
const weekLabel = `Semaine ${week} — ${monday.getDate()} ${monthFr} ${year}`

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
