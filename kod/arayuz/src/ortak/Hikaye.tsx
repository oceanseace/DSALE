/**
 * Hikâye cümlesi (EK-6): her ana ekranın başında, durumdan üretilen TEK cümle.
 * "Bugün 437 açık iş var. 12 işin 24 saatine 2 saatten az kaldı — önce onlar."
 *
 * Önce en önemli şey, sonra ayrıntı: ayrıntı "Ayrıntı" düğmesinin arkasındadır
 * (perde). Ton renk değil, küçük bir işaretle verilir; cümle hep nötr yazıdır.
 */

import { useState, type ReactNode } from 'react';
import { sureMetni } from './sure';
import './bilesen.css';

export type HikayeTonu = 'sakin' | 'dikkat' | 'acil' | 'iyi';

export function Hikaye({
  cumle,
  ton = 'sakin',
  ayrinti,
  eylem,
}: {
  cumle: ReactNode;
  ton?: HikayeTonu;
  /** Perdenin arkası: açılınca görünen ayrıntı. */
  ayrinti?: ReactNode;
  /** Cümlenin sonundaki tek bağlantı-düğme ("Önce onlar ›"). */
  eylem?: { etiket: string; calistir: () => void };
}) {
  const [acik, setAcik] = useState(false);
  return (
    <section className={`o-hikaye ${ton}`} aria-live="polite">
      <div className="satir">
        <span className="isaret" aria-hidden="true" />
        <p className="cumle">
          {cumle}
          {eylem ? (
            <>
              {' '}
              <button type="button" className="o-bag" onClick={eylem.calistir}>
                {eylem.etiket}
              </button>
            </>
          ) : null}
        </p>
        {ayrinti ? (
          <button
            type="button"
            className="o-bag ayrinti-dugme"
            aria-expanded={acik}
            onClick={() => setAcik((a) => !a)}
          >
            {acik ? 'Gizle' : 'Ayrıntı'}
          </button>
        ) : null}
      </div>
      {ayrinti && acik ? <div className="ayrinti">{ayrinti}</div> : null}
    </section>
  );
}

const sayi = (n: number) => n.toLocaleString('tr-TR');

/**
 * İşler panosunun cümlesi (WP-C kullanır). Girdi `IslerYanit.sayac` + satırlardan
 * sayılan "2 saatten az kalan" iş sayısı.
 */
export function islerHikayesi(s: {
  acik: number;
  atanmamis: number;
  en_eski_atanmamis_dk?: number | null;
  asan24?: number;
  btk48?: number;
  yakin?: number;
}): { cumle: string; ton: HikayeTonu } {
  if (!s.acik) return { cumle: 'Açık iş yok. Yeni rapor gelince burada görünür.', ton: 'iyi' };
  const bas = `Bugün ${sayi(s.acik)} açık iş var.`;
  if (s.btk48) {
    return { cumle: `${bas} ${sayi(s.btk48)} BTK işi 48 saati aştı — önce onlar.`, ton: 'acil' };
  }
  if (s.yakin) {
    return { cumle: `${bas} ${sayi(s.yakin)} işin 24 saatine 2 saatten az kaldı — önce onlar.`, ton: 'acil' };
  }
  if (s.atanmamis) {
    const bekleme = s.en_eski_atanmamis_dk ? ` En eskisi ${sureMetni(s.en_eski_atanmamis_dk)} bekliyor.` : '';
    return {
      cumle: `${bas} ${sayi(s.atanmamis)} iş henüz teknisyene atanmadı.${bekleme}`,
      ton: (s.en_eski_atanmamis_dk ?? 0) >= 15 ? 'dikkat' : 'sakin',
    };
  }
  return { cumle: `${bas} Hepsi bir teknisyende; atanmamış iş yok.`, ton: 'iyi' };
}
