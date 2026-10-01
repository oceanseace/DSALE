# -*- coding: utf-8 -*-
"""cikti/is_emri_analizi.json -> is_emri_analizi.md (Türkçe rapor). Önce is_emri_analizi.py çalışmalı."""
import json
from pathlib import Path

HERE = Path(__file__).parent
R = json.loads((HERE / "cikti" / "is_emri_analizi.json").read_text(encoding="utf-8"))
L = []
w = L.append


def s(x, d=0):
    """Türkçe sayı biçimi: 1.234 / 12,5"""
    if x is None:
        return "–"
    if d == 0:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def p(x, d=0):
    return "–" if x is None else "%" + s(100 * x, d)


def dd(d):
    return ", ".join(f"{k}: {v}" for k, v in (d or {}).items())


def tablo(baslik, satirlar):
    w("| " + " | ".join(baslik) + " |")
    w("|" + "|".join(["---"] * len(baslik)) + "|")
    for r in satirlar:
        w("| " + " | ".join(str(c) for c in r) + " |")
    w("")


SORULAR = [
    "`TAMAMLANDI.xlsx` ve `ANLATILAN.xlsx` (masaüstü) bu analizde kullanılabilir mi? Kurulum için de aynı biçimde 'Tamamlandı' raporu (son 30 gün, tüm tipler, Teknik Ekip İşe Başlama/Bitirme sütunlarıyla) çekilebilir mi?",
    "Kanal Şikayeti'nin ~7 gün 'abone kaynaklı askı'da bekletilmesi Turkcell'in istediği bir kural mı, yoksa aynı gün telefonla kapatılabilir mi? BTK ölçümüne giriyor mu?",
    "Esas alınacak hedef hangisi: bayi SL'i (Bağlantı 24s, TV 16s) mi, Turkcell FOX hedefi (Bağlantı 12s, TV 6s) mi, yoksa 'her iş 24 saat' kuralı mı?",
    "2.Donanım (125 açık), Yan Oda, TV+ Kurulum (mevcut aboneye TV), Fiber Dönüşüm/Nakil kimde: arıza ekibinde mi kurulum ekibinde mi?",
    "Cihaz İade Bekleniyor (218 açık): cihazı teknisyen mi topluyor, müşteri bayiye mi getiriyor / kargo mu? Kim kapatıyor?",
    "'BOSS üzerinden arama sağlandı, ulaşılamadı' notunu kim düşüyor (operasyon mu, teknisyen mi)? Günde kaç kişi mevcut müşteriyi arıyor?",
    "Arıza ekibi kaç kişi ve vardiya düzeni ne (12 kişi, Pazar nöbeti 4–8)? Gerektiğinde kurulumcudan arızaya kaydırma mümkün mü? Mesai kaçta başlıyor (ilk kapanışlar ~11:00)?",
    "BOSS'ta 'Randevulu' gerçekten müşteriye bildirilen 2 saatlik bir dilim mi, yoksa yalnızca ekibe atama kaydı mı?",
    "Yalnız FOX'ta kalan 56 kayıt (Donanım Teslimat Şikayet 25, BTK Şikayet 5, Kurulum Taskı Ürememiş 4 …) kimin sorumluluğunda ve nereden kapatılıyor?",
    "Lokasyonu olmayan işler (Superbox, Kanal Şikayeti, TT Fiber, Cihaz İade) için adres metninden yerel (ağ çağrısız) mahalle eşlemesi yapılmasına izin var mı?",
]
TX, SL, BR, GI, TK, RV, PS, PR = (R[k] for k in ["taksonomi", "sla", "birikim", "giris", "teknisyen", "randevu", "ps26", "parametreler"])
mv = BR["sahip"]["mevcut_musteri"]; yn = BR["sahip"]["yeni_musteri_kurulum"]
koh = SL["gercek_24s_uyum_kohort"]; gi = GI["mevcut_gelen_ozet"]; ver = TK["tamamlanan_verimlilik_3_15_eylul"]
kap = TX["kapanis_nedenleri_3_15_eylul"]; tek = TX["tekrar_ariza_1_15_eylul"]
toplam = R["meta"]["satir"]["boss_acik"]

w("# İş Emri Analizi — BOSS + FOX açık kayıtlar (29 Eylül 2026)")
w("")
w(f"*Referans an: {R['meta']['referans_an'].replace('T', ' ')} · Üreten: `operasyon/analiz/is_emri_analizi.py` → "
  "`cikti/is_emri_analizi.json` → bu rapor (`rapor_md.py`). Tüm sayılar toplu; müşteri adı/no/adres/telefon, task no ve "
  "tekil lokasyon kimliği yoktur.*")
w("")

