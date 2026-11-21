import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "js");

const SAFE_CALLS = [
  "escapeHtml(",
  "formatDate",
  "formatTime",
  "formatDateTime",
  "formatTemp",
  "formatHum",
  "formatNumber",
  "formatPercent",
  "formatRange",
  "timeAgo(",
  "truncate(",
  "valueLabel(",
  "rangeLabel(",
];

const SAFE_PROPERTIES =
  /\.(length|id|year|order_index|count|total|page|page_size|label|icon|className)\b/;

const RISKY_DATA =
  /\b(truck|device|route|alert|point|admin|reading|setting|weather)\b/i;

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await walk(full)));
    else if (entry.name.endsWith(".js")) files.push(full);
  }
  return files;
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

function isSafe(expression) {
  if (SAFE_CALLS.some((call) => expression.includes(call))) return true;
  if (
    SAFE_PROPERTIES.test(expression) &&
    !/\.(name|plate|brand|model|description|address|username|email)\b/.test(expression)
  ) {
    return true;
  }
  // Ternarios que solo devuelven literales de clase o texto.
  if (/^[^?]+\?\s*"[^"]*"\s*:\s*"[^"]*"$/.test(expression.replace(/\s+/g, " "))) {
    return true;
  }
  if (!RISKY_DATA.test(expression)) return true;
  return false;
}

function checkTemplate(source, literal) {
  const problems = [];
  for (const match of literal.matchAll(/\$\{([^}]*)\}/g)) {
    const expression = match[1].trim();
    if (!expression) continue;
    if (!isSafe(expression)) problems.push(expression);
  }
  return problems;
}

const files = await walk(root);
let violations = 0;

for (const file of files) {
  const text = await readFile(file, "utf8");
  const pattern = /\.innerHTML\s*=\s*`([\s\S]*?)`/g;
  for (const match of text.matchAll(pattern)) {
    const problems = checkTemplate(text, match[1]);
    if (problems.length) {
      violations += problems.length;
      const relative = path.relative(path.join(root, ".."), file).replaceAll("\\", "/");
      console.error(
        `${relative}:${lineOf(text, match.index)} interpolación sin escape: ${problems.join(" | ")}`
      );
    }
  }
}

if (violations) {
  console.error(
    `\n${violations} interpolación(es) de innerHTML sin escape. Use escapeHtml() o un formateador.`
  );
  process.exit(1);
}
console.log(
  "innerHTML OK: todas las interpolaciones de datos usan escapeHtml o formateadores."
);
