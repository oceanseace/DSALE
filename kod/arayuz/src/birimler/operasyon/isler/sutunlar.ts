/**
 * TASKS tablosunun sütunları: sabit sütunlar (IsSatir alanları) + BOSS listesindeki BÜTÜN alanlar (`ek`).
 * Giriş: `useSutunlar(ekEtiketler, isler)` → Sutun[] (kimliği yalnız sütun kümesi değişince değişir);
 * varsayılan görünenler `VARSAYILAN_GORUNEN`.
 * Kim kullanır: Isler.tsx (kurar), Tablo.tsx (çizer), tabloSuzgec.ts (süzer/sıralar), excelAc.ts, secim.ts.
 */

import { useMemo, useRef } from 'react';
import type { EkDeger, IsaretRengi, IsSatir } from '../../../cekirdek/is/tipler';
import { DURUM_ETIKET } from '../../../cekirdek/is/tipler';
import { telefon10 } from '../../../cekirdek/ortak/KopyalaNo';

export interface Sutun {
  id: string;
  baslik: string;
  /** Varsayılan genişlik (px). */
  gen: number;
  grup: 'temel' | 'boss';
  /** Hücrede görünen ve kopyalanan metin ('' → boş). */
  deger: (s: IsSatir) => string;
  /** Otomatik süzgeçteki değer (verilmezse `deger`): tarihlerde yalnız gün. */
  suzgec?: (s: IsSatir) => string;
  /** Sıralama anahtarı (verilmezse `deger`). */
  sira?: (s: IsSatir) => string;
  /** Sayıysa sayı (durum çubuğunda Toplam, Excel'de sayı hücresi); değilse null. */
  sayi?: (s: IsSatir) => number | null;
  /** Uzun numara: Excel'e METİN olarak gitsin (05… ve 12+ hane bozulmasın). */
  numara?: boolean;
  /** Çok değerli süzgeç: `suzgec` değerleri COKLU_AYRAC ile birleştirir; ▾ listesinde her biri ayrı değerdir. */
  coklu?: boolean;
}

/** Çok değerli süzgeç değerlerinin ayracı (ekranda görünmez). */
export const COKLU_AYRAC = '\u001f';

/* ------------------------------ biçim ------------------------------ */

/** "2026-10-06 09:12:33" ya da "2026-10-06T09:12" → { gun: "06.10.2026", saat: "09:12" }. */
function tarihParca(m: string | null | undefined): { gun: string; saat: string } | null {
  const e = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(String(m ?? ''));
  if (!e) return null;
  return { gun: `${e[3]}.${e[2]}.${e[1]}`, saat: e[4] ? `${e[4]}:${e[5]}` : '' };
}

export function tarihSaat(m: string | null | undefined): string {
  const p = tarihParca(m);
  return p ? `${p.gun}${p.saat ? ` ${p.saat}` : ''}` : '';
}

/** Randevu: "07.10.2026 11:00–13:00" (Excel'de gün değişince anlamı değişmesin diye mutlak). */
function randevuMetni(s: IsSatir): string {
  if (!s.randevu) return '';
  const b = tarihParca(s.randevu.bas);
  const e = tarihParca(s.randevu.bit);
  if (!b) return '';
  return `${b.gun}${b.saat ? ` ${b.saat}` : ''}${e?.saat ? `–${e.saat}` : ''}`;
}

export const RENK_ADI: Record<IsaretRengi, string> = {
  sari: 'Sarı',
  kirmizi: 'Kırmızı',
  yesil: 'Yeşil',
  mavi: 'Mavi',
  mor: 'Mor',
  turuncu: 'Turuncu',
};

/**
 * Hücrenin dolgu rengi (Excel gibi hücre düzeyi): hücreye boyanan renk; yoksa satırın eski rengi (`isaret`, satırın
 * bütün hücrelerine uygulanır); hücrede 'yok' → satır rengi o hücrede kaldırılmış.
 */
export function hucreRengi(s: Pick<IsSatir, 'isaret' | 'hucre_renk'>, sutun: string): IsaretRengi | null {
  const h = s.hucre_renk?.[sutun];
  if (h === 'yok') return null;
  return h ?? s.isaret ?? null;
}

/** Hücrelere dolgu uygula (sunucudaki isaret.hucre_yaz ile aynı kural): renk → o renk (satır rengiyle aynıysa kayıt
 *  tutulmaz); null → satır rengi varsa 'yok', yoksa kayıt silinir. Yeni `hucre_renk` döner (eskisi değişmez). */
