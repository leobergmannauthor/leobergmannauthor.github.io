const fs = require("node:fs");
const path = require("node:path");
const sharp = require("sharp");

const ROOT = path.resolve(__dirname, "..");
const IMAGE_DIR = path.join(ROOT, "assets", "recipes");
const WIDTH = 896;
const HEIGHT = 1152;

const creatives = [
  ["recipe_003", ["BLUMENKOHL-WINGS"], "pikant · knusprig · vegetarisch"],
  ["recipe_012", ["GEFÜLLTE", "CHAMPIGNONS"], "cremig · würzig · 10 Min. Garzeit"],
  ["recipe_017", ["FETA & TOMATEN"], "mediterran · cremig · einfach"],
  ["recipe_024", ["PORTOBELLO-BURGER"], "saftig · vegetarisch · voller Aroma"],
  ["recipe_025", ["KNUSPRIGE", "HÄHNCHENKEULEN"], "würzig mariniert · familienfreundlich"],
  ["recipe_040", ["GYROS AUS DEM", "AIRFRYER"], "würzig · saftig · knusprige Ränder"],
  ["recipe_059", ["LACHS MIT", "DILLKRUSTE"], "butterzart · aromatisch · 12 Min. Garzeit"],
  ["recipe_064", ["KNUSPRIGE CALAMARI"], "goldbraun · mediterran · fettarm"],
  ["recipe_082", ["ASIATISCHE", "FRÜHLINGSROLLEN"], "knusprig · gemüsig · Airfryer leicht"],
  ["recipe_088", ["ORIENTALISCHE", "FALAFEL"], "außen kross · innen saftig"],
  ["recipe_092", ["ARGENTINISCHE", "EMPANADAS"], "herzhaft · würzig · perfekt zum Teilen"],
  ["recipe_117", ["YORKSHIRE PUDDING"], "luftig · goldbraun · britischer Klassiker"],
];

function escapeXml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function overlaySvg(headlineLines, benefit) {
  const headline = headlineLines
    .map(
      (line, index) =>
        `<tspan x="56" dy="${index === 0 ? 0 : 68}">${escapeXml(line)}</tspan>`,
    )
    .join("");
  const benefitY = headlineLines.length === 1 ? 234 : 302;

  return Buffer.from(`
    <svg width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="top" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#10281f" stop-opacity="0.96"/>
          <stop offset="0.72" stop-color="#10281f" stop-opacity="0.62"/>
          <stop offset="1" stop-color="#10281f" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="bottom" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#10281f" stop-opacity="0"/>
          <stop offset="0.48" stop-color="#10281f" stop-opacity="0.72"/>
          <stop offset="1" stop-color="#10281f" stop-opacity="0.96"/>
        </linearGradient>
      </defs>

      <rect width="896" height="410" fill="url(#top)"/>
      <rect y="865" width="896" height="287" fill="url(#bottom)"/>

      <rect x="56" y="46" width="264" height="42" rx="21" fill="#f2b84b"/>
      <text x="188" y="74" text-anchor="middle" fill="#10281f"
            font-family="Segoe UI, Arial, sans-serif" font-size="20" font-weight="800"
            letter-spacing="1.8">AIRFRYER-REZEPT</text>

      <text x="56" y="154" fill="#fffaf0"
            font-family="Segoe UI, Arial, sans-serif" font-size="58" font-weight="900"
            letter-spacing="-1.2">${headline}</text>

      <text x="56" y="${benefitY}" fill="#fffaf0"
            font-family="Segoe UI, Arial, sans-serif" font-size="27" font-weight="600">
        ${escapeXml(benefit)}
      </text>

      <rect x="56" y="1008" width="424" height="68" rx="34" fill="#f2b84b"/>
      <text x="268" y="1052" text-anchor="middle" fill="#10281f"
            font-family="Segoe UI, Arial, sans-serif" font-size="24" font-weight="800">
        140 Airfryer-Ideen entdecken
      </text>

      <text x="840" y="1102" text-anchor="end" fill="#fffaf0"
            font-family="Segoe UI, Arial, sans-serif" font-size="19" font-weight="700"
            letter-spacing="1.4">LEO BERGMANN</text>
    </svg>
  `);
}

async function render() {
  for (const [id, headlineLines, benefit] of creatives) {
    const source = path.join(IMAGE_DIR, `${id}.jpg`);
    const destination = path.join(IMAGE_DIR, `${id}-pin.jpg`);
    if (!fs.existsSync(source)) {
      throw new Error(`Missing source image: ${source}`);
    }

    await sharp(source)
      .resize(WIDTH, HEIGHT, { fit: "cover", position: "attention" })
      .composite([{ input: overlaySvg(headlineLines, benefit), top: 0, left: 0 }])
      .jpeg({ quality: 91, progressive: true, chromaSubsampling: "4:4:4" })
      .toFile(destination);

    process.stdout.write(`${path.basename(destination)}\n`);
  }
}

render().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
