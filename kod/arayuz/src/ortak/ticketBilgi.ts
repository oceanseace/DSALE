/**
 * Ticket konuları ve durumları — ekranda nasıl yazılır, hangi renkte durur.
 *
 * Değerler sunucudaki `saha/ticket.py` (KONULAR, DURUMLAR, KONU_ETIKET) ile
 * birebir aynıdır; burada yalnız görünüş (etiket, renk, tek cümlelik anlam) var.
 * Açık sayılan durumlar: AÇIK, HATA, TRANSFER — bunlar takip ister.
 */

import type { TicketDurumu, TicketKonusu } from '../api/tipler';
import type { TicketTuru } from './kimlik';

export const TICKET_KONULARI: Array<{ konu: TicketKonusu; etiket: string; kisa: string }> = [
  { konu: 'SİNYAL', etiket: 'Sinyal zayıf (BTK)', kisa: 'Sinyal' },
  { konu: 'EK SP', etiket: 'Ek kapasite (EK SP)', kisa: 'Ek kapasite' },
  { konu: 'GÜZERGAH', etiket: 'Güzergah', kisa: 'Güzergah' },
  { konu: 'ALTYAPI', etiket: 'Altyapı', kisa: 'Altyapı' },
  { konu: 'DİĞER', etiket: 'Diğer', kisa: 'Diğer' },
];

export function konuEtiketi(konu: string): string {
  return TICKET_KONULARI.find((k) => k.konu === konu)?.etiket ?? konu;
}

/** Çevrimdışı yedek: `kimlik.ts` yalnız bu iki konunun metnini üretebilir. */
export const KONU_TURU: Partial<Record<TicketKonusu, TicketTuru>> = {
  'SİNYAL': 'sinyal',
  'EK SP': 'ek_kapasite',
};

export interface DurumBilgisi {
  durum: TicketDurumu;
  etiket: string;
  /** CSS sınıfı: tk-d-mavi · tk-d-kirmizi · tk-d-mor · tk-d-yesil · tk-d-gri */
  renk: 'mavi' | 'kirmizi' | 'mor' | 'yesil' | 'gri';
  acik: boolean;
  /** "5 yaşındaki çocuk da anlasın" — durumun ne demek olduğu. */
  anlam: string;
}

export const TICKET_DURUMLARI: DurumBilgisi[] = [
  { durum: 'AÇIK', etiket: 'Açık', renk: 'mavi', acik: true, anlam: "OneDesk'te çözülmeyi bekliyor." },
  {
    durum: 'HATA',
    etiket: 'Hata',
    renk: 'kirmizi',
    acik: true,
    anlam: 'OneDesk reddetti ya da yanlış açıldı: düzeltip yeniden açın.',
  },
  {
    durum: 'TRANSFER',
    etiket: 'Transfer',
    renk: 'mor',
    acik: true,
    anlam: 'Başka ekibe geçti; sonucu bekleniyor.',
  },
  { durum: 'ÇÖZÜLDÜ', etiket: 'Çözüldü', renk: 'yesil', acik: false, anlam: 'Sorun giderildi.' },
  { durum: 'KAPATILDI', etiket: 'Kapatıldı', renk: 'gri', acik: false, anlam: 'Çözülmeden kapatıldı.' },
  { durum: 'İPTAL', etiket: 'İptal', renk: 'gri', acik: false, anlam: 'Vazgeçildi; kayıt iz olarak durur.' },
];

export function durumBilgisi(durum: string): DurumBilgisi {
  return (
    TICKET_DURUMLARI.find((d) => d.durum === durum) ?? {
      durum: durum as TicketDurumu,
      etiket: durum,
      renk: 'gri',
      acik: false,
      anlam: '',
    }
  );
}

/** "2026-09-29" → "29.09.2026" */
export function tarihKisa(deger: string | null | undefined): string {
  if (!deger) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(deger);
  return m ? `${m[3]}.${m[2]}.${m[1]}` : deger;
}

/** Açık ticket'ın yaşı, insan diliyle: "bugün açıldı" · "3 gündür açık". */
export function acikGunMetni(gun: number | null | undefined): string | null {
  if (gun == null) return null;
  if (gun <= 0) return 'bugün açıldı';
  if (gun === 1) return 'dünden beri açık';
  return `${gun.toLocaleString('tr-TR')} gündür açık`;
}
