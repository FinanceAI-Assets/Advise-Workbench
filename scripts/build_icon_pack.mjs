// Build the deck icon pack: curated Lucide icons rendered to PNG for the PPTX renderer.
//
//   node scripts/build_icon_pack.mjs
//
// Reads icon geometry from frontend/node_modules/lucide-react (ISC licence) and rasterises
// each icon with sharp as black strokes on a transparent background. The Python renderer
// tints the alpha mask to any brand colour, so no SVG library (Cairo) is needed at render
// time. Output: src/deliverables/assets/icons/<name>.png and the Lucide licence.

import { createRequire } from "node:module";
import { copyFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const frontend = join(root, "frontend");
const require = createRequire(join(frontend, "package.json"));
const sharp = require("sharp");
const iconsDir = join(frontend, "node_modules", "lucide-react", "dist", "esm", "icons");
const outDir = join(root, "src", "deliverables", "assets", "icons");

// Deck icon name -> Lucide icon file. Names are what slides reference in `icon` fields.
const ICONS = {
  users: "users",
  user_check: "user-check",
  target: "target",
  shield_check: "shield-check",
  shield: "shield",
  bar_chart: "chart-column",
  line_chart: "chart-line",
  pie_chart: "chart-pie",
  dollar: "circle-dollar-sign",
  coins: "coins",
  savings: "piggy-bank",
  invoice: "receipt",
  clock: "clock",
  timer: "timer",
  hourglass: "hourglass",
  calendar: "calendar",
  gauge: "gauge",
  settings: "settings-2",
  cog: "cog",
  wrench: "wrench",
  database: "database",
  server: "server",
  cloud: "cloud",
  cpu: "cpu",
  ai: "brain",
  bot: "bot",
  sparkles: "sparkles",
  workflow: "workflow",
  network: "network",
  branch: "git-branch",
  layers: "layers",
  refresh: "refresh-cw",
  repeat: "repeat",
  exchange: "arrow-right-left",
  lightbulb: "lightbulb",
  handshake: "handshake",
  globe: "globe",
  building: "building-2",
  bank: "landmark",
  factory: "factory",
  truck: "truck",
  package: "package",
  document: "file-text",
  document_search: "file-search",
  check: "circle-check",
  checklist: "list-checks",
  clipboard: "clipboard-check",
  alert: "triangle-alert",
  trend_up: "trending-up",
  trend_down: "trending-down",
  lock: "lock",
  zap: "zap",
  rocket: "rocket",
  flag: "flag",
  search: "search",
  scan: "scan-search",
  route: "route",
  milestone: "milestone",
  map: "map",
  bell: "bell",
  eye: "eye",
  scale: "scale",
  award: "award",
  message: "message-square",
  presentation: "presentation",
  pill: "pill",
  health: "heart-pulse",
  activity: "activity",
  stethoscope: "stethoscope",
  lab: "flask-conical",
  microscope: "microscope",
  briefcase: "briefcase",
  sliders: "sliders-horizontal",
  leaf: "leaf",
};

const SIZE = 192;

function toSvg(node) {
  const attrs = (props) =>
    Object.entries(props)
      .filter(([key]) => key !== "key")
      .map(([key, value]) => `${key}="${value}"`)
      .join(" ");
  const body = node.map(([tag, props]) => `<${tag} ${attrs(props)}/>`).join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 24 24" ` +
    `fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`
  );
}

mkdirSync(outDir, { recursive: true });
let built = 0;
for (const [name, file] of Object.entries(ICONS)) {
  const mod = await import(pathToFileURL(join(iconsDir, `${file}.js`)).href);
  const png = await sharp(Buffer.from(toSvg(mod.__iconNode))).png().toBuffer();
  writeFileSync(join(outDir, `${name}.png`), png);
  built += 1;
}
copyFileSync(join(frontend, "node_modules", "lucide-react", "LICENSE"), join(outDir, "LICENSE.lucide.txt"));
writeFileSync(
  join(outDir, "README.md"),
  "Deck icons rendered from Lucide (https://lucide.dev, ISC licence, see LICENSE.lucide.txt).\n" +
    "Regenerate with `node scripts/build_icon_pack.mjs`. Black strokes on transparent; the renderer tints them.\n"
);
console.log(`Built ${built} icons into ${outDir}`);
