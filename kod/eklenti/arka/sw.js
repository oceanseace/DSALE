/*
 * Saha eklentisi — arka plan çalışanı (Manifest V3 service worker).
 *
 * Tek görevi: içerik betikleri / panel ile Saha sunucusu arasında GÜVENLİ aracılık.
 *   · Jeton yalnız burada kullanılır; içerik betikleri jetonu görmez.
 *   · Her mesaj türü yalnız kendi sitesinden kabul edilir (ör. talep yalnız web.whatsapp.com'dan).
 *   · Sunucuya giden gövde burada BEYAZ LİSTEYLE yeniden kurulur (fazladan alan geçmez).
 *   · Hiçbir kişisel veri diske yazılmaz: chrome.storage.local'da yalnız sunucu adresi, jeton ve ayarlar;
 *     kişinin adı chrome.storage.session'da (bellekte, tarayıcı kapanınca silinir).
 *   · Arka planda Turkcell sayfası okunmaz; yalnız kullanıcının açtığı sekmedeki içerik betiği okur.
 */
'use strict';

importScripts('../ortak/metin.js', '../ortak/api.js');

const M = self.DSMetin;
const API = self.DSApi;
const SURUM = chrome.runtime.getManifest().version;

const HOSTLAR = {
  boss: ['boss.turkcell.com.tr', 'boss.superonline.net'],
  owa: ['mail.turkcell.com.tr'],
  whatsapp: ['web.whatsapp.com'],
  atmosfer: ['atmosfer.turkcell.com.tr'],
};
const TUM_HOSTLAR = [].concat(...Object.values(HOSTLAR));

// İçerik betiğinden gelebilecek mesajlar ve kabul edildikleri siteler.
const ICERIK_IZNI = {
  'durum': TUM_HOSTLAR,
  'panel.ac': TUM_HOSTLAR,
  'boss.gonder': HOSTLAR.boss,
  'boss.baglam': HOSTLAR.boss,
  'ticket.gonder': HOSTLAR.owa,
  'talep.gonder': HOSTLAR.whatsapp,
  'rehber.gonder': HOSTLAR.atmosfer,
};
// Yalnız eklentinin kendi sayfalarından (açılır pencere / yan panel) gelebilecek mesajlar.
const SAYFA_MESAJLARI = new Set(['durum', 'eslestir', 'cikis', 'ben', 'giden.liste', 'giden.islendi', 'yapi.gonder', 'ayar.yaz']);

// Mesaj türü → gereken kapsam (sunucu ayrıca kendi yetkisini denetler).
const KAPSAM = {
  'boss.gonder': 'boss.oku',
  'giden.liste': 'boss.giden',
  'giden.islendi': 'boss.giden',
  'ticket.gonder': 'ticket',
  'talep.gonder': 'talep',
  'rehber.gonder': 'rehber',
  'yapi.gonder': 'yapi',
};

// İstemci tarafı hız sınırı (sunucu da sınırlar): [en çok, pencere ms]
const SINIR = {
  'boss.gonder': [12, 60000],
  'ticket.gonder': [20, 60000],
  'talep.gonder': [20, 60000],
  'rehber.gonder': [6, 60000],
  'yapi.gonder': [3, 60000],
  'giden.islendi': [60, 60000],
  'eslestir': [5, 60000],
};
const sayac = new Map();

function sinirAsildi(tur) {
  const s = SINIR[tur];
  if (!s) return false;
  const simdi = Date.now();
  const liste = (sayac.get(tur) || []).filter((t) => simdi - t < s[1]);
  if (liste.length >= s[0]) { sayac.set(tur, liste); return true; }
  liste.push(simdi);
  sayac.set(tur, liste);
  return false;
}

// ------------------------------------------------------------------ depolama
async function eslesmeOku() {
  const { eslesme } = await chrome.storage.local.get('eslesme');
  return eslesme && eslesme.jeton && eslesme.sunucu ? eslesme : null;
}

async function ayarOku() {
  const { ayar } = await chrome.storage.local.get('ayar');
  return Object.assign({ canli_boss: true }, ayar || {});
}

async function eslesmeSil(neden) {
  await chrome.storage.local.remove(['eslesme', 'secici_ek', 'sunucu_ayar']);
  await chrome.storage.session.remove(['ben']);
  if (neden === 'bitti') {
    await chrome.action.setBadgeBackgroundColor({ color: '#c02a2a' });
    await chrome.action.setBadgeText({ text: '!' });
    await chrome.action.setTitle({ title: 'Saha · Eşleşme sona erdi — yeniden bağlanın' });
  } else {
    await rozet(0);
  }
  yayinla();
}

