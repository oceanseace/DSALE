/*
 * Saha eklentisi — ekran ayrıştırıcıları (yalnız OKUR, sayfaya dokunmaz).
 *
 *   BOSS     : task listesi (beyaz listedeki sütunlar) ve task detayı (etiket → değer)
 *   OWA      : açık mailin konu + gövde metni, OneDesk ticket no + yeni durum
 *   WhatsApp : mesaj satırı → metin, zaman, gönderen, yön, kimlik
 *   Atmosfer : personel kartları → ad + unvan (+ yetkili/ekip bölümü)
 *
 * Her işlev belgeyi / kökü parametre olarak alır (global yok) → Node + jsdom ile test edilir.
 */
(function (kok, fabrika) {
  const M = (typeof module === 'object' && module.exports) ? require('./metin.js') : kok.DSMetin;
  const m = fabrika(M);
  if (typeof module === 'object' && module.exports) module.exports = m;
  else kok.DSAyristir = m;
})(typeof globalThis !== 'undefined' ? globalThis : this, function (M) {
  'use strict';

  const { anahtar, sade, telefonDuzelt, tarihNormal, randevuAraligi } = M;

  // ------------------------------------------------------------------ ortak DOM yardımcıları
  /** Görünen metin: tarayıcıda innerText (gizli öğeleri atlar, satır sonlarını korur), jsdom'da textContent. */
  function metin(el) {
    if (!el) return '';
    const it = el.innerText;
    return typeof it === 'string' ? it : (el.textContent || '');
  }

  /** Öğenin yalnız kendi metin düğümleri (alt öğelerin metni hariç). */
  function kendiMetni(el) {
    let s = '';
    for (const n of el.childNodes) if (n.nodeType === 3) s += n.nodeValue;
    return s;
  }

  function ilkEslesen(kok, seciciler) {
    if (!kok) return null;
    for (const s of [].concat(seciciler || [])) {
      if (!s) continue;
      try {
        const el = kok.querySelector(s);
        if (el) return el;
      } catch (_) { /* geçersiz seçici: sıradakine geç */ }
    }
    return null;
  }

  function tumu(kok, secici) {
    try { return Array.from(kok.querySelectorAll(secici)); } catch (_) { return []; }
  }

  const KONTROL = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image]):not([type=password]):not([type=file]), select, textarea, [role="combobox"], mat-select, [contenteditable="true"]';

  /** Form öğesinin gösterdiği değer (select → seçili seçeneğin metni). */
  function kontrolDegeri(el) {
    if (!el) return '';
    const t = el.tagName;
    if (t === 'INPUT') {
      const tip = (el.getAttribute('type') || 'text').toLowerCase();
      if (tip === 'checkbox' || tip === 'radio') return el.checked ? 'Evet' : 'Hayır';
      return sade(el.value);
    }
    if (t === 'SELECT') {
      const o = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
      return o ? sade(o.text) : '';
    }
    if (t === 'TEXTAREA') return sade(el.value);
    const ic = el.querySelector && el.querySelector('input:not([type=hidden]), select, textarea');
    if (ic) return kontrolDegeri(ic);
    return sade(metin(el));
  }

  /** Eşanlamlı listesi → {anahtar: alan}. */
  function esanlamHaritasi(alanlar) {
    const h = new Map();
    for (const [alan, liste] of Object.entries(alanlar)) {
      for (const ad of liste) {
        const k = anahtar(ad);
        if (k && !h.has(k)) h.set(k, alan);
      }
    }
    return h;
  }

  function etiketAnahtari(s) {
    return anahtar(String(s || '').replace(/[:：*]+\s*$/, ''));
  }

  // ------------------------------------------------------------------ etiket → değer (detay ekranları)
  const ETIKET_ADAYI = 'label, dt, th, td, span, div, p, strong, b, small, em, mat-label, legend, h3, h4, h5, h6, li';

  function _degerMi(s, harita) {
    const d = sade(s);
    return !!d && d.length <= 200 && !harita.has(etiketAnahtari(d));
  }

  function _kardesDegeri(el, harita) {
    for (let s = el.nextElementSibling, i = 0; s && i < 3; s = s.nextElementSibling, i++) {
      const kontrol = s.matches(KONTROL) ? s : s.querySelector(KONTROL);
      const d = kontrol ? kontrolDegeri(kontrol) : sade(metin(s));
      if (_degerMi(d, harita)) return d;
      if (d) return null;           // bir sonraki etiketle karşılaştık: bu etiketin değeri boş
    }
    return undefined;
  }

  function _etiketDegeri(el, harita, doc) {
    const t = el.tagName;
    if (t === 'LABEL') {
      const hedefId = el.getAttribute('for');
      if (hedefId) {
        const h = doc.getElementById(hedefId);
        if (h) return kontrolDegeri(h);
      }
      const ic = el.querySelector(KONTROL);
      if (ic) return kontrolDegeri(ic);
    }
    if (t === 'DT') {
      let s = el.nextElementSibling;
      while (s && s.tagName !== 'DD') s = s.nextElementSibling;
      if (s) return kontrolDegeri(s);
    }
    if (t === 'TH' || t === 'TD') {
      const s = el.nextElementSibling;
      if (s) {
        const d = kontrolDegeri(s);
        return _degerMi(d, harita) ? d : '';
      }
    }
    // Kardeş, sonra (yalnız bu etiketi saran) üst öğenin kardeşi — en çok 3 kat.
    let cur = el;
    for (let kat = 0; kat < 4 && cur; kat++) {
      const d = _kardesDegeri(cur, harita);
      if (d !== undefined) return d || '';
      const ust = cur.parentElement;
      if (!ust || etiketAnahtari(metin(ust)) !== etiketAnahtari(metin(el))) break;
      cur = ust;
    }
    // Form alanı kabı (mat-form-field, .form-group …) içindeki kontrol.
    const kap = el.closest && el.closest('mat-form-field, .mat-form-field, .mat-mdc-form-field, .form-group, .form-field, .field, .p-field');
    if (kap) {
      const k = kap.querySelector(KONTROL);
      if (k) return kontrolDegeri(k);
    }
    return '';
  }

  /**
   * Etiket metinlerinden değer toplar. alanlar: {alan: [eşanlamlılar]}.
   * Dönen: {alan: değer} (bulunamayan alan yok sayılır).
   */
  function etiketDegerleri(kok, alanlar) {
    const doc = kok.ownerDocument || kok;
    const harita = esanlamHaritasi(alanlar);
    const sonuc = {};
    for (const el of tumu(kok, ETIKET_ADAYI)) {
      const kendi = sade(kendiMetni(el));
      if (!kendi || kendi.length > 60) continue;
      // "Task No: 412102947" — etiket ve değer aynı metin düğümünde
      const ikili = kendi.match(/^([^:：]{2,40})[:：]\s*(.+)$/);
      if (ikili) {
        const alan = harita.get(etiketAnahtari(ikili[1]));
        if (alan && !(alan in sonuc) && _degerMi(ikili[2], harita)) { sonuc[alan] = sade(ikili[2]); continue; }
      }
      const alan = harita.get(etiketAnahtari(kendi));
      if (!alan || alan in sonuc) continue;
      const tam = sade(metin(el));
      if (etiketAnahtari(tam) !== etiketAnahtari(kendi)) {
        const kontrolIcinde = el.tagName === 'LABEL' && el.querySelector(KONTROL);
        if (!kontrolIcinde) {
          // "Durum: <b>Açık</b>" — etiket öğenin kendi metninde, değer alt öğede.
          if (/[:：]\s*$/.test(kendi) && el.children.length <= 3 && tam.startsWith(kendi)) {
            const kalan = sade(tam.slice(kendi.length));
            if (_degerMi(kalan, harita)) sonuc[alan] = kalan;
          }
          // Metni başka alt öğelerde de olan kapsayıcılar (ör. bütün satırı saran div) etiket değildir.
          continue;
        }
      }
      const d = _etiketDegeri(el, harita, doc);
      if (d) sonuc[alan] = d;
    }
    return sonuc;
  }

  // ------------------------------------------------------------------ BOSS
  function _bossAdresi(loc, S) {
    const href = String((loc && loc.href) || '').toLowerCase();
    return S.boss.yol_parcalari.some((p) => href.includes(p));
  }

  function _adrestenTaskNo(loc, S) {
    try {
      const m = String(loc.pathname + (loc.hash || '')).match(new RegExp(S.boss.detay_yol_deseni, 'i'));
      return m ? m[1] : null;
    } catch (_) { return null; }
  }

  function _taskNoTemizle(s) {
    const d = sade(s);
    const m = d.match(/\d{6,}/);
    if (m) return m[0];
    return /^[A-Za-z0-9][\w-]{3,30}$/.test(d) ? d : null;
  }

  function _hucreler(satir, hucreSec) {
    return Array.from(satir.children).filter((c) => {
      try { return c.matches(hucreSec); } catch (_) { return false; }
    });
  }

  function _basliklar(tablo, S) {
    for (const sec of S.boss.baslik_hucre) {
      const liste = tumu(tablo, sec).filter((h) => h.closest(S.boss.tablo_adaylari.join(',')) === tablo || S.boss.liste_tablo);
      if (liste.length >= 2) return liste;
    }
    // Başlıksız tablo: ilk satırın th hücreleri
    const ilk = tablo.querySelector('tr');
    if (ilk) {
      const th = Array.from(ilk.children).filter((c) => c.tagName === 'TH');
      if (th.length >= 2) return th;
    }
    return [];
  }

  /** Başlık metinleri → {sütun indeksi: alan}. Önce tam eşleşme, sonra ön ek. */
  function basliklariEsle(metinler, alanlar) {
    const harita = esanlamHaritasi(alanlar);
    const esle = new Map();
    const kullanilan = new Set();
    metinler.forEach((m, i) => {
      const alan = harita.get(etiketAnahtari(m));
      if (alan && !kullanilan.has(alan)) { esle.set(i, alan); kullanilan.add(alan); }
    });
    metinler.forEach((m, i) => {
      if (esle.has(i)) return;
      const k = etiketAnahtari(m);
      let enIyi = null, uzunluk = 0;
      for (const [ak, alan] of harita) {
        if (kullanilan.has(alan) || ak.length < 5) continue;
        if (k.startsWith(ak) && ak.length > uzunluk) { enIyi = alan; uzunluk = ak.length; }
      }
      if (enIyi) { esle.set(i, enIyi); kullanilan.add(enIyi); }
    });
    return esle;
  }

  function _tabloAdaylari(doc, S) {
    const sec = S.boss.liste_tablo || S.boss.tablo_adaylari.join(',');
    const liste = tumu(doc, sec);
    // İç içe adaylarda en içteki (asıl tablo) kalsın.
    return liste.filter((t) => !liste.some((u) => u !== t && t.contains(u) && u.matches('table, [role="grid"], [role="table"]')));
  }

  function _gorevNesnesi(ham) {
    const g = {};
    if (ham.task_no) g.task_no = _taskNoTemizle(ham.task_no);
    for (const a of ['task_adi', 'durum', 'ekip', 'randevu_durumu', 'merkeze_gonder']) if (ham[a]) g[a] = sade(ham[a]).slice(0, 120);
    if (ham.lokasyon) {
      const l = sade(ham.lokasyon).match(/[A-Z]?\d{6,10}/i);
      g.lokasyon = l ? l[0].toUpperCase() : sade(ham.lokasyon).slice(0, 40);
    }
    let bas = ham.randevu_baslangic ? tarihNormal(ham.randevu_baslangic) : null;
    let bit = ham.randevu_bitis ? tarihNormal(ham.randevu_bitis) : null;
    if (ham.randevu && (!bas || !bit)) {
      const r = randevuAraligi(ham.randevu);
      bas = bas || r.bas; bit = bit || r.bit;
    }
    if (ham.randevu_baslangic && !bas) bas = randevuAraligi(ham.randevu_baslangic).bas;
    if (bas) g.randevu_baslangic = bas;
    if (bit) g.randevu_bitis = bit;
    return g;
  }

  /**
   * BOSS task listesi. Yalnız S.boss.alanlar'daki sütunlar okunur (müşteri sütunları hiç okunmaz).
   * Dönen: {tablo: bool, eslesen: [alan], tasklar: [...], satir: n}
   */
  function bossListeOku(doc, S) {
    let enIyi = null;
    for (const t of _tabloAdaylari(doc, S)) {
      const bas = _basliklar(t, S);
      if (!bas.length) continue;
      const esle = basliklariEsle(bas.map((h) => sade(metin(h))), S.boss.alanlar);
      if (![...esle.values()].includes('task_no')) continue;
      if (!enIyi || esle.size > enIyi.esle.size) enIyi = { t, esle, bas };
    }
    if (!enIyi) return { tablo: false, eslesen: [], tasklar: [], satir: 0 };
    const hucreSec = S.boss.hucre.join(',');
    const basSatiri = enIyi.bas[0].parentElement;
    let satirlar = [];
    for (const sec of S.boss.satir) {
      satirlar = tumu(enIyi.t, sec).filter((r) => r !== basSatiri && _hucreler(r, hucreSec).length >= 2);
      if (satirlar.length) break;
    }
    const tasklar = [];
    const gorulen = new Set();
    for (const r of satirlar.slice(0, 500)) {
      const h = _hucreler(r, hucreSec);
      const ham = {};
      for (const [i, alan] of enIyi.esle) if (h[i]) ham[alan] = kontrolDegeri(h[i]);
      const g = _gorevNesnesi(ham);
      if (!g.task_no || gorulen.has(g.task_no)) continue;
      gorulen.add(g.task_no);
      tasklar.push(g);
    }
    return { tablo: true, eslesen: [...new Set(enIyi.esle.values())], tasklar, satir: satirlar.length };
  }

  /**
   * BOSS task detayı. telefon=true YALNIZ kullanıcı "Saha'ya gönder"e bastığında verilir.
   * Dönen: {task_no, durum, ekip, …, musteri_tel?, telefon: 'bulundu'|'etiket_yok'|'maskeli'|'gecersiz'|'okunmadi'}
   */
  function bossDetayOku(doc, loc, S, secenek) {
    const kok = (S.boss.detay_kok && ilkEslesen(doc, S.boss.detay_kok)) || doc.body || doc;
    const ham = etiketDegerleri(kok, S.boss.alanlar);
    if (!ham.task_no) {
      const adres = _adrestenTaskNo(loc, S);
      if (adres) ham.task_no = adres;
    }
    const g = _gorevNesnesi(ham);
    g.telefon = 'okunmadi';
    if (secenek && secenek.telefon) {
      const t = etiketDegerleri(kok, { musteri_tel: S.boss.telefon_etiketleri }).musteri_tel;
      if (!t) g.telefon = 'etiket_yok';
      else if (/[•*xX]{2,}/.test(t)) g.telefon = 'maskeli';
      else {
        const n = telefonDuzelt(t);
        if (n) { g.musteri_tel = n; g.telefon = 'bulundu'; } else g.telefon = 'gecersiz';
      }
    }
    return g;
  }

  /** 'liste' | 'detay' | null. Önce adres, sonra ekrandaki yapı. */
  function bossSayfaTuru(loc, doc, S) {
    const adresUygun = _bossAdresi(loc, S);
    const adresTask = _adrestenTaskNo(loc, S);
    if (adresUygun && adresTask) return 'detay';
    const liste = bossListeOku(doc, S);
    if (liste.tablo && liste.tasklar.length > 1) return 'liste';
    const d = etiketDegerleri(doc.body || doc, { task_no: S.boss.alanlar.task_no });
    if (d.task_no && _taskNoTemizle(d.task_no)) return 'detay';
    if (liste.tablo) return 'liste';
    return adresUygun ? 'liste' : null;
  }

  // ------------------------------------------------------------------ OWA / OneDesk
  function owaMailOku(doc, S) {
    const bolme = ilkEslesen(doc, S.owa.okuma_bolmesi) || doc;
    const govdeEl = ilkEslesen(bolme, S.owa.govde);
    if (!govdeEl) return null;
    const konuEl = ilkEslesen(bolme, S.owa.konu);
    const govde = String(metin(govdeEl) || '').slice(0, 20000);
    if (!sade(govde)) return null;
    return { konu: konuEl ? sade(metin(konuEl)).slice(0, 300) : '', govde };
  }

  const DURUMLAR = ['AÇIK', 'ÇÖZÜLDÜ', 'HATA', 'KAPATILDI', 'İPTAL', 'TRANSFER'];

  /** Serbest durum metni → Saha ticket durumu (saha/ticket.py DURUMLAR ile aynı küme). */
  function durumCoz(ham) {
    const k = anahtar(ham);
    if (!k) return null;
    const kural = [
      [['COZUL', 'COZUM', 'RESOLV', 'GIDERIL'], 'ÇÖZÜLDÜ'],
      [['KAPATIL', 'KAPAN', 'KAPALI', 'CLOSE'], 'KAPATILDI'],
      [['IPTAL', 'CANCEL'], 'İPTAL'],
      [['REDDEDIL', 'REJECT', 'HATA', 'BASARISIZ'], 'HATA'],
      [['TRANSFER', 'YONLENDIRIL', 'AKTARIL', 'ATANDI', 'ASSIGN'], 'TRANSFER'],
      [['ACIK', 'ACILDI', 'OLUSTURUL', 'KAYDEDIL', 'OPEN', 'NEW', 'YENI'], 'AÇIK'],
    ];
    for (const [onekler, durum] of kural) if (onekler.some((o) => k.startsWith(o))) return durum;
    return null;
  }

  const DURUM_IFADELERI = [
    [/çözüldü|çözülmüştür|çözümlendi|çözüme kavuş|giderildi|cozuldu|\bresolved\b/i, 'ÇÖZÜLDÜ'],
    [/kapatıldı|kapatılmıştır|kapandı|kapatildi|\bclosed\b/i, 'KAPATILDI'],
    [/iptal edil|iptal edilmiştir|\bcancell?ed\b/i, 'İPTAL'],
    [/reddedildi|reddedilmiştir|hatalı açıl|\brejected\b/i, 'HATA'],
    [/transfer edil|yönlendiril|aktarıldı|ekibine atandı|\btransferred\b|\bassigned\b/i, 'TRANSFER'],
    [/kaydınız açıl|kaydı açıl|oluşturuldu|açılmıştır|\bcreated\b|\bopened\b/i, 'AÇIK'],
  ];

  function _ilkIfade(metin_) {
    let enIyi = null;
    for (const [re, durum] of DURUM_IFADELERI) {
      const m = re.exec(metin_);
      if (m && (!enIyi || m.index < enIyi.i)) enIyi = { i: m.index, durum };
    }
    return enIyi ? enIyi.durum : null;
  }

  const TICKET_ETIKETLI = /(?:one\s*desk(?:\s*(?:id|no))?|ticket|çağrı|cagri|kayıt|kayit|talep|incident)\s*(?:no\.?|numarası|numarasi|numara|id|kimliği|kimligi)?\s*[:#=\-–]?\s*(?:no\s*[:#]?\s*)?#?\s*([A-Z]{0,4}\d{6,15})\b/i;
  const TICKET_CIPLAK = /(?<![\d])(10\d{9})(?![\d])/;
  const TICKET_REMEDY = /\b((?:INC|REQ|WO|CRQ|SR)\d{6,15})\b/i;
  const DURUM_ETIKETLI = /(?:yeni\s+durum(?:u)?|son\s+durum(?:u)?|durum(?:u)?|statü(?:sü)?|statu(?:su)?|status|state)\s*[:=\-–]\s*([A-Za-zÇĞİÖŞÜçğıöşü][A-Za-zÇĞİÖŞÜçğıöşü ]{1,30})/i;

  /**
   * OneDesk bildirim maili → {ticket_no, durum, guven, onedesk}. Ticket no yoksa null.
   * Gerçek mail kalıbı henüz bilinmiyor (SAYFA_HARITASI §2): etiketli kalıp "kesin", çıplak numara "tahmin" sayılır;
   * şerit durumu her zaman kullanıcıya değiştirilebilir gösterir.
   */
  function onedeskCoz(konu, govde, S) {
    const tum = sade(konu || '') + '\n' + String(govde || '');
    const kucuk = tum.toLocaleLowerCase('tr');
    const isaretler = (S && S.owa && S.owa.onedesk_isaret) || ['onedesk'];
    const onedesk = isaretler.some((i) => kucuk.includes(i));
    let ticket = null, guven = 'tahmin';
    let m = TICKET_ETIKETLI.exec(tum);
    if (m) { ticket = m[1].toUpperCase(); guven = 'etiketli'; }
    if (!ticket && (m = TICKET_REMEDY.exec(tum))) ticket = m[1].toUpperCase();
    if (!ticket && onedesk && (m = TICKET_CIPLAK.exec(tum))) ticket = m[1];
    if (!ticket) return null;
    if (!onedesk && guven !== 'etiketli') return null;
    let durum = null;
    const d = DURUM_ETIKETLI.exec(tum);
    if (d) durum = durumCoz(d[1].split(/\s+/).slice(0, 2).join(' ')) || durumCoz(d[1].split(/\s+/)[0]);
    if (!durum) durum = _ilkIfade(sade(konu || '')) || _ilkIfade(String(govde || ''));
    return { ticket_no: ticket, durum, guven: durum ? guven : 'tahmin', onedesk };
  }

  // ------------------------------------------------------------------ WhatsApp
  /** data-pre-plain-text: "[14:32, 30.09.2026] Ad Soyad: " → {saat, tarih, zaman, gonderen}. */
  function waOnBilgiCoz(s) {
    const m = String(s || '').match(/^\s*\[\s*(\d{1,2}[:.]\d{2})(?:\s*([AaPp][Mm]))?\s*,\s*([\d./-]{6,10})\s*\]\s*(.*?)\s*:?\s*$/);
    if (!m) return null;
    let [sa, dk] = m[1].split(/[:.]/).map(Number);
    if (m[2]) { const pm = /p/i.test(m[2]); if (pm && sa < 12) sa += 12; if (!pm && sa === 12) sa = 0; }
    const saat = String(sa).padStart(2, '0') + ':' + String(dk).padStart(2, '0');
    const zaman = tarihNormal(m[3] + ' ' + saat);
    return { saat, tarih: m[3], zaman, gonderen: sade(m[4]).replace(/:$/, '') || null };
  }

  function _cokSatirliMetin(el) {
    const ham = metin(el);
    return String(ham || '').split(/\n/).map((x) => sade(x)).filter(Boolean).join('\n');
  }

  function waSohbetAdi(doc, S) {
    const el = ilkEslesen(doc, S.whatsapp.sohbet_basligi);
    if (!el) return null;
    return sade(el.getAttribute('title') || metin(el)).slice(0, 120) || null;
  }

  /** Bir mesaj satırı ([role=row]) → {kimlik, yon, metin, gonderen, zaman, saat, sohbet}. */
  function waMesajOku(satir, doc, S) {
    const W = S.whatsapp;
    const kimlikEl = satir.matches(W.kimlik) ? satir : satir.querySelector(W.kimlik);
    const kimlik = kimlikEl ? kimlikEl.getAttribute('data-id') : null;
    const yon = kimlik ? (kimlik.startsWith('true_') ? 'giden' : kimlik.startsWith('false_') ? 'gelen' : null) : null;
    const onEl = satir.querySelector(W.on_bilgi);
    const on = onEl ? waOnBilgiCoz(onEl.getAttribute('data-pre-plain-text')) : null;
    const metinEl = ilkEslesen(onEl || satir, W.metin) || ilkEslesen(satir, W.metin);
    const govde = metinEl ? _cokSatirliMetin(metinEl) : '';
    const saatEl = satir.querySelector(W.saat);
    const saatMeta = saatEl ? (sade(metin(saatEl)).match(/\d{1,2}[:.]\d{2}/) || [null])[0] : null;
    return {
      kimlik,
      yon,
      metin: govde.slice(0, 4000),
      gonderen: on ? on.gonderen : null,
      zaman: on ? on.zaman : null,
      saat: on ? on.saat : saatMeta,
      sohbet: waSohbetAdi(doc, S),
    };
  }

  /** Mesaj metninden talep türü tahmini. */
  function talepTuruTahmin(s) {
    const t = String(s || '').toLocaleLowerCase('tr');
    if (/ek\s*kapasite|boş\s*port|bos\s*port|port\s*(yok|kalmadı|kalmadi|dolu|bitti)|\bek\s*sp\b|splitt?er|\b4004\b|kapasite\s*(yok|dolu|bitti)/.test(t)) return 'ek_kapasite';
    if (/sinyal\s*(yok|gelmiyor|zayıf|zayif|düşük|dusuk|kesik|kayb)|ışık\s*yok|isik\s*yok|\blos\b|kırmızı\s*ışık|kirmizi\s*isik|sinyalsiz/.test(t)) return 'sinyal_yok';
    return 'diger';
  }

  /** Metinden bina kimliği: Bina Serial (XX-1234567890[-12]) ya da Location Id. */
  function binaAyikla(s) {
    const t = String(s || '');
    let m = t.match(/\b([A-Za-z]{2}-\d{8,10}(?:-\d{1,3})?)\b/);
    if (m) return { deger: m[1].toUpperCase(), tur: 'bina_serial', tahmin: false };
    m = t.match(/(?:location\s*id|lokasyon\s*(?:id|no)?|loc\s*id|lok\.?\s*id)\s*[:=\-–]?\s*([A-Za-z]?\d{7,8})(?!\d)/i);
    if (m) return { deger: m[1].toUpperCase(), tur: 'location_id', tahmin: false };
    m = t.match(/\b(?:bn|bina\s*(?:no|seri\s*no|serial(?:\s*number)?))\s*[:=\-–]?\s*([A-Za-z]{2}-[\d-]{8,14}|\d{7,12})/i);
    if (m) return { deger: m[1].toUpperCase(), tur: 'bina_serial', tahmin: false };
    m = t.match(/(?<![\d+])([A-Za-z]?\d{8})(?![\d])/);
    if (m) return { deger: m[1].toUpperCase(), tur: 'location_id', tahmin: true };
    return null;
  }

  // ------------------------------------------------------------------ Atmosfer
  /** Personel sayfası → {kisiler: [{ad, unvan, bolum}], yetkili, ekip}. Sayfa yoksa null. */
  function atmosferOku(doc, S) {
    const A = S.atmosfer;
    const kok = doc.querySelector(A.kok);
    if (!kok) return null;
    const kisiler = [];
    const gorulen = new Set();
    const sayi = { yetkili: 0, ekip: 0 };
    for (const [bolum, sec] of [['yetkili', A.yetkili], ['ekip', A.ekip]]) {
      const b = kok.querySelector(sec);
      if (!b) continue;
      for (const kart of tumu(b, A.kart)) {
        const ad = sade(metin(kart.querySelector(A.ad)));
        const unvan = sade(metin(kart.querySelector(A.unvan)));
        if (!ad) continue;
        const k = anahtar(ad) + '|' + bolum;
        if (gorulen.has(k)) continue;
        gorulen.add(k);
        kisiler.push({ ad: ad.slice(0, 120), unvan: unvan ? unvan.slice(0, 120) : null, bolum });
        sayi[bolum]++;
      }
    }
    return { kisiler, yetkili: sayi.yetkili, ekip: sayi.ekip };
  }

  return {
    metin, kendiMetni, ilkEslesen, kontrolDegeri, etiketDegerleri, basliklariEsle, KONTROL,
    bossListeOku, bossDetayOku, bossSayfaTuru,
    owaMailOku, onedeskCoz, durumCoz, DURUMLAR,
    waOnBilgiCoz, waMesajOku, waSohbetAdi, talepTuruTahmin, binaAyikla,
    atmosferOku,
  };
});
