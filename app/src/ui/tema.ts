/**
 * Tema belirteçleri (design tokens).
 *
 * Ölçek: tüm boyutlar 1920×1080 tasarım pikseli cinsindendir ve `u(px)` ile ekrana orantılanır
 * (CSS değişkeni --u = min(100vh/1080, 100vw/1920)). Böylece sunum 1366×768'de de aynı kompozisyonu korur.
 * 65 yaşındaki izleyici için: gövde metni en az 28 tasarım pikseli, başlıklar 72-120.
 */
import type { CSSProperties } from 'react';

export const renk = {
  /** sahne zemini (neredeyse siyah lacivert) */
  zemin: '#03060D',
  zemin2: '#07101F',
  /** kara (ilçe alanları) */
  kara: '#0A1426',
  /** cam panel */
  panel: 'rgba(7, 14, 30, 0.72)',
  panelKoyu: 'rgba(3, 7, 16, 0.86)',
  cizgi: 'rgba(130, 170, 255, 0.18)',
  cizgiGuclu: 'rgba(130, 170, 255, 0.36)',
  /** Turkcell benzeri sarı vurgu */
  sari: '#FFC400',
  sariYumusak: 'rgba(255, 196, 0, 0.18)',
  /** elektrik mavisi */
  mavi: '#00A8FF',
  maviYumusak: 'rgba(0, 168, 255, 0.18)',
  metin: '#F4F7FF',
  metin2: '#B4C1DC',
  metin3: '#6F7FA0',
  /**
   * Durum renkleri — YALNIZ yazı ve ikon rengi olarak kullanılır.
   * Bölge renklerinin yanında dolgu (chip/rozet zemini) olarak kullanılmaz: bölge paleti
   * zaten 8 canlı renk taşır, üstüne yeşil/kırmızı dolgu eklemek "bu bölge kötü" izlenimi verir.
   */
  basari: '#7BE8B6',
  uyari: '#FFB35C',
  tehlike: '#FF8A9B',
} as const;

/** deck.gl katmanları için RGBA karşılıkları */
export const renkRgba = {
  zemin: [3, 6, 13, 255],
  kara: [10, 20, 38, 255],
  sari: [255, 196, 0, 255],
  mavi: [0, 168, 255, 255],
  beyaz: [244, 247, 255, 255],
  yol: [70, 120, 200, 255],
  su: [4, 14, 32, 255],
  kiyi: [0, 168, 255, 255],
  ilceSiniri: [140, 170, 230, 255],
} as const satisfies Record<string, [number, number, number, number]>;

export const yazi = {
  /** başlıklar ve büyük rakamlar (dar, güçlü) */
  baslik: "'Barlow Condensed', 'Arial Narrow', sans-serif",
  /** gövde metni */
  govde: "'Inter Variable', 'Segoe UI', system-ui, sans-serif",
  /** deck.gl TextLayer fontFamily (yerel yüklü) */
  harita: 'Barlow Condensed',
} as const;

/** Yazı boyutları (tasarım pikseli, 1080p) */
export const boy = {
  not: 16, // kaynak notu, dipnot
  kucuk: 22, // lejant ikincil
  govde: 28, // en küçük okunur gövde
  buyuk: 36,
  alt: 48, // alt başlık
  baslik: 72,
  dev: 120, // kahraman rakam / manşet
  mega: 168,
} as const;

/** Boşluk ölçeği (tasarım pikseli) */
export const bosluk = { xs: 8, s: 16, m: 24, l: 40, xl: 64, xxl: 96 } as const;

/** Tasarım pikselini ekrana orantılı CSS uzunluğuna çevirir: u(28) → "calc(28 * var(--u))" */
export function u(px: number): string {
  return `calc(${px} * var(--u))`;
}

/** Tasarım pikselini gerçek piksele çevirir (canvas/deck.gl gibi CSS dışı yerler için). */
export function uPx(px: number): number {
  if (typeof window === 'undefined') return px;
  return px * Math.min(window.innerHeight / 1080, window.innerWidth / 1920);
}

export const golge = {
  panel: '0 20px 60px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.06)',
  parlama: (hex: string) => `0 0 24px ${hex}66, 0 0 60px ${hex}33`,
} as const;

export const gecis = {
  hizli: 250,
  normal: 600,
  yavas: 1200,
  /** CSS easing */
  egri: 'cubic-bezier(0.22, 1, 0.36, 1)',
} as const;

/** Sık kullanılan hazır stiller */
export const stil = {
  tamEkran: { position: 'absolute', inset: 0 } satisfies CSSProperties,
  baslik: {
    fontFamily: yazi.baslik,
    fontWeight: 700,
    letterSpacing: '0.01em',
    lineHeight: 1.0,
    color: renk.metin,
  } satisfies CSSProperties,
  govde: {
    fontFamily: yazi.govde,
    fontSize: u(boy.govde),
    lineHeight: 1.35,
    color: renk.metin2,
  } satisfies CSSProperties,
  rakam: {
    fontFamily: yazi.baslik,
    fontWeight: 700,
    fontVariantNumeric: 'tabular-nums',
    lineHeight: 0.95,
    color: renk.metin,
  } satisfies CSSProperties,
} as const;

/* ------------------------------------------------------------------ durum (sapma) göstergesi */

export type DurumSeviyesi = 'iyi' | 'orta' | 'kotu';

export interface DurumIsareti {
  seviye: DurumSeviyesi;
  /** ✓ (hedefte) · ▲ (hedefin üstünde) · ▼ (hedefin altında) */
  ikon: string;
  /** yalnız yazı/ikon rengi */
  renk: string;
}

/**
 * Sapmayı (0..1 oran, işaretli) nötr bir işarete çevirir.
 * |sapma| ≤ esik → ✓ "dengede"; üstündeyse yön oku. Dolgu rengi ÜRETMEZ.
 */
export function durumIsareti(sapma: number, esik = 0.01): DurumIsareti {
  const a = Math.abs(sapma);
  if (!Number.isFinite(sapma) || a <= esik) return { seviye: 'iyi', ikon: '✓', renk: renk.metin2 };
  const ikon = sapma > 0 ? '▲' : '▼';
  if (a <= esik * 2) return { seviye: 'orta', ikon, renk: renk.uyari };
  return { seviye: 'kotu', ikon, renk: renk.tehlike };
}

export const tema = { renk, renkRgba, yazi, boy, bosluk, golge, gecis, stil, u, uPx, durumIsareti } as const;
export default tema;
