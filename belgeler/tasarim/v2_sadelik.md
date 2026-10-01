# İş emri akışı v2: sadelik tasarımı

*Dehanet EÇM · Saha Sistemi · 30.09.2026 · Açı: **SADELİK** (Apple gibi; işe ilk gün başlayan biri eğitimsiz başarır)*

*Kapsam: `docs/GEREKSINIMLER.md` §F (F1–F22), ayrıca C, D, E'deki ilgili satırlar. Tasarım `docs/OPERASYON_TASARIM.md`'deki
KARMA-2 ile uyumludur; bilinçli sapmalar §12'de gerekçesiyle yazıyor. Bu belgede kişisel veri yok: örneklerdeki kişi, müşteri ve
mahalle adları uydurmadır, sayılar yalnız topluca verilir.*

---

## 0. Tek bakışta

### 0.1 Beş ilke

1. **Her ekranda tek belirgin iş.** Her ekranda yalnız bir birincil (mavi, dolu) düğme olur. Diğer eylemler metin düğmesidir ya da "Diğer" altında durur.
2. **Sistem bildiğini sormaz.** Kişinin görevi ana ekranını seçer. Öbeğin teknisyeni hazır seçili gelir, sıradaki boş saat dilimi de hazırdır. Operasyonun yaptığı yalnız **onaylamaktır**.
3. **Ayrıntı istenince açılır.** Liste satırı yalnız karar için gerekeni gösterir (kalan süre, müşteri, yer, durum). Gerisi sağdan (bilgisayar) ya da alttan (telefon) açılan **çekmecededir**.
4. **İş merkezde, harita ikinci planda.** Ekranın ana nesnesi iş listesidir. Harita "Liste | Harita" düğmesiyle açılır.
5. **Veri kaybolmaz.** İşin anahtarı Task No'dur. Göçler yalnız ekler. Her göçten önce kendiliğinden yedek alınır. Kullanıcının `obekler.json` dosyasına hiç yazılmaz. Canlı hesaplar, PIN'ler ve ziyaretler birebir korunur.

### 0.2 On beş dakikalık yol (F17'nin ekrandaki karşılığı)

```
10:00  Operasyon raporu İşler ekranına bırakır (ya da "Rapor yükle")
10:00  Üst şerit: "12 yeni iş · 0 bakılacak" ─ tek satırlık fark: Yeni 12 · Kapanan 30 · Yeniden açılan 1
10:01  Sol listede "Görükle  31 · 4 yeni ●" → dokun
10:01  Liste başında tek cümle: "4 atanmamış iş → Ali K.'ya ata"  [Ata]   (öbeğin teknisyeni, dilimler hazır)
10:02  Tost: "4 iş Ali K.'ya atandı · Geri al"      → sayaç: "Atanmayı bekleyen 8 · en eski 2 dk"
10:03  Sıradaki öbek…     Günün göstergesi: "Atama süresi (medyan) 3 dk · hedef 15 dk"
```

Bir işin 15 dakikada çözülmesinin ekrandaki karşılığı şudur: **içe aktarımdan atamaya ≤ 15 dk**. Bu süre her iş için
ölçülür ve gösterilir. İşin kalanı KARMA-2'nin işidir: aramadan sevk, BTK'da masanın paralel teşhisi, evde yok merdiveni.
Arayüz bu süreyi kısaltır, süreci ise değiştirmez.

---

## 1. İzlenebilirlik: F1–F22 → bu belge → kabul testi

| # | İstek (kısa) | Karşılandığı yer | Kabul testi (§10) |
|---|---|---|---|
| F1 | Öbek düzenle: mahalleleri gör, çıkar, ekle | §4.4 Öbek çekmecesi · §5.4 `obek`, `obek_mahalle` · §6.3 öbek uçları | T1.1–T1.3 |
| F2 | Raporda olmayan mahalle (Göçmen, Gürsu) ve ilçenin tamamı | §4.4 Mahalle seçici · §5.4 `mahalle_sozluk` · §5.5 tohumlama | T2.1–T2.4 |
| F3 | Öbeğe tıkla → aboneler (işler) | §4.2 Öbeğin işleri · §6.3 `GET /api/is-emri/isler` | T3.1–T3.2 |
| F4 | Mahalle önce Location Id'den; kontrol yalnız gerçek sorun | §7 adım 3 (bina eşleşmesi DB'den, 332/332) · §4.5 | T4.1–T4.2 |
| F5 | Hatalı adres (İzmir) görünsün, elle öbeğe eklensin | §4.5 Bakılacaklar · `is_emri.obek_elle_id` | T5.1–T5.2 |
| F6 | Operasyon / Teknik / Saha ayrımı | §2 Roller · §6.2 yetki tablosu · §4.0 yönlendirme | T6.1–T6.3 |
| F7 | Tekniğe ata; teknik gideceği işi bilsin | §4.3 Planla · §4.7 Toplu ata · §4.10 İşlerim | T7.1–T7.2 |
| F8 | Randevu | §4.3 Gün + dilim · §3.2 geçişler | T8.1–T8.2 |
| F9 | Ticket işaretle, takip et | §4.3 Ticket bölümü · `is_emri.ticket_id` · §3.2 (ticket çözülünce iş geri döner) | T9.1–T9.2 |
| F10 | Rapor → operasyon randevular → atar → teknik yapar | §3 durum makinesi | T10.1–T10.2 |
| F11 | Düzgün arayüz; yönetici paneli takip için | §4.12 Pano · §9 tasarım sistemi · §4.16 düzeltmeler | T11.1–T11.3 |
| F12 | Görevler Satış · Operasyon · Teknik · Yönetici | §2.1 · §4.11 · §5.3 rol göçü | T12.1–T12.2 |
| F13 | Kişi sil; işi varsa uyar, Pasife al öner | §4.11 · §6.3 `DELETE /api/kullanici/{id}` | T13.1–T13.4 |
| F14 | Apple gibi; ilk gün başlayan hızla uyum sağlar | §0.1 · §4.14 boş durumlar · §4.15 sözlük · §9 | T14.1–T14.3 |
| F15 | Satış yönetimi | §4.12 Pano "Satış" kartı · §4.13 | T15.1 |
| F16 | İş emri kaynağı: global ya da bayi | §4.9 Yeni iş · `is_emri.kaynak`, `kanal` | T16.1–T16.2 |
| F17 | 24 s tavan; "15 dakikada nasıl" | §0.2 · §3.4 saatler · §4.1 üst şerit · §4.7 | T17.1–T17.2 |
| F18 | Pipeline sağlam | §7 içe aktarım hattı · §8 eşzamanlılık | T18.1–T18.6 |
| F19 | Bilgisayarda ve telefonda mükemmel | §9.5 masaüstü / telefon kuralları · her ekranın iki çizimi | T19.1 |
| F20 | Güncellemede veri zarar görmesin | §5.2 göç çerçevesi · §5.3 rol göçü · §5.6 doğrulama | T20.1–T20.4 |
| F21 | Operasyon müşteri bilgisine erişsin | §2.3 kişisel veri kuralları · `musteri_erisim` | T21.1–T21.3 |
| F22 | Parçala, üret, test et, düzelt, tekrarla | §11 yapım planı · §10 test paketi · defter güncellemesi | T22.1 |

---

## 2. Roller

### 2.1 Dört görev

Veritabanındaki `satisci` ve `yonetici` değerleri **yeniden adlandırılmaz**, çünkü SQL içinde sabit yazılılar (rapor.py,
bolgeleme.py, demo.py, kur.py). Yalnız `operasyon` ve `teknik` **eklenir**. "Satış" yalnız ekrandaki etikettir.

| Ekranda | DB `rol` | Kim | Masaüstünde ilk ekran | Telefonda ilk ekran | Tek birincil eylem |
|---|---|---|---|---|---|
| **Satış** | `satisci` | Saha satışçısı | Bugün (bugünkü satış uygulaması, değişmez) | Bugün | "Sonucu işle" |
| **Operasyon** | `operasyon` | Masa, atama, randevu | **İşler** (sevk panosu, §4.1) | İşler (öbek listesi) | "Ata" |
| **Teknik** | `teknik` | Arıza teknisyeni | İşlerim (ortada 640 px liste) | **İşlerim** (§4.10) | "Yola çıktım" → "Başladım" → "Bitti" |
| **Yönetici** | `yonetici` | Bayi yönetimi, operasyon lideri | **Pano** (§4.12); son açtığı bölümü hatırlar | Pano | yok (takip ekranı) |

Görev adı olarak `teknik` seçildi, çünkü F12'nin kelimesi bu. OPERASYON_TASARIM §5.1'deki `teknisyen` ve `teknik_lider`
ise v2'de `teknik` olur. "Lider" ve masa etiketleri (triyaj, BTK, akşam bandı) sonraki fazda eklenir; bunun için
`kullanici` tablosuna dokunulmaz, ayrı bir `etiket` tablosu kurulur (§12).

### 2.2 Yetki tablosu

"Evet" yazmayan her şey **yasaktır**. Varsayılan ret: bilinmeyen rol hiçbir yere giremez (§6.4).

| Eylem | Satış | Operasyon | Teknik | Yönetici |
|---|---|---|---|---|
| Satış ekranları (Bugün, bina listesi, harita, ziyaret yazma) | Kendi bölgesi | — | — | Evet |
| Bina kartını görme | Kendi bölgesi | Evet (salt okuma) | Yalnız kendi işlerinin binası | Evet |
| İş listesi, öbekler, rapor yükleme, Excel | — | Evet | — | Evet |
| Müşteri adı ve no (tam) | — | Evet (kayıt tutulur) | Kendi işi: kısa ad + müşteri no | Evet (kayıt tutulur) |
| Tam adres | — | Evet | Kendi işi | Evet |
| Ata, randevu, öbek değiştir, askı, telefonda çözüldü | — | Evet | — | Evet |
| Yola çıktım, Başladım, Bitti, Evde yok | — | Evet (düzeltme için) | Kendi işi | Evet |
| Öbek düzenle (mahalle ekle/çıkar, yeni mahalle) | — | Evet | — | Evet |
| Ticket defteri | Bina kartından talep aç (bugünkü gibi) | Evet | Kendi işine "Ticket var" işareti | Evet |
| Ekip (kişi ekle, görev, sil, PIN sıfırla) | — | Teknik listesini görür (atama için) | — | Evet |
| Pano | — | Evet (salt okuma) | — | Evet |
| Bölge planlayıcı, tur raporu, veri kalitesi | — | — | — | Evet |

### 2.3 Müşteri bilgisi (F21) ve KVKK

F21, OPERASYON_TASARIM §6.5 ("ad maskelenir") ile çelişiyor. v2, kullanıcının son ve açık isteğini (F21) uygular. Karşılığında dört güvence koyar:

1. **Rolle sınırlı.** Tam ad ve müşteri no yalnız operasyon ve yöneticiye gider. Teknik yalnız **kendi işinde** kısa adı ("Ayşe K.") ve müşteri no'yu görür; bunlar kapıdaki zil ve BOSS Mobil'de arama için yeterlidir. Satışçı iş listesine hiç giremez.
2. **Kayıtlı.** İş çekmecesinin her açılışı (kişi ve iş başına günde 1 satır), müşteri no'nun her kopyalanışı ve her Excel indirilişi `musteri_erisim` tablosuna yazılır. Yönetici bu kaydı Pano → "Erişim kaydı"nda görür.
3. **Süreli.** Kapanıştan 30 gün sonra `musteri_adi` ve `adres` NULL yapılır; `musteri_no` tek yönlü özete çevrilir (tekrar arıza tespiti için). Temizlik açılışta ve 19:30 yedek görevinde çalışır.
4. **Telefon yok.** Müşteri telefonu sisteme girmez (BOSS dışa aktarımında da yok). Arama BOSS/Maya'dan yapılır; bunun için ekranda "Müşteri No'yu kopyala" düğmesi var.

API yanıtı role göre **sunucuda** kırpılır. İstemcide gizlemek yeterli sayılmaz. Olay geçmişine (`is_olay`) kişisel veri yazılmaz: adres değiştiyse yalnız "adres değişti" yazar.

### 2.4 Bugünkü kişiler yeni görevine nasıl geçer

- Göç **hiçbir kişinin rolünü değiştirmez**. 10 hesap, PIN'leri, telefonları ve oturumları aynen kalır (§5.3).
- İlk açılışta Ekip ekranının başında tek bir kart çıkar: **"Görevleri gözden geçirin. 8 kişi 'Yönetici' görünüyor. Gerçek görevlerini seçin."** Her satırda dört parçalı bir seçici (Satış · Operasyon · Teknik · Yönetici) ve altta tek bir "Kaydet" düğmesi var.
- Görevi değişen kişinin telefonu bir kez oturumdan düşer (`oturum_no` artar) ve yalnız PIN ister. PIN değişmez. Hata mesajı yeni: "Göreviniz değişti. PIN'inizle yeniden girin." (kod `gorev_degisti`).
- Korumalar: kişi kendi görevini düşüremez. Son aktif yönetici düşürülemez, pasife alınamaz, silinemez (kod `son_yonetici`).
- Satış seçilince bölge zorunlu olur. Teknik seçilince "Öbekleri" (çoklu) ve "BOSS'taki ekip adı" alanları açılır. Bu ad, içe aktarımda BOSS "Ekip" sütunuyla eşleşip işi kendiliğinden bu kişiye bağlar.

### 2.5 Giriş (C9 ve bilgisayar klavyesi)

- Tek birimli kişiye birim sorulmaz; rolü onu doğru ekrana götürür (ilke 2).
- Birden çok birime girebilen kişiye (yönetici) **o cihazdaki ilk girişte bir kez** sorulur: "Bu cihazda nereden başlayalım? **Operasyon · Teknik · Satış · Yönetim**". Seçim cihazda hatırlanır ve kenar çubuğunun altından değiştirilebilir. C9'daki "üç kutu" böylece yalnız işe yaradığı yerde sorulur.
- Masaüstünde fiziksel klavye çalışır: rakamlar, Backspace ve Enter. Giriş sütunu 360 px'i geçmez ve "Devam" düğmesi de bu genişlikte kalır. Ofis bilgisayarı için "Bu bilgisayarda beni hatırla" seçeneği var: 30 günlük jeton, bugünkü davranış.

---

## 3. İş emrinin hayatı: durum makinesi

### 3.1 Durumlar

