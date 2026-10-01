# İş Emri Simülasyonu: Strateji Yarışı

*Dehanet EÇM, mevcut müşteri iş emirleri. Ayrık olay benzetimi; 2026-09-29 20:02 tarihli çalıştırma, 723 koşu. Kod: `operasyon/analiz/simulasyon.py`, sayısal çıktı: `cikti/simulasyon.json`.*

## 1. Kısa sonuç

- **Kazanan: KARMA.** Tüm stratejiler aynı gelişler, aynı müşteri davranışı ve aynı kaynakla yarıştı. Referans kadroda (16 arıza teknisyeni) yeni işlerin 24 saatte kapanma oranı KARMA %66, HAM %64, DSİR %52, RPHT %49, U1H %43, BÖLGE %28; bugünkü süreç %24.
- **Bugünkü kadroda (10 teknisyen) fark en büyük.** KARMA %50, ikinci RPHT %40. Kullanıcının ham fikri (HAM) %34, bugünkü süreç %24.
- **Kadro yeterliyse ham fikir de iyi çalışıyor.** 20 teknisyende HAM %78 ile KARMA %77 başa baş. HAM'ın katı 'önce BTK' sırası BTK'da biraz daha iyi (%81 ve %77).
- **Asıl kaldıraç teknisyen sayısı.** Hiçbir strateji 24 teknisyene kadar %90'a ulaşmıyor. KARMA'da 24 saat uyumu 10 kişide %50, 14 kişide %60, 16 kişide %66, 20 kişide %77, 24 kişide %82.
- **Arama politikası:** aramadan gidip evde olmayanı aramak, herkesi önce aramaktan hızlı. Boşa ziyaret (HAM %17), bekletilen işin 24 saati kaçırmasından ucuz. Önce arayan stratejilerde boşa ziyaret düşük (DSİR %7) ama ulaşılamayan iş masada günlerce bekliyor.
- **Bugünkü süreçte darboğaz ofis.** BUGÜN modelinde 2 kişilik ofis araması %100 dolu; teknisyen 10'dan 24'e çıksa da 24 saat uyumu %24 → %31 kalıyor. Önce süreç değişmeli ('herkesi ara' kaldırılmalı), sonra kadro eklenmeli.
- **Sıralamanın sağlamlığı:** 32 senaryonun (8 kadro düzeyi + 24 duyarlılık) 24'inde KARMA, 8'inde HAM birinci; diğerleri hiçbir senaryoda birinci değil. Yöntem sıralamasını tersine çeviren tek şey kapasite/yük oranı: kıt kapasitede KARMA açık ara önde, bol kapasitede HAM ile başa baş (BTK'da HAM önde).

## 2. Yöntem

**Model.** 5 dakikalık adımlı ayrık olay benzetimi. Başlangıç 29.09.2026 18:00 (BOSS dışa aktarım anı), ufuk 35 gün (30 iş günü + 5 Pazar). Bileşenler:

- **Gelişler (VERİ).** Günlük hacim ANLATILAN 1-15 Eylül'den alındı: hafta içi 337,7, Cumartesi 384, Pazar 182; günlük sapma lognormal σ=0,15. Tip payları ve saatlik varış profili (09:00 zirvesi) de veriden. 2.Donanım günde 5,4.
- **Kapsam (metro).** Nilüfer, Osmangazi, Yıldırım, Mudanya, Gürsu ve Kestel; son 24 saatteki BOSS işlerinin payı %96. Uzak ilçeler (Yalova, İnegöl, Gemlik, Karacabey...) yerel teknisyene bağlı kabul edildi.
- **Başlangıç birikimi.** BOSS 'Task Detail Report' sayfasındaki 522 metro mevcut-müşteri işi; tip, yaş, askı/durum, 'ulaşılamadı' notu ve bina konumuyla (Lokasyon, 8 haneye tamamlanarak bina_master'a bağlandı).
- **Konum.** Yeni iş, aktif abone sayısına göre ağırlıklı rastgele bir metro binasına düşer. Konumlu olma olasılığı BOSS'taki tip oranıdır (TV %100, Bağlantı %74, Kanal/Superbox %0). Konumsuz iş planlamada mahalle merkezine, yol hesabında gerçek binaya göre yürür. Yol: kuş uçuşu ×1,35, şehirde 25 km/sa (10 km üstü 60 km/sa), park 5 dk.
- **Arıza doğası (VERİ, TAMAMLANDI kapanış nedenleri).** BTK işi telefonla çözülür (Bağlantı %28,6, TV %34), şebeke (%11-14; yarısı 300 m içinde 3 saatte gelen kümeler, çözüm medyanı 6 s), altyapı (%2, 72 s) ya da gerçek saha işidir. Telefonla çözülenin %40'ı kendiliğinden düzelir (ort. 6 s). Masa teşhisi %85, kısa kontrol %45 çözer.
- **Müşteri (VARSAYIM).** Üç ulaşılabilirlik sınıfı var: %60 kolay, %25 orta, %15 zor; 'ulaşılamadı' notlu birikimde bu oranlar %20/%35/%45. Her müşterinin gizli bir 'evde mi' durumu var. Çalışan müşteri (%8/%22/%45) hafta içi 09-17 dışarıda, herkes her 2 saatlik blokta %6 dışarıda. Habersiz gündüz ziyarette ortalama evde yok ≈%22. Telefonu açma evde olmaya bağlı: dışarıdaki müşteri, evdekinin ρ=0,3 katı olasılıkla açar. Bu yüzden 'açmadı' bilgisi 'evde değil' olasılığını artırır ve bu korelasyon her stratejiye aynı işler.
- **Ziyaret sonucu.** Habersiz ziyarette müşteri gizli duruma göre evdedir ya da değildir. Teyitli ziyarette %5, randevuda %8 gelmeme var; pencereye geç kalınırsa başarı ×0,6. SMS ile dilim bildirilen ve o saatte dışarıda olan müşterinin %40'ı yine de evde birini bulundurur. İlk seferde çözüm %92. Telefonla kapatılan BTK işinin %6'sı (7 günlük tekrar bayraklıda %20) 1-7 gün içinde tekrar arıza olarak geri gelir.
- **Teknisyen.** Hafta içi ve Cumartesi N kişi, Pazar tavan(0,55·N). Gündüz vardiyası 08:30-18:30 (BUGÜN ~09:15), akşam vardiyası 12:00-21:00, 30 dk mola. Her teknisyenin k-ortalama ile belirlenen bir bölgesi var. Aday sırası: önce kendi bölgesi ve 3 km içi, sonra 10 km içi, sonra tüm metro. İş biten teknisyen bir sonraki işi stratejinin kuralıyla seçer.
- **Operasyon (masa).** 08:30-17:30 arası 8 kişi, 17:30-20:30 arası 4 kişi, Pazar 3 kişi; verim 0,8. Arama süreleri: başarısız 2 dk, randevu/kontrol 4 dk, uzaktan teşhis 10 dk. BUGÜN'de ofis araması 2 kişi. Önceliği strateji belirler; kapasite dolarsa kuyruk bekler.
- **Adil yarış.** Ortak rastgele sayılar kullanıldı: aynı tohumda her strateji aynı işleri, aynı müşteriyi ve k. aramada aynı açma/açmama çekilişini görür. Stratejiler yalnız kararlarıyla ayrışır. Kaynaklar eşit: aynı N, aynı masa. Geçici kurtarma timi ya da esnek teknisyen yok. Önerilen stratejiler kendi vardiya bölüşümünü seçer.
- **Tohumlar.** KARMA, tohum 1-3 ile tasarlandı. Raporlanan ana yarış 101-105, kadro taraması ve duyarlılık 201-203 tohumlarıyla koşuldu. Bu tohumlar tasarımda hiç kullanılmadı.

**Ölçütler.** Hepsi 35 günlük dönem için; yeni işler son 24 saat hariç.

- **24 s uyumu:** 29.09 18:00'den sonra gelen işlerin 24 takvim saatinde kapanan payı. Kapanış türüne bakılmaz; ulaşılamadı kapanışı ayrıca raporlanır.
- **BTK 24 s:** Bağlantı, TV+ Arıza, Arama ve Doping işlerinde aynı oran. TV 6 s ve Bağlantı 12 s, Turkcell FOX hedefleri.
- **Birikim erime günü:** başlangıçta 24 saati geçmiş birikimin %95'inin kapandığı gün. 35 günde erimiyorsa son haftanın hızıyla uzatılır; hız sıfırsa 'erimiyor' yazılır.
- **Çağrı/gün:** operasyon ve teknisyen denemeleri ile müşterinin geri araması.
- **Boşa ziyaret:** ziyaretlerde evde yok ve gelmeme payı.
- **km/teknisyen-gün:** ziyaret yapan teknisyen başına yol (km).
- **Operasyon saat/gün:** masa meşguliyeti ÷ verim.

## 3. Yarışan stratejiler

| Kod | Özet |
|---|---|
| **BUGÜN** | Bugünkü süreç (referans): ofis her işi bir kez arar; ulaşırsa 2 saatlik dilim yazar, ulaşamazsa not düşer ve ertesi gün yine arar. Teknisyen yalnız dilimli işe gider. Kanal Şikayeti ~1 hafta askıda. |
| **HAM** | Kullanıcının ilk fikri: iş aranmadan ekibe verilir, teknisyen habersiz gider (BTK önce, sonra en eski). Evde olmayanı operasyon arar ve randevular. |
| **DSİR** | Doğrudan Sevk + İstisna Randevu: aramasız sevk, EDF sırası; teknisyen her işten önce 2 kez arar, ulaşamazsa iş operasyonun 5 denemeli istisna kuyruğuna gider. %10 akşam vardiyası; Pazar yalnız BTK. |
| **RPHT** | Risk Puanlı Hibrit Triyaj: BTK'yı masa 15-30 dk içinde uzaktan teşhis eder, ulaşamazsa habersiz sevk; BTK dışı işi teyit edip dilim verir; küme bekletme; birikim için masa taraması. |
| **BÖLGE** | Bölge Dalgaları: her iş aranmadan bölge takviminde 24 saat içindeki ilk 2 saatlik dilime yazılır ve SMS gider; teknisyen yola çıkarken bir kez arar, ulaşamazsa ≤1 km ise gider, değilse atlar. Fazla rezervasyon. |
| **U1H** | Uzaktan-Önce Huni: her iş önce masaya gelir (~2 saatte 3 deneme); ulaşılan iş uzaktan teşhis, kurye ya da aynı görüşmede verilen dilimle kapanır; BTK'da 3 denemede ulaşılamazsa teyitsiz sevk. %30 geç vardiya. |
| **KARMA** | Yarış sonrası birleşim: HAM'ın aramasız sevki + 'yetişir' sıralaması (24 saatine hâlâ yetişebilecek iş önce, gecikmişe kota) + BTK'da masanın paralel hızlı teşhisi (sahayı bekletmez) + şebeke kümesi NOC kontrolü. |

BÖLGE, DSİR, RPHT ve U1H'nin kuralları kendi tasarım belgelerindeki sıraya sadık kodlandı (K/R numaraları koddaki yorumlarda). Eşit kaynak ilkesi gereği önerilerdeki ek kadro (DSİR 17+2, BÖLGE 34-38 kişi, U1H 10 kişilik masa + esnek havuz) yarışa verilmedi; etkisi kadro ve masa taramasında görülür.

## 4. Kalibrasyon (bugünkü süreç)

| Ölçü | Model (BUGÜN, 10 teknisyen) | Gözlenen |
|---|---|---|
| 24 s uyumu | %24 | 1-14 Eylül kohortu %43; 12-14 Eylül %21-24 |
| 48 s uyumu | %29 | 1-14 Eylül kohortu %59 |
| Kapanış/gün | 189 (takvim günü ort.) | hafta içi ~224 |
| Teknisyen başına ziyaret/gün | 14,1 | kapanış medyanı 17 (telefonla ve toplu kapanış dahil) |

Model, eylül ortasındaki bozulmuş durumu (%21-24) yakalıyor. Ayın başındaki kohort ortalamasından (%43) düşük; o dönemde birikim küçüktü. 48 saat uyumu gözlenenden düşük, yani model bugünkü süreç için biraz karamsar. Stratejiler aynı dünyada yarıştığı için bu fark sıralamayı etkilemez.

## 5.1 Bugünkü kadro: 10 arıza teknisyeni (Pazar 6)

5 tekrar ortalaması; köşeli parantez içinde en düşük ve en yüksek tekrar.

| Strateji | 24 s uyumu | BTK 24 s | TV 6 s | Bağlantı 12 s | 48 s | Birikim erime (gün) | Çağrı/gün (ops+tek.) | Boşa ziyaret | km/tek.-gün | Operasyon saat/gün | 24 s üstü açık (son hafta) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **KARMA** | %50 [%49-%51] | %46 | %19 | %19 | %56 | 13 | 303 (301+0) | %18 | 48,1 | 29,9 | 3.421 |
| RPHT | %40 [%39-%41] | %35 | %24 | %21 | %47 | erimiyor | 524 (480+40) | %28 | 49,1 | 58,5 | 3.378 |
| DSİR | %36 [%35-%38] | %26 | %6 | %4 | %45 | 7 | 445 (216+223) | %7 | 51,6 | 14,2 | 3.703 |
| HAM | %34 [%34-%35] | %22 | %11 | %13 | %39 | erimiyor | 183 (178+0) | %17 | 34,3 | 11,9 | 3.408 |
| BÖLGE | %24 [%23-%24] | %4 | %1 | %1 | %29 | 75,5 | 380 (151+229) | %17 | 26,4 | 10,2 | 4.312 |
| U1H | %19 [%18-%20] | %27 | %17 | %19 | %21 | erimiyor | 669 (523+128) | %29 | 61,0 | 75,8 | 5.391 |
| BUGÜN | %24 [%23-%24] | %24 | %9 | %11 | %29 | 217,8 | 286 (286+0) | %28 | 51,8 | 15,4 | 4.428 |

## 5.2 Referans: 16 teknisyen (Pazar 9)

5 tekrar ortalaması; köşeli parantez içinde en düşük ve en yüksek tekrar.

| Strateji | 24 s uyumu | BTK 24 s | TV 6 s | Bağlantı 12 s | 48 s | Birikim erime (gün) | Çağrı/gün (ops+tek.) | Boşa ziyaret | km/tek.-gün | Operasyon saat/gün | 24 s üstü açık (son hafta) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **KARMA** | %66 [%64-%67] | %67 | %29 | %32 | %73 | 7 | 350 (348+0) | %19 | 41,2 | 32,3 | 1.205 |
| HAM | %64 [%59-%67] | %70 | %32 | %38 | %77 | 8 | 227 (220+0) | %17 | 31,4 | 14,2 | 875 |
| DSİR | %52 [%49-%53] | %49 | %20 | %15 | %66 | 6 | 643 (275+360) | %7 | 42,4 | 17,6 | 1.319 |
| RPHT | %49 [%48-%49] | %43 | %28 | %25 | %56 | 4 | 506 (402+100) | %21 | 39,4 | 45,0 | 1.285 |
| U1H | %43 [%40-%45] | %45 | %26 | %29 | %56 | 9 | 859 (637+203) | %26 | 56,1 | 75,2 | 1.812 |
| BÖLGE | %28 [%28-%28] | %10 | %1 | %2 | %36 | 10 | 521 (181+340) | %18 | 21,3 | 11,7 | 2.676 |
| BUGÜN | %24 [%23-%25] | %25 | %10 | %11 | %29 | 138,9 | 287 (287+0) | %14 | 31,9 | 15,4 | 3.773 |

## 5.3 Hedefe yakın kadro: 20 teknisyen (Pazar 11)

5 tekrar ortalaması; köşeli parantez içinde en düşük ve en yüksek tekrar.

| Strateji | 24 s uyumu | BTK 24 s | TV 6 s | Bağlantı 12 s | 48 s | Birikim erime (gün) | Çağrı/gün (ops+tek.) | Boşa ziyaret | km/tek.-gün | Operasyon saat/gün | 24 s üstü açık (son hafta) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **HAM** | %78 [%75-%80] | %81 | %49 | %54 | %88 | 4 | 239 (232+0) | %17 | 50,4 | 14,9 | 107 |
| KARMA | %77 [%75-%79] | %77 | %48 | %54 | %86 | 6 | 379 (377+0) | %20 | 50,6 | 33,5 | 173 |
| DSİR | %66 [%64-%68] | %65 | %36 | %37 | %77 | 6 | 729 (300+419) | %7 | 48,3 | 19,1 | 390 |
| RPHT | %61 [%57-%64] | %58 | %35 | %34 | %73 | 4 | 562 (421+138) | %23 | 48,7 | 45,8 | 350 |
| U1H | %59 [%58-%60] | %55 | %36 | %38 | %66 | 8 | 835 (606+215) | %13 | 61,8 | 65,5 | 425 |
| BÖLGE | %34 [%32-%34] | %18 | %4 | %4 | %44 | 7 | 566 (185+380) | %17 | 17,9 | 11,9 | 2.007 |
| BUGÜN | %25 [%25-%26] | %26 | %11 | %11 | %32 | 122,3 | 287 (287+0) | %11 | 30,7 | 15,4 | 3.633 |

## 6. Kadro taraması

24 saat uyumu ve parantez içinde BTK 24 saat uyumu. 10, 16 ve 20 kişide 5 tekrar (tohum 101-105), diğer düzeylerde 3 tekrar (tohum 201-203).

| Strateji | N=10 | N=12 | N=14 | N=16 | N=18 | N=20 | N=22 | N=24 |
|---|---|---|---|---|---|---|---|---|
| KARMA | %50 (%46) | %55 (%54) | %60 (%62) | %66 (%67) | %72 (%73) | %77 (%77) | %81 (%80) | %82 (%81) |
| HAM | %34 (%22) | %46 (%43) | %52 (%53) | %64 (%70) | %71 (%78) | %78 (%81) | %83 (%85) | %84 (%85) |
| DSİR | %36 (%26) | %42 (%32) | %46 (%41) | %52 (%49) | %60 (%58) | %66 (%65) | %69 (%67) | %70 (%68) |
| RPHT | %40 (%35) | %41 (%34) | %44 (%38) | %49 (%43) | %52 (%46) | %61 (%58) | %68 (%65) | %72 (%69) |
| U1H | %19 (%27) | %26 (%33) | %32 (%38) | %43 (%45) | %54 (%50) | %59 (%55) | %61 (%59) | %57 (%53) |
| BÖLGE | %24 (%4) | %26 (%7) | %27 (%8) | %28 (%10) | %31 (%14) | %34 (%18) | %37 (%22) | %42 (%29) |
| BUGÜN | %24 (%24) | %24 (%25) | %25 (%26) | %24 (%25) | %26 (%27) | %25 (%26) | %28 (%29) | %31 (%33) |

Birikim erime günü, kadroya göre:

| Strateji | N=10 | N=12 | N=14 | N=16 | N=18 | N=20 | N=22 | N=24 |
|---|---|---|---|---|---|---|---|---|
| KARMA | 13 | 24 | 10 | 7 | 6 | 6 | 6 | 6 |
| HAM | erimiyor | erimiyor | 28 | 8 | 5 | 4 | 4 | 4 |
| DSİR | 7 | 6 | 7 | 6 | 6 | 6 | 6 | 6 |
| RPHT | erimiyor | erimiyor | 5 | 4 | 4 | 4 | 4 | 4 |
| U1H | erimiyor | erimiyor | 107,5 | 9 | 9 | 8 | 9 | 9 |
| BÖLGE | 75,5 | 212,5 | 64,2 | 10 | 11 | 7 | 9 | 10 |
| BUGÜN | 217,8 | 177,4 | 163,4 | 138,9 | 132,1 | 122,3 | 127,9 | 154,6 |

**BÖLGE için kontrol.** BÖLGE'nin düşük sonucu uygulama ayrıntısından mı kaynaklanıyor? Bunu sınamak için takvim gevşetildi: boştaki teknisyen sonraki dilimi öne çekebiliyor ve cevapsız müşteriye 2 km'ye kadar gidiliyor. Sonuç (BÖLGE-esnek): N=16: %35 (BTK %21), N=20: %45 (BTK %34), N=24: %58 (BTK %50). Sonuç iyileşiyor ama sıralama değişmiyor. Katı dilim takvimi, boştaki teknisyenin bekleyen işi alamaması demek (teknisyen başına günde 2-3 saat boşta).

## 7. Duyarlılık (16 teknisyen, 3 tekrar, tohum 201-203)

Her satırda tek bir varsayım değişti, diğerleri referansta kaldı. Hücrelerde 24 saat uyumu ve parantez içinde BTK 24 saat uyumu var.

| Senaryo | KARMA | HAM | DSİR | RPHT | U1H | BÖLGE | BUGÜN | 1. |
|---|---|---|---|---|---|---|---|---|
| referans | %66 (%68) | %66 (%72) | %52 (%49) | %48 (%42) | %44 (%45) | %29 (%11) | %24 (%24) | KARMA |
| evde yok %15 | %70 (%72) | %70 (%78) | %54 (%51) | %49 (%43) | %43 (%45) | %29 (%11) | %24 (%25) | HAM |
| evde yok %30 | %63 (%63) | %61 (%64) | %50 (%46) | %47 (%41) | %44 (%44) | %28 (%10) | %24 (%25) | KARMA |
| evde yok %45 | %58 (%56) | %50 (%47) | %47 (%41) | %45 (%38) | %44 (%44) | %27 (%9) | %24 (%25) | KARMA |
| telefonla cozulur x0.6 | %62 (%62) | %58 (%60) | %46 (%41) | %44 (%37) | %33 (%36) | %28 (%9) | %23 (%23) | KARMA |
| telefonla cozulur x1.3 | %69 (%71) | %68 (%76) | %57 (%56) | %50 (%45) | %53 (%53) | %29 (%12) | %25 (%27) | KARMA |
| disaridaki acar rho0.1 | %67 (%68) | %67 (%74) | %52 (%49) | %47 (%40) | %44 (%45) | %29 (%11) | %24 (%25) | HAM |
| disaridaki acar rho0.6 | %67 (%68) | %65 (%71) | %52 (%49) | %49 (%43) | %44 (%46) | %28 (%10) | %24 (%25) | KARMA |
| disaridaki acar rho0.9 | %67 (%68) | %66 (%72) | %51 (%47) | %49 (%43) | %43 (%45) | %28 (%10) | %24 (%24) | KARMA |
| ulasma dusuk | %66 (%68) | %66 (%73) | %51 (%47) | %46 (%39) | %49 (%48) | %28 (%10) | %21 (%21) | KARMA |
| ulasma yuksek | %67 (%68) | %65 (%70) | %53 (%50) | %50 (%44) | %39 (%44) | %29 (%11) | %26 (%28) | KARMA |
| operasyon 4 kisi | %65 (%68) | %65 (%71) | %52 (%49) | %38 (%46) | %26 (%44) | %28 (%10) | %24 (%24) | HAM |
| operasyon 12 kisi | %67 (%68) | %66 (%72) | %52 (%49) | %49 (%42) | %48 (%41) | %29 (%11) | %24 (%24) | KARMA |
| arama hizi dusuk verim0.6 | %66 (%67) | %66 (%72) | %52 (%49) | %47 (%43) | %42 (%54) | %28 (%11) | %12 (%7) | KARMA |
| arama hizi yuksek verim0.95 | %67 (%68) | %66 (%72) | %52 (%48) | %49 (%42) | %45 (%42) | %29 (%11) | %24 (%25) | KARMA |
| giris -15% | %74 (%75) | %75 (%80) | %62 (%61) | %55 (%49) | %62 (%58) | %31 (%14) | %24 (%25) | HAM |
| giris +15% | %62 (%63) | %47 (%42) | %46 (%40) | %45 (%39) | %33 (%42) | %27 (%9) | %23 (%23) | KARMA |
| trafik 20kmsa | %65 (%66) | %63 (%68) | %49 (%45) | %47 (%41) | %39 (%42) | %28 (%10) | %24 (%24) | KARMA |
| trafik 35kmsa | %68 (%70) | %68 (%75) | %56 (%54) | %49 (%43) | %52 (%51) | %29 (%11) | %24 (%25) | KARMA |
| elle 3 aktarim | %63 (%66) | %61 (%66) | %51 (%47) | %37 (%26) | %38 (%40) | %26 (%9) | %22 (%22) | KARMA |
| konumsuz ilce merkezi | %65 (%65) | %57 (%57) | %52 (%47) | %46 (%41) | %39 (%44) | %29 (%11) | %25 (%26) | KARMA |
| sms kanali yok | %66 (%68) | %66 (%72) | %52 (%49) | %48 (%42) | %44 (%45) | %28 (%10) | %24 (%24) | KARMA |
| kurye yok | %66 (%68) | %66 (%72) | %52 (%49) | %48 (%42) | %37 (%41) | %29 (%11) | %24 (%24) | KARMA |
| uzaktan cozum dusuk | %65 (%66) | %66 (%73) | %51 (%47) | %46 (%39) | %40 (%41) | %28 (%10) | %23 (%23) | HAM |

**Sıralama sağlamlığı (32 senaryo = 8 kadro + 24 duyarlılık).**

- 24 s uyumunda birinci: KARMA 24, HAM 8.
- BTK 24 s uyumunda birinci: HAM 25, KARMA 7.

**Sıralamayı değiştiren ve değiştirmeyen varsayımlar**

1. **Kapasite/yük oranı** (teknisyen sayısı, giriş hacmi, evde yok oranı) KARMA ile HAM'ın yerini değiştiren tek etken. Kapasite kıtken HAM'ın 'en eski önce' sırası domino etkisiyle çöküyor; KARMA yeni işlerin 24 saatini korurken gecikmişleri kotayla eritiyor. Giriş %15 artınca KARMA %62, HAM %47. Evde yok %45 olunca KARMA %58, HAM %50. Kapasite bolken (giriş %15 az, evde yok %15) HAM bir iki puan önde.
2. **İlk iki sıra neredeyse hiç değişmiyor.** 32 senaryonun 31'inde ilk iki KARMA ve HAM; istisna N=10 (orada HAM dördüncü, RPHT ikinci). Üçüncülük: DSİR 31, RPHT 1. Sonunculuk: BÖLGE 30, U1H 2 (BUGÜN hariç; U1H masa doyduğunda 10-12 kişide BÖLGE'nin de altına düşüyor).
3. **Telefonla çözülebilir pay** tüm stratejileri aynı yönde kaydırıyor (×0,6 ile ×1,3 arası). En duyarlı U1H: %33 ile %53 arası. Sıralamayı değiştirmiyor.
4. **Masa kapasitesi (operasyon kişi sayısı, arama hızı)** yalnız masa ağırlıklı stratejileri etkiliyor. 4 kişilik masada U1H %26, RPHT %38. 12 kişide U1H ancak %48. HAM ve KARMA masaya az yük bindirdiği için etkilenmiyor. BUGÜN'de ofis arama hızı düşerse uyum %12 oluyor.
5. **Dışarıdaki müşterinin telefonu açma oranı (ρ)** teknisyenin gitmeden aramasının değerini belirliyor. ρ 0,1 ile 0,9 arasında sonuçlar ±1-2 puan oynuyor. Aramadan gitme avantajı, arayan stratejilerin ulaşılamayanı saatlerce masada bekletmesinden geliyor; ρ'dan değil.
6. **Konum kalitesi:** konumsuz iş mahalle yerine ilçe merkezinde planlanırsa bir bölgeye yığılma oluyor. HAM -9 puan, KARMA -2 puan etkileniyor. Adres metninden mahalle eşlemesi yapılması (yerel, ağ çağrısı yok) bu yüzden önemli.
7. **Elle günde 3 dışa aktarım (30 dk köprü yerine)** en çok RPHT'yi vuruyor (-11 puan), çünkü 15-30 dakikalık BTK arama hedefi tutmuyor. KARMA -4 puan etkileniyor.
8. **SMS kanalı ve kurye** yalnız kendi stratejilerini etkiliyor. Kurye olmayınca U1H -7 puan kaybediyor. SMS kanalı yokken BÖLGE'de değişim ≤1 puan, çünkü BÖLGE'yi geride bırakan etken kapasite takvimi.
9. **Trafik (20-35 km/sa)** ve **ulaşma oranı** düzeyi kaydırıyor, sıralamayı değiştirmiyor.

## 8. Bulgular

1. **Aramadan sevk, önce aramaktan hızlı.** Müşteriye ulaşamayan her strateji işi bir kuyruğa (istisna, merdiven, dilim) koyuyor ve iş orada saatlerce, bazen günlerce bekliyor. Habersiz ziyarette evde yok olasılığı ~%22. Boşa giden ziyaretin maliyeti yaklaşık 20-25 dk (yol + 10 dk bekleme); bekleyen işin 24 saati kaçırma maliyeti ise çok daha büyük.
2. **Sıralama kuralı, kapasite kıtken belirleyici.** Kapasite yetmediğinde 'en eski önce' (FIFO) kuralı, 24 saati zaten kaçmış işleri yapmakla yeni işleri de kaçırıyor (domino etkisi). 'Yetişir' kuralıyla KARMA, 10 teknisyende HAM'dan 16 puan önde. Gecikmiş işlere kota ayrıldığı için birikim de 13 günde eriyor; HAM'da erimiyor.
3. **BTK için masanın paralel teşhisi yararlı.** İş sahada sırasını beklerken masa bir kez arıyor; telefonla çözülen iş hiç ziyaret edilmeden kapanıyor. Masa yükü 32 kişi-saat/gün (≈4 kişi). Sahayı bekleten 'önce masa' tasarımları (U1H, RPHT) bu kazancı gecikmeyle geri veriyor.
4. **Teknisyenin gitmeden araması net kayıp.** DSİR teknisyenleri günde 360 arama yapıyor (teknisyen başına ~24). Boşa ziyaret %7'ye iniyor, ama ulaşılamayan iş istisna kuyruğunda bekliyor ve 24 saat uyumu %52 kalıyor. Kural 'arama yap, ulaşamazsan yine git' olsaydı da arama süresi kazancı yiyordu (tasarım denemelerinde −1,5 ile −3,5 puan).
5. **Takvime dayalı rezervasyon (BÖLGE) eşit kadroda en zayıf.** Beklenen birimle yapılan fazla rezervasyon, geliş dalgalanmasında takvimi günler ötesine itiyor. Teknisyen kendi dilimi boşalınca bekleyen işi alamıyor ve günde 169 dk boşta kalıyor. Tasarım da 34-38 kişi öngörüyordu.
6. **Hiçbir yöntem %90'a kadro olmadan ulaşmıyor.** KARMA'da 24 saat uyumu 20 kişide %77, 24 kişide %82. Tavanı şunlar belirliyor: müşterinin ileri gün istemesi, üç denemede ulaşılamayan müşteri, Pazar'ın yarım kadrosu ve akşam 17:00 sonrası gelen işler (girişin ~%30'u). Turkcell FOX hedefleri (TV 6 s, Bağlantı 12 s) 20 kişide bile yaklaşık %50'de; gece gelen işler için bu hedefler fiziksel olarak tutulamıyor.
7. **Bugünkü süreçte teknisyen eklemek yetmiyor.** Herkesi önce ofis aradığı ve ulaşılamayan iş teknisyene hiç gitmediği için darboğaz ofis araması. Modelde teknisyen sayısı artsa da uyum yerinde sayıyor.

