# Saha Sistemi — saha uygulaması (PWA)

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
npm run qa         # örnek veriyle ekran fotoğrafları → qa/*.png
npm run e2e        # GERÇEK sunucuya karşı uçtan uca test → qa/e2e/*.png
npm run ikon       # PWA simgelerini yeniden üret (Python + Pillow)
npm run build:sahte  # DEMO derlemesi (örnek veri içerir) → dist-sahte/
```

`dist/` klasörü FastAPI tarafından statik olarak sunulur (sözleşme §5).

### Uçtan uca test

`qa/e2e.mjs` derlenmiş uygulamayı **çalışan bir FastAPI sunucusuna** bağlar ve
gerçek akışı yürütür: ilk giriş (davet kodu + PIN) → günün 25 binalık rotası →
dört farklı sonuç → yenileme sonrası kalıcılık → çevrimdışı iki kayıt →
bağlantı gelince tam bir kez senkron → yönetici konsolunda sayıların hareketi.
Her adımın fotoğrafı `qa/e2e/` altına düşer.

```bash
SAHA_URL=http://127.0.0.1:8098 E2E_DAVET=<6 hane> E2E_YONETICI_DAVET=<6 hane> node qa/e2e.mjs
```

> Test **veri yazar**. Gerçek veritabanı yerine bir kopyaya bağlanın
> (`SAHA_DB=<kopya> PYTHONPATH=kod python -m saha.sunucu --host 127.0.0.1 --port 8098`).

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
   kalır (`depo/bugun.tsx` → `bekleyenleriUygula`). Aksi hâlde satışçı işlediği
   bina yeniden listeye düşünce uygulamaya güvenmez.
6. Uygulama kabuğu ve son liste servis çalışanında önbellektedir; sinyal yokken
   yeniden açılsa bile aynı şekilde çalışır.
7. Kuyrukta kayıt varken çıkış yapılamaz.

> "Ana ekrana ekle" ve çevrimdışı çalışma yalnız HTTPS'te (veya
> `http://localhost`) devreye girer. Ofis ağında düz HTTP ile her şey çalışır,
> çevrimdışı hariç.

## Klasörler

| Yol | İçerik |
|---|---|
| `src/api/` | Sözleşme tipleri (`tipler.ts`), fetch sarmalayıcı (`istemci.ts`), uçlar (`uclar.ts`), örnek sunucu (`sahte.ts`) |
| `src/depo/` | IndexedDB (`db.ts`), kuyruk/senkron (`senkron.tsx`), oturum (`oturum.tsx`), bugünün listesi (`bugun.tsx`) |
| `src/ekran/` | Giriş · Bugün · Bina · Sonuç çekmecesi · Harita · Ben |
| `src/ortak/` | Ortak arayüz parçaları, simgeler, Türkçe biçimlendirme, yol tarifi bağlantıları |
| `src/yonetici/` | **Başka bir ajanın alanı.** Şimdilik yer tutucu. |
| `src/stil/temel.css` | Tüm tasarım (tek dosya, değişken tabanlı) |
| `src/sw.js` | Servis çalışanı şablonu; dosya adları derlemede gömülür |
| `qa/cek.mjs` | Ekran görüntüsü + çevrimdışı doğrulama betiği |

## Tasarım kuralları

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
