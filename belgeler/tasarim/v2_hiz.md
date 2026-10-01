# İş emri akışı v2 · HIZ tasarımı: "Bir iş emrini 15 dakikada çöz"

*Dehanet EÇM (Bursa + Yalova) · mevcut müşteri iş emirleri · 30.09.2026*
*Kapsam: `docs/GEREKSINIMLER.md` §F'deki F1–F22 satırlarının tamamı. Temel: `docs/OPERASYON_TASARIM.md` (KARMA-2, roller, fazlar).*
*Bu belgede kişisel veri yoktur. Sayılar yalnız toplamdır: 30.09 11:38 raporu, 437 iş.*

---

## 0. Tek sayfada

### 0.1 Hedef

**24 saat tavandır, hedef değildir.** Bir iş emri BOSS'a düştükten sonra en geç **15 dakika içinde** şu dört
şey tamamlanmış olmalı:

- işin sahibi (teknisyen ya da masa) belli,
- iş teknisyenin telefonunda,
- müşteriye verilecek dilim yazılmış,
- BTK işiyse masanın teşhis araması sırada.

Operatör bu 15 dakikada karar vermez, **onaylar**. Kararı sistem önerir: öbek, sonra teknisyen, sonra dilim.
Öneri KARMA-2 kurallarıyla verilir: aramasız sevk, BTK önce, evde olmayanı masa arar.

```
BİR İŞİN İLK 15 DAKİKASI (hedef zaman çizelgesi)

 t0        BOSS'a düştü
 t0+≤30dk  Rapor İndirilenler klasörüne indi → sistem kendi alır (tık yok)       [dış adım: dışa aktarım sıklığı]
 +2 sn     Kontrol + öneri: şerit, öbek, bina, teknisyen, dilim, 24 s / BTK saati  [sistem]
 +≤15 dk   Operatör "O" tuşuna basar (ya da öbeğin bütün önerilerini onaylar)     [ANA HEDEF: gelişten atamaya ≤15 dk]
 +≤2 sn    İş teknisyenin "İşlerim" ekranında, telefon titrer                     [uzun sorgu]
 +≤5 dk    Teknisyen gördü (otomatik alındı bildirimi)
 +≤15 dk   BOSS'a Ekip + dilim girildi ("BOSS'a işlendi" kutusu; sonraki raporda doğrulanır)
 BTK       Masa teşhis araması: hedef 15 dk, vade 45 dk (KARMA-2 kural 4). İş bu sırada saha sırasını kaybetmez
```

Bu zinciri kısaltmak için v2'de on araç var. Her birinin kaldırdığı adım yanında yazılı:

| # | Hız aracı | Kaldırdığı adım |
|---|---|---|
| 1 | **Klasör izleme**: BOSS raporu İndirilenler'e iner inmez içe alınır | Dosyayı bulmak, sürüklemek |
| 2 | **Değişmeyen işe dokunulmaz.** Aynı rapor ikinci kez gelirse hiçbir şey olmaz. Yeni, değişen, kapanan ve yeniden açılan iş tek satırla bildirilir | Listeyi baştan okumak, çift kaydı ayıklamak |
| 3 | **Otomatik kontrol**: bina, mahalle ve öbek sistemde çözülür. Kontrol listesine yalnız gerçek sorunlu iş düşer | Adresi okuyup mahalleyi bulmak |
| 4 | **Öneri**: öbekten teknisyen, teknisyenin sırasından dilim çıkar | "Kime vereyim, hangi saate" kararı |
| 5 | **Tek tuşla onay**: **O**; bütün öbek için **Shift+O** | Form doldurmak |
| 6 | **BOSS ekibini içe alma**: raporda Ekip doluysa iş o kişiye kendiliğinden atanır (bugün 437 işin 258'inde dolu) | Aynı atamayı iki kez yapmak |
| 7 | **Anında teslim**: teknisyenin telefonu 2 saniyede güncellenir | Telefonla haber vermek |
| 8 | **Tek dokunuşla durum**: Yola çıktım → Başladım → Bitti | Teknisyenin rapor yazması |
| 9 | **Canlı saatler**: her satırda atama saati, BTK hedefi ve 24 s saati | "Hangisi acil?" sorusu |
| 10 | **Hız hattı ölçümü**: her adımın medyanı yönetici panosunda | Tıkanan adımı tahminle bulmak |

### 0.2 Bugün nerede duruyoruz (F22)

| Konu | Bugün | v2 sonrası |
|---|---|---|
| Rapor içe alma | Sürükle-bırak. Son yükleme tek bir pickle dosyasında tutuluyor. İşin kimliği Excel'deki satır numarası; her yükleme günün atamalarını siliyor | SQLite, anahtar **Task No**. Yükleme upsert ve fark üretir. Aynı dosya ikinci kez hiçbir şeyi değiştirmez. Klasör izleme |
| Mahalle ve konum | Location Id CSV'den eşleşiyor: 332 işin 287'si bulunuyor | Veritabanından ve normalleştirilmiş anahtarla eşleşiyor: 332/332 |
| Öbek | Mahalle yalnız bugünkü raporda varsa eklenebiliyor. İş olmayan öbek listede görünmüyor. Öbeği açıp içini görmek mümkün değil | Öbek düzenleyici: bütün Bursa + Yalova sözlüğünden ekleme, ilçenin tamamı, çıkarma, taşıma onayı |
| İş listesi | Yok. İşler yalnız sayı ve harita noktası olarak görünüyor | Sevk panosu: müşteri, adres, task, aşama, kalan süre, randevu, teknisyen, ticket |
| Atama, randevu, ticket | Yok | Öneri + onay, dilim seçici, ticket rozeti, durum makinesi |
| Roller | Yalnız satisci ve yonetici. 10 gerçek hesabın 8'i yönetici | Satış · Operasyon · Teknik · Yönetici. Yetki varsayılan olarak kapalı |
| Kişi silme | Yok | Silme var. İşi olan kişide uyarı çıkar ve "Pasife al" önerilir |
| Güncelleme güvenliği | Göçten önce yedek alınmıyor. Göç, port kontrolünden önce çalışıyor | Göçten önce doğrulanmış yedek alınıyor. Tek işlem, doğrulama, `user_version` |
| 24 s saati | Görünmüyor. Aslında 437 işin 288'i 24 saati, 189'u 48 saati aşmış; medyan yaş 41 saat | Her satırda canlı saat, manşette 24 s ve 48 s sayaçları |

### 0.3 Kapsam ve fazlar

| Sürüm | İçerik | Süre |
|---|---|---|
| **v2.0** (bu belge) | §1–§6'nın tamamı: roller, DB'de iş emri, içe aktarım hattı, klasör izleme, öneri motoru (basit KARMA-2 sırası), sevk panosu, öbek düzenleyici, iş çekmecesi, İşlerim, Ekip, Takip paneli, bayi işi, testler | 1–2 gün, 5 paralel ajan (§7) |
| v2.1 | Aşırı yük modunun kotaları (3. ve 4. seçim), masa merdiveninin otomatik zamanlayıcısı, FOX içe alma, kalıcı "öbeği böl" önerisi, köy biçimli mahalle ayrıştırması | 1 hafta |
| Faz 2 (OPERASYON_TASARIM §8) | VPN + HTTPS ile sahadan erişim, 2 öbekte pilot, kontrol grubu | BT'ye bağlı |

KARMA-2 ile uyum: v2.0, OPERASYON_TASARIM'daki **Faz 1**'i (içe al, triyaj, 24 s saati, öbek panosu, kapasite
göstergesi) tamamlar. **Faz 2**'deki teknisyen ekranını da öne çeker, çünkü F7 bunu istiyor. İki fark var:

- Teknisyen ekranı bugünden **ofis ağında** çalışır. Sahadan canlı bağlantı için VPN gerekir; o gelene kadar telefon işleri önbellekten gösterir, basılan düğmeleri kuyruğa alır (§4.7).
- Teknisyenin uygulamayı kullanması **zorunlu değildir**. Uygulamasız teknisyen de atanabilir; o kişi BOSS Mobil'le çalışır. "Gördü" ölçümü yalnız uygulamayı kullananlar için yapılır.

---

## 1. Roller

### 1.1 Dört rol ve ilk ekran

Veritabanındaki değerler: `satisci` · `operasyon` · `teknik` · `yonetici`. Ekrandaki etiketler: **Satış · Operasyon ·
Teknik · Yönetici**.

- `satisci` ve `yonetici` değerleri SQL'e gömülü olduğu için **adları değişmez** (rapor.py, bolgeleme.py, demo.py, kur.py).
- OPERASYON_TASARIM §5.1'deki "teknisyen" rolü burada `teknik` adını alır (F12'deki kelime). "Teknik lider" ve masa etiketleri (BTK, arama, altyapı, lojistik, vardiya) ayrı rol değildir; `kullanici.etiket` alanına yazılır (Faz 2).
- Kullanıcının "Saha" dediği (F6) Satış rolüdür.

| Rol | Masaüstünde ilk ekran | Telefonda ilk ekran | Alt sekmeler (telefon) |
|---|---|---|---|
| **Satış** | Bugün (bugünkü satışçı uygulaması, değişmez) | Bugün | Bugün · Harita · Ben |
| **Operasyon** | **Sevk panosu** `#/operasyon`: öbekler, iş listesi, iş çekmecesi | İşler (Atanacak listesi) | İşler · Öbekler · Masa · Daha |
| **Teknik** | İşlerim (tek sütun, ortada, en fazla 560 px) | **İşlerim** `#/teknik` | İşlerim · Harita · Ben |
| **Yönetici** | **Takip** `#/yonetici/takip`: 24 s uyumu, hız hattı, kapasite, birikim | Takip | Takip · İşler · Ekip · Daha |

