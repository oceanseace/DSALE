/**
 * Sunumda imleç 2 saniye hareketsizlikten sonra kaybolur, fare kıpırdayınca geri gelir.
 * Perde görüntüsünde beyaz ok kalmasın diye.
 */
import { useEffect } from 'react';

export function useImlecGizle(gecikmeMs = 2000): void {
  useEffect(() => {
    const kok = document.documentElement;
    let zaman = 0;
    const gizle = () => kok.classList.add('dsale-imlec-gizli');
    const goster = () => {
      kok.classList.remove('dsale-imlec-gizli');
      clearTimeout(zaman);
      zaman = window.setTimeout(gizle, gecikmeMs);
    };
    goster();
    window.addEventListener('mousemove', goster);
    window.addEventListener('mousedown', goster);
    return () => {
      clearTimeout(zaman);
      kok.classList.remove('dsale-imlec-gizli');
      window.removeEventListener('mousemove', goster);
      window.removeEventListener('mousedown', goster);
    };
  }, [gecikmeMs]);
}
