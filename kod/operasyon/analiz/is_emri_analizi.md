# İş Emri Analizi — BOSS + FOX açık kayıtlar (29 Eylül 2026)

*Referans an: 2026-09-29 16:45:00 · Üreten: `operasyon/analiz/is_emri_analizi.py` → `cikti/is_emri_analizi.json` → bu rapor (`rapor_md.py`). Tüm sayılar toplu; müşteri adı/no/adres/telefon, task no ve tekil lokasyon kimliği yoktur.*

## 0. Yönetici özeti — 12 bulgu

1. **Açık iş: 2.567** (BOSS) — **953 mevcut müşteri** (sizin sorumluluğunuz, 2.Donanım 125 dahil; bunlardan 493 adedi BTK'ya sayılan bağlantı/TV/kanal/arama) + **1.614 yeni müşteri kurulum**. BOSS kayıtlarının %99,8'i FOX'ta da var (2.561 ortak; 56 yalnız FOX'ta, 6 yalnız BOSS'ta).
2. **Gerçek 24 saat uyumu (mevcut müşteri, 1–14 Eylül kohortu): %43.** 12 saatte %28, 48 saatte %59. Gün gün **%65'ten (1 Eylül) %21–24'e (12–14 Eylül) düştü** — birikim büyüdükçe yeni gelen iş eski işin arkasında bekliyor.
3. **Giriş hızı (mevcut müşteri, sansürsüz): takvim günü ortalama 323/gün** (hafta içi 338, Cumartesi 384, Pazar 182). Sizin '250–300' tahmininiz doğru mertebede. Kapanış ise hafta içi ~224/gün → **günde ~80–110 iş açık veriliyor**, birikim bu yüzden büyüyor.
4. **Bağlantı Problemi tek başına mevcut girişin yaklaşık %44 kadarı** (~142/gün); ardından Kanal Şikayeti (~49), Cihaz İade (~35), Modem Değişikliği (~32), TV+ Arıza (~29).
5. **BTK arızalarında ziyaretsiz kapanabilecek pay %44**: %30 'müşteri sorunun düzeldiğini söyledi / çağrı merkezi çözebilirdi', ~%12 şebeke/genel arıza, ~%3 ofis kapanışı. Teknisyenin gidip 'düzelmiş' bulduğu işler de dahil olduğu için bu bir ÜST SINIR; 'önce ara/uzaktan kontrol et, sonra gönder' filtresinin gerçekçi eleme payı tahminen %25–35.
6. **Kanal Şikayeti hiç sahaya gitmiyor**: kapananlarda ofis kapanışı %98, 'müşteri düzeldi dedi' nedeni %98; ama medyan 169 saat (≈7 gün) 'abone kaynaklı askı'da bekletiliyor → 24 saat uyumu %3. Aynı gün telefonla kapatılabilir.
7. **Tekrarlayan arıza yüksek**: 1–15 Eylül'deki 2.256 BTK arıza task'ı içinde tekrar payı %35: aynı müşteride 15 gün içinde 2., 3. kez açılmış (398 müşteri).
8. **Atama yok denecek kadar az**: 2.567 açık işin 1.905 adedinde Ekip boş. BOSS'ta 'Randevulu' = ekibe 2 saatlik dilimle atanmış demek (randevulu işlerin %98'inde ekip dolu, randevusuzların hiçbirinde yok); 586 iş sevk dilimi geçmiş ama kapanmamış.
9. **Mevcut müşteri birikiminin bugün aksiyon alınabilir kısmı**: 415 iş sahaya verilebilir, 397 iş ofisten/telefonla kapatılabilir, 138 iş operasyonun tekrar araması/çözmesi gereken (askı + merkeze gönderilen).
10. **Ulaşılamama asıl darboğaz**: son açıklaması 'arandı, ulaşılamadı' olan 648 iş (mevcut 558), 'Aboneye ulaşılamadı' ile merkeze dönen 306, abone kaynaklı askı 349. Açık Bağlantı Problemi işlerinde son notu 'ulaşılamadı' olan pay %91 → işlerin çoğu sahaya çıkmadan bir 'ulaşılamadı' kaydıyla bekliyor.
11. **Saha kapasitesi**: 12 kişilik arıza ekibinden günde ~10 kişi aktif, kişi başı medyan **17 iş/gün** (p25–p75: 14–20); ardışık iki kapanış arası medyan 31 dk (yol+iş vekili). Pazar günleri ekip 4–8 kişiye düşüyor; Pazar gelenlerin 24s uyumu %21–25.
12. **Coğrafi kümelenme güçlü**: konumlu açık mevcut-müşteri işlerinde 500 m içinde başka açık iş bulunan pay %96 (medyan 5 komşu; 2 km'de 27). Tek günün girişinde bile en yakın komşu medyanı ~150–270 m. Lokasyon eşleşmesi: dolu Lokasyon içinde bina_master'a bağlanan %98,7; ama Lokasyon'u dolu iş oranı yalnız %58 (Superbox/Kanal Şikayeti/TT Fiber'de hiç yok).

## 1. Veri kaynakları ve kapsam

| Kaynak | Satır | Ne? |
|---|---|---|
| BOSS `TeknikTaskDetayRaporu.xlsx` | 2.567 | Bayiye düşmüş AÇIK teknik task'lar (51 sütun) |
| FOX `ReportResultAçık.xls` | 2.094 | FOX'ta açık akışlar (kuyrukta/atandı) |
| FOX `ReportResultAskı.xls` | 523 | FOX'ta ASKIDA akışlar |
| PS26 `data.xlsx` | 6 sayfa | ORIGN (tur raporu), LOCS, TICKET, GUZERGAH, ALTYAPI, PVT |
| `TAMAMLANDI.xlsx` (masaüstü, ek) | 3.667 | 1–15 Eylül açılıp 16 Eylül'e kadar KAPANAN mevcut-müşteri task'ları |
| `ANLATILAN.xlsx` (masaüstü, ek) | 15 gün | Günlük GELEN / YAPILAN / ekip sayısı / arızacı-kurulumcu-ofis kırılımı |
| `data/master/bina_master.csv` | 19.706 | OneMap koordinatlı bina envanteri (location_id anahtarı) |

> **Not:** `TAMAMLANDI.xlsx` ve `ANLATILAN.xlsx` bu istekte eklenmedi, masaüstünde bulundu. Açık-iş export'ları kapanmış işleri göstermediği için giriş hızı, telefonla çözülebilirlik, teknisyen verimi ve gerçek 24s uyumu yalnızca bu iki dosyadan sansürsüz hesaplanabildi. Kullanılmaması istenirse ilgili bölümler 'alt sınır' tahminlerine düşer.

> **Kritik boşluk:** BOSS açık export'unda `Telefonla Çözülebilir Miydi?`, `Temel Arıza Nedeni`, `Arıza Nedeni` 2.567 satırın **hiçbirinde dolu değil** (kapanışta doldurulan alanlar); `Teknik Ekip Bitirme Tarihi` yalnızca 2 satırda dolu.

## 2. Kanonik task taksonomisi (FOX ↔ BOSS)

Eşleme ortak anahtarla (FOX `Akış No` = BOSS `Task No`) birebir doğrulandı. İsmi farklı olan eşleşmeler:

| FOX Task Adı | BOSS Task Adı | Kayıt |
|---|---|---|
| IP TV Kurulum | TV+ Kurulum | 417 |
| Quiknet Kurulum Talebi | Fiber Kurulum | 307 |
| Bağlantı Problemleri | Bağlantı Problemi | 233 |
| Quiknet Kurulum Talebi | Fiber Kurulum(Dönüşüm) | 129 |
| İkinci Donanım Kurulum | 2.Donanım | 124 |
| Quiknet Kurulum Talebi | Fiber Kurulum(Nakil) | 62 |
| TT Fiber Kurulum Talebi | TT Fiber Kurulum | 60 |
| IP TV Arıza | TV+ Arıza | 58 |
| TT Fiber Kurulum Talebi | TT Fiber Kurulum(Geçiş) | 43 |
| IP TV Kurulum | TV+ Kurulum(Nakil) | 37 |
| Kurulum ve cihaz gönderim | Kurulum ve Cihaz Gönderim(Nakil) | 35 |
| TV Yan Oda Kurulum | Yan Oda Kurulum | 29 |
| Ücretlendirilecek Servisler | Teknik Servis Ücretlendirme | 23 |
| Arıza Bildirim | Doping Arıza Bildirimi | 19 |
| Kurulum ve cihaz gönderim | Kurulum ve Cihaz Gönderim(Geçiş) | 14 |
| Quiknet Kurulum Talebi | Fiber Kurulum(Geçiş) | 13 |
| IP TV Kurulum | TV+ Kurulum(Geçiş) | 9 |
| TT Fiber Kurulum Talebi | TT Fiber Kurulum(Nakil) | 2 |
| Turksat Cihaz İade Bekleniyor | Turksat Cihaz İade - Yerinde Hizmet | 2 |

