"""Süreç tasarımının makine-okur parametreleri + birikmiş iş eritme senaryosu.

surec.md'deki durum makinesi, zaman bütçeleri, rol→ekran listesi ve kurtarma
planı sayıları TEK KAYNAKTAN buradan gelir. Belge ile bu dosya çelişirse bu
dosya doğrudur; belge güncellenir.

Girdi : operasyon/analiz/cikti/surec_veri.json (surec_analiz.py üretir)
Çıktı : operasyon/analiz/cikti/surec_parametre.json

Çalıştırma:
  .venv/Scripts/python.exe operasyon/analiz/surec_analiz.py
  .venv/Scripts/python.exe operasyon/analiz/surec_parametre.py
"""

from __future__ import annotations

import json
from pathlib import Path

BURASI = Path(__file__).resolve().parent
VERI = BURASI / "cikti" / "surec_veri.json"
CIKTI = BURASI / "cikti" / "surec_parametre.json"

# ---------------------------------------------------------------------------
# 1. Şeritler (lane) ve saat hedefleri
#    turkcell_sl: FOX 'Hedef SL' sütunundan ölçüldü (0 = FOX'ta hedef yok).
#    bayi_hedef : bayi kuralı 24 saat; Turkcell hedefi daha sıkıysa o geçerli.
# ---------------------------------------------------------------------------
SERITLER = {
    "BTK": {
        "ad": "BTK hızlı şerit (arıza)",
        "task_adlari": ["Bağlantı Problemi", "TV+ Arıza", "Arama Problemi", "Doping Arıza Bildirimi"],
        "fox_adlari": ["Bağlantı Problemleri", "IP TV Arıza", "Arama Problemi", "Arıza Bildirim",
                       "BTK Şikayet", "BTK / Mahkeme Şikayet"],
        "turkcell_sl_saat": {"TV+ Arıza": 6, "Bağlantı Problemi": 12, "Arama Problemi": 12,
                             "Doping Arıza Bildirimi": 24, "BTK / Mahkeme Şikayet": 4, "BTK Şikayet": 168},
        "bayi_hedef_saat": "min(turkcell_sl, 24)",
        "sahibi": "Mevcut müşteri sorumlusu (kullanıcı) + BTK masası",
        "temas": "paralel: atama hemen + operasyon uzaktan ön-teşhis araması (bekletmez)",
    },
    "CIHAZ": {
        "ad": "Cihaz / donanım hizmeti",
        "task_adlari": ["2.Donanım", "Modem Değişikliği", "Superbox Modem Değişikliği", "STB Cihaz Değişikliği"],
        "bayi_hedef_saat": 24,
        "sahibi": "Mevcut müşteri sorumlusu",
        "temas": "doğrudan atama + teknisyen rota kurarken arar",
    },
    "MASA": {
        "ad": "Masa işi (sahaya gitmeden, telefonla)",
        "task_adlari": ["Kanal Şikayeti", "Teknik Servis Ücretlendirme"],
        "turkcell_sl_saat": {"Kanal Şikayeti": 24},
        "bayi_hedef_saat": 24,
        "sahibi": "Operasyon arama masası",
        "temas": "operasyon arar; sahaya yalnız gerekirse iner",
    },
    "LOJISTIK": {
        "ad": "Lojistik (iade, geri alım, evrak)",
        "task_adlari": ["Cihaz İade Bekleniyor", "Cihaz Geri Alım", "Turksat Cihaz İade - Yerinde Hizmet",
                        "Sosyal Destek Evrak Toplama", "Turksat Evrak Toplama"],
        "turkcell_sl_saat": {"Cihaz İade Bekleniyor": 24, "Cihaz Geri Alım": 48},
        "bayi_hedef_saat": 24,
        "sahibi": "Operasyon lojistik masası",
        "temas": "SMS/arama ile 'bayiye/kargoya teslim' seçeneği; kalan → rotaya dolgu durağı",
    },
    "KURULUM": {
        "ad": "Yeni müşteri kurulumu",
        "kural": "Task adında 'kurulum' geçen (Kurulum Taskı Ürememiş hariç)",
        "bayi_hedef_saat": 24,
        "sahibi": "Yeni müşteri kurulum ekipleri (operasyon triaj masası 24 saati izler)",
        "temas": "doğrudan atama + teknisyen rota kurarken arar",
    },
}

