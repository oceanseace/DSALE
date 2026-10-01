# Saha Sistemi — veri modeli ve API sözleşmesi (v1)

Amaç: 8 satışçının sahada hangi binaya gittiğini, neyi bulduğunu ve nereye hâlâ dokunulmadığını
tek yerden takip etmek. Algoritma "bugün şuraya git" listesini üretir; satışçı sonucu işler;
yönetici haritada boşlukların dolduğunu görür.

Karar (2026-09-21): **PWA** (telefon tarayıcısı → ana ekrana ekle) · sunucu **ofisteki bilgisayarda**
· ilk fazda **bina bazında** takip (daire kırılımı v2) · giriş **telefon + 4 haneli PIN**.

> HTTPS notu: "ana ekrana ekle" ve çevrimdışı çalışma yalnız HTTPS adreste açılır. Ofis ağında
> http://<pc-ip>:8080 ile her şey çalışır (çevrimdışı hariç). Sahadan erişim için Cloudflare Tunnel
> / şirket VPN / sabit IP gerekir — kullanıcı onayı alınmadan dışarı açılmaz.

## 1. Veritabanı (SQLite, `saha/saha.db`, WAL)

| Tablo | Alanlar |
|---|---|
| `kullanici` | id · ad · telefon (tekil, 5XXXXXXXXX) · pin_hash · rol (`satisci`\|`yonetici`) · bolge (1..8, null=yönetici) · aktif · olusturma |
| `bina` | bina_serial (PK) · ad · site_adi · mahalle · ilce · il · cadde · sokak · kapi_no · lat · lon · kat · daire · res_hp · aktif_res · firsat · sales_ready · bolge · obek · site_grup |
| `bina_durum` | bina_serial (PK) · durum · son_ziyaret · son_kullanici_id · son_sonuc · tekrar_tarih · toplam_satis · not |
| `ziyaret` | id · offline_id (tekil) · bina_serial · kullanici_id · zaman · sonuc · satis_adedi · konusulan_daire · not · lat · lon · cihaz |
| `gorev` | id · kullanici_id · tarih · durum (`acik`\|`tamam`) · olusturan_id · kaynak (`algoritma`\|`yonetici`) · not |
| `gorev_bina` | gorev_id · bina_serial · sira · durum (`bekliyor`\|`tamam`\|`atlandi`) |
| `ayar` | anahtar · deger |

`bina_durum.durum`: `bekliyor` (hiç dokunulmadı) · `planli` (bugünün listesinde) · `ziyaret_edildi` ·
`tekrar_gel` · `girilemedi` (yönetici/kapıcı izin vermedi) · `altyapi_sorunu`.

`ziyaret.sonuc`: `satis` · `ilgilenmedi` · `evde_yok` · `randevu` · `altyapi_sorunu` · `girilemedi` · `yanlis_adres`.

Tohumlama: `data/master/bina_master.csv` + `outputs/N08_res_hp/atama.csv` (bölge) → `bina`.
Her bina için `bina_durum.durum='bekliyor'`. Kullanıcılar: 1 yönetici + 8 satışçı (ad/telefon
yönetici ekranından düzenlenir, PIN ilk girişte belirlenir).

## 2. Öncelik ve rota algoritması (`saha/rota.py`)

`oncelik = firsat × yeni_site_carpani × tekrar_carpani × doygunluk_carpani`
- `yeni_site_carpani`: sales_ready son 12 ayda 1,6 · 12-24 ay 1,3 · daha eski 1,0 (yeni açılan siteler daha yüksek potansiyel)
- `tekrar_carpani`: `tekrar_gel` ve tarihi gelmişse 1,4 · `girilemedi` 0,4 · `altyapi_sorunu` 0,2
- `doygunluk_carpani`: penetrasyon %60 üstü 0,7 · %30 altı 1,2
- `bekliyor` dışındaki binalar 30 gün boyunca listeye girmez (tekrar_gel hariç).

Rota: satışçının bölgesindeki uygun binalardan en yüksek öncelikli ~200 aday → başlangıç noktasına
(ofis veya satışçının konumu) göre en yakın komşu + 2-opt ile `adet` (varsayılan 25) binalık tur;
aynı site grubundaki binalar peş peşe gelir. Çıktı: sıralı liste + her adım için metre cinsinden mesafe.

## 3. API (FastAPI, `/api`, JWT Bearer, tüm metinler Türkçe)

**Giriş**
- `POST /api/giris` `{telefon, pin}` → `{token, kullanici}` · ilk girişte PIN yoksa `{pin_belirle:true}`
- `POST /api/pin` `{telefon, pin}` (ilk kez belirleme, yönetici onaylı davet ile)
- `GET /api/ben` → kullanıcı + bugünün özeti `{gorev_id, toplam, tamam, kalan, satis}`

**Satışçı**
- `GET /api/gorev/bugun` → `{gorev_id, tarih, binalar:[{bina..., sira, durum, mesafe_m}]}`
- `POST /api/gorev/olustur` `{adet?, baslangic?:[lat,lon]}` → kendine yeni liste (algoritma)
- `POST /api/ziyaret` `{offline_id, bina_serial, sonuc, satis_adedi?, konusulan_daire?, not?, lat?, lon?, zaman}` → idempotent
- `POST /api/ziyaret/toplu` `[…]` → çevrimdışı kuyruk senkronu (aynı idempotanlık)
- `GET /api/bina/{serial}` → bina + son durum + ziyaret geçmişi
- `GET /api/bina?bolge=&durum=&mahalle=&q=&limit=` → arama/liste (hafif alanlar)
- `GET /api/harita?bolge=` → harita için sıkı diziler `{serial[], lat[], lon[], durum[], firsat[]}`

