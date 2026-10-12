# Kod haritası — buradan başla

Turkcell.exe: Dehanet EÇM (Turkcell Superonline bayisi, Bursa + Yalova) iş akışı. İşler BOSS'tan eklentiyle
canlı gelir, operasyon Excel gibi bir tabloda yönetir, teknisyen ve satışçı telefondan çalışır.
Bu dosya tek giriş noktasıdır. `` `yol:satır sembol` `` biçimindeki çapaların satır numaralarını
`kod/araclar/harita_uret.py` koddan günceller; `<!-- OTOMATIK -->` arasını da o yazar (elle düzenleme).
Her klasörde kısa `BENIOKU.md` vardır. Bütün uçların listesi: [`HARITA_UCLAR.md`](HARITA_UCLAR.md).

## 1. Ana akış: BOSS'tan tabloya

```
BOSS Teknik Havuz sayfası (kullanıcının tarayıcısı, kendi oturumu)
 └ kod/eklenti/kanca.js      sayfanın fetch/XHR'ını dinler, liste isteğini tutar, sayfa sayfa okur
   └ kod/eklenti/kopru.js    sayfa ↔ eklenti mesaj köprüsü (window.postMessage ↔ chrome.runtime)
     └ kod/eklenti/arka.js   2 dk'da bir eşitler; eslem.js ile sade görev biçimine çevirir
       └ POST /api/boss/esitle   (X-Eslesme-Kodu başlığı; izin is.yukle)
         └ kod/operasyon/v2/api.py → boss.esitle → aktarim._uygula  → SQLite `is_emri` (+ boss_iz, boss_ham)
           └ GET /api/isler?ek=1   (izin is.liste) → gorunum.isler_yaniti (role göre kırpılmış satırlar)
             └ kod/arayuz/src/cekirdek/is/api.ts islerGetir → birimler/operasyon/isler/durum.tsx (depo)
               └ Isler.tsx (ekran) → Tablo.tsx (ızgara) · sutunlar.ts (sütunlar)
```

| Adım | Çapa |
|---|---|
| Liste isteğini yakalama | `kod/eklenti/kanca.js:122 listeyiTut` |
| Sayfa sayfa okuma | `kod/eklenti/kanca.js:511 tara` |
| BOSS alanı → sade alan (TEK eşleme yeri) | `kod/eklenti/eslem.js:9 ALANLAR` |
| Tanı/kayıt örneğinde kişisel veri maskesi (TEK yer) | `kod/eklenti/maske.js:7 KISISEL` |
| TASKS adresleri ve Pano'dan hazır süzgeç (`suz/<kod>`) | `kod/arayuz/src/cekirdek/yol/tasks.ts:12 TASKS_SUZ` · `kod/arayuz/src/birimler/operasyon/isler/panoSuzgeci.ts:18 panoSuzgeci` |
| Eşitlemeyi başlatma / sunucuya yollama | `kod/eklenti/arka.js:132 esitleBaslat` · `kod/eklenti/arka.js:159 sunucuyaGonder` |
| Uç | `kod/operasyon/v2/api.py:1743 @r.post("/api/boss/esitle")` |
| Eşitleme motoru | `kod/operasyon/v2/boss.py:249 esitle` |
| Sade alan → rapor sütunu | `kod/operasyon/v2/boss.py:54 _SUTUN` |
| Görevi iş emrine yazma (yeni/değişen/kapanan) | `kod/operasyon/v2/aktarim.py:798 _uygula` |
| BOSS'un bütün ham alanları (tablonun "ek" sütunları) | `kod/operasyon/v2/boss_ham.py:75 yaz` · `kod/operasyon/v2/boss_ham.py:136 ekle` |
| Liste ucu | `kod/operasyon/v2/api.py:1091 @r.get("/api/isler")` |
| Satır biçimi (müşteri verisinin çıktığı TEK yer) | `kod/operasyon/v2/gorunum.py:187 satir` · `kod/operasyon/v2/gorunum.py:613 isler_yaniti` |
| Arayüz isteği | `kod/arayuz/src/cekirdek/is/api.ts:145 islerGetir` |
| Arayüz deposu (yükleme + değişim yoklaması) | `kod/arayuz/src/birimler/operasyon/isler/durum.tsx:96 IslerSaglayici` |
| Satır tipi | `kod/arayuz/src/cekirdek/is/tipler.ts:79 IsSatir` |

