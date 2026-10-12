// Arka plan: BOSS sekmesi açıkken ~2 dakikada bir (ve panelden "Şimdi eşitle" ile) Teknik Havuz listesini
// sayfadaki kancaya okutur, görevleri eslem.js ile sade biçime çevirir ve yerel uygulamaya yollar
// (http://127.0.0.1:<port>/api/boss/esitle, eşleme koduyla).
// - BOSS oturum bilgisi buraya HİÇ gelmez (kanca kendi belleğinde tutar).
// - Müşteri verisi yalnız chrome.storage.session'da (bellek; tarayıcı kapanınca silinir) ve yerel uygulamada.
// - chrome.storage.local'da yalnız ayarlar (port, eşleme kodu, kayıt modu) ve DEĞERSİZ yapı kayıtları durur.
// - BOSS sekmesine ulaşılamazsa (eklenti yenilendi / uygulama yeniden başladı) içerik betikleri sekmeye yeniden
//   yüklenir (sekmeyeGonder); kullanıcıdan sayfayı yenilemesi istenmez.
// - BOSS'a yazma: sunucunun yazılacakları sekmedeki kancaya iletilir. Gerçek gönderim yalnız şablon doğrulanmışsa
//   ve (genel anahtar açık [ayar.boss_yazma, varsayılan KAPALI] ya da eylemin kendi anahtarı açık [eylem_acik; not
//   için varsayılan AÇIK] ya da yöneticinin "tek iş denemesi", deneme: true); aksi hâlde kanca yalnız "önizleme" der.
//   Sonuç (HTTP + BOSS returnCode/returnMessage) /api/boss/yazma-sonucu'na gider (yazilacaklariSor). Sunucu işe özgü
//   askı nedeni kataloğu isterse (okunacaklar) kanca o tek GET'i yapar.
// - Ayrıntı önden okuma: sunucu ayrıntısı saklı olmayan (ya da değişmiş) açık işleri, kullanıcının önce açacağı işler
//   başta olmak üzere verir (detay_onden); kanca her işin sekmelerini en çok 3 istekle okur, her iş okununca
//   /api/boss/detay-onden'e gider, yanıt sıradaki işleri verir. Hiçbir sonuç düşürülmez (servis çalışanı uyuyup
//   uyansa da). Sürmeyen okuma yoklamada (ondenDevam) sunucudan sıradakileri isteyip kaldığı yerden sürer: internet,
//   bilgisayar ya da uygulama kesintisinden sonra da (sunucu ayrıntısı saklı olmayan işleri bilir).
// - Kullanıcının açtığı işin ayrıntısı: /api/boss/istekler uzun yoklamayla (bekle=20) sorulur; istek gelir gelmez
//   kancaya gider (9 sekme aynı anda), önden okuma o sırada bekler.
// - Panel sayacı: büyük sayı SON BAŞARILI eşitlemenin açık iş sayısıdır (esitleme.acik); eşitleme sürerken yalnız
//   esitleme.suruyor işaretlenir, sayı sıfırlanmaz.
// - BOSS ile giriş: Turkcell.exe giriş ekranı Brave'de http://127.0.0.1:<port>/boss-giris/<istek> açar; bu sekme
//   adresinden istek kimliği alınır (girisIstegi, 2 dk) ve sekme BOSS'a geçirilir. Kanca BOSS kullanıcısının kimliğini
//   (yalnız ad/kod/unvan) bildirince /api/giris/boss/kimlik'e gider (tek kez). BOSS oturumu bitince (kanca
//   "oturum-bitti") /api/giris/boss/bitti: o kullanıcının BOSS'la açılmış uygulama oturumu kapanır. Şifre/kod ve
//   oturum jetonu buraya HİÇ gelmez.
// - Ekip GPS konumu: BOSS sekmesi açıkken 2 dk'da bir (alarm 'ekip-konum') bir sekmedeki kancaya "konum-oku" denir;
//   kanca BOSS "GPS Takip" ucunu sayfanın başlıklarıyla bir kez okur. Ham yanıt (ve sayfanın kendi GPS yanıtları,
//   en çok 30 sn'de bir) /api/boss/ekip-konum'a gider; eklentide saklanmaz.
try { importScripts('eslem.js'); } catch (e) { /* test ortamı eslem'i kendisi yükler */ }
// OneMap bina eşitlemesi (BOSS'tan bağımsız; kendi alarmı ve mesajları): onemap_arka.js
try { importScripts('onemap_arka.js'); } catch (e) { /* test ortamı ayrıca yükler */ }
const E = self.DehanetEslem;

chrome.sidePanel && chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

const ACIK_DURUMLAR = ['Açık', 'Başlandı', 'Ertelendi', 'Merkeze gönderildi', 'Konum paylaşıldı', 'Randevu alındı',
  'Askıya alındı', 'Randevusuz'];
const KAPALI_DURUMLAR = ['Tamamlandı', 'FOX tarafından iptal edildi', 'İptal edildi'];
const ARALIK_DK = 2;
const ZAMAN_ASIMI_MS = 4 * 60 * 1000;
const EN_COK_KAYIT = 50;
const TAM_ARALIK_MS = 30 * 60 * 1000;   // artımlı eşitlemede bile 30 dk'da bir tam görüntü (izde olmayan alanlar için)
const VARSAYILAN_PORT = 8080;

let aktif = null;               // { istek_id, tabId, gorevler: Map, harita, basla, zamanlayici }

