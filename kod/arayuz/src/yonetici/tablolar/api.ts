/**
 * Tablolar (EK-8) ve ticket fotoğrafları istemcisi — sunucu: `saha/tablolar_uclari.py`, `saha/ek_dosya.py`.
 *
 * Fotoğraflar jetonla korunur: `<img src>` başlık taşıyamadığı için resim `fetch` ile alınıp
 * `URL.createObjectURL` ile gösterilir (adreste jeton ya da kişisel veri yoktur).
 */

import { istek, jetonuAl, SahaHatasi } from '../../api/istemci';
import type { IslerYanit } from '../../is/tipler';

/* ------------------------------ Tipler ------------------------------ */

export type SekmeAnahtari = 'ticketlar' | 'guzergah' | 'altyapi' | 'binalar' | 'isler';
export type HucreDegeri = string | number | null;

export interface SunucuSutunu {
  anahtar: string;
  baslik: string;
  tur: 'metin' | 'sayi' | 'tarih' | 'durum';
  genislik?: number;
  kartta?: 'baslik' | 'alt' | 'gizli';
  gizli?: boolean;
}

export interface TabloVerisi {
  sekme: SekmeAnahtari;
  ad: string;
  sutunlar: SunucuSutunu[];
  satirlar: HucreDegeri[][];
  kimlik: string;
  toplam: number;
  sunucu_zamani: string;
  ozet?: Record<string, number | null>;
  pivot?: { sutunlar: SunucuSutunu[]; satirlar: HucreDegeri[][] };
}

export interface TablolarOzeti {
  sunucu_zamani: string;
  sekmeler: Array<{ anahtar: SekmeAnahtari; ad: string; satir: number | null }>;
  ozet: {
    ticket_takipte: number | null;
    guzergah_acik: number | null;
    altyapi_bekliyor: number | null;
    altyapi_en_eski_gun: number | null;
    foto: number | null;
    ps26_son_aktarim: string | null;
  };
}

export interface Ps26Durumu {
  klasor: { bulundu: false } | {
    bulundu: true;
    yer: string;
    dosya: { ad: string; boyut: number; degisme: string };
    zip: number | null;
  };
  son_aktarim: string | null;
  en_buyuk_bayt: number;
}

type Sayac = Partial<Record<'okunan' | 'eklenen' | 'eklenecek' | 'zaten_var' | 'guncellenen' | 'uygulamada_degismis'
  | 'binaya_baglanan' | 'binasiz' | 'excelde_yok' | 'satici_sayisi' | 'zip' | 'eslesen_zip' | 'eslesmeyen_zip'
  | 'dosya' | 'alinmayan' | 'bozuk_zip', number>>;

export interface Ps26Sonucu {
  dosya: string;
  kuru: boolean;
  ticket: Sayac;
  guzergah: Sayac;
  altyapi: Sayac;
  foto: Sayac & { klasor: boolean };
  eklenecek_toplam: number;
  bekliyora_donen_is: number;
  yedek?: string | null;
  sure_sn: number;
}

export interface AltyapiKaydi {
  id: number;
  baslangic: string;
  musteri_no?: string;
  kanal: string;
  satici_ad: string;
  bolge: string;
  durum: string;
  durum_kod: 'bekliyor' | 'kuruldu' | 'iptal';
  bekleme_gun: number | null;
  bina_serial: string;
  notu: string;
  kaynak: string;
}

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

/* ------------------------------ Tablolar ------------------------------ */

export function tablolarOzeti(): Promise<TablolarOzeti> {
  return istek<TablolarOzeti>('/api/tablolar');
}

export function tabloGetir(sekme: Exclude<SekmeAnahtari, 'isler'>): Promise<TabloVerisi> {
  return istek<TabloVerisi>(`/api/tablolar/${sekme}`, { zamanAsimiMs: 60000 });
}

/** İşler sekmesi v2 iş listesini kullanır (müşteri alanlarını sunucu görevle süzer). */
export function isListesi(): Promise<IslerYanit> {
  return istek<IslerYanit>('/api/isler?kova=acik', { zamanAsimiMs: 30000 });
}

export function altyapiGuncelle(
  id: number,
  govde: { durum?: AltyapiKaydi['durum_kod']; notu?: string | null; bina_serial?: string | null },
): Promise<{ kayit: AltyapiKaydi; degisti: boolean }> {
  return istek(`/api/tablolar/altyapi/${id}`, { yontem: 'PATCH', govde });
}

export function altyapiEkle(govde: {
  musteri_no?: string;
  kanal?: string;
  baslangic?: string;
  satici_ad?: string;
  bolge?: string;
  bina_serial?: string;
  notu?: string;
}): Promise<{ kayit: AltyapiKaydi; mesaj: string }> {
  return istek('/api/tablolar/altyapi', { yontem: 'POST', govde });
}

/* ------------------------------ PS26 ------------------------------ */

export function ps26Durumu(): Promise<Ps26Durumu> {
  return istek<Ps26Durumu>('/api/ps26');
}

async function gonder<T>(yol: string, govde: BodyInit | null, zamanAsimiMs = 300000): Promise<T> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  const denetleyici = new AbortController();
  const sayac = setTimeout(() => denetleyici.abort(), zamanAsimiMs);
  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      method: 'POST',
      headers: { Authorization: `Bearer ${jeton}`, Accept: 'application/json' },
      body: govde,
      credentials: 'same-origin',
      cache: 'no-store',
      signal: denetleyici.signal,
    });
  } catch {
    throw new SahaHatasi('Gönderilemedi: bağlantı yok ya da sunucu yanıt vermedi.', 'ag_yok', 0);
  } finally {
    clearTimeout(sayac);
  }
  const veri = await yanit.json().catch(() => null);
  if (!yanit.ok) throw new SahaHatasi(veri?.hata || 'İşlenemedi.', veri?.kod || 'sunucu', yanit.status);
  return veri as T;
}

/**
 * PS26 aktarımı. `kaynak`: 'klasor' → sunucunun bilgisayarındaki PS26 klasörü; ya da seçilen
 * data.xlsx (+ isteğe bağlı fotoğraf arşivleri). `kuru` → yalnız önizleme, hiçbir şey yazılmaz.
 */
export function ps26Aktar(
  kaynak: 'klasor' | { xlsx: File; zipler: File[] },
  kuru: boolean,
): Promise<Ps26Sonucu> {
  const sorgu = `?kuru=${kuru ? 'true' : 'false'}`;
  if (kaynak === 'klasor') return gonder<Ps26Sonucu>(`/api/ps26/aktar${sorgu}&klasor=true`, null);
  const form = new FormData();
  form.append('dosya', kaynak.xlsx, kaynak.xlsx.name);
  for (const z of kaynak.zipler) form.append('zip', z, z.name);
  return gonder<Ps26Sonucu>(`/api/ps26/aktar${sorgu}`, form);
}

/* ------------------------------ Ticket fotoğrafları ------------------------------ */

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
