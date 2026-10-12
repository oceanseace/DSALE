/**
 * RUT sunucu sözleşmesi (kod/operasyon/v2/rut_api.py). İzin: is.duzenle.
 *   GET /api/rut?tarih=   · PUT /api/rut/hucre {tarih, task_no, alan, deger} · PUT /api/rut/ayar {mesai_bas, mesai_bit}
 */

import { istek } from '../../../cekirdek/api/istemci';

export type RutAlan = 'giris' | 'cikis' | 'yardimci' | 'cihaz' | 'switch_id' | 'durum';

export interface RutSutun {
  id: string;
  baslik: string;
  duzenlenir: boolean;
}

export interface RutSatir {
  is_no: string | null;
  task_no: string;
  /** 'yan' = TV · donanım · arıza; 'kurulum' = fiber K */
  tur: 'kurulum' | 'yan';
  is_durumu: string | null;
  /** Elle yazılan alanlar (diğer düzenlenir alanlar öneridir). */
  elle: string[];
  oneri: Partial<Record<RutAlan, string>>;
  [alan: string]: unknown;
}

export interface RutEkip {
  ad: string;
  kisi_id: number | null;
  satirlar: RutSatir[];
}

export interface RutOzet {
  n: number;
  sef: string;
  yardimci: string | null;
  ilk_giris: string | null;
  son_cikis: string | null;
  mesai_dk: number | null;
  mesai_ici: number;
  iptal_erteleme: number;
  mesai_disi: number;
  yan_is: number;
  adet: number;
}

export interface RutGun {
  tarih: string;
  mesai: { bas: string; bit: string };
  musteri: boolean;
  durumlar: string[];
  sutunlar: RutSutun[];
  ozet_sutunlari: Array<{ id: keyof RutOzet; baslik: string }>;
  ekipler: RutEkip[];
  ozet: RutOzet[];
  adet: number;
}

export function rutGetir(tarih: string): Promise<RutGun> {
  return istek<RutGun>(`/api/rut?tarih=${encodeURIComponent(tarih)}`);
}

export function rutHucreYaz(tarih: string, taskNo: string, alan: RutAlan, deger: string): Promise<RutGun> {
  return istek<RutGun>('/api/rut/hucre', { yontem: 'PUT', govde: { tarih, task_no: taskNo, alan, deger } });
}

export function rutMesaiYaz(bas: string, bit: string): Promise<{ mesai: { bas: string; bit: string } }> {
  return istek('/api/rut/ayar', { yontem: 'PUT', govde: { mesai_bas: bas, mesai_bit: bit } });
}
