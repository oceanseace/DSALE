/**
 * 3B dijital ikiz — "Blackshark.ai gibi binaları simüle edip veriyle konuşturmak".
 *
 * Her bina gerçek taban çizgisiyle (OneMap poligonu) yerden kaldırılır:
 * yükseklik = kat × 3 m. Rengi seçilen MERCEKTEN gelir:
 *   Durum     — dokunuldu / bekliyor / tekrar gel (2B haritayla aynı renkler)
 *   Fırsat    — binadaki boş kapı sayısı
 *   Doluluk   — penetrasyon (aktif abone / konut)
 *   Açık iş emri — operasyon modülü bağlanınca dolacak (şimdilik boş)
 *
 * Hız: 19.706 binanın ~166 bin köşesi TEK bir Float64Array'dedir; renk ve
 * yükseklik dizin (index) ile okunur. Her karede hiçbir şey yeniden
 * hesaplanmaz — yalnız mercek, veri ya da seçim değişince renkler tazelenir
 * (`updateTriggers`). Taban çizgileri bir kez üçgenlenir.
 *
 * Sunucuda taban çizgisi yoksa (uç henüz kurulmamış / bağlantı yok) bina
 * yine görünür: konumuna küçük sekizgen bir "temsili" gövde konur ve ekranda
 * bunun temsili olduğu açıkça yazılır.
 */

import { SolidPolygonLayer } from '@deck.gl/layers';
import type { MapViewState, PickingInfo } from '@deck.gl/core';
import { WebMercatorViewport } from '@deck.gl/core';
import { useEffect, useMemo, useRef, useState } from 'react';
import { istek, SahaHatasi, SAHTE_IZIN, sahteMod } from '../api/istemci';
import { onbellegeYaz, onbellektenOku } from '../depo/db';
import type { BinaDurumu } from '../api/tipler';

export type Renk = [number, number, number, number];
export type Mercek = 'durum' | 'firsat' | 'doluluk' | 'is_emri';
export const MERCEKLER: readonly Mercek[] = ['durum', 'firsat', 'doluluk', 'is_emri'];
export const MERCEK_ADLARI: Record<Mercek, string> = {
  durum: 'Durum',
  firsat: 'Fırsat',
  doluluk: 'Doluluk',
  is_emri: 'Açık iş emri',
};

/** Haritadaki bir bina — iki haritanın ortak en küçük hâli. */
export interface IkizNoktasi {
  serial: string;
  konum: readonly [number, number];
  durum: BinaDurumu;
  firsat: number;
  ad?: string;
  loc?: string;
}

/* ------------------------------ Sunucu verisi ------------------------------ */

/**
 * `GET /api/binalar/geometri?bolge=` — taban çizgileri, sıkı dizilerle.
 * i. binanın köşeleri `ofs[i] … ofs[i+1]-1`; her köşe `fark` içinde
 * (dx, dy) çifti, bina konumuna göre milyonda bir derece.
 */
export interface GeometriYaniti {
  serial: string[];
  ofs: number[];
  fark: number[];
  kat: Array<number | null>;
  lat: number[];
  lon: number[];
  /** Farkların birimi (derece); yoksa 1e-6 (mikro-derece). */
  olcek?: number;
  /** Bir katın yüksekliği (m); yoksa 3. */
  kat_yuksekligi_m?: number;
  /** İsteğe bağlı: penetrasyon 0–1 (ölçülemiyorsa null) — "Doluluk" merceği. */
  pen?: Array<number | null>;
  /** İsteğe bağlı: binadaki açık iş emri sayısı — operasyon modülü. */
  acik_is?: number[];
}

export interface Geometri {
  yanit: GeometriYaniti;
  sira: Map<string, number>;
}

export type GeometriSonucu =
  | { tur: 'hazir'; geometri: Geometri }
  | { tur: 'yok' } // sunucuda uç yok (404) → temsili gövdeler
  | { tur: 'baglanti' }; // bağlantı yok ve kopya da yok → temsili gövdeler

const bellek = new Map<string, Promise<GeometriSonucu>>();

