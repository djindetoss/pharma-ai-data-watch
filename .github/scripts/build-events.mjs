/**
 * build-events.mjs
 * Generates portal/events.html from portal/data/events.json
 *
 * Source of truth: events.json
 * - Every event MUST have a verified url_verified date (YYYY-MM-DD)
 * - Events with url_verified older than MAX_STALENESS_DAYS are flagged
 * - Events with date < today are auto-excluded (past events)
 *
 * Run: node .github/scripts/build-events.mjs
 */

import { readFileSync, writeFileSync } from 'fs'
import { fileURLToPath } from 'url'
import path from 'path'

const __dir = path.dirname(fileURLToPath(import.meta.url))
const ROOT   = path.resolve(__dir, '../..')
const JSON_PATH = path.join(ROOT, 'portal/data/events.json')
const HTML_PATH = path.join(ROOT, 'portal/events.html')

const MAX_STALENESS_DAYS = 90   // flag events not re-verified in 90 days
const TODAY = new Date().toISOString().split('T')[0]

// ── Load events ────────────────────────────────────────────────────────────────
const events = JSON.parse(readFileSync(JSON_PATH, 'utf8'))

// Validate all events have required fields
const required = ['id', 'title', 'org', 'url', 'url_verified', 'date', 'category', 'description']
let warnings = []
for (const ev of events) {
  for (const f of required) {
    if (!ev[f]) warnings.push(`⚠️  Event "${ev.id || '?'}" missing field: ${f}`)
  }
  // Check staleness
  const verifiedDate = new Date(ev.url_verified)
  const diffDays = Math.floor((Date.now() - verifiedDate) / 86400000)
  if (diffDays > MAX_STALENESS_DAYS) {
    warnings.push(`⚠️  Event "${ev.id}" url_verified is ${diffDays} days old — re-verify: ${ev.url}`)
  }
}
if (warnings.length) {
  console.warn('\n' + warnings.join('\n') + '\n')
}

// ── Group by category ──────────────────────────────────────────────────────────
const SECTIONS = [
  { cat: 'regulatory', icon: '🇪🇺', title: 'Regulatory Science — EMA · FDA · TOPRA · RAPS · DIA', source: { url: 'https://www.ema.europa.eu/en/events/upcoming-events', label: 'View all EMA events →' } },
  { cat: 'data',       icon: '📊',  title: 'European Health Data Space (EHDS) & Data Standards',  source: { url: 'https://health.ec.europa.eu/ehealth-digital-health-and-care/european-health-data-space-regulation-ehds_en', label: 'EHDS official page →' } },
  { cat: 'ai-discovery', icon: '🧬', title: 'AI in Drug Discovery & Computational Biology',        source: { url: 'https://intuitionlabs.ai/conferences', label: 'Life sciences AI directory →' } },
  { cat: 'clinical',   icon: '🔬',  title: 'Clinical AI, Real-world Evidence & Pharmacovigilance', source: null },
  { cat: 'general',    icon: '🤖',  title: 'Frontier AI — LLMs, Foundation Models & Governance',  source: { url: 'https://oecd.ai/en/', label: 'OECD AI Observatory →' } },
]

function badge(label, cls) {
  return `<span class="event-badge eb-${cls}">${label}</span>`
}

function dateBlock(ev) {
  const d = ev.display
  if (d.ongoing) {
    return `<div class="event-card-date ongoing"><div class="month">${d.month}</div><div class="day">${d.day}</div></div>`
  }
  return `<div class="event-card-date"><div class="month">${d.month}</div><div class="day">${d.day}</div>${d.year ? `<div class="year">${d.year}</div>` : ''}</div>`
}

function eventCard(ev) {
  const stale = (() => {
    const d = new Date(ev.url_verified)
    return Math.floor((Date.now() - d) / 86400000) > MAX_STALENESS_DAYS
  })()

  const staleBadge = stale ? `<span class="event-badge eb-stale" title="Link not re-verified recently">⚠️ Verify link</span>` : ''
  const badges = (ev.badges || []).map(([label, cls]) => badge(label, cls)).join('\n            ')

  return `
        <a class="event-card" href="${ev.url}" target="_blank" rel="noopener" data-date="${ev.date}" data-id="${ev.id}">
          <div class="event-card-top">
            ${dateBlock(ev)}
            <div class="event-card-meta">
              <div class="event-card-title">${ev.title}</div>
              <div class="event-card-org">${ev.org}</div>
            </div>
          </div>
          <div class="event-card-badges">
            ${badges}
            ${staleBadge}
          </div>
          <div class="event-card-desc">${ev.description}</div>
          <span class="event-card-link">${ev.link_text || 'More info →'}</span>
        </a>`
}

function section(sec, sectionEvents) {
  if (!sectionEvents.length) return ''
  const source = sec.source
    ? `<a href="${sec.source.url}" target="_blank" class="events-section-source">${sec.source.label}</a>`
    : ''
  return `
    <!-- ══════════════════════════════════════════════════════
         ${sec.title.toUpperCase()}
    ══════════════════════════════════════════════════════ -->
    <div class="events-section" data-cat="${sec.cat}">
      <div class="events-section-header">
        <span class="events-section-icon">${sec.icon}</span>
        <span class="events-section-title">${sec.title}</span>
        ${source}
      </div>
      <div class="events-grid">
        ${sectionEvents.map(eventCard).join('')}
      </div>
    </div>`
}

// ── Read existing events.html (for head/foot) ──────────────────────────────────
const existing = readFileSync(HTML_PATH, 'utf8')

// Extract everything before <!-- ── BODY ── --> and after <!-- /events-body -->
const bodyStart = existing.indexOf('<!-- Category filter pills -->')
const bodyEnd   = existing.indexOf('</div><!-- /events-body -->')

if (bodyStart === -1 || bodyEnd === -1) {
  console.error('Could not find body markers in events.html — aborting')
  process.exit(1)
}

const head = existing.slice(0, bodyStart)
const foot = existing.slice(bodyEnd + '</div><!-- /events-body -->'.length)

// ── Build body ─────────────────────────────────────────────────────────────────
const upcomingCount = events.filter(e => {
  const d = e.date
  return d && d !== '2099-12-31' && d >= TODAY
}).length

const body = `<!-- Category filter pills -->
    <div class="cat-filter">
      <button class="cat-pill active" data-cat="all">🗂 All events</button>
      <button class="cat-pill" data-cat="regulatory">🏛️ Regulatory science</button>
      <button class="cat-pill" data-cat="data">📊 Data &amp; EHDS</button>
      <button class="cat-pill" data-cat="ai-discovery">🧬 AI drug discovery</button>
      <button class="cat-pill" data-cat="clinical">🔬 Clinical AI &amp; RWE</button>
      <button class="cat-pill" data-cat="general">🤖 Frontier AI &amp; LLMs</button>
    </div>
${SECTIONS.map(sec => section(sec, events.filter(e => e.category === sec.cat))).join('\n')}
`

// ── Write output ───────────────────────────────────────────────────────────────
const output = head + body + '\n  </div><!-- /events-body -->' + foot
writeFileSync(HTML_PATH, output, 'utf8')

console.log(`✅ events.html generated from ${events.length} events (${upcomingCount} upcoming dated)`)
if (warnings.length) {
  console.log(`⚠️  ${warnings.length} warning(s) — see above`)
  process.exit(1)  // fail CI if stale links detected
}
