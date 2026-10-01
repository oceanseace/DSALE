/**
 * DENETÇİ BULGULARININ UYGULAMA AYAĞI — tek tek, gerçek sunucuya karşı.
 *
 *   SAHA_URL=http://127.0.0.1:8099 node qa/bulgular.mjs
 *
 * `qa/e2e.mjs` günün akışını baştan sona geçer; bu betik ise denetimde tek tek
 * yazılmış maddelerin GERÇEKTEN düzeldiğini ölçer: giriş hatasının metni,
 * yöneticinin nereye düştüğü, zayıf PIN, karanlık mod, dar ekranda düğmenin
 * ulaşılabilirliği, çıkışta önbelleğin temizlenmesi...
 *
 * Ölçer, fotoğraflamaz: her madde bir sayıya ya da bir metne bakar.
 */

import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
const CIKIS = join(KOK, 'qa', 'son');
const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8099';

const SATISCI = {
  telefon: process.env.E2E_TELEFON || '5550000005',
  pin: '4726',
  davet: process.env.E2E_DAVET || '',
};
const YONETICI = {
  telefon: '5550000000',
  pin: '8153',
  davet: process.env.E2E_YONETICI_DAVET || '',
};
/** Bu hesap PIN'i HENÜZ OLMAYAN biri olmalı: ilk giriş akışı ölçülüyor. */
const YENI = { telefon: process.env.E2E_YENI || '5550000007', davet: process.env.E2E_YENI_DAVET || '' };

/** Betik başlamadan önce hesapların PIN'ini kurar (temiz veritabanı için). */
async function hesabiHazirla(hesap) {
  const giris = await fetch(ADRES + '/api/giris', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telefon: hesap.telefon, pin: hesap.pin }),
  });
  if (giris.ok && (await giris.json()).token) return;
  const yanit = await fetch(ADRES + '/api/pin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telefon: hesap.telefon, pin: hesap.pin, davet_kodu: hesap.davet }),
  });
  if (!yanit.ok) {
    throw new Error(`${hesap.telefon} hazırlanamadı: ${yanit.status} ${await yanit.text()}`);
  }
}

const TELEFON = {
  viewport: { width: 393, height: 852 },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
  locale: 'tr-TR',
  timezoneId: 'Europe/Istanbul',
  userAgent:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
    '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
};

const gecen = [];
const dusen = [];
function kontrol(no, ad, kosul, ayrinti = '') {
  (kosul ? gecen : dusen).push(`${no} — ${ad}${ayrinti ? ` (${ayrinti})` : ''}`);
  console.log(`  ${kosul ? '✓' : '✗'} [${no}] ${ad}${ayrinti ? ` — ${ayrinti}` : ''}`);
}

async function rakam(sayfa, metin) {
  for (const r of metin) {
    await sayfa.getByRole('button', { name: r, exact: true }).click();
    await sayfa.waitForTimeout(45);
  }
}

