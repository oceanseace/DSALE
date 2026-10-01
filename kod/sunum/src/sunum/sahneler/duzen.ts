/** Sahne yerleşimi — her sahne aynı çapa noktalarını kullanır (1920×1080 tasarım pikseli). */
import type { CSSProperties } from 'react';
import { u } from '../../ui/tema';

const KENAR = 72;

export const duzen = {
  /** manşet bloğu: sol alt (ilerleme noktalarının üstü) */
  solAlt: { position: 'absolute', left: u(KENAR), bottom: u(150) } as CSSProperties,
  /** ikincil bilgi: sol üst (markanın altı) */
  solUst: { position: 'absolute', left: u(KENAR), top: u(150) } as CSSProperties,
  /** kart / panel: sağ */
  sag: { position: 'absolute', right: u(KENAR), top: u(140) } as CSSProperties,
  sagAlt: { position: 'absolute', right: u(KENAR), bottom: u(150) } as CSSProperties,
  /** ortalanmış alt şerit (lejant, adım ikonları) */
  ortaAlt: {
    position: 'absolute',
    left: '50%',
    bottom: u(96),
    transform: 'translateX(-50%)',
  } as CSSProperties,
  /** tam genişlik alt şerit */
  serit: { position: 'absolute', left: u(KENAR), right: u(KENAR), bottom: u(96) } as CSSProperties,
  /** ekran ortası */
  orta: {
    position: 'absolute',
    left: '50%',
    top: '50%',
    transform: 'translate(-50%, -50%)',
    textAlign: 'center',
  } as CSSProperties,
} as const;

export const KENAR_BOSLUK = KENAR;
