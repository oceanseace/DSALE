/** Fırsat / penetrasyon renk ölçeği lejantı (yalnız o modlarda görünür). */
import { veri } from '../data/load';
import { sayi, yuzde } from '../data/selectors';
import Lejant from '../ui/Lejant';
import { boy, renk, u } from '../ui/tema';
import type { Metrik } from './durum';
import { FIRSAT_PALETI, PENETRASYON_PALETI } from './katmanKur';

let _firsatUst: number | null = null;

/** Fırsat renk ölçeğinin üst ucu (binaların %98'lik dilimi) — `binaRenkleri` ile aynı kural. */
function firsatUstSinir(): number {
  if (_firsatUst != null) return _firsatUst;
  const f = veri().binalar.firsat;
  const a = Float64Array.from(f);
  a.sort();
  _firsatUst = a[Math.min(a.length - 1, Math.floor(0.98 * a.length))] || 1;
  return _firsatUst;
}

export interface MetrikLejantProps {
  metrik: Metrik;
}

export default function MetrikLejant({ metrik }: MetrikLejantProps) {
  if (metrik === 'bolge') return null;
  const firsat = metrik === 'firsat';
  return (
    <div className="ks-cam ks-belir" style={{ padding: u(16), flex: '0 0 auto' }}>
      <Lejant
        baslik={firsat ? 'Fırsat — boş konut HP' : 'Penetrasyon — aktif / RES HP'}
        gradyan={firsat ? FIRSAT_PALETI : PENETRASYON_PALETI}
        uclar={firsat ? ['0', `${sayi(firsatUstSinir())}+ hane`] : [yuzde(0, 0), `${yuzde(0.75, 0)}+`]}
      />
      <div style={{ fontSize: u(boy.not), color: renk.metin3, marginTop: u(8) }}>
        {firsat ? 'Bina başına · parlak bina = daha çok boş hane' : 'Açık = doygun, koyu mor = fırsat'}
      </div>
    </div>
  );
}