function gecerliMi(y: GeometriYaniti | null): y is GeometriYaniti {
  if (!y || !Array.isArray(y.serial) || !Array.isArray(y.ofs) || !Array.isArray(y.fark)) return false;
  const n = y.serial.length;
  return (
    Array.isArray(y.lat) &&
    Array.isArray(y.lon) &&
    y.lat.length === n &&
    y.lon.length === n &&
    y.ofs.length >= n &&
    y.fark.length % 2 === 0
  );
}

function dizinle(yanit: GeometriYaniti): Geometri {
  const sira = new Map<string, number>();
  yanit.serial.forEach((s, i) => sira.set(s, i));
  return { yanit, sira };
}

/**
 * Taban çizgilerini bir kez indirir; oturum boyunca bellekte kalır.
 * Satışçının bölgesi (~2.400 bina, ~250 kB) telefonda da saklanır: 3B
 * çevrimdışı da açılsın.
 */
export function geometriAl(bolge: number | null): Promise<GeometriSonucu> {
  const anahtar = bolge == null ? 'hepsi' : String(bolge);
  let soz = bellek.get(anahtar);
  if (soz) return soz;
  soz = (async (): Promise<GeometriSonucu> => {
    if (SAHTE_IZIN && sahteMod) return { tur: 'yok' };
    const onbellekAdi = `harita.geometri.${anahtar}`;
    try {
      const yanit = await istek<GeometriYaniti>(
        `/api/binalar/geometri${bolge == null ? '' : `?bolge=${bolge}`}`,
        { zamanAsimiMs: 60000 },
      );
      if (!gecerliMi(yanit)) return { tur: 'yok' };
      if (bolge != null) void onbellegeYaz(onbellekAdi, yanit);
      return { tur: 'hazir', geometri: dizinle(yanit) };
    } catch (h) {
      bellek.delete(anahtar); // sonra yeniden denensin
      if (h instanceof SahaHatasi && (h.durum === 404 || h.durum === 405)) return { tur: 'yok' };
      const saklanan = bolge != null ? await onbellektenOku<GeometriYaniti>(onbellekAdi) : null;
      if (gecerliMi(saklanan)) return { tur: 'hazir', geometri: dizinle(saklanan) };
      return { tur: 'baglanti' };
    }
  })();
  bellek.set(anahtar, soz);
  return soz;
}

/* ------------------------------ İkiz verisi ------------------------------ */

/**
 * deck.gl'in "ikili veri" biçimi: `length` + `startIndices` + köşe dizisi.
 * Geri kalan alanlar bizim: dizinden binaya giden yol.
 */
export interface IkizVerisi {
  length: number;
  startIndices: Uint32Array;
  attributes: { getPolygon: { value: Float64Array; size: 3 } };
  /** Dizin → çağıranın nokta listesindeki sırası. */
  kaynak: Int32Array;
  /** Metre. */
  yukseklik: Float32Array;
  /** Kat (0 = bilinmiyor). */
  kat: Int16Array;
  /** 0–1; ölçülemiyorsa NaN. */
  doluluk: Float32Array;
  dolulukVar: boolean;
  acikIs: Int16Array | null;
  /** Taban çizgisi olmadığı için temsili gövdeyle çizilen bina sayısı. */
  temsili: number;
}

const KAT_YUKSEKLIGI = 3; // m
const TEMSILI_YARICAP = 7; // m
const METRE_DERECE = 1 / 111320;

/**
 * Nokta listesinden 3B gövdeleri kurar. Veri değişmedikçe bir kez çalışır
 * (19.706 bina için ~20 ms); üçgenleme deck.gl'de, yine bir kez.
 */
