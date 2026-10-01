/**
 * Süre metinleri — iş ekranlarının tek biçimi (§6.15 sözlüğü ile uyumlu).
 *
 *   45       → "45 dk"
 *   130      → "2 s 10 dk"
 *   1500     → "1 g 1 s"
 *   gecikme  → "Gecikti · 17 s"
 */

export function sureMetni(dakika: number | null | undefined): string {
  if (dakika === null || dakika === undefined || !Number.isFinite(dakika)) return '—';
  const dk = Math.max(0, Math.round(Math.abs(dakika)));
  if (dk < 60) return `${dk} dk`;
  const s = Math.floor(dk / 60);
  const kalan = dk % 60;
  if (s < 24) return kalan ? `${s} s ${kalan} dk` : `${s} s`;
  const g = Math.floor(s / 24);
  const ks = s % 24;
  return ks ? `${g} g ${ks} s` : `${g} g`;
}

/** Yalnız en büyük birim: "17 s", "3 g" (gecikme gibi kaba sürelerde). */
export function kabaSure(dakika: number): string {
  const dk = Math.max(0, Math.round(Math.abs(dakika)));
  if (dk < 60) return `${dk} dk`;
  const s = Math.floor(dk / 60);
  if (s < 48) return `${s} s`;
  return `${Math.floor(s / 24)} g`;
}

/** "AAAA-AA-GG SS:DD:ss" (sunucu, Türkiye saati) → Date. */
export function sunucuZamani(metin: string | null | undefined): Date | null {
  if (!metin) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(metin);
  if (!m) {
    const d = new Date(metin);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0));
}

/** "14:05" */
export function saatDakika(metin: string | null | undefined): string {
  const d = sunucuZamani(metin);
  if (!d) return '—';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