**Kanonik tipler** — sahip = kullanıcı kuralı ('kurulum' geçen → yeni müşteri ekibi, 'Kurulum Taskı Ürememiş' hariç). *Saha* = fiziki ziyaret ihtiyacı (evet / kısmen / hayır). *Ziyaretsiz %* = 3–15 Eylül kapanışlarında ofisten kapanan veya nedeni 'müşteri düzeldi dedi / çağrı merkezi / şebeke-genel arıza' olan oran.

| Kod | BOSS adı | FOX adı | Sahip | BTK | Saha | Açık BOSS | FOX açık/askı | Tamamlanan 1–15 Eyl | Ziyaretsiz % |
|---|---|---|---|---|---|---|---|---|---|
| `BAGLANTI` | Bağlantı Problemi | Bağlantı Problemleri | Mevcut | ✔ | kismen | 234 | 165/71 | 1.792 | %42 |
| `TV_ARIZA` | TV+ Arıza | IP TV Arıza | Mevcut | ✔ | kismen | 58 | 40/18 | 354 | %49 |
| `KANAL_SIKAYETI` | Kanal Şikayeti | Kanal Şikayeti | Mevcut | ✔ | hayir | 179 | 2/177 | 479 | %99 |
| `ARAMA` | Arama Problemi | Arama Problemi | Mevcut | ✔ | kismen | 3 | 3/0 | 8 | %38 |
| `DOPING_ARIZA` | Doping Arıza Bildirimi | Arıza Bildirim | Mevcut | ✔ | kismen | 19 | 19/0 | 102 | %49 |
| `MODEM_DEGISIKLIGI` | Modem Değişikliği | Modem Değişikliği | Mevcut |  | evet | 58 | 55/2 | 395 | %1 |
| `SUPERBOX_MODEM` | Superbox Modem Değişikliği | Superbox Modem Değişikliği | Mevcut |  | evet | 5 | 4/3 | 28 | %0 |
| `STB_DEGISIKLIGI` | STB Cihaz Değişikliği | STB Cihaz Değişikliği | Mevcut |  | evet | 5 | 4/1 | 23 | %0 |
| `CIHAZ_IADE` | Cihaz İade Bekleniyor | Cihaz İade Bekleniyor | Mevcut |  | kismen | 218 | 215/3 | 219 | %1 |
| `CIHAZ_GERI_ALIM` | Cihaz Geri Alım | Cihaz Geri Alım | Mevcut |  | evet | 5 | 5/0 | 21 | %71 |
| `TURKSAT_CIHAZ_IADE` | Turksat Cihaz İade - Yerinde Hizmet | Turksat Cihaz İade Bekleniyor | Mevcut |  | evet | 2 | 1/1 | 2 | %0 |
| `UCRETSIZ_KUMANDA` | Ücretsiz Kumanda Teslimatı | — | Mevcut |  | kismen | 0 | 0/0 | 1 | %0 |
| `EVRAK_SOSYAL` | Sosyal Destek Evrak Toplama | Sosyal Destek Evrak Toplama | Mevcut |  | evet | 14 | 13/1 | 53 | %0 |
| `EVRAK_TURKSAT` | Turksat Evrak Toplama | Turksat Evrak Toplama | Mevcut |  | kismen | 4 | 2/2 | 6 | %0 |
| `UCRETLENDIRME` | Teknik Servis Ücretlendirme | Ücretlendirilecek Servisler | Mevcut |  | evet | 24 | 16/9 | 131 | %1 |
| `SORU_CEVAP` | Soru Cevap / Yazılı Bilgi Talebi | — | Mevcut |  | hayir | 0 | 0/0 | 29 | %42 |
| `IKINCI_DONANIM` | 2.Donanım | İkinci Donanım Kurulum | Mevcut |  | evet | 125 | 125/0 | 0 | – |
| `YAN_ODA` | Yan Oda Kurulum | TV Yan Oda Kurulum | Kurulum |  | evet | 29 | 29/0 | 0 | – |
| `FIBER_KURULUM` | Fiber Kurulum | Quiknet Kurulum Talebi | Kurulum |  | evet | 308 | 307/0 | 0 | – |
| `FIBER_DONUSUM` | Fiber Kurulum(Dönüşüm) | Quiknet Kurulum Talebi | Kurulum |  | evet | 129 | 129/0 | 0 | – |
| `FIBER_NAKIL` | Fiber Kurulum(Nakil) | Quiknet Kurulum Talebi | Kurulum |  | evet | 62 | 45/17 | 0 | – |
| `FIBER_GECIS` | Fiber Kurulum(Geçiş) | Quiknet Kurulum Talebi | Kurulum |  | evet | 13 | 13/0 | 0 | – |
| `TT_FIBER_KURULUM` | TT Fiber Kurulum / TT Fiber Kurulum(Geçiş) / TT Fiber Kurulum(Nakil) | TT Fiber Kurulum Talebi | Kurulum |  | evet | 106 | 105/0 | 0 | – |
| `SUPERBOX_KURULUM` | Superbox Kurulum | SuperBox Kurulum | Kurulum |  | evet | 325 | 325/0 | 0 | – |
| `TV_KURULUM` | TV+ Kurulum / TV+ Kurulum(Nakil) / TV+ Kurulum(Geçiş) | IP TV Kurulum | Kurulum |  | evet | 463 | 451/12 | 24 | %0 |
| `KURULUM_CIHAZ_GONDERIM` | Kurulum ve Cihaz Gönderim / Kurulum ve Cihaz Gönderim(Nakil) / Kurulum ve Cihaz Gönderim(Geçiş) | Kurulum ve cihaz gönderim | Kurulum |  | kismen | 179 | 8/172 | 0 | – |
| `KURULUM_URETILMEMIS` | — | Kurulum Taskı Ürememiş | Mevcut |  | hayir | 0 | 1/3 | 0 | – |
| `BTK_SIKAYET` | — | BTK Şikayet / BTK / Mahkeme Şikayet | Mevcut | ✔ | hayir | 0 | 2/4 | 0 | – |
| `DONANIM_TESLIMAT_SIKAYET` | — | Donanım Teslimat Şikayet | Mevcut |  | hayir | 0 | 2/23 | 0 | – |
| `FATURA_KAMPANYA` | — | Fatura İtiraz Bildirimi / Kampanya Tanımlama Problemleri | Mevcut |  | hayir | 0 | 0/3 | 0 | – |
| `DIGER_OFIS` | — | Bayi Kanal İnceleme / BDH Problem Çözüm / Nakil/Numara Değişikliği | Mevcut |  | hayir | 0 | 5/1 | 0 | – |
| `ALTYAPI_TALEP` | — | Fiber gelsin / XDSL Boş Port Yok | Mevcut |  | hayir | 0 | 3/0 | 0 | – |

**Belirsiz (kural ile gerçek işin çeliştiği) tipler:**

- `MODEM_DEGISIKLIGI` (58 açık): Adında 'kurulum' yok -> mevcut müşteri; ama iş fiilen cihaz değişimi/kurulumu (teknisyen veya kargo).
- `CIHAZ_IADE` (218 açık): Kapanan 219 kaydın medyan süresi 15 dk (sistemsel/ofis kaydı gibi); açık kalanlar ise müşterinin cihazı teslim etmesini bekliyor (medyan 9 gün). Teknisyen toplaması gerekebilir.
- `IKINCI_DONANIM` (125 açık): FOX adı 'İkinci Donanım Kurulum' (kurulum geçiyor -> yeni müşteri ekibi), BOSS adı '2.Donanım' (geçmiyor -> mevcut). Müşteri mevcut abone; ürün kamera/tablet/mesh gibi ek cihaz. **(FOX adına göre sahip değişiyor!)**
- `YAN_ODA` (29 açık): Adında 'kurulum' var -> kurulum ekibi; ama müşteri mevcut TV+ abonesi (ek STB).
- `FIBER_DONUSUM` (129 açık): Dönüşüm = mevcut (xDSL) abonenin fibere geçişi; kurala göre kurulum ekibi.
- `FIBER_NAKIL` (62 açık): Nakil = mevcut abonenin adres taşıması; kurala göre kurulum ekibi.
- `TV_KURULUM` (463 açık): Çoğunlukla mevcut internet abonesine TV eklenmesi; kurala göre kurulum ekibi.
- `KURULUM_CIHAZ_GONDERIM` (179 açık): Adında 'kurulum' var -> kurulum ekibi; ama cihaz gönderimli (xDSL) iş, çoğu TT etiketlemesi beklediği için askıda (TT kaynaklı).
- `KURULUM_URETILMEMIS` (0 açık): Adında 'kurulum' geçse de kullanıcı kuralı gereği MEVCUT müşteri (operasyon) işi.

