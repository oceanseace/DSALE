/**
 * Bina kimlikleri, koordinat ve ticket metni.
 *
 * Operasyon ekibi OneDesk ticket'ı açarken lokasyonu elle yazıyordu:
 *   *BTK ÇAĞRISI ACİL MÜDAHALE* … <TAB>Bina Serial Number<TAB>BN-…<TAB>Tellcordia ID<TAB>…
 * Aynı metin (sekme ayrımlı, Excel'deki LOCS sayfasıyla birebir) burada tek
 * dokunuşla üretilip panoya kopyalanır.
 */

import type { Bina } from '../api/tipler';

export type TicketTuru = 'sinyal' | 'ek_kapasite';

export const TICKET_ADLARI: Record<TicketTuru, string> = {
  sinyal: 'Sinyal zayıf (BTK)',
  ek_kapasite: 'Ek kapasite (EK SP)',
};

const TICKET_GIRIS: Record<TicketTuru, string> = {
  sinyal:
    '*BTK ÇAĞRISI ACİL MÜDAHALE* Merhaba, bilgisi olan lokasyonda boş kılda/kıllarda sinyal zayıftır, düzeltilmesi konusunda desteğinizi rica ederim.',
  // Kullanıcıdan örnek metin gelince güncellenecek taslak.
  ek_kapasite:
    'Merhaba, bilgisi olan lokasyonda boş port kalmamıştır, ek kapasite (EK SP) açılması konusunda desteğinizi rica ederim.',
};

const EKIP_ANAHTARI = 'saha.ticketEkip';

export function kayitliEkipTelefonu(): string {
  try {
    return localStorage.getItem(EKIP_ANAHTARI) || '';
  } catch {
    return '';
  }
}

export function ekipTelefonunuKaydet(deger: string) {
  try {
    localStorage.setItem(EKIP_ANAHTARI, deger.trim());
  } catch {
    /* depolama kapalıysa her seferinde yazılır */
  }
}

/** "40.188516, 29.136894" — Google/Yandex/OneMap arama kutusuna doğrudan yapıştırılabilir. */
export function koordinatMetni(lat: number, lon: number): string {
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
}

/**
 * Konumu ADRESLE değil KOORDİNATLA açar. Adresle aranınca harita başka bir ildeki
 * aynı adlı siteye gidebiliyor; koordinat tek anlamlıdır.
 */
export function konumBaglantisi(lat: number, lon: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(6)},${lon.toFixed(6)}`;
}

export function ticketMetni(b: Bina, tur: TicketTuru, ekip: string): string {
  const k = b.kimlik;
  const site = (b.crm_site_adi || b.ad || b.site_adi || '').trim();
  const alanlar = [
    TICKET_GIRIS[tur],
    'Bina Serial Number',
    k?.bina_serial || b.bina_serial,
    'Tellcordia ID',
    k?.tellcordia_id || '',
    '',
    'Location Id',
    k?.location_id || '',
    '',
    '',
    'Obek Adı',
    b.obek || '',
    'Site Adı',
    site,
    `Ekip: ${ekip.trim()}`.trim(),
  ];
  return alanlar.join('\t');
}

/** Panoya kopyalar; eski tarayıcıda/izin yoksa gizli metin alanıyla dener. */
export async function kopyala(metin: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(metin);
    return true;
  } catch {
    try {
      const alan = document.createElement('textarea');
      alan.value = metin;
      alan.setAttribute('readonly', '');
      alan.style.position = 'fixed';
      alan.style.opacity = '0';
      document.body.appendChild(alan);
      alan.select();
      const tamam = document.execCommand('copy');
      document.body.removeChild(alan);
      return tamam;
    } catch {
      return false;
    }
  }
}
