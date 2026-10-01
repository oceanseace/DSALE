/*
 * Saha eklentisi — sayfa içi arayüz takımı (kapalı gölge DOM; sitenin CSS'i karışmaz, site betiği okuyamaz).
 *
 *   hap      sağ altta küçük hap: "Saha · 24 task · Saha'ya gönder"
 *   kart     hapın üstünde açılan onay kartı
 *   serit    üstte ince şerit (OWA)
 *   pencere  ortada küçük form penceresi (WhatsApp talep, Atmosfer önizleme)
 *   bildirim kısa, sessiz bildirim
 *
 * Bütün metinler textContent ile yazılır (innerHTML ile veri YAZILMAZ).
 */
(function () {
  'use strict';
  if (globalThis.DSKabuk) return;

  // Uçtan uca test kopyası bunu 'open' yapar (Playwright kapalı gölgeye giremez). Üretimde 'closed'.
  const GOLGE_KIPI = 'closed';

  const CSS = `
:host { all: initial; }
* { box-sizing: border-box; }
.kok {
  --zemin: #eff1f5; --kart: #ffffff; --kart-bas: #f7f8fa; --cizgi: #e2e6ed;
  --metin: #101828; --metin-2: #525c6b; --metin-3: #626b7a;
  --birincil: #0b63e5; --birincil-bas: #0a4fb8; --birincil-yazi: #0b63e5; --birincil-yumusak: #e7f0ff;
  --sari: #ffc900; --yesil: #0b7a3f; --yesil-yumusak: #e3f6ec; --amber: #94500a; --amber-yumusak: #fff2e0;
  --kirmizi: #c02a2a; --kirmizi-yumusak: #fdeaea; --bildirim-zemin: #101828; --bildirim-yazi: #ffffff;
  --golge: 0 1px 2px rgba(16,24,40,.06), 0 10px 30px rgba(16,24,40,.16);
  --perde: rgba(16,24,40,.40);
  --hareket: 180ms;
  font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
  color: var(--metin); -webkit-font-smoothing: antialiased; letter-spacing: -0.005em;
}
@media (prefers-color-scheme: dark) {
  .kok {
    --zemin: #0f1319; --kart: #181d26; --kart-bas: #1e242f; --cizgi: #2a313d;
    --metin: #eef1f6; --metin-2: #aab3c1; --metin-3: #9aa3b1;
    --birincil: #2563eb; --birincil-bas: #1d4ed8; --birincil-yazi: #7cb2ff; --birincil-yumusak: #15233d;
    --yesil: #3ecf82; --yesil-yumusak: #123024; --amber: #f0b45c; --amber-yumusak: #33260f;
    --kirmizi: #ff8a8a; --kirmizi-yumusak: #3a1a1c; --bildirim-zemin: #eef1f6; --bildirim-yazi: #101828;
    --golge: 0 1px 2px rgba(0,0,0,.5), 0 10px 30px rgba(0,0,0,.5); --perde: rgba(0,0,0,.55);
  }
}
@media (prefers-reduced-motion: reduce) { .kok { --hareket: 0ms; } }
button { font: inherit; letter-spacing: inherit; cursor: pointer; border: 0; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible { outline: 2px solid var(--birincil); outline-offset: 2px; }
.isaret { flex: none; width: 22px; height: 22px; border-radius: 6px; background: var(--birincil); color: var(--sari);
  font-weight: 800; font-size: 14px; line-height: 22px; text-align: center; }
.dugme { height: 32px; padding: 0 14px; border-radius: 9px; font-weight: 600; font-size: 13px; white-space: nowrap;
  transition: background var(--hareket), opacity var(--hareket); }
.dugme.birincil { background: var(--birincil); color: #fff; }
.dugme.birincil:hover { background: var(--birincil-bas); }
.dugme.ikincil { background: var(--birincil-yumusak); color: var(--birincil-yazi); }
.dugme.sessiz { background: transparent; color: var(--metin-2); padding: 0 10px; }
.dugme.sessiz:hover { color: var(--metin); }
.dugme[disabled] { opacity: .55; cursor: default; }
.ikon { width: 28px; height: 28px; padding: 0; border-radius: 8px; background: transparent; color: var(--metin-3); font-size: 16px; line-height: 28px; }
.ikon:hover { background: var(--kart-bas); color: var(--metin); }

.hap { position: fixed; right: 20px; bottom: 20px; display: flex; align-items: center; gap: 10px; max-width: min(560px, calc(100vw - 40px));
  padding: 8px 8px 8px 10px; background: var(--kart); border: 1px solid var(--cizgi); border-radius: 14px; box-shadow: var(--golge);
  animation: gir var(--hareket) ease-out; }
.hap .yazi { display: flex; flex-direction: column; min-width: 0; }
.hap .ana { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hap .alt { font-size: 12px; color: var(--metin-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hap .eylem { display: flex; gap: 6px; margin-left: 4px; }

.kart { position: fixed; right: 20px; bottom: 76px; width: 340px; max-width: calc(100vw - 40px); background: var(--kart);
  border: 1px solid var(--cizgi); border-radius: 16px; box-shadow: var(--golge); padding: 16px; animation: gir var(--hareket) ease-out; }
.kart h2, .pencere h2 { margin: 0 0 2px; font-size: 16px; font-weight: 650; letter-spacing: -0.01em; }
.kart .aciklama, .pencere .aciklama { margin: 0 0 12px; color: var(--metin-2); font-size: 13px; }
.satirlar { margin: 0 0 14px; padding: 0; border-top: 1px solid var(--cizgi); }
.satirlar > div { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--cizgi); }
.satirlar dt { color: var(--metin-2); margin: 0; }
.satirlar dd { margin: 0; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
.secim { display: flex; align-items: flex-start; gap: 8px; margin: 0 0 14px; color: var(--metin-2); font-size: 13px; }
.secim input { margin: 2px 0 0; accent-color: var(--birincil); }
.eylemler { display: flex; justify-content: flex-end; gap: 8px; }

.serit { position: fixed; top: 12px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 10px;
  max-width: calc(100vw - 24px); padding: 8px 8px 8px 12px; background: var(--kart); border: 1px solid var(--cizgi);
  border-radius: 14px; box-shadow: var(--golge); animation: gir var(--hareket) ease-out; }
.serit .ana { font-weight: 600; white-space: nowrap; }
.serit .alt { color: var(--metin-3); font-size: 12px; }
.serit select { height: 32px; border-radius: 9px; border: 1px solid var(--cizgi); background: var(--kart-bas); color: var(--metin); padding: 0 8px; font: inherit; }

.perde { position: fixed; inset: 0; background: var(--perde); display: flex; align-items: center; justify-content: center;
  padding: 20px; animation: sol var(--hareket) ease-out; }
.pencere { width: 440px; max-width: 100%; max-height: calc(100vh - 40px); overflow: auto; background: var(--kart);
  border-radius: 18px; box-shadow: var(--golge); padding: 20px; animation: gir var(--hareket) ease-out; }
.alan { display: block; margin: 0 0 14px; }
.alan > span { display: block; font-size: 12px; font-weight: 600; color: var(--metin-2); margin: 0 0 6px; }
.alan input, .alan textarea { width: 100%; font: inherit; color: var(--metin); background: var(--kart-bas); border: 1px solid var(--cizgi);
  border-radius: 10px; padding: 9px 11px; }
.alan textarea { min-height: 120px; resize: vertical; }
.alan small { display: block; margin-top: 5px; color: var(--metin-3); font-size: 12px; }
.bolumlu { display: flex; background: var(--kart-bas); border: 1px solid var(--cizgi); border-radius: 11px; padding: 3px; gap: 3px; }
.bolumlu label { flex: 1; text-align: center; padding: 7px 6px; border-radius: 8px; font-size: 13px; font-weight: 600; color: var(--metin-2); cursor: pointer; }
.bolumlu input { position: absolute; opacity: 0; pointer-events: none; }
.bolumlu label:has(input:checked) { background: var(--kart); color: var(--metin); box-shadow: 0 1px 2px rgba(16,24,40,.12); }
.bolumlu label:has(input:focus-visible) { outline: 2px solid var(--birincil); }
.liste { margin: 0 0 14px; padding: 0; list-style: none; border: 1px solid var(--cizgi); border-radius: 12px; overflow: hidden; }
.liste li { display: flex; justify-content: space-between; gap: 10px; padding: 9px 12px; border-top: 1px solid var(--cizgi); }
.liste li:first-child { border-top: 0; }
.liste .sayi { font-weight: 700; font-variant-numeric: tabular-nums; }
details { margin: 0 0 14px; }
summary { cursor: pointer; color: var(--birincil-yazi); font-weight: 600; font-size: 13px; }
details ul { margin: 8px 0 0; padding-left: 18px; color: var(--metin-2); font-size: 13px; max-height: 180px; overflow: auto; }
.not { padding: 10px 12px; border-radius: 10px; background: var(--amber-yumusak); color: var(--amber); font-size: 13px; margin: 0 0 14px; }
.not.iyi { background: var(--yesil-yumusak); color: var(--yesil); }

.bildirim { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); max-width: calc(100vw - 40px);
  background: var(--bildirim-zemin); color: var(--bildirim-yazi); border-radius: 12px; padding: 10px 16px; box-shadow: var(--golge);
  font-weight: 500; animation: gir var(--hareket) ease-out; }
.bildirim.hata { background: var(--kirmizi); color: #fff; }
.gizli { display: none !important; }
@keyframes gir { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; } }
.serit, .bildirim { animation-name: sol; }
@keyframes sol { from { opacity: 0; } to { opacity: 1; } }
`;

  let host = null;
  let golge = null;
  let kap = null;

  function kok() {
    if (host && host.isConnected && kap) return kap;
    host = document.createElement('ds-saha');
    host.setAttribute('style', 'all: initial !important; position: fixed !important; top: 0 !important; left: 0 !important; width: 0 !important; height: 0 !important; z-index: 2147483600 !important;');
    golge = host.attachShadow({ mode: GOLGE_KIPI });
    const stil = document.createElement('style');
    stil.textContent = CSS;
    kap = document.createElement('div');
    kap.className = 'kok';
    golge.append(stil, kap);
    (document.documentElement || document.body).appendChild(host);
    return kap;
  }

  /** Küçük öğe kurucu. props: {class, text, on:{click}, attrs...}. Çocuklar: düğüm ya da metin. */
  function el(tag, props, ...cocuklar) {
    const e = document.createElement(tag);
    const p = props || {};
    for (const [k, v] of Object.entries(p)) {
      if (v == null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else if (k === 'on') for (const [ad, f] of Object.entries(v)) e.addEventListener(ad, f);
      else if (k in e && typeof v !== 'string') e[k] = v;
      else e.setAttribute(k, v === true ? '' : String(v));
    }
    for (const c of cocuklar.flat()) {
      if (c == null || c === false) continue;
      e.append(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return e;
  }

  function dugme(t) {
    const b = el('button', { type: 'button', class: 'dugme ' + (t.tur || 'ikincil'), text: t.metin, 'aria-label': t.aria || null, 'data-ds': t.kimlik || null });
    if (t.devre) b.disabled = true;
    b.addEventListener('click', async (olay) => {
      olay.stopPropagation();
      if (b.disabled) return;
      const eski = b.textContent;
      b.disabled = true;
      if (t.mesgul) b.textContent = t.mesgul;
      try { await t.tik(olay); } finally {
        if (b.isConnected) { b.disabled = !!t.kalsin; if (t.mesgul && b.textContent === t.mesgul) b.textContent = eski; }
      }
    });
    return b;
  }

  function _isaret() { return el('span', { class: 'isaret', 'aria-hidden': 'true', text: 'S' }); }

  // ------------------------------------------------------------------ hap
  let hapEl = null;
  let hapAnahtari = '';
  function hap(t) {
    const k = kok();
    // Aynı içerik yeniden çizilmez (kullanıcı düğmeye basarken hap altından değişmesin).
    const anahtar = [t.metin, t.alt || '', (t.eylemler || []).map((e) => e.metin + ':' + (e.kimlik || '')).join(',')].join('|');
    if (hapEl && hapEl.isConnected && anahtar === hapAnahtari) return hapEl;
    hapAnahtari = anahtar;
    const yeni = el('div', { class: 'hap', role: 'status', 'data-ds': 'hap' },
      _isaret(),
      el('div', { class: 'yazi' }, el('span', { class: 'ana', text: t.metin }), t.alt ? el('span', { class: 'alt', text: t.alt }) : null),
      (t.eylemler && t.eylemler.length) ? el('div', { class: 'eylem' }, t.eylemler.map(dugme)) : null,
      t.kapat ? el('button', { type: 'button', class: 'ikon', 'aria-label': 'Gizle', text: '×', on: { click: () => { hapGizle(); t.kapat(); } } }) : null);
    if (hapEl && hapEl.isConnected) hapEl.replaceWith(yeni); else k.append(yeni);
    hapEl = yeni;
    return yeni;
  }
  function hapGizle() { if (hapEl) { hapEl.remove(); hapEl = null; hapAnahtari = ''; } kartKapat(); }

  // ------------------------------------------------------------------ kart
  let kartEl = null;
  function kart(t) {
    const k = kok();
    kartKapat();
    kartEl = el('section', { class: 'kart', role: 'dialog', 'aria-label': t.baslik, 'data-ds': 'kart' },
      el('h2', { text: t.baslik }),
      t.aciklama ? el('p', { class: 'aciklama', text: t.aciklama }) : null,
      t.govde || null,
      el('div', { class: 'eylemler' }, (t.eylemler || []).map(dugme)));
    k.append(kartEl);
    const ilk = kartEl.querySelector('button.birincil') || kartEl.querySelector('button');
    if (ilk) ilk.focus();
    return kartEl;
  }
  function kartKapat() { if (kartEl) { kartEl.remove(); kartEl = null; } }

  /** [[etiket, değer], …] → tanım listesi. */
  function satirlar(ciftler) {
    return el('dl', { class: 'satirlar' }, ciftler.filter((c) => c && c[1] != null && c[1] !== '').map(([a, b]) => el('div', null, el('dt', { text: a }), el('dd', { text: b }))));
  }

  // ------------------------------------------------------------------ şerit
  let seritEl = null;
  function serit(t) {
    const k = kok();
    const yeni = el('div', { class: 'serit', role: 'region', 'aria-label': 'Saha', 'data-ds': 'serit' },
      _isaret(),
      el('div', null, el('div', { class: 'ana', text: t.metin }), t.alt ? el('div', { class: 'alt', text: t.alt }) : null),
      t.ek || null,
      (t.eylemler || []).map(dugme),
      el('button', { type: 'button', class: 'ikon', 'aria-label': 'Kapat', text: '×', on: { click: () => { seritGizle(); if (t.kapat) t.kapat(); } } }));
    if (seritEl && seritEl.isConnected) seritEl.replaceWith(yeni); else k.append(yeni);
    seritEl = yeni;
    return yeni;
  }
  function seritGizle() { if (seritEl) { seritEl.remove(); seritEl = null; } }

  // ------------------------------------------------------------------ pencere
  let pencereKapat = null;
  function pencere(t) {
    const k = kok();
    if (pencereKapat) pencereKapat();
    const onceki = document.activeElement;
    const kutu = el('div', { class: 'pencere', role: 'dialog', 'aria-modal': 'true', 'aria-label': t.baslik, 'data-ds': 'pencere' },
      el('h2', { text: t.baslik }),
      t.aciklama ? el('p', { class: 'aciklama', text: t.aciklama }) : null,
      t.govde || null,
      el('div', { class: 'eylemler' }, (t.eylemler || []).map(dugme)));
    const perde = el('div', { class: 'perde', 'data-ds': 'perde' }, kutu);
    const tus = (e) => { if (e.key === 'Escape') { e.stopPropagation(); kapat(); } };
    perde.addEventListener('keydown', tus);
    perde.addEventListener('mousedown', (e) => { if (e.target === perde) kapat(); });
    // Sayfanın kısayolları (WhatsApp vb.) pencere içindeki yazmayı yakalamasın.
    ['keydown', 'keyup', 'keypress', 'input', 'paste'].forEach((ad) => kutu.addEventListener(ad, (e) => e.stopPropagation()));
    function kapat() {
      perde.remove();
      pencereKapat = null;
      if (t.kapaninca) t.kapaninca();
      try { if (onceki && onceki.focus) onceki.focus(); } catch (_) { /* önemsiz */ }
    }
    pencereKapat = kapat;
    k.append(perde);
    const ilk = kutu.querySelector('input:not([type=radio]), textarea, button.birincil');
    if (ilk) ilk.focus();
    return { kutu, kapat };
  }

  // ------------------------------------------------------------------ bildirim
  let bildirimZaman = null;
  function bildirim(metin, tur) {
    const k = kok();
    const eski = k.querySelector('.bildirim');
    if (eski) eski.remove();
    const b = el('div', { class: 'bildirim' + (tur === 'hata' ? ' hata' : ''), role: tur === 'hata' ? 'alert' : 'status', 'data-ds': 'bildirim', text: metin });
    k.append(b);
    clearTimeout(bildirimZaman);
    bildirimZaman = setTimeout(() => b.remove(), tur === 'hata' ? 7000 : 4000);
  }

  // ------------------------------------------------------------------ arka plan çalışanına mesaj
  function mesaj(tur, veri) {
    return new Promise((coz) => {
      try {
        chrome.runtime.sendMessage(Object.assign({}, veri || {}, { tur }), (y) => {
          const hata = chrome.runtime.lastError;
          if (hata) coz({ ok: false, hata: 'Eklenti yeniden yüklendi. Sayfayı yenileyin.', kod: 'baglam' });
          else coz(y || { ok: false, hata: 'Eklentiden yanıt gelmedi.', kod: 'yanit_yok' });
        });
      } catch (_) {
        coz({ ok: false, hata: 'Eklenti yeniden yüklendi. Sayfayı yenileyin.', kod: 'baglam' });
      }
    });
  }

  /** Kısa özet (SHA-256, onaltılık). Ham kimlik sunucuya gitmez. */
  async function ozetle(s) {
    const veri = new TextEncoder().encode(String(s));
    const h = await crypto.subtle.digest('SHA-256', veri);
    return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  /** Geciktirici: art arda çağrıları tek çağrıya indirir. */
  function geciktir(f, ms) {
    let z = null;
    return function () { clearTimeout(z); z = setTimeout(f, ms); };
  }

  globalThis.DSKabuk = { el, dugme, hap, hapGizle, kart, kartKapat, satirlar, serit, seritGizle, pencere, bildirim, mesaj, ozetle, geciktir };
})();