export function ikizKur(noktalar: readonly IkizNoktasi[], sonuc: GeometriSonucu | null): IkizVerisi {
  const g = sonuc?.tur === 'hazir' ? sonuc.geometri : null;
  const y = g?.yanit;
  const n = noktalar.length;
  const gIndis = new Int32Array(n).fill(-1);

  // 1. geçiş: kaç köşe gerekecek?
  let toplam = 0;
  for (let i = 0; i < n; i++) {
    const gi = g ? (g.sira.get(noktalar[i].serial) ?? -1) : -1;
    let adet = 0;
    if (gi >= 0 && y) {
      const bas = y.ofs[gi];
      const son = gi + 1 < y.ofs.length ? y.ofs[gi + 1] : y.fark.length / 2;
      adet = son - bas;
    }
    if (adet >= 3) {
      gIndis[i] = gi;
      const bas = y!.ofs[gi];
      const kapali =
        y!.fark[2 * bas] === y!.fark[2 * (bas + adet - 1)] &&
        y!.fark[2 * bas + 1] === y!.fark[2 * (bas + adet - 1) + 1];
      toplam += kapali ? adet : adet + 1;
    } else {
      toplam += 9; // temsili sekizgen (kapalı halka)
    }
  }

  const konumlar = new Float64Array(toplam * 3);
  const baslangic = new Uint32Array(n + 1);
  const kaynak = new Int32Array(n);
  const yukseklik = new Float32Array(n);
  const katDizi = new Int16Array(n);
  const doluluk = new Float32Array(n).fill(NaN);
  const acikIs = y?.acik_is ? new Int16Array(n) : null;
  let temsili = 0;
  let dolulukVar = false;
  let k = 0;
  const olcek = y?.olcek && y.olcek > 0 && y.olcek < 1e-3 ? y.olcek : 1e-6;
  const katBoyu =
    y?.kat_yuksekligi_m && y.kat_yuksekligi_m > 1 && y.kat_yuksekligi_m < 6
      ? y.kat_yuksekligi_m
      : KAT_YUKSEKLIGI;

  // 2. geçiş: köşeleri yaz. Halka hep SAAT YÖNÜNDE yazılır (deck.gl'e
  // `_windingOrder: 'CW'` deniyor); duvarların ışığı buna göre hesaplanır.
  for (let i = 0; i < n; i++) {
    baslangic[i] = k;
    kaynak[i] = i;
    const gi = gIndis[i];
    let kat = 0;
    if (gi >= 0 && y) {
      const bas = y.ofs[gi];
      const son = gi + 1 < y.ofs.length ? y.ofs[gi + 1] : y.fark.length / 2;
      const lon0 = y.lon[gi];
      const lat0 = y.lat[gi];
      // İşaretli alan (>0 = saat yönünün tersi).
      let alan = 0;
      for (let p = bas; p < son; p++) {
        const q = p + 1 < son ? p + 1 : bas;
        alan += y.fark[2 * p] * y.fark[2 * q + 1] - y.fark[2 * q] * y.fark[2 * p + 1];
      }
      const ters = alan > 0;
      const adet = son - bas;
      for (let j = 0; j < adet; j++) {
        const p = ters ? son - 1 - j : bas + j;
        konumlar[k * 3] = lon0 + y.fark[2 * p] * olcek;
        konumlar[k * 3 + 1] = lat0 + y.fark[2 * p + 1] * olcek;
        k += 1;
      }
      const ilk = baslangic[i];
      const acik =
        konumlar[ilk * 3] !== konumlar[(k - 1) * 3] ||
        konumlar[ilk * 3 + 1] !== konumlar[(k - 1) * 3 + 1];
      if (acik) {
        konumlar[k * 3] = konumlar[ilk * 3];
        konumlar[k * 3 + 1] = konumlar[ilk * 3 + 1];
        k += 1;
      }
      kat = Number(y.kat?.[gi]) || 0;
      const pen = y.pen?.[gi];
      if (typeof pen === 'number' && Number.isFinite(pen)) {
        doluluk[i] = Math.max(0, Math.min(1, pen));
        dolulukVar = true;
      }
      if (acikIs) acikIs[i] = Math.max(0, Number(y.acik_is?.[gi]) || 0);
    } else {
      // Taban çizgisi yok: konumuna küçük sekizgen (temsili) gövde.
      temsili += 1;
      const [lon0, lat0] = noktalar[i].konum;
      const dLat = TEMSILI_YARICAP * METRE_DERECE;
      const dLon = dLat / Math.max(0.2, Math.cos((lat0 * Math.PI) / 180));
      for (let j = 0; j <= 8; j++) {
        const aci = (-j * Math.PI) / 4; // eksi: saat yönünde
        konumlar[k * 3] = lon0 + Math.cos(aci) * dLon;
        konumlar[k * 3 + 1] = lat0 + Math.sin(aci) * dLat;
        k += 1;
      }
    }
    katDizi[i] = Math.max(0, Math.min(99, Math.round(kat)));
    // Kat bilinmiyorsa 3 kat varsayılır: yere yapışık bir leke değil, bina görünsün.
    yukseklik[i] = (kat > 0 ? Math.min(kat, 60) : 3) * katBoyu;
  }
  baslangic[n] = k;

  return {
    length: n,
    startIndices: baslangic,
    attributes: { getPolygon: { value: konumlar.subarray(0, k * 3), size: 3 } },
    kaynak,
    yukseklik,
    kat: katDizi,
    doluluk,
    dolulukVar,
    acikIs,
    temsili,
  };
}

