/**
 * Veri yükleme ve çözme.
 *
 * JSON dosyaları derlemeye ?raw ile gömülür (TS büyük JSON'dan tip çıkarmasın diye) ve
 * ilk `veri()` çağrısında BİR KEZ JSON.parse edilir. Bina taban poligonları deck.gl'e
 * doğrudan verilebilen ikili (binary) dizilere çözülür.
 *
 * Planlar: paketteki planlar (N = 2…50) + çalışma anında "Plan Aç…" ile yüklenen dış planlar
 * (aynı N'deki paket planını geçersiz kılar). Değişiklikler `planDinle` ile izlenir.
 */
import binalarHam from './generated/binalar.json?raw';
import planlarHam from './generated/planlar.json?raw';
import metaHam from './generated/meta.json?raw';
import altlikHam from './generated/altlik.json?raw';

import type {
  Altlik,
  BinalarPaketi,
  Bolge,
  GeoGeometri,
  LonLat,
  Meta,
  Plan,
  PlanlarPaketi,
} from './types';

/* ================================================================== çözülmüş yapılar */

/** deck.gl SolidPolygonLayer/PolygonLayer için ikili taban verisi (binary data). */
export interface TabanIkili {
  /** poligon (bina) sayısı */
  length: number;
  /** i. poligonun ilk köşesinin indeksi (uzunluk n + 1; son eleman = toplam köşe) */
  startIndices: Uint32Array;
  attributes: {
    /** [lon, lat, lon, lat, …] — halkalar kapalı, saat yönünde (CW) */
    getPolygon: { value: Float64Array; size: 2 };
  };
}

export interface BinaVerisi {
  n: number;
  /** ham sütunlar (sozluk, serial vb. için) */
  paket: BinalarPaketi;
  /** [lon0, lat0, lon1, lat1, …] */
  konum: Float64Array;
  lon: Float64Array;
  lat: Float64Array;
  kat: Uint8Array;
  /** metre cinsinden yükseklik = max(kat, 1) × KAT_YUKSEKLIGI_M */
  yukseklik: Float32Array;
  toplamHp: Uint32Array;
  resHp: Uint32Array;
  aktif: Uint32Array;
  firsat: Uint32Array;
  /** site-grup indeksi → plan.birim_bolge */
  birim: Uint32Array;
  ilce: Uint16Array;
  mahalle: Uint16Array;
  il: Uint8Array;
  /** Yalova binası mı (1/0) */
  yalova: Uint8Array;
  /** ofise kuş uçuşu uzaklık (km) — "ofisten yayılma" animasyonları için */
  ofisMesafeKm: Float32Array;
  /** 0..n-1 — HexagonLayer / ScatterplotLayer gibi nesne dizisi isteyen katmanlar için */
  indeksler: number[];
  /** taban poligonları (deck.gl ikili biçim) */
  taban: TabanIkili;
}

export interface YolParcasi {
  yol: LonLat[];
  /** önem 1..4 */
  s: number;
}

export interface IlceAlani {
  ad: string;
  /** Polygon halkaları dizisi (MultiPolygon parçalara ayrılır) */
  poligon: LonLat[][];
}

export interface IlceEtiketi {
  ad: string;
  konum: LonLat;
  /** binası olan ilçe mi (etiket vurgusu için) */
  aktif: boolean;
}

export interface AltlikVerisi {
  attribution: string;
  yollar: YolParcasi[];
  kiyi: LonLat[][];
  goller: LonLat[][][];
  ilceAlanlari: IlceAlani[];
  /** ilçe sınır çizgileri (dış halkalar) */
  ilceSinirlari: { ad: string; yol: LonLat[] }[];
  ilceEtiketleri: IlceEtiketi[];
}

export interface Veri {
  binalar: BinaVerisi;
  meta: Meta;
  altlik: AltlikVerisi;
  planPaketi: PlanlarPaketi;
}

/** kat başına yükseklik (m) */
export const KAT_YUKSEKLIGI_M = 3;

