/**
 * Teknisyenin düğme kuyruğu (OPERASYON_V2_SPEC §6.9, §5.1, §5.5).
 *
 * Kural satış kuyruğuyla aynı (`depo/senkron.tsx`): düğmeye basıldığı anda
 * eylem ÖNCE telefona yazılır, SONRA gönderilir. Sinyal yoksa ekranda
 * "2 işlem gönderilmeyi bekliyor" yazar; bağlantı gelince kendiliğinden gider.
 *
 * Her kayıt `istemci_id` (uuid) ve cihazdaki basış anını (`zaman`) taşır.
 * Sunucu aynı kimliği ikinci kez görürse ilk sonucu döner: tekrar göndermek
 * çift kayıt üretmez. Geç gelen "Yola çıktım" iş zaten ilerideyse yalnız olay
 * yazılır, durum geri gitmez (sunucu kuralı).
 *
 * Sunucu bir eylemi REDDEDERSE (iş başkasına geçti → 404 `is_yok`; geçersiz
 * geçiş → 409; eksik alan → 422) kayıt kuyruktan düşer ve kişiye bir cümleyle
 * söylenir. Ağ hatasında kayıt bekler ve artan aralıklarla yeniden denenir.
 * 24 saatten eski, gönderilememiş kayıt düşer ve söylenir.
 */

import { SahaHatasi } from '../api/istemci';
import {
  aktifIsKisisi,
  isKuyrugundanSil,
  isKuyrugunaYaz,
  isKuyrugunuOku,
  isKuyrukDenemeArtir,
  IS_KAYDI_OMRU_MS,
  type IsKuyrukKaydi,
} from '../depo/db';
import { durumGonder, notGonder, siraGonder } from './api';

export type { IsKuyrukKaydi };

export type KuyrukOlayi =
  | { tur: 'degisti'; bekleyen: IsKuyrukKaydi[] }
  | { tur: 'gitti'; kayit: IsKuyrukKaydi }
  | { tur: 'dustu'; kayit: IsKuyrukKaydi; mesaj: string; kod: string };

const dinleyiciler = new Set<(o: KuyrukOlayi) => void>();

export function isKuyrugunuDinle(f: (o: KuyrukOlayi) => void): () => void {
  dinleyiciler.add(f);
  return () => {
    dinleyiciler.delete(f);
  };
}

function yayinla(o: KuyrukOlayi) {
  dinleyiciler.forEach((f) => {
    try {
      f(o);
    } catch {
      /* bir dinleyicinin hatası kuyruğu durdurmaz */
    }
  });
}

/* ------------------------------ Kimlik ve an ------------------------------ */

export function istemciKimligi(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  } catch {
    /* eski tarayıcı */
  }
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Sunucu saati − cihaz saati (ms). "İşlerim" her yanıtta günceller. */
let sunucuFarkMs = 0;
export function sunucuFarkiniYaz(ms: number) {
  if (Number.isFinite(ms) && Math.abs(ms) < 7 * 24 * 3600 * 1000) sunucuFarkMs = ms;
}

/** Basış anı, sunucunun biçiminde ("AAAA-AA-GG SS:DD:ss", Türkiye saati). */
export function basisAni(): string {
  const t = new Date(Date.now() + sunucuFarkMs);
  const iki = (n: number) => String(n).padStart(2, '0');
  return (
    `${t.getFullYear()}-${iki(t.getMonth() + 1)}-${iki(t.getDate())} ` +
    `${iki(t.getHours())}:${iki(t.getMinutes())}:${iki(t.getSeconds())}`
  );
}

/* ------------------------------ Kuyruk ------------------------------ */

async function kendiKayitlari(): Promise<IsKuyrukKaydi[]> {
  const kisi = aktifIsKisisi();
  const hepsi = await isKuyrugunuOku();
  return kisi == null ? [] : hepsi.filter((k) => k.kullanici_id === kisi);
}

/** Ekrandaki "bekleyen" listesi için (yalnız girişli kişinin kayıtları). */
export async function bekleyenleriOku(): Promise<IsKuyrukKaydi[]> {
  return kendiKayitlari();
}

async function degistiYayinla() {
  yayinla({ tur: 'degisti', bekleyen: await kendiKayitlari() });
}

/**
 * Eylemi kuyruğa yazar ve (bağlantı varsa) hemen göndermeyi dener. Yazma
 * başarısızsa (depolama kapalı) doğrudan gönderir; o da olmazsa hata atar.
 */
