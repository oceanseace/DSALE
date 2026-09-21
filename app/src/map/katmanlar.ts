/**
 * Katman fabrikası — deck.gl katmanlarını döndüren SAF fonksiyonlar.
 *
 * Kurallar:
 *  - Her fonksiyon yeni katman örnekleri döndürür; aynı `id` ile her karede yeniden çağırmak normaldir
 *    (deck.gl yalnız değişen prop'ları işler). Veri nesneleri önbellekli ve kimliği sabittir.
 *  - Erişimci (accessor) fonksiyonlarının kimliği önemsizdir; değişiklik `updateTriggers` ile bildirilir.
 *  - Önerilen çizim sırası:
 *      karo? → altlik → bolgeSinirlari(dolgu) → binalar3D / binaIsiklari → bolgeSinirlari(çizgi)
 *      → hpSutunlari → arklar → ofisIsaretcisi → etiketler
 *    (bolgeSinirlari tek çağrıda dolgu + çizgi döndürür; sıralama için `parca` seçeneğini kullanın.)
 */
import type { Color, Layer, LayersList, Position } from '@deck.gl/core';
import {
  ArcLayer,
  BitmapLayer,
  ColumnLayer,
  PathLayer,
  ScatterplotLayer,
  SolidPolygonLayer,
  TextLayer,
} from '@deck.gl/layers';
import { TileLayer, TripsLayer } from '@deck.gl/geo-layers';
import { HexagonLayer } from '@deck.gl/aggregation-layers';
import { DataFilterExtension, PathStyleExtension } from '@deck.gl/extensions';
import { interpolateRgbBasis } from 'd3-interpolate';
import { scaleLinear, scaleLog, scaleSqrt } from 'd3-scale';

import {
  anlikBinaBolgeleri,
  binaBolgeleri,
  bolgeAlanlari,
  bolgeEtiketNoktasi,
  bolgeHalkalari,
  veri,
  type BolgeAlani,
  type BolgeHalkasi,
  type IlceEtiketi,
  type YolParcasi,
} from '../data/load';
import { binaMetrigi, buyukHarf, hexRgba, karistir, tonla, type BinaMetrigi, type RGBA } from '../data/selectors';
import type { Bolge, LonLat, Plan } from '../data/types';
import { renkRgba } from '../ui/tema';
import { HARITA_FONT } from './fontlar';
import { BINA_MALZEMESI, SUTUN_MALZEMESI } from './isik';

/* ================================================================== ortak */

/** Düz zemin katmanları: derinlik yazmaz, sırayla çizilir (z-fighting yok). */
const ZEMIN_PARAMETRELERI = { depthWriteEnabled: false, depthCompare: 'always' } as const;
/** Toplamsal karışım (parlama/ışık) */
export const TOPLAMSAL_KARISIM = {
  blend: true,
  blendColorOperation: 'add',
  blendColorSrcFactor: 'src-alpha',
  blendColorDstFactor: 'one',
  blendAlphaOperation: 'add',
  blendAlphaSrcFactor: 'one',
  blendAlphaDstFactor: 'one-minus-src-alpha',
  depthWriteEnabled: false,
} as const;
/** Her zaman üstte (etiketler) */
const USTTE_PARAMETRELERI = { depthCompare: 'always', depthWriteEnabled: false } as const;

function alfa(c: readonly number[], a: number): RGBA {
  return [c[0], c[1], c[2], Math.max(0, Math.min(255, a))];
}

/** Plan nesnesine kararlı kimlik (updateTriggers için) */
const planKimlikleri = new WeakMap<Plan, number>();
let _planSayaci = 0;
export function planAnahtari(plan: Plan | null | undefined): string {
  if (!plan) return '-';
  let k = planKimlikleri.get(plan);
  if (k == null) {
    k = ++_planSayaci;
    planKimlikleri.set(plan, k);
  }
  return `${plan.n}#${k}`;
}

/* ================================================================== altlık */

export interface AltlikSecenekleri {
  id?: string;
  /** 0..1 genel opaklık çarpanı (belirme animasyonu için) */
  gorunurluk?: number;
  /** ilçe adları */
  ilceEtiketleri?: boolean;
  /** ilçe sınırları (kesikli çizgi) */
  ilceSinirlari?: boolean;
  /** yol parlaması (geniş, soluk alt çizgi) */
  yolParlama?: boolean;
  /** ilçe etiket boyutu (px) */
  etiketBoyutu?: number;
  /** kara (ilçe alanı) dolgusu */
  kara?: boolean;
}

/**
 * Çevrimdışı altlık: kara (ilçe alanları), göller, kıyı çizgisi (parlamalı), yollar (öneme göre), ilçe sınırları + adları.
 */
