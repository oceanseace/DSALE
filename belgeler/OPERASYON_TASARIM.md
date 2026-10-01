# Operasyon Tasarımı: Her iş emri 24 saatte sonuçlanır

*Dehanet EÇM (Bursa + Yalova) · mevcut müşteri iş emirleri · 30.09.2026*
*Dayanak: 29.09 BOSS/FOX dışa aktarımları, 1-15 Eylül kapanışları (yalnız toplu sayım), 7 stratejinin
ayrık olay simülasyonu ve üç bağımsız hakem incelemesi (toplam 2.000'i aşkın koşu). Belgede kişisel veri yoktur;
yalnız sayım, oran, ilçe ve saat vardır.*

---

## 0. Önce: senin gününde ne değişiyor

| Bugün | Yeni düzende |
|---|---|
| BOSS raporunu indirip elle süzüyorsun, kurulumları ayıklıyorsun. | Zaten yaptık: raporu **İş emirleri** ekranına bırakıyorsun (ya da `IS_EMRI_HAZIRLA.bat`). Buna FOX açık + askı dosyaları eklenir. Sistem her işe şerit, öbek, bina ve **24 saat saati** verir. |
| Ofis her işi bir kez arıyor. Ulaşamayınca "ulaşılamadı" notu düşüp işi 11:00 dilimine yazıyor. Açık 601 işin 518'inde bu not var, 298'inin dilimi geçmiş. | **Kimse işi önceden aramaz.** Saha işi doğrudan öbeğinin teknisyenine gider. Masa yalnız üç şeyi arar: BTK arızasını 30-45 dk içinde teşhis için (iş sahadaki sırasını kaybetmez), evde bulunamayan müşteriyi ve Kanal Şikayeti'ni. |
| Teknisyen hangi işe gideceğini listeden kendisi seçiyor. Kapasite yetmeyince "en eski önce" gidiyor, bu da BTK'yı gömüyor. | Senin **öbeklerin** sevk birimi olur. Yoğun öbek her sabah parçalara bölünür, her parça bir teknisyenin günüdür. Sıra kuralı kapasiteye göre kendiliğinden değişir (§2.4). |
| BTK arızası diğer işlerle aynı kuyrukta bekliyor. | BTK **hızlı şeritte**: Turkcell hedefi (TV 6 s, Bağlantı 12 s) sıralamayı belirler. Masa paralel teşhis yapar. 48 saati aşan her BTK işi ertesi sabah ilk dalgaya, isimli sahibiyle girer. |
| Sinyal, güzergah, port sorunu olan binaya teknisyen boşuna gidiyor. Ticket'lar Excel'de. | Açık ticket'ı olan binaya teknisyen **gönderilmez**; iş ticket'a bağlanır. Bina başına tek OneDesk ticket açılır, metni hazır gelir (Ticketlar ekranı zaten var). |
| Gün sonunda ne kadar geciktiğimizi kimse sayıyla bilmiyor. | 17:00'de "ekibi boş yeni iş = 0" kontrolü yapılır. 17:30'da günlük rapor çıkar. Hasan Bey her sabah **kapasite göstergesini** görür: "bugün şu kadar teknisyen lazım, şu kadar var". |

**Senin masan** yalnız şunlarla dolar: sadece FOX'ta görünen BTK Şikayet ve BTK/Mahkeme işleri (4 saat hedefli), 48 saati aşan
BTK işleri, OneDesk ve ONENT kayıtları, tekrar eden arızalar, FOX ile BOSS'un çeliştiği kayıtlar. Geri kalanını
sistem ve masa yürütür.

---

## 1. Hedef ve bugünkü durum

### 1.1 Tek cümlelik hedef

> **Kurulum dışındaki her iş emri geldiği andan itibaren 24 saat içinde sonuçlanır. BTK arızaları Turkcell'in 6/12
> saatlik hedefine göre önde yürür ve hiçbir BTK işi 48 saati geçmez.**

"Sonuçlanır" demek: iş sahada bitti, telefonda doğrulanarak kapandı ya da gerekçeli bir istisnaya alındı (müşteri
talepli ileri randevu, altyapı ticket'ı, 3 denemede ulaşılamadı). İstisnada da saat durmaz; istisnalar ayrı raporlanır.

### 1.2 Bugün (29.09.2026, sayılarla)

| Ölçü | Değer |
|---|---|
| BOSS'ta açık iş | **2.567**: mevcut müşteri 953, yeni kurulum 1.614 |
| Senin kapsamın (17:55 dışa aktarımın) | **601**. Bu sayı yaklaşık 953 − 2.Donanım 125 − Cihaz İade 218 ≈ 610'a denk geliyor |
| 24 saati geçmiş mevcut müşteri işi | **%73** (703/953); medyan yaş 55,7 saat |
| Gerçek 24 saat uyumu (1-14 Eylül'de açılan işler) | **%43**. 1 Eylül'de %65 iken 12-14 Eylül'de **%21-24**'e düştü |
| BTK uyumu | Bağlantı 24 s'te %53, Turkcell'in 12 s hedefinde %30. TV 24 s'te %50, 6 s hedefinde %20 |
| Gelen iş (mevcut müşteri) | Takvim günü ortalaması 323. Hafta içi 338, Çarşamba 417, Cumartesi 384, Pazar 182. Tepe saat 09:00 (%13) |
| Kapanan iş | Hafta içi ~224/gün. Her gün 80-110 iş devrediliyor; birikim 15 günde **+1.180** arttı |
| Arıza ekibi | 12 kişi, günde ~10 aktif, kişi başı 17 kapanış. İlk kapanış saati medyanı **11:04**. Kapanışların **%34**'ü bir öncekinden 5 dakikadan kısa arayla yapılıyor (toplu kapatma) |
| "Arama sağlandı, ulaşılamadı" notu | Açık 601 işin **518**'inde var; notların %90'ı tek bir ofis kullanıcısından. Dilimi geçmiş ama hâlâ açık **298** iş var; 189 dilim 11:00'de başlıyor |
| Ziyaretsiz kapanış | BTK arızalarının %44'ü: telefon/uzaktan %30, şebeke %12 |
| Kanal Şikayeti | %98'i ofisten "düzeldi" ile kapanıyor, ama medyan **169 saat** askıda bekliyor. 24 s uyumu %3 |
| Tekrar arıza | Aynı müşteride 15 gün içinde **%35** |
| Yalnız FOX'ta kalan iş | 56; aralarında 5 BTK Şikayet ve 1 BTK/Mahkeme (4 s hedefli). Bunlar BOSS'a hiç düşmüyor |
| FOX askıda, BOSS'ta açık | 78 iş (kayıt çelişkisi) |
| Konum | Makro 601 işin 601'inde mahalleyi buldu, 492'sini tam binasına koydu |

### 1.3 Neden geç kalıyoruz: dört kök neden

1. **Kapasite yetmiyor.** Günde ~200 saha ziyareti gerekiyor (hafta içi 338 işin ~%59'u); arıza ekibi 10 aktif × 17 ≈ 170 yapıyor. Aradaki fark her gün birikime ekleniyor.
2. **Süreç kapasiteyi yiyor.** "Önce ara, ulaşamazsan varsayılan dilime yaz" düzeni hem gereksiz arama hem çürüyen iş üretiyor. Simülasyonda bugünkü süreçte darboğaz 2 kişilik ofis araması (%100 dolu): teknisyen sayısı 24'e çıksa bile 24 s uyumu %31'de kalıyor. **Önce süreç değişmeli, sonra kadro.**
3. **Tempo.** İlk kapanış 11:00 civarında. Toplu kapatma yüzünden işin gerçekte ne zaman bittiği bilinmiyor.
4. **Yanlış sıra.** Kapasite kıtken "en eski önce" kuralı domino etkisi yapıyor: bugünün işi yarının gecikmişi oluyor ve BTK gömülüyor.

---

## 2. Kazanan strateji: KARMA-2 ve nedeni

### 2.1 Nasıl yarıştırıldı

Yedi strateji aynı gelişler, aynı müşteri davranışı ve aynı kaynakla yarıştı:

- Simülasyon adımı 5 dakika, süre 35 gün.
- Kapsam metro: Nilüfer, Osmangazi, Yıldırım, Mudanya, Gürsu, Kestel (son 24 saatteki işlerin %96'sı).
- Başlangıç: 29.09 akşamındaki gerçek birikim.
- Giriş hızı, tip payları, saat profili ve kapanış nedenleri veriden alındı.
- Ortak rastgele sayılar kullanıldı: her strateji aynı işi ve aynı müşteriyi görür, yalnız kararları ayrışır.

Sonra üç hakem sonuçları birbirinden bağımsız denetledi: bir operasyon müdürü, bir saha ekip lideri ve bir
istatistik denetçisi gözüyle. Tasarımda hiç kullanılmamış tohumlarla yeniden koştular.

Yarışan stratejiler:

| Kod | Özü |
|---|---|
| **HAM** | Senin fikrin: aramadan ekibe ver, evde olmayanı operasyon arasın. |
| **KARMA** | HAM + "24 saatine yetişecek iş önce" sırası + BTK'da masanın paralel teşhisi. |
| **DSİR** | Aramasız sevk; teknisyen her işten önce 2 kez arar, ulaşamazsa iş istisna kuyruğuna gider. |
| **RPHT** | Her işe puan verilir; BTK'yı önce masa teşhis eder, sonra sevk edilir. |
| **U1H** | Her iş önce masadan geçer (3 deneme + uzaktan teşhis + kurye), sonra sahaya. |
| **BÖLGE** | Sabit bölge takvimi, aramasız SMS dilimi, fazla rezervasyon. |
| **BUGÜN** | Bugünkü süreç (kalibrasyon için referans). |

### 2.2 Sonuç tablosu

N, hafta içi aktif arıza teknisyeni sayısıdır (Pazar ≈ 0,55·N). Değerler taze tohumlarla (301-305) 5 tekrarın
ortalaması. **KARMA-2 çekirdeği** hakem 1'in düzelttiği hâldir (HAKEM-B).

| Strateji | 24 s uyumu N=10 | N=16 | N=20 | BTK 24 s (N=16) | BTK işinde 72 s'i aşan (N=16) | 24 s üstü açık iş artışı (N=16, iş/gün) | Masa yükü (kişi-saat/gün) | Boşa ziyaret |
|---|---|---|---|---|---|---|---|---|
| **KARMA-2 çekirdeği** | **%52,5** | **%71,4** | **%79,3** | **%75,4** | %11,2 | **+17** | 32 | %18 |
| KARMA (ilk hâli) | %50,7 | %66,9 | %77,8 | %68,2 | %21,2 | +30 | 32 | %19 |
| HAM (senin fikrin) | %34,4 | %65,0 | %78,6 | %71,0 | **%6,8** | +20 | **14** | %17 |
| DSİR | %36,4 | %52,5 | %66,6 | %49,4 | %22,8 | +34 | 17 (+ teknisyen 24 arama/gün) | **%7** |
| RPHT | %40,2 | %48,4 | %60,9 | %42,3 | %44,1 | +32 | 44 | %21 |
| U1H | %18,9 | %46,1 | %59,1 | %46,5 | %36,4 | +46 | 74 | %25 |
| BÖLGE | %23,5 | %28,2 | %34,0 | %10,6 | %70,8 | +68 | 12 | %17 |
| BUGÜN (referans) | ~%24 | ~%24 | ~%25 | ~%25 | ~%62 | — | 15 (2 kişi, %100 dolu) | %14 |

Ek bilgiler:

- N=14'te: KARMA-2 çekirdeği %66,3, KARMA %60,6, HAM %51,3.
- N=16'da KARMA-2 çekirdeğinin Turkcell hedeflerindeki uyumu: TV 6 s %48, Bağlantı 12 s %51.
- N=20'de 24 saati aşan açık iş sayısı artık büyümüyor: KARMA-2 çekirdeği ≈ 0, HAM −1,7 iş/gün.

### 2.3 Hakemler ne dedi

**Hakem 1 (operasyon müdürü: 24 saat ve BTK).** Yarış tek bir skorla yapılmış: 24 saatte kapanan işlerin oranı.
Bu skor, bir işin 24 saati kaç saat aştığını hiç ölçmüyor. KARMA'nın "yetişir" sırası bu yüzden gecikmiş BTK işini,
taze ama BTK olmayan işin arkasına atıyor:

- BTK işi başına ortalama gecikme KARMA'da 51,5 saat, HAM'da 8,4 saat.
- KARMA'da BTK işlerinin %21'i 72 saati aşıyor.
- "Birikim 7 günde eriyor" ölçütü yalnız başlangıçtaki işlere bakıyor. Oysa N=16'da her stratejide yeni gecikmiş iş birikmeye devam ediyor.

Yapılan düzeltme:

- Aşırı yükte BTK her zaman önce gelir.
- Masa teşhisi yalnız işi kapatmak için yapılır.
- Ulaşılamayan iş için HAM'ın arama merdiveni kullanılır.

Sonuç: 8 duyarlılık senaryosunun 8'inde hem 24 s uyumunda hem BTK'da birinci.

**Hakem 2 (saha ekip lideri).** Model, aramadan giden stratejileri kayırıyordu. Üç saha gerçeği eklendi:

- Habersiz gidilen ve evde olan müşteriye %8 oranında yine de erişilemiyor (site kapısı, zil).
- Telefonda alınan "evdeyim" teyidi 3 saat sonra bayatlıyor.
- "Başka gün gelin" diyecek müşteri, habersiz gelen teknisyeni yarı yarıya kabul ediyor.

Bu düzeltmelerle mutlak değerler 4-10 puan düşüyor (HAM N=16'da %64 → %54), sıralama büyük ölçüde korunuyor.
Ayrıca "yetişir" sırası yalnız kapasite açığı varken işe yarıyor (N=10-12'de +8/+9 puan); kapasite yetince
BTK kuyruğunu şişiriyor. Bu yüzden sıra kuralı bir kapasite göstergesine bağlanmalı. Teknisyenin aramayı bekletmeden
yaptığı "yoldayım" araması ise zararsız: boşa ziyareti %26'dan %22'ye indiriyor.

**Hakem 3 (istatistik denetim; 10 tohum, güven aralıklı).**

- N=16'da KARMA'nın HAM'a üstünlüğü yalnız +1,6 ±1,2 puan, yani sınırda. 48 saat ölçütünde −4,8 puan geride.
- N=20'de HAM her ölçütte önde.
- KARMA'nın her kadroda net katkı veren tek parçası **BTK paralel masa teşhisi**: +2,5..+4 puan ve günde +12..17 kapanış.
- Bu hakemin iki eki sonucu iyileştiriyor:
  - "En acil 5 iş içinden en yakını" kuralı: +0,7..1 puan.
  - Telefonda müsait çıkan BTK müşterisine 3 saatlik pencere verilmesi: TV 6 s uyumu %29'dan %39'a çıkıyor.
- Uyarı: bugünkü süreç modeli gerçeğe göre karamsar (48 saatte model %29, gözlenen %59). **Mutlak iyileşme rakamları söz olarak verilmemeli.**

**Ortak karar:** Kazanan KARMA ailesi, ama düzeltilmiş hâliyle. Çekirdeği senin fikrin, üstüne BTK'da paralel
teşhis ve kapasiteye göre değişen iki modlu sıra geliyor. Bu belgede adı **KARMA-2**.

### 2.4 KARMA-2: kurallar

Her kuralın yanında hangi stratejiden alındığı yazıyor.

| # | Kural | Kaynağı |
|---|---|---|
| 1 | **İçe aktarım ve sınıflama.** BOSS + FOX dosyası her yüklendiğinde (hedef 30 dk'da bir; şimdilik günde 3 kez) her iş şeride, öbeğe ve binaya bağlanır. Adında "kurulum" ya da "2. donanım" geçen iş çıkarılır (makronun kuralı). | Makro + entegrasyon |
| 2 | **Saat.** Herkese verilen söz: son24 = açılış + 24 s. BTK'nın sıra anahtarı = açılış + Turkcell hedefi (TV 6, Bağlantı/Arama 12, Doping 24, BTK/Mahkeme 4). | DSİR, U1H |
| 3 | **Aramasız sevk.** Saha işi, mahallesinin öbeğine ve o öbeğin/parçanın teknisyenine gider. Önceden kimse aramaz. BOSS'a Ekip + gerçek tahmini varış dilimi yazılır; varsayılan 11:00 damgası yasak. | HAM (senin fikrin) + DSİR |
| 4 | **BTK paralel masa teşhisi.** BTK işi gelince masa 30-45 dk içinde bir kez arar; iş sahadaki sırasını kaybetmez. Ulaşılırsa 8-10 dk teşhis yapılır. (a) "Düzeldi", canlı testle doğrulanırsa (hız testi, kanal açılıyor) ya da şebeke kaynaklıysa iş kapanır ve saha ziyareti iptal edilir. (b) "Şimdi evdeyim" derse 3 saatlik pencere verilir, iş öne alınır; teyit 3 saat sonra bayatlar. (c) Başka gün isterse onun seçtiği dilim yazılır. Bunların dışında randevu verilmez. Ulaşılamazsa hiçbir şey değişmez. | KARMA + hakem 1, hakem 3 |
| 5 | **İki modlu sıra.** Her sabah 07:45'te kapasite göstergesi hesaplanır: bugünkü saha talebi ile aktif teknisyen × 15 karşılaştırılır. **Normal mod** (kapasite yetiyor): önce BTK, sonra en eski iş; en eski 5 aday içinden teknisyene en yakını alınır. **Aşırı yük modu** (kapasite yetmiyor): önce BTK, her zaman. BTK içinde 24 saatine hâlâ yetişebilecek iş son tarih sırasıyla alınır (TV 2 saat öne). Her 3. seçimde en eski gecikmiş BTK, her 4. seçimde en eski gecikmiş BTK dışı iş alınır. Hep "en acil 5 içinden en yakın", ama bolluğu 90 dakikanın altına düşmüş iş varsa o iş. **Normal moda dönüş:** kapasite yetiyor ve 24 saati aşan açık iş 7 gündür büyümüyor. | Hakem 1 + hakem 2 + hakem 3 |
| 6 | **Emniyet supabı.** 48 saati aşan her BTK işi ertesi sabah ilk dalgaya ve isimli bir sahibe yazılır. | Hakem 1 |
| 7 | **Aday alanı.** Teknisyen önce kendi parçasından, sonra kendi öbeğinden, sonra 3 km içinden, en son 10 km içinden iş alır. | Simülasyon, BÖLGE |
| 8 | **Evde yok merdiveni.** Teknisyen kapıda 10 dk bekler, BOSS'tan 2 kez arar, not bırakır, "evde yok" kodlar ve sıradaki işe geçer. Masa sırayla: hemen (≤60 dk), +2 saat, akşam 17:30-19:30 (ya da ertesi gün 10:00), SMS. Sonra iş 48 saat askıya alınır (BTK'da 24 saat); uyanmada son bir arama yapılır; sonuç yoksa iş Turkcell kuralıyla kapanır. Ulaşılan müşterinin seçtiği 2 saatlik dilim önceliklidir. **Aynı işe teknisyen ikinci kez habersiz gönderilmez.** | HAM + hakem 1 |
| 9 | **Yoldayım araması (pilotta ölçülür).** Teknisyen bir önceki işten çıkarken eller serbest bir kez arar. Ulaşamazsa **yine gider**. | Hakem 2 (DSİR'in yumuşatılmışı) |
| 10 | **Şebeke kümesi.** Aynı binada 2 saatte 3 ya da daha fazla, veya 300 m içinde 3 saatte 5 ya da daha fazla BTK işi gelirse işler 60 dk (TV) / 90 dk (Bağlantı) bekletilir. Altyapı masası NOC/TT'ye sorar ve bina başına tek OneDesk ticket açılır. Genel arıza yoksa bekletme hemen kalkar. | KARMA, RPHT |
| 11 | **Altyapı bayrağı.** Açık SİNYAL, EK SP, GÜZERGAH ya da ALTYAPI kaydı olan binaya teknisyen gönderilmez; iş o kayda bağlanır. | Süreç, DSİR |
| 12 | **Masa şeridi.** Kanal Şikayeti aynı gün 3 kez aranır (hemen, +3 saat, akşam); "düzeldi" ise kapanır. Askı yalnız müşteri isterse, en fazla 3 gün. Cihaz İade'de sistem kaydı 2 saat içinde kontrol edilir; cihaz hâlâ müşterideyse iş, 1 km içinde komşu işi olan bir rotaya "dolgu durağı" olarak eklenir. | RPHT, U1H |
| 13 | **Telefonla kapatmada kalite.** Canlı test şartı aranır. 7 gün içinde tekrar eden arızada telefonla kapatma yasaktır, iş kıdemli teknisyene gider. Telefonla kapananların %20'si 24 saat içinde geri aranır. Bir tipte telefonla kapananların 7 günlük tekrar oranı sahada kapananlarınkini 10 puandan fazla aşarsa, o tipte telefonla kapatma kapanır. | U1H, DSİR |
| 14 | **Masayı boşa çevirmeme.** Önceki işinde ulaşılamayan müşteriye sonraki işte de %94 oranında ulaşılamıyor. Bu müşteriye teşhis araması yapılmaz, iş doğrudan sevk edilir. Masanın bant sırası: BTK/Mahkeme > TV > Bağlantı > geri arama > Kanal. | RPHT |
| 15 | **Kapasite kaldıracı.** 07:45 esnek formülü kurulum ekiplerinden ödünç teknisyen önerir: öneri = min(8, ⌈(talep − aktif × 15) / 15⌉). İlk ziyaret 09:00'dan önce yapılır. İş bittiğinde kapatılır, toplu kapatma yapılmaz. Pazar nöbeti ≈ 0,55·N. | U1H, BÖLGE |
| 16 | **Akşam bandı.** Yalnız kadro 16-18'i geçince, 2-3 kişilik 12:00-21:00 vardiyası kurulur. Etkisi: TV 6 s uyumu +2-3 puan, 24 s uyumu −0,6..−2,8 puan. | DSİR, U1H, hakem 1 |
| 17 | **Ölçüm.** Sonuç kodları zorunludur: evde miydi; cevap / cevapsız / kapalı / yanlış numara. İlk 2 hafta işlerin %10'u kontrol grubuna ayrılır. Katsayılar haftalık ayarlanır. | RPHT, DSİR |

### 2.5 Senin fikrin ne oldu

Senin fikrin kazananın **çekirdeği** oldu. Aramadan sevk edip yalnız evde olmayanı aramak, herkesi önce aramaktan
hızlı: boşa ziyaretin bedeli (%17-18), bekletilen işin 24 saati kaçırmasından daha ucuz. "~50 iş/gün aranır"
tahminin de tutuyor: günde ~200 ziyaretin %17-18'i evde yok çıkıyor, bu da ~35-45 iş/gün eder.

İki düzeltme eklendi:

1. **Kapasite kıtken "en eski önce" çöküyor.** Bugünkü kadroda (N=10) HAM'ın BTK uyumu %23'e iniyor. Aşırı yük modu bu yüzden var.
2. **BTK'da masanın paralel teşhisi** her kadroda 2-4 puan getiriyor. Bu, "hepsini arama" ilkesiyle çelişmiyor: arama işi bekletmiyor, yalnız telefonda kapanacak işi erken kapatıyor.

Kadro 20'ye yaklaşınca sistem kendiliğinden senin sıranla (normal mod) çalışır.

### 2.6 Duyarlılık: sonuç neye bağlı

N=16. Hücrelerde 24 s uyumu / BTK 24 s. Temel satır 5 taze tohumun (301-305), senaryolar 3 tohumun (201-203) ortalaması.

| Senaryo | KARMA-2 çekirdeği | KARMA | HAM |
|---|---|---|---|
| Temel | %71 / %75 | %67 / %68 | %65 / %71 |
| Günde 3 elle dışa aktarım (30 dk yerine) | %68 / %73 | %63 / %66 | %61 / %66 |
| Evde yok %15 (iyimser) | %75 / %80 | %70 / %72 | %70 / %78 |
| Evde yok %45 (kötümser) | %62 / %62 | %58 / %56 | %50 / %47 |
| Giriş +%15 | %66 / %70 | %62 / %63 | %47 / %42 |
| Konumsuz iş ilçe merkezinde planlanırsa | %68 / %70 | %65 / %65 | %57 / %57 |
| Telefonla çözülen pay ×0,6 | %67 / %71 | %63 / %62 | %59 / %60 |
| Masa 4 kişi | %70 / %75 | %65 / %68 | %65 / %71 |
| Düşük ulaşma | %71 / %75 | %66 / %68 | %66 / %73 |

Sıralamayı değiştiren tek etken **kapasite/yük oranı**. Kapasite bolken HAM, KARMA-2 ile başa baş, BTK'da hafif önde;
KARMA-2 bu durumda zaten HAM sırasına geçiyor. Konumsuz işin ilçe merkezinde planlanması HAM'a 9 puan kaybettiriyordu;
makro artık her işi mahallesine ya da binasına koyduğu için bu risk büyük ölçüde kapandı.

### 2.7 Alınmayanlar ve nedenleri

| Fikir | Neden alınmadı |
|---|---|
| Herkesi önce aramak (bugünkü düzen, U1H) | Ulaşılamayan iş masada günlerce bekliyor. Masa 8 kişide doyuyor, 7 kişide sistem çöküyor. |
| Teknisyenin her işten önce iki kez araması, ulaşamayınca işi bırakması (DSİR) | Boşa ziyaret en düşük (%7), ama teknisyen günde ~24 arama yapıyor ve ulaşılamayan iş 24 saati kaçırıyor. |
| Önce masa, sonra saha hunisi (RPHT, U1H) | Zaten sahaya gidecek işler (~%55) masada 1-2 saat bekliyor. |
| Katı bölge dilim takvimi (BÖLGE) | Teknisyen günde ~170 dk boş kalıyor, BTK işleri günler sonrasına itiliyor. Gevşetilmiş hâli de sonuncu. |
| Saf "yetişir" sırası (KARMA'nın ilk hâli) | Gecikmiş işi terk etmeyi öğretiyor: BTK p90 ~10 gün. |

**Bu stratejilerden alınan iyi parçalar:** DSİR'den deneme sayacı, gerçek varış dilimi, tekrar koruması ve kendini ayarlama.
RPHT'den ulaşılabilirlik geçmişi, kontrol grubu ve bant sırası. U1H'den esnek formül, kalite geri araması ve kurye
(Turkcell izin verirse). BÖLGE'den günlük kadro formülü ve bölge sahipliği. Hepsi §2.4'teki kurallara işlendi.

### 2.8 Dürüst sınırlar

- **Yöntem kapasiteyi yaratmıyor.** Bugünkü 10 aktif teknisyenle en iyi kural bile %52 veriyor ve birikim yine büyüyor (metro modelinde günde ~87 iş). Denge ancak **~20 aktif arıza teknisyeninde** geliyor. Modelin varsaydığı 08:30 başlangıç ve kişi başı 15-17 ziyaret, bugünkü tempodan iyimser; aynı tempoda kalınırsa ihtiyaç %15-20 daha yüksek.
- **%90'a hiçbir kadroda ulaşılmıyor** (N=24'te ~%82). TV 6 s ve Bağlantı 12 s hedefleri N=20'de bile ~%50-55'te kalıyor. Gece ve akşam gelen BTK işleri akşam vardiyası olmadan bu hedeflere yetişemiyor.
- **Ölçülmemiş varsayımlar:** habersiz ziyarette evde yok oranı (~%22), ilk aramada ulaşma, masa teşhisinin çözme oranı (%85), ilk seferde çözüm (%92). Pilotta ilk ölçülecekler bunlar.
- **KARMA-2 tek parça olarak koşulmadı.** Parçaları ayrı ayrı ölçüldü. Beklenen düzey N=16'da %65-72 (düzeltilmiş müşteri modeliyle alt uç). Faz 1 sırasında birleşik hâli tek koşuyla doğrulanacak.
- Simülasyon yalnız metroyu kapsıyor. Kurulum ekibiyle kaynak paylaşımı ve rota eniyilemesi modellenmedi.

---

## 3. İş emrinin hayatı

### 3.1 Sınıflama: grup ve şerit

**Grup.** Task Adı'nda "kurulum" (Kurulum Taskı Ürememiş hariç) ya da "2. donanım" geçiyorsa iş **yeni müşteri**
ekibinindir ve senin kapsamın dışındadır. Bu, makronun bugünkü kuralı. Diğer işler **mevcut müşteri**, yani senin
sorumluluğun. Sınıflama BOSS adına göre yapılır; FOX adı görev sözlüğüyle çevrilir (örneğin "IP TV Kurulum" = "TV+ Kurulum",
"Bağlantı Problemleri" = "Bağlantı Problemi").

| Şerit | İşler | Kim yürütür | Hedef |
|---|---|---|---|
| **BTK** | Bağlantı Problemi, TV+ Arıza, Arama Problemi, Doping Arıza | Saha + masada paralel teşhis | Sıra: TV 6 s, Bağlantı/Arama 12 s. Söz: 24 s |
| **YALNIZ-FOX** | BTK Şikayet, BTK/Mahkeme, Donanım Teslimat Şikayet | Sen | BTK/Mahkeme 4 s |
| **SAHA** | Modem, Superbox, STB değişikliği; Teknik Servis Ücretlendirme; Evrak toplama | Saha (aramasız) | 24 s |
| **MASA** | Kanal Şikayeti, Soru-Cevap | Operasyon masası (telefon) | Aynı gün |
| **LOJİSTİK** | Cihaz İade Bekleniyor, Cihaz Geri Alım, Türksat iade | Masa kontrolü + dolgu durağı | 24-48 s |
| **ALTYAPI** | Binasında açık ticket ya da engel olan her iş | Altyapı masası + sen (OneDesk/ONENT) | Ticket'a bağlı; çözülünce 24 s |

### 3.2 Durumlar, sahipler, süre bütçesi

| Kod | Durum | Sahibi | BOSS / FOX'ta görünüşü | Süre bütçesi (standart / BTK) |
|---|---|---|---|---|
| S0 | **Geldi** | Sistem | Açık, Ekip boş / KUYRUKTA | Bir sonraki içe aktarıma kadar (hedef ≤30 dk) |
| S1 | **Sınıflandı**: şerit, öbek, bina, saat | Sistem → triyaj masası | Açık | ≤15 dk. Bağlanamayan iş triyaja düşer |
| S2 | **Kuyrukta**: öbek ve parça teknisyeni belli | Öbek sahibi teknisyen | Açık, Ekip dolu, Randevu = tahmini varış | Kesim kuralına göre (§3.3) |
| S2b | *(BTK)* **Masada teşhis**, S2 ile paralel | BTK masası | Değişmez | İlk arama ≤45 dk, teşhis ≤10 dk |
| S3 | **Yolda** | Teknisyen | Konum Paylaşıldı | ≤60 dk / ≤45 dk |
| S4 | **Sahada** | Teknisyen | Başlandı | ≤120 dk / ≤90 dk |
| S5 | **Bitti** | Teknisyen | Bitirildi | Anında kapatılır, toplu kapatma yok |
| S6 | **Doğrulandı** | Sistem | Açık listeden düştü (ve FOX'ta kapalı) | Sonraki içe aktarım. BTK telefon kapanışlarının %20'si geri aranır |

**İstisnalar** (her birinin sayacı, uyanma saati ve sahibi vardır):

| Kod | İstisna | Sahibi | BOSS'ta | Kural |
|---|---|---|---|---|
| E1 | **Evde yok / ulaşılamadı** | Masa (merdiven) | Merkeze gönder: ABONEYE ULAŞILAMADI | §3.5 merdiveni. BTK'da 24 s, diğerlerinde 48 s içinde çözülür |
| E2 | **Abone kaynaklı askı** | Masa | Askıya alındı: Abone kaynaklı | Neden + uyanma tarihi zorunlu. BTK en çok 1 gün, diğerleri 3 gün, müşteri talepli ileri randevu en çok 7 gün |
| E3 | **Altyapı** | Altyapı masası; OneDesk ticket'ını sen açarsın | Askı TT kaynaklı / Merkeze: GÜZERGAH, SİNYAL, BOŞ PORT | §3.6 |
| E4 | **Malzeme** | Lojistik | Başlandı + not | 8 s / BTK 2 s |
| E5 | **Ofisten kapandı** | Operasyon | Kapalı | Neden kodu zorunlu: telefonda çözüldü, iptal, mükerrer, FOX'ta kapalı, 3 denemede ulaşılamadı |
| E6 | **Tekrar arıza** (7 gün içinde) | Mevcut müşteri sorumlusu (sen) | Açık | Kıdemli teknisyen; telefonla kapatma yasak |

### 3.3 24 saatlik zaman bütçesi ve kesim saatleri

Standart iş için 1.440 dakika şöyle harcanır:

| Adım | Bütçe |
|---|---|
| Geldi → Sınıflandı | 30 dk (içe aktarım aralığı) |
| Sınıflandı → Kuyrukta | 15 dk (öbek sahibine otomatik) |
| Kuyrukta bekleme (gece dahil) | Kalan süre; aşağıdaki kesim kuralına göre |
| Yolda | 60 dk |
| Sahada | 120 dk |
| Kapanış ve doğrulama | ≤30 dk |

**Kesim kuralı** (müşteriye söylenen gün de budur):

| İş ne zaman geldi | En geç ne zaman biter |
|---|---|
| 00:00-12:00 | Aynı gün |
| 12:00-17:00 | Ertesi gün 12:00 |
| 17:00-24:00 | Ertesi gün 17:00 |

Bu kural her işi 24 saatin içinde tutar ve sabah gelen işi "aynı güne" döndürür.

**BTK bütçesi.** Bağlantı 12 s (720 dk): sınıflama 15, teşhis araması paralel 30-45, kuyruk ~525, yol 45, saha 90, kapanış 10.
TV 6 s (360 dk): sınıflama 10, teşhis paralel 20-30, kuyruk ~180, yol 45, saha 90, kapanış 10.
20:30-08:00 arasında gelen BTK işi ertesi sabah ilk dalgaya girer; her teknisyenin ilk 2 durağı gece gelen BTK işleridir.

### 3.4 BTK hızlı şeridi (bir Bağlantı arızasının yolu)

```
09:40  BOSS'a düştü (FOX'tan aktarım medyanı 7 sn)
10:00  İçe aktarım: şerit BTK, öbek "Görükle", bina bulundu, hedef 21:40 (12 s), söz 09:40+1g
10:00  Öbek teknisyeninin sırasına girdi (aşırı yük modunda bile BTK önde)
10:05  BTK masası aradı ─┬─ ulaşıldı, "modemi kapat-aç, hız testi" → düzeldi → KAPANDI, ziyaret iptal
                         ├─ "şimdi evdeyim" → 3 saatlik pencere, iş öne alındı
                         ├─ "yarın 10-12" → teyitli dilim, BOSS'a gerçek dilim yazıldı
                         └─ ulaşılamadı → hiçbir şey değişmez, teknisyen habersiz gider
15:10  (hedefin %50'si) hâlâ 'Yolda' değilse → vardiya lideri: araya alma
19:15  (hedefin %80'i) → sen + Hasan Bey
21:40  hedef aşıldı → günlük rapor, ertesi 08:00 ilk dalga, isimli sahip
```

### 3.5 Evde yok / ulaşılamadı merdiveni

| Adım | Ne zaman | Kim | Sonuç |
|---|---|---|---|
| Kapıda | Varışta | Teknisyen | 10 dk bekler, BOSS'tan 2 arama, kapıya not, "evde yok" kodu, sıradakine geçer |
| Deneme 1 | ≤60 dk | Masa | Ulaşılırsa müşterinin seçtiği 2 saatlik dilim (öncelikli, gerçek varış saati) |
| Deneme 2 | +2 saat | Masa | Aynı |
| Deneme 3 | 17:30-19:30 (ya da ertesi gün 10:00) | Masa (akşam bandı) | Aynı |
| SMS | Deneme 3'ten sonra | Sistem şablonu (mevcut kanal) | Müşteri masa hattını geri arar |
| Askı | +48 s (BTK +24 s) | Masa | BOSS: Askı, abone kaynaklı + uyanma saati |
| Son arama | Uyanmada | Masa | Sonuç yoksa Turkcell kuralıyla kapanış ya da merkeze gönderme (kural teyit edilecek) |

Teknisyen aynı işe ikinci kez habersiz gönderilmez. Simülasyonda bu merdiven işlerin ~%3-4'ünü 3-4 günde
"ulaşılamadı" olarak kapatıyor.

### 3.6 Eskalasyon

**Zamana bağlı eskalasyon:**

| Tetikleyici | Kime gider | Ne olur |
|---|---|---|
| BTK teşhis araması 45 dk içinde yapılmadı | Masa lideri | Kuyruk bant sırası kontrol edilir |
| Hedefin %50'si doldu, iş hâlâ "Yolda" değil | Vardiya lideri (sarı) | Araya alma: en yakın teknisyen |
| BTK'da hedefin %80'i doldu | Sen + Hasan Bey (kırmızı) | Kararı sen verirsin |
| Hedef aşıldı | Günlük rapor | Ertesi 08:00 ilk dalga, isimli sahip |
| BTK işi 48 saati aştı | Sen | Emniyet supabı (§2.4 kural 6) |
| Dilim geçti, iş "Yolda" değil | Teknisyen + atama masası | Yeni dilim ya da yeniden atama |
| "Başlandı" durumunda 12 saatten uzun kaldı | Teknik ekip lideri | Malzeme mi, kayıt mı? |
| 17:00'de ekibi boş yeni iş var | Vardiya lideri | Akşam bandına ya da ertesi sabah ilk dalgaya |
| Askının uyanma saati geldi | 08:00 kuyruğu | Masa arar |
| Aynı binada 2 saatte ≥3 / 300 m'de ≥5 BTK | Altyapı masası | NOC kontrolü (§2.4 kural 10) |

**Dışarıya eskalasyon.** Bu adımların hepsinde ticket'ı ya da talebi **sen** açarsın; sistem metni hazırlar.

- **OneDesk: sinyal, güzergah, altyapı.**
  1. Bina başına tek ticket açılır. Metin LOCS şablonuyla gelir (uygulamada "Ticket metni" düğmesi zaten var).
  2. Sen OneDesk'te açarsın, numarayı Ticketlar ekranına yazarsın.
  3. Binadaki bütün işler bu ticket'a bağlanır. BOSS'ta "Merkeze gönder: SİNYAL/GÜZERGAH/BOŞ PORT" ya da "Askı: TT kaynaklı" yapılır.
  4. Durum kontrolü: BTK işi bağlıysa 12 saatte bir, diğerlerinde günde bir. 48 saatte çözülmezse Turkcell bölgeye eskale edilir.
  5. Çözülünce binadaki işler 24 saat içinde teyitli ziyarete döner ve **bina satış listesine geri açılır** (satışçıya bildirim gider).
- **ONENT: ek kapasite (EKSP).**
  1. Port yoksa ön kontrol listesi uygulanır. Bugün EK SP taleplerinin %46'sı HATA durumunda; eksik bilgi başlıca şüpheli.
  2. Ön dolu talep metni hazırlanır, sen ONENT'te açarsın, talep numarası geri girilir.
  3. Günde bir durum kontrol edilir. Çözülünce OneDesk'teki gibi işler döner.
- **TT kaynaklı askı.** TT etiketlemesi bekleyen işler (bugün kurulumda 160, mevcutta az) haftalık toplu listeyle TT'ye gider. 48 saatte bir sorgulanır.
- **Yalnız FOX'taki BTK Şikayet ve BTK/Mahkeme (4 s).** İş anında senin masana düşer. Masa 10 dakikadan kısa sürede arar, iş ilk müsait teknisyene verilir.

### 3.7 Günün ritmi

| Saat | Ne olur |
|---|---|
| 07:45 | BOSS + FOX içe aktarım. Sistem sınıflar, kapasite göstergesini ve esnek önerisini hesaplar, öbekleri parçalara böler |
| 08:00 | 10 dakikalık toplantı. Kuyruklar sıfırlanır: gece gelen BTK, 48 s aşan BTK, uyanan askılar, kaçan dilimler, 12 saatten uzun "Başlandı"da kalanlar |
| 08:30 | İlk dalga. Her teknisyenin ilk iki durağı gece gelen BTK işleri |
| 09:00-17:00 | 30 dakikada bir içe aktarım (şimdilik 12:15 ve 16:45'te). Her teslimde yeni işler öbeklerine düşer; BTK işleri anında masaya |
| 12:30 | Kontrol: BTK riski, öğleden sonra dengeleme, evde yok 2. denemeler |
| 17:00 | Ekibi boş yeni iş = 0. Yarının taslak parçaları hazırlanır |
| 17:30 | Günlük rapor (otomatik) |
| 17:30-19:30 | Akşam arama bandı: evde yok 3. denemeler, Kanal 3. denemeleri |

---

## 4. Birikmiş işin eritilme planı

### 4.1 Başlangıç ve ilkeler

29.09'da 953 açık mevcut müşteri işi vardı; senin kapsamında 601. 24 saati geçmiş olan 703. Kovalara göre:

| Kova | İş | Sonraki adım |
|---|---|---|
| Sahaya verilebilir | 415 | Öbek kuyruğu |
| Ofisten kapatılabilir | 397 (Kanal 179, Cihaz İade 218) | Masa |
| Abone kaynaklı askıda | 112 | Masa: uyanma tarihi |
| Merkeze gönderilmiş | 26 | Masa / sen |
| İleri tarihli randevu | 3 | Bekler |

**İlkeler:**

1. **Önce musluğu kapat.** Yeni işin 24 saati korunur. Birikim ayrı kapasiteyle ve boş kapasiteyle erir. Aşırı yük modunun kotaları (her 3. ve 4. seçim) bunu kendiliğinden sağlar.
2. **Önce BTK, sonra en eski.** Birikim öbek öbek, küme hâlinde erir; teknisyen aynı sokakta 3-4 işi birlikte bitirir.
3. **Masada biten sahaya gitmez.** Kanal, Cihaz İade ve "düzelmiş olabilir" BTK işleri önce telefonla elenir.
4. **Yapılmayacaklar:** Sahaya göndermeden önce herkesi arama taraması yapılmaz. Müşteriye ulaşmadan toplu kapatma yapılmaz. Kurtarma işi taze işin önüne geçmez.

### 4.2 Gün gün

| Gün | Masa | Saha | Beklenen |
|---|---|---|---|
| **Gün 0** (karar günü, 1-2 saat) | Açık işler yeni kurallarla yeniden sınıflanır. Varsayılan 11:00 dilimleri silinir. Dilimi geçmiş 298 iş öbek sahibine yeniden yazılır | Yarının parçaları hazırlanır | Tek liste: şerit × öbek × yaş |
| **Gün 1** | Kanal 179: üç zaman bandında arama (09-12, 14-16, 17:30-19:30). Birikimdeki BTK işlerine tek "düzeldi mi?" araması; gündüz ulaşılamamış olanlar akşam bandında aranır. Askıdaki 112 işe uyanma tarihi ve neden girilir. Merkeze gönderilmiş 26 iş gözden geçirilir | Taze işler öbek sahiplerine; en eski gecikmiş BTK her 3. seçimde. Kurtarma timi onaylandıysa en yoğun öbeklerde en eski BTK'dan başlar | Kanal'da %60-80 kapanış (~110-145 iş). BTK birikiminde 50-120 ziyaretsiz kapanış |
| **Gün 2** | Kanal 3. denemeleri. Kalanlar ya müşteri talepli askıya (en çok 3 gün) ya da merdivene girer. Cihaz İade (kapsamdaysa) sistem kontrolünden geçer | Aynı | Masa kovası büyük ölçüde boşalır |
| **Gün 3-10** | Yalnız evde yok merdiveni ve yeni işler | Kalan saha birikimi (senin kapsamında ~300-350) küme hâlinde erir. Günlük kota: Q = max(0, kapasite − 1,1 × tahmini yeni saha işi). Önce en eski BTK; sonra ekleme maliyeti 12 dakikadan az olan işler; 7 günü geçen iş zorunlu eklenir | 48 s üstü BTK sıfıra iner |
| **Hafta 2-4** | Kalite geri aramaları, kontrol grubu ölçümü | 24 s üstü açık iş sayısı ve eğimi izlenir. Kapasite yetiyor ve stok 7 gündür büyümüyorsa normal moda geçilir | §4.4'teki hedef çizgisi |

### 4.3 Kurtarma timi (öneri)

Kurtarma timi 10 iş günü çalışır:

- **4 teknisyen**: kurulumdan ödünç, fazla mesai ya da geçici. Her gün 08:00'de birikimi en yoğun, henüz kimsenin almadığı öbeği alır.
- **2 kurtarma masası**: Gün 1-2'deki Kanal ve BTK doğrulama taramasını yapar, sonra evde yok merdivenine destek verir.

### 4.4 Kadroya göre ne olur

Simülasyon (metro) sonuçları:

| Aktif arıza teknisyeni | Başlangıç birikimi | Yeni gecikenler | Ne demek |
|---|---|---|---|
| **10** (bugün) | Erimez | Günde ~+87 | Yalnız BTK korunur (%50). Birikim büyür |
| **16** (örneğin bugünkü ~10 + 4 kurtarma timi + 2 esnek) | ~1 haftada erir | Günde ~+17 | Birikim erir ama sonra yavaşça yeniden birikir |
| **20** | ~1 haftada erir | ≈ 0 (denge) | 24 saati aşan açık iş ~100 civarında sabitlenir |

**Hedef çizgisi** (mevcut müşteri, 24 saati aşan açık iş). İlk iki hafta en az 16 aktif eşdeğeri, 4. hafta ve sonrası
~20 aktif eşdeğeri gerektirir:

| Başlangıç | Hafta 1 | Hafta 2 | Hafta 4 |
|---|---|---|---|
| 703 | <350 | <150 | <100 |

48 saati aşan BTK sayısı 2. haftadan itibaren 0 olmalı. Kadro 10'da kalırsa bu çizgi tutmaz; bunu ilk günden
Hasan Bey'e açıkça söylemek gerekir.

---

## 5. Ekranlar

Hepsi mevcut uygulamanın (saha/ + saha_app/) içinde. Yeni bir uygulama yok.

### 5.1 Giriş: Satış · Teknik · Operasyon

1. Açılışta üç büyük kutu: **Satış · Teknik · Operasyon**. Cihaz son seçimi hatırlar.
2. Sonra bugünkü telefon + PIN girişi (değişmez).
3. Sistem rolü denetler: satışçı Operasyon'a giremez, teknisyen yalnız kendi işlerini görür. Yönetici üçüne de girer.
4. Roller: `satisci`, `teknisyen`, `teknik_lider`, `operasyon` (masa etiketiyle: triyaj, BTK, arama, altyapı, lojistik, vardiya), `yonetici`. "Mevcut müşteri sorumlusu" (sen) yöneticinin bir etiketidir.

### 5.2 Operasyon: İş emirleri · öbekler (sabah atama panosu)

Bugünkü **İş emirleri** ekranının büyümüş hâli. Dosya bırakma, öbek yapma, Böl ve Excel zaten var; bunlara kapasite
çubuğu, şerit ve saat sütunları, teknisyen ataması ve "BOSS'a işlenecekler" listesi eklenir. (Aşağıdaki sayılar örnektir.)

```
İŞ EMİRLERİ · ÖBEKLER             BOSS 07:46 · FOX açık 07:48 · FOX askı 07:48   [Dosya bırak]
KAPASİTE  talep ~205 ziyaret · 11 teknisyen × 15 = 165  →  AŞIRI YÜK MODU · öneri: +3 esnek
─────────────────────────────────────────────────────────────────────────────────────────────
Öbek                          Açık  BTK  24s aşan  48s aşan BTK  Teknisyen       İşlem
Görükle                         31   14      9          2         sahip + 1       [Böl → 2]
Nilüfer Dumlupınar              12    6      2          0         sahip
19 Mayıs·Yüzüncüyıl·Altınşehir  44   20     15          4         sahip + 2       [Böl → 3]
Öbeksiz · Mudanya                7    3      1          0         —               [Öbek yap]
─────────────────────────────────────────────────────────────────────────────────────────────
[Parçaları ata]   [BOSS'a işlenecekler (Ekip + dilim)]   [Excel]   [Yalnız FOX: 6]   [Çelişki: 78]
```

- Satıra basınca öbeğin işleri açılır. Sütunlar: Task No, tip, şerit rozeti, bina, **kalan süre** (yeşil / sarı %50 / kırmızı %80), sıra no, sahip.
- **Böl:** Mevcut dengeli bölme kullanılır; aynı binadaki işler ayrılmaz. Parça sayısı önerisi = ⌈öbeğin bugünkü saha yükü / 15⌉.
- **BOSS'a işlenecekler:** Atama masası BOSS'a hangi işe hangi Ekip ve dilimi gireceğini buradan görür. Sonraki içe aktarımda BOSS'ta gerçekten girildi mi diye doğrulanır (giden kutusu).

### 5.3 Operasyon: Masa kuyrukları

```
MASA                                          bekleyen   en eski / sıradaki
BTK teşhis (vade 45 dk)                           18      32 dk
Evde yok merdiveni                                11      sıradaki deneme 14:30
Kanal Şikayeti                                     9      2. deneme 15:00
Kalite geri araması (%20)                          6
Uyanan askılar                                     4
```

- İşe basınca iş kartı açılır: tip, bina, deneme geçmişi, önerilen konuşma adımları (teşhis betiği).
- Telefon numarası sistemde **yoktur**. Arama BOSS/Maya'dan yapılır, sonuç tek dokunuşla kodlanır: ulaşıldı-düzeldi (canlı test), ulaşıldı-evdeyim (3 saat), ulaşıldı-başka gün (dilim), cevapsız, kapalı, yanlış numara.
- Kötü geçmişli müşteri (önceki işinde ulaşılamadı) listede gri görünür ve teşhis kuyruğuna alınmaz.

### 5.4 Teknisyenin günü (Faz 2)

```
BUGÜN · 14 iş · 3 BTK                                   Mod: aşırı yük · 1 dolgu durağı
 1  BTK  TV+ Arıza     Görükle · A Sitesi B Blok      kalan 3 s 10 dk    [Yol tarifi]
 2  BTK  Bağlantı      Görükle · 12. Sokak No 4        kalan 7 s
 3       Modem Değ.    Görükle · C Sitesi              kalan 19 s
 …
İŞ KARTI   [Yoldayım]  [Başladım]  [Bitti]  [Evde yok]  [Düzelmiş]  [Şebeke]  [Malzeme]  [Altyapı]
```

- Sıra, sistemin önerisidir (§2.4 kuralları 5 ve 7). Teknisyen değiştirebilir, ama nedenini seçer.
- **"Evde miydi"** her sonuçta zorunludur. "Evde yok"a basınca masa merdiveni anında başlar.
- Yol tarifi koordinatla açılır (satışçı ekranındaki gibi). Bina adı, Location Id ve açık ticket bilgisi kartta görünür.
- Müşteri adı ve telefonu gösterilmez; teknisyen bunlara BOSS Mobil'den ulaşır.
- İş bittiğinde kapatılır; gün sonu toplu kapatma yoktur.

### 5.5 Yönetici panosu (Hasan Bey)

| Gösterge | Hedef |
|---|---|
| **24 s uyumu** (dün gelen işler) | Ana gösterge |
| BTK 24 s · TV 6 s · Bağlantı 12 s | |
| **48 saati aşan açık BTK sayısı** ve en yaşlı BTK işinin yaşı | 0 |
| 24 saati aşan açık iş ve 7 günlük eğimi | Birikim eriyor mu? |
| **Kapasite göstergesi**: talep vs aktif × 15, mod, esnek önerisi ve gerçekleşen | |
| Boşa ziyaret oranı (evde yok) | Pilottan sonra belirlenir, ~%18'den başlar |
| BTK'da ilk arama ≤45 dk oranı; teşhisle kapanan pay | |
| Telefonla kapananların 7 günlük tekrar oranı (sahadakiyle karşılaştırmalı) | Fark ≤10 puan |
| İlk ziyaret saati (medyan) | ≤09:15 (bugün 11:04) |
| Toplu kapanış payı | <%10 (bugün %34) |
| 17:00'de ekibi boş yeni iş | 0 |
| Kayıt hijyeni: FOX/BOSS çelişkisi, dilimi geçmiş açık iş | 0 |
| Ticket yaşı; EK SP HATA oranı | %46 → <%10 |

Ayrıca **3B ikizdeki "Açık iş emri" merceği** dolar: her binanın açık işi, BTK işi ve yaşı renkle görünür.
Öbek ısı haritası da buradan açılır.

### 5.6 Senin masan: "Mevcut müşteri"

```
MASAM                                                         bugün
Yalnız FOX · BTK Şikayet / Mahkeme (4 s)         2   en yakın hedef 13:20
48 saati aşan BTK                                 5   en yaşlı 71 s
OneDesk taslakları (bina başına)                  3   [Metni kopyala] [No gir]
ONENT EKSP bekleyen                               4   2'si HATA → eksik bilgi
Tekrar arıza (7 gün)                              7   kıdemli teknisyen atandı mı?
FOX askıda / BOSS açık çelişkisi                 78   [Listeyi aç]
```

Ticketlar ekranı (defter, durum geçmişi, bina bağlantısı) olduğu gibi kalır; bu masa onun özetidir.

### 5.7 Satışa etkisi

- Satışçı bina kartından **"Sinyal yok / Ek kapasite" talebi** açar. WhatsApp'a yazmak yerine bu kullanılır; talep kayda girer.
- Açık altyapı bayrağı olan bina satış haritasında işaretli görünür. Ticket çözülünce bina satış listesine geri döner.
- Faz 3'te **"Satışlarım: kurulum durumu"** ekranı gelir.

---

## 6. Veri entegrasyonu

### 6.1 Kaynak başına önerilen yol

Kırmızı çizgiler: Turkcell sistemlerine otomatik yazma yok. Tarayıcı çerezi ya da parola saklanmaz. WhatsApp Web otomasyonu yok
(Hizmet Şartları). Veri bu bilgisayardan dışarı çıkmaz.

| Kaynak | Şimdi (Faz 1) | Sonra (BT onayıyla) | Hedef | Sıklık |
|---|---|---|---|---|
| **BOSS** açık işler | Dışa aktar → İş emirleri ekranına bırak (var). Ek olarak İndirilenler klasörü izlenir, bırakmak bile gerekmez | Yerel tarayıcı eklentisi raporu 30 dk'da bir alıp klasöre yazar | Zamanlanmış rapor ya da salt okunur API | 07:45 / 12:15 / 16:45 → 30 dk |
| **BOSS** dün kapananlar | Her sabah tarih aralıklı "Tamamlandı" raporu (gerçek süre için) | Aynı | API | Günde 1 |
| **FOX** açık + askı | İki dosya birlikte (15 dk içinde). Akış No = BOSS Task No | Köprü | API | Günde 2-4 |
| **OneDesk** | Sistem ticket metnini üretir, sen yapıştırırsın, numarayı geri yazarsın (var) | Sayfayı okuyan yer imi | Salt okunur API | Açarken + günde 1 durum |
| **ONENT** EKSP | Ön dolu talep + talep no geri girişi | Yer imi | API | Açarken + günde 1 |
| **OneMap** | Uygulamanın ürettiği hazır sorgu adresi (100'lük kimlik grupları) → JSON kaydet → bırak (var) | Köprü, ayda 1 tam çekim | Servis hesabı | Yeni binalar + ayda 1 |
| **Tur raporu** | Sürükle → fark önizleme → onay → uygula (var) | Paylaşılan klasöre teslim | — | Geldikçe |
| **Outlook** | Ticket çözüldü mailinde durumu elle güncelle | Paylaşılan kutu + EWS | — | Düşük öncelik |
| **WhatsApp** | Kaynak taşınır: satışçı talebi bina kartından açar; gerekirse "Sohbeti dışa aktar" .txt | — (otomasyon yasak) | — | — |

### 6.2 Her yüklemede ne olur

1. **Tanı.** Dosyanın BOSS mu FOX mu olduğu anlaşılır. Doğru sayfa bulunur (başa eklenen pivot sayfası sorun değil).
2. **Çevir.** FOX ve BOSS görev adları sözlükle ortak koda çevrilir (33 FOX adı).
3. **Bina.** Lokasyon yalnız rakamsa 8 haneye sıfırla tamamlanır ve binaya bağlanır. Bağlanamazsa adresteki site adı ya da mahalle merkezi kullanılır (makro bunu bugün yapıyor).
4. **Fark.** Bir önceki yüklemeyle karşılaştırılır: **yeni**, **değişen**, **listeden düşen** (kapandı sayılır, "dün kapananlar" raporuyla doğrulanır) ve **yeniden açılan**. Gerçek 24 saat saati buradan çıkar; BOSS açık raporunda Task Bitiş neredeyse hiç dolu değil.
5. **Uzlaştır.** İş FOX'ta var BOSS'ta yoksa ya da tersiyse işaretlenir. FOX'ta askıda olup BOSS'ta açık görünen iş masaya düşer.
6. **Giden kutusu.** Sistemin önerip operasyonun BOSS'a elle girdiği şeyler (Ekip, dilim, askı, kapatma) bir sonraki yüklemede "gerçekten girildi mi" diye kontrol edilir.

### 6.3 Tur raporu ve OneMap yenilemesi

Tur raporu yükleme akışı çalışıyor: yükle → fark (yeni, çıkan, sayısı değişen, geri dönen) → uygula. Çıkan bina
silinmez, pasife alınır; iz `bina_degisim` tablosunda kalır. Yeni binanın konumu OneMap aracından gelir.
Location Id'deki baştaki sıfır kaybı (2.335 bina) veri kalitesi motorunda düzeltildi; iş emri eşlemesi aynı kuralı
(yalnız rakamsa 8 haneye tamamla) kullanır. OneMap'in "son düzenleme tarihi" alanı artımlı çekim için güvenilmez; bu
yüzden kimlik bazlı çekim yapılır ve ayda bir tam çekimde fark aranır.

### 6.4 Dinamik bölge ve öbek planı

İki ayrı katman var:

| Katman | Kimin | Neyle tanımlı | Nasıl değişir |
|---|---|---|---|
| **Satış bölgesi** | Satışçılar | Bina (Bölge planlayıcı, var) | Satışçı sayısı değişince önizle → uygula → geri al |
| **Operasyon öbeği** | Teknisyenler | Mahalle grubu (`obekler.json`, senin tanımın) | Sen düzenlersin; sistem ayda bir öneri yapar |

- **Öbekler mahalleyle tanımlı olduğu için tur raporu ve OneMap yenilemesinden etkilenmez.** Yeni bina mahallesiyle birlikte kendiliğinden öbeğine düşer. Öbeği olmayan mahalledeki iş "Öbeksiz · ilçe" satırında görünür; tek tıkla bir öbeğe eklenir.
- **Teknisyen sahipliği:** Her arıza teknisyeninin 1-2 "ev öbeği" olur (hesap verebilirlik, yol kısalığı). Günlük parçalar bu sahiplikten başlar. Esnek teknisyenler en yüklü öbeklere gider.
- **Aylık denge önerisi:** Son 28 günün saha yükü öbek başına hesaplanır. ±%15 sapma varsa sistem bir öneri üretir ("bu öbeği ikiye böl", "bu iki küçük öbeği birleştir"); uygulama senin onayınla olur.
- **Teknisyen sayısı değişince** öbekler sabit kalır, yalnız sahiplik yeniden dağıtılır. Bunun için öbek merkezleri üzerinde aynı dengeli bölme (`operasyon/yakinlik.py`) kullanılır.
- **Uzak ilçeler** (Yalova, İnegöl, Gemlik-Orhangazi, Karacabey): kendi öbeğinde yerleşik ya da hibrit teknisyen olur. Açık işlerin %7'si Yalova'da, oysa yeni girişte payı ~%1,5; Yalova'da iş birikiyor.

### 6.5 Gizlilik

- Telefon numarası sisteme girmez; BOSS dışa aktarımında zaten yok.
- Müşteri adı maskelenir. Adres yalnız bina bulunamadıysa tutulur ve kapanıştan 30 gün sonra silinir. Ham dosyalar 7 gün sonra silinir.
- Raporlar ve yönetici panosu yalnız toplu sayı gösterir.
- Analiz çıktılarından biri (`operasyon/analiz/cikti/is_emri_analizi.json`) ekip listesi içeriyor; yalnız-toplu-veri kuralı gereği temizlenmeli.
- **Acil:** PS26 deposu tur raporunu ve müşteri no'lu listeleri GitHub Pages'e itiyor. Pages varsayılan olarak herkese açıktır; bu KVKK md. 9 (yurt dışına aktarım) riski doğurur. Yayın kapatılmalı.

---

## 7. Veri modeli eklemeleri

Tam SQL taslağı `operasyon/analiz/entegrasyon.md` §5.3'te. Burada yalnız ne var, ne eklenecek ve KARMA-2'nin ne
istediği yazıyor.

**Zaten var:**

- Tablolar: `kullanici`, `bina`, `ziyaret`, `gorev`, `bolge_plani`, `tur_raporu`, `bina_bekleyen`, `bina_degisim`, `ticket`, `ticket_gecmis`.
- `operasyon/obekler.json` (öbek tanımları).
- `son_yukleme.pkl`: yalnız son BOSS yüklemesi. Faz 1'de tablolara taşınır, çünkü fark ve 24 saat saati için geçmiş gerekiyor.

**Faz 1'de eklenecekler:**

| Tablo | Ne tutar | KARMA-2'deki işi |
|---|---|---|
| `kaynak_senkron` | Her yükleme: kaynak, dosya özeti, anlık zamanı, yeni/kaybolan sayıları | Fark, tazelik uyarısı |
| `gorev_tipi` | FOX↔BOSS ad sözlüğü, şerit, BTK bayrağı, Turkcell hedefi, bayi hedefi | Sınıflama, saat |
| `is_emri` | İşin güncel hâli (Task No = Akış No). Eklenen alanlar: `serit`, `obek`, `parca`, `hedef_zaman`, `son24`, `durum_kodu` (S0-S6, E1-E6), `deneme_sayaci`, `uyanma`, `tekrar7g`, `kontrol_grubu`, `kotu_gecmis` | Her şey |
| `is_emri_gecmis` | Yalnız eklenir, hiç güncellenmez: alan değişiklikleri, kayboldu, yeniden açıldı | Gerçek süre, denetim |
| `obek`, `obek_mahalle` | Öbek adı, ev teknisyeni, aktif; mahalle (il/ilçe/mahalle) → öbek. `obekler.json` buradan üretilir | Sevk birimi |
| `gunluk_parca` | Tarih, öbek, parça, teknisyen, iş listesi ve sırası | Sabah planı, Excel "Parça" sütunu |
| `kapasite_gunu` | Tarih, talep tahmini, aktif teknisyen, kapasite, **mod** (normal / aşırı yük), esnek önerisi ve gerçekleşen, 24 s üstü stok | İki modlu sıra, yönetici panosu |
| `masa_gorevi` | Task No, tür (btk_teshis, evde_yok, kanal, dogrulama, kalite), vade, deneme no, bant, durum | Masa kuyrukları |
| `arama` | Her deneme: zaman, kim, sonuç kodu. **Telefon tutulmaz** | Merdiven, ölçüm |
| `dis_islem` | Giden kutusu: BOSS'a girilecek Ekip, dilim, askı, kapatma; girildi mi, doğrulandı mı | Sistemle BOSS'un uyumu |

**Faz 2'de eklenecekler:**

- `teknisyen`: BOSS Ekip adıyla eşleşme, ev öbekleri, yetkinlik, vardiya.
- `ziyaret_sonucu`: evde miydi, neden kodu, zaman, konum.
- `randevu`.
- `musteri_ulasim`: Müşteri No'nun tek yönlü özeti; cevaplanan/cevapsız sayıları; cevap verdiği saat bandı. Kötü geçmiş kuralı bunu kullanır.
- Rol genişlemesi: `teknisyen`, `teknik_lider`, `operasyon`.

**Faz 3'te eklenecekler:** `talep` (WhatsApp, mail, satış), `eksp_talebi`, `altyapi_engeli`, `ticket_is` (ticket ↔ iş), `veri_surumu`, `bina_gecmis`.
Mevcut `bina` tablosuna `aktif` ve `location_id_norm` sütunları eklenir.

**Saklama:** 180 günden eski geçmiş günlük özete sıkıştırılır. Yedekler müşteri verisi içereceği için şifreli olmalı
(BitLocker teyidi).

---

## 8. Aşamalı yol haritası

| Faz | Ne | Değer | Süre | Ön koşul | Bitti sayılır, eğer… |
|---|---|---|---|---|---|
| **0: Kararlar** (kod yok) | §9 kararları. PS26 yayını kapatılır. BOSS'a 11:00 varsayılan dilim yazılması durur. Kanal Şikayeti aynı gün aranır. Teknisyen listesi (BOSS Ekip adı ↔ kişi ↔ ev öbeği) çıkarılır. Pilot öbekler seçilir | Süreç darboğazı kod beklemeden açılır | 1-3 gün | Sen + Hasan Bey | Kararlar yazılı |
| **1: İçe al + triyaj + 24 s saati** | Mevcut **İş emirleri** ekranı genişler: (1) FOX açık + askı da bırakılır, yalnız-FOX BTK işleri senin masana düşer. (2) Her yükleme saklanır; yeni, kapanan ve yeniden açılan bulunur, her işin 24 s saati işler. (3) Şerit, hedef, kalan süre, renk; 48 s üstü BTK listesi. (4) Öbek panosu, kapasite göstergesi, mod, esnek önerisi; Böl → parça → teknisyen; KARMA-2 sırası; "BOSS'a işlenecekler" listesi ve Excel. (5) Masa kuyrukları ve sonuç kodları. (6) 17:30 günlük rapor, yönetici panosunun ilk sürümü, 3B "Açık iş emri" merceği. (7) Birleşik KARMA-2'nin simülasyonda tek koşuyla doğrulanması | **İlk günden:** herkes aynı listeyi görür; neyin geciktiğini, kimin elinde olduğunu ve bugün kaç teknisyen gerektiğini sayıyla bilirsin. Teknisyenler bugünkü gibi BOSS Mobil'le çalışır; uygulama beklemeleri gerekmez | 1-2 hafta | Günde 3 dışa aktarım | 5 iş günü boyunca 07:45/12:15/16:45 yüklemesi yapıldı; her işin saati görünüyor; 17:00'de ekibi boş yeni iş 0 |
| **2: Teknisyen ekranı + pilot** | Teknisyen rolü; İşlerim (sıralı), iş kartı, sonuç kodları ("evde miydi" zorunlu). Evde yok anında masaya düşer. Yoldayım araması. Canlı "sıradaki iş" önerisi. **Pilot:** 2 öbek, 2 hafta, %10 kontrol grubu. Ölçülenler: evde yok, ilk aramada ulaşma, masa teşhis çözümü, ziyaret/gün | Varsayımlar ölçülür, katsayılar oturur; toplu kapatma biter | 2-3 hafta geliştirme + 2 hafta pilot | **VPN + HTTPS** (teknisyen sahadan bağlanmalı) | Pilot öbeklerde 24 s uyumu ve boşa ziyaret ölçüldü; KARMA-2 katsayıları güncellendi |
| **3: Canlı senkron + dış sistemler** | Klasör izleme → tarayıcı köprüsü (30 dk) → zamanlanmış rapor/API. OneDesk ve ONENT durum takibi. Talep kaydı (satış, WhatsApp, mail). "Satışlarım: kurulum durumu". Altyapı bayrağının satış haritasına yansıması | BTK teşhisi 15-30 dk'ya iner (günde 3 aktarımda −3 puan kayboluyordu) | 4-8 hafta | BT onayı | 30 dk senkron 1 hafta kesintisiz çalıştı |
| **4: Kurulum ekiplerine genişleme** | Aynı motor yeni müşteri işlerinde (1.614 birikim). Ortak kapasite: esnek havuz iki yönlü | Kurulum 24 s | Sonra | Faz 2 sonuçları | — |
| **5: Paketleme** (kararlı sürümden sonra) | Kurulum sihirbazı / setup, tek exe, çevrimiçi lisans anahtarı, cihaz yönetimi, SaaS | Başka bayilere taşınabilirlik | Kararlı sürümden sonra | Önce mülkiyet ve lisans sözleşmesi (GEREKSINIMLER E6 notu) | — |

---

## 9. Karar verilmesi gerekenler

### 9.1 Senin ve Hasan Bey'in kararları

| # | Soru | Seçenekler | Öneri | Kim |
|---|---|---|---|---|
| 1 | **Kadro.** Model ~20 aktif arıza teknisyeni istiyor; bugün ~10 | (a) Bugünkü kadro (tavan ~%50, birikim büyür) · (b) 4 kişilik kurtarma timi (10 iş günü) + 07:45 esnek formülüyle kurulumdan günlük ödünç (en çok 8) + tempo (ilk ziyaret 09:00 öncesi, toplu kapatma yok) · (c) Kalıcı +8-10 teknisyen | **(b)**, kalıcı karar pilot ölçümünden sonra | Hasan Bey |
| 2 | **Hangi hedef ölçülür?** | (a) Her iş 24 s (bayi kuralı) · (b) Turkcell FOX hedefleri (TV 6 s, Bağlantı 12 s) · (c) BOSS bayi SL'i (Bağlantı 24, TV 16) | **(a)** söz ve ana gösterge; BTK sırası FOX hedefiyle; FOX uyumu ayrıca raporlanır | Sen (+ Turkcell teyidi) |
| 3 | **Temas politikası** | (a) KARMA-2: aramasız sevk + BTK paralel teşhis + evde yok merdiveni · (b) Saf HAM (en az masa) · (c) Herkesi önce ara (bugünkü) | **(a)** | Sen |
| 4 | **Aşırı yükte gecikmiş işlere kota** | (a) BTK önce + yetişir + gecikmiş BTK her 3., diğerleri her 4. seçimde · (b) Saf "en eski önce" · (c) Saf "yetişir" | **(a)**, kapasite yetince normal moda (HAM sırası) geçer | Sen |
| 5 | **Kapsam: 2.Donanım (125) ve Cihaz İade (218)** | (a) 2.Donanım kurulum ekibine (makro zaten çıkarıyor), Cihaz İade operasyonun lojistik masasına · (b) İkisi de senin masana · (c) İkisi de kurulum ekibine | **(a)** | Sen |
| 6 | **Kanal Şikayeti** | (a) Aynı gün 3 deneme ile telefonla kapat; askı yalnız müşteri isterse, en çok 3 gün · (b) Bugünkü ~7 gün askı | **(a)** (Turkcell kuralı teyit edilmeli) | Sen |
| 7 | **Ulaşılamayan müşteri** | (a) 3 deneme (farklı saat bantları) + SMS + 48 s askı + son arama → Turkcell kuralıyla kapat · (b) Süresiz merkeze gönder · (c) Ertesi gün yine habersiz git | **(a)** | Sen + Turkcell |
| 8 | **Telefonla kapatmada kalite** | (a) Canlı test + 7 gün tekrar yasağı + %20 geri arama · (b) Müşterinin "düzeldi" demesi yeter | **(a)**; tekrar arıza %35, telefonla kapatma bunu artırmamalı | Sen |
| 9 | **BOSS "Randevulu" alanı** | (a) Gerçek tahmini varış dilimi; varsayılan 11:00 yasak · (b) Bugünkü gibi | **(a)** | Sen |
| 10 | **Masa kadrosu** (20 kişilik operasyondan) | (a) BTK teşhis 2 + merdiven/Kanal 2 + akşam bandı 1 + vardiya lideri 1 (≈32 kişi-saat/gün), ilk 10 gün +2 kurtarma · (b) Bugünkü 2 kişilik arama | **(a)** | Sen |
| 11 | **Akşam vardiyası** | (a) Kadro 16-18'i geçince 2-3 kişi 12-21 · (b) Hemen · (c) Yok | **(a)** | Hasan Bey |
| 12 | **Veri tazeliği** | (a) Şimdi günde 3 elle dışa aktarım + klasör izleme; BT'den 30 dk köprü ya da zamanlanmış rapor istenir · (b) Yalnız elle | **(a)** | Sen + BT |
| 13 | **Teknisyenin sahadan erişimi** | (a) Şirket VPN'i + HTTPS · (b) Cloudflare Tunnel (KVKK md. 9 sorusu doğar) | **(a)** | BT |
| 14 | **Kapanmış iş dosyaları** (TAMAMLANDI.xlsx, ANLATILAN.xlsx) | (a) Kalibrasyonda yalnız toplu sayımla kullanılır; her sabah "dün kapananlar" raporu alınır · (b) Kullanılmaz | **(a)** | Sen |
| 15 | **PS26 GitHub Pages yayını** | (a) Hemen kapat, depoyu özele al · (b) Açık kalsın | **(a)**, acil | Sen |
| 16 | **Pilot** | (a) 2 öbek, 2 hafta, %10 kontrol grubu · (b) Pilotsuz tüm metro | **(a)** | Sen |
| 17 | **OneDesk ticket açma yetkisi** | (a) Sen açmaya devam edersin, metni sistem hazırlar · (b) Altyapı masasına yetki verilir | Şimdilik **(a)**, Faz 3'te yeniden bakılır | Sen |

**Kapanmış soru:** Konumsuz işler için adresten mahalle eşlemesi artık makroda yapılıyor (601/601).

### 9.2 BT'den istenecekler

1. Bu bilgisayarda yerel veri işleme onayı (KVKK veri işleyen) ve BitLocker teyidi.
2. BOSS ve FOX için saatlik zamanlanmış rapor ya da salt okunur API ve servis hesabı. Ara çözüm: tarayıcı eklentisi izni (saatte en çok 2 çağrı).
3. Teknisyenler için şirket VPN'i ve HTTPS sertifikası.
4. OneMap (ArcGIS) salt okunur erişimi.
5. İsteğe bağlı: paylaşılan posta kutusu ve EWS.

### 9.3 Turkcell'e sorulacaklar

1. SL saati takvim saatiyle mi, mesai saatiyle mi işliyor? Askıdayken saat duruyor mu?
2. Ulaşılamayan müşteri kaç denemeden ve kaç günden sonra kapatılabilir?
3. Telefonla kapatma hangi nedenlerle kabul ediliyor? Kanal Şikayeti BTK ölçümüne giriyor mu?
4. BOSS "Randevulu" kaydı müşteriye otomatik SMS gönderiyor mu?
5. Modem ve Superbox değişiminde kuryeyle teslim ve müşterinin kendisinin kurması kabul ediliyor mu?

---

*İlgili dosyalar (hepsi `operasyon/` altında):*

- Makro ve ekran: `is_emri.py`, `api.py`, `obekler.json`, `yakinlik.py`.
- Analiz: `analiz/is_emri_analizi.md`, `analiz/surec.md`, `analiz/entegrasyon.md`, `analiz/simulasyon.md`.
- Hakem çıktıları: `analiz/hakem1/cikti/hakem1_karar.json`, `analiz/hakem2/cikti/hakem_ozet.txt`, `analiz/hakem3/cikti/h3_tablo.txt`.
- Tek sayfalık özet: `docs/OPERASYON_OZET.md`.
