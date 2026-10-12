/**
 * Kısa bildirim (toast). Bir işlem bittiğinde ekranın altında (masaüstünde
 * sağ üstte) kısa süre görünür. Kullanıcıya hiçbir şey sormaz, hiçbir şeyi
 * engellemez.
 *
 * `geriAl(yazi, calistir)`: 10 saniye duran "Geri al" düğmeli bildirim (§7.3
 * GeriAlBildirimi). Silme/taşıma gibi eylemler onay sormak yerine önce yapılır,
 * sonra geri alınabilir — bu, "emin misiniz?" sorusundan daha az yorar.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Onay, Uyari } from './Ikon';

type Tur = 'bilgi' | 'basari' | 'uyari';

interface Eylem {
  etiket: string;
  calistir: () => void | Promise<void>;
}

interface Kayit {
  id: number;
  tur: Tur;
  yazi: string;
  eylem?: Eylem;
}

interface BildirimDurumu {
  goster: (yazi: string, tur?: Tur, secenek?: { eylem?: Eylem; sureMs?: number }) => void;
  /** 10 sn "Geri al" düğmeli bildirim. */
  geriAl: (yazi: string, calistir: () => void | Promise<void>, sureMs?: number) => void;
}

const Baglam = createContext<BildirimDurumu | null>(null);

export function BildirimSaglayici({ children }: { children: ReactNode }) {
  const [kayitlar, setKayitlar] = useState<Kayit[]>([]);
  const sayacRef = useRef(0);

  const kaldir = useCallback((id: number) => {
    setKayitlar((onceki) => onceki.filter((k) => k.id !== id));
  }, []);

  const goster = useCallback(
    (yazi: string, tur: Tur = 'bilgi', secenek: { eylem?: Eylem; sureMs?: number } = {}) => {
      const id = ++sayacRef.current;
      // En çok İKİ bildirim birden. Üçü aynı anda göründüğünde listenin yarısını
      // kapatıyordu; hızlı çalışan satışçı arka arkaya kayıt giriyor.
      setKayitlar((onceki) => [...onceki.slice(-1), { id, tur, yazi, eylem: secenek.eylem }]);
      window.setTimeout(() => kaldir(id), secenek.sureMs ?? (secenek.eylem ? 10000 : 2600));
    },
    [kaldir],
  );

  const geriAl = useCallback(
    (yazi: string, calistir: () => void | Promise<void>, sureMs = 10000) => {
      goster(yazi, 'bilgi', { eylem: { etiket: 'Geri al', calistir }, sureMs });
    },
    [goster],
  );

  const deger = useMemo(() => ({ goster, geriAl }), [goster, geriAl]);

  return (
    <Baglam.Provider value={deger}>
      {children}
      <div className="bildirimler" role="status" aria-live="polite">
        {kayitlar.map((k) => (
          <div key={k.id} className={`bildirim ${k.tur}${k.eylem ? ' eylemli' : ''}`}>
            {k.tur === 'basari' ? <Onay boyut={20} /> : k.tur === 'uyari' ? <Uyari boyut={20} /> : null}
            <span className="bildirim-yazi">{k.yazi}</span>
            {k.eylem ? (
              <button
                type="button"
                className="bildirim-eylem"
                onClick={() => {
                  kaldir(k.id);
                  void k.eylem?.calistir();
                }}
              >
                {k.eylem.etiket}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </Baglam.Provider>
  );
}

export function useBildirim() {
  const deger = useContext(Baglam);
  if (!deger) throw new Error('BildirimSaglayici bulunamadı');
  return deger;
}