export function altlik(o: AltlikSecenekleri = {}): Layer[] {
  const {
    id = 'altlik',
    gorunurluk = 1,
    ilceEtiketleri = true,
    ilceSinirlari = true,
    yolParlama = true,
    etiketBoyutu = 22,
    kara = true,
  } = o;
  const a = veri().altlik;
  const g = Math.max(0, Math.min(1, gorunurluk));
  const k: Layer[] = [];

  if (kara)
    k.push(
      new SolidPolygonLayer<(typeof a.ilceAlanlari)[number]>({
        id: `${id}-kara`,
        data: a.ilceAlanlari,
        getPolygon: (d) => d.poligon,
        getFillColor: alfa(renkRgba.kara, 255 * g),
        parameters: ZEMIN_PARAMETRELERI,
        updateTriggers: { getFillColor: g },
      }),
    );

  k.push(
    new SolidPolygonLayer<LonLat[][]>({
      id: `${id}-gol`,
      data: a.goller,
      getPolygon: (d) => d,
      getFillColor: alfa(renkRgba.su, 255 * g),
      parameters: ZEMIN_PARAMETRELERI,
      updateTriggers: { getFillColor: g },
    }),
    new PathLayer<LonLat[]>({
      id: `${id}-kiyi-hale`,
      data: a.kiyi,
      getPath: (d) => d,
      getColor: alfa(renkRgba.kiyi, 38 * g),
      getWidth: 9,
      widthUnits: 'pixels',
      jointRounded: true,
      capRounded: true,
      parameters: ZEMIN_PARAMETRELERI,
      updateTriggers: { getColor: g },
    }),
    new PathLayer<LonLat[]>({
      id: `${id}-kiyi`,
      data: a.kiyi,
      getPath: (d) => d,
      getColor: alfa(renkRgba.kiyi, 150 * g),
      getWidth: 1.4,
      widthUnits: 'pixels',
      parameters: ZEMIN_PARAMETRELERI,
      updateTriggers: { getColor: g },
    }),
  );

  if (ilceSinirlari) {
    // getDashArray/dashJustified PathStyleExtension prop'larıdır; PathLayerProps tipinde yoktur.
    const sinirProps = {
      id: `${id}-ilce-sinir`,
      data: a.ilceSinirlari,
      getPath: (d: { yol: LonLat[] }) => d.yol,
      getColor: alfa(renkRgba.ilceSiniri, 60 * g),
      getWidth: 1.2,
      widthUnits: 'pixels',
      getDashArray: [5, 4],
      dashJustified: true,
      extensions: [new PathStyleExtension({ dash: true })],
      parameters: ZEMIN_PARAMETRELERI,
      updateTriggers: { getColor: g },
    };
    k.push(new PathLayer<{ ad: string; yol: LonLat[] }>(sinirProps as never));
  }

  const YOL_GENISLIK = [0, 2.6, 1.8, 1.1, 0.7];
  const YOL_ALFA = [0, 170, 125, 80, 50];
  if (yolParlama)
    k.push(
      new PathLayer<YolParcasi>({
        id: `${id}-yol-hale`,
        data: a.yollar.filter((y) => y.s <= 2),
        getPath: (d) => d.yol,
        getColor: alfa(renkRgba.yol, 28 * g),
        getWidth: (d) => (d.s === 1 ? 9 : 6),
        widthUnits: 'pixels',
        jointRounded: true,
        parameters: ZEMIN_PARAMETRELERI,
        updateTriggers: { getColor: g },
      }),
    );
  k.push(
    new PathLayer<YolParcasi>({
      id: `${id}-yol`,
      data: a.yollar,
      getPath: (d) => d.yol,
      getColor: (d) => alfa(d.s <= 1 ? [120, 160, 230] : renkRgba.yol, YOL_ALFA[d.s] * g),
      getWidth: (d) => YOL_GENISLIK[d.s],
      widthUnits: 'pixels',
      jointRounded: true,
      parameters: ZEMIN_PARAMETRELERI,
      updateTriggers: { getColor: g },
    }),
  );

  if (ilceEtiketleri) k.push(ilceEtiketKatmani({ id: `${id}-ilce-etiket`, gorunurluk: g, etiketBoyutu }));
  return k;
}

export interface IlceEtiketSecenekleri {
  id?: string;
  gorunurluk?: number;
  etiketBoyutu?: number;
}

/**
 * Yalnız ilçe adları — `altlik()` bunu kendi içinde çağırır.
 *
 * Ayrı durmasının nedeni çizim SIRASI: altlık en başta çizilir, dolayısıyla sonradan gelen
 * 3B sütunlar (S2/S3 altıgenleri) ilçe adlarının üstüne biniyor ve "GEMLİK" → "GE..İK" oluyordu.
 * Sütunlu sahneler `altlik({ ilceEtiketleri: false })` deyip bu katmanı EN SONA koyar.
 */
export function ilceEtiketKatmani(o: IlceEtiketSecenekleri = {}): Layer {
  const { id = 'ilce-etiket', gorunurluk = 1, etiketBoyutu = 22 } = o;
  const g = Math.max(0, Math.min(1, gorunurluk));
  return new TextLayer<IlceEtiketi>({
    id,
    data: veri().altlik.ilceEtiketleri,
    getPosition: (d) => d.konum,
    getText: (d) => aralikli(buyukHarf(d.ad)),
    getColor: (d) => (d.aktif ? alfa([170, 190, 230], 150 * g) : alfa([120, 140, 180], 80 * g)),
    getSize: (d) => (d.aktif ? etiketBoyutu : etiketBoyutu * 0.8),
    sizeUnits: 'pixels',
    ...HARITA_FONT,
    fontWeight: 600,
    outlineWidth: 3,
    outlineColor: [3, 6, 13, 220],
    parameters: USTTE_PARAMETRELERI,
    updateTriggers: { getColor: g },
  });
}

/** "NİLÜFER" → "N İ L Ü F E R" (ince boşluklu, zarif harita etiketi) */
export function aralikli(s: string): string {
  return [...s].join(' ');
}

/* ================================================================== binalar */

export type BinaRenkModu =
  | { tur: 'bolge'; plan: Plan }
  | { tur: 'tek'; renk: RGBA }
  | {
      tur: 'metrik';
      metrik: BinaMetrigi;
      /** hex renk durakları (düşük → yüksek) */
      palet?: string[];
      /** [min, maks]; verilmezse [0, %98'lik] */
      alan?: [number, number];
      olcek?: 'dogrusal' | 'karekok' | 'log';
    }
  | { tur: 'ozel'; renk: (i: number) => RGBA; /** değişince renkler yeniden hesaplanır */ anahtar: string }
  | {
      /** Algoritma ara adımı: plan.anlik_etiket[s] dizesine göre renk (S4 "nasıl böldük"). */
      tur: 'etiketDizisi';
      /** birim başına bölge karakteri: bölge = charCodeAt(birim) − 48 */
      dizi: string;
      /** bölge no → renk tablosu (genelde bolgeRenkTablosu(plan)) */
      tablo: RGBA[];
      /** önbellek anahtarı; verilmezse adım dizesinin uzunluğu + tablo kullanılır */
      anahtar?: string;
    };

/** Varsayılan metrik paleti: gece mavisi → elektrik mavisi → camgöbeği → sarı → beyaz */
export const METRIK_PALETI = ['#0B1E3F', '#0057B8', '#00A8FF', '#7CF3FF', '#FFC400', '#FFF4CC'];

