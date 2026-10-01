/**
 * QA — yönetici konsolunun her ekranını dizüstü ve tablet boyutunda fotoğraflar.
 *
 *   node qa/yonetici.mjs [adres]
 *
 * Satışçı QA'sinden farkı: burada SAHTE veri yok, gerçek sunucuya bağlanır
 * (varsayılan http://127.0.0.1:8123). Böylece 19.706 binalık gerçek veriyle
 * haritanın, tabloların ve atamanın gerçekten çalıştığı görülür.
 *
 * Tarayıcı: app/ ile aynı paketlenmiş Chromium (playwright-core).
 */

import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const CIKIS = join(KOK, 'qa');
const ADRES = process.argv[2] ?? 'http://127.0.0.1:8123';
const TELEFON = '5321110000';
const PIN = '2468';

const CIHAZLAR = [
  { ad: 'laptop', genislik: 1440, yukseklik: 900, hedef: 7 },
  { ad: 'tablet', genislik: 1024, yukseklik: 768, hedef: 6 },
];

let sayac = 0;
async function cek(sayfa, cihaz, ad, bekleme = 400) {
  await sayfa.waitForTimeout(bekleme);
  sayac += 1;
  const dosya = join(CIKIS, `${cihaz.ad}-${String(sayac).padStart(2, '0')}-${ad}.png`);
  await sayfa.screenshot({ path: dosya });
  console.log('  ✓', `qa/${cihaz.ad}-${String(sayac).padStart(2, '0')}-${ad}.png`);
}

async function rakamlariBas(sayfa, rakamlar) {
  for (const r of rakamlar) {
    await sayfa.getByRole('button', { name: r, exact: true }).click();
    await sayfa.waitForTimeout(30);
  }
}

