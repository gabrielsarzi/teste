// Gera um único arquivo HTML autocontido (CSS + JS embutidos).
//  dist/batida.html -> conteúdo para o Artifact (sem <!doctype>/<html>, o host envolve)
//  dist/index.html  -> documento completo (navegador local / Capacitor)
import * as esbuild from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const watch = process.argv.includes('--watch');

async function build() {
  const js = await esbuild.build({
    entryPoints: ['src/main.js'],
    bundle: true,
    minify: true,
    format: 'iife',
    target: ['es2020', 'safari14'],
    write: false,
  });
  const css = await esbuild.transform(readFileSync('src/fonts.css', 'utf8') + readFileSync('src/styles.css', 'utf8'), {
    loader: 'css',
    minify: true,
  });
  const code = js.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
  const head = readFileSync('src/head.html', 'utf8');
  const body = `${head}\n<style>${css.code}</style>\n<div id="app"></div>\n<script>${code}</script>\n`;

  mkdirSync('dist', { recursive: true });
  writeFileSync('dist/batida.html', body);
  writeFileSync(
    'dist/index.html',
    `<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, user-scalable=no">\n</head>\n<body>\n${body}</body>\n</html>\n`,
  );
  console.log(`build ok — ${(body.length / 1024).toFixed(1)} KB`);
}

await build();
if (watch) {
  const { watch: fsWatch } = await import('node:fs');
  let t;
  fsWatch('src', { recursive: true }, () => {
    clearTimeout(t);
    t = setTimeout(() => build().catch((e) => console.error(e.message)), 80);
  });
}
