/**
 * Keşif durumu (state) ve indirgeyici (reducer).
 *
 * Adres parametreleri (sözleşmenin Keşif eki — ARCHITECTURE.md §5):
 *   ?bolge=<1..N>       bölge seç
 *   ?ara=<metin>        arama kutusunu aç ve sorguyu uygula
 *   ?bina=<serial|i>    bina seç (serial ya da 0 tabanlı indeks)
 *   ?gorunum=2b|3b      2B (kuşbakışı) / 3B
 *   ?renk=bolge|firsat|penetrasyon
 *   ?katman=binalar,sinirlar,sutun,yollar,ofis   (virgüllü liste = AÇIK olanlar)
 */
import { urlOku } from '../core/url';

export type Metrik = 'bolge' | 'firsat' | 'penetrasyon';
export type Gorunum = '3b' | '2b';
export type KatmanAdi = 'binalar' | 'sinirlar' | 'sutun' | 'yollar' | 'ofis';
export type Katmanlar = Record<KatmanAdi, boolean>;

export const KATMAN_ADLARI: KatmanAdi[] = ['binalar', 'sinirlar', 'sutun', 'yollar', 'ofis'];

/** Tek bina seçimi */
export interface BinaSecimi {
  tur: 'bina';
  i: number;
}
/** Çoklu seçim (site grubu ya da mahalle) */
export interface GrupSecimi {
  tur: 'grup';
  baslik: string;
  alt: string;
  /** 'site' | 'mahalle' — kart başlığındaki tür etiketi */
  tip: 'site' | 'mahalle';
  indeksler: number[];
}
export type Secim = BinaSecimi | GrupSecimi | null;

export interface KesifDurumu {
  /** seçili bölge no (1..N) ya da null = tümü */
  secBolge: number | null;
  metrik: Metrik;
  katman: Katmanlar;
  gorunum: Gorunum;
  secim: Secim;
  /** arama kutusundaki metin */
  arama: string;
  /** sonuç listesi açık mı */
  aramaAcik: boolean;
}

export const VARSAYILAN_KATMANLAR: Katmanlar = {
  binalar: true,
  sinirlar: true,
  sutun: false,
  yollar: true,
  ofis: true,
};

export const VARSAYILAN_DURUM: KesifDurumu = {
  secBolge: null,
  metrik: 'bolge',
  katman: VARSAYILAN_KATMANLAR,
  gorunum: '3b',
  secim: null,
  arama: '',
  aramaAcik: false,
};

export type Eylem =
  | { tur: 'bolge'; no: number | null }
  | { tur: 'metrik'; deger: Metrik }
  | { tur: 'katman'; ad: KatmanAdi; acik?: boolean }
  | { tur: 'gorunum'; deger: Gorunum }
  | { tur: 'secim'; deger: Secim }
  | { tur: 'arama'; metin: string; acik?: boolean }
  | { tur: 'aramaAcik'; acik: boolean }
  | { tur: 'sifirla' };

export function indirge(d: KesifDurumu, e: Eylem): KesifDurumu {
  switch (e.tur) {
    case 'bolge':
      if (d.secBolge === e.no) return d;
      return { ...d, secBolge: e.no };
    case 'metrik':
      return d.metrik === e.deger ? d : { ...d, metrik: e.deger };
    case 'katman': {
      const acik = e.acik ?? !d.katman[e.ad];
      if (d.katman[e.ad] === acik) return d;
      return { ...d, katman: { ...d.katman, [e.ad]: acik } };
    }
    case 'gorunum':
      return d.gorunum === e.deger ? d : { ...d, gorunum: e.deger };
    case 'secim':
      return { ...d, secim: e.deger };
    case 'arama':
      return { ...d, arama: e.metin, aramaAcik: e.acik ?? e.metin.trim().length > 0 };
    case 'aramaAcik':
      return d.aramaAcik === e.acik ? d : { ...d, aramaAcik: e.acik };
    case 'sifirla':
      return { ...d, secBolge: null, secim: null, arama: '', aramaAcik: false };
  }
}

export interface Baslangic {
  durum: KesifDurumu;
  /** ?bolge — ilk karede uygulanır (plan N'i bilinmeden doğrulanamaz) */
  bolge: number | null;
  /** ?bina — serial ya da indeks metni */
  bina: string | null;
  /** ?ara — ilk karede uygulanır */
  ara: string | null;
}

/** Adres parametrelerinden başlangıç durumu (QA senaryoları buradan kurulur). */
export function urldenBaslangic(): Baslangic {
  const p = urlOku().ham;
  const oku = (ad: string) => {
    const v = p.get(ad);
    return v == null || v === '' ? null : v;
  };

  const renk = (oku('renk') ?? '').toLowerCase();
  const metrik: Metrik = renk === 'firsat' || renk === 'fırsat' ? 'firsat' : renk === 'penetrasyon' ? 'penetrasyon' : 'bolge';
  const gorunum: Gorunum = (oku('gorunum') ?? '').toLowerCase() === '2b' ? '2b' : '3b';

  let katman = VARSAYILAN_KATMANLAR;
  const kl = oku('katman');
  if (kl) {
    const acikOlanlar = new Set(kl.toLowerCase().split(',').map((s) => s.trim()));
    katman = KATMAN_ADLARI.reduce((o, ad) => ({ ...o, [ad]: acikOlanlar.has(ad) }), {} as Katmanlar);
  }

  const ara = oku('ara');
  const bolgeHam = oku('bolge');
  const bolge = bolgeHam != null && /^\d+$/.test(bolgeHam) ? Number(bolgeHam) : null;

  return {
    durum: {
      ...VARSAYILAN_DURUM,
      metrik,
      gorunum,
      katman,
      arama: ara ?? '',
      aramaAcik: !!ara,
    },
    bolge,
    bina: oku('bina'),
    ara,
  };
}
