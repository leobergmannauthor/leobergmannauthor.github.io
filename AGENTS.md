# AGENTS.md

## Purpose

This repository publishes Leo Bergmann's public author website and a Pinterest-compatible RSS feed. Its job is to turn approved book material into useful reader-facing teasers that lead to the corresponding Amazon book page. The current campaign focuses on the Airfryer cookbook, but the structure may be extended to other books and social channels.

These instructions apply to the entire repository.

## Sources of truth

Book production sources are outside this public repository:

- Book library: `C:\Daten\src\python\BookGenPy\library`
- KDP product projects: `C:\Daten\src\python\BookGenPy\products\kdp`
- Local marketing control project and dashboard: `C:\Daten\src\python\marketing_codex` and `http://127.0.0.1:8765/`
- Native/manual Pinterest publication log: `C:\Daten\src\python\marketing_codex\data\run_log.json`

Read those sources when a task requires accurate book metadata or content. Do not edit book production files unless the task explicitly includes that work. Copy only material that is suitable and licensed for public use.

## Repository map

- `site_config.json`: public site metadata, Amazon destination, RSS metadata, Pinterest board, and domain verification.
- `content/recipes.json`: scheduled public items and their metadata.
- `data/publication_history.json`: durable RSS-to-Pinterest publication ledger.
- `publication_history.py`: idempotent ledger synchronization and verified Pin confirmation command.
- `assets/`: publishable cover and social images.
- `scripts/render_pin_creatives.cjs`: deterministic renderer for Pinterest creatives with exact German typography.
- `build.py`: deterministic static-site and RSS generator.
- `styles.css`: source stylesheet.
- `docs/`: generated GitHub Pages output; never edit it by hand.
- `tests/`: public-output, history, RSS, link, and Pinterest verification checks.
- `.github/workflows/publish.yml`: scheduled build, ledger update, verification, and publication workflow.

## Public-content boundaries

- Write for readers. Never expose budgets, campaign notes, scheduler state, account setup details, credentials, private email addresses, tokens, browser data, customer data, or private file inventories in the generated website or RSS feed.
- The source-controlled ledger may contain public URLs, content IDs, public titles, and non-secret publication timestamps only.
- Never commit `credentials.vault.json`, `.env`, cookies, browser profiles, exported credentials, or secrets.
- Keep credentials and account recovery data outside this public repository. GitHub Actions secrets are appropriate only when an integration genuinely needs them.
- Do not invent testimonials, ratings, health claims, book contents, discounts, availability, publication results, or performance results.
- Avoid spam, repetitive near-duplicates, unsolicited messages, and engagement manipulation.
- Paid actions require explicit current authorization. A public page must never describe internal spending limits.
- Preserve the Pinterest verification meta tag unless ownership intentionally changes.
- Keep Amazon links sponsored/nofollow in rendered HTML. Update the destination centrally in `site_config.json`, not in generated pages.
- Each RSS item must use a canonical URL on the claimed website and an absolute public image URL.

## Durable publication history

Always read `data/publication_history.json` before creating, rescheduling, or confirming Pinterest content. It prevents duplicate work and distinguishes three facts that must never be conflated:

1. `scheduled_at` says when the item is intended to become eligible.
2. `rss.status = published_to_feed` says the item is present in the public RSS feed.
3. `pinterest.status = confirmed` says an actual public Pinterest Pin was independently verified and its `pin_url` recorded.

`awaiting_import_confirmation` is not a successful Pin publication. The synchronizer changes it to `confirmation_overdue` when the 24-hour window has elapsed without proof. Pinterest's expected import window is not proof. Never change an item to `confirmed` without a working public `/pin/` URL or an authoritative Pinterest API result.

Run `python publication_history.py sync` after changing `content/recipes.json`. The command is idempotent, creates missing ledger entries, advances due RSS entries, and preserves verified Pin data. Once a public imported Pin is verified, run:

```powershell
python publication_history.py confirm-pinterest <content-id> <public-pin-url>
```

The RSS ledger covers only feed-driven items. Native Pins created or scheduled directly in Pinterest are tracked separately in the local marketing `data/run_log.json`; check both sources before publishing similar content.

## Creating a recipe item and Pinterest Pin

Pinterest imports the RSS title, description, destination page, and `media:content` image. To add an item:

1. Inspect the relevant book source and choose a truthful teaser. Do not publish a full paid recipe or substantial book excerpt without explicit approval.
2. Search both the RSS ledger and the native Pinterest run log for duplicates or materially similar posts.
3. Create or select a publishable, rights-cleared source image and place it under `assets/recipes/`. For Pinterest-facing items, render a distinct branded creative with `scripts/render_pin_creatives.cjs`: preserve the unmodified source JPEG, create a sibling `<content-id>-pin.jpg`, and reference that designed file from `content/recipes.json`. The creative should keep the food prominent while adding a concise hook, a truthful benefit line, an author mark, and a clear CTA. Check every German line visually; do not add invented claims, discounts, ratings, or urgency.
4. Append an object to `content/recipes.json` with a unique, stable `id`, reader-facing `title` and `description`, optional `prep`, `cook`, `servings`, and `difficulty`, a repository-relative `image`, and an ISO-8601 UTC `publish_at`.
5. Use natural German, useful search terms, and genuinely distinct copy. The description must make sense on both the page and Pinterest.
6. Schedule only within the requested campaign window. Confirm UTC conversion when the requested time is local Europe/Berlin time.
7. Synchronize the ledger, build, and test. Confirm that the generated page, image, canonical URL, feed entry, ledger entry, and Amazon destination all work.

For a native Pin or another social network, use the generated public page as the destination, adapt the image dimensions and copy to that platform, and keep account operations outside this repository. Prefer official APIs or platform-supported schedulers. Do not automate CAPTCHA, phone, email, or identity verification.

## Build and verification

Run from the repository root:

```powershell
python publication_history.py sync
python build.py
python -m unittest discover -s tests -v
python -m http.server 8080 --directory docs
```

For a reproducible preview, use `python build.py --now 2026-07-21T18:00:00Z` and `python publication_history.py sync --now 2026-07-21T18:00:00Z`. Before publishing:

- inspect `git status` and the complete diff;
- run the full test suite;
- visually inspect the home page, privacy page, one item page, and a narrow viewport;
- confirm public HTML and RSS contain no operational or secret markers;
- verify RSS XML, target pages, images, canonical links, Pinterest verification, and the Amazon URL;
- confirm every content ID occurs exactly once in the ledger;
- ensure RSS-published ledger entries match the generated feed;
- keep generated `docs/` and `data/publication_history.json` in sync with their sources.

## Deployment

GitHub Pages serves `docs/` from `main`. The workflow checks due content at 03:15 and 14:15 UTC, synchronizes the durable history, rebuilds the site, runs tests, and commits changed history and generated output. RSS build dates are deterministic, so the feed remains unchanged after the last scheduled item.

Because the workflow can commit to `main`, run `git pull --ff-only` before new publication work and again if a push is rejected. After pushing, verify both the workflow and the public URLs:

- Website: https://leobergmannauthor.github.io/
- RSS: https://leobergmannauthor.github.io/feed.xml
- Repository: https://github.com/leobergmannauthor/leobergmannauthor.github.io

## Account and domain migration

The active GitHub identity, repository, website, and Pinterest RSS source are all leobergmannauthor / https://leobergmannauthor.github.io/. This repository was created on 21 July 2026 as a clean copy without the former personal account's Git history. Pinterest has verified the new domain, the public profile links to it, and the existing feed configuration for Schnelle & einfache Rezepte was edited in place to use https://leobergmannauthor.github.io/feed.xml.

The former https://leanovich.github.io/leo-bergmann-books/ deployment is intentionally kept online only as a transition fallback for existing Pins whose destination URLs cannot be changed retroactively. Never use the legacy URL for new pages, feed items, Pins, profile links, or documentation. Do not delete or disable the fallback until its inbound Pin destinations have been inventoried or redirected and the user explicitly authorizes retirement.

## Current campaign context

The 22–29 July 2026 vacation campaign is complete. On 30 July 2026 the public profile contained 28 public Pins: 16 recipe Pins imported from the active RSS feed, the earlier cookbook RSS Pin, and 11 native Pins. The 16 recipe imports are confirmed in the ledger; the earlier cookbook Pin is not confirmed against the active ledger because it still targets the legacy site.

A follow-up series of 12 distinct Airfryer recipes is scheduled from 30 July through 10 August 2026 at one item per day. It uses source IDs recipe_003, recipe_012, recipe_017, recipe_024, recipe_025, recipe_040, recipe_059, recipe_064, recipe_082, recipe_088, recipe_092, and recipe_117. Keep this cadence and content mix unless a later request explicitly changes it; do not publish duplicate variants of the same recipes while this series is active.

The follow-up series uses branded `-pin.jpg` creatives rather than unchanged source photos. The current template places a category label, large recipe hook, benefit line, CTA, and author mark over the photo. Run the renderer again after changing creative copy, then synchronize the ledger, rebuild, test, and visually inspect representative light and dark food images before pushing.