/* ================================================================== çözücüler */

function binalariCoz(p: BinalarPaketi, ofis: { lon: number; lat: number }): BinaVerisi {
  const n = p.n;
  const konum = new Float64Array(n * 2);
  const lon = Float64Array.from(p.lon);
  const lat = Float64Array.from(p.lat);
  const kat = new Uint8Array(n);
  const yukseklik = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    konum[2 * i] = lon[i];
    konum[2 * i + 1] = lat[i];
    const k = Math.max(1, Math.min(255, p.kat[i] | 0));
    kat[i] = k;
    yukseklik[i] = k * KAT_YUKSEKLIGI_M;
  }
  const ilSozluk = p.sozluk.il;
  const yalovaIl = ilSozluk.indexOf('Yalova');
  const il = Uint8Array.from(p.il);
  const yalova = new Uint8Array(n);
  if (yalovaIl >= 0) for (let i = 0; i < n; i++) yalova[i] = il[i] === yalovaIl ? 1 : 0;
  // eşdikdörtgen yaklaşımı (bu ölçekte hata < %0,1)
  const ofisMesafeKm = new Float32Array(n);
  const kx = 111.32 * Math.cos((ofis.lat * Math.PI) / 180);
  for (let i = 0; i < n; i++) {
    const dx = (lon[i] - ofis.lon) * kx;
    const dy = (lat[i] - ofis.lat) * 110.57;
    ofisMesafeKm[i] = Math.sqrt(dx * dx + dy * dy);
  }

  return {
    n,
    paket: p,
    konum,
    lon,
    lat,
    kat,
    yukseklik,
    toplamHp: Uint32Array.from(p.toplam_hp),
    resHp: Uint32Array.from(p.res_hp),
    aktif: Uint32Array.from(p.aktif),
    firsat: Uint32Array.from(p.firsat),
    birim: Uint32Array.from(p.birim),
    ilce: Uint16Array.from(p.ilce),
    mahalle: Uint16Array.from(p.mahalle),
    il,
    yalova,
    ofisMesafeKm,
    indeksler: Array.from({ length: n }, (_, i) => i),
    taban: tabanCoz(p, lon, lat),
  };
}

/** Taban poligonlarını mutlak lon/lat ikili dizisine çözer; poligonu olmayan binaya küçük kare üretir. */
function tabanCoz(p: BinalarPaketi, lon: Float64Array, lat: Float64Array): TabanIkili {
  const { fark, ofs, olcek } = p.poligon;
  const n = p.n;
  // Poligonsuz binalar için 5 köşeli (kapalı) kare: ~8 m
  const KARE = 0.00005;
  let toplam = 0;
  for (let i = 0; i < n; i++) {
    const c = ofs[i + 1] - ofs[i];
    toplam += c >= 4 ? c : 5;
  }
  const deger = new Float64Array(toplam * 2);
  const baslangic = new Uint32Array(n + 1);
  let v = 0;
  for (let i = 0; i < n; i++) {
    baslangic[i] = v;
    const a = ofs[i];
    const b = ofs[i + 1];
    if (b - a >= 4) {
      for (let q = a; q < b; q++) {
        deger[2 * v] = lon[i] + fark[2 * q] * olcek;
        deger[2 * v + 1] = lat[i] + fark[2 * q + 1] * olcek;
        v++;
      }
    } else {
      // saat yönünde kapalı kare
      const kx = [-1, -1, 1, 1, -1];
      const ky = [-1, 1, 1, -1, -1];
      for (let k = 0; k < 5; k++) {
        deger[2 * v] = lon[i] + kx[k] * KARE;
        deger[2 * v + 1] = lat[i] + ky[k] * KARE * 0.76;
        v++;
      }
    }
  }
  baslangic[n] = v;
  return { length: n, startIndices: baslangic, attributes: { getPolygon: { value: deger, size: 2 } } };
}