## 9. Önerilen işleyiş (KARMA kuralları)

1. **Giriş.** BOSS ve FOX 08:00-20:00 arasında 30 dakikada bir içe aktarılır. Adında 'kurulum' geçen iş kapsam dışıdır ('Kurulum Taskı Ürememiş' hariç). Kanal Şikayeti ve Soru-Cevap masaya gider (hemen, +2 s ve akşam denemesi). Cihaz İade önce sistemde kontrol edilir, gerekirse aranır.
2. **Saha işi aranmadan kuyruğa girer.** İş, bölge teknisyeninin kuyruğuna doğrudan düşer. Randevu yalnız istisnada verilir: müşteri 'şimdi olmaz' derse, evde bulunamazsa ya da masa teşhisinde müşteri başka bir saat isterse.
3. **BTK'da paralel masa teşhisi.** İş sahadayken masa 30-45 dk içinde bir kez arar ve 10 dakikalık uzaktan teşhis yapar. Çözülürse iş kapanır. Şebeke arızası çıkarsa iş bekletilir. Müşteri şimdi müsait değilse randevu verilir. Ulaşılamazsa hiçbir şey yapılmaz, teknisyen zaten gidecek. Son 7 günde tekrar eden arızada telefonla kapatma yapılmaz.
4. **Sıralama: 'yetişir' kuralı.** Teknisyen her işi bitirince sıradaki işi şöyle seçer:
   - Önce penceresi açılan randevu.
   - Sonra 24 saatine hâlâ yetişebilecek işler, son tarih sırasıyla. BTK 6 saat, TV 2 saat daha öne alınır; yakınlık hafif ağırlıklıdır.
   - Sonra 24 saati kaçmış işler, en eski önce; BTK 12 saat öne alınır.
   - Teknisyenin aday listesinde 15 ya da daha fazla gecikmiş iş varsa (aşırı yük), gecikmiş işlere her 4. seçimde bir yer verilir. Yoksa sıra normal FIFO'dur: önce BTK, sonra en eski.
