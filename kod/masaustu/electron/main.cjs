/**
 * Dehanet Saha — masaüstü kabuğu (Electron ana süreç).
 *
 * Görevi: SahaSunucu.exe'yi (dondurulmuş Python sunucusu) başlatmak, /api/saglik yanıt verene
 * kadar sakin bir "açılıyor" ekranı göstermek, sonra yönetici ekranını kendi penceresinde açmak.
 * Pencere kapanınca sunucu tepside çalışmaya devam eder (telefonlar bağlı kalır).
 *
 * Veri HİÇBİR ZAMAN kurulum klasörüne yazılmaz: %ProgramData%\DehanetSaha (Ayarlar'dan değişir).
 * Güncelleme = yeni kurulum dosyasını çalıştırmak; veri klasörü olduğu gibi kalır, ilk açılışta
 * sunucu kendi doğrulanmış yedeğini alıp şemayı günceller.
 *
 * Komut satırı (hepsi isteğe bağlı; testler ve yöneticiler için):
 *   --veri=<klasör>  --port=<n>  --yerel | --ag   (bu oturum için ayarları ezer, kaydetmez)
 *   --profil=<klasör>  Electron profil klasörü (ayarlar.json + oturum çerezi) — test yalıtımı
 *   --gizli            pencere açmadan tepside başlar (bilgisayar açılınca başlat)
 *   --kapat            çalışan kopyadan düzgün kapanmasını ister (kurulum programı kullanır)
 *   --dogrula=<json>   sunucu + pencere hazır olunca durumu JSON'a yazar ve kapanır (otomatik test)
 */
'use strict';

const { app, BrowserWindow, Tray, Menu, dialog, shell, nativeImage, ipcMain, clipboard } = require('electron');
const { spawn, execFile } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const net = require('node:net');

const URUN = 'Dehanet Saha';
const ZEMIN = '#EFF1F5';
const HAZIR_ZAMAN_ASIMI_MS = 15 * 60 * 1000; // göç + ilk veri kalitesi hesabı uzun sürebilir
const DURDURMA_BEKLE_MS = 20 * 1000;

/* ------------------------------------------------------------------ komut satırı */
function argDegeri(ad) {
  const on = `--${ad}=`;
  const bulunan = process.argv.find((a) => a.startsWith(on));
  return bulunan ? bulunan.slice(on.length) : null;
}
const ARG = {
  veri: argDegeri('veri'),
  port: argDegeri('port') ? Number(argDegeri('port')) : null,
  ag: process.argv.includes('--yerel') ? false : process.argv.includes('--ag') ? true : null,
  profil: argDegeri('profil'),
  gizli: process.argv.includes('--gizli'),
  kapat: process.argv.includes('--kapat'),
  dogrula: argDegeri('dogrula'),
};
if (ARG.profil) app.setPath('userData', path.resolve(ARG.profil));

/* ------------------------------------------------------------------ yollar */
const PAKETLI = app.isPackaged;
const IKON_DIZINI = PAKETLI ? path.join(process.resourcesPath, 'ikon') : path.join(__dirname, '..', 'build');
const EKRAN = path.join(__dirname, 'ekran');

function sunucuKomutu() {
  const exe = PAKETLI
    ? path.join(process.resourcesPath, 'sunucu', 'SahaSunucu.exe')
    : path.join(__dirname, '..', 'build', 'sunucu', 'SahaSunucu.exe');
  if (fs.existsSync(exe)) return { dosya: exe, onEk: [] };
  // Geliştirme: derlenmemişse repo'daki Python ile çalışır (DEHANET_SAHA_PY=<python.exe>)
  const py = process.env.DEHANET_SAHA_PY;
  if (!PAKETLI && py) return { dosya: py, onEk: [path.join(__dirname, '..', 'sunucu_giris.py')] };
  return null;
}

function varsayilanVeri() {
  const kok = process.env.ProgramData || process.env.ALLUSERSPROFILE || 'C:\\ProgramData';
  return path.join(kok, 'DehanetSaha');
}

/* ------------------------------------------------------------------ ayarlar */
const AYAR_DOSYASI = () => path.join(app.getPath('userData'), 'ayarlar.json');
const VARSAYILAN_AYAR = { veriKlasoru: null, port: 8080, ag: true, otomatikBaslat: false, arkaPlanBilgisi: false };
let ayar = { ...VARSAYILAN_AYAR };

function ayarOku() {
  try {
    ayar = { ...VARSAYILAN_AYAR, ...JSON.parse(fs.readFileSync(AYAR_DOSYASI(), 'utf8')) };
  } catch {
    ayar = { ...VARSAYILAN_AYAR };
  }
}
function ayarYaz() {
  try {
    fs.mkdirSync(path.dirname(AYAR_DOSYASI()), { recursive: true });
    fs.writeFileSync(AYAR_DOSYASI(), JSON.stringify(ayar, null, 2), 'utf8');
  } catch (e) {
    gunluk(`Ayarlar yazılamadı: ${e.message}`);
  }
}
/** Bu oturumda geçerli değerler (komut satırı ayarı ezer). */
const etkin = {
  veri: () => path.resolve(ARG.veri || ayar.veriKlasoru || varsayilanVeri()),
  port: () => ARG.port || Number(ayar.port) || 8080,
  ag: () => (ARG.ag !== null ? ARG.ag : ayar.ag !== false),
};
const host = () => (etkin.ag() ? '0.0.0.0' : '127.0.0.1');
const arayuzAdresi = () => `http://127.0.0.1:${etkin.port()}/`;

