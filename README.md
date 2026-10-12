# Turkcell

Bayi iş akışı uygulaması (Bursa + Yalova). Her şey bu klasörde yaşar; bilgisayarda başka yere yazılmaz.

## Kullanım

**`Turkcell.exe`'ye çift tıklayın.** Pencere açılır, sunucu ve API'ler uygulamanın içinde başlar, hazır olunca
ekran gelir.

- **İlk açılış:** eski düzendeki canlı veri (`canli\`) doğrulanmış bir kopyayla bir kez `veri\canli\`'ye devredilir
  (`veri\canli\devir.json`). Eski klasöre dokunulmaz. Şema güncellemesi açılışta, yedek alınarak kendiliğinden yapılır.
- **Windows Güvenlik Duvarı** ilk açılışta soru sorarsa **"İzin ver"** deyin (özel ağ): telefonlar ofis ağından bu
  yolla bağlanır. Adres: bildirim alanındaki Turkcell simgesi → *Telefonlar için adres* (panoya kopyalar).
- **Pencereyi kapatmak sunucuyu kapatmaz**; telefonlar çalışmaya devam eder. Tamamen kapatmak: simge → *Çıkış*.
- **Administrator** hesabı `veri\canli\turkcell.json` dosyasındaki telefonla tanınır (git dışı).
- **Yedek:** günde bir, kendiliğinden (`veri\canli\saha\yedek\`).

## Klasörler

`Turkcell.exe` uygulama · `kod\` kaynak kod · `veri\` bina verisi, çıktılar (`veri\cikti\`) ve canlı veri
(`veri\canli\`) · `belgeler\` kılavuzlar. Gizli: `.turkcell\` (uygulama dosyaları), `canli\` (eski düzen),
`gelistirme\` (geliştirme verisi), `.venv\`, `.git\`.

## Geliştirici notları

```
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r kod\requirements.txt
cd kod\arayuz && npm install && node node_modules\vite\bin\vite.js build
.venv\Scripts\python.exe kod\masaustu\derle.py        → kökte Turkcell.exe + .turkcell\
.venv\Scripts\python.exe -m pytest                    bütün testler (kökten, ~10 dk)
```

Deneme: `TURKCELL_PORT=8097`, `SAHA_VERI_DIZINI=<mutlak yol>` (verilirse devir yapılmaz). Yollar tek yerde:
`kod\yollar.py`. Arayüz birimleri: `kod\arayuz\README.md`.
