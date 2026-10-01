/** Teknik ekranlarının ortak kancaları. */

import { useEffect, useMemo, useState } from 'react';
import type { IslerimDeposu } from './depo';

/** Yarım dakikada bir tazelenen an (kalan süreler ve "ne zamandır" yazıları için). */
export function useDakika(): number {
  const [an, setAn] = useState(() => Date.now());
  useEffect(() => {
    const sayac = window.setInterval(() => {
      if (document.visibilityState === 'visible') setAn(Date.now());
    }, 30_000);
    return () => window.clearInterval(sayac);
  }, []);
  return an;
}

/** Depodaki işi numarasıyla bulur: açık, bugün biten ya da ofise dönen. */
export function useIs(depo: IslerimDeposu, isNo: string) {
  return useMemo(() => {
    const g = depo.gorunum;
    const acik = [...g.simdiki, ...g.bugun, ...g.sonraki].find((x) => x.is_no === isNo);
    if (acik) return { acik, biten: null, ofiste: null };
    const biten = g.bitenler.find((x) => x.is_no === isNo) ?? null;
    const ofiste = g.ofiseDonenler.find((x) => x.is_no === isNo) ?? null;
    return { acik: null, biten, ofiste };
  }, [depo.gorunum, isNo]);
}
