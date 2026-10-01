# Dehanet Saha — Masaüstü uygulaması

Saha Sistemi'nin ofis bilgisayarında **tek tıkla** çalışan hâli. İçinde her şey var: sunucu
(`SahaSunucu.exe`), yönetici ekranı, telefon uygulaması ve bina verisi. Bilgisayarda Python ya da
Node **gerekmez**; başka bir bilgisayara da aynı dosyayla kurulur.

| Dosya | Ne işe yarar |
|---|---|
| `kod\masaustu\dist\DehanetSaha-Kurulum-<sürüm>.exe` | Kurulum programı. Yönetici izni istemez ("yalnız benim için"); istenirse "bu bilgisayardaki herkes için". Masaüstü + Başlat menüsü kısayolu. |
| `kod\masaustu\dist\DehanetSaha.exe` ve kökteki `DehanetSaha.exe` | Kurulumsuz (taşınabilir) sürüm. Çift tıkla, çalışsın. Kurulu sürümle **aynı** veri klasörünü kullanır. Her açılışta kendini açtığı için ilk pencere ≈1 dk sürer; her gün kullanılacak bilgisayara kurulumu tercih edin. |

## İlk açılış

1. Çift tıklayın. "Hoş geldiniz" ekranı iki yol sunar:
   * **Yeni kurulum** — 19.706 bina yüklenir, ekip için davet kodları üretilir (bir dakikadan kısa). Kodlar ekranda
     gösterilir; sonra tepsi → **Davet kodları**.
   * **Var olan veriyi getir** — eski kurulumun `saha.db` dosyasını seçin (ör.
     `DSALE\canli\surum\saha\saha.db`; yayın aracından sonra `DSALE\canli\veri\saha\saha.db`). Kaynağa yalnız okunur dokunulur, doğrulanmış kopya alınır;
     yanındaki `gizli.key` (telefonlar yeniden giriş yapmaz) ve `operasyon\obekler.json` da gelir.
     **Önce eski sunucuyu kapatın (DURDUR.bat) ve bir daha açmayın**: iki sunucu kayıtları ikiye böler.
2. Sunucu açılır, yönetici ekranı pencerede belirir. Pencere başlığında telefon adresi yazar.
3. Windows Güvenlik Duvarı ilk seferde sorarsa **Özel ağlar** işaretliyken **İzin ver**.

## Günlük kullanım

* Pencereyi kapatmak sunucuyu **kapatmaz**; telefonlar çalışmaya devam eder. Sağ alttaki mavi **S** simgesi:
  Telefon adresi (karekodlu) · Sunucuyu durdur/başlat · Yeniden başlat · Veri klasörünü aç ·
  Yedek al · Davet kodları · Ayarlar · Bilgisayar açılınca başlat · Çıkış.
* **Günlük yedek kendiliğinden** alınır (açılıştan 1 dk sonra ve saatte bir denetlenir; günde bir dosya,
  30 gün saklanır). "Yedek al" istediğiniz an bir tane daha alır.
* Ayarlar: ağ erişimi (ofis ağı / yalnız bu bilgisayar), port (varsayılan 8080), veri klasörü,
  bilgisayar açılınca arka planda başlama.

## Veri klasörü