5. **Teknisyen gitmeden aramaz.** Müşteri evde değilse 10 dk bekler ve iş masaya düşer. Masa hemen, +2 saatte ve akşam arar; ulaşınca 'düzeldi mi' kontrolü yapar ya da randevu verir. Üç denemede ulaşılamazsa SMS gider ve iş ertesi gün yine habersiz ziyarete çıkar. İkinci boşa ziyaretten sonra 48 saat askı, bir son arama, sonra Turkcell kuralıyla kapatma.
6. **Şebeke kümesi.** 2 saat içinde aynı binada 3 ya da 300 m içinde 5 BTK işi gelirse NOC kontrolü yapılır. Arıza varsa işler bekletilir ve çözümde doğrulama aramasıyla kapatılır.
7. **Kaynak.** Masa ≈32 kişi-saat/gün (4-5 kişi), teknisyen ≈41 km/gün. Kadro hedefi: hafta içi 16 aktif teknisyenle ~%66, 20 ile ~%77. Kadro 20'yi geçip kapasite bollaşınca katı 'önce BTK, sonra en eski' sırasına (HAM) geçmek BTK'da 2-4 puan kazandırır; KARMA'nın aşırı yük eşiği bu geçişi yalnız kısmen yapıyor.

## 10. Varsayımlar

