# İş emri akışı v2 — Yapım sözleşmesi (BUILD SPEC)

*Dehanet EÇM · Saha Sistemi · 30.09.2026 · Kapsam: `docs/GEREKSINIMLER.md` §F (F1–F22), C9 ile birlikte.*
*Bu belge paralel çalışan yapım ajanlarının **tek sözleşmesidir**. Tasarım belgeleri (`docs/tasarim/v2_*.md`) yalnız gerekçe
içindir; çelişkide bu belge kazanır. Bu belgede kişisel veri yoktur; sayılar yalnız toplamdır.*

> **Yollar değişti (01.10.2026, depo toparlama).** Bu belgedeki eski yollar şöyle okunur — tek kaynak `kod/yollar.py`:
>
> | Eski yol | Yeni yol |
> |---|---|
> | `saha/` · `operasyon/` · `dsale/` · `lisans/` · `eklenti/` · `masaustu/` | `kod/saha/` · `kod/operasyon/` · `kod/dsale/` · `kod/lisans/` · `kod/eklenti/` · `kod/masaustu/` |
> | `saha_app/` · `app/` · `scripts/` + `bolge.py` | `kod/arayuz/` · `kod/sunum/` · `kod/araclar/` |
> | `data/` · `outputs/` · `docs/` | `veri/` · `cikti/` · `belgeler/` |
> | `saha/saha.db*` · `gizli.key` · `yedek/` · `kayit/` · `ek/` · `operasyon/obekler.json` · `operasyon/veri/` · `data/raw/gelen/` | çalışma klasörü (`SAHA_VERI_DIZINI`; geliştirmede `gelistirme/veri/`, canlıda `canli/veri/`) altında `saha/…` · `operasyon/…` · `gelen/` |
> | `python -m saha.…` · `pytest saha/testler` | `PYTHONPATH=kod` ile aynı komut · kökte `pytest` (`pytest.ini`: `pythonpath = kod`) |

---

## 0. Belgenin kullanımı

### 0.1 Sentez: ne nereden geldi

İki hakem farklı kazanan seçti (HIZ 85/70, SAĞLAMLIK 74/85, SADELİK 79/77). Ortalamada önde olan ve canlı veriyi en güvenli
ele alan **SAĞLAMLIK omurgadır** (veri modeli, göç, içe aktarım hattı, yetki, durum makinesi). Üzerine şunlar aşılandı:

| Kaynak | Alınan parça | Bu belgede |
|---|---|---|
| SAĞLAMLIK (omurga) | 12 durum + 4 kova, randevu alan (durum değil), BOSS uzlaşma kuralları, giden kutusu ("BOSS'a işlenecek"), `is_no` ↔ `boss_task_no UNIQUE`, içe aktarım hattı (sha, bekçiler, diskte fark, yedek, tek işlem), sürüm kilidi, yetki matrisi testi, GERI_YUKLE/KORUNAN/kur koruması, disk kontrolü, `sema_goc` defteri, çökme testleri, köy biçimi ayrıştırma | §1, §3, §4, §5, §10 |
| SAĞLAMLIK'a hakem düzeltmeleri | (1) göç yedeği `db.gocler`'den **önce**; (2) pickle **hiç açılmaz**; (3) `saha/api.py` **tek sahip**; (4) müşteri telefonu varsayılan **kapalı**; (5) `is_emri.bina_serial` üzerinde **FK yok** | §1.2, §1.13, §8 |
| HIZ | İz tablolarında kişiye FK yok (id + ad anlık görüntüsü); O / Shift+O onayı (K çakışması giderildi); "Eşleşmemiş BOSS ekibi" çipi; hız hattı; rapor bayatlığı 30/60 dk; 15 dk ölçüsünün kapsamı; `SAHA_GOC_LIFESPAN`; zorla yüklenen eski raporda `tam_kapsam=0`; satırda öneri alanı | §1.7, §3.5, §5, §6 |
| SADELİK | Toplu atama kartı (`toplu_id` ile geri al); beş ilke; boş durumlar; ilk açılış ipucu; kelime sözlüğü; Aranacaklar tek liste; "Müşteriyle konuşuldu, saat teyitli" tek kutu; yalın aşırı yük sırası; müşteri no'nun 30 gün sonra HMAC özete dönmesi; sözleşme önce (`tipler.ts` + `sahte.ts`); bilinçli sapmalar tablosu | §3.6, §6, §7, §14 |
| Hakem 2 (D) | `db.gocler`'i çağıran bütün komut satırı araçları sürüm denetler, göç **yalnız sunucu açılışında** koşar; "eski kod + yeni DB" testi | §1.2, §10 |

Hakemlerin saydığı her boşluğun kapandığı yer **Ek A**'dadır.

### 0.2 Kapsam

| Sürüm | İçerik |
|---|---|
| **v2.0 (bu yapım)** | Dört rol + yetki matrisi; güvenli göç; iş emirleri DB'de (Task No anahtarlı, upsert, fark, geçmiş); öbek düzenleyici + Bursa/Yalova mahalle sözlüğü; İşler panosu (masaüstü + telefon), iş çekmecesi, toplu atama, Aranacaklar, Kontrol; Teknik "İşlerim" (çevrimdışı kuyruklu); Ekip (4 görev, silme, davet bir kez); Takip paneli (hız hattı, kapasite, satış bölümü); tasarım sistemi + koyu mod; 20 sn imleçli canlı yoklama |
| v2.1 | Klasör izleme (İndirilenler), uzun sorgu (`bekle>0`), "en acil 5 içinden en yakın" aday alanı (3 km / 10 km), satışçının bina ekranından "Talep aç", 3B "Açık iş emri" merceği (`geometri.py` → `acik_is[]`), kalıcı "öbeği ikiye böl" önerisi |
| Sonra (OT Faz 2–3) | FOX içe alma, SMS, kontrol grubu, kalite geri araması, VPN + HTTPS ile sahadan canlı erişim, ayrıntılı satış hedef/prim yönetimi |

### 0.3 Değişmez kurallar (bütün ajanlar)

