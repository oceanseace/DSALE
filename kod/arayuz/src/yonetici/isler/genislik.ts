/**
 * Kırılım (§7.4): telefon < 768 · orta 768–1199 · geniş ≥ 1200 (üç bölme).
 * CSS aynı sınırları kullanır; bu kanca yalnız YAPI değişen yerler içindir
 * (telefonda itmeli gezinme, genişte öbek sütunu).
 */

import { useEffect, useState } from 'react';

export type Genislik = 'telefon' | 'orta' | 'genis';

function olc(): Genislik {
  try {
    if (window.matchMedia('(max-width: 767px)').matches) return 'telefon';
    if (window.matchMedia('(min-width: 1200px)').matches) return 'genis';
  } catch {
    /* matchMedia yoksa geniş say */
  }
  return typeof window !== 'undefined' && window.innerWidth < 768 ? 'telefon' : 'orta';
}

export function useGenislik(): Genislik {
  const [g, setG] = useState<Genislik>(olc);
  useEffect(() => {
    const d = () => setG(olc());
    window.addEventListener('resize', d);
    return () => window.removeEventListener('resize', d);
  }, []);
  return g;
}

/** Fare/klavye cihazı mı (tuş ipuçları yalnız orada). */
export function klavyeCihazi(): boolean {
  try {
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  } catch {
    return true;
  }
}
