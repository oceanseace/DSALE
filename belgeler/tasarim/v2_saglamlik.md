# İş emri akışı v2: Sağlamlık tasarımı

*Dehanet EÇM · Saha Sistemi · 30.09.2026 · Yaklaşım: **SAĞLAMLIK** (iş akışı ve veri güvenliği)*
*Kapsam: `docs/GEREKSINIMLER.md` §F'nin 22 satırının tamamı (F1–F22); C, D ve E ile tutarlı.*
*Dayanak: `docs/OPERASYON_TASARIM.md` (KARMA-2, roller, fazlar), `docs/SAHA_SOZLESME.md`, 30.09 kod haritası, kullanılabilirlik denetimi ve veri/güncelleme denetimi.*
*Bu belgede kişisel veri yoktur. Yalnız sayım, oran, ilçe ve mahalle adı geçer.*

---

## 0. Tek sayfada

### 0.1 Beş söz

Bu tasarım, sistemin kullanıcıya verdiği beş sözü koda çevirir. Her sözün bir otomatik testi vardır (§6).

| # | Söz | Nasıl tutulur |
|---|---|---|
| 1 | **Güncelleme veri kaybettirmez.** | Her şema değişikliğinden önce otomatik ve doğrulanmış yedek alınır. Değişiklik tek işlemde yapılır; sonucu satır satır doğrulanmadan kaydedilmez. Her sürüm, canlı veritabanının kopyasında bir yükseltme testinden geçer. Kullanıcının öbek dosyası hiçbir koşulda üzerine yazılmaz. |
| 2 | **Bir iş, bir kayıttır.** | İşin anahtarı BOSS Task No'dur. Rapor kaç kez, hangi sırayla yüklenirse yüklensin çift kayıt oluşmaz. Randevu, atama ve öbek bilgisi yeni yüklemede silinmez. Kapanan ve yeniden açılan iş yakalanır. |
| 3 | **Her değişikliğin sahibi ve saati vardır.** | Kim, ne zaman, neyi, neyden neye değiştirdi: olay defterine yazılır. Defter silinemez ve değiştirilemez (veritabanı tetikleyicisi). |
| 4 | **Kimse başkasının işini sessizce ezmez.** | Her iş ve öbek düzeni bir sürüm numarası taşır. Eski ekranla yapılan değişiklik reddedilir; ekran güncel hâli gösterir ve kimin neyi değiştirdiğini söyler. |
| 5 | **Herkes yalnız işi için gerekeni görür.** | Rol başına açık bir izin tablosu vardır; tabloda olmayan her şey yasaktır. Müşteri bilgisini operasyon görür, teknik yalnız kendi işini görür. Her müşteri görüntülemesi kayda geçer. |

### 0.2 Şu an ne durumdayız (F22)

| Konu | Bugün (30.09) | v2 ile |
|---|---|---|
| BOSS raporunu içe alma | Makro çalışıyor: 1.628 satır → 437 iş, mahalle 437/437. Ancak durum **tek bir pickle dosyasında** duruyor, iş kimliği satır numarası ve her yükleme parçaları siliyor. | İşler veritabanında, Task No anahtarlı. Yükleme birleştirir (upsert), farkı gösterir, geçmişi saklar. |
| Öbekler | `operasyon/obekler.json` (14 öbek, 120 mahalle). Açılıp düzenlenemiyor. Yalnız bugünkü raporda geçen mahalle eklenebiliyor. | Öbek düzenleyici açılır: mahalleler görünür, eklenir ve çıkarılır. Bursa + Yalova'nın bütün ilçeleri, ilçenin tamamı ve listede olmayan mahalle de eklenebilir. |
| İş listesi | Yok. Öbeğe tıklamak yalnız süzgeç koyuyor. | Öbeğe tıkla → işler (müşteri, adres, task, durum, kalan süre, randevu, teknisyen) → iş kartı. |
| Randevu, atama, ticket, takip | Yok. | Durum makinesi, iş kartı, "İşlerim" (teknik), olay defteri. |
| Roller | Yalnız `satisci` ve `yonetici`. Canlıdaki 10 gerçek hesabın 8'i "yönetici". | Satış · Operasyon · Teknik · Yönetici. Göç kopyada denenmiş sırayla yapılır. |
| Kişi silme | Yok. | Kaydı olmayan kişi silinir. Kaydı olan için uyarı çıkar ve "Pasife al" önerilir. |
| Güncelleme güvenliği | Göçten önce yedek alınmıyor. Göç iki yerde ve port kontrolünden önce çalışıyor. | Önce yedek, tek işlem, doğrulama; tek yerden ve kilitli çalışır. Canlı kopyada test edilir. |
| Arayüz | Çok düğme, iç içe kaydırma. Telefonda menü ekranın %35'ini kaplıyor. Karanlık modda okunmayan yazılar var. | Tek tasarım dili: satışçı uygulamasının sakin bileşenleri yönetim ekranlarına da taşınır. |

### 0.3 Bu turda yapılmayanlar

Bunlar KARMA-2'nin sonraki parçalarıdır; §9'da gerekçeleriyle listelenir:

- FOX dosyası içe alma
- Masa kuyruklarının tamamı: SMS, kontrol grubu, kalite geri araması
- Otomatik sıra motorunun iki modu (bu turda sıralama kuralı ve mod göstergesi var)
- Sahadan VPN ile erişim

---

## 1. Roller

### 1.1 Dört görev

Veritabanındaki değerler değişmez; yalnız iki yeni değer eklenir. `satisci` ve `yonetici` SQL'e gömülü olduğu için (rapor.py, bolgeleme.py, demo.py, kur.py) **yeniden adlandırılmaz**. Arayüzde "Satış" yazılır.

| DB değeri | Ekranda | Kimdir | Masaüstünde ilk ekran | Telefonda ilk ekran |
|---|---|---|---|---|
| `satisci` | **Satış** | Bayinin satış temsilcisi | Bugün (satış listesi) | Bugün (bugünkü uygulama, değişmez) |
| `operasyon` | **Operasyon** | Masa: triyaj, BTK teşhisi, arama, atama, randevu | **İşler** panosu | İşler (öbek listesi → işler → iş kartı) |
| `teknik` | **Teknik** | Arıza teknisyeni. Teknik lider için ayrı rol yok, `etiket` kullanılır (§1.5) | İşlerim (ortalanmış tek sütun) | **İşlerim** |
| `yonetici` | **Yönetici** | Operasyon lideri, bayi müdürü | **İşler** panosu. Cihaz son açılan bölümü hatırlar | İşler |

OPERASYON_TASARIM §5.1 ile uyum:

- Orada `teknisyen`, `teknik_lider` ve masa etiketli `operasyon` önerilmişti. Kullanıcının F12'deki sözü "Teknik" olduğu için DB değeri `teknik` seçildi.
- `teknik_lider` bir rol değil, `etiket = ["lider"]`.
- Masa türleri de etikettir: `["triyaj","btk","arama","altyapi","lojistik","vardiya"]`.
- Yetki rolden gelir, etiket yalnız süzgeç ve gösterge içindir. Böylece yeni bir alt görev için **bir daha tablo yeniden kurulmaz**.

Giriş (C9, §5.1): Bu turda birim kutusu **yok**. Rol, telefon numarasından bilinir ve kişi doğru ekrana düşer. Üç kutuyu seçtirmek, rolü zaten bilinen kişiye fazladan bir adım olurdu (F14: "işe ilk başlayan hızla uyum sağlasın"). C9 bu tasarımla karşılanır; kutu isteniyorsa açık soru 10'da seçenek olarak duruyor.

### 1.2 İzin tablosu (varsayılan: YASAK)

Kaynak dosya `saha/yetki.py`. Her uç bir eylem adıyla korunur: `Depends(izin("is.ata"))`. Tabloda olmayan eylem her rol için 403 döner. Bir test, uygulamadaki **bütün** uçları gezer ve tabloda olmayan uç bulursa kırmızı olur (§6.3).

| Eylem | Satış | Operasyon | Teknik | Yönetici |
|---|---|---|---|---|
| Satış: bina listesi, harita, ziyaret yazma (`satis.*`) | Kendi bölgesi. Bölgesiz ise hiçbir şey | — | — | Hepsi |
| Satış özetleri, kapsama, görev atama, bölge planlayıcı | — | Yalnız okuma: kapsama ve özet | — | Hepsi |
| Bina kartı `GET /api/bina/{serial}` | Kendi bölgesi | Hepsi | Yalnız kendisine atanmış açık işin binası | Hepsi |
| `is.liste` (iş listesi) | Yalnız kendi açtığı işler | Hepsi | Yalnız kendisine atanmış açık işler | Hepsi |
| `is.musteri` (ad, müşteri no, adres, telefon) | Yalnız kendi açtığı işte | Hepsi | Kendisine atanmış **açık** işte (kapanınca görünmez) | Hepsi |
| `is.yukle` (rapor içe alma) | — | ✓ | — | ✓ |
| `is.ata`, `is.randevu`, `is.ticket`, `is.obek`, `is.iletisim` | — | ✓ | — | ✓ |
| `is.durum` | — | Her geçiş | Kendi işinde yalnız: Yolda, Sahada, Çözüldü, Ulaşılamadı | Her geçiş |
| `is.olustur` (bayi iş emri, F16) | ✓ (talep; triyaja düşer) | ✓ | — | ✓ |
| `is.excel` (müşteri sütunlu) | — | ✓ (kayda geçer) | — | ✓ (kayda geçer) |
| `obek.oku` | — | ✓ | Yalnız kendi öbeğinin adı | ✓ |
| `obek.duzenle`, `mahalle.ekle` | — | ✓ | — | ✓ |
| `ticket.*` (defter) | Ticket metni şablonu (bugünkü gibi) | ✓ | Kendi işinin binasındaki ticket'ı okur | ✓ |
| `takip.oku` (yönetici paneli) | — | ✓ | — | ✓ |
| `ekip.*` (kişi ekle, düzenle, PIN, pasife al, sil) | — | — | — | ✓ |
| Veri: tur raporu, veri kalitesi, OneMap | — | — | — | ✓ |

**Bugünkü sızıntıların kapatılması.** Denetimde kopyada ölçüldü: bölgesi NULL olan `teknik` hesabı 19.706 binayı gördü ve 3. bölgeye ziyaret yazabildi. Düzeltmeler:

1. `_bolge_kontrol(k, bolge)` üç duruma ayrılır:
   - `yonetici` ve `operasyon` → istenen bölge ya da hepsi (None).
   - `satisci` → kendi bölgesi. **Bölgesi NULL ise 403 `bolge_yok`**: "Size henüz bölge atanmadı. Yöneticinize başvurun."
   - Diğer her rol (teknik, bilinmeyen) → 403 `yasak`.
2. `bina_detay`, `_bina_yetkili` ve `_ziyaret_isle` içindeki `if rol == 'satisci'` kalıpları kaldırılır. Yerine `yetki.bina_gorebilir(k, serial)` ve `yetki.ziyaret_yazabilir(k, serial)` gelir; ikisi de izin listesiyle çalışır. Ziyaret yazma yalnız satış ve yöneticiye açıktır.
3. `/api/ben` her rol için kendi dalını döner ve `ana_ekran` alanını taşır (`bugun` · `isler` · `islerim`). Bilinmeyen rol 403 alır.
4. İş emri yönlendiricisi `Depends(yonetici)` yerine eylem bazlı `izin(...)` kullanır.

### 1.3 Müşteri bilgisi (F21) ile OPERASYON_TASARIM §6.5'in uzlaştırılması

§6.5 "müşteri adı maskelenir, telefon sisteme girmez" diyor. F21 ise "operasyon müşteri bilgilerine erişebilmeli ki randevu alabilsin, ekibe atayabilsin" diyor. Karar önerisi: **rol bazlı açık erişim, kayıt ve süre sınırı.**

| Alan | Nereden gelir | Kim görür | Ne zaman silinir |
|---|---|---|---|
| Müşteri adı, Müşteri No | BOSS raporu (B, C sütunları) | Operasyon, Yönetici; Teknik kendi açık işinde; Satış kendi açtığı işte | İş kapandıktan 30 gün sonra alan boşaltılır (NULL) |
| Adres (tam) | BOSS (G) | Aynı | Kapanış + 30 gün |
| Telefon | BOSS'ta yok (Superbox GSM No boş). **Yalnız operasyonun elle girdiği**, isteğe bağlı | Operasyon, Yönetici; Teknik kendi açık işinde | Kapanış + 30 gün |
| İl, ilçe, mahalle, bina, Task No, task adı | BOSS | Rolün iş listesine göre | Silinmez (sayım ve takip için) |
| Ham rapor dosyası | Yükleme | Diskte, yalnız sunucu | 7 gün sonra silinir (§6.5 ile aynı) |

Kurallar:

- **Görüntüleme kaydı** (`erisim_kaydi`): liste isteği tek satır ve kaç müşteri döndüğünü yazar. İş kartı açılışı, Excel indirme ve telefonu gösterme de kayda geçer. Kayıt silinemez.
- Olay defterine (§4.1) **kişisel veri değeri yazılmaz**. Örneğin telefon değişince yalnız "iletisim: musteri_tel değişti" yazar.
- Rapor ve yönetici panosu yalnız toplam sayı gösterir.
- Telefonun sisteme girmesi açık bir karardır (açık soru 2). Varsayılan **açık** ama `ayar.musteri_tel = 'kapali'` ile alan tamamen gizlenir ve kabul edilmez.

### 1.4 Mevcut kişiler yeni rolüne nasıl geçer

1. Güncellemede **hiçbir kişinin rolü kendiliğinden değişmez**. Tahmin yapılmaz. Göç yalnız izin verilen değer listesini genişletir. `oturum_no`, `pin_hash`, `telefon` ve `davet_kodu` alanlarına dokunulmaz; açık telefonlar oturumda kalır (kopyada doğrulandı: eski jetonlar 200 döndü).
2. İlk açılışta Ekip ekranının üstünde bir kez şu şerit çıkar: "**Görevler artık dört çeşit.** 8 kişi 'Yönetici' görünüyor. Her birinin görevini kontrol edin." Her satırda dört seçenekli bir seçici bulunur: Satış · Operasyon · Teknik · Yönetici.
3. Görevi değişen kişinin `oturum_no` değeri artar. O kişi telefonda bir kez yeniden giriş yapar; **PIN'i değişmez**. Ekran bunu önceden söyler: "Bu kişi bir kez yeniden giriş yapacak. PIN'i aynı kalır."
4. Korumalar:
   - Kişi kendi rolünü düşüremez, kendini pasife alamaz, kendini silemez.
   - Son aktif yönetici düşürülemez, pasife alınamaz ve silinemez: 409 `son_yonetici`.
5. Teknik kişinin formunda "BOSS'taki ekip adı" alanı (`boss_ekip`) vardır. İçe aktarımda BOSS'ta Ekip'i dolu iş bu kişiye bağlanır (§2.3). Bugün 258 işte Ekip dolu.

### 1.5 Etiketler

`kullanici.etiket` bir JSON listedir ve yalnız süzgeç ve görünüm içindir:

- Teknik: `lider` (teknik lider)
- Operasyon: `triyaj`, `btk`, `arama`, `altyapi`, `lojistik`, `vardiya`

Yetki hiçbir zaman etiketten gelmez.

---

## 2. İş emrinin yaşam döngüsü

### 2.1 Durumlar

Kodlar KARMA-2'nin S0–S6 ve E1–E6 kodlarıyla eşleşir (OPERASYON_TASARIM §3.2). Ekranda 12 durum dört kovada görünür: **Atanmadı · Teknikte · Beklemede · Biten**.

| Kod (DB) | Ekranda | Kova | KARMA-2 | Sahibi | Süre bütçesi |
|---|---|---|---|---|---|
| `triyaj` | Kontrol gerekli | Atanmadı | S1 (bağlanamadı) | Operasyon (triyaj) | ≤15 dk |
| `bekliyor` | Atanmadı | Atanmadı | S1 | Operasyon | **≤15 dk** (gelişten atamaya) |
| `randevulu` | Randevu verildi | Atanmadı | S2 (dilim teyitli) | Operasyon | Atama dilimden önce |
| `atandi` | Atandı | Teknikte | S2 | Teknik | Kesim kuralına göre (§3.3 OT) |
| `yolda` | Yolda | Teknikte | S3 | Teknik | ≤60 dk / BTK ≤45 dk |
| `sahada` | Sahada | Teknikte | S4 | Teknik | ≤120 dk / BTK ≤90 dk |
| `ulasilamadi` | Ulaşılamadı | Beklemede | E1 | Operasyon (merdiven) | BTK 24 s, diğer 48 s |
| `askida` | Askıda | Beklemede | E2 | Operasyon | Uyanma zorunlu; BTK ≤1 gün, diğer ≤3 gün, müşteri talepli ≤7 gün |
| `altyapi` | Altyapı bekliyor | Beklemede | E3 | Operasyon + ticket | Ticket'a bağlı |
| `merkeze` | Merkeze gönderildi | Beklemede | E3 / BOSS | Operasyon | BOSS'a bağlı |
| `cozuldu` | Çözüldü | Biten | S5 / E5 | Sistem (BOSS teyidi bekler) | Sonraki rapor |
| `kapandi` | Kapandı | Biten | S6 | Sistem | — |

**Randevu bir durum değil, bir alandır.** KARMA-2 "aramasız sevk" der: iş randevusuz da doğrudan öbeğin teknisyenine atanabilir. F10 ise "operasyon randevular → tekniğe atar → teknik yapar" der. İki yol da geçerlidir:

- Randevu verilip atanmayan iş `randevulu` durumunda bekler.
- Randevuyla atanan iş `atandi` olur ve randevu saati iş satırında görünür.

**Bayraklar** (durumdan bağımsız):

- `tekrar7g`: aynı Müşteri No ve aynı Task Adı 7 gün içinde kapanmış bir işte görüldü (E6). Rozet "Tekrar" çıkar; telefonla kapatma kapalıdır.
- `ticket_id` / binada açık ticket: rozet "Ticket" (§2.5).
- `boss_bekleyen`: bizim atama ya da randevumuz BOSS'a henüz işlenmemiş (§2.3.4).
- `triyaj_nedeni`: `il_disi` · `mahalle_yok` · `obeksiz`.

### 2.2 Geçişler

