/**
 * Depo ▸ Seri takibi: her cihazın seri numarası an be an nerede — depoda,
 * hangi ekipte ya da hangi abonede. Seri girişi bir sonraki adımda gelecek.
 */

import { AkisSeridi } from '../../cekirdek/ortak/AkisSeridi';
import { Ev, Kisi } from '../../cekirdek/ortak/Ikon';
import { Kutu } from '../../cekirdek/konsol/simgeler';
import { BosDurum } from '../../cekirdek/ortak/Bos';
import { Icerik, YonUst } from '../../cekirdek/konsol/Kabuk';

export function Depo() {
  return (
    <>
      <YonUst baslik="Seri takibi" />
      <Icerik>
        <AkisSeridi
          adimlar={[
            { simge: <Kutu boyut={24} />, ad: 'Depo', cumle: 'Seri okutulur, rafa girer' },
            { simge: <Kisi boyut={24} />, ad: 'Ekip', cumle: 'Araçtaki stok, ekip adına' },
            { simge: <Ev boyut={24} />, ad: 'Abone', cumle: 'Kurulumda aboneye bağlanır' },
          ]}
          dallar={[{ kosul: 'Arızalı cihaz', sonuc: 'aboneden geri alınır, depoya döner' }]}
        />
        <BosDurum simge="📦" baslik="Henüz seri girişi yok" />
      </Icerik>
    </>
  );
}