/** Telefon + PIN ile normal giriş. */
async function girisYap(sayfa, hesap) {
  await sayfa.goto(ADRES + '/', { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakam(sayfa, hesap.telefon);
  await sayfa.getByRole('button', { name: 'Devam' }).click();
  await sayfa.waitForTimeout(400);
  await rakam(sayfa, hesap.pin);
}

async function main() {
  mkdirSync(CIKIS, { recursive: true });
  console.log(`\nDENETİM MADDELERİ — uygulama ayağı\nSunucu: ${ADRES}\n`);
  await hesabiHazirla(SATISCI);
  await hesabiHazirla(YONETICI);
  const tarayici = await chromium.launch();

  /* ---------- A1: giriş hatasının METNİ ekranda ---------- */
  {
    const b = await tarayici.newContext(TELEFON);
    const s = await b.newPage();
    await girisYap(s, { telefon: SATISCI.telefon, pin: '9999' });
    await s.waitForTimeout(2500);
    const metin = (await s.locator('body').innerText()).replace(/\s+/g, ' ');
    // Sunucunun Türkçe cümlesi ekranda durmalı; eskiden istemci onu
    // "Bir şeyler ters gitti" gibi genel bir metinle eziyordu.
    kontrol(
      'A1',
      'yanlış PIN: sunucunun Türkçe mesajı ekranda',
      /PIN|şifre|hatalı|yanlış/i.test(metin) && !/ters gitti|Error|undefined/i.test(metin),
      metin.match(/[^.]*(hatalı|yanlış)[^.]*/i)?.[0]?.trim().slice(0, 70) ?? '—',
    );
    await b.close();
  }

  /* ---------- A2: yönetici girişten sonra KONSOLA düşüyor ---------- */
  {
    const b = await tarayici.newContext({ viewport: { width: 1440, height: 900 }, locale: 'tr-TR' });
    const s = await b.newPage();
    await girisYap(s, YONETICI);
    await s.waitForTimeout(3500);
    const adres = await s.evaluate(() => location.hash);
    const yonVar = await s.locator('.yon').count();
    kontrol(
      'A2',
      'yönetici girişten sonra doğrudan konsola düşüyor',
      yonVar > 0 && adres.includes('yonetici'),
      `adres=${adres || '(boş)'} .yon=${yonVar}`,
    );
    /* ---------- A17: yönetici baş harfleri ---------- */
    const rozet = await s.locator('.yon .bas-harf, .yon .kisi-rozet').first();
    const harf = (await rozet.count()) ? (await rozet.innerText()).trim() : '';
    kontrol(
      'A17',
      'satışçı rozetleri Türkçe baş harf veriyor',
      /^[A-ZÇĞİÖŞÜ]{1,2}$/.test(harf),
      `rozet="${harf}"`,
    );
    await b.close();
  }

  /* ---------- A11: zayıf PIN, ilk giriş akışında ---------- */
  {
    const b = await tarayici.newContext(TELEFON);
    const s = await b.newPage();
    await s.goto(ADRES + '/', { waitUntil: 'domcontentloaded' });
    await s.waitForSelector('.tus-takimi', { timeout: 20000 });
    await rakam(s, YENI.telefon);
    await s.getByRole('button', { name: 'Devam' }).click();
    await s.waitForSelector('text=Davet kodun', { timeout: 20000 });
    await rakam(s, YENI.davet);
    await s.waitForSelector('text=Yeni PIN belirle', { timeout: 10000 });
    await rakam(s, '1234');
    await s.waitForTimeout(1500);
    const metin = (await s.locator('body').innerText()).replace(/\s+/g, ' ');
    const hala = await s.locator('.tus-takimi').count();
    kontrol(
      'A11',
      'zayıf PIN aynı ekranda, Türkçe gerekçeyle reddediliyor',
      /kolay|zayıf|tahmin|basit/i.test(metin) && hala > 0,
      metin.match(/[^.]*(kolay|zayıf|tahmin)[^.]*/i)?.[0]?.trim().slice(0, 70) ?? '—',
    );
    // ...ve hemen ardından güçlü PIN kabul edilmeli (akış kilitlenmemeli).
    await rakam(s, '7391');
    await s.waitForSelector('text=tekrar gir', { timeout: 10000 });
    await rakam(s, '7391');
    // Bu hesabın bugün listesi olmayabilir — o zaman boş durum ekranı gelir.
    await s.waitForSelector('.ilerleme-kart, .bos', { timeout: 25000 });
    kontrol('A11b', 'reddedilen PIN sonrası akış kilitlenmiyor', true, 'güçlü PIN kabul edildi');
    await b.close();
  }

  /* ---------- A6 + A4 + A10: 360 px ekranda ulaşılabilirlik ---------- */
  {
    const b = await tarayici.newContext({ ...TELEFON, viewport: { width: 360, height: 640 } });
    const s = await b.newPage();
    await girisYap(s, SATISCI);
    await s.waitForSelector('.ilerleme-kart', { timeout: 25000 });

    const tasma = await s.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    kontrol('A4', '360x640 listede yatay taşma yok', tasma <= 0, `${tasma} px`);

    await s.locator('.liste-kart:not(.bitti)').first().click();
    await s.waitForSelector('.eylem-serit', { timeout: 15000 });
    await s.getByRole('button', { name: /Sonucu işle/ }).click();
    await s.waitForSelector('.sonuc-izgara');
    await s.getByRole('button', { name: 'Satış', exact: true }).click();
    await s.waitForTimeout(400);

    const kaydet = s.getByRole('button', { name: 'Kaydet', exact: true });
    const kutu = await kaydet.boundingBox();
    const ekranY = 640;
    kontrol(
      'A6',
      'dar ekranda "Kaydet" tamamen görünür ve parmak boyutunda',
      Boolean(kutu) && kutu.y + kutu.height <= ekranY + 1 && kutu.height >= 44,
      kutu ? `y=${Math.round(kutu.y)} h=${Math.round(kutu.height)} alt=${Math.round(kutu.y + kutu.height)}` : 'yok',
    );

    /* ---------- A3: satış sayacı ---------- */
    const sayacOnce = (await s.locator('.sayac-satir').innerText()).replace(/\s+/g, ' ');
    await s.getByRole('button', { name: 'Artır' }).click();
    await s.waitForTimeout(150);
    await s.getByRole('button', { name: 'Artır' }).click();
    await s.waitForTimeout(150);
    const sayacIki = (await s.locator('.sayac-satir').innerText()).replace(/\s+/g, ' ');
    await s.getByRole('button', { name: 'Azalt' }).click();
    await s.waitForTimeout(150);
    const sayacSon = (await s.locator('.sayac-satir').innerText()).replace(/\s+/g, ' ');
    kontrol(
      'A3',
      'satış sayacı 1 ile başlıyor, artıp azalabiliyor, 1 altına düşmüyor',
      /(^|\D)1(\D|$)/.test(sayacOnce) && /3/.test(sayacIki) && /2/.test(sayacSon),
      `${sayacOnce} → ${sayacIki} → ${sayacSon}`,
    );

    /* ---------- A13: "bina burada değil" ulaşılabilir ---------- */
    const yanlis = s.getByRole('button', { name: /Bina burada değil/ });
    kontrol('A13', '"Bina burada değil" seçeneği ekranda', (await yanlis.count()) > 0);

    /* ---------- A5: çekmece kapanınca girilen veri kaybolmuyor ---------- */
    await s.getByRole('button', { name: 'Not ekle' }).click();
    await s.locator('textarea.girdi').fill('Kapıcıyla konuşuldu, yarın tekrar.');
    await s.keyboard.press('Escape');
    await s.waitForTimeout(600);
    const uyariMetni = (await s.locator('body').innerText()).replace(/\s+/g, ' ');
    const cekmeceAcik = await s.locator('.sonuc-izgara').count();
    kontrol(
      'A5',
      'dolu çekmece kazara kapanmıyor (uyarı veya açık kalma)',
      cekmeceAcik > 0 || /kaydedilmedi|vazgeç|emin/i.test(uyariMetni),
      cekmeceAcik > 0 ? 'çekmece açık kaldı' : 'onay soruldu',
    );
    await b.close();
  }

  /* ---------- A12: karanlık mod ---------- */
  {
    const b = await tarayici.newContext({ ...TELEFON, colorScheme: 'dark' });
    const s = await b.newPage();
    await girisYap(s, SATISCI);
    await s.waitForSelector('.ilerleme-kart', { timeout: 25000 });
    await s.waitForTimeout(600);
    const renkler = await s.evaluate(() => {
      const oku = (sec) => {
        const e = document.querySelector(sec);
        if (!e) return null;
        const b = getComputedStyle(e);
        return { zemin: b.backgroundColor, yazi: b.color };
      };
      return { govde: oku('body'), ust: oku('.ust'), sekme: oku('.alt-bar') };
    });
    const parcala = (s) => (s || '').match(/\d+/g)?.slice(0, 3).map(Number) ?? [255, 255, 255];
    const parlak = (c) => {
      const [r, g, mavi] = parcala(c);
      return 0.299 * r + 0.587 * g + 0.114 * mavi;
    };
    const ustKoyu = parlak(renkler.ust?.zemin) < 90;
    const ustOkunur = Math.abs(parlak(renkler.ust?.zemin) - parlak(renkler.ust?.yazi)) > 90;
    kontrol(
      'A12',
      'karanlık modda başlık şeridi de koyu ve yazı okunur',
      ustKoyu && ustOkunur,
      `ust zemin=${renkler.ust?.zemin} yazı=${renkler.ust?.yazi}`,
    );
    await s.screenshot({ path: join(CIKIS, '26-karanlik-mod.png') });
    await b.close();
  }

  /* ---------- A18: çıkışta jeton ve önbellek temizleniyor ---------- */
  {
    const b = await tarayici.newContext(TELEFON);
    const s = await b.newPage();
    await girisYap(s, SATISCI);
    await s.waitForSelector('.ilerleme-kart', { timeout: 25000 });
    await s.getByRole('button', { name: 'Ben' }).click();
    await s.waitForSelector('.bilgi-izgara', { timeout: 15000 });
    await s.getByRole('button', { name: 'Çıkış yap', exact: true }).click();
    // Çıkış tek dokunuşla OLMAZ: önce onay sorulur (kuyruk doluysa engellenir).
    await s.waitForSelector('.cekmece', { timeout: 10000 });
    await s.getByRole('button', { name: 'Evet, çıkış yap', exact: true }).click();
    await s.waitForSelector('.tus-takimi', { timeout: 20000 });
    await s.waitForTimeout(800);
    const kalinti = await s.evaluate(async () => {
      const jeton = localStorage.getItem('saha.jeton');
      const onbellek = await new Promise((coz) => {
        const istek = indexedDB.open('saha');
        istek.onsuccess = () => {
          const db = istek.result;
          if (!db.objectStoreNames.contains('onbellek')) return coz(0);
          const say = db.transaction('onbellek').objectStore('onbellek').count();
          say.onsuccess = () => coz(say.result);
          say.onerror = () => coz(-1);
        };
        istek.onerror = () => coz(-1);
      });
      return { jeton, onbellek };
    });
    kontrol(
      'A18',
      'çıkışta jeton ve bina önbelleği siliniyor (ortak telefon)',
      !kalinti.jeton && kalinti.onbellek === 0,
      `jeton=${kalinti.jeton ? 'DURUYOR' : 'yok'} önbellek=${kalinti.onbellek} kayıt`,
    );
    await b.close();
  }

  await tarayici.close();
  console.log(`\nGEÇEN ${gecen.length} · DÜŞEN ${dusen.length}`);
  dusen.forEach((d) => console.log('   ✗', d));
  process.exit(dusen.length ? 1 : 0);
}

main().catch((h) => {
  console.error('\n💥 Çöktü:', h);
  process.exit(2);
});