function renkModuAnahtari(m: BinaRenkModu): string {
  switch (m.tur) {
    case 'bolge':
      return 'bolge:' + planAnahtari(m.plan);
    case 'tek':
      return 'tek:' + m.renk.join(',');
    case 'metrik':
      return `metrik:${m.metrik}:${m.palet?.join('') ?? ''}:${m.alan?.join(',') ?? ''}:${m.olcek ?? ''}`;
    case 'ozel':
      return 'ozel:' + m.anahtar;
    case 'etiketDizisi':
      return 'anlik:' + (m.anahtar ?? `${m.dizi.length}#${m.tablo.length}#${m.dizi.slice(0, 24)}`);
  }
}

function yuzdelik(deger: (i: number) => number, n: number, p: number): number {
  const a = new Float64Array(n);
  for (let i = 0; i < n; i++) a[i] = deger(i);
  a.sort();
  return a[Math.min(n - 1, Math.floor(p * n))] || 1;
}

/**
 * Bina rengi tablosu (i → RGBA, düz Uint8ClampedArray). Sonuç `anahtar` başına önbelleklenir —
 * 'ozel' modu dahil: S4 gibi sahneler her karede aynı anahtarla çağırır, 19.706 bina × her kare
 * yeniden hesaplanmamalıdır. Renk fonksiyonu değiştiğinde `anahtar`ı değiştirin.
 */
const renkOnbellek = new Map<string, Uint8ClampedArray>();
const RENK_ONBELLEK_SINIRI = 16;

function onbellegeYaz(anahtar: string, out: Uint8ClampedArray): void {
  if (renkOnbellek.size >= RENK_ONBELLEK_SINIRI) {
    // en eski girdiyi at (Map ekleme sırasını korur)
    const ilk = renkOnbellek.keys().next();
    if (!ilk.done) renkOnbellek.delete(ilk.value);
  }
  renkOnbellek.set(anahtar, out);
}

export function binaRenkleri(m: BinaRenkModu): Uint8ClampedArray {
  const anahtar = renkModuAnahtari(m);
  const var_ = renkOnbellek.get(anahtar);
  if (var_) return var_;
  const { n } = veri().binalar;
  const out = new Uint8ClampedArray(n * 4);
  const yaz = (i: number, c: readonly number[]) => {
    out[4 * i] = c[0];
    out[4 * i + 1] = c[1];
    out[4 * i + 2] = c[2];
    out[4 * i + 3] = c[3] ?? 255;
  };
  if (m.tur === 'bolge') {
    const bb = binaBolgeleri(m.plan);
    const tablo: RGBA[] = [];
    for (const b of m.plan.bolgeler) tablo[b.bolge] = hexRgba(b.renk);
    for (let i = 0; i < n; i++) yaz(i, tablo[bb[i]] ?? [90, 100, 120, 255]);
  } else if (m.tur === 'tek') {
    for (let i = 0; i < n; i++) yaz(i, m.renk);
  } else if (m.tur === 'metrik') {
    const f = binaMetrigi(m.metrik);
    const alan = m.alan ?? [0, yuzdelik(f, n, 0.98)];
    const interp = interpolateRgbBasis(m.palet ?? METRIK_PALETI);
    const olcek =
      m.olcek === 'log'
        ? scaleLog().domain([Math.max(1, alan[0]), alan[1]]).range([0, 1]).clamp(true)
        : m.olcek === 'dogrusal'
          ? scaleLinear().domain(alan).range([0, 1]).clamp(true)
          : scaleSqrt().domain(alan).range([0, 1]).clamp(true);
    const tablo: RGBA[] = [];
    for (let s = 0; s <= 255; s++) tablo[s] = hexRgba(rgbDizeHex(interp(s / 255)));
    for (let i = 0; i < n; i++) {
      const v = f(i);
      yaz(i, tablo[Math.round(olcek(m.olcek === 'log' ? Math.max(1, v) : v) * 255)]);
    }
  } else if (m.tur === 'etiketDizisi') {
    const bb = anlikBinaBolgeleri(m.dizi);
    const notr: RGBA = [90, 100, 120, 255];
    for (let i = 0; i < n; i++) yaz(i, m.tablo[bb[i]] ?? notr);
  } else {
    for (let i = 0; i < n; i++) yaz(i, m.renk(i));
  }
  onbellegeYaz(anahtar, out);
  return out;
}

function rgbDizeHex(s: string): string {
  // d3-interpolate "rgb(r, g, b)" döndürür
  const m = s.match(/\d+(\.\d+)?/g);
  if (!m) return '#ffffff';
  return '#' + m.slice(0, 3).map((x) => Math.round(+x).toString(16).padStart(2, '0')).join('');
}

export interface Binalar3DSecenekleri {
  id?: string;
  /** renk modu (varsayılan: plan verilmişse bölge rengi, yoksa sarı) */
  renkModu?: BinaRenkModu;
  /** bölge vurgusu / bölge filtresi için plan */
  plan?: Plan;
  /** elevationScale — "şehir yükseliyor" için 0 → 1 (ya da abartı için > 1) animasyonu */
  yukseklikOlcegi?: number;
  /** yalnız bu bölgeler canlı renkte; diğerleri koyulaşır */
  vurguBolgeler?: number[] | null;
  /** vurgusuz binaların koyulaşma oranı 0..1 (varsayılan 0.82) */
  sonukluk?: number;
  /** yalnız bu bölgelerin binaları görünür (GPU filtresi) */
  gorunurBolgeler?: number[] | null;
  /** yalnız ofise bu km'den yakın binalar görünür (GPU filtresi) — "fiber ofisten yayılıyor" animasyonu */
  gorunurYaricapKm?: number | null;
  /** renk geçiş süresi (ms) */
  renkGecisMs?: number;
  pickable?: boolean;
  /** vurgulanan (üzerine gelinen) binayı parlat */
  autoHighlight?: boolean;
  /** genel opaklık 0..1 */
  opacity?: number;
  /** tel kafes kenarlar */
  kenar?: boolean;
}

/**
 * 19.706 binanın ekstrüde taban poligonları (yükseklik = kat × 3 m × yukseklikOlcegi).
 * İkili veri + GPU filtresi — kare başına yeniden oluşturmak ucuzdur (yalnız uniform'lar değişir).
 */
