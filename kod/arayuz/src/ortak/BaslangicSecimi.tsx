/**
 * "Bu cihazda nereden başlayalım?" (§2.1, §6.12, C9).
 *
 * Tek birimli kişiye sorulmaz. Yalnız YÖNETİCİYE, o cihazdaki ilk girişte bir
 * kez sorulur; seçim cihazda hatırlanır ve menünün altındaki "Başlangıç
 * ekranı" satırından değişir. Seçmeden kapatan İşler'de kalır.
 */

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { baslangicOku, type Baslangic } from '../depo/oturum';
import './bilesen.css';

const SECENEKLER: Array<{ deger: Baslangic; baslik: string; aciklama: string }> = [
  { deger: 'isler', baslik: 'İşler', aciklama: 'Gelen işleri teknisyenlere atamak için.' },
  { deger: 'takip', baslik: 'Takip', aciklama: 'Sözümüzü tutuyor muyuz, hızlı mıyız — tek bakışta.' },
  { deger: 'bugun', baslik: 'Satış uygulaması', aciklama: 'Satışçıların bina listesi ve ziyaretleri.' },
];

export function BaslangicSecimi({
  acik,
  sec,
  ilkKez = true,
}: {
  acik: boolean;
  sec: (b: Baslangic) => void;
  /** Menüden yeniden açıldıysa başlık farklı. */
  ilkKez?: boolean;
}) {
  const [secili, setSecili] = useState<Baslangic>(() => baslangicOku() ?? 'isler');

  useEffect(() => {
    if (!acik) return;
    setSecili(baslangicOku() ?? 'isler');
    const esc = (o: KeyboardEvent) => {
      if (o.key === 'Escape') sec(baslangicOku() ?? 'isler');
    };
    document.addEventListener('keydown', esc);
    return () => document.removeEventListener('keydown', esc);
  }, [acik, sec]);

  if (!acik) return null;
  return createPortal(
    <>
      <div className="o-onay-perde" aria-hidden="true" />
      <div className="o-onay o-baslangic" role="dialog" aria-modal="true" aria-labelledby="baslangic-baslik">
        <h2 id="baslangic-baslik">{ilkKez ? 'Bu cihazda nereden başlayalım?' : 'Başlangıç ekranı'}</h2>
        <p>Bu cihazda her açılışta bu ekran gelir. Sonra menünün altından değiştirebilirsiniz.</p>
        <div className="o-baslangic-secenek" role="radiogroup" aria-label="Başlangıç ekranı">
          {SECENEKLER.map((s) => (
            <label key={s.deger} className={secili === s.deger ? 'secili' : undefined}>
              <input
                type="radio"
                name="baslangic"
                value={s.deger}
                checked={secili === s.deger}
                onChange={() => setSecili(s.deger)}
              />
              <span className="metin">
                <strong>{s.baslik}</strong>
                <span>{s.aciklama}</span>
              </span>
            </label>
          ))}
        </div>
        <div className="o-onay-dugmeler">
          <button type="button" className="o-dugme birincil" onClick={() => sec(secili)} autoFocus>
            Başla
          </button>
        </div>
      </div>
    </>,
    document.body,
  );
}
