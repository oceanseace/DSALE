/**
 * İş emri akışı v2 — sunucu ile arayüzün ortak sözleşmesi.
 *
 * Kaynak: belgeler/OPERASYON_V2_SPEC.md §5.2 (birebir) + belgeler/OPERASYON_V2_EK.md
 * (EK-1 görev kümesi, EK-2 girişsiz kişi ve unvan, EK-3 askı aralıkları ve net
 * BTK saati, EK-4 BOSS giden kutusu, EK-10 klasör izleme, EK-12 Turkcell süreç
 * kuralları: öncelik, BTK şikâyet sayacı, arama merdiveni, kesinti). Alan adları
 * `operasyon/v2/gorunum.py` ve `operasyon/v2/api.py` ile birebir aynıdır.
 *
 * Değişiklik günlüğü (WP-B, 30.09 akşam): EK-12 alanları eklendi — IsSatir.oncelik /
 * btk_sikayet / genel_ariza; IsAyrinti.aski_uyari / merdiven / aramalar;
 * BossGiden.alanlar.talep_ulasamama_sms; KurallarYanit, Kesinti*, Arama*; yeni hata
 * kodları. Hepsi EKLEMEDİR, var olan alan değişmedi.
 *
 * Sahibi WP-B. 0. saatten sonra yalnız WP-B değiştirir ve değişiklik
 * OPERASYON_V2_SPEC "Değişiklik günlüğü"ne yazılır. Zamanlar sunucunun
 * `zaman_metni()` biçimindedir: Türkiye saati, "AAAA-AA-GG SS:DD:ss".
 */

// ----------------------------------------------------------------------------- temel
export type Rol = 'satisci' | 'operasyon' | 'teknik' | 'yonetici';
export type Durum = 'triyaj'|'bekliyor'|'randevulu'|'atandi'|'yolda'|'sahada'
                  |'ulasilamadi'|'askida'|'altyapi'|'merkeze'|'cozuldu'|'kapandi';
export type Kova = 'atanmadi' | 'teknikte' | 'beklemede' | 'biten';
export type Serit = 'BTK' | 'SAHA' | 'MASA' | 'LOJISTIK';
export type Renk = 'yesil' | 'amber' | 'kirmizi';
export type KanalGrubu = 'global' | 'dehanet' | 'diger_bayi' | 'kurumsal' | 'bos';
export type TriyajNedeni = 'il_disi' | 'mahalle_yok' | 'obeksiz' | 'mahalle_benzer' | 'altyapi_supheli';
export type Rozet = 'btk'|'ticket'|'tekrar'|'bayi'|'global'|'konum'|'boss_islenecek'|'boss_acik'|'yeniden'|'elle';
/** §6.2 tek birincil eylem kodu (sunucu üretir). */
export type BirincilEylem = 'obege_ata' | 'ata' | 'yeniden_ata' | 'uyandir' | 'ticketi_ac' | 'ticketa_bagla' | 'sahaya_al';

/**
 * Kişi (iş tutan ya da öneri alan). EK-1/EK-2 alanları isteğe bağlıdır: yalnız
 * operasyon/yönetici yanıtlarında gelir. `giris_var=false` → "Girişsiz · BOSS Mobil".
 */
export interface Kisi {
  id: number; ad: string;
  gorevler?: Rol[];               // EK-1: görev kümesi (ana görev dahil)
  unvan?: string | null;          // EK-2: Turkcell unvanı (rehberden)
  giris_var?: boolean;            // EK-2: telefonu var mı (yoksa bizde giriş yapamaz)
}