# ---------------------------------------------------------------------------
# 2. Durum makinesi
#    boss/fox: dış sistemde bu durumun nasıl göründüğü (eşleme)
#    butce_dk : standart şerit (24 s) için bu durumda kalınabilecek en uzun süre
#    btk_butce_dk: BTK şeridi (TV 6 s / bağlantı 12 s) için
# ---------------------------------------------------------------------------
DURUMLAR = [
    {"kod": "S0_GELDI", "ad": "Geldi", "sahibi": "Sistem",
     "boss": "Açık, Ekip boş", "fox": "*KUYRUKTA",
     "butce_dk": 5, "btk_butce_dk": 5,
     "cikis": "Otomatik sınıflama (şerit + öncelik + altyapı ön kontrol)"},
    {"kod": "S1_TRIAJ", "ad": "Triaj", "sahibi": "Operasyon triaj/atama masası",
     "boss": "Açık, Ekip boş", "fox": "*KUYRUKTA",
     "butce_dk": 30, "btk_butce_dk": 15,
     "cikis": "S2_MASADA | S3_ATANDI | E3_ALTYAPI (bina bayraklı) | E5_KAPANDI (mükerrer/Fox'ta kapalı)"},
    {"kod": "S2_MASADA", "ad": "Masada (telefonla çözüm)", "sahibi": "Operasyon arama masası",
     "boss": "Açık", "fox": "*KUYRUKTA",
     "butce_dk": 240, "btk_butce_dk": 30,
     "cikis": "E5_KAPANDI (telefonda çözüldü) | S3_ATANDI (saha gerekli) | E1_ULASILAMADI"},
    {"kod": "S3_ATANDI", "ad": "Ekibe atandı", "sahibi": "Teknisyen",
     "boss": "Açık, Ekip dolu", "fox": "*ATANDI",
     "butce_dk": 120, "btk_butce_dk": 30,
     "cikis": "S4_TEYITLI (müşteriye ulaştı, saat verdi) | E1_ULASILAMADI (2 deneme) | E2_ASKI_ABONE (ileri tarih ister)"},
    {"kod": "S4_TEYITLI", "ad": "Teyitli (zaman penceresi verildi)", "sahibi": "Teknisyen",
     "boss": "Randevulu (2 saatlik pencere)", "fox": "*ATANDI",
     "butce_dk": 1080, "btk_butce_dk": 240,
     "cikis": "S5_YOLDA"},
    {"kod": "S5_YOLDA", "ad": "Yolda", "sahibi": "Teknisyen",
     "boss": "Konum Paylaşıldı", "fox": "*ATANDI",
     "butce_dk": 60, "btk_butce_dk": 45,
     "cikis": "S6_SAHADA | E1_ULASILAMADI (kapıda yok, 10 dk bekleme + 1 arama)"},
    {"kod": "S6_SAHADA", "ad": "Sahada", "sahibi": "Teknisyen",
     "boss": "Başlandı", "fox": "*ATANDI",
     "butce_dk": 120, "btk_butce_dk": 90,
     "cikis": "S7_TAMAM | E3_ALTYAPI (güzergah/sinyal/port) | E4_MALZEME (stok/cihaz) | E2_ASKI_ABONE"},
    {"kod": "S7_TAMAM", "ad": "Tamamlandı", "sahibi": "Teknisyen → sistem",
     "boss": "Bitirildi (açık rapordan düşer)", "fox": "kapalı",
     "butce_dk": 30, "btk_butce_dk": 15,
     "cikis": "S8_DOGRULANDI | E6_TEKRAR (7 gün içinde aynı müşteride yeni arıza)"},
    {"kod": "S8_DOGRULANDI", "ad": "Doğrulandı", "sahibi": "Operasyon (veri/rapor)",
     "boss": "yok (açık listede değil)", "fox": "yok (açık/askı listesinde değil)",
     "butce_dk": None, "btk_butce_dk": None,
     "cikis": "son (24 s saatine dahil değil; ertesi sabah otomatik)"},
    # --- istisnalar / eskalasyon ---
    {"kod": "E1_ULASILAMADI", "ad": "Ulaşılamadı", "sahibi": "Operasyon arama masası",
     "boss": "Merkeze gönderildi: ABONEYE ULAŞILAMADI - MÜSAİT DEĞİL", "fox": "*KUYRUKTA",
     "butce_dk": 1440, "btk_butce_dk": 240,
     "kural": "3 deneme farklı saatlerde (hemen, +2 s, 17-19 arası) + SMS; ulaşılırsa aynı gün/ertesi sabah rotaya; 3 başarısız → E2_ASKI_ABONE"},
    {"kod": "E2_ASKI_ABONE", "ad": "Askı: abone kaynaklı", "sahibi": "Operasyon arama masası (uyandırma)",
     "boss": "Askıya alındı: Abone kaynaklı", "fox": "ASKIDA",
     "butce_dk": 4320, "btk_butce_dk": 1440,
     "kural": "Askı ancak neden + uyanma tarihi ile açılır; uyanma günü sabah 08:00 kuyruğuna düşer; en çok 3 gün (ileri tarih randevu hariç, en çok 7 gün); süre dolunca kapatma/iptal kararı"},
    {"kod": "E3_ALTYAPI", "ad": "Altyapı / TT bekliyor", "sahibi": "Operasyon altyapı masası; OneDesk ticket'ı kullanıcı açar",
     "boss": "Askıya alındı: TT kaynaklı | Merkeze gönderildi: GÜZERGAH YOK / SİNYAL YOK / BOŞ PORT YOK",
     "fox": "ASKIDA",
     "butce_dk": 2880, "btk_butce_dk": 240,
     "kural": "Bina (Lokasyon) bazında TEK ticket; aynı binadaki tüm işler ticket'a bağlanır; 48 saatte bir durum sorgusu; ticket kapanınca işler S1_TRIAJ'a geri döner ve satışa haber gider"},
    {"kod": "E4_MALZEME", "ad": "Malzeme / stok bekliyor", "sahibi": "Operasyon lojistik masası",
     "boss": "Açık (Son Açıklama: stok/depo)", "fox": "*ATANDI",
     "butce_dk": 480, "btk_butce_dk": 120,
     "kural": "Depodan aynı gün çıkış; stok yoksa yönetici uyarısı"},
    {"kod": "E5_KAPANDI", "ad": "İşsiz kapandı", "sahibi": "Operasyon",
     "boss": "kapalı", "fox": "kapalı",
     "butce_dk": None, "btk_butce_dk": None,
     "kural": "Telefonda çözüldü / müşteri iptal / mükerrer / Fox'ta zaten kapalı; neden kodu zorunlu"},
    {"kod": "E6_TEKRAR", "ad": "Tekrar arıza", "sahibi": "Mevcut müşteri sorumlusu",
     "boss": "yeni task", "fox": "yeni akış",
     "butce_dk": None, "btk_butce_dk": None,
     "kural": "Aynı müşteri/bina 7 gün içinde yeniden arıza → ilk seferde çözüm sayılmaz; kıdemli teknisyene atanır"},
]

