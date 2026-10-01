# DSALE

Dehanet EÇM · Bursa fiber saha sistemi. Her şey bu klasörde.

**Her gün:** `BASLAT.bat` — çalışan sistemi açar. Başka bir şeye gerek yok.

## Ne nerede

| Yer | Ne |
|---|---|
| `BASLAT.bat` | Saha Sistemi'ni açar (canlı). |
| `YAYINLA.bat` | Yeni sürümü canlıya geçirir — hazırlanıyor. |
| `canli/` | Çalışan sistem ve gerçek veri. Elle dokunmayın. |
| `kod/` | Bütün kaynak kod. Yollar tek dosyada: `kod/yollar.py`. |
| `veri/` | Bina verisi: `raw/` ham · `master/` işlenmiş · `ref/` harita ve sözlükler. |
| `cikti/` | Sunum (`DSALE_Sunum.exe`), bölge planları, Excel raporları. |
| `belgeler/` | Kılavuzlar: `SAHA_KULLANIM.md` · `SUNUM.md` · `MASAUSTU.md` · `LISANS.md`. |
| `gelistirme/` | Geliştirme verisi (git dışı; gerçek verinin kopyası olabilir). |

`kod/` içinde: `saha/` sunucu · `operasyon/` iş emirleri · `dsale/` bölgeleme ·
`lisans/` lisans · `arayuz/` telefon ve yönetici uygulaması · `sunum/` 3B sunum ·
`masaustu/` masaüstü paketi · `eklenti/` tarayıcı eklentisi · `araclar/` komut satırı araçları.

## Geliştirme

```
.venv\Scripts\python.exe -m pytest                  bütün testler (kökten)
kod\saha\GELISTIRME_BASLAT.bat                      geliştirme sunucusu · 127.0.0.1:8090 · gelistirme\veri
cd kod\arayuz  &&  npm run build                    arayüzü derle
.venv\Scripts\python.exe kod\araclar\bolge.py --n 10    10 bölgelik plan → cikti\N10_res_hp
```

Python komutları `kod\`'u içe aktarma yoluna ister: `.bat` dosyaları ve `pytest.ini` bunu
kendisi yapar; elle çalıştırırken `set PYTHONPATH=kod`.
Geliştirme hiçbir zaman `canli\` klasörüne ve 8080 portuna dokunmaz.