`durum` sütununda **CHECK yok** (bugünkü dar CHECK'lerin genişletilmesi pahalıya patladı). Değerler Python'da
`operasyon/durum.py:DURUMLAR` sabitiyle doğrulanır.

| Kod | Ekranda | Anlamı | Sahibi | OPERASYON_TASARIM karşılığı |
|---|---|---|---|---|
| `yeni` | Yeni | Rapordan geldi; öbeği, binası ve saati belli | Operasyon | S0 + S1 |
| `bakilacak` | Bakılacak | Öbeğe konamadı (il bölge dışı, mahalle yok, öbeksiz mahalle) | Operasyon | S1 (triyaj) |
| `randevulu` | Randevulu | Saat dilimi var, teknisyen henüz yok (müşteri "yarın 10-12" dedi) | Operasyon | S2 öncesi |
| `atandi` | Atandı | Teknisyen ve dilim belli; teknisyenin "İşlerim"inde | Teknik | S2 |
| `yolda` | Yolda | Teknisyen yola çıktı | Teknik | S3 |
| `sahada` | Sahada | İş başladı | Teknik | S4 |
| `cozuldu` | Çözüldü | Sahada bitti ya da telefonda çözüldü; BOSS'tan düşmesi bekleniyor | — | S5 |
| `evde_yok` | Evde yok | Kapıda ulaşılamadı; masa merdiveni işliyor | Operasyon | E1 |
| `askida` | Askıda | Neden ve uyanma zamanı zorunlu (abone talebi, malzeme, diğer) | Operasyon | E2, E4 |
| `altyapi` | Altyapı bekliyor | İş bir ticket'a bağlı; teknisyen gönderilmez | Operasyon | E3 |
| `merkezde` | Merkeze gönderildi | BOSS'ta "Merkeze gönderildi" ya da operasyonun kararı | Operasyon | E3 / E5 |
| `kapandi` | Kapandı | Tam raporda artık yok, yani BOSS'ta kapanmış | — | S6 |

**Bayraklar** durumdan bağımsızdır ve satırda rozet olarak görünür:

| Bayrak | Anlamı |
|---|---|
| `btk` | Şerit BTK (Bağlantı, TV+, Arama, Doping). Kalan süre BTK hedefiyle hesaplanır |
| `binada_ticket` | Binada açık SİNYAL/EK SP/GÜZERGAH/ALTYAPI ticket'ı var. Ata düğmesi yerine "Ticket'a bağla" gelir (KARMA-2 kural 11) |
| `tekrar` | Aynı müşteri no + aynı task adı 7 gün içinde yeniden geldi (E6). Telefonda kapatma yasak |
| `konum_yaklasik` | Konum bina değil, mahalle ya da ilçe merkezi. Alarm değil; sessiz bilgi |
| `aranacak` | Masanın araması gerekiyor: BTK teşhisi ≤45 dk, evde yok denemesi, uyanan askı, Kanal |
| `kaynak` | `boss` (rapordan) ya da `bayi` (elle açıldı); `kanal`: `global` ya da `bayi` (F16) |

### 3.2 Geçişler: kim, hangi düğmeyle

```
             içe aktarım                 Ata (teknisyen + dilim)            Yola çıktım       Başladım        Bitti
 (yok) ──────────────► yeni ─────────────────────────────────────► atandi ──────────► yolda ────────► sahada ──────► cozuldu
                        │  ▲                       ▲       │                             │               │              │
          öbeğe konamadı│  │Öbeğe ekle             │       │Yeniden ata                  └── Evde yok ───┴─► evde_yok    │ tam raporda yok
                        ▼  │                       │                                                         │          ▼
                    bakilacak        Randevu ver ─► randevulu ──Ata──┘            masa: ulaşıldı → dilim ─────┘       kapandi
                                                                                                                         │ raporda yeniden var
   herhangi açık durum ── Ticket'a bağla ──► altyapi ── ticket ÇÖZÜLDÜ ──► yeni (24 s saati yeniden: teyitli ziyaret)   ▼
   herhangi açık durum ── Askıya al ───────► askida  ── uyanma geldi ────► yeni                                   yeni (+tekrar)
   herhangi açık durum ── Telefonda çözüldü ─► cozuldu      herhangi açık ── Merkeze gönderildi ──► merkezde
```

| Kimden | Kime | Tetik (düğme) | Kim | Zorunlu alan / kural |
|---|---|---|---|---|
| — | `yeni` / `bakilacak` | İçe aktarım, "Yeni iş" | Sistem, operasyon | Öbek bulunamazsa `bakilacak` |
| `bakilacak` | `yeni` | "Öbeğe ekle" | Operasyon | `obek_elle_id` |
| `yeni` | `randevulu` | "Randevu ver" (teknisyensiz) | Operasyon | gün + dilim |
| `yeni`, `randevulu`, `askida`, `merkezde` | `atandi` | "Ata" | Operasyon | teknisyen; dilim boşsa sıradaki boş dilim kendiliğinden |
| `evde_yok` | `atandi` | "Ata" | Operasyon | **"Müşteriye ulaşıldı, saat teyitli" işareti zorunlu.** KARMA-2 kural 8: aynı işe ikinci kez habersiz gidilmez |
| `atandi` | `atandi` | "Başkasına ata", dilim değiştir | Operasyon | — |
| `atandi` | `yolda` | "Yola çıktım" | Teknik (ya da BOSS "Konum Paylaşıldı") | — |
| `yolda` | `sahada` | "Başladım" | Teknik (ya da BOSS "Başlandı") | — |
| `yolda`, `sahada` | `cozuldu` | "Bitti" | Teknik | isteğe bağlı not |
| `yolda`, `sahada` | `evde_yok` | "Evde yok" | Teknik | "10 dk bekledim, 2 kez aradım" işareti. Masa merdiveni başlar: `uyanma` = şimdi |
| herhangi açık | `cozuldu` | "Telefonda çözüldü" | Operasyon | neden: canlı test yapıldı · şebeke kaynaklı · iptal · mükerrer. `tekrar` bayraklı işte "canlı test" dışı seçilemez (KARMA-2 kural 13) |
| herhangi açık | `askida` | "Askıya al" (teknikte "Malzeme") | Operasyon, teknik | neden + uyanma. Üst sınır: BTK 1 gün, diğerleri 3 gün, müşteri talepli 7 gün |
| herhangi açık | `altyapi` | "Ticket'a bağla" | Operasyon | `ticket_id` |
| herhangi açık | `merkezde` | "Merkeze gönderildi" | Operasyon, BOSS | neden |
| `altyapi` | `yeni` | Bağlı ticket ÇÖZÜLDÜ, KAPATILDI ya da İPTAL oldu | Sistem | Olay: "Ticket çözüldü, teyitli ziyarete döndü" |
| `askida`, `evde_yok` | `yeni` / `aranacak` bayrağı | `uyanma` geldi | Sistem | Her okumada ve içe aktarımda değerlendirilir |
| açık, BOSS işi | `kapandi` | **Tam** raporda yok | Sistem | `kapanis_nedeni`: `dogrulandi` (bizde çözüldüyse) · `bossta_kapandi` |
| `kapandi` | `yeni` | Raporda yeniden var | Sistem | `tekrar=1`; eski teknisyen öneri olarak gelir |
| geçersiz her geçiş | — | — | — | 409 `gecersiz_gecis` + Türkçe açıklama |

**Geri al.** Her geçişin tostunda 10 sn "Geri al" düğmesi durur. Sunucu `{"geri_al": olay_id}` isteğini üç şartla kabul eder: olay işin son olayıdır, aynı kişiye aittir ve 60 sn'den eski değildir.

### 3.3 BOSS ile uzlaşma: kim kazanır

Faz 1'de teknisyenler BOSS Mobil'i kullanmaya devam eder. BOSS'un söylediği `boss_*` sütunlarına yazılır; bizim kararlarımızı yalnız **ileri** götürür:

| BOSS Task Durumu | Bizde |
|---|---|
| Açık, Ekip boş | Değişmez |
| Açık, Ekip dolu | `teknisyen_id` boşsa ve Ekip adı bir teknisyenin "BOSS'taki ekip adı" ile eşleşiyorsa → `atandi` (olay kaynağı `ice_aktarim`). Eşleşmezse satırda "BOSS'ta ekip: …" bilgisi durur |
| Konum Paylaşıldı | `atandi` ise → `yolda` |
| Başlandı | `atandi` ya da `yolda` ise → `sahada` |
| Askıya alındı | `cozuldu` ya da `altyapi` değilse → `askida` (neden = Askıya Alınma Nedeni; uyanma boş kalır, bakılacak listesine "uyanma saati girin" düşer) |
| Merkeze gönderildi | `cozuldu` değilse → `merkezde` |

Sıra: `yeni < randevulu < atandi < yolda < sahada`. BOSS hiçbir zaman geri götürmez. Bizde `cozuldu` olan iş iki içe aktarım
boyunca BOSS'ta açık kalırsa satırda **"BOSS'ta hâlâ açık: kapattınız mı?"** notu çıkar. Bu, OPERASYON_TASARIM §6.2'deki giden kutusunun sade hâlidir.
BOSS'taki randevu (`boss_randevu_*`) çekmecede salt okunur "BOSS'taki randevu" olarak gösterilir, ama bizim dilimimizin yerine geçmez;
varsayılan 11:00 damgalarına güvenilmez.

### 3.4 Saatler

| Saat | Formül | Nerede görünür |
|---|---|---|
| **24 s tavanı** (söz) | `son24 = acilis + 24 s` (`acilis` = BOSS Task Başlangıç) | Her satırda "Kalan 7 s" / "Gecikti 5 s" |
| **BTK hedefi** (sıra anahtarı) | TV+ Arıza 6 s · Bağlantı ve Arama Problemi 12 s · Doping 24 s | BTK rozetinin yanında "hedef 21:40" |
| **Renk** | `oran = (şimdi − acilis) / (hedef ya da son24 − acilis)` → <0,5 yeşil · 0,5–0,8 amber · ≥0,8 kırmızı · gecikmiş: kırmızı + saat simgesi | Renk hiçbir zaman tek başına bilgi taşımaz: yazı ve simge hep yanındadır |
| **Atama süresi** (15 dk hedefi) | `atama_zamani − ilk_gorulme`. BOSS'tan ekibi dolu gelen iş ölçüye girmez | Üst şerit: "Atanmayı bekleyen 12 · en eski 9 dk" · Pano: medyan, p90, 15 dk içinde atanan pay |
| **Müşteriye söz** (kesim kuralı) | 00–12 geldiyse aynı gün · 12–17 ertesi gün 12:00 · 17–24 ertesi gün 17:00 | Çekmecede tek satır: "Müşteriye söz: bugün 17:00'ye kadar" |
| **48 s BTK emniyet supabı** | `btk` ve şimdi − acilis > 48 s | Üst şerit sayacı, Pano, "Aranacaklar" |
| **Masa vadesi** | BTK işi: `ilk_gorulme + 45 dk` | Aranacaklar listesinde "vade 12 dk" |

Kalan süre istemcide dakikada bir, sunucu saatinden türetilerek yenilenir. Yanıttaki `sunucu_zamani` ile kayma düzeltilir.

### 3.5 Kapanma ve yeniden açılma (F18)

- **Tam rapor** yüklemesinde, açık bir BOSS işi dosyada yoksa `kaybolma = şimdi` ve `durum = kapandi` olur.
- Dosyadaki iş sayısı açık işlerin %70'inin altındaysa (ya da kaybolacak iş 20'den fazla ve %30'u aşıyorsa) sunucu kapatmaz ve sorar: **"Bu rapor eksik görünüyor (437 açık iş → dosyada 120). Kaybolan 317 iş kapatılsın mı?"** Seçenekler: "Hayır, yalnız ekle ve güncelle" (varsayılan, `tur=kismi`) · "Evet, tam rapor". Böylece süzülmüş bir dışa aktarım yanlışlıkla yüzlerce işi kapatamaz.
- Kapanmış iş raporda yeniden görünürse `yeni` olur, `tekrar=1` işaretlenir ve olay yazılır: "Yeniden açıldı".
- Yeni bir Task No, 7 gün içinde kapanmış bir işle aynı `(musteri_no, task_adi)` çiftine sahipse `tekrar=1` olur.

---

## 4. Ekranlar

### 4.0 Bilgi mimarisi

**Masaüstü kenar çubuğu** (220 px, role göre süzülür; grup başlıkları küçük harf değil, sade metin):

| Operasyon | Yönetici |
|---|---|
| İşler · Aranacaklar · Öbekler · Ticketlar | **Pano** · İşler · Aranacaklar · Öbekler · Ticketlar · Ekip · Satış ▸ (Canlı durum, Kapsama, Görev atama, Rapor) · Veri ▸ (Bölge planlayıcı, Tur raporu, Veri kalitesi) |

Kenar çubuğunun altında kişinin adı, görevi ve "Çıkış" durur; yönetici için "Satış uygulaması" da eklenir.

**Telefon alt sekmeleri** (en çok 4; 44 px başlık çubuğu; iç içe kaydırma yok):

| Görev | Sekmeler |
|---|---|
| Satış | Bugün · Harita · Ben (değişmez) |
| Operasyon | İşler · Aranacak · Öbekler · Daha (Ticketlar, Çıkış) |
| Teknik | İşlerim · Harita · Ben |
| Yönetici | Pano · İşler · Ekip · Daha (geri kalan her şey) |

**Adresler** (hash yönlendirici; eski yer imleri yönlendirilir):

```
#/yonetici/pano                       Pano (yönetici)
#/yonetici/isler[/<obek_id>]          İşler panosu; öbek seçili
#/yonetici/is/<task_no>               İş çekmecesi açık (arkada pano)
#/yonetici/aranacak                   Masa kuyruğu
#/yonetici/obekler[/<obek_id>]        Öbek listesi; öbek çekmecesi açık
#/yonetici/is-emirleri                → #/yonetici/isler (eski adres)
#/islerim[/<task_no>]                 Teknik
```

`App.tsx` içindeki yönetim kapısı `rol ∈ {yonetici, operasyon}` olur. Girişten sonra yönlendirme şöyle: satisci → `#/bugun` · teknik → `#/islerim` ·
operasyon → `#/yonetici/isler` · yonetici → cihazın hatırladığı bölüm, yoksa `#/yonetici/pano`.
**"GÖSTERİM VERİSİ" bandı yalnız demo ziyaret kullanan satış ekranlarında**, başlığın yanında küçük bir hap olarak görünür. İşler, Ticketlar ve Pano'da görünmez; oradaki veri gerçektir.

### 4.1 Operasyon · İşler (sevk panosu)

**Masaüstü, ≥1200 px: üç sütun, sayfa hiç yeniden akmaz.**

```
┌───────────────┬───────────────────────────────────────────────────────────────────────────────────────────┐
│ ▣ Dehanet EÇM │ İşler                                 Son rapor 12:12 · 437 iş ⓘ   [Rapor yükle]  [＋ Yeni iş] │
│               │ Atanmayı bekleyen 12 · en eski 9 dk │ 24 saati aşan 288 │ 48 saati aşan BTK 5 │ Kapasite 165/205 ▲ │
│ ● İşler       ├─────────────────────────┬─────────────────────────────────────────────────────────────────┤
│   Aranacaklar │ 🔍 Öbek ya da iş ara     │ Görükle                        31 açık · 9 geciken   [Liste│Harita] │
│   Öbekler     │ ⚠ Bakılacak          3 › │ ┌─────────────────────────────────────────────────────────────┐ │
│   Ticketlar   │ Görükle   31 · 4 yeni ● │ │ 4 atanmamış iş  →  Ali K.'ya ata (bugün 3, yarın 1)   [ Ata ]│ │
│               │ Dumlupınar      65      │ └─────────────────────────────────────────────────────────────┘ │
│               │ Özlüce          22 · 1 ●│ [Süz ▾]  Durum: Hepsi ×                                          │
│               │ …                        │ Kalan    Müşteri      Yer                Task          Durum     │
│               │ Öbeksiz               0 │ 2 s 10 ● A. Yılmaz    Görükle · 12. Sk   BTK Bağlantı  Yeni      │
│               │                          │ Gecikti  B. Kaya      Görükle · Site A   Modem Değ.    Atandı · Ali K. · 14–16 │
│ ───────────── │                          │ …                                                             ⚑ │
│ Ayşe Y.       │                          │                                                                  │
│ Operasyon     │                          │                                                                  │
└───────────────┴─────────────────────────┴─────────────────────────────────────────────────────────────────┘
```

- **Üst şerit: dört sakin sayı.** Her birine basınca liste o süzgeçle açılır. "ⓘ" içe aktarımın ayrıntısını gösterir: kaç satır geldi, kaçı çıkarıldı, mahalle ve konum kaynakları. Bu bilgi artık başlıkta geliştirici günlüğü gibi durmaz.
- **Sol sütun (280 px): öbekler.** Satır = ad · açık · yeni (mavi nokta) · teknisyenin baş harfi. Sıralama: önce yeni işi olan, sonra geciken sayısı. En üstte sabit "⚠ Bakılacak N" satırı durur; 0 ise "✓ Bakılacak iş yok" soluk yazılır. İşi olmayan öbek de listededir (soluk), yani düzenlenebilir.
- **Orta sütun: seçili öbeğin işleri.** Atanmamış iş varsa listenin başında **tek cümlelik toplu eylem** durur (§4.7). Liste varsayılan olarak kalan süreye göre sıralıdır, BTK önce gelir. Tabloda en çok 6 sütun olur. 1200 px'in altında "Yer" ile "Task" tek hücrede birleşir.
- **Süz** tek bir düğmedir. Açılan çekmecede Durum, Task, İlçe, Teknisyen ve "Yalnız: geciken · BTK · atanmamış · ticketlı" seçenekleri var. Etkin süzgeçler aramanın yanında kaldırılabilir çip olarak durur. 33 çiplik süzgeç duvarı kalkar.
- **Harita** "Liste | Harita" ile açılır; yalnız seçili öbeğin işlerini gösterir. Konumu yaklaşık olan iş halka ile çizilir.
- **Klavye:** ↑↓ satır seçer, Enter çekmeceyi açar, `A` "Ata", Esc kapatır, `/` aramaya odaklanır.
- **Sağ çekmece** (440 px) listenin üzerine kayar; sayfa yeniden akmaz.

**Telefon, <768 px: iç içe itme (push) gezinme.**

```
┌──────────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────────────────┐
│ İşler                    ＋  │   │ ‹ İşler      Görükle   Harita│   │ ‹ Görükle                  ⋯ │
│ 12 atanmayı bekliyor · 9 dk  │   │ 31 açık · 9 geciken          │   │ BTK  Bağlantı Problemi       │
│ 288 iş 24 saati aştı         │   │ ┌──────────────────────────┐ │   │ Kalan 2 s 10 dk  (hedef 21:40)│
│ ──────────────────────────── │   │ │4 atanmamış iş            │ │   │ Müşteriye söz: bugün 17:00   │
│ ⚠ Bakılacak               3 ›│   │ │Ali K.'ya ata   [  Ata  ] │ │   │ ── Müşteri ───────────────── │
│ Görükle      31 · 4 yeni ● › │   │ └──────────────────────────┘ │   │ A. Yılmaz                    │
│ Dumlupınar          65     › │   │ 2 s 10 · BTK Bağlantı        │   │ No 1234…  [Kopyala]          │
│ Özlüce         22 · 1 ●    › │   │ A. Yılmaz · Görükle 12. Sk › │   │ ── Adres ─────────────────── │
│ …                            │   │ Gecikti · Modem Değ.         │   │ …                            │
│                              │   │ B. Kaya · Atandı Ali K.    › │   │ ── Planla ────────────────── │
├──────────────────────────────┤   │ …                            │   │ Teknisyen  Ali K. (öbeğin) › │
│ İşler  Aranacak Öbekler  Daha│   ├──────────────────────────────┤   │ Bugün · Yarın · Seç          │
└──────────────────────────────┘   │ İşler  Aranacak Öbekler  Daha│   │ 10–12 · 12–14 · 14–16 · …    │
                                    └──────────────────────────────┘   ├──────────────────────────────┤
                                                                        │ [            Ata           ] │ ← başparmak bölgesi
                                                                        └──────────────────────────────┘
```

Telefonda tablo yoktur; her iş iki satırlık bir karttır. Harita başlıktaki düğmeyle açılır. Listeler tek bir kaydırma alanındadır.

### 4.2 Öbeğe tıkla → işleri (F3)

Öbek satırına basınca orta sütun (telefonda yeni sayfa) o öbeğin işlerini gösterir. Satırda şunlar var:

| Alan | Örnek | Not |
|---|---|---|
| Kalan süre | "2 s 10 dk" yeşil · "Gecikti 5 s" kırmızı + ⏱ | Varsayılan sıralama; BTK'da hedefe göre |
| Müşteri | "A. Yılmaz" + müşteri no | Operasyon ve yönetici tam adı görür (§2.3) |
| Yer | "Görükle · 12. Sokak" | Mahalle + adresin kısa hâli; konum yaklaşıksa ◌ |
| Task | "BTK · Bağlantı" | Rozet: BTK · Tekrar · Global/Bayi |
| Durum | "Atandı · Ali K. · 14–16" | Randevu ve teknisyen durum hücresinde; teyitliyse ✓ |
| Ticket | ⚑ | Bağlı ya da binada açık ticket |

Başlıkta "31 açık · 9 geciken · 14 BTK · teknisyen Ali K. · [Düzenle]" yazar. "Düzenle" öbek çekmecesini açar (§4.4).

### 4.3 İş çekmecesi (F7, F8, F9, F10, F21)

Masaüstünde sağdan 440 px, telefonda tam ekran açılır; başlıkta bir tutamak (grabber) vardır. Bölümler yukarıdan aşağıya
"karar için gereken sırayla" dizilir. Ayrıntı bölümleri (Geçmiş, BOSS bilgileri) kapalı başlar.

```
┌ BTK  Bağlantı Problemi                                   ✕ ┐
│ Kalan 7 s 20 dk · BTK hedefi 21:40 · Müşteriye söz: bugün   │
│ Task No 123456789  [Kopyala]      Global                     │
├ Müşteri ────────────────────────────────────────────────────┤
│ Ad Soyad (tam)                                               │
│ Müşteri No 12345678  [Kopyala]  [BOSS'ta aç]                 │
├ Adres ──────────────────────────────────────────────────────┤
│ (tam adres)                                                  │
│ Görükle · Nilüfer · Öbek: Görükle  [Değiştir]                │
│ ◉ Binası bulundu (Location Id)   [Haritada aç]  [Binayı aç]  │
├ Planla ─────────────────────────────────────────────────────┤
│ Teknisyen   Ali K. · öbeğin teknisyeni · bugün 9 iş      ›   │
│ Gün         (Bugün) (Yarın) (Seç…)                           │
│ Saat        (10–12) (12–14) (14–16) (16–18) (18–20)          │
│             ☐ Müşteriyle konuşuldu, saat teyitli             │
│ [                      Ata                              ]    │
├ Ticket ─────────────────────────────────────────────────────┤
│ Binada açık ticket yok.            [Ticket bağla / aç]       │
├ Diğer ──────────────────────────────────────────────────────┤
│ Evde yok · Askıya al · Telefonda çözüldü · Merkeze gönderildi │
├ Not ────────────────────────────────────────────────────────┤
│ [ Not ekleyin…                                    ] [Ekle]   │
├ Geçmiş ▸  (6)                                                │
│   10:02 Rapordan geldi                                       │
│   10:09 Ali K.'ya atandı · 14–16 · 7 dk içinde · Ayşe Y.     │
├ BOSS bilgileri ▸  Durum: Açık · Ekip: — · BOSS randevusu: —  │
└──────────────────────────────────────────────────────────────┘
```

- **Tek birincil düğme** işin durumuna göre değişir: Yeni → "Ata" · Randevulu → "Ata" · Atandı → "Kaydet" (yalnız bir şey değiştiyse, yoksa hiç birincil yok) · Evde yok → "Yeniden ata" (teyit işareti zorunlu) · Altyapı → "Ticket'ı aç".
- **Teknisyen seçici:** en üstte öbeğin teknisyeni, altında bugünkü yüküyle diğer teknisyenler ("bugün 9 iş · 3 BTK"), sonra "Yakındaki teknisyenler" (işin 3 km içinde işi olanlar). Arama kutusu var.
- **Dilim:** 2 saatlik dilimler; 08–20 ayardan gelir. Varsayılan, teknisyenin **sıradaki boş dilimidir** (dilim kapasitesi = ⌈günlük iş / 5⌉). Randevu KARMA-2'ye göre **aramadan** verilir: dilim, müşteriye söylenecek tahmini varış saatidir. "Teyitli" işareti yalnız müşteriyle konuşulduysa konur.
- **Randevusuz ata** mümkündür: dilim seçilmezse sıradaki boş dilim yazılır. **Teknisyensiz randevu** da mümkündür: "Randevu ver" metin düğmesi işi `randevulu` yapar.
- **BOSS'ta aç:** `ayar.boss_is_url` şablonu (`{task_no}`, `{musteri_no}`) tanımlıysa yeni sekmede açar. Tanımlı değilse Task No'yu kopyalar ve "Task No kopyalandı, BOSS'ta arayın" der.
- **Ticket (F9):** Binada açık ticket varsa bölüm sarıya döner: "Bu binada açık SİNYAL ticket'ı var (#12, 3 gündür). Teknisyen gönderilmez." Birincil düğme "Ticket'a bağla" olur. Ticket yoksa "Ticket bağla / aç", ön doldurulmuş "Yeni ticket" penceresini açar (bina, konu, metin hazır). Bağlanınca iş `altyapi` olur; rozet ticket'ın durumunu gösterir. Ticket ÇÖZÜLDÜ olunca iş kendiliğinden `yeni`ye döner.
- **Öbek: Değiştir (F5):** öbek seçici açılır; seçilen öbek bu iş için `obek_elle_id` olur ve satırda "elle" diye işaretlenir. Mahallenin öbeği değişmez. Yeniden içe aktarımda elle öbek korunur.
- **Diğer:** her biri tek soruluk küçük bir çekmece açar ("Neden?" + gerekiyorsa "Ne zaman tekrar bakılsın?").
- Açılış ve kopyalama `musteri_erisim` kaydına yazılır (§2.3).
- **Eşzamanlılık:** kaydederken `surum` gider. Başkası iş üzerinde değişiklik yaptıysa çekmece güncel hâle döner ve üstte bir satır belirir: "Bu iş az önce Mehmet T. tarafından güncellendi; güncel hâli gösteriliyor." Kullanıcının yazdığı not kaybolmaz.

### 4.4 Öbek çekmecesi ve mahalle seçici (F1, F2)

Öbekler listesinden, öbek başlığındaki "Düzenle"den ya da `#/yonetici/obekler/<id>` adresinden açılır.

```
┌ Görükle                                     [Bitti] ┐      ┌ Mahalle ekle · Görükle              [Vazgeç] ┐
│ 3 mahalle · 31 açık iş                               │      │ 🔍 Mahalle ya da ilçe yazın                   │
│ Teknisyen  Ali K.                          Değiştir › │      ├ GÜRSU ───────────────────────────────────────┤
├ Mahalleler ─────────────────────────────────────────┤      │ ☐ İlçenin tamamı (15 mahalle)                 │
│ Görükle · Nilüfer                14 iş         ⊖     │      │ ☐ Mahalle 1                  bugün iş yok     │
│ Mahalle 2 · Nilüfer              17 iş         ⊖     │      │ ☑ Mahalle 2   bugün 2 iş · Yıldırım öbeğinde  │
│ Mahalle 3 · Nilüfer        bugün iş yok        ⊖     │      │ ☐ Mahalle 3                  bugün iş yok     │
│ ＋ Mahalle ekle                                       │      ├───────────────────────────────────────────────┤
├──────────────────────────────────────────────────────┤      │ "Göçmen" listede yok.                          │
│ Adını değiştir                                        │      │   [Yeni mahalle olarak ekle]                   │
│ Teknisyenlere böl                                     │      ├───────────────────────────────────────────────┤
│ Öbeği sil                                  (kırmızı)  │      │ 1 mahalle Yıldırım öbeğinden taşınacak.        │
└──────────────────────────────────────────────────────┘      │ [        2 mahalleyi ekle ve taşı        ]    │
                                                               └───────────────────────────────────────────────┘
```

- **Mahalleler listesi (F1)** öbeğin *tanımıdır*; bugünkü rapora bağlı değildir. Her satırda bugünkü iş sayısı yazar (işi yoksa "bugün iş yok"). "⊖" düğmesi 44 px'tir ve mahalleyi hemen çıkarır; çıkarılan mahalle öbeksiz kalır. Tost: "Mahalle 2 çıkarıldı · Geri al". İş sayıları aynı yanıtta güncellenir; sayfa yenilenmez.
- **İlçenin tamamı** satırında "Mudanya · ilçenin tamamı · 7 iş" yazar. Aynı ilçeden tek tek eklenmiş mahalle varsa o mahalle önceliklidir: birebir eşleşme önce gelir, bugünkü `bul` kuralı.
- **"＋ Mahalle ekle" (F2)** Bursa + Yalova'nın **bütün** mahalle sözlüğünü açar (§5.5): 23 ilçe, rapordan bağımsız. Arama Türkçe harf duyarsızdır ("gursu" → Gürsu). Sonuçlar ilçeye göre gruplanır ve her ilçenin başında "İlçenin tamamı" durur. Başka öbekteki mahallenin yanında o öbeğin adı yazar. Seçilince alt çubukta **tek cümlelik taşıma onayı** görünür: "1 mahalle Yıldırım öbeğinden taşınacak." Sessiz taşıma yoktur.
- **Listede yoksa:** Arama birebir sonuç vermezse "“Göçmen” listede yok. [Yeni mahalle olarak ekle]" çıkar. Bu düğme ilçe seçtirir (23 ilçe; aramada ilçe adı yazıldıysa o seçili gelir). Mahalle sözlüğe `kaynak='elle'` ile girer ve öbeğe eklenir. Aynı ad ileride bir raporda gelirse (ör. "Göçmen Mah.") o iş kendiliğinden bu öbeğe düşer.
- **Öbek boş kalabilir.** Son mahalle çıkınca öbek silinmez; "Bu öbekte mahalle yok" boş durumu görünür (§4.14). Silmek ayrı ve açık bir eylemdir.
- **Adını değiştir:** aynı ad (Türkçe harf duyarsız) başka bir öbekte varsa reddedilir: "Bu adda bir öbek var." Sessiz birleştirme yoktur.
- **Teknisyenlere böl:** bugünkü "Böl" özelliğidir (dengeli bölme, aynı bina ayrılmaz). Önizlemede her parçanın satırı ve teknisyen seçicisi vardır; tek "Ata" düğmesi işleri teknisyenlere dağıtır. "Mahalleye göre kalıcı böl" ikinci düzeydedir (Diğer ▸).
- **Öbeği sil:** onay çekmecesinde "Görükle öbeği silinsin mi? 3 mahallesi öbeksiz kalır; 31 iş Bakılacak'a düşer." yazar. Sonra 10 sn "Geri al" tostu çıkar. Silinen tanım `obek_olay.ayrinti` içinde saklanır.
- **Yeni öbek:** Öbekler listesinin başında "＋ Yeni öbek". Ad yazılır, çekmece açılır ve "＋ Mahalle ekle" hemen odaklanır.

### 4.5 Bakılacaklar: sorunlu işi elle öbeğe koymak (F4, F5)

Bu liste **yalnız gerçek sorunları** gösterir (F4). Kullanıcının kuralına göre Location Id varsa OneMap binasının mahallesi
esastır; Lokasyon eşleşmesi DB üzerinden 332/332'dir (§7).

| Neden (düz Türkçe) | Kod | Eylem |
|---|---|---|
| "Adres İzmir yazıyor; bölgemiz Bursa ve Yalova." | `il_disi` | [Öbeğe ekle] · [Adres doğru, bölge dışı → Merkeze gönderildi] |
| "Mahalle bulunamadı." | `mahalle_yok` | [Öbeğe ekle] · [Mahalleyi seç] (sözlükten; o mahalleye bağlanır ve öbeği varsa oraya düşer) |
| "Mahallesi hiçbir öbekte değil: Mahalle 4 · Kestel." | `obeksiz` | [Mahalleyi bir öbeğe ekle] (öbek çekmecesi, mahalle seçili gelir) · [Yalnız bu işi öbeğe ekle] |
| "BOSS'ta askıda; ne zaman tekrar bakılacağı yok." | `uyanma_yok` | [Uyanma saati gir] |

"Öbeğe ekle" öbek seçiciyi açar. Seçimden sonra iş `obek_elle_id` alır, `sorun` temizlenir ve iş seçilen öbeğin listesine "elle" işaretiyle düşer (F5).
**Konumu yaklaşık** işler (bugün 50 ilçe merkezi + 46 mahalle merkezi) Bakılacak'a **girmez**. Onlar başlıkta sessiz bir bilgi çipi
olarak durur ("96 işin konumu yaklaşık"); basınca süzülür. Liste boşsa yeşil bir hap görünür: "✓ Bütün işler öbeğinde".

### 4.6 Aranacaklar: masa kuyruğu (KARMA-2 kural 4, 8, 12)

Tek liste, bant sırasıyla dizilir: BTK teşhis (vade 45 dk) › evde yok denemesi › uyanan askı › Kanal Şikayeti. Satırda vade ("12 dk kaldı"),
deneme sayısı ve "Müşteri No [Kopyala]" var. Telefon sistemde olmadığı için arama BOSS/Maya'dan yapılır. Sonuç **tek dokunuşla** girilir:

| Düğme | Ne olur |
|---|---|
| Düzeldi (canlı test yapıldı) | `cozuldu`, neden `telefonda_canli_test`; saha ziyareti iptal. `tekrar` bayraklı işte bu düğme yoktur |
| Şimdi evde | Dilim = şimdi … +3 s, teyitli; iş teknisyenin sırasında öne alınır |
| Başka gün | Gün + dilim seçici; teyitli |
| Ulaşılamadı | `deneme + 1`. BTK teşhisinde başka hiçbir şey değişmez, teknisyen habersiz gider. Evde yok merdiveninde sıradaki bant `uyanma` olur (+2 s, akşam 17:30, ertesi 10:00) |
| Cevapsız · Kapalı · Yanlış numara | "Ulaşılamadı" gibi işler; ölçüm için ayrı kodlanır (kural 17) |

Önceki işinde ulaşılamamış müşteri ("kötü geçmiş") gri görünür ve BTK teşhis kuyruğuna alınmaz (kural 14).

### 4.7 Toplu ata: 15 dakikanın anahtarı (F7, F17)

Öbek listesinin başındaki kart: **"4 atanmamış iş → Ali K.'ya ata (bugün 3, yarın 1)  [Ata]"**.

- Teknisyen = öbeğin teknisyeni. Yoksa kart "Bu öbeğin teknisyeni yok. [Teknisyen seç]" der.
- Sıra: BTK önce (hedefe göre), sonra kalan süre. Dilimler teknisyenin sıradaki boş dilimlerinden dağıtılır. Bugünün kapasitesi dolarsa yarın 08:30'dan devam edilir (KARMA-2: gece gelen BTK ilk dalgada).
- Açık ticket'ı olan binadaki iş **atanmaz**. Kartta "1 iş ticket bekliyor, atanmadı" yazar (kural 11).
- Evde yok durumundaki iş toplu atamaya **girmez** (kural 8).
- Sonuç tostu: "4 iş Ali K.'ya atandı · Geri al". Geri al, bu toplu işlemin bütün olaylarını geri çevirir.
- Kartın yanındaki "Başkasına…" metin düğmesi teknisyen seçtirir; "Teknisyenlere böl" öbek çekmecesine gider.

### 4.8 Rapor yükle ve fark (F18)

- Dosya sayfanın herhangi bir yerine bırakılır ya da başlıktaki "Rapor yükle" (ikincil düğme) ile seçilir. Yükleme sürerken şerit ince bir ilerleme çubuğuna döner ve **başka hiçbir kullanıcı beklemez** (§7.4).
- Sonuç tek satırdır: **"Yeni 12 · Güncellenen 41 · Kapanan 30 · Yeniden açılan 1 · Değişmeyen 353"**. Her sayıya basınca o işler süzülür.
- Aynı dosya ikinci kez yüklenirse: "Bu dosya 12:12'de yüklendi; değişiklik yok." (kayıt oluşmaz).
- Eksik rapor koruması §3.5'teki soruyu sorar.
- Atamalar, randevular, elle öbekler, ticket bağları ve notlar **hiçbir yüklemede silinmez** (anahtar Task No).

### 4.9 Yeni iş: bayinin açtığı iş (F16)

Başlıktaki "＋ Yeni iş" açılır. Alanlar sırayla:

1. **Kaynak**: [Bayi açtı] [Global (dış kanal)]
2. Müşteri No
3. Müşteri adı
4. İş tipi: bilinen task adlarından arama
5. **Bina**: Location Id, bina adı ya da adres ara → mahalle ve öbek kendiliğinden gelir. Bulunamazsa ilçe + mahalle seçilir.
6. Not

Birincil düğme: "İşi aç". Task No `B000001` biçiminde bayi numarası alır. İş `yeni` olarak düşer; 24 s saati açılış anından başlar.
Rapordan gelen işte kaynak Satış Kanalı sütunundan türetilir: "GLOBAL" geçiyorsa `global`, "DEHA" geçiyorsa `bayi`, boşsa `NULL`
("kaynağı bilinmiyor"; eşleme kuralı kullanıcı onayı bekliyor, §13). Satırda "Global" ya da "Bayi" rozeti görünür; Süz'de kaynak süzgeci vardır.
**Birleştirme (P2):** Bayi işi BOSS'a düşünce aynı `(musteri_no, task_adi)` 3 gün içinde gelirse bayi işinin çekmecesinde
"BOSS'ta 123456789 olarak açıldı. [Birleştir]" çıkar. Birleştirince geçmiş ve atama BOSS işine taşınır; bayi işi `kapandi/birlesti` olur.

### 4.10 Teknik · İşlerim (telefon önce; F7)

```
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ İşlerim               Çar 30 │   │ ‹ İşlerim                    │
│ 6 iş · 2 BTK · ilki 08:30    │   │ BTK  Bağlantı Problemi       │
│ ──────────────────────────── │   │ Kalan 5 s 10 dk              │
│ 1  08–10  BTK Bağlantı     › │   │ 08–10 · teyitli ✓            │
│    Görükle · 12. Sokak       │   │ Ayşe K. · No 1234… [Kopyala] │
│    Kalan 5 s                 │   │ (adres)                      │
│ 2  10–12  Modem Değişikliği › │   │ Site A · Location Id [Kopyala]│
│    Görükle · Site A    ⚑     │   │ [       Yol tarifi        ]  │
│ 3  12–14  TV+ Arıza        › │   │ ⚑ Binada ticket: SİNYAL açık │
│ …                            │   │ ──────────────────────────── │
│ Bitenler (2) ▸               │   │ Evde yok · Malzeme · Not     │
├──────────────────────────────┤   ├──────────────────────────────┤
│  İşlerim   Harita   Ben      │   │ [       Yola çıktım       ]  │
└──────────────────────────────┘   └──────────────────────────────┘
```

- Sıralama: dilim, sonra BTK, sonra kalan süre. Aşırı yük modunda KARMA-2 kural 5'in yalın hâli uygulanır (§6.3 `sira`). Teknisyen sırayı değiştirebilir; nedenini tek dokunuşla seçer (yakın · müşteri istedi · diğer).
- Kartın altında **tek birincil düğme** durur ve sırayla değişir: "Yola çıktım" → "Başladım" → "Bitti". "Bitti"den sonra kart "Bitenler"e iner.
- **"Evde yok"**: "10 dk bekledim, 2 kez aradım" işareti + isteğe bağlı not. İş anında operasyonun Aranacaklar listesine düşer.
- **"Ticket var"** (Diğer ▸): sinyal ya da port sorunu sahada fark edilirse işaretlenir; iş operasyona "altyapı şüphesi" notuyla döner.
- Bina kimliği (bina adı, Location Id, koordinat), satışçı uygulamasındaki `BinaKimlik` bileşeniyle gösterilir. Yol tarifi koordinatla açılır.
- **Çevrimdışı önce:** Sunucu ofis ağında (10.54.3.75) ve sahadan erişim için VPN + HTTPS gerekiyor (OPERASYON_TASARIM Faz 2 ön koşulu). Bu yüzden:
  - Liste sabah ofis Wi-Fi'ında alınır ve telefonda saklanır (SW önce ağ, olmazsa önbellek: `/api/islerim` eklenir).
  - Durum düğmeleri bugünkü satış kuyruğuna (IndexedDB) `offline_id` ile yazılır ve bağlantı gelince gönderilir. Çift gönderim zararsızdır (`is_olay` benzersiz dizini).
  - Başlıkta bugünkü "Çevrimdışı · 3 kayıt bekliyor" şeridi görünür.
  - VPN gelene kadar teknisyen BOSS Mobil'le de çalışabilir; BOSS durumları §3.3'e göre içe aktarımla yansır.
- Masaüstünde aynı liste ortada, 640 px genişlikte görünür.

### 4.11 Ekip (F12, F13)

```
┌ Ekip                                                         [＋ Kişi ekle] ┐
│ ┌ Görevleri gözden geçirin ─────────────────────────────────────────────┐  │
│ │ 8 kişi "Yönetici" görünüyor. Gerçek görevlerini seçin.  [Gözden geçir]│  │
│ └────────────────────────────────────────────────────────────────────────┘  │
│ [Hepsi 10] [Satış 2] [Operasyon 0] [Teknik 0] [Yönetici 8]   🔍 Ara          │
│ ◯ Ali K.        Teknik · Görükle, Özlüce           Aktif               ›     │
│ ◯ Ayşe Y.       Operasyon                          Aktif               ›     │
│ ◯ Can D.        Satış · Bölge 3                    Davet bekliyor      ›     │
│ ◯ Deniz A.      Satış · Bölge 5                    Pasif               ›     │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **Liste satırı:** baş harf, ad, görev + görev bilgisi, durum. Telefon numarası listede maskelidir ("0532 ••• •• 06"); tam hâli kişi çekmecesindedir. Telefonda tablo yoktur, satır vardır.
- **Kişi çekmecesi:**
  - Alanlar: Ad · Telefon · **Görev** (Satış · Operasyon · Teknik · Yönetici; dört parçalı seçici) · göreve göre açılan alanlar (Satış → Bölge, zorunlu; Teknik → Öbekleri, BOSS'taki ekip adı, günlük iş kapasitesi (varsayılan 15)) · Aktif.
  - Alt kısım: "Kaydet" (birincil) · "PIN'i sıfırla" · "Cihazlardan çıkış yaptır" · **"Kişiyi sil"** (kırmızı metin).
- **Davet kodu yalnız bir kez gösterilir:** oluştururken ya da sıfırlarken çıkan "Davet kodu hazır" çekmecesinde. Listede yalnız "Davet bekliyor" yazar. Kod 48 saatte geçerliliğini yitirir; çekmecede "Yeni kod üret" düğmesi var.
- **Sil (F13):**
  1. Düğmeye basınca sunucuya ön kontrol gider (`GET /api/kullanici/{id}/kayitlar`).
  2. **Kaydı yoksa:** "Can D. silinsin mi? Bu işlem geri alınamaz." → [Sil] (kırmızı) · [Vazgeç].
  3. **Kaydı varsa:** "Can D. silinemez: 2 açık işi, 312 ziyareti, 1 ticket kaydı var. Kayıtlar korunmalı. Pasife alırsanız giriş yapamaz, geçmişi olduğu gibi kalır." → [Pasife al] (birincil) · [Vazgeç].
     - Açık işi varsa ek satır: "Önce 2 açık işini başkasına atayın. [İşlerini göster]".
     - Kayıtlar yalnız gösterim (demo) verisiyse ek satır: "Bu kayıtların hepsi gösterim verisi." Bu durumda silme, gösterim verisi temizlenince açılır (§13).
  4. Korumalar: kişi kendini silemez (`kendini_silemez`). Son aktif yönetici silinemez (`son_yonetici`).
- `window.confirm` hiçbir yerde kalmaz. Onaylar uygulama içi çekmecededir (§9.3 Onay).

### 4.12 Yönetici · Pano (F11, F15, F17)

```
┌ Pano · 30 Eylül Çarşamba                                       Son rapor 12:12 ┐
│ ┌──────────────────┬──────────────────┬──────────────────┬──────────────────┐   │
│ │ 24 saatte sonuç  │ Atama süresi     │ 48 saati aşan BTK│ Bugün kapasite   │   │
│ │ %52              │ 9 dk             │ 5                │ 165 / 205        │   │
│ │ dün gelen 310 iş │ medyan · hedef 15│ en yaşlı 71 s    │ Aşırı yük · +3   │   │
│ └──────────────────┴──────────────────┴──────────────────┴──────────────────┘   │
│ Birikim · 24 saati aşan açık iş        ▁▂▃▅▆▆▇  288  (7 gün, ↑ 12/gün)           │
│ ── Öbekler ──────────────────────────────────────────────────────────────────── │
│ Öbek         Açık  Geciken  BTK  Atanmamış  Teknisyen   Bugün kapanan           │
│ Dumlupınar     65     31     22       0      —           4                      │
│ …                                                                              │
│ ── Ekip bugün ──────────────────────────────────────────────────────────────── │
│ Ali K.   Teknik   9 atandı · 5 bitti · 1 evde yok   İlk iş 08:42               │
│ ── Satış ───────────────────────────────────────────────────────────────────── │
│ Bugün 7 satış · 64 ziyaret · Hafta 31 / 60 hedef ▓▓▓▓▓░░░░   [Satışa git ›]     │
│ ── Erişim kaydı ▸  (bugün 41 müşteri kartı açıldı)                              │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Dört kutu, dört soru:**
  - Sözümüzü tuttuk mu? Dün gelen işlerin 24 s içinde `cozuldu` ya da `kapandi` olan payı.
  - Hızlı mıyız? Atama süresinin medyanı.
  - BTK'yı kaçırıyor muyuz? 48 saati aşan BTK sayısı.
  - Yetiyor muyuz? Kapasite: talep = açık saha işi; kapasite = aktif teknik × günlük iş; mod ve esnek önerisi KARMA-2 kural 15'ten.
- Her kutuya basınca ilgili liste açılır. Renk yalnız hedef aşılınca girer; kutular varsayılan olarak nötrdür.
- Veri yoksa: "Bu hafta kayıt yok" yazar; sıfır çubuk çizilmez.
- Telefonda kutular alt alta satır olur: değer sağa yaslı, açıklaması altında.
- Kapanış anı, bizde `cozum_zamani` varsa odur. Yoksa `kaybolma` kullanılır, ama bu içe aktarım aralığı kadar geç olabilir; Task Bitiş sütunu doluysa o esastır. Kutunun ⓘ'sinde bu yazar.

### 4.13 Satış yönetimi kancası (F15)

v2 satış tarafını **yeniden tasarlamaz**; satış uygulaması zaten sade. v2'nin yaptıkları:

1. Pano'ya "Satış" kartı eklenir: bugün ve hafta satış/ziyaret, `ayar.haftalik_satis_hedefi` ile ilerleme, satışçı başına mini satır. Veri bugünkü `/api/ozet/gun` uçlarından gelir.
2. "Satış ▸" menü grubu yöneticide mevcut ekranları toplar: Canlı durum, Kapsama, Görev atama, Rapor.
3. Ticket çözülünce binanın satış listesine geri dönmesi (OPERASYON_TASARIM §3.6 adım 5) bu işin sonraki adımıdır.
4. Ayrıntılı satış yönetimi (hedef, prim, kampanya) sonraki fazdadır; §13'te soru olarak duruyor.

### 4.14 Boş durumlar ve ilk gün (F14)

Her boş durum **ne olduğunu, neden boş olduğunu ve ne yapılacağını** tek cümlede söyler ve tek eylem sunar.

| Yer | Metin | Eylem |
|---|---|---|
| İşler, hiç rapor yok | "Henüz iş yok. BOSS'tan **Teknik Task Detay Raporu**'nu indirip buraya bırakın. Sistem kurulum işlerini ayıklar, her işi öbeğine koyar." | [Rapor seç] |
| Öbeğin işi yok | "Bugün Görükle'de iş yok. Yeni rapor gelince burada görünür." | — |
| Öbekte mahalle yok | "Bu öbekte mahalle yok. Bursa ve Yalova'nın bütün mahallelerinden seçebilirsiniz; bugün işi olmayanlar da listede." | [＋ Mahalle ekle] |
| Bakılacak boş | "✓ Bütün işler öbeğinde." | — |
| Aranacaklar boş | "Şu an aranacak kimse yok. BTK işi gelince 45 dakika içinde burada olur." | — |
| İşlerim boş | "Bugün size atanmış iş yok. Operasyon atayınca burada sıralı görünür. Aşağı çekerek yenileyin." | — |
| Ekip, tek kişi | "Ekibinizi ekleyin: telefon numarası yeter; kişi ilk girişte kendi PIN'ini belirler." | [＋ Kişi ekle] |
| Ticketlar boş | "Takipte ticket yok. Bir işte 'Ticket bağla' ya da Excel'den aktar." | [Excel'den aktar] (CLI ipucu kalkar) |

**İlk açılış ipucu** (kişi başına bir kez; "Anladım" ile kapanır): İşler'de üç küçük balon görünür: **"1 Öbek seçin · 2 İşe dokunun · 3 Ata'ya basın"**.
Her ekranın başlığının altında o ekranın ne işe yaradığını söyleyen tek bir cümle durur. Örnek: "Gelen işleri teknisyenlere buradan dağıtırsınız."

### 4.15 Kelime sözlüğü (düz Türkçe)

| Eskisi / iç terim | Ekranda |
|---|---|
| parça, Süzüleni böl | Teknisyenlere böl |
| Mahalleye göre / Binaya göre | (Diğer ▸) "Mahalleye göre kalıcı böl" |
| Kontrol edilecek adresler | Bakılacak |
| Mahalle kaynağı: adres-yeni … | (yalnız ⓘ içinde) "Mahalle adresten bulundu" |
| Konum kaynağı: ilçe merkezi (kaba) | "Konum yaklaşık (ilçe merkezi)" |
| Task Durumu = Askıya alındı | Askıda |
| öbek | **Öbek**. Kullanıcının kendi kelimesi, korunur. İlk görüldüğü yerde ⓘ: "Birlikte çalışılan mahalle grubu" |
| window.confirm "silinsin mi?" | Onay çekmecesi + Geri al |
| rol | Görev |

### 4.16 Denetimden gelen mevcut ekran düzeltmeleri

| Öncelik | Düzeltme |
|---|---|
| P1 | İşler ekranı §4.1'deki gibi yeniden kurulur (bugünkü IsEmirleri.tsx'in yerine geçer; eski adres yönlenir) |
| P1 | Telefonda yönetici menüsü sabit blok değil, alt sekme çubuğu (§4.0) |
| P1 | Ekip: davet kodu bir kez; 4 görev; sil; telefonda satır listesi |
| P1 | Giriş: fiziksel klavye; 360 px sütun; rol yönlendirmesi |
| P1 | Karanlık mod: `.yon-uyari` türevleri, birincil düğme, öbek renk noktaları, demo hapı için token kullanımı (§9.4) |
| P2 | Kapsama ve Veri kalitesi: telefonda büyük sayılar alt alta satır; kaydırılabilir segment |
| P2 | Canlı durum → "Bugün için görev ata" seçili satışçıyla açılsın (`/yonetici/atama/${id}`) |
| P2 | Tek marka işareti (giriş, PWA simgesi, konsol) |
| P2 | Yönetici CSS'indeki ~70 sabit renk koduna token (dokunulan ekranlarda P1) |

---

## 5. Veri modeli ve göçler

### 5.1 İlkeler

- **Yalnız ekleyen göç.** Yeni tablo ve sütun eklenir. Tek istisna `kullanici` tablosunun CHECK'idir; o da §5.3'teki kanıtlanmış sırayla yeniden kurulur.
- **Yeni tablolarda dar CHECK yok.** Değer kümeleri Python sabitleriyle doğrulanır.
- **Anahtar Task No (TEXT).** Pandas satır numarası hiçbir yerde kimlik olarak kullanılmaz.
- **Kullanıcının dosyaları salt okunur.** `operasyon/obekler.json` ve `operasyon/veri/son_yukleme.pkl` okunur (JSON) ya da hiç açılmaz (pickle). Asla yazılmaz, silinmez.

### 5.2 Göç çerçevesi (F20)

Yeni modül `saha/goc.py`. Bugünkü `db.gocler()` aynen çalışmaya devam eder (idempotent, tespit tabanlı). Onun ardından sürümlü adımlar gelir:

```python
ADIMLAR = [
    (2, "rol_genislet", rol_genislet),        # §5.3
    (3, "is_emri_tablolari", v2_tablolar),    # §5.4 (CREATE TABLE IF NOT EXISTS)
    (4, "v2_tohum", v2_tohumla),              # §5.5 (öbek JSON'u, mahalle sözlüğü)
]
```

1. **Tek yerde, tek kez.** `saha/sunucu.py` önce `port_dolu_mu()` kontrolünü yapar. Port doluysa "Sunucu zaten açık" der ve **hiçbir şeye dokunmadan** çıkar. Sonra `saha/.goc.kilit` dosyası `os.open(O_CREAT|O_EXCL)` ile kilitlenir. Lifespan içindeki `_veritabanini_hazirla` aynı kilidi kullanır; kilit alınamazsa göç atlanır.
2. **Bekleyen adım var mı?** `PRAGMA user_version` < 4 ya da bir adımın tespit sorgusu "eksik" diyorsa bekleyen adım vardır. Yoksa hiçbir şey yapılmaz (ikinci açılış no-op).
3. **Göç öncesi yedek, ayrı adla:** `yedekle.goc_yedegi()` → `saha/yedek/goc/saha-oncesi-AAAAAGG-SSDDss.db`. Kaynak salt okunur açılır ve backup API kullanılır. Kopyada `PRAGMA journal_mode=DELETE` çalıştırılır, dosya salt okunur yapılır. `integrity_check = ok` olmalı ve tablo satır sayıları kaynakla eşit olmalı. **Yedek doğrulanamazsa göç yapılmaz**; sunucu Türkçe mesajla kapanır: "Güncelleme öncesi yedek alınamadı; veritabanına dokunulmadı. Diskte yer var mı? BT'ye haber verin." Günlük `saha-AAAA-AA-GG.db` dosyasının üzerine yazılmaz. Göç yedekleri `eskileri_sil` kapsamı dışındadır; en son 10 tanesi tutulur.
4. **Her adım tek işlemde.** `BEGIN IMMEDIATE … COMMIT`, hata olursa `ROLLBACK`. `executescript` kullanılmaz, çünkü kendiliğinden commit eder. Adım bitince `PRAGMA user_version = N`.
5. **Sonra doğrula:** `integrity_check`, `foreign_key_check` boş olmalı, satır sayıları öncekiyle eşit olmalı (yeni tablolar hariç). Sonuç `ayar.son_goc` içine JSON olarak yazılır ve açılış ekranına tek satır basılır: "Güncelleme tamam: 10 kişi, 1.257 ziyaret korundu. Yedek: saha/yedek/goc/…".
6. **İstisna yutulmaz.** `sunucu.py` istisnayı yakalar, Türkçe yazar ve kapanır. Yarım şemayla açılmaz.
7. **Yeniden tohumlama koruması:** `saha.db` yoksa ve `saha/yedek/` içinde dosya varsa `baslat.bat`/`kur.py` **tohumlamaz**. Şunu der: "Veritabanı bulunamadı. En son yedek: … Geri yüklemek için GERI_YUKLE.bat." Bu, 10 gerçek hesabın yer tutucularla ezilmesini önler.
8. **Açılışta ısınma:** `dsale.metrics`, `dsale.partition` ve `shapely` içe aktarımları lifespan'de, `yield`'den **önce** ve eşzamanlı yapılır (arka plan iş parçacığı kalkar). Bu, denetimde görülen yarı yüklenmiş shapely hatasını (500) kapatır.
9. `saha/gizli.key` güncellemede korunur; yoksa bütün jetonlar geçersiz olur. Kurulum notunda yazılıdır.

### 5.3 Göç 2: rol genişletme (kopyada kanıtlandı)

Tespit: `SELECT sql FROM sqlite_master WHERE type='table' AND name='kullanici'` içinde `'operasyon'` yoksa çalışır. CHECK'siz eski tablo da bu tespite takılır ve yeniden kurulur.
Bağlantı `isolation_level=None` ile açılır.

```sql
PRAGMA foreign_keys=OFF;                      -- işlem DIŞINDA (içeride etkisiz)
BEGIN IMMEDIATE;
-- Python: eski_seq = SELECT seq FROM sqlite_sequence WHERE name='kullanici'
-- Python: once = satır sayıları (bütün tablolar) + sha256(kullanici satırları, id sırasıyla, 10 sütun)
CREATE TABLE kullanici_yeni (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ad          TEXT    NOT NULL,
    telefon     TEXT    NOT NULL UNIQUE,
    pin_hash    TEXT,
    davet_kodu  TEXT,
    rol         TEXT    NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge       INTEGER,
    aktif       INTEGER NOT NULL DEFAULT 1,
    oturum_no   INTEGER NOT NULL DEFAULT 1,
    olusturma   TEXT    NOT NULL
);
INSERT INTO kullanici_yeni (id, ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, oturum_no, olusturma)
     SELECT id, ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, oturum_no, olusturma FROM kullanici;
DROP TABLE kullanici;
ALTER TABLE kullanici_yeni RENAME TO kullanici;
-- Silinmiş kişilerin id'si asla yeniden kullanılmaz (jeton kid+otr taşır):
INSERT INTO sqlite_sequence(name, seq)
     SELECT 'kullanici', :eski_seq WHERE NOT EXISTS (SELECT 1 FROM sqlite_sequence WHERE name='kullanici');
UPDATE sqlite_sequence SET seq = MAX(seq, :eski_seq) WHERE name='kullanici';
-- Python doğrulaması, COMMIT'ten ÖNCE (biri tutmazsa ROLLBACK):
--   satır sayıları == once; sha256(kullanici) == once
--   PRAGMA foreign_key_check  → 0 satır
--   SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_eski%' OR sql LIKE '%kullanici_yeni%' → 0
--   SELECT m.name FROM sqlite_master m, pragma_foreign_key_list(m.name) p
--          WHERE m.type='table' AND p."table" <> 'kullanici' AND p."table" LIKE 'kullanici%' → 0
COMMIT;
PRAGMA foreign_keys=ON;
PRAGMA user_version=2;
```

- **Yasak:** Önce eskiyi `RENAME` etmek (bugünkü ziyaret kalıbı). SQLite 3.50.4, 7 alt tablodaki 11 yabancı anahtarı `kullanici_eski`'ye yeniden yazar; tablo silinince uygulama çöker. Bu kopyada doğrulandı.
- Bilinmeyen bir rol değeri CHECK'e takılırsa `ROLLBACK` olur. DB değişmez, sunucu açılır, yalnız yeni görevler atanamaz: "Veritabanı yeni görevleri henüz tanımıyor; güncelleme günlüğüne bakın" (`rol_hatali`).
- `oturum_no`, `pin_hash`, `telefon` ve `davet_kodu` aynen kopyalanır. Açık telefonlar oturumda kalır; denetimde eski jetonlar yeniden kurulumdan sonra 200 döndü.
- Aynı sürümde `db.SEMA` içindeki kullanici tanımı bu CHECK ile, `ayarlar.ROLLER` de `("satisci","operasyon","teknik","yonetici")` ile güncellenir.

### 5.4 Göç 3: yeni tablolar

Hepsi `CREATE TABLE IF NOT EXISTS`. Tek işlemde, `execute` ile tek tek çalıştırılır (`executescript` değil).

```sql
-- ── Öbekler (obekler.json'un yerine geçer) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS obek (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ad            TEXT    NOT NULL,
    ad_k          TEXT    NOT NULL UNIQUE,            -- ie.anahtar(ad): Türkçe harf duyarsız tekillik
    teknisyen_id  INTEGER REFERENCES kullanici(id),   -- öbeğin (ev) teknisyeni; kişi silinirken NULL yapılır
    renk          INTEGER NOT NULL DEFAULT 0,         -- palet sırası 0..11
    olusturma     TEXT    NOT NULL,
    guncelleme    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS obek_mahalle (
    il_k       TEXT NOT NULL,
    ilce_k     TEXT NOT NULL,
    mahalle_k  TEXT NOT NULL,                         -- '*' = ilçenin tamamı
    obek_id    INTEGER NOT NULL REFERENCES obek(id) ON DELETE CASCADE,
    ref        TEXT NOT NULL,                         -- görünen biçim: 'Bursa/Nilüfer/Görükle'
    eklenme    TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k)             -- bir mahalle en çok BİR öbekte
);
CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id);
CREATE TABLE IF NOT EXISTS obek_olay (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    kullanici_id  INTEGER REFERENCES kullanici(id),
    obek_ad       TEXT NOT NULL,
    tur           TEXT NOT NULL,     -- olustur | ad | ekle | cikar | tasi | sil | geri_al | teknisyen | json_aktarim
    ayrinti       TEXT               -- JSON: ref'ler, eski/yeni ad, silinen tanımın tamamı (geri al için)
);

-- ── Mahalle sözlüğü: Bursa + Yalova, rapordan bağımsız (F2) ──────────────────
CREATE TABLE IF NOT EXISTS mahalle_sozluk (
    il_k       TEXT NOT NULL,
    ilce_k     TEXT NOT NULL,
    mahalle_k  TEXT NOT NULL,
    il         TEXT NOT NULL,
    ilce       TEXT NOT NULL,
    ad         TEXT NOT NULL,
    lat        REAL,
    lon        REAL,
    kaynak     TEXT NOT NULL,        -- resmi | liste | bina | rapor | obek | elle
    ekleyen_id INTEGER REFERENCES kullanici(id),
    eklenme    TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k)
);

-- ── Teknik profil (kullanici tablosuna dokunmadan) ───────────────────────────
CREATE TABLE IF NOT EXISTS teknik_profil (
    kullanici_id  INTEGER PRIMARY KEY REFERENCES kullanici(id),
    boss_ekip     TEXT,              -- BOSS 'Ekip' sütunundaki ad (içe aktarımda eşleşme)
    gunluk_is     INTEGER NOT NULL DEFAULT 15,
    guncelleme    TEXT NOT NULL
);

-- ── İçe aktarımlar ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ie_yukleme (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dosya_adi       TEXT    NOT NULL,
    sha256          TEXT    NOT NULL,
    tur             TEXT    NOT NULL DEFAULT 'tam',   -- tam | kismi
    zaman           TEXT    NOT NULL,
    yukleyen_id     INTEGER REFERENCES kullanici(id),
    satir           INTEGER NOT NULL DEFAULT 0,
    cikarilan       INTEGER NOT NULL DEFAULT 0,
    kalan           INTEGER NOT NULL DEFAULT 0,
    yeni            INTEGER NOT NULL DEFAULT 0,
    degisen         INTEGER NOT NULL DEFAULT 0,
    ayni            INTEGER NOT NULL DEFAULT 0,
    kaybolan        INTEGER NOT NULL DEFAULT 0,
    yeniden_acilan  INTEGER NOT NULL DEFAULT 0,
    sure_sn         REAL,
    ozet            TEXT             -- JSON, yalnız sayılar (çıkarılma nedenleri, mahalle/konum kaynakları)
);
CREATE INDEX IF NOT EXISTS ix_ie_yukleme_sha ON ie_yukleme(sha256);

-- ── İş emri: güncel hâl ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS is_emri (
    task_no          TEXT PRIMARY KEY,                -- BOSS Task No (metin) · bayi işi 'B000001'
    kaynak           TEXT NOT NULL DEFAULT 'boss',    -- boss | bayi
    kanal            TEXT,                            -- global | bayi | NULL
    task_adi         TEXT NOT NULL,
    serit            TEXT NOT NULL DEFAULT 'saha',    -- btk | saha | masa | lojistik
    musteri_no       TEXT,                            -- KİŞİSEL VERİ
    musteri_adi      TEXT,                            -- KİŞİSEL VERİ (kapanış + 30 gün → NULL)
    adres            TEXT,                            -- KİŞİSEL VERİ (kapanış + 30 gün → NULL)
    il TEXT, ilce TEXT, mahalle TEXT,
    il_k TEXT, ilce_k TEXT, mahalle_k TEXT,           -- öbek eşlemesi için anahtarlar
    mahalle_kaynak   TEXT,
    lokasyon         TEXT,
    bina_serial      TEXT,                            -- bilinçli olarak FK değil (bina pasif olabilir)
    lat REAL, lon REAL,
    konum_kaynak     TEXT,                            -- bina | site | mahalle | ilce | NULL
    obek_id          INTEGER REFERENCES obek(id) ON DELETE SET NULL,   -- mahalleden (sistem)
    obek_elle_id     INTEGER REFERENCES obek(id) ON DELETE SET NULL,   -- F5: varsa bu geçerli
    sorun            TEXT,                            -- il_disi | mahalle_yok | obeksiz | uyanma_yok | NULL
    acilis           TEXT NOT NULL,
    son24            TEXT NOT NULL,
    hedef            TEXT,                            -- BTK hedefi
    ilk_gorulme      TEXT NOT NULL,
    son_gorulme      TEXT,
    kaybolma         TEXT,
    ilk_yukleme_id   INTEGER REFERENCES ie_yukleme(id),
    son_yukleme_id   INTEGER REFERENCES ie_yukleme(id),
    boss_durum TEXT, boss_ekip TEXT, boss_randevu_bas TEXT, boss_randevu_bit TEXT, boss_aski TEXT,
    boss_bitis       TEXT,                            -- Task Bitiş Tarihi (doluysa kapanış anı)
    durum            TEXT NOT NULL DEFAULT 'yeni',
    durum_zamani     TEXT NOT NULL,
    teknisyen_id     INTEGER REFERENCES kullanici(id),
    sira             INTEGER,
    randevu_bas      TEXT,
    randevu_bit      TEXT,
    randevu_teyitli  INTEGER NOT NULL DEFAULT 0,
    ticket_id        INTEGER REFERENCES ticket(id),
    parca            TEXT,
    uyanma           TEXT,
    deneme           INTEGER NOT NULL DEFAULT 0,
    tekrar           INTEGER NOT NULL DEFAULT 0,
    atama_zamani     TEXT,
    atama_kaynak     TEXT,                            -- ekran | boss
    cozum_zamani     TEXT,
    kapanis_nedeni   TEXT,                            -- dogrulandi | bossta_kapandi | birlesti | ...
    notu             TEXT,
    olusturan_id     INTEGER REFERENCES kullanici(id),
    surum            INTEGER NOT NULL DEFAULT 1,
    guncelleme       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_is_durum     ON is_emri(durum);
CREATE INDEX IF NOT EXISTS ix_is_obek      ON is_emri(obek_id);
CREATE INDEX IF NOT EXISTS ix_is_teknisyen ON is_emri(teknisyen_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_mahalle   ON is_emri(il_k, ilce_k, mahalle_k);
CREATE INDEX IF NOT EXISTS ix_is_musteri   ON is_emri(musteri_no, task_adi);
CREATE INDEX IF NOT EXISTS ix_is_bina      ON is_emri(bina_serial);
CREATE INDEX IF NOT EXISTS ix_is_ticket    ON is_emri(ticket_id);

-- ── İş geçmişi: yalnız eklenir, hiç güncellenmez ──────────────────────────────
CREATE TABLE IF NOT EXISTS is_olay (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_no       TEXT NOT NULL REFERENCES is_emri(task_no),
    zaman         TEXT NOT NULL,
    kullanici_id  INTEGER REFERENCES kullanici(id),   -- NULL = sistem / içe aktarım
    kaynak        TEXT NOT NULL,                      -- ekran | telefon | ice_aktarim | sistem
    tur           TEXT NOT NULL,                      -- ice_aktarildi | durum | atama | randevu | obek | ticket | not
                                                      -- | alan | kayboldu | yeniden_acildi | geri_al | toplu
    eski          TEXT,
    yeni          TEXT,                               -- KİŞİSEL VERİ YAZILMAZ (adres/ad değişince yalnız alan adı)
    notu          TEXT,
    yukleme_id    INTEGER REFERENCES ie_yukleme(id),
    toplu_id      TEXT,                               -- toplu atamada ortak kimlik (hepsini geri almak için)
    offline_id    TEXT
);
CREATE INDEX IF NOT EXISTS ix_is_olay_task ON is_olay(task_no, zaman);
CREATE UNIQUE INDEX IF NOT EXISTS ux_is_olay_offline ON is_olay(kullanici_id, offline_id)
    WHERE offline_id IS NOT NULL;

-- ── Müşteri bilgisine erişim kaydı (KVKK) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS musteri_erisim (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici_id  INTEGER NOT NULL REFERENCES kullanici(id),
    task_no       TEXT NOT NULL,
    eylem         TEXT NOT NULL,     -- ac | kopyala | excel
    zaman         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_erisim ON musteri_erisim(kullanici_id, zaman);
```

Yeni `ayar` anahtarları: `obek_surum` (tam sayı; her öbek değişikliğinde +1) · `bayi_is_sayac` · `dilimler` ("08-10,10-12,12-14,14-16,16-18,18-20") ·
`boss_is_url` · `haftalik_satis_hedefi` · `son_goc`.

### 5.5 Göç 4: tohumlama (salt okuma kaynaklardan)

1. **Öbekler:** `obek` tablosu boşsa ve `OPERASYON_OBEK` (varsayılan `operasyon/obekler.json`) varsa dosya **okunur**. Her ref kanonik biçime çevrilir: 2 parçalı ref'e il, ilçeden tamamlanır, tekrarlar atılır. Sonra `obek` ve `obek_mahalle` satırları yazılır. Aynı mahalle iki öbekte geçiyorsa bugünkü `bul` kuralındaki gibi ilk öbek kazanır ve `obek_olay`'a `json_aktarim` çakışma notu düşülür (bugün 0 çakışma). Dosyaya **yazılmaz**. Kanıt: 14 öbek, 120 ref DB'de; dosyanın sha256'sı değişmemiş.
2. **Mahalle sözlüğü** (`INSERT OR IGNORE`; her açılışta çalışır, idempotent), öncelik sırasıyla:
   1. `data/ref/mahalle_resmi.json` varsa (Bursa 17 + Yalova 6 ilçenin resmî listesi, §13) → `resmi`
   2. `data/ref/mahalle_listesi.json` (10 ilçe, 621 mahalle, koordinatlı) → `liste`
   3. `bina` tablosundaki farklı `(il, ilce, mahalle)` → `bina`
   4. Öbek ref'leri (Yalova ve Karacabey'dekiler dahil 36 ref) → `obek`
   5. Her içe aktarımda raporda bulunan mahalleler → `rapor`
   6. Ekrandan eklenenler → `elle`
