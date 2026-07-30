from __future__ import annotations

import sys
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pinterest_autopilot import (  # noqa: E402
    choose_recipes,
    future_dates,
    is_duplicate_title,
    render_creative,
    split_headline,
)


class PinterestAutopilotTest(unittest.TestCase):
    def test_duplicate_detection_handles_existing_native_variant(self):
        self.assertTrue(
            is_duplicate_title(
                "Churros mit Schokosoße",
                ["Churros aus dem Airfryer – knusprig und schnell"],
            )
        )
        self.assertFalse(
            is_duplicate_title(
                "Mozzarella-Sticks knusprig",
                ["Churros aus dem Airfryer – knusprig und schnell"],
            )
        )

    def test_future_dates_extend_only_to_target_horizon(self):
        items = [{"id": "recipe_001", "publish_at": "2026-08-10T07:00:00Z"}]
        dates = future_dates(
            items,
            target_days=14,
            max_new=7,
            now=datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
            publish_hour=9,
        )
        self.assertEqual(
            [value.date().isoformat() for value in dates],
            ["2026-08-11", "2026-08-12", "2026-08-13"],
        )

    def test_selection_penalizes_an_overrepresented_category(self):
        candidates = [
            {
                "id": "recipe_079",
                "title": "Mozzarella-Sticks knusprig",
                "description": "",
                "category": "snacks",
                "cook_minutes": 10,
            },
            {
                "id": "recipe_060",
                "title": "Garnelen im Knoblauchöl",
                "description": "",
                "category": "fish",
                "cook_minutes": 10,
            },
        ]
        selected = choose_recipes(candidates, 1, Counter({"snacks": 10}))
        self.assertEqual(selected[0]["category"], "fish")

    def test_headline_is_limited_to_three_lines(self):
        lines = split_headline("Rinderhüftsteak mit Knoblauchbutter im Airfryer")
        self.assertLessEqual(len(lines), 3)
        self.assertTrue(all(lines))

    def test_renderer_creates_pinterest_portrait(self):
        test_root = Path(__file__).resolve().parent
        source = test_root / "_autopilot_render_source.png"
        destination = test_root / "_autopilot_render_pin.jpg"
        try:
            Image.new("RGB", (700, 700), "#bf6d2f").save(source)
            render_creative(
                source,
                destination,
                ["TEST-REZEPT"],
                "knusprig · einfach · 10 Min. Garzeit",
            )
            with Image.open(destination) as rendered:
                self.assertEqual(rendered.size, (896, 1152))
                self.assertEqual(rendered.format, "JPEG")
        finally:
            source.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
