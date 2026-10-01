# Bursa Fiber Satış Haritası — sunum

**TURKCELL SUPERONLINE DEHANET EV ÇÖZÜM MERKEZİ** için hazırlanmış 3B saha haritası.

Bursa ve Yalova'daki **19.706 bina · 296.778 RES HP · 108.491 aktif abone · 189.272 fırsat**,
25 satış sorumlusunun bugünkü kadrosuna göre **8 bölgeye** bölündü. Bölgeler RES HP üzerinden
dengelendi: hedef **37.097 hane**, gerçekleşen sapma **−%0,02 / +%0,06** (hedeften en büyük sapma 23 hane; en büyük ve en küçük
bölge arasındaki açıklık 31 hane).
Uygulamanın iki modu var: **Sunum** (10 sahnelik sinematik anlatım) ve **Keşif** (bölge, mahalle,
bina düzeyinde serbest gezinme).

---

## Sunumu açma

### 1. Uygulama (önerilen) — `DSALE_Sunum.exe`

Çift tıklayın. Kurulum yok, internet yok, yönetici yetkisi yok. İlk açılışta kendini geçici
klasöre açar, o sırada **“Bursa Fiber Satış Haritası · açılıyor…”** görseli görünür — bu
bilgisayara göre **15–30 saniye** sürer (test makinesinde pencere ~16 sn, harita çizilmiş hâlde
24–27 sn; antivirüsün ilk taraması tek seferlik 38 sn'ye çıkarabiliyor). **İkinci kez tıklamayın**,
pencere kendiliğinden gelecek. USB'den değil, diske kopyalayıp çalıştırmak belirgin biçimde hızlıdır.

> **Süre uygulamanın kendisinden geliyor, sıkıştırmadan değil.** Sıkıştırmasız (332 MB) bir
> sürüm ölçüldü: açılış aynı kaldı (25 sn). Yani dosyayı büyütmenin faydası yok — çözüm
> **toplantıdan önce açıp açık bırakmak**.

> **Windows “bilgisayarınızı korudu” uyarısı çıkarsa**
> İmzalı bir kurumsal sertifikamız olmadığı için Windows SmartScreen mavi bir pencere açabilir.
> **Daha fazla bilgi** → **Yine de çalıştır**. Tek seferlik.

### 2. Yedek yol — `DSALE_Sunum.html`

Tek dosya. Edge veya Chrome'a sürükleyip bırakın; tamamen çevrimdışı çalışır, kurulum istemez.
Görüntü exe ile birebir aynıdır.

> **USB'ye ikisini birden koyun.** Sunum laptopu exe'yi çalıştırmazsa (politika, antivirüs,
> SmartScreen) HTML dosyası aynı çubuktan saniyeler içinde açılır. Yedek olmadan sunuma gitmeyin.

> **Sunumdan önce prova yapın.** Uygulamayı **sunumun yapılacağı laptopta**, projeksiyon bağlıyken
> bir kez açın: ilk açılış süresini görün, tam ekranı (**F11**) deneyin, bir sahne ilerletin.
> Eski ekran kartlarında 3B sahne ilk karede biraz yavaş kurulur. Toplantı başlamadan açık olsun.

### 3. Son çare — `DSALE_Tanitim.mp4`

Film modunun 1920×1080 kaydı (1 dk 34 sn, sessiz). Hiçbir şey açılmazsa medya oynatıcıda
çalıştırın; etkileşim yoktur ama 10 sahnenin tamamını gösterir.

---

## Tuşlar

| Tuş | İşlev |
|---|---|
| **→** | Sonraki sahne / adım (Boşluk, Enter, sol tık da olur) |
| **←** | Önceki sahne / adım (sağ tık da olur) |
| **F** | Film modu — 10 sahne kendiliğinden akar (≈95 sn, döngüsel). **Esc** durdurur |
| **K** | Mod değiştir: Sunum ⇄ Keşif |
| **1–9, 0** | Doğrudan o sahneye atla (0 = 10. sahne) |
| **Home / End** | İlk / son sahne |
| **F11** | Tam ekran (Esc çıkar) |
| **Ctrl+O** | Plan dosyası aç |

**Keşif modunda ayrıca:** `/` arama · `2` / `3` kuşbakışı ↔ eğik görünüm · `Esc` seçimi bırak ·
`Home` başa dön.

---

## Bölgeleri yeniden bölmek

Ekip büyüdüğünde ya da veri tazelendiğinde bölgeler yeniden hesaplanabilir.

```bash
# depo kökünden (DSALE)
# 1) (yalnız ham veri değiştiyse) veriyi yeniden işle
PYTHONPATH=kod .venv/Scripts/python.exe -m dsale.enrich

# 2) istediğiniz sayıda bölgeye böl — örnek: 10 satışçı
.venv/Scripts/python.exe kod/araclar/bolge.py --n 10
```

Sonuç `cikti/N10_res_hp/` altına yazılır:
`plan_N10.json` (uygulama için) · `Bursa_10_Satisci_Bolgeleme.xlsx` (Excel raporu) ·
`atama.csv` · `bolgeler.json`.

Yeni planı uygulamada görmek için: **Dosya › Plan Aç…** → `cikti/N10_res_hp/plan_N10.json`.
Plan anında yüklenir, exe'yi yeniden derlemeye gerek yoktur.

Yeni planı **varsayılan** yapmak isterseniz (exe açılışta onunla gelsin):

```bash
cd kod/sunum
npm run dist                        # → kod/sunum/release/DSALE_Sunum.exe
npm run build:html -- --outDir dist-html   # → kod/sunum/dist-html/index.html
```

İkisini `cikti/DSALE_Sunum.exe` ve `cikti/DSALE_Sunum.html` olarak kopyalayın.

> Not: uygulama 2–50 arası hazır planları içinde taşır; Keşif modundaki **N seçici** ile
> yeniden bölmeye gerek kalmadan denenebilir. `kod/araclar/bolge.py` yalnız Excel raporu ve dışa aktarılacak
> dosyalar için gereklidir.

---

## Veri kaynakları ve atıf

| Kaynak | Ne için |
|---|---|
| `veri/raw/data.xlsx` | Turkcell Superonline saha verisi: bina, HP, aktif abone, kurulum/churn |
| `veri/raw/onemap_bina_bursa.json` | **OneMap** bina geometrileri ve adresleri |
| `veri/ref/osm_*.geojson` | **© OpenStreetMap katkıcıları** — ilçe sınırları, yollar, su alanları (ODbL 1.0) |
| `veri/ref/BursaStateList.xlsx` | Mahalle / ilçe eşleme tablosu |

Haritanın altlığı **çevrimdışı** OSM verisinden çizilir; uygulama internete ihtiyaç duymaz.
İnternet varsa Keşif modunda “Yollar” katmanı **CARTO** karolarıyla zenginleşir
(© OpenStreetMap katkıcıları, © CARTO). Bu veri kurum içidir, dışarı paylaşılmaz.

---

## Klasör haritası

Bütün deponun haritası kökteki `README.md`'dedir. Sunumla ilgili parçalar:

```
DSALE/
├─ kod/
│   ├─ araclar/bolge.py       bölgeleme çalıştırıcısı (CLI) · dogrula.py · renk_denetimi.py
│   ├─ dsale/                 Python veri hattı (enrich · partition · metrics · excel_report · bundle)
│   └─ sunum/                 sunum uygulamasının kaynak kodu (React + deck.gl + Electron)
│       └─ ARCHITECTURE.md    geliştirici notları
├─ veri/                      raw/ (ham) · master/ (işlenmiş bina tablosu) · ref/ (OSM, referans)
└─ cikti/
    ├─ DSALE_Sunum.exe        ► sunum uygulaması (Windows, taşınabilir · 90 MB)
    ├─ DSALE_Sunum.html       ► tek dosya yedek (herhangi bir tarayıcı · 10 MB)
    ├─ DSALE_Tanitim.mp4      ► film modunun kaydı (1:34 · 38 MB)
    └─ N08_res_hp/            8 bölgelik plan + Excel raporu
```

---

*Hazırlayan: Dehanet EÇM · Müdür Serdar Aytaç · Sürüm 1.0*
