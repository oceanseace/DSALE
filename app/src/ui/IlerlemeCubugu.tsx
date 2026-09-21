/** İnce ilerleme çubuğu — film modu zamanlayıcısı ve penetrasyon barları için. */
import type { CSSProperties } from 'react';
import { renk, u } from './tema';

export interface IlerlemeCubuguProps {
  /** 0..1 */
  oran: number;
  /** yükseklik (tasarım px) */
  kalinlik?: number;
  renkKodu?: string;
  zeminRengi?: string;
  /** geçiş süresi ms (0 = anında; film çubuğu için 0 kullanın) */
  gecisMs?: number;
  parlama?: boolean;
  style?: CSSProperties;
}

export default function IlerlemeCubugu({
  oran,
  kalinlik = 6,
  renkKodu = renk.sari,
  zeminRengi = 'rgba(255,255,255,0.10)',
  gecisMs = 0,
  parlama = false,
  style,
}: IlerlemeCubuguProps) {
  const o = Math.max(0, Math.min(1, Number.isFinite(oran) ? oran : 0));
  return (
    <div
      style={{
        height: u(kalinlik),
        borderRadius: u(kalinlik),
        background: zeminRengi,
        overflow: 'hidden',
        width: '100%',
        ...style,
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${o * 100}%`,
          background: renkKodu,
          borderRadius: u(kalinlik),
          boxShadow: parlama ? `0 0 ${u(16)} ${renkKodu}aa` : undefined,
          transition: gecisMs ? `width ${gecisMs}ms cubic-bezier(0.22,1,0.36,1)` : undefined,
        }}
      />
    </div>
  );
}