# ------------------------------------------------------------------ ÖZET
w("## 0. Yönetici özeti — 12 bulgu")
w("")
ozet = [
    f"**Açık iş: {s(toplam)}** (BOSS) — **{s(mv['n'])} mevcut müşteri** (sizin sorumluluğunuz, 2.Donanım 125 dahil; bunlardan {s(mv['btk'])} adedi BTK'ya sayılan "
    f"bağlantı/TV/kanal/arama) + **{s(yn['n'])} yeni müşteri kurulum**. BOSS kayıtlarının %99,8'i FOX'ta da var "
    f"({s(TX['fox_boss_birlesim']['ortak'])} ortak; {TX['fox_boss_birlesim']['sadece_fox']} yalnız FOX'ta, "
    f"{TX['fox_boss_birlesim']['sadece_boss']} yalnız BOSS'ta).",
    f"**Gerçek 24 saat uyumu (mevcut müşteri, 1–14 Eylül kohortu): {p(koh['orani']['24s'])}.** 12 saatte "
    f"{p(koh['orani']['12s'])}, 48 saatte {p(koh['orani']['48s'])}. Gün gün **%65'ten (1 Eylül) %21–24'e (12–14 Eylül) "
    "düştü** — birikim büyüdükçe yeni gelen iş eski işin arkasında bekliyor.",
    f"**Giriş hızı (mevcut müşteri, sansürsüz): takvim günü ortalama {s(gi['takvim_gunu_ort'])}/gün** "
    f"(hafta içi {s(gi['hafta_ici_ort'])}, Cumartesi {s(gi['cumartesi_ort'])}, Pazar {s(gi['pazar_ort'])}). "
    f"Sizin '250–300' tahmininiz doğru mertebede. Kapanış ise hafta içi ~{s(PR['mevcut_kapasite_acigi']['yapilan_7_15_eylul_ort'])}/gün → "
    "**günde ~80–110 iş açık veriliyor**, birikim bu yüzden büyüyor.",
    f"**Bağlantı Problemi tek başına mevcut girişin yaklaşık %{s(100*GI['mevcut_tip_payi']['BAGLANTI'])} kadarı** (~{s(GI['mevcut_tip_bazinda_gunluk_tahmin']['BAGLANTI']['gunluk_ort'])}/gün); "
    f"ardından Kanal Şikayeti (~{s(GI['mevcut_tip_bazinda_gunluk_tahmin']['KANAL_SIKAYETI']['gunluk_ort'])}), Cihaz İade "
    f"(~{s(GI['mevcut_tip_bazinda_gunluk_tahmin']['CIHAZ_IADE']['gunluk_ort'])}), Modem Değişikliği "
    f"(~{s(GI['mevcut_tip_bazinda_gunluk_tahmin']['MODEM_DEGISIKLIGI']['gunluk_ort'])}), TV+ Arıza "
    f"(~{s(GI['mevcut_tip_bazinda_gunluk_tahmin']['TV_ARIZA']['gunluk_ort'])}).",
    f"**BTK arızalarında ziyaretsiz kapanabilecek pay {p(PR['ziyaretsiz_kapanis_orani_btk_ariza'])}**: "
    f"{p(PR['telefon_uzaktan_neden_orani_btk_ariza'])} 'müşteri sorunun düzeldiğini söyledi / çağrı merkezi çözebilirdi', "
    "~%12 şebeke/genel arıza, ~%3 ofis kapanışı. Teknisyenin gidip 'düzelmiş' bulduğu işler de dahil olduğu için bu bir ÜST SINIR; "
    "'önce ara/uzaktan kontrol et, sonra gönder' filtresinin gerçekçi eleme payı tahminen %25–35.",
    f"**Kanal Şikayeti hiç sahaya gitmiyor**: kapananlarda ofis kapanışı {p(kap['KANAL_SIKAYETI']['ofis_kapanis_orani'])}, "
    f"'müşteri düzeldi dedi' nedeni {p(kap['KANAL_SIKAYETI']['neden_girilenlerde']['telefon_uzaktan'])}; ama medyan "
    f"{s(SL['tamamlanma_suresi_saat']['tip']['KANAL_SIKAYETI']['p50'])} saat (≈7 gün) 'abone kaynaklı askı'da bekletiliyor → 24 saat "
    f"uyumu {p(koh['tip_bazinda']['KANAL_SIKAYETI']['uyum_24s'])}. Aynı gün telefonla kapatılabilir.",
    f"**Tekrarlayan arıza yüksek**: 1–15 Eylül'deki {s(tek['task'])} BTK arıza task'ı içinde tekrar payı {p(tek['tekrar_task_orani'])}: "
    f"aynı müşteride 15 gün içinde 2., 3. kez açılmış ({s(tek['birden_fazla_task_musteri'])} müşteri).",
    f"**Atama yok denecek kadar az**: {s(toplam)} açık işin {s(TK['boss_acik_ekip_ozet']['atanmamis_is'])} adedinde Ekip boş. "
    "BOSS'ta 'Randevulu' = ekibe 2 saatlik dilimle atanmış demek (randevulu işlerin %98'inde ekip dolu, randevusuzların hiçbirinde yok); "
    f"{s(RV['gecmis_randevu_hala_acik'])} iş sevk dilimi geçmiş ama kapanmamış.",
    f"**Mevcut müşteri birikiminin bugün aksiyon alınabilir kısmı**: {s(mv['aksiyon'].get('A_bugun_sahaya_verilebilir', 0))} iş "
    f"sahaya verilebilir, {s(mv['aksiyon'].get('C_ofisten_kapatilabilir', 0))} iş ofisten/telefonla kapatılabilir, "
    f"{s(mv['aksiyon'].get('B_askida_abone_takip', 0) + mv['aksiyon'].get('B_merkezde_operasyon_aksiyonu', 0))} iş operasyonun "
    "tekrar araması/çözmesi gereken (askı + merkeze gönderilen).",
    f"**Ulaşılamama asıl darboğaz**: son açıklaması 'arandı, ulaşılamadı' olan {s(PR['ulasilamama']['son_aciklama_ulasilamadi_tum'])} iş "
    f"(mevcut {s(PR['ulasilamama']['son_aciklama_ulasilamadi_mevcut'])}), 'Aboneye ulaşılamadı' ile merkeze dönen "
    f"{s(PR['ulasilamama']['boss_merkeze_abone_ulasilamadi'])}, abone kaynaklı askı {s(PR['ulasilamama']['abone_kaynakli_aski'])}. "
    f"Açık Bağlantı Problemi işlerinde son notu 'ulaşılamadı' olan pay {p(PR['ulasilamama']['baglanti_acik_ulasilamadi_orani'])} → "
    "işlerin çoğu sahaya çıkmadan bir 'ulaşılamadı' kaydıyla bekliyor.",
    f"**Saha kapasitesi**: 12 kişilik arıza ekibinden günde ~{s(ver['gunluk_aktif_ariza_teknisyeni']['p50'])} kişi aktif, kişi başı "
    f"medyan **{s(ver['ariza_ekibi_gunluk_is_per_teknisyen']['p50'])} iş/gün** (p25–p75: {s(ver['ariza_ekibi_gunluk_is_per_teknisyen']['p25'])}–"
    f"{s(ver['ariza_ekibi_gunluk_is_per_teknisyen']['p75'])}); ardışık iki kapanış arası medyan "
    f"{s(ver['ardisik_kapanis_arasi_dk_5_180']['p50'])} dk (yol+iş vekili). Pazar günleri ekip 4–8 kişiye düşüyor; Pazar gelenlerin 24s uyumu %21–25.",
    f"**Coğrafi kümelenme güçlü**: konumlu açık mevcut-müşteri işlerinde 500 m içinde başka açık iş bulunan pay {p(TK['kume_acik_mevcut']['komsu_500m']['en_az_1_komsu_orani'])} "
    f"(medyan {s(TK['kume_acik_mevcut']['komsu_500m']['medyan_komsu'])} komşu; 2 km'de "
    f"{s(TK['kume_acik_mevcut']['komsu_2000m']['medyan_komsu'])}). Tek günün girişinde bile en yakın komşu medyanı ~150–270 m. "
    f"Lokasyon eşleşmesi: dolu Lokasyon içinde bina_master'a bağlanan {p(TK['lokasyon_eslesme']['boss_lokasyon_dolu_icinde_eslesme'], 1)}; "
    f"ama Lokasyon'u dolu iş oranı yalnız {p(TK['lokasyon_eslesme']['boss_konumlu_oran'])} (Superbox/Kanal Şikayeti/TT Fiber'de hiç yok).",
]
for i, t in enumerate(ozet, 1):
    w(f"{i}. {t}")
w("")

# ------------------------------------------------------------------ 1 KAYNAK
w("## 1. Veri kaynakları ve kapsam")
w("")
ms = R["meta"]["satir"]
tablo(["Kaynak", "Satır", "Ne?"], [
    ["BOSS `TeknikTaskDetayRaporu.xlsx`", s(ms["boss_acik"]), "Bayiye düşmüş AÇIK teknik task'lar (51 sütun)"],
    ["FOX `ReportResultAçık.xls`", s(ms["fox_acik"]), "FOX'ta açık akışlar (kuyrukta/atandı)"],
    ["FOX `ReportResultAskı.xls`", s(ms["fox_aski"]), "FOX'ta ASKIDA akışlar"],
    ["PS26 `data.xlsx`", "6 sayfa", "ORIGN (tur raporu), LOCS, TICKET, GUZERGAH, ALTYAPI, PVT"],
    ["`TAMAMLANDI.xlsx` (masaüstü, ek)", s(ms["tamamlandi_1_15_eylul"]), "1–15 Eylül açılıp 16 Eylül'e kadar KAPANAN mevcut-müşteri task'ları"],
    ["`ANLATILAN.xlsx` (masaüstü, ek)", "15 gün", "Günlük GELEN / YAPILAN / ekip sayısı / arızacı-kurulumcu-ofis kırılımı"],
    ["`veri/master/bina_master.csv`", s(ms["bina_master"]), "OneMap koordinatlı bina envanteri (location_id anahtarı)"],
])
w("> **Not:** `TAMAMLANDI.xlsx` ve `ANLATILAN.xlsx` bu istekte eklenmedi, masaüstünde bulundu. Açık-iş export'ları "
  "kapanmış işleri göstermediği için giriş hızı, telefonla çözülebilirlik, teknisyen verimi ve gerçek 24s uyumu yalnızca "
  "bu iki dosyadan sansürsüz hesaplanabildi. Kullanılmaması istenirse ilgili bölümler 'alt sınır' tahminlerine düşer.")
