/**
 * Keşif katman tarifi — saf fonksiyon, yalnız `map/katmanlar.ts` fabrikasından beslenir.
 *
 * Çizim sırası: karo? → altlık → bölge dolgusu → binalar → bölge çizgisi → ısı sütunları
 *               → yaylar → ofis → seçim halkası → bölge etiketleri
 */
import { ColumnLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import type { Layer, LayersList } from '@deck.gl/core';

import { veri, bolgeEtiketNoktasi } from '../data/load';
import { hexRgba, karistir, type RGBA } from '../data/selectors';
import type { Bolge, LonLat, Plan } from '../data/types';
import { HARITA_FONT } from '../map/fontlar';
import {
  altlik,
  binaIsiklari,
  binaRenkleri,
  arklar,
  binalar3D,
  bolgeSinirlari,
  cartoKaroKatmani,
  hpSutunlari,
  katmanlar,
  ofisIsaretcisi,
  planAnahtari,
  TOPLAMSAL_KARISIM,
  type BinaRenkModu,
} from '../map/katmanlar';
import type { KesifDurumu, Metrik } from './durum';

/** Fırsat ısı paleti: gece moru → kor → altın (yüksek fırsat parlar). */
export const FIRSAT_PALETI = ['#140B2A', '#4A1648', '#A3213F', '#FF5A36', '#FFA41B', '#FFE7A0'];
/**
 * Penetrasyon paleti: mor (fırsat) → mavi → camgöbeği → beyaz (doygun).
 *
 * Kırmızı–yeşil rampa kullanılmıyor: izleyicinin renk körlüğü olasılığı düşük değil ve o rampanın
 * iki ucu ayırt edilemiyordu. Bu ölçekte AÇIKLIK tek başına sinyali taşır (L* ≈ 28 → 94), yani
 * renk hiç görülmese bile sıra okunur. Sunumun geri kalanında kırmızı "sorun" demek olduğu için
 * fırsatı kırmızıyla işaretleme çelişkisi de ortadan kalkar.
 */
export const PENETRASYON_PALETI = ['#4B1E86', '#5E3BC4', '#4F79E8', '#3FAEDC', '#7FDCE0', '#DFF6F7'];

/** Metrik moduna göre bina renk modu. */
export function renkModu(metrik: Metrik, plan: Plan): BinaRenkModu {
  if (metrik === 'firsat')
    return { tur: 'metrik', metrik: 'firsat', palet: FIRSAT_PALETI, olcek: 'karekok' };
  if (metrik === 'penetrasyon')
    return { tur: 'metrik', metrik: 'penetrasyon', palet: PENETRASYON_PALETI, alan: [0, 0.75], olcek: 'dogrusal' };
  return { tur: 'bolge', plan };
}

export interface KesifKatmanSecenekleri {
  plan: Plan;
  durum: KesifDurumu;
  /** 3B ↔ 2B geçişinde yumuşatılan bina yükseklik çarpanı (1 → 0,02) */
  yukseklikOlcegi: number;
  /** CARTO karoları erişilebilir mi (yalnız çevrimiçi; OSM altlığının ALTINA konur) */
  karo: boolean;
  /** vurgulanacak bina indeksleri (seçim halkası) */
  secimIndeksleri: number[] | null;
}

/**
 * Seçili binaların rengi — temel renk modunun üstüne marka sarısı.
 * (Halka yerine binanın kendisini boyamak yakın planda blob oluşturmaz.)
 */
function secimliRenkModu(temelMod: BinaRenkModu, indeksler: number[] | null, anahtar: string): BinaRenkModu {
  if (!indeksler || !indeksler.length) return temelMod;
  const temel = binaRenkleri(temelMod);
  const sec = new Set(indeksler);
  // Soluk sarı bina, B8'in doygun kırmızı duvarında seçilmiyordu. Seçili bina neredeyse beyaz
  // boyanır ve tek/az binalı seçimde çevresi %40 söndürülür: bakış doğrudan oraya gider.
  const vurguRenk: RGBA = [255, 248, 224, 255];
  const sondur = indeksler.length <= 40 ? 0.6 : 1;
  return {
    tur: 'ozel',
    anahtar,
    renk: (i: number) =>
      sec.has(i)
        ? vurguRenk
        : ([
            temel[4 * i] * sondur,
            temel[4 * i + 1] * sondur,
            temel[4 * i + 2] * sondur,
            temel[4 * i + 3],
          ] as RGBA),
  };
}

/** Seçim halkası — konumu uzaktan da belli etsin diye ince ve küçük. */
function secimHalkasi(indeksler: number[], ikiBoyut: boolean): Layer[] {
  const b = veri().binalar;
  const veriler = indeksler.slice(0, 300);
  const tek = veriler.length === 1;
  const konum = (i: number): [number, number, number] => [b.lon[i], b.lat[i], ikiBoyut ? 6 : b.yukseklik[i] + 16];
  const k: Layer[] = [];
  if (tek)
    k.push(
      new ScatterplotLayer<number>({
        id: 'secim-hale',
        data: veriler,
        getPosition: konum,
        getRadius: 60,
        radiusUnits: 'meters',
        radiusMinPixels: 12,
        radiusMaxPixels: 46,
        getFillColor: [255, 196, 0, 55],
        parameters: TOPLAMSAL_KARISIM,
        updateTriggers: { getPosition: ikiBoyut },
      }),
    );
  k.push(
    new ScatterplotLayer<number>({
      id: 'secim-halka',
      data: veriler,
      getPosition: konum,
      stroked: true,
      filled: false,
      getRadius: tek ? 34 : 20,
      radiusUnits: 'meters',
      radiusMinPixels: tek ? 9 : 6,
      radiusMaxPixels: tek ? 30 : 11,
      // beyaz halka: dolgu rengi ne olursa olsun kontrastı kaybolmaz
      getLineColor: [255, 255, 255, tek ? 245 : 175],
      getLineWidth: tek ? 2.6 : 2,
      lineWidthUnits: 'pixels',
      updateTriggers: { getPosition: ikiBoyut, getRadius: tek, getLineColor: tek },
    }),
  );
  // Işık huzmesi: seçili binayı kalabalık bir kümede bile bir bakışta bulduran şey.
  if (veriler.length <= 40 && !ikiBoyut)
    k.push(
      new ColumnLayer<number>({
        id: 'secim-huzme',
        data: veriler,
        getPosition: (i: number) => [b.lon[i], b.lat[i], b.yukseklik[i]],
        radius: tek ? 9 : 7,
        diskResolution: 10,
        extruded: true,
        getElevation: tek ? 520 : 360,
        getFillColor: [255, 236, 170, 130],
        material: false,
        parameters: TOPLAMSAL_KARISIM,
        updateTriggers: { getPosition: ikiBoyut, getElevation: tek },
      }),
    );
  return k;
}

/**
 * Hangi bölgelerin etiketi çizilir?
 *
 * Şehir merkezinde B2/B3/B5/B6 etiket noktaları birkaç yüz metre arayla; hepsini basmak
 * okunmaz bir yığın üretiyor. Kararlı (viewport'tan bağımsız) bir eleme yapılır:
 * ofis noktası baştan kabul edilir, bölgeler ofise uzaklığa göre sıralanır ve
 * kabul edilenlere `eps` dereceden yakın olan etiket atlanır. Seçili bölge varsa yalnız o çizilir.
 *
 * (deck.gl CollisionFilterExtension denendi: cihaz piksel oranı 1 dışında etiketleri
 * tamamen yutuyor — sunum dizüstünde %125/%150 ölçek çok olası olduğu için kullanılmadı.)
 */
function gorunurEtiketler(plan: Plan, secili: number | null): Set<number> {
  if (secili != null) return new Set([secili]);
  const of = veri().meta.ofis;
  const eps = plan.n <= 12 ? 0.07 : 0.045;
  const epsY = eps * 0.8;
  const kabul: LonLat[] = [[of.lon, of.lat]];
  const out = new Set<number>();
  for (const b of [...plan.bolgeler].sort((a, z) => z.ofis_km - a.ofis_km)) {
    const [x, y] = bolgeEtiketNoktasi(b);
    if (kabul.some(([px, py]) => Math.abs(px - x) < eps && Math.abs(py - y) < epsY)) continue;
    kabul.push([x, y]);
    out.add(b.bolge);
  }
  return out;
}

/** Etiket katmanları — bölge etiketleri + ofis etiketi (3B sahnenin üstünde). */
function etiketKatmanlari(plan: Plan, durum: KesifDurumu, ofisGoster: boolean): Layer[] {
  // Fırsat/Penetrasyon modunda ekranda tek bir renk dili olsun: etiketler bölge rengini bırakır.
  const bolgeRengiyle = durum.metrik === 'bolge';
  const kisa = plan.n <= 12;
  const boyut = kisa ? 25 : 19;
  const ikiBoyut = durum.gorunum === '2b';
  const yukseklik = ikiBoyut ? 0 : 200;
  const secili = durum.secBolge;
  // etiketler 3B sahnenin üstünde kalsın (katmanlar.ts'teki USTTE_PARAMETRELERI ile aynı)
  const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;
  const of = veri().meta.ofis;
  const gorunur = gorunurEtiketler(plan, secili);
  const veriler = plan.bolgeler.filter((b) => gorunur.has(b.bolge));

  const bolgeler = new TextLayer<Bolge>({
    id: 'bolge-etiket',
    data: veriler,
    getPosition: (d: Bolge) => {
      const [lon, lat] = bolgeEtiketNoktasi(d);
      return [lon, lat, yukseklik];
    },
    getText: (d: Bolge) => (kisa || secili === d.bolge ? `${d.kod} · ${d.kisa_ad}` : d.kod),
    getSize: (d: Bolge) => (secili === d.bolge ? boyut * 1.3 : boyut),
    sizeUnits: 'pixels',
    ...HARITA_FONT,
    getColor: [255, 255, 255, 255],
    background: true,
    getBackgroundColor: (d: Bolge) =>
      (bolgeRengiyle
        ? karistir([5, 10, 22, 235], hexRgba(d.renk), 0.2)
        : [8, 14, 28, 235]) as [number, number, number, number],
    getBorderColor: (d: Bolge) => (bolgeRengiyle ? hexRgba(d.renk) : ([120, 140, 175, 220] as RGBA)),
    getBorderWidth: 2,
    backgroundPadding: [13, 6, 13, 6],
    backgroundBorderRadius: 8,
    // Seçili bölgede etiket, `etiket` noktasının SAĞINA yazılır: fitBounds bu noktayı
    // panellerin sağında tutar, böylece etiket sol panelin altında yarım kalmaz.
    getTextAnchor: secili ? 'start' : 'middle',
    getPixelOffset: secili ? [14, 0] : [0, 0],
    getAlignmentBaseline: 'center',
    parameters: USTTE,
    updateTriggers: {
      getPosition: yukseklik,
      getText: [kisa, secili],
      getSize: [secili, boyut],
      getBackgroundColor: [planAnahtari(plan), bolgeRengiyle],
      getBorderColor: [planAnahtari(plan), bolgeRengiyle],
      getTextAnchor: secili,
      getPixelOffset: secili,
    },
  } as never);

  // Ofis etiketi: marka etiketi her zaman görünür (eleme ofisten başlar).
  const ofisEtiketi = new TextLayer<number>({
    id: 'ofis-etiket',
    data: [0],
    getPosition: () => [of.lon, of.lat, ikiBoyut ? 60 : 2260],
    getText: () => 'DEHANET EÇM',
    getSize: 23,
    sizeUnits: 'pixels',
    ...HARITA_FONT,
    fontWeight: 800,
    getColor: [3, 6, 13, 255],
    background: true,
    getBackgroundColor: [255, 196, 0, 255],
    backgroundPadding: [14, 6, 14, 4],
    backgroundBorderRadius: 6,
    // Fenerin SAĞINA yazılır: 1366'da ortalanmış etiketin sol yarısı cam panelin altında
    // kalıyor ve "NET EÇM" diye okunuyordu. Seçili bölge etiketinde de aynı çözüm var.
    getTextAnchor: 'start',
    getAlignmentBaseline: 'center',
    getPixelOffset: [16, -6],
    parameters: USTTE,
    updateTriggers: { getPosition: ikiBoyut },
  } as never);

  return ofisGoster ? [bolgeler, ofisEtiketi] : [bolgeler];
}

/** Keşif sahnesinin tüm katmanları. */
export function kesifKatmanlari(o: KesifKatmanSecenekleri): LayersList {
  const { plan, durum, yukseklikOlcegi, karo, secimIndeksleri } = o;
  const { katman, metrik, secBolge, gorunum } = durum;
  const ikiBoyut = gorunum === '2b';
  const vurgu = secBolge ? [secBolge] : null;
  const secimAnahtari = `sec:${metrik}:${planAnahtari(plan)}:${secimIndeksleri?.length ?? 0}:${secimIndeksleri?.[0] ?? -1}`;
  const binaRenkModu = secimliRenkModu(renkModu(metrik, plan), secimIndeksleri, secimAnahtari);

  // Yollar kapalıysa altlığın yol katmanlarını id ile ayıkla (paylaşılan fabrikada anahtarı yok).
  const altlikKatmanlari = altlik({
    ilceEtiketleri: true,
    ilceSinirlari: true,
    yolParlama: katman.yollar,
  }).filter((k) => katman.yollar || !k.id.includes('-yol'));

  return katmanlar(
    // CARTO yalnız çevrimiçi ve yalnız OSM altlığının ALTINDA (çevrimdışı sessizce atlanır)
    karo && katman.yollar ? cartoKaroKatmani({ stil: 'dark_nolabels', opaklik: 0.5 }) : null,
    altlikKatmanlari,
    katman.sinirlar &&
      bolgeSinirlari({
        plan,
        parca: 'dolgu',
        dolguAlfa: metrik === 'bolge' ? (secBolge ? 20 : 30) : secBolge ? 14 : 10,
        vurguBolgeler: vurgu,
      }),
    katman.binalar &&
      binalar3D({
        plan,
        renkModu: binaRenkModu,
        yukseklikOlcegi,
        vurguBolgeler: vurgu,
        sonukluk: 0.8,
        renkGecisMs: 600,
        pickable: true,
        autoHighlight: true,
        opacity: katman.sutun ? 0.45 : 1,
      }),
    // Uzak görünümde binalar 1-2 piksel kalıyor; toplamsal "şehir ışıkları" katmanı
    // renk modunu (bölge / fırsat / penetrasyon) ta baştan okunur kılar.
    // Bölge seçiliyken kapatılır: toplamsal ışık katmanı sönükleştirmeyi (vurguBolgeler) tanımıyor,
    // seçili bölgenin önüne geçiyordu.
    katman.binalar &&
      !secBolge &&
      binaIsiklari({
        plan,
        renkModu: binaRenkModu,
        yaricap: 26,
        minPiksel: 1.5,
        alfa: metrik === 'bolge' ? 150 : 205,
      }),
    katman.sinirlar &&
      bolgeSinirlari({
        plan,
        parca: 'cizgi',
        cizgiGenislik: plan.n > 20 ? 1.6 : 2.4,
        // metrik modlarında sınır parlaması bina renklerini bastırıyor
        parlama: metrik === 'bolge',
        vurguBolgeler: vurgu,
      }),
    katman.sutun &&
      hpSutunlari({
        mod: 'hex',
        olcu: metrik === 'firsat' ? 'firsat' : metrik === 'penetrasyon' ? 'aktif' : 'res_hp',
        // sütun renkleri lejanttaki paletle aynı aileden olsun
        renkAraligi: metrik === 'firsat' ? FIRSAT_PALETI : metrik === 'penetrasyon' ? PENETRASYON_PALETI : undefined,
        yaricap: 450,
        yukseklikOlcegi: ikiBoyut ? 0.05 : 4,
        pickable: false,
      }),
    katman.ofis && arklar({ plan, bolgeler: vurgu, genislik: plan.n > 20 ? 2 : 3 }),
    katman.ofis && ofisIsaretcisi({ t: 0, etiket: false, yukseklik: ikiBoyut ? 0 : 2200 }),
    secimIndeksleri && secimIndeksleri.length ? secimHalkasi(secimIndeksleri, ikiBoyut) : null,
    etiketKatmanlari(plan, durum, katman.ofis),
  );
}
