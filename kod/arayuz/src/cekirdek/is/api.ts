/**
 * İş emri v2 uçlarının istemcisi (OPERASYON_V2_SPEC §5.3; sahibi WP-C).
 *
 * `api/istemci.ts`'in `istek`i yalnız ilk hata cümlesini taşır; iş ekranları
 * hata GÖVDESİNİN tamamına ihtiyaç duyar (409 `guncel_degil` → güncel iş +
 * değiştiren kişi, `baska_obekte` → çatışan mahalleler, `onay_gerekli` →
 * rapor farkı…). Bu yüzden burada küçük bir `cagir` var; oturum düşerse
 * (401) merkezi istemciye haber verilir, giriş ekranına o döner.
 *
 * Sahte kip (`?sahte=1`, yalnız geliştirme derlemesi) `is/sahte.ts`'e gider;
 * normal derlemede o dosya pakete girmez.
 */

import { istek, jetonuAl, SahaHatasi, SAHTE_IZIN, sahteMod } from '../api/istemci';
import type {
  BossEkipYanit,
  BossGiden,
  DegisimYanit,
  Durum,
  HataYaniti,
  IlceKaydi,
  IliskiliIs,
  IliskiliUyumsuz,
  IsaretRengi,
  IsAyarlari,
  IsAyrinti,
  IslerYanit,
  MahalleKaydi,
  MahallelerYanit,
  Obek,
  ObekDegisimYanit,
  ObeklerYanit,
  TeknikOzet,
  TopluGeriAlSonuc,
  TopluSonuc,
} from './tipler';

/** Sunucunun hata gövdesiyle birlikte gelen hata. */
export class IsHatasi extends SahaHatasi {
  govde: HataYaniti & Record<string, unknown>;
  constructor(govde: HataYaniti & Record<string, unknown>, durum: number) {
    super(govde.hata || 'Bir şeyler ters gitti.', govde.kod || 'sunucu', durum);
    this.name = 'IsHatasi';
    this.govde = govde;
  }
}

type Yontem = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

async function sahte<T>(yontem: Yontem, yol: string, govde?: unknown): Promise<T> {
  const m = await import('./sahte');
  try {
    return await m.sahteIstek<T>(yontem, yol, govde);
  } catch (e) {
    const h = e as { govde?: HataYaniti; durum?: number; message?: string };
    if (h && h.govde) throw new IsHatasi(h.govde as HataYaniti & Record<string, unknown>, h.durum ?? 409);
    throw e;
  }
}

/** 401: merkezi istemci oturumu kapatsın (giriş ekranı + "Göreviniz değişti" şeridi oradan). */
function oturumDustu() {
  void istek('/api/ben').catch(() => undefined);
}

async function cagir<T>(
  yontem: Yontem,
  yol: string,
  govde?: unknown,
  secenek: { zamanAsimiMs?: number; form?: FormData } = {},
): Promise<T> {
  if (SAHTE_IZIN && sahteMod) return sahte<T>(yontem, yol, govde);
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  const basliklar: Record<string, string> = { Accept: 'application/json', Authorization: `Bearer ${jeton}` };
  let govdeMetni: BodyInit | undefined;
  if (secenek.form) govdeMetni = secenek.form;
  else if (govde !== undefined) {
    basliklar['Content-Type'] = 'application/json';
    govdeMetni = JSON.stringify(govde);
  }
  const denetleyici = new AbortController();
  const sayac = window.setTimeout(() => denetleyici.abort(), secenek.zamanAsimiMs ?? 20000);
  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      method: yontem,
      headers: basliklar,
      body: govdeMetni,
      signal: denetleyici.signal,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Sunucuya ulaşılamıyor.', 'ag_yok', 0);
  } finally {
    window.clearTimeout(sayac);
  }
  if (yanit.status === 401) {
    oturumDustu();
    throw new SahaHatasi('Güvenlik için çıkış yapıldı. Tekrar giriş yapın.', 'oturum_bitti', 401);
  }
  if (yanit.status === 204) return undefined as T;
  const metin = await yanit.text();
  let veri: unknown = null;
  if (metin) {
    try {
      veri = JSON.parse(metin);
    } catch {
      veri = null;
    }
  }
  if (!yanit.ok) {
    // FastAPI HTTPException gövdesi {detail: {...}} ya da düz {hata, kod}
    const ham = (veri ?? {}) as Record<string, unknown>;
    const icerik = (ham.detail && typeof ham.detail === 'object' ? ham.detail : ham) as HataYaniti & Record<string, unknown>;
    if (!icerik.hata) icerik.hata = yanit.status === 403 ? 'Bu bölüm görevinize kapalı.' : 'Bir şeyler ters gitti.';
    throw new IsHatasi(icerik, yanit.status);
  }
  return veri as T;
}