function halkaAlani(h: LonLat[]): number {
  let s = 0;
  for (let i = 0, j = h.length - 1; i < h.length; j = i++) s += (h[j][0] + h[i][0]) * (h[j][1] - h[i][1]);
  return s / 2;
}

function halkaAgirlikMerkezi(h: LonLat[]): LonLat {
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = h.length - 1; i < h.length; j = i++) {
    const f = h[j][0] * h[i][1] - h[i][0] * h[j][1];
    a += f;
    cx += (h[j][0] + h[i][0]) * f;
    cy += (h[j][1] + h[i][1]) * f;
  }
  if (Math.abs(a) < 1e-12) return h[0];
  return [cx / (3 * a), cy / (3 * a)];
}

/** Polygon | MultiPolygon → Polygon (halka listesi) listesi */
export function poligonParcalari(g: GeoGeometri | undefined | null): LonLat[][][] {
  if (!g) return [];
  if (g.type === 'Polygon') return [g.coordinates];
  if (g.type === 'MultiPolygon') return g.coordinates;
  return [];
}

/** LineString | MultiLineString → yol listesi */
export function cizgiParcalari(g: GeoGeometri | undefined | null): LonLat[][] {
  if (!g) return [];
  if (g.type === 'LineString') return [g.coordinates];
  if (g.type === 'MultiLineString') return g.coordinates;
  return [];
}

function altligiCoz(a: Altlik, meta: Meta): AltlikVerisi {
  const yollar: YolParcasi[] = [];
  for (const f of a.yollar.features) {
    for (const yol of cizgiParcalari(f.geometry)) yollar.push({ yol, s: f.properties.s ?? 4 });
  }
  // önemsizden önemliye çiz (önemli yollar üstte kalsın)
  yollar.sort((x, y) => y.s - x.s);

  const kiyi: LonLat[][] = [];
  const goller: LonLat[][][] = [];
  for (const f of a.su.features) {
    if (f.properties.tur === 'kiyi') kiyi.push(...cizgiParcalari(f.geometry));
    else goller.push(...poligonParcalari(f.geometry));
  }

  const binaliIlceler = new Set(meta.ilceler.map((x) => x.ilce));
  const ilceMerkezi = new Map(meta.ilceler.map((x) => [x.ilce, [x.lon, x.lat] as LonLat]));
  const ilceAlanlari: IlceAlani[] = [];
  const ilceSinirlari: { ad: string; yol: LonLat[] }[] = [];
  const ilceEtiketleri: IlceEtiketi[] = [];
  for (const f of a.ilce.features) {
    const ad = f.properties.ad;
    const parcalar = poligonParcalari(f.geometry);
    let enBuyuk: LonLat[] | null = null;
    let enBuyukAlan = 0;
    for (const p of parcalar) {
      ilceAlanlari.push({ ad, poligon: p });
      if (p[0]) {
        ilceSinirlari.push({ ad, yol: p[0] });
        const alan = Math.abs(halkaAlani(p[0]));
        if (alan > enBuyukAlan) {
          enBuyukAlan = alan;
          enBuyuk = p[0];
        }
      }
    }
    if (!enBuyuk) continue;
    // Binası olan ilçelerde etiket bina yoğunluğunun merkezine; diğerlerinde alan ağırlık merkezine
    const aktif = binaliIlceler.has(ad);
    const konum = (aktif && ilceMerkezi.get(ad)) || halkaAgirlikMerkezi(enBuyuk);
    ilceEtiketleri.push({ ad: ad === 'Yalova Merkez' ? 'Yalova' : ad, konum, aktif });
  }
  return { attribution: a.attribution, yollar, kiyi, goller, ilceAlanlari, ilceSinirlari, ilceEtiketleri };
}

/* ================================================================== tekil veri */

let _veri: Veri | null = null;

/**
 * Tüm veriyi döndürür (ilk çağrıda ayrıştırır, ~100-300 ms). Sonraki çağrılar önbellekten.
 * Uygulama açılışında main.tsx bir kez çağırır; bileşenler serbestçe çağırabilir.
 */
