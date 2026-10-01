/**
 * Minik adres yönlendirici (hash tabanlı).
 *
 * Tek dosya, dış bağımlılık yok. Adres `#/bugun`, `#/bina/BN-123` biçimindedir;
 * hash kullanmamızın sebebi uygulamanın sunucu ayarı olmadan (ve `file://`
 * ile açılan derlemede) da çalışmasıdır.
 */

import { useCallback, useEffect, useState } from 'react';

function simdikiYol(): string {
  const ham = window.location.hash.replace(/^#/, '');
  return ham.startsWith('/') ? ham : '/' + ham;
}

export function useAdres() {
  const [yol, setYol] = useState(simdikiYol);

  useEffect(() => {
    const degisti = () => setYol(simdikiYol());
    window.addEventListener('hashchange', degisti);
    return () => window.removeEventListener('hashchange', degisti);
  }, []);

  return yol === '/' ? '/bugun' : yol;
}

export function git(yol: string, secenek: { degistir?: boolean } = {}) {
  const hedef = '#' + (yol.startsWith('/') ? yol : '/' + yol);
  if (secenek.degistir) {
    window.history.replaceState(null, '', hedef);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else if (window.location.hash !== hedef) {
    window.location.hash = hedef;
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
