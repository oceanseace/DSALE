/**
 * MAP noktalarının yumuşak geçişi: süzülmüş satırlar değişince noktalar yerinde güncellenir,
 * çıkan (kapanan ya da süzgeç dışına düşen) nokta solarak kaybolur, rengi değişen nokta nabız atar.
 * Sığdırma anahtarı noktalarla AYNI anda güncellenir: süzgeç değişince harita yeni noktalara sığar (eskilere değil).
 * Giriş: useNoktaGecisi(satirlar, anahtar). Çağıran: IsHaritasiEkrani (çıktısı MapTuval'e ve lejant sayımına gider).
 */

import { useEffect, useState } from 'react';
import type { IsSatir } from '../../../../cekirdek/is/tipler';
import { noktaYap, siraVer, type Nokta } from './noktalar';

/** Solan noktanın ekranda kaldığı süre (MapTuval'deki renk geçişiyle aynı). */
export const SOLMA_MS = 900;

export function useNoktaGecisi(
  satirlar: readonly IsSatir[],
  anahtar: string,
  /** Durum → renk eşlemesi değişince (Administrator Ayarlar) noktalar yeniden renklenir; harita sığdırılmaz. */
  renkSurumu = 0,
): { noktalar: Nokta[]; sigdirmaAnahtari: string } {
  const [noktalar, setNoktalar] = useState<Nokta[]>([]);
  const [sigdirmaAnahtari, setSigdirmaAnahtari] = useState('');

  useEffect(() => {
    setSigdirmaAnahtari(anahtar);
    const yeniler = new Map<string, Nokta>();
    for (const s of satirlar) {
      const n = noktaYap(s);
      if (n) yeniler.set(n.no, n);
    }
    const simdi = Date.now();
    setNoktalar((eski) => {
      // Güncelleyici saf olmalı (React geliştirmede iki kez çağırır): `yeni` burada kopyalanır, dıştaki bozulmaz.
      const yeni = new Map(yeniler);
      const sonuc: Nokta[] = [];
      for (const e of eski) {
        const g = yeni.get(e.no);
        if (g) {
          const degisti = e.kat !== g.kat && !e.cikis ? simdi : e.degisti;
          sonuc.push({ ...g, degisti });
          yeni.delete(e.no);
        } else if (!e.cikis) sonuc.push({ ...e, cikis: simdi });
        else if (simdi - e.cikis < SOLMA_MS) sonuc.push(e);
      }
      yeni.forEach((n) => sonuc.push(n));
      return siraVer(sonuc);
    });
  }, [satirlar, anahtar, renkSurumu]);

  /* Solan noktaları süre dolunca kaldır. */
  useEffect(() => {
    if (!noktalar.some((n) => n.cikis)) return undefined;
    const t = window.setTimeout(() => {
      const simdi = Date.now();
      setNoktalar((l) => l.filter((n) => !n.cikis || simdi - n.cikis < SOLMA_MS));
    }, SOLMA_MS + 50);
    return () => window.clearTimeout(t);
  }, [noktalar]);

  return { noktalar, sigdirmaAnahtari };
}
