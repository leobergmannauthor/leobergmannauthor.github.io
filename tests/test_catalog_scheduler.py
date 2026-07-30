from __future__ import annotations

import copy
import json
import sys
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog_scheduler import parse_time, schedule_payloads  # noqa: E402


class PreparedCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data" / "pin_catalog.json").read_text(encoding="utf-8"))
        cls.books = json.loads((ROOT / "data" / "books.json").read_text(encoding="utf-8"))
        cls.policy = json.loads((ROOT / "data" / "automation_policy.json").read_text(encoding="utf-8"))

    def test_catalog_covers_every_german_recipe_book(self):
        self.assertEqual(len(self.books["books"]), 14)
        self.assertEqual(self.catalog["item_count"], 1960)
        counts = Counter(item["book_id"] for item in self.catalog["items"])
        self.assertEqual(set(counts.values()), {140})
        self.assertEqual(len({item["catalog_id"] for item in self.catalog["items"]}), 1960)

    def test_catalog_is_publication_safe(self):
        serialized = json.dumps(self.catalog, ensure_ascii=False).lower()
        self.assertNotIn("c:\\daten", serialized)
        self.assertNotIn("bookgenpy", serialized)
        for item in self.catalog["items"]:
            self.assertLessEqual(len(item["pin_title"]), 100)
            self.assertLessEqual(len(item["pin_description"]), 500)
            self.assertIn(item["asset_status"], {"ready", "blocked_missing_asset"})
            self.assertIn(item["publication_status"], {"available", "scheduled", "confirmed", "unpublished"})
            lowered = item["description"].lower()
            for risky in ("entgiftet", "entgiften", "bekämpft entzündungen", "heilende kraft", "leberschützende wirkung"):
                self.assertNotIn(risky, lowered, item["catalog_id"])

    def test_only_published_books_have_verified_direct_amazon_destinations(self):
        published = [book for book in self.books["books"] if book["published"]]
        unpublished = [book for book in self.books["books"] if not book["published"]]
        self.assertEqual(len(published), 11)
        self.assertEqual(len(unpublished), 3)
        for book in published:
            self.assertEqual(book["target_kind"], "direct")
            self.assertIn("https://www.amazon.de/dp/", book["amazon_url"])
            self.assertNotIn("/s?", book["amazon_url"])
        for book in unpublished:
            self.assertEqual(book["target_kind"], "unpublished")
            self.assertEqual(book["amazon_url"], "")
            self.assertFalse(any(
                item["book_id"] == book["id"]
                for item in self.catalog["items"]
                if item["publication_status"] != "unpublished"
            ))

    def test_ready_creatives_have_valid_pinterest_dimensions(self):
        ready = [item for item in self.catalog["items"] if item["asset_status"] == "ready"]
        self.assertGreaterEqual(len(ready), 1539)
        by_book = {}
        for item in ready:
            path = ROOT / "docs" / item["image"]
            self.assertTrue(path.is_file(), item["catalog_id"])
            by_book.setdefault(item["book_id"], path)
        for path in by_book.values():
            with Image.open(path) as image:
                self.assertEqual(image.size, (1000, 1500))
                self.assertEqual(image.format, "JPEG")

    def test_scheduler_is_idempotent_and_respects_daily_limit(self):
        catalog = copy.deepcopy(self.catalog)
        for item in catalog["items"]:
            if item["asset_status"] == "ready":
                item["publication_status"] = "available"
                item["scheduled_at"] = None
                item["pin_url"] = None
        now = datetime(2026, 8, 1, 8, tzinfo=timezone.utc)
        scheduled, content, result = schedule_payloads(catalog, self.books, [], self.policy, now)
        self.assertEqual(len(scheduled), 60)
        daily = Counter(parse_time(item["publish_at"]).date() for item in content)
        self.assertTrue(all(value <= 2 for value in daily.values()))
        scheduled_again, content_again, _ = schedule_payloads(result["catalog"], self.books, content, self.policy, now)
        self.assertEqual(scheduled_again, [])
        self.assertEqual(content_again, content)

    def test_three_year_simulation_exhausts_cleanly_without_duplicates(self):
        catalog = copy.deepcopy(self.catalog)
        for item in catalog["items"]:
            if item["asset_status"] == "ready":
                item["publication_status"] = "available"
                item["scheduled_at"] = None
                item["pin_url"] = None
        content = []
        result = {"catalog": catalog, "state": {}}
        now = datetime(2026, 8, 1, 8, tzinfo=timezone.utc)
        for offset in range(0, 1096, 30):
            _, content, result = schedule_payloads(result["catalog"], self.books, content, self.policy, now + timedelta(days=offset))
        ids = [item["id"] for item in content]
        self.assertEqual(len(ids), len(set(ids)))
        daily = Counter(parse_time(item["publish_at"]).date() for item in content)
        self.assertTrue(all(value <= 2 for value in daily.values()))
        self.assertEqual(result["state"]["queue_status"], "exhausted")
        before = len(content)
        scheduled, content, result = schedule_payloads(result["catalog"], self.books, content, self.policy, now + timedelta(days=1125))
        self.assertEqual(scheduled, [])
        self.assertEqual(len(content), before)
        self.assertEqual(result["state"]["queue_status"], "exhausted")

    def test_zero_budget_lock_fails_closed(self):
        unsafe = dict(self.policy, daily_budget_eur=1)
        with self.assertRaises(RuntimeError):
            schedule_payloads(self.catalog, self.books, [], unsafe, datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
