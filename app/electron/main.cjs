/**
 * Electron ana süreç — "Bursa Fiber Satış Haritası · Dehanet EÇM".
 *
 * Tasarım kararları (sunum laptopunda tek tık açılsın diye):
 *  - Pencere hazır olana kadar gizli (`show:false`), zemin rengi sahne rengiyle aynı → beyaz parlama yok.
 *  - Tek örnek kilidi: exe'ye iki kez tıklanırsa var olan pencere öne gelir.
 *  - F11 / Esc tam ekran, `--kiosk` ile kiosk modu.
 *  - Türkçe menü: Dosya › Plan Aç… (JSON okur, IPC ile pencereye yollar), Görünüm › Sunum/Keşif.
 *  - Paketliyken DevTools ve gezinme kapalı.
 *  - QA kancası: DSALE_QA_EKRAN=<png> → uygulama hazır olunca capturePage ile kare alır ve kapanır.
 */
const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const fs = require('node:fs');
const path = require('node:path');

const BASLIK = 'Bursa Fiber Satış Haritası · Dehanet EÇM';
const ZEMIN = '#03060D';

// Sunum laptopunda eski sürücüler yüzünden WebGL kara ekran olmasın
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('enable-gpu-rasterization');

/** argv → URL sorgu parametreleri (--mod=kesif --sahne=5 --film --n=25) */
function argvSorgu(argv) {
  const q = {};
  for (const ham of argv) {
    const m = /^--(mod|sahne|adim|n)=(.+)$/.exec(ham);
    if (m) q[m[1]] = m[2];
    else if (ham === '--film') q.film = '1';
    else if (/^--film=(.+)$/.test(ham)) q.film = /^--film=(.+)$/.exec(ham)[1];
  }
  return q;
}

let pencere = null;
let kiosk = false;

function pencereOlustur() {
  const q = argvSorgu(process.argv.slice(1));
  kiosk = process.argv.includes('--kiosk');

  pencere = new BrowserWindow({
    width: 1920,
    height: 1080,
    minWidth: 1280,
    minHeight: 720,
    show: false,
    backgroundColor: ZEMIN,
    title: BASLIK,
    autoHideMenuBar: false,
    kiosk,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false,
      devTools: !app.isPackaged,
    },
  });

  pencere.setMenu(menuKur());
  pencere.once('ready-to-show', () => {
    if (!kiosk) pencere.maximize();
    pencere.show();
    pencere.focus();
  });
  // sayfa başlığı pencere başlığını ezmesin
  pencere.on('page-title-updated', (e) => e.preventDefault());

  const gelistirmeUrl = process.env.DSALE_DEV_URL;
  if (gelistirmeUrl) {
    const u = new URL(gelistirmeUrl);
    for (const [k, v] of Object.entries(q)) u.searchParams.set(k, v);
    pencere.loadURL(u.toString());
  } else {
    pencere.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), { query: q });
  }

  // dış bağlantılar varsayılan tarayıcıda; uygulama içi gezinme yok
  pencere.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  pencere.webContents.on('will-navigate', (e, url) => {
    if (url !== pencere.webContents.getURL()) e.preventDefault();
  });

  // F11 / Esc tam ekran
  pencere.webContents.on('before-input-event', (e, girdi) => {
    if (girdi.type !== 'keyDown') return;
    if (girdi.key === 'F11') {
      e.preventDefault();
      tamEkranDegistir();
    } else if (girdi.key === 'Escape' && pencere.isFullScreen()) {
      e.preventDefault();
      pencere.setFullScreen(false);
    }
  });

  if (process.env.DSALE_QA_EKRAN) qaEkranKancasi(process.env.DSALE_QA_EKRAN);
  pencere.on('closed', () => {
    pencere = null;
  });
}

function tamEkranDegistir() {
  if (!pencere) return;
  pencere.setFullScreen(!pencere.isFullScreen());
}

function moduGonder(mod) {
  pencere?.webContents.send('dsale:mod', mod);
}

async function planSec() {
  if (!pencere) return;
  const s = await dialog.showOpenDialog(pencere, {
    title: 'Plan dosyası seç',
    filters: [{ name: 'Plan (JSON)', extensions: ['json'] }],
    properties: ['openFile'],
  });
  if (s.canceled || !s.filePaths[0]) return;
  planGonder(s.filePaths[0]);
}

