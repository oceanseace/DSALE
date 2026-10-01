/**
 * Durum yazısı ve adım çizgisi (§7.3).
 *
 * Durum NÖTR yazılır (renkli kutu değil): renk yalnız küçük noktadadır.
 * Satırda asıl renk süre hapındadır; iki renkli işaret yan yana kavga etmez.
 */

import './bilesen.css';

export type NoktaRengi = 'yesil' | 'amber' | 'kirmizi' | 'mor' | 'mavi' | 'gri';

export function DurumYazisi({ etiket, renk = 'gri' }: { etiket: string; renk?: NoktaRengi }) {
  return (
    <span className="o-durum">
      <span className={`nokta ${renk}`} aria-hidden="true" />
      {etiket}
    </span>
  );
}

/**
 * İnce adım çizgisi: Atandı → Yolda → Sahada → Bitti gibi. `adim` 0'dan başlar;
 * o adıma kadar olan parçalar dolu çizilir.
 */
export function AdimCizgisi({
  adim,
  adimlar,
}: {
  adim: number;
  adimlar: string[];
}) {
  return (
    <div
      className="o-adim"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={adimlar.length}
      aria-valuenow={adim + 1}
      aria-valuetext={adimlar[adim] ?? ''}
    >
      {adimlar.map((a, i) => (
        <span key={a} className={i <= adim ? 'dolu' : undefined} title={a} />
      ))}
    </div>
  );
}
