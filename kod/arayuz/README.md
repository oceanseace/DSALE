# Turkcell — arayüz (PWA)

8 satışçının telefonunda çalışan uygulama. Algoritmanın hazırladığı günlük bina
listesini gösterir, yol tarifi verir, ziyaret sonucunu kaydeder; bağlantı
gitse bile hiçbir kayıt kaybolmaz.

Sözleşme: [`belgeler/SAHA_SOZLESME.md`](../../belgeler/SAHA_SOZLESME.md) — veri modeli,
uçlar ve ekranlar orada tanımlı. Bu klasör onun arayüz tarafıdır.

## Çalıştırma

```bash
npm install
npm run dev        # http://127.0.0.1:5180  (/api → 127.0.0.1:8090'a vekil: kod/saha/GELISTIRME_BASLAT.bat)
npm run build      # tsc + vite  →  dist/
npm run onizle     # derlenmiş hali 127.0.0.1:4173'te aç
npm run sinir      # birim sınırı denetimi (build bunu kendisi çalıştırır)
npm run tasi -- <eski> <yeni>   # dosya taşı, içe aktarmaları düzelt (yollar src'ye göre)
npm run ikon       # PWA simgelerini yeniden üret (Python + Pillow)
npm run build:sahte  # DEMO derlemesi (örnek veri içerir) → dist-sahte/
```

`dist/` klasörü FastAPI tarafından statik olarak sunulur (sözleşme §5).

### Sunucu yokken: örnek veri kipi

**Örnek (sahte) veri normal derlemeye GİRMEZ.** `npm run build` ile alınan
pakette `sahte.ts` yoktur; uygulama yalnız gerçek API ile konuşur — saha ekibi
uydurma bir listeyi gerçek sanamaz.

Örnek veri iki yerde açıktır: `npm run dev` (geliştirme) ve `npm run build:sahte`
(gösterim derlemesi, `dist-sahte/`). Bu iki kipte adrese `?sahte=1` eklenir;
tercih tarayıcıda saklanır, `?sahte=0` ile kapanır.

| Adres | Ne gösterir |
|---|---|
| `?sahte=1` | Normal gün: 25 binalık liste, 7'si bitmiş |
| `?sahte=1&durum=bitti` | "Liste bitti 🎉" ekranı |
| `?sahte=1&durum=bos` | "Bugün için liste yok" ekranı |

Örnek giriş: telefon `5321234567`, PIN `1234`. `5550000000` ilk giriş (PIN
belirleme) akışını açar. Örnek veri gerçek `cikti/N08_res_hp/atama.csv`
dosyasından üretilmiştir (bölge 3 · Nilüfer 23 Nisan – Ataevler);
`scripts/ornek_veri.py` ile yenilenir. Bu modül ayrı bir parçadır, üretimde
indirilmez.

## Sunucudan beklenenler

Sözleşme §3'teki uçlar aynen kullanılır. İkisi sözleşmede yok, ikisi de
**isteğe bağlı** — sunucu vermezse uygulama sessizce o özelliği gizler:

| Uç | Durum | Yoksa ne olur |
|---|---|---|
| `GET /api/yollar?bolge=` | Eklenti. `veri/ref/osm_yollar.geojson` kesiti (GeoJSON `FeatureCollection`, LineString/MultiLineString). | Harita yolsuz çizilir. |
| `GET /api/ben` içinde `hafta` ve `bolge` blokları | Eklenti. `hafta:{ziyaret,satis,randevu}` · `bolge:{toplam,dokunulan,kalan,kalan_firsat?}` | "Ben" ekranında o kartlar gösterilmez. |
| `POST /api/ziyaret` gövdesinde `tekrar_tarih` | Eklenti. Randevu seçilince `YYYY-AA-GG`. | Alan yok sayılabilir. |
| `GET /api/harita` içinde `ad[]` dizisi | Eklenti. Haritada binaya dokununca başlık. | Başlık yerine bina seri no görünür. |

