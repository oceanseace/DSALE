# Eklenti sayfa haritası (salt okunur keşif)

Tarih: 30.09.2026 · Amaç: tarayıcı eklentisinin (BOSS · OWA · WhatsApp Web · Atmosfer · ONENT · FOX)
ekranlarında **nereye bakacağını** yazmak. Bu belge yalnız **yapı** içerir: adres, alan etiketi, CSS seçici,
tablo başlığı, sayı. Müşteri ya da çalışan verisi (ad, telefon, adres, müşteri no, mesaj metni) **yoktur**.

Kural: bu belgedeki her seçici, eklentide **tek bir dosyada** (ör. `secici.js`) tutulur. Turkcell ekranı
değişince yalnız o dosya güncellenir; eklenti seçici bulamazsa sessizce bozulmaz, "Bu ekran değişmiş,
yöneticiye haber verin" der.

---

## 0. Özet: ne haritalandı, ne engellendi

| # | Sayfa | Durum | Nasıl bakıldı |
|---|---|---|---|
| 1 | BOSS `boss.turkcell.com.tr/technical-tasks` | **Erişilemedi** (`ERR_CONNECTION_TIMED_OUT`) | Bağlı tarayıcı şirket ağında değil |
| 2 | OWA `mail.turkcell.com.tr/owa/` | **Giriş gerekli** (F5 `…/my.policy` giriş sayfasına yönlendi) | Yönlendirme adresi |
| 3 | WhatsApp Web `web.whatsapp.com` | **Canlı haritalandı** (sohbet listesi, sohbet başlığı, mesaj satırı işaretleri) | DOM yapısı, değerler maskeli |
| 4 | Atmosfer personel listesi | **Giriş gerekli** (`/auth/login`), ama sayfa kodu (herkese açık `main.js`) okundu: **seçiciler ve API kesin** | React paket kodu |
| 5a | ONENT `onent.turkcell.com.tr` | **Giriş gerekli** (F5 `…/my.policy`) | Yönlendirme adresi |
| 5b | FOX `foxsaha.global-bilgi.entp` | **Erişilemedi** (`DNS_PROBE_FINISHED_NXDOMAIN`, iç ağ adı) | — |

**Engel (açıkça):** Claude-in-Chrome'a bağlı tek tarayıcı `Browser 1 / macOS` idi (`isLocal=false`). Kullanıcının
BOSS'a girdiği **Windows bilgisayardaki Brave** bağlı değildi. Bu yüzden şirket içi adresler (BOSS, FOX) açılmadı,
SSO arkasındaki sayfalar (OWA, ONENT, Atmosfer) giriş istedi. Şifre girilmedi. WhatsApp haritalaması sırasında
sekme grubu dışarıdan kapandı (tarayıcının başındaki kişi kapatmış olabilir); **sekme yeniden açılmadı**,
keşif orada durduruldu.

