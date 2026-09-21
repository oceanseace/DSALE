# Uygulama mimarisi — Dehanet EÇM · Bursa Fiber Satış Haritası

Bu belge **Sunum** (`src/sunum/**`) ve **Keşif** (`src/kesif/**`) sahiplerinin ihtiyaç duyduğu her
dışa açık arayüzü listeler. Temel (foundation) katmanı burada donmuştur: imzalar geriye dönük
uyumlu kalacak, yenileri eklenecek.

**Kurallar**
- Tüm arayüz metinleri Türkçedir (ı İ ş ğ ü ö ç). Sayılar `selectors.ts` biçimlendiricileriyle yazılır — `toLocaleString` elle çağrılmaz.
- Hiçbir sayı koda gömülmez. 19.706 / 296.778 / 37.097 / ±%0,5 gibi değerler `meta` ve `plan`dan türetilir.
- `window.__DSALE__`'ı yalnız `core/kontrat.ts` yazar.
- Ağ yok: altlık çevrimdışı (OSM verisi pakete gömülü). CARTO karoları yalnız `karoErisimi()` true dönerse ve yalnız OSM altlığının **altına** eklenir.

```
src/
  data/     veri paketi (JSON → tipli yapılar), seçiciler, biçimlendiriciler   [temel]
  map/      deck.gl: HaritaSahnesi + katman fabrikası + kamera + ışık + font   [temel]
  ui/       tema belirteçleri ve ortak bileşenler                              [temel]
  core/     URL sözleşmesi, __DSALE__, platform köprüsü, uygulama bağlamı      [temel]
  sunum/    sunum modu  (Sunum ajanı)          ← şu an taslak
  kesif/    keşif modu  (Keşif ajanı)          ← şu an taslak
  App.tsx   mod kabuğu + global tuşlar
  main.tsx  giriş: font + veri + sözleşme → React
electron/   main.cjs (ana süreç) + preload.cjs (köprü)
scripts/    qa.mjs (görsel test), electron-dev.mjs
build/      icon.svg (sürüm ajanı PNG/ICO üretir)
```

---

## 1. Veri — `src/data`

```ts
import { veri, planGetir, planVeyaVarsayilan, planNleri, binaBolgeleri } from './data/load';
import { sayi, yuzde, isaretliYuzde, kisaSayi, km, onlukOran, enBuyukFarkHane } from './data/selectors';
```

### `load.ts`
| Export | Açıklama |
|---|---|
| `veri(): Veri` | Tümü: `{binalar, meta, altlik, planPaketi}`. İlk çağrıda ayrıştırır (~200 ms), sonrası önbellek. |
| `BinaVerisi` | `n, konum, lon, lat, kat, yukseklik, toplamHp, resHp, aktif, firsat, birim, ilce, mahalle, il, yalova, ofisMesafeKm, indeksler, taban, paket` — tümü tipli diziler, deck.gl'e doğrudan verilebilir. |
| `AltlikVerisi` | `attribution, yollar, kiyi, goller, ilceAlanlari, ilceSinirlari, ilceEtiketleri` |
| `varsayilanN()` · `planNleri()` · `planGetir(n)` · `planVeyaVarsayilan(n)` · `planHariciMi(n)` | Plan erişimi. `planGetir` dış (Plan Aç…) planı öncelikler. |
| `planEkle(ham): {tamam:true,plan} \| {tamam:false,hata}` | Dış plan doğrular + kaydeder. |
| `planSurumu()` · `planDinle(cb): ()=>void` | Dış plan değişiminde artar / haber verir (`useMemo` bağımlılığı). |
| `binaBolgeleri(plan): Uint8Array` | Bina → bölge no (1..N, 0 = atanmamış). Plan başına önbellekli. |
| `bolgeHalkalari(plan)` · `bolgeAlanlari(plan)` | Sınır çizgisi / dolgu verisi (PathLayer / SolidPolygonLayer). |
| `bolgeEtiketNoktasi(b): LonLat` | **`b.etiket ?? b.merkez`.** Tüm etiket, pin ve çağrı balonları bunu kullanır (`merkez` poligonun dışına düşebilir). |
| `anlikEtiketVar(plan): boolean` | Planda gerçek `anlik_etiket` var mı (CCPD-2.5+). |
| `anlikBinaBolgeleri(dizi): Uint8Array` | `plan.anlik_etiket[s]` → bina→bölge dizisi (LRU 32 önbellek). |
| `poligonParcalari(g)` · `cizgiParcalari(g)` · `KAT_YUKSEKLIGI_M` | Geometri yardımcıları. |