// ---------------------------------------------------------------- yardımcılar
const uctanAd = (url) => {
  try {
    return new URL(url, 'https://boss.turkcell.com.tr').pathname
      .replace(/^\/boss-gateway-service\//, '')
      .replace(/\/api\/v\d+\//, ' · ')
      .replace(/\/\d{4,}(?=\/|$)/g, '/#');
  } catch (e) {
    return String(url);
  }
};

async function durumYaz(ek) {
  const { esitleme = {} } = await chrome.storage.session.get(['esitleme']);
  await chrome.storage.session.set({ esitleme: { ...esitleme, ...ek } });
}

async function ayarlar() {
  const d = await chrome.storage.local.get(['port', 'eslesme']);
  return { port: Number(d.port) || VARSAYILAN_PORT, eslesme: d.eslesme || '' };
}

// ---------------------------------------------------------------- dinleme (sayfanın kendi yanıtları)
async function yanitIsle(m) {
  const ad = uctanAd(m.yol);
  const { uclar = {} } = await chrome.storage.session.get(['uclar']);
  const kucuk = /count$|btk|teams/.test(ad);
  uclar[ad] = { ad, yontem: m.yontem, zaman: m.zaman, yapi: E.yapi(m.veri), govdeYapi: m.govde ? E.yapi(m.govde) : null, veri: kucuk ? m.veri : undefined };
  await chrome.storage.session.set({ uclar, sonGorulme: m.zaman }).catch(() => {});
}

// ---------------------------------------------------------------- BOSS sekmesi (kendiliğinden toparlanır)
const BOSS_ADRESI = 'https://boss.turkcell.com.tr/*';

async function bossSekmesi() {
  const sekmeler = await chrome.tabs.query({ url: BOSS_ADRESI });
  if (!sekmeler.length) return null;
  const { yakalanan = {} } = await chrome.storage.session.get(['yakalanan']);
  return sekmeler.find((s) => yakalanan[s.id]) || sekmeler.find((s) => s.active && !s.discarded) ||
    sekmeler.find((s) => !s.discarded) || sekmeler[0];
}

// İçerik betiklerini açık sekmeye yeniden yükler (eklenti yenilenince Chrome eski sekmelere kendisi yüklemez).
// maske.js kancadan önce yüklenir. kanca.js kendini bir kez kurar (aynı sürüm sayfada varsa — yakaladığı liste
// isteğiyle birlikte — o çalışmaya devam eder; ESKİ sürüm varsa "kanca-eski" gelir ve panel F5 ister);
// kopru.js yeni köprüyü kurup eskisini devre dışı bırakır.
async function betikleriYukle(tabId) {
  if (!chrome.scripting) return false;
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['maske.js', 'kanca.js'], world: 'MAIN', injectImmediately: true });
    await chrome.scripting.executeScript({ target: { tabId }, files: ['kopru.js'], injectImmediately: true });
    return true;
  } catch (e) {
    return false;
  }
}

// Sekmeye mesaj; köprü yoksa betikleri yükleyip bir kez daha dener. Uyutulmuş (discarded) sekme yeniden yüklenir
// (ekranda içeriği olmayan sekmedir; liste isteği sayfa açılınca yakalanır). Ulaşıldıysa true.
async function sekmeyeGonder(sekme, mesaj) {
  try {
    await chrome.tabs.sendMessage(sekme.id, mesaj);
    return true;
  } catch (e) { /* köprü yok: aşağıda onarılır */ }
  if (sekme.discarded) {
    try { await chrome.tabs.reload(sekme.id); } catch (e) { /* sekme kapanmış olabilir */ }
    return false;
  }
  if (!(await betikleriYukle(sekme.id))) return false;
  try {
    await chrome.tabs.sendMessage(sekme.id, mesaj);
    return true;
  } catch (e) {
    return false;
  }
}

async function sekmeleriHazirla() {
  for (const s of await chrome.tabs.query({ url: BOSS_ADRESI })) if (!s.discarded) await betikleriYukle(s.id);
}

// ---------------------------------------------------------------- eşitleme

async function esitleBaslat(neden) {
  if (aktif && Date.now() - aktif.basla < ZAMAN_ASIMI_MS) return { durum: 'suruyor' };
  const sekme = await bossSekmesi();
  if (!sekme) {
    await durumYaz({ durum: 'boss_kapali', suruyor: false, denendi: Date.now() });
    return { durum: 'boss_kapali' };
  }
  const istek_id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  aktif = { istek_id, tabId: sekme.id, gorevler: new Map(), harita: {}, basla: Date.now(), neden };
  // son sayılar (acik, sonEsitleme) DURUR; yalnız "denetleniyor" işareti
  await durumYaz({ suruyor: true, basla: aktif.basla, okunan: 0 });
  if (!(await sekmeyeGonder(sekme, { tur: 'esitle-baslat', istek_id, acik: ACIK_DURUMLAR, kapali: KAPALI_DURUMLAR, kapaliSayfa: 2 }))) {
    aktif = null;
    await durumYaz({ durum: 'sayfa_yenile', suruyor: false, denendi: Date.now() });
    return { durum: 'sayfa_yenile' };
  }
  return { durum: 'basladi', istek_id };
}

async function parcaIsle(m) {
  if (!aktif || m.istek_id !== aktif.istek_id) return;
  const { gorevler, alanHaritasi } = E.cevirHepsi(m.gorevler || []);
  for (const g of gorevler) aktif.gorevler.set(g.task_no, g);
  Object.assign(aktif.harita, alanHaritasi);
  await durumYaz({ okunan: aktif.gorevler.size });
}

async function sunucuyaGonder(gorevler, tam, ekipler, ek) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  let y;
  try {
    y = await fetch(`http://127.0.0.1:${port}/api/boss/esitle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
      body: JSON.stringify({ gorevler, tam, ...(Array.isArray(ekipler) ? { ekipler } : {}), ...(ek || {}), kaynak: 'eklenti', surum: chrome.runtime.getManifest ? chrome.runtime.getManifest().version : '' }),
    });
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
  if (y.status === 401) return { durum: 'kod_yanlis' };
  let govde = null;
  try { govde = await y.json(); } catch (e) { /* boş */ }
  if (!y.ok) {
    const h = (govde && (govde.detail || govde)) || {};
    return { durum: y.status === 409 ? 'sunucu_mesgul' : 'sunucu_hata', mesaj: h.hata || `HTTP ${y.status}` };
  }
  return { durum: 'tamam', sonuc: govde };
}

// Artımlı eşitleme: sunucunun bildiği parmak izleri (görev no → iz). Yoksa / eski sunucuysa null → tam gönderim.
async function sunucuIzleri() {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return null;
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/izler`, { headers: { 'X-Eslesme-Kodu': eslesme } });
    if (!y.ok) return null;
    const j = await y.json();
    return j && j.izler && typeof j.izler === 'object' && !Array.isArray(j.izler) ? j : null;
  } catch (e) {
    return null;
  }
}

