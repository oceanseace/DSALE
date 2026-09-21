/**
 * Veri paketinin TypeScript tipleri.
 * Kaynak: dsale/bundle.py → app/src/data/generated/{binalar,planlar,meta,altlik}.json
 * (JSON dosyaları ?raw ile içe alınıp JSON.parse edilir; tipleri buradan gelir, TS dosyadan çıkarım yapmaz.)
 */

/** [boylam, enlem] */
export type LonLat = [number, number];

/* ------------------------------------------------------------------ GeoJSON (yalın) */

export interface GeoPolygon {
  type: 'Polygon';
  coordinates: LonLat[][];
}
export interface GeoMultiPolygon {
  type: 'MultiPolygon';
  coordinates: LonLat[][][];
}
export interface GeoLineString {
  type: 'LineString';
  coordinates: LonLat[];
}
export interface GeoMultiLineString {
  type: 'MultiLineString';
  coordinates: LonLat[][];
}
export type GeoGeometri = GeoPolygon | GeoMultiPolygon | GeoLineString | GeoMultiLineString;

export interface GeoFeature<G extends GeoGeometri = GeoGeometri, P = Record<string, unknown>> {
  type: 'Feature';
  properties: P;
  geometry: G;
}
export interface GeoFeatureCollection<G extends GeoGeometri = GeoGeometri, P = Record<string, unknown>> {
  type: 'FeatureCollection';
  features: GeoFeature<G, P>[];
  attribution?: string;
}

/* ------------------------------------------------------------------ binalar.json */

/** Sütunsal bina verisi: her dizi n uzunluğunda, i. eleman i. binaya ait. */
export interface BinalarPaketi {
  surum: number;
  /** bina sayısı (19.706) */
  n: number;
  /** bina seri no, ör. "BN-00000853-1" */
  serial: string[];
  lon: number[];
  lat: number[];
  /** kat sayısı (OneMap veya tahmin) */
  kat: number[];
  toplam_hp: number[];
  res_hp: number[];
  /** aktif residential abone */
  aktif: number[];
  /** fırsat = boş residential HP (res_hp − aktif) */
  firsat: number[];
  /** site-grup (bölgeleme birimi) indeksi → sozluk.birim ve plan.birim_bolge */
  birim: number[];
  /** sozluk.mahalle indeksleri */
  mahalle: number[];
  /** sozluk.ilce indeksleri */
  ilce: number[];
  /** sozluk.il indeksleri */
  il: number[];
  /** sozluk.ad indeksleri (site adı ya da bina adı) */
  ad: number[];
  sozluk: {
    mahalle: string[];
    ilce: string[];
    il: string[];
    ad: string[];
    birim: string[];
  };
  /**
   * Taban poligonları: i. binanın noktaları ofs[i] .. ofs[i+1]-1.
   * p. noktanın boylamı = lon[i] + fark[2p]*olcek, enlemi = lat[i] + fark[2p+1]*olcek.
   * Poligonu olmayan binada ofs[i] === ofs[i+1].
   */
  poligon: {
    fark: number[];
    ofs: number[];
    olcek: number;
  };
}

/* ------------------------------------------------------------------ planlar.json */

export interface IlcePayi {
  ilce: string;
  /** 0..1 — bölgenin RES HP'sindeki payı */
  pay: number;
}

export interface BolgeMahallesi {
  ilce: string;
  mahalle: string;
  firsat: number;
  res_hp: number;
  bina: number;
}

/** Tek bir satış bölgesinin özet KPI'ları (dsale/metrics.py → bolge_ozetleri). */
export interface Bolge {
  /** 1..N */
  bolge: number;
  /** "B1" */
  kod: string;
  /** uzun ad, ör. "Nilüfer · Dumlupınar – Balkan" veya "Mudanya · Gemlik · Yalova · Orhangazi" */
  ad: string;
  /** kısa ad, ör. "Dumlupınar" */
  kisa_ad: string;
  /** "#FFC400" */
  renk: string;
  bina: number;
  site: number;
  toplam_hp: number;
  res_hp: number;
  soho_hp: number;
  aktif_res: number;
  aktif_toplam: number;
  firsat: number;
  /** aktif_res / res_hp (0..1) */
  penetrasyon: number;
  kurulum_son_ay: number;
  churn_son_ay: number;
  tv: number;
  olcu: string;
  olcu_deger: number;
  /** hedefe göre sapma (ör. 0.0045 = %0,45) */
  sapma: number;
  /** RES HP ağırlıklı merkez [lon, lat] — km KPI'ları bundan hesaplanır */
  merkez: LonLat;
  /**
   * Etiket noktası [lon, lat] — poligonun içinde garanti (polylabel).
   * CCPD-2.5 öncesi veri paketlerinde yoktur; tüm etiket/pin/çağrı yerleşimleri `etiket ?? merkez` kullanır.
   */
  etiket?: LonLat;
  /** ofisten merkeze km */
  ofis_km: number;
  ort_merkez_km: number;
  maks_merkez_km: number;
  /** minimum yayılan ağaç uzunluğu (km) — rota yükü göstergesi */
  mst_km: number;
  ilceler: IlcePayi[];
  mahalle_sayisi: number;
  ust_mahalleler: BolgeMahallesi[];
  yalova_bina: number;
  yalova_res_hp: number;
  /** bölge sınırı (tamponlu içbükey zarf) */
  poligon?: GeoPolygon | GeoMultiPolygon;
  /** yerleşim alanı (km²) — binaların kapladığı tamponlu alan, idari alan değil */
  alan_km2?: number;
  /** boş bölge (olağan dışı) */
  bos?: boolean;
}