/** Hatanın ekranda yazılacak cümlesi. */
export function hataMetni(h: unknown): string {
  if (h instanceof SahaHatasi) {
    if (h.kod === 'ag_yok') return 'Sunucuya ulaşılamıyor. Bağlantıyı kontrol edip tekrar deneyin.';
    return h.message;
  }
  return 'Bir şeyler ters gitti. Tekrar deneyin.';
}

const q = (p: Record<string, string | number | boolean | null | undefined>) => {
  const s = new URLSearchParams();
  Object.entries(p).forEach(([a, v]) => {
    if (v !== null && v !== undefined && v !== '') s.set(a, String(v));
  });
  const m = s.toString();
  return m ? `?${m}` : '';
};
const no = (isNo: string) => encodeURIComponent(isNo);

/* ------------------------------ İşler ------------------------------ */

/** `ek: true` → her satırda BOSS listesinin bütün alanları (`ek`) ve kökte `ek_etiketler` (TASKS tablosu). */
export const islerGetir = (kova: 'acik' | 'biten' = 'acik', secenek: { gun?: number; ek?: boolean } = {}) =>
  cagir<IslerYanit>(
    'GET',
    `/api/isler${q({ kova, gun: kova === 'biten' ? secenek.gun ?? 7 : undefined, ek: secenek.ek ? 1 : undefined })}`,
  );
export const degisimGetir = (imlec: number, ek = false) =>
  cagir<DegisimYanit>('GET', `/api/isler/degisim${q({ imlec, ek: ek ? 1 : undefined })}`);
/** MAP/TASKS ⟳: eklentiden hemen bir BOSS eşitlemesi iste (sunucu en çok 20 sn'de bir verir). */
export const bossEsitleIste = () => cagir<{ istendi: boolean; sonraki_sn?: number }>('POST', '/api/boss/esitle-iste');
export const isGetir = (isNo: string) => cagir<IsAyrinti>('GET', `/api/isler/${no(isNo)}`);
export const isAyarlari = () => cagir<IsAyarlari>('GET', '/api/isler/ayarlar');
export const teknikler = (tarih?: string) => cagir<TeknikOzet[]>('GET', `/api/isler/teknikler${q({ tarih })}`);

export interface RandevuGirdi {
  bas: string | null;
  bit: string | null;
  teyitli: boolean;
}

export const ata = (
  isNo: string,
  g: { teknik_id: number; randevu?: RandevuGirdi | null; yine_de?: boolean; notu?: string; surum: number },
) => cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/ata`, g);

export const randevuVer = (isNo: string, g: { bas: string | null; bit?: string | null; teyitli?: boolean; notu?: string; surum: number }) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/randevu`, g);

export interface DurumGirdi {
  yeni: Durum;
  neden?: string;
  uyanma?: string;
  canli_test?: boolean;
  teknik_id?: number;
  randevu?: RandevuGirdi;
  notu?: string;
  surum?: number;
}
export const durumDegistir = (isNo: string, g: DurumGirdi) => cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/durum`, g);

/** İşler tablosu: "Bizim durum" (null → temizle). */
export const BIZIM_DURUMLAR = ['Aranacak', 'Randevulu', 'Port yok', 'Kıl yok', 'Sinyal yok', 'Güzergah yok', 'Kuruldu', 'İptal', 'Askıda', 'Ulaşılamadı'] as const;
export const bizimDurumYaz = (isNo: string, deger: string | null, surum?: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/bizim-durum`, { deger, surum });

/** TASKS tablosu: satırın dolgu rengi (null → temizle). İzin: is.duzenle. */
export const isaretYaz = (isNo: string, renk: IsaretRengi | null) =>
  cagir<{ ok: boolean; isaret: IsaretRengi | null }>('POST', `/api/isler/${no(isNo)}/isaret`, { renk });