# Standart şerit için 24 saatin dağılımı (dakika) — toplam 1440
BUTCE_24S = {
    "S0_GELDI": 5, "S1_TRIAJ": 30, "S3_ATANDI (temas)": 120,
    "S4_TEYITLI (rotada bekleme, gece dahil)": 1080, "S5_YOLDA": 60, "S6_SAHADA": 120, "S7_TAMAM (kapanış)": 25,
}
# BTK şeridi: bağlantı 12 s (720 dk), TV arıza 6 s (360 dk)
BUTCE_BTK_12S = {"S0_GELDI": 5, "S1_TRIAJ": 15, "S3_ATANDI (temas + paralel ön-teşhis)": 30,
                 "S4_TEYITLI (rotada bekleme)": 525, "S5_YOLDA": 45, "S6_SAHADA": 90, "S7_TAMAM": 10}
BUTCE_BTK_6S = {"S0_GELDI": 5, "S1_TRIAJ": 10, "S3_ATANDI (temas + paralel ön-teşhis)": 20,
                "S4_TEYITLI (rotada bekleme)": 180, "S5_YOLDA": 45, "S6_SAHADA": 90, "S7_TAMAM": 10}

# Eskalasyon tetikleri (bütçenin yüzdesi tüketildiğinde)
ESKALASYON = [
    {"tetik": "durum bütçesinin %100'ü doldu", "kime": "durumun sahibi (uygulama bildirimi)"},
    {"tetik": "işin toplam hedefinin %50'si doldu ve iş S5_YOLDA'ya gelmedi", "kime": "operasyon vardiya lideri (sarı)"},
    {"tetik": "işin toplam hedefinin %80'i doldu", "kime": "BTK ise kullanıcı + yönetici; diğer işlerde vardiya lideri (kırmızı)"},
    {"tetik": "hedef aşıldı", "kime": "günlük raporun 'geciken' listesi; ertesi 08:00 toplantısında isimli sahiplik"},
    {"tetik": "E2/E3 uyanma tarihi geldi ya da askı süresi doldu", "kime": "operasyon arama / altyapı masası 08:00 kuyruğu"},
    {"tetik": "S6_SAHADA 12 saati geçti (başladı ama bitmedi)", "kime": "teknik ekip lideri: kapat ya da neden yaz"},
]