// ----------------------------------------------------------------------------- EK-12 yardımcı tipler
/** EK-12.2: BTK şikâyet sayacı (iş günü). Şikâyet işaretli değilse satırda null. */
export interface BtkSikayet {
  baslama: string; reopen: boolean;
  sure_is_gunu: number;           // 10 (reopen 5) — ayar.btk_sikayet
  gecen_is_gunu: number; kalan_is_gunu: number;
  son_gun: string;                // sürenin bittiği iş gününün sonu
  alarm: string | null;           // "8. iş günü" | "10. iş günü" (reopen "3." / "5.") | null
  gecikti: boolean;
  tcs: string | null;             // tahmini çözüm tarihi (bir kez girilir)
  btk_kapali: boolean;            // TÇS girildi → "BTK'da kapalı, FOX'ta açık"
}
/** EK-12.4: masa aramasının sonucu. */
export type AramaSonucu = 'ulasildi' | 'ulasilamadi' | 'mesgul_kapali' | 'dit' | 'yanlis_no';
export interface AramaKaydi {
  zaman: string; sonuc: AramaSonucu; sure_sn: number | null;
  webphone: boolean;              // Webphone dışı arama askı hakkı vermez
  sms: boolean;                   // "Talep Ulaşamama SMS" gönderildi mi
  yeni_numara: boolean;           // merdiven bu aramadan başlar
  kisi: string | null;
}
/** EK-12.4: ulaşılamayan müşteri merdiveni (gün 1: 2 arama ≥3 s arayla; gün 2: 2 arama). */
export interface AramaMerdiveni {
  deneme: number; gecerli: number; gerekli: number; gunler: number[];
  son: string | null;
  sonraki: string | null;         // bir sonraki aramanın en erken zamanı (pencere içinde)
  tamam: boolean;                 // "Müşteriye ulaşılamadı" kapanışı yalnız tamamsa açılır
  eksik: string | null;           // "2 arama daha gerekli (2/4)"
  sms_eksik: number; ulasildi: boolean;
  ata_havuzu: boolean;            // son arama "irtibat hatalı" → ATA havuzu
}

// ----------------------------------------------------------------------------- iş satırı
export interface IsSatir {
  is_no: string; boss_task_no: string | null; kaynak: 'boss' | 'bayi'; kanal_grubu: KanalGrubu | null;
  task_adi: string; serit: Serit; btk_hedef_saat: number | null;
  durum: Durum; kova: Kova; durum_zamani: string;
  il: string | null; ilce: string | null; mahalle: string | null;
  musteri_adi?: string | null;        // yalnız is.musteri izniyle (teknikte kısa ad)
  musteri_no?: string | null;         // yalnız is.musteri izniyle
  kisa_adres?: string | null;         // "Görükle · X Sitesi" (yalnız is.musteri izniyle)
  obek: { id: number; ad: string; renk: number } | null; obek_elle: boolean;
  triyaj_nedeni: TriyajNedeni | null; triyaj_metni: string | null;
  konum_yaklasik: boolean; lat: number | null; lon: number | null;
  acilis: string; son24: string; btk_hedef: string | null;
  kalan_dk: number; renk: Renk; gecikti: boolean;
  bekleme_dk: number | null;          // atanmamışsa gorulme_zamani'ndan beri; değilse null
  randevu: { bas: string; bit: string; teyitli: boolean; kaynak: 'biz' | 'boss' } | null;
  atanan: Kisi | null;
  oneri: { teknik: Kisi; bas: string | null; bit: string | null; neden: string } | null;
  boss_ekip?: string | null;          // yalnız operasyon/yönetici
  ticket: { id: number; konu: string; durum: string; gun: number } | null;
  binada_acik_ticket: number;
  rozetler: Rozet[];
  kotu_gecmis: boolean; sira: number | null;
  surum: number;
  // --- EK-3: BTK saati abone kaynaklı askıda durur -------------------------
  /** Şu an BTK saatini durduran bir askı sürüyor mu. */
  btk_durdu: boolean;
  /** btk_hedef + Σ(durduran askı süresi); BTK değilse null. Renk ve "Gecikti" BTK'da buna göre. */
  btk_hedef_net: string | null;
  /** btk_hedef_net − şimdi (dakika; askı sürüyorsa donmuş değer). BTK değilse null. */
  btk_kalan_dk: number | null;
  // --- EK-12 ---------------------------------------------------------------
  /** Öncelikli iş tipi (ör. 40 Kanal Şikâyeti: "süre zaten kaçmış — önce bu"); liste en üstte. Yoksa null. */
  oncelik: string | null;
  /** BTK şikâyeti işaretliyse 10/5 iş günü sayacı; değilse null. */
  btk_sikayet: BtkSikayet | null;
  /** "Genel arıza — sevk etme" (kesinti bülteni yüzünden askıda). */
  genel_ariza: boolean;
}

