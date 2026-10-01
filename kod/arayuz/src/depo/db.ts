/**
 * Telefonun içindeki küçük veritabanı (IndexedDB).
 *
 * Üç iş yapar:
 *  1. `kuyruk` — sunucuya gönderilmemiş ziyaret kayıtları. Sinyal gitse de,
 *     uygulama kapansa da, telefon yeniden başlasa da burada durur.
 *  2. `is_kuyruk` — teknisyenin gönderilmemiş iş düğmeleri ("Yola çıktım",
 *     "Bitti", not, sıra). Her kayıt `istemci_id` ve basış anını taşır; sunucu
 *     aynı kimliği ikinci kez görürse ilk sonucu döner (OPERASYON_V2_SPEC §5.1).
 *  3. `onbellek` — bugünün listesi, harita, özet ve teknisyenin "İşlerim"i.
 *     Çevrimdışı açılışta ekran boş kalmasın diye.
 *
 * İş kayıtları müşteri bilgisi taşır (kısa ad, adres, müşteri no): çıkışta,
 * 401'de ve 24 saatten eskiyse silinir (§6.9). Kuyruklar BİLEREK silinmez.
 */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { ZiyaretKaydi } from '../api/tipler';

export interface KuyrukKaydi extends ZiyaretKaydi {
  /** Kaç kez gönderilmeye çalışıldı. */
  deneme: number;
  /** Son denemede alınan hata. Reddedilen kayıtlarda kullanıcıya gösterilir. */
  son_hata?: string;
  /**
   * Sunucu bu kaydı REDDETTİ (ağ hatası değil: bölge değişti, bina yok vb.).
   * Böyle bir kayıt asla sessizce silinmez; ekranda görünür, kullanıcı ya
   * tekrar dener ya bilerek atar.
   */
  reddedildi?: boolean;
  /** Kuyruğa yazılma anı (ms). */
  olusturma: number;
}

/**
 * Teknisyenin gönderilmemiş bir iş eylemi. Gövde sunucuya olduğu gibi gider
 * (içinde `istemci_id` ve cihazdaki basış anı `zaman` vardır).
 */
export interface IsKuyrukKaydi {
  istemci_id: string;
  /** Kaydı yazan kişi: yalnız o kişi girişliyken gönderilir. */
  kullanici_id: number;
  is_no: string;
  tur: 'durum' | 'not' | 'sira';
  govde: Record<string, unknown>;
  /** Ekranda görünen ad ("Yola çıktım", "Bitti · Çözüldü"). */
  etiket: string;
  olusturma: number;
  deneme: number;
  son_hata?: string;
}

interface SahaSemasi extends DBSchema {
  kuyruk: {
    key: string;
    value: KuyrukKaydi;
    indexes: { olusturma: number };
  };
  is_kuyruk: {
    key: string;
    value: IsKuyrukKaydi;
    indexes: { olusturma: number };
  };
  onbellek: {
    key: string;
    value: { anahtar: string; veri: unknown; zaman: number };
  };
}

let sozu: Promise<IDBPDatabase<SahaSemasi>> | null = null;

export function db() {
  if (!sozu) {
    // Sürüm 2: teknisyen iş kuyruğu. Yükseltme yalnız EKLER; ziyaret kuyruğuna dokunmaz.
    sozu = openDB<SahaSemasi>('saha', 2, {
      upgrade(veritabani) {
        if (!veritabani.objectStoreNames.contains('kuyruk')) {
          const depo = veritabani.createObjectStore('kuyruk', { keyPath: 'offline_id' });
          depo.createIndex('olusturma', 'olusturma');
        }
        if (!veritabani.objectStoreNames.contains('onbellek')) {
          veritabani.createObjectStore('onbellek', { keyPath: 'anahtar' });
        }
        if (!veritabani.objectStoreNames.contains('is_kuyruk')) {
          const depo = veritabani.createObjectStore('is_kuyruk', { keyPath: 'istemci_id' });
          depo.createIndex('olusturma', 'olusturma');
        }
      },
      // Eski sürüm başka bir sekmede açıksa yükseltme bekler; o sekme kendini kapatsın.
      blocking() {
        void sozu?.then((v) => v.close());
        sozu = null;
      },
    });
  }
  return sozu;
}

/* ------------------------------ Önbellek ------------------------------ */

export async function onbellegeYaz(anahtar: string, veri: unknown) {
  try {
    const veritabani = await db();
    await veritabani.put('onbellek', { anahtar, veri, zaman: Date.now() });
  } catch {
    /* depolama kapalıysa uygulama yine çalışır, sadece çevrimdışı açılış zayıflar */
  }
}

