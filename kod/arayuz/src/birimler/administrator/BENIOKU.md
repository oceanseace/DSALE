# Administrator birimi (arayüz)

Amaç: yönetim ekranları.
- `takip/` Pano (menünün en üstü; bütün birimlerin göstergeleri), giriş `takip/index.ts`.
- `ekip/Ekip.tsx` Kişiler: ekleme, unvan, davet kodu, PIN sıfırlama.
- `unvan/Unvanlar.tsx` unvan × yetkinlik matrisi. `VeriKalitesi.tsx` bina veri kalitesi kuralları.
Kim çağırır: yalnız `src/Konsol.tsx` (bölümler `takip`, `ekip`, `unvanlar`, `veri-kalitesi`).
Bağımlı: `cekirdek/api` (yonetim.ts), `cekirdek/konsol`, `cekirdek/ortak`.
Sunucu karşılığı: `kod/saha/ekip_uclari.py`, `admin_uclari.py`, `yetki.py`, `kod/operasyon/v2/takip.py`.
