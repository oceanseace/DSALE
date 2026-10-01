/**
 * Yönetim menüsü — tek tanım, iki çizim (OPERASYON_V2_SPEC §6.0):
 *   · masaüstü sol menü (232 px; gruplar açılır/kapanır, hâli cihazda hatırlanır)
 *   · telefon alt sekmeleri (en çok 4; kalanı "Daha" çekmecesinde)
 *
 * Her öğe bir İZİNLE açılır (`/api/ben.izinler`, EK-1 görev kümesinin
 * birleşimi). Kişi yalnız görevlerinin açtığı bölümleri görür.
 */

import { HaritaIkon, Kisi } from '../../ortak/Ikon';
import type { Rol } from '../../api/tipler';
import {
  Ahize,
  Belge,
  Bilet,
  Bolgeler,
  Gecmis,
  Grafik,
  IsPanosu,
  Izgara,
  Kalkan,
  Nabiz,
  Obek,
  Paket,
  Yukle,
} from './simgeler';

export type Bolum =
  | 'isler'
  | 'aranacak'
  | 'obekler'
  | 'takip'
  | 'tablolar'
  | 'ticketlar'
  | 'ekip'
  | 'canli'
  | 'kapsama'
  | 'atama'
  | 'rapor'
  | 'rapor-gecmisi'
  | 'bolge-planlayici'
  | 'tur-raporu'
  | 'veri-kalitesi';

export type Grup = 'satis' | 'veri';

export const GRUP_ADI: Record<Grup, string> = { satis: 'Satış', veri: 'Veri' };

export interface MenuTanimi {
  bolum: Bolum;
  etiket: string;
  /** Telefon sekmesinde kısa ad. */
  kisa?: string;
  Ikon: (p: { boyut?: number }) => JSX.Element;
  /** Bu izinlerden biri yeterli. */
  izin: string[];
  grup?: Grup;
}

export const MENU: MenuTanimi[] = [
  { bolum: 'isler', etiket: 'İşler', Ikon: IsPanosu, izin: ['is.ata'] },
  { bolum: 'aranacak', etiket: 'Aranacaklar', kisa: 'Aranacak', Ikon: Ahize, izin: ['is.duzenle'] },
  { bolum: 'obekler', etiket: 'Öbekler', Ikon: Obek, izin: ['obek.oku'] },
  { bolum: 'takip', etiket: 'Takip', Ikon: Grafik, izin: ['takip.oku'] },
  { bolum: 'tablolar', etiket: 'Tablolar', Ikon: Izgara, izin: ['ticket.defter'] },
  { bolum: 'ticketlar', etiket: 'Ticketlar', Ikon: Bilet, izin: ['ticket.defter'] },
  { bolum: 'ekip', etiket: 'Ekip', Ikon: Kisi, izin: ['ekip.yonet'] },
  { bolum: 'canli', etiket: 'Canlı durum', Ikon: Nabiz, izin: ['satis.izle'], grup: 'satis' },
  { bolum: 'kapsama', etiket: 'Kapsama', Ikon: HaritaIkon, izin: ['satis.izle'], grup: 'satis' },
  { bolum: 'atama', etiket: 'Görev atama', Ikon: Paket, izin: ['satis.izle'], grup: 'satis' },
  { bolum: 'rapor', etiket: 'Rapor', Ikon: Belge, izin: ['satis.izle'], grup: 'satis' },
  { bolum: 'rapor-gecmisi', etiket: 'Rapor geçmişi', Ikon: Gecmis, izin: ['is.yukle'], grup: 'veri' },
  { bolum: 'bolge-planlayici', etiket: 'Bölge planlayıcı', Ikon: Bolgeler, izin: ['veri.yonet'], grup: 'veri' },
  { bolum: 'tur-raporu', etiket: 'Tur raporu', Ikon: Yukle, izin: ['veri.yonet'], grup: 'veri' },
  { bolum: 'veri-kalitesi', etiket: 'Veri kalitesi', Ikon: Kalkan, izin: ['veri.yonet'], grup: 'veri' },
];

export const BOLUMLER = MENU.map((m) => m.bolum);

/** Başlığın altındaki "Bu ekranda ne yaparım?" cümlesi (§6.0). */
export const EKRAN_CUMLESI: Partial<Record<Bolum, string>> = {
  isler: 'Gelen işleri teknisyenlere atayın; kırmızılar önce.',
  aranacak: 'Aranması gereken müşteriler burada; sonucu tek dokunuşla işleyin.',
  obekler: 'Öbek, birlikte çalışılan mahalle grubudur. Mahalle ekleyin, çıkarın.',
  takip: 'Sözümüzü tutuyor muyuz, hızlı mıyız, ekip yetiyor mu — tek bakışta.',
  ekip: 'Kişi ekleyin, görevini seçin; ayrılanı pasife alın.',
  ticketlar: 'Altyapı ticket’larını izleyin; çözülenleri kapatın.',
  tablolar: 'Excel’deki gibi: sekme seçin, arayın, sıralayın, kopyalayın.',
};

export function bolumYolu(b: Bolum): string {
  return `/yonetici/${b}`;
}

export function menuSuz(izinli: (...e: string[]) => boolean): MenuTanimi[] {
  return MENU.filter((m) => izinli(...m.izin));
}

/**
 * Telefonun alt sekmeleri (§6.0): Operasyon "İşler · Aranacak · Öbekler · Daha",
 * Yönetici "İşler · Öbekler · Takip · Daha". Kalan her şey "Daha"da.
 */
export function telefonSekmeleri(rol: Rol | undefined, gorunen: MenuTanimi[]): Bolum[] {
  const tercih: Bolum[] =
    rol === 'operasyon' ? ['isler', 'aranacak', 'obekler'] : ['isler', 'obekler', 'takip'];
  const acik = new Set(gorunen.map((m) => m.bolum));
  const secilen = tercih.filter((b) => acik.has(b));
  // İzinler tercihi karşılamıyorsa (ör. yalnız satış izleyen yönetici) ilk üç açık bölüm.
  for (const m of gorunen) {
    if (secilen.length >= 3) break;
    if (!secilen.includes(m.bolum)) secilen.push(m.bolum);
  }
  return secilen.slice(0, 3);
}