**Yönetici**
- `GET /api/ozet/gun?tarih=` → satışçı bazında `{ziyaret, satis, ret, randevu, kalan}`
- `GET /api/ozet/kapsama?kirilim=bolge|mahalle` → `{toplam, dokunulan, oran, kalan_firsat}`
- `GET/POST /api/kullanici` · `POST /api/kullanici/{id}/pin-sifirla`
- `POST /api/gorev/ata` `{kullanici_id, tarih, bina_serial[]|mahalle|bbox, adet?}` → elle görev atama
- `GET /api/dosya/rapor.xlsx?tarih=` → günlük rapor (Excel)

Hata biçimi: `{hata:"...", kod:"..."}` · HTTP 401 → uygulama giriş ekranına döner.

## 4. Uygulama ekranları (mobil öncelikli, tek elle kullanım)

1. **Giriş** — telefon + 4 hane PIN, büyük tuşlar.
2. **Bugün** — sıralı kart listesi: bina adı, mahalle/sokak, daire sayısı, "boş kapı" rozeti, mesafe.
   Üstte ilerleme çubuğu ("12/25 bina"). Tek dokunuş → bina ekranı.
3. **Bina** — adres, kat/daire, boş kapı, mevcut abone; **iki büyük buton**: "Yol tarifi" (Google/Yandex
   Maps'e derin bağlantı) ve "Sonucu işle". Sonuç ekranı 6 büyük seçenek (satış · ilgilenmedi · evde yok ·
   randevu · altyapı · girilemedi), satışta adet, isteğe bağlı not. Kaydet → listeye döner, bina yeşile döner.
4. **Harita** — kendi bölgesi; yeşil = dokunuldu, gri = bekliyor, sarı = tekrar gel. Bugünün rotası çizili.
5. **Ben** — bugün/hafta: ziyaret, satış, dönüşüm; kalan bina sayısı.
6. **Yönetici** — canlı harita (kapsama ısısı), satışçı kartları, mahalle/bölge kapsama tablosu,
   görev atama (haritadan veya mahalleden seç → satışçıya gönder), günlük rapor indir.

Çevrimdışı: uygulama kabuğu + bugünün listesi önbellekte; ziyaretler IndexedDB kuyruğuna yazılır,
bağlantı gelince otomatik gönderilir. Ekranda "3 kayıt bekliyor" rozeti.

## 5. Klasörler
- `saha/` — FastAPI uygulaması, SQLite şeması + tohumlama, rota/öncelik algoritması, testler
- `saha_app/` — PWA (Vite + React + TS), `saha_app/dist` derlenir ve FastAPI tarafından sunulur
- `saha/baslat.bat` — ofis bilgisayarında tek tıkla sunucu

---

## 6. v1 uygulamasında netleşenler (2026-09-21, bütünleştirme)

Sözleşme yazıldığında belirsiz kalan ve uçtan uca denemede hataya yol açan
noktalar. Yenisini yazan herkes önce burayı okusun.

**İki ayrı "durum" vardır, karıştırılmamalı.** Bina kartı ikisini de taşır:

| Alan | Değerler | Anlamı |
|---|---|---|
| `durum` | `bekliyor` · `planli` · `ziyaret_edildi` · `tekrar_gel` · `girilemedi` · `altyapi_sorunu` | Binanın hayattaki hâli. Bugünün listesine giren bina **`planli`** olur. Harita rengi buradan. |
| `gorev_durum` | `bekliyor` · `tamam` · `atlandi` | Binanın **bugünkü listedeki** hâli. "Bu binayı gezdim mi?" sorusunun cevabı budur. |

> Uygulama bu ikisini karıştırırsa günün listesi ilk açılışta "25/25 bitti"
> görünür (bütün binalar `planli` olduğu için) ve ekran kullanılamaz hâle gelir.

**İlk giriş üç adımdır:** telefon → `POST /api/giris` → `{pin_belirle:true}` →
**6 haneli davet kodu** → `POST /api/pin {telefon, pin, davet_kodu}` → jeton.
Davet kodu olmadan PIN belirlenemez; uygulama kodu sormazsa hiç kimse sisteme
giremez.

**Ziyaret kaydı yan alanlar yüzünden reddedilmez.** Özü `bina_serial` + `sonuc`;
`cihaz` (80 karaktere kırpılır), `notu` (1000) ve `konusulan_daire` (serbest
metinden sayı çıkarılır) hiçbir koşulda 422 üretmez. Sahadaki kayıt, tarayıcı
künyesi uzun diye kaybolamaz.

**Bina kartı alan adları:** görünen ad hem `baslik` hem `ad` alanında gelir
(aynı metin), tek satır adres `adres` alanındadır.

**Sözleşmeye eklenen uçlar ve alanlar:**
- `GET /api/yollar?bolge=` → harita arka planı (`data/ref/osm_yollar.geojson`,
  bölge verilirse o bölgenin kutusuna kırpılır). İsteğe bağlı: 404 dönerse
  harita yolsuz çizilir.
- `GET /api/ben` → `hafta:{ziyaret,satis,randevu}` ve
  `bolge:{toplam,dokunulan,kalan,kalan_firsat}` (§4.5 "Ben" ekranı için).
  `hafta.satis` ve bugünkü `satis` **aynı şeyi** sayar: satılan abonelik adedi.
- `GET /api/harita` → `ad[]` dizisi (haritada noktaya dokununca bina adı).
- `GET /api/saglik` ve `GET /api/ben` → `demo: true|false` (gösterim verisi
  kuruluysa ekranlar uyarı şeridi gösterir).
- `POST /api/ziyaret` → isteğe bağlı `tekrar_tarih` (randevu günü).

**Denetim sonrası eklenenler (2026-09-21, düzeltme turu):**

- `POST /api/ziyaret/toplu` → yanıta **`kabul: [offline_id, ...]`** eklendi.
  Uygulama kuyruktan **yalnız bu listedeki** kayıtları siler; `hatali`
  listesindekiler telefonda kalır ve satışçıya gösterilir. Sayıya bakıp
  kuyruğu topluca silmek YASAK — sunucunun reddettiği kayıt aksi hâlde
  sessizce kaybolur.
