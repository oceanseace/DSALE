/**
 * Bina kimlik kartı ve yönetici "Ayrıntılar" penceresi — hızlı görsel kontrol.
 *   SAHA_URL=http://127.0.0.1:8097 SAHA_TEL=5550000000 SAHA_PIN=2580 node qa/kimlik-kontrol.mjs
 */
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const CIKIS = join(KOK, 'qa', 'kimlik');
mkdirSync(CIKIS, { recursive: true });
const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8097';
const SERIAL = process.env.SAHA_BINA || 'BN-0000362608';

const giris = await fetch(`${ADRES}/api/giris`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ telefon: process.env.SAHA_TEL, pin: process.env.SAHA_PIN }),
}).then((r) => r.json());
if (!giris.token) throw new Error('Giriş olmadı: ' + JSON.stringify(giris));

const ayrinti = await fetch(`${ADRES}/api/bina/${SERIAL}`, {
  headers: { Authorization: `Bearer ${giris.token}` },
}).then((r) => r.json());
console.log('API kimlik:', JSON.stringify(ayrinti.bina.kimlik), 'crm:', ayrinti.bina.crm_site_adi, 'kat:', ayrinti.bina.kat);

const tarayici = await chromium.launch();
for (const [ad, boyut] of [
  ['telefon', { width: 393, height: 852 }],
  ['masaustu', { width: 1440, height: 900 }],
]) {
  const baglam = await tarayici.newContext({
    viewport: boyut,
    deviceScaleFactor: ad === 'telefon' ? 2 : 1,
    serviceWorkers: 'block',
    permissions: ['clipboard-read', 'clipboard-write'],
  });
  await baglam.addInitScript((j) => localStorage.setItem('saha.jeton', j), giris.token);
  const sayfa = await baglam.newPage();
  const hatalar = [];
  sayfa.on('pageerror', (e) => hatalar.push(String(e)));
  await sayfa.goto(`${ADRES}/#/bina/${encodeURIComponent(SERIAL)}`, { waitUntil: 'networkidle' });
  try { await sayfa.waitForSelector('.bk-kart', { timeout: 15000 }); } catch (e) { await sayfa.screenshot({ path: join(CIKIS, `hata-${ad}.png`) }); console.log('URL:', sayfa.url()); throw e; }
  await sayfa.locator('.bk-kart').scrollIntoViewIfNeeded();
  await sayfa.locator('.bk-kart').screenshot({ path: join(CIKIS, `bina-${ad}.png`) });
  // Ticket metnini kopyala ve panodan oku
  await sayfa.fill('.bk-ekip input', '+905551234567');
  await sayfa.locator('.bk-dugme', { hasText: 'Sinyal' }).click();
  const pano = await sayfa.evaluate(() => navigator.clipboard.readText());
  console.log(`[${ad}] pano:`, JSON.stringify(pano));
  console.log(`[${ad}] sayfa hataları:`, hatalar.length ? hatalar : 'yok');
  await baglam.close();
}
await tarayici.close();
