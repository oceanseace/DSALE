# Teknik birimi (arayüz)

Amaç: teknisyenin telefonundaki "İşlerim": sıralı iş listesi ve tek büyük düğmeli iş ekranı (Yola çıktım → Başladım → Bitti).
Giriş: `index.ts` → `Islerim.tsx` (#/islerim) · `IsEkrani.tsx` (#/islerim/<is_no>).
Çevrimdışı: düğme basışları `kuyruk.ts`'te bekler; `yerel.ts` listeyi telefonda tutar; sunucu çağrıları `api.ts`.
Kim çağırır: `src/App.tsx` (ekran + `isKuyrugunuBaslat/isKuyrugunuGonder` ek kuyruk olarak senkrona bağlanır).
Bağımlı: `cekirdek/is`, `cekirdek/yerel`, `cekirdek/ortak`, `cekirdek/api`.
Sunucu karşılığı: `kod/operasyon/v2/api.py` (/api/islerim*, /api/isler/{is_no}/…), `gorunum.islerim`.
