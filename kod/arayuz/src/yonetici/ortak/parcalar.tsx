/** Yönetici ekranlarının ortak küçük parçaları: sayı kutusu, tablo, boş durum… */

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { sayi, yuzde } from '../../ortak/bicim';
import { SahaHatasi } from '../../api/istemci';

/* ------------------------------ Veri çekme ------------------------------ */

export interface VeriDurumu<T> {
  veri: T | null;
  yukleniyor: boolean;
  hata: string | null;
  yenile: () => void;
  sonGuncelleme: Date | null;
}

/**
 * Tek bir uçtan veri çeker; `yenile()` ile tazelenir, `araMs` verilirse
 * kendi kendine tazeler. Yenilemede eldeki veri ekranda kalır (ekran zıplamaz).
 */
export function useVeri<T>(
  getir: () => Promise<T>,
  bagimliliklar: unknown[],
  araMs = 0,
): VeriDurumu<T> {
  const [veri, setVeri] = useState<T | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [sonGuncelleme, setSonGuncelleme] = useState<Date | null>(null);
  const getirRef = useRef(getir);
  getirRef.current = getir;
  const canli = useRef(true);

  useEffect(() => {
    canli.current = true;
    return () => {
      canli.current = false;
    };
  }, []);

  const calistir = useCallback(async (ilk: boolean) => {
    if (ilk) setYukleniyor(true);
    try {
      const sonuc = await getirRef.current();
      if (!canli.current) return;
      setVeri(sonuc);
      setHata(null);
      setSonGuncelleme(new Date());
    } catch (h) {
      if (!canli.current) return;
      setHata(h instanceof SahaHatasi ? h.message : 'Veri alınamadı.');
    } finally {
      if (canli.current) setYukleniyor(false);
    }
  }, []);

  useEffect(() => {
    void calistir(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, bagimliliklar);

  useEffect(() => {
    if (!araMs) return;
    const sayac = setInterval(() => {
      if (document.visibilityState === 'visible') void calistir(false);
    }, araMs);
    return () => clearInterval(sayac);
  }, [araMs, calistir, ...bagimliliklar]); // eslint-disable-line react-hooks/exhaustive-deps

  const yenile = useCallback(() => {
    void calistir(false);
  }, [calistir]);

  return { veri, yukleniyor, hata, yenile, sonGuncelleme };
}

/* ------------------------------ Sayı kutusu ------------------------------ */

export function SayiKutusu({
  etiket,
  deger,
  ek,
  renk,
  simge,
}: {
  etiket: string;
  deger: ReactNode;
  ek?: ReactNode;
  renk?: 'yesil' | 'amber' | 'kirmizi' | 'mavi';
  simge?: ReactNode;
}) {
  return (
    <div className={`yon-sayi${renk ? ' ' + renk : ''}`}>
      <div className="etiket">
        {simge}
        {etiket}
      </div>
      <div className="deger">{deger}</div>
      {ek ? <div className="ek">{ek}</div> : null}
    </div>
  );
}

/* ------------------------------ Kart ------------------------------ */

export function Kart({
  baslik,
  altYazi,
  sag,
  children,
  sikis = false,
}: {
  baslik?: string;
  altYazi?: ReactNode;
  sag?: ReactNode;
  children: ReactNode;
  sikis?: boolean;
}) {
  return (
    <section className={`yon-kart${sikis ? ' sikis' : ''}`}>
      {baslik ? (
        <div className="yon-kart-bas" style={sikis ? { padding: '16px 18px 0' } : undefined}>
          <div style={{ minWidth: 0 }}>
            <h2>{baslik}</h2>
            {altYazi ? <div className="alt">{altYazi}</div> : null}
          </div>
          {sag ? <div className="sag">{sag}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

/* ------------------------------ Oran çubuğu ------------------------------ */

export function OranCubugu({ oran }: { oran: number }) {
  const genislik = Math.max(0, Math.min(1, oran)) * 100;
  return (
    <div className="oran-hucre">
      <div className="yol">
        <span style={{ width: `${genislik}%` }} />
      </div>
      <span className="deger">{yuzde(oran, oran > 0 && oran < 0.1 ? 1 : 0)}</span>
    </div>
  );
}

/* ------------------------------ Durum bilgileri ------------------------------ */

export function BosDurumKutusu({
  simge,
  baslik,
  aciklama,
  children,
}: {
  simge: string;
  baslik: string;
  aciklama?: string;
  children?: ReactNode;
}) {
  return (
    <div className="yon-bos">
      <div className="simge" aria-hidden="true">
        {simge}
      </div>
      <h3>{baslik}</h3>
      {aciklama ? <p>{aciklama}</p> : null}
      {children ? <div style={{ marginTop: 14 }}>{children}</div> : null}
    </div>
  );
}

export function HataKutusu({ mesaj, yenile }: { mesaj: string; yenile?: () => void }) {
  return (
    <div className="yon-uyari kirmizi">
      <span>{mesaj}</span>
      {yenile ? (
        <span className="sag">
          <button className="yd" onClick={yenile}>
            Tekrar dene
          </button>
        </span>
      ) : null}
    </div>
  );
}

export function Iskelet({ yukseklik = 120 }: { yukseklik?: number }) {
  return <div className="yon-iskelet" style={{ height: yukseklik }} aria-hidden="true" />;
}

/* ------------------------------ Kişi baş harfi ------------------------------ */

/** Kişi rozeti renkleri tokendır (temel.css --kisi-1…8): koyu temada da beyaz yazı ≥ 4,5:1. */
const RENKLER = Array.from({ length: 8 }, (_, i) => `var(--kisi-${i + 1})`);

/**
 * Baş harf rozeti.
 *
 * "Hasan Bey (yönetici)" adından "H(" çıkıyordu: parantez içi ve unvanlar
 * ayıklanır, yalnız harfler kalır.
 */
const UNVANLAR = new Set(['bey', 'hanım', 'hanim', 'bay', 'sayın', 'sayin']);

export function basHarfler(ad: string): string {
  const temiz = (ad ?? '')
    .replace(/\(.*?\)/g, ' ')
    .replace(/[^\p{L}\s]/gu, ' ')
    .trim();
  const parcalar = temiz
    .split(/\s+/)
    .filter(Boolean)
    .filter((p) => !UNVANLAR.has(p.toLocaleLowerCase('tr-TR')));
  if (!parcalar.length) return '?';
  const ilk = parcalar[0][0] ?? '';
  const son = parcalar.length > 1 ? (parcalar[parcalar.length - 1][0] ?? '') : '';
  return (ilk + son).toLocaleUpperCase('tr-TR');
}

export function kisiRengi(anahtar: number | string): string {
  const sayisal =
    typeof anahtar === 'number'
      ? anahtar
      : Array.from(anahtar).reduce((t, h) => t + h.charCodeAt(0), 0);
  return RENKLER[Math.abs(sayisal) % RENKLER.length];
}

export function BasHarf({ ad, anahtar, boyut }: { ad: string; anahtar: number | string; boyut?: number }) {
  return (
    <span
      className="bas-harf"
      style={{
        background: kisiRengi(anahtar),
        ...(boyut ? { width: boyut, height: boyut, flexBasis: boyut, fontSize: Math.max(12, boyut * 0.38) } : null),
      }}
      aria-hidden="true"
    >
      {basHarfler(ad)}
    </span>
  );
}

/* ------------------------------ Sayı + etiket ------------------------------ */

export function MiniSayi({
  deger,
  etiket,
  yesil = false,
}: {
  deger: number;
  etiket: string;
  yesil?: boolean;
}) {
  return (
    <div className={`mini-sayi${yesil && deger > 0 ? ' yesil' : ''}`}>
      <div className="deger">{sayi(deger)}</div>
      <div className="etiket">{etiket}</div>
    </div>
  );
}

/* ------------------------------ Segment ------------------------------ */

export function Segment<T extends string>({
  secenekler,
  deger,
  degisti,
  etiket,
}: {
  secenekler: Array<{ deger: T; etiket: string }>;
  deger: T;
  degisti: (yeni: T) => void;
  etiket?: string;
}) {
  return (
    <div className="yon-segment" role="group" aria-label={etiket}>
      {secenekler.map((s) => (
        <button
          key={s.deger}
          className={deger === s.deger ? 'secili' : undefined}
          aria-pressed={deger === s.deger}
          onClick={() => degisti(s.deger)}
        >
          {s.etiket}
        </button>
      ))}
    </div>
  );
}