/* ------------------------------------------------------------------ günlük */
let gunlukYolu = null;
function yerelZaman() {
  const d = new Date();
  const iki = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())} ${iki(d.getHours())}:${iki(d.getMinutes())}:${iki(d.getSeconds())}`;
}
function gunluk(satir) {
  const metin = `${yerelZaman()}  ${satir}\n`;
  try {
    if (!gunlukYolu) return;
    fs.mkdirSync(path.dirname(gunlukYolu), { recursive: true });
    try {
      if (fs.statSync(gunlukYolu).size > 2 * 1024 * 1024) fs.renameSync(gunlukYolu, `${gunlukYolu}.1`);
    } catch {
      /* ilk satır */
    }
    fs.appendFileSync(gunlukYolu, metin, 'utf8');
  } catch {
    /* günlük yazılamazsa uygulama durmaz */
  }
}

function yazilabilirMi(klasor) {
  try {
    fs.mkdirSync(path.join(klasor, 'kayit'), { recursive: true });
    const deneme = path.join(klasor, 'kayit', '.yazma-denemesi');
    fs.writeFileSync(deneme, 'ok');
    fs.unlinkSync(deneme);
    return null;
  } catch (e) {
    return e.message;
  }
}

/** Veri klasörü yazılabilir mi? Varsayılan (%ProgramData%) yazılamıyorsa kullanıcı profiline geçilir. */
function veriKlasorunuHazirla() {
  const aday = etkin.veri();
  let hata = yazilabilirMi(aday);
  if (hata && !ARG.veri && !ayar.veriKlasoru) {
    const yerel = process.env.LOCALAPPDATA || path.join(app.getPath('appData'), '..', 'Local');
    const yedekYer = path.join(yerel, 'DehanetSaha', 'Veri');
    if (!yazilabilirMi(yedekYer)) {
      ayar.veriKlasoru = path.resolve(yedekYer);
      ayarYaz();
      gunlukYolu = path.join(etkin.veri(), 'kayit', 'masaustu.log');
      gunluk(`${aday} yazılamadı (${hata}); veri klasörü ${etkin.veri()} oldu`);
      return { ok: true, yol: etkin.veri() };
    }
  }
  if (!hata) {
    gunlukYolu = path.join(aday, 'kayit', 'masaustu.log');
    return { ok: true, yol: aday };
  }
  gunlukYolu = path.join(app.getPath('userData'), 'masaustu.log');
  return { ok: false, yol: aday, hata };
}

/* ------------------------------------------------------------------ ağ adresleri */
function yerelIpler() {
  const oncelik = (ad, ip) => {
    let p = 0;
    if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(ip)) p -= 10;
    if (/vethernet|virtual|vmware|hyper-v|vbox|loopback|wsl|docker|bluetooth/i.test(ad)) p += 20;
    return p;
  };
  const liste = [];
  for (const [ad, adresler] of Object.entries(os.networkInterfaces())) {
    for (const a of adresler || []) {
      if (a.family !== 'IPv4' || a.internal || a.address.startsWith('169.254.')) continue;
      liste.push({ ad, ip: a.address, p: oncelik(ad, a.address) });
    }
  }
  return liste.sort((x, y) => x.p - y.p).map((x) => x.ip);
}
function telefonAdresleri() {
  if (!etkin.ag()) return [];
  return yerelIpler().map((ip) => `http://${ip}:${etkin.port()}`);
}

/* ------------------------------------------------------------------ tek seferlik sunucu komutları */
function tekKomut(komut, ekler = [], zamanAsimiMs = 10 * 60 * 1000) {
  return new Promise((coz) => {
    const k = sunucuKomutu();
    if (!k) return coz({ kod: -1, cikti: 'SahaSunucu.exe bulunamadı. Kurulum bozuk olabilir; yeniden kurun.' });
    const argv = [...k.onEk, komut, '--veri', etkin.veri(), '--port', String(etkin.port()), ...ekler];
    let cikti = '';
    let bitti = false;
    const p = spawn(k.dosya, argv, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: cocukOrtami() });
    const zamanlayici = setTimeout(() => {
      if (!bitti) agaciOldur(p.pid);
    }, zamanAsimiMs);
    p.stdout.on('data', (b) => (cikti += b.toString('utf8')));
    p.stderr.on('data', (b) => (cikti += b.toString('utf8')));
    p.on('error', (e) => {
      bitti = true;
      clearTimeout(zamanlayici);
      coz({ kod: -1, cikti: `${cikti}\n${e.message}` });
    });
    p.on('close', (kod) => {
      bitti = true;
      clearTimeout(zamanlayici);
      gunluk(`komut ${komut} → ${kod}`);
      coz({ kod, cikti: cikti.replace(/\r\n/g, '\n').trim() });
    });
  });
}
function cocukOrtami() {
  const e = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' };
  delete e.ELECTRON_RUN_AS_NODE;
  return e;
}
function agaciOldur(pid) {
  if (!pid) return;
  try {
    execFile('taskkill', ['/pid', String(pid), '/T', '/F'], { windowsHide: true }, () => {});
  } catch {
    /* zaten kapanmış */
  }
}

async function veriDurumu() {
  const r = await tekKomut('durum', [], 60 * 1000);
  try {
    return JSON.parse(r.cikti.split(/\r?\n/).filter((s) => s.trim().startsWith('{')).pop());
  } catch {
    return { hata: r.cikti || `Sunucu yanıt vermedi (kod ${r.kod}).` };
  }
}

/* ------------------------------------------------------------------ HTTP yardımcıları */
function saglikAl(port, zamanAsimi = 2500) {
  return new Promise((coz) => {
    const istek = http.get({ host: '127.0.0.1', port, path: '/api/saglik', timeout: zamanAsimi }, (y) => {
      let govde = '';
      y.setEncoding('utf8');
      y.on('data', (p) => (govde += p));
      y.on('end', () => {
        try {
          coz({ durum: y.statusCode, veri: JSON.parse(govde) });
        } catch {
          coz({ durum: y.statusCode, veri: null });
        }
      });
    });
    istek.on('timeout', () => istek.destroy());
    istek.on('error', () => coz(null));
  });
}
function portDoluMu(port) {
  return new Promise((coz) => {
    const s = net.connect({ host: '127.0.0.1', port });
    s.setTimeout(700);
    s.once('connect', () => {
      s.destroy();
      coz(true);
    });
    s.once('timeout', () => {
      s.destroy();
      coz(false);
    });
    s.once('error', () => coz(false));
  });
}
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------------ durum (ekranlar + tepsi) */
// ekran: hazirlaniyor | calisiyor | ilk | yedek-var | kuruluyor | kurulum-tamam | durdu | harici | hata
let durum = { ekran: 'hazirlaniyor', baslik: 'Sunucu açılıyor…', ayrinti: '', satirlar: [], ekstra: {} };
let sunucu = null; // { p, kapaniyor }
let sonSaglik = null;
let cikiliyor = false;