function planGonder(dosya) {
  try {
    const icerik = fs.readFileSync(dosya, 'utf8');
    pencere?.webContents.send('dsale:plan', { ad: path.basename(dosya), icerik });
  } catch (e) {
    dialog.showErrorBox('Plan okunamadı', String(e && e.message ? e.message : e));
  }
}

function menuKur() {
  return Menu.buildFromTemplate([
    {
      label: 'Dosya',
      submenu: [
        { label: 'Plan Aç…', accelerator: 'CmdOrCtrl+O', click: planSec },
        { type: 'separator' },
        { label: 'Çıkış', accelerator: 'Alt+F4', role: 'quit' },
      ],
    },
    {
      label: 'Görünüm',
      submenu: [
        { label: 'Tam Ekran', accelerator: 'F11', click: tamEkranDegistir },
        { type: 'separator' },
        { label: 'Sunum', click: () => moduGonder('sunum') },
        { label: 'Keşif', click: () => moduGonder('kesif') },
        { type: 'separator' },
        { label: 'Yeniden Yükle', accelerator: 'CmdOrCtrl+R', click: () => pencere?.reload() },
        ...(app.isPackaged
          ? []
          : [{ label: 'Geliştirici Araçları', accelerator: 'F12', click: () => pencere?.webContents.toggleDevTools() }]),
      ],
    },
    {
      label: 'Yardım',
      submenu: [
        {
          label: 'Hakkında',
          click: () =>
            dialog.showMessageBox(pencere, {
              type: 'info',
              title: 'Hakkında',
              message: BASLIK,
              detail: `Sürüm ${app.getVersion()}\nTURKCELL SUPERONLINE DEHANET EV ÇÖZÜM MERKEZİ\n\nTuşlar: → ← sahne · F film · K keşif · F11 tam ekran`,
              buttons: ['Tamam'],
            }),
        },
      ],
    },
  ]);
}

/** QA: uygulama hazır olunca pencereyi PNG'ye çeker ve çıkar. */
function qaEkranKancasi(hedef) {
  const bekle = async () => {
    const t0 = Date.now();
    while (Date.now() - t0 < 60000) {
      try {
        const hazir = await pencere.webContents.executeJavaScript(
          'Boolean(window.__DSALE__ && window.__DSALE__.hazir && !window.__DSALE__.mesgul)',
        );
        if (hazir) break;
      } catch {
        /* sayfa henüz yüklenmedi */
      }
      await new Promise((r) => setTimeout(r, 300));
    }
    await new Promise((r) => setTimeout(r, 1200));
    const kare = await pencere.webContents.capturePage();
    fs.mkdirSync(path.dirname(hedef), { recursive: true });
    fs.writeFileSync(hedef, kare.toPNG());
    console.log('[qa] ekran görüntüsü:', hedef);
    app.quit();
  };
  pencere.webContents.once('did-finish-load', () => {
    bekle().catch((e) => {
      console.error('[qa]', e);
      app.quit();
    });
  });
}

/* ------------------------------------------------------------------ yaşam döngüsü */

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!pencere) return;
    if (pencere.isMinimized()) pencere.restore();
    pencere.focus();
  });

  ipcMain.handle('dsale:planAc', async () => {
    if (!pencere) return null;
    const s = await dialog.showOpenDialog(pencere, {
      title: 'Plan dosyası seç',
      filters: [{ name: 'Plan (JSON)', extensions: ['json'] }],
      properties: ['openFile'],
    });
    if (s.canceled || !s.filePaths[0]) return null;
    return { ad: path.basename(s.filePaths[0]), icerik: fs.readFileSync(s.filePaths[0], 'utf8') };
  });
  ipcMain.handle('dsale:tamEkran', () => {
    tamEkranDegistir();
    return !!pencere?.isFullScreen();
  });
  ipcMain.handle('dsale:tamEkranMi', () => !!pencere?.isFullScreen());

  app.whenReady().then(() => {
    pencereOlustur();
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) pencereOlustur();
    });
  });

  app.on('window-all-closed', () => app.quit());
}
