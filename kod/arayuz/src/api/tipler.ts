/**
 * belgeler/SAHA_SOZLESME.md içindeki veri modelinin TypeScript karşılığı.
 * Bu dosya sözleşmenin tek doğruluk kaynağıdır; sunucu ile alan adları birebir aynıdır.
 */

/**
 * Görev (DB'de `kullanici.rol`). v2'de dört görev var; ekranda "Satış ·
 * Operasyon · Teknik · Yönetici" yazılır (OPERASYON_V2_SPEC §2.1). Bir kişinin
 * birden çok görevi olabilir (EK-1): `rol` ANA görevdir (girişte açılan ekran),
 * yetki görev kümesinin (`gorevler`) birleşiminden gelir.
 */
export type Rol = 'satisci' | 'operasyon' | 'teknik' | 'yonetici';

/** Girişten sonra açılan ana ekran (`/api/ben.ana_ekran`). */
export type AnaEkran = 'bugun' | 'isler' | 'islerim';

/** bina_durum.durum */
export type BinaDurumu =
  | 'bekliyor'
  | 'planli'
  | 'ziyaret_edildi'
  | 'tekrar_gel'
  | 'girilemedi'
  | 'altyapi_sorunu';

/** ziyaret.sonuc */
export type ZiyaretSonucu =
  | 'satis'
  | 'ilgilenmedi'
  | 'evde_yok'
  | 'randevu'
  | 'altyapi_sorunu'
  | 'girilemedi'
  | 'yanlis_adres';

/** gorev_bina.durum */
export type GorevBinaDurumu = 'bekliyor' | 'tamam' | 'atlandi';

export interface Kullanici {
  id: number;
  ad: string;
  telefon: string;
  rol: Rol;
  bolge: number | null;
  bolge_adi?: string | null;
  aktif?: boolean;
  /** EK-1: görev kümesi (ana görev dahil). Eski sunucu göndermez → [rol]. */
  gorevler?: Rol[];
}

export interface Bina {
  bina_serial: string;
  /**
   * Sunucunun hazırladığı görünen ad (site adı → sokak No → seri numarası).
   * Gerçek API her bina kartında gönderir; yalnız geliştirme fikstürü boş
   * bırakabilir, o durumda `ad` kullanılır (bkz. `binaBasligi`).
   */
  baslik?: string;
  /** `baslik` ile aynı metin; sözleşmedeki `bina.ad` alanının karşılığı. */
  ad: string;
  /** Sunucunun hazırladığı tek satırlık adres. */
  adres?: string;
  site_adi?: string | null;
  mahalle: string;
  ilce: string;
  il?: string;
  cadde?: string | null;
  sokak?: string | null;
  kapi_no?: string | null;
  lat: number;
  lon: number;
  kat?: number | null;
  daire?: number | null;
  res_hp?: number | null;
  aktif_res?: number | null;
  firsat?: number | null;
  sales_ready?: string | null;
  bolge?: number | null;
  site_grup?: string | null;
  /**
   * Binanın hayattaki hâli. Sözleşmedeki BinaKart bunu HER bina yanıtında
   * gönderir — liste kartında da, `/api/bina/{serial}` ayrıntısında da.
   * (Eskiden yalnız `GorevBinasi` üzerinde tanımlıydı, bu yüzden bina ekranı
   * sunucudan yeni okuduğu durumu kullanamıyordu.)
   */
  durum?: BinaDurumu;
  durum_etiket?: string;
  son_ziyaret?: string | null;
  son_sonuc?: ZiyaretSonucu | null;
  tekrar_tarih?: string | null;
  toplam_satis?: number | null;
  ziyaret_sayisi?: number | null;
  penetrasyon?: number | null;
  yeni_site?: boolean;
  /** Kimlikler — yönetici "Ayrıntılar" penceresi, BOSS/Fox eşleştirmesi. */
  kimlik?: {
    bina_serial: string;
    location_id?: string;
    tellcordia_id?: string;
    uavt_bina_kodu?: string;
  };
  blok_adi?: string;
  bina_turu?: string;
  toplam_hp?: number;
  altyapi?: string;
  teknoloji?: string;
  obek?: string;
  /** data.xlsx 'Site Adı' — ticket metninde bu yazılır (ör. 'MERSA SİT. D BLK. MERSA D'). */
  crm_site_adi?: string;
  /** Veri kalitesi notları (sözleşme §7.1). Sıra: sunucunun verdiği. */
  kalite?: KaliteBayragi[];
  /** Son tur raporunda yok: listeye girmez, geçmişi durur (§7.0). */
  pasif?: boolean;
}

