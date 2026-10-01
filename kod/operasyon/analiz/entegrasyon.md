# Operasyon Sistemi — Entegrasyon Mimarisi

**Dehanet EÇM · 29 Eylül 2026 · durum: tasarım (kod yazılmadı, hiçbir Turkcell sistemine bağlanılmadı)**

Bu belge yeni sistemin veriyi **nereden, nasıl, ne sıklıkla** alacağını ve Turkcell sistemlerine
**nasıl geri yazacağını** anlatır. Hedef: en az elle iş, sıfır şifre riski.

Dayanak ölçümler: `operasyon/analiz/entegrasyon_profil.py` → `cikti/entegrasyon_profil.json` ve
`cikti/gorev_sozlugu.json`. Çıktılarda yalnız toplu sayım var; müşteri adı, adres, telefon ya da müşteri no yok.

---

## 0. Tek sayfada

| Kaynak | Şimdi (1. hafta, BT gerekmez) | Sonra (BT onayıyla) | Hedef (BT projesi) | Sıklık |
|---|---|---|---|---|
| **BOSS** açık işler | Dışa aktar → **İndirilenler klasörünü izleyen içe aktarma** | Tarayıcı köprüsü (eklenti), 30 dk | Rapor API'si ya da zamanlanmış rapor | 30 dk (köprü) / günde 3–4 (elle) + **günlük "dün kapananlar"** |
| **Fox** açık + askı | Aynı: iki dosya birlikte, klasör izleme | Köprü, 1–2 saat | Rapor API'si | Günde 2–4 |
| **OneDesk** ticket | Uygulama ticket metnini hazırlar → sen yapıştırırsın → ticket no'yu geri girersin | Ticket sayfasından DOM okuyan yer imi | Salt okunur ticket API'si | Açarken + günde 1 durum |
| **ONENT** ek kapasite (EKSP) | Aynı desen: ön-dolu talep + talep no geri girilir | DOM okuyan yer imi | Salt okunur talep API'si | Açarken + günde 1 |
| **OneMap** | Uygulamanın ürettiği **hazır sorgu adresi** tarayıcıda açılıp kaydedilir | Köprü (bugünkü çekimin aynısı) | ArcGIS servis hesabı | Yalnız yeni bina + ayda 1 tam |
| **Tur raporu** (data.xlsx) | Sürükle-bırak → **fark önizleme** → onay | — | Paylaşılan klasöre/SFTP'ye zamanlanmış teslim | Geldikçe |
| **Outlook** | Uygulamada "maildeki talep" formu (kod ayıklar) | Outlook masaüstü kuralı + yerel klasör okuma | Paylaşılan posta kutusu + EWS | Geldikçe |
| **WhatsApp** | **Kaynağı taşı:** talep saha uygulamasından girilir; geçmiş için sohbet dışa aktarımı | **Yok** (WhatsApp Web otomasyonu yasak) | Uygun değil | — |

**Veriden çıkan 10 bulgu (tasarımı değiştirenler):**

