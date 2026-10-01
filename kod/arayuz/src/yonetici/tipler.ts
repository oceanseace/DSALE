/**
 * Yönetici uçlarının yanıt biçimleri.
 *
 * Alan adları sunucudaki `saha/api.py` ile birebir aynıdır; sözleşmenin
 * yönetici bölümünün (§3 "Yönetici", §4.6) TypeScript karşılığıdır.
 */

import type {
  BinaDurumu,
  KaliteBayragi,
  Rol,
  Ticket,
  TicketDurumu,
  TicketKonusu,
  ZiyaretSonucu,
} from '../api/tipler';

/** Sunucunun her bina yanıtında kullandığı ortak kart biçimi. */
export interface BinaKart {
  bina_serial: string;
  baslik: string;
  adres: string;
  site_adi: string;
  site_grup: string;
  mahalle: string;
  ilce: string;
  sokak: string;
  kapi_no: string;
  lat: number;
  lon: number;
  kat: number;
  daire: number;
  res_hp: number;
  aktif_res: number;
  firsat: number;
  penetrasyon: number;
  sales_ready: string | null;
  yeni_site: boolean;
  bolge: number | null;
  durum: BinaDurumu;
  durum_etiket: string;
  son_ziyaret: string | null;
  /** Öncelik sınıfı: 0 sözü olan · 1 hiç dokunulmamış · 2 tekrar ziyaret. */
  sinif?: number;
  son_sonuc: ZiyaretSonucu | null;
  tekrar_tarih: string | null;
  toplam_satis: number;
  ziyaret_sayisi: number;
  /* göreve ait ek alanlar */
  sira?: number;
  mesafe_m?: number;
  oncelik?: number;
  gorev_durum?: 'bekliyor' | 'tamam' | 'atlandi';
}

/** GET /api/ozet/gun — bir satışçının bugünü. */
export interface SatisciGunu {
  kullanici_id: number;
  ad: string;
  bolge: number | null;
  gorev_id: number | null;
  ziyaret: number;
  satis: number;
  satis_adedi: number;
  ret: number;
  randevu: number;
  evde_yok: number;
  girilemedi: number;
  altyapi_sorunu: number;
  kalan: number;
  donusum: number;
  /** Günün listesindeki bina sayısı — ilerleme çubuğunun PAYDASI. */
  gorev_toplam?: number;
  /** Listeden kapatılan bina sayısı — ilerleme çubuğunun PAYI. */
  gorev_tamam?: number;
}

export interface GunToplami {
  ziyaret: number;
  satis: number;
  satis_adedi: number;
  gorev_toplam?: number;
  gorev_tamam?: number;
  ret: number;
  randevu: number;
  kalan: number;
  donusum: number;
}

export interface GunOzetiYaniti {
  tarih: string;
  satiscilar: SatisciGunu[];
  toplam: GunToplami;
}

/** GET /api/ozet/kapsama */
export interface KapsamaSatiri {
  ad: string;
  toplam: number;
  dokunulan: number;
  /** Kapı açıldı, biriyle konuşuldu (girilemedi/altyapı hariç). */
  temas?: number;
  kalan: number;
  oran: number;
  firsat: number;
  /** Henüz SATILMAMIŞ boş kapı. */
  kalan_firsat: number;
  /** Hiç dokunulmamış binalardaki boş kapı (eski ölçü, ayrı kutu). */
  dokunulmayan_firsat?: number;
  satis_bina?: number;
  mahalle?: string | null;
  ilce?: string | null;
  satis: number;
}

export interface KapsamaYaniti extends Omit<KapsamaSatiri, 'ad'> {
  kirilim: 'bolge' | 'mahalle' | 'ilce';
  satirlar: KapsamaSatiri[];
}

/** GET /api/harita — sıkı diziler; yönetici bütün bölgeleri alır. */
export interface YoneticiHaritaVerisi {
  adet: number;
  serial: string[];
  /** Bina adı (site/blok) — haritada seri numarası yerine gösterilir. */
  ad?: string[];
  loc?: string[];
  lat: number[];
  lon: number[];
  durum: BinaDurumu[];
  firsat: number[];
  bolge: Array<number | null>;
  ofis: { ad: string; lat: number; lon: number };
}

