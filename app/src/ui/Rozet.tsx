/**
 * Rozet (chip) — nötr cam zemin, isteğe bağlı renk noktası.
 *
 * Kural: durum renkleri (yeşil/kırmızı) ZEMİN olarak kullanılmaz; yalnız yazı ve ikon rengidir.
 * Bölge renkleri zaten 8 canlı ton taşır, üstüne renkli dolgu eklemek mesajı bulandırır.
 */
import type { CSSProperties, ReactNode } from 'react';
import { isaretliYuzde } from '../data/selectors';
import { boy, durumIsareti, renk, u, yazi } from './tema';

export interface RozetProps {
  children: ReactNode;
  /** sol tarafta renk noktası (ör. bölge rengi) */
  nokta?: string;
  /** yazı rengi */
  renkKodu?: string;
  boyut?: number;
  style?: CSSProperties;
}

export default function Rozet({ children, nokta, renkKodu = renk.metin, boyut = boy.kucuk, style }: RozetProps) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: u(8),
        padding: `${u(boyut * 0.22)} ${u(boyut * 0.55)}`,
        borderRadius: u(999),
        background: 'rgba(255,255,255,0.06)',
        border: `1px solid ${renk.cizgi}`,
        fontFamily: yazi.govde,
        fontSize: u(boyut),
        color: renkKodu,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {nokta && (
        <span
          style={{
            width: u(boyut * 0.5),
            height: u(boyut * 0.5),
            borderRadius: '50%',
            background: nokta,
            boxShadow: `0 0 ${u(12)} ${nokta}aa`,
            flex: '0 0 auto',
          }}
        />
      )}
      {children}
    </span>
  );
}

export interface DurumRozetiProps {
  /** sapma oranı (0..1, işaretli) */
  sapma: number;
  /** "dengede" sayılan eşik (varsayılan %1) */
  esik?: number;
  boyut?: number;
  /** yüzdeyi de yaz (varsayılan evet) */
  yuzdeyiGoster?: boolean;
  style?: CSSProperties;
}

/** Sapma göstergesi: ✓ / ▲ / ▼ + nötr yazı. Dolgu rengi kullanmaz. */
export function DurumRozeti({ sapma, esik = 0.01, boyut = boy.kucuk, yuzdeyiGoster = true, style }: DurumRozetiProps) {
  const d = durumIsareti(sapma, esik);
  return (
    <Rozet boyut={boyut} renkKodu={d.renk} style={style}>
      <span style={{ fontSize: u(boyut * 0.95) }}>{d.ikon}</span>
      {yuzdeyiGoster && <span style={{ fontVariantNumeric: 'tabular-nums' }}>{isaretliYuzde(sapma)}</span>}
    </Rozet>
  );
}