- `POST /api/ziyaret` → isteğe bağlı **`duzeltilen_offline_id`**. Verilirse o
  eski kayıt `iptal=1` olur, sayaçlardan düşer ve yanıt `duzeltildi: true`
  döner. "Evde yok yerine yanlışlıkla Satış işledim" böyle düzeltilir;
  iki kayıt birden sayılmaz.
- `POST /api/ziyaret/{id}/iptal` → kaydı iptal eder (yönetici, ya da kaydı
  giren satışçı aynı gün içinde). Sayaçlar geri alınır, `bina_durum` kalan
  GEÇERLİ ziyaretlerden yeniden hesaplanır, satır geçmişte iz olarak kalır.
- `POST /api/kullanici/{id}/cihaz-cikis` → o kişinin bütün cihazlarını çıkış
  yaptırır, **PIN'i değiştirmeden** (telefon kaybolduğunda ilk hareket).
- `GET /api/ayar` · `POST /api/ayar` → `yardim_telefon` / `yardim_ad`.
  Giriş ekranındaki "Giriş yapamıyor musun?" bağlantısı buradan beslenir.
- `GET /api/saglik` → `yazilabilir: bool` (disk dolu / veritabanı salt-okunur
  ise `false`) ve `etiketler` (sonuç ve durum metinleri). **Sonuç etiketleri
  tek kaynaktan gelir**: uygulama kendi sabit listesini tutmaz, yoksa aynı
  sonuç satışçıda "Giremedim", raporda "Girilemedi" diye görünür.
- `POST /api/giris` → **PIN'siz yoklama**. Uygulama önce boş PIN ile sorar;
  yanıt `{pin_belirle: true}` ise ekran doğrudan davet kodu adımına geçer.
  Yoklama hesabın **adını döndürmez** ve hatalı deneme sayılmaz.
- `GET /api/ozet/kapsama` → satırlarda `ilce` + `mahalle` ayrı alanlar
  (`kirilim=mahalle` artık **ilçe+mahalle çifti** ile gruplar: Bursa'da "Yeni"
  mahallesi dört ayrı ilçede var), ayrıca `temas` (kapı açıldı, konuşuldu) ve
  `dokunulmayan_firsat`. **`kalan_firsat` = satılmamış kapı**
  (`firsat - toplam_satis`), "dokunulmamış binanın bütün kapıları" değil.
- Bina kartı → `penetrasyon` ölçülemiyorsa **`null`** döner (eskiden `res_hp=0`
  olan binada "%0 doluluk, 14 daire" gibi kendi içinde çelişen bir kart
  çıkıyordu); oran hiçbir zaman %100'ü aşmaz.
- `POST /api/ziyaret` → `zaman` **saat dilimiyle** (`+03:00` ya da `Z`) kabul
  edilir ve yerel saate çevrilerek saklanır; dilimsiz gelirse yerel varsayılır.
  İleri tarihli (+5 dk üstü) ya da 14 günden eski damgalar sunucu saatine
  çekilir — bozuk saatli tek bir telefon binayı iş havuzundan düşüremez.

**Son bütünleştirme turunda eklenenler (2026-09-21):**

- `GET /api/gorev/bugun` → **`onceki_binalar: [BinaKart, ...]`**. Aynı GÜN daha
  önce bitirilmiş listelerin binaları. Satışçı 25'i bitirip "yeni liste al"
  derse sunucu sabahki görevi kapatıp yenisini açıyor; uygulama yalnız açık
  görevi gösterdiği için sabahki emek ekrandan siliniyordu. Bu alan "Bitenler"
  bölümünün altına eklenir, **ilerleme sayacına karışmaz**: `ozet.toplam` ve
  `ozet.tamam` yalnız AÇIK listeyi sayar, yoksa ikinci listede "25 / 50" gibi
  bir sayı çıkar. Liste yoksa alan boş dizi döner.
- Rota, bölgenin sonunda iki parçalı kurulur: kalan dokunulmamış bina bir
  günlük işin altına düşünce **önce onlar** alınır, gün tekrar ziyaretlerle
  doldurulur. Sözleşmedeki formül değişmedi; değişen, puan yarışının son
  binaları kalıcı olarak elemesinin engellenmesi (bkz. `docs/SAHA_KULLANIM.md`
  § Kapsama simülasyonu).

---

## 7. Faz 2 (2026-09-29): veri kalitesi · bölge planlayıcı · tur raporu · ticket · 3B · altlık

Bu bölüm yalnız EKLER; §1-6'daki hiçbir uç ya da alan kaldırılmadı. Kod:
`saha/yonetim_uclari.py` (uçlar), `saha/veri_kalitesi.py`, `saha/bolgeleme.py`,
`saha/tur_raporu.py`, `saha/ticket.py`, `saha/geometri.py`, `saha/altlik.py`,
kurallar `dsale/kalite.py`. Hata biçimi aynı: `{hata, kod}`. "Yönetici" yazan uçlar
satışçıya **403 `yasak`** döner.

### 7.0 Veritabanı eklemeleri (hepsi göçle, yalnız EKLEYEREK)

Sunucu açılırken `db.gocler()` eksik sütun/tabloyu ekler; hiçbir satır silinmez,
değişmez. Canlı veritabanının bir kopyasında denendi: 9 kullanıcı, 1.257 ziyaret,
7 görev, 180 görev binası, 19.706 bina ve bütün `bina_durum` satırları birebir aynı
kaldı; ikinci çalıştırma iş yapmaz. İlk açılışta veri kalitesi bir kez hesaplanır (~2,5 sn).

