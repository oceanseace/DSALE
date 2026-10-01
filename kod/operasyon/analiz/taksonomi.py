# -*- coding: utf-8 -*-
"""Kanonik iş emri (task) taksonomisi: FOX Task Adı <-> BOSS Task Adı eşlemesi ve sınıflar.

Eşleme, iki sistemin ortak anahtarı (FOX 'Akış No' = BOSS 'Task No') ile 2026-09-29
export'larında birebir doğrulandı (2.561 ortak kayıt). Kişisel veri içermez.

Alanlar
  kod           : kanonik tip kodu
  boss / fox    : o sistemde görülen task adları
  grup          : ariza | tv_sikayet | cihaz_degisim | cihaz_lojistik | evrak | faturalama |
                  ek_donanim | kurulum | sikayet_ofis | bilgi_talebi | altyapi
  sahip         : kullanıcı kuralına göre ('kurulum' geçen -> yeni_musteri_kurulum, "Kurulum Taskı
                  Ürememiş" hariç; diğer her şey -> mevcut_musteri)
  belirsiz      : kural ile gerçek iş sahipliğinin çelişebildiği tipler (açıklamalı)
  btk           : BTK'ya sayılan öncelikli (bağlantı / TV / arama / BTK şikayeti)
  saha          : 'evet' fiziki ziyaret gerekli, 'kismen' bir kısmı telefonla/uzaktan kapanıyor,
                  'hayir' ofis/lojistik/telefon işi (TAMAMLANDI kapanış nedenleriyle desteklendi)
"""
import re
import unicodedata

