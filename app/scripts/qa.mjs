#!/usr/bin/env node
/**
 * Görsel QA sürücüsü — tek dosya HTML'i Edge (msedge) ile açar, sahne sahne ekran görüntüsü alır,
 * konsol hatalarını ve deck.gl "Missing character" uyarılarını toplar.
 *
 * Kullanım (app/ içinden):
 *   node scripts/qa.mjs
 *   node scripts/qa.mjs --html ../outputs/DSALE_Sunum.html --offline --modes sunum,kesif \
 *        --scenes 1-10 --adim 6:1,4,8 --kesif-durumlar varsayilan,bolge4,n25,arama,2b,hover \
 *        --sizes 1920x1080,1366x768 --out qa/release
 *
 * Seçenekler:
 *   --html <yol>            açılacak HTML (varsayılan dist-html/index.html)
 *   --out <klasör>          PNG klasörü (varsayılan qa)
 *   --modes a,b             sunum,kesif (varsayılan sunum)
 *   --scenes 1-10 | 1,5,7   sunum sahneleri (varsayılan 1)
 *   --adim 6:1,4,8          sahne 6 için 1., 4. ve 8. adım
 *   --kesif-durumlar ...    varsayilan,bolge<N>,n<N>,arama,2b,hover,planac,firsat,penetrasyon,
 *                           sutun,bina[:<seri|indeks>]
 *   --sizes 1920x1080,...   pencere boyutları
 *   --bekle <ms>            hazır olduktan sonra ek bekleme (varsayılan 900)
 *   --zaman-asimi <ms>      hazır bekleme süresi (varsayılan 45000)
 *   --offline               ağ kapalı (çevrimdışı senaryo); file:// dışına çıkış engellenir
 *   --n <N>                 plan (bölge sayısı)
 *   --film                  ?film=1 ile aç
 *   --kanal msedge|chromium tarayıcıyı zorla (varsayılan: önce msedge, sonra Playwright Chromium)
 *   --basli                 tarayıcıyı görünür aç (hata ayıklama)
 *
 * Çıkış kodu: konsol hatası / eksik karakter uyarısı / hazır olmayan sayfa varsa 1.
 */
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(BURASI, '..');

/* ------------------------------------------------------------------ argümanlar */

function argumanlar(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const ad = a.slice(2);
    const sonraki = argv[i + 1];
    if (sonraki && !sonraki.startsWith('--')) {
      o[ad] = sonraki;
      i++;
    } else o[ad] = true;
  }
  return o;
}

/** "1-10" | "1,5,7" | "3" → [1,…] */
function sayilar(metin, varsayilan) {
  if (metin == null || metin === true) return varsayilan;
  const out = [];
  for (const p of String(metin).split(',')) {
    const m = /^(\d+)-(\d+)$/.exec(p.trim());
    if (m) for (let i = +m[1]; i <= +m[2]; i++) out.push(i);
    else if (/^\d+$/.test(p.trim())) out.push(+p.trim());
  }
  return out.length ? out : varsayilan;
}

/** "6:1,4,8;9:2" → Map {6:[1,4,8], 9:[2]} */
function adimHaritasi(metin) {
  const h = new Map();
  if (!metin || metin === true) return h;
  for (const parca of String(metin).split(';')) {
    const [s, liste] = parca.split(':');
    if (!s || !liste) continue;
    h.set(+s, sayilar(liste, [1]));
  }
  return h;
}

const arg = argumanlar(process.argv.slice(2));
const HTML = path.resolve(APP, arg.html && arg.html !== true ? String(arg.html) : 'dist-html/index.html');
const CIKTI = path.resolve(APP, arg.out && arg.out !== true ? String(arg.out) : 'qa');
const MODLAR = String(arg.modes && arg.modes !== true ? arg.modes : 'sunum').split(',').map((s) => s.trim()).filter(Boolean);
const SAHNELER = sayilar(arg.scenes, [1]);
const ADIMLAR = adimHaritasi(arg.adim);
const KESIF_DURUMLAR = String(arg['kesif-durumlar'] && arg['kesif-durumlar'] !== true ? arg['kesif-durumlar'] : 'varsayilan')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);
const BOYUTLAR = String(arg.sizes && arg.sizes !== true ? arg.sizes : '1920x1080')
  .split(',')
  .map((s) => {
    const [w, h] = s.trim().toLowerCase().split('x').map(Number);
    return { width: w || 1920, height: h || 1080 };
  });
const BEKLE = Number(arg.bekle && arg.bekle !== true ? arg.bekle : 900);
const ZAMAN_ASIMI = Number(arg['zaman-asimi'] && arg['zaman-asimi'] !== true ? arg['zaman-asimi'] : 45000);
const OFFLINE = !!arg.offline;
const PLAN_N = arg.n && arg.n !== true ? Number(arg.n) : null;
const FILM = !!arg.film;
const BASLI = !!arg.basli;