/**
 * GET /api/kullanici (spec §5.3.7 + EK-1/EK-2).
 *
 * Listede telefon MASKELİDİR ("0532 ••• •• 06") ve `telefon` alanı yoktur; tam
 * hâli yalnız tek kişi yanıtında (`GET /api/kullanici/{id}`) gelir. Davet kodu
 * listede artık DÖNMEZ (yalnız oluşturma / yeni kod yanıtında bir kez).
 */
export interface YoneticiKullanici {
  id: number;
  ad: string;
  /** Yalnız tek kişi yanıtında; girişsiz kişide null. */
  telefon?: string | null;
  telefon_goster: string;
  /** ANA görev: girişte açılan ekran. */
  rol: Rol;
  /** EK-1: görev kümesi (ana görev dahil). Eski sunucu göndermez. */
  gorevler?: Rol[];
  gorev_etiketi?: string;
  bolge: number | null;
  aktif: boolean;
  pin_var: boolean;
  /** v1 sunucusu gönderiyordu; v2'de yok. */
  davet_kodu?: string | null;
  /** EK-2: telefonu var mı (yoksa "Girişsiz · BOSS Mobil"). */
  giris_var?: boolean;
  unvan?: string | null;
  kaynak?: 'elle' | 'rehber' | string | null;
  /** ["lider"] gibi — yetki VERMEZ. */
  etiket?: string[] | null;
  boss_ekip?: string | null;
  kapasite?: number | null;
  davet_bekliyor?: boolean;
  davet_suresi_doldu?: boolean;
  son_etkinlik?: string | null;
  /** Ev teknisyeni olduğu öbekler (öbeğin `sahip_id`'si). */
  obekler?: Array<{ id: number; ad: string }>;
}

export interface KullaniciKaydiYaniti {
  kullanici: YoneticiKullanici;
  davet_kodu: string | null;
  oturum_dustu?: boolean;
  davet_gecerlilik_saat?: number;
}

/** GET /api/kullanici/{id}/iliskiler — silmeden önce sayım (F13). */
export interface KullaniciIliskileri {
  silinebilir: boolean;
  engeller: Array<'kendini_silemez' | 'son_yonetici' | 'iliskili_kayit' | string>;
  sayilar: Record<string, number>;
  acik_is: number;
  obek_sahipligi: number;
  obekleri_birak_gerekli?: boolean;
  demo: number;
  hepsi_demo?: boolean;
  /** "312 ziyaret" gibi insanın okuyacağı karşılıklar. */
  etiketler: Array<{ metin: string; sayi: number }>;
}

/** POST /api/kullanici/rehber — önizleme ve uygulama aynı biçimde döner. */
export interface RehberSonucu {
  okunan: number;
  okunamayan_satir: number;
  ayni: number;
  eklenecek: Array<{ ad: string; unvan: string | null; gorevler: Rol[]; rol: Rol }>;
  guncellenecek: Array<{ id: number; ad: string; unvan_eski: string | null; unvan: string }>;
  atlanacak: Array<{ ad: string; unvan: string | null; neden: 'gorev_yok' | 'unvan_yok' | string }>;
  sayilar: { eklenecek: number; guncellenecek: number; atlanacak: number; ayni: number };
  uygulandi: boolean;
}

/** Unvan → görev eşlemesi (ayar `unvan_gorev_esleme`); ilk eşleşen kural kazanır. */
export interface UnvanKurali {
  desen: string;
  gorevler: Rol[];
}

export interface PinSifirlamaYaniti {
  kullanici_id: number;
  davet_kodu: string;
  mesaj: string;
}

/** POST /api/gorev/ata */
export interface AtamaIstegi {
  kullanici_id: number;
  tarih?: string;
  bina_serial?: string[];
  mahalle?: string;
  bbox?: [number, number, number, number];
  adet?: number;
  notu?: string;
}

export interface AtamaYaniti {
  gorev_id: number;
  tarih: string;
  kullanici: { id: number; ad: string; bolge: number | null };
  eklenen: number;
  binalar: BinaKart[];
  ozet: { toplam: number; tamam: number; kalan: number; satis: number };
}

/** GET /api/bina */
export interface BinaListesiYaniti {
  toplam: number;
  limit: number;
  offset: number;
  binalar: BinaKart[];
}