export interface Olay { id: number; zaman: string; kisi: string | null; tur: string; ozet: string; notu: string | null; }

/** EK-3: bir askı aralığı. `bitis=null` → sürüyor. */
export interface AskiAraligi {
  id: number;
  baslama: string; bitis: string | null;
  neden: string | null;
  kaynak: 'boss' | 'elle';
  durdurur: boolean;              // bu askı BTK saatini durduruyor mu (ayar kuralından)
  yaklasik: boolean;              // BOSS raporundan: başlangıç raporun indirildiği ana yuvarlandı
  sure_dk: number;                // şimdiye kadar (sürüyorsa şimdiye)
}

/** EK-4: BOSS'a birebir yazılacak değerler (giden kutusu satırı; eklentiye hazır). */
export interface BossGiden {
  is_no: string;
  boss_task_no: string | null;
  alanlar: {
    ekip: string | null; randevu_baslangic: string | null; randevu_bitis: string | null;
    aski_nedeni?: string | null; uyanma?: string | null;      // neden 'aski' içeriyorsa
    talep_ulasamama_sms?: boolean;                             // EK-12.4: neden 'sms' içeriyorsa (BOSS "Talep Ulaşamama SMS")
  };
  neden: string;                  // 'ekip' | 'randevu' | 'aski' | 'sms' — virgülle birleşik ("ekip,randevu")
  olusma: string;                 // bayrağın düştüğü an
}

export interface IsAyrinti extends IsSatir {
  adres?: string | null; musteri_tel?: string | null;
  lokasyon: string | null; mahalle_kaynak: string | null; konum_kaynak: string | null;
  bina: { serial: string; ad: string | null; location_id: string | null; lat: number; lon: number } | null;
  boss: { durum: string | null; randevu_durumu: string | null; randevu_bas: string | null; randevu_bit: string | null;
          ekip: string | null; aski_nedeni: string | null; sl: string | null; sl_saat: number | null;
          son_aciklama: string | null; bekleyen: string | null; islendi: string | null };
  uyanma: string | null; askida_neden: string | null; evde_yok_sayisi: number;
  masa_vade: string | null; teshis_sonucu: string | null;
  soz: string;                        // "Müşteriye söz: bugün 17:00'ye kadar"
  birincil: BirincilEylem | null;     // §6.2 tablosundaki eylem kodu
  izinler: { ata: boolean; randevu: boolean; ticket: boolean; obek: boolean; iletisim: boolean;
             durumlar: Durum[]; ofisten_kapat: boolean; yeniden_ac: boolean; boss_bagla: boolean };
  boss_url: string | null;
  bayi_oneri: { boss_task_no: string } | null;
  olaylar: Olay[];                    // yeniden eskiye, en çok 50
  // --- EK-3 ---
  aski: AskiAraligi[];                // eskiden yeniye
  aski_durdu_dk: number;              // Σ durduran askı (dakika)
  btk_net_gecen_dk: number | null;    // (şimdi − açılış) − Σ durduran askı; BTK değilse null
  // --- EK-4 ---
  boss_giden: BossGiden | null;       // "BOSS'a gir: Ekip … · 11:00–13:00 [Kopyala]"
  // --- diğer ---
  kapanis: string | null; kapanis_nedeni: string | null;
  acilma_sayisi: number;
  ilk_gorulme: string; gorulme_zamani: string;
  // --- EK-12 ---
  /** "Geçersiz askı: … Süre BTK saatine eklenmiyor." ya da abone askısı sınıra yaklaştı; yoksa null. */
  aski_uyari: string | null;
  /** Yalnız operasyon/yönetici: masa aramaları (eskiden yeniye, en çok 20) ve merdiven (açık işte). */
  aramalar?: AramaKaydi[];
  merdiven?: AramaMerdiveni | null;
}