// Ne gönderilecek: {gorevler: yalnız yeni/değişen (+ sunucuda açık görünen kapanmışlar), kaldirilan} ya da null
// (tam gönderim gerekir). kaldirilan yalnız eksiksiz görüntüde (tam) dolar.
function farkHesapla(gorevler, sunucu, tam) {
  if (!sunucu || sunucu.tam_gerekli) return null;
  const iz = sunucu.izler;
  const kapali = (g) => /tamamland|iptal/i.test(String(g.durum || '').toLocaleLowerCase('tr-TR'));
  const gonder = [];
  const gorulen = new Set();
  for (const g of gorevler) {
    gorulen.add(g.task_no);
    if (kapali(g)) {
      if (Object.prototype.hasOwnProperty.call(iz, g.task_no)) gonder.push(g);
    } else if (iz[g.task_no] !== g.iz) gonder.push(g);
  }
  const kaldirilan = tam ? Object.keys(iz).filter((no) => !gorulen.has(no)) : [];
  return { gorevler: gonder, kaldirilan };
}

async function bittiIsle(m) {
  if (!aktif || m.istek_id !== aktif.istek_id) return;
  const a = aktif;
  aktif = null;
  if (m.hata) {
    await durumYaz({ durum: m.hata === 'istek_yok' ? 'istek_yok' : 'okuma_hata', hata: m.hata, suruyor: false, denendi: Date.now() });
    return;
  }
  const gorevler = [...a.gorevler.values()];
  const acik = gorevler.filter((g) => !/tamamland|iptal/i.test(String(g.durum || '').toLocaleLowerCase('tr-TR')));
  // iş listesi eklentide saklanmaz (panel yalnız sayıları gösterir); yalnız alan haritası (değer yok)
  await chrome.storage.session.set({ alanHaritasi: a.harita }).catch(() => {});
  await chrome.storage.local.set({ alanHaritasi: a.harita });     // yalnız alan adları (değer yok)
  for (const g of gorevler) g.iz = E.iz(g);
  const { esitlemeTam = 0 } = await chrome.storage.session.get(['esitlemeTam']);
  const tamZamani = !esitlemeTam || Date.now() - esitlemeTam > TAM_ARALIK_MS;
  const f = tamZamani ? null : farkHesapla(gorevler, await sunucuIzleri(), !!m.tam);
  const s = f
    ? await sunucuyaGonder(f.gorevler, !!m.tam, m.ekipler, { mod: 'fark', kaldirilan: f.kaldirilan })
    : await sunucuyaGonder(gorevler, !!m.tam, m.ekipler);
  if (s.durum === 'tamam' && !f && m.tam) await chrome.storage.session.set({ esitlemeTam: Date.now() }).catch(() => {});
  if (s.durum === 'tamam' && s.sonuc && Array.isArray(s.sonuc.iletisim) && s.sonuc.iletisim.length) iletisimBaslat(s.sonuc.iletisim);
  if (s.durum === 'tamam' && s.sonuc && Array.isArray(s.sonuc.detay_onden) && s.sonuc.detay_onden.length) detayOndenBaslat(s.sonuc.detay_onden);
  const oz = (s.sonuc && s.sonuc.ozet) || {};
  // panelin "+3 yeni · 2 değişti · 1 kapandı" satırı: sunucunun gerçek değişiklik listeleri (yoksa eski özet)
  const dg = (s.sonuc && s.sonuc.degisiklik) || null;
  const say = (ad) => (dg && Array.isArray(dg[ad]) ? dg[ad].length : (oz[ad] ?? null));
  const tamam = s.durum === 'tamam';
  const dt = tamam && s.sonuc && s.sonuc.detay_toplam != null ? { detayTamam: s.sonuc.detay_tamam ?? 0, detayToplam: s.sonuc.detay_toplam, detayKalanDk: s.sonuc.detay_kalan_dk ?? null } : {};
  // açık iş sayısı yalnız BAŞARILI eşitlemede değişir (panelin büyük sayısı hiç 0/— olmaz)
  await durumYaz({
    mod: f ? 'fark' : 'tam', gonderilen: f ? f.gorevler.length : gorevler.length,
    durum: s.durum, mesaj: s.mesaj || null, zaman: Date.now(), okunan: gorevler.length, tam: !!m.tam, suruyor: false,
    toplam: m.toplam ?? null, ...dt,
    ...(tamam ? { acik: acik.length, sonEsitleme: Date.now(), yeni: say('yeni'), degisen: say('degisen'), kapanan: say('kapanan'),
      sunucu: { yeni: s.sonuc?.fark?.yeni ?? 0, uyari: s.sonuc?.uyari ?? null } } : {}),
  });
}

// ---------------------------------------------------------------- iş ayrıntısı (uygulama ister, BOSS'tan okunur)
const DETAY_ARALIK_MS = 2500;
const DETAY_ZAMAN_ASIMI_MS = 60 * 1000;
const detayBekleyen = new Map();      // istek_id → başlangıç
let detaySoruluyor = false;

async function detayYolla(govde) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/detay`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme }, body: JSON.stringify(govde),
    });
    return { durum: y.ok ? 'tamam' : `http_${y.status}` };
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
}

async function istekleriSor(bekle = 0) {
  if (detaySoruluyor) return { durum: 'suruyor' };
  detaySoruluyor = true;
  try {
    const { port, eslesme } = await ayarlar();
    if (!eslesme) return { durum: 'kod_yok' };
    for (const [id, t] of detayBekleyen) if (Date.now() - t > DETAY_ZAMAN_ASIMI_MS) detayBekleyen.delete(id);
    let liste = [];
    try {
      const y = await fetch(`http://127.0.0.1:${port}/api/boss/istekler${bekle ? `?bekle=${bekle}` : ''}`,
        { headers: { 'X-Eslesme-Kodu': eslesme } });
      if (!y.ok) return { durum: `http_${y.status}` };
      const j = (await y.json()) || {};
      liste = j.istekler || [];
      // MAP/TASKS ⟳ "şimdi eşitle" istedi (POST /api/boss/esitle-iste): hemen eşitle (sürüyorsa yenisi başlamaz)
      if (j.esitle === true) esitleBaslat('istek').catch(() => {});
    } catch (e) {
      return { durum: 'sunucu_yok' };
    }
    for (const i of liste) {
      if (!i || !i.istek_id || detayBekleyen.has(i.istek_id)) continue;
      const sekme = await bossSekmesi();
      if (!sekme) {
        await detayYolla({ istek_id: i.istek_id, is_no: i.is_no, uuid: i.uuid, hata: 'boss_kapali' });
        continue;
      }
      detayBekleyen.set(i.istek_id, Date.now());
      if (!(await sekmeyeGonder(sekme, { tur: 'detay-baslat', istek_id: i.istek_id, is_no: i.is_no, uuid: i.uuid }))) {
        detayBekleyen.delete(i.istek_id);
        await detayYolla({ istek_id: i.istek_id, is_no: i.is_no, uuid: i.uuid, hata: 'sayfa_yenile' });
      }
    }
    return { durum: 'tamam', istek: liste.length };
  } finally {
    detaySoruluyor = false;
  }
}