export function hucreBoya(
  s: Pick<IsSatir, 'isaret' | 'hucre_renk'>,
  sutunlar: string[],
  renk: IsaretRengi | null,
): Record<string, IsaretRengi | 'yok'> {
  const m = { ...(s.hucre_renk ?? {}) };
  const satir = s.isaret ?? null;
  for (const c of sutunlar) {
    const hedef = renk ?? (satir ? 'yok' : null);
    if (hedef === null || hedef === satir) delete m[c];
    else m[c] = hedef;
  }
  return m;
}

/** Satırdaki bütün dolgu renkleri (Renk sütunu): satır rengi + hücre renkleri, adlarıyla, sıralı. */
export function satirRenkleri(s: Pick<IsSatir, 'isaret' | 'hucre_renk'>): string {
  const k = new Set<IsaretRengi>();
  if (s.isaret) k.add(s.isaret);
  Object.values(s.hucre_renk ?? {}).forEach((r) => r !== 'yok' && k.add(r));
  return [...k].map((r) => RENK_ADI[r]).sort((a, b) => a.localeCompare(b, 'tr')).join(', ');
}

/** Uyarı simgeleri: kanal şikâyeti ⚠ · altyapı ⛔ · tekrar gelen iş ↻ (metin yok; açıklama hücrenin ipucunda). */
export const UYARI_SIMGESI: Record<string, string> = { kanal_sikayeti: '⚠', altyapi: '⛔', tekrar: '↻' };
/** Uyarı sütununun ▾ süzgeç değerleri (çok değerli: bir satır birden çok uyarı taşıyabilir). */
export const UYARI_ADI: Record<string, string> = { kanal_sikayeti: 'Kanal şikâyeti', altyapi: 'Altyapı', tekrar: 'Tekrar' };

/** Uyarı sütununun süzgeç değeri: uyarı adları ("Kanal şikâyeti", "Altyapı", "Tekrar"), COKLU_AYRAC ile. */
export function uyariSuzgec(s: IsSatir): string {
  return [...new Set((s.uyarilar ?? []).map((u) => UYARI_ADI[u.tur] ?? u.tur))].sort().join(COKLU_AYRAC);
}

/** Uyarı sütununun değeri: yalnız simgeler (süzgeç listesinde de "⚠", "⛔", "⛔ ⚠"). */
export function uyariMetni(s: IsSatir): string {
  const l = [...new Set((s.uyarilar ?? []).map((u) => UYARI_SIMGESI[u.tur] ?? '⚠'))];
  return l.sort().join(' ');
}

/* ------------------------------ sabit sütunlar ------------------------------ */

const TEMEL: Sutun[] = [
  { id: 'task', baslik: 'Task No', gen: 108, grup: 'temel', numara: true, deger: (s) => s.boss_task_no ?? '' },
  { id: 'musteri_no', baslik: 'Müşteri No', gen: 108, grup: 'temel', numara: true, deger: (s) => s.musteri_no ?? '' },
  { id: 'ad', baslik: 'Ad Soyad', gen: 170, grup: 'temel', deger: (s) => s.musteri_adi ?? '' },
  {
    id: 'tel',
    baslik: 'Telefon',
    gen: 104,
    grup: 'temel',
    numara: true,
    deger: (s) => (s.musteri_tel ? telefon10(s.musteri_tel) : ''),
  },
  { id: 'tur', baslik: 'Task adı', gen: 200, grup: 'temel', deger: (s) => s.task_adi ?? '' },
  { id: 'boss', baslik: 'BOSS durumu', gen: 130, grup: 'temel', deger: (s) => s.boss_durum ?? '' },
  { id: 'bizim', baslik: 'Bizim durum', gen: 124, grup: 'temel', deger: (s) => s.bizim_durum ?? '' },
  {
    id: 'randevu',
    baslik: 'Randevu',
    gen: 150,
    grup: 'temel',
    deger: randevuMetni,
    suzgec: (s) => tarihParca(s.randevu?.bas)?.gun ?? '',
    sira: (s) => s.randevu?.bas ?? '',
  },
  { id: 'ekip', baslik: 'Ekip', gen: 140, grup: 'temel', deger: (s) => s.atanan?.ad || s.boss_ekip || '' },
  { id: 'ilce', baslik: 'İlçe', gen: 100, grup: 'temel', deger: (s) => s.ilce ?? '' },
  { id: 'mahalle', baslik: 'Mahalle', gen: 140, grup: 'temel', deger: (s) => s.mahalle ?? '' },
  { id: 'kanal', baslik: 'Satış kanalı', gen: 130, grup: 'temel', deger: (s) => s.satis_kanali ?? '' },
  {
    id: 'gelis',
    baslik: 'Geliş tarihi',
    gen: 128,
    grup: 'temel',
    deger: (s) => tarihSaat(s.acilis),
    suzgec: (s) => tarihParca(s.acilis)?.gun ?? '',
    sira: (s) => s.acilis ?? '',
  },
  { id: 'uyari', baslik: 'Uyarı', gen: 56, grup: 'temel', deger: uyariMetni, suzgec: uyariSuzgec, coklu: true },
  { id: 'iliskili', baslik: 'İlişkili akış', gen: 200, grup: 'temel', deger: (s) => s.iliskili_akis ?? '' },
  // Varsayılanda gizli; "Sütunlar"dan açılır.
  { id: 'akis', baslik: 'Akış durumu', gen: 130, grup: 'temel', deger: (s) => DURUM_ETIKET[s.durum] ?? '' },
  { id: 'obek', baslik: 'Öbek', gen: 130, grup: 'temel', deger: (s) => s.obek?.ad ?? '' },
  { id: 'adres', baslik: 'Kısa adres', gen: 200, grup: 'temel', deger: (s) => s.kisa_adres ?? '' },
  { id: 'renk', baslik: 'Renk', gen: 80, grup: 'temel', deger: satirRenkleri },
];