// ----------------------------------------------------------------------------- İşler panosu
export interface SonAktarim {
  id: number; zaman: string; dosya_adi: string; is_sayisi: number; yas_dk: number; renk: Renk;
  yontem?: 'surukle' | 'komut' | 'klasor';          // EK-10
  fark?: { yeni: number; degisen: number; kaybolan: number; yeniden_acilan: number; degismeyen: number };
}

/** EK-10: bekçiye takıldığı için kendiliğinden uygulanmamış rapor. */
export interface OnayBekleyenRapor {
  aktarim_id: number; zaman: string; dosya_adi: string;
  yontem: 'surukle' | 'komut' | 'klasor';
  nedenler: Array<'cok_kaybolan' | 'eski_rapor'>;
  fark: { yeni: number; degisen: number; kaybolan: number; yeniden_acilan: number; degismeyen: number };
  mesaj: string;                  // §6.7 bekçi cümlesi
}

export interface IslerSayac {
  acik: number; asan24: number; atanmamis: number; en_eski_atanmamis_dk: number | null; btk48: number;
  kontrol: number; boss_bekleyen: number; konum_yaklasik: number; aranacak: number; eslesmemis_ekip: number;
  // EK-3
  askida_btk_durdu: number; askida_uyanmasiz: number;
}

export interface IslerYanit {
  sunucu_zamani: string; imlec: number; obek_surumu: number; mod: 'normal' | 'asiri_yuk';
  son_aktarim: SonAktarim | null;
  sayac: IslerSayac;
  isler: IsSatir[];
  /** EK-6: durumdan üretilen tek hikâye cümlesi ("Bugün 437 iş var. 12'sinin …"). */
  hikaye: string;
  /** EK-10: klasörden gelip onay bekleyen raporlar (boşsa []). */
  onay_bekleyen: OnayBekleyenRapor[];
}

export interface DegisimYanit {
  imlec: number; isler: IsSatir[]; gorunmez: string[]; obek_surumu: number;
  son_aktarim: SonAktarim | null; sayac: IslerSayac;
  sunucu_zamani: string; onay_bekleyen: OnayBekleyenRapor[];
}

/** Toplu işlemler: oneri-onayla, toplu-ata, boss-ekip/esle, is-aktar. */
export interface TopluSonuc {
  toplu_id: string;
  atanan: string[];
  atlanan: Array<{ is_no: string; kod: string; hata: string }>;
}
export interface TopluGeriAlSonuc { geri_alinan: string[]; atlanan: Array<{ is_no: string; kod: string }>; }

export interface TeknikOzet extends Kisi {
  etiket: string[];
  boss_ekip: string | null;
  kapasite: number;
  bugun: { atanan: number; biten: number; btk: number };
  obekler: Array<{ id: number; ad: string }>;
  bugun_yok: boolean;
}

export interface BossEkipYanit {
  eslesmemis: Array<{ boss_ekip: string; is: number }>;
  eslesmis: Array<{ boss_ekip: string; kisi: Kisi }>;
}

export interface AranacakYanit {
  sunucu_zamani: string;
  bantlar: Array<{ bant: 'btk_teshis' | 'ulasilamadi' | 'uyanan' | 'masa'; isler: IsSatir[] }>;
}

export interface DagitOnizleme { gruplar: Array<{ teknik_id: number; is_nolar: string[]; btk: number; km: number }>; }

export interface YeniIsYanit { is_no: string; is: IsAyrinti; }

/** Ekranın ihtiyaç duyduğu ayarlar (`GET /api/isler/ayarlar`, is.liste). */
export interface IsAyarlari {
  dilimler: Array<{ bas: string; bit: string }>;         // "08:00"–"10:00"
  mesai: { bas: string; bit: string };
  musteri_tel: 'acik' | 'kapali';
  boss_task_url: string | null;
  aski_nedenleri: Array<{ kod: string; metin: string; durdurur: boolean }>;   // EK-3
  son24_askida_durur: boolean;                                              // EK-3
  btk_durduran_aski?: string[];                                             // EK-3/EK-12.3
  kutlamalar: boolean;                                                      // EK-6
  kapanis_nedenleri: Array<{ kod: string; metin: string }>;
  teknik_kapasite?: number;
}

