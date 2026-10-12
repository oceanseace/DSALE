// OneMap sayfası (onemap_sayfa.js, MAIN) ↔ arka plan (onemap_arka.js) köprüsü; yalnız aynı kökenden mesaj.
// Arka plan "onemap-sorgu" gönderir, köprü sayfaya iletir, sonucu aynı mesajın yanıtı olarak döndürür.
// Oturum bilgisi bu köprüden hiç geçmez (sayfa betiği yalnız satırları ve hata kodunu verir).
(() => {
  const bekleyen = new Map();          // istek_id → sendResponse
  let etkin = true;
  const gonder = (m) => {
    try {
      const p = chrome.runtime.sendMessage(m);
      if (p && typeof p.catch === 'function') p.catch(() => {});
    } catch (e) {
      etkin = false;                   // eklenti yeniden yüklendi: bu köprü ölü
    }
  };

  window.addEventListener('message', (olay) => {
    if (olay.source !== window || olay.origin !== location.origin) return;
    const d = olay.data;
    if (!d || d.kaynak !== 'dehanet-onemap' || !etkin) return;
    if (d.tur === 'hazir') {
      gonder({ tur: 'onemap-sayfa' });
    } else if (d.tur === 'sonuc' && bekleyen.has(d.istek_id)) {
      const yanitla = bekleyen.get(d.istek_id);
      bekleyen.delete(d.istek_id);
      yanitla({ features: d.features, asim: d.asim, hata: d.hata, http: d.http, mesaj: d.mesaj, jetonVar: d.jetonVar });
    }
  });

  chrome.runtime.onMessage.addListener((m, _gonderen, yanitla) => {
    if (!m || m.tur !== 'onemap-sorgu' || !etkin) return undefined;
    bekleyen.set(m.istek_id, yanitla);
    window.postMessage({ kaynak: 'dehanet-onemap-komut', tur: 'sorgu', istek_id: m.istek_id, servis: m.servis,
      params: m.params }, location.origin);
    return true;                       // yanıt sonra (sendResponse)
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => gonder({ tur: 'onemap-sayfa' }));
  else gonder({ tur: 'onemap-sayfa' });
})();