function durumYay(yeni) {
  durum = { ...durum, ...yeni };
  const paket = durumPaketi();
  for (const w of BrowserWindow.getAllWindows()) {
    if (!w.isDestroyed() && w.webContents.getURL().startsWith('file:')) w.webContents.send('dehanet:durum', paket);
  }
  tepsiGuncelle();
  baslikGuncelle();
}
function durumPaketi() {
  return {
    ...durum,
    veri: etkin.veri(),
    port: etkin.port(),
    ag: etkin.ag(),
    adresler: telefonAdresleri(),
    surum: app.getVersion(),
    saglik: sonSaglik ? { surum: sonSaglik.surum, bina: sonSaglik.bina, sema: sonSaglik.sema_surumu } : null,
  };
}

/* ------------------------------------------------------------------ sunucu yaşam döngüsü */
const durDosyasi = () => path.join(etkin.veri(), 'kayit', 'masaustu-dur.istek');

let baslatiliyor = false;
/** Aynı anda iki başlatma olmasın (ör. "Yeniden dene"ye iki kez basıldı). */
async function sunucuyuBaslat() {
  if (baslatiliyor || (sunucu && !sunucu.kapaniyor)) return;
  baslatiliyor = true;
  try {
    await sunucuyuBaslatIc();
  } finally {
    baslatiliyor = false;
  }
}

async function sunucuyuBaslatIc() {
  sonSaglik = null;
  durumYay({ ekran: 'hazirlaniyor', baslik: 'Sunucu açılıyor…', ayrinti: '', satirlar: [] });
  const vk = veriKlasorunuHazirla();
  if (!vk.ok) {
    return durumYay({
      ekran: 'hata',
      baslik: 'Veri klasörüne yazılamıyor',
      ayrinti: `${vk.yol}\n${vk.hata}\n\nAyarlar'dan yazılabilir bir klasör seçin.`,
    });
  }
  gunluk(`--- ${URUN} ${app.getVersion()} · veri ${vk.yol} · ${host()}:${etkin.port()}`);
  if (!sunucuKomutu()) {
    return durumYay({ ekran: 'hata', baslik: 'Sunucu dosyası bulunamadı', ayrinti: 'SahaSunucu.exe eksik. Programı yeniden kurun.' });
  }

  const d = await veriDurumu();
  if (d.hata && !d.db_var) {
    return durumYay({ ekran: 'hata', baslik: 'Veri klasörü okunamadı', ayrinti: d.hata });
  }
  if (!d.db_var) {
    if (d.yedek_sayisi > 0) {
      return durumYay({ ekran: 'yedek-var', baslik: 'Veritabanı bulunamadı', ekstra: { yedekSayisi: d.yedek_sayisi } });
    }
    return durumYay({ ekran: 'ilk', baslik: 'Hoş geldiniz' });
  }
  if (d.db_sema != null && d.hedef_sema != null && d.db_sema > d.hedef_sema) {
    return durumYay({
      ekran: 'hata',
      baslik: 'Bu sürüm verinizden eski',
      ayrinti: `Veritabanı şema v${d.db_sema}, bu program v${d.hedef_sema}. Daha yeni kurulum dosyasını çalıştırın; veriniz değiştirilmedi.`,
    });
  }

  if (await portDoluMu(etkin.port())) {
    const s = await saglikAl(etkin.port());
    if (s && s.veri && s.veri.surum) {
      return durumYay({
        ekran: 'harici',
        baslik: 'Bu bilgisayarda Saha sunucusu zaten açık',
        ayrinti: `Port ${etkin.port()} başka bir Saha sunucusunda (sürüm ${s.veri.surum}). İkinci bir sunucu açılmadı; veriniz korunuyor.`,
      });
    }
    return durumYay({
      ekran: 'hata',
      baslik: `Port ${etkin.port()} kullanımda`,
      ayrinti: 'Başka bir program bu portu kullanıyor. Ayarlar\'dan başka bir port seçin (ör. 8090).',
    });
  }

  const k = sunucuKomutu();
  const argv = [
    ...k.onEk,
    'calistir',
    '--veri', etkin.veri(),
    '--host', host(),
    '--port', String(etkin.port()),
    '--ebeveyn', String(process.pid),
    '--dur-dosyasi', durDosyasi(),
  ];
  gunluk(`sunucu başlatılıyor: ${path.basename(k.dosya)} ${argv.slice(k.onEk.length).join(' ')}`);
  const p = spawn(k.dosya, argv, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: cocukOrtami() });
  const kayit = { p, kapaniyor: false, satirlar: [] };
  sunucu = kayit;
  const satirIsle = (tampon) => {
    for (const ham of tampon.toString('utf8').split(/\r?\n/)) {
      const s = ham.trimEnd();
      if (!s) continue;
      kayit.satirlar.push(s);
      if (kayit.satirlar.length > 300) kayit.satirlar.shift();
      if (durum.ekran === 'hazirlaniyor') {
        const onemli = /Veritabanı|GÜNCELLEME|Güncelle|yedek|Yedek|startup|Veri kalitesi|Harita/i.test(s);
        if (onemli) durumYay({ ayrinti: s.replace(/^\d{4}-\d\d-\d\d [\d:,]+\s+\w+\s+[\w.]+\s+/, '').slice(0, 240) });
      }
    }
  };
  p.stdout.on('data', satirIsle);
  p.stderr.on('data', satirIsle);
  p.on('error', (e) => {
    gunluk(`sunucu başlatılamadı: ${e.message}`);
    if (sunucu === kayit) sunucu = null;
    durumYay({ ekran: 'hata', baslik: 'Sunucu başlatılamadı', ayrinti: e.message });
  });
  p.on('exit', (kod) => {
    gunluk(`sunucu kapandı (kod ${kod})`);
    if (sunucu === kayit) sunucu = null;
    sonSaglik = null;
    if (kayit.kapaniyor || cikiliyor) return;
    const son = kayit.satirlar.slice(-25).join('\n');
    const anlam = {
      2: ['Sunucu zaten çalışıyor', 'Aynı portta başka bir sunucu açık. İkinci bir sunucu açılmadı.'],
      3: ['Güncelleme durdu — veriniz korundu', 'Aşağıdaki mesajın ekran görüntüsünü BT\'ye gönderin.'],
    }[kod] || ['Sunucu beklenmedik şekilde kapandı', 'Aşağıdaki satırları BT\'ye iletin. Veriniz yerinde.'];
    yerelEkranaDon();
    durumYay({ ekran: 'hata', baslik: anlam[0], ayrinti: anlam[1], satirlar: son.split('\n') });
  });

  // /api/saglik yanıt verene kadar bekle
  const t0 = Date.now();
  while (sunucu === kayit && Date.now() - t0 < HAZIR_ZAMAN_ASIMI_MS) {
    const s = await saglikAl(etkin.port());
    if (s && s.durum === 200 && s.veri) {
      sonSaglik = s.veri;
      gunluk(`sunucu hazır (${Math.round((Date.now() - t0) / 1000)} sn) · şema v${s.veri.sema_surumu} · ${s.veri.bina} bina`);
      durumYay({ ekran: 'calisiyor', baslik: 'Çalışıyor', ayrinti: '' });
      arayuzuAc();
      gunlukYedekPlanla();
      return;
    }
    await bekle(700);
  }
  if (sunucu === kayit) {
    durumYay({
      ekran: 'hata',
      baslik: 'Sunucu zamanında açılmadı',
      ayrinti: 'Sunucu 15 dakikada hazır olmadı. Yeniden deneyin; sorun sürerse günlüğü BT\'ye iletin.',
      satirlar: kayit.satirlar.slice(-25),
    });
  }
}

