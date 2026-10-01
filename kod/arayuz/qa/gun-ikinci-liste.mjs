/**
 * Gün içinde İKİNCİ liste alındığında sabahki emek ekranda kalıyor mu?
 *
 *   node qa/gun-ikinci-liste.mjs            (sunucu: SAHA_URL, öntanımlı :8098)
 *
 * Sunucu ikinci listede önceki görevi kapatıp yenisini açıyor; görev sayacı
 * (0 / 4) sıfırlanıyor. Günlük ziyaret sayısı ise ziyaret kayıtlarından geldiği
 * için sıfırlanmıyor ve kartta ayrıca yazılmalı: "Bugün toplam 25 bina gezdin".
 * Bu betik o durumu kurar ve fotoğraflar.
 */

import { chromium } from 'playwright-core';

const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8098';
const TELEFON = process.env.E2E_TELEFON || '5550000005';
const DAVET = process.env.E2E_DAVET || '';
const PIN = '4726';
const CIKIS = process.argv[2] || 'qa/e2e/21-gun-ikinci-liste.png';

async function jetonAl() {
  const govde = { telefon: TELEFON, pin: PIN, davet_kodu: DAVET };
  let y = await fetch(`${ADRES}/api/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(govde),
  }).then((r) => r.json());
  // PIN zaten belirlenmişse düz giriş.
  if (!y.token) {
    y = await fetch(`${ADRES}/api/giris`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telefon: TELEFON, pin: PIN }),
    }).then((r) => r.json());
  }
  if (!y.token) throw new Error(`giriş yapılamadı: ${JSON.stringify(y)}`);
  return y.token;
}

async function main() {
  const jeton = await jetonAl();
  const api = (yol, sec = {}) =>
    fetch(ADRES + yol, {
      ...sec,
      headers: {
        Authorization: `Bearer ${jeton}`,
        'Content-Type': 'application/json',
        ...(sec.headers || {}),
      },
    }).then((r) => r.json());

  /* 1) Günün ilk listesini al ve TAMAMEN bitir. */
  const ilk = await api('/api/gorev/olustur', {
    method: 'POST',
    body: JSON.stringify({ adet: 25 }),
  });
  for (const b of ilk.binalar) {
    await api('/api/ziyaret', {
      method: 'POST',
      body: JSON.stringify({
        offline_id: `gun2-${b.bina_serial}`,
        bina_serial: b.bina_serial,
        sonuc: 'ilgilenmedi',
      }),
    });
  }
  const bitince = await api('/api/ben');

  /* 2) İkinci listeyi al — sunucu yeni bir görev açar, sayaç sıfırlanır. */
  await api('/api/gorev/olustur', { method: 'POST', body: JSON.stringify({ adet: 25 }) });
  const sonra = await api('/api/ben');

  console.log(`ilk liste bitti  → tamam=${bitince.bugun.tamam} ziyaret=${bitince.bugun.ziyaret}`);
  console.log(`ikinci liste     → tamam=${sonra.bugun.tamam} ziyaret=${sonra.bugun.ziyaret}`);
  if (sonra.bugun.ziyaret <= sonra.bugun.tamam) {
    throw new Error('beklenen durum kurulamadı: günlük ziyaret görev sayacından büyük değil');
  }

  /* 3) Uygulamayı aç ve ekranı fotoğrafla. */
  const tarayici = await chromium.launch();
  const baglam = await tarayici.newContext({
    viewport: { width: 393, height: 852 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  });
  const sayfa = await baglam.newPage();
  await sayfa.goto(ADRES, { waitUntil: 'networkidle' });
  const bas = async (rakamlar) => {
    for (const r of rakamlar) {
      await sayfa.click(`button:has-text("${r}")`);
      await sayfa.waitForTimeout(60);
    }
  };
  await bas(TELEFON);
  await sayfa.click('button:has-text("Devam")');
  await sayfa.waitForTimeout(900);
  await bas(PIN);
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 20000 });
  await sayfa.waitForTimeout(800);
  await sayfa.screenshot({ path: CIKIS });

  const yazi = (await sayfa.textContent('.ilerleme-kart')).replace(/\s+/g, ' ').trim();
  console.log('ekrandaki kart:', yazi);
  if (!yazi.includes('Bugün toplam')) {
    throw new Error('KART GÜNÜN TOPLAMINI YAZMIYOR — sabahki emek ekrandan kayboluyor');
  }

  /* 4) Sayı yetmez: sabahki binalar LİSTEDE de durmalı, tek tek açılabilmeli. */
  const bitenlerDugmesi = sayfa.getByRole('button', { name: /Bitenler/ });
  if (!(await bitenlerDugmesi.count())) {
    throw new Error('"BİTENLER" BÖLÜMÜ YOK — sabah gezilen binalar listeden silinmiş');
  }
  const baslik = (await bitenlerDugmesi.innerText()).replace(/\s+/g, ' ').trim();
  const sayi = Number(baslik.match(/\((\d+)\)/)?.[1] ?? 0);
  if (sayi < bitince.bugun.tamam) {
    throw new Error(
      `"Bitenler (${sayi})" sabahki ${bitince.bugun.tamam} binayı kapsamıyor`,
    );
  }
  await bitenlerDugmesi.click();
  await sayfa.waitForTimeout(500);
  const kartSayisi = await sayfa.locator('.liste-kart.bitti').count();
  if (kartSayisi < bitince.bugun.tamam) {
    throw new Error(`bitenler açıldı ama ${kartSayisi} kart var, ${bitince.bugun.tamam} bekleniyordu`);
  }
  await sayfa.screenshot({ path: CIKIS.replace('.png', '-bitenler.png') });
  console.log(`  ✓ "${baslik}" — sabahki binalar listede, tek tek açılabiliyor`);
  console.log(`✅ günün emeği ekranda duruyor → ${CIKIS}`);
  await tarayici.close();
}

main().catch((h) => {
  console.error('✗', h.message);
  process.exit(1);
});
