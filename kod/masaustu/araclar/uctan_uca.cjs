#!/usr/bin/env node
/**
 * Paketli masaüstü uygulamasının uçtan uca denemesi (gerçek veriye DOKUNMAZ).
 *
 *   node kod\masaustu\araclar\uctan_uca.cjs [--exe=<DehanetSaha.exe>] [--kok=<karalama klasörü>]
 *                                        [--kaynak=<saha.db kopyası>] [--port=8113]
 *
 * Senaryo 1 (her zaman): boş veri klasörü → "Hoş geldiniz" → Yeni kurulum → Sunucuyu başlat →
 *   yönetici giriş ekranı + /api/saglik → yerel ekranlarda köprü var, sunucu sayfasında YOK →
 *   ikinci kopya --kapat → birinci kopya sunucuyu düzgün kapatıp çıkar, süreç kalmaz.
 * Senaryo 2 (--kaynak verilirse): "Var olan veriyi getir" (dosya seçimi taklit edilir) → ilk açılışta
 *   doğrulanmış yedekli göç → yönetici ekranı → --kapat.
 *
 * Varsayılan karalama kökü %TEMP%\DehanetSahaDeneme; iş bitince silinir. Canlı klasöre ve 8080'e
 * yöneltmeyin. Kişisel veri içeren hiçbir ekranın görüntüsü alınmaz; çıktı yalnız sayı/durumdur.
 * playwright-core: kod/masaustu, kod/sunum ya da kod/arayuz node_modules klasöründen bulunur.
 */
'use strict';
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { spawnSync, execSync } = require('node:child_process');

const MASAUSTU = path.resolve(__dirname, '..');
const arg = (ad, varsayilan) => {
  const a = process.argv.find((x) => x.startsWith(`--${ad}=`));
  return a ? a.slice(ad.length + 3) : varsayilan;
};
const EXE = path.resolve(arg('exe', path.join(MASAUSTU, 'dist', 'win-unpacked', 'DehanetSaha.exe')));
const KOK = path.resolve(arg('kok', path.join(os.tmpdir(), 'DehanetSahaDeneme')));
const KAYNAK = arg('kaynak', null);
const PORT = Number(arg('port', '8113'));
if (PORT === 8080) {
  console.error('8080 canlı sunucunun portudur; başka bir port verin.');
  process.exit(2);
}

function playwright() {
  // kod/masaustu → kardeş klasörler kod/sunum ve kod/arayuz
  for (const d of [MASAUSTU, path.join(MASAUSTU, '..', 'sunum'), path.join(MASAUSTU, '..', 'arayuz')]) {
    try {
      return require(require.resolve('playwright-core', { paths: [d] }));
    } catch {
      /* sıradaki */
    }
  }
  throw new Error('playwright-core bulunamadı (kod/sunum ya da kod/arayuz içinde npm install).');
}
const { _electron } = playwright();

const sonuc = { exe: EXE, senaryolar: {} };
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

async function kapatVeDenetle(uyg, profil, s) {
  const t = Date.now();
  const k = spawnSync(EXE, ['--kapat', `--profil=${profil}`], { timeout: 60000 });
  s.kapat = { kod: k.status, sure_ms: Date.now() - t };
  const proc = uyg.process();
  s.birinci_kopya_kapandi = await Promise.race([
    proc.exitCode !== null ? Promise.resolve(true) : new Promise((r) => proc.once('exit', () => r(true))),
    bekle(40000).then(() => false),
  ]);
  await bekle(1500);
  s.sunucu_sureci_kaldi = /SahaSunucu\.exe/i.test(execSync('tasklist /FI "IMAGENAME eq SahaSunucu.exe" /NH').toString());
  if (!s.birinci_kopya_kapandi) await uyg.close().catch(() => {});
}

async function arayuzuDenetle(w, s) {
  await w.waitForURL(`http://127.0.0.1:${PORT}/**`, { timeout: 15 * 60000 });
  await w.waitForLoadState('domcontentloaded');
  await bekle(1500);
  s.arayuz_basligi = await w.title();
  const g = await w.evaluate(async () => (await fetch('/api/saglik')).json());
  s.saglik = { ok: g.ok, bina: g.bina, sema: g.sema_surumu, kullanici: g.kullanici, guncelleme_bekliyor: g.guncelleme_bekliyor, uyari: g.uyari };
  s.sunucu_sayfasinda_kopru_yok = await w.evaluate(() => typeof window.dehanet === 'undefined');
}

