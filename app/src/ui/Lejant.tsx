/**
 * Lejant — iki biçim:
 *  - `ogeler` verilirse renk kutucukları (8 bölge şeridi gibi)
 *  - `gradyan` verilirse sürekli ölçek çubuğu (fırsat / penetrasyon)
 */
import type { CSSProperties } from 'react';
import { boy, renk, u, yazi } from './tema';

export interface LejantOgesi {
  renk: string;
  etiket: string;
  /** sağda küçük ikincil metin */
  deger?: string;
  vurgu?: boolean;
}

export interface LejantProps {
  ogeler?: LejantOgesi[];
  /** hex renk durakları (düşük → yüksek) */
  gradyan?: string[];
  /** gradyan uçlarının etiketleri */
  uclar?: [string, string];
  baslik?: string;
  /** 'yatay' (şerit) | 'dikey' (liste) */
  yon?: 'yatay' | 'dikey';
  boyut?: number;
  style?: CSSProperties;
}

export default function Lejant({ ogeler, gradyan, uclar, baslik, yon = 'yatay', boyut = boy.govde, style }: LejantProps) {
  return (
    <div style={{ fontFamily: yazi.govde, ...style }}>
      {baslik && (
        <div
          style={{
            fontSize: u(boy.not),
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: renk.metin3,
            marginBottom: u(8),
          }}
        >
          {baslik}
        </div>
      )}
      {gradyan && (
        <div style={{ minWidth: u(260) }}>
          <div
            style={{
              height: u(12),
              borderRadius: u(6),
              background: `linear-gradient(90deg, ${gradyan.join(', ')})`,
              border: `1px solid ${renk.cizgi}`,
            }}
          />
          {uclar && (
            <div style={{ display: 'flex', justifyContent: 'space-between', color: renk.metin2, fontSize: u(boy.kucuk), marginTop: u(6) }}>
              <span>{uclar[0]}</span>
              <span>{uclar[1]}</span>
            </div>
          )}
        </div>
      )}
      {ogeler && (
        <div
          style={{
            display: 'flex',
            flexDirection: yon === 'yatay' ? 'row' : 'column',
            flexWrap: yon === 'yatay' ? 'wrap' : 'nowrap',
            gap: yon === 'yatay' ? u(20) : u(10),
          }}
        >
          {ogeler.map((o, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: u(10), opacity: o.vurgu === false ? 0.45 : 1 }}>
              <span
                style={{
                  width: u(boyut * 0.62),
                  height: u(boyut * 0.62),
                  borderRadius: u(5),
                  background: o.renk,
                  boxShadow: `0 0 ${u(14)} ${o.renk}88`,
                  flex: '0 0 auto',
                }}
              />
              <span style={{ fontSize: u(boyut), color: renk.metin, whiteSpace: 'nowrap' }}>{o.etiket}</span>
              {o.deger && (
                <span style={{ fontSize: u(boyut * 0.86), color: renk.metin2, fontVariantNumeric: 'tabular-nums' }}>{o.deger}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
