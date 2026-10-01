/*
 * Saha eklentisi — WhatsApp Web "Talep olarak kaydet" (C12).
 *
 * Açık sohbetteki mesaj balonlarının yanına, üzerine gelince görünen küçük bir "+ Talep" düğmesi eklenir.
 * Basınca küçük bir form açılır (tür, bina / Location Id, not — mesaj metniyle dolu); "Kaydet" sunucuya gönderir.
 * WhatsApp'ta hiçbir şey yazılmaz / gönderilmez; yazma kutusuna dokunulmaz. Ham mesaj kimliği (içinde telefon
 * numarası vardır) sunucuya gitmez: yalnız SHA-256 özeti (çift kaydı önlemek için).
 */
(function () {
  'use strict';
  if (globalThis.__dsWhatsapp) return;
  globalThis.__dsWhatsapp = true;

  const M = globalThis.DSMetin, A = globalThis.DSAyristir, K = globalThis.DSKabuk;
  let S = globalThis.DSSecici.al();
  let durum = { eslesmis: false, kapsamlar: [] };
  const kaydedilen = new Map(); // mesaj özeti → talep no (yalnız bu sekmenin belleğinde)

  const TURLER = [['sinyal_yok', 'Sinyal yok'], ['ek_kapasite', 'Ek kapasite'], ['diger', 'Diğer']];

  async function durumYenile() {
    const r = await K.mesaj('durum');
    if (r && r.ok) { durum = r; S = globalThis.DSSecici.al(r.secici_ek || null); }
  }

  function aktifMi() { return durum.eslesmis && (durum.kapsamlar || []).includes('talep'); }

  function formAc(satir) {
    const mesaj = A.waMesajOku(satir, document, S);
    const bina = A.binaAyikla(mesaj.metin);
    const secim = { tur: A.talepTuruTahmin(mesaj.metin) };
    const kimden = [mesaj.gonderen || (mesaj.yon === 'giden' ? 'Siz' : null), mesaj.sohbet && mesaj.sohbet !== mesaj.gonderen ? mesaj.sohbet : null]
      .filter(Boolean).join(' · ');
    const zaman = mesaj.zaman ? M.tarihKisa(mesaj.zaman) : (mesaj.saat || '');

    const turlar = K.el('div', { class: 'bolumlu', role: 'radiogroup', 'aria-label': 'Talep türü' },
      TURLER.map(([deger, ad]) => K.el('label', null,
        K.el('input', { type: 'radio', name: 'ds-tur', value: deger, checked: deger === secim.tur, 'data-ds': 'tur-' + deger,
          on: { change: () => { secim.tur = deger; } } }),
        ad)));
    const binaGirdi = K.el('input', { type: 'text', value: bina ? bina.deger : '', maxlength: '40', autocomplete: 'off', spellcheck: 'false',
      placeholder: 'ör. BU-1234567890 ya da 12345678', 'data-ds': 'bina' });
    const notGirdi = K.el('textarea', { maxlength: '2000', 'data-ds': 'not' });
    notGirdi.value = mesaj.metin || '';

    const govde = K.el('div', null,
      K.el('div', { class: 'alan' }, K.el('span', { text: 'Tür' }), turlar),
      K.el('label', { class: 'alan' }, K.el('span', { text: 'Bina / Location Id' }), binaGirdi,
        K.el('small', { text: bina ? (bina.tahmin ? 'Mesajdaki numaradan tahmin edildi — kontrol edin.' : 'Mesajdan bulundu.') : 'Mesajda bulunamadı. Biliyorsanız yazın.' })),
      K.el('label', { class: 'alan' }, K.el('span', { text: 'Not' }), notGirdi,
        K.el('small', { text: 'Mesaj metniyle dolduruldu. Gereksiz kısmı silebilirsiniz.' })));

    const p = K.pencere({
      baslik: 'Talep olarak kaydet',
      aciklama: [kimden, zaman].filter(Boolean).join(' · ') || 'WhatsApp mesajı',
      govde,
      eylemler: [
        { metin: 'Vazgeç', tur: 'sessiz', tik: () => p.kapat() },
        { metin: 'Kaydet', tur: 'birincil', kimlik: 'talep-kaydet', mesgul: 'Kaydediliyor…', tik: async () => {
          if (!aktifMi()) { K.bildirim('Eklenti bağlı değil ya da bu işlem görevinize kapalı.', 'hata'); return; }
          const not = M.sade(notGirdi.value) ? notGirdi.value.trim() : '';
          if (!not && !M.sade(binaGirdi.value)) { K.bildirim('Not ya da bina yazın.', 'hata'); return; }
          const ozet = mesaj.kimlik ? await K.ozetle(mesaj.kimlik) : null;
          const r = await K.mesaj('talep.gonder', {
            talep: {
              tur: secim.tur,
              bina: M.sade(binaGirdi.value).toUpperCase() || null,
              not,
              mesaj_ozeti: ozet,
              sohbet: mesaj.sohbet,
              gonderen: mesaj.gonderen,
              mesaj_zamani: mesaj.zaman,
              yon: mesaj.yon,
            },
          });
          if (r.ok || r.kod === 'zaten_var') {
            const no = (r.veri && (r.veri.talep_id || r.veri.id)) || (r.veri && r.veri.detail && r.veri.detail.talep_id) || null;
            if (ozet) kaydedilen.set(ozet, no || true);
            p.kapat();
            K.bildirim(r.ok ? 'Talep kaydedildi' + (no ? ' (#' + no + ')' : '') + '.' : (r.hata || 'Bu mesaj zaten talep olarak kayıtlı.'));
            isaretle(satir, true);
          } else {
            K.bildirim(r.hata || 'Kaydedilemedi.', 'hata');
          }
        } },
      ],
    });
  }

  function isaretle(satir, kayitli) {
    const b = satir.querySelector('.ds-talep-dugme');
    if (!b) return;
    b.textContent = kayitli ? '✓ Talep' : '+ Talep';
    b.classList.toggle('ds-kayitli', !!kayitli);
    b.title = kayitli ? 'Talep olarak kaydedildi' : 'Talep olarak kaydet';
  }

  function dugmeEkle(satir) {
    const balon = A.ilkEslesen(satir, S.whatsapp.balon);
    if (!balon || balon.querySelector('.ds-talep-dugme')) return;
    const kimlikEl = satir.matches(S.whatsapp.kimlik) ? satir : satir.querySelector(S.whatsapp.kimlik);
    const kimlik = kimlikEl ? kimlikEl.getAttribute('data-id') || '' : '';
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'ds-talep-dugme' + (kimlik.startsWith('true_') ? ' ds-giden' : '');
    b.textContent = '+ Talep';
    b.title = 'Talep olarak kaydet';
    b.setAttribute('aria-label', 'Talep olarak kaydet');
    b.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!durum.eslesmis) { K.bildirim('Eklenti bağlı değil. Saha simgesine tıklayıp bağlanın.', 'hata'); return; }
      formAc(satir);
    });
    balon.appendChild(b);
    if (kimlik) K.ozetle(kimlik).then((o) => { if (kaydedilen.has(o)) isaretle(satir, true); });
  }

  function isle() {
    if (!aktifMi()) { document.querySelectorAll('.ds-talep-dugme').forEach((b) => b.remove()); return; }
    const panel = document.querySelector(S.whatsapp.sohbet_paneli);
    if (!panel) return;
    const liste = A.ilkEslesen(panel, S.whatsapp.mesaj_listesi) || panel;
    for (const satir of liste.querySelectorAll(S.whatsapp.mesaj_satiri)) {
      if (!satir.querySelector(S.whatsapp.kimlik) && !satir.matches(S.whatsapp.kimlik)) continue;
      dugmeEkle(satir);
    }
  }

  const geciktirilmis = K.geciktir(isle, 400);
  new MutationObserver(geciktirilmis).observe(document.documentElement, { childList: true, subtree: true });

  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (msg && sender.id === chrome.runtime.id && !sender.tab && msg.tur === 'durum.degisti') durumYenile().then(isle);
    return false;
  });

  durumYenile().then(isle);
})();
