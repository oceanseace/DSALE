# Altyapı birimi (arayüz)

Amaç: altyapı sorunlarının takibi.
- `ticket/Ticketlar.tsx` Excel TICKET sayfası gibi tablo (Müşteri No "+N" özeti · Loc ID · Site · Task No · Task adı ⚠ ·
  Konu · Durum · Satış kanalı · Ticket · Başlangıç · Detay); hücreden konu/durum/ticket no (Hata'da no istenmez);
  ⋯ menü: "Çözüldü, 3 aydan eski" toplu temizlik. `TicketAyrinti.tsx` çekmece: işler, "+ abone ekle", Sil (kalıcı, iz bırakmaz).
  Varsayılan görünüm "Açık engeller": açık ticket'lar (TASKS'ta Bizim durum Port yok · Kıl yok · Sinyal yok ·
  Güzergah yok → iş ertelenir, ticket'a bağlanır; ticket Çözüldü → bağlı ve seçilen işler "Aranacak", bildirimde task no).
- `ticket/YeniSatir.tsx` + `ticket/IsSecici.tsx`: Müşteri No / Loc ID → açık işlerden seçim (kurulum önceden seçili,
  "Hepsini seç"), aynı lokasyonda ticket uyarısı (`bildirim.ts benzerMetni`). Konu/Durum: `hucreler.tsx Acilir`.
- `ticket/TicketFotolari.tsx` (+ `fotoApi.ts`, `fotolar.css`): ticket fotoğrafları.
  Eski "Tablolar" ekranı 2026-10'da kaldırıldı (sunucu uçları `/api/tablolar*` duruyor).
Kim çağırır: yalnız `src/Konsol.tsx` (bölüm `ticketlar`).
Bağımlı: `cekirdek/api` (yonetim.ts ticket uçları), `cekirdek/ticket` (iş seçici, silme, temizlik, yeni ticket açma),
`cekirdek/ortak`, `cekirdek/konsol`.
Sunucu karşılığı: `kod/saha/ticket.py` + `yonetim_uclari.py` (/api/ticket*), `ek_dosya.py`.
