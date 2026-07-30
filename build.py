from __future__ import annotations

import argparse
import html
import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
CONTENT_FILE = ROOT / "content" / "recipes.json"
CONFIG_FILE = ROOT / "site_config.json"
BOOKS_FILE = ROOT / "data" / "books.json"
ASSETS = ROOT / "assets"


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def page_shell(config: dict, title: str, description: str, canonical: str, body: str, image: str | None = None, structured_data: dict | None = None) -> str:
    site_name = esc(config["site_name"])
    image_meta = f'  <meta property="og:image" content="{esc(image)}">' if image else ""
    json_ld = ""
    if structured_data:
        json_ld = '  <script type="application/ld+json">' + json.dumps(structured_data, ensure_ascii=False) + "</script>"
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="p:domain_verify" content="{esc(config['pinterest_domain_verify'])}">
  <title>{esc(title)} | {site_name}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
{image_meta}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" type="application/rss+xml" title="{esc(config['rss_title'])}" href="{esc(config['base_url'] + '/feed.xml')}">
  <link rel="stylesheet" href="{esc(config['base_url'] + '/styles.css')}">
{json_ld}
</head>
<body>
  <header class="site-header"><a class="brand" href="{esc(config['base_url'] + '/')}">{site_name}</a>
    <nav aria-label="Hauptnavigation"><a href="{esc(config['base_url'] + '/')}">Rezepte</a><a href="{esc(config['base_url'] + '/datenschutz.html')}">Datenschutz</a><a href="{esc(config['base_url'] + '/feed.xml')}">RSS</a></nav>
  </header>
  <main>{body}</main>
  <footer><p>&copy; {datetime.now().year} {esc(config['author'])}</p></footer>
</body>
</html>
"""


def item_urls(config: dict, item: dict) -> tuple[str, str]:
    canonical = f"{config['base_url']}/rezepte/{item['id']}.html"
    image = f"{config['base_url']}/{item['image']}"
    return canonical, image


def book_for(item: dict, books: dict[str, dict], config: dict) -> dict:
    return books.get(item.get("book_id", "002_airfryer"), {
        "id": "002_airfryer",
        "title": config.get("book_title", "Leo Bergmann Kochbuch"),
        "label": "REZEPTIDEE",
        "promise": "Einfach • abwechslungsreich • alltagstauglich",
        "recipe_count": 140,
        "cover": "assets/book-cover.jpg",
        "amazon_url": config["amazon_url"],
    })


def render_item(config: dict, books: dict[str, dict], item: dict) -> str:
    canonical, image = item_urls(config, item)
    book = book_for(item, books, config)
    target = item.get("amazon_url") or book["amazon_url"]
    cover_source = book.get("cover") or "assets/book-cover.jpg"
    cover = cover_source if str(cover_source).startswith("https://") else f"{config['base_url']}/{cover_source}"
    recipe_count = int(book.get("recipe_count", 140))
    promise_parts = [part.strip() for part in str(book.get("promise", "")).split("•") if part.strip()]
    if not promise_parts:
        promise_parts = ["Abwechslungsreich", "Alltagstauglich", "Verständlich"]
    facts = []
    for label, key in (("Vorbereitung", "prep"), ("Zubereitung", "cook"), ("Portionen", "servings"), ("Schwierigkeit", "difficulty")):
        if item.get(key):
            facts.append(f"<li><span>{esc(label)}</span><strong>{esc(item[key])}</strong></li>")
    facts_html = '<ul class="facts">' + "".join(facts) + "</ul>" if facts else ""
    compact_benefits = "".join(f"<li>{esc(part)}</li>" for part in promise_parts[:3])
    promise = " · ".join(promise_parts[:3])
    amazon_label = f"{book['title']} bei Amazon ansehen"
    amazon_link = (
        f'<a class="cta cta-primary" data-amazon-cta href="{esc(target)}" '
        f'target="_blank" rel="nofollow sponsored noopener" aria-label="{esc(amazon_label)}">'
        f'<strong>Buch bei Amazon ansehen</strong><span>Aktueller Preis und verfügbare Formate auf Amazon.de</span></a>'
    )
    body = f"""