# ---------------------------------------------------------------------------
# 3. Rol → ekran listesi
# ---------------------------------------------------------------------------
EKRANLAR = {
    "ORTAK": [
        "G0 Birim seçimi (Satış · Teknik · Operasyon)",
        "G1 Giriş (telefon + 4 haneli PIN, ilk girişte davet kodu) — mevcut",
        "G2 Bina kartı: bina adı (ör. site + blok), location_id, tellcordia_id, BN seri no, açık işler, altyapı bayrakları, ticket geçmişi",
        "G3 Harita: dokununca bina adı, ayrıntıda G2",
    ],
    "SATIS": [
        "Bugün (mevcut)", "Bina (mevcut)", "Harita (mevcut)", "Ben (mevcut)",
        "Sonuç çekmecesi (mevcut) — 'Altyapı sorunu' seçilince otomatik Talep açılır",
        "YENİ: Taleplerim (bildirdiğim altyapı sorunlarının durumu)",
    ],
    "TEKNIK": [
        "T1 İşlerim: günün sıralı rotası, SL sayacı, BTK kırmızı rozet, teyit durumu",
        "T2 İş kartı: bina adı + adres, zaman penceresi, iş tipi/ürün/hız, ara + yol tarifi",
        "T3 Temas sonucu: ulaştım (saat teyit) / ulaşamadım / ileri tarih ister / adres yanlış",
        "T4 Saha sonucu: tamamlandı / merkeze gönder (neden kodu) / malzeme yok",
        "T5 Harita: günün durakları",
        "T6 Ben: bugün biten, ilk seferde çözüm, zamanında %",
    ],
    "OPERASYON": [
        "O1 Canlı pano: gelen, triaj bekleyen, BTK risk, >24 s, askı uyanan",
        "O2 Triaj & atama panosu: atanmamış işler + önerilen teknisyen, ekip yükleri",
        "O3 BTK kuyruğu: SL geri sayımı, ön-teşhis araması",
        "O4 Arama kuyruğu: ulaşılamadı (3 deneme protokolü), masa işleri, randevu verme",
        "O5 Askı takibi: uyanma tarihi gelenler, süresi dolanlar",
        "O6 Altyapı & eskalasyon: bina bazında gruplu; OneDesk/ONENT ticket no; TT etiketleme",
        "O7 Talepler: WhatsApp / mail / satış / telefon girişleri",
        "O8 Lojistik: cihaz iade, depo, dolgu durağı önerisi",
        "O9 Kurtarma: birikmiş iş kovaları, toplu doğrulama listeleri, eritme grafiği",
        "O10 Veri yükle: BOSS + FOX dışa aktarımı yükle, fark raporu",
        "O11 Günlük rapor",
    ],
    "MEVCUT_SORUMLUSU": [
        "M1 Masam: mevcut müşteri işleri (BTK · Cihaz · Masa · Lojistik), üzerimdeki askılar",
        "M2 OneDesk taslakları: altyapı masasının hazırladığı ticket metni (bina bilgisi dolu), tek tıkla kopyala",
        "M3 Tekrar arıza listesi",
        "+ Operasyon ekranlarının hepsi",
    ],
    "YONETICI": [
        "Y1 KPI panosu (zamanında %, yaş kovaları, BTK, askı, boşa ziyaret, arama/iş)",
        "Y2 Birim görünümü (Satış · Teknik · Operasyon)",
        "Y3 Ekip/teknisyen performansı",
        "Y4 Kurtarma ilerlemesi",
        "Y5 Kullanıcılar ve roller (mevcut, genişletilir)",
        "Y6 Rapor indir",
    ],
}