/** Bir binanın veri notu: ne bulundu, düzeltildiyse neyden neye. */
export interface KaliteBayragi {
  kural: string;
  mesaj: string;
  seviye: 'bilgi' | 'uyari';
  duzeltme?: { alan: string; eski: string | number | null; yeni: string | number | null } | null;
}

/** Ticket konusu — sunucudaki `ticket.KONULAR` ile birebir. */
export type TicketKonusu = 'SİNYAL' | 'EK SP' | 'GÜZERGAH' | 'ALTYAPI' | 'DİĞER';

/** Ticket durumu. Açık sayılanlar: AÇIK · HATA · TRANSFER. */
export type TicketDurumu = 'AÇIK' | 'ÇÖZÜLDÜ' | 'HATA' | 'KAPATILDI' | 'İPTAL' | 'TRANSFER';

/** OneDesk ticket kaydı (sözleşme §7.4). */
export interface Ticket {
  id: number;
  /** OneDesk numarası; açılana kadar boş. */
  ticket_no: string;
  acilis: string | null;
  konu: TicketKonusu;
  konu_etiket: string;
  durum: TicketDurumu;
  acik: boolean;
  /** Açık ticket kaç gündür açık (kapalıda null). */
  acik_gun: number | null;
  bina_serial: string | null;
  location_id: string;
  site: string;
  musteri: string;
  kanal: string;
  detay: string;
  metin: string;
  olusturan: string | null;
  olusturma: string;
  guncelleme: string;
  kapanis: string | null;
  kaynak: 'uygulama' | 'excel' | string;
  /** EK-5: OneDesk ekibi (varsayılan TEAM-TAS1BRS) — eski sunucu göndermez. */
  onedesk_ekip?: string | null;
  /** EK-5: OneDesk başlığı ("NETWORK / GPON / SINYAL YOK / MEVCUT BINA" …). */
  kategori?: string | null;
  /** EK-8: PS26'dan gelen tür ('guzergah' vb.); yoksa normal ticket. */
  tur?: string | null;
  /** EK-8: ekli fotoğraf sayısı (WP-G `ticket_ek`); yoksa gösterilmez. */
  ek_sayisi?: number | null;
  bina: {
    bina_serial: string;
    ad: string;
    bolge: number | null;
    ilce: string | null;
    mahalle: string | null;
    lat: number | null;
    lon: number | null;
  } | null;
}

/**
 * Bugünün listesindeki bir satır: bina + göreve ait alanlar.
 *
 * DİKKAT — iki ayrı durum vardır, karıştırılmamalı:
 *   `durum`       binanın hayattaki hâli: bekliyor · planli · ziyaret_edildi …
 *                 (bugünün listesine giren bina `planli` olur)
 *   `gorev_durum` BUGÜNÜN listesindeki hâli: bekliyor · tamam · atlandi
 *
 * "Bu binayı gezdim mi?" sorusunun cevabı her zaman `gorev_durum`tur.
 */
export interface GorevBinasi extends Bina {
  sira: number;
  /** Bugünün listesindeki durumu — listede "bitti mi" bunu okur. */
  gorev_durum: GorevBinaDurumu;
  mesafe_m?: number | null;
}

export interface BugunGorevi {
  gorev_id: number;
  tarih: string; // YYYY-AA-GG
  binalar: GorevBinasi[];
  /**
   * AYNI GÜN daha önce bitirilmiş listelerin binaları. Satışçı 25'i bitirip
   * yeni liste alınca sabahki emek ekrandan silinmesin diye "Bitenler"in
   * altına eklenir; ilerleme sayacına karışmaz.
   */
  onceki_binalar?: GorevBinasi[];
  toplam_mesafe_m?: number;
  /** Tur bir günde gezilemeyecek kadar uzunsa sunucunun Türkçe uyarısı. */
  uyari?: string | null;
  ozet?: GunOzeti;
}

