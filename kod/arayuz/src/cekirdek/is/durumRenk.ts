/**
 * MAP nokta rengi: iş durumu → 5 renkten biri. TEK tablo burada (sunucudaki eşi: operasyon/v2/api.py
 * DURUM_RENK_VARSAYILAN). Administrator Ayarlar ▸ "Durum renkleri"nden değiştirir (PUT /api/isler/ayarlar
 * {durum_renkleri}); herkese GET /api/isler/ayarlar ile gelir ve `durumRenkleriniKur` ile buraya yazılır.
 * Kim: birimler/operasyon/isler/map/noktalar.ts (katOf), IsHaritasiEkrani (lejant + durum çubuğu),
 * cekirdek/konsol/AyarlarPaneli.tsx (düzenleme).
 */

import { useSyncExternalStore } from 'react';

/** Lejant renkleri (sıra lejant sırasıdır). */
export type DurumRengi = 'gri' | 'sari' | 'mavi' | 'kirmizi' | 'mor';

/** Renk tanımı: lejant adı ve haritadaki RGB. */
export const RENK_TANIMI: ReadonlyArray<{ renk: DurumRengi; ad: string; rgb: [number, number, number] }> = [
  { renk: 'gri', ad: 'Gri', rgb: [150, 158, 172] },
  { renk: 'sari', ad: 'Sarı', rgb: [254, 198, 0] },
  { renk: 'mavi', ad: 'Mavi', rgb: [64, 140, 255] },
  { renk: 'kirmizi', ad: 'Kırmızı', rgb: [232, 72, 72] },
  { renk: 'mor', ad: 'Mor', rgb: [168, 120, 240] },
];

/** Renklendirilen durumlar (BOSS statüsü; uygulamanın kendi durumu da bunlardan birine düşer). */
export type DurumAnahtari =
  | 'askiya_alindi'
  | 'ertelendi'
  | 'merkeze_gonderildi'
  | 'altyapi'
  | 'randevu_alindi'
  | 'acik_randevulu'
  | 'acik'
  | 'basladi'
  | 'konum_paylasildi';

/** Ayarlar ekranındaki sıra ve adlar. */
export const DURUM_ADI: ReadonlyArray<{ anahtar: DurumAnahtari; ad: string }> = [
  { anahtar: 'askiya_alindi', ad: 'Askıya alındı' },
  { anahtar: 'ertelendi', ad: 'Ertelendi' },
  { anahtar: 'merkeze_gonderildi', ad: 'Merkeze gönderildi' },
  { anahtar: 'altyapi', ad: 'Altyapı sorunu (uygulama)' },
  { anahtar: 'randevu_alindi', ad: 'Randevu alındı' },
  { anahtar: 'acik_randevulu', ad: 'Açık — randevusu var' },
  { anahtar: 'acik', ad: 'Açık — randevusuz' },
  { anahtar: 'basladi', ad: 'Başlandı' },
  { anahtar: 'konum_paylasildi', ad: 'Konum paylaşıldı' },
];

/** Varsayılan (kullanıcının 08.10 tarifi): mor yalnız askı · kırmızı ertelendi/merkeze · sarı randevulu ·
 *  gri randevusuz · mavi başlandı/konum paylaşıldı. */
export const DURUM_RENK_VARSAYILAN: Readonly<Record<DurumAnahtari, DurumRengi>> = {
  askiya_alindi: 'mor',
  ertelendi: 'kirmizi',
  merkeze_gonderildi: 'kirmizi',
  altyapi: 'kirmizi',
  randevu_alindi: 'sari',
  acik_randevulu: 'sari',
  acik: 'gri',
  basladi: 'mavi',
  konum_paylasildi: 'mavi',
};

export type DurumRenkleri = Record<DurumAnahtari, DurumRengi>;

const RENK_KUMESI = new Set<string>(RENK_TANIMI.map((r) => r.renk));

/** Sunucudan gelen (eksik/bozuk olabilen) eşleme → tam eşleme. */
export function durumRenkleriOku(v: unknown): DurumRenkleri {
  const out: DurumRenkleri = { ...DURUM_RENK_VARSAYILAN };
  if (v && typeof v === 'object')
    for (const [k, r] of Object.entries(v as Record<string, unknown>))
      if (k in out && typeof r === 'string' && RENK_KUMESI.has(r)) out[k as DurumAnahtari] = r as DurumRengi;
  return out;
}

let etkin: DurumRenkleri = { ...DURUM_RENK_VARSAYILAN };
let surum = 0;
const dinleyiciler = new Set<() => void>();

/** Eşlemeyi kur (ayarlar gelince / Administrator değiştirince); haritalar yeniden boyanır. */
export function durumRenkleriniKur(v: unknown): void {
  const y = durumRenkleriOku(v);
  if (JSON.stringify(y) === JSON.stringify(etkin)) return;
  etkin = y;
  surum += 1;
  dinleyiciler.forEach((f) => f());
}

export function durumRenkleri(): DurumRenkleri {
  return etkin;
}

/** Eşlemenin sürümü (değişince artar): MAP noktalarının yeniden hesaplanması için anahtar. */
export function useDurumRenkSurumu(): number {
  return useSyncExternalStore(
    (f) => {
      dinleyiciler.add(f);
      return () => dinleyiciler.delete(f);
    },
    () => surum,
  );
}

/** Lejantta kısa ad (aynı ad bir kez). */
const KISA_AD: Record<DurumAnahtari, string> = {
  askiya_alindi: 'Askıda',
  ertelendi: 'Ertelendi',
  merkeze_gonderildi: 'Merkeze',
  altyapi: 'Altyapı',
  randevu_alindi: 'Randevulu',
  acik_randevulu: 'Randevulu',
  acik: 'Randevusuz',
  basladi: 'Başlandı',
  konum_paylasildi: 'Konum',
};

/** Lejant/durum çubuğu adı: o renkteki durumlar ("Ertelendi · Merkeze"); hiçbiri yoksa rengin adı. Uygulamanın
 *  iç "Altyapı" durumu başka durumla aynı renkteyse adı yazılmaz (ipucunda görünür). */
export function renkEtiketi(renk: DurumRengi, esleme: DurumRenkleri = etkin): string {
  const l = DURUM_ADI.filter((d) => esleme[d.anahtar] === renk).map((d) => d.anahtar);
  const gorunen = l.length > 1 ? l.filter((a) => a !== 'altyapi') : l;
  const adlar = [...new Set(gorunen.map((a) => KISA_AD[a]))];
  return adlar.length ? adlar.join(' · ') : RENK_TANIMI.find((r) => r.renk === renk)?.ad ?? renk;
}

/** İpucu: o renkteki bütün durumların tam adı. */
export function renkIpucu(renk: DurumRengi, esleme: DurumRenkleri = etkin): string {
  const l = DURUM_ADI.filter((d) => esleme[d.anahtar] === renk).map((d) => d.ad);
  return l.length ? l.join(', ') : 'Bu renkte durum yok';
}