/* ------------------------------------------------------------------ tarayıcı */

const GPU_ARGS = [
  '--use-angle=d3d11',
  '--ignore-gpu-blocklist',
  '--enable-gpu-rasterization',
  '--enable-webgl',
  '--disable-features=UseChromeOSDirectVideoDecoder',
  '--allow-file-access-from-files',
];
const YAZILIM_ARGS = [
  '--use-gl=swiftshader',
  '--use-angle=swiftshader',
  '--enable-unsafe-swiftshader',
  '--ignore-gpu-blocklist',
  '--allow-file-access-from-files',
];

/** WebGL2 gerçekten çalışıyor mu (ve hangi sürücüyle)? */
async function webglDene(tarayici) {
  const s = await tarayici.newContext({ viewport: { width: 400, height: 300 } });
  const p = await s.newPage();
  await p.goto('about:blank');
  const sonuc = await p.evaluate(() => {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2');
    if (!gl) return { tamam: false, bilgi: 'webgl2 yok' };
    const d = gl.getExtension('WEBGL_debug_renderer_info');
    return { tamam: true, bilgi: d ? String(gl.getParameter(d.UNMASKED_RENDERER_WEBGL)) : 'bilinmiyor' };
  });
  await s.close();
  return sonuc;
}

/**
 * Tarayıcıyı sırayla dener:
 *   1. Edge (channel msedge) + ANGLE d3d11 — sunum laptopunun gerçek tarayıcısı
 *   2. Playwright'in kendi Chromium'u + d3d11 — Edge sürümü playwright-core ile uyumsuzsa
 *   3. Chromium + SwiftShader — GPU yoksa (yazılımla çizer, yavaş ama kare üretir)
 * Chromium indirilmemişse:  node node_modules/playwright-core/cli.js install chromium
 */
async function tarayiciSec() {
  const zorla = arg.kanal && arg.kanal !== true ? String(arg.kanal) : null;
  const denemeler = [];
  if (!zorla || zorla === 'msedge') denemeler.push({ ad: 'msedge + d3d11', kanal: 'msedge', args: GPU_ARGS });
  if (!zorla || zorla === 'chromium') denemeler.push({ ad: 'chromium + d3d11', kanal: null, args: GPU_ARGS });
  denemeler.push({ ad: (zorla === 'msedge' ? 'msedge' : 'chromium') + ' + swiftshader', kanal: zorla === 'msedge' ? 'msedge' : null, args: YAZILIM_ARGS });

  let sonHata = null;
  for (const d of denemeler) {
    let tarayici = null;
    try {
      tarayici = await chromium.launch({ ...(d.kanal ? { channel: d.kanal } : {}), headless: !BASLI, args: d.args });
      const gpu = await webglDene(tarayici);
      if (gpu.tamam) return { tarayici, gpu, ad: d.ad };
      sonHata = `${d.ad}: ${gpu.bilgi}`;
      await tarayici.close();
    } catch (e) {
      sonHata = `${d.ad}: ${e.message}`;
      try {
        await tarayici?.close();
      } catch {
        /* yoksay */
      }
    }
    console.log(`    ${d.ad} olmadı → sonraki`);
  }
  throw new Error('WebGL2 çalışan tarayıcı bulunamadı. Son hata: ' + sonHata);
}

/* ------------------------------------------------------------------ yardımcılar */

function adres(params) {
  const u = new URL(pathToFileURL(HTML).href);
  for (const [k, v] of Object.entries(params)) if (v != null) u.searchParams.set(k, String(v));
  if (PLAN_N && !u.searchParams.has('n')) u.searchParams.set('n', String(PLAN_N));
  if (FILM) u.searchParams.set('film', '1');
  return u.toString();
}

const GOZ_ARDI = [
  /favicon/i,
  /net::ERR_INTERNET_DISCONNECTED/i,
  /basemaps\.cartocdn\.com/i,
  /Failed to load resource/i,
];

function onemliMi(metin) {
  return !GOZ_ARDI.some((r) => r.test(metin));
}

async function hazirBekle(sayfa, etiket, gunluk) {
  try {
    await sayfa.waitForFunction(() => !!window.__DSALE__ && window.__DSALE__.hazir === true, null, { timeout: ZAMAN_ASIMI });
  } catch {
    gunluk.hatalar.push(`${etiket}: __DSALE__.hazir ${ZAMAN_ASIMI} ms içinde true olmadı`);
    return false;
  }
  try {
    await sayfa.waitForFunction(() => !window.__DSALE__?.mesgul && !window.__DSALE__?.kesif?.mesgul, null, { timeout: 20000 });
  } catch {
    gunluk.uyarilar.push(`${etiket}: mesgul bayrağı 20 sn içinde düşmedi (kamera hâlâ hareket ediyor olabilir)`);
  }
  await sayfa.waitForTimeout(BEKLE);
  return true;
}