| Nerede | Ne |
|---|---|
| `bina` (+6 sütun) | `kalite` (JSON bayraklar) · `kalite_kaynak` (JSON kanıt, ham değerler) · `pasif` (0/1) · `pasif_tarih` · `tur_tarihi` · `ekleme_kaynagi` (`NULL` ilk kurulum, `'tur'` sonradan gelen) |
| `bolge_plani` | Plan geçmişi: `n, olcu, kaynak ('baslangic' / 'hazir' / 'onbellek' / 'hesap'), plan_ref, imza, atama (JSON serial→bölge), bolgeler (JSON), kullanicilar (uygulama öncesi satışçı bölgeleri), ozet, olusturan_id, zaman, aktif, geri_alindi, onceki_id, notu` |
| `tur_raporu` | Yüklenen raporlar: `dosya, ozet_imza (sha256), yukleme, yukleyen_id, durum ('onizleme' / 'uygulandi' / 'eskidi'), ozet (JSON fark), uygulama, uygulayan_id` |
| `bina_bekleyen` | Raporda olup haritada olmayan bina: `bina_serial, tellcordia_id, location_id, veri (JSON satır), durum ('konum_bekliyor' / 'eklendi' / 'rapordan_cikti'), tur_id, eklenme, guncelleme` |
| `bina_degisim` | Künye değişikliğinin izi: `bina_serial, kaynak ('tur:<id>' / 'onemap'), alan, eski, yeni, zaman` |
| `bina_geometri_ek` | Sonradan eklenen binaların taban poligonu (`halka` JSON) |
| `ticket`, `ticket_gecmis` | §7.4 |
| `ayar` | `bina_surumu` (künye sürümü; harita/geometri önbelleği buna bakar) · `altlik` (JSON) · `tur_raporu_son` · `bolge_adlari` (plan uygulanınca güncellenir) |

**Bölge 0 = "bölgesiz".** Bölgesi kalmayan satışçının `kullanici.bolge` değeri `0`
olur: hiçbir binaya dokunamaz, listesi boş gelir, rota kuramaz. (`NULL` olsaydı
satışçı ekranları bütün şehri gösterirdi.) Yönetici Ekip ekranından yeni bölge verir.

**Pasif bina.** Son tur raporunda olmayan bina silinmez, `pasif=1` olur: rota adayı
olmaz, elle atanamaz (`400 bina_pasif`), kapsama / `/api/ben` toplamlarına ve
`/api/harita` dizilerine girmez; `/api/bina/{serial}` ile geçmişi görülür
(`bina.pasif: true`). Rapora geri dönerse kendiliğinden etkinleşir.

### 7.1 Veri kalitesi (GEREKSINIMLER B1)

Kurallar `dsale/kalite.py`de, her biri sade Türkçe bir mesajla. Düzeltme yalnız
GÜVENLİ olduğunda yapılır (sonuç kesin, ya da değer yalnız görüntüyü etkiliyor);
**RES HP ve aboneye asla dokunulmaz.** Orijinal değer bayrağın `duzeltme.eski`
alanında ve `kalite_kaynak.ham` içinde kalır. Bugünkü sayılar (19.706 bina):

| Kural (`kural`) | Seviye | Düzeltir mi | Adet | Ne yapılır |
|---|---|---|---|---|
| `location_sifir` | uyari | evet | 2.335 | Excel `00113680`'i `113680` yapmış; OneMap ENTEGRASYON_ID birebir aynıysa 8 haneye tamamlanır (BOSS/ticket bu hâli kullanır) |
| `location_uyusmaz` | uyari | hayır | 0 | Raporla OneMap'in Location Id'si farklı |
| `tellcordia_bozuk` | uyari | evet | 2 | `1,61623150353E+011` → `161623150353` (bütün basamaklar duruyor + OneMap aynı) |
| `abone_hp_asiyor` | uyari | hayır | 181 | Aktif abone > RES HP > 0; fırsat 0 sayılır |
| `hp_sifir_abone_var` | uyari | hayır | 122 | RES HP 0 ama abone var (181 + 122 = "aktif > HP" olan 303 bina) |
| `hp_sifir` | bilgi | hayır | 44 | RES HP 0, abone yok |
| `kat_tahmini` | bilgi | hayır | 9.835 | Kat OneMap'te yok, daireden tahmin (`enrich._kat_tahmini`) |
| `kat_daire_celiski` | uyari | evet | 91 | 1-2 katta kat başına >12 daire ya da daire sayısının iki katından fazla kat (≥8) → tahmini kat (yalnız 3B yüksekliği etkiler) |
| `kat_basina_cok_daire` | bilgi | hayır | 3 | Kat başına >20 daire |
| `daire_bilinmiyor` | bilgi | hayır | 7 | OneMap'te daire sayısı yok |
| `tekrar_satir` | uyari | hayır | 1 | Aynı Bina Serial raporda iki kez; büyük Toplam HP'li satır alındı |
| `konum_sapmasi` | uyari | hayır | 2 | OneMap LAT/LON ile poligon merkezi 100 m'den uzak |
| `ilce_uyusmazligi` | uyari | hayır | 1 | CRM ilçesi ≠ OneMap ilçesi |
| `bos_ad` | bilgi | 'Null' ise | 1.403 (7 düzeltme) | Ad boş ya da 'Null' yazıyor; kart site adına düşer. CRM site adındaki "Null " öneki de atılır |

Bir binanın HP'si/abonesi değişince (tur raporu) o binanın bayrakları yeniden
hesaplanır. Aynı binayı iki kez denetlemek aynı sonucu verir. Kanıtlar
`data/master/bina_kalite_kanit.json`'da önbelleklenir (kaynak dosyalar değişince yenilenir).

