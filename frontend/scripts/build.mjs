import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { build, transform } from "esbuild";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "build");
const buildAssets = path.join(outDir, "assets", "build");

const readSource = async (file) =>
  (await readFile(file, "utf8")).replace(/\r\n/g, "\n");

const PAGES_CONFIG = JSON.parse(
  await readFile(path.join(root, "pages.config.json"), "utf8")
);
const HEAD_PARTIAL = await readSource(path.join(root, "partials", "head.html"));
const SIDEBAR_PARTIAL = await readSource(path.join(root, "partials", "sidebar.html"));
const THEME_BOOT = (
  await transform(await readSource(path.join(root, "js", "core", "theme-boot.js")), {
    loader: "js",
    minify: true,
  })
).code.trim();
const scriptHashes = new Set([
  `'sha256-${createHash("sha256").update(THEME_BOOT).digest("base64")}'`,
]);
const PAGES = Object.keys(PAGES_CONFIG);

const SIDEBAR_ALIASES = {
  "truck-detail.html": "trucks",
  "route-detail.html": "routes",
};

function renderHead(meta) {
  const description = meta.description
    ? `  <meta name="description" content="${meta.description}" />\n`
    : "";
  const styles = meta.styles
    .map((href) => `  <link rel="stylesheet" href="${href}" />`)
    .join("\n");
  return HEAD_PARTIAL.replace("{{title}}", meta.title)
    .replace("{{description}}\n", description)
    .replace("{{styles}}", styles)
    .trim();
}

function renderSidebar(page) {
  const active = SIDEBAR_ALIASES[page] || page.replace(/\.html$/, "");
  return SIDEBAR_PARTIAL.replace(
    new RegExp(`class="nav-link"([^>]*?data-nav="${active}")`),
    'class="nav-link is-active"$1 aria-current="page"'
  ).trim();
}

function hashedName(name, content) {
  const hash = createHash("sha256").update(content).digest("hex").slice(0, 8);
  const extension = path.extname(name);
  const base = path.basename(name, extension);
  return `${base}.${hash}${extension}`;
}

function rewriteCssUrls(file, css) {
  return css.replace(/url\((['"]?)([^)'"]+)\1\)/g, (match, quote, url) => {
    if (/^(?:[a-z][a-z0-9+.-]*:|\/|#)/i.test(url)) return match;
    const [pathname, suffix = ""] = url.split(/(?=[?#])/);
    const target = path.posix.normalize(
      path.posix.join(path.posix.dirname(file.replace(/\\/g, "/")), pathname)
    );
    const relative = path.posix.relative("assets/build", target);
    return `url(${quote}${relative}${suffix}${quote})`;
  });
}

async function minifyCss(files) {
  const chunks = [];
  for (const file of files) {
    const css = await readFile(path.join(root, file), "utf8");
    chunks.push(rewriteCssUrls(file, css));
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
    path.join(root, "assets", "logo-160.png"),
    path.join(outDir, "assets", "logo-160.png")
  );
  await cp(
    path.join(root, "assets", "favicon-32.png"),
    path.join(outDir, "assets", "favicon-32.png")
  );
  await cp(
    path.join(root, "assets", "apple-touch-icon.png"),
    path.join(outDir, "assets", "apple-touch-icon.png")
  );

  const manifest = {};

  for (const page of PAGES) {
    const htmlPath = path.join(root, page);
    let html = await readSource(htmlPath);
    const meta = PAGES_CONFIG[page];

    if (!meta) throw new Error(`Falta metadata para ${page}`);
    if (!html.includes("<!-- @include head -->")) {
      throw new Error(`Falta el include de head en ${page}`);
    }
    html = html.replace("<!-- @include head -->", renderHead(meta));
    if (html.includes("<!-- @include sidebar -->")) {
      html = html.replace("<!-- @include sidebar -->", renderSidebar(page));
    }
    if (html.includes("<!-- @include ")) {
      throw new Error(`Include sin resolver en ${page}`);
    }

    const cssLinks = [
      ...html.matchAll(
        /<link rel="stylesheet" href="((?:css|assets\/vendors)\/[^"]+\.css)"\s*\/?>/g
      ),
    ];
    if (cssLinks.length) {
      const files = cssLinks.map((match) => match[1]);
      const code = await minifyCss(files);
      const name = hashedName(`${path.basename(page, ".html")}.css`, code);
      await writeFile(path.join(buildAssets, name), code, "utf8");
      manifest[files.join("+")] = `assets/build/${name}`;
      // Elimina la línea completa para no dejar líneas en blanco.
      html = html.replace(
        /^[ \t]*<link rel="stylesheet" href="(?:css|assets\/vendors)\/[^"]+\.css"[ \t]*\/?>\r?\n/gm,
        ""
      );
      html = html.replace(
        "</head>",
        `  <link rel="stylesheet" href="assets/build/${name}" />\n</head>`
      );
    }

    const themeScript = html.match(/<script src="js\/core\/theme-boot\.js"><\/script>/);
    if (themeScript) {
      html = html.replace(themeScript[0], () => `<script>${THEME_BOOT}</script>`);
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
  await writeFile(
    path.join(outDir, "csp.json"),
    `${JSON.stringify({ script_hashes: [...scriptHashes] }, null, 2)}\n`,
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
