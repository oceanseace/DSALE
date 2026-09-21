/**
 * Marka imzası: sarı işaret + "Dehanet EÇM" (meta.organizasyon_kisa) ve isteğe bağlı alt satır.
 * Her sahnenin sol üstünde aynı yerde durur — sunum boyunca sabit çapa.
 */
import type { CSSProperties } from 'react';
import { veri } from '../data/load';
import { boy, renk, u, yazi } from './tema';

export interface MarkaProps {
  /** alt satır, ör. tarih ya da meta.hitap */
  alt?: string;
  boyut?: number;
  /** işaret (sarı kare) gösterilsin mi */
  isaret?: boolean;
  style?: CSSProperties;
}

export default function Marka({ alt, boyut = boy.govde, isaret = true, style }: MarkaProps) {
  const m = veri().meta;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: u(14), ...style }}>
      {isaret && (
        <span
          style={{
            width: u(boyut * 0.75),
            height: u(boyut * 0.75),
            borderRadius: u(6),
            background: renk.sari,
            boxShadow: `0 0 ${u(20)} ${renk.sari}77`,
            flex: '0 0 auto',
          }}
        />
      )}
      <span>
        <span
          style={{
            display: 'block',
            fontFamily: yazi.baslik,
            fontWeight: 700,
            fontSize: u(boyut),
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: renk.metin,
            lineHeight: 1.05,
          }}
        >
          {m.organizasyon_kisa}
        </span>
        {alt && (
          <span style={{ display: 'block', fontFamily: yazi.govde, fontSize: u(boyut * 0.66), color: renk.metin3 }}>{alt}</span>
        )}
      </span>
    </div>
  );
}
