// OneMap sayfasının İÇİNDE çalışır (MAIN world; onemap.turkcell.com.tr ve arcgis.turkcell.com.tr).
// Görev: arka planın verdiği ArcGIS bina sorgusunu SAYFANIN KENDİ oturumuyla (çerezler; sayfa jeton kullanıyorsa o
// jeton) yürütmek ve yalnız sonuç satırlarını köprüye (onemap_kopru.js) vermek.
//  - Sorgu yalnız https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0/query'ye gider;
//    başka adres istenirse reddedilir.
//  - Sayfanın ArcGIS isteklerinde "token" varsa YALNIZ bu kapanışın belleğinde tutulur ve yalnız aynı ArcGIS
//    sunucusuna giden sorguya eklenir. Hiçbir mesaja, depoya, günlüğe girmez; uygulamaya gitmez.
// BOSS kancasından (kanca.js) bağımsızdır; BOSS sayfasında yüklenmez.
(() => {
  const SURUM = 1;
  if (window.__dehanetOnemap === SURUM) return;
  window.__dehanetOnemap = SURUM;

  const ARCGIS = 'https://arcgis.turkcell.com.tr/';
  const IZINLI = /^https:\/\/arcgis\.turkcell\.com\.tr\/arcgis\/rest\/services\/ONEMAP\/BINA\/MapServer\/0$/;
  const ZAMAN_ASIMI_MS = 120000;   // OneMap büyük sayfalarda 60 sn yetmeyebiliyor
  let jeton = null;            // sayfanın ArcGIS jetonu (varsa) — yalnız burada

  const jetonAra = (metin) => {
    try {
      const s = String(metin || '');
      if (!s.includes('token=')) return;
      const m = s.match(/[?&]token=([^&#\s]+)/) || s.match(/(?:^|&)token=([^&#\s]+)/);
      if (m && m[1] && m[1].length >= 8) jeton = decodeURIComponent(m[1]);
    } catch (e) { /* sessiz */ }
  };
  const arcgisMi = (url) => String(url || '').startsWith(ARCGIS);

  // Sayfanın kendi ArcGIS isteklerinden jeton (değiştirmeden; yalnız okur)
  try {
    const asilFetch = window.fetch;
    window.fetch = function (girdi, secenek) {
      try {
        const url = typeof girdi === 'string' ? girdi : (girdi && girdi.url) || '';
        if (arcgisMi(url)) {
          jetonAra(url);
          if (secenek && typeof secenek.body === 'string') jetonAra(secenek.body);
          else if (secenek && secenek.body instanceof URLSearchParams) jetonAra(secenek.body.toString());
        }
      } catch (e) { /* sessiz */ }
      return asilFetch.apply(this, arguments);
    };
    const XO = XMLHttpRequest.prototype.open;
    const XS = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (yontem, url) {
      try { this.__dhOm = arcgisMi(url); if (this.__dhOm) jetonAra(url); } catch (e) { /* sessiz */ }
      return XO.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function (govde) {
      try { if (this.__dhOm && typeof govde === 'string') jetonAra(govde); } catch (e) { /* sessiz */ }
      return XS.apply(this, arguments);
    };
  } catch (e) { /* sessiz */ }

  const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

  async function istek(servis, params, kimlik) {
    const govde = new URLSearchParams();
    for (const [k, v] of Object.entries(params || {})) if (v !== undefined && v !== null) govde.set(k, String(v));
    if (jeton) govde.set('token', jeton);
    const ac = typeof AbortController === 'function' ? new AbortController() : null;
    const sayac = ac ? setTimeout(() => ac.abort(), ZAMAN_ASIMI_MS) : null;
    try {
      const y = await fetch(`${servis}/query`, {
        method: 'POST', body: govde.toString(), credentials: kimlik,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, ...(ac ? { signal: ac.signal } : {}),
      });
      if (y.status === 401 || y.status === 403) return { hata: 'yetki', http: y.status };
      if (!y.ok) return { hata: 'http', http: y.status };
      const j = await y.json();
      if (j && j.error) {
        const kod = Number(j.error.code) || 0;
        return { hata: kod === 498 || kod === 499 || kod === 403 ? 'yetki' : 'arcgis', http: kod,
          mesaj: String(j.error.message || '').slice(0, 200) };
      }
      return { features: Array.isArray(j && j.features) ? j.features : [], asim: !!(j && j.exceededTransferLimit) };
    } finally {
      if (sayac) clearTimeout(sayac);
    }
  }

  async function sorgu(m) {
    if (!IZINLI.test(String(m.servis || ''))) return { hata: 'adres' };
    let son = null;
    for (let deneme = 0; deneme < 3; deneme++) {
      try {
        // önce sayfanın çerezleriyle; CORS çerezsiz izin veriyorsa (ağ hatası) çerezsiz + jeton
        try {
          son = await istek(m.servis, m.params, 'include');
        } catch (e) {
          if (e && e.name === 'AbortError') throw e;
          son = await istek(m.servis, m.params, 'omit');
        }
        if (!son.hata || son.hata === 'yetki' || son.hata === 'adres') return son;
      } catch (e) {
        son = { hata: 'ag', mesaj: String((e && e.message) || e).slice(0, 120) };
      }
      await bekle(1500 * (deneme + 1));
    }
    return son;
  }

  window.addEventListener('message', async (olay) => {
    if (olay.source !== window || olay.origin !== location.origin) return;
    const m = olay.data;
    if (!m || m.kaynak !== 'dehanet-onemap-komut' || m.tur !== 'sorgu') return;
    let sonuc;
    try { sonuc = await sorgu(m); } catch (e) { sonuc = { hata: 'ag', mesaj: String((e && e.message) || e).slice(0, 120) }; }
    window.postMessage({ kaynak: 'dehanet-onemap', tur: 'sonuc', istek_id: m.istek_id, ...sonuc, jetonVar: !!jeton },
      location.origin);
  });
  window.postMessage({ kaynak: 'dehanet-onemap', tur: 'hazir' }, location.origin);
})();