/** TASKS tablosu: seçili HÜCRELERİN dolgu rengi (Excel gibi; null → dolgu yok). İzin: is.duzenle. */
export const hucreRenkYaz = (hucreler: Array<{ is_no: string; sutun: string }>, renk: IsaretRengi | null) =>
  cagir<{ ok: boolean; renk: IsaretRengi | null; isler: Record<string, Record<string, IsaretRengi | 'yok'>> }>(
    'POST',
    '/api/isler/hucre-renk',
    { hucreler, renk },
  );

/** Administrator: MAP durum → renk eşlemesi (PUT /api/isler/ayarlar {durum_renkleri}). */
export const durumRenkleriYaz = (durum_renkleri: Record<string, string>) =>
  cagir<IsAyarlari>('PUT', '/api/isler/ayarlar', { durum_renkleri });
/** Otomatik planlama anahtarları (yalnız Administrator). */
export const otomatikAyarYaz = (
  g: Partial<
    Pick<IsAyarlari, 'iliskili_dahil' | 'ticket_otomatik_aski' | 'ticket_cozum_yeniden_ata' | 'ticket_cozum_slot' | 'boss_yazma_paralel'>
  >,
) => cagir<IsAyarlari>('PUT', '/api/isler/ayarlar', g);

/** Seçili işlerin aynı müşterideki öbür açık işleri (perakende; toptan genişletilmez). */
export const iliskiliIsler = (is_nolar: string[]) =>
  cagir<{ isler: IliskiliIs[]; toptan_atlanan: number; varsayilan: boolean }>('POST', '/api/isler/iliskili/isler', { is_nolar });
export const iliskiliUyumsuz = () => cagir<IliskiliUyumsuz>('GET', '/api/isler/iliskili/uyumsuz');
export const iliskiliHizala = (is_nolar?: string[]) =>
  cagir<TopluSonuc>('POST', '/api/isler/iliskili/hizala', is_nolar ? { is_nolar } : {}, { zamanAsimiMs: 120000 });

export type TeshisSonucu = 'duzeldi' | 'simdi_evde' | 'baska_gun' | 'cevapsiz' | 'kapali' | 'yanlis_no';
export const teshis = (isNo: string, g: { sonuc: TeshisSonucu; canli_test?: boolean; randevu?: RandevuGirdi; surum?: number }) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/teshis`, g);

export const ticketBagla = (
  isNo: string,
  g: { ticket_id?: number; yeni?: { konu: string; ticket_no?: string; detay?: string }; teknisyen_gonderme: boolean; surum?: number },
) => cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/ticket`, g);
export const ticketAyir = (isNo: string, surum?: number) =>
  cagir<IsAyrinti>('DELETE', `/api/isler/${no(isNo)}/ticket${q({ surum })}`);

export const obegeAta = (isNo: string, obek_id: number | null, surum?: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/obek`, { obek_id, surum });
export const mahalleSec = (isNo: string, mahalle_id: number, surum?: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/mahalle`, { mahalle_id, surum });
export const notEkle = (isNo: string, metin: string) =>
  cagir<{ olay_id: number }>('POST', `/api/isler/${no(isNo)}/not`, { metin });
export const kopyaKaydi = (isNo: string) => cagir<void>('POST', `/api/isler/${no(isNo)}/kopya`, { alan: 'musteri_no' });
export const bossIslendi = (isNo: string, islendi: boolean, surum?: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/boss-islendi`, { islendi, surum });
export const bossBagla = (isNo: string, boss_task_no: string, surum?: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/boss-bagla`, { boss_task_no, surum });
export const geriAl = (isNo: string, olay_id: number) =>
  cagir<IsAyrinti>('POST', `/api/isler/${no(isNo)}/geri-al`, { olay_id });

export const topluGeriAl = (topluId: string) =>
  cagir<TopluGeriAlSonuc>('POST', `/api/isler/toplu/${encodeURIComponent(topluId)}/geri-al`, undefined, { zamanAsimiMs: 60000 });

/** Toplu atama (TASKS/MAP "Ata…"): her iş kendi işleminde; BOSS'a yazma her iş için kuyruğa girer. */
export interface TopluAtamaGirdi {
  is_no: string;
  teknik_id: number;
  surum?: number;
  randevu?: { bas: string; bit: string; teyitli: boolean } | null;
  /** Yalnız iş çekmecesinin tek işi: altyapı engeline rağmen ata. */
  yine_de?: boolean;
}
export const topluAta = (atamalar: TopluAtamaGirdi[]) =>
  cagir<TopluSonuc>('POST', '/api/isler/toplu-ata', { atamalar }, { zamanAsimiMs: 120000 });

