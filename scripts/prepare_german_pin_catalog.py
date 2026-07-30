"""Prepare durable Pinterest creatives for every German Leo Bergmann recipe book.

This local, incremental build step reads the private BookGenPy source library and writes
only publication-safe metadata plus finished 1000x1500 JPEG creatives into this repo.
GitHub Actions never needs access to the private source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from pinterest_autopilot import IMAGE_SIZE, render_creative, split_headline

ROOT = SCRIPT_DIR.parent
SOURCE_LIBRARY = Path(os.environ.get("BOOKGENPY_LIBRARY", r"C:\Daten\src\python\BookGenPy\library"))
CATALOG_FILE = ROOT / "data" / "pin_catalog.json"
BOOKS_FILE = ROOT / "data" / "books.json"
CONTENT_FILE = ROOT / "content" / "recipes.json"
OUTPUT_ROOT = ROOT / "docs" / "assets" / "pins"
CREATIVE_VERSION = "de-recipe-v2-1000x1500"

BOOKS: dict[str, dict[str, Any]] = {
    "001_protein": {"title": "High Protein Power-Küche für Berufstätige", "label": "HIGH PROTEIN", "promise": "Proteinreich • schnell • alltagstauglich", "asin": "B0G1KMD28S", "published": True},
    "002_airfryer": {"title": "XXL Airfryer Kochbuch: 140 schnelle Rezepte für die Heißluftfritteuse", "label": "AIRFRYER-REZEPT", "promise": "Knusprig • einfach • alltagstauglich", "asin": "B0GHFYM758", "published": True},
    "003_vegetarisch": {"title": "Vegetarisches XXL Kochbuch: 140 schnelle Rezepte", "label": "VEGETARISCH", "promise": "Fleischlos • lecker • unkompliziert", "asin": "B0GHJLCKSV", "published": True},
    "004_meal_prep": {"title": "XXL Meal Prep Kochbuch für Anfänger", "label": "MEAL PREP", "promise": "Vorkochen • mitnehmen • Zeit sparen", "asin": "B0GHMMF8LP", "published": True},
    "005_low_carb": {"title": "XXL Low Carb Kochbuch für Anfänger", "label": "LOW CARB", "promise": "Kohlenhydratarm • lecker • einfach", "asin": "B0GMBPQ4HJ", "published": True},
    "006_family": {"title": "XXL Familienkochbuch für jeden Geldbeutel", "label": "FAMILIENKÜCHE", "promise": "Familienfreundlich • günstig • lecker", "asin": "B0GMBVNP6Z", "published": True},
    "007_men": {"title": "XXL Männer-Kochbuch", "label": "EINFACH DEFTIG", "promise": "Deftig • unkompliziert • sättigend", "asin": "B0GMH1JMYW", "published": True},
    "008_liver": {"title": "XXL Fettleber Kochbuch", "label": "LEBERFREUNDLICH", "promise": "Ausgewogen • genussvoll • alltagstauglich", "asin": "B0GMQ23L4J", "published": True},
    "009_anti_entzuendung": {"title": "XXL Anti-Entzündliches Kochbuch", "label": "BEWUSST GENIESSEN", "promise": "Aromatisch • ausgewogen • vielseitig", "asin": "B0GPKWWSS9", "published": True},
    "011_hp_basics": {"title": "Eiweißreich kochen: 140 proteinreiche Rezepte mit max. 5 Zutaten", "label": "5 ZUTATEN", "promise": "Proteinreich • wenige Zutaten • schnell", "asin": "B0H8K8XZFZ", "published": True},
    "012_hp_veggie": {"title": "Vegetarisches High Protein Kochbuch für Muskelaufbau", "label": "VEGGIE PROTEIN", "promise": "Fleischlos • proteinreich • sättigend", "asin": "B0H9NYMR72", "published": True},
    "013_hp_prep": {"title": "High Protein Meal Prep für Büro und Training", "label": "PROTEIN MEAL PREP", "promise": "Vorkochen • proteinreich • praktisch", "asin": "", "published": False},
    "014_hp_snacks": {"title": "High Protein Backen & Snacks ohne Proteinpulver", "label": "PROTEIN SNACK", "promise": "Snacken • backen • proteinreich", "asin": "", "published": False},
    "015_hp_women": {"title": "High Protein Kochbuch für Frauen ab 40", "label": "PROTEIN 40+", "promise": "Proteinreich • genussvoll • alltagstauglich", "asin": "", "published": False},
}


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return fallback


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def amazon_url(book: dict[str, Any]) -> tuple[str, str]:
    if not book["published"]:
        return "", "unpublished"
    if not book["asin"]:
        raise RuntimeError(f"Published book lacks a verified ASIN: {book['title']}")
    return f"https://www.amazon.de/dp/{book['asin']}?utm_source=pinterest&utm_medium=organic&utm_campaign=leo_bergmann_books", "direct"


def value(nutrition: dict[str, Any], key: str) -> str:
    raw = nutrition.get(key, "")
    return str(raw.get("value", "") if isinstance(raw, dict) else raw).strip()


def source_fingerprint(recipe_path: Path, image_path: Path | None) -> str:
    digest = hashlib.sha256()
    digest.update(CREATIVE_VERSION.encode())
    digest.update(recipe_path.read_bytes())
    if image_path and image_path.exists():
        stat = image_path.stat()
        digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


RISKY_CLAIM = re.compile(
    r"entzünd|leber|entgift|heil(?:end|t|kraft)|bekämpf|linder|therap|rheuma|arthrose|"
    r"stoffwechsel|wechseljahr|blutzucker|cholesterin|krankheit|fettverbrenn|abnehm",
    re.IGNORECASE,
)


def safe_excerpt(title: str, description: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", description).strip())
    safe = [sentence for sentence in sentences if sentence and not RISKY_CLAIM.search(sentence)]
    excerpt = " ".join(safe[:2]).strip()
    if not excerpt:
        excerpt = f"{title} – eine abwechslungsreiche Rezeptidee für den genussvollen Alltag."
    if len(excerpt) > 280:
        excerpt = excerpt[:279].rsplit(" ", 1)[0] + "…"
    return excerpt


def pin_description(title: str, description: str, book_title: str) -> str:
    cleaned = re.sub(r"\s+", " ", description).strip()
    suffix = f" Entdecke dieses Rezept und 139 weitere Ideen in ‚{book_title}‘ von Leo Bergmann."
    maximum = 500 - len(suffix)
    if len(cleaned) > maximum:
        cleaned = cleaned[: maximum - 1].rsplit(" ", 1)[0] + "…"
    return (cleaned + suffix)[:500]


def benefit(book: dict[str, Any], nutrition: dict[str, Any]) -> str:
    cook = value(nutrition, "cookTime")
    if cook and cook not in {"–", "-"}:
        return f"{book['promise']} • {cook}"
    return book["promise"]


def image_is_valid(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            return image.size == IMAGE_SIZE and image.format == "JPEG" and path.stat().st_size >= 25_000
    except (OSError, ValueError):
        return False


def prepare(*, limit: int | None = None, force: bool = False, validate_only: bool = False) -> dict[str, int]:
    previous = read_json(CATALOG_FILE, {"items": []})
    previous_by_id = {entry["catalog_id"]: entry for entry in previous.get("items", [])}
    content = read_json(CONTENT_FILE, [])
    existing_content = {f"002_airfryer:{item['id']}": item for item in content if str(item.get("id", "")).startswith("recipe_")}
    now = datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []
    counts = {"total": 0, "ready": 0, "blocked": 0, "rendered": 0, "reused": 0}
    render_budget = limit

    book_rows: list[dict[str, Any]] = []
    for book_id, book in BOOKS.items():
        target, target_kind = amazon_url(book)
        book_rows.append({
            "id": book_id,
            "title": book["title"],
            "label": book["label"],
            "promise": book["promise"],
            "published": book["published"],
            "amazon_url": target,
            "target_kind": target_kind,
            "recipe_count": 140,
        })
        source_root = SOURCE_LIBRARY / book_id
        recipe_root = source_root / "german" / "book_src" / "recipes"
        image_root = source_root / "images" / "recipes"
        recipe_paths = sorted(recipe_root.rglob("recipe_*.json"))
        if len(recipe_paths) != 140:
            raise RuntimeError(f"{book_id}: expected 140 German recipes, found {len(recipe_paths)}")

        for recipe_path in recipe_paths:
            recipe = read_json(recipe_path, {})
            recipe_id = recipe_path.stem
            catalog_id = f"{book_id}:{recipe_id}"
            title = re.sub(r"\s+", " ", str(recipe.get("title", ""))).strip()
            raw_description = re.sub(r"\s+", " ", str(recipe.get("description", ""))).strip()
            description = safe_excerpt(title, raw_description)
            if not title or not raw_description:
                raise RuntimeError(f"{catalog_id}: missing title or description")
            nutrition = recipe.get("nutrition", {})
            image_path = image_root / f"{recipe_id}.png"
            output_rel = f"assets/pins/{book_id}/{recipe_id}.jpg"
            output_path = ROOT / "docs" / output_rel
            fingerprint = source_fingerprint(recipe_path, image_path if image_path.exists() else None)
            old = previous_by_id.get(catalog_id, {})
            asset_status = "blocked_missing_asset"

            may_render = render_budget is None or render_budget > 0
            needs_render = force or not image_is_valid(output_path) or (bool(old) and old.get("source_fingerprint") != fingerprint)
            if image_path.exists():
                if validate_only:
                    asset_status = "ready" if image_is_valid(output_path) else "pending_render"
                elif needs_render and may_render:
                    render_creative(
                        image_path,
                        output_path,
                        split_headline(title),
                        benefit(book, nutrition),
                        label=book["label"],
                        cta="140 REZEPTE ENTDECKEN",
                        accent="LEO BERGMANN",
                    )
                    asset_status = "ready"
                    counts["rendered"] += 1
                    if render_budget is not None:
                        render_budget -= 1
                elif image_is_valid(output_path):
                    asset_status = "ready"
                    counts["reused"] += 1
                else:
                    asset_status = "pending_render"

            publication_status = old.get("publication_status", "available")
            scheduled_at = old.get("scheduled_at")
            pin_url = old.get("pin_url")
            if catalog_id in existing_content:
                publication_status = "scheduled"
                scheduled_at = existing_content[catalog_id].get("publish_at")
            if not book["published"]:
                publication_status = "unpublished"
                scheduled_at = None
                pin_url = None

            entry = {
                "catalog_id": catalog_id,
                "book_id": book_id,
                "source_recipe_id": recipe_id,
                "category": recipe_path.parent.name,
                "title": title,
                "description": description,
                "pin_title": title[:100],
                "pin_description": pin_description(title, description, book["title"]),
                "prep": value(nutrition, "prepTime"),
                "cook": value(nutrition, "cookTime"),
                "servings": value(nutrition, "servings"),
                "difficulty": value(nutrition, "difficulty"),
                "image": output_rel,
                "asset_status": asset_status,
                "publication_status": publication_status,
                "scheduled_at": scheduled_at,
                "pin_url": pin_url,
                "source_fingerprint": fingerprint,
                "creative_version": CREATIVE_VERSION,
            }
            items.append(entry)
            counts["total"] += 1
            counts["ready" if asset_status == "ready" else "blocked"] += 1

    if counts["total"] != len(BOOKS) * 140:
        raise RuntimeError(f"Catalog count mismatch: {counts['total']}")

    item_by_catalog_id = {item["catalog_id"]: item for item in items}
    book_by_id = {book["id"]: book for book in book_rows}
    for item in content:
        if str(item.get("id", "")).startswith("recipe_"):
            item.setdefault("book_id", "002_airfryer")
            item.setdefault("catalog_id", f"002_airfryer:{item['id']}")
        catalog_item = item_by_catalog_id.get(item.get("catalog_id"))
        if catalog_item and str(item.get("image", "")).startswith("assets/pins/"):
            item.update({
                "title": catalog_item["pin_title"],
                "description": catalog_item["pin_description"],
                "image": catalog_item["image"],
                "book_id": catalog_item["book_id"],
                "amazon_url": book_by_id[catalog_item["book_id"]]["amazon_url"],
            })

    payload = {
        "schema_version": 2,
        "creative_version": CREATIVE_VERSION,
        "generated_at": now,
        "source_book_count": len(BOOKS),
        "item_count": len(items),
        "ready_count": sum(1 for item in items if item["asset_status"] == "ready"),
        "blocked_count": sum(1 for item in items if item["asset_status"] != "ready"),
        "available_count": sum(1 for item in items if item["asset_status"] == "ready" and item["publication_status"] == "available"),
        "items": sorted(items, key=lambda item: item["catalog_id"]),
    }
    previous_comparable = dict(previous)
    payload_comparable = dict(payload)
    previous_comparable["generated_at"] = None
    payload_comparable["generated_at"] = None
    if previous_comparable == payload_comparable and previous.get("generated_at"):
        payload["generated_at"] = previous["generated_at"]
    atomic_json(BOOKS_FILE, {"schema_version": 1, "books": book_rows})
    atomic_json(CATALOG_FILE, payload)
    atomic_json(CONTENT_FILE, content)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare all German recipe-book Pinterest creatives")
    parser.add_argument("--limit", type=int, help="Render at most this many missing/changed creatives")
    parser.add_argument("--force", action="store_true", help="Re-render existing creatives")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    counts = prepare(limit=args.limit, force=args.force, validate_only=args.validate_only)
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