export function binalar3D(o: Binalar3DSecenekleri = {}): Layer {
  const {
    id = 'binalar',
    plan,
    yukseklikOlcegi = 1,
    vurguBolgeler = null,
    sonukluk = 0.82,
    gorunurBolgeler = null,
    gorunurYaricapKm = null,
    renkGecisMs = 0,
    pickable = true,
    autoHighlight = false,
    opacity = 1,
    kenar = false,
  } = o;
  const b = veri().binalar;
  const renkModu: BinaRenkModu = o.renkModu ?? (plan ? { tur: 'bolge', plan } : { tur: 'tek', renk: [255, 196, 0, 255] });
  const renkler = binaRenkleri(renkModu);
  const bb = plan ? binaBolgeleri(plan) : null;
  const vurgu = vurguBolgeler && bb ? new Set(vurguBolgeler) : null;
  const koyu: RGBA = [8, 14, 28, 255];

  const kategori = gorunurBolgeler && bb ? gorunurBolgeler : null;
  const maksBolge = plan ? Math.max(...plan.bolgeler.map((x) => x.bolge)) : 0;

  return new SolidPolygonLayer({
    id,
    data: b.taban as never,
    _normalize: false,
    extruded: true,
    wireframe: kenar,
    getLineColor: [255, 255, 255, 40],
    getElevation: (_: unknown, { index }: { index: number }) => b.yukseklik[index],
    elevationScale: yukseklikOlcegi,
    getFillColor: (_: unknown, { index }: { index: number }) => {
      const c: RGBA = [renkler[4 * index], renkler[4 * index + 1], renkler[4 * index + 2], renkler[4 * index + 3]];
      if (vurgu && bb && !vurgu.has(bb[index])) return karistir(c, koyu, sonukluk);
      return c;
    },
    material: BINA_MALZEMESI,
    opacity,
    pickable,
    autoHighlight,
    highlightColor: [255, 255, 255, 110],
    transitions: renkGecisMs ? { getFillColor: { duration: renkGecisMs } } : undefined,
    updateTriggers: {
      getFillColor: [renkModuAnahtari(renkModu), vurguBolgeler?.join(',') ?? '', sonukluk, planAnahtari(plan)],
      getFilterCategory: planAnahtari(plan),
    },
    // GPU filtreleri: [ofis uzaklığı km] + [bölge kategorisi]
    extensions: [new DataFilterExtension({ filterSize: 1, categorySize: 1 })],
    getFilterValue: (_: unknown, { index }: { index: number }) => b.ofisMesafeKm[index],
    filterRange: [-1, gorunurYaricapKm ?? 1e6],
    filterSoftRange: gorunurYaricapKm != null ? [-1, Math.max(0, gorunurYaricapKm - 1.5)] : undefined,
    getFilterCategory: (_: unknown, { index }: { index: number }) => (bb ? bb[index] : 0),
    filterCategories: kategori ?? Array.from({ length: maksBolge + 1 }, (_, i) => i),
  } as never);
}

export interface BinaIsiklariSecenekleri {
  id?: string;
  renkModu?: BinaRenkModu;
  plan?: Plan;
  /** metre (varsayılan 22) */
  yaricap?: number;
  /** en küçük piksel yarıçapı (uzak görünümde görünür kalsın) */
  minPiksel?: number;
  /** 0..255 */
  alfa?: number;
  gorunurYaricapKm?: number | null;
}

/**
 * Binalar "şehir ışıkları" olarak (toplamsal parlayan noktalar) — uzak görünümlerde 3B yerine/üstüne.
 */
export function binaIsiklari(o: BinaIsiklariSecenekleri = {}): Layer {
  const { id = 'bina-isik', plan, yaricap = 22, minPiksel = 1.3, alfa: a = 200, gorunurYaricapKm = null } = o;
  const b = veri().binalar;
  const renkModu: BinaRenkModu = o.renkModu ?? (plan ? { tur: 'bolge', plan } : { tur: 'tek', renk: [255, 196, 0, 255] });
  const renkler = binaRenkleri(renkModu);
  return new ScatterplotLayer({
    id,
    data: { length: b.n } as never,
    getPosition: (_: unknown, { index }: { index: number }) => [b.lon[index], b.lat[index]],
    getRadius: yaricap,
    radiusUnits: 'meters',
    radiusMinPixels: minPiksel,
    getFillColor: (_: unknown, { index }: { index: number }) => [
      renkler[4 * index],
      renkler[4 * index + 1],
      renkler[4 * index + 2],
      a,
    ],
    parameters: TOPLAMSAL_KARISIM,
    updateTriggers: { getFillColor: [renkModuAnahtari(renkModu), a] },
    extensions: [new DataFilterExtension({ filterSize: 1 })],
    getFilterValue: (_: unknown, { index }: { index: number }) => b.ofisMesafeKm[index],
    filterRange: [-1, gorunurYaricapKm ?? 1e6],
  } as never);
}

/* ================================================================== bölge sınırları */

export interface BolgeSinirlariSecenekleri {
  plan: Plan;
  id?: string;
  /** 'hepsi' | yalnız 'dolgu' | yalnız 'cizgi' (çizim sırasını ayarlamak için) */
  parca?: 'hepsi' | 'dolgu' | 'cizgi';
  /** dolgu opaklığı 0..255 (varsayılan 34) */
  dolguAlfa?: number;
  /** çekirdek çizgi genişliği px (varsayılan 2.5) */
  cizgiGenislik?: number;
  /** parlama katmanları */
  parlama?: boolean;
  /** vurgulanan bölgeler (diğerleri sönük) */
  vurguBolgeler?: number[] | null;
  /** yalnız bu bölgeler çizilir */
  bolgeler?: number[] | null;
  /** 0..1 opaklık çarpanı */
  gorunurluk?: number;
}

/**
 * Bölge sınırları: yarı saydam dolgu + parlayan (glow) sınır çizgisi.
 */
