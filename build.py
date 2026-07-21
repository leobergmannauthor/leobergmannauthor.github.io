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
  <meta name="p:domain_verify" content="{esc(config["pinterest_domain_verify"])}">
  <title>{esc(title)} | {site_name}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(canonical)}">
{image_meta}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" type="application/rss+xml" title="{esc(config["rss_title"])}" href="{esc(config["base_url"] + "/feed.xml")}">
  <link rel="stylesheet" href="{esc(config["base_url"] + "/styles.css")}">
{json_ld}
</head>
<body>
  <header class="site-header">
    <a class="brand" href="{esc(config["base_url"] + "/")}">{site_name}</a>
    <nav aria-label="Hauptnavigation">
      <a href="{esc(config["base_url"] + "/")}">Rezepte</a>
      <a href="{esc(config["base_url"] + "/datenschutz.html")}">Datenschutz</a>
      <a href="{esc(config["base_url"] + "/feed.xml")}">RSS</a>
    </nav>
  </header>
  <main>{body}</main>
  <footer>
    <p>&copy; {datetime.now().year} {esc(config["author"])}</p>
  </footer>
</body>
</html>
"""


def item_urls(config: dict, item: dict) -> tuple[str, str]:
    canonical = f'{config["base_url"]}/rezepte/{item["id"]}.html'
    image = f'{config["base_url"]}/{item["image"]}'
    return canonical, image


def render_item(config: dict, item: dict) -> str:
    canonical, image = item_urls(config, item)
    facts = []
    for label, key in (("Vorbereitung", "prep"), ("Airfryer", "cook"), ("Portionen", "servings"), ("Schwierigkeit", "difficulty")):
        if item.get(key):
            facts.append(f"<li><span>{esc(label)}</span><strong>{esc(item[key])}</strong></li>")
    facts_html = "    <ul class=\"facts\">" + "".join(facts) + "</ul>" if facts else ""
    body = f"""
<article class="recipe">
  <div class="recipe-copy">
    <h1>{esc(item["title"])}</h1>
    <p class="lead">{esc(item["description"])}</p>
{facts_html}
    <p class="teaser-note">Dies ist ein Rezept-Teaser. Die vollst&auml;ndige Zubereitung und viele weitere Ideen findest du im Buch.</p>
    <a class="cta" href="{esc(config["amazon_url"])}" rel="nofollow sponsored">Buch bei Amazon ansehen</a>
  </div>
  <figure><img src="{esc(image)}" alt="{esc(item["title"])}" width="1000" height="1000"><figcaption>{esc(item["title"])}</figcaption></figure>
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
    }
    return page_shell(config, item["title"], item["description"], canonical, body, image, structured)


def render_index(config: dict, items: list[dict]) -> str:
    cards = []
    for item in items:
        canonical, image = item_urls(config, item)
        cards.append(f"""
<article class="card">
  <a href="{esc(canonical)}"><img src="{esc(image)}" alt="{esc(item["title"])}" width="700" height="700"></a>
  <div><p class="eyebrow">Airfryer-Idee</p><h2><a href="{esc(canonical)}">{esc(item["title"])}</a></h2><p>{esc(item["description"])}</p></div>
</article>
""")
    cards_html = "".join(cards) if cards else "<p>Die erste Rezeptidee erscheint in Kuerze.</p>"
    body = f"""
<section class="hero">
  <div><h1>Einfach. Knusprig. Airfryer.</h1>
  <p>{esc(config["description"])}</p>
  <a class="cta" href="{esc(config["amazon_url"])}" rel="nofollow sponsored">140 Rezepte im Buch entdecken</a></div>
</section>
<section class="section"><h2>Neue Rezeptideen</h2><div class="cards">{cards_html}</div></section>
"""
    return page_shell(config, config["site_name"], config["description"], config["base_url"] + "/", body)


def render_privacy(config: dict) -> str:
    body = """
<article class="prose">
  <p class="eyebrow">Datenschutz</p>
  <h1>Datenschutzhinweise</h1>
  <p>Diese statische Website setzt keine Cookies ein, verwendet keine Formulare und bindet keine externen Analyse- oder Werbedienste ein.</p>
  <p>Beim Aufruf verarbeitet der Hosting-Anbieter technisch notwendige Serverdaten. Beim Klick auf einen Amazon-Link gelten die Datenschutzbestimmungen von Amazon.</p>
  <p>Die Links f&uuml;hren zu den jeweiligen Buchangeboten bei Amazon. Auf dieser Website werden keine Zahlungs- oder Kundendaten verarbeitet.</p>
</article>
"""
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
    for item in sorted(items, key=lambda value: parse_time(value["publish_at"]), reverse=True)[:50]:
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
    items = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    live = [item for item in items if parse_time(item["publish_at"]) <= now]

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    shutil.copytree(ASSETS, DOCS / "assets", dirs_exist_ok=True)

    write(DOCS / ".nojekyll", "")
    write(DOCS / "styles.css", (ROOT / "styles.css").read_text(encoding="utf-8"))
    write(DOCS / "index.html", render_index(config, sorted(live, key=lambda value: parse_time(value["publish_at"]), reverse=True)))
    write(DOCS / "datenschutz.html", render_privacy(config))
    for item in live:
        write(DOCS / "rezepte" / f'{item["id"]}.html', render_item(config, item))

    (DOCS / "feed.xml").write_bytes(render_feed(config, live))
    sitemap_urls = [config["base_url"] + "/", config["base_url"] + "/datenschutz.html"]
    sitemap_urls.extend(item_urls(config, item)[0] for item in live)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += "".join(f"  <url><loc>{esc(url)}</loc></url>\n" for url in sitemap_urls)
    sitemap += "</urlset>\n"
    write(DOCS / "sitemap.xml", sitemap)
    write(DOCS / "robots.txt", f'User-agent: *\nAllow: /\nSitemap: {config["base_url"]}/sitemap.xml\n')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", help="UTC ISO timestamp used for a reproducible build")
    parser.add_argument("--base-url", help="Override the public URL for local preview")
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    build(now, args.base_url)


if __name__ == "__main__":
    main()
