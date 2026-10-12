/** Türkçe biçimlendirme — sayı, tarih, mesafe, etiketler. */

import type { BinaDurumu, GorevBinasi, ZiyaretSonucu } from '../api/tipler';

const sayiBicimi = new Intl.NumberFormat('tr-TR');

export function sayi(deger: number | null | undefined): string {
  if (deger == null || Number.isNaN(deger)) return '—';
  return sayiBicimi.format(deger);
}

export function yuzde(oran: number | null | undefined, basamak = 0): string {
  if (oran == null || Number.isNaN(oran)) return '—';
  return `%${(oran * 100).toLocaleString('tr-TR', {
    minimumFractionDigits: basamak,
    maximumFractionDigits: basamak,
  })}`;
}

export function mesafe(metre: number | null | undefined): string | null {
  if (metre == null || Number.isNaN(metre)) return null;
  if (metre < 1000) return `${Math.round(metre)} m`;
  return `${(metre / 1000).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} km`;
}

const gunler = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];
const aylar = [
  'Ocak',
  'Şubat',
  'Mart',
  'Nisan',
  'Mayıs',
  'Haziran',
  'Temmuz',
  'Ağustos',
  'Eylül',
  'Ekim',
  'Kasım',
  'Aralık',
];

export function tarihUzun(giris?: string | Date): string {
  const t = giris ? (typeof giris === 'string' ? yerelTarih(giris) : giris) : new Date();
  return `${t.getDate()} ${aylar[t.getMonth()]} ${gunler[t.getDay()]}`;
}