- `GET /api/kalite/ozet?bolge=` (yönetici) → `{toplam_bina, bayrakli_bina, hesaplanmamis, kural_surumu, kurallar:[{kural, ad, seviye, aciklama, duzeltir, adet, duzeltilen}]}`
- `GET /api/kalite/liste?kural=&bolge=&seviye=bilgi|uyari&limit=50&offset=0` (yönetici, limit ≤ 500) → `{toplam, limit, offset, binalar:[{bina_serial, baslik, ad, site_adi, sokak, kapi_no, mahalle, ilce, bolge, lat, lon, location_id, tellcordia_id, res_hp, aktif_res, kat, daire, kalite:[…]}]}` · bilinmeyen kural `400 kural_gecersiz`
- `POST /api/kalite/yenile` (yönetici) → kanıtları tazeleyip bütün binaları yeniden denetler: `{bina, bayrakli, duzeltilen, yazilan, alan_degisikligi, mesaj}`
- **Bina kartı** (`_bina_kart`, her listede): `kalite: [{kural, mesaj, seviye, duzeltme?:{alan, eski, yeni}}]` ve `pasif: bool`.
- `GET /api/bina/{serial}` ayrıca `ticketlar: [Ticket]` döner (§7.4).
- Kart başlığı artık `'Null'` yazısını boş sayar (7 binada "Null" başlık çıkıyordu).

### 7.2 Bölge planlayıcı (B3, B5) — hepsi yönetici

