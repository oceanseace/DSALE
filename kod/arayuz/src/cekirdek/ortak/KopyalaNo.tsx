/**
 * Numaranın kendisi kopyalama düğmesidir: Task No, Müşteri No, telefona dokununca
 * panoya kopyalanır ve kısa "kopyalandı" bildirimi çıkar. Ayrı "Kopyala" yazısı yok.
 */

import type { ReactNode } from 'react';
import { kopyala } from './kimlik';
import { useBildirim } from './Bildirim';

/** "0531 702 47 44" / "+90 531 702 4744" → "5317024744" (başında 0 ya da +90 olmadan 10 hane). */
export function telefon10(t: string | null | undefined): string {
  let d = String(t ?? '').replace(/\D/g, '');
  if (d.length > 10 && d.startsWith('90')) d = d.slice(2);
  while (d.length > 10 && d.startsWith('0')) d = d.slice(1);
  if (d.length === 11 && d.startsWith('0')) d = d.slice(1);
  return d;
}

/** Panoya kopyala + bildirim; başarıyı döndürür. */
export function useKopyala(): (metin: string, yazi?: string) => Promise<boolean> {
  const { goster } = useBildirim();
  return async (metin, yazi) => {
    const tamam = await kopyala(metin);
    if (tamam) goster(yazi ?? `${metin} kopyalandı`, 'basari');
    else goster('Kopyalanamadı. Metni seçip Ctrl+C ile kopyalayın.', 'uyari');
    return tamam;
  };
}

export function KopyalaNo({
  deger,
  children,
  sonra,
  className,
}: {
  /** Kopyalanacak metin; boşsa "—" yazılır, düğme olmaz. */
  deger: string | null | undefined;
  children?: ReactNode;
  /** Kopyalandıktan sonra (erişim kaydı gibi). */
  sonra?: () => void;
  className?: string;
}) {
  const kopya = useKopyala();
  const d = String(deger ?? '').trim();
  if (!d) return <span className={`o-kopyala-no bos${className ? ` ${className}` : ''}`}>—</span>;
  return (
    <button
      type="button"
      className={`o-kopyala-no${className ? ` ${className}` : ''}`}
      title="Kopyalamak için dokunun"
      onClick={async (o) => {
        o.stopPropagation();
        if (await kopya(d)) sonra?.();
      }}
    >
      {children ?? d}
    </button>
  );
}
