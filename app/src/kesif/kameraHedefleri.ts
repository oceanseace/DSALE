/**
 * Keşif kamera hedefleri ve arayüz kenar boşlukları.
 *
 * Sol panel, sağ çekmece ve üst çubuk haritanın üstünde durduğundan `fitBounds` boşlukları
 * tasarım pikselinden gerçek piksele (`uPx`) çevrilerek verilir — böylece seçilen bölge
 * panellerin altında kalmaz.
 */
import { veri } from '../data/load';
import type { LonLat } from '../data/types';
import { uPx } from '../ui/tema';

/** Tasarım pikseli cinsinden yerleşim ölçüleri (1920×1080). */
export const OLCU = {
  kenar: 36,
  ustCubuk: 112,
  solGenislik: 432,
  sagGenislik: 500,
} as const;

export interface KenarBosluk {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

/** deck.gl `fitBounds` için gerçek piksel kenar boşlukları. */
export function uiBosluk(sagAcik: boolean): KenarBosluk {
  return {
    top: uPx(OLCU.ustCubuk + 28),
    bottom: uPx(64),
    left: uPx(OLCU.kenar + OLCU.solGenislik + 28),
    right: uPx(sagAcik ? OLCU.kenar + OLCU.sagGenislik + 28 : 64),
  };
}

/** Bina indekslerinin sınır kutusu (arama sonucu / site grubu uçuşu). */
export function binaKutusu(indeksler: number[]): [LonLat, LonLat] {
  const b = veri().binalar;
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const i of indeksler) {
    const x = b.lon[i];
    const y = b.lat[i];
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  if (!Number.isFinite(x0)) return [[28.9, 40.2], [29.0, 40.25]];
  // tek bina / çok küçük kutu: en az ~250 m genişlet
  const d = 0.0018;
  if (x1 - x0 < d) {
    const c = (x0 + x1) / 2;
    x0 = c - d / 2;
    x1 = c + d / 2;
  }
  if (y1 - y0 < d) {
    const c = (y0 + y1) / 2;
    y0 = c - d / 2;
    y1 = c + d / 2;
  }
  return [[x0, y0], [x1, y1]];
}