// Uzun yoklama döngüsü: sunucu yeni istek gelince hemen yanıtlar (en çok ISTEK_BEKLE_SN bekletir). Tek döngü.
const ISTEK_BEKLE_SN = 20;
let istekDongusu = false;
const uyu = (ms) => new Promise((ok) => setTimeout(ok, ms));
async function istekDongusuBaslat() {
  if (istekDongusu) return;
  istekDongusu = true;
  try {
    for (;;) {
      const t0 = Date.now();
      const r = await istekleriSor(ISTEK_BEKLE_SN).catch(() => ({ durum: 'hata' }));
      if (r.durum === 'suruyor') return;                       // başka bir sorma sürüyor
      if (r.durum !== 'tamam') return;                         // sunucu yok / kod yok: yoklama yeniden dener
      if (Date.now() - t0 < 300 && !r.istek) await uyu(DETAY_ARALIK_MS);     // sunucu bekletmedi (eski sürüm)
    }
  } finally {
    istekDongusu = false;
  }
}

async function detayBittiIsle(m) {
  if (!detayBekleyen.has(m.istek_id)) return { durum: 'beklenmiyor' };
  detayBekleyen.delete(m.istek_id);
  return detayYolla({ istek_id: m.istek_id, is_no: m.is_no, uuid: m.uuid, sekmeler: m.sekmeler, hata: m.hata || undefined });
}

// ---------------------------------------------------------------- müşteri telefonu önden okuma
// Sunucu "telefonu okunacak" işleri ({task_no, uuid}) verir; kanca yalnız detail/customer/list'i SIRAYLA (~300 ms)
// okur; sonuçlar parça parça /api/boss/iletisim'e gider; yanıt sıradaki işleri verir (ilk çalışmada bütün açıklar).
const ILETISIM_TUR_SINIRI = 40;
let iletisim = null;            // { istek_id, tur, sonraki }

async function iletisimBaslat(liste, tur = 0) {
  if (iletisim && Date.now() - iletisim.basla < 30 * 60 * 1000) return { durum: 'suruyor' };
  if (!Array.isArray(liste) || !liste.length || tur >= ILETISIM_TUR_SINIRI) return { durum: 'atlandi' };
  const sekme = await bossSekmesi();
  if (!sekme) return { durum: 'boss_kapali' };
  const istek_id = `il-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  iletisim = { istek_id, tur, sonraki: null, basla: Date.now() };
  if (!(await sekmeyeGonder(sekme, { tur: 'iletisim-baslat', istek_id,
    isler: liste.filter((x) => x && x.task_no && x.uuid).map((x) => ({ task_no: String(x.task_no), uuid: String(x.uuid) })) }))) {
    iletisim = null;
    return { durum: 'sayfa_yenile' };
  }
  return { durum: 'basladi', istek_id };
}

// parçalar sırayla yollanır; "bitti" son parçanın yanıtını (sıradaki işler) bekler
function iletisimParcaIsle(m) {
  if (!iletisim || m.istek_id !== iletisim.istek_id) return Promise.resolve({ durum: 'beklenmiyor' });
  iletisim.zincir = (iletisim.zincir || Promise.resolve()).then(() => iletisimParcaYolla(m));
  return iletisim.zincir;
}

async function iletisimParcaYolla(m) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/iletisim`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
      body: JSON.stringify({ sonuclar: m.sonuclar || [] }),
    });
    if (!y.ok) return { durum: `http_${y.status}` };
    const j = (await y.json()) || {};
    if (iletisim && m.istek_id === iletisim.istek_id) iletisim.sonraki = j.iletisim || [];
    await durumYaz({ iletisimTamam: j.iletisim_tamam ?? null, iletisimToplam: j.iletisim_toplam ?? null });
    return { durum: 'tamam' };
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
}

async function iletisimBittiIsle(m) {
  if (!iletisim || m.istek_id !== iletisim.istek_id) return { durum: 'beklenmiyor' };
  if (iletisim.zincir) await iletisim.zincir.catch(() => {});
  const { tur, sonraki } = iletisim;
  iletisim = null;
  if (!m.hata && sonraki && sonraki.length) return iletisimBaslat(sonraki, tur + 1);
  return { durum: m.hata ? 'hata' : 'bitti' };
}

// ---------------------------------------------------------------- iş ayrıntısı önden okuma
// Sunucu {task_no, uuid} listesi verir (önce kullanıcının açacağı işler); kanca her işi okuyunca bir parça yollar;
// parça HER ZAMAN /api/boss/detay-onden'e gider (servis çalışanı arada uyuyup uyandıysa da düşmez); yanıt sıradaki
// işleri verir. Okuma bitince sıradakiyle sürer; hiç okuma yokken yoklama (ondenDevam) sunucuya sorup yeniden başlar.
const DETAY_TUR_SINIRI = 1000;
const ONDEN_SESSIZ_MS = 2 * 60 * 1000;     // bu sürede parça gelmeyen okuma ölü sayılır (yenisi başlayabilir)
const ONDEN_BOS_MS = 60 * 1000;            // sunucu "okunacak yok" derse bu kadar sonra yeniden sorulur
const ONDEN_HATA_MS = 30 * 1000;           // okuma hatayla bittiyse (oturum, sayfa) bu kadar sonra yeniden
let onden = null;               // { istek_id, tur, sonraki, son }
let ondenSon = 0;               // son parça (herhangi bir okumadan) ya da başlatma
let ondenSonraki = [];          // son yanıtın sıradaki işleri
let ondenBekle = 0;             // bu zamana dek ondenDevam yeniden başlatmaz
let ondenZincir = Promise.resolve();

