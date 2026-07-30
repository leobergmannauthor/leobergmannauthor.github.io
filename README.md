# Leo Bergmann Books

Public author website, durable Pinterest-RSS publication ledger, and zero-budget organic publishing pipeline for Leo Bergmann's German recipe books. The repository contains publishable marketing assets and metadata, never credentials or private source files.

## What is automated

The prepared catalog retains all 14 German recipe-book projects with 1,960 recipes. Eleven books are published and eligible for marketing. Finished Pinterest creatives use a 1000 × 1500 px (2:3) template with a book-specific label, recipe hook, truthful benefit line, CTA, and author mark.

- 1,540 recipes currently have a rights-cleared source image and a finished Pin creative.
- Books `013_hp_prep`, `014_hp_snacks`, and `015_hp_women` are not published and therefore remain `unpublished` regardless of asset availability. Their 420 recipes also currently have no source images. They are retained in the catalog but never scheduled.
- Two organic items per local Europe/Berlin day are planned, with at most one item per book on a day where possible.
- GitHub Actions maintains a rolling 30-day queue twice daily, publishes due pages and RSS entries, runs all tests, and commits durable state.
- The scheduler is idempotent, enforces a 180-day exact-title cooldown, stops safely at queue exhaustion, and has a hard 0-EUR paid-channel lock.

After the prepared assets are pushed, the notebook may be switched off. GitHub Actions releases content and Pinterest's official RSS importer polls https://leobergmannauthor.github.io/feed.xml. A feed entry is not counted as a confirmed Pin until a real public Pinterest /pin/ URL is recorded.

## Local commands

Run from the repository root:

~~~powershell
python scripts/prepare_german_pin_catalog.py
python scripts/catalog_scheduler.py
python publication_history.py sync
python build.py
python -m unittest discover -s tests -v
python -m http.server 8080 --directory docs
~~~

`prepare_german_pin_catalog.py` reads the private BookGenPy library, is BOM-tolerant and resumable, reuses unchanged creatives, filters risky health claims, and writes only publication-safe data. Use it again only after recipes, source images, or the template change. Normal daily operation happens in GitHub and does not require this local generator.

On Windows, `Pinterest-Autopilot.cmd` performs the same safe all-book preparation, queue refill, validation, commit, and push workflow, then opens the local dashboard. It is a maintenance launcher, not a daily requirement.

## Durable files

- `data/books.json`: public book titles, labels, and Amazon destinations.
- `data/pin_catalog.json`: all 1,960 stable content IDs, prepared copy, checksums, asset state, and schedule state.
- `content/recipes.json`: the rolling publication queue and already published RSS items.
- `data/scheduler_state.json`: last refill, queue health, remaining prepared items, missing assets, and zero cost.
- `data/publication_history.json`: separate RSS and independently verified Pinterest status for every queued item.
- `docs/assets/pins/`: finished one-copy Pin creatives. Unlike other files in `docs`, these are prepared source artifacts preserved by `build.py`.
- `docs/assets/books/`: authentic public book covers used by the conversion-focused recipe landing pages. Prefer visually verified German local exports; a verified official Amazon CDN cover may be configured when no language-safe local export exists.

The catalog preserves each `catalog_id` across sessions. Re-running the generator or scheduler never creates a second item for the same book/recipe pair.

## Amazon destinations

All eleven published books use verified direct Amazon ASIN links. Amazon search fallbacks are forbidden: a published book without a verified ASIN fails the catalog build. Books `013_hp_prep`, `014_hp_snacks`, and `015_hp_women` have no destination and cannot enter the publication queue until their listings are live, their ASINs are verified, and their `published` flags are explicitly enabled.

Every recipe landing page is a genuine content page and a book-specific sales bridge: it shows the matching authentic cover, recipe count, truthful benefits, and three clear Amazon calls to action. Automatic redirects are forbidden. Amazon links open the verified direct listing with `nofollow sponsored noopener`.

## Verification

The test suite validates catalog completeness, public-data safety, 2:3 image dimensions, title and description limits, daily cadence, idempotency, zero-budget failure behavior, RSS targets, ledger consistency, and a three-year simulation through clean queue exhaustion.

After independently verifying an imported public Pin, record it with:

~~~powershell
python publication_history.py confirm-pinterest <content-id> <public-pin-url>
~~~

Never confirm a Pin based only on an expected import window.

## Deployment

GitHub Pages serves `docs/` from `main`. The active repository and public endpoints are:

- Repository: https://github.com/leobergmannauthor/leobergmannauthor.github.io
- Website: https://leobergmannauthor.github.io/
- RSS: https://leobergmannauthor.github.io/feed.xml

The former `leanovich.github.io/leo-bergmann-books/` site is a transition fallback for old Pin destinations only. Do not use it for new publications.

## Security and policy

- No passwords, tokens, cookies, email addresses, browser profiles, or customer data belong here.
- Paid actions remain disabled and the daily budget is 0 EUR.
- No invented ratings, testimonials, scarcity, medical outcomes, or performance claims.
- No unapproved browser automation; Pinterest publication uses the claimed-site RSS feature.
- Amazon links use `nofollow sponsored` on the rendered pages.
