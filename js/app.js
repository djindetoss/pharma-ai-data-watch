'use strict';

/* ── State ── */
let activeFilter = 'all';
let searchQuery = '';
let ALL_ARTICLES = [];   // populated from articles.json

/* ── Type config ── */
const TYPE_CONFIG = {
  news:    { icon: '📰', label: 'News',             iconClass: 'icon-news',    badgeClass: 'badge-type-news'    },
  paper:   { icon: '📄', label: 'Scientific paper',  iconClass: 'icon-paper',   badgeClass: 'badge-type-paper'   },
  webinar: { icon: '🎥', label: 'Webinar',           iconClass: 'icon-webinar',  badgeClass: 'badge-type-webinar' },
  seminar: { icon: '🎓', label: 'Seminar',           iconClass: 'icon-seminar',  badgeClass: 'badge-type-seminar' },
  ainews:  { icon: '🤖', label: 'AI news',           iconClass: 'icon-ainews',   badgeClass: 'badge-type-ainews'  },
};

/* ── Helpers ── */
function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/* ── Filtering ── */
function filterArticles() {
  return ALL_ARTICLES.filter(a => {
    const matchType = activeFilter === 'all' || a.type === activeFilter;
    const q = searchQuery.toLowerCase();
    const matchSearch = !q ||
      a.title.toLowerCase().includes(q) ||
      a.excerpt.toLowerCase().includes(q) ||
      (a.tags || []).some(t => t.toLowerCase().includes(q)) ||
      a.source.toLowerCase().includes(q);
    return matchType && matchSearch;
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
  const showFeatured = activeFilter === 'all' && !searchQuery;
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
    return `
      <article class="card-list" onclick="window.open('${a.url}','_blank')">
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
            <span class="read-time">⏱ ${a.readTime}</span>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

/* ── Update filter counts ── */
function updateFilterCounts() {
  const base = ALL_ARTICLES.filter(a => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return a.title.toLowerCase().includes(q) ||
      a.excerpt.toLowerCase().includes(q) ||
      (a.tags || []).some(t => t.toLowerCase().includes(q));
  });

  document.querySelectorAll('.filter-btn[data-filter]').forEach(btn => {
    const f = btn.dataset.filter;
    const count = f === 'all' ? base.length : base.filter(a => a.type === f).length;
    const el = btn.querySelector('.count');
    if (el) el.textContent = count;
  });
}

/* ── Render events ── */
function renderEvents() {
  const container = document.getElementById('event-list');
  if (!container) return;
  container.innerHTML = UPCOMING_EVENTS.map(e => {
    const [month, day] = e.date.split(' ');
    const cfg = TYPE_CONFIG[e.type] || { icon: '📅' };
    return `
      <div class="event-item">
        <div class="event-date-badge">
          <div class="month">${month}</div>
          <div class="day">${day}</div>
        </div>
        <div class="event-info">
          <div class="event-title">${e.title}</div>
          <div class="event-location">${cfg.icon} ${e.location}</div>
        </div>
      </div>`;
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

/* ── Main render ── */
function render() {
  const filtered = filterArticles();
  const showFeatured = activeFilter === 'all' && !searchQuery;

  const featuredSection = document.getElementById('featured-section');
  if (featuredSection) featuredSection.style.display = showFeatured ? '' : 'none';
  if (showFeatured) renderFeatured(ALL_ARTICLES);

  renderList(filtered);
  updateFilterCounts();
}

/* ── Load articles from JSON ── */
async function loadArticles() {
  try {
    const res = await fetch('js/articles.json?v=' + Date.now());
    if (!res.ok) throw new Error('fetch failed');
    ALL_ARTICLES = await res.json();
    // Sort newest first
    ALL_ARTICLES.sort((a, b) => new Date(b.date) - new Date(a.date));
  } catch (e) {
    console.warn('Could not load articles.json, using fallback data.', e);
    ALL_ARTICLES = typeof ARTICLES !== 'undefined' ? ARTICLES : [];
  }
  render();
}

/* ── Filter buttons ── */
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
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));
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

/* ── Nav ── */
function initNav() {
  document.querySelectorAll('nav a[data-filter-link]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const filter = link.dataset.filterLink;
      activeFilter = filter;
      document.querySelectorAll('.filter-btn[data-filter]').forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
      document.querySelectorAll('nav a[data-filter-link]').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      render();
      document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  renderStats();
  renderEvents();
  initFilters();
  initSearch();
  initTagClicks();
  initSubscribeModal();
  initNav();
  loadArticles();  // async: fetches articles.json then renders
});
