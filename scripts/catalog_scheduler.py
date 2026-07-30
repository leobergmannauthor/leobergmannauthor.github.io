"""Durable zero-budget scheduler for prepared Pinterest RSS content.

Runs in GitHub Actions without private book sources or Pillow. It only promotes already
prepared, validated creatives from data/pin_catalog.json into content/recipes.json.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = ROOT / "data" / "pin_catalog.json"
BOOKS_FILE = ROOT / "data" / "books.json"
POLICY_FILE = ROOT / "data" / "automation_policy.json"
STATE_FILE = ROOT / "data" / "scheduler_state.json"
CONTENT_FILE = ROOT / "content" / "recipes.json"


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("daily_budget_eur") != 0 or policy.get("paid_channels_enabled") is not False:
        raise RuntimeError("Zero-budget safety lock is not active")
    if not 1 <= int(policy.get("pins_per_day", 0)) <= 5:
        raise RuntimeError("pins_per_day must be between 1 and 5")
    hours = policy.get("publish_hours", [])
    if len(hours) < int(policy["pins_per_day"]) or len(set(hours)) != len(hours):
        raise RuntimeError("publish_hours must contain unique slots for every daily pin")
    if any(not isinstance(hour, int) or hour < 0 or hour > 23 for hour in hours):
        raise RuntimeError("publish_hours contains an invalid hour")


def pick_candidate(
    candidates: list[dict[str, Any]],
    slot: datetime,
    content: list[dict[str, Any]],
    book_counts: Counter[str],
    cooldown_days: int,
) -> dict[str, Any] | None:
    threshold = slot.astimezone(timezone.utc) - timedelta(days=cooldown_days)
    recent_titles = {
        normalize(item.get("title", ""))
        for item in content
        if item.get("publish_at") and threshold <= parse_time(item["publish_at"]) <= slot.astimezone(timezone.utc)
    }
    day = slot.date()
    day_books = {
        item.get("book_id")
        for item in content
        if item.get("publish_at") and parse_time(item["publish_at"]).astimezone(slot.tzinfo).date() == day
    }
    eligible = [
        item for item in candidates
        if item["book_id"] not in day_books and normalize(item["title"]) not in recent_titles
    ]
    if not eligible:
        eligible = [item for item in candidates if normalize(item["title"]) not in recent_titles]
    if not eligible:
        return None
    eligible.sort(key=lambda item: (book_counts[item["book_id"]], item["book_id"], item["source_recipe_id"]))
    return eligible[0]


def schedule_payloads(
    catalog: dict[str, Any],
    books_payload: dict[str, Any],
    content: list[dict[str, Any]],
    policy: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    validate_policy(policy)
    timezone_name = policy.get("timezone", "Europe/Berlin")
    local_zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(local_zone)
    horizon = int(policy.get("schedule_horizon_days", 30))
    pins_per_day = int(policy["pins_per_day"])
    publish_hours = list(policy["publish_hours"])
    cooldown_days = int(policy.get("title_cooldown_days", 180))
    book_by_id = {book["id"]: book for book in books_payload.get("books", [])}
    catalog_items = copy.deepcopy(catalog.get("items", []))
    by_catalog_id = {item["catalog_id"]: item for item in catalog_items}
    existing_catalog_ids = {item.get("catalog_id") for item in content if item.get("catalog_id")}
    existing_content_ids = {item.get("id") for item in content}
    candidates = [
        item for item in catalog_items
        if item.get("asset_status") == "ready"
        and item.get("publication_status") == "available"
        and book_by_id.get(item.get("book_id"), {}).get("published") is True
        and item.get("catalog_id") not in existing_catalog_ids
        and not item.get("pin_url")
    ]
    book_counts = Counter(item.get("book_id") for item in content if item.get("book_id"))
    scheduled: list[dict[str, Any]] = []

    for day_offset in range(1, horizon + 1):
        day = local_now.date() + timedelta(days=day_offset)
        day_items = [
            item for item in content
            if item.get("publish_at") and parse_time(item["publish_at"]).astimezone(local_zone).date() == day
        ]
        remaining = max(0, pins_per_day - len(day_items))
        used_hours = {parse_time(item["publish_at"]).astimezone(local_zone).hour for item in day_items}
        for hour in publish_hours:
            if remaining <= 0 or not candidates:
                break
            if hour in used_hours:
                continue
            slot = datetime.combine(day, time(hour, 0), local_zone)
            candidate = pick_candidate(candidates, slot, content, book_counts, cooldown_days)
            if candidate is None:
                continue
            content_id = candidate["catalog_id"].replace(":", "-")
            if content_id in existing_content_ids:
                raise RuntimeError(f"Duplicate content id: {content_id}")
            book = book_by_id[candidate["book_id"]]
            publish_at = slot.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            new_item = {
                "id": content_id,
                "catalog_id": candidate["catalog_id"],
                "book_id": candidate["book_id"],
                "title": candidate["pin_title"],
                "description": candidate["pin_description"],
                "prep": candidate.get("prep", ""),
                "cook": candidate.get("cook", ""),
                "servings": candidate.get("servings", ""),
                "difficulty": candidate.get("difficulty", ""),
                "image": candidate["image"],
                "publish_at": publish_at,
                "amazon_url": book["amazon_url"],
            }
            content.append(new_item)
            scheduled.append(new_item)
            existing_content_ids.add(content_id)
            existing_catalog_ids.add(candidate["catalog_id"])
            candidate["publication_status"] = "scheduled"
            candidate["scheduled_at"] = publish_at
            by_catalog_id[candidate["catalog_id"]] = candidate
            candidates.remove(candidate)
            book_counts[candidate["book_id"]] += 1
            used_hours.add(hour)
            remaining -= 1

    updated_catalog = copy.deepcopy(catalog)
    updated_catalog["items"] = sorted(by_catalog_id.values(), key=lambda item: item["catalog_id"])
    updated_catalog["ready_count"] = sum(1 for item in updated_catalog["items"] if item.get("asset_status") == "ready")
    updated_catalog["available_count"] = sum(1 for item in updated_catalog["items"] if item.get("asset_status") == "ready" and item.get("publication_status") == "available")
    available = updated_catalog["available_count"]
    state = {
        "schema_version": 1,
        "last_run_at": now.astimezone(timezone.utc).isoformat(),
        "scheduled_this_run": len(scheduled),
        "scheduled_through": max((item["publish_at"] for item in content if item.get("publish_at")), default=None),
        "ready_available": available,
        "blocked_missing_asset": sum(1 for item in updated_catalog["items"] if item.get("asset_status") == "blocked_missing_asset"),
        "queue_status": "active" if available else "exhausted",
        "cost_eur": 0,
    }
    content.sort(key=lambda item: (parse_time(item["publish_at"]), item["id"]))
    return scheduled, content, {"catalog": updated_catalog, "state": state}


def execute(now: datetime, dry_run: bool = False) -> dict[str, Any]:
    catalog = read_json(CATALOG_FILE, {"items": []})
    books = read_json(BOOKS_FILE, {"books": []})
    policy = read_json(POLICY_FILE, {})
    content = read_json(CONTENT_FILE, [])
    previous_state = read_json(STATE_FILE, {})
    scheduled, updated_content, result = schedule_payloads(catalog, books, content, policy, now)
    if not scheduled and previous_state:
        stable_keys = ("scheduled_through", "ready_available", "blocked_missing_asset", "queue_status", "cost_eur")
        if all(previous_state.get(key) == result["state"].get(key) for key in stable_keys):
            result["state"] = previous_state
    if not dry_run:
        atomic_json(CONTENT_FILE, updated_content)
        atomic_json(CATALOG_FILE, result["catalog"])
        atomic_json(STATE_FILE, result["state"])
    return {"scheduled": scheduled, "state": result["state"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule prepared organic Pinterest content")
    parser.add_argument("--now", help="ISO timestamp for reproducible runs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    result = execute(now, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