w("")
w("> **Kritik boşluk:** BOSS açık export'unda `Telefonla Çözülebilir Miydi?`, `Temel Arıza Nedeni`, `Arıza Nedeni` "
  "2.567 satırın **hiçbirinde dolu değil** (kapanışta doldurulan alanlar); `Teknik Ekip Bitirme Tarihi` yalnızca 2 satırda dolu.")
w("")

# ------------------------------------------------------------------ 2 TAKSONOMİ
w("## 2. Kanonik task taksonomisi (FOX ↔ BOSS)")
w("")
w("Eşleme ortak anahtarla (FOX `Akış No` = BOSS `Task No`) birebir doğrulandı. İsmi farklı olan eşleşmeler:")
w("")
tablo(["FOX Task Adı", "BOSS Task Adı", "Kayıt"], [[r["fox"], r["boss"], r["n"]] for r in TX["farkli_isimli_eslesmeler"]])
w("**Kanonik tipler** — sahip = kullanıcı kuralı ('kurulum' geçen → yeni müşteri ekibi, 'Kurulum Taskı Ürememiş' hariç). "
  "*Saha* = fiziki ziyaret ihtiyacı (evet / kısmen / hayır). *Ziyaretsiz %* = 3–15 Eylül kapanışlarında ofisten kapanan "
  "veya nedeni 'müşteri düzeldi dedi / çağrı merkezi / şebeke-genel arıza' olan oran.")
w("")
rows = []
for r in TX["kanonik_tipler"]:
    rows.append([f"`{r['kod']}`", " / ".join(r["boss_adlari"]) or "—", " / ".join(r["fox_adlari"]) or "—",
                 "Mevcut" if r["sahip"] == "mevcut_musteri" else "Kurulum",
                 "✔" if r["btk_kritik"] else "", r["saha_ihtiyaci"], s(r["acik_boss"]), f"{r['acik_fox']}/{r['aski_fox']}",
                 s(r["tamamlanan_1_15_eylul"]), p(r["ziyaretsiz_kapanis_orani"])])
tablo(["Kod", "BOSS adı", "FOX adı", "Sahip", "BTK", "Saha", "Açık BOSS", "FOX açık/askı", "Tamamlanan 1–15 Eyl", "Ziyaretsiz %"], rows)
w("**Belirsiz (kural ile gerçek işin çeliştiği) tipler:**")
w("")
for r in TX["kanonik_tipler"]:
    if r.get("belirsiz"):
        ek = ""
        if r["sahip_fox_adina_gore"] and r["sahip_fox_adina_gore"] != r["sahip"]:
            ek = " **(FOX adına göre sahip değişiyor!)**"
        w(f"- `{r['kod']}` ({s(r['acik_boss'])} açık): {r['belirsiz']}{ek}")
w("")
fb = TX["fox_boss_birlesim"]
w(f"**Yalnız FOX'ta olan {fb['sadece_fox']} kayıt** (askıda: {fb['sadece_fox_dosya'].get('aski', 0)}) BOSS'a hiç düşmüyor → "
  "operasyon bunları FOX'tan izlemek zorunda: " + ", ".join(f"{k} ({v})" for k, v in fb["sadece_fox_task_adi"].items()) + ".")
w("")
w("**Kapanış nedenine göre saha ihtiyacı (TAMAMLANDI, 3–15 Eylül; 1–2 Eylül'de 'Teknisyen' alanı hiç dolmadığı için hariç):**")
w("")
rows = []
for k in ["BAGLANTI", "TV_ARIZA", "DOPING_ARIZA", "ARAMA", "KANAL_SIKAYETI", "MODEM_DEGISIKLIGI", "CIHAZ_IADE", "UCRETLENDIRME", "EVRAK_SOSYAL", "CIHAZ_GERI_ALIM"]:
    if k not in kap:
        continue
    d = kap[k]; ng = d["neden_grup"]; n = d["n"]
    rows.append([f"`{k}`", s(n), p(d["ofis_kapanis_orani"]), p(ng.get("telefon_uzaktan", 0) / n), p(ng.get("sebeke_altyapi", 0) / n),
                 p(ng.get("saha_mudahale", 0) / n), p(ng.get("neden_girilmemis", 0) / n), p(d["ziyaretsiz_kapanis_orani"])])
tablo(["Tip", "Kapanan", "Ofisten kapanan", "Telefon/uzaktan nedeni", "Şebeke/genel arıza", "Saha müdahalesi (kablo/cihaz)", "Neden boş", "Ziyaretsiz toplam"], rows)
w("Telefon/uzaktan = 'Müşteri sorununun düzeldiğini söyledi' + 'Çağrı merkezi tarafından çözülebilirdi' + 'Müşteriyle görüşüldü'. "
  "Şebeke = 'Lokasyonda genel arıza' + 'BÇO/NW müdahale sonrası düzeldi' + 'TT kaynaklı'. Saha = 'Kablo/konnektör/uç değişimi' + "
  "'Cihaz değişimi'. Bağlantı'da teknisyen kapanışlarının da %26'sı 'müşteri düzeldi dedi' → teknisyen gitmeden bir telefonla "
  "elenebilecek iş payı.")
w("")
w(f"**Tekrarlayan arıza:** {s(tek['musteri'])} müşteride {s(tek['task'])} BTK arıza task'ı; {s(tek['birden_fazla_task_musteri'])} müşteride "
  f"birden fazla → {s(tek['tekrar_task'])} tekrar task ({p(tek['tekrar_task_orani'])}). Şu an {s(TX['ayni_musteride_birden_fazla_acik_task'])} "
  "müşterinin aynı anda birden fazla açık task'ı var (tek ziyarette birleştirilebilir).")
w("")

# ------------------------------------------------------------------ 3 SLA
w("## 3. SLA modeli")
w("")
w("### 3.1 Alanlar gerçekte neyi ölçüyor")
w("")
for k, v in SL["tanimlar"].items():
    w(f"- **{k.replace('_', ' ')}** — {v}")
w(f"- **Teknik Ekip Konum Paylaşma / İşe Başlama** — ikisi de dolu {SL['teknik_ekip_sl_dk']['ikisi_de_dolu']} kaydın "
  f"{p(SL['teknik_ekip_sl_dk']['ayni_dakikada_orani'])} kadarında aynı dakika içinde basılmış → yol süresi ölçülemiyor.")
w("")
w("### 3.2 Hedef süreler (saat) — BOSS (bayi SL'i) vs FOX (Turkcell akış SL'i)")
w("")
bh = SL["boss_hedef_saat_tip"]; fh = SL["fox_hedef_saat_tip"]
pairs = [("Bağlantı Problemi", "Bağlantı Problemleri"), ("TV+ Arıza", "IP TV Arıza"), ("Arama Problemi", "Arama Problemi"),
         ("Kanal Şikayeti", "Kanal Şikayeti"), ("Doping Arıza Bildirimi", "Arıza Bildirim"),
         ("Cihaz İade Bekleniyor", "Cihaz İade Bekleniyor"), ("Cihaz Geri Alım", "Cihaz Geri Alım"),
         ("Modem Değişikliği", "Modem Değişikliği"), ("STB Cihaz Değişikliği", "STB Cihaz Değişikliği"),
         ("Teknik Servis Ücretlendirme", "Ücretlendirilecek Servisler"), ("2.Donanım", "İkinci Donanım Kurulum"),
         ("Fiber Kurulum", "Quiknet Kurulum Talebi"), ("TV+ Kurulum", "IP TV Kurulum"), ("Yan Oda Kurulum", "TV Yan Oda Kurulum"),
         ("Superbox Kurulum", "SuperBox Kurulum"), ("Kurulum ve Cihaz Gönderim", "Kurulum ve cihaz gönderim"),
         ("TT Fiber Kurulum", "TT Fiber Kurulum Talebi"), ("—", "BTK Şikayet"), ("—", "BTK / Mahkeme Şikayet")]