### `types.ts` (veri sözleşmesi)
`Plan { n, olcu, hedef, sapma_min, sapma_maks, birim_bolge[], bolgeler[], anlik?, anlik_etiket? }`
`Bolge { bolge, kod, ad, kisa_ad, renk, bina, res_hp, firsat, penetrasyon, sapma, merkez, etiket?, ofis_km, mst_km, ilceler[], mahalle_sayisi, ust_mahalleler[], yalova_bina, yalova_res_hp, poligon?, alan_km2? }`

İki alan **isteğe bağlıdır** ve eski veri paketlerinde yoktur — ikisini de savunmacı okuyun:
- `Bolge.etiket?: [lon,lat]` → `bolgeEtiketNoktasi()` ile
- `Plan.anlik_etiket?: string[]` → `anlikEtiketVar()` ile (yoksa S4 yedeğe düşer)

### `selectors.ts`
| Export | Örnek |
|---|---|
| `sayi(x, basamak=0)` | `19706 → "19.706"` |
| `yuzde(oran, basamak=1)` | `0.0045 → "%0,45"`, `-0.0035 → "−%0,35"` (işaret % ÖNÜNDE, U+2212) |
| `isaretliYuzde(oran, basamak=2)` | `+%0,51` · `−%0,35` · yuvarlamada sıfırsa `%0,00` |
| `kisaSayi(x)` | `296778 → "297 bin"` |
| `km(x)` · `km2(x)` · `buyukHarf(s)` | `12,3 km` · `42 km²` · Türkçe büyük harf |
| `onlukOran(pay, payda, birim='hane')` | `(1745,1971) → "10 haneden 9'u"` |
| `maksSapma(plan)` · `sapmaAraligi(plan)` | en büyük \|sapma\| · `[min,maks]` |
| `enBuyukFarkHane(plan)` | hedeften en büyük sapmanın hane karşılığı (yukarı yuvarlanır) |
| `dengeliPlanlar(esik=0.01): number[]` | \|sapma\| ≤ eşik olan plan N'leri — **kaydırıcılar yalnız bunlarda durur** |
| `binaBilgisi(i, plan?)` | ipucu/kart verisi; `ad` boşsa `''` ("Null" temizlenir) |
| `temizAd(s)` | `'Null'` / boş → `''` |
| `binaMetrigi(m)` | `'res_hp'\|'firsat'\|'aktif'\|'toplam_hp'\|'kat'\|'penetrasyon'` → `(i)=>number` |
| `bolgeSinirKutusu(plan, bolgeler?)` · `tumSinirKutusu()` | `fitBounds` için `[[minLon,minLat],[maxLon,maxLat]]` |
| `hexRgba` `hexRgb` `rgbaCss` `tonla` `karistir` `bolgeRenkTablosu` | renk yardımcıları (RGBA = `[r,g,b,a]`) |
| `toplamlar()` · `bolgeBul(plan,no)` · `binaBolgesi(plan,i)` | kısayollar |

---

## 2. Harita — `src/map`

### `HaritaSahnesi.tsx` (tek deck.gl yüzeyi)

```tsx
const harita = useRef<HaritaApi>(null);

<HaritaSahnesi
  ref={harita}
  katmanlar={(t) => sahneKatmanlari(t)}   // LayersList ya da (t saniye) => LayersList
  baslangicKamera={KAMERA.bursa}
  kamera={{ durum: {...}, sureMs: 2200, tur: 'fly' }}   // bildirimsel; içerik değişince uçar
  etkilesim={false}                        // true → controller açık (Keşif)
  isik="gece"                              // 'gece' | 'gunes' | 'golgeli' | false
  pickingRadius={6}
  onHover={...} onClick={...} getTooltip={...} getCursor={...}
  onIlkKare={hazirBildir}                  // 2. kareden sonra bir kez
  onKameraDegisti={(k) => ...}
  onMesgul={(m) => kontratGuncelle({ mesgul: m })}
  onBoyut={(b) => ...}
  saat={false}                             // dizi verilse de rAF saatini zorla
>
  {/* HTML katmanı (children) */}
</HaritaSahnesi>
```

