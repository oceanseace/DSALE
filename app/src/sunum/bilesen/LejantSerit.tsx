/**
 * Bölge lejantı şeridi: tüm bölgelerin kodu + kısa adı tek satırda.
 * S5'te "8 kodun hepsi 1366×768'de de görünür" şartını bu şerit garanti eder.
 */
import type { CSSProperties } from 'react';
import type { Plan } from '../../data/types';
import { boy, renk, u, yazi } from '../../ui/tema';

export interface LejantSeritProps {
  plan: Plan;
  /** vurgulanan bölge (diğerleri soluk) */
  vurgu?: number | null;
  boyut?: number;
  style?: CSSProperties;
}

export default function LejantSerit({ plan, vurgu = null, boyut = boy.kucuk, style }: LejantSeritProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexWrap: 'wrap',
        gap: `${u(10)} ${u(26)}`,
        fontFamily: yazi.govde,
        ...style,
      }}
    >
      {plan.bolgeler.map((b, i) => {
        const soluk = vurgu != null && vurgu !== b.bolge;
        return (
          <span
            key={b.bolge}
            className={`s-soluk s-g${Math.min(6, Math.floor(i / 2) + 1)}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: u(9),
              opacity: soluk ? 0.35 : 1,
              transition: 'opacity 300ms linear',
            }}
          >
            <span
              style={{
                width: u(boyut * 0.7),
                height: u(boyut * 0.7),
                borderRadius: u(5),
                background: b.renk,
                boxShadow: `0 0 ${u(14)} ${b.renk}99`,
                flex: '0 0 auto',
              }}
            />
            <span
              style={{
                fontFamily: yazi.baslik,
                fontWeight: 700,
                fontSize: u(boyut * 1.15),
                color: renk.metin,
                letterSpacing: '0.02em',
              }}
            >
              {b.kod}
            </span>
            <span style={{ fontSize: u(boyut), color: renk.metin2, whiteSpace: 'nowrap' }}>{b.kisa_ad}</span>
          </span>
        );
      })}
    </div>
  );
}