Varsayılan `C:\ProgramData\DehanetSaha` (Ayarlar'dan değişir). Kurulum klasörüne **hiçbir şey yazılmaz**.

```
saha.db  gizli.key  obekler.json
kayit\     saha.log (sunucu), masaustu.log (kabuk)
yedek\     saha-AAAA-AA-GG.db (günlük)   yedek\goc\ (güncelleme öncesi, doğrulanmış)
raporlar\  cikti\  gelen\  operasyon\
```

## Güncelleme ve kaldırma

* Yeni `DehanetSaha-Kurulum-x.y.z.exe`'yi çalıştırın. Açık uygulama önce **kendini düzgün kapatır**
  (sunucu açık kayıtları tamamlar), dosyalar değişir, veri klasörüne dokunulmaz.
* İlk açılışta sunucu şemayı günceller: önce **doğrulanmış yedek** (`yedek\goc\saha-oncesi-…db`), sonra
  göç. Bir şey ters giderse sunucu açılmaz ve ekranda "Güncelleme durdu — veriniz korundu" yazar.
* Veri, programdan yeni bir sürümdeyse (eski kurulum dosyası çalıştırıldıysa) sunucu açılmaz:
  "Bu sürüm verinizden eski".
* Kaldırma: Ayarlar → Uygulamalar → Dehanet Saha. Veri klasörü **kalır**; gerçekten silmek elle yapılır.

## Geliştirici: derleme

```
kod\masaustu\DERLE.bat            tam derleme (≈3–6 dk)
kod\masaustu\DERLE.bat /hizli     SahaSunucu.exe'yi yeniden derlemez (yalnız kabuk değiştiyse)
kod\masaustu\DERLE.bat /pwa       telefon uygulamasını önce kod\masaustu\build\pwa'ya derler
```

Adımlar: simgeler (`araclar\ikon_uret.py`) → `SahaSunucu.exe` (`sunucu.spec`, PyInstaller, tek klasör) →
veri kaynakları (`araclar\kaynak_topla.py`, `_internal\` altına repo ile aynı yerleşim) → electron-builder
(NSIS + portable) → kök kopya. Sürüm: `kod\masaustu\package.json` → `version`. Yollar: `kod\yollar.py`.

| Parça | Dosya |
|---|---|
| Sunucu girişi (yolları VERİ klasörüne yönlendirir, repo koduna dokunmaz) | `kod\masaustu\sunucu_giris.py` |
| Kabuk (sunucu yaşam döngüsü, tepsi, pencereler) | `kod\masaustu\electron\main.cjs` |
| Kabuk ekranları (açılıyor / ilk kurulum / hata · telefon · ayarlar) | `kod\masaustu\electron\ekran\` |
| Kurulum eklentisi (güncellemede düzgün kapatma) | `kod\masaustu\nsis\installer.nsh` |
| Uçtan uca deneme | `kod\masaustu\araclar\uctan_uca.cjs` |

Sunucu komut satırından da kullanılır (kurulu klasörde `resources\sunucu\SahaSunucu.exe`):
`durum · kur · kodlar · yedek · ice-aktar --kaynak <db> · geri-yukle --dosya <yedek> · surum`, hepsi `--veri <klasör>` alır.

Deneme (gerçek veriye dokunmadan; **canlı klasöre ve 8080'e yöneltmeyin**):

* `DehanetSaha.exe --veri=<karalama> --port=8111 --yerel --profil=<karalama> --dogrula=<sonuc.json>` →
  sunucu + pencere hazır olunca durumu JSON'a yazar (yalnız sayılar) ve düzgün kapanır.
* `node kod\masaustu\araclar\uctan_uca.cjs --kaynak=<saha.db kopyası> --port=8116` → ilk kurulum ve
  "var olan veriyi getir + göç" senaryoları, `--kapat` ile düzgün çıkış; karalama klasörünü kendisi siler.

## Sunucu sözleşmesi (masaüstünün çalışması için kodun uyması gerekenler)

1. `saha.sunucu.main(["--host", h, "--port", p, "--seviye", s])` kalır; çıkış kodları 0 tamam · 1 hata ·
   2 zaten çalışıyor · 3 güncelleme durdu. Sunucu `uvicorn.run(...)`'ı **modül özelliği** olarak çağırır
   (kabuk düzgün kapatmayı buna takar; değişirse 20 sn sonra zorla kapatır).
2. Yazılan her dosya şu köklerden birinden türetilir: `ayarlar.CALISMA`, `SAHA_DB`/`db.db_yolu().parent`,
   `ayarlar.GIZLI_ANAHTAR`, `ayarlar.KAYIT_DIZINI`, `ayarlar.cikti_dizini()`, `ayarlar.gelen_dizini()`,
   `OPERASYON_VERI`, `OPERASYON_OBEK`. **`yollar.KOK` / `yollar.KOD` (depo) altına yazılmaz**
   (masaüstünde orası salt okunur program klasörüdür).
3. Çalışırken okunan yeni bir veri dosyası `kod\yollar.py` üzerinden okunur ve `kod\masaustu\araclar\kaynak_topla.py` listesine eklenir.
4. Dinamik içe aktarılan modüller `saha`, `operasyon`, `dsale` paketlerinde kalır (otomatik toplanır);
   `testler` / `analiz` adlı alt paketler pakete girmez.
5. `GET /api/saglik` oturumsuz kalır; hazırken 200 ve `surum`, `bina`, `sema_surumu` döner.
6. Donmuş sürümde `kod\arayuz\src` yoktur: `operasyon.v2.api`'nin eski iş emri ekranı denetimi
   (`ESKI_EKRAN.exists()`) orada her zaman "yok" görür, eski uçlar 410 döner.

## Bilinen sınırlar

* Exe **imzasız**: SmartScreen "Windows bilgisayarınızı korudu" derse → **Ek bilgi → Yine de çalıştır**.
  Kod imzalama sertifikası alınınca `package.json` → `build.win` içine eklenir.
* Kurulum dosyaları şirket verisi (bina listesi) içerir: herkese açık yere, GitHub'a koymayın.
  `kod\masaustu\build`, `dist`, `node_modules` ve kökteki `DehanetSaha.exe` `.gitignore`'dadır.
* Paket, derlendiği andaki `kod/saha`, `kod/operasyon`, `kod/dsale` kodunu taşır: kod değişince `DERLE.bat` yeniden.
* Bağlantı `http` (şifresiz): yalnız ofis ağı. Sahadan erişim kararı (VPN / tünel) ayrıdır.
* Aynı bilgisayarda farklı Windows kullanıcıları aynı veri klasörünü paylaşacaksa klasör izinleri
  (Kullanıcılar: Değiştir) elle verilmeli; `gizli.key` bilerek yalnız sunucuyu açan kullanıcıya açıktır.
