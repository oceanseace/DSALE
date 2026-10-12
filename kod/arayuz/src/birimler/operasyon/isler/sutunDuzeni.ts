/**
 * TASKS sütun düzeni, kişi başına ve SUNUCUDA (tercihDeposu.ts): hangi sütunlar görünür, hangi sırada, kaç px.
 * Giriş: `useSutunDuzeni(sutunlar)` → { gorunen, genislik, goster, tasi, genislikYaz, varsayilan }.
 * Kim: Isler.tsx (kurar), Tablo.tsx (genişlik), SutunSecici.tsx (göster/gizle + SIRA: sürükle ya da ↑/↓).
 * VARSAYILAN_GORUNEN'e sonradan eklenen sütun, düzenini daha önce kaydetmiş kişide de sona eklenir (`bilinen`).
 * Adlı düzenler, unvan varsayılanı ve "Varsayılana dön": DuzenMenusu.tsx.
 */

import { useCallback, useMemo } from 'react';
import { VARSAYILAN_GORUNEN, type Sutun } from './sutunlar';
import { FABRIKA_DUZENI, duzenUygula, etkinDuzen, etkinYaz, useTercih, type Duzen } from './tercihDeposu';

/**
 * Sıra değişikliği ("Sütunlar" menüsünde sürükle ya da ↑/↓): `id`, listedeki `hedef` konumunun ÖNÜNE taşınır
 * (hedef = eski listedeki indeks, 0…uzunluk; uzunluk → en sona). Yeni dizi döner.
 */
export function yeniSira(liste: string[], id: string, hedef: number): string[] {
  const i = liste.indexOf(id);
  if (i < 0) return liste;
  const h = Math.max(0, Math.min(liste.length, hedef));
  if (h === i || h === i + 1) return liste;
  const l = liste.filter((x) => x !== id);
  l.splice(h > i ? h - 1 : h, 0, id);
  return l;
}

/** Kaydedildiğinden beri varsayılana eklenmiş sütunlar sona eklenir. */
function gecerliDuzen(d: Duzen): Duzen {
  if (!Array.isArray(d.bilinen)) return d;
  const yeni = VARSAYILAN_GORUNEN.filter((id) => !d.bilinen!.includes(id) && !d.gorunen.includes(id));
  return yeni.length ? { ...d, gorunen: [...d.gorunen, ...yeni] } : d;
}

export function useSutunDuzeni(sutunlar: Sutun[]) {
  const t = useTercih();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const duzen = useMemo(() => gecerliDuzen(etkinDuzen(t)), [t.etkin, t.unvan]);
  /** Her kayıtta o anki varsayılan listesi de yazılır (sonradan eklenen sütunu tanımak için). */
  const setDuzen = useCallback(
    (f: (d: Duzen) => Duzen) => etkinYaz((o) => ({ ...f(gecerliDuzen(o)), bilinen: VARSAYILAN_GORUNEN })),
    [],
  );

  const gorunen = useMemo(() => {
    const m = new Map(sutunlar.map((c) => [c.id, c]));
    return duzen.gorunen.map((id) => m.get(id)).filter((c): c is Sutun => Boolean(c));
  }, [sutunlar, duzen.gorunen]);

  const genislik = useCallback((c: Sutun) => duzen.gen[c.id] ?? c.gen, [duzen.gen]);

  const goster = useCallback(
    (id: string, acik: boolean) =>
      setDuzen((d) => ({
        ...d,
        gorunen: acik ? (d.gorunen.includes(id) ? d.gorunen : [...d.gorunen, id]) : d.gorunen.filter((x) => x !== id),
      })),
    [setDuzen],
  );

  /** `id`'yi `onceki`nin önüne taşı (null → en sona). */
  const tasi = useCallback(
    (id: string, onceki: string | null) =>
      setDuzen((d) => {
        const l = d.gorunen.filter((x) => x !== id);
        const i = onceki ? l.indexOf(onceki) : -1;
        l.splice(i < 0 ? l.length : i, 0, id);
        return { ...d, gorunen: l };
      }),
    [setDuzen],
  );

  /** Sütunlar menüsü: `id`'yi görünen listede `hedef` konumunun önüne taşı (yeniSira). */
  const siraYaz = useCallback(
    (id: string, hedef: number) => setDuzen((d) => ({ ...d, gorunen: yeniSira(d.gorunen, id, hedef) })),
    [setDuzen],
  );

  const genislikYaz = useCallback(
    (id: string, px: number) => setDuzen((d) => ({ ...d, gen: { ...d.gen, [id]: Math.max(40, Math.min(800, Math.round(px))) } })),
    [setDuzen],
  );

  /** Fabrika varsayılanı (sütunlar, genişlik, yakınlaştırma; süzgeçler değişmez). */
  const varsayilan = useCallback(() => duzenUygula(null, { ...FABRIKA_DUZENI, bilinen: VARSAYILAN_GORUNEN }), []);

  return {
    gorunen,
    gorunenIdler: duzen.gorunen,
    genislik,
    goster,
    tasi,
    siraYaz,
    genislikYaz,
    varsayilan,
    yakinlik: duzen.yakinlik ?? 100,
    /** Harf satırı (A, B, C…) Excel'deki gibi hep açık. */
    harfler: true,
    ad: duzen.ad ?? null,
    degisti: Boolean(duzen.degisti),
  };
}
export type SutunDuzeni = ReturnType<typeof useSutunDuzeni>;