tablo(["BOSS tipi", "BOSS hedef", "FOX tipi", "FOX Hedef SL"],
      [[a, s(bh.get(a)) if bh.get(a) else "SL yok", b, (s(fh.get(b)) if fh.get(b) else "0 (yok)")] for a, b in pairs])
w("Bağlantı için Turkcell (FOX) hedefi **12 saat**, bayi (BOSS) hedefi **24 saat**; TV+ Arıza'da 6 / 16 saat. Kanal Şikayeti, "
  "Cihaz İade, Modem Değişikliği, Doping, Evrak ve TT Fiber için BOSS'ta SL tanımı yok (SL sütunu boş) — bu işler BOSS SL "
  "raporunda görünmeden yaşlanıyor.")
w("")
w("### 3.3 Açık işlerde ihlal ve yaş (kanonik tip)")
w("")
rows = []
order = sorted(SL["ihlal_kanonik"].items(), key=lambda kv: (kv[1]["sahip"] != "mevcut_musteri", -kv[1]["n"]))
for k, v in order:
    yd = v["yas_dagilimi"]
    rows.append([f"`{k}`", "M" if v["sahip"] == "mevcut_musteri" else "K", s(v["n"]), s(v["boss_hedef_saat"]) if v["boss_hedef_saat"] else "–",
                 s(v["fox_hedef_saat"]) if v["fox_hedef_saat"] else "–", s(v["boss_sl_gecti"]),
                 f"{s(v['yas_24s_ustu'])} ({p(v['yas_24s_ustu_oran'])})", s(v["yas_medyan_saat"]),
                 yd["<24s"], yd["24-48s"], yd["48-72s"], yd["3-7g"], yd["7-30g"], yd[">30g"]])
tablo(["Tip", "M/K", "Açık", "BOSS hedef", "FOX hedef", "BOSS SL Geçti", ">24s (kullanıcı kuralı)", "Medyan yaş (s)",
       "<24s", "24–48s", "48–72s", "3–7g", "7–30g", ">30g"], rows)
ym = SL["yas_mevcut_musteri"]; yy = SL["yas_yeni_musteri_kurulum"]
w(f"**Anlık tablo:** 24 saati geçmiş açık iş oranı mevcut müşteride {p(ym['yas_24s_ustu_oran'])}, kurulumda {p(yy['yas_24s_ustu_oran'])}."
  f" Mevcut müşteride medyan yaş {s(ym['medyan_saat'])} saat, kurulumda {s(yy['medyan_saat'])} saat. "
  f"BOSS'un kendi SL'ine göre: mevcut {s(ym['boss_sl_gecti'])} geçti / {s(ym['boss_sl_gecmedi'])} geçmedi / {s(ym['boss_sl_yok'])} SL tanımsız; "
  f"kurulum {s(yy['boss_sl_gecti'])} / {s(yy['boss_sl_gecmedi'])} / {s(yy['boss_sl_yok'])}.")
w("")
w("### 3.4 Gerçek 24 saat uyumu (kohort — en doğru ölçü)")
w("")
w(koh["tanim"])
w("")
tablo(["Süre", "≤6s", "≤12s", "≤24s", "≤48s", "≤72s"], [["Tamamlanma oranı"] + [p(koh["orani"][k], 1) for k in ["6s", "12s", "24s", "48s", "72s"]]])
rows = []
for k, v in sorted(koh["tip_bazinda"].items(), key=lambda kv: -(kv[1]["tamamlanan_kohort"] + kv[1]["tahmini_acik_kalan"])):
    if v["tamamlanan_kohort"] < 5:
        continue
    rows.append([f"`{k}`", s(v["tamamlanan_kohort"]), s(v["tahmini_acik_kalan"]), p(v["uyum_24s"]),
                 (f"{p(v['uyum_fox_hedef'])} (≤{v['fox_hedef_saat']}s)" if v.get("uyum_fox_hedef") is not None else "–")])
tablo(["Tip", "Kohortta kapanan", "Tahmini açık kalan (16 Eyl)", "24s uyumu", "FOX hedefi uyumu"], rows)
w("Tip payları tahmini: 16 Eylül'de açık kalan 1.180 işin tipi bilinmediğinden, bugün açık ve ≤15 gün yaşındaki mevcut-müşteri "
  "işlerinin tip dağılımıyla paylaştırıldı (durağanlık varsayımı).")
w("")
w("**Açılış gününe göre 24s uyumu (gün kötüleşiyor):**")
w("")
g24 = SL["gunluk_24s_uyum_acilis_gunune_gore"]
tablo(["Tarih", "Gün", "Gelen", "24s içinde kapanan", "Uyum"], [[k[5:], v["gun"], v["gelen"], v["ok24"], p(v["oran"])] for k, v in g24.items()])
w("Pazar açılan işlerin uyumu %21–25 (ekip 4 kişi, 'nöbet'); 12 Eylül Cumartesi 462 iş gelmiş (olağandışı pik), sonrasında uyum "
  "%21–24 bandına oturmuş. Hafta içi ilk günler %50–65 iken birikim büyüdükçe düşüş var.")
w("")
ts = SL["tamamlanma_suresi_saat"]
w(f"**Kapananların açılış→kapanış süresi (saat, sağdan sansürlü):** tümü medyan {s(ts['tum']['p50'], 1)} (p75 {s(ts['tum']['p75'], 1)}, "
  f"p90 {s(ts['tum']['p90'], 1)}); saha teknisyeni kapanışı medyan {s(ts['saha_teknisyeni']['p50'], 1)}, ofis kapanışı medyan "
  f"{s(ts['ofis_operasyon']['p50'], 1)} ama p75 {s(ts['ofis_operasyon']['p75'])} (Kanal Şikayeti'nin 7 günlük askısı).")
w("")

# ------------------------------------------------------------------ 4 BİRİKİM
w("## 4. Birikim ayrıştırması")
w("")
w("### 4.1 Sahip × durum")
w("")
dur = ["Açık", "Askıya alındı", "Merkeze gönderildi", "Konum Paylaşıldı", "Başlandı"]
tablo(["Sahip", "Toplam"] + dur + ["Ekip atanmış", "Randevulu (=sevk edilmiş)"],
      [[n, s(d["n"])] + [s(d["durum"].get(x, 0)) for x in dur] + [s(d["atanmis"].get("ekip_atanmis", 0)),
                                                                   s(d["n"] - d["randevu_konum"].get("randevusuz", 0))]
       for n, d in [("Mevcut müşteri", mv), ("Yeni müşteri kurulum", yn)]])
w("### 4.2 Bugün ne yapılabilir? (aksiyon kovaları)")
w("")
for k, v in BR["aksiyon_tanimi"].items():
    w(f"- **{k}** — {v}")
