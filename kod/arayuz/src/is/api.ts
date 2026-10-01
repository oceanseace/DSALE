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
  AktarimKaydi,
  AktarimSonucu,
  AranacakYanit,
  BossEkipYanit,
  BossGiden,
  DagitOnizleme,
  DegisimYanit,
  Durum,
  HataYaniti,
  IlceKaydi,
  IsAyarlari,
  IsAyrinti,
  IslerYanit,
  IzlemeDurumu,
  MahalleKaydi,
  MahallelerYanit,
  Obek,
  ObekDegisimYanit,
  ObeklerYanit,
  TeknikOzet,
  TopluGeriAlSonuc,
  TopluSonuc,
  YeniIsYanit,
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

export function hataKodu(h: unknown): string | null {
  return h instanceof SahaHatasi ? h.kod : null;
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

export const islerGetir = (kova: 'acik' | 'biten' = 'acik', gun = 7) =>
  cagir<IslerYanit>('GET', `/api/isler${q({ kova, gun: kova === 'biten' ? gun : undefined })}`);
export const degisimGetir = (imlec: number) => cagir<DegisimYanit>('GET', `/api/isler/degisim${q({ imlec })}`);
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

export const oneriOnayla = (isler: Record<string, number>) =>
  cagir<TopluSonuc>('POST', '/api/isler/oneri-onayla', { isler }, { zamanAsimiMs: 60000 });
export const topluAta = (
  atamalar: Array<{ is_no: string; teknik_id: number; surum: number; randevu?: RandevuGirdi | null }>,
  parca?: string,
) => cagir<TopluSonuc>('POST', '/api/isler/toplu-ata', { atamalar, parca }, { zamanAsimiMs: 60000 });
export const topluGeriAl = (topluId: string) =>
  cagir<TopluGeriAlSonuc>('POST', `/api/isler/toplu/${encodeURIComponent(topluId)}/geri-al`, undefined, { zamanAsimiMs: 60000 });

export interface YeniIsGirdi {
  task_adi: string;
  bina_serial?: string | null;
  adres?: string | null;
  mahalle_id?: number | null;
  musteri_adi?: string | null;
  musteri_no?: string | null;
  aciklama?: string | null;
  istemci_id: string;
}
export const yeniIs = (g: YeniIsGirdi) => cagir<YeniIsYanit>('POST', '/api/isler', g);

export const dagitOnizle = (obek_id: number, teknik_idler: number[]) =>
  cagir<DagitOnizleme>('POST', '/api/isler/dagit/onizle', { obek_id, teknik_idler }, { zamanAsimiMs: 60000 });
export const dagitUygula = (obek_id: number, teknik_idler: number[], isler: Record<string, number>) =>
  cagir<{ gruplar: DagitOnizleme['gruplar']; yazilan: string[]; atlanan: Array<{ is_no: string; kod: string }> }>(
    'POST',
    '/api/isler/dagit/uygula',
    { obek_id, teknik_idler, isler },
    { zamanAsimiMs: 60000 },
  );

export const bossEkip = () => cagir<BossEkipYanit>('GET', '/api/isler/boss-ekip');
export const bossEkipEsle = (boss_ekip: string, teknik_id: number) =>
  cagir<TopluSonuc & { atanan: string[] | number }>('POST', '/api/isler/boss-ekip/esle', { boss_ekip, teknik_id }, { zamanAsimiMs: 60000 });
export const bossGiden = () => cagir<BossGiden[]>('GET', '/api/boss/giden');
export const bossGidenIslendi = (isNo: string) => cagir<IsAyrinti>('POST', `/api/boss/giden/${no(isNo)}/islendi`);

export const aranacaklar = () => cagir<AranacakYanit>('GET', '/api/aranacaklar');

/** Excel (müşteri sütunları role göre; sunucu erişim kaydına yazar). */
export async function islerExcel(kova: 'acik' | 'biten', obekId?: number | null): Promise<void> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch(`/api/isler/excel${q({ kova, obek_id: obekId ?? undefined })}`, {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Sunucuya ulaşılamıyor.', 'ag_yok', 0);
  }
  if (!yanit.ok) throw new SahaHatasi('Excel alınamadı.', 'excel_yok', yanit.status);
  const ad = /filename="([^"]+)"/.exec(yanit.headers.get('Content-Disposition') ?? '')?.[1] ?? 'isler.xlsx';
  const adres = URL.createObjectURL(await yanit.blob());
  const bag = document.createElement('a');
  bag.href = adres;
  bag.download = ad;
  document.body.appendChild(bag);
  bag.click();
  bag.remove();
  window.setTimeout(() => URL.revokeObjectURL(adres), 30000);
}

/* ------------------------------ Aktarım ------------------------------ */

/** Rapor yükle: multipart (dosya + dosya_zamani). 409 `onay_gerekli` IsHatasi olarak gelir (gövdede fark). */
export function raporYukle(dosya: File): Promise<AktarimSonucu> {
  const form = new FormData();
  form.append('dosya', dosya, dosya.name);
  try {
    const an = new Date(dosya.lastModified);
    const iki = (n: number) => String(n).padStart(2, '0');
    form.append(
      'dosya_zamani',
      `${an.getFullYear()}-${iki(an.getMonth() + 1)}-${iki(an.getDate())} ${iki(an.getHours())}:${iki(an.getMinutes())}:${iki(an.getSeconds())}`,
    );
  } catch {
    /* zaman okunamazsa sunucu yükleme anını kullanır */
  }
  return cagir<AktarimSonucu>('POST', '/api/aktarim', undefined, { form, zamanAsimiMs: 180000 });
}
export const aktarimUygula = (id: number, mod: 'tam' | 'kismi') =>
  cagir<AktarimSonucu>('POST', `/api/aktarim/${id}/uygula`, { mod }, { zamanAsimiMs: 180000 });
export const aktarimVazgec = (id: number) => cagir<unknown>('POST', `/api/aktarim/${id}/vazgec`);
export const aktarimGecmisi = (limit = 30) => cagir<AktarimKaydi[]>('GET', `/api/aktarim${q({ limit })}`);
export const izlemeDurumu = () => cagir<IzlemeDurumu>('GET', '/api/aktarim/izleme');
export const izlemeYaz = (acik: boolean) => cagir<IzlemeDurumu>('PUT', '/api/aktarim/izleme', { acik });

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
