'use strict';

/* ── State ── */
let activeFilter      = 'all';   // type filter
let activeTopicFilter = 'all';   // topic filter
let searchQuery       = '';
let ALL_ARTICLES      = [];      // populated from articles.json

/* ── Topic filter definitions ── */
const TOPIC_FILTERS = {
  regulatory: {
    label: '🏛️ Regulatory science',
    keywords: ['ema', 'fda', 'chmp', 'regulatory', 'guidance', 'prime', 'conditional marketing',
                'marketing authorisation', 'mhra', 'who', 'ich', 'reflection paper', 'epar',
                'orphan', 'advanced therapy', 'atmp', 'qualification', 'benefit-risk', 'label',
                'approval', 'submission', 'dossier', 'ctd', 'ich', 'signal detection', 'psur',
                'rmp', 'risk management', 'post-market', 'pharmacopoeia', 'gmp', 'gdp'],
  },
  'data-governance': {
    label: '📊 Data governance',
    keywords: ['ehds', 'european health data space', 'idmp', 'fhir', 'data governance',
                'federated learning', 'privacy', 'gdpr', 'real-world data', 'rwd',
                'rwe', 'real-world evidence', 'interoperability', 'data standard',
                'omop', 'cdm', 'health data', 'data sharing', 'data quality',
                'data lake', 'data platform', 'synthetic data', 'fair data',
                'linked data', 'data space', 'consent', 'pseudonymisation',
                'anonymisation', 'secondary use', 'ehr', 'electronic health record'],
  },
  'drug-discovery': {
    label: '🧬 AI in drug discovery',
    keywords: ['drug discovery', 'drug design', 'drug development', 'target identification',
                'lead optimisation', 'lead optimization', 'admet', 'alphafold',
                'molecular', 'molecule', 'compound', 'scaffold', 'generative chemistry',
                'de novo', 'binding affinity', 'protein structure', 'virtual screening',
                'high-throughput screening', 'hit identification', 'medicinal chemistry',
                'pharmacophore', 'docking', 'qsar', 'cheminformatics', 'bioinformatics',
                'multi-omics', 'genomics', 'proteomics', 'biomarker', 'target validation',
                'phenotypic screening', 'graph neural network', 'gnn', 'diffusion model',
                'generative model', 'foundation model', 'repurposing', 'repositioning'],
  },
  'clinical-ai': {
    label: '🔬 Clinical AI',
    keywords: ['clinical trial', 'adaptive trial', 'decentralised trial', 'pharmacovigilance',
                'adverse event', 'signal', 'rwe', 'real-world evidence', 'patient stratification',
                'patient selection', 'endpoint', 'surrogate endpoint', 'biomarker',
                'precision medicine', 'digital biomarker', 'wearable', 'ehr', 'emr',
                'electronic health record', 'medical imaging', 'radiology', 'pathology',
                'diagnosis', 'prognosis', 'treatment response', 'clinical decision',
                'nlp', 'natural language processing', 'medical writing', 'protocol',
                'basket trial', 'umbrella trial', 'platform trial', 'rct'],
  },
};

/* ── Type config ── */
const TYPE_CONFIG = {
  news:    { icon: '📰', label: 'News',             iconClass: 'icon-news',    badgeClass: 'badge-type-news'    },
  paper:   { icon: '📄', label: 'Scientific paper',  iconClass: 'icon-paper',   badgeClass: 'badge-type-paper'   },
  webinar: { icon: '🎥', label: 'Webinar',           iconClass: 'icon-webinar',  badgeClass: 'badge-type-webinar' },
  seminar: { icon: '🎓', label: 'Seminar / Event',   iconClass: 'icon-seminar',  badgeClass: 'badge-type-seminar' },
  ainews:  { icon: '🤖', label: 'AI news',           iconClass: 'icon-ainews',   badgeClass: 'badge-type-ainews'  },
};