Diğer beklentiler:

- `GET /api/gorev/bugun` bugün görev yoksa **404** döner (uygulama bunu boş gün
  sayar, hata göstermez).
- `POST /api/ziyaret` ve `/api/ziyaret/toplu` **idempotent** olmalı: aynı
  `offline_id` ikinci kez gelirse yeni kayıt açılmamalı. Kuyruk yeniden
  gönderebilir.
- `401` → uygulama jetonu atar ve giriş ekranına döner.
- Hata gövdesi `{hata, kod}`; `hata` alanı kullanıcıya olduğu gibi gösterilir,
  bu yüzden Türkçe ve anlaşılır olmalı.

## Çevrimdışı davranış

Bu uygulamanın tek sözü var: **kaydettiğin hiçbir şey kaybolmaz.**

1. "Kaydet"e basıldığında kayıt **önce** telefona (IndexedDB `kuyruk`) yazılır,
   **sonra** sunucuya gönderilir. Sıra hiçbir zaman ters değildir.
2. Liste beklemeden güncellenir; bina "bitti" olur ve listeden düşer.
3. Ekranda "3 kayıt bekliyor" şeridi ve sekmede sayı rozeti görünür.
4. Gönderim; bağlantı gelince, uygulamaya dönülünce ve artan aralıklarla
   (15 sn → 5 dk) kendiliğinden tekrar denenir.
5. Liste sunucudan tazelendiğinde kuyrukta bekleyen binalar yine "bitti"
   kalır (`cekirdek/yerel/bugun.tsx` → `bekleyenleriUygula`). Aksi hâlde satışçı işlediği
   bina yeniden listeye düşünce uygulamaya güvenmez.
6. Uygulama kabuğu ve son liste servis çalışanında önbellektedir; sinyal yokken
   yeniden açılsa bile aynı şekilde çalışır.
7. Kuyrukta kayıt varken çıkış yapılamaz.

> "Ana ekrana ekle" ve çevrimdışı çalışma yalnız HTTPS'te (veya
> `http://localhost`) devreye girer. Ofis ağında düz HTTP ile her şey çalışır,
> çevrimdışı hariç.

## Klasörler — birimler

Kod, organizasyon şemasındaki birimlere bölünmüştür. Bir değişiklik tek birime dokunur.

| Yol | Birim · içerik |
|---|---|
| `src/birimler/operasyon/` | **Operasyon.** `isler/` **TASKS** (Excel gibi tek tablo: `Isler.tsx` ekran, `Tablo.tsx` ızgara, `Baslik`/`SuzgecMenusu`/`SagTikMenusu`/`SutunSecici`/`DurumCubugu`; `secim`, `klavye`, `pano`, `panoSuzgeci`, `sutunlar`, `sutunDuzeni`, `tabloSuzgec` mantık; adres sözleşmesi `cekirdek/yol/tasks.ts`) · `isler/map/` **MAP** (`IsHaritasiEkrani.tsx` ekran; `MapTuval`, `KonumAra`, `SecimKarti`, `konumArama`, `tarihSuzgeci`, `noktalar`, `noktaGecisi`) · İş çekmecesi, Görünümler, BOSS bağlantısı · `obekler/` (menüde yok) |
| `src/birimler/saha/` | **Saha.** `ekran/` satışçının telefonu (Bugün · Bina · Harita · Ben) · `yonetim/` Canlı · Kapsama · Görev atama · Rapor · Tur raporu · `bolge/` Bölge planlayıcı |
| `src/birimler/altyapi/` | **Altyapı.** `ticket/` Ticketlar (Excel TICKET sayfası gibi tablo; hücreden durum ve ticket no) · `tablolar/` (PS26 yerine) |
| `src/birimler/teknik/` | **Teknik.** teknisyenin İşlerim'i (`Islerim`, `IsEkrani`, çevrimdışı `kuyruk`) |
| `src/birimler/depo/` | **Depo.** Seri takibi |
| `src/birimler/administrator/` | **Administrator.** `takip/` Pano (gösterge paneli) · `ekip/` kişiler ve görevler · `unvan/` · Veri kalitesi |
| `src/cekirdek/` | Ortak çekirdek: `api/` sunucu sözleşmesi · `yerel/` IndexedDB, oturum, senkron · `konsol/` kabuk ve menü (`menu.ts`) · `ortak/` arayüz parçaları · `harita/` · `is/` iş modeli · `ticket/` ticket açma · `giris/` · `yol/` · `stil/` |
| `src/App.tsx` · `src/Konsol.tsx` | Birimleri birbirine bağlayan tek iki yer (adresler, menü bölümleri) |
| `src/sw.js` | Servis çalışanı şablonu; dosya adları derlemede gömülür |