export async function onbellektenOku<T>(anahtar: string): Promise<T | null> {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('onbellek', anahtar);
    return kayit ? (kayit.veri as T) : null;
  } catch {
    return null;
  }
}

export async function onbellegiTemizle() {
  try {
    const veritabani = await db();
    await veritabani.clear('onbellek');
  } catch {
    /* yok sayılır */
  }
}

/* ------------------------------ Kuyruk ------------------------------ */

export async function kuyrugaYaz(kayit: ZiyaretKaydi) {
  const veritabani = await db();
  const tam: KuyrukKaydi = { ...kayit, deneme: 0, olusturma: Date.now() };
  await veritabani.put('kuyruk', tam);
  return tam;
}

export async function kuyruguOku(): Promise<KuyrukKaydi[]> {
  try {
    const veritabani = await db();
    const hepsi = await veritabani.getAllFromIndex('kuyruk', 'olusturma');
    return hepsi;
  } catch {
    return [];
  }
}

export async function kuyruktanSil(offlineId: string) {
  try {
    const veritabani = await db();
    await veritabani.delete('kuyruk', offlineId);
  } catch {
    /* yok sayılır */
  }
}

/** Sunucunun reddettiği kaydı işaretler — silinmez, kullanıcıya gösterilir. */
export async function kuyrugaReddiYaz(offlineId: string, hata: string) {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('kuyruk', offlineId);
    if (!kayit) return;
    kayit.reddedildi = true;
    kayit.son_hata = hata.slice(0, 200);
    await veritabani.put('kuyruk', kayit);
  } catch {
    /* yok sayılır */
  }
}

export async function kuyrukDenemeArtir(offlineId: string, hata: string) {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('kuyruk', offlineId);
    if (!kayit) return;
    kayit.deneme += 1;
    kayit.son_hata = hata.slice(0, 200);
    await veritabani.put('kuyruk', kayit);
  } catch {
    /* yok sayılır */
  }
}

export async function kuyrukSayisi(): Promise<number> {
  try {
    const veritabani = await db();
    return await veritabani.count('kuyruk');
  } catch {
    return 0;
  }
}

/**
 * Çıkışta kişisel veri telefonda kalmasın.
 *
 * IndexedDB önbelleği YETMEZ: servis çalışanı `/api/ben`, `/api/gorev/bugun`,
 * `/api/harita` ve `/api/bina` yanıtlarını Cache Storage'da URL'e göre
 * saklıyor — Authorization başlığı anahtara girmiyor. Temizlenmezse aynı
 * telefonda kullanıcı değiştiğinde yeni satışçı eskisinin adını, bölgesini ve
 * gün listesini görebiliyor; çıkıştan sonra da ~1,4 MB iç bina verisi cihazda
 * kalıyordu. Kuyruk BİLEREK silinmez: gönderilmemiş ziyaret kaybolmaz.
 */
export async function hepsiniTemizle() {
  try {
    const veritabani = await db();
    await veritabani.clear('onbellek');
  } catch {
    /* yok sayılır */
  }
  await apiOnbelleginiTemizle();
}

/**
 * Servis çalışanının sakladığı kişiye özel API yanıtlarını siler. Oturum
 * düştüğünde (401: oturum bitti, görev değişti, hesap kapandı, "cihazlardan
 * çıkış") ve her girişte çağrılır; bu yüzden teknisyenin iş kayıtları
 * (müşteri kısa adı, adres, müşteri no) da burada silinir (§6.9).
 */
export async function apiOnbelleginiTemizle() {
  await isKayitlariniTemizle();
  try {
    if (typeof caches === 'undefined') return;
    const adlar = await caches.keys();
    await Promise.all(
      adlar.filter((ad) => ad.startsWith('saha-api-')).map((ad) => caches.delete(ad)),
    );
  } catch {
    /* gizli sekmede / depolama kapalıyken erişilemeyebilir */
  }
}

/* ------------------------------ Teknisyen: iş kayıtları ------------------------------ */

/** İş kayıtları (müşteri bilgisi taşır) en çok bu kadar tutulur (§6.9). */
export const IS_KAYDI_OMRU_MS = 24 * 60 * 60 * 1000;
const IS_ANAHTARI = 'islerim';
/** Kuyruğu gönderme hakkı olan kişi (son giren teknisyen); çıkışta/401'de silinir. */
const AKTIF_KISI_ANAHTARI = 'saha.is.kisi';

interface IsKaydiZarfi<T> {
  kullanici_id: number;
  veri: T;
}

