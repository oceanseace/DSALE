/**
 * TASKS hücre seçimi, Excel gibi: çapa (seçimin başladığı hücre) + etkin hücre; aradaki dikdörtgen seçilidir.
 * Hücreler satırın iş no'su + sütun kimliğiyle tutulur: canlı tazelemede satır yer değiştirse de seçim kaymaz.
 * Giriş: `useSecim(satirlar, sutunlar)`. Kim: Isler.tsx (kurar), Tablo.tsx (fare/klavye), DurumCubugu.tsx,
 * DolguRengi.tsx (seçili hücreler: dolgu yalnız onlara).
 */

import { useCallback, useMemo, useState } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import type { Sutun } from './sutunlar';

interface Hucre {
  no: string;
  c: string;
}
/** Seçili dikdörtgen: satır ve sütun indeksleri (dahil). */
export interface Alan {
  r1: number;
  r2: number;
  c1: number;
  c2: number;
}

export function useSecim(satirlar: IsSatir[], sutunlar: Sutun[]) {
  const [capa, setCapa] = useState<Hucre | null>(null);
  const [odak, setOdak] = useState<Hucre | null>(null);

  const satirNo = useMemo(() => new Map(satirlar.map((s, i) => [s.is_no, i])), [satirlar]);
  const sutunNo = useMemo(() => new Map(sutunlar.map((c, i) => [c.id, i])), [sutunlar]);

  const konum = useCallback(
    (h: Hucre | null): { r: number; c: number } | null => {
      if (!h) return null;
      const r = satirNo.get(h.no);
      if (r === undefined) return null;
      return { r, c: sutunNo.get(h.c) ?? 0 };
    },
    [satirNo, sutunNo],
  );

  /** Etkin hücre (klavyenin olduğu yer); satırı süzgeçle gizlendiyse null. */
  const etkin = useMemo(() => konum(odak), [konum, odak]);
  const alan: Alan | null = useMemo(() => {
    if (!etkin) return null;
    const a = konum(capa) ?? etkin;
    return {
      r1: Math.min(a.r, etkin.r),
      r2: Math.max(a.r, etkin.r),
      c1: Math.min(a.c, etkin.c),
      c2: Math.max(a.c, etkin.c),
    };
  }, [konum, capa, etkin]);

  const hucre = useCallback(
    (r: number, c: number): Hucre | null => {
      if (!satirlar.length || !sutunlar.length) return null;
      const rr = Math.max(0, Math.min(satirlar.length - 1, r));
      const cc = Math.max(0, Math.min(sutunlar.length - 1, c));
      return { no: satirlar[rr].is_no, c: sutunlar[cc].id };
    },
    [satirlar, sutunlar],
  );

  /** Hücreye git; `genislet` (Shift) ise çapa yerinde kalır. */
  const git = useCallback(
    (r: number, c: number, genislet = false) => {
      const h = hucre(r, c);
      if (!h) return;
      if (!genislet || !capa || !konum(capa)) setCapa(h);
      setOdak(h);
    },
    [hucre, capa, konum],
  );

  /** Dikdörtgen seç: (r1,c1) çapa, (r2,c2) etkin. */
  const alanSec = useCallback(
    (r1: number, c1: number, r2: number, c2: number) => {
      setCapa(hucre(r1, c1));
      setOdak(hucre(r2, c2));
    },
    [hucre],
  );

  const hepsi = useCallback(
    () => alanSec(0, 0, satirlar.length - 1, sutunlar.length - 1),
    [alanSec, satirlar.length, sutunlar.length],
  );
  const birak = useCallback(() => {
    setCapa(null);
    setOdak(null);
  }, []);

  /** Seçili hücreler (iş no + sütun kimliği): dolgu rengi yalnız bunlara uygulanır (Excel gibi). */
  const seciliHucreler = useCallback(
    (): Array<{ is_no: string; sutun: string }> => (alan ? alanHucreleri(satirlar, sutunlar, alan) : []),
    [alan, satirlar, sutunlar],
  );

  /** Seçimin kapsadığı satırlar (yukarıdan aşağı). */
  const seciliSatirlar = useCallback(
    (): IsSatir[] => (alan ? satirlar.slice(alan.r1, alan.r2 + 1) : []),
    [alan, satirlar],
  );

  return { alan, etkin, git, alanSec, hepsi, birak, seciliSatirlar, seciliHucreler };
}
export type Secim = ReturnType<typeof useSecim>;

/** Dikdörtgenin hücreleri (satır satır): { is_no, sutun }. */
export function alanHucreleri(
  satirlar: Array<Pick<IsSatir, 'is_no'>>,
  sutunlar: Array<Pick<Sutun, 'id'>>,
  alan: Alan,
): Array<{ is_no: string; sutun: string }> {
  const l: Array<{ is_no: string; sutun: string }> = [];
  for (let r = alan.r1; r <= alan.r2; r++) {
    const s = satirlar[r];
    if (!s) continue;
    for (let c = alan.c1; c <= alan.c2; c++) if (sutunlar[c]) l.push({ is_no: s.is_no, sutun: sutunlar[c].id });
  }
  return l;
}

/** Durum çubuğu: Excel'deki gibi Sayı (dolu hücre), seçili satır, sayısal hücrelerin Toplamı ve Ortalaması. */
export function secimOzeti(satirlar: IsSatir[], sutunlar: Sutun[], alan: Alan | null) {
  if (!alan) return null;
  let sayi = 0;
  let sayisal = 0;
  let toplam = 0;
  for (let r = alan.r1; r <= alan.r2; r++) {
    const s = satirlar[r];
    if (!s) continue;
    for (let c = alan.c1; c <= alan.c2; c++) {
      const k = sutunlar[c];
      if (!k) continue;
      const n = k.sayi?.(s);
      if (n !== null && n !== undefined) {
        sayi++;
        sayisal++;
        toplam += n;
      } else if (k.deger(s)) sayi++;
    }
  }
  return {
    sayi,
    satir: alan.r2 - alan.r1 + 1,
    hucre: (alan.r2 - alan.r1 + 1) * (alan.c2 - alan.c1 + 1),
    toplam: sayisal ? toplam : null,
    ortalama: sayisal ? toplam / sayisal : null,
  };
}
