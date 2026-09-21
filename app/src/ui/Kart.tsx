/** Cam panel (glass card): koyu saydam zemin, ince kenar, yumuşak gölge. */
import type { CSSProperties, ReactNode } from 'react';
import { bosluk, golge, renk, u, yazi, boy } from './tema';

export interface KartProps {
  children: ReactNode;
  /** başlık satırı (isteğe bağlı) */
  baslik?: ReactNode;
  /** sol kenarda renk şeridi (bölge rengi) */
  seritRengi?: string;
  /** iç boşluk (tasarım px) */
  ic?: number;
  /** köşe yarıçapı (tasarım px) */
  yaricap?: number;
  koyu?: boolean;
  style?: CSSProperties;
  className?: string;
  onClick?: () => void;
}

export default function Kart({
  children,
  baslik,
  seritRengi,
  ic = bosluk.m,
  yaricap = 18,
  koyu = false,
  style,
  className,
  onClick,
}: KartProps) {
  return (
    <div
      className={className}
      onClick={onClick}
      style={{
        position: 'relative',
        background: koyu ? renk.panelKoyu : renk.panel,
        border: `1px solid ${renk.cizgi}`,
        borderRadius: u(yaricap),
        boxShadow: golge.panel,
        padding: u(ic),
        backdropFilter: 'blur(14px)',
        overflow: 'hidden',
        ...style,
      }}
    >
      {seritRengi && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: u(6),
            background: seritRengi,
            boxShadow: golge.parlama(seritRengi),
          }}
        />
      )}
      {baslik != null && (
        <div
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: renk.metin3,
            marginBottom: u(bosluk.s),
          }}
        >
          {baslik}
        </div>
      )}
      {children}
    </div>
  );
}
