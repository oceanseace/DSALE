# Turkcell Superonline Süreç Bilgisi (Dehanet EÇM için derleme)

Derleme tarihi: 30.09.2026. Kaynaklar: extrajet.turkcell.com.tr (Superonline "Evim İçin"), atmosfer.turkcell.com.tr. Pusulaev okunamadı (giriş gerekli).
Yöntem: yalnız okuma. Hiçbir form gönderilmedi, dosya indirilmedi, PDF/Office ekleri açılmadı (başlık + yol kaydedildi).
Kişisel veri (müşteri, çalışan adı, kişisel e-posta, telefon) bu dosyaya alınmadı. Yalnız unvan, ekip kodu ve adet var.

Güven düzeyi: **kesin** = sayfada açıkça yazıyor · **muhtemel** = birden çok sayfadan çıkarım · **belirsiz** = doküman netleştirmiyor.

Kısaltmalar: IB = Inbound (çağrı merkezi), BO = Backoffice (Global Bilgi), GB = Global Bilgi, EÇM/FÇM/DÇM = Ev/Fiber/DSL Çözüm Merkezi (bayi), SD = Satış Destek,
TÇS = Tahmini Çözüm Süresi, TÇM = Tüketici Çözüm Merkezi (BTK kurum incelemesi), BÇO = Bölge Çözüm Ortağı, KDH/BDH = Bayi Destek Hattı, ÜTS = Ücretli Teknik Servis,
SL/SLA = hizmet süresi, WG = workgroup (ekip havuzu), Solid = teknik teşhis iş akışı aracı, Maya = SOL CRM.

---

## 1. Arıza / iş emri akışı: FOX ↔ BOSS

### 1.1 Sistemlerin rolü
| Sistem | Ne | Kim kullanıyor | Güven |
|---|---|---|---|
| **FOX** (`foxapp.global-bilgi.entp`) | Global Bilgi'nin akış (task) sistemi. Ana akış, alt akış, BTK Şikayeti formu, askı yan barı, alarm akışları, notlar burada. | IB/BO (Global Bilgi), TÇM, Riskli Müşteri (Prosentez) ekibi. EÇM kullanıcılarına da Atmosfer "Platformlar" altında link verilmiş. | kesin (sistem), muhtemel (bayi erişimi) |
| **BOSS** (`boss.superonline.net`) | Superonline saha/bayi sistemi. D2D ön satış lead'i, randevu ataması, teknik ekibin araması, "Talep Ulaşamama SMS", TÇS alanı, task kapama. | EÇM satış, satış destek, teknik ekipler (mobil BOSS) | kesin |
| **Maya / SOL CRM** | Müşteri, sipariş, SR/teşhis; "Modem Değişim" butonu, "Modem Downgrade", "Task sorgu", "Önceliklendir" butonu | IB, BO, bayi | kesin |
| **Solid** | Teknik teşhis iş akışları (İnternete Giremiyorum, Yayın Problemi vb.); task'a otomatik bilgi ekler | IB, BO | kesin |
| **OneDesk** | ICT/Network/ROD çağrı (ticket) sistemi | BO, bayi (ek kapasite ROD talebi, WiFi6 modem sorunları) | kesin |
| **OneNT** | Altyapı/port; "Protokol Yönetimi > Akışlar > Yeni > Ek Kapasite" | BO, bayi | kesin |
| **ONE MAP, MAYA SAHA** | Harita / saha CRM (Atmosfer platform listesinde) | bayi | kesin (link), açıklama yok |