/** EK-12: `GET /api/isler/kurallar` — her kural ayardır; değer + varsayılan + teyit notu. */
export interface KuralKaydi<T = unknown> {
  deger: T; varsayilan: T; aciklama: string;
  teyit_bekliyor: string | null;  // belgede kesin değil, kullanıcı teyidi bekliyor
  degisti: boolean;               // varsayılandan farklı (ayar yazılmış)
}
export type KuralAdi =
  | 'hedef_saatleri' | 'serit_kurallari' | 'oncelikli_isler' | 'btk_durduran_aski' | 'aski_sinirlari' | 'aski_gecerlilik'
  | 'arama_merdiveni' | 'btk_sikayet' | 'resmi_tatiller' | 'kesinti_etkilenen' | 'kesinti_ornek_esigi' | 'kesinti_ornek_saat';
export type KurallarYanit = Record<KuralAdi, KuralKaydi>;

/** EK-12.6: yapıştırılan "Santral Arıza" bülteni. */
export interface Kesinti {
  id: number; no: string | null; tur: 'GPON' | 'FTTX' | null;
  durum: 'devam' | 'planli' | 'bitti'; durum_metni: string;
  baslama: string; baslama_saat: string | null; bitis: string | null;
  etki_musteri: number | null; ekleyen: string | null;
  ilceler: Array<{ il_k: string; ilce_k: string; il: string; ilce: string }>; ilce_metni: string;
  ozet: string;
  askida_is?: number;             // bu bülten yüzünden askıdaki iş
}
export interface KesintiListesi { kesintiler: Kesinti[]; }
export interface KesintiEkleYanit { kesinti: Kesinti; askiya_alinan: string[]; atlanan: Array<{ is_no: string; kod: string }>; }
export interface KesintiBitirYanit { kesinti: Kesinti; uyanan: string[]; }
/** Bülten yokken toplu arıza şüphesi: "verimlilik ekibine gönder" paketi (sekme ayrımlı; kopyalanır). */
export interface KesintiAdaylari {
  esik: number; saat: number;
  gruplar: Array<{ il: string; ilce: string; adet: number; is_nolar: string[]; paket: string }>;
}

// ----------------------------------------------------------------------------- Teknik
export interface IslerimYanit {
  sunucu_zamani: string; imlec: number;
  isler: IsAyrinti[];                 // kendi açık işleri, sira ile
  bitenler: IsSatir[];                // bugün
}

// ----------------------------------------------------------------------------- Aktarım
export interface AktarimFark { yeni: number; degisen: number; kaybolan: number; yeniden_acilan: number; degismeyen: number; }
export interface AktarimSonucu {
  aktarim_id: number;
  ayni_dosya?: boolean; zaman?: string;             // aynı dosya yeniden bırakıldıysa yalnız bunlar anlamlı
  fark: AktarimFark;
  cikarilan: { kurulum: number; ikinci_donanim: number; istisna_tutulan: number; satir: number; adlar: Record<string, number> };
  kontrol: number; boss_atamasi: number; sure_sn: number; yedek: string | null;
  tam_kapsam: boolean;
  aski: { acilan: number; kapanan: number };         // EK-3
}
/** 409 onay_gerekli gövdesi. */
export interface AktarimOnay {
  hata: string; kod: 'onay_gerekli';
  aktarim_id: number; fark: AktarimFark; nedenler: Array<'cok_kaybolan' | 'eski_rapor'>;
  acik: number; kaybolan_oran: number; son_rapor_zamani: string | null;
}
export interface AktarimKaydi {
  id: number; zaman: string; yukleyen: string | null; dosya_adi: string; yontem: 'surukle' | 'komut' | 'klasor';
  is_sayisi: number | null; yeni: number | null; degisen: number | null; kaybolan: number | null;
  yeniden_acilan: number | null; degismeyen: number | null; cikarilan: number | null;
  durum: 'isleniyor' | 'onay_bekliyor' | 'uygulandi' | 'vazgecildi' | 'hata';
  tam_kapsam: boolean; yedek: string | null; hata: string | null;
}