Tablodaki satır dışındaki her geçiş 409 `gecersiz_gecis` döner. Mesaj: "Bu iş 'Çözüldü' durumunda; 'Yolda' yapılamaz."

| Nereden | Nereye | Kim | Zorunlu alan |
|---|---|---|---|
| (yok) | `triyaj` / `bekliyor` / BOSS'un söylediği | Sistem (içe aktarım) | — |
| (yok) | `triyaj` | Satış / Operasyon / Yönetici (bayi işi, F16) | Task türü, adres ya da bina |
| `triyaj` | `bekliyor` | Operasyon (öbeğe ata / mahalle seç) ya da sistem (öbek sonradan tanımlandı) | Öbek |
| `bekliyor`, `triyaj` | `randevulu` | Operasyon | Randevu (başlangıç, bitiş) |
| `bekliyor`, `randevulu`, `triyaj`, `ulasilamadi`, `askida` | `atandi` | Operasyon; sistem (BOSS Ekip → tanınan teknik) | Teknik kişi. Randevu isteğe bağlı |
| `atandi` | `atandi` (başka teknik) | Operasyon | Yeni teknik |
| `atandi` | `yolda` | Teknik (kendi işi), Operasyon, sistem (BOSS "Konum Paylaşıldı") | — |
| `atandi`, `yolda` | `sahada` | Teknik, Operasyon, sistem (BOSS "Başlandı") | — |
| `atandi`, `yolda`, `sahada` | `cozuldu` | Teknik | **"Evde miydi?"** (KARMA-2 kural 17), sonuç kodu |
| Açık her durum | `cozuldu` (ofisten) | Operasyon | Neden: `telefonda_cozuldu` (canlı test onayı), `iptal`, `mukerrer`. `tekrar7g` işinde `telefonda_cozuldu` yasaktır |
| `atandi`, `yolda`, `sahada` | `ulasilamadi` | Teknik ("Evde yok"), Operasyon | Deneme notu; `evde_yok_sayisi` +1 |
| `ulasilamadi` | `randevulu` / `atandi` | Operasyon (merdiven sonucu) | Randevu ya da teknik |
| Açık her durum | `askida` | Operasyon; sistem (BOSS "Askıya alındı") | Neden + **uyanma zamanı**; üst sınırlar §2.1'deki gibi |
| `askida` | `bekliyor` | Sistem (uyanma zamanı geldi) ya da Operasyon | — |
| Açık her durum | `altyapi` | Operasyon | **Ticket bağlı** (`ticket_id`) |
| `altyapi` | `bekliyor` | Sistem (ticket ÇÖZÜLDÜ/KAPATILDI) ya da Operasyon | — |
| Açık her durum | `merkeze` | Operasyon; sistem (BOSS "Merkeze gönderildi") | Neden |
| `cozuldu` | `atandi` | Operasyon ("Yeniden aç") | Neden |
| Her durum | `kapandi` | **Yalnız sistem**: iş BOSS açık listesinden düştü | — |
| `kapandi` | BOSS'un söylediği / `bekliyor` | **Yalnız sistem**: iş yeniden göründü | `acilma_sayisi` +1 |

"Açık her durum" demek `kapandi` ve `cozuldu` dışındaki her durum demektir.

### 2.3 BOSS ile uzlaşma (her içe aktarımda)

BOSS'un bildiği alanlar (`boss_*` sütunları) her aktarımda **üzerine yazılır**. Operasyon bu alanlara yazamaz. Bizim akışımızı ilgilendiren kararlar:

1. **İleri doğru kural.** BOSS durumu bizim durumumuzdan "ilerideyse" durum ilerletilir. Sıra: Açık → Konum Paylaşıldı (`yolda`) → Başlandı (`sahada`). Olay `durum` yazılır; kullanıcı NULL, not "BOSS". Geri gitme yoktur: BOSS "Açık" dese de bizdeki `sahada` korunur.
2. **İstisnalar.**
   - BOSS "Askıya alındı" dediğinde bizde iş `triyaj`, `bekliyor`, `randevulu` ya da `atandi` ise iş `askida` olur. Uyanma BOSS'ta yoksa hijyen listesine düşer: "Askıda, uyanma yok".
   - BOSS "Merkeze gönderildi" → `merkeze`.
   - Bizde `ulasilamadi`, `altyapi` ya da `askida` ise **bizim bilgimiz korunur**.
3. **Ekip eşleşmesi.** İş BOSS'ta "Açık" ve Ekip dolu, bizde atanmamış, Ekip adı bir `teknik` kişinin `boss_ekip` alanıyla eşleşiyor: iş `atandi` olur ve o kişiye bağlanır. Olay notu "BOSS'ta atanmış". Eşleşmezse iş `bekliyor` kalır ve satırında "BOSS ekibi: …" yazar (yalnız operasyon ve yönetici görür).
4. **BOSS'a işlenecekler (giden kutusu).** Sistem Turkcell sistemlerine **yazmaz** (OPERASYON_TASARIM §6.1 kırmızı çizgi). Bizde yapılan atama ya da randevu BOSS'taki Ekip ya da dilimden farklıysa işe `boss_bekleyen` bayrağı konur: `ekip`, `randevu` ya da ikisi. Panoda "BOSS'a işlenecek · 7" süzgeci vardır; her satırda Task No, Ekip ve dilimi kopyalama düğmesi bulunur. Sonraki aktarımda BOSS eşleşirse bayrak kalkar ve olay yazılır: "BOSS'ta işlendi".
5. **Listeden düşen.** Açık bir BOSS işi yeni raporda yoksa `kapandi` olur:
   - `kapanis` = aktarım zamanı. Gerçek an bilinmez; `kapanis_kesin = 0` olarak işaretlenir.
   - `kapanis_nedeni` bizde `cozuldu` idiyse `cozuldu_dogrulandi`, değilse `boss_listeden_dustu` olur.
6. **Yeniden açılan.** `kapandi` iş yeni raporda varsa:
   - Durum 1–3 kurallarıyla yeniden hesaplanır.
   - `acilma_sayisi` +1, `kapanis` = NULL.
   - `gorulme_zamani` = şimdi, `ilk_atama_zamani` = NULL. Böylece 15 dakika saati yeniden başlar.
   - Olay yazılır: `yeniden_acildi`.
7. **Çelişki.** Bizde `cozuldu` olan iş, arka arkaya 2 raporda BOSS'ta hâlâ açıksa `boss_kapanmadi` bayrağı konur. Takip panelinin hijyen listesine düşer: "Çözüldü ama BOSS'ta açık".
8. **Tekrar.** Yeni gelen işin (Müşteri No, Task Adı) çifti son 7 günde kapanmış bir işte varsa `tekrar7g = 1` olur.

### 2.4 Saatler

| Saat | Tanım | Nerede görünür |
|---|---|---|
| `acilis` | BOSS "Task Başlangıç Tarihi". Bayi işinde oluşturma anı | İş kartı |
| `son24` | `acilis + 24 s`: bayinin sözü, tavan | **Kalan süre** her satırda |
| BTK hedefi | `acilis` + TV 6 s, Bağlantı/Arama 12 s, Doping 24 s (OT §2.4 kural 2) | BTK rozetinin rengi; iş kartında "BTK hedefi 21:40" |
| `gorulme_zamani` | İşin sisteme ilk girdiği an (içe aktarım ya da oluşturma); yeniden açılınca yenilenir | "12 dk önce geldi" |
| `ilk_atama_zamani` | O açılış döneminde ilk `atandi`, ofisten `cozuldu` ya da `altyapi` anı | **F17 ölçüsü**: atama süresi = `ilk_atama_zamani − gorulme_zamani` |
| Rapor tazeliği | Son uygulanan aktarımın zamanı | Pano başlığı: "Son rapor 11:38 · 2 s önce". Mesai içinde 4 saati aşarsa amber, 6 saati aşarsa kırmızı |

**Kalan süre rengi.** Oranlar `son24`'e göre hesaplanır:

- Yeşil: geçen süre < %50
- Amber: ≥ %50
- Kırmızı: ≥ %80
- "Gecikti · 17 s" (kırmızı, kalın): süre aşıldı

BTK işinde BTK hedefi aşıldıysa rozet kırmızı olur.

**Sıralama (varsayılan):**

1. BTK işleri: BTK hedefine göre artan.
2. Diğerleri: `son24`'e göre artan.

Bu, KARMA-2 kural 5'in "aşırı yük" sırasının sade hâlidir (kota ve "en yakın 5" bu turda yok). Satır başındaki sıra numarası gösterilmez; renk ve süre yeterlidir.

**15 dakika hedefi (F17).**

- Atanmamış her iş satırında "geleli 12 dk" yazar. 10 dakikada amber, 15 dakikada kırmızı olur.
- Pano başlığında "Atanmamış 7 · en eskisi 23 dk" görünür.
- Takip panelinde bugünkü ve son 7 günün atama süresi medyanı ve "%82'si 15 dk içinde" oranı yer alır.
- Rapor tazeliği ayrıca gösterilir, çünkü 3 saatlik bir raporla 15 dakika hedefi tutturulamaz. Bu dürüstçe söylenir.

### 2.5 Ticket bayrağı (F9)

- **Binada açık ticket.** İş kartında ve satırda "Ticket" rozeti çıkar. İş bağlanmamış olsa da çıkar. Kaynak: `ticket.bina_serial = is_emri.bina_serial` ve durum `AÇIK`, `HATA` ya da `TRANSFER`.
- **İşe bağlama.** İş kartında "Ticket bağla" açılır:
  - Aynı binanın açık ticket'larından biri seçilir ya da "Yeni ticket" açılır. Yeni ticket için mevcut `YeniTicketPenceresi` kullanılır; bina ve konu önceden dolu gelir.
  - "Teknisyen gönderilmesin" anahtarı açıksa (varsayılan açık, OT kural 11) iş `altyapi` olur.
- **Ticket çözülünce.** Ticket ÇÖZÜLDÜ ya da KAPATILDI olunca bağlı işler `bekliyor` durumuna döner (OT §3.6 adım 5). Olay yazılır ve bu işler "Atanmadı" listesinin başına geçer.
- **Rapor.** Ticket ile iş arasındaki bağ `is_emri.ticket_id` alanında tutulur. Bir ticket'a birden çok iş bağlanabilir. Takipte "ticket'a bağlı iş: 14 · en yaşlı ticket 3 gün" görünür.

### 2.6 Akış çizimi

```
BOSS raporu ─► İÇE AKTARIM ─┬─► Kontrol gerekli (triyaj) ──öbeğe ata──┐
(ya da bayi işi)            └─► Atanmadı ◄──────────────────────────────┘
                                 │  └──randevu ver──► Randevu verildi ──┐
                                 └──tekniğe ata (öbeğin teknisyeni hazır)┴─► Atandı
                                                                       │
                          Teknik (telefon):  Yola çıktım ─► İşe başladım ─► Bitti ─► Çözüldü
                                                 └──────── Evde yok ─► Ulaşılamadı ─► (masa) ─► Randevu / Atandı
   Operasyon: Askıya al (uyanma) · Altyapı (ticket) · Merkeze gönder · Ofisten kapat (neden)
   Sonraki rapor: listede yok ─► Kapandı      ·      yeniden göründü ─► Yeniden açıldı
```

---

## 3. Ekranlar

### 3.0 Bilgi mimarisi

**Yönetim menüsü** (operasyon ve yönetici; operasyon yalnız izni olanları görür). Menü artık işi merkeze alır:

```
İşler            ← operasyonun ve yöneticinin ana ekranı (F3, F7–F10, F17)
Öbekler          ← öbek düzenleyici (F1, F2)
Takip            ← yönetici paneli (F11, F15, F17)
Ticketlar
Ekip             ← yalnız yönetici (F12, F13)
Satış ▸          Canlı · Kapsama · Görev atama · Rapor           (yalnız yönetici)
Veri ▸           Rapor geçmişi · Bölge planlayıcı · Tur raporu · Veri kalitesi
```