/** GET /api/gorev/bugun?kullanici_id= */
export interface GorevYaniti {
  gorev_id: number | null;
  tarih: string;
  kaynak?: string | null;
  notu?: string | null;
  binalar: BinaKart[];
  toplam_mesafe_m: number;
  ozet: { toplam: number; tamam: number; kalan: number; satis: number };
  mesaj?: string;
}

/* =========================================================================
   Faz 2 (sözleşme §7): veri kalitesi · bölge planlayıcı · tur raporu · ticket
   ========================================================================= */

/* ------------------------------ Veri kalitesi ------------------------------ */

export interface KaliteKurali {
  kural: string;
  ad: string;
  seviye: 'bilgi' | 'uyari';
  aciklama: string;
  /** Bu kural değeri kendisi düzeltebiliyor mu (güvenli düzeltme)? */
  duzeltir: boolean;
  adet: number;
  duzeltilen: number;
}

/** GET /api/kalite/ozet */
export interface KaliteOzeti {
  toplam_bina: number;
  bayrakli_bina: number;
  hesaplanmamis: number;
  kural_surumu: string;
  kurallar: KaliteKurali[];
}

export interface KaliteBinasi {
  bina_serial: string;
  baslik: string;
  ad: string;
  site_adi: string;
  sokak: string;
  kapi_no: string;
  mahalle: string;
  ilce: string;
  bolge: number | null;
  lat: number;
  lon: number;
  location_id: string;
  tellcordia_id: string;
  res_hp: number;
  aktif_res: number;
  kat: number;
  daire: number;
  kalite: KaliteBayragi[];
}

/** GET /api/kalite/liste */
export interface KaliteListesi {
  toplam: number;
  limit: number;
  offset: number;
  binalar: KaliteBinasi[];
}

/* ------------------------------ Bölge planlayıcı ------------------------------ */

/** Bir bölgedeki satışçının kısa kartı. */
export interface PlanSatiscisi {
  id: number;
  ad: string;
  telefon_goster: string;
  aktif: boolean;
  pin_var: boolean;
  eski_bolge?: number;
  yeni_bolge?: number;
}

export interface GeoCokgen {
  type: 'MultiPolygon' | 'Polygon';
  coordinates: number[][][][] | number[][][];
}

export interface PlanBolgesi {
  bolge: number;
  ad: string;
  kisa_ad: string;
  /** "#6EFF3D" — sunumdaki ve Excel'deki renk. */
  renk: string;
  bina: number;
  res_hp: number;
  aktif_res: number;
  toplam_hp: number;
  firsat: number;
  kalan_firsat: number;
  dokunulan: number;
  dokunulan_oran: number;
  satis: number;
  ziyaret: number;
  penetrasyon: number | null;
  /** Ölçünün ortalamadan sapması (0,001 = %0,1). */
  sapma: number;
  poligon: GeoCokgen | null;
  satiscilar: PlanSatiscisi[];
  /* yalnız önizlemede */
  merkez?: [number, number] | null;
  etiket?: [number, number] | null;
  yeni_satisci_acilacak?: boolean;
  nereden?: Array<{ bolge: number | null; bina: number }>;
}

export type PlanOlcusu = 'res_hp' | 'firsat' | 'toplam_hp' | 'bina';

export interface PlanGecmisi {
  id: number;
  n: number;
  olcu: string;
  kaynak: string;
  zaman: string;
  aktif: number | boolean;
  geri_alindi: number | boolean;
  onceki_id: number | null;
  notu: string | null;
  olusturan: string | null;
}

export interface HesapIsi {
  is_id: string;
  n: number;
  olcu: string;
  durum: 'bekliyor' | 'calisiyor' | 'bitti' | 'hata';
  /** 0..1 — bölgeleme aşamasında süreye göre TAHMİNİ. */
  ilerleme: number;
  asama: string;
  mesaj: string | null;
  baslangic: string | null;
  bitis: string | null;
  tahmini_sn: number;
}

/** GET /api/bolgeleme/durum */
export interface BolgelemeDurumu {
  n: number;
  olcu: PlanOlcusu;
  plan: { id: number; n: number; kaynak: string; zaman: string; notu: string | null } | null;
  geri_alinabilir: boolean;
  bolgeler: PlanBolgesi[];
  toplam: {
    bina: number;
    res_hp: number;
    firsat: number;
    kalan_firsat: number;
    dokunulan: number;
    satis: number;
    dokunulan_oran: number;
  };
  bolgesiz_satiscilar: Array<PlanSatiscisi & { bolge: number | null }>;
  bolgesiz_bina: number;
  hazir_nler: number[];
  en_az_n: number;
  en_cok_n: number;
  calisan_is: HesapIsi | null;
  gecmis: PlanGecmisi[];
}

