/**
 * Son aramalar — yalnız BİNA seçimleri (Location ID / site adı). Müşteri adı,
 * müşteri no, task no, kişi adı ASLA saklanmaz (kişisel veri). Cihazda, bu
 * tarayıcıda; okunamazsa (gizli pencere) liste boş döner, palet yine çalışır.
 */

const ANAHTAR = 'turkcell.arama.son';
const EN_COK = 6;

export interface SonArama {
  serial: string;
  baslik: string;
  loc?: string | null;
  alt?: string;
  lat?: number | null;
  lon?: number | null;
}

export function sonAramalar(): SonArama[] {
  try {
    const ham = localStorage.getItem(ANAHTAR);
    const liste = ham ? (JSON.parse(ham) as SonArama[]) : [];
    return Array.isArray(liste) ? liste.filter((x) => x && typeof x.serial === 'string').slice(0, EN_COK) : [];
  } catch {
    return [];
  }
}

export function sonAramaEkle(s: SonArama) {
  try {
    const liste = [s, ...sonAramalar().filter((x) => x.serial !== s.serial)].slice(0, EN_COK);
    localStorage.setItem(ANAHTAR, JSON.stringify(liste));
  } catch {
    /* yazılamazsa hatırlanmaz */
  }
}

export function sonAramalariSil() {
  try {
    localStorage.removeItem(ANAHTAR);
  } catch {
    /* önemsiz */
  }
}
