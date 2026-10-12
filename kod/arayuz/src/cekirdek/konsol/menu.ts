/**
 * Konsol menüsü — tek tanım, iki çizim. En üstte birimlerden bağımsız Pano, sonra
 * organizasyon şemasına göre beş birim:
 * Operasyon (TASKS · MAP · RUT · BOSS) · Saha · Altyapı (Ticketlar) · Depo · Administrator.
 *   · masaüstü sol menü (232 px; bir seferde tek birim açık) — çizen: cekirdek/konsol/Kabuk.tsx
 *   · telefon alt sekmeleri (en çok 4; kalanı "Daha" çekmecesinde, birim başlıklı)
 * Bölümü ekrana bağlayan tek yer: src/Konsol.tsx.
 *
 * Her öğe bir İZİNLE açılır (`/api/ben.izinler`: unvanın + ek yetkinliklerin
 * birleşimi; Administrator hepsi). Kişi yalnız yetkinliklerinin açtığı bölümleri görür.
 * Müdür/koordinatör (yalnız Pano) iş atama, planlama ve altyapı bölümlerini görmez.
 */

import { HaritaIkon, Kisi } from '../ortak/Ikon';
import type { Rol } from '../api/tipler';
import {
  Alet,
  Belge,
  Bilet,
  Bolgeler,
  Gecmis,
  Grafik,
  IsPanosu,
  Kalkan,
  Kutu,
  Nabiz,
  Obek,
  Paket,
  Yukle,
} from './simgeler';

export type Bolum =
  | 'isler'
  | 'obekler'
  | 'is-haritasi'
  | 'rut'
  | 'boss'
  | 'canli'
  | 'kapsama'
  | 'atama'
  | 'rapor'
  | 'bolge-planlayici'
  | 'tur-raporu'
  | 'ticketlar'
  | 'depo'
  | 'takip'
  | 'ekip'
  | 'unvanlar'
  | 'veri-kalitesi';

/**
 * Menü grupları; bu sırayla çizilir. `pano` bir birim değildir: menünün en üstünde,
 * başlıksız durur (bkz. `BASLIKSIZ_BIRIMLER`). Diğerleri organizasyon şemasındaki birimler.
 */
export type Birim = 'pano' | 'operasyon' | 'saha' | 'altyapi' | 'depo' | 'administrator';

export const BIRIMLER: Birim[] = ['pano', 'operasyon', 'saha', 'altyapi', 'depo', 'administrator'];

export const BIRIM_ADI: Record<Birim, string> = {
  pano: 'Pano',
  operasyon: 'Operasyon',
  saha: 'Saha',
  altyapi: 'Altyapı',
  depo: 'Depo',
  administrator: 'Administrator',
};

/** Başlıksız (açılır/kapanır olmayan) gruplar: Pano menünün en üstünde tek satırdır. */
export const BASLIKSIZ_BIRIMLER: ReadonlySet<Birim> = new Set<Birim>(['pano']);

export interface MenuTanimi {
  bolum: Bolum;
  etiket: string;
  /** Telefon sekmesinde kısa ad. */
  kisa?: string;
  Ikon: (p: { boyut?: number }) => JSX.Element;
  /** Bu izinlerden biri yeterli. */
  izin: string[];
  birim: Birim;
  /** Menüde çizilmez; adresle (ör. arama paletinden) yine açılır. */
  gizli?: boolean;
}