/** Atamanın BOSS hâli: gidiyor · tamam (BOSS'ta ✓) · hata (nedeni) · kapali (yazma kapalı) · yok (kayıt yok). */
export interface BossAtamaHali {
  durum: 'gidiyor' | 'tamam' | 'hata' | 'kapali' | 'yok';
  hata?: string;
  /** Hatalı kayıt "Yeniden dene" ile tekrar kuyruğa alınabilir. */
  yeniden?: boolean;
}
export const bossAtamaDurumlari = (is_nolar: string[]) =>
  cagir<{ durumlar: Record<string, BossAtamaHali> }>('POST', '/api/boss/atama-durumlari', { is_nolar });
/** BOSS'a yazılamayan atamaları yeniden kuyruğa alır (her iş tek başına istekte; kendiliğinden yeniden denenmez). */
export const bossAtamaYeniden = (is_nolar: string[]) =>
  cagir<{ yeniden: string[]; atlanan: Array<{ is_no: string; neden: string }> }>('POST', '/api/boss/atama-yeniden', { is_nolar });

/** BOSS yazma kuyruğu (hata ayıklama): son 7 günün kayıtları. Kişisel veri yok (ad/telefon/müşteri adı dönmez). */
export type BossKuyrukDurumu = 'bekliyor' | 'gonderiliyor' | 'gonderildi' | 'hata' | 'zaman_asimi' | 'onizleme' | 'eksik';
export interface BossKuyrukKaydi {
  id: number;
  zaman: string;
  guncelleme: string | null;
  tur: 'atama' | 'aski' | 'not';
  eylem: string;
  task_no: string;
  is_no: string;
  durum: BossKuyrukDurumu | string;
  mesaj: string | null;
  eksik: string[];
  http: number | null;
  return_kodu: number | string | null;
  yeniden: boolean;
}
export interface BossKuyruk {
  kayitlar: BossKuyrukKaydi[];
  sayilar: Record<string, number>;
  toplam: number;
  gun: number;
}
export const bossKuyruk = (p: { durum?: string; tur?: string; ara?: string } = {}) =>
  cagir<BossKuyruk>('GET', `/api/boss/yazmalar${q(p)}`);
export const bossKuyrukYeniden = (id: number) =>
  cagir<{ kayit_id: number; yeni_id: number | null; durum: string; eksik: string[]; aciklama: string }>(
    'POST',
    `/api/boss/yazmalar/${id}/yeniden`,
  );

/** Toplu askı: seçili işlerin BOSS askı nedenleri (kataloglarının birleşimi). */
export interface TopluAskiNedeni {
  kod: string | null;
  ad: string | null;
  katalog: number;
  alt: string[];
}
export interface TopluAskiNedenleri {
  nedenler: TopluAskiNedeni[];
  is_sayisi: number;
  boss_disi: number;
  katalogsuz: number;
  bekleniyor: boolean;
  alt_biliniyor: boolean;
  gonderilir: boolean;
  /** Önceden seçilecek çift: ABONE > Ulaşılamadı (sunucu: boss_yazma.VARSAYILAN_ASKI). */
  varsayilan?: { neden: string; alt: string };
  aciklama: string | null;
}
export const topluAskiNedenleri = (is_nolar: string[]) =>
  cagir<TopluAskiNedenleri>('POST', '/api/isler/toplu-aski/nedenler', { is_nolar });
export interface TopluAskiGirdi {
  is_nolar: string[];
  neden: string;
  alt: string | null;
  bitis: string;
  aciklama: string | null;
}
export const topluAski = (g: TopluAskiGirdi) =>
  cagir<TopluSonuc & { boss: { gonderilir: boolean; aciklama: string | null } }>('POST', '/api/isler/toplu-aski', g, {
    zamanAsimiMs: 120000,
  });

export const bossEkip = () => cagir<BossEkipYanit>('GET', '/api/isler/boss-ekip');
export const bossEkipEsle = (boss_ekip: string, teknik_id: number) =>
  cagir<TopluSonuc & { atanan: string[] | number }>('POST', '/api/isler/boss-ekip/esle', { boss_ekip, teknik_id }, { zamanAsimiMs: 60000 });
