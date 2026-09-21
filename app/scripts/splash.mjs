#!/usr/bin/env node
/**
 * build/splash.bmp — taşınabilir exe kendini %TEMP%'e açarken görünen 600×300 görsel.
 *
 * Neden gerekli: portable exe ilk açılışta ~100 MB'ı diske açar, bu 5-15 sn sürer ve
 * o sırada ekranda HİÇBİR ŞEY olmaz. Patron "çalışmadı" diye ikinci kez tıklar.
 * Splash, "açılıyor…" diyerek o boşluğu doldurur.
 *
 * NSIS splash eklentisi sıkıştırılmamış BMP ister; resvg RGBA piksel verir,
 * biz de onu 24-bit alttan-üste BMP olarak yazarız.
 *
 * Kullanım:  node scripts/splash.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Resvg } from '@resvg/resvg-js';

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(BURASI, '..');
const BUILD = path.join(APP, 'build');
const GENISLIK = 600;
const YUKSEKLIK = 300;

const SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="${GENISLIK}" height="${YUKSEKLIK}" viewBox="0 0 ${GENISLIK} ${YUKSEKLIK}">
  <defs>
    <linearGradient id="zemin" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0A1630"/>
      <stop offset="0.55" stop-color="#050B1C"/>
      <stop offset="1" stop-color="#03060D"/>
    </linearGradient>
    <radialGradient id="hale" cx="0.18" cy="0.5" r="0.55">
      <stop offset="0" stop-color="#FFC400" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#FFC400" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="${GENISLIK}" height="${YUKSEKLIK}" fill="url(#zemin)"/>
  <rect width="${GENISLIK}" height="${YUKSEKLIK}" fill="url(#hale)"/>

  <!-- sol blokta 8 bölge dilimi + ofis iğnesi (icon.svg'nin küçük hâli) -->
  <g transform="translate(110 150) scale(0.215)">
    <g fill="none" stroke-width="42" stroke-linecap="round">
      <path d="M 0 -330 A 330 330 0 0 1 233 -233" stroke="#6EFF3D"/>
      <path d="M 249 -217 A 330 330 0 0 1 330 0"  stroke="#1FC7FF"/>
      <path d="M 330 22 A 330 330 0 0 1 233 233"  stroke="#FF3D8E"/>
      <path d="M 217 249 A 330 330 0 0 1 0 330"   stroke="#1FFFC7"/>
      <path d="M -22 330 A 330 330 0 0 1 -233 233" stroke="#5C77FF"/>
      <path d="M -249 217 A 330 330 0 0 1 -330 0" stroke="#F7A164"/>
      <path d="M -330 -22 A 330 330 0 0 1 -233 -233" stroke="#EA00FF"/>
      <path d="M -217 -249 A 330 330 0 0 1 -22 -330" stroke="#FF2E2E"/>
    </g>
    <g transform="translate(-512 -500)">
      <path d="M512 252c-90 0-163 73-163 163 0 114 140 277 155 293a10 10 0 0 0 15 0c15-16 155-179 155-293 0-90-73-163-163-163z" fill="#FFC400"/>
      <circle cx="512" cy="413" r="62" fill="#03060D"/>
    </g>
  </g>

  <!-- yazı bloğu -->
  <g font-family="Segoe UI, Inter, Arial, sans-serif">
    <text x="208" y="120" fill="#FFC400" font-size="15" font-weight="600" letter-spacing="3.2">DEHANET EÇM</text>
    <text x="208" y="163" fill="#FFFFFF" font-size="28" font-weight="700">Bursa Fiber</text>
    <text x="208" y="196" fill="#FFFFFF" font-size="28" font-weight="700">Satış Haritası</text>
    <text x="208" y="232" fill="#9FB2CE" font-size="16" font-weight="400">açılıyor…</text>
  </g>

  <!-- alt şerit -->
  <rect x="208" y="248" width="330" height="3" rx="1.5" fill="#12203C"/>
  <rect x="208" y="248" width="126" height="3" rx="1.5" fill="#FFC400"/>
</svg>`;

/** RGBA piksel dizisi → 24-bit sıkıştırmasız BMP (alttan üste, satırlar 4 bayta hizalı). */
function bmpYaz(rgba, w, h) {
  const satirBayt = w * 3;
  const dolgu = (4 - (satirBayt % 4)) % 4;
  const veriBoyu = (satirBayt + dolgu) * h;
  const basliklar = 14 + 40;
  const tampon = Buffer.alloc(basliklar + veriBoyu);

  // BITMAPFILEHEADER
  tampon.write('BM', 0, 'ascii');
  tampon.writeUInt32LE(basliklar + veriBoyu, 2);
  tampon.writeUInt32LE(basliklar, 10);
  // BITMAPINFOHEADER
  tampon.writeUInt32LE(40, 14);
  tampon.writeInt32LE(w, 18);
  tampon.writeInt32LE(h, 22); // pozitif ⇒ alttan üste
  tampon.writeUInt16LE(1, 26);
  tampon.writeUInt16LE(24, 28);
  tampon.writeUInt32LE(0, 30); // BI_RGB
  tampon.writeUInt32LE(veriBoyu, 34);
  tampon.writeInt32LE(2835, 38); // 72 dpi
  tampon.writeInt32LE(2835, 42);

  let o = basliklar;
  for (let y = h - 1; y >= 0; y--) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const a = rgba[i + 3] / 255;
      // opak siyah zemin üzerine alfa karıştır (BMP'de saydamlık yok)
      tampon[o++] = Math.round(rgba[i + 2] * a);
      tampon[o++] = Math.round(rgba[i + 1] * a);
      tampon[o++] = Math.round(rgba[i] * a);
    }
    o += dolgu;
  }
  return tampon;
}

function main() {
  const r = new Resvg(SVG, {
    fitTo: { mode: 'width', value: GENISLIK },
    background: '#03060D',
    font: { loadSystemFonts: true, defaultFontFamily: 'Segoe UI' },
    shapeRendering: 2,
  });
  const cizim = r.render();
  const rgba = cizim.pixels;
  if (!rgba || rgba.length !== cizim.width * cizim.height * 4) {
    throw new Error(`beklenmeyen piksel verisi: ${rgba && rgba.length}`);
  }
  fs.mkdirSync(BUILD, { recursive: true });

  const bmp = bmpYaz(rgba, cizim.width, cizim.height);
  const hedef = path.join(BUILD, 'splash.bmp');
  fs.writeFileSync(hedef, bmp);
  // gözle bakabilmek için PNG kopyası da bırakalım
  fs.writeFileSync(path.join(BUILD, 'splash.png'), cizim.asPng());
  console.log(`  splash.bmp ${cizim.width}×${cizim.height}`, (bmp.length / 1024).toFixed(1), 'KB');
}

main();