export function saat(iso: string): string {
  const t = yerelTarih(iso);
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`;
}

export function tarihSaat(iso: string): string {
  const t = yerelTarih(iso);
  return `${t.getDate()} ${aylar[t.getMonth()]} ${saat(iso)}`;
}

function yerelTarih(deger: string): Date {
  // "2026-09-21" biçimi UTC olarak okunur; gün kaymasın diye yerel saate çekiyoruz.
  if (/^\d{4}-\d{2}-\d{2}$/.test(deger)) {
    const [y, a, g] = deger.split('-').map(Number);
    return new Date(y, a - 1, g);
  }
  return new Date(deger);
}

/**
 * YEREL gün: "2026-09-21". Sunucu da günleri yerel saatle yazdığı için
 * karşılaştırmalar bununla yapılmalı. `toISOString()` UTC verdiğinden gece
 * 00:00-03:00 arasında bir gün geri kalıyordu.
 */
export function gunMetni(gun: Date = new Date()): string {
  const iki = (s: number) => String(s).padStart(2, '0');
  return `${gun.getFullYear()}-${iki(gun.getMonth() + 1)}-${iki(gun.getDate())}`;
}

/** 5321234567 → 0532 123 45 67 */
export function telefonBicimle(ham: string): string {
  const s = ham.replace(/\D/g, '').slice(0, 10);
  const p = [s.slice(0, 3), s.slice(3, 6), s.slice(6, 8), s.slice(8, 10)].filter(Boolean);
  return p.join(' ');
}

/* ------------------------------ Etiketler ------------------------------ */

/**
 * YEDEK etiketler. Gerçek kaynak sunucudur (`ayarlar.py`): `/api/ben` yanıtı
 * `etiketler.sonuc` sözlüğünü getirir ve `etiketleriYaz` ile buraya yazılır.
 * Aksi halde aynı sonuç telefonda "Giremedim", raporda "Girilemedi" yazıyor ve
 * iki ekranı yan yana koyan yönetici farklı bir şey sanıyordu.
 */
export const SONUC_ETIKETLERI: Record<ZiyaretSonucu, string> = {
  satis: 'Satış',
  ilgilenmedi: 'İlgilenmedi',
  evde_yok: 'Evde yok',
  randevu: 'Randevu',
  altyapi_sorunu: 'Altyapı sorunu',
  girilemedi: 'Girilemedi',
  yanlis_adres: 'Bina burada değil',
};

let sunucuEtiketleri: Partial<Record<ZiyaretSonucu, string>> = {};

/** Sunucudan gelen etiket sözlüğünü yürürlüğe koyar. */
export function etiketleriYaz(sozluk?: Partial<Record<ZiyaretSonucu, string>> | null) {
  if (sozluk && Object.keys(sozluk).length) sunucuEtiketleri = sozluk;
}

export function sonucEtiketi(sonuc: ZiyaretSonucu): string {
  return sunucuEtiketleri[sonuc] ?? SONUC_ETIKETLERI[sonuc] ?? sonuc;
}

export const DURUM_ETIKETLERI: Record<BinaDurumu, string> = {
  bekliyor: 'Bekliyor',
  planli: 'Bugünkü listede',
  ziyaret_edildi: 'Gidildi',
  tekrar_gel: 'Tekrar gel',
  girilemedi: 'Girilemedi',
  altyapi_sorunu: 'Altyapı sorunu',
};

/** Rozet rengi sınıfı. */
export function durumRengi(durum: BinaDurumu): string {
  switch (durum) {
    case 'ziyaret_edildi':
      return 'yesil';
    case 'tekrar_gel':
      return 'amber';
    case 'altyapi_sorunu':
      return 'kirmizi';
    case 'girilemedi':
      return 'amber';
    case 'planli':
      return 'firsat';
    default:
      return '';
  }
}

/**
 * Kapı numarası alanı kaynakta bazen "Diğer", "-", "YOK" gibi dolgu değerler
 * içeriyor. Ekranda "No: Diğer" yazmak satışçıya hiçbir şey anlatmaz; bu
 * değerleri hiç göstermiyoruz.
 */
const ANLAMSIZ_KAPI_NO = new Set(['diger', 'diğer', 'yok', 'bilinmiyor', 'null', '-', '.', '0']);

export function kapiNo(deger?: string | null): string | null {
  const temiz = (deger ?? '').trim();
  if (!temiz) return null;
  if (ANLAMSIZ_KAPI_NO.has(temiz.toLocaleLowerCase('tr-TR'))) return null;
  return temiz;
}

/**
 * Kart altındaki adres satırı — SOKAK ÖNDE.
 *
 * Binayı sokakta bulmayı sağlayan tek bilgi sokak + kapı numarasıdır ve
 * eskiden mahalle adı öne geldiği için tam da bu kısım kesiliyordu
 * ("Dumlupınar · Atatürk/500. Blv. N…"). Aynı sitedeki blokların başlıkları
 * birebir aynı olduğundan kartları ayıran şey de buydu.
 */
export function adresSatiri(bina: {
  mahalle?: string | null;
  sokak?: string | null;
  cadde?: string | null;
  kapi_no?: string | null;
}): string {
  const yol = bina.sokak || bina.cadde || '';
  return yol || bina.mahalle || '';
}

/** Kapı numarası rozeti — asla kesilmez, hep görünür. */
export function kapiRozeti(bina: { kapi_no?: string | null }): string | null {
  const no = kapiNo(bina.kapi_no);
  return no ? `No ${no}` : null;
}

/**
 * Kartın ikinci satırı: bina adı (site + blok) + mahalle.
 *
 * BLOK HARFİ ŞART: aynı sitenin blokları aynı sokakta olduğu için kartları
 * ayıran tek şey odur ("DIMORA CITY K BLOK" ile "DIMORA CITY L BLOK").
 * Yalnız site adı yazılırsa iki kart birbirinin aynısı görünür.
 */
export function yerSatiri(bina: {
  mahalle?: string | null;
  site_adi?: string | null;
  ad?: string | null;
  baslik?: string | null;
}): string {
  const ad = (bina.baslik ?? bina.ad ?? bina.site_adi ?? '').trim();
  return [ad, bina.mahalle ?? ''].filter(Boolean).join(' · ');
}

/** Tam adres (bina ekranı). */
export function tamAdres(bina: {
  mahalle?: string | null;
  sokak?: string | null;
  cadde?: string | null;
  kapi_no?: string | null;
  ilce?: string | null;
  il?: string | null;
}): string {
  const yol = bina.sokak || bina.cadde || '';
  const no = kapiNo(bina.kapi_no);
  return [
    [yol, no ? `No: ${no}` : ''].filter(Boolean).join(' '),
    bina.mahalle,
    bina.ilce,
    bina.il ?? 'Bursa',
  ]
    .filter(Boolean)
    .join(', ');
}

/**
 * Kartın başlığı.
 *
 * Sunucu her bina kartında hazır `baslik` gönderir (site adı → sokak No → seri).
 * `ad` eş anlamlısı ve `site_adi` yalnız yedek; hiçbiri yoksa seri numarası
 * gösterilir — "Bina" yazan kart satışçıya hiçbir şey anlatmaz.
 */
export function binaBasligi(
  bina: Pick<GorevBinasi, 'ad' | 'site_adi'> & { baslik?: string | null; bina_serial?: string },
): string {
  return (
    bina.baslik?.trim() ||
    bina.ad?.trim() ||
    bina.site_adi?.trim() ||
    bina.bina_serial ||
    'Bina'
  );
}
