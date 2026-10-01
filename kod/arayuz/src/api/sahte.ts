/**
 * Örnek (sahte) sunucu — yalnız `?sahte=1` ile devreye girer.
 *
 * Sunucu hazır olmadan arayüzü geliştirip ekran görüntüsü alabilmek için var.
 * Sözleşmedeki uçların aynı biçimde yanıt verir, küçük bir gecikme ekler ve
 * gönderilen ziyaretleri bellekte tutar; böylece iyimser arayüz gerçekten test
 * edilebilir. Üretimde bu modül hiç indirilmez.
 */

import type {
  BenYaniti,
  BinaAyrintisi,
  BugunGorevi,
  GirisYaniti,
  GorevBinasi,
  HaritaVerisi,
  YolAgi,
  TopluYanit,
  ZiyaretKaydi,
  ZiyaretYaniti,
} from './tipler';
import { HARITA, META, ROTA, YOLLAR } from './sahteVeri';
import { SahaHatasi } from './istemci';

const GECIKME = 260;
const bekle = (ms = GECIKME) => new Promise<void>((c) => setTimeout(c, ms));

/** Örnek kullanıcı: 3 numaralı bölgenin satışçısı. */
const KULLANICI = {
  id: 3,
  ad: 'Murat Şahin',
  telefon: '5321234567',
  rol: 'satisci' as const,
  bolge: META.bolge,
  bolge_adi: META.bolge_adi,
  aktif: true,
};

/**
 * Örnek kipte ekran durumunu adresten seçebiliriz:
 *   ?sahte=1&durum=bitti → bütün liste tamamlanmış ("Liste bitti" ekranı)
 *   ?sahte=1&durum=bos   → bugün için görev yok ("Liste oluştur" ekranı)
 * Tasarımı gözden geçirirken bu ekranlara tıklaya tıklaya ulaşmak gerekmesin diye.
 */
function ekranDurumu(): 'normal' | 'bitti' | 'bos' {
  try {
    const deger = new URL(window.location.href).searchParams.get('durum');
    if (deger === 'bitti' || deger === 'bos') return deger;
  } catch {
    /* adres okunamazsa normal akış */
  }
  return 'normal';
}

const DURUM = ekranDurumu();

const rota: GorevBinasi[] = ROTA.map((b) =>
  DURUM === 'bitti'
    ? { ...b, gorev_durum: 'tamam' as const, durum: 'ziyaret_edildi' as const }
    : { ...b },
);
const gonderilen = new Map<string, ZiyaretKaydi>();

function bugunTarihi() {
  const g = new Date();
  return `${g.getFullYear()}-${String(g.getMonth() + 1).padStart(2, '0')}-${String(
    g.getDate(),
  ).padStart(2, '0')}`;
}

function satisSayisi() {
  let toplam = 0;
  gonderilen.forEach((z) => {
    if (z.sonuc === 'satis') toplam += z.satis_adedi ?? 1;
  });
  // Ekran boş görünmesin diye günün başlangıcında 3 satış varsayılır.
  return 3 + toplam;
}

/* ------------------------------ Uçlar ------------------------------ */

export async function giris(telefon: string, pin: string): Promise<GirisYaniti> {
  await bekle(420);
  const temiz = telefon.replace(/\D/g, '');
  if (temiz.length !== 10) throw new SahaHatasi('Telefon numarası 10 hane olmalı.', 'telefon', 400);
  if (temiz === '5550000000') return { pin_belirle: true };
  if (pin !== '1234') throw new SahaHatasi('PIN hatalı. Tekrar deneyin.', 'pin', 401);
  return { token: 'ornek-jeton', kullanici: { ...KULLANICI, telefon: temiz } };
}

export async function pinBelirle(telefon: string, _pin: string): Promise<GirisYaniti> {
  await bekle(420);
  return { token: 'ornek-jeton', kullanici: { ...KULLANICI, telefon: telefon.replace(/\D/g, '') } };
}

