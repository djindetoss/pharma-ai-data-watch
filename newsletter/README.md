# IncreaseNET AI Community – Newsletter

A bi-weekly newsletter for the IncreaseNET AI community (~45 colleagues from
18 European NCAs). It reuses what the daily pipeline already collects
(`portal/js/articles.json`). Each edition has:

1. **an introduction**: the main threads of the period, the highlight and what not
   to miss (written by the LLM; a plain automatic version without an API key);
2. **featured items, numbered #1, #2…**: a highlight, scientific articles and
   news & regulatory updates, strictly on AI and data for medicines, each with
   a summary, a short personal comment and a *Why it matters for NCAs* line;
3. **In brief**: up to 40 one-line notes grouped by theme (more scientific
   articles, medicines & health, regulation & law, research & methods, safety
   & privacy, tools), deliberately broader than the featured scope.

**Distribution is by e-mail only.** The newsletter is never published as a web
page (no GitHub Pages, no online archive): you receive it by e-mail and forward
it to the task group from your own mailbox.

```
articles.json (+ git history) ─► dedup ─► keyword pre-filter ─► LLM score (optional)
   ─► quotas & threshold (top-up to the minimum) ─► LLM summaries + comments (optional)
   ─► In-brief notes ─► introduction ─► drafts/DATE.yaml  ◄── you edit
   ─► render (e-mail HTML, text, Markdown) ─► PR ─► merge = validate ─► e-mail to you ─► you forward
```

| Path | What it is |
|---|---|
| `config.yaml` | everything editorial: window, frequency, quotas, thresholds, keywords, colours |
| `drafts/DATE.yaml` | the editable draft (plus rendered `.email.html`, `.txt`, `.md` previews) |
| `editions/DATE.yaml`, `editions.json` | validated editions and their numbers (used to re-send an edition) |
| `assets/increasenet-logo.png` | logo; the e-mail loads it from its raw URL in this repository (`config.yaml → logo_url`) |
| `send_email.py` | SMTP sender (standard library only) |
| `extract_palette.py` | extracts the brand colours from the logo |