**Sınır kuralı:** `cekirdek/` hiçbir birimi içe aktarmaz; bir birim başka birimi içe aktarmaz.
`npm run build` önce `npm run sinir` ile bunu denetler. İki birimin ortak kullandığı parça
çekirdeğe taşınır: `npm run tasi -- <eski> <yeni>` (içe aktarmaları kendisi düzeltir).

## Tasarım sistemi (masaüstü konsolu + telefon)

Tek kaynak: `src/cekirdek/stil/tokenlar.css` (Fluent 2 temelli). İlkeller:
`src/cekirdek/ortak/Ilkel.tsx` + `ilkel.css` (Dugme, SimgeDugme, Girdi, Secici, Alan,
AramaKutusu, Sekmeler, AracCubugu, DurumCubugu/DurumIcerigi); pencere `Onay.tsx`,
çekmece `Panel.tsx`, ⋯ menü `Menu.tsx`, tablo `Tablo.tsx`.

- Renk: nötr griler + tek vurgu lacivert (`--vurgu`). Sarı (`--birincil`) yalnız ekranın
  TEK ana eylemi ve marka. Yeşil/kırmızı/amber yalnız durum. Ekran CSS'inde renk kodu yok.
- Boşluk 4'ün katları (`--b1…--b8`); tek yazı ailesi, 4 boy (`--boy-k/o/b/bb` = 12/14/16/20),
  kalınlık 400/600. Bölgeler zemin farkıyla ayrılır; gölge yalnız menü/pencerede.
- Hareket ≤ 150 ms ease-out; ışıma, degrade, nabız, zıplama yok.
- İskelet: üst çubuk (başlık solda, eylemler sağda) · iş alanı · durum çubuğu
  (`YonUst altYazi` ve `DurumIcerigi` oraya yazar). Başlığın altına açıklama yazılmaz.
- Simgeler: ✕ kapat, ← geri, büyüteç ara, çöp sil, kalem düzenle, ⋯ daha.
- Örnek veriyle yönetim konsolu: `npm run dev` → `?sahte=1&rol=admin`.

## Telefon (saha) kuralları

Kullanıcı kışın eldivenle, güneş altında, tek eliyle çalışıyor. Bu yüzden:

- Dokunma hedefleri **en az 56 px**; giriş tuşları 68 px.
- Her ekranda **tek bir ana eylem**; menü yok, gizli hareket yok.
- Koyu yazı / açık zemin (güneşte okunur), gövde yazısı 17 px.
- Sistem yazı tipi: iPhone'da SF Pro, Android'de Roboto. Dışarıdan yazı tipi,
  simge paketi veya harita karosu indirilmez — hepsi uygulamanın içinde.
- Her metin Türkçe, jargonsuz: "boş kapı", "gidildi", "kayıt bekliyor".
- Sayılar `tr-TR` biçiminde (1.973), tarihler Türkçe ay adlarıyla.
- Bina ekranında alt sekme çubuğu gizlenir; iki büyük düğme ekranın altını tek
  başına kullanır.
