#!/usr/bin/env node
/**
 * build/icon.svg → build/icon.ico (çok boyutlu) + build/icon.png (512) + electron/icon.png
 *
 * Neden resvg: sharp'ın aksine derleme gerektirmeyen hazır napi ikilisi ile gelir,
 * SVG'yi Windows simgesi için gereken küçük boyutlarda temiz rasterler.
 *
 * Kullanım:  node scripts/ikon.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Resvg } from '@resvg/resvg-js';
import * as pngToIcoModule from 'png-to-ico';

const pngToIco = pngToIcoModule.default ?? pngToIcoModule;

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(BURASI, '..');
const BUILD = path.join(APP, 'build');
const KAYNAK = path.join(BUILD, 'icon.svg');

/** ICO içine konacak boyutlar — 16/24/32/48 görev çubuğu ve gezgin, 256 büyük simge. */
const BOYUTLAR = [16, 24, 32, 48, 64, 128, 256];

function cizPng(svg, boyut) {
  const r = new Resvg(svg, {
    fitTo: { mode: 'width', value: boyut },
    background: 'rgba(0,0,0,0)',
    shapeRendering: 2, // geometricPrecision
    imageRendering: 0,
  });
  return r.render().asPng();
}

async function main() {
  if (!fs.existsSync(KAYNAK)) {
    console.error('build/icon.svg bulunamadı:', KAYNAK);
    process.exit(2);
  }
  const svg = fs.readFileSync(KAYNAK, 'utf8');
  fs.mkdirSync(BUILD, { recursive: true });

  const pngler = [];
  for (const b of BOYUTLAR) {
    const dosya = path.join(BUILD, `icon-${b}.png`);
    fs.writeFileSync(dosya, cizPng(svg, b));
    pngler.push(dosya);
    console.log(`  icon-${b}.png`, fs.statSync(dosya).size, 'B');
  }

  const ico = await pngToIco(pngler);
  const icoYol = path.join(BUILD, 'icon.ico');
  fs.writeFileSync(icoYol, ico);
  console.log('  icon.ico', (fs.statSync(icoYol).size / 1024).toFixed(1), 'KB', `(${BOYUTLAR.join('/')})`);

  // electron-builder Linux/mac için, BrowserWindow için ve favicon üretimi için 512'lik PNG
  const png512 = cizPng(svg, 512);
  fs.writeFileSync(path.join(BUILD, 'icon.png'), png512);
  fs.mkdirSync(path.join(APP, 'electron'), { recursive: true });
  fs.writeFileSync(path.join(APP, 'electron', 'icon.png'), png512);
  console.log('  icon.png + electron/icon.png', (png512.length / 1024).toFixed(1), 'KB');

  // index.html içindeki favicon'u 64 px data-URI olarak tazele (tek dosya HTML'de de çalışsın)
  const indexYol = path.join(APP, 'index.html');
  if (fs.existsSync(indexYol)) {
    const favicon = `data:image/png;base64,${cizPng(svg, 64).toString('base64')}`;
    const etiket = `<link rel="icon" type="image/png" href="${favicon}" />`;
    let html = fs.readFileSync(indexYol, 'utf8');
    if (/<link rel="icon"[^>]*>/.test(html)) html = html.replace(/<link rel="icon"[^>]*>/, etiket);
    else html = html.replace('</head>', `    ${etiket}\n  </head>`);
    fs.writeFileSync(indexYol, html);
    console.log('  index.html favicon güncellendi');
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