ROLLER = {
    "satisci": {"birim": "Satış", "ekranlar": "SATIS", "musteri_telefonu": False},
    "teknisyen": {"birim": "Teknik", "ekranlar": "TEKNIK", "musteri_telefonu": "yalnız kendisine atanmış açık işte"},
    "teknik_lider": {"birim": "Teknik", "ekranlar": "TEKNIK + O2 (salt kendi ekibi) + Y3 (kendi ekibi)", "musteri_telefonu": "ekibinin açık işlerinde"},
    "operasyon": {"birim": "Operasyon", "ekranlar": "OPERASYON (masa yetkisine göre)", "musteri_telefonu": "kuyruğundaki işlerde"},
    "mevcut_sorumlusu": {"birim": "Operasyon", "ekranlar": "MEVCUT_SORUMLUSU", "musteri_telefonu": True},
    "yonetici": {"birim": "hepsi", "ekranlar": "YONETICI + hepsini görür", "musteri_telefonu": "raporlarda yok"},
}

OPERASYON_MASALARI = {
    "triaj_atama": 3, "btk": 2, "arama_randevu": 5, "altyapi_eskalasyon_talep": 2,
    "lojistik_depo": 2, "satis_destek": 2, "veri_rapor": 1, "vardiya_lideri": 1,
    "kurtarma_gecici(4 hafta)": 2,
}

# ---------------------------------------------------------------------------
# 4. Kurtarma senaryosu (VARSAYIMLAR açıkça yazılı; hafta 1'de ölçülüp düzeltilecek)
# ---------------------------------------------------------------------------
VARSAYIM = {
    "gunluk_giris": 300,            # kullanıcı tahmini 250-300; veri alt sınırı Pzt-Salı 310-350
    "saha_gerektiren_pay": 0.85,    # MASA + lojistiğin bir kısmı sahaya gitmez
    "teknisyen": 65,
    "musaitlik": 0.9,               # izin/rapor/araç
    "ziyaret_teknisyen_gun": 5.0,   # karışık iş (kurulum ~1,5-2 s, arıza ~1 s) + yol
    "bosa_ziyaret_bugun": 0.20,     # ulaşılamadı + altyapı yüzünden sonuçsuz
    "bosa_ziyaret_hedef": 0.07,
    "kurtarma_ek_teknisyen": 10,    # 4 hafta geçici ek ekip / başka bölgeden destek
    "pazar_mesaisi_teknisyen": 30,  # pazar yarım ekip, gün başı 5 ziyaret
    "dogrulamada_eriyen_pay": 0.20, # >7 gün saha işlerinin zaten yapılmış/iptal/mükerrer çıkan payı
    "masa_kisi": 4, "masa_is_kisi_gun": 45,
}