async function rozet(n) {
  await chrome.action.setBadgeBackgroundColor({ color: '#0b63e5' });
  await chrome.action.setBadgeText({ text: n > 0 ? String(n > 99 ? '99+' : n) : '' });
  await chrome.action.setTitle({ title: n > 0 ? 'Saha · ' + n + " iş BOSS'a işlenmeyi bekliyor" : 'Saha' });
}

/** Açık sekmelerdeki içerik betiklerine "durum değişti" haberi (eşleşme / ayar). */
async function yayinla() {
  try {
    const sekmeler = await chrome.tabs.query({ url: TUM_HOSTLAR.map((h) => 'https://' + h + '/*') });
    for (const s of sekmeler) chrome.tabs.sendMessage(s.id, { tur: 'durum.degisti' }).catch(() => {});
  } catch (_) { /* sekme yok */ }
}

// ------------------------------------------------------------------ sunucu
async function sunucu(ad, secenek) {
  const e = await eslesmeOku();
  if (!e) return { ok: false, durum: 401, hata: "Eklenti Saha'ya bağlı değil. Saha simgesine tıklayıp bağlanın.", kod: 'eslesme_yok' };
  const r = await API.cagir(fetch, { sunucu: e.sunucu, jeton: e.jeton }, ad, Object.assign({ surum: SURUM }, secenek || {}));
  if (!r.ok && r.durum === 401) await eslesmeSil('bitti');
  return r;
}

async function sunucuAyariGetir() {
  const r = await sunucu('ayar');
  if (!r.ok || !r.veri || typeof r.veri !== 'object') return;
  const v = r.veri;
  const kayit = {};
  if (v.secici_ek && typeof v.secici_ek === 'object') kayit.secici_ek = v.secici_ek;
  const ayar = {};
  if (typeof v.boss_task_url === 'string' && /^https:\/\/[^/]+\/.*\{task_no\}/.test(v.boss_task_url)) ayar.boss_task_url = v.boss_task_url;
  kayit.sunucu_ayar = ayar;
  await chrome.storage.local.set(kayit);
}

function cihazBilgisi() {
  const ua = (self.navigator && self.navigator.userAgentData) || null;
  const markalar = ua && ua.brands ? ua.brands.map((b) => b.brand).join(' ') : '';
  const tarayici = /Edge/i.test(markalar) ? 'Edge' : /Brave/i.test(markalar) ? 'Brave' : /Chrome/i.test(markalar) ? 'Chrome' : 'Chromium';
  const platform = ua && ua.platform ? ua.platform : '';
  return { ad: (tarayici + (platform ? ' · ' + platform : '')).slice(0, 60), tarayici, platform, eklenti_surum: SURUM };
}

// ------------------------------------------------------------------ gövde kurucular (beyaz liste)
const metin = (v, n) => (typeof v === 'string' ? M.sade(v).slice(0, n) : null) || null;

function sec(o, alanlar, n) {
  const c = {};
  for (const a of alanlar) {
    const v = metin(o && o[a], n || 120);
    if (v) c[a] = v;
  }
  return c;
}

const TASK_ALANLARI = ['task_no', 'task_adi', 'durum', 'ekip', 'lokasyon', 'randevu_durumu', 'randevu_baslangic', 'randevu_bitis', 'merkeze_gonder'];

function bossGovdesi(msg, kapsamlar) {
  const gorunum = msg.gorunum === 'detay' ? 'detay' : 'liste';
  const tasklar = (Array.isArray(msg.tasklar) ? msg.tasklar : []).slice(0, 500)
    .map((t) => sec(t, TASK_ALANLARI))
    .filter((t) => t.task_no && /^[\w-]{4,30}$/.test(t.task_no));
  const g = {
    gorunum,
    otomatik: !!msg.otomatik,
    sayfa: typeof msg.sayfa === 'string' ? msg.sayfa.replace(/\d{3,}/g, '#').slice(0, 120) : null,
    okuma_zamani: new Date().toISOString(),
    tasklar,
  };
  // Müşteri telefonu: yalnız detayda, tek task, kullanıcı onayıyla ve kapsam varsa.
  if (gorunum === 'detay' && tasklar.length === 1 && msg.kullanici_onayi === true && msg.musteri_tel && kapsamlar.includes('boss.tel')) {
    const t = M.telefonDuzelt(msg.musteri_tel);
    if (t) { g.musteri_tel = t; g.kullanici_onayi = true; }
  }
  return g;
}

