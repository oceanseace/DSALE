/**
 * Sunuma özel küçük yardımcılar: yumuşatma eğrileri, zaman aralığı eşlemesi ve
 * katman fabrikasında bulunmayan üç minik katman (nabız halkaları, serbest yay, pin).
 */
import type { Layer } from '@deck.gl/core';
import { ColumnLayer, PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';

import type { HaritaApi } from '../../map/HaritaSahnesi';
import type { KameraDurumu } from '../../map/kamera';
import { HARITA_FONT } from '../../map/fontlar';
import { TOPLAMSAL_KARISIM, arkYolu } from '../../map/katmanlar';
import type { RGBA } from '../../data/selectors';
import type { LonLat, Meta } from '../../data/types';
import type { CagriNoktasi } from '../bilesen/Cagrilar';

/* ================================================================== ofis çağrısı */

/**
 * Ofis fenerinin HTML çağrı balonu.
 *
 * Geniş kadrajlarda (S5, S9, S10) sarı "DEHANET EÇM" rozeti deck.gl TextLayer'ıyla çiziliyordu ve
 * bölge iğneleriyle üst üste biniyordu — kapanış karesinde beş iğne ve rozet tek bir lekeydi.
 * Artık ofis de bölge çipleriyle AYNI çakışma çözücüye girer ve `sabit` olduğu için yerini korur;
 * bölge çipleri ona göre kaçar. O sahnelerde `ofisIsaretcisi({ etiket: false })` kullanılır.
 */
export function ofisCagrisi(meta: Meta, o: { sap?: number } = {}): CagriNoktasi {
  return {
    anahtar: 'ofis',
    konum: [meta.ofis.lon, meta.ofis.lat],
    baslik: 'DEHANET EÇM',
    renk: '#FFC400',
    sabit: true,
    kucuk: true,
    sap: o.sap ?? 86,
  };
}

/* ================================================================== eğriler */

export function sinir(x: number, alt = 0, ust = 1): number {
  return x < alt ? alt : x > ust ? ust : x;
}

/** t ∈ [bas, bit] → 0..1 (dışarıda kırpılır) */
export function oran(t: number, bas: number, bit: number): number {
  if (bit <= bas) return t >= bit ? 1 : 0;
  return sinir((t - bas) / (bit - bas));
}

/** yavaşlayarak biten eğri (easeOutCubic) */
export function kolay(t: number): number {
  const x = sinir(t);
  return 1 - Math.pow(1 - x, 3);
}

/** hızlanıp yavaşlayan eğri (easeInOutCubic) */
export function kolayCift(t: number): number {
  const x = sinir(t);
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

/** doğrusal ara değer */
export function ara(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/* ================================================================== eğik sığdırma */

export interface SigdirSecenekleri {
  padding?: number | { top: number; bottom: number; left: number; right: number };
  pitch?: number;
  bearing?: number;
  maksZoom?: number;
  /** ek yakınlaştırma; verilmezse eğimden türetilir */
  ek?: number;
  /** merkezi ekran "aşağısına" kaydırma oranı (kutu yüksekliğinin katı); verilmezse eğimden türetilir */
  kaydir?: number;
  /**
   * Bearing telafisi: `fitBounds` döndürmeyi hesaba katmaz, döndürülmüş kutu ekranda daha
   * geniş yer kaplar. true ise dönme büyümesi kadar uzaklaşılır (kadrajı sabit tutmak
   * gereken sahneler — ör. yanında kart olan bölge turu — için).
   */
  donme?: boolean;
}

/**
 * Eğik (pitch'li) görünüm için sınır kutusuna sığdırma.
 *
 * `fitBounds` kuşbakışı hesaplanır. Eğim eklendiğinde zemin ufka doğru sıkışır: kutunun
 * kameraya yakın (ekranda alt) yarısı BÜYÜR ve alttan taşar, uzak yarısı küçülür. Bu yüzden
 *   1. eğimle artan görüş alanı için bir miktar yakınlaştırma (`ek`) eklenir,
 *   2. kamera merkezi bakış yönünün TERSİNE kaydırılır (kutu ekranda yukarı çıkar).
 * İkisi de tan(pitch) ile ölçeklenir; sahneler gerekirse elle verebilir.
 */
export function sigdirEgik(api: HaritaApi, kutu: [LonLat, LonLat], o: SigdirSecenekleri = {}): KameraDurumu {
  const pitch = o.pitch ?? 0;
  const bearing = o.bearing ?? 0;
  const k = api.sigdirHesapla(kutu, { padding: o.padding, pitch: 0, bearing, maksZoom: o.maksZoom });
  const egim = Math.tan((pitch * Math.PI) / 180);
  let ek = o.ek ?? egim * 0.30;
  const kaydir = o.kaydir ?? egim * 0.20;
  if (o.donme && bearing % 180 !== 0) {
    const ortaEnlem = (kutu[0][1] + kutu[1][1]) / 2;
    const g = Math.max(1e-9, Math.abs(kutu[1][0] - kutu[0][0]) * Math.cos((ortaEnlem * Math.PI) / 180));
    const y = Math.max(1e-9, Math.abs(kutu[1][1] - kutu[0][1]));
    const br = (Math.abs(bearing) * Math.PI) / 180;
    const c = Math.abs(Math.cos(br));
    const sn = Math.abs(Math.sin(br));
    ek -= Math.log2(Math.max((g * c + y * sn) / g, (g * sn + y * c) / y));
  }
  const dLat = Math.abs(kutu[1][1] - kutu[0][1]) || 0.01;
  const aci = ((bearing + 180) * Math.PI) / 180;
  const enlem = k.latitude + Math.cos(aci) * dLat * kaydir;
  const boylamOlcek = Math.max(0.2, Math.cos((k.latitude * Math.PI) / 180));
  return {
    longitude: k.longitude + (Math.sin(aci) * dLat * kaydir) / boylamOlcek,
    latitude: enlem,
    zoom: k.zoom + ek,
    pitch,
    bearing,
  };
}

/* ================================================================== nabız halkaları */

export interface NabizSecenekleri {
  id: string;
  konum: LonLat;
  /** saniye */
  t: number;
  renk: RGBA;
  /** en büyük yarıçap (m) */
  maksYaricap?: number;
  halkaSayisi?: number;
  /** bir halkanın tur süresi (sn) */
  periyot?: number;
  genislik?: number;
}

/** Bir noktadan yayılan nabız halkaları (ofis dışındaki vurgular için). */
export function nabizHalkalari(o: NabizSecenekleri): Layer {
  const { id, konum, t, renk, maksYaricap = 1400, halkaSayisi = 3, periyot = 2.6, genislik = 3 } = o;
  const veri = Array.from({ length: halkaSayisi }, (_, k) => {
    const faz = (((t / periyot + k / halkaSayisi) % 1) + 1) % 1;
    return { r: 60 + maksYaricap * faz, a: 235 * (1 - faz) * (1 - faz) };
  });
  return new ScatterplotLayer<{ r: number; a: number }>({
    id,
    data: veri,
    getPosition: () => konum,
    getRadius: (d) => d.r,
    filled: false,
    stroked: true,
    getLineColor: (d) => [renk[0], renk[1], renk[2], d.a],
    getLineWidth: genislik,
    lineWidthUnits: 'pixels',
    parameters: TOPLAMSAL_KARISIM,
    updateTriggers: { getRadius: t, getLineColor: t },
  });
}

/* ================================================================== serbest yay */

type Nokta3 = [number, number, number];

function yolKirp(yol: Nokta3[], ilerleme: number): Nokta3[] {
  if (ilerleme >= 1) return yol;
  if (ilerleme <= 0) return [yol[0], yol[0]];
  const f = ilerleme * (yol.length - 1);
  const i = Math.floor(f);
  const r = f - i;
  const son = yol[i + 1] ?? yol[i];
  const p = [0, 1, 2].map((k) => yol[i][k] + (son[k] - yol[i][k]) * r) as Nokta3;
  return [...yol.slice(0, i + 1), p];
}

export interface OzelArkSecenekleri {
  id: string;
  a: LonLat;
  b: LonLat;
  renk: RGBA;
  /** 0..1 çizilme animasyonu */
  ilerleme?: number;
  genislik?: number;
  yukseklikOrani?: number;
  /** 0..1 genel görünürlük (sahne sonunda söndürmek için) */
  gorunurluk?: number;
}

/** İki nokta arasında parlayan 3B yay (ofis → Yalova gibi plan dışı hedefler için). */
export function ozelArk(o: OzelArkSecenekleri): Layer[] {
  const { id, a, b, renk, ilerleme = 1, genislik = 3, yukseklikOrani = 0.26, gorunurluk = 1 } = o;
  const g = sinir(gorunurluk);
  if (g <= 0.01) return [];
  const yol = yolKirp(arkYolu(a, b, yukseklikOrani) as Nokta3[], ilerleme);
  const veri = [{ yol }];
  return [
    new PathLayer<{ yol: Nokta3[] }>({
      id: `${id}-hale`,
      data: veri,
      getPath: (d) => d.yol,
      getColor: [renk[0], renk[1], renk[2], 80 * g],
      getWidth: genislik * 4,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      billboard: true,
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getPath: ilerleme, getColor: g },
    }),
    new PathLayer<{ yol: Nokta3[] }>({
      id: `${id}-cizgi`,
      data: veri,
      getPath: (d) => d.yol,
      getColor: [255, 255, 255, 235 * g],
      getWidth: genislik,
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      billboard: true,
      updateTriggers: { getPath: ilerleme, getColor: g },
    }),
  ];
}

/* ================================================================== pinler */

export interface Pin {
  konum: LonLat;
  metin: string;
  renk: RGBA;
}

export interface PinSecenekleri {
  id: string;
  pinler: Pin[];
  /** direk yüksekliği (m) */
  yukseklik?: number;
  /** 0..1 düşme animasyonu (1 = yerinde) */
  ilerleme?: number;
  etiketBoyutu?: number;
  /** etiket gösterilsin mi */
  etiket?: boolean;
  /** direk yarıçapı (m) — yakın planda inceltilir */
  direkYaricapi?: number;
}

/**
 * Yere saplanan ışık direği + parlayan baş + etiket.
 * S4'te algoritmanın merkezlerini, S7'de Yalova'yı işaretler.
 */
export function pinler(o: PinSecenekleri): Layer[] {
  const { id, pinler: p, yukseklik = 2600, ilerleme = 1, etiketBoyutu = 26, etiket = true, direkYaricapi = 40 } = o;
  const h = yukseklik;
  // düşme: yukarıdan gelip yerine oturur
  const dus = 1 - kolay(ilerleme);
  const k: Layer[] = [
    new ColumnLayer<Pin>({
      id: `${id}-direk`,
      data: p,
      getPosition: (d) => d.konum,
      radius: direkYaricapi,
      diskResolution: 12,
      extruded: true,
      getElevation: h * sinir(ilerleme * 1.4),
      getFillColor: (d) => [d.renk[0], d.renk[1], d.renk[2], 150],
      material: false,
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getElevation: ilerleme, getFillColor: p.length },
    }),
    new ScatterplotLayer<Pin>({
      id: `${id}-bas`,
      data: p,
      getPosition: (d) => [d.konum[0], d.konum[1], h * (1 + dus * 1.2)],
      getRadius: 9,
      radiusUnits: 'pixels',
      radiusMinPixels: 5,
      getFillColor: (d) => [d.renk[0], d.renk[1], d.renk[2], 255],
      stroked: true,
      getLineColor: [255, 255, 255, 230],
      getLineWidth: 2,
      lineWidthUnits: 'pixels',
      parameters: TOPLAMSAL_KARISIM,
      updateTriggers: { getPosition: ilerleme, getFillColor: p.length },
    }),
  ];
  if (etiket)
    k.push(
      new TextLayer<Pin>({
        id: `${id}-etiket`,
        data: p,
        getPosition: (d) => [d.konum[0], d.konum[1], h * (1 + dus * 1.2)],
        getText: (d) => d.metin,
        getSize: etiketBoyutu,
        sizeUnits: 'pixels',
        getColor: [8, 12, 22, 255],
        ...HARITA_FONT,
        fontWeight: 800,
        outlineWidth: 0,
        background: true,
        getBackgroundColor: (d) => [d.renk[0], d.renk[1], d.renk[2], 240],
        backgroundPadding: [12, 5, 12, 4],
        backgroundBorderRadius: 6,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'bottom',
        getPixelOffset: [0, -16],
        parameters: { depthCompare: 'always', depthWriteEnabled: false },
        updateTriggers: { getPosition: ilerleme, getBackgroundColor: p.length },
      }),
    );
  return k;
}
