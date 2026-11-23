import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { build, transform } from "esbuild";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "build");
const buildAssets = path.join(outDir, "assets", "build");

const PAGES = [
  "index.html",
  "login.html",
  "dashboard.html",
  "trucks.html",
  "truck-detail.html",
  "routes.html",
  "route-detail.html",
  "alerts.html",
  "settings.html",
  "driver.html",
  "drivers.html",
  "ai.html",
];

function hashedName(name, content) {
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 8);
  const extension = path.extname(name);
  const base = path.basename(name, extension);
  return `${base}.${hash}${extension}`;
}

async function minifyCss(files) {
  const chunks = [];
  for (const file of files) {
    chunks.push(await readFile(path.join(root, file), "utf8"));
  }
  const result = await transform(chunks.join("\n"), {
    loader: "css",
    minify: true,
  });
  return result.code;
}

async function bundleJs(entry) {
  const result = await build({
    entryPoints: [path.join(root, entry)],
    bundle: true,
    minify: true,
    format: "esm",
    target: ["es2022"],
    legalComments: "none",
    logLevel: "silent",
    write: false,
    outfile: path.join(buildAssets, path.basename(entry)),
  });
  return result.outputFiles[0].contents;
}

async function main() {
  await rm(outDir, { recursive: true, force: true });
  await mkdir(buildAssets, { recursive: true });

  await cp(path.join(root, "assets", "fonts"), path.join(outDir, "assets", "fonts"), {
    recursive: true,
  });
  await cp(
    path.join(root, "assets", "vendors"),
    path.join(outDir, "assets", "vendors"),
    { recursive: true }
  );
  await cp(
    path.join(root, "assets", "logo.png"),
    path.join(outDir, "assets", "logo.png")
  );

  const manifest = {};

  for (const page of PAGES) {
    const htmlPath = path.join(root, page);
    let html = await readFile(htmlPath, "utf8");

    const cssLinks = [
      ...html.matchAll(/<link rel="stylesheet" href="(css\/[^"]+)"\s*\/?>/g),
    ];
    if (cssLinks.length) {
      const files = cssLinks.map((match) => match[1]);
      const code = await minifyCss(files);
      const name = hashedName(`${path.basename(page, ".html")}.css`, code);
      await writeFile(path.join(buildAssets, name), code, "utf8");
      manifest[files.join("+")] = `assets/build/${name}`;
      html = html.replace(/<link rel="stylesheet" href="css\/[^"]+"\s*\/?>/g, "");
      html = html.replace(
        "</head>",
        `  <link rel="stylesheet" href="assets/build/${name}" />\n</head>`
      );
    }

    const themeScript = html.match(/<script src="js\/core\/theme-boot\.js"><\/script>/);
    if (themeScript) {
      const source = await readFile(
        path.join(root, "js", "core", "theme-boot.js"),
        "utf8"
      );
      const result = await transform(source, { loader: "js", minify: true });
      const name = hashedName("theme-boot.js", result.code);
      await writeFile(path.join(buildAssets, name), result.code, "utf8");
      manifest["js/core/theme-boot.js"] = `assets/build/${name}`;
      html = html.replace(
        themeScript[0],
        `<script src="assets/build/${name}"></script>`
      );
    }

    const moduleScript = html.match(
      /<script type="module" src="(js\/[^"]+)"><\/script>/
    );
    if (moduleScript) {
      const code = await bundleJs(moduleScript[1]);
      const name = hashedName(path.basename(moduleScript[1]), code);
      await writeFile(path.join(buildAssets, name), code);
      manifest[moduleScript[1]] = `assets/build/${name}`;
      html = html.replace(
        moduleScript[0],
        `<script type="module" src="assets/build/${name}"></script>`
      );
    }

    await writeFile(path.join(outDir, page), html, "utf8");
  }

  await writeFile(
    path.join(outDir, "manifest.json"),
    JSON.stringify(manifest, null, 2),
    "utf8"
  );

  const buildFiles = await readdir(buildAssets);
  const total = buildFiles.reduce(async (accumulator, file) => {
    const size = (await readFile(path.join(buildAssets, file))).length;
    return (await accumulator) + size;
  }, Promise.resolve(0));
  console.log(
    `Build listo: ${buildFiles.length} assets, ${((await total) / 1024).toFixed(1)} KB`
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
