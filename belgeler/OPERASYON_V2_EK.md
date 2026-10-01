# OPERASYON_V2_SPEC — Ek A2 (30.09 öğleden sonra, kullanıcının ikinci mesajı)

Bu ek `OPERASYON_V2_SPEC.md`'nin **üstündedir**: çelişki varsa bu ek geçerlidir. Kaynak: GEREKSINIMLER §G (G1–G17).
Süreç kuralları için ayrıca `docs/TURKCELL_SUREC_BILGISI.md` (extrajet araştırması, hazır olduğunda) okunur; oradan gelen
kurallar **ayar** anahtarlarıyla değiştirilebilir tutulur, koda gömülmez.

---

## EK-1 · Bir kişiye birden fazla görev (G12) — sahibi WP-A (sunucu) + WP-E (Ekip arayüzü)

- `kullanici.rol` (v1'de 4 değere genişletilen) artık **ana görev** = girişte açılan ana ekran. Yetki **görev kümesinden** gelir.
- **v6 (yeni, yalnız ekleme):**
  ```sql
  CREATE TABLE IF NOT EXISTS kullanici_gorev (
      kullanici_id INTEGER NOT NULL REFERENCES kullanici(id) ON DELETE CASCADE,
      rol TEXT NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
      PRIMARY KEY (kullanici_id, rol)
  );
  INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) SELECT id, rol FROM kullanici;   -- herkes bugünkü göreviyle
  ```
- `yetki.izinler(kisi)` = kümedeki görevlerin izinlerinin **birleşimi** (varsayılan YASAK kuralı aynen). Kümede yoksa → ana görev.
- Kural: kümede `satisci` varsa bölge gereklidir (bölgesizse bugünkü "Size henüz bölge atanmadı"). Ana görev her zaman kümenin içindedir.
- Küme ya da ana görev değişince `oturum_no + 1` (o kişinin cihazları yeniden girer).
- Silme ilişki sayımı (`/api/kullanici/{id}/iliskiler`) **`kullanici_gorev`'i engel saymaz** (CASCADE ile birlikte silinir).
- Ekranlar ve menü izinlerden çizilir; kişi yalnız görevlerinin açtığı bölümleri görür. Herkese açık olanlar: bina kartı/kimlik,
  ticket metni şablonu, harita altlığı, kendi profili.
- Ekip arayüzü: "Görevler" çoklu seçim (Satış · Operasyon · Teknik · Yönetici) + "Girişte açılacak ekran" (kümeden biri).
- Testler: {operasyon,yonetici} birleşimi görür; {satisci} iş emirlerine 403; görev çıkarılınca eski jeton 401; son yönetici korunur.

## EK-2 · Girişsiz kişiler: BOSS Mobil'le çalışan teknisyenler, personel rehberi (G9, G13) — WP-A + WP-E

Teknisyenlerin çoğu (≈65) işini **BOSS Mobil** ile yapar; bizde hesabı/telefonu olmayabilir. Atama yine de onlara yapılabilmeli
(sonra BOSS'a işlenir). Bu yüzden:

- **v1'deki `kullanici_yeni` tanımında tek değişiklik:** `telefon TEXT UNIQUE` (NOT NULL kaldırılır; SQLite UNIQUE birden çok NULL'a izin
  verir). Diğer her şey spec §1.4'teki doğrulanmış SQL'le birebir; WP-A doğrulamayı (özet, sayılar, FK) bu tanımla yeniden koşar.
- **v2 ek sütunlar (ALTER ADD):** `unvan TEXT` (Turkcell unvanı), `kaynak TEXT` ('elle' | 'rehber'), `giris_var` hesaplanır = telefon dolu.
- Telefonu olmayan kişi **giriş yapamaz** (giriş telefonla); davet kodu da verilmez. Ekip'te "Girişsiz · BOSS Mobil" rozeti; telefon
  eklenince bugünkü davet akışı çalışır. `telefon_goster(None)` → "—"; telefonu varsayan her kod yolu WP-A tarafından denetlenir.
- **Personel rehberi içe aktarımı:** `POST /api/kullanici/rehber` (`ekip.yonet`) — gövde: yapıştırılan düz metin (Atmosfer/Pusula
  "Çalışanlar" listesi: ad satırı + unvan satırı çiftleri). Kural:
  - Ad `anahtar()` ile mevcut kişiyle eşleşirse yalnız `unvan` yazılır (görevine dokunulmaz).
  - Eşleşmezse ve unvan bir göreve eşleniyorsa **girişsiz kişi** oluşturulur (`kaynak='rehber'`, telefon NULL, aktif=1).
  - Göreve eşlenmeyen unvanlar (Stok, İdari İşler, Finans, İK, Fiber Yayılım…) **alınmaz**, sayısı raporlanır.
  - Önce **önizleme** (eklenecek/güncellenecek/atlanacak sayıları ve listesi), sonra "Uygula". İki kez uygulamak çift kayıt üretmez.
- **Unvan → görev eşlemesi** `ayar.unvan_gorev_esleme` (JSON, Ekip ekranından düzenlenir). Varsayılan:
  | Unvan içinde geçen | Görev kümesi |
  |---|---|
  | `Teknik - Müdür` | teknik, yonetici |
  | `Teknik - Sorumlu` | teknik |
  | `Yeni Müşteri - Takım Lideri` | satisci, yonetici |
  | `Yeni Müşteri - Sorumlu` | satisci (bölgesiz; bölge Ekip'te verilir) |
  | `Satış Destek - Takım Lideri` | operasyon, yonetici |
  | `Satış Destek - Sorumlu` · `Satış Destek - Uzman` · `Hizmet Danışmanı` | operasyon |
  | `Satış-Müdür` · `Genel Koordinatör` | yonetici |
- BOSS "Ekip" sütunundaki ad (ör. teknisyen adı) `boss_ekip` eşleşmesinde (spec §3.4-3) rehberden gelen kişiyle de eşleşir.

## EK-3 · BTK saati abone kaynaklı askıda durur (G2) — WP-B (motor) + WP-C (çekmece) + WP-D (Takip)

- **v7 (yeni):**
  ```sql
  CREATE TABLE IF NOT EXISTS is_aski (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      is_no TEXT NOT NULL,                 -- is_emri anahtarı (FK yok; iz tablosu kuralı)
      baslama TEXT NOT NULL, bitis TEXT,   -- bitis NULL = sürüyor
      neden TEXT, kaynak TEXT NOT NULL CHECK (kaynak IN ('boss','elle')),
      durdurur INTEGER NOT NULL DEFAULT 0  -- bu askı BTK saatini durduruyor mu (ayar kuralından)
  );
  CREATE INDEX IF NOT EXISTS ix_is_aski_is ON is_aski(is_no);
  ```
- Her içe aktarımda: iş "Askıya alındı"ya geçmişse aralık açılır (`baslama` = raporun zamanı, kaynak='boss'); askıdan çıkmışsa kapanır.
  Operatör bizde askıya alırsa zaman kesindir (kaynak='elle'; BOSS'a işlenecek bayrağı da düşer). **Dürüstlük:** BOSS raporunda askı
  saati yok; rapordan gelen başlangıç, raporun indirildiği ana yuvarlanır — çekmecede "yaklaşık" yazar.
- `ayar.btk_durduran_aski` (JSON liste, varsayılan: nedeninde `abone` geçenler; extrajet araştırması netleştirince güncellenir).
  `ayar.son24_askida_durur` (varsayılan **false**: bayinin 24 s sözü takvim saatidir; true yapılırsa aynı kural 24 s'e de uygulanır).
- `btk_net_gecen = (şimdi − acilis) − Σ durdurur=1 askı süresi`; `btk_hedef_net = btk_hedef + Σ durdurur=1 askı süresi`.
  Renk ve "Gecikti" BTK'da net süreden hesaplanır. Çekmecede zaman çizelgesi: "BTK saati durdu · abone kaynaklı askı · 3 s 20 dk".
- Takip: "Askıda (BTK durdu) n", "Askıda uyanma yok n". Test: askı aç/kapa aralıkları, iki aralık, sürerken net süre, 24 s ayarı.

## EK-4 · BOSS/FOX ile konuşma sınırı ve eklentiye hazır giden kutusu (G1, G3, G8) — WP-B + WP-F (belge)

- **Kırmızı çizgi aynen:** sunucu Turkcell sistemlerine **yazmaz**. Tarayıcı eklentisi ayrı bir iştir ve Turkcell BT onayı bekler.
- Giden kutusunu eklentiye hazır yap: `GET /api/boss/giden` (`is.ata`) → `[{is_no, boss_task_no, alanlar: {ekip, randevu_baslangic,
  randevu_bitis}, neden, olusma}]` — BOSS'a birebir yazılacak değerler; `POST /api/boss/giden/{is_no}/islendi` (bugünkü "BOSS'a işlendi").
  Eklenti gelirse bu iki uçla çalışır; bugün operatör kopyala-yapıştır yapar.
- WP-F `docs/SAHA_KULLANIM.md` içine **"Hangi işlem nereye yansır"** tablosu ekler (her satır: bizdeki eylem → BOSS · FOX · Maya ·
  OneDesk · ONENT: `okunur (rapor)` / `elle işlenir (giden kutusu)` / `eklentiyle (onaylı fazda)` / `yok`).

## EK-5 · Ticket ekibi ve başlıkları (G10) — WP-A (sunucu) + WP-E (Ticketlar arayüzü)

- `ticket` tablosuna (ALTER ADD): `onedesk_ekip TEXT`, `kategori TEXT`.
- `ayar.ticket_kategorileri` varsayılan (ekip `TEAM-TAS1BRS`):
  `NETWORK / FTTB / SW ARIZA` · `NETWORK / GPON / SINYAL VAR / IP ALAMIYOR` · `NETWORK / GPON / SINYAL YOK / MEVCUT BINA` ·
  `NETWORK / GPON / SINYAL YOK / YENI BINA` · `NETWORK \ IMALAT REVIZYON TALEBI` · `NETWORK \ GPON \ ONT_SABITLEME_SORUNU` ·
  `NETWORK \ HATALI NW READY BILDIRIMI` · `NETWORK \ BASK \ SW YER DEGISIMI` · `NETWORK \ KABIN HASAR BILDIRIMI` ·
  `NETWORK \ EK SWITCH VE SPLITER TALEBI` · `NETWORK \ SWITCH UPS - FAN SES PROBLEMI`.
- "Yeni ticket" formunda ekip (varsayılan TEAM-TAS1BRS) + başlık seçimi; sinyal şablonu "SINYAL YOK" başlıklarında önerilir.

## EK-6 · Hikâye gibi anlatan, perdeleyen arayüz; küçük sevinçler (G7, G14, G15, G16) — WP-E (+ C, D)

- Her ana ekranın başında **tek hikâye cümlesi** (durumdan üretilir): "Bugün 437 iş var. 12'sinin 24 saatine 2 saatten az kaldı —
  önce onlar." Ayrıntı perdenin arkasında (aç/kapa, çekmece). Önce en önemli, sonra ayrıntı.
- İç jargon yok (spec §6.15 sözlüğü). Bir ekranda tek birincil eylem.
- **Küçük sevinçler (ayar `kutlamalar`, varsayılan açık, kapatılabilir):** "Atanmamış iş kalmadı" ve "Bugünün bütün BTK işleri
  çözüldü" anlarında kısa, sessiz bir animasyon; logoya 5 kez dokununca ekibin küçük bir notu (easter egg). Hareket
  `prefers-reduced-motion`'a uyar. İş akışını asla bekletmez.
- "Oyun gibi" canlı operasyon katmanı (3B ikiz üzerinde teknisyen/iş akışı) **bu yapımın dışında**; sonraki faz.

## EK-8 · PS26'nın yerini almak (kullanıcı: "data.xlsx bu sisteme geçerse PS26'yı kaldıracağım") — sahibi WP-G (yeni)

PS26 bugün: `data.xlsx` → `convert.py` → `data/*.json` → git push → GitHub Pages'te sayfa sekmeli + "Ara..." kutulu tablo görüntüleyici
(herkese açık!). Sayfalar: TICKET (198), GUZERGAH (16.912 satırın ~64'ü dolu; ticket biçiminde, konu "güzergah"), ALTYAPI (67; müşteri,
kanal, başlangıç, satıcı, bölge — altyapı yüzünden kurulamayan satışlar), PVT (satıcı başına sayım), LOCS/ORIGN (bina arama = bizde bina
tablosu). `imgs/<ticket no>.zip` içinde ticket'a ait fotoğraflar (jpeg).

- **İçe aktarım** `saha/ps26_aktar.py` (yeni; `python -m saha.ps26_aktar <data.xlsx> [--kuru]` + ekrandan): etkisiz (iki kez = aynı),
  önce önizleme. TICKET → mevcut ticket aktarımıyla aynı kurallar (spec'teki `ticket_aktar` yeniden kullanılır). GUZERGAH → ticket
  (`tur='guzergah'`), yalnız dolu satırlar. ALTYAPI → yeni `altyapi_bekleyen` tablosu (ALTER/CREATE yalnız ekleme: id, musteri_no,
  kanal, baslangic, satici_ad, bolge, bina_serial NULL, durum 'bekliyor'|'kuruldu'|'iptal', not, olusturma, guncelleme).
  PVT türetilir (saklanmaz). LOCS/ORIGN içe alınmaz (bina tablosu zaten var).
- **Ticket fotoğrafları:** `imgs/<no>.zip` → `saha/ek/ticket/<ticket_id>/…` (git dışı klasör), `ticket_ek` tablosu (id, ticket_id,
  dosya_adi, boyut, sha256, olusturma). Yetki: ticketı görebilen görür. Uçlar: liste, küçük resim, tam resim, yükle (sürükle-bırak,
  telefonda kamera/galeri). 10 MB/dosya sınırı; yalnız jpeg/png/heic→jpeg.
- **"Tablolar" ekranı** (Excel alışkanlığı — kullanıcının kelimesiyle "Microsoft'u geçmek"): PS26 gibi üstte sayfa sekmeleri
  (Ticketlar · Güzergah · Altyapı bekleyen · Binalar · İşler), tek "Ara…" kutusu (bütün sütunlarda, Türkçe harf duyarsız), sütun
  başlığına tıklayınca sıralama ve süzgeç, dondurulmuş başlık, klavyeyle hücre gezinme, seçip **Ctrl+C ile Excel'e yapıştırılabilir**
  kopya (sekme ayrımlı), "Excel'e indir". Telefonda satırlar kart olur, arama aynı. Kişisel veri yetkiyle süzülür.
- Menü: Yönetici/Operasyon için "Tablolar" (WP-E menüye ekler; ekran WP-G'nin).

## EK-9 · Excel alışkanlığı her listede (G7, kullanıcı: "insanlar Excel dışında bir şey kullanmak istemiyor") — WP-E ortak bileşeni

Ortak `Tablo` bileşeni (WP-E sahibi, `saha_app/src/ortak/Tablo.tsx`): sıralama, sütun süzgeci, arama, sanal kaydırma (20.000 satır akıcı),
klavye (ok tuşları, Enter=aç, Esc), seçim + Ctrl+C sekme ayrımlı kopya, "Excel'e indir". İşler panosunun liste kipi, Ticketlar ve
Tablolar bunu kullanır. Bildik görünüm: ince ızgara çizgileri, sağa yaslı sayılar, Türkçe biçim.

## EK-10 · Rapor klasör izleme — "15 dakika"nın asıl engeli (F17) — WP-B

Sunucu kullanıcının bilgisayarında çalıştığı için BOSS'tan indirilen rapor aynı makineye düşer. `ayar.izlenen_klasorler` (varsayılan:
sunucuyu çalıştıran kullanıcının İndirilenler ve Masaüstü klasörleri) ve `ayar.izlenen_desenler` (varsayılan `TeknikTaskDetayRaporu*.xlsx`,
FOX dışa aktarım adları araştırmadan sonra). Yeni ya da değişen dosya 5 sn sabit kalınca spec §4 hattından **aynen** geçer (sha
etkisizliği, eksik/eski rapor bekçisi, önizleme gerektiren durumda otomatik uygulanmaz → "Onay bekleyen rapor" bildirimi). Yoklama tabanlı
(15 sn; ek paket yok), kapatılabilir. Ekranda: "Yeni rapor alındı · 11:38 · 12 yeni iş, 3 kapandı" bildirimi.

## EK-11 · Masaüstü uygulaması (exe) — yapım sonrası sıradaki adım (E1, E2)
Kullanıcı: "exe olarak yaparsan daha özgür oluruz, web bizi kısıtlıyor". Karar: **tek kod tabanı, iki kabuk.** Ofis (operasyon,
yönetici) için Windows masaüstü uygulaması (Electron — sunum uygulamasındaki yol; kurulum sihirbazı + tek exe; içinde sunucu, klasör
izleme, yerel bildirim, Excel'i doğrudan açma); telefonlar (teknik, satış) için bugünkü web uygulaması (PWA). Bu yapımda arayüz kodu
kabuktan bağımsız yazılır (tarayıcıya özgü varsayım yok), böylece exe paketleme sonraki adımda yalnız kabuk işi olur.

## EK-12 · Turkcell süreç kuralları → varsayılanlar (extrajet araştırması 30.09; kaynak `docs/TURKCELL_SUREC_BILGISI.md`)

Hepsi **ayar** anahtarıdır (kod içine gömülmez); aşağıdakiler varsayılan değerlerdir. Belirsiz olanlar kullanıcıya sorulana kadar işaretli.
1. **Hedef saatler:** arıza/bağlantı **24 s** (belgede kesin); "TV 6 s / Bağlantı 12 s" belgede bulunamadı — kullanıcının **FOX dışa
   aktarımındaki "Hedef SL"** sütunundan geliyor. Kural: FOX verisi olan işte FOX Hedef SL kullanılır; yoksa 24 s. Diğer: modem değişim
   7 gün, TT fiber saha bağlantı 48 s, ek kapasite 5 (+3) iş günü, Cihaz İade Bekleniyor 15 gün (kendiliğinden kapanır, sevk edilmez;
   elden geri alım hariç), ATA 7 gün.
2. **BTK şikayet sayacı** (şikayet bildirilmiş işte): ilk şikayet **10 iş günü**, reopen **5 iş günü**; alarm 8./10. (reopen 3./5.) iş günü.
   TÇS (tahmini çözüm tarihi) tek sefer girilir, değişmez → formda "gerçekçi, ekipten teyitli" onay kutusu; girildiyse "BTK'da kapalı,
   FOX'ta açık" rozeti. BTK'ya bildirilmiş task elle iptal edilemez (uyarı).
3. **Askı ve saat (EK-3'ü tamamlar):** askı **nedeniyle** tutulur. Duraklatan nedenler varsayılanı: abone kaynaklı, abone kaynaklı (akşam),
   BTK "Bilgi & Belge" (10 gün, müşteri dönünce uyanır), genel arıza; **TT kaynaklı belirsiz → varsayılan duraklatmaz, kullanıcı onayı**.
   Abone kaynaklı askı **geçerliliği:** Webphone ile aranmış + ilk aramadan sonra SMS atılmış + **2 farklı günde** aranmış; değilse askı
   süresi saate eklenmez ve "geçersiz askı" uyarısı. **Bayi kaynaklı randevu ötelemesi duraklatmaz.** Fiber teknikte abone kaynaklı askı
   en çok **4 gün** (sınırda uyarı).
4. **Ulaşılamayan müşteri merdiveni (EÇM Müşteri Arama Kuralları, 29.04.2026) — Aranacaklar'ın varsayılanı:** Gün 1 A1 (10:00–18:00;
   ayarla 20:00'ye) → BOSS **"Talep Ulaşamama SMS"** (giden kutusuna düşer, zorunlu işaret) → A2 A1'den **≥ 3 saat** sonra → SMS;
   Gün 2 A3 (zorunlu) → SMS, ulaşılamazsa ≥ 3 s sonra A4. Her aramada sonuç: süre ≥ 30 sn / meşgul-kapalı / dıt; Webphone dışı arama askı
   hakkı vermez. İrtibat hatalı → **ATA havuzu** durumu + açıklama; yeni numarada merdiven sıfırlanır. 22:00 sonrası arama yok.
   "Ulaşılamadı" kapanışı yalnız merdiven tamamsa açılır (kapanışın kimde olduğu belirsiz → kullanıcı sorusu).
5. **Triyaj şeridi:** her işte kaynak sistem (BOSS / FOX / ikisi). BOSS raporundaki task = sahaya inmiş iş (sevk). FOX'ta kalanlar
   (944 Bayi Kanal İnceleme: 48 s + 24 s açıklama sayacı, BTK alt akışı, fatura, iyileştirme) → **"izle, sahaya gönderme"** şeridi.
   **40 Kanal Şikayeti** bayiye düşmüşse SL zaten kaçmıştır → en üst öncelik, Kanal Şikayeti masası.
6. **Kesintiye duyarlı sevk:** "Santral Arıza" bülteni (Bursa/Yalova, Devam ediyor/Planlandı) yapıştırılınca il-ilçe + GPON/FTTX
   ayrıştırılır; etkilenen ilçe/öbekteki bağlantı/TV işleri **"Genel arıza — sevk etme"** olur (genel arıza askısı, bülten bitince uyanır).
   Bülten yoksa ve bölgede toplu arıza varsa: aynı bölgeden **en az 5 örnek** → "verimlilik ekibine gönder" paketi (kopyalanır).
7. **Ticket:** varsayılan ekip TEAM-TAS1BRS (BÇO Bursa); listede TEAM-TAS1KOC da (Yalova'nın bağlı olduğu BÇO belirsiz). Zorunlu alanlar:
   müşteri no, Hizmet ID, seri no (değişimde eski+yeni), SW ip/port veya OLT ip/port, yapılan kontroller, aranmak istediği saat (≤ 22:00),
   tarih-saatli ekran görüntüsü (ek dosya). BÇO'da 24 saati geçen ticket → "TL'ye mail: OneDesk ID + müşteri no" hatırlatması; kırmızı hat
   mail konusu şablonu `Task No / Task Adı / Kırmızı Hat` (Örümcek için hazır taslak).
8. **Hangi işlem nereye yansır** tablosu (EK-4): `TURKCELL_SUREC_BILGISI.md` §F'deki tablo birebir kullanılır (randevu → BOSS; ulaşılamadı
   → BOSS Talep Ulaşamama SMS + Webphone sonuç kodu; askı → BOSS task askısı; kapama → BOSS; TÇS → BOSS/FOX; modem değişim → Maya; 944 →
   FOX; ticket → OneDesk/OneNT). Yansıtılamayanlar (yalnız Global Bilgi/Turkcell): BTK form yanıtı/kapama, Bilgi & Belge, Ara Bilgilendirme,
   FOX task iptali, reopen, kanal şikayeti kararı, fatura müdahalesi.

## EK-7 · Bu yapımın dışında kalanlar (sıraya alındı)
Tarayıcı eklentisinin kendisi (G1, BT onayı), Örümcek'e hazır mail taslakları (G6, alıcılar araştırmadan sonra), Atmosfer/Pusula'dan
otomatik rehber çekme (G9; bugün yapıştırma ile), canlı operasyon oyunu (G15), exe kabuğu (EK-11), paketleme/lisans (E),
ofis dışından erişim (VPN/HTTPS — kullanıcı kararı; PS26'nın kapanması buna bağlı).
