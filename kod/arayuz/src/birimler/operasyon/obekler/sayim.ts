/**
 * Öbek mahalle sayımı: "ilçenin tamamı" bir mahalle sayılmaz; sunucu o ilçenin sözlükteki
 * (başka öbeğe tek tek verilmemiş) bütün mahallelerini `mahalle_sayisi` olarak gönderir.
 */
import type { Obek, ObekMahalle } from '../../../cekirdek/is/tipler';

type Sayili = { mahalle_sayisi?: number };

export function mahalleSayisi(m: ObekMahalle): number {
  const n = (m as ObekMahalle & Sayili).mahalle_sayisi;
  return typeof n === 'number' ? n : 1;
}

export function obekMahalleSayisi(o: Obek): number {
  return o.mahalleler.reduce((t, m) => t + mahalleSayisi(m), 0);
}

export function mahalleEtiketi(m: ObekMahalle): string {
  if (!m.tum_ilce) return m.mahalle;
  const n = (m as ObekMahalle & Sayili).mahalle_sayisi;
  return typeof n === 'number' ? `${m.ilce} (tüm ilçe · ${n} mahalle)` : `${m.ilce} (tüm ilçe)`;
}