/** EK-10: klasör izleme durumu (`GET /api/aktarim/izleme`). */
export interface IzlemeDurumu {
  acik: boolean;
  calisiyor?: boolean;            // izleme iş parçacığı bu sunucuda açık mı
  klasorler_varsayilan?: boolean; // klasörler ayarlanmamış: İndirilenler + Masaüstü
  klasorler: string[]; desenler: string[];
  yoklama_sn: number; sabit_sn: number;
  son_bakis: string | null;
  son_alinan: { aktarim_id: number | null; zaman: string; dosya_adi: string; sonuc: string } | null;
  onay_bekleyen: OnayBekleyenRapor[];
}

// ----------------------------------------------------------------------------- Öbekler
export interface ObekMahalle { ref: string; il: string; ilce: string; mahalle: string; tum_ilce: boolean; acik: number; }
export interface Obek {
  id: number; ad: string; renk: number;
  sahip: Kisi | null; yedek: Kisi | null;
  mahalleler: ObekMahalle[];
  acik: number; geciken: number; btk: number; atanmamis: number;
}
export interface ObeklerYanit {
  surum: number;
  obekler: Obek[];
  obeksiz: Array<{ il: string; ilce: string; mahalle: string; mahalle_id: number | null; acik: number }>;
}
export interface ObekDegisimYanit {
  surum: number; etkilenen_is: number; obekler: Obek[];
  geri_al_olay_id?: number; obeksiz_kalan_is?: number;
}
export interface IlceKaydi {
  il: string; ilce: string; il_k: string; ilce_k: string; mahalle_sayisi: number;
  tum_ilce_obek: { id: number; ad: string } | null;
}
export interface MahalleKaydi {
  id: number; il: string; ilce: string; ad: string; ref: string; kaynak: string;
  obek: { id: number; ad: string } | null; acik: number;
}
export interface MahallelerYanit {
  ilceler: IlceKaydi[];
  mahalleler: MahalleKaydi[];
  oneriler: Array<{ id: number; ad: string; ilce: string; benzerlik: number }>;
}

// ----------------------------------------------------------------------------- Takip
export interface HizAdimi { adim: string; medyan_dk: number | null; p90_dk: number | null; n: number; hedef_dk: number; hedefte_oran: number | null; }
export interface TakipYanit {
  sunucu_zamani: string;
  hikaye: string;                                     // EK-6
  manset: { acik: number; asan24: number; atanmamis: number; en_eski_atanmamis_dk: number | null; btk48: number;
            en_yasli_btk_s: number | null; kontrol: number };
  uyum24: { oran: number | null; n: number; yaklasik: boolean; egim: Array<{ gun: string; oran: number | null }> };
  btk: { tv6: number | null; baglanti12: number | null; teshis45: number | null };
  birikim: { asan24: number; egim_gun: number | null; seri: Array<{ zaman: string; acik: number; asan24: number }> };
  kapasite: { talep: number; aktif: number; kapasite: number; mod: 'normal' | 'asiri_yuk'; esnek_oneri: number; elle: boolean;
              mesaj: string | null };       // "Ekip'ten Teknik görevli kişi ekleyin." (teknik yoksa)
  hiz_hatti: HizAdimi[];
  hijyen: { cozuldu_boss_acik: number; askida_uyanmasiz: number; boss_islenecek: number; rapor_yas_dk: number | null;
            askida_btk_durdu: number;               // EK-3
            btk_alarm: number;                      // EK-12.2: alarm gününe gelmiş (TÇS'siz) BTK şikâyeti
            genel_ariza: number;                    // EK-12.6: kesinti yüzünden askıda
            oncelikli: number };                    // EK-12.5: açık öncelikli iş (kanal şikâyeti)
  obekler: Array<{ id: number; ad: string; acik: number; geciken: number; btk: number; atanmamis: number; sahip: Kisi | null }>;
  teknikler: Array<{ id: number; ad: string; atanan: number; biten: number; evde_yok: number; yolda_sahada: number; ilk_is: string | null }>;
  sistem: { son_rapor: string | null; son_yedek: string | null; son_goc: string | null; saklama_metni: string };
}
export interface TakipSatisYanit {
  demo_dahil: boolean;
  bugun: { ziyaret: number; temas: number; satis: number; aktif_satisci: number; toplam_satisci: number };
  hafta: { ziyaret: number; temas: number; satis: number; hedef: number | null; ilerleme: number | null };
  huni: { ziyaret: number; temas: number; satis: number };
  satiscilar: Array<{ id: number; ad: string; bolge: number | null; bugun_ziyaret: number; bugun_satis: number;
                      hafta_ziyaret: number; hafta_satis: number; donusum: number | null }>;
  altyapisi_cozulen_bina: number;
}