async function detayOndenBaslat(liste, tur = 0) {
  if (onden && Date.now() - onden.son < ONDEN_SESSIZ_MS) return { durum: 'suruyor' };
  if (!Array.isArray(liste) || !liste.length || tur >= DETAY_TUR_SINIRI) return { durum: 'atlandi' };
  const sekme = await bossSekmesi();
  if (!sekme) return { durum: 'boss_kapali' };
  const istek_id = `do-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  onden = { istek_id, tur, sonraki: null, son: Date.now() };
  ondenSon = Date.now();
  if (!(await sekmeyeGonder(sekme, { tur: 'detay-onden-baslat', istek_id,
    isler: liste.filter((x) => x && x.task_no && x.uuid).map((x) => ({ task_no: String(x.task_no), uuid: String(x.uuid) })) }))) {
    onden = null;
    ondenBekle = Date.now() + ONDEN_HATA_MS;
    return { durum: 'sayfa_yenile' };
  }
  return { durum: 'basladi', istek_id };
}

// parça: hangi okumadan gelirse gelsin sunucuya (sırayla) gider
function detayOndenParcaIsle(m) {
  ondenSon = Date.now();
  if (onden && m.istek_id === onden.istek_id) onden.son = Date.now();
  ondenZincir = ondenZincir.catch(() => {}).then(() => detayOndenYolla(m.sonuclar || [], m.istek_id));
  return ondenZincir;
}

async function detayOndenYolla(sonuclar, istek_id) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/detay-onden`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
      body: JSON.stringify({ sonuclar }),
    });
    if (!y.ok) return { durum: `http_${y.status}` };
    const j = (await y.json()) || {};
    ondenSonraki = Array.isArray(j.detay_onden) ? j.detay_onden : [];
    if (onden && istek_id && istek_id === onden.istek_id) onden.sonraki = ondenSonraki;
    await durumYaz({ detayTamam: j.detay_tamam ?? null, detayToplam: j.detay_toplam ?? null, detayKalanDk: j.detay_kalan_dk ?? null });
    return { durum: 'tamam', sonraki: ondenSonraki.length };
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
}

async function detayOndenBittiIsle(m) {
  await ondenZincir.catch(() => {});
  if (!onden || m.istek_id !== onden.istek_id) return { durum: 'beklenmiyor' };
  const { tur, sonraki } = onden;
  onden = null;
  if (m.hata === 'suruyor') {                      // kancada önceki okuma sürüyor (servis çalışanı uyumuştu)
    ondenSon = Date.now();
    return { durum: 'suruyor' };
  }
  if (m.hata) {
    ondenBekle = Date.now() + ONDEN_HATA_MS;
    return { durum: 'hata' };
  }
  if (sonraki && sonraki.length) return detayOndenBaslat(sonraki, tur + 1);
  return { durum: 'bitti' };
}

// Yoklamadan: okuma sürmüyorsa sunucudan sıradakileri al ve başlat (kesintiden sonra kaldığı yerden sürer).
let ondenSoruluyor = false;
async function ondenDevam() {
  const simdi = Date.now();
  if (ondenSoruluyor || simdi < ondenBekle) return { durum: 'bekliyor' };
  if (simdi - ondenSon < ONDEN_SESSIZ_MS && (onden || ondenSon)) {
    if (onden || simdi - ondenSon < 15 * 1000) return { durum: 'suruyor' };   // kancadan parça geliyor
  }
  if (aktif) return { durum: 'esitleme' };          // eşitleme yanıtı zaten sıradakileri getirir
  ondenSoruluyor = true;
  try {
    const sekme = await bossSekmesi();
    if (!sekme) return { durum: 'boss_kapali' };
    const { yakalanan = {} } = await chrome.storage.session.get(['yakalanan']);
    if (!yakalanan[sekme.id]) return { durum: 'istek_yok' };          // sayfa liste isteğini henüz yapmadı
    onden = null;
    const r = await detayOndenYolla([], null);
    if (r.durum !== 'tamam') { ondenBekle = Date.now() + ONDEN_HATA_MS; return r; }
    if (!ondenSonraki.length) { ondenBekle = Date.now() + ONDEN_BOS_MS; return { durum: 'bos' }; }
    return detayOndenBaslat(ondenSonraki, 0);
  } finally {
    ondenSoruluyor = false;
  }
}

// ---------------------------------------------------------------- kayıt modu
async function kayitEkle(m) {
  const { kayitModu, kayitlar = [] } = await chrome.storage.local.get(['kayitModu', 'kayitlar']);
  if (!kayitModu) return;
  const anahtar = `${m.yontem} ${m.yol}`;
  const yeni = kayitlar.filter((k) => `${k.yontem} ${k.yol}` !== anahtar);
  yeni.unshift({ yontem: m.yontem, yol: m.yol, govdeYapi: m.govdeYapi, zaman: Date.now() });
  await chrome.storage.local.set({ kayitlar: yeni.slice(0, EN_COK_KAYIT) });
}

// ---------------------------------------------------------------- BOSS'a yazma (GERÇEK YAZMA KAPALI)
// Sunucu (boss_yazma.py) yazılacakları verir; sekmedeki kanca yürütür. Sunucu "yazma: kapali" (varsayılan) ya da
// şablon doğrulanmamış derse kanca BOSS'a hiçbir istek göndermez, yalnız "önizleme" der. Sonuç sunucuya gider.
const yazmaBekleyen = new Map();      // istek_id → başlangıç
const YAZMA_ZAMAN_ASIMI_MS = 60 * 1000;
let yazmaSoruluyor = false;