<article class="sales-page">
  <section class="recipe-hero">
    <div class="recipe-copy">
      <p class="eyebrow">{esc(book.get('label', 'REZEPTIDEE'))}</p>
      <h1>{esc(item['title'])}</h1>
      <p class="lead">{esc(item['description'])}</p>
{facts_html}
      <div class="conversion-card" aria-label="Passendes Kochbuch">
        <img class="mini-cover" src="{esc(cover)}" alt="Buchcover: {esc(book['title'])}" width="160" height="226" decoding="async">
        <div class="conversion-copy">
          <p class="microcopy">DAS PASSENDE KOCHBUCH</p>
          <h2>{esc(book['title'])}</h2>
          <p>Diese Rezeptidee ist ein Vorgeschmack auf <strong>{recipe_count} Rezepte</strong> im Buch von Leo Bergmann.</p>
          <ul class="compact-benefits">{compact_benefits}</ul>
          {amazon_link}
        </div>
      </div>
    </div>
    <figure class="recipe-visual"><img src="{esc(image)}" alt="{esc(item['title'])}" width="1000" height="1500" fetchpriority="high" decoding="async"><figcaption>{esc(item['title'])}</figcaption></figure>
  </section>

  <section class="book-offer" id="buch">
    <div class="cover-stage"><img class="book-cover" src="{esc(cover)}" alt="Buchcover: {esc(book['title'])}" width="484" height="685" loading="lazy" decoding="async"></div>
    <div class="offer-copy">
      <p class="eyebrow eyebrow-light">MEHR AUS DIESER REZEPTWELT</p>
      <h2>Aus einer Rezeptidee werden {recipe_count}.</h2>
      <p class="offer-lead">Wenn dir <strong>{esc(item['title'])}</strong> gefällt, findest du im passenden Kochbuch viele weitere Ideen zum Auswählen, Nachkochen und Genießen.</p>
      <div class="benefit-grid" aria-label="Vorteile des Buches">
        <div><strong>{recipe_count}</strong><span>Rezeptideen in einem Buch</span></div>
        <div><strong>Passend</strong><span>{esc(promise)}</span></div>
        <div><strong>Direkt</strong><span>Zur Produktseite auf Amazon.de</span></div>
      </div>
      {amazon_link}
      <p class="amazon-note">Der Link öffnet die Produktseite bei Amazon.de. Dort siehst du den aktuellen Preis und die verfügbaren Buchformate.</p>
    </div>
  </section>

  <section class="closing-cta">
    <p class="eyebrow">BEREIT FÜR DIE NÄCHSTE REZEPTIDEE?</p>
    <h2>{esc(book['title'])}</h2>
    <p>{recipe_count} Rezeptideen gesammelt an einem Ort – {esc(promise)}.</p>
    {amazon_link}
  </section>

  <aside class="mobile-buy-bar" aria-label="Buch bei Amazon ansehen">
    <div><span>{recipe_count} Rezepte</span><strong>{esc(book.get('label', 'KOCHBUCH'))}</strong></div>
    <a href="{esc(target)}" target="_blank" rel="nofollow sponsored noopener">Bei Amazon ansehen</a>
  </aside>