def senaryo(v: dict, veri: dict) -> dict:
    kova = veri["birikmis_is"]["kova"]
    saha_birikim = kova["K8_ekipte_bekliyor"]["adet"] + kova["K9_atanmamis_saha_isi"]["adet"]
    masa_birikim = sum(kova[k]["adet"] for k in kova if k not in ("K8_ekipte_bekliyor", "K9_atanmamis_saha_isi"))
    saha_giris = v["gunluk_giris"] * v["saha_gerektiren_pay"]
    kisi = v["teknisyen"] * v["musaitlik"]
    kap_bugun = kisi * v["ziyaret_teknisyen_gun"] * (1 - v["bosa_ziyaret_bugun"])
    kap_hedef = kisi * v["ziyaret_teknisyen_gun"] * (1 - v["bosa_ziyaret_hedef"])
    ek = v["kurtarma_ek_teknisyen"] * v["ziyaret_teknisyen_gun"] * (1 - v["bosa_ziyaret_hedef"])
    pazar_gunluk_ort = v["pazar_mesaisi_teknisyen"] * v["ziyaret_teknisyen_gun"] / 6
    fazla = kap_hedef - saha_giris
    eriyen = saha_birikim * v["dogrulamada_eriyen_pay"]
    net = saha_birikim - eriyen
    hiz = fazla + ek + pazar_gunluk_ort
    return {
        "saha_birikimi_24s_ustu": saha_birikim,
        "masa_birikimi_24s_ustu": masa_birikim,
        "gunluk_saha_girisi": round(saha_giris),
        "etkin_kapasite_bugun": round(kap_bugun),
        "etkin_kapasite_hedef": round(kap_hedef),
        "bugunku_acik_gun": round(saha_giris - kap_bugun),
        "yorum_bugun": "kapasite girişin altında → birikim her gün ~20 iş büyür (gözlenenle uyumlu: en eski açık iş 24.05, ~4 ayda ~2.100 geciken ≈ 17/gün)",
        "gunluk_fazla_bosa_ziyaret_dusunce": round(fazla),
        "ek_ekip_gunluk": round(ek),
        "pazar_mesaisi_gunluk_ort": round(pazar_gunluk_ort),
        "dogrulamada_erimesi_beklenen": round(eriyen),
        "saha_eritme_hizi_gun": round(hiz),
        "saha_eritme_is_gunu": round(net / hiz, 1) if hiz > 0 else None,
        "masa_eritme_is_gunu": round(masa_birikim / (v["masa_kisi"] * v["masa_is_kisi_gun"]), 1),
        "not": "Masa birikiminin altyapı kısmı (K1+K2) TT/Turkcell'e bağlı; bizim tarafımız toplu ticket'ı 1. haftada açmak.",
    }


def main() -> None:
    veri = json.loads(VERI.read_text(encoding="utf-8"))
    out = {
        "seritler": SERITLER,
        "durumlar": DURUMLAR,
        "zaman_butcesi_dk": {"standart_24s": BUTCE_24S, "btk_baglanti_12s": BUTCE_BTK_12S, "btk_tv_6s": BUTCE_BTK_6S,
                             "toplamlar": {"standart_24s": sum(BUTCE_24S.values()),
                                           "btk_baglanti_12s": sum(BUTCE_BTK_12S.values()),
                                           "btk_tv_6s": sum(BUTCE_BTK_6S.values())}},
        "eskalasyon": ESKALASYON,
        "ekranlar": EKRANLAR,
        "roller": ROLLER,
        "operasyon_masalari_kisi": OPERASYON_MASALARI,
        "operasyon_toplam_kisi": sum(OPERASYON_MASALARI.values()),
        "kurtarma_varsayim": VARSAYIM,
        "kurtarma_senaryo": senaryo(VARSAYIM, veri),
    }
    CIKTI.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["zaman_butcesi_dk"]["toplamlar"], ensure_ascii=False))
    print(json.dumps(out["kurtarma_senaryo"], ensure_ascii=False, indent=1))
    print("operasyon kişi:", out["operasyon_toplam_kisi"])


if __name__ == "__main__":
    main()
