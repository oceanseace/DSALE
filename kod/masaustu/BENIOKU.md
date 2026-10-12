# masaustu — Turkcell.exe kabuğu

Amaç: tek tıkla pencere (pywebview) + aynı süreçte sunucu (`saha`), tepsi simgesi, günlük yedek, Excel köprüsü.
Giriş: `turkcell.py` `main()`. Port: canlıda 8080, geliştirmede 8090 (`TURKCELL_PORT`).
`devir.py` ilk açılışta eski `canli/` verisini `veri/canli/`'ya kopyalar (kaynağa dokunmaz). `derle.py` PyInstaller ile exe üretir; `ikon.py` simgeler.
Kim çağırır: kullanıcı (Turkcell.exe) ya da `python kod/masaustu/turkcell.py`.
Bağımlı: `saha` (sunucu, göç), `yollar`. Exe açıkken derleme yapma. Testler: `masaustu/testler`.