const DURUMLAR = ['AÇIK', 'ÇÖZÜLDÜ', 'HATA', 'KAPATILDI', 'İPTAL', 'TRANSFER'];

function ticketGovdesi(msg) {
  const no = String(msg.ticket_no || '').toUpperCase();
  if (!/^[A-Z0-9]{6,20}$/.test(no)) return null;
  if (!DURUMLAR.includes(msg.durum)) return null;
  return {
    ticket_no: no,
    durum: msg.durum,
    kaynak: msg.kaynak === 'owa_secim' ? 'owa_secim' : 'owa',
    guven: msg.guven === 'etiketli' ? 'etiketli' : 'tahmin',
    okuma_zamani: new Date().toISOString(),
  };
}

function talepGovdesi(msg) {
  const t = msg.talep || {};
  const tur = ['sinyal_yok', 'ek_kapasite', 'diger'].includes(t.tur) ? t.tur : 'diger';
  const not = typeof t.not === 'string' ? t.not.replace(/\r\n/g, '\n').trim().slice(0, 2000) : '';
  const bina = metin(t.bina, 40);
  if (!not && !bina) return null;
  return {
    tur,
    bina: bina ? bina.toUpperCase() : null,
    not: not || null,
    kaynak: 'whatsapp',
    mesaj_ozeti: typeof t.mesaj_ozeti === 'string' && /^[0-9a-f]{64}$/.test(t.mesaj_ozeti) ? t.mesaj_ozeti : null,
    sohbet: metin(t.sohbet, 120),
    gonderen: metin(t.gonderen, 120),
    mesaj_zamani: t.mesaj_zamani && M.tarihNormal(t.mesaj_zamani) ? M.tarihNormal(t.mesaj_zamani) : null,
    yon: t.yon === 'giden' || t.yon === 'gelen' ? t.yon : null,
  };
}

function rehberGovdesi(msg) {
  const kisiler = (Array.isArray(msg.kisiler) ? msg.kisiler : []).slice(0, 1000)
    .map((k) => ({ ad: metin(k && k.ad, 120), unvan: metin(k && k.unvan, 120), bolum: k && k.bolum === 'yetkili' ? 'yetkili' : 'ekip' }))
    .filter((k) => k.ad);
  if (!kisiler.length) return null;
  return { kaynak: 'atmosfer', kisiler, uygula: msg.uygula === true };
}

// ------------------------------------------------------------------ mesaj yönlendirici
function gondereniDogrula(msg, sender) {
  if (!msg || typeof msg.tur !== 'string' || sender.id !== chrome.runtime.id) return 'yok';
  if (sender.tab) {
    const izinli = ICERIK_IZNI[msg.tur];
    let host = '';
    try { host = new URL(sender.url || sender.tab.url || '').hostname; } catch (_) { host = ''; }
    return izinli && izinli.includes(host) ? 'icerik' : 'yok';
  }
  const sayfa = String(sender.url || '');
  return sayfa.startsWith(chrome.runtime.getURL('arayuz/')) && SAYFA_MESAJLARI.has(msg.tur) ? 'sayfa' : 'yok';
}