async function sunucuyuDurdur() {
  const kayit = sunucu;
  if (!kayit) return;
  kayit.kapaniyor = true;
  if (!cikiliyor) yerelEkranaDon();
  durumYay({ ekran: 'hazirlaniyor', baslik: 'Sunucu kapatılıyor…', ayrinti: 'Açık kayıtlar tamamlanıyor.' });
  try {
    fs.writeFileSync(durDosyasi(), 'dur', 'utf8');
  } catch (e) {
    gunluk(`durdurma dosyası yazılamadı: ${e.message}`);
  }
  const bitti = new Promise((coz) => {
    if (kayit.p.exitCode !== null) return coz(true);
    kayit.p.once('exit', () => coz(true));
  });
  const sonuc = await Promise.race([bitti, bekle(DURDURMA_BEKLE_MS).then(() => false)]);
  if (!sonuc) {
    gunluk('sunucu 20 sn içinde kapanmadı, sonlandırılıyor');
    agaciOldur(kayit.p.pid);
    await Promise.race([bitti, bekle(5000)]);
  }
  try {
    fs.unlinkSync(durDosyasi());
  } catch {
    /* sunucu sildi */
  }
  if (sunucu === kayit) sunucu = null;
  sonSaglik = null;
}

async function yenidenBaslat() {
  await sunucuyuDurdur();
  // Önceki başlatmanın bekleme döngüsü (en çok ~3 sn) bitsin; yoksa yeni başlatma yutulur.
  for (let i = 0; i < 20 && baslatiliyor; i++) await bekle(250);
  await sunucuyuBaslat();
}

async function durdurVeGoster() {
  await sunucuyuDurdur();
  durumYay({ ekran: 'durdu', baslik: 'Sunucu durduruldu', ayrinti: 'Telefonlar şu an bağlanamaz.' });
  durumEkraniniGoster();
}