| Parametre | Değer | Kaynak | Taranan aralık |
|---|---|---|---|
| Günlük geliş | Hafta içi 337,7 · Cumartesi 384 · Pazar 182 (× metro payı 0,96) | VERİ (ANLATILAN 1-15 Eylül) | ×0,85-1,15 |
| Tip payları | Bağlantı %44, Kanal %15, Cihaz İade %11, Modem %10, TV %9 ... | VERİ | - |
| Saatlik varış | 09:00'da %13 zirve, 10-19 arası saat başı %6-8 | VERİ | - |
| Konum | Metro binaları, aktif abone ağırlıklı; konumlu olma BOSS tip oranı (%0-100) | VERİ (bina_master + BOSS Lokasyon) | - |
| Telefonla çözülebilir BTK payı | Bağlantı %28,6, TV %34,1, Doping %33,7 | VERİ (TAMAMLANDI kapanış nedeni; üst sınır) | ×0,6-1,3 |
| Şebeke kaynaklı BTK payı | Bağlantı %11,2, TV %14,3; yarısı 300 m kümeler, çözüm medyanı 6 s | VERİ + VARSAYIM (küme) | - |
| Ulaşılabilirlik sınıfları (kolay/orta/zor) | 0,60, 0,25, 0,15; notlu birikimde 0,20, 0,35, 0,45 | VARSAYIM (veri: önce ulaşılamayana sonra da %94 ulaşılamıyor) | - |
| Tek aramada açma (gündüz, sınıf başına) | 0,80, 0,45, 0,12 | VARSAYIM | 0,70/0,35/0,08 - 0,88/0,55/0,18 |
| ρ: dışarıdaki müşterinin açma oranı / evdekinin | 0,30 | VARSAYIM | 0,1-0,9 |
| Habersiz ziyarette evde yok | hafta içi gündüz ~%22 (çalışan müşteri %8/%22/%45 + %6 gürültü); akşam/hafta sonu ~%11 | VARSAYIM | %15-45 |
| Teyitli ziyarette evde yok / randevuda gelmeme | %5 / %8 (geç kalınırsa başarı ×0,6) | VARSAYIM | - |
| Telefonla çözme başarısı | masa teşhisi %85, kısa kontrol %45; kendiliğinden düzelme %40 (ort. 6 s) | VARSAYIM | %60 / %30 |
| Yerinde süre | arıza 30, modem 35, 2.Donanım 55 dk (lognormal σ 0,5); hafif 12, şebeke 15; kapıda bekleme 10 | VERİ vekili (ardışık kapanış 31 dk) + VARSAYIM | - |
| Yol | kuş uçuşu ×1,35; şehir 25 km/sa (10 km üstü 60 km/sa); park 5 dk | VARSAYIM | 20-35 km/sa |
| Teknisyen vardiyası | gündüz 08:30-18:30 (BUGÜN ~09:15), akşam 12:00-21:00, 30 dk mola; Pazar tavan(0,55·N) | VERİ (Pazar 4-8 kişi) + VARSAYIM | N = 10-24 |
| Operasyon masası | 8 kişi 08:30-17:30, 4 kişi 17:30-20:30, Pazar 3; verim 0,8; başarısız arama 2 dk, randevu 4, teşhis 10 | VARSAYIM | 4-12 kişi; verim 0,6-0,95 |
| İlk seferde çözüm | %92 | VARSAYIM | - |
| Telefonla kapanışın ek tekrar riski | %6 (7 günlük tekrar bayraklıda %20) | VARSAYIM (veri: 15 günde tekrar %35) | - |
| Altyapı engeli | BTK'nın %2'si; çözüm medyanı 72 s; yarısı binada önceden biliniyor | VARSAYIM | - |
| SMS'e geri dönüş | %25 | VARSAYIM | - |
| Kurye (yalnız U1H) | kabul Modem %35 / STB %50 / Superbox %70; 40 durak/gün; destek araması %90 | VARSAYIM (U1H önerisi) | - |
| 7 gün içinde tekrar arıza bayrağı | BTK işlerinin %25'i | VERİ (U1H analizi) + VARSAYIM | - |