KANONIK = [
    # --- Mevcut müşteri: arıza (BTK) ---
    dict(kod="BAGLANTI", ad="Bağlantı Problemi", boss=["Bağlantı Problemi"], fox=["Bağlantı Problemleri"],
         grup="ariza", btk=True, saha="kismen"),
    dict(kod="TV_ARIZA", ad="TV+ Arıza", boss=["TV+ Arıza"], fox=["IP TV Arıza"],
         grup="ariza", btk=True, saha="kismen"),
    dict(kod="KANAL_SIKAYETI", ad="Kanal Şikayeti", boss=["Kanal Şikayeti"], fox=["Kanal Şikayeti"],
         grup="tv_sikayet", btk=True, saha="hayir"),
    dict(kod="ARAMA", ad="Arama Problemi", boss=["Arama Problemi"], fox=["Arama Problemi"],
         grup="ariza", btk=True, saha="kismen"),
    dict(kod="DOPING_ARIZA", ad="Doping Arıza Bildirimi", boss=["Doping Arıza Bildirimi"], fox=["Arıza Bildirim"],
         grup="ariza", btk=True, saha="kismen"),
    # --- Mevcut müşteri: cihaz değişimi ---
    dict(kod="MODEM_DEGISIKLIGI", ad="Modem Değişikliği", boss=["Modem Değişikliği"], fox=["Modem Değişikliği"],
         grup="cihaz_degisim", btk=False, saha="evet",
         belirsiz="Adında 'kurulum' yok -> mevcut müşteri; ama iş fiilen cihaz değişimi/kurulumu (teknisyen veya kargo)."),
    dict(kod="SUPERBOX_MODEM", ad="Superbox Modem Değişikliği", boss=["Superbox Modem Değişikliği"],
         fox=["Superbox Modem Değişikliği"], grup="cihaz_degisim", btk=False, saha="evet"),
    dict(kod="STB_DEGISIKLIGI", ad="STB Cihaz Değişikliği", boss=["STB Cihaz Değişikliği"], fox=["STB Cihaz Değişikliği"],
         grup="cihaz_degisim", btk=False, saha="evet"),
    # --- Mevcut müşteri: cihaz lojistiği ---
    dict(kod="CIHAZ_IADE", ad="Cihaz İade Bekleniyor", boss=["Cihaz İade Bekleniyor"], fox=["Cihaz İade Bekleniyor"],
         grup="cihaz_lojistik", btk=False, saha="kismen",
         belirsiz="Kapanan 219 kaydın medyan süresi 15 dk (sistemsel/ofis kaydı gibi); açık kalanlar ise müşterinin "
                  "cihazı teslim etmesini bekliyor (medyan 9 gün). Teknisyen toplaması gerekebilir."),
    dict(kod="CIHAZ_GERI_ALIM", ad="Cihaz Geri Alım", boss=["Cihaz Geri Alım"], fox=["Cihaz Geri Alım"],
         grup="cihaz_lojistik", btk=False, saha="evet"),
    dict(kod="TURKSAT_CIHAZ_IADE", ad="Turksat Cihaz İade", boss=["Turksat Cihaz İade - Yerinde Hizmet"],
         fox=["Turksat Cihaz İade Bekleniyor"], grup="cihaz_lojistik", btk=False, saha="evet"),
    dict(kod="UCRETSIZ_KUMANDA", ad="Ücretsiz Kumanda Teslimatı", boss=["Ücretsiz Kumanda Teslimatı"], fox=[],
         grup="cihaz_lojistik", btk=False, saha="kismen"),
    # --- Mevcut müşteri: evrak / faturalama / bilgi ---
    dict(kod="EVRAK_SOSYAL", ad="Sosyal Destek Evrak Toplama", boss=["Sosyal Destek Evrak Toplama"],
         fox=["Sosyal Destek Evrak Toplama"], grup="evrak", btk=False, saha="evet"),
    dict(kod="EVRAK_TURKSAT", ad="Turksat Evrak Toplama", boss=["Turksat Evrak Toplama"], fox=["Turksat Evrak Toplama"],
         grup="evrak", btk=False, saha="kismen"),
    dict(kod="UCRETLENDIRME", ad="Teknik Servis Ücretlendirme", boss=["Teknik Servis Ücretlendirme"],
         fox=["Ücretlendirilecek Servisler"], grup="faturalama", btk=False, saha="evet"),
    dict(kod="SORU_CEVAP", ad="Soru Cevap / Yazılı Bilgi", boss=["Soru Cevap", "Yazılı Bilgi Talebi"], fox=[],
         grup="bilgi_talebi", btk=False, saha="hayir"),
    # --- Ek donanım (belirsiz sahiplik) ---
    dict(kod="IKINCI_DONANIM", ad="2. Donanım", boss=["2.Donanım"], fox=["İkinci Donanım Kurulum"],
         grup="ek_donanim", btk=False, saha="evet",
         belirsiz="FOX adı 'İkinci Donanım Kurulum' (kurulum geçiyor -> yeni müşteri ekibi), BOSS adı '2.Donanım' "
                  "(geçmiyor -> mevcut). Müşteri mevcut abone; ürün kamera/tablet/mesh gibi ek cihaz."),
    dict(kod="YAN_ODA", ad="Yan Oda Kurulum", boss=["Yan Oda Kurulum"], fox=["TV Yan Oda Kurulum"],
         grup="kurulum", btk=False, saha="evet",
         belirsiz="Adında 'kurulum' var -> kurulum ekibi; ama müşteri mevcut TV+ abonesi (ek STB)."),
    # --- Yeni müşteri kurulumları ---
    dict(kod="FIBER_KURULUM", ad="Fiber Kurulum", boss=["Fiber Kurulum"], fox=["Quiknet Kurulum Talebi"],
         grup="kurulum", btk=False, saha="evet"),
    dict(kod="FIBER_DONUSUM", ad="Fiber Kurulum (Dönüşüm)", boss=["Fiber Kurulum(Dönüşüm)"], fox=["Quiknet Kurulum Talebi"],
         grup="kurulum", btk=False, saha="evet",
         belirsiz="Dönüşüm = mevcut (xDSL) abonenin fibere geçişi; kurala göre kurulum ekibi."),
    dict(kod="FIBER_NAKIL", ad="Fiber Kurulum (Nakil)", boss=["Fiber Kurulum(Nakil)"], fox=["Quiknet Kurulum Talebi"],
         grup="kurulum", btk=False, saha="evet",
         belirsiz="Nakil = mevcut abonenin adres taşıması; kurala göre kurulum ekibi."),
    dict(kod="FIBER_GECIS", ad="Fiber Kurulum (Geçiş)", boss=["Fiber Kurulum(Geçiş)"], fox=["Quiknet Kurulum Talebi"],
         grup="kurulum", btk=False, saha="evet"),
    dict(kod="TT_FIBER_KURULUM", ad="TT Fiber Kurulum", boss=["TT Fiber Kurulum", "TT Fiber Kurulum(Geçiş)", "TT Fiber Kurulum(Nakil)"],
         fox=["TT Fiber Kurulum Talebi"], grup="kurulum", btk=False, saha="evet"),
    dict(kod="SUPERBOX_KURULUM", ad="Superbox Kurulum", boss=["Superbox Kurulum"], fox=["SuperBox Kurulum"],
         grup="kurulum", btk=False, saha="evet"),
    dict(kod="TV_KURULUM", ad="TV+ Kurulum", boss=["TV+ Kurulum", "TV+ Kurulum(Nakil)", "TV+ Kurulum(Geçiş)"],
         fox=["IP TV Kurulum"], grup="kurulum", btk=False, saha="evet",
         belirsiz="Çoğunlukla mevcut internet abonesine TV eklenmesi; kurala göre kurulum ekibi."),
    dict(kod="KURULUM_CIHAZ_GONDERIM", ad="Kurulum ve Cihaz Gönderim",
         boss=["Kurulum ve Cihaz Gönderim", "Kurulum ve Cihaz Gönderim(Nakil)", "Kurulum ve Cihaz Gönderim(Geçiş)"],
         fox=["Kurulum ve cihaz gönderim"], grup="kurulum", btk=False, saha="kismen",
         belirsiz="Adında 'kurulum' var -> kurulum ekibi; ama cihaz gönderimli (xDSL) iş, çoğu TT etiketlemesi "
                  "beklediği için askıda (TT kaynaklı)."),
    # --- FOX'ta kalan (BOSS'a düşmeyen) ofis işleri ---
    dict(kod="KURULUM_URETILMEMIS", ad="Kurulum Taskı Ürememiş", boss=[], fox=["Kurulum Taskı Ürememiş"],
         grup="sikayet_ofis", btk=False, saha="hayir",
         belirsiz="Adında 'kurulum' geçse de kullanıcı kuralı gereği MEVCUT müşteri (operasyon) işi."),
    dict(kod="BTK_SIKAYET", ad="BTK Şikayet", boss=[], fox=["BTK Şikayet", "BTK / Mahkeme Şikayet"],
         grup="sikayet_ofis", btk=True, saha="hayir"),
    dict(kod="DONANIM_TESLIMAT_SIKAYET", ad="Donanım Teslimat Şikayet", boss=[], fox=["Donanım Teslimat Şikayet"],
         grup="sikayet_ofis", btk=False, saha="hayir"),
    dict(kod="FATURA_KAMPANYA", ad="Fatura / Kampanya Problemi", boss=[],
         fox=["Fatura İtiraz Bildirimi", "Kampanya Tanımlama Problemleri"], grup="faturalama", btk=False, saha="hayir"),
    dict(kod="DIGER_OFIS", ad="Diğer ofis (Bayi Kanal İnceleme, BDH, Nakil/Numara)", boss=[],
         fox=["Bayi Kanal İnceleme", "BDH Problem Çözüm", "Nakil/Numara Değişikliği"], grup="sikayet_ofis",
         btk=False, saha="hayir"),
    dict(kod="ALTYAPI_TALEP", ad="Altyapı talebi (Fiber gelsin, xDSL boş port yok)", boss=[],
         fox=["Fiber gelsin", "XDSL Boş Port Yok"], grup="altyapi", btk=False, saha="hayir"),
]


