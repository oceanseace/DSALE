/**
 * İş emirleri ekranı — uçtan uca görsel kontrol (yalnız 127.0.0.1 test sunucusu + DB kopyası).
 *   SAHA_URL=http://127.0.0.1:8093 SAHA_TEL=5550000000 SAHA_PIN=2580 RAPOR=...xlsx node qa/is-emri-kontrol.mjs
 * Ekran görüntüleri: qa/is-emri/ (git dışı — rapor adres içerir)
 */
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const CIKIS = process.env.CIKIS || join(KOK, 'qa', 'is-emri');
mkdirSync(CIKIS, { recursive: true });
const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8093';
if (!/^http:\/\/127\.0\.0\.1:80(9\d)$/.test(ADRES)) throw new Error('Yalnız 127.0.0.1:8090-8099 test sunucusu');

const giris = await fetch(`${ADRES}/api/giris`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ telefon: process.env.SAHA_TEL, pin: process.env.SAHA_PIN }),
}).then((r) => r.json());
if (!giris.token) throw new Error('Giriş olmadı: ' + JSON.stringify(giris));

const tarayici = await chromium.launch();
const sonuc = {};
for (const [ad, boyut] of [
  ['genis', { width: 1680, height: 1000 }],
  ['dizustu', { width: 1366, height: 800 }],
]) {
  const baglam = await tarayici.newContext({ viewport: boyut, serviceWorkers: 'block' });
  await baglam.addInitScript((j) => localStorage.setItem('saha.jeton', j), giris.token);
  const sayfa = await baglam.newPage();
  const hatalar = [];
  sayfa.on('pageerror', (e) => hatalar.push(String(e)));
  sayfa.on('console', (m) => m.type() === 'error' && hatalar.push(m.text()));
  await sayfa.goto(`${ADRES}/#/yonetici/is-emirleri`, { waitUntil: 'networkidle' });
  await sayfa.waitForSelector('.ie-birak', { timeout: 20000 });

  if (ad === 'genis' && process.env.RAPOR) {
    await sayfa.setInputFiles('input[type=file]', process.env.RAPOR);
    await sayfa.waitForSelector('.ie-ozet', { timeout: 30000 });
  }
  await sayfa.waitForSelector('.ie-mahalle', { timeout: 20000 });
  await sayfa.waitForTimeout(2500); // harita karoları
  await sayfa.screenshot({ path: join(CIKIS, `1-acilis-${ad}.png`) });

  if (ad === 'genis') {
    // İlçe süzgeci: Nilüfer
    await sayfa.locator('.ie-cip', { hasText: 'Nilüfer' }).first().click();
    await sayfa.waitForTimeout(1200);
    sonuc.nilufer = await sayfa.locator('.ie-sayac b').innerText();
    // İki mahalle seç → öbek yap
    const satirlar = sayfa.locator('.ie-mahalle');
    const hedefler = [];
    for (let i = 0; i < (await satirlar.count()) && hedefler.length < 2; i++) {
      const s = satirlar.nth(i);
      if ((await s.locator('.obek').count()) === 0) {
        hedefler.push(await s.locator('.mh').innerText());
        await s.locator('input').check();
      }
    }
    await sayfa.fill('.ie-obek-yap input.yon-alan', 'Deneme öbeği');
    await sayfa.click('.ie-obek-yap button.birincil');
    await sayfa.waitForSelector('.ie-bildiri', { timeout: 10000 });
    sonuc.obek_yapildi = { mahalleler: hedefler, bildiri: await sayfa.locator('.ie-bildiri').innerText() };
    await sayfa.waitForTimeout(1500);
    await sayfa.screenshot({ path: join(CIKIS, `2-obek-${ad}.png`) });

    // En kalabalık öbeği böl (mahalleye göre 2)
    await sayfa.locator('.ie-obek .eylem button', { hasText: 'Böl' }).first().click();
    await sayfa.click('.ie-bol button.birincil');
    await sayfa.waitForSelector('.ie-parca', { timeout: 60000 });
    await sayfa.waitForTimeout(1500);
    sonuc.bolme_mahalle = await sayfa.locator('.ie-parca .sayi').allInnerTexts();
    await sayfa.screenshot({ path: join(CIKIS, `3-bolme-onizleme-${ad}.png`) });
    // Binaya göre, 3 parça
    await sayfa.locator('.yon-segment button', { hasText: 'Binaya göre' }).click();
    await sayfa.locator('.ie-adim button[aria-label="Artır"]').click();
    await sayfa.click('.ie-bol button.birincil');
    await sayfa.waitForTimeout(3000);
    sonuc.bolme_bina = await sayfa.locator('.ie-parca .sayi').allInnerTexts();
    await sayfa.screenshot({ path: join(CIKIS, `4-bolme-bina-${ad}.png`) });
    await sayfa.locator('.ie-bol-dugmeler button.birincil').click();
    await sayfa.waitForSelector('.ie-parca-ozet', { timeout: 10000 });
    sonuc.parca_ozet = await sayfa.locator('.ie-parca-ozet').innerText();
    // Kontrol tablosu
    await sayfa.locator('.yon-kart', { hasText: 'Kontrol edilecek' }).locator('button', { hasText: 'Göster' }).click();
    await sayfa.waitForTimeout(500);
    sonuc.kontrol_satir = await sayfa.locator('.ie-kontrol tbody tr').count();
    await sayfa.screenshot({ path: join(CIKIS, `5-son-${ad}.png`), fullPage: true });
  }
  sonuc[`hatalar_${ad}`] = hatalar;
  await baglam.close();
}
await tarayici.close();
console.log(JSON.stringify(sonuc, null, 2));
