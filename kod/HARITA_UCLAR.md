# Uçlar — otomatik

Bu dosyayı `kod/araclar/harita_uret.py` üretir; elle düzenleme. Giriş: [`HARITA.md`](HARITA.md).
İzin = `yetki.ROTA_IZNI` (eylemlerden biri yeter; tanımlar `kod/saha/yetki.py` IZINLER).

| Yöntem | Yol | İşleyen | İzin |
|---|---|---|---|
| GET | `/api/admin/kisiler` | `kod/saha/admin_uclari.py:228` kisi_listesi | yetkinlik.yonet · ekip.yonet |
| PATCH | `/api/admin/kisiler/{kullanici_id}` | `kod/saha/admin_uclari.py:244` kisi_duzenle | yetkinlik.yonet · ekip.yonet |
| GET | `/api/admin/matris` | `kod/saha/admin_uclari.py:165` matris_oku | yetkinlik.yonet · ekip.yonet |
| PUT | `/api/admin/matris` | `kod/saha/admin_uclari.py:180` matris_yaz | yetkinlik.yonet |
| GET | `/api/admin/unvanlar` | `kod/saha/admin_uclari.py:69` unvan_listesi | yetkinlik.yonet · ekip.yonet |
| POST | `/api/admin/unvanlar` | `kod/saha/admin_uclari.py:117` unvan_ekle | yetkinlik.yonet |
| PATCH | `/api/admin/unvanlar/{unvan_id}` | `kod/saha/admin_uclari.py:135` unvan_degistir | yetkinlik.yonet |
| GET | `/api/admin/yetkinlikler` | `kod/saha/admin_uclari.py:64` yetkinlik_katalogu | yetkinlik.yonet · ekip.yonet |
| GET | `/api/aktarim` | `kod/operasyon/v2/api.py:1419` aktarim_gecmis | is.yukle |
| POST | `/api/aktarim` | `kod/operasyon/v2/api.py:1403` aktarim_yukle | is.yukle |
| GET | `/api/aktarim/izleme` | `kod/operasyon/v2/api.py:1424` izleme_durum | is.yukle |
| PUT | `/api/aktarim/izleme` | `kod/operasyon/v2/api.py:1428` izleme_yaz | is.yukle |
| POST | `/api/aktarim/{aktarim_id}/uygula` | `kod/operasyon/v2/api.py:1411` aktarim_uygula | is.yukle |
| POST | `/api/aktarim/{aktarim_id}/vazgec` | `kod/operasyon/v2/api.py:1415` aktarim_vazgec | is.yukle |
| GET | `/api/ara` | `kod/saha/arama_uclari.py:386` ara_ucu | oturum |
| GET | `/api/ayar` | `kod/saha/ekip_uclari.py:773` ayar_oku_ucu | oturum |
| POST | `/api/ayar` | `kod/saha/ekip_uclari.py:750` ayar_kaydet | veri.yonet |
| GET | `/api/ayar/altlik` | `kod/saha/yonetim_uclari.py:651` altlik_oku | altlik.oku |
| PUT | `/api/ayar/altlik` | `kod/saha/yonetim_uclari.py:656` altlik_yaz | veri.yonet |
| GET | `/api/ben` | `kod/saha/giris_uclari.py:191` ben | oturum |
| GET | `/api/bina` | `kod/saha/satis_uclari.py:768` bina_listesi | satis.kendi |
| GET | `/api/bina/{bina_serial}` | `kod/saha/satis_uclari.py:813` bina_detay | bina.oku |
| GET | `/api/bina/{bina_serial}/degisim` | `kod/saha/yonetim_uclari.py:281` bina_degisim | veri.yonet |
| GET | `/api/bina/{bina_serial}/ticket` | `kod/saha/yonetim_uclari.py:609` bina_ticketlari | bina.oku |
| GET | `/api/binalar/geometri` | `kod/saha/yonetim_uclari.py:618` bina_geometrisi | geometri.oku |
| GET | `/api/bolgeleme/durum` | `kod/saha/yonetim_uclari.py:112` bolgeleme_durum | veri.yonet |
| GET | `/api/bolgeleme/excel` | `kod/saha/yonetim_uclari.py:183` bolgeleme_excel | veri.yonet |
| POST | `/api/bolgeleme/geri-al` | `kod/saha/yonetim_uclari.py:173` bolgeleme_geri_al | veri.yonet |
| GET | `/api/bolgeleme/is/{is_id}` | `kod/saha/yonetim_uclari.py:154` bolgeleme_is | veri.yonet |
| GET | `/api/bolgeleme/onizleme` | `kod/saha/yonetim_uclari.py:123` bolgeleme_onizleme | veri.yonet |
| POST | `/api/bolgeleme/uygula` | `kod/saha/yonetim_uclari.py:162` bolgeleme_uygula | veri.yonet |
| GET | `/api/boss/akis` | `kod/operasyon/v2/api.py:1721` boss_akis | is.yukle |
| GET | `/api/boss/aski-nedenleri` | `kod/operasyon/v2/api.py:1716` boss_aski_nedenleri | is.duzenle |
| POST | `/api/boss/atama-durumlari` | `kod/operasyon/v2/api.py:1305` boss_atama_durumlari | is.ata |
| POST | `/api/boss/atama-yeniden` | `kod/operasyon/v2/api.py:1310` boss_atama_yeniden | is.ata |
| POST | `/api/boss/detay` | `kod/operasyon/v2/api.py:1869` boss_detay_al | is.yukle |
| POST | `/api/boss/detay-oncelik` | `kod/operasyon/v2/api.py:1864` boss_detay_oncelik | is.liste |
| POST | `/api/boss/detay-onden` | `kod/operasyon/v2/api.py:1786` boss_detay_onden | is.yukle |
| GET | `/api/boss/durum` | `kod/operasyon/v2/api.py:1801` boss_durum | is.liste |
| POST | `/api/boss/ekip-konum` | `kod/operasyon/v2/api.py:1898` boss_ekip_konum | is.yukle |
| GET | `/api/boss/ekipler` | `kod/operasyon/v2/api.py:1894` boss_ekipler | is.ata |
| POST | `/api/boss/esitle` | `kod/operasyon/v2/api.py:1743` boss_esitle | is.yukle |
| POST | `/api/boss/esitle-iste` | `kod/operasyon/v2/api.py:1858` boss_esitle_iste | is.liste |
| GET | `/api/boss/eslesme-kodu` | `kod/operasyon/v2/api.py:1805` boss_eslesme_kodu | is.ata |
| POST | `/api/boss/eslesme-kodu/yenile` | `kod/operasyon/v2/api.py:1809` boss_eslesme_yenile | is.ata |
| GET | `/api/boss/farklar` | `kod/operasyon/v2/api.py:1711` boss_farklar | is.liste |
| GET | `/api/boss/giden` | `kod/operasyon/v2/api.py:1606` boss_giden | is.ata |
| POST | `/api/boss/giden/{is_no}/islendi` | `kod/operasyon/v2/api.py:1610` boss_giden_islendi | is.ata |
| POST | `/api/boss/gunluk` | `kod/operasyon/v2/api.py:1633` boss_gunluk | is.yukle |
| POST | `/api/boss/iletisim` | `kod/operasyon/v2/api.py:1772` boss_iletisim | is.yukle |
| GET | `/api/boss/istekler` | `kod/operasyon/v2/api.py:1838` boss_istekler | is.yukle |
| GET | `/api/boss/izler` | `kod/operasyon/v2/api.py:1767` boss_izler | is.yukle |
| GET | `/api/boss/yazilacaklar` | `kod/operasyon/v2/api.py:1653` boss_yazilacaklar | is.yukle |
| PUT | `/api/boss/yazma-anahtari` | `kod/operasyon/v2/api.py:1685` boss_yazma_anahtari | yetkinlik.yonet |
| POST | `/api/boss/yazma-dene` | `kod/operasyon/v2/api.py:1694` boss_yazma_dene | yetkinlik.yonet |
| POST | `/api/boss/yazma-sonucu` | `kod/operasyon/v2/api.py:1665` boss_yazma_sonucu | is.yukle |
| GET | `/api/boss/yazmalar` | `kod/operasyon/v2/api.py:1319` boss_yazmalar | is.ata |
| POST | `/api/boss/yazmalar/{kayit_id}/yeniden` | `kod/operasyon/v2/api.py:1326` boss_yazma_yeniden | is.ata |
| GET | `/api/dagitim` | `kod/operasyon/v2/api.py:1039` dagitim_liste | is.ata |
| POST | `/api/dagitim/ata` | `kod/operasyon/v2/api.py:1058` dagitim_ata | is.ata |
| PUT | `/api/dagitim/kurallar` | `kod/operasyon/v2/api.py:1047` dagitim_kurallar | is.ata |
| POST | `/api/dagitim/uygula` | `kod/operasyon/v2/api.py:1054` dagitim_uygula | is.ata |
| GET | `/api/dosya/rapor.xlsx` | `kod/saha/satis_uclari.py:1136` gunluk_rapor | satis.izle |
| POST | `/api/giris` | `kod/saha/giris_uclari.py:64` giris | herkese açık |
| POST | `/api/giris/boss/baslat` | `kod/saha/boss_giris.py:230` baslat | herkese açık |
| POST | `/api/giris/boss/bitti` | `kod/saha/boss_giris.py:319` bitti | herkese açık |
| POST | `/api/giris/boss/durum` | `kod/saha/boss_giris.py:292` durum | herkese açık |
| POST | `/api/giris/boss/kimlik` | `kod/saha/boss_giris.py:268` kimlik | herkese açık |
| POST | `/api/gorev/ata` | `kod/saha/satis_uclari.py:347` gorev_ata | satis.izle |
| GET | `/api/gorev/bugun` | `kod/saha/satis_uclari.py:246` gorev_bugun | satis.kendi · satis.izle |
| POST | `/api/gorev/olustur` | `kod/saha/satis_uclari.py:281` gorev_olustur | satis.kendi |
| GET | `/api/harita` | `kod/saha/satis_uclari.py:898` harita | satis.kendi |
| GET | `/api/ilceler` | `kod/operasyon/v2/api.py:1487` ilceler | obek.oku |
| DELETE | `/api/is-emri` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| GET | `/api/is-emri` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| PATCH | `/api/is-emri` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| POST | `/api/is-emri` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| PUT | `/api/is-emri` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| DELETE | `/api/is-emri/{yol:path}` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| GET | `/api/is-emri/{yol:path}` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| PATCH | `/api/is-emri/{yol:path}` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| POST | `/api/is-emri/{yol:path}` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| PUT | `/api/is-emri/{yol:path}` | `kod/saha/api.py:428` _is_emri_yenilendi | herkese açık |
| GET | `/api/isler` | `kod/operasyon/v2/api.py:1091` isler | is.liste |
| POST | `/api/isler` | `kod/operasyon/v2/api.py:1188` yeni_is | is.olustur |
| GET | `/api/isler/ayarlar` | `kod/operasyon/v2/api.py:1125` isler_ayarlar | is.liste |
| PUT | `/api/isler/ayarlar` | `kod/operasyon/v2/api.py:1129` isler_ayarlar_yaz | veri.yonet |
| GET | `/api/isler/boss-ekip` | `kod/operasyon/v2/api.py:1134` boss_ekip | is.ata |
| POST | `/api/isler/boss-ekip/esle` | `kod/operasyon/v2/api.py:1138` boss_ekip_esle | is.ata |
| POST | `/api/isler/dagit/onizle` | `kod/operasyon/v2/api.py:1171` dagit_onizle | is.ata |
| POST | `/api/isler/dagit/uygula` | `kod/operasyon/v2/api.py:1175` dagit_uygula | is.ata |
| GET | `/api/isler/degisim` | `kod/operasyon/v2/api.py:1105` degisim | is.liste |
| GET | `/api/isler/ekip-konumlari` | `kod/operasyon/v2/api.py:1193` isler_ekip_konumlari | is.liste |
| GET | `/api/isler/excel` | `kod/operasyon/v2/api.py:1115` isler_excel | is.excel |
| GET | `/api/isler/gorunumler` | `kod/operasyon/v2/api.py:1063` isler_gorunumler | is.liste |
| PUT | `/api/isler/gorunumler` | `kod/operasyon/v2/api.py:1067` isler_gorunumler_yaz | is.ata |
| POST | `/api/isler/hucre-renk` | `kod/operasyon/v2/api.py:1295` is_hucre_renk | is.duzenle |
| POST | `/api/isler/iliskili/hizala` | `kod/operasyon/v2/api.py:1356` iliskili_hizala | is.ata |
| POST | `/api/isler/iliskili/isler` | `kod/operasyon/v2/api.py:1345` iliskili_isler | is.liste |
| GET | `/api/isler/iliskili/uyumsuz` | `kod/operasyon/v2/api.py:1351` iliskili_uyumsuz | is.liste |
| GET | `/api/isler/kurallar` | `kod/operasyon/v2/api.py:1179` isler_kurallar | is.liste |
| PUT | `/api/isler/kurallar` | `kod/operasyon/v2/api.py:1183` isler_kurallar_yaz | veri.yonet |
| POST | `/api/isler/oneri-onayla` | `kod/operasyon/v2/api.py:1156` oneri_onayla | is.ata |
| GET | `/api/isler/teknikler` | `kod/operasyon/v2/api.py:1146` teknikler | ekip.teknikler |
| PUT | `/api/isler/teknikler/{teknik_id}/bugun-yok` | `kod/operasyon/v2/api.py:1151` teknik_bugun_yok | kapasite.yaz |
| GET | `/api/isler/tercih` | `kod/operasyon/v2/api.py:1074` isler_tercih | is.liste |
| PUT | `/api/isler/tercih` | `kod/operasyon/v2/api.py:1078` isler_tercih_yaz | is.liste |
| PUT | `/api/isler/tercih/unvan` | `kod/operasyon/v2/api.py:1083` isler_tercih_unvan | is.liste |
| POST | `/api/isler/toplu-aski` | `kod/operasyon/v2/api.py:1339` toplu_aski | is.duzenle |
| POST | `/api/isler/toplu-aski/nedenler` | `kod/operasyon/v2/api.py:1334` toplu_aski_nedenleri | is.duzenle |
| POST | `/api/isler/toplu-ata` | `kod/operasyon/v2/api.py:1161` toplu_ata | is.ata |
| POST | `/api/isler/toplu/{toplu_id}/geri-al` | `kod/operasyon/v2/api.py:1167` toplu_geri_al | is.ata |
| GET | `/api/isler/{is_no}` | `kod/operasyon/v2/api.py:1200` is_ayrinti | is.liste |
| POST | `/api/isler/{is_no}/arama` | `kod/operasyon/v2/api.py:1278` arama | is.duzenle |
| POST | `/api/isler/{is_no}/ata` | `kod/operasyon/v2/api.py:1208` ata | is.ata |
| POST | `/api/isler/{is_no}/bizim-durum` | `kod/operasyon/v2/api.py:1290` bizim_durum | is.duzenle |
| GET | `/api/isler/{is_no}/boss-aski-nedenleri` | `kod/operasyon/v2/api.py:1705` is_boss_aski_nedenleri | is.duzenle |
| POST | `/api/isler/{is_no}/boss-bagla` | `kod/operasyon/v2/api.py:1378` boss_bagla | is.ata |
| GET | `/api/isler/{is_no}/boss-detay` | `kod/operasyon/v2/api.py:1823` boss_detay_oku | is.liste |
| POST | `/api/isler/{is_no}/boss-detay` | `kod/operasyon/v2/api.py:1815` boss_detay_iste | is.liste |
| POST | `/api/isler/{is_no}/boss-islendi` | `kod/operasyon/v2/api.py:1373` boss_islendi | is.ata |
| GET | `/api/isler/{is_no}/boss-yazma-onizleme` | `kod/operasyon/v2/api.py:1362` boss_yazma_onizleme | is.liste |
| POST | `/api/isler/{is_no}/btk-sikayet` | `kod/operasyon/v2/api.py:1284` btk_sikayet | is.duzenle |
| POST | `/api/isler/{is_no}/durum` | `kod/operasyon/v2/api.py:1220` durum | is.saha · is.duzenle |
| POST | `/api/isler/{is_no}/geri-al` | `kod/operasyon/v2/api.py:1383` geri_al | is.ata · is.duzenle · is.saha |
| PATCH | `/api/isler/{is_no}/iletisim` | `kod/operasyon/v2/api.py:1261` iletisim | is.duzenle |
| POST | `/api/isler/{is_no}/isaret` | `kod/operasyon/v2/api.py:1300` is_isaret | is.duzenle |
| POST | `/api/isler/{is_no}/kopya` | `kod/operasyon/v2/api.py:1268` kopya | is.musteri |
| POST | `/api/isler/{is_no}/mahalle` | `kod/operasyon/v2/api.py:1251` is_mahalle | is.duzenle |
| POST | `/api/isler/{is_no}/not` | `kod/operasyon/v2/api.py:1256` is_not | is.duzenle · is.saha |
| POST | `/api/isler/{is_no}/obek` | `kod/operasyon/v2/api.py:1246` is_obek | is.duzenle |
| POST | `/api/isler/{is_no}/randevu` | `kod/operasyon/v2/api.py:1214` randevu | is.ata · is.randevu |
| POST | `/api/isler/{is_no}/tcs` | `kod/operasyon/v2/api.py:1368` tcs | is.duzenle |
| POST | `/api/isler/{is_no}/teshis` | `kod/operasyon/v2/api.py:1228` teshis | is.duzenle |
| DELETE | `/api/isler/{is_no}/ticket` | `kod/operasyon/v2/api.py:1241` ticket_ayir | is.duzenle |
| POST | `/api/isler/{is_no}/ticket` | `kod/operasyon/v2/api.py:1234` ticket_bagla | is.duzenle |
| GET | `/api/islerim` | `kod/operasyon/v2/api.py:1389` islerim | is.saha |
| POST | `/api/islerim/gordu` | `kod/operasyon/v2/api.py:1393` gordu | is.saha |
| POST | `/api/islerim/sira` | `kod/operasyon/v2/api.py:1398` sira | is.saha |
| GET | `/api/kalite/liste` | `kod/saha/yonetim_uclari.py:78` kalite_liste | veri.yonet |
| GET | `/api/kalite/ozet` | `kod/saha/yonetim_uclari.py:71` kalite_ozet | veri.yonet |
| POST | `/api/kalite/yenile` | `kod/saha/yonetim_uclari.py:94` kalite_yenile | veri.yonet |
| GET | `/api/kesinti` | `kod/operasyon/v2/api.py:1587` kesinti_liste | is.duzenle |
| POST | `/api/kesinti` | `kod/operasyon/v2/api.py:1591` kesinti_ekle | is.duzenle |
| GET | `/api/kesinti/aday` | `kod/operasyon/v2/api.py:1596` kesinti_aday | is.duzenle |
| POST | `/api/kesinti/{kesinti_id}/bitti` | `kod/operasyon/v2/api.py:1600` kesinti_bitti | is.duzenle |
| GET | `/api/kullanici` | `kod/saha/ekip_uclari.py:136` kullanici_listesi | ekip.yonet |
| POST | `/api/kullanici` | `kod/saha/ekip_uclari.py:352` kullanici_kaydet | ekip.yonet |
| POST | `/api/kullanici/gorevler` | `kod/saha/ekip_uclari.py:469` kullanici_gorevler | ekip.yonet |
| POST | `/api/kullanici/rehber` | `kod/saha/ekip_uclari.py:932` kullanici_rehber | ekip.yonet |
| GET | `/api/kullanici/rehber/esleme` | `kod/saha/ekip_uclari.py:1028` rehber_esleme_oku | ekip.yonet |
| PUT | `/api/kullanici/rehber/esleme` | `kod/saha/ekip_uclari.py:1034` rehber_esleme_yaz | ekip.yonet |
| DELETE | `/api/kullanici/{kullanici_id}` | `kod/saha/ekip_uclari.py:647` kullanici_sil | ekip.yonet |
| GET | `/api/kullanici/{kullanici_id}` | `kod/saha/ekip_uclari.py:150` kullanici_getir | ekip.yonet |
| POST | `/api/kullanici/{kullanici_id}/cihaz-cikis` | `kod/saha/ekip_uclari.py:805` cihaz_cikis | ekip.yonet |
| POST | `/api/kullanici/{kullanici_id}/davet` | `kod/saha/ekip_uclari.py:528` kullanici_davet | ekip.yonet |
| GET | `/api/kullanici/{kullanici_id}/iliskiler` | `kod/saha/ekip_uclari.py:632` kullanici_iliskileri | ekip.yonet |
| POST | `/api/kullanici/{kullanici_id}/is-aktar` | `kod/saha/ekip_uclari.py:705` kullanici_is_aktar | ekip.yonet |
| POST | `/api/kullanici/{kullanici_id}/pin-sifirla` | `kod/saha/ekip_uclari.py:779` pin_sifirla | ekip.yonet |
| GET | `/api/mahalleler` | `kod/operasyon/v2/api.py:1481` mahalleler | obek.oku |
| POST | `/api/mahalleler` | `kod/operasyon/v2/api.py:1491` mahalle_ekle | mahalle.ekle |
| POST | `/api/mahalleler/esad` | `kod/operasyon/v2/api.py:1508` mahalle_esad | mahalle.ekle |
| POST | `/api/mahalleler/yukle` | `kod/operasyon/v2/api.py:1523` mahalle_yukle | mahalle.yukle |
| GET | `/api/obekler` | `kod/operasyon/v2/api.py:1440` obekler | obek.oku |
| POST | `/api/obekler` | `kod/operasyon/v2/api.py:1444` obek_olustur | obek.duzenle |
| POST | `/api/obekler/geri-al` | `kod/operasyon/v2/api.py:1471` obek_geri_al | obek.duzenle |
| DELETE | `/api/obekler/{obek_id}` | `kod/operasyon/v2/api.py:1466` obek_sil | obek.duzenle |
| PATCH | `/api/obekler/{obek_id}` | `kod/operasyon/v2/api.py:1449` obek_guncelle | obek.duzenle |
| POST | `/api/obekler/{obek_id}/bol` | `kod/operasyon/v2/api.py:1476` obek_bol | obek.duzenle |
| POST | `/api/obekler/{obek_id}/mahalle` | `kod/operasyon/v2/api.py:1455` obek_mahalle | obek.duzenle |
| POST | `/api/obekler/{obek_id}/mahalle/cikar` | `kod/operasyon/v2/api.py:1461` obek_cikar | obek.duzenle |
| POST | `/api/onemap/binalar` | `kod/saha/onemap_esitle.py:626` onemap_binalar | is.yukle |
| GET | `/api/onemap/durum` | `kod/saha/onemap_esitle.py:632` onemap_durum | is.yukle · is.ata |
| GET | `/api/onemap/gorev` | `kod/saha/onemap_esitle.py:621` onemap_gorev | is.yukle |
| GET | `/api/oturum/boss` | `kod/saha/boss_giris.py:326` oturum_yokla | oturum |
| GET | `/api/ozet/gun` | `kod/saha/satis_uclari.py:987` ozet_gun | satis.izle |
| GET | `/api/ozet/kapsama` | `kod/saha/satis_uclari.py:1047` ozet_kapsama | satis.kendi · satis.izle |
| POST | `/api/pin` | `kod/saha/giris_uclari.py:132` pin_belirle | herkese açık |
| GET | `/api/rut` | `kod/operasyon/v2/rut_api.py:67` rut_gun | is.duzenle |
| PUT | `/api/rut/ayar` | `kod/operasyon/v2/rut_api.py:80` rut_ayar | is.duzenle |
| PUT | `/api/rut/hucre` | `kod/operasyon/v2/rut_api.py:75` rut_hucre | is.duzenle |
| GET | `/api/saglik` | `kod/saha/api.py:202` saglik | herkese açık |
| GET | `/api/tablolar` | `kod/saha/tablolar_uclari.py:252` tablolar_ozet | tablolar.oku |
| POST | `/api/tablolar/altyapi` | `kod/saha/tablolar_uclari.py:313` altyapi_ekle | ticket.defter |
| PATCH | `/api/tablolar/altyapi/{kayit_id}` | `kod/saha/tablolar_uclari.py:335` altyapi_guncelle | ticket.defter |
| GET | `/api/tablolar/{sekme}` | `kod/saha/tablolar_uclari.py:276` tablo | tablolar.oku |
| GET | `/api/takip` | `kod/operasyon/v2/api.py:1549` takip_ | takip.oku |
| GET | `/api/takip/erisim` | `kod/operasyon/v2/api.py:1559` takip_erisim | takip.tam |
| PUT | `/api/takip/kapasite` | `kod/operasyon/v2/api.py:1569` takip_kapasite | kapasite.yaz |
| GET | `/api/takip/satis` | `kod/operasyon/v2/api.py:1554` takip_satis | takip.tam |
| GET | `/api/takip/yonetim` | `kod/operasyon/v2/api.py:1564` takip_yonetim | takip.tam |
| GET | `/api/ticket` | `kod/saha/yonetim_uclari.py:337` ticket_liste | ticket.oku · ticket.defter |
| POST | `/api/ticket` | `kod/saha/yonetim_uclari.py:507` ticket_olustur | ticket.defter |
| GET | `/api/ticket/harita` | `kod/saha/yonetim_uclari.py:483` ticket_harita | ticket.oku · ticket.defter |
| GET | `/api/ticket/isler` | `kod/saha/yonetim_uclari.py:402` ticket_is_secenekleri | ticket.defter |
| GET | `/api/ticket/kategoriler` | `kod/saha/yonetim_uclari.py:478` ticket_kategorileri | ticket.sablon |
| GET | `/api/ticket/lokasyon` | `kod/saha/yonetim_uclari.py:365` ticket_lokasyon | ticket.defter |
| GET | `/api/ticket/musteri` | `kod/saha/yonetim_uclari.py:385` ticket_musteri | ticket.defter |
| GET | `/api/ticket/sablon` | `kod/saha/yonetim_uclari.py:350` ticket_sablon | ticket.sablon |
| GET | `/api/ticket/temizlik` | `kod/saha/yonetim_uclari.py:422` ticket_temizlik_onizle | ticket.defter |
| POST | `/api/ticket/temizlik` | `kod/saha/yonetim_uclari.py:429` ticket_temizlik | ticket.defter |
| GET | `/api/ticket/{ticket_id}` | `kod/saha/yonetim_uclari.py:527` ticket_getir | ticket.oku · ticket.defter |
| PATCH | `/api/ticket/{ticket_id}` | `kod/saha/yonetim_uclari.py:536` ticket_guncelle | ticket.defter |
| GET | `/api/ticket/{ticket_id}/ek` | `kod/saha/ek_dosya.py:318` ek_listesi | ticket.oku · ticket.defter · bina.oku |
| POST | `/api/ticket/{ticket_id}/ek` | `kod/saha/ek_dosya.py:377` ek_yukle | ticket.defter · is.saha |
| GET | `/api/ticket/{ticket_id}/ek/{ek_id}` | `kod/saha/ek_dosya.py:335` ek_tam | ticket.oku · ticket.defter · bina.oku |
| GET | `/api/ticket/{ticket_id}/ek/{ek_id}/kucuk` | `kod/saha/ek_dosya.py:344` ek_kucuk | ticket.oku · ticket.defter · bina.oku |
| POST | `/api/ticket/{ticket_id}/isler` | `kod/saha/yonetim_uclari.py:572` ticket_is_ekle | ticket.defter |
| POST | `/api/ticket/{ticket_id}/isler/cikar` | `kod/saha/yonetim_uclari.py:586` ticket_is_cikar | ticket.defter |
| POST | `/api/ticket/{ticket_id}/sil` | `kod/saha/yonetim_uclari.py:560` ticket_sil | ticket.defter |
| GET | `/api/veri/bekleyen` | `kod/saha/yonetim_uclari.py:239` bekleyen_binalar | veri.yonet |
| GET | `/api/veri/bekleyen.txt` | `kod/saha/yonetim_uclari.py:247` bekleyen_kimlikler | veri.yonet |
| POST | `/api/veri/onemap` | `kod/saha/yonetim_uclari.py:263` onemap_yukle | veri.yonet |
| GET | `/api/veri/onemap-araci.js` | `kod/saha/yonetim_uclari.py:255` onemap_araci | veri.yonet |
| GET | `/api/veri/tur-raporu` | `kod/saha/yonetim_uclari.py:214` tur_raporu_liste | veri.yonet |
| POST | `/api/veri/tur-raporu` | `kod/saha/yonetim_uclari.py:203` tur_raporu_yukle | veri.yonet |
| POST | `/api/veri/tur-raporu/uygula` | `kod/saha/yonetim_uclari.py:228` tur_raporu_uygula | veri.yonet |
| GET | `/api/veri/tur-raporu/{tur_id}` | `kod/saha/yonetim_uclari.py:220` tur_raporu_getir | veri.yonet |
| GET | `/api/yollar` | `kod/saha/satis_uclari.py:927` yollar | satis.kendi |
| POST | `/api/ziyaret` | `kod/saha/satis_uclari.py:652` ziyaret_ekle | satis.kendi |
| POST | `/api/ziyaret/toplu` | `kod/saha/satis_uclari.py:665` ziyaret_toplu | satis.kendi |
| POST | `/api/ziyaret/{ziyaret_id}/iptal` | `kod/saha/satis_uclari.py:707` ziyaret_iptal | satis.kendi |
| GET | `/boss-giris/{istek_id}` | `kod/saha/boss_giris.py:250` tarayici_sayfasi | herkese açık |
