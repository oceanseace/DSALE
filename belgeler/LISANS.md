# Saha Sistemi — Lisans

**Durum (30.09.2026):** lisans araçları hazır ve test edildi (`kod/lisans/`, 99 test). Sunucuya bağlanması bir sonraki
yapımın işidir (§8, **sunucu sözleşmesi**). Genel anahtar henüz oluşturulmadı; bu yüzden bağlantı kurulsa bile
denetim **kapalı** kalır ve hiç kimse etkilenmez. Denetim, lisans sahibi §7'yi yapınca açılır.

Karşıladığı istekler: GEREKSINIMLER E4 (lisans anahtarı), E5 (cihazlar), E6 (ücretli kullanımı durdurmak / sürdürmek).

---

## 1. Tek paragrafta

Lisans, lisans sahibinin **dijital imzasını taşıyan, düz metin** bir dosyadır: müşteri, bayi kodu, başlangıç ve bitiş,
hangi bilgisayar(lar), hangi modüller. Uygulama imzayı doğrular ve koşulları **Ayarlar › Lisans** ekranında gösterir.
Süre bitince **14 gün ek süre** vardır; her şey çalışır, açık bir uyarı görünür. Ek süre de bitince sistem **salt okunur**
olur: kayıtlar görüntülenir, raporlar ve dışa aktarma çalışır, yalnız yeni kayıt yapılamaz. Yeni lisans yüklendiği
anda her şey kaldığı yerden devam eder. **Veri hiçbir zaman silinmez, kilitlenmez, şifrelenmez; gizli ya da uzaktan kapatma
yoktur.** Sözleşme taslağı: `kod/lisans/SOZLESME_TASLAGI.md`.

## 2. Ne yapar, ne yapmaz

| Yapar | Yapmaz |
|---|---|
| İmzalı, süreli lisansı doğrular (Ed25519) | İnternete bağlanmaz (bugün) |
| Koşulları uygulamada açıkça gösterir | Gizli kapatma, uzaktan kapatma, uzaktan silme |
| Bitişten 30 gün önce yöneticiyi uyarır | Veriyi silmez, kilitlemez, şifrelemez |
| 14 gün ek süre, sonra salt okunur | Dışa aktarmayı ya da yedeklemeyi durdurmaz |
| Lisansı bir bilgisayara bağlayabilir | Sahadaki telefon kayıtlarını düşürmez (503 → kuyrukta bekler) |
| Modül bayrakları, aktif kullanıcı sınırı | Var olan bir kullanıcıyı kapatmaz |

## 3. Parçalar