## Install (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r newsletter/requirements-dev.txt
```

All commands run from the repository root.

## 1. Generate, edit, validate and send an edition

### Generate a draft

```bash
python -m newsletter draft                      # period = last 14 days up to today
python -m newsletter draft --end 2026-11-10 --days 21
python -m newsletter draft --no-llm             # keyword pre-filter only
```

With `ANTHROPIC_API_KEY` set, an LLM (model in `config.yaml → llm.model`) rates
the shortlisted items 0–10 and writes, for the retained ones, an original
plain-language summary, a short personal comment, a *Why it matters for NCAs*
line and tags. Without a
key, the selection uses the keyword score and the summaries are left as
`TODO` placeholders for you to write: abstracts are never copied.

Preview locally: open `newsletter/drafts/DATE.preview.html` in a browser
(same as the e-mail, but with the logo loaded from the repository).

### Links

Every link in the draft is opened when the draft is generated, and again each
time you push an edit to the draft PR (`python -m newsletter check-links DRAFT`):

- tracking and feed parameters are removed (`utm_*`, `?rss=1`, `?af=R`…), and
  redirects (doi.org, http→https, feed proxies) are replaced by the final
  address, so each link opens the page in one click;
- sites that refuse robots but work in a browser (some publishers answer 403)
  are kept as they are;
- a dead link (404, 410, DNS error, timeout) removes the In-brief line, and marks
  a featured item `link_check: BROKEN`; validation is refused until you fix the
  URL or delete the item.

Gmail ("google.com/url?q=…") and Outlook ("safelinks.protection.outlook.com")
wrap every link in their own security redirect when the recipient clicks. This
happens in the recipient's mailbox and cannot be turned off by the sender; the
address in the e-mail itself is the direct one (hover or right-click → copy link
to see it).

### Edit the draft

Open `newsletter/drafts/DATE.yaml`:

- **remove** an item: delete its block (from `- id:` to the next `- id:`);
- **reorder**: move blocks (the order in the file is the order in the newsletter);
- **promote** a runner-up: move its block from `runners_up` into `scientific_articles` or `news`;
- **highlight**: replace the block, or set `highlight: null`;
- edit `editorial`, `summary`, `comment`, `why_it_matters`, `tags` freely;
- `in_brief`: one `note` per line, grouped by `section`; delete, edit or move lines;
- items marked `below_threshold: true` were added to reach the minimum quota
  (`selection.fill_to_min`): keep or delete them.

The `comment` is the editor's voice: one to three sentences, first person,
conversational, adding what the summary does not say (what is surprising, a
caveat, a practical takeaway for assessors), with a light touch of humour when it
fits. The style guide given to the LLM is `COMMENT_STYLE` in `llm.py`; adjust it
there if the tone drifts. Delete the field to show no comment for an item.

`runners_up` and `stats` are never rendered. Then re-render only:

```bash
python -m newsletter render newsletter/drafts/DATE.yaml
```

The command lists any remaining `TODO` / `EDIT ME` markers.

### Validate

In the normal flow you **merge the draft pull request** and GitHub Actions
validates it and e-mails you the final version. By hand:

```bash
python -m newsletter publish newsletter/drafts/DATE.yaml   # refuses if TODO markers remain (--force to override)
```

Validation assigns the next edition number, stores the edition in
`editions/DATE.yaml` + `editions.json` and deletes the draft files. No web
page is produced.

### Send

```bash
python -m newsletter.send_email --draft newsletter/drafts/DATE.yaml --dry-run   # writes newsletter/out/DATE-draft.eml
python -m newsletter.send_email --edition DATE --dry-run                         # final edition
python -m newsletter.send_email --edition DATE                                   # really send (env vars below)
```

Open the `.eml` file with Mail/Outlook to check the result without sending anything.

## 2. Automation (GitHub Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `newsletter-draft.yml` | every Monday 08:00 UTC (+ manual) | if an edition is due: draft → branch `newsletter/draft-DATE` → pull request → `[DRAFT]` e-mail with the PR link |
| `newsletter-draft.yml` (rerender job) | you push an edit to the draft YAML in the PR | re-renders the previews in the PR |
| `newsletter-publish.yml` | a draft reaches `master` (= you merged the PR) | validate (number) → commit → final e-mail to you |

**Run it now**: Actions → *Newsletter – draft* → *Run workflow* (tick *force*).

> **One-time setting**: for the workflow to open the PR itself, enable
> *Settings → Actions → General → Workflow permissions → "Allow GitHub Actions to create and approve pull requests"*.
> Without it, the workflow still pushes the branch, prints a "compare" link
> and puts that link in the draft e-mail; you open the PR with one click.

## 3. Tuning

All in `config.yaml`:

| Setting | Effect |
|---|---|
| `schedule.window_days` | period covered (default 14) |
| `schedule.frequency_days` | the Monday cron only creates a draft if the last edition is at least this old (default 14). To change the weekday/hour, edit the `cron` line in `.github/workflows/newsletter-draft.yml` |
| `selection.papers` / `selection.news` | `min` and `max` featured items per section |
| `selection.fill_to_min`, `fill_floor` | top a thin period up to `min` with the best items below the threshold (never below `fill_floor`) |
| `in_brief.sections` | In-brief sections and the keywords that route an item to each |
| `in_brief.max_total`, `max_per_section`, `max_papers` | length of the In-brief part |
| `source.exclude_domains` | sites left out entirely (default: `ema.europa.eu`, already followed by readers) |
| `selection.min_llm_score` | final threshold (0–10) with the LLM |
| `selection.min_prefilter_score` | final threshold (0–10) without the LLM |
| `selection.shortlist_floor`, `shortlist_size` | what reaches the LLM |
| `prefilter.themes.*.keywords` / `weight` | priority themes; title hits count double (`title_multiplier`) |
| `prefilter.ai_gate` | an item must contain one of these to be considered |
| `prefilter.exclusions` | words that drop an item when found in the title |
| `prefilter.source_bonus` / `source_penalty` | trust adjustments by source name |
| `tags` | controlled tag vocabulary |
| `colors` | brand palette (see below) |

Tip: `python -m newsletter draft --no-llm` then read `stats` and `runners_up` in
the YAML to see what each change does.

**Colours.** `python newsletter/extract_palette.py` prints the logo's colour
clusters with their WCAG contrast on white. The light blue and light green
(≈ 2.3:1) are used for decoration only, never as text.

### Upstream sources (daily pipeline)

The newsletter can only select what `pipeline/` collects. Sources relevant to
AI & data for medicines are configured in `pipeline/config.json`:

- `pubmed.search_queries`: the first 7 queries target AI/data for medicines
  regulation and carry `"auto_approve": true`. Always parenthesise `OR` groups
  (`A AND (B OR C)`); `[tiab]` restricts to title/abstract.
- `rss_sources.feeds`: broad medicines feeds (EMA what's new, FDA Drugs, medRxiv /
  bioRxiv pharmacology, Clin Pharmacol Ther, Nat Rev Drug Discov, npj Digit Med)
  use `"require_ai_or_data": true`. Only items containing a word from
  `ai_or_data_gate` (whole-word match) are kept.

## 4. E-mail delivery: app password and GitHub secrets

The repository is **public**: no address, password or key is ever written in the
code or in `config.yaml`. Everything comes from GitHub secrets / environment variables.

### Create an app password

An *app password* is a separate password for one application, which you can
revoke at any time. Never use your main account password.

- **Gmail**: turn on 2-Step Verification (Google Account → Security), then open
  <https://myaccount.google.com/apppasswords>, create one named "IncreaseNET newsletter"
  and copy the 16 characters.
  SMTP: host `smtp.gmail.com`, port `465`.
- **Yahoo Mail**: Account info → Account security → *Generate app password* (2-step
  verification required), name it "IncreaseNET newsletter".
  SMTP: host `smtp.mail.yahoo.com`, port `465`.

### Configure the secrets

GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Example value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` (SSL) or `587` (STARTTLS) |
| `SMTP_USER` | your full mailbox address |
| `SMTP_PASSWORD` | the app password |
| `NEWSLETTER_FROM` | usually the same as `SMTP_USER` (Gmail/Yahoo reject other senders) |
| `NEWSLETTER_TO` | where you receive the newsletter (several addresses: comma-separated) |
| `ANTHROPIC_API_KEY` | already configured for the daily pipeline; reused here |

