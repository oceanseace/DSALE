/**
 * MAP'te aramadan seçilen sonucun kartı. İş: başlık, Task/müşteri, durum, neden haritada görünmediği ve
 * "İşi aç". Bina: ad, Location ID (dokununca kopyalanır), BN, adres ve bu binadaki açık işler.
 * Giriş: <SecimKarti>. Çağıran: map/KonumAra.tsx. İş çekmecesini yalnız `isiAc` ile açtırır.
 */

import { useMemo } from 'react';
import { DURUM_ETIKET, type IsSatir } from '../../../../cekirdek/is/tipler';
import { KopyalaNo } from '../../../../cekirdek/ortak/KopyalaNo';
import { KapatDugmesi } from '../../../../cekirdek/ortak/Ilkel';
import { yakinIsler, type Bulunan } from './konumArama';

const BINADA_EN_FAZLA = 6;

export function SecimKarti({
  secim,
  isler,
  isiAc,
  gizliMi,
  kapat,
}: {
  secim: Bulunan;
  /** Yüklü açık işler (bina kartında "bu binadaki işler" için). */
  isler: readonly IsSatir[];
  isiAc: (isNo: string) => void;
  gizliMi: (isNo: string) => boolean;
  kapat: () => void;
}) {
  const binadakiler = useMemo(
    () => (secim.tur === 'bina' ? yakinIsler(isler, secim.konum) : []),
    [secim, isler],
  );

  const ust = (
    <div className="mp-kart-ust">
      <span className="mp-kart-tur">{secim.tur === 'bina' ? 'Bina' : 'İş'}</span>
      <KapatDugmesi kucuk etiket="Seçimi kaldır" kapat={kapat} />
    </div>
  );

  if (secim.tur === 'is') {
    const not = !secim.konum
      ? 'Bu işin konumu yok; haritada gösterilemiyor.'
      : !secim.acik
        ? 'Kapalı iş; yeri iğneyle gösterildi.'
        : !secim.yuklu
          ? 'Bu iş açık işler listesinde yok; yeri iğneyle gösterildi.'
          : gizliMi(secim.isNo)
            ? 'Bu iş seçili süzgeçte gizli; yeri iğneyle gösterildi.'
            : null;
    return (
      <div className="mp-kart" role="status">
        {ust}
        <strong className="mp-kart-ad">{secim.baslik}</strong>
        {secim.alt ? <div className="mp-kart-alt">{secim.alt}</div> : null}
        {not ? <div className="mp-kart-not">{not}</div> : null}
        <button type="button" className="o-dugme vurgu mp-kart-dugme" onClick={() => isiAc(secim.isNo)}>
          İşi aç
        </button>
      </div>
    );
  }

  return (
    <div className="mp-kart" role="status">
      {ust}
      <strong className="mp-kart-ad">{secim.ad}</strong>
      <div className="mp-kimlik">
        <span>
          Location ID{' '}
          {secim.loc ? <KopyalaNo deger={secim.loc} /> : <em>yok</em>}
        </span>
        <span>
          BN <KopyalaNo deger={secim.serial} />
        </span>
      </div>
      {secim.alt ? <div className="mp-kart-alt">{secim.alt}</div> : null}
      <div className="mp-binada">
        {binadakiler.length ? (
          <>
            <div className="mp-binada-baslik">
              Bu binada <b>{binadakiler.length.toLocaleString('tr-TR')}</b> açık iş
            </div>
            <ul>
              {binadakiler.slice(0, BINADA_EN_FAZLA).map((s) => (
                <li key={s.is_no}>
                  <button type="button" onClick={() => isiAc(s.is_no)}>
                    <span>{s.task_adi || '—'}</span>
                    <span className="mp-binada-durum">{DURUM_ETIKET[s.durum]}</span>
                  </button>
                </li>
              ))}
            </ul>
            {binadakiler.length > BINADA_EN_FAZLA ? (
              <div className="mp-kart-alt">ve {(binadakiler.length - BINADA_EN_FAZLA).toLocaleString('tr-TR')} iş daha (noktalara basın)</div>
            ) : null}
          </>
        ) : (
          <div className="mp-kart-alt">Bu binada açık iş yok.</div>
        )}
      </div>
    </div>
  );
}