İlk hafta pilotta ölçülmesi gerekenler:

- Habersiz ziyarette evde yok oranı.
- İlk aramada ulaşma oranı.
- Masa uzaktan teşhisinin çözme oranı.
- Telefonla kapatılan işin 7 günlük tekrar oranı.
- Teknisyen başına ziyaret/gün.

Bu ölçümler `varsayilan()` içine yazılıp simülasyon yeniden koşulabilir.

## 11. Sınırlamalar

- **Rota planı.** Rota eniyilemesi (zaman pencereli araç rotalama) yok. Teknisyen her iş sonunda kuralına göre tek bir iş seçiyor. Pencere ağırlıklı stratejiler (U1H, BÖLGE) gerçek bir rota planlayıcıyla biraz daha iyi sonuç alabilir; BÖLGE-esnek kontrolü bu payın sıralamayı değiştirmediğini gösteriyor.
- **Kapsam.** Yalnız metro. Uzak ilçelerin yerel teknisyenleri ve kurulum ekipleriyle kaynak paylaşımı modellenmedi.
- **Veri kaynağı.** Telefonla çözülebilirlik ve yerinde süre, kapanmış işlerin toplu sayımından geliyor (TAMAMLANDI; bu istekte eklenmedi, önceki analiz toplu parametre olarak kullandı). Bu dosyaya burada doğrudan erişilmedi.
- **Ölçülmemiş davranış.** Müşteri davranışı (sınıf payları, ρ, evde yok) ölçülmedi; aralıklarla tarandı.
- **Başlangıç birikimi.** Kullanıcının 18:21 dışa aktarımı kullanıldı; 522 metro satırı alındı, metro dışı 79 satır atlandı. Bu dışa aktarımda Cihaz İade ve 2.Donanım yok, ama yeni gelişlerde bu tipler var. 16:45 anlık görüntüsündeki 953 işlik birikimle erime süreleri uzar.
- **Turkcell kuralları.** Askıdayken SLA saati duruyor mu, ulaşılamayan iş kaç denemede kapatılır? Bunlar teyit edilmedi. Modelde saat hep işliyor; 5-6 başarısız temastan sonra kapatılıyor.

## 12. Dosyalar ve çalıştırma

- `operasyon/analiz/simulasyon.py`: model, stratejiler, deneyler.
  - `python simulasyon.py`: tam set, 16 çekirdekte ~10 dk.
  - `--hizli`: kısa deneme.
  - `--tek KARMA 16`: tek koşu.
  - `--md`: raporu JSON'dan yeniden yazar.
- `operasyon/analiz/cikti/simulasyon.json`: bütün ortalamalar, en düşük ve en yüksek tekrar, günlük seriler, kadro taraması, duyarlılık ve sıralamalar.
- Gizlilik: çıktılarda yalnız toplu sayılar var. Müşteri, task ya da lokasyon kimliği, adres, telefon ya da kişi adı yok.
