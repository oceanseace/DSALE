/**
 * Harita tercihleri — cihaz başına hatırlanır (localStorage).
 *
 * "Uydu"yu seçen yönetici haritayı her açışında yeniden seçmek zorunda
 * kalmasın. Tarayıcı depolamayı kapatmışsa (gizli sekme, kurum ayarı) tercih
 * yalnız o oturumda geçerli olur; harita yine çalışır, hiçbir şey kırılmaz.
 */

import { useCallback, useState } from 'react';

const ONEK = 'saha.harita.';

function oku(anahtar: string): string | null {
  try {
    return localStorage.getItem(ONEK + anahtar);
  } catch {
    return null;
  }
}

function yaz(anahtar: string, deger: string) {
  try {
    localStorage.setItem(ONEK + anahtar, deger);
  } catch {
    /* depolama kapalı: tercih yalnız bu oturumda geçerli */
  }
}

/** Geçerli değerlerden biri olmak zorunda olan, cihazda saklanan seçim. */
export function useKaliciSecim<T extends string>(
  anahtar: string,
  varsayilan: T,
  gecerli: readonly T[],
): [T, (yeni: T) => void] {
  const [deger, setDeger] = useState<T>(() => {
    const saklanan = oku(anahtar);
    return saklanan && (gecerli as readonly string[]).includes(saklanan)
      ? (saklanan as T)
      : varsayilan;
  });
  const degistir = useCallback(
    (yeni: T) => {
      setDeger(yeni);
      yaz(anahtar, yeni);
    },
    [anahtar],
  );
  return [deger, degistir];
}