1. **Fox → BOSS aktarımı neredeyse anlık:** 2.561 ortak işte gecikme medyanı **7 sn**, p99 **9 dk**. Ana akış BOSS'tan beslenebilir.
2. **Ama Fox tek başına gerekli:** 56 iş **yalnız Fox'ta**, bunların 54'ü mevcut müşteri. Aralarında **5 "BTK Şikayet" ve 1 "BTK / Mahkeme Şikayet" (Turkcell hedefi 4 saat)** var. Bunlar BOSS'a hiç düşmüyor. Fox'u bırakırsak en kritik işler görünmez olur.
3. **78 işte askı durumu çelişiyor:** Fox "askıda", BOSS değil (57'si BOSS'ta "Açık"). Tersi 2 iş. Her içe aktarmada çelişki listesi üretilmeli.
4. **Binaya bağlama:** BOSS `Lokasyon` işlerin yalnız **%59**'unda dolu. Ham eşleşme %51,7. Kök neden bulundu: tur raporu Excel'i sayısal Location Id'lerin **baştaki sıfırlarını atıyor** (2.335 binada `113704` ↔ `00113704`). Sıfır doldurma kuralıyla eşleşme %58,3'e, dolu olanlarda **%98,7**'ye, aynı müşterinin başka işinden kurtarmayla **%62,1**'e çıkıyor. Fiber işlerde oran %98,5. Kalan boşluk Superbox, ADSL ve TT Fiber: bu işlerin fiber binası yok, adresten mahalleye düşülür.
5. **Açık iş listesi kapanışı ölçemez:** BOSS dışa aktarımında `Task Bitiş` 2.567 işin yalnız 2'sinde dolu. Gerçek SLA için ya sık anlık görüntü (kaybolma tespiti) ya da **günlük "kapanan işler" raporu** şart.
6. **BOSS dışa aktarımında telefon numarası yok:** telefon kolonu yok, adres ve son açıklama alanında da telefon izi 0. Arama için numara BOSS/Maya ekranından okunur. Bizim veritabanımıza **telefon girmez**; bu büyük bir KVKK kazancı.
7. **BOSS'un saha alanları neredeyse hiç kullanılmıyor:** konum paylaşma 182, işe başlama 173 iş (%7). "Telefonla çözülebilir miydi?", "Temel arıza nedeni" ve "Arıza nedeni" kolonları **tamamen boş**. Bu bilgileri bizim uygulama toplamalı.
8. **Takip kitabındaki GUZERGAH sayfası 16.912 değil, 64 kayıt.** Geri kalanı biçimlendirilmiş boş satır. TICKET 197 kayıt (SİNYAL 132, EK SP 65; 26 açık), ALTYAPI 67 kayıt. Göç küçük ve tek seferlik.
9. **Tur raporu henüz yenilenmedi:** PS26'daki ORIGN, 19 Eylül kopyasıyla birebir aynı (0 yeni, 0 kalkan, 0 değişen). OneMap'te `LAST_EDITED_DATE` artımlı çekim için **işe yaramıyor**: 19.706 binanın 16.876'sı çekimden önceki 30 günde "düzenlenmiş" görünüyor, yani toplu sistem güncellemesi var. Artımlı çekim **kimlik (ID) bazlı** yapılmalı.
10. **ACİL güvenlik riski:** PS26 deposu `guncelle.bat` ile `data/*.json` dosyalarını GitHub'a itiyor ve GitHub Pages ile yayınlıyor. İçerik: tur raporu (ORIGN, 5 MB), müşteri no'lu TICKET, GUZERGAH ve ALTYAPI listeleri, satıcı adları. GitHub Pages siteleri depo özel olsa bile varsayılan olarak **herkese açıktır** (erişim denetimi yalnız Enterprise Cloud'da var). Ayrıca bu, Turkcell verisinin yurt dışına aktarımı demek (KVKK md. 9). → §6.3

---

## 1. Kırmızı çizgiler (her seçenek bunlara uymak zorunda)

1. **Şifre yok.** Uygulama, betik ya da eklenti hiçbir Turkcell şifresini, çerezini ya da jetonunu okumaz, saklamaz, girmez. Oturum düşerse sistem giriş denemez; "oturum açın" uyarısı verir.
2. **Turkcell sistemlerine otomatik yazma yok.** Atama, randevu, askı, kapatma, ticket ve EKSP işlemleri Turkcell ekranlarında **insan eliyle** yapılır. Bizim sistem bunları hazırlar, sıraya koyar (giden kutusu, §3.9) ve bir sonraki içe aktarmada **yapıldığını doğrular**.
3. **Resmî kayıt BOSS ve Fox'tur.** Bizim sistem gölge takip ve karar destek aracıdır. Çelişkide BOSS/Fox kazanır; bizim sistem çelişkiyi gösterir.
4. **Veri en aza indirilir.** Telefon içe alınmaz. Müşteri adı maskeli tutulur (`A*** K***`). Tam adres yalnız binaya bağlanamayan işlerde tutulur ve iş kapandıktan 30 gün sonra silinir. Ham dışa aktarım dosyaları 7 gün sonra silinir.
5. **Veri ofis bilgisayarında kalır.** Bulut yok, git yok (`saha/.gitignore` zaten `saha.db`, `yedek/` ve `gizli.key` dosyalarını dışarıda tutuyor). Diskte BitLocker ve şifreli yedek olmalı (BT).
6. **Her içe aktarma kayıt altında:** kim, ne zaman, hangi dosya (SHA-256), kaç satır, ne değişti.
7. **(b) tarayıcı köprüsü yalnız BT'nin yazılı onayıyla açılır.** Onaya kadar sistem tamamen (a) ile çalışır. Tasarım (b) olmadan da eksiksiz çalışmalı.

---

## 2. Kaynaklar

### 2.0 Üç yol ne demek

**(a) Elle dışa aktarma → otomatik içe aktarma.** Bugün yaptığın şey (BOSS'ta "Excel'e aktar") aynen devam eder; sonrasında elle iş kalmaz.
- **Sürükle-bırak:** Yönetici konsolunda "Veri Yükle" kutusu. Kaynak **kolon imzasından** tanınır, dosya adı önemsizdir (`ReportResultAçık.xls` adındaki Türkçe karakter bozulsa da sorun olmaz).
- **Klasör izleme (önerilen):** Sunucu, ofis bilgisayarında `İndirilenler` klasörünü (ya da `İndirilenler\DSALE`) izler. `TeknikTaskDetayRaporu*.xlsx` veya `ReportResult*.xls` düştüğü anda içe alır ve dosyayı karantina klasörüne taşır. **Dışa aktar düğmesine basmak dışında tek tık yok.**
- Güvenilirlik yüksek, tek zayıflığı insan. Bu yüzden ekranda **veri yaşı rozeti** olur: BOSS verisi 2 saatten eskiyse sarı, 4 saatten eskiyse kırmızı.

**(b) Tarayıcı köprüsü (browser-assisted sync).** OneMap'i çekerken yaptığımız yöntem, ama kalıcı ve denetlenebilir biçimde.
- Küçük bir yerel tarayıcı eklentisi ("Dehanet Köprü"): Manifest V3, paketlenmemiş, yaklaşık 150 satır, kaynak kodu depoda, harici sunucu yok.
- Eklenti, **sen zaten oturum açmışken** BOSS sekmesinin içinden, sayfanın kendi "Excel'e aktar" düğmesinin çağırdığı adresi çağırır. Çağrı `credentials: 'include'` ile aynı kökenden yapılır. Oturum çerezi tarayıcıdan hiç çıkmaz; eklentinin `cookies` izni yoktur.
- Sonuç iki yoldan birine gider: `http://127.0.0.1:8080/api/op/kopru/{kaynak}` adresine gönderilir, ya da `chrome.downloads` ile izlenen klasöre yazılır. İkinci yol daha sağlamdır: CORS gerekmez, Chrome 142+'in **Yerel Ağ Erişimi (LNA)** izin istemi çıkmaz.
- Yer imi (bookmarklet) seçeneği kurulum istemez. Ama sayfanın CSP kuralı `127.0.0.1`'e çağrıyı engelleyebilir, LNA istemi çıkar ve zamanlanamaz. Bu yüzden yalnız OneDesk/ONENT'te **ekrandaki ticket no'yu okumak** için uygundur.
- Zamanlama (BT onayından sonra): `chrome.alarms` ile 30 dakikada bir, yalnız 08:00–20:00, yalnız açık ve oturumu geçerli bir BOSS sekmesi varsa çalışır.
- **Denetim izi:** Turkcell tarafında bu çağrılar senin oturumundan yapılmış rapor istekleri olarak görünür; senin düğmeye basmanla aynı kayıttır. Sıklık (saatte en fazla 2–4) ve amaç BT'ye yazılı bildirilir.
- **Uç keşfi:** Düğmenin hangi adresi çağırdığı bir kez öğrenilmeli (Ağ sekmesi). Chrome'da DevTools şirket politikasıyla kapalı; OneMap'te Brave kullanmıştık. **Politikayla kapatılmış bir özelliği başka tarayıcıyla aşmak denetimde "politika atlatma" sayılabilir.** Brave ve eklenti kullanımı BT'ye açıkça sorulmalı (§6.2).
- Kırılganlık: Turkcell ekranı değiştiğinde köprü bozulur. Bozulunca sistem sessizce eski veriyle çalışmaz; kırmızı rozet çıkar ve (a)'ya düşülür.

**(c) Resmî API / veritabanı erişimi (Turkcell BT).** Salt okunur servis hesabı, IP kısıtlı, loglu. En güvenilir ve denetim açısından en temiz yol. Ama süre haftalar-aylar ve bayiye verilip verilmeyeceği belirsiz. Ara çözüm: **zamanlanmış rapor**. BT, BOSS raporunu her saat başı paylaşılan bir klasöre ya da SFTP'ye bırakır; bizim klasör izleyici aynen alır. Kod değişmez, yalnız klasör yolu değişir.

> Üç yolda da **içe aktarma kodu aynıdır**: dosya ya da yük → aynı doğrulama ve upsert hattı (§3). Yol değiştirmek yeniden yazım gerektirmez.

---

### 2.1 BOSS (boss.turkcell.com.tr) — ana iş emri kaynağı

| | |
|---|---|
| **Ne lazım** | Task No, Task Adı, Müşteri No, İl/İlçe, Lokasyon, Ürün Bilgisi, Segment, Hız Detay, Task Başlangıç/Bitiş, Task Durumu, Randevu Durumu/Başlangıç/Bitiş, Askıya Alınma Nedeni, Merkeze Gönder Statüsü, Ekip, Teknisyen, Teknik Ekip Konum Paylaşma/İşe Başlama/Bitirme, SL, SL Süresi(Sa), Son Açıklama, Satış Kanalı, En Son İşlem Yapan (yalnız rol/sayım için). **Alınmayan:** Cihaz Seri No, Satış Temsilcisi adı; müşteri adı yalnız maskeli; adres yalnız eşleşmeyende. 6 kolon tamamen boş, 5 kolon sabit: içe alınmaz. |
| **Yön** | Okuma. Yazma (atama, randevu, askı, kapatma) **elle**, giden kutusundan (§3.9). |
| **Sıklık** | Açık liste: köprüyle 30 dk; elle 08:30, 12:30, 16:30 (+ 19:30). **Kapanan işler:** her sabah "dün kapananlar" (Task Bitiş dolu) raporu. Hacim: günde ~300+ yeni iş (28 ve 29 Eylül'de açılıp hâlâ açık olanlar 350 ve 310), 2.567 açık satır, dosya ~1 MB. |
| **Veri notu** | Rapor 51 kolon, `Task No` tekil. Kalıcı eşleşme anahtarları: `Task No` (= Fox `Akış No`), `Müşteri No` (Fox ile %100 tutarlı), `Lokasyon` (= bina `location_id`, sıfır doldurmalı). |

| Sıra | Yol | Emek (biz) | Güvenilirlik | Hukuk / güvenlik | BT'den istenecek |
|---|---|---|---|---|---|
| **1 (şimdi)** | (a) dışa aktar + klasör izleme | 2 gün | Yüksek; bayatlık riski rozetle görünür | Temiz: zaten indirdiğin dosya. KVKK: yerel kopya için veri işleme onayı (§6.2) | Yerel işleme onayı |
| **2 (sonra)** | (b) köprü eklentisi, 30 dk | 3 gün + uç keşfi 0,5 gün | Orta: ekran değişince bozulur, bozulunca görünür | Kullanıcı oturumuyla otomatik rapor çağrısı: **yazılı BT onayı şart**, sıklık sınırı | Eklenti izni (allowlist), sıklık onayı, DevTools/Brave kararı |
| 3 (hedef) | (c) rapor API'si ya da zamanlanmış rapor | 1 gün (klasör yolu) | En yüksek | En temiz: servis hesabı, IP kısıtı, BT logu | Salt okunur API ya da saatlik rapor teslimi (SFTP/paylaşım), "kapanan işler" dahil |

### 2.2 Fox (foxsaha.global-bilgi.entp) — Turkcell iş emrinin ilk düştüğü yer

| | |
|---|---|
| **Ne lazım** | Akış No, Akış Tipi (TICKETYENI / TICKET2YENI), Task Adı, Başlangıç, Atanma Zamanı, Akış Statüsü, Adım Statüsü, Kalan Süre, Hedef SL, Ürün, Müşteri İl/İlçe, Kanal. **Alınmayan:** Akışı Başlatan, Üstlenen (kişi adı). |
| **Neden gerekli** | (1) **Yalnız Fox'ta olan iş türleri:** Donanım Teslimat Şikayet 25, BTK Şikayet 5, Bayi Kanal İnceleme 4, Kurulum Taskı Ürememiş 4, BTK/Mahkeme 1 ve diğerleri, toplam 56 iş. (2) **Turkcell'in kendi SL hedefi** (TV arıza 6 sa, bağlantı 12 sa, BTK/Mahkeme 4 sa) ve `Kalan Süre`. (3) Askı durumunun Turkcell tarafındaki doğrusu. |
| **Yön** | Okuma. Fox'ta kapatılan kayıtlar için yazma elle, giden kutusundan. |
| **Sıklık** | Günde 2–4 kez. **Açık ve Askı dosyası aynı anda** (15 dk içinde) alınmalı. Tek dosya gelirse askıya geçen iş "kapandı" sanılır (§3.5). |
| **Veri notu** | Dosya gerçek BIFF `.xls` (NPOI ile üretilmiş), `xlrd` ile okunuyor. `Kalan Süre` virgüllü metin ("-976,63" = 976,63 saat gecikme). `Hedef SL = 0` olan 834 işte (kurulum türleri) Fox SL saymıyor. Müşteri İl/İlçe %33 boş: ilçe BOSS'tan alınır. Fox'ta adres ve lokasyon yok; bina bağlama BOSS eşleşmesi ya da Müşteri No üzerinden yapılır. |

| Sıra | Yol | Emek | Güvenilirlik | Hukuk / güvenlik | BT'den |
|---|---|---|---|---|---|
| **1** | (a) iki dosya + klasör izleme | 1,5 gün | Yüksek | Temiz | Yerel işleme onayı |
| 2 | (b) köprü | 3–4 gün (ASP.NET postback'li rapor olabilir; BOSS'tan daha kırılgan) | Orta-düşük | BOSS ile aynı; ayrıca Global Bilgi'nin sistemi olduğu için onay zinciri ayrı olabilir | Global Bilgi / Turkcell BT onayı |
| 3 | (c) API ya da zamanlanmış rapor | 1 gün | Yüksek | Temiz | Açık + askı + kapanan raporu, servis hesabı |

### 2.3 OneDesk (onedeskfix.turkcell.com.tr) — ticket'lar (yalnız sen açıyorsun)

| | |
|---|---|
| **Ne lazım** | Ticket no, üst/alt ticket (takip kitabındaki `Detay`), tür (SİNYAL / EK SP / GÜZERGAH), bina (Lokasyon), bağlı Task No / Müşteri No, açılış, kanal (GLOBAL / DEHA / ARIZA / TOPTAN), durum (AÇIK / ÇÖZÜLDÜ / HATA / KAPATILDI / İPTAL), son kontrol, çözüm açıklaması. |
| **Yön** | **Yazma:** ticket'ı sen OneDesk'te açarsın. Uygulama metni hazırlar: takip kitabındaki LOCS şablonunun ("\*BTK ÇAĞRISI ACİL MÜDAHALE\* …") karşılığı; BN, Tellcordia ID, Location Id, site, öbek binadan otomatik dolar. Sen "Kopyala"ya basıp yapıştırırsın, oluşan ticket no'yu geri girersin. **Okuma:** durum. |
| **Sıklık** | Açarken + her sabah açık ticket'ların durum kontrolü (bugün 26 açık). |
| **Tetikleyiciler** | BOSS `Merkeze Gönder Statüsü` = "SİNYAL YOK" (28 iş) ya da "GÜZERGAH YOK" (35 iş) olunca uygulama otomatik "ticket önerisi" üretir. Aynı binada 3 veya daha fazla açık bağlantı arızası varsa "toplu arıza" önerisi çıkar (bugün 66 binada 3+ açık iş var). |

| Sıra | Yol | Emek | Güvenilirlik | Hukuk / güvenlik | BT'den |
|---|---|---|---|---|---|
| **1** | (a) ön-dolu metin + ticket no geri girişi; durum uygulamada elle, varsa OneDesk liste dışa aktarımı sürükle-bırak | 2 gün | Yüksek | Temiz | — |
| 2 | (b) **yer imi:** açık ticket sayfasında ekrandan ticket no ve durumu okur, uygulamaya yollar (ağ çağrısı yok, yalnız DOM) | 1 gün | Orta | Düşük risk: yalnız ekranda gördüğünü okur | Yer imi ve LNA izni |
| 3 | (c) salt okunur ticket API'si (bayi kullanıcısının açtıkları) | — | Yüksek | Temiz | API/servis hesabı |

### 2.4 ONENT ek kapasite (onent.turkcell.com.tr/Pys#AdditionalCapacityFlowNew)

| | |
|---|---|
| **Ne lazım** | Talep no, bina (Lokasyon / BN), gerekçe (BOŞ PORT YOK / talep yoğunluğu), istenen port, açılış, açan, akış adımı / durum, sonuç tarihi. Bağlı Task No'lar (bekleyen kurulum ve arızalar) ve bağlı ticket. |
| **Yön** | Yazma elle, ön-dolu. Okuma: durum. |
| **Sıklık** | Açarken + günde 1 durum. Tetik: BOSS "BOŞ PORT YOK" (18 iş), takip kitabı "EK SP" (65 kayıt), WhatsApp'tan gelen ek kapasite talepleri. |

Seçenekler OneDesk ile aynı sırada: **(a)** ön-dolu + talep no geri girişi, **(b)** DOM okuyan yer imi, **(c)** API. Not: ONENT `#` ile yönlenen bir tek sayfa uygulaması; (b) için DOM okumak, arka uç çağırmaktan daha güvenli ve kararlıdır.

### 2.5 OneMap (onemap.turkcell.com.tr → arcgis.turkcell.com.tr/…/ONEMAP/BINA/MapServer/0)

| | |
|---|---|
| **Ne lazım** | Yalnız **yeni** bina kimlikleri için: geometri (merkez + taban), ID, LOCATION_ID (BN), ENTEGRASYON_ID, ADI, SITE_ADI, BLOK_ADI, KAPI_NO, CADDE, SOKAK, MAHALLE, ILCE, KAT_ADEDI, KONUT_SAYISI, TURU, TEKNOLOJI, UAVT_BINA_KODU, MAINTAIN. Katman 88 alan taşıyor; 20 tanesi yeter. |
| **Yön** | Okuma. |
| **Sıklık** | Tur raporu yeni kimlik getirdiğinde + ayda 1 tam çekim (adres ve geometri değişikliği farkı için). |
| **Sorgu** | ArcGIS REST `query`: `where=ID IN (…)` 100'lük gruplar, `outFields=<20 alan>`, `returnGeometry=true`, `outSR=4326`, `f=json`. Yedek anahtar `LOCATION_ID IN ('BN-…')`. Tam çekimde `BAYI_NO` iki biçimde dolu ("DEHANET ECM" 10.017 bina, "44003.00001" 9.686 bina): filtre ikisini de içermeli. `ISDELETED` hep 0; silinen bina katmandan düşüyor, **kalkan bina kimlik karşılaştırmasıyla** bulunur. |

| Sıra | Yol | Emek | Güvenilirlik | Hukuk / güvenlik | BT'den |
|---|---|---|---|---|---|
| **1** | (a) **hazır sorgu adresi:** uygulama yeni kimlikler için sorgu adresini üretir. Sen oturum açık tarayıcıda tıklarsın, JSON ekranda açılır, Ctrl+S ile kaydeder ve sürüklersin. Betik yok, DevTools yok. | 1 gün | Yüksek | Temiz: tarayıcıda bir adres açmak | — |
| 2 | (b) köprü (bugünkü çekimin kalıcı hâli), ayda 1 tam çekim | 1 gün | Orta | Brave/DevTools sorusu (§2.0) | Eklenti izni |
| 3 | (c) ArcGIS servis hesabı ya da jeton, salt okunur, bayi filtresi | 0,5 gün | Yüksek | Temiz | ArcGIS erişimi |

### 2.6 Tur raporu (data.xlsx, ORIGN sayfası)

| | |
|---|---|
| **Ne lazım** | ORIGN'in 31 kolonu (bugün `dsale/enrich.py` 28'ini kullanıyor). Takip kitabının diğer sayfaları (TICKET, GUZERGAH, ALTYAPI) **bir kez** göç edilir, sonra uygulamada yaşar. LOCS 29.590 satırlık bir formül şablonu: uygulama tek tıkla üretir. PVT bir özet: canlı rapora dönüşür. |
| **Yön** | Okuma. |
| **Sıklık** | Geldikçe (ayda 1 olduğu varsayılıyor; teyit gerekir). Akış §4'te. |

Seçenekler: **(a) 1.** sürükle-bırak → fark önizleme → onay (3 gün, §4). **(c) 2.** BT/bölge, raporu paylaşılan klasöre koyar, klasör izleyici alır. **(b) 3.** Rapor bir web portalından geliyorsa köprü yazılabilir; bugün kaynağı bilinmiyor.

### 2.7 Outlook (mail.turkcell.com.tr/owa)

| | |
|---|---|
| **Ne lazım** | Yalnız **iş doğuran** mailler: kimden/konu kalıbı, içindeki Task No, BN veya Lokasyon kodu, talep türü, alınma zamanı. Mail gövdesi saklanmaz; ayıklanan alanlar ve 300 karakterlik özet saklanır. |
| **Yön** | Okuma (yanıt yine Outlook'tan). |
| **Sıklık** | Geldikçe. Öncelik düşük: mail bir bildirim kanalı, iş kaydı değil. |
| **Teknik not** | OWA adresi şirket içi Exchange'e işaret ediyor. **Microsoft Graph şirket içi posta kutularını desteklemez**; programlı erişim EWS ile olur ve bunu ancak BT verir. |

| Sıra | Yol | Emek | Güvenilirlik | Hukuk / güvenlik | BT'den |
|---|---|---|---|---|---|
| **1** | (a) Uygulamada "Mailden talep" kutusu: konu ve gövdeyi yapıştırırsın, uygulama Task No / BN / O-kodu / 10–11 haneli müşteri no'yu ayıklar, talep kaydı açar. OWA'nın ".eml indir" çıktısı da sürüklenebilir. | 1 gün | Yüksek | Temiz | — |
| 2 | (c) Paylaşılan posta kutusu (ör. operasyon@) + kural + EWS, yalnız o kutu | 1–2 gün | Yüksek | Temiz, BT kontrolünde | Paylaşılan kutu + EWS uygulama izni |
| 3 | (b) Outlook masaüstü kuralı → "DSALE" klasörü → yerel COM ile okuma (şifre yok, kullanıcı oturumu) | 1 gün | Orta (Outlook "programlı erişim" uyarısı; politika engelleyebilir) | Orta | Programlı erişim izni |

OWA sayfasının iç çağrılarını köprüyle okumak **önerilmez**: belgesiz, kırılgan ve kişisel posta kutusunun tamamına dokunur.

### 2.8 WhatsApp (web.whatsapp.com) — "sinyal yok" ve ek kapasite talepleri

| | |
|---|---|
| **Ne lazım** | Talep türü (sinyal yok / ek kapasite / güzergah), bina, müşteri no ya da Task No, bildiren (satışçı/teknisyen), zaman, fotoğraf (isteğe bağlı). |
| **Yön** | Okuma; yanıt ve geri bildirim. |
| **Temel karar** | WhatsApp'ı **entegre etmek yerine kaynağı taşı.** Satışçılar zaten saha uygulamasını kullanıyor: bina kartına "Sinyal yok" ve "Ek kapasite" düğmeleri eklenir (bina seçili, konum otomatik, foto eklenebilir). Talep doğrudan operasyon kuyruğuna düşer, ticket/EKSP metni hazırdır. WhatsApp sohbet için kalır; iş kaydı uygulamada olur. |

| Sıra | Yol | Emek | Güvenilirlik | Hukuk / güvenlik | BT'den |
|---|---|---|---|---|---|
| **1** | (a) Uygulama içi talep formu + geçmiş için WhatsApp'ın kendi **"Sohbeti dışa aktar"** (.txt; medyasız son 40.000, medyalı son 10.000 mesaj). Aktarılan dosya içe alınır; BN-/O-kodu, Task No ve "sinyal", "ek kapasite", "port" anahtar sözcükleri ayıklanır. | 2 gün (form) + 1 gün (.txt ayrıştırıcı) | Yüksek | Temiz: WhatsApp'ın kendi özelliği. Dışa aktarılan dosyadaki kişisel veri içe alınınca silinir. | — |
| 3 | (c) WhatsApp Business Platform (Cloud API) | Yüksek | — | Meta işletme doğrulaması ve ayrı numara gerekir. **Mevcut grupları okuyamaz**; Groups API yalnız işletme numarasının kurduğu küçük gruplar için (8 katılımcı sınırı bildiriliyor). Veri Meta'ya gider (KVKK md. 9). Uygun değil. | — |
| ✗ | (b) WhatsApp Web otomasyonu | — | — | **Yasak:** WhatsApp Hizmet Şartları otomatik ve yetkisiz erişimi yasaklıyor, hesap kalıcı kapatılabilir. Ayrıca kişisel sohbetleri tarar. **Yapılmayacak.** | — |

---

## 3. İçe aktarma hattı

### 3.1 Akış

```
 dosya / köprü yükü
        │
  [1] AL ─────────── SHA-256 → daha önce görüldü mü? (evet → "zaten yüklendi", dur)
        │            karantina klasörüne kopya (7 gün sonra silinir)
  [2] TANI & DOĞRULA  kolon imzası → kaynak; zorunlu kolonlar; satır sayısı akıl kontrolü
        │            anlık görüntü zamanı; tam kapsam mı?
  [3] NORMALİZE ───── tarih (TR saati), "Kalan Süre" virgülü, görev adı → kanonik tip,
        │            kategori (kurulum/mevcut), BTK önceliği, lokasyon sıfır doldurma, maskeleme
  [4] BİNAYA BAĞLA ── lokasyon → müşterinin başka işi → adres→mahalle → yok
        │
  [5] UPSERT ──────── task_no anahtarı; alan bazında fark → is_emri_gecmis;
        │            durum değiştiyse is_emri_durum aralığı kapat/aç
  [6] KAYBOLANLAR ─── yalnız TAM KAPSAMLI anlık görüntüde: önceki görüntüde olup bunda olmayan
        │            → "kayboldu"; iki kaynakta da kaybolduysa → "kapandı"
  [7] UZLAŞTIR ────── Fox ↔ BOSS: yalnız Fox / yalnız BOSS / askı çelişkisi
        │            giden kutusu doğrulaması (randevu/atama BOSS'a işlenmiş mi?)
  [8] ÖZET ────────── "+312 yeni · 845 güncellendi · 290 kapandı · 6 çelişki · 41 bina bulunamadı"
                     veri yaşı rozeti, uyarılar; tek işlem (transaction), hata olursa hiçbir şey yazılmaz
```

Bütün adımlar tek bir SQLite işleminde (500'lük gruplarla) çalışır. Ölçüm: BOSS dosyasını okumak ~4 sn, Fox'un iki dosyası ~0,3 sn; eşleme ve upsert birkaç saniye daha. İçe aktarma arka plan iş parçacığında çalışır; saha uygulamasının okumaları bekletilmez (WAL).

### 3.2 Kaynak tanıma ve doğrulama

| Kaynak | Kolon imzası (hepsi bulunmalı) | Kapsam | Zaman damgası |
|---|---|---|---|
| `boss_acik` | Task No, Task Adı, Task Durumu, Lokasyon, Teknik Ekip SL Süresi(Dk) | Tam, eğer: Task Bitiş neredeyse boş + en eski iş 30 günden eski + satır sayısı öncekinin ±%30'u içinde | Klasör: dosya oluşma zamanı; sürükle: yükleme zamanı. Alt sınır: en yeni Task Başlangıç |
| `boss_kapanan` | Aynı imza + Task Bitiş dolu satır oranı %50'den fazla | Tarih aralığı | Aynı |
| `fox_acik` / `fox_aski` | Akış No, Akış Tipi, Kalan Süre, Hedef SL | Açık ve askı ayrımı **Akış Statüsü'nden** (ASKIDA), dosya adından değil | Aynı; iki dosya 15 dk içindeyse "Fox tam görüntü" |
| `tur` | ORIGN sayfası: Bina Serial Number, Tellcordia ID, Location Id, RES HP | Tam | Dosya zamanı |
| `onemap` | JSON `features[].attributes`: ID, LOCATION_ID, ENTEGRASYON_ID | Kısmi (yeni kimlikler) ya da tam | Çekim zamanı |

Satır sayısı öncekine göre %30'dan fazla düşerse (ör. BOSS'ta ilçe filtresi açık kalmış) görüntü **kısmi** sayılır: yeni ve güncellenen işler yazılır, **kaybolma çıkarımı yapılmaz** ve ekranda "filtreli dışa aktarım olabilir" uyarısı çıkar.

**Eski görüntü koruması:** Her satır `son_anlik` zamanını taşır. Daha eski bir dosya sonradan yüklenirse yalnız bilinmeyen işler eklenir; daha yeni bilgi ezilmez, kaybolma çıkarımı yapılmaz.

### 3.3 Normalizasyon ve görev tipi sözlüğü

`cikti/gorev_sozlugu.json` veriden üretildi: 33 Fox adı, eşleştiği BOSS adları, kanonik kod, aile, kurulum kuralı, BTK önceliği ve Turkcell hedef SL'si. Sözlük veritabanında `gorev_tipi` tablosu olur ve yönetici ekranından düzenlenir. İçe aktarmada **tanımsız bir ad** gelirse iş durmaz: kural uygulanır ("kurulum" geçiyorsa kurulum) ve "yeni görev adı: sınıflandırın" uyarısı çıkar.

| Aile | Fox adı → BOSS adı | Turkcell hedef SL | BTK önceliği |
|---|---|---|---|
| Bağlantı | Bağlantı Problemleri → Bağlantı Problemi (236) · Arıza Bildirim → Doping Arıza Bildirimi (19) | 12 sa · 24 sa | Evet |
| TV | IP TV Arıza → TV+ Arıza (58) · Kanal Şikayeti (179) | **6 sa** · 24 sa | Evet · *teyit* |
| Ses | Arama Problemi (3) | 12 sa | *teyit* |
| BTK şikâyet | BTK Şikayet (5) · BTK / Mahkeme Şikayet (1) — **yalnız Fox** | 168 sa · **4 sa** | Evet, en üst |
| Cihaz | Modem / Superbox Modem / STB değişikliği | — | Hayır |
| İade | Cihaz İade Bekleniyor (218) · Cihaz Geri Alım · Turksat Cihaz İade | 24 · 48 sa | Hayır |
| Şikâyet | Donanım Teslimat Şikayet (25) · Bayi Kanal İnceleme (4) — **yalnız Fox** | 24 sa | Hayır |
| Kurulum | Quiknet Kurulum Talebi → Fiber Kurulum (+Dönüşüm/Geçiş/Nakil) · IP TV Kurulum → TV+ Kurulum · SuperBox · Kurulum ve cihaz gönderim · TT Fiber · TV Yan Oda | — | Hayır → yeni müşteri ekipleri |
| **Kural çelişkisi** | **İkinci Donanım Kurulum** (Fox'ta "kurulum" geçer) → **2.Donanım** (BOSS'ta geçmez), 125 iş | — | Kural hangi ada uygulanırsa sonuç değişir: **karar senin** |

Kurallar:
- `kategori` Fox adından hesaplanır, çünkü kullanıcı kuralı Fox başlıklarıyla konuşuluyor. Tek istisna çelişkili satırdır; orada sözlükteki karar geçerlidir.
- **Bayi SL'si her iş için 24 saattir** (senin kuralın). Turkcell hedefi ayrıca saklanır: TV arıza için Turkcell'in 6 saati bayinin 24 saatinden sıkı ve öncelik algoritması bunu bilmeli.

### 3.4 İdempotent upsert

- **Dosya düzeyi:** Aynı SHA-256 ikinci kez gelirse hiçbir şey yazılmaz.
- **Satır düzeyi:** `INSERT … ON CONFLICT(task_no) DO UPDATE`, ama önce **izlenen alanların özeti** (`ozet_hash`) karşılaştırılır. Aynıysa yalnız `son_gorulme_*` güncellenir. Farklıysa her değişen alan için `is_emri_gecmis` satırı yazılır.
- **İzlenen alanlar:** boss_durum, fox_akis_statu, fox_liste (açık/askı), randevu_durum/bas/bit, aski_nedeni, merkeze_gonder, ekip, teknisyen, konum_paylasma, ise_baslama, bitirme, boss_bitis, sl_boss, fox_kalan_saat (yalnız işaret değişimi: SL aşıldı), son_aciklama.
- **Kaynak kolonları ayrı tutulur:** BOSS'tan gelen `boss_durum` ile Fox'tan gelen `fox_akis_statu` birbirini ezmez. Birleşik görünüm bir SQL görünümüdür (`v_is_emri`).

### 3.5 Değişiklik tespiti: yeni, güncellenen, kaybolan, yeniden açılan

| Olay | Koşul |
|---|---|
| `yeni` | task_no ilk kez görüldü (herhangi bir kaynakta) |
| `alan_degisti` | izlenen alan değişti (eski → yeni) |
| `kayboldu_boss` | önceki **tam** BOSS açık görüntüsünde vardı, bu tam görüntüde yok |
| `kayboldu_fox` | önceki **tam Fox görüntüsünde (açık + askı birlikte)** vardı, bunda yok |
| `kapandi` | kaynaklarının hepsinde kayboldu, ya da `boss_kapanan` raporunda Task Bitiş geldi (kesin zaman) |
| `yeniden_acildi` | kapandı sayılan iş yeniden açık listede. Kalite göstergesi: aynı iş iki kez gidilmiş demek |

**Fox tuzağı:** Açıktan askıya geçen iş açık dosyadan çıkar, askı dosyasına girer. İki dosya birlikte değerlendirilmezse bu hareket "kapandı" sanılır. Bu yüzden Fox kaybolması yalnız iki dosyanın birleşimi üzerinden çıkarılır.

### 3.6 Geçmiş ve gerçek SLA

- `is_emri_durum` her durum için bir **aralık** tutar: `(task_no, durum, bas, bit)`. Buradan "işler Açık'ta ortalama kaç saat, Merkeze Gönderildi'de kaç saat bekliyor" sorusu cevaplanır.
- **Kapanış zamanı**, öncelik sırasıyla: `boss_kapanan` raporundaki Task Bitiş (kesin) → Teknik Ekip Bitirme → kaybolma tahmini. Kaybolma tahmini, son görülme ile ilk görülmeme arasının ortasıdır. Hata payı senkron aralığının yarısı: 30 dakikalık köprüyle ±15 dk, günde 3 kez elle yüklemede ±2 saat. **Bu yüzden günlük "dün kapananlar" raporu önemli:** SLA'yı kesinleştirir.
- **Gerçek SLA** = kapanış − Task Başlangıç (Fox Başlangıç ile medyan fark 7 sn). "Askıda geçen süre hariç" metriği ayrı hesaplanır; hangisinin resmî sayılacağı Turkcell tanımına bağlı.
- Bugünkü tablo (yalnız açık işler): BOSS "SL Geçti" 1.498 / "Geçmedi" 463 / boş 606. BOSS'un SL süresi medyanı 88 saat. Fox'ta SL'si aşılmış 928 iş; aşım medyanı 70 saat, p90 14 gün.

### 3.7 Fox ↔ BOSS uzlaştırma kuralları

| Durum | Bugün | Kural | Kime |
|---|---|---|---|
| Ortak | 2.561 | Normal. Saha durumu BOSS'tan, SL ve askı doğrusu Fox'tan | — |
| **Yalnız Fox** | 56 (açık 22, askı 34; yaş medyanı 4,7 gün) | Bu iş türleri BOSS'a düşmüyor. "Yalnız Fox" rozetiyle listelenir; BTK şikâyetleri listenin **en üstünde**. Fox'ta çalışılır. | Operasyon (sen) |
| Yalnız BOSS | 6 (4 Başlandı, 2 Açık) | Fox'ta kapanmış ya da taşınmış olabilir. "BOSS'ta kontrol et / kapat" listesi | Operasyon |
| Fox askıda, BOSS değil | 78 | Çelişki listesi. Teknisyene gönderilmeden önce kontrol edilir: askıdaki işe boşuna gidilmesin | Operasyon |
| BOSS askıda, Fox açık | 2 | Çelişki listesi. Turkcell tarafında SL işliyor olabilir, BTK riski | Operasyon |
| Müşteri No uyuşmazlığı | 0 (%100 tutarlı) | Görülürse veri hatası uyarısı | — |

### 3.8 Binaya bağlama (katmanlı)

1. **Lokasyon:** `Lokasyon` yalnız rakamsa 8 haneye sıfırla doldurulur, "O…" ile başlıyorsa olduğu gibi kalır. Sonra `bina.location_id` (aynı kurala göre normalize) ile eşleştirilir. **%58,3** (1.496 iş, dolu Lokasyon'un %98,7'si).
2. **Aynı müşterinin başka işi:** Müşteri No aynı ve o iş binaya bağlıysa. **+98 iş → %62,1.** Fox-only işler de böyle bağlanır (56'nın 19'unun müşterisi BOSS'ta var, 11'i binaya bağlanabiliyor).
3. **Adres → mahalle:** BOSS adresi yapılı ("… Mah. … Sk. No: D:"; %99,8'inde "Mah", %97'sinde "No" var). İlk basit denemede mahalle adı OneMap mahalle listesiyle %60–67 eşleşiyor; iyileştirilebilir. Mahalle merkezi rota için yaklaşık konum verir (`bina_eslesme='mahalle'`).
4. **Yok:** Harita dışı liste; ilçe seviyesinde gruplanır.

Not: Superbox (385), ADSL (194) ve TT Fiber (130) işlerinde Lokasyon **doğası gereği yok**: bunlar bizim fiber binalarımız değil. Bu işler için hedef bina değil **mahalle/koordinat**. Dışarıdan geocoding servisi kullanılmaz: adres Turkcell dışına çıkmaz.

**Mevcut koddaki etki (düzeltme önerisi, salt okunur olduğumuz için uygulanmadı):** `dsale/enrich.py`, `location_id`'yi tur raporundan sıfırları atılmış olarak alıyor. Bu yüzden `saha.db` → `bina.location_id` 2.335 binada BOSS'la eşleşmiyor ve yönetici "Ayrıntılar" penceresi bu binalarda yanlış biçimi gösteriyor. Düzeltme: enrich'te aynı `lokasyon_norm` kuralı, ya da doğrudan OneMap `ENTEGRASYON_ID` kullanmak (19.706 binada dolu ve doğru biçimde).

### 3.9 Giden kutusu: Turkcell sistemlerine yazılacaklar

Bizim sistem Turkcell'e yazmaz ama **yazılması gerekeni unutturmaz**:

| İşlem | Hedef | Oluşunca | Doğrulama (sonraki içe aktarmada otomatik) |
|---|---|---|---|
| Teknisyene ata | BOSS | Operasyon ya da algoritma günlük atamayı yaptı | BOSS `Ekip` = atanan teknisyenin BOSS adı |
| Randevu gir | BOSS | Arama "randevu alındı" | BOSS `Randevu Başlangıç` ±30 dk |
| Askıya al (abone kaynaklı) | BOSS/Fox | Arama "müşteri istemiyor / yok" | BOSS `Askıya Alınma Nedeni` dolu, Fox askı dosyasında |
| Kapat | BOSS | Teknisyen "tamamlandı" dedi | İş açık listeden kayboldu ya da kapananlar raporunda |
| Ticket aç | OneDesk | Sinyal yok / güzergah önerisi onaylandı | Ticket no girildi |
| EKSP aç | ONENT | Boş port yok önerisi onaylandı | Talep no girildi |

Her satırın durumu: `bekliyor → yapıldı (elle işaret) → doğrulandı (içe aktarma)`. 2 saatten uzun "yapıldı ama doğrulanmadı" kalan işler kırmızıya döner: ya işlenmemiştir ya yanlış işlenmiştir.

Bunun bir yararı daha var: BOSS saha alanları kullanılmadığı için (konum/başlama %7), teknisyenin uygulamada bastığı "başladım / bitirdim" düğmeleri **gerçek saha zamanlarını** verir; BOSS'a yalnız resmî kapanış işlenir. Böylece çift veri girişi olmaz.

### 3.10 Senkron sağlığı ekranı

Her kaynak için tek satır: son veri zamanı, yöntem, satır sayısı, yeni/güncellenen/kapanan sayıları, uyarılar, rozet (yeşil/sarı/kırmızı). Eşikler: BOSS 2/4 saat, Fox 6/12 saat, OneDesk/ONENT durumu 24/48 saat, tur raporu 45/60 gün. Kırmızı rozet, öncelik listesinin üstünde "bu liste X saatlik veriye dayanıyor" şeridi gösterir.

---

## 4. Tur raporu ve OneMap yenileme

### 4.1 Bugünkü durum

- PS26 ORIGN ile `data/raw/data.xlsx` **birebir aynı**. Gerçek bir yenileme henüz yaşanmadı; hat ilk gerçek yenilemede **önizleme modunda** denenecek.
- Tur raporunda 1 tekrar eden Bina Serial var; enrich en büyük HP'li satırı tutuyor. Bu davranış korunmalı.
- **Mevcut kodda yenilemeyi bozacak 4 nokta** (düzeltilmedi, not edildi):
  1. `saha/kur.py` tazelemede `bolge=excluded.bolge` yazıyor. `bolge.py` yeniden çalıştırılırsa **bütün bölgeler sessizce yeniden dağılır** ve satışçıların binaları değişir.
  2. Koordinatı olmayan yeni bina `lat NOT NULL` yüzünden **sessizce atlanıyor**: yeni bina sistemde hiç görünmez.
  3. Tur raporundan kalkan bina `bina` tablosundan hiç düşmüyor ve işaretlenmiyor.
  4. `api.py` → `_harita_sabiti` önbelleği yalnız **bina sayısı** değişince tazeleniyor. Bir bina kalkıp bir bina eklenirse sayı aynı kalır ve harita yeniden başlatılana kadar **yanlış ad ve konum** gösterir. Anahtara bina sürüm numarası eklenmeli.

### 4.2 Yenileme akışı

```
yeni data.xlsx ─► [şema kontrolü] ─► [FARK: aktif sürüme karşı]
                                        ├─ yeni bina   (Bina Serial yok)          → OneMap listesi
                                        ├─ kalkan bina (artık yok)                → aktif=0 (silinmez)
                                        ├─ değişen     (HP, aktif abone, ad, öbek, sales ready …)
                                        └─ kimlik değişimi (aynı BN, farklı Tellcordia/Location Id) → uyarı
      ─► [OneMap: YALNIZ yeni kimlikler]  hazır sorgu adresi (§2.5) → JSON → koordinat + adres
      ─► [bölge ataması: kararlı kurallar §4.4]
      ─► [ÖNİZLEME RAPORU]  +12 bina · −3 bina · RES HP +418 · 2 bölgede sapma %1,4 → %1,9 · 0 satışçı değişimi
      ─► [ONAY] (yönetici)  ─► tek işlemde uygula ─► veri_surumu kaydı ─► harita önbelleği tazelenir
      ─► [GERİ AL] bir önceki sürüme dönüş (bina_gecmis'ten)
```

- **Eşleştirme sırası** mevcut yaklaşımın aynısı: `Tellcordia ID = OneMap ID`, yoksa `Bina Serial = LOCATION_ID`. 19 Eylül çekiminde %100 tuttu.
- **HP değişimleri** yalnız yükü değiştirir, bölgeyi değiştirmez. Bölge yük sapması canlı izlenir.
- **Ziyaret, görev ve iş emri geçmişi hiçbir yenilemede silinmez.** Kalkan bina `aktif=0` olur; geçmişi ve raporları durur.

### 4.3 OneMap artımlı çekim

- `LAST_EDITED_DATE` seçici değil (§0, madde 9). Artımlı çekim **ID listesiyle** yapılır.
- **Ayda bir tam çekim:** Her binanın ilgili 20 alanı için özet (hash) tutulur, yalnız değişenler güncellenir (adres, kat, konut sayısı, geometri). Tam çekim bugünkü yöntemle 19.706 kayıttır; köprü varsa gece değil **mesai içinde, senin oturumunla** yapılır.
- Kalkan bina: tam çekimde ID yoksa "OneMap'te yok" işareti konur. Tur raporundan da kalkmadıkça aktif kalır; ikisi çelişirse uyarı verilir.

### 4.4 Bölge kararlılığı kuralları

Mevcut atamalar **kutsaldır**. Yalnız yeni binalar atanır:

1. Aynı `site_grup`'ta atanmış bina varsa → o bölge (site bütünlüğü; algoritma zaten site gruplarıyla çalışıyor).
2. Değilse, bina bir bölge poligonunun içindeyse → o bölge (`bolgeler.json` poligonları).
3. Değilse, en yakın 5 atanmış binanın çoğunluk bölgesi. Eşitlikte yükü (RES HP) en düşük bölge.
4. Atama nedeni kaydedilir: `bolge_kaynagi = 'yeni_bina_otomatik'`. Yönetici tek binayı elle taşıyabilir (`'elle'`).

**Denge izleme:** Her bölgenin hedeften sapması canlı gösterilir (bugün −%0,02 / +%0,06). ±%3 aşılırsa **"yeniden dengeleme önerisi"** çıkar. Bu **en az taşımalı** bir önerme olmalı: yalnız sınır site grupları taşınır. Rapor: kaç bina, hangi bölgeden hangisine, RES HP, etkilenen satışçı, açık görev ve randevular. Öneri **yalnız açık onayla** uygulanır.

(Bugünkü `partition.bolgele` sıfırdan böler. "Mevcut atamadan en az sapma" kipi için algoritmaya bir hareket cezası eklenmesi gerekir; bu ayrı bir geliştirme.)

### 4.5 Sürümleme

- `veri_surumu`: her tur ve OneMap yüklemesi için satır (dosya SHA, tarih, bina sayısı, RES HP toplamı, yeni/kalkan/değişen sayıları, durum `onizleme | uygulandi | geri_alindi`, fark raporu JSON).
- `bina_gecmis`: alan bazında eski ve yeni değer.
- `bolge_plani` + `bina_bolge_gecmis`: hangi bina hangi tarihten hangi tarihe hangi bölgedeydi. Kapsama ve satış raporları doğru döneme bağlanır.
- Ham dosya `data/raw/arsiv/2026-09-29_data.xlsx` olarak saklanır: git dışı, şifreli disk.

### 4.6 Statik Excel yerine canlı görünüm

`Bursa_8_Satisci_Bolgeleme.xlsx` 10 sayfalık bir anlık görüntü (OZET, PERSONEL_ATAMA, BOLGE_DETAY, BINA_ATAMA 19.706 satır, ILCE/MAHALLE_MATRIS, METODOLOJI, VERI_KALITESI, PARAMETRELER, LISTE). Yerine:

- **Yönetici konsolunda "Bölgeler" sayfası:** bölge kartları (bina, RES HP, aktif, fırsat, sapma, kapsama %, satışçı, açık iş emri, açık altyapı engeli), harita poligonları, ilçe/mahalle matrisi, filtreler ve arama. Kaynak doğrudan `saha.db` olduğu için ziyaret, satış, tur yenilemesi ve atama değişince görünüm hemen güncellenir.
- **"Excel indir" düğmesi:** Aynı 10 sayfa, `dsale/excel_report.py` yeniden kullanılarak ama veritabanından üretilir. Her sayfada veri sürümü damgası ("Tur 2026-09-19 · OneMap 2026-09-19 · Plan N=8 CCPD-2.5"). Uç: `GET /api/dosya/bolgeleme.xlsx`.
- Bina "Ayrıntılar" penceresi binaya bağlı **açık iş emri, ticket, EKSP ve altyapı engeli** sayılarını da gösterir (anahtar: normalize `location_id`).

### 4.7 "Sistemden anlık veri çekilebilir mi?" — dürüst cevap

- **Bugün (BT'siz):** Veri, son dışa aktarım kadar tazedir. Klasör izleme dışa aktarımdan saniyeler sonra ekrana getirir; "anlık" olan dışa aktarımın kendisidir.
- **Köprüyle:** 30 dakikalık gecikmeyle neredeyse anlık, ama yalnız senin tarayıcın açık ve oturumun geçerliyken.
- **Gerçek anlık** yalnız (c) ile: Turkcell BT'nin verdiği API ya da rapor teslimi.

Tasarım üçünde de aynı çalıştığı için bugünden başlamak bir şey kaybettirmez.

---

## 5. Mimari

### 5.1 Karar: mevcut `saha/` sunucusu genişletilsin (ayrı servis değil)

| Ölçüt | `saha/` genişletme | Ayrı servis |
|---|---|---|
| Ortak veri | `bina` tablosu, `location_id`, bölge, harita **aynı yerde**; iş emri binaya JOIN ile bağlanır | Bina verisi iki kopya, senkron derdi |
| Giriş | Tek uygulama: girişte **Satış / Operasyon / Teknik** seçimi, aynı PIN sistemi | İki hesap, iki şifre |
| İşletme | Tek bilgisayar, tek `baslat.bat`, tek yedek, tek log | İki süreç, iki yedek |
| Çapraz fayda | Satışçının "sinyal yok" talebi → operasyon kuyruğu → teknisyen; altyapı engeli satış haritasında görünür | API ile köprü yazmak gerekir |
| Yük | Günde ~300 yeni iş, ~2.600 açık, senkron başına ~200 değişiklik: SQLite WAL için önemsiz | — |
| Risk | Tek hata noktası. Önlem: içe aktarma ayrı iş parçacığında ve kısa işlemlerle; modüller ayrı klasörde | Ayrıştırma kolay |

**Ayrı servis ancak şu durumda:** Turkcell BT sistemi kendi sunucusunda barındırmak isterse ya da operasyon, saha uygulaması kapalıyken de çalışmak zorundaysa. Modül sınırı buna göre çizilir, sonradan ayırmak kolay olur.

### 5.2 Modül yapısı

```
saha/
  operasyon/
    __init__.py
    sema.py          # ek tablolar + göçler (db.gocler deseniyle, her adım kendi başına güvenli)
    sozluk.py        # gorev_tipi: gorev_sozlugu.json ile tohumlanır
    normalize.py     # lokasyon_norm, kalan_sure, maskeleme, kategori
    esleme.py        # binaya bağlama katmanları
    ice_aktar/       # boss.py · fox.py · tur.py · onemap.py · whatsapp_txt.py · ortak.py (imza, SHA, işlem)
    uzlastirma.py    # Fox↔BOSS, giden kutusu doğrulaması
    izleyici.py      # klasör izleme (arka plan iş parçacığı, 5 sn yoklama; ek paket gerekmez)
    api_op.py        # APIRouter(prefix="/api/op") → api.py'de uygulama.include_router(...)
    rapor_op.py      # günlük SLA, çelişki, senkron raporu (Excel)
```

### 5.3 Veri modeli ekleri

```sql
-- Kullanıcı rolleri: CHECK (rol IN ('satisci','yonetici')) genişler.
-- SQLite CHECK değişmez: db.gocler içinde ziyaret tablosundaki gibi yeniden kurulur.
--   rol IN ('satisci','yonetici','operasyon','teknisyen')

CREATE TABLE kaynak_senkron (                       -- her içe aktarma
  id INTEGER PRIMARY KEY, kaynak TEXT NOT NULL,     -- boss_acik|boss_kapanan|fox_acik|fox_aski|tur|onemap|onedesk|onent|whatsapp_txt|mail
  yontem TEXT NOT NULL,                             -- surukle|klasor|kopru|api
  dosya_adi TEXT, dosya_sha256 TEXT UNIQUE, anlik_zamani TEXT NOT NULL, yukleme_zamani TEXT NOT NULL,
  yukleyen_id INTEGER REFERENCES kullanici(id), satir INTEGER, yeni INTEGER, guncellenen INTEGER,
  kaybolan INTEGER, yeniden_acilan INTEGER, binasiz INTEGER, tam_kapsam INTEGER NOT NULL DEFAULT 0,
  durum TEXT NOT NULL, uyari TEXT);

CREATE TABLE gorev_tipi (
  kod TEXT PRIMARY KEY, fox_adi TEXT UNIQUE, boss_adlari TEXT,        -- JSON dizi
  aile TEXT, kategori TEXT CHECK (kategori IN ('kurulum','mevcut')), btk INTEGER NOT NULL DEFAULT 0,
  turkcell_sl_saat INTEGER, bayi_sl_saat INTEGER NOT NULL DEFAULT 24,
  sorumlu_birim TEXT, yalniz_fox INTEGER NOT NULL DEFAULT 0, aktif INTEGER NOT NULL DEFAULT 1);

CREATE TABLE is_emri (                               -- işin GÜNCEL hâli (task_no = Fox Akış No)
  task_no INTEGER PRIMARY KEY, musteri_no TEXT, musteri_ad_maske TEXT,
  gorev_kodu TEXT REFERENCES gorev_tipi(kod), boss_adi TEXT, fox_adi TEXT,
  kategori TEXT, btk INTEGER, urun TEXT, segment TEXT, hiz TEXT, satis_kanali TEXT,
  il TEXT, ilce TEXT, mahalle TEXT,
  location_id TEXT, bina_serial TEXT REFERENCES bina(bina_serial),
  bina_eslesme TEXT,                                 -- lokasyon|musteri|mahalle|yok
  adres_tam TEXT,                                    -- yalnız bina_serial NULL ise; kapanış+30 gün silinir
  acilis TEXT NOT NULL, fox_atanma TEXT, bayi_sl_bitis TEXT, turkcell_sl_saat INTEGER, fox_kalan_saat REAL,
  boss_durum TEXT, fox_akis_statu TEXT, fox_adim_statu TEXT, fox_liste TEXT,   -- fox_liste: acik|aski
  randevu_durum TEXT, randevu_bas TEXT, randevu_bit TEXT, aski_nedeni TEXT, merkeze_gonder TEXT,
  ekip TEXT, teknisyen_id INTEGER REFERENCES teknisyen(id),
  konum_paylasma TEXT, ise_baslama TEXT, bitirme TEXT, boss_bitis TEXT, sl_boss TEXT, sl_boss_saat REAL,
  son_aciklama TEXT,
  kaynak_boss INTEGER NOT NULL DEFAULT 0, kaynak_fox INTEGER NOT NULL DEFAULT 0,
  uzlasma TEXT,                                      -- ortak|yalniz_fox|yalniz_boss|aski_celiski
  ilk_gorulme TEXT NOT NULL, son_gorulme_boss TEXT, son_gorulme_fox TEXT, son_anlik TEXT,
  acik INTEGER NOT NULL DEFAULT 1, kapanis TEXT, kapanis_kaynagi TEXT,        -- boss_bitis|kayboldu|elle
  yeniden_acilma INTEGER NOT NULL DEFAULT 0, ozet_hash TEXT, guncelleme TEXT);
CREATE INDEX ix_is_acik ON is_emri(acik, kategori, btk);
CREATE INDEX ix_is_bina ON is_emri(bina_serial);
CREATE INDEX ix_is_musteri ON is_emri(musteri_no);

CREATE TABLE is_emri_gecmis (                        -- yalnız eklenir, asla güncellenmez
  id INTEGER PRIMARY KEY, task_no INTEGER NOT NULL, senkron_id INTEGER REFERENCES kaynak_senkron(id),
  zaman TEXT NOT NULL, olay TEXT NOT NULL,           -- yeni|alan_degisti|kayboldu_boss|kayboldu_fox|kapandi|yeniden_acildi
  alan TEXT, eski TEXT, yeni TEXT);
CREATE INDEX ix_gecmis_task ON is_emri_gecmis(task_no, zaman);

CREATE TABLE is_emri_durum (                         -- durumda geçen süre
  task_no INTEGER NOT NULL, kaynak TEXT NOT NULL, durum TEXT NOT NULL, bas TEXT NOT NULL, bit TEXT,
  PRIMARY KEY (task_no, kaynak, bas));

CREATE TABLE teknisyen (
  id INTEGER PRIMARY KEY, kullanici_id INTEGER REFERENCES kullanici(id),
  boss_ekip_adi TEXT UNIQUE,                         -- BOSS "Ekip" ile eşleşme anahtarı
  ilce_tabani TEXT, yetkinlik TEXT, gunluk_kapasite INTEGER, aktif INTEGER NOT NULL DEFAULT 1);

CREATE TABLE arama (                                 -- her arama denemesi (telefon numarası TUTULMAZ)
  id INTEGER PRIMARY KEY, offline_id TEXT NOT NULL, task_no INTEGER NOT NULL, kullanici_id INTEGER NOT NULL,
  zaman TEXT NOT NULL, sonuc TEXT NOT NULL,          -- ulasildi_randevu|ulasilamadi|mesgul|numara_hatali|
                                                     -- telefonla_cozuldu|iptal_istedi|tekrar_ara
  sonraki_arama TEXT, notu TEXT, UNIQUE (kullanici_id, offline_id));

CREATE TABLE randevu (
  id INTEGER PRIMARY KEY, task_no INTEGER NOT NULL, bas TEXT NOT NULL, bit TEXT, kaynak TEXT,  -- uygulama|boss
  durum TEXT NOT NULL DEFAULT 'planli',              -- planli|gerceklesti|kacti|iptal
  olusturan_id INTEGER, olusturma TEXT, boss_dogrulandi TEXT);

CREATE TABLE gunluk_atama (
  id INTEGER PRIMARY KEY, tarih TEXT NOT NULL, task_no INTEGER NOT NULL, teknisyen_id INTEGER NOT NULL,
  sira INTEGER, durum TEXT NOT NULL DEFAULT 'atandi',-- atandi|yolda|basladi|bitti|ulasilamadi|iade
  kaynak TEXT,                                       -- algoritma|operasyon
  basladi TEXT, bitti TEXT, lat REAL, lon REAL, boss_dogrulandi TEXT, UNIQUE (tarih, task_no));

CREATE TABLE ticket (                                -- OneDesk
  id INTEGER PRIMARY KEY, ticket_no TEXT UNIQUE, ust_ticket_no TEXT, tur TEXT,   -- sinyal|ek_sp|guzergah|diger
  bina_serial TEXT, location_id TEXT, musteri_no TEXT, kanal TEXT, acilis TEXT, acan_id INTEGER,
  durum TEXT,                                        -- acik|cozuldu|hata|kapatildi|iptal
  son_kontrol TEXT, cozum TEXT, metin TEXT, kaynak TEXT);  -- uygulama|excel_gocu
CREATE TABLE ticket_is (ticket_id INTEGER, task_no INTEGER, PRIMARY KEY (ticket_id, task_no));

CREATE TABLE eksp_talebi (                           -- ONENT ek kapasite
  id INTEGER PRIMARY KEY, talep_no TEXT UNIQUE, bina_serial TEXT, location_id TEXT, gerekce TEXT,
  istenen_port INTEGER, acilis TEXT, acan_id INTEGER, durum TEXT, onent_adim TEXT,
  son_kontrol TEXT, sonuc_tarihi TEXT, notu TEXT);
CREATE TABLE eksp_is (eksp_id INTEGER, task_no INTEGER, PRIMARY KEY (eksp_id, task_no));

CREATE TABLE altyapi_engeli (                        -- binaya bağlı engel: satış haritası da görür
  id INTEGER PRIMARY KEY, tur TEXT NOT NULL,         -- guzergah_yok|sinyal_yok|bos_port_yok|altyapi_yok
  bina_serial TEXT, location_id TEXT, musteri_no TEXT,
  kaynak TEXT,                                       -- boss_merkeze_gonder|excel_gocu|saha|whatsapp|mail
  ilk_tespit TEXT, durum TEXT NOT NULL DEFAULT 'acik', ticket_id INTEGER, eksp_id INTEGER, kapanis TEXT);

CREATE TABLE talep (                                 -- WhatsApp / mail / telefon / saha uygulaması girişi
  id INTEGER PRIMARY KEY, kanal TEXT NOT NULL, gelis TEXT NOT NULL, giren_id INTEGER, bildiren TEXT,
  konu TEXT, bina_serial TEXT, task_no INTEGER, musteri_no TEXT, ozet TEXT,   -- ≤300 karakter
  durum TEXT NOT NULL DEFAULT 'yeni', ticket_id INTEGER, eksp_id INTEGER, altyapi_id INTEGER);

CREATE TABLE dis_islem (                             -- giden kutusu (§3.9)
  id INTEGER PRIMARY KEY, hedef TEXT NOT NULL,       -- boss|fox|onedesk|onent
  islem TEXT NOT NULL,                               -- ata|randevu|askiya_al|kapat|ticket_ac|eksp_ac
  task_no INTEGER, ticket_id INTEGER, eksp_id INTEGER, veri TEXT,  -- JSON: ön-dolu metin
  olusturan_id INTEGER, olusturma TEXT NOT NULL, yapan_id INTEGER, yapildi TEXT, dogrulandi TEXT,
  durum TEXT NOT NULL DEFAULT 'bekliyor');           -- bekliyor|yapildi|dogrulandi|iptal

-- Bina sürümleme ve bölge kararlılığı
ALTER TABLE bina ADD COLUMN aktif INTEGER NOT NULL DEFAULT 1;
ALTER TABLE bina ADD COLUMN kaldirilma TEXT;
ALTER TABLE bina ADD COLUMN ilk_surum INTEGER;
ALTER TABLE bina ADD COLUMN son_surum INTEGER;
ALTER TABLE bina ADD COLUMN bolge_kaynagi TEXT;       -- plan|yeni_bina_otomatik|elle
ALTER TABLE bina ADD COLUMN location_id_norm TEXT;    -- sıfır doldurulmuş anahtar (BOSS eşleşmesi)
CREATE INDEX ix_bina_locnorm ON bina(location_id_norm);
CREATE TABLE veri_surumu (id INTEGER PRIMARY KEY, kaynak TEXT, dosya_sha256 TEXT, tarih TEXT, yukleme TEXT,
  bina INTEGER, res_hp INTEGER, yeni INTEGER, kalkan INTEGER, degisen INTEGER, durum TEXT, rapor TEXT);
CREATE TABLE bina_gecmis (bina_serial TEXT, surum_id INTEGER, alan TEXT, eski TEXT, yeni TEXT);
CREATE TABLE bolge_plani (id INTEGER PRIMARY KEY, n INTEGER, olcu TEXT, algoritma TEXT, olusturma TEXT,
  aktif INTEGER, aciklama TEXT);
CREATE TABLE bina_bolge_gecmis (bina_serial TEXT, plan_id INTEGER, bolge INTEGER, bas TEXT, bit TEXT, neden TEXT);
```

Takip kitabı göçü (tek seferlik, `kaynak='excel_gocu'`): TICKET 197 kayıt → `ticket`; GUZERGAH 64 kayıt → `altyapi_engeli(tur='guzergah_yok')`; ALTYAPI 67 kayıt → `altyapi_engeli(tur='altyapi_yok')`. Lokasyon eşleşmesi TICKET'ta %97,4, GUZERGAH'ta %98,4.

### 5.4 API uçları (`/api/op`, Bearer jeton, rol denetimli)

| Uç | Rol | İş |
|---|---|---|
| `POST /api/op/ice-aktar` (dosya) | operasyon, yönetici | Kaynağı tanır, hattı çalıştırır, özet döner. `?onizleme=1` ile yazmadan fark gösterir |
| `POST /api/op/kopru/{kaynak}` | yalnız `127.0.0.1` + yerel köprü anahtarı | Köprü yükü. Turkcell kimlik bilgisi değil, bu PC'ye özel rastgele anahtar |
| `GET /api/op/senkron` | operasyon | Kaynak sağlığı, son yüklemeler |
| `GET /api/op/is-emri?kategori=&btk=&durum=&ilce=&teknisyen=&sl=asan` | operasyon | Liste (maskeli) |
| `GET /api/op/is-emri/{task_no}` | operasyon; teknisyen yalnız kendi işini görür | Zaman çizelgesi: geçmiş, durum aralıkları, aramalar, randevular, ticket |
| `POST /api/op/arama` · `POST /api/op/randevu` · `POST /api/op/atama` | operasyon | Idempotent (`offline_id`); giden kutusuna satır düşer |
| `POST /api/op/teknik/durum` | teknisyen | yolda / başladım / bitirdim / ulaşamadım (konumlu) |
| `POST /api/op/talep` | satışçı, teknisyen, operasyon | "Sinyal yok", "ek kapasite" (bina kartından) |
| `POST /api/op/ticket` · `POST /api/op/eksp` | operasyon | Ön-dolu metin üret, no'yu kaydet |
| `GET /api/op/uzlasma` | operasyon | Yalnız Fox, yalnız BOSS, askı çelişkisi, doğrulanmamış giden işlemler |
| `POST /api/op/tur/onizle` · `POST /api/op/tur/uygula` · `POST /api/op/tur/geri-al` | yönetici | §4 |
| `GET /api/op/onemap/sorgu-adresi` | yönetici | Yeni kimlikler için hazır ArcGIS sorgu adresleri |
| `GET /api/dosya/bolgeleme.xlsx` · `GET /api/dosya/operasyon.xlsx?tarih=` | yönetici | İsteğe bağlı Excel |

### 5.5 Roller ve kişisel veri görünürlüğü

| Rol | Görür | Görmez |
|---|---|---|
| Satış | Bina, bölge, kendi talepleri, binadaki **altyapı engeli** (satışı yönlendirir) | İş emri müşteri bilgisi |
| Operasyon | Bütün iş emirleri (maskeli ad, müşteri no, Task No), aramalar, uzlaştırma, giden kutusu | Telefon (sistemde yok) |
| Teknik | Yalnız kendi günlük atamaları: adres ya da bina, iş tipi, randevu saati | Başkalarının işleri, müşteri no |
| Yönetici | Hepsi + içe aktarma, tur yenileme, bölge | — |

### 5.6 Kapasite ve saklama

- **Hacim:** ~300 yeni iş/gün. Senkron başına ~150–250 alan değişikliği; 30 dakikalık köprüyle günde ~5–8 bin geçmiş satırı, yılda ~2–3 milyon satır (~300–500 MB).
- **Saklama:** 180 günden eski `is_emri_gecmis` günlük özetlere sıkıştırılır. Kapanmış işte `adres_tam` 30 gün sonra, ham dosyalar 7 gün sonra silinir. Kapalı işler için Müşteri No 1 yıl sonra özetlenir (Turkcell'in saklama politikasıyla hizalanmalı).
- `saha/yedek/` artık müşteri verisi içerecek: yedeklerin **şifreli** olması (BitLocker ya da şifreli arşiv) ve 30 günden eskilerinin silinmesi gerekir.

### 5.7 Uzaktan erişim artık engelleyici

Satış tarafında "ofis wifi'sinde çalışır, sahada kuyruğa yazar" kabul edilebilirdi. **Teknik ekip için değil:** teknisyen gün boyu sahada, atamasını ve randevu saatini canlı görmeli. `docs/SAHA_KULLANIM.md` §9'daki karar (Cloudflare Tunnel / şirket VPN / sabit IP) artık teknik modülün ön koşulu.

- Öneri: **şirket VPN'i**. Veri Turkcell ağından çıkmaz.
- Cloudflare Tunnel trafiği yurt dışındaki bir firmanın ağından geçirir. Müşteri verisi için KVKK md. 9 sorusu doğurur.
- Hangisi seçilirse seçilsin önce HTTPS.

---

## 6. İstenecekler

### 6.1 Senden (kullanıcı)

1. BOSS rapor ekranında **tarih aralığıyla "kapanan işler"** raporu alınabiliyor mu (Task Bitiş dolu)? Filtreler neler? Dışa aktarılan dosyada filtre bilgisi yazıyor mu?
2. Fox'ta kapanan kayıt raporu var mı? Fox'ta kayıtları kim kapatıyor?
3. **Görev sınıflandırması:** 2.Donanım / İkinci Donanım Kurulum (125 iş) ve TV Yan Oda Kurulum (29) hangi ekibin? Kanal Şikayeti (179) ve Arama Problemi BTK önceliğinde mi?
4. **PS26 deposu** (github.com/oceanseace/PS26) herkese açık mı, GitHub Pages açık mı? (§6.3)
5. OneDesk'te ve ONENT'te "listeyi Excel'e aktar" var mı? Ticket ve talep numarası biçimi ne?
6. Teknisyen listesi: BOSS "Ekip" adı ↔ kişi ↔ ilçe ↔ uzmanlık (bugün açık işlerde 37 farklı ekip adı var; toplam ~65 kişi).
7. BOSS'ta Task No ile işi doğrudan açan bir adres (derin bağlantı) var mı? Arama ekranında "BOSS'ta aç" düğmesi için.
8. Fox "Atanma Zamanı" ilk atamayı mı, son atamayı mı gösteriyor? (%10'unda başlangıçtan 39 saatten fazla sonra.)
9. WhatsApp'tan günde kaç talep geliyor, hangi gruplardan? Satışçılar bu talepleri saha uygulamasından girmeye geçebilir mi?
10. Hangi mailler iş doğuruyor (gönderen ve konu kalıpları)?
11. Tur raporu ne sıklıkla, kimden, hangi yolla geliyor?

### 6.2 BT'den (hazır talep metni)

> **Konu:** Dehanet EÇM – bayi operasyon takip aracı için veri erişimi ve güvenlik onayı
>
> 1. **Yerel veri işleme onayı:** Ofis bilgisayarında çalışan yerel bir takip uygulaması, BOSS ve Fox iş emri dışa aktarımlarını (Task No, iş tipi, durum, zaman, lokasyon, müşteri no; **telefon hariç**, adres kısıtlı) işleyecek. Amaç: iş emirlerinin 24 saat içinde kapanmasını takip. Veri bilgisayardan çıkmaz, disk şifreli, yedekler şifreli, saklama süreleri tanımlı. KVKK veri işleyen yükümlülükleri çerçevesinde onayınızı rica ederiz.
> 2. **Rapor teslimi (tercih edilen):** BOSS "Teknik Task Detay" raporunun (açık + önceki gün kapananlar) saatlik olarak bayiye özel bir paylaşım klasörüne veya SFTP'ye bırakılması; Fox açık/askı/kapanan raporları için de aynısı. Ya da salt okunur, IP kısıtlı bir rapor API'si ve servis hesabı.
> 3. **Bu olana kadar:** Kullanıcının kendi tarayıcı oturumunda, rapor ekranının kendi "dışa aktar" isteğini saatte en fazla 2 kez tetikleyen yerel bir tarayıcı eklentisine izin (şifre ve çerez okumaz, dışarı veri göndermez). Chrome'da eklenti izin listesi; Brave kullanımı hakkında görüşünüz.
> 4. **OneMap / ArcGIS:** Bayi binaları için salt okunur sorgu erişimi (servis hesabı ya da jeton).
> 5. **Posta:** Operasyon için paylaşılan posta kutusu ve yalnız o kutuya EWS erişimi (isteğe bağlı).
> 6. **Uzaktan erişim:** Teknisyenlerin sahadan uygulamaya bağlanması için şirket VPN'i (ya da onaylı bir alternatif) ve HTTPS sertifikası.
> 7. **Disk şifreleme:** Ofis bilgisayarında BitLocker'ın açık olduğunun teyidi.

### 6.3 ACİL — PS26'nın GitHub yayını

`PS26/guncelle.bat` her güncellemede `data/` klasörünü `github.com/oceanseace/PS26` deposuna itiyor ve GitHub Pages'te yayınlıyor. Klasörde şunlar var:
- `ORIGN.json` (tur raporu, 19.707 bina, 5 MB)
- `LOCS.json` (11 MB)
- `TICKET.json` (müşteri no'lu)
- `GUZERGAH.json`, `ALTYAPI.json` (müşteri no, satıcı adı)

GitHub Pages siteleri depo özel olsa bile varsayılan olarak herkese açıktır; erişim denetimi yalnız GitHub Enterprise Cloud'da var. Bu hem ticari sır hem kişisel veri, hem de yurt dışına aktarım (KVKK md. 9) sorunu.

Öneri, sırasıyla:
1. Pages'i hemen kapat, depoyu özel yap.
2. `guncelle.bat` içindeki `git push` adımını kaldır.
3. Geçmiş commit'lerde veri kaldığı için BT/güvenlik ile nasıl temizleneceğini konuş.
4. Harita ihtiyacı artık saha uygulamasının yönetici haritasından karşılanır (bina adı + "Ayrıntılar" penceresinde location_id ve Tellcordia ID zaten var).

*Bu belgede hiçbir dosya değiştirilmedi. Karar ve uygulama senin.*

---

## 7. Yol haritası

| Faz | Süre | İş | Bağımlılık |
|---|---|---|---|
| 0 | Bugün | PS26 yayınını kapat (§6.3); BT'ye §6.2 metnini gönder; §6.1 sorularını cevapla | — |
| 1 | 1. hafta | Şema + göç; görev sözlüğü; BOSS ve Fox içe aktarma (sürükle-bırak + klasör izleme); binaya bağlama (sıfır doldurma dahil); uzlaştırma listesi; senkron sağlığı ekranı; takip kitabı göçü | Yerel işleme onayı |
| 2 | 2. hafta | Arama, randevu ve atama kayıtları + giden kutusu doğrulaması; ticket ve EKSP ön-dolu metin; talep formu (saha uygulaması bina kartı); günlük "kapananlar" ile gerçek SLA | §6.1 madde 1–3 cevapları |
| 3 | 3. hafta | Tur raporu fark/önizleme/onay hattı; OneMap hazır sorgu adresi; kararlı bölge ataması; canlı "Bölgeler" görünümü + Excel indir; `kur.py` ve harita önbelleği riskleri | İlk gerçek tur yenilemesi |
| 4 | BT onayıyla | Köprü eklentisi: önce BOSS 30 dk, sonra Fox ve OneMap | Eklenti izni |
| 5 | BT projesi | Zamanlanmış rapor ya da API → klasör yolu değişir, kod aynı kalır | Turkcell BT |

---

**Kaynaklar (genel teknoloji belgeleri):**
[ArcGIS REST Query (Map Service/Layer)](https://developers.arcgis.com/rest/services-reference/enterprise/query-map-service-layer/) ·
[Esri — Date-time queries](https://www.esri.com/arcgis-blog/products/api-rest/data-management/querying-feature-services-date-time-queries) ·
[Chrome — Local Network Access izni](https://developer.chrome.com/blog/local-network-access) ·
[WhatsApp — Sohbet dışa aktarma](https://faq.whatsapp.com/1180414079177245/?cms_platform=android) ·
[WhatsApp — Resmî olmayan uygulamalar](https://faq.whatsapp.com/1217634902127718) ·
[WhatsApp Hizmet Şartları](https://www.whatsapp.com/legal/terms-of-service) ·
[Meta — WhatsApp Groups API](https://developers.facebook.com/documentation/business-messaging/whatsapp/groups) ·
[Microsoft — Hibrit Exchange'de REST desteği](https://learn.microsoft.com/en-us/graph/hybrid-rest-support) ·
[GitHub — Pages görünürlüğü (Enterprise Cloud)](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site) ·
[GitHub Changelog — Pages erişim denetimi](https://github.blog/changelog/2021-01-21-access-control-for-github-pages/)