async function kareAl(sayfa, dosya, gunluk) {
  fs.mkdirSync(path.dirname(dosya), { recursive: true });
  await sayfa.screenshot({ path: dosya });
  gunluk.kareler.push(dosya);
  console.log('  →', path.relative(APP, dosya));
}

function sayfaDinle(sayfa, etiket, gunluk) {
  sayfa.on('console', (m) => {
    const metin = m.text();
    if (m.type() === 'error' && onemliMi(metin)) gunluk.hatalar.push(`${etiket} [konsol] ${metin}`);
    if (/missing character/i.test(metin)) gunluk.eksikKarakter.push(`${etiket} ${metin}`);
  });
  sayfa.on('pageerror', (e) => gunluk.hatalar.push(`${etiket} [sayfa] ${e.message}`));
}

/* ------------------------------------------------------------------ senaryolar */

async function sunumKareleri(baglam, boyut, gunluk) {
  for (const sahne of SAHNELER) {
    const adimlar = ADIMLAR.get(sahne) ?? [null];
    for (const adim of adimlar) {
      const etiket = `sunum s${sahne}${adim ? `a${adim}` : ''} ${boyut.width}x${boyut.height}`;
      const sayfa = await baglam.newPage();
      sayfaDinle(sayfa, etiket, gunluk);
      await sayfa.goto(adres({ mod: 'sunum', sahne, adim }), { waitUntil: 'load' });
      const tamam = await hazirBekle(sayfa, etiket, gunluk);
      // sahne URL'den uygulanmadıysa sözleşme üzerinden dene
      if (tamam) {
        const su = await sayfa.evaluate(() => window.__DSALE__?.sahne ?? 1);
        if (su !== sahne) {
          await sayfa.evaluate((s) => window.__DSALE__?.git?.(s), sahne);
          await hazirBekle(sayfa, etiket, gunluk);
        }
      }
      const ad = `sunum-s${String(sahne).padStart(2, '0')}${adim ? `-a${adim}` : ''}-${boyut.width}x${boyut.height}.png`;
      await kareAl(sayfa, path.join(CIKTI, ad), gunluk);
      await sayfa.close();
    }
  }
}

async function kesifKareleri(baglam, boyut, gunluk) {
  for (const durum of KESIF_DURUMLAR) {
    const etiket = `kesif ${durum} ${boyut.width}x${boyut.height}`;
    const params = { mod: 'kesif' };
    let mBolge = /^bolge(\d+)$/.exec(durum);
    let mN = /^n(\d+)$/.exec(durum);
    if (mBolge) params.bolge = mBolge[1];
    if (mN) params.n = mN[1];
    if (durum === '2b') params.gorunum = '2b';
    if (durum === 'arama') params.ara = 'hamitler';
    // renk modları ve bina seçimi de adres parametresiyle kurulabiliyor (durum.ts)
    if (durum === 'firsat' || durum === 'penetrasyon') params.renk = durum;
    if (durum === 'sutun') params.katman = 'binalar,sinirlar,sutun,ofis';
    const mBina = /^bina(?::(.+))?$/.exec(durum);
    if (mBina) params.bina = mBina[1] ?? '0';

    const sayfa = await baglam.newPage();
    sayfaDinle(sayfa, etiket, gunluk);
    await sayfa.goto(adres(params), { waitUntil: 'load' });
    await hazirBekle(sayfa, etiket, gunluk);

    // URL parametresi henüz desteklenmiyorsa test kancasını dene (Keşif ajanı ekler)
    if (mBolge) await kanca(sayfa, 'bolgeSec', Number(mBolge[1]), gunluk, etiket);
    if (durum === '2b') await kanca(sayfa, 'boyut', '2b', gunluk, etiket);
    if (durum === 'arama') await kanca(sayfa, 'ara', 'hamitler', gunluk, etiket);
    if (mBina) await kanca(sayfa, 'binaSec', mBina[1] ?? 0, gunluk, etiket);
    if (durum === 'hover') {
      // Varsayılan kamerada ekranın TAM ORTASI Marmara denizi: fare oraya gidince ipucu hiç
      // çıkmıyordu ve kare varsayılan kareyle birebir aynı oluyordu (yani hiçbir şey kanıtlamıyordu).
      // Önce B1 seçilir, kamera durur, sonra bina kümesinin üstüne gidilir.
      await kanca(sayfa, 'bolgeSec', 1, gunluk, etiket);
      await sayfa
        .waitForFunction(() => !window.__DSALE__?.kesif?.mesgul, null, { timeout: 20000 })
        .catch(() => gunluk.uyarilar.push(`${etiket}: hover öncesi kamera durmadı`));
      await sayfa.waitForTimeout(400);
      await sayfa.mouse.move(boyut.width * 0.55, boyut.height * 0.5);
      await sayfa.waitForTimeout(600);
      const ipucuVar = await sayfa.evaluate(() => !!document.querySelector('.ks-ipucu'));
      if (!ipucuVar) gunluk.uyarilar.push(`${etiket}: imlecin altında bina yok, ipucu çıkmadı`);
    }
    if (durum === 'planac') {
      // gizli dosya girdisi (core/platform.ts) — Electron dışında Plan Aç… bu yolu kullanır
      const planDosyasi = path.resolve(APP, '..', 'outputs', 'N08_res_hp', 'plan_N08.json');
      if (!fs.existsSync(planDosyasi)) {
        gunluk.uyarilar.push(`${etiket}: örnek plan dosyası yok (${planDosyasi})`);
      } else {
        await sayfa.evaluate(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'o' })));
        await sayfa.waitForSelector('#dsale-plan-dosya', { state: 'attached', timeout: 5000 }).catch(() => {});
        await sayfa.setInputFiles('#dsale-plan-dosya', planDosyasi);
        await sayfa.waitForTimeout(1200);
      }
    }
    if (mBolge || durum === '2b' || durum === 'arama') await hazirBekle(sayfa, etiket, gunluk);

    await kareAl(sayfa, path.join(CIKTI, `kesif-${durum}-${boyut.width}x${boyut.height}.png`), gunluk);
    await sayfa.close();
  }
}

