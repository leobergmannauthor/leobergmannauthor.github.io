from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTENT_FILE = ROOT / "content" / "recipes.json"
CONFIG_FILE = ROOT / "site_config.json"
HISTORY_FILE = ROOT / "data" / "publication_history.json"

RSS_SCHEDULED = "scheduled"
RSS_PUBLISHED = "published_to_feed"
PINTEREST_NOT_ELIGIBLE = "not_yet_eligible"
PINTEREST_AWAITING = "awaiting_import_confirmation"
PINTEREST_CONFIRMED = "confirmed"
PINTEREST_OVERDUE = "confirmation_overdue"
PINTEREST_TERMINAL = {PINTEREST_CONFIRMED, "failed"}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def item_urls(config: dict, item: dict) -> tuple[str, str]:
    base_url = config["base_url"].rstrip("/")
    return (
        f'{base_url}/rezepte/{item["id"]}.html',
        f'{base_url}/{item["image"]}',
    )


def synchronize_history(recipes: list[dict], config: dict, history: dict, now: datetime) -> dict:
    now = now.astimezone(timezone.utc)
    existing_by_id = {
        entry["content_id"]: entry
        for entry in history.get("items", [])
        if isinstance(entry, dict) and entry.get("content_id")
    }
    entries = []

    for item in sorted(recipes, key=lambda value: parse_time(value["publish_at"])):
        existing = existing_by_id.get(item["id"], {})
        due = parse_time(item["publish_at"]) <= now
        expected_import_by = parse_time(item["publish_at"]) + timedelta(hours=24)
        page_url, image_url = item_urls(config, item)

        old_rss = existing.get("rss", {})
        first_observed = old_rss.get("first_repository_observed_at")
        if due and not first_observed:
            first_observed = format_time(now)

        old_pinterest = deepcopy(existing.get("pinterest", {}))
        pinterest_status = old_pinterest.get("status")
        if pinterest_status not in PINTEREST_TERMINAL:
            if not due:
                pinterest_status = PINTEREST_NOT_ELIGIBLE
            elif now <= expected_import_by:
                pinterest_status = PINTEREST_AWAITING
            else:
                pinterest_status = PINTEREST_OVERDUE

        pinterest = {
            "status": pinterest_status,
            "expected_import_by": format_time(expected_import_by),
            "pin_url": old_pinterest.get("pin_url"),
            "confirmed_at": old_pinterest.get("confirmed_at"),
            "last_checked_at": old_pinterest.get("last_checked_at"),
        }
        if old_pinterest.get("note"):
            pinterest["note"] = old_pinterest["note"]

        entries.append(
            {
                "content_id": item["id"],
                "title": item["title"],
                "scheduled_at": item["publish_at"],
                "page_url": page_url,
                "image_url": image_url,
                "rss": {
                    "status": RSS_PUBLISHED if due else RSS_SCHEDULED,
                    "feed_item_pub_date": item["publish_at"] if due else None,
                    "first_repository_observed_at": first_observed if due else None,
                },
                "pinterest": pinterest,
            }
        )

    candidate = {
        "schema_version": 1,
        "channel": "pinterest_rss",
        "feed_url": config["base_url"].rstrip("/") + "/feed.xml",
        "board": config["pinterest_board"],
        "last_updated_at": history.get("last_updated_at"),
        "items": entries,
    }

    comparable_old = deepcopy(history)
    comparable_old["last_updated_at"] = candidate["last_updated_at"]
    if comparable_old != candidate:
        candidate["last_updated_at"] = format_time(now)
    return candidate


def sync(now: datetime) -> dict:
    recipes = load_json(CONTENT_FILE, [])
    config = load_json(CONFIG_FILE, {})
    history = load_json(HISTORY_FILE, {})
    updated = synchronize_history(recipes, config, history, now)
    if updated != history:
        write_json(HISTORY_FILE, updated)
    return updated


def confirm_pinterest(content_id: str, pin_url: str, confirmed_at: datetime) -> dict:
    parsed = urlparse(pin_url)
    if parsed.scheme != "https" or not parsed.hostname or "pinterest." not in parsed.hostname or "/pin/" not in parsed.path:
        raise ValueError("pin_url must be a public HTTPS Pinterest /pin/ URL")

    history = sync(confirmed_at)
    matching = [item for item in history["items"] if item["content_id"] == content_id]
    if not matching:
        raise KeyError(f"Unknown content_id: {content_id}")

    item = matching[0]
    if item["rss"]["status"] != RSS_PUBLISHED:
        raise ValueError("A Pinterest import cannot be confirmed before the item is published in RSS")

    timestamp = format_time(confirmed_at)
    item["pinterest"] = {
        "status": PINTEREST_CONFIRMED,
        "expected_import_by": item["pinterest"]["expected_import_by"],
        "pin_url": pin_url,
        "confirmed_at": timestamp,
        "last_checked_at": timestamp,
    }
    history["last_updated_at"] = timestamp
    write_json(HISTORY_FILE, history)
    return history


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain the durable RSS and Pinterest publication ledger.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Synchronize RSS eligibility and preserve Pinterest confirmations.")
    sync_parser.add_argument("--now", help="UTC ISO timestamp for reproducible synchronization.")

    confirm_parser = subparsers.add_parser("confirm-pinterest", help="Record a verified public Pinterest Pin.")
    confirm_parser.add_argument("content_id")
    confirm_parser.add_argument("pin_url")
    confirm_parser.add_argument("--confirmed-at", help="UTC ISO timestamp; defaults to now.")

    args = parser.parse_args()
    if args.command == "sync":
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
        result = sync(now)
    else:
        confirmed_at = parse_time(args.confirmed_at) if args.confirmed_at else datetime.now(timezone.utc)
        result = confirm_pinterest(args.content_id, args.pin_url, confirmed_at)

    published = sum(item["rss"]["status"] == RSS_PUBLISHED for item in result["items"])
    confirmed = sum(item["pinterest"]["status"] == PINTEREST_CONFIRMED for item in result["items"])
    print(f"History synchronized: {published} RSS items published, {confirmed} Pinterest imports confirmed.")


if __name__ == "__main__":
    main()
