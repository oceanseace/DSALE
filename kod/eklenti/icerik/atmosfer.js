/*
 * Saha eklentisi — Atmosfer personel listesi → Saha personel rehberi (G9).
 *
 * `dealer-manager/employee` sayfasında kartlar görünür olunca sağ altta "Rehbere aktar" çıkar.
 * Basınca ad + unvan çiftleri (+ yetkili / ekip bölümü) sunucuya ÖNİZLEME için gider; kullanıcı sayıları
 * görür, "Uygula"ya basarsa aynı liste uygulanır. Atmosfer jetonu okunmaz, Atmosfer API'si çağrılmaz.
 */
(function () {
  'use strict';
  if (globalThis.__dsAtmosfer) return;
  globalThis.__dsAtmosfer = true;

  const A = globalThis.DSAyristir, K = globalThis.DSKabuk;
  let S = globalThis.DSSecici.al();
  let durum = { eslesmis: false, kapsamlar: [] };
  let ilkGorulme = 0;

  async function durumYenile() {
    const r = await K.mesaj('durum');
    if (r && r.ok) { durum = r; S = globalThis.DSSecici.al(r.secici_ek || null); }
  }

  function listeOgesi(etiket, sayi, kimlik) {
    return K.el('li', { 'data-ds': kimlik }, K.el('span', { text: etiket }), K.el('span', { class: 'sayi', text: String(sayi) }));
  }

  function ayrinti(baslik, kisiler, bicim) {
    if (!kisiler || !kisiler.length) return null;
    return K.el('details', null, K.el('summary', { text: baslik + ' (' + kisiler.length + ')' }),
      K.el('ul', null, kisiler.slice(0, 200).map((k) => K.el('li', { text: bicim(k) }))));
  }

  async function onizle() {
    const okunan = A.atmosferOku(document, S);
    if (!okunan || !okunan.kisiler.length) { K.bildirim('Çalışan kartı bulunamadı.', 'hata'); return; }
    const r = await K.mesaj('rehber.gonder', { kisiler: okunan.kisiler, uygula: false });
    if (!r.ok) { K.bildirim(r.hata || 'Önizleme alınamadı.', 'hata'); return; }
    const v = r.veri || {};
    const say = v.sayilar || {};
    const degisiklik = (say.eklenecek || 0) + (say.guncellenecek || 0);
    const govde = K.el('div', null,
      K.el('ul', { class: 'liste' },
        listeOgesi('Yeni kişi eklenecek', say.eklenecek || 0, 'eklenecek'),
        listeOgesi('Unvanı güncellenecek', say.guncellenecek || 0, 'guncellenecek'),
        listeOgesi('Zaten güncel', say.ayni || 0, 'ayni'),
        listeOgesi('Alınmayacak (göreve eşlenmeyen unvan)', say.atlanacak || 0, 'atlanacak')),
      ayrinti('Eklenecekler', v.eklenecek, (k) => k.ad + (k.unvan ? ' — ' + k.unvan : '')),
      ayrinti('Güncellenecekler', v.guncellenecek, (k) => k.ad + ': ' + (k.unvan_eski || '—') + ' → ' + k.unvan),
      ayrinti('Alınmayacaklar', v.atlanacak, (k) => k.ad + (k.unvan ? ' — ' + k.unvan : '')),
      degisiklik ? K.el('p', { class: 'not iyi', text: 'Eklenen kişiler girişsiz açılır (telefon yok, BOSS Mobil). Görevleri unvandan gelir.' })
        : K.el('p', { class: 'not iyi', text: 'Saha rehberi bu listeyle aynı. Yapılacak bir şey yok.' }));
    const p = K.pencere({
      baslik: 'Rehbere aktar',
      aciklama: okunan.kisiler.length + ' çalışan okundu (' + okunan.yetkili + ' yetkili, ' + okunan.ekip + ' ekip).',
      govde,
      eylemler: [
        { metin: degisiklik ? 'Vazgeç' : 'Kapat', tur: 'sessiz', tik: () => p.kapat() },
        degisiklik ? { metin: 'Uygula', tur: 'birincil', kimlik: 'rehber-uygula', mesgul: 'Uygulanıyor…', tik: async () => {
          const u = await K.mesaj('rehber.gonder', { kisiler: okunan.kisiler, uygula: true });
          if (u.ok) {
            const s = (u.veri && u.veri.sayilar) || {};
            p.kapat();
            K.bildirim('Rehber güncellendi · ' + (s.eklenecek || 0) + ' eklendi, ' + (s.guncellenecek || 0) + ' güncellendi.');
          } else K.bildirim(u.hata || 'Uygulanamadı.', 'hata');
        } } : null,
      ].filter(Boolean),
    });
  }

  function tara() {
    if (document.visibilityState !== 'visible') return;
    const sayfada = location.pathname.includes(S.atmosfer.yol_parcasi) || document.querySelector(S.atmosfer.kok);
    if (!sayfada) { K.hapGizle(); ilkGorulme = 0; return; }
    if (!ilkGorulme) { ilkGorulme = Date.now(); setTimeout(tara, S.atmosfer.bekleme_ms + 100); }
    const okunan = A.atmosferOku(document, S);
    const n = okunan ? okunan.kisiler.length : 0;
    if (!n) {
      if (Date.now() - ilkGorulme >= S.atmosfer.bekleme_ms) K.hap({ metin: 'Saha · Çalışan listesi bulunamadı', alt: '"Çalışanlar" düğmesine basıp listeyi açın' });
      else K.hapGizle();
      return;
    }
    if (!durum.eslesmis) { K.hap({ metin: 'Saha · ' + n + ' çalışan', alt: 'Eklenti bağlı değil — Saha simgesine tıklayıp bağlanın' }); return; }
    if (!(durum.kapsamlar || []).includes('rehber')) { K.hap({ metin: 'Saha · ' + n + ' çalışan', alt: 'Rehber aktarımı yöneticiye açık' }); return; }
    K.hap({ metin: 'Saha · ' + n + ' çalışan', alt: 'Personel rehberine aktarılabilir',
      eylemler: [{ metin: 'Rehbere aktar', tur: 'birincil', kimlik: 'rehber-aktar', mesgul: 'Okunuyor…', tik: onizle }] });
  }

  const geciktirilmis = K.geciktir(tara, 700);
  new MutationObserver(geciktirilmis).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener('visibilitychange', geciktirilmis);
  window.addEventListener('popstate', geciktirilmis);

  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (msg && sender.id === chrome.runtime.id && !sender.tab && msg.tur === 'durum.degisti') durumYenile().then(tara);
    return false;
  });

  durumYenile().then(tara);
})();
