from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONFIG = json.loads((ROOT / "site_config.json").read_text(encoding="utf-8"))


class SiteBuildTest(unittest.TestCase):
    def test_required_files_exist(self):
        for relative in ("index.html", "feed.xml", "sitemap.xml", "robots.txt", "styles.css", "datenschutz.html"):
            self.assertTrue((DOCS / relative).is_file(), relative)

    def test_feed_is_valid_and_has_public_items(self):
        root = ET.parse(DOCS / "feed.xml").getroot()
        self.assertEqual(root.tag, "rss")
        feed_base = root.findtext("./channel/link").rstrip("/")
        items = root.findall("./channel/item")
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            link = item.findtext("link")
            self.assertTrue(link.startswith(feed_base + "/"))
            self.assertTrue(item.findtext("title"))
            self.assertTrue(item.findtext("description"))
            media = item.find("{http://search.yahoo.com/mrss/}content")
            self.assertIsNotNone(media)
            self.assertTrue(media.attrib["url"].startswith(feed_base + "/assets/"))

    def test_every_feed_target_and_image_exists(self):
        root = ET.parse(DOCS / "feed.xml").getroot()
        feed_base = root.findtext("./channel/link").rstrip("/")
        base_path = urlparse(feed_base).path.rstrip("/")
        for item in root.findall("./channel/item"):
            page_path = urlparse(item.findtext("link")).path
            relative_page = page_path[len(base_path):].lstrip("/")
            self.assertTrue((DOCS / relative_page).is_file(), relative_page)
            media = item.find("{http://search.yahoo.com/mrss/}content")
            image_path = urlparse(media.attrib["url"]).path
            relative_image = image_path[len(base_path):].lstrip("/")
            self.assertTrue((DOCS / relative_image).is_file(), relative_image)

    def test_feed_build_date_tracks_newest_item(self):
        root = ET.parse(DOCS / "feed.xml").getroot()
        newest_item = max(
            parsedate_to_datetime(item.findtext("pubDate")) for item in root.findall("./channel/item")
        )
        self.assertEqual(parsedate_to_datetime(root.findtext("./channel/lastBuildDate")), newest_item)

    def test_public_output_contains_no_internal_or_secret_markers(self):
        forbidden = (
            "credentials.vault",
            "password",
            "api_key",
            "access_token",
            "secret_key",
            "werbung f",
            "0 eur",
            "werbebudget",
            "keine bezahlte pinterest-werbung",
        )
        for path in DOCS.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".html", ".xml", ".txt", ".css", ""}:
                text = path.read_text(encoding="utf-8").lower()
                for marker in forbidden:
                    self.assertNotIn(marker, text, f"{marker} in {path}")

    def test_pinterest_verification_tag_is_published(self):
        index = (DOCS / "index.html").read_text(encoding="utf-8")
        expected = f'<meta name="p:domain_verify" content="{CONFIG["pinterest_domain_verify"]}">'
        self.assertIn(expected, index)


    def test_workflow_installs_declared_dependencies_before_tests(self):
        workflow = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-autopilot.txt").read_text(encoding="utf-8")
        install_command = "python -m pip install --requirement requirements-autopilot.txt"
        test_command = "python -m unittest discover -s tests -v"
        self.assertIn("Pillow==12.0.0", requirements)
        self.assertIn(install_command, workflow)
        self.assertIn(test_command, workflow)
        self.assertLess(workflow.index(install_command), workflow.index(test_command))

    def test_published_books_have_public_covers(self):
        books = json.loads((ROOT / "data" / "books.json").read_text(encoding="utf-8"))["books"]
        published = [book for book in books if book.get("published")]
        self.assertEqual(len(published), 11)
        for book in published:
            self.assertTrue(book.get("cover"), book["id"])
            parsed = urlparse(book["cover"])
            if parsed.scheme:
                self.assertEqual(parsed.scheme, "https", book["id"])
                self.assertEqual(parsed.netloc, "m.media-amazon.com", book["id"])
                self.assertTrue(parsed.path.endswith(".jpg"), book["id"])
            else:
                cover = DOCS / book["cover"]
                self.assertTrue(cover.is_file(), book["id"])
                self.assertGreater(cover.stat().st_size, 50_000, book["id"])

    def test_every_recipe_page_has_conversion_sections_and_direct_amazon_ctas(self):
        pages = sorted((DOCS / "rezepte").glob("*.html"))
        self.assertGreaterEqual(len(pages), 1)
        for page in pages:
            text = page.read_text(encoding="utf-8")
            self.assertIn('class="conversion-card"', text, page.name)
            self.assertIn('class="book-offer"', text, page.name)
            self.assertIn('class="mobile-buy-bar"', text, page.name)
            self.assertGreaterEqual(text.count("data-amazon-cta"), 3, page.name)
            self.assertGreaterEqual(text.count("https://www.amazon.de/dp/"), 4, page.name)
            self.assertIn('rel="nofollow sponsored noopener"', text, page.name)
            self.assertNotIn("https://www.amazon.de/s?", text, page.name)

if __name__ == "__main__":
    unittest.main()