- `GET /api/bolgeleme/durum` → `{n, olcu, plan:{id, n, kaynak, zaman, notu} | null, geri_alinabilir, bolgeler:[{bolge, ad, kisa_ad, renk, bina, res_hp, aktif_res, toplam_hp, firsat, kalan_firsat, dokunulan, dokunulan_oran, satis, ziyaret, penetrasyon, sapma, poligon, satiscilar:[{id, ad, telefon_goster, aktif, pin_var}]}], toplam:{bina, res_hp, firsat, kalan_firsat, dokunulan, satis, dokunulan_oran}, bolgesiz_satiscilar, bolgesiz_bina, hazir_nler:[2..30, 35, 40, 45, 50], en_az_n:2, en_cok_n:60, calisan_is, gecmis:[{id, n, olcu, kaynak, zaman, aktif, geri_alindi, onceki_id, notu, olusturan}]}`
- `GET /api/bolgeleme/onizleme?n=14&olcu=res_hp|firsat|toplam_hp|bina&hesapla=0|1&kaynak=hazir|onbellek|hesap`
  - Plan bulunursa **200**: `{hazir:true, n, olcu, plan_ref, kaynak, kaynak_ad, parametreler, mevcut_n, bolgeler:[{bolge, ad, kisa_ad, renk, bina, res_hp, aktif_res, toplam_hp, firsat, kalan_firsat, dokunulan, dokunulan_oran, satis, ziyaret, penetrasyon, sapma, poligon (GeoJSON MultiPolygon), merkez, etiket, satiscilar, yeni_satisci_acilacak, nereden:[{bolge (eski), bina}]}], denge:{sapma_min, sapma_maks}, fark:{aktif_bina, el_degistiren_bina, el_degistiren_oran, el_degistiren_ziyaret, el_degistiren_dokunulmus_bina, numarasi_degisen_bina, bugun_listede_el_degistiren, satisci_hareketleri, bolgesiz_kalacak_satiscilar, yeni_satisci_acilacak_bolgeler, kalkan_bolgeler}, uyarilar:[metin], bina_bolge:[int]}`
  - `bina_bolge`: `/api/harita` (bölgesiz istek) ile AYNI seri sırasında (pasif olmayan binalar, `bina_serial` artan) yeni bölge numaraları → önizleme haritası bunu boyar.
  - Plan yoksa (ya da `hesapla=1`) **202**: `{hazir:false, n, olcu, is:{is_id, n, olcu, durum, ilerleme (0..1; bölgeleme aşamasında süreye göre TAHMİNİ), asama, tahmini_sn, baslangic, bitis, mesaj}, mesaj}`. Aynı anda tek hesap; başka N hesaplanıyorsa `409 hesap_suruyor`.
  - Kaynak sırası: bu veriyle sunucuda hesaplanmış plan (`outputs/_onbellek/saha/<veri imzası>/plan_NXX_<ölçü>.json`) → sunum paketi `app/src/data/generated/planlar.json` (yalnız `res_hp`; veritabanının en az %97'sini birebir tanımıyorsa kullanılmaz) → `bolge.py` önbelleği (yalnız bugünkü master ile üretilmişse). Planda olmayan bina en yakın binanın bölgesine verilir.
  - Geçersiz `n` → 422, geçersiz ölçü → `400 olcu_gecersiz`.
- `GET /api/bolgeleme/is/{is_id}` → iş durumu (`durum`: `bekliyor` · `calisiyor` · `bitti` · `hata`). Bitince `onizleme?n=` aynı N için `kaynak:'hesap'` döner. Sunucu yeniden başlarsa iş kaydı kaybolur (`404 is_yok`), hesaplanmış dosya kalır.
- `POST /api/bolgeleme/uygula {n, plan_ref, pasiflestir?:false, notu?}` → `{plan_id, n, onceki_plan_id, degisen_bina, el_degistiren_bina, el_degistiren_ziyaret, tasinan_satiscilar, bolgesiz_kalan, pasife_alinan, yeni_satiscilar:[{id, ad, bolge, telefon, telefon_goster, davet_kodu}], mesaj}`
  - TEK İŞLEM: ilk kullanımda bugünkü durum `baslangic` planı olarak kaydedilir; `bina.bolge` güncellenir (pasif binalar dahil); satışçılar eşleşen bölgeye taşınır; satışçısı olmayan bölgeye yer tutucu hesap + 6 haneli davet kodu açılır (telefon `50000000NN`, yönetici düzenler); `bolge_adlari` ve künye sürümü güncellenir. Hata olursa hiçbir şey yazılmaz.
  - **Ziyaret, görev ve `bina_durum` tablolarına dokunulmaz.** Bugünkü listeler olduğu gibi kalır.
  - Numaralandırma: yeni bölgeler, binalarının (ziyaret edilmişler ağır) çoğunu devraldıkları eski bölgeyle Macar yöntemiyle eşleşir. 8→14: 1-8 numarası ve satışçısı korunur, 9-14 yeni. 14→8: numaralar 1-8'e sıkışır; bölgesi kalmayan satışçı `bolge=0` (bölgesiz, hesap açık) olur, `pasiflestir:true` ise ayrıca `aktif=0` ve oturumları düşer. Hesap SİLİNMEZ.
  - `plan_ref` = `kaynak:n:olcu:imza`; önizlemeden sonra binalar değiştiyse `409 plan_degisti`, plan bulunamazsa `409 plan_yok`, `n` uyuşmazsa `400 plan_ref_gecersiz`.
- `POST /api/bolgeleme/geri-al` → önceki plana (`onceki_id`) döner: bina bölgeleri ve satışçıların bölge/aktiflik durumu uygulama öncesine; o plan için açılan yer tutucular `aktif=0` (silinmez). → `{plan_id, geri_alinan_plan_id, n, degisen_bina, kapatilan_yer_tutucular:[{id, ad, pin_belirlemisti}], mesaj}` · geri alınacak yoksa `409 geri_alinacak_yok`. Arka arkaya geri almak plan zincirinde geriye yürür (başlangıçta durur).
- `GET /api/bolgeleme/excel?plan_id=` → etkin (ya da verilen) planın açıklayıcı Excel'i `Bursa_{N}_Satisci_Bolgeleme.xlsx` (`dsale.excel_report`, güncel HP ile; PERSONEL_ATAMA satışçı adlarıyla dolu). İlk üretim ~15-30 sn, sonra önbellekten (`outputs/saha_bolgeleme/`); plan, künye sürümü ya da satışçı adları değişince yeniden üretilir.
- `GET /api/saglik` → `bolge_sayisi` (etkin N). `POST /api/kullanici` satışçı bölgesini `1..bolge_sayisi` aralığında kabul eder (14 bölgede 14).
- **Gün içinde plan değişirse:** satışçının son 14 gündeki listelerinde olan bina, bölgesi değişse de ona açıktır (`POST /api/ziyaret`, `/api/ziyaret/toplu`, `GET /api/bina/{serial}`, ticket şablonu) — çevrimdışı kuyruk "başka bölge" diye takılmaz. Listede olmayan başka bölge binası hâlâ `403 baska_bolge`.
- `python -m saha.kur` yeniden çalışırsa: plan geçmişi varsa bölgelere, `tur_tarihi` dolu binaların HP/abone/fırsatına DOKUNMAZ.

### 7.3 Tur raporu ve OneMap yenileme (B2) — hepsi yönetici

- `POST /api/veri/tur-raporu` — gövde: `multipart/form-data` (`dosya` alanı) ya da ham `.xlsx` (`application/octet-stream`, isteğe bağlı `X-Dosya-Adi` başlığı). En çok 80 MB. Dosya `data/raw/gelen/tur_<YYYYAAGG_SSDDss>.xlsx` olarak saklanır, **ORIGN** sayfası (yoksa ilk sayfa) okunur, farkı döner, **bina tablosuna hiçbir şey yazmaz** → `{tur_id, dosya, dosya_adi, okuma:{sayfa, satir, tekil_bina, bos_serial, tekrar, tekrar_ornek, bozuk_tellcordia}, fark:{once:{bina, res_hp, aktif_res, firsat, toplam_hp}, sonra:{…}, sonra_haric_yeni, yeni_bina, yeni_bina_il_disi, il_disi_dagilim, cikan_bina, cikan_oran, pasif_onay_gerekli, geri_donen_bina, degisen_bina, degismeyen_bina, ornek:{yeni, cikan, degisen:[{bina_serial, ad, bolge, ilce, degisim:{alan:[eski, yeni]}, firsat_fark}], geri_donen}, hizmet_illeri, uyarilar}, ayni_dosya_daha_once}` · xlsx değilse `400 dosya_gecersiz`, zorunlu sütun yoksa `400 sutun_eksik` (okunamayan dosya saklanmaz), 80 MB üstü `413 dosya_buyuk`.
- `GET /api/veri/tur-raporu` → `{raporlar:[{tur_id, dosya, yukleme, durum, uygulama, yukleyen, yeni_bina, cikan_bina, degisen_bina}], son_uygulanan}` · `GET /api/veri/tur-raporu/{tur_id}` → kayıtlı önizleme.
- `POST /api/veri/tur-raporu/uygula {tur_id, pasif_onay?:false, iller?:[..]}` → TEK İŞLEM: var olan binalarda `res_hp, aktif_res, firsat, toplam_hp, soho_hp, tur_tarihi` güncellenir (her değişiklik `bina_degisim`'e), raporda olmayan bina pasif, geri dönen etkin, yeni bina `bina_bekleyen`'e (yalnız hizmet verilen illerden; `iller` ile genişletilir), kalite yeniden hesaplanır. **Bölgeler ve `site_grup` değişmez.** → `{tur_id, zaten_uygulandi, guncellenen_bina, pasife_alinan_bina, geri_donen_bina, konum_bekleyen_bina, once, sonra, mesaj}`
  - İkinci kez: `200 {zaten_uygulandi:true}` (hiçbir şey iki kez yazılmaz).
  - Bugünkü binaların %10'undan fazlası raporda yoksa (kısmi rapor: tek ilçe, yarım dosya) `pasif_onay:true` olmadan `409 pasif_onay_gerekli`.
  - Daha yeni bir rapor uygulanmışsa eskisi `409 daha_yeni_var`; uygulanan raporun öncesindeki önizlemeler `eskidi` olur.
- `GET /api/veri/bekleyen?durum=konum_bekliyor|eklendi|rapordan_cikti` → `{durum, toplam, binalar:[{bina_serial, tellcordia_id, location_id, ad, site_adi, ilce, il, res_hp, firsat, durum, tur_id, eklenme}]}`
- `GET /api/veri/bekleyen.txt` → OneMap aracına verilecek `bekleyen_idler.txt` (satır başına Tellcordia ID = OneMap `ID`; yoksa Bina Serial = `LOCATION_ID`).
- `GET /api/veri/onemap-araci.js` → `saha/araclar/onemap_cek.js` (tarayıcı konsoluna yapıştırılır; kullanım `SAHA_KULLANIM.md` §12).
- `POST /api/veri/onemap` — gövde: aracın indirdiği `onemap_yeni.json` (multipart `dosya` ya da ham JSON). Hem araç biçimi `{features:[{a, g}]}` hem ham ArcGIS `{features:[{attributes, geometry:{rings}}]}` kabul edilir. Eşleşen bekleyen bina poligon merkeziyle (poligon yoksa LAT/LON) `bina`ya eklenir: mahalle `enrich.mahalle_norm`, kat OneMap (1-60) ya da daireden tahmin, `site_grup` aynı ilçe + mahalle + site adındaki 350 m içindeki VAR OLAN gruba katılır (yoksa yeni anahtar; var olanlar asla değişmez), bölge = aynı site grubunun bölgesi, yoksa en yakın etkin binanın bölgesi; `bina_durum='bekliyor'`, poligon `bina_geometri_ek`'e, dosya `data/raw/gelen/onemap_<zaman>.json`'a. → `{eklenen, eslesmeyen, zaten_haritada, konumsuz, hala_bekleyen, binalar:[{bina_serial, ad, bolge, lat, lon, site_grup}], mesaj}` · boş dosya `400 onemap_bos`, JSON değilse `400 dosya_gecersiz`. Aynı dosya iki kez: `eklenen:0`.
- `GET /api/bina/{serial}/degisim` (yönetici) → `{bina_serial, degisimler:[{kaynak, alan, eski, yeni, zaman}]}` (en yenisi önce, 200 satır).
- Komut satırı (arayüz hazır olmasa da): `python -m saha.veri_araci tur | bekleyen | onemap | bolge | excel | kalite` (aynı işlevler).

### 7.4 Ticket defteri (C11)

`ticket`: `id, ticket_no (OneDesk; açılana kadar boş), acilis (YYYY-AA-GG), konu, durum, bina_serial, location_id, site, musteri (serbest metin), kanal (DEHA / GLOBAL / ARIZA / TOPTAN …, büyük harf), detay, metin, olusturan_id, olusturma, guncelleme, kapanis, kaynak ('uygulama' / 'excel'), aktarim_anahtari`.
`ticket_gecmis`: `ticket_id, zaman, kullanici_id, eski_durum, yeni_durum, notu, alanlar (JSON {alan:[eski, yeni]})`. Kayıt silinmez; iptal bir durumdur.

- Konu: `SİNYAL · EK SP · GÜZERGAH · ALTYAPI · DİĞER` (girişte "sinyal", "EKSP", "ek kapasite" gibi yazımlar tanınır). Durum: `AÇIK · ÇÖZÜLDÜ · HATA · KAPATILDI · İPTAL · TRANSFER`; **açık sayılan**: AÇIK, HATA, TRANSFER. Kapalı duruma geçince `kapanis` dolar, yeniden açılınca boşalır.
- **Ticket metni** `saha/ticket.py → ticket_metni()` ile `saha_app/src/ortak/kimlik.ts → ticketMetni()` BİREBİR aynı (sekme ayrımlı: giriş cümlesi · Bina Serial Number · BN · Tellcordia ID · … · Location Id · … · Obek Adı · Site Adı · `Ekip: <tel>`; Site Adı = CRM site adı, yoksa bina adı). SİNYAL metni kullanıcının gerçek ticket'ıyla karakter karakter test edilir; diğer konular `sablon_taslak:true` (örnek metin bekleniyor). Birinde değişiklik yapan diğerini de değiştirmeli.
- `GET /api/ticket?durum=&konu=&kanal=&q=&bina_serial=&acik=true|false&bolge=&limit=100&offset=0` (yönetici, limit ≤ 500) → `{toplam, limit, offset, sayilar:{DURUM:n}, acik_toplam, acik_konu:{KONU:n}, ticketlar:[Ticket]}`; açıklar önce, sonra açılış tarihi yeni→eski. `q`: ticket no, Location Id, site, müşteri, detay, BN, bina adı.
- `Ticket` = `{id, ticket_no, acilis, konu, konu_etiket, durum, acik, acik_gun, bina_serial, location_id, site, musteri, kanal, detay, metin, olusturan, olusturma, guncelleme, kapanis, kaynak, bina:{bina_serial, ad, bolge, ilce, mahalle, lat, lon} | null}`
- `POST /api/ticket {konu, bina_serial?, location_id?, ticket_no?, acilis?, durum?='AÇIK', musteri?, kanal?, detay?, site?, ekip?, metin?, notu?}` (yönetici) → **201** `{ticket, sablon_taslak, mesaj}`. Binadan açılınca Location Id, site ve metin binadan dolar; yalnız `location_id` verilirse bina Location Id'den bulunur (birebir · 8 haneye sıfırlı · baştaki sıfırsız · sondaki "-1" eki atılmış). Geçersiz konu/durum `400 gecersiz_veri`, olmayan bina `404 bina_yok`.
- `GET /api/ticket/{id}` (yönetici) → `{ticket, gecmis:[{id, zaman, eski_durum, yeni_durum, notu, alanlar, kullanici}]}`
- `PATCH /api/ticket/{id} {durum?, ticket_no?, acilis?, konu?, musteri?, kanal?, detay?, site?, location_id?, notu?}` (yönetici) → `{degisti, alanlar, ticket, gecmis}`; değişiklik ya da not varsa bir geçmiş satırı yazar, yoksa `degisti:false`.
- `GET /api/ticket/sablon?bina_serial=&konu=SİNYAL&ekip=` (giriş yapmış herkes; satışçı yalnız kendi bölgesi/listesi) → `{bina_serial, konu, metin, sablon_taslak, alanlar:{bina_serial, tellcordia_id, location_id, obek, site_adi}}` — ticket açmadan kopyalanacak metin.
- `GET /api/bina/{serial}/ticket` (satışçı kendi bölgesinde) → `{bina_serial, acik, ticketlar}`
- `GET /api/ticket/harita` (yönetici) → `{serial:[], acik:[]}` açık ticket'ı olan binalar (3B/harita boyaması).
- **Excel'den aktarım**: `python -m saha.ticket_aktar [--dosya ../PS26/data.xlsx] [--sayfa TICKET] [--db …] [--kuru]`. Anahtar yalnız değişmeyen alanlardan (başlangıç + lokasyon + konu; lokasyonsuz satırda müşteri + site); tekrar çalışınca yeni satırı ekler, Excel'de numarası/durumu/detayı değişmiş ve uygulamada elle değiştirilmemiş ticket'ı günceller ("Excel'den güncellendi"), uygulamada değiştirilmişe dokunmaz. 2026-09-29 18:25'teki dosyada 198 satır, 197'si binaya bağlandı (1 satırda lokasyon yok). **Canlı veritabanına henüz aktarılmadı** (bkz. `SAHA_KULLANIM.md` §14).

### 7.5 3B dijital ikiz geometrisi (A9)

`GET /api/binalar/geometri?bolge=` (giriş yapmış herkes; satışçı kendi bölgesi) →
`{surum:1, adet, bolge, serial[], lat[], lon[], kat[], ofs[], fark[], olcek:1e-6, kat_yuksekligi_m:3, poligonsuz}`.
Biçim `dsale/bundle.py → binalar()` ile aynı: i. binanın noktaları `k = ofs[i] … ofs[i+1]-1`,
`lon = lon[i] + fark[2k]·olcek`, `lat = lat[i] + fark[2k+1]·olcek`. Poligonsuz binada
`ofs[i] == ofs[i+1]`. Pasif binalar yok. `kat` kalite düzeltmesinden geçmiş değerdir
(yükseklik = kat × 3 m). Veri renkleri için `/api/harita` (durum, fırsat) ve
`/api/ticket/harita` (açık ticket) aynı `serial` ile birleştirilir.
Yanıt bellekte hazır tutulur (künye sürümü değişince yenilenir), `Accept-Encoding: gzip`
ise önceden sıkıştırılmış gönderilir, `ETag` + `If-None-Match` → `304`.

### 7.6 Harita altlığı (A8)

- `GET /api/ayar/altlik` (giriş yapmış herkes) → `{sokak_url, uydu_url, sokak_atif, uydu_atif, atif, sokak_en_fazla_zoom, uydu_en_fazla_zoom, varsayilan, lisans_notu, referrer_policy}`
  - Varsayılan sokak: `https://tile.openstreetmap.org/{z}/{x}/{y}.png` (atıf "© OpenStreetMap katkıcıları") · uydu: `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` (atıf "Uydu: Esri, Maxar, Earthstar Geographics ve GIS Kullanıcı Topluluğu"). Esri adresinde sıra `{z}/{y}/{x}`'tir. `atif` iki katmanın atfını tek satırda verir.
- `PUT /api/ayar/altlik {sokak_url?, uydu_url?, sokak_atif?, uydu_atif?, atif?, sokak_en_fazla_zoom?, uydu_en_fazla_zoom?, varsayilana_don?}` (yönetici). Adres `https://` olmalı (http yalnız ofis içi / özel IP), `{z} {x} {y}` (ya da `{-y}`) içermeli, ek olarak yalnız `{s}` kabul edilir; atıf boş olamaz. Geçersizse `400 altlik_gecersiz`. Turkcell'in kendi altlığı ya da lisanslı bir sağlayıcı buradan bağlanır.
- **CSP**: `img-src` ve `connect-src` artık `'self'` + yalnız bu iki karo sunucusunun kökenini içerir (`{s}` → `*.alan`); ayar değişince sunucu yeniden başlatılmadan güncellenir. Başka hiçbir dış kaynak açılmadı.
- **Referrer-Policy** `no-referrer` → `strict-origin-when-cross-origin`: OSM karo politikası Referer ister; yalnız köken (`http://<ofis-ip>:8080`) gider, yol/sorgu/ekran asla gitmez.
- **Lisans uyarısı:** OSM'nin karo sunucuları yalnız hafif kullanım içindir (çevrimdışı önbellek için toplu indirme YASAK), atıf her zaman görünmeli. Esri World Imagery'nin ticari kullanımı ArcGIS lisansı ister; kurumsal lisans yoksa uydu yalnız değerlendirme amaçlıdır. Kalıcı çözüm: MapTiler / Mapbox / HERE gibi lisanslı sağlayıcı ya da Turkcell altlığı (yalnız adres değişir). Karo isteği tarayıcıdan sağlayıcıya gider: sağlayıcı ofis IP'sini ve bakılan bölgeyi görür; **bina/müşteri verisi gitmez.**

### 7.7 Değişen mevcut davranışlar (arayüz için kontrol listesi)

1. `bina.bolge` / `kullanici.bolge` 1..8 ile sınırlı değil: `/api/saglik.bolge_sayisi` kadar; satışçıda `0` = bölgesiz.
2. `/api/harita`, `/api/ozet/kapsama`, `/api/ben` (bölge kartı) pasif binaları saymaz; harita önbelleği künye sürümüyle tazelenir (plan/tur sonrası yeniden başlatma gerekmez).
3. Bina kartı: `kalite[]`, `pasif`; detay yanıtı: `ticketlar[]`. Kimliklerde düzeltilmiş değerler (8 haneli Location Id, düzeltilmiş Tellcordia ID).
4. Ziyaret ve bina detayı: satışçının son 14 gündeki listesinde olan bina, bölgesi değişse de açık.
5. Güvenlik başlıkları: CSP'de karo sunucuları; Referrer-Policy `strict-origin-when-cross-origin`.
6. Sunucu için ek paketler: `pandas, numpy, scipy, shapely, python-multipart` (`saha/gereksinimler.txt`; `baslat.bat` eksikse kurar).
