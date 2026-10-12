/**
 * Ticket fotoğrafları istemcisi — sunucu: `saha/ek_dosya.py`. (Eski Tablolar ekranının api.ts'inden taşındı.)
 *
 * Fotoğraflar jetonla korunur: `<img src>` başlık taşıyamadığı için resim `fetch` ile alınıp
 * `URL.createObjectURL` ile gösterilir (adreste jeton ya da kişisel veri yoktur).
 */

import { istek, jetonuAl, SahaHatasi } from '../../../cekirdek/api/istemci';

export interface TicketEki {
  id: number;
  ticket_id: number;
  dosya_adi: string;
  boyut: number;
  olusturma: string;
  tur: 'jpg' | 'png';
  kucuk: string;
  tam: string;
}

export interface EkListesi {
  ticket_id: number;
  ekler: TicketEki[];
  toplam: number;
  yukleyebilir: boolean;
  en_buyuk_bayt: number;
}

export function ekListesi(ticketId: number): Promise<EkListesi> {
  return istek<EkListesi>(`/api/ticket/${ticketId}/ek`);
}

/** Fotoğraf yükler (ham gövde + `X-Dosya-Adi`; ad başlıkta Türkçe harf taşıyamadığı için kodlanır). */
export async function ekYukle(ticketId: number, dosya: File): Promise<{ ek: TicketEki; zaten_vardi: boolean; mesaj: string }> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch(`/api/ticket/${ticketId}/ek`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${jeton}`,
        Accept: 'application/json',
        'Content-Type': 'application/octet-stream',
        'X-Dosya-Adi': encodeURIComponent(dosya.name || 'foto.jpg'),
      },
      body: dosya,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Fotoğraf gönderilemedi: bağlantı yok.', 'ag_yok', 0);
  }
  const veri = await yanit.json().catch(() => null);
  if (!yanit.ok) throw new SahaHatasi(veri?.hata || 'Fotoğraf eklenemedi.', veri?.kod || 'sunucu', yanit.status);
  return veri;
}

/** Jetonla resim getirir; gösterilecek geçici adres döner (işi bitince `URL.revokeObjectURL`). */
export async function resimAdresi(yol: string, isaret?: AbortSignal): Promise<string> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
      signal: isaret,
    });
  } catch {
    throw new SahaHatasi('Fotoğraf alınamadı.', 'ag_yok', 0);
  }
  if (!yanit.ok) throw new SahaHatasi('Fotoğraf alınamadı.', 'ek_yok', yanit.status);
  return URL.createObjectURL(await yanit.blob());
}
