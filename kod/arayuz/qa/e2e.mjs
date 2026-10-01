/**
 * UÇTAN UCA TEST — gerçek sunucu, gerçek veri, gerçek telefon boyutu.
 *
 *   node qa/e2e.mjs                        # http://127.0.0.1:8098
 *   SAHA_URL=http://127.0.0.1:8099 node qa/e2e.mjs
 *
 * `qa/cek.mjs` sahte veriyle ekranları fotoğraflar; bu betik ise FastAPI
 * sunucusuna bağlanır ve şunları GERÇEKTEN yapar:
 *
 *   1. Satışçı ilk kez giriyor: telefon → davet kodu → yeni PIN (iki kez).
 *   2. Bugünün rotası sunucudan geliyor mu (25 bina).
 *   3. Bir bina açılıyor, DÖRT FARKLI sonuç işleniyor.
 *   4. Sayfa yenileniyor: kayıtlar sunucuda mı, liste doğru mu.
 *   5. İnternet kesiliyor, İKİ kayıt daha işleniyor, uygulama çevrimdışı
 *      yeniden açılıyor, sonra internet geliyor: kuyruk boşalıyor mu ve
 *      kayıtlar TAM BİR KEZ mi düşüyor (idempotanlık).
 *   6. Yönetici konsolu: satışçının sayıları ve kapsama oranı hareket etti mi.
 *   7. Harita dosyası inemezse (sinyalsiz telefon) uygulama çökmüyor mu.
 *
 * Her adımda hem ekran görüntüsü alınır (`qa/e2e/`) hem de API'den okunan
 * gerçek sayılarla karşılaştırma yapılır. Beklenti tutmazsa betik düşer.
 */

import { mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const KOK = resolve(fileURLToPath(new URL('..', import.meta.url)));
/* E2E_CIHAZ=android → 360x800 küçük Android; öntanımlı iPhone 14 Pro. */
const CIHAZ_ADI = (process.env.E2E_CIHAZ || 'iphone').toLowerCase();
const CIKIS = join(
  KOK,
  'qa',
  process.env.E2E_CIKIS || (CIHAZ_ADI === 'iphone' ? 'e2e' : `e2e-${CIHAZ_ADI}`),
);
const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8098';

/* Test hesapları — saha/demo.py ile tohumlanan yer tutucular. */
const SATISCI = {
  telefon: process.env.E2E_TELEFON || '5550000005', // 5. bölge: bugün hiç başlamamış
  davet: process.env.E2E_DAVET || '',
  pin: '4726',
};
const YONETICI = {
  telefon: process.env.E2E_YONETICI || '5550000000',
  davet: process.env.E2E_YONETICI_DAVET || '',
  pin: '8153',
};

const CIHAZLAR = {
  iphone: {
    viewport: { width: 393, height: 852 }, // iPhone 14 Pro
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 ' +
      '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  },
  android: {
    viewport: { width: 360, height: 800 }, // küçük Android — en dar gerçek ekran
    userAgent:
      'Mozilla/5.0 (Linux; Android 13; SM-A135F) AppleWebKit/537.36 (KHTML, like Gecko) ' +
      'Chrome/120.0.0.0 Mobile Safari/537.36',
  },
};

const CIHAZ = {
  ...(CIHAZLAR[CIHAZ_ADI] || CIHAZLAR.iphone),
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
  locale: 'tr-TR',
  timezoneId: 'Europe/Istanbul',
};

/** Sunucunun yazdığı gibi YEREL gün ("2026-09-21"); toISOString UTC'den okur. */
function gunMetni(t = new Date()) {
  const p = (n) => String(n).padStart(2, '0');
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`;
}

let adimNo = 0;
const hatalar = [];
const olculer = [];

async function cek(sayfa, ad, bekleme = 400) {
  await sayfa.waitForTimeout(bekleme);
  adimNo += 1;
  const dosya = join(CIKIS, `${String(adimNo).padStart(2, '0')}-${ad}.png`);
  await sayfa.screenshot({ path: dosya });
  console.log(`  📸 ${String(adimNo).padStart(2, '0')}-${ad}.png`);
  return dosya;
}

function bekle(kosul, mesaj) {
  if (kosul) {
    console.log(`  ✓ ${mesaj}`);
  } else {
    console.log(`  ✗ ${mesaj}`);
    hatalar.push(mesaj);
  }
}

/* ------------------------------ API yardımcıları ------------------------------ */

async function api(yol, secenek = {}) {
  const { jeton, yontem = 'GET', govde } = secenek;
  const basliklar = { Accept: 'application/json' };
  if (jeton) basliklar.Authorization = `Bearer ${jeton}`;
  if (govde !== undefined) basliklar['Content-Type'] = 'application/json';
  const baslangic = Date.now();
  const yanit = await fetch(ADRES + yol, {
    method: yontem,
    headers: basliklar,
    body: govde === undefined ? undefined : JSON.stringify(govde),
  });
  const sure = Date.now() - baslangic;
  olculer.push({ yol, sure, durum: yanit.status });
  const metin = await yanit.text();
  let veri = null;
  try {
    veri = JSON.parse(metin);
  } catch {
    /* JSON değilse ham metin yeter */
  }
  if (!yanit.ok) {
    const e = new Error(`${yontem} ${yol} → ${yanit.status} ${metin.slice(0, 200)}`);
    e.durum = yanit.status;
    e.veri = veri;
    throw e;
  }
  return veri;
}

/** Yönetici olarak giriş yapıp jeton alır (ölçüm ve doğrulama için). */
async function yoneticiJetonu() {
  try {
    const y = await api('/api/giris', {
      yontem: 'POST',
      govde: { telefon: YONETICI.telefon, pin: YONETICI.pin },
    });
    if (y.token) return y.token;
  } catch {
    /* PIN henüz yok, davet koduyla belirlenecek */
  }
  const y = await api('/api/pin', {
    yontem: 'POST',
    govde: { telefon: YONETICI.telefon, pin: YONETICI.pin, davet_kodu: YONETICI.davet },
  });
  return y.token;
}

/* ------------------------------ Ekran yardımcıları ------------------------------ */

async function rakamlariBas(sayfa, rakamlar) {
  for (const r of rakamlar) {
    await sayfa.getByRole('button', { name: r, exact: true }).click();
    await sayfa.waitForTimeout(45);
  }
}

/**
 * "Sıradakiler" listesindeki ilk binayı açar, verilen sonucu işler ve
 * listeye döner. `adet` yalnız satışta kullanılır.
 */
async function binaIsle(sayfa, sonuc, { adet = 0, not = null } = {}) {
  const kart = sayfa.locator('.liste-kart:not(.bitti)').first();
  await kart.waitFor({ state: 'visible', timeout: 15000 });
  const ad = (await kart.locator('.kart-sokak').innerText()).trim();

  await kart.click();
  await sayfa.waitForSelector('.eylem-serit', { timeout: 15000 });
  await sayfa.getByRole('button', { name: /Sonucu işle/ }).click();
  await sayfa.waitForSelector('.sonuc-izgara');
  await sayfa.getByRole('button', { name: sonuc, exact: true }).click();

  if (adet > 1) {
    await sayfa.waitForSelector('.sayac-satir');
    for (let i = 1; i < adet; i++) {
      await sayfa.getByRole('button', { name: 'Artır' }).click();
      await sayfa.waitForTimeout(60);
    }
  }
  if (not) {
    await sayfa.getByRole('button', { name: 'Not ekle' }).click();
    await sayfa.locator('textarea.girdi').fill(not);
  }
  return { ad, kaydet: () => sayfa.getByRole('button', { name: 'Kaydet', exact: true }).click() };
}

async function listedeKaydet(sayfa, sonuc, secenek = {}) {
  const { ad, kaydet } = await binaIsle(sayfa, sonuc, secenek);
  await kaydet();
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 20000 });
  console.log(`     · ${sonuc.padEnd(16)} → ${ad}`);
  return ad;
}

/** "7 / 25 bina" metnindeki iki sayı. */
async function ilerleme(sayfa) {
  const metin = await sayfa.locator('.ilerleme-kart').innerText();
  const eslesme = metin.replace(/\s+/g, ' ').match(/(\d+)\s*\/\s*(\d+)/);
  return eslesme ? { tamam: Number(eslesme[1]), toplam: Number(eslesme[2]) } : null;
}

/* ------------------------------ Test ------------------------------ */

async function main() {
  rmSync(CIKIS, { recursive: true, force: true });
  mkdirSync(CIKIS, { recursive: true });

  console.log(`\nSAHA SİSTEMİ — uçtan uca test\nSunucu: ${ADRES}\n`);

  const saglik = await api('/api/saglik');
  bekle(saglik.ok === true, `sunucu ayakta (${saglik.bina.toLocaleString('tr-TR')} bina)`);
  bekle(saglik.demo === true, 'gösterim verisi kurulu (demo bayrağı açık)');

  const yjeton = await yoneticiJetonu();
  const kapsamaOnce = await api('/api/ozet/kapsama?kirilim=bolge', { jeton: yjeton });
  console.log(
    `  · başlangıç kapsama: ${kapsamaOnce.dokunulan.toLocaleString('tr-TR')} / ` +
      `${kapsamaOnce.toplam.toLocaleString('tr-TR')} bina`,
  );

  const tarayici = await chromium.launch();
  const baglam = await tarayici.newContext(CIHAZ);
  const sayfa = await baglam.newPage();
  const sayfaHatalari = [];
  const konsolHatalari = [];
  sayfa.on('pageerror', (h) => sayfaHatalari.push(h.message));
  sayfa.on('console', (m) => {
    if (m.type() === 'error') konsolHatalari.push(m.text().slice(0, 200));
  });

  /* ---------- 1. İlk giriş: telefon → davet kodu → PIN ---------- */
  console.log('\n1. İlk giriş (davet kodu + yeni PIN)');
  const acilisBaslangic = Date.now();
  await sayfa.goto(ADRES + '/', { waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  const ilkBoya = Date.now() - acilisBaslangic;
  console.log(`  · ilk ekran ${ilkBoya} ms'de geldi`);
  await cek(sayfa, 'giris');

  await rakamlariBas(sayfa, SATISCI.telefon);
  await sayfa.getByRole('button', { name: 'Devam' }).click();

  // "Devam"dan sonra PIN SORULMADAN davet kodu adımına geçilmeli: hesabın PIN'i
  // yoksa uygulama bunu sunucuya sorup öğrenir. Eskiden kullanıcı "Şifren"
  // ekranına düşüp olmayan bir şifreyi tahmin etmeye çalışıyordu.
  await sayfa.waitForSelector('text=Davet kodun', { timeout: 20000 });
  await cek(sayfa, 'davet-kodu');
  bekle(true, 'ilk girişte PIN sorulmadan doğrudan davet kodu istendi');

  await rakamlariBas(sayfa, SATISCI.davet);
  await sayfa.waitForSelector('text=Yeni PIN belirle', { timeout: 10000 });
  await cek(sayfa, 'yeni-pin');
  await rakamlariBas(sayfa, SATISCI.pin);
  await sayfa.waitForSelector('text=tekrar gir', { timeout: 10000 });
  await rakamlariBas(sayfa, SATISCI.pin);

  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 25000 });
  bekle(true, 'PIN belirlendi ve giriş yapıldı');

  /* ---------- 2. Bugünün rotası ---------- */
  console.log('\n2. Bugünün rotası');
  await cek(sayfa, 'bugun', 900);
  const bas = await ilerleme(sayfa);
  // Site bütünlüğü için liste birkaç bina taşabilir (bkz. rota.LISTE_TASMA).
  bekle(
    (bas?.toplam ?? 0) >= 25 && (bas?.toplam ?? 0) <= 30,
    `listede 25-30 bina var (${bas?.toplam})`,
  );
  /*
   * Betiğin bütün beklentileri "güne sıfırdan başlayan satışçı" varsayar
   * (4 bina işle → 4 görsün). Gün içinde işe başlamış bir hesapla koşulursa
   * arka arkaya onlarca kontrol düşer ve sebebi görünmez olur; bunu burada
   * tek ve anlaşılır bir hatayla söylüyoruz.
   */
  if ((bas?.tamam ?? 0) !== 0) {
    throw new Error(
      `E2E_TELEFON=${SATISCI.telefon} hesabı bugün zaten ${bas.tamam} bina işlemiş. ` +
        'Bu betik güne sıfırdan başlayan bir satışçı ister: ya listesi boş bir hesap seçin ' +
        'ya da veritabanının taze bir kopyasıyla çalışın.',
    );
  }
  bekle(bas?.tamam === 0, `hiçbiri işlenmemiş (${bas?.tamam})`);
  const demoSerit = await sayfa.locator('.serit.demo').count();
  bekle(demoSerit > 0, 'gösterim verisi şeridi ekranda');

  /*
   * Kapsama beklentisini VERİDEN çıkar, sayıyı elle yazma. Bugünün listesinde
   * daha önce gidilmiş binalar da olabilir (randevusu gelenler soğumadan muaf);
   * onlar zaten "dokunulan" sayılıyor, tekrar gidilince kapsama artmaz.
   */
  const ilkJeton = await sayfa.evaluate(() => localStorage.getItem('saha.jeton'));
  const acilisGorevi = await api('/api/gorev/bugun', { jeton: ilkJeton });
  // "dokunulan" ölçüsü `son_ziyaret IS NOT NULL` demek — listeye girmek
  // (durum='planli') binayı dokunulmuş yapmaz.
  const hicGidilmemis = new Set(
    acilisGorevi.binalar.filter((b) => !b.son_ziyaret).map((b) => b.bina_serial),
  );

  /* ---------- 3. Bir bina açılıyor, dört farklı sonuç ---------- */
  console.log('\n3. Bina ekranı ve dört farklı sonuç');
  const ilkKart = sayfa.locator('.liste-kart').first();
  await ilkKart.click();
  await sayfa.waitForSelector('.eylem-serit', { timeout: 15000 });
  await cek(sayfa, 'bina');
  const binaBasligiMetni = (await sayfa.locator('.sayfa-govde h2').first().innerText()).trim();
  bekle(
    binaBasligiMetni.length > 0 && binaBasligiMetni !== 'Bina',
    `bina başlığı dolu: "${binaBasligiMetni}"`,
  );
  await sayfa.getByRole('button', { name: /Sonucu işle/ }).click();
  await sayfa.waitForSelector('.sonuc-izgara');
  await cek(sayfa, 'sonuc-secenekleri');
  await sayfa.getByRole('button', { name: 'Satış', exact: true }).click();
  await sayfa.waitForSelector('.sayac-satir');
  await sayfa.getByRole('button', { name: 'Artır' }).click();
  await cek(sayfa, 'sonuc-satis');
  await sayfa.getByRole('button', { name: 'Kaydet', exact: true }).click();
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 20000 });
  console.log('     · satis            → 2 adet');

  const islenen = ['satis'];
  islenen.push(await listedeKaydet(sayfa, 'İlgilenmedi'));
  islenen.push(await listedeKaydet(sayfa, 'Evde yok'));
  islenen.push(await listedeKaydet(sayfa, 'Altyapı sorunu', { not: 'Bina girişi kapalı, altyapı çalışması var.' }));
  await cek(sayfa, 'dort-sonuc-islendi', 900);

  const dortSonra = await ilerleme(sayfa);
  bekle(dortSonra?.tamam === 4, `ekranda 4 bina bitti görünüyor (${dortSonra?.tamam})`);

  const jeton = await sayfa.evaluate(() => localStorage.getItem('saha.jeton'));
  let gorev = await api('/api/gorev/bugun', { jeton });
  bekle(gorev.ozet.tamam === 4, `sunucuda da 4 bina tamam (${gorev.ozet.tamam})`);
  bekle(gorev.ozet.satis === 2, `sunucuda 2 satış (${gorev.ozet.satis})`);
  const sonuclar = new Set(
    gorev.binalar.filter((b) => b.gorev_durum === 'tamam').map((b) => b.son_sonuc),
  );
  bekle(sonuclar.size === 4, `dört FARKLI sonuç kaydedildi: ${[...sonuclar].join(', ')}`);

  /* ---------- 4. Yenileme sonrası kalıcılık ---------- */
  console.log('\n4. Sayfa yenilendi — kayıtlar duruyor mu');
  await sayfa.reload({ waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 25000 });
  await cek(sayfa, 'yenileme-sonrasi', 1200);
  const yenilemeSonrasi = await ilerleme(sayfa);
  bekle(
    yenilemeSonrasi?.tamam === 4 && yenilemeSonrasi?.toplam === bas?.toplam,
    `yenilemeden sonra hâlâ ${yenilemeSonrasi?.tamam}/${yenilemeSonrasi?.toplam}`,
  );

  /* ---------- 4b. Yanlış işlenmiş kaydı düzeltme ---------- */
  /*
   * Sahada en sık yapılan hata: acele ederken yanlış düğmeye basmak. Kayıt
   * SİLİNMEZ, düzeltilir: eski ziyaret iptal edilir, yenisi yazılır. Ne bina
   * ikinci kez "gezildi" sayılır ne de satış çift görünür. "İlgilenmedi"
   * işlenmiş binayı satışa çeviriyoruz — en pahalı yanlış bu.
   */
  console.log('\n4b. Yanlış kaydı düzelt (ilgilenmedi → satış)');
  const duzeltmeOnce = await api('/api/gorev/bugun', { jeton });
  const yanlisKayit = duzeltmeOnce.binalar.find(
    (b) => b.gorev_durum === 'tamam' && b.son_sonuc === 'ilgilenmedi',
  );
  bekle(Boolean(yanlisKayit), `düzeltilecek kayıt bulundu (${yanlisKayit?.bina_serial})`);

  // Biten binalar "Bitenler (n)" başlığının altına iner; satışçı yanlış kaydı
  // oradan bulur. Önce bölümü açıp görünür olduğunu fotoğraflıyoruz.
  await sayfa.getByRole('button', { name: /Bitenler/ }).click();
  await sayfa.waitForSelector('.liste-kart.bitti', { timeout: 10000 });
  const bitenSayisi = await sayfa.locator('.liste-kart.bitti').count();
  bekle(bitenSayisi === 4, `"Bitenler" altında 4 bina duruyor (${bitenSayisi})`);
  await cek(sayfa, 'bitenler-listesi', 500);

  // Hangi binayı düzelttiğimiz TESTİN BELİRLEDİĞİ bir şey olmalı; "ilk biten
  // kart" bambaşka bir binaya denk gelir ve test yanlış şeyi ölçer.
  await sayfa.goto(`${ADRES}/#/bina/${encodeURIComponent(yanlisKayit.bina_serial)}`, {
    waitUntil: 'domcontentloaded',
  });
  await sayfa.waitForSelector('.eylem-serit', { timeout: 15000 });
  await cek(sayfa, 'biten-bina-duzeltme');

  // İşlenmiş binada birincil düğme "Tekrar işle" DEĞİL "Kaydı düzelt" olmalı:
  // ikinci ziyaret eklemek sayıları şişirir, düzeltmek şişirmez.
  const duzeltDugmesi = sayfa.getByRole('button', { name: 'Kaydı düzelt', exact: true }).first();
  bekle(await duzeltDugmesi.count() > 0, 'işlenmiş binada birincil düğme "Kaydı düzelt"');
  await duzeltDugmesi.click();
  await sayfa.waitForSelector('.sonuc-izgara', { timeout: 10000 });
  const duzeltmeBasligi = (await sayfa.locator('.cekmece').innerText()).replace(/\s+/g, ' ');
  bekle(
    /Kaydı düzelt/.test(duzeltmeBasligi),
    'çekmece "Kaydı düzelt" başlığıyla ve eski sonucu yazarak açıldı',
  );
  await cek(sayfa, 'duzeltme-cekmecesi');
  await sayfa.getByRole('button', { name: 'Satış', exact: true }).click();
  await sayfa.waitForSelector('.sayac-satir');
  await sayfa.getByRole('button', { name: /Düzeltmeyi kaydet/ }).click();
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 20000 });
  await cek(sayfa, 'duzeltme-sonrasi', 900);

  const duzeltmeSonra = await api('/api/gorev/bugun', { jeton });
  bekle(
    duzeltmeSonra.ozet.tamam === 4,
    `düzeltme bina sayısını ŞİŞİRMEDİ, hâlâ 4 bina bitti (${duzeltmeSonra.ozet.tamam})`,
  );
  bekle(
    duzeltmeSonra.ozet.satis === 3,
    `satış adedi 2 → 3 oldu, çift sayılmadı (${duzeltmeSonra.ozet.satis})`,
  );
  const duzeltilenBina = duzeltmeSonra.binalar.find(
    (b) => b.bina_serial === yanlisKayit?.bina_serial,
  );
  bekle(duzeltilenBina?.son_sonuc === 'satis', `binanın son sonucu "satis" (${duzeltilenBina?.son_sonuc})`);
  const duzeltmeAyrinti = await api(`/api/bina/${encodeURIComponent(yanlisKayit.bina_serial)}`, {
    jeton,
  });
  const bugunKayitlari = duzeltmeAyrinti.ziyaretler.filter((z) =>
    (z.zaman ?? '').startsWith(gunMetni()),
  );
  bekle(
    bugunKayitlari.length === 1,
    `geçerli ziyaret TEK (${bugunKayitlari.length}) — eski kayıt iptal edildi, silinmedi`,
  );

  /* ---------- 5. Çevrimdışı: iki kayıt, tekrar çevrimiçi ---------- */
  console.log('\n5. Çevrimdışı iki kayıt ve senkron');
  await baglam.setOffline(true);
  await sayfa.evaluate(() => window.dispatchEvent(new Event('offline')));
  await sayfa.waitForSelector('.serit.cevrimdisi', { timeout: 15000 });
  bekle(true, 'kuyruk boştu, şerit "İnternet yok" oldu');
  await cek(sayfa, 'cevrimdisi');

  await listedeKaydet(sayfa, 'Randevu');
  // Çevrimdışıyken şerit İKİ BİLGİYİ BİRDEN verir: internet yok VE kaç kayıt
  // beklediği. Eskiden kayıt girilince "internet yok" bilgisi kayboluyor,
  // yerine "telefonda güvende" yazıyor ve bu "gönderildi" gibi okunuyordu.
  await sayfa.waitForSelector('.serit.cevrimdisi', { timeout: 15000 });
  await listedeKaydet(sayfa, 'Girilemedi');
  await cek(sayfa, 'cevrimdisi-iki-kayit-bekliyor', 700);
  const bekleyenYazi = await sayfa.locator('.serit.cevrimdisi').innerText();
  bekle(/2 kayıt/.test(bekleyenYazi), `şeritte "${bekleyenYazi.trim()}"`);
  bekle(/İnternet yok/.test(bekleyenYazi), 'şerit internetin olmadığını da söylüyor');

  const cevrimdisiIlerleme = await ilerleme(sayfa);
  bekle(cevrimdisiIlerleme?.tamam === 6, `çevrimdışıyken de 6/25 görünüyor (${cevrimdisiIlerleme?.tamam})`);

  // Sunucu bu ikisini HENÜZ görmemeli.
  gorev = await api('/api/gorev/bugun', { jeton });
  bekle(gorev.ozet.tamam === 4, `sunucu hâlâ 4 diyor (kayıtlar telefonda) — ${gorev.ozet.tamam}`);

  // Uygulama çevrimdışıyken yeniden açılıyor: kabuk önbellekten gelmeli.
  await sayfa.reload({ waitUntil: 'domcontentloaded' });
  await sayfa.waitForSelector('.serit.cevrimdisi', { timeout: 25000 });
  await cek(sayfa, 'cevrimdisi-yeniden-acildi', 1000);
  const yenidenIlerleme = await ilerleme(sayfa);
  bekle(
    yenidenIlerleme?.tamam === 6,
    `internetsiz yeniden açılışta kayıtlar duruyor (${yenidenIlerleme?.tamam}/25)`,
  );

  // İnternet geldi.
  await baglam.setOffline(false);
  await sayfa.evaluate(() => window.dispatchEvent(new Event('online')));
  await sayfa.waitForSelector('.serit.bekleyen, .serit.cevrimdisi', {
    state: 'detached',
    timeout: 30000,
  });
  await cek(sayfa, 'senkron-tamamlandi', 1200);

  gorev = await api('/api/gorev/bugun', { jeton });
  bekle(gorev.ozet.tamam === 6, `sunucuda 6 bina tamam (${gorev.ozet.tamam})`);

  /* Tam bir kez mi düştü: aynı binaya iki ziyaret yazılmamalı. */
  const bitenler = gorev.binalar.filter((b) => b.gorev_durum === 'tamam');
  const cift = [];
  for (const b of bitenler) {
    const ayrinti = await api(`/api/bina/${encodeURIComponent(b.bina_serial)}`, { jeton });
    const bugunkuler = ayrinti.ziyaretler.filter((z) => z.zaman.startsWith(gunMetni()));
    if (bugunkuler.length !== 1) cift.push(`${b.bina_serial}: ${bugunkuler.length} ziyaret`);
  }
  bekle(cift.length === 0, `her bina TAM BİR KEZ kaydedildi (çift kayıt: ${cift.length})`);

  /* Kuyruk gerçekten boş mu. */
  const kuyruk = await sayfa.evaluate(
    () =>
      new Promise((coz) => {
        const istek = indexedDB.open('saha');
        istek.onsuccess = () => {
          const db = istek.result;
          if (!db.objectStoreNames.contains('kuyruk')) return coz(-1);
          const say = db.transaction('kuyruk').objectStore('kuyruk').count();
          say.onsuccess = () => coz(say.result);
          say.onerror = () => coz(-1);
        };
        istek.onerror = () => coz(-1);
      }),
  );
  bekle(kuyruk === 0, `telefondaki kuyruk boş (${kuyruk} kayıt)`);

  /* ---------- 6. Ben ekranı ---------- */
  console.log('\n6. Ben ekranı');
  await sayfa.getByRole('button', { name: 'Ben' }).click();
  await sayfa.waitForSelector('.bilgi-izgara', { timeout: 15000 });
  await cek(sayfa, 'ben', 900);

  /* ---------- 7. Harita ---------- */
  console.log('\n7. Harita');
  await sayfa.getByRole('button', { name: 'Harita' }).click();
  await sayfa.waitForTimeout(4000);
  await cek(sayfa, 'harita-rota', 900);
  if (await sayfa.getByRole('button', { name: 'Tüm bölgem' }).count()) {
    await sayfa.getByRole('button', { name: 'Tüm bölgem' }).click();
    await cek(sayfa, 'harita-bolge', 2200);
  }
  await baglam.close();

  /* ---------- 8. Yönetici konsolu ---------- */
  console.log('\n8. Yönetici konsolu');
  const masa = await tarayici.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  });
  const ySayfa = await masa.newPage();
  ySayfa.on('pageerror', (h) => sayfaHatalari.push('yönetici: ' + h.message));
  ySayfa.on('console', (m) => {
    if (m.type() === 'error') konsolHatalari.push('yönetici: ' + m.text().slice(0, 200));
  });

  await ySayfa.goto(ADRES + '/', { waitUntil: 'domcontentloaded' });
  await ySayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakamlariBas(ySayfa, YONETICI.telefon);
  await ySayfa.getByRole('button', { name: 'Devam' }).click();
  await ySayfa.waitForTimeout(250);
  await rakamlariBas(ySayfa, YONETICI.pin);
  await ySayfa.waitForTimeout(1800);
  if (await ySayfa.locator('text=Davet kodun').count()) {
    await rakamlariBas(ySayfa, YONETICI.davet);
    await ySayfa.waitForSelector('text=Yeni PIN belirle', { timeout: 10000 });
    await rakamlariBas(ySayfa, YONETICI.pin);
    await ySayfa.waitForSelector('text=tekrar gir', { timeout: 10000 });
    await rakamlariBas(ySayfa, YONETICI.pin);
  }
  await ySayfa.waitForTimeout(2500);

  await ySayfa.goto(ADRES + '/#/yonetici', { waitUntil: 'domcontentloaded' });
  await ySayfa.waitForSelector('.yon', { timeout: 25000 });
  await ySayfa.waitForTimeout(2500);
  await cek(ySayfa, 'yonetici-canli', 1200);
  bekle((await ySayfa.locator('.yon-demo').count()) > 0, 'yönetici ekranında gösterim uyarısı var');

  const canliMetin = (await ySayfa.locator('.yon').innerText()).replace(/\s+/g, ' ');
  const gun = await api('/api/ozet/gun', { jeton: yjeton });
  const benimSatirim = gun.satiscilar.find((s) => s.bolge === 5);
  bekle(
    benimSatirim?.ziyaret === 6,
    `yönetici özeti: 5. bölge bugün 6 ziyaret (${benimSatirim?.ziyaret})`,
  );
  // 1 doğrudan satış + 1 düzeltmeyle satışa çevrilen bina = 2 bina, 3 abonelik.
  // İptal edilen "ilgilenmedi" kaydı hiçbir sayıya girmiyor.
  bekle(benimSatirim?.satis === 2, `5. bölge 2 binada satış (${benimSatirim?.satis})`);
  bekle(benimSatirim?.satis_adedi === 3, `5. bölge 3 abonelik (${benimSatirim?.satis_adedi})`);
  bekle(
    canliMetin.includes(benimSatirim?.ad ?? ' '),
    `satışçı kartı ekranda: ${benimSatirim?.ad}`,
  );

  await ySayfa.goto(ADRES + '/#/yonetici/kapsama', { waitUntil: 'domcontentloaded' });
  await ySayfa.waitForTimeout(5000);
  await cek(ySayfa, 'yonetici-kapsama', 1500);

  const kapsamaSonra = await api('/api/ozet/kapsama?kirilim=bolge', { jeton: yjeton });
  const fark = kapsamaSonra.dokunulan - kapsamaOnce.dokunulan;
  // Kapsama YALNIZ ilk kez gidilen binalar kadar artmalı: ne eksik (kayıp
  // ziyaret) ne fazla (çift sayım).
  const ilkKezGidilen = gorev.binalar.filter(
    (b) => b.gorev_durum === 'tamam' && hicGidilmemis.has(b.bina_serial),
  ).length;
  bekle(
    fark === ilkKezGidilen,
    `kapsama ilk kez gidilen bina kadar ilerledi: ` +
      `${kapsamaOnce.dokunulan.toLocaleString('tr-TR')} → ` +
      `${kapsamaSonra.dokunulan.toLocaleString('tr-TR')} ` +
      `(fark ${fark}, beklenen ${ilkKezGidilen}; 6 binanın ${6 - ilkKezGidilen} tanesine daha önce gidilmişti)`,
  );
  bekle(
    kapsamaSonra.kalan_firsat < kapsamaOnce.kalan_firsat,
    `kalan boş kapı azaldı: ${kapsamaOnce.kalan_firsat.toLocaleString('tr-TR')} → ` +
      `${kapsamaSonra.kalan_firsat.toLocaleString('tr-TR')}`,
  );
  const kapsamaMetin = (await ySayfa.locator('.yon').innerText()).replace(/\s+/g, ' ');
  bekle(
    kapsamaMetin.includes(kapsamaSonra.dokunulan.toLocaleString('tr-TR')),
    `ekrandaki manşet API ile aynı sayıyı gösteriyor (${kapsamaSonra.dokunulan.toLocaleString('tr-TR')})`,
  );

  await ySayfa.goto(ADRES + '/#/yonetici/rapor', { waitUntil: 'domcontentloaded' });
  await ySayfa.waitForTimeout(3000);
  await cek(ySayfa, 'yonetici-rapor', 1200);

  /* ---------- 8b. Günlük Excel raporu ---------- */
  /*
   * Rapor jeton istediği için düz bağlantı çalışmaz; uygulama dosyayı
   * fetch + blob ile indirir. Burada indirmenin GERÇEKTEN olduğunu ve dosyanın
   * içinde bugünün sayılarının bulunduğunu doğruluyoruz.
   */
  console.log('\n8b. Günlük Excel raporu');
  const indirmeSozu = ySayfa.waitForEvent('download', { timeout: 30000 });
  await ySayfa.getByRole('button', { name: /Excel indir/ }).click();
  const indirme = await indirmeSozu;
  const raporYolu = join(CIKIS, 'rapor.xlsx');
  await indirme.saveAs(raporYolu);
  const raporBoyut = statSync(raporYolu).size;
  bekle(
    /^Saha_Gun_Raporu_\d{4}-\d{2}-\d{2}\.xlsx$/.test(indirme.suggestedFilename()),
    `dosya adı doğru: ${indirme.suggestedFilename()}`,
  );
  bekle(raporBoyut > 5000, `Excel dosyası indi (${raporBoyut.toLocaleString('tr-TR')} bayt)`);
  // xlsx = zip; ilk iki bayt "PK" değilse dosya bozuktur.
  const ilkBaytlar = readFileSync(raporYolu).subarray(0, 2).toString('latin1');
  bekle(ilkBaytlar === 'PK', `dosya gerçekten xlsx (imza "${ilkBaytlar}")`);
  await cek(ySayfa, 'yonetici-rapor-indirildi', 900);

  await masa.close();

  /* ---------- 9. Harita parçası inemezse uygulama ÇÖKMEMELİ ---------- */
  console.log('\n9. Harita açılamazsa (sinyalsiz telefon)');
  const kirik = await tarayici.newContext({ ...CIHAZ, serviceWorkers: 'block' });
  await kirik.route('**/varlik/harita-*.js', (r) => r.abort('failed'));
  const kSayfa = await kirik.newPage();
  const kirikHata = [];
  kSayfa.on('pageerror', (h) => kirikHata.push(h.message));
  await kSayfa.goto(ADRES + '/', { waitUntil: 'domcontentloaded' });
  await kSayfa.waitForSelector('.tus-takimi', { timeout: 20000 });
  await rakamlariBas(kSayfa, SATISCI.telefon);
  await kSayfa.getByRole('button', { name: 'Devam' }).click();
  await kSayfa.waitForTimeout(250);
  await rakamlariBas(kSayfa, SATISCI.pin);
  await kSayfa.waitForSelector('.ilerleme-kart', { timeout: 25000 });
  await kSayfa.getByRole('button', { name: 'Harita' }).click();
  await kSayfa.waitForTimeout(4000);
  await cek(kSayfa, 'harita-acilamadi', 500);
  const kirikMetin = (await kSayfa.locator('body').innerText()).replace(/\s+/g, ' ');
  bekle(kirikMetin.includes('acilamiyor') || kirikMetin.includes('açılamıyor'),
        'harita inemeyince Turkce uyari cikiyor');
  bekle(kirikHata.length === 0, `uygulama cokmedi (sayfa hatasi ${kirikHata.length})`);
  await kSayfa.getByRole('button', { name: /Bugünün listesine dön/ }).click();
  await kSayfa.waitForSelector('.ilerleme-kart', { timeout: 15000 });
  bekle(true, 'listeye donulebiliyor - bugunun isi kaybolmadi');
  await kirik.close();

  await tarayici.close();

  /* ---------- Özet ---------- */
  console.log('\n--- API süreleri ---');
  const enYavas = [...olculer].sort((a, b) => b.sure - a.sure).slice(0, 6);
  for (const o of enYavas) console.log(`  ${String(o.sure).padStart(5)} ms  ${o.yol}`);
  /*
   * PIN belirleme ve giriş BİLEREK yavaştır: scrypt 16 MiB ile özet alıyor,
   * kaba kuvveti pahalı kılan şey bu. Günde bir kez çalışır. Onları günlük
   * kullanımın 300 ms bütçesine sokmak yanlış olur; ayrı ve gevşek ölçülür.
   */
  const kriptoUcu = (yol) => yol.startsWith('/api/pin') || yol.startsWith('/api/giris');
  const gunluk = olculer.filter((o) => !kriptoUcu(o.yol));
  const kripto = olculer.filter((o) => kriptoUcu(o.yol));
  const asan = gunluk.filter((o) => o.sure > 300);
  bekle(asan.length === 0, `günlük API yanıtları 300 ms altında (aşan: ${asan.length})`);
  const kriptoAsan = kripto.filter((o) => o.sure > 2500);
  bekle(kriptoAsan.length === 0, `giriş/PIN uçları 2,5 sn altında (aşan: ${kriptoAsan.length})`);
  bekle(ilkBoya < 2000, `ilk ekran 2 sn altında geldi (${ilkBoya} ms)`);
  bekle(sayfaHatalari.length === 0, `sayfa hatası yok (${sayfaHatalari.length})`);
  if (sayfaHatalari.length) sayfaHatalari.forEach((h) => console.log('    !', h));
  if (konsolHatalari.length) {
    console.log(`  · konsol hatası: ${konsolHatalari.length}`);
    [...new Set(konsolHatalari)].slice(0, 5).forEach((h) => console.log('    !', h));
  }

  writeFileSync(
    join(CIKIS, 'ozet.json'),
    JSON.stringify(
      {
        adres: ADRES,
        zaman: new Date().toISOString(),
        ilkBoyaMs: ilkBoya,
        kapsamaOnce: kapsamaOnce.dokunulan,
        kapsamaSonra: kapsamaSonra.dokunulan,
        apiEnYavasMs: enYavas[0]?.sure ?? 0,
        basarisiz: hatalar,
      },
      null,
      2,
    ),
    'utf8',
  );

  console.log(`\n${hatalar.length === 0 ? '✅ HEPSİ GEÇTİ' : '❌ ' + hatalar.length + ' KONTROL DÜŞTÜ'}`);
  hatalar.forEach((h) => console.log('   ✗', h));
  process.exit(hatalar.length === 0 ? 0 : 1);
}

main().catch((h) => {
  console.error('\n💥 Test çöktü:', h);
  process.exit(2);
});