/* ------------------------------ Mercekler ------------------------------ */

export interface Sinif {
  etiket: string;
  renk: Renk;
}

const NOTR: Renk = [206, 212, 221, 255];

/** Sıralı tek renk (turuncu): açık → koyu = az → çok boş kapı. */
const FIRSAT_SINIFLARI: Sinif[] = [
  { etiket: 'Boş kapı yok', renk: NOTR },
  { etiket: '1–4', renk: [251, 217, 196, 255] },
  { etiket: '5–9', renk: [246, 173, 134, 255] },
  { etiket: '10–19', renk: [236, 124, 75, 255] },
  { etiket: '20–39', renk: [201, 83, 31, 255] },
  { etiket: '40+', renk: [143, 53, 16, 255] },
];

/** Sıralı tek renk (mavi): açık → koyu = boş → dolu. */
const DOLULUK_SINIFLARI: Sinif[] = [
  { etiket: 'Ölçülemiyor', renk: NOTR },
  { etiket: '%0–14', renk: [205, 226, 251, 255] },
  { etiket: '%15–29', renk: [158, 197, 244, 255] },
  { etiket: '%30–44', renk: [85, 152, 231, 255] },
  { etiket: '%45–59', renk: [37, 106, 191, 255] },
  { etiket: '%60+', renk: [16, 66, 129, 255] },
];

const IS_EMRI_SINIFLARI: Sinif[] = [
  { etiket: 'Açık iş yok', renk: NOTR },
  { etiket: '1 açık iş', renk: [240, 138, 138, 255] },
  { etiket: '2+ açık iş', renk: [192, 42, 42, 255] },
];

const DURUM_SIRASI: BinaDurumu[] = [
  'bekliyor',
  'ziyaret_edildi',
  'tekrar_gel',
  'girilemedi',
  'altyapi_sorunu',
  'planli',
];

export const SECILI_RENK: Renk = [11, 99, 229, 255];

function firsatSinifi(f: number) {
  if (!(f > 0)) return 0;
  if (f < 5) return 1;
  if (f < 10) return 2;
  if (f < 20) return 3;
  if (f < 40) return 4;
  return 5;
}

function dolulukSinifi(p: number) {
  if (Number.isNaN(p)) return 0;
  if (p < 0.15) return 1;
  if (p < 0.3) return 2;
  if (p < 0.45) return 3;
  if (p < 0.6) return 4;
  return 5;
}

export interface Boyama {
  /** Dizin → renk (her çağrıda aynı sabit dizi döner; ayırma yok). */
  renk: (i: number) => Renk;
  /** Lejant: sınıflar ve her sınıftaki bina sayısı. */
  siniflar: Array<Sinif & { adet: number }>;
  /** Mercek bu veride çalışmıyorsa kullanıcıya söylenecek cümle. */
  not: string | null;
}

/**
 * Seçilen merceğe göre her binanın rengi. Sınıf dizisi bir kez hesaplanır;
 * deck.gl'in her köşe için çağırdığı `renk(i)` yalnız tablodan okur.
 */