w("")
ak = ["A_bugun_sahaya_verilebilir", "C_ofisten_kapatilabilir", "B_askida_abone_takip", "B_merkezde_operasyon_aksiyonu", "D_dis_bagimli_TT", "E_ileri_tarihli_randevu"]
tablo(["Sahip"] + ak, [[n] + [s(d["aksiyon"].get(x, 0)) for x in ak] for n, d in [("Mevcut", mv), ("Kurulum", yn)]])
rows = []
for k, v in sorted(BR["tip_x_aksiyon"].items(), key=lambda kv: -sum(kv[1].values())):
    rows.append([f"`{k}`"] + [s(v.get(x, 0)) for x in ak])
tablo(["Tip"] + ak, rows)
w("### 4.3 Askı, merkeze gönderme ve son açıklama")
w("")
tablo(["", "Mevcut", "Kurulum"], [
    ["Askı: Abone kaynaklı", s(mv["aski_nedeni"].get("Abone kaynaklı", 0)), s(yn["aski_nedeni"].get("Abone kaynaklı", 0))],
    ["Askı: TT kaynaklı", s(mv["aski_nedeni"].get("TT kaynaklı", 0)), s(yn["aski_nedeni"].get("TT kaynaklı", 0))],
] + [[f"Merkeze: {k}", s(mv["merkeze_gonder"].get(k, 0)), s(yn["merkeze_gonder"].get(k, 0))]
     for k in ["ABONEYE ULAŞILAMADI - MÜSAİT DEĞİL", "GÜZERGAH YOK", "SİNYAL YOK", "BOŞ PORT YOK", "TASK GEÇ DÜŞTÜ", "ABONE CİHAZI KAYIP-BULAMADI"]]
  + [[f"Son açıklama: {k}", s(mv["aciklama_grup"].get(k, 0)), s(yn["aciklama_grup"].get(k, 0))]
     for k in ["musteriye_ulasilamadi", "ekibe_atandi_notu", "tt_etiketleme_bekliyor", "musteri_ileri_tarih_istedi", "port_sinyal_kapasite",
               "guzergah", "stok_cihaz_yok", "musteri_cihazi_teslim_edecek", "iptal_istegi", "diger", "(boş)"]])
w("Son açıklamalar anahtar kelimeyle gruplandı (metin kopyalanmadı). 'BOSS üzerinden arama sağlandı, ulaşılamadı' kalıbı tek "
  "başına ~550 kayıtta — kayıtlı arama denemelerinin büyük kısmı sonuçsuz (aramayı kimin/neyin yaptığı açık soru).")
w("'Ulaşılamadı' notlu mevcut-müşteri işleri tipe göre: " + dd(PR['ulasilamama']['ulasilamadi_notlu_tip_mevcut']) + ".")
w("")
w("Askıdaki işlerin yaşı — mevcut: " + dd(BR['askidaki_yas'].get('mevcut_musteri')) + "; kurulum: " + dd(BR['askidaki_yas'].get('yeni_musteri_kurulum')) + ".")
w("")
w("### 4.4 İlçe")
w("")
ic = BR["ilce_x_sahip"]
top = sorted(ic.items(), key=lambda kv: -sum(kv[1].values()))[:14]
tablo(["İlçe", "Mevcut", "Kurulum", "Toplam"], [[k, s(v.get("mevcut_musteri", 0)), s(v.get("yeni_musteri_kurulum", 0)), s(sum(v.values()))] for k, v in top])

# ------------------------------------------------------------------ 5 GİRİŞ
w("## 5. Giriş (inflow) tahmini")
w("")
w("> " + GI["sansur_notu"])
w("")
w("### 5.1 Mevcut müşteri — sansürsüz (ANLATILAN 'GELEN', 1–15 Eylül)")
w("")
gg = GI["mevcut_gelen_gunluk_1_15_eylul"]
tablo(["Tarih"] + [k[5:] for k in gg], [["Gelen"] + [str(v) for v in gg.values()]])
wd = GI["mevcut_gelen_haftanin_gunu_ort"]
tablo(["Gün"] + list(wd), [["Ortalama gelen"] + [s(v) for v in wd.values()]])
w(f"Takvim günü ortalaması **{s(gi['takvim_gunu_ort'])}**, hafta içi {s(gi['hafta_ici_ort'])} (std {s(gi['hafta_ici_std'])}), "
  f"Cumartesi {s(gi['cumartesi_ort'])}, Pazar {s(gi['pazar_ort'])}. Ayın ilk günleri (1–2 Eylül: 433, 518) ve 12 Eylül (462) pik.")
w("")
w("**Tip bazında günlük giriş (tahmin):**")
w("")
tb = GI["mevcut_tip_bazinda_gunluk_tahmin"]
tablo(["Tip", "Kapanan (15 gün)", "16 Eyl'de açık kalan (tahmin)", "Günlük ort.", "Pay"],
      [[f"`{k}`", s(v["tamamlanan"]), s(v["tahmini_acik_kalan"]), s(v["gunluk_ort"], 1), p(GI["mevcut_tip_payi"][k], 1)]
       for k, v in sorted(tb.items(), key=lambda kv: -kv[1]["gunluk_ort"]) if v["gunluk_ort"] >= 0.5])
w(f"Bu kapsamda **2.Donanım yok** (TAMAMLANDI'da hiç yok); açık dosyadan alt sınırı ~{s(PR['ikinci_donanim_giris_alt_sinir_gunluk'], 1)}/gün.")
w("")
vs = GI["mevcut_varis_saat_profili"]
w("**Saatlik varış profili (mevcut, pay %):** " + ", ".join(f"{h}:00 {s(100*v, 1)}" for h, v in vs.items() if v >= 0.01) +
  ". 09:00 piki (%13) gece biriken işlerin sabah düşmesi; 09–19 arası saatte %6–8 düzgün; akşam 20:00 sonrası ~%13.")
w("")
w("### 5.2 Kurulum — yalnız alt sınır (sansürlü)")
w("")
al = GI["alt_sinir_hala_acik"]
w(f"Son 7 günde açılıp hâlâ açık: kurulum **{s(al['yeni_musteri_kurulum']['son_7g_gunluk_ort'])}/gün**, mevcut "
  f"{s(al['mevcut_musteri']['son_7g_gunluk_ort'])}/gün (gerçek mevcut girişin ~%30'u → kurulumda da gerçek giriş belirgin biçimde daha yüksek). "
  f"Son 24 saatte açılıp açık: kurulum {al['yeni_musteri_kurulum']['son_24s']}, mevcut {al['mevcut_musteri']['son_24s']}.")
w("")
tablo(["Kurulum tipi", "Son 7 gün, hâlâ açık / gün"], [[f"`{k}`", s(v, 1)] for k, v in al["yeni_musteri_kurulum"]["tip_son_7g_gunluk"].items()])
w("### 5.3 Kapasite açığı")
w("")
ka = PR["mevcut_kapasite_acigi"]
w(f"Hafta içi gelen ~{s(ka['gelen_hafta_ici'])}/gün; 7–15 Eylül (12–13 Eylül hariç) kapanan ~{s(ka['yapilan_7_15_eylul_ort'])}/gün. "
  f"ANLATILAN 'DURUM' sütununun 15 gün toplamı +1.180 (birikim artışı). {ka['not_']}")
w("")

