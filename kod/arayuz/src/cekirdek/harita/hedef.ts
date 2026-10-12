/**
 * Haritada "şuraya git": arama paletinden, "Location ID ile git" kutusundan ya da
 * adresten (`#/harita?loc=…`, `?loc=…`) gelen hedef.
 *
 * Birimler birbirini tanımaz; palet haritayı içe aktarmaz. Hedefi buraya bırakır,
 * sonra yalnız ROTA ile haritaya gider. Açılan harita (satış haritası ya da
 * konsoldaki HaritaTuval) hedefi alır, kamerayı uçurur, iğne + halka ile vurgular.
 * Hedef bir kez tüketilir; sayfa yenilenince kalmaz (müşteri verisi saklanmaz).
 *
 * Bu dosya deck.gl yüklemez (palet ana pakette); kamera ve katmanlar `hedefKatman.ts`te.
 */

import { useCallback, useEffect, useState } from 'react';

export interface HaritaHedefi {
  /** Aranan metin (Location ID / BN / site adı) — konum yoksa harita kendisi çözer. */
  sorgu?: string;
  serial?: string;
  loc?: string;
  lat?: number | null;
  lon?: number | null;
  etiket?: string;
}

const OLAY = 'turkcell:harita-hedef';
let bekleyen: HaritaHedefi | null = null;

/** Hedefi bırak (palet çağırır, ardından `git('/harita')`). */
export function haritaHedefiBirak(h: HaritaHedefi) {
  bekleyen = h;
  window.dispatchEvent(new CustomEvent(OLAY));
}

/** Adresteki `loc` (ya da `q`) parametresi: `#/harita?loc=…` ya da `?loc=…#/harita`. */
export function adrestekiHedef(): HaritaHedefi | null {
  try {
    const hash = window.location.hash;
    const i = hash.indexOf('?');
    const ps = [new URLSearchParams(i >= 0 ? hash.slice(i + 1) : ''), new URLSearchParams(window.location.search)];
    for (const p of ps) {
      const v = (p.get('loc') || p.get('bina') || '').trim();
      if (v) return { sorgu: v };
    }
  } catch {
    /* bozuk adres: hedef yok */
  }
  return null;
}

/** Adresteki `?loc=` tüketildi: adres sadeleşir (yenileyince yeniden uçmasın). */
function adresiTemizle() {
  try {
    const hash = window.location.hash;
    const i = hash.indexOf('?');
    if (i >= 0) window.history.replaceState(null, '', window.location.pathname + window.location.search + hash.slice(0, i));
  } catch {
    /* önemsiz */
  }
}

/**
 * Haritanın dinlediği hedef. Bileşen ilk açıldığında bekleyen hedef ya da adres
 * parametresi varsa onu döndürür; `tuket()` hedefi temizler.
 */
export function useHaritaHedefi(): [HaritaHedefi | null, () => void] {
  // Başlatıcı yan etkisizdir (StrictMode iki kez çağırabilir); tüketme etkide.
  const [hedef, setHedef] = useState<HaritaHedefi | null>(() => bekleyen ?? adrestekiHedef());
  useEffect(() => {
    bekleyen = null;
    adresiTemizle();
    const al = () => {
      if (!bekleyen) return;
      setHedef(bekleyen);
      bekleyen = null;
    };
    window.addEventListener(OLAY, al);
    window.addEventListener('hashchange', al);
    return () => {
      window.removeEventListener(OLAY, al);
      window.removeEventListener('hashchange', al);
    };
  }, []);
  const tuket = useCallback(() => setHedef(null), []);
  return [hedef, tuket];
}
