/**
 * Anahtar: iOS tarzı aç/kapa (switch). Admin yetki matrisi ve ayarlar bunu
 * kullanır. Görünüm stil/temel.css `.anahtar` sınıfındadır (yay hareketli
 * başparmak, açıkken Turkcell sarısı ray).
 *
 * Erişilebilirlik: gerçek bir checkbox (role="switch") — klavyede Boşluk ile
 * değişir, ekran okuyucu "açık/kapalı" okur. Etiket verilmezse `aciklama`
 * (aria-label) zorunludur.
 */

import type { ReactNode } from 'react';

export function Anahtar({
  acik,
  degisti,
  etiket,
  aciklama,
  kapali = false,
  kucuk = false,
}: {
  acik: boolean;
  degisti: (yeni: boolean) => void;
  /** Anahtarın yanındaki görünür yazı. */
  etiket?: ReactNode;
  /** Görünür etiket yoksa ekran okuyucu adı. */
  aciklama?: string;
  kapali?: boolean;
  kucuk?: boolean;
}) {
  return (
    <label className={`anahtar${kucuk ? ' kucuk' : ''}${kapali ? ' kapali' : ''}`}>
      <input
        type="checkbox"
        role="switch"
        checked={acik}
        disabled={kapali}
        aria-checked={acik}
        aria-label={etiket ? undefined : aciklama}
        onChange={(o) => degisti(o.currentTarget.checked)}
      />
      <span className="ray" aria-hidden="true" />
      {etiket ? <span className="anahtar-etiket">{etiket}</span> : null}
    </label>
  );
}
