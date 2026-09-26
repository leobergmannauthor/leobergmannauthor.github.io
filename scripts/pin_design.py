"""Food-first Pinterest art direction; deterministic variants for measurement."""
from __future__ import annotations
import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

VARIANTS = ("editorial", "photo", "bold")

@lru_cache(maxsize=180)
def face(size: int, serif: bool = False):
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    paths = ([win / "georgiab.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")]
             if serif else [win / "arialbd.ttf", Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")])
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("A scalable bold font is required for readable pins")

def variant_for(key: str) -> str:
    return VARIANTS[int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % len(VARIANTS)]

def headline_parts(title: str) -> tuple[str, str]:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\bLinsen Omelett\b", "Linsen-Omelett", title, flags=re.I)
    parts = re.split(r"\s+(?=(?:mit|auf|aus|in|an|ohne)\s)", title, maxsplit=1, flags=re.I)
    return parts[0], parts[1] if len(parts) > 1 else ""

def wrap(draw, text, width, max_height, start=110, minimum=48, serif=False):
    for size in range(start, minimum - 1, -2):
        f = face(size, serif)
        lines, line = [], ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if line and draw.textlength(candidate, font=f) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if len(lines) * (size + 7) <= max_height and all(draw.textlength(x, font=f) <= width for x in lines):
            return f, lines
    # Long German compounds can wrap at real hyphens, never lose characters.
    if "-" in text:
        return wrap(draw, text.replace("-", "- "), width, max_height, start, minimum, serif) if "- " not in text else _overflow(text)
    return _overflow(text)

def _overflow(text):
    raise ValueError(f"Headline needs editorial attention: {text}")

def draw_lines(draw, text, xy, width, height, fill, start=110, minimum=48, serif=False):
    f, lines = wrap(draw, text, width, height, start, minimum, serif)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=f, fill=fill, anchor="lt")
        y += f.size + 7
    return y

def recipe_hook(title: str, description: str) -> str:
    source = (title + " " + description).lower()
    words = [("knusprig", "Knusprig"), ("cremig", "Cremig"), ("saftig", "Saftig"),
             ("fruchtig", "Fruchtig"), ("würzig", "Würzig"), ("herzhaft", "Herzhaft"),
             ("eiweißreich", "Eiweißreich"), ("proteinreich", "Proteinreich")]
    found = [display for word, display in words if word in source][:2]
    return " & ".join(found)


def render_pin(source: Path, destination: Path, title: str, label: str, *, variant: str | None = None,
               hook: str = "", cook: str = "", author: str = "LEO BERGMANN"):
    variant = variant or variant_for(label + ":" + title)
    if variant not in VARIANTS:
        raise ValueError(variant)
    cream, ink, red, yellow = "#FFF7E9", "#192E26", "#C92F24", "#FFDF4F"
    image = Image.new("RGB", (1000,1500), cream)
    draw = ImageDraw.Draw(image)
    main, detail = headline_parts(title)
    # A short recipe name gets generous type; longer names retain all their words.
    def title_block(y, height=260, color=ink, serif=True):
        nonlocal draw
        detail_height = 112 if detail else 0
        main_height = height - detail_height - (8 if detail else 0)
        end = draw_lines(draw, main, (54,y), 892, main_height, color, start=112, minimum=48, serif=serif)
        if detail:
            draw_lines(draw, detail, (56,end+8), 888, detail_height, color, start=55, minimum=38)
    def photo(top,bottom):
        with Image.open(source) as original:
            fitted=ImageOps.fit(ImageOps.exif_transpose(original).convert("RGB"),(1000,bottom-top),method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
            image.paste(fitted,(0,top))
    category = "BEWUSSTE KÜCHE" if label == "LEBERFREUNDLICH" else label.replace("-REZEPT", "")
    if variant == "photo":
        photo(0,1125)
        draw.rounded_rectangle((42,42,958,132),radius=20,fill=red)
        draw_lines(draw, category, (70,65), 855, 55, cream, start=44, minimum=32)
        draw.rectangle((0,1065,1000,1500),fill=cream)
        title_block(1100,255)
        footer_y=1380
    elif variant == "bold":
        photo(310,1330)
        draw.rectangle((0,0,1000,325),fill=yellow)
        draw_lines(draw, category, (56,32), 888, 50, ink, start=36, minimum=30)
        title_block(96,215,serif=False)
        footer_y=1360
    else:
        photo(350,1330)
        draw.rectangle((0,0,1000,360),fill=cream)
        draw.text((56,30), category, font=face(36), fill=red, anchor="lt")
        title_block(90,260)
        footer_y=1360
    # A concise appetite cue is grounded in recipe copy; no health/performance claim.
    if hook and variant != "photo":
        draw.rounded_rectangle((40,388,960,473),radius=16,fill=red)
        draw_lines(draw,hook,(68,407),860,58,cream,start=46,minimum=36)
    # Cooking time is labelled explicitly and never sold as total preparation time.
    minutes = re.fullmatch(r"\s*([1-9]\d?)\s*(?:min|Min\.|Minuten)\s*", cook)
    if minutes and variant != "photo":
        cx,cy=852,1195
        draw.ellipse((cx-108,cy-108,cx+108,cy+108),fill=yellow)
        draw.text((cx,cy-66),minutes[1],font=face(80),fill=ink,anchor="mt")
        draw.text((cx,cy+18),"MIN",font=face(36),fill=ink,anchor="mt")
        draw.text((cx,cy+61),"GARZEIT",font=face(25),fill=ink,anchor="mt")
    draw.rectangle((0,footer_y,1000,1500),fill=red)
    draw.text((52,footer_y+22),"Mehr Ideen im Kochbuch",font=face(49),fill=cream,anchor="lt")
    draw.text((54,footer_y+86),author+"  /  140 REZEPTE",font=face(29),fill=cream,anchor="lt")
    draw.line((872,footer_y+52,941,footer_y+52),fill=cream,width=6)
    draw.line((919,footer_y+29,941,footer_y+52,919,footer_y+75),fill=cream,width=6)
    destination.parent.mkdir(parents=True,exist_ok=True)
    image.save(destination,"JPEG",quality=87,optimize=True,progressive=True)
