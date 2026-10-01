/*
 * Saha eklentisi — "Yapı keşfi" (belgeler/eklenti/SAYFA_HARITASI.md §6).
 *
 * Açık ekranın YAPISINI çıkarır, DEĞERLERİNİ asla: adres kalıbı, çatı işareti, tablo başlıkları + satır SAYISI,
 * form alanlarının etiket / ad / tür bilgisi (value YOK), düğme metinleri, bağlantı kalıpları, sayfanın
 * fetch/XHR yol kalıpları (gövde YOK). Bütün metinler ayrıca maskelenir (3+ rakam → #, e-posta → <e-posta>).
 * Döküm gönderilmeden önce kullanıcıya gösterilir.
 */
(function (kok, fabrika) {
  const node = typeof module === 'object' && module.exports;
  const M = node ? require('./metin.js') : kok.DSMetin;
  const m = fabrika(M);
  if (node) module.exports = m;
  else kok.DSYapi = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (M) {
  'use strict';

  const { maskele, sade } = M;

  function _yolKalibi(yol) {
    return String(yol || '')
      .split('/')
      .map((p) => (/\d/.test(p) || /^[0-9a-f-]{16,}$/i.test(p) || p.length > 40) ? (p ? '#' : p) : p)
      .join('/');
  }

  function _adresKalibi(href, taban) {
    try {
      const u = new URL(href, taban);
      const adlar = Array.from(new Set(Array.from(u.searchParams.keys()))).map((k) => maskele(k, 40));
      const ayni = taban && u.origin === new URL(taban).origin;
      return (ayni ? '' : u.origin) + _yolKalibi(u.pathname) + (adlar.length ? '?' + adlar.map((a) => a + '=<..>').join('&') : '');
    } catch (_) {
      return null;
    }
  }

  function _karmaSinifMi(c) {
    return /\d/.test(c) || c.length > 28 || /^(x[0-9a-z]{4,}|_[a-z0-9]{4,}|css-|sc-|jss)/i.test(c) || /^ng-(tns|star|untouched|touched|pristine|dirty|valid|invalid)/.test(c);
  }

  /** Kısa, kararlı bir CSS yolu (en çok 4 kat; kimlikte rakam varsa kullanılmaz). */
  function seciciYolu(el) {
    const parca = [];
    let cur = el;
    for (let i = 0; cur && cur.nodeType === 1 && i < 4; i++) {
      let p = cur.tagName.toLowerCase();
      const id = cur.getAttribute('id');
      if (id && !/\d/.test(id) && id.length < 40) { parca.unshift(p + '#' + id); break; }
      const tid = cur.getAttribute('data-testid');
      if (tid && !/\d{3,}/.test(tid)) p += '[data-testid="' + tid + '"]';
      const rol = cur.getAttribute('role');
      if (rol) p += '[role="' + rol + '"]';
      const siniflar = Array.from(cur.classList || []).filter((c) => !_karmaSinifMi(c)).slice(0, 2);
      if (siniflar.length) p += '.' + siniflar.join('.');
      parca.unshift(p);
      cur = cur.parentElement;
    }
    return parca.join(' > ');
  }

  function _metin(el) {
    const it = el.innerText;
    return sade(typeof it === 'string' ? it : el.textContent);
  }

  function _alanEtiketi(el, doc) {
    try {
      if (el.labels && el.labels.length) return _metin(el.labels[0]);
    } catch (_) { /* labels desteklenmiyor */ }
    const id = el.getAttribute('id');
    if (id) {
      try {
        const l = doc.querySelector('label[for="' + id.replace(/"/g, '') + '"]');
        if (l) return _metin(l);
      } catch (_) { /* geçersiz */ }
    }
    const lb = el.getAttribute('aria-labelledby');
    if (lb) {
      const x = doc.getElementById(lb.split(/\s+/)[0]);
      if (x) return _metin(x);
    }
    const ff = el.closest && el.closest('mat-form-field, .mat-mdc-form-field, .form-group, .p-field');
    if (ff) {
      const ml = ff.querySelector('mat-label, label, .mat-form-field-label');
      if (ml) return _metin(ml);
    }
    return el.getAttribute('aria-label') || '';
  }

  const ETIKET_SECICI = 'label, dt, th, mat-label, legend, [role="columnheader"], .label, .form-label, .mat-form-field-label';

  /**
   * Yapı dökümü. `perf` (performance) verilirse fetch/XHR yol kalıpları eklenir.
   * Dönen nesnede kullanıcı / müşteri değeri bulunmaz.
   */
  function cikar(doc, loc, perf) {
    const taban = loc.origin + '/';
    const hash = String(loc.hash || '');
    const hashYol = hash.split('?')[0];
    const hashParam = hash.includes('?') ? Array.from(new URLSearchParams(hash.split('?')[1]).keys()) : [];
    const d = {
      surum: 1,
      zaman: new Date().toISOString().slice(0, 16).replace('T', ' '),
      adres: {
        origin: loc.origin,
        yol: _yolKalibi(loc.pathname),
        hash_rota: _yolKalibi(hashYol).slice(0, 120),
        parametreler: Array.from(new Set([...new URLSearchParams(loc.search).keys(), ...hashParam])).map((k) => maskele(k, 40)),
      },
      cati: {
        angular: (doc.querySelector('[ng-version]') || { getAttribute: () => null }).getAttribute('ng-version'),
        react_kok: !!doc.querySelector('#root, [data-reactroot]'),
        app_kok: !!doc.getElementById('app'),
        vue: !!doc.querySelector('[data-v-app], #__nuxt'),
        iframe: doc.querySelectorAll('iframe').length,
      },
      tablolar: [],
      alanlar: [],
      dugmeler: [],
      etiketler: [],
      baglantilar: [],
      ag: [],
      sayac: { eleman: doc.getElementsByTagName('*').length },
    };

    const tablolar = Array.from(doc.querySelectorAll('table, [role="grid"], [role="table"], mat-table')).slice(0, 12);
    for (const t of tablolar) {
      let bas = Array.from(t.querySelectorAll('thead th, [role="columnheader"], mat-header-cell, .mat-header-cell'));
      if (!bas.length) { const ilk = t.querySelector('tr'); if (ilk) bas = Array.from(ilk.querySelectorAll('th')); }
      const satir = t.querySelectorAll('tbody tr, [role="row"], mat-row').length;
      d.tablolar.push({
        secici: seciciYolu(t),
        basliklar: bas.slice(0, 50).map((h) => maskele(_metin(h), 50)),
        satir_sayisi: satir,
      });
    }

    const alanlar = Array.from(doc.querySelectorAll('input:not([type=hidden]), select, textarea, [role="combobox"], mat-select, [formcontrolname]')).slice(0, 120);
    for (const el of alanlar) {
      d.alanlar.push({
        etiket: maskele(_alanEtiketi(el, doc), 50),
        etiket_tag: el.tagName.toLowerCase(),
        type: (el.getAttribute('type') || '').toLowerCase() || null,
        name: el.getAttribute('name') ? maskele(el.getAttribute('name'), 50) : null,
        id: el.getAttribute('id') ? maskele(el.getAttribute('id'), 50) : null,
        formcontrolname: el.getAttribute('formcontrolname') ? maskele(el.getAttribute('formcontrolname'), 50) : null,
        role: el.getAttribute('role'),
        placeholder: el.getAttribute('placeholder') ? maskele(el.getAttribute('placeholder'), 50) : null,
        zorunlu: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
        salt_okunur: el.hasAttribute('readonly') || el.hasAttribute('disabled'),
        secenek_sayisi: el.tagName === 'SELECT' ? el.options.length : null,
        secici: seciciYolu(el),
      });
    }

    const dugmeler = Array.from(doc.querySelectorAll('button, [role="button"], input[type=submit], input[type=button]')).slice(0, 80);
    for (const b of dugmeler) {
      d.dugmeler.push({
        metin: maskele(b.tagName === 'INPUT' ? '' : _metin(b), 40),
        aria_label: b.getAttribute('aria-label') ? maskele(b.getAttribute('aria-label'), 40) : null,
        type: b.getAttribute('type'),
        id: b.getAttribute('id') ? maskele(b.getAttribute('id'), 40) : null,
      });
    }

    const etiketler = new Set();
    for (const e of doc.querySelectorAll(ETIKET_SECICI)) {
      const t = _metin(e);
      if (t && t.length <= 40) etiketler.add(maskele(t, 40));
      if (etiketler.size >= 200) break;
    }
    // Kendi metni YALNIZ "Etiket:" olan öğeler (değer alt öğede). "Etiket: değer" tek metinse alınmaz:
    // iki noktanın solunda bir kişi adı olabilir (ör. sohbet satırı).
    for (const e of doc.querySelectorAll('span, div, p, strong, b, td')) {
      if (etiketler.size >= 200) break;
      let own = '';
      for (const n of e.childNodes) if (n.nodeType === 3) own += n.nodeValue;
      const m = sade(own).match(/^([^:]{2,35}):$/);
      if (m) etiketler.add(maskele(m[1], 40));
    }
    d.etiketler = Array.from(etiketler);

    const kaliplar = new Set();
    for (const a of doc.querySelectorAll('a[href]')) {
      const k = _adresKalibi(a.getAttribute('href'), taban);
      if (k && !k.startsWith('javascript')) kaliplar.add(k);
      if (kaliplar.size >= 20) break;
    }
    d.baglantilar = Array.from(kaliplar);

    if (perf && typeof perf.getEntriesByType === 'function') {
      const ag = new Set();
      for (const e of perf.getEntriesByType('resource')) {
        if (e.initiatorType !== 'xmlhttprequest' && e.initiatorType !== 'fetch') continue;
        const k = _adresKalibi(e.name, taban);
        if (k) ag.add(e.initiatorType + ' ' + k);
      }
      d.ag = Array.from(ag).slice(-50);
    }
    return d;
  }

  /** Dökümün kısa özeti (arayüzde gösterilir). */
  function ozet(d) {
    return {
      tablo: d.tablolar.length,
      baslik: d.tablolar.reduce((t, x) => t + x.basliklar.length, 0),
      alan: d.alanlar.length,
      dugme: d.dugmeler.length,
      etiket: d.etiketler.length,
      ag: d.ag.length,
    };
  }

  return { cikar, ozet, seciciYolu };
});