export function veri(): Veri {
  if (_veri) return _veri;
  const t0 = performance.now();
  const meta = JSON.parse(metaHam) as Meta;
  const binalar = binalariCoz(JSON.parse(binalarHam) as BinalarPaketi, meta.ofis);
  const planPaketi = JSON.parse(planlarHam) as PlanlarPaketi;
  const altlik = altligiCoz(JSON.parse(altlikHam) as Altlik, meta);
  _veri = { binalar, meta, altlik, planPaketi };
  if (import.meta.env.DEV) console.info(`[veri] ${Math.round(performance.now() - t0)} ms`);
  return _veri;
}

/* ================================================================== planlar */

const harici = new Map<number, Plan>();
let _planSurumu = 0;
const dinleyiciler = new Set<() => void>();

/** Varsayılan plan N'i (8). */
export function varsayilanN(): number {
  return veri().planPaketi.varsayilan;
}

/** Mevcut plan N'leri (artan). */
export function planNleri(): number[] {
  const s = new Set<number>(Object.keys(veri().planPaketi.planlar).map(Number));
  for (const k of harici.keys()) s.add(k);
  return [...s].sort((a, b) => a - b);
}

/** N bölgeli plan (dış yüklenen plan varsa o). Yoksa undefined. */
export function planGetir(n: number): Plan | undefined {
  return harici.get(n) ?? veri().planPaketi.planlar[String(n)];
}

/** planGetir; bulunamazsa varsayılan plan. */
export function planVeyaVarsayilan(n: number | null | undefined): Plan {
  return (n != null && planGetir(n)) || planGetir(varsayilanN())!;
}

/** Plan N'ine ait dış yükleme var mı */
export function planHariciMi(n: number): boolean {
  return harici.has(n);
}

/** Dış planlar her eklendiğinde artan sayaç (updateTriggers / useMemo bağımlılığı için). */
export function planSurumu(): number {
  return _planSurumu;
}

/** Plan değişikliklerini dinle; dönüş: aboneliği iptal eden fonksiyon. */
export function planDinle(cb: () => void): () => void {
  dinleyiciler.add(cb);
  return () => dinleyiciler.delete(cb);
}

export type PlanEklemeSonucu = { tamam: true; plan: Plan } | { tamam: false; hata: string };

/**
 * Dışarıdan (plan_N*.json) gelen planı doğrular ve kaydeder.
 * Aynı N'deki paket planını geçersiz kılar.
 */
export function planEkle(ham: unknown): PlanEklemeSonucu {
  const p = ham as Partial<Plan> | null;
  const birimSayisi = veri().planPaketi.birim_sayisi;
  if (!p || typeof p !== 'object') return { tamam: false, hata: 'Dosya bir plan içermiyor.' };
  if (typeof p.n !== 'number' || p.n < 1) return { tamam: false, hata: 'Planda bölge sayısı (n) yok.' };
  if (!Array.isArray(p.birim_bolge) || p.birim_bolge.length !== birimSayisi)
    return {
      tamam: false,
      hata: `Plan bu veri paketiyle uyumsuz (birim sayısı ${p.birim_bolge?.length ?? 0}, beklenen ${birimSayisi}).`,
    };
  if (!Array.isArray(p.bolgeler) || p.bolgeler.length === 0)
    return { tamam: false, hata: 'Planda bölge özetleri yok.' };
  const plan: Plan = {
    ...(p as Plan),
    olcu: p.olcu ?? 'res_hp',
    hedef: p.hedef ?? 0,
    sapma_min: p.sapma_min ?? 0,
    sapma_maks: p.sapma_maks ?? 0,
    bolgeler: (p.bolgeler as Bolge[]).filter((b) => !b.bos),
  };
  harici.set(plan.n, plan);
  _planSurumu++;
  for (const cb of dinleyiciler) cb();
  return { tamam: true, plan };
}

/* ================================================================== bina → bölge */