- **Masaüstü (≥1024 px):** 232 px sol menü. Grupların ("Satış ▸", "Veri ▸") başında ok vardır ve açılıp kapanır; son hâl cihazda hatırlanır.
- **Telefon (<768 px):** Alt sekme çubuğu 4 öğelidir: **İşler · Öbekler · Takip · Daha fazla**. "Daha fazla" düz bir listedir: Ticketlar, Ekip, Satış, Veri, Saha uygulaması, Çıkış. Üstte 44 px başlık çubuğu olur. Bugünkü yapışkan menü bloğu (ekranın %35'i) kalkar.
- **Teknik:** Alt çubuk 2 öğelidir: **İşlerim · Ben**.
- **Satış:** Bugünkü uygulama olduğu gibi kalır (Bugün · Harita · Ben). "Ben" ekranına "Talep aç" girişi eklenir (§3.10).
- **Gösterim verisi uyarısı.** Sarı "GÖSTERİM VERİSİ" bandı yalnız demo ziyaret kullanan satış ekranlarında kalır ve küçük bir hapa dönüşür. İşler, Öbekler, Takip ve Ticketlar gerçek veridir; bantları kalkar.

### 3.1 İşler: operasyon panosu

**Masaüstü (≥1440 px), üç bölme:**

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│ İşler                    Açık 437 · 24 saati aşan 288 · Atanmamış 61 (en eskisi 23 dk)       │
│                          BTK 48 s aşan 5            [Son rapor 11:38 · 2 s önce]  [Rapor yükle]│
├─────────────────────┬──────────────────────────────────────────┬─────────────────────────────┤
│ ÖBEKLER             │ Dumlupınar · 65 iş        [Ara…] [Süz ▾] │ İŞ KARTI (§3.2)             │
│ Tümü           437  │ Atanmadı 12 · Teknikte 40 · Beklemede 13 │                             │
│ Kontrol gerekli  3 ●│ ──────────────────────────────────────── │                             │
│ BOSS'a işlenecek 7  │ ● 2 s 10 dk  BTK  Bağlantı Problemi      │                             │
│ ─────────────────── │   Müşteri adı · Mahalle, kısa adres      │                             │
│ Dumlupınar  65 ·9 ·4│   Atanmadı · geleli 12 dk        Ticket  │                             │
│ Görükle     31 ·9 ·2│ ● 7 s        Modem Değişikliği           │                             │
│ …                   │   Müşteri adı · …   Atandı · T. A · 10–12│                             │
│ Öbeksiz · Mudanya 7 │ …                                        │                             │
│ Gürsu        0      │                                          │                             │
└─────────────────────┴──────────────────────────────────────────┴─────────────────────────────┘
```

- **Başlık şeridi.** Tek satır, sakin yazı. Sayıların her biri tıklanabilir ve listeyi süzer. "Rapor yükle" ikincil düğmedir; dosya ekrana sürüklenerek de bırakılabilir (§3.6).
- **Öbek sütunu (264 px).**
  - Her satır: öbek adı + üç sayı: *açık · geciken (24 s aşan) · BTK*. Sağda atanmamış iş varsa küçük bir nokta.
  - Özel satırlar üstte:
    - "Tümü"
    - "Kontrol gerekli" (triyaj; 0 ise gizli)
    - "BOSS'a işlenecek" (0 ise gizli)
    - "Konum yaklaşık" (ilçe ya da mahalle merkezindeki işler; bilgi süzgeci)
  - Özel satırlar altta: "Öbeksiz · <ilçe>" satırları.
  - **İşi 0 olan öbekler de görünür** (soluk). Böylece hiçbir öbek "kaybolmaz" (F1, F2).
  - Öbek adına tıklamak listeyi o öbekle süzer (F3). Satırın sağındaki "…" menüsünde "Öbeği düzenle" (→ §3.4) ve "Parçalara böl" bulunur.
- **İş listesi.**
  - Satır üç bilgiden oluşur:
    1. Kalan süre hapı (renkli) + BTK rozeti + task adı
    2. Müşteri adı · mahalle, kısa adres (yetkiye göre)
    3. Durum yazısı (renksiz, küçük nokta) · randevu dilimi · teknisyen baş harfleri · rozetler: Ticket, Tekrar, Bayi, BOSS'a işlenecek
  - Satır yüksekliği 72 px, tek tık hedefi.
  - Varsayılan sıra §2.4'teki gibidir.
  - Kovalar segment olarak listenin üstündedir: **Atanmadı · Teknikte · Beklemede · Biten**. Varsayılan "Atanmadı".
- **Süz** tek düğmedir. Açılan menüde şunlar vardır: İlçe, Task türü, Şerit (BTK/Saha/Masa/Lojistik), Teknisyen, Kaynak (Global/Bayi), "Randevusu bugün", "Tekrar". Etkin süzgeçler aramanın yanında kaldırılabilir çipler olarak görünür. Bugünkü 33 çip ve öbek seçicisi kalkar.
- **Harita** listeye alternatiftir: "Liste | Harita" düğmesi. Merkez değildir. Bugünkü `IsHaritasi` kullanılır.
- **Parçalara böl** (C21): öbek menüsünden açılan bir penceredir, sayfayı yeniden dizmez.
  - Parça sayısı önerisi: ⌈saha yükü / 15⌉.
  - Önizleme haritası gösterilir.
  - Her parçaya bir teknik seçilir, sonra "Parçaları ata" (toplu atama, §4.6).
  - Yöntem seçimi "Mahalleye göre / Binaya göre" yerine sade söz kullanılır: "Bugünkü ekiplere dağıt".

**1024–1439 px:** Öbek sütunu + liste görünür. İş kartı sağdan üste kayar (liste solar); Esc ile kapanır.

**Telefon (<768 px): itmeli gezinme.**

- **1. ekran, İşler:** Başlık şeridi 2 satıra kırılır. Altında öbek listesi (tam genişlikte satırlar) ve özel satırlar gelir.
- **2. ekran, öbeğin işleri:** Kova segmenti, arama ve "Süz" vardır. Satırlar 2 satırdır.
- **3. ekran, iş kartı:** Tam ekran. Birincil eylem alttaki yapışkan çubukta durur (56 px).
- İç içe kaydırma alanı yoktur. Her ekranda tek bir liste vardır.

### 3.2 İş kartı

Masaüstünde sağ panel, telefonda tam ekrandır. Bölümler yukarıdan aşağıya:

1. **Başlık:** task adı · BTK rozeti · kalan süre (büyük) · durum yazısı · kaynak rozeti (Global / Bayi). Altında ince bir adım çizgisi: *Geldi → Atandı → Yolda → Sahada → Çözüldü*.
2. **Müşteri** (yetki varsa):
   - Ad.
   - Müşteri No [Kopyala]. BOSS/Maya'da aramak içindir.
   - Telefon: [Ekle] ya da numara + [Ara] (tel: bağlantısı).
   - Adres [Kopyala] · [Konumu aç]. Koordinatla açılır (A5).
   - Task No [Kopyala]. `ayar.boss_task_url` tanımlıysa [BOSS'ta aç] da çıkar.
3. **Yer:**
   - Mahalle ve kaynağı: "Location Id'den" / "Adresten" / "Elle".
   - Bina adı ve Location Id; "Binayı aç" (bina ayrıntısı, açık ticket'lar, veri notları).
   - Öbek: "Dumlupınar" + [Öbeğe taşı] (F5). Elle taşınmışsa "elle" etiketi çıkar.
4. **Randevu:**
   - BOSS'taki randevu (salt okunur, "BOSS: 30.09 10:00–12:00").
   - Bizim randevumuz: gün çipleri (Bugün · Yarın · Tarih seç) + dilim çipleri (08–10 · 10–12 · 12–14 · 14–16 · 16–18 · 18–20) + "Randevu yok".
   - BTK teşhis araması sonucunda "Şimdi evde" seçilirse 3 saatlik pencere kendiliğinden yazılır (OT kural 4b).
5. **Teknisyen:**
   - Öbeğin sahibi (ev teknisyeni) **önceden seçili** gelir (KARMA-2 kural 3: aramasız sevk).
   - Liste: teknik kişiler, her birinin yanında bugünkü iş sayısı ve "kendi öbeği" işareti.
6. **Ticket** (§2.5): rozet + ticket durumu + [Ticket bağla / aç].
7. **BTK teşhisi** (yalnız BTK işinde, OT kural 4):
   - "Arandı mı?" altında tek dokunuşla sonuç: *Düzeldi (canlı test yapıldı)* · *Şimdi evde* · *Başka gün* · *Cevapsız* · *Kapalı* · *Yanlış numara*.
   - "Düzeldi" seçilince iş ofisten çözülür. `tekrar7g` işinde bu seçenek kapalıdır.
8. **BOSS bilgisi** (katlanır): BOSS durumu, Ekip, randevu durumu, askı nedeni, SL, son açıklama.
9. **Notlar:** tek satırlık ekleme; notlar zaman ve kişiyle listelenir.
10. **Geçmiş:** olay defteri, yeniden eskiye. "14:02 · Operasyon 2 · Teknisyen A'ya atadı · randevu 10–12".

**Alt çubuk: duruma göre tek birincil eylem** ("Diğer" menüsünde kalan izinli eylemler):

| Durum | Birincil | İkincil |
|---|---|---|
| Kontrol gerekli | **Öbeğe ata** | Mahalleyi seç · Ofisten kapat |
| Atanmadı | **Tekniğe ata** | Randevu ver · Ticket bağla · Askıya al |
| Randevu verildi | **Tekniğe ata** | Randevuyu değiştir |
| Atandı / Yolda / Sahada | — (takipte) | Başka tekniğe ver · Randevuyu değiştir · Ticket bağla |
| Ulaşılamadı | **Yeniden randevu ver** | Tekrar gönder · Askıya al |
| Askıda | **Uyandır** | Uyanmayı değiştir |
| Altyapı bekliyor | **Ticket'ı aç** | Ticket'tan ayır |
| Çözüldü | — ("BOSS'ta kapanması bekleniyor") | Yeniden aç |

Hangi düğmelerin görüneceğine sunucu karar verir: yanıttaki `izinler` alanı. İzin yoksa düğme hiç çizilmez.

**Çakışma (§4.7).** Kaydederken 409 `guncel_degil` dönerse kart yenilenir ve üstte sarı bir satır çıkar: "Bu iş siz bakarken değişti: 14:02'de Operasyon 2, Teknisyen A'ya atadı." Kullanıcının seçimi kaybolmaz; "Yine de uygula" ile yeniden gönderilebilir (yeni sürümle).

### 3.3 Ata · Randevu · Öbeğe taşı · Ofisten kapat

- **Ata:** İş kartındaki teknisyen bölümü doğrudan kullanılır; ayrı pencere yoktur. "Ata" düğmesi seçimi uygular. Başarılı olunca bildirim çıkar: "Teknisyen A'ya atandı · Geri al (10 sn)". Geri al, yeni bir olayla önceki hâle döner.
- **Randevu:** Çip seçimi anında kaydedilmez; "Randevu ver" ile kaydedilir. Kurallar:
  - Bitiş başlangıçtan sonra.
  - Dilim en çok 4 saat.
  - Geçmişe en fazla 1 saat, ileriye en fazla 7 gün (E2).
- **Öbeğe taşı** (F5):
  - Öbek listesi açılır (arama + "Öbeksiz bırak").
  - Seçilen öbek `obek_elle_id` alanına yazılır. **Sonraki raporlarda da korunur.**
  - Kartta "elle" etiketi görünür. "Mahallesine göre" ile geri alınır.
- **Ofisten kapat:**
  - Neden zorunludur: Telefonda çözüldü (canlı test onayı) · İptal · Mükerrer · Müşteri vazgeçti.
  - Onay penceresinde uyarı yer alır: "BOSS'ta da kapatmayı unutmayın."

### 3.4 Öbek düzenleyici (F1, F2)

Öbekler menüsünden ya da pano öbek satırındaki "Öbeği düzenle"den açılır. Masaüstünde sağ panel, telefonda tam ekrandır.

```
Dumlupınar                                        [Adı değiştir]
Ev teknisyeni: Teknisyen A ▾          65 açık iş · 9 geciken · 4 BTK

MAHALLELER (4)                                     [+ Mahalle ekle]
Bursa / Nilüfer / Dumlupınar                 38 iş          [×]
Bursa / Nilüfer / Ertuğrul                   12 iş          [×]
Bursa / Nilüfer / Esentepe                    9 iş          [×]
Bursa / Gürsu / tamamı                        0 iş          [×]
───────────────────────────────────────────────────────────
Öbeği sil
```

- **Mahalle listesi:** Öbekteki her mahalle bir satırdır. Satırda il/ilçe/mahalle, **bugünkü açık iş sayısı** (0 da yazılır) ve × düğmesi bulunur.
  - × düğmesi mahalleyi öbekten hemen çıkarır. Bildirim çıkar: "Ertuğrul çıkarıldı · Geri al".
  - O mahalledeki işlerin öbeği aynı işlemde yeniden hesaplanır. Pano sayıları **sayfa yenilenmeden** güncellenir (F1 kabulü).
- **Mahalle ekle** tam listeli bir seçicidir (F2):
  - Arama kutusu ve ilçeye göre gruplu liste.
  - Bursa'nın 17 ilçesi ve Yalova'nın 6 ilçesi görünür. **Rapordan bağımsızdır**; kaynak mahalle sözlüğüdür (§4.4).
  - Her ilçenin ilk satırı "**İlçenin tamamı**"dır (ör. Gürsu / tamamı).
  - Her mahalle satırında şu an hangi öbekte olduğu yazar ("Beşevler öbeğinde") ve bugünkü iş sayısı görünür.
  - Çoklu seçim yapılabilir, ardından "Ekle (3)".
  - **"Listede yok mu?"**: il, ilçe ve mahalle adı yazılır; sözlüğe `elle` kaynaklı eklenir ve "elle eklendi" etiketi taşır. Göçmen bugün bu yolla eklenir. Rapora ilk düştüğü gün iş kendiliğinden öbeğine girer.
  - Yazım yakınsa öneri çıkar: "Taşlimanı mı demek istediniz?" (sözlükte benzer anahtar).
- **Başka öbekteki mahalle** seçildiyse ekleme sırasında satır içinde sorulur: "**Beşevler şu an 'Yıldırım' öbeğinde.** Buraya taşınsın mı?" → [Taşı] [Atla]. Sessiz taşıma yoktur (denetim bulgusu).
- **Boş öbek** artık kendiliğinden silinmez. Öbeksiz mahalleler kendi satırında listelenir.
- **Yeni öbek:** Öbekler ekranının başındaki "+ Yeni öbek" düğmesi önce yalnız ad sorar, sonra düzenleyici açılır. Ad benzersizdir; Türkçe harf ve büyük/küçük harf duyarsız karşılaştırılır. Var olan ada yeniden adlandırma 409 döner: "Bu adla bir öbek var." Sessiz birleştirme yoktur.
- **Ev teknisyeni** (`obek.sahip_id`): "Tekniğe ata"da önceden seçilen kişidir (KARMA-2 kural 3 ve 7).
- **Öbeği sil:** Onay penceresinde "Mahalleleri öbeksiz kalır; işler 'Öbeksiz' satırına düşer" yazar. Silindikten sonra 10 sn boyunca "Geri al" çıkar ve kayıt defterde kalır (yumuşak silme, §4.1).
- **Öbekler ekranı (liste):**
  - Masaüstünde tablo sütunları: Öbek · Mahalle sayısı · Açık · Geciken · BTK · Ev teknisyeni.
  - Telefonda satırlar.
  - Üstte "+ Yeni öbek" ve "Öbeksiz mahalleler (N)" satırı (bugünkü raporda işi olan ama öbeği olmayan mahalleler; tek tıkla bir öbeğe eklenir).

### 3.5 Kontrol gerekli ve hatalı adres (F4, F5)

- F4 korunur: Location Id varsa OneMap binasının mahallesi esas alınır. Kontrol listesi yalnız gerçek sorunları içerir.
- Location Id eşlemesi **veritabanı üzerinden** yapılır (`ticket.lokasyondan_bina`: 8 haneye sıfırla, sıfırsız, "-1" eksiz). Bugün 332 Lokasyon'un 287'si bulunuyor; bu yolla 332/332 bulunur.
- "Kontrol gerekli" satırı yalnız şu nedenlerle dolar:
  - `il_disi`: "İl bölge dışı (İzmir)"
  - `mahalle_yok`: "Adresten mahalle bulunamadı"
  - `obeksiz`: "Mahalle bulundu, öbeği yok". Bu neden yalnız o mahalle bir öbeğe eklenene kadar geçerlidir; eklenince iş kendiliğinden `bekliyor` olur.
- Kontrol gerekli işin kartındaki birincil eylem **"Öbeğe ata"**dır (F5: İzmir diye gelmiş iş elle öbeğe eklenir). İkincil eylem **"Mahalleyi seç"**tir: sözlükten mahalle seçilir, öbek mahalleden gelir, kaynak "elle" olur.
- Her iki seçim de sonraki raporlarda korunur (`obek_elle_id`, `mahalle_elle`).
- "Konum yaklaşık" bir bilgi süzgecidir, iş akışını durdurmaz. Bugün 50 iş ilçe merkezinde, 46 iş mahalle merkezinde. Haritada halka olarak görünür. İş kartında "Konum yaklaşık: mahalle merkezi" yazar ve "Binayı seç" (bina arama) sunulur.
- Liste boşsa kart hiç görünmez. Başlıkta küçük yeşil bir hap çıkar: "Hepsi yerinde".

### 3.6 Rapor yükle ve rapor geçmişi (F18)

- **Bırak:** Dosya pano üstüne sürüklenir ya da "Rapor yükle" ile seçilir. Sunucu işler; ilerleme yazısı "Rapor okunuyor…" (≤5 sn) olarak görünür.
- **Sonuç** tek satırlık bir bildirimle gelir ve pano aynı anda güncellenir: "Rapor işlendi · **Yeni 12 · Değişen 30 · Kapanan 30 · Yeniden açılan 3 · Aynı 392** · çıkarılan: kurulum 1.072, 2. donanım 119." Bildirime tıklayınca ayrıntı açılır: çıkarılan task adları sayımı, kontrol gerekenler, süre.
- **Aynı dosya ikinci kez:** "Bu dosya 11:38'de zaten yüklenmişti. Hiçbir şey değişmedi." Veritabanına tek bir yazma bile yapılmaz.
- **Onay gereken iki durum** (onay penceresi, "Uygula / Vazgeç"):
  - **Çok iş düştü:** kaybolan > max(50, açık işlerin %25'i). Mesaj: "Bu raporda 180 açık iş yok (açık işlerin %41'i). Rapor eksik indirilmiş olabilir (süzgeçli ya da tek ilçe). Bu işler kapanmış sayılsın mı?"
  - **Eski rapor:** dosyanın tarayıcıdaki zamanı ya da içindeki en yeni Task Başlangıç Tarihi, son uygulanan rapordan eski. Mesaj: "Bu rapor en son yüklenenden (11:38) eski görünüyor. Yine de işlensin mi?"
- **Aynı anda iki yükleme:** İkincisi 409 alır: "Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin."
- **Rapor geçmişi** (Veri ▸ Rapor geçmişi): son 30 yükleme listelenir. Sütunlar: zaman · yükleyen · dosya adı · iş sayısı · yeni/değişen/kapanan/yeniden açılan · durum. Satır ayrıntısında uyarılar ve alınan yedeğin adı görünür.

### 3.7 Teknik: İşlerim (F7, F8, telefon öncelikli)

Satışçı uygulamasının "Bugün" ve "Bina" ekranları örnek alınır: sakin kart, tek birincil eylem, alttan açılan panel.

```
İşlerim · 30 Eylül Salı                         9 iş · 3 BTK
────────────────────────────────────────────────────────────
 10:00–12:00   BTK  TV+ Arıza                    kalan 3 s 10 dk
               Mahalle · kısa adres
 12:00–14:00        Modem Değişikliği            kalan 19 s
               Mahalle · kısa adres
 Randevusuz    BTK  Bağlantı Problemi            kalan 7 s
 …
```

- **Sıra:**
  1. Randevulu işler dilim başlangıcına göre (F8: "teknisyenin listesinde sıralı").
  2. Randevusuzlar §2.4 sırasıyla (BTK önce, sonra kalan süre).
- **İş ekranı:**
  - Task adı, müşteri adı (kendi açık işi), adres, randevu, kalan süre.
  - Bina adı + Location Id + binada açık ticket uyarısı: "Bu binada açık SİNYAL ticket'ı var. Operasyonla konuşun."
  - Operasyonun notları.
  - [Yol tarifi]: koordinatla açılır.
  - Telefon girilmişse [Ara].
- **Alt çubukta tek büyük düğme** (56 px), duruma göre değişir:

| Durum | Düğme |
|---|---|
| Atandı | **Yola çıktım** |
| Yolda | **İşe başladım** |
| Sahada | **Bitti** |

  - "Bitti"de iki soru sorulur: **"Müşteri evde miydi?"** (Evet/Hayır, zorunlu) ve sonuç kodu (Çözüldü · Cihaz değişti · Malzeme gerekli · Altyapı sorunu).
  - İkincil düğmeler: **Evde yok** (10 dk bekleme ve 2 arama hatırlatması; iş anında operasyonun "Ulaşılamadı" listesine düşer) · **Not ekle**.
- **Çevrimdışı:**
  - Durum düğmeleri önce telefona yazılır (mevcut `kuyruk` deseni), bağlantı gelince gönderilir.
  - Her yazma bir `istemci_id` taşır. Sunucu aynı kimliği ikinci kez işlemez (§4.8).
  - Bekleyen yazma varsa üstte ince bir şerit çıkar: "2 işlem gönderilmeyi bekliyor".
- **Görmediği şeyler:** Başkasının işi, satış verisi, müşteri geçmişi, kapanmış işin müşteri bilgisi.
- **Sahadan erişim.** Ekran ofis ağında ve ofis Wi-Fi'ında bugün çalışır. Sahadan (mobil veri) kullanım için şirket VPN'i ve HTTPS gerekir (OT karar 13, Faz 2). Pilot bu ön koşula bağlıdır.

### 3.8 Ekip (F12, F13)

- **Liste:**
  - Masaüstünde tablo: Kişi · Görev · Bölge / Öbek · Giriş · son etkinlik.
  - Telefonda satırlar: baş harf · ad · görev rozeti. Satıra dokununca kişi paneli açılır. Yatay kaydırma yoktur.
  - Telefon numarası maskelidir (`0532 ••• •• 06`). Tamamı kişi panelinde görünür.
- **Görev süzgeci:** segment olarak Tümü · Satış · Operasyon · Teknik · Yönetici.
- **Kişi paneli (form):**
  - Ad, telefon.
  - **Görev**: dört seçenekli segment, her birinin altında tek cümlelik açıklama:
    - Satış: "Bina listesi ve satış ziyaretleri. Kendi bölgesini görür."
    - Operasyon: "İş emirlerini dağıtır, randevu verir, müşteri bilgisini görür."
    - Teknik: "Yalnız kendisine atanan işleri görür ve durumunu işler."
    - Yönetici: "Her şeyi görür; ekip ve ayarları yönetir."
  - Göreve göre alanlar:
    - Bölge yalnız Satış'ta görünür ve zorunludur.
    - Teknik'te: ev öbekleri (çoklu), "BOSS'taki ekip adı", "Teknik lider" anahtarı.
    - Operasyon'da: masa etiketleri (isteğe bağlı).
  - Aktif anahtarı.
- **Davet kodu:**
  - Yalnız oluşturulduğu ya da sıfırlandığı an bir kez gösterilir; bugünkü "Davet kodu hazır" penceresi kullanılır.
  - Listede yalnız "Davet bekliyor" yazar.
  - Kod 48 saat geçerlidir (`davet_zamani`). Süresi dolunca "Yeni kod üret" çıkar.
- **Sil** (F13): Kişi panelinin en altında kırmızı "Kişiyi sil" düğmesi bulunur.
  - Önce sunucuya "ilişkiler" sorulur (`GET /api/kullanici/{id}/iliskiler`).
  - **Kaydı yoksa** onay penceresi açılır ("Bu kişi kalıcı olarak silinecek."). Silinir, listeden kalkar. Kimlik numarası bir daha kullanılmaz (AUTOINCREMENT + sequence korunur).
  - **Kaydı varsa** silme yapılmaz. Pencere şunu söyler: "**Bu kişi silinemez.** 312 ziyaret, 2 görev ve 3 açık iş kaydı var. Geçmiş kayıtlar korunmalı. Bunun yerine pasife alabilirsiniz: giriş yapamaz, listede soluk görünür." → [Pasife al] [Vazgeç].
  - **Açık işi varsa** "Pasife al"dan önce bir adım gelir: "Önce 3 açık işi başka teknisyene aktarın" → [İşleri aktar] (hedef kişi seçilir, toplu atama).
  - Kendini silme ve son yöneticiyi silme düğmesi hiç çizilmez; sunucu da 409 döner.
- `window.confirm` hiçbir yerde kalmaz. Onay her zaman uygulama içi penceredir; geri alınabilen işlemlerde "Geri al" bildirimi kullanılır.

### 3.9 Takip: yönetici paneli (F11, F15, F17)

Sade kartlar. Her sayı tıklanınca İşler'i o süzgeçle açar. Kişisel veri yoktur.

```
TAKİP · 30 Eylül                                         Son rapor 11:38
┌ 24 s uyumu (dün açılan) ┐ ┌ Açık iş ┐ ┌ 24 s aşan ┐ ┌ 48 s aşan BTK ┐ ┌ Atama süresi (bugün) ┐
│  %43   ▁▂▃▅ 7 gün        │ │  437     │ │ 288 ↘ 7 gün│ │  5 · en yaşlı 71 s│ │ medyan 9 dk · %82 ≤15 dk│
└──────────────────────────┘ └─────────┘ └───────────┘ └────────────────┘ └──────────────────────┘
KAPASİTE   Bugün saha talebi ~205 · Sahada 11 teknisyen × 15 = 165  →  AŞIRI YÜK · öneri +3 esnek   [11 −/+]
BTK        Bağlantı 12 s: %51 · TV 6 s: %48 · teşhis araması ≤45 dk: %—
ÖBEKLER    Öbek · Açık · Geciken · BTK · Atanmamış · Ev teknisyeni          (tablo)
TEKNİK     Kişi · Atanmış · Bugün biten · Evde yok · Yolda/Sahada           (tablo)
HİJYEN     Çözüldü ama BOSS'ta açık 4 · Askıda uyanma yok 12 · BOSS'a işlenecek 7 · Rapor 4 s'ten eski
SATIŞ      Bugün 214 kapı · 31 satış · 7/8 satışçı sahada · Satış taleplerinden açılan iş 2   [Canlı ▸]
```

- **24 s uyumu.** Dün açılan işlerden `son24`'ten önce çözülen ya da kapananların oranıdır.
  - Kapanma anı teknik "Bitti" dediyse olay zamanından alınır. Değilse raporda kaybolduğu zamandan alınır; bu bir üst sınırdır. Kesin olmayanların payı %30'u geçerse kartta "yaklaşık" yazar.
  - 7 günlük çizgi `takip_anlik` tablosundan gelir. Her aktarımda bir satır yazılır.
- **Kapasite göstergesi** (OT kural 5 ve 15):
  - Talep = bugün `son24`'ü dolacak açık saha ve BTK işleri + atanmamış işler.
  - Aktif teknisyen sayısı, yöneticinin sabah girdiği sayıdır (−/+). Varsayılan, bugün işi olan teknik kişi sayısıdır.
  - Talep > aktif × 15 ise **Aşırı yük** yazar.
  - Öneri = min(8, ⌈(talep − aktif × 15) / 15⌉).
- **Satış kartı (F15, ilk adım):**
  - Bugünkü ziyaret, satış ve sahadaki satışçı sayısı. Mevcut `/api/ozet/gun` kullanılır.
  - Satışçıların açtığı taleplerden kaç iş emri çıktığı.
  - "Canlı ▸" bağlantısı.
  - Satış yönetiminin geri kalanı (hedefler, "Satışlarım: kurulum durumu") OT Faz 3'tedir. Bu kart yalnız kancadır.
- Hedef çizgileri (OT §4.4) küçük gri çizgi olarak görünür; ör. 24 s aşan için 1. hafta <350.

### 3.10 Yeni iş emri: bayi ya da satış talebi (F16)

- **Kim açar:**
  - Operasyon ve yönetici: İşler başlığındaki "+ Yeni iş" düğmesi.
  - Satış: bina ekranında "Talep aç" (sinyal yok, ek kapasite, müşteri arızası; OT §5.7).
- **Form:**
  - Task türü: BOSS task adları listesi + "Diğer".
  - Bina: ad ya da Location Id ile arama, ya da bina ekranından hazır gelir. Bina yoksa adres + mahalle seçici.
  - Müşteri adı, Müşteri No (isteğe bağlı), telefon (isteğe bağlı).
  - Açıklama.
- **Kayıt:**
  - `kaynak = 'bayi'`.
  - Numara `B-260930-001` biçimindedir; BOSS'un 9 haneli numarasıyla karışmaz.
  - İş `triyaj` durumunda açılır. Öbek belliyse `bekliyor` olur.
  - Rozet "Bayi" çıkar.
- **BOSS'a bağlama:** Aynı iş sonra BOSS'ta açılırsa iş kartında "BOSS Task No'yu bağla" kullanılır. Sonraki rapor **aynı satırı** günceller; ikinci kayıt oluşmaz.
- **Kanal ayrımı** (F16 "global / dış kanal"):
  - BOSS'tan gelen her iş `kaynak = 'boss'` olur.
  - Ayrıca BOSS "Satış Kanalı" değerinden bir **kanal grubu** türetilir:
    - "GLOBAL…" ile başlayan → `global`
    - "DEHANET…" / "DEHA…" → `dehanet`
    - Başka bayi adları (…ECM, …KCM, şirket unvanları) → `diger_bayi`
    - "TURKCELL…" → `kurumsal`
    - Boş → `bos`
  - Bu eşleme açık soru 1 ile teyit edilecek. Rozet ve süzgeç buradan çalışır.

### 3.11 Giriş

- Fiziksel klavyeden rakam, Backspace ve Enter kabul edilir. Bugün ofis bilgisayarında 14 tıklama gerekiyor.
- Giriş sütunu en çok 360 px genişliktedir; "Devam" düğmesi bu sütunu aşmaz.
- Girişten sonra `/api/ben.ana_ekran` alanına göre yönlenir: `bugun` → `#/bugun`, `isler` → `#/yonetici/isler`, `islerim` → `#/islerim`.
- Tek marka işareti kullanılır: girişteki ve konsoldaki simge aynıdır.

### 3.12 Boş, hata ve çevrimdışı durumları

| Durum | Metin |
|---|---|
| Hiç rapor yok | "Henüz rapor yok. BOSS'tan **Teknik Task Detay Raporu**'nu indirip buraya bırakın." + [Dosya seç] |
| Öbekte iş yok | "Bu öbekte açık iş yok." (Öbek düzenleme bağlantısı altta) |
| Teknikte iş yok | "Bugün size atanmış iş yok. Yeni iş gelince burada görünür." |
| Sunucuya ulaşılamıyor | Üstte ince şerit: "Sunucuya ulaşılamıyor. Son bilgiler 14:05'ten. Yaptıklarınız telefonda bekliyor." |
| 403 | "Bu bölüm görevinize kapalı." + ana ekrana dönüş |

---

## 4. Teknik tasarım

### 4.1 Veri modeli

Hepsi `saha/saha.db` içinde (aynı yedek, aynı dosya).

- Yeni tablolar yalnız **eklenir**.
- Tek yeniden kurma, `kullanici` tablosudur (§4.2 v1).
- Sıralı değer listeleri (durum, kaynak) yeni tablolarda **CHECK ile değil tetikleyiciyle** korunur. Denetimin "yeni dar CHECK kurma" uyarısı böyle karşılanır: yarın yeni bir durum eklemek için tabloyu yeniden kurmak gerekmez; bir göç tetikleyiciyi düşürüp yenisini kurar.
- Tetikleyicinin listesi ve uygulama kodunun listesi **tek sabitten** (`operasyon/akis.py: DURUMLAR`) üretilir.

**v1: kullanici** (yeniden kurulur; tanım `db.SEMA` içinde de aynı olur)

```sql
CREATE TABLE kullanici (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ad           TEXT    NOT NULL,
    telefon      TEXT    NOT NULL UNIQUE,
    pin_hash     TEXT,
    davet_kodu   TEXT,
    rol          TEXT    NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge        INTEGER,                 -- yalnız satışta
    aktif        INTEGER NOT NULL DEFAULT 1,
    oturum_no    INTEGER NOT NULL DEFAULT 1,
    olusturma    TEXT    NOT NULL,
    etiket       TEXT,                    -- JSON ["lider"] / ["btk","arama"]; yetki vermez
    boss_ekip    TEXT,                    -- teknikte BOSS "Ekip" adı (içe aktarım eşleşmesi)
    davet_zamani TEXT                     -- davet kodunun üretildiği an (48 s geçerlilik)
);
```

**v2: öbek ve mahalle sözlüğü**

```sql
CREATE TABLE IF NOT EXISTS ilce (
    il      TEXT NOT NULL, ad TEXT NOT NULL,
    il_k    TEXT NOT NULL, ilce_k TEXT NOT NULL,   -- ie.ilce_anahtari()
    lat     REAL, lon REAL,
    PRIMARY KEY (il_k, ilce_k)
);

CREATE TABLE IF NOT EXISTS mahalle (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    il TEXT NOT NULL, ilce TEXT NOT NULL, ad TEXT NOT NULL,
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,  -- ie.anahtar()
    lat REAL, lon REAL,
    kaynak      TEXT NOT NULL,            -- 'liste'|'bina'|'rapor'|'obek'|'elle'|'resmi'
    dogrulandi  INTEGER NOT NULL DEFAULT 0,
    ekleyen_id  INTEGER REFERENCES kullanici(id),
    eklenme     TEXT NOT NULL,
    UNIQUE (il_k, ilce_k, mahalle_k)
);

CREATE TABLE IF NOT EXISTS mahalle_esad (          -- yazım farkı → asıl mahalle
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, esad_k TEXT NOT NULL,
    mahalle_id INTEGER NOT NULL REFERENCES mahalle(id),
    PRIMARY KEY (il_k, ilce_k, esad_k)
);

CREATE TABLE IF NOT EXISTS obek (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ad          TEXT NOT NULL,
    ad_k        TEXT NOT NULL UNIQUE,     -- ie.anahtar(ad); silinince ad_k || '#' || id
    renk        TEXT,
    sahip_id    INTEGER REFERENCES kullanici(id),   -- ev teknisyeni
    aktif       INTEGER NOT NULL DEFAULT 1,         -- 0 = silindi (yumuşak silme)
    olusturma   TEXT NOT NULL,
    guncelleme  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS obek_mahalle (
    obek_id    INTEGER NOT NULL REFERENCES obek(id),
    il_k       TEXT NOT NULL,
    ilce_k     TEXT NOT NULL,
    mahalle_k  TEXT NOT NULL,             -- '*' = ilçenin tamamı
    ref        TEXT NOT NULL,             -- görünen biçim 'Bursa/Nilüfer/Görükle' (hep 3 parça)
    ekleyen_id INTEGER REFERENCES kullanici(id),
    eklenme    TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k) -- bir mahalle yalnız BİR öbekte olabilir
);
CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id);

CREATE TABLE IF NOT EXISTS obek_olay (      -- yalnız eklenir
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman        TEXT NOT NULL,
    kullanici_id INTEGER REFERENCES kullanici(id),   -- NULL = sistem (JSON aktarımı)
    tur          TEXT NOT NULL,   -- olustur|ad|renk|sahip|mahalle_ekle|mahalle_cikar|tasi|sil|geri_al|json_aktarim
    obek_id      INTEGER REFERENCES obek(id),
    veri         TEXT NOT NULL,   -- JSON {once, sonra} (geri al buradan yapılır)
    surum        INTEGER NOT NULL -- işlemden SONRAKİ öbek düzeni sürümü
);
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_degismez BEFORE UPDATE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_silinmez BEFORE DELETE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay silinemez'); END;
-- ayar('obek_surumu') = öbek düzeninin tek sürüm sayacı (§4.7)
```

**v3: iş emirleri**

```sql
CREATE TABLE IF NOT EXISTS ie_aktarim (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kaynak         TEXT NOT NULL DEFAULT 'boss_teknik_task',   -- ileride 'fox_acik','fox_aski'
    dosya_adi      TEXT NOT NULL,
    dosya_sha256   TEXT NOT NULL,
    dosya_zamani   TEXT,          -- tarayıcının bildirdiği lastModified
    rapor_en_yeni  TEXT,          -- dosyadaki en yeni Task Başlangıç Tarihi
    yukleyen_id    INTEGER REFERENCES kullanici(id),
    baslama        TEXT NOT NULL,
    bitis          TEXT,
    durum          TEXT NOT NULL DEFAULT 'isleniyor',  -- isleniyor|onay_bekliyor|uygulandi|vazgecildi|hata
    satir INTEGER, cikarilan INTEGER, is_sayisi INTEGER,
    yeni INTEGER, degisen INTEGER, kaybolan INTEGER, yeniden_acilan INTEGER, degismeyen INTEGER,
    kontrol        INTEGER,
    onay_nedeni    TEXT,          -- JSON ['cok_kaybolan','eski_rapor']
    ozet           TEXT,          -- JSON: çıkarılan task adı sayımı, uyarılar, süre (kişisel veri YOK)
    yedek_yolu     TEXT,
    hata           TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_aktarim_sha ON ie_aktarim(dosya_sha256) WHERE durum = 'uygulandi';
CREATE INDEX IF NOT EXISTS ix_aktarim_zaman ON ie_aktarim(baslama);

CREATE TABLE IF NOT EXISTS is_emri (
    is_no             TEXT PRIMARY KEY,   -- BOSS Task No (9 hane, METİN) | bayi 'B-260930-001'
    boss_task_no      TEXT UNIQUE,        -- BOSS işinde = is_no; bayi işinde bağlanınca dolar
    kaynak            TEXT NOT NULL,      -- 'boss' | 'bayi'
    satis_kanali      TEXT,               -- ham BOSS 'Satış Kanalı'
    kanal_grubu       TEXT,               -- global|dehanet|diger_bayi|kurumsal|bos
    task_adi          TEXT NOT NULL,
    serit             TEXT NOT NULL,      -- BTK|SAHA|MASA|LOJISTIK (OT §3.1)
    btk_hedef_saat    INTEGER,
    -- müşteri (kişisel veri; yetkiye göre döner; kapanış + 30 gün sonra NULL)
    musteri_no        TEXT,
    musteri_adi       TEXT,
    musteri_tel       TEXT,               -- yalnız operasyonun elle girdiği
    adres             TEXT,
    -- yer
    il TEXT, ilce TEXT, mahalle TEXT,
    il_k TEXT, ilce_k TEXT, mahalle_k TEXT,
    mahalle_kaynak    TEXT,               -- lokasyon|adres|adres-yeni|adres-benzer|elle
    mahalle_elle      INTEGER NOT NULL DEFAULT 0,  -- 1: raporla ezilmez
    lokasyon          TEXT,
    bina_serial       TEXT REFERENCES bina(bina_serial),
    lat REAL, lon REAL,
    konum_kaynak      TEXT,               -- bina|site|mahalle_merkezi|ilce_merkezi|elle
    -- öbek
    obek_id           INTEGER REFERENCES obek(id),   -- mahalleden türetilen
    obek_elle_id      INTEGER REFERENCES obek(id),   -- elle (F5); doluysa türetileni ezer
    parca             TEXT, parca_tarih TEXT,
    triyaj_nedeni     TEXT,               -- il_disi|mahalle_yok|obeksiz|NULL
    -- BOSS'un söyledikleri (her aktarımda üzerine yazılır)
    boss_durum TEXT, boss_randevu_durumu TEXT, boss_randevu_bas TEXT, boss_randevu_bit TEXT,
    boss_ekip TEXT, boss_aski_nedeni TEXT, boss_sl TEXT, boss_sl_saat REAL,
    boss_son_aciklama TEXT,
    boss_ozet         TEXT,               -- yukarıdakilerin sha1'i: "değişti mi" için
    boss_bekleyen     TEXT,               -- 'ekip'|'randevu'|'ekip,randevu'|NULL (giden kutusu)
    boss_kapanmadi    INTEGER NOT NULL DEFAULT 0,
    -- bizim akış
    durum             TEXT NOT NULL,
    durum_zamani      TEXT NOT NULL,
    atanan_id         INTEGER REFERENCES kullanici(id),
    atama_zamani      TEXT,
    randevu_bas TEXT, randevu_bit TEXT,
    ticket_id         INTEGER REFERENCES ticket(id),
    uyanma            TEXT,
    evde_yok_sayisi   INTEGER NOT NULL DEFAULT 0,
    teshis_sonucu     TEXT,               -- BTK teşhis araması son sonucu
    sonuc_kodu        TEXT,
    tekrar7g          INTEGER NOT NULL DEFAULT 0,
    -- saatler
    acilis            TEXT NOT NULL,
    son24             TEXT NOT NULL,
    gorulme_zamani    TEXT NOT NULL,      -- 15 dk saati buradan başlar
    ilk_atama_zamani  TEXT,
    ilk_gorulme       TEXT NOT NULL,      -- hiç değişmez
    son_gorulme       TEXT,
    kapanis           TEXT,
    kapanis_kesin     INTEGER NOT NULL DEFAULT 1,
    kapanis_nedeni    TEXT,
    acilma_sayisi     INTEGER NOT NULL DEFAULT 1,
    son_aktarim_id    INTEGER REFERENCES ie_aktarim(id),
    olusturan_id      INTEGER REFERENCES kullanici(id),
    surum             INTEGER NOT NULL DEFAULT 1,   -- operasyon alanları değişince +1 (§4.7)
    guncelleme        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_is_durum   ON is_emri(durum, son24);
CREATE INDEX IF NOT EXISTS ix_is_obek    ON is_emri(obek_id);
CREATE INDEX IF NOT EXISTS ix_is_atanan  ON is_emri(atanan_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_mahalle ON is_emri(il_k, ilce_k, mahalle_k);
CREATE INDEX IF NOT EXISTS ix_is_bina    ON is_emri(bina_serial);
CREATE INDEX IF NOT EXISTS ix_is_musteri ON is_emri(musteri_no, task_adi);
CREATE INDEX IF NOT EXISTS ix_is_ticket  ON is_emri(ticket_id);

-- Değer listesi tetikleyicileri: akis.DURUMLAR'dan üretilir (örnek; liste koddan gelir)
CREATE TRIGGER IF NOT EXISTS trg_is_durum_ekle BEFORE INSERT ON is_emri
WHEN NEW.durum NOT IN ('triyaj','bekliyor','randevulu','atandi','yolda','sahada',
                       'ulasilamadi','askida','altyapi','merkeze','cozuldu','kapandi')
  OR NEW.kaynak NOT IN ('boss','bayi')
BEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END;
CREATE TRIGGER IF NOT EXISTS trg_is_durum_guncelle BEFORE UPDATE OF durum, kaynak ON is_emri
WHEN NEW.durum NOT IN ('triyaj','bekliyor','randevulu','atandi','yolda','sahada',
                       'ulasilamadi','askida','altyapi','merkeze','cozuldu','kapandi')
  OR NEW.kaynak NOT IN ('boss','bayi')
BEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END;

CREATE TABLE IF NOT EXISTS is_emri_olay (    -- olay defteri: yalnız eklenir
    id           INTEGER PRIMARY KEY AUTOINCREMENT,   -- aynı zamanda "değişim imleci" (§4.7)
    is_no        TEXT NOT NULL REFERENCES is_emri(is_no),
    zaman        TEXT NOT NULL,
    kullanici_id INTEGER REFERENCES kullanici(id),   -- NULL = sistem (aktarım, saat, ticket)
    tur          TEXT NOT NULL,   -- olustu|aktarim_degisti|kayboldu|yeniden_acildi|durum|atama|
                                  -- randevu|ticket|obek|mahalle|not|iletisim|teshis|celiski|
                                  -- uyandi|boss_islendi|boss_bagla
    eski         TEXT,            -- JSON {alan: değer}; kişisel veri alanlarında yalnız ad
    yeni         TEXT,
    notu         TEXT,
    aktarim_id   INTEGER REFERENCES ie_aktarim(id),
    istemci_id   TEXT,            -- telefondan gelen yazmanın tekillik anahtarı
    UNIQUE (kullanici_id, istemci_id)
);
CREATE INDEX IF NOT EXISTS ix_olay_is ON is_emri_olay(is_no, id);
CREATE TRIGGER IF NOT EXISTS trg_is_olay_degismez BEFORE UPDATE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_is_olay_silinmez BEFORE DELETE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay silinemez'); END;

CREATE TABLE IF NOT EXISTS erisim_kaydi (    -- müşteri bilgisi görüntüleme kaydı (KVKK)
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman        TEXT NOT NULL,
    kullanici_id INTEGER NOT NULL REFERENCES kullanici(id),
    eylem        TEXT NOT NULL,   -- is_liste|is_ayrinti|excel|tel_goster
    is_no        TEXT,
    adet         INTEGER,
    ip           TEXT
);
CREATE INDEX IF NOT EXISTS ix_erisim ON erisim_kaydi(kullanici_id, zaman);
CREATE TRIGGER IF NOT EXISTS trg_erisim_degismez BEFORE UPDATE ON erisim_kaydi
BEGIN SELECT RAISE(ABORT, 'erisim_kaydi degistirilemez'); END;

CREATE TABLE IF NOT EXISTS takip_anlik (     -- her aktarımda bir satır: 7 günlük eğim için
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, aktarim_id INTEGER REFERENCES ie_aktarim(id),
    acik INTEGER, asan24 INTEGER, btk_asan48 INTEGER, atanmamis INTEGER, altyapi INTEGER
);

CREATE TABLE IF NOT EXISTS sema_goc (        -- uygulanan göçlerin defteri
    surum      INTEGER PRIMARY KEY,
    ad         TEXT NOT NULL,
    baslama    TEXT NOT NULL,
    bitis      TEXT NOT NULL,
    yedek_yolu TEXT NOT NULL,
    ozet       TEXT               -- JSON: önce/sonra satır sayıları (toplam; kişisel veri yok)
);
```

`erisim_kaydi` için silme tetikleyicisi bilerek yoktur. Saklama süresi (ör. 2 yıl) dolunca temizleyecek olan göç, bu tetikleyiciyi kaldırmak zorunda kalmasın.

**v4: onarım** (yalnız ekler)

```sql
CREATE INDEX IF NOT EXISTS ix_ziyaret_bina      ON ziyaret(bina_serial);
CREATE INDEX IF NOT EXISTS ix_ziyaret_kullanici ON ziyaret(kullanici_id, zaman);
```

Eski şemadan göç etmiş veritabanlarında bu indeksler kaybolmuştu. Canlıda indeksler var; `IF NOT EXISTS` bu durumda hiçbir şey yapmaz.

**Ayar anahtarları:**

| Anahtar | Değer |
|---|---|
| `obek_surumu` | Tamsayı |
| `boss_task_url` | Şablon; `{task_no}` içerir. Boşsa "BOSS'ta aç" düğmesi gizlenir |
| `musteri_tel` | `acik` \| `kapali` |
| `kapasite_<YYYY-AA-GG>` | Sabah girilen aktif teknik sayısı |
| `aktarim_esik` | JSON `{"kaybolan_oran":0.25,"kaybolan_min":50}` |

### 4.2 Göç çerçevesi: güncellemede veri zarar görmez (F20)

**Yeni dosya `saha/goc.py`.** Tek giriş noktası `hazirla(yol) -> GocRaporu`.

```python
HEDEF = 4
GOCLER = [
    (1, "kullanici_rol_dort",  goc_1_rol),        # tek yeniden kurma
    (2, "obek_ve_mahalle",     goc_2_obek),       # ekler + obekler.json'u DB'ye aktarır
    (3, "is_emri_tablolari",   goc_3_is_emri),    # ekler (+ son_yukleme.pkl varsa taşır)
    (4, "indeks_onarim",       goc_4_indeks),     # ekler
]

def hazirla(yol: Path) -> GocRaporu:
    with dosya_kilidi(yol.with_name("saha.db.goc.kilit")):   # os.open(O_CREAT|O_EXCL); bayat kilit 10 dk
        conn = sqlite3.connect(yol, isolation_level=None, timeout=30)   # işlemleri biz yönetiriz
        conn.execute("PRAGMA busy_timeout=30000")
        db.gocler(conn)                      # bugünkü "yalnız ekleyen" adımlar (değişmez; ziyaret onarımı hariç)
        surum = conn.execute("PRAGMA user_version").fetchone()[0]
        bekleyen = [g for g in GOCLER if g[0] > surum]
        if not bekleyen:
            return GocRaporu(bos=True)
        disk_kontrol(yol, kat=2.5)           # boş yer < 2,5 × DB → dur, Türkçe mesaj
        yedek = yedekle.goc_yedegi(yol, surum, HEDEF)   # doğrulanamazsa istisna → GÖÇ YOK
        for no, ad, fn in bekleyen:
            fn(conn, yedek)                  # her fonksiyon kendi BEGIN IMMEDIATE…COMMIT'ini yapar
        son_kontrol(conn)                    # integrity_check='ok', foreign_key_check boş
        return GocRaporu(...)
```

**Göç öncesi yedek** (`yedekle.goc_yedegi`):

1. Hedef: `saha/yedek/goc/saha-oncesi-v{eski}-v{yeni}-{AAAAGGAA-SSDDss}.db`. Günlük yedeğin (`saha-AAAA-AA-GG.db`) **üzerine yazmaz**. `eskileri_sil` bu klasöre **girmez**.
2. Kaynak `file:…?mode=ro` ile açılır; sqlite backup API kullanılır.
3. Kopya doğrulanır:
   - `PRAGMA integrity_check` = `ok`
   - Bütün tabloların satır sayıları kaynakla aynı
   - `kullanici` satırlarının sha256 özeti aynı
4. Kopyada `PRAGMA journal_mode=DELETE` çalıştırılır; kopya kapanınca -wal/-shm dosyası kalmaz.
5. Dosya salt okunur yapılır (`os.chmod(S_IREAD)`).
6. Herhangi bir adım başarısızsa `GocHatasi` fırlatılır; göç **başlamaz**.

**v1: `kullanici` yeniden kurma.** Kopyada denenen ve doğrulanan sıra budur. **Eski tabloyu önce yeniden adlandırmak yasaktır**: SQLite 3.50.4, 11 yabancı anahtarı `kullanici_eski`ye yeniden yazıyor.

```sql
-- koşul: sqlite_master'daki kullanici tanımında 'operasyon' YOKSA (CHECK'siz eski tablo da buraya girer)
PRAGMA foreign_keys = OFF;              -- işlem DIŞINDA (işlem içinde etkisiz)
PRAGMA legacy_alter_table = OFF;        -- varsayılan; açıkça yazılır
BEGIN IMMEDIATE;
-- ÖNCE: n0 = COUNT(*), h0 = sha256(id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma ORDER BY id),
--       s0 = (SELECT seq FROM sqlite_sequence WHERE name='kullanici'),
--       x0 = sqlite_master'da tbl_name='kullanici' olan autoindex dışı index/trigger/view listesi
CREATE TABLE kullanici_yeni ( …§4.1 v1 tanımı, sabitten üretilir, eski SQL'in metin değişimiyle değil… );
INSERT INTO kullanici_yeni (id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma)
     SELECT id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma FROM kullanici;
     -- tanınmayan rol → CHECK hatası → ROLLBACK (aşağı bakın)
DROP TABLE kullanici;
ALTER TABLE kullanici_yeni RENAME TO kullanici;
-- x0'daki nesneler varsa yeniden kurulur (bugün yok)
UPDATE sqlite_sequence SET seq = MAX(seq, :s0) WHERE name = 'kullanici';
INSERT INTO sqlite_sequence(name, seq) SELECT 'kullanici', :s0
    WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name='kullanici') AND :s0 IS NOT NULL;
-- DOĞRULAMA (hepsi geçmezse ROLLBACK + GocHatasi):
--   COUNT(*) = n0 ; özet = h0 ; seq >= s0
--   PRAGMA foreign_key_check  → 0 satır
--   SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_yeni%' OR sql LIKE '%kullanici_eski%' → 0
--   SELECT COUNT(*) FROM sqlite_master m, pragma_foreign_key_list(m.name) p
--          WHERE p."table" NOT IN (SELECT name FROM sqlite_master WHERE type='table') → 0
INSERT INTO sema_goc(surum, ad, baslama, bitis, yedek_yolu, ozet) VALUES (1, 'kullanici_rol_dort', …);
PRAGMA user_version = 1;                -- başlık sayfasında; işlemle birlikte geri alınır
COMMIT;
PRAGMA foreign_keys = ON;
```

**Göç başarısız olursa.** Örnek: tanınmayan rol, doğrulama farkı ya da disk hatası.

- ROLLBACK yapılır; veritabanı **dokunulmamış** kalır. Kopyada denendi: DROP'tan sonra istisna ve süreç öldürme, ikisinde de 0 değişiklik.
- Sunucu **açılmaz**. Konsola Türkçe yazar: "GÜNCELLEME DURDU: kullanıcı tablosunda tanınmayan görev 'x' (2 kişi). Veritabanı DEĞİŞMEDİ. Yedek: saha\yedek\goc\…db. Eski sürümle devam etmek için önceki klasörü çalıştırın ya da BT'ye bu ekranın fotoğrafını gönderin."
- Yarım şemayla çalışma yoktur. Bugün `api.py:1888` göç hatasını yutuyor; bu kaldırılır.

**v2: öbekler.**

1. Tablolar kurulur.
2. `ilce` tablosu tohumlanır:
   - Bursa (17): Büyükorhan, Gemlik, Gürsu, Harmancık, İnegöl, İznik, Karacabey, Keles, Kestel, Mudanya, Mustafakemalpaşa, Nilüfer, Orhaneli, Orhangazi, Osmangazi, Yenişehir, Yıldırım.
   - Yalova (6): Altınova, Armutlu, Çınarcık, Çiftlikköy, Merkez, Termal.
3. `mahalle` tohumlanır (§4.4).
4. `obekler.json` DB'ye aktarılır (§4.3).

Hepsi tek işlemdir.

**v3: iş emirleri.**

1. Tablolar ve tetikleyiciler kurulur.
2. `operasyon/veri/son_yukleme.pkl` varsa ve okunabiliyorsa, içindeki işler **ilk aktarım** olarak yazılır (`kaynak='pickle'`). Bugünkü parça etiketleri satır numarasından Task No'ya çevrilip korunur. Böylece geçiş günü yapılan iş kaybolmaz.
3. Pickle okunamazsa uyarı yazılır, göç **durmaz**. Pickle dosyası **silinmez ve değiştirilmez**.

**Başlatma sırası** (`saha/sunucu.py`):

1. `port_dolu_mu` → dolu ise "Zaten çalışıyor" yazar ve çıkar. **Göç çalışmaz.** Bugün göç port kontrolünden önce koşuyor: ikinci tıklamada çalışan sunucunun altında canlı DB göç ediliyordu.
2. `goc.hazirla()` → rapor ekrana yazılır. Örnek: "Güncelleme tamam (v0 → v4): 10 kişi, 1.257 ziyaret, 19.706 bina aynen korundu. 14 öbek ve 120 mahalle aktarıldı. Yedek: saha\yedek\goc\saha-oncesi-v0-v4-….db"
3. Ağır modüller (dsale.metrics, dsale.partition, shapely) lifespan içinde **eşzamanlı** içe alınır. Isıtma iş parçacığı kaldırılır; denetimde görülen "partially initialized shapely" yarışı böyle kapanır.
4. `api._veritabanini_hazirla` artık göç **yapmaz**; yalnız `user_version == HEDEF` doğrular. Testlerde TestClient bu yüzden `goc.hazirla`'yı açıkça çağırır (conftest).

**Diğer koruyucular:**

- `db.gocler` içindeki `ziyaret` yeniden kurması (eski DB'ler için) aynı güvenli desene çevrilir: yeni tablo → kopyala → DROP → RENAME → indeksleri yeniden kur, tek işlemde. Canlıda bu adım zaten çalışmaz; kalıp düzeltilir ki bir gün kopyalanırsa zarar vermesin.
- `kur.py --sifirla`: `kullanici` içinde `5000000000` tohum numaraları dışında kişi varsa reddeder. `--evet-gercek-kisileri-sil` + otomatik yedek olmadan çalışmaz.
- `baslat.bat`: `saha.db` yoksa ve `saha/yedek` içinde yedek varsa **sessizce tohumlamaz**. Konsola şunu yazar: "Veritabanı bulunamadı. En son yedek: … Geri yüklemek için GERI_YUKLE.bat."
- `GERI_YUKLE.bat` (yeni):
  1. Sunucu çalışıyorsa durur ve kullanıcıdan durdurmasını ister.
  2. Mevcut `saha.db` dosyasını `saha-hatali-<zaman>.db` adıyla kenara koyar. **Silmez.**
  3. Seçilen yedeği kopyalar ve `integrity_check` çalıştırır.
- **Güncellemenin asla üzerine yazmadığı dosyalar** (`saha/KORUNAN.txt`; güncelleme betiği bunları atlar ve varlığını doğrular):
  - `saha/saha.db*`
  - `saha/gizli.key` (yoksa bütün jetonlar düşer)
  - `saha/yedek/**`
  - `operasyon/obekler.json`
  - `operasyon/veri/**`
  - `data/raw/gelen/**`

### 4.3 Kullanıcının öbekleri asla kaybolmaz

1. v2 göçü `OPERASYON_OBEK` (yoksa `operasyon/obekler.json`) dosyasını **yalnız okur**. Önce `operasyon/yedek/obekler-<zaman>.json` olarak bir kopya alır.
2. Her `ref` 3 parçaya tamamlanır: 2 parçalıysa il, ilçe sözlüğünden bulunur. Aktarılan her mahalle sözlükte yoksa `kaynak='obek'` ile sözlüğe de eklenir. Canlıda 36 mahalle hiçbir listede yok; bunlar kaybolmaz.
3. Çakışma: aynı mahalle iki öbekte ise dosyadaki ilk öbek kazanır ve `obek_olay` + göç raporuna yazılır. Canlıda çakışma 0.
4. Aktarım doğrulaması (aynı işlemde):
   - Öbek sayısı = 14.
   - `obek_mahalle` satırı = 120.
   - Dosyadaki her ref için `bul()` sonucu DB'deki öbekle aynı.
   - Tutmazsa ROLLBACK.
5. Göçten sonra **kaynak DB'dir**. Sunucu `obekler.json` dosyasına bir daha **yazmaz**. Dosya olduğu gibi kalır.
6. Okunabilir bir ayna tutulur: her öbek değişikliğinden sonra `operasyon/veri/obekler_ayna/obekler-<zaman>.json` yazılır (son 50 tutulur, gitignore'da). Olay defteriyle birlikte "dün öbekler nasıldı" sorusunu cevaplar.
7. Komut satırı (`IS_EMRI_HAZIRLA.bat`): öbekleri DB'den okur. Öbek tablosu yazma özelliği kapatılır; yerine şu mesaj çıkar: "Öbekleri uygulamadaki Öbekler ekranından düzenleyin."
8. `.gitignore`'a `operasyon/obekler.json` eklenir. Bunun yerine `operasyon/obekler.ornek.json` gelir. Böylece `git add operasyon/` kullanıcının öbeklerini depoya göndermez.

### 4.4 Mahalle sözlüğü (F2)

| Sıra | Kaynak (`kaynak`) | İçerik | Bugün |
|---|---|---|---|
| 1 | `liste` | `data/ref/mahalle_listesi.json` (BursaStateList) | 10 Bursa ilçesi, 621 mahalle, koordinatlı |
| 2 | `bina` | `bina` tablosundaki farklı (il, ilçe, mahalle) + bina ağırlık merkezi | 165 (Yalova Merkez'in 4'ü dahil) |
| 3 | `obek` | Öbek dosyasında olup listede olmayanlar | 36 (Yalova 25; Karacabey, M.Kemalpaşa, Keles 11) |
| 4 | `rapor` | Her aktarımda raporda görülen yeni mahalleler (adres-yeni) | Geldikçe |
| 5 | `elle` | "Listede yok mu?" ile eklenen (Göçmen) | Kullanıcıdan |
| 6 | `resmi` | "Mahalle listesi yükle" (Veri ▸): il, ilçe, mahalle[, lat, lon] sütunlu Excel/CSV | Resmî liste gelince (açık soru 5) |

- Her ilçe ayrıca "tamamı" (`'*'`) olarak seçilebilir. Seçici `ilce` tablosundan gelir; o ilçede hiç mahalle kaydı olmasa da çalışır.
- Anahtar `ie.anahtar()` ile üretilir; aynı ad farklı ilçede ayrıdır (C19).
- Eşanlamlılar `mahalle_esad` tablosundadır. Örnek: "TASLIMAN" → "TASLIMANI". "Taşlimanı mı demek istediniz?" önerisi kabul edilince eşanlam kaydı yazılır; sonraki raporlarda o yazım doğru mahalleye düşer.
- Köy biçimleri (denetim bulgusu, yalnız Yalova'da görüldü):
  - "X Bbk.Mah.(Y)" ve "X (Y) Mh." → köy Y (X alt yer adı olarak not edilir).
  - "Y Köyü" → Y.
  - Testle kilitlenir.

### 4.5 İçe aktarım hattı (F18)

`operasyon/aktarim.py`. Uç `def` olarak tanımlanır (async değil). FastAPI işi iş parçacığı havuzunda çalıştırır; olay döngüsü kilitlenmez. Denetimde yükleme sırasında `/api/saglik` 3,3 sn bekliyordu.

```
1. AL        Dosya ≤25 MB. sha256 hesaplanır.
             Aynı sha 'uygulandi' olarak varsa  → 200 {ayni_dosya:true, aktarim_id, zaman}. HİÇBİR ŞEY YAZILMAZ.
2. KİLİTLE   Süreç kilidi (threading.Lock, bloklamadan dene) + ie_aktarim satırı 'isleniyor'.
             Kilit doluysa → 409 aktarim_suruyor.
3. SAKLA     Ham dosya → operasyon/veri/gelen/<sha>.xlsx (7 gün sonra silinir).
4. OKU       raporu_oku → çıkarma (kurulum / 2. donanım; çıkarılan satırlar SAKLANMAZ, yalnız sayımı)
             → mahalle ve konum. Lokasyon → bina VERİTABANINDAN (ticket.lokasyondan_bina normalizasyonu),
             bina.mahalle esas (F4); yoksa adres; sözlük DB'den (mahalle + mahalle_esad).
             → şerit, BTK hedefi, kanal grubu, triyaj nedeni.
             Rapor tanınmazsa ('Task Adı' ve 'Adres' başlıklı sayfa yok) → 422 rapor_tanimadi.
5. FARK      Anahtar boss_task_no. Kümeler: yeni · yeniden_acilan (DB'de 'kapandi') ·
             degisen (boss_ozet farklı ya da adres/lokasyon değişti) · degismeyen ·
             kaybolan (DB'de açık, kaynak='boss' ya da bağlı bayi işi, dosyada yok).
6. BEKÇİ     kaybolan > max(aktarim_esik.kaybolan_min, açık × kaybolan_oran)  → 'cok_kaybolan'
             dosya_zamani < son uygulananın dosya_zamani, ya da
             rapor_en_yeni < son uygulananın rapor_en_yeni − 1 s               → 'eski_rapor'
             Biri varsa → durum 'onay_bekliyor' + 409 onay_gerekli {aktarim_id, fark, nedenler}.
             Fark sonucu bellekte değil diskte (operasyon/veri/gelen/<id>.fark.json) bekler.
             "Uygula" gelince 5. adım YENİDEN hesaplanır; bu arada başka değişiklik olduysa yeni fark gösterilir.
7. YEDEK     yedekle.aktarim_yedegi() → saha/yedek/aktarim/ (son 10 tutulur). 1 sn'nin altında.
8. UYGULA    TEK işlem (BEGIN IMMEDIATE):
             - yeni: INSERT is_emri + olay 'olustu'; durum §2.3'e göre; tekrar7g
             - degisen: boss_* güncellenir + olay 'aktarim_degisti' {alan: [eski, yeni]}
               (kişisel veri alanlarında yalnız ad); durum ileri kuralı; boss_bekleyen yeniden hesaplanır
             - degismeyen: yalnız son_gorulme, son_aktarim_id
             - kaybolan: durum 'kapandi', kapanis=şimdi, kapanis_kesin=0, olay 'kayboldu'
             - yeniden_acilan: §2.3 kural 6
             - korunur: obek_elle_id, mahalle_elle, atanan_id, randevu_*, ticket_id, parca,
               musteri_tel, notlar
             - öbek: obek_id = öbek_bul(il_k, ilce_k, mahalle_k), elle olan ezilmez
             - sözlük: raporda görülen yeni mahalleler kaynak 'rapor' ile eklenir
             - takip_anlik satırı; ie_aktarim satırı 'uygulandi' + sayımlar
             437 iş için hedef < 300 ms.
9. BİLDİR    Yanıt: {aktarim_id, fark:{yeni,degisen,kaybolan,yeniden_acilan,degismeyen},
             cikarilan:{kurulum,ikinci_donanim}, kontrol, sure_sn, yedek}
```

**Hata durumu.** Adım 4 ya da 8'de istisna olursa ROLLBACK yapılır ve `ie_aktarim.durum='hata'` + Türkçe hata metni yazılır. İşler ve öbekler **hiç değişmez**.

**FOX** (sonraki adım): Aynı hat `kaynak='fox_acik' | 'fox_aski'` ile çalışacak şekilde tasarlanmıştır. Anahtar olarak Akış No = BOSS Task No kullanılır. Bu turda uygulanmaz.

### 4.6 API sözleşmesi

- Bütün yanıtlar JSON'dur. Hata biçimi bugünkü gibidir: `{"hata": "<Türkçe cümle>", "kod": "<kod>"}`.
- Zamanlar ISO 8601 yerel saattir (`2026-09-30T14:05:00`).
- Yeni uçlar `/api/isler`, `/api/obekler`, `/api/mahalleler`, `/api/aktarim`, `/api/takip` altındadır.
- Eski `/api/is-emri/*` uçları, yeni ekran açılınca kaldırılır. O güne kadar salt okunur kalır ve DB'den beslenir.

**Tipler**

```ts
type Durum = 'triyaj'|'bekliyor'|'randevulu'|'atandi'|'yolda'|'sahada'
           |'ulasilamadi'|'askida'|'altyapi'|'merkeze'|'cozuldu'|'kapandi';
interface IsSatir {
  is_no: string; kaynak: 'boss'|'bayi'; kanal_grubu: string|null;
  task_adi: string; serit: 'BTK'|'SAHA'|'MASA'|'LOJISTIK'; btk_hedef_saat: number|null;
  durum: Durum; durum_zamani: string;
  il: string; ilce: string; mahalle: string|null;
  musteri_adi?: string|null; kisa_adres?: string|null;      // yalnız is.musteri izniyle
  obek: {id: number; ad: string}|null; obek_elle: boolean; triyaj_nedeni: string|null;
  konum_yaklasik: boolean;
  acilis: string; son24: string; kalan_dk: number; renk: 'yesil'|'amber'|'kirmizi'; gecikti: boolean;
  btk_kalan_dk: number|null;
  randevu: {bas: string; bit: string; kaynak: 'biz'|'boss'}|null;
  atanan: {id: number; ad: string}|null;
  boss_ekip?: string|null;                                   // yalnız operasyon/yönetici
  ticket: {id: number; durum: string}|null; binada_acik_ticket: number;
  tekrar7g: boolean; boss_bekleyen: string|null; boss_kapanmadi: boolean;
  bekleme_dk: number|null;                                   // atanmamışsa gorulme_zamani'ndan beri
  surum: number;
}
interface IsAyrinti extends IsSatir {
  musteri_no?: string|null; musteri_tel?: string|null; adres?: string|null;
  lokasyon: string|null; mahalle_kaynak: string|null; konum_kaynak: string|null;
  bina: {serial: string; ad: string|null; location_id: string|null; lat: number; lon: number}|null;
  lat: number|null; lon: number|null;
  boss: {durum; randevu_durumu; randevu_bas; randevu_bit; ekip; aski_nedeni; sl; sl_saat; son_aciklama};
  uyanma: string|null; evde_yok_sayisi: number; teshis_sonucu: string|null;
  olaylar: {id; zaman; kisi: string|null; tur; ozet: string; notu: string|null}[];
  izinler: {ata: boolean; randevu: boolean; ticket: boolean; obek: boolean; iletisim: boolean;
            durumlar: Durum[]; ofisten_kapat: boolean};
  boss_url: string|null;
}
```

**Uçlar**

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `GET /api/isler` | `is.liste` (kapsam role göre) | `?kova=acik\|biten&gun=7` | `{sunucu_zamani, imlec, obek_surumu, son_aktarim:{id,zaman,dosya_adi,is_sayisi,yas_dk}, sayac:{acik,asan24,atanmamis,en_eski_atanmamis_dk,btk48,kontrol,boss_bekleyen,konum_yaklasik}, isler: IsSatir[]}`. Operasyon ve yönetici bütün açık işleri alır; süzme istemcidedir (437 iş < 150 ms). Teknik yalnız kendi açık işlerini, satış yalnız kendi açtıklarını alır. Müşteri alanı döndüyse `erisim_kaydi` tek satır |
| `GET /api/isler/degisim` | `is.liste` | `?imlec=<olay_id>` | `{imlec, isler: IsSatir[], obek_surumu, son_aktarim}`. İmleçten sonra olayı olan işler döner. Pano bunu 20 sn'de bir çağırır; iki operatör aynı anda canlı görür |
| `GET /api/isler/{is_no}` | `is.liste` + kapsam | — | `IsAyrinti`. Kapsam dışı iş 404 döner (varlığı sızdırılmaz). `erisim_kaydi` satırı |
| `POST /api/isler/{is_no}/ata` | `is.ata` | `{teknik_id, randevu?:{bas,bit}, surum, notu?}` | 200 `IsAyrinti`. 409 `guncel_degil` + `{guncel: IsAyrinti, degistiren, zaman}`. 422 `teknik_gecersiz` (rol teknik değil ya da pasif). 409 `altyapi_engeli` (binada açık ticket ve iş bağlı değil; `yine_de:true` ile geçilir, OT kural 11) |
| `POST /api/isler/toplu-ata` | `is.ata` | `{atamalar:[{is_no, teknik_id, surum, parca?}]}` | `{sonuc:[{is_no, tamam:bool, kod?}]}`. Her iş kendi alt işleminde (SAVEPOINT) yürür; biri çakışırsa diğerleri kaydedilir |
| `POST /api/isler/{is_no}/randevu` | `is.randevu` | `{bas, bit, notu?, surum}` ya da `{bas:null, surum}` (kaldır) | 200 / 409 `guncel_degil` / 422 `randevu_gecersiz` ("Bitiş başlangıçtan sonra olmalı", "En çok 7 gün ileri") |
| `POST /api/isler/{is_no}/durum` | `is.durum` | `{yeni, neden?, evde_miydi?, sonuc_kodu?, uyanma?, notu?, surum?, istemci_id?}` | 200 / 409 `gecersiz_gecis` / 409 `guncel_degil`. Teknikte `surum` isteğe bağlıdır; geçiş mevcut durumdan geçerliyse uygulanır. Aynı `istemci_id` ikinci kez gelirse ilk sonuç döner. 422 `alan_eksik` ("Müşteri evde miydi?") |
| `POST /api/isler/{is_no}/teshis` | `is.durum` (operasyon) | `{sonuc:'duzeldi'\|'simdi_evde'\|'baska_gun'\|'cevapsiz'\|'kapali'\|'yanlis_no', canli_test?, randevu?, surum}` | 200. `duzeldi` + `canli_test` → `cozuldu` (neden `telefonda_cozuldu`; `tekrar7g` ise 409 `tekrar_ariza`). `simdi_evde` → 3 saatlik randevu |
| `POST /api/isler/{is_no}/ticket` | `is.ticket` | `{ticket_id}` ya da `{yeni:{konu, ticket_no?, detay?}}`, `teknisyen_gonderme:bool`, `surum` | 200. `DELETE` aynı yolda: bağı kaldırır |
| `POST /api/isler/{is_no}/obek` | `is.obek` | `{obek_id\|null, surum}` | 200. `null` elle atamayı kaldırır (mahallesine göre) |
| `POST /api/isler/{is_no}/mahalle` | `is.obek` | `{mahalle_id, surum}` | 200. `mahalle_elle=1` |
| `POST /api/isler/{is_no}/not` | `is.liste` + kapsam (teknik kendi işine) | `{metin (≤1000), istemci_id?}` | 201 |
| `PATCH /api/isler/{is_no}/iletisim` | `is.iletisim` | `{musteri_tel, surum}` | 200 / 403 `tel_kapali` (ayar kapalı). 05XXXXXXXXX doğrulaması |
| `POST /api/isler` | `is.olustur` | `{task_adi, bina_serial?, adres?, mahalle_id?, musteri_adi?, musteri_no?, musteri_tel?, aciklama?, istemci_id}` | 201 `{is_no:'B-260930-001'}`. Satışta durum `triyaj` |
| `POST /api/isler/{is_no}/boss-bagla` | `is.ata` | `{boss_task_no (9 hane), surum}` | 200 / 409 `boss_no_kullanilmis` |
| `POST /api/isler/bol` | `is.ata` | `{obek_id, k (2–30), yontem:'bina'}` | `{parcalar:[{ad, is_nolar[], merkez, yaricap_km}]}` (yalnız öneri; yazmaz) |
| `GET /api/isler/excel` | `is.excel` | `?kova=acik` | xlsx. Müşteri sütunları role göre. `erisim_kaydi` satırı |
| `POST /api/aktarim` | `is.yukle` | multipart `dosya`, `dosya_zamani` | §4.5-9 / 200 `{ayni_dosya:true}` / 409 `onay_gerekli` / 409 `aktarim_suruyor` / 413 `buyuk_dosya` / 422 `rapor_tanimadi` |
| `POST /api/aktarim/{id}/uygula` | `is.yukle` | `{onay:true}` | §4.5-9 / 409 `durum_gecersiz` |
| `POST /api/aktarim/{id}/vazgec` | `is.yukle` | — | 200 |
| `GET /api/aktarim` | `is.yukle` | `?limit=30` | Geçmiş listesi (kişisel veri yok) |
| `GET /api/obekler` | `obek.oku` | — | `{surum, obekler:[{id, ad, renk, sahip:{id,ad}\|null, mahalleler:[{ref, il, ilce, mahalle, tum_ilce, acik}], acik, geciken, btk, atanmamis}], obeksiz:[{il, ilce, mahalle, acik}]}`. İşi 0 olan öbekler **dahil** |
| `POST /api/obekler` | `obek.duzenle` | `{ad, surum}` | 201 / 409 `ad_var` / 409 `guncel_degil` |
| `PATCH /api/obekler/{id}` | `obek.duzenle` | `{ad?, renk?, sahip_id?, surum}` | 200 / 409 `ad_var` (sessiz birleştirme yok) |
| `POST /api/obekler/{id}/mahalle` | `obek.duzenle` | `{mahalle_idler?: number[], tum_ilce?: [{il, ilce}], tasi: bool, surum}` | 200 `{surum, etkilenen_is}`. 409 `baska_obekte` `{catisma:[{ref, obek:{id,ad}}]}` (tasi=false iken) |
| `DELETE /api/obekler/{id}/mahalle` | `obek.duzenle` | `{refler:[…], surum}` | 200. Öbek boş kalsa da **silinmez** |
| `DELETE /api/obekler/{id}` | `obek.duzenle` | `?surum=` | 200 `{geri_al_olay_id}` (yumuşak silme) |
| `POST /api/obekler/geri-al` | `obek.duzenle` | `{olay_id, surum}` | 200 (10 dk içinde; sonra 409 `sure_doldu`) |
| `GET /api/mahalleler` | `obek.oku` | `?q=&il=&ilce=` | `{ilceler:[{il, ilce, mahalle_sayisi}], mahalleler:[{id, il, ilce, ad, ref, kaynak, dogrulandi, obek:{id,ad}\|null, acik}], oneriler:[…]}` |
| `POST /api/mahalleler` | `mahalle.ekle` | `{il, ilce, ad}` | 201 / 409 `var` + mevcut kayıt / 422 `ilce_yok` |
| `POST /api/mahalleler/yukle` | yönetici | multipart xlsx/csv | `{eklenen, var_olan, hatali:[satir]}` |
| `GET /api/takip` | `takip.oku` | `?gun=7` | §3.9'daki sayılar, yalnız toplamlar |
| `PUT /api/takip/kapasite` | `takip.oku` + operasyon/yönetici | `{tarih, aktif_teknik}` | 200 |
| `GET /api/ben` | giriş yapmış herkes | — | Bugünkü alanlar + `ana_ekran`, `izinler: string[]` (arayüz menüsü bundan çizilir) |
| `GET /api/kullanici/{id}/iliskiler` | `ekip.*` | — | `{silinebilir: bool, sayilar:{ziyaret, gorev, bina_durum, ticket, tur_raporu, bolge_plani, is_acik, is_olay, erisim, obek_sahip}}` |
| `DELETE /api/kullanici/{id}` | `ekip.*` | — | 204 / 409 `iliskili_kayit` + sayılar / 409 `kendini_silemez` / 409 `son_yonetici`. Kontrol ve DELETE tek işlemdedir. IntegrityError uçta yakalanır ve 409'a çevrilir (global 503 işleyicisine düşmez) |
| `POST /api/kullanici/{id}/is-aktar` | `ekip.*` | `{hedef_id}` | `{aktarilan}`. Açık işler yeni teknik kişiye; her biri olaylı |
| `POST/PUT /api/kullanici` (mevcut) | `ekip.*` | `rol ∈ 4 değer`, `etiket?`, `boss_ekip?`; bölge yalnız satışta | Rol ya da aktiflik değişince `oturum_no` +1 (bugünkü gibi). 409 `son_yonetici`, 409 `kendi_rolu` |

**Global hata işleyicisi.** `sqlite3.IntegrityError` artık 503 "BT'ye haber verin" değil, 409 `butunluk` döner: "Bu kayıt başka kayıtlarla bağlantılı olduğu için değiştirilemedi." Disk ya da kilit hataları 503 kalır.

### 4.7 Eşzamanlılık: iki operatör, bir sunucu

| Durum | Kural |
|---|---|
| İki kişi aynı işe atama yapar | Her iş `surum` taşır. Yazma şöyledir: `UPDATE is_emri SET …, surum = surum + 1 WHERE is_no = ? AND surum = ?`. 0 satır → 409 `guncel_degil` + güncel kayıt + son olayın sahibi ve zamanı. Kimse sessizce ezilmez |
| `surum` neyle artar | Yalnız operasyon alanlarıyla: durum, atama, randevu, ticket, elle öbek, elle mahalle, iletişim. BOSS alanları ve türetilen öbek sürümü **artırmaz**; eski ekrandaki BOSS bilgisinin eskimesi kimseye zarar vermez. Aktarım durumu ilerletirse `surum` artar |
| Öbek düzeni | Tek sayaç `ayar.obek_surumu`. Her öbek yazması `surum` taşır ve uyuşmazsa 409 + güncel öbek listesi alır. Mahalle taşıma iki öbeğe dokunduğu için öbek başına değil küresel sayaç seçildi (öbek düzenleme seyrek yapılır) |
| Aktarım ve düzenleme aynı anda | Aktarım hesabını işlem dışında yapar, yazmayı tek `BEGIN IMMEDIATE` işleminde yapar (<300 ms). SQLite yazıcıları sıraya koyar (busy_timeout 15 sn). Aktarım operasyon alanlarına dokunmaz |
| İki aktarım aynı anda | Süreç kilidi. İkincisi 409 `aktarim_suruyor` |
| Canlı pano | `GET /api/isler/degisim?imlec=` 20 sn'de bir çağrılır. İmleç `is_emri_olay.id`'dir. Öbek değişikliği `obek_surumu` üzerinden fark edilir ve öbek listesi yeniden alınır |
| Göç | Dosya kilidi + port kontrolünden sonra, sunucu açılmadan önce çalışır. Aynı anda iki göç imkânsızdır |
| Tek süreç | Sunucu tek uvicorn işçisiyle çalışır (bellek önbellekleri ve süreç kilitleri buna dayanır). `sunucu.py` `workers>1` isteğini reddeder |

### 4.8 Çevrimdışı teknik

- Telefon, durum yazmalarını IndexedDB kuyruğuna yazar. Mevcut `senkron.tsx` deseni kullanılır.
- Her yazma `istemci_id` (uuid) taşır. Sunucuda `UNIQUE(kullanici_id, istemci_id)` vardır. Tekrar gelen yazma işlenmez, ilk sonucu döner.
- Teknik yazmaları `surum` istemez. Sunucu geçişin mevcut durumdan geçerli olup olmadığına bakar.
  - Geçersizse 409 `gecersiz_gecis` döner. Örnek: iş bu arada başka teknik kişiye verilmişse 403 `kapsam_disi`.
  - Kuyruk bu yazmayı düşürür ve ekranda söyler: "Bu iş size ait değil artık; operasyon başka birine verdi."
- `sw.js`: `/api/isler*` GET istekleri **önce ağa** gider; ağ yoksa önbellekten gelir. Önbellekteki kopyada müşteri alanı bulunur; bu yüzden çıkışta önbellek silinir (mevcut çıkış akışına eklenir).

### 4.9 Başarım bütçeleri (test edilir)

| Ölçü | Bütçe |
|---|---|
| `GET /api/isler` (437 iş, operasyon) | < 150 ms |
| `GET /api/isler/{no}` | < 50 ms |
| Aktarım: okuma + hesap (iş parçacığında) | < 3 sn; yazma işlemi < 300 ms |
| Aktarım sırasında `/api/saglik` | < 300 ms (bugün 3,3 sn) |
| Öbek düzenleme (mahalle ekle/çıkar + işlerin yeniden hesabı) | < 150 ms |
| Göç v0→v4 (canlı kopya) | < 10 sn, yedek dahil |

### 4.10 Saklama ve temizlik

Görev her açılışta ve her gün 03:00'te çalışır (mevcut zamanlanmış görev yanına).

- Kapanıştan 30 gün sonra: `musteri_adi`, `musteri_no`, `musteri_tel`, `adres` → NULL. Olay yazılmaz; yalnız sayım günlüğe geçer.
- `operasyon/veri/gelen/*.xlsx`: 7 gün sonra silinir.
- `saha/yedek/aktarim/`: son 10 dosya tutulur.
- `saha/yedek/goc/`: **hiç silinmez** (elle).
- `son_yukleme.pkl` göçten sonra okunmaz. Silinmesi kullanıcı onayıyla olur; dosyada kişisel veri var (açık soru 11).
- Olay defteri ve erişim kaydı 180 gün sonra da silinmez (şimdilik). Sıkıştırma, OT §7'deki gibi ayrı bir göçle yapılır.

---

## 5. Tasarım sistemi

**İlke.** Satışçı uygulaması (Bugün, Bina, Sonuç paneli, Harita) denetimde çıtayı tutan tek bölümdü. Onun dili yönetim ekranlarına taşınır: sakin kart, tek birincil eylem, 44 px hedef ve doğru karanlık mod. Tersi yapılmaz.

### 5.1 Tokenlar (`src/stil/temel.css :root`; yönetici CSS'indeki sabit renkler bunlara çevrilir)

| Token | Açık | Koyu | Kullanım / ölçüt |
|---|---|---|---|
| `--zemin` | #EFF1F5 | #0F1319 | Sayfa zemini |
| `--kart` | #FFFFFF | #181D26 | Kart, liste, panel |
| `--kart-bas` | #F7F8FA | #1E242F | Grup başlığı, seçili satır |
| `--cizgi` | #E2E6ED | #2A313D | Ayırıcı |
| `--metin` | #101828 | #EEF1F6 | Ana yazı |
| `--metin-2` | #475467 | #B4BCC8 | İkincil yazı (≥7:1) |
| `--metin-3` | #667085 | #8C95A3 | Üçüncül yazı (kartta ≥4,5:1) |
| `--birincil` | #0B63E5 | **#2F6FEB** | Dolgu düğme, üstü beyaz yazı: 5,3:1 / 4,6:1. Bugünkü koyu #4D95FF'de beyaz yazı 2,98:1'di |
| `--birincil-yazi` | #0B63E5 | #7CB2FF | Bağlantı, seçili sekme |
| `--yesil` / `-yumusak` | #0F8A4A / #E3F6EC | #3ECF82 / #123024 | Kalan süre < %50, "Hepsi yerinde" |
| `--amber` / `-yumusak` | #A55A06 / #FFF2E0 | #F0B45C / #33260F | ≥ %50, bekleme 10 dk |
| `--kirmizi` / `-yumusak` | #C02A2A / #FDEAEA | #FF8A8A / #3A1A1C | ≥ %80, gecikti, sil |
| `--mor` / `-yumusak` | #6033C9 / #EFE9FD | #B79BFF / #2A2140 | Randevu dilimi |
| `--gri` / `-yumusak` | #6E7889 / #EEF1F5 | #9AA3B2 / #232A35 | Nötr rozet |

- Uyarı kutuları (`.yon-uyari-*`) koyu modda **açık yazı + koyu renkli zemin** kullanır (`--kirmizi` üstünde `--kirmizi-yumusak`). Bugünkü 1,6–1,7:1'lik kutular düzelir.
- Öbek renkleri bir paletten gelir (8 renk, her birinin koyu karşılığı var). Öbek adı her zaman nötr yazıyla ve yanında renk noktasıyla yazılır; renkli zeminde yazı yoktur.
- Karanlık mod `@media (prefers-color-scheme: dark)` ile gelir. Ayrıca `:root[data-theme]` ile elle seçim yapılabilir ("Görünüm: Sistem · Açık · Koyu", Ben / Daha fazla içinde).
- `index.html` iki `theme-color` taşır (media sorgulu).
- Haritada koyu modda varsayılan altlık "Sade"dir.
- Tipografi: sistem yazı tipi. Boyutlar 13 · 15 · 17 · 20 · 28 px. Telefonda gövde 17, masaüstünde 15. Kalınlıklar 400 ve 600. Sayılarda `font-variant-numeric: tabular-nums`. En küçük yazı 13 px (bugün 10,5 px var).
- Boşluk 4'ün katlarıdır: 4 · 8 · 12 · 16 · 24 · 32. Köşe `--yaricap` 16 / `--yaricap-k` 12.
- Dokunma hedefi en az 44 × 44 px. Telefonda birincil düğme 56 px.

### 5.2 Bileşenler

| Bileşen | Dosya | Not |
|---|---|---|
| `Liste`, `ListeSatiri` | `ortak/Liste.tsx` (yeni) | 2–3 satırlı; sol ek (hap/simge), sağ ek (rozet/ok); 44–72 px |
| `SureHapi` | `ortak/SureHapi.tsx` | `kalan_dk` → "2 s 10 dk" / "Gecikti · 17 s"; renk §2.4 |
| `Rozet` | `ortak/Rozet.tsx` | BTK · Ticket · Tekrar · Bayi · Global · BOSS'a işlenecek · elle |
| `DurumYazisi`, `AdimCizgisi` | `ortak/Durum.tsx` | Nötr yazı + nokta; 5 adımlık ince çizgi |
| `Panel` (sağ) / `Cekmece` (alt) | `ortak/Cekmece.tsx` (var) + `Panel.tsx` | Masaüstünde sağdan 420 px; telefonda tam ekran ya da alttan |
| `Onay` | `ortak/Onay.tsx` | `window.confirm` yerine: başlık, tek cümle, iki düğme (yıkıcı olan kırmızı ve sağda) |
| `GeriAlBildirimi` | `ortak/Bildirim.tsx` (var) + eylem | 10 sn; "Geri al" |
| `Segment` | `yonetici/ortak/parcalar.tsx` (var) | Dar ekranda yatay kayar; taşmaz |
| `SuzMenusu` + `SuzCipi` | `ortak/Suz.tsx` | Tek "Süz" düğmesi; etkin süzgeçler kaldırılabilir çip |
| `MahalleSecici` | `yonetici/is/MahalleSecici.tsx` | Arama, ilçe grupları, "İlçenin tamamı", "Listede yok mu?", "hangi öbekte" |
| `TeknikSecici` | `yonetici/is/TeknikSecici.tsx` | Ev teknisyeni üstte; bugünkü yük; pasifler gizli |
| `RandevuSecici` | `yonetici/is/RandevuSecici.tsx` | Gün çipleri + 2 saatlik dilim çipleri + "yok" |
| `SekmeCubugu` | `ortak/AltBar.tsx` (genişler) | Role göre 2–4 öğe |
| `BaslikCubugu` | `ortak/Sayfa.tsx` (var) | 44 px; geri oku; tek "…" ya da "+" |
| `BosDurum`, `Iskelet`, `HataKutusu` | var | Her listede |

### 5.3 Masaüstü ve telefon kuralları

| Kural | Masaüstü (≥1024) | Telefon (<768) |
|---|---|---|
| Gezinme | Sol menü, gruplar katlanır | Alt sekme çubuğu + itmeli gezinme |
| Ayrıntı | Sağ panel (≥1440 yan yana, altında üstte) | Tam ekran |
| Tablo | Serbest (öbekler, takip) | **Tablo yok**; satır listesi |
| Kaydırma | Bölme başına bir | Ekran başına **bir**; iç içe yok |
| Birincil eylem | Panel altında bir tane | Yapışkan alt çubukta bir tane |
| Klavye | `/` ara · ↑↓ iş seç · `A` ata · `R` randevu · `Esc` kapat | — |
| Harita | "Liste \| Harita" düğmesi | Aynı; varsayılan liste |
| Başlık eylemleri | Sağda en çok 2 düğme | Tek "…" ya da "+" |

Doğrulanan genişlikler (F19): **1440 · 1366 · 393 px**, açık ve koyu. Ek: 1024 ve 768.

### 5.4 Dil

- Fiiller sadedir: "Ata", "Randevu ver", "Öbeğe taşı", "Ticket bağla", "Pasife al", "Sil", "Geri al".
- İç jargon ekrana çıkmaz: "parça" yerine "Bugünkü ekiplere dağıt", "yarıçap" gösterilmez.
- Her ekranın başlığının altında tek cümle vardır: "Bu ekranda ne yaparım?" Örnek (İşler): "Gelen işleri teknisyene atayın; kırmızılar önce."
- Sayı ve tarih biçimi `ortak/bicim.ts` ile verilir: 1.234 · %43 · 30.09.2026 14:05 · "3 s 10 dk" · "12 dk önce".
- Bütün metinler Türkçe harflerle yazılır (ı İ ş ğ ü ö ç).

---

## 6. Kabul testleri

Taban çizgisi 213 yeşil testtir. Hepsi kopyalarla çalışır (`OPERASYON_OBEK`, `OPERASYON_VERI`, `SAHA_DB` geçici dizine). Canlı `saha.db` ve `obekler.json` **okunmaz ve yazılmaz**. Gerçek BOSS dosyası ve canlı yedek yoksa ilgili testler atlanır (skip).

### 6.1 F1–F22 eşlemesi

| # | Test (dosya · ad) | Tür | Geçer, eğer… |
|---|---|---|---|
| F1 | `operasyon/testler/test_obek_db.py::test_mahalle_ekle_cikar_is_sayisi` · `qa/v2/obek-duzenle.mjs` | pytest + Playwright | Öbeğe mahalle eklenip çıkarılınca aynı yanıtta etkilenen iş sayısı döner. `GET /api/isler` öbek sayıları değişir. Ekranda öbek düzenleyici mahalleleri listeler, × ile çıkarılan mahalle yenilemesiz kaybolur ve pano sayısı değişir |
| F2 | `test_obek_db.py::test_rapordisi_mahalle_ve_ilce_tamami` · `qa/v2/mahalle-secici.mjs` | pytest + PW | "Bursa/Gürsu/*" ve elle eklenen "Göçmen" (seçilen ilçede) işi 0 olan öbeğe eklenir. Öbek listede görünür (0 iş, silinmez). Sonraki aktarımda bu mahalledeki sentetik iş o öbeğe düşer. Seçicide "Gürsu" araması "İlçenin tamamı" satırını gösterir; 23 ilçenin hepsi listededir |
| F3 | `test_isler_api.py::test_obek_isleri_musteri_alanlari` · `qa/v2/obek-isleri.mjs` | pytest + PW | Operasyon için `?`→öbek süzgeçli satırlar `musteri_adi`, `kisa_adres`, `task_adi`, `durum`, `kalan_dk`, `randevu`, `atanan` taşır. Ekranda öbeğe tıklayınca ≥1 satır görünür. Telefonda öbek → işler → iş kartı itmeli gezinmesi çalışır |
| F4 | `test_aktarim.py::test_lokasyon_db_esleme` · `test_lokasyon_sifirli` | pytest | Gerçek raporda (varsa) kontrol = 0. Lokasyon eşleşmesi DB üzerinden 332/332. "00123456" ↔ "123456" aynı binaya düşer. Bina mahallesi adresten önce gelir |
| F5 | `test_akis.py::test_il_disi_elle_obek_kalici` | pytest | İl "İzmir" olan sentetik iş `triyaj/il_disi` olur. `POST …/obek` → `bekliyor`, `obek_elle_id` dolu. Aynı rapor değişik sırayla yeniden yüklenince elle öbek korunur |
| F6 | `saha/testler/test_yetki_matrisi.py` · `qa/v2/rol-girisleri.mjs` | pytest + PW | Uygulamadaki **her** uç × 5 kimlik (satış, bölgesiz satış, operasyon, teknik, yönetici) × beklenen kod tablosu tutar. Tabloda olmayan uç testi kırar. Girişten sonra her rol kendi ana ekranına düşer |
| F7 | `test_akis.py::test_ata_teknik_gorur` · `qa/v2/teknik-islerim.mjs` | pytest + PW | Operasyon atar → teknik `GET /api/isler` yalnız o işi görür, başka işi 404 alır. Telefon görünümünde İşlerim'de iş görünür |
| F8 | `test_akis.py::test_randevu_kurallari_ve_sira` | pytest | Geçersiz randevular 422 alır (bitiş < başlangıç, >7 gün, >4 saat dilim). Teknik listesi randevu başlangıcına göre sıralı, randevusuzlar sonda |
| F9 | `test_akis.py::test_ticket_bagla_altyapi_cozulunce_doner` | pytest | Ticket bağlanınca iş `altyapi` olur ve rozet görünür. Binada açık ticket varken bağlanmamış işe atama 409 `altyapi_engeli` alır. Ticket ÇÖZÜLDÜ olunca iş `bekliyor` olur ve olay yazılır |
| F10 | `test_akis.py::test_uctan_uca_durum_makinesi` | pytest | Aktarım → randevu → ata → yolda → sahada → çözüldü → iş olmayan rapor → `kapandi (cozuldu_dogrulandi)`. Her adımda olay ve doğru kişi var. Tablo dışı her geçiş 409 alır (bütün çiftler döngüyle denenir) |
| F11 | `qa/v2/matris.mjs` | Playwright | İşler, İş kartı, Öbekler, Takip, Ekip, İşlerim: 1440 · 1366 · 393 × açık/koyu. Her görünümde tek birincil düğme, 0 yatay taşma, telefonda 0 küçük hedef (<44 px), 0 kontrast hatası (<4,5:1, hesaplanmış renkle). Ekran görüntüleri `saha_app/qa/v2/` altına |
| F12 | `test_ekip.py::test_dort_gorev` · `qa/v2/ekip.mjs` | pytest + PW | Formda 4 görev var. Bölge yalnız Satış'ta. DB CHECK 'hacker' değerini reddeder. Rol değişince `oturum_no` +1 olur, `pin_hash` değişmez |
| F13 | `test_kullanici_sil.py` (5 durum) · `qa/v2/ekip-sil.mjs` | pytest + PW | Kaydı yok → 204 ve id yeniden kullanılmaz. Ziyareti/işi var → 409 + sayılar. Kendini → 409. Son yönetici → 409. Açık işi olan pasife alınırken önce "İşleri aktar". Ekranda uyarı + "Pasife al" görünür, `window.confirm` çağrılmaz |
| F14 | `qa/v2/ilk-gun.mjs` + elle koridor testi | PW + gözlem | Senaryolu yol: girişten ilk atamaya ≤5 tıklama (bırak → öbek → iş → Ata). Her ekranda "Bu ekranda ne yaparım?" cümlesi var. Jargon listesi (`parça`, `yarıçap`, `RES HP`…) operasyon ekranlarında 0. Elle: ilk kez gören bir çalışan rehbersiz ilk işi ≤2 dk'da atar |
| F15 | `test_takip.py::test_satis_karti` | pytest | Takip yanıtında satış kartı (ziyaret, satış, sahadaki satışçı) mevcut özetle aynı sayıları verir. Satışçının açtığı talep operasyonun "Kontrol gerekli" listesine düşer |
| F16 | `test_akis.py::test_bayi_isi_ve_boss_baglama` · `test_kanal_grubu` | pytest | `POST /api/isler` → `B-…`, `kaynak=bayi`. `boss-bagla` sonrası o Task No'lu rapor aynı satırı günceller; toplam iş sayısı artmaz. Kanal grubu eşlemesi 5 örnekte doğru |
| F17 | `test_takip.py::test_atama_suresi` (dondurulmuş saat) · `qa/v2/bekleme.mjs` | pytest + PW | Aktarım 10:00, atama 10:09 → medyan 9 dk, oran doğru. Yeniden açılan iş saati sıfırlar. Atanmamış satırda "geleli N dk" yazar; 10/15 dk'da renk değişir |
| F18 | `test_aktarim.py` (8 durum) | pytest | (1) Aynı dosya 2× → `ayni_dosya`, DB özeti değişmez. (2) Ters sıralı aynı içerik → 0 yeni, parça/atama/randevu korunur. (3) Eksik iş → `kapandi`. (4) Geri gelen → `yeniden_acildi`, `acilma_sayisi=2`. (5) %40 eksik → 409 `onay_gerekli`. (6) Eski rapor → 409. (7) Eşzamanlı iki yükleme → biri 409. (8) Yükleme sırasında `/api/saglik` <300 ms (gerçek uvicorn, 127.0.0.1:809x) |
| F19 | `qa/v2/matris.mjs` (F11 ile aynı koşu) | Playwright | 1440 · 1366 · 393 ekran görüntüleri; taşma 0; konsol hatası 0 |
| F20 | `saha/testler/test_guncelleme_canli_kopya.py` · `test_goc.py` | pytest | §6.2'nin tamamı |
| F21 | `test_yetki_matrisi.py::test_musteri_alanlari` | pytest | Operasyon ve yönetici müşteri adı ve no'yu görür. Teknik yalnız kendi **açık** işinde görür; kapanınca alan yoktur. Satış yalnız kendi açtığında görür. Diğer yanıtlarda anahtar hiç yoktur. Her görüntülemede `erisim_kaydi` satırı yazılır. 30 gün sonra alanlar NULL olur (saat ileri alınarak) |
| F22 | `docs/GEREKSINIMLER.md` §F satırları | Belge | Her yinelemede durum sütunu ve test adı güncellenir. Kullanıcıya "ne bitti / ne kaldı" tek tabloyla verilir |

### 6.2 Yükseltme testi: canlı kopya (F20)

`saha/testler/test_guncelleme_canli_kopya.py`. `saha/yedek/saha-2026-09-30.db` yoksa atlanır.

1. Kaynak `file:…?mode=ro&immutable=1` ile açılır, backup API ile `tmp_path` içine kopyalanır. Kaynakta -wal/-shm oluşmadığı doğrulanır.
2. Önce bütün tabloların satır sayısı ve satır özetleri (sha256) alınır. `kullanici` için 10 sütunun özeti alınır.
3. `goc.hazirla()` çalıştırılır. Beklenenler:
   - `user_version = 4`.
   - `integrity_check = ok`, `foreign_key_check` boş.
   - Eski tabloların hepsi satır satır aynı (`ayar.saglik_kontrol` hariç).
   - `kullanici` 10/10 aynı.
   - `sqlite_sequence.kullanici` ≥ 19.
   - Bütün yabancı anahtarlar `kullanici`ya bakar (`pragma_foreign_key_list`).
   - `rol` CHECK 'teknik' ve 'operasyon' değerlerini kabul eder, 'hacker' değerini reddeder.
4. Göç öncesi yedek dosyası:
   - Var, salt okunur, `integrity_check = ok`.
   - `journal_mode = delete`.
   - Satır sayıları kaynakla aynı.
5. Öbek aktarımı (canlı `obekler.json`'un **kopyasıyla**):
   - 14 öbek, 120 mahalle.
   - Her ref için DB `bul()` = JSON `bul()`.
   - Kopya JSON'un sha256'sı göçten önce ve sonra aynı (dosyaya yazılmadı).
6. Oturum: kopyadaki bir kişi için test anahtarıyla üretilen jeton göçten önce ve sonra `/api/ben` için 200 döner. Rolü `teknik` yapılan kişinin eski jetonu 401 alır (oturum_no arttı); PIN ile yeniden giriş 200 döner.
7. İkinci `goc.hazirla()` hiçbir şey yapmaz ve yedek almaz.
8. **Çökme enjeksiyonu** (ayrı kopyalarda):
   - v1'de INSERT'ten sonra, DROP'tan sonra ve RENAME'den sonra istisna → her birinde DB özeti göç öncesiyle **birebir** aynı, `user_version = 0`.
   - `os._exit` ile süreç öldürme (alt süreç) → aynı sonuç.
9. Yanlış desen koruması: bir test, "önce eskiyi yeniden adlandır" deseninin 11 yabancı anahtarı bozduğunu gösterir. Birisi bu deseni yeniden yazarsa kod incelemesinde neden yasak olduğu görülsün.
10. Gerçek BOSS dosyası varsa (salt okunur): göçten sonra aktarım 437 iş verir. Her işin öbeği bugünkü JSON motoruyla aynıdır (437/437).

Ayrıca:

- `test_goc.py::test_checksiz_eski_sema`: test_kalite'nin ESKI_SEMA'sı sorunsuz v4'e çıkar.
- `test_goc.py::test_bilinmeyen_rol_durdurur`: tanınmayan rol varsa göç ROLLBACK eder, `GocHatasi` Türkçe mesaj taşır.
- `test_goc.py::test_port_doluyken_goc_yok`: port doluyken göç çalışmaz.

### 6.3 Güvenlik matrisi (deny-by-default kanıtı)

`test_yetki_matrisi.py`, `uygulama.routes` listesindeki her yolu ve yöntemi gezer. Her birinin `YETKI_TABLOSU`'nda bir satırı olmalıdır: `{(yöntem, yol): {rol: beklenen_kod}}`. Satır yoksa test kırılır.

Tabloda en az şu bugünkü sızıntılar kilitlenir:

- Bölgesiz teknik ve bölgesiz satış için `/api/bina`, `/api/harita`, `/api/yollar`, `/api/ozet/kapsama`, `/api/binalar/geometri` → 403.
- `POST /api/ziyaret` → 403.
- `/api/ben` → kendi dalı.

---

## 7. Uygulama planı: 5 ajan, 1–2 gün

**Sözleşme önce.** Ajan 2 ilk 2 saatte §4.6'daki tipleri ve örnek yanıtları yazar: `operasyon/ornek_yanitlar/*.json`, kişisel veri yok, sentetik ad. Arayüz ajanları bu örneklerle başlar. Ajan 1 ilk yarım günde şema sabitlerini `saha/sema_v2.py` olarak verir.

| Ajan | İş | Sahip olduğu dosyalar | Testler |
|---|---|---|---|
| **1 · VERİ-GÖÇ** | §4.1–4.4 ve §4.2'nin bütün koruyucuları: `goc.py`, v1–v4, göç yedeği, doğrulama; `sunucu.py` sırası ve kilidi; ısıtma yarışı; `kur.py`/`baslat.bat` korumaları, `GERI_YUKLE.bat`, `KORUNAN.txt`; öbek JSON → DB; mahalle sözlüğü tohumu; pickle taşıma; `.gitignore` | `saha/goc.py`, `saha/sema_v2.py`, `saha/db.py`, `saha/yedekle.py`, `saha/sunucu.py`, `saha/kur.py`, `saha/*.bat`, `api.py` içinde yalnız lifespan bloğu | `test_goc.py`, `test_guncelleme_canli_kopya.py` |
| **2 · İŞ MOTORU** | §2 ve §4.5–4.8: `akis.py` (durumlar, geçiş tablosu, tetikleyici üretimi), `depo.py` (SQL), `aktarim.py` (hat, fark, bekçiler), `is_emri.py` (DB'den Lokasyon ve sözlük, köy biçimleri), yeni yönlendiriciler (`/api/isler`, `/api/aktarim`, `/api/obekler`, `/api/mahalleler`, `/api/takip`), saklama görevi | `operasyon/*.py` (`obekler.json` hariç), `operasyon/ornek_yanitlar/` | `test_aktarim.py`, `test_akis.py`, `test_obek_db.py`, `test_isler_api.py`, `test_takip.py` |
| **3 · YETKİ-EKİP** | §1: `yetki.py` + izin bağımlılıkları; `api.py` ve `yonetim_uclari.py` korumaları; `/api/ben`; kullanıcı 4 rol, etiket, boss_ekip, davet 48 s; silme, ilişkiler, iş aktar; IntegrityError işleyicisi. Arayüz: `Ekip.tsx`, `yonetici/api.ts`, `tipler.ts` | `saha/yetki.py`, `saha/api.py` (lifespan hariç), `saha/yonetim_uclari.py`, `saha_app/src/yonetici/ekran/Ekip.tsx`, `yonetici/api.ts`, `yonetici/tipler.ts`, `api/tipler.ts` | `test_yetki_matrisi.py`, `test_ekip.py`, `test_kullanici_sil.py` + mevcut rol testlerinin güncellenmesi |
| **4 · OPERASYON ARAYÜZÜ** | §5 tokenları ve bileşenleri; `Kabuk.tsx` (yeni menü, telefonda sekme çubuğu, demo bandı); İşler panosu, İş kartı, Ata/Randevu/Öbeğe taşı, Öbekler + düzenleyici + MahalleSecici, Rapor yükle + geçmiş | `src/stil/temel.css`, `yonetici/yonetim.css`, `yonetici/ortak/*`, `src/ortak/{Liste,SureHapi,Rozet,Durum,Onay,Suz,Panel}.tsx`, `yonetici/ekran/{Isler,Obekler,RaporGecmisi}.tsx`, `yonetici/is/*` | `qa/v2/obek-duzenle.mjs`, `mahalle-secici.mjs`, `obek-isleri.mjs` |
| **5 · TEKNİK + TAKİP + QA** | İşlerim ve iş ekranı (telefon, çevrimdışı kuyruk); rol yönlendirmesi (`App.tsx`, `oturum.tsx`, `AltBar.tsx`); `Giris.tsx` (klavye, 360 px); Takip; Yeni iş emri (ortak form); `sw.js`; Playwright matrisi ve kontrast ölçer | `src/ekran/{Islerim,IsEkrani}.tsx`, `src/App.tsx`, `src/depo/oturum.tsx`, `src/ortak/AltBar.tsx`, `src/ekran/Giris.tsx`, `yonetici/ekran/{Takip,YeniIs}.tsx`, `src/sw.js`, `saha_app/qa/v2/*.mjs` | `matris.mjs`, `rol-girisleri.mjs`, `teknik-islerim.mjs`, `ilk-gun.mjs`, `bekleme.mjs` |

**Sıra.**

- **1. gün sabah:** 1 (şema, göç), 2 (sözleşme + motor), 3 (yetki iskeleti + matris). 4 ve 5 örnek yanıtlarla ekran.
- **1. gün öğleden sonra:** Birleştirme. Test sunucusu yalnız 127.0.0.1:8090–8099'da, canlı kopya üzerinde çalışır.
- **2. gün:**
  1. Canlı kopya yükseltme testi.
  2. Gerçek raporla aktarım (yalnız test sunucusuna).
  3. Ekran matrisi (1440/1366/393 × açık/koyu).
  4. "Üret → test et → düzelt → tekrarla" döngüsü.
  5. Belgeler: `SAHA_SOZLESME` §8, `SAHA_KULLANIM` (İşler, Öbekler, İşlerim, Ekip), `GEREKSINIMLER` §F durumları.

**Bitti sayılır, eğer:**

- 213 + yeni testlerin hepsi yeşil.
- Canlı kopya yükseltme testi yeşil.
- Gerçek raporda 437 iş, 437 öbek eşleşmesi ve 332/332 Lokasyon.
- Matris ekran görüntüleri gözden geçirildi.
- Canlı `saha.db` ve `obekler.json`'a dokunulmadığı dosya zamanı ve sha ile gösterildi.
- Kullanıcıya **güncelleme günü talimatı** verildi:
  1. `DURDUR.bat`
  2. Yeni klasör (korunan dosyalar yerinde)
  3. `BASLAT.bat` → konsoldaki "Güncelleme tamam … aynen korundu" satırı
  4. Ekip → 8 kişinin görevini seç
  5. Sorun olursa `GERI_YUKLE.bat`

---

## 8. Açık sorular (kullanıcı kararı)

1. **Kanal (F16):**
   - "Global (dış kanal)" ile BOSS Satış Kanalı'ndaki "GLOBAL…" değerleri mi kastediliyor?
   - "Bayinin oluşturduğu" iş BOSS'ta bayi kullanıcısının açtığı iş mi, yoksa yalnız bu sistemde açılan iş mi?
   - Öneri: iki ayrı alan. `kaynak` (sistem içi / BOSS) ve `kanal_grubu` (Satış Kanalı'ndan). Eşleme tablosu teyit edilince kesinleşir.
2. **Müşteri telefonu (F21 ↔ OT §6.5):** Operasyon telefonu elle girebilsin mi? Öneri: evet. Yalnız operasyon, yönetici ve atanmış teknik görür; kapanış + 30 günde silinir; her gösterim kayda geçer. Hayır denirse ayarla kapatılır.
3. **Teknik müşteri adını görsün mü?** Öneri: yalnız kendi açık işinde ad, Müşteri No ve adres. OT §5.4 "teknisyen BOSS Mobil'den bakar" diyordu.
4. **Rol adı:** `teknik` (F12'deki söz) + `etiket: lider` mi, yoksa OT §5.1'deki `teknisyen` / `teknik_lider` mi? Öneri: `teknik` + etiket. Tek yeniden kurma, ileride yeni kurma yok.
5. **Mahalle listesi:**
   - Göçmen hangi ilçede?
   - Bursa (17) + Yalova (6) için resmî tam liste (UAVT/TÜİK, koordinatlı) BT'den alınabilir mi?
   - Alınana kadar "Listede yok mu? Ekle" ile çalışılır.
6. **Mevcut 8 "yönetici" hesap:** Kim Operasyon, kim Teknik, kim Yönetici? Sistem tahmin etmez. Güncellemeden sonra Ekip ekranında sizin seçmeniz gerekir. Rolü değişen kişi bir kez yeniden giriş yapar.
7. **Kurulum filtresi (C5 ↔ C17):** "Kurulum Taskı Ürememiş" ve "Kurulumsuz …" adlı işler mevcut müşteride mi kalsın? Bugün adında "kurulum" geçen her iş çıkarılıyor.
8. **BOSS bağlantısı:** "BOSS'ta aç" için bir adres şablonu var mı (`…?taskNo={task_no}`)? Yoksa yalnız "Task No'yu kopyala" kalır.
9. **Eksik rapor eşiği:** Kaybolan > max(50, açık işlerin %25'i) olunca onay istensin mi? Rakamlar ayarla değişir.
10. **Giriş ekranı (C9):** Üç birim kutusu (Satış · Teknik · Operasyon) yine de istensin mi? Öneri: hayır. Rol telefondan bilinir, bir adım eksilir.
11. **Eski pickle:** `operasyon/veri/son_yukleme.pkl` (müşteri adı ve adres içeriyor) göçten sonra silinsin mi? Öneri: 7 gün sonra, sizin onayınızla.
12. **Kapasite sayısı:** "Bugün sahada kaç teknisyen var" her sabah elle mi girilsin? Öneri: varsayılan = bugün işi olan teknik sayısı, üzerine −/+ ile düzeltme.

---

## 9. Alınmayanlar ve nedenleri

| Seçenek | Neden alınmadı |
|---|---|
| `kullanici`'yı "önce eskiyi yeniden adlandır" kalıbıyla kurmak (bugünkü `gocler` kalıbı) | Kopyada doğrulandı: 11 yabancı anahtar `kullanici_eski`ye yeniden yazılıyor, silinince bütün ziyaret yazmaları hata veriyor |
| `writable_schema` ile CHECK'i yerinde değiştirmek | Çalışıyor ama tek yazım hatası şemayı bozar ve ileride SQLITE_DBCONFIG_DEFENSIVE açık sürümde çalışmaz |
| CHECK'e dokunmayıp yeni bir `gorev` sütunu eklemek | Yetkinin iki kaynağı olur. Her kontrol iki sütuna bakar ve bir gün biri unutulur |
| Rolleri tamamen tetikleyiciyle korumak (CHECK'siz tablo) | Denenmiş ve doğrulanmış CHECK varken yeni ve denenmemiş bir yol açmak gerekmedi. Alt görevler `etiket` ile çözülüyor. Yeni tablolarda tetikleyici kullanıldı, çünkü orada liste büyüyecek |
| İşleri pickle/JSON'da tutmaya devam etmek | Sürüm değişince sessizce kayboluyor, iki kullanıcıyı ayırmıyor, geçmiş ve fark yok, kişisel veriyi şifresiz tutuyor |
| Her yüklemede "hepsini değiştir" | Sabah yapılan atamalar öğlen yüklemesinde siliniyordu (denetimde 6/6 parça → 0) |
| Öbekleri JSON'da bırakıp üstüne kilit koymak | Sürüm ve çakışma, "bir mahalle tek öbekte" kuralı ve geçmiş, SQLite'ta tek satırlık kısıt. JSON'da ise elle yazılmış kod |
| Sisteme BOSS'a otomatik yazdırmak | Turkcell sistemlerine otomatik yazma kırmızı çizgi (OT §6.1). Yerine "BOSS'a işlenecekler" giden kutusu ve sonraki raporda doğrulama |
| Operasyona müşteriyi maskeli göstermek (OT §6.5 aynen) | F21 ile çelişiyor: operasyon randevu için müşteriyi bulmak zorunda. Yerine rol, kayıt ve süre sınırı |
| Giriş ekranında birim seçimi | Rol zaten biliniyor. Seçim yalnız yanlış kapı açma riski ve bir adım daha getiriyor (açık soru 10) |
| Bu turda FOX içe alma, masa kuyruklarının tamamı, KARMA-2 kotaları, SMS | 1–2 günlük kapsamı aşar. Hat (`ie_aktarim.kaynak`), durumlar (E1–E6) ve olay defteri bunlara hazır kuruldu. OT Faz 1'in kalanı ve Faz 2'de eklenir |
