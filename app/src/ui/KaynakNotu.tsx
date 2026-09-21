/**
 * Kaynak/atıf notu — ekranın en altında, küçük ve sönük.
 * OSM lisansı (ODbL) gereği altlık atfı her görünümde bulunmalıdır.
 */
import type { CSSProperties } from 'react';
import { veri } from '../data/load';
import { boy, renk, u, yazi } from './tema';

export interface KaynakNotuProps {
  /** ek metin (ör. "Veri: 2026-09 · OneMap") */
  ek?: string;
  /** altlık atfı gösterilsin mi (varsayılan evet) */
  altlik?: boolean;
  style?: CSSProperties;
}

export default function KaynakNotu({ ek, altlik = true, style }: KaynakNotuProps) {
  const v = veri();
  const parcalar: string[] = [];
  if (ek) parcalar.push(ek);
  if (altlik) parcalar.push(v.altlik.attribution || '© OpenStreetMap katkıcıları');
  return (
    <div
      style={{
        fontFamily: yazi.govde,
        fontSize: u(boy.not),
        color: renk.metin3,
        letterSpacing: '0.02em',
        opacity: 0.8,
        ...style,
      }}
    >
      {parcalar.join(' · ')}
    </div>
  );
}