kd = PR["kapasite_kaba_denge"]
w(f"**Kaba denge (simülasyon öncesi sağlama):** mevcut giriş {s(kd['mevcut_giris_takvim'])}/gün × (1 − ziyaretsiz pay {p(kd['ziyaretsiz_pay'])}) ≈ "
  f"**{s(kd['saha_gereken_gunluk'])} saha ziyareti/gün** gerekir; arıza ekibi kapasitesi ≈ ort. aktif teknisyen × ort. iş/gün ≈ "
  f"**{s(kd['ariza_teknisyen_kapasitesi_gunluk'])}/gün** (7 gün ortalaması). Ancak teknisyen kapanışlarının "
  f"{p(kd['saha_kapanisinda_duzelmis_bulunan_pay_btk'])} kadarı 'düzelmiş/şebeke' bulunan iş; telefon filtresi bunları ayıklarsa "
  "kalan işler gerçek onarım olur ve kişi başı iş/gün düşer (tahmini 12–14). Simülasyon bu iki etkiyi birlikte modellemeli.")
w("")

# ------------------------------------------------------------------ 6 TEKNİSYEN
w("## 6. Teknisyen yükü ve coğrafya")
w("")
eo = TK["boss_acik_ekip_ozet"]
w(f"**BOSS açık işlerde:** {eo['ekip_sayisi']} farklı ekip adı, atanmış {s(eo['atanmis_is'])} iş, atanmamış {s(eo['atanmamis_is'])}. "
  f"Ekip başı açık iş medyan {s(eo['is_basina_q']['p50'])} (p90 {s(eo['is_basina_q']['p90'])}). BOSS 'Teknisyen' alanı saha teknisyeni değil "
  f"({TK['boss_teknisyen_alani']['dolu']} kayıtta dolu, pozisyonları: " + dd(TK['boss_teknisyen_alani']['pozisyon']) + ").")
w("")
rows = [[k, s(v["n"]), s(v["mevcut"]), s(v["btk"]), s(v["ilce_sayisi"]), s(v["yas_medyan_saat"])] for k, v in list(TK["boss_acik_ekip_yuku"].items())[:20]]
tablo(["Ekip (ilk 20)", "Açık iş", "Mevcut", "BTK", "İlçe sayısı", "Medyan yaş (s)"], rows)
w(f"Arıza ekibi ile kurulum ekipleri net ayrık: açık işi olan {eo['ekip_sayisi']} ekipten {sum(1 for v in TK['boss_acik_ekip_yuku'].values() if v['mevcut'] >= 0.9 * v['n'])} "
  f"ekipte işlerin ≥%90'ı mevcut müşteri, {sum(1 for v in TK['boss_acik_ekip_yuku'].values() if v['mevcut'] <= 0.1 * v['n'])} ekipte ≥%90'ı kurulum.")
w("")
w("### 6.1 Verim (TAMAMLANDI, 3–15 Eylül)")
w("")
eb = TK["ekip_listesi_birlesik"]
tablo(["Ölçü", "Değer"], [
    ["Arıza ekibi (ANLATILAN pivot)", f"{ver['ariza_ekibi_kisi']} kişi"],
    ["Günlük aktif arıza teknisyeni (medyan / ort.)", f"{s(ver['gunluk_aktif_ariza_teknisyeni']['p50'])} / {s(ver['gunluk_aktif_ariza_teknisyeni']['ort'], 1)}"],
    ["ANLATILAN 'EKİP SAYISI' (medyan, min–maks)", f"{s(eb['ekip_sayisi_gunluk_anlatilan']['p50'])} (Pazar 4–8)"],
    ["Günlük aktif saha adı (kurulumcu dahil, medyan)", s(ver["gunluk_aktif_saha_teknisyeni"]["p50"])],
    ["Arıza teknisyeni iş/gün (p25 / medyan / p75 / p90)", " / ".join(s(ver["ariza_ekibi_gunluk_is_per_teknisyen"][k]) for k in ["p25", "p50", "p75", "p90"])],
    ["Ardışık kapanış arası dk (5–180 dk; p25/medyan/p75)", " / ".join(s(ver["ardisik_kapanis_arasi_dk_5_180"][k]) for k in ["p25", "p50", "p75"])],
    ["<5 dk arayla kapanış (toplu kapatma işareti)", p(ver["toplu_kapanis_orani_5dk_alti"])],
    ["Gün içi ilk / son kapanış saati (medyan)", f"{s(ver['gun_ici_ilk_kapanis_saati']['p50'], 1)} / {s(ver['gun_ici_son_kapanis_saati']['p50'], 1)}"],
    ["İlk→son kapanış aralığı (saat, medyan)", s(ver["ilk_son_kapanis_arasi_saat"]["p50"], 1)],
    ["Ofisten kapanış oranı (12 Eylül toplu kapatma hariç / dahil)", f"{p(TK['ofis_kapanis']['oran_12_eylul_haric'], 1)} / {p(TK['ofis_kapanis']['oran_3_15_eylul'], 1)}"],
    ["12 Eylül ofisten toplu kapanış", s(TK["ofis_kapanis"]["gunluk"].get("2026-09-12"))],
])
w("Yerinde iş süresi (İşe Başlama→Bitirme) **türetilemedi**: kapanmış işlerde bu damgalar yok, açık export'ta bitirme 2 kayıtta. "
  "Döngü süresi vekili (yol + iş) medyan ~31 dk; ancak kapanışların üçte biri <5 dk arayla (sahada değil sonradan toplu kapatma) — "
  "gerçek döngü muhtemelen 35–45 dk. Günlük 17 iş × ~30 dk ≈ 8,5 saat, 'ilk→son kapanış' ~8,1 saat ile tutarlı.")
w("")
w("### 6.2 Lokasyon eşleşmesi (BOSS `Lokasyon` → `bina_master.location_id`)")
w("")
le = TK["lokasyon_eslesme"]
tablo(["Durum", "BOSS açık", "TAMAMLANDI"], [[k, s(le["boss"].get(k, 0)), s(le["tamamlandi"].get(k, 0))]
                                            for k in ["dogrudan", "sifir_kirpma", "master_da_yok", "lokasyon_yok"]])
w(f"Konumlu oran: tüm açık {p(le['boss_konumlu_oran'])} (mevcut {p(le['boss_mevcut_konumlu_oran'])}, kurulum {p(le['boss_yeni_konumlu_oran'])}); "
  f"dolu Lokasyon içinde eşleşme {p(le['boss_lokasyon_dolu_icinde_eslesme'], 1)}. 'sifir_kirpma' = BOSS'ta '00xxxxxx' biçimli, baştaki sıfırlar "
  "atılınca eşleşen kimlikler. " + le["not_"])
w("")
w("### 6.3 Kümelenme potansiyeli")
w("")
rows = []
for n, k in [("Tüm açık", "kume_acik_tum"), ("Mevcut açık", "kume_acik_mevcut"), ("Mevcut, bugün sahaya verilebilir", "kume_acik_mevcut_saha"), ("Kurulum açık", "kume_acik_yeni")]:
    c = TK[k]
    rows.append([n, s(c["n"]), p(c["komsu_500m"]["en_az_1_komsu_orani"]), s(c["komsu_500m"]["medyan_komsu"]),
                 p(c["komsu_500m"]["en_az_5_komsu_orani"]), s(c["komsu_2000m"]["medyan_komsu"]), s(c["en_yakin_komsu_m"]["p50"]),
                 p(c["ayni_bina_orani"]), f"{c['kume_500m']['kume_sayisi']} / {c['kume_500m']['en_buyuk_kume']}",
                 f"{c['kume_2000m']['kume_sayisi']} / {c['kume_2000m']['en_buyuk_kume']}"])
tablo(["Küme", "Konumlu iş", "500 m'de ≥1 komşu", "500 m komşu (medyan)", "500 m'de ≥5 komşu", "2 km komşu (medyan)",
       "En yakın komşu m (medyan)", "Aynı binada başka iş", "500 m kümeleri (sayı / en büyük)", "2 km kümeleri"], rows)
