/**
 * Bir işin kimlik kartı — İş çekmecesinin başında (IsCekmecesi.tsx):
 *   [Task başlığı + durum] · Task No · Müşteri No · Müşteri · Telefon · Adres · Randevu · Ekip
 * Değer yoksa "—". Numaralar (telefon dahil) dokununca kopyalanır. Çekmecede başlık panel başlığında
 * durduğu için `basliksiz` + `sikisik` (iki sütun, küçük yazı) kullanılır.
 */

import type { IsSatir } from '../../../cekirdek/is/tipler';
import { DURUM_ETIKET } from '../../../cekirdek/is/tipler';
import { KopyalaNo, telefon10 } from '../../../cekirdek/ortak/KopyalaNo';
import { Telefon } from '../../../cekirdek/ortak/Ikon';
import { dilimMetni } from './parcalar';

type IsVerisi = IsSatir & { musteri_tel?: string | null; adres?: string | null };

type DurumTonu = 'gri' | 'sari' | 'mavi' | 'mor';
function durumTonu(s: IsSatir): DurumTonu {
  if (s.durum === 'yolda' || s.durum === 'sahada' || s.durum === 'atandi') return 'mavi';
  if (s.durum === 'askida' || s.durum === 'merkeze' || s.durum === 'altyapi') return 'mor';
  if (s.durum === 'randevulu' || s.randevu) return 'sari';
  return 'gri';
}

/** Küçük satır içi telefon: numaraya dokununca 10 hane (başında 0/+90 yok) kopyalanır; yanında küçük "Ara". */
export function TelefonEylem({ tel }: { tel: string | null }) {
  if (!tel) return <span className="ik-tel-yok">—</span>;
  const on = telefon10(tel);
  return (
    <span className="ik-tel">
      <KopyalaNo deger={on}>{tel}</KopyalaNo>
      <a
        className="o-simge-dugme kucuk ik-ara"
        href={`tel:${tel.replace(/\s+/g, '')}`}
        aria-label="Ara"
        title="Ara"
        onClick={(o) => o.stopPropagation()}
      >
        <Telefon boyut={14} />
      </a>
    </span>
  );
}

export function IsKimlik({
  s,
  musteriNoKopyalandi,
  basliksiz,
  sikisik,
}: {
  s: IsSatir;
  musteriNoKopyalandi?: () => void;
  /** Başlık zaten üstte (çekmece başlığı): tekrar yazılmaz. */
  basliksiz?: boolean;
  /** İki sütun, küçük yazı. */
  sikisik?: boolean;
}) {
  const v = s as IsVerisi;
  const adres = v.adres || s.kisa_adres || [s.mahalle, s.ilce].filter(Boolean).join(' · ') || '';
  const randevu = s.randevu ? `${dilimMetni(s.randevu.bas, s.randevu.bit)}${s.randevu.teyitli ? ' · teyitli' : ''}` : '';
  const ekip = s.atanan?.ad || s.boss_ekip || '';
  const bas = (
    <span className="ik-bas">
      <span className="ik-baslik">{s.task_adi || 'İş'}</span>
      <span className={`sk-hap ${durumTonu(s)}`}>{DURUM_ETIKET[s.durum]}</span>
    </span>
  );
  return (
    <div className={`ik-kart${sikisik ? ' sikisik' : ''}`}>
      {basliksiz ? null : bas}
      <dl className="ik-alanlar">
        <div className="ik-alan">
          <dt>Task No</dt>
          <dd>
            <KopyalaNo deger={s.boss_task_no} />
          </dd>
        </div>
        <div className="ik-alan">
          <dt>Müşteri No</dt>
          <dd>
            <KopyalaNo deger={s.musteri_no} sonra={musteriNoKopyalandi} />
          </dd>
        </div>
        <div className="ik-alan">
          <dt>Müşteri</dt>
          <dd>{s.musteri_adi || '—'}</dd>
        </div>
        <div className="ik-alan">
          <dt>Telefon</dt>
          <dd>
            <TelefonEylem tel={v.musteri_tel ?? null} />
          </dd>
        </div>
        <div className="ik-alan genis">
          <dt>Adres</dt>
          <dd>{adres || '—'}</dd>
        </div>
        <div className="ik-alan">
          <dt>Randevu</dt>
          <dd>{randevu || '—'}</dd>
        </div>
        <div className="ik-alan">
          <dt>Ekip</dt>
          <dd>{ekip || '—'}</dd>
        </div>
      </dl>
    </div>
  );
}