async function girisYap(sayfa) {
  await sayfa.goto(`${ADRES}/?sahte=0`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakamlariBas(sayfa, TELEFON);
  await sayfa.getByRole('button', { name: 'Devam' }).click();
  await sayfa.waitForTimeout(250);
  await rakamlariBas(sayfa, PIN);
  await sayfa.waitForTimeout(1500);
}

async function gez(tarayici, cihaz) {
  console.log(`\n${cihaz.ad} (${cihaz.genislik}x${cihaz.yukseklik})`);
  sayac = 0;
  const baglam = await tarayici.newContext({
    viewport: { width: cihaz.genislik, height: cihaz.yukseklik },
    deviceScaleFactor: 1,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  });
  const sayfa = await baglam.newPage();
  const hatalar = [];
  sayfa.on('pageerror', (h) => hatalar.push('sayfa: ' + h.message));
  sayfa.on('console', (m) => {
    if (m.type() === 'error') hatalar.push('konsol: ' + m.text().slice(0, 200));
  });

  /* --- Giriş --- */
  await sayfa.goto(`${ADRES}/?sahte=0`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakamlariBas(sayfa, TELEFON);
  await cek(sayfa, cihaz, 'giris');
  await sayfa.getByRole('button', { name: 'Devam' }).click();
  await sayfa.waitForTimeout(250);
  await rakamlariBas(sayfa, PIN);
  await sayfa.waitForTimeout(1800);

  /* --- Canlı durum --- */
  await sayfa.goto(`${ADRES}/#/yonetici`, { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.satisci-kart', { timeout: 25000 });
  await cek(sayfa, cihaz, 'canli', 1200);
  await sayfa.mouse.wheel(0, 500);
  await cek(sayfa, cihaz, 'canli-kartlar', 600);
  await sayfa.mouse.wheel(0, -900);

  /* Bir satışçının gün listesi */
  await sayfa.getByRole('button', { name: 'Listesini aç' }).first().click();
  await sayfa.waitForSelector('.cekmece', { timeout: 15000 });
  await cek(sayfa, cihaz, 'canli-gun-listesi', 1200);
  await sayfa.keyboard.press('Escape');
  await sayfa.waitForTimeout(300);

  /* --- Kapsama haritası --- */
  await sayfa.getByRole('button', { name: 'Kapsama haritası' }).click();
  await sayfa.waitForSelector('.yon-manset', { timeout: 30000 });
  await sayfa.waitForTimeout(6000);
  await cek(sayfa, cihaz, 'kapsama', 1500);

  /* Bölgeye süz */
  await sayfa.locator('select[aria-label="Bölge süzgeci"]').selectOption('3');
  await sayfa.waitForTimeout(3500);
  await cek(sayfa, cihaz, 'kapsama-bolge', 1200);

  /* --- Ekip --- */
  await sayfa.getByRole('button', { name: 'Ekip', exact: true }).click();
  await sayfa.waitForSelector('table.yon-tablo', { timeout: 20000 });
  await cek(sayfa, cihaz, 'ekip', 800);
  await sayfa.getByRole('button', { name: 'Yeni kişi' }).click();
  await sayfa.waitForSelector('.cekmece', { timeout: 10000 });
  await sayfa.locator('.cekmece input').first().fill('Kerem Doğan');
  await sayfa.locator('.cekmece input').nth(1).fill('5321110009');
  await cek(sayfa, cihaz, 'ekip-yeni-kisi', 700);
  await sayfa.keyboard.press('Escape');
  await sayfa.waitForTimeout(300);

  /* --- Rapor --- */
  await sayfa.getByRole('button', { name: 'Rapor' }).click();
  await sayfa.waitForSelector('.trend-grafik', { timeout: 25000 });
  await cek(sayfa, cihaz, 'rapor', 2500);
  await sayfa.mouse.wheel(0, 400);
  await cek(sayfa, cihaz, 'rapor-kapsama', 700);
  await sayfa.mouse.wheel(0, -600);

  /* --- Görev atama --- */
  await sayfa.getByRole('button', { name: 'Görev atama' }).click();
  await sayfa.waitForSelector('.kisi-izgara', { timeout: 20000 });
  await cek(sayfa, cihaz, 'atama-kime', 900);

  /* Listesi olmayan satışçıyı seç (her cihaz farklı kişiye atasın ki ikinci
     tur birincinin listesinin üstüne eklemesin). */
  await sayfa.locator('.kisi-secim').nth(cihaz.hedef).click();
  await sayfa.waitForSelector('.yol-secim', { timeout: 20000 });
  await sayfa.waitForTimeout(7000); // bölgenin binaları + harita
  await cek(sayfa, cihaz, 'atama-yol', 1200);

  /* Algoritma seçsin */
  await sayfa.getByRole('button', { name: /Algoritma seçsin/ }).click();
  await sayfa.waitForSelector('.secim-listesi', { timeout: 20000 });
  await cek(sayfa, cihaz, 'atama-algoritma', 1600);

  /* Haritadan dikdörtgen çiz */
  await sayfa.getByRole('button', { name: /Haritadan çiz/ }).click();
  await sayfa.waitForTimeout(700);
  const ortu = await sayfa.locator('.yon-harita-ortu').boundingBox();
  if (ortu) {
    const bx = ortu.x + ortu.width * 0.34;
    const by = ortu.y + ortu.height * 0.34;
    await sayfa.mouse.move(bx, by);
    await sayfa.mouse.down();
    await sayfa.mouse.move(bx + ortu.width * 0.24, by + ortu.height * 0.22, { steps: 14 });
    await cek(sayfa, cihaz, 'atama-cizim', 350);
    await sayfa.mouse.up();
    await sayfa.waitForTimeout(900);
    await cek(sayfa, cihaz, 'atama-harita-secim', 900);
  }

  /* Gönder */
  await sayfa.getByRole('button', { name: /Algoritma seçsin/ }).click();
  await sayfa.waitForTimeout(800);
  await sayfa.getByRole('button', { name: 'Listeyi gönder' }).click();
  await sayfa.waitForTimeout(3500);
  await cek(sayfa, cihaz, 'atama-gonderildi', 800);

  if (hatalar.length) {
    console.log('  ! hatalar:');
    hatalar.slice(0, 12).forEach((h) => console.log('    -', h));
  } else {
    console.log('  (konsol temiz)');
  }
  await baglam.close();
  return hatalar;
}

async function calistir() {
  mkdirSync(CIKIS, { recursive: true });
  console.log('sunucu:', ADRES);
  const tarayici = await chromium.launch({
    headless: true,
    args: [
      '--use-gl=angle',
      '--use-angle=swiftshader',
      '--enable-unsafe-swiftshader',
      '--ignore-gpu-blocklist',
    ],
  });
  let hepsi = [];
  try {
    for (const cihaz of CIHAZLAR) {
      hepsi = hepsi.concat(await gez(tarayici, cihaz));
    }
  } finally {
    await tarayici.close();
  }
  console.log('\nbitti.', hepsi.length ? `${hepsi.length} hata` : 'hata yok');
}

calistir().catch((h) => {
  console.error(h);
  process.exit(1);
});