async function isle(msg, sender, kaynak) {
  const tur = msg.tur;
  if (sinirAsildi(tur)) return { ok: false, hata: 'Çok sık gönderim. Biraz sonra tekrar deneyin.', kod: 'cok_sik' };

  if (tur === 'durum') {
    const e = await eslesmeOku();
    const ayar = await ayarOku();
    const { secici_ek } = await chrome.storage.local.get('secici_ek');
    return { ok: true, eslesmis: !!e, kapsamlar: e ? e.kapsamlar || [] : [], canli: ayar.canli_boss !== false, secici_ek: secici_ek || null };
  }
  if (tur === 'boss.baglam') return { ok: true };
  if (tur === 'panel.ac') {
    try {
      await chrome.sidePanel.open({ tabId: sender.tab.id });
      return { ok: true };
    } catch (_) {
      return { ok: false, hata: 'Paneli açmak için tarayıcı çubuğundaki Saha simgesine tıklayın.' };
    }
  }

  if (tur === 'eslestir') return eslestir(msg);
  if (tur === 'cikis') return cikis();
  if (tur === 'ben') return ben();
  if (tur === 'ayar.yaz') {
    const ayar = await ayarOku();
    if (typeof msg.canli_boss === 'boolean') ayar.canli_boss = msg.canli_boss;
    await chrome.storage.local.set({ ayar });
    yayinla();
    return { ok: true, ayar };
  }

  const e = await eslesmeOku();
  if (!e) return { ok: false, hata: "Eklenti Saha'ya bağlı değil. Saha simgesine tıklayıp bağlanın.", kod: 'eslesme_yok' };
  const gereken = KAPSAM[tur];
  if (gereken && !(e.kapsamlar || []).includes(gereken)) return { ok: false, hata: 'Bu işlem görevinize kapalı.', kod: 'yasak' };

  switch (tur) {
    case 'boss.gonder': {
      const g = bossGovdesi(msg, e.kapsamlar || []);
      if (!g.tasklar.length) return { ok: false, hata: 'Gönderilecek task bulunamadı.', kod: 'bos' };
      return sunucu('boss_task', { govde: g });
    }
    case 'ticket.gonder': {
      const g = ticketGovdesi(msg);
      if (!g) return { ok: false, hata: 'Ticket numarası ya da durum geçersiz.', kod: 'gecersiz' };
      return sunucu('ticket', { govde: g });
    }
    case 'talep.gonder': {
      const g = talepGovdesi(msg);
      if (!g) return { ok: false, hata: 'Not ya da bina yazın.', kod: 'gecersiz' };
      return sunucu('talep', { govde: g });
    }
    case 'rehber.gonder': {
      const g = rehberGovdesi(msg);
      if (!g) return { ok: false, hata: 'Okunacak çalışan bulunamadı.', kod: 'bos' };
      return sunucu('rehber', { govde: g });
    }
    case 'giden.liste': {
      const r = await sunucu('giden', { zamanAsimi: 15000 });
      if (r.ok && Array.isArray(r.veri)) await rozet(r.veri.length);
      return r;
    }
    case 'giden.islendi': {
      if (!/^[\w.-]{1,64}$/.test(String(msg.is_no || ''))) return { ok: false, hata: 'Geçersiz iş numarası.', kod: 'gecersiz' };
      return sunucu('islendi', { param: { is_no: String(msg.is_no) }, govde: { kaynak: 'eklenti' } });
    }
    case 'yapi.gonder': {
      const d = msg.dokum;
      const json = JSON.stringify(d || null);
      if (!d || typeof d !== 'object' || json.length > 300000) return { ok: false, hata: 'Döküm çok büyük ya da boş.', kod: 'gecersiz' };
      return sunucu('yapi', { govde: { dokum: d, not: metin(msg.not, 300) } });
    }
    default:
      return { ok: false, hata: 'Bilinmeyen işlem.', kod: 'ic' };
  }
}

// ------------------------------------------------------------------ eşleştirme
async function eslestir(msg) {
  const s = API.sunucuDuzelt(msg.sunucu);
  if (!s.ok) return s;
  const kod = String(msg.kod || '').replace(/\D/g, '');
  if (kod.length !== 6) return { ok: false, hata: 'Eşleştirme kodu 6 haneli olmalı.', kod: 'kod' };
  let izin = false;
  try { izin = await chrome.permissions.contains({ origins: [s.desen] }); } catch (_) { izin = false; }
  if (!izin) return { ok: false, hata: 'Bu sunucuyla konuşma izni verilmedi. "Bağlan"a yeniden basıp izin verin.', kod: 'izin_yok' };
  const r = await API.cagir(fetch, { sunucu: s.koken }, 'eslestir', { surum: SURUM, govde: { kod, cihaz: cihazBilgisi() } });
  if (!r.ok) {
    if (r.durum === 401 || r.durum === 400 || r.durum === 410) return { ok: false, hata: (r.veri && r.veri.detail && r.veri.detail.hata) || 'Kod hatalı ya da süresi dolmuş. Uygulamadan yeni kod alın.', kod: 'kod' };
    if (r.kod === 'uc_yok') return { ok: false, hata: "Bu Saha sunucusu eklentiyi henüz desteklemiyor. Saha Sistemi'nin güncellenmesi gerekiyor.", kod: 'uc_yok' };
    return r;
  }
  const v = r.veri || {};
  if (typeof v.jeton !== 'string' || v.jeton.length < 20) return { ok: false, hata: 'Sunucudan geçersiz yanıt geldi.', kod: 'yanit' };
  const kapsamlar = Array.isArray(v.kapsamlar) ? v.kapsamlar.filter((k) => typeof k === 'string').slice(0, 20) : [];
  await chrome.storage.local.set({
    eslesme: { sunucu: s.koken, jeton: v.jeton, cihaz_id: v.cihaz_id || null, kapsamlar, bitis: v.bitis || null },
    son_sunucu: s.koken,
  });
  await chrome.storage.session.set({ ben: benKart(v.kullanici) });
  await sunucuAyariGetir().catch(() => {});
  await rozet(0);
  yayinla();
  return { ok: true, kapsamlar, ben: benKart(v.kullanici), host: s.host };
}