async function senaryo1() {
  const s = (sonuc.senaryolar.ilk_kurulum = {});
  const veri = path.join(KOK, 'veri1');
  const profil = path.join(KOK, 'profil1');
  const uyg = await _electron.launch({ executablePath: EXE, args: [`--veri=${veri}`, `--port=${PORT}`, '--yerel', `--profil=${profil}`], timeout: 120000 });
  const w = await uyg.firstWindow();
  await w.waitForSelector('text=Hoş geldiniz', { timeout: 60000 });
  s.yerel_ekranda_kopru = await w.evaluate(() => typeof window.dehanet);
  await w.click('text=Yeni kurulum');
  await w.waitForSelector('#tamam:not(.gizli)', { timeout: 15 * 60000 });
  s.kurulum_19706_bina = /Bina\s+:\s+19\.706/.test(await w.textContent('#cikti'));
  await w.click('#tamam >> text=Sunucuyu başlat');
  await arayuzuDenetle(w, s);
  await kapatVeDenetle(uyg, profil, s);
  s.veri_klasoru = fs.readdirSync(veri).sort();
}

async function senaryo2() {
  const s = (sonuc.senaryolar.var_olan_veri = {});
  const veri = path.join(KOK, 'veri2');
  const profil = path.join(KOK, 'profil2');
  const kopya = path.join(KOK, 'kaynak', 'saha.db');
  fs.mkdirSync(path.dirname(kopya), { recursive: true });
  fs.copyFileSync(KAYNAK, kopya);
  fs.chmodSync(kopya, 0o666);
  const uyg = await _electron.launch({ executablePath: EXE, args: [`--veri=${veri}`, `--port=${PORT}`, '--yerel', `--profil=${profil}`], timeout: 120000 });
  await uyg.evaluate(({ dialog }, yol) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [yol] });
  }, kopya);
  const w = await uyg.firstWindow();
  await w.waitForSelector('text=Hoş geldiniz', { timeout: 60000 });
  await w.click('text=Var olan veriyi getir');
  await w.waitForSelector('#tamam:not(.gizli)', { timeout: 10 * 60000 });
  s.getirme_baslik = await w.textContent('#baslik');
  await w.click('#tamam >> text=Sunucuyu başlat');
  await arayuzuDenetle(w, s);
  const goc = path.join(veri, 'yedek', 'goc');
  s.goc_yedegi_sayisi = fs.existsSync(goc) ? fs.readdirSync(goc).filter((a) => a.endsWith('.db')).length : 0;
  await kapatVeDenetle(uyg, profil, s);
}

(async () => {
  if (!fs.existsSync(EXE)) throw new Error(`Uygulama yok: ${EXE} (önce DERLE.bat)`);
  fs.rmSync(KOK, { recursive: true, force: true });
  await senaryo1();
  if (KAYNAK) await senaryo2();
  const hatalar = [];
  for (const [ad, s] of Object.entries(sonuc.senaryolar)) {
    if (!s.saglik || !s.saglik.ok || s.saglik.bina !== 19706) hatalar.push(`${ad}: sağlık`);
    if (!s.sunucu_sayfasinda_kopru_yok) hatalar.push(`${ad}: köprü sunucu sayfasına sızdı`);
    if (!s.birinci_kopya_kapandi || s.sunucu_sureci_kaldi) hatalar.push(`${ad}: düzgün kapanmadı`);
    if (s.kapat && s.kapat.kod !== 0) hatalar.push(`${ad}: --kapat kodu ${s.kapat.kod}`);
  }
  sonuc.hatalar = hatalar;
  console.log(JSON.stringify(sonuc, null, 2));
  fs.rmSync(KOK, { recursive: true, force: true });
  process.exit(hatalar.length ? 1 : 0);
})().catch((e) => {
  console.error('DENEME DURDU:', e && e.message ? e.message : e);
  console.error(JSON.stringify(sonuc, null, 2));
  process.exit(1);
});
