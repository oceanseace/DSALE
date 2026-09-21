/**
 * Kahraman rakam: büyük sayı + üst etiket + alt açıklama.
 * Sunum sahnelerinde "tek büyük sayı" kuralı için. Sayı `CountUp` ile akar.
 */
import type { CSSProperties, ReactNode } from 'react';
import CountUp from './CountUp';
import { boy, renk, u, yazi } from './tema';

export interface BuyukRakamProps {
  /** sayısal değer (animasyonlu) ya da hazır metin */
  deger: number | string;
  bicim?: (x: number) => string;
  /** üstte küçük etiket, ör. "RES HANE" */
  etiket?: ReactNode;
  /** altta açıklama, ör. "10 haneden 9'u bizi bekliyor" */
  alt?: ReactNode;
  /** rakam boyutu (tasarım px) */
  boyut?: number;
  renkKodu?: string;
  animasyon?: boolean;
  gecikme?: number;
  hizala?: 'left' | 'center' | 'right';
  style?: CSSProperties;
}

export default function BuyukRakam({
  deger,
  bicim,
  etiket,
  alt,
  boyut = boy.dev,
  renkKodu = renk.metin,
  animasyon = true,
  gecikme = 0,
  hizala = 'left',
  style,
}: BuyukRakamProps) {
  return (
    <div style={{ textAlign: hizala, ...style }}>
      {etiket != null && (
        <div
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            color: renk.metin3,
            marginBottom: u(8),
          }}
        >
          {etiket}
        </div>
      )}
      <div
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(boyut),
          lineHeight: 0.95,
          color: renkKodu,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {typeof deger === 'number' ? <CountUp deger={deger} bicim={bicim} animasyon={animasyon} gecikme={gecikme} /> : deger}
      </div>
      {alt != null && (
        <div style={{ fontFamily: yazi.govde, fontSize: u(boy.govde), color: renk.metin2, marginTop: u(10) }}>{alt}</div>
      )}
    </div>
  );
}
