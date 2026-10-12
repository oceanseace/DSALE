/**
 * MAP noktaları: açık iş satırı → haritadaki ışıyan nokta (renk sınıfı, ipucu metni, aynı binada sıra).
 * Giriş: noktaYap(satir), siraVer(noktalar), kayma(nokta), KATLAR/RENK (lejant). Renk eşlemesi: cekirdek/is/durumRenk.ts.
 * Çağıranlar: IsHaritasiEkrani (sayım, lejant), map/noktaGecisi.ts (solma), map/MapTuval.tsx (çizim).
 */

import { DURUM_ETIKET, type IsSatir } from '../../../../cekirdek/is/tipler';
import { RENK_TANIMI, durumRenkleri, type DurumAnahtari, type DurumRengi } from '../../../../cekirdek/is/durumRenk';

/** Nokta rengi = durum → renk eşlemesinin (cekirdek/is/durumRenk.ts; Administrator Ayarlar'dan değiştirir) sonucu. */
export type Kat = DurumRengi;
export type RGB = [number, number, number];
/** [boylam, enlem] — deck.gl sırası. */
export type Konum = [number, number];

/** Lejant sırası ve renkleri: gri · sarı · mavi · kırmızı · mor (adlar hangi durumların o renkte olduğunu söyler). */
export const KATLAR: ReadonlyArray<{ kat: Kat; ad: string; renk: RGB }> = RENK_TANIMI.map((r) => ({ kat: r.renk, ad: r.ad, renk: r.rgb }));
export const RENK = Object.fromEntries(KATLAR.map((k) => [k.kat, k.renk])) as Record<Kat, RGB>;
export const BOS_SAYIM = (): Record<Kat, number> => ({ gri: 0, sari: 0, mavi: 0, kirmizi: 0, mor: 0 });

/** Haritada gösterilmeyen (biten) durumlar. */
export const KAPALI_DURUM = new Set(['cozuldu', 'kapandi']);

/** Aynı binadaki işler arası kaydırma (piksel); halka düzeninde dizilir. */
const KAYMA_PX = 9;

export interface Nokta {
  no: string;
  lat: number;
  lon: number;
  kat: Kat;
  baslik: string;
  alt: string;
  /** Kapandı / süzgeç dışına çıktı: solarak çıkıyor (zaman damgası). */
  cikis?: number;
  /** Durumu (rengi) yeni değişti: nabız için zaman damgası. */
  degisti?: number;
  /** Aynı binada kaçıncı / kaç iş (kaydırma için). */
  sira?: number;
  adet?: number;
}

/**
 * BOSS statüsü → durum anahtarı (BOSS kesin kaynak; tanınmayan statüde uygulamanın durumu kullanılır).
 * BOSS listesinde randevu alınmış işler çoğu zaman hâlâ "Açık" görünür; randevu bilgisi ayrı alanlardadır
 * (boss_randevu_durumu "Randevulu", boss_randevu_bas/bit → satırın `randevu`'su). Bu yüzden "Açık" statüsünde randevu
 * varsa (BOSS'ta ya da uygulamada) durum "acik_randevulu" olur (canlı 08.10: 817 / 1.856 "Açık" işte).
 */
const BOSS_DURUM: Record<string, DurumAnahtari> = {
  'ASKIYA ALINDI': 'askiya_alindi',
  ERTELENDI: 'ertelendi',
  'MERKEZE GONDERILDI': 'merkeze_gonderildi',
  'RANDEVU ALINDI': 'randevu_alindi',
  BASLANDI: 'basladi',
  'KONUM PAYLASILDI': 'konum_paylasildi',
  ACIK: 'acik',
  RANDEVUSUZ: 'acik',
};

function bossSade(s: string): string {
  return s
    .toLocaleUpperCase('tr-TR')
    .replace(/[ÇĞİIÖŞÜ]/g, (c) => ({ Ç: 'C', Ğ: 'G', İ: 'I', I: 'I', Ö: 'O', Ş: 'S', Ü: 'U' })[c] ?? c)
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim();
}

/**
 * Bu oturumda uygulamadan yapılan atama/askı (iyimser renk): BOSS eşitlemesi (≈2 dk) yeni hâli getirene dek nokta
 * beklenen renkte görünsün (askı → hemen mor). İşin BOSS imzası (statü · randevu durumu · ekip) DEĞİŞİNCE, 10 dk
 * geçince ya da ⟳ (yerelTemizle) ile düşer: BOSS'ta yapılan değişiklik her zaman kazanır. Kim yazar: TopluAta,
 * IsCekmecesi, TopluAski (MAP ve TASKS'ta aynı).
 */
