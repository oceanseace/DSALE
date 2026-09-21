/**
 * URL parametreleri — test edilebilirlik sözleşmesinin adres tarafı.
 *
 *   ?mod=sunum|kesif   hangi mod açılır (varsayılan sunum)
 *   ?sahne=1..10       sunum sahnesi (1 tabanlı)
 *   ?adim=1..k         sahne içi adım (1 tabanlı; S6 bölge turu)
 *   ?film=1            otomatik oynatma
 *   ?n=2..50           plan (bölge sayısı)
 *
 * file:// üzerinde de çalışır (Chromium sorgu dizesini korur).
 * Keşif kendi ek parametrelerini (?bolge ?ara ?bina ?gorunum ?renk ?katman) `ham` üzerinden okur.
 */

export type Mod = 'sunum' | 'kesif';

export interface UrlParametreleri {
  mod: Mod;
  /** 1 tabanlı sahne; yoksa null */
  sahne: number | null;
  /** 1 tabanlı adım; yoksa null */
  adim: number | null;
  film: boolean;
  /** plan N; yoksa null */
  n: number | null;
  /** ham arama parametreleri (mod'a özel ek okumalar için) */
  ham: URLSearchParams;
}

function parametreler(): URLSearchParams {
  if (typeof window === 'undefined') return new URLSearchParams();
  // file:// + hash yönlendirmesi: "?" hash'in içinde de olabilir
  const s = new URLSearchParams(window.location.search);
  const h = window.location.hash;
  const i = h.indexOf('?');
  if (i >= 0) for (const [k, v] of new URLSearchParams(h.slice(i + 1))) if (!s.has(k)) s.set(k, v);
  return s;
}

/** Tam sayı parametre; geçersizse null. */
export function urlSayi(ad: string, p = parametreler()): number | null {
  const v = p.get(ad);
  if (v == null || v === '') return null;
  const x = Number(v);
  return Number.isFinite(x) ? Math.trunc(x) : null;
}

/** Bayrak parametre: ?film, ?film=1, ?film=true → true; ?film=0 → false. */
export function urlBayrak(ad: string, p = parametreler()): boolean {
  if (!p.has(ad)) return false;
  const v = (p.get(ad) ?? '').toLowerCase();
  return v !== '0' && v !== 'false' && v !== 'hayir';
}

/** Adresteki tüm sözleşme parametrelerini okur. */
export function urlOku(): UrlParametreleri {
  const p = parametreler();
  const mod = (p.get('mod') ?? '').toLowerCase();
  return {
    mod: mod === 'kesif' || mod === 'keşif' ? 'kesif' : 'sunum',
    sahne: urlSayi('sahne', p),
    adim: urlSayi('adim', p),
    film: urlBayrak('film', p),
    n: urlSayi('n', p),
    ham: p,
  };
}

/**
 * Adres çubuğunu sessizce günceller (geçmişe kayıt eklemez).
 * null/undefined verilen anahtar adresten silinir.
 */
export function urlYaz(degerler: Record<string, string | number | boolean | null | undefined>): void {
  if (typeof window === 'undefined' || !window.history?.replaceState) return;
  const p = parametreler();
  for (const [k, v] of Object.entries(degerler)) {
    if (v == null || v === false || v === '') p.delete(k);
    else p.set(k, v === true ? '1' : String(v));
  }
  const q = p.toString();
  const yeni = window.location.pathname + (q ? '?' + q : '') + (window.location.hash.split('?')[0] || '');
  try {
    window.history.replaceState(null, '', yeni);
  } catch {
    /* file:// bazı tarayıcılarda replaceState'i reddeder — sorun değil */
  }
}
