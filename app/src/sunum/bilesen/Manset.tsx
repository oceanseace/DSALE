/**
 * Manşet bloğu: küçük üstlük + en fazla 6 kelimelik başlık + tek kahraman rakam + alt satır.
 * "Minimum açıklama, maksimum görsel" — bir sahnede yalnız bir tane bulunur.
 */
import type { CSSProperties, ReactNode } from 'react';
import { boy, renk, u, yazi } from '../../ui/tema';

export interface MansetProps {
  /** üstte küçük, harf aralıklı etiket (ör. "BUGÜN") */
  ustluk?: ReactNode;
  baslik: ReactNode;
  /** kahraman rakam satırı (BuyukRakam ya da serbest içerik) */
  rakam?: ReactNode;
  /** altta tek cümlelik açıklama */
  alt?: ReactNode;
  /** başlık boyutu (tasarım px) */
  baslikBoyu?: number;
  hizala?: 'left' | 'center';
  genislik?: number;
  style?: CSSProperties;
}

export default function Manset({
  ustluk,
  baslik,
  rakam,
  alt,
  baslikBoyu = boy.baslik,
  hizala = 'left',
  genislik,
  style,
}: MansetProps) {
  return (
    <div
      style={{
        textAlign: hizala,
        maxWidth: genislik != null ? u(genislik) : undefined,
        ...style,
      }}
    >
      {ustluk != null && (
        <div
          className="s-gir s-g1"
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            color: renk.sari,
            marginBottom: u(12),
          }}
        >
          {ustluk}
        </div>
      )}
      <div
        className="s-gir s-g2"
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(baslikBoyu),
          lineHeight: 1.02,
          letterSpacing: '0.005em',
          color: renk.metin,
          textShadow: '0 4px 28px rgba(0,0,0,0.75)',
        }}
      >
        {baslik}
      </div>
      {rakam != null && (
        <div className="s-gir s-g3" style={{ marginTop: u(18) }}>
          {rakam}
        </div>
      )}
      {alt != null && (
        <div className="s-gir s-g4" style={{ marginTop: u(16) }}>
          {/*
            Alt satırın arkasına yumuşak bir perde: canlı altlığın ilçe adları (GEMLİK, ORHANGAZİ)
            cümlenin son kelimelerinin içinden geçiyordu ve "taşır." okunmaz hâle geliyordu.
            Perde sağa doğru şeffaflaşır, yani bir kutu gibi görünmez.
          */}
          <span
            style={{
              display: 'inline-block',
              fontFamily: yazi.govde,
              fontSize: u(boy.buyuk),
              lineHeight: 1.3,
              color: renk.metin2,
              textShadow: '0 2px 18px rgba(5,10,24,0.95)',
              background:
                'linear-gradient(90deg, rgba(6,12,28,0.82) 0%, rgba(6,12,28,0.74) 62%, rgba(6,12,28,0) 100%)',
              padding: `${u(6)} ${u(56)} ${u(8)} ${u(14)}`,
              marginLeft: u(-14),
              borderRadius: u(10),
            }}
          >
            {alt}
          </span>
        </div>
      )}
    </div>
  );
}