3. **İlçe listesi** kod içinde sabittir (`operasyon/mahalle.py:ILCELER`):
   - Bursa (17): Büyükorhan, Gemlik, Gürsu, Harmancık, İnegöl, İznik, Karacabey, Keles, Kestel, Mudanya, Mustafakemalpaşa, Nilüfer, Orhaneli, Orhangazi, Osmangazi, Yenişehir, Yıldırım.
   - Yalova (6): Merkez, Altınova, Armutlu, Çiftlikköy, Çınarcık, Termal.
   - Anahtarlar `ie.ilce_anahtari` ile üretilir ("Yalova Merkez" = "Merkez").
   - Bu sabit sayesinde **ilçenin tamamı** ve **yeni mahalle ekleme** sözlükte hiç mahallesi olmayan ilçede de çalışır.
   - Merkez koordinatı: `data/ref/osm_ilce.geojson` sınırlarının ağırlık merkezinden; Büyükorhan ve Harmancık için sabit.
4. **Pickle:** `son_yukleme.pkl` **açılmaz** (unpickle güvensiz ve sürüme bağlı) ve silinmez. `is_emri` boşsa İşler ekranı şunu der: "Yeni sürüm iş emirlerini kalıcı saklıyor. Son raporu bir kez daha bırakın." Günlük parça etiketleri zaten her yüklemede sıfırlanıyordu; kayıp yoktur.

