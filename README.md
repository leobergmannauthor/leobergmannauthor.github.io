# Leo Bergmann Books

Public static author site with a Pinterest-compatible RSS feed and a durable, non-secret publication ledger. The repository contains publishable marketing content and publication metadata, but no credentials.

## Local verification

1. Run `python publication_history.py sync`.
2. Run `python build.py`.
3. Run `python -m unittest discover -s tests -v`.
4. Serve `docs` with `python -m http.server 8080 --directory docs`.
5. Open `http://127.0.0.1:8080/`.

## GitHub Pages

The intended repository is `leobergmannauthor/leobergmannauthor.github.io`. Configure GitHub Pages to publish from the `docs` directory on the `main` branch.

The workflow checks newly due content at 03:15 UTC and 14:15 UTC. It updates the publication ledger, adds only content whose `publish_at` timestamp has been reached, runs the tests, and commits changed history and generated pages. Pinterest can then import the feed from:

`https://leobergmannauthor.github.io/feed.xml`

Before connecting the feed, claim the website in Pinterest. Every feed item links to the claimed website and the website links to the Amazon book.

## Identity migration

On 21 July 2026 this site was recreated as a clean repository under the dedicated author account leobergmannauthor; no Git history from the previous personal account was imported. Pinterest ownership of leobergmannauthor.github.io was verified, the public profile website was changed to the new domain, and the existing RSS configuration for Schnelle & einfache Rezepte was updated in place to https://leobergmannauthor.github.io/feed.xml.

The former leanovich.github.io/leo-bergmann-books/ site is a transition fallback only, so existing Pins that still target old page URLs do not break. It is not the source for new RSS publications. Do not remove the fallback until all old destination URLs have been inventoried or redirected.

## Durable publication history

The source-controlled ledger is `data/publication_history.json`. It contains one entry for every item in `content/recipes.json`, including its schedule, public page and image, RSS state, and separately verified Pinterest state.

The states have deliberately different meanings:

- `rss.status = scheduled`: the item is not yet in the public feed.
- `rss.status = published_to_feed`: the item is present in RSS. This does not prove that Pinterest created a Pin.
- `pinterest.status = awaiting_import_confirmation`: Pinterest may import the item, but no public Pin URL has been verified.
- `pinterest.status = confirmation_overdue`: 24 hours have elapsed without confirmation; the Pin must be checked.
- `pinterest.status = confirmed`: a public Pinterest `/pin/` URL and confirmation timestamp are recorded.

The scheduled GitHub workflow advances RSS states automatically and preserves existing confirmations. After independently verifying an imported Pin, record it with:

```powershell
python publication_history.py confirm-pinterest <content-id> <public-pin-url>
```

Never mark an item as confirmed based only on the usual Pinterest import window.

## Security

- No account passwords, tokens, customer data, or private catalog files belong in this repository.
- The ledger may contain public URLs and non-secret publication timestamps only.
- The site uses no cookies and no external analytics.
- Internal campaign state, budgets, credentials, and operational notes must never be rendered on the public website or RSS feed.
