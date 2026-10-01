/*
 * Saha eklentisi — sunucu istemcisi (yalnız arka plan çalışanı kullanır; içerik betikleri jetonu görmez).
 *
 * Yalnız aşağıdaki SABİT yollar çağrılabilir; içerik betiği yol ya da adres veremez.
 * Sözleşme: belgeler/eklenti/SUNUCU_SOZLESMESI.md
 */
(function (kok, fabrika) {
  const m = fabrika();
  if (typeof module === 'object' && module.exports) module.exports = m;
  else kok.DSApi = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const YOLLAR = {
    eslestir: { yontem: 'POST', yol: '/api/eklenti/eslestir', jetonsuz: true },
    ben: { yontem: 'GET', yol: '/api/eklenti/ben' },
    ayar: { yontem: 'GET', yol: '/api/eklenti/ayar' },
    cikis: { yontem: 'POST', yol: '/api/eklenti/cikis' },
    giden: { yontem: 'GET', yol: '/api/boss/giden' },
    islendi: { yontem: 'POST', yol: '/api/boss/giden/{is_no}/islendi' },
    boss_task: { yontem: 'POST', yol: '/api/eklenti/boss/task' },
    ticket: { yontem: 'POST', yol: '/api/eklenti/ticket/durum' },
    talep: { yontem: 'POST', yol: '/api/eklenti/talep' },
    rehber: { yontem: 'POST', yol: '/api/eklenti/rehber' },
    yapi: { yontem: 'POST', yol: '/api/eklenti/yapi' },
  };

  /**
   * Kullanıcının yazdığı sunucu adresi → köken ("http://10.54.3.75:8080").
   * Yol, sorgu, kullanıcı adı/şifre kabul edilmez; şema yoksa http varsayılır.
   */
  function sunucuDuzelt(ham) {
    let s = String(ham || '').trim();
    if (!s) return { ok: false, hata: 'Sunucu adresini yazın.' };
    if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = 'http://' + s;
    let u;
    try { u = new URL(s); } catch (_) { return { ok: false, hata: 'Adres anlaşılamadı. Örnek: http://10.54.3.75:8080' }; }
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return { ok: false, hata: 'Adres http:// ya da https:// ile başlamalı.' };
    if (u.username || u.password) return { ok: false, hata: 'Adreste kullanıcı adı ya da şifre olmamalı.' };
    if (!u.hostname) return { ok: false, hata: 'Adres anlaşılamadı.' };
    if ((u.pathname && u.pathname !== '/') || u.search || u.hash) {
      return { ok: false, hata: 'Yalnız sunucu adresini yazın (ör. http://10.54.3.75:8080), sayfa yolu olmadan.' };
    }
    return { ok: true, koken: u.origin, desen: u.origin + '/*', host: u.host };
  }

  function yolKur(ad, param) {
    const t = YOLLAR[ad];
    if (!t) throw new Error('Bilinmeyen uç: ' + ad);
    return t.yol.replace(/\{(\w+)\}/g, (_, k) => {
      const v = param && param[k];
      if (v == null || !/^[\w.-]{1,64}$/.test(String(v))) throw new Error('Geçersiz parametre: ' + k);
      return encodeURIComponent(String(v));
    });
  }

  /** HTTP durumu + sunucu gövdesi → Türkçe, kullanıcıya gösterilecek hata. */
  function hataMetni(durum, veri, host) {
    const d = veri && typeof veri === 'object' ? veri.detail : null;
    const sunucuMetni = d && typeof d === 'object' && typeof d.hata === 'string' ? d.hata : null;
    const kod = d && typeof d === 'object' && typeof d.kod === 'string' ? d.kod : null;
    if (durum === 0) return { hata: 'Saha sunucusuna ulaşılamadı' + (host ? ' (' + host + ')' : '') + '. Bilgisayar şirket ağında mı?', kod: 'ag' };
    if (durum === 401) return { hata: sunucuMetni || 'Eşleşme sona erdi. Eklentiyi yeniden bağlayın.', kod: 'eslesme_bitti' };
    if (durum === 403) return { hata: sunucuMetni || 'Bu işlem görevinize kapalı.', kod: kod || 'yasak' };
    if (durum === 404 && !kod) return { hata: 'Sunucu bu özelliği henüz desteklemiyor. Saha Sistemi güncellenmeli.', kod: 'uc_yok' };
    if (durum === 429) {
      const sn = veri && veri.bekle_sn ? veri.bekle_sn : (d && d.bekle_sn) || null;
      return { hata: sunucuMetni || ('Çok sık gönderim. ' + (sn ? sn + ' sn' : 'Biraz') + ' sonra tekrar deneyin.'), kod: 'cok_sik' };
    }
    if (durum >= 500) return { hata: 'Sunucuda bir hata oluştu. Biraz sonra tekrar deneyin.', kod: 'sunucu' };
    if (sunucuMetni) return { hata: sunucuMetni, kod: kod || 'hata' };
    if (durum === 422) return { hata: 'Gönderilen bilgi eksik ya da hatalı.', kod: 'gecersiz' };
    return { hata: 'Beklenmeyen yanıt (' + durum + ').', kod: 'hata' };
  }

  /**
   * Sunucu çağrısı. fetchFn: global fetch (testte sahte). Dönen: {ok, durum, veri} ya da {ok:false, durum, hata, kod}.
   */
  async function cagir(fetchFn, baglanti, ad, secenek) {
    const t = YOLLAR[ad];
    if (!t) return { ok: false, durum: 0, hata: 'Bilinmeyen işlem.', kod: 'ic' };
    const s = secenek || {};
    let url;
    try { url = baglanti.sunucu + yolKur(ad, s.param); } catch (e) { return { ok: false, durum: 0, hata: 'Geçersiz istek.', kod: 'ic' }; }
    const baslik = { 'Accept': 'application/json', 'X-Saha-Eklenti': String(s.surum || '1') };
    if (!t.jetonsuz) {
      if (!baglanti.jeton) return { ok: false, durum: 401, hata: 'Eklenti bağlı değil.', kod: 'eslesme_yok' };
      baslik.Authorization = 'Bearer ' + baglanti.jeton;
    }
    const ist = { method: t.yontem, headers: baslik, credentials: 'omit', cache: 'no-store', redirect: 'error' };
    if (s.govde !== undefined) {
      baslik['Content-Type'] = 'application/json';
      ist.body = JSON.stringify(s.govde);
    }
    const kontrol = typeof AbortController !== 'undefined' ? new AbortController() : null;
    if (kontrol) ist.signal = kontrol.signal;
    const zaman = kontrol ? setTimeout(() => kontrol.abort(), s.zamanAsimi || 12000) : null;
    let yanit;
    try {
      yanit = await fetchFn(url, ist);
    } catch (_) {
      if (zaman) clearTimeout(zaman);
      let host = '';
      try { host = new URL(baglanti.sunucu).host; } catch (__) { /* yok */ }
      return Object.assign({ ok: false, durum: 0 }, hataMetni(0, null, host));
    }
    if (zaman) clearTimeout(zaman);
    let veri = null;
    if (yanit.status !== 204) {
      try { veri = await yanit.json(); } catch (_) { veri = null; }
    }
    if (yanit.ok) return { ok: true, durum: yanit.status, veri };
    if (yanit.status === 429) {
      const ra = yanit.headers && yanit.headers.get ? Number(yanit.headers.get('Retry-After')) : NaN;
      if (ra && veri && typeof veri === 'object') veri.bekle_sn = ra;
      else if (ra) veri = { bekle_sn: ra };
    }
    return Object.assign({ ok: false, durum: yanit.status, veri }, hataMetni(yanit.status, veri));
  }

  return { YOLLAR, sunucuDuzelt, yolKur, hataMetni, cagir };
});