export function boya(
  mercek: Mercek,
  veri: IkizVerisi,
  noktalar: readonly IkizNoktasi[],
  durumRenkleri: Record<BinaDurumu, readonly number[]>,
  durumEtiketleri: Partial<Record<BinaDurumu, string>>,
  vurgulanan?: ReadonlySet<string> | null,
): Boyama {
  let siniflar: Sinif[];
  let sinifOf: (i: number) => number;
  let not: string | null = null;
  /** Merceğin verisi hiç yok: "0 bina" diye sıfırlarla dolu bir lejant yalan olur. */
  let veriYok = false;

  if (mercek === 'durum') {
    siniflar = DURUM_SIRASI.map((d) => ({
      etiket: durumEtiketleri[d] ?? d,
      renk: [...durumRenkleri[d].slice(0, 3), 255] as Renk,
    }));
    sinifOf = (i) => Math.max(0, DURUM_SIRASI.indexOf(noktalar[veri.kaynak[i]].durum));
  } else if (mercek === 'firsat') {
    siniflar = FIRSAT_SINIFLARI;
    sinifOf = (i) => firsatSinifi(noktalar[veri.kaynak[i]].firsat);
  } else if (mercek === 'doluluk') {
    siniflar = DOLULUK_SINIFLARI;
    sinifOf = (i) => dolulukSinifi(veri.doluluk[i]);
    if (!veri.dolulukVar) {
      not = 'Doluluk verisi sunucudan henüz gelmiyor; binalar gri çiziliyor.';
      veriYok = true;
    }
  } else {
    siniflar = IS_EMRI_SINIFLARI;
    sinifOf = (i) => (veri.acikIs ? Math.min(2, veri.acikIs[i]) : 0);
    if (!veri.acikIs) {
      not = 'Yakında: operasyon modülü bağlanınca açık iş emri olan binalar kırmızıyla yükselecek.';
      veriYok = true;
    }
  }

  const n = veri.length;
  const sinif = new Uint8Array(n);
  const adet = new Array<number>(siniflar.length).fill(0);
  let seciliAdet = 0;
  const secili = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const s = sinifOf(i);
    sinif[i] = s;
    adet[s] += 1;
    if (vurgulanan?.size && vurgulanan.has(noktalar[veri.kaynak[i]].serial)) {
      secili[i] = 1;
      seciliAdet += 1;
    }
  }
  const tablo = siniflar.map((s) => s.renk);
  const cikti = siniflar.map((s, j) => ({ ...s, adet: adet[j] }));
  if (seciliAdet) cikti.push({ etiket: 'Seçili', renk: SECILI_RENK, adet: seciliAdet });

  return {
    renk: (i: number) => (secili[i] ? SECILI_RENK : tablo[sinif[i]]),
    // Durum merceğinde hiç olmayan durumlar lejantı kalabalıklaştırmasın.
    siniflar: veriYok
      ? cikti.filter((s) => s.etiket === 'Seçili')
      : mercek === 'durum'
        ? cikti.filter((s) => s.adet > 0)
        : cikti,
    not,
  };
}

/* ------------------------------ Katman ------------------------------ */

const IZ_SARI: Renk = [255, 201, 0, 255];
const IZ_BEYAZ: Renk = [255, 255, 255, 110];

/** Gövdeler: hafif mat bir yüzey; tepeler duvarlardan açık görünür. */
const MALZEME = {
  ambient: 0.5,
  diffuse: 0.55,
  shininess: 16,
  specularColor: [40, 44, 52] as [number, number, number],
};

export function ikizKatmani(secenek: {
  id: string;
  veri: IkizVerisi;
  boyama: Boyama;
  /** Renkler değişince artan anahtar (mercek, veri sürümü, seçim). */
  boyamaAnahtari: unknown;
  seciliIndis: number;
  tiklandi?: (indis: number) => void;
}) {
  const { id, veri, boyama, boyamaAnahtari, seciliIndis, tiklandi } = secenek;
  return new SolidPolygonLayer({
    id,
    data: veri as never,
    _normalize: false,
    _windingOrder: 'CW',
    positionFormat: 'XYZ',
    filled: true,
    extruded: true,
    wireframe: false,
    material: MALZEME,
    getElevation: (_: unknown, { index }: { index: number }) => veri.yukseklik[index],
    getFillColor: (_: unknown, { index }: { index: number }) => boyama.renk(index),
    updateTriggers: { getFillColor: boyamaAnahtari, getElevation: veri },
    pickable: true,
    autoHighlight: seciliIndis < 0,
    highlightedObjectIndex: seciliIndis >= 0 ? seciliIndis : null,
    highlightColor: seciliIndis >= 0 ? IZ_SARI : IZ_BEYAZ,
    onClick: (bilgi: PickingInfo) => {
      if (bilgi.index < 0 || !tiklandi) return false;
      tiklandi(veri.kaynak[bilgi.index]);
      return true;
    },
  } as never);
}