export const bossGiden = () => cagir<BossGiden[]>('GET', '/api/boss/giden');
export const bossGidenIslendi = (isNo: string) => cagir<IsAyrinti>('POST', `/api/boss/giden/${no(isNo)}/islendi`);

/* ------------------------------ Aktarım ------------------------------ */

/* ------------------------------ Öbekler ve mahalleler ------------------------------ */

export const obeklerGetir = () => cagir<ObeklerYanit>('GET', '/api/obekler');
export const obekOlustur = (ad: string, surum: number) =>
  cagir<{ obek: Obek; surum: number }>('POST', '/api/obekler', { ad, surum });
export const obekGuncelle = (
  id: number,
  alanlar: { ad?: string; renk?: number; sahip_id?: number | null; yedek_id?: number | null },
  surum: number,
) => cagir<{ obek: Obek; surum: number }>('PATCH', `/api/obekler/${id}`, { ...alanlar, surum });
export const obekMahalleEkle = (
  id: number,
  g: { mahalle_idler?: number[]; tum_ilce?: Array<{ il: string; ilce: string }>; tasi: boolean; surum: number },
) => cagir<ObekDegisimYanit>('POST', `/api/obekler/${id}/mahalle`, g);
export const obekMahalleCikar = (id: number, refler: string[], surum: number) =>
  cagir<ObekDegisimYanit>('POST', `/api/obekler/${id}/mahalle/cikar`, { refler, surum });
export const obekSil = (id: number, surum: number) => cagir<ObekDegisimYanit>('DELETE', `/api/obekler/${id}${q({ surum })}`);
export const obekGeriAl = (olay_id: number, surum: number) =>
  cagir<ObekDegisimYanit>('POST', '/api/obekler/geri-al', { olay_id, surum });
export const obekBol = (id: number, k: number, onizle: boolean, surum: number) =>
  cagir<{ parcalar: Array<{ mahalleler: string[]; is: number; ad?: string }>; surum: number; obekler?: Obek[] }>(
    'POST',
    `/api/obekler/${id}/bol`,
    { k, onizle, surum },
  );

export const mahalleAra = (p: { q?: string; il?: string; ilce?: string; limit?: number }) =>
  cagir<MahallelerYanit>('GET', `/api/mahalleler${q(p)}`);
export const ilceler = () => cagir<IlceKaydi[]>('GET', '/api/ilceler');
export const mahalleEkle = (g: { il: string; ilce: string; ad: string; benzerine_ragmen?: boolean }) =>
  cagir<{ mahalle: MahalleKaydi; etkilenen_is: number }>('POST', '/api/mahalleler', g);
export const esadEkle = (g: { il?: string; ilce?: string; esad: string; mahalle_id: number }) =>
  cagir<{ mahalle: MahalleKaydi; etkilenen_is: number }>('POST', '/api/mahalleler/esad', g);

