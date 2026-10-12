/**
 * Hikâye cümlesi (EK-6): her ana ekranın başında, durumdan üretilen TEK cümle.
 * "Bugün 437 açık iş var. 12 işin 24 saatine 2 saatten az kaldı — önce onlar."
 *
 * Önce en önemli şey, sonra ayrıntı: ayrıntı "Ayrıntı" düğmesinin arkasındadır
 * (perde). Ton renk değil, küçük bir işaretle verilir; cümle hep nötr yazıdır.
 */

import { useState, type ReactNode } from 'react';
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