| Dosya | Ne | Uygulamayla gider mi |
|---|---|---|
| `kod/lisans/lisans.py` | Doğrulama, durumlar, ek süre, cihaz kimliği, salt okunur kapısı kuralları, `Denetci` | **Evet** |
| `kod/lisans/sunucu.py` | FastAPI bağlantısı: `LisansKapisi` (ASGI), `lisans_yonlendirici` (`/api/lisans`), `acilis_metni` | **Evet** |
| `kod/lisans/genel_anahtar.pem` | Doğrulama anahtarı. **Henüz yok** → denetim kapalı | Evet (sahip oluşturunca) |
| `kod/lisans/uret.py` | Sahibin aracı: anahtar, ver, yenile, durdur, liste, göster | **Hayır** |
| `kod/lisans/testler/` | 99 test (kurcalama, süre, ek süre, cihaz, denetçi, yükleme, kapı, FastAPI, CLI) | Hayır |
| `kod/lisans/SOZLESME_TASLAGI.md` | Türkçe lisans sözleşmesi taslağı | Hayır |
| `~\.saha-lisans\` (kasa) | **Özel anahtar**, verilen lisanslar, defter. Depo DIŞINDA, yalnız sahipte | **Asla** |

Uygulamayla giden modüllerde özel anahtar yükleyen ya da imza atan kod yoktur (test: `test_uygulama_modulu_imzalayamaz`).

Testler: `.venv\Scripts\python.exe -m pytest kod/lisans/testler -q` (depo kökünden; `pytest.ini` `kod/`'u yola koyar)

## 4. Lisans dosyası

Sunucu bilgisayarında, çalışma klasöründe `saha/lisans.json` (canlıda `canli\veri\saha\lisans.json`). Örnek (sahte veri):

```json
{
  "bicim": "saha-lisans/1",
  "aciklama": "Saha Sistemi lisansı. İçerik okunabilir; tek bir harf bile değişirse imza tutmaz ...",
  "lisans": {
    "surum": 1,
    "urun": "saha-sistemi",
    "lisans_no": "SL-2026-7F3A9C",
    "musteri": "ÖRNEK BAYİ İLETİŞİM LTD. ŞTİ.",
    "bayi_kodu": "00000.00000",
    "baslangic": "2026-10-01",
    "bitis": "2027-09-30",
    "ek_sure_gun": 14,
    "cihaz_siniri": 1,
    "izinli_cihazlar": ["7F3A-91BC-04DE-55A1-2B6C"],
    "kullanici_siniri": null,
    "ozellikler": {"satis": true, "is_emri": true},
    "duzenleme_tarihi": "2026-09-30",
    "not": "Yıllık lisans"
  },
  "anahtar_kimligi": "c5b92d73f95e088e",
  "imza": "hgmUG6ya9MTamf30ZXAdlgteiqOIYdZKS3zw-AEBAXXsyZ_oOLYgpdwfgdsO3C9YuTCyV2A853C7BUxTslPcAA"
}
```

| Alan | Kural |
|---|---|
| `surum` | Biçim sürümü (1). Daha yenisi gelirse "uygulamayı güncelleyin" |
| `lisans_no` | `A-Z 0-9 -`, 4–40. Sahip aracı `SL-<yıl>-<6 hane>` üretir |
| `baslangic`, `bitis` | `YYYY-AA-GG`, **bitiş günü dahil**, Türkiye saati (UTC+3) |
| `ek_sure_gun` | 0–90 (varsayılan 14). Koşul lisansta yazılı ve görünür |
| `cihaz_siniri`, `izinli_cihazlar` | Liste boşsa her bilgisayarda geçerli; doluysa yalnız o kimlikler. Liste ≤ sınır |
| `kullanici_siniri` | Aktif kullanıcı üst sınırı; `null` = sınırsız |
| `ozellikler` | `{ad: true/false}`. `satis`, `is_emri` yazmıyorsa **açık**; başka (ileride satılacak) modül yazmıyorsa **kapalı** |
| `onceki_lisans_no`, `not` | İsteğe bağlı |

**İmza.** İmzalanan baytlar: `b"saha-lisans/1\n"` + içeriğin kanonik JSON'u (anahtarlar sıralı, boşluksuz, UTF-8, NFC,
kesirli sayı yok). Girinti, alan sırası, Not Defteri'nin eklediği BOM, NFD'ye çeviren bir düzenleyici imzayı bozmaz;
**içerikte tek bir değer değişirse bozar.** `bicim`, `aciklama`, `anahtar_kimligi` imzaya girmez (bilgi amaçlıdır).

**Lisans metni.** Aynı lisansın tek satırlık biçimi: `SAHA1.<içerik base64url>.<imza base64url>` (~600 karakter).
E-postayla ya da yazışmayla gönderilir, Ayarlar › Lisans'a yapıştırılır. Satır kırılırsa da okunur.

**Anahtar yenileme.** `genel_anahtar.pem` birden çok PEM bloğu taşıyabilir; geçişte eski ve yeni anahtar birlikte kabul edilir.

## 5. Durumlar ve kipler

`Denetci.sonuc()` → `Sonuc` (`durum`, `mod`, `seviye`, `baslik`, `mesaj`, `mesaj_ekip`, `kalan_gun`, `ek_sure_son`, …).

| Durum | Ne zaman | Kip | Seviye | Ekip görür mü |
|---|---|---|---|---|
| `denetlenmiyor` | `kod/lisans/genel_anahtar.pem` yok | tam | yok | hayır |
| `gecerli` | bitişe > 30 gün | tam | yok | hayır |
| `suresi_yakin` | bitişe 30…8 gün / 7…0 gün | tam | bilgi / uyarı | hayır |
| `suresi_doldu` | bitişten sonra, ek süre içinde | tam | uyarı; son 3 gün kritik | son 3 gün |
| `suresi_doldu` | ek süre bitti | **salt okunur** | kritik | evet |
| `imza_bozuk` | okunamadı, imza tutmuyor, başka anahtar, içerik geçersiz | tam → salt okunur | uyarı → kritik | son 3 gün + salt okunur |
| `cihaz_disi` | bu bilgisayar `izinli_cihazlar`da yok | tam → salt okunur | uyarı → kritik | aynı |
| `lisans_yok` | anahtar var, lisans dosyası yok | tam → salt okunur | uyarı → kritik | aynı |
| `henuz_baslamadi` | bugün < başlangıç | tam → salt okunur | uyarı → kritik | aynı |

Zaman çizelgesi (bitiş 30 Eylül 2027, ek süre 14 gün):

```
31 Ağu–22 Eyl  bilgi (yalnız yönetici)
23 Eyl–30 Eyl  uyarı (30 Eyl = son gün)
 1 Eki–11 Eki  ek süre, her şey çalışır (uyarı)
