/**
 * Sahne saatleri.
 *
 *  - Katmanlar HaritaSahnesi'nin rAF saatini kullanır (60 Hz, React dışında).
 *    `adimSaati()` küresel saati adım girişine göre sıfırlar.
 *  - HTML katmanı 10 Hz'lik yavaş saatle çalışır (`useYavasSaat`); React ağacını
 *    saniyede 60 kez yeniden çizmenin anlamı yok.
 */
import { useEffect, useRef, useState } from 'react';

export interface AdimSaati {
  /** küresel t (sn) → adım girişinden beri geçen saniye */
  (anahtar: string, kureselT: number): number;
}

/** Adım anahtarı değişince sıfırlanan saat üreticisi (ref üzerinde tutulur). */
export function adimSaatiOlustur(): AdimSaati {
  let anahtarSon = '';
  let t0 = 0;
  return (anahtar: string, kureselT: number) => {
    if (anahtar !== anahtarSon) {
      anahtarSon = anahtar;
      t0 = kureselT;
    }
    return Math.max(0, kureselT - t0);
  };
}

/**
 * HTML katmanı için yavaş saat: `anahtar` değişince sıfırlanır, `aktif` false ise durur.
 * `bitisSn` verilirse o saniyeden sonra saat durur (boşuna render olmasın).
 */
export function useYavasSaat(aktif: boolean, anahtar: string, bitisSn = Infinity, araMs = 100): number {
  const [t, setT] = useState(0);
  const bitisRef = useRef(bitisSn);
  bitisRef.current = bitisSn;

  useEffect(() => {
    setT(0);
    if (!aktif) return;
    const bas = performance.now();
    const sayac = setInterval(() => {
      const gecen = (performance.now() - bas) / 1000;
      setT(gecen);
      if (gecen >= bitisRef.current) clearInterval(sayac);
    }, araMs);
    return () => clearInterval(sayac);
  }, [aktif, anahtar, araMs]);

  return t;
}