/* ------------------------------------------------------------------ günlük yedek */
let yedekZamanlayici = null;
function bugunEtiketi() {
  const d = new Date();
  const iki = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())}`;
}
async function gunlukYedekGerekirse() {
  if (!sunucu || durum.ekran !== 'calisiyor') return;
  const hedef = path.join(etkin.veri(), 'yedek', `saha-${bugunEtiketi()}.db`);
  if (fs.existsSync(hedef)) return;
  const r = await tekKomut('yedek', [], 5 * 60 * 1000);
  gunluk(`otomatik günlük yedek: kod ${r.kod}`);
}
function gunlukYedekPlanla() {
  clearInterval(yedekZamanlayici);
  setTimeout(gunlukYedekGerekirse, 60 * 1000);
  yedekZamanlayici = setInterval(gunlukYedekGerekirse, 60 * 60 * 1000);
}

/* ------------------------------------------------------------------ pencereler */
let pencere = null;
let tepsi = null;
let telefonPenceresi = null;
let ayarPenceresi = null;

function simge(ad) {
  const yol = path.join(IKON_DIZINI, ad);
  return fs.existsSync(yol) ? nativeImage.createFromPath(yol) : nativeImage.createEmpty();
}

function anaPencereOlustur(goster = true) {
  pencere = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 980,
    minHeight: 640,
    show: false,
    backgroundColor: ZEMIN,
    title: URUN,
    icon: path.join(IKON_DIZINI, 'icon.ico'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
      devTools: !PAKETLI,
    },
  });
  pencere.setMenu(menuKur());
  pencere.on('page-title-updated', (e) => e.preventDefault());
  pencere.once('ready-to-show', () => {
    if (goster) {
      pencere.show();
      pencere.focus();
    }
  });
  pencere.on('close', (e) => {
    if (cikiliyor) return;
    e.preventDefault();
    pencere.hide();
    if (!ayar.arkaPlanBilgisi && sunucu && tepsi) {
      ayar.arkaPlanBilgisi = true;
      ayarYaz();
      tepsi.displayBalloon({
        iconType: 'info',
        title: 'Dehanet Saha arka planda çalışıyor',
        content: 'Telefonlar bağlanmaya devam eder. Kapatmak için sağ alttaki simge → Çıkış.',
      });
    }
  });
  pencere.on('closed', () => (pencere = null));
  // Windows oturumu kapanırken sunucu kendini düzgün kapatsın (kabuk süreci de izleniyor; bu ek güvence).
  pencere.on('session-end', () => {
    try {
      fs.writeFileSync(durDosyasi(), 'dur', 'utf8');
    } catch {
      /* */
    }
  });
  gezinmeKurallari(pencere);
  baslikGuncelle();
  if (durum.ekran === 'calisiyor') pencere.loadURL(arayuzAdresi());
  else pencere.loadFile(path.join(EKRAN, 'durum.html'));
}

function gezinmeKurallari(w) {
  const kendiKokeni = (u) => {
    try {
      const x = new URL(u);
      return x.protocol === 'file:' || (x.hostname === '127.0.0.1' && Number(x.port) === etkin.port());
    } catch {
      return false;
    }
  };
  w.webContents.setWindowOpenHandler(({ url }) => {
    if (kendiKokeni(url) && !url.startsWith('file:')) return { action: 'allow' };
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  w.webContents.on('will-navigate', (e, url) => {
    if (kendiKokeni(url)) return;
    e.preventDefault();
    if (/^https?:/i.test(url)) shell.openExternal(url);
  });
  w.webContents.on('before-input-event', (e, girdi) => {
    if (girdi.type !== 'keyDown') return;
    if (girdi.key === 'F5' || (girdi.control && girdi.key.toLowerCase() === 'r')) {
      e.preventDefault();
      w.webContents.reload();
    } else if (girdi.key === 'F11') {
      e.preventDefault();
      w.setFullScreen(!w.isFullScreen());
    }
  });
  // Arayüz yüklenemezse (sunucu o an düştüyse) boş beyaz sayfa kalmasın.
  w.webContents.on('did-fail-load', (_e, kod, aciklama, url, anaCerceve) => {
    if (!anaCerceve || url.startsWith('file:') || kod === -3) return;
    gunluk(`arayüz yüklenemedi: ${kod} ${aciklama}`);
    w.loadFile(path.join(EKRAN, 'durum.html'));
  });
}

function arayuzuAc() {
  if (!pencere) {
    if (!ARG.gizli || ARG.dogrula) anaPencereOlustur(!ARG.gizli);
    return;
  }
  pencere.loadURL(arayuzAdresi());
}

/** Pencere sunucu arayüzünü gösteriyorsa (sunucu kapanacak) yerel durum ekranına döner; öne getirmez. */
function yerelEkranaDon() {
  if (pencere && !pencere.isDestroyed() && !pencere.webContents.getURL().startsWith('file:')) {
    pencere.loadFile(path.join(EKRAN, 'durum.html'));
  }
}

function durumEkraniniGoster() {
  if (!pencere) return anaPencereOlustur(true);
  yerelEkranaDon();
  pencereyiOneGetir();
}

function pencereyiOneGetir() {
  if (!pencere) return anaPencereOlustur(true);
  if (pencere.isMinimized()) pencere.restore();
  pencere.show();
  pencere.focus();
}

function baslikGuncelle() {
  if (!pencere || pencere.isDestroyed()) return;
  let ek = '';
  if (durum.ekran === 'calisiyor') {
    const a = telefonAdresleri();
    ek = etkin.ag() ? (a[0] ? ` — Telefon adresi: ${a[0]}` : ' — ağ bağlantısı yok') : ' — yalnız bu bilgisayar';
  } else if (durum.ekran === 'durdu') ek = ' — sunucu durduruldu';
  pencere.setTitle(`${URUN}${ek}`);
}

function kucukPencere(dosya, genislik, yukseklik, baslik) {
  const w = new BrowserWindow({
    width: genislik,
    height: yukseklik,
    resizable: false,
    minimizable: false,
    maximizable: false,
    show: false,
    backgroundColor: '#FFFFFF',
    title: baslik,
    icon: path.join(IKON_DIZINI, 'icon.ico'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      devTools: !PAKETLI,
    },
  });
  w.setMenu(null);
  w.on('page-title-updated', (e) => e.preventDefault());
  w.once('ready-to-show', () => w.show());
  gezinmeKurallari(w);
  w.loadFile(path.join(EKRAN, dosya));
  return w;
}

function telefonPenceresiAc() {
  if (telefonPenceresi && !telefonPenceresi.isDestroyed()) return telefonPenceresi.focus();
  telefonPenceresi = kucukPencere('telefon.html', 520, 700, 'Telefonla bağlan');
  telefonPenceresi.on('closed', () => (telefonPenceresi = null));
}

function ayarPenceresiAc() {
  if (ayarPenceresi && !ayarPenceresi.isDestroyed()) return ayarPenceresi.focus();
  ayarPenceresi = kucukPencere('ayarlar.html', 580, 690, 'Ayarlar');
  ayarPenceresi.on('closed', () => (ayarPenceresi = null));
}

/* ------------------------------------------------------------------ menü + tepsi */
function sunucuMenusu() {
  const calisiyor = durum.ekran === 'calisiyor';
  const adres = telefonAdresleri()[0];
  return [
    { label: adres ? `Telefon adresi: ${adres}` : 'Telefonla bağlan…', click: telefonPenceresiAc },
    { label: 'Adresi kopyala', enabled: !!adres, click: () => adres && clipboard.writeText(adres) },
    { type: 'separator' },
    calisiyor || sunucu
      ? { label: 'Sunucuyu durdur', click: () => durdurVeGoster() }
      : { label: 'Sunucuyu başlat', click: () => sunucuyuBaslat() },
    { label: 'Yeniden başlat', click: () => yenidenBaslat() },
    { type: 'separator' },
    { label: 'Veri klasörünü aç', click: () => shell.openPath(etkin.veri()) },
    { label: 'Yedek al', click: () => elleYedek() },
    { label: 'Davet kodları…', click: () => davetKodlari() },
    { type: 'separator' },
    { label: 'Ayarlar…', click: ayarPenceresiAc },
  ];
}

function menuKur() {
  return Menu.buildFromTemplate([
    { label: 'Sunucu', submenu: [...sunucuMenusu(), { type: 'separator' }, { label: 'Çıkış', click: () => cikis() }] },
    {
      label: 'Görünüm',
      submenu: [
        { label: 'Yenile', accelerator: 'F5', click: () => pencere?.webContents.reload() },
        { type: 'separator' },
        { label: 'Yakınlaştır', accelerator: 'CmdOrCtrl+=', role: 'zoomIn' },
        { label: 'Uzaklaştır', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' },
        { label: 'Gerçek boyut', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
        { type: 'separator' },
        { label: 'Tam ekran', accelerator: 'F11', role: 'togglefullscreen' },
        ...(PAKETLI ? [] : [{ label: 'Geliştirici araçları', accelerator: 'F12', role: 'toggleDevTools' }]),
      ],
    },
    {
      label: 'Yardım',
      submenu: [
        { label: 'Günlüğü aç', click: () => gunlukYolu && shell.openPath(gunlukYolu) },
        { label: 'Sunucu günlüğünü aç', click: () => shell.openPath(path.join(etkin.veri(), 'kayit', 'saha.log')) },
        { type: 'separator' },
        { label: 'Hakkında', click: hakkinda },
      ],
    },
  ]);
}

let tepsiImzasi = '';
function tepsiGuncelle(zorla = false) {
  if (!tepsi) return;
  const calisiyor = durum.ekran === 'calisiyor';
  // Menüler yalnız durum/ayar değişince yeniden kurulur (açılış satırları her geldiğinde değil).
  const imza = [durum.ekran, !!sunucu, etkin.port(), etkin.ag(), ayar.otomatikBaslat, telefonAdresleri()[0] || ''].join('|');
  if (!zorla && imza === tepsiImzasi) return;
  tepsiImzasi = imza;
  const etiket = {
    calisiyor: 'Çalışıyor',
    hazirlaniyor: 'Hazırlanıyor…',
    kuruluyor: 'Kuruluyor…',
    durdu: 'Durduruldu',
    harici: 'Başka sunucu açık',
    hata: 'Dikkat gerekiyor',
    ilk: 'Kurulum bekliyor',
    'yedek-var': 'Kurulum bekliyor',
    'kurulum-tamam': 'Kurulum tamam',
  }[durum.ekran] || '';
  tepsi.setImage(simge(calisiyor ? 'tepsi.ico' : 'tepsi-durdu.ico'));
  const adres = telefonAdresleri()[0];
  tepsi.setToolTip(`${URUN} · ${etiket}${calisiyor && adres ? `\n${adres}` : ''}`.slice(0, 127));
  tepsi.setContextMenu(
    Menu.buildFromTemplate([
      { label: `${URUN} — ${etiket}`, enabled: false },
      { type: 'separator' },
      { label: 'Pencereyi aç', click: pencereyiOneGetir },
      { type: 'separator' },
      ...sunucuMenusu(),
      {
        label: 'Bilgisayar açılınca başlat',
        type: 'checkbox',
        checked: !!ayar.otomatikBaslat,
        click: (m) => otomatikBaslatAyarla(m.checked),
      },
      { type: 'separator' },
      { label: 'Çıkış', click: () => cikis() },
    ]),
  );
  if (pencere && !pencere.isDestroyed()) pencere.setMenu(menuKur());
}

function tepsiKur() {
  tepsi = new Tray(simge('tepsi-durdu.ico'));
  tepsi.on('click', pencereyiOneGetir);
  tepsi.on('double-click', pencereyiOneGetir);
  tepsiGuncelle();
}

/* ------------------------------------------------------------------ eylemler */
function exeYolu() {
  return process.env.PORTABLE_EXECUTABLE_FILE || process.execPath;
}
function otomatikBaslatAyarla(acik) {
  ayar.otomatikBaslat = !!acik;
  ayarYaz();
  if (PAKETLI) {
    app.setLoginItemSettings({ openAtLogin: !!acik, path: exeYolu(), args: ['--gizli'], name: 'DehanetSaha' });
  }
  tepsiGuncelle();
}

async function elleYedek() {
  if (!fs.existsSync(path.join(etkin.veri(), 'saha.db'))) {
    return dialog.showMessageBox(pencere || undefined, { type: 'info', title: 'Yedek', message: 'Henüz veritabanı yok; yedeklenecek bir şey yok.' });
  }
  const r = await tekKomut('yedek', [], 5 * 60 * 1000);
  const tamam = r.kod === 0;
  const secim = await dialog.showMessageBox(pencere && pencere.isVisible() ? pencere : undefined, {
    type: tamam ? 'info' : 'warning',
    title: 'Yedek',
    message: tamam ? 'Yedek alındı.' : 'Yedek alınamadı.',
    detail: r.cikti.slice(0, 1500),
    buttons: tamam ? ['Tamam', 'Yedek klasörünü aç'] : ['Tamam'],
    defaultId: 0,
  });
  if (tamam && secim.response === 1) shell.openPath(path.join(etkin.veri(), 'yedek'));
}

async function davetKodlari() {
  if (!fs.existsSync(path.join(etkin.veri(), 'saha.db'))) return;
  const r = await tekKomut('kodlar', [], 2 * 60 * 1000);
  const secim = await dialog.showMessageBox(pencere && pencere.isVisible() ? pencere : undefined, {
    type: 'info',
    title: 'Davet kodları',
    message: 'PIN belirlememiş kişilerin ilk giriş kodları',
    detail: `${r.cikti.slice(0, 3000)}\n\nKodu kişiye sözlü verin; kişi ilk girişte kendi PIN'ini belirler.`,
    buttons: ['Kapat', 'Kopyala'],
    defaultId: 0,
  });
  if (secim.response === 1) clipboard.writeText(r.cikti);
}

