/**
 * Profil ("Ben") — satış dışındaki görevler için: kim olduğum, görevim,
 * görünüm ve çıkış. Satışçının "Ben" ekranı (haftalık sayılar) ayrıdır.
 *
 * Teknik görevlinin ikinci sekmesi budur (İşlerim · Ben). Herkese açıktır
 * (EK-1: "kendi profili" her görevde görünür).
 */

import { useOturum } from '../depo/oturum';
import { git } from '../yol/rota';
import { Sayfa, SayfaGovde, Ust } from './Sayfa';
import { Segment } from './Segment';
import { Marka } from './Marka';
import { useGorunum, GORUNUM_ETIKET, type Gorunum } from './tema';
import { useKutlama } from './Kutlama';
import { useSenkron } from '../depo/senkron';
import { telefonBicimle } from './bicim';
import './bilesen.css';

export function Profil() {
  const { kullanici, gorevAdi, cikisYap, izinli } = useOturum();
  const { gorunum, degistir } = useGorunum();
  const kutlama = useKutlama();
  const { bekleyen } = useSenkron();

  return (
    <Sayfa>
      <Ust baslik="Ben" />
      <SayfaGovde>
        <div className="o-profil">
          <section className="o-profil-kart">
            <Marka boyut={44} />
            <div>
              <div className="ad">{kullanici?.ad ?? '—'}</div>
              <div className="alt">
                {gorevAdi}
                {kullanici?.telefon ? ` · 0${telefonBicimle(kullanici.telefon)}` : ''}
              </div>
            </div>
          </section>

          {bekleyen > 0 ? (
            <p className="o-hata" role="status">
              Telefonda gönderilmeyi bekleyen {bekleyen} kayıt var. Çıkmadan önce internete bağlanın.
            </p>
          ) : null}

          <section className="o-profil-kart dikey">
            <div className="baslik">Görünüm</div>
            <Segment<Gorunum>
              etiket="Görünüm"
              tam
              deger={gorunum}
              degisti={degistir}
              secenekler={(['sistem', 'acik', 'koyu'] as Gorunum[]).map((g) => ({ deger: g, etiket: GORUNUM_ETIKET[g] }))}
            />
            <label className="o-onay-kutusu">
              <input type="checkbox" checked={kutlama.acik} onChange={(o) => kutlama.degistir(o.target.checked)} />
              <span>Küçük kutlamalar (iş bitince kısa bir işaret)</span>
            </label>
          </section>

          {izinli('is.ata', 'satis.izle', 'ekip.yonet') ? (
            <button type="button" className="o-dugme genis" onClick={() => git('/yonetici')}>
              Yönetime dön
            </button>
          ) : null}
          <button type="button" className="o-dugme genis yikici-metin" onClick={cikisYap}>
            Çıkış yap
          </button>
        </div>
      </SayfaGovde>
    </Sayfa>
  );
}
