/**
 * Türkçe harf duyarsız arama: "gursu" → "Gürsu", "GOCMEN" → "Göçmen",
 * "ISIK" → "Işık". Aranan da aranılan da aynı biçime katlanır.
 */

const HARF: Record<string, string> = {
  ç: 'c', ğ: 'g', ı: 'i', i: 'i', ö: 'o', ş: 's', ü: 'u', â: 'a', î: 'i', û: 'u',
};

export function katla(metin: unknown): string {
  if (metin === null || metin === undefined) return '';
  return String(metin)
    .toLocaleLowerCase('tr-TR')
    .replace(/[çğıiöşüâîû]/g, (h) => HARF[h] ?? h)
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/** Aranan sözcüklerin HEPSİ metinde geçiyor mu? ("görükle btk" iki sözcük) */
export function eslesir(metin: string, sorgu: string): boolean {
  const s = katla(sorgu).trim();
  if (!s) return true;
  const m = katla(metin);
  return s.split(/\s+/).every((p) => m.includes(p));
}