async function yazmaSonucuYolla(m) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/yazma-sonucu`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
      body: JSON.stringify({ istek_id: m.istek_id, kayitlar: m.kayitlar || [], durum: m.durum, http: m.http ?? null,
        hata: m.hata || null, hazir: !!m.hazir, return_kodu: m.return_kodu ?? null, return_mesaji: m.return_mesaji ?? null,
        yanit_metni: typeof m.yanit_metni === 'string' ? m.yanit_metni.slice(0, 1500) : null }),
    });
    return { durum: y.ok ? 'tamam' : `http_${y.status}` };
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
}

async function yazilacaklariSor() {
  if (yazmaSoruluyor) return { durum: 'suruyor' };
  yazmaSoruluyor = true;
  try {
    const { port, eslesme } = await ayarlar();
    if (!eslesme) return { durum: 'kod_yok' };
    for (const [id, t] of yazmaBekleyen) if (Date.now() - t > YAZMA_ZAMAN_ASIMI_MS) yazmaBekleyen.delete(id);
    let j;
    try {
      const y = await fetch(`http://127.0.0.1:${port}/api/boss/yazilacaklar`, { headers: { 'X-Eslesme-Kodu': eslesme } });
      if (!y.ok) return { durum: `http_${y.status}` };
      j = (await y.json()) || {};
    } catch (e) {
      return { durum: 'sunucu_yok' };
    }
    const acik = j.yazma === 'acik';
    // eşzamanlı BOSS yazma sayısı (sunucu ayarı boss_yazma_paralel); kanca ayrıca 1–10'a kırpar
    const paralel = Number.isInteger(j.paralel) ? Math.min(10, Math.max(1, j.paralel)) : null;
    const istekler = Array.isArray(j.istekler) ? j.istekler : [];
    const okunacaklar = Array.isArray(j.okunacaklar) ? j.okunacaklar.filter((y) => typeof y === 'string').slice(0, 10) : [];
    if (!istekler.length && !okunacaklar.length) return { durum: 'tamam', istek: 0 };
    const sekme = await bossSekmesi();
    // BOSS sekmesi yok / kancaya ulaşılamadı: sunucu bu istekleri 'gonderiliyor' saymıştı — hiçbir şey gitmedi,
    // "ertelendi" denir (kayıt bekliyor'a döner, sonra yeniden verilir). Eskiden 5 dk sonra "Sonuç gelmedi" oluyordu.
    const ertele = (i) => (i && i.istek_id && i.yaz === true
      ? yazmaSonucuYolla({ istek_id: i.istek_id, kayitlar: i.kayitlar || [], durum: 'ertelendi', hata: 'sekme_yok' })
      : null);
    if (!sekme) {
      for (const i of istekler) await ertele(i);
      return { durum: 'boss_kapali', istek: istekler.length };
    }
    for (const yol of okunacaklar) await sekmeyeGonder(sekme, { tur: 'neden-oku-baslat', yol });
    for (const i of istekler) {
      if (!i || !i.istek_id || yazmaBekleyen.has(i.istek_id)) continue;
      yazmaBekleyen.set(i.istek_id, Date.now());
      // gerçek gönderim: şablon doğrulanmış + (genel anahtar açık ya da eylemin kendi anahtarı açık [not]), ya da
      // yöneticinin tek iş denemesi
      const deneme = i.deneme === true && i.yaz === true;
      const istek = { istek_id: i.istek_id, kayitlar: i.kayitlar || [], tur: i.tur, yontem: i.yontem, yol: i.yol,
        govde: i.govde, dogrulandi: i.dogrulandi === true, deneme, ...(paralel ? { paralel } : {}),
        yaz: deneme || ((acik || i.eylem_acik === true) && i.yaz === true && i.dogrulandi === true) };
      if (!(await sekmeyeGonder(sekme, { tur: 'yaz-baslat', istek }))) {
        yazmaBekleyen.delete(i.istek_id);
        await ertele(i);
      }
    }
    return { durum: 'tamam', istek: istekler.length };
  } finally {
    yazmaSoruluyor = false;
  }
}

// Kancanın sonucu HER ZAMAN sunucuya gider: yazma kuyruğu eşitleme/ayrıntı okuması bitene dek bekleyebilir (≥ 60 sn)
// ve servis çalışanı arada uyuyup uyanabilir (yazmaBekleyen boşalır). Eskiden bilinmeyen istek_id'nin sonucu
// düşürülüyordu → BOSS'a yazılmış iş uygulamada 5 dk sonra "Sonuç gelmedi" oluyordu (08.10). Sunucu yalnız bekleyen
// (ya da sonucu gelmedi diye işaretlenmiş) kaydı günceller; iki kez gelen sonuç zararsızdır.
async function yazSonucIsle(m) {
  if (!m || !m.istek_id) return { durum: 'gecersiz' };
  if (m.durum !== 'alindi') yazmaBekleyen.delete(m.istek_id);   // "alindi": kanca kuyruğa aldı, sonuç sonra gelir
  return yazmaSonucuYolla(m);
}

// Tanı satırı Turkcell sunucusuna (değer içermez); sunucu kapalıysa sessizce düşer
async function taniGonder(m) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return;
  fetch(`http://127.0.0.1:${port}/api/boss/gunluk`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
    body: JSON.stringify({ adim: m.adim, yol: m.yol, ileti: m.ileti, ek: m.ek, surum: chrome.runtime.getManifest().version }),
  }).catch(() => {});
}

// ---------------------------------------------------------------- ekip GPS konumu (MAP "Ekipler")
const KONUM_ARALIK_DK = 2;
const KONUM_SAYFA_ARA_MS = 30 * 1000;      // sayfanın kendi yanıtları en çok bu sıklıkta iletilir
let konumIstegi = null;                    // { istek_id, basla }
let konumSayfaSon = 0;

async function ekipKonumGonder(govde) {
  const { port, eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  try {
    const y = await fetch(`http://127.0.0.1:${port}/api/boss/ekip-konum`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': eslesme },
      body: JSON.stringify({ ...govde, surum: chrome.runtime.getManifest ? chrome.runtime.getManifest().version : '' }),
    });
    return { durum: y.ok ? 'tamam' : `http_${y.status}` };
  } catch (e) {
    return { durum: 'sunucu_yok' };
  }
}