async function kanca(sayfa, ad, deger, gunluk, etiket) {
  const sonuc = await sayfa.evaluate(
    ([a, d]) => {
      const k = window.__DSALE__?.kesif;
      if (!k || typeof k[a] !== 'function') return 'yok';
      k[a](d);
      return 'tamam';
    },
    [ad, deger],
  );
  if (sonuc === 'yok') gunluk.uyarilar.push(`${etiket}: __DSALE__.kesif.${ad} kancası yok (taslak sürüm?)`);
}

/* ------------------------------------------------------------------ ana akış */

async function main() {
  if (!fs.existsSync(HTML)) {
    console.error('HTML bulunamadı:', HTML, '\nÖnce: npm.cmd run build:html');
    process.exit(2);
  }
  fs.mkdirSync(CIKTI, { recursive: true });
  console.log('QA →', HTML);
  console.log('    modlar:', MODLAR.join(','), '| sahneler:', SAHNELER.join(','), '| boyutlar:', BOYUTLAR.map((b) => `${b.width}x${b.height}`).join(','));

  const { tarayici, gpu, ad: tarayiciAdi } = await tarayiciSec();
  console.log('    tarayıcı:', tarayiciAdi, '| WebGL:', gpu.bilgi);

  const gunluk = { hatalar: [], uyarilar: [], eksikKarakter: [], kareler: [] };

  for (const boyut of BOYUTLAR) {
    const baglam = await tarayici.newContext({ viewport: boyut, deviceScaleFactor: 1, locale: 'tr-TR', timezoneId: 'Europe/Istanbul' });
    if (OFFLINE) {
      await baglam.setOffline(true);
      await baglam.route('**', (r) => (r.request().url().startsWith('file:') ? r.continue() : r.abort()));
    }
    console.log(`\n[${boyut.width}x${boyut.height}]`);
    if (MODLAR.includes('sunum')) await sunumKareleri(baglam, boyut, gunluk);
    if (MODLAR.includes('kesif')) await kesifKareleri(baglam, boyut, gunluk);
    await baglam.close();
  }
  await tarayici.close();

  console.log('\n──────── ÖZET ────────');
  console.log(`kare: ${gunluk.kareler.length} → ${path.relative(APP, CIKTI)}`);
  if (gunluk.uyarilar.length) {
    console.log(`uyarı (${gunluk.uyarilar.length}):`);
    for (const u of gunluk.uyarilar) console.log('  -', u);
  }
  if (gunluk.eksikKarakter.length) {
    console.log(`EKSİK KARAKTER (${gunluk.eksikKarakter.length}):`);
    for (const u of [...new Set(gunluk.eksikKarakter)]) console.log('  -', u);
  }
  if (gunluk.hatalar.length) {
    console.log(`HATA (${gunluk.hatalar.length}):`);
    for (const u of gunluk.hatalar) console.log('  -', u);
  }
  const basarisiz = gunluk.hatalar.length > 0 || gunluk.eksikKarakter.length > 0 || !gpu.tamam;
  console.log(basarisiz ? 'SONUÇ: BAŞARISIZ' : 'SONUÇ: TEMİZ');
  process.exit(basarisiz ? 1 : 0);
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