### 5.6 Doğrulama sorguları (F20, T20)

```sql
SELECT rol, COUNT(*), SUM(aktif), SUM(pin_hash IS NOT NULL) FROM kullanici GROUP BY rol;   -- öncesiyle aynı
SELECT m.name, p."table" FROM sqlite_master m, pragma_foreign_key_list(m.name) p
 WHERE m.type='table' AND p."table" LIKE 'kullanici%';                                     -- hepsi 'kullanici'
SELECT COUNT(*) FROM ziyaret z LEFT JOIN kullanici k ON k.id=z.kullanici_id WHERE k.id IS NULL;  -- 0
SELECT seq FROM sqlite_sequence WHERE name='kullanici';                                    -- ≥ önceki (bugün 19)
PRAGMA integrity_check;  PRAGMA foreign_key_check;  PRAGMA user_version;                    -- ok · 0 satır · 4
```

### 5.7 Saklama

| Veri | Süre | Nasıl |
|---|---|---|
| `musteri_adi`, `adres` | Kapanış + 30 gün | NULL; açılışta ve 19:30 görevinde |
| `musteri_no` | Kapanış + 30 gün | HMAC-SHA256 (`gizli.key`) özetine çevrilir; tekrar tespiti özetle çalışır |
| Ham BOSS dosyası | 7 gün | `operasyon/veri/gelen/<sha>.xlsx` (git dışı), sonra silinir |
| `musteri_erisim` | 2 yıl | — |
| `is_olay` | Süresiz (kişisel veri içermez) | — |
| Excel çıktısı | Diske yazılmaz | Akış olarak iner; `musteri_erisim` 'excel' kaydı |

