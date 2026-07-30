# AGENTS.md

## Purpose and scope

This repository is the public, zero-budget organic marketing pipeline for Leo Bergmann's German recipe books. It publishes the author website, a Pinterest-compatible RSS feed, purpose-built Pin creatives, a durable publication queue, and a separate proof ledger for actual Pinterest imports. These instructions apply to the entire repository.

The system retains 14 German recipe-book projects and 1,960 recipes. Eleven are currently published and eligible for marketing. It must remain idempotent, recoverable after interruption, safe when assets are missing or a book is unpublished, and independent of a running notebook after prepared assets are pushed.

## Private sources of truth

Book production sources live outside this public repository:

- Book library: `C:\Daten\src\python\BookGenPy\library`
- KDP product projects: `C:\Daten\src\python\BookGenPy\products\kdp`
- Local marketing control project/dashboard: `C:\Daten\src\python\marketing_codex` and `http://127.0.0.1:8765/`
- Native/manual Pinterest log: `C:\Daten\src\python\marketing_codex\data\run_log.json`

Read these sources for accurate content but do not edit production files unless explicitly requested. Never copy private paths, credentials, browser state, full paid recipes, or internal campaign data into public output.

## Catalog coverage

The all-book generator intentionally includes:

- `001_protein`, `002_airfryer`, `003_vegetarisch`, `004_meal_prep`
- `005_low_carb`, `006_family`, `007_men`, `008_liver`
- `009_anti_entzuendung`, `011_hp_basics`, `012_hp_veggie`
- `013_hp_prep`, `014_hp_snacks`, `015_hp_women`

Each contributes 140 German recipes. At the July 2026 baseline, 1,540 source images are available. Books 013-015 are not published and their 420 recipes have no recipe image assets. Their publication state must remain `unpublished` even if images later appear. Enable them only after the Amazon listing is live and its direct ASIN has been verified. Never substitute an unrelated image merely to increase volume.

## Repository map

- `data/books.json`: public book titles, labels, promises, Amazon destinations, and target type.
- `data/pin_catalog.json`: durable 1,960-item catalog, checksums, prepared copy, asset state, and publication state.
- `data/automation_policy.json`: timezone, cadence, cooldown, horizon, and strict 0-EUR lock.
- `data/scheduler_state.json`: last queue refill and current health/exhaustion state.
- `content/recipes.json`: scheduled and already published site/RSS items.
- `data/publication_history.json`: RSS state and independently confirmed Pinterest state.
- `scripts/prepare_german_pin_catalog.py`: private-source importer and bulk 2:3 creative renderer.
- `scripts/catalog_scheduler.py`: cloud-safe stdlib queue filler; it never reads private source paths.
- `scripts/pinterest_autopilot.py`: shared renderer plus legacy Airfryer helpers.
- `Pinterest-Autopilot.cmd` and `scripts/run-pinterest-autopilot.ps1`: local maintenance launcher.
- `build.py`: deterministic multi-book website, RSS, sitemap, and page generator.
- `docs/assets/pins/`: prepared final creatives stored only once to keep the Pages repository below size limits.
- `docs/assets/books/`: authentic public cover images for published books; preserve them during builds. Prefer visually verified German local exports. A verified official Amazon CDN URL is acceptable only when no language-safe local export exists; never trust a generic `output/covers` file without visual inspection.
- `.github/workflows/publish.yml`: twice-daily queue refill, ledger sync, build, test, and commit.

Most of `docs/` is generated. The exception is `docs/assets/pins/`: it is prepared source material and `build.py` must preserve it. Do not restore a blanket deletion of `docs/`.

## Creating and updating all-book creatives

Run locally after recipe metadata, source images, templates, or book destinations change:

~~~powershell
python scripts/prepare_german_pin_catalog.py
python scripts/catalog_scheduler.py
python publication_history.py sync
python build.py
python -m unittest discover -s tests -v
~~~

The generator must remain:

- incremental via `source_fingerprint` and `creative_version`;
- resumable after interruption and tolerant of UTF-8 BOM source files;
- strict about 140 recipes per included book;
- safe when source images are absent;
- limited to publication-safe fields with no local source paths;
- visually standardized at 1000 × 1500 JPEG;
- conservative about medical/health promises and other risky claims.

