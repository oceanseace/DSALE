#!/usr/bin/env node
/**
 * Tanıtım filmi — tek dosya HTML'i `?film=1` ile açar, film döngüsünü kaydeder,
 * ffmpeg-static ile MP4'e çevirir.
 *
 * Kullanım (app/ içinden):
 *   node scripts/film.mjs --html ../outputs/DSALE_Sunum.html --out ../outputs/DSALE_Tanitim.mp4
 *
 * Seçenekler:
 *   --html <yol>      kaynak HTML (varsayılan dist-html/index.html)
 *   --out <yol>       MP4 hedefi (varsayılan ../outputs/DSALE_Tanitim.mp4)
 *   --crf <n>         x264 kalitesi (varsayılan 20; dosya 60 MB'ı aşarsa 23 ile tekrar denenir)
 *   --zaman-asimi <s> döngü bekleme üst sınırı (varsayılan 150 sn)
 *   --kanal msedge|chromium
 *   --basli           tarayıcıyı görünür aç (bu makinede genelde `spawn UNKNOWN` verir;
 *                     varsayılan başsız, Playwright ekran kaydı başsız modda da çalışır)
 *
 * Not: Playwright'in ekran kaydı VP8'dir ve GPU yükü altında kare düşürebilir.
 * Kareler yumuşak/takılmalı görünürse sunum motoruna sabit adımlı saat eklemek gerekir.
 */
import { chromium } from 'playwright-core';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import ffmpegYolu from 'ffmpeg-static';

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(BURASI, '..');

function argumanlar(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const sonraki = argv[i + 1];
    if (sonraki && !sonraki.startsWith('--')) { o[a.slice(2)] = sonraki; i++; } else o[a.slice(2)] = true;
  }
  return o;
}
const arg = argumanlar(process.argv.slice(2));
const deger = (ad, vars) => (arg[ad] && arg[ad] !== true ? String(arg[ad]) : vars);

const HTML = path.resolve(APP, deger('html', 'dist-html/index.html'));
const HEDEF = path.resolve(APP, deger('out', '../outputs/DSALE_Tanitim.mp4'));
const CRF = Number(deger('crf', '20'));
const ZAMAN_ASIMI = Number(deger('zaman-asimi', '150')) * 1000;
const KANAL = deger('kanal', null);
const BASLI = !!arg.basli;
const EN = 1920;
const BOY = 1080;

const GPU_ARGS = [
  '--use-angle=d3d11',
  '--ignore-gpu-blocklist',
  '--enable-gpu-rasterization',
  '--allow-file-access-from-files',
  '--hide-scrollbars',
  '--autoplay-policy=no-user-gesture-required',
];

async function tarayiciAc(kayitKlasoru) {
  const denemeler = [];
  if (!KANAL || KANAL === 'msedge') denemeler.push({ ad: 'msedge', kanal: 'msedge' });
  if (!KANAL || KANAL === 'chromium') denemeler.push({ ad: 'chromium', kanal: null });
  let sonHata = null;
  for (const d of denemeler) {
    try {
      const t = await chromium.launch({ ...(d.kanal ? { channel: d.kanal } : {}), headless: !BASLI, args: GPU_ARGS });
      const b = await t.newContext({
        viewport: { width: EN, height: BOY },
        deviceScaleFactor: 1,
        locale: 'tr-TR',
        timezoneId: 'Europe/Istanbul',
        recordVideo: { dir: kayitKlasoru, size: { width: EN, height: BOY } },
      });
      const s = await b.newPage();
      return { tarayici: t, baglam: b, sayfa: s, ad: d.ad };
    } catch (e) {
      sonHata = `${d.ad}: ${e.message}`;
      console.log(`    ${d.ad} olmadı → sonraki`);
    }
  }
  throw new Error('Tarayıcı açılamadı. Son hata: ' + sonHata);
}

