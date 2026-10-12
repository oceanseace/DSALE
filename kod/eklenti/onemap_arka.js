// Arka plan (arka.js importScripts ile yükler): OneMap sekmesi açıkken bina listesini OneMap'le eşitler.
// BOSS eşitlemesinden bağımsızdır (ayrı alarm, ayrı mesajlar, ayrı durum anahtarı 'onemap').
//  1) GET  /api/onemap/gorev     → sunucu ne sorgulanacağını söyler (arama listeleri, artımlı/tam tarama, taban süzgeç).
//  2) Her sorgu OneMap sekmesindeki sayfa betiğine (onemap_sayfa.js) gider; sayfa kendi oturumuyla ArcGIS'e sorar.
//  3) Satırlar sadeSatir ile sade biçime çevrilir → POST /api/onemap/binalar (eşleme koduyla).
// Sorgular arası bekleme sunucunun verdiği bekleme_ms; tam tarama sunucuda kaldığı OBJECTID'den sürer.
// OneMap oturum bilgisi buraya HİÇ gelmez.
(() => {
  const g = typeof self !== 'undefined' ? self : globalThis;
  const ADRESLER = ['https://onemap.turkcell.com.tr/*', 'https://arcgis.turkcell.com.tr/*'];
  const ARALIK_DK = 10;
  const EN_COK_SAYFA = 200;            // tek döngüde en çok sorgu sayfası
  const KILIT_MS = 15 * 60 * 1000;
  const SERVIS = /^https:\/\/arcgis\.turkcell\.com\.tr\/arcgis\/rest\/services\/ONEMAP\/BINA\/MapServer\/0$/;
  let calisiyor = 0;
  let sayfaDesteksiz = false;          // ArcGIS resultRecordCount kabul etmiyorsa

  const bekle = (ms) => new Promise((r) => setTimeout(r, ms));
  const metin = (v) => (v === undefined || v === null ? null : String(v).trim() || null);
  const sayi = (v) => {
    if (v === undefined || v === null || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const tam = (v) => {
    const n = sayi(v);
    return n === null ? null : Math.trunc(n);
  };

  // ArcGIS özniteliği → sunucunun sade satırı (saha/onemap_esitle.py BinaSatiri). TEK eşleme yeri.
  function sadeSatir(f) {
    const a = (f && f.attributes) || {};
    const halkalar = f && f.geometry && Array.isArray(f.geometry.rings) ? f.geometry.rings : null;
    let halka = null;
    if (halkalar && Array.isArray(halkalar[0]) && halkalar[0].length >= 3 && halkalar[0].length <= 4000) {
      halka = halkalar[0].map((p) => [Math.round(p[0] * 1e6) / 1e6, Math.round(p[1] * 1e6) / 1e6]);
    }
    const id = sayi(a.ID);
    return {
      objectid: tam(a.OBJECTID), om_id: id === null ? metin(a.ID) : String(Math.trunc(id)),
      bina_serial: metin(a.LOCATION_ID), location_id: metin(a.ENTEGRASYON_ID),
      ad: metin(a.ADI), site_adi: metin(a.SITE_ADI), blok_adi: metin(a.BLOK_ADI), kapi_no: metin(a.KAPI_NO),
      turu: metin(a.TURU), blok_tipi: metin(a.BLOK_TIPI), mahalle: metin(a.MAHALLE), ilce: metin(a.ILCE),
      il: metin(a.IL), cadde: metin(a.CADDE), sokak: metin(a.SOKAK), lat: sayi(a.LAT), lon: sayi(a.LON),
      kat: tam(a.KAT_ADEDI), konut: tam(a.KONUT_SAYISI), isyeri: tam(a.ISYERI_SAYISI), hp: tam(a.FTTX_HP),
      firma: metin(a.PROTOKOL_FIRMA), obek: metin(a.OBEK_ADI), uavt: metin(a.UAVT_BINA_KODU),
      teknoloji: metin(a.TEKNOLOJI), duzenleme: tam(a.LAST_EDITED_DATE), silindi: tam(a.ISDELETED) === 1, halka,
    };
  }

  async function durumYaz(ek) {
    const { onemap = {} } = await chrome.storage.session.get(['onemap']);
    await chrome.storage.session.set({ onemap: { ...onemap, ...ek } }).catch(() => {});
  }

  async function uygulama(yol, govde) {
    const d = await chrome.storage.local.get(['port', 'eslesme']);
    const port = Number(d.port) || 8080;
    if (!d.eslesme) return { durum: 'kod_yok' };
    let y;
    try {
      y = await fetch(`http://127.0.0.1:${port}${yol}`, {
        method: govde === undefined ? 'GET' : 'POST',
        headers: { 'X-Eslesme-Kodu': d.eslesme, ...(govde === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(govde === undefined ? {} : { body: JSON.stringify(govde) }),
      });
    } catch (e) {
      return { durum: 'sunucu_yok' };
    }
    if (y.status === 401) return { durum: 'kod_yanlis' };
    if (y.status === 404) return { durum: 'sunucu_eski' };
    if (!y.ok) return { durum: 'sunucu_hata', http: y.status };
    try { return { durum: 'tamam', veri: await y.json() }; } catch (e) { return { durum: 'sunucu_hata' }; }
  }

  async function sekmeBul() {
    const sekmeler = await chrome.tabs.query({ url: ADRESLER });
    return sekmeler.find((s) => !s.discarded && /^https:\/\/onemap\./.test(s.url || '')) ||
      sekmeler.find((s) => !s.discarded) || null;
  }

  async function betikYukle(tabId) {
    if (!chrome.scripting) return false;
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ['onemap_sayfa.js'], world: 'MAIN', injectImmediately: true });
      await chrome.scripting.executeScript({ target: { tabId }, files: ['onemap_kopru.js'], injectImmediately: true });
      return true;
    } catch (e) {
      return false;
    }
  }

  // Sekmede tek sorgu; köprü yoksa betikleri yükleyip bir kez daha dener.
  async function sekmedeSorgu(sekme, servis, params) {
    const m = { tur: 'onemap-sorgu', istek_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, servis, params };
    try {
      const y = await chrome.tabs.sendMessage(sekme.id, m);
      if (y) return y;
    } catch (e) { /* köprü yok */ }
    if (!(await betikYukle(sekme.id))) return { hata: 'sekme' };
    try {
      return (await chrome.tabs.sendMessage(sekme.id, m)) || { hata: 'sekme' };
    } catch (e) {
      return { hata: 'sekme' };
    }
  }

  async function sorgula(sekme, plan, where, geometri, ek) {
    const params = {
      where, outFields: plan.alanlar.join(','), returnGeometry: geometri ? 'true' : 'false', outSR: '4326', f: 'json',
      ...(ek || {}),
    };
    let y = await sekmedeSorgu(sekme, plan.servis, params);
    if (y.hata === 'arcgis' && params.resultRecordCount) {          // sayfalama desteklenmiyor: sunucu sınırıyla
      sayfaDesteksiz = true;
      delete params.resultRecordCount;
      y = await sekmedeSorgu(sekme, plan.servis, params);
    }
    return y;
  }

  async function aramalar(sekme, plan) {
    let bulunan = 0;
    for (const a of plan.arama || []) {
      const y = await sorgula(sekme, plan, a.where, true);
      if (y.hata) return { hata: y.hata, mesaj: y.mesaj, bulunan };
      const binalar = (y.features || []).map(sadeSatir);
      bulunan += binalar.length;
      const s = await uygulama('/api/onemap/binalar', { tur: 'arama', aranan: { alan: a.alan, degerler: a.degerler }, binalar });
      if (s.durum !== 'tamam') return { hata: s.durum, bulunan };
      await bekle(plan.bekleme_ms || 800);
    }
    return { bulunan };
  }

  async function tarama(sekme, plan) {
    const t = plan.tarama;
    if (!t) return { sayfa: 0 };
    let imlec = Number(t.basla) || 0;
    let sayfa = 0;
    let okunan = 0;
    for (; sayfa < EN_COK_SAYFA; sayfa++) {
      const ek = { orderByFields: 'OBJECTID ASC', ...(sayfaDesteksiz ? {} : { resultRecordCount: plan.sayfa || 500 }) };
      const y = await sorgula(sekme, plan, `(${plan.taban}) AND OBJECTID > ${imlec}`, t.tur === 'artimli', ek);
      if (y.hata) return { hata: y.hata, mesaj: y.mesaj, sayfa, okunan };
      const binalar = (y.features || []).map(sadeSatir);
      okunan += binalar.length;
      const enBuyuk = binalar.reduce((m, b) => Math.max(m, b.objectid || 0), imlec);
      const bitti = !binalar.length || enBuyuk <= imlec || (!y.asim && binalar.length < (plan.sayfa || 500));
      const s = await uygulama('/api/onemap/binalar', { tur: t.tur, binalar, imlec: enBuyuk, bitti });
      if (s.durum !== 'tamam') return { hata: s.durum, sayfa, okunan };
      imlec = enBuyuk;
      if (bitti) return { sayfa: sayfa + 1, okunan, bitti: true };
      await bekle(plan.bekleme_ms || 800);
    }
    return { sayfa, okunan };
  }

  async function onemapEsitle(neden) {
    if (calisiyor && Date.now() - calisiyor < KILIT_MS) return { durum: 'suruyor' };
    const sekme = await sekmeBul();
    if (!sekme) {
      await durumYaz({ durum: 'sekme_yok', denendi: Date.now() });
      return { durum: 'sekme_yok' };
    }
    calisiyor = Date.now();
    try {
      const p = await uygulama('/api/onemap/gorev');
      if (p.durum !== 'tamam') {
        await durumYaz({ durum: p.durum, denendi: Date.now() });
        return { durum: p.durum };
      }
      const plan = p.veri || {};
      if (!SERVIS.test(String(plan.servis || '')) || !Array.isArray(plan.alanlar)) {
        await durumYaz({ durum: 'plan_hatali', denendi: Date.now() });
        return { durum: 'plan_hatali' };
      }
      const a = await aramalar(sekme, plan);
      const t = a.hata ? { sayfa: 0 } : await tarama(sekme, plan);
      const hata = a.hata || t.hata || null;
      if (hata && !['kod_yok', 'kod_yanlis', 'sunucu_yok', 'sunucu_eski', 'sunucu_hata'].includes(hata)) {
        // OneMap tarafı hatası (oturum, ağ): sunucu kartında görünsün
        await uygulama('/api/onemap/binalar', { tur: 'artimli', binalar: [], hata: `${hata}${a.mesaj || t.mesaj ? `: ${a.mesaj || t.mesaj}` : ''}`.slice(0, 300) });
      }
      const durum = hata ? (hata === 'yetki' ? 'oturum_yok' : hata) : 'tamam';
      await durumYaz({ durum, neden, son: Date.now(), bulunan: a.bulunan || 0, okunan: t.okunan || 0, tamBitti: !!t.bitti });
      return { durum, bulunan: a.bulunan || 0, okunan: t.okunan || 0 };
    } finally {
      calisiyor = 0;
    }
  }

  let sayfaZamanlayici = null;
  chrome.runtime.onMessage.addListener((m) => {
    if (!m) return undefined;
    if (m.tur === 'onemap-sayfa') {            // OneMap sekmesi açıldı/yenilendi: biraz sonra eşitle
      if (sayfaZamanlayici) clearTimeout(sayfaZamanlayici);
      sayfaZamanlayici = setTimeout(() => { sayfaZamanlayici = null; onemapEsitle('sayfa').catch(() => {}); }, 5000);
    }
    return undefined;
  });
  if (chrome.alarms) {
    chrome.alarms.create('onemap', { periodInMinutes: ARALIK_DK });
    chrome.alarms.onAlarm.addListener((a) => { if (a.name === 'onemap') onemapEsitle('zamanli').catch(() => {}); });
  }

  g.__dehanetOnemap = { onemapEsitle, sadeSatir, aramalar, tarama, sekmedeSorgu };
})();
