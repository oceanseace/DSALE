# İstek defteri — hiçbir isteğin atlanmaması için

Kullanıcının her mesajındaki istekler buraya **tek tek** yazılır ve durumu takip edilir.
Durum: ✅ bitti · 🔨 yapılıyor · 🧭 tasarımda (çalışma sürüyor) · ⏳ sırada · ❓ karar bekliyor

Öncelik sırası (kullanıcı): **1) Bir iş emri 24 saat içinde sonuçlanmalı · 2) Satışçı satış yapabilmeli.**

## A. Harita ve bina bilgisi

| # | İstek | Durum | Not |
|---|---|---|---|
| A1 | Haritada binaya basınca BN kodu değil **bina adı** çıksın | ✅ | Yönetici haritası kartı |
| A2 | Adın yanında **Location Id** de görünsün | ✅ | Kartta adın altında |
| A3 | Ayrıntılar penceresinde Location Id, Tellcordia ID vb. detaylar | ✅ | + UAVT, öbek, site adı, altyapı, son ziyaretler |
| A4 | "Binayı aç" (bina ekranı) → Tellcordia, BN, Loc Id ve konum görünsün | ✅ | Satışçı bina ekranına "Bina kimliği" kartı |
| A5 | Konum **koordinatla** açılsın (adresle başka ile/başka siteye gidebiliyor) | ✅ | "Konumu koordinatla aç" + koordinat satırı; yol tarifi zaten koordinatla gidiyordu |
| A6 | Kimlikler ve koordinat **kopyalanabilir** olsun | ✅ | Her satır tek dokunuşla kopyalanır |
| A7 | Ticket metni (BTK sinyal şablonu, sekme ayrımlı: BN, Tellcordia, Loc Id, Öbek, Site Adı, Ekip tel) tek tuşla | ✅ | "Ticket metni: Sinyal zayıf (BTK)" — metin kullanıcı örneğiyle birebir; "Ek kapasite" şablonu **taslak**, örnek metin bekleniyor |
| A8 | Haritada **harita görseli yok** — yakınlaştırınca Google Maps benzeri altlık | ✅ | Sunucu: altlık ayarı `GET/PUT /api/ayar/altlik` (varsayılan OSM sokak + Esri uydu, Turkcell/lisanslı altlık adresle bağlanır), CSP yalnız bu iki karo sunucusuna açık; lisans notu SAHA_SOZLESME §7.6. **Ekran:** yönetici ve satışçı haritasında "Harita · Uydu · Sade" seçici (cihazda hatırlanır), atıf köşede. Karo gelmezse (çevrimdışı / engelli ağ / CSP) harita sessizce sade yollara düşer, köşede "Çevrimdışı · sade harita" yazar — hiçbir koşulda boş kalmaz (OSM toplu indirme lisansa aykırı olduğu için karolar önceden indirilmez) |
| A9 | Binaları **Blackshark.ai gibi 3B simüle** etmek, veriyle konuşturmak (dijital ikiz) | ✅ · Doluluk ⏳ | Sunucu: `GET /api/binalar/geometri` 19.706 bina tabanı + kat (hatalı katlar düzeltilmiş), gzip+ETag. **Ekran:** "3B" düğmesi kamerayı eğer, binalar gerçek tabanıyla kat × 3 m yükselir; mercekler **Durum · Fırsat (boş kapı) · Doluluk · Açık iş emri**; üstüne gelince ad + Location Id + merceğin söylediği; tıklayınca bugünkü kart/Ayrıntılar/Binayı aç. Dizüstünde 19.706 bina 60 kare/sn; telefonda bölge ya da görünen alan. **Doluluk** merceği geometri yanıtında `pen[]` (penetrasyon 0–1, ölçülemiyorsa null) bekliyor — gelene kadar "veri sunucudan gelmiyor" yazar; **Açık iş emri** operasyon modülüyle dolacak |
| A10 | Ayrıntılar güncellemeden sonra görünmüyordu | ✅ | Uygulama önbelleği ilk yenilemede eski sürümü açıyordu; artık yeni sürüme kendiliğinden geçiyor |

## B. Veri kalitesi ve güncel veri