Girişte birim sorulmaz (C9'daki üç kutu yok). Rol hesaptan gelir; biri yanlış birime giremez ve ilk günü
başlayan kişi bir karar daha vermek zorunda kalmaz. Yönetici, başlıktaki **Görünüm** menüsünden Operasyon, Teknik ya
da Satış ekranına geçebilir. Seçim cihazda hatırlanır.

### 1.2 Yetki matrisi

Sunucu **varsayılan olarak reddeder**. Her uç, aşağıdaki eylemlerden birini ister. Bir rol listede yoksa istek 403
alır. Yani yeni bir rol eklendiğinde kendiliğinden hiçbir yere erişemez.

| Eylem (kod) | Satış | Operasyon | Teknik | Yönetici |
|---|---|---|---|---|
| `satis.kendi` (liste, ziyaret yazma, kendi bölgesinin haritası) | ✓ | — | — | ✓ |
| `satis.tum` (bütün şehir haritası, kapsama, canlı, görev atama) | — | okur | — | ✓ |
| `bina.oku` (bina kartı) | kendi bölgesi | ✓ | kendi işlerinin binaları | ✓ |
| `is.liste` (bütün iş emirleri) | — | ✓ | — | ✓ |
| `is.kendi` (kendi işleri) | — | ✓ | ✓ | ✓ |
| `is.pii` (müşteri adı, no, tam adres) | — | ✓ | yalnız kendine atanmış **açık** işte | ✓ |
| `is.ata` (atama, randevu, öbeğe taşıma, not, ticket bağlama, bayi işi açma) | — | ✓ | — | ✓ |
| `is.gecis.saha` (yolda, sahada, bitti, evde yok) | — | ✓ (düzeltme) | kendi işinde | ✓ |
| `is.ice_aktar` (rapor yükleme, kısmi onay, klasör izleme durumu) | — | ✓ | — | ✓ |
| `is.izleme_ayar` (izlenen klasörü değiştirme) | — | — | — | ✓ |
| `obek.duzenle` (öbek ve mahalle sözlüğü) | — | ✓ | — | ✓ |
| `ticket.yonet` | — | ✓ | — (işindeki ticket'ı okur) | ✓ |
| `ekip.yonet` (kişi ekleme, silme, rol, PIN) | — | — | — | ✓ |
| `veri.yonet` (bölge planlayıcı, tur raporu, veri kalitesi) | — | — | — | ✓ |
| `takip.oku` (Takip paneli) | — | kendi özeti | — | ✓ |

### 1.3 Müşteri kişisel verisi (F21)

OPERASYON_TASARIM §6.5'te "müşteri adı maskelenir" deniyordu. F21 ise "operasyon müşteri bilgilerine erişebilmeli ki
randevu alabilsin, ekibe atayabilsin" diyor. v2 bu kuralı **rol tabanlı erişimle** değiştirir:

| Alan | Satış | Operasyon | Teknik | Yönetici | Saklama |
|---|---|---|---|---|---|
| Müşteri adı | ✗ | ✓ | kendi açık işinde | ✓ | Kapanıştan 30 gün sonra silinir (`NULL`) |
| Müşteri no | ✗ | ✓ (tek dokunuşla kopyala → BOSS/Maya'da ara) | kendi açık işinde | ✓ | Aynı |
| Tam adres | ✗ | ✓ | kendi işinde | ✓ | Aynı |
| Telefon | Sistemde **yok** (BOSS dışa aktarımında zaten boş). Arama BOSS/Maya'dan yapılır | | | | — |
| Ham BOSS dosyası | — | — | — | — | `operasyon/veri/ham/`; 7 gün sonra silinir |

- **Görüntüleme kaydı:** Bir iş çekmecesini açmak ya da müşteri numarasını kopyalamak `erisim_kaydi` tablosuna bir satır yazar. Aynı kişi, aynı iş ve aynı gün için yalnız bir satır yazılır. Yönetici bu kaydı Takip → Sistem kartında görür.
- **Excel çıktısı** kişisel veri içerir. Yalnız operasyon ve yönetici alabilir; her indirme kaydedilir.
- **Liste yanıtlarında** kişisel veri alanları role göre sunucuda çıkarılır. İstemci tarafında gizlemek yeterli sayılmaz.

### 1.4 Mevcut kullanıcılar yeni rolünü nasıl alır

1. Göç (§4.1) hiçbir rolü değiştirmez. 8 yönetici yönetici, 2 satışçı satışçı olarak kalır. PIN'lere ve oturumlara dokunulmaz; açık telefonlar oturumda kalır.
2. Göçten sonra yönetici Ekip ekranında bir kez **"Görevleri gözden geçirin"** kartını görür. Kartta rolü `yonetici` olan her kişi için bir satır ve dört seçenekli bir düğme (Satış · Operasyon · Teknik · Yönetici) bulunur; en altta **Kaydet** vardır.
3. Rolü değişen kişinin oturumu düşer, çünkü `oturum_no` artar. Kişi aynı telefon ve PIN ile yeniden girer ve yeni rolünün ekranında açılır. Kart bunu önceden yazar: "Bu kişiler bir kez yeniden giriş yapacak, PIN'leri aynı".
4. Korumalar:
   - Kişi kendi rolünü düşüremez.
   - Son aktif yönetici düşürülemez, pasife alınamaz ve silinemez (409 `son_yonetici`).
5. Teknik kişi için iki ek alan vardır:
   - **BOSS'taki ekip adı** (`boss_ekip`): BOSS'taki atamaları içe almak ve "BOSS'a işlendi mi?" doğrulaması için.
   - **Ev öbekleri**: öneri bunlardan başlar.

   Bugünkü raporda Ekip'i dolu 258 iş var. Panoda **"Eşleşmemiş BOSS ekibi (k)"** çipi çıkar. Operatör ekip adını bir kişiyle eşleştirdiğinde o ekibin bütün işleri tek hamlede "Atandı" olur.

### 1.5 Sunucuda kapatılan açıklar

Denetimin bulduğu açık şuydu: bölgesi NULL olan yeni bir rol şehrin tamamını görüyor ve her binaya ziyaret yazabiliyor.
Bu açık v2'de kapanır:

- **`saha/yetki.py` (yeni).** `YETKI: dict[str, frozenset[str]]` (§1.2) ve `yetki_gerekli(*eylemler)` bağımlılık fabrikası. `yonetici()` bağımlılığı `yetki_gerekli('ekip.yonet')` gibi eşdeğerlerle değiştirilir.
- **`_bolge_kontrol`** yalnız açıkça izin verilenler için çalışır:
  - yönetici ve operasyon → `None` (hepsi);
  - satisci → kendi bölgesi; bölge NULL ise 403 `bolgesiz`;
  - teknik ve bilinmeyen rol → 403 `yasak`.
- **Ziyaret yazma** (`_ziyaret_isle`), **`bina_detay`** ve **`_bina_yetkili`** "yalnız satisci'yi kısıtla" mantığından "yalnız izinliyi geçir" mantığına döner. Teknik rol bina kartını yalnız kendisine atanmış açık işin binası için alır.
- **`/api/ben`** her rol için kendi dalını döndürür. Yanıta `ana_ekran` ('satis' | 'operasyon' | 'teknik' | 'yonetici') ve `yetkiler: string[]` eklenir.
- **İş emri yönlendiricisi:** `Depends(yonetici)` yerine her uca kendi eylemi.
- **Davet kodu** Ekip listesinde gösterilmez; yalnız üretildiği anda bir kez gösterilir. 48 saat geçerlidir (`davet_zamani`). Listede "Davet bekliyor" yazar.

---

## 2. İş emrinin yaşam döngüsü

### 2.1 Aşamalar

Veritabanında `is_emri.asama` alanında durur. **CHECK kısıtı konmaz.** Geçerli değerler `operasyon/v2/motor.py`
içinde `ASAMALAR` olarak tanımlıdır. Böylece ileride yeni bir değer eklemek tablo yeniden kurmayı gerektirmez.

| Kod | Ekranda | Karşılığı (OPERASYON_TASARIM §3.2) | Sahibi | Açık mı? |
|---|---|---|---|---|
| `gelen` | Yeni | S0 Geldi | Sistem (≤2 sn içinde bir sonraki aşamaya geçer) | ✓ |
| `kontrol` | Kontrol | S1 (bağlanamayan iş triyaja düşer) | Operasyon | ✓ |
| `atanacak` | Atanacak | S1 Sınıflandı + öneri hazır | Operasyon (onaylar) | ✓ |
| `masada` | Masada | Masa şeridi: Kanal, Cihaz İade | Operasyon (`sahip_id`) | ✓ |
| `atandi` | Atandı | S2 Kuyrukta | Teknisyen | ✓ |
| `yolda` | Yolda | S3 | Teknisyen | ✓ |
| `sahada` | Sahada | S4 | Teknisyen | ✓ |
| `bitti` | Bitti | S5 (BOSS'tan düşmesi bekleniyor) | Sistem | ✓ (bizim için çözüldü) |
| `kapandi` | Kapandı | S6 Doğrulandı | — | ✗ |
| `evde_yok` | Evde yok | E1 | Operasyon (merdiven) | ✓ |
| `aski` | Askıda | E2 | Operasyon (uyanma zorunlu) | ✓ |
| `altyapi` | Altyapı | E3 (ticket bağlı) | Operasyon / altyapı | ✓ |
| `merkezde` | Merkezde | BOSS "Merkeze gönderildi" | Operasyon | ✓ |
| `iptal` | İptal | E5 (yalnız bayi işi ya da mükerrer) | — | ✗ |
| `birlesti` | (görünmez) | Bayi işi BOSS işiyle birleşti | — | ✗ |

"Açık" sayılan iş: `asama NOT IN ('kapandi','iptal','birlesti')`. 24 saat uyumu şu an üzerinden ölçülür:
`bitti_zamani`, o yoksa `kapanis` (BOSS'tan düşme anı).

### 2.2 Geçişler: kim, ne zaman

Her geçiş `is_olay` tablosuna bir satır yazar (eski aşama, yeni aşama, kişi, zaman) ve ilgili zaman damgasını doldurur.
Geçersiz bir geçiş 409 `gecersiz_gecis` döndürür ve mesajında izinli geçişleri Türkçe listeler.

| Geçiş | Kim | Koşul | Damga |
|---|---|---|---|
| `gelen → atanacak` | Sistem | Öbek ve teknisyen önerisi bulundu (SAHA/BTK şeridi) | `hazir_zamani` |
| `gelen → masada` | Sistem | MASA ya da LOJİSTİK şeridi: iş otomatik olarak masa kuyruğuna gider | `hazir_zamani` |
| `gelen → kontrol` | Sistem | Öbek yok · il bölge dışı · mahalle yok | — |
| `gelen → atandi` | Sistem | BOSS Ekip dolu ve bilinen bir teknisyenle eşleşiyor (`kaynak='boss'`) | `atama_zamani` |
| `gelen → altyapi` | Sistem | Binada açık SİNYAL / EK SP / GÜZERGAH / ALTYAPI ticket'ı var (KARMA-2 kural 11) | — |
| `kontrol → atanacak` | Operasyon | İş elle bir öbeğe taşındı ya da mahallesi seçildi (F5) | `hazir_zamani` |
| `atanacak → atandi` | Operasyon | Öneri onaylandı ya da teknisyen ve dilim elle seçildi | `atama_zamani` |
| `atandi → atandi` | Operasyon | Başka teknisyene verildi ya da dilim değişti; olay yazılır | — |
| `atandi` (görüldü) | Teknik (otomatik) | İş, telefonda ekrana ilk girdiğinde | `gorulme_zamani` |
| `atandi → yolda` | Teknik (kendi işi), operasyon | "Yola çıktım" | `yolda_zamani` |
| `yolda → sahada` | Teknik | "Başladım" | `sahada_zamani` |
| `sahada/yolda → bitti` | Teknik | Sonuç "Çözüldü"; **"Evde miydi?"** yanıtı zorunlu (kural 17) | `bitti_zamani` |
| `atandi/yolda/sahada → evde_yok` | Teknik | Kapıda 10 dk beklendi, 2 arama yapıldı (kural 8) | `deneme+1`, `uyanma = şimdi + 60 dk` |
| `evde_yok → atandi` | Operasyon | Müşteriye ulaşıldı, **teyitli** dilim alındı | `atama_zamani` (yeniden) |
| `evde_yok → aski` | Operasyon | 3 deneme doldu ya da müşteri başka gün istedi; uyanma zorunlu (BTK ≤ 1 gün, diğer ≤ 3 gün, müşteri isteği ≤ 7 gün) | — |
| `aski → atanacak` | Sistem (uyanma geldi), operasyon | — | `hazir_zamani` |
| açık iş `→ altyapi` | Teknik ("Altyapı sorunu"), operasyon, sistem | Bir ticket bağlanmış olmalı | — |
| `altyapi → atanacak` | Sistem (bağlı ticket ÇÖZÜLDÜ), operasyon | — | `hazir_zamani` |
| `atanacak/atandi/masada → bitti` | Operasyon | Telefonda çözüldü: canlı test yapıldı (kural 4a ve 13) | `bitti_zamani` |
| `masada → atanacak` | Operasyon | "Sahaya gitmeli" | — |
| açık iş `→ iptal` | Operasyon, yönetici | Yalnız bayi işi ya da mükerrer; neden zorunlu | `kapanis` |
| açık iş `→ kapandi` | Sistem | Tam BOSS raporunda artık yok | `kapanis`, `kapanis_nedeni` |
| `kapandi → gelen` | Sistem | BOSS'ta yeniden göründü | `yeniden_acilma+1` |
| Geri al | Geçişi yapan kişi | Son geçişinden sonraki 10 dk içinde, bir kez | Olay yazılır |

Teknik rol yalnız kendi işinde ve yalnız saha geçişlerini yapabilir. Aynı işe ikinci kez habersiz teknisyen
gönderilmez (kural 8): `evde_yok` durumundan `atandi`ya dönüş yalnız `randevu_tur='teyitli'` ile yapılabilir.

### 2.3 BOSS aynası, BOSS'ta kapanma ve yeniden açılma

- **Ayna alanları.** BOSS'tan gelen alanlar (`boss_*`) her içe aktarımda yenilenir. Bizim alanlarımız (aşama, teknisyen, randevu, elle öbek, elle mahalle, not) **asla ezilmez**.
- **BOSS durumunun aşamaya yansıması.** BOSS durumu bizim aşamamızı yalnız iş henüz bizim elimize girmemişse değiştirir, yani `gelen`, `kontrol` ya da `atanacak` aşamasındaysa:
  - "Askıya alındı" → `aski` (uyanma yoksa "uyanma girilmeli" rozeti)
  - "Merkeze gönderildi" → `merkezde`
  - "Başlandı" / "Konum Paylaşıldı" + eşleşen Ekip → `sahada` / `yolda`

  Elimizdeki işte BOSS'la çelişki olursa bir rozet çıkar ("BOSS: Askıda"). Bu kayıt çelişkisi Takip'te sayılır.
- **Kapanma.** Tam bir raporda bulunmayan açık BOSS işi `kapandi` olur, `kapanis = raporun anı`. Bizim aşamamız `bitti` değilse `kapanis_nedeni='boss_dustu_bizsiz'` yazılır: iş BOSS'ta bizim akışımız dışında kapanmış demektir ve raporda ayrıca sayılır.
- **Yeniden açılma.** Kapanmış bir Task No yeniden gelirse iş `gelen` aşamasına döner, `yeniden_acilma` bir artar ve "Yeniden açıldı" rozeti alır. Önceki teknisyen öneride öne alınır.
- **Tekrar arıza.** Aynı `musteri_no` ve aynı `task_adi` 7 gün içinde kapanmış bir işte görülürse "Tekrar" rozeti çıkar (kural 13: telefonla kapatma yasaktır, iş kıdemli teknisyene gider). Bu kontrol `ix_is_musteri` indeksiyle yapılır.

### 2.4 Şerit ve BTK hızlı şeridi

Şerit `task_adi` alanından kodla çıkarılır (`motor.SERITLER`); bu v2'de bir tablo değildir.

| Şerit | Task adları (BOSS) | Hedef (`hedef_saat`) | Öneri |
|---|---|---|---|
| **BTK** | Bağlantı Problemi (12), Arama Problemi (12), TV+ Arıza (6), Doping Arıza (24) | FOX hedefi; söz 24 s | Öbeğin teknisyeni. Masa teşhis bayrağı açılır, vade `ilk_gorulme + 45 dk`, hedef 15 dk |
| **SAHA** | Modem, Superbox, STB değişikliği; Teknik Servis Ücretlendirme; Evrak; bilinmeyen tipler | 24 | Öbeğin teknisyeni (aramasız sevk, kural 3) |
| **MASA** | Kanal Şikayeti, Soru-Cevap | 24 (aynı gün) | Masa: aynı gün 3 deneme (kural 12) |
| **LOJİSTİK** | Cihaz İade, Cihaz Geri Alım, Türksat iade | 24–48 | Masa kontrolü; gerekirse "dolgu durağı" |

Bilinmeyen task adı SAHA şeridine düşer ve bir "Tip?" rozeti alır. İşi bekletmez.

BTK işlerinin hızlı şeridi şöyle işler:

1. **Önce BTK.** Atanacak listesinde ve teknisyenin sırasında BTK her zaman önce gelir.
2. **Paralel teşhis.** Masa teşhis aramasını paralel yapar. Arama işin atanmasını beklemez; masa arıyor diye iş de beklemez. Sonuç kodları (kural 4):
   - `duzeldi`: canlı test yapıldı → iş `bitti`, saha ziyareti iptal;
   - `evde`: 3 saatlik teyitli pencere, iş sırada öne alınır;
   - `baska_gun`: müşterinin seçtiği dilim yazılır;
   - `ulasilamadi`: hiçbir şey değişmez;
   - `kotu_gecmis`: önceki işinde ulaşılamamış müşteri; arama yapılmaz (kural 14).
3. **48 saati aşan BTK** (kural 6): Takip'te kırmızı sayaçta görünür. Ertesi sabahın "İlk dalga" listesine isimli bir sahiple (`sahip_id`) yazılır.

### 2.5 Saatler

| Saat | Başlangıç → bitiş | Hedef | Nerede görünür |
|---|---|---|---|
| **Atama saati (15 dk)** | `ilk_gorulme` → `atama_zamani` | 15 dk. 10. dakikada sarı, 15'te kırmızı | Atanacak listesinin her satırı ("Atama: 6 dk") |
| **24 s tavanı** | `acilis` (BOSS Task Başlangıç) → `bitti_zamani` / `kapanis` | 24 saat, `son24` | Her satır ve iş çekmecesi |
| **BTK hedefi** | `acilis` → `hedef` (6 / 12 / 24 s) | FOX hedefi | BTK satırlarında ana saat budur |
| **Teşhis** (BTK) | `ilk_gorulme` → ilk masa araması | Hedef 15 dk, vade 45 dk | Masa sekmesi |
| **Yol** | `yolda_zamani` → `sahada_zamani` | 60 dk (BTK 45) | Teknisyen ve iş çekmecesi |
| **Saha** | `sahada_zamani` → `bitti_zamani` | 120 dk (BTK 90) | Aynı |
| **BOSS'a işleme** | `atama_zamani` → `boss_islendi` | 15 dk | "BOSS'a işlenecek" çipi |
| **Kapanış doğrulama** | `bitti_zamani` → `kapanis` | Sonraki içe aktarım | Takip → hız hattı |

**Renk kuralı** (§3.6'daki eskalasyon eşiği): geçen süre hedefin %50'sinin altındaysa yeşil, %50–80 arasındaysa sarı,
%80'in üstündeyse kırmızı. Aşıldıysa kalın kırmızı "Gecikti 17 sa" yazar. Saat istisnada da durmaz (§1.1).

**Söz günü** (§3.3 kesim kuralı) iş çekmecesinde yazar. İş 00–12 arasında geldiyse "bugün", 12–17 arasında geldiyse
"yarın 12:00", 17–24 arasında geldiyse "yarın 17:00".

**15 dk metriğinin kapsamı:** yalnız `acilis ≥ sistemin ilk içe aktarım anı` olan işler, yani sistem çalışırken
doğmuş işler. Bu işlerden BOSS'tan atanmış gelenler (`kaynak='boss'`) de metriğe girmez. Devralınan birikim 24 s
ölçümüne girer, 15 dk ölçümüne girmez.

### 2.6 Otomatik kontrol ve öneri motoru

`motor.oneri_hesapla(conn, task_nolar)` her içe aktarımdan, her öbek değişikliğinden ve her atamadan sonra çalışır.
437 iş için süre 200 ms'nin altında kalmalı.

1. **Öbek.** Önce `obek_elle` alanı, sonra `(il_k, ilce_k, mahalle_k)`, sonra `(il_k, ilce_k, '*')` denenir. Hiçbiri bulunmazsa iş `kontrol` aşamasına düşer ve nedeni `obek_yok` olur.
2. **Kontrol nedenleri** yalnız gerçek sorunlardır: `il_disi`, `mahalle_yok`, `obek_yok`.
   - "Konum yaklaşık" (ilçe ya da mahalle merkezi) **kontrol nedeni değildir.** Öbek mahalleden geldiği için sevki etkilemez. Yalnız bir rozet ve "Konum belirsiz (n)" süzgeci olarak görünür.
3. **Teknisyen** (aday alanı, kural 7). Sırayla denenir:
   - bugün bu öbek bölündüyse işin düştüğü parçanın teknisyeni;
   - öbeğin ev teknisyeni (`obek.teknisyen_id`), sonra yedeği;
   - 3 km içinde işi olan ve kapasitesi dolmamış teknisyen;
   - 10 km içindeki teknisyen.

   Kapasite ölçüsü: bugün atanmış iş sayısı < `kullanici.kapasite` (varsayılan 15). "Bugün yok" işaretli teknisyen (`teknik_yoklama`) atlanır. Önerinin nedeni tek satırla yazılır: "Görükle öbeğinin teknisyeni · bugün 9/15".
4. **Sıra** (v2.0'daki basit KARMA-2):
   - teyitli dilimi olan iş kendi penceresine konur;
   - ardından BTK işleri, `hedef` alanına göre artan sırayla;
   - sonra diğer işler, yine `hedef` sırasıyla (en eski önce);
   - her adımda "en acil 5 aday içinden bir önceki durağa en yakın olanı" seçilir (`yakinlik.mesafe_km`).

   Aşırı yük modunun kotaları (her 3. ve 4. seçim) v2.1'dedir. Mod yine de hesaplanır ve gösterilir (§3.10).
5. **Dilim.** Teknisyenin gün planında işin sırası p olsun. Tahmini varış = `max(gün başlangıcı 08:30, şimdi) + p × ortalama iş süresi` (`ayar.is_suresi_dk`, varsayılan 32 = 480/15). Bu an 2 saatlik pencereye yuvarlanır (09–11, 11–13, 13–15, 15–17, 17–19). Pencere 19:00'u geçerse ertesi gün 09–11 önerilir. Varsayılan 11:00 damgası **yasaktır** (kural 3).
6. **Altyapı.** İşin binasında açık bir ticket varsa iş `altyapi` aşamasına geçer ve ticket otomatik bağlanır (`ticket_is`). İşe teknisyen önerilmez.

### 2.7 Ticket bayrağı (F9)

- **Otomatik.** Bina → açık ticket'lar (`ticket.bina_serial` ya da `location_id`, `ACIK_DURUMLAR`). İşin satırında konu, durum ve yaşıyla bir rozet görünür: "SİNYAL · AÇIK · 3 g".
- **Elle.** İş çekmecesinde **Ticket bağla** (binanın ticket'ları arasından seçilir) ve **Ticket aç** düğmeleri vardır. Ticket aç, bugünkü "Yeni ticket" akışını açar; bina ve konu önceden dolu gelir, metin hazırdır. İki işlem de `ticket_is` satırı yazar ve `is_olay` tablosunda `ticket_baglandi` olarak görünür.
- **Takip.** Ticket'ın durumu ÇÖZÜLDÜ ya da KAPATILDI olunca bağlı işler `altyapi` → `atanacak` geçişini yapar ve bir "Ticket çözüldü" rozeti alır (KARMA-2 §3.6 adım 5). Bu kontrol ticket güncelleme ucunda yapılır.
- **Teknisyenin gördüğü:** iş kartında "Binada açık SİNYAL ticket'ı var" satırı. Böyle bir işe teknisyen zaten gönderilmez.

### 2.8 İki kaynak: dış kanal ve bayi (F16)

- **`kaynak`** işin sisteme nereden girdiğini söyler: `boss` (rapordan) ya da `bayi` (Dehanet'in kendi açtığı iş).
- **`kanal`** işin kime ait olduğunu söyler; BOSS "Satış Kanalı" sütunundan türetilir. İçinde "GLOBAL" geçiyorsa `global` (dış kanal), "DEHA" ya da "DEHANET" geçiyorsa `bayi`, boşsa `NULL` olur. Bugünkü dağılım: GLOBAL 243, DEHA 37, boş 53. **Bu eşleme kullanıcı onayı bekliyor** (Açık soru 4).
- **Bayi işi açma:** Sevk panosunda "Yeni iş emri" düğmesi (§3.12).
  - İşin kimliği `B-000001` biçimindedir (`sqlite_sequence` benzeri bir sayaç `ayar.bayi_is_sayac` alanında tutulur).
  - Aşaması hemen `gelen` olur ve öneri motorundan geçer.
  - 24 saat saati açıldığı andan başlar.
- **Birleştirme:** Sonraki bir BOSS raporunda aynı `musteri_no` ile ve aynı normalleştirilmiş `task_adi` ile ±48 saat içinde açılmış bir iş gelirse:
  - tek aday varsa iki kayıt kendiliğinden birleşir: bizim alanlarımız BOSS satırına taşınır, bayi satırı `birlesti` olur ve `bagli_task_no` alanına BOSS Task No yazılır;
  - birden çok aday varsa iş çekmecesinde "BOSS'ta göründü mü?" seçimi çıkar.

### 2.9 Hız hattı: neyi, nasıl ölçüyoruz (F17)

Her adım `is_emri` tablosundaki zaman damgalarından hesaplanır. Takip paneli bugün ve son 7 gün için medyan, p90,
iş sayısı ve "hedefte" oranını gösterir.

| Adım | Hesap | Hedef |
|---|---|---|
| BOSS → sistem | `ilk_gorulme − acilis` (yalnız sistem çalışırken doğan işler) | ≤ 30 dk; dışa aktarım sıklığına bağlı |
| Sistem → öneri | `hazir_zamani − ilk_gorulme` | ≤ 1 dk |
| **Öneri → atama** | `atama_zamani − ilk_gorulme` | **≤ 15 dk (ana gösterge)** |
| Atama → görüldü | `gorulme_zamani − atama_zamani` | ≤ 5 dk (yalnız uygulamayı kullanan teknisyen) |
| Atama → BOSS'a işlendi | `boss_islendi − atama_zamani` | ≤ 15 dk |
| Atama → yolda | `yolda_zamani − atama_zamani` | Dilime göre |
| Yolda → sahada | | ≤ 60 dk (BTK 45) |
| Sahada → bitti | | ≤ 120 dk (BTK 90) |
| Bitti → BOSS'ta kapandı | `kapanis − bitti_zamani` | Sonraki içe aktarım |
| **Uçtan uca** | `bitti_zamani − acilis` | 24 s tavanı; BTK için FOX hedefi |

Rapor bayatlığı da aynı ölçüye bağlanır. Mesai saatinde son içe aktarımın üzerinden 30 dakika geçmişse manşetteki
"Son rapor" yazısı sarıya, 60 dakika geçmişse kırmızıya döner ve yanında "BOSS'tan yeni rapor al" yazar.

---

## 3. Ekranlar

### 3.0 Ortak ilkeler (F11, F14, F19)

1. **Her ekranda bir birincil eylem vardır.** Mavi dolgulu düğme yalnız o eylemdir; diğerleri metin ya da çerçeveli düğmedir.
2. **Sayfa içinde iç içe kaydırma yoktur.** Bir ekranda tek liste kayar. Telefonda sayfalar iterek açılır (öbek listesi → öbeğin işleri → iş).
3. **Tarayıcının `window.confirm` kutusu kullanılmaz.** Onay bir çekmecede (sheet) sorulur. Geri alınabilen işlemden sonra 10 saniyelik "Geri al" bildirimi çıkar.
4. **Her ekranın başlığının altında bir cümle vardır**: "Bu ekranda ne yaparım?". Kapatılabilir; cihaz bunu hatırlar. Boş ekran da her zaman bir sonraki adımı söyler.
5. **Uygulama kendi iç sözcüklerini kullanmaz.** Sözlük §5.5'te.
6. **Gösterim verisi uyarısı** yalnız demo ziyaretlerini kullanan satış ekranlarında görünür; orada da küçük bir hap olarak. İş emri, öbek, ekip ve takip ekranlarında görünmez.

### 3.1 Operasyon · Sevk panosu (masaüstü ≥ 1200 px)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Sevk panosu        Açık 437 · 24 s'i aşan 288 · 48 s'i aşan BTK 41 · Atanacak 12        Son rapor 11:38 · 7 dk önce │
│                                                                              [Yeni iş emri]  [Rapor yükle]  │
├───────────────────────────┬──────────────────────────────────────────────────────────────────────────────┤
│ ÖBEKLER             [+ ]  │  [Atanacak 12] [Masada 9] [Sahada 71] [Bekleyen 38] [Tümü]    🔍 Ara…   [Süz]  │
│ ─────────────────────────  │  Görükle ✕   BTK ✕                                                           │
│ ● Görükle          31     │  ──────────────────────────────────────────────────────────────────────────── │
│   geciken 9 · BTK 14 · HK │  BTK  Bağlantı Problemi  (müşteri) Görükle · X Sitesi   Kalan 3 sa 10 dk    │
│ ● Nilüfer Dumlupınar 12   │       Atama: 6 dk        Öneri: MK · 11–13            [Onayla  O]            │
│   geciken 2 · BTK 6 · MK  │  ──────────────────────────────────────────────────────────────────────────── │
│ ● 19 Mayıs·Yüzüncüyıl 44  │  BTK  TV+ Arıza          …           Görükle · 12. Sk      Kalan 1 sa 40 dk    │
│ ◌ Gürsu             0     │       Ticket: SİNYAL · AÇIK → Altyapı                                         │
│ ─────────────────────────  │  ──────────────────────────────────────────────────────────────────────────── │
│ ⚠ Kontrol bekleyen   3    │       Modem Değişikliği  …           Nilüfer · Dumlupınar  Kalan 19 sa        │
│ ⓘ Konum belirsiz    50    │  …                                                                           │
│ ⓘ Eşleşmemiş BOSS ekibi 4 │                                                        [Liste | Harita]      │
└───────────────────────────┴──────────────────────────────────────────────────────────────────────────────┘
                                                          (iş seçilince sağdan 440 px'lik iş çekmecesi açılır)
```

**Sol sütun: Öbekler (280 px, sabit).**

- Her satırda öbek adı ve açık iş sayısı yer alır. Alt satırda "geciken · BTK" sayıları ve teknisyenin baş harfleri görünür.
- İşi olmayan öbek de listededir; soluk görünür (bugün örneğin Gürsu).
- En altta üç bilgi satırı bulunur: **Kontrol bekleyen**, **Konum belirsiz**, **Eşleşmemiş BOSS ekibi**. Her biri tıklanınca listeyi süzer.
- Öbeğe tıklamak listeyi o öbeğe süzer ve listenin üstünde **öbek başlık kartı** açar. Kartta şunlar vardır:
  - ad ve teknisyen;
  - **Düzenle** (öbek düzenleyici, §3.5);
  - **Ekiplere dağıt** (bugünkü Böl, §3.6);
  - birincil düğme **Önerileri onayla (n)** (**Shift+O**).

**Orta sütun: iş listesi.**

- Üstte segmentler: **Atanacak** (kontrol + atanacak) · **Masada** · **Sahada** (atandı + yolda + sahada) · **Bekleyen** (evde yok, askı, altyapı, merkezde) · **Tümü**.
- **Varsayılan sıralama aciliyettir.** Önce kontrol işleri, sonra BTK işleri `hedef`e göre artan sırayla, sonra diğerleri `hedef`e göre. Her satırın ilk sırasında en acil iş durur.
- Satır iki satırlıktır:
  - 1. satır: şerit rozeti, task, müşteri adı (operasyon ve yönetici görür), "mahalle · bina", **kalan süre** (renkli, tabular rakam).
  - 2. satır: atama saati ya da aşama, randevu, teknisyen (öneriyse gri ve eğik), rozetler (Ticket, Bayi, Yeniden açıldı, Tekrar, Konum yaklaşık, BOSS'a işlenecek). En sağda satırın tek eylemi durur: **Onayla** / **Ata** / **Aç**.
- Arama; Task No, müşteri no, müşteri adı, mahalle ve bina adında çalışır.
- **Süz** düğmesi ilçe, şerit, task tipi, aşama, teknisyen, "Konum belirsiz" ve "BOSS'a işlenecek" seçeneklerini açar. Etkin süzgeçler aramanın yanında kaldırılabilir çipler olarak görünür. Bugünkü 33 çip tek düğmeye iner.
- **Liste | Harita** geçişi: harita ikincil görünümdür ve bugünkü `IsHaritasi` bileşeni kullanılır. İşaretçiler aşama rengindedir; yaklaşık konumlu işler halka olarak çizilir.

**Klavye** (yalnız masaüstü; `?` tuşu yardım çekmecesini açar):

| Tuş | Eylem |
|---|---|
| `J` / `K` ya da `↓` / `↑` | Sonraki / önceki iş |
| `Enter` | İş çekmecesini aç |
| `O` | Seçili işin önerisini onayla (tek tuşla atama) |
| `Shift+O` | Öbeğin bütün önerilerini onayla. Sayıyı gösteren bir onay çekmecesi açılır ("12 iş, 3 teknisyene") |
| `T` | Teknisyen seç (yazdıkça daralan liste; `Enter` seçer) |
| `R` | Randevu: `1`–`5` bugünün dilimleri, `Y` yarın, `D` tarih seç |
| `B` | Öbeğe taşı |
| `K` | Ticket bağla / aç |
| `N` | Not |
| `/` | Ara |
| `G` sonra `Ö` / `İ` / `M` | Öbekler / İşler / Masa |
| `Esc` | Çekmeceyi kapat |

Tuş ipuçları düğmelerin yanında `kbd` olarak yalnız masaüstünde görünür.

**1024–1199 px:** öbek sütunu listenin üstünde tek bir "Öbek: Tümü ▾" seçicisine döner. İş çekmecesi listenin
üzerinde açılır.

### 3.2 Operasyon · telefon (< 768 px)

- **Başlık çubuğu 44 px.** Solda başlık, sağda tek bir `+` (Yeni iş emri) ya da `…` düğmesi. Alt sekme çubuğunda 4 öğe: **İşler · Öbekler · Masa · Daha**. Bugün ekranın %35'ini kaplayan yapışkan menü kalkar.
- **İşler:** segment (Atanacak · Sahada · Bekleyen), arama ve tek liste. Satır bir kart gibidir; sağında "Onayla" düğmesi (en az 44 px). Karta dokunmak iş sayfasını tam ekran iterek açar.
- **Öbekler:** liste → öbek sayfası. Öbek sayfasının başlığında "Düzenle", altında o öbeğin işleri vardır (F3). Sayfanın altında sabit birincil düğme **Önerileri onayla (n)** durur.
- **Masa:** BTK teşhis (vade sırasıyla), evde yok merdiveni, Kanal, uyanan askılar. İşe dokununca sonuç kodları büyük düğmeler olarak gelir.
- **Daha:** Ekip (yalnız yöneticide), Ticketlar, Rapor yükle, Tema, Çıkış.

### 3.3 İş çekmecesi (masaüstünde sağdan 440 px; telefonda tam ekran)

Çekmecedeki sıra hızı esas alır; en üstte karar, en altta geçmiş durur.

```
BTK · Bağlantı Problemi                                     Atanacak
Kalan 3 sa 10 dk  ·  hedef 21:40  ·  24 s: yarın 09:40  ·  söz: bugün
───────────────────────────────────────────────────────────────────
Öneri   MK  ·  11:00–13:00  ·  Görükle öbeğinin teknisyeni, bugün 9/15
        [ Onayla  ⌘↵ ]   Değiştir
───────────────────────────────────────────────────────────────────
Müşteri   A**** Y****   No 1234 5678  [Kopyala]      ← kopyala = BOSS/Maya'da ara
Adres     …tam adres…                  [Kopyala]  [Haritada aç]
Bina      X Sitesi B Blok · Location Id O123… [Kopyala] · Konum: bina (Location Id)
───────────────────────────────────────────────────────────────────
Randevu   [09–11] [11–13] [13–15] [15–17] [17–19] [Yarın] [Tarih…]   Tür: Tahmini ▾
Teknisyen [ MK ▾ ]            Öbek  Görükle  [Öbeğe taşı]
Ticket    Binada açık ticket yok    [Ticket bağla]  [Ticket aç]
Masa      BTK teşhis araması: vade 10:45  [Ulaşıldı–düzeldi] [Evde] [Başka gün] [Ulaşılamadı]
Not       …
───────────────────────────────────────────────────────────────────
BOSS      Açık · Ekip: — · Randevusuz · Son açıklama: …
          BOSS'a gir: Ekip MK · 11:00–13:00  [Kopyala]   ☐ BOSS'a işlendi
───────────────────────────────────────────────────────────────────
Geçmiş    11:38 Rapordan geldi · 11:38 Öneri hazır (0 sn) · 11:44 Atandı (6 dk) · …
```

- **Birincil eylem aşamaya göre değişir:**
  - Kontrol → "Öbeğe ata";
  - Atanacak → "Onayla";
  - Masada → "Sonucu işle";
  - Evde yok → "Yeni dilim ver";
  - Atandı → birincil eylem yoktur; "Başka teknisyene ver" ikincil düğme olarak kalır.
- **Teknisyen seçici:** her kişinin bugünkü yükünü ve işe uzaklığını gösterir: "MK · 9/15 · 1,2 km". Önerilen kişi en üsttedir.
- **Randevu seçici:** 2 saatlik dilim çipleri. `tur` üç değer alır: **Tahmini** (sistemin önerisi), **Teyitli** (müşteriyle konuşuldu), **Müşteri isteği**. Kısıtlar: bitiş > başlangıç, başlangıç ≤ şimdi + 7 gün, pencere ≤ 4 saat.
- **Kişisel veri:** müşteri satırı yalnız `is.pii` yetkisi olan role döner. Çekmeceyi açmak görüntüleme kaydı yazar.

### 3.4 Kontrol ve elle öbeğe atama (F4, F5)

Kontrol aşamasındaki iş Atanacak segmentinin en üstünde, kırmızı bir "Kontrol" çipiyle görünür. Nedeni tek satırda
yazar ve eylemleri satırın üzerindedir:

| Neden | Metin | Eylemler |
|---|---|---|
| `il_disi` | "İl bölge dışı: İzmir. Adres hatalı olabilir." | **Öbeğe ata** · Mahalleyi seç · Bayi dışı, iptal (yalnız bayi işi) |
| `mahalle_yok` | "Adreste mahalle bulunamadı." | **Mahalleyi seç** (sözlük seçici) · Öbeğe ata |
| `obek_yok` | "Gürsu / Kurtul hiçbir öbekte değil." | **Bu mahalleyi bir öbeğe ekle**: tek tık, bundan sonra bu mahalleden gelen her iş kendiliğinden o öbeğe düşer · Yalnız bu işi taşı |

İki eylemin etkisi:

- **Öbeğe ata** `obek_elle = 1` yazar. Sonraki içe aktarımlar bu seçimi ezmez; iş hemen öneri motorundan geçer ve `atanacak` olur.
- **Mahalleyi seç** `mahalle_elle = 1` yazar. Öbek bu mahalleden yeniden çözülür.

Mahalle bulma sırası F4'teki gibi kalır: önce Location Id (veritabanındaki binanın OneMap mahallesi), sonra adres.
Kontrol listesine **yalnız** yukarıdaki üç neden girer. "Konum belirsiz" bir bilgidir ve sol sütunda ayrı bir sayaç
olarak durur. "Hepsi yerinde" durumunda Kontrol satırı yeşil bir hapa döner.

### 3.5 Öbek düzenleyici (F1, F2)

Öbek başlık kartındaki "Düzenle" ya da öbek satırına çift tık ile açılır. Masaüstünde sağ çekmecede, telefonda tam
ekranda görünür.

```
Görükle                                   [Adı düzenle]
Teknisyen  MK ▾     Yedek  — ▾            Bu öbekte bugün 31 açık iş
───────────────────────────────────────────────────────────
Mahalleler (6)                                   [+ Mahalle ekle]
  Bursa · Nilüfer · Görükle            14 iş        ✕
  Bursa · Nilüfer · Kayapa              9 iş        ✕
  Bursa · Nilüfer · Dağyenice           0 iş        ✕
  …
───────────────────────────────────────────────────────────
Öbeği ikiye böl (kalıcı)…                 Öbeği sil
```

- **Çıkar (×):** mahalle bir dokunuşla çıkar ve 10 saniyelik "Geri al" bildirimi görünür. Son mahalle çıkarsa öbek **silinmez**, boş kalır.
- **+ Mahalle ekle** bütün sözlükte arayan bir seçici açar (`mahalle_sozluk`, §4.3):
  - Sözlük Bursa'nın 17 ilçesini ve Yalova'nın 6 ilçesini kapsar ve rapordan bağımsızdır.
  - Sonuçlar ilçeye göre gruplanır. Her ilçenin en üstünde **"İlçenin tamamı (Gürsu)"** satırı bulunur (`mahalle_k='*'`).
  - Her sonuç satırında o mahallenin bugünkü iş sayısı ve **şu anki öbeği** görünür.
  - Arama Türkçe harf duyarsızdır ve ek yok sayar: "gocmen" yazmak "Göçmen"i bulur.
  - Çoklu seçim yapılabilir, alttaki **Ekle (n)** düğmesiyle eklenir.
- **Listede olmayan mahalle.** Aranan ad bulunamazsa sonuç listesinin sonunda **"'Göçmen' listede yok: ilçesini seçip ekleyin"** satırı çıkar.
  - Kullanıcı ilçeyi seçer ve adı onaylar.
  - Sistem aynı ilçede benzer bir ad varsa bunu önce gösterir ("Taşliman ↔ Taşlimanı"); kullanıcı ya o kaydı seçer ya da yeni ad olarak ekler (`kaynak='elle'`).
  - Bundan sonra o mahalleden gelen iş kendiliğinden bu öbeğe düşer.
- **Taşıma onayı.** Seçilen mahalle başka bir öbekteyse çekmece içinde onay sorulur: "Kayapa şu an Nilüfer Batı öbeğinde. Görükle'ye taşınsın mı?" → **Taşı** / Vazgeç. Bugünkü sessiz taşıma kalkar.
- **Anında güncelleme.** Her değişiklikten sonra açık işlerin öbeği yeniden çözülür (§4.4 adım 7). Sol sütundaki sayılar ve kontrol listesi 1 saniye içinde güncellenir (F1 kabul testi). Daha önce atanmış işlerin teknisyeni değişmez; bu işler "Öbeği değişti" rozeti alır.
- **Yeni öbek:** öbek listesinin başlığındaki `+` düğmesi. Ad yazılır, boş öbek oluşur, düzenleyici açılır.
- **Öbeği sil:** çekmecede kırmızı düğmeyle yapılır.
  - Öbeğin açık işleri "Kontrol: öbek yok" aşamasına düşer. Çekmece bunu önceden söyler: "31 açık iş öbeksiz kalır".
  - 10 saniyelik geri alma, `obek_gecmis` tablosundaki anlık görüntüden yapılır.
- **Ad değişikliği** var olan bir adla çakışırsa reddedilir (409 `ad_var`). Bugünkü sessiz birleştirme kalkar.
- **Öbeği ikiye böl (kalıcı)** bugünkü mahalleye göre bölme işlevidir (C21, `yakinlik.dengeli_bol`): önizleme gösterilir, sonra iki öbek oluşur.

### 3.6 Öbeğe tıkla → aboneler (F3) ve Ekiplere dağıt

- Öbeğe tıklamak orta listeyi o öbeğin işleriyle doldurur. Her satırda F3'ün istediği bütün alanlar vardır: **müşteri** (ad; no kopyalanabilir), **adres** (kısa; çekmecede tamamı), **task**, **aşama**, **kalan süre**, **randevu**, **teknisyen** (atanmış ya da önerilen).
- Satır sayısı öbek satırındaki sayıyla aynıdır; Tümü segmentinde bütün açık işler görünür.
- **Ekiplere dağıt** (bugünkü "Böl (binaya göre)" işlevinin yeni adı):
  1. Teknisyenler seçilir. Varsayılan seçim: öbeğin teknisyeni ve bugün boşta olanlar.
  2. Önizleme gösterilir: kişi başına iş sayısı, BTK sayısı ve toplam km. Aynı binadaki işler bölünmez.
  3. **Önerileri güncelle** düğmesi yalnız `oneri_teknisyen_id` alanlarını yazar.
  4. Atama, **Önerileri onayla (n)** ile yapılır.

  Böylece "Böl" ile "Ata" arasında ayrı bir parça adımı kalmaz. `parca` alanı Excel çıktısı için doldurulmaya devam eder.

### 3.7 İçe aktarım: klasör izleme, sürükle, fark satırı (F18)

- **Klasör izleme** varsayılan olarak açıktır. İzlenen klasör sunucu bilgisayarında `%USERPROFILE%\Downloads`, desen `TeknikTaskDetayRaporu*.xlsx`.
  - Yeni bir dosya inince panonun başlığında bir bildirim çıkar: "Yeni rapor alındı · 11:38 · Yeni 12 · Değişen 30 · Kapanan 18 · Yeniden açılan 1 · Kontrol 2".
  - Bildirime tıklayınca yeni gelen işler süzülür.
- **Sürükle-bırak** ve **Rapor yükle** düğmesi de aynı içe aktarım işlevini çağırır (`yontem='surukle'`). Rapor başka bir bilgisayara indiyse bu yol kullanılır.
- **Aynı dosya** yeniden gelirse sessizce yok sayılır ("Bu rapor 11:38'de alınmıştı").
- **Eski rapor** (anı, son içe aktarımınkinden eski) reddedilir: "Bu rapor, 12:15'te alınandan eski. Yüklemek isterseniz yalnız yeni işler eklenir." Kullanıcı isterse **Yine de yükle** der; bu durumda hiçbir iş kapatılmaz.
- **Kısmi rapor.** Yeni raporda açık iş sayısı bir öncekinin %60'ından azsa ve önceki en az 50 işse içe aktarım bekletilir. Başlıkta sarı bir kart çıkar: "Bu rapor bir öncekinden çok küçük (412 → 96). Süzülmüş bir rapor mu?" İki seçenek sunulur:
  - **Tam rapor**: düşen işler kapanır;
  - **Kısmi rapor**: düşen işlere dokunulmaz.
- **Çıkarılan satırlar** tek satırda özetlenir: "1.628 satırdan 1.191'i kurulum ekibinin (kurulum 1.072 · 2. donanım 119)". Ayrıntısı bir çekmecede açılır. Bugünkü geliştirici günlüğüne benzeyen şerit kalkar.

### 3.8 Teknik · İşlerim (telefon)

```
İşlerim                                   ● Az önce güncellendi
Bugün 9 iş · 2 BTK · 1 randevu teyitli
─────────────────────────────────────────
SIRADAKİ
BTK  TV+ Arıza                 Kalan 1 sa 40 dk
Görükle · X Sitesi B Blok      Randevu 09–11 (teyitli)
Müşteri no 1234 5678  [Kopyala]
Binada açık ticket yok
[ Yol tarifi ]        [ YOLA ÇIKTIM ]      ← tek birincil düğme
─────────────────────────────────────────
2  BTK  Bağlantı Problemi   Görükle · 12. Sk   11–13
3       Modem Değişikliği   Kayapa · Y Evleri  13–15
…
```

- **Birincil düğme aşamaya göre değişir:** Yola çıktım → Başladım → Bitti. Her basış bir olay yazar ve operasyon ekranını 2 saniye içinde günceller.
- **"Bitti"** alttan bir sonuç çekmecesi açar:
  - **Çözüldü**;
  - **Evde yok**: kural 8'in metni ekranda yazar ("10 dk bekledim, BOSS'tan 2 kez aradım, not bıraktım");
  - **Altyapı sorunu**: ticket açılması için masaya düşer;
  - **Malzeme gerekiyor**;
  - **Müşteri başka gün istedi** (tarih seçilir).

  **"Evde miydi?"** sorusu (Evet / Hayır) her sonuçta zorunludur.
- **Yeni iş gelince** telefon titrer (`navigator.vibrate`), liste başında "Yeni" rozeti belirir ve üstte "1 yeni iş" bildirimi çıkar. İş ekrana ilk girdiğinde `gorulme_zamani` gönderilir.
- **Sıra** sistemin önerisidir (§2.6). Teknisyen bir işi yukarı taşıyabilir, ama kısa bir neden seçmek zorundadır: "Yakındaydım", "Müşteri aradı", "Diğer".
- **Kişisel veri:** müşteri no ve adı yalnız kendine atanmış açık işte görünür (§1.3). İş kapanınca gizlenir.
- **Çevrimdışı:** liste önbellekte kalır. Basılan düğmeler IndexedDB kuyruğuna `offline_id` ve cihazdaki basış anıyla yazılır (bugünkü ziyaret kuyruğu kullanılır). Ekranda "2 işlem bekliyor" görünür.
- **Tasarım:** satışçı uygulamasının Bugün ve Bina ekranlarındaki bileşenler kullanılır: kart, iki düğmeli alt bölüm, alt sekmeler, 56 px hedef.

### 3.9 Ekip: 4 görev ve silme (F12, F13)

- **Liste satırı:** baş harfler · ad · görev (Satış / Operasyon / Teknik / Yönetici) · durum (Aktif · Davet bekliyor · Pasif). Telefon maskelenir: "0532 ••• •• 06". Masaüstünde tablo yerine satır listesi vardır; telefonda yatay kaydırma yoktur.
- **Kişi çekmecesi:** Ad, Telefon, **Görev** (dört seçenekli segment).
  - Seçilen göreve göre ilgili alanlar görünür: Satış için **Bölge** (zorunlu); Teknik için **Ev öbekleri**, **BOSS'taki ekip adı**, **Günlük kapasite** (varsayılan 15) ve "Bugün çalışmıyor" anahtarı; Operasyon için bir etiket (Faz 2).
  - Aktif anahtarı.
- **Alt bölüm:** PIN sıfırla · Cihazlardan çıkar · Pasife al · **Sil** (kırmızı).
- **Silme akışı:**
  1. `GET /api/kullanici/{id}/bagimlilik` çağrılır.
  2. Kişinin **herhangi bir kaydı** varsa çekmece açılır: "Bu kişinin üstünde iş var: 3 açık iş emri · 120 ziyaret · 1 ticket. Silinemez, çünkü kayıtlar bu kişiye bağlı. Pasife alırsanız giriş yapamaz, kayıtları korunur." Seçenekler: **[Pasife al]** (birincil) · Vazgeç. Açık işler varsa ayrıca **"Açık işleri başkasına ver"** bağlantısı çıkar ve panoyu o kişinin işleriyle açar.
  3. Kaydı yoksa: "<Ad Soyad> kalıcı olarak silinsin mi? Bu işlem geri alınamaz." → **Sil** / Vazgeç. Silme 204 döner.
  4. Kişi kendini silemez. Son aktif yönetici silinemez.
- **Davet kodu** yalnız "Davet kodu hazır" çekmecesinde, bir kez gösterilir. Süresi 48 saattir; süresi dolmuşsa "Yeni kod üret" düğmesi çıkar.
- **Göç sonrası kart:** §1.4'teki "Görevleri gözden geçirin" kartı.

Not: bugün 10 hesabın 8'inde demo ziyareti var. Bu hesaplar demo verisi temizlenmeden silinemez; ekran bunu
"120 ziyaret (gösterim verisi)" diye açıkça yazar. Demo verisinin temizlenmesi ayrı bir karardır (Açık soru 11).

### 3.10 Yönetici · Takip paneli (F11, F17)

```
Takip · bugün 30.09                                           [Gün ▾]  [Excel]
───────────────────────────────────────────────────────────────────────────────
 Açık 437     24 s'i aşan 288     48 s'i aşan BTK 41     Atanmamış 12     Kontrol 3
───────────────────────────────────────────────────────────────────────────────
HIZ HATTI (bugün, medyan · hedefte %)
 BOSS→sistem 22 dk · %71 │ öneri 1 sn │ ATAMA 9 dk · %83 │ gördü 2 dk │ BOSS'a işlendi 14 dk │ yol 38 dk │ saha 71 dk
───────────────────────────────────────────────────────────────────────────────
24 s UYUMU (dün gelen)  %43   ▁▂▂▃▄▅ 7 gün         BTK: TV 6 s %20 · Bağlantı 12 s %30
BİRİKİM (24 s'i aşan açık)  288  ↘ −14/gün (7 gün)
KAPASİTE  talep ~205 · 11 teknisyen × 15 = 165 → AŞIRI YÜK · öneri +3 esnek
17:00 KONTROLÜ  ekibi boş yeni iş: 0 ✓
───────────────────────────────────────────────────────────────────────────────
TEKNİSYENLER   atanmış · yolda · bitti · geciken · ilk iş saati
ÖBEKLER        açık · geciken · BTK · 48 s'i aşan BTK        (ısı sırası)
SATIŞ (bugün)  ziyaret 142 · satış 11 · aktif satışçı 7/8          [Canlı durum →]
SİSTEM         Son rapor 11:38 · klasör izleme açık · son yedek 30.09 19:30 · kişisel veri görüntüleme 57
```

- **Göstergeler** OPERASYON_TASARIM §5.5'teki listeden alınır. v2.0'da şunlar vardır: 24 s uyumu, BTK uyumu, 48 s'i aşan BTK, birikim ve eğimi, kapasite göstergesi ve mod, 17:00 kontrolü, ilk ziyaret saati. Boşa ziyaret oranı ve telefonla kapatmanın tekrar oranı, "Evde miydi?" verisi biriktikçe dolar.
- **Tıklanabilirlik:** her sayı tıklanınca Sevk panosunu o süzgeçle açar. Örneğin "48 s'i aşan BTK" → BTK + gecikenler.
- **Günlük özet** `gun_ozeti` tablosuna günün ilk içe aktarımında (dün için) ve 17:30'da (bugün için) yazılır. 7 günlük çizgiler bu tablodan çizilir.
- **Kapasite:**
  - talep = SAHA ve BTK şeritlerinde, istisnada olmayan ve `hedef` alanı bugün ya da daha önce olan açık işler;
  - kapasite = bugün çalışan teknisyen sayısı × `kapasite`;
  - talep > kapasite ise **aşırı yük**;
  - esnek önerisi = min(8, ⌈(talep − kapasite) / 15⌉) (kural 15).

  Hiç teknisyen tanımlı değilse gösterge sayı yerine "Ekip'ten Teknik görevli kişi ekleyin" yazar.
- **Operasyon rolü** bu paneli yalnız ilk iki bölümle (manşet ve hız hattı) görür.

### 3.11 Satış yönetimi kancası (F15)

v2.0'da:

- Takip panelindeki **Satış** kartı: bugünkü ziyaret, satış ve aktif satışçı sayısı (`/api/ozet/gun`) ile en çok ve en az ziyaret yapan satışçı. Karttan Canlı durum ekranına gidilir.
- Menüdeki **Satış ▸** grubu: Canlı durum, Kapsama, Görev atama, Rapor. Bu ekranlar bugünkü haliyle kalır.
- **Operasyondan satışa köprü:** altyapı ticket'ı çözülünce bina satış listesine geri açılır (OPERASYON_TASARIM §3.6). Bunun v2'deki izi, `altyapi → atanacak` geçişinde binanın satış tarafında "Altyapı çözüldü" notunu alması.
- Canlı ekrandaki küçük hata da düzeltilir: satışçı kartındaki "Bugün için görev ata" düğmesi o satışçıyı seçili olarak açmalı (`/yonetici/atama/{id}`).

Sonraki faz (tasarımı ayrı yapılacak): satışçı başına haftalık hedef, huni (ziyaret → ilgi → satış → kurulum),
"Satışlarım: kurulum durumu", bayi iş emri ile satış bağlantısı.

### 3.12 Yeni iş emri (bayi; F16)

Çekmecede tek sütunlu bir form:

- Müşteri no (8 hane; varsa aynı müşterinin açık işi gösterilir)
- Müşteri adı
- İş tipi (bilinen task adlarından seçilir; şerit buradan çıkar)
- Adres (serbest metin) **ya da** Bina seç (site adı ya da Location Id ile arama)
- Mahalle (sözlük seçici; bina seçildiyse kendiliğinden dolar)
- Not

Kaynak her zaman **Bayi**'dir. **Kaydet** düğmesine basılınca iş Atanacak listesinin başına öneriyle birlikte düşer
ve "Bayi" rozeti alır. BOSS'ta göründüğünde §2.8'deki kuralla birleşir.

### 3.13 Giriş

- **Klavye:** fiziksel klavyeden rakam, Backspace ve Enter kabul edilir. Denetimde bu çalışmıyordu; ofis bilgisayarında 14 tıklama gerekiyordu.
- **Genişlik:** giriş sütunu, **Devam** düğmesi dahil en fazla 360 px.
- **Uygulama simgesi:** girişte, PWA simgesinde ve konsolda aynı marka işareti kullanılır.

### 3.14 Menü ve yönlendirme

- **Adres yapısı:**
  - `#/operasyon[/obek/<id>][/is/<task_no>]`: Sevk panosu; adres paylaşılabilir;
  - `#/teknik[/is/<task_no>]`;
  - `#/yonetici/<bölüm>` (bugünkü yapı) + `takip`.
- **Yönetici konsolunun menüsü** işin etrafında yeniden sıralanır: **Takip · Sevk panosu · Öbekler · Ticketlar · Ekip · Satış ▸** (Canlı, Kapsama, Görev atama, Rapor) **· Veri ▸** (Bölge planlayıcı, Tur raporu, Veri kalitesi).
- **Eski "İş emirleri" ekranı** menüden kalkar; §4.10'a bakın.
- **`App.tsx`** rolü okuyup `ana_ekran`a yönlendirir (`depo/oturum.tsx:121`). `AltBar`, rolün sekmelerini gösterir.

---

## 4. Teknik tasarım

### 4.1 Göç çerçevesi: güncellemede veri zarar görmez (F20)

**Yeni modül `saha/goc.py`.** Bugünkü `db.gocler()` yalnız ekleme yapan adımlarıyla aynen kalır. Yeni adımlar
`goc.v2(conn)` içinde yazılır. `gocler()` en sonda `goc.v2()` adımını çağırır.

**Tespit:** `v2` adımı `user_version`'a değil, şemanın kendisine bakar: CREATE metni, sütunlar ve tablolar
incelenir. Böylece her adım tekrar koşturulabilir ve ikinci koşu hiçbir şey yapmaz. En sonda `PRAGMA user_version=3`
yazılır. Bu değer yalnız bilgi amaçlıdır.

**Açılış sırası** (`saha/sunucu.py:main`):

1. **Port kontrolü ÖNCE yapılır.** Port doluysa şu yazılır ve çıkılır; veritabanına dokunulmaz: "Sunucu zaten açık: http://…:8080. İkinci kez açmaya gerek yok."
2. `goc.bekleyen(conn)` bekleyen göç adımlarını listeler. Liste boşsa 5. adıma geçilir.
3. **Göç yedeği** alınır: `yedekle.goc_yedegi()` → `saha/yedek/goc/saha-oncesi-AAAAAGG-SSDDss.db`.
   - Kaynak `mode=ro` ile açılır ve backup API kullanılır.
   - Kopyada `journal_mode=DELETE` yapılır ve `integrity_check` = ok ile tablo satır sayılarının kaynağa eşitliği doğrulanır.
   - Günlük yedeğin üzerine yazılmaz. `eskileri_sil` bu klasöre dokunmaz.
   - **Yedek alınamazsa göç yapılmaz ve sunucu açılmaz**: "Güncelleme öncesi yedek alınamadı; veritabanına dokunulmadı. BT'ye haber verin." Hata ayrıntısı günlüğe yazılır.
4. **Göç** uygulanır (4.2). Her tablo yeniden kurulumu tek bir `BEGIN IMMEDIATE … COMMIT` içindedir ve COMMIT'ten önce doğrulanır. İstisna olursa ROLLBACK yapılır, ekrana Türkçe hata yazılır, sunucu açılmaz. Yedeğin yolu da yazılır.
5. `api.py` lifespan'i göç **yapmaz**, yalnız doğrular. `user_version < 3` ise uyarı yazar ve iş emri uçları 503 `guncelleme_bekliyor` döner. Testler için `SAHA_GOC_LIFESPAN=1` lifespan'de göçü açar (bugünkü davranış).
6. **Açılış özeti** ekrana ve günlüğe yazılır: "Güncelleme tamam · 10 kişi (2 PIN) · 1.257 ziyaret · 7 görev · 19.706 bina · yedek: …". Yalnız sayı yazılır, isim yazılmaz.

**Güncelleme adımları** (kullanıcı için, SAHA_KULLANIM'a eklenir):

1. DURDUR.bat.
2. Yeni dosyaları kopyala. **Üzerine yazılmayacaklar:** `saha/saha.db*`, `saha/gizli.key`, `saha/yedek/`, `operasyon/obekler.json`, `operasyon/veri/`.
3. baslat.bat.
4. Açılış özetindeki sayıları kontrol et.

### 4.2 SQL (tam)

Genel kurallar:

- Yeni tablolarda **enum CHECK kısıtı yoktur**; değerler Python'da doğrulanır.
- İz tutan tablolarda (`is_olay`, `erisim_kaydi`, `ice_aktarim`, `obek_gecmis`) kişiye **yabancı anahtar yoktur**; `kullanici_id` ve `kullanici_ad` olarak anlık görüntü tutulur. Böylece kişi silinse de iz okunur ve iz kaydı silmeyi engellemez.
- İş tutan tablolar (`is_emri.teknisyen_id`, `is_emri.sahip_id`, `obek.teknisyen_id`, `teknik_yoklama`) `kullanici(id)`'ye bağlıdır. İşi olan kişi bu sayede silinemez (F13).
- Zaman alanları `ayarlar.zaman_metni()` biçimindedir: Türkiye saati, `'AAAA-AA-GG SS:DD:ss'`.

**G1 · `kullanici` rol genişletme** (yalnız `sqlite_master.sql` içinde `'teknik'` yoksa çalışır; CHECK'siz eski tabloda da çalışır):

```sql
-- Python: conn.isolation_level = None; önce conn.commit()
PRAGMA foreign_keys=OFF;                       -- işlem DIŞINDA; işlem içinde etkisiz
BEGIN IMMEDIATE;
-- Python: eski_seq = SELECT seq FROM sqlite_sequence WHERE name='kullanici'
--         once = (satır sayısı, sha256(id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma sıralı))
--         bilinmeyen rol varsa (rol NOT IN 4 rol) → ROLLBACK, uyarı, sunucu ESKİ rollerle açılır
CREATE TABLE kullanici_yeni (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ad           TEXT    NOT NULL,
    telefon      TEXT    NOT NULL UNIQUE,
    pin_hash     TEXT,
    davet_kodu   TEXT,
    rol          TEXT    NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge        INTEGER,
    aktif        INTEGER NOT NULL DEFAULT 1,
    oturum_no    INTEGER NOT NULL DEFAULT 1,
    olusturma    TEXT    NOT NULL,
    davet_zamani TEXT,          -- davet kodunun üretildiği an (48 s)
    boss_ekip    TEXT,          -- teknik: BOSS 'Ekip' sütunundaki ad
    kapasite     INTEGER,       -- teknik: günlük iş (NULL → ayar 'teknik_kapasite' = 15)
    etiket       TEXT           -- operasyon masa etiketi / 'lider' (Faz 2)
);
INSERT INTO kullanici_yeni (id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma)
     SELECT id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma FROM kullanici;
DROP TABLE kullanici;                           -- ÖNCE yeni kur, SONRA eskiyi düşür
ALTER TABLE kullanici_yeni RENAME TO kullanici; -- ASLA önce eskiyi RENAME etme (11 FK 'kullanici_eski'ye kayar)
UPDATE sqlite_sequence SET seq = MAX(seq, :eski_seq) WHERE name='kullanici';
-- Python: changes()==0 ise INSERT INTO sqlite_sequence(name,seq) VALUES('kullanici', :eski_seq)
-- Doğrulama (hepsi geçmezse ROLLBACK):
--   satır sayısı ve özet aynı · PRAGMA foreign_key_check boş
--   SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_eski%' OR sql LIKE '%kullanici_yeni%' = 0
--   pragma_foreign_key_list: kullanici'ye giden bütün FK'lar hedef olarak 'kullanici' gösteriyor
COMMIT;
PRAGMA foreign_keys=ON;
PRAGMA integrity_check;                         -- 'ok' değilse: yedek yolunu yaz, sunucuyu açma
```

`db.SEMA` içindeki `kullanici` tanımı ve `ayarlar.ROLLER` aynı sürümde güncellenir. `kullanici_yeni` tanımı
`db.KULLANICI_TANIMI` sabitinden üretilir; eski SQL'in metin değiştirilerek kullanılması yasaktır.
Sonradan eklenecek sütunlar için `ALTER TABLE kullanici ADD COLUMN` (G1 geçildiyse) kullanılır.

**G2 · Yeni tablolar.** Tek işlemde kurulur; her ifade `IF NOT EXISTS` içerir. `executescript` kullanılmaz,
ifadeler tek tek `execute` edilir.

```sql
BEGIN IMMEDIATE;

-- İlçe ve mahalle sözlüğü (F2)
CREATE TABLE IF NOT EXISTS ilce (
  il_k TEXT NOT NULL, ilce_k TEXT NOT NULL,
  il TEXT NOT NULL, ad TEXT NOT NULL,
  lat REAL, lon REAL,
  PRIMARY KEY (il_k, ilce_k)
);
CREATE TABLE IF NOT EXISTS mahalle_sozluk (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, ad_k TEXT NOT NULL,   -- ie.anahtar()
  il TEXT NOT NULL, ilce TEXT NOT NULL, ad TEXT NOT NULL,          -- görünen
  lat REAL, lon REAL,
  kaynak      TEXT NOT NULL,            -- liste | bina | obek | rapor | elle
  ekleyen_id  INTEGER, ekleyen_ad TEXT, -- FK yok
  olusturma   TEXT NOT NULL,
  UNIQUE (il_k, ilce_k, ad_k)
);
CREATE TABLE IF NOT EXISTS mahalle_takma_ad (       -- yazım farkları: TASLIMAN → TASLIMANI
  il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, takma_k TEXT NOT NULL,
  mahalle_id INTEGER NOT NULL REFERENCES mahalle_sozluk(id) ON DELETE CASCADE,
  PRIMARY KEY (il_k, ilce_k, takma_k)
);
CREATE TABLE IF NOT EXISTS ilce_takma_ad (          -- 'M.KEMALPASA' → MUSTAFAKEMALPASA, 'YALOVA MERKEZ' → MERKEZ
  il_k TEXT NOT NULL, takma_k TEXT NOT NULL, ilce_k TEXT NOT NULL,
  PRIMARY KEY (il_k, takma_k)
);

-- Öbekler (obekler.json'un yerini alır)
CREATE TABLE IF NOT EXISTS obek (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  ad                 TEXT NOT NULL,
  ad_k               TEXT NOT NULL UNIQUE,
  teknisyen_id       INTEGER REFERENCES kullanici(id),
  yedek_teknisyen_id INTEGER REFERENCES kullanici(id),
  renk               INTEGER,
  surum              INTEGER NOT NULL DEFAULT 1,
  olusturma          TEXT NOT NULL,
  guncelleme         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS obek_mahalle (
  il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,   -- '*' = ilçenin tamamı
  il TEXT NOT NULL, ilce TEXT NOT NULL, mahalle TEXT NOT NULL,
  obek_id INTEGER NOT NULL REFERENCES obek(id) ON DELETE CASCADE,
  ekleme  TEXT NOT NULL,
  PRIMARY KEY (il_k, ilce_k, mahalle_k)             -- bir mahalle yalnız bir öbekte
);
CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id);
CREATE TABLE IF NOT EXISTS obek_gecmis (            -- yalnız eklenir
  id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT NOT NULL,
  kullanici_id INTEGER, kullanici_ad TEXT,
  islem TEXT NOT NULL,                              -- olustur|ad|mahalle_ekle|mahalle_cikar|tasi|teknisyen|sil|geri_al|bol|tohum
  obek_id INTEGER, obek_ad TEXT,
  veri TEXT                                         -- JSON; 'sil' için tam anlık görüntü (geri al)
);

-- İçe aktarımlar (her rapor)
CREATE TABLE IF NOT EXISTS ice_aktarim (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  kaynak        TEXT NOT NULL DEFAULT 'boss_acik',
  yontem        TEXT NOT NULL,                      -- klasor | surukle | komut
  dosya_adi     TEXT NOT NULL,
  dosya_sha256  TEXT NOT NULL,
  anlik         TEXT NOT NULL,                      -- raporun anı (dosya zamanı; en fazla 'şimdi')
  baslangic     TEXT NOT NULL,
  bitis         TEXT,
  yukleyen_id   INTEGER, yukleyen_ad TEXT,          -- klasörde: NULL, 'Klasör izleme'
  satir INTEGER, cikarilan INTEGER, kalan INTEGER,
  yeni INTEGER, degisen INTEGER, ayni INTEGER, kaybolan INTEGER, yeniden_acilan INTEGER,
  kontrol INTEGER, boss_atamasi INTEGER, birlesen INTEGER,
  tam_kapsam    INTEGER NOT NULL DEFAULT 1,
  durum         TEXT NOT NULL,                      -- tamam | kismi_onay | reddedildi | hata
  uyari         TEXT,
  sure_sn       REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_aktarim_sha ON ice_aktarim(dosya_sha256) WHERE durum='tamam';

-- İş emri: işin güncel hâli
CREATE TABLE IF NOT EXISTS is_emri (
  task_no            TEXT PRIMARY KEY,              -- BOSS Task No (9 hane, METİN) · bayi: 'B-000001'
  kaynak             TEXT NOT NULL DEFAULT 'boss',  -- boss | bayi
  kanal              TEXT,                          -- global | bayi | NULL
  bagli_task_no      TEXT,                          -- bayi işi → BOSS Task No
  task_adi           TEXT NOT NULL,
  serit              TEXT NOT NULL,                 -- BTK | SAHA | MASA | LOJISTIK
  hedef_saat         INTEGER NOT NULL DEFAULT 24,
  musteri_no         TEXT,                          -- KİŞİSEL VERİ · kapanış+30 g → NULL
  musteri_ad         TEXT,                          -- KİŞİSEL VERİ
  adres              TEXT,                          -- KİŞİSEL VERİ
  il TEXT, ilce TEXT, mahalle TEXT,
  il_k TEXT, ilce_k TEXT, mahalle_k TEXT,
  mahalle_kaynak     TEXT,                          -- lokasyon | adres | site | adres-yeni | elle | …
  mahalle_elle       INTEGER NOT NULL DEFAULT 0,
  lokasyon           TEXT,
  bina_serial        TEXT,                          -- FK yok: bina pasife alınabilir
  lat REAL, lon REAL,
  konum_kaynak       TEXT,
  konum_yaklasik     INTEGER NOT NULL DEFAULT 0,
  obek_id            INTEGER REFERENCES obek(id),
  obek_elle          INTEGER NOT NULL DEFAULT 0,
  -- BOSS aynası
  boss_durum TEXT, boss_ekip TEXT, boss_randevu TEXT, boss_randevu_bas TEXT, boss_randevu_bit TEXT,
  boss_aski_nedeni TEXT, boss_sl_saat REAL, boss_son_aciklama TEXT, boss_satis_kanali TEXT,
  -- saatler
  acilis             TEXT NOT NULL,
  son24              TEXT NOT NULL,
  hedef              TEXT NOT NULL,
  -- akış
  asama              TEXT NOT NULL DEFAULT 'gelen',
  kontrol            TEXT,                          -- JSON dizi: ["il_disi","mahalle_yok","obek_yok"]
  oneri_teknisyen_id INTEGER, oneri_bas TEXT, oneri_bit TEXT, oneri_neden TEXT,
  teknisyen_id       INTEGER REFERENCES kullanici(id),
  sahip_id           INTEGER REFERENCES kullanici(id),   -- masa / isimli sahip (kural 6)
  randevu_bas TEXT, randevu_bit TEXT, randevu_tur TEXT,  -- tahmini | teyitli | musteri_istegi
  atama_kaynagi      TEXT,                          -- oneri | elle | boss
  sira               INTEGER,
  parca              TEXT,
  masa_teshis        TEXT,                          -- NULL | duzeldi | evde | baska_gun | ulasilamadi | kotu_gecmis
  masa_vade          TEXT,
  uyanma             TEXT,
  deneme             INTEGER NOT NULL DEFAULT 0,
  boss_islendi       TEXT,
  boss_dogrulandi    TEXT,
  notu               TEXT,
  rozet_tekrar       INTEGER NOT NULL DEFAULT 0,
  -- zaman damgaları (hız hattı)
  ilk_gorulme        TEXT NOT NULL,
  hazir_zamani TEXT, atama_zamani TEXT, gorulme_zamani TEXT,
  yolda_zamani TEXT, sahada_zamani TEXT, bitti_zamani TEXT,
  kapanis TEXT, kapanis_nedeni TEXT,
  son_gorulme        TEXT,
  yeniden_acilma     INTEGER NOT NULL DEFAULT 0,
  son_aktarim_id     INTEGER REFERENCES ice_aktarim(id),
  ozet               TEXT,                          -- BOSS ayna alanlarının sha1'i
  surum              INTEGER NOT NULL DEFAULT 1,    -- iyimser kilit
  guncelleme         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_is_asama   ON is_emri(asama, hedef);
CREATE INDEX IF NOT EXISTS ix_is_obek    ON is_emri(obek_id, asama);
CREATE INDEX IF NOT EXISTS ix_is_teknik  ON is_emri(teknisyen_id, asama);
CREATE INDEX IF NOT EXISTS ix_is_mahalle ON is_emri(il_k, ilce_k, mahalle_k);
CREATE INDEX IF NOT EXISTS ix_is_bina    ON is_emri(bina_serial);
CREATE INDEX IF NOT EXISTS ix_is_musteri ON is_emri(musteri_no, task_adi);
CREATE INDEX IF NOT EXISTS ix_is_bagli   ON is_emri(bagli_task_no);

-- Olay günlüğü: geçmiş + canlı güncelleme + hız ölçümü (yalnız eklenir)
CREATE TABLE IF NOT EXISTS is_olay (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_no       TEXT NOT NULL,
  zaman         TEXT NOT NULL,                      -- olayın anı (çevrimdışıda cihazdaki basış anı)
  kayit_zamani  TEXT NOT NULL,                      -- sunucuya ulaştığı an
  tur           TEXT NOT NULL,                      -- ice_aktarildi|asama|atandi|randevu|goruldu|obek|mahalle|ticket_baglandi|
                                                    -- ticket_ayrildi|not|boss_alan|boss_islendi|boss_dogrulandi|kayboldu|
                                                    -- yeniden_acildi|birlesti|masa|geri_al
  eski TEXT, yeni TEXT,                             -- aşama ya da alan değeri (kişisel veri YAZILMAZ)
  kullanici_id  INTEGER, kullanici_ad TEXT,         -- FK yok
  ice_aktarim_id INTEGER,
  offline_id    TEXT,
  veri          TEXT                                -- JSON
);
CREATE INDEX IF NOT EXISTS ix_olay_task ON is_olay(task_no, id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_olay_offline ON is_olay(kullanici_id, offline_id) WHERE offline_id IS NOT NULL;

-- Ticket ↔ iş (F9)
CREATE TABLE IF NOT EXISTS ticket_is (
  ticket_id   INTEGER NOT NULL REFERENCES ticket(id),
  task_no     TEXT    NOT NULL REFERENCES is_emri(task_no),
  baglayan_id INTEGER, zaman TEXT NOT NULL, otomatik INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (ticket_id, task_no)
);
CREATE INDEX IF NOT EXISTS ix_ticket_is_task ON ticket_is(task_no);

-- Kişisel veri görüntüleme kaydı (F21 · KVKK)
CREATE TABLE IF NOT EXISTS erisim_kaydi (
  id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT NOT NULL, gun TEXT NOT NULL,
  kullanici_id INTEGER NOT NULL, kullanici_ad TEXT,
  task_no TEXT NOT NULL, tur TEXT NOT NULL          -- cekmece | kopya_musteri_no | excel
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_erisim_gun ON erisim_kaydi(gun, kullanici_id, task_no, tur);

-- Teknisyen yoklaması ve günlük özet
CREATE TABLE IF NOT EXISTS teknik_yoklama (
  tarih TEXT NOT NULL, kullanici_id INTEGER NOT NULL REFERENCES kullanici(id),
  durum TEXT NOT NULL,                              -- calisiyor | yok
  PRIMARY KEY (tarih, kullanici_id)
);
CREATE TABLE IF NOT EXISTS gun_ozeti (
  tarih TEXT PRIMARY KEY, hesap TEXT NOT NULL,
  acik INTEGER, asan24 INTEGER, asan48_btk INTEGER, gelen INTEGER, cozulen INTEGER,
  uyum24 REAL, uyum_btk_tv REAL, uyum_btk_baglanti REAL,
  atama_medyan_dk REAL, atama_15dk_oran REAL, ilk_is_saati TEXT,
  talep INTEGER, teknisyen INTEGER, kapasite INTEGER, mod TEXT
);

COMMIT;
```

**G3 · Ayar varsayılanları** (`INSERT OR IGNORE INTO ayar`):

- `izleme_acik=1`
- `izleme_klasoru=<USERPROFILE>\Downloads`
- `izleme_desen=TeknikTaskDetayRaporu*.xlsx`
- `is_suresi_dk=32`
- `teknik_kapasite=15`
- `gun_baslangic=08:30`
- `rapor_bayat_dk=30`
- `bayi_is_sayac=0`
- `pii_saklama_gun=30`
- `ham_saklama_gun=7`

**G4 · Tohumlar** (§4.3). **G5:** `PRAGMA user_version=3`.

### 4.3 Tohumlar: öbekler ve mahalle sözlüğü

**Öbek tohumu.** `obek` tablosu boşsa ve `operasyon/obekler.json` varsa yapılır:

- Dosya **yalnız okunur**. Ortam değişkeni `OPERASYON_OBEK` tanımlıysa onun gösterdiği dosya okunur.
- Her öbek için `obek` satırı; her ref için `obek_mahalle` satırı yazılır (`'İl/İlçe/Mahalle'` ya da `'İl/İlçe/*'`). Refler kanonik hâle getirilir: il ilçeden doldurulur, anahtar `ie.anahtar()` ile üretilir.
- Kopyalar ayıklanır. Aynı anahtarı iki öbek istiyorsa ilk gelen kazanır ve uyarı yazılır (bugün çakışma 0).
- Doğrulama: öbek sayısı (bugün 14) ve ref sayısı (bugün 120) dosyayla eşit olmalı. Sonuç `obek_gecmis` tablosuna `islem='tohum'` olarak yazılır.
- **`obekler.json`'a hiçbir zaman yazılmaz.** Dosya ilk tohum ve donmuş yedek olarak kalır.
- Her öbek değişikliğinden sonra sunucu bir yansı yazar: `operasyon/veri/obek_yedek/obekler-AAAAAGG-SSDDss.json`. Son 50 dosya tutulur; klasör git dışıdır.

**Mahalle sözlüğü.** `INSERT OR IGNORE` ile, idempotent olarak doldurulur:

1. `ilce`: Bursa'nın 17 ilçesi (Büyükorhan, Gemlik, Gürsu, Harmancık, İnegöl, İznik, Karacabey, Keles, Kestel, Mudanya, Mustafakemalpaşa, Nilüfer, Orhaneli, Orhangazi, Osmangazi, Yenişehir, Yıldırım) ve Yalova'nın 6 ilçesi (Altınova, Armutlu, Çınarcık, Çiftlikköy, Merkez, Termal). Merkez noktaları `data/ref/osm_ilce.geojson`'dan hesaplanır; bulunamayan ilçede noktalar NULL kalır.
2. `data/ref/mahalle_listesi.json`: 621 mahalle, 10 Bursa ilçesi, merkez noktalarıyla (`kaynak='liste'`).
3. `bina` tablosundaki `DISTINCT (il, ilce, mahalle)` (`kaynak='bina'`). Merkez noktası o mahalledeki binaların ortalamasıdır.
4. `obek_mahalle` içinde olup sözlükte bulunmayan refler (`kaynak='obek'`). Bugün 120 refin 36'sı böyle (Yalova ve üç Bursa ilçesi).
5. Her içe aktarımda raporda görülüp sözlükte olmayan mahalleler (`kaynak='rapor'`).
6. Kullanıcının elle eklediği mahalleler (`kaynak='elle'`, §3.5).
7. İlçe takma adları: `M.KEMALPASA`, `MKEMALPASA` → `MUSTAFAKEMALPASA`; `YALOVA MERKEZ` → `MERKEZ`.

"İlçenin tamamı" 23 ilçenin **hepsi** için ilk günden çalışır. Bursa'nın 17 ilçesi ve Yalova'nın 6 ilçesi için eksiksiz
resmî mahalle listesi (UAVT ya da BursaStateList'in tam sürümü) geldiğinde `python -m operasyon.v2.sozluk_yukle
DOSYA.xlsx` ile aynı tabloya eklenir (Açık soru 5). O güne kadar listede olmayan mahalle (ör. Göçmen) elle eklenir
(§3.5).

### 4.4 İçe aktarım hattı (idempotent, geçmişli)

`operasyon/v2/ice_aktar.py:ice_aktar(conn, veri, dosya_adi, anlik, yontem, kullanici, mod='otomatik', zorla=False)`.
Uç `def` olarak tanımlanır, `async def` olarak değil; FastAPI işi threadpool'da çalıştırır ve olay döngüsü
kilitlenmez. İşlem boyunca süreç düzeyindeki bir kilit (`IceAktarimKilidi`) tutulur, böylece iki içe aktarım
aynı anda çalışmaz.

1. **Özet.** `sha256(veri)` hesaplanır. `durum='tamam'` olan aynı özetli bir kayıt varsa `{kod:'ayni_dosya', aktarim_id}` döner (HTTP 200) ve hiçbir şey değişmez.
2. **Tazelik.** `anlik < MAX(anlik WHERE durum='tamam')` ise ve `zorla` verilmemişse 409 `eski_rapor` döner. `zorla=1` verilirse `tam_kapsam=0` sayılır ve hiçbir iş kapatılmaz.
3. **Ayrıştırma** (işlem dışında):
   - `ie.raporu_oku` ve `ie.hazirla(df, obekler_db, sozluk_db)` çağrılır. `sozluk_db`, `bina` tablosunu **veritabanından** okur (pasif olmayanlar önce, `ekleme_kaynagi='tur'` dahil).
   - Location Id iki tarafta da normalleştirilir: birebir, 8 haneye sıfırla tamamlanmış, baştaki sıfırı atılmış ve "-N" eki atılmış biçimler aynı binaya çıkar. Bu, `ticket.lokasyondan_bina` ve `kalite.location_norm` kurallarıyla aynıdır. Hedef: 332/332.
   - Mahalle listeleri `mahalle_sozluk`'tan gelir.
   - Kurulum ve 2. donanım filtresi aynen kalır (C17).
4. **Kısmi rapor koruması.** `mod='otomatik'` ise, `kalan < 0,6 × önceki açık BOSS işi sayısı` ve önceki ≥ 50 ise ham dosya `operasyon/veri/ham/<sha>.xlsx` olarak saklanır. `ice_aktarim` satırı `durum='kismi_onay'` ile yazılır ve 202 `kismi_onay` döner. Kullanıcı `/onayla {mod:'tam'|'kismi'}` ile karar verene kadar başka bir şey yapılmaz.
5. **Tek işlem** (`BEGIN IMMEDIATE`). Her satır için Task No metin olarak alınır ve baştaki/sondaki boşluk kırpılır. Sonra:
   - **Yok:** `INSERT`, `asama='gelen'`, `ilk_gorulme=şimdi`. Olay: `ice_aktarildi`.
   - **Var ve kapalı:** iş yeniden açılır (§2.3). Olay: `yeniden_acildi`.
   - **Var ve açık:** yalnız BOSS ayna alanları, `son_gorulme` ve `son_aktarim_id` güncellenir. `ozet` aynıysa satıra dokunulmaz (`ayni` sayacı). Değişen ayna alanları için `boss_alan` olayı yazılır. `obek_elle`/`mahalle_elle` = 1 ise çözülmüş mahalle ve öbek **ezilmez**.
   - **BOSS Ekip:** boşsa bir şey yapılmaz. Doluysa `kullanici.boss_ekip` ile eşleşme aranır (büyük/küçük harf ve Türkçe harf duyarsız):
     - bizim teknisyen boşsa `teknisyen_id` o kişi olur, `atama_kaynagi='boss'`, aşama §2.3'e göre ilerler;
     - bizim teknisyen aynı kişiyse `boss_dogrulandi=şimdi`.
   - **Bayi birleştirme** (§2.8).
   - **Tekrar arıza rozeti** (§2.3).
6. **Kaybolanlar.** `tam_kapsam=1` ise raporda olmayan her açık `kaynak='boss'` işi `kapandi` olur (§2.3). Olay: `kayboldu`.
7. **Öbek çözümü ve öneri.** Sırayla:
   - `UPDATE is_emri SET obek_id = (tam mahalle ref) ?? (ilçe '*' ref) WHERE obek_elle=0 AND açık`;
   - yeni, yeniden açılan ve öbeği değişen işler için `motor.oneri_hesapla(conn, task_nolar)`. Bu adım kontrol ve öneriyi yazar, `hazir_zamani`'nı doldurur ve otomatik altyapı bağlantısını kurar.
8. **Kayıt.** `ice_aktarim` satırı sayaçlarla birlikte `durum='tamam'` olarak yazılır. `raporda görülen ama sözlükte olmayan mahalleler` sözlüğe eklenir. **COMMIT.**
9. **Sonrası** (işlem dışında):
   - `Yayin.bildir()` (§4.7);
   - ham dosya kopyası: `operasyon/veri/ham/`;
   - 7 günden eski ham dosyalar silinir;
   - kapanışının üzerinden 30 gün geçmiş işlerin `musteri_ad`, `musteri_no` ve `adres` alanları `NULL` yapılır.

**Hata olursa:** ROLLBACK yapılır ve `ice_aktarim` satırı `durum='hata'` ile ayrı bir işlemde yazılır. Hata mesajı
Türkçedir. Örnek: "Raporda eksik sütun: Task No. BOSS'tan 'Teknik Task Detay Raporu'nu seçtiğinizden emin olun."

**Performans bütçesi:** 1.628 satırlık rapor için ayrıştırma ≤ 3 sn, işlem ≤ 1 sn. Başka bir isteğin içe
aktarım sırasında beklemesi ≤ 100 ms olmalı (denetimde 3,3 sn ölçülmüştü).

### 4.5 Klasör izleme

`operasyon/v2/izleyici.py`: lifespan'de başlatılan bir daemon iş parçacığıdır. Yalnız `ayar.izleme_acik=1` ise
çalışır; `OPERASYON_IZLEME_KAPALI=1` tanımlıysa (testlerde) hiç başlamaz.

- 5 saniyede bir `izleme_klasoru/izleme_desen` taranır. Bir dosya şu koşullarda "hazır" sayılır:
  - değişiklik zamanı son işlenenden yeni;
  - boyutu art arda iki taramada aynı;
  - adı `~$` ile başlamıyor.
- Dosya salt okunur açılır (Excel dosyayı kilitliyorsa bir sonraki taramada yeniden denenir). Ardından `ice_aktar(…, yontem='klasor', anlik=dosyanın değişiklik zamanı)` çağrılır.
- Durum `ayar` tablosuna yazılır: `izleme_son_tarama`, `izleme_son_dosya`, `izleme_son_hata`. Panoda başlık altında bir hap olarak görünür: "Klasör izleme açık · son dosya 11:38".
- Aynı dosya iki kez görülürse SHA sayesinde işlem yapılmaz.

### 4.6 API uçları

Genel kurallar:

- Hepsi `/api` altında, Bearer jeton ile çalışır. Hata biçimi `{hata, kod}`, metinler Türkçedir.
- Yazma uçları `surum` alır. Sürüm eşleşmezse **409 `degisti`** döner ve yanıtta işin güncel hâli bulunur.
- Yönlendirici: `operasyon/v2/api.py` (`/api/is`, `/api/obek`, `/api/mahalle`, `/api/teknik`, `/api/takip`). Kişi uçları `saha/api.py` içindedir.

**Liste ögesi** (`IsSatiri`; kişisel veri alanları role göre sunucuda çıkarılır):

```json
{
  "task_no": "4xxxxxxxx", "kaynak": "boss", "kanal": "global",
  "task_adi": "Bağlantı Problemi", "serit": "BTK", "hedef_saat": 12,
  "asama": "atanacak", "kontrol": [],
  "il": "Bursa", "ilce": "Nilüfer", "mahalle": "Görükle",
  "obek": {"id": 3, "ad": "Görükle"}, "obek_elle": false,
  "bina": {"serial": "BN-…", "ad": "X Sitesi B Blok"}, "konum_yaklasik": false, "lat": 40.22, "lon": 28.87,
  "musteri": {"no": "12345678", "ad": "…"},
  "adres_kisa": "X Sitesi B Blok, 12. Sk",
  "acilis": "2026-09-30 09:40:00", "hedef": "2026-09-30 21:40:00", "son24": "2026-10-01 09:40:00",
  "ilk_gorulme": "2026-09-30 11:38:05", "atama_zamani": null,
  "teknisyen": null,
  "oneri": {"teknisyen": {"id": 12, "ad": "M. K."}, "bas": "2026-09-30 11:00:00", "bit": "2026-09-30 13:00:00",
            "neden": "Görükle öbeğinin teknisyeni · bugün 9/15"},
  "randevu": null, "sira": null,
  "ticket": {"id": 88, "konu": "SİNYAL", "durum": "AÇIK", "gun": 3},
  "rozetler": ["yeniden_acildi", "tekrar", "bayi", "konum_yaklasik", "boss_islenecek", "boss_celiski", "obek_degisti"],
  "boss": {"durum": "Açık", "ekip": "—", "islendi": false, "dogrulandi": false},
  "surum": 7
}
```

Liste yanıtının zarfı: `{sunucu_zamani, son_olay_id, isler: IsSatiri[]}`. İstemci saatleri `sunucu_zamani` ile
cihaz saati arasındaki farkı düzelterek yerelde canlı işletir.

| Uç | Rol (eylem) | Girdi → Çıktı |
|---|---|---|
| `GET /api/is?asama=&obek_id=&teknisyen_id=&serit=&q=&acik=1` | `is.liste` | Zarf. Varsayılan: bütün açık işler (≤ 2.000; süzme istemcide) |
| `GET /api/is/ozet` | `is.liste` | `{acik, asan24, asan48_btk, atanacak, kontrol, masada, konum_belirsiz, eslesmemis_ekip:[{ekip, is}], son_rapor:{zaman, dk_once}, izleme:{acik, son_dosya, hata}, obekler:[{id, acik, geciken, btk, kontrol}]}` |
| `GET /api/is/{task_no}` | `is.liste` ya da kendi işi | IsSatiri + `{adres, olaylar:[…], ticketlar:[…], bina_karti}`. Kişisel veri görüldüyse erişim kaydı yazılır |
| `POST /api/is/{task_no}/ata` | `is.ata` | `{teknisyen_id, randevu_bas, randevu_bit, randevu_tur, surum}` → IsSatiri. `atanacak`/`evde_yok`/`atandi` → `atandi` |
| `POST /api/is/onayla` | `is.ata` | `{isler: {task_no: surum}}` → `{atanan:[task_no], atlanan:[{task_no, kod, hata}]}`. Önerisi olanlar toplu atanır; her iş kendi sürümüyle denetlenir |
| `POST /api/is/{task_no}/gecis` | Geçişe göre (§2.2) | `{hedef, surum, neden?, uyanma?, evde_miydi?, sonuc?, notu?, offline_id?, zaman?}` → IsSatiri. `hedef` ∈ yolda, sahada, bitti, evde_yok, aski, altyapi, masada, atanacak, iptal, geri_al |
| `POST /api/is/{task_no}/masa` | `is.ata` | `{sonuc: duzeldi\|evde\|baska_gun\|ulasilamadi, bas?, bit?, surum}` → BTK teşhis sonucu (§2.4) |
| `POST /api/is/{task_no}/obek` | `is.ata` | `{obek_id \| null, surum}` → `obek_elle=1` (null ise 0: mahalleye dön) |
| `POST /api/is/{task_no}/mahalle` | `is.ata` | `{mahalle_id, surum}` → `mahalle_elle=1`, öbek yeniden çözülür |
| `POST /api/is/{task_no}/ticket` | `is.ata` | `{ticket_id}` → bağlar. `DELETE /api/is/{task_no}/ticket/{ticket_id}` ayırır |
| `POST /api/is/{task_no}/not` | `is.ata` | `{notu ≤1000}` |
| `POST /api/is/{task_no}/boss-islendi` | `is.ata` | `{islendi: bool}` |
| `POST /api/is/{task_no}/kopya` | `is.pii` | `{tur:'musteri_no'}` → 204 (yalnız erişim kaydı) |
| `POST /api/is` | `is.ata` | Bayi işi `{musteri_no, musteri_ad, task_adi, adres?, bina_serial?, mahalle_id?, notu?}` → IsSatiri (`B-…`) |
| `POST /api/is/ice-aktar` | `is.ice_aktar` | Gövde: xlsx baytları; başlık `X-Dosya-Adi`, `X-Dosya-Zamani` (ISO; istemcideki `File.lastModified`); `?zorla=1`. Yanıt: 200 `{kod:'tamam'\|'ayni_dosya', aktarim:{…sayaçlar}}` · 202 `{kod:'kismi_onay', aktarim_id, onceki, simdi}` · 409 `{kod:'eski_rapor'}` · 413 · 422 |
| `POST /api/is/ice-aktar/{id}/onayla` | `is.ice_aktar` | `{mod:'tam'\|'kismi'\|'vazgec'}` |
| `GET /api/is/ice-aktarimlar?limit=20` | `is.ice_aktar` | Geçmiş (kişisel veri yok) |
| `GET/PUT /api/is/izleme` | GET `is.ice_aktar`, PUT `is.izleme_ayar` | `{acik, klasor, desen}`; PUT klasörün var olduğunu doğrular |
| `GET /api/is/degisen?since=<olay_id>&bekle=25` | Rol kapsamında | Uzun sorgu (§4.7) → `{son_olay_id, isler: IsSatiri[], gorunmez: task_no[]}` |
| `GET /api/is/excel?asama=&obek_id=` | `is.pii` | xlsx (kişisel veri dahil); erişim kaydı `tur='excel'` |
| `POST /api/is/dagit/onizle` | `is.ata` | `{obek_id, teknisyen_idler:[…]}` → `{gruplar:[{teknisyen_id, isler:[task_no], btk, km}]}` (`yakinlik.dengeli_bol`, aynı bina bölünmez) |
| `POST /api/is/dagit/uygula` | `is.ata` | Önizleme gövdesi → `oneri_teknisyen_id` ve `parca` yazılır (atama yapılmaz) |
| `GET /api/obek` | `is.liste` | `[{id, ad, teknisyen, yedek, mahalleler:[{il, ilce, mahalle, il_k, ilce_k, mahalle_k, is}], sayilar:{acik, geciken, btk, kontrol}, surum}]`; iş olmayan öbekler dahil |
| `POST /api/obek` | `obek.duzenle` | `{ad}` → boş öbek; 409 `ad_var` |
| `PATCH /api/obek/{id}` | `obek.duzenle` | `{ad?, teknisyen_id?, yedek_teknisyen_id?, surum}` |
| `POST /api/obek/{id}/mahalle` | `obek.duzenle` | `{refler:[{il_k, ilce_k, mahalle_k}], tasi:false, surum}` → 409 `baska_obekte` + `cakisma:[{ref, obek_id, obek_ad}]`; `tasi:true` ile taşır |
| `DELETE /api/obek/{id}/mahalle` | `obek.duzenle` | `{refler, surum}` → öbek boş kalabilir |
| `DELETE /api/obek/{id}` | `obek.duzenle` | `?surum=` → `{geri_al: <obek_gecmis.id>, acik_is: n}` |
| `POST /api/obek/geri-al` | `obek.duzenle` | `{gecmis_id}` → yalnız son 10 dakika ve yalnız aynı kişi için |
| `POST /api/obek/{id}/bol` | `obek.duzenle` | `{k, onizle: bool}` → mahalleye göre kalıcı bölme (C21) |
| `GET /api/mahalle?q=&il=&ilce=&limit=50` | `is.liste` | `[{id, il, ilce, ad, kaynak, obek:{id, ad}\|null, is}]` + her ilçe için `{ilce_tamami:{il_k, ilce_k, obek}}` |
| `GET /api/ilce` | `is.liste` | 23 ilçe |
| `POST /api/mahalle` | `obek.duzenle` | `{il_k, ilce_k, ad, benzerine_ragmen?:false}` → 409 `benzer_var` + `oneriler:[…]`; yoksa yeni satır |
| `GET /api/teknik/islerim` | `is.kendi` | Kendi `atandi`/`yolda`/`sahada`/`evde_yok` işleri (bugün ve gecikenler), `sira` sırasıyla + bina kartı (hafif) |
| `POST /api/teknik/goruldu` | `is.kendi` | `{task_nolar}` → ilk kez görülen işlerde `gorulme_zamani` |
| `POST /api/teknik/sira` | `is.kendi` | `{task_no, yeni_sira, neden}` |
| `GET /api/takip?gun=` | `takip.oku` | Manşet, hız hattı (`[{adim, medyan_dk, p90_dk, n, hedefte_oran}]`), uyum, birikim eğimi, kapasite, 17:00 kontrolü, teknisyen ve öbek tabloları, satış kartı, sistem kartı |
| `GET /api/kullanici/{id}/bagimlilik` | `ekip.yonet` | `{silinebilir, acik_is, sayilar:{tablo.sutun: n}, etiketler:[{metin, sayi}]}`: `pragma_foreign_key_list` ile kullanici'ye giden **bütün** FK'lar sayılır; yeni tablolar kendiliğinden girer |
| `DELETE /api/kullanici/{id}` | `ekip.yonet` | 204 · 409 `isi_var` (sayılarla) · 409 `kendini_silemez` · 409 `son_yonetici`. Tek işlem; `IntegrityError` burada yakalanır ve 409'a çevrilir (global 503 işleyicisine gitmez) |
| `POST /api/kullanici` (var) | `ekip.yonet` | `rol` ∈ 4 rol; bölge yalnız satışta zorunlu; teknik alanları: `boss_ekip`, `kapasite`, `ev_obekleri:[id]` |
| `POST /api/kullanici/{id}/davet` | `ekip.yonet` | Yeni 6 haneli kod → `{davet_kodu, gecerlilik}` (yalnız bu yanıtta) |
| `PUT /api/teknik/yoklama` | `is.ata` | `{tarih, kullanici_id, durum}` |

`GET /api/kullanici` artık `davet_kodu` döndürmez; yerine `davet_bekliyor: bool` döner.

### 4.7 Canlı güncelleme: uzun sorgu

EventSource, Authorization başlığı taşıyamaz. Bu yüzden SSE yerine `fetch` ile **uzun sorgu** kullanılır; bugünkü
Bearer jeton olduğu gibi çalışır.

- **`operasyon/v2/yayin.py`:** `Yayin` nesnesi. Alanları: `son_id: int`, lifespan'de yakalanan olay döngüsü (`loop`) ve `asyncio.Event`.
  - Her yazma işleminin COMMIT'inden sonra `yayin.bildir(son_olay_id)` çağrılır. Bu çağrı threadpool'dan geldiği için `loop.call_soon_threadsafe(...)` kullanılır.
- **`GET /api/is/degisen`** `async def` olarak yazılır:
  1. `since < son_id` ise hemen döner.
  2. Değilse `bekle` saniye (en fazla 25) olayı bekler.
  3. Sonra `SELECT DISTINCT task_no FROM is_olay WHERE id > ?` sorgusunu ve satırları `run_in_threadpool` ile okur.
  4. Teknik rol için yalnız kendi işleri döner. Başkasına verilen işler `gorunmez` listesine girer ve istemci onları listesinden çıkarır.
- **İstemci döngüsü:** sekme görünürken sürekli çalışır. Hata olursa 5 sn, sonra 15 sn bekleyip yeniden dener. Sekme gizlenince durur; görünür olunca hemen bir istek atar.
- **Service worker:** `/api/is/degisen` isteği ağdan gider, önbelleğe alınmaz. `/api/teknik/islerim` önce ağdan denenir, ağ yoksa önbellekten verilir (çevrimdışı liste için).
- **Hedef:** operatörün onayından teknisyenin ekranına ≤ 2 sn.
- **Tek süreç:** uygulama tek uvicorn süreciyle çalışır. `Yayin` ve kilitler bu süreçte yaşar; birden çok işçi süreci **kullanılmaz** (baslat.bat'ta `workers=1`).

### 4.8 Eşzamanlılık

- **İş satırı:** her yazma şu tek ifadeyle yapılır: `UPDATE is_emri SET …, surum=surum+1 WHERE task_no=? AND surum=?`. Etkilenen satır 0 ise işlem 409 `degisti` ile döner ve yanıtta işin güncel hâli bulunur. İstemci bir bildirim gösterir ("Bu iş az önce değişti: <kişi> atadı") ve çekmeceyi yeniler.
- **Öbek:** öbek başına `surum` tutulur. Mahalle ekleme ve çıkarma aynı kuralla korunur. `obek_mahalle` birincil anahtarı bir mahallenin iki öbekte olmasını veritabanı düzeyinde engeller.
- **İçe aktarım ve atama aynı anda.** İçe aktarım yalnız BOSS ayna alanlarını yazar; atama yalnız bizim alanlarımızı. İkisi de `surum` artırır. İçe aktarım bizim alanlarımıza hiç dokunmadığı için, içe aktarım sırasında atama yapan operatör en kötü ihtimalle bir kez 409 alır ve yeniden dener. İstemci bu yeniden denemeyi otomatik bir kez yapar.
- **Toplu onay:** `onayla` her işi kendi sürümüyle yazar. Kısmi başarı normaldir ve yanıt `atanan` ile `atlanan` listelerini ayrı verir.
- **Çevrimdışı teknisyen:** `offline_id` benzersizdir; aynı basış iki kez gelirse ikincisi sessizce kabul edilir ve bir şey değişmez. Olayın zamanı cihazdaki basış anıdır (`zaman`); sunucu kendi anını `kayit_zamani`na yazar. Geç gelen bir "Yola çıktım" basışı iş zaten `sahada` ise yalnız olay olarak kaydedilir, aşamayı geri almaz.
- **Uzun işlemler** threadpool'da çalışır: içe aktarım, Excel, dağıt önizlemesi. Olay döngüsü üzerinde kilit tutulmaz. Aynı düzeltme `tur_raporu_yukle` ve `onemap_yukle` uçlarına da uygulanır.
- **Isınma yarışı:** `dsale.metrics`, `dsale.partition` ve `shapely` lifespan'de, `yield`'den önce eşzamanlı olarak içe alınır. Arka plan ısınma iş parçacığı kaldırılır.

### 4.9 Modül arayüzleri

Ajanlar bu imzalara göre paralel çalışır.

```python
# saha/yetki.py
YETKI: dict[str, frozenset[str]]
def izinli(k: dict, eylem: str) -> bool
def yetki_gerekli(*eylemler: str) -> Callable[..., dict]          # FastAPI bağımlılığı; 403 'yasak'

# saha/goc.py
def bekleyen(conn) -> list[str]
def v2(conn) -> list[str]                                          # G1..G5, idempotent
# saha/yedekle.py
def goc_yedegi(etiket: str = "oncesi") -> Path                     # doğrulanmış; başarısızsa istisna

# operasyon/v2/sozluk_db.py
def sozluk(conn) -> ie.Sozluk                                     # bina: DB'den; loc: normalleştirilmiş
def obekler(conn) -> ie.Obekler                                   # DB'deki öbeklerden (ie.hazirla ile uyumlu)
def mahalle_ara(conn, q, il_k=None, ilce_k=None, limit=50) -> list[dict]
def mahalle_ekle(conn, il_k, ilce_k, ad, kullanici, benzerine_ragmen=False) -> dict   # BenzerVar istisnası

# operasyon/v2/ice_aktar.py
@dataclass class AktarimSonucu: kod: str; aktarim_id: int | None; sayac: dict; uyari: list[str]
def ice_aktar(conn, veri: bytes, dosya_adi: str, anlik: datetime, yontem: str,
              kullanici: dict | None, mod: str = "otomatik", zorla: bool = False) -> AktarimSonucu
def kismi_onayla(conn, aktarim_id: int, mod: str, kullanici: dict) -> AktarimSonucu

# operasyon/v2/motor.py
ASAMALAR: dict[str, str]; ACIK: frozenset[str]; SERITLER: dict; GECISLER: dict[tuple[str, str], frozenset[str]]
def serit(task_adi: str) -> tuple[str, int]                        # (şerit, hedef_saat)
def oneri_hesapla(conn, task_nolar: list[str] | None = None) -> int
def obek_yeniden_coz(conn) -> list[str]                            # öbeği değişen task_no'lar
def ata(conn, task_no, teknisyen_id, bas, bit, tur, kullanici, surum, kaynak="elle") -> dict
def onayla(conn, isler: dict[str, int], kullanici) -> dict
def gecis(conn, task_no, hedef, kullanici, surum, **alanlar) -> dict   # GecersizGecis, Degisti istisnaları
def satir(conn, task_no, kullanici) -> dict                        # IsSatiri, rol kapsamlı
def liste(conn, kullanici, **suzgec) -> list[dict]
def ozet(conn, simdi) -> dict
def takip(conn, gun) -> dict
def pii_temizle(conn, simdi) -> int

# operasyon/v2/obek.py
def olustur / adlandir / mahalle_ekle / mahalle_cikar / sil / geri_al / teknisyen_ata (conn, …, kullanici, surum)

# operasyon/v2/yayin.py
class Yayin: son_id: int; def bildir(self, olay_id: int) -> None; async def bekle(self, since: int, sn: float) -> int
```

Ön yüzde yeni klasörler şunlardır:

- `saha_app/src/operasyon/` (index.tsx, Pano.tsx, IsListesi.tsx, IsCekmecesi.tsx, ObekDuzenle.tsx, MahalleSecici.tsx, Kontrol.tsx, YeniIsEmri.tsx, Dagit.tsx, klavye.ts, api.ts, tipler.ts, depo.tsx: uzun sorgu ve önbellek)
- `saha_app/src/teknik/` (Islerim.tsx, IsKarti.tsx, SonucCekmecesi.tsx, api.ts)
- `saha_app/src/yonetici/ekran/Takip.tsx`

Paylaşılan tipler `saha_app/src/api/is_tipleri.ts` dosyasındadır (tek sahibi A3'tür, §7).

### 4.10 Eski uçlar ve komut satırı

- **`/api/is-emri/*` (pickle):** v2 göçünden sonra GET uçları bir sürüm boyunca çalışır. POST uçları 410 `yenilendi` döner: "İş emirleri ekranı yenilendi; sayfayı yenileyin." Böylece önbellekte eski arayüz kalmış olsa bile `obekler.json`'a yazılamaz. `operasyon/testler/test_is_emri.py` buna göre güncellenir. `son_yukleme.pkl` okunmaz; 30.09 raporu yeniden bırakılarak DB'ye alınır.
- **`IS_EMRI_HAZIRLA.bat` / `python -m operasyon.is_emri RAPOR.xlsx`** (C16 makrosu) çalışmaya devam eder. `saha/saha.db` varsa öbekleri oradan **salt okunur** alır; yoksa `obekler.json`'dan okur. Öbek tablosu kipi (`OBEK_TABLOSU.xlsx` → `obekler.json`) şu mesajla kapatılır: "Öbekleri artık Sevk panosu → Öbekler'den düzenleyin."
- **`dsale/`, satış uçları, bölge planlayıcı, tur raporu, ticket defteri** değişmez. Yalnız yetki bağımlılıkları değişir.

### 4.11 Güvenilirlik kontrol listesi

- [ ] Açılışta port kontrolü göçten önce yapılıyor.
- [ ] Göçten önce doğrulanmış bir yedek alınıyor; yedek başarısızsa göç yapılmıyor.
- [ ] Tablo yeniden kurmak tek işlemde yapılıyor ve COMMIT'ten önce doğrulanıyor.
- [ ] `ziyaret` yeniden kurulumundaki (eski göç) atomik olmama sorunu da aynı kalıba çevriliyor ve silinen iki indeks yeniden kuruluyor (`ix_ziyaret_bina`, `ix_ziyaret_kullanici`, IF NOT EXISTS). Bu hata canlı DB'yi etkilemiyor, ama eski yedekten geri dönüşte ortaya çıkar.
- [ ] Yeni tablolarda dar CHECK yok.
- [ ] İz tablolarının kişiye FK'sı yok.
- [ ] İçe aktarım tek işlemde; aynı dosya etkisiz; eski rapor reddediliyor; kısmi rapor onay istiyor.
- [ ] Kişisel veri saklama süreleri uygulanıyor.
- [ ] Yedekler `journal_mode=DELETE` ile yazılıyor (yan dosya oluşmuyor).
- [ ] `saha/gizli.key` güncellemede korunuyor (§4.1 kopyalama listesi).

---

## 5. Tasarım sistemi

### 5.1 Tokenlar

Tek kaynak `saha_app/src/stil/temel.css :root` blokudur. Yönetici CSS'indeki (`yonetim.css`, `faz2.css`,
`is_emri.css`) 70'i aşkın sabit hex bu tokenlara taşınır.

Karanlık mod iki yoldan açılır:

- `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }`
- `:root[data-theme="dark"] {…}`

Tema seçimi "Daha → Tema: Sistem · Açık · Koyu" ile yapılır ve cihazda hatırlanır. `<meta name="theme-color">` iki
moda göre ayrı verilir.

| Token | Açık | Koyu | Kullanım |
|---|---|---|---|
| `--zemin` | `#EFF1F5` | `#0B0D12` | Sayfa zemini |
| `--kart` | `#FFFFFF` | `#161A22` | Kart, çekmece, liste satırı |
| `--kart-bas` | `#F7F8FA` | `#1D222C` | Basılı / seçili satır, ikincil yüzey |
| `--cizgi` | `#E2E6ED` | `#2A303B` | Ayraç |
| `--metin` | `#101828` | `#F2F4F7` | Ana yazı |
| `--metin-2` | `#525C6B` | `#B4BCC8` | İkincil yazı |
| `--metin-3` | `#626B7A` | `#8B94A3` | Üçüncül yazı (her iki modda ≥ 4,5:1) |
| `--birincil` | `#0B63E5` | `#2563EB` | Birincil düğme zemini (beyaz yazıyla ≥ 5:1) |
| `--birincil-yazi` | `#0B63E5` | `#7AB0FF` | Bağlantı, metin düğme |
| `--birincil-yumusak` | `#E7F0FF` | `#15233D` | Seçili segment, çip |
| `--ok` / `--ok-zemin` | `#1E7B34` / `#E7F5EA` | `#6FD08C` / `#12291A` | Kalan süre yeşil, "Hepsi yerinde" |
| `--uyari` / `--uyari-zemin` | `#8A5300` / `#FFF3DC` | `#FFC766` / `#33260F` | %50–80 arası, bayat rapor |
| `--kritik` / `--kritik-zemin` | `#B42318` / `#FDECEA` | `#FF8A80` / `#3A1A1C` | %80 üstü, gecikti, Kontrol, Sil |
| `--btk` / `--btk-zemin` | `#6B3FD4` / `#EFE9FC` | `#B79CFF` / `#241A3D` | BTK rozeti |
| `--notr` / `--notr-zemin` | `#525C6B` / `#EEF1F5` | `#B4BCC8` / `#232833` | Bilgi rozetleri (Bayi, Konum yaklaşık) |
| `--golge-cekmece` | `0 8px 32px rgba(16,24,40,.16)` | `0 8px 32px rgba(0,0,0,.5)` | Çekmece |

Bütün metin ve zemin çiftleri **≥ 4,5:1** kontrastı sağlar; QA betiği bunu ölçer (§6). Öbek renkleri yalnız 8 px'lik
bir nokta olarak kullanılır; öbek adı nötr metin rengindedir. Denetimdeki "mavi yazı koyu zeminde 3,16:1" sorunu bu
kuralla kapanır.

### 5.2 Tipografi, boşluk, hedef

- **Yazı tipi:** sistem yazısı (`-apple-system, "SF Pro Text", Roboto, "Segoe UI", sans-serif`).
- **Boyutlar:** 28/34 başlık · 22/28 bölüm · 17/22 satır başlığı · 15/20 gövde · 13/18 ikincil. **12 px'ten küçük yazı yoktur** (denetimde 10,5 px vardı).
- **Rakamlar:** saat, sayaç ve tablo rakamları `font-variant-numeric: tabular-nums` ile yazılır.
- **Boşluk:** 4'ün katları (4 · 8 · 12 · 16 · 24 · 32). Kart iç boşluğu 16, liste satırı dikey 12.
- **Köşe:** kart 16, düğme ve çip 12, rozet 8.
- **Dokunma hedefi:** telefonda ≥ 48 px (teknisyen ve satışçı ekranında 56 px); masaüstünde ≥ 32 px (liste içi ikincil eylemler), birincil düğme 40 px.
- **Hareket:** çekmece 200 ms ease-out; `prefers-reduced-motion` ise hareket yoktur.

### 5.3 Bileşenler

Yeni bileşenler `saha_app/src/ortak/` altına gelir ve bütün ekranlar aynı bileşenleri kullanır. Temel olarak
satışçı uygulamasının bileşenleri alınır.

| Bileşen | Tanım |
|---|---|
| `BaslikCubugu` | 44 px başlık, solda geri ya da başlık, sağda en fazla bir eylem ya da `…` |
| `AltSekme` | 4 öğe, güvenli alan payı, etkin öğe `--birincil-yazi` renginde |
| `Segment` | 2–5 seçenek, sayaçlı; dar ekranda yatay kayar, taşmaz |
| `ListeSatiri` | Önde rozet, iki satır metin, sonda saat ya da eylem; tüm satır tıklanabilir; `content-visibility:auto` |
| `Saat` | `hedef`, `baslangic` ve `sunucuFarki` alır; kalan veya geçen süreyi yazar ve renk kuralını uygular (§2.5); dakikada bir güncellenir, son 60 dakikada saniyede bir |
| `Rozet` | Tür: btk · ticket · bayi · yeniden · tekrar · konum · boss · kontrol |
| `Cekmece` (var) | Masaüstünde ≥ 1024 px'te sağ panel (440 px), altında alttan açılan panel; `Esc` ve kaydırarak kapanır |
| `OnayCekmecesi` | `window.confirm` yerine; başlık, bir cümle etki, iki düğme (tehlikeli olan kırmızı) |
| `GeriAlBildirimi` | 10 sn, "Geri al" düğmeli |
| `DilimSecici` | 2 saatlik çipler + Yarın + Tarih; `1`–`5` tuşları |
| `KisiSecici` | Yazdıkça daralır; her kişide yük ve uzaklık (`MK · 9/15 · 1,2 km`) |
| `MahalleSecici` | Sözlük araması, ilçe grupları, "İlçenin tamamı", çoklu seçim, "listede yok" yolu |
| `BosDurum` | Simge yok; bir cümle ve bir eylem ("Rapor yok. BOSS'tan raporu indirin; sistem kendisi alır.") |
| `Kbd` | Masaüstünde tuş ipucu; dokunmatik cihazda gizli |
| `Manset` | Tek satırda sakin sayılar; her sayı tıklanınca süzer |

### 5.4 Masaüstü ve telefon kuralları

| Genişlik | Yerleşim |
|---|---|
| ≥ 1200 | 3 sütun: öbekler 280 · liste esnek · çekmece 440 (listenin üstüne biner, sayfa yeniden akmaz) |
| 1024–1199 | 2 sütun: liste + çekmece; öbekler üstte seçici |
| 768–1023 | Tek liste; çekmece alttan yarım ekran, kaydırınca tam |
| < 768 | İterek gezinme; alt sekme; çekmece tam ekran; **iç içe kaydırma yok**; başlık eylemleri tek `…` altında; tablo yok, satır listesi var |

Yönetici ekranlarındaki tablolar (Ekip, Kapsama, Veri kalitesi) 600 px'in altında satır listesine döner. Manşet
kutuları alt alta dizilir ve değerler sağa yaslanır (Kapsama ve Veri kalitesindeki çakışmalar bu kuralla kapanır).
Segment dar ekranda yatay kayar. Hiçbir genişlikte yatay sayfa kaydırması olmaz.

### 5.5 Dil ve biçim

| İç sözcük / eski | Ekranda |
|---|---|
| triyaj, kontrol listesi | **Kontrol** ("Kontrol bekleyen 3") |
| parça, Böl (binaya göre), Süzüleni böl | **Ekiplere dağıt** |
| Böl (mahalleye göre) | **Öbeği ikiye böl** |
| hazır, S1 | **Atanacak** |
| öbek | **öbek** (kullanıcının kelimesi). İlk görüşte tek cümle açıklama: "Öbek: birlikte çalışılan mahalle grubu." |
| ilçe merkezi / kaba konum | **Konum yaklaşık** |
| RES HP, yarıçap 11,1 km | İş emri ekranlarında görünmez |

- **Sayılar:** `1.234`, `%52`, `3,5 km`.
- **Tarih ve saat:** `30.09.2026`, `14:05`, `bugün 14:05`, `yarın 09:00`.
- **Süreler:** `7 sa 12 dk`, `45 dk`, `3 g`.
- **Göreli zaman:** "az önce", "7 dk önce".

Biçimleyiciler `ortak/bicim.ts` dosyasında: bugünküler + `sure(dk)` + `goreli(zaman, simdi)`.

---

## 6. Kabul testleri (F1–F22)

Yerleşim:

- **Otomatik testler:** `pytest` → `saha/testler/test_v2_*.py` ve `operasyon/testler/test_v2_*.py`.
- **Tarayıcı testleri:** Playwright → `saha_app/qa/v2/*.mjs`; ekran görüntüleri `saha_app/qa/v2/` altında (git dışı).
- **Ortam:** testler canlı dosyalara dokunmaz. `SAHA_DB`, `OPERASYON_OBEK`, `OPERASYON_VERI` karalama klasöründeki kopyaları gösterir; `OPERASYON_IZLEME_KAPALI=1`.
- **Gerçek raporla testler** yalnız `BOSS_GERCEK_RAPOR` ortam değişkeni tanımlıysa koşar ve yalnız toplam sayıları doğrular.

| F | Kabul ölçütü | Otomatik test |
|---|---|---|
| **F1** | Öbek açılınca mahalleleri listelenir; mahalle çıkarılıp eklenebilir; iş sayıları 1 sn içinde güncellenir; son mahalle çıkınca öbek kalır | `test_v2_obek.py::test_mahalle_cikar_ekle_sayilar_aninda`, `::test_son_mahalle_obegi_silmez`, `::test_baska_obekteki_mahalle_409_ve_tasi`; `qa/v2/obek-duzenle.mjs` (1440 ve 393) |
| **F2** | Rapor dışı mahalle (Gürsu ve altındaki bir mahalle; listede olmayan "Göçmen" elle) öbeğe eklenir; ilçenin tamamı 23 ilçenin hepsinde eklenebilir; o mahalleden sonradan gelen iş kendiliğinden öbeğe düşer | `test_v2_sozluk.py::test_23_ilce`, `::test_rapor_disi_mahalle_eklenir`, `::test_listede_olmayan_elle_eklenir_benzer_uyarisi`, `::test_sonraki_rapordaki_is_obege_duser` |
| **F3** | Dumlupınar (Nilüfer) öbeğine tıklanınca işleri gelir. Her satırda müşteri, adres, task, aşama, kalan süre, randevu ve teknisyen var; satır sayısı öbek sayacına eşit | `test_v2_api.py::test_obek_isleri_alanlar` (operasyon rolüyle); `qa/v2/obek-isleri.mjs` |
| **F4** | Location Id'si olan işte mahalle, veritabanındaki binanın OneMap mahallesi olur; sıfırı düşmüş Lokasyon eşleşir; kontrol listesinde yalnız 3 neden var | `test_v2_ice_aktar.py::test_lokasyon_sifirli_eslesir`, `::test_kontrol_yalniz_gercek_sorun`; gerçek rapor (koşullu): Lokasyon 332/332 |
| **F5** | İl'i İzmir olan iş Kontrol'e "il_disi" nedeniyle düşer; elle öbeğe atanınca Atanacak olur; aynı rapor yeniden yüklenince elle atama korunur | `test_v2_ice_aktar.py::test_il_disi_elle_obek_kalici` |
| **F6** | Her rol kendi ana ekranında açılır; yasak uçlar 403 döner; bölgesi olmayan teknik ya da operasyon satış haritasını ve ziyaret yazmayı açamaz | `test_v2_yetki.py::test_uc_rol_matrisi` (her uç × 4 rol, beklenen kod tablosu), `::test_bolgesiz_teknik_sehri_goremez`, `::test_teknik_ziyaret_yazamaz`; `qa/v2/rol-girisleri.mjs` |
| **F7** | Operasyon atar → iş teknisyenin İşlerim ekranında ≤ 2 sn içinde görünür; "görüldü" damgası yazılır | `test_v2_canli.py::test_atama_uzun_sorguya_2sn_icinde_duser`; `qa/v2/ata-teknik.mjs` (iki tarayıcı bağlamı) |
| **F8** | Tarih + 2 saatlik aralık girilir; İşlerim randevuya göre sıralanır; geçersiz aralık 422 döner | `test_v2_motor.py::test_randevu_dogrulama`, `::test_islerim_randevu_sirali` |
| **F9** | Açık ticket'lı binadaki iş otomatik Altyapı olur ve rozet alır; elle bağla ve ayır çalışır; ticket ÇÖZÜLDÜ olunca iş Atanacak'a döner | `test_v2_ticket.py::test_otomatik_altyapi`, `::test_elle_bagla_ayir`, `::test_cozulunce_geri_doner` |
| **F10** | Uçtan uca: içe aktarım → atanacak → atandı → görüldü → yolda → sahada → bitti → sonraki raporda yok → kapandı; geçersiz geçiş 409 | `test_v2_akis.py::test_uctan_uca`, `::test_gecersiz_gecis_409`, `::test_evde_yok_merdiveni`, `::test_geri_al_10dk` |
| **F11** | Takip paneli manşet, hız hattı ve kapasiteyi gösterir; her ekranda en fazla 1 birincil düğme var; gösterim verisi bandı operasyon ekranlarında yok; `window.confirm` kullanılmıyor | `qa/v2/denetim.mjs`: birincil sayısı ≤ 1, `confirm` kancası hiç tetiklenmiyor, bant yok; ekran görüntüleri |
| **F12** | Kişi çekmecesinde 4 görev var; teknik ve operasyon kaydedilir; bölge yalnız Satış'ta zorunlu | `test_v2_ekip.py::test_dort_rol_kaydedilir`, `::test_bolge_yalniz_satista`; `qa/v2/ekip.mjs` |
| **F13** | İşi olan kişi silinemez: 409, sayılar ve "Pasife al" önerisi; kaydı olmayan kişi silinir (204); kişi kendini silemez; son yönetici silinemez; hata 503 olarak dönmez | `test_v2_ekip.py::test_isi_olan_silinmez`, `::test_bos_hesap_silinir`, `::test_kendini_silemez`, `::test_son_yonetici`, `::test_fk_hatasi_503_degil` |
| **F14** | Yeni başlayan testi: rehbersiz ilk işi 2 dakikada atar. Otomatik vekil ölçüt: pano açıldıktan sonra en acil iş ilk satırda ve en fazla 2 etkileşimle (`O` ya da "Onayla") atanıyor; her ekranda "Bu ekranda ne yaparım?" cümlesi var; §5.5'teki iç sözcükler ekranda geçmiyor | `qa/v2/ilk-gun.mjs` (etkileşim sayısı ve süre); `qa/v2/sozcuk-tarama.mjs`. Ayrıca bir kişiyle 1 oturum elle denenir ve süre not edilir |
| **F15** | Takip panelindeki satış kartındaki sayılar `/api/ozet/gun` ile aynı; karttan Canlı durum açılır | `test_v2_takip.py::test_satis_karti` |
| **F16** | Bayi işi `B-…` kimliğiyle açılır ve öneri alır; `kanal` Satış Kanalı'ndan türer; BOSS'ta aynı müşteri no ve aynı task ile görünen iş birleşir | `test_v2_bayi.py::test_bayi_is_ac`, `::test_kanal_turet`, `::test_boss_ile_birlesir`, `::test_coklu_aday_elle` |
| **F17** | İçe aktarımdan atamaya geçen süre her iş için ölçülür; atanmamış satırda 15 dk saati görünür; Takip'te medyan ve "≤ 15 dk" oranı var | `test_v2_takip.py::test_hiz_hatti_dondurulmus_saat` (saat dondurulur); `qa/v2/saatler.mjs` |
| **F18** | Aynı rapor iki kez yüklenince hiçbir şey değişmez; düşen iş kapanır; yeniden gelen iş yeniden açılır; kısmi rapor onay ister; eski rapor 409; eski sürümle yazma 409; atamalar yeni rapordan sonra korunur | `test_v2_ice_aktar.py::test_ayni_dosya_etkisiz`, `::test_kaybolan_kapanir`, `::test_yeniden_acilir`, `::test_kismi_onay`, `::test_eski_rapor`, `::test_atamalar_korunur`; `test_v2_eszamanli.py::test_surum_409`, `::test_ice_aktarim_sirasinda_atama` |
| **F19** | Bütün yeni ekranlar 1440×900, 1366×768 ve 393×852'de, açık ve koyu modda: yatay taşma yok, üst üste binen öğe yok, telefonda dokunma hedefi ≥ 44 px, metin kontrastı ≥ 4,5:1 | `qa/v2/matris.mjs` (7 ekran × 3 genişlik × 2 tema; ölçümler JSON olarak yazılır ve eşik aşılırsa betik başarısız olur) |
| **F20** | Canlı yedeğin kopyasında güncelleme: 10 kişi 10 sütunda aynı, PIN'ler, oturum numaraları, 1.257 ziyaret, diğer tablolar bayt olarak eşit; FK kontrolü 0; eski jetonlar hâlâ 200 döner; göç öncesi yedek alınmış ve doğrulanmış; ikinci açılış etkisiz; COMMIT'ten önce çökmede değişiklik yok; port doluyken göç yok | `test_v2_goc.py::test_canli_kopya_birebir` (`SAHA_CANLI_YEDEK` ile koşullu), `::test_eski_sema_checksiz`, `::test_bilinmeyen_rol_rollback`, `::test_cokme_enjeksiyonu`, `::test_ikinci_kosu_etkisiz`, `::test_port_doluyken_goc_yok`, `::test_goc_yedegi_dogrulanir` |
| **F21** | Operasyon müşteri adını ve no'sunu görür; teknik yalnız kendine atanmış açık işte görür, başka işe erişince 403 alır; satış 403 alır; erişim kaydı yazılır; kapanıştan 30 gün sonra alanlar NULL olur | `test_v2_pii.py::test_rol_kapsami`, `::test_erisim_kaydi_gunde_bir`, `::test_saklama_suresi`, `::test_liste_yanitinda_pii_yok_teknik` |
| **F22** | Her ajan kendi F satırlarını test ve ekran görüntüsüyle kapatır; GEREKSINIMLER §F'nin Durum sütunu ve notları güncellenir; "Şu an ne durumdasın?" sorusunun cevabı §0.2 tablosunun güncel hâlidir | §7'deki kapılar; `GEREKSINIMLER.md` farkı |

**Regresyon.** Bugünkü ≈213 test yeşil kalmalı. Yetki değişikliği nedeniyle güncellenen testler (`test_yetki.py`,
`test_bolgeleme.py:204-211`, `operasyon/testler/test_is_emri.py`) değişiklik notuyla güncellenir; beklentiler
gevşetilmez.

---

## 7. İş planı: 5 ajan, 2 gün

**Dosya sahipliği çakışmaz.** Paylaşılan iki dosyanın tek sahibi vardır:

- `saha/api.py`: sahibi **A1**. A3'ün yönlendiricisini `include_router` ile bağlama satırı da A1'dedir.
- `saha_app/src/api/is_tipleri.ts`: sahibi **A3**. İlk saatte §4.6'daki JSON'dan üretilir.

| Ajan | Kapsam | Dosyalar | F |
|---|---|---|---|
| **A1 · Veri, göç, yetki** | G1–G5 göçü, göç yedeği, açılış sırası, `yetki.py` ve bütün rol denetimlerinin çevrilmesi, `/api/ben` dalları, kişi silme, bağımlılık, davet süresi, ısınma yarışı | `saha/db.py`, `saha/goc.py`, `saha/yedekle.py`, `saha/sunucu.py`, `saha/ayarlar.py`, `saha/yetki.py`, `saha/api.py`, `saha/yonetim_uclari.py`, `saha/testler/test_v2_goc.py`, `test_v2_yetki.py`, `test_v2_ekip.py` | F6, F12, F13, F20 (+F21'in sunucu kapsamı) |
| **A2 · İçe aktarım ve motor** | `sozluk_db`, `ice_aktar`, `motor`, `obek`, `izleyici`, tohumlar, eski uçlara 410, CLI'nin DB'den okuması | `operasyon/v2/{sozluk_db,ice_aktar,motor,obek,izleyici}.py`, `operasyon/is_emri.py` (yalnız DB okuma ve loc normalleştirme), `operasyon/api.py` (410), `operasyon/testler/test_v2_{ice_aktar,motor,sozluk,obek,akis,bayi,ticket}.py` | F1, F2, F4, F5, F8, F9, F10, F16, F18 |
| **A3 · API ve canlı güncelleme** | `operasyon/v2/api.py` uçları, `yayin.py`, kişisel veri projeksiyonu, erişim kaydı, Excel, takip hesapları, service worker kuralları, `is_tipleri.ts` | `operasyon/v2/{api,yayin,takip}.py`, `saha_app/src/sw.js` (yalnız iki kural), `saha_app/src/api/is_tipleri.ts`, `operasyon/testler/test_v2_{api,canli,pii,takip,eszamanli}.py` | F3, F7, F15, F17, F21 |
| **A4 · Operasyon ekranları** | Sevk panosu (masaüstü ve telefon), iş çekmecesi, Kontrol, öbek düzenleyici, mahalle seçici, Ekiplere dağıt, Yeni iş emri, klavye, tokenlar ve karanlık mod | `saha_app/src/operasyon/**`, `saha_app/src/ortak/{Saat,Rozet,OnayCekmecesi,GeriAlBildirimi,DilimSecici,KisiSecici,MahalleSecici,BaslikCubugu,AltSekme,Manset}.tsx`, `saha_app/src/stil/temel.css`, `yonetim.css`, `faz2.css` (yalnız token geçişi) | F1, F2, F3, F5, F8, F9, F11, F14, F16, F19 |
| **A5 · Teknik, Ekip, Takip, yönlendirme, QA** | İşlerim, sonuç çekmecesi, çevrimdışı kuyruk; Ekip (4 rol, silme, "Görevleri gözden geçirin", davet); Takip paneli; `App.tsx`, `oturum.tsx`, `AltBar`, `Kabuk` menüsü; giriş klavyesi; Canlı → Atama düzeltmesi; bütün `qa/v2` betikleri | `saha_app/src/teknik/**`, `yonetici/ekran/{Ekip,Takip,Canli}.tsx`, `App.tsx`, `depo/oturum.tsx`, `ortak/AltBar.tsx`, `yonetici/ortak/Kabuk.tsx`, `ekran/Giris.tsx`, `saha_app/qa/v2/*.mjs` | F6, F7, F11, F12, F13, F14, F15, F17, F19 (+F22 ölçümü) |

**Gün 1**

| Saat | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| 0–1 | `KULLANICI_TANIMI`, G1–G2 SQL | `serit`, `ASAMALAR`, `GECISLER` | `is_tipleri.ts`, sahte (mock) veriyle uçlar | Tokenlar, `Saat`, `Rozet`, `ListeSatiri` | Rol yönlendirmesi, `ana_ekran` |
| 1–4 | Göç + yedek + testler (karalama kopyasında) | `sozluk_db` (loc normalleştirme, 332/332), tohumlar | `yayin`, `degisen`, PII projeksiyonu | Sevk panosu (mock), klavye | İşlerim (mock), Ekip formu |
| 4–8 | `yetki.py`, rol denetimleri, kişi silme | `ice_aktar` (upsert, fark, kısmi, eski), `motor.oneri_hesapla` | Bütün uçlar gerçek motora bağlanır | İş çekmecesi, Kontrol, öbek düzenleyici | Takip paneli (mock), giriş klavyesi |
| Kapı | `pytest` yeşil; canlı yedeğin kopyasında göç provası (sayılar birebir) | Gerçek raporla iki içe aktarım: ikincisi etkisiz | Rol matrisi testi | 1440 ve 393'te ekran görüntüsü | Rol girişleri e2e |

**Gün 2**

| Saat | Herkes |
|---|---|
| 0–3 | Mock'lar kaldırılır; 127.0.0.1:8090–8099'da test sunucusu (canlı DB'nin kopyası + gerçek rapor); uçtan uca akış (F10) iki tarayıcıda |
| 3–5 | `qa/v2/matris.mjs` (F19), `denetim.mjs` (F11), `ilk-gun.mjs` (F14); bulunan hatalar sahibine gider |
| 5–7 | Düzelt, tekrarla; performans bütçesi (§4.4) ölçülür |
| 7–8 | GEREKSINIMLER §F güncellenir; SAHA_KULLANIM'a "Güncelleme adımları" ve "Sevk panosu" bölümleri eklenir; kullanıcıya kısa durum raporu (yalnız toplam sayılar) |

**Canlı sistemi koruyan kurallar** (bütün ajanlar için):

- Canlı `saha/saha.db`'ye yazılmaz. Kullanıcının sunucusu durdurulmaz.
- Test sunucuları yalnız 127.0.0.1:8090–8099'da çalışır ve iş bitince kapatılır.
- `operasyon/obekler.json` yalnız okunur.
- Ekran görüntüleri yalnız `saha_app/qa/v2/` altına kaydedilir.
- Commit yapılmaz.
- Kullanıcının güncellemesi, §4.1'deki adımlarla onun kendi eliyle yapılır.

---

## 8. Riskler ve önlemler

| Risk | Önlem |
|---|---|
| Rol eklenince yetki sızıntısı (bölgesi NULL olan yeni rol şehrin tamamını görüyor) | Varsayılan olarak red; `yetki.py`; rol matrisi testi her uç için (F6) |
| Göç sırasında veri kaybı ya da FK kayması | Yeni kur → kopyala → eskiyi düşür → yeniden adlandır; tek işlem; COMMIT öncesi doğrulama; göç öncesi doğrulanmış yedek; port kontrolü önce; canlı kopyada prova (F20) |
| Teknisyen sahada ağa bağlanamıyor (VPN yok) | Liste önbellekte, durum kuyrukta, olay zamanı cihazdan; Takip "gecikmeli bildirim" oranını gösterir; VPN, BT kararı 13 |
| Rapor bilgisayarda değil, başka yere iniyor | Sürükle-bırak aynı hattı kullanır; bayat rapor uyarısı (30/60 dk) |
| Sözlükte mahalle eksik (Göçmen, Yalova köyleri) | Elle ekleme ve benzer ad uyarısı; takma ad tablosu; tam resmî liste için sözlük yükleyici (Açık soru 5) |
| Öneri yanlış kişiye gidiyor (öbek teknisyeni tanımsız) | Öneri nedeni satırda yazar; teknisyeni olmayan öbek "Teknisyen yok" rozetiyle görünür ve öneri boş kalır (Onayla düğmesi yerine Ata) |
| Kişisel veri yayılması | Rol projeksiyonu sunucuda; erişim kaydı; Excel yalnız iki role; saklama süreleri; ham dosyalar 7 gün |
| `obekler.json` git'e girmesi ya da ezilmesi | v2 bu dosyaya hiç yazmaz; güncelleme listesinde "üzerine yazma"; yansılar `operasyon/veri/` altında (git dışı) |
| İçe aktarım sırasında sunucunun donması | `def` uç + threadpool + ayrıştırma işlem dışında; bütçe testi |
| Birikimin 15 dk metriğini bozması | Metrik yalnız sistem çalışırken doğan işlerde (§2.5) |
| Uygulamayı kullanmayan teknisyen | Atama ve BOSS Ekip eşleşmesi yine çalışır; "görüldü" ölçülmez, Takip ayrı gösterir |

---

## 9. Açık sorular (kullanıcı kararı)

1. **Teknik müşteri bilgisini görsün mü?** Öneri: yalnız kendine atanmış **açık** işte müşteri adı ve no; iş kapanınca gizlenir. (OPERASYON_TASARIM §5.4 "gösterilmez" diyordu; F21 "teknik yalnız kendi işini" diyor.)
2. **Kişisel veri saklama:** müşteri adı, no ve adres kapanıştan 30 gün sonra silinsin mi? Ham dosya 7 gün mü kalsın?
3. **Rol adı** `teknik` olsun mu? "Teknik lider" ve masa etiketleri rol değil etiket olarak Faz 2'ye kalsın mı?
4. **F16:** BOSS "Satış Kanalı" sütunu doğru sinyal mi? GLOBAL = dış kanal, DEHA ve DEHANET ECM = bayi, boş = bilinmiyor.
5. **Mahalle listesi:** Bursa'nın 17 ilçesi ve Yalova'nın 6 ilçesi için eksiksiz liste nereden alınacak (BursaStateList'in tamamı, UAVT, OneMap)? "Göçmen" hangi ilçede?
6. **BOSS Ekip adları:** her teknisyenin BOSS'ta hangi adla yazıldığını içeren listeyi kim verecek? (Faz 0 maddesi: "BOSS Ekip adı ↔ kişi ↔ ev öbeği".)
7. **Giriş ekranı:** C9'daki üç kutu yerine rol hesaptan gelsin mi (öneri: evet)?
8. **BOSS raporu hangi bilgisayara iniyor?** Klasör izleme yalnız sunucunun çalıştığı bilgisayarda (10.54.3.75) çalışır.
9. **Sahadan erişim:** VPN + HTTPS için BT'ye ne zaman gidilecek? O gelene kadar teknisyen listesini ofis Wi-Fi'de alır.
10. **Kurulum filtresi:** "Kurulum Taskı Ürememiş" ve "Kurulumsuz …" adlı işler mevcut müşteride kalsın mı? (C5 ile C17 çelişiyor.)
11. **Kişi silme kuralı:** yalnız hiç kaydı olmayan hesap silinsin, geçmiş kaydı olan kişi yalnız pasife alınsın mı? Bugün 8 hesapta gösterim ziyaretleri var; gösterim verisi temizlensin mi (önce yedekle)?
12. **Müşteri telefonu** sisteme hiç girmesin mi (öneri: girmesin; arama BOSS/Maya'dan)?
