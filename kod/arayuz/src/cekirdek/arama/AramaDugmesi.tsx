/**
 * Paleti açan düğme: masaüstünde kenar menüde arama kutusu görünümünde
 * ("Ara  Ctrl+K"), telefonda başlıkta yalnız büyüteç.
 */

import { SimgeDugme } from '../ortak/Ilkel';
import { Buyutec } from '../ortak/Ikon';
import { paletiAc } from './Palet';
import './arama.css';

const mac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

export function AramaDugmesi({ bicim = 'alan', className }: { bicim?: 'alan' | 'simge'; className?: string }) {
  if (bicim === 'simge') {
    return (
      <SimgeDugme
        etiket="Ara (Location ID, bina, abone)"
        className={`ara-simge-dugme${className ? ` ${className}` : ''}`}
        onClick={() => paletiAc()}
      >
        <Buyutec boyut={20} />
      </SimgeDugme>
    );
  }
  return (
    <button
      type="button"
      className={`ara-alan-dugme${className ? ` ${className}` : ''}`}
      onClick={() => paletiAc()}
      aria-label="Ara: Location ID, bina, abone, kişi"
      aria-keyshortcuts="Control+F Control+K /"
    >
      <Buyutec boyut={16} />
      <span className="yazi">Ara</span>
      <span className="kisayol" aria-hidden="true">
        {mac ? '⌘K' : 'Ctrl+K'}
      </span>
    </button>
  );
}
