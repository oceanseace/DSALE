/**
 * TASKS tablosunda Excel tuşlarının götürdüğü hücre (saf hesap, çizim yok):
 * oklar (Ctrl ile kenara), Tab / Shift+Tab (satır sonunda alt satıra sarar), Home / End,
 * Ctrl+Home / Ctrl+End, PgUp / PgDn. Giriş: `tusHedefi(...)` → yeni {r, c} ya da null (tuş gezinme değil).
 * Kim: Tablo.tsx.
 */

export interface Konum {
  r: number;
  c: number;
}

export function tusHedefi(
  tus: string,
  ctrl: boolean,
  shift: boolean,
  e: Konum,
  satirSayisi: number,
  sutunSayisi: number,
  sayfa: number,
): Konum | null {
  const sonR = satirSayisi - 1;
  const sonC = sutunSayisi - 1;
  switch (tus) {
    case 'ArrowDown':
      return { r: ctrl ? sonR : Math.min(sonR, e.r + 1), c: e.c };
    case 'ArrowUp':
      return { r: ctrl ? 0 : Math.max(0, e.r - 1), c: e.c };
    case 'ArrowRight':
      return { r: e.r, c: ctrl ? sonC : Math.min(sonC, e.c + 1) };
    case 'ArrowLeft':
      return { r: e.r, c: ctrl ? 0 : Math.max(0, e.c - 1) };
    case 'Tab':
      if (shift) return e.c > 0 ? { r: e.r, c: e.c - 1 } : e.r > 0 ? { r: e.r - 1, c: sonC } : null;
      return e.c < sonC ? { r: e.r, c: e.c + 1 } : e.r < sonR ? { r: e.r + 1, c: 0 } : null;
    case 'Home':
      return ctrl ? { r: 0, c: 0 } : { r: e.r, c: 0 };
    case 'End':
      return ctrl ? { r: sonR, c: sonC } : { r: e.r, c: sonC };
    case 'PageDown':
      return { r: Math.min(sonR, e.r + sayfa), c: e.c };
    case 'PageUp':
      return { r: Math.max(0, e.r - sayfa), c: e.c };
    default:
      return null;
  }
}