export interface GunOzeti {
  gorev_id: number | null;
  toplam: number;
  tamam: number;
  kalan: number;
  /** Satılan ABONELİK adedi (satışçının primi buna bağlı). */
  satis: number;
  /** Satışla biten BİNA sayısı. Dönüşümün payı budur. */
  satis_bina?: number;
  ziyaret?: number;
  /** Sunucudan gelen tek dönüşüm tanımı: satışla biten bina / gezilen bina. */
  donusum?: number;
}

export interface HaftaOzeti {
  ziyaret: number;
  /** Satışla biten bina. */
  satis: number;
  /** Satılan abonelik adedi. */
  satis_adedi?: number;
  randevu: number;
  donusum?: number;
}

export interface BolgeOzeti {
  toplam: number;
  dokunulan: number;
  kalan: number;
  /** Henüz SATILMAMIŞ boş kapı. */
  kalan_firsat?: number;
}

/** Sunucudan gelen etiket sözlüğü — tek doğruluk kaynağı ayarlar.py. */
export interface Etiketler {
  sonuc?: Partial<Record<ZiyaretSonucu, string>>;
  durum?: Partial<Record<BinaDurumu, string>>;
}

/** GET /api/ben */
export interface BenYaniti {
  kullanici: Kullanici;
  /**
   * Sunucuda GÖSTERİM (demo) verisi kurulu. Ekranlardaki sayılar uydurmadır;
   * uygulama bunu her yerde açıkça yazar (bkz. `DemoSeridi`).
   */
  demo?: boolean;
  bugun: GunOzeti;
  /** Sözleşme dışı, isteğe bağlı genişletme — yoksa ekranda gösterilmez. */
  hafta?: HaftaOzeti;
  /** Sözleşme dışı, isteğe bağlı genişletme — yoksa ekranda gösterilmez. */
  bolge?: BolgeOzeti;
  /** Sonuç/durum etiketleri sunucudan gelir; istemcideki liste yalnız yedek. */
  etiketler?: Etiketler;

  /* ---- v2 ortak alanlar (§5.3.1). Eski sunucu göndermez; istemci bunları
     `ortak/yetki.ts` ile rolden türetir. ---- */
  /** Girişte açılacak ekran. */
  ana_ekran?: AnaEkran;
  /** Kişinin izinleri (görev kümesinin birleşimi) — menü bundan çizilir. */
  izinler?: string[];
  /** "Yönetici" · "Operasyon + Yönetici" gibi ekranda yazılan görev adı. */
  gorev_etiketi?: string;
  /** Satış: bölgesi yoksa "Size henüz bölge atanmadı" (§2.4). */
  bolge_yok?: boolean;
  /** Yönetici: dört göreve geçişten sonra görevler henüz gözden geçirilmedi (§6.10). */
  gorev_gozden_gecir?: boolean;
  /** Operasyon dalı: yardım satırı. */
  yardim?: { ad?: string | null; telefon?: string | null } | null;
  /** EK-6: küçük sevinçler açık mı (ayar `kutlamalar`, varsayılan açık). */
  kutlamalar?: boolean;
}

/**
 * Teknik görevlinin `/api/ben.bugun` dalı (§5.3.1). Satışçınınkinden farklı
 * olduğu için `BenYaniti.bugun` bu biçimde de gelebilir; teknik ekranı onu
 * bu tiple okur.
 */
export interface TeknikBugun {
  is: number;
  btk: number;
  biten: number;
}

/** POST /api/giris */
export interface GirisYaniti {
  token?: string;
  kullanici?: Kullanici;
  /** İlk giriş: kullanıcının PIN'i henüz yok. */
  pin_belirle?: boolean;
  /** Sunucunun kendi açıklaması ("İlk giriş. Davet kodunuzla..."). */
  mesaj?: string | null;
}