export function bolgeSinirlari(o: BolgeSinirlariSecenekleri): Layer[] {
  const {
    plan,
    id = 'bolge',
    parca = 'hepsi',
    dolguAlfa = 34,
    cizgiGenislik = 2.5,
    parlama = true,
    vurguBolgeler = null,
    bolgeler = null,
    gorunurluk = 1,
  } = o;
  const g = Math.max(0, Math.min(1, gorunurluk));
  const sec = bolgeler ? new Set(bolgeler) : null;
  const vurgu = vurguBolgeler ? new Set(vurguBolgeler) : null;
  const carpan = (no: number) => (vurgu ? (vurgu.has(no) ? 1 : 0.25) : 1) * g;
  const alanlar = sec ? bolgeAlanlari(plan).filter((d) => sec.has(d.bolge)) : bolgeAlanlari(plan);
  const halkalar = sec ? bolgeHalkalari(plan).filter((d) => sec.has(d.bolge)) : bolgeHalkalari(plan);
  const tetik = [planAnahtari(plan), vurguBolgeler?.join(',') ?? '', bolgeler?.join(',') ?? '', g, dolguAlfa];
  const k: Layer[] = [];

  if (parca !== 'cizgi' && dolguAlfa > 0)
    k.push(
      new SolidPolygonLayer<BolgeAlani>({
        id: `${id}-dolgu`,
        data: alanlar,
        getPolygon: (d) => d.poligon,
        getFillColor: (d) => alfa(hexRgba(d.renk), dolguAlfa * carpan(d.bolge) * (vurgu?.has(d.bolge) ? 1.6 : 1)),
        parameters: ZEMIN_PARAMETRELERI,
        updateTriggers: { getFillColor: tetik },
        pickable: false,
      }),
    );

  if (parca !== 'dolgu') {
    if (parlama)
      k.push(
        new PathLayer<BolgeHalkasi>({
          id: `${id}-hale-genis`,
          data: halkalar,
          getPath: (d) => d.yol,
          getColor: (d) => alfa(hexRgba(d.renk), 30 * carpan(d.bolge)),
          getWidth: cizgiGenislik * 7,
          widthUnits: 'pixels',
          jointRounded: true,
          capRounded: true,
          parameters: TOPLAMSAL_KARISIM,
          updateTriggers: { getColor: tetik, getWidth: cizgiGenislik },
        }),
        new PathLayer<BolgeHalkasi>({
          id: `${id}-hale`,
          data: halkalar,
          getPath: (d) => d.yol,
          getColor: (d) => alfa(hexRgba(d.renk), 70 * carpan(d.bolge)),
          getWidth: cizgiGenislik * 3,
          widthUnits: 'pixels',
          jointRounded: true,
          capRounded: true,
          parameters: TOPLAMSAL_KARISIM,
          updateTriggers: { getColor: tetik, getWidth: cizgiGenislik },
        }),
      );
    k.push(
      new PathLayer<BolgeHalkasi>({
        id: `${id}-cizgi`,
        data: halkalar,
        getPath: (d) => d.yol,
        getColor: (d) => alfa(tonla(hexRgba(d.renk), 0.25), 255 * carpan(d.bolge)),
        getWidth: (d) => (vurgu?.has(d.bolge) ? cizgiGenislik * 1.6 : cizgiGenislik),
        widthUnits: 'pixels',
        jointRounded: true,
        capRounded: true,
        updateTriggers: { getColor: tetik, getWidth: tetik },
      }),
    );
  }
  return k;
}

/* ================================================================== HP sütunları */

export type SutunOlcusu = 'res_hp' | 'firsat' | 'aktif' | 'toplam_hp';

export interface HpSutunlariSecenekleri {
  id?: string;
  /** hangi ölçü (varsayılan 'res_hp') */
  olcu?: SutunOlcusu;
  /** 'hex' = altıgen ızgara (bina verisinden), 'bolge' = bölge merkezlerinde birer sütun */
  mod?: 'hex' | 'bolge';
  /** mod 'bolge' için zorunlu */
  plan?: Plan;
  /** hex yarıçapı (m, varsayılan 450) ya da bölge sütun yarıçapı (m, varsayılan 900) */
  yaricap?: number;
  /** 0..1 büyüme animasyonu (elevationScale çarpanı) */
  ilerleme?: number;
  /** hex: elevationScale (varsayılan 4); bolge: birim başına metre (varsayılan 0.06 → 37 bin HP ≈ 2,2 km) */
  yukseklikOlcegi?: number;
  /** hex renk aralığı (düşük → yüksek), varsayılan METRIK_PALETI */
  renkAraligi?: string[];
  /** bolge: vurgulanan bölgeler */
  vurguBolgeler?: number[] | null;
  pickable?: boolean;
}

/**
 * HP yoğunluğu sütunları: altıgen ızgara (HexagonLayer) ya da bölge başına tek sütun (ColumnLayer).
 */
export function hpSutunlari(o: HpSutunlariSecenekleri = {}): Layer {
  const { id = 'hp-sutun', olcu = 'res_hp', mod = 'hex', plan, ilerleme = 1, pickable = true, vurguBolgeler = null } = o;
  const b = veri().binalar;
  if (mod === 'bolge') {
    if (!plan) throw new Error('hpSutunlari: mod "bolge" için plan gerekli');
    const olcek = o.yukseklikOlcegi ?? 0.06;
    const vurgu = vurguBolgeler ? new Set(vurguBolgeler) : null;
    const deger = (d: Bolge) => (olcu === 'aktif' ? d.aktif_res : d[olcu]);
    return new ColumnLayer<Bolge>({
      id,
      data: plan.bolgeler,
      getPosition: (d) => bolgeEtiketNoktasi(d),
      getElevation: (d) => deger(d),
      elevationScale: olcek * ilerleme,
      radius: o.yaricap ?? 900,
      diskResolution: 48,
      extruded: true,
      getFillColor: (d) => (vurgu && !vurgu.has(d.bolge) ? karistir(hexRgba(d.renk), [8, 14, 28, 255], 0.75) : hexRgba(d.renk)),
      material: SUTUN_MALZEMESI,
      pickable,
      updateTriggers: { getFillColor: [planAnahtari(plan), vurguBolgeler?.join(',') ?? ''], getElevation: olcu },
    });
  }
  const f = binaMetrigi(olcu === 'aktif' ? 'aktif' : olcu);
  const renkler = (o.renkAraligi ?? METRIK_PALETI).map((h) => hexRgba(h) as Color);
  return new HexagonLayer<number>({
    id,
    data: b.indeksler,
    getPosition: (i) => [b.lon[i], b.lat[i]],
    getElevationWeight: (i) => f(i),
    getColorWeight: (i) => f(i),
    elevationAggregation: 'SUM',
    colorAggregation: 'SUM',
    radius: o.yaricap ?? 450,
    coverage: 0.86,
    extruded: true,
    elevationScale: (o.yukseklikOlcegi ?? 4) * ilerleme,
    colorRange: renkler,
    upperPercentile: 99.5,
    material: SUTUN_MALZEMESI,
    pickable,
    gpuAggregation: false,
    updateTriggers: { getElevationWeight: olcu, getColorWeight: olcu },
  });
}

