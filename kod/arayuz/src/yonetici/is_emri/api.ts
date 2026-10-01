/**
 * İş emri (BOSS raporu) uçları — /api/is-emri/*  (yalnız yönetici).
 * Sunucu tarafı: operasyon/api.py
 */

import { istek, jetonuAl, SahaHatasi } from '../../api/istemci';

export interface Is {
  id: number;
  task_no: string | null;
  task: string;
  durum: string;
  ekip: string;
  il: string;
  ilce: string;
  mahalle: string;
  obek: string;
  lat: number | null;
  lon: number | null;
  /** bina (Lokasyon) · bina (site adı) · mahalle merkezi · ilçe merkezi (kaba) · yok */
  konum: string;
  /** adres · adres-benzer · adres-yeni · adres-isaretsiz · lokasyon · site · yok */
  mahalle_kaynak: string;
  /** Kontrol notu: yalnız gerçekten bakılması gerekenler (boşsa sorun yok) */
  not: string;
  /** Bilgi: kontrol gerektirmeyen farklar (adresteki yazım, OneMap farkı) */
  bilgi?: string;
  /** Bölme birimi: aynı yerdeki işler birlikte kalır */
  yer: string;
  baslangic: string | null;
  randevu: string | null;
  adres: string;
  lokasyon: string | null;
  parca: string | null;
}

export interface ObekTanimi {
  ad: string;
  /** "İl/İlçe/Mahalle" · "İl/İlçe/*" (ilçenin tamamı) */
  mahalleler: string[];
}

export interface MahalleSatiri {
  il: string;
  ilce: string;
  mahalle: string;
  is: number;
  obek: string;
  lat: number | null;
  lon: number | null;
}

export interface YuklemeOzeti {
  toplam_satir: number;
  cikarilan: number;
  cikarilan_neden: Record<string, number>;
  kalan: number;
  mahalle_bulunan: number;
  mahalle_kaynak: Record<string, number>;
  konum_kaynak: Record<string, number>;
  obekli: number;
  mahalle_sayisi: number;
}

export interface IsEmriDurumu {
  yukleme: { dosya: string; zaman: string; ozet: YuklemeOzeti; sure_sn: number } | null;
  isler: Is[];
  obekler: ObekTanimi[];
  mahalleler: MahalleSatiri[];
}

export interface Parca {
  parca: number;
  ad: string;
  is: number;
  mahalleler: string[];
  merkez: [number, number] | null;
  yaricap_km: number | null;
  ort_km: number | null;
}

export interface BolmeSonucu {
  atama: Record<string, number>;
  parcalar: Parca[];
  birim: 'bina' | 'mahalle';
  k: number;
}

export const mahalleRef = (il: string, ilce: string, mahalle: string) => `${il}/${ilce}/${mahalle}`;

export function durumOku(): Promise<IsEmriDurumu> {
  return istek<IsEmriDurumu>('/api/is-emri', { zamanAsimiMs: 30000 });
}

/** Excel'i olduğu gibi gönderir (form değil, ham gövde) — sunucu sayfayı kendisi bulur. */
export async function raporYukle(dosya: File): Promise<IsEmriDurumu> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch('/api/is-emri/yukle', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${jeton}`,
        'Content-Type': 'application/octet-stream',
        'X-Dosya-Adi': encodeURIComponent(dosya.name),
      },
      body: dosya,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  }
  const veri = await yanit.json().catch(() => null);
  if (!yanit.ok) {
    throw new SahaHatasi(veri?.hata || 'Rapor yüklenemedi.', veri?.kod || 'sunucu', yanit.status);
  }
  return veri as IsEmriDurumu;
}

export function obekIslemi(govde: {
  islem: 'ata' | 'cikar' | 'sil' | 'ad';
  ad?: string;
  yeni_ad?: string;
  mahalleler?: string[];
}): Promise<IsEmriDurumu> {
  return istek<IsEmriDurumu>('/api/is-emri/obek', { yontem: 'POST', govde, zamanAsimiMs: 30000 });
}

export function bol(govde: {
  ids: number[];
  k: number;
  birim: 'bina' | 'mahalle';
  ad?: string;
}): Promise<BolmeSonucu> {
  return istek<BolmeSonucu>('/api/is-emri/bol', { yontem: 'POST', govde, zamanAsimiMs: 60000 });
}

export function parcaKaydet(govde: {
  atama?: Record<number, string | null>;
  temizle?: boolean;
  obek_olarak?: Array<{ ad: string; mahalleler: string[] }>;
  eski_obek?: string | null;
}): Promise<IsEmriDurumu> {
  return istek<IsEmriDurumu>('/api/is-emri/parca', {
    yontem: 'POST',
    govde: { atama: {}, ...govde },
    zamanAsimiMs: 30000,
  });
}

/** Hazır Excel'i indirir (İşler · Öbekler · Mahalleler · Kontrol · Çıkarılanlar · Özet). */
export async function excelIndir(dosyaAdi: string): Promise<void> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch('/api/is-emri/excel', {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  }
  if (!yanit.ok) throw new SahaHatasi('Excel alınamadı.', 'excel_yok', yanit.status);
  const adres = URL.createObjectURL(await yanit.blob());
  const bag = document.createElement('a');
  bag.href = adres;
  bag.download = dosyaAdi.replace(/\.xlsx?$/i, '') + '_hazir.xlsx';
  document.body.appendChild(bag);
  bag.click();
  bag.remove();
  setTimeout(() => URL.revokeObjectURL(adres), 30000);
}