/** Görev tanımındaki varsayılan görünür sütunlar (sırasıyla; "i" satır başında hep vardır). */
export const VARSAYILAN_GORUNEN = [
  'task', 'musteri_no', 'ad', 'tel', 'tur', 'boss', 'bizim', 'randevu', 'ekip', 'ilce', 'mahalle', 'kanal', 'gelis', 'uyari',
  'iliskili',
];

/* ------------------------------ BOSS (ek) sütunları ------------------------------ */

export const EK_ONEK = 'ek:';

function ekMetni(v: EkDeger | undefined): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'boolean') return v ? 'Evet' : 'Hayır';
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : '';
  const t = tarihParca(v);
  // ISO tarih ("2026-10-06T09:12:00") Türkçe biçimde; başka metin olduğu gibi.
  return t && /^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$/.test(v)
    ? `${t.gun}${t.saat ? ` ${t.saat}` : ''}`
    : v;
}

function ekSutunu(anahtar: string, baslik: string): Sutun {
  const ham = (s: IsSatir) => s.ek?.[anahtar];
  return {
    id: EK_ONEK + anahtar,
    baslik,
    gen: Math.min(220, Math.max(90, baslik.length * 8 + 34)),
    grup: 'boss',
    deger: (s) => ekMetni(ham(s)),
    sira: (s) => {
      const v = ham(s);
      return typeof v === 'string' ? v : ekMetni(v);
    },
    sayi: (s) => {
      const v = ham(s);
      return typeof v === 'number' && Number.isFinite(v) ? v : null;
    },
  };
}

/**
 * Bütün sütunlar: önce sabitler, sonra BOSS alanları (sunucunun `ek_etiketler` sırasıyla). Etiketi
 * gelmemiş ama satırlarda görülen alan da (ilk 300 satıra bakılır) ham adıyla eklenir.
 */
export function sutunlariKur(ekEtiketler: Record<string, string> | undefined, isler: IsSatir[]): Sutun[] {
  const ek: Sutun[] = [];
  const gorulen = new Set<string>();
  Object.entries(ekEtiketler ?? {}).forEach(([k, b]) => {
    gorulen.add(k);
    ek.push(ekSutunu(k, b || k));
  });
  for (let i = 0; i < Math.min(isler.length, 300); i++) {
    for (const k of Object.keys(isler[i].ek ?? {})) {
      if (!gorulen.has(k)) {
        gorulen.add(k);
        ek.push(ekSutunu(k, k));
      }
    }
  }
  return [...TEMEL, ...ek];
}

/** `sutunlariKur`, ama sütun kümesi aynı kaldıkça AYNI dizi (canlı tazelemede süzgeç önbelleği bozulmasın). */
export function useSutunlar(ekEtiketler: Record<string, string> | undefined, isler: IsSatir[]): Sutun[] {
  const onceki = useRef<{ imza: string; sutunlar: Sutun[] } | null>(null);
  return useMemo(() => {
    const yeni = sutunlariKur(ekEtiketler, isler);
    const imza = yeni.map((c) => `${c.id}=${c.baslik}`).join('|');
    if (onceki.current?.imza === imza) return onceki.current.sutunlar;
    onceki.current = { imza, sutunlar: yeni };
    return yeni;
  }, [ekEtiketler, isler]);
}
