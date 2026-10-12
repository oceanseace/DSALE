# Saha birimi (arayüz)

Amaç: 8 satışçının telefonu ve satış yönetimi.
- `ekran/` satışçı: Bugün · Bina · Harita · Ben (+ sonuç ve ticket metni çekmeceleri).
- `yonetim/` yönetici: Canlı · Kapsama · Görev atama · Rapor · Tur raporu.
- `bolge/` Bölge planlayıcı (ekip sayısı değişince bölgeleri yeniden böler).
Kim çağırır: `src/App.tsx` (#/bugun, #/bina/<seri>, #/harita, #/ben) ve `src/Konsol.tsx` (yönetim bölümleri).
Bağımlı: `cekirdek/api` (uclar.ts, yonetim.ts), `cekirdek/yerel` (çevrimdışı kuyruk, bugün listesi), `cekirdek/harita`, `cekirdek/konsol`, `cekirdek/ortak`.
Sunucu karşılığı: `kod/saha/satis_uclari.py`, `kod/saha/yonetim_uclari.py`, `kod/saha/rota.py`.
