/**
 * TASKS açılır pencereleri (süzgeç ▾, sağ tık, Sütunlar, Özel filtreler, Dolgu rengi, Bizim durum) için ortak:
 *  - kapanış: dışarı basınca, kaydırınca, pencere odağı kaybedince ya da Esc'te `kapat` (cekirdek/ortak/disariKapat.ts);
 *  - ekrana sığdırma (`useEkranaSigdir`): pencere ekranın altına/sağına taşmaz. Sabit (fixed) menü yukarı/sola
 *    kaydırılır, ekrandan uzunsa yüksekliği ekrana göre kısılır (süzgeçte yalnız değer listesi kısalır; Tamam/İptal
 *    her zaman görünür); araç çubuğundan açılan (absolute) pencerenin yüksekliği ekranın kalanına kısılır, içi kayar.
 * Giriş: `useDisariKapat(kok, kapat, acik)` · `useEkranaSigdir(kok, acik)`.
 */

import { useLayoutEffect, type RefObject } from 'react';

export { useDisariKapat } from '../../../cekirdek/ortak/disariKapat';

const KENAR = 8;

export function useEkranaSigdir(kok: RefObject<HTMLElement>, acik = true): void {
  useLayoutEffect(() => {
    const el = kok.current;
    if (!acik || !el) return undefined;
    const sigdir = () => {
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      const sabit = window.getComputedStyle(el).position === 'fixed';
      el.style.maxHeight = '';
      let r = el.getBoundingClientRect();
      if (sabit) {
        if (r.height > vh - 2 * KENAR) {
          el.style.maxHeight = `${vh - 2 * KENAR}px`;
          r = el.getBoundingClientRect();
        }
        if (r.bottom > vh - KENAR) el.style.top = `${Math.max(KENAR, vh - KENAR - r.height)}px`;
        if (r.right > vw - KENAR) el.style.left = `${Math.max(KENAR, vw - KENAR - r.width)}px`;
      } else {
        const alan = vh - r.top - KENAR;
        if (r.height > alan) el.style.maxHeight = `${Math.max(160, alan)}px`;
        el.style.transform = '';
        r = el.getBoundingClientRect();
        if (r.right > vw - KENAR) el.style.transform = `translateX(${-Math.min(r.left - KENAR, r.right - vw + KENAR)}px)`;
      }
    };
    sigdir();
    const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => sigdir()) : null;
    ro?.observe(el);
    window.addEventListener('resize', sigdir);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', sigdir);
    };
  });
}
