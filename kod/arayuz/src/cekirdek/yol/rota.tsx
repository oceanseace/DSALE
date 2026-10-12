/**
 * Minik adres yönlendirici (hash tabanlı).
 *
 * Tek dosya, dış bağımlılık yok. Adres `#/bugun`, `#/bina/BN-123` biçimindedir;
 * hash kullanmamızın sebebi uygulamanın sunucu ayarı olmadan (ve `file://`
 * ile açılan derlemede) da çalışmasıdır.
 */

import { useCallback, useEffect, useState } from 'react';
import { flushSync } from 'react-dom';

/*
 * Sayfa geçişi: View Transitions API ile çapraz geçiş (stil/temel.css
 * ::view-transition-*). git() adresi startViewTransition içinde değiştirir;
 * hashchange dinleyicisi bekleyen geçiş varken React'i flushSync ile EŞZAMANLI
 * çizer ki tarayıcı yeni görünümü yakalasın. API yoksa ya da kullanıcı hareket
 * istemiyorsa düz geçiş olur. Geçiş en geç 400 ms'de kendiliğinden biter.
 */
type GecisBelgesi = Document & {
  startViewTransition?: (guncelle: () => Promise<void> | void) => unknown;
};
let gecisBitir: (() => void) | null = null;

function gecisOlsunMu(): boolean {
  const belge = document as GecisBelgesi;
  if (typeof belge.startViewTransition !== 'function') return false;
  if (document.visibilityState !== 'visible') return false;
  try {
    return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return true;
  }
}

function gecisle(degistir: () => void) {
  if (!gecisOlsunMu() || gecisBitir) {
    degistir();
    return;
  }
  (document as GecisBelgesi).startViewTransition?.(
    () =>
      new Promise<void>((bitti) => {
        const zaman = window.setTimeout(() => {
          gecisBitir = null;
          bitti();
        }, 400);
        gecisBitir = () => {
          window.clearTimeout(zaman);
          gecisBitir = null;
          bitti();
        };
        degistir();
      }),
  );
}

function simdikiYol(): string {
  const ham = window.location.hash.replace(/^#/, '');
  return ham.startsWith('/') ? ham : '/' + ham;
}

export function useAdres() {
  const [yol, setYol] = useState(simdikiYol);

  useEffect(() => {
    const degisti = () => {
      const yeni = simdikiYol();
      if (gecisBitir) {
        const bitir = gecisBitir;
        flushSync(() => setYol(yeni));
        // Aynı olaydaki öbür dinleyiciler de (onlar da flushSync ile) çizsin;
        // yeni görünüm bir sonraki karede yakalanır.
        requestAnimationFrame(() => {
          if (gecisBitir === bitir) bitir();
        });
      } else {
        setYol(yeni);
      }
    };
    window.addEventListener('hashchange', degisti);
    return () => window.removeEventListener('hashchange', degisti);
  }, []);

  return yol === '/' ? '/bugun' : yol;
}

export function git(yol: string, secenek: { degistir?: boolean } = {}) {
  const hedef = '#' + (yol.startsWith('/') ? yol : '/' + yol);
  if (secenek.degistir) {
    gecisle(() => {
      window.history.replaceState(null, '', hedef);
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
  } else if (window.location.hash !== hedef) {
    gecisle(() => {
      window.location.hash = hedef;
    });
  }
}

export function useGeri(yedekYol = '/bugun') {
  return useCallback(() => {
    if (window.history.length > 1) window.history.back();
    else git(yedekYol, { degistir: true });
  }, [yedekYol]);
}

/**
 * Adres boş mu (`#`, `#/` ya da hiç)? Uygulama o zaman kişinin ANA EKRANINA
 * gider (satış Bugün, teknik İşlerim, operasyon/yönetici İşler); `useAdres`
 * satış tarafı için boş adresi yine `/bugun` sayar.
 */
export function bosAdresMi(): boolean {
  const ham = window.location.hash.replace(/^#/, '');
  return ham === '' || ham === '/';
}

/** `/bina/BN-123` → `{ ekran: 'bina', deger: 'BN-123' }` */
export function yoluCoz(yol: string): { ekran: string; deger: string | null } {
  const parcalar = yol.split('/').filter(Boolean);
  return { ekran: parcalar[0] ?? 'bugun', deger: parcalar[1] ? decodeURIComponent(parcalar[1]) : null };
}