/** Bir ziyaret kaydı — çevrimdışı kuyrukta da aynı biçimde tutulur. */
export interface ZiyaretKaydi {
  offline_id: string;
  bina_serial: string;
  sonuc: ZiyaretSonucu;
  satis_adedi?: number;
  konusulan_daire?: string;
  not?: string;
  lat?: number | null;
  lon?: number | null;
  zaman: string; // ISO 8601
  /** Sözleşme dışı, isteğe bağlı: randevu/tekrar için hedef tarih (YYYY-AA-GG). */
  tekrar_tarih?: string;
  cihaz?: string;
  /**
   * Bu kayıt bir DÜZELTME: aynı binada bu offline_id'li eski ziyaret iptal
   * edilir ve sayaçlardan düşer. Yanlış düğmeye basmak sahada en sık yapılan
   * hatadır; ikinci bir kayıt eklemek ilkini silmiyordu.
   */
  duzeltilen_offline_id?: string;
}

/** POST /api/ziyaret yanıtı. */
export interface ZiyaretYaniti {
  ziyaret_id: number | null;
  yinelenen: boolean;
  bina_serial: string;
  durum: BinaDurumu;
  durum_etiket: string;
  duzeltildi?: boolean;
  mesaj?: string;
  ozet?: GunOzeti;
}

/**
 * POST /api/ziyaret/toplu yanıtı.
 * `hatali` OKUNMAK ZORUNDA: sunucu kısmi hatada 200 döner, reddettiği
 * kayıtları burada bildirir. Bu liste yok sayılırsa gerçek ziyaretler
 * sessizce kaybolur.
 */
export interface TopluYanit {
  kaydedilen: number;
  yinelenen: number;
  /**
   * Sunucunun YAZDIĞINI ONAYLADIĞI kayıtlar. Kuyruktan yalnız bunlar silinir —
   * "hata listesinde yok" demek "yazıldı" demek değildir.
   */
  kabul?: string[];
  hatali: Array<{ offline_id: string; hata: string; kod?: string }>;
  ozet?: GunOzeti;
}

/** GET /api/bina/{serial} */
export interface BinaAyrintisi {
  /**
   * Binanın SUNUCUDAN yeni okunmuş hâli. Durum, son sonuç ve toplam satış
   * burada; ayrı bir `durum` nesnesi YOK. (Eskiden tip böyle bir nesne vaat
   * ediyordu, sunucu hiç göndermiyordu: ekran sessizce listedeki eski karta
   * düşüyordu ve düzeltmeden sonra rozet güncellenmiyordu.)
   */
  bina: Bina;
  ziyaretler: Array<{
    id?: number;
    offline_id?: string;
    zaman: string;
    sonuc: ZiyaretSonucu;
    sonuc_etiket?: string;
    satis_adedi?: number | null;
    konusulan_daire?: number | string | null;
    notu?: string | null;
    not?: string | null;
    kullanici_id?: number | null;
    kullanici?: string | null;
    kullanici_ad?: string | null;
  }>;
  /** Bu binaya açılmış ticket'lar (açıklar önce, sonra yeni→eski). */
  ticketlar?: Ticket[];
}

/** GET /api/harita?bolge= — sıkı diziler (binlerce bina için hafif). */
export interface HaritaVerisi {
  serial: string[];
  lat: number[];
  lon: number[];
  durum: BinaDurumu[];
  firsat: number[];
  /** Sözleşme dışı, isteğe bağlı: kart başlığı için bina adı. */
  ad?: string[];
}

/**
 * GET /api/yollar — haritanın arka planındaki yol çizgileri.
 * Sözleşmede yok; sunucu `veri/ref/osm_yollar.geojson` dosyasını sunarsa kullanılır.
 */
export interface YolAgi {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry:
      | { type: 'LineString'; coordinates: number[][] }
      | { type: 'MultiLineString'; coordinates: number[][][] };
    properties?: Record<string, unknown> | null;
  }>;
}

/** Sunucu hata biçimi. */
export interface ApiHatasi {
  hata: string;
  kod?: string;
}
