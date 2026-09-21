/**
 * S4 "nasıl böldük" adım şeridi: dört kural, dört ikon. Etkin adım sarıya döner.
 * Metin yerine ikon kullanılır — beş saniyede okunmalı.
 */
import type { CSSProperties, ReactNode } from 'react';
import { boy, renk, u, yazi } from '../../ui/tema';

export interface AdimOgesi {
  ikon: ReactNode;
  metin: string;
}

const CIZGI = { fill: 'none', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

/** 1 — her bina tek tek */
export const IkonBina = (
  <svg viewBox="0 0 32 32" width="100%" height="100%" aria-hidden>
    <g stroke="currentColor" {...CIZGI}>
      <rect x="4" y="12" width="9" height="16" rx="1" />
      <rect x="17" y="5" width="11" height="23" rx="1" />
      <path d="M7 16h3M7 20h3M7 24h3M20 9h5M20 14h5M20 19h5M20 24h5" />
    </g>
  </svg>
);

/** 2 — siteler bölünmez */
export const IkonKilit = (
  <svg viewBox="0 0 32 32" width="100%" height="100%" aria-hidden>
    <g stroke="currentColor" {...CIZGI}>
      <rect x="7" y="14" width="18" height="13" rx="2.5" />
      <path d="M11 14v-4a5 5 0 0 1 10 0v4" />
      <circle cx="16" cy="20.5" r="1.8" />
    </g>
  </svg>
);

/** 3 — hane yükü eşit */
export const IkonTerazi = (
  <svg viewBox="0 0 32 32" width="100%" height="100%" aria-hidden>
    <g stroke="currentColor" {...CIZGI}>
      <path d="M16 6v21M9 27h14M6 11h20M16 8.5 6 11l-3 7a5 5 0 0 0 10 0Zm0 0 10 2.5 3 7a5 5 0 0 1-10 0Z" />
    </g>
  </svg>
);

/** 4 — rota kısa */
export const IkonRota = (
  <svg viewBox="0 0 32 32" width="100%" height="100%" aria-hidden>
    <g stroke="currentColor" {...CIZGI}>
      <circle cx="8" cy="8" r="3.2" />
      <circle cx="24" cy="24" r="3.2" />
      <path d="M8 11.5v6.5a4 4 0 0 0 4 4h8" strokeDasharray="3 3" />
    </g>
  </svg>
);

export interface AdimIkonlariProps {
  ogeler: AdimOgesi[];
  /** 0 tabanlı etkin adım */
  etkin: number;
  style?: CSSProperties;
}

export default function AdimIkonlari({ ogeler, etkin, style }: AdimIkonlariProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: u(44), ...style }}>
      {ogeler.map((o, i) => {
        const aktif = i <= etkin;
        const simdi = i === etkin;
        return (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: u(14),
              opacity: aktif ? 1 : 0.34,
              transition: 'opacity 400ms linear',
            }}
          >
            <span
              style={{
                width: u(52),
                height: u(52),
                borderRadius: u(14),
                border: `1px solid ${simdi ? renk.sari : renk.cizgi}`,
                background: simdi ? 'rgba(255,196,0,0.14)' : 'rgba(255,255,255,0.05)',
                boxShadow: simdi ? `0 0 ${u(26)} ${renk.sari}55` : undefined,
                color: simdi ? renk.sari : renk.metin2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: u(10),
                flex: '0 0 auto',
                transition: 'all 400ms linear',
              }}
            >
              {o.ikon}
            </span>
            <span
              style={{
                fontFamily: yazi.govde,
                fontSize: u(boy.govde),
                color: simdi ? renk.metin : renk.metin2,
                whiteSpace: 'nowrap',
              }}
            >
              {o.metin}
            </span>
          </div>
        );
      })}
    </div>
  );
}