/* ================================================================== ofis işaretçisi */

export interface OfisSecenekleri {
  id?: string;
  /** saniye cinsinden zaman (nabız halkaları); sabit görüntü için 0 */
  t?: number;
  /** ışık sütunu yüksekliği (m, varsayılan 2200) */
  yukseklik?: number;
  /** etiket metni; false = etiketsiz */
  etiket?: string | false;
  /** etiket boyutu px (varsayılan 30) */
  etiketBoyutu?: number;
  /** 0..1 ölçek (belirme animasyonu) */
  olcek?: number;
  renk?: RGBA;
  /** nabız halkası en büyük yarıçapı (m, varsayılan 1800) */
  halkaYaricapi?: number;
}

/**
 * Ofis (bayi merkezi) işaretçisi: ışık sütunu + hale + zeminde nabız halkaları + etiket.
 */
export function ofisIsaretcisi(o: OfisSecenekleri = {}): Layer[] {
  const {
    id = 'ofis',
    t = 0,
    yukseklik = 2200,
    etiket = 'DEHANET EÇM',
    etiketBoyutu = 30,
    olcek = 1,
    renk = [255, 196, 0, 255],
    halkaYaricapi = 1800,
  } = o;
  const of = veri().meta.ofis;
  const konum: LonLat = [of.lon, of.lat];
  const s = Math.max(0.0001, olcek);
  const HALKA = 3;
  const halkalar = Array.from({ length: HALKA }, (_, k) => {
    const faz = (((t / 2.4 + k / HALKA) % 1) + 1) % 1;
    return { r: (60 + halkaYaricapi * faz) * s, a: 230 * (1 - faz) * (1 - faz) };
  });
  const k: Layer[] = [
    new ScatterplotLayer<{ r: number; a: number }>({
      id: `${id}-zemin-hale`,
      data: [{ r: 420 * s, a: 70 }, { r: 160 * s, a: 150 }],
      getPosition: () => konum,
      getRadius: (d) => d.r,
      getFillColor: (d) => alfa(renk, d.a),
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getRadius: s },
    }),
    new ScatterplotLayer<{ r: number; a: number }>({
      id: `${id}-nabiz`,
      data: halkalar,
      getPosition: () => konum,
      getRadius: (d) => d.r,
      filled: false,
      stroked: true,
      getLineColor: (d) => alfa(renk, d.a),
      getLineWidth: 3,
      lineWidthUnits: 'pixels',
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getRadius: [t, s], getLineColor: t },
    }),
    new ColumnLayer<number>({
      id: `${id}-sutun-hale`,
      data: [0],
      getPosition: () => konum,
      radius: 70 * s,
      diskResolution: 24,
      extruded: true,
      getElevation: yukseklik * s,
      getFillColor: alfa(renk, 60),
      material: false,
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getElevation: s },
    }),
    new ColumnLayer<number>({
      id: `${id}-sutun`,
      data: [0],
      getPosition: () => konum,
      radius: 22 * s,
      diskResolution: 16,
      extruded: true,
      getElevation: yukseklik * s,
      getFillColor: tonla(renk, 0.35),
      material: false,
      updateTriggers: { getElevation: s },
    }),
  ];
  if (etiket)
    k.push(
      new TextLayer<number>({
        id: `${id}-etiket`,
        data: [0],
        getPosition: () => [konum[0], konum[1], yukseklik * s + 60],
        getText: () => etiket,
        getSize: etiketBoyutu,
        sizeUnits: 'pixels',
        getColor: [3, 6, 13, 255],
        ...HARITA_FONT,
        fontWeight: 800,
        outlineWidth: 0,
        background: true,
        getBackgroundColor: renk,
        backgroundPadding: [14, 6, 14, 4],
        backgroundBorderRadius: 6,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'bottom',
        getPixelOffset: [0, -8],
        parameters: USTTE_PARAMETRELERI,
        updateTriggers: { getPosition: s },
      }),
    );
  return k;
}

/* ================================================================== arklar (ofis → bölge merkezleri) */

type Nokta3 = [number, number, number];
const arkOnbellek = new Map<string, { bolge: Bolge; yol: Nokta3[]; zaman: number[] }[]>();

/** a→b arası 3B parabolik yay (z metre). */
export function arkYolu(a: LonLat, b: LonLat, yukseklikOrani = 0.22, adim = 64): Nokta3[] {
  const kx = 111320 * Math.cos((a[1] * Math.PI) / 180);
  const dx = (b[0] - a[0]) * kx;
  const dy = (b[1] - a[1]) * 110570;
  const h = Math.sqrt(dx * dx + dy * dy) * yukseklikOrani;
  const yol: Nokta3[] = [];
  for (let s = 0; s <= adim; s++) {
    const u = s / adim;
    yol.push([a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, 4 * h * u * (1 - u)]);
  }
  return yol;
}

function yolKirp(yol: Nokta3[], ilerleme: number): Nokta3[] {
  if (ilerleme >= 1) return yol;
  if (ilerleme <= 0) return [yol[0], yol[0]];
  const f = ilerleme * (yol.length - 1);
  const i = Math.floor(f);
  const r = f - i;
  const son = yol[i + 1] ?? yol[i];
  const p: Nokta3 = [0, 1, 2].map((k) => yol[i][k] + (son[k] - yol[i][k]) * r) as Nokta3;
  return [...yol.slice(0, i + 1), p];
}