type BossImzaAlanlari = Pick<IsSatir, 'is_no' | 'boss_durum'> & { boss_randevu_durumu?: string | null; boss_ekip?: string | null };
const YEREL = new Map<string, { durum: DurumAnahtari; imza: string; an: number }>();
const YEREL_MS = 10 * 60_000;
/** BOSS'tan gelen, rengi belirleyen alanların imzası (eşitleme bunlardan birini değiştirince iyimser renk düşer). */
export const bossImzasi = (s: Omit<BossImzaAlanlari, 'is_no'>): string =>
  [s.boss_durum ?? '', s.boss_randevu_durumu ?? '', s.boss_ekip ?? ''].join('|');
export function yerelKatYaz(satirlar: BossImzaAlanlari[], durum: DurumAnahtari): void {
  const an = Date.now();
  satirlar.forEach((s) => YEREL.set(s.is_no, { durum, imza: bossImzasi(s), an }));
}
/** ⟳ (tam tazeleme): iyimser renklerin hepsi düşer; noktalar yalnız sunucunun (BOSS'un) hâlinden boyanır. */
export function yerelTemizle(): void {
  YEREL.clear();
}

/** İşin renklendirilen durumu (BOSS statüsü + randevu; yoksa uygulamanın durumu). */
export function durumAnahtari(s: IsSatir): DurumAnahtari {
  const y = YEREL.get(s.is_no);
  if (y) {
    if (bossImzasi(s) === y.imza && Date.now() - y.an < YEREL_MS) return y.durum;
    YEREL.delete(s.is_no);
  }
  const b = s.boss_durum ? BOSS_DURUM[bossSade(s.boss_durum)] : undefined;
  if (b === 'acik') return randevuVar(s) ? 'acik_randevulu' : 'acik';
  return b ?? durumKati(s);
}

/** Noktanın rengi: durum → renk eşlemesi (Administrator değiştirebilir). */
export function katOf(s: IsSatir): Kat {
  return durumRenkleri()[durumAnahtari(s)];
}

/** BOSS'ta ("Randevulu" / randevu saati) ya da uygulamada randevu var mı. */
export function randevuVar(s: Pick<IsSatir, 'randevu' | 'durum'> & { boss_randevu_durumu?: string | null }): boolean {
  if (s.randevu || s.durum === 'randevulu') return true;
  const d = s.boss_randevu_durumu ? bossSade(s.boss_randevu_durumu) : '';
  return d === 'RANDEVULU' || d === 'RANDEVU ALINDI';
}

/** Uygulamanın kendi durumundan durum anahtarı (BOSS statüsü tanınmazsa; eylem sonrası beklenen renk). */
export function durumKati(s: Pick<IsSatir, 'durum' | 'randevu'>): DurumAnahtari {
  if (s.durum === 'yolda' || s.durum === 'sahada') return 'basladi';
  if (s.durum === 'askida') return 'askiya_alindi';
  if (s.durum === 'merkeze') return 'merkeze_gonderildi';
  if (s.durum === 'altyapi') return 'altyapi';
  if (s.durum === 'randevulu' || s.randevu) return 'acik_randevulu';
  return 'acik';
}

/** Konumsuz ya da biten iş nokta olmaz (null). */
export function noktaYap(s: IsSatir): Nokta | null {
  if (s.lat === null || s.lon === null || KAPALI_DURUM.has(s.durum)) return null;
  const yer = [s.ilce, s.mahalle].filter(Boolean).join(' · ');
  return {
    no: s.is_no,
    lat: s.lat,
    lon: s.lon,
    kat: katOf(s),
    baslik: `${s.task_adi} · ${DURUM_ETIKET[s.durum]}`,
    alt: [yer, s.atanan?.ad].filter(Boolean).join(' · '),
  };
}

/** Aynı binadaki (5 basamak eşit koordinat) işlere sıra ve adet verir; yeni dizi döner. */
export function siraVer(noktalar: Nokta[]): Nokta[] {
  const yer = new Map<string, Nokta[]>();
  const kopya = noktalar.map((n) => ({ ...n }));
  for (const n of kopya) {
    const k = `${n.lat.toFixed(5)},${n.lon.toFixed(5)}`;
    const l = yer.get(k);
    if (l) l.push(n);
    else yer.set(k, [n]);
  }
  yer.forEach((l) =>
    l
      .sort((a, b) => a.no.localeCompare(b.no))
      .forEach((n, i) => {
        n.sira = i;
        n.adet = l.length;
      }),
  );
  return kopya;
}

/** Noktanın ekrandaki kaydırması (piksel): aynı binadaki işler halka şeklinde yana dizilir. */
export function kayma(n: Nokta): [number, number] {
  if (!n.adet || n.adet < 2 || n.sira === undefined) return [0, 0];
  const aci = (n.sira / Math.min(n.adet, 8)) * Math.PI * 2;
  const r = KAYMA_PX * (1 + Math.floor(n.sira / 8) * 0.9);
  return [Math.cos(aci) * r, -Math.sin(aci) * r];
}
