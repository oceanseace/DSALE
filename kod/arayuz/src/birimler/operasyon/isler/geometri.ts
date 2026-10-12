/**
 * TASKS ızgarasının ölçüleri: satır/başlık yüksekliği, satır başı ("i") genişliği, donuk sütun sayısı
 * (Excel'deki "Bölmeleri dondur": başlık + ilk 2 sütun) ve her sütunun sol kenarı.
 * Giriş: `geometri(genislikler)`. Kim: Tablo.tsx, Baslik.tsx.
 */

/** Excel'deki gibi sık satır (Calibri 11 pt). */
export const SATIR_Y = 22;
/** Alan adları satırı. */
export const BAS_Y = 24;
/** İsteğe bağlı sütun harfleri satırı (A, B, C…). */
export const HARF_Y = 20;
/** Satır başı: satır numarası + "i" düğmesi. */
export const SATIR_BASI = 58;

/** Başlık bölümünün toplam yüksekliği (harf satırı açıksa onunla). */
export function basYuksekligi(harfler: boolean): number {
  return BAS_Y + (harfler ? HARF_Y : 0);
}

/** Excel sütun harfi: 0 → A, 25 → Z, 26 → AA. */
export function sutunHarfi(j: number): string {
  let s = '';
  for (let k = j + 1; k > 0; k = Math.floor((k - 1) / 26)) s = String.fromCharCode(65 + ((k - 1) % 26)) + s;
  return s;
}
export const DONUK = 2;

export interface Geometri {
  gen: number[];
  /** Sütunun içerikteki sol kenarı (satır başı dahil). */
  sol: number[];
  toplam: number;
  /** CSS grid-template-columns. */
  sablon: string;
  /** Kaymayan sol bölümün genişliği (satır başı + donuk sütunlar). */
  donukGen: number;
}

export function geometri(gen: number[]): Geometri {
  const sol: number[] = [];
  let x = SATIR_BASI;
  for (const g of gen) {
    sol.push(x);
    x += g;
  }
  const donukSon = Math.min(DONUK, gen.length) - 1;
  return {
    gen,
    sol,
    toplam: x,
    sablon: [SATIR_BASI, ...gen].map((g) => `${g}px`).join(' '),
    donukGen: donukSon >= 0 ? sol[donukSon] + gen[donukSon] : SATIR_BASI,
  };
}

/** İçerikteki x'e (satır başı dahil) düşen sütun; satır başındaysa -1. */
export function sutunBul(g: Geometri, x: number): number {
  if (x < SATIR_BASI) return -1;
  for (let j = 0; j < g.sol.length; j++) if (x < g.sol[j] + g.gen[j]) return j;
  return g.sol.length - 1;
}