function hakkinda() {
  const s = sonSaglik;
  dialog.showMessageBox(pencere || undefined, {
    type: 'info',
    title: 'Hakkında',
    message: URUN,
    detail: [
      `Masaüstü sürümü ${app.getVersion()}`,
      s ? `Sunucu ${s.surum} · şema v${s.sema_surumu} · ${Number(s.bina).toLocaleString('tr-TR')} bina` : 'Sunucu kapalı',
      `Veri klasörü: ${etkin.veri()}`,
      `Adres: ${etkin.ag() ? 'ofis ağı' : 'yalnız bu bilgisayar'} · port ${etkin.port()}`,
      '',
      'TURKCELL SUPERONLINE DEHANET EV ÇÖZÜM MERKEZİ',
    ].join('\n'),
    buttons: ['Tamam'],
  });
}

async function yeniKurulum(yineDe = false) {
  durumYay({ ekran: 'kuruluyor', baslik: 'Veritabanı kuruluyor…', ayrinti: '19.706 bina yükleniyor, kalite kuralları uygulanıyor. Bir dakikadan kısa sürer.' });
  const r = await tekKomut('kur', yineDe ? ['--yine-de'] : [], 15 * 60 * 1000);
  if (r.kod !== 0) {
    return durumYay({ ekran: 'hata', baslik: 'Kurulum tamamlanamadı', ayrinti: 'Aşağıdaki satırları BT\'ye iletin. Hiçbir veri silinmedi.', satirlar: r.cikti.split(/\r?\n/).slice(-25) });
  }
  durumYay({ ekran: 'kurulum-tamam', baslik: 'Kurulum tamam', ayrinti: '', ekstra: { cikti: r.cikti } });
}