Kaynak: Atmosfer "Platformlar" (https://atmosfer.turkcell.com.tr/platforms); Ev Çözüm Merkezi sayfası; Kanal Şikayeti SSS 40; Atmosfer sinyali #7414635.

### 1.2 Şikayetten saha taskına
1. Müşteri CC'yi arar; IB Maya'da **hizmet talebi yarat** ekranından SR açar, teşhis seçer. Teknik kontroller **Solid** iş akışıyla yapılır. (kesin — BTK Faz 2 "SOL Inbound Task Açma Süreci" sekmesi; Fiber Gpon İnternete Giremiyorum)
2. Aynı çağrıda aynı ürün + aynı konu için **yalnız 1 şikayet SR'ı** açılabilir. Aynı SR'dan açık task varsa ikincisi açılmaz, akışa not düşülür. "Bayide ise SL süresi geçmiş ise kırmızı hat süreci işletilmelidir." (kesin — BTK Faz 2, 02.03.2026)
3. Teşhise göre task ya **BO Teknik**'e (FOX) ya da **doğrudan sahaya (Entegratör = bayi)** gider:
   - "ONT Sinyal Problemi requesti üzerinde açılan Bağlantı Problemleri taskı **direk Entegratör'e** gider." Ekip çözünce taskı BO Teknik'e geri gönderir, BO müşteriyi arayıp teyit eder; sorun sürüyorsa yeniden entegratöre. (kesin — ONT Sinyal Problemi, 04.11.2025)
   - IB modemi arızalı bulursa (elektrik yok, adaptör, kayıp, kırık) "İnternete Giremiyorum" akışında cihaz arızası seçilir; task **bölgeye FÇM/DÇM'ye** düşer, bayi ekip gönderip cihazı değiştirir; bayi dönüşü akış BO'ya döner, BO rutin kontrol yapar. (kesin — Arızalı Cihaz Değişikliği, 15.09.2026)
   - BO Teknik, müşteriyle görüşmeden ve tüm kontrolleri yapmadan sahaya task yönlendirmez; "sadece ekip gitsin diye" task açılmaz; hız sorununda kanal değişikliği ile düzeliyorsa task açılmaz. (kesin — Sahaya İletilen Tasklar, v8 04.09.2020)
4. BO tarafı IP alamama tasklarında önce **L1**, çözülmezse **L2**'ye eskale eder; Layer2 NOK ise Turkuaz ekibine. (kesin — Fiber Gpon İnternete Giremiyorum, 30.09.2024)
5. TV+ BO karar ağacı (kesin — TV+ Ev Teknik Destek, 28.04.2026):
   - ONT sinyali −12…−27 dBm **dışında** → **sahaya** (L1'e değil); aralıkta → L1.
   - STB-modem haberleşmiyor → saha; haberleşiyor ama sorun sürüyor → NW L1.
   - Açılış 1. adım → saha; 2. adım IP yok → VLAN103 + NW L1; 3-6. adım → NW L1; Amino geri sarma → saha.
   - Solid ONT sinyal seviyesinde sorun bulduysa: ilk aramada ulaşılamasa bile **2. arama beklenmeden** task ekibe iletilir.
6. BO teknik tasklarda (WAN portunda sinyal yok, ONT sinyal problemi, modem buluşmuyor, IP alamama) müşteri **en az 2 saat kesintisiz** bağlıysa task SMS ile kapatılabilir; son 24 saatte 6+ kopma varsa SMS ile kapatılmaz. (kesin — Teknik Taskı Olan Müşteri Desteği, 12.11.2024) BTK tarafında bu kapama "Çözüldü, müşteriden çözüm teyidi alınmadı" kodudur (BTK Faz 2 SSS 21).

### 1.3 Hangi iş FOX'ta kalır, hangisi BOSS'a (sahaya) iner
| İş | Nerede | Güven |
|---|---|---|
| Bağlantı Problemi (ONT sinyal problemi teşhisi) | Doğrudan saha (BOSS) | kesin |
| Modem/adaptör arızası, kayıp/kırık modem, STB/Superbox cihaz değişimi | Saha (FÇM/DÇM) | kesin |
| ÜTS (ücretli teknik servis: kablolama, modem yer değişikliği, yeni cihaz kurulumu) | Saha; bayi 24 saat içinde müşteriyle iletişime geçer | kesin |
| (560) Modem Değişim taskı (WiFi6/Ultra Fiber) | Saha | kesin |
| Kurulum, nakil, 2. donanım teslimatı (kurye projesi hariç), GPON dönüşüm, sosyal destek evrak toplama | Saha | kesin |
| Cihaz İade Bekleniyor / Cihaz Geri Alım | Bayi (elden) veya OMSAN (kargo) | kesin |
| 40 – Kanal Şikayeti (randevuya gidilmedi, arıza çözülmeden kapatıldı, cihaz değişmedi, tavır…) | Doğrudan bayiye atanır | kesin |
| 944 – Bayi Kanal İnceleme (hatalı kampanya, eksik evrak, hatalı devir) | GB BO inceler, bayiye en fazla 2 alt akış (48 s + 24 s) | kesin |
| BTK şikayet ana akışı, reopen, BTK formu, TÇS, bilgi/belge, ara bilgilendirme | FOX (BO); saha alt akış olarak katılır ve TÇS girebilir | kesin |
| Kurum incelemesi (btk.gov.tr'den gelen) | FOX, TÇM (Acil Servis) ekibi | kesin |
| Fatura itirazı, finansal talepler, iyileştirme aksiyonu, hızlı müdahale (957), riskli müşteri callback (960) | FOX (fiziksel iş yok) | kesin |
| IP alamama L1/L2, TV+ NW/ICT izleme | FOX → OneDesk (L1/L2/ICT) | kesin |
| ATA (iptal teyit araması) | EÇM satışında ATA arama kanalı **EÇM** (DSL, TT Fiber, Vodafone, Kablo; SOL Fiber yok) | kesin |

Kaynaklar: Kanal Şikayeti (…/mevcut-musteri-upsell/kanal-sikayeti.aspx), Fiber ÜTS (…/fiber-saha-ucretli-teknik-servis-kurgusu.aspx, 05.02.2026), ATA Süreci (…/genel-icerik/ata-sureci-abone-teyit-aramalari.aspx, 26.11.2024), Riskli Müşteri (…/riskli-musteri-sikayet-yonetimi.aspx, 31.07.2026).

### 1.4 Kanal şikayeti (bayi aleyhine)
Kaynak: **Kanal Şikayeti** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/mevcut-musteri-upsell/kanal-sikayeti.aspx (güncelleme tarihi sayfada yok; ekler 2024-2025). Güven: kesin.
- Satış kanalları: EÇM, KÇM, TİM, DSN, DSN Plus, DSN Ekstra, Telesales. Şikayet kanalları: CC, web, sosyal medya, şikayet siteleri, resmi kurumlar, BTK, THH.
- **944 Bayi Kanal İnceleme**: önce GB BO inceler; bayiden **2 kez** açıklama ister (1. alt akış **48 saat**, 2. alt akış **24 saat**). Bayi süresinde dönmezse "hatalı kabul edilebilir", müşteri lehine aksiyon alınır. Müşteri haklıysa finansal aksiyon için bayiden alınan açıklama yeterli, iade otomatik onaylanır ve **bayiden rücu** edilir. Hatalı bayiye gönderilirse bayi "hatalı bayi" der, sayaç yeni bayide sıfırlanır.
- **40 Kanal Şikayeti** (doğrudan bayiye): kurulum taskı **48 saat** geçtiği halde randevu alınmadı/kuruluma gidilmedi; arıza taskı **24 saat** geçtiği halde randevu alınmadı; randevu saatinde gidilmedi (SL içi/dışı fark etmez); kurulum yapılamadı; **arıza çözülmeden task kapatıldı**; cihaz değişimi yapılmadı; fiziki zarar; kurulum veya satış çalışanının tavrı.
- **SL içindeyse kanal şikayeti açılmaz**: müşteriye SL bilgisi verilir, task sorgu yapılır; kriz müşteride kırmızı hat.
- SSS 21: bayiye düşen kurulum, arıza ve şikayet tasklarında bayi müşteriyi **3 saat arayla toplam 2 kez** arar, her ulaşamamada **SMS** gönderir (CRM'de görünür). Randevu tarih/saati task'a not olarak girilir. SMS gönderilmemişse kanal şikayeti açılır.
- SSS 37 (WiFi6 modem): bayi sorunu **OneDesk ile takip edip çözene kadar taskı askıda bekletmeli**, çözünce kapatmalı. Kapatıp müşteriye ücret çıkarırsa bayi hatası. "**2x2 arama süreci**" (sahanın CEM ekipleriyle mutabık kaldığı) task içinde görünüyorsa ve ulaşılamamışsa ücrete müşteri memnuniyeti adına müdahale edilir.
- SSS 47 (2. donanım): stok yoksa diğer bayiden transfer (en fazla 1 ay); **task iptal edilmez, askıya alınır**, ara bilgilendirme yapılır. İptal edilirse müşteri otomatik cihazsız kampanyaya geçer → bayi hatası.
- SSS 27: teknik şikayet taskında ücretli işlem yapılırsa **hizmet formu zorunlu**; nüsha müşteriye verilir.
- SSS 53: bayi müşterinin mağduriyetini **kendisi ödeyemez** (elden/IBAN yasak); fatura müdahalesini genel müdürlük yapar.
- Bayide açık task'a not → mutlaka **BAYIHIZLANDIRMA** not tipi.
- Görüşmeler **Webphone** dışında yapılamaz/kaydedilemez; webphone kaydı yoksa müşteri lehine karar.

---

## 2. BTK kuralları

### 2.1 BTK Faz 2 şikayet yönetmeliği
Kaynak: **BTK Faz 2 Şikayet Süreçleri** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/mevcut-musteri-upsell/btk-faz-2-sikayet-surecleri.aspx (başlangıç 07.02.2021, güncelleme 02.03.2026) ve Atmosfer sinyali **#7414635 "BTK Şikayet Süreleri ve TÇS Hatırlatması"** (17.09.2026). Güven: kesin.
- **Tüm kanallardan gelen tüm şikayet taskları BTK'ya raporlanır.** Görev: ilk şikayet (sıfır/ana akış) **10 iş günü** içinde çözülür. Kapandıktan sonraki 10 iş günü içinde aynı konu tekrar gelirse **reopen**, süre **5 iş günü**. En fazla 2 reopen; sonra yeni sıfır akış veya btk.gov.tr.
- Süre **uçtan uca**; akışa dokunan tüm kanallar sorumlu. Atmosfer: "BÇO, network veya farklı bir ekipten aksiyon bekleniyor olsa dahi, şikayetin takibi ve müşterinin doğru bilgilendirilmesine ilişkin süreç sorumluluğumuz devam etmektedir."
- 12 BTK kategorisi: Abonelik_İşlemleri, **Bağlantı_Hız_Hizmet_Kalitesi**, Diğer, Faturalandırma, Fesih_Geçici_Durdurma, İşletmeci_Değişikliği, Katma_Değerli_Hizmetler, Nakil_Devir_İşlemleri, Taahhütname_Cezai_Şart_Cayma_Bedeli, Tarifeler_Kampanyalar, Veri_Gizliliği, Yanlış_Eksik_Bilgilendirme.
- **BTK bildirimi yapılmış şikayet taskı manuel iptal edilmez.** Hatalı başlık → yeni task açılır, eskisi "birleştirme nedeniyle" otomatik kapanır.
- Kapama (BTK yanıt tipi): "Çözüldü, müşteriden çözüm teyidi alındı" / "Çözüldü, teyit alınmadı" (SMS ile kapama, müşteri aranmak istemiyor) / "**Müşteriye ulaşılamadı**" (ispat yükü işletmede).
- **Alarm akışı**: sıfır akışta SL'nin **8. ve 10. iş günü**, reopen'da **3. ve 5. iş günü** otomatik üretilir. Birinci seviye ve alt akışta bekleyenler için ilgili ekiplere otomatik mail gider.
- **TÇS (Ek Süre İlet)**: SL içinde çözülemeyecekse **bir kez** girilebilir, sonradan değiştirilemez; SL içindeki bir tarih seçilemez. TÇS girilince akış **BTK'da "Kapalı"** görünür, FOX'ta süreç sürer. Alt akış yapılan ekipler (ICT, Network, Finans, **Saha (Bayi)**, Kalite…) TÇS girebilir; BO'ya alarm akışı üretilir. Atmosfer: TÇS "**BOSS/FOX ekranlarında**" girilir; varsayımsal/gelişigüzel tarih girilmez, çözüm beklenen ekipten güncel tarih alınır.
- PROFX (otomatik memnuniyet araması): 1 = sorun yok → COMPLETED; 2 = sorun devam → BO'ya atanır (BTK "13 MT Ara Bilgilendirme"); 3 tuşlama yok / 4 ulaşılamadı → COMPLETED (BTK 17 ulaşılamadı).
- "DSL Arıza BTK Bildirim" akışı sadece bilgi taskıdır (TT'ye arıza kaydı açılınca BTK'ya bildirim gider), işlem gerekmez.

### 2.2 Hangi işler "BTK'ya sayılır"
- Kesin olan: **şikayet tipindeki tüm tasklar** BTK'ya raporlanır ve 12 kategoriden birine bağlanır. Bağlantı problemi → "Bağlantı_Hız_Hizmet_Kalitesi". (kesin)
- İşlem tipi task (ör. BDH "Bayi Finansal Talepler") için ayrı SL var: Global SL 72, BTK SL 96 (birim muhtemelen saat). (kesin tablo, birim belirsiz)
- **"TV 6 saat, bağlantı 12 saat" hedefi hiçbir okunan sayfada bulunamadı.** (belirsiz) Bulunan saha süreleri:
  - Kırmızı Hat sayfasındaki **EÇM SLA** tablosu: Şikayet **24 saat**, Kurulum **2–4 gün**, Arıza **24 saat**, Donanım teslimat **8 iş günü**. (kesin — Kırmızı Hat Süreci, 23.09.2026)
  - Fiber ve DSL **Bağlantı Problemi task SLA 24 saat**. (kesin — Arızalı Cihaz Değişikliği)
  - TT Fiber: TT'ye açılan arıza SL **24 saat**, sahaya giden bağlantı problemi akışı **48 saat**. (kesin — TT Fiber Teknik Süreçler, 03.01.2025)
  - "Önceliklendir" butonu (Maya, bireysel şikayet): kalan SL Black/Platinum/Sosyal Medya için **2 saate**, diğerleri **5 saate** iner (müşteriyle paylaşılmaz). (kesin, ama sayfa 2018)
  - Modem değişikliği SL **7 gün**; kanal şikayeti bu süre geçtikten sonra açılır. (kesin — Modem Değişim Süreci SSS 10)
  - 6/12 saat değerleri muhtemelen indirilebilir **"Güncel SR & Task SLA Listesi.xlsx"** (03.05.2026) içinde; okunamadı (bkz. Okunamayanlar).

### 2.3 BTK saati ve askı
Güven notu: Dokümanlar **"BTK saati durur"** ifadesini açıkça kullanmıyor. Mekanizma şöyle:
- **Bilgi & Belge butonu** (FOX BTK formu): müşteriden bilgi/belge istenirse akış otomatik **10 gün "BTK Süreci Kaynaklı"** askıya alınır. Müşteriye otomatik SMS gider, müşterinin **10 iş günü** süresi başlar (reopen'da da 10 iş günü; SSS 17'de reopen için 5 iş günü denmiş, çelişkili). Bilgi gelmezse akış otomatik kapanır. Müşteri not/OİM ile dönünce akış **otomatik askıdan düşer**. Butonsuz bu nedenle askıya alma sistemce engellenir. (kesin)
- SSS 20: müşteri 4-5 gün müsait değilse ("müşteriden kaynaklı bekleme") akış **"müşteriden bilgi/belge bekleniyor"** olarak askıya alınır. (kesin) → Abone kaynaklı beklemenin BTK'ya karşı resmi yolu budur. (muhtemel: bu süre BTK süresinden düşer)
- SSS 23: müşteri hastalık/karantina gibi nedenle uzun süre müsait değilse **TÇS** girilir. (kesin)
- "BTK Şikayet Taskları **Evinde Yok**" ve "BTK Şikayet Taskları **Ulaşılamadı**" askı nedenleri: önce BTK formundan **Ara Bilgilendirme** yapılmadan sistem askıya almaya izin vermez. Alt akış adımında (BTK formu salt okunur) askıya alınırsa alt akışı başlatana **BTK Alarm Akışı** üretilir. (kesin)
- "Çözüm Süresi Öteleme" askı nedeni + TÇS → BTK alarm akışı → Ek Süre İlet. (kesin)
- **Abone kaynaklı / TT kaynaklı** askı nedenleri Backoffice Askı Kurallarında tanımlı (bkz. 2.4). Bunların BTK 10 iş günü süresini durdurup durdurmadığı yazmıyor. (belirsiz) Ancak EÇM askı kuralları "askıya alınmaz = süre işlemeye devam eder" mantığıyla yazılmış; yani abone kaynaklı askı **task SL saatini** durduruyor. (muhtemel)
- Riskli müşteri: task "doğru ekiplerin reason'ı ile" askıya alınmalı (Global Bilgi'de bekliyorsa GB reason'ı, ICT'de bekliyorsa ICT reason'ı). (kesin)

### 2.4 İzinli askı nedenleri ve kanıt
Kaynak: **Backoffice Askı Kullanım Kuralları** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/genel-icerik/backoffice-aski-kullanim-kurallari.aspx?menuid=137 (güncelleme 10.11.2025). Aynı "EÇM – Abone Kaynaklı Askı Kullanımı" sekmesi **Ev Çözüm Merkezi** sayfasında da var (29.04.2026). Güven: kesin.

| Neden | Ne zaman | Süre / şart |
|---|---|---|
| **Abone kaynaklı** | Müşteriye ulaşılamıyor veya müşteri talebiyle bekletme | **Fiber teknik ekip max 4 gün**, diğer ekipler max 2 gün |
| Abone kaynaklı **akşam araması** | Müşteri akşam aranmak istiyor | 18:00 ve sonrası; askıdan düşünce kullanıcıya değil **havuza öncelikli** atanır |
| Sistem problemi | Maya, Decoder gibi Turkcell sistemleri | — |
| Operasyon (Global) kaynaklı | FOX/Atix kaynaklı arama yapılamaması, fatura onay adımı | — |
| ICT | OneDesk açılamıyor / form çıkmıyor, manuel kayıt | — |
| Superonline kaynaklı | Extrajet'te bilgi yok, SOL kontağına iletilen konu; **22:00 sonrası arama yapılmaz**, ertesi 09:00'a alınan geri dönüş | — |
| **TT kaynaklı** | TT'den sorgulama yapıldı veya TT provizyonu bekleniyor | — |
| BTK Süreci Kaynaklı | Bilgi & Belge butonu ile otomatik | 10 gün |
| Genel arıza (SOL kaynaklı) | Genel arıza öncesi açılmış fiber task; verimlilik ekibine sorgu sırasında | Arıza bitene kadar (TV+ Ev Teknik SSS 3) |

Kanıt: "Akışların bir maile ya da bilgilendirmeye istinaden askıya alınması durumunda mutlaka ilgili doküman **Dosya alanına** eklenmelidir." (kesin)

**EÇM abone kaynaklı askı senaryoları** (kesin):
1. Randevu için arandı, ulaşılamadı → **alınabilir**. Şartlar: arama **Webphone**'dan; ilk aramadan sonra "arandınız, ulaşılamadı" SMS'i; **2 farklı günde** arama.
2. Bayi saat önerdi, müşteri kabul etti → **alınamaz** (bayi kaynaklı öteleme SL'i durdurmaz).
3. Bayi saat önerdi, müşteri reddetti, bayi daha ileri bir saat önerdi, müşteri kabul etti → **kısmi**: yalnız bayinin ilk önerdiği saat ile nihai randevu arasındaki süre (ör. 11:00–16:00). Randevu saatinde askıdan düşürülür.
4. Müşteri daha ileri saat önerdi, bayi kabul etti → aynı kısmi kural.
5. Webphone dışı arama → **alınamaz**.

---

## 3. Müşteriye ulaşma, randevu, ulaşılamama

### 3.1 EÇM Müşteri Arama Kuralları (bizim için en bağlayıcı kaynak)
Kaynak: **Ev Çözüm Merkezi** → "Müşteri Arama Kuralları" sekmesi — http://extrajet.turkcell.com.tr/superonline/Pages/genel/genel-icerik/ev-cozum-merkezi.aspx (başlangıç 17.02.2025, güncelleme 29.04.2026). Güven: kesin.
- Kapsam: teyit, kurulum/arıza randevusu, şikayet, dönüşüm dahil **tüm müşteri aramaları**.
- Saat: **10:00–18:00**. Bayi yönetimi 20:00'ye uzatabilir.
- İlk ve ikinci arama arasında **en az 3 saat**.
- Ulaşılamazsa her task için **2. gün en az 1 arama zorunlu**.
- Her arama **en az 30–35 sn (~6 çalma)**. Meşgul/kapalı anonsu en az 5 sn dinlenir. Meşgul/kapalı/ulaşılamıyor = 1 arama sayılır. "Dıt" sesiyle düşen (engelli) numara en az 2 kez aranır.
- 3. aramada da ulaşılamazsa **en az 3 saat sonra** yeniden aranır.
- Müşteri müsait değilse uygun saati öğrenilir, 3. arama olsa bile tekrar aranır. Sonra aranmak isterse task **talep ettiği tarih/saate kadar abone kaynaklı askıya** alınır, ATA havuzuna atılmaz.
- Ulaşılamayan durumda bir sonraki arama zamanına kadar task **abone kaynaklı askıya** alınabilir.
- İrtibat hatalıysa task **ATA havuzuna** atanır, açıklamaya hatalı iletişim detayı yazılır. ATA'da güncel numara alınırsa o numarayla **3 arama süreci** uygulanır.
- **Her ulaşılamayan aramadan sonra BOSS'tan "Talep Ulaşamama SMS" gönderimi zorunludur.**
- Tüm aramalar **Webphone**'dan (tek numara 0532 757 5 532 görünür). İşitme engelli müşteriye yazılı kanal; yazışma task'a not.
- Webphone sonuç kodları: Satış-Teyit-Kurulum {Randevu, Red, Tekrar Ara}; Kurulum (diğer kanallar) {…}; **Genel Şikayet Akışları {Randevu, Red, Tekrar Ara}** (Bağlantı Problemi, IP TV Arıza, ÜTS, Modem/STB değişimi); GPON Dönüşüm {Kabul-Tekrar Ara, Randevu, Red, Tekrar Ara}; Diğer İşlemler.
- Randevu scripti: kendini tanıt + bayi adı, TCK anonsu (2 sabit metin), 3 kimlik teyit sorusu, adresi müşteriye söylet, **BOSS'ta randevu ataması**, TCKK PIN, kablolu TV+ bilgisi. Arıza scripti: "yerinde çözülemezse farklı destek birimine kayıt açıyoruz"; sorun SOL kaynaklı değilse ÜTS ücreti.

### 3.2 Diğer sayfalardaki (farklı) arama merdivenleri
| Kaynak | Kural | Güven |
|---|---|---|
| BTK Faz 2 (02.03.2026) | Her şikayet kaydı için **birbirini izleyen 2 gün**, farklı saatlerde, günde 2, **toplam 3 arama + 3 SMS**. SSS 22: farklı gün/saatte 4. arama da ulaşamazsa "Müşteriye ulaşılamadı" ile kapat. SSS 24: 2 farklı gün 3 arama + uygun SMS → "Müşteriye ulaşılamadı". | kesin |
| BTK Faz 2 SSS 28 | İrtibat geçersizse 1. gün task'taki ve CRM'deki numara aranır; hatalıysa task **1 gün müşteri kaynaklı askıya**; 2. gün 1 arama daha; ulaşılamazsa "Müşteriye ulaşılamadı". | kesin |
| TV+ Ev Teknik Destek (28.04.2026) | "Teknik tasklarda task kapama süreci **ilk gün 2 saat ara ile 2 arama, ikinci gün 1 arama**." Öncelik 2 günde 3 aramadır; ilk arama akşama denk gelirse 3 saat arayla 2 arama. Müşterinin aranmak istediği saat (**22:00'a kadar**) task'a yazılır. | kesin |
| Kanal Şikayeti SSS 21 | Bayi tasklarında 3 saat arayla toplam 2 arama + her aramadan sonra SMS. | kesin (daha eski kural) |
| Kanal Şikayeti SSS 37 | Saha ile CEM arasında mutabık "2x2 arama süreci". | kesin (içerik tanımsız) |
| Modem Değişim (WiFi6) | Retention sonrası modem değişim taskında bayi **4 gün, günde 2** arama yapmalı; kurala uymadan olumsuz kapatırsa bayi hatası (fatura müdahalesi). | kesin |
| ATA Süreci | Aynı gün 2 arama (17:00 sonrası ilk aramada ulaşılamazsa 2. ertesi gün); 1. ve 2. arasında 3 saat; min 30 sn; "dıt" en az 3 kez; otomatik kapama 7 gün. | kesin |
| Riskli Müşteri (Hızlı Müdahale 957) | 09:00–18:00; ulaşılamazsa 2 farklı günde, 3 saat arayla 3 arama; son arama mutlaka ertesi gün; ulaşılamazsa müşteri kaynaklı askı. | kesin |
| Kırmızı Hat | GB, bayiyi 30 dk arayla 2 kez arar; ulaşamazsa EÇM mail grubuna yazar; 3 saat yanıt yoksa 3'er saat arayla 2 mail daha; sonra Kanal Yöneticisi. | kesin |

### 3.3 "Çağrı Sonlandırma Kriterleri"
Kaynak: http://extrajet.turkcell.com.tr/superonline/Pages/genel/mevcut-musteri-upsell/cagri-sonlandirma-kriterleri.aspx (15.04.2026). Güven: kesin.
**Bu sayfa çağrı merkezinin canlı görüşmeyi nasıl bitireceğini** anlatıyor, saha "ulaşılamadı" kapanışını değil. Örnekler: bekletmede en az 1 dk beklenir; ses gelmiyorsa 1 anons sonra kapatılır; küfür/hakaret 1 uyarı sonra kapatılır (çalışana yönelikse uyarısız); konferans görüşme (teknik konular hariç) uyarı sonra kapatılır. Arama nedenleri "Task Açılmaz". Bizim araç için doğrudan kural yok.

### 3.4 Merkeze/kırmızı hatta gönderme
Kaynak: **Kırmızı Hat Süreci** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/genel-icerik/kirmizi-hat-sureci.aspx (23.09.2026). Güven: kesin.
- Devreye girer: SL'i geçmiş akış hızlandırma; üst yönetim, sosyal medya, BTK kaynaklı acil talep; hizmeti kesilmiş kriz müşteri; hızlı müdahale taskı olan kriz müşteri.
- SL **içinde**: müşteriye bilgi verilir, task'a not, kırmızı hat **aranmaz**. SL **dışında**: bayi kırmızı hat numarası aranır.
- Bayi çalışma saati **Pzt–Cmt 09:00–18:00**; Pazar ve resmi/dini tatilde kapalı. Mesai dışında kırmızı hat uygulanmaz, bayi mail grubuna yazılır.
- Mail konusu formatı: **"Task No / Task Adı / Kırmızı Hat"**; detay yoksa aksiyon alınmaz. Bekleme sebebi ve OneDesk/ONENT ticket no mutlaka yazılır.
- Dehanet: bölge **Güney Marmara**, SD mail grubu **TEAM-SOL-ECM-DEHANET**. Turkcell tarafında iki muhatap rolü var (bkz. 6.3).

---

## 4. Network eskalasyonu, OneDesk, ek kapasite, kesinti

### 4.1 BÇO ve TEAM-TAS1BRS
Kaynak: **BÇO Bilgileri** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/genel-icerik/bco-bilgileri.aspx (başlangıç 31.12.2025, güncelleme 25.02.2026). Güven: kesin.
- BÇO = **Bölge Çözüm Ortağı**: bölge operasyon ekiplerinin sahadaki operasyonel işlerini yapan, arıza ve işletme süreçlerini sahada izleyen ekipler.
- **TEAM-TAS** ile başlayan grup = BÇO; akış bu gruptaysa BÇO'da bekliyor demektir. **TEAM-TAS1BRS = Bursa** (işletmeci: Karel), TEAM-TAS1KOC = Kocaeli. Grup e-posta adresi sayfada var.
- BÇO'da **24 saati geçen** akış için **Takım Lideri**, BÇO grup adresine **OneDesk ID + müşteri no** ile mail atar. Üst yönetim/kriz müşteride süre beklemeden hızlandırılır.
- "NETWORK / GPON / SINYAL YOK / MEVCUT BINA" gibi başlık metinleri extrajet'te bulunamadı. Muhtemelen OneDesk formunun kendi kategori ağacı. (belirsiz)

### 4.2 OneDesk kuralları
Kaynak: **Onedesk (ICT) Çağrı Açma Kriterleri** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/genel-icerik/onedesk-ict-cagri-acma-kriterleri.aspx (18.03.2025). Güven: kesin.
- ŞİKAYET = SOL uygulamalarında sistem problemi; TALEP = problem dışı istek (yetki, kurulum…).
- Zorunlu içerik: müşteri no, tarih/saat görünen ekran görüntüsü (JPEG/BMP), MSISDN, **Hizmet ID**, **Modem/ONT/STB seri no** (modem değişiminde eski + yeni), hata kodu/tarih/saat, yapılan tüm işlemler.
- Müşteri kategorileri: Müşteri_Fatura; Müşteri_FIX ICT (non-teknik); **Müşteri_FIX Network (teknik)**; Müşteri_Turkcell TV_İzleme; Müşteri_Turkcell TV_abonelik; Müşteri_superesor.
- TV+: donma/mozaik/VLAN103/STB 2-4-5-6. adım → "TV NT İzleme"; login/içerik → "TV ICT İzleme". "TV+ tasklarının kapanmasında **FOX/BOSS hata veriyorsa**" hata alınan uygulama seçilerek kayıt açılır.
- ADRNIM hata kodları: 9999/9000/4006/9001/4009/9998/4008 → FIX-ICT L1; 4014/4001/4002/4003/**4004 (boş port yok)** → OneNT-Periskop L1.
- Hedef süre: ICT L1 her incident'a **24 saat içinde dokunur**; çözemezse 24 saat içinde PM açıp L2/L3'e; PM sonrası L1+L2+L3 için **12 gün** hedef.
- Genel kural (Sahaya İletilen Tasklar): OneDesk'e task içeriği kopyalanmaz, sadece problem anlatılır.

### 4.3 Ek kapasite (boş port) — OneNT / ROD
Kaynak: **Fiber Ek Kapasite (Boş Port)** — http://extrajet.turkcell.com.tr/superonline/Pages/genel/mevcut-musteri-upsell/fiber-ek-kapasite-bos-port.aspx (başlangıç 01.09.2025, güncelleme 20.10.2025). Güven: kesin.
- Taşınma, adres teyidi ve yeni satışta "boş port yok" hatasında **OneNT** üzerinden ek kapasite talebi açılır (menü: Protokol Yönetimi > Akışlar > Yeni > Ek Kapasite).
- OneNT'den açılamazsa: **bölge kurulum (ROD)** ekibine OneDesk "SOL BAYİ / GPON EK SWITCH ve SPLITTER" talebi. **Bölge yöneticisi onayı** gerekir. Önce ekteki "Boş port hataları" dokümanına bakılır.
- Ortalama karşılama **5 iş günü**, teknik yetersizlikte **+3 gün**.
- Kırmızı hat: task'ta BÇO'da bekleyen **ONENT/ONEDESK** talebi ve ticket no varsa müşterinin adresine uygun **ROD** ekibine mail atılır, **Kanal Operasyon Yöneticisi** CC'ye eklenir. (kesin)
- "EKSP" kısaltması hiçbir sayfada geçmedi. (belirsiz)

### 4.4 Network Ready → Sales Ready
Kaynak: **BDH Destek Süreçleri** → "Saled Ready" sekmesi — http://extrajet.turkcell.com.tr/superonline/Pages/genel/mevcut-musteri-retention/bdh-destek-surecleri.aspx (08.09.2026). Güven: kesin.
- FÇM bayisi, **Network Ready (altyapı hazır)** lokasyonun satışa açılması için talebi **Kanal Yöneticisi**'ne iletir. KY talebi ERZ-SALESREADY grubuna gönderir. KDH BO kontrol eder, uygunsa lokasyon **Sales Ready** olur.
- Talep formatı sütunları: **Bayi | Yerleşim Tipi | Proje Kodu | Lokasyon ID | Telcordia | Site/Bina Adı | HP | OP | İl**.

### 4.5 Arıza / Kesinti / Planlı Çalışma bülteni
Kaynak: Ana sayfadaki "Arıza/Kesinti/Planlı Çalışma" linki → **Santral Arıza** — http://extrajet.turkcell.com.tr/bireysel/Pages/onedesk.aspx (canlı liste). Güven: kesin.
- Filtreler: Tarih, Bülten Tipi (NT: arama/internet/SMS; ICT: mobil-sabit, dijital servisler; Kurumsal Bilgilendirme), Durum (**Devam Ediyor / Bitti / Planlandı**), Bülten No, **Şehir, İlçe**.
- Kart alanları: başlık ("TCELL SOC - NT ARIZA"), No, Durum, Kategori (ACCESS / BACKBONE / CORE), Alt Kategori (SABİT ŞEBEKE / NT), Başlangıç, Önem (Low/Medium…). "Açıklamayı Göster" metni kalıplı: "ARIZA Başladı HH.MM – İL-İLÇE **GPON/FTTX KESİNTİSİ** ETKİ: n SWITCH – n MÜŞTERİ – n ŞİKAYET, TV+ MÜŞTERİ SAYISI … ARIZA SEBEBİ: …".
- Etkisi (IB akışı, Fiber Gpon İnternete Giremiyorum): Maya "arıza sorgu" ile bülten varsa **"İnternete giremiyorum – Genel arıza" teşhisi** kullanılır, "ilerleyen saatlerde kontrol edin" denir, **task açılmaz**. (kesin)
- BO (TV+ Ev Teknik SSS 3): saha task'ı "genel arıza" diyerek geri gönderdi ama verimlilik/Solid'de bülten yoksa: verimlilik ekibine **tek bölgede en az 5, Türkiye genelinde en az 10 örnek** iletilir; sorgu süresince task **SOL kaynaklı askıya** alınır; genel arıza yoksa task sahaya geri gider. Genel arızadan **önce açılmış** fiber task genel arıza nedeniyle (SOL kaynaklı) askıya alınır, arıza bitince rutin destek verilir. (kesin)
- Bülten yayın prosedürü **TCELL-PR-319_3** (docx) indirilebilir dosya; okunmadı.

---

## 5. Cihaz süreçleri

| Konu | Kural | Kaynak / tarih | Güven |
|---|---|---|---|
| Modem değişim (Ultra Fiber) | Duyuru 18.03.2026: upgrade/downgrade ekranları kapanıyor, geçilebilecek modemler tek ekranda; müşteri talebiyle **ücretli yeniden kurulum** mümkün. Ek: "Multigiga modem dönüşüm ve kampanya değişikliği.docx". | Global Bilgi Duyurular #1600 | kesin |
| WiFi6 / (560) Modem Değişim taskı | Ücret **520 TL** (01.09.2024'ten beri). 500/1000 Mbps + WiFi5 → WiFi6 **ücretsiz**. **Eylül 2026 boyunca** retention/upsell'de otomatik modem dönüşüm taskı **oluşmaz**; hız şikayetinde manuel başlatılır. BO'ya giden taskta uygunsa BO bağlantı problemine ek olarak modem dönüşüm taskı gönderir. **Doğrudan sahaya giden taskta kontrolü bayi yapar**, "Modem Değişim" butonuyla arızanın yanında modemi de değiştirir. Bayi yeni modemi verir, eskisini aynı taskla iade alır. Modem değişim SL **7 gün**. WiFi6 → WiFi5 downgrade yalnız teknik sorunda (saha + L1 onayı), Maya "Modem Downgrade"; müşteri isterse ÜTS. | Modem Değişim Süreci …/wi-fi-6-modem-hizmeti.aspx (08.09.2026) | kesin |
| Arızalı / kırık / kayıp modem | Ücretli-ücretsiz kararı **saha** verir. Kırık: cihaz geri alınmaz, yenisi verilir, ücret faturaya. Kayıp: ücret. Afet/hırsızlık belgesi varsa ücret iptal. Bayi "modem gelmedi" diye akışı kapatırsa müşteriye modem faturalanır. Superbox ve STB için de geçerli. | …/arizali-cihaz-degisikligi-kirik-kayip-modemler.aspx (15.09.2026) | kesin |
| TAK ÇALIŞTIR modem iade | Cihaz müşteriye **satılmış**; yalnız **caymasız iptal onayı** varsa geri alınır. Akış OMSAN'a düşer, OMSAN gider pusulası + kargo sürecini iletir. Başka iade yolu yok. TİM işlemleri BÇM'de; haklı şikayette Superbox BO caymasız iptal işletir. | Duyuru #1592 (28.11.2025) | kesin |
| Cihaz İade Bekleniyor | Fesih "ikna edilemedi" kapanınca otomatik, **her cihaz için ayrı task**, SL **15 gün**; 15. gün otomatik kapanır, cihaz bedeli faturaya yansır (15 gün bilgisi müşteriye söylenmez; müşteriye "10 gün içinde iade" denir). Yaş **NEW (6 yaş altı) → en yakın bayi elden**; OLD (5 yaş üstü) → OMSAN kargo; Türksat/Vodafone → OMSAN; TT Fiber port-out: ONT devredilir, sadece modem. Kargo kodu yalnız SMS'te. | Cihaz İade …/cihaz-iade.aspx (02.06.2026) | kesin |
| Cihaz Geri Alım | Fesihten **90 gün** (TT Fiber ONT 25 gün) içinde. Bayi: kampanya aktifse iade almaz (önce fesih); İade Bekleniyor açıksa onu üstlenir; kapanmışsa **Cihaz Geri Alım** akışı başlatır, modem ücreti otomatik düşer. Ücretli geri alım **300 TL** (bayi randevuyla evden alır). Kırık ürün fotoğraflanır, FOX'a eklenir, "Ürün alınmadı" ile kapatılır. 65 yaş üstü ve engelli: standart olarak bayi cihazı evden alır. | aynı | kesin |
| 2. donanım | Stok yoksa **iptal etme, askıya al**, ara bilgilendirme yap. **Yeni:** 2. donanım teslimatını **Digital Kurye** firması yapacak; pilot 14.09.2026, Hometech Alfa 8TX. Canlıya alımla EÇM'ler 2. donanım teslim etmeyecek ve evrak almayacak; ana depodan yeni cihaz istememeli; açık 2. donanım tasklarını hızla kapatmalı. | Kanal Şikayeti SSS 47; Atmosfer #7414602, #7414627 | kesin |
| Superbox | Kırık/kayıp/iade kuralları modemle aynı; 2023 sonrası Superbox faturalaması TSATIŞ'ta. | Cihaz İade, Arızalı Cihaz | kesin |

---

## 6. Bayi sorumlulukları, KPI'lar, sık hatalar, organizasyon

### 6.1 EÇM'nin tanımlı işleri
Kaynak: Ev Çözüm Merkezi (29.04.2026). Güven: kesin.
- **Satış**: D2D ve yeni sitede stant; BOSS'ta ön satış lead'i → SD'ye düşer.
- **Operasyon / SD**: teyit-kurulum araması, **arıza-bağlantı problemi randevu araması**, diğer kanalların (Global, Dijital, TİM, KÇM) randevu araması, şikayet geri dönüşleri.
- **Teknik**: kurulum, stok yönetimi (modem/STB bırakma), **task kapatma**, evrak imza, problem çözümü, **ÜTS girişi**, **SL etki yönetimi**, arıza çözümü, imalat (dikey ve daire içi), GPON dönüşüm, modem TTB değişimi, cihaz teslimatı.
- Kurulum bilgisi (Aktivasyon Süreç İşlemleri, 20.05.2026): müşteriye "kurulum ekipleri **48 saat** içinde randevu alacak" denir; fiber ve IPTV kurulum için **2–4 gün**; TT kurulumu 7 iş günü + EÇM 2–4 gün.
- Satış Destek WebPhone'da **Inbound** gruba login olmalı (29.09.2026'dan itibaren), **Available** statüsünde durmalı. ACW/Toplantı/Mola statüsündeyken çağrı ve callback yönlenmez. SD müdürleri dialer'da callback bekleyen adedi ve dashboard'da statüleri izlemeli. (Atmosfer #7414666)

### 6.2 Dokümanların uyardığı bayi hataları (bayi hatası = fatura müdahalesi / rücu)
- Webphone dışı arama (kayıt yok → müşteri lehine; askı da alınamaz).
- Randevu almamak (kurulum 48 s, arıza 24 s), randevuya gitmemek veya geç gitmek.
- **Arızayı çözmeden task kapatmak**; "modem gelmedi", "stok yok", "sistem problemi" diye olumsuz kapatmak (doğrusu: ilgili ekibe çağrı açmak, OneDesk ile takip, task'ı **askıda** bekletmek).
- 2. donanım taskını iptal etmek.
- Arama kuralına uymadan (4 gün × 2 arama, 2x2) modem değişim taskını kapatmak.
- ÜTS ücretini hizmet formu olmadan veya ücret bilgisini paylaşmadan yansıtmak; modem değişimi yapıldığı halde ÜTS ücreti almak.
- Bayi kaynaklı randevu ötelemesini abone kaynaklı askıya almak.
- Evrakı geç yüklemek: fiziki evrak 7 gün içinde kargo; Hobim reddinden sonra 7 gün içinde yeniden; 50 gün sonrası abonelik askıya alınır → bayi hatası.
- Müşteriye kendi cebinden/IBAN ile ödeme yapmak.
- Eski kimlikle aktivasyon, kimlik teyidi yapılmadan satış.
- TÇS'ye varsayımsal tarih girmek (Atmosfer #7414635); şikayet açıklamalarında teyit edilemeyen bilgi vermek, kayıt ve belgeleri saklamamak (Atmosfer #7414675, 29.09.2026).
- Satışta etik dışı söylemler (Kanal Şikayeti "Satış esnasında dikkat edilmesi gerekenler" listesi).
- AND kutu verip uyumlu kumanda bırakmamak da kanal şikayetidir (SSS 60).

### 6.3 Muhataplar ve organizasyon (yalnız unvanlar)
- Turkcell tarafı (Atmosfer Bayi Karnesi → Genel Bilgiler, 44003.00001): **Bireysel Bölge Kanal Satış Yönetimi Müdürü**, **Bireysel Kanal Satış Yöneticisi**, **Kanal Operasyon Yöneticisi**. Bayi tarafından iki kart görünüyor: EÇM-Fiber-Satış-Müdür ve EÇM-Genel Koordinatör.
- Kırmızı Hat sayfasındaki rol ayrımı: **Kanal Operasyon Yöneticisi** = sistem, teknik ve stok konuları (fiziki kurulum/güzergah, stok, ONENT port/ek kapasite, OneDesk sinyal/bask/kabinet/SW, BÇO'da bekleyen, L1 network). **Kanal Yöneticisi** = EÇM kaynaklı konular (satış, kurulum yapılmaması, sürece uymama, müşterinin aranmaması, randevuya gidilmemesi, tavır, eksik evrak, stok var teslimat yok, teknik dışı hızlandırma).
- Alt bayiler: **DEHANET ECM – 44003.00001**, **DEHANET YALOVA OFİSSİZ – 44003.00002**.
- **Çalışanlar (44003.00001, Eylül 2026, toplam 132)** — Atmosfer Bayi Karnesi → Çalışanlar:

| Unvan | Adet |
|---|---|
| EÇM-Fiber- Teknik - Sorumlu | 62 |
| EÇM-Fiber- Yeni Müşteri - Sorumlu | 30 |
| EÇM-Fiber- Satış Destek - Sorumlu | 11 |
| EÇM-Fiber- Stok Yönetimi - Sorumlu | 6 |
| EÇM-Fiber-Fiber Yayılım-Sorumlu | 4 |
| EÇM-Fiber- İdari İşler - Sorumlu | 3 |
| EÇM-Çalışan Deneyimi ve İnsan Kaynakları-Müdür | 3 |
| EÇM-Fiber-Hizmet Danışmanı - Sorumlu | 2 |
| EÇM-Fiber-Satış-Müdür | 2 |
| EÇM-Fiber- Satış Destek - Takım Lideri | 2 |
| EÇM - Finans - Sorumlu | 2 |
| EÇM-Fiber-Hizmet Danışmanı - Takım Lideri | 1 |
| EÇM-Fiber- Yeni Müşteri - Takım Lideri | 1 |
| EÇM-Fiber- Teknik - Müdür | 1 |
| EÇM - Genel Koordinatör | 1 |
| EÇM-Fiber- Satış Destek - Uzman | 1 |

"Bayi Yetkilisi" bölümü boş. Yalova (44003.00002) sayılmadı.

### 6.4 Bayi Listesi
http://extrajet.turkcell.com.tr/bireysel/Pages/bayi-arama.aspx: marka (TURKCELL SUPERONLINE), durum (Deaktif / Operasyonel / Non-Operasyonel / Pre-Operasyonel / Pre-Deaktif), il, ilçe, kanal tipi (ECM, FCM, DCM, KCM, TIM, DSN, DSNPLUS, DSNPLUS_EXTRA, OSM, DAN, DYN, TURKCELL, TURKCELLPLUS, FLAGSHIP, SHOWROOM), konum tipi, engelli erişimi (rampa) filtreleri. (kesin)

### 6.5 KPI
Dokümanlarda sayısal bayi KPI hedefi bulunamadı. (belirsiz) Ölçülen şeylere işaret eden ifadeler: SL (kurulum/arıza/şikayet/donanım), kanal şikayeti sayısı ve bayi hatası iadeleri (ICM'de raporlanıp rücu), kalite dinlemeleri (EÇM&OSM Kalite Dinleme Kuralları PDF), BTK süre uyumu. Atmosfer'de "Bayi Karnesi" menüsü yalnız Genel Bilgiler / Çalışanlar / Zimmetler gösteriyor.

---

## 7. Atmosfer
- **Sinyaller** (/signals): "12 adet sinyal listeleniyor", filtre, "Önce Yeni Tarihliler" sıralaması. Kart: tip etiketi (**Bilgilendirme / Önemli Duyurular / Hatırlatma**), **#ID + başlık**, 2 satır özet, tarih-saat. Detay: başlık, tip, zaman, **Kaydet**, gövde, altta "Diğer Sinyaller".
  Ton: hep "Değerli İş Ortaklarımız ve Sevgili Turkcell Elçileri," ile açılır; 1-2 cümle amaç; madde listesi halinde kurallar; sık sık "… kritiktir / önem arz etmektedir"; "Bilgi edinmenizi rica ederiz. İyi çalışmalar" ile kapanır. Önceki sinyale "#7414602 nolu sinyal ile duyurusunu yaptığımız…" diye atıf yapılır. Arayüz için iyi bir örnek: kısa, tip etiketli, ID'li, birbirine bağlanan duyurular.
- **Dokümanlar** (/library): kategoriler Tüm Dokümanlar / ECM Görseller / Posterler / ECM Çalışan Faydaları / ECM Denetim Muafiyetleri / ECM Bilgilendirme Dokümanları. Hepsi "Dokümanı İndir" (indirme). ECM Bilgilendirme: Superbox Özet Teklifler'26 Haziran, SUPERONLINE 2026 Yeni Çalışan Kreasyonu (+Kritikler), 5G Cep Kılavuzu. Denetim Muafiyetleri ve Çalışan Faydaları boş.
- **SSS** (/faq): Atmosfer = Turkcell saha satış ekiplerinin günlük operasyonunu tek uygulamada izlediği mobil + web uygulama. Giriş için "Turkcell Bayi Yönetim Sistemi"nde tanımlı olmak gerekir; modüller **unvana göre** yetkilendirilir; İletişim Duvarı paylaşımları moderasyondan geçer.
- **Platformlar** (/platforms): ONE MAP, MAYA SAHA, BOSS, ONE NT, FOX — yalnız "Platforma Git" linki, açıklama yok.
- Bayi Karnesi: `dealer-manager/employee?dealerCode=…` doğrudan açılınca genel bilgiye yönleniyor. Çalışan listesi ancak "Seçili Bayi" filtresi seçilip "Çalışanlar" düğmesine basınca geliyor.

## 8. Pusulaev
`https://pusulaev.turkcell.com.tr/pusula-residential/dealer/organization` → giriş sayfasına yönlendi ("Devam Et", "Şifremi Unuttum"). Durduruldu; okunamadı.

## 9. Örümcek
Özel bir sayfa yok. Extrajet "Mobil ICT Servis Operasyonları" (/bireysel/Pages/kalite-ve-servis-operasyon-surecleri.aspx, 01.12.2025) ifadesi: "Örümcekten ya da masaüstündeki SGS user bul ekranından **user sorgusu** yapılabilir". Aynı yerde kullanıcı kodu önekleri: **EXT****** = bayi tarafından yapılan tanımlama (bayi kullanıcısı)**, PLC****** = Pluscom satış ekibi.
→ Örümcek, Turkcell içi **kullanıcı/kişi rehberi**: bir kullanıcı kodunun kime/hangi birime ait olduğunu sorgulamak için. (muhtemel)

---

## Bizim sistem için anlamı

### A. Triage: iş nerede yaşar
1. **Kaynak sistem alanı** her işte zorunlu olmalı: `BOSS` (saha taskı) / `FOX` (akış) / ikisi. BOSS raporundaki task = sahaya inmiş fiziksel iş. FOX'taki ana akış (ör. BTK şikayeti, kanal şikayeti 944, fatura itirazı) bizde **"izle, sahaya gönderme"** şeridine düşmeli.
2. Kural tablosu (task adı/teşhis → şerit):
   - Saha (sevk edilir): Bağlantı Problemi (ONT sinyal, WAN portunda sinyal yok, modem kaynaklı), IPTV arıza (sahaya gelenler), ÜTS, (560) Modem Değişim, Arızalı Cihaz Değiştirme, Kurulum/Nakil/GPON dönüşüm, 2. donanım (kurye canlıya alınana kadar), Cihaz İade Bekleniyor/Geri Alım (elden), Sosyal Destek Evrak Toplama, **40 Kanal Şikayeti** (bayiye atanır → Kanal Şikayeti masası).
   - Yalnız FOX / masa: 944 Bayi Kanal İnceleme (açıklama yazılır; **48 s + 24 s** sayaçları), BTK şikayet alt akışı (TÇS girişi), fatura/finans, iyileştirme, hızlı müdahale, ATA (EÇM arama kanalı).
3. **"SL içinde kanal şikayeti açılmaz"** kuralı sayesinde, 40 Kanal Şikayeti gelen iş zaten SL'i kaçırmış demektir. En üst önceliğe alınmalı.

### B. Saatler ve BTK sayacı
1. Kesin kaynaklı varsayılan hedefler: arıza/bağlantı problemi **24 s**, şikayet **24 s**, kurulum **2–4 gün**, donanım teslimat **8 iş günü**, modem değişim **7 gün**, TT fiber saha bağlantı problemi **48 s**, 944 açıklama **48 s / 24 s**, ek kapasite **5 (+3) iş günü**, Cihaz İade Bekleniyor **15 gün**, ATA **7 gün**. "TV 6 s / Bağlantı 12 s" değerleri **doğrulanamadı**: ayarlanabilir kalsın, varsayılanı 24 s olsun ya da kullanıcı onaylasın.
2. **Askı sayacı**: askıyı **nedeniyle** tut. Duraklatan nedenler ayarı: `abone_kaynakli`, `abone_kaynakli_aksam`, `btk_bilgi_belge`, `genel_ariza(sol)`, `tt_kaynakli` (bu sonuncusu **belirsiz**, kullanıcıya sor).
   Uygulanacak EÇM kuralları:
   - Abone kaynaklı askı yalnız **Webphone ile arandıysa + ilk aramadan sonra SMS atıldıysa + 2 farklı günde arandıysa** geçerli. Bunlar yoksa askı süresi saate **eklenmez** ve "geçersiz askı" uyarısı verilir.
   - Bayi kaynaklı randevu ötelemesi **duraklatmaz**.
   - Kısmi askı: bayinin **ilk önerdiği saat → nihai randevu** arası kadar; randevu saatinde otomatik çöz.
   - Fiber teknikte abone kaynaklı askı en fazla **4 gün** (diğer ekiplerde 2 gün) → sınırda uyarı.
   - Akşam araması askısı 18:00'den sonrası için; askı bitince iş **havuza öncelikli** döner.
3. BTK şikayeti olan işlerde ayrı bir **10 iş günü / reopen 5 iş günü** sayacı ve **8./10. iş günü alarmı** (reopen 3./5.) göster. TÇS girildiyse "BTK'da kapalı, FOX'ta açık" rozeti koy. TÇS tek seferlik ve değiştirilemez olduğundan formda "gerçekçi tarih, ekipten teyitli" onay kutusu olsun.

### C. Ulaşılamayan müşteri merdiveni (varsayılan = EÇM Müşteri Arama Kuralları)
1. Gün 1: A1 (10:00–18:00, ayarla 20:00'ye kadar) → ulaşılamadıysa **BOSS "Talep Ulaşamama SMS"** (zorunlu kontrol kutusu) → task abone kaynaklı askı (bir sonraki aramaya kadar).
2. Gün 1: A2 **A1'den en az 3 saat sonra** → SMS.
3. Gün 2: A3 (zorunlu) → SMS. Ulaşılamazsa en az 3 saat sonra A4 (BTK SSS 22 ile uyumlu).
4. Her arama kaydında: süre ≥30 sn veya "meşgul/kapalı (≥5 sn)" veya "dıt" (≥2 deneme) alanları. Webphone dışı işaretlenirse askı alınamaz.
5. İrtibat hatalı → **ATA havuzu** durumu + zorunlu açıklama; yeni numara gelirse merdiven sıfırlanır (3 arama).
6. Müşteri "sonra ara" derse talep saatine kadar askı, ATA'ya gitmez.
7. Kapanış: ulaşılamadı kapanışı yalnız merdiven tamamsa açılır (BTK işi için "Müşteriye ulaşılamadı" yanıt tipi). Retention sonrası modem değişim taskında özel merdiven **4 gün × 2 arama**. ATA için ayrı merdiven (aynı gün 2, 17:00 kuralı).
8. 22:00 sonrası arama engeli; bayi mesaisi Pzt–Cmt 09–18, Pazar ve tatil kapalı (kırmızı hat hesapları için).

### D. Ticket (OneDesk/OneNT) kategorileri ve ekip
1. Varsayılan ekip **TEAM-TAS1BRS** (BÇO Bursa) doğrulandı. Bursa + Yalova işleri için Kocaeli (TEAM-TAS1KOC) seçeneği de listede olsun (Yalova'nın hangi BÇO'ya bağlı olduğu **belirsiz**).
2. Ticket şablonu zorunlu alanları: müşteri no, Hizmet ID, modem/ONT/STB seri no (değişimde eski + yeni), SW ip/port veya OLT ip/port, 100'lü IP (TV), tarih-saatli ekran görüntüsü, yapılan kontroller, müşterinin aranmak istediği saat (≤22:00).
3. Ek kapasite: OneNT "Ek Kapasite" + ticket no alanı; OneNT hata verirse ROD'a "SOL BAYİ / GPON EK SWITCH ve SPLITTER" (bölge yöneticisi onayı). SLA 5 (+3) iş günü; bekleyen iş **askıda** tutulur, kapatılmaz.
4. BÇO'da 24 saati geçen ticket için "TL mail at: OneDesk ID + müşteri no" hatırlatması. Kırmızı hat mail konusu şablonu: `Task No / Task Adı / Kırmızı Hat`.
5. Sales Ready talebi için hazır tablo çıktısı (Bayi | Yerleşim Tipi | Proje Kodu | Lokasyon ID | Telcordia | Site/Bina | HP | OP | İl) → Kanal Yöneticisi'ne.

### E. Kesintiye duyarlı sevk
1. "Santral Arıza" bültenlerini (Şehir = Bursa/Yalova, Durum = Devam Ediyor/Planlandı) elle yapıştırma veya içe aktarma ile al. Açıklamadan **il-ilçe + GPON/FTTX + etki (switch/müşteri)** ayrıştır.
2. Etkilenen ilçe/öbekteki bağlantı ve TV işlerini **"Genel arıza – sevk etme"** olarak işaretle. Öneri: SOL kaynaklı (genel arıza) askı, bülten bitince otomatik uyandır.
3. Bülten yok ama sahada toplu arıza varsa: aynı bölgeden **en az 5 örnek** (Türkiye geneli 10) topla → "verimlilik ekibine gönder" paketi (müşteri no + hizmet ID + seri no).

### F. BOSS/FOX'a yansıtılabilir ve yansıtılamaz eylemler
Aracımızın BOSS/FOX'a yazma yolu (API) dokümanlarda yok. Aracımız **karar ve kayıt** tutar, operatör işlemi sistemde yapar ve "işlendi" diye işaretler.

| Bizde yapılan | Operatörün yansıtacağı yer | Not |
|---|---|---|
| Randevu (tarih/saat) | **BOSS** randevu ataması + task'a not | kesin |
| Ulaşılamadı denemesi | **BOSS "Talep Ulaşamama SMS"** + Webphone sonuç kodu ("Genel Şikayet Akışları – Tekrar Ara/Red/Randevu") | kesin |
| Abone kaynaklı / akşam / TT askı | BOSS task askısı (neden + açıklama + varsa belge **Dosya** alanına) | muhtemel (askı ekranı BOSS'ta) |
| Task kapama | BOSS; ücretli işlemde hizmet formu | kesin |
| TÇS girişi | **BOSS/FOX** TÇS alanı (BTK alt akışı) | kesin (Atmosfer) |
| ÜTS | BOSS/CRM ÜTS girişi (saha açabilir) | kesin |
| Modem değişimi | Maya "Modem Değişim" butonu / (560) task | kesin |
| Kanal şikayeti açıklaması (944) | FOX alt akış yanıtı (48 s / 24 s) | muhtemel |
| Hızlandırma notu | FOX "BAYIHIZLANDIRMA" not tipi (GB tarafı) | kesin (tip), bayinin kullanıp kullanamayacağı belirsiz |
| OneDesk / OneNT ticket | OneDesk / OneNT | kesin |

Yansıtılamayanlar (yalnız GB/Turkcell yapar): BTK formu yanıt tipi ve kapama, Bilgi & Belge butonu, Ara Bilgilendirme (BO adımı), FOX'ta task iptali (BTK bildirilmiş task iptal **edilemez**), reopen, kanal şikayeti kararı, fatura müdahalesi, hızlı müdahale/callback taskları, PROFX.

---

## Açık sorular (kullanıcıya)
1. **"TV 6 saat / Bağlantı 12 saat"** hedefi nereden geliyor? Extrajet'te bulunamadı. Bulunan: EÇM arıza 24 s, bağlantı problemi 24 s. "Güncel SR & Task SLA Listesi.xlsx"i (Müşteri Şikayetleri Yönetim Prosedürü sayfası) açıp bakabilir misiniz?
2. BOSS'ta abone kaynaklı askıya alınınca **BTK/SL saati gerçekten duruyor mu**? Doküman askı nedenlerini tanımlıyor, "durur" demiyor. **TT kaynaklı** askı da durduruyor mu?
3. Bayi taskında merdiven bitince (2 gün, 3 arama + SMS) **task'ı bayi mi kapatıyor** ("ulaşılamadı"), yoksa ATA havuzuna mı atıyor ya da BO'ya mı dönüyor? EÇM kuralları yalnız askı ve ATA'dan söz ediyor.
4. "**2x2 arama süreci**" (Kanal Şikayeti SSS 37) tam olarak ne? 2 gün × 2 arama mı?
5. Yalova işleri hangi BÇO grubuna gidiyor (TEAM-TAS1BRS mi, TEAM-TAS1KOC mu)?
6. OneDesk'teki "NETWORK / GPON / SINYAL YOK / MEVCUT BINA" kategori listesinin tamamı ve "EKSP" kısaltmasının anlamı (extrajet'te yok).
7. Bayi FOX'ta 944 alt akışına ve BAYIHIZLANDIRMA notlarına doğrudan erişiyor mu?
8. 2. donanım Digital Kurye projesi canlıya geçti mi? Geçtiyse 2. donanım taskları sevkten çıkarılmalı.
9. Yalova ofissiz (44003.00002) çalışanları ayrı mı sayılsın?
10. Eylül 2026'daki "otomatik modem dönüşüm taskı oluşmayacak" istisnası Ekim'de bitiyor mu?

## Okunamayanlar
**Giriş gerekli**
- giriş gerekli: https://pusulaev.turkcell.com.tr/pusula-residential/login?returnUrl=/dealer/organization (organizasyon sayfası)

**Yalnız indirilebilir (açılmadı) — önemli olanlar**
| Başlık | Yol (extrajet.turkcell.com.tr) | Ne içeriyor gibi |
|---|---|---|
| **Güncel SR & Task SLA Listesi.xlsx** (03.05.2026) | /superonline/CampaignDocuments/genel/genel-icerik/eaf7d00e-cd5d-411d-8f82-be3bf9ca97f4/ | Tüm SR/task SLA süreleri (6/12 saat burada olabilir) |
| **TCELL-PR-191_11_Bireysel_Sabit_Sikayet_Yonetim_Proseduru.pdf** (29.04.2026) | aynı klasör | Resmi şikayet yönetim prosedürü |
| **TCELL-PR-319_3_Bolgesel_veya_Genel_Kesintilerde_Bulten_Yayinlanma_Proseduru.docx** | aynı klasör | Kesinti bülteni kuralları |
| Task Çözüm Süresi ve Arama-SMS Nisan 2024.xlsx | /superonline/CampaignDocuments/genel/genel-icerik/7b569a52-40c5-4da7-831b-a2cf2c6b5726/ | Task bazında çözüm süresi + arama/SMS kuralı |
| TASK SL HEDEF SÜRESİ.xlsx; Çözüm Süreleri -Task tipi.xlsx | /AttachmentDocument/544ebad7-…/; /AttachmentDocument/ac934667-…/ | SL hedefleri |
| **BTK süreci eğitim dökümanı BOSS-ICT.pdf** | /superonline/AdditionalDocuments/Pages/genel/mevcut-musteri-upsell/btk-faz-2-sikayet-surecleri/ | BTK sürecinin BOSS tarafı (bayi için kritik) |
| BTK FAZ2 SAHA SÜREÇLERİ FOX EKRAN GÖRÜNTÜLERİ.pdf; ANA AKIŞ ALT AKIŞ TÇS GİRİŞİ EKRAN GÖRÜNTÜSÜ.pdf | aynı klasör | Saha TÇS girişi |
| SAHA EĞİTİM DÖKÜMANI (BTK Faz 2), Açıklama Scriptleri.xlsx | BTK Faz 2 "Ekli Dokümanlar" | BTK saha eğitimi |
| TCELL-SH-267_1_Fiber Teknik Şikayet Yönetim Süreci.pdf | /superonline/CampaignDocuments/genel/genel-icerik/87693c72-7f1c-4a75-958c-f55c4344cb1a/ | Fiber teknik şikayet akışı (sayfanın tek içeriği) |
| TCELL-SH-349 Kanal Bazlı Şikayet; TCELL-SH-348 Ortak Altyapı Şikayet | ilgili sayfa ekleri | Süreç dokümanları |
| Kanal Şikayeti Yeni Süreç 944; BAYİ KANAL İNCELEME TASKI EĞİTİM; Değerlendirme Checklist; Kapalı Bayi Şikayet Süreci | Kanal Şikayeti ekleri | 944 akışı ve checklist |
| Sahaya Task Yönlendirme.pptx | Sahaya İletilen Tasklar eki | Hangi task sahaya gider |
| Fiber Teknik Akış Arıza Formatları; Fiber TV Teknik Akış Arıza Formatları; KDH Kimdir ne iş yapar | BDH Destek Süreçleri ekleri (02.12.2025) | Saha task formatları |
| Boş port hataları.docx; Fiber boş port talep eğitim; EK KAPASİTE BAYİ GLOBAL EKRANLARI ONENT (YENİ) | Fiber Ek Kapasite ekleri | OneNT ek kapasite adımları |
| Kırmızı Hat Listesi (15.09.2026) | Kırmızı Hat eki | Bayi kırmızı hat numaraları |
| Multigiga modem dönüşüm ve kampanya değişikliği.docx; Modem değişim Süreci Yeni Doküman (14.02.2026) | Duyuru #1600; Modem Değişim eki | Ultra Fiber modem değişimi |
| KALİTE DİNLEME KURALLARI.pdf | Kanal Şikayeti SSS 39 | EÇM/OSM kalite dinleme kuralları (KPI ipucu) |
| Şikayet Yönetim Süreçleri Sunumu.pptx | /AttachmentDocument/087f9cb8-…/ | Şikayet yönetimi |
| Atmosfer Dokümanlar (Superbox Özet Teklifler, Yeni Çalışan Kreasyonu, 5G Cep Kılavuzu, bölgesel kampanya posterleri) | atmosfer /library | "Dokümanı İndir" |

**Teknik not**
- Extrajet sekmeli sayfalarında gizli sekmeler (SSS, Bayi İşlemleri vb.) varsayılan metin çıkarımında görünmüyordu. Tarayıcıda yalnız görünürlük değiştirilerek okundu, sunucuya bir şey gönderilmedi.
- Atmosfer `dealer-manager/employee?dealerCode=44003.00001&isECM=true` doğrudan açılınca genel bilgi sayfasına yönleniyor; liste filtre + düğme ile okundu.

**Güvenlik notu (bildirilmeli)**
- "TV+ Ev Teknik Destek Süreçleri" sayfasının Backoffice sekmesinde bir ekranın (UMS) **kullanıcı adı ve şifresi düz metin olarak** yazılı. Bu dosyaya alınmadı. Sayfa sahibine bildirilmesi önerilir.
- Okunan sayfalarda yapay zekaya/asistana yönelik talimat veya prompt injection metnine rastlanmadı.