// Bir BOSS sekmesine "konum-oku" (uyutulmuş sekme yalnız bunun için uyandırılmaz).
async function konumOkut() {
  if (konumIstegi && Date.now() - konumIstegi.basla < 60 * 1000) return { durum: 'suruyor' };
  const { eslesme } = await ayarlar();
  if (!eslesme) return { durum: 'kod_yok' };
  const sekme = await bossSekmesi();
  if (!sekme) return { durum: 'boss_kapali' };
  if (sekme.discarded) return { durum: 'uyuyor' };
  const istek_id = `ko-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  konumIstegi = { istek_id, basla: Date.now() };
  if (!(await sekmeyeGonder(sekme, { tur: 'konum-oku-baslat', istek_id }))) {
    konumIstegi = null;
    return { durum: 'sayfa_yenile' };
  }
  return { durum: 'basladi', istek_id };
}

async function konumBittiIsle(m) {
  if (konumIstegi && m.istek_id === konumIstegi.istek_id) konumIstegi = null;
  if (m.veri !== undefined && !m.hata) return ekipKonumGonder({ kaynak: 'komut', yol: m.yol || null, veri: m.veri, varsayilan: !!m.varsayilan });
  // hata da (yalnız kod) sunucuya: canlı akışta görünür, veri değişmez; 'mesgul'/'suruyor' gürültüdür, gitmez
  if (m.hata && !['mesgul', 'suruyor'].includes(m.hata)) return ekipKonumGonder({ kaynak: 'komut', yol: m.yol || null, hata: String(m.hata).slice(0, 60) });
  return { durum: 'atlandi' };
}

async function konumYanitIsle(m) {
  if (Date.now() - konumSayfaSon < KONUM_SAYFA_ARA_MS) return { durum: 'atlandi' };
  konumSayfaSon = Date.now();
  return ekipKonumGonder({ kaynak: 'sayfa', yol: m.yol || null, veri: m.veri });
}

// ---------------------------------------------------------------- BOSS ile giriş
const GIRIS_ADRESI = /^http:\/\/(127\.0\.0\.1|localhost):(\d{2,5})\/boss-giris\/([A-Za-z0-9_-]{16,80})(\?|#|$)/;
const GIRIS_SURE_MS = 120 * 1000;
const BOSS_KOK = 'https://boss.turkcell.com.tr/';

async function girisSekmesi(tabId, url) {
  const e = GIRIS_ADRESI.exec(url || '');
  if (!e) return false;
  await chrome.storage.session.set({ girisIstegi: { id: e[3], port: Number(e[2]), an: Date.now() } });
  // ara sayfa kendisi de yönlendirir; eski servis çalışanı araya girdiyse sekmeyi BOSS'a eklenti geçirir
  if (chrome.tabs && chrome.tabs.get && chrome.tabs.update && tabId != null) {
    setTimeout(() => {
      chrome.tabs.get(tabId).then((t) => {
        if (t && GIRIS_ADRESI.test(t.url || '')) return chrome.tabs.update(tabId, { url: BOSS_KOK });
        return null;
      }).catch(() => {});
    }, 2500);
  }
  await kimlikGonder();
  return true;
}

async function uygulamaya(yol, govde, port) {
  const a = await ayarlar();
  if (!a.eslesme) return null;
  return fetch(`http://127.0.0.1:${port || a.port}${yol}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Eslesme-Kodu': a.eslesme },
    body: JSON.stringify(govde),
  });
}

// Bekleyen giriş isteği + bilinen BOSS kimliği varsa bir kez bildirir.
async function kimlikGonder() {
  const { girisIstegi, bossKimlik } = await chrome.storage.session.get(['girisIstegi', 'bossKimlik']);
  if (!girisIstegi || !bossKimlik || !bossKimlik.ad) return false;
  if (Date.now() - girisIstegi.an > GIRIS_SURE_MS) {
    await chrome.storage.session.set({ girisIstegi: null });
    return false;
  }
  await chrome.storage.session.set({ girisIstegi: null });          // tek kullanımlık
  try {
    await uygulamaya('/api/giris/boss/kimlik', { istek_id: girisIstegi.id, ad: bossKimlik.ad, kod: bossKimlik.kod || null,
      unvan: bossKimlik.unvan || null, bayi: bossKimlik.bayi || null, kaynak: bossKimlik.kaynak || null }, girisIstegi.port);
    return true;
  } catch (e) {
    return false;
  }
}

// Kimlik kaynakları: 'dom' (BOSS sayfa başlığındaki ad / bayi; kopru.js) BİRİNCİL; jeton/uç/depo (kanca.js) yedek —
// dom kimliği varken yedek kaynak onu ezmez.
const adNorm = (s) => String(s || '').toLocaleUpperCase('tr-TR').replace(/\s+/g, ' ').trim();
async function kimlikIsle(m) {
  if (!m || typeof m.ad !== 'string' || !m.ad.trim()) return;
  const { bossKimlik } = await chrome.storage.session.get(['bossKimlik']);
  const kaynak = m.kaynak === 'dom' ? 'dom' : 'sayfa';
  if (bossKimlik && bossKimlik.kaynak === 'dom' && kaynak !== 'dom') return;
  const yeni = { ad: m.ad.trim().slice(0, 120), kod: m.kod ? String(m.kod).slice(0, 80) : null,
    unvan: m.unvan ? String(m.unvan).slice(0, 120) : null, bayi: m.bayi ? String(m.bayi).slice(0, 120) : null,
    kaynak, an: Date.now() };
  if (kaynak === 'dom' && bossKimlik && adNorm(bossKimlik.ad) === adNorm(yeni.ad)) {
    yeni.kod = bossKimlik.kod || null;                 // yedek kaynağın kullanıcı kodu / unvanı korunur
    yeni.unvan = bossKimlik.unvan || null;
  }
  // BOSS'ta başka kullanıcı oturum açtı: öncekinin BOSS'la açılmış uygulama oturumu biter
  const kodFarkli = bossKimlik && bossKimlik.kod && yeni.kod && bossKimlik.kod !== yeni.kod;
  if (bossKimlik && bossKimlik.ad && (adNorm(bossKimlik.ad) !== adNorm(yeni.ad) || kodFarkli)) {
    uygulamaya('/api/giris/boss/bitti', { ad: bossKimlik.ad, kod: bossKimlik.kod || null, neden: 'kullanici_degisti' }).catch(() => {});
  }
  await chrome.storage.session.set({ bossKimlik: yeni });
  await kimlikGonder();
}

