/**
 * Sayı sayacı — 0'dan hedefe akar. Türkçe biçimlendirme `bicim` ile verilir (varsayılan `sayi`).
 * Genişlik sabit tutulur (`tabular-nums` + en uzun metnin yer tutucusu), böylece sayarken
 * satır kaymaz. 65 yaşındaki izleyici için: 5 saniyede okunacak, titremeyecek.
 */
import { useEffect, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { sayi } from '../data/selectors';

export interface CountUpProps {
  /** hedef değer */
  deger: number;
  /** ms (varsayılan 1400) */
  sure?: number;
  /** ms gecikme */
  gecikme?: number;
  /** sayı → metin (varsayılan Türkçe tam sayı) */
  bicim?: (x: number) => string;
  /** false ise anında hedef değer yazılır (film dışı / indirgenmiş hareket) */
  animasyon?: boolean;
  onek?: string;
  sonek?: string;
  style?: CSSProperties;
  className?: string;
}

function yumusat(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export default function CountUp({
  deger,
  sure = 1400,
  gecikme = 0,
  bicim = (x) => sayi(x),
  animasyon = true,
  onek = '',
  sonek = '',
  style,
  className,
}: CountUpProps) {
  const [v, setV] = useState(animasyon ? 0 : deger);
  const rafRef = useRef(0);

  useEffect(() => {
    if (!animasyon || sure <= 0) {
      setV(deger);
      return;
    }
    const azalt = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (azalt) {
      setV(deger);
      return;
    }
    let bas = 0;
    const kare = (simdi: number) => {
      if (!bas) bas = simdi;
      const t = (simdi - bas - gecikme) / sure;
      if (t < 0) {
        rafRef.current = requestAnimationFrame(kare);
        return;
      }
      if (t >= 1) {
        setV(deger);
        return;
      }
      setV(deger * yumusat(t));
      rafRef.current = requestAnimationFrame(kare);
    };
    setV(0);
    rafRef.current = requestAnimationFrame(kare);
    return () => cancelAnimationFrame(rafRef.current);
  }, [deger, sure, gecikme, animasyon]);

  // yer tutucu: hedef değerin metni, görünmez — kutu genişliği sabit kalır
  const hedefMetin = onek + bicim(deger) + sonek;
  return (
    <span className={className} style={{ display: 'inline-grid', fontVariantNumeric: 'tabular-nums', ...style }}>
      <span style={{ gridArea: '1 / 1', visibility: 'hidden' }} aria-hidden>
        {hedefMetin}
      </span>
      <span style={{ gridArea: '1 / 1' }}>{onek + bicim(v) + sonek}</span>
    </span>
  );
}
