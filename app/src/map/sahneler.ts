/**
 * Hazır sahne tarifleri — katman fabrikasının önerilen çizim sırasını tek çağrıda verir.
 *
 * Sunum ve Keşif kendi sahnelerini `katmanlar.ts` fonksiyonlarıyla kurar; bu dosya
 * "8 bölgeli 3B şehir" temel görüntüsünü tekrar etmemek için ortak bir başlangıç noktasıdır.
 * Sahneye özel her şey (vurgu, animasyon, ısı sütunları) seçeneklerle açılır.
 */
import type { LayersList } from '@deck.gl/core';
import type { Plan } from '../data/types';
import {
  altlik,
  arklar,
  binaIsiklari,
  binalar3D,
  bolgeEtiketleri,
  bolgeSinirlari,
  katmanlar,
  ofisIsaretcisi,
  type BinaRenkModu,
} from './katmanlar';

export interface TemelSahneSecenekleri {
  /** saniye — nabız/akış animasyonları için; sabit görüntü 0 */
  t?: number;
  /** bina renk modu (varsayılan bölge rengi) */
  renkModu?: BinaRenkModu;
  /** 0..1 bina yüksekliği (açılış animasyonu) */
  yukseklikOlcegi?: number;
  /** yalnız bu bölgeler canlı */
  vurguBolgeler?: number[] | null;
  /** bina seçilebilir mi (Keşif: true) */
  secilebilir?: boolean;
  /** sınır dolgusu + çizgisi */
  sinirlar?: boolean;
  /** ofis işaretçisi ve ofis→bölge yayları */
  ofis?: boolean;
  arklar?: boolean;
  /** bölge etiketleri ('kod' | 'kisa' | 'kodKisa' | 'tam'); false = yok */
  etiket?: 'kod' | 'kisa' | 'kodKisa' | 'tam' | false;
  /** ilçe adları ve sınırları */
  ilceler?: boolean;
  /** uzak görünümde binaları görünür kılan toplamsal "şehir ışıkları" katmanı */
  isiklar?: boolean;
  /** 0..1 genel altlık opaklığı */
  altlikGorunurlugu?: number;
  /** bina renk geçişi (ms) */
  renkGecisMs?: number;
}

/**
 * Temel 3B şehir sahnesi: altlık → bölge dolgusu → binalar → bölge çizgisi → yaylar → ofis → etiketler.
 * Dönen liste doğrudan `HaritaSahnesi`'ne verilebilir.
 */
export function temelSahne(plan: Plan, o: TemelSahneSecenekleri = {}): LayersList {
  const {
    t = 0,
    renkModu,
    yukseklikOlcegi = 1,
    vurguBolgeler = null,
    secilebilir = false,
    sinirlar = true,
    ofis = true,
    arklar: yaylar = false,
    etiket = 'kodKisa',
    ilceler = true,
    isiklar = false,
    altlikGorunurlugu = 1,
    renkGecisMs = 0,
  } = o;
  return katmanlar(
    altlik({ gorunurluk: altlikGorunurlugu, ilceEtiketleri: ilceler, ilceSinirlari: ilceler }),
    sinirlar && bolgeSinirlari({ plan, parca: 'dolgu', vurguBolgeler }),
    binalar3D({ plan, renkModu, yukseklikOlcegi, vurguBolgeler, pickable: secilebilir, autoHighlight: secilebilir, renkGecisMs }),
    isiklar && binaIsiklari({ plan, renkModu, alfa: 150 }),
    sinirlar && bolgeSinirlari({ plan, parca: 'cizgi', vurguBolgeler }),
    yaylar && arklar({ plan, t, bolgeler: vurguBolgeler }),
    ofis && ofisIsaretcisi({ t }),
    etiket && bolgeEtiketleri({ plan, bicim: etiket, boyut: plan.n <= 12 ? 28 : 20, vurguBolgeler }),
  );
}
