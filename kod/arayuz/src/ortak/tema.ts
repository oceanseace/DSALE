/**
 * Görünüm: Sistem · Açık · Koyu (OPERASYON_V2_SPEC §7.1).
 *
 * Seçim cihazda hatırlanır ve `<html data-theme>` ile uygulanır; "Sistem"de
 * öznitelik kaldırılır ve renkleri telefonun/bilgisayarın tercihi belirler
 * (temel.css'teki iki koyu blok). `index.html` aynı anahtarı ilk boyamadan
 * ÖNCE okur; böylece koyu seçen kişi açılışta beyaz bir parlama görmez.
 * Tarayıcıya özgü bir şey yok: masaüstü kabuğunda (EK-11) da aynı çalışır.
 */

import { useCallback, useEffect, useState } from 'react';
import { yerelOku, yerelYaz } from './yerel';

export type Gorunum = 'sistem' | 'acik' | 'koyu';

export const GORUNUM_ANAHTARI = 'saha.gorunum';
export const GORUNUM_ETIKET: Record<Gorunum, string> = { sistem: 'Sistem', acik: 'Açık', koyu: 'Koyu' };

/** Tarayıcı çubuğunun rengi (index.html'deki iki meta ile aynı). */
const CUBUK = { acik: '#EFF1F5', koyu: '#0F1319' };

const dinleyiciler = new Set<(g: Gorunum) => void>();

export function gorunumOku(): Gorunum {
  const ham = yerelOku(GORUNUM_ANAHTARI);
  return ham === 'acik' || ham === 'koyu' ? ham : 'sistem';
}

function sistemKoyuMu(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return false;
  }
}

/** Şu an ekranda koyu renkler mi var? (harita altlığı gibi renk seçenler için) */
export function koyuMu(g: Gorunum = gorunumOku()): boolean {
  return g === 'koyu' || (g === 'sistem' && sistemKoyuMu());
}

export function gorunumUygula(g: Gorunum): void {
  const kok = document.documentElement;
  if (g === 'sistem') kok.removeAttribute('data-theme');
  else kok.setAttribute('data-theme', g === 'koyu' ? 'dark' : 'light');
  // Tarayıcı çubuğu: "Sistem"de media sorgulu iki meta kendi işini yapar;
  // elle seçimde ikisi de seçilen renge çekilir.
  const renk = koyuMu(g) ? CUBUK.koyu : CUBUK.acik;
  document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]').forEach((m) => {
    if (g === 'sistem') {
      const koyuMeta = (m.getAttribute('media') ?? '').includes('dark');
      m.content = koyuMeta ? CUBUK.koyu : CUBUK.acik;
    } else {
      m.content = renk;
    }
  });
}

export function gorunumYaz(g: Gorunum): void {
  yerelYaz(GORUNUM_ANAHTARI, g === 'sistem' ? null : g);
  gorunumUygula(g);
  dinleyiciler.forEach((d) => d(g));
}

/* Modül yüklenir yüklenmez uygula: `tema-erken.js` bir nedenle gelmediyse
   (çevrimdışı ilk açılış) arayüz yine doğru renkte çizilir. */
try {
  if (typeof document !== 'undefined') gorunumUygula(gorunumOku());
} catch {
  /* belge yoksa (test) geç */
}

/** Görünüm seçimi + o an koyu mu (sistem değişince de güncellenir). */
export function useGorunum(): { gorunum: Gorunum; koyu: boolean; degistir: (g: Gorunum) => void } {
  const [gorunum, setGorunum] = useState<Gorunum>(gorunumOku);
  const [koyu, setKoyu] = useState(() => koyuMu(gorunumOku()));

  useEffect(() => {
    const d = (g: Gorunum) => {
      setGorunum(g);
      setKoyu(koyuMu(g));
    };
    dinleyiciler.add(d);
    let sorgu: MediaQueryList | null = null;
    const sistemDegisti = () => setKoyu(koyuMu(gorunumOku()));
    try {
      sorgu = window.matchMedia('(prefers-color-scheme: dark)');
      sorgu.addEventListener('change', sistemDegisti);
    } catch {
      sorgu = null;
    }
    return () => {
      dinleyiciler.delete(d);
      sorgu?.removeEventListener('change', sistemDegisti);
    };
  }, []);

  const degistir = useCallback((g: Gorunum) => gorunumYaz(g), []);
  return { gorunum, koyu, degistir };
}
