/**
 * Türkçe ekler: "Ali K.'ya atandı", "Emre Ş.'ye", "Görükle'de". Kısaltmada son
 * harfin okunuşu esas alınır (K → "ka" → 'ya; Ş → "şe" → 'ye).
 */

const INCE = 'eiöü';
const KALIN = 'aıou';
const UNLU = INCE + KALIN;

/** Harfin okunuşunun son ünlüsü: B → "be" → e, K → "ka" → a, H → "he" → e. */
function harfUnlusu(h: string): string {
  const k = h.toLocaleLowerCase('tr-TR');
  if (UNLU.includes(k)) return k;
  return k === 'k' ? 'a' : 'e';
}

function sonUnlu(metin: string): { unlu: string; unluyleBiter: boolean } {
  const temiz = metin.trim().replace(/[)\]"'’]+$/, '');
  if (temiz.endsWith('.')) {
    // Kısaltma: "Ali K." → K harfinin okunuşu
    const harf = temiz.slice(0, -1).slice(-1);
    const u = harfUnlusu(harf);
    return { unlu: u, unluyleBiter: true };
  }
  const k = temiz.toLocaleLowerCase('tr-TR');
  for (let i = k.length - 1; i >= 0; i--) {
    if (UNLU.includes(k[i])) return { unlu: k[i], unluyleBiter: i === k.length - 1 };
    if (/\d/.test(k[i])) break;
  }
  return { unlu: 'e', unluyleBiter: false };
}

/** Yönelme: "Ali K." → "Ali K.'ya", "Emre" → "Emre'ye", "Kaya" → "Kaya'ya", "Görükle" → "Görükle'ye". */
export function yonelme(ad: string): string {
  const { unlu, unluyleBiter } = sonUnlu(ad);
  const ince = INCE.includes(unlu);
  return `${ad}'${unluyleBiter ? 'y' : ''}${ince ? 'e' : 'a'}`;
}

/** Bulunma: "Görükle" → "Görükle'de", "Dumlupınar" → "Dumlupınar'da" (sert ünsüzde -te/-ta). */
export function bulunma(ad: string): string {
  const { unlu } = sonUnlu(ad);
  const ince = INCE.includes(unlu);
  const son = ad.trim().slice(-1).toLocaleLowerCase('tr-TR');
  const sert = 'fstkçşhp'.includes(son);
  return `${ad}'${sert ? 't' : 'd'}${ince ? 'e' : 'a'}`;
}

/** Ayrılma: "Yıldırım" → "Yıldırım'dan". */
export function ayrilma(ad: string): string {
  const { unlu } = sonUnlu(ad);
  const ince = INCE.includes(unlu);
  const son = ad.trim().slice(-1).toLocaleLowerCase('tr-TR');
  const sert = 'fstkçşhp'.includes(son);
  return `${ad}'${sert ? 't' : 'd'}${ince ? 'en' : 'an'}`;
}

/** Tamlayan: "Görükle" → "Görükle'nin", "Dumlupınar" → "Dumlupınar'ın". */
export function tamlayan(ad: string): string {
  const { unlu, unluyleBiter } = sonUnlu(ad);
  const e = { a: 'ı', ı: 'ı', o: 'u', u: 'u', e: 'i', i: 'i', ö: 'ü', ü: 'ü' }[unlu] ?? 'i';
  return `${ad}'${unluyleBiter ? 'n' : ''}${e}n`;
}