export interface ArklarSecenekleri {
  plan: Plan;
  id?: string;
  /** yalnız bu bölgeler */
  bolgeler?: number[] | null;
  /** 0..1 çizilme animasyonu */
  ilerleme?: number;
  /** saniye; verilirse ark boyunca akan ışık (TripsLayer) çizilir */
  t?: number | null;
  /** çekirdek çizgi genişliği px (varsayılan 3) */
  genislik?: number;
  /** yay yüksekliği / mesafe (varsayılan 0.22) */
  yukseklikOrani?: number;
}

/** Ofisten bölge merkezlerine parlayan 3B yaylar (+ isteğe bağlı akan ışık). */
export function arklar(o: ArklarSecenekleri): Layer[] {
  const { plan, id = 'ark', bolgeler = null, ilerleme = 1, t = null, genislik = 3, yukseklikOrani = 0.22 } = o;
  const of = veri().meta.ofis;
  const anahtar = `${planAnahtari(plan)}:${yukseklikOrani}`;
  let tum = arkOnbellek.get(anahtar);
  if (!tum) {
    tum = plan.bolgeler.map((b) => {
      const yol = arkYolu([of.lon, of.lat], bolgeEtiketNoktasi(b), yukseklikOrani);
      return { bolge: b, yol, zaman: yol.map((_, i) => i / (yol.length - 1)) };
    });
    if (arkOnbellek.size > 16) arkOnbellek.clear();
    arkOnbellek.set(anahtar, tum);
  }
  const sec = bolgeler ? new Set(bolgeler) : null;
  const veriler = (sec ? tum.filter((d) => sec.has(d.bolge.bolge)) : tum).map((d) => ({
    ...d,
    kirpik: yolKirp(d.yol, ilerleme),
  }));
  type D = (typeof veriler)[number];
  const tetik = [anahtar, bolgeler?.join(',') ?? '', ilerleme];
  const k: Layer[] = [
    new PathLayer<D>({
      id: `${id}-hale`,
      data: veriler,
      getPath: (d) => d.kirpik as Position[],
      getColor: (d) => alfa(hexRgba(d.bolge.renk), 70),
      getWidth: genislik * 4,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      billboard: true,
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getPath: tetik, getColor: tetik },
    }),
    new PathLayer<D>({
      id: `${id}-cizgi`,
      data: veriler,
      getPath: (d) => d.kirpik as Position[],
      getColor: (d) => tonla(hexRgba(d.bolge.renk), 0.35),
      getWidth: genislik,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      billboard: true,
      updateTriggers: { getPath: tetik, getColor: tetik },
    }),
  ];
  if (t != null && ilerleme >= 1)
    k.push(
      new TripsLayer<D>({
        id: `${id}-akis`,
        data: veriler,
        getPath: (d) => d.yol as Position[],
        getTimestamps: (d) => d.zaman,
        getColor: [255, 255, 255, 255],
        currentTime: ((t / 1.8) % 1.35) - 0.1,
        trailLength: 0.28,
        fadeTrail: true,
        getWidth: genislik * 2.2,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
        billboard: true,
        parameters: TOPLAMSAL_KARISIM,
        updateTriggers: { getPath: tetik },
      }),
    );
  return k;
}

/** Yassı ArcLayer alternatifi (GPU yayı, animasyonsuz). */
export function arkKatmani(o: { plan: Plan; id?: string; genislik?: number; bolgeler?: number[] | null }): Layer {
  const of = veri().meta.ofis;
  const sec = o.bolgeler ? new Set(o.bolgeler) : null;
  return new ArcLayer<Bolge>({
    id: o.id ?? 'ark-gpu',
    data: sec ? o.plan.bolgeler.filter((b) => sec.has(b.bolge)) : o.plan.bolgeler,
    getSourcePosition: () => [of.lon, of.lat],
    getTargetPosition: (d) => bolgeEtiketNoktasi(d),
    getSourceColor: renkRgba.sari,
    getTargetColor: (d) => hexRgba(d.renk),
    getWidth: o.genislik ?? 4,
    getHeight: 0.6,
    widthUnits: 'pixels',
  });
}

/* ================================================================== etiketler */

export interface Etiket {
  konum: LonLat | [number, number, number];
  metin: string;
  renk?: RGBA;
  /** px */
  boyut?: number;
  arkaPlan?: RGBA;
  kenar?: RGBA;
}

export interface EtiketSecenekleri {
  id?: string;
  veri: Etiket[];
  /** varsayılan boyut px (32) */
  boyut?: number;
  renk?: RGBA;
  /** arka plan kutusu (varsayılan açık) */
  arkaPlan?: boolean;
  arkaPlanRengi?: RGBA;
  /** kutu kenar rengi (varsayılan yok) */
  kenarRengi?: RGBA;
  /** 'middle' | 'start' | 'end' */
  yatay?: 'start' | 'middle' | 'end';
  dikey?: 'top' | 'center' | 'bottom';
  /** piksel kaydırma [x, y] */
  kaydir?: [number, number];
  /** 0..1 opaklık */
  gorunurluk?: number;
  fontWeight?: number;
  /** hep üstte (varsayılan true) */
  ustte?: boolean;
}

/** Büyük, okunaklı harita etiketleri (yerel font, SDF kontur, isteğe bağlı kutu). */
export function etiketler(o: EtiketSecenekleri): Layer {
  const {
    id = 'etiket',
    veri: d,
    boyut = 32,
    renk = [244, 247, 255, 255],
    arkaPlan = true,
    arkaPlanRengi = [5, 10, 22, 215],
    kenarRengi,
    yatay = 'middle',
    dikey = 'center',
    kaydir = [0, 0],
    gorunurluk = 1,
    fontWeight = 700,
    ustte = true,
  } = o;
  return new TextLayer<Etiket>({
    id,
    data: d,
    getPosition: (e) => e.konum as Position,
    getText: (e) => e.metin,
    getColor: (e) => alfa(e.renk ?? renk, (e.renk ?? renk)[3] * gorunurluk),
    getSize: (e) => e.boyut ?? boyut,
    sizeUnits: 'pixels',
    ...HARITA_FONT,
    fontWeight,
    outlineWidth: arkaPlan ? 0 : 4,
    outlineColor: [3, 6, 13, 230],
    background: arkaPlan,
    getBackgroundColor: (e) => alfa(e.arkaPlan ?? arkaPlanRengi, (e.arkaPlan ?? arkaPlanRengi)[3] * gorunurluk),
    getBorderColor: (e) => alfa(e.kenar ?? kenarRengi ?? [0, 0, 0, 0], (e.kenar ?? kenarRengi ?? [0, 0, 0, 0])[3] * gorunurluk),
    getBorderWidth: kenarRengi ? 2 : 0,
    backgroundPadding: [14, 6, 14, 6],
    backgroundBorderRadius: 8,
    getTextAnchor: yatay,
    getAlignmentBaseline: dikey,
    getPixelOffset: kaydir,
    parameters: ustte ? USTTE_PARAMETRELERI : undefined,
    updateTriggers: { getColor: gorunurluk, getBackgroundColor: gorunurluk, getBorderColor: gorunurluk },
  });
}

