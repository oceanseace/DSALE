/**
 * İlkeller — her ekranın kullandığı tek bileşen takımı (Fluent 2 temelli).
 * Stil: ilkel.css (yalnız tokenlar). Pencere: Onay.tsx · çekmece: Panel.tsx ·
 * ⋯ menü: Menu.tsx · tablo: Tablo.tsx.
 *
 * Yerleşik anlamlar (her ekranda aynı): ✕ kapatır · ← geri · büyüteç arar ·
 * çöp siler · kalem düzenler · ⋯ daha fazla. Sarı (birincil) ekranda TEK.
 */

import {
  forwardRef,
  useEffect,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react';
import { createPortal } from 'react-dom';
import { Buyutec, Kapat } from './Ikon';
import './bilesen.css';

const sinif = (...p: Array<string | false | null | undefined>) => p.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ Düğme */

export type DugmeTuru = 'ikincil' | 'birincil' | 'vurgu' | 'metin' | 'yikici' | 'yikici-metin' | 'yesil';

export interface DugmeOzellik extends ButtonHTMLAttributes<HTMLButtonElement> {
  tur?: DugmeTuru;
  boy?: 'kucuk' | 'orta' | 'buyuk';
  genis?: boolean;
  simge?: ReactNode;
}

export const Dugme = forwardRef<HTMLButtonElement, DugmeOzellik>(function Dugme(
  { tur = 'ikincil', boy = 'orta', genis, simge, className, children, type = 'button', ...p },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={sinif('o-dugme', tur !== 'ikincil' && tur, boy !== 'orta' && boy, genis && 'genis', className)}
      {...p}
    >
      {simge}
      {children}
    </button>
  );
});

export interface SimgeDugmeOzellik extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Ekran okuyucu + ipucu (zorunlu: simgenin anlamı). */
  etiket: string;
  kucuk?: boolean;
  yikici?: boolean;
  children: ReactNode;
}

export const SimgeDugme = forwardRef<HTMLButtonElement, SimgeDugmeOzellik>(function SimgeDugme(
  { etiket, kucuk, yikici, className, children, type = 'button', ...p },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={etiket}
      title={etiket}
      className={sinif('o-simge-dugme', kucuk && 'kucuk', yikici && 'yikici', className)}
      {...p}
    >
      {children}
    </button>
  );
});

/** ✕ — her yerde aynı kapatma düğmesi. */
export function KapatDugmesi({ kapat, etiket = 'Kapat', kucuk }: { kapat: () => void; etiket?: string; kucuk?: boolean }) {
  return (
    <SimgeDugme etiket={etiket} kucuk={kucuk} onClick={kapat}>
      <Kapat boyut={kucuk ? 14 : 16} kalinlik={2} />
    </SimgeDugme>
  );
}

/* ------------------------------------------------------------------ Girdi */

export const Girdi = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { kucuk?: boolean }>(
  function Girdi({ className, kucuk, ...p }, ref) {
    return <input ref={ref} className={sinif('o-girdi', kucuk && 'kucuk', className)} {...p} />;
  },
);

export const Secici = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Secici(
  { className, children, ...p },
  ref,
) {
  return (
    <select ref={ref} className={sinif('o-girdi', className)} {...p}>
      {children}
    </select>
  );
});

/** Etiket + denetim + (isteğe bağlı) açıklama/hata. */
export function Alan({
  etiket,
  aciklama,
  hata,
  children,
}: {
  etiket: ReactNode;
  aciklama?: ReactNode;
  hata?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="o-alan">
      <span className="etiket">{etiket}</span>
      {children}
      {hata ? <span className="hata">{hata}</span> : aciklama ? <span className="aciklama">{aciklama}</span> : null}
    </label>
  );
}

/** Büyüteç + metin + ✕ temizle. */
export function AramaKutusu({
  deger,
  degisti,
  yerTutucu = 'Ara',
  className,
  ...p
}: {
  deger: string;
  degisti: (yeni: string) => void;
  yerTutucu?: string;
  className?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'>) {
  return (
    <div className={sinif('o-arama', className)}>
      <Buyutec boyut={16} />
      <input
        type="search"
        value={deger}
        placeholder={yerTutucu}
        aria-label={yerTutucu}
        onChange={(o) => degisti(o.target.value)}
        onKeyDown={(o) => {
          if (o.key === 'Escape' && deger) {
            o.stopPropagation();
            degisti('');
          }
        }}
        {...p}
      />
      {deger ? <KapatDugmesi kucuk etiket="Temizle" kapat={() => degisti('')} /> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Sekmeler */

export interface Sekme<T extends string> {
  deger: T;
  etiket: ReactNode;
  sayi?: number;
}

export function Sekmeler<T extends string>({
  sekmeler,
  deger,
  degisti,
  etiket,
  className,
}: {
  sekmeler: Array<Sekme<T>>;
  deger: T;
  degisti: (yeni: T) => void;
  etiket: string;
  className?: string;
}) {
  return (
    <div className={sinif('o-sekmeler', className)} role="tablist" aria-label={etiket}>
      {sekmeler.map((s) => (
        <button
          key={s.deger}
          type="button"
          role="tab"
          aria-selected={s.deger === deger}
          tabIndex={s.deger === deger ? 0 : -1}
          onClick={() => degisti(s.deger)}
          onKeyDown={(o) => {
            if (o.key !== 'ArrowRight' && o.key !== 'ArrowLeft') return;
            const i = sekmeler.findIndex((x) => x.deger === deger);
            const j = (i + (o.key === 'ArrowRight' ? 1 : -1) + sekmeler.length) % sekmeler.length;
            degisti(sekmeler[j]!.deger);
          }}
        >
          {s.etiket}
          {s.sayi !== undefined ? <span className="sayi">{s.sayi.toLocaleString('tr-TR')}</span> : null}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Araç çubuğu */

export function AracCubugu({ etiket, children, className }: { etiket: string; children: ReactNode; className?: string }) {
  return (
    <div className={sinif('o-arac', className)} role="toolbar" aria-label={etiket}>
      {children}
    </div>
  );
}
export const AracBosluk = () => <span className="o-bosluk" />;
export const AracAyrac = () => <span className="o-arac-ayrac" aria-hidden="true" />;

/* ------------------------------------------------------------------ Durum çubuğu */

const YUVA_KIMLIGI = 'o-durum-yuva';

/** Kabuğun alt çubuğu: solda ekranın yuvası, sağda verilen öğeler (bağlantı). */
export function DurumCubugu({ children }: { children?: ReactNode }) {
  return (
    <footer className="o-durum-cubugu yon-durum" role="status" aria-live="polite">
      <div className="o-durum-yuva" id={YUVA_KIMLIGI} />
      {children}
    </footer>
  );
}

/** Ekranın durum çubuğuna yazdığı içerik (kayıt sayısı, seçim özeti…). Yuva yoksa hiçbir şey çizmez. */
export function DurumIcerigi({ children }: { children: ReactNode }) {
  const [yuva, setYuva] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setYuva(document.getElementById(YUVA_KIMLIGI));
  }, []);
  return yuva ? createPortal(<span>{children}</span>, yuva) : null;
}
