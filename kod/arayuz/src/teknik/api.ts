/**
 * Teknisyen uçları (OPERASYON_V2_SPEC §5.3.3 + §5.3.2 durum/not).
 *
 * Normal derlemede hep gerçek sunucu. Geliştirirken (`?sahte=1`) WP-B'nin
 * sözleşme sahtesi (`is/sahte.ts`) kullanılır; `SAHTE_IZIN` derlemede sabite
 * dönüştüğü için sahte veri ofis derlemesine hiç girmez.
 */

import { istek, sahteMod, SAHTE_IZIN, SahaHatasi } from '../api/istemci';
import type { DegisimYanit, IsAyrinti, IslerimYanit } from '../is/tipler';

type Yontem = 'GET' | 'POST';

async function cagir<T>(yol: string, yontem: Yontem = 'GET', govde?: unknown): Promise<T> {
  if (SAHTE_IZIN && sahteMod) {
    const m = await import('../is/sahte');
    try {
      return await m.sahteIstek<T>(yontem, yol, govde);
    } catch (h) {
      if (h instanceof m.SahteHata) throw new SahaHatasi(h.govde.hata, String(h.govde.kod), h.durum);
      throw h;
    }
  }
  return istek<T>(yol, { yontem, govde });
}

const yolu = (isNo: string) => `/api/isler/${encodeURIComponent(isNo)}`;

/** Kendi açık işleri (sırayla, tam ayrıntı) + bugün bitenler. */
export function islerimGetir(): Promise<IslerimYanit> {
  return cagir<IslerimYanit>('/api/islerim');
}

/** Canlı yoklama: imleçten sonra değişen işler (teknikte başkasına geçenler `gorunmez`). */
export function degisimGetir(imlec: number): Promise<DegisimYanit> {
  return cagir<DegisimYanit>(`/api/isler/degisim?imlec=${Math.max(0, Math.floor(imlec))}`);
}

/** İş ekrana ilk girdiğinde: sunucu `teknik_gordu` damgasını yazar (hız hattı "gördü"). */
export function gorduBildir(isNolar: string[]): Promise<void> {
  return cagir<void>('/api/islerim/gordu', 'POST', { is_nolar: isNolar });
}

/** Durum düğmeleri: gövde `yeni`, `istemci_id`, `zaman` ve geçişe özgü alanları taşır. */
export function durumGonder(isNo: string, govde: Record<string, unknown>): Promise<IsAyrinti> {
  return cagir<IsAyrinti>(`${yolu(isNo)}/durum`, 'POST', govde);
}

export function notGonder(isNo: string, govde: Record<string, unknown>): Promise<{ olay_id: number }> {
  return cagir<{ olay_id: number }>(`${yolu(isNo)}/not`, 'POST', govde);
}

export function siraGonder(govde: Record<string, unknown>): Promise<IsAyrinti> {
  return cagir<IsAyrinti>('/api/islerim/sira', 'POST', govde);
}

/** Müşteri no kopyalandı: yalnız erişim kaydı (KVKK). Başarısızlığı kişiyi bekletmez. */
export function kopyaBildir(isNo: string): Promise<void> {
  return cagir<void>(`${yolu(isNo)}/kopya`, 'POST', { alan: 'musteri_no' });
}