export interface BolgeEtiketSecenekleri {
  plan: Plan;
  id?: string;
  /** 'kod' "B1" | 'kisa' "Dumlupınar" | 'kodKisa' "B1 · Dumlupınar" | 'tam' uzun ad */
  bicim?: 'kod' | 'kisa' | 'kodKisa' | 'tam';
  boyut?: number;
  /** etiket yüksekliği (m) — 3B sahnede binaların üstünde dursun */
  yukseklik?: number;
  bolgeler?: number[] | null;
  vurguBolgeler?: number[] | null;
  gorunurluk?: number;
}

/** Bölge merkezlerinde bölge rengi kenarlı etiketler. */
export function bolgeEtiketleri(o: BolgeEtiketSecenekleri): Layer {
  const { plan, id = 'bolge-etiket', bicim = 'kodKisa', boyut = 30, yukseklik = 0, bolgeler = null, vurguBolgeler = null } = o;
  const sec = bolgeler ? new Set(bolgeler) : null;
  const vurgu = vurguBolgeler ? new Set(vurguBolgeler) : null;
  const metin = (b: Bolge) =>
    bicim === 'kod' ? b.kod : bicim === 'kisa' ? b.kisa_ad : bicim === 'tam' ? b.ad : `${b.kod} · ${b.kisa_ad}`;
  return etiketler({
    id,
    boyut,
    gorunurluk: o.gorunurluk,
    veri: plan.bolgeler
      .filter((b) => !sec || sec.has(b.bolge))
      .map((b) => {
        const c = hexRgba(b.renk);
        const sonuk = vurgu && !vurgu.has(b.bolge);
        return {
          konum: [bolgeEtiketNoktasi(b)[0], bolgeEtiketNoktasi(b)[1], yukseklik] as [number, number, number],
          metin: metin(b),
          renk: sonuk ? ([150, 160, 180, 160] as RGBA) : ([255, 255, 255, 255] as RGBA),
          arkaPlan: sonuk ? ([5, 10, 22, 150] as RGBA) : (karistir([5, 10, 22, 230], c, 0.18) as RGBA),
          kenar: alfa(c, sonuk ? 90 : 255),
          boyut: vurgu?.has(b.bolge) ? boyut * 1.25 : boyut,
        };
      }),
    kenarRengi: [255, 255, 255, 255],
  });
}

/* ================================================================== çevrimiçi raster altlık (isteğe bağlı) */

export type KaroStili = 'dark_nolabels' | 'dark_all' | 'dark_only_labels';

/** CARTO koyu raster karolar — YALNIZ çevrimiçiyken; hata sessizce yutulur. Önce `karoErisimi()` ile deneyin. */
export function cartoKaroKatmani(o: { id?: string; stil?: KaroStili; opaklik?: number } = {}): Layer {
  const { id = 'carto', stil = 'dark_nolabels', opaklik = 1 } = o;
  return new TileLayer({
    id,
    data: ['a', 'b', 'c', 'd'].map((s) => `https://${s}.basemaps.cartocdn.com/${stil}/{z}/{x}/{y}@2x.png`),
    minZoom: 0,
    maxZoom: 19,
    tileSize: 256,
    opacity: opaklik,
    maxRequests: 12,
    onTileError: () => {},
    renderSubLayers: (props) => {
      const { boundingBox } = props.tile;
      return new BitmapLayer(props, {
        data: undefined,
        image: props.data as never,
        bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]],
        parameters: ZEMIN_PARAMETRELERI,
      });
    },
    parameters: ZEMIN_PARAMETRELERI,
  });
}

let _karoErisimi: Promise<boolean> | null = null;
/**
 * CARTO karolarına gerçekten erişilebiliyor mu (tek sefer denenir, ≤2,5 sn).
 *
 * `fetch(..., {mode:'no-cors'})` opak yanıt döndürür: captive portal / HTML hata sayfası da
 * "başarılı" görünür. Bunun yerine tek bir karo `Image()` ile yüklenir ve `naturalWidth > 0`
 * aranır — yalnız gerçek bir PNG çözüldüyse true döner. Çevrimdışı çalışma varsayılandır;
 * karolar yalnız OSM altlığının ALTINA eklenir, onun yerine değil.
 */
export function karoErisimi(): Promise<boolean> {
  if (_karoErisimi) return _karoErisimi;
  _karoErisimi = new Promise<boolean>((coz) => {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return coz(false);
    if (typeof Image === 'undefined') return coz(false);
    const img = new Image();
    let bitti = false;
    const son = (v: boolean) => {
      if (bitti) return;
      bitti = true;
      clearTimeout(zaman);
      img.onload = img.onerror = null;
      img.src = '';
      coz(v);
    };
    const zaman = setTimeout(() => son(false), 2500);
    img.crossOrigin = 'anonymous';
    img.onload = () => son(img.naturalWidth > 0);
    img.onerror = () => son(false);
    img.src = 'https://a.basemaps.cartocdn.com/dark_nolabels/10/573/388.png?d=' + Date.now();
  });
  return _karoErisimi;
}

/* ================================================================== toplu yardımcı */

/** Katman listesinden boş/false öğeleri ayıklar. */
export function katmanlar(...parcalar: (Layer | Layer[] | null | undefined | false)[]): LayersList {
  const out: Layer[] = [];
  for (const p of parcalar) {
    if (!p) continue;
    if (Array.isArray(p)) out.push(...p);
    else out.push(p);
  }
  return out;
}
