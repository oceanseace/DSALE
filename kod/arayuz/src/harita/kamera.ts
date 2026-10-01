/**
 * Kamera yardımcıları: 2B ↔ 3B geçişi ve eğik haritada kutu seçimi.
 */

import { FlyToInterpolator, WebMercatorViewport, type MapViewState } from '@deck.gl/core';

/** 3B'de kameranın eğimi (derece). 60 deck.gl'in üst sınırı; 55 hem derin hem okunur. */
export const UC_B_EGIM = 55;
const UC_B_ACI = -20;

const GECIS = new FlyToInterpolator({ speed: 1.8 });

/**
 * 3B'ye geçiş: kamera yumuşakça eğilir. Şehir genelinden bakarken binalar
 * birkaç piksel boyunda kalır; bu yüzden gerekirse mahalle ölçeğine yaklaşılır.
 */
export function ucBGorunumu(
  g: MapViewState,
  enAzZoom: number,
  odak?: readonly [number, number] | null,
): MapViewState {
  return {
    ...g,
    longitude: odak ? odak[0] : g.longitude,
    latitude: odak ? odak[1] : g.latitude,
    zoom: Math.max(g.zoom, enAzZoom),
    pitch: UC_B_EGIM,
    bearing: Math.abs(g.bearing ?? 0) > 1 ? (g.bearing ?? 0) : UC_B_ACI,
    transitionDuration: 1100,
    transitionInterpolator: GECIS,
  };
}

/** 2B'ye dönüş: kuzey yukarı, tepeden bakış. */
export function duzGorunum(g: MapViewState): MapViewState {
  return {
    ...g,
    pitch: 0,
    bearing: 0,
    transitionDuration: 700,
    transitionInterpolator: GECIS,
  };
}

/**
 * Ekranda çizilen dikdörtgenin haritadaki karşılığı.
 * Kamera döndürülmüş ya da eğikse ekrandaki dikdörtgen haritada yamuk olur;
 * iki köşeden kutu çıkarmak yanlış binaları seçer. Dört köşe ayrı ayrı
 * çevrilir, seçim bu dörtgenin içidir.
 */
export function ekrandanCokgen(
  g: MapViewState,
  genislik: number,
  yukseklik: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): Array<[number, number]> {
  const gorus = new WebMercatorViewport({ ...g, width: genislik, height: yukseklik });
  const sol = Math.min(x1, x2);
  const sag = Math.max(x1, x2);
  const ust = Math.min(y1, y2);
  const alt = Math.max(y1, y2);
  return [
    [sol, ust],
    [sag, ust],
    [sag, alt],
    [sol, alt],
  ].map((p) => gorus.unproject(p) as [number, number]).map((p) => [p[0], p[1]]);
}

/** Nokta çokgenin içinde mi (ışın yöntemi). */
export function cokgenIcinde(cokgen: ReadonlyArray<readonly [number, number]>, lon: number, lat: number) {
  let icinde = false;
  for (let i = 0, j = cokgen.length - 1; i < cokgen.length; j = i++) {
    const [xi, yi] = cokgen[i];
    const [xj, yj] = cokgen[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) icinde = !icinde;
  }
  return icinde;
}

/** Küçük ekran mı (telefon)? 3B orada görünen alanla sınırlanır. */
export function kucukEkran(): boolean {
  try {
    return window.matchMedia('(max-width: 760px), (pointer: coarse)').matches;
  } catch {
    return false;
  }
}

/** Fareyle üstüne gelinebiliyor mu? Değilse (dokunmatik) ipucu gösterilmez. */
export function fareVar(): boolean {
  try {
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  } catch {
    return true;
  }
}
