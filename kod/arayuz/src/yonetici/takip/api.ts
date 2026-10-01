/**
 * Takip uçları (OPERASYON_V2_SPEC §5.3.6). Kişisel veri yok: yalnız sayı ve
 * ekip adları. Geliştirirken (`?sahte=1`) WP-B'nin sözleşme sahtesi kullanılır.
 */

import { istek, sahteMod, SAHTE_IZIN, SahaHatasi } from '../../api/istemci';
import type { TakipSatisYanit, TakipYanit } from '../../is/tipler';

async function cagir<T>(yol: string, yontem: 'GET' | 'PUT' = 'GET', govde?: unknown): Promise<T> {
  if (SAHTE_IZIN && sahteMod) {
    const m = await import('../../is/sahte');
    try {
      return await m.sahteIstek<T>(yontem, yol, govde);
    } catch (h) {
      if (h instanceof m.SahteHata) throw new SahaHatasi(h.govde.hata, String(h.govde.kod), h.durum);
      throw h;
    }
  }
  return istek<T>(yol, { yontem, govde });
}

export function takipGetir(gun: number): Promise<TakipYanit> {
  return cagir<TakipYanit>(`/api/takip?gun=${gun}`);
}

/** Satış bölümü (yalnız yönetici, `takip.tam`). Sayılar `/api/ozet/gun` ile aynı tanımdır. */
export function takipSatis(gun: number): Promise<TakipSatisYanit> {
  return cagir<TakipSatisYanit>(`/api/takip/satis?gun=${gun}`);
}

export interface ErisimYanit {
  gunler: Array<{ gun: string; kisi: string | null; eylem: string; adet: number }>;
}

/** Müşteri bilgisine erişim sayımı (kim, hangi eylem, kaç kez; müşteri adı yok). */
export function takipErisim(gun: number): Promise<ErisimYanit> {
  return cagir<ErisimYanit>(`/api/takip/erisim?gun=${gun}`);
}

export interface YonetimKaydi {
  id: number;
  zaman: string;
  kullanici_id: number | null;
  kullanici_ad: string | null;
  eylem: string;
  hedef: string | null;
  ozet: string | null;
}

export function takipYonetim(limit = 100): Promise<YonetimKaydi[]> {
  return cagir<YonetimKaydi[]>(`/api/takip/yonetim?limit=${limit}`);
}

/**
 * Bugün sahadaki teknik sayısını elle yazar (kapasite modu, §3.6). `null` elle
 * değeri kaldırır (sayı yeniden atamalardan hesaplanır). Yanıt: güncel kapasite.
 */
export function kapasiteYaz(tarih: string, aktifTeknik: number | null): Promise<TakipYanit['kapasite']> {
  return cagir<TakipYanit['kapasite']>('/api/takip/kapasite', 'PUT', { tarih, aktif_teknik: aktifTeknik });
}