async function main() {
  if (!fs.existsSync(HTML)) { console.error('HTML yok:', HTML); process.exit(2); }
  if (!ffmpegYolu || !fs.existsSync(ffmpegYolu)) { console.error('ffmpeg bulunamadı'); process.exit(2); }

  const gecici = fs.mkdtempSync(path.join(os.tmpdir(), 'dsale-film-'));
  console.log('Film →', HTML, '\n    kayıt:', gecici);

  const { tarayici, baglam, sayfa, ad } = await tarayiciAc(gecici);
  console.log('    tarayıcı:', ad);

  const hatalar = [];
  sayfa.on('pageerror', (e) => hatalar.push(e.message));

  const u = new URL(pathToFileURL(HTML).href);
  u.searchParams.set('mod', 'sunum');
  u.searchParams.set('film', '1');
  await sayfa.goto(u.toString(), { waitUntil: 'load' });

  const kayitBasi = Date.now();
  await sayfa.waitForFunction(() => window.__DSALE__?.hazir === true, null, { timeout: 60000 });
  const t0 = (Date.now() - kayitBasi) / 1000; // videonun başındaki ölü süre
  console.log(`    hazır: +${t0.toFixed(1)} sn — döngü bekleniyor…`);

  // sahne sayısına ulaşıp 1'e dönene kadar bekle
  const dongu = await sayfa.evaluate(
    (zamanAsimi) =>
      new Promise((coz) => {
        const t = performance.now();
        let enYuksek = 0;
        let sarildi = false;
        const i = setInterval(() => {
          const d = window.__DSALE__;
          if (!d) return;
          if (d.sahne > enYuksek) enYuksek = d.sahne;
          if (enYuksek >= (d.sahneSayisi ?? 10) && d.sahne === 1) sarildi = true;
          if (sarildi || performance.now() - t > zamanAsimi) {
            clearInterval(i);
            coz({ sn: (performance.now() - t) / 1000, sarildi, enYuksek });
          }
        }, 250);
      }),
    ZAMAN_ASIMI,
  );
  console.log(`    döngü: ${dongu.sn.toFixed(1)} sn · en yüksek sahne ${dongu.enYuksek} · ${dongu.sarildi ? 'başa döndü' : 'ZAMAN AŞIMI'}`);

  const video = sayfa.video();
  await baglam.close();
  await tarayici.close();
  const webm = await video.path();
  console.log('    webm:', (fs.statSync(webm).size / 1048576).toFixed(1), 'MB');
  if (hatalar.length) console.log('    sayfa hataları:', hatalar.slice(0, 3).join(' | '));

  fs.mkdirSync(path.dirname(HEDEF), { recursive: true });
  const cevir = (crf) => {
    const a = [
      '-y', '-ss', t0.toFixed(2), '-i', webm,
      '-t', dongu.sn.toFixed(2),
      '-c:v', 'libx264', '-preset', 'slow', '-crf', String(crf),
      '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an', HEDEF,
    ];
    const r = spawnSync(ffmpegYolu, a, { encoding: 'utf8' });
    if (r.status !== 0) { console.error(r.stderr?.slice(-2000)); throw new Error('ffmpeg çıkış ' + r.status); }
    return fs.statSync(HEDEF).size;
  };

  let boy = cevir(CRF);
  console.log(`    mp4 (crf ${CRF}): ${(boy / 1048576).toFixed(1)} MB`);
  if (boy > 60 * 1048576) {
    boy = cevir(23);
    console.log(`    mp4 (crf 23): ${(boy / 1048576).toFixed(1)} MB`);
  }

  // kontrol kareleri
  const kareKlasor = path.join(APP, 'qa', 'film');
  fs.mkdirSync(kareKlasor, { recursive: true });
  spawnSync(ffmpegYolu, ['-y', '-i', HEDEF, '-vf', 'fps=1/20', '-frames:v', '5', path.join(kareKlasor, 'film-%02d.png')], { encoding: 'utf8' });
  console.log('    kontrol kareleri:', path.relative(APP, kareKlasor));

  try { fs.rmSync(gecici, { recursive: true, force: true }); } catch { /* yoksay */ }
  console.log('TAMAM →', HEDEF);
}

main().catch((e) => { console.error(e); process.exit(1); });
