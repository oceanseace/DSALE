/**
 * QA — derlenmiş uygulamanın her ekranını telefon boyutlarında fotoğraflar.
 *
 *   node qa/cek.mjs
 *
 * Kendi içinde küçük bir dosya sunucusu açar (127.0.0.1, rastgele port), sahte
 * veri kipiyle (`?sahte=1`) gezinir ve PNG'leri `qa/` altına yazar. Çevrimdışı
 * yol da denenir: bağlantı kesilir, ziyaret kaydedilir, rozet beklenir.
 *
 * Tarayıcı: app/ ile aynı paketlenmiş Chromium (playwright-core 1.63).
 */

import { createServer } from 'node:http';
import { createReadStream, existsSync, mkdirSync, statSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const DIST = join(KOK, 'dist');
const CIKIS = join(KOK, 'qa');

const TURLER = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function sunucuBaslat() {
  const sunucu = createServer((istek, yanit) => {
    const yol = decodeURIComponent(new URL(istek.url, 'http://127.0.0.1').pathname);
    let dosya = join(DIST, yol === '/' ? 'index.html' : yol.replace(/^\/+/, ''));
    if (!existsSync(dosya) || statSync(dosya).isDirectory()) dosya = join(DIST, 'index.html');
    yanit.writeHead(200, {
      'Content-Type': TURLER[extname(dosya)] ?? 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    createReadStream(dosya).pipe(yanit);
  });
  return new Promise((coz) => {
    sunucu.listen(0, '127.0.0.1', () => coz({ sunucu, port: sunucu.address().port }));
  });
}

const CIHAZLAR = [
  { ad: 'iphone', genislik: 393, yukseklik: 852, olcek: 2 }, // iPhone 14 Pro
  { ad: 'android', genislik: 360, yukseklik: 800, olcek: 2 }, // küçük Android
];

let sayac = 0;
async function cek(sayfa, cihaz, ad, bekleme = 450) {
  await sayfa.waitForTimeout(bekleme);
  sayac += 1;
  const dosya = join(CIKIS, `${cihaz.ad}-${String(sayac).padStart(2, '0')}-${ad}.png`);
  await sayfa.screenshot({ path: dosya });
  console.log('  ✓', dosya.replace(KOK + '\\', '').replace(KOK + '/', ''));
}

async function rakamlariBas(sayfa, rakamlar) {
  for (const r of rakamlar) {
    await sayfa.getByRole('button', { name: r, exact: true }).click();
    await sayfa.waitForTimeout(40);
  }
}

async function cihaziGez(tarayici, cihaz, adres) {
  console.log(`\n${cihaz.ad} (${cihaz.genislik}x${cihaz.yukseklik})`);
  sayac = 0;
  const baglam = await tarayici.newContext({
    viewport: { width: cihaz.genislik, height: cihaz.yukseklik },
    deviceScaleFactor: cihaz.olcek,
    isMobile: true,
    hasTouch: true,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });
  const sayfa = await baglam.newPage();
  sayfa.on('pageerror', (h) => console.log('  ! sayfa hatası:', h.message));
  sayfa.on('console', (m) => {
    if (m.type() === 'error') console.log('  ! konsol:', m.text().slice(0, 160));
  });

  /* --- Giriş --- */
  await sayfa.goto(`${adres}/?sahte=1`, { waitUntil: 'networkidle' });
  await sayfa.waitForSelector('.tus-takimi');
  await cek(sayfa, cihaz, 'giris-bos');

  await rakamlariBas(sayfa, '5321234567');
  await cek(sayfa, cihaz, 'giris-telefon');

  await sayfa.getByRole('button', { name: 'Devam' }).click();
  await sayfa.waitForTimeout(200);
  await rakamlariBas(sayfa, '123');
  await cek(sayfa, cihaz, 'giris-pin');

  await rakamlariBas(sayfa, '4');
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 15000 });

  /* --- Bugün --- */
  await cek(sayfa, cihaz, 'bugun', 900);

  await sayfa.getByRole('button', { name: /Bitenler/ }).click();
  await cek(sayfa, cihaz, 'bugun-bitenler');
  await sayfa.getByRole('button', { name: /Bitenler/ }).click();
  await sayfa.waitForTimeout(200);

  /* --- Bina --- */
  await sayfa.locator('.liste-kart').first().click();
  await sayfa.waitForSelector('.eylem-serit');
  await cek(sayfa, cihaz, 'bina');

  /* --- Sonuç çekmecesi --- */
  await sayfa.getByRole('button', { name: /Sonucu işle/ }).click();
  await sayfa.waitForSelector('.sonuc-izgara');
  await cek(sayfa, cihaz, 'sonuc-secim');

  await sayfa.getByRole('button', { name: 'Satış', exact: true }).click();
  await sayfa.waitForSelector('.sayac-satir');
  await sayfa.getByRole('button', { name: 'Artır' }).click();
  await cek(sayfa, cihaz, 'sonuc-satis');

  await sayfa.getByRole('button', { name: 'Not ekle' }).click();
  await sayfa.locator('textarea.girdi').fill('Kapıcı akşam gelmemizi söyledi.');
  await cek(sayfa, cihaz, 'sonuc-not');

  await sayfa.getByRole('button', { name: 'Kaydet', exact: true }).click();
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 15000 });
  await cek(sayfa, cihaz, 'kaydedildi', 300);

  /* --- Harita --- */
  await sayfa.getByRole('button', { name: 'Harita' }).click();
  await sayfa.waitForTimeout(3500);
  await cek(sayfa, cihaz, 'harita', 900);

  if (await sayfa.getByRole('button', { name: 'Tüm bölgem' }).count()) {
    await sayfa.getByRole('button', { name: 'Tüm bölgem' }).click();
    await cek(sayfa, cihaz, 'harita-bolge', 1600);
    await sayfa.getByRole('button', { name: 'Bugünün rotası' }).click();
    await sayfa.waitForTimeout(1200);
  }

  const binaNoktasi = await sayfa.locator('.harita-sarmal canvas').first();
  if (await binaNoktasi.count()) {
    const kutu = await binaNoktasi.boundingBox();
    if (kutu) {
      // Haritanın ortasına yakın bir yere dokunup kart açmayı dene.
      await sayfa.mouse.click(kutu.x + kutu.width / 2, kutu.y + kutu.height / 2);
      await sayfa.waitForTimeout(500);
      if (await sayfa.locator('.harita-kart').count()) {
        await cek(sayfa, cihaz, 'harita-secim');
      }
    }
  }

  /* --- Ben --- */
  await sayfa.getByRole('button', { name: 'Ben' }).click();
  await sayfa.waitForSelector('.bilgi-izgara');
  await cek(sayfa, cihaz, 'ben', 900);

  /* --- Çevrimdışı --- */
  console.log('  · çevrimdışı deneme');
  await baglam.setOffline(true);
  await sayfa.evaluate(() => window.dispatchEvent(new Event('offline')));
  await sayfa.getByRole('button', { name: 'Bugün' }).click();
  await sayfa.waitForSelector('.ilerleme-kart');
  await cek(sayfa, cihaz, 'cevrimdisi-bugun', 600);

  await sayfa.locator('.liste-kart').first().click();
  await sayfa.waitForSelector('.eylem-serit');
  await sayfa.getByRole('button', { name: /Sonucu işle/ }).click();
  await sayfa.waitForSelector('.sonuc-izgara');
  await sayfa.getByRole('button', { name: 'Evde yok', exact: true }).click();
  await sayfa.getByRole('button', { name: 'Kaydet', exact: true }).click();
  await sayfa.waitForSelector('.serit.bekleyen', { timeout: 15000 });
  await cek(sayfa, cihaz, 'cevrimdisi-bekleyen', 700);

  // Uygulamayı çevrimdışıyken yeniden aç: kabuk önbellekten gelmeli, kayıt durmalı.
  await sayfa.reload({ waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.serit.bekleyen', { timeout: 20000 });
  await cek(sayfa, cihaz, 'cevrimdisi-yeniden-acildi', 900);

  // Bağlantı geri geldi: kuyruk kendiliğinden boşalmalı.
  await baglam.setOffline(false);
  await sayfa.evaluate(() => window.dispatchEvent(new Event('online')));
  await sayfa.waitForSelector('.serit.bekleyen', { state: 'detached', timeout: 20000 });
  await sayfa.getByRole('button', { name: 'Ben' }).click();
  await sayfa.waitForSelector('.serit.basarili', { timeout: 15000 });
  await cek(sayfa, cihaz, 'senkron-tamam', 700);

  await baglam.close();
}

/** Tıklayarak ulaşılması zor iki ekran: liste bitti · bugün liste yok. */
async function ekDurumlar(tarayici, cihaz, adres) {
  for (const [durum, ad] of [
    ['bitti', 'liste-bitti'],
    ['bos', 'liste-yok'],
  ]) {
    const baglam = await tarayici.newContext({
      viewport: { width: cihaz.genislik, height: cihaz.yukseklik },
      deviceScaleFactor: cihaz.olcek,
      isMobile: true,
      hasTouch: true,
      locale: 'tr-TR',
      timezoneId: 'Europe/Istanbul',
    });
    const sayfa = await baglam.newPage();
    await sayfa.goto(`${adres}/?sahte=1&durum=${durum}`, { waitUntil: 'networkidle' });
    await sayfa.waitForSelector('.tus-takimi');
    await rakamlariBas(sayfa, '5321234567');
    await sayfa.getByRole('button', { name: 'Devam' }).click();
    await sayfa.waitForTimeout(200);
    await rakamlariBas(sayfa, '1234');
    await sayfa.waitForSelector('.bos', { timeout: 15000 });
    await cek(sayfa, cihaz, ad, 900);
    await baglam.close();
  }
}

async function calistir() {
  if (!existsSync(DIST)) {
    console.error('dist/ yok — önce `npm run build` çalıştırın.');
    process.exit(1);
  }
  mkdirSync(CIKIS, { recursive: true });

  const { sunucu, port } = await sunucuBaslat();
  const adres = `http://127.0.0.1:${port}`;
  console.log('sunucu:', adres);

  const tarayici = await chromium.launch({
    headless: true,
    args: [
      '--use-gl=angle',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
      '--ignore-gpu-blocklist',
    ],
  });

  try {
    for (const cihaz of CIHAZLAR) {
      await cihaziGez(tarayici, cihaz, adres);
      await ekDurumlar(tarayici, cihaz, adres);
    }
  } finally {
    await tarayici.close();
    sunucu.close();
  }
  console.log('\nbitti.');
}

calistir().catch((h) => {
  console.error(h);
  process.exit(1);
});