---

## 6. API

### 6.1 Genel

- Hata biçimi bugünkü gibidir: `{"hata": "<Türkçe cümle>", "kod": "<makine kodu>"}`.
- **Yeni kodlar:** `gecersiz_gecis`, `surum_eski` (409, gövdede güncel kayıt), `kismi_rapor_mi` (409), `ayni_dosya` (200 bilgi), `baska_obekte` (409), `ad_var` (409), `kaydi_var` (409), `kendini_silemez`, `son_yonetici`, `gorev_degisti` (401).
- **Sürüm:** Yazan her uç `surum` alır (iş başına `is_emri.surum`, öbekler için `ayar.obek_surum`). Uyuşmazsa 409 `surum_eski` + güncel hâl döner. İstemci güncel hâli gösterir ve kullanıcının yazdığı metni korur.
- **Rol bağımlılığı:** `yetki.rol_gerekli("operasyon", "yonetici")`. Bugünkü `yonetici()` bu fabrikanın özel hâli olarak kalır. Bilinmeyen rol her yerde 403 alır.
- **Kişisel veri kırpma:** `operasyon/gorunum.py:is_karti(satir, k)` tek yerdir. Teknik rol yalnız `teknisyen_id == k.id` olan işi görür; diğerinde 404 alır (varlığı bile sızmaz).
- Saatler yerel saat ISO biçimindedir (`2026-09-30T14:00`). Her liste yanıtında `sunucu_zamani` vardır.

### 6.2 Uç × rol tablosu