12 Eki–14 Eki  ek süre, son 3 gün (kritik; ekip de görür)
15 Eki →       salt okunur (veri yerinde, okuma ve dışa aktarma açık)
```

**Ek süre nasıl sayılır.** Süre dolmasında bitişin ertesi günden. Diğer sorunlarda sorunun **ilk görüldüğü** günden;
`Denetci` bu günü `saha/lisans_durum.json`'da tutar ve yalnız sorunsuz bir duruma dönünce siler. Sorun türü değişse de
(lisans yok → bozuk dosya → süresi dolmuş dosya) sayaç **baştan başlamaz**: dosyayı silmek ya da değiştirmek ek süre kazandırmaz.

**Saat koruması.** `Denetci` görülen en ileri tarihi saklar. Windows tarihi bundan geri alınırsa lisans hesabı o tarihle
yapılır ve yöneticiye "Bilgisayarın tarihi geri alınmış görünüyor" denir. 400 günden büyük ileri sıçramalar saklanmaz
(bozuk bir BIOS saati kurulumu kalıcı olarak kilitlemesin).

Örnek `GET /api/lisans` yanıtları: §8.4.

## 6. Cihaz kimliği

`XXXX-XXXX-XXXX-XXXX-XXXX` (20 onaltılık hane). Windows'ta `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`
okunur ve ürüne özgü tuzla SHA-256 özeti alınır: ham GUID hiçbir yere yazılmaz, kişisel veri içermez, başka
yazılımların kimliğiyle eşleştirilemez. Linux'ta `/etc/machine-id`; ikisi de yoksa ağ kartı adresi.

- Görmek için: **Ayarlar › Lisans** (denetim kapalıyken de görünür) ya da sunucu bilgisayarında
  `set PYTHONPATH=kod` sonra `.venv\Scripts\python.exe -m lisans.lisans cihaz`.
- Windows yeniden kurulursa kimlik **değişir** (bilgisayar değişmiş gibi, §9). Sanal makine kopyalanırsa **aynı kalır** (§11).

## 7. Lisans sahibi için

> Önce **mülkiyet**: lisans verme hakkı kimdeyse o verir. Bu, işveren ve bayi ile yazılı olarak kararlaştırılmalıdır
> (`kod/lisans/SOZLESME_TASLAGI.md` başındaki uyarı). Aşağıdaki adımlar o karardan sonra yapılır.

Bütün komutlar depo kökünden: `set PYTHONPATH=kod` sonra `.venv\Scripts\python.exe -m lisans.uret <komut>`
(ya da doğrudan `.venv\Scripts\python.exe kod\lisans\uret.py <komut>`)

| Ne | Komut |
|---|---|
| Anahtar çifti (bir kez) | `anahtar-olustur` → kasa parolası sorar. Kasada anahtar varsa **asla üzerine yazmaz** |
| Denetimi uygulamada açmak | `copy %USERPROFILE%\.saha-lisans\genel_anahtar.pem kod\lisans\genel_anahtar.pem` (ya da `anahtar-olustur --depoya-yaz`) |
| Lisans vermek | `ver --musteri "ÖRNEK BAYİ" --bayi-kodu 00000.00000 --ay 12 --cihaz 7F3A-91BC-04DE-55A1-2B6C` |
| Seçenekler | `--baslangic`, `--bitis`/`--gun`, `--cihaz-siniri`, `--ozellik is_emri=hayir`, `--kullanici-siniri 25`, `--ek-sure-gun 14`, `--not`, `--cikti` |
| Yenilemek (ödemeye devam) | `yenile SL-2026-7F3A9C --ay 12` → eski bitişin ertesinden kesintisiz uzatır; `--cihaz-ekle/--cihaz-cikar` |
| Durdurmak (ödeme yok) | `durdur SL-2026-7F3A9C --neden "…"` → "yenilenmeyecek" işareti + müşteriye bildirilecek tarihler. `--geri-al` kaldırır |
| Listelemek | `liste` (`--hepsi`: yenilenmiş eskiler de) |
| Bir dosyayı doğrulamak | `goster dosya.json` ya da `goster SAHA1.…` |

`ver` iki şey üretir: dosya (`kasa\lisanslar\SL-….lisans.json`) ve tek satırlık lisans metni. Müşteri ikisinden birini
Ayarlar › Lisans'a yükler.

**Durdurmanın anlamı (dürüst):** verilmiş bir lisans geri alınamaz. "Durdurmak" yenilememektir: müşterinin sistemi
bitişe kadar çalışır, sonra 14 gün ek süre, sonra salt okunur. `durdur` komutu bu tarihleri yazar. Sözleşme gereği
yenilememe en az 30 gün önce yazılı bildirilir.

**Kasa** (`%USERPROFILE%\.saha-lisans`, `--kasa` ya da `SAHA_LISANS_KASA` ile değişir): `ozel_anahtar.pem` (parolalı PKCS#8),
`genel_anahtar.pem`, `verilenler.jsonl` (yalnız eklenen defter), `lisanslar\`, `OKUBENI.txt`. **Şifreli bir USB belleğe
yedekleyin.** Özel anahtar depoya, uygulamaya, e-postaya asla girmez. Otomasyon için parola `SAHA_LISANS_PAROLA` ile verilebilir.

## 8. SUNUCU SÖZLEŞMESİ (bir sonraki yapım)

İlke: lisans kuralları `kod/lisans/` içinde kalır ve test edilmiştir; sunucu yalnız **bağlar**. Aşağıdaki her madde zorunludur.

### 8.1 Dosyalar, kurulum, korunan yollar
- Güncelleme paketiyle ofis bilgisayarına giden: `kod/lisans/__init__.py`, `kod/lisans/lisans.py`, `kod/lisans/sunucu.py`,
  ve **varsa** `kod/lisans/genel_anahtar.pem`. Gitmeyen: `kod/lisans/uret.py`, `kod/lisans/testler/`.
- `kod/saha/gereksinimler.txt`'e ekle: `cryptography>=42` (depodaki `.venv`'de 50.0.2 kurulu; canlı `.venv`'e de kurulmalı).
- `kod/saha/ayarlar.py`'ye ekle:
  ```python
  LISANS_DOSYASI = Path(os.environ.get("SAHA_LISANS") or (CALISMA / "lisans.json"))   # testler geçici dosyaya yönlendirir
  LISANS_DURUM = LISANS_DOSYASI.with_name("lisans_durum.json")
  ```
- `kod/saha/KORUNAN.txt` ve `kod/saha/.gitignore`'a ekle: `saha/lisans.json`, `saha/lisans_durum.json`
  (eski lisanslar `saha/yedek/lisans-*.json`'a yedeklenir; `yedek/**` zaten korunuyor).
- `kod/saha/testler/conftest.py`: `SAHA_LISANS` geçici bir yola. Genel anahtar yokken bütün eski testler aynen geçer
  (`denetlenmiyor`); varken lisans yok → ek süre → yine tam kip.

### 8.2 Açılış (`kod/saha/sunucu.py`)
`_guncelle()` başarılı olduktan sonra, `_adres_yaz`'dan önce:
```python
from lisans import lisans as lisans_cekirdek
from lisans.sunucu import acilis_metni

sonuc = lisans_cekirdek.Denetci(ayarlar.LISANS_DOSYASI, ayarlar.LISANS_DURUM).sonuc()
for satir in acilis_metni(sonuc):          # sorun yoksa boş; varsa çerçeveli Türkçe uyarı
    yaz(satir)
logging.getLogger("saha.lisans").info("Lisans: %s · %s · %s", sonuc.durum, sonuc.mod, sonuc.ayrinti or "-")
```
**Sunucu lisans yüzünden asla açılmamazlık etmez**; çıkış kodu değişmez. Salt okunurluk yalnız HTTP kapısında uygulanır.
Şema göçü (`goc.hazirla`) salt okunurda da çalışır: sistem güncellemesidir, iş verisi yazımı değildir.

### 8.3 Denetçi ve kapı (`kod/saha/api.py`)
```python
from lisans import lisans as lisans_cekirdek
from lisans.sunucu import LisansKapisi, lisans_yonlendirici

LISANS = lisans_cekirdek.Denetci(ayarlar.LISANS_DOSYASI, ayarlar.LISANS_DURUM, yedek_dizini=ayarlar.KOK / "yedek")
uygulama.add_middleware(LisansKapisi, denetci=LISANS)

def _lisans_kaydi(k: dict, s) -> None:      # yonetim_kaydi: kim, ne zaman, hangi lisans
    conn = db.baglan()
    try:
        ...  # eylem='lisans_yukle', hedef=s.lisans['lisans_no'], ozet={baslangic, bitis}, kullanici_id=k['id']
        conn.commit()
    finally:
        conn.close()

uygulama.include_router(lisans_yonlendirici(
    LISANS, oturum=izin("oturum"), yukleme_izni=izin("lisans.yonet"),
    yonetici_mi=lambda k: izinli(k, "lisans.yonet"), kayit=_lisans_kaydi))
```
- `LisansKapisi` saf ASGI'dir, yönlendirmeden önce çalışır, v2 yönlendiricileri dahil **bütün** uçları kapsar.
- Okuma (`GET/HEAD/OPTIONS`) asla durdurulmaz. Yazma (`POST/PUT/PATCH/DELETE`) salt okunurda **varsayılan YASAK**;
  yalnız `lisans_cekirdek.SALT_OKUNUR_SERBEST` geçer:

  | Yöntem | Yol | Neden |
  |---|---|---|
  | POST | `/api/giris` | oturum açılmadan veri görülemez |
  | POST | `/api/pin` | var olan kişi verisini görebilsin |
  | POST | `/api/lisans` | salt okunurdan çıkmanın yolu |
  | POST | `/api/kullanici/{id}/cihaz-cikis` | kayıp telefonun oturumunu kapatmak (güvenlik) |
  | POST | `/api/isler/{is_no}/kopya` | okuma + erişim kaydı |

- Durdurulan istek: **HTTP 503**, `Retry-After: 3600`,
  `{"hata": "Sistem şu an yalnız okuma modunda (lisans güncellenmeli); bu kayıt yazılmadı. Sahadan gönderilen ziyaretler telefonda bekler, lisans yenilenince kendiliğinden gönderilir.", "kod": "salt_okunur", "lisans": {"durum": "...", "mod": "salt_okunur"}}`.
  **503 bilinçli:** `kod/arayuz/src/api/istemci.ts` `agHatasi` 5xx'i yeniden denenecek hata sayar ve ziyareti kuyrukta
  tutar; 4xx olsaydı kayıt "reddedildi" işaretlenirdi. Bu kod değiştirilmemeli.
- Denetim bir istisna fırlatırsa kapı isteği **geçirir** (lisans hatası kimsenin işini durdurmaz) ve günlüğe yazar.
- Sonuç önbelleklidir: dosya, genel anahtar ya da tarih değişince ya da 10 dakikada bir yeniden hesaplanır.

### 8.4 Uçlar

**`GET /api/lisans`** — izin `oturum`. Yönetici (`lisans.yonet`) tam görünüm, diğerleri kısa görünüm alır.

Ekip (müşteri, bayi, lisans no, cihaz kimliği **yok**):
```json
{"durum": "suresi_doldu", "mod": "salt_okunur", "seviye": "kritik", "goster": true,
 "baslik": "Sistem salt okunur",
 "mesaj": "Kayıtlar görüntülenebilir ama yeni kayıt yapılamıyor. Sahada işlediğiniz ziyaretler telefonunuzda bekler, lisans yenilenince kendiliğinden gönderilir. Yöneticinize haber verin.",
 "ek_sure_son": "2027-10-14"}
```
Yönetici (ek süre, son 3 gün):
```json
{"durum": "suresi_doldu", "mod": "tam", "seviye": "kritik", "goster": true, "ekibe_goster": true,
 "baslik": "Lisansın süresi doldu · ek süre",
 "mesaj": "Lisans 30 Eylül 2027 tarihinde bitti. 14 Ekim 2027 tarihine kadar her şey çalışır (3 gün); sonra sistem salt okunur olur (veriler silinmez, görüntüleme ve dışa aktarma sürer, yalnız yeni kayıt yapılamaz). Yeni lisans dosyasını Ayarlar › Lisans bölümünden yükleyin.",
 "baslik_ekip": "Lisans güncellenmeli", "mesaj_ekip": "Sistemin lisansı güncellenmeli: 14 Ekim 2027 tarihinden sonra yeni kayıt yapılamayacak. Yöneticinize haber verin.",
 "tarih": "2027-10-12", "kalan_gun": -12, "bitis": "2027-09-30", "bitis_metni": "30 Eylül 2027",
 "ek_sure_son": "2027-10-14", "ek_sure_son_metni": "14 Ekim 2027", "ek_sure_kalan_gun": 2,
 "saat_uyarisi": false, "ayrinti": null, "cihaz_kimligi": "7F3A-91BC-04DE-55A1-2B6C", "cihaz_izinli": true,
 "anahtar_kimligi": "c5b92d73f95e088e",
 "lisans": {"lisans_no": "SL-2026-7F3A9C", "musteri": "ÖRNEK BAYİ İLETİŞİM LTD. ŞTİ.", "bayi_kodu": "00000.00000",
            "baslangic": "2026-10-01", "bitis": "2027-09-30", "ek_sure_gun": 14, "cihaz_siniri": 1,
            "izinli_cihazlar": ["7F3A-91BC-04DE-55A1-2B6C"], "kullanici_siniri": null,
            "duzenleme_tarihi": "2026-09-30", "onceki_lisans_no": null, "not": "Yıllık lisans"},
 "ozellikler": {"satis": {"etiket": "Satış: bina listesi, rota, ziyaret", "acik": true},
                "is_emri": {"etiket": "İş emirleri: operasyon ve teknik", "acik": true}}}
```
`kalan_gun`: bitişe kalan gün (0 = bugün son gün, eksi = geçti). `ek_sure_kalan_gun`: 0 = bugün son gün, eksi = salt okunur.

**`POST /api/lisans`** — izin `lisans.yonet` (yalnız yönetici); salt okunurda da serbest.
Gövde `{"metin": "<lisans dosyasının içeriği ya da SAHA1. metni>"}` (en çok 64 KB; arayüz dosyayı FileReader ile okur).
- 200 → yeni durum (yönetici görünümü). Eski dosya `saha/yedek/lisans-<zaman>.json`'a yedeklenir, yazma atomiktir.
- 422 `{"hata", "kod"}`, kod: `imza_bozuk` · `cihaz_disi` (mesajda bu bilgisayarın kimliği) · `henuz_baslamadi` ·
  `suresi_doldu` · `daha_kisa` (yüklü lisans daha uzun süreli) · `gecersiz_veri` (boş/çok büyük gövde).
- 409 `denetim_kapali` (genel anahtar yok) · 503 `yazilamadi` (lisans doğru ama disk/klasör yazılamıyor).

**`GET /api/saglik`** (herkese açık) — ek alan `"lisans": LISANS.sonuc().sozluk(yonetici=False)`. Giriş ekranı salt okunur
şeridini buradan gösterir. Müşteri bilgisi içermez.

**`GET /api/ben`** — ek alan `"lisans": LISANS.sonuc().sozluk(yonetici=izinli(k, "lisans.yonet"))` (açılışta ayrı istek gerekmesin).

**`GET /api/veri/disa-aktar`** (YENİ, izin `veri.yonet`) — "veri asla kilitlenmez" sözünün düğmesi: bütün veritabanının
tutarlı kopyası (`sqlite3` online backup → `saha.db`) + `OKUBENI.txt`, tek ZIP. Her kipte çalışır. Kişisel veri içerir:
yalnız yönetici, `erisim_kaydi`'na yazılır. (Mevcut `rapor.xlsx`, `isler/excel`, `bolgeleme/excel` de GET'tir, zaten açık.)

### 8.5 Yetki (`kod/saha/yetki.py`)
```python
IZINLER["lisans.yonet"] = frozenset({Y})
ROTA_IZNI[("GET", "/api/lisans")] = "oturum"
ROTA_IZNI[("POST", "/api/lisans")] = "lisans.yonet"
ROTA_IZNI[("GET", "/api/veri/disa-aktar")] = "veri.yonet"
```

### 8.6 Salt okunur kuralları

| Çalışır | Durur (503 `salt_okunur`) |
|---|---|
| Giriş, ilk PIN | Ziyaret kaydı (telefonda kuyrukta bekler, sonra gider) |
| Bütün ekranlar, harita, arama, bina kartı | İş emri oluşturma, atama, randevu, durum, not |
| Raporlar, Excel, `veri/disa-aktar` | Kişi ekleme/düzenleme/silme, görev değişikliği, ayarlar |
| Lisans yükleme | BOSS raporu / tur raporu / OneMap yükleme, bölgeleme uygula |
| Kayıp telefonun oturumunu kapatma | Ticket açma/düzenleme, öbek düzenleme |
| Günlük yedek, şema göçü | Klasör izleme içe aktarımı (bkz. aşağı) |

- `kod/operasyon/v2/izleme.py`: her taramadan önce `LISANS.sonuc().salt_okunur` ise **taramayı atla**; dosyalar klasörde
  kalır, lisans gelince işlenir. Günlükte bir kez "Lisans salt okunur: klasör izleme bekliyor".
- Zamanlanmış yedek (`kod/saha/yedekle.py`) **her zaman** çalışır.

### 8.7 Özellik bayrakları ve kullanıcı sınırı
- `LISANS.sonuc().ozellik_acik("is_emri")` **açıkça false** ise: o modülün yazma uçları 403
  `{"kod": "lisans_ozellik_kapali", "hata": "Bu modül lisansınızda yok. Lisans sahibine başvurun."}`; okuma ve dışa aktarma
  açık; menüde "Lisansta yok" etiketi. `satis` ve `is_emri` lisansta yazmıyorsa açıktır (bugünkü lisanslar ikisini de açık verir).
- `kullanici_siniri`: `POST /api/kullanici` (yeni aktif kişi) ve pasiften aktife alma, `not s.kullanici_eklenebilir(aktif_sayi)`
  ise 409 `{"kod": "lisans_kullanici_siniri", "hata": "Lisansınız en çok N aktif kullanıcıya izin veriyor. Birini pasife alın ya da lisans sahibine başvurun."}`.
  **Var olan kişi asla kapatılmaz.**

### 8.8 Arayüz (`kod/arayuz`)
- **Lisans şeridi** (yönetici konsolu ve telefon, her ekranın üstü): kaynak `/api/ben.lisans`; sonra 30 dakikada bir
  `GET /api/lisans` ve herhangi bir yanıt `kod: "salt_okunur"` taşıdığında hemen. `goster` true ise görünür.
  Renk `seviye`'ye göre: `bilgi` sakin (gri/mavi, gün boyu gizlenebilir), `uyari` amber, `kritik` kırmızı (gizlenemez).
  Metin: kalın `baslik` + `mesaj`. Yöneticide "Ayrıntı" → Ayarlar › Lisans.
- **Ayarlar › Lisans** (yalnız `lisans.yonet`; bu ad mesajlarda geçer, değiştirilmemeli): durum rozeti; müşteri, bayi kodu,
  lisans no; başlangıç–bitiş (`bitis_metni`), kalan gün; ek süre bitişi; **cihaz kimliği + Kopyala düğmesi**; cihaz
  sınırı; aktif kullanıcı / sınır; özellikler listesi. Yükleme: "Dosya seç" ve "Metni yapıştır"; hata `hata` alanından
  satır içinde. Altta tek cümle: "Lisans hiçbir veriyi silmez ya da kilitlemez; süre dolsa da kayıtlar görüntülenir ve
  dışa aktarılır." Denetim kapalıyken: "Lisans denetimi kapalı" + cihaz kimliği.
- **Salt okunurda:** kaydet düğmeleri pasif, üzerinde "Sistem salt okunur (lisans)"; kuyruk rozeti "N kayıt lisans
  yenilenince gönderilecek" (son hata `salt_okunur` ise). Giriş ekranı `/api/saglik.lisans` ile şeridi gösterir.

### 8.9 Eklenecek testler
1. **Salt okunur matrisi:** `ROTA_IZNI`'deki her yazma rotası, salt okunur bir denetçiyle 503 `salt_okunur` döner —
   `SALT_OKUNUR_SERBEST` dışında; hiçbir GET rotası 503 dönmez (`test_yetki_matrisi.py` gibi, tablo güdümlü).
2. `POST /api/lisans`: satışçı 403, yönetici 200 / 422; `GET /api/saglik.lisans` müşteri adı içermez.
3. `/api/ziyaret` salt okunurda 503 → uygulama kuyruğu kaydı silmez (istemci testi).
4. Güncelleme testi: `saha/lisans.json` ve `saha/lisans_durum.json` güncellemeden aynen çıkar.
5. Klasör izleme salt okunurda dosya işlemez, dosyayı silmez.
6. Kullanıcı sınırı: sınırdayken yeni kişi 409, var olan kişiler çalışır.
7. `veri/disa-aktar`: ZIP açılır, içindeki `saha.db` bütünlük denetiminden geçer; salt okunurda da 200.

### 8.10 Devreye alma sırası
1. Bağlantılı sürüm **genel anahtarsız** kurulur → her yerde `denetlenmiyor`; kullanıcı hiçbir fark görmez.
2. Mülkiyet ve sözleşme yazılı olarak netleşir (§7 uyarısı).
3. Sahip `anahtar-olustur` çalıştırır, kasayı yedekler.
4. Ofis bilgisayarının cihaz kimliği Ayarlar › Lisans'tan alınır; sahip `ver … --cihaz <kimlik>` ile lisansı verir.
5. Lisans dosyası `saha/lisans.json` olarak konur, **sonra** `kod/lisans/genel_anahtar.pem`'li sürüm kurulur.
   Unutulursa zarar yok: `lisans_yok` → 14 gün ek süre içinde Ayarlar › Lisans'tan yüklenir.

## 9. Destek senaryoları

| Durum | Ne olur | Ne yapılır |
|---|---|---|
| Ofis bilgisayarı değişti / Windows yeniden kuruldu | `cihaz_disi`, yeni kimlik ekranda, 14 gün tam | Sahip: `yenile SL-… --cihaz-cikar ESKİ --cihaz-ekle YENİ --bitis <aynı bitiş>` |
| Lisans dosyası bozuldu/silindi | `imza_bozuk` / `lisans_yok`, 14 gün | Kasadaki kopya (`kasa\lisanslar\SL-….lisans.json`) yeniden yüklenir |
| Bilgisayar saati yanlış | `saat_uyarisi`, yöneticiye açık mesaj | Saat düzeltilir. İleri takılı kaldıysa `saha/lisans_durum.json` silinir (sayaçları da sıfırlar) |
| Özel anahtar kayboldu | Verilmiş lisanslar bitişe kadar çalışır; yenisi verilemez | Yeni anahtar; `genel_anahtar.pem`'e eski+yeni birlikte; lisanslar yeniden verilir |
| Özel anahtar ele geçirildi | Herkes lisans üretebilir | Yeni anahtar; `genel_anahtar.pem`'de **yalnız yeni**; bütün lisanslar yeniden verilir |
| Müşteri ödemiyor | — | `durdur SL-…`; yazılı bildirim; bitiş + 14 gün sonra salt okunur, veri müşteride kalır |

## 10. Gelecek: çevrimiçi yetkilendirme ve cihaz yönetimi (yalnız tasarım)

Bugün internet gerekmez. Çevrimiçi adım **barındırma** (alan adı + HTTPS sunucu) ve **ofis bilgisayarının dışarı
çıkış izni** (Turkcell/bayi ağ politikası) ister; ikisi de kullanıcının kurması/onaylatması gereken şeylerdir.
Sözleşmede Madde 8 gereği yazılı ek protokolle açılır.

**Aşama 1 — Yenileme adresi (yalnız statik barındırma).** Sahip yenilenen lisans dosyasını tahmin edilemez bir adrese koyar:
`https://<alan>/l/<lisans_no>-<rastgele 16 hane>.json`. Adres lisans içeriğine yeni bir alan olarak yazılır (`yenileme_adresi`).
Sunucu günde bir kez HTTPS ile bakar; aynı zincirde (`onceki_lisans_no`), aynı cihaza, daha geç bitişli, imzası geçerli bir
lisans bulursa `Denetci.yukle` ile kurar. Bulamazsa ya da ağ yoksa hiçbir şey olmaz (günlüğe yazılır). Durdurmak = yeni
dosya koymamak. Sunucu kodu gerekmez; herhangi bir statik HTTPS barındırma yeter.

**Aşama 2 — Etkinleştirme sunucusu (cihaz yönetimi).**
- Uçlar (HTTPS, JSON; müşteri tarafında kimlik = lisans no + cihaz kimliği):
  - `POST /v1/etkinlestir {lisans_no, cihaz_kimligi, cihaz_adi, uygulama_surumu}` → lisans etkin ve etkin cihaz sayısı
    `cihaz_siniri`'nin altındaysa **etkinlik belgesi** döner: ayrı bir "etkinlik anahtarı"yla imzalı
    `{lisans_no, cihaz_kimligi, verilis, gecerlilik_sonu: +30 gün}`.
  - `POST /v1/nabiz {lisans_no, cihaz_kimligi, belge_no, uygulama_surumu}` (günde bir) → belgeyi 30 gün kaydırır; yenilenmiş
    lisans varsa onu da döner (Aşama 1'in yerini alır).
  - Sahip paneli (yalnız sahip, iki adımlı giriş): `GET /v1/cihazlar?lisans_no=`, `POST /v1/cihazlar/{id}/birak`
    (koltuğu boşalt), `POST /v1/lisans/{no}/yenileme-durdur`.
- Uygulama: lisans içeriğinde `cevrimici: true` varsa geçerlilik = imzalı lisans **ve** süresi geçmemiş etkinlik belgesi.
  İnternet 30 gün yoksa belge dolar → mevcut 14 günlük ek süre → salt okunur. Yani kesinti **44 gün** işi durdurmaz;
  şeritte "Son çevrimiçi doğrulama: …" görünür.
- Cihazı kapatmak = koltuğu bırakmak: o cihazın nabzı reddedilir, belgesi en geç 30 günde dolar, ek süre işler. **Anlık
  uzaktan kapatma bilinçli olarak yoktur.**
- Gönderilen veri yalnız: lisans no, cihaz kimliği, cihaz adı, uygulama sürümü. **Müşteri verisi asla.** KVKK aydınlatma
  metni panelde ve sözleşmede.
- Güvenlik: etkinlik anahtarı lisans anahtarından **ayrıdır** (sunucu ele geçirilse lisans üretilemez); lisans özel anahtarı
  sunucuya konmaz. Sunucu veritabanı yedeklenir.
- Barındırma seçenekleri: küçük bir VPS ya da sunucusuz (ör. Cloudflare Workers + D1). Ödeme sistem dışında kalır; ileride
  ödeme sağlayıcısının bildirimiyle yenileme otomatikleştirilebilir.
- Biçim: `cevrimici` ve `yenileme_adresi` yeni isteğe bağlı alanlardır; eski uygulamalar onları yok sayar.

## 11. Sınırlar (dürüst)

- Çevrimdışı lisans **sözleşmeyi uygulatan bir araçtır, kopya koruması değildir.** Sunucu bilgisayarına yönetici olarak
  erişen biri kodu değiştirebilir, `genel_anahtar.pem`'i silip denetimi kapatabilir, `lisans_durum.json`'u silip sayaçları
  sıfırlayabilir. Bunlar sözleşmenin Madde 10'unun ihlalidir. Asıl korunması gereken **özel anahtardır**.
- Cihaz kimliği sanal makine kopyalarını ayırt edemez; Windows yeniden kurulunca değişir.
- Saat koruması yalnız "tarihi geri alma"yı yakalar; durum dosyası silinirse sıfırlanır.
- `cihaz_siniri` çevrimdışıyken yalnız `izinli_cihazlar` listesiyle uygulanır; liste boşsa sınır bilgi amaçlıdır ve
  Aşama 2'de etkinleşir.
- Hukuk: lisans verme hakkı ve müşteri verisinin durumu `kod/lisans/SOZLESME_TASLAGI.md` başındaki uyarıya bağlıdır.