`katmanlar` bir **fonksiyon** ise rAF saati çalışır (animasyon); **dizi** ise saat durur ve GPU boşta kalır.
Verilmeyen geri çağrılar deck.gl'e aktarılmaz (undefined prop deck'in varsayılanını ezip çizimi kırar).

**`HaritaApi` (ref):**
```ts
flyTo(hedef: Partial<KameraDurumu>, sureMs?, secenek?): Promise<boolean>  // false = kesildi
orbit(dereceSaniye?): void            // 0 = durdur
durdur(): void
fitBounds(kutu, { padding?, pitch?, bearing?, maksZoom?, sureMs?, secenek? }): Promise<boolean>
sigdirHesapla(kutu, {...}): KameraDurumu       // uçmadan hesapla
kamera(): KameraDurumu
kameraAyarla(k: Partial<KameraDurumu>): void   // anında, animasyonsuz
boyut(): { width, height }
yansit(konum: LonLat | [lon,lat,z]): [x, y]    // HTML çağrı balonları için ekran pikseli
mesgulMu(): boolean
deck(): Deck | null
```
Kullanıcı etkileşimi (sürükle/zoom/döndür) uçuşu ve yörüngeyi otomatik keser.

### `kamera.ts`
- `KAMERA` ön ayarları: `genel, genelEgik, bursa, nilufer, ofis, yalova` (hepsi `KameraDurumu`).
- `KameraDurumu = {longitude, latitude, zoom, pitch, bearing}`
- `fitBounds(kutu, {width, height, padding?, pitch?, bearing?, maxZoom?}): KameraDurumu`
- `kameraAraDeger(a, b, t, boyut, {tur:'fly'|'linear', yumusatma?, egri?})`
- `KameraSurucusu` (HaritaSahnesi kullanır; doğrudan gerekmez): `flyTo/orbit/durdur/etkilesim/mesgulMu/yokEt`
- `aciNormalize(a)` · `OFIS_KONUM`

### `katmanlar.ts` — katman fabrikası (saf fonksiyonlar)
Önerilen çizim sırası: `karo? → altlik → bolgeSinirlari('dolgu') → binalar3D/binaIsiklari → bolgeSinirlari('cizgi') → hpSutunlari → arklar → ofisIsaretcisi → etiketler`

