/**
 * Sözleşmedeki uçların (endpoint) tek tek karşılıkları.
 *
 * Normal derlemede burada yalnız gerçek sunucu çağrıları kalır: `SAHTE_IZIN`
 * derleme sabiti `false` olduğu için sahte dalları ve `import('./sahte')`
 * satırı pakete girmez.
 */

import { istek, sahteMod, SAHTE_IZIN, SahaHatasi } from './istemci';
import type {
  BenYaniti,
  BinaAyrintisi,
  BugunGorevi,
  GirisYaniti,
  HaritaVerisi,
  TicketKonusu,
  TopluYanit,
  YolAgi,
  ZiyaretKaydi,
  ZiyaretYaniti,
} from './tipler';

/** Örnek veri modülü yalnız gerektiğinde indirilir (ayrı parça). */
let sahteSoz: Promise<typeof import('./sahte')> | null = null;
function sahteApi() {
  if (!sahteSoz) sahteSoz = import('./sahte');
  return sahteSoz;
}

/* ------------------------------ Açık uçlar ------------------------------ */

export interface SaglikYaniti {
  ok: boolean;
  surum?: string;
  demo?: boolean;
  yazilabilir?: boolean;
  uyari?: string | null;
  /** Giriş ekranındaki "Yöneticini ara" satırı. */
  yardim_telefon?: string | null;
  yardim_ad?: string | null;
}

/** Jeton gerektirmez; giriş ekranı yardım satırı için kullanır. */
export async function saglik(): Promise<SaglikYaniti | null> {
  if (SAHTE_IZIN && sahteMod) return { ok: true };
  try {
    return await istek<SaglikYaniti>('/api/saglik', { acik: true, zamanAsimiMs: 5000 });
  } catch {
    return null;
  }
}

/* ------------------------------ Giriş ------------------------------ */

export async function giris(telefon: string, pin: string): Promise<GirisYaniti> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).giris(telefon, pin);
  return istek<GirisYaniti>('/api/giris', { yontem: 'POST', govde: { telefon, pin }, acik: true });
}

/** İlk giriş: yöneticiden alınan davet kodu ile kendi PIN'ini belirler. */
export async function pinBelirle(
  telefon: string,
  pin: string,
  davetKodu: string,
): Promise<GirisYaniti> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).pinBelirle(telefon, pin);
  return istek<GirisYaniti>('/api/pin', {
    yontem: 'POST',
    govde: { telefon, pin, davet_kodu: davetKodu },
    acik: true,
  });
}

/* ------------------------------ Satışçı ------------------------------ */

export async function ben(): Promise<BenYaniti> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).ben();
  return istek<BenYaniti>('/api/ben');
}

export async function bugunGorevi(): Promise<BugunGorevi | null> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).bugunGorevi();
  try {
    return await istek<BugunGorevi>('/api/gorev/bugun');
  } catch (h) {
    // Bugün için görev yoksa sunucu 404 döndürür — bu bir hata değil, boş bir gün.
    if (h instanceof SahaHatasi && h.durum === 404) return null;
    throw h;
  }
}

export async function gorevOlustur(
  adet?: number,
  baslangic?: [number, number],
): Promise<BugunGorevi> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).gorevOlustur(adet);
  return istek<BugunGorevi>('/api/gorev/olustur', {
    yontem: 'POST',
    govde: { adet, baslangic },
    zamanAsimiMs: 30000,
  });
}

export async function ziyaretGonder(kayit: ZiyaretKaydi): Promise<ZiyaretYaniti> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).ziyaretGonder(kayit);
  return istek<ZiyaretYaniti>('/api/ziyaret', { yontem: 'POST', govde: kayit });
}

/**
 * Çevrimdışı kuyruğun toplu senkronu.
 *
 * YANIT GÖVDESİ OKUNMAK ZORUNDA: sunucu kısmi hatada HTTP 200 döner ve
 * reddettiği kayıtları `hatali` listesinde bildirir. Bu liste okunmadığında
 * kuyruğun TAMAMI siliniyordu — yani sunucunun kabul etmediği gerçek ziyaretler
 * sessizce kayboluyordu. "Uygulamaya %100 güvenilmeli" şartını ihlal eden tek
 * hata buydu.
 */
export async function ziyaretToplu(kayitlar: ZiyaretKaydi[]): Promise<TopluYanit> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).ziyaretToplu(kayitlar);
  return istek<TopluYanit>('/api/ziyaret/toplu', {
    yontem: 'POST',
    govde: kayitlar,
    zamanAsimiMs: 30000,
  });
}

/** Yanlış işlenen kaydı geri alır (aynı gün içinde, kaydı giren kişi). */
export async function ziyaretIptal(ziyaretId: number, neden?: string): Promise<void> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).ziyaretIptal(ziyaretId);
  await istek<unknown>(`/api/ziyaret/${ziyaretId}/iptal`, {
    yontem: 'POST',
    govde: { neden },
  });
}

export async function binaAyrinti(serial: string): Promise<BinaAyrintisi> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).binaAyrinti(serial);
  return istek<BinaAyrintisi>(`/api/bina/${encodeURIComponent(serial)}`);
}

export async function haritaVerisi(bolge?: number | null): Promise<HaritaVerisi> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).haritaVerisi();
  const sorgu = bolge == null ? '' : `?bolge=${bolge}`;
  return istek<HaritaVerisi>(`/api/harita${sorgu}`, { zamanAsimiMs: 30000 });
}

/**
 * Yol ağı (arka plan çizgileri). Sözleşmede tanımlı değil; sunucu
 * `veri/ref/osm_yollar.geojson` dosyasını sunarsa harita daha okunur olur.
 * Uç yoksa harita yollarsız çizilir — hata verilmez.
 */
export async function yollar(bolge?: number | null): Promise<YolAgi | null> {
  if (SAHTE_IZIN && sahteMod) return (await sahteApi()).yollar();
  const sorgu = bolge == null ? '' : `?bolge=${bolge}`;
  try {
    return await istek<YolAgi>(`/api/yollar${sorgu}`, { zamanAsimiMs: 30000 });
  } catch {
    return null;
  }
}

/* ------------------------------ Ticket metni ------------------------------ */

export interface TicketSablonu {
  bina_serial: string;
  konu: TicketKonusu;
  /** OneDesk'e yapıştırılacak sekme ayrımlı metin. */
  metin: string;
  /** SİNYAL dışındaki konular: örnek metin gelene kadar taslak. */
  sablon_taslak: boolean;
  alanlar: {
    bina_serial: string;
    tellcordia_id: string;
    location_id: string;
    obek: string;
    site_adi: string;
  };
}

/**
 * Ticket metni sunucudan — tek doğruluk kaynağı `saha/ticket.py → ticket_metni()`.
 * Satışçı yalnız kendi bölgesindeki (ya da listesindeki) binanın metnini alır.
 * Çevrimdışıysa çağıran taraf `ortak/kimlik.ts → ticketMetni()` ile aynı metni üretir.
 */
export async function ticketSablonu(
  binaSerial: string,
  konu: TicketKonusu,
  ekip: string,
): Promise<TicketSablonu> {
  const sorgu = `bina_serial=${encodeURIComponent(binaSerial)}&konu=${encodeURIComponent(konu)}&ekip=${encodeURIComponent(ekip.trim())}`;
  return istek<TicketSablonu>(`/api/ticket/sablon?${sorgu}`, { zamanAsimiMs: 10000 });
}