async function iceAktar() {
  const secim = await dialog.showOpenDialog(pencere || undefined, {
    title: 'Var olan Saha verisini seçin (saha.db)',
    defaultPath: path.join(os.homedir(), 'Documents'),
    filters: [{ name: 'Saha veritabanı', extensions: ['db'] }],
    properties: ['openFile'],
  });
  if (secim.canceled || !secim.filePaths[0]) return;
  durumYay({ ekran: 'kuruluyor', baslik: 'Veri getiriliyor…', ayrinti: 'Kaynak dosyaya yalnız okunur dokunuluyor; kopya doğrulanıyor.' });
  const r = await tekKomut('ice-aktar', ['--kaynak', secim.filePaths[0]], 10 * 60 * 1000);
  if (r.kod !== 0) {
    return durumYay({ ekran: 'hata', baslik: 'Veri getirilemedi', ayrinti: r.cikti.slice(0, 1200) || `Kod ${r.kod}` });
  }
  durumYay({ ekran: 'kurulum-tamam', baslik: 'Veri getirildi', ayrinti: 'Eski sunucuyu artık açmayın: iki sunucu aynı anda çalışırsa kayıtlar ikiye bölünür.', ekstra: { cikti: r.cikti } });
}

async function geriYukle(enYeni) {
  let dosya = null;
  const yedekDizini = path.join(etkin.veri(), 'yedek');
  if (enYeni) {
    const adaylar = [];
    for (const d of [yedekDizini, path.join(yedekDizini, 'goc')]) {
      try {
        for (const ad of fs.readdirSync(d)) {
          if (/^saha-.*\.db$/.test(ad)) {
            const yol = path.join(d, ad);
            adaylar.push({ yol, t: fs.statSync(yol).mtimeMs });
          }
        }
      } catch {
        /* klasör yok */
      }
    }
    adaylar.sort((a, b) => b.t - a.t);
    dosya = adaylar[0]?.yol;
  } else {
    const secim = await dialog.showOpenDialog(pencere || undefined, {
      title: 'Geri yüklenecek yedeği seçin',
      defaultPath: yedekDizini,
      filters: [{ name: 'Saha yedeği', extensions: ['db'] }],
      properties: ['openFile'],
    });
    if (secim.canceled) return;
    dosya = secim.filePaths[0];
  }
  if (!dosya) return;
  durumYay({ ekran: 'kuruluyor', baslik: 'Yedek geri yükleniyor…', ayrinti: path.basename(dosya) });
  const r = await tekKomut('geri-yukle', ['--dosya', dosya], 5 * 60 * 1000);
  if (r.kod !== 0) return durumYay({ ekran: 'hata', baslik: 'Geri yüklenemedi', ayrinti: r.cikti.slice(0, 1200) });
  await sunucuyuBaslat();
}

async function veriKlasoruSec() {
  const secim = await dialog.showOpenDialog(ayarPenceresi || pencere || undefined, {
    title: 'Veri klasörünü seçin',
    defaultPath: etkin.veri(),
    properties: ['openDirectory', 'createDirectory'],
  });
  if (secim.canceled || !secim.filePaths[0]) return null;
  return secim.filePaths[0];
}

async function ayarKaydet(yeni) {
  const onceki = { veri: etkin.veri(), port: etkin.port(), ag: etkin.ag() };
  const port = Math.round(Number(yeni.port));
  if (!(port >= 1024 && port <= 65535)) return { ok: false, hata: 'Port 1024 ile 65535 arasında olmalı.' };
  ayar.port = port;
  ayar.ag = !!yeni.ag;
  if (yeni.veriKlasoru) ayar.veriKlasoru = path.resolve(yeni.veriKlasoru) === path.resolve(varsayilanVeri()) ? null : path.resolve(yeni.veriKlasoru);
  ayarYaz();
  if (!!yeni.otomatikBaslat !== !!ayar.otomatikBaslat) otomatikBaslatAyarla(!!yeni.otomatikBaslat);
  const degisti = onceki.veri !== etkin.veri() || onceki.port !== etkin.port() || onceki.ag !== etkin.ag();
  tepsiGuncelle(true);
  if (degisti) {
    // Eski veri klasöründeki sunucu durdurulur; yeni ayarla yeniden açılır (Ayarlar penceresi beklemez).
    (async () => {
      const kayit = sunucu;
      if (kayit) {
        kayit.kapaniyor = true;
        yerelEkranaDon();
        durumYay({ ekran: 'hazirlaniyor', baslik: 'Sunucu yeni ayarla açılıyor…', ayrinti: '' });
        try {
          fs.writeFileSync(path.join(onceki.veri, 'kayit', 'masaustu-dur.istek'), 'dur', 'utf8');
        } catch {
          /* sunucu yine de 20 sn sonra sonlandırılır */
        }
        await Promise.race([
          new Promise((r) => (kayit.p.exitCode !== null ? r() : kayit.p.once('exit', r))),
          bekle(DURDURMA_BEKLE_MS),
        ]);
        if (kayit.p.exitCode === null) agaciOldur(kayit.p.pid);
        if (sunucu === kayit) sunucu = null;
      }
      for (let i = 0; i < 20 && baslatiliyor; i++) await bekle(250);
      durumEkraniniGoster();
      await sunucuyuBaslat();
    })();
  }
  return { ok: true, yenidenBaslatildi: degisti };
}

function qrSvg(metin) {
  const uret = require('qrcode-generator');
  const qr = uret(0, 'M');
  qr.addData(metin);
  qr.make();
  const n = qr.getModuleCount();
  const k = 2; // kenar boşluğu (modül)
  let yol = '';
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (qr.isDark(y, x)) yol += `M${x + k} ${y + k}h1v1h-1z`;
  const t = n + 2 * k;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${t} ${t}" shape-rendering="crispEdges"><rect width="${t}" height="${t}" fill="#fff"/><path d="${yol}" fill="#1d1d1f"/></svg>`;
}

