/**
 * Küçük sevinçler (EK-6): "Atanmamış iş kalmadı", "Bugünün bütün BTK işleri
 * çözüldü" anlarında kısa, SESSİZ bir animasyon. 1,6 saniye sürer, hiçbir
 * şeye dokunulmasını engellemez (pointer-events yok), iş akışını bekletmez.
 *
 * Kapatılabilir: sunucu ayarı `kutlamalar` false ise ya da kişi cihazında
 * kapattıysa hiç görünmez. `prefers-reduced-motion` açıksa hareket yoktur;
 * yalnız cümle kısa bir bildirim olarak görünür.
 *
 *   const { kutla } = useKutlama();
 *   kutla('Atanmamış iş kalmadı');
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { yerelOku, yerelYaz } from './yerel';
import './bilesen.css';

const ANAHTAR = 'saha.kutlama';

interface KutlamaDurumu {
  kutla: (metin: string) => void;
  acik: boolean;
  degistir: (acik: boolean) => void;
}

const Baglam = createContext<KutlamaDurumu | null>(null);

export function KutlamaSaglayici({ children, sunucuIzni = true }: { children: ReactNode; sunucuIzni?: boolean }) {
  const [cihazAcik, setCihazAcik] = useState(() => yerelOku(ANAHTAR) !== '0');
  const [gosterilen, setGosterilen] = useState<{ id: number; metin: string } | null>(null);
  const sayac = useRef(0);
  const sonAn = useRef<Record<string, number>>({});

  const kutla = useCallback(
    (metin: string) => {
      if (!sunucuIzni || !cihazAcik) return;
      // Aynı an bir saat içinde ikinci kez kutlanmaz (liste yenilenince tekrar etmesin).
      const simdi = Date.now();
      if (simdi - (sonAn.current[metin] ?? 0) < 60 * 60 * 1000) return;
      sonAn.current[metin] = simdi;
      const id = ++sayac.current;
      setGosterilen({ id, metin });
      window.setTimeout(() => setGosterilen((g) => (g?.id === id ? null : g)), 2600);
    },
    [sunucuIzni, cihazAcik],
  );

  const degistir = useCallback((acik: boolean) => {
    yerelYaz(ANAHTAR, acik ? null : '0');
    setCihazAcik(acik);
  }, []);

  const deger = useMemo(
    () => ({ kutla, acik: sunucuIzni && cihazAcik, degistir }),
    [kutla, sunucuIzni, cihazAcik, degistir],
  );

  return (
    <Baglam.Provider value={deger}>
      {children}
      {gosterilen
        ? createPortal(
            <div key={gosterilen.id} className="o-kutlama" role="status" aria-live="polite">
              <div className="halka" aria-hidden="true">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6">
                  <path d="m5 12.5 4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {Array.from({ length: 8 }, (_, i) => (
                  <i key={i} style={{ ['--aci' as string]: `${i * 45}deg` }} />
                ))}
              </div>
              <span className="metin">{gosterilen.metin}</span>
            </div>,
            document.body,
          )
        : null}
    </Baglam.Provider>
  );
}

export function useKutlama(): KutlamaDurumu {
  return (
    useContext(Baglam) ?? {
      kutla: () => undefined,
      acik: false,
      degistir: () => undefined,
    }
  );
}

/**
 * Bir durum YANLIŞTAN DOĞRUYA döndüğü an bir kez kutlar (ilk çizimde değil):
 *
 *   useKutlamaGecisi(atanmamis === 0 && acik > 0, 'Atanmamış iş kalmadı');
 *   useKutlamaGecisi(btkBugun > 0 && btkAcik === 0, "Bugünün bütün BTK işleri çözüldü");
 *
 * Veri henüz yüklenmediyse `null` verin: geçiş sayılmaz.
 */
export function useKutlamaGecisi(kosul: boolean | null, metin: string): void {
  const { kutla } = useKutlama();
  const onceki = useRef<boolean | null>(null);
  useEffect(() => {
    if (kosul === null) return;
    if (onceki.current === false && kosul) kutla(metin);
    onceki.current = kosul;
  }, [kosul, metin, kutla]);
}
