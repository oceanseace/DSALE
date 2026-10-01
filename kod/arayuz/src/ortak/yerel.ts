/**
 * Cihazda hatırlanan küçük tercihler (görünüm, başlangıç ekranı, kapatılan ipucu…).
 *
 * `localStorage` gizli sekmede, dolu diskte ya da kapatılmış site verisinde
 * hata fırlatabilir; o zaman tercih yalnız bu oturumda geçerli kalır, uygulama
 * yine çalışır. Bu yüzden her okuma/yazma buradan geçer.
 */

const bellek = new Map<string, string>();

export function yerelOku(anahtar: string): string | null {
  try {
    const deger = window.localStorage.getItem(anahtar);
    if (deger !== null) return deger;
  } catch {
    /* depolama kapalı: bellekteki kopyaya bak */
  }
  return bellek.get(anahtar) ?? null;
}

export function yerelYaz(anahtar: string, deger: string | null): void {
  if (deger === null) bellek.delete(anahtar);
  else bellek.set(anahtar, deger);
  try {
    if (deger === null) window.localStorage.removeItem(anahtar);
    else window.localStorage.setItem(anahtar, deger);
  } catch {
    /* yazılamadı: tercih yalnız bu oturumda geçerli */
  }
}

export function yerelJsonOku<T>(anahtar: string, yedek: T): T {
  const ham = yerelOku(anahtar);
  if (!ham) return yedek;
  try {
    return JSON.parse(ham) as T;
  } catch {
    return yedek;
  }
}

export function yerelJsonYaz(anahtar: string, deger: unknown): void {
  try {
    yerelYaz(anahtar, JSON.stringify(deger));
  } catch {
    /* döngüsel nesne vb. — sessizce geç */
  }
}
