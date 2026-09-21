/**
 * Yönetmen — sahne/adım durum makinesi ve film (otomatik oynatma) zamanlayıcısı.
 *
 * Sahne ve adım 1 tabanlıdır. `ileri()` önce adımları, sonra sahneyi ilerletir;
 * son sahnenin son adımından sonra film modunda başa döner (yaklaşık 90 sn'lik döngü).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { Plan } from '../../data/types';
import type { SahneTanimi } from './tipler';

export interface YonetmenSecenekleri {
  sahneler: SahneTanimi[];
  plan: Plan;
  ilkSahne?: number | null;
  ilkAdim?: number | null;
  ilkFilm?: boolean;
}

export interface Yonetmen {
  sahne: number;
  adim: number;
  sahneSayisi: number;
  adimSayisi: number;
  film: boolean;
  /** etkin adımın film ilerlemesi 0..1 (film kapalıyken 0) */
  filmOran: number;
  ileri: () => void;
  geri: () => void;
  git: (sahne: number, adim?: number) => void;
  basa: () => void;
  sona: () => void;
  filmDegistir: (acik?: boolean) => void;
}

function kisitla(x: number, alt: number, ust: number): number {
  return x < alt ? alt : x > ust ? ust : x;
}

export function useYonetmen({ sahneler, plan, ilkSahne, ilkAdim, ilkFilm }: YonetmenSecenekleri): Yonetmen {
  const sahneSayisi = sahneler.length;

  const adimSayisiOf = useCallback(
    (sahne: number) => Math.max(1, sahneler[kisitla(sahne, 1, sahneSayisi) - 1]?.adimSayisi?.(plan) ?? 1),
    [sahneler, sahneSayisi, plan],
  );
  const adimSayisiRef = useRef(adimSayisiOf);
  adimSayisiRef.current = adimSayisiOf;

  const [durum, setDurum] = useState(() => {
    const s = kisitla(ilkSahne ?? 1, 1, sahneSayisi);
    const a = kisitla(ilkAdim ?? 1, 1, Math.max(1, sahneler[s - 1]?.adimSayisi?.(plan) ?? 1));
    return { sahne: s, adim: a };
  });
  const [film, setFilm] = useState(!!ilkFilm);
  const [filmOran, setFilmOran] = useState(0);

  // plan değişince (N değişimi) adım sayısı değişebilir → adımı kısıtla
  useEffect(() => {
    setDurum((d) => {
      const ust = adimSayisiRef.current(d.sahne);
      return d.adim > ust ? { ...d, adim: ust } : d;
    });
  }, [plan]);

  const git = useCallback(
    (sahne: number, adim = 1) => {
      const s = kisitla(Math.round(sahne), 1, sahneSayisi);
      setDurum({ sahne: s, adim: kisitla(Math.round(adim), 1, adimSayisiRef.current(s)) });
    },
    [sahneSayisi],
  );

  const ileri = useCallback(() => {
    setDurum((d) => {
      const ust = adimSayisiRef.current(d.sahne);
      if (d.adim < ust) return { sahne: d.sahne, adim: d.adim + 1 };
      if (d.sahne < sahneSayisi) return { sahne: d.sahne + 1, adim: 1 };
      return { sahne: 1, adim: 1 };
    });
  }, [sahneSayisi]);

  const geri = useCallback(() => {
    setDurum((d) => {
      if (d.adim > 1) return { sahne: d.sahne, adim: d.adim - 1 };
      if (d.sahne > 1) {
        const s = d.sahne - 1;
        return { sahne: s, adim: adimSayisiRef.current(s) };
      }
      return d;
    });
  }, []);

  const basa = useCallback(() => setDurum({ sahne: 1, adim: 1 }), []);
  const sona = useCallback(
    () => setDurum({ sahne: sahneSayisi, adim: adimSayisiRef.current(sahneSayisi) }),
    [sahneSayisi],
  );
  const filmDegistir = useCallback((acik?: boolean) => setFilm((f) => (acik == null ? !f : acik)), []);

  /* ---------------------------------------------------------------- film zamanlayıcısı */
  const sureMs = useMemo(() => {
    const s = sahneler[durum.sahne - 1];
    return Math.max(1200, s?.filmMs?.(durum.adim, plan) ?? 6000);
  }, [sahneler, durum.sahne, durum.adim, plan]);

  useEffect(() => {
    if (!film) {
      setFilmOran(0);
      return;
    }
    const bas = performance.now();
    setFilmOran(0);
    const sayac = setInterval(() => {
      setFilmOran(Math.min(1, (performance.now() - bas) / sureMs));
    }, 100);
    const zaman = setTimeout(ileri, sureMs);
    return () => {
      clearInterval(sayac);
      clearTimeout(zaman);
    };
  }, [film, sureMs, durum.sahne, durum.adim, ileri]);

  return {
    sahne: durum.sahne,
    adim: durum.adim,
    sahneSayisi,
    adimSayisi: adimSayisiOf(durum.sahne),
    film,
    filmOran,
    ileri,
    geri,
    git,
    basa,
    sona,
    filmDegistir,
  };
}