export const MENU: MenuTanimi[] = [
  { birim: 'pano', bolum: 'takip', etiket: 'Pano', Ikon: Grafik, izin: ['takip.oku'] },
  /* Randevu ve arama (Hizmet Danışmanı) işleri görür, randevu verir; atamayı Operasyon planlama yapar. */
  { birim: 'operasyon', bolum: 'isler', etiket: 'TASKS', Ikon: IsPanosu, izin: ['is.ata', 'is.randevu'] },
  { birim: 'operasyon', bolum: 'is-haritasi', etiket: 'MAP', Ikon: HaritaIkon, izin: ['is.liste', 'is.ata'] },
  /* Kurulum ekiplerinin günlük rotası (ekiplere giden Excel'in yerine); hücre yazmak is.duzenle ister. */
  { birim: 'operasyon', bolum: 'rut', etiket: 'RUT', Ikon: Alet, izin: ['is.duzenle'], gizli: true }, // şimdilik gizli (kod duruyor)
  { birim: 'operasyon', bolum: 'obekler', etiket: 'Öbekler', Ikon: Obek, izin: ['obek.oku'], gizli: true },
  { birim: 'operasyon', bolum: 'boss', etiket: 'BOSS bağlantısı', kisa: 'BOSS', Ikon: Gecmis, izin: ['is.yukle', 'is.ata'] },
  { birim: 'saha', bolum: 'canli', etiket: 'Canlı durum', Ikon: Nabiz, izin: ['satis.izle'] },
  { birim: 'saha', bolum: 'kapsama', etiket: 'Kapsama', Ikon: HaritaIkon, izin: ['satis.izle'] },
  { birim: 'saha', bolum: 'atama', etiket: 'Görev atama', Ikon: Paket, izin: ['satis.izle'] },
  { birim: 'saha', bolum: 'rapor', etiket: 'Rapor', Ikon: Belge, izin: ['satis.izle'] },
  { birim: 'saha', bolum: 'bolge-planlayici', etiket: 'Bölge planlayıcı', Ikon: Bolgeler, izin: ['veri.yonet'] },
  { birim: 'saha', bolum: 'tur-raporu', etiket: 'Tur raporu', Ikon: Yukle, izin: ['veri.yonet'] },
  { birim: 'altyapi', bolum: 'ticketlar', etiket: 'Ticketlar', kisa: 'Ticket', Ikon: Bilet, izin: ['ticket.oku', 'ticket.defter'] },
  { birim: 'depo', bolum: 'depo', etiket: 'Seri takibi', kisa: 'Depo', Ikon: Kutu, izin: ['depo.yonet'] },
  { birim: 'administrator', bolum: 'ekip', etiket: 'Kişiler', Ikon: Kisi, izin: ['ekip.yonet', 'yetkinlik.yonet'] },
  { birim: 'administrator', bolum: 'unvanlar', etiket: 'Unvan ve yetkinlik', kisa: 'Unvanlar', Ikon: Kalkan, izin: ['yetkinlik.yonet'] },
  { birim: 'administrator', bolum: 'veri-kalitesi', etiket: 'Veri kalitesi', Ikon: Nabiz, izin: ['veri.yonet'] },
];

export const BOLUMLER = MENU.map((m) => m.bolum);

export function bolumYolu(b: Bolum): string {
  return `/yonetici/${b}`;
}

export function menuSuz(izinli: (...e: string[]) => boolean): MenuTanimi[] {
  return MENU.filter((m) => !m.gizli && izinli(...m.izin));
}

/**
 * Telefonun alt sekmeleri: Operasyon "TASKS · MAP · Ticket · Daha",
 * diğerleri "Pano · TASKS · Kişiler · Daha". Kalan her şey "Daha"da.
 */
export function telefonSekmeleri(rol: Rol | undefined, gorunen: MenuTanimi[]): Bolum[] {
  const tercih: Bolum[] =
    rol === 'operasyon' ? ['isler', 'is-haritasi', 'ticketlar'] : ['takip', 'isler', 'ekip'];
  const acik = new Set(gorunen.map((m) => m.bolum));
  const secilen = tercih.filter((b) => acik.has(b));
  // İzinler tercihi karşılamıyorsa (ör. yalnız satış izleyen yönetici) ilk üç açık bölüm.
  for (const m of gorunen) {
    if (secilen.length >= 3) break;
    if (!secilen.includes(m.bolum)) secilen.push(m.bolum);
  }
  return secilen.slice(0, 3);
}