/* ── Helpers ── */
function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function matchesTopic(article, topicKey) {
  if (topicKey === 'all') return true;
  const topic = TOPIC_FILTERS[topicKey];
  if (!topic) return true;
  const haystack = [
    article.title,
    article.excerpt,
    ...(article.tags || []),
    article.source,
    article.badge || '',
  ].join(' ').toLowerCase();
  return topic.keywords.some(kw => haystack.includes(kw));
}

/* ── Filtering ── */
function filterArticles() {
  return ALL_ARTICLES.filter(a => {
    const matchType  = activeFilter === 'all' || a.type === activeFilter;
    const matchTopic = matchesTopic(a, activeTopicFilter);
    const q = searchQuery.toLowerCase();
    const matchSearch = !q ||
      a.title.toLowerCase().includes(q) ||
      a.excerpt.toLowerCase().includes(q) ||
      (a.tags || []).some(t => t.toLowerCase().includes(q)) ||
      a.source.toLowerCase().includes(q);
    return matchType && matchTopic && matchSearch;
  });
}

/* ── Render Featured Cards ── */
function renderFeatured(articles) {
  const featured = articles.filter(a => a.featured).slice(0, 3);
  const container = document.getElementById('featured-grid');
  if (!container) return;
  if (featured.length === 0) { container.innerHTML = ''; return; }
  container.innerHTML = featured.map((a, i) => {
    const cfg = TYPE_CONFIG[a.type] || TYPE_CONFIG.news;
    const isFirst = i === 0;
    return `
      <article class="card-featured" onclick="window.open('${a.url}','_blank')">
        <div class="card-featured-image">${cfg.icon}</div>
        <div class="card-featured-body">
          <div class="card-meta">
            <span class="badge ${cfg.badgeClass}">${cfg.label}</span>
            ${a.badge ? `<span class="badge badge-label">${a.badge}</span>` : ''}
            <span class="card-meta-source">${a.source}</span>
            <span class="card-meta-date">${formatDate(a.date)}</span>
          </div>
          <h3 class="card-title">${a.title}</h3>
          <p class="card-excerpt">${a.excerpt}</p>
          ${a.eventDate ? `<p class="card-event-date">📅 ${a.eventDate}</p>` : ''}
          <div class="card-footer">
            <div class="card-tags">
              ${(a.tags || []).slice(0, isFirst ? 4 : 2).map(t => `<span class="tag">${t}</span>`).join('')}
            </div>
            <span class="read-time">⏱ ${a.readTime}</span>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

/* ── Render Article List ── */
function renderList(articles) {
  const showFeatured = activeFilter === 'all' && activeTopicFilter === 'all' && !searchQuery;
  const list = showFeatured ? articles.filter(a => !a.featured) : articles;
  const container = document.getElementById('articles-list');
  if (!container) return;
  if (list.length === 0) {
    container.innerHTML = `
      <div class="no-results">
        <div class="no-results-icon">🔍</div>
        <h3>No results found</h3>
        <p>Try adjusting your search or filter criteria.</p>
      </div>`;
    return;
  }
  container.innerHTML = list.map(a => {
    const cfg = TYPE_CONFIG[a.type] || TYPE_CONFIG.news;
    const isEvent = a.type === 'webinar' || a.type === 'seminar';
    return `
      <article class="card-list" onclick="window.open('${a.url}','_blank')" style="cursor:pointer">
        <div class="card-list-icon ${cfg.iconClass}">${cfg.icon}</div>
        <div class="card-list-body">
          <div class="card-meta">
            <span class="badge ${cfg.badgeClass}">${cfg.label}</span>
            ${a.badge ? `<span class="badge badge-label">${a.badge}</span>` : ''}
            <span class="card-meta-source">${a.source}</span>
            <span class="card-meta-date">${formatDate(a.date)}</span>
          </div>
          <h3 class="card-title">${a.title}</h3>
          <p class="card-excerpt">${a.excerpt}</p>
          ${a.eventDate ? `<p class="card-event-date">📅 ${a.eventDate}</p>` : ''}
          <div class="card-footer">
            <div class="card-tags">
              ${(a.tags || []).slice(0, 3).map(t => `<span class="tag">${t}</span>`).join('')}
            </div>
            ${isEvent
              ? `<a class="event-link-btn" href="${a.url}" target="_blank" onclick="event.stopPropagation()">View event →</a>`
              : `<span class="read-time">⏱ ${a.readTime}</span>`}
          </div>
        </div>
      </article>
    `;
  }).join('');
}

/* ── Update filter counts ── */
function updateFilterCounts() {
  const base = ALL_ARTICLES.filter(a => {
    const matchTopic = matchesTopic(a, activeTopicFilter);
    if (!searchQuery) return matchTopic;
    const q = searchQuery.toLowerCase();
    return matchTopic && (
      a.title.toLowerCase().includes(q) ||
      a.excerpt.toLowerCase().includes(q) ||
      (a.tags || []).some(t => t.toLowerCase().includes(q))
    );
  });

  document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
    const f = btn.dataset.filter;
    const count = f === 'all' ? base.length : base.filter(a => a.type === f).length;
    const el = btn.querySelector('.count');
    if (el) el.textContent = count;
  });
}

/* ── Render events sidebar from real articles ── */
function renderEvents() {
  const container = document.getElementById('event-list');
  if (!container) return;

  // Pull webinar + seminar articles, most recent first, max 6
  const events = ALL_ARTICLES
    .filter(a => a.type === 'webinar' || a.type === 'seminar')
    .slice(0, 6);

  if (events.length === 0) {
    // Fallback to static list if pipeline hasn't fetched events yet
    container.innerHTML = UPCOMING_EVENTS.map(e => {
      const parts = e.date.split(' ');
      const cfg = TYPE_CONFIG[e.type] || { icon: '📅' };
      return `
        <div class="event-item">
          <div class="event-date-badge">
            <div class="month">${parts[0]}</div>
            <div class="day">${parts[1] || ''}</div>
          </div>
          <div class="event-info">
            <div class="event-title">${e.title}</div>
            <div class="event-location">${cfg.icon} ${e.location}</div>
          </div>
        </div>`;
    }).join('');
    return;
  }

  container.innerHTML = events.map(a => {
    const cfg = TYPE_CONFIG[a.type] || { icon: '📅' };
    const d = new Date(a.date);
    const month = d.toLocaleDateString('en-GB', { month: 'short' }).toUpperCase();
    const day   = d.getDate();
    return `
      <a class="event-item event-item-link" href="${a.url}" target="_blank">
        <div class="event-date-badge">
          <div class="month">${month}</div>
          <div class="day">${day}</div>
        </div>
        <div class="event-info">
          <div class="event-title">${a.title}</div>
          <div class="event-location">${cfg.icon} ${a.source}</div>
        </div>
      </a>`;
  }).join('');
}

/* ── Render stats ── */
function renderStats() {
  const container = document.getElementById('hero-stats');
  if (!container) return;
  container.innerHTML = STATS.map(s => `
    <div class="stat-item">
      <div class="stat-value">${s.value}</div>
      <div class="stat-label">${s.label}</div>
    </div>`).join('');
}

/* ── Topic heading banner ── */
function renderTopicBanner() {
  const banner = document.getElementById('topic-banner');
  if (!banner) return;
  if (activeTopicFilter === 'all') {
    banner.style.display = 'none';
    return;
  }
  const topic = TOPIC_FILTERS[activeTopicFilter];
  banner.style.display = '';
  banner.innerHTML = `
    <span class="topic-banner-label">${topic.label}</span>
    <button class="topic-banner-clear" onclick="clearTopicFilter()">✕ Clear filter</button>
  `;
}

function clearTopicFilter() {
  activeTopicFilter = 'all';
  document.querySelectorAll('.topic-btn').forEach(b => b.classList.toggle('active', b.dataset.topic === 'all'));
  document.querySelectorAll('nav a[data-topic-link]').forEach(l => l.classList.remove('active'));
  render();
}

/* ── Main render ── */
function render() {
  const filtered = filterArticles();
  const showFeatured = activeFilter === 'all' && activeTopicFilter === 'all' && !searchQuery;
  const featuredSection = document.getElementById('featured-section');
  if (featuredSection) featuredSection.style.display = showFeatured ? '' : 'none';
  if (showFeatured) renderFeatured(ALL_ARTICLES);
  renderList(filtered);
  updateFilterCounts();
  renderTopicBanner();
  renderEvents();
}

/* ── Load articles from JSON ── */
async function loadArticles() {
  try {
    const res = await fetch('js/articles.json?v=' + Date.now());
    if (!res.ok) throw new Error('fetch failed');
    ALL_ARTICLES = await res.json();
    ALL_ARTICLES.sort((a, b) => new Date(b.date) - new Date(a.date));
  } catch (e) {
    console.warn('Could not load articles.json, using fallback data.', e);
    ALL_ARTICLES = typeof ARTICLES !== 'undefined' ? ARTICLES : [];
  }
  render();
}

/* ── Type filter buttons ── */
function initFilters() {
  document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.filter;
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('nav a[data-filter-link]').forEach(l => l.classList.remove('active'));
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ── Topic filter buttons ── */
function initTopicFilters() {
  document.querySelectorAll('.topic-btn[data-topic]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTopicFilter = btn.dataset.topic;
      document.querySelectorAll('.topic-btn[data-topic]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      // Sync nav
      document.querySelectorAll('nav a[data-topic-link]').forEach(l =>
        l.classList.toggle('active', l.dataset.topicLink === activeTopicFilter)
      );
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ── Nav ── */
function initNav() {
  // Type-based nav links
  document.querySelectorAll('nav a[data-filter-link]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      activeFilter = link.dataset.filterLink;
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b =>
        b.classList.toggle('active', b.dataset.filter === activeFilter)
      );
      document.querySelectorAll('nav a[data-filter-link]').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
    });
  });

  // Topic-based nav links
  document.querySelectorAll('nav a[data-topic-link]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      activeTopicFilter = link.dataset.topicLink;
      document.querySelectorAll('.topic-btn[data-topic]').forEach(b =>
        b.classList.toggle('active', b.dataset.topic === activeTopicFilter)
      );
      document.querySelectorAll('nav a[data-topic-link]').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      // Reset type filter to all when picking a topic
      activeFilter = 'all';
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b =>
        b.classList.toggle('active', b.dataset.filter === 'all')
      );
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

/* ── Search ── */
function initSearch() {
  document.querySelectorAll('.search-input').forEach(input => {
    input.addEventListener('input', e => {
      searchQuery = e.target.value.trim();
      document.querySelectorAll('.search-input').forEach(i => { if (i !== e.target) i.value = searchQuery; });
      render();
    });
  });
}

/* ── Tag clicks ── */
function initTagClicks() {
  document.addEventListener('click', e => {
    if (e.target.classList.contains('tag') || e.target.classList.contains('tag-cloud-item')) {
      const tag = e.target.textContent.trim();
      searchQuery = tag;
      document.querySelectorAll('.search-input').forEach(i => i.value = tag);
      activeFilter = 'all';
      activeTopicFilter = 'all';
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b =>
        b.classList.toggle('active', b.dataset.filter === 'all')
      );
      document.querySelectorAll('.topic-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.topic === 'all')
      );
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
    }
  });
}

/* ── Subscribe modal ── */
function initSubscribeModal() {
  const modal = document.getElementById('subscribe-modal');
  document.querySelectorAll('[data-open-subscribe]').forEach(btn =>
    btn.addEventListener('click', () => modal?.classList.add('open'))
  );
  document.getElementById('modal-close')?.addEventListener('click', () => modal?.classList.remove('open'));
  modal?.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });
  document.getElementById('subscribe-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.textContent = '✓ Subscribed!';
    btn.style.background = '#059669';
    setTimeout(() => modal?.classList.remove('open'), 1500);
  });
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  renderStats();
  renderEvents();
  initFilters();
  initTopicFilters();
  initSearch();
  initTagClicks();
  initSubscribeModal();
  initNav();
  loadArticles();
});