**Yalnız FOX'ta olan 56 kayıt** (askıda: 34) BOSS'a hiç düşmüyor → operasyon bunları FOX'tan izlemek zorunda: Donanım Teslimat Şikayet (25), BTK Şikayet (5), Kurulum Taskı Ürememiş (4), Bayi Kanal İnceleme (4), Bağlantı Problemleri (3), Superbox Modem Değişikliği (2), Ücretlendirilecek Servisler (2), Kampanya Tanımlama Problemleri (2), Fiber gelsin (2), Kurulum ve cihaz gönderim (1), BDH Problem Çözüm (1), Fatura İtiraz Bildirimi (1), BTK / Mahkeme Şikayet (1), XDSL Boş Port Yok (1), Nakil/Numara Değişikliği (1), İkinci Donanım Kurulum (1).

**Kapanış nedenine göre saha ihtiyacı (TAMAMLANDI, 3–15 Eylül; 1–2 Eylül'de 'Teknisyen' alanı hiç dolmadığı için hariç):**

| Tip | Kapanan | Ofisten kapanan | Telefon/uzaktan nedeni | Şebeke/genel arıza | Saha müdahalesi (kablo/cihaz) | Neden boş | Ziyaretsiz toplam |
|---|---|---|---|---|---|---|---|
| `BAGLANTI` | 1.484 | %8 | %29 | %11 | %60 | %0 | %42 |
| `TV_ARIZA` | 287 | %3 | %34 | %14 | %52 | %0 | %49 |
| `DOPING_ARIZA` | 86 | %8 | %34 | %15 | %51 | %0 | %49 |
| `ARAMA` | 8 | %0 | %25 | %12 | %62 | %0 | %38 |
| `KANAL_SIKAYETI` | 476 | %98 | %98 | %0 | %1 | %0 | %99 |
| `MODEM_DEGISIKLIGI` | 310 | %1 | %0 | %0 | %0 | %100 | %1 |
| `CIHAZ_IADE` | 189 | %1 | %0 | %0 | %0 | %100 | %1 |
| `UCRETLENDIRME` | 75 | %1 | %0 | %0 | %0 | %100 | %1 |
| `EVRAK_SOSYAL` | 42 | %0 | %0 | %0 | %0 | %100 | %0 |
| `CIHAZ_GERI_ALIM` | 21 | %71 | %0 | %0 | %0 | %100 | %71 |

Telefon/uzaktan = 'Müşteri sorununun düzeldiğini söyledi' + 'Çağrı merkezi tarafından çözülebilirdi' + 'Müşteriyle görüşüldü'. Şebeke = 'Lokasyonda genel arıza' + 'BÇO/NW müdahale sonrası düzeldi' + 'TT kaynaklı'. Saha = 'Kablo/konnektör/uç değişimi' + 'Cihaz değişimi'. Bağlantı'da teknisyen kapanışlarının da %26'sı 'müşteri düzeldi dedi' → teknisyen gitmeden bir telefonla elenebilecek iş payı.

**Tekrarlayan arıza:** 1.470 müşteride 2.256 BTK arıza task'ı; 398 müşteride birden fazla → 786 tekrar task (%35). Şu an 303 müşterinin aynı anda birden fazla açık task'ı var (tek ziyarette birleştirilebilir).

## 3. SLA modeli

### 3.1 Alanlar gerçekte neyi ölçüyor

- **BOSS SL** — 'SL Geçti' / 'SL Geçmedi'; boş = o task tipi için BOSS'ta SL tanımı yok.
- **BOSS SL Suresi Sa** — SL hedefinin KAÇ SAAT AŞILDIĞI (tam saat, aşağı yuvarlanmış). 'SL Geçmedi' ise 0. Doğrulama: (şimdi - Task Başlangıç) - SL Süresi, her tip için sabit bir hedefe oturuyor (±1 saat), saat takvim saati (gece/hafta sonu düşülmüyor).
- **FOX Hedef SL** — Turkcell'in akış (ticket) bazlı SL hedefi, saat. 0 = FOX'ta SL yok (kurulum tipleri).
- **FOX Kalan Sure** — Hedef SL - geçen süre (saat); negatif = gecikmiş. Geçen süre çoğunlukla Başlangıç'tan sayılıyor ama bazı kayıtlarda saat duruyor/sınırlanıyor (ör. Cihaz İade'de -72'de, Bağlantı'da -36'da donmuş kayıtlar). Yaşlandırma için güvenilmez; yaş Başlangıç'tan hesaplanmalı.
- **Teknik Ekip SL Suresi Dk** — Teknisyenin 'konum paylaş' (yola çıktım) anından 'işe başla' anına kadar geçen dakika; işe başlanmadıysa konum paylaşımından export anına kadar geçen dakika. Konum paylaşılmayan kayıtlarda 0. Yani varış/yol süresi göstergesi, task SL'i değil.
- **Teknik Ekip Konum Paylaşma / İşe Başlama** — ikisi de dolu 120 kaydın %81 kadarında aynı dakika içinde basılmış → yol süresi ölçülemiyor.

### 3.2 Hedef süreler (saat) — BOSS (bayi SL'i) vs FOX (Turkcell akış SL'i)

| BOSS tipi | BOSS hedef | FOX tipi | FOX Hedef SL |
|---|---|---|---|
| Bağlantı Problemi | 24 | Bağlantı Problemleri | 12 |
| TV+ Arıza | 16 | IP TV Arıza | 6 |
| Arama Problemi | 24 | Arama Problemi | 12 |
| Kanal Şikayeti | SL yok | Kanal Şikayeti | 24 |
| Doping Arıza Bildirimi | SL yok | Arıza Bildirim | 24 |
| Cihaz İade Bekleniyor | SL yok | Cihaz İade Bekleniyor | 24 |
| Cihaz Geri Alım | SL yok | Cihaz Geri Alım | 48 |
| Modem Değişikliği | SL yok | Modem Değişikliği | 0 (yok) |
| STB Cihaz Değişikliği | 48 | STB Cihaz Değişikliği | 0 (yok) |
| Teknik Servis Ücretlendirme | 56 | Ücretlendirilecek Servisler | 0 (yok) |
| 2.Donanım | 96 | İkinci Donanım Kurulum | 0 (yok) |
| Fiber Kurulum | 36 | Quiknet Kurulum Talebi | 0 (yok) |
| TV+ Kurulum | 36 | IP TV Kurulum | 0 (yok) |
| Yan Oda Kurulum | 36 | TV Yan Oda Kurulum | 0 (yok) |
| Superbox Kurulum | 48 | SuperBox Kurulum | 0 (yok) |
| Kurulum ve Cihaz Gönderim | 48 | Kurulum ve cihaz gönderim | 0 (yok) |
| TT Fiber Kurulum | SL yok | TT Fiber Kurulum Talebi | 0 (yok) |
| — | SL yok | BTK Şikayet | 168 |
| — | SL yok | BTK / Mahkeme Şikayet | 4 |

Bağlantı için Turkcell (FOX) hedefi **12 saat**, bayi (BOSS) hedefi **24 saat**; TV+ Arıza'da 6 / 16 saat. Kanal Şikayeti, Cihaz İade, Modem Değişikliği, Doping, Evrak ve TT Fiber için BOSS'ta SL tanımı yok (SL sütunu boş) — bu işler BOSS SL raporunda görünmeden yaşlanıyor.

### 3.3 Açık işlerde ihlal ve yaş (kanonik tip)

| Tip | M/K | Açık | BOSS hedef | FOX hedef | BOSS SL Geçti | >24s (kullanıcı kuralı) | Medyan yaş (s) | <24s | 24–48s | 48–72s | 3–7g | 7–30g | >30g |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `BAGLANTI` | M | 234 | 24 | 12 | 126 | 128 (%55) | 29 | 106 | 36 | 33 | 30 | 29 | 0 |
| `CIHAZ_IADE` | M | 218 | – | 24 | 0 | 199 (%91) | 216 | 19 | 17 | 4 | 44 | 134 | 0 |
| `KANAL_SIKAYETI` | M | 179 | – | 24 | 0 | 132 (%74) | 50 | 47 | 25 | 99 | 8 | 0 | 0 |
| `IKINCI_DONANIM` | M | 125 | 96 | – | 105 | 120 (%96) | 458 | 5 | 2 | 3 | 28 | 65 | 22 |
| `MODEM_DEGISIKLIGI` | M | 58 | – | – | 0 | 42 (%72) | 76 | 16 | 3 | 8 | 26 | 5 | 0 |
| `TV_ARIZA` | M | 58 | 16 | 6 | 38 | 29 (%50) | 24 | 29 | 9 | 5 | 14 | 1 | 0 |
| `UCRETLENDIRME` | M | 24 | 56 | – | 11 | 13 (%54) | 26 | 11 | 2 | 1 | 6 | 4 | 0 |
| `DOPING_ARIZA` | M | 19 | – | 24 | 0 | 8 (%42) | 10 | 11 | 7 | 0 | 1 | 0 | 0 |
| `EVRAK_SOSYAL` | M | 14 | – | – | 0 | 10 (%71) | 103 | 4 | 2 | 0 | 3 | 5 | 0 |
| `CIHAZ_GERI_ALIM` | M | 5 | – | 48 | 0 | 4 (%80) | 98 | 1 | 1 | 0 | 3 | 0 | 0 |
| `STB_DEGISIKLIGI` | M | 5 | 48 | – | 2 | 3 (%60) | 26 | 2 | 1 | 2 | 0 | 0 | 0 |
| `SUPERBOX_MODEM` | M | 5 | – | – | 0 | 3 (%60) | 61 | 2 | 0 | 1 | 2 | 0 | 0 |
| `EVRAK_TURKSAT` | M | 4 | 48 | – | 4 | 4 (%100) | 154 | 0 | 0 | 0 | 3 | 1 | 0 |
| `ARAMA` | M | 3 | 24 | 12 | 2 | 2 (%67) | 28 | 1 | 1 | 0 | 1 | 0 | 0 |
| `TURKSAT_CIHAZ_IADE` | M | 2 | – | – | 0 | 2 (%100) | 51 | 0 | 1 | 0 | 1 | 0 | 0 |
| `TV_KURULUM` | K | 463 | 36 | – | 416 | 434 (%94) | 334 | 29 | 23 | 15 | 83 | 177 | 136 |
| `SUPERBOX_KURULUM` | K | 325 | 48 | – | 247 | 286 (%88) | 127 | 39 | 38 | 23 | 101 | 123 | 1 |
| `FIBER_KURULUM` | K | 308 | 36 | – | 203 | 237 (%77) | 77 | 71 | 50 | 23 | 89 | 72 | 3 |
| `KURULUM_CIHAZ_GONDERIM` | K | 179 | 48 | – | 158 | 165 (%92) | 197 | 14 | 7 | 3 | 46 | 103 | 6 |
| `FIBER_DONUSUM` | K | 129 | 36 | – | 111 | 127 (%98) | 143 | 2 | 16 | 20 | 40 | 51 | 0 |
| `TT_FIBER_KURULUM` | K | 106 | – | – | 0 | 85 (%80) | 97 | 21 | 17 | 7 | 41 | 20 | 0 |
| `FIBER_NAKIL` | K | 62 | 36 | – | 40 | 50 (%81) | 82 | 12 | 11 | 5 | 26 | 8 | 0 |
| `YAN_ODA` | K | 29 | 36 | – | 27 | 27 (%93) | 284 | 2 | 1 | 0 | 8 | 10 | 8 |
| `FIBER_GECIS` | K | 13 | 36 | – | 8 | 8 (%62) | 48 | 5 | 1 | 1 | 4 | 2 | 0 |

**Anlık tablo:** 24 saati geçmiş açık iş oranı mevcut müşteride %73, kurulumda %88. Mevcut müşteride medyan yaş 56 saat, kurulumda 145 saat. BOSS'un kendi SL'ine göre: mevcut 288 geçti / 165 geçmedi / 500 SL tanımsız; kurulum 1.210 / 298 / 106.

### 3.4 Gerçek 24 saat uyumu (kohort — en doğru ölçü)

1-14 Eylül'de açılan mevcut-müşteri task'larından kaçı açılıştan sonraki X saat içinde tamamlandı. Payda = ANLATILAN 'GELEN' (günlük açılan), pay = TAMAMLANDI'da süresi ≤X saat olanlar. 24 saat içinde kapanan her task TAMAMLANDI'da görünür (export 16 Eylül sabahı), bu yüzden oran sansürsüz.

| Süre | ≤6s | ≤12s | ≤24s | ≤48s | ≤72s |
|---|---|---|---|---|---|
| Tamamlanma oranı | %20,0 | %28,1 | %43,4 | %59,0 | %65,5 |

| Tip | Kohortta kapanan | Tahmini açık kalan (16 Eyl) | 24s uyumu | FOX hedefi uyumu |
|---|---|---|---|---|
| `BAGLANTI` | 1.784 | 318 | %53 | %30 (≤12s) |
| `KANAL_SIKAYETI` | 479 | 243 | %3 | %3 (≤24s) |
| `CIHAZ_IADE` | 203 | 281 | %40 | %40 (≤24s) |
| `MODEM_DEGISIKLIGI` | 392 | 79 | %54 | – |
| `TV_ARIZA` | 354 | 79 | %50 | %20 (≤6s) |
| `UCRETLENDIRME` | 127 | 33 | %24 | – |
| `DOPING_ARIZA` | 100 | 26 | %47 | %47 (≤24s) |
| `EVRAK_SOSYAL` | 53 | 18 | %47 | – |
| `SUPERBOX_MODEM` | 28 | 7 | %49 | – |
| `STB_DEGISIKLIGI` | 23 | 7 | %13 | – |
| `SORU_CEVAP` | 29 | 0 | %79 | – |
| `CIHAZ_GERI_ALIM` | 21 | 7 | %4 | %18 (≤48s) |
| `TV_KURULUM` | 23 | 0 | %22 | – |
| `ARAMA` | 8 | 4 | %33 | %17 (≤12s) |
| `EVRAK_TURKSAT` | 6 | 5 | %9 | – |

Tip payları tahmini: 16 Eylül'de açık kalan 1.180 işin tipi bilinmediğinden, bugün açık ve ≤15 gün yaşındaki mevcut-müşteri işlerinin tip dağılımıyla paylaştırıldı (durağanlık varsayımı).

**Açılış gününe göre 24s uyumu (gün kötüleşiyor):**

| Tarih | Gün | Gelen | 24s içinde kapanan | Uyum |
|---|---|---|---|---|
| 09-01 | Sal | 433 | 280 | %65 |
| 09-02 | Çar | 518 | 279 | %54 |
| 09-03 | Per | 368 | 187 | %51 |
| 09-04 | Cum | 324 | 162 | %50 |
| 09-05 | Cmt | 306 | 145 | %47 |
| 09-06 | Paz | 205 | 51 | %25 |
| 09-07 | Pzt | 308 | 135 | %44 |
| 09-08 | Sal | 273 | 132 | %48 |
| 09-09 | Çar | 316 | 145 | %46 |
| 09-10 | Per | 271 | 130 | %48 |
| 09-11 | Cum | 275 | 119 | %43 |
| 09-12 | Cmt | 462 | 100 | %22 |
| 09-13 | Paz | 159 | 33 | %21 |
| 09-14 | Pzt | 339 | 81 | %24 |

Pazar açılan işlerin uyumu %21–25 (ekip 4 kişi, 'nöbet'); 12 Eylül Cumartesi 462 iş gelmiş (olağandışı pik), sonrasında uyum %21–24 bandına oturmuş. Hafta içi ilk günler %50–65 iken birikim büyüdükçe düşüş var.

**Kapananların açılış→kapanış süresi (saat, sağdan sansürlü):** tümü medyan 21,5 (p75 47,8, p90 121,8); saha teknisyeni kapanışı medyan 21,2, ofis kapanışı medyan 22,6 ama p75 131 (Kanal Şikayeti'nin 7 günlük askısı).

## 4. Birikim ayrıştırması

### 4.1 Sahip × durum

| Sahip | Toplam | Açık | Askıya alındı | Merkeze gönderildi | Konum Paylaşıldı | Başlandı | Ekip atanmış | Randevulu (=sevk edilmiş) |
|---|---|---|---|---|---|---|---|---|
| Mevcut müşteri | 953 | 627 | 221 | 53 | 18 | 34 | 380 | 381 |
| Yeni müşteri kurulum | 1.614 | 1.042 | 192 | 298 | 52 | 30 | 282 | 293 |

### 4.2 Bugün ne yapılabilir? (aksiyon kovaları)

- **A_bugun_sahaya_verilebilir** — Açık/Konum paylaşıldı/Başlandı, askıda değil, ileri tarihli randevusu yok, saha gerektiren tip.
- **B_askida_abone_takip** — Abone kaynaklı askı (müşteri müsait değil vb.) -> operasyon tekrar arayıp randevu verir.
- **B_merkezde_operasyon_aksiyonu** — Teknisyen 'merkeze gönderdi' (ulaşılamadı, güzergah/sinyal/port yok...) -> ofis çözer.
- **C_ofisten_kapatilabilir** — Saha gerektirmeyen tipler: Kanal Şikayeti (%98 'müşteri düzeldi dedi' ile ofisten kapanıyor), Cihaz İade (lojistik), FOX ofis işleri -> telefonla/ofisten kapatılır.
- **D_dis_bagimli_TT** — TT kaynaklı askı (etiketleme vb.) -> dış bağımlı, takip.
- **E_ileri_tarihli_randevu** — Randevusu yarın veya sonrasında.

| Sahip | A_bugun_sahaya_verilebilir | C_ofisten_kapatilabilir | B_askida_abone_takip | B_merkezde_operasyon_aksiyonu | D_dis_bagimli_TT | E_ileri_tarihli_randevu |
|---|---|---|---|---|---|---|
| Mevcut | 415 | 397 | 112 | 26 | 0 | 3 |
| Kurulum | 1.110 | 0 | 50 | 294 | 160 | 0 |

| Tip | A_bugun_sahaya_verilebilir | C_ofisten_kapatilabilir | B_askida_abone_takip | B_merkezde_operasyon_aksiyonu | D_dis_bagimli_TT | E_ileri_tarihli_randevu |
|---|---|---|---|---|---|---|
| `TV_KURULUM` | 331 | 0 | 16 | 116 | 0 | 0 |
| `SUPERBOX_KURULUM` | 255 | 0 | 3 | 67 | 0 | 0 |
| `FIBER_KURULUM` | 241 | 0 | 0 | 67 | 0 | 0 |
| `BAGLANTI` | 161 | 0 | 71 | 0 | 0 | 2 |
| `CIHAZ_IADE` | 0 | 218 | 0 | 0 | 0 | 0 |
| `KANAL_SIKAYETI` | 0 | 179 | 0 | 0 | 0 | 0 |
| `KURULUM_CIHAZ_GONDERIM` | 6 | 0 | 13 | 0 | 160 | 0 |
| `FIBER_DONUSUM` | 111 | 0 | 0 | 18 | 0 | 0 |
| `IKINCI_DONANIM` | 99 | 0 | 0 | 26 | 0 | 0 |
| `TT_FIBER_KURULUM` | 87 | 0 | 0 | 19 | 0 | 0 |
| `FIBER_NAKIL` | 43 | 0 | 18 | 1 | 0 | 0 |
| `MODEM_DEGISIKLIGI` | 54 | 0 | 4 | 0 | 0 | 0 |
| `TV_ARIZA` | 40 | 0 | 18 | 0 | 0 | 0 |
| `YAN_ODA` | 28 | 0 | 0 | 1 | 0 | 0 |
| `UCRETLENDIRME` | 15 | 0 | 9 | 0 | 0 | 0 |
| `DOPING_ARIZA` | 19 | 0 | 0 | 0 | 0 | 0 |
| `EVRAK_SOSYAL` | 12 | 0 | 2 | 0 | 0 | 0 |
| `FIBER_GECIS` | 8 | 0 | 0 | 5 | 0 | 0 |
| `CIHAZ_GERI_ALIM` | 5 | 0 | 0 | 0 | 0 | 0 |
| `STB_DEGISIKLIGI` | 4 | 0 | 1 | 0 | 0 | 0 |
| `SUPERBOX_MODEM` | 2 | 0 | 3 | 0 | 0 | 0 |
| `EVRAK_TURKSAT` | 1 | 0 | 3 | 0 | 0 | 0 |
| `ARAMA` | 2 | 0 | 0 | 0 | 0 | 1 |
| `TURKSAT_CIHAZ_IADE` | 1 | 0 | 1 | 0 | 0 | 0 |

### 4.3 Askı, merkeze gönderme ve son açıklama

|  | Mevcut | Kurulum |
|---|---|---|
| Askı: Abone kaynaklı | 301 | 48 |
| Askı: TT kaynaklı | 0 | 160 |
| Merkeze: ABONEYE ULAŞILAMADI - MÜSAİT DEĞİL | 46 | 260 |
| Merkeze: GÜZERGAH YOK | 0 | 35 |
| Merkeze: SİNYAL YOK | 1 | 27 |
| Merkeze: BOŞ PORT YOK | 1 | 17 |
| Merkeze: TASK GEÇ DÜŞTÜ | 8 | 15 |
| Merkeze: ABONE CİHAZI KAYIP-BULAMADI | 11 | 4 |
| Son açıklama: musteriye_ulasilamadi | 558 | 90 |
| Son açıklama: ekibe_atandi_notu | 42 | 259 |
| Son açıklama: tt_etiketleme_bekliyor | 0 | 159 |
| Son açıklama: musteri_ileri_tarih_istedi | 4 | 61 |
| Son açıklama: port_sinyal_kapasite | 0 | 25 |
| Son açıklama: guzergah | 0 | 21 |
| Son açıklama: stok_cihaz_yok | 1 | 10 |
| Son açıklama: musteri_cihazi_teslim_edecek | 13 | 0 |
| Son açıklama: iptal_istegi | 0 | 16 |
| Son açıklama: diger | 42 | 118 |
| Son açıklama: (boş) | 293 | 855 |

Son açıklamalar anahtar kelimeyle gruplandı (metin kopyalanmadı). 'BOSS üzerinden arama sağlandı, ulaşılamadı' kalıbı tek başına ~550 kayıtta — kayıtlı arama denemelerinin büyük kısmı sonuçsuz (aramayı kimin/neyin yaptığı açık soru).
'Ulaşılamadı' notlu mevcut-müşteri işleri tipe göre: BAGLANTI: 212, KANAL_SIKAYETI: 158, MODEM_DEGISIKLIGI: 53, TV_ARIZA: 53, UCRETLENDIRME: 20, DOPING_ARIZA: 19, CIHAZ_IADE: 12, EVRAK_SOSYAL: 9, IKINCI_DONANIM: 8, SUPERBOX_MODEM: 4, EVRAK_TURKSAT: 3, STB_DEGISIKLIGI: 3, TURKSAT_CIHAZ_IADE: 2, ARAMA: 2.

Askıdaki işlerin yaşı — mevcut: <24s: 48, 24-48s: 21, 48-72s: 87, 3-7g: 29, 7-30g: 36, >30g: 0; kurulum: <24s: 10, 24-48s: 7, 48-72s: 3, 3-7g: 59, 7-30g: 106, >30g: 7.

### 4.4 İlçe

| İlçe | Mevcut | Kurulum | Toplam |
|---|---|---|---|
| Nilüfer | 472 | 851 | 1.323 |
| Osmangazi | 176 | 248 | 424 |
| Yıldırım | 103 | 149 | 252 |
| İnegöl | 29 | 73 | 102 |
| Mudanya | 37 | 61 | 98 |
| Gemlik | 15 | 49 | 64 |
| Merkez | 28 | 29 | 57 |
| Kestel | 12 | 36 | 48 |
| Orhangazi | 9 | 21 | 30 |
| Karacabey | 14 | 14 | 28 |
| Çiftlikköy | 16 | 11 | 27 |
| Altınova | 5 | 18 | 23 |
| Gürsu | 6 | 17 | 23 |
| Armutlu | 7 | 10 | 17 |

## 5. Giriş (inflow) tahmini

> BOSS/FOX export'ları yalnızca HÂLÂ AÇIK işleri içerir; kapanmış işler görünmez. Bu yüzden açık dosyadan sayılan 'günlük açılış' her gün için bir ALT SINIRdır ve eski günlerde (kapananlar düştükçe) sistematik olarak küçülür. Mevcut-müşteri için sansürsüz tahmin ANLATILAN 'GELEN' (= o gün açılan tüm task; TAMAMLANDI + 16 Eylül'de açık kalan) ile yapıldı. Kurulum için sansürsüz kaynak yok; kapanmış kurulum raporu (BOSS 'Tamamlandı' filtresi) gerekir.

### 5.1 Mevcut müşteri — sansürsüz (ANLATILAN 'GELEN', 1–15 Eylül)

| Tarih | 09-01 | 09-02 | 09-03 | 09-04 | 09-05 | 09-06 | 09-07 | 09-08 | 09-09 | 09-10 | 09-11 | 09-12 | 09-13 | 09-14 | 09-15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gelen | 433 | 518 | 368 | 324 | 306 | 205 | 308 | 273 | 316 | 271 | 275 | 462 | 159 | 339 | 290 |

| Gün | Pzt | Sal | Çar | Per | Cum | Cmt | Paz |
|---|---|---|---|---|---|---|---|
| Ortalama gelen | 324 | 332 | 417 | 320 | 300 | 384 | 182 |

Takvim günü ortalaması **323**, hafta içi 338 (std 77), Cumartesi 384, Pazar 182. Ayın ilk günleri (1–2 Eylül: 433, 518) ve 12 Eylül (462) pik.

**Tip bazında günlük giriş (tahmin):**

| Tip | Kapanan (15 gün) | 16 Eyl'de açık kalan (tahmin) | Günlük ort. | Pay |
|---|---|---|---|---|
| `BAGLANTI` | 1.792 | 338 | 142,0 | %44,0 |
| `KANAL_SIKAYETI` | 479 | 259 | 49,2 | %15,2 |
| `CIHAZ_IADE` | 219 | 299 | 34,6 | %10,7 |
| `MODEM_DEGISIKLIGI` | 395 | 84 | 31,9 | %9,9 |
| `TV_ARIZA` | 354 | 84 | 29,2 | %9,0 |
| `UCRETLENDIRME` | 131 | 35 | 11,1 | %3,4 |
| `DOPING_ARIZA` | 102 | 28 | 8,6 | %2,7 |
| `EVRAK_SOSYAL` | 53 | 19 | 4,8 | %1,5 |
| `SUPERBOX_MODEM` | 28 | 7 | 2,4 | %0,7 |
| `STB_DEGISIKLIGI` | 23 | 7 | 2,0 | %0,6 |
| `SORU_CEVAP` | 29 | 0 | 1,9 | %0,6 |
| `CIHAZ_GERI_ALIM` | 21 | 7 | 1,9 | %0,6 |
| `TV_KURULUM` | 24 | 0 | 1,6 | %0,5 |
| `ARAMA` | 8 | 4 | 0,8 | %0,3 |
| `EVRAK_TURKSAT` | 6 | 6 | 0,8 | %0,2 |

Bu kapsamda **2.Donanım yok** (TAMAMLANDI'da hiç yok); açık dosyadan alt sınırı ~5,4/gün.

**Saatlik varış profili (mevcut, pay %):** 0:00 1,4, 8:00 1,5, 9:00 12,9, 10:00 7,9, 11:00 6,6, 12:00 8,1, 13:00 8,1, 14:00 7,4, 15:00 7,0, 16:00 6,6, 17:00 7,4, 18:00 6,2, 19:00 6,3, 20:00 4,3, 21:00 3,3, 22:00 2,2, 23:00 1,5. 09:00 piki (%13) gece biriken işlerin sabah düşmesi; 09–19 arası saatte %6–8 düzgün; akşam 20:00 sonrası ~%13.

### 5.2 Kurulum — yalnız alt sınır (sansürlü)

Son 7 günde açılıp hâlâ açık: kurulum **128/gün**, mevcut 98/gün (gerçek mevcut girişin ~%30'u → kurulumda da gerçek giriş belirgin biçimde daha yüksek). Son 24 saatte açılıp açık: kurulum 195, mevcut 254.

| Kurulum tipi | Son 7 gün, hâlâ açık / gün |
|---|---|
| `FIBER_KURULUM` | 33,3 |
| `SUPERBOX_KURULUM` | 28,7 |
| `TV_KURULUM` | 21,4 |
| `TT_FIBER_KURULUM` | 12,3 |
| `FIBER_DONUSUM` | 11,1 |
| `KURULUM_CIHAZ_GONDERIM` | 10,0 |
| `FIBER_NAKIL` | 7,7 |
| `FIBER_GECIS` | 1,6 |
| `YAN_ODA` | 1,6 |

### 5.3 Kapasite açığı

Hafta içi gelen ~338/gün; 7–15 Eylül (12–13 Eylül hariç) kapanan ~224/gün. ANLATILAN 'DURUM' sütununun 15 gün toplamı +1.180 (birikim artışı). YAPILAN yalnızca 1 Eylül sonrası açılan task'ların kapanışını sayar (Ağustos devri hariç) -> kapasite hafif eksik.

**Kaba denge (simülasyon öncesi sağlama):** mevcut giriş 323/gün × (1 − ziyaretsiz pay %43) ≈ **184 saha ziyareti/gün** gerekir; arıza ekibi kapasitesi ≈ ort. aktif teknisyen × ort. iş/gün ≈ **163/gün** (7 gün ortalaması). Ancak teknisyen kapanışlarının %39 kadarı 'düzelmiş/şebeke' bulunan iş; telefon filtresi bunları ayıklarsa kalan işler gerçek onarım olur ve kişi başı iş/gün düşer (tahmini 12–14). Simülasyon bu iki etkiyi birlikte modellemeli.

## 6. Teknisyen yükü ve coğrafya

**BOSS açık işlerde:** 37 farklı ekip adı, atanmış 662 iş, atanmamış 1.905. Ekip başı açık iş medyan 13 (p90 32). BOSS 'Teknisyen' alanı saha teknisyeni değil (68 kayıtta dolu, pozisyonları: EÇM-Fiber- Satış Destek - Sorumlu: 59, EÇM-Fiber- Satış Destek - Takım Lideri: 7, EÇM-Fiber- Teknik - Sorumlu: 2).

| Ekip (ilk 20) | Açık iş | Mevcut | BTK | İlçe sayısı | Medyan yaş (s) |
|---|---|---|---|---|---|
| HAKTAN GURBETÇİ | 66 | 65 | 62 | 2 | 32 |
| SELİM SANIR | 66 | 66 | 48 | 2 | 67 |
| YUNUS EMRE PINARCI | 34 | 0 | 0 | 1 | 239 |
| DENİZ EKİCİ | 34 | 1 | 0 | 3 | 216 |
| ŞÜKRÜ BİLEN | 30 | 30 | 26 | 2 | 29 |
| ABDULLAH AKINOĞLU | 29 | 29 | 2 | 1 | 102 |
| HAKAN ORAL | 29 | 29 | 27 | 1 | 28 |
| EFECAN ŞAHİN | 29 | 0 | 0 | 1 | 48 |
| ENES KORHAN | 28 | 28 | 26 | 3 | 25 |
| AHMET TEMEL | 27 | 27 | 22 | 1 | 21 |
| ERKAN DEMİR | 26 | 0 | 0 | 1 | 149 |
| MUSTAFA EGEMEN YILDIRIM | 23 | 23 | 13 | 1 | 53 |
| SÜLEYMAN SAĞ | 22 | 22 | 15 | 1 | 20 |
| MUTSEL TARIK EYİZLER | 21 | 21 | 18 | 1 | 8 |
| ERTUĞRUL ŞAHİN | 20 | 13 | 0 | 3 | 734 |
| CAHİT PEKŞEN | 14 | 13 | 10 | 4 | 8 |
| FERHAT BİROL | 14 | 0 | 0 | 1 | 125 |
| İBRAHİM GÖÇOĞLU | 14 | 0 | 0 | 1 | 132 |
| SERVET DAĞDAGÜL | 13 | 0 | 0 | 3 | 151 |
| UMUT ÇORUM | 11 | 11 | 6 | 1 | 52 |

Arıza ekibi ile kurulum ekipleri net ayrık: açık işi olan 37 ekipten 13 ekipte işlerin ≥%90'ı mevcut müşteri, 22 ekipte ≥%90'ı kurulum.

### 6.1 Verim (TAMAMLANDI, 3–15 Eylül)

| Ölçü | Değer |
|---|---|
| Arıza ekibi (ANLATILAN pivot) | 12 kişi |
| Günlük aktif arıza teknisyeni (medyan / ort.) | 10 / 9,0 |
| ANLATILAN 'EKİP SAYISI' (medyan, min–maks) | 10 (Pazar 4–8) |
| Günlük aktif saha adı (kurulumcu dahil, medyan) | 18 |
| Arıza teknisyeni iş/gün (p25 / medyan / p75 / p90) | 14 / 17 / 20 / 26 |
| Ardışık kapanış arası dk (5–180 dk; p25/medyan/p75) | 18 / 31 / 50 |
| <5 dk arayla kapanış (toplu kapatma işareti) | %34 |
| Gün içi ilk / son kapanış saati (medyan) | 11,1 / 18,7 |
| İlk→son kapanış aralığı (saat, medyan) | 8,1 |
| Ofisten kapanış oranı (12 Eylül toplu kapatma hariç / dahil) | %8,3 / %20,6 |
| 12 Eylül ofisten toplu kapanış | 430 |

Yerinde iş süresi (İşe Başlama→Bitirme) **türetilemedi**: kapanmış işlerde bu damgalar yok, açık export'ta bitirme 2 kayıtta. Döngü süresi vekili (yol + iş) medyan ~31 dk; ancak kapanışların üçte biri <5 dk arayla (sahada değil sonradan toplu kapatma) — gerçek döngü muhtemelen 35–45 dk. Günlük 17 iş × ~30 dk ≈ 8,5 saat, 'ilk→son kapanış' ~8,1 saat ile tutarlı.

### 6.2 Lokasyon eşleşmesi (BOSS `Lokasyon` → `bina_master.location_id`)

| Durum | BOSS açık | TAMAMLANDI |
|---|---|---|
| dogrudan | 1.328 | 2.166 |
| sifir_kirpma | 168 | 394 |
| master_da_yok | 20 | 2 |
| lokasyon_yok | 1.051 | 1.105 |

Konumlu oran: tüm açık %58 (mevcut %54, kurulum %61); dolu Lokasyon içinde eşleşme %98,7. 'sifir_kirpma' = BOSS'ta '00xxxxxx' biçimli, baştaki sıfırlar atılınca eşleşen kimlikler. Lokasyon boş olan tipler: Superbox (kablosuz), Kanal Şikayeti, TT Fiber, Kurulum ve Cihaz Gönderim, çoğu Cihaz İade -> bunlar için yalnızca ilçe var. 'master_da_yok' = tur raporunda olmayan binalar (yeni eklenmiş olabilir).

### 6.3 Kümelenme potansiyeli

| Küme | Konumlu iş | 500 m'de ≥1 komşu | 500 m komşu (medyan) | 500 m'de ≥5 komşu | 2 km komşu (medyan) | En yakın komşu m (medyan) | Aynı binada başka iş | 500 m kümeleri (sayı / en büyük) | 2 km kümeleri |
|---|---|---|---|---|---|---|---|---|---|
| Tüm açık | 1.496 | %99 | 13 | %86 | 66 | 40 | %41 | 75 / 435 | 18 / 570 |
| Mevcut açık | 512 | %96 | 5 | %56 | 27 | 112 | %18 | 68 / 111 | 16 / 236 |
| Mevcut, bugün sahaya verilebilir | 377 | %92 | 4 | %47 | 20 | 155 | %12 | 72 / 96 | 14 / 169 |
| Kurulum açık | 984 | %98 | 9 | %77 | 40 | 37 | %45 | 91 / 324 | 18 / 403 |

**Tek bir günün girişi** (1–12 Eylül, konumlu, günde ~150–280 iş): en yakın komşu medyanı 140–271 m; işlerin %72–89 kadarının 500 m içinde aynı gün gelen başka işi var.
**Bugünkü rota yayılımı:** bir teknisyenin bir gün kapattığı işlerin ağırlık merkezine medyan uzaklığı 1.816 m (p75 2.803, p90 5.196 m), gün başına medyan 1 ilçe. Mevcut açık işlerin ofise uzaklığı medyan 9,1 km (p90 16,9).

Mevcut açık işin en yoğun mahalleleri: Dumlupınar (80), Görükle (31), Yüzüncüyıl (23), Millet (21), Hamitler (18), Balkan (18), Yenikent (14), Çamlıca (14), 30 Ağustos Zafer (14), Konak (12).

## 7. Randevu

> BOSS'ta 'Randevulu' = işin bir ekibe 2 saatlik zaman dilimiyle atanması (randevulu işlerin %98'inde Ekip dolu, randevusuzların hiçbirinde yok). Yani 'randevu' müşteriyle kararlaştırılmış saatten çok sevk (dispatch) kaydı; 'geçmiş randevu + hâlâ açık' = sevk edilmiş ama kapanmamış iş.

| Ölçü | Değer |
|---|---|
| Randevulu / Randevusuz | 648 / 1.919 |
| Randevu dilimi uzunluğu | 2 saat (669/674) |
| En sık dilim başlangıcı | 11:00 (221); 13–19 arası her saat 37–61; 02–03 arası 32 (gece girilmiş/yer tutucu) |
| Açılış → randevu (mevcut; medyan / p75 / p90 saat) | 6,1 / 19,3 / 94,5 |
| Açılış → randevu (kurulum; medyan / p75 / p90 saat) | 47,0 / 141,9 / 309,5 |
| Dilimi geçmiş ama hâlâ açık | 586 (durum: Açık: 467, Konum Paylaşıldı: 60, Başlandı: 57, Askıya alındı: 2) |
| Geçmiş dilimin üzerinden geçen gün (medyan / p75 / p90) | 1,2 / 3,0 / 7,9 |
| İleri tarihli (yarın+) | 15 |

Geçmiş dilimi olup açık kalan işler tipe göre: BAGLANTI 150, FIBER_DONUSUM 108, TV_KURULUM 66, MODEM_DEGISIKLIGI 49, TV_ARIZA 48, FIBER_KURULUM 38, SUPERBOX_KURULUM 36, DOPING_ARIZA 18, IKINCI_DONANIM 14, FIBER_NAKIL 13.

## 8. PS26 `data.xlsx` manuel sayfalar — hangi süreç, ne hacim

| Sayfa | Süreç | Hacim / durum |
|---|---|---|
| ORIGN | Tur raporu (fiber bina envanteri: HP, aktif abone, altyapı, sales-ready). Bölgeleme ve LOCS'un kaynağı. | 19.707 bina; location_id'lerin tamamı bina_master ile ortak (19.706) |
| LOCS | BTK acil sinyal ticket'ı metin şablonu ('*BTK ÇAĞRISI ACİL MÜDAHALE* … sinyal zayıftır') + bina arama tablosu (Bina Serial, Tellcordia ID, Location Id, Öbek, Site Adı). OneDesk ticket'ı açarken lokasyon bilgisini kopyalamak için kullanılıyor; OPENED = bugün. | 19.707 bina satırı; müşteri no yalnız 1 satırda |
| TICKET | Sinyal zayıf/yok (SİNYAL, 132) ve ek splitter/kapasite (EK SP, 65) talepleri: lokasyon bazında OneDesk (sinyal) / ONENT PYS 'Ek Kapasite' (EK SP) ticket'ı açılıp durum elle izleniyor. HATA = ticket reddedildi/hatalı; Ticket no boş = henüz ticket açılamamış (çoğu EK SP HATA). | 197 kayıt: SİNYAL 132 / EK SP 65; durum ÇÖZÜLDÜ: 128, HATA: 32, AÇIK: 26, KAPATILDI: 9, İPTAL: 2 |
| GUZERGAH | Kurulumda 'güzergah yok' (binaya/daireye kablo yolu yok) çıkan işler. Sayfada 16.912 satır var ama yalnızca ~64'ü dolu (geri kalanı boş/biçim satırı). Hepsi 'YOK' durumunda: kapanış/çözüm alanı yok. | 16.912 satır, dolu olan 64; kanal DEHA: 34, GLOBAL: 30; aylık 2026-07: 30, 2026-08: 21, 2026-09: 13 |
| ALTYAPI | Altyapı kaynaklı gecikme/iptal: satışı yapılmış ama altyapı (port/fiber yok) yüzünden kurulamayan müşteriler; satıcı ve bölge ile. Durum/çözüm sütunu yok. | 67 kayıt; kanal GLOBAL: 30, DEHA: 23, TOPTAN: 14; aylık 2026-08: 35, 2026-09: 24, 2026-07: 8; 25 satıcı |
| PVT | ALTYAPI sayfasının satıcıya göre pivotu (toplam 66-67). | 27 satır |

**TICKET ayrıntı:** SİNYAL'de çözülme %83; EK SP'de yalnız %29 çözülmüş, %46 HATA (ticket no'su boş: HATA: 31, AÇIK: 2, ÇÖZÜLDÜ: 2). Son 30 günde 105 ticket (~3,5/gün). AÇIK ticket yaşı medyan 22 gün (p90 62); HATA yaşı medyan 30 gün. Detay notlarında 12 'tekrar açıldı', 8 'EK SP için müşteri eklenmeli'. Kanal: GLOBAL: 97, DEHA: 49, ARIZA: 47, TOPTAN: 4. Lokasyon→bina_master eşleşmesi %97,4.

**BOSS ile çapraz kontrol:** BOSS'ta 'SİNYAL YOK / BOŞ PORT YOK' ile merkeze dönmüş 31 lokasyonun 19 adedi TICKET sayfasında var (%61); 'GÜZERGAH YOK' ile dönen 20 lokasyondan yalnız 2 adedi GUZERGAH sayfasında → manuel takip BOSS'tan kopuk; güzergah listesi güncel değil.

**GUZERGAH:** kayıtların hepsi 'YOK' durumunda, kapanış alanı yok; yaş medyan 58 gün; 17 kayıt 'TURDA YOK' (tur raporunda olmayan bina). **ALTYAPI:** yaş medyan 36 gün; en çok Demirtaş (15) ve Görükle (13).

## 9. Simülasyon parametreleri (özet — tamamı JSON `parametreler`)

| Parametre | Değer | Dayanak |
|---|---|---|
| Mevcut müşteri giriş / gün | takvim 323; hafta içi 338; Cmt 384; Paz 182 | ANLATILAN GELEN 1–15 Eyl |
| Tip payı (mevcut) | BAGLANTI %44, KANAL_SIKAYETI %15, CIHAZ_IADE %11, MODEM_DEGISIKLIGI %10, TV_ARIZA %9, UCRETLENDIRME %3, DOPING_ARIZA %3 | TAMAMLANDI + açık paylaştırma |
| Kurulum giriş / gün | ≥128 (alt sınır) | son 7 gün hâlâ açık |
| Ziyaretsiz kapanış (mevcut / BTK arıza) | %43 / %44 | Arıza Nedeni + kapatan |
| Telefon/uzaktan nedeni (BTK arıza) | %30 | 'müşteri düzeldi dedi' vb. |
| Kanal Şikayeti ziyaretsiz | %99 | %98 ofis kapanışı |
| Tekrar arıza oranı (15 gün) | %35 | aynı müşteri >1 BTK task |
| Arıza teknisyeni iş/gün | medyan 17 (ort 18,1) | TAMAMLANDI 3–15 Eyl |
| Aktif arıza teknisyeni / gün | medyan 10 (12 kişilik havuz; Pazar 4–8) | TAMAMLANDI + ANLATILAN |
| Döngü süresi (yol+iş) vekili | medyan 31 dk (p75 50) | ardışık kapanış farkı |
| Yerinde iş süresi | türetilemedi | İşe Başlama→Bitirme yok |
| Mesai penceresi (kapanış) | ~11,1 – 18,7 | ilk/son kapanış medyanı |
| Varış profili | 09:00 %13; 10–19 saatte %6–8; 20:00+ ~%13 | saatlik |
| SL hedefi (saat) | Bağlantı 24 (FOX 12) · TV+ Arıza 16 (FOX 6) · Arama 24 (FOX 12) · Kanal —(FOX 24) · Kurulum 36–48 · 2.Donanım 96 | BOSS SL Süresi ters mühendislik |
| Gerçek 24s uyumu (mevcut) | %43 (Bağlantı %53, TV %50, Kanal %3) | kohort |
| Birikim (mevcut / kurulum) | 953 / 1.614 | BOSS açık |
| Konumlu iş oranı | mevcut %54, kurulum %61, kapanan mevcut %70 | Lokasyon→bina_master |
| Ulaşılamama | açıklamalı işlerde 'ulaşılamadı' payı %46 | Son Açıklama |

## 10. Veri kalitesi sorunları (sistemi kurarken düzeltilmesi gerekenler)

- Kapanışta **Arıza Nedeni** BTK arızalarında dolu ama Modem Değişikliği, Cihaz İade, Ücretlendirme, Evrak'ta hiç girilmiyor; açık export'ta 'Telefonla Çözülebilir Miydi?' alanı boş.
- **Konum Paylaş ve İşe Başla aynı anda basılıyor** (%81) → yol süresi ve varış saati ölçülemiyor; Bitirme damgası kapanmış işlere taşınmıyor.
- **1–2 Eylül'de 'Teknisyen' alanı hiç dolmamış**; 12 Eylül'de 430 iş ofisten toplu kapatılmış → günlük verim bu günlerde yanıltıcı.
- Kapanışların **üçte biri <5 dk arayla** (sonradan toplu kapatma) → gerçek zamanlı durum görünmüyor.
- **Lokasyon** Superbox, Kanal Şikayeti, TT Fiber, Kurulum ve Cihaz Gönderim ve Cihaz İade'nin çoğunda boş → bu işler haritalanamıyor (yalnız ilçe).
- BOSS 'Askıya Alınma Nedeni' değerinde sondaki boşluk ('TT kaynaklı ') — filtrelerde gözden kaçıyor.
- Kanal Şikayeti, Cihaz İade, Modem Değişikliği, Doping, Evrak, TT Fiber için **BOSS'ta SL yok** → SL raporunda görünmüyor.
- FOX 'Kalan Süre' bazı kayıtlarda donuyor (-72 / -36) → yaşlandırma için kullanılmamalı.
- PS26 GUZERGAH sayfasında 16.912 satırın yalnız 64'ü dolu; TICKET'ta ticket no'suz 35 kayıt; ALTYAPI/GUZERGAH'ta durum/çözüm alanı yok.

## 11. Yalnızca sizin cevaplayabileceğiniz sorular

1. `TAMAMLANDI.xlsx` ve `ANLATILAN.xlsx` (masaüstü) bu analizde kullanılabilir mi? Kurulum için de aynı biçimde 'Tamamlandı' raporu (son 30 gün, tüm tipler, Teknik Ekip İşe Başlama/Bitirme sütunlarıyla) çekilebilir mi?
2. Kanal Şikayeti'nin ~7 gün 'abone kaynaklı askı'da bekletilmesi Turkcell'in istediği bir kural mı, yoksa aynı gün telefonla kapatılabilir mi? BTK ölçümüne giriyor mu?
3. Esas alınacak hedef hangisi: bayi SL'i (Bağlantı 24s, TV 16s) mi, Turkcell FOX hedefi (Bağlantı 12s, TV 6s) mi, yoksa 'her iş 24 saat' kuralı mı?
4. 2.Donanım (125 açık), Yan Oda, TV+ Kurulum (mevcut aboneye TV), Fiber Dönüşüm/Nakil kimde: arıza ekibinde mi kurulum ekibinde mi?
5. Cihaz İade Bekleniyor (218 açık): cihazı teknisyen mi topluyor, müşteri bayiye mi getiriyor / kargo mu? Kim kapatıyor?
6. 'BOSS üzerinden arama sağlandı, ulaşılamadı' notunu kim düşüyor (operasyon mu, teknisyen mi)? Günde kaç kişi mevcut müşteriyi arıyor?
7. Arıza ekibi kaç kişi ve vardiya düzeni ne (12 kişi, Pazar nöbeti 4–8)? Gerektiğinde kurulumcudan arızaya kaydırma mümkün mü? Mesai kaçta başlıyor (ilk kapanışlar ~11:00)?
8. BOSS'ta 'Randevulu' gerçekten müşteriye bildirilen 2 saatlik bir dilim mi, yoksa yalnızca ekibe atama kaydı mı?
9. Yalnız FOX'ta kalan 56 kayıt (Donanım Teslimat Şikayet 25, BTK Şikayet 5, Kurulum Taskı Ürememiş 4 …) kimin sorumluluğunda ve nereden kapatılıyor?
10. Lokasyonu olmayan işler (Superbox, Kanal Şikayeti, TT Fiber, Cihaz İade) için adres metninden yerel (ağ çağrısız) mahalle eşlemesi yapılmasına izin var mı?