1. Canlı `saha/saha.db`'ye **yazılmaz**; kullanıcının sunucusu (10.54.3.75:8080) durdurulmaz, yeniden başlatılmaz.
2. Kopya yalnız SQLite backup API ile alınır; kaynak `file:…?mode=ro` (yedek dosyasıysa `&immutable=1`) açılır.
3. Test sunucuları yalnız `127.0.0.1:8090–8099`'da, arka planda koşar ve iş bitince kapatılır.
4. `operasyon/obekler.json` hiçbir koşulda yazılmaz; testler `OPERASYON_OBEK` / `OPERASYON_VERI` ile kopya kullanır.
5. Git commit yok. Kullanıcı verisi silinmez.
6. Müşteri adı / numarası / adresi ve çalışan telefonları hiçbir sonuç, günlük, belge ya da test çıktısına yazılmaz; yalnız toplam.
7. Ekran görüntüleri yalnız `saha_app/qa/v2/` (gitignore'da) altına. Gerçek BOSS dosyası
   (`C:/Users/EXT03426951/Desktop/TeknikTaskDetayRaporu.xlsx`) salt okunur, yalnız 127.0.0.1 test sunucusuna yüklenir.
8. Bütün arayüz metni Türkçe (ı İ ş ğ ü ö ç), Türkçe sayı/tarih biçimi (`ortak/bicim.ts`).
9. Araçlar: `.venv/Scripts/python.exe -m pytest saha/testler operasyon/testler -q` (taban çizgisi ≈213 yeşil);
   `saha_app` içinde `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` ve `node node_modules/vite/bin/vite.js build`;
   Playwright `playwright-core` + paketli Chromium (`chromium.launch()`).
10. Var olan testlerin beklentileri **gevşetilmez**; değişen davranış yeni testle kilitlenir.

### 0.4 Beş ilke (arayüz ve sunucu)

1. **Her ekranda tek birincil eylem.** Mavi dolgu düğme yalnız odur; gerisi metin düğmesi ya da "Diğer" menüsü.
2. **Sistem bildiğini sormaz.** Rol ana ekranı seçer; öbeğin teknisyeni ve sıradaki boş dilim hazır gelir; operasyon çoğunlukla **onaylar**.
3. **Ayrıntı istenince açılır.** Satır karar için gerekeni gösterir; gerisi çekmecede (masaüstünde sağdan, telefonda tam ekran).
4. **İş merkezde, harita ikinci planda** ("Liste | Harita").
5. **Veri kaybolmaz.** Anahtar Task No; göç önce yedek alır; her değişikliğin sahibi ve saati vardır; kimse başkasının işini sessizce ezmez.

---

## 1. Veri modeli ve göç (F20)

### 1.1 İlkeler

- Göçler **yalnız ekler**. Tek istisna `kullanici` tablosunun rol CHECK'idir; o da §1.4'teki **doğrulanmış** sırayla yeniden kurulur.
- Yeni tablolarda **dar CHECK yok**. Değer listeleri Python sabitinden üretilen, düşürülüp yeniden kurulabilen tetikleyicilerle korunur.
- **İz tabloları kişiye FK taşımaz** (`kullanici_id` + `kullanici_ad` anlık görüntüsü). **İş tutan** bağlar FK'lıdır:
  `is_emri.atanan_id`, `obek.sahip_id`, `obek.yedek_id` (+ bugünkü ziyaret, görev, bina_durum, ticket…). Böylece F13'ün
  "üstünde iş olan silinmez" kuralını veritabanı zorlar, iz kaydı silmeyi engellemez.
- `is_emri.bina_serial` üzerinde **FK yok** (yanlış BOSS serial'i bütün aktarımı ROLLBACK ettirmesin; bina DB eşleşmesinden gelir,
  eşleşmezse NULL).
- `executescript` kullanılmaz (kendiliğinden commit eder). Her adım `isolation_level=None` bağlantıda tek
  `BEGIN IMMEDIATE … COMMIT`; ifadeler tek tek `execute` edilir.
- Zaman alanları `ayarlar.zaman_metni()` biçimindedir (Türkiye saati, `AAAA-AA-GG SS:DD:ss…`). Anahtar alanlar (`il_k`, `ilce_k`,
  `mahalle_k`, `ad_k`) `operasyon.is_emri.anahtar()` / `ilce_anahtari()` ile üretilir.

### 1.2 Göç çerçevesi: `saha/goc.py` (yeni, sahibi WP-A)

```python
HEDEF = 5
ADIMLAR = [   # (sürüm, ad, fonksiyon) — her fonksiyon kendi BEGIN IMMEDIATE…COMMIT'ini yapar
    (1, "kullanici_rol_dort",    goc_1_rol),          # §1.4 — tek yeniden kurma (doğrulanmış SQL)
    (2, "kullanici_ek_sutunlar", goc_2_ek_sutun),     # §1.5 — ALTER ADD
    (3, "obek_ve_mahalle",       goc_3_obek),         # §1.6 — tablolar + ilçe/mahalle tohumu + obekler.json aktarımı
    (4, "is_emri_tablolari",     goc_4_is_emri),      # §1.7 — tablolar + tetikleyiciler + ayar varsayılanları
    (5, "indeks_onarim",         goc_5_indeks),       # §1.8 — eski göçte kaybolan ziyaret indeksleri
]

class GocHatasi(Exception): ...          # .mesaj Türkçe, .yedek_yolu

@dataclass
class GocRaporu:
    bos: bool                            # yapılacak iş yoktu (ikinci açılış)
    eski_surum: int; yeni_surum: int
    yedek_yolu: str | None
    sayilar: dict[str, int]              # yalnız toplamlar: kullanici, ziyaret, bina, obek, obek_mahalle, mahalle
    satirlar: list[str]                  # konsola yazılacak Türkçe satırlar

def bekleyen(conn) -> list[str]            # db.bekleyen_gocler(conn) + user_version < HEDEF adımları
def hazirla(yol: Path, *, yedek: bool = True) -> GocRaporu
def surum_dogrula(conn) -> None            # user_version != HEDEF ise SurumUyumsuz (Türkçe)
def main(argv) -> int                      # python -m saha.goc --db <yol>  (prova ve elle kullanım)
```

`hazirla(yol)` sırası (**sıra sözleşmedir**):

1. **Kilit:** `yol.with_name(yol.name + ".goc.kilit")` dosyası `os.open(O_CREAT|O_EXCL|O_WRONLY)` ile alınır; içine pid + zaman yazılır.
   Kilit 10 dakikadan eskiyse bayat sayılır, silinip yeniden alınır. Alınamazsa `GocHatasi("Başka bir güncelleme sürüyor.")`.
2. `conn = sqlite3.connect(yol, isolation_level=None, timeout=30)`; `PRAGMA busy_timeout=30000`.
3. **Bekleyen var mı?** `db.bekleyen_gocler(conn)` (bugünkü `gocler`'in **yan etkisiz** tespit hâli: eksik sütun/tablo, ziyaret UNIQUE)
   ∪ `ADIMLAR` içinde `sürüm > PRAGMA user_version` olanlar. İkisi de boşsa `GocRaporu(bos=True)` döner; **yedek alınmaz**.
4. **Disk:** boş yer < 2,5 × (db + wal) boyutu → `GocHatasi("Diskte yer yok: … MB gerekli. Veritabanına dokunulmadı.")`.
5. **Yedek (doğrulanmış):** `yedekle.goc_yedegi(yol, eski=user_version, yeni=HEDEF)` (§1.3). Başarısızsa `GocHatasi`; **göç başlamaz**.
6. `db.gocler(conn)` — bugünkü yalnız-ekleyen adımlar (yedekten **sonra**). Ziyaret yeniden kurması §1.9'daki güvenli desene çevrilmiştir.
7. Bekleyen her adım sırayla; her biri `sema_goc` satırı yazar ve `PRAGMA user_version = N` ile biter (işlemin içinde; ROLLBACK'te geri alınır).
8. **Son kontrol:** `PRAGMA integrity_check = 'ok'`, `PRAGMA foreign_key_check` 0 satır, `foreign_keys=ON`. Tutmazsa `GocHatasi`
   (yedek yolu mesajda).
9. `ayar('son_goc')` = rapor JSON'u (yalnız toplam); kilit bırakılır.

**Çağrıldığı tek yer — `saha/sunucu.py:main` yeni sırası:**

1. `port_dolu_mu(port)` → doluysa bugünkü "ZATEN ÇALIŞIYOR" metni, `return 2`. **Veritabanına dokunulmaz.**
2. `_veritabani_kontrol()` (bugünkü: dosya var mı, bina > 0) — **göç çağrısı buradan kaldırılır**.
3. `goc.hazirla(db.db_yolu())` → `GocHatasi` yakalanır, konsola çerçeveli Türkçe yazılır, `return 3`. Sunucu **açılmaz**:
   ```
   ==============================================================
     GÜNCELLEME DURDU — veritabanı DEĞİŞMEDİ.
     Neden: kullanıcı tablosunda tanınmayan görev 'x' (2 kişi).
     Yedek: saha\yedek\goc\saha-oncesi-v0-v5-20260930-1930.db
     Eski sürümle devam etmek için önceki klasörü çalıştırın ya da
     bu ekranın fotoğrafını BT'ye gönderin.
   ==============================================================
   ```
4. Başarılıysa rapor satırları yazılır (yalnız sayı):
   `GÜNCELLEME TAMAM (v0 → v5) · 10 kişi (2 PIN) · 1.257 ziyaret · 19.706 bina aynen korundu · 14 öbek / 120 mahalle aktarıldı · yedek: saha\yedek\goc\…`
5. `--workers` yoktur; tek uvicorn süreci. (Bellek önbellekleri, süreç kilitleri buna dayanır.)

**`saha/api.py` lifespan (`_veritabanini_hazirla`):** göç **yapmaz**. `SAHA_GOC_LIFESPAN=1` ise (yalnız testler ve
`uvicorn saha.api:app` ile geliştirme) `goc.hazirla(db.db_yolu(), yedek=False)` çağırır; değilse `goc.surum_dogrula` —
uyumsuzsa `GUNCELLEME_BEKLIYOR=True` olur, bütün v2 uçları 503 `guncelleme_bekliyor` ("Sunucu güncellenmeyi bekliyor. BASLAT.bat ile
yeniden açın.") döner, eski uçlar çalışır. Göç hatası **yutulmaz** (bugünkü `api.py:1888` davranışı kalkar). `veri_kalitesi.hazirla`
ve `altlik.csp_tazele` aynen kalır.

**Ağır modüller:** arka plandaki `_agir_modulleri_isit` iş parçacığı **kaldırılır**; `dsale.metrics`, `dsale.partition`, `shapely`
lifespan içinde `yield`'den **önce, eşzamanlı** içe alınır (≈3 sn). Başarısızsa günlüğe yazılır, sunucu açılır, ilgili uç Türkçe hata verir.

**Komut satırı araçları (`db.gocler` çağıranlar):** `ticket_aktar.py`, `veri_araci.py`, `demo_temizle.py`, `demo.py`, `kur.py`
(`semayi_kur` üzerinden). Hepsi `db.gocler(...)` / `db.semayi_kur(...)` yerine:

```python
db.semayi_kur(conn)   # YENİ davranış: dosya boşsa (kullanici tablosu yoksa) SEMA + SEMA_V2 kurar, user_version=HEDEF,
                      # tohum (§1.6) yapar. Doluysa: goc.surum_dogrula(conn) — eskiyse DURUR:
                      # "Veritabanı eski sürümde (v0). Önce sunucuyu yeni sürümle açın (BASLAT.bat); güncelleme orada yapılır."
                      # yeniyse DURUR: "Bu araç veritabanından eski. Yeni sürüm klasöründen çalıştırın."
```

`simulasyon.py` geçici kopyada çalıştığı için `goc.hazirla(kopya, yedek=False)` çağırabilir (hedef canlı yol ise reddeder).

### 1.3 Göç öncesi yedek: `saha/yedekle.py`

```python
def goc_yedegi(kaynak: Path, eski: int, yeni: int, etiket: str = "oncesi") -> Path
def aktarim_yedegi(kaynak: Path) -> Path
def saklama_uygula(kaynak: Path) -> dict        # §1.12
```

- Hedef klasör **veritabanının yanındadır**: `kaynak.parent / "yedek" / "goc"` (canlıda `saha\yedek\goc\`). Ad:
  `saha-{etiket}-v{eski}-v{yeni}-{AAAAAGG-SSDDss}.db` (göçte `etiket='oncesi'`; `kur --sifirla` ve `demo_temizle` aynı işlevi
  `etiket='sifirla'` / `'demo-temizle'`, `eski=yeni=user_version` ile çağırır). Günlük `saha-AAAA-AA-GG.db` dosyasının **üzerine yazmaz**; `eskileri_sil`
  bu alt klasöre girmez (bugün de yalnız `yedek/saha-*.db` desenini tarar).
- Yöntem: `sqlite3.connect(f"file:{kaynak}?mode=ro", uri=True)` + `backup()` → `.yaziliyor` geçici dosya.
- Doğrulama (hepsi tutmazsa istisna, geçici dosya silinir, **göç yok**):
  `PRAGMA integrity_check = 'ok'`; her tablonun `COUNT(*)`'ı kaynakla aynı; `kullanici` 10 sütun özeti (§1.4) aynı.
- Kopyada `PRAGMA journal_mode=DELETE` (kapanınca -wal/-shm kalmaz), sonra `os.replace` ile asıl ada, sonra
  `os.chmod(yol, stat.S_IREAD)` (salt okunur).
- `aktarim_yedegi`: aynı yöntem, `yedek/aktarim/saha-aktarim-{AAAAAGG-SSDDss}.db`, doğrulama yalnız `integrity_check` + satır sayısı,
  hedef < 1 sn (bugünkü DB ≈21 MB).

### 1.4 v1 — `kullanici` rol CHECK'inin genişletilmesi (**doğrulanmış SQL, birebir**)

Tespit: `SELECT sql FROM sqlite_master WHERE type='table' AND name='kullanici'` metninde `'operasyon'` **yoksa** çalışır
(CHECK'siz eski tablo da buraya girer). Yeni tanım bir sabitten (`saha/sema_v2.py: KULLANICI_TANIMI_10`) gelir; eski SQL'in metin
değişimiyle **üretilmez**.

```sql
-- Python: conn.isolation_level = None
PRAGMA foreign_keys = OFF;                 -- işlem DIŞINDA (işlem içinde etkisiz)
BEGIN IMMEDIATE;
-- ÖNCE (Python):
--   n0 = SELECT COUNT(*) FROM kullanici
--   h0 = sha256( json(satır) for satır in SELECT id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma
--                                            FROM kullanici ORDER BY id )
--   s0 = SELECT seq FROM sqlite_sequence WHERE name='kullanici'        -- canlıda 19
--   d0 = {tablo: COUNT(*)} (kullanici hariç bütün tablolar)
--   x0 = SELECT type,name,sql FROM sqlite_master WHERE tbl_name='kullanici'
--          AND name NOT LIKE 'sqlite_autoindex%' AND type IN ('index','trigger')   -- canlıda boş
CREATE TABLE IF NOT EXISTS sema_goc (surum INTEGER PRIMARY KEY, ad TEXT NOT NULL, baslama TEXT NOT NULL,
                                     bitis TEXT NOT NULL, yedek_yolu TEXT, ozet TEXT);
CREATE TABLE kullanici_yeni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    telefon TEXT NOT NULL UNIQUE,
    pin_hash TEXT,
    davet_kodu TEXT,
    rol TEXT NOT NULL CHECK (rol IN ('satisci','operasyon','teknik','yonetici')),
    bolge INTEGER,
    aktif INTEGER NOT NULL DEFAULT 1,
    oturum_no INTEGER NOT NULL DEFAULT 1,
    olusturma TEXT NOT NULL
);
INSERT INTO kullanici_yeni (id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma)
     SELECT id,ad,telefon,pin_hash,davet_kodu,rol,bolge,aktif,oturum_no,olusturma FROM kullanici;
     -- tanınmayan rol → CHECK hatası → ROLLBACK + GocHatasi("tanınmayan görev 'x' (n kişi)")
DROP TABLE kullanici;                      -- ÖNCE yeni kurulur, SONRA eski düşürülür
ALTER TABLE kullanici_yeni RENAME TO kullanici;
-- x0'daki index/trigger nesneleri varsa aynı SQL ile yeniden kurulur (bugün yok)
UPDATE sqlite_sequence SET seq = MAX(seq, :s0) WHERE name = 'kullanici';
-- Python: changes()==0 ve s0 NULL değilse → INSERT INTO sqlite_sequence(name, seq) VALUES ('kullanici', :s0)
-- DOĞRULAMA (biri tutmazsa ROLLBACK + GocHatasi):
--   COUNT(*) = n0 ; özet = h0 ; seq >= s0 ; diğer tablolar = d0
--   PRAGMA foreign_key_check → 0 satır
--   SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_eski%' OR sql LIKE '%kullanici_yeni%' → 0
--   SELECT COUNT(*) FROM sqlite_master m, pragma_foreign_key_list(m.name) p
--      WHERE m.type='table' AND p."table" NOT IN (SELECT name FROM sqlite_master WHERE type='table') → 0
INSERT INTO sema_goc VALUES (1, 'kullanici_rol_dort', :baslama, :bitis, :yedek_yolu, :ozet_json);
PRAGMA user_version = 1;
COMMIT;
PRAGMA foreign_keys = ON;
```

**YASAK:** önce eski tabloyu yeniden adlandırmak (`ALTER TABLE kullanici RENAME TO kullanici_eski` — bugünkü `gocler` ziyaret kalıbı).
SQLite 3.50.4, kullanici'ye bakan **7 alt tablonun** REFERENCES tanımını `kullanici_eski`'ye yeniden yazar; tablo silinince her ziyaret
ve görev INSERT'i düşer. Bu, 30.09 karalama kopyasında yeniden ölçüldü (7 tablo) ve `test_goc.py::test_yasak_desen` ile kilitlenir.

`oturum_no`, `pin_hash`, `telefon`, `davet_kodu` birebir kopyalanır: açık telefonlar oturumda kalır, PIN'ler aynıdır.

### 1.5 v2 — `kullanici` ek sütunları (yalnız ALTER ADD)

```sql
BEGIN IMMEDIATE;
ALTER TABLE kullanici ADD COLUMN etiket       TEXT;     -- JSON liste: ["lider"] / ["btk","arama"]; YETKİ VERMEZ
ALTER TABLE kullanici ADD COLUMN boss_ekip    TEXT;     -- teknik: BOSS "Ekip" sütunundaki ad (eşleşme anahtarı)
ALTER TABLE kullanici ADD COLUMN kapasite     INTEGER;  -- teknik: günlük iş; NULL → ayar teknik_kapasite (15)
ALTER TABLE kullanici ADD COLUMN davet_zamani TEXT;     -- yeni davet kodunun üretildiği an (48 s geçerlilik)
ALTER TABLE kullanici ADD COLUMN oturum_neden TEXT;     -- son oturum_no artışının nedeni: pin|gorev|bolge|pasif|cihaz
INSERT INTO sema_goc VALUES (2, 'kullanici_ek_sutunlar', …);
PRAGMA user_version = 2;
COMMIT;
```

Her ALTER yalnız sütun yoksa yazılır (`PRAGMA table_info`). Taze kurulumda (`db.SEMA`) `kullanici` 15 sütunla ve 4 rollü CHECK ile
tanımlanır; `test_goc.py::test_sutun_kumesi_taze_ile_ayni` göç edilmiş ve taze tablonun sütun kümesinin aynı olduğunu doğrular.
`ayarlar.ROLLER = ("satisci", "operasyon", "teknik", "yonetici")`.

### 1.6 v3 — İlçe/mahalle sözlüğü ve öbekler

```sql
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS ilce (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, il TEXT NOT NULL, ad TEXT NOT NULL,
    lat REAL, lon REAL, PRIMARY KEY (il_k, ilce_k));
CREATE TABLE IF NOT EXISTS ilce_esad (             -- 'M.Kemalpaşa' → MUSTAFAKEMALPASA, 'Yalova Merkez' → MERKEZ
    il_k TEXT NOT NULL, esad_k TEXT NOT NULL, ilce_k TEXT NOT NULL, PRIMARY KEY (il_k, esad_k));
CREATE TABLE IF NOT EXISTS mahalle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    il TEXT NOT NULL, ilce TEXT NOT NULL, ad TEXT NOT NULL,             -- görünen
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,  -- anahtar
    lat REAL, lon REAL,
    kaynak TEXT NOT NULL,                  -- resmi | liste | bina | obek | rapor | elle
    ekleyen_id INTEGER, ekleyen_ad TEXT,   -- iz: FK YOK
    eklenme TEXT NOT NULL,
    UNIQUE (il_k, ilce_k, mahalle_k));
CREATE TABLE IF NOT EXISTS mahalle_esad (          -- yazım farkı → asıl mahalle (TASLIMAN → TASLIMANI)
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, esad_k TEXT NOT NULL,
    mahalle_id INTEGER NOT NULL REFERENCES mahalle(id),
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, esad_k));
CREATE TABLE IF NOT EXISTS obek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    ad_k TEXT NOT NULL UNIQUE,             -- anahtar(ad); yumuşak silinince ad_k || '#' || id
    renk INTEGER NOT NULL DEFAULT 0,       -- palet 0..7 (§7.1)
    sahip_id INTEGER REFERENCES kullanici(id),   -- ev teknisyeni (iş tutan bağ)
    yedek_id INTEGER REFERENCES kullanici(id),
    aktif INTEGER NOT NULL DEFAULT 1,      -- 0 = silindi (yumuşak)
    olusturma TEXT NOT NULL, guncelleme TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS obek_mahalle (
    il_k TEXT NOT NULL, ilce_k TEXT NOT NULL, mahalle_k TEXT NOT NULL,   -- '*' = ilçenin tamamı
    obek_id INTEGER NOT NULL REFERENCES obek(id),
    ref TEXT NOT NULL,                     -- görünen, her zaman 3 parça: 'Bursa/Nilüfer/Görükle' | 'Bursa/Gürsu/*'
    ekleyen_id INTEGER, eklenme TEXT NOT NULL,
    PRIMARY KEY (il_k, ilce_k, mahalle_k));      -- bir mahalle yalnız BİR öbekte
CREATE INDEX IF NOT EXISTS ix_obek_mahalle_obek ON obek_mahalle(obek_id);
CREATE TABLE IF NOT EXISTS obek_olay (             -- yalnız eklenir; geri al buradan
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,   -- NULL = sistem; FK YOK
    tur TEXT NOT NULL,     -- json_aktarim|olustur|ad|renk|sahip|mahalle_ekle|mahalle_cikar|tasi|sil|geri_al|bol
    obek_id INTEGER,       -- FK yok (yumuşak silinen öbek de okunur)
    veri TEXT NOT NULL,    -- JSON {once, sonra}
    surum INTEGER NOT NULL,   -- işlemden SONRAKİ öbek düzeni sürümü
    toplu_id TEXT);
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_degismez BEFORE UPDATE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_obek_olay_silinmez BEFORE DELETE ON obek_olay
BEGIN SELECT RAISE(ABORT, 'obek_olay silinemez'); END;
-- tohum (aynı işlemde; aşağıda) → INSERT INTO sema_goc … ; PRAGMA user_version = 3; COMMIT;
```

**Tohum (aynı işlemde; fonksiyonları WP-B verir, WP-A'nın göç adımı çağırır):**

1. `operasyon.v2.sozluk.tohumla(conn, zaman)`:
   - `ilce`: Bursa (17) — Büyükorhan, Gemlik, Gürsu, Harmancık, İnegöl, İznik, Karacabey, Keles, Kestel, Mudanya, Mustafakemalpaşa,
     Nilüfer, Orhaneli, Orhangazi, Osmangazi, Yenişehir, Yıldırım; Yalova (6) — Altınova, Armutlu, Çınarcık, Çiftlikköy, Merkez, Termal.
     Kod sabiti `operasyon/v2/sozluk.py: ILCELER`. Merkez koordinatı `data/ref/osm_ilce.geojson` ağırlık merkezinden; bulunamazsa NULL.
   - `ilce_esad`: `M.Kemalpaşa`, `MKemalpaşa` → Mustafakemalpaşa; `Yalova Merkez` → Merkez.
   - `mahalle` (`INSERT OR IGNORE`, öncelik sırası): `data/ref/mahalle_resmi.json` varsa `resmi` → `data/ref/mahalle_listesi.json`
     (`liste`, 621) → `bina` tablosundaki farklı (il, ilçe, mahalle), koordinat = binaların ortalaması (`bina`) → öbek ref'leri (`obek`).
2. `operasyon.v2.obek.json_aktar(conn, yol, zaman)` — `obek` tablosu boşsa ve dosya varsa:
   - Yol: `OPERASYON_OBEK` ortam değişkeni, yoksa `operasyon/obekler.json`. Dosya **yalnız okunur**; önce
     `operasyon/veri/obek_yedek/obekler-oncesi-{zaman}.json` kopyası alınır (klasör gitignore'da).
   - Her ref 3 parçaya tamamlanır (2 parçalıysa il `ilce` tablosundan); anahtar `_ref_anahtari`; aynı anahtar iki öbekteyse dosyadaki
     **ilk** öbek kazanır, çakışma `obek_olay(tur='json_aktarim')` + göç raporuna yazılır.
   - Doğrulama (aynı işlemde; tutmazsa ROLLBACK): öbek sayısı = dosyadaki öbek sayısı; `obek_mahalle` + çakışma = dosyadaki ref sayısı;
     dosyadaki her ref için DB'nin çözdüğü öbek = `ie.Obekler.bul()` sonucu.
   - `ayar('obek_surumu')='1'`.
3. **Sonrası:** sunucu `obekler.json`'a **bir daha hiç yazmaz**; kaynak DB'dir. Her öbek değişikliğinden sonra okunabilir ayna
   `operasyon/veri/obek_yedek/obekler-{zaman}.json` yazılır (son 50 tutulur).

Taze kurulumda (`semayi_kur`, boş dosya) aynı iki fonksiyon çağrılır; testlerde `OPERASYON_OBEK` bir **örnek** dosyayı gösterir
(`operasyon/obekler.ornek.json`, sentetik).

### 1.7 v4 — İş emri tabloları

```sql
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS ie_aktarim (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kaynak TEXT NOT NULL DEFAULT 'boss_teknik_task',   -- ileride fox_acik | fox_aski
    yontem TEXT NOT NULL DEFAULT 'surukle',            -- surukle | komut | klasor (v2.1)
    dosya_adi TEXT NOT NULL,
    dosya_sha256 TEXT NOT NULL,
    dosya_zamani TEXT,                 -- tarayıcının File.lastModified'ı
    rapor_en_yeni TEXT,                -- dosyadaki en yeni Task Başlangıç Tarihi
    yukleyen_id INTEGER, yukleyen_ad TEXT,   -- FK YOK
    baslama TEXT NOT NULL, bitis TEXT,
    durum TEXT NOT NULL DEFAULT 'isleniyor', -- isleniyor | onay_bekliyor | uygulandi | vazgecildi | hata
    tam_kapsam INTEGER NOT NULL DEFAULT 1,   -- 0 = kısmi/eski rapor: HİÇBİR iş kapatılmaz
    satir INTEGER, cikarilan INTEGER, is_sayisi INTEGER,
    yeni INTEGER, degisen INTEGER, kaybolan INTEGER, yeniden_acilan INTEGER, degismeyen INTEGER,
    kontrol INTEGER, boss_atamasi INTEGER,
    onay_nedeni TEXT,                  -- JSON ["cok_kaybolan","eski_rapor"]
    ozet TEXT,                         -- JSON: çıkarılan task adı sayımı, uyarılar, süre (kişisel veri YOK)
    yedek_yolu TEXT,
    hata TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS ux_aktarim_sha ON ie_aktarim(dosya_sha256) WHERE durum = 'uygulandi';
CREATE INDEX IF NOT EXISTS ix_aktarim_zaman ON ie_aktarim(baslama);

CREATE TABLE IF NOT EXISTS is_emri (
    is_no TEXT PRIMARY KEY,            -- BOSS Task No (9 hane, METİN) | bayi 'B-260930-001'
    boss_task_no TEXT UNIQUE,          -- BOSS işinde = is_no; bayi işinde "BOSS Task No'yu bağla" ile dolar
    kaynak TEXT NOT NULL,              -- boss | bayi (tetikleyiciyle korunur)
    satis_kanali TEXT,                 -- ham BOSS 'Satış Kanalı'
    kanal_grubu TEXT,                  -- global | dehanet | diger_bayi | kurumsal | bos
    task_adi TEXT NOT NULL,
    serit TEXT NOT NULL,               -- BTK | SAHA | MASA | LOJISTIK
    btk_hedef_saat INTEGER,            -- 6 | 12 | 24 | NULL
    -- müşteri (KİŞİSEL VERİ; role göre döner; kapanış + 30 gün → NULL, no → yalnız özet kalır)
    musteri_no TEXT,
    musteri_ozet TEXT,                 -- HMAC-SHA256(gizli.key, musteri_no); tekrar/kötü geçmiş tespiti bununla
    musteri_adi TEXT,
    musteri_tel TEXT,                  -- ayar musteri_tel='acik' değilse HİÇ yazılmaz (varsayılan kapalı)
    adres TEXT,
    -- yer
    il TEXT, ilce TEXT, mahalle TEXT,
    il_k TEXT, ilce_k TEXT, mahalle_k TEXT,
    mahalle_kaynak TEXT,               -- lokasyon | adres | adres-yeni | adres-benzer | adres-isaretsiz | koy | elle
    mahalle_elle INTEGER NOT NULL DEFAULT 0,   -- 1: raporla ezilmez
    lokasyon TEXT,
    bina_serial TEXT,                  -- FK YOK (DB eşleşmesinden; eşleşmezse NULL)
    lat REAL, lon REAL,
    konum_kaynak TEXT,                 -- bina | site | mahalle_merkezi | ilce_merkezi | elle
    konum_yaklasik INTEGER NOT NULL DEFAULT 0,
    -- öbek
    obek_id INTEGER REFERENCES obek(id),        -- mahalleden türetilen
    obek_elle_id INTEGER REFERENCES obek(id),   -- elle (F5); doluysa türetileni ezer, raporla ezilmez
    parca TEXT, parca_tarih TEXT,
    triyaj_nedeni TEXT,                -- il_disi | mahalle_yok | obeksiz | mahalle_benzer | altyapi_supheli | NULL
    -- BOSS aynası (her aktarımda üzerine yazılır)
    boss_durum TEXT, boss_randevu_durumu TEXT, boss_randevu_bas TEXT, boss_randevu_bit TEXT,
    boss_ekip TEXT, boss_aski_nedeni TEXT, boss_sl TEXT, boss_sl_saat REAL, boss_son_aciklama TEXT,
    boss_ozet TEXT,                    -- sha1(boss_* + task_adi + adres + lokasyon + musteri alanları): "değişti mi"
    boss_bekleyen TEXT,                -- giden kutusu: 'ekip' | 'randevu' | 'ekip,randevu' | NULL
    boss_islendi TEXT,                 -- operatörün "BOSS'a işlendi" işaretlediği an
    boss_kapanmadi INTEGER NOT NULL DEFAULT 0,  -- bizde çözüldü, 2 raporda BOSS'ta hâlâ açık
    -- bizim akış
    durum TEXT NOT NULL,               -- §3.1 (tetikleyiciyle korunur)
    durum_zamani TEXT NOT NULL,
    atanan_id INTEGER REFERENCES kullanici(id), -- İŞ TUTAN BAĞ
    atama_kaynagi TEXT,                -- oneri | elle | boss | toplu
    randevu_bas TEXT, randevu_bit TEXT,
    randevu_teyitli INTEGER NOT NULL DEFAULT 0,
    oneri_teknik_id INTEGER, oneri_bas TEXT, oneri_bit TEXT, oneri_neden TEXT,   -- FK yok (öneri iz değildir)
    sira INTEGER,                      -- teknisyenin gün sırası (öneri ya da teknisyenin değişikliği)
    ticket_id INTEGER REFERENCES ticket(id),
    uyanma TEXT, askida_neden TEXT,
    evde_yok_sayisi INTEGER NOT NULL DEFAULT 0,
    masa_vade TEXT,                    -- BTK: gorulme_zamani + 45 dk
    teshis_sonucu TEXT,                -- duzeldi|simdi_evde|baska_gun|cevapsiz|kapali|yanlis_no
    kotu_gecmis INTEGER NOT NULL DEFAULT 0,
    sonuc_kodu TEXT, evde_miydi INTEGER,
    kapanis_nedeni TEXT,               -- cozuldu_dogrulandi | boss_listeden_dustu | telefonda_cozuldu | iptal | mukerrer | musteri_vazgecti
    tekrar7g INTEGER NOT NULL DEFAULT 0,
    -- saatler
    acilis TEXT NOT NULL,              -- BOSS Task Başlangıç; bayi işinde oluşturma anı
    son24 TEXT NOT NULL,               -- acilis + 24 s (söz, tavan)
    btk_hedef TEXT,                    -- acilis + btk_hedef_saat
    ilk_gorulme TEXT NOT NULL,         -- hiç değişmez
    gorulme_zamani TEXT NOT NULL,      -- bu açılış döneminde sisteme giriş; 15 dk saati buradan başlar
    ilk_atama_zamani TEXT,             -- dönemdeki ilk karar anı (atandi / ofisten çözüldü / altyapı)
    atama_zamani TEXT, teknik_gordu TEXT,
    yolda_zamani TEXT, sahada_zamani TEXT, cozum_zamani TEXT,
    son_gorulme TEXT,
    kapanis TEXT,
    kapanis_kesin INTEGER NOT NULL DEFAULT 1,  -- 0: kapanış anı = aktarım anı (üst sınır)
    acilma_sayisi INTEGER NOT NULL DEFAULT 1,
    son_aktarim_id INTEGER REFERENCES ie_aktarim(id),
    olusturan_id INTEGER, olusturan_ad TEXT,   -- FK YOK
    surum INTEGER NOT NULL DEFAULT 1,          -- yalnız operasyon alanları değişince +1 (§5.5)
    guncelleme TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_is_durum     ON is_emri(durum, son24);
CREATE INDEX IF NOT EXISTS ix_is_obek      ON is_emri(obek_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_obek_elle ON is_emri(obek_elle_id);
CREATE INDEX IF NOT EXISTS ix_is_atanan    ON is_emri(atanan_id, durum);
CREATE INDEX IF NOT EXISTS ix_is_mahalle   ON is_emri(il_k, ilce_k, mahalle_k);
CREATE INDEX IF NOT EXISTS ix_is_bina      ON is_emri(bina_serial);
CREATE INDEX IF NOT EXISTS ix_is_musteri   ON is_emri(musteri_ozet, task_adi);
CREATE INDEX IF NOT EXISTS ix_is_ticket    ON is_emri(ticket_id);
-- Değer tetikleyicileri: liste operasyon/v2/akis.py:DURUMLAR'dan üretilir; test ikisinin eşitliğini denetler
CREATE TRIGGER IF NOT EXISTS trg_is_deger_ekle BEFORE INSERT ON is_emri
WHEN NEW.durum NOT IN ('triyaj','bekliyor','randevulu','atandi','yolda','sahada',
                       'ulasilamadi','askida','altyapi','merkeze','cozuldu','kapandi')
  OR NEW.kaynak NOT IN ('boss','bayi')
BEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END;
CREATE TRIGGER IF NOT EXISTS trg_is_deger_guncelle BEFORE UPDATE OF durum, kaynak ON is_emri
WHEN NEW.durum NOT IN ('triyaj','bekliyor','randevulu','atandi','yolda','sahada',
                       'ulasilamadi','askida','altyapi','merkeze','cozuldu','kapandi')
  OR NEW.kaynak NOT IN ('boss','bayi')
BEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END;

CREATE TABLE IF NOT EXISTS is_emri_olay (          -- olay defteri: yalnız eklenir; id = canlı pano imleci
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    is_no TEXT NOT NULL REFERENCES is_emri(is_no),
    zaman TEXT NOT NULL,               -- olayın anı (çevrimdışıda cihazdaki basış anı)
    kayit_zamani TEXT NOT NULL,        -- sunucuya ulaştığı an
    kullanici_id INTEGER, kullanici_ad TEXT,   -- NULL = sistem; FK YOK
    tur TEXT NOT NULL,  -- olustu|aktarim_degisti|kayboldu|yeniden_acildi|durum|atama|randevu|oneri|ticket|obek|
                        -- mahalle|not|iletisim|teshis|uyandi|boss_islendi|boss_bagla|boss_ekip|teknik_gordu|sira|geri_al
    eski TEXT, yeni TEXT,              -- JSON {alan: değer}; kişisel veri alanlarında YALNIZ alan adı ("adres değişti")
    notu TEXT,
    aktarim_id INTEGER,
    toplu_id TEXT,                     -- toplu atama / toplu geri al
    istemci_id TEXT);                  -- telefondan gelen yazmanın tekillik anahtarı
CREATE INDEX IF NOT EXISTS ix_olay_is ON is_emri_olay(is_no, id);
CREATE INDEX IF NOT EXISTS ix_olay_toplu ON is_emri_olay(toplu_id) WHERE toplu_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_olay_istemci ON is_emri_olay(kullanici_id, istemci_id) WHERE istemci_id IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS trg_is_olay_degismez BEFORE UPDATE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_is_olay_silinmez BEFORE DELETE ON is_emri_olay
BEGIN SELECT RAISE(ABORT, 'is_emri_olay silinemez'); END;

CREATE TABLE IF NOT EXISTS erisim_kaydi (          -- müşteri bilgisi görüntüleme kaydı (KVKK)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, gun TEXT NOT NULL,
    kullanici_id INTEGER NOT NULL, kullanici_ad TEXT,   -- FK YOK
    eylem TEXT NOT NULL,               -- is_liste | is_ayrinti | kopya_musteri_no | excel | tel_goster
    is_no TEXT, adet INTEGER, ip TEXT);
CREATE INDEX IF NOT EXISTS ix_erisim ON erisim_kaydi(kullanici_id, zaman);
CREATE UNIQUE INDEX IF NOT EXISTS ux_erisim_gun ON erisim_kaydi(gun, kullanici_id, eylem, is_no) WHERE is_no IS NOT NULL;
CREATE TRIGGER IF NOT EXISTS trg_erisim_degismez BEFORE UPDATE ON erisim_kaydi
BEGIN SELECT RAISE(ABORT, 'erisim_kaydi degistirilemez'); END;
-- erisim_kaydi için silme tetikleyicisi BİLEREK yok: 2 yıllık saklama temizliği göç gerektirmesin.

CREATE TABLE IF NOT EXISTS takip_anlik (           -- her aktarımda bir satır: 7 günlük eğimler
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL, aktarim_id INTEGER,
    acik INTEGER, asan24 INTEGER, btk_asan48 INTEGER, atanmamis INTEGER, altyapi INTEGER);

CREATE TABLE IF NOT EXISTS yonetim_kaydi (         -- ekip/veri yönetimi izi (rol geçişi dönemi için)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    kullanici_id INTEGER, kullanici_ad TEXT,   -- FK YOK
    eylem TEXT NOT NULL,               -- kisi_ekle|kisi_duzenle|gorev|pin_sifirla|cihaz_cikis|davet|kisi_sil|pasif|is_aktar|
                                       -- bolge_uygula|bolge_geri_al|tur_uygula|onemap|ayar|mahalle_yukle|ticket_aktar|demo_temizle
    hedef TEXT,                        -- kullanici:<id> | plan:<id> | …
    ozet TEXT);                        -- JSON; kişisel veri değeri YOK (telefon, PIN, davet kodu yazılmaz)
CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_degismez BEFORE UPDATE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi degistirilemez'); END;
CREATE TRIGGER IF NOT EXISTS trg_yonetim_kaydi_silinmez BEFORE DELETE ON yonetim_kaydi
BEGIN SELECT RAISE(ABORT, 'yonetim_kaydi silinemez'); END;
-- ayar varsayılanları (INSERT OR IGNORE, §1.10) → sema_goc → PRAGMA user_version = 4; COMMIT;
```

### 1.8 v5 — İndeks onarımı

```sql
BEGIN IMMEDIATE;
CREATE INDEX IF NOT EXISTS ix_ziyaret_bina      ON ziyaret(bina_serial);
CREATE INDEX IF NOT EXISTS ix_ziyaret_kullanici ON ziyaret(kullanici_id, zaman);
INSERT INTO sema_goc VALUES (5, 'indeks_onarim', …);
PRAGMA user_version = 5;
COMMIT;
```

Canlıda indeksler vardır (IF NOT EXISTS etkisiz); eski şemadan göç etmiş yedeklerde kaybolmuştur.

### 1.9 `db.gocler` içindeki ziyaret yeniden kurmasının düzeltilmesi

Bugünkü kalıp (RENAME → executescript → INSERT → DROP) **atomik değildir** ve iki indeksi kaybettirir. Yeni kalıp (yalnız eski
DB'lerde koşar; canlıda koşmaz): `foreign_keys=OFF` (işlem dışında) → `BEGIN IMMEDIATE` → `CREATE TABLE ziyaret_yeni (…SEMA'daki tanım…)`
→ `INSERT … SELECT` (kesişen sütunlar) → `DROP TABLE ziyaret` → `ALTER TABLE ziyaret_yeni RENAME TO ziyaret` → üç ziyaret indeksini
`CREATE INDEX IF NOT EXISTS` ile yeniden kur → satır sayısı + `foreign_key_check` doğrula → `COMMIT` → `foreign_keys=ON`.
`db.bekleyen_gocler(conn)` aynı tespitleri yan etkisiz yapar.

### 1.10 Ayar anahtarları (`INSERT OR IGNORE INTO ayar`, v4'te)

| Anahtar | Varsayılan | Anlam |
|---|---|---|
| `obek_surumu` | `1` | Öbek düzeninin tek sürüm sayacı (§5.5) |
| `musteri_tel` | `kapali` | `acik` olmadıkça telefon alanı kabul edilmez ve döndürülmez |
| `boss_task_url` | *(boş)* | `{task_no}` içeren şablon; boşsa "BOSS'ta aç" yerine "Task No'yu kopyala" |
| `aktarim_esik` | `{"kaybolan_oran":0.25,"kaybolan_min":50}` | Eksik rapor bekçisi |
| `rapor_bayat_dk` | `{"amber":30,"kirmizi":60}` | Mesai içinde rapor tazeliği uyarısı |
| `mesai` | `08:00-20:00` | Tazelik ve dilim hesabı |
| `dilimler` | `08-10,10-12,12-14,14-16,16-18,18-20` | Randevu çipleri |
| `gun_baslangic` | `08:30` | Öneri dilimi başlangıcı |
| `teknik_kapasite` | `15` | Kişi başı günlük iş (kişide `kapasite` boşsa) |
| `kapasite_<AAAA-AA-GG>` | *(yok)* | O gün sahadaki teknik sayısı (−/+ ile girilir) |
| `filtre_istisnalari` | `["KURULUM TASKI UREMEMIS"]` | `sade()` biçiminde; çıkarma kuralından ÖNCE denetlenir (C5) |
| `pii_saklama_gun` | `30` | Kapanıştan sonra müşteri alanları |
| `ham_saklama_gun` | `7` | Ham BOSS dosyaları |
| `haftalik_satis_hedefi` | *(boş)* | Boşsa Takip'te ilerleme çubuğu gizli |
| `gorev_gozden_gecirildi` | `0` | Ekip'teki "Görevleri gözden geçirin" kartı |
| `ilk_aktarim` | *(ilk aktarımda yazılır)* | 15 dk ölçüsünün başlangıcı |

### 1.11 Bugünkü 10 kişi yeni görevlerine nasıl geçer (kimse erişim kaybetmez)

1. Göç **hiçbir kişinin rolünü değiştirmez**, tahmin yapmaz: bugün `yonetici` olan 8 kişi `yonetici`, 2 `satisci` `satisci` kalır.
   `oturum_no`, `pin_hash`, `telefon`, `davet_kodu` aynen kalır → açık telefonlar oturumda, PIN'ler aynı.
2. Güncellemeden sonra her yönetim ekranının üstünde (yalnız yöneticide) sakin bir şerit çıkar, Ekip'te kart olarak açılır:
   **"Görevler artık dört çeşit. 8 kişi 'Yönetici' görünüyor. Gerçek görevlerini seçin."** [Gözden geçir]
   Kartta rolü `yonetici` olan her kişi için dört parçalı seçici (Satış · Operasyon · Teknik · Yönetici) ve altta tek **Kaydet**.
   "Şimdilik böyle kalsın" metin düğmesi kartı kapatır (`gorev_gozden_gecirildi=1`).
3. Görevi değişen kişinin `oturum_no` +1, `oturum_neden='gorev'`. Telefonu bir kez **"Göreviniz değişti. PIN'inizle yeniden girin."**
   (401 `gorev_degisti`) der; aynı telefon + PIN ile girer ve yeni ana ekranında açılır. Kart bunu önceden yazar:
   "Bu kişiler bir kez yeniden giriş yapacak; PIN'leri aynı kalır."
4. Korumalar (sunucu, 409): kişi kendi görevini düşüremez (`kendi_rolu`), kendini pasife alamaz / silemez (`kendini_silemez`); son aktif
   yönetici düşürülemez, pasife alınamaz, silinemez (`son_yonetici`).
5. Geçiş dönemi izi: ekip ve veri yönetimi eylemlerinin hepsi `yonetim_kaydi`'na yazılır; Takip → Sistem kartında "Yönetim kaydı" açılır.
   Böylece 8 kişi hâlâ yöneticiyken yapılan PIN sıfırlama, silme, plan uygulama gibi işlemlerin sahibi ve saati görünür.
6. Davet kodları: bugün var olan kodlar (`davet_zamani` NULL) **geçerli kalır** (henüz PIN belirlememiş kişi kilitlenmez) ama listede artık
   gösterilmez. Yeni kodlar 48 saat geçerlidir ve yalnız üretildiği an bir kez gösterilir.

### 1.12 Saklama, temizlik, yedek süreleri (KVKK)

`operasyon.v2.saklama.uygula(conn, simdi)` — sunucu açılışında, her aktarımdan sonra ve `YEDEK.bat` (19:30 görevi) sonunda koşar:

| Veri | Süre | Nasıl |
|---|---|---|
| `musteri_adi`, `adres`, `musteri_tel` | Kapanış + `pii_saklama_gun` (30) | NULL |
| `musteri_no` | Kapanış + 30 gün | NULL; `musteri_ozet` (HMAC) kalır → tekrar arıza tespiti bozulmaz |
| Ham BOSS dosyası `operasyon/veri/gelen/<sha>.xlsx` | `ham_saklama_gun` (7) | Silinir |
| Fark dosyaları `operasyon/veri/gelen/<id>.fark.json` | Karar verilince ya da 1 gün | Silinir |
| `yedek/aktarim/` | Son 10 dosya | Eskiler silinir |
| `yedek/goc/` | Son 5 dosya; 90 günden eskisi yalnız daha yeni doğrulanmış bir göç yedeği varsa silinir | — |
| Günlük yedek `yedek/saha-*.db` | 30 gün (bugünkü kural, en yeni 7 hep kalır) | Değişmez |
| `erisim_kaydi` | 2 yıl | Ayrı bakım adımı (bu turda silme yok) |
| `is_emri_olay`, `obek_olay`, `yonetim_kaydi` | Süresiz | Kişisel veri değeri içermez |
| `operasyon/veri/son_yukleme.pkl` | Açılmaz, silinmez | Kullanıcı onayıyla elle silinir (açık soru) |

Sonuç: canlı tabloda müşteri verisi en çok kapanış + 30 gün, günlük yedeklerde + 30 gün daha (≈60 gün), göç yedeklerinde en çok
≈90 gün kalır. Bu süreler Takip → Sistem kartında tek satırla yazar. Yedek diskinin şifreli olması (BitLocker) BT'den teyit edilir (OT §9.2).

### 1.13 Güncellemede korunan dosyalar, geri dönüş, yeniden tohumlama koruması

- `saha/KORUNAN.txt` (yeni): güncellemenin **asla üzerine yazmadığı** yollar — `saha/saha.db*`, `saha/gizli.key` (yoksa bütün jetonlar
  düşer), `saha/yedek/**`, `saha/kayit/**`, `operasyon/obekler.json`, `operasyon/veri/**`, `data/raw/gelen/**`.
- `.gitignore`'a `operasyon/obekler.json` eklenir; yerine sentetik `operasyon/obekler.ornek.json` depoya girer.
- `saha/GERI_YUKLE.bat` (yeni): (1) port doluysa "Önce DURDUR.bat" der ve çıkar; (2) `saha\yedek\goc\` ve `saha\yedek\` içindeki
  yedekleri tarihli listeler; (3) mevcut `saha.db`'yi `saha-hatali-<zaman>.db` adıyla kenara koyar (**silmez**); (4) seçilen yedeği kopyalar,
  salt okunurluğu kaldırır, `integrity_check` çalıştırır; (5) "Önceki sürüm klasöründen BASLAT.bat ile açın" der.
- `kur.py`: hedef dosya varsa ve `kullanici` içinde `500000000x` tohum numaraları dışında kişi varsa `--sifirla` **reddedilir**:
  "Bu veritabanında gerçek kişiler var. Sıfırlamak için önce yedek alın ve --evet-gercek-kisileri-sil ekleyin." Bu bayrakla da önce
  `goc_yedegi(etiket='sifirla')` alınır. `--sifirla` olmadan dolu DB'de `kur` bina alanlarını CSV'den ezmez: "Veritabanı zaten kurulu; bina
  güncellemesi için Tur raporu ekranını kullanın." (testlerin `kur.kur(sifirla=True, yol=tmp)` çağrısı etkilenmez: dosya boştur.)
- `baslat.bat`: `saha.db` yoksa ve `saha\yedek\` içinde yedek varsa **tohumlamaz**: "Veritabanı bulunamadı. En son yedek: … Geri yüklemek için
  GERI_YUKLE.bat." Yedek de yoksa bugünkü kurulum çalışır.
- `demo_temizle.py`: çalışmadan önce `goc_yedegi(etiket='demo-temizle')` alır ve `yonetim_kaydi` yazar. **Otomatik çalışmaz**; kullanıcı kararıdır.

### 1.14 Karalama kopyasında doğrulanan sonuçlar (30.09.2026)

§1.4–§1.8'in SQL'i ve §1.6 tohumu, `saha/yedek/saha-2026-09-30.db`'nin (`mode=ro&immutable=1` ile açılıp backup API ile alınan)
karalama kopyasında denendi. Canlı `saha.db`'ye ve `obekler.json`'a dokunulmadı (JSON'un kopyası kullanıldı, sha256'sı değişmedi).

| Ölçü | Sonuç |
|---|---|
| user_version | 0 → 5 |
| kullanici | 10 satır, 10 sütun özeti birebir; `sqlite_sequence` 19 → 19; roller öncesiyle aynı (8 yönetici, 2 satışçı; 2 PIN) |
| Diğer eski tablolar | Satır sayıları birebir (bina 19.706, ziyaret 1.257, …); yalnız `ayar` +1 (`obek_surumu`) |
| Bütünlük | `integrity_check = ok`, `foreign_key_check` 0 satır; kullanici'ye bakan 13 FK'nın (10 eski + `obek.sahip_id`, `obek.yedek_id`, `is_emri.atanan_id`) hepsinin hedefi `kullanici` |
| Sütunlar | kullanici 15 sütun (10 + 5 ek) |
| CHECK | `teknik` ve `operasyon` kabul, `hacker` ret |
| Tohum | 23 ilçe; mahalle sözlüğü 663 (liste 621 + bina 6 + öbek 36); 14 öbek, 120 ref, 0 çakışma, `bul()` farkı 0 |
| Tetikleyiciler | geçersiz durum reddi; olay defteri güncellenemez/silinemez; aynı sha ikinci kez `uygulandi` olamaz |
| F13 FK | İşi (atanan_id) olan kişi silinemedi; iz tablolarında FK yok |
| Çökme | v1'de INSERT, DROP ve RENAME sonrasında istisna: üçünde de DB (şema metni + sayılar + özet + user_version) birebir aynı |
| Yasak desen | Önce eskiyi RENAME: 7 tablonun REFERENCES'ı `kullanici_eski`'ye yeniden yazıldı |

---

## 2. Roller ve yetki (F6, F12, F21)

### 2.1 Dört görev

| DB `rol` | Ekranda | Kimdir | Masaüstünde ilk ekran | Telefonda ilk ekran |
|---|---|---|---|---|
| `satisci` | **Satış** | Satış temsilcisi ("Saha") | `#/bugun` (bugünkü uygulama, değişmez) | Aynı |
| `operasyon` | **Operasyon** | Masa: atama, randevu, arama, ticket | `#/yonetici/isler` | Aynı (itmeli gezinme) |
| `teknik` | **Teknik** | Arıza teknisyeni; lider = `etiket:["lider"]` | `#/islerim` (ortada 640 px) | `#/islerim` |
| `yonetici` | **Yönetici** | Operasyon lideri, bayi müdürü | `#/yonetici/isler` (cihaz son bölümü hatırlar) | Aynı |

- `satisci` ve `yonetici` SQL'e gömülü (rapor.py:109, bolgeleme.py:469/733/743/806, demo.py, veri_araci.py, kur.py) → **yeniden adlandırılmaz**.
- C9 (girişte birim): tek birimli kişiye sorulmaz. **Yalnız yöneticiye, o cihazdaki ilk girişte bir kez** sorulur:
  "Bu cihazda nereden başlayalım?" → **İşler** (seçili) · Takip · Satış uygulaması. Seçim `localStorage` (try/catch) ile hatırlanır,
  menünün altındaki "Başlangıç ekranı" satırından değişir.

### 2.2 İzin tablosu — `saha/yetki.py` (varsayılan: YASAK)

Tabloda olmayan eylem her rol için 403 `yasak` ("Bu bölüm görevinize kapalı."). Yetki **rolden** gelir, etiketten asla.

| Eylem | Satış | Operasyon | Teknik | Yönetici |
|---|---|---|---|---|
| `satis.kendi` — Bugün, bina listesi, harita, yollar, görev oluştur, ziyaret yaz/iptal | Kendi bölgesi | — | — | Hepsi |
| `satis.izle` — gün özeti, kapsama, rapor.xlsx, görev ata, başkasının listesi | — | — | — | ✓ |
| `bina.oku` — bina kartı, binanın ticket'ları | Kendi bölgesi | Hepsi | Yalnız kendisine atanmış **açık** işin binası | Hepsi |
| `geometri.oku` — `/api/binalar/geometri` | Kendi bölgesi | Hepsi | — | Hepsi |
| `altlik.oku`, `ticket.sablon` | ✓ | ✓ | ✓ | ✓ |
| `is.liste` — iş listesi/ayrıntı | — | Hepsi | Yalnız kendi açık işleri (+ bugün biten) | Hepsi |
| `is.musteri` — ad, no, tam adres | — | ✓ | Kendi **açık** işinde: kısa ad + no + adres | ✓ |
| `is.yukle` — rapor içe alma | — | ✓ | — | ✓ |
| `is.ata` — ata, toplu ata, öneri onayla, randevu, dağıt, BOSS ekibi eşle, BOSS'a işlendi, BOSS'a bağla | — | ✓ | — | ✓ |
| `is.duzenle` — öbeğe taşı, mahalle seç, ticket bağla, not, teşhis, askı, merkeze, ofisten kapat, yeniden aç | — | ✓ | — | ✓ |
| `is.saha` — yolda, sahada, bitti, evde yok, başka gün, not, "gördüm" | — | ✓ (düzeltme) | Kendi işinde | ✓ |
| `is.olustur` — bayi işi | — | ✓ | — | ✓ |
| `is.excel` — müşteri sütunlu Excel (kayda geçer) | — | ✓ | — | ✓ |
| `obek.oku` | — | ✓ | — | ✓ |
| `obek.duzenle`, `mahalle.ekle` | — | ✓ | — | ✓ |
| `mahalle.yukle` — resmî liste yükleme | — | — | — | ✓ |
| `ticket.defter` — liste, oluştur, güncelle, harita, Excel'den aktar | — | ✓ | — | ✓ |
| `takip.oku` — Takip (operasyon bölümleri) | — | ✓ | — | ✓ |
| `takip.tam` — Takip satış bölümü, erişim kaydı, yönetim kaydı | — | — | — | ✓ |
| `kapasite.yaz` | — | ✓ | — | ✓ |
| `ekip.teknikler` — atama için teknik listesi | — | ✓ | — | ✓ |
| `ekip.yonet` — kişi ekle/düzenle/sil, görev, PIN, davet, cihaz çıkışı, iş aktar | — | — | — | ✓ |
| `veri.yonet` — kalite, bölgeleme, tur raporu, OneMap, bina değişim, ayar, altlık yaz | — | — | — | ✓ |

```python
# saha/yetki.py (WP-A) — sözleşme
ROLLER = ("satisci", "operasyon", "teknik", "yonetici")
ETIKET = {"satisci": "Satış", "operasyon": "Operasyon", "teknik": "Teknik", "yonetici": "Yönetici"}
IZINLER: dict[str, frozenset[str]]                 # eylem → roller (yukarıdaki tablo)
ROTA_IZNI: dict[tuple[str, str], str | None]       # (yöntem, yol şablonu) → eylem; None = herkese açık (saglik, giris, pin, statik)
def izinli(k: dict, eylem: str) -> bool
def izin(*eylemler: str) -> Callable[..., dict]    # FastAPI bağımlılığı; herhangi biri yeterli; 403 'yasak'
def izin_listesi(rol: str) -> list[str]            # /api/ben.izinler — arayüz menüsü bundan çizilir
def ana_ekran(rol: str) -> str                      # 'bugun' | 'isler' | 'islerim'
def bolge_kapsami(k: dict, istenen: int | None) -> int | None   # _bolge_kontrol'ün yerine (§2.4)
def bina_gorebilir(conn, k: dict, bina_serial: str) -> bool
def ziyaret_yazabilir(conn, k: dict, bina_serial: str) -> bool
```

`yonetici()` bağımlılığı kalır ama yalnız `veri.yonet` / `ekip.yonet` anlamında kullanılır; başka her uç kendi eylemini ister.

### 2.3 Var olan uçların yeni izni

| Uç | Bugün | v2 eylemi |
|---|---|---|
| `GET /api/saglik`, `POST /api/giris`, `POST /api/pin` | açık | açık (None) |
| `GET /api/ben` | giriş | giriş (rol dalı, §5.3.1) |
| `GET /api/gorev/bugun` | giriş | `satis.kendi` (başkasınınki `satis.izle`) |
| `POST /api/gorev/olustur` | satışçı | `satis.kendi` (bölgesizse 400 `bolge_yok`, bugünkü gibi) |
| `POST /api/gorev/ata` | yönetici | `satis.izle` |
| `POST /api/ziyaret`, `/toplu`, `/{id}/iptal` | giriş | `satis.kendi` + `ziyaret_yazabilir` |
| `GET /api/bina`, `/api/harita`, `/api/yollar` | giriş | `satis.kendi` + `bolge_kapsami` |
| `GET /api/bina/{serial}` | giriş | `bina.oku` + `bina_gorebilir` |
| `GET /api/ozet/gun`, `/api/ozet/kapsama`, `/api/dosya/rapor.xlsx` | yönetici / giriş | `satis.izle` |
| `GET/POST /api/kullanici`, `/pin-sifirla`, `/cihaz-cikis` | yönetici | `ekip.yonet` |
| `GET/POST /api/ayar` | yönetici | `veri.yonet` (GET yardım telefonu: giriş) |
| `/api/kalite/*`, `/api/bolgeleme/*`, `/api/veri/*`, `/api/bina/{s}/degisim`, `PUT /api/ayar/altlik` | yönetici | `veri.yonet` |
| `GET /api/ticket`, `/harita`, `/{id}`, `POST/PATCH /api/ticket` | yönetici | `ticket.defter` |
| `GET /api/ticket/sablon`, `GET /api/ayar/altlik` | giriş | `ticket.sablon` / `altlik.oku` |
| `GET /api/bina/{s}/ticket` | giriş | `bina.oku` + `bina_gorebilir` |
| `GET /api/binalar/geometri` | giriş | `geometri.oku` + `bolge_kapsami` |
| `/api/is-emri/*` (pickle) | yönetici | **410 `yenilendi`**: "İş emirleri ekranı yenilendi; sayfayı yenileyin." (§4.6) |

### 2.4 Kapatılan açıklar (yeni roller eklenmeden ÖNCE)

Denetimde bölgesi NULL `teknik` hesabı 19.706 binayı gördü ve 3. bölgeye ziyaret yazdı. Düzeltme:

1. `bolge_kapsami(k, istenen)`:
   - `yonetici`, `operasyon` → `istenen` (None = hepsi).
   - `satisci` → kendi bölgesi; `istenen` başka bölgeyse 403 `baska_bolge`. **Bölgesi NULL ya da 0 ise `0` döner** → listeler boş (200),
     `/api/ben` yanıtında `bolge_yok: true` ve ekranda "Size henüz bölge atanmadı. Yöneticinize başvurun." (bugünkü
     `test_bolgesiz_satisci_sehri_goremez` davranışı korunur).
   - `teknik` ve bilinmeyen rol → 403 `yasak`.
2. `bina_detay`, `yonetim_uclari._bina_yetkili`, `_ziyaret_isle` içindeki `if rol == 'satisci'` kalıpları kalkar; yerine
   `bina_gorebilir` / `ziyaret_yazabilir` (izin listesiyle, deny-by-default). Ziyaret yazma yalnız satış (kendi bölgesi) ve yönetici.
3. `/api/ben` her rol için kendi dalını döner; bilinmeyen rol 403.
4. Global `sqlite3.IntegrityError` işleyicisi: 409 `butunluk` "Bu kayıt başka kayıtlarla bağlantılı olduğu için değiştirilemedi."
   (Disk dolu / kilit gibi diğer `sqlite3.Error` 503 `yazilamiyor` kalır.)
5. Ağır `async def` uçlar (`tur_raporu_yukle`, `onemap_yukle`) gövdeyi async okur, işi `run_in_threadpool` ile yapar; olay döngüsünde kilit tutulmaz.

### 2.5 Müşteri bilgisi (F21) — OT §6.5 ile uzlaşma

OT §6.5 "ad maskelenir, telefon tutulmaz" diyordu; F21 "operasyon müşteri bilgilerine erişebilmeli ki randevu alabilsin, ekibe
atayabilsin" diyor. v2 kullanıcının son ve açık isteğini uygular, dört güvenceyle:

1. **Rolle sınırlı, sunucuda kırpılır** (`operasyon/v2/gorunum.py` tek yer): tam ad + no + tam adres yalnız operasyon ve yöneticiye;
   teknik yalnız kendisine atanmış **açık** işte kısa ad ("Ayşe K.") + no + adres (zil ve BOSS Mobil araması için); satış hiçbirini
   görmez. Yetkisiz yanıtta anahtar **hiç yoktur** (null değil).
2. **Kayıtlı:** liste yanıtı (müşteri alanı döndüyse) tek satır `is_liste` (adet); iş çekmecesi `is_ayrinti` (kişi+iş+gün başına bir);
   "Müşteri No'yu kopyala" `kopya_musteri_no`; Excel `excel` (adet).
3. **Süreli:** §1.12.
4. **Telefon yok (varsayılan):** `ayar.musteri_tel='kapali'`; arama BOSS/Maya'dan yapılır, ekranda "Müşteri No'yu kopyala". `acik`
   yapılırsa yalnız operasyonun elle girdiği numara tutulur, her gösterim `tel_goster` kaydı yazar.

Olay defterine kişisel veri değeri yazılmaz ("adres değişti"). Çıkışta ve 401'de telefonda IndexedDB + service worker önbelleğindeki
müşteri alanları silinir (§6.9).

---

## 3. İş emrinin hayatı (F7–F10, F17)

### 3.1 Durumlar ve kovalar

Kodlar KARMA-2'nin S0–S6 / E1–E6 kodlarıyla eşleşir. Ekranda 12 durum **dört kovada** görünür.

| Kod (DB) | Ekranda | Kova | KARMA-2 | Sahibi | Süre bütçesi |
|---|---|---|---|---|---|
| `triyaj` | Kontrol gerekli | **Atanmadı** | S1 (bağlanamadı) | Operasyon | ≤15 dk |
| `bekliyor` | Atanmadı | **Atanmadı** | S1 | Operasyon | **≤15 dk** (gelişten ilk karara) |
| `randevulu` | Randevu verildi | **Atanmadı** | S2 öncesi | Operasyon | Atama dilimden önce |
| `atandi` | Atandı | **Teknikte** | S2 | Teknik | Kesim kuralı (OT §3.3) |
| `yolda` | Yolda | **Teknikte** | S3 | Teknik | ≤60 dk / BTK ≤45 |
| `sahada` | Sahada | **Teknikte** | S4 | Teknik | ≤120 dk / BTK ≤90 |
| `ulasilamadi` | Ulaşılamadı | **Beklemede** | E1 | Operasyon (merdiven) | BTK 24 s, diğer 48 s |
| `askida` | Askıda | **Beklemede** | E2 / E4 | Operasyon | Uyanma zorunlu: BTK ≤1 g, diğer ≤3 g, müşteri talepli ≤7 g, malzeme 8 s (BTK 2 s) |
| `altyapi` | Altyapı bekliyor | **Beklemede** | E3 | Operasyon + ticket | Ticket'a bağlı |
| `merkeze` | Merkeze gönderildi | **Beklemede** | E3 / BOSS | Operasyon | BOSS'a bağlı |
| `cozuldu` | Çözüldü | **Biten** | S5 / E5 | Sistem (BOSS teyidi) | Sonraki rapor |
| `kapandi` | Kapandı | **Biten** | S6 | Sistem | — |

"Açık" = `kapandi` ve `cozuldu` dışındaki her durum.

### 3.2 Bayraklar (durumdan bağımsız, satırda rozet)

| Bayrak / alan | Rozet | Anlam |
|---|---|---|
| `serit='BTK'` | **BTK** | Bağlantı / Arama (12 s), TV+ (6 s), Doping (24 s); sıra anahtarı `btk_hedef` |
| `ticket_id` ya da binada açık ticket | **Ticket** | Bina `ticket.bina_serial` = `is_emri.bina_serial`, durum AÇIK / HATA / TRANSFER |
| `tekrar7g` | **Tekrar** | Aynı `musteri_ozet` + `task_adi` 7 gün içinde kapanmış işte; telefonda kapatma yasak (kural 13) |
| `kaynak='bayi'` / `kanal_grubu` | **Bayi** / **Global** | F16 (§3.8); `bos` → rozet yok, süzgeçte "Kanal bilinmiyor" |
| `konum_yaklasik` | ◌ **Konum yaklaşık** | Bina değil, mahalle/ilçe merkezi; alarm değil, sessiz bilgi |
| `boss_bekleyen` | **BOSS'a işlenecek** | Giden kutusu (§3.4-4) |
| `boss_kapanmadi` | **BOSS'ta açık** | Bizde çözüldü, 2 raporda BOSS'ta hâlâ açık |
| `acilma_sayisi>1` | **Yeniden açıldı** | Kapanmış iş raporda yeniden göründü |
| `obek_elle_id` | **elle** | Öbek elle verildi (F5) |
| `kotu_gecmis` | (gri satır) | Önceki işinde ulaşılamadı; BTK teşhis araması yapılmaz (kural 14) |

### 3.3 Geçişler (tablo dışı her geçiş 409 `gecersiz_gecis`)

Mesaj biçimi: "Bu iş 'Çözüldü' durumunda; 'Yolda' yapılamaz." Her geçiş tek işlemde: `is_emri` güncellenir (`surum+1`),
`is_emri_olay` satırı yazılır, ilgili zaman damgası dolar.

| # | Nereden | Nereye | Kim | Tetik (düğme) | Zorunlu / kural | Damga |
|---|---|---|---|---|---|---|
| 1 | (yok) | §3.4 kurallarıyla | Sistem | Rapor içe aktarımı | — | `ilk_gorulme`, `gorulme_zamani` |
| 2 | (yok) | `triyaj` / `bekliyor` | Operasyon, Yönetici | "+ Yeni iş" | task_adi; bina ya da adres+mahalle | aynı |
| 3 | `triyaj` | `bekliyor` | Operasyon; Sistem (öbek/mahalle sonradan eklendi) | "Öbeğe ata" / "Mahalleyi seç" | öbek belli olmalı | — |
| 4 | `bekliyor`, `triyaj` | `randevulu` | Operasyon | "Randevu ver" (teknisyensiz) | randevu_bas/bit | — |
| 5 | `bekliyor`, `randevulu`, `triyaj`, `askida`, `merkeze` | `atandi` | Operasyon (tek / toplu / öneri onayı); Sistem (BOSS Ekip eşleşti) | "Ata", "Tekniğe ata", **O**, **Shift+O**, toplu kart | teknik (aktif, rol `teknik`); randevu isteğe bağlı (yoksa öneri dilimi yazılır) | `atama_zamani`, `ilk_atama_zamani` (dönemde ilkse) |
| 6 | `ulasilamadi` | `atandi` | Operasyon | "Yeniden ata" | **`randevu_teyitli=1` zorunlu** — aynı işe habersiz ikinci gidiş yok (kural 8) | `atama_zamani` |
| 7 | `atandi` | `atandi` | Operasyon; Teknik (yalnız "Başka gün": kendi işinde yeni dilim, teyitli) | "Başka tekniğe ver", "Randevuyu değiştir" | — | `atama_zamani` |
| 8 | `atandi` | `yolda` | Teknik (kendi), Operasyon, Sistem (BOSS "Konum Paylaşıldı") | "Yola çıktım" | — | `yolda_zamani` |
| 9 | `atandi`, `yolda` | `sahada` | Teknik, Operasyon, Sistem (BOSS "Başlandı") | "İşe başladım" | — | `sahada_zamani` |
| 10 | `atandi`, `yolda`, `sahada` | `cozuldu` | Teknik | "Bitti" → "Çözüldü" / "Cihaz değişti" | **`evde_miydi` zorunlu** (kural 17), `sonuc_kodu` | `cozum_zamani` |
| 10a | `atandi`, `yolda`, `sahada` | `askida` | Teknik | "Bitti" → "Malzeme gerekiyor" | evde_miydi; uyanma = +8 s (BTK +2 s) | — |
| 10b | `atandi`, `yolda`, `sahada` | `triyaj` (`altyapi_supheli`) | Teknik | "Bitti" → "Altyapı sorunu" | evde_miydi; not | — |
| 11 | açık | `cozuldu` | Operasyon | "Ofisten kapat" / Aranacaklar "Düzeldi" | neden ∈ `telefonda_cozuldu` (canlı test onayı zorunlu; `tekrar7g` işinde **409 `tekrar_ariza`**), `iptal`, `mukerrer`, `musteri_vazgecti`. Bağlanmamış bayi işi → doğrudan `kapandi` (`kapanis_kesin=1`) | `cozum_zamani`, `ilk_atama_zamani` (ilkse) |
| 12 | `atandi`, `yolda`, `sahada` | `ulasilamadi` | Teknik ("Evde yok"), Operasyon | "Evde yok" | onay kutusu "10 dk bekledim, BOSS'tan 2 kez aradım, not bıraktım"; `evde_yok_sayisi+1`, `uyanma=şimdi` | — |
| 13 | `ulasilamadi` | `randevulu` | Operasyon (Aranacaklar "Başka gün") | teşhis sonucu | dilim, teyitli | — |
| 14 | açık | `askida` | Operasyon; Sistem (BOSS "Askıya alındı") | "Askıya al" | neden + uyanma (üst sınırlar §3.1); sistemde uyanma yoksa NULL → hijyen "Askıda, uyanma yok" | — |
| 15 | `askida` | `bekliyor` | Sistem (uyanma geldi → olay `uyandi`, Aranacaklar bant 3); Operasyon "Uyandır" | — | — | — |
| 16 | açık | `altyapi` | Operasyon ("Ticket'a bağla", "Teknisyen gönderilmesin" açık); Sistem (yeni gelen işin binasında açık SİNYAL/EK SP/GÜZERGAH/ALTYAPI ticket'ı varsa otomatik bağlanır — kural 11) | — | `ticket_id` zorunlu | `ilk_atama_zamani` (ilkse) |
| 17 | `altyapi` | `bekliyor` | Sistem (ticket ÇÖZÜLDÜ / KAPATILDI / İPTAL); Operasyon "Ticket'tan ayır" | — | olay: "Ticket çözüldü; teyitli ziyarete döndü" | — |
| 18 | açık | `merkeze` | Operasyon; Sistem (BOSS "Merkeze gönderildi") | "Merkeze gönderildi" | neden | — |
| 19 | `merkeze` | `bekliyor` | Operasyon | "Sahaya al" | — | — |
| 20 | `cozuldu` | `atandi` | Operasyon | "Yeniden aç" | neden, teknik | `atama_zamani` |
| 21 | her durum | `kapandi` | **Yalnız sistem** | Tam raporda yok (§3.4-5) | — | `kapanis`, `kapanis_kesin=0` |
| 22 | `kapandi` | §3.4 kuralları | **Yalnız sistem** | Raporda yeniden var | `acilma_sayisi+1` | `gorulme_zamani=şimdi`, `ilk_atama_zamani=NULL` |
| — | *(son olay)* | önceki değerler | Olayı yapan kişi | Bildirimdeki "Geri al" | Sunucu 10 dk içinde, aynı kişi, iş `surum`'u o olaydan beri değişmemişse kabul eder (olay `geri_al`) | — |

`operasyon/v2/akis.py` bu tabloyu tek sabitte tutar: `GECISLER: dict[tuple[str, str], GecisKurali]`
(`roller`, `zorunlu_alanlar`, `teknik_kendi_isi: bool`). Test bütün (nereden, nereye) çiftlerini döngüyle dener.

### 3.4 BOSS ile uzlaşma (her içe aktarımda)

BOSS alanları (`boss_*`, `task_adi`, `adres`, `lokasyon`, müşteri alanları) her aktarımda üzerine yazılır; **bizim alanlarımız asla
ezilmez**: `obek_elle_id`, `mahalle_elle` (1 ise il/ilçe/mahalle/konum da), `atanan_id`, `randevu_*`, `ticket_id`, `parca`,
`musteri_tel`, notlar, teşhis, uyanma.

1. **İleri kuralı.** Sıra: `triyaj/bekliyor/randevulu` < `atandi` < `yolda` < `sahada`. BOSS "Konum Paylaşıldı" → `yolda`, "Başlandı" →
   `sahada`, yalnız bizimki daha gerideyse ve iş atanmışsa (atanmamışsa önce 3. kural). Geri gitme yok.
2. **İstisnalar.** BOSS "Askıya alındı" + bizde `triyaj/bekliyor/randevulu/atandi` → `askida` (neden = Askıya Alınma Nedeni).
   BOSS "Merkeze gönderildi" + bizde `cozuldu`/`altyapi` değil → `merkeze`. Bizde `ulasilamadi`, `altyapi`, `askida` ise bilgimiz korunur.
3. **Ekip eşleşmesi.** BOSS Ekip dolu, bizde `atanan_id` boş, Ekip adı (`anahtar()` ile) bir aktif `teknik` kişinin `boss_ekip`'iyle
   eşleşiyor → `atandi`, `atama_kaynagi='boss'` (15 dk ölçüsüne girmez), olay notu "BOSS'ta atanmış". Eşleşmezse iş olduğu durumda kalır,
   satırında "BOSS ekibi: …" (yalnız operasyon/yönetici) ve panoda **"Eşleşmemiş BOSS ekibi (k)"** çipi sayar. Bizim teknik aynı kişiyse
   `boss_islendi` doğrulanır.
4. **Giden kutusu.** Sistem Turkcell'e **yazmaz** (OT §6.1). Bizdeki atama/randevu BOSS'taki Ekip/dilimden farklıysa `boss_bekleyen`
   = `ekip` / `randevu` / ikisi. Operatör BOSS'a girip "BOSS'a işlendi" kutusunu işaretler (`boss_islendi`); sonraki raporda BOSS eşleşirse
   bayrak kalkar ve olay "BOSS'ta doğrulandı" yazılır.
5. **Listeden düşen** (yalnız `tam_kapsam=1` aktarımda): açık BOSS işi (ya da BOSS'a bağlı bayi işi) raporda yoksa `kapandi`,
   `kapanis=aktarım anı`, `kapanis_kesin=0`, `kapanis_nedeni` = bizde `cozuldu` idiyse `cozuldu_dogrulandi`, değilse `boss_listeden_dustu`.
6. **Yeniden açılan:** `kapandi` iş raporda varsa durum 1–3 kurallarıyla yeniden hesaplanır, `acilma_sayisi+1`, `kapanis=NULL`,
   `gorulme_zamani=şimdi`, `ilk_atama_zamani=NULL`; önceki teknik öneride öne alınır; olay `yeniden_acildi`.
7. **Çelişki:** bizde `cozuldu`, arka arkaya 2 raporda BOSS'ta açık → `boss_kapanmadi=1` (hijyen: "Çözüldü ama BOSS'ta açık").
8. **Tekrar:** yeni işin (`musteri_ozet`, `task_adi`) çifti son 7 günde kapanmış bir işte varsa `tekrar7g=1`.
9. **Kötü geçmiş:** aynı `musteri_ozet`'in son 30 gündeki bir işinde `evde_yok_sayisi>0` ya da teşhis `cevapsiz/kapali/yanlis_no` ise `kotu_gecmis=1`.

### 3.5 Saatler, renkler, 15 dakika ölçüsü, rapor tazeliği

| Saat | Tanım | Görünür |
|---|---|---|
| `son24` | `acilis + 24 s` (söz, tavan) | Her satırda **kalan süre** |
| `btk_hedef` | `acilis` + TV+ 6 s · Bağlantı/Arama 12 s · Doping 24 s | BTK rozeti ve iş çekmecesinde "BTK hedefi 21:40" |
| Müşteriye söz | Kesim kuralı: 00–12 gelen → aynı gün; 12–17 → ertesi 12:00; 17–24 → ertesi 17:00 | Çekmecede "Müşteriye söz: bugün 17:00'ye kadar" |
| **Atama süresi** | `ilk_atama_zamani − gorulme_zamani` | Atanmamış satırda "geleli 12 dk" (10 dk amber, 15 dk kırmızı) |
| Masa vadesi | BTK: `gorulme_zamani + 45 dk` (kötü geçmişte yok) | Aranacaklar "vade 12 dk" |
| 48 s BTK supabı | BTK ve `şimdi − acilis > 48 s` | Başlık sayacı, Takip, Aranacaklar |
| Rapor tazeliği | Son `uygulandi` aktarımın zamanı | Başlık: "Son rapor 11:38 · 12 dk önce"; mesai içinde ≥30 dk amber, ≥60 dk kırmızı + "BOSS'tan yeni raporu indirip bırakın" |

**Renk:** `oran = (şimdi − acilis) / (hedef − acilis)` (hedef = BTK'da `btk_hedef`, diğerlerinde `son24`): `<0,5` yeşil, `0,5–0,8` amber,
`≥0,8` kırmızı; aşıldıysa kalın kırmızı "Gecikti · 17 s" + saat simgesi. Renk hiçbir zaman tek başına bilgi taşımaz (yazı + simge).
İstemci saatleri dakikada bir (son 60 dk'da saniyede bir) yerelde işletir; `sunucu_zamani` ile kayma düzeltilir.

**15 dk ölçüsünün kapsamı (F17):** yalnız `acilis ≥ ayar.ilk_aktarim` olan (sistem çalışırken doğan) ve `atama_kaynagi ≠ 'boss'` işler.
Devralınan birikim 24 s ölçüsüne girer, 15 dk ölçüsüne girmez. Ayrıca **BOSS→sistem** gecikmesi (`gorulme_zamani − acilis`) ayrı adım
olarak ölçülür; rapor dışa aktarım ritmi (hedef 30 dk, OT karar 12) bunu belirler ve Takip bunu dürüstçe gösterir.

### 3.6 Sıralama, kapasite modu, öneri, dilim — `operasyon/v2/siralama.py`

**Kapasite modu** (her aktarımda ve kapasite değişince):
`talep` = açık, `serit ∈ {SAHA, BTK}`, kova Atanmadı/Teknikte ve (`son24 ≤ bugün 23:59` ya da atanmamış) işler;
`aktif` = `ayar.kapasite_<bugün>` yoksa bugün en az bir işi atanmış aktif teknik sayısı; `kapasite = Σ(kişi kapasitesi)`
(boşsa `aktif × 15`). `talep > kapasite` → **aşırı yük**. Esnek önerisi = `min(8, ⌈(talep − kapasite)/15⌉)` (kural 15).
Hiç teknik yoksa gösterge "Ekip'ten Teknik görevli kişi ekleyin." der.

**Sıra** (`sirala(isler, mod, simdi) -> list[str]`, deterministik; operasyon listesinin varsayılanı ve teknisyen sırası):
- `triyaj` işler her zaman en üstte (Atanmadı kovasında).
- **Normal mod:** BTK'lar `btk_hedef` artan; sonra diğerleri `son24` artan (en eski önce).
- **Aşırı yük (KARMA-2 kural 5'in yalın hâli):** kümeler — T: 24 saatine hâlâ yetişebilecek BTK (`son24 > şimdi`), anahtar `son24`
  (TV+ için `son24 − 2 s`); Gb: gecikmiş BTK, `acilis` artan; Gd: gecikmiş BTK dışı, `acilis` artan; Y: yetişebilecek BTK dışı, `son24`.
  Seçim i = 1, 2, …: bolluğu (`son24 − şimdi`) 90 dk'nın altına düşmüş T∪Y işi varsa o; değilse `i % 3 == 0` ve Gb doluysa Gb;
  değilse `i % 4 == 0` ve Gd doluysa Gd; değilse T; değilse Y; değilse Gb, sonra Gd.
- "En acil 5 içinden en yakın" (mesafe) v2.1'de.

**Öneri** (`oneri_hesapla(conn, is_nolar=None)`; aktarım, öbek değişikliği, atama, kapasite değişikliğinden sonra):
teknik = işin öbeğinin (`obek_elle_id` ?? `obek_id`) `sahip_id`'si (aktif, `teknik`, bugünkü yükü < kapasite) → yoksa `yedek_id` →
yoksa öneri yok ("Bu öbeğin teknisyeni yok"). Neden tek satır: "Görükle öbeğinin teknisyeni · bugün 9/15".
Binada açık ticket varsa öneri yazılmaz (kural 11). `ulasilamadi` işe öneri yazılmaz (kural 8).

**Dilim:** teknisyenin günü `ayar.dilimler` (2 saatlik, 08–20); dilim kapasitesi = `⌈kapasite / dilim sayısı⌉`. İş, `sirala` sırasıyla
teknisyenin sıradaki boş dilimine yazılır; bugünkü dilimler dolunca ertesi gün ilk dilimden devam eder (gece gelen BTK ilk dalga).
Varsayılan 11:00 damgası **yoktur** (kural 3). Randevu = müşteriye söylenecek tahmini varış; aramadan verilir; "Müşteriyle konuşuldu,
saat teyitli" kutusu yalnız konuşulduysa işaretlenir. Doğrulama: bitiş > başlangıç, pencere ≤ 4 s, başlangıç ≥ şimdi − 1 s ve
≤ şimdi + 7 gün → aksi 422 `randevu_gecersiz`.

### 3.7 Ticket bağı (F9)

- Rozet: işin binasında açık ticket varsa (bağlı olmasa da). Kaynak `ticket.bina_serial = is_emri.bina_serial`, durum AÇIK/HATA/TRANSFER.
- "Ticket bağla": aynı binanın açık ticket'larından biri ya da "Yeni ticket" (bugünkü `YeniTicketPenceresi`; bina ve konu dolu, metin hazır).
  "Teknisyen gönderilmesin" (varsayılan açık) → `altyapi`. Bir ticket'a birden çok iş bağlanabilir; bir işin tek ticket'ı olur.
- Binada açık ticket varken bağlanmamış işe "Ata" → 409 `altyapi_engeli` ("Bu binada açık SİNYAL ticket'ı var (#12, 3 gündür).
  Teknisyen gönderilmez.") — `yine_de: true` ile geçilir.
- Ticket durumu ÇÖZÜLDÜ/KAPATILDI/İPTAL olunca (`PATCH /api/ticket/{id}` ve Excel'den aktarım sonrası) bağlı `altyapi` işleri `bekliyor`
  olur (geçiş 17): `operasyon.v2.akis.ticket_degisti(conn, ticket_id, kullanici)` çağrılır; aynı denetim her aktarımda da yapılır (kaçan olmasın).

### 3.8 Kaynak ve kanal (F16)

- `kaynak`: `boss` (rapordan) · `bayi` (bu sistemde "+ Yeni iş" ile açılan). Bayi işinin numarası `B-AAGGAA-NNN` (günlük sayaç,
  `BEGIN IMMEDIATE` içinde `MAX+1`); BOSS'un 9 haneli numarasıyla karışmaz.
- `kanal_grubu` BOSS "Satış Kanalı"ndan türetilir (`sade()` üzerinde): `GLOBAL…` → `global` (rozet **Global**); `DEHA…`/`DEHANET…` →
  `dehanet` (rozet **Bayi**); başka bayi unvanları (…ECM, …KCM, şirket) → `diger_bayi`; `TURKCELL…` → `kurumsal`; boş → `bos`
  (rozet yok, süzgeçte "Kanal bilinmiyor"). Bugün: GLOBAL 243, DEHA 37, boş 53. Eşleme tablosu `akis.KANAL_KURALLARI`'nda; kullanıcı
  teyidine kadar bu varsayılan geçerlidir.
- **BOSS'a bağlama:** bayi işi BOSS'ta açılırsa iş çekmecesinde **"BOSS Task No'yu bağla"** (9 hane). `boss_task_no` UNIQUE'tir;
  sonraki rapor **aynı satırı** günceller. Sistem otomatik birleştirmez; aktarımda aynı `musteri_ozet` + `task_adi` ile ±72 saat içinde
  tek aday BOSS işi gelirse bayi işinde öneri çipi çıkar: "BOSS'ta 4xxxxxxxx olarak açılmış olabilir. [Bağla]". Bağlanınca BOSS satırı
  (varsa) bayi satırına katılır: BOSS'tan gelen yeni satır hiç yazılmamışsa sorun yok; yazılmışsa bağlama 409 `boss_no_kullanilmis`
  döner ve "Bu Task No başka bir işte" der (elle çözülür).

---

## 4. İçe aktarım hattı (F4, F5, F18) — `operasyon/v2/aktarim.py`

Uç `def` (async değil): FastAPI iş parçacığı havuzunda çalıştırır; olay döngüsü kilitlenmez (denetimde yükleme sırasında
`/api/saglik` 3,3 sn bekliyordu; hedef <300 ms).

```
1. AL        Dosya ≤ 25 MB (413 buyuk_dosya). sha256.
             Aynı sha 'uygulandi' olarak varsa → 200 {ayni_dosya:true, aktarim_id, zaman}. HİÇBİR ŞEY YAZILMAZ.
2. KİLİTLE   Süreç kilidi threading.Lock.acquire(blocking=False); doluysa 409 aktarim_suruyor.
             ie_aktarim satırı 'isleniyor' (yukleyen_id + ad anlık görüntüsü).
3. SAKLA     Ham dosya → operasyon/veri/gelen/<sha>.xlsx (OPERASYON_VERI kökü; 7 gün).
4. OKU       ie.raporu_oku → çıkarma: önce ayar.filtre_istisnalari (C5: "Kurulum Taskı Ürememiş" KALIR), sonra C17 kuralı
             (kurulum / 2. donanım). Çıkarılan satırlar SAKLANMAZ; yalnız task adı → sayım ozet'e.
             Mahalle ve konum: Lokasyon → bina VERİTABANINDAN (ticket.lokasyondan_bina normalizasyonu: birebir · 8 haneye sıfırla ·
             baştaki sıfırsız · '-N' eksiz; pasif olmayan önce; tur raporuyla eklenen binalar dahil) → bina.mahalle esas (F4);
             yoksa adres → sözlük DB'den (mahalle + mahalle_esad + ilce_esad); köy biçimleri: "X Bbk.Mah.(Y)" ve "X (Y) Mh." → Y,
             "Y Köyü" → Y (X alt yer adı olarak nota).
             Şerit, BTK hedefi, kanal grubu, musteri_ozet (HMAC), triyaj nedeni:
               il ∉ {Bursa, Yalova} → il_disi · mahalle yok → mahalle_yok · mahalle yeni ve aynı ilçede benzer anahtar var
               (Levenshtein ≤ 2 ya da biri diğerinin öneki) → mahalle_benzer · öbek bulunamadı → obeksiz.
             'Konum yaklaşık' TRİYAJ NEDENİ DEĞİLDİR.
             Rapor tanınmazsa ('Task No', 'Task Adı', 'Adres' başlıklı sayfa yok) → 422 rapor_tanimadi
             ("Bu dosya Teknik Task Detay Raporu değil. BOSS'tan doğru raporu indirin.").
5. FARK      Anahtar boss_task_no. Kümeler: yeni · yeniden_acilan (DB'de kapandi) · degisen (boss_ozet farklı) · degismeyen ·
             kaybolan (DB'de açık, kaynak boss ya da BOSS'a bağlı bayi işi, dosyada yok).
6. BEKÇİ     kaybolan > max(kaybolan_min, açık × kaybolan_oran) → 'cok_kaybolan'
             dosya_zamani < son uygulananın dosya_zamani  ya da  rapor_en_yeni < son uygulananın rapor_en_yeni − 1 s → 'eski_rapor'
             Biri varsa: durum 'onay_bekliyor', fark diske (operasyon/veri/gelen/<id>.fark.json, kişisel veri yok: yalnız is_no ve
             sayılar), 409 onay_gerekli {aktarim_id, fark, nedenler}. Kilit bırakılır.
7. YEDEK     yedekle.aktarim_yedegi() → saha/yedek/aktarim/ (son 10). Başarısızsa 503 yedek_alinamadi, hiçbir şey yazılmaz.
8. UYGULA    TEK işlem (BEGIN IMMEDIATE; hedef < 300 ms, 437 iş):
             yeni → INSERT + olay 'olustu'; durum §3.4; açık ticket'lı binada → altyapi + ticket bağı (kural 11)
             degisen → boss_* güncelle + olay 'aktarim_degisti' {alan:[eski,yeni]} (kişisel alanlarda yalnız ad);
                       mahalle_elle=0 ise mahalle/konum yeniden çözülür; ileri kuralı; boss_bekleyen yeniden hesaplanır
             degismeyen → yalnız son_gorulme, son_aktarim_id (surum ARTMAZ)
             kaybolan → yalnız tam_kapsam=1 ise §3.4-5
             yeniden_acilan → §3.4-6
             öbek: obek_id = obek_bul(il_k, ilce_k, mahalle_k) (birebir → ilçe '*'); obek_elle_id ezilmez
             sözlük: raporda görülen yeni mahalleler kaynak 'rapor' ile eklenir
             ayar.ilk_aktarim yoksa yazılır; takip_anlik satırı; ie_aktarim 'uygulandi' + sayımlar
             COMMIT → sonra (işlem dışında) oneri_hesapla, saklama.uygula, ticket denetimi.
9. BİLDİR    200 {aktarim_id, fark:{yeni,degisen,kaybolan,yeniden_acilan,degismeyen}, cikarilan:{kurulum, ikinci_donanim,
             istisna_tutulan}, kontrol, boss_atamasi, sure_sn, yedek}
```

- **Onay:** `POST /api/aktarim/{id}/uygula {mod:'tam'|'kismi'}` 5–9'u **yeniden hesaplar** (bu arada başka değişiklik olduysa yeni fark
  döner). `eski_rapor` nedeni varsa `mod` zorla `kismi` (`tam_kapsam=0`: hiçbir iş kapatılmaz, yalnız ekler/günceller).
  `POST /api/aktarim/{id}/vazgec` → `vazgecildi`.
- **Hata:** 4 ya da 8'de istisna → ROLLBACK; ayrı işlemde `durum='hata'`, Türkçe `hata`. İşler ve öbekler **hiç değişmez**.
- **Pickle:** `operasyon/veri/son_yukleme.pkl` hiç **açılmaz** ve silinmez. `is_emri` boşken İşler ekranı: "Yeni sürüm iş emirlerini kalıcı
  saklıyor. Son raporu bir kez daha bırakın."
- **Komut satırı makrosu** (`IS_EMRI_HAZIRLA.bat` / `python -m operasyon.is_emri RAPOR.xlsx`, C16) çalışmaya devam eder: `saha/saha.db`
  varsa öbekleri oradan **salt okunur** (`mode=ro`) alır, yoksa `obekler.json`'dan. Öbek tablosu yazma kipi kapanır: "Öbekleri uygulamadaki
  Öbekler ekranından düzenleyin." Bu, yeni ekran sorun çıkarırsa `_hazir.xlsx` üretmeye devam eden **yedek yoldur**.

---

## 5. API sözleşmesi

### 5.1 Genel

- Hepsi `/api` altında, Bearer jeton. Hata biçimi bugünkü gibi: `{"hata": "<Türkçe cümle>", "kod": "<kod>"}` (+ uca özel alanlar).
- Zamanlar `ayarlar.zaman_metni()` biçiminde metin. Her liste yanıtında `sunucu_zamani`.
- Yazan her iş ucu `surum` alır; iş `UPDATE … SET …, surum=surum+1 WHERE is_no=? AND surum=?` ile yazılır; 0 satır → 409 `guncel_degil`
  + `{guncel: IsAyrinti, degistiren: "<ad>", zaman}`. Öbek yazmaları `ayar.obek_surumu` ile aynı kural.
- Teknik yazmaları `surum` istemez; `istemci_id` (uuid) taşır: `UNIQUE(kullanici_id, istemci_id)`; aynı kimlik ikinci kez gelirse ilk sonuç döner.
- Kapsam dışı iş (teknikte başkasının işi) **404** `is_yok` döner; varlığı sızdırılmaz.
- v2 yönlendiricileri `operasyon/v2/api.py`'dadır ve `saha/api.py`'ye tek yerden bağlanır:
  ```python
  @dataclass
  class Bagimliliklar:           # saha/api.py (WP-A) oluşturur, operasyon'a verir → döngüsel içe aktarma yok
      izin: Callable[..., Callable]      # yetki.izin
      kullanici: Callable                # mevcut_kullanici
      baglanti: Callable                 # baglanti
  def yonlendiriciler(b: Bagimliliklar) -> list[APIRouter]   # operasyon/v2/api.py (WP-B)
  ```

### 5.2 Tipler (TypeScript; `saha_app/src/is/tipler.ts` — sahibi WP-B, 0. saatte bu bölümden birebir)

```ts
export type Rol = 'satisci' | 'operasyon' | 'teknik' | 'yonetici';
export type Durum = 'triyaj'|'bekliyor'|'randevulu'|'atandi'|'yolda'|'sahada'
                  |'ulasilamadi'|'askida'|'altyapi'|'merkeze'|'cozuldu'|'kapandi';
export type Kova = 'atanmadi' | 'teknikte' | 'beklemede' | 'biten';
export type Serit = 'BTK' | 'SAHA' | 'MASA' | 'LOJISTIK';
export type Renk = 'yesil' | 'amber' | 'kirmizi';

export interface Kisi { id: number; ad: string; }
export interface IsSatir {
  is_no: string; boss_task_no: string | null; kaynak: 'boss' | 'bayi'; kanal_grubu: string | null;
  task_adi: string; serit: Serit; btk_hedef_saat: number | null;
  durum: Durum; kova: Kova; durum_zamani: string;
  il: string | null; ilce: string | null; mahalle: string | null;
  musteri_adi?: string | null;        // yalnız is.musteri izniyle (teknikte kısa ad)
  musteri_no?: string | null;         // yalnız is.musteri izniyle
  kisa_adres?: string | null;         // "Görükle · X Sitesi" (yalnız is.musteri izniyle)
  obek: { id: number; ad: string; renk: number } | null; obek_elle: boolean;
  triyaj_nedeni: string | null; triyaj_metni: string | null;
  konum_yaklasik: boolean; lat: number | null; lon: number | null;
  acilis: string; son24: string; btk_hedef: string | null;
  kalan_dk: number; renk: Renk; gecikti: boolean;
  bekleme_dk: number | null;          // atanmamışsa gorulme_zamani'ndan beri; değilse null
  randevu: { bas: string; bit: string; teyitli: boolean; kaynak: 'biz' | 'boss' } | null;
  atanan: Kisi | null;
  oneri: { teknik: Kisi; bas: string | null; bit: string | null; neden: string } | null;
  boss_ekip?: string | null;          // yalnız operasyon/yönetici
  ticket: { id: number; konu: string; durum: string; gun: number } | null;
  binada_acik_ticket: number;
  rozetler: Array<'btk'|'ticket'|'tekrar'|'bayi'|'global'|'konum'|'boss_islenecek'|'boss_acik'|'yeniden'|'elle'>;
  kotu_gecmis: boolean; sira: number | null;
  surum: number;
}
export interface Olay { id: number; zaman: string; kisi: string | null; tur: string; ozet: string; notu: string | null; }
export interface IsAyrinti extends IsSatir {
  adres?: string | null; musteri_tel?: string | null;
  lokasyon: string | null; mahalle_kaynak: string | null; konum_kaynak: string | null;
  bina: { serial: string; ad: string | null; location_id: string | null; lat: number; lon: number } | null;
  boss: { durum: string | null; randevu_durumu: string | null; randevu_bas: string | null; randevu_bit: string | null;
          ekip: string | null; aski_nedeni: string | null; sl: string | null; sl_saat: number | null;
          son_aciklama: string | null; bekleyen: string | null; islendi: string | null };
  uyanma: string | null; askida_neden: string | null; evde_yok_sayisi: number;
  masa_vade: string | null; teshis_sonucu: string | null;
  soz: string;                        // "Müşteriye söz: bugün 17:00'ye kadar"
  birincil: string | null;            // §6.2 tablosundaki eylem kodu: 'obege_ata'|'ata'|'yeniden_ata'|'uyandir'|'ticketi_ac'|null
  izinler: { ata: boolean; randevu: boolean; ticket: boolean; obek: boolean; iletisim: boolean;
             durumlar: Durum[]; ofisten_kapat: boolean; yeniden_ac: boolean; boss_bagla: boolean };
  boss_url: string | null;
  bayi_oneri: { boss_task_no: string } | null;
  olaylar: Olay[];                    // yeniden eskiye, en çok 50
}
export interface IslerYanit {
  sunucu_zamani: string; imlec: number; obek_surumu: number; mod: 'normal' | 'asiri_yuk';
  son_aktarim: { id: number; zaman: string; dosya_adi: string; is_sayisi: number; yas_dk: number; renk: Renk } | null;
  sayac: { acik: number; asan24: number; atanmamis: number; en_eski_atanmamis_dk: number | null; btk48: number;
           kontrol: number; boss_bekleyen: number; konum_yaklasik: number; aranacak: number; eslesmemis_ekip: number };
  isler: IsSatir[];
}
```

`saha_app/src/is/sahte.ts` (WP-B, 0. saat): yukarıdaki tiplerde **sentetik** (uydurma ad, gerçek olmayan numara) 40 işlik veri + her uç
için örnek yanıt; arayüz ajanları sunucu hazır olana kadar `import.meta.env.MODE === 'sahte'` ile bunu kullanır.
`operasyon/v2/ornek/*.json` aynı örneklerin JSON hâlidir (sözleşme testi bunlarla yanıt şemasını karşılaştırır).

### 5.3 Uçlar

#### 5.3.1 Oturum ve ben

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `POST /api/giris`, `POST /api/pin` | açık | bugünkü | bugünkü + `kullanici.rol` 4 değerden biri. Davet kodu `davet_zamani` doluysa ve 48 s geçtiyse 410 `davet_suresi_doldu` "Kodun süresi doldu. Yöneticinizden yeni kod isteyin." |
| `GET /api/ben` | giriş | — | Ortak: `{kullanici, ana_ekran, izinler: string[], gorev_etiketi}`. `satisci`: bugünkü alanlar + `bolge_yok`. `yonetici`: bugünkü özet + `gorev_gozden_gecir: bool`. `operasyon`: `{…ortak, yardim}`. `teknik`: `{…ortak, bugun:{is, btk, biten}}`. 401 kodları: `oturum_bitti`, `gorev_degisti` ("Göreviniz değişti. PIN'inizle yeniden girin."), `hesap_kapali`. Bilinmeyen rol 403 |

#### 5.3.2 İşler

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `GET /api/isler` | `is.liste` | `?kova=acik\|biten&gun=7` | `IslerYanit`. Operasyon/yönetici bütün açık işleri alır (süzme istemcide; 437 iş < 150 ms); teknik yalnız kendi açık + bugün biten. Müşteri alanı döndüyse `erisim_kaydi(is_liste, adet)` |
| `GET /api/isler/degisim` | `is.liste` | `?imlec=<olay_id>&bekle=0..25` | `{imlec, isler: IsSatir[], gorunmez: string[], obek_surumu, son_aktarim, sayac}`: imleçten sonra olayı olan işler; teknikte başkasına geçen işler `gorunmez`. v2.0'da `bekle` yok sayılabilir (hemen döner); istemci operasyonda 20 sn, teknikte 15 sn'de bir, sekme görünürken çağırır |
| `GET /api/isler/{is_no}` | `is.liste` + kapsam | — | `IsAyrinti`; 404 `is_yok`; müşteri alanı döndüyse `erisim_kaydi(is_ayrinti)` |
| `POST /api/isler/{is_no}/ata` | `is.ata` | `{teknik_id, randevu?:{bas,bit,teyitli}, yine_de?:bool, notu?, surum}` | 200 `IsAyrinti` · 409 `guncel_degil` · 409 `gecersiz_gecis` · 409 `altyapi_engeli` · 422 `teknik_gecersiz` (rol teknik değil / pasif) · 422 `teyit_gerekli` (ulasilamadi'dan) · 422 `randevu_gecersiz` |
| `POST /api/isler/oneri-onayla` | `is.ata` | `{isler: {is_no: surum}}` | `{toplu_id, atanan: string[], atlanan: [{is_no, kod, hata}]}` — önerisi olanlar önerilen teknik + dilimle atanır; her iş kendi SAVEPOINT'inde (**O**, **Shift+O**, toplu kart) |
| `POST /api/isler/toplu-ata` | `is.ata` | `{atamalar: [{is_no, teknik_id, randevu?, surum}], parca?: string}` | aynı biçim (`toplu_id`) |
| `POST /api/isler/toplu/{toplu_id}/geri-al` | `is.ata` | — | `{geri_alinan: string[], atlanan: [{is_no, kod}]}` — 10 dk içinde, aynı kişi; iş o toplu işlemden beri değiştiyse atlanır (`guncel_degil`) |
| `POST /api/isler/{is_no}/randevu` | `is.ata` | `{bas, bit, teyitli:bool, notu?, surum}` ya da `{bas:null, surum}` (kaldır) | 200 · 409 `guncel_degil` · 422 `randevu_gecersiz` ("Bitiş başlangıçtan sonra olmalı" · "En çok 4 saatlik aralık" · "En çok 7 gün ileri") |
| `POST /api/isler/{is_no}/durum` | `is.saha` (saha geçişleri) / `is.duzenle` (diğerleri) | `{yeni: Durum, neden?, evde_miydi?:bool, sonuc_kodu?, uyanma?, canli_test?:bool, randevu?:{bas,bit}, notu?, surum?, istemci_id?, zaman?}`. Teknik "Bitti" eşlemesi: `cozuldu`/`cihaz_degisti` → `yeni:'cozuldu'`; `malzeme` → `yeni:'askida'`; `altyapi_sorunu` → `yeni:'triyaj'`; `baska_gun` → `yeni:'atandi'` + `randevu` (teyitli). "Evde yok" → `yeni:'ulasilamadi'` | 200 `IsAyrinti` · 409 `gecersiz_gecis` · 409 `guncel_degil` · 409 `tekrar_ariza` · 422 `alan_eksik` ("Müşteri evde miydi?", "Uyanma zamanı gerekli") · 404 `is_yok` |
| `POST /api/isler/{is_no}/teshis` | `is.duzenle` | `{sonuc:'duzeldi'\|'simdi_evde'\|'baska_gun'\|'cevapsiz'\|'kapali'\|'yanlis_no', canli_test?:bool, randevu?:{bas,bit}, surum}` | `duzeldi`+`canli_test` → `cozuldu` (`telefonda_cozuldu`; tekrar7g → 409 `tekrar_ariza`); `simdi_evde` → şimdi…+3 s teyitli randevu, sırada öne; `baska_gun` → randevu teyitli (ulasilamadi → randevulu); `cevapsiz/kapali/yanlis_no` → BTK teşhisinde değişiklik yok; merdivende `evde_yok_sayisi` sabit, `uyanma` = sonraki bant (+2 s, 17:30, ertesi 10:00) |
| `POST /api/isler/{is_no}/ticket` | `is.duzenle` | `{ticket_id}` ya da `{yeni:{konu, ticket_no?, detay?}}`, `teknisyen_gonderme:bool`, `surum` | 200; `DELETE /api/isler/{is_no}/ticket?surum=` bağı kaldırır (`altyapi` → `bekliyor`) |
| `POST /api/isler/{is_no}/obek` | `is.duzenle` | `{obek_id \| null, surum}` | 200 — `null` elle öbeği kaldırır (mahallesine göre) |
| `POST /api/isler/{is_no}/mahalle` | `is.duzenle` | `{mahalle_id, surum}` | 200 — `mahalle_elle=1`, öbek yeniden çözülür, konum mahalle merkezi |
| `POST /api/isler/{is_no}/not` | `is.duzenle` / teknikte `is.saha` (kendi işi) | `{metin (1–1000), istemci_id?}` | 201 `{olay_id}` |
| `PATCH /api/isler/{is_no}/iletisim` | `is.duzenle` | `{musteri_tel, surum}` | 200 · 403 `tel_kapali` ("Müşteri telefonu tutulmuyor (ayar kapalı).") · 422 `telefon_gecersiz` |
| `POST /api/isler/{is_no}/kopya` | `is.musteri` | `{alan:'musteri_no'}` | 204 (yalnız erişim kaydı) |
| `POST /api/isler/{is_no}/boss-islendi` | `is.ata` | `{islendi: bool, surum}` | 200 |
| `POST /api/isler/{is_no}/boss-bagla` | `is.ata` | `{boss_task_no (9 hane), surum}` | 200 · 409 `boss_no_kullanilmis` · 422 `task_no_gecersiz` |
| `POST /api/isler/{is_no}/geri-al` | olayı yapan | `{olay_id}` | 200 · 409 `geri_alinamaz` ("Bu değişiklik artık geri alınamaz; iş sonra değişti.") · 409 `sure_doldu` |
| `POST /api/isler` | `is.olustur` | `{task_adi, bina_serial?, adres?, mahalle_id?, musteri_adi?, musteri_no?, aciklama?, istemci_id}` | 201 `{is_no:'B-260930-001', is: IsAyrinti}` · 422 `alan_eksik` ("Bina ya da adres + mahalle gerekli") |
| `GET /api/isler/excel` | `is.excel` | `?kova=acik&obek_id=` | xlsx akışı (diske yazılmaz); müşteri sütunları role göre; `erisim_kaydi(excel, adet)` |
| `POST /api/isler/dagit/onizle` | `is.ata` | `{obek_id, teknik_idler: number[]}` | `{gruplar:[{teknik_id, is_nolar, btk, km}]}` (`yakinlik.dengeli_bol`; aynı bina bölünmez; yazmaz) |
| `POST /api/isler/dagit/uygula` | `is.ata` | önizleme gövdesi + `{isler:{is_no:surum}}` | `oneri_teknik_id` + `parca` yazılır (atama yapılmaz; atama "Önerileri onayla" ile) |
| `GET /api/isler/boss-ekip` | `is.ata` | — | `{eslesmemis:[{boss_ekip, is: n}], eslesmis:[{boss_ekip, kisi: Kisi}]}` |
| `POST /api/isler/boss-ekip/esle` | `is.ata` + `ekip.teknikler` | `{boss_ekip, teknik_id}` | `{toplu_id, atanan: n}` — kişinin `boss_ekip`'i yazılır (`yonetim_kaydi`), o ekibin atanmamış açık işleri tek hamlede `atandi` (`atama_kaynagi='boss'`) |
| `GET /api/isler/teknikler` | `ekip.teknikler` | `?tarih=` | `[{id, ad, etiket, kapasite, bugun:{atanan, biten, btk}, obekler:[{id, ad}], bugun_yok: bool}]` |
| `GET /api/aranacaklar` | `is.duzenle` | — | `{bantlar:[{bant:'btk_teshis'\|'ulasilamadi'\|'uyanan'\|'masa', isler: IsSatir[]}]}` (§6.6 sırası) |

#### 5.3.3 Teknik

| Uç | İzin | İstek | Yanıt |
|---|---|---|---|
| `GET /api/islerim` | `is.saha` (teknik) | — | `{sunucu_zamani, imlec, isler: IsAyrinti[] (kendi açık işleri, sira ile), bitenler: IsSatir[] (bugün)}`; SW önce ağ, yoksa önbellek |
| `POST /api/islerim/gordu` | `is.saha` | `{is_nolar: string[]}` | 204 — ilk kez görülenlerde `teknik_gordu` |
| `POST /api/islerim/sira` | `is.saha` | `{is_no, yeni_sira, neden:'yakindaydim'\|'musteri_aradi'\|'diger', istemci_id}` | 200 |

Durum değişiklikleri `POST /api/isler/{is_no}/durum` (teknikte `surum` yok, `istemci_id` zorunlu).

#### 5.3.4 Aktarım

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `POST /api/aktarim` | `is.yukle` | multipart `dosya`, `dosya_zamani` (ISO) | §4-9 · 200 `{ayni_dosya:true}` · 409 `onay_gerekli` · 409 `aktarim_suruyor` ("Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin.") · 413 `buyuk_dosya` · 422 `rapor_tanimadi` · 503 `yedek_alinamadi` |
| `POST /api/aktarim/{id}/uygula` | `is.yukle` | `{mod:'tam'\|'kismi'}` | §4-9 · 409 `durum_gecersiz` |
| `POST /api/aktarim/{id}/vazgec` | `is.yukle` | — | 200 |
| `GET /api/aktarim` | `is.yukle` | `?limit=30` | `[{id, zaman, yukleyen, dosya_adi, is_sayisi, yeni, degisen, kaybolan, yeniden_acilan, degismeyen, cikarilan, durum, tam_kapsam, yedek}]` (kişisel veri yok) |

#### 5.3.5 Öbekler ve mahalleler

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `GET /api/obekler` | `obek.oku` | — | `{surum, obekler:[{id, ad, renk, sahip: Kisi\|null, yedek: Kisi\|null, mahalleler:[{ref, il, ilce, mahalle, tum_ilce: bool, acik: n}], acik, geciken, btk, atanmamis}], obeksiz:[{il, ilce, mahalle, mahalle_id, acik}]}` — işi 0 olan öbekler **dahil** |
| `POST /api/obekler` | `obek.duzenle` | `{ad, surum}` | 201 `{obek, surum}` · 409 `ad_var` ("Bu adla bir öbek var.") · 409 `guncel_degil` |
| `PATCH /api/obekler/{id}` | `obek.duzenle` | `{ad?, renk?, sahip_id?, yedek_id?, surum}` | 200 · 409 `ad_var` (sessiz birleştirme **yok**) · 422 `teknik_gecersiz` |
| `POST /api/obekler/{id}/mahalle` | `obek.duzenle` | `{mahalle_idler?: number[], tum_ilce?: [{il, ilce}], tasi: bool, surum}` | 200 `{surum, etkilenen_is: n, obekler: …}` · 409 `baska_obekte` `{catisma:[{ref, obek:{id, ad}}]}` (tasi=false iken) |
| `POST /api/obekler/{id}/mahalle/cikar` | `obek.duzenle` | `{refler: string[], surum}` | 200 `{surum, etkilenen_is, geri_al_olay_id}` — öbek boş kalsa da **silinmez** |
| `DELETE /api/obekler/{id}` | `obek.duzenle` | `?surum=` | 200 `{geri_al_olay_id, obeksiz_kalan_is: n}` (yumuşak silme; `ad_k` serbest kalır) |
| `POST /api/obekler/geri-al` | `obek.duzenle` | `{olay_id, surum}` | 200 · 409 `sure_doldu` (10 dk) |
| `POST /api/obekler/{id}/bol` | `obek.duzenle` | `{k (2–10), onizle: bool, surum}` | Mahalleye göre kalıcı bölme (C21): önizleme `{parcalar:[{mahalleler, is}]}`; uygula iki öbek kurar |
| `GET /api/mahalleler` | `obek.oku` | `?q=&il=&ilce=&limit=50` | `{ilceler:[{il, ilce, il_k, ilce_k, mahalle_sayisi, tum_ilce_obek: {id,ad}\|null}], mahalleler:[{id, il, ilce, ad, ref, kaynak, obek:{id,ad}\|null, acik}], oneriler:[{id, ad, ilce, benzerlik}]}` — Türkçe harf duyarsız ("gursu", "gocmen") |
| `GET /api/ilceler` | `obek.oku` | — | 23 ilçe |
| `POST /api/mahalleler` | `mahalle.ekle` | `{il, ilce, ad, benzerine_ragmen?: bool}` | 201 `{mahalle}` · 409 `benzer_var` `{oneriler}` · 409 `var` `{mahalle}` · 422 `ilce_yok` |
| `POST /api/mahalleler/esad` | `mahalle.ekle` | `{il, ilce, esad, mahalle_id}` | 201 — sonraki raporlarda o yazım doğru mahalleye düşer; o yazımla `mahalle_benzer` triyajındaki işler yeniden çözülür |
| `POST /api/mahalleler/yukle` | `mahalle.yukle` | multipart xlsx/csv (`il, ilce, mahalle[, lat, lon]`) | `{eklenen, var_olan, hatali:[satir_no]}` (kaynak `resmi`) |

#### 5.3.6 Takip

| Uç | İzin | İstek | Yanıt |
|---|---|---|---|
| `GET /api/takip` | `takip.oku` | `?gun=7` | `{sunucu_zamani, manset:{acik, asan24, atanmamis, en_eski_atanmamis_dk, btk48, en_yasli_btk_s, kontrol}, uyum24:{oran, n, yaklasik: bool, egim:[{gun, oran}]}, btk:{tv6, baglanti12, teshis45}, birikim:{asan24, egim_gun, seri:[…]}, kapasite:{talep, aktif, kapasite, mod, esnek_oneri, elle: bool}, hiz_hatti:[{adim, medyan_dk, p90_dk, n, hedef_dk, hedefte_oran}], hijyen:{cozuldu_boss_acik, askida_uyanmasiz, boss_islenecek, rapor_yas_dk}, obekler:[{id, ad, acik, geciken, btk, atanmamis, sahip}], teknikler:[{id, ad, atanan, biten, evde_yok, yolda_sahada, ilk_is}], sistem:{son_rapor, son_yedek, son_goc, saklama_metni}}` — kişisel veri yok |
| `GET /api/takip/satis` | `takip.tam` | `?gun=7` | `{demo_dahil: bool, bugun:{ziyaret, temas, satis, aktif_satisci, toplam_satisci}, hafta:{ziyaret, temas, satis, hedef\|null, ilerleme\|null}, huni:{ziyaret, temas, satis}, satiscilar:[{id, ad, bolge, bugun_ziyaret, bugun_satis, hafta_ziyaret, hafta_satis, donusum}], altyapisi_cozulen_bina: n}` — `temas` = `ayarlar.TEMAS_SONUCLARI`; iptal edilen ziyaret sayılmaz; `/api/ozet/gun` ile aynı sayıları verir |
| `GET /api/takip/erisim` | `takip.tam` | `?gun=7` | `{gunler:[{gun, kisi, eylem, adet}]}` (müşteri adı yok, yalnız sayım) |
| `GET /api/takip/yonetim` | `takip.tam` | `?limit=100` | `yonetim_kaydi` satırları |
| `PUT /api/takip/kapasite` | `kapasite.yaz` | `{tarih, aktif_teknik}` | 200 |

Hız hattı adımları: `boss_sistem` (`gorulme_zamani − acilis`, hedef 30), **`atama`** (`ilk_atama_zamani − gorulme_zamani`, hedef **15**),
`teknik_gordu` (hedef 5), `boss_islendi` (`boss_islendi − atama_zamani`, hedef 15), `yola_cikis`, `yol` (60 / BTK 45), `saha` (120 / BTK 90),
`kapanis_dogrulama`, `uctan_uca` (`cozum_zamani ?? kapanis − acilis`, hedef 24 s).

#### 5.3.7 Ekip

| Uç | İzin | İstek | Yanıt / hatalar |
|---|---|---|---|
| `GET /api/kullanici` | `ekip.yonet` | — | `{kullanicilar:[{…kart, rol, gorev_etiketi, etiket, boss_ekip, kapasite, davet_bekliyor: bool, davet_suresi_doldu: bool, son_etkinlik}]}` — **`davet_kodu` artık dönmez**; telefon `telefon_goster` maskeli ("0532 ••• •• 06"), tam hâli yalnız tek kişi yanıtında |
| `POST /api/kullanici` | `ekip.yonet` | `{id?, ad, telefon, rol ∈ 4, bolge? (yalnız satışta zorunlu), etiket?, boss_ekip?, kapasite?, aktif}` | Bugünkü + rol/bölge/aktiflik değişince `oturum_no+1` ve `oturum_neden`. 409 `son_yonetici` · 409 `kendi_rolu` · 409 `kendini_silemez` (kendini pasife) · 400 `bolge_gecersiz` · 409 `telefon_var`. Yeni kişide `davet_kodu` + `davet_zamani` (yalnız bu yanıtta) |
| `POST /api/kullanici/gorevler` | `ekip.yonet` | `{degisiklikler:[{id, rol, bolge?}], tamam: bool}` | `{degisen: n}` — tek işlem; korumalar aynı; `gorev_gozden_gecirildi=1` |
| `POST /api/kullanici/{id}/davet` | `ekip.yonet` | — | `{davet_kodu, gecerlilik}` — yeni 6 haneli kod, 48 s; yalnız bu yanıtta |
| `GET /api/kullanici/{id}/iliskiler` | `ekip.yonet` | — | `{silinebilir, engeller: ['kendini_silemez'\|'son_yonetici'\|'iliskili_kayit'], sayilar:{"ziyaret.kullanici_id": n, …}, acik_is: n, obek_sahipligi: n, demo: n, etiketler:[{metin, sayi}]}` — `pragma_foreign_key_list` ile kullanici'ye giden **bütün** FK'lar dinamik sayılır (yeni tablolar kendiliğinden girer) |
| `DELETE /api/kullanici/{id}` | `ekip.yonet` | `?obekleri_birak=0\|1` | 204 · 409 `iliskili_kayit` + sayılar · 409 `kendini_silemez` · 409 `son_yonetici`. Kontrol + DELETE tek işlem; tek bağ öbek sahipliğiyse ve `obekleri_birak=1` ise `sahip_id/yedek_id` NULL yapılıp silinir. `IntegrityError` uçta yakalanır → 409 |
| `POST /api/kullanici/{id}/is-aktar` | `ekip.yonet` | `{hedef_id}` | `{toplu_id, aktarilan: n}` — açık işler yeni teknik kişiye, her biri olaylı |
| `POST /api/kullanici/{id}/pin-sifirla`, `/cihaz-cikis` | `ekip.yonet` | bugünkü | bugünkü + `oturum_neden` + `yonetim_kaydi` |

#### 5.3.8 Ticket eki

| Uç | İzin | İstek | Yanıt |
|---|---|---|---|
| `POST /api/ticket/aktar` | `ticket.defter` | multipart xlsx (TICKET sayfası), `kuru: bool` | `{okunan, eklenen, zaten_var, guncellenen, binaya_baglanan, binasiz, baglanamayan:[{satir, lokasyon_var: bool}]}` — önce `aktarim_yedegi`; `ticket_aktar.satirlari_oku` + `aktar` kullanılır; sonra `akis.ticket_degisti` denetimi |
| `PATCH /api/ticket/{id}` (var) | `ticket.defter` | bugünkü | + durum ÇÖZÜLDÜ/KAPATILDI/İPTAL olunca `akis.ticket_degisti` |

#### 5.3.9 Eski uçlar

`/api/is-emri`, `/api/is-emri/*` (bütün yöntemler) → 410 `yenilendi` "İş emirleri ekranı yenilendi; sayfayı yenileyin."
(`operasyon/v2/api.py: eski_yonlendirici`). `operasyon/api.py` bağlanmaz (dosya yerinde kalır; `test_is_emri.py::test_api_*` 410'u doğrular,
eşdeğer davranış `test_v2_*` ile kilitlenir).

### 5.4 Hata kodları sözlüğü

| Kod | HTTP | Metin (Türkçe) |
|---|---|---|
| `yasak` | 403 | Bu bölüm görevinize kapalı. |
| `baska_bolge` | 403 | Yalnızca kendi bölgenizi görebilirsiniz. |
| `is_yok` | 404 | Bu iş bulunamadı ya da size ait değil. |
| `gorev_degisti` | 401 | Göreviniz değişti. PIN'inizle yeniden girin. |
| `guncel_degil` | 409 | Bu iş siz bakarken değişti: {saat}'te {kişi} {ne yaptı}. |
| `gecersiz_gecis` | 409 | Bu iş '{durum}' durumunda; '{yeni}' yapılamaz. |
| `altyapi_engeli` | 409 | Bu binada açık {konu} ticket'ı var (#{no}, {gün} gündür). Teknisyen gönderilmez. |
| `tekrar_ariza` | 409 | Bu arıza 7 gün içinde tekrar geldi; telefonda kapatılamaz. Kıdemli teknisyene atayın. |
| `teyit_gerekli` | 422 | Müşteriye ulaşılmadan aynı işe ikinci kez teknisyen gönderilmez. "Saat teyitli" işaretleyin. |
| `randevu_gecersiz` | 422 | (neden cümlesi) |
| `alan_eksik` | 422 | (eksik alanın sorusu) |
| `teknik_gecersiz` | 422 | Seçilen kişi aktif bir teknik görevli değil. |
| `onay_gerekli` | 409 | (bekçi mesajı, §6.7) |
| `aktarim_suruyor` | 409 | Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin. |
| `rapor_tanimadi` | 422 | Bu dosya Teknik Task Detay Raporu değil. |
| `ayni_dosya` | 200 | Bu dosya {saat}'te zaten yüklenmişti. Hiçbir şey değişmedi. |
| `baska_obekte` | 409 | {mahalle} şu an '{öbek}' öbeğinde. Buraya taşınsın mı? |
| `ad_var` | 409 | Bu adla bir öbek var. |
| `benzer_var` | 409 | Benzer bir mahalle var: {ad}. Aynı yer mi? |
| `iliskili_kayit` | 409 | Bu kişi silinemez: {sayılar}. Pasife alabilirsiniz. |
| `kendini_silemez` | 409 | Kendinizi silemez ya da pasife alamazsınız. |
| `son_yonetici` | 409 | Son aktif yönetici düşürülemez, pasife alınamaz, silinemez. |
| `kendi_rolu` | 409 | Kendi görevinizi değiştiremezsiniz. |
| `boss_no_kullanilmis` | 409 | Bu Task No başka bir işte. |
| `tel_kapali` | 403 | Müşteri telefonu tutulmuyor (ayar kapalı). |
| `davet_suresi_doldu` | 410 | Kodun süresi doldu. Yöneticinizden yeni kod isteyin. |
| `butunluk` | 409 | Bu kayıt başka kayıtlarla bağlantılı olduğu için değiştirilemedi. |
| `guncelleme_bekliyor` | 503 | Sunucu güncellenmeyi bekliyor. BASLAT.bat ile yeniden açın. |
| `yedek_alinamadi` | 503 | Güvenlik yedeği alınamadı; hiçbir şey değiştirilmedi. Diskte yer var mı? |
| `yenilendi` | 410 | İş emirleri ekranı yenilendi; sayfayı yenileyin. |
| `sure_doldu` / `geri_alinamaz` | 409 | Bu değişiklik artık geri alınamaz. |

### 5.5 Eşzamanlılık

| Durum | Kural |
|---|---|
| İki operatör aynı işe yazar | İş `surum`'u; kaybeden 409 `guncel_degil` + güncel hâl + son olayın sahibi/zamanı. Kullanıcının yazdığı not/seçim kaybolmaz; "Yine de uygula" yeni sürümle yeniden gönderir |
| `surum` neyle artar | Yalnız operasyon alanları: durum, atama, randevu, ticket, elle öbek/mahalle, iletişim, boss_islendi, sıra. BOSS alanları, türetilen `obek_id`, öneri alanları **artırmaz**; aktarım durumu ilerletirse artar |
| Öbek düzeni | Tek küresel sayaç `ayar.obek_surumu` (mahalle taşıma iki öbeğe dokunur); uyuşmazsa 409 + güncel öbek listesi |
| Aktarım + düzenleme | Ayrıştırma işlem dışında; yazma tek `BEGIN IMMEDIATE` (<300 ms); operasyon alanlarına dokunmaz |
| İki aktarım | Süreç kilidi → ikincisi 409 `aktarim_suruyor` |
| Toplu atama | Her iş kendi SAVEPOINT'inde; kısmi başarı normal (`atanan` / `atlanan`) |
| Çevrimdışı teknik | `istemci_id` tekil; olay `zaman` = cihazdaki basış, `kayit_zamani` = sunucu; geç gelen "Yola çıktım" iş zaten `sahada` ise yalnız olay yazılır, durum geri gitmez; iş başkasına geçmişse 404 `is_yok` → kuyruk düşürür ve söyler |
| Canlı pano | `GET /api/isler/degisim?imlec=` (20 sn); öbek değişikliği `obek_surumu` ile fark edilir |
| Göç | Dosya kilidi + port kontrolünden sonra, sunucu açılmadan önce |
| Süreç | Tek uvicorn süreci |

### 5.6 Başarım bütçeleri (test edilir)

| Ölçü | Bütçe |
|---|---|
| `GET /api/isler` (437 iş, operasyon) | < 150 ms |
| `GET /api/isler/{no}` | < 50 ms |
| Aktarım: okuma + hesap (iş parçacığında) | < 3 sn; yazma işlemi < 300 ms |
| Aktarım sırasında `/api/saglik` (gerçek uvicorn, 127.0.0.1:809x) | < 300 ms |
| Öbek düzenleme (mahalle ekle/çıkar + işlerin yeniden çözümü) | < 150 ms |
| Göç v0 → v5 (canlı kopya, yedek dahil) | < 10 sn |

---

## 6. Ekranlar (F1–F3, F5, F7–F17, F19)

### 6.0 Bilgi mimarisi, yönlendirme, menü

**Adresler** (hash yönlendirici; `yol/rota.tsx`):

```
#/bugun, #/bina/<serial>, #/harita, #/ben         Satış (değişmez)
#/islerim[/<is_no>]                               Teknik
#/yonetici/isler[/obek/<id>][/is/<is_no>]         İşler panosu (operasyon, yönetici)
#/yonetici/aranacak                               Aranacaklar
#/yonetici/obekler[/<id>]                         Öbekler; öbek çekmecesi açık
#/yonetici/takip                                  Takip
#/yonetici/ekip                                   Ekip (yalnız yönetici)
#/yonetici/rapor-gecmisi                          Veri ▸ Rapor geçmişi
#/yonetici/is-emirleri                            → #/yonetici/isler (eski yer imi)
#/yonetici/{canli,kapsama,atama,rapor,ticketlar,bolge-planlayici,tur-raporu,veri-kalitesi}   bugünkü ekranlar
```

`App.tsx`: yönetim kapısı `rol ∈ {yonetici, operasyon}`; `#/islerim` kapısı `rol = teknik`; izinsiz adreste "Bu bölüm görevinize kapalı."
+ [Ana ekrana dön]. Girişten sonra `/api/ben.ana_ekran`'a gider (`depo/oturum.tsx`); yönetici için cihaz tercihi (§2.1).

**Masaüstü sol menü** (232 px; `/api/ben.izinler`'e göre süzülür; gruplar açılır/kapanır, hâli cihazda hatırlanır):

| Operasyon | Yönetici |
|---|---|
| İşler · Aranacaklar · Öbekler · Takip · Ticketlar · Veri ▸ (Rapor geçmişi) | **İşler** · Aranacaklar · Öbekler · Takip · Ticketlar · Ekip · Satış ▸ (Canlı durum, Kapsama, Görev atama, Rapor) · Veri ▸ (Rapor geçmişi, Bölge planlayıcı, Tur raporu, Veri kalitesi) |

Menünün altında: kişinin adı + görev rozeti, "Başlangıç ekranı" (yalnız yönetici), "Satış uygulaması" (yalnız yönetici), "Görünüm: Sistem ·
Açık · Koyu", "Çıkış".

**Telefon alt sekmeleri** (en çok 4; 44 px başlık çubuğu; bugünkü yapışkan menü bloğu kalkar):

| Görev | Sekmeler |
|---|---|
| Satış | Bugün · Harita · Ben (değişmez) |
| Operasyon | İşler · Aranacak · Öbekler · Daha (Takip, Ticketlar, Rapor geçmişi, Görünüm, Çıkış) |
| Teknik | İşlerim · Ben |
| Yönetici | İşler · Öbekler · Takip · Daha (Aranacaklar, Ticketlar, Ekip, Satış ▸, Veri ▸, Görünüm, Çıkış) |

**Gösterim verisi uyarısı:** yalnız demo ziyaret kullanan satış ekranlarında (Canlı, Kapsama, Rapor, Takip → Satış) başlığın yanında
küçük bir hap: "Gösterim verisi". İşler, Aranacaklar, Öbekler, Ticketlar, Ekip, İşlerim'de **yok**.

**Her ekranın başlığının altında tek cümle** ("Bu ekranda ne yaparım?"; kapatılabilir, cihaz hatırlar):

| Ekran | Cümle |
|---|---|
| İşler | Gelen işleri teknisyenlere atayın; kırmızılar önce. |
| Aranacaklar | Aranması gereken müşteriler burada; sonucu tek dokunuşla işleyin. |
| Öbekler | Öbek, birlikte çalışılan mahalle grubudur. Mahalle ekleyin, çıkarın. |
| Takip | Sözümüzü tutuyor muyuz, hızlı mıyız, ekip yetiyor mu — tek bakışta. |
| Ekip | Kişi ekleyin, görevini seçin; ayrılanı pasife alın. |
| İşlerim | Size atanan işler sırayla burada. Sıradakine gidin. |

### 6.1 İşler — operasyon panosu

**Masaüstü ≥1200 px, üç bölme; sayfa hiç yeniden akmaz:**

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ İşler      Açık 437 · 24 saati aşan 288 · Atanmamış 12 (en eskisi 9 dk) · 48 saati aşan BTK 5          │
│ Gelen işleri teknisyenlere atayın; kırmızılar önce.        Son rapor 11:38 · 12 dk önce  [Rapor yükle] [+ Yeni iş] │
├──────────────────────────┬─────────────────────────────────────────────────────────┬─────────────────┤
│ ÖBEKLER          🔍      │ Görükle                   31 açık · 9 geciken · 14 BTK │ İŞ ÇEKMECESİ    │
│ Tümü               437   │ Teknisyen: A. K.   [Düzenle]  [Ekiplere dağıt]          │ (440 px, listenin│
│ ⚠ Kontrol gerekli    3 › │ ┌─────────────────────────────────────────────────────┐ │  üstüne kayar)  │
│ ⓘ Eşleşmemiş BOSS ekibi 4│ │ 4 atanmamış iş → A. K.'ya ata (bugün 3, yarın 1) [Ata]│ │                 │
│ ⓘ BOSS'a işlenecek   7   │ └─────────────────────────────────────────────────────┘ │                 │
│ ─────────────────────── │ [Atanmadı 12] [Teknikte 40] [Beklemede 13] [Biten]  🔍 Ara  [Süz ▾]      │
│ ● Görükle   31 ·9 ·14 ●  │ ─────────────────────────────────────────────────────── │                 │
│ ● Dumlupınar 65 ·31 ·22  │ 2 s 10 dk ● BTK Bağlantı Problemi                       │                 │
│ ● Özlüce    22 ·4 ·9  ●  │   (Müşteri) · Görükle · X Sitesi                        │                 │
│ …                        │   Atanmadı · geleli 12 dk · Öneri A. K. 11–13   [Onayla O]│                │
│ ◌ Gürsu      0           │ Gecikti · 5 s  Modem Değişikliği                         │                 │
│ Öbeksiz · Mudanya    7   │   (Müşteri) · Görükle · 12. Sk   Atandı · A. K. · 14–16  │                 │
│ ⓘ Konum yaklaşık    96   │ …                                        [Liste | Harita]│                 │
└──────────────────────────┴─────────────────────────────────────────────────────────┴─────────────────┘
```

- **Başlık şeridi:** tek satır sakin sayılar; her sayı tıklanınca listeyi süzer. "Rapor yükle" **ikincil** düğme; dosya sayfanın her yerine
  bırakılabilir. Rapor tazeliği §3.5 rengiyle.
- **Öbek sütunu (280 px, sabit):** satır = renk noktası · ad · açık · geciken · BTK · atanmamış varsa mavi nokta. Sıra: atanmamışı olan,
  sonra geciken sayısı. Özel satırlar: üstte "Tümü", "⚠ Kontrol gerekli" (0 ise yeşil hap "✓ Bütün işler öbeğinde"), "Eşleşmemiş BOSS ekibi"
  (0 ise gizli), "BOSS'a işlenecek" (0 ise gizli); altta "Öbeksiz · <ilçe>" satırları ve "ⓘ Konum yaklaşık" (bilgi süzgeci). **İşi 0 olan öbek
  soluk görünür**, kaybolmaz. Öbeğe tıklamak listeyi süzer (F3) ve üstte **öbek başlık kartını** açar (ad, teknisyen, [Düzenle] →
  öbek çekmecesi §6.4, [Ekiplere dağıt] → pencere, toplu atama kartı §6.3).
- **Liste:** kovalar segment (Atanmadı varsayılan). Satır 72 px, üç bilgi:
  1. Kalan süre hapı (renk + yazı) · BTK rozeti · task adı
  2. Müşteri adı (yetkiye göre) · mahalle · kısa adres (◌ konum yaklaşıksa)
  3. Durum yazısı (nötr, nokta) · "geleli N dk" (atanmamışsa) · randevu dilimi (teyitliyse ✓) · teknisyen · rozetler · **satırın tek eylemi**:
     Kontrol → [Öbeğe ata] · önerisi olan atanmamış → [Onayla] · önerisiz atanmamış → [Ata] · diğer → yok (satır tıklanır).
  Varsayılan sıra §3.6. 1200 px altında "Yer" ve "Task" tek hücrede.
- **Süz:** tek düğme; çekmecede İlçe, Task türü, Şerit (BTK/Saha/Masa/Lojistik), Teknisyen, Kaynak (Global/Bayi/Kanal bilinmiyor), "Yalnız:
  geciken · BTK · ticketlı · tekrar · randevusu bugün · BOSS'a işlenecek". Etkin süzgeçler aramanın yanında kaldırılabilir çip. Bugünkü
  33 çiplik süzgeç duvarı ve öbek seçicisi kalkar. Arama: Task No, müşteri no, müşteri adı, mahalle, bina adı.
- **Harita:** "Liste | Harita"; bugünkü `IsHaritasi` bileşeni, yalnız süzülen işler; konum yaklaşık halka.
- **Klavye (yalnız masaüstü; `?` yardım çekmecesi; tuş ipucu `kbd` yalnız fare/klavye cihazda):**

| Tuş | Eylem |
|---|---|
| `↓` / `↑` (ya da `J`) | Sonraki / önceki iş |
| `Enter` | İş çekmecesini aç |
| `O` | Seçili işin önerisini onayla |
| `Shift+O` | Öbeğin bütün önerilerini onayla (onay çekmecesi: "12 iş, 3 teknisyene") |
| `A` | Ata (teknisyen seçicisine odaklan) |
| `R` | Randevu: `1`–`6` bugünün dilimleri, `Y` yarın, `D` tarih |
| `B` | Öbeğe taşı |
| `T` | Ticket bağla / aç |
| `N` | Not |
| `/` | Ara |
| `Esc` | Çekmeceyi kapat |

**1024–1199 px:** öbek sütunu listenin üstünde "Öbek: Tümü ▾" seçicisine döner; çekmece listenin üstüne biner.
**768–1023 px:** tek liste; çekmece alttan yarım ekran, çekince tam ekran.

**Telefon <768 px — itmeli gezinme, iç içe kaydırma yok, tablo yok:**

```
┌──────────────────────────────┐  ┌──────────────────────────────┐  ┌──────────────────────────────┐
│ İşler                    ＋  │  │ ‹ İşler     Görükle   Harita │  │ ‹ Görükle                  ⋯ │
│ 12 atanmayı bekliyor · 9 dk  │  │ 31 açık · 9 geciken          │  │ BTK  Bağlantı Problemi       │
│ 288 iş 24 saati aştı         │  │ ┌──────────────────────────┐ │  │ Kalan 2 s 10 dk              │
│ Son rapor 11:38 · 12 dk      │  │ │ 4 atanmamış iş           │ │  │ Müşteriye söz: bugün 17:00   │
│ ──────────────────────────── │  │ │ A. K.'ya ata    [  Ata  ]│ │  │ ── Müşteri ───────────────── │
│ ⚠ Kontrol gerekli         3 ›│  │ └──────────────────────────┘ │  │ (Ad Soyad)                   │
│ Görükle     31 · 4 yeni ●  › │  │ [Atanmadı][Teknikte][Bekle.] │  │ No ••••  [Kopyala]           │
│ Dumlupınar         65      › │  │ 2 s 10 · BTK Bağlantı      › │  │ ── Planla ────────────────── │
│ …                            │  │ (Müşteri) · Görükle 12. Sk   │  │ Teknisyen  A. K. (öbeğin)  › │
├──────────────────────────────┤  │ …                            │  │ Bugün · Yarın · Tarih…       │
│ İşler  Aranacak Öbekler Daha │  ├──────────────────────────────┤  │ 08–10 10–12 12–14 14–16 …    │
└──────────────────────────────┘  │ İşler  Aranacak Öbekler Daha │  │ ☐ Müşteriyle konuşuldu,      │
                                  └──────────────────────────────┘  │   saat teyitli               │
                                                                    ├──────────────────────────────┤
                                                                    │ [            Ata           ] │ ← 56 px, başparmak
                                                                    └──────────────────────────────┘
```

### 6.2 İş çekmecesi (masaüstünde sağdan 440 px; telefonda tam ekran)

Bölümler karar sırasıyla; "Geçmiş" ve "BOSS bilgisi" kapalı başlar.

1. **Başlık:** BTK rozeti · task adı · kalan süre (büyük) · BTK hedefi · "Müşteriye söz: …" · durum yazısı · kaynak rozeti · Task No [Kopyala].
   İnce adım çizgisi: *Geldi → Atandı → Yolda → Sahada → Çözüldü*.
2. **Müşteri** (yetki varsa): ad; Müşteri No [Kopyala] (erişim kaydı) · [BOSS'ta aç] (`boss_task_url` varsa; yoksa "Task No'yu kopyala" ve
   bildirim "Task No kopyalandı, BOSS'ta arayın"); telefon yalnız `musteri_tel='acik'` ise.
3. **Adres ve yer:** tam adres [Kopyala] · [Haritada aç] (koordinatla, A5); "Mahalle: Görükle · Location Id'den" (kaynak düz Türkçe:
   "Location Id'den" / "Adresten" / "Elle"); bina adı + Location Id + [Binayı aç]; **Öbek: Görükle [Öbeğe taşı]** ("elle" etiketi; geri alma:
   "Mahallesine göre"). Konum yaklaşıksa: "Konum yaklaşık: mahalle merkezi".
4. **Planla:** Teknisyen (öbeğin ev teknisyeni **önceden seçili**; seçicide "A. K. · öbeğin · bugün 9/15", sonra diğer teknikler yüküyle; pasifler
   gizli; "Bugün yok" işaretliler soluk) · Gün çipleri (Bugün · Yarın · Tarih…) · dilim çipleri (`ayar.dilimler`; varsayılan öneri dilimi) ·
   ☐ **Müşteriyle konuşuldu, saat teyitli** · BOSS'taki randevu salt okunur ("BOSS: 30.09 10:00–12:00").
5. **Ticket:** "Binada açık ticket yok." [Ticket bağla / aç] — ya da sarı: "Bu binada açık SİNYAL ticket'ı var (#12, 3 gündür). Teknisyen
   gönderilmez." [Ticket'a bağla].
6. **BTK teşhisi** (yalnız BTK işinde, kötü geçmiş değilse): "Masa araması · vade 10:45" + tek dokunuşla sonuç düğmeleri (§6.6).
7. **BOSS'a işlenecek** (bayrak varsa): "BOSS'a gir: Ekip A. K. · 11:00–13:00 [Kopyala]  ☐ BOSS'a işlendi".
8. **Diğer** (metin düğmeleri, izin varsa): Evde yok · Askıya al · Ofisten kapat · Merkeze gönderildi · Yeniden aç · BOSS Task No'yu bağla.
   Her biri tek soruluk küçük çekmece ("Neden?" + gerekiyorsa "Ne zaman tekrar bakılsın?").
9. **Not:** tek satır [Ekle].
10. **Geçmiş ▸ (n):** "14:02 · Ayşe Y. · A. K.'ya atadı · 10–12 · 7 dk içinde".
11. **BOSS bilgisi ▸:** durum, Ekip, randevu durumu, askı nedeni, SL, son açıklama.

**Tek birincil eylem (alt çubuk; sunucunun `birincil` alanından):**

| Durum | Birincil | Diğer |
|---|---|---|
| Kontrol gerekli | **Öbeğe ata** | Mahalleyi seç · Ofisten kapat |
| Atanmadı (binada açık ticket) | **Ticket'a bağla** | Yine de ata |
| Atanmadı | **Ata** | Randevu ver · Ticket bağla · Askıya al |
| Randevu verildi | **Ata** | Randevuyu değiştir |
| Atandı / Yolda / Sahada | — (değişiklik varsa **Kaydet**) | Başka tekniğe ver · Randevuyu değiştir · Ticket bağla |
| Ulaşılamadı | **Yeniden ata** (teyit kutusu zorunlu) | Askıya al · Aranacaklara git |
| Askıda | **Uyandır** | Uyanmayı değiştir |
| Altyapı bekliyor | **Ticket'ı aç** | Ticket'tan ayır |
| Merkeze gönderildi | **Sahaya al** | — |
| Çözüldü | — ("BOSS'ta kapanması bekleniyor") | Yeniden aç |

Başarıdan sonra bildirim: "A. K.'ya atandı · **Geri al**" (10 sn). **Çakışma:** 409 `guncel_degil` → çekmece güncel hâle döner, üstte sarı satır
"Bu iş siz bakarken değişti: 14:02'de Mehmet T. A. K.'ya atadı." Kullanıcının seçimi korunur, [Yine de uygula].

### 6.3 Toplu atama kartı (15 dakikanın ana yolu; F7, F17)

Öbek seçiliyken listenin başında tek cümle: **"4 atanmamış iş → A. K.'ya ata (bugün 3, yarın 1)  [Ata]"**.

- Teknisyen = öbeğin ev teknisyeni (öneri). Yoksa: "Bu öbeğin teknisyeni yok. [Teknisyen seç]" (öbek çekmecesi açılır).
- Kapsam: öbeğin önerisi olan atanmamış işleri; sıra §3.6; dilimler teknisyenin sıradaki boş dilimlerinden; bugün dolunca yarın ilk dilim.
- **Atlanır:** binasında açık ticket olan iş ("1 iş ticket bekliyor, atanmadı"), `ulasilamadi` işler (kural 8), `triyaj` işler.
- Sonuç: "4 iş A. K.'ya atandı · Geri al" (10 sn; `POST /api/isler/toplu/{toplu_id}/geri-al`).
- Yanındaki "Başkasına…" metin düğmesi teknisyen seçtirir. **Shift+O** aynı işlemin klavye yoludur.
- **Eşleşmemiş BOSS ekibi** satırı açılınca: "BOSS'ta 'EKİP ADI' yazan 23 iş var. Bu ekip kim?" + teknik seçici + [Eşle ve ata] → tek hamlede atanır.

### 6.4 Öbekler, öbek çekmecesi, mahalle seçici (F1, F2)

**Öbekler ekranı:** masaüstünde tablo (Öbek · Mahalle · Açık · Geciken · BTK · Atanmamış · Ev teknisyeni); telefonda satır listesi.
Başta [+ Yeni öbek] ve "Öbeksiz mahalleler (N) ›" (bugün işi olan ama öbeği olmayan mahalleler; satırda [Bir öbeğe ekle]).

**Öbek çekmecesi:**

```
┌ Görükle                                        [Adı değiştir] ┐   ┌ Mahalle ekle · Görükle            [Vazgeç] ┐
│ 3 mahalle · 31 açık iş · 9 geciken · 14 BTK                   │   │ 🔍 Mahalle ya da ilçe yazın                 │
│ Ev teknisyeni  A. K. ▾        Yedek  — ▾                      │   ├ GÜRSU ─────────────────────────────────────┤
├ Mahalleler ───────────────────────────────── [+ Mahalle ekle] ┤   │ ☐ İlçenin tamamı                            │
│ Bursa · Nilüfer · Görükle        14 iş                    ⊖   │   │ ☐ Mahalle A                 bugün iş yok    │
│ Bursa · Nilüfer · Kayapa          17 iş                    ⊖   │   │ ☑ Mahalle B   bugün 2 iş · Yıldırım öbeğinde│
│ Bursa · Gürsu · ilçenin tamamı    bugün iş yok             ⊖   │   ├────────────────────────────────────────────┤
├───────────────────────────────────────────────────────────────┤   │ "Göçmen" listede yok.                       │
│ Öbeği ikiye böl…                                               │   │   [Yeni mahalle olarak ekle]                │
│ Öbeği sil                                           (kırmızı)  │   ├────────────────────────────────────────────┤
└───────────────────────────────────────────────────────────────┘   │ 1 mahalle Yıldırım öbeğinden taşınacak.     │
                                                                    │ [      2 mahalleyi ekle ve taşı      ]      │
                                                                    └────────────────────────────────────────────┘
```

- **Mahalleler (F1)** öbeğin tanımıdır, rapora bağlı değildir; her satırda bugünkü açık iş sayısı (0 → "bugün iş yok") ve 44 px ⊖. ⊖ hemen
  çıkarır; bildirim "Kayapa çıkarıldı · Geri al"; işlerin öbeği aynı işlemde yeniden çözülür ve pano sayıları **sayfa yenilenmeden** (aynı
  yanıttan) güncellenir. Son mahalle çıkınca öbek **silinmez**: "Bu öbekte mahalle yok. Bursa ve Yalova'nın bütün mahallelerinden
  seçebilirsiniz; bugün işi olmayanlar da listede." [+ Mahalle ekle].
- **Mahalle seçici (F2):** 23 ilçenin tamamı, rapordan bağımsız (`GET /api/mahalleler`); Türkçe harf duyarsız arama ("gursu" → Gürsu);
  ilçeye göre gruplu; her ilçenin başında **"İlçenin tamamı"** (sözlükte mahallesi olmayan ilçede de çalışır); her satırda bugünkü iş sayısı
  ve **şu anki öbeği**; çoklu seçim; alt çubukta tek cümlelik **taşıma onayı** ("1 mahalle Yıldırım öbeğinden taşınacak."). Sessiz taşıma yok.
- **Listede yoksa:** "'Göçmen' listede yok. [Yeni mahalle olarak ekle]" → ilçe seçtirir (aramada ilçe adı geçtiyse seçili gelir) → benzer ad
  varsa önce sorar: "Aynı ilçede 'Taşlimanı' var. Aynı yer mi? [Evet, aynı] [Hayır, yeni mahalle]" ("Evet" → `mahalle_esad`). Yeni mahalle
  `kaynak='elle'` ile sözlüğe ve öbeğe girer; o mahalleden sonra gelen iş kendiliğinden bu öbeğe düşer.
- **İlçenin tamamı + tek mahalle:** aynı ilçeden tek tek eklenmiş mahalle önceliklidir (birebir önce, sonra `*`).
- **Adı değiştir:** aynı ad (Türkçe harf duyarsız) varsa "Bu adla bir öbek var." (sessiz birleştirme yok).
- **Öbeği sil:** onay çekmecesi "Görükle öbeği silinsin mi? 3 mahallesi öbeksiz kalır; 31 iş 'Kontrol gerekli'ye düşer." [Sil] (kırmızı, sağda)
  [Vazgeç]; sonra 10 sn "Geri al".
- **Öbeği ikiye böl…** (C21, mahalleye göre kalıcı): önizleme haritası + iki listenin iş sayıları → [İki öbek oluştur].
- **Ekiplere dağıt** (bugünkü "Böl (binaya göre)"): teknisyenleri seç (varsayılan: öbeğin teknisyeni + bugün boşta olanlar) → önizleme
  (kişi başına iş, BTK, km; aynı bina bölünmez) → [Önerileri güncelle] → atama "Önerileri onayla (n)" ile. Pencere sayfayı yeniden dizmez.

### 6.5 Kontrol gerekli (F4, F5)

Liste yalnız gerçek sorunları gösterir; her satırda düz Türkçe neden ve eylemler:

| Neden | Metin | Eylemler |
|---|---|---|
| `il_disi` | "Adres İzmir yazıyor; bölgemiz Bursa ve Yalova." | **Öbeğe ata** · Mahalleyi seç · Merkeze gönderildi |
| `mahalle_yok` | "Adreste mahalle bulunamadı." | **Mahalleyi seç** · Öbeğe ata |
| `mahalle_benzer` | "'Taşliman' yazılmış; 'Taşlimanı' olabilir." | **Aynı mahalle** (eşad yazılır) · Yeni mahalle · Öbeğe ata |
| `obeksiz` | "Mahallesi hiçbir öbekte değil: Kurtul · Gürsu." | **Bu mahalleyi bir öbeğe ekle** (bundan sonra hep oraya düşer) · Yalnız bu işi taşı |
| `altyapi_supheli` | "Teknisyen altyapı sorunu bildirdi." | **Ticket'a bağla** · Yeniden ata |

"Öbeğe ata" `obek_elle_id` yazar (sonraki raporlarda korunur, satırda "elle"); "Mahalleyi seç" `mahalle_elle=1` yazar. **Konum yaklaşık**
(bugün 50 ilçe merkezi + 46 mahalle merkezi) Kontrol'e girmez; öbek sütununda "ⓘ Konum yaklaşık 96" bilgi süzgecidir; iş çekmecesinde
"Binayı seç" (bina arama) sunulur.

### 6.6 Aranacaklar (masa kuyruğu; KARMA-2 kural 4, 8, 12, 14)

Tek liste, bant sırasıyla: **1 BTK teşhis** (vade 45 dk; `masa_vade` artan) › **2 Ulaşılamadı** (uyanma geldi; deneme sayısı) › **3 Uyanan
askı** (son arama) › **4 Masa işleri** (Kanal Şikayeti, Soru-Cevap). Satır: vade ("12 dk kaldı" / "vade geçti 5 dk"), task, müşteri,
deneme "2/3", "Müşteri No [Kopyala]". Kötü geçmişli müşteri gri ve BTK bandına girmez. Sonuç düğmeleri (tek dokunuş, 44 px):

| Düğme | Ne olur |
|---|---|
| Düzeldi (canlı test yapıldı) | `cozuldu` (`telefonda_cozuldu`); saha ziyareti iptal. `tekrar7g` işte yoktur |
| Şimdi evde | Randevu şimdi…+3 s, teyitli; iş teknisyenin sırasında öne |
| Başka gün | Gün + dilim; teyitli (ulaşılamadı → randevulu) |
| Cevapsız · Kapalı · Yanlış numara | BTK teşhisinde değişiklik yok (teknisyen habersiz gider); merdivende sonraki bant (+2 s, 17:30, ertesi 10:00); 3. denemeden sonra "Askıya al (48 s, BTK 24 s)" önerilir |

Boş: "Şu an aranacak kimse yok. BTK işi gelince 45 dakika içinde burada olur."

### 6.7 Rapor yükle ve rapor geçmişi (F18)

- Bırak ya da [Rapor yükle] → ince ilerleme "Rapor okunuyor…" (başka hiçbir kullanıcı beklemez).
- Sonuç tek satır bildirim, pano aynı anda güncellenir: **"Rapor işlendi · Yeni 12 · Değişen 30 · Kapanan 30 · Yeniden açılan 3 · Aynı 392"**;
  her sayıya basınca o işler süzülür; [Ayrıntı] çekmecesi: çıkarılanlar ("1.628 satırdan 1.191'i kurulum ekibinin: kurulum 1.072 ·
  2. donanım 119"), istisna tutulan, kontrol gerekenler, süre, alınan yedeğin adı. Bugünkü geliştirici günlüğü şeridi kalkar.
- Aynı dosya: "Bu dosya 11:38'de zaten yüklenmişti. Hiçbir şey değişmedi."
- **Onay çekmecesi** (409 `onay_gerekli`):
  - `cok_kaybolan`: "Bu raporda 180 açık iş yok (açık işlerin %41'i). Rapor süzgeçli ya da tek ilçe indirilmiş olabilir."
    [Tam rapor: kapanmış say] [Kısmi rapor: kapatma] [Vazgeç]
  - `eski_rapor`: "Bu rapor en son yüklenenden (11:38) eski görünüyor. İşlenirse hiçbir iş kapatılmaz, yalnız eklenir ve güncellenir."
    [Yine de işle] [Vazgeç]
- Eşzamanlı: "Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin."
- **Rapor geçmişi** (Veri ▸): son 30 aktarım — zaman · yükleyen · dosya adı · iş · yeni/değişen/kapanan/yeniden açılan · durum · yedek.

### 6.8 Yeni iş (bayi; F16)

Çekmece, tek sütun: Müşteri No (isteğe bağlı; aynı müşterinin açık işi varsa altında "Bu müşterinin açık işi var: …") · Müşteri adı · İş tipi
(bilinen task adlarından arama; şerit buradan) · **Bina** (Location Id / bina adı / adres ile ara → mahalle ve öbek kendiliğinden) ya da Adres +
İlçe + Mahalle (sözlük seçici) · Açıklama. Birincil: **"İşi aç"**. Sonuç: "B-260930-001 açıldı · Atanmadı listesinde." İş "Bayi" rozetiyle
Atanmadı listesinin başına öneriyle düşer; 24 s saati açılış anından başlar.

### 6.9 Teknik — İşlerim (telefon önce; F7, F8)

```
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ İşlerim           Salı 30.09 │   │ ‹ İşlerim                    │
│ 6 iş · 2 BTK · ilki 08:30    │   │ BTK  Bağlantı Problemi       │
│ ● Az önce güncellendi        │   │ Kalan 5 s 10 dk              │
│ ──────────────────────────── │   │ 08–10 · teyitli ✓            │
│ SIRADAKİ                     │   │ (Ayşe K.) · No ••• [Kopyala] │
│ 08–10  BTK Bağlantı        › │   │ (adres)                      │
│  Görükle · 12. Sokak         │   │ Site A · Location Id [Kopyala]│
│  Kalan 5 s                   │   │ [       Yol tarifi        ]  │
│ 10–12  Modem Değişikliği   › │   │ ⚑ Binada açık SİNYAL ticket'ı│
│  Görükle · Site A    ⚑       │   │   var. Operasyonla konuşun.  │
│ Randevusuz  TV+ Arıza      › │   │ Operasyon notu: …            │
│ …                            │   │ ──────────────────────────── │
│ Bitenler (2) ▸               │   │ Evde yok · Not ekle          │
├──────────────────────────────┤   ├──────────────────────────────┤
│   İşlerim            Ben     │   │ [       Yola çıktım       ]  │  ← 56 px
└──────────────────────────────┘   └──────────────────────────────┘
```

- **Sıra:** bugünkü randevulu işler dilim başlangıcına göre, sonra randevusuzlar §3.6 sırasıyla; teknisyen bir işi taşıyabilir, nedenini tek
  dokunuşla seçer (Yakındaydım · Müşteri aradı · Diğer).
- **Tek büyük düğme** duruma göre: Atandı → **Yola çıktım** · Yolda → **İşe başladım** · Sahada → **Bitti**.
- **Bitti** alttan çekmece: önce zorunlu **"Müşteri evde miydi?"** [Evet] [Hayır]; sonra sonuç: **Çözüldü** · Cihaz değişti · Malzeme gerekiyor ·
  Altyapı sorunu · Müşteri başka gün istedi (gün + dilim). Kart "Bitenler"e iner.
- **Evde yok:** onay kutusu "10 dk bekledim, BOSS'tan 2 kez aradım, not bıraktım" + isteğe bağlı not → iş anında operasyonun Aranacaklar
  listesine düşer.
- **Yeni iş gelince:** `navigator.vibrate(200)`, üstte "1 yeni iş" bildirimi, satırda "Yeni" rozeti; iş ekrana ilk girince `POST /api/islerim/gordu`.
- **Görmediği şeyler:** başkasının işi, satış verisi, kapanmış işin müşteri bilgisi, öbek düzeni.
- **Çevrimdışı:** liste SW'de önce ağ, yoksa önbellek (`/api/islerim`); 24 saatten eski önbellek gösterilmez. Durum düğmeleri IndexedDB
  kuyruğuna (`depo/senkron.tsx` deseni) `istemci_id` + cihaz anıyla yazılır; üstte "2 işlem gönderilmeyi bekliyor"; iş başkasına geçmişse
  "Bu iş artık size ait değil; operasyon başka birine verdi." der ve kuyruktan düşürür.
- **Çıkış ve 401:** `oturum_bitti` / `gorev_degisti` / `hesap_kapali` → IndexedDB'deki iş kayıtları ve SW API önbelleği silinir, giriş ekranı.
  Cihaz kaybında yönetici Ekip'ten [Cihazlardan çıkış yaptır] der; telefon ilk bağlantıda verisini siler.
- **Sahadan erişim:** VPN + HTTPS gelene kadar liste ofis Wi-Fi'ında güncellenir; teknisyen BOSS Mobil'le de çalışabilir, BOSS durumları
  aktarımla yansır (§3.4). Masaüstünde aynı liste ortada 640 px.
- Boş: "Bugün size atanmış iş yok. Operasyon atayınca burada sıralı görünür."

### 6.10 Ekip (F12, F13)

```
┌ Ekip                                                               [+ Kişi ekle] ┐
│ ┌ Görevler artık dört çeşit ────────────────────────────────────────────────────┐ │
│ │ 8 kişi "Yönetici" görünüyor. Gerçek görevlerini seçin.        [Gözden geçir]  │ │
│ └───────────────────────────────────────────────────────────────────────────────┘ │
│ [Hepsi 10] [Satış 2] [Operasyon 0] [Teknik 0] [Yönetici 8]          🔍 Ara        │
│ ◯ A. K.      Teknik · Görükle, Özlüce        Aktif                            ›  │
│ ◯ Ayşe Y.    Operasyon                       Aktif                            ›  │
│ ◯ Can D.     Satış · Bölge 3                 Davet bekliyor                   ›  │
│ ◯ Deniz A.   Satış · Bölge 5                 Pasif                            ›  │
└───────────────────────────────────────────────────────────────────────────────────┘
```

- **Liste:** baş harf · ad · görev + bilgisi · durum (Aktif · Davet bekliyor · Davetin süresi doldu · Pasif). Telefon listede maskeli.
  Telefonda tablo yok; satıra dokununca kişi çekmecesi. Yatay kaydırma yok.
- **Kişi çekmecesi:** Ad · Telefon · **Görev** (dört parçalı segment, altında tek cümle):
  - Satış: "Bina listesi ve satış ziyaretleri. Kendi bölgesini görür." → **Bölge** (zorunlu)
  - Operasyon: "İş emirlerini dağıtır, randevu verir, müşteri bilgisini görür." → masa etiketleri (isteğe bağlı)
  - Teknik: "Yalnız kendisine atanan işleri görür ve durumunu işler." → Ev öbekleri (öbeklerin `sahip_id`'si) · BOSS'taki ekip adı ·
    Günlük kapasite (15) · "Teknik lider" anahtarı · "Bugün çalışmıyor"
  - Yönetici: "Her şeyi görür; ekip ve ayarları yönetir."
  Görev değişince: "Bu kişi bir kez yeniden giriş yapacak. PIN'i aynı kalır." Alt: **Kaydet** (birincil) · PIN'i sıfırla · Cihazlardan çıkış
  yaptır · Yeni davet kodu · **Kişiyi sil** (kırmızı metin; kendisi ve son yönetici için çizilmez).
- **Davet kodu** yalnız "Davet kodu hazır" çekmecesinde bir kez: "Kod: 123 456 · 48 saat geçerli. Kişiye iletin; ilk girişte kendi PIN'ini belirler."
- **Sil (F13):** önce `GET …/iliskiler`.
  - Kaydı yoksa: "Can D. kalıcı olarak silinsin mi? Bu işlem geri alınamaz." [Sil] [Vazgeç].
  - Yalnız öbek sahipliği varsa: "Can D. 2 öbeğin ev teknisyeni; silinirse öbekler teknisyensiz kalır." [Sil] [Vazgeç].
  - Kaydı varsa: "**Can D. silinemez.** 2 açık işi, 312 ziyareti, 1 ticket kaydı var. Kayıtlar korunmalı. Pasife alırsanız giriş yapamaz,
    geçmişi olduğu gibi kalır." [Pasife al] (birincil) [Vazgeç]. Açık işi varsa önce: "Önce 2 açık işi başka teknisyene aktarın." [İşleri aktar].
    Kayıtların hepsi gösterim verisiyse ek satır: "Bu kayıtların hepsi gösterim verisi; gösterim verisi temizlenince silinebilir."
- `window.confirm` hiçbir yerde kalmaz.

### 6.11 Takip — yönetici paneli (F11, F15, F17)

```
┌ Takip · 30 Eylül Salı                                            Son rapor 11:38 ┐
│ ┌ 24 saatte sonuç ┐ ┌ Atama süresi ─┐ ┌ 48 s aşan BTK ┐ ┌ Bugün kapasite ─────┐  │
│ │ %43             │ │ 9 dk          │ │ 5             │ │ 165 / 205            │  │
│ │ dün gelen 310   │ │ medyan · %82  │ │ en yaşlı 71 s │ │ Aşırı yük · +3 esnek │  │
│ │ ▁▂▃▅ 7 gün      │ │ ≤ 15 dk       │ │               │ │ Sahada 11 [− +]      │  │
│ └─────────────────┘ └───────────────┘ └───────────────┘ └──────────────────────┘  │
│ HIZ HATTI (bugün, medyan · hedefte)                                               │
│ BOSS→sistem 22 dk %71 │ ATAMA 9 dk %82 │ gördü 2 dk │ BOSS'a işlendi 14 dk │ yol 38 dk │ saha 71 dk │
│ BİRİKİM  24 saati aşan açık 288  ↘ −14/gün (7 gün)                                │
│ BTK  TV 6 s %20 · Bağlantı 12 s %30 · teşhis araması ≤45 dk %—                    │
│ ÖBEKLER   Öbek · Açık · Geciken · BTK · Atanmamış · Ev teknisyeni                  │
│ TEKNİK    Kişi · Atanan · Biten · Evde yok · Yolda/Sahada · İlk iş                 │
│ HİJYEN    Çözüldü ama BOSS'ta açık 4 · Askıda, uyanma yok 12 · BOSS'a işlenecek 7  │
│ SATIŞ (yönetici)  Bugün 142 ziyaret · 11 satış · 7/8 satışçı · Hafta 31/60 ▓▓▓░  [Satış ›] │
│ SİSTEM    Son yedek 30.09 19:30 · son güncelleme v5 · müşteri kartı açılışı bugün 41 · Yönetim kaydı › │
└───────────────────────────────────────────────────────────────────────────────────┘
```

- Dört kutu, dört soru: **Sözümüzü tutuyor muyuz?** (dün gelenlerin 24 s içinde çözülen/kapanan payı; kapanış anı kesin değilse ve pay %30'u
  aşıyorsa "yaklaşık") · **Hızlı mıyız?** (atama medyanı, ≤15 dk payı) · **BTK'yı kaçırıyor muyuz?** · **Yetiyor muyuz?** (§3.6).
- Her sayı tıklanınca İşler'i o süzgeçle açar. Renk yalnız hedef aşılınca girer; kutular varsayılan nötr. Veri yoksa "Bu hafta kayıt yok"
  (sıfır çubuk çizilmez). Telefonda kutular alt alta satır: değer sağa yaslı.
- **Satış bölümü (F15; yalnız yönetici):** `GET /api/takip/satis` — bugün/hafta ziyaret, temas, satış; haftalık hedef (varsa) ilerleme; huni
  (ziyaret → temas → satış); satışçı başına satır (bugün/hafta ziyaret, satış, dönüşüm); "Altyapısı çözülen bina: 3 (satışa döndü)"; gösterim
  verisi dahilse hap. [Satış ›] → Canlı durum. Canlı → "Bugün için görev ata" düğmesi o satışçıyı seçili açar (`/yonetici/atama/${id}`).
- Operasyon rolü manşet, hız hattı, birikim, BTK, öbek, teknik ve hijyen bölümlerini görür; satış ve sistem kayıtlarını görmez.

### 6.12 Giriş (C9)

- Fiziksel klavyeden rakam, Backspace ve Enter (telefon ve PIN adımlarında). Giriş sütunu (Devam dahil) en çok 360 px.
- Tek marka işareti: girişte, PWA simgesinde ve konsolda aynı.
- Girişten sonra `ana_ekran`; yöneticiye cihazda bir kez "Bu cihazda nereden başlayalım?" (§2.1).
- 401 `gorev_degisti` metni girişin üstünde bilgi şeridi olarak görünür.

### 6.13 Boş, hata, çevrimdışı durumları

| Yer | Metin | Eylem |
|---|---|---|
| İşler, hiç iş yok | "Henüz iş yok. BOSS'tan **Teknik Task Detay Raporu**'nu indirip buraya bırakın. Sistem kurulum işlerini ayıklar, her işi öbeğine koyar." | [Rapor seç] |
| İşler, v2'nin ilk açılışı | "Yeni sürüm iş emirlerini kalıcı saklıyor. Son raporu bir kez daha bırakın." | [Rapor seç] |
| Öbeğin işi yok | "Bugün Görükle'de iş yok. Yeni rapor gelince burada görünür." | — |
| Öbekte mahalle yok | §6.4 | [+ Mahalle ekle] |
| Kontrol boş | "✓ Bütün işler öbeğinde." | — |
| Aranacaklar boş | §6.6 | — |
| İşlerim boş | §6.9 | — |
| Ekip tek kişi | "Ekibinizi ekleyin: telefon numarası yeter; kişi ilk girişte kendi PIN'ini belirler." | [+ Kişi ekle] |
| Ticketlar boş | "Takipte ticket yok. Bir işte 'Ticket bağla' deyin ya da Excel'deki TICKET sayfasını aktarın." (CLI ipucu kalkar) | [Excel'den aktar] |
| Sunucuya ulaşılamıyor | İnce şerit: "Sunucuya ulaşılamıyor. Son bilgiler 14:05'ten. Yaptıklarınız telefonda bekliyor." | — |
| 403 | "Bu bölüm görevinize kapalı." | [Ana ekrana dön] |
| Rapor bayat | Başlıktaki hap amber/kırmızı: "Son rapor 1 s önce · BOSS'tan yeni raporu indirip bırakın" | — |

**İlk açılış ipucu** (kişi başına bir kez, `localStorage` try/catch; "Anladım" ile kapanır): İşler'de üç küçük balon —
**"1 Öbek seçin · 2 İşe dokunun · 3 Ata'ya basın"**.

### 6.14 Denetimden gelen mevcut ekran düzeltmeleri

| Öncelik | Düzeltme | Sahibi |
|---|---|---|
| P1 | İşler ekranı §6.1 ile yeniden kurulur (`IsEmirleri.tsx` menüden kalkar; eski adres yönlenir) | WP-C |
| P1 | Telefonda yönetici menüsü sabit blok değil, alt sekme çubuğu | WP-E |
| P1 | Ekip: davet kodu bir kez; 4 görev; sil; telefonda satır listesi | WP-E |
| P1 | Giriş: fiziksel klavye; 360 px; rol yönlendirmesi | WP-E |
| P1 | Koyu mod: `.yon-uyari*` türevleri, birincil düğme, öbek renk noktaları, demo hapı (§7.1) | WP-E |
| P2 | Kapsama ve Veri kalitesi: telefonda manşet sayıları alt alta satır; segment yatay kayar | WP-E |
| P2 | Canlı → "Bugün için görev ata" seçili satışçıyla (`/yonetici/atama/${id}`) | WP-E |
| P2 | Tek marka işareti; ~70 sabit renk kodu tokenlara (`yonetim.css`, `faz2.css`, `is_emri.css`) | WP-E |
| P2 | Bina kartlarında satışın `bina.obek` alanı "**Satış öbeği**" etiketiyle gösterilir (operasyon öbeğiyle karışmasın). Ticket metni şablonu (A7) **değişmez** | WP-E |

### 6.15 Kelime sözlüğü (ekranda iç jargon yok)

| İç terim / eski | Ekranda |
|---|---|
| triyaj, kontrol listesi, "Kontrol edilecek adresler" | **Kontrol gerekli** |
| parça, Böl (binaya göre), Süzüleni böl | **Ekiplere dağıt** |
| Böl (mahalleye göre) | **Öbeği ikiye böl** |
| bekliyor | **Atanmadı** |
| mahalle kaynağı: adres-yeni … | (yalnız ⓘ içinde) "Mahalle adresten bulundu" |
| ilçe merkezi (kaba) | **Konum yaklaşık** |
| rol | **Görev** |
| öbek | **Öbek** (kullanıcının kelimesi; ilk görüldüğü yerde ⓘ "Birlikte çalışılan mahalle grubu") |
| RES HP, yarıçap, SL | İş emri ekranlarında görünmez (SL yalnız "BOSS bilgisi ▸" içinde) |
| window.confirm "silinsin mi?" | Onay çekmecesi + Geri al |

`qa/v2/sozcuk-tarama.mjs` operasyon ve teknik ekranlarında şu sözcükleri arar ve bulursa kırılır: `triyaj`, `parça`, `Süzüleni`, `yarıçap`,
`RES HP`, `adres-yeni`, `kaba`, `bekliyor` (durum etiketi olarak).

---

## 7. Tasarım sistemi (F11, F14, F19)

**İlke:** satışçı uygulamasının sakin dili (Bugün, Bina, Sonuç çekmecesi — denetimde çıtayı tutan tek bölüm) yönetim ve teknik ekranlarına
taşınır; tersi yapılmaz.

### 7.1 Tokenlar (`saha_app/src/stil/temel.css :root` tek kaynak)

Koyu mod iki yoldan: `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` ve `:root[data-theme="dark"] {…}`.
"Görünüm: Sistem · Açık · Koyu" cihazda hatırlanır. `index.html` iki `<meta name="theme-color">` (media sorgulu: açık `#EFF1F5`,
koyu `#0F1319`). Her metin/zemin çifti ≥4,5:1 (30.09'da hesaplandı; QA betiği ölçer).

| Token | Açık | Koyu | Kullanım · kontrast |
|---|---|---|---|
| `--zemin` | `#EFF1F5` | `#0F1319` | Sayfa |
| `--kart` | `#FFFFFF` | `#181D26` | Kart, liste, çekmece |
| `--kart-bas` | `#F7F8FA` | `#1E242F` | Seçili satır, grup başlığı |
| `--cizgi` / `--cizgi-koyu` | `#E2E6ED` / `#CFD6E0` | `#2A313D` / `#3A424F` | Ayraç |
| `--metin` | `#101828` | `#EEF1F6` | 17,8:1 / 14,9:1 |
| `--metin-2` | `#525C6B` | `#AAB3C1` | ikincil (kartta ≥7:1) |
| `--metin-3` | `#626B7A` | `#9AA3B1` | üçüncül: zeminde 4,76:1 / kartta 6,6:1 |
| `--birincil` | `#0B63E5` | **`#2563EB`** | Dolgu düğme; beyaz yazı 5,34:1 / 5,17:1 (bugünkü koyu `#4D95FF` 2,98:1 idi) |
| `--birincil-bas` | `#0A4FB8` | `#1D4ED8` | Basılı |
| `--birincil-yazi` (yeni) | `#0B63E5` | `#7CB2FF` | Bağlantı, seçili sekme: 5,34:1 / 7,78:1 |
| `--birincil-yumusak` | `#E7F0FF` | `#15233D` | Seçili segment, çip (üstünde `--birincil-yazi` 4,66:1 / 7,22:1) |
| `--yesil` / `-yumusak` | **`#0B7A3F`** / `#E3F6EC` | `#3ECF82` / `#123024` | Kalan <%50: 4,82:1 / 7,09:1 (bugünkü açık `#0F8A4A` yumuşakta 3,92:1 idi) |
| `--amber` / `-yumusak` | **`#94500A`** / `#FFF2E0` | `#F0B45C` / `#33260F` | %50–80, bekleme 10 dk: 5,58:1 / 7,99:1 |
| `--kirmizi` / `-yumusak` | `#C02A2A` / `#FDEAEA` | `#FF8A8A` / `#3A1A1C` | ≥%80, gecikti, sil: 5,03:1 / 6,88:1 |
| `--mor` / `-yumusak` | `#6033C9` / `#EFE9FD` | `#B79BFF` / `#2A2140` | BTK, randevu dilimi: 6,30:1 / 6,58:1 |
| `--gri` / `-yumusak` | **`#5D6778`** / `#EEF1F5` | `#9AA3B2` / `#232A35` | Nötr rozet: 5,04:1 / 5,68:1 (bugünkü `#6E7889` 3,93:1 idi) |
| `--pasif-zemin` / `--pasif-yazi` | `#DFE4EC` / `#4A5462` | `#2A313D` / `#AAB3C1` | Pasif düğme |

- `.yon-uyari-*` kutuları koyuda **açık yazı + koyu renkli zemin** (`--kirmizi` üstünde `--kirmizi-yumusak`, `--amber` üstünde
  `--amber-yumusak`); bugünkü 1,6–1,7:1'lik kutular düzelir. Demo hapının koyu karşılığı `--amber` / `--amber-yumusak`.
- **Öbek paleti** (8 renk; yalnız 8 px nokta, öbek adı hep nötr `--metin`): açık `#0B63E5 #0B7A3F #94500A #B42318 #6033C9 #0E7490 #9D174D #4D7C0F`,
  koyu `#6EA8FF #3ECF82 #F0B45C #FF8A8A #B79BFF #5ED3F3 #F472B6 #A3E635` (kart üstünde ≥5:1 / ≥6,3:1).
- Haritada koyu modda varsayılan altlık "Sade".

### 7.2 Tipografi, boşluk, hedef, hareket

- Sistem yazısı (`-apple-system, "SF Pro Text", Roboto, "Segoe UI", sans-serif`). Boyutlar: 28/34 başlık · 22/28 bölüm · 17/22 satır başlığı ·
  15/20 gövde (masaüstü) — telefonda gövde 17 · 13/18 ikincil. **12 px'ten küçük yazı yok** (denetimde 10,5 px vardı). Kalınlık 400 / 600.
- Saat, sayaç, tablo rakamları `font-variant-numeric: tabular-nums`.
- Boşluk 4'ün katları (4 · 8 · 12 · 16 · 24 · 32); kart iç boşluğu 16; köşe kart 16, düğme/çip 12, rozet 8.
- Dokunma hedefi: telefonda ≥44 px (teknik ve satış birincil düğmesi 56 px, başparmak bölgesinde, alt yapışkan çubukta); masaüstünde liste içi
  ikincil eylem ≥32 px, birincil 40 px.
- Çekmece 200 ms ease-out; `prefers-reduced-motion` → hareket yok.

### 7.3 Bileşenler (`saha_app/src/ortak/`; sahibi WP-E)

| Bileşen | Dosya | Tanım |
|---|---|---|
| `Liste`, `ListeSatiri` | `ortak/Liste.tsx` | 2–3 satır; sol ek (hap/simge), sağ ek (rozet/ok/eylem); 44–72 px; tüm satır tıklanır; `content-visibility:auto` |
| `SureHapi` | `ortak/SureHapi.tsx` | `kalan_dk`, `renk`, `gecikti` → "2 s 10 dk" / "Gecikti · 17 s" + simge |
| `Saat` | `ortak/Saat.tsx` | Hedef + başlangıç + sunucu farkı; dakikada bir, son 60 dk saniyede bir yeniler |
| `Rozet` | `ortak/Rozet.tsx` | btk · ticket · tekrar · bayi · global · konum · boss_islenecek · boss_acik · yeniden · elle · kontrol |
| `DurumYazisi`, `AdimCizgisi` | `ortak/Durum.tsx` | Nötr yazı + nokta; 5 adımlık ince çizgi |
| `Cekmece` (var) + `Panel` | `ortak/Cekmece.tsx`, `ortak/Panel.tsx` | Masaüstünde sağdan 440 px, listenin üstüne biner; telefonda tam ekran / alttan; Esc ve kaydırarak kapanır |
| `Onay` | `ortak/Onay.tsx` | `window.confirm` yerine: başlık, tek cümle, iki düğme (yıkıcı olan kırmızı ve sağda) |
| `GeriAlBildirimi` | `ortak/Bildirim.tsx` (var) + eylem | 10 sn "Geri al" |
| `Segment` | `ortak/Segment.tsx` | 2–5 seçenek, sayaçlı; dar ekranda yatay kayar, taşmaz |
| `SuzDugmesi`, `SuzCipi` | `ortak/Suz.tsx` | Tek "Süz"; etkin süzgeç çipleri |
| `BaslikCubugu` | `ortak/Sayfa.tsx` (genişler) | 44 px; geri oku; sağda en çok 1 eylem ya da "…"; altında "Bu ekranda ne yaparım?" |
| `AltSekme` | `ortak/AltBar.tsx` (genişler) | Role göre 2–4 öğe; güvenli alan payı |
| `Manset` | `ortak/Manset.tsx` | Tek satır sakin sayılar; her sayı tıklanır |
| `DilimSecici` | `ortak/DilimSecici.tsx` | Gün çipleri + 2 saatlik dilim çipleri + teyit kutusu |
| `KisiSecici` | `ortak/KisiSecici.tsx` | Yazdıkça daralır; "A. K. · öbeğin · bugün 9/15" |
| `IlkIpucu` | `ortak/IlkIpucu.tsx` | Balonlar; `localStorage` try/catch |
| `BosDurum`, `Iskelet`, `HataKutusu` | var | Her listede |
| `Kbd` | `ortak/Kbd.tsx` | Tuş ipucu; dokunmatikte gizli |

`MahalleSecici`, `ObekSecici`, `TopluAtaKarti`, `IsSatiri` operasyon ekranlarına özgüdür (WP-C, `yonetici/isler/`).

### 7.4 Kırılım kuralları

| Genişlik | Yerleşim |
|---|---|
| ≥1200 | 3 bölme: öbekler 280 · liste esnek · çekmece 440 (listenin üstüne biner, sayfa yeniden akmaz) |
| 1024–1199 | Liste + çekmece; öbekler üstte seçici |
| 768–1023 | Tek liste; çekmece alttan yarım ekran |
| <768 | İtmeli gezinme; alt sekme; çekmece tam ekran; **iç içe kaydırma yok**; başlık eylemleri tek "…"/"+"; **tablo yok** |

Yönetici tabloları (Ekip, Öbekler, Kapsama, Veri kalitesi, Takip tabloları) 600 px altında satır listesine döner; manşet kutuları alt alta,
değer sağa yaslı. Hiçbir genişlikte yatay sayfa kaydırması yok. Doğrulanan genişlikler: **1440 · 1366 · 393** (+ 1024, 768), açık ve koyu.

---

## 8. İş paketleri (6 paralel ajan)

### 8.1 Dosya sahipliği (çakışma yok; paylaşılan dosyanın **tek** sahibi var)

| Dosya / klasör | Sahip |
|---|---|
| `saha/db.py`, `saha/goc.py` (yeni), `saha/sema_v2.py` (yeni), `saha/yetki.py` (yeni), `saha/yedekle.py`, `saha/sunucu.py`, `saha/ayarlar.py`, `saha/guvenlik.py`, `saha/api.py` (**tamamı**: lifespan, uçlar, router bağlama satırları), `saha/yonetim_uclari.py`, `saha/veri_kalitesi.py`, `saha/kur.py`, `saha/demo.py`, `saha/demo_temizle.py`, `saha/veri_araci.py`, `saha/ticket_aktar.py`, `saha/ticket.py`, `saha/simulasyon.py`, `saha/*.bat`, `saha/KORUNAN.txt`, `.gitignore`, `saha/testler/**` (conftest dahil) | **WP-A** |
| `operasyon/v2/**` (yeni), `operasyon/is_emri.py`, `operasyon/api.py`, `operasyon/yakinlik.py`, `operasyon/IS_EMRI_HAZIRLA.bat`, `operasyon/obekler.ornek.json` (yeni), `operasyon/testler/**`, `saha_app/src/is/tipler.ts` + `saha_app/src/is/sahte.ts` (yeni; 0. saatten sonra donar) | **WP-B** |
| `saha_app/src/yonetici/isler/**` (yeni: İşler, İş çekmecesi, Toplu ata, Kontrol, Aranacaklar, Rapor yükle, Rapor geçmişi, Yeni iş, Dağıt, klavye), `saha_app/src/yonetici/obekler/**` (yeni: Öbekler, Öbek çekmecesi, Mahalle seçici), `saha_app/src/is/api.ts` (yeni fetch istemcisi), `saha_app/src/yonetici/is_emri/**` (IsHaritasi yeniden kullanımı; `api.ts` + `is_emri.css` kaldırma), `saha_app/src/yonetici/ekran/IsEmirleri.tsx` (kaldırma) | **WP-C** |
| `saha_app/src/teknik/**` (yeni: İşlerim, İş ekranı, Bitti çekmecesi, kuyruk, api), `saha_app/src/sw.js`, `saha_app/src/depo/senkron.tsx`, `saha_app/src/depo/db.ts`, `saha_app/src/yonetici/takip/**` (yeni: Takip, Satış bölümü) | **WP-D** |
| `saha_app/src/stil/temel.css`, `saha_app/src/yonetici/yonetim.css`, `saha_app/src/yonetici/ekran/faz2.css`, `saha_app/index.html`, `saha_app/src/App.tsx`, `saha_app/src/yol/rota.tsx`, `saha_app/src/depo/oturum.tsx`, `saha_app/src/ortak/**` (yeni bileşenler + AltBar, Sayfa, BinaKimlik), `saha_app/src/ekran/Giris.tsx`, `saha_app/src/api/tipler.ts`, `saha_app/src/yonetici/index.tsx`, `saha_app/src/yonetici/ortak/**` (Kabuk, BinaAyrinti, parcalar), `saha_app/src/yonetici/api.ts`, `saha_app/src/yonetici/tipler.ts`, `saha_app/src/yonetici/depo.tsx`, `saha_app/src/yonetici/ekran/{Ekip,Canli,Kapsama,VeriKalitesi,Ticketlar}.tsx` | **WP-E** |
| `docs/SAHA_SOZLESME.md`, `docs/SAHA_KULLANIM.md`, `docs/GEREKSINIMLER.md`, `docs/OPERASYON_V2_SPEC.md` (yalnız "Değişiklik günlüğü" eki), `saha/prova_v2.py` (yeni), `saha_app/qa/v2/*.mjs`, karalama `eski_kod` anlık görüntüsü | **WP-F** |

Kural: başka paketin dosyasına ihtiyaç doğarsa sahibine yazılı istek gider (bu belgedeki arayüzler değişmez; değişiklik WP-F'nin günlüğüne
girer). `saha_app/src/is/tipler.ts` 0. saatten sonra yalnız WP-B tarafından ve günlüğe yazılarak değişir.

### 8.2 Paketler

#### WP-A · Temel: DB, göç, yetki, Ekip API, `saha/api.py`

- **Amaç:** Canlı veriyi bozmadan şemayı v5'e taşımak; dört rolü deny-by-default yetkiyle açmak; Ekip uçlarını (F12, F13) ve bütün `saha/api.py`
  değişikliklerini tek elden yapmak.
- **İş listesi:** §1 (tamamı: `goc.py`, `sema_v2.py`, `yedekle.goc_yedegi/aktarim_yedegi/saklama_uygula`, `db.bekleyen_gocler`, `db.semayi_kur` yeni
  davranışı, ziyaret kalıbı düzeltmesi, CLI sürüm denetimi, `sunucu.py` sırası ve kilidi, lifespan, ısınma yarışı, `kur`/`baslat.bat` korumaları,
  `GERI_YUKLE.bat`, `KORUNAN.txt`, `.gitignore`); §2 (tamamı: `yetki.py`, bütün rol denetimlerinin çevrilmesi, `/api/ben` dalları, IntegrityError
  → 409, async ağır uçlar); §5.3.1, §5.3.7, §5.3.8 uçları; `mevcut_kullanici`'de `gorev_degisti`; `yonetim_kaydi` yazımı; `veri_kalitesi` güvenli
  düzeltmelerinin `bina_degisim(kaynak='kalite')` izi; ticket güncellemesinde `akis.ticket_degisti` çağrısı; v2 yönlendiricilerinin bağlanması
  (`Bagimliliklar`) ve 0. saatte v2 için saplama (`operasyon.v2.api.yonlendiriciler` yoksa boş liste).
- **Bağımlılık:** WP-B'nin `sozluk.tohumla(conn, zaman)`, `obek.json_aktar(conn, yol, zaman)`, `akis.ticket_degisti(conn, ticket_id, k)`,
  `api.yonlendiriciler(b)` imzaları (0. saat; gövdeler gün 1 öğlene kadar). Göç testleri bu fonksiyonlar gelene kadar saplama ile koşar.
- **Kabul testleri:**
  - `saha/testler/test_goc.py`: `test_bos_db_hedef_surumde_kurulur`, `test_checksiz_eski_sema_v5e_cikar` (test_kalite ESKI_SEMA), `test_bilinmeyen_rol_rollback_turkce`,
    `test_cokme_enjeksiyonu[insert|drop|rename]`, `test_os_exit_alt_surec`, `test_ikinci_kosu_bos_yedek_yok`, `test_yasak_desen_7_tablo`,
    `test_port_doluyken_goc_yok`, `test_goc_yedegi_dogrulanir_salt_okunur_delete_journal`, `test_yedek_alinamazsa_goc_yok`, `test_yedek_gocler_oncesi`,
    `test_cli_surum_eskiyse_durur` (ticket_aktar, veri_araci, demo_temizle, kur), `test_kilit_bayat_10dk`, `test_sutun_kumesi_taze_ile_ayni`,
    `test_ziyaret_yeniden_kurma_guvenli_desen`, `test_kur_sifirla_gercek_kisi_reddi` — **F20**
  - `saha/testler/test_guncelleme_canli_kopya.py` (`SAHA_CANLI_YEDEK` yoksa skip) — §10'un 1–8. adımları — **F20**
  - `saha/testler/test_yetki_matrisi.py`: her rota × {satış, bölgesiz satış, operasyon, teknik, yönetici} × beklenen kod; `ROTA_IZNI`'nda olmayan rota
    testi kırar; bölgesiz teknik/operasyon `/api/bina`, `/api/harita`, `/api/yollar`, `/api/ozet/kapsama`, `/api/binalar/geometri`, `POST /api/ziyaret` → 403;
    `/api/ben` her rolde kendi dalı — **F6**
  - `saha/testler/test_ekip_v2.py`: `test_dort_gorev_kaydedilir`, `test_bolge_yalniz_satista`, `test_rol_degisince_gorev_degisti_401_pin_ayni`, `test_son_yonetici`,
    `test_kendi_rolu`, `test_davet_bir_kez_48s`, `test_eski_davet_kodu_gecerli`, `test_gorevler_toplu`, `test_yonetim_kaydi_yazilir`,
    `test_liste_davet_kodu_dondurmez` — **F12**
  - `saha/testler/test_kullanici_sil.py`: kaydı yok → 204 ve id yeniden kullanılmaz; ziyareti/işi var → 409 + sayılar; yalnız öbek sahipliği → `obekleri_birak`;
    kendini → 409; son yönetici → 409; FK hatası 503 değil 409 — **F13**
  - Var olan testler: `test_yetki.py`, `test_giris.py`, `test_duzeltmeler.py`, `test_bolgeleme.py` (bolge=0 davranışı korunur) yeşil; beklentiler gevşetilmez.

#### WP-B · İş motoru (operasyon)

- **Amaç:** İş emirlerini DB'de, Task No anahtarlı, uzlaşmalı ve ölçülür kılmak (F1–F5, F8–F10, F16–F18, F21'in sunucu tarafı).
- **Modüller (`operasyon/v2/`):**
  ```python
  # akis.py
  DURUMLAR: tuple[str, ...]; KOVALAR: dict[str, str]; SERITLER: dict[str, tuple[str, int|None]]
  KANAL_KURALLARI: list[tuple[str, str]]; GECISLER: dict[tuple[str, str], GecisKurali]
  def gecis(conn, is_no, yeni, k, *, surum=None, istemci_id=None, zaman=None, **alanlar) -> dict   # GecersizGecis, GuncelDegil, AlanEksik
  def ata(conn, is_no, teknik_id, k, *, randevu=None, surum, yine_de=False, toplu_id=None, kaynak="elle") -> dict
  def oneri_onayla(conn, isler: dict[str, int], k) -> dict
  def toplu_geri_al(conn, toplu_id, k) -> dict
  def ticket_degisti(conn, ticket_id: int, k: dict | None) -> list[str]
  def uyananlari_isle(conn, simdi) -> list[str]
  def trigger_sql() -> list[str]            # sema_v2 ile eşitliği test edilir
  # sozluk.py
  ILCELER: dict[str, list[str]]
  def tohumla(conn, zaman) -> dict          # WP-A göç v3 ve taze kurulum çağırır
  def sozluk_db(conn) -> ie.Sozluk          # bina + loc (normalleştirilmiş) + mahalle + eşad
  def ara(conn, q, il=None, ilce=None, limit=50) -> dict
  def ekle(conn, il, ilce, ad, k, benzerine_ragmen=False) -> dict   # BenzerVar, Var, IlceYok
  def koy_bicimi(adres: str) -> str | None
  # obek.py
  def json_aktar(conn, yol: Path, zaman) -> dict      # dosyayı YALNIZ okur
  def bul(conn, il_k, ilce_k, mahalle_k) -> int | None
  def yeniden_coz(conn, is_nolar=None) -> list[str]
  def olustur/adlandir/guncelle/mahalle_ekle/mahalle_cikar/sil/geri_al/bol(conn, …, k, surum)
  # aktarim.py
  def aktar(conn_fabrikasi, veri: bytes, dosya_adi, dosya_zamani, k) -> AktarimSonucu
  def uygula(conn_fabrikasi, aktarim_id, mod, k) -> AktarimSonucu ; def vazgec(...)
  # siralama.py
  def mod(conn, simdi) -> dict ; def sirala(isler, mod, simdi) -> list[str]
  def oneri_hesapla(conn, is_nolar=None, simdi=None) -> int ; def dilim_oner(conn, teknik_id, simdi) -> tuple[str, str]
  # gorunum.py
  def satir(conn, r, k) -> dict ; def ayrinti(conn, is_no, k) -> dict ; def kisa_adres(adres, bina) -> str | None
  def kisa_ad(ad) -> str                     # "Ayşe Kaya" → "Ayşe K."
  # takip.py
  def takip(conn, simdi, gun=7, tam=False) -> dict ; def satis(conn, simdi, gun=7) -> dict
  # saklama.py
  def uygula(conn, simdi) -> dict
  # api.py
  def yonlendiriciler(b: Bagimliliklar) -> list[APIRouter] ; eski_yonlendirici
  ```
- **Ayrıca:** `is_emri.py` — DB'den sözlük/loc (332/332), köy biçimleri, `filtre_istisnalari`, CLI'nin öbekleri DB'den salt okunur alması ve öbek
  tablosu yazma kipinin kapanması; `obekler.ornek.json`; `operasyon/v2/ornek/*.json`; `saha_app/src/is/tipler.ts` ve `sahte.ts` (0. saat).
- **Bağımlılık:** WP-A'nın `sema_v2` sabitleri ve `Bagimliliklar` (0. saat); `yetki.izin`.
- **Kabul testleri:**
  - `operasyon/testler/test_v2_obek.py`: `test_mahalle_ekle_cikar_is_sayisi` (**F1**), `test_son_mahalle_obegi_silmez`, `test_baska_obekte_409_ve_tasi`,
    `test_rapordisi_mahalle_ve_ilce_tamami` (Bursa/Gürsu/* ve elle eklenen "Göçmen", işi 0 öbek listede — **F2**), `test_23_ilce`,
    `test_sonraki_rapordaki_is_obege_duser` (**F2**), `test_ad_var_409`, `test_sil_geri_al`, `test_json_aktarim_14_120_bul_ayni` (gerçek JSON'un **kopyası**),
    `test_obekler_json_yazilmaz` (sha aynı), `test_benzer_ad_ve_esad`, `test_obek_surum_409`
  - `operasyon/testler/test_v2_aktarim.py`: `test_ayni_dosya_etkisiz` (DB özeti değişmez), `test_ters_sirali_ayni_icerik_0_yeni_atama_korunur`,
    `test_kaybolan_kapanir`, `test_yeniden_acilir_acilma_sayisi_2`, `test_cok_kaybolan_onay_ve_yeniden_hesap`, `test_eski_rapor_409_zorla_kismi_hic_kapatmaz`,
    `test_eszamanli_iki_yukleme_409`, `test_saglik_300ms_uvicorn` (127.0.0.1:8091), `test_yedek_alinir`, `test_hata_rollback`, `test_filtre_istisnasi_c5`,
    `test_koy_bicimi_yalova`, `test_lokasyon_sifirli_eslesir`, `test_lokasyon_db_332` (gerçek rapor varsa; yalnız sayı), `test_kontrol_yalniz_gercek_sorun`,
    `test_yeni_is_acik_ticketli_binada_altyapi` — **F4, F18**
  - `operasyon/testler/test_v2_akis.py`: `test_uctan_uca_durum_makinesi` (aktarım → randevu → ata → yolda → sahada → çözüldü → iş olmayan rapor →
    `kapandi/cozuldu_dogrulandi`; her adımda olay ve kişi — **F10**), `test_gecersiz_gecis_tum_ciftler_409`, `test_il_disi_elle_obek_kalici` (**F5**),
    `test_randevu_kurallari_ve_teknik_sirasi` (**F8**), `test_teknisyensiz_randevu`, `test_evde_yok_teyit_zorunlu`, `test_ticket_bagla_altyapi_cozulunce_doner`,
    `test_altyapi_engeli_409` (**F9**), `test_telefonda_cozuldu_tekrar_yasak`, `test_bayi_isi_ve_boss_bagla_toplam_artmaz`, `test_kanal_grubu_5_ornek` (**F16**),
    `test_boss_ileri_kurali`, `test_boss_ekip_eslesme_ve_esle_ucu`, `test_surum_409`, `test_toplu_ata_geri_al`, `test_istemci_id_idempotent`,
    `test_trigger_listesi_akis_ile_ayni`
  - `operasyon/testler/test_v2_isler_api.py`: `test_obek_isleri_alanlar` (operasyon: müşteri, kısa adres, task, durum, kalan, randevu, atanan — **F3**),
    `test_teknik_yalniz_kendi_isi_digerine_404` (**F7**), `test_musteri_alanlari_rol` (anahtar yoksa yok; teknik kapanınca görmez — **F21**),
    `test_erisim_kaydi_gunde_bir`, `test_saklama_30_gun_hmac` (saat ileri), `test_excel_rol_ve_kayit`, `test_degisim_imleci`, `test_eski_uclar_410`,
    `test_ornek_yanitlar_sema_uyumu`
  - `operasyon/testler/test_v2_takip.py`: `test_atama_suresi_dondurulmus_saat` (10:00 aktarım, 10:09 atama → medyan 9 dk, oran; yeniden açılan saati sıfırlar;
    BOSS ataması ölçüye girmez — **F17**), `test_hiz_hatti_adimlari`, `test_kapasite_modu`, `test_siralama_asiri_yuk_deterministik`,
    `test_satis_ozet_gun_ile_ayni` (**F15**)
  - `operasyon/testler/test_is_emri.py` (güncellenir): makro testleri aynen yeşil; `test_api_*` → 410

#### WP-C · Operasyon konsolu arayüzü

- **Amaç:** İşler panosu (masaüstü + telefon), iş çekmecesi, toplu atama, Kontrol, Aranacaklar, Öbekler + mahalle seçici, rapor yükle/geçmiş,
  yeni iş, ekiplere dağıt, klavye (§6.1–§6.8).
- **Dışa açtığı:** `saha_app/src/yonetici/isler/index.ts` → `Isler`, `Aranacaklar`, `RaporGecmisi`; `saha_app/src/yonetici/obekler/index.ts` →
  `Obekler`. WP-E bunları `yonetici/index.tsx`'e bağlar.
- **Bağımlılık:** WP-B `tipler.ts` + `sahte.ts` (0. saat; sahte kipte başlar); WP-E tokenlar ve ortak bileşenler (gün 1 öğlen; o saate kadar
  var olan `Cekmece`, `Bildirim`, `parcalar` ile); WP-B uçları (gün 1 akşam).
- **Kabul testleri** (Playwright betikleri WP-F'nindir; WP-C çalıştırır ve kırmızıyı düzeltir): `qa/v2/obek-duzenle.mjs` (**F1**: çekmece mahalleleri
  listeler, ⊖ ile çıkan mahalle yenilemesiz kaybolur, pano sayısı değişir; 1440 ve 393), `qa/v2/mahalle-secici.mjs` (**F2**: "gursu" → İlçenin tamamı,
  23 ilçe, "Göçmen" listede yok → ekle), `qa/v2/obek-isleri.mjs` (**F3**: öbeğe tıkla → ≥1 satır, satır sayısı = sayaç; telefonda öbek → işler →
  iş itmeli gezinme), `qa/v2/kontrol-elle-obek.mjs` (**F5**), `qa/v2/ticket-rozet.mjs` (**F9**), `qa/v2/yeni-is.mjs` (**F16**), `qa/v2/rapor-yukle.mjs`
  (**F18**: fark satırı, aynı dosya metni, onay çekmecesi), `qa/v2/bekleme.mjs` (**F17**: "geleli N dk", 10/15 dk renk), `qa/v2/ilk-gun.mjs` (**F14**:
  girişten ilk atamaya ≤5 etkileşim: bırak → öbek → Ata; `window.confirm` hiç çağrılmaz)

#### WP-D · Teknik telefon arayüzü + Takip paneli

- **Amaç:** Teknisyenin "İşlerim"i (çevrimdışı, tek büyük düğme, "Evde miydi?" zorunlu; F7, F8) ve yönetici Takip paneli (F11, F15, F17).
- **Dışa açtığı:** `saha_app/src/teknik/index.ts` → `Islerim`; `saha_app/src/yonetici/takip/index.ts` → `Takip`.
- **Ayrıca:** `sw.js` — `/api/islerim`, `/api/isler*` GET önce ağ, yoksa önbellek; `/api/isler/degisim` önbelleğe alınmaz; çıkışta ve 401'de API
  önbelleği + IndexedDB iş kayıtları silinir; `depo/db.ts` + `senkron.tsx` — teknik durum yazmaları için kuyruk (`istemci_id`).
- **Bağımlılık:** WP-B tipler/sahte (0. saat), WP-A `/api/ben.ana_ekran` (gün 1 öğlen), WP-E bileşenler.
- **Kabul testleri:** `qa/v2/teknik-islerim.mjs` (**F7, F8**: iki tarayıcı bağlamı — operasyon atar, teknik 20 sn içinde listede görür; sıra randevuya göre;
  Yola çıktım → İşe başladım → Bitti; "Evde miydi?" seçilmeden Bitti olmaz; çevrimdışı basış kuyruğa girer, bağlanınca gider),
  `qa/v2/akis-uctan-uca.mjs` (**F10**, iki bağlam), `qa/v2/takip.mjs` (**F11, F15, F17**: dört kutu, hız hattı, satış bölümü sayıları API ile aynı,
  sayıya tıklayınca İşler süzülür).

#### WP-E · Kabuk, tasarım sistemi, roller arayüzü, Ekip

- **Amaç:** Tek tasarım dili (tokenlar, koyu mod, bileşenler), role göre yönlendirme ve menü, telefon sekme çubuğu, giriş, Ekip (4 görev, gözden
  geçir kartı, sil akışı, davet bir kez), denetimin mevcut ekran düzeltmeleri (§6.14) (F6, F11, F12, F13, F14, F19).
- **Sıra:** tokenlar + `Liste`, `SureHapi`, `Rozet`, `Onay`, `GeriAlBildirimi`, `Segment`, `Suz`, `BaslikCubugu`, `AltSekme`, `Panel` **gün 1 öğlene
  kadar** (C ve D kullanır); sonra `App.tsx`/`oturum.tsx`/`rota.tsx` yönlendirmesi, `Kabuk.tsx` menüsü, `Giris.tsx`, `Ekip.tsx`; gün 2 koyu mod ve
  telefon düzeltmeleri.
- **Bağımlılık:** WP-A `/api/ben` (`ana_ekran`, `izinler`), Ekip uçları; WP-C/WP-D dışa açtığı ekranlar (gün 1 akşam bağlanır; öncesinde yer tutucu).
- **Kabul testleri:** `qa/v2/rol-girisleri.mjs` (**F6**: dört rol kendi ana ekranında açılır; izinsiz adreste 403 ekranı; menü role göre),
  `qa/v2/ekip.mjs` (**F12**: 4 görev, bölge yalnız Satış'ta, görev değişince uyarı cümlesi), `qa/v2/ekip-sil.mjs` (**F13**: kaydı olana uyarı +
  "Pasife al"; kaydı olmayan silinir; `window.confirm` çağrılmaz), `qa/v2/giris-klavye.mjs` (fiziksel klavye, 360 px),
  `qa/v2/matris.mjs` (**F11, F19**: İşler, İş çekmecesi, Öbekler, Aranacaklar, Takip, Ekip, İşlerim, Giriş × 1440/1366/393 × açık/koyu: 0 yatay
  taşma, görünür alanda en çok 1 birincil düğme, telefonda <44 px hedef 0, hesaplanmış kontrast <4,5:1 → 0, konsol hatası 0),
  `qa/v2/sozcuk-tarama.mjs` (**F14**).

#### WP-F · Belgeler, QA altyapısı, yükseltme provası

- **Amaç:** "Üret → test et → düzelt → tekrarla" döngüsünü ölçülür kılmak (F22), canlı kopyada yükseltme provası (F20), kullanıcı belgeleri.
- **İş listesi:**
  - **0. saat, herkesten önce:** mevcut kodun anlık görüntüsü → karalama `eski_kod/` (`saha/`, `operasyon/`, `dsale/`, `saha_app/dist/`; `saha.db`,
    `gizli.key`, `yedek/` **hariç**); taban test koşusu (≈213 yeşil) kaydı.
  - `saha/prova_v2.py` (§10'u tek komutla yürütür; hedef yol canlı `saha/saha.db`'ye çözülürse reddeder).
  - `saha_app/qa/v2/*.mjs` betiklerinin hepsi (ortak yardımcı: giriş, ekran görüntüsü `qa/v2/<betik>/`, kontrast ölçer, hedef ölçer, taşma ölçer).
  - `docs/SAHA_SOZLESME.md` §8 (v2 uçları, bu belgeye atıfla), `docs/SAHA_KULLANIM.md` (İşler, Öbekler, Aranacaklar, İşlerim, Ekip, Takip, **Güncelleme
    günü**, **Geri dönüş**), `docs/GEREKSINIMLER.md` §F durumları (her yinelemede; test adıyla).
  - **F14 elle testi protokolü:** kullanıcı (operasyon lideri) gün 2 öğleden sonra, sistemi hiç görmemiş bir çalışanla 15 dakikalık oturum yapar:
    "Bu rapordaki Görükle işlerini teknisyene atayın." — rehbersiz; süre ve takıldığı yerler not edilir; ölçüt ilk atama ≤ 2 dk. Sonuç GEREKSINIMLER F14 notuna yazılır.
- **Bağımlılık:** WP-A göç (gün 1 akşam) prova için; bütün arayüz paketleri (gün 2) matris için.
- **Kabul testleri:** `saha/prova_v2.py` raporu yeşil (§10), `qa/v2/matris.mjs` JSON çıktısında eşik aşımı 0, GEREKSINIMLER §F güncel (**F20, F19, F22**).

### 8.3 Takvim ve kapılar (2 gün)

| Zaman | WP-A | WP-B | WP-C | WP-D | WP-E | WP-F |
|---|---|---|---|---|---|---|
| G1 0–1 s | `sema_v2.py`, `yetki.py` iskeleti, `Bagimliliklar` + saplama bağlama | `tipler.ts`, `sahte.ts`, `ornek/*.json`, fonksiyon imzaları (saplama) | sahte kipte İşler iskeleti | sahte kipte İşlerim iskeleti | tokenlar | **eski kod anlık görüntüsü**, taban test koşusu |
| G1 1–4 s | `goc.py` v1–v5 + yedek + testler (karalama kopyası) | `sozluk`, `obek`, `json_aktar`, `tohumla` | İşler 3 bölme + telefon | İşlerim + kuyruk | bileşenler (öğlen teslim) | `prova_v2.py`, QA yardımcıları |
| G1 4–8 s | rol denetimleri, `/api/ben`, Ekip uçları, lifespan/sunucu sırası | `aktarim`, `akis`, `siralama`, `gorunum`, `api` | iş çekmecesi, toplu kart, Kontrol | Takip | yönlendirme, Kabuk, Giriş, Ekip | matris, rol, ilk-gün betikleri |
| **Kapı G1** | `pytest` yeşil; canlı kopyada göç provası (§10 1–5) | gerçek raporla iki aktarım: ikincisi etkisiz; 332/332 | 1440 + 393 ekran görüntüsü (sahte) | aynı | rol girişleri e2e (sahte) | prova raporu |
| G2 0–3 s | Sahteler kalkar; 127.0.0.1:8090–8099'da canlı kopya + gerçek rapor; F10 uçtan uca iki tarayıcıda — **herkes** |
| G2 3–5 s | `matris.mjs` (F19), `sozcuk-tarama` (F14), `ilk-gun` (F14), performans bütçeleri (§5.6); bulgular sahibine — **herkes** |
| G2 5–7 s | Düzelt → tekrar koş (döngü); "eski kod + yeni DB" smoke (§10-9) | | | | | |
| G2 7–8 s | GEREKSINIMLER §F, SAHA_KULLANIM (Güncelleme günü), kullanıcıya kısa durum raporu (yalnız toplam) — WP-F; F14 elle testi — kullanıcı |

**Bitti sayılır, eğer:** 213 + yeni testlerin hepsi yeşil; canlı kopya yükseltme provası yeşil; gerçek raporda 437 iş, 437 öbek eşleşmesi (bugünkü
JSON motoruyla aynı), Lokasyon 332/332; matris eşikleri 0; T-F14 elle testi yapıldı; canlı `saha.db` ve `obekler.json`'a dokunulmadığı (araçların
yalnız karalama yollarıyla çalıştığı) prova günlüğünde gösterildi; kullanıcıya güncelleme günü talimatı verildi.

### 8.4 Ortak kurallar

§0.3'ün hepsi. Ek olarak: her paket kendi testini yazar ve **başka paketin testini değiştirmez**; `tsc --noEmit` ve `vite build` yeşil kalır; yeni
metinlerde Türkçe harf; kişisel veri içeren örnek yazılmaz (sahte veride uydurma ad, `5550000000` gibi gerçek olmayan numara).

---

## 9. Kabul testleri: F1–F22 eşlemesi

| F | Kabul ölçütü | Test(ler) | Paket |
|---|---|---|---|
| F1 | Öbek açılınca mahalleleri görünür; çıkar/ekle; iş sayıları aynı yanıtta güncellenir; son mahalle çıkınca öbek kalır | `test_v2_obek.py::test_mahalle_ekle_cikar_is_sayisi`, `::test_son_mahalle_obegi_silmez`; `qa/v2/obek-duzenle.mjs` | B, C |
| F2 | Rapor dışı mahalle (Gürsu/*, elle "Göçmen") öbeğe eklenir; 23 ilçenin her birinde "İlçenin tamamı"; sonraki rapordaki iş o öbeğe düşer | `test_v2_obek.py::test_rapordisi_mahalle_ve_ilce_tamami`, `::test_23_ilce`, `::test_sonraki_rapordaki_is_obege_duser`; `qa/v2/mahalle-secici.mjs` | B, C |
| F3 | Öbeğe tıkla → işler: müşteri, adres, task, durum, kalan süre, randevu, teknisyen; satır sayısı = sayaç | `test_v2_isler_api.py::test_obek_isleri_alanlar`; `qa/v2/obek-isleri.mjs` | B, C |
| F4 | Location Id varsa OneMap binasının mahallesi; sıfırlı Lokasyon eşleşir; 332/332; kontrol yalnız gerçek sorun | `test_v2_aktarim.py::test_lokasyon_db_332`, `::test_lokasyon_sifirli_eslesir`, `::test_kontrol_yalniz_gercek_sorun` | B |
| F5 | İzmir → Kontrol (`il_disi`); elle öbeğe atanır; yeniden yüklemede korunur | `test_v2_akis.py::test_il_disi_elle_obek_kalici`; `qa/v2/kontrol-elle-obek.mjs` | B, C |
| F6 | Her rol kendi ana ekranında; yasak uçlar 403; bölgesiz yeni rol şehri göremez, ziyaret yazamaz | `test_yetki_matrisi.py`; `qa/v2/rol-girisleri.mjs` | A, E |
| F7 | Operasyon atar → teknik İşlerim'de görür (≤20 sn v2.0); başka işe 404 | `test_v2_isler_api.py::test_teknik_yalniz_kendi_isi_digerine_404`; `qa/v2/teknik-islerim.mjs` | B, D |
| F8 | Tarih + 2 saatlik aralık; geçersiz 422; İşlerim randevuya göre sıralı | `test_v2_akis.py::test_randevu_kurallari_ve_teknik_sirasi`, `::test_teknisyensiz_randevu`; `qa/v2/teknik-islerim.mjs` | B, D |
| F9 | Ticket bağlanınca Altyapı + rozet; açık ticket'lı binaya atama 409; ticket çözülünce iş döner | `test_v2_akis.py::test_ticket_bagla_altyapi_cozulunce_doner`, `::test_altyapi_engeli_409`; `test_v2_aktarim.py::test_yeni_is_acik_ticketli_binada_altyapi`; `qa/v2/ticket-rozet.mjs` | B, C |
| F10 | Rapor → randevu → ata → yolda → sahada → çözüldü → kapandı; geçersiz her çift 409 | `test_v2_akis.py::test_uctan_uca_durum_makinesi`, `::test_gecersiz_gecis_tum_ciftler_409`; `qa/v2/akis-uctan-uca.mjs` | B, D |
| F11 | Takip paneli; her görünümde ≤1 birincil; demo bandı operasyon ekranlarında yok; `window.confirm` yok | `qa/v2/matris.mjs`, `qa/v2/takip.mjs` + ekran görüntüsü incelemesi (elle) | D, E, F |
| F12 | 4 görev; bölge yalnız Satış'ta; CHECK 'hacker' reddi; görev değişince `oturum_no+1`, PIN aynı | `test_ekip_v2.py`; `test_goc.py`; `qa/v2/ekip.mjs` | A, E |
| F13 | İşi olan silinmez (409 + sayılar + Pasife al); işi olmayan silinir; kendini/son yönetici korunur; 503 değil 409 | `test_kullanici_sil.py`; `qa/v2/ekip-sil.mjs` | A, E |
| F14 | Yeni başlayan rehbersiz ilk işi ≤2 dk'da atar; vekil: ≤5 etkileşim, "Bu ekranda ne yaparım?" var, jargon 0 | `qa/v2/ilk-gun.mjs`, `qa/v2/sozcuk-tarama.mjs` + **elle protokol** (§8.2 WP-F) | C, E, F |
| F15 | Takip'te satış bölümü; sayılar `/api/ozet/gun` ile aynı; karttan Canlı durum | `test_v2_takip.py::test_satis_ozet_gun_ile_ayni`; `qa/v2/takip.mjs` | B, D |
| F16 | Bayi işi `B-…`; kanal grubu türetilir; BOSS'a bağlanınca aynı satır güncellenir | `test_v2_akis.py::test_bayi_isi_ve_boss_bagla_toplam_artmaz`, `::test_kanal_grubu_5_ornek`; `qa/v2/yeni-is.mjs` | B, C |
| F17 | Gelişten ilk karara süre her iş için ölçülür; atanmamış satırda saat; Takip'te medyan, p90, ≤15 dk payı | `test_v2_takip.py::test_atama_suresi_dondurulmus_saat`, `::test_hiz_hatti_adimlari`; `qa/v2/bekleme.mjs` | B, C, D |
| F18 | Aynı rapor iki kez → çift kayıt yok; kapanan/yeniden açılan yakalanır; eksik/eski rapor bekçisi; atamalar korunur | `test_v2_aktarim.py` (hepsi); `qa/v2/rapor-yukle.mjs` | B, C |
| F19 | 1440 · 1366 · 393 × açık/koyu; taşma 0; hedef ≥44; kontrast ≥4,5; konsol hatası 0 | `qa/v2/matris.mjs` | E (+C, D düzeltir) |
| F20 | Canlı kopyada güncelleme: kişiler, PIN'ler, ziyaretler aynen; göç öncesi doğrulanmış yedek; çökme güvenli; ikinci açılış etkisiz | `test_goc.py`, `test_guncelleme_canli_kopya.py`, `saha/prova_v2.py` | A, F |
| F21 | Operasyon müşteri adını/no'yu görür; teknik yalnız kendi açık işinde; satış hiç; erişim kaydı; 30 gün sonra NULL/HMAC | `test_v2_isler_api.py::test_musteri_alanlari_rol`, `::test_erisim_kaydi_gunde_bir`, `::test_saklama_30_gun_hmac` | B |
| F22 | Her yinelemede §F durum ve test adları güncel; "ne bitti / ne kaldı" tek tablo | GEREKSINIMLER farkı + WP-F durum raporu | F |

---

## 10. Yükseltme test prosedürü (canlı kopya) — `saha/prova_v2.py`

Tek komut: `.venv/Scripts/python.exe -m saha.prova_v2 --hedef <karalama>/prova --rapor "C:/Users/EXT03426951/Desktop/TeknikTaskDetayRaporu.xlsx"`.
Canlı dosyaya **yazmaz**; `SAHA_DB`, `OPERASYON_OBEK`, `OPERASYON_VERI`, `SAHA_GIZLI` karalama yollarını gösterir; hedef canlı `saha/saha.db`'ye
çözülürse "Canlı veritabanında prova yapılmaz." der ve çıkar. Çıktı yalnız toplam sayı.

1. **Kopya:** kaynak canlı `saha/saha.db` → `file:…?mode=ro` + backup API → `prova/a.db` (ya da `--kaynak saha/yedek/saha-2026-09-30.db`,
   `mode=ro&immutable=1`). Kaynakta -wal/-shm oluşmadığı (yedek dosyasıysa) denetlenir. `obekler.json` → `prova/obekler.json` (kopya).
2. **Hazırlık (yalnız kopyada):** iki kişiye test PIN'i yazılır (biri yönetici, biri satış) — ÖNCE anlık görüntüsünden önce. Jetonlar test
   anahtarıyla (`SAHA_GIZLI`) üretilir; gerçek `gizli.key` okunmaz.
3. **Önce anlık görüntü:** her tablonun satır sayısı ve `rowid` sıralı sha256'sı; `kullanici` 10 sütun özeti; `sqlite_sequence`; FK hedefleri; şema metni.
4. **Eski kodla taban:** `eski_kod/` anlık görüntüsünden sunucu `127.0.0.1:8094` (a.db'nin kopyası üzerinde): `/api/saglik` 200, yönetici ve satış
   jetonuyla `/api/ben` 200. Sunucu kapatılır.
5. **Göç:** `python -m saha.goc --db prova/a.db`. Beklenen (30.09 verisiyle):
   - `user_version = 5`; `sema_goc` 5 satır; göç yedeği `prova/yedek/goc/saha-oncesi-v0-v5-*.db` var, salt okunur, `journal_mode=delete`,
     `integrity_check=ok`, satır sayıları kaynakla aynı.
   - `integrity_check=ok`, `foreign_key_check` 0 satır; kullanici'ye bakan bütün FK'ların hedefi `kullanici` (13).
   - Eski tabloların hepsi satır satır aynı (`ayar` hariç: +1 `obek_surumu` ve v4 varsayılanları); `kullanici` 10/10 aynı, 15 sütun; seq ≥ 19.
   - CHECK `teknik`/`operasyon` kabul, `hacker` ret.
   - 23 ilçe; sözlük ≥ 663; 14 öbek, 120 ref, 0 çakışma; her ref için DB `bul` = JSON `bul`; `prova/obekler.json` sha256'sı değişmedi.
   - `db.bekleyen_gocler` boş; ikinci `goc.hazirla` → `bos=True`, yeni yedek yok.
6. **Yeni kodla oturum:** yeni sunucu `127.0.0.1:8095` (a.db): 2. adımın jetonlarıyla `/api/ben` 200 (açık telefonlar oturumda kalır); bir kişinin
   görevi API'yle `teknik` yapılır → eski jetonu 401 `gorev_degisti`, PIN ile giriş 200, `/api/ben.ana_ekran = 'islerim'`; pin_hash değişmedi.
7. **Gerçek rapor (yalnız 8095'e):** aktarım → 437 iş; öbeği belli iş sayısı bugünkü JSON motoruyla aynı (437); Lokasyon eşleşmesi 332/332;
   kontrol sayısı raporlanır; aktarım sırasında paralel `/api/saglik` < 300 ms. Aynı dosya ikinci kez → `ayni_dosya`, DB özeti değişmez.
   Satır sırası ters çevrilmiş kopya (karalamada üretilir, yalnız 8095'e) → 0 yeni, 437 aynı/değişen; önceden yapılan 3 atama ve 1 randevu
   korunur. Bir işi çıkarılmış kopya → o iş `kapandi`; asıl dosya tekrar (farklı sha için 1 hücre değişmiş kopya) → `yeniden_acildi`.
8. **Çökme enjeksiyonu** (ayrı kopyalarda): v1 INSERT/DROP/RENAME sonrası istisna ve `os._exit` ile öldürülen alt süreç → DB birebir göç öncesi,
   `user_version=0`. Yasak desen: 7 tablonun REFERENCES'ı bozulur (test kilidi).
9. **Eski kod + yeni DB (geri dönüş güvenliği):** göç edilmiş kopyanın kopyasında `eski_kod/` sunucusu 8094: `/api/saglik` 200, giriş 200,
   `/api/ben` 200, `GET /api/bina` 200, satış jetonuyla `POST /api/ziyaret` 200; eski `gocler` şemayı bozmaz (`kullanici` tanımı ve FK hedefleri aynı,
   `integrity_check=ok`). **Not:** eski kod `teknik` rolünü tanımaz (bölgesiz → şehir geneli açığı geri gelir); bu yüzden geri dönüş yolu
   **GERI_YUKLE.bat ile göç öncesi yedek + önceki klasördür**, eski kodu yeni veritabanıyla çalıştırmak değil (SAHA_KULLANIM'da yazılı).
10. **Temizlik:** 8094/8095 kapatılır; karalama klasörü kalır (kullanıcı verisi silinmez); rapor: yalnız sayılar, süreler, geçti/kaldı.

---

## 11. Güncelleme günü (kullanıcı talimatı) ve geri dönüş

Önkoşul: §10 provası aynı gün yeşil. Zaman: mesai sonu (19:30 yedeğinden sonra).

1. `saha\DURDUR.bat`.
2. `saha\YEDEK.bat` (günlük yedek; ayrıca göç kendi yedeğini alacak).
3. Yeni sürüm dosyalarını kopyalayın; `saha\KORUNAN.txt`'teki yolların **üzerine yazmayın** (`saha.db*`, `gizli.key`, `yedek\`, `kayit\`,
   `operasyon\obekler.json`, `operasyon\veri\`, `data\raw\gelen\`).
4. `saha\baslat.bat` → konsolda "GÜNCELLEME TAMAM (v0 → v5) · 10 kişi (2 PIN) · 1.257 ziyaret · 19.706 bina aynen korundu · 14 öbek / 120 mahalle
   aktarıldı · yedek: …" satırını görün. "GÜNCELLEME DURDU" görürseniz veritabanı değişmemiştir; ekranın fotoğrafını gönderin.
5. Telefonlar: açık oturumlar sürer; kimsenin PIN'i değişmez.
6. Ekip → **Görevleri gözden geçirin**: 8 kişinin gerçek görevini seçin (en az bir Yönetici kalır).
7. Ticketlar → **Excel'den aktar** (TICKET sayfası; 198 satır) — ticket rozetleri ve otomatik Altyapı bunu ister.
8. İşler → son BOSS raporunu **bir kez daha bırakın** (eski kayıt pickle'dan taşınmaz).
9. Öbekler → Göçmen'i (ilçesini seçerek) ve gerekirse "Gürsu · ilçenin tamamı"nı ekleyin; teknisyen varsa her öbeğe ev teknisyenini seçin.
10. İşler → "Eşleşmemiş BOSS ekibi" satırından BOSS ekip adlarını kişilerle eşleyin.

**Geri dönüş:** `saha\DURDUR.bat` → `saha\GERI_YUKLE.bat` → listeden `yedek\goc\saha-oncesi-v0-v5-…` yedeğini seçin (mevcut dosya
`saha-hatali-<zaman>.db` olarak kenara konur, silinmez) → **önceki sürüm klasöründen** `baslat.bat`. Güncellemeden sonra yapılan atama/randevular
geri dönüşte kaybolur (yedek güncelleme anındadır). Makro yolu (`IS_EMRI_HAZIRLA.bat`) iki sürümde de çalışır.

---

## 12. Varsayılan kararlar (karar gelene kadar uygulanan; OPERASYON_TASARIM kararlarından)

1. **Rol adı `teknik`**; teknik lider ve masa türleri **etiket** (yetki vermez). OT §5.1'deki `teknisyen/teknik_lider` rolleri açılmaz.
2. **Göç rol değiştirmez**: bugün yönetici olan 8 kişi yönetici kalır; kullanıcı Ekip'te "Görevleri gözden geçirin" ile atar; kimse erişim kaybetmez;
   son yönetici korunur; geçiş dönemi `yonetim_kaydi` ile izlenir.
3. **Giriş:** birim kutusu yok, rol yönlendirir; yalnız yöneticiye cihazda bir kez "Nereden başlayalım?" (varsayılan İşler) — C9 böyle karşılanır.
4. **Yönetici ana ekranı İşler** (kullanıcı operasyon lideri); operasyon → İşler; teknik → İşlerim; satış → Bugün.
5. **F21:** operasyon + yönetici tam müşteri adı/no/adres; teknik yalnız kendine atanmış açık işte kısa ad + no + adres; satış hiçbiri; her görüntüleme
   kayıtlı; kapanış + 30 gün → ad/adres NULL, no → HMAC özeti; ham dosya 7 gün; Excel yalnız iki rol ve kayıtlı.
6. **Müşteri telefonu tutulmaz** (`musteri_tel='kapali'`); arama BOSS/Maya'dan, "Müşteri No'yu kopyala" ile.
7. **Temas politikası KARMA-2** (OT karar 3): aramasız sevk; randevu = tahmini varış dilimi, aramadan; "saat teyitli" tek kutu; ulaşılamayan işe
   teyitsiz ikinci gidiş yok; varsayılan 11:00 yasak (OT karar 9).
8. **Hedef:** 24 s söz ana gösterge; BTK sırası FOX hedefiyle (TV 6, Bağlantı/Arama 12, Doping 24) (OT karar 2).
9. **Aşırı yük sırası:** KARMA-2 kural 5'in yalın hâli (OT karar 4a); "en yakın 5" v2.1.
10. **Dilim ve kapasite:** 2 saatlik dilimler 08–20; teknisyen başı günde 15 iş; gün başlangıcı 08:30; kapasite varsayılanı = bugün işi olan aktif
    teknik sayısı, sabah −/+ ile düzeltilir.
11. **Kanal eşlemesi:** GLOBAL → global; DEHA/DEHANET → Bayi (dehanet); diğer bayi; TURKCELL → kurumsal; boş (bugün 53) → "Kanal bilinmiyor", rozet yok.
12. **Bayi işi** `B-AAGGAA-NNN`; BOSS işiyle **otomatik birleşme yok**, yalnız "BOSS Task No'yu bağla" (sistem tek adayda öneri çipi gösterir).
13. **Filtre (C5 ↔ C17):** C17 kuralı korunur; tek istisna C5/OT §3.1: "Kurulum Taskı Ürememiş" mevcut müşteride kalır (`filtre_istisnalari`).
    "Kurulumsuz …" bugünkü gibi çıkarılır ve yükleme ayrıntısında adıyla sayılır.
14. **Eksik rapor:** kaybolan > max(50, açık × %25) → onay; eski rapor → onay ve kapatmasız işleme (`tam_kapsam=0`).
15. **Rapor tazeliği:** mesai 08–20 içinde 30 dk amber, 60 dk kırmızı; dışa aktarım ritmi hedefi 30 dk, en az 07:45 / 12:15 / 16:45 (OT karar 12a);
    klasör izleme v2.1.
16. **Canlı güncelleme:** v2.0'da imleçli yoklama (operasyon 20 sn, teknik 15 sn); uzun sorgu v2.1 (sözleşmede `bekle` parametresi hazır).
17. **Sahadan erişim:** VPN + HTTPS gelene kadar İşlerim ofis Wi-Fi'ında güncellenir, çevrimdışı kuyrukla çalışır; teknisyen BOSS Mobil'le de
    çalışabilir (OT karar 13a).
18. **Kişi silme:** yalnız kaydı olmayan hesap silinir; kaydı olan pasife alınır; `demo_temizle` otomatik **çalışmaz** (kullanıcı kararı; çalışırsa
    önce doğrulanmış yedek). Bölge planlayıcının hiç kullanılmamış yer tutucu hesapları kaydı olmadığı için silinebilir.
19. **Pickle** açılmaz, silinmez; kullanıcı onayıyla 7 gün sonra elle silinebilir.
20. **Yedek saklama:** günlük 30 gün (bugünkü); göç yedekleri son 5 (+90 gün kuralı); aktarım yedekleri son 10.
21. **Bölgesiz satışçı:** boş liste (200) + "Size henüz bölge atanmadı" (bugünkü test davranışı).
22. **Davet kodu:** mevcut kodlar geçerli kalır ama listede gösterilmez; yeni kodlar 48 saat, bir kez gösterilir.
23. **Ticket açma:** OneDesk'te kullanıcı açar, sistem metni hazırlar (OT karar 17); Excel ticket aktarımı güncelleme günü bir kez yapılır.
24. **Satış hedefi:** `haftalik_satis_hedefi` tek sayı, boşsa çubuk gizli; satışçı başı hedef sonraki faz.
25. **BOSS'ta aç:** `boss_task_url` boş → "Task No'yu kopyala".
26. **Tema:** sistem; elle Açık/Koyu seçilebilir.
27. **Mahalle listesi:** resmî liste gelene kadar 621 + bina + öbek + elle; Göçmen'in ilçesini kullanıcı seçer (sistem tahmin etmez).
28. **Satışçının "Talep aç"ı** v2.1; v2.0'da bayi işini operasyon/yönetici açar.

## 13. Açık sorular (varsayılanla ilerlenir; cevap gelince ayar/kodla değişir)

1. F21 varsayılanı (§12-5, 6) onaylanıyor mu? Teknik kısa ad + no + adres görsün mü?
2. 8 kişiden kim Operasyon, kim Teknik, kim Yönetici? (Ekip'te seçilecek.)
3. Kanal eşlemesi (§12-11) doğru mu; boş Satış Kanalı ne sayılsın?
4. Bursa 17 + Yalova 6 ilçenin resmî, koordinatlı mahalle listesi sağlanabilir mi? Göçmen hangi ilçede?
5. "Kurulumsuz …" işleri mevcut müşteride kalsın mı? (Bugün çıkarılıyor.)
6. BOSS'ta Task No'dan işi açan bir adres şablonu var mı?
7. Gösterim verisi (1.257 ziyaret, 7 görev) yedekle temizlensin mi?
8. Her teknisyenin BOSS'taki ekip adını ve ev öbeğini kim verecek? (Eşleşmemiş BOSS ekibi satırıyla ekrandan da yapılabilir.)
9. BOSS raporu hangi bilgisayara iniyor? (Klasör izleme v2.1 için.)
10. VPN + HTTPS için BT'ye ne zaman gidilecek?
11. Haftalık satış hedefi tek sayı mı, satışçı başına mı?
12. `son_yukleme.pkl` (müşteri adı ve adres içeriyor) silinsin mi?

## 14. OPERASYON_TASARIM'dan bilinçli sapmalar

| Konu | OPERASYON_TASARIM | v2 | Neden |
|---|---|---|---|
| Gizlilik | Ad maskelenir (§6.5) | Operasyon/yönetici tam görür (kayıtlı, 30 gün); teknik kısa ad; telefon yok | F21 (kullanıcının son açık isteği) |
| Roller | `teknisyen`, `teknik_lider`, masa etiketli `operasyon` | `teknik` + etiket; `operasyon` | F12'nin kelimesi; tablo bir daha yeniden kurulmasın |
| Giriş | 3 kutu (§5.1) | Rol yönlendirir; yalnız yöneticiye cihazda bir kez | İlke 2; C9 yine karşılanır |
| Veri modeli | `gunluk_parca`, `kapasite_gunu`, `masa_gorevi`, `arama`, `dis_islem`, `is_emri_gecmis`, `kaynak_senkron` | `is_emri` alanları + `is_emri_olay` türleri + `ie_aktarim` + ayar anahtarları | 2 günde sağlam kurulabilecek en küçük şema; CHECK'siz, genişlemeye açık |
| Teknisyen ekranı | Faz 2 | v2.0'da, ofis ağında + çevrimdışı kuyruk | F7 istiyor; VPN ön koşulu korunur |
| Sıra | İki modlu tam kural | Yalın hâli; "en yakın 5" v2.1 | Kapsam |
| Bayi ↔ BOSS | — | Elle bağlama, otomatik birleşme yok | 10 müşterinin birden çok açık işi var; yanlış birleşme riski |
| `entegrasyon.md` §5.3 ticket taslağı | — | Kullanılmaz; bugünkü `ticket` tablosu esas | Çelişiyor |

---

## Ek A — Hakemlerin boşlukları → bu belgede kapandığı yer

| Boşluk (hakem) | Kapandığı yer |
|---|---|
| F17 veri tazeliği: rapor elle ve seyrek; 15 dk BOSS'tan değil sistemden başlıyor (H1) | §3.5 (BOSS→sistem ayrı adım, tazelik 30/60 dk, dürüst gösterim), §12-15 (ritim), klasör izleme v2.1 (§0.2) |
| F7 sahada VPN yok; BOSS'a çift giriş (H1, H2) | §3.4-4 giden kutusu + "BOSS'a işlendi" + sonraki raporda doğrulama; §6.9 çevrimdışı kuyruk; §12-17; Turkcell'e yazmama kırmızı çizgisi korunur |
| F15 satış yönetimi yalnız kart (H1, H2) | §5.3.6 `/api/takip/satis` + §6.11 satış bölümü (bugün/hafta, huni, satışçı başı, hedef ilerlemesi, altyapısı çözülüp satışa dönen bina); ayrıntılı hedef/prim sonraki faz |
| F13 canlıda 8 hesapta demo verisi; iz FK'ları silmeyi engelliyor (H1, H2) | §1.1 iz tablolarında FK yok; §6.10 "gösterim verisi" satırı; §1.13 `demo_temizle` yedekli ve kullanıcı kararıyla; yer tutucu hesaplar silinebilir |
| F6/F12 geçiş döneminde 8 yönetici tam yetkili (H1) | §1.11 kalıcı şerit + toplu "Gözden geçir" kartı + `yonetim_kaydi`; kimse erişim kaybetmez |
| Aşırı yükte "en eski önce" BTK'yı gömüyor (H1) | §3.6 KARMA-2 kural 5'in yalın hâli, deterministik test |
| F2 resmî liste yok; Göçmen; Yalova köy biçimi; yazım farkı sessizce öbeksiz (H1, H2) | §1.6 sözlük + 23 ilçe + ilçenin tamamı; §5.3.5 elle ekleme + eşad + resmî liste yükleme; §4 köy biçimi v2.0'da; `mahalle_benzer` triyaj nedeni (sessiz kalmaz) |
| F9 canlı ticket tablosu boş (H1, H2) | §5.3.8 `POST /api/ticket/aktar` + Ticketlar boş durumunda [Excel'den aktar]; §11 adım 7 |
| F21 KVKK kararı, telefondaki önbellek, yedek süreleri (H1, H2) | §2.5, §1.12 (yedek süreleri dahil), §6.9 (çıkış/401'de silme, 24 s önbellek sınırı, cihaz çıkışı), telefon varsayılan kapalı |
| F16 kanal eşlemesi ve birleşme kuralları farklı (H1, H2) | §3.8 + §12-11/12: tek eşleme tablosu, otomatik birleşme yok |
| C5 ↔ C17 filtre çelişkisi (H1) | §1.10 `filtre_istisnalari`, §12-13 |
| F14/F22 teslim riski, aşamalı devreye alma, geri dönüş yolu (H1) | §0.2 v2.0/v2.1 ayrımı; roller doğal anahtar (Teknik atanana kadar İşlerim kimseye açılmaz); makro yolu yedek; §11 geri dönüş; §10-9 eski kod + yeni DB; F14 elle protokolü sahibiyle (§8.2 WP-F) |
| CLI'lar sunucu açıkken ve yedeksiz göç edebilir (H2) | §1.2 `semayi_kur`/`surum_dogrula`; göç yalnız `sunucu.py` ve `python -m saha.goc` |
| Göç yedeği `db.gocler`'den sonra (H2) | §1.2 adım 5–6 |
| Pickle göçte açılıyor (H2) | §4 "Pickle hiç açılmaz" |
| `saha/api.py` iki ajana bölünmüş; conftest sahipsiz; A4 yükü ağır (H2) | §8.1 `saha/api.py` ve `saha/testler/**` WP-A'da; arayüz yükü C/D/E'ye bölündü, Takip WP-D'de |
| `is_emri.bina_serial` FK'sı aktarımı ROLLBACK ettirebilir (H2) | §1.1, §1.7 FK yok |
| `erisim_kaydi` FK'sı müşteri kartı açan herkesi silinemez yapıyor (H2) | §1.7 FK yok |
| F7 kapasite verisi yok; BOSS Ekip ↔ kişi listesi yok (H2) | §3.4-3 + §5.3.2 `boss-ekip/esle` + §6.3 "Eşleşmemiş BOSS ekibi"; §3.6 teknik yoksa açık mesaj |
| İki "öbek" karışıklığı (H2) | §6.14 "Satış öbeği" etiketi; operasyon öbeği "Öbek" |
| F19/F11 iş yükü küçümsenmiş (70+ hex, koyu mod, telefon hataları) (H2) | §7 tokenlar (hesaplanmış kontrast), §6.14 sahipli düzeltme listesi, WP-E ayrı paket |
| Mevcut rol testlerinin sahibi yok (H2) | §8.1 `saha/testler/**` WP-A; §2.4-1 bölge=0 davranışı korunur |
| F14 yalnız elle doğrulanabilir (H2) | §8.2 WP-F protokolü + otomatik vekiller (`ilk-gun`, `sozcuk-tarama`) |
| HIZ: K tuşu çakışması (H1) | §6.1 klavye tablosu (Ticket = `T`, önceki iş = `↑`) |
| HIZ: `surum` BOSS alanlarıyla artıyor (H2) | §5.5 yalnız operasyon alanları |
| HIZ: teknisyensiz randevu yok (H1, H2) | §3.3 geçiş 4 (`randevulu`) |
| SADELİK: eski rapor koruması, eşzamanlı aktarım kilidi, aktarım öncesi yedek yok (H2) | §4 adım 2, 6, 7 |
| SADELİK: davet süresi için sütun yok (H2) | §1.5 `davet_zamani` |
| SAĞLAMLIK: telefon varsayılan açık (H2) | §1.10 `musteri_tel='kapali'` |

---

## Değişiklik günlüğü

| Tarih | Kim | Değişiklik |
|---|---|---|
| 30.09.2026 | Sentez | İlk sürüm (üç tasarım + iki hakem + kullanılabilirlik ve veri denetimleri); göç SQL'i karalama kopyasında doğrulandı (§1.14) |