const bolgeOnbellek = new WeakMap<Plan, Uint8Array>();

/**
 * Plana göre her binanın bölge numarası (1..N; 0 = atanmamış).
 * binaBolgeleri(plan)[i] — birim → birim_bolge üzerinden. Plan nesnesi başına önbellekli.
 */
export function binaBolgeleri(plan: Plan): Uint8Array {
  let d = bolgeOnbellek.get(plan);
  if (d) return d;
  const { birim, n } = veri().binalar;
  const bb = plan.birim_bolge;
  d = new Uint8Array(n);
  for (let i = 0; i < n; i++) d[i] = bb[birim[i]] ?? 0;
  bolgeOnbellek.set(plan, d);
  return d;
}

/** Kısayol: N'li planın bina→bölge dizisi. */
export function buildingRegion(nPlan: number): Uint8Array {
  return binaBolgeleri(planVeyaVarsayilan(nPlan));
}

/* ================================================================== anlık (algoritma ara adımları) */

const anlikOnbellek = new Map<string, Uint8Array>();

/**
 * `plan.anlik_etiket[s]` dizesini bina→bölge dizisine çözer (birim üzerinden).
 * Eski veri paketlerinde `anlik_etiket` yoktur; o durumda `anlikVar(plan)` false döner.
 * Sonuç dize başına önbelleklenir (LRU 32).
 */
export function anlikBinaBolgeleri(dizi: string): Uint8Array {
  let d = anlikOnbellek.get(dizi);
  if (d) return d;
  const { birim, n } = veri().binalar;
  d = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const c = dizi.charCodeAt(birim[i]);
    d[i] = Number.isNaN(c) ? 0 : c - 48;
  }
  if (anlikOnbellek.size > 32) anlikOnbellek.clear();
  anlikOnbellek.set(dizi, d);
  return d;
}

/** Planda gerçek anlık etiketleri var mı (CCPD-2.5+). */
export function anlikEtiketVar(plan: Plan | null | undefined): boolean {
  const a = plan?.anlik_etiket;
  return Array.isArray(a) && a.length > 0 && typeof a[0] === 'string' && a[0].length > 0;
}

/** Bölgenin etiket noktası: `etiket` varsa o, yoksa ağırlık merkezi. Tüm etiket/pin/çağrılar bunu kullanır. */
export function bolgeEtiketNoktasi(b: Bolge): LonLat {
  return b.etiket ?? b.merkez;
}

/* ================================================================== bölge geometrileri */

export interface BolgeHalkasi {
  bolge: number;
  renk: string;
  yol: LonLat[];
}
export interface BolgeAlani {
  bolge: number;
  renk: string;
  /** halkalar: [dış, delik1, …] */
  poligon: LonLat[][];
}

const halkaOnbellek = new WeakMap<Plan, BolgeHalkasi[]>();
const alanOnbellek = new WeakMap<Plan, BolgeAlani[]>();

/** Bölge sınır çizgileri (tüm dış + iç halkalar) — PathLayer verisi. */
export function bolgeHalkalari(plan: Plan): BolgeHalkasi[] {
  let d = halkaOnbellek.get(plan);
  if (d) return d;
  d = [];
  for (const b of plan.bolgeler) {
    for (const p of poligonParcalari(b.poligon)) for (const h of p) d.push({ bolge: b.bolge, renk: b.renk, yol: h });
  }
  halkaOnbellek.set(plan, d);
  return d;
}

/** Bölge alanları (MultiPolygon parçalara ayrılmış) — SolidPolygonLayer verisi. */
export function bolgeAlanlari(plan: Plan): BolgeAlani[] {
  let d = alanOnbellek.get(plan);
  if (d) return d;
  d = [];
  for (const b of plan.bolgeler) {
    for (const p of poligonParcalari(b.poligon)) d.push({ bolge: b.bolge, renk: b.renk, poligon: p });
  }
  alanOnbellek.set(plan, d);
  return d;
}
