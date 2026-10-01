/**
 * Saat: bir hedefe ne kaldığını CANLI yazar (§7.3).
 *
 * Sunucu saati ile cihaz saati farklı olabilir (telefonun saati 3 dk ileri);
 * `sunucuZamani` verilirse fark bir kez ölçülür ve hep düzeltilir. Dakikada
 * bir yenilenir; son 60 dakikada saniyede bir. Sekme arkadayken durur.
 */

import { useEffect, useMemo, useState } from 'react';
import { sunucuZamani as coz, sureMetni } from './sure';

export function useSimdi(hedefMs: number | null, sunucuFarkMs = 0): number {
  const [simdi, setSimdi] = useState(() => Date.now() + sunucuFarkMs);
  useEffect(() => {
    let sayac = 0;
    const kur = () => {
      const kalan = hedefMs === null ? Infinity : hedefMs - (Date.now() + sunucuFarkMs);
      const adim = Math.abs(kalan) < 60 * 60 * 1000 ? 1000 : 30 * 1000;
      sayac = window.setTimeout(() => {
        if (document.visibilityState === 'visible') setSimdi(Date.now() + sunucuFarkMs);
        kur();
      }, adim);
    };
    kur();
    return () => window.clearTimeout(sayac);
  }, [hedefMs, sunucuFarkMs]);
  return simdi;
}

/** Sunucu zamanı metninden cihaz farkı (ms). */
export function sunucuFarki(sunucuZamaniMetni: string | null | undefined): number {
  const d = coz(sunucuZamaniMetni);
  return d ? d.getTime() - Date.now() : 0;
}

export function Saat({
  hedef,
  sunucuZamani,
  bicim = 'kalan',
}: {
  /** Hedef an (sunucu biçimi). */
  hedef: string;
  /** Yanıttaki `sunucu_zamani` (cihaz saati farkı için). */
  sunucuZamani?: string | null;
  /** 'kalan' → "2 s 10 dk kaldı" / "17 dk geçti"; 'sayac' → "01:59:12". */
  bicim?: 'kalan' | 'sayac';
}) {
  const fark = useMemo(() => sunucuFarki(sunucuZamani), [sunucuZamani]);
  const hedefMs = useMemo(() => coz(hedef)?.getTime() ?? null, [hedef]);
  const simdi = useSimdi(hedefMs, fark);
  if (hedefMs === null) return <span>—</span>;
  const kalanMs = hedefMs - simdi;
  if (bicim === 'sayac') {
    const t = Math.max(0, Math.floor(Math.abs(kalanMs) / 1000));
    const s = Math.floor(t / 3600);
    const d = Math.floor((t % 3600) / 60);
    const sn = t % 60;
    const metin = [s, d, sn].map((x) => String(x).padStart(2, '0')).join(':');
    return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{kalanMs < 0 ? `−${metin}` : metin}</span>;
  }
  const dk = kalanMs / 60000;
  return (
    <span style={{ fontVariantNumeric: 'tabular-nums' }}>
      {dk >= 0 ? `${sureMetni(dk)} kaldı` : `${sureMetni(-dk)} geçti`}
    </span>
  );
}
