/*
 * Saha eklentisi — OWA (mail.turkcell.com.tr/owa) OneDesk bildirim mailleri (C11).
 *
 * Açık mail OneDesk bildirimi gibi görünüyorsa üstte küçük bir şerit çıkar:
 *   "OneDesk 10131790029 · [ÇÖZÜLDÜ ▾] · Ticket durumunu Saha'ya işle"
 * Kullanıcı basmadan hiçbir şey gönderilmez. Sunucuya yalnız ticket no + durum gider; mail gövdesi GİTMEZ.
 * Seçiciler tutmazsa sağ tık → "Seçili metni Saha'ya işle" aynı şeridi açar (seçiciye bağlı olmayan yol).
 */
(function () {
  'use strict';
  if (globalThis.__dsOwa) return;
  globalThis.__dsOwa = true;

  const A = globalThis.DSAyristir, K = globalThis.DSKabuk;
  let S = globalThis.DSSecici.al();
  let durum = { eslesmis: false, kapsamlar: [] };
  let sonImza = '';
  let kapatilan = '';

  async function durumYenile() {
    const r = await K.mesaj('durum');
    if (r && r.ok) { durum = r; S = globalThis.DSSecici.al(r.secici_ek || null); }
  }

  function seritGoster(sonuc, kaynak) {
    const secilen = { durum: sonuc.durum || '' };
    const sec = K.el('select', { 'aria-label': 'Yeni durum', 'data-ds': 'durum-sec', on: { change: (e) => { secilen.durum = e.target.value; gonderDugmesi(); } } },
      K.el('option', { value: '', text: 'Durum seçin' }),
      A.DURUMLAR.map((d) => K.el('option', { value: d, text: d, selected: d === sonuc.durum })));
    function gonderDugmesi() {
      K.serit({
        metin: 'OneDesk ' + sonuc.ticket_no,
        alt: kaynak === 'secim' ? 'Seçili metinden okundu' : (sonuc.guven === 'etiketli' ? 'Mailden okundu' : 'Mailden tahmin edildi — kontrol edin'),
        ek: sec,
        eylemler: [{
          metin: "Ticket durumunu Saha'ya işle", tur: 'birincil', kimlik: 'ticket-gonder', mesgul: 'İşleniyor…', devre: !secilen.durum,
          tik: async () => {
            if (!durum.eslesmis) { K.bildirim('Eklenti bağlı değil. Saha simgesine tıklayıp bağlanın.', 'hata'); return; }
            const r = await K.mesaj('ticket.gonder', { ticket_no: sonuc.ticket_no, durum: secilen.durum, guven: sonuc.guven, kaynak: kaynak === 'secim' ? 'owa_secim' : 'owa' });
            if (r.ok) {
              const v = r.veri || {};
              K.seritGizle();
              kapatilan = sonuc.ticket_no + secilen.durum;
              K.bildirim(v.degismedi ? 'Saha’da zaten ' + secilen.durum + '.' : 'Saha’da güncellendi: ' + sonuc.ticket_no + ' → ' + secilen.durum);
            } else {
              K.bildirim(r.hata || 'İşlenemedi.', 'hata');
            }
          },
        }],
        kapat: () => { kapatilan = sonuc.ticket_no + (sonuc.durum || ''); },
      });
      // select her çizimde yeniden eklenir; seçim korunur
      sec.value = secilen.durum;
    }
    gonderDugmesi();
  }

  function tara() {
    if (document.visibilityState !== 'visible') return;
    if (!durum.kapsamlar || !durum.kapsamlar.includes('ticket')) { if (durum.eslesmis) K.seritGizle(); return; }
    const mail = A.owaMailOku(document, S);
    if (!mail) { if (sonImza) { sonImza = ''; K.seritGizle(); } return; }
    const imza = mail.konu + '|' + mail.govde.slice(0, 400);
    if (imza === sonImza) return;
    sonImza = imza;
    const sonuc = A.onedeskCoz(mail.konu, mail.govde, S);
    if (!sonuc || kapatilan === sonuc.ticket_no + (sonuc.durum || '')) { K.seritGizle(); return; }
    seritGoster(sonuc, 'mail');
  }

  const geciktirilmis = K.geciktir(tara, 800);
  new MutationObserver(geciktirilmis).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  document.addEventListener('visibilitychange', geciktirilmis);
  window.addEventListener('hashchange', geciktirilmis);

  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (!msg || sender.id !== chrome.runtime.id || sender.tab) return false;
    if (msg.tur === 'owa.secim') {
      const sonuc = A.onedeskCoz('', String(msg.metin || '').slice(0, 20000), S) ||
        A.onedeskCoz('OneDesk', String(msg.metin || '').slice(0, 20000), S);
      if (sonuc) seritGoster(sonuc, 'secim');
      else K.bildirim('Seçili metinde ticket numarası bulunamadı.', 'hata');
    } else if (msg.tur === 'durum.degisti') {
      durumYenile().then(() => { sonImza = ''; tara(); });
    }
    return false;
  });

  durumYenile().then(tara);
})();
