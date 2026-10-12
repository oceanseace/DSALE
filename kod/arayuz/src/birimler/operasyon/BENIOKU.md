# Operasyon birimi (arayüz)

Amaç: BOSS'tan canlı gelen açık işleri Excel gibi yönetmek (TASKS), haritada görmek (MAP), BOSS eklentisinin durumunu izlemek.
Giriş: `isler/index.ts` (Isler · BossBaglantisi · IsHaritasiEkrani) ve `obekler/index.ts` (Obekler, menüde gizli).
- `isler/Isler.tsx` ekran → `Tablo.tsx` ızgara; sütunlar `sutunlar.ts`; veri deposu `durum.tsx` (GET /api/isler?ek=1 + değişim yoklaması).
- `isler/IsCekmecesi.tsx` tek işin çekmecesi; `isler/map/` MAP ekranının parçaları.
Kim çağırır: yalnız `src/Konsol.tsx` (bölümler `isler`, `is-haritasi`, `boss`, `obekler`).
Bağımlı: `cekirdek/is` (iş modeli + /api/isler istemcisi), `cekirdek/ortak`, `cekirdek/harita`, `cekirdek/yol`.
Sunucu karşılığı: `kod/operasyon/v2/` (api.py uçları, gorunum.py satır biçimi). Akış: `kod/HARITA.md` §1.
- Kişisel tercihler (düzen, adlı düzenler, TASKS↔MAP ortak süzgeç) sunucuda: `isler/tercihDeposu.ts` (GET/PUT /api/isler/tercih); Düzen menüsü `isler/DuzenMenusu.tsx`; MAP süzgeç şeridi/çekmecesi `isler/map/MapSuzgec.tsx`.