**Sonraki adım (BOSS ve FOX için şart):** keşif turu, kullanıcının Windows bilgisayarındaki **Brave** üzerinden
tekrarlanmalı (Chrome'da kurumsal DevTools politikası eklenti betiğini engelliyor; bkz. proje notları). İki yol:

1. Claude-in-Chrome eklentisi Windows Brave'e bağlanır, bu görev yeniden çalıştırılır (30 dk).
2. Eklentinin ilk sürümü bir **"Yapı keşfi"** düğmesiyle çıkar (§6). Kullanıcı BOSS'ta bir kez basar, eklenti
   maskeli yapı dökümünü (değer yok) sunucuya yollar; seçiciler oradan doldurulur.

---

## 1. BOSS — teknik task listesi ve task detayı

**Durum: canlı haritalanamadı** (bağlı tarayıcıdan `ERR_CONNECTION_TIMED_OUT`; BOSS yalnız şirket ağından açılıyor).

Bilinenler (repo belgelerinden, canlı değil):

| Konu | Bilgi | Kaynak |
|---|---|---|
| Adres | Görevdeki adres `https://boss.turkcell.com.tr/technical-tasks`. `docs/TURKCELL_SUREC_BILGISI.md` BOSS için `boss.superonline.net` diyor. **Eklenti ikisini de eşlemeli.** | görev metni + süreç belgesi |
| Dışa aktarım | `TeknikTaskDetayRaporu.xlsx`, 51 kolon. Eklentide kullanılacak başlıklar: `Task No` (= Fox Akış No, tekil anahtar), `Task Adı`, `Ekip`, `Lokasyon` (= bina `location_id`), `Müşteri No`, `Randevu Durumu`, `Randevu Başlangıç Tarihi`, `Randevu Bitiş Tarihi`, `Merkeze Gönder Statüsü`, `Durum` | `operasyon/analiz/entegrasyon.md` §2.1, `operasyon/is_emri.py` |
| Müşteri telefonu | Raporda **yok**; teknik ekip detay ekranından elle alıyor (GEREKSINIMLER C14). Eklenti yalnız **etiketi** bilmeli, değeri sunucuya yalnız kullanıcı "Getir"e basınca taşımalı. | GEREKSINIMLER |
| Randevu | Randevu ataması BOSS'ta yapılır, tarih/saat task'a not olarak da girilir. | süreç belgesi §3 |

**Keşif turunda doldurulacak boşluklar** (Windows Brave'de, yalnız yapı):

| # | Soru | Nasıl bakılır | Sonuç |
|---|---|---|---|
| B1 | Liste sayfası SPA mı? Çatı (Angular `[ng-version]` / React `#root`) | `document.querySelector('[ng-version]')`, `#root` | _boş_ |
| B2 | Liste adres parametreleri (sayfa, filtre, sıralama) | Filtre değiştirip `location.search` / `location.hash` | _boş_ |
| B3 | Liste kapsayıcısı ve satır seçicisi | `table`/`[role=grid]`/`mat-table`; satır sayısı | _boş_ |
| B4 | Kolon başlıkları (metin) | `th`, `[role=columnheader]` metinleri | _boş_ |
| B5 | Satırdan detaya geçiş (link `href` kalıbı mı, tıklama mı, yeni sekme mi) | satırdaki `a[href]` kalıbı, ör. `/technical-tasks/<id>` | _boş_ |
| B6 | Sayfalama ve filtre kontrolleri (etiket + seçici) | `paginator`, `select`, `input[type=search]` | _boş_ |
| B7 | Detay: Task No, Durum, Ekip, Randevu alanlarının **etiketleri** ve seçicileri | etiket metni → yanındaki alan | _boş_ |
| B8 | Detay: müşteri telefonu alanının **etiketi** (değer değil) | etiket metni | _boş_ |
| B9 | Ekip atama ve randevu kontrolleri: düğme/alan adı, `formcontrolname`/`name`/`id` | **Basılmaz**, yalnız okunur | _boş_ |
| B10 | Sayfanın kendi XHR/fetch çağrıları: adres kalıbı + JSON **alan adları** | Ağ istekleri; gövde değeri yazılmaz | _boş_ |

Eklenti davranışı için karar (G1): **ilk sürüm BOSS'a yazmaz.** Bizde yapılan atamayı BOSS formuna
**doldurur**, "Kaydet"e kişi basar. Bu yüzden B9'da yalnız alan seçicisi yeter, düğmeye dokunulmaz.

---

## 2. OWA (Outlook web)

**Durum: giriş gerekli.** `https://mail.turkcell.com.tr/owa/` → `https://mail.turkcell.com.tr/my.policy`
(F5 BIG-IP APM giriş sayfası). Posta kutusu şirket içi Exchange; Microsoft Graph kullanılamaz
(`operasyon/analiz/entegrasyon.md` §2.7).

`outlook.office.com` **denenmedi**: bağlı tarayıcı kullanıcının iş bilgisayarı değildi, kişisel bir posta
kutusu açılma riski vardı.

**Bilinen mail kalıpları** (repo belgelerinden; gerçek mail okunmadı):

| Mail türü | Kalıp | Ayıklanacak alan |
|---|---|---|
| Kırmızı hat (bayiye / bayiden) | Konu: `Task No / Task Adı / Kırmızı Hat` | Task No (Fox Akış No), Task Adı |
| BÇO 24 saat eskalasyonu | Gövdede `OneDesk ID + müşteri no` | OneDesk ID |
| Global Bilgi alarm akışı | Otomatik mail (SL'nin 8./10. iş günü; reopen'da 3./5.) | Akış No |
| **OneDesk bildirim maili** | **Bilinmiyor.** Gönderen adresi, konu kalıbı, ticket no ve durumun yeri keşif turunda **tek bir maskeli örnekle** belirlenecek | ticket no, durum (AÇIK / ÇÖZÜLDÜ / HATA / KAPATILDI / İPTAL) |

**Eklenti için öneri (seçiciye bağımlı olmayan yol):** OWA'nın DOM'u sürümden sürüme değişiyor. İlk sürümde
eklenti OWA'da **sağ tık menüsü** kullanır: "Seçili metni talep olarak kaydet". Kullanıcı mail gövdesinde
ilgili kısmı seçer; eklenti metinden Task No / BN / Lokasyon / OneDesk no'yu **kodla ayıklar**
(sunucudaki mevcut "Mailden talep" ayıklayıcısıyla aynı kurallar), gövdenin tamamını saklamaz.
Seçiciyle okuma (liste satırı, okuma bölmesi) keşif turundan sonra eklenir.

---

## 3. WhatsApp Web — "Talep olarak kaydet" düğmesi

**Durum: canlı haritalandı** (30.09.2026, arayüz dili Türkçe). Mesaj metni, kişi adı, numara **okunmadı**;
yalnız etiket türü, `data-testid`, `role` ve sayılar alındı. Bir sohbet açıldı (okunmamış mesajı olmayan,
okundu bilgisi gitmeyen); metin okunmadı.

### 3.1 Sayfa iskeleti

| Parça | Seçici | Not |
|---|---|---|
| Uygulama kökü | `#app` | |
| Sohbet listesi | `#pane-side` | Sanal liste: yalnız görünen satırlar DOM'da (6 satır görüldü) |
| Sohbet satırı | `#pane-side [role="row"][data-testid^="list-item-"]` | `list-item-0`, `list-item-1`… |
| Satırdaki sohbet adı | `[data-testid="cell-frame-title"] span[title]` | ad `title` niteliğinde |
| Satırdaki son mesaj | `[data-testid="cell-frame-secondary"] [data-testid="last-msg-status"]` | |
| Satır zamanı | `[data-testid="cell-frame-primary-detail"] span` | |
| Açık sohbet paneli | `#main` | sohbet açılınca oluşur |

### 3.2 Açık sohbetin başlığı

| Parça | Seçici |
|---|---|
| Başlık | `#main header[data-testid="conversation-header"]` |
| Başlık bilgi alanı (tıklanabilir) | `[data-testid="conversation-info-header"]` |
| **Sohbet adı** | `[data-testid="conversation-info-header-chat-title"]` (metin) |
| Başlık düğmeleri (`aria-label`) | `Görüntülü arama`, `Sesli arama`, `Ara`, `Menü` |

"Talep olarak kaydet" için başlık düğmelerinin yanına eklenecek yer: `#main header` içindeki son düğme grubu
(`button[aria-label="Menü"]` öncesi). Seçici olarak `aria-label` kullanmak dile bağlıdır; birincil olarak
**konum** (header içindeki son `button`) ya da `data-tab` kullanılmalı, `aria-label` yalnız yedek.

### 3.3 Mesaj satırı (baloncuk)

`#main` altında `[data-testid="conversation-panel-body"]` → `[data-testid="conversation-panel-messages"]`.
Görülen sohbette 14 mesaj satırı vardı; 12'si metin mesajı (`data-pre-plain-text` taşıyan), 2'si medya/bağlantı.

| Parça | Seçici | Not |
|---|---|---|
| Mesaj satırı | `[data-testid="conversation-panel-messages"] [role="row"]` | 14/14 satırda `data-id` var |
| Mesaj kimliği | satır içindeki `[data-id]` | Kalıp: `true_<sohbet-jid>_<mesaj-id>` (giden) / `false_<sohbet-jid>_<mesaj-id>` (gelen). jid sonu `@c.us` (kişi), `@g.us` (grup), `@lid`. **Kalıp genel WhatsApp Web bilgisidir; bu turda değer okunmadı** |
| Mesaj kapsayıcısı | `[data-testid^="conv-msg-"]` | `conv-msg-<mesaj-id>` |
| Baloncuk | `[data-testid="msg-container"]` | düğme buraya (üzerine gelince) eklenir |
| Yön | `[data-testid="tail-in"]` (gelen) / `[data-testid="tail-out"]` (giden) | Yalnız grubun **ilk** mesajında kuyruk var; yön için esas kaynak `data-id` öneki. Eski `.message-in` / `.message-out` sınıfları **artık yok** (0 eşleşme) |
| **Mesaj metni** | `.copyable-text` → `span.selectable-text` (`[data-testid="selectable-text"]`) | 12 metin mesajında 12 eşleşme |
| **Zaman + gönderen** | `.copyable-text[data-pre-plain-text]` | Değer biçimi `[SS:DD, G.AA.YYYY] Gönderen: ` (genel bilgi; bu turda değer okunmadı). Tarihi **tek** güvenilir kaynak bu nitelik |
| Saat (görünen) | `[data-testid="msg-meta"]` | Medya mesajında `data-pre-plain-text` yok → saat buradan, tarih gün ayracından |
| Medya | `[data-testid="image-thumb"]`, `[data-testid="media-state-download"]` | |
| Bağlantı önizleme | `[data-testid="link-preview-container"]`, `link-preview-title`, `link-description`, `url-element` | |
| Tepki | `[data-testid="reaction-bubble"]` | |
| Yazma kutusu | `footer [data-testid="compose-box"]`, `[data-testid="conversation-compose-box-input"]` | **Eklenti buraya asla yazmaz** |

### 3.4 Eklenti için uygulama notu

- `[data-testid="conversation-panel-messages"]` üzerine bir `MutationObserver`; yeni `[role="row"]` gelince
  `msg-container`'a gizli bir "Talep olarak kaydet" düğmesi eklenir (üzerine gelince görünür).
- Basınca gönderilen alanlar: sohbet adı (başlık), mesaj metni (`selectable-text`), zaman (`data-pre-plain-text`
  içinden), mesaj kimliği (`data-id`, çift kaydı önlemek için). Kullanıcı kaydetmeden önce özet kartı görür
  ve metni kısaltabilir. Sunucu metinden BN / Lokasyon / Task No / "sinyal yok" / "ek kapasite" ayıklar.
- Sınıf adları karışık (`x1abc…`) ve her sürümde değişir: **sınıfa bağlanılmaz**, yalnız `data-testid`,
  `role`, `data-id`, `data-pre-plain-text`, `#main`, `#pane-side`.

---

## 4. Atmosfer — personel listesi (personel rehberi için)

**Durum: giriş gerekli** (`https://atmosfer.turkcell.com.tr/dealer-manager/employee?dealerCode=…&isECM=true`
→ `/auth/login`; giriş alanları `#formBasicEmail` "Kullanıcı Adı", `#formBasicPassword` "Şifre"). Şifre girilmedi.

Ancak Atmosfer bir **React tek sayfa uygulaması** (`div#root`, `/runtime.js`, `/vendor.js`, `/main.js`) ve
paket kodu giriş sayfasında da yükleniyor. Personel sayfasının bileşeni
(`app/pages/dealer-manager/dealer-manager-employees/dealer-manager-employees.tsx`) ve kart bileşeni
(`PersonCard`) okundu. Aşağıdaki seçiciler **koddan kesin**; canlı sayfada bir kez doğrulanmalı.

### 4.1 Adres parametreleri

| Parametre | Anlam |
|---|---|
| `dealerCode` | Bayi kodu (Dehanet: `44003.00001`). Varsa bayi personeli listelenir |
| `vendorId` | `dealerCode` yoksa firma personeli listelenir |
| `isECM` | `true` = EÇM görünümü |

### 4.2 DOM yapısı

```
div.management-card
  Card.padding-20
    PageTitle
    div.dealer-employees
      div.dealer-employees__authorized            başlık: "Bayi Yetkilisi"
        div.dealer-employees__list
          div.person-card.readonly.person-card--clickable   (positionTypeName içinde "BAYİ SAHİBİ" geçenler)
      div.dealer-employees__team                  başlık: "Bayi Ekibi"
        div.dealer-employees__list
          div.person-card.readonly.person-card--clickable   (geri kalan herkes)
```

Kart içi (`PersonCard`, Atlas bileşen kütüphanesi, sınıflar karmasız):

| Parça | Seçici | Veri alanı |
|---|---|---|
| Kart | `.person-card` | |
| Rozet (varsa) | `.person-card__badge` | |
| Fotoğraf | `.person-card__avatar` (arka plan resmi) | |
| **Ad Soyad** | `.person-card__content > .person-card__text1` | `fullName` |
| **Unvan** | `.person-card__content > .person-card__text2` | `positionTypeName` |
| Ek satır | `.person-card__text3` (bu sayfada kullanılmıyor) | |

Kişi kimliği (`ldapName`) DOM'da **yok**; karta tıklanınca `UserModal` açılır. Personel rehberi için ad + unvan
yeterli; bayi yetkilisi / ekip ayrımı kapsayıcıdan (`__authorized` / `__team`) gelir.

Eklenti seçicisi: `.dealer-employees__authorized .person-card, .dealer-employees__team .person-card`.
Liste veri gelince çizildiği için eklenti `.dealer-employees__list` altında kart görünene kadar bekler
(`MutationObserver`, en çok 10 sn).

### 4.3 Sayfanın kendi API çağrıları (yalnız bilgi)

Taban adres canlıda `/pusula-api/` (kodda `BASE_URL = '/pusula-api/'`). Kimlik doğrulama:
`Authorization: Bearer <localStorage.token>`.

| Amaç | Çağrı | Bilinen alan adları |
|---|---|---|
| Bayi personeli | `GET /pusula-api/bys/employees/filter-dealer-employees/v2?dealerCode=<kod>` | dizi; `fullName`, `positionTypeName`, `ldapName` |
| Firma personeli | `GET /pusula-api/bys/employees/filter-firm-employees?vendorId=<id>` | aynı |
| Kişi özeti (modal) | `GET /pusula-api/bys/users/<ldapName>/basicInfo` | — |
| Kişi detayı | `GET /pusula-api/bys/employees/employee-detail-info?ldapName=<ldap>` | — |
| EÇM unvan listesi | `GET /pusula-api/bys/target-audience/employee-titles/ecm` | — |

**Öneri:** eklenti **DOM'dan** okur, jetonu (`token`) okumaz ve API'yi kendisi çağırmaz. API tablosu yalnız
DOM değişirse hangi alanın neyi taşıdığını bilmek için.

Not: Atmosfer kodunda OneDesk için `https://onedeskwsdynamic.turkcell.com.tr/api/dynamic` adresi geçiyor
(OneDesk ticket durumu için ileride bakılacak bir iz; bu turda incelenmedi).

---

## 5. ONENT ve FOX

| Sistem | Adres | Durum | Bilinen |
|---|---|---|---|
| ONENT ek kapasite | `https://onent.turkcell.com.tr/Pys#AdditionalCapacityFlowNew` | **Giriş gerekli**: `/my.policy` (F5 APM; alanlar `username`, `password`, `Domain` seçimi TURKCELL/KKTCELL) | `#` ile yönlenen tek sayfa uygulaması (`operasyon/analiz/entegrasyon.md` §2.4). Talep listesi/detay seçicileri keşif turunda |
| FOX | `foxsaha.global-bilgi.entp` (belgelerde `foxapp.global-bilgi.entp` de geçiyor) | **Erişilemedi**: `DNS_PROBE_FINISHED_NXDOMAIN` (http ve https) | Yalnız Global Bilgi / Turkcell iç ağında çözülen ad. ASP.NET postback'li rapor ekranı olabilir |

---

## 6. Eklenti için "Yapı keşfi" (BOSS / FOX / ONENT / OWA boşluklarını doldurmak için)

Eklentinin ilk sürümüne, yalnız yöneticiye görünen bir **"Bu ekranın yapısını gönder"** düğmesi konur.
Kullanıcı Windows Brave'de, oturumu açıkken bir kez basar. Eklenti **hiçbir değeri** göndermez:

- `location.origin + location.pathname`, `location.hash`'in rota kısmı; parametre **adları** (değerler `<..>`).
- Çatı işareti: `[ng-version]` değeri, `#root`, `#app`.
- Her `table` / `[role=grid]` için: kapsayıcı seçici, `th` / `[role=columnheader]` **metinleri**, satır sayısı.
  Hücre metni gönderilmez.
- Form alanları: `label` metni, `name`, `id`, `formcontrolname`, `type`, `placeholder`. **`value` gönderilmez.**
- Düğmeler: metin ve `aria-label` (arayüz dili), `type`, `id`. Düğmeye basılmaz.
- İlk 20 `a[href]` için yol kalıbı: rakam dizileri `#` ile değiştirilmiş (`/technical-tasks/#`).
- Ağ: sayfanın son 50 `fetch`/`XHR` çağrısının yöntemi ve yol kalıbı (rakamlar `#`), JSON cevabın **üst
  düzey alan adları** (değer yok). Bunun için eklenti yalnız keşif anında `PerformanceObserver`
  (`resource`) kullanır; gövde okumaz.

Sunucu bu dökümü `docs/eklenti/` altına yazılacak BOSS/FOX tablolarının (§1 B1–B10) girdisi olarak saklar.
Kişisel veri içermediği için ayrı izin gerekmez; yine de döküm kullanıcıya gönderilmeden önce gösterilir.

---

## 7. Eklenti izinleri (manifest `host_permissions` taslağı)

```
https://boss.turkcell.com.tr/*
https://boss.superonline.net/*
https://atmosfer.turkcell.com.tr/*
https://web.whatsapp.com/*
https://mail.turkcell.com.tr/owa/*
https://onent.turkcell.com.tr/*
https://foxsaha.global-bilgi.entp/*
http://foxsaha.global-bilgi.entp/*
```

Sunucu (Saha Sistemi) adresi ayrıca eklenir (ör. `http://10.54.3.75:8080/*`, ya da seçilen HTTPS adresi).
