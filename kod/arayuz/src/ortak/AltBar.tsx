/**
 * Alt sekme çubuğu — telefonda ana bölümler, hepsi başparmak menzilinde,
 * ikon + Türkçe etiket (§6.0, §7.3 AltSekme).
 *
 * Göreve göre (EK-1: görev kümesinin izinlerine göre) 2–4 sekme:
 *   Satış     Bugün · Harita · Ben            (değişmez)
 *   Teknik    İşlerim · Ben
 *   Operasyon / Yönetici sekmeleri yönetim kabuğunda çizilir (Kabuk.tsx).
 *
 * `AltSekme` genel bileşendir; güvenli alan (ana ekran çubuğu) payı içindedir.
 */

import { git, useAdres, yoluCoz } from '../yol/rota';
import { useSenkron } from '../depo/senkron';
import { useOturum } from '../depo/oturum';
import { HaritaIkon, Kisi, Liste, Yonetici } from './Ikon';

export interface AltSekmeOgesi {
  anahtar: string;
  etiket: string;
  Ikon: (p: { boyut?: number }) => JSX.Element;
  etkin: boolean;
  tikla: () => void;
  /** Kırmızı sayaç (bekleyen kayıt, atanmamış iş…). */
  sayac?: number;
  sayacEtiketi?: string;
}

export function AltSekme({ ogeler, etiket = 'Ana bölümler' }: { ogeler: AltSekmeOgesi[]; etiket?: string }) {
  return (
    <nav className="sekmeler" aria-label={etiket}>
      {ogeler.map((s) => (
        <button
          key={s.anahtar}
          type="button"
          className={`sekme${s.etkin ? ' etkin' : ''}`}
          onClick={s.tikla}
          aria-current={s.etkin ? 'page' : undefined}
        >
          <span className="ikon-kutu">
            <s.Ikon boyut={25} />
            {s.sayac ? (
              <span className="sayac" aria-label={s.sayacEtiketi ?? `${s.sayac}`}>
                {s.sayac > 99 ? '99+' : s.sayac}
              </span>
            ) : null}
          </span>
          <span>{s.etiket}</span>
        </button>
      ))}
    </nav>
  );
}

/** Satış ve teknik görevlinin sekme çubuğu (yönetim kabuğunun dışında). */
export function AltBar() {
  const adres = useAdres();
  const { ekran } = yoluCoz(adres);
  const { bekleyen } = useSenkron();
  const { izinli, gorevler } = useOturum();

  const ogeler: AltSekmeOgesi[] = [];
  const satis = izinli('satis.kendi');
  if (satis) {
    ogeler.push(
      { anahtar: 'bugun', etiket: 'Bugün', Ikon: Liste, etkin: ekran === 'bugun', tikla: () => git('/bugun') },
      { anahtar: 'harita', etiket: 'Harita', Ikon: HaritaIkon, etkin: ekran === 'harita', tikla: () => git('/harita') },
    );
  }
  if (gorevler.includes('teknik')) {
    ogeler.push({ anahtar: 'islerim', etiket: 'İşlerim', Ikon: Liste, etkin: ekran === 'islerim', tikla: () => git('/islerim') });
  }
  ogeler.push({
    anahtar: 'ben',
    etiket: 'Ben',
    Ikon: Kisi,
    etkin: ekran === 'ben',
    tikla: () => git('/ben'),
    sayac: bekleyen,
    sayacEtiketi: `${bekleyen} kayıt bekliyor`,
  });
  // Birden çok görevi olan kişi (yönetici, operasyon) yönetime buradan döner.
  if (izinli('is.ata', 'satis.izle', 'ekip.yonet') && ogeler.length < 4) {
    ogeler.push({
      anahtar: 'yonetici',
      etiket: 'Yönetim',
      Ikon: Yonetici,
      etkin: ekran === 'yonetici',
      tikla: () => git('/yonetici'),
    });
  }
  return <AltSekme ogeler={ogeler} />;
}