export interface PlanFarki {
  aktif_bina: number;
  el_degistiren_bina: number;
  el_degistiren_oran: number;
  el_degistiren_ziyaret: number;
  el_degistiren_dokunulmus_bina: number;
  numarasi_degisen_bina: number;
  bugun_listede_el_degistiren: number;
  satisci_hareketleri: PlanSatiscisi[];
  bolgesiz_kalacak_satiscilar: PlanSatiscisi[];
  yeni_satisci_acilacak_bolgeler: number[];
  kalkan_bolgeler: number[];
}

/** GET /api/bolgeleme/onizleme — plan hazır (200). */
export interface PlanOnizlemesi {
  hazir: true;
  n: number;
  olcu: PlanOlcusu;
  plan_ref: string;
  kaynak: 'hazir' | 'onbellek' | 'hesap' | string;
  kaynak_ad: string;
  mevcut_n: number;
  bolgeler: PlanBolgesi[];
  denge: { sapma_min: number; sapma_maks: number };
  fark: PlanFarki;
  uyarilar: string[];
  /** /api/harita (bölgesiz istek) seri sırasıyla yeni bölge numaraları. */
  bina_bolge: number[];
}

/** GET /api/bolgeleme/onizleme — plan hesaplanıyor (202). */
export interface PlanHesaplaniyor {
  hazir: false;
  n: number;
  olcu: PlanOlcusu;
  is: HesapIsi;
  mesaj: string;
}

export interface YeniSatisciHesabi {
  id: number;
  ad: string;
  bolge: number;
  telefon: string;
  telefon_goster: string;
  davet_kodu: string;
}

/** POST /api/bolgeleme/uygula */
export interface PlanUygulamaYaniti {
  plan_id: number;
  n: number;
  onceki_plan_id: number | null;
  degisen_bina: number;
  el_degistiren_bina: number;
  el_degistiren_ziyaret: number;
  yeni_satiscilar: YeniSatisciHesabi[];
  mesaj: string;
}

/** POST /api/bolgeleme/geri-al */
export interface GeriAlmaYaniti {
  plan_id: number;
  geri_alinan_plan_id: number;
  n: number;
  degisen_bina: number;
  kapatilan_yer_tutucular: Array<{ id: number; ad: string; pin_belirlemisti: boolean }>;
  mesaj: string;
}

/* ------------------------------ Tur raporu / OneMap ------------------------------ */

export interface TurToplami {
  bina: number;
  res_hp: number;
  aktif_res: number;
  firsat: number;
  toplam_hp: number;
}

export interface TurDegisenBina {
  bina_serial: string;
  ad: string;
  bolge: number | null;
  ilce: string | null;
  /** {alan: [eski, yeni]} */
  degisim: Record<string, [number, number]>;
  firsat_fark: number;
}

export interface TurFarki {
  once: TurToplami;
  sonra: TurToplami;
  sonra_haric_yeni: TurToplami;
  yeni_bina: number;
  yeni_bina_il_disi: number;
  il_disi_dagilim: Record<string, number>;
  cikan_bina: number;
  cikan_oran: number;
  pasif_onay_gerekli: boolean;
  geri_donen_bina: number;
  degisen_bina: number;
  degismeyen_bina: number;
  ornek: {
    yeni: Array<{
      bina_serial: string;
      ad: string;
      site_adi_crm: string;
      ilce_crm: string;
      il: string;
      res_hp: number;
      aktif_res: number;
      firsat: number;
    }>;
    cikan: Array<{
      bina_serial: string;
      ad: string;
      site_adi: string;
      ilce: string;
      bolge: number | null;
      res_hp: number;
      firsat: number;
    }>;
    degisen: TurDegisenBina[];
    geri_donen: Array<{ bina_serial: string; ad: string; ilce: string; bolge: number | null }>;
  };
  hizmet_illeri: string[];
  uyarilar: string[];
}