| Uç | Satış | Operasyon | Teknik | Yönetici |
|---|---|---|---|---|
| `GET /api/is-emri/ozet` | 403 | ✓ | 403 | ✓ |
| `GET /api/is-emri/isler` | 403 | ✓ | 403 | ✓ |
| `GET /api/is-emri/is/{task_no}` | 403 | ✓ | yalnız kendi işi | ✓ |
| `POST /api/is-emri/is/{task_no}` (atama, randevu, durum, öbek, ticket, not) | 403 | ✓ | yalnız kendi işi, yalnız `yolda`/`sahada`/`cozuldu`/`evde_yok`/"Malzeme"/"Ticket var"/not | ✓ |
| `POST /api/is-emri/toplu-ata` | 403 | ✓ | 403 | ✓ |
| `POST /api/is-emri/is` (yeni bayi işi) | 403 | ✓ | 403 | ✓ |
| `POST /api/is-emri/yukle` · `GET /api/is-emri/excel` | 403 | ✓ | 403 | ✓ |
| `GET /api/is-emri/aranacak` | 403 | ✓ | 403 | ✓ |
| `GET/POST/PATCH/DELETE /api/obek…` | 403 | ✓ | 403 (GET: yalnız kendi öbeklerinin adı) | ✓ |
| `GET/POST /api/mahalle` | 403 | ✓ | 403 | ✓ |
| `GET /api/islerim` · `POST /api/islerim/{task_no}` | 403 | ✓ (`?kullanici=`) | ✓ (kendisi) | ✓ (`?kullanici=`) |
| `GET /api/pano` | 403 | ✓ | 403 | ✓ |
| `GET /api/kullanici/{id}/kayitlar` · `DELETE /api/kullanici/{id}` | 403 | 403 | 403 | ✓ |
| `GET /api/kullanici?rol=teknik` (atama için) | 403 | ✓ (ad, id, yük; telefon yok) | 403 | ✓ |
| Satış uçları (`/api/bina*`, `/api/harita`, `/api/yollar`, `/api/ozet/kapsama`, `/api/ziyaret`, `/api/gorev/*`) | bölgesi | GET ✓, ziyaret ✗ | ✗ (kendi işinin `bina/{serial}` GET ✓) | ✓ |

### 6.3 Uçlar ve yükleri

**`GET /api/is-emri/ozet`**: üst şerit ve sol sütun için.

```json
{ "sunucu_zamani": "2026-09-30T12:14",
  "yukleme": {"id": 5, "zaman": "2026-09-30T12:12", "dosya_adi": "TeknikTaskDetayRaporu.xlsx", "tur": "tam",
              "yeni": 12, "degisen": 41, "kaybolan": 30, "yeniden_acilan": 1, "ayni": 353},
  "sayilar": {"acik": 437, "atanmamis": 12, "gecikmis_24": 288, "gecikmis_48": 189, "btk_48": 5,
              "bakilacak": 3, "aranacak": 7, "konum_yaklasik": 96, "ticket_bekleyen": 4},
  "atama": {"en_eski_atanmamis_dk": 9, "medyan_dk_bugun": 9, "hedef_dk": 15},
  "kapasite": {"talep": 205, "teknisyen": 11, "kisi_basi": 15, "kapasite": 165, "mod": "asiri_yuk", "esnek_oneri": 3},
  "obek_surum": 42,
  "obekler": [{"id": 3, "ad": "Görükle", "renk": 2, "acik": 31, "yeni": 4, "atanmamis": 4, "geciken": 9, "btk": 14,
               "teknisyen": {"id": 21, "ad": "Ali K."}}],
  "obeksiz": {"acik": 0} }
```

"Açık" = `kaybolma IS NULL AND durum NOT IN ('cozuldu','kapandi')`. Geçerli öbek = `COALESCE(obek_elle_id, obek_id)`.

**`GET /api/is-emri/isler?obek=3|obeksiz|bakilacak&durum=yeni,atandi&sadece=atanmamis|geciken|btk|ticketli|yaklasik&teknisyen=21&kaynak=global&ara=…&sirala=kalan|acilis|randevu&limit=500`**

```json
{ "sunucu_zamani": "…", "toplam": 31,
  "isler": [{
    "task_no": "123456789", "task_adi": "Bağlantı Problemi", "serit": "btk", "kaynak": "boss", "kanal": "global",
    "durum": "atandi", "musteri_adi": "…", "musteri_no": "…",
    "adres_kisa": "Görükle · 12. Sokak", "il": "Bursa", "ilce": "Nilüfer", "mahalle": "Görükle",
    "obek": {"id": 3, "ad": "Görükle", "elle": false},
    "acilis": "2026-09-30T09:40", "son24": "2026-10-01T09:40", "hedef": "2026-09-30T21:40",
    "kalan_dk": 1320, "renk": "yesil",
    "randevu": {"bas": "2026-09-30T14:00", "bit": "2026-09-30T16:00", "teyitli": false},
    "teknisyen": {"id": 21, "ad": "Ali K."},
    "ticket": {"id": 12, "durum": "AÇIK", "konu": "SİNYAL"},
    "bayraklar": ["btk", "binada_ticket", "tekrar", "konum_yaklasik"],
    "sorun": null, "surum": 3 }] }
```

Teknik rolünde `musteri_adi` kısa ("Ayşe K."). Satış rolü bu uca giremez.

**`GET /api/is-emri/is/{task_no}`**: liste satırının bütün alanları, ayrıca `adres` (tam), `lokasyon`, `bina` (`BinaKimlik` alanları),
`konum_kaynak`, `boss` (durum, ekip, randevu, askı), `musteri_sozu` (kesim kuralı), `olaylar[]` (son 50) ve `oneriler`
(`{teknisyen: [...öbeğin, yükü az olanlar, yakındakiler], dilim: {gun, bas, bit}, binada_ticket: {...}|null}`). Yan etki: `musteri_erisim('ac')` (kişi + iş başına günde bir).

**`POST /api/is-emri/is/{task_no}`**: tek uç, açık niyetler:

```json
{ "surum": 3,
  "ata":      {"teknisyen_id": 21, "randevu": {"bas": "…", "bit": "…", "teyitli": false}, "musteriye_ulasildi": false},
  "randevu":  {"bas": "…", "bit": "…", "teyitli": true},
  "durum":    {"kod": "askida", "neden": "abone_talebi", "uyanma": "2026-10-02T10:00"},
  "obek_elle_id": 5,
  "ticket_id": 12,
  "not": "Site yönetimi anahtarı verdi",
  "geri_al": 9812,
  "offline_id": "tel-…" }
```

Kurallar:
- Aynı istekte birden çok niyet olabilir. Hepsi tek işlemde, **§3.2 tablosuna göre** doğrulanır.
- `teknisyen_id` aktif bir `teknik` kullanıcısı olmalıdır.
- `randevu.bit > randevu.bas` olmalı ve en çok 7 gün ileride olabilir.
- `ticket_id` açık bir ticket olmalıdır.
- `evde_yok`tan atamada `musteriye_ulasildi: true` zorunludur.
- Yanıt: güncel iş kartı + oluşan `olay_id`'ler.

**`POST /api/is-emri/toplu-ata`**: `{"obek_id": 3, "task_nolar": [...]?, "teknisyen_id": 21, "onizle": true|false}`.
Önizleme `{atanacak: [{task_no, dilim}], atlanan: [{task_no, neden: "binada_ticket"|"evde_yok"}], bugun: 3, yarin: 1}` döner.
Uygulama `toplu_id` ile olay yazar; `{"geri_al_toplu": "<toplu_id>"}` bu işlemin hepsini geri alır (60 sn, aynı kişi).

**`POST /api/is-emri/is`** (bayi işi): `{"kanal": "bayi"|"global", "musteri_no", "musteri_adi", "task_adi", "bina_serial"?, "lokasyon"?, "il", "ilce", "mahalle"?, "not"?}` → `{task_no: "B000001", ...kart}`.

**`POST /api/is-emri/yukle?tur=tam|kismi`**: gövde xlsx, başlık `x-dosya-adi`. Uç **düz `def`** olarak tanımlanır; FastAPI onu iş parçacığı havuzunda çalıştırır, olay döngüsü tıkanmaz. Olası yanıtlar:
- `200 {yukleme: {...sayilar}, ozet: {...}}`
- `200 {kod: "ayni_dosya", yukleme_id}`
- `409 {kod: "kismi_rapor_mi", acik: 437, dosyada: 120, kaybolacak: 317}`
- `400 {kod: "rapor_tanınmadı" | "okunamadi" | "bos_dosya"}`
- `413 {kod: "buyuk_dosya"}`

**`GET /api/is-emri/aranacak`**: `{isler: [...liste satırı + {bant: "btk_teshis"|"evde_yok"|"aski"|"kanal", vade_dk, deneme, kotu_gecmis}]}`.
Sonuçlar `POST /api/is-emri/is/{task_no}` ile yazılır: `{"arama": {"sonuc": "duzeldi"|"simdi_evde"|"baska_gun"|"ulasilamadi"|"cevapsiz"|"kapali"|"yanlis_no", "randevu"?}}`.

**`GET /api/is-emri/excel`**: bugünkü `_hazir.xlsx` biçimi DB'den üretilir; Parça, Teknisyen, Randevu ve Durum sütunları eklenir. `musteri_erisim('excel')` kaydı yazılır.

**Öbek uçları** (`operasyon/api_obek.py`; hepsi `obek_surum` ister ve yanıtta döner):

| Uç | Gövde | Yanıt / hata |
|---|---|---|
| `GET /api/obek` | — | `{obek_surum, obekler: [{id, ad, renk, teknisyen, mahalleler: [{ref, il, ilce, ad, tum_ilce: bool, bugun_is}], acik, geciken}]}` (işi olmayan öbekler dahil) |
| `POST /api/obek` | `{obek_surum, ad}` | 409 `ad_var` |
| `PATCH /api/obek/{id}` | `{obek_surum, ad?, teknisyen_id?}` | 409 `ad_var` (sessiz birleştirme yok) |
| `POST /api/obek/{id}/mahalle` | `{obek_surum, refler: ["Bursa/Gürsu/*", "Bursa/Yıldırım/<mahalle>"], tasi: false}` | Başka öbekteki ref varsa ve `tasi=false` ise 409 `baska_obekte` + `[{ref, obek}]`; `tasi=true` taşır. Ref sözlükte yoksa 400 `mahalle_yok` (önce `POST /api/mahalle`) |
| `DELETE /api/obek/{id}/mahalle` | `{obek_surum, refler}` | Öbek boş kalabilir |
| `DELETE /api/obek/{id}` | `{obek_surum}` | `{geri_al: <obek_olay.id>}` |
| `POST /api/obek/geri-al` | `{obek_surum, olay_id}` | Silinen öbek ve mahalleleri geri gelir (başka öbeğe geçmemiş olanlar) |

Her öbek yazımı **aynı işlemde** açık işlerin `obek_id`'sini yeniden hesaplar (`UPDATE is_emri SET obek_id = … WHERE kaybolma IS NULL`; 437 satır, <50 ms)
ve güncel `ozet.obekler` sayılarını döndürür (F1: "iş sayıları anında güncellenir"). Değişiklikten sonra `operasyon/veri/obek_yedek/obek-<zaman>.json`
anlık görüntüsü yazılır (son 50 tutulur). **`obekler.json`'a yazılmaz.** CLI (`IS_EMRI_HAZIRLA.bat`) öbekleri `saha.db` varsa oradan salt okunur alır, yoksa JSON'dan.

**Mahalle uçları:**
- `GET /api/mahalle?ara=gursu&ilce=&limit=200` → `{ilceler: [{il, ilce, tum_ilce_ref, mahalle_sayisi, mahalleler: [{ref, ad, bugun_is, obek: {id, ad}|null, kaynak}]}]}`. Arama `ie.anahtar` ile yapılır (Türkçe harf, büyük/küçük ve nokta duyarsız); ilçe adı da eşleşir.
- `POST /api/mahalle` → `{il, ilce, ad}`: 23 ilçeden biri olmalı. Ad sözlükte zaten varsa (anahtar eşit) mevcut kaydı döner; yoksa `kaynak='elle'` ile eklenir. Açık işlerde `mahalle_k` eşleşen varsa `sorun` yeniden hesaplanır.

**Teknik uçları:**
- `GET /api/islerim?gun=2026-09-30` → `{sunucu_zamani, kapasite: {gunluk_is, atanan}, isler: [...liste satırı (kısa ad) + {sira, bina: {ad, location_id, lat, lon}, ticket}], bitenler: [...]}`.
- `POST /api/islerim/{task_no}` → `{offline_id, kod: "yolda"|"sahada"|"bitti"|"evde_yok"|"malzeme"|"ticket_var"|"not", not?, bekledim_aradim?: true, uyanma?}`. İdempotenttir: aynı `offline_id` ikinci kez gelirse ilk sonucu döner. Durum geçersizse (ör. operasyon işi başkasına atadıysa) 409 `gecersiz_gecis` + güncel kart döner ve telefon kartı "Bu iş size ait değil artık" diye kapatır.
- **Sıra:** `operasyon/siralama.py:sira(isler, mod)`. Normal mod: dilim → BTK → kalan süre. Aşırı yük modu: dilim → BTK (hedefe yetişebilecek önce) → her 3. seçimde en eski gecikmiş BTK → kalan süre. "En acil 5 içinden en yakın" kuralı Faz 2 pilotunda eklenir.

**Ekip uçları:**
- `POST /api/kullanici` (değişiyor): `rol ∈ ROLLER`; `bolge` yalnız satışta zorunludur; `teknik: {boss_ekip?, gunluk_is?, obekler?: [id]}` → `teknik_profil` + `obek.teknisyen_id`. Son aktif yönetici düşürülemez ya da pasife alınamaz (`son_yonetici`); kişi kendi görevini değiştiremez. Görev değişince `oturum_no+1`; `mevcut_kullanici` bu durumda `gorev_degisti` kodunu döndürür (jetondaki `rol` ile DB karşılaştırılır).
- `GET /api/kullanici/{id}/kayitlar` → `{silinebilir: false, acik_is: 2, sayilar: {"ziyaret": 312, "is_emri": 7, "ticket": 1, ...}, yalniz_gosterim: false}`. Sayılar **dinamik** üretilir: `pragma_foreign_key_list` ile `kullanici(id)`'ye başvuran bütün tablo/sütunlar taranır. İleride eklenen tablolar da kendiliğinden sayılır. `teknik_profil` ve `obek.teknisyen_id` "sahip olunan ayar" sayılır ve engellemez. Ziyaretlerde `offline_id LIKE 'demo-%'` ayrıca sayılır.
- `DELETE /api/kullanici/{id}` → tek işlemde `DELETE teknik_profil`, `UPDATE obek SET teknisyen_id=NULL`, `DELETE kullanici`. `IntegrityError` (yarış) → 409 `kaydi_var` + sayılar. Global `sqlite3.Error` işleyicisine (503 "BT'ye haber verin") **düşmez**.

**`GET /api/pano?gun=`** → `{uyum_24: {dun_gelen, sonuclanan, oran}, atama: {medyan_dk, p90_dk, hedef_ici_oran}, btk_48: {sayi, en_yasli_saat}, birikim: {gecikmis_24, seri_7g: [{gun, sayi}]}, kapasite, obekler: [...], ekip: [{id, ad, rol, atanan, biten, evde_yok, ilk_is}], satis: {bugun_satis, bugun_ziyaret, hafta_satis, hafta_hedef, satiscilar: [...]}, erisim: {bugun: 41}}`.
`seri_7g`, `is_emri.acilis/kaybolma/cozum_zamani` üzerinden geriye dönük hesaplanır; ayrı tablo gerekmez.

### 6.4 Güvenlik düzeltmeleri (yeni roller eklenmeden ÖNCE)

- `saha/yetki.py` rol başına bir izin tablosu tutar. Her `rol == 'satisci'` kısıtı olumlu izin listesine çevrilir: `api.py:1048` `_ziyaret_isle`, `api.py:1305` `bina_detay`, `yonetim_uclari.py:370` `_bina_yetkili`.
- `_bolge_kontrol`: yonetici ve operasyon → serbest (salt okuma). satisci → kendi bölgesi; bölge NULL ise **boş** (bugün 'şehrin tamamı' dönüyordu). teknik ve bilinmeyen rol → 403.
- `/api/ben`: rol başına dal. teknik → `{kullanici, islerim: {bugun, bitti}}` · operasyon → `{kullanici, is_ozet}`. Yönetici özeti yalnız yöneticiye gider.
- `/api/gorev/*`: yalnız satisci ve yonetici.
- `operasyon/api.py`: `APIRouter(dependencies=[Depends(rol_gerekli("operasyon","yonetici"))])`. Teknik uçları ayrı yönlendiricidedir.
- Ekip listesi yanıtında `davet_kodu` yoktur; kod yalnız oluşturma ve sıfırlama yanıtında bir kez döner.
- Test: her rol × her uç tablo güdümlü bir testle denenir (T6.2).

---

## 7. İçe aktarım hattı (F18)

### 7.1 Adımlar (tek işlem)

1. **Kimlik:** Gövdenin sha256'sı alınır. `ie_yukleme`'de varsa: "Bu dosya 12:12'de yüklendi; değişiklik yok." Hiçbir şey yazılmaz.
2. **Okuma** (iş parçacığı havuzunda): `ie.raporu_oku` + `ie.hazirla`. Kural değişmez: "kurulum" ve "2. donanım" çıkar, mahalle anahtarı (il, ilçe, mahalle), Location Id → OneMap binasının mahallesi. v2'de `hazirla` şu sütunları **da taşır**: Task No, Müşteri No, Müşteri Adı, Satış Kanalı, Task Durumu, Ekip, Randevu Başlangıç/Bitiş, Askıya Alınma Nedeni, Task Bitiş Tarihi. Taşımayanlar diske yazılmaz: cihaz seri no, Son Açıklama, satış temsilcisi.
3. **Bina eşleşmesi DB'den (F4):** `Sozluk.loc` `bina` tablosundan kurulur: `location_id`, `kalite.location_norm()` ile normalleştirilmiş hâli, baştaki sıfırsız hâli ve '-1' eksiz hâli (`ticket.lokasyondan_bina` ile aynı kural), tur raporuyla eklenen binalar dahil. Hedef: 30.09 raporunda **332/332** (bugün CSV'den 287/332). CSV yalnız DB yoksa (CLI) kullanılır.
4. **Sınıflama:** `serit` ve BTK hedefi `operasyon/durum.py:GOREV_TIPI` sözlüğünden gelir (OPERASYON_TASARIM §3.1). `kanal` Satış Kanalı'ndan türetilir. `sorun` alanı §4.5'e göre yazılır. `obek_id` = `obek_mahalle` eşlemesi (birebir önce, sonra ilçenin tamamı).
5. **Fark** (açık BOSS işleri ile dosya karşılaştırılır; anahtar Task No):
   - **yeni:** `INSERT` → durum `yeni` ya da `bakilacak`; `ilk_gorulme = şimdi`; olay `ice_aktarildi`. Aynı `(musteri_no, task_adi)` 7 gün içinde kapanmışsa `tekrar=1`.
   - **mevcut:** Yalnız BOSS alanları ve yer alanları güncellenir. **Bizim alanlarımıza dokunulmaz:** teknisyen, randevu, elle öbek, ticket, not, parça, durum (§3.3 ileri götürme dışında). Değişen alan varsa `degisen` sayılır ve olay `alan` yazılır (yalnız alan adları).
   - **kaybolan** (yalnız `tur=tam`): `kaybolma`, `kapandi` ve `kapanis_nedeni`.
   - **yeniden açılan:** `kaybolma=NULL`, `yeni`, `tekrar=1`.
   - **eksik rapor koruması:** §3.5; `tur` verilmemişse 409 `kismi_rapor_mi`.