// ----------------------------------------------------------------------------- hata
export type HataKodu =
  | 'yasak' | 'baska_bolge' | 'is_yok' | 'gorev_degisti' | 'guncel_degil' | 'gecersiz_gecis' | 'altyapi_engeli'
  | 'tekrar_ariza' | 'teyit_gerekli' | 'randevu_gecersiz' | 'alan_eksik' | 'teknik_gecersiz' | 'onay_gerekli'
  | 'aktarim_suruyor' | 'rapor_tanimadi' | 'ayni_dosya' | 'baska_obekte' | 'ad_var' | 'benzer_var' | 'var' | 'ilce_yok'
  | 'boss_no_kullanilmis' | 'task_no_gecersiz' | 'tel_kapali' | 'telefon_gecersiz' | 'butunluk' | 'guncelleme_bekliyor'
  | 'yedek_alinamadi' | 'yenilendi' | 'sure_doldu' | 'geri_alinamaz' | 'durum_gecersiz' | 'buyuk_dosya'
  | 'uyanma_gecersiz' | 'oneri_yok' | 'rapor_okunamadi'
  // EK-12
  | 'arama_saati' | 'arama_kisa' | 'merdiven_eksik' | 'btk_iptal_yasak' | 'btk_sikayet_yok' | 'tcs_var' | 'tcs_gecersiz'
  | 'bulten_bitti';

/** Sunucunun hata gövdesi. 409 guncel_degil'de `guncel` + `degistiren` + `zaman` da gelir. */
export interface HataYaniti {
  hata: string; kod: HataKodu | string;
  guncel?: IsAyrinti; degistiren?: string | null; zaman?: string | null;
  merdiven?: AramaMerdiveni;      // 409 merdiven_eksik
  catisma?: Array<{ ref: string; obek: { id: number; ad: string } }>;
  oneriler?: Array<{ id: number; ad: string; ilce: string; benzerlik: number }>;
}

// ----------------------------------------------------------------------------- sabit sözlük
/** Ekranda görünen durum adları (§3.1). */
export const DURUM_ETIKET: Record<Durum, string> = {
  triyaj: 'Kontrol gerekli', bekliyor: 'Atanmadı', randevulu: 'Randevu verildi', atandi: 'Atandı',
  yolda: 'Yolda', sahada: 'Sahada', ulasilamadi: 'Ulaşılamadı', askida: 'Askıda', altyapi: 'Altyapı bekliyor',
  merkeze: 'Merkeze gönderildi', cozuldu: 'Çözüldü', kapandi: 'Kapandı',
};
export const KOVA_ETIKET: Record<Kova, string> = {
  atanmadi: 'Atanmadı', teknikte: 'Teknikte', beklemede: 'Beklemede', biten: 'Biten',
};
export const DURUM_KOVA: Record<Durum, Kova> = {
  triyaj: 'atanmadi', bekliyor: 'atanmadi', randevulu: 'atanmadi',
  atandi: 'teknikte', yolda: 'teknikte', sahada: 'teknikte',
  ulasilamadi: 'beklemede', askida: 'beklemede', altyapi: 'beklemede', merkeze: 'beklemede',
  cozuldu: 'biten', kapandi: 'biten',
};