function benKart(k) {
  const x = k || {};
  return {
    ad: metin(x.ad, 80),
    gorevler: Array.isArray(x.gorevler) ? x.gorevler.filter((g) => typeof g === 'string').slice(0, 8) : [],
  };
}

async function ben() {
  const e = await eslesmeOku();
  const { son_sunucu } = await chrome.storage.local.get('son_sunucu');
  const ayar = await ayarOku();
  if (!e) return { ok: true, eslesmis: false, son_sunucu: son_sunucu || '', ayar };
  const r = await sunucu('ben');
  if (!r.ok && r.durum === 401) {
    return { ok: true, eslesmis: false, son_sunucu: e.sunucu, bitti: true, ayar };
  }
  let kart;
  let kapsamlar = e.kapsamlar || [];
  if (r.ok && r.veri) {
    kart = benKart(r.veri.kullanici);
    await chrome.storage.session.set({ ben: kart });
    if (Array.isArray(r.veri.kapsamlar)) {
      kapsamlar = r.veri.kapsamlar.filter((k) => typeof k === 'string').slice(0, 20);
      if (JSON.stringify(kapsamlar) !== JSON.stringify(e.kapsamlar)) {
        await chrome.storage.local.set({ eslesme: Object.assign({}, e, { kapsamlar }) });
        yayinla();
      }
    }
    sunucuAyariGetir().catch(() => {});
  } else {
    kart = (await chrome.storage.session.get('ben')).ben || null;
  }
  const { sunucu_ayar } = await chrome.storage.local.get('sunucu_ayar');
  let host = '';
  try { host = new URL(e.sunucu).host; } catch (_) { /* yok */ }
  return {
    ok: true, eslesmis: true, sunucu: e.sunucu, host, kapsamlar, ben: kart, ayar,
    sunucu_ayar: sunucu_ayar || {}, cevrimdisi: !r.ok, uyari: r.ok ? null : r.hata,
  };
}

async function cikis() {
  const e = await eslesmeOku();
  if (e) {
    await API.cagir(fetch, { sunucu: e.sunucu, jeton: e.jeton }, 'cikis', { surum: SURUM, zamanAsimi: 5000 }).catch(() => {});
    try { await chrome.permissions.remove({ origins: [e.sunucu + '/*'] }); } catch (_) { /* manifest izni ya da zaten yok */ }
  }
  await eslesmeSil('cikis');
  return { ok: true };
}

// ------------------------------------------------------------------ dinleyiciler
chrome.runtime.onMessage.addListener((msg, sender, yanit) => {
  const kaynak = gondereniDogrula(msg, sender);
  if (kaynak === 'yok') return false;
  isle(msg, sender, kaynak).then(yanit, (hata) => {
    yanit({ ok: false, hata: 'Eklentide beklenmeyen hata.', kod: 'ic', ayrinti: String(hata && hata.message || hata).slice(0, 200) });
  });
  return true;
});

chrome.runtime.onInstalled.addListener(() => {
  try { chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' }).catch(() => {}); } catch (_) { /* eski tarayıcı */ }
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'ds-owa-secim',
      title: "Seçili metni Saha'ya işle",
      contexts: ['selection'],
      documentUrlPatterns: ['https://mail.turkcell.com.tr/owa/*'],
    });
  });
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {});
});

chrome.contextMenus.onClicked.addListener((bilgi, sekme) => {
  if (bilgi.menuItemId !== 'ds-owa-secim' || !sekme || !sekme.id) return;
  let host = '';
  try { host = new URL(sekme.url || '').hostname; } catch (_) { return; }
  if (!HOSTLAR.owa.includes(host)) return;
  chrome.tabs.sendMessage(sekme.id, { tur: 'owa.secim', metin: String(bilgi.selectionText || '').slice(0, 20000) }).catch(() => {});
});