</article>
"""
    structured = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": item["title"],
        "description": item["description"],
        "image": image,
        "author": {"@type": "Person", "name": config["author"]},
        "datePublished": item["publish_at"],
        "mainEntityOfPage": canonical,
        "about": {"@type": "Book", "name": book["title"], "url": target},
    }
    return page_shell(config, item["title"], item["description"], canonical, body, image, structured)


def render_index(config: dict, books: dict[str, dict], items: list[dict]) -> str:
    cards = []
    for item in items:
        canonical, image = item_urls(config, item)
        book = book_for(item, books, config)
        cards.append(f"""<article class="card"><a href="{esc(canonical)}"><img src="{esc(image)}" alt="{esc(item['title'])}" width="700" height="1050"></a><div><p class="eyebrow">{esc(book.get('label', 'REZEPTIDEE'))}</p><h2><a href="{esc(canonical)}">{esc(item['title'])}</a></h2><p>{esc(item['description'])}</p></div></article>""")
    cards_html = "".join(cards) if cards else "<p>Die erste Rezeptidee erscheint in Kürze.</p>"
    body = f"""<section class="hero"><div><p class="eyebrow">REZEPTIDEEN VON LEO BERGMANN</p><h1>Einfach kochen. Besser genießen.</h1><p>{esc(config['description'])}</p></div></section><section class="section"><h2>Neue Rezeptideen</h2><div class="cards">{cards_html}</div></section>"""
    return page_shell(config, config["site_name"], config["description"], config["base_url"] + "/", body)


def render_privacy(config: dict) -> str:
    body = """<article class="prose"><p class="eyebrow">Datenschutz</p><h1>Datenschutzhinweise</h1><p>Diese statische Website setzt keine eigenen Cookies ein, verwendet keine Formulare und bindet keine externen Analyse- oder Werbedienste ein. Einzelne Buchcover können technisch von einem Bildserver von Amazon geladen werden; dabei kann Amazon Verbindungsdaten wie die IP-Adresse verarbeiten.</p><p>Beim Aufruf verarbeitet der Hosting-Anbieter technisch notwendige Serverdaten. Beim Klick auf einen Amazon-Link gelten die Datenschutzbestimmungen von Amazon.</p><p>Die Links führen zu den jeweiligen Buchangeboten bei Amazon. Auf dieser Website werden keine Zahlungs- oder Kundendaten verarbeitet.</p></article>"""
    return page_shell(config, "Datenschutz", "Datenschutzhinweise der Website", config["base_url"] + "/datenschutz.html", body)


def render_feed(config: dict, items: list[dict]) -> bytes:
    ET.register_namespace("media", "http://search.yahoo.com/mrss/")
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = config["rss_title"]
    ET.SubElement(channel, "link").text = config["base_url"] + "/"
    ET.SubElement(channel, "description").text = config["rss_description"]
    ET.SubElement(channel, "language").text = "de-DE"
    build_date = max((parse_time(item["publish_at"]) for item in items), default=datetime(1970, 1, 1, tzinfo=timezone.utc))
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(build_date)
    for item in sorted(items, key=lambda value: parse_time(value["publish_at"]), reverse=True):
        canonical, image = item_urls(config, item)
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"]
        ET.SubElement(node, "link").text = canonical
        ET.SubElement(node, "guid", {"isPermaLink": "true"}).text = canonical
        ET.SubElement(node, "description").text = item["description"]
        ET.SubElement(node, "pubDate").text = format_datetime(parse_time(item["publish_at"]))
        ET.SubElement(node, "{http://search.yahoo.com/mrss/}content", {"url": image, "medium": "image"})
        ET.SubElement(node, "{http://search.yahoo.com/mrss/}title").text = item["title"]
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def build(now: datetime, base_url_override: str | None = None) -> None:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    if base_url_override:
        config["base_url"] = base_url_override.rstrip("/")
    books_payload = json.loads(BOOKS_FILE.read_text(encoding="utf-8")) if BOOKS_FILE.exists() else {"books": []}
    books = {book["id"]: book for book in books_payload.get("books", [])}
    items = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    live = [item for item in items if parse_time(item["publish_at"]) <= now]

    DOCS.mkdir(parents=True, exist_ok=True)
    recipe_pages = DOCS / "rezepte"
    if recipe_pages.exists():
        shutil.rmtree(recipe_pages)
    shutil.copytree(ASSETS, DOCS / "assets", dirs_exist_ok=True)

    write(DOCS / ".nojekyll", "")
    write(DOCS / "styles.css", (ROOT / "styles.css").read_text(encoding="utf-8"))
    ordered = sorted(live, key=lambda value: parse_time(value["publish_at"]), reverse=True)
    write(DOCS / "index.html", render_index(config, books, ordered))
    write(DOCS / "datenschutz.html", render_privacy(config))
    for item in live:
        write(DOCS / "rezepte" / f"{item['id']}.html", render_item(config, books, item))
    (DOCS / "feed.xml").write_bytes(render_feed(config, live))
    sitemap_urls = [config["base_url"] + "/", config["base_url"] + "/datenschutz.html"]
    sitemap_urls.extend(item_urls(config, item)[0] for item in live)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{esc(url)}</loc></url>\n" for url in sitemap_urls)
    sitemap += "</urlset>\n"
    write(DOCS / "sitemap.xml", sitemap)
    write(DOCS / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {config['base_url']}/sitemap.xml\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", help="UTC ISO timestamp used for a reproducible build")
    parser.add_argument("--base-url", help="Override the public URL for local preview")
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    build(now, args.base_url)


if __name__ == "__main__":
    main()