/* ------------------------------ İpucu ------------------------------ */

function kacis(metin: string) {
  return metin.replace(/[&<>"']/g, (c) =>
    c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c === '"' ? '&quot;' : '&#39;',
  );
}

/** Farenin üstündeki bina: adı, Location Id'si ve merceğin söylediği (HTML). */
export function ipucu(ad: string, loc: string | undefined, satirlar: Array<string | null>) {
  const govde = satirlar.filter(Boolean).map((s) => `<div class="alt">${kacis(s!)}</div>`);
  return (
    `<div class="ad">${kacis(ad)}</div>` +
    (loc ? `<div class="loc">Location Id ${kacis(loc)}</div>` : '') +
    govde.join('')
  );
}

/**
 * İpucunu imlecin yanına koyar (null → gizler).
 *
 * deck.gl'in kendi ipucu, sayfa kaydırılınca yüksekliği yanlış hesaplayıp
 * kutuyu haritanın dışına (görünmez yere) atıyordu. Kendi kutumuzu tuvalin
 * koordinatlarıyla yerleştiriyoruz; React durumu kullanılmaz — fare her
 * kıpırdadığında harita yeniden çizilmesin.
 */
export function ipucuYerlestir(kutu: HTMLDivElement | null, x: number, y: number, html: string | null) {
  if (!kutu) return;
  if (!html) {
    if (kutu.style.display !== 'none') kutu.style.display = 'none';
    return;
  }
  if (kutu.innerHTML !== html) kutu.innerHTML = html;
  kutu.style.display = 'block';
  const ebeveyn = kutu.parentElement;
  const g = ebeveyn?.clientWidth ?? 0;
  const h = ebeveyn?.clientHeight ?? 0;
  const w = kutu.offsetWidth;
  const k = kutu.offsetHeight;
  // İmlecin sağ altına; kenara taşarsa öbür yana.
  const sol = x + 14 + w > g ? Math.max(4, x - 14 - w) : x + 14;
  const ust = y + 14 + k > h ? Math.max(4, y - 14 - k) : y + 14;
  kutu.style.transform = `translate(${Math.round(sol)}px, ${Math.round(ust)}px)`;
}

/** Merceğe göre ipucunun ikinci satırı ("12 boş kapı · 6 kat" gibi). */
export function mercekSatiri(
  mercek: Mercek,
  veri: IkizVerisi,
  indis: number,
  nokta: IkizNoktasi,
  durumEtiketi: string,
): string {
  const kat = veri.kat[indis];
  const katMetni = kat > 0 ? `${kat} kat` : 'kat bilinmiyor';
  if (mercek === 'firsat') return `${nokta.firsat.toLocaleString('tr-TR')} boş kapı · ${katMetni}`;
  if (mercek === 'doluluk') {
    const p = veri.doluluk[indis];
    const oran = Number.isNaN(p) ? 'Doluluk ölçülemiyor' : `Doluluk %${Math.round(p * 100)}`;
    return `${oran} · ${katMetni}`;
  }
  if (mercek === 'is_emri') {
    const a = veri.acikIs?.[indis] ?? 0;
    return `${veri.acikIs ? `${a} açık iş emri` : 'İş emri verisi yakında'} · ${katMetni}`;
  }
  return `${durumEtiketi} · ${katMetni}`;
}

/* ------------------------------ Kanca ------------------------------ */

export type IkizDurumu = 'kapali' | 'yukleniyor' | 'hazir' | 'temsili';

/**
 * Telefonlarda 3B yalnız ekranın çevresindeki binalarla kurulur (en fazla
 * `TELEFON_SINIRI`). Görünüm bu kutudan çıkınca ya da yakınlık belirgin
 * değişince yeniden kurulur — her karede değil.
 */
const TELEFON_SINIRI = 3000;

function kutuIcinde(k: [number, number, number, number], lon: number, lat: number) {
  return lon >= k[0] && lon <= k[2] && lat >= k[1] && lat <= k[3];
}

/**
 * 3B açıldığında taban çizgilerini indirir, noktalarla birleştirir.
 * `sinirli`: küçük ekran — yalnız görünen alan çevresi kurulur.
 */
export function useIkiz<T extends IkizNoktasi>(
  acik: boolean,
  noktalar: readonly T[],
  bolge: number | null,
  gorunum: MapViewState | null,
  genislik: number,
  yukseklik: number,
  sinirli: boolean,
): { veri: IkizVerisi | null; ogeler: readonly T[]; durum: IkizDurumu } {
  const [sonuc, setSonuc] = useState<GeometriSonucu | null>(null);
  const sonucRef = useRef(sonuc);
  sonucRef.current = sonuc;

  /*
   * 3B her açıldığında: taban çizgileri yoksa (ya da geçen sefer bağlantı
   * yoktuysa) sorulur. İndirme sürerken 3B kapatılıp yeniden açılırsa aynı
   * istek beklenir: `geometriAl` isteği paylaştığı için veri ikinci kez inmez.
   */
  useEffect(() => {
    const mevcut = sonucRef.current;
    if (!acik || (mevcut && mevcut.tur !== 'baglanti')) return undefined;
    let iptal = false;
    void geometriAl(bolge).then((s) => {
      if (!iptal) setSonuc(s);
    });
    return () => {
      iptal = true;
    };
  }, [acik, bolge]);

  /* Telefonda: görünen alanın çevresi (kaydırdıkça değil, kutudan çıkınca tazelenir). */
  const kapsamRef = useRef<{ kutu: [number, number, number, number]; zoom: number } | null>(null);
  const [kapsamSurum, setKapsamSurum] = useState(0);
  const cokluk = noktalar.length > TELEFON_SINIRI;
  useEffect(() => {
    if (!acik || !sinirli || !cokluk || !gorunum || !genislik || !yukseklik) return;
    let kutu: [number, number, number, number];
    try {
      kutu = new WebMercatorViewport({ ...gorunum, width: genislik, height: yukseklik }).getBounds() as [
        number,
        number,
        number,
        number,
      ];
    } catch {
      return;
    }
    const o = kapsamRef.current;
    const icinde =
      o &&
      kutuIcinde(o.kutu, kutu[0], kutu[1]) &&
      kutuIcinde(o.kutu, kutu[2], kutu[3]) &&
      Math.abs(o.zoom - gorunum.zoom) < 1.5;
    if (icinde) return;
    const px = (kutu[2] - kutu[0]) * 0.6;
    const py = (kutu[3] - kutu[1]) * 0.6;
    kapsamRef.current = {
      kutu: [kutu[0] - px, kutu[1] - py, kutu[2] + px, kutu[3] + py],
      zoom: gorunum.zoom,
    };
    setKapsamSurum((s) => s + 1);
  }, [acik, sinirli, cokluk, gorunum, genislik, yukseklik]);

  const ogeler = useMemo<readonly T[]>(() => {
    if (!sinirli || !cokluk) return noktalar;
    const k = kapsamRef.current?.kutu;
    if (!k) return [];
    const [mx, my] = [(k[0] + k[2]) / 2, (k[1] + k[3]) / 2];
    const icerde = noktalar.filter((n) => kutuIcinde(k, n.konum[0], n.konum[1]));
    if (icerde.length <= TELEFON_SINIRI) return icerde;
    // Hâlâ çoksa merkeze en yakınlar: ekranın ortası hiç boş kalmasın.
    return icerde
      .map((n) => ({ n, u: (n.konum[0] - mx) ** 2 + (n.konum[1] - my) ** 2 }))
      .sort((a, b) => a.u - b.u)
      .slice(0, TELEFON_SINIRI)
      .map((x) => x.n);
  }, [noktalar, sinirli, cokluk, kapsamSurum]);

  // 3B kapatılıp açılınca yeniden kurulmaz: `acik` bilerek bağımlılık değil.
  const veri = useMemo(() => (sonuc ? ikizKur(ogeler, sonuc) : null), [ogeler, sonuc]);

  let durum: IkizDurumu = 'kapali';
  if (acik) {
    durum = !veri
      ? 'yukleniyor'
      : sonuc?.tur === 'hazir' && (veri.length === 0 || veri.temsili < veri.length)
        ? 'hazir'
        : 'temsili';
  }
  return { veri: acik ? veri : null, ogeler, durum };
}