/** "İşlerim" yanıtını telefona yazar (çevrimdışı açılış için). */
export async function isKayitlariniYaz<T>(kullaniciId: number, veri: T) {
  try {
    const veritabani = await db();
    const zarf: IsKaydiZarfi<T> = { kullanici_id: kullaniciId, veri };
    await veritabani.put('onbellek', { anahtar: IS_ANAHTARI, veri: zarf, zaman: Date.now() });
  } catch {
    /* depolama kapalıysa liste yine ağdan gelir */
  }
}

/**
 * Telefondaki "İşlerim" kopyası: yalnız aynı kişinin ve 24 saatten yeni ise.
 * Eskiyse ya da başkasınınsa okunmaz, silinir.
 */
export async function isKayitlariniOku<T>(kullaniciId: number): Promise<{ veri: T; zaman: number } | null> {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('onbellek', IS_ANAHTARI);
    if (!kayit) return null;
    const zarf = kayit.veri as IsKaydiZarfi<T> | null;
    if (!zarf || zarf.kullanici_id !== kullaniciId || Date.now() - kayit.zaman > IS_KAYDI_OMRU_MS) {
      await veritabani.delete('onbellek', IS_ANAHTARI);
      return null;
    }
    return { veri: zarf.veri, zaman: kayit.zaman };
  } catch {
    return null;
  }
}

/** İş kayıtlarını (IndexedDB) ve kuyruğu gönderecek kişi işaretini siler. */
export async function isKayitlariniTemizle() {
  try {
    localStorage.removeItem(AKTIF_KISI_ANAHTARI);
  } catch {
    /* depolama kapalı */
  }
  try {
    const veritabani = await db();
    await veritabani.delete('onbellek', IS_ANAHTARI);
  } catch {
    /* yok sayılır */
  }
}

/**
 * 24 saatten eski iş kayıtlarını siler: IndexedDB kopyası ve servis
 * çalışanının sakladığı `/api/islerim`, `/api/isler…` yanıtları. Uygulama her
 * açılışta ve açıkken yarım saatte bir çağırır (teknisyen İşlerim'e hiç
 * girmese de).
 */
export async function eskiIsKayitlariniTemizle() {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('onbellek', IS_ANAHTARI);
    if (kayit && Date.now() - kayit.zaman > IS_KAYDI_OMRU_MS) await veritabani.delete('onbellek', IS_ANAHTARI);
  } catch {
    /* yok sayılır */
  }
  try {
    if (typeof caches === 'undefined') return;
    for (const ad of await caches.keys()) {
      if (!ad.startsWith('saha-api-')) continue;
      const onbellek = await caches.open(ad);
      for (const istek of await onbellek.keys()) {
        const yol = new URL(istek.url).pathname;
        if (!yol.startsWith('/api/islerim') && !yol.startsWith('/api/isler')) continue;
        const yanit = await onbellek.match(istek);
        const zaman = Number(yanit?.headers.get('x-saha-zaman') || 0);
        if (!zaman || Date.now() - zaman > IS_KAYDI_OMRU_MS) await onbellek.delete(istek);
      }
    }
  } catch {
    /* depolama kapalıyken erişilemeyebilir */
  }
}

/** Kuyruğu gönderecek kişi: İşlerim açılınca yazılır. */
export function aktifIsKisisiYaz(kullaniciId: number | null) {
  try {
    if (kullaniciId == null) localStorage.removeItem(AKTIF_KISI_ANAHTARI);
    else localStorage.setItem(AKTIF_KISI_ANAHTARI, String(kullaniciId));
  } catch {
    /* gizli sekme */
  }
}

export function aktifIsKisisi(): number | null {
  try {
    const ham = localStorage.getItem(AKTIF_KISI_ANAHTARI);
    const n = ham ? Number(ham) : NaN;
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

/* ------------------------------ Teknisyen: iş kuyruğu ------------------------------ */

export async function isKuyrugunaYaz(kayit: IsKuyrukKaydi) {
  const veritabani = await db();
  await veritabani.put('is_kuyruk', kayit);
}

export async function isKuyrugunuOku(): Promise<IsKuyrukKaydi[]> {
  try {
    const veritabani = await db();
    return await veritabani.getAllFromIndex('is_kuyruk', 'olusturma');
  } catch {
    return [];
  }
}

export async function isKuyrugundanSil(istemciId: string) {
  try {
    const veritabani = await db();
    await veritabani.delete('is_kuyruk', istemciId);
  } catch {
    /* yok sayılır */
  }
}

export async function isKuyrukDenemeArtir(istemciId: string, hata: string) {
  try {
    const veritabani = await db();
    const kayit = await veritabani.get('is_kuyruk', istemciId);
    if (!kayit) return;
    kayit.deneme += 1;
    kayit.son_hata = hata.slice(0, 200);
    await veritabani.put('is_kuyruk', kayit);
  } catch {
    /* yok sayılır */
  }
}