Every new item uses the stable key `<book-id>:<recipe-id>`. Never recycle or rename an existing `catalog_id`. Inspect representative light, dark, short-title, and long-title images after a renderer change.

## Scheduling behavior

The cloud scheduler reads only committed prepared assets. It currently targets two organic items per Europe/Berlin day, keeps a rolling 30-day horizon, avoids two items from the same book on one day where possible, and suppresses exact-title reuse within 180 days. Five Pins/day is the hard safety ceiling; changing cadence requires an explicit marketing decision and updated tests.

Scheduler requirements:

- a second run with unchanged inputs is a no-op;
- no content ID or catalog ID may appear twice;
- missing images are never scheduled;
- a dirty or exhausted queue is recorded, not treated as permission to fabricate content;
- exhaustion is a stable no-op, not a crash loop;
- daily budget must equal 0 and paid channels must be false or the run fails closed;
- scheduled times are stored in UTC after Europe/Berlin conversion.

## Publication facts and proof

Never conflate these states:

1. `scheduled_at`: intended eligibility time.
2. `rss.status = published_to_feed`: the item is actually in the public RSS feed.
3. `pinterest.status = confirmed`: a public Pinterest `/pin/` URL was independently verified.

`awaiting_import_confirmation` and `confirmation_overdue` are not successful Pinterest publications. Confirm only with:

~~~powershell
python publication_history.py confirm-pinterest <content-id> <public-pin-url>
~~~

Read both `data/publication_history.json` and the external native `run_log.json` before manually creating similar content.

## Public-content and platform boundaries

- Write for readers; never render budgets, queue notes, account setup details, private emails, credentials, or source inventories.
- Do not invent ratings, testimonials, urgency, discounts, results, medical outcomes, or sales performance.
- Remove claims such as curing, detoxifying, fighting disease/inflammation, or guaranteeing weight loss. A factual book title may remain, but teaser copy must not promise outcomes.
- Avoid repetitive near-duplicates, irrelevant destinations, engagement manipulation, and unapproved browser automation.
- Pinterest publication uses the claimed-site RSS feature; do not automate CAPTCHA, identity, phone, or email verification.
- Each RSS item requires a canonical URL on `https://leobergmannauthor.github.io/` and an absolute image URL.
- Keep Amazon links `nofollow sponsored`. Never invent ASINs and never use search-result fallbacks. Every published book must have a verified direct ASIN or the catalog build fails closed. Books 013-015 stay unpublished and unscheduled until their listings and direct ASINs are verified.
- Recipe landing pages must remain genuine, useful content pages with a matching cover, truthful book-specific benefits, and prominent direct Amazon CTAs. Never replace them with automatic redirects, fake urgency, fabricated reviews, or hidden commercial behavior.
- Paid actions require explicit current authorization. The current policy is strictly 0 EUR.

## Build and verification

Before committing, always run:

~~~powershell
python publication_history.py sync
python build.py
python -m unittest discover -s tests -v
~~~

The tests must cover catalog count, 140 items/book, public-data safety, image dimensions, title/description limits, idempotency, daily caps, zero-budget failure, ledger/feed equality, URLs, files, and at least a three-year simulated run through queue exhaustion.

Also inspect `git status`, the complete diff, repository size, representative creatives, home page, one recipe page, RSS, sitemap, canonical targets, Pinterest verification tag, and Amazon destinations. Keep `content/recipes.json`, `data/pin_catalog.json`, `data/publication_history.json`, and generated pages synchronized.

## Deployment and recovery

GitHub Pages serves `docs/` from `main`. The workflow runs at 03:15 and 14:15 UTC, refills the queue, synchronizes history, builds, tests, and commits state. A workflow commit may trigger one extra idempotent run; it must produce no second schedule.

After a local push, the notebook can be off. If a run is interrupted, rerun the same command: valid creatives are reused. If GitHub Actions is unavailable, the queue already contains roughly 30 days of future items. If the prepared queue becomes exhausted, the workflow remains green and records `queue_status = exhausted`; replenish only with valid new assets.

Active endpoints:

- Website: https://leobergmannauthor.github.io/
- RSS: https://leobergmannauthor.github.io/feed.xml
- Repository: https://github.com/leobergmannauthor/leobergmannauthor.github.io

The old `leanovich.github.io/leo-bergmann-books/` deployment is only a fallback for existing old Pin URLs. Never use it for new content.
