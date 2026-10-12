/**
 * Açılır menü / süzgeç paneli kapanışı (TEK yer): menünün DIŞINA basılınca (yakalama evresinde: tablo hücresi
 * olayı durdursa bile), sayfa kaydırılınca (menünün kendi içi hariç), pencere odağı kaybedince ya da boyutu
 * değişince, Esc'te (`esc` açıksa; yalnız menüyü kapatır, arkadaki çekmece açık kalır) `kapat`.
 * Giriş: `useDisariKapat(kok, kapat, acik)` ya da efekt içinde `disariDinle(...)` (temizleme işlevi döner).
 */

import { useEffect, useRef, type RefObject } from 'react';

export interface DisariSecenek {
  /** Esc de kapatsın (varsayılan açık). */
  esc?: boolean;
  /** Menüye ait sayılan başka öğeler (ör. menüyü açan düğme: ona basmak kapatıp yeniden açmasın). */
  icinde?: Array<RefObject<HTMLElement>>;
}

export function disariDinle(kok: RefObject<HTMLElement>, kapat: () => void, secenek: DisariSecenek = {}): () => void {
  const icindeMi = (h: EventTarget | null) => {
    const n = h as Node | null;
    if (!n) return false;
    if (kok.current?.contains(n)) return true;
    return (secenek.icinde ?? []).some((r) => r.current?.contains(n));
  };
  const bas = (o: Event) => {
    if (!icindeMi(o.target)) kapat();
  };
  const kaydir = (o: Event) => {
    if (o.target === document || !icindeMi(o.target)) kapat();
  };
  const odak = () => kapat();
  const esc = (o: KeyboardEvent) => {
    if (o.key !== 'Escape') return;
    o.stopImmediatePropagation();
    o.preventDefault();
    kapat();
  };
  // açan tıklamanın kendisi menüyü hemen kapatmasın: dinleyiciler bir sonraki görevde kurulur
  let kuruldu = false;
  const t = window.setTimeout(() => {
    kuruldu = true;
    window.addEventListener('pointerdown', bas, true);
    window.addEventListener('scroll', kaydir, true);
    window.addEventListener('blur', odak);
    window.addEventListener('resize', odak);
  }, 0);
  if (secenek.esc !== false) window.addEventListener('keydown', esc, true);
  return () => {
    window.clearTimeout(t);
    if (kuruldu) {
      window.removeEventListener('pointerdown', bas, true);
      window.removeEventListener('scroll', kaydir, true);
      window.removeEventListener('blur', odak);
      window.removeEventListener('resize', odak);
    }
    window.removeEventListener('keydown', esc, true);
  };
}

export function useDisariKapat(
  kok: RefObject<HTMLElement>,
  kapat: () => void,
  acik = true,
  secenek: DisariSecenek = {},
): void {
  const kapatRef = useRef(kapat);
  kapatRef.current = kapat;
  const esc = secenek.esc !== false;
  const icinde = secenek.icinde;
  useEffect(() => {
    if (!acik) return undefined;
    return disariDinle(kok, () => kapatRef.current(), { esc, icinde });
    // icinde: çağıranın sabit ref dizisi
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kok, acik, esc]);
}
