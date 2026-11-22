import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "css");

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await walk(full)));
    else if (entry.name.endsWith(".css")) files.push(full);
  }
  return files;
}

function selectors(text) {
  const clean = text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/@font-face\s*\{[^}]*\}/g, "");
  const found = [];
  for (const match of clean.matchAll(/([^{}]+)\{/g)) {
    const part = match[1].trim();
    if (part.startsWith("@") || /^(from|to|\d+%)$/.test(part)) continue;
    for (const selector of part.split(",")) {
      const normalized = selector.replace(/\s+/g, " ").trim();
      if (normalized && !/^(from|to|\d+%)$/.test(normalized)) found.push(normalized);
    }
  }
  return found;
}

const files = await walk(root);
const owners = new Map();
for (const file of files) {
  const relative = path.relative(path.join(root, ".."), file).replaceAll("\\", "/");
  for (const selector of new Set(selectors(await readFile(file, "utf8")))) {
    if (!owners.has(selector)) owners.set(selector, []);
    owners.get(selector).push(relative);
  }
}

const duplicates = [...owners.entries()].filter(([, list]) => list.length > 1);
if (duplicates.length) {
  for (const [selector, list] of duplicates) {
    console.error(`${selector} -> ${list.join(", ")}`);
  }
  console.error(`\n${duplicates.length} selector(es) duplicados entre archivos.`);
  process.exit(1);
}
console.log(
  `CSS OK: ${files.length} archivos sin selectores duplicados entre archivos.`
);