/** Sunucu kimliği (çevrimdışı tekrar gönderimde çift kayıt olmasın). */
export function istemciKimligi(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/* ------------------------------ BOSS bağlantısı (eklenti) ------------------------------ */

export interface BossDurum {
  bagli: boolean;
  son_esitleme: string | null;
  acik_sayisi: number;
  durum_sayilari: Record<string, number>;
  /** Son eşitlemenin uyarısı (ör. çok iş düştü, kapatılmadı). */
  uyari?: string | null;
  /** BOSS'a yazma özeti (anahtar, sürmekte olan ve son tek iş denemesi). */
  yazma?: BossYazmaOzeti;
}

/* ------------------------------ BOSS'a yazma (Administrator) ------------------------------ */

export type BossYazmaEylem = 'not' | 'atama' | 'aski';
/** Eklentinin yürütme sonucu (BOSS returnCode/returnMessage dahil). */
export interface BossYazmaSonuc {
  durum: 'onizleme' | 'gonderildi' | 'hata' | 'ertelendi';
  http?: number | null;
  hata?: string | null;
  return_kodu?: number | string | null;
  return_mesaji?: string | null;
  belirsiz?: boolean;
  /** 2xx olmayan yanıtın metni (maskeli, kısaltılmış). */
  yanit?: string | null;
}
export interface BossYazmaDenemeKaydi {
  id: number;
  is_no: string;
  tur: string;
  zaman?: string;
  kullanici_ad?: string | null;
  sonuc?: BossYazmaSonuc;
  bitis?: string;
}
export interface BossYazmaOzeti {
  ayar: 'acik' | 'kapali';
  sayilar: Record<string, number>;
  deneme: BossYazmaDenemeKaydi | null;
  son_deneme: BossYazmaDenemeKaydi | null;
}
export interface BossYazmaOnizlemeKaydi {
  id: number;
  tur: string;
  ad?: string | null;
  durum: string;
  olusturma?: string;
  guncelleme?: string;
  kisi?: string | null;
  yontem?: string;
  yol?: string;
  govde: unknown;
  eksik: string[];
  dogrulandi: boolean;
  deneme: boolean;
  eklenti: BossYazmaSonuc | null;
}
export interface BossYazmaOnizleme {
  is_no: string;
  yazma: 'acik' | 'kapali';
  /** Eylem (not, atama, aski) BOSS'a gerçekten gider mi: kendi anahtarı + doğrulanmış şablon. */
  eylemler?: Record<string, 'acik' | 'kapali'>;
  kayitlar: BossYazmaOnizlemeKaydi[];
}
export const bossYazmaOnizleme = (isNo: string) =>
  cagir<BossYazmaOnizleme>('GET', `/api/isler/${no(isNo)}/boss-yazma-onizleme`);
export const bossYazmaDene = (isNo: string, eylem: BossYazmaEylem) =>
  cagir<{ kayit_id: number; govde: unknown; dogrulandi: boolean }>('POST', '/api/boss/yazma-dene', { is_no: isNo, eylem });
export const bossYazmaAnahtari = (acik: boolean) => cagir<BossYazmaOzeti>('PUT', '/api/boss/yazma-anahtari', { acik });
/** 404 → sunucuda uç yok: "bağlantı kurulmadı" (null). */
export async function bossDurum(): Promise<BossDurum | null> {
  try {
    return await cagir<BossDurum>('GET', '/api/boss/durum');
  } catch (h) {
    if (h instanceof SahaHatasi && h.durum === 404) return null;
    throw h;
  }
}
/** OneMap bina eşitlemesi (BOSS Yardımcısı, OneMap sekmesi açıkken): GET /api/onemap/durum. */
export interface OnemapDurum {
  bagli: boolean;
  son_temas: string | null;
  son_esitleme: string | null;
  son_tam: string | null;
  yeni_bina: number;
  guncellenen_toplam: number;
  baglanan_is_toplam: number;
  bilinmeyen_lokasyon: number;
  bulunamayan: number;
  son_hata: string | null;
}
/** 404/403 → uç yok ya da izin yok: kart gösterilmez (null). */
export async function onemapDurum(): Promise<OnemapDurum | null> {
  try {
    return await cagir<OnemapDurum>('GET', '/api/onemap/durum');
  } catch (h) {
    if (h instanceof SahaHatasi && (h.durum === 404 || h.durum === 403)) return null;
    throw h;
  }
}
/** Eklentiyi bu sunucuya eşleyen kısa kod; uç yoksa null. */
export async function bossEslesmeKodu(): Promise<string | null> {
  try {
    const y = await cagir<{ kod?: string | null }>('GET', '/api/boss/eslesme-kodu');
    return y?.kod ?? null;
  } catch (h) {
    if (h instanceof SahaHatasi && (h.durum === 404 || h.durum === 403)) return null;
    throw h;
  }
}

/* ------------------------------ BOSS iş ayrıntısı (sekmeler, canlı) ------------------------------ */

export type BossDetaySekme =
  | 'urunler' | 'iletisim' | 'aciklama' | 'ariza_gecmisi' | 'fotograflar' | 'cihaz'
  | 'ariza_nedeni' | 'notlar' | 'evraklar' | 'tarihce' | 'adres_teyidi';
export interface BossDetayYanit {
  durum: 'bekliyor' | 'hazir' | 'yok';
  sekmeler?: Partial<Record<BossDetaySekme, unknown>> | null;
  zaman?: string | null;
  /** Beklerken: istek ne zamandır bekliyor (sn). */
  bekleme_sn?: number;
  /** Beklerken: BOSS Yardımcısı isteği aldı mı. */
  eklenti_aldi?: boolean;
  zaman_asimi_sn?: number;
  /** durum 'yok' iken neden ("zaman_asimi" ya da metin). */
  hata?: string | null;
  /** Hazır (önbellekteki) ayrıntı gösterilirken BOSS'tan tazesi isteniyor mu. */
  yenileniyor?: boolean;
}
const yokSa404 = (h: unknown) => h instanceof SahaHatasi && (h.durum === 404 || h.durum === 405 || h.durum === 501);
/** BOSS'tan canlı ayrıntı iste (`yenile`: önbellekte olsa da tazesini); uç yoksa null. */
export async function bossDetayIste(isNo: string, yenile = false): Promise<BossDetayYanit | null> {
  try {
    const yol = `/api/isler/${no(isNo)}/boss-detay${yenile ? '?yenile=true' : ''}`;
    return (await cagir<BossDetayYanit | null>('POST', yol)) ?? { durum: 'bekliyor' };
  } catch (h) {
    if (yokSa404(h)) return null;
    throw h;
  }
}
/** TASKS'ın o an gösterdiği ilk işler: BOSS ayrıntısı önden okunurken önce bunlar okunur (sessiz; hata yutulur). */
export async function bossDetayOncelik(isNolar: string[]): Promise<void> {
  try {
    await cagir('POST', '/api/boss/detay-oncelik', { is_nolar: isNolar.slice(0, 200) });
  } catch {
    /* eski sunucu / izin yok: önden okuma kendi sırasıyla sürer */
  }
}

export async function bossDetayGetir(isNo: string): Promise<BossDetayYanit | null> {
  try {
    return await cagir<BossDetayYanit>('GET', `/api/isler/${no(isNo)}/boss-detay`);
  } catch (h) {
    if (yokSa404(h)) return null;
    throw h;
  }
}
/** BOSS teknisyen listesi; uç yoksa boş. */
export async function bossEkipleri(): Promise<Array<{ id: string | number; ad: string; aktif?: boolean }>> {
  try {
    const y = await cagir<Array<{ id: string | number; ad: string; aktif?: boolean }>>('GET', '/api/boss/ekipler');
    return Array.isArray(y) ? y : [];
  } catch (h) {
    if (yokSa404(h) || (h instanceof SahaHatasi && h.durum === 403)) return [];
    throw h;
  }
}

/* ------------------------------ Görünümler (task başlığına göre süzgeç) ------------------------------ */

export interface Gorunum {
  id: number;
  ad: string;
  task_adlari: string[];
  kisi_id: number | null;
  kisi: { id: number; ad: string } | null;
}
export interface GorunumlerYanit {
  gorunumler: Gorunum[];
  /** Açık işlerin task başlıkları, adede göre azalan. */
  basliklar: Array<{ ad: string; adet: number }>;
  kisiler: Array<{ id: number; ad: string; tur: 'ofis' | 'ekip' }>;
}
export interface GorunumYaz {
  id?: number;
  ad: string;
  task_adlari: string[];
  kisi_id?: number | null;
}
export const gorunumlerGetir = () => cagir<GorunumlerYanit>('GET', '/api/isler/gorunumler');
export const gorunumlerYaz = (gorunumler: GorunumYaz[]) => cagir<GorunumlerYanit>('PUT', '/api/isler/gorunumler', { gorunumler });

/* ------------------------------ TASKS/MAP kişisel tercihleri (sunucuda; kişiyi izler) ------------------------------ */

/** Excel düzeni: içeriğini birimler/operasyon/isler/tercihDeposu.ts tanımlar; sunucu yalnız saklar. */
export type DuzenVeri = Record<string, unknown> & { gorunen?: string[]; gen?: Record<string, number> };
export interface AdliDuzen {
  ad: string;
  duzen: DuzenVeri;
}
export interface TasksTercih {
  etkin: DuzenVeri | null;
  duzenler: AdliDuzen[];
  suzgec: Record<string, unknown> | null;
  /** Hazır düzenler ("TV ekibi"); değiştirilemez. */
  fabrika: AdliDuzen[];
  /** Kişinin unvanı ve Administrator'ın o unvana verdiği varsayılan düzen. */
  unvan: { id: number; ad: string | null; duzen: DuzenVeri | null } | null;
  administrator: boolean;
  /** Yalnız Administrator: bütün unvanlar ve varsayılan düzenleri. */
  unvanlar?: Array<{ id: number; ad: string; duzen: DuzenVeri | null }>;
  /** Kişisel Ayarlar (Kabuk ▸ Ayarlar); eski sunucu vermez. */
  ayarlar?: Partial<KisiAyarlari>;
}
/** Kişisel ayarlar (sunucuda kişi başına; kod/operasyon/v2/tasks_tercih.py AYAR_VARSAYILAN). */
export interface KisiAyarlari {
  /** MAP üstünde durum sayaç çubuğu (Randevusuz · Randevulu · Ekip yolda · Askıda). */
  map_durum_cubugu: boolean;
  /** MAP sağ alt renk lejantı. */
  map_lejant: boolean;
  /** MAP otomatik tazeleme aralığı (sn; 0 = kapalı). */
  map_tazeleme_sn: number;
  /** Süzgeç değer listesi (TASKS ▾, MAP Filtreler): diğer süzgeçlerle gizlenen değerler soluk gösterilsin mi
   *  (varsayılan kapalı → listede yok; arama yine hepsini bulur). */
  suzgec_soluk_goster: boolean;
}
export const tercihGetir = () => cagir<TasksTercih>('GET', '/api/isler/tercih');
export const tercihYaz = (g: {
  etkin?: DuzenVeri | null;
  duzenler?: AdliDuzen[];
  suzgec?: Record<string, unknown> | null;
  ayarlar?: Partial<KisiAyarlari> | null;
}) =>
  cagir<TasksTercih>('PUT', '/api/isler/tercih', g);
export const unvanDuzeniYaz = (unvan_id: number, duzen: DuzenVeri | null) =>
  cagir<TasksTercih>('PUT', '/api/isler/tercih/unvan', { unvan_id, duzen });

/* ------------------------------ BOSS eşitleme farkları (değişiklik akışı) ------------------------------ */

/** Bir eşitlemenin farkı: yalnız BOSS task no'ları (kişisel veri yok). */
export interface BossFark {
  no: number;
  zaman: string;
  mod?: string | null;
  tam?: boolean;
  yeni: string[];
  degisen: string[];
  kapanan: string[];
}
/** `GET /api/boss/farklar` (son 50 eşitleme, en yenisi önde). Uç yoksa / izin yoksa null (şerit gizlenir). */
export async function bossFarklar(): Promise<BossFark[] | null> {
  try {
    const y = await cagir<{ farklar?: BossFark[] }>('GET', '/api/boss/farklar');
    return Array.isArray(y?.farklar) ? y.farklar : null;
  } catch (h) {
    if (yokSa404(h) || (h instanceof SahaHatasi && h.durum === 403)) return null;
    throw h;
  }
}

/* ------------------------------ BOSS ekip GPS konumları (MAP "Ekipler" katmanı) ------------------------------ */

/** Bir BOSS ekibinin son konumu (`kod/operasyon/v2/ekip_konum.py liste`). */
export interface EkipKonum {
  ekip: string;
  ad: string;
  lat: number;
  lon: number;
  /** Konumun zamanı (Türkiye saati, "AAAA-AA-GG SS:DD:ss"); BOSS zaman vermediyse alındığı an. */
  zaman: string;
  zaman_kesin?: boolean;
  yas_dk: number | null;
  /** BOSS ekibine eşli teknisyen (varsa). */
  teknik_id?: number | null;
  teknik_ad?: string | null;
}
export interface EkipKonumYanit {
  ekipler: EkipKonum[];
  /** Eklenti BOSS GPS yanıtını hiç yakaladı mı (yoksa ipucu gösterilir). */
  kaynak_goruldu: boolean;
  son_alim: string | null;
  son_bulunan?: number | null;
}
/** `GET /api/isler/ekip-konumlari`. Uç yoksa (eski sunucu) / izin yoksa null. */
export async function ekipKonumlari(): Promise<EkipKonumYanit | null> {
  try {
    const y = await cagir<EkipKonumYanit>('GET', '/api/isler/ekip-konumlari');
    return y && Array.isArray(y.ekipler) ? y : null;
  } catch (h) {
    if (yokSa404(h) || (h instanceof SahaHatasi && h.durum === 403)) return null;
    throw h;
  }
}
