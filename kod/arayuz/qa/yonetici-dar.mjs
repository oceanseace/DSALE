/**
 * QA — yönetici konsolunun dar ekranlardaki hâli.
 *
 *   node qa/yonetici-dar.mjs [adres]
 *
 * Tablet dikey (768x1024) ve telefon (390x844): sol menü üst şeride dönüşüyor mu,
 * haritayla tablo alt alta geçiyor mu, hiçbir şey yana taşıyor mu?
 */

import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const CIKIS = join(KOK, 'qa');
const ADRES = process.argv[2] ?? 'http://127.0.0.1:8123';

const CIHAZLAR = [
  { ad: 'tabletdikey', genislik: 768, yukseklik: 1024, dokunmatik: true },
  { ad: 'telefon', genislik: 390, yukseklik: 844, dokunmatik: true },
];

async function rakamlariBas(sayfa, rakamlar) {
  for (const r of rakamlar) {
    await sayfa.getByRole('button', { name: r, exact: true }).click();
    await sayfa.waitForTimeout(30);
  }
}

async function gez(tarayici, cihaz) {
  console.log(`\n${cihaz.ad} (${cihaz.genislik}x${cihaz.yukseklik})`);
  const baglam = await tarayici.newContext({
    viewport: { width: cihaz.genislik, height: cihaz.yukseklik },
    deviceScaleFactor: 1,
    isMobile: cihaz.dokunmatik,
    hasTouch: cihaz.dokunmatik,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  });
  const sayfa = await baglam.newPage();
  const hatalar = [];
  sayfa.on('pageerror', (h) => hatalar.push('sayfa: ' + h.message));

  await sayfa.goto(`${ADRES}/?sahte=0`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakamlariBas(sayfa, '5321110000');
  await sayfa.getByRole('button', { name: 'Devam' }).click();
  await sayfa.waitForTimeout(250);
  await rakamlariBas(sayfa, '2468');
  await sayfa.waitForTimeout(1800);

  const cek = async (ad, bekleme = 900) => {
    await sayfa.waitForTimeout(bekleme);
    const dosya = join(CIKIS, `${cihaz.ad}-${ad}.png`);
    await sayfa.screenshot({ path: dosya });
    console.log('  ✓', `qa/${cihaz.ad}-${ad}.png`);
  };

  await sayfa.goto(`${ADRES}/#/yonetici`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.satisci-kart', { timeout: 25000 });
  await cek('canli', 1400);

  await sayfa.goto(`${ADRES}/#/yonetici/kapsama`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.yon-manset', { timeout: 30000 });
  await cek('kapsama', 7000);

  await sayfa.goto(`${ADRES}/#/yonetici/atama`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.kisi-izgara', { timeout: 20000 });
  await cek('atama', 1200);

  await sayfa.goto(`${ADRES}/#/yonetici/ekip`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('table.yon-tablo', { timeout: 20000 });
  await cek('ekip', 900);

  /* Yana taşma var mı? */
  const tasma = await sayfa.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  console.log('  yatay taşma:', tasma, 'px');
  if (hatalar.length) hatalar.forEach((h) => console.log('  !', h));
  await baglam.close();
}

async function calistir() {
  mkdirSync(CIKIS, { recursive: true });
  const tarayici = await chromium.launch({
    headless: true,
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
  try {
    for (const cihaz of CIHAZLAR) await gez(tarayici, cihaz);
  } finally {
    await tarayici.close();
  }
  console.log('\nbitti.');
}

calistir().catch((h) => {
  console.error(h);
  process.exit(1);
});