6. **BOSS ekibinden atama:** Ekip adı bir `teknik_profil.boss_ekip` ile eşleşiyorsa ve `teknisyen_id` boşsa iş `atandi` olur (`atama_kaynak='boss'`; 15 dk ölçüsüne girmez).
7. **Mahalle sözlüğü:** Raporda görülen mahalleler `kaynak='rapor'` ile eklenir (`INSERT OR IGNORE`).
8. **Kayıt:** `ie_yukleme` satırı sayılarla yazılır ve `COMMIT` edilir. Ham dosya `operasyon/veri/gelen/<sha>.xlsx` olarak 7 gün saklanır.

### 7.2 Sağlamlık kuralları

- Tek işlem: yarıda kalan içe aktarım hiçbir iz bırakmaz.
- **Idempotent:** aynı dosya → değişiklik yok. Aynı işler farklı sırada → 0 yeni, 0 kaybolan; atamalar yerinde kalır. Denetimdeki "ters sırada rapor, 65 parça yanlış müşteride" senaryosu T18.2'de test edilir.
- Rapor biçimi tanınmazsa hiçbir şey yazılmaz; hata Türkçedir.
- Başarım: 1.628 satır < 3 sn (bugün 1,95–3,57 sn). Bu sürede başka isteklerin yanıtı < 200 ms kalır (T18.6).

### 7.3 FOX ve 30 dakikalık senkron

v2'nin kapsamı dışındadır (OPERASYON_TASARIM Faz 1 (FOX) ve Faz 3). Tablolar bunu karşılayacak biçimde kuruldu: `ie_yukleme.dosya_adi`/`tur`, ileride `kaynak` sütunu eklenebilir.

### 7.4 Sunucu yanıt verebilirliği

`yukle`, `tur_raporu_yukle` ve `onemap_yukle` düz `def` olur (ya da `run_in_threadpool` kullanılır). `threading.RLock` olay döngüsünde alınmaz.
Sunucu **tek uvicorn süreci** olarak kalır; çok işçili çalıştırma desteklenmez.

---

## 8. Eşzamanlılık

| Durum | Davranış |
|---|---|
| İki kişi aynı işi aynı anda atıyor | İkincisi 409 `surum_eski` alır; çekmece güncel hâli gösterir ve "Bu iş az önce Ali K.'ya atandı" der |
| Biri rapor yüklerken diğeri atıyor | Yazmalar SQLite `BEGIN IMMEDIATE` ile sıralanır (busy_timeout 15 sn). İçe aktarım bizim alanlarımıza dokunmadığı için atama korunur |
| Eski ekranla öbek düzenleme | `obek_surum` uyuşmazsa 409; ekran öbekleri yeniden çeker. Sessiz diriltme ya da sessiz çalma olmaz |
| Teknik çevrimdışıyken operasyon işi başkasına verdi | Kuyruktaki "Yola çıktım" 409 alır; telefon kartı "Bu iş size ait değil artık" diye kapatır; kuyruktan düşer (hatalı kayıtlar listesine değil) |
| Aynı telefon kaydı iki kez gönderdi | `ux_is_olay_offline` ikincisini yutar, ilk sonuç döner |
| Ekranlar ne sıklıkla tazelenir | İşler 30 sn'de bir `ozet` + görünen liste; `If-None-Match` (ETag = `max(is_emri.guncelleme)` + `obek_surum`); sekme gizliyken durur |

---

## 9. Tasarım sistemi

### 9.1 Token'lar

Hepsi `src/stil/temel.css` içinde tanımlıdır; yönetici CSS'i yerel sabit renk kullanmaz, bu token'ları kullanır.

```css
:root {
  /* Yazı ölçeği (masaüstü / telefonda .telefon kökünde +2 px gövde) */
  --yazi-buyuk: 600 28px/34px var(--yazi-aile);     /* sayfa başlığı */
  --yazi-b2:    600 20px/26px var(--yazi-aile);     /* bölüm başlığı */
  --yazi-b3:    600 17px/22px var(--yazi-aile);     /* kart / çekmece başlığı */
  --yazi-govde: 400 15px/22px var(--yazi-aile);     /* telefonda 17px/24px */
  --yazi-ikincil: 400 13px/18px var(--yazi-aile);
  --yazi-dipnot:  500 12px/16px var(--yazi-aile);   /* EN KÜÇÜK; 10,5 px kalkar */
  --yazi-sayi:  600 32px/36px var(--yazi-aile);     /* Pano kutuları; font-variant-numeric: tabular-nums */
  --yazi-aile: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;

  /* Boşluk: 4'ün katları */
  --b1: 4px; --b2: 8px; --b3: 12px; --b4: 16px; --b5: 20px; --b6: 24px; --b8: 32px; --b12: 48px;

  /* Köşe */
  --kose-k: 8px;   /* çip, girdi */
  --kose:   12px;  /* kart, liste grubu */
  --kose-c: 16px;  /* çekmece üst köşeleri */

  /* Hedef boyu */
  --hedef-masa: 36px;      /* görsel yükseklik; tıklama alanı ≥ 44 px (dolgu ile) */
  --hedef: 56px;           /* telefon (bugünkü değer korunur) */

  /* Renk: bugünkü token'lar korunur; eklenenler */
  --birincil-zemin: #0b63e5;  --birincil-zemin-bas: #0a4fb8;  --birincil-uzeri: #ffffff;
  --zaman-yesil: #0b7a41;  --zaman-amber: #a55a06;  --zaman-kirmizi: #c02a2a;   /* beyazda ≥ 5:1 */
  --odak: 0 0 0 3px color-mix(in srgb, var(--birincil) 40%, transparent);
  --cekmece-golge: 0 8px 40px rgba(16, 24, 40, .18);
  --ortu: rgba(16, 24, 40, .32);
  --hareket: 200ms cubic-bezier(.2, .8, .2, 1);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="acik"]) {
    --birincil-zemin: #2563eb;  --birincil-zemin-bas: #1d4ed8;   /* beyaz yazıyla 5,2:1 (bugünkü #4d95ff 2,98:1) */
    --zaman-yesil: #3ecf82;  --zaman-amber: #f0b45c;  --zaman-kirmizi: #ff6b6b;
    --cekmece-golge: 0 8px 40px rgba(0, 0, 0, .6);
    --ortu: rgba(0, 0, 0, .55);
  }
}
:root[data-tema="koyu"] { /* aynı koyu değerler: elle tema seçimi için */ }
@media (prefers-reduced-motion: reduce) { :root { --hareket: 0ms; } }
```

`index.html`: iki `theme-color` meta etiketi (`media="(prefers-color-scheme: dark)"` → `#0f1319`, açık → `#eff1f5`).

### 9.2 Bileşenler

Yeni klasör: `saha_app/src/tasarim/`. Satışçı uygulamasının örüntüleri (liste kartı, alttan çekmece, iki düğmeli alt çubuk) esas alınır.

| Bileşen | Tanım |
|---|---|
| `Cekmece` (sheet) | Masaüstünde sağdan 440 px, örtüsüz, listenin üzerine kayar; Esc kapatır; odak içeride tutulur. Telefonda alttan tam yükseklik, tutamaklı, aşağı çekince kapanır. Alt kısmında sabit eylem çubuğu (tek birincil) |
| `Onay` | `window.confirm`'ün yerine geçer. Başlık bir soru, tek cümle sonuç, sağda yıkıcı düğme (kırmızı), solda "Vazgeç". Telefonda alt çekmece |
| `Tost` | Altta ortada, 4 sn; "Geri al" varsa 10 sn. Aynı anda en çok 1 |
| `Liste`, `Satir` | Gruplu liste (inset). Satırın solunda nokta ya da baş harf, ortada başlık ve alt yazı, sağda değer ve ›. Yükseklik masaüstünde 44, telefonda 56 px |
| `Segment` | 2–4 seçenek; telefonda taşarsa yatay kayar (taşma yok) |
| `Cip` | Süzgeç çipi (× ile kaldırılır) ve bilgi çipi (soluk) |
| `Rozet` | BTK (kırmızı yumuşak) · Tekrar (mor) · Global/Bayi (gri) · Ticket ⚑ (amber) · elle (gri, italik). Metin 12 px/600 |
| `ZamanEtiketi` | "Kalan 2 s 10 dk" / "Gecikti 5 s" + ⏱; renk `--zaman-*`; `aria-label` tam cümle |
| `SayacSeridi` | Üst şerit; 2–4 sayı; her biri düğme |
| `BosDurum` | Simge + tek cümle + tek eylem (§4.14) |
| `Secici` | Aramalı, gruplu, çoklu seçimli liste (mahalle, teknisyen, öbek). Seçim alt çubukta özetlenir |
| `DilimSecici` | Gün çipleri (Bugün · Yarın · Seç…) + 2 saatlik dilim çipleri; dolu dilim soluk ve "dolu" yazılı |
| `IlkIpucu` | 3 adımlı balon; kişi başına bir kez (`localStorage`, try/catch) |

**Kural:** Görünür alanda en çok **bir** `.dugme-birincil` bulunur. Bunu QA betiği sayar (T11.2).

### 9.3 Açık ve koyu tema

- Her renk çifti (yazı/zemin) iki temada da ≥ 4,5:1 olmalıdır; büyük sayılarda ≥ 3:1. QA betiği hesaplanmış stillerden ölçer.
- Denetimde bulunan hatalar token'la kapanır: `.yon-uyari` kırmızı 1,71:1 → `--kirmizi` üzerine `--kirmizi-yumusak`; amber 1,64:1 → `--amber` üzerine `--amber-yumusak`; birincil düğme 2,98:1 → `--birincil-zemin`; kırmızı menü sayacı → nötr gri hap.
- Öbek renkleri çip zemini olarak kullanılmaz: ad nötr yazı + 8 px renk noktası. Palet iki temada da ayrı tanımlıdır.
- Demo hapı ve harita açıklamasının koyu türevi vardır. Koyu temada varsayılan harita altlığı "Sade"dir.

### 9.4 Masaüstü ve telefon: ayrı tasarlanır, sıkıştırılmaz

| Genişlik | Düzen |
|---|---|
| ≥ 1200 px | Kenar çubuğu 220 px + üç sütun (öbekler 280 · liste esnek · çekmece 440, üste kayar). Klavye kısayolları |
| 1024–1199 | Kenar çubuğu simgelere iner (64 px); öbek listesi 240 px; tablo sütunları birleşir (Yer + Task) |
| 768–1023 (tablet) | Öbek listesi liste başında açılır bir seçiciye döner; çekmece 400 px |
| < 768 (telefon) | Alt sekme çubuğu; 44 px başlık; itme gezinmesi (Öbekler → Öbeğin işleri → İş); çekmece tam ekran; **tablo yok**; iç içe kaydırma yok; harita düğme arkasında; birincil düğme başparmak bölgesinde sabit; aşağı çekerek yenileme |

Ortak kurallar:
- Yatay sayfa kayması hiçbir genişlikte yoktur (`overflow-x: clip` + QA ölçümü).
- Güvenli alanlar (çentik) korunur.
- 393 px'te her metin sarar; hiçbir düğme ekran dışına taşmaz.
- Başlık eylemleri telefonda tek bir "＋" ya da "⋯" düğmesinde toplanır.

### 9.5 Erişilebilirlik

- Renk hiçbir zaman tek başına bilgi taşımaz; yanında simge ve yazı olur.
- Odak halkası (`--odak`) her etkileşimli ögede görünür.
- Çekmece `role="dialog"`, `aria-modal` (telefonda), başlığı `aria-labelledby`.
- Tostlar `aria-live="polite"`.
- Dokunma hedefi masaüstünde ≥ 44 px tıklama alanı, telefonda ≥ 56 px (bugünkü `--hedef`).

---

## 10. Kabul testleri (F1–F22)