/** POST /api/veri/tur-raporu · GET /api/veri/tur-raporu/{id} */
export interface TurOnizlemesi {
  tur_id: number;
  dosya: string;
  dosya_adi: string;
  yukleme?: string;
  durum?: 'onizleme' | 'uygulandi' | 'eskidi';
  uygulama?: string | null;
  okuma: {
    sayfa: string;
    satir: number;
    tekil_bina: number;
    bos_serial: number;
    tekrar: number;
    tekrar_ornek?: string[];
    bozuk_tellcordia: number;
  };
  fark: TurFarki;
  ayni_dosya_daha_once: { id: number; yukleme: string; durum: string } | null;
}

export interface TurKaydi {
  tur_id: number;
  dosya: string;
  yukleme: string;
  durum: 'onizleme' | 'uygulandi' | 'eskidi';
  uygulama: string | null;
  yukleyen: string | null;
  yeni_bina: number | null;
  cikan_bina: number | null;
  degisen_bina: number | null;
}

export interface TurListesi {
  raporlar: TurKaydi[];
  son_uygulanan: { tur_id: number; zaman: string } | null;
}

export interface TurUygulamaYaniti {
  tur_id: number;
  zaten_uygulandi: boolean;
  guncellenen_bina?: number;
  pasife_alinan_bina?: number;
  geri_donen_bina?: number;
  konum_bekleyen_bina?: number;
  once?: TurToplami;
  sonra?: TurToplami;
  mesaj: string;
}

export interface BekleyenBina {
  bina_serial: string;
  tellcordia_id: string | null;
  location_id: string | null;
  ad: string | null;
  site_adi: string | null;
  ilce: string | null;
  il: string | null;
  res_hp: number | null;
  firsat: number | null;
  durum: 'konum_bekliyor' | 'eklendi' | 'rapordan_cikti';
  tur_id: number | null;
  eklenme: string | null;
}

export interface BekleyenListesi {
  durum: string;
  toplam: number;
  binalar: BekleyenBina[];
}

/** POST /api/veri/onemap */
export interface OneMapYaniti {
  eklenen: number;
  eslesmeyen: number;
  zaten_haritada: number;
  konumsuz: number;
  hala_bekleyen: number;
  binalar: Array<{
    bina_serial: string;
    ad: string;
    bolge: number | null;
    lat: number;
    lon: number;
    site_grup: string;
  }>;
  mesaj: string;
}

/* ------------------------------ Ticket defteri ------------------------------ */

/** GET /api/ticket */
export interface TicketListesi {
  toplam: number;
  limit: number;
  offset: number;
  sayilar: Record<TicketDurumu, number>;
  acik_toplam: number;
  acik_konu: Record<TicketKonusu, number>;
  ticketlar: Ticket[];
}

export interface TicketGecmisSatiri {
  id: number;
  zaman: string;
  eski_durum: TicketDurumu | null;
  yeni_durum: TicketDurumu | null;
  notu: string | null;
  /** {alan: [eski, yeni]} */
  alanlar: Record<string, [string | null, string | null]> | null;
  kullanici: string | null;
}

/** GET /api/ticket/{id} · PATCH yanıtı da bu alanları taşır. */
export interface TicketAyrintisi {
  ticket: Ticket;
  gecmis: TicketGecmisSatiri[];
  degisti?: boolean;
  alanlar?: string[];
}

export interface TicketGirdisi {
  konu: TicketKonusu;
  bina_serial?: string | null;
  location_id?: string | null;
  ticket_no?: string | null;
  acilis?: string | null;
  durum?: TicketDurumu;
  musteri?: string | null;
  kanal?: string | null;
  detay?: string | null;
  site?: string | null;
  ekip?: string | null;
  metin?: string | null;
  notu?: string | null;
  /** EK-5: OneDesk ekibi (varsayılan TEAM-TAS1BRS) ve başlığı. */
  onedesk_ekip?: string | null;
  kategori?: string | null;
}

export interface TicketGuncelleme {
  durum?: TicketDurumu;
  ticket_no?: string;
  acilis?: string;
  konu?: TicketKonusu;
  musteri?: string;
  kanal?: string;
  detay?: string;
  site?: string;
  location_id?: string;
  notu?: string;
  onedesk_ekip?: string;
  kategori?: string;
}

/** GET /api/bina/{serial}/degisim */
export interface BinaDegisimleri {
  bina_serial: string;
  degisimler: Array<{
    kaynak: string;
    alan: string;
    eski: string | null;
    yeni: string | null;
    zaman: string;
  }>;
}