let sonBitti = 0;
async function oturumBittiIsle(m) {
  const { bossKimlik } = await chrome.storage.session.get(['bossKimlik']);
  if (!bossKimlik && Date.now() - sonBitti < 30000) return;        // aynı bitiş tekrar tekrar bildirilmez
  sonBitti = Date.now();
  await chrome.storage.session.set({ bossKimlik: null });
  try {
    await uygulamaya('/api/giris/boss/bitti', { ad: bossKimlik ? bossKimlik.ad : null, kod: bossKimlik ? bossKimlik.kod || null : null,
      neden: String((m && m.neden) || '').slice(0, 40) || null });
  } catch (e) { /* uygulama kapalı */ }
}

if (chrome.tabs && chrome.tabs.onUpdated) {
  chrome.tabs.onUpdated.addListener((tabId, degisim, sekme) => {
    const url = (degisim && degisim.url) || (degisim && degisim.status === 'loading' && sekme && sekme.url);
    if (url) girisSekmesi(tabId, url).catch(() => {});
  });
}

// ---------------------------------------------------------------- mesajlar
chrome.runtime.onMessage.addListener((m, gonderen, yanitla) => {
  if (!m) return;
  const tab = gonderen && gonderen.tab && gonderen.tab.id;
  if (m.tur === 'boss-yanit') yanitIsle(m);
  else if (m.tur === 'liste-yakalandi' && tab != null) {
    chrome.storage.session.get(['yakalanan']).then(({ yakalanan = {} }) => {
      yakalanan[tab] = Date.now();
      return chrome.storage.session.set({ yakalanan, hazir: true });
    }).then(async () => {
      // ilk yakalamada hemen eşitle (kullanıcı Teknik Havuz'u yeni açtı)
      const { esitleme = {} } = await chrome.storage.session.get(['esitleme']);
      if (!esitleme.sonEsitleme || ['istek_yok', 'sayfa_yenile', 'okuma_hata'].includes(esitleme.durum)) esitleBaslat('ilk');
    });
  } else if (m.tur === 'sayfa-acildi' && tab != null) {
    chrome.storage.session.get(['yakalanan', 'kancaEski']).then(({ yakalanan = {}, kancaEski = {} }) => {
      delete yakalanan[tab];
      delete kancaEski[tab];                                  // sayfa yenilendi: yeni kanca kuruldu
      return chrome.storage.session.set({ yakalanan, kancaEski, hazir: Object.keys(yakalanan).length > 0 });
    });
  } else if (m.tur === 'kanca-eski' && tab != null) {
    chrome.storage.session.get(['kancaEski']).then(({ kancaEski = {} }) => {
      kancaEski[tab] = Date.now();
      return chrome.storage.session.set({ kancaEski });
    });
  } else if (m.tur === 'esitle-parca') parcaIsle(m);
  else if (m.tur === 'esitle-bitti') bittiIsle(m);
  else if (m.tur === 'detay-bitti') detayBittiIsle(m);
  else if (m.tur === 'yaz-sonuc') yazSonucIsle(m);
  else if (m.tur === 'iletisim-parca') iletisimParcaIsle(m);
  else if (m.tur === 'iletisim-bitti') iletisimBittiIsle(m);
  else if (m.tur === 'detay-onden-parca') detayOndenParcaIsle(m);
  else if (m.tur === 'detay-onden-bitti') detayOndenBittiIsle(m);
  else if (m.tur === 'kayit') kayitEkle(m);
  else if (m.tur === 'tani') taniGonder(m);
  else if (m.tur === 'kimlik') kimlikIsle(m);
  else if (m.tur === 'oturum-bitti') oturumBittiIsle(m);
  else if (m.tur === 'konum-bitti') konumBittiIsle(m);
  else if (m.tur === 'konum-yanit') konumYanitIsle(m);
  else if (m.tur === 'esitle-simdi') {
    esitleBaslat('elle').then(yanitla);
    return true;
  }
});

chrome.alarms && chrome.alarms.create('esitle', { periodInMinutes: ARALIK_DK });
chrome.alarms && chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'esitle') esitleBaslat('zamanli');
});
chrome.alarms && chrome.alarms.create('ekip-konum', { periodInMinutes: KONUM_ARALIK_DK });
chrome.alarms && chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'ekip-konum') konumOkut().catch(() => {});
});

// ayrıntı istekleri ve BOSS'a yazılacaklar: servis çalışanı uyanıkken 2,5 sn'de bir; uyuduysa alarm uyandırır
const yokla = () => {
  istekDongusuBaslat().catch(() => {});
  yazilacaklariSor().catch(() => {});
  ondenDevam().catch(() => {});
};
if (typeof setInterval === 'function' && !self.__dehanetTest) setInterval(yokla, DETAY_ARALIK_MS);
chrome.alarms && chrome.alarms.create('detay', { periodInMinutes: 0.5 });
chrome.alarms && chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === 'detay') yokla();
});

// eklenti kurulunca/güncellenince açık BOSS sekmelerine betikler hemen yüklenir (F5 gerekmez)
chrome.runtime.onInstalled && chrome.runtime.onInstalled.addListener(() => { sekmeleriHazirla().catch(() => {}); });

self.__dehanetArka = { esitleBaslat, parcaIsle, bittiIsle, sunucuyaGonder, istekleriSor, detayBittiIsle,
  farkHesapla, iletisimBaslat, iletisimParcaIsle, iletisimBittiIsle, sekmeyeGonder, betikleriYukle,
  detayOndenBaslat, detayOndenParcaIsle, detayOndenBittiIsle, ondenDevam, istekDongusuBaslat,
  yazilacaklariSor, yazSonucIsle, girisSekmesi, kimlikIsle, oturumBittiIsle, kimlikGonder, ACIK_DURUMLAR, KAPALI_DURUMLAR,
  konumOkut, konumBittiIsle, konumYanitIsle };