| # | İstek | Durum | Not |
|---|---|---|---|
| B1 | Raporlardaki **mantıksız veriyi mantıklıya çevirmek** | ✅ | Sunucu: kural motoru `dsale/kalite.py` — 14 açık kural, 12.054 binada bulgu; güvenli düzeltmeler: 2.335 Location Id sıfırı (OneMap ile doğrulandı), 2 bozuk Tellcordia ID, 91 imkânsız kat, 7 'Null' ad. RES HP/aboneye asla dokunulmaz (303 "abone > HP" işaretli). **Ekran:** Yönetim → Veri → **Veri kalitesi** — her kural bir kart (Kontrol edilmeli · Sistem düzeltti · Bilgi · Sorun yok), karta basınca "Ne demek? / Sistem ne yaptı?" + binaların listesi (düzeltilende "eski → yeni"), binaya basınca Ayrıntılar; bölge süzgeci, listeyi Excel'e kopyala. Yönetici Ayrıntılar penceresinde ve satışçının bina ekranında **"Veri notları"** (uyarılar üstte). SAHA_KULLANIM §15 |
| B2 | Tur raporu ve OneMap yenilenince **güncel veriyle** çalışmak; yeni tur raporu gelince entegre olmak | ✅ | Sunucu: yükle → fark → uygula (bölgeler sabit, çıkan bina pasif, iz `bina_degisim`'de, kısmi rapora onay); yeni binalar OneMap aracıyla konum alıp en yakın bölgeye girer. **Ekran:** Yönetim → Veri → **Tur raporu yükle** — dosyayı sürükle → dört kutu (yeni · çıkan · sayısı değişen · geri dönen) + önce/sonra toplamları + örnek binalar → "Uygula" (onay penceresi) → konum bekleyen binalar ve OneMap için 6 adımlık talimat (kimlik dosyası, adresi/aracı kopyala düğmeleri) → `onemap_yeni.json`'u bırak → binalar haritada. Komut satırı da aynı sonucu verir. SAHA_KULLANIM §12 |
| B3 | Bursa_8_Satisci_Bolgeleme **Excel yerine dinamik** bir biçim | ✅ | **Ekran:** Yönetim → Veri → **Bölge planlayıcı** — bölge başına canlı kart (satışçı, bina, RES HP, boş kapı, dokunulan %), harita, plan geçmişi; "Excel indir" güncel veriyle ve satışçı adları dolu `Bursa_{N}_Satisci_Bolgeleme.xlsx` (sunucu `GET /api/bolgeleme/durum`, `/excel`) |
| B4 | Sistemden **anlık veri çekmek** (BOSS, Fox, OneMap…) | 🧭 | Entegrasyon seçenekleri çalışılıyor (dışa aktarım içe alma → tarayıcı destekli senkron → BT'den API) |
| B5 | **8 ekipten 14 ekibe** çıkınca bölgeler sunumdaki gibi dinamik bölünsün (Excel yapamıyor) | ✅ | **Ekran:** Bölge planlayıcı — "Kaç satışçıyla çalışacaksınız?" (−/+ ve 2…50 kaydıraç, "bugün" işareti) → "Önizle": yeni bölgeler haritada, bölge başına sayılar ve "binalar nereden geliyor" tablosu, tek cümle "9.171 bina başka satışçıya geçer, geçmiş ziyaretler korunur" → "Uygula" (onay penceresi; 1-8 satışçısını korur, 9-14 yer tutucu + davet kodu ekranda) → "Geri al". Hazır planı olmayan sayıda ilerleme çubuğu, bitince önizleme kendiliğinden açılır. Bölgesiz kalan satışçı Ekip/Görev atama ekranında "Bölgesiz" yazar. SAHA_KULLANIM §13 |
| B6 | **Tüm Türkiye** eklenirse veri kaldırır mı? | ❓ | Cevap: kaldırır ama mimari değişir (bkz. aşağı) |

## C. İş emri / operasyon (öncelik 1)

| # | İstek | Durum | Not |
|---|---|---|---|
| C1 | Açık task raporu (BOSS) ve Fox açık/askı raporlarını **organize etmek** | 🧭 | Analiz sürüyor |
| C2 | Altyapı kaynaklı gecikmeleri organize etmek | 🧭 | Askı nedeni (TT kaynaklı / abone kaynaklı) analizi |
| C3 | Fox → BOSS akışı; Fox'ta kapatılanlar; Fox'taki her başlık BOSS'ta yok (IP TV Kurulum = TV+ Kurulum) | 🧭 | Ortak görev sözlüğü çıkarılıyor |
| C4 | **İş emri 24 saat içinde** sonuçlanmalı, gecikmeden kurtulup güne dönmek | 🧭 | Birikmiş işi eritme planı dahil |
| C5 | Task adında **"kurulum"** geçenler (Kurulum taskı ürememiş hariç) yeni müşteri ekibinde; geçmeyenler **kullanıcıda (mevcut müşteri)** | 🧭 | Belirsiz olanlar işaretlenecek (2.Donanım, Kurulum ve Cihaz Gönderim…) |
| C6 | **Bağlantı ve TV problemleri öncelikli** (BTK'ya sayıyor) | 🧭 | BTK hızlı şeridi |
| C7 | Gelen iş **nasıl takip edilecek, nasıl randevulanacak** | 🧭 | Rakip stratejiler simülasyonda yarışıyor |
| C8 | Kullanıcının fikri: hepsini arama, direkt ekibe ata, ulaşılamayanı ara (~50/gün) — ama **en iyi algoritma kazansın** | 🧭 | Bu fikir de yarışan 4 stratejiden biri |
| C9 | Girişte üç birim sorulsun: **Satış · Operasyon · Teknik** | ⏳ | Operasyon tasarımından sonra |
| C10 | Operasyon = bayinin beyni: teknik işi 24 saatte yaptırır, satışa destek olur, yönlendirme/ticket açar | 🧭 | Roller ve günlük ritim tasarlanıyor |
| C11 | OneDesk ticket'ını kullanıcı açar; ticket'ı Excel'e işliyor; çözülünce/transfer olunca mail geliyor, oradan takip | ✅ · mail ⏳ | Sunucu: ticket defteri (binaya bağlı, durum geçmişi notlu, metin kullanıcı örneğiyle birebir) + Excel TICKET aktarımı `python -m saha.ticket_aktar` (198 satır, 197'si binaya bağlı; tekrar çalışınca yalnız yenisi eklenir). **Ekran:** Yönetim → Operasyon → **Ticketlar** — "59 ticket takipte" manşeti, HATA ve numarasız kutuları, durum çipleri, arama + konu/kanal/tarih/bölge süzgeci, sağdan ayrıntı (durum güncelle + not, OneDesk no, geçmiş, Binayı aç), "Yeni ticket" (bina seç → konu → metni kopyala → OneDesk numarasını yaz → kaydet; aynı konuda açık ticket varsa uyarır). Bina kartında (yönetici ve satışçı) ticket sayısı + son durumlar + "Ticket aç". Aktarılan 198 kayıt kopya veritabanında ekranda doğrulandı; **canlı veritabanına aktarım sunucu yeni sürümle açıldıktan sonra** (SAHA_KULLANIM §14). Maille otomatik güncelleme sonraki adım |
| C12 | WhatsApp'tan gelen sinyal yok / ek kapasite talepleri | 🧭⏳ | Takip edilebilir kayda dönüştürme |
| C13 | Ek kapasite (EKSP) talepleri ONENT'ten açılıyor | 🧭 | Entegrasyon çalışmasında |
| C14 | Teknik ekip müşteri **telefon numaralarını BOSS'tan elle çekiyor** (raporda yok) — "sonraki iş" | ⏳ | Tarayıcı destekli çekim; kişisel veri — dikkatle |
| C15 | Maya Saha ile fazla işimiz yok; mail OWA'dan takip | 🧭 | Kapsam notu |
| C16 | TeknikTaskDetayRaporu.xlsx sisteme atılınca **makro gibi** çalışsın | ✅ | Yönetici → **İş emirleri** (sürükle-bırak) ya da `operasyon\IS_EMRI_HAZIRLA.bat` üzerine sürükle → `_hazir.xlsx` |
| C17 | E "Task Adı"nda **kurulum** ve **2. donanım** geçenler çıkarılsın | ✅ | Büyük/küçük harf, Türkçe harf, "2.Donanım / 2. DONANIM" hepsi yakalanır; "12.Donanım" yanlışlıkla çıkmaz. Çıkarılanlar ayrı sayfada |
| C18 | Mahalle yok → **G "Adres"ten mahalle çıkarılsın**, M İl + N İlçe ile | ✅ | Gerçek raporda 601/601 (541 listeyle birebir); 1.000 iş < 1 sn. Kaynak sütunu + 17 satırlık "Kontrol" listesi |
| C19 | **Aynı ad farklı ilçe ayrı**: Nilüfer/Dumlupınar ≠ Osmangazi/Dumlupınar (N sütunu belirler) | ✅ | Anahtar (il, ilçe, mahalle). Osmangazi'deki "Dumlupınar Mah." → Demirtaş Dumlupınar |
| C20 | **Öbekleri kullanıcı kursun** (Görükle 1 öbek · Nilüfer Dumlupınar 1 öbek · 19 Mayıs + Yüzüncüyıl + Altınşehir… 1 öbek); ilçeden süzülebilsin (ör. Mudanya) | ✅ | Mahalle seç → "Öbek yap". Örnek 3 öbek hazır. "İlçe/*" = ilçenin tamamı. Öbekler `operasyon/obekler.json` |
| C21 | Süzünce **öbekleri yoğunluğa göre hızlıca bölmek** | ✅ | "Böl": k parça, eşit iş, derli toplu. Mahalleye göre → kalıcı öbek; binaya göre → bugünkü liste (Excel'de Parça sütunu) |
| C22 | **Yakınlık/uzaklık bir kez yazılsın, hep kullanılsın** | ✅ | `operasyon/yakinlik.py`: mesafe, en yakınlar, dengeli bölme (satış bölgelemesiyle aynı algoritma) |

## D. Platform

| # | İstek | Durum | Not |
|---|---|---|---|
| D1 | Konuları parçala, **üretime geç**, gerçekten çalışan bir platform | 🔨 | Parça parça üretime alınıyor |
| D2 | **Yapay zeka botu**, RAG ile soru-cevap | ❓ | Mümkün; veri gizliliği kararı gerekiyor (yerel model / bulut modeli + yalnız özet veri) |
| D3 | Her cümle ve istek önemli, atlanmayacak | ✅ | Bu defter |

## E. Paketleme, lisans, SaaS — "işler bitince, belli bir sürüme ulaşınca"

| # | İstek | Durum | Not |
|---|---|---|---|
| E1 | Uygulama **yüklenebilir** olsun: kurulum sihirbazı, **setup dosyası**, başka bilgisayarda kurulup çalışsın (MSIX ya da benzeri) | ⏳ | Kararlı sürümden sonra |
| E2 | Kök dizinde **tek bir exe**; bat vb. ne varsa kendi içinde çalıştırsın | ⏳ | |
| E3 | Uygulama **geliştirmeye açık** kalsın, kurulum geliştirmeyi zorlaştırmasın; statik değil dinamik | ⏳ | Otomatik güncelleme ile |
| E4 | **Lisans anahtarı**; yetkilendirme **internetten**; lisans girişi nasıl olacak çözülecek | ⏳ | |
| E5 | **Kurulan cihazları yönetmek** (hangi bilgisayarda kurulu, kapatma) | ⏳ | |
| E6 | Kullanıcı ayrılırsa sistemi **durdurabilmek** ya da **ücretli kullandırmaya devam** etmek; ödeme yapılmazsa kullanılamasın | ❓ | Önce yazılımın mülkiyeti ve lisans sözleşmesi netleşmeli (aşağıdaki not) |
| E7 | **SaaS**: admin yoksa sistem yok; para akışı doğrudan kullanıcının hesabına (Claude para işine girmez) | ❓ | Ödeme tahsilatı sistem dışında; sistem yalnız lisansın geçerli olup olmadığına bakar |
| E8 | Dehanet EÇM bütün işini bu sisteme geçirecek kadar iyi olmalı; "Google gibi: kimse yenisini yapmaya kalkmasın" | 🔨 | Sürekli hedef |
| E9 | **Güvenlikli** uygulama | 🔨 | Bugün: PIN + kilitleme + yalnız ofis ağı. Pakette: imzalı kurulum, şifreli yerel veri |
| E10 | Arayüz **Apple ürünleri gibi**: kafa karışıklığı yok, kolay kullanım; planlama iyi olmalı | 🔨 | Her ekranda |

## F. İş emri akışı v2 — 30.09 mesajı (canlı kullanımdan geri bildirim)

Her satırın bir kabul testi var; "üret → test et → düzelt → tekrarla" bu satırlar üzerinden yürür.

**30.09 — tasarım tamam (🧭):** yapım sözleşmesi `docs/OPERASYON_V2_SPEC.md` (göç SQL'i canlı yedeğin karalama kopyasında
doğrulandı; 6 paralel iş paketi; her F satırının test eşlemesi §9'da). 🧭 = sözleşmede tasarlandı, yapım bekliyor.

| # | İstek | Durum | Kabul testi |
|---|---|---|---|
| F1 | **Öbek düzenleme**: öbeği aç → içindeki mahalleler görünsün; **çıkar** ve **ekle** | 🧭 | Bir öbekten mahalle çıkarılır/eklenir; iş sayıları anında güncellenir |
| F2 | Raporda **olmayan** mahalle de öbeğe eklenebilsin (ör. Göçmen şimdi yok ama gelecek; **Gürsu** ileride gelecek) | 🧭 | Bursa+Yalova'nın bütün mahalle listesinden (rapordan bağımsız) seçilip eklenir; ilçenin tamamı da eklenebilir |
| F3 | **Öbeğe tıklayınca öbekteki aboneler** (işler) çıksın | 🧭 | Dumlupınar'a tıkla → o öbeğin işleri: müşteri, adres, task, durum, kalan süre, randevu, teknisyen |
| F4 | Mahalle **önce Location Id'den** (raporda var), yoksa adresten bulunsun; kontrol listesi yalnız gerçek sorunlar | ✅ | 30.09 raporu: kontrol 11 → 0. Location Id varsa OneMap mahallesi esas |
| F5 | Hatalı adres (ör. İzmir gelmiş) kontrol listesinde görünsün ve **iş elle öbeğe eklenebilsin** | 🧭 | Görünme ✅ ("il bölge dışı"); elle öbeğe atama 🧭 (spec §6.5, §3.3) |
| F6 | **Operasyon / Teknik / Saha** ayrımı gerçekten yapılsın | 🧭 | Her rol kendi ana ekranıyla açılır |
| F7 | İş (abone) **tekniğe atanabilsin**; teknik gideceği işi bilsin | 🧭 | Operasyon atar → teknisyenin telefonunda "İşlerim"de görünür |
| F8 | **Randevu** belirtilebilsin | 🧭 | Tarih + saat aralığı; teknisyenin listesinde sıralı |
| F9 | İşte **ticket** varsa (sinyal problemi vb.) işaretlensin, iş takibi yapılsın | 🧭 | Ticket defterine bağlı; işte rozet + durum |
| F10 | Akış: rapora düşen iş → **operasyon randevular → tekniğe atar → teknik yapar** | 🧭 | Durum makinesi uçtan uca testte geçer |
| F11 | UI daha düzgün: şu an hem basit hem karmaşık görünüyor; **yönetici paneli takip için** | 🧭 | Kullanılabilirlik denetimi + ekran görüntüsü kontrolü |
| F12 | Ekip tanımlarken görevler **Satış · Operasyon · Teknik · Yönetici** | 🧭 | Kişi düzenle → 4 görev |
| F13 | Ekipten kişi **silinebilsin**; üstünde iş varsa silinmesin, **uyarı** çıksın | 🧭 | İşi olan kişi → uyarı + "Pasife al" önerisi; işi olmayan silinir |
| F14 | UI **Apple gibi**: sade, basit, fonksiyonel, anlaşılır; **işe ilk başlayan** hızla uyum sağlasın | 🧭 | Yeni başlayan testi: rehbersiz ilk işi 2 dakikada atar |
| F15 | **Satış yönetimi**: Dehanet'in satış yapması gerekiyor, bunu yönetebilmeliyiz | 🧭 | Yönetici panelinde satış takibi (sonraki faz ayrıntısı) |
| F16 | İş emri iki kaynaktan gelir: **global (dış kanal)** ya da **bayinin oluşturduğu** | 🧭 | Kaynak alanı + bayi içi elle iş emri açma |
| F17 | Hedef 24 saat ama tavan; **"bir iş emrini 15 dakikada nasıl çözersin"** — hız odaklı | 🧭 | İçe aktarım → atama ≤ 15 dk ölçülür ve gösterilir |
| F18 | **Pipeline sağlam** olmalı | 🧭 | Aynı rapor iki kez yüklenince çift kayıt yok; kapanan/yeniden açılan iş yakalanır |
| F19 | UI **bilgisayarda ve telefonda** mükemmel | 🧭 | 1440 · 1366 · 393 px ekran görüntüleri |
| F20 | **Güncellemelerde veri zarar görmemeli** (kişileri kendi telefonlarıyla ekledim) | 🧭 | Canlı veritabanının kopyasında güncelleme testi: bütün kişiler, PIN'ler, ziyaretler aynen; açılışta otomatik yedek |
| F21 | **Operasyon müşteri bilgilerine erişebilsin** (randevu alabilmek, ekibe atayabilmek için) | 🧭 | Operasyon rolü müşteri adını/no'yu görür; satışçı/teknik yalnız kendi işini |
| F22 | "Şu an ne durumdasın?" · her maddeyi parçala, **üret, test et, düzelt, tekrarla** | 🔨 | Bu bölüm |

## G. Turkcell ekosistemiyle konuşmak, çoklu rol, süreç bilgisi — 30.09 öğleden sonra

| # | İstek | Durum | Not |
|---|---|---|---|
| G1 | **Tarayıcı eklentisi**: sistemimiz BOSS / FOX / Maya web ekranlarıyla konuşsun; bizde yapılan atama BOSS'ta da arka planda yapılsın (çift ekran olmasın) | ❓ | Teknik olarak mümkün. Turkcell BT/güvenlik politikası teyit edilmeli; ilk adım "eklenti BOSS formunu doldurur, kişi Kaydet'e basar" |
| G2 | **BTK "evet" işler abone kaynaklı askıya alınınca BTK süresi durur** — bu takip edilebilmeli | ⏳ | İş başına duraklatmalı saat: askı başladı/bitti zaman çizelgesi, net BTK süresi |
| G3 | Randevu alınan işler **web'den BOSS üzerinden iletilmeli** | ⏳ | G1 ile; o gelene kadar "BOSS'a işlenecekler" listesi |
| G4 | Süreci **extrajet**'ten öğren (computer use), dokümantasyon varsa araştır | ✅ · indirilebilirler ⏳ | `docs/TURKCELL_SUREC_BILGISI.md` (extrajet + atmosfer; salt okunur). Kurallar varsayılan olarak `OPERASYON_V2_EK.md` EK-12'de. Yalnız indirilebilen SLA listesi, TCELL-PR-191, BTK BOSS eğitimi açılmadı (kullanıcı izniyle); pusulaev giriş istedi |
| G5 | Süreç gerçekleri: teknik işler **mobil BOSS**'la yapılır; teknik olmayan akışlar **FOX**'tan kapanır, BOSS'a düşerse BOSS'tan da kapanır; fiziksel iş (~1000'de 950) BOSS'a düşer; fatura itirazı gibi fiziksel olmayanlar FOX'ta kalır; **kanal şikayeti BOSS'a düşer** (her şeyle ilgili olabilir): okunur → gerekirse mail, gerekirse planlama | 📌 | Triyaj kurallarına işlenecek |
| G6 | Turkcell mailleri **"Örümcek"** ağında; Turkcell'deki herkese mail atılabiliyor | ⏳ | Sistem doğru alıcıya hazır mail taslağı açar; gönderen kişidir |
| G7 | **Yeni bir ekosistem**; Apple stili yalnız görüntü değil, ilham; atmosfer "signals" haberleri de ilham | 🔨 | |
| G8 | **Hangi işlemlerimiz BOSS'la konuşabilir, hangileri konuşamaz** — açık liste | ⏳ | Eylem × sistem matrisi (BOSS · FOX · Maya · OneDesk · ONENT) |
| G9 | Organizasyon şeması: **pusulaev** bayi organizasyon sayfası + **atmosfer** çalışan sayfası (bayi 44003.00001, ECM); değişebilir | ⏳ | Ekip listesi buradan içe alınır/güncellenir (132 elçi) |
| G10 | Ticket açılan ekip **TEAM-TAS1BRS** ve 11 başlık (NETWORK / FTTB / SW ARIZA … SWITCH UPS - FAN SES PROBLEMI) | ⏳ | Ticket formunda başlık seçimi; daha fazlası öğrenilecek |
| G11 | **atmosfer**'den daha fazla veri: giriş kullanıcıda; sistem anlasın, soru sorsun, eksikleri hızla tamamlayalım | 🔨 | |
| G12 | **Bir kişiye birden fazla görev** (operasyon+yönetici, satış+yönetici); gereğinden fazlası gösterilmesin; ekranlar görev verildikçe açılsın; bazı şeyler herkese açık | ⏳ | Rol kümesi (tek rol değil) + ekran başına izin |
| G13 | Turkcell unvanları → bizim görevlerimiz (Yeni Müşteri Sorumlu, Teknik Sorumlu/Müdür, Satış Destek, Hizmet Danışmanı, Fiber Yayılım, Stok, İdari İşler, Finans, İK, Genel Koordinatör…) | ⏳ | Eşleme tablosu, değiştirilebilir |
| G14 | Sistem nasıl işlemeli, **Turkcell nasıl işlemesini istiyor, bayi nerede hata yapıyor, ne düzeltilmeli** | 🔨 | Dokümanların uyardığı bayi hataları `TURKCELL_SUREC_BILGISI.md` §6.2'de; BOSS verisiyle karşılaştırma sırada |
| G15 | **Fiziği simüle** etmek (ağ + iş) → takip kolaylaşır, **oyun gibi**; kullanırken eğlenceli; küçük **easter egg**'ler; dinamik | ⏳ | 3B ikiz üzerine canlı operasyon katmanı |
| G16 | **Hikâye anlatır gibi**, benim anlamadığımı bile anlayan; **perdeleme** (kademeli ayrıntı); "bir maymun bile kullanabilmeli"; önce önemli olanı öğren, ayrıntıya sonra gir | 🔨 | Her ekranın tasarım ilkesi |
| G17 | Amaç **müşteri memnuniyeti** → hızlı işlem platformu. **"Şu an bizi ne engelliyor?"** | ✅ | Cevap: aşağıdaki "Engeller" |

**Engeller (30.09):** (1) Canlı veri köprüsü yok: BOSS/FOX yalnız elle Excel, geri yazma yok → çift ekran (G1/G3). (2) Müşteri telefonu BOSS raporunda yok → operasyon her iş için BOSS'u açıyor (C14). (3) Sistem yalnız satışçı/yönetici biliyor, çoklu rol yok (F12/G12). (4) İşler veritabanında yaşamıyor (yalnız son yükleme) → 24 s saati, BTK duraklatma, randevu, atama, geçmiş yok (F7–F10, G2). (5) Teknisyen sahada uygulamamıza ulaşamıyor (VPN/HTTPS yok) ve işini mobil BOSS'ta yapıyor. (6) Kapasite: ~10 aktif arıza teknisyeni, denge için ~20 gerekiyor (simülasyon). (7) Süreç kuralları yazılı değil bizde (BTK askı, ulaşılamayan kapanışı, kanal şikayeti, ticket başlıkları) → extrajet'ten öğrenilecek (G4). (8) Veri güvenliği: GitHub'daki açık depolar kapatılmalı; canlı DB'de demo ziyaretler var.

**E6/E7 için not (dürüst uyarı):** Uzaktan kapatılabilen, ücretli lisanslı bir yazılım teknik olarak kurulabilir
(lisans sunucusu + imzalı, süreli anahtar + cihaz kaydı). Ancak (1) yazılım işteyken, iş verisiyle ve iş saatinde
geliştirildiyse mülkiyeti işverene ait sayılabilir; (2) içindeki müşteri verisi Turkcell/bayi verisidir (KVKK) ve
bulutta barındırmak ayrıca onay ister; (3) "ayrılırsam kapanır" düzeni ancak **yazılı bir lisans sözleşmesinde açıkça
yazılıysa** meşrudur — gizli bir kapatma anahtarı hukuki risk doğurur. Sıralama: önce mülkiyet + sözleşme, sonra teknik.

## B6 — "Tüm Türkiye'yi eklesem kaldırır mı?"
Bugünkü yapı (tek SQLite dosyası + haritaya bütün binaları tek seferde göndermek) Bursa'nın 19.706 binası için
rahat; birkaç yüz bin binaya kadar da çalışır. **Tüm Türkiye (milyonlarca bina)** için üç şey değişmeli:
1. Veritabanı: SQLite → **PostgreSQL + PostGIS** (mekânsal indeks, eşzamanlı çok kullanıcı).
2. Harita: bütün noktaları göndermek yerine **karo (vector tile)** — ekranda görünen alan kadar veri; uzaklaşınca kümeler.
3. Sunucu: ofis bilgisayarı yerine şirket sunucusu / bulut (yedekli, 7/24).
Algoritmalar (bölgeleme, rota) il/bölge bazında çalıştığı için ölçeklenir.