If the SMTP secrets are missing, the workflows simply skip the e-mail step.

To send from your machine, export the same variables in your shell (do not put
them in a committed file).

### What the e-mail looks like (and why)

So that it survives being forwarded from a private mailbox to Outlook:

- `multipart/alternative`: HTML (600 px table layout, inline CSS, no JavaScript,
  no web fonts) **and** a readable plain-text version;
- the HTML edition also **attached** as `IncreaseNET-AI-Newsletter-YYYY-MM-DD.html`
  (open it, copy it into a new Outlook message, or forward it as is);
- a line at the top pointing to the attached HTML file if the display is broken
  (there is deliberately no online version);
- the logo referenced by an absolute URL (raw file in this repository), with no base64 or CID
  images, which Outlook often blocks or drops when forwarding;
- constant subject: `IncreaseNET AI Community – Newsletter #N (period)`, with `[DRAFT] ` for previews.

**Forwarding from Outlook**: open the received e-mail and use *Forward*. If
the layout breaks, open the attached HTML file in a browser, select all, copy,
and paste it into a new Outlook message, or simply forward the e-mail with the
attachment.

## 5. Tests

```bash
python -m pytest newsletter/tests -q
```

Covered: deduplication, keyword scoring and quota selection, HTML validity and
Outlook constraints, text/Markdown output, message structure and `--dry-run`.