Geri yön (uygulama → BOSS; not ve atama+randevu kendi anahtarlarıyla `ayar.boss_yazma_not` / `ayar.boss_yazma_atama` varsayılan 'acik' — çekmecede BOSS’a gidiyor / BOSS’ta ✓ / hata; askı ve diğerleri genel anahtar `ayar.boss_yazma` varsayılan 'kapali', yalnız Administrator açar:
`PUT /api/boss/yazma-anahtari`; anahtar kapalıyken tek gerçek yol Administrator'ın tek iş denemesi `POST /api/boss/yazma-dene`):
`akis._boss_yaz` → `boss_yazma.kuyruga_ekle` → eklenti `GET /api/boss/yazilacaklar` → `kanca.js yaz` (sınırlı havuz: aynı anda
`ayar.boss_yazma_paralel` istek, varsayılan 6, en çok 10; 429/502/503/504'te üstel geri çekilip yeniden dener; yazma sürerken eşitleme bekler) →
`POST /api/boss/yazma-sonucu` (HTTP + BOSS returnCode). Askı nedenleri işe göre: `GET /api/isler/{is_no}/boss-aski-nedenleri`.
Eşitleme farkları (değişiklik akışı): `GET /api/boss/farklar`. Çapalar: `kod/operasyon/v2/akis.py:624 _boss_yaz` ·
`kod/operasyon/v2/boss_yazma.py:178 kuyruga_ekle` · `kod/eklenti/arka.js:524 yazilacaklariSor` · `kod/eklenti/kanca.js:900 yaz`.

Toplu "Ata…": `TopluAta.tsx` → `POST /api/isler/toplu-ata` → BOSS'a ekip+dilim+BOSS durumu (taskStatus) başına dizi istek (`boss_yazma.atama_gruplari`, ≤10), özet `POST /api/boss/atama-durumlari`; hatalılar için "Yeniden dene" `POST /api/boss/atama-yeniden` (tekli, kendiliğinden yeniden gönderim yok). 2xx olmayan yanıtın maskeli metni `sonuc.yanit`.
Toplu "Askıya al…": `TopluAski.tsx` → `POST /api/isler/toplu-aski/nedenler` (katalog birleşimi) · `POST /api/isler/toplu-aski` → `akis.toplu_aski` → her iş için task/suspend (`boss_yazma.aski_kimlikleri`). Alt neden kaynağı: kancanın yakaladığı `.../sub/reasons` GET'i (`aski_alt_durumu`; bilinene dek askı yalnız önizlenir), elle askı örneği `ayar.boss_aski_ornek`.
09.10: yazma teslimi (`alindi` onayı, `boss_yazma.boss_goruntusuyle_dogrula`) · ilişkili işler (`operasyon/v2/iliskili.py`,
`isler/IliskiliSecim.tsx`, `isler/IliskiliHizala.tsx`) · ticket → askı + çözümde geri atama (`saha/ticket_boss_aski.py`).
BÜTÜN askılar (tek, toplu, MAP, ticket) varsayılan ABONE > "Ulaşılamadı" (alt neden işin kendi kategori listesinden seçilir): `boss_yazma.VARSAYILAN_ASKI` (form önceden seçer).
BOSS ile giriş: `kod/saha/boss_giris.py` (akış başlıkta) · `Giris.tsx BossIleGiris` · `KabukApi.tarayicida_ac` · eklenti `kimlikCikar`/`oturumBitti` → `arka.js kimlikIsle`.
Atama her AÇIK durumdan (Sahada, Yolda, Askıda, Merkeze, Ulaşılamadı …) yapılır, önceki durum olay notunda kalır (`akis.py` kural 5b); boş açıklama BOSS'a "Teknik ekibe iletildi" (`boss_yazma.VARSAYILAN_ACIKLAMA`).
TASKS/MAP kişisel tercihleri SUNUCUDA: `GET/PUT /api/isler/tercih` (Excel düzeni, adlı düzenler, TASKS↔MAP ORTAK süzgeç) · `PUT /api/isler/tercih/unvan` (Administrator: unvan varsayılanı) → `kod/operasyon/v2/tasks_tercih.py`; arayüz deposu `birimler/operasyon/isler/tercihDeposu.ts`, menü `DuzenMenusu.tsx`, MAP süzgeç şeridi + çekmece `map/MapSuzgec.tsx`.
İş çekmecesi İşlem (Ata/Askı/Not) = toplu yol (`useAtaFormu({tek})`, `useAskiFormu({tek})`); BOSS'a yazmayanlar ⋯ menüde.
Yazma sonucu her zaman sunucuya (`arka.js yazSonucIsle`; geç sonuç `sonuc_al`). MAP ⟳: `yerelTemizle` + `POST /api/boss/esitle-iste`.
Süzgeç değer listesi tek bileşen `SuzgecMenusu.tsx DegerSecici` (`degerListesi`); odak kuralı `scripts/sinir.mjs`.
BOSS durumu kesin kaynak: `aktarim._guncelle` (BOSS geri giderse iç durum da, olay notuyla) · MAP rengi `map/noktalar.ts katOf`.
BOSS EKİBİ kesin kaynak: `operasyon/v2/ekip_uzlas.py uzlas` (her eşitleme sonunda; BOSS'ta ekip boş → atama kalkar,
dolu → eşli teknisyen; sonucu gelmemiş uygulama atama yazması korunur) · açılışta bir kez yedekli `calistir` (`ayar.boss_ekip_uzlasma`).
MAP renkleri (5: gri/sarı/mavi/kırmızı/mor) TEK tablo: `arayuz/src/cekirdek/is/durumRenk.ts DURUM_RENK_VARSAYILAN` (sunucu eşi
`operasyon/v2/api.py DURUM_RENK_VARSAYILAN`; Administrator Ayarlar ▸ Durum renkleri → `PUT /api/isler/ayarlar {durum_renkleri}`).
TASKS dolgu rengi HÜCRE düzeyinde: `POST /api/isler/hucre-renk` → `operasyon/v2/isaret.py hucre_yaz` (tablo `is_hucre_renk`);
eski satır rengi (`is_isaret`) bütün hücrelere uygulanır — arayüzde `sutunlar.ts hucreRengi`.
Sütun süzgeci (TASKS ▾ ve MAP Filtreler) MAP "İş türü" ile aynı: işaretli = seçilen, kip yalnız göster/gizle seçer
(`tabloSuzgec.ts degerUyar/suzgecKur`, gövde `SuzgecMenusu.tsx SuzgecGovde`). Başlıkta sürüklemek sütun aralığı SEÇER;
sıra `SutunSecici.tsx` (sürükle, ↑/↓).
Canlı olay akışı (gerçek BOSS alan adlarını görmek için; `gorev_yapisi` olayı alanları değersiz verir):
`curl -s -m 5 -N -H "X-Eslesme-Kodu: <kod>" http://127.0.0.1:8080/api/boss/akis`

## 2. Klasörler ve giriş dosyaları

| Klasör | Ne | Giriş dosyası |
|---|---|---|
| `kod/masaustu/` | Turkcell.exe kabuğu: pencere + aynı süreçte sunucu | `kod/masaustu/turkcell.py:728 main` |
| `kod/saha/` | FastAPI sunucusu: giriş, yetki, satış, ekip, ticket, göç | `kod/saha/api.py:411 uygulama.include_router` · `kod/saha/sunucu.py` (geliştirme) |
| `kod/operasyon/v2/` | İş motoru: BOSS eşitleme, iş akışı, görünüm, dağıtım | `kod/operasyon/v2/api.py:1033 yonlendiriciler` |
| `kod/eklenti/` | BOSS Yardımcısı (Chrome/Brave eklentisi) | `kod/eklenti/manifest.json` → `arka.js` |
| `kod/arayuz/` | React + Vite PWA (telefon + masaüstü konsolu) | `kod/arayuz/src/main.tsx` → `App.tsx` → `Konsol.tsx` |
| `kod/dsale/` | Bölgeleme algoritması (bina → satışçı bölgesi) | `kod/araclar/bolge.py` |
| `kod/araclar/` | Komut satırı araçları (bölge, doğrula, renk, bu harita) | dosya başlıkları |
| `kod/lisans/` | İmzalı lisans (doğrulama uygulamayla gider) | `kod/lisans/lisans.py` |
| `kod/sunum/` | 3B sunum uygulaması (Electron, ayrı) | `kod/sunum/ARCHITECTURE.md` |
| `kod/yollar.py` | Depo yollarının TEK kaynağı | — |

Sunucu bağlama sırası: `saha/api.py` önce kendi uç modüllerini (`giris_uclari`, `satis_uclari`, `ekip_uclari`,
`yonetim_uclari`) bağlar, sonra `_v2_bagla` ile `operasyon.v2.api`, `tablolar_uclari`, `ek_dosya`,
`arama_uclari`, `admin_uclari`'yı; her modül kendi `ROTA_IZNI` sözlüğünü verir (`kod/saha/api.py:480 _v2_bagla`).

### Arayüz birimleri (`kod/arayuz/src`)
Kural: `cekirdek/` hiçbir birimi içe aktarmaz; birim başka birimi içe aktarmaz; birimleri yalnız `App.tsx`
(telefon adresleri) ve `Konsol.tsx` (yönetici menüsü) bağlar. Denetim: `node scripts/sinir.mjs`.
Taşıma: `node scripts/tasi.mjs <eski> <yeni>` (içe aktarmaları düzeltir).

| Birim | Sorumluluk |
|---|---|
| `birimler/operasyon` | TASKS (Excel gibi iş tablosu), MAP (iş haritası), BOSS bağlantısı, öbekler |
| `birimler/saha` | Satışçı telefonu (Bugün · Bina · Harita · Ben), Canlı · Kapsama · Atama · Rapor · Bölge planlayıcı |
| `birimler/altyapi` | Ticketlar (Excel TICKET sayfası; iş seçici, abone ekle, yumuşak silme) |
| `birimler/teknik` | Teknisyenin İşlerim ekranı + çevrimdışı düğme kuyruğu |
| `birimler/depo` | Seri takibi |
| `birimler/administrator` | Pano (takip), Kişiler, Unvan/yetkinlik, Veri kalitesi |
| `cekirdek/` | api (sunucu sözleşmesi) · is (iş modeli) · yerel (IndexedDB, oturum, senkron) · konsol (kabuk, menü) · ortak (parçalar) · harita · yol (adres) |

Telefon adresleri: `kod/arayuz/src/App.tsx:133 Ekran` · yönetici bölümleri: `kod/arayuz/src/Konsol.tsx:152 Bolumu`.

## 3. Veri klasörleri (yollar: `kod/yollar.py`)

| Yer | İçerik | Kural |
|---|---|---|
| `gelistirme/veri/` | Geliştirme çalışma klasörü (saha.db, gizli.key, yedek/) | git dışı; varsayılan |
| `veri/canli/` | Turkcell.exe'nin CANLI çalışma klasörü | **doğrudan yazma yok**; göç yalnız `saha/goc.py` ile, yedekli |
| `canli/` | Eski çalışan sistem (Turkcell.exe ilk açılışta devralır, dokunmaz) | **dokunma** |
| `veri/raw · ref · master` | Ham, referans, işlenmiş bina tablosu | salt okunur |
| `veri/cikti/` | Bölgeleme planları, Excel raporları | — |
| `gelistirme/test/` | Gerçek veriden sabit test girdileri | git dışı |

Deneme sunucusu: `SAHA_VERI_DIZINI=<karalama klasörü>` + port 8090–8099 (8080 canlıdır).

## 4. Çalıştırma, derleme, test

| İş | Komut (depo kökünden) |
|---|---|
| Geliştirme sunucusu | `kod\saha\GELISTIRME_BASLAT.bat` (127.0.0.1:8090) ya da `PYTHONPATH=kod .venv\Scripts\python.exe -m saha.sunucu --port 8093` |
| Arayüz geliştirme | `cd kod/arayuz && npm run dev` (5180; /api → 8090) |
| Sınır + tip denetimi | `cd kod/arayuz && node scripts/sinir.mjs && node node_modules/typescript/bin/tsc --noEmit -p .` |
| Arayüz derleme | `npm run build` (dist/; sunucu bunu sunar) |
| Exe derleme | `.venv\Scripts\python.exe kod\masaustu\derle.py` (Turkcell.exe açıkken DERLEME) |
| Python testleri | `.venv\Scripts\python.exe -m pytest kod/operasyon/testler -q` (tam takım kökten ~10 dk) |
| Eklenti testi | `node kod/eklenti/test.mjs` |
| Bu harita | `.venv\Scripts\python.exe kod\araclar\harita_uret.py` · eskimiş mi: `... --denetle` |

## 5. NASIL — cerrahi tarifler

**Yeni TASKS sütunu (sunucudan gelen alan)**
1. Alan sunucuda satıra eklenir: `kod/operasyon/v2/gorunum.py:187 satir` (rol kırpması da orada).
2. Tip: `kod/arayuz/src/cekirdek/is/tipler.ts:79 IsSatir`'a isteğe bağlı alan.
3. Sütun: `kod/arayuz/src/birimler/operasyon/isler/sutunlar.ts:121 TEMEL` dizisine `{id, baslik, gen, grup:'temel', deger}`;
   varsayılan görünsün diye `kod/arayuz/src/birimler/operasyon/isler/sutunlar.ts:168 VARSAYILAN_GORUNEN`.
4. Süzme/sıralama/kopyalama sütun tanımından kendiliğinden gelir (`tabloSuzgec.ts`, `secim.ts`, `excelAc.ts`).
5. Örnek veri kipinde görünsün: `kod/arayuz/src/cekirdek/is/sahte.ts`. Test: `kod/operasyon/testler/test_v2_tasks_tablosu.py`.

**Yeni BOSS alanını eşlemek**
- Yalnız tabloda görünmesi yetiyorsa HİÇBİR ŞEY yapma: bütün BOSS alanları `ham` olarak gelir ve "ek:" sütunu olur
  (`kod/eklenti/eslem.js:57 hamDuz` → `kod/operasyon/v2/boss_ham.py:75 yaz`). Kişisel sayılanlar: `kod/operasyon/v2/boss_ham.py:48 kisisel_mi`.
- İş motoru kullanacaksa: gerçek alan adını canlı akıştan (`gorev_yapisi`) bul → `kod/eklenti/eslem.js:9 ALANLAR`'a
  sade alan + aday düzenli ifadeler → sunucuda `kod/operasyon/v2/boss.py:54 _SUTUN` (sade alan → rapor sütunu,
  sütun adları `kod/operasyon/v2/aktarim.py:51 K`) → `is_emri` sütunu gerekiyorsa göç (aşağıda) →
  `kod/operasyon/v2/aktarim.py:562 _yeni_durum` / `kod/operasyon/v2/aktarim.py:651 _guncelle`.
  Eşleme boş kalırsa ham addan yedek: `kod/operasyon/v2/boss.py:65 _HAM_YEDEK`. Test: `node kod/eklenti/test.mjs`.

**Yeni menü öğesi (yönetici konsolu)**
1. `kod/arayuz/src/cekirdek/konsol/menu.ts:32 Bolum` tipine ad; `kod/arayuz/src/cekirdek/konsol/menu.ts:84 MENU`'ye satır
   (birim, etiket, simge, `izin: [...]`). Başlığın altına açıklama cümlesi yazılmaz (tasarım: `kod/arayuz/src/cekirdek/stil/tokenlar.css`).
2. Ekran dosyası ilgili birimin klasörüne (ör. `birimler/depo/Depo.tsx`).
3. Bağlama: `kod/arayuz/src/Konsol.tsx` başına `lazy(() => import(...))`, `kod/arayuz/src/Konsol.tsx:152 Bolumu`'ya `case`.
4. İzin yoksa önce sunucuda tanımla: `kod/saha/yetki.py:52 IZINLER` (+ paket `kod/saha/yetki.py:94 YETKINLIKLER`).
5. `node scripts/sinir.mjs` + tsc; sonra `harita_uret.py` (menü tablosu aşağıda güncellenir).

**Yeni uç + izin**
- İş motoru ucu: `kod/operasyon/v2/api.py:1033 yonlendiriciler` içinde `@r.get/post(...)`, bağımlılık `Depends(izin("eylem"))`;
  AYNI satırı modülün `kod/operasyon/v2/api.py:34 ROTA_IZNI` sözlüğüne ekle.
- Saha ucu: ilgili `kod/saha/*_uclari.py` → `yonlendirici`; izin satırı `kod/saha/yetki.py:147 ROTA_IZNI`.
- Yeni eylem adı yalnız `kod/saha/yetki.py:52 IZINLER`'e eklenir. Denetim: `kod/saha/testler/test_yetki_matrisi.py`
  (tabloda olmayan ya da eylemi farklı uç testi kırar). Arayüz çağrısı: `cekirdek/is/api.ts` ya da `cekirdek/api/*.ts`.

**BOSS'a yeni yazma şablonu** (önce önizleme, sonra Administrator'ın tek iş denemesiyle doğrulama)
1. `kod/operasyon/v2/boss_yazma.py:46 SABLONLAR`'a `{ad, yontem, dizi, dogrulandi: False, yol}`; tahmini alanlar `kod/operasyon/v2/boss_yazma.py:59 TAHMINI`;
   ilk gerçek deneme `POST /api/boss/yazma-dene {is_no, eylem}` ile; BOSS returnCode 0 görülünce `dogrulandi: True`.
2. Gövde: `kod/operasyon/v2/boss_yazma.py:262 govde_kur`. Tetik: iş geçişinden `kod/operasyon/v2/akis.py:624 _boss_yaz`.
3. Eklenti tarafı değişmez (`kanca.js yaz` şablonu körü körüne yürütür); sonuç `sonuc_al`'a döner.
4. Test: `kod/operasyon/testler/test_v2_boss_yazma.py`. BOSS'a gerçek istek ATMA.

**Göç (şema değişikliği)**
1. SQL sabitini `kod/saha/sema_v2.py` (taze kurulum ile göç aynı sabiti kullanır) ya da sonradan eklenen tablo için
   `kod/operasyon/v2/ek_sema.py`'ye yaz.
2. `kod/saha/goc.py`'ye `goc_N_ad(conn, baglam)` fonksiyonu, `kod/saha/goc.py:593 ADIMLAR`'a satır, `kod/saha/sema_v2.py:26 HEDEF`'i artır.
3. Göç yedek alarak `goc.hazirla` ile koşar (`kod/saha/goc.py:722 hazirla`); canlı veriye elle SQL yazma.
4. Test: `kod/saha/testler/test_goc.py` (`test_sutun_kumesi_taze_ile_ayni`).

<!-- OTOMATIK:BASLA -->
## 6. Otomatik (harita_uret.py üretir — elle düzenleme)

### Menü bölümü → ekran

| Birim | Bölüm (#/yonetici/…) | Etiket | Ekran | İzin |
|---|---|---|---|---|
| pano | `takip` | Pano | `kod/arayuz/src/birimler/administrator/takip/Takip.tsx:88` Takip | takip.oku |
| operasyon | `isler` | TASKS | `kod/arayuz/src/birimler/operasyon/isler/Isler.tsx:124` Isler | is.ata, is.randevu |
| operasyon | `is-haritasi` | MAP | `kod/arayuz/src/birimler/operasyon/isler/IsHaritasiEkrani.tsx:51` IsHaritasiEkrani | is.liste, is.ata |
| operasyon | `rut` | RUT (gizli) | `kod/arayuz/src/birimler/operasyon/rut/Rut.tsx:263` Rut | is.duzenle |
| operasyon | `obekler` | Öbekler (gizli) | `kod/arayuz/src/birimler/operasyon/obekler/Obekler.tsx:28` Obekler | obek.oku |
| operasyon | `boss` | BOSS bağlantısı | `kod/arayuz/src/birimler/operasyon/isler/BossBaglantisi.tsx:29` BossBaglantisi | is.yukle, is.ata |
| saha | `canli` | Canlı durum | `kod/arayuz/src/birimler/saha/yonetim/Canli.tsx:50` Canli | satis.izle |
| saha | `kapsama` | Kapsama | `kod/arayuz/src/birimler/saha/yonetim/Kapsama.tsx:32` Kapsama | satis.izle |
| saha | `atama` | Görev atama | `kod/arayuz/src/birimler/saha/yonetim/Atama.tsx:43` Atama | satis.izle |
| saha | `rapor` | Rapor | `kod/arayuz/src/birimler/saha/yonetim/Rapor.tsx:24` Rapor | satis.izle |
| saha | `bolge-planlayici` | Bölge planlayıcı | `kod/arayuz/src/birimler/saha/bolge/BolgePlanlayici.tsx:85` BolgePlanlayici | veri.yonet |
| saha | `tur-raporu` | Tur raporu | `kod/arayuz/src/birimler/saha/yonetim/TurRaporu.tsx:79` TurRaporu | veri.yonet |
| altyapi | `ticketlar` | Ticketlar | `kod/arayuz/src/birimler/altyapi/ticket/Ticketlar.tsx:64` Ticketlar | ticket.oku, ticket.defter |
| depo | `depo` | Seri takibi | `kod/arayuz/src/birimler/depo/Depo.tsx:12` Depo | depo.yonet |
| administrator | `ekip` | Kişiler | `kod/arayuz/src/birimler/administrator/ekip/Ekip.tsx:146` Ekip | ekip.yonet, yetkinlik.yonet |
| administrator | `unvanlar` | Unvan ve yetkinlik | `kod/arayuz/src/birimler/administrator/unvan/Unvanlar.tsx:40` Unvanlar | yetkinlik.yonet |
| administrator | `veri-kalitesi` | Veri kalitesi | `kod/arayuz/src/birimler/administrator/VeriKalitesi.tsx:69` VeriKalitesi | veri.yonet |

### Eklenti mesajları (kanca ↔ kopru ↔ arka ↔ panel)

| Tür | Gönderen | İşleyen |
|---|---|---|
| `boss-yanit` | kopru.js | `kod/eklenti/arka.js:743` yanitIsle |
| `detay` | kopru.js | `kod/eklenti/kanca.js:967` detay |
| `detay-baslat` | arka.js | `kod/eklenti/kopru.js:76` komut |
| `detay-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:42` gonder · `kod/eklenti/arka.js:766` detayBittiIsle |
| `detay-onden` | kopru.js | `kod/eklenti/kanca.js:969` detayOnden |
| `detay-onden-baslat` | arka.js | `kod/eklenti/kopru.js:80` komut |
| `detay-onden-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:50` gonder · `kod/eklenti/arka.js:771` detayOndenBittiIsle |
| `detay-onden-parca` | kanca.js, kopru.js | `kod/eklenti/kopru.js:48` gonder · `kod/eklenti/arka.js:770` detayOndenParcaIsle |
| `devir` | kopru.js | `kod/eklenti/kopru.js:26` dahaYeni |
| `durum` | kopru.js | `kod/eklenti/kanca.js:43` window.postMessage · `kod/eklenti/kanca.js:974` ilet |
| `esitle` | kopru.js | `kod/eklenti/kanca.js:966` esitle |
| `esitle-baslat` | arka.js | `kod/eklenti/kopru.js:74` komut |
| `esitle-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:40` gonder · `kod/eklenti/arka.js:765` bittiIsle |
| `esitle-parca` | kanca.js, kopru.js | `kod/eklenti/kopru.js:38` gonder · `kod/eklenti/arka.js:764` parcaIsle |
| `esitle-simdi` | panel.js | `kod/eklenti/arka.js:778` esitleBaslat |
| `iletisim` | kopru.js | `kod/eklenti/kanca.js:968` iletisimOku |
| `iletisim-baslat` | arka.js | `kod/eklenti/kopru.js:78` komut |
| `iletisim-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:46` gonder · `kod/eklenti/arka.js:769` iletisimBittiIsle |
| `iletisim-parca` | kanca.js, kopru.js | `kod/eklenti/kopru.js:44` gonder · `kod/eklenti/arka.js:768` iletisimParcaIsle |
| `kanca-durum` | kanca.js | `kod/eklenti/kopru.js:35` gonder |
| `kanca-eski` | kopru.js | `kod/eklenti/arka.js:759` chrome.storage.session.get |
| `kayit` | kanca.js, kopru.js | `kod/eklenti/kopru.js:61` gonder · `kod/eklenti/arka.js:772` kayitEkle |
| `kayit-modu` | kopru.js | `kod/eklenti/kanca.js:970` satır içi |
| `kimlik` | kanca.js, kopru.js | `kod/eklenti/kopru.js:57` gonder · `kod/eklenti/arka.js:774` kimlikIsle |
| `konum-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:65` gonder · `kod/eklenti/arka.js:776` konumBittiIsle |
| `konum-oku` | kopru.js | `kod/eklenti/kanca.js:973` konumOku |
| `konum-oku-baslat` | arka.js | `kod/eklenti/kopru.js:86` komut |
| `konum-yanit` | kanca.js, kopru.js | `kod/eklenti/kopru.js:63` gonder · `kod/eklenti/arka.js:777` konumYanitIsle |
| `liste-yakalandi` | kanca.js, kopru.js | `kod/eklenti/kopru.js:33` gonder · `kod/eklenti/arka.js:744` chrome.storage.session.get |
| `neden-oku` | kopru.js | `kod/eklenti/kanca.js:972` nedenOku |
| `neden-oku-baslat` | arka.js | `kod/eklenti/kopru.js:84` komut |
| `oturum-bitti` | kanca.js, kopru.js | `kod/eklenti/kopru.js:59` gonder · `kod/eklenti/arka.js:775` oturumBittiIsle |
| `sayfa-acildi` | kopru.js | `kod/eklenti/arka.js:753` chrome.storage.session.get |
| `tani` | kanca.js, kopru.js | `kod/eklenti/kopru.js:55` gonder · `kod/eklenti/arka.js:773` taniGonder |
| `yanit` | kanca.js | `kod/eklenti/kopru.js:31` gonder |
| `yaz` | kopru.js | `kod/eklenti/kanca.js:971` yaz |
| `yaz-baslat` | arka.js | `kod/eklenti/kopru.js:82` komut |
| `yaz-sonuc` | kanca.js, kopru.js | `kod/eklenti/kopru.js:52` gonder · `kod/eklenti/arka.js:767` yazSonucIsle |

### Uçlar: 223 (tam liste [`HARITA_UCLAR.md`](HARITA_UCLAR.md))

| Dosya | Uç | Yol önekleri |
|---|---|---|
| `kod/operasyon/v2/api.py` | 115 | /api/aktarim /api/boss /api/dagitim /api/ilceler /api/isler /api/islerim /api/kesinti /api/mahalleler … |
| `kod/saha/yonetim_uclari.py` | 37 | /api/ayar /api/bina /api/binalar /api/bolgeleme /api/kalite /api/ticket /api/veri |
| `kod/saha/ekip_uclari.py` | 15 | /api/ayar /api/kullanici |
| `kod/saha/satis_uclari.py` | 13 | /api/bina /api/dosya /api/gorev /api/harita /api/ozet /api/yollar /api/ziyaret |
| `kod/saha/api.py` | 11 | /api/is-emri /api/saglik |
| `kod/saha/admin_uclari.py` | 8 | /api/admin |
| `kod/saha/boss_giris.py` | 6 | /api/giris /api/oturum /boss-giris/{istek_id} |
| `kod/saha/tablolar_uclari.py` | 4 | /api/tablolar |
| `kod/saha/ek_dosya.py` | 4 | /api/ticket |
| `kod/saha/giris_uclari.py` | 3 | /api/ben /api/giris /api/pin |
| `kod/saha/onemap_esitle.py` | 3 | /api/onemap |
| `kod/operasyon/v2/rut_api.py` | 3 | /api/rut |
| `kod/saha/arama_uclari.py` | 1 | /api/ara |
<!-- OTOMATIK:BITIR -->
