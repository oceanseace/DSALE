/*
 * Saha eklentisi — BOSS teknik task ekranları (B4 / C14 / F17 okuma, G1 / G3 doldurma).
 *
 * OKUMA: yalnız kullanıcının AÇTIĞI ve GÖRÜNEN sekmedeki liste/detay. Liste için task no, durum, ekip, lokasyon,
 *        randevu (müşteri sütunları hiç okunmaz). "Canlı eşitleme" açıksa bu alanlar değiştikçe gönderilir.
 *        Müşteri telefonu YALNIZ detayda, kullanıcı "Saha'ya gönder"e basıp onay kartında gördükten sonra.
 * DOLDURMA: panelden "Formu doldur" gelince ekip / randevu alanlarına yazar. Kaydet'e ASLA basmaz.
 */
(function () {
  'use strict';
  if (globalThis.__dsBoss) return;
  globalThis.__dsBoss = true;

  const M = globalThis.DSMetin, A = globalThis.DSAyristir, D = globalThis.DSDoldur, K = globalThis.DSKabuk;
  let S = globalThis.DSSecici.al();
  let durum = { eslesmis: false, kapsamlar: [], canli: true };
  let sonImza = '';
  let sonGonderim = 0;
  let sonSonuc = '';
  let baglam = { gorunum: null, task_no: null, sayi: 0 };
  let kartAcik = false;
  const ASGARI_ARALIK_MS = 15000;

  const kapsam = (k) => (durum.kapsamlar || []).includes(k);

  async function durumYenile() {
    const r = await K.mesaj('durum');
    if (r && r.ok) {
      durum = r;
      S = globalThis.DSSecici.al(r.secici_ek || null);
    }
  }

  function saat() {
    const d = new Date();
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  }

  function baglamBildir(yeni) {
    const degisti = yeni.gorunum !== baglam.gorunum || yeni.task_no !== baglam.task_no || yeni.sayi !== baglam.sayi;
    baglam = yeni;
    if (degisti) K.mesaj('boss.baglam', { baglam: yeni });
  }

  async function gonder(gorunum, tasklar, ek, otomatik) {
    const r = await K.mesaj('boss.gonder', Object.assign({ gorunum, tasklar, otomatik: !!otomatik, sayfa: location.pathname }, ek || {}));
    if (r.ok) {
      sonGonderim = Date.now();
      const v = r.veri || {};
      sonSonuc = "Saha'ya işlendi · " + saat() + (v.guncellenen ? ' · ' + v.guncellenen + ' değişiklik' : '');
    } else if (!otomatik) {
      K.bildirim(r.hata || 'Gönderilemedi.', 'hata');
    } else if (r.kod === 'eslesme_bitti' || r.kod === 'eslesme_yok') {
      durum.eslesmis = false;
    }
    return r;
  }

  function panelDugmesi() {
    return { metin: 'Panel', tur: 'sessiz', aria: 'Saha panelini aç', kimlik: 'panel', tik: async () => {
      const r = await K.mesaj('panel.ac');
      if (!r.ok) K.bildirim(r.hata || 'Paneli açmak için tarayıcı çubuğundaki Saha simgesine tıklayın.');
    } };
  }

  // ------------------------------------------------------------------ liste
  function listeIsle() {
    const sonuc = A.bossListeOku(document, S);
    baglamBildir({ gorunum: 'liste', task_no: null, sayi: sonuc.tasklar.length });
    if (kartAcik) return;
    if (!sonuc.tablo) {
      K.hap({ metin: 'Saha · Bu liste tanınmadı', alt: 'Yöneticiye haber verin: eklenti simgesi → Yapı keşfi' });
      return;
    }
    if (!durum.eslesmis) {
      K.hap({ metin: 'Saha · ' + sonuc.tasklar.length + ' task görünüyor', alt: 'Eklenti bağlı değil — Saha simgesine tıklayıp bağlanın' });
      return;
    }
    const canli = durum.canli && kapsam('boss.oku');
    K.hap({
      metin: 'Saha · ' + sonuc.tasklar.length + ' task görünüyor',
      alt: sonSonuc || (canli ? 'Canlı eşitleme açık' : 'Canlı eşitleme kapalı'),
      eylemler: kapsam('boss.oku') ? [{ metin: "Saha'ya gönder", tur: 'birincil', kimlik: 'liste-gonder', mesgul: 'Gönderiliyor…', tik: async () => {
        const r = await gonder('liste', A.bossListeOku(document, S).tasklar, null, false);
        if (r.ok) { K.bildirim(sonuc.tasklar.length + " task Saha'ya işlendi."); tara(); }
      } }] : [],
    });
    if (canli && sonuc.tasklar.length) canliGonder('liste', sonuc.tasklar);
  }

  /** Canlı eşitleme: yalnız değişince, en sık 15 sn'de bir; aralık dolmadıysa sonda bir kez daha dener. */
  let canliZaman = null;
  function canliGonder(gorunum, tasklar) {
    const imza = gorunum + JSON.stringify(tasklar);
    if (imza === sonImza) return;
    const bekle = ASGARI_ARALIK_MS - (Date.now() - sonGonderim);
    if (bekle > 0) {
      clearTimeout(canliZaman);
      canliZaman = setTimeout(tara, bekle + 250);
      return;
    }
    sonImza = imza;
    sonGonderim = Date.now();
    gonder(gorunum, tasklar, null, true).then((r) => {
      if (!r.ok) sonImza = '';          // ağ yoksa sonraki aralıkta yeniden denenir
      if (!kartAcik) tara();
    });
  }

  // ------------------------------------------------------------------ detay
  function detayIsle() {
    const d = A.bossDetayOku(document, location, S, { telefon: false });
    baglamBildir({ gorunum: 'detay', task_no: d.task_no || null, sayi: d.task_no ? 1 : 0 });
    if (kartAcik) return;
    if (!d.task_no) {
      K.hap({ metin: 'Saha · Task numarası bulunamadı', alt: 'Yöneticiye haber verin: eklenti simgesi → Yapı keşfi' });
      return;
    }
    if (!durum.eslesmis) {
      K.hap({ metin: 'Saha · Task ' + d.task_no, alt: 'Eklenti bağlı değil — Saha simgesine tıklayıp bağlanın' });
      return;
    }
    const eylemler = [];
    if (kapsam('boss.oku')) eylemler.push({ metin: "Saha'ya gönder", tur: 'birincil', kimlik: 'detay-gonder', tik: () => onayKarti() });
    if (kapsam('boss.giden')) eylemler.push(panelDugmesi());
    K.hap({ metin: 'Saha · Task ' + d.task_no, alt: sonSonuc || (d.durum ? d.durum : 'BOSS task detayı'), eylemler });
    // Canlı eşitleme: müşteri bilgisi OLMADAN (task no, durum, ekip, randevu).
    if (durum.canli && kapsam('boss.oku')) {
      const temiz = Object.assign({}, d);
      delete temiz.telefon;
      delete temiz.musteri_tel;
      canliGonder('detay', [temiz]);
    }
  }

  function onayKarti() {
    const d = A.bossDetayOku(document, location, S, { telefon: kapsam('boss.tel') });
    const tel = d.musteri_tel || null;
    const telMetni = {
      bulundu: M.telefonMaskeli(tel),
      etiket_yok: 'Ekranda bulunamadı',
      maskeli: 'Ekranda gizli (önce BOSS’ta görünür yapın)',
      gecersiz: 'Okunamadı',
      okunmadi: null,
    }[d.telefon];
    let telGonder = !!tel;
    const govde = K.el('div', null,
      K.satirlar([
        ['Task No', d.task_no],
        ['Durum', d.durum],
        ['Ekip', d.ekip],
        ['Randevu', d.randevu_baslangic ? M.tarihKisa(d.randevu_baslangic) + (d.randevu_bitis ? ' – ' + M.saatKisa(d.randevu_bitis) : '') : null],
        kapsam('boss.tel') ? ['Müşteri telefonu', telMetni] : null,
      ]),
      tel ? K.el('label', { class: 'secim' },
        K.el('input', { type: 'checkbox', checked: true, 'data-ds': 'tel-onay', on: { change: (e) => { telGonder = e.target.checked; } } }),
        K.el('span', { text: "Müşteri telefonunu da Saha'ya gönder (yalnız bu task için, teknik ekip araması için)." })) : null);
    kartAcik = true;
    K.kart({
      baslik: "Saha'ya gönder",
      aciklama: 'Bu task’ın bilgileri Saha’daki işle eşleştirilir.',
      govde,
      eylemler: [
        { metin: 'Vazgeç', tur: 'sessiz', tik: () => { kartAcik = false; K.kartKapat(); tara(); } },
        { metin: 'Gönder', tur: 'birincil', kimlik: 'kart-gonder', mesgul: 'Gönderiliyor…', tik: async () => {
          const temiz = Object.assign({}, d);
          delete temiz.telefon;
          delete temiz.musteri_tel;
          const ek = tel && telGonder ? { musteri_tel: tel, kullanici_onayi: true } : null;
          const r = await gonder('detay', [temiz], ek, false);
          if (r.ok) {
            kartAcik = false;
            K.kartKapat();
            const v = r.veri || {};
            K.bildirim(v.eslesmeyen ? "Task Saha'da bulunamadı; bilgisi not edildi." : "Task Saha'ya işlendi" + (ek ? ' (telefon dahil).' : '.'));
            tara();
          }
        } },
      ],
    });
  }

  // ------------------------------------------------------------------ tarama
  function tara() {
    if (document.visibilityState !== 'visible') return;
    const tur = A.bossSayfaTuru(location, document, S);
    if (!tur) {
      K.hapGizle();
      baglamBildir({ gorunum: null, task_no: null, sayi: 0 });
      return;
    }
    if (tur === 'liste') listeIsle(); else detayIsle();
  }

  const geciktirilmis = K.geciktir(tara, 1200);
  let sonAdres = location.href;

  new MutationObserver(() => {
    if (location.href !== sonAdres) { sonAdres = location.href; sonImza = ''; kartAcik = false; K.kartKapat(); }
    geciktirilmis();
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  document.addEventListener('visibilitychange', geciktirilmis);
  window.addEventListener('hashchange', geciktirilmis);
  window.addEventListener('popstate', geciktirilmis);

  // ------------------------------------------------------------------ panelden gelenler
  chrome.runtime.onMessage.addListener((msg, sender, yanit) => {
    if (!msg || sender.id !== chrome.runtime.id || sender.tab) return false;
    if (msg.tur === 'boss.oku') {
      const tur = A.bossSayfaTuru(location, document, S);
      if (tur === 'detay') {
        const d = A.bossDetayOku(document, location, S, { telefon: false });
        yanit({ ok: true, gorunum: 'detay', task_no: d.task_no || null, durum: d.durum || null, ekip: d.ekip || null, sayi: d.task_no ? 1 : 0 });
      } else if (tur === 'liste') {
        const l = A.bossListeOku(document, S);
        yanit({ ok: true, gorunum: 'liste', task_no: null, sayi: l.tasklar.length, tablo: l.tablo, son: sonSonuc });
      } else yanit({ ok: true, gorunum: null });
      return false;
    }
    if (msg.tur === 'boss.doldur') {
      const rapor = D.doldur(document, msg.alanlar || {}, S);
      const o = D.ozet(rapor);
      if (o.toplam) {
        K.serit({
          metin: o.elle ? 'Alanların bir kısmı dolduruldu' : 'Alanlar dolduruldu',
          alt: 'Kontrol edin, sonra BOSS’ta Kaydet’e siz basın.',
        });
        setTimeout(K.seritGizle, 9000);
      }
      yanit({ ok: true, rapor });
      return false;
    }
    if (msg.tur === 'durum.degisti') {
      durumYenile().then(tara);
      return false;
    }
    return false;
  });

  durumYenile().then(tara);
})();