gk = TK["gunluk_giris_kumelenme_tamamlanan"]
w("**Tek bir günün girişi** (1–12 Eylül, konumlu, günde ~150–280 iş): en yakın komşu medyanı "
  f"{s(min(x['nn_medyan_m'] for x in gk[:12]))}–{s(max(x['nn_medyan_m'] for x in gk[:12]))} m; işlerin "
  f"%{s(100*min(x['komsu500_orani'] for x in gk[:12]))}–{s(100*max(x['komsu500_orani'] for x in gk[:12]))} kadarının 500 m içinde aynı gün gelen başka işi var.")
ty = TK["teknisyen_gunluk_yayilim"]
w(f"**Bugünkü rota yayılımı:** bir teknisyenin bir gün kapattığı işlerin ağırlık merkezine medyan uzaklığı {s(ty['medyan_yaricap_m']['p50'])} m "
  f"(p75 {s(ty['medyan_yaricap_m']['p75'])}, p90 {s(ty['medyan_yaricap_m']['p90'])} m), gün başına medyan {s(ty['ilce_sayisi']['p50'])} ilçe. "
  f"Mevcut açık işlerin ofise uzaklığı medyan {s(TK['ofis_uzaklik_km_mevcut_acik']['p50'], 1)} km (p90 {s(TK['ofis_uzaklik_km_mevcut_acik']['p90'], 1)}).")
w("")
w("Mevcut açık işin en yoğun mahalleleri: " + ", ".join(f"{x['mahalle']} ({x['n']})" for x in TK["mevcut_acik_mahalle_top25"][:10]) + ".")
w("")

# ------------------------------------------------------------------ 7 RANDEVU
w("## 7. Randevu")
w("")
w("> " + RV["yorum"])
w("")
ar = RV["acilistan_randevuya_saat_sahip"]
tablo(["Ölçü", "Değer"], [
    ["Randevulu / Randevusuz", f"{s(RV['randevu_durumu']['Randevulu'])} / {s(RV['randevu_durumu']['Randevusuz'])}"],
    ["Randevu dilimi uzunluğu", "2 saat (669/674)"],
    ["En sık dilim başlangıcı", "11:00 (221); 13–19 arası her saat 37–61; 02–03 arası 32 (gece girilmiş/yer tutucu)"],
    ["Açılış → randevu (mevcut; medyan / p75 / p90 saat)", f"{s(ar['mevcut_musteri']['p50'], 1)} / {s(ar['mevcut_musteri']['p75'], 1)} / {s(ar['mevcut_musteri']['p90'], 1)}"],
    ["Açılış → randevu (kurulum; medyan / p75 / p90 saat)", f"{s(ar['yeni_musteri_kurulum']['p50'], 1)} / {s(ar['yeni_musteri_kurulum']['p75'], 1)} / {s(ar['yeni_musteri_kurulum']['p90'], 1)}"],
    ["Dilimi geçmiş ama hâlâ açık", f"{s(RV['gecmis_randevu_hala_acik'])} (durum: " + dd(RV['gecmis_randevu_durum']) + ")"],
    ["Geçmiş dilimin üzerinden geçen gün (medyan / p75 / p90)", f"{s(RV['gecmis_randevu_gecikme_gun']['p50'], 1)} / {s(RV['gecmis_randevu_gecikme_gun']['p75'], 1)} / {s(RV['gecmis_randevu_gecikme_gun']['p90'], 1)}"],
    ["İleri tarihli (yarın+)", s(sum(v for k, v in RV["ileri_tarih_gun"].items() if k != "0"))],
])
w("Geçmiş dilimi olup açık kalan işler tipe göre: " + ", ".join(f"{k} {v}" for k, v in list(RV["gecmis_randevu_tip"].items())[:10]) + ".")
w("")

# ------------------------------------------------------------------ 8 PS26
w("## 8. PS26 `data.xlsx` manuel sayfalar — hangi süreç, ne hacim")
w("")
tk = PS["TICKET"]; gz = PS["GUZERGAH"]; alt = PS["ALTYAPI"]; orj = PS["ORIGN"]
tablo(["Sayfa", "Süreç", "Hacim / durum"], [
    ["ORIGN", orj["surec"], f"{s(orj['satir'])} bina; location_id'lerin tamamı bina_master ile ortak ({s(orj['location_id_master_ile_ortak'])})"],
    ["LOCS", PS["LOCS"]["surec"], f"{s(PS['LOCS']['satir_dolu_bina'])} bina satırı; müşteri no yalnız {PS['LOCS']['musteri_no_dolu']} satırda"],
    ["TICKET", tk["surec"], f"{tk['n']} kayıt: SİNYAL {tk['konu']['SİNYAL']} / EK SP {tk['konu']['EK SP']}; durum " + dd(tk['durum'])],
    ["GUZERGAH", gz["surec"], f"{s(gz['sayfa_satir'])} satır, dolu olan {gz['gercek_kayit']}; kanal " + dd(gz['kanal']) + "; aylık " + dd(gz['aylik'])],
    ["ALTYAPI", alt["surec"], f"{alt['n']} kayıt; kanal " + dd(alt['kanal']) + "; aylık " + dd(alt['aylik']) + f"; {alt['satici_sayisi']} satıcı"],
    ["PVT", PS["PVT"]["surec"], f"{PS['PVT']['n']} satır"],
])
w(f"**TICKET ayrıntı:** SİNYAL'de çözülme {p(tk['konu_x_durum']['SİNYAL'].get('ÇÖZÜLDÜ', 0) / tk['konu']['SİNYAL'])}; EK SP'de yalnız "
  f"{p(tk['konu_x_durum']['EK SP'].get('ÇÖZÜLDÜ', 0) / tk['konu']['EK SP'])} çözülmüş, {p(tk['konu_x_durum']['EK SP'].get('HATA', 0) / tk['konu']['EK SP'])} HATA "
  f"(ticket no'su boş: {dd(tk['ticket_no_bos_durum'])}). Son 30 günde {tk['son_30_gun']} ticket (~{s(tk['son_30_gun_gunluk'], 1)}/gün). AÇIK ticket "
  f"yaşı medyan {s(tk['acik_yas_gun']['p50'])} gün (p90 {s(tk['acik_yas_gun']['p90'])}); HATA yaşı medyan {s(tk['hata_yas_gun']['p50'])} gün. "
  f"Detay notlarında {tk['detay_tekrar_acildi']} 'tekrar açıldı', {tk['detay_ek_sp_musteri_eklenmeli']} 'EK SP için müşteri eklenmeli'. "
  f"Kanal: {dd(tk['kanal'])}. Lokasyon→bina_master eşleşmesi {p(tk['lokasyon_master_eslesme'], 1)}.")
w("")
w(f"**BOSS ile çapraz kontrol:** BOSS'ta 'SİNYAL YOK / BOŞ PORT YOK' ile merkeze dönmüş {tk['boss_sinyal_port_merkeze_lokasyon']} lokasyonun "
  f"{tk['bunlardan_ticket_sayfasinda']} adedi TICKET sayfasında var (%{s(100*tk['bunlardan_ticket_sayfasinda']/max(tk['boss_sinyal_port_merkeze_lokasyon'],1))}); "
  f"'GÜZERGAH YOK' ile dönen {gz['boss_guzergah_yok_lokasyon']} lokasyondan yalnız {gz['bunlardan_guzergah_sayfasinda']} adedi GUZERGAH sayfasında → "
  "manuel takip BOSS'tan kopuk; güzergah listesi güncel değil.")