| Fabrika | İmza (seçeneklerin tamamı JSDoc'ta) |
|---|---|
| `altlik(o?)` | `{id, gorunurluk, ilceEtiketleri, ilceSinirlari, yolParlama, etiketBoyutu, kara}` → `Layer[]` |
| `ilceEtiketKatmani(o?)` | `{id, gorunurluk, etiketBoyutu}` → `Layer` — yalnız ilçe adları. `altlik` bunu kendi içinde çağırır; **3B sütun/parlak küme kullanan sahneler** `altlik({ilceEtiketleri:false})` deyip bu katmanı EN SONA koyar (yoksa sütunlar "GEMLİK"i "GE..İK" yapıyor). S2/S3/S6 böyle. |
| `binalar3D(o?)` | `{id, plan, renkModu, yukseklikOlcegi, vurguBolgeler, sonukluk, gorunurBolgeler, gorunurYaricapKm, renkGecisMs, pickable, autoHighlight, opacity, kenar}` → `Layer` (id varsayılan `'binalar'`) |
| `binaIsiklari(o?)` | `{id, plan, renkModu, yaricap, minPiksel, alfa, gorunurYaricapKm}` — uzak görünümde parlayan şehir |
| `bolgeSinirlari(o)` | `{plan, id, parca:'hepsi'\|'dolgu'\|'cizgi', dolguAlfa, cizgiGenislik, parlama, vurguBolgeler, bolgeler, gorunurluk}` → `Layer[]` |
| `hpSutunlari(o?)` | `{id, olcu:'res_hp'\|'firsat'\|'aktif'\|'toplam_hp', mod:'hex'\|'bolge', plan, yaricap, ilerleme, yukseklikOlcegi, renkAraligi, vurguBolgeler, pickable}` |
| `ofisIsaretcisi(o?)` | `{id, t, yukseklik, etiket, etiketBoyutu, olcek, renk, halkaYaricapi}` → `Layer[]` (sarı marka rengi) |
| `arklar(o)` | `{plan, id, bolgeler, ilerleme, t, genislik, yukseklikOrani}` → `Layer[]` (ofis → bölge etiketi) |
| `arkKatmani(o)` | GPU ArcLayer alternatifi |
| `etiketler(o)` | `{id, veri: Etiket[], boyut, renk, arkaPlan, arkaPlanRengi, kenarRengi, yatay, dikey, kaydir, gorunurluk, fontWeight, ustte}` |
| `bolgeEtiketleri(o)` | `{plan, id, bicim:'kod'\|'kisa'\|'kodKisa'\|'tam', boyut, yukseklik, bolgeler, vurguBolgeler, gorunurluk}` |
| `cartoKaroKatmani(o?)` / `karoErisimi()` | Çevrimiçi raster; `karoErisimi()` tek karoyu `Image()` ile dener (≤2,5 sn, `naturalWidth>0`). |
| `katmanlar(...parcalar)` | `false/null` ayıklayan birleştirici |
| `planAnahtari(plan)` | `updateTriggers` için kararlı kimlik |
| `binaRenkleri(mod)` | `Uint8ClampedArray(n*4)`; **anahtar başına önbellekli (LRU 16)** |
| `aralikli(s)` | `"NİLÜFER" → "N İ L Ü F E R"` (U+2009) |
| `TOPLAMSAL_KARISIM` · `METRIK_PALETI` | parlama karışımı · varsayılan metrik paleti |

**`BinaRenkModu`** (dördü de `binalar3D`/`binaIsiklari`/`binaRenkleri` ile çalışır):
```ts
{ tur:'bolge', plan }
{ tur:'tek', renk: RGBA }
{ tur:'metrik', metrik: BinaMetrigi, palet?: string[], alan?: [min,max], olcek?: 'dogrusal'|'karekok'|'log' }
{ tur:'ozel', renk: (i)=>RGBA, anahtar: string }          // anahtar değişmedikçe yeniden hesaplanmaz
{ tur:'etiketDizisi', dizi: string, tablo: RGBA[], anahtar? }  // S4: plan.anlik_etiket[s] kareleri
```
`'etiketDizisi'` kullanımı (S4 "nasıl böldük"):
```ts
const tablo = bolgeRenkTablosu(plan);
const dizi  = plan.anlik_etiket![s];
binalar3D({ plan, renkModu: { tur:'etiketDizisi', dizi, tablo, anahtar: `s${s}` }, renkGecisMs: 1200 });
```

### `sahneler.ts`
`temelSahne(plan, o?)` → `LayersList`: altlık + bölge dolgusu + 3B binalar + (şehir ışıkları) + sınır çizgisi + (yaylar) + ofis + bölge etiketleri.
Seçenekler: `{t, renkModu, yukseklikOlcegi, vurguBolgeler, secilebilir, sinirlar, ofis, arklar, etiket, ilceler, isiklar, altlikGorunurlugu, renkGecisMs}`.
Zorunlu değil — kendi sahnenizi doğrudan fabrikadan kurabilirsiniz.

### `isik.ts` · `fontlar.ts`
- `isikEfekti('gece'|'gunes'|'golgeli')`, `BINA_MALZEMESI`, `SUTUN_MALZEMESI`
- `HARITA_FONT` (TextLayer'a yayılır), `KARAKTER_SETI`, `fontlariYukle()`
  **Yeni bir tipografik işaret kullanacaksanız (ör. ✓ ▲ ‰) önce `KARAKTER_SETI`'ne ekleyin,** yoksa deck.gl "Missing character" uyarısı verir ve QA kırmızıya döner.

---

## 3. Tema ve bileşenler — `src/ui`

`tema.ts`: `renk` (zemin, panel, cizgi, sari `#FFC400`, mavi, metin/metin2/metin3, basari, uyari, tehlike), `renkRgba`, `yazi` (baslik = Barlow Condensed, govde = Inter, harita), `boy` (not 16 · kucuk 22 · govde 28 · buyuk 36 · alt 48 · baslik 72 · dev 120 · mega 168), `bosluk`, `golge`, `gecis`, `stil`.

- **Ölçek:** her ölçü 1920×1080 tasarım pikselidir; CSS'te `u(28)` → `calc(28 * var(--u))`, canvas için `uPx(28)`. Böylece 1366×768'de kompozisyon aynı kalır.
- **Durum renkleri yalnız yazı/ikon içindir**, bölge renklerinin yanında dolgu olarak kullanılmaz.
  `durumIsareti(sapma, esik=0.01) → { seviye, ikon: '✓'|'▲'|'▼', renk }`

Bileşenler (`import { ... } from './ui'`):
| Bileşen | Öne çıkan prop'lar |
|---|---|
| `CountUp` | `deger, sure, gecikme, bicim, animasyon, onek, sonek` — genişliği sabit, sayarken kaymaz |
| `BuyukRakam` | `deger, bicim, etiket, alt, boyut, renkKodu, animasyon, gecikme, hizala` |
| `Kart` | `baslik, seritRengi, ic, yaricap, koyu` — cam panel |
| `Lejant` | `ogeler[{renk,etiket,deger,vurgu}]` ya da `gradyan[] + uclar`, `yon`, `baslik` |
| `IlerlemeCubugu` | `oran, kalinlik, renkKodu, gecisMs, parlama` |
| `Marka` | `alt, boyut, isaret` — `meta.organizasyon_kisa` |
| `KaynakNotu` | `ek, altlik` — OSM atfı (ODbL gereği her görünümde) |
| `Rozet` / `DurumRozeti` | `nokta, renkKodu, boyut` / `sapma, esik, yuzdeyiGoster` |
| `Grafik` | `secenek: EChartsCoreOption, birlestirme` — ECharts + `'dehanet'` teması (bar/line/pie, markLine, tooltip, graphic) |

---

## 4. Çekirdek — `src/core`

```ts
const { mod, setMod, n, setN, plan, nListesi, planSurum, meta, planAc, planMetniYukle, bildirim, bildir, hazirBildir }
  = useUygulama();
```
- `plan` = etkin plan (`n` + dış planlar), `planSurum` değişince yeniden hesaplayın.
- `planAc()` Electron'da yerel iletişim kutusunu, tarayıcıda gizli `<input id="dsale-plan-dosya">` girdisini kullanır. Menü (`Dosya › Plan Aç…`) ve pencereye `.json` sürükleme zaten bağlıdır.
- `bildir(metin, 'bilgi'|'basari'|'hata')` App'teki ortak bildirimi gösterir.
- `hazirBildir()` → `__DSALE__.hazir = true` (HaritaSahnesi'nin `onIlkKare`'sinden çağırın).

`url.ts`: `urlOku(): {mod, sahne, adim, film, n, ham}`, `urlYaz({...})` (replaceState), `urlSayi(ad)`, `urlBayrak(ad)`.
Mod'a özel ek parametreleri `ham` (URLSearchParams) üzerinden okuyun.

`platform.ts`: `masaustuMu()`, `planDosyasiAc()`, `onPlanYuklendi(cb)`, `onModDegistir(cb)`, `tamEkranDegistir()`, `surukleBirak(cb)`.

`kontrat.ts`: `kontratGuncelle(p)`, `kontratOku()`, `hazirBildir()`. **`window.__DSALE__` yalnız buradan yazılır.**

---

## 5. Test edilebilirlik sözleşmesi

Adres parametreleri: `?mod=sunum|kesif` · `?sahne=<1..10>` · `?adim=<n>` · `?film=1` · `?n=<planN>`
(Keşif kendi eklerini `ham` üzerinden okur: `?bolge ?ara ?bina ?gorunum=2b ?renk ?katman`.)

```ts
window.__DSALE__ = {
  hazir: boolean,        // ilk kare + fontlar hazır → ekran görüntüsü alınabilir
  mesgul: boolean,       // kamera uçuyor / geçiş sürüyor
  mod: 'sunum' | 'kesif',
  sahne: number, sahneSayisi: number,
  adim: number,  adimSayisi: number,
  n: number,
  git(sahne: number): void,
  kesif?: { ... },       // Keşif'in ek kancası (bolgeSec, ara, binaSec, boyut, katman, mesgul)
  veriSurumu?: number,
};
```
Her mod, kendi durumu değiştiğinde `kontratGuncelle({...})` çağırmakla yükümlüdür (en az: `sahne`, `adim`, `n`, `mesgul`).
QA `hazir === true && !mesgul` olana kadar bekler, sonra ek 900 ms.

---

## 6. Yeni sahne eklemek (Sunum)

1. `src/sunum/sahneler/sXX....tsx` içinde sahneyi tanımlayın: kamera anahtar kareleri, `katmanlar(b)` (saf, `t`'den türetilmiş) ve HTML `Katman` bileşeni.
2. `src/sunum/sahneler/index.ts` dizisine ekleyin — **dizi sırası = sahne numarası**.
3. `sahneSayisi` otomatik olarak dizi uzunluğudur; `kontratGuncelle({ sahne, sahneSayisi, adim, adimSayisi })` çağırın.
4. Kamera: sahne girişinde `harita.flyTo(...)` zinciri ya da `kamera={{durum, sureMs}}` prop'u. Uçuş sırasında `onMesgul` zaten `mesgul`ü yönetir.
5. Katmanlarda animasyon için `katmanlar` prop'unu **fonksiyon** verin (`(t) => …`); sahne durağan hâle geldiğinde diziye dönerek saati durdurabilirsiniz.
6. Metinler: manşet ≤ 6 kelime, tek büyük sayı; tüm rakamlar `plan`/`meta`dan türetilir.

**Sunum tuşları** (`src/sunum/motor/tuslar.ts`): `→` `PageDown` `Boşluk` `Enter` / sol tık = ileri ·
`←` `PageUp` `Backspace` / sağ tık = geri · `Home` `End` · `F` film (≈95 sn döngü) · `Esc` filmi durdur ·
`1`–`9`, `0` sahneye atla · `↑`/`↓` S9'da bölge sayısı.
`data-etkilesim="1"` taşıyan parçalara tıklamak sahneyi ilerletmez.
Kabuk tuşları (`App.tsx`) bozulmadan kalır: `K` mod, `O` plan aç, `Shift+F` tam ekran.

---

## 7. Derleme ve görsel QA

```bash
npm.cmd run typecheck                 # tsc --noEmit
npm.cmd run build                     # dist/       (Electron kabuğu)
npm.cmd run build:html                # dist-html/index.html (tek dosya, file:// çalışır)
npm.cmd run build:html -- --outDir dist-kesif     # ayrı klasöre

node scripts/qa.mjs                                        # dist-html, sunum s1, 1920×1080
node scripts/qa.mjs --modes sunum,kesif --scenes 1-10 \
     --adim 6:1,4,8 --kesif-durumlar varsayilan,bolge4,n25,arama,2b,hover \
     --sizes 1920x1080,1366x768 --offline --out qa/release
node scripts/qa.mjs --html ../outputs/DSALE_Sunum.html --offline
```
- Tarayıcı sırası: **msedge + ANGLE d3d11** → Playwright Chromium + d3d11 → SwiftShader.
  Bu makinede yüklü Edge (153.x) playwright-core 1.63 ile uyumsuz olduğundan otomatik olarak
  Playwright'in Chromium'una düşer (`node node_modules/playwright-core/cli.js install chromium` ile indirilmiştir).
  `--kanal msedge|chromium` ile zorlayabilirsiniz.
- Çıkış kodu 1: konsol hatası, "Missing character" uyarısı ya da `hazir` olmayan sayfa.
- PNG'ler `app/qa/` altına düşer — **bakın ve dürüstçe değerlendirin** (taşma, kırpılma, kara harita, 1366'da okunabilirlik).
- Keşif senaryoları: `varsayilan,bolge<N>,n<N>,arama,2b,hover,planac,firsat,penetrasyon,sutun,bina[:<seri|indeks>]`.
  `hover` önce `bolgeSec(1)` yapar, kamera durmasını bekler, sonra (0,55·G, 0,5·Y) noktasına gider — ekranın tam ortası
  varsayılan kamerada Marmara denizi olduğu için eski senaryo hiçbir zaman ipucu yakalamıyordu.

**Electron:**
```bash
npm.cmd run electron:dev              # vite + electron (DSALE_DEV_URL)
npm.cmd run electron:start            # build + electron .
DSALE_QA_EKRAN=qa/exe-ilk-kare.png node_modules/.bin/electron . --mod=kesif   # hazır olunca kare alır ve çıkar
```
`electron/main.cjs`: tek örnek kilidi · `show:false` + `#03060D` zemin · maximize · F11/Esc tam ekran · `--kiosk` ·
Türkçe menü (Dosya › Plan Aç… / Çıkış, Görünüm › Tam Ekran / Sunum / Keşif / Yeniden Yükle, Yardım › Hakkında) ·
paketliyken DevTools ve gezinme kapalı · argv → URL (`--mod= --sahne= --adim= --n= --film`).

---

## 8. Bilinen sınırlar

- Bölge etiketleri şehir merkezinde üst üste biniyor (B1/B2/B3/B5 merkezleri 0,04–0,16° arayla). Sunum bunu HTML çağrı
  balonlarıyla (`sunum/bilesen/Cagrilar.tsx`) çözer; **ofis rozeti de o katmandadır** (`ofisCagrisi`, `sabit: true`) ve
  o sahnelerde `ofisIsaretcisi({etiket:false})` kullanılır. Keşif kararlı coğrafi eleme kullanır (`gorunurEtiketler`).
- `Cagrilar` kadraj dışı noktaları GİZLEMEZ: kutuyu ekran kenarına yaslar ve `◂ / ▸` oku koyar. Çakışma çözümü sabit
  noktaya çarpana kadar tekrarlanır (tek geçiş, kutuyu daha önce yerleşmiş bir kutunun altına saklıyordu).
  Ek alanlar: `sabit` (önce yerleşir, itilmez) · `kucuk` (küçük kutu) · `sap` (nokta başına çizgi boyu) · prop `altPay`
  (alt kenardan bırakılan pay; lejant şeridi oraya oturur).
- `sigdirEgik`in `ek`/`kaydir` telafisi AMPİRİKTİR. `kaydir` büyütülürse kamera merkezi kayar ve geniş bölgelerin uzak
  ucu kadrajdan taşar; `ek` küçültülüp `donme:true` ile birleşince kadraj gereğinden fazla açılır ve küçük kümeler
  (B4'ün 266 Yalova binası) görünmez olur. S6 bu yüzden `{ek: 0.05, kaydir: 0.04}` sabitini kullanır.
- CARTO karoları yalnız çevrimiçi ve `karoErisimi()` true iken, OSM altlığının altına eklenmelidir.
- Paketli exe'nin açılışı (~24 sn, ilk çizilmiş kareye kadar) **sıkıştırmadan gelmiyor**: `compression:"store"` ile
  332 MB'lık bir sürüm ölçüldü, süre değişmedi. Maliyet Electron + Chromium + deck.gl ilk kare kurulumunda.

---

## 9. Keşif modu — `src/kesif` (ek)

Dosyalar: `Kesif.tsx` (kök) · `durum.ts` (reducer + adres parametreleri) · `katmanKur.ts` (katman tarifi) ·
`kameraHedefleri.ts` (kenar boşlukları, sınır kutusu) · `arama.ts` (dizin + puanlama) ·
`UstBar/NSecici/AramaKutusu/SolPanel/KatmanKarti/MetrikLejant/BolgeCekmecesi/BinaKarti/Ipucu` · `ikonlar.tsx` · `kesif.css`.

**Ek adres parametreleri** (`urlOku().ham` üzerinden okunur, `urlYaz` ile geri yazılır):

| Parametre | Değer | Etki |
|---|---|---|
| `?bolge=` | 1..N | bölgeyi seçer, çekmeceyi açar, oraya uçar |
| `?ara=` | metin | arama kutusunu doldurur ve sonuç listesini açar |
| `?bina=` | seri no ya da 0 tabanlı indeks | binayı seçer ve oraya uçar |
| `?gorunum=` | `2b` \| `3b` | kuşbakışı / eğik 3B |
| `?renk=` | `bolge` \| `firsat` \| `penetrasyon` | bina renk modu |
| `?katman=` | `binalar,sinirlar,sutun,yollar,ofis` | **açık** katmanların listesi |

**QA kancası** — `window.__DSALE__.kesif` (yalnız Keşif yazar, `kontratGuncelle({kesif})` ile bir kez bağlanır):

```ts
kesif = {
  mesgul: boolean,                    // kamera uçuyor ya da 2B/3B geçişi sürüyor
  bolgeSec(no: number | null),        // null = "Tümü"
  ara(metin: string),                 // dizini kurar + listeyi açar
  aramaSec(sira = 0),                 // sonuç listesinden seçer ve uçar
  binaSec(i: number | string),        // indeks ya da seri no
  boyut('2b' | '3b'),
  katman(ad: 'binalar'|'sinirlar'|'sutun'|'yollar'|'ofis', acik?: boolean),
  basaDon(),
  durum(): KesifDurumu,
}
```

**Tuşlar:** `Esc` seçim → arama → bölge sırayla kapatır · `/` veya `Ctrl+F` aramaya odaklanır ·
`2` / `3` görünüm · `Home` başa dön · `F` tam ekran. (`K` mod, `O` plan aç → App kabuğunda.)

**Yerleşim** (tasarım pikseli): üst çubuk 112 · sol sütun 432 (bölge listesi + katmanlar) ·
sağ sütun 500 (seçim kartı + bölge çekmecesi) · metrik lejantı haritanın sol altında yüzer.
`kameraHedefleri.uiBosluk(sagAcik)` bu ölçüleri `uPx` ile gerçek piksele çevirip `fitBounds`'a verir —
seçilen bölge panellerin altında kalmaz.

**Bölge etiketleri.** deck.gl `CollisionFilterExtension` kullanılmadı: cihaz piksel oranı 1 dışında
(Windows %125/%150 ölçek, ki sunum dizüstünde çok olası) etiketleri tamamen yutuyor.
Yerine `katmanKur.gorunurEtiketler()` var — ofis noktası baştan kabul, bölgeler ofise uzaklığa göre
sıralı, kabul edilene `eps` dereceden yakın etiket atlanır. Sonuç viewport'tan bağımsız ve kararlı
(N=8'de B1·B4·B7·B8 + ofis). Bölge seçiliyken yalnız o bölgenin etiketi, `etiket` noktasının sağına yazılır.

**Seçim vurgusu.** Halka yerine binanın kendisi boyanır (`binaRenkleri` 'ozel' modu, anahtar
`sec:<metrik>:<plan>:<adet>:<ilk>`); üstüne ince sarı halka eklenir. Yakın planda 65 binalık bir sitede
büyük daireler tek bir sarı lekeye dönüşüyordu.

**Arama.** Dizin ilk odaklanmada kurulur (`dizinHazirla`). Mahalle girdileri **(ilçe, mahalle) çifti**
ile anahtarlanır (meta.mahalle_sayisi = 165 bu çiftleri sayar), site/bina girdileri birim bazlıdır;
adsız birimler dizine girmez (mahalle ya da seri no ile bulunur). 4+ rakamlı sorgu seri no araması yapar.

**CARTO.** `karoErisimi()` true dönerse ve "Yollar" katmanı açıksa, OSM altlığının **altına** eklenir.
Çevrimdışı sessizce atlanır (probe 2,5 sn).
