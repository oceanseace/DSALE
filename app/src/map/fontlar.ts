/**
 * deck.gl TextLayer için yerel font hazırlığı.
 * TextLayer font atlasını canvas ile çizer; font yüklenmeden atlas oluşturulursa yedek font kullanılır.
 * Bu yüzden harita açılmadan önce `fontlariYukle()` beklenir (main.tsx yapar).
 */
import { yazi } from '../ui/tema';

/** TextLayer karakter seti: ASCII + Türkçe + tipografik işaretler */
export const KARAKTER_SETI: string[] = (() => {
  const s = new Set<string>();
  for (let c = 32; c < 127; c++) s.add(String.fromCharCode(c));
  // U+2009 ince boşluk (aralikli()), U+202F kırılmaz dar boşluk (sayı + birim) — eksikse deck.gl
  // "Missing character" uyarısı verir ve etiketler boşluksuz görünür.
  for (const c of 'ÇçĞğİıÖöŞşÜüÂâÎîÛû·–—…‘’“”•°²³½¼¾%₺€→←↑↓×±−✓▲▼  ') s.add(c);
  return [...s];
})();

/** Harita etiketleri için font ayarları (SDF → keskin büyük yazı + kontur) */
export const HARITA_FONT = {
  fontFamily: yazi.harita,
  fontWeight: 700,
  characterSet: KARAKTER_SETI,
  fontSettings: { sdf: true, fontSize: 96, buffer: 12, radius: 18, cutoff: 0.22, smoothing: 0.12 },
} as const;

let _yukleme: Promise<void> | null = null;

/** Yerel fontları (Barlow Condensed 500-800, Inter) yükler; en fazla ~3 sn bekler. */
export function fontlariYukle(): Promise<void> {
  if (_yukleme) return _yukleme;
  const ornek = 'ÇĞİÖŞÜçğıöşü 0123456789';
  const istekler = [
    `500 48px "${yazi.harita}"`,
    `600 48px "${yazi.harita}"`,
    `700 48px "${yazi.harita}"`,
    `800 48px "${yazi.harita}"`,
    `400 28px "Inter Variable"`,
    `700 28px "Inter Variable"`,
  ].map((f) => document.fonts.load(f, ornek).catch(() => []));
  const zamanAsimi = new Promise<void>((r) => setTimeout(r, 3000));
  _yukleme = Promise.race([Promise.all(istekler).then(() => undefined), zamanAsimi]);
  return _yukleme;
}