Otomasyon araçları:
- **pytest** (`saha/testler`, `operasyon/testler`): `SAHA_DB` kopya, `OPERASYON_OBEK` ve `OPERASYON_VERI` geçici dizin.
- **pw**: `saha_app/qa/v2/kabul.mjs` (playwright-core + paketli Chromium, 127.0.0.1:8090–8099). Ekran görüntüleri `saha_app/qa/v2/kabul/` altına gider (gitignore'da).
- Sentetik raporlar gerçek dosyanın biçimindedir, uydurma verilidir. Gerçek 30.09 dosyası yalnız yerel test sunucusuna yüklenir ve sonuçlarda yalnız sayı raporlanır.

| Test | F | Adımlar | Beklenen | Araç |
|---|---|---|---|---|
| T1.1 | F1 | 3 mahalleli öbekten 1 mahalle `DELETE /api/obek/{id}/mahalle` | GET'te 2 mahalle; aynı yanıtta `ozet.obekler[].acik` o mahallenin iş sayısı kadar azalır; işler öbeksiz → `bakilacak` | pytest |
| T1.2 | F1 | Mahalle ekle, sonra çıkar, sonra geri al | Her adımda sayılar doğru; `obek_olay` 3 satır | pytest |
| T1.3 | F1 | Öbek çekmecesi → ⊖ | 1 sn içinde satır kalkar, sayı güncellenir, sayfa yenilenmez; tostta Geri al | pw 1440 + 393 |
| T2.1 | F2 | Bugün işi olmayan `Bursa/Gürsu/*` ekle | 200; GET'te "ilçenin tamamı"; sonra Gürsu işi içeren sentetik rapor → iş bu öbekte | pytest |
| T2.2 | F2 | `POST /api/mahalle {Bursa, <ilçe>, "Göçmen"}` → öbeğe ekle → "Göçmen Mah." içeren rapor | Sözlükte `elle`; iş bu öbekte; `sorun` NULL | pytest |
| T2.3 | F2 | Seçicide "gursu" yaz | Gürsu grubu ve "İlçenin tamamı" görünür; işi olmayan mahalleler "bugün iş yok" | pw |
| T2.4 | F2 | Başka öbekteki mahalleyi `tasi=false` ile ekle | 409 `baska_obekte`; ekranda taşıma cümlesi; `tasi=true` ile taşınır | pytest + pw |
| T3.1 | F3 | Operasyon: `GET /isler?obek=<Dumlupınar>` | Satır sayısı = `ozet` açık sayısı; her satırda müşteri, adres_kisa, task, durum, kalan_dk, randevu, teknisyen alanı | pytest |
| T3.2 | F3 | Pano → öbeğe tıkla | 1440'ta orta sütunda, 393'te yeni sayfada ≥1 iş satırı; satır → çekmece | pw |
| T4.1 | F4 | Gerçek 30.09 raporu | Lokasyonu dolu 332 işin 332'si binaya bağlı; bakılacak yalnız `il_disi`/`mahalle_yok`/`obeksiz` | pytest (yerel) |
| T4.2 | F4 | Sıfırı düşmüş ve 8 haneye tamamlanmış Lokasyon içeren sentetik satır | İkisi de aynı binaya, `mahalle_kaynak=lokasyon` | pytest |
| T5.1 | F5 | İl "İzmir" olan sentetik iş | `sorun=il_disi`, Bakılacak'ta; `obek_elle_id` verilince öbek listesinde "elle" | pytest |
| T5.2 | F5 | Aynı rapor yeniden yüklenir | `obek_elle_id` korunur | pytest |
| T6.1 | F6 | Her görevle giriş | satisci → `#/bugun`; teknik → `#/islerim`; operasyon → `#/yonetici/isler`; yonetici → `#/yonetici/pano` | pw |
| T6.2 | F6 | Tablo güdümlü: 4 rol × §6.2'deki her uç | Beklenen durum kodları birebir; teknik `/api/bina?limit=1` → 403; teknik `POST /api/ziyaret` → 403; bölgesiz satisci → 0 bina | pytest |
| T6.3 | F6 | Bilinmeyen rol (DB'de elle) | Her uçta 403 | pytest |
| T7.1 | F7 | Operasyon atar → teknik A `GET /api/islerim` | İş A'da var, teknik B'de yok; B `GET /is/{task}` → 404 | pytest |
| T7.2 | F7 | Telefonda (393) teknik → iş kartı → Yola çıktım → Başladım → Bitti (çevrimdışı arada) | Kuyruk bağlantıyla gönderilir; `is_olay` 3 satır, çift yok | pw |
| T8.1 | F8 | Randevu `bit <= bas` | 400; geçerli randevu → İşlerim'de dilim sırası | pytest |
| T8.2 | F8 | Dilim seçilmeden ata | Sıradaki boş dilim yazılır | pytest |
| T9.1 | F9 | İşe ticket bağla → ticket'ı ÇÖZÜLDÜ yap | İş `altyapi` → `yeni`; olay "Ticket çözüldü" | pytest |
| T9.2 | F9 | Binada açık ticket olan işte ata | Birincil düğme "Ticket'a bağla"; toplu atamada `atlanan: binada_ticket` | pytest + pw |
| T10.1 | F10 | Uçtan uca: rapor → yeni → randevu+ata → yolda → sahada → çözüldü → işsiz tam rapor | `kapandi / dogrulandi`; her adımda doğru sahip; zaman damgaları sıralı | pytest |
| T10.2 | F10 | Geçersiz geçişler (yeni → sahada, kapandi → atandi, evde_yok → atandi teyitsiz) | 409 `gecersiz_gecis` | pytest |
| T11.1 | F11 | `GET /api/pano` | Sayılar bağımsız SQL kâhinine eşit | pytest |
| T11.2 | F11 | Her ekranda görünür `.dugme-birincil` sayısı | ≤ 1 | pw |
| T11.3 | F11 | Ekran görüntüsü incelemesi (listeye göre) | Denetimdeki blocker/major bulguların hiçbiri yeniden görülmez | elle + pw |
| T12.1 | F12 | Kişi çekmecesi | 4 görev; Satış'ta bölge zorunlu; Teknik'te öbek ve BOSS ekip alanları | pw |
| T12.2 | F12 | `POST /api/kullanici` rol=teknik, bolge yok | 200; rol=satisci bolge yok → 400 `bolge_gecersiz` | pytest |
| T13.1 | F13 | Ziyareti olan kişiyi sil | 409 `kaydi_var` + sayılar; satır duruyor; 503 değil | pytest |
| T13.2 | F13 | Kaydı olmayan kişiyi sil | 200; satır yok; `sqlite_sequence` düşmedi | pytest |
| T13.3 | F13 | Kendini sil · son yöneticiyi sil/pasife al/düşür | 409 `kendini_silemez` / `son_yonetici` | pytest |
| T13.4 | F13 | Ekip → kişi → Kişiyi sil | Kaydı varsa uyarı + "Pasife al"; yoksa onay → silinir | pw |
| T14.1 | F14 | İlk gün testi: bir çalışma arkadaşı, rehbersiz | İlk işi ≤ 2 dk'da atar (süre ve tıklama not edilir) | elle |
| T14.2 | F14 | İşler → öbek → iş → Ata | ≤ 3 tıklama (toplu atamada 2) | pw |
| T14.3 | F14 | Operasyon ekranlarının metinlerinde yasaklı jargon | "parça", "Süzüleni", "RES HP", "Konum Kaynağı", "kaba" geçmez | pw (DOM metni) |
| T15.1 | F15 | Pano satış kartı | `/api/ozet/gun` toplamlarıyla eşit | pytest |
| T16.1 | F16 | `POST /api/is-emri/is` bayi | `B000001`, `kaynak=bayi`; 24 s saati açılıştan | pytest |
| T16.2 | F16 | Satış Kanalı GLOBAL / DEHA / boş | `kanal` global / bayi / NULL; rozet ve süzgeç | pytest + pw |
| T17.1 | F17 | İçe aktar → 7 dk sonra (sahte saat) ata | `atama_zamani − ilk_gorulme = 7 dk`; `ozet.atama.medyan_dk_bugun` | pytest |
| T17.2 | F17 | Üst şerit | "Atanmayı bekleyen N · en eski M dk" doğru | pw |
| T18.1 | F18 | Aynı dosya iki kez | İkincisi `ayni_dosya`; `is_emri`/`is_olay` satır sayısı değişmez | pytest |
| T18.2 | F18 | Aynı işler ters sırada | 0 yeni, 0 kaybolan; atama ve randevular aynı Task No'larda (denetimdeki yıkıcı senaryo) | pytest (gerçek dosya, yerel) |
| T18.3 | F18 | 30 işi eksik tam rapor, sonra tam dosya | 30 `kapandi`; sonra 30 `yeniden_acilan`, `tekrar=1` | pytest |
| T18.4 | F18 | İşlerin %25'ini içeren dosya | 409 `kismi_rapor_mi`; `tur=kismi` ile yalnız upsert | pytest |
| T18.5 | F18 | Eski `surum` ile yazma | 409 `surum_eski` + güncel kart | pytest |
| T18.6 | F18 | Yükleme sürerken `/api/saglik` | < 200 ms | pytest (uvicorn 127.0.0.1) |
| T19.1 | F19 | 1440×900 · 1366×768 · 393×852 × açık/koyu: Giriş, İşler, İş çekmecesi, Öbek çekmecesi, Mahalle seçici, Bakılacak, Aranacaklar, İşlerim, Ekip, Kişi, Pano | Yatay taşma 0; üst üste binen öge 0; kontrast ≥ 4,5:1; hedef ≥ 44 px; konsol hatası 0; ekran görüntüleri `qa/v2/kabul/` | pw |
| T20.1 | F20 | Canlı yedeğin kopyasında (salt okuma + backup API) v2 açılışı | `saha/yedek/goc/…` var ve doğrulanmış; kullanici 10/10 bütün sütunlarda özet eşit; ziyaret 1.257 eşit; eski tablolar eşit; FK 0; integrity ok; `user_version=4` | pytest |
| T20.2 | F20 | Göçten önce alınmış jetonla `/api/ben` | 200 (telefonlar düşmez) | pytest |
| T20.3 | F20 | İkinci açılış · port doluyken açılış · DROP'tan sonra hata enjeksiyonu | No-op · dokunmadan çıkış · tam geri alma | pytest |
| T20.4 | F20 | `obekler.json` ve `son_yukleme.pkl` sha256 | Açılıştan önce ve sonra eşit; `obek` tablosunda 14 öbek, 120 ref | pytest |
| T21.1 | F21 | Operasyon ve yönetici iş kartı | `musteri_adi` ve `musteri_no` dolu; `musteri_erisim` satırı yazılmış | pytest |
| T21.2 | F21 | Teknik kendi işi / başkasının işi · satisci | Kısa ad / 404 · 403 | pytest |
| T21.3 | F21 | Kapanış + 31 gün (sahte saat) → temizlik | `musteri_adi` ve `adres` NULL; `musteri_no` özet | pytest |
| T22.1 | F22 | `.venv/Scripts/python.exe -m pytest saha/testler operasyon/testler -q` + `node saha_app/qa/v2/kabul.mjs` | Hepsi yeşil (temel çizgi 213 + yeniler); GEREKSINIMLER §F durumları test kimlikleriyle güncel | komut |

---

## 11. Yapım planı: 5 ajan, 2 gün

**Sözleşme bu belgedir** (§5.4 SQL, §6 uçlar ve yükler). İstemci tipleri 0. saatte `saha_app/src/is/tipler.ts` dosyasına A2 tarafından
§6.3'teki JSON'lardan birebir yazılır. Arayüz ajanları sunucu hazır olana kadar `src/api/sahte.ts` üzerinde çalışır.

| Ajan | Gün 1 | Gün 2 | Sahip olduğu dosyalar (çakışma yok) |
|---|---|---|---|
| **A1 · Temel** | `saha/goc.py` (§5.2–5.3), `yedekle.goc_yedegi`, `sunucu.py` sırası + kilit, `ayarlar.ROLLER`, `db.SEMA`, `saha/yetki.py` + §6.4 düzeltmeleri, `/api/ben` dalları, `POST/DELETE /api/kullanici` + `/kayitlar`, lifespan ısınması. Testler: T6.2, T6.3, T12.2, T13.1–3, T20.1–4 | QA: `saha_app/qa/v2/kabul.mjs` matrisi (T19.1, T11.2, T14.3), canlı kopyada yükseltme provası, bulguları ajanlara dağıtma | `saha/goc.py`, `saha/yetki.py`, `saha/sunucu.py`, `saha/yedekle.py`, `saha/api.py` (yalnız yetki ve kullanici bölümleri), `saha/ayarlar.py`, `saha/db.py` (SEMA kullanici), `saha/testler/test_goc_v2.py`, `test_roller_v2.py`, `test_kisi_sil.py`, `saha_app/qa/v2/` |
| **A2 · İş hattı** | `operasyon/depo.py` (DB deposu, §7 içe aktarım + fark), `operasyon/durum.py` (§3 makine, GOREV_TIPI), `operasyon/gorunum.py` (kırpma), `is_emri.py`'de DB'den bina eşleşmesi + yeni sütunlar, `operasyon/api.py` iş uçları (ozet, isler, is, toplu-ata, yukle, excel, aranacak, bayi işi). Testler: T3.1, T4, T5, T7.1, T8, T9.1, T10, T16, T17.1, T18, T21 | `islerim` uçları + `siralama.py`, Pano'nun iş metrikleri, entegrasyon hataları | `operasyon/depo.py`, `durum.py`, `gorunum.py`, `siralama.py`, `api.py`, `is_emri.py`, `operasyon/testler/test_hat_v2.py`, `test_durum.py`, `saha_app/src/is/tipler.ts` |
| **A3 · Öbek, mahalle, pano** | §5.4 tabloları (A1'in göç adımına `v2_tablolar` fonksiyonu olarak verilir), §5.5 tohumlama, `operasyon/obek_db.py`, `operasyon/mahalle.py` (ILCELER, sözlük, arama), `operasyon/api_obek.py` (öbek + mahalle uçları), `operasyon/pano.py` + `GET /api/pano`. Testler: T1.1–2, T2.1–2, T2.4, T11.1, T15.1 | **Teknik İşlerim** ekranı (`saha_app/src/teknik/`), SW'ye `/api/islerim`, çevrimdışı kuyruk bağlantısı (T7.2) | `operasyon/obek_db.py`, `mahalle.py`, `api_obek.py`, `pano.py`, `operasyon/testler/test_obek_db.py`, `test_pano.py`, `saha_app/src/teknik/*`, `saha_app/src/sw.js` (yalnız ağ listesi) |
| **A4 · Operasyon ekranları** | `saha_app/src/yonetici/isler/`: `Isler.tsx` (3 sütun + telefon itme gezinmesi), `IsCekmecesi.tsx`, `TopluAta.tsx`, `RaporYukle.tsx` (fark satırı, eksik rapor sorusu) | `ObekCekmecesi.tsx`, `MahalleSecici.tsx`, `Bakilacak.tsx`, `Aranacak.tsx`, `YeniIs.tsx`, `api.ts`; T1.3, T2.3, T3.2, T9.2, T14.2, T17.2 | `saha_app/src/yonetici/isler/*` |
| **A5 · Kabuk ve sistem** | `src/tasarim/` bileşenleri (§9.2) + token'lar (§9.1) **öğlene kadar** (A4 ve A3 kullanır). `Kabuk.tsx` role göre menü + telefon sekme çubuğu, `App.tsx` ve `oturum.tsx` rol yönlendirmesi, `Giris.tsx` klavye ve 360 px sütun, birim sorusu (§2.5) | `Ekip.tsx` (4 görev, gözden geçir kartı, sil akışı, davet kodu bir kez), `Pano.tsx`, koyu tema düzeltmeleri (§9.3), demo hapı; T6.1, T12.1, T13.4 | `saha_app/src/tasarim/*`, `src/stil/temel.css`, `src/App.tsx`, `src/depo/oturum.tsx`, `src/ekran/Giris.tsx`, `src/yonetici/ortak/Kabuk.tsx`, `src/yonetici/index.tsx`, `src/yonetici/ekran/Ekip.tsx`, `src/yonetici/ekran/Pano.tsx`, `yonetim.css`, `index.html` |

**Birleşme noktaları:**
- Gün 1, 12:00: A5 bileşenleri; A1 göç çerçevesi (A3 tabloları çağırır).
- Gün 1, 17:00: bütün sunucu uçları yeşil test.
- Gün 2, 10:00: 127.0.0.1 test sunucusunda canlı kopya + gerçek rapor ile uçtan uca.
- Gün 2, 16:00: T19 matrisi ve düzeltme turu. "Üret → test et → düzelt → tekrarla" bu noktada kapanır.

**Kurallar (hepsi için):**
- Canlı `saha/saha.db`'ye yazılmaz ve kullanıcının sunucusuna (10.54.3.75:8080) dokunulmaz. Kopya backup API ile, kaynak `mode=ro` açılarak alınır.
- Test sunucuları yalnız 127.0.0.1:8090–8099'da çalışır ve iş bitince kapatılır.
- `obekler.json`'a yazılmaz; git commit yapılmaz.
- Sonuç raporlarında kişisel veri olmaz, yalnız sayı.

**Bitti tanımı:**
- §10'daki bütün otomatik testler yeşil.
- T14.1 ve T11.3 elle yapıldı.
- GEREKSINIMLER §F satırları ✅ ve test kimlikleriyle güncellendi.
- Canlı kopyada yükseltme provası (T20.1) raporu yazıldı.
- Kullanıcıya yükseltme adımı tek sayfa: yedek → yeni sürüm → aç → "Güncelleme tamam" satırı → Ekip'te görevleri gözden geçir.

**Kapsam dışı (bilerek, sonraki faz):**
- FOX dosyaları ve 30 dk senkron.
- KARMA-2'nin tam iki modlu sırası ve "en acil 5 içinden en yakın" kuralı (pilotta).
- SMS.
- Teknik lider ve masa etiketleri.
- Bayi işinin BOSS işiyle birleştirilmesi (P2).
- Ayrıntılı satış hedef yönetimi.
- 3B "Açık iş emri" merceğinin beslenmesi (`is_emri` hazır olduğundan `geometri.py`'ye `acik_is[]` eklemek küçük bir iş; P2).

---

## 12. OPERASYON_TASARIM ile tutarlılık ve bilinçli sapmalar

| Konu | OPERASYON_TASARIM | v2 | Neden |
|---|---|---|---|
| Temas politikası | KARMA-2: aramasız sevk | Aynı. "Randevu" = tahmini varış dilimi, aramadan verilir; "teyitli" isteğe bağlı. Evde yok'tan yeniden atamada teyit zorunlu | F10'daki "operasyon randevular" isteği KARMA-2 ile çelişmesin diye |
| BTK paralel teşhis | 45 dk içinde masa araması | Aranacaklar listesi, vade sayacı, tek dokunuşla sonuç | Kural 4 |
| Altyapı bayrağı | Açık ticket'lı binaya gidilmez | Ata yerine "Ticket'a bağla"; toplu atama atlar | Kural 11 |
| 48 s BTK supabı | Ertesi sabah ilk dalga | Sayaç + süzgeç + toplu atamada öncelik | Kural 6 |
| Kapasite göstergesi | 07:45 formülü | `ozet.kapasite` + Pano kutusu | Kural 5, 15 |
| Durumlar | S0–S6, E1–E6 | §3.1'de bire bir eşleme; S0 ile S1 ekranda "Yeni" olarak birleşir | Sadelik: kullanıcı iki durumu ayırt etmiyor |
| Roller | `teknisyen`, `teknik_lider`, `operasyon` + masa etiketleri | `teknik`, `operasyon`; lider ve etiketler sonra | F12'nin kelimeleri; 2 günlük kapsam |
| Giriş | 3 kutu (Satış · Teknik · Operasyon) | Rol yönlendirir; kutular yalnız çok birimli kişiye bir kez sorulur | İlke 2; C9 yine karşılanır |
| Gizlilik | Ad maskelenir | Operasyon ve yönetici tam görür (kayıtlı, 30 gün); teknik kısa ad; telefon hâlâ yok | F21 (kullanıcının son açık isteği); §13'te onay sorusu |
| Veri modeli | `is_emri`, `is_emri_gecmis`, `obek`, `obek_mahalle`, `gunluk_parca`, `kapasite_gunu`, `masa_gorevi`, `arama`, `dis_islem` | `is_emri`, `is_olay`, `obek`, `obek_mahalle`, `ie_yukleme` (= kaynak_senkron). Parça `is_emri.parca`'da; masa ve arama `is_olay` türleri; kapasite anlık hesaplanır | 2 günde sağlam kurulabilecek en küçük şema; genişlemeye açık, CHECK'siz |
| `entegrasyon.md` §5.3 ticket taslağı | — | Kullanılmaz; bugünkü `ticket` tablosu esastır | Çelişiyor |

---

## 13. Açık sorular (kullanıcı kararı)

1. **Müşteri bilgisi (F21 ve §6.5):** Operasyon ve yönetici müşterinin tam adını ve no'sunu görsün (kayıtlı, kapanıştan 30 gün sonra silinir); teknik yalnız kendi işinde kısa adı ve no'yu görsün; telefon hiç tutulmasın. Onaylıyor musunuz?
2. **Görev adı:** Veritabanı değeri `teknik` olsun mu (OPERASYON_TASARIM'daki `teknisyen` yerine)? "Teknik lider" ayrı görev mi, etiket mi?
3. **Kişilerin görevleri:** Bugün "Yönetici" görünen 8 kişiden hangileri Operasyon, hangileri Teknik? En az bir yönetici kalacak. Göç rolleri değiştirmez; siz Ekip'teki "Gözden geçir" kartından seçeceksiniz.
4. **Kaynak eşlemesi (F16):** Satış Kanalı'nda "GLOBAL" geçen = global, "DEHA" geçen = bayi. Boş olanlar (bugün 53) ne sayılsın?
5. **Tam mahalle listesi (F2):** 17 Bursa + 6 Yalova ilçesinin resmî mahalle listesini (BursaStateList'in eksik ilçeleri ya da TÜİK/UAVT listesi) sağlayabilir misiniz? Sağlanamazsa sistem bilinen 621 mahalle, bina verisi, raporlar ve sizin "Yeni mahalle olarak ekle" dediklerinizle çalışır; "ilçenin tamamı" her ilçede zaten mümkün.
6. **Filtre istisnası (C5 ve C17):** "Kurulum taskı ürememiş" ve "Kurulumsuz …" adlı işler mevcut müşteri kapsamında kalsın mı? Bugün çıkarılıyorlar.
7. **BOSS bağlantısı:** BOSS'ta bir işi ya da müşteriyi doğrudan açan bir adres biçimi var mı? Yoksa "BOSS'ta aç" düğmesi numarayı kopyalar.
8. **Gösterim verisi:** Gerçek 8 hesaba bağlı 1.257 demo ziyaret ve 7 görev yüzünden bu kişiler silinemiyor. Yedek alınarak `demo_temizle` çalıştırılsın mı, yoksa kişiler yalnız pasife mi alınsın?
9. **Randevu dilimleri ve kapasite:** 2 saatlik dilimler 08–20 ve teknisyen başı günde 15 iş varsayılanları uygun mu?
10. **Teknisyenin sahadan erişimi:** VPN + HTTPS gelene kadar İşlerim sabah ofis ağında alınıp çevrimdışı çalışacak; durumlar bağlantı gelince gidecek. Bu ara çözüm kabul mü, yoksa teknisyenler bu sürede yalnız BOSS Mobil mi kullansın?
11. **Satış yönetimi (F15):** Haftalık satış hedefi tek sayı mı, satışçı başına mı? Pano'da başka ne izlenmeli?
