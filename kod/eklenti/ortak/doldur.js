/*
 * Saha eklentisi — BOSS formunu DOLDURUR, asla KAYDETMEZ (G1/G3; Turkcell BT onayı bekleniyor).
 *
 * Kırmızı çizgi: bu dosya hiçbir düğmeye basmaz, formu göndermez, tuş olayı üretmez.
 * Yalnız alan değerini yazar ve çatıların (Angular / React) dinlediği input / change / blur olaylarını yayar.
 * "Kaydet"e her zaman kişi basar. test/birim/guvenlik.test.js bu kuralı kaynak kodda denetler.
 */
(function (kok, fabrika) {
  const node = typeof module === 'object' && module.exports;
  const M = node ? require('./metin.js') : kok.DSMetin;
  const A = node ? require('./ayristir.js') : kok.DSAyristir;
  const m = fabrika(M, A);
  if (node) module.exports = m;
  else kok.DSDoldur = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (M, A) {
  'use strict';

  const { anahtar, sade, tarihBicimle, tarihKisa } = M;

  const YAZILABILIR = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]):not([type=password]):not([type=file]):not([type=checkbox]):not([type=radio]), select, textarea';
  const SECMELI = '[role="combobox"], mat-select, .mat-mdc-select, .ng-select, .p-dropdown, .select2-selection';
  const HEPSI = YAZILABILIR + ', ' + SECMELI;

  const ETIKET = {
    ekip: 'Ekip',
    randevu_baslangic: 'Randevu başlangıç',
    randevu_bitis: 'Randevu bitiş',
    randevu_baslangic_saat: 'Başlangıç saati',
    randevu_bitis_saat: 'Bitiş saati',
  };

  function _gorunur(el) {
    if (el.disabled) return false;
    const st = el.ownerDocument.defaultView.getComputedStyle ? el.ownerDocument.defaultView.getComputedStyle(el) : null;
    return !(st && (st.display === 'none' || st.visibility === 'hidden'));
  }

  function _niteliklerAnahtar(el) {
    return ['formcontrolname', 'name', 'id', 'aria-label', 'placeholder', 'data-testid', 'ng-reflect-name']
      .map((n) => anahtar(el.getAttribute(n) || '')).filter(Boolean);
  }

  function _etiketMetni(el, doc) {
    const parcalar = [];
    if (el.id) {
      try {
        const l = doc.querySelector('label[for="' + el.id.replace(/"/g, '') + '"]');
        if (l) parcalar.push(A.metin(l));
      } catch (_) { /* id seçiciye uymuyor */ }
    }
    const kapLabel = el.closest('label');
    if (kapLabel) parcalar.push(A.kendiMetni(kapLabel));
    const lb = el.getAttribute('aria-labelledby');
    if (lb) lb.split(/\s+/).forEach((id) => { const x = doc.getElementById(id); if (x) parcalar.push(A.metin(x)); });
    return parcalar.map((p) => anahtar(String(p).replace(/[:：*]+\s*$/, ''))).filter(Boolean);
  }

  /** Alan tanımına (secici / ad / etiket) göre form kontrolünü bulur. Düğme ve gizli alan asla dönmez. */
  function kontrolBul(doc, tanim) {
    if (!tanim) return null;
    if (tanim.secici) {
      try {
        const el = doc.querySelector(tanim.secici);
        if (el) return el;
      } catch (_) { /* geçersiz seçici */ }
    }
    const adlar = (tanim.ad || []).map(anahtar);
    const etiketler = (tanim.etiket || []).map(anahtar);
    const kontroller = Array.from(doc.querySelectorAll(HEPSI)).filter(_gorunur);
    // 1) ad niteliği tam eşleşme
    for (const el of kontroller) if (_niteliklerAnahtar(el).some((k) => adlar.includes(k))) return el;
    // 2) etiket (label[for], saran label, aria-labelledby) tam eşleşme
    for (const el of kontroller) if (_etiketMetni(el, doc).some((k) => etiketler.includes(k))) return el;
    // 3) ekrandaki etiket metni → en yakın kaptaki kontrol
    for (const e of doc.querySelectorAll('label, mat-label, span, div, td, th, dt, p, strong, b')) {
      const kendi = anahtar(sade(A.kendiMetni(e)).replace(/[:：*]+\s*$/, ''));
      if (!kendi || !etiketler.includes(kendi)) continue;
      let kap = e;
      for (let i = 0; i < 4 && kap; i++) {
        kap = kap.parentElement;
        if (!kap) break;
        const aday = Array.from(kap.querySelectorAll(HEPSI)).filter(_gorunur);
        if (aday.length === 1 || (aday.length > 1 && i >= 1)) {
          // Etiketten SONRA gelen ilk kontrol (belge sırasıyla).
          const sonraki = aday.find((c) => e.compareDocumentPosition(c) & 4);
          if (sonraki) return sonraki;
        }
      }
    }
    // 4) ad niteliği içinde geçme (uzun eşanlamlılar)
    for (const el of kontroller) if (_niteliklerAnahtar(el).some((k) => adlar.some((a) => a.length >= 6 && k.includes(a)))) return el;
    return null;
  }

  /** Çatıların fark edeceği şekilde değer yazar (tıklama / tuş YOK). */
  function degerYaz(el, deger) {
    const W = el.ownerDocument.defaultView;
    const proto = el.tagName === 'TEXTAREA' ? W.HTMLTextAreaElement.prototype
      : el.tagName === 'SELECT' ? W.HTMLSelectElement.prototype : W.HTMLInputElement.prototype;
    const d = Object.getOwnPropertyDescriptor(proto, 'value');
    if (d && d.set) d.set.call(el, deger); else el.value = deger;
    el.dispatchEvent(new W.Event('input', { bubbles: true }));
    el.dispatchEvent(new W.Event('change', { bubbles: true }));
    el.dispatchEvent(new W.Event('blur'));
  }

  function _vurgula(el) {
    try {
      const eski = el.style.outline, eskiO = el.style.outlineOffset;
      el.style.outline = '2px solid #0b63e5';
      el.style.outlineOffset = '2px';
      el.ownerDocument.defaultView.setTimeout(() => { el.style.outline = eski; el.style.outlineOffset = eskiO; }, 6000);
    } catch (_) { /* stil yazılamadı: önemsiz */ }
  }

  function _secenekSec(sel, hedef) {
    const k = anahtar(hedef);
    const secenekler = Array.from(sel.options || []);
    let o = secenekler.find((x) => anahtar(x.text) === k || anahtar(x.value) === k);
    if (!o) {
      const icerenler = secenekler.filter((x) => k.length >= 3 && (anahtar(x.text).includes(k) || k.includes(anahtar(x.text)) && anahtar(x.text).length >= 3));
      if (icerenler.length === 1) o = icerenler[0];
    }
    if (!o) return false;
    if (sel.value === o.value) return 'ayni';
    degerYaz(sel, o.value);
    return true;
  }

  /** Alanın beklediği biçim: datetime-local | date | time | iso | tr (GG.AA.YYYY SS:DD) | tr-tarih (GG.AA.YYYY). */
  function _tarihBicimi(el) {
    const tip = (el.getAttribute('type') || 'text').toLowerCase();
    if (tip === 'datetime-local') return 'datetime-local';
    if (tip === 'date') return 'date';
    if (tip === 'time') return 'time';
    const ph = (el.getAttribute('placeholder') || '').toLowerCase();
    if (/yyyy-mm-dd|yyyy-aa-gg/.test(ph)) return 'iso';
    if (/(gg|dd)[./](aa|mm)[./](yyyy|yy)/.test(ph) && !/(ss|hh)[:.](dd|mm)/.test(ph)) return 'tr-tarih';
    return 'tr';
  }

  function _kayit(alan, durum, deger, not) {
    return { alan, etiket: ETIKET[alan] || alan, durum, deger: deger || '', not: not || '' };
  }

  function _metinYaz(el, alan, deger, gosterim, rapor) {
    if (el.readOnly || el.getAttribute('aria-readonly') === 'true') {
      rapor.push(_kayit(alan, 'elle', gosterim, 'Salt okunur alan: takvimden / listeden seçin.'));
      return;
    }
    if (sade(el.value) === sade(deger)) { rapor.push(_kayit(alan, 'ayni', gosterim)); return; }
    degerYaz(el, deger);
    _vurgula(el);
    const oneri = el.getAttribute('role') === 'combobox' || el.getAttribute('aria-autocomplete') || el.getAttribute('list');
    rapor.push(_kayit(alan, oneri ? 'elle' : 'dolduruldu', gosterim, oneri ? 'Açılan listeden doğru seçeneği seçin.' : ''));
  }

  function _ekipDoldur(doc, S, ekip, rapor) {
    const el = kontrolBul(doc, S.boss.form.ekip);
    if (!el) { rapor.push(_kayit('ekip', 'bulunamadi', ekip, 'Ekip alanı bulunamadı: elle seçin.')); return; }
    if (el.tagName === 'SELECT') {
      const r = _secenekSec(el, ekip);
      if (r === 'ayni') rapor.push(_kayit('ekip', 'ayni', ekip));
      else if (r) { _vurgula(el); rapor.push(_kayit('ekip', 'dolduruldu', ekip)); }
      else rapor.push(_kayit('ekip', 'elle', ekip, 'Listede birebir bulunamadı: elle seçin.'));
      return;
    }
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') { _metinYaz(el, 'ekip', ekip, ekip, rapor); return; }
    _vurgula(el);
    rapor.push(_kayit('ekip', 'elle', ekip, 'Bu liste eklentiyle doldurulamıyor: elle seçin.'));
  }

  function _tarihDoldur(doc, S, alan, saatAlani, normal, rapor) {
    const gosterim = tarihBicimle(normal, 'tr');
    const el = kontrolBul(doc, S.boss.form[alan]);
    if (!el) { rapor.push(_kayit(alan, 'bulunamadi', gosterim, 'Alan bulunamadı: elle girin.')); return; }
    if (el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA') {
      _vurgula(el);
      rapor.push(_kayit(alan, 'elle', gosterim, 'Takvimden seçin.'));
      return;
    }
    const bicim = _tarihBicimi(el);
    if (bicim === 'time') {
      rapor.push(_kayit(alan, 'elle', gosterim, 'Tarih alanı bulunamadı: elle girin.'));
      return;
    }
    const saatEl = bicim === 'datetime-local' ? null : kontrolBul(doc, S.boss.form[saatAlani]);
    const ayriSaat = !!saatEl && saatEl !== el;
    // Tarih alanı yalnız tarihi mi taşıyor? (tarih + ayrı saat alanı düzeni)
    const tarihSadece = bicim === 'date' || bicim === 'tr-tarih' || ayriSaat;
    let deger;
    if (bicim === 'datetime-local') deger = tarihBicimle(normal, 'datetime-local');
    else if (bicim === 'date') deger = tarihBicimle(normal, 'date');
    else if (bicim === 'iso') deger = tarihBicimle(normal, tarihSadece ? 'date' : 'iso');
    else deger = tarihBicimle(normal, tarihSadece ? 'tr-tarih' : 'tr');
    _metinYaz(el, alan, deger, gosterim, rapor);
    if (tarihSadece && ayriSaat) {
      _metinYaz(saatEl, saatAlani, tarihBicimle(normal, 'time'), tarihBicimle(normal, 'time'), rapor);
    } else if (tarihSadece && !ayriSaat) {
      rapor.push(_kayit(saatAlani, 'elle', tarihBicimle(normal, 'time'), 'Saat alanı bulunamadı: saati elle girin.'));
    }
  }

  /**
   * Giden kutusu satırının alanlarını BOSS formuna yazar.
   * alanlar: {ekip, randevu_baslangic, randevu_bitis} (sunucudan, "YYYY-AA-GG SS:DD:ss").
   * Dönen: [{alan, etiket, durum: 'dolduruldu'|'ayni'|'elle'|'bulunamadi', deger, not}]
   */
  function doldur(doc, alanlar, S) {
    const rapor = [];
    if (!alanlar) return rapor;
    if (alanlar.ekip) _ekipDoldur(doc, S, sade(alanlar.ekip), rapor);
    if (alanlar.randevu_baslangic) _tarihDoldur(doc, S, 'randevu_baslangic', 'randevu_baslangic_saat', alanlar.randevu_baslangic, rapor);
    if (alanlar.randevu_bitis) _tarihDoldur(doc, S, 'randevu_bitis', 'randevu_bitis_saat', alanlar.randevu_bitis, rapor);
    return rapor;
  }

  /** Panelde gösterilecek kısa özet ("Ekip ✓ · Randevu elle"). */
  function ozet(rapor) {
    const tamam = rapor.filter((r) => r.durum === 'dolduruldu' || r.durum === 'ayni').length;
    return { tamam, elle: rapor.length - tamam, toplam: rapor.length };
  }

  return { kontrolBul, degerYaz, doldur, ozet, ETIKET, tarihKisa };
});