w("")
w(f"**GUZERGAH:** kayıtların hepsi 'YOK' durumunda, kapanış alanı yok; yaş medyan {s(gz['yas_gun']['p50'])} gün; {gz['site_turda_yok']} kayıt "
  f"'TURDA YOK' (tur raporunda olmayan bina). **ALTYAPI:** yaş medyan {s(alt['yas_gun']['p50'])} gün; en çok Demirtaş (15) ve Görükle (13).")
w("")

# ------------------------------------------------------------------ 9 PARAMETRE
w("## 9. Simülasyon parametreleri (özet — tamamı JSON `parametreler`)")
w("")
tablo(["Parametre", "Değer", "Dayanak"], [
    ["Mevcut müşteri giriş / gün", f"takvim {s(gi['takvim_gunu_ort'])}; hafta içi {s(gi['hafta_ici_ort'])}; Cmt {s(gi['cumartesi_ort'])}; Paz {s(gi['pazar_ort'])}", "ANLATILAN GELEN 1–15 Eyl"],
    ["Tip payı (mevcut)", ", ".join(f"{k} {p(v)}" for k, v in sorted(GI['mevcut_tip_payi'].items(), key=lambda kv: -kv[1]) if v >= 0.02), "TAMAMLANDI + açık paylaştırma"],
    ["Kurulum giriş / gün", f"≥{s(al['yeni_musteri_kurulum']['son_7g_gunluk_ort'])} (alt sınır)", "son 7 gün hâlâ açık"],
    ["Ziyaretsiz kapanış (mevcut / BTK arıza)", f"{p(PR['ziyaretsiz_kapanis_orani_mevcut'])} / {p(PR['ziyaretsiz_kapanis_orani_btk_ariza'])}", "Arıza Nedeni + kapatan"],
    ["Telefon/uzaktan nedeni (BTK arıza)", p(PR["telefon_uzaktan_neden_orani_btk_ariza"]), "'müşteri düzeldi dedi' vb."],
    ["Kanal Şikayeti ziyaretsiz", p(kap["KANAL_SIKAYETI"]["ziyaretsiz_kapanis_orani"]), "%98 ofis kapanışı"],
    ["Tekrar arıza oranı (15 gün)", p(PR["tekrar_ariza_orani"]), "aynı müşteri >1 BTK task"],
    ["Arıza teknisyeni iş/gün", f"medyan {s(ver['ariza_ekibi_gunluk_is_per_teknisyen']['p50'])} (ort {s(ver['ariza_ekibi_gunluk_is_per_teknisyen']['ort'], 1)})", "TAMAMLANDI 3–15 Eyl"],
    ["Aktif arıza teknisyeni / gün", f"medyan {s(ver['gunluk_aktif_ariza_teknisyeni']['p50'])} (12 kişilik havuz; Pazar 4–8)", "TAMAMLANDI + ANLATILAN"],
    ["Döngü süresi (yol+iş) vekili", f"medyan {s(ver['ardisik_kapanis_arasi_dk_5_180']['p50'])} dk (p75 {s(ver['ardisik_kapanis_arasi_dk_5_180']['p75'])})", "ardışık kapanış farkı"],
    ["Yerinde iş süresi", "türetilemedi", "İşe Başlama→Bitirme yok"],
    ["Mesai penceresi (kapanış)", f"~{s(ver['gun_ici_ilk_kapanis_saati']['p50'], 1)} – {s(ver['gun_ici_son_kapanis_saati']['p50'], 1)}", "ilk/son kapanış medyanı"],
    ["Varış profili", "09:00 %13; 10–19 saatte %6–8; 20:00+ ~%13", "saatlik"],
    ["SL hedefi (saat)", "Bağlantı 24 (FOX 12) · TV+ Arıza 16 (FOX 6) · Arama 24 (FOX 12) · Kanal —(FOX 24) · Kurulum 36–48 · 2.Donanım 96", "BOSS SL Süresi ters mühendislik"],
    ["Gerçek 24s uyumu (mevcut)", f"{p(koh['orani']['24s'])} (Bağlantı {p(koh['tip_bazinda']['BAGLANTI']['uyum_24s'])}, TV {p(koh['tip_bazinda']['TV_ARIZA']['uyum_24s'])}, Kanal {p(koh['tip_bazinda']['KANAL_SIKAYETI']['uyum_24s'])})", "kohort"],
    ["Birikim (mevcut / kurulum)", f"{s(mv['n'])} / {s(yn['n'])}", "BOSS açık"],
    ["Konumlu iş oranı", f"mevcut {p(le['boss_mevcut_konumlu_oran'])}, kurulum {p(le['boss_yeni_konumlu_oran'])}, kapanan mevcut {p(le['tamamlandi_konumlu_oran'])}", "Lokasyon→bina_master"],
    ["Ulaşılamama", f"açıklamalı işlerde 'ulaşılamadı' payı {p(PR['ulasilamama']['son_aciklama_ulasilamadi_orani_aciklamali'])}", "Son Açıklama"],
])

# ------------------------------------------------------------------ 10 VERİ KALİTESİ
w("## 10. Veri kalitesi sorunları (sistemi kurarken düzeltilmesi gerekenler)")
w("")
for t_ in [
    "Kapanışta **Arıza Nedeni** BTK arızalarında dolu ama Modem Değişikliği, Cihaz İade, Ücretlendirme, Evrak'ta hiç girilmiyor; açık export'ta 'Telefonla Çözülebilir Miydi?' alanı boş.",
    "**Konum Paylaş ve İşe Başla aynı anda basılıyor** (%81) → yol süresi ve varış saati ölçülemiyor; Bitirme damgası kapanmış işlere taşınmıyor.",
    "**1–2 Eylül'de 'Teknisyen' alanı hiç dolmamış**; 12 Eylül'de 430 iş ofisten toplu kapatılmış → günlük verim bu günlerde yanıltıcı.",
    "Kapanışların **üçte biri <5 dk arayla** (sonradan toplu kapatma) → gerçek zamanlı durum görünmüyor.",
    "**Lokasyon** Superbox, Kanal Şikayeti, TT Fiber, Kurulum ve Cihaz Gönderim ve Cihaz İade'nin çoğunda boş → bu işler haritalanamıyor (yalnız ilçe).",
    "BOSS 'Askıya Alınma Nedeni' değerinde sondaki boşluk ('TT kaynaklı ') — filtrelerde gözden kaçıyor.",
    "Kanal Şikayeti, Cihaz İade, Modem Değişikliği, Doping, Evrak, TT Fiber için **BOSS'ta SL yok** → SL raporunda görünmüyor.",
    "FOX 'Kalan Süre' bazı kayıtlarda donuyor (-72 / -36) → yaşlandırma için kullanılmamalı.",
    "PS26 GUZERGAH sayfasında 16.912 satırın yalnız 64'ü dolu; TICKET'ta ticket no'suz 35 kayıt; ALTYAPI/GUZERGAH'ta durum/çözüm alanı yok.",
]:
    w(f"- {t_}")
w("")
w("## 11. Yalnızca sizin cevaplayabileceğiniz sorular")
w("")
for i, t_ in enumerate(SORULAR, 1):
    w(f"{i}. {t_}")
w("")
(HERE / "is_emri_analizi.md").write_text("\n".join(L), encoding="utf-8")
print("yazıldı:", HERE / "is_emri_analizi.md", len(L), "satır")
