/**
 * Karanlık mod ve BÜYÜK YAZI (iOS Dynamic Type / Android yazı boyutu) kontrolü.
 *
 *   node qa/tema-yazi.mjs
 *
 * Denetimde ikisi de çalışmıyordu: karanlık modda uygulama bembeyaz açılıyor,
 * yazı boyutu büyütülünce hiçbir şey değişmiyordu (bütün ölçüler sabit px'ti).
 */

import { chromium } from 'playwright-core';

const ADRES = process.env.SAHA_URL || 'http://127.0.0.1:8098';
const TELEFON = process.env.E2E_TELEFON || '5550000005';
const DAVET = process.env.E2E_DAVET || '';
const PIN = '4726';

async function jetonAl() {
  let y = await fetch(`${ADRES}/api/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telefon: TELEFON, pin: PIN, davet_kodu: DAVET }),
  }).then((r) => r.json());
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

async function acVeGir(baglam) {
  const sayfa = await baglam.newPage();
  await sayfa.goto(ADRES, { waitUntil: 'networkidle' });
  const bas = async (rakamlar) => {
    for (const r of rakamlar) {
      await sayfa.click(`button:has-text("${r}")`);
      await sayfa.waitForTimeout(55);
    }
  };
  await bas(TELEFON);
  await sayfa.click('button:has-text("Devam")');
  await sayfa.waitForTimeout(900);
  await bas(PIN);
  await sayfa.waitForSelector('.ilerleme-kart', { timeout: 20000 });
  await sayfa.waitForTimeout(700);
  return sayfa;
}

const hatalar = [];
const bekle = (kosul, mesaj) => {
  console.log(`  ${kosul ? '✓' : '✗'} ${mesaj}`);
  if (!kosul) hatalar.push(mesaj);
};

async function main() {
  const jeton = await jetonAl();
  await fetch(`${ADRES}/api/gorev/olustur`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${jeton}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ adet: 25 }),
  });

  const tarayici = await chromium.launch();
  const olcu = {
    viewport: { width: 393, height: 852 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: 'tr-TR',
    timezoneId: 'Europe/Istanbul',
  };

  /* 1) Karanlık mod */
  console.log('\n1. Karanlık mod');
  const koyuBaglam = await tarayici.newContext({ ...olcu, colorScheme: 'dark' });
  const koyu = await acVeGir(koyuBaglam);
  const zemin = await koyu.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const yazi = await koyu.evaluate(() => getComputedStyle(document.body).color);
  const [kr, kg, kb] = zemin.match(/\d+/g).map(Number);
  bekle(kr + kg + kb < 200, `zemin gerçekten koyu (${zemin})`);
  const [yr, yg, yb] = yazi.match(/\d+/g).map(Number);
  bekle(yr + yg + yb > 500, `yazı açık renkte (${yazi})`);
  const sekmeZemin = await koyu.evaluate(
    () => getComputedStyle(document.querySelector('.sekmeler')).backgroundColor,
  );
  bekle(!sekmeZemin.includes('255, 255, 255'), `sekme çubuğu da koyu (${sekmeZemin})`);
  await koyu.screenshot({ path: 'qa/e2e/22-karanlik-mod.png' });
  console.log('  📸 22-karanlik-mod.png');
  await koyuBaglam.close();

  /* 2) Büyük yazı — tarayıcı kök ölçüsü büyütülür (iOS/Android ayarının karşılığı). */
  console.log('\n2. Büyük yazı (kök ölçü 20px)');
  const buyukBaglam = await tarayici.newContext(olcu);
  const buyuk = await acVeGir(buyukBaglam);
  // Tarayıcının "varsayılan yazı boyutu" ayarının karşılığı: kök ölçüyü büyüt.
  // Uygulama rem kullanıyorsa her şey birlikte büyümeli.
  await buyuk.evaluate(() => {
    document.documentElement.style.fontSize = '20px';
  });
  await buyuk.waitForTimeout(400);
  const olcuAl = (secici) =>
    buyuk.evaluate((s) => {
      const e = document.querySelector(s);
      return e ? parseFloat(getComputedStyle(e).fontSize) : null;
    }, secici);
  const kartAd = await olcuAl('.kart-sokak');
  const govde = await olcuAl('body');
  bekle(govde > 17, `gövde yazısı büyüdü (${govde}px > 17px)`);
  bekle(kartAd !== null && kartAd > 18, `kart sokak satırı büyüdü (${kartAd}px > 18px)`);
  const tasma = await buyuk.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  bekle(tasma <= 0, `yatay taşma yok (${tasma}px)`);
  await buyuk.screenshot({ path: 'qa/e2e/23-buyuk-yazi.png' });
  console.log('  📸 23-buyuk-yazi.png');
  await buyukBaglam.close();

  await tarayici.close();
  console.log(`\n${hatalar.length === 0 ? '✅ HEPSİ GEÇTİ' : '❌ ' + hatalar.length + ' KONTROL DÜŞTÜ'}`);
  hatalar.forEach((h) => console.log('   ✗', h));
  if (hatalar.length) process.exit(1);
}

main().catch((h) => {
  console.error('✗', h.message);
  process.exit(1);
});