export async function isKuyrugunaEkle(
  kayit: Omit<IsKuyrukKaydi, 'olusturma' | 'deneme'>,
): Promise<void> {
  const tam: IsKuyrukKaydi = { ...kayit, olusturma: Date.now(), deneme: 0 };
  try {
    await isKuyrugunaYaz(tam);
  } catch {
    // Gizli sekme / depolama kapalı: kuyruk yok, doğrudan gönder.
    await tekGonder(tam);
    yayinla({ tur: 'gitti', kayit: tam });
    return;
  }
  await degistiYayinla();
  void isKuyrugunuGonder();
}

async function tekGonder(k: IsKuyrukKaydi): Promise<void> {
  if (k.tur === 'durum') await durumGonder(k.is_no, k.govde);
  else if (k.tur === 'not') await notGonder(k.is_no, k.govde);
  else await siraGonder(k.govde);
}

/** Sunucunun reddini kişiye söylenecek cümleye çevirir. */
function redMesaji(h: SahaHatasi): string {
  if (h.kod === 'is_yok' || h.durum === 404) return 'Bu iş artık size ait değil; operasyon başka birine verdi.';
  return h.message || 'Sunucu bu işlemi kabul etmedi.';
}

let calisiyor = false;
let hataSayisi = 0;
let zamanlayici: number | null = null;
const EN_KISA_BEKLEME = 10_000;
const EN_UZUN_BEKLEME = 3 * 60_000;

function yenidenKur(bekleyenVar: boolean) {
  if (zamanlayici) {
    window.clearTimeout(zamanlayici);
    zamanlayici = null;
  }
  if (!bekleyenVar) return;
  const bekleme = Math.min(EN_UZUN_BEKLEME, EN_KISA_BEKLEME * 2 ** Math.min(hataSayisi, 6));
  zamanlayici = window.setTimeout(() => void isKuyrugunuGonder(), bekleme);
}

/**
 * Kuyruğu sırayla gönderir (aynı işin "Yola çıktım"ı "İşe başladım"dan önce
 * gitsin). Ağ hatasında durur ve sonra yeniden dener; sunucu reddinde o kaydı
 * düşürüp söyler ve sıradakine geçer.
 */
export async function isKuyrugunuGonder(): Promise<void> {
  if (calisiyor) return;
  calisiyor = true;
  try {
    const kayitlar = await kendiKayitlari();
    for (const k of kayitlar) {
      if (Date.now() - k.olusturma > IS_KAYDI_OMRU_MS) {
        await isKuyrugundanSil(k.istemci_id);
        yayinla({
          tur: 'dustu',
          kayit: k,
          kod: 'eski',
          mesaj: `${k.etiket} 24 saat içinde gönderilemedi; operasyona haber verin.`,
        });
        continue;
      }
      if (typeof navigator !== 'undefined' && navigator.onLine === false) break;
      try {
        await tekGonder(k);
        await isKuyrugundanSil(k.istemci_id);
        hataSayisi = 0;
        yayinla({ tur: 'gitti', kayit: k });
      } catch (h) {
        if (h instanceof SahaHatasi && h.durum === 401) break; // oturum düştü: kayıt bekler
        if (h instanceof SahaHatasi && !h.agHatasi) {
          await isKuyrugundanSil(k.istemci_id);
          yayinla({ tur: 'dustu', kayit: k, kod: h.kod, mesaj: redMesaji(h) });
          continue;
        }
        hataSayisi += 1;
        await isKuyrukDenemeArtir(k.istemci_id, h instanceof Error ? h.message : 'bilinmeyen');
        break;
      }
    }
  } finally {
    calisiyor = false;
    const kalan = await kendiKayitlari();
    yayinla({ tur: 'degisti', bekleyen: kalan });
    yenidenKur(kalan.length > 0);
  }
}

let basladi = false;

/**
 * Uygulama açılınca bir kez (SenkronSaglayici): bağlantı gelince, uygulamaya
 * dönülünce ve servis çalışanı dürtünce kuyruğu gönderir. Teknisyen İşlerim
 * dışında (Ben sekmesi) dursa da kuyruk boşalır.
 */
export function isKuyrugunuBaslat(): () => void {
  if (basladi) return () => undefined;
  basladi = true;
  const dene = () => void isKuyrugunuGonder();
  const gorunur = () => {
    if (document.visibilityState === 'visible') dene();
  };
  window.addEventListener('online', dene);
  document.addEventListener('visibilitychange', gorunur);
  dene();
  return () => {
    basladi = false;
    window.removeEventListener('online', dene);
    document.removeEventListener('visibilitychange', gorunur);
  };
}
