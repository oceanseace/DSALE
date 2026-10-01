/**
 * İmleç ipucu için minik dış depo (external store).
 *
 * Hover her fare hareketinde tetiklenir; bunu React durumunda tutmak tüm Keşif ağacını
 * saniyede 60 kez yeniden çizerdi. Burada tutulur, yalnız `Ipucu` bileşeni abone olur.
 */

export interface IpucuDurumu {
  /** bina indeksi ya da null */
  i: number | null;
  /** ekran pikseli (harita tuvali koordinatı) */
  x: number;
  y: number;
}

let _durum: IpucuDurumu = { i: null, x: 0, y: 0 };
const _dinleyiciler = new Set<() => void>();

export function ipucuYaz(i: number | null, x = 0, y = 0): void {
  if (_durum.i === i && Math.abs(_durum.x - x) < 1 && Math.abs(_durum.y - y) < 1) return;
  _durum = { i, x, y };
  for (const cb of _dinleyiciler) cb();
}

export function ipucuAbone(cb: () => void): () => void {
  _dinleyiciler.add(cb);
  return () => {
    _dinleyiciler.delete(cb);
  };
}

export function ipucuOku(): IpucuDurumu {
  return _durum;
}
