# Operasyon planı: tek sayfa

*Hasan Bey için · Dehanet EÇM · 30.09.2026 · Ayrıntı: `docs/OPERASYON_TASARIM.md`*

## Hedef

**Kurulum dışındaki her iş emri 24 saatte sonuçlanır. BTK arızaları öncelikli yürür; hiçbiri 48 saati geçmez.**

## Bugün (29.09)

| | |
|---|---|
| Açık iş (BOSS) | 2.567: mevcut müşteri 953, kurulum 1.614 |
| 24 saati geçmiş mevcut müşteri işi | %73 |
| Gerçek 24 saat uyumu | 1 Eylül %65 → 12-14 Eylül **%21-24** |
| Günlük gelen / kapanan (hafta içi) | 338 / 224. Birikim 15 günde **+1.180** |
| Arıza ekibi | 12 kişi, günde ~10 aktif. İlk iş kapanışı ~11:00 |
| "Arandı, ulaşılamadı" notlu açık iş | 601 işin 518'i |

## Neden

1. **Kapasite:** günde ~200 saha ziyareti lazım, ~170 yapılıyor.
2. **Süreç:** herkesi önce aramak ofiste darboğaz yaratıyor; teknisyen eklense bile uyum %31'i geçmiyor.
3. **Sıra:** kapasite kıtken "en eski önce" kuralı BTK'yı gömüyor.

## Plan: KARMA-2 (7 strateji, 2.000'i aşkın simülasyon, 3 bağımsız hakem)

1. **Aramadan sevk:** iş, mahallesinin öbeğine ve o öbeğin teknisyenine gider. Evde olmayanı operasyon arar.
2. **BTK hızlı şerit:** masa 45 dk içinde paralel teşhis yapar; telefonda çözülen iş ziyarete gitmez.
3. **Kapasiteye göre sıra:** kapasite yetmezken önce BTK ve 24 saatine yetişecek iş alınır, gecikmişe kota ayrılır. Kapasite yetince önce BTK, sonra en eski.
4. **Altyapı sorunlu binaya gidilmez:** bina başına tek OneDesk ticket açılır.
5. **Her sabah kapasite göstergesi:** "bugün X teknisyen lazım, Y var". Açığı kapatmak için kurulumdan esnek teknisyen önerilir.

## Beklenen sonuç (simülasyon; söz değil, pilotla doğrulanacak)

| Aktif arıza teknisyeni | 24 s uyumu | BTK 24 s | Birikim |
|---|---|---|---|
| Bugünkü süreç, herhangi kadro | ~%24 | ~%25 | Büyür |
| **10** (bugün) + yeni süreç | %52 | %51 | Büyür (~+87/gün) |
| **16** + yeni süreç | %71 | %75 | Başlangıç birikimi ~1 haftada erir, sonra yavaş büyür |
| **20** + yeni süreç | %79 | %79 | Denge |

**Asıl kaldıraç kadro.** Simülasyonda yöntem aynı kadroyla uyumu yaklaşık iki katına çıkarıyor; ama dengeye ~20 aktif teknisyenle geliniyor.
Hiçbir senaryo %90'a ulaşmıyor.

## Sizden istenen kararlar

1. **Kadro:** 10 iş günü için 4 kişilik kurtarma timi, sabah formülüyle kurulumdan günlük esnek teknisyen (en çok 8), ilk ziyaretin 09:00'dan önce yapılması. Kalıcı kadro kararı 2 haftalık pilottan sonra.
2. **Masa:** operasyonun 20 kişisinden 5-6'sı telefon masasına (BTK teşhisi, evde yok, akşam bandı).
3. **Akşam vardiyası:** kadro 16-18'e çıkınca 2-3 kişi, 12:00-21:00.
4. **BT talepleri:** 30 dakikalık BOSS/FOX raporu (köprü ya da zamanlanmış rapor), teknisyen için VPN + HTTPS, yerel veri işleme onayı.
5. **Acil (KVKK):** PS26 deposunun GitHub Pages yayını kapatılmalı; tur raporu ve müşteri no'lu listeler herkese açık olabilir.

## Takvim

| Faz | Ne | Süre |
|---|---|---|
| 0 | Kararlar; 11:00 varsayılan dilimi ve "önce herkesi ara" düzeni durur | 1-3 gün |
| 1 | Rapor içe alma (var) + FOX + triyaj + 24 saat saati + öbek panosu + kapasite göstergesi + günlük rapor | 1-2 hafta |
| 2 | Teknisyen ekranı + 2 öbekte 2 haftalık pilot | 4-5 hafta |
| 3 | 30 dakikalık canlı senkron, OneDesk/ONENT takibi | BT onayına bağlı |
| 4-5 | Kurulum ekipleri; sonra paketleme ve lisans | Sonra |
