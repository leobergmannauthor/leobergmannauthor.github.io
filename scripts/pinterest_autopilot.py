"""Local zero-budget Pinterest RSS autopilot for Leo Bergmann.

The tool keeps a rolling schedule of distinct Airfryer recipe teasers, renders
branded Pinterest images, validates the public site, and publishes the changes
through the existing GitHub/Pinterest RSS connection.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, time as daytime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETING_ROOT = REPO_ROOT.parent
CONTENT_FILE = REPO_ROOT / "content" / "recipes.json"
HISTORY_FILE = REPO_ROOT / "data" / "publication_history.json"
CREATIVE_FILE = REPO_ROOT / "data" / "pin_creatives.json"
SETTINGS_FILE = MARKETING_ROOT / "config" / "settings.json"
RUN_LOG_FILE = MARKETING_ROOT / "data" / "run_log.json"
STATUS_FILE = MARKETING_ROOT / "data" / "pinterest_autopilot_status.json"
SOURCE_ROOT = Path(
    os.environ.get(
        "BOOKGENPY_AIRFRYER_ROOT",
        r"C:\Daten\src\python\BookGenPy\library\002_airfryer",
    )
)
RECIPE_ROOT = SOURCE_ROOT / "german" / "book_src" / "recipes"
SOURCE_IMAGE_ROOT = SOURCE_ROOT / "images" / "recipes"
ASSET_DIR = REPO_ROOT / "assets" / "recipes"
PUBLIC_BASE = "https://leobergmannauthor.github.io"
BERLIN = ZoneInfo("Europe/Berlin")
IMAGE_SIZE = (1000, 1500)

CATEGORY_BENEFITS = {
    "vegetables": "vegetarisch · knusprig · unkompliziert",
    "meat": "saftig · würzig · familienfreundlich",
    "fish": "saftig · aromatisch · unkompliziert",
    "snacks": "knusprig · würzig · perfekt zum Teilen",
    "sides": "goldbraun · knusprig · unkompliziert",
    "desserts": "süß · goldbraun · einfach",
}

KEYWORD_SCORES = {
    "mozzarella": 16,
    "pizza": 15,
    "nuggets": 15,
    "burger": 14,
    "churros": 14,
    "brownie": 14,
    "zimtschnecken": 14,
    "garnelen": 13,
    "parmesan": 12,
    "bbq": 12,
    "knoblauch": 11,
    "schokolade": 11,
    "käse": 10,
    "knusprig": 9,
    "sticks": 8,
}

STOP_WORDS = {
    "mit",
    "und",
    "aus",
    "dem",
    "der",
    "die",
    "das",
    "im",
    "in",
    "am",
    "an",
    "klassisch",
    "selbstgemacht",
    "knusprig",
    "schnell",
    "einfach",
    "würzig",
}


class AutopilotError(RuntimeError):
    """Expected user-facing failure."""


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run(command: list[str], cwd: Path = REPO_ROOT) -> str:
    printable = " ".join(command)
    print(f"> {printable}")
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.returncode:
        raise AutopilotError(
            f"Befehl fehlgeschlagen ({completed.returncode}): {printable}"
        )
    return completed.stdout


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def meaningful_words(value: str) -> set[str]:
    return {
        word
        for word in normalize(value).split()
        if len(word) >= 5 and word not in STOP_WORDS
    }


def is_duplicate_title(title: str, existing_titles: list[str]) -> bool:
    normalized = normalize(title)
    words = meaningful_words(title)
    for existing in existing_titles:
        existing_normalized = normalize(existing)
        if normalized == existing_normalized:
            return True
        overlap = words & meaningful_words(existing)
        if overlap and len(overlap) >= min(2, max(1, len(words))):
            return True
        if any(len(word) >= 7 and word in existing_normalized for word in words):
            return True
    return False


def recipe_number(content_id: str) -> int:
    return int(content_id.split("_", 1)[1])


def category_for_id(content_id: str) -> str:
    number = recipe_number(content_id)
    if number <= 24:
        return "vegetables"
    if number <= 58:
        return "meat"
    if number <= 78:
        return "fish"
    if number <= 104:
        return "snacks"
    if number <= 124:
        return "sides"
    return "desserts"


def recipe_score(recipe: dict[str, Any]) -> int:
    searchable = normalize(f"{recipe['title']} {recipe.get('description', '')}")
    score = sum(points for keyword, points in KEYWORD_SCORES.items() if normalize(keyword) in searchable)
    score += max(0, 8 - abs(12 - recipe.get("cook_minutes", 15)))
    return score


def parse_minutes(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group()) if match else None


def load_source_recipes(existing_titles: list[str]) -> list[dict[str, Any]]:
    if not RECIPE_ROOT.exists() or not SOURCE_IMAGE_ROOT.exists():
        raise AutopilotError(f"Airfryer-Quellen fehlen: {SOURCE_ROOT}")

    recipes: list[dict[str, Any]] = []
    for source in sorted(RECIPE_ROOT.rglob("recipe_*.json")):
        content_id = source.stem
        image = SOURCE_IMAGE_ROOT / f"{content_id}.png"
        if not image.exists():
            continue
        payload = read_json(source, {})
        title = str(payload.get("title", "")).strip()
        if not title or is_duplicate_title(title, existing_titles):
            continue
        nutrition = payload.get("nutrition", {})
        cook = str(nutrition.get("cookTime", {}).get("value", ""))
        recipes.append(
            {
                "id": content_id,
                "title": title,
                "description": str(payload.get("description", "")).strip().replace(" - ", " – "),
                "prep": str(nutrition.get("prepTime", {}).get("value", "")),
                "cook": cook,
                "cook_minutes": parse_minutes(cook),
                "servings": str(nutrition.get("servings", {}).get("value", "")),
                "difficulty": str(nutrition.get("difficulty", {}).get("value", "")),
                "category": source.parent.name,
                "source_image": image,
            }
        )
    return recipes


def choose_recipes(
    candidates: list[dict[str, Any]],
    count: int,
    existing_category_counts: Counter[str],
) -> list[dict[str, Any]]:
    remaining = list(candidates)
    selected: list[dict[str, Any]] = []
    counts = existing_category_counts.copy()
    while remaining and len(selected) < count:
        remaining.sort(
            key=lambda recipe: (
                recipe_score(recipe) - counts[recipe["category"]] * 7,
                recipe_score(recipe),
                -recipe_number(recipe["id"]),
            ),
            reverse=True,
        )
        winner = remaining.pop(0)
        selected.append(winner)
        counts[winner["category"]] += 1
    return selected


def future_dates(
    existing_items: list[dict[str, Any]],
    target_days: int,
    max_new: int,
    now: datetime,
    publish_hour: int,
) -> list[datetime]:
    today = now.astimezone(BERLIN).date()
    desired_last_date = today + timedelta(days=target_days)
    scheduled = [
        datetime.fromisoformat(item["publish_at"].replace("Z", "+00:00")).astimezone(BERLIN)
        for item in existing_items
        if item.get("id") != "airfryer-kochbuch" and item.get("publish_at")
    ]
    latest_date = max((value.date() for value in scheduled), default=today)
    next_date = max(today + timedelta(days=1), latest_date + timedelta(days=1))
    dates: list[datetime] = []
    while next_date <= desired_last_date and len(dates) < max_new:
        dates.append(datetime.combine(next_date, daytime(publish_hour), BERLIN))
        next_date += timedelta(days=1)
    return dates


def split_headline(title: str) -> list[str]:
    cleaned = re.sub(
        r"\b(im Airfryer|selbstgemacht|klassisch|vegetarisch)\b",
        "",
        title,
        flags=re.IGNORECASE,
    )
    words = cleaned.upper().replace("  ", " ").strip().split()
    if not words:
        words = title.upper().split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > 22 and len(lines) < 2:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 3:
        lines = lines[:3]
    if len(lines[-1]) > 27:
        lines[-1] = lines[-1][:26].rstrip() + "…"
    return lines


def benefit_for(recipe: dict[str, Any]) -> str:
    base = CATEGORY_BENEFITS.get(recipe["category"], "aromatisch · einfach · alltagstauglich")
    minutes = recipe.get("cook_minutes")
    if minutes and minutes <= 12:
        first_two = base.split(" · ")[:2]
        return " · ".join([*first_two, f"{minutes} Min. Garzeit"])
    return base


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf"]
        if bold
        else [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "seguisb.ttf"]
    )
    candidates.extend(
        [
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fitted_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, minimum: int) -> ImageFont.FreeTypeFont:
    size = start
    while size > minimum:
        candidate = font(size, bold=True)
        if draw.textbbox((0, 0), text, font=candidate)[2] <= max_width:
            return candidate
        size -= 2
    return font(minimum, bold=True)


def vertical_gradient(size: tuple[int, int], top_alpha: int, bottom_alpha: int) -> Image.Image:
    width, height = size
    strip = Image.new("RGBA", (1, height))
    pixels = strip.load()
    for y in range(height):
        alpha = round(top_alpha + (bottom_alpha - top_alpha) * (y / max(1, height - 1)))
        pixels[0, y] = (16, 40, 31, alpha)
    return strip.resize((width, height))


def render_creative(
    source: Path,
    destination: Path,
    headline_lines: list[str],
    benefit: str,
    *,
    label: str = "AIRFRYER-REZEPT",
    cta: str = "140 REZEPTE ENTDECKEN",
    accent: str = "LEO BERGMANN",
) -> None:
    with Image.open(source) as source_image:
        image = ImageOps.fit(
            source_image.convert("RGB"),
            IMAGE_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.48),
        ).convert("RGBA")

    image.alpha_composite(vertical_gradient((IMAGE_SIZE[0], 575), 250, 0), (0, 0))
    image.alpha_composite(vertical_gradient((IMAGE_SIZE[0], 420), 0, 248), (0, IMAGE_SIZE[1] - 420))
    draw = ImageDraw.Draw(image)
    gold = "#f2b84b"
    forest = "#10281f"
    cream = "#fffaf0"

    draw.rounded_rectangle((64, 58, 470, 116), radius=29, fill=gold)
    category_font = fitted_font(draw, label.upper(), 360, 26, 18)
    label_box = draw.textbbox((0, 0), label.upper(), font=category_font)
    draw.text((267 - (label_box[2] - label_box[0]) / 2, 73), label.upper(), font=category_font, fill=forest)

    longest = max(headline_lines, key=len)
    headline_font = fitted_font(draw, longest, 872, 76, 48)
    line_height = headline_font.size + 12
    y = 154
    for line in headline_lines:
        draw.text((64, y), line, font=headline_font, fill=cream, stroke_width=1, stroke_fill=forest)
        y += line_height

    benefit_font = fitted_font(draw, benefit, 872, 33, 23)
    draw.text((64, y + 18), benefit, font=benefit_font, fill=cream)

    draw.rounded_rectangle((64, 1326, 590, 1418), radius=46, fill=gold)
    cta_font = fitted_font(draw, cta, 470, 29, 20)
    cta_box = draw.textbbox((0, 0), cta, font=cta_font)
    draw.text((327 - (cta_box[2] - cta_box[0]) / 2, 1355), cta, font=cta_font, fill=forest)

    author_font = font(23, bold=True)
    author_box = draw.textbbox((0, 0), accent, font=author_font)
    draw.text((936 - (author_box[2] - author_box[0]), 1442), accent, font=author_font, fill=cream)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(destination, "JPEG", quality=84, optimize=True, progressive=True, subsampling=2)

def ensure_zero_budget() -> None:
    settings = read_json(SETTINGS_FILE, {})
    if settings.get("daily_budget_eur") != 0 or settings.get("paid_channels_enabled"):
        raise AutopilotError("Abbruch: Der 0-EUR-Sicherheits-Lock ist nicht aktiv.")


def git_is_clean() -> bool:
    return not run(["git", "status", "--porcelain"]).strip()


def prepare_items(
    target_days: int,
    max_new: int,
    publish_hour: int,
    now: datetime,
    dry_run: bool,
) -> list[dict[str, Any]]:
    items = read_json(CONTENT_FILE, [])
    existing_ids = {item["id"] for item in items}
    run_log = read_json(RUN_LOG_FILE, {"events": []})
    existing_titles = [str(item.get("title", "")) for item in items]
    existing_titles.extend(str(event.get("title", "")) for event in run_log.get("events", []))

    dates = future_dates(items, target_days, max_new, now, publish_hour)
    if not dates:
        print(f"Der Veröffentlichungsplan reicht bereits mindestens {target_days} Tage voraus.")
        return []

    candidates = [
        recipe
        for recipe in load_source_recipes(existing_titles)
        if recipe["id"] not in existing_ids
    ]
    future_counts = Counter(
        category_for_id(item["id"])
        for item in items
        if item.get("id", "").startswith("recipe_")
        and datetime.fromisoformat(item["publish_at"].replace("Z", "+00:00")) > now
    )
    selected = choose_recipes(candidates, len(dates), future_counts)
    if len(selected) < len(dates):
        raise AutopilotError("Nicht genügend neue, eindeutige Airfryer-Rezepte verfügbar.")

    planned: list[dict[str, Any]] = []
    for recipe, scheduled_local in zip(selected, dates, strict=True):
        scheduled_utc = scheduled_local.astimezone(timezone.utc)
        planned.append(
            {
                "id": recipe["id"],
                "title": recipe["title"],
                "description": recipe["description"],
                "prep": recipe["prep"],
                "cook": recipe["cook"],
                "servings": recipe["servings"],
                "difficulty": recipe["difficulty"],
                "image": f"assets/recipes/{recipe['id']}-pin.jpg",
                "publish_at": scheduled_utc.isoformat().replace("+00:00", "Z"),
                "_source_image": recipe["source_image"],
                "_category": recipe["category"],
                "_headline_lines": split_headline(recipe["title"]),
                "_benefit": benefit_for(recipe),
            }
        )

    for item in planned:
        print(
            f"NEU: {item['publish_at']} | {item['title']} | "
            f"{' / '.join(item['_headline_lines'])} | {item['_benefit']}"
        )

    if dry_run:
        return planned

    manifest = read_json(CREATIVE_FILE, {"version": 1, "items": []})
    manifest_by_id = {entry["content_id"]: entry for entry in manifest.get("items", [])}
    for item in planned:
        content_id = item["id"]
        source_destination = ASSET_DIR / f"{content_id}.png"
        output_destination = ASSET_DIR / f"{content_id}-pin.jpg"
        shutil.copy2(item["_source_image"], source_destination)
        render_creative(
            source_destination,
            output_destination,
            item["_headline_lines"],
            item["_benefit"],
        )
        manifest_by_id[content_id] = {
            "content_id": content_id,
            "source_image": f"assets/recipes/{content_id}.png",
            "output_image": f"assets/recipes/{content_id}-pin.jpg",
            "headline_lines": item["_headline_lines"],
            "benefit": item["_benefit"],
            "template": "airfryer_v1",
        }
        public_item = {key: value for key, value in item.items() if not key.startswith("_")}
        items.append(public_item)

    manifest["items"] = sorted(manifest_by_id.values(), key=lambda entry: entry["content_id"])
    write_json(CREATIVE_FILE, manifest)
    write_json(CONTENT_FILE, items)
    return planned


def verify_local_output(planned: list[dict[str, Any]]) -> None:
    docs = REPO_ROOT / "docs"
    for item in planned:
        image = docs / "assets" / "recipes" / f"{item['id']}-pin.jpg"
        if not image.exists() or image.stat().st_size < 20_000:
            raise AutopilotError(f"Generiertes Pinterest-Bild fehlt oder ist zu klein: {image}")
        with Image.open(image) as rendered:
            if rendered.size != IMAGE_SIZE:
                raise AutopilotError(f"Falsche Bildgröße für {item['id']}: {rendered.size}")


def commit_and_push(planned: list[dict[str, Any]]) -> str | None:
    run(["git", "add", "--", "content", "data", "assets/recipes", "docs"])
    staged = run(["git", "diff", "--cached", "--name-only"]).strip()
    if not staged:
        print("Keine Repository-Änderungen zu veröffentlichen.")
        return None
    run(["git", "diff", "--cached", "--check"])
    message = (
        f"Add {len(planned)} Pinterest autopilot creatives"
        if planned
        else "Publish scheduled Pinterest RSS content"
    )
    run(["git", "commit", "-m", message])
    commit = run(["git", "rev-parse", "--short", "HEAD"]).strip()
    run(["git", "push", "origin", "main"])
    return commit


def verify_public_images(planned: list[dict[str, Any]], timeout_seconds: int = 120) -> list[str]:
    if not planned:
        return []
    urls = [f"{PUBLIC_BASE}/assets/recipes/{item['id']}-pin.jpg" for item in planned]
    deadline = time.monotonic() + timeout_seconds
    pending = set(urls)
    while pending and time.monotonic() < deadline:
        for url in list(pending):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Leo-Bergmann-Autopilot/1.0"})
                with urllib.request.urlopen(request, timeout=12) as response:
                    if response.status == 200 and response.headers.get_content_type() == "image/jpeg":
                        pending.remove(url)
            except (urllib.error.URLError, TimeoutError):
                pass
        if pending:
            time.sleep(5)
    if pending:
        print("Hinweis: GitHub Pages ist noch nicht vollständig aktualisiert:")
        for url in sorted(pending):
            print(f"  wartet auf Deployment: {url}")
    return [url for url in urls if url not in pending]


def write_status(
    *,
    status: str,
    started_at: datetime,
    planned: list[dict[str, Any]],
    commit: str | None = None,
    verified_urls: list[str] | None = None,
    error: str | None = None,
) -> None:
    previous = read_json(STATUS_FILE, {})
    current_items = [
        {
            "content_id": item["id"],
            "title": item["title"],
            "publish_at": item["publish_at"],
            "image_url": f"{PUBLIC_BASE}/assets/recipes/{item['id']}-pin.jpg",
        }
        for item in planned
    ]
    last_published_items = (
        current_items
        if status == "success" and current_items
        else previous.get("last_published_items", previous.get("new_items", []))
    )
    payload = {
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "new_items": current_items,
        "last_published_items": last_published_items,
        "commit": commit,
        "last_commit": commit or previous.get("last_commit", previous.get("commit")),
        "verified_image_urls": verified_urls or previous.get("verified_image_urls", []),
        "error": error,
        "cost_eur": 0,
    }
    write_json(STATUS_FILE, payload)


def execute(args: argparse.Namespace) -> int:
    started_at = datetime.now(timezone.utc)
    planned: list[dict[str, Any]] = []
    try:
        ensure_zero_budget()
        if not args.dry_run:
            if not git_is_clean():
                raise AutopilotError(
                    "Das Website-Repository enthält ungespeicherte Änderungen. "
                    "Bitte zuerst prüfen/committen; der Autopilot überschreibt nichts."
                )
            run(["git", "pull", "--ff-only", "origin", "main"])

        planned = prepare_items(
            target_days=args.target_days,
            max_new=args.max_new,
            publish_hour=args.publish_hour,
            now=started_at,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            print(f"Dry-Run erfolgreich: {len(planned)} neue Pins würden vorbereitet.")
            write_status(status="dry_run", started_at=started_at, planned=planned)
            return 0

        run([sys.executable, "publication_history.py", "sync"])
        run([sys.executable, "build.py"])
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        verify_local_output(planned)
        commit = None if args.no_push else commit_and_push(planned)
        verified = [] if args.no_push else verify_public_images(planned, args.deploy_timeout)
        write_status(
            status="success",
            started_at=started_at,
            planned=planned,
            commit=commit,
            verified_urls=verified,
        )
        print()
        print(f"ERFOLG: {len(planned)} neue Pinterest-Creatives, Kosten 0 EUR.")
        if commit:
            print(f"GitHub-Commit: {commit}")
        print("Pinterest übernimmt fällige Einträge über den verbundenen RSS-Feed.")
        return 0
    except (AutopilotError, OSError, ValueError) as error:
        write_status(
            status="failed",
            started_at=started_at,
            planned=planned,
            error=str(error),
        )
        print(f"\nFEHLER: {error}", file=sys.stderr)
        return 1


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Pinterest RSS Autopilot (0 EUR)")
    result.add_argument("--target-days", type=int, default=14)
    result.add_argument("--max-new", type=int, default=7)
    result.add_argument("--publish-hour", type=int, default=9)
    result.add_argument("--deploy-timeout", type=int, default=120)
    result.add_argument("--dry-run", action="store_true")
    result.add_argument("--no-push", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    if args.target_days < 1 or args.max_new < 1 or not 0 <= args.publish_hour <= 23:
        parser().error("Ungültige Planungseinstellungen.")
    raise SystemExit(execute(args))


if __name__ == "__main__":
    main()