def norm(s):
    """Türkçe karakter/büyük-küçük harf/boşluk farklarını yok sayan anahtar."""
    if s is None:
        return ""
    s = str(s).strip().upper()
    tr = str.maketrans("ÇĞİIÖŞÜÂÎÛ", "CGIIOSUAIU")
    s = s.translate(tr)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def sahip_kurali(ad):
    """Kullanıcı kuralı: adında 'kurulum' geçen -> yeni_musteri_kurulum (Ürememiş hariç)."""
    n = norm(ad)
    if "KURULUM" in n and "UREMEMIS" not in n:
        return "yeni_musteri_kurulum"
    return "mevcut_musteri"


_BOSS = {}
_FOX = {}
for _k in KANONIK:
    for _n in _k["boss"]:
        _BOSS[norm(_n)] = _k["kod"]
    for _n in _k["fox"]:
        _FOX.setdefault(norm(_n), _k["kod"])
    # kanonik sahiplik: BOSS adı esas (BOSS'ta yoksa FOX adı)
    _ref = (_k["boss"] or _k["fox"])[0]
    _k["sahip"] = sahip_kurali(_ref)
    _k["sahip_fox_adina_gore"] = sahip_kurali(_k["fox"][0]) if _k["fox"] else None
KOD = {k["kod"]: k for k in KANONIK}

# FOX 'Quiknet Kurulum Talebi' tek başına alt tipi söylemez -> FIBER_KURULUM'a düşer (BOSS eşleşmesi varsa o esas)
_FOX[norm("Quiknet Kurulum Talebi")] = "FIBER_KURULUM"


def boss_kod(ad):
    return _BOSS.get(norm(ad), "BILINMEYEN")


def fox_kod(ad):
    return _FOX.get(norm(ad), "BILINMEYEN")
