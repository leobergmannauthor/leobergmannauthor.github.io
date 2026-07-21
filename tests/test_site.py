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


if __name__ == "__main__":
    unittest.main()
