from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from publication_history import (
    PINTEREST_AWAITING,
    PINTEREST_CONFIRMED,
    PINTEREST_NOT_ELIGIBLE,
    PINTEREST_OVERDUE,
    RSS_PUBLISHED,
    RSS_SCHEDULED,
    synchronize_history,
)

ROOT = Path(__file__).resolve().parents[1]
RECIPES = json.loads((ROOT / "content" / "recipes.json").read_text(encoding="utf-8"))
CONFIG = json.loads((ROOT / "site_config.json").read_text(encoding="utf-8"))
HISTORY = json.loads((ROOT / "data" / "publication_history.json").read_text(encoding="utf-8"))


class PublicationHistoryTest(unittest.TestCase):
    def test_history_tracks_every_content_item_once(self):
        recipe_ids = [item["id"] for item in RECIPES]
        history_ids = [item["content_id"] for item in HISTORY["items"]]
        self.assertEqual(history_ids, recipe_ids)
        self.assertEqual(len(history_ids), len(set(history_ids)))

    def test_published_history_matches_current_feed(self):
        feed = ET.parse(ROOT / "docs" / "feed.xml").getroot()
        feed_ids = {
            Path(urlparse(item.findtext("guid")).path).stem
            for item in feed.findall("./channel/item")
        }
        published_ids = {
            item["content_id"]
            for item in HISTORY["items"]
            if item["rss"]["status"] == RSS_PUBLISHED
        }
        self.assertEqual(published_ids, feed_ids)

    def test_status_fields_do_not_claim_unverified_pins(self):
        for item in HISTORY["items"]:
            rss = item["rss"]
            pinterest = item["pinterest"]
            self.assertIn(rss["status"], {RSS_SCHEDULED, RSS_PUBLISHED})
            self.assertIn(
                pinterest["status"],
                {PINTEREST_NOT_ELIGIBLE, PINTEREST_AWAITING, PINTEREST_CONFIRMED, PINTEREST_OVERDUE, "failed"},
            )
            self.assertTrue(pinterest["expected_import_by"])
            if pinterest["status"] == PINTEREST_CONFIRMED:
                self.assertTrue(pinterest["pin_url"])
                self.assertTrue(pinterest["confirmed_at"])
            else:
                self.assertIsNone(pinterest["pin_url"])
                self.assertIsNone(pinterest["confirmed_at"])

    def test_sync_is_idempotent_until_the_next_item_is_due(self):
        first_now = datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc)
        first = synchronize_history(RECIPES, CONFIG, {}, first_now)
        second = synchronize_history(
            RECIPES,
            CONFIG,
            first,
            datetime(2026, 7, 22, 5, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(first, second)
        self.assertEqual(
            sum(item["rss"]["status"] == RSS_PUBLISHED for item in first["items"]),
            4,
        )

    def test_unconfirmed_item_becomes_overdue_after_24_hours(self):
        initial = synchronize_history(
            RECIPES,
            CONFIG,
            {},
            datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc),
        )
        updated = synchronize_history(
            RECIPES,
            CONFIG,
            initial,
            datetime(2026, 7, 23, 5, 0, tzinfo=timezone.utc),
        )
        by_id = {item["content_id"]: item for item in updated["items"]}
        self.assertEqual(by_id["recipe_101"]["pinterest"]["status"], PINTEREST_OVERDUE)
        self.assertEqual(
            by_id["recipe_101"]["pinterest"]["expected_import_by"],
            "2026-07-22T21:28:00Z",
        )

    def test_sync_transitions_due_items_and_preserves_confirmations(self):
        initial = synchronize_history(
            RECIPES,
            CONFIG,
            {},
            datetime(2026, 7, 22, 4, 0, tzinfo=timezone.utc),
        )
        initial["items"][0]["pinterest"] = {
            "status": PINTEREST_CONFIRMED,
            "pin_url": "https://www.pinterest.com/pin/123456789/",
            "confirmed_at": "2026-07-22T04:30:00Z",
            "last_checked_at": "2026-07-22T04:30:00Z",
        }
        updated = synchronize_history(
            RECIPES,
            CONFIG,
            initial,
            datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc),
        )
        by_id = {item["content_id"]: item for item in updated["items"]}
        self.assertEqual(by_id["recipe_102"]["rss"]["status"], RSS_PUBLISHED)
        self.assertEqual(by_id["recipe_102"]["pinterest"]["status"], PINTEREST_AWAITING)
        self.assertEqual(by_id["airfryer-kochbuch"]["pinterest"]["status"], PINTEREST_CONFIRMED)


if __name__ == "__main__":
    unittest.main()
