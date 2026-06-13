# Pharma AI & Data Watch — Monthly Digests

This directory contains the auto-generated monthly digest files.
**No manual editing required** — all files are produced by `.github/scripts/build-digest.mjs`.

## Files

| File | Description |
|------|-------------|
| `index.json` | List of all published digests (newest first) |
| `YYYY-MM.json` | Cumulative digest for that month |

## How it works

1. Every **Monday at 07:00 UTC**, the `Build Weekly Digest` GitHub Actions workflow runs automatically.
2. It reads `portal/js/articles.json` (produced by the daily ingestion pipeline).
3. Articles from the current month (or ingested in the past 7 days) are added to the current `YYYY-MM.json`.
4. The digest is **cumulative** — each Monday adds new articles on top of what was already there.
5. Files are committed to `master` and synced to `gh-pages` automatically.

**Cost: $0.00** — zero API calls. Pure Node.js with native `fs`/`path` modules only.

## Manual trigger

From GitHub: **Actions → Build Weekly Digest → Run workflow**.

## JSON structure

### `index.json`
```json
[
  {
    "id": "2026-06",
    "label": "juin 2026",
    "totalArticles": 42,
    "updatedAt": "2026-06-09T07:05:00.000Z"
  }
]
```

### `YYYY-MM.json`
```json
{
  "id": "2026-06",
  "generatedAt": "2026-06-09T07:05:00.000Z",
  "weekStart": "2026-06-02",
  "signal": {
    "monthLabel": "juin 2026",
    "totalArticles": 42,
    "categoryCounts": { "PHARMA": 12, "REGLEMENTAIRE": 10, "..." : "..." },
    "dominantCategory": "PHARMA",
    "dominantCategoryCount": 12,
    "topSources": ["EMA", "PubMed", "Nature"],
    "paperCount": 15,
    "criticalCount": 3,
    "importantCount": 28,
    "text": "Ce mois de juin 2026, le digest recense 42 articles…",
    "generatedAt": "2026-06-09T07:05:00.000Z"
  },
  "articles": [
    {
      "id": "auto-abc123",
      "title": "...",
      "titleFr": null,
      "source": "Nature Machine Intelligence",
      "url": "https://...",
      "publishedDate": "2026-06-07",
      "type": "paper",
      "category": "PHARMA",
      "relevance": "CRITIQUE",
      "summary": "2-3 sentence summary…",
      "regulatoryAngle": null,
      "tags": ["Drug discovery", "AlphaFold"],
      "badge": "Research",
      "topic": "drug-discovery",
      "authors": null,
      "country": null,
      "university": null,
      "lab": null
    }
  ]
}
```

## Article fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique article ID (from pipeline) |
| `title` | string | Article title |
| `titleFr` | null | Reserved for future French translation |
| `source` | string | Journal or news source name |
| `url` | string | Link to original article |
| `publishedDate` | YYYY-MM-DD | Publication date |
| `type` | string | `paper`, `news`, `ainews`, `seminar`, `webinar` |
| `category` | string | Auto-classified category (see below) |
| `relevance` | string | `CRITIQUE`, `IMPORTANT`, or `A_SURVEILLER` |
| `summary` | string | Cleaned excerpt (from Haiku if available, else raw) |
| `regulatoryAngle` | null | Reserved — would require LLM call |
| `tags` | string[] | Tags from pipeline |
| `badge` | string | Source badge (e.g. `PubMed`, `Regulatory`) |
| `topic` | string\|null | Pipeline topic (`drug-discovery`, `regulatory`, etc.) |

## Categories

| Key | Label |
|-----|-------|
| `PHARMA` | Pharma & biotech |
| `MEDECINE` | Médecine & santé |
| `REGLEMENTAIRE` | Réglementaire |
| `TECHNIQUE` | Technique |
| `ACADEMIQUE` | Académique |
| `SCIENCE` | Science (fallback) |
| `EUROPE` | Europe |
| `ETHIQUE` | Éthique & société |
| `ECONOMIE` | Économie & travail |
| `SECURITE` | Cybersécurité & IA |
| `GEOPOLITIQUE` | Géopolitique |
| `SOUVERAINETE` | Souveraineté numérique |
| `PHILOSOPHIE` | Philosophie & IA |
| `ENVIRONNEMENT` | Environnement |

## Optional: enable Haiku signal enrichment

The `signal.text` is currently a template string (cost $0).
To generate a richer AI-written summary (~$0.005/month extra):
1. Add a step in `build-digest.yml` after the Node script that calls Claude Haiku
   with the signal stats as input.
2. Patch the `signal.text` field in the JSON output.

Not implemented by default to keep cost at $0.