export interface PlanParametreleri {
  algoritma?: string;
  olcu?: string;
  seed?: number;
  birim_sayisi?: number;
  [anahtar: string]: unknown;
}

/** Bir bölgeleme planı (planlar.json → planlar[N]; outputs/N08_res_hp/plan_N08.json ile aynı biçim). */
export interface Plan {
  n: number;
  olcu: string;
  /** bölge başına hedef ölçü değeri (ör. 37.097,25 RES HP) */
  hedef: number;
  sapma_min: number;
  sapma_maks: number;
  sure_sn?: number;
  parametreler?: PlanParametreleri;
  /** birim (site-grup) indeksi → bölge no (1..N); 0 = atanmamış */
  birim_bolge: number[];
  bolgeler: Bolge[];
  /** algoritma ara adımları: her adım N merkezlik [lon,lat] listesi (yalnız varsayılan planda dolu) */
  anlik?: LonLat[][];
  /**
   * `anlik` ile aynı uzunlukta: her adımda her birimin (site-grup) bölgesi.
   * Dize uzunluğu = birim_sayisi; s. adımda i. birimin bölgesi = anlik_etiket[s].charCodeAt(i) − 48.
   * Yalnız varsayılan planda ve yalnız CCPD-2.5+ veri paketlerinde bulunur.
   */
  anlik_etiket?: string[];
}

export interface PlanlarPaketi {
  varsayilan: number;
  olcu: string;
  birim_sayisi: number;
  /** anahtar = N ("2" … "50") */
  planlar: Record<string, Plan>;
}

/* ------------------------------------------------------------------ meta.json */

export interface Ofis {
  ad: string;
  lat: number;
  lon: number;
  plus_code?: string;
}

export interface Toplamlar {
  bina: number;
  toplam_hp: number;
  res_hp: number;
  soho_hp: number;
  aktif_res: number;
  aktif_toplam: number;
  firsat: number;
  kurulum_son_ay: number;
  churn_son_ay: number;
}

export interface IlceOzeti {
  il: string;
  ilce: string;
  bina: number;
  res_hp: number;
  aktif: number;
  firsat: number;
  lon: number;
  lat: number;
}

export interface MahalleOzeti {
  ilce: string;
  mahalle: string;
  bina: number;
  res_hp: number;
  firsat: number;
  lon: number;
  lat: number;
}

export interface Meta {
  surum: number;
  uretim: string;
  /** "TURKCELL SUPERONLINE DEHANET EV ÇÖZÜM MERKEZİ" */
  organizasyon: string;
  /** "Dehanet EÇM" */
  organizasyon_kisa: string;
  /** "Sayın Hasan Kızılkaya'nın bilgilerine" */
  hitap: string;
  /** "Bursa Fiber Satış Haritası" */
  baslik: string;
  ofis: Ofis;
  ekip: { mudur: string; takim_lideri: string; sorumlu_sayisi: number };
  toplam: Toplamlar;
  mahalle_sayisi: number;
  ilce_sayisi: number;
  /** aktif_res / res_hp */
  penetrasyon: number;
  ilceler: IlceOzeti[];
  ust_mahalleler: MahalleOzeti[];
  yalova: {
    bina: number;
    res_hp: number;
    toplam_hp: number;
    aktif: number;
    firsat: number;
    merkez: LonLat | null;
    /** Yalova binası içeren bölge numaraları (varsayılan plan) */
    bolgeler: number[];
  };
  sinir: { lon: [number, number]; lat: [number, number] };
  kaynaklar: { bina: string; konum: string; altlik: string };
  kalite: {
    data_satir?: number;
    tekil_bina?: number;
    eslesme?: Record<string, number>;
    kat_kaynagi?: Record<string, number>;
    aktif_res_gt_res_hp?: number;
    onemap_cekim_tarihi?: string;
    site_grup_sayisi?: number;
  };
}

/* ------------------------------------------------------------------ altlik.json */

export interface Altlik {
  attribution: string;
  /** s = önem: 1 otoyol/devlet yolu, 2 birincil, 3 ikincil, 4 üçüncül */
  yollar: GeoFeatureCollection<GeoLineString | GeoMultiLineString, { s: number }>;
  /** tur = "kiyi" (MultiLineString/LineString) | "gol" (Polygon) */
  su: GeoFeatureCollection<GeoGeometri, { tur: 'kiyi' | 'gol' }>;
  /** ilçe sınırları; ad = ilçe adı */
  ilce: GeoFeatureCollection<GeoPolygon | GeoMultiPolygon, { ad: string }>;
}