export async function ben(): Promise<BenYaniti> {
  await bekle();
  const tamam = rota.filter((b) => b.gorev_durum === 'tamam').length;
  return {
    kullanici: KULLANICI,
    bugun: {
      gorev_id: 1,
      toplam: rota.length,
      tamam,
      kalan: rota.length - tamam,
      satis: satisSayisi(),
    },
    hafta: { ziyaret: 86 + gonderilen.size, satis: 11 + (satisSayisi() - 3), randevu: 7 },
    bolge: {
      toplam: META.bolge_toplam,
      dokunulan: META.bolge_dokunulan + gonderilen.size,
      kalan: META.bolge_toplam - META.bolge_dokunulan - gonderilen.size,
      kalan_firsat: 20710,
    },
  };
}

export async function bugunGorevi(): Promise<BugunGorevi | null> {
  await bekle();
  if (DURUM === 'bos') return null;
  return { gorev_id: 1, tarih: bugunTarihi(), binalar: rota.map((b) => ({ ...b })) };
}

export async function gorevOlustur(adet = 25): Promise<BugunGorevi> {
  await bekle(900);
  rota.forEach((b) => {
    b.gorev_durum = 'bekliyor';
    b.durum = 'planli';
  });
  return { gorev_id: 2, tarih: bugunTarihi(), binalar: rota.slice(0, adet).map((b) => ({ ...b })) };
}

export async function ziyaretGonder(kayit: ZiyaretKaydi): Promise<ZiyaretYaniti> {
  await bekle(380);
  gonderilen.set(kayit.offline_id, kayit);
  const satir = rota.find((b) => b.bina_serial === kayit.bina_serial);
  if (satir) {
    satir.gorev_durum = 'tamam';
    satir.durum = 'ziyaret_edildi';
  }
  return {
    ziyaret_id: gonderilen.size,
    yinelenen: false,
    bina_serial: kayit.bina_serial,
    durum: 'ziyaret_edildi',
    durum_etiket: 'Ziyaret edildi',
    duzeltildi: Boolean(kayit.duzeltilen_offline_id),
    mesaj: 'Kaydedildi.',
  };
}

export async function ziyaretToplu(kayitlar: ZiyaretKaydi[]): Promise<TopluYanit> {
  await bekle(520);
  for (const k of kayitlar) {
    gonderilen.set(k.offline_id, k);
    const satir = rota.find((b) => b.bina_serial === k.bina_serial);
    if (satir) {
      satir.gorev_durum = 'tamam';
      satir.durum = 'ziyaret_edildi';
    }
  }
  return { kaydedilen: kayitlar.length, yinelenen: 0, hatali: [] };
}

export async function ziyaretIptal(_ziyaretId: number): Promise<void> {
  await bekle(200);
}

export async function binaAyrinti(serial: string): Promise<BinaAyrintisi> {
  await bekle(200);
  const bina = rota.find((b) => b.bina_serial === serial);
  if (!bina) throw new SahaHatasi('Bina bulunamadı.', 'yok', 404);
  const gecmis = [...gonderilen.values()]
    .filter((z) => z.bina_serial === serial)
    .map((z) => ({
      zaman: z.zaman,
      sonuc: z.sonuc,
      satis_adedi: z.satis_adedi ?? null,
      not: z.not ?? null,
      kullanici_ad: KULLANICI.ad,
    }));
  // Gerçek sunucu gibi: durum bilgisi AYRI bir nesnede değil, binanın kendisinde.
  return {
    bina: {
      ...bina,
      son_ziyaret: gecmis.length ? gecmis[gecmis.length - 1].zaman : null,
      son_sonuc: gecmis.length ? gecmis[gecmis.length - 1].sonuc : null,
      toplam_satis: 0,
    },
    ziyaretler: gecmis,
  };
}

export async function haritaVerisi(): Promise<HaritaVerisi> {
  await bekle(340);
  const veri: HaritaVerisi = {
    serial: HARITA.serial.slice(),
    lat: HARITA.lat.slice(),
    lon: HARITA.lon.slice(),
    durum: HARITA.durum.slice(),
    firsat: HARITA.firsat.slice(),
    ad: HARITA.ad ? HARITA.ad.slice() : undefined,
  };
  // Bugün işlenen ziyaretler haritada da yeşile dönsün.
  gonderilen.forEach((z) => {
    const i = veri.serial.indexOf(z.bina_serial);
    if (i >= 0) veri.durum[i] = z.sonuc === 'girilemedi' ? 'girilemedi' : 'ziyaret_edildi';
  });
  return veri;
}

export async function yollar(): Promise<YolAgi> {
  await bekle(120);
  return YOLLAR;
}