/* ------------------------------------------------------------------ IPC (yalnız yerel ekranlar) */
function yerelMi(olay) {
  const url = olay.senderFrame ? olay.senderFrame.url : '';
  return typeof url === 'string' && url.startsWith('file:');
}
function ipcKur() {
  ipcMain.handle('dehanet:durum', (e) => (yerelMi(e) ? durumPaketi() : null));
  ipcMain.handle('dehanet:ayarlar', (e) =>
    yerelMi(e)
      ? { veriKlasoru: etkin.veri(), varsayilanVeri: varsayilanVeri(), port: etkin.port(), ag: etkin.ag(), otomatikBaslat: !!ayar.otomatikBaslat, gecici: !!(ARG.veri || ARG.port || ARG.ag !== null) }
      : null,
  );
  ipcMain.handle('dehanet:telefon', (e) => {
    if (!yerelMi(e)) return null;
    const adresler = telefonAdresleri();
    return { ag: etkin.ag(), calisiyor: durum.ekran === 'calisiyor', adresler, qr: adresler[0] ? qrSvg(adresler[0]) : null };
  });
  ipcMain.handle('dehanet:eylem', async (e, ad, veri) => {
    if (!yerelMi(e)) return null;
    switch (ad) {
      case 'yeniKurulum':
        return yeniKurulum(false);
      case 'bosKurulum':
        return yeniKurulum(true);
      case 'iceAktar':
        return iceAktar();
      case 'geriYukleEnYeni':
        return geriYukle(true);
      case 'yedekSec':
        return geriYukle(false);
      case 'baslat':
      case 'yenidenDene':
        return sunucu ? yenidenBaslat() : sunucuyuBaslat();
      case 'hariciAc':
        return pencere?.loadURL(arayuzAdresi());
      case 'arayuzuAc':
        return durum.ekran === 'calisiyor' ? pencere?.loadURL(arayuzAdresi()) : null;
      case 'gunluguAc':
        return shell.openPath(path.join(etkin.veri(), 'kayit', 'saha.log'));
      case 'veriKlasorunuAc':
        return shell.openPath(etkin.veri());
      case 'ayarlar':
        return ayarPenceresiAc();
      case 'telefon':
        return telefonPenceresiAc();
      case 'kopyala':
        return clipboard.writeText(String(veri || ''));
      case 'veriKlasoruSec':
        return veriKlasoruSec();
      case 'ayarKaydet':
        return ayarKaydet(veri || {});
      case 'agiAc':
        return ayarKaydet({ port: etkin.port(), ag: true, veriKlasoru: ayar.veriKlasoru, otomatikBaslat: ayar.otomatikBaslat });
      case 'pencereyiKapat':
        return BrowserWindow.fromWebContents(e.sender)?.close();
      default:
        return null;
    }
  });
}

/* ------------------------------------------------------------------ çıkış */
async function cikis() {
  if (cikiliyor) return;
  cikiliyor = true;
  gunluk('çıkış: sunucu düzgün kapatılıyor');
  clearInterval(yedekZamanlayici);
  try {
    await sunucuyuDurdur();
  } finally {
    if (tepsi) tepsi.destroy();
    app.exit(0);
  }
}

/* ------------------------------------------------------------------ otomatik doğrulama (--dogrula) */
function dogrulamaKancasi() {
  if (!ARG.dogrula) return;
  const t0 = Date.now();
  // Yalnız yapısal alanlar: sağlık yanıtındaki yardım adı/telefonu gibi kişisel alanlar dosyaya yazılmaz.
  const ALANLAR = ['ok', 'surum', 'bina', 'sema_surumu', 'guncelleme_bekliyor', 'kullanici', 'yazilabilir', 'uyari', 'bolge_sayisi', 'bos_disk_mb'];
  const yaz = async (ek) => {
    const saglik = sonSaglik ? Object.fromEntries(ALANLAR.map((k) => [k, sonSaglik[k]])) : null;
    const sonuc = { zaman: new Date().toISOString(), sure_sn: Math.round((Date.now() - t0) / 1000), ekran: durum.ekran, baslik: durum.baslik, saglik, ...ek };
    fs.mkdirSync(path.dirname(path.resolve(ARG.dogrula)), { recursive: true });
    fs.writeFileSync(path.resolve(ARG.dogrula), JSON.stringify(sonuc, null, 2), 'utf8');
    await cikis();
  };
  const kareAl = async () => {
    if (!process.env.DEHANET_DOGRULA_PNG || !pencere) return null;
    const kare = await pencere.webContents.capturePage();
    fs.writeFileSync(process.env.DEHANET_DOGRULA_PNG, kare.toPNG());
    return process.env.DEHANET_DOGRULA_PNG;
  };
  const dene = setInterval(async () => {
    if (durum.ekran === 'hata' || durum.ekran === 'ilk' || durum.ekran === 'yedek-var' || durum.ekran === 'harici') {
      clearInterval(dene);
      await bekle(1200);
      const ekranGoruntusu = await kareAl();
      return yaz({ yuklendi: false, ayrinti: durum.ayrinti, satirlar: durum.satirlar, ekranGoruntusu });
    }
    if (durum.ekran !== 'calisiyor' || !pencere) return;
    const url = pencere.webContents.getURL();
    if (!url.startsWith('http') || pencere.webContents.isLoading()) return;
    clearInterval(dene);
    await bekle(2500); // uygulama kabuğu çizilsin
    let dom = null;
    try {
      dom = await pencere.webContents.executeJavaScript(
        `({ baslik: document.title, kok: !!document.querySelector('#kok, #root, #uygulama, body > div'), metinUzunlugu: document.body ? document.body.innerText.length : 0, sw: 'serviceWorker' in navigator })`,
      );
    } catch (e) {
      dom = { hata: String(e) };
    }
    const ekranGoruntusu = await kareAl();
    yaz({ yuklendi: true, url, pencere_basligi: pencere.getTitle(), dom, ekranGoruntusu, sunucu_pid: sunucu?.p.pid || null });
  }, 500);
  setTimeout(() => yaz({ yuklendi: false, zaman_asimi: true }), HAZIR_ZAMAN_ASIMI_MS);
}

/* ------------------------------------------------------------------ başlangıç */
if (ARG.kapat) {
  // Kilit isteği çalışan kopyaya 'second-instance' (argv'de --kapat) olarak EŞZAMANLI iletilir;
  // o kopya sunucuyu düzgün kapatıp çıkar. Bu kopya her durumda hemen çıkar (kurulum programı bekler).
  app.requestSingleInstanceLock();
  app.exit(0);
} else if (!app.requestSingleInstanceLock()) {
  app.exit(0);
} else {
  app.setAppUserModelId('com.dehanet.saha');
  app.on('second-instance', (_e, argv) => {
    if (argv.includes('--kapat')) return cikis();
    pencereyiOneGetir();
  });
  app.on('window-all-closed', () => {
    /* tepside kalır */
  });
  app.on('before-quit', (e) => {
    if (!cikiliyor) {
      e.preventDefault();
      cikis();
    }
  });

  app.whenReady().then(() => {
    ayarOku();
    veriKlasorunuHazirla();
    ipcKur();
    tepsiKur();
    if (!ARG.gizli || ARG.dogrula) anaPencereOlustur(!ARG.gizli);
    dogrulamaKancasi();
    sunucuyuBaslat();
  });
}
