/*
 * Saha Sistemi — servis çalışanı.
 * Tek amacı var: uygulama sinyal yokken de aynı şekilde açılsın.
 *  - Uygulama kabuğu (html/js/css/ikon) kurulumda önbelleğe alınır.
 *  - GET /api/... yanıtları "önce ağ, olmazsa önbellek" ile saklanır.
 *  - POST /api/... asla önbelleğe alınmaz; kayıtların kuyruğu uygulamada (IndexedDB).
 *
 * İş emirleri (OPERASYON_V2_SPEC §6.9, WP-D): `/api/islerim` ve `/api/isler…`
 * GET yanıtları da "önce ağ, yoksa önbellek"tir; `/api/isler/degisim` (canlı
 * yoklama) ve `/api/isler/excel` (dosya akışı) hiç saklanmaz. Bu yanıtlar
 * müşteri bilgisi taşır: saklanırken `x-saha-zaman` damgası alır ve 24 saatten
 * eskisi GÖSTERİLMEZ (silinir). Çıkışta ve 401'de uygulama bu önbelleği
 * tümden siler (`depo/db.ts → apiOnbelleginiTemizle`).
 */

const SURUM = '__SAHA_SURUM__';
const KABUK_ONBELLEK = `saha-kabuk-${SURUM}`;
const API_ONBELLEK = `saha-api-${SURUM}`;
const KABUK = __SAHA_KABUK__;
/** İş kayıtlarının en uzun ömrü (ms): 24 saat. */
const IS_OMRU_MS = 24 * 60 * 60 * 1000;

self.addEventListener('install', (olay) => {
  olay.waitUntil(
    (async () => {
      const onbellek = await caches.open(KABUK_ONBELLEK);
      await Promise.allSettled(KABUK.map((yol) => onbellek.add(new Request(yol, { cache: 'reload' }))));
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (olay) => {
  olay.waitUntil(
    (async () => {
      const adlar = await caches.keys();
      await Promise.all(
        adlar
          .filter((ad) => ad.startsWith('saha-') && ad !== KABUK_ONBELLEK && ad !== API_ONBELLEK)
          .map((ad) => caches.delete(ad)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('message', (olay) => {
  if (olay.data && olay.data.tip === 'HEMEN_GEC') self.skipWaiting();
});

/** İş emri uçları: müşteri bilgisi taşır, 24 saat ömürlü saklanır. */
function isUcu(yol) {
  if (yol.startsWith('/api/islerim')) return true;
  if (yol === '/api/isler' || yol.startsWith('/api/isler/')) {
    return !yol.startsWith('/api/isler/degisim') && !yol.startsWith('/api/isler/excel');
  }
  return false;
}

/** GET yanıtı saklanacak mı? Sadece okunan uçlar. */
function apiSaklanir(yol) {
  return (
    yol.startsWith('/api/gorev/bugun') ||
    yol.startsWith('/api/ben') ||
    yol.startsWith('/api/harita') ||
    yol.startsWith('/api/yollar') ||
    yol.startsWith('/api/bina') ||
    isUcu(yol)
  );
}

/** Yanıtı saklama anı damgasıyla kopyalar (24 saat kuralı için). */
async function damgala(yanit) {
  const basliklar = new Headers(yanit.headers);
  basliklar.set('x-saha-zaman', String(Date.now()));
  const govde = await yanit.clone().blob();
  return new Response(govde, { status: yanit.status, statusText: yanit.statusText, headers: basliklar });
}

async function onceAg(istek, onbellekAdi, zamanAsimiMs, omurMs) {
  const onbellek = await caches.open(onbellekAdi);
  try {
    const denetleyici = new AbortController();
    const sayac = setTimeout(() => denetleyici.abort(), zamanAsimiMs);
    const yanit = await fetch(istek, { signal: denetleyici.signal });
    clearTimeout(sayac);
    if (yanit && yanit.ok) {
      if (omurMs) onbellek.put(istek, await damgala(yanit));
      else onbellek.put(istek, yanit.clone());
    }
    return yanit;
  } catch {
    const saklanan = await onbellek.match(istek);
    if (saklanan && omurMs) {
      const zaman = Number(saklanan.headers.get('x-saha-zaman') || 0);
      if (!zaman || Date.now() - zaman > omurMs) {
        // 24 saatten eski müşteri bilgisi gösterilmez: silinir.
        await onbellek.delete(istek);
        throw new Error('ag-yok');
      }
    }
    if (saklanan) return saklanan;
    throw new Error('ag-yok');
  }
}

self.addEventListener('fetch', (olay) => {
  const istek = olay.request;
  if (istek.method !== 'GET') return; // POST/PUT doğrudan ağa gider.

  const adres = new URL(istek.url);
  if (adres.origin !== self.location.origin) return;

  // Sayfa gezinmeleri: kabuk önbellekten anında açılır, arka planda tazelenir.
  if (istek.mode === 'navigate') {
    olay.respondWith(
      (async () => {
        const onbellek = await caches.open(KABUK_ONBELLEK);
        const saklanan = await onbellek.match('/index.html');
        const agdan = fetch(istek)
          .then((yanit) => {
            if (yanit && yanit.ok) onbellek.put('/index.html', yanit.clone());
            return yanit;
          })
          .catch(() => null);
        return saklanan || (await agdan) || new Response('Çevrimdışı', { status: 503 });
      })(),
    );
    return;
  }

  if (adres.pathname.startsWith('/api/')) {
    if (!apiSaklanir(adres.pathname)) return;
    olay.respondWith(
      onceAg(istek, API_ONBELLEK, 8000, isUcu(adres.pathname) ? IS_OMRU_MS : 0).catch(
        () =>
          new Response(JSON.stringify({ hata: 'Bağlantı yok', kod: 'ag_yok' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    );
    return;
  }

  // Parmak izli dosyalar: önce önbellek.
  olay.respondWith(
    (async () => {
      const onbellek = await caches.open(KABUK_ONBELLEK);
      const saklanan = await onbellek.match(istek);
      if (saklanan) return saklanan;
      try {
        const yanit = await fetch(istek);
        if (yanit && yanit.ok && adres.pathname.startsWith('/varlik/')) onbellek.put(istek, yanit.clone());
        return yanit;
      } catch {
        return new Response('', { status: 504 });
      }
    })(),
  );
});

// Arka plan senkronu destekleniyorsa uygulamayı dürt.
self.addEventListener('sync', (olay) => {
  if (olay.tag !== 'saha-kuyruk') return;
  olay.waitUntil(
    (async () => {
      const istemciler = await self.clients.matchAll({ includeUncontrolled: true, type: 'window' });
      istemciler.forEach((istemci) => istemci.postMessage({ tip: 'KUYRUGU_GONDER' }));
    })(),
  );
});
