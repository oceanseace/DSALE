"""Süreç tasarımı için açık iş emri özetleri (yalnız toplulaştırılmış sayılar).

Girdi (salt okunur):
  - BOSS açık task raporu   : Desktop/TeknikTaskDetayRaporu.xlsx
  - FOX açık kayıtlar        : Desktop/ReportResultAçık.xls
  - FOX askıdaki kayıtlar    : Desktop/ReportResultAskı.xls
  - Kullanıcının takip dosyası: PS26/data.xlsx (TICKET / GUZERGAH / ALTYAPI)
  - Bina ana tablosu         : veri/master/bina_master.csv (location_id eşleşmesi)

Çıktı: operasyon/analiz/cikti/surec_veri.json

KİŞİSEL VERİ YOK: müşteri adı, adres, telefon, müşteri no, task no çıktıya
yazılmaz. Yalnız sayım, oran, ilçe, saat, kategori.

Çalıştırma:
  .venv/Scripts/python.exe operasyon/analiz/surec_analiz.py
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

if __package__ in (None, ""):  # doğrudan çalıştırıldı: kod/ içe aktarma yoluna (yollar)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import yollar  # noqa: E402
MASA = Path(r"C:/Users/EXT03426951/Desktop")
BOSS = MASA / "TeknikTaskDetayRaporu.xlsx"
FOX_ACIK = MASA / "ReportResultAçık.xls"
FOX_ASKI = MASA / "ReportResultAskı.xls"
TAKIP = yollar.PS26 / "data.xlsx"
BINA = yollar.VERI / "master" / "bina_master.csv"
CIKTI = Path(__file__).resolve().parent / "cikti" / "surec_veri.json"

# ---------------------------------------------------------------------------
# Sınıflandırma kuralları (süreç belgesindeki şeritlerle aynı)
# ---------------------------------------------------------------------------

def grup(ad: str) -> str:
    """Kullanıcı kuralı: adında 'kurulum' geçen = yeni müşteri, gerisi mevcut.
    İstisna: 'Kurulum Taskı Ürememiş' mevcut müşteri (operasyon) işidir."""
    a = str(ad).lower()
    if "ürememiş" in a:
        return "MEVCUT"
    return "YENI" if "kurulum" in a else "MEVCUT"


# Mevcut müşteri işleri için şerit (lane). Turkcell hedef SL'i FOX 'Hedef SL'
# sütunundan okunur; burada yalnız iş tipinin doğası tanımlanır.
SERIT = {
    # BTK'ya sayılan arızalar: hızlı şerit
    "Bağlantı Problemi": "BTK",
    "TV+ Arıza": "BTK",
    "Arama Problemi": "BTK",
    "Doping Arıza Bildirimi": "BTK",
    # Telefonla/masa başında çözülen: sahaya gitmeden
    "Kanal Şikayeti": "MASA",
    "Teknik Servis Ücretlendirme": "MASA",
    # Sahada cihaz işi (arıza değil, hizmet)
    "2.Donanım": "CIHAZ",
    "Modem Değişikliği": "CIHAZ",
    "Superbox Modem Değişikliği": "CIHAZ",
    "STB Cihaz Değişikliği": "CIHAZ",
    # Toplanabilir lojistik: iade, geri alım, evrak
    "Cihaz İade Bekleniyor": "LOJISTIK",
    "Cihaz Geri Alım": "LOJISTIK",
    "Turksat Cihaz İade - Yerinde Hizmet": "LOJISTIK",
    "Sosyal Destek Evrak Toplama": "LOJISTIK",
    "Turksat Evrak Toplama": "LOJISTIK",
}


def serit(ad: str) -> str:
    if grup(ad) == "YENI":
        return "KURULUM"
    return SERIT.get(str(ad), "DIGER")


YAS_SINIR = [0, 24, 48, 72, 24 * 7, 24 * 30, 1e9]
YAS_AD = ["<24s", "24-48s", "48-72s", "3-7g", "7-30g", ">30g"]


def yas_kova(saat: pd.Series) -> pd.Series:
    return pd.cut(saat, YAS_SINIR, labels=YAS_AD, right=False)


def sayim(s: pd.Series) -> dict:
    return {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}


def kova_say(s: pd.Series) -> dict:
    v = yas_kova(s).value_counts().reindex(YAS_AD).fillna(0)
    return {k: int(x) for k, x in v.items()}


def ceyrek(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {}
    q = s.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(len(s)), "p10": round(float(q[0.1]), 2), "p25": round(float(q[0.25]), 2),
            "medyan": round(float(q[0.5]), 2), "p75": round(float(q[0.75]), 2),
            "p90": round(float(q[0.9]), 2)}


# "Son Açıklama" serbest metninden eylem sınıfı (içerik dışarı yazılmaz)
ACIKLAMA_KURAL = [
    ("ulasilamadi", r"ula[sş][ıi]lam|cevaps[ıi]z|cvp verm|cevap verm|aramalara cevap|ula[sş]am[ıi]yor"),
    ("tt_etiket", r"etiketleme"),
    ("ekibe_iletildi", r"ekip ata|ekibe|teknik ekibe|atamas|atama"),
    ("ileri_tarih", r"ileri (bir )?tarih|ertelen"),
    ("musteri_teslim", r"kendisi teslim|kargo"),
    ("stok_yok", r"stok|depoda"),
    ("guzergah", r"g[uü]zergah"),
    ("adres_hatali", r"adres[ıi]? hatal|do[gğ]ru adres"),
]


def aciklama_sinifi(metin) -> str:
    if not isinstance(metin, str) or not metin.strip(" .\n"):
        return "bos"
    m = metin.lower()
    for ad, desen in ACIKLAMA_KURAL:
        if re.search(desen, m):
            return ad
    return "diger"


def main() -> None:
    b = pd.read_excel(BOSS)
    fa = pd.read_excel(FOX_ACIK)
    fk = pd.read_excel(FOX_ASKI)
    fox = pd.concat([fa.assign(fox_liste="acik"), fk.assign(fox_liste="aski")], ignore_index=True)
    fox["kalan_saat"] = (fox["Kalan Süre"].astype(str).str.replace(".", "", regex=False)
                         .str.replace(",", ".", regex=False).astype(float))

    # Dışa aktarım anı: en yeni task başlangıcının hemen sonrası
    simdi = b["Task Başlangıç Tarihi"].max().ceil("h")

    b["Askıya Alınma Nedeni"] = b["Askıya Alınma Nedeni"].map(lambda v: v.strip() if isinstance(v, str) else None)
    b["Merkeze Gönder Statüsü"] = b["Merkeze Gönder Statüsü"].map(lambda v: v.strip() if isinstance(v, str) else None)
    b["grup"] = b["Task Adı"].map(grup)
    b["serit"] = b["Task Adı"].map(serit)
    b["yas_saat"] = (simdi - b["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600
    b["aciklama"] = b["Son Açıklama"].map(aciklama_sinifi)

    m = b.merge(fox[["Akış No", "fox_liste", "Hedef SL", "kalan_saat", "Akış Statüsü",
                     "Başlangıç Tarihi", "Task Adı", "Üstlenen Kodu - Adı"]]
                .rename(columns={"Task Adı": "fox_task", "Başlangıç Tarihi": "fox_baslangic"}),
                left_on="Task No", right_on="Akış No", how="left")

    out: dict = {"uretim": {"simdi_varsayim": str(simdi), "not": "yalnız toplulaştırılmış sayılar"}}

    # --- 1. Kaynak eşleşmesi --------------------------------------------------
    sb, sa, sk = set(b["Task No"]), set(fa["Akış No"]), set(fk["Akış No"])
    fox_aski_boss_aktif = m[(m["fox_liste"] == "aski") & (m["Task Durumu"] != "Askıya alındı")]
    boss_aski_fox_acik = m[(m["fox_liste"] == "acik") & (m["Task Durumu"] == "Askıya alındı")]
    out["eslesme"] = {
        "boss": len(sb), "fox_acik": len(sa), "fox_aski": len(sk),
        "boss_ve_fox_acik": len(sb & sa), "boss_ve_fox_aski": len(sb & sk),
        "yalniz_boss": len(sb - sa - sk), "yalniz_fox_acik": len(sa - sb), "yalniz_fox_aski": len(sk - sb),
        "fox_askida_ama_boss_aktif": int(len(fox_aski_boss_aktif)),
        "fox_askida_ama_boss_aktif_durum": sayim(fox_aski_boss_aktif["Task Durumu"]),
        "boss_askida_ama_fox_acik": int(len(boss_aski_fox_acik)),
        "fox_to_boss_gecikme_saat": ceyrek((m["Task Başlangıç Tarihi"] - m["fox_baslangic"]).dt.total_seconds() / 3600),
        "fox_task_adi_eslesmesi": {f"{r['Task Adı']} <- {r['fox_task']}": int(r["n"])
                                    for _, r in m.groupby(["Task Adı", "fox_task"]).size()
                                    .reset_index(name="n").iterrows()},
    }
    # FOX askı kayıtlarının kimin üzerinde durduğu (kişi adı yazılmaz, yalnız pay)
    ustlenen = fk["Üstlenen Kodu - Adı"].fillna("-").astype(str)
    out["fox_aski_ustlenen"] = {
        "kullanicinin_kendisi(EXT03426951)": int(ustlenen.str.startswith("EXT03426951").sum()),
        "diger_4_kisi": int((~ustlenen.str.startswith("EXT03426951")).sum()),
        "kisi_sayisi": int(ustlenen.nunique()),
    }

    # --- 2. Turkcell hedef SL (FOX) iş tipine göre ----------------------------
    hsl = fox.groupby("Task Adı")["Hedef SL"].agg(lambda s: int(s.mode().iloc[0])).to_dict()
    out["turkcell_hedef_sl_saat_fox"] = {k: int(v) for k, v in sorted(hsl.items(), key=lambda x: x[1])}
    out["fox_akis_statusu"] = sayim(fox["Akış Statüsü"])

    # --- 3. Grup / şerit ---------------------------------------------------------
    def ozet(d: pd.DataFrame) -> dict:
        return {
            "adet": int(len(d)),
            "yas_kovasi": kova_say(d["yas_saat"]),
            "yas_saat": ceyrek(d["yas_saat"]),
            "task_durumu": sayim(d["Task Durumu"]),
            "randevu": sayim(d["Randevu Durumu"]),
            "ekip_var": int(d["Ekip"].notna().sum()),
            "aski_nedeni": sayim(d["Askıya Alınma Nedeni"].fillna("-")),
            "merkeze_gonder": sayim(d["Merkeze Gönder Statüsü"].fillna("-")),
            "sl": sayim(d["SL"].fillna("-")),
            "son_aciklama_sinifi": sayim(d["aciklama"]),
            "24s_asan": int((d["yas_saat"] >= 24).sum()),
        }

    out["grup"] = {g: ozet(d) for g, d in b.groupby("grup")}
    out["serit"] = {s: ozet(d) for s, d in b.groupby("serit")}
    out["task_adi"] = {t: {"adet": int(len(d)), "grup": d["grup"].iloc[0], "serit": d["serit"].iloc[0],
                           "yas_medyan_saat": round(float(d["yas_saat"].median()), 1),
                           "24s_asan": int((d["yas_saat"] >= 24).sum()),
                           "askida": int((d["Task Durumu"] == "Askıya alındı").sum()),
                           "merkeze": int((d["Task Durumu"] == "Merkeze gönderildi").sum())}
                       for t, d in b.groupby("Task Adı")}
    out["genel"] = ozet(b)

    # Turkcell hedef SL'e göre gecikme (FOX hedefi > 0 olan işler)
    hedefli = m[m["Hedef SL"].fillna(0) > 0].copy()
    hedefli["gecikme"] = hedefli["yas_saat"] - hedefli["Hedef SL"]
    out["turkcell_hedefine_gore"] = {
        "hedefli_is": int(len(hedefli)),
        "hedefi_asan": int((hedefli["gecikme"] > 0).sum()),
        "hedef_bazinda": {str(int(h)): {"adet": int(len(d)), "asan": int((d["gecikme"] > 0).sum())}
                          for h, d in hedefli.groupby("Hedef SL")},
    }

    # --- 4. Varış deseni (yalnız hâlâ açık olanlar: kapananlar görünmez) --------
    son14 = b[b["Task Başlangıç Tarihi"] >= simdi.normalize() - pd.Timedelta(days=13)]
    gun = son14.groupby([son14["Task Başlangıç Tarihi"].dt.date, "grup"]).size().unstack(fill_value=0)
    out["varis_gunluk_acik_kalan"] = {str(k): {g: int(v) for g, v in r.items()} for k, r in gun.iterrows()}
    son7 = b[b["Task Başlangıç Tarihi"] >= simdi - pd.Timedelta(days=7)]
    saat = son7["Task Başlangıç Tarihi"].dt.hour.value_counts().sort_index()
    out["varis_saat_son7g"] = {int(k): int(v) for k, v in saat.items()}
    toplam7 = max(len(son7), 1)
    out["varis_pencere_payi_son7g"] = {
        "00-08": round(float(son7["Task Başlangıç Tarihi"].dt.hour.between(0, 7).sum()) / toplam7, 3),
        "08-12": round(float(son7["Task Başlangıç Tarihi"].dt.hour.between(8, 11).sum()) / toplam7, 3),
        "12-17": round(float(son7["Task Başlangıç Tarihi"].dt.hour.between(12, 16).sum()) / toplam7, 3),
        "17-20": round(float(son7["Task Başlangıç Tarihi"].dt.hour.between(17, 19).sum()) / toplam7, 3),
        "20-24": round(float(son7["Task Başlangıç Tarihi"].dt.hour.between(20, 23).sum()) / toplam7, 3),
    }
    out["varis_haftanin_gunu_son14g"] = sayim(son14["Task Başlangıç Tarihi"].dt.day_name())

    # --- 5. Randevu --------------------------------------------------------------
    r = b[b["Randevu Durumu"] == "Randevulu"].copy()
    bugun = simdi.normalize()
    rgun = (r["Randevu Başlangıç Tarihi"].dt.normalize() - bugun).dt.days
    out["randevu"] = {
        "randevulu": int(len(r)),
        "randevu_tarihi_gecmis": int((rgun < 0).sum()),
        "randevu_bugun": int((rgun == 0).sum()),
        "randevu_yarin": int((rgun == 1).sum()),
        "randevu_2g_ve_sonra": int((rgun >= 2).sum()),
        "gecmis_randevu_task_durumu": sayim(r.loc[rgun < 0, "Task Durumu"]),
        "task_basindan_randevuya_saat": ceyrek((r["Randevu Başlangıç Tarihi"] - r["Task Başlangıç Tarihi"])
                                               .dt.total_seconds() / 3600),
        "randevu_penceresi_saat": ceyrek((r["Randevu Bitiş Tarihi"] - r["Randevu Başlangıç Tarihi"])
                                         .dt.total_seconds() / 3600),
        "randevu_saat_dagilimi": {int(k): int(v) for k, v in
                                  r["Randevu Başlangıç Tarihi"].dt.hour.value_counts().sort_index().items()},
    }

    # --- 6. Teknisyen adımı (konum paylaştı / başladı ama bitmedi) ---------------
    kp = b["Teknik Ekip Konum Paylaşma Tarihi"]
    ib = b["Teknik Ekip İşe Başlama Tarihi"]
    out["saha_adimi"] = {
        "konum_paylasilmis": int(kp.notna().sum()),
        "ise_baslanmis": int(ib.notna().sum()),
        "konumdan_bu_yana_saat": ceyrek((simdi - kp).dt.total_seconds() / 3600),
        "baslamadan_bu_yana_saat": ceyrek((simdi - ib).dt.total_seconds() / 3600),
        "baslama_12s_ustu_hala_acik(her_durum)": int(((simdi - ib).dt.total_seconds() / 3600 > 12).sum()),
        # Şu an "Konum Paylaşıldı" ya da "Başlandı" durumunda olup o adımdan beri 12 saati geçenler
        "sahada_durumunda": int(b["Task Durumu"].isin(["Başlandı", "Konum Paylaşıldı"]).sum()),
        "sahada_durumunda_12s_ustu": int((b["Task Durumu"].isin(["Başlandı", "Konum Paylaşıldı"])
                                          & ((simdi - ib.fillna(kp)).dt.total_seconds() / 3600 > 12)).sum()),
        "task_basindan_konuma_saat": ceyrek((kp - b["Task Başlangıç Tarihi"]).dt.total_seconds() / 3600),
        "web_mobil": sayim(b["Web/Mobil"].fillna("-")),
    }

    # --- 7. Ekip yükü (isim yazılmaz) -------------------------------------------
    ek = b["Ekip"].dropna().value_counts()
    out["ekip_yuku"] = {
        "atanmis_task": int(b["Ekip"].notna().sum()), "atanmamis_task": int(b["Ekip"].isna().sum()),
        "ekip_sayisi_acik_isi_olan": int(len(ek)),
        "ekip_basina_acik_is": ceyrek(ek.astype(float)),
        "en_yuklu_ekip_is": int(ek.max()) if len(ek) else 0,
        "atanmamis_durum": sayim(b.loc[b["Ekip"].isna(), "Task Durumu"]),
    }

    # --- 8. Askı ve merkeze gönderilenler ----------------------------------------
    ask = b[b["Task Durumu"] == "Askıya alındı"]
    mg = b[b["Task Durumu"] == "Merkeze gönderildi"]
    out["aski"] = {
        "adet": int(len(ask)),
        "neden": sayim(ask["Askıya Alınma Nedeni"].fillna("-")),
        "neden_yas": {n: kova_say(d["yas_saat"]) for n, d in ask.groupby(ask["Askıya Alınma Nedeni"].fillna("-"))},
        "task_adi": sayim(ask["Task Adı"]),
        "son_aciklama_sinifi": sayim(ask["aciklama"]),
    }
    out["merkeze_gonderildi"] = {
        "adet": int(len(mg)),
        "neden": sayim(mg["Merkeze Gönder Statüsü"].fillna("-")),
        "yas": kova_say(mg["yas_saat"]),
        "task_adi": sayim(mg["Task Adı"]),
    }
    # Altyapı kaynaklı (sahaya gitmekle çözülmeyen) işler ve bina yoğunlaşması
    altyapi_nedeni = {"GÜZERGAH YOK", "SİNYAL YOK", "BOŞ PORT YOK"}
    alt = b[(b["Askıya Alınma Nedeni"] == "TT kaynaklı")
            | b["Merkeze Gönder Statüsü"].isin(altyapi_nedeni)
            | (b["aciklama"].isin(["tt_etiket", "guzergah"]))]
    lok = alt["Lokasyon"].dropna()
    out["altyapi_kaynakli"] = {
        "adet": int(len(alt)),
        "lokasyonu_bilinen": int(len(lok)),
        "tekil_lokasyon": int(lok.nunique()),
        "en_kalabalik_lokasyondaki_is": int(lok.value_counts().max()) if len(lok) else 0,
        "2_ve_ustu_isli_lokasyon": int((lok.value_counts() >= 2).sum()),
        "neden": {
            "TT_kaynakli_aski": int((alt["Askıya Alınma Nedeni"] == "TT kaynaklı").sum()),
            "tt_etiketleme_aciklamasi": int((alt["aciklama"] == "tt_etiket").sum()),
            **{k: int((alt["Merkeze Gönder Statüsü"] == k).sum()) for k in sorted(altyapi_nedeni)},
        },
        "grup": sayim(alt["grup"]),
    }

    # --- 9. Lokasyon → bina eşleşmesi (harita / rota için) -----------------------
    try:
        bm = pd.read_csv(BINA, usecols=["location_id", "ilce", "lat", "lon"], dtype={"location_id": str})
        lokset = set(bm["location_id"].dropna().astype(str))
        l = b["Lokasyon"].dropna().astype(str)
        out["lokasyon_eslesme"] = {
            "lokasyonu_dolu_task": int(len(l)),
            "bina_master_ile_eslesen": int(l.isin(lokset).sum()),
            "lokasyonu_bos_task": int(b["Lokasyon"].isna().sum()),
            "lokasyonu_bos_grup": sayim(b.loc[b["Lokasyon"].isna(), "grup"]),
        }
    except Exception as e:  # noqa: BLE001
        out["lokasyon_eslesme"] = {"hata": str(e)}

    # --- 10. İlçe dağılımı (mevcut müşteri) --------------------------------------
    out["ilce_mevcut"] = sayim(b.loc[b["grup"] == "MEVCUT", "İlçe"])
    out["ilce_yeni"] = sayim(b.loc[b["grup"] == "YENI", "İlçe"])

    # --- 11. Kullanıcının takip dosyası (TICKET / GUZERGAH / ALTYAPI) ------------
    try:
        x = pd.ExcelFile(TAKIP)
        t = x.parse("TICKET")
        g = x.parse("GUZERGAH")
        g = g[g["Konu"].notna()]
        al = x.parse("ALTYAPI")
        t_acik = t[t["Durum"] == "AÇIK"]
        out["takip_dosyasi"] = {
            "ticket_adet": int(len(t)), "ticket_konu": sayim(t["Konu"]), "ticket_durum": sayim(t["Durum"]),
            "ticket_konu_durum": {f"{a}|{d}": int(n) for (a, d), n in t.groupby(["Konu", "Durum"]).size().items()},
            "ticket_kanal": sayim(t["Kanal"]),
            "acik_ticket_yas_gun": ceyrek((simdi - pd.to_datetime(t_acik["Baslangic"], errors="coerce")).dt.days.astype(float)),
            "ticket_tarih_araligi": [str(pd.to_datetime(t["Baslangic"]).min().date()), str(pd.to_datetime(t["Baslangic"]).max().date())],
            "guzergah_yok_kayit": int(len(g)), "guzergah_tekil_lokasyon": int(g["Lokasyon"].nunique()),
            "altyapi_satis_kaydi": int(len(al)), "altyapi_kanal": sayim(al["Kanal"]),
            "altyapi_tarih_araligi": [str(pd.to_datetime(al["Baslangic"]).min().date()), str(pd.to_datetime(al["Baslangic"]).max().date())],
        }
    except Exception as e:  # noqa: BLE001
        out["takip_dosyasi"] = {"hata": str(e)}

    # --- 12. Birikmiş iş (backlog) kovaları: karşılıklı dışlayan -----------------
    def kova(r) -> str:
        if r["Task Durumu"] == "Askıya alındı" and r["Askıya Alınma Nedeni"] == "TT kaynaklı":
            return "K1_TT_altyapi_bekliyor"
        if r["Merkeze Gönder Statüsü"] in altyapi_nedeni or r["aciklama"] in ("tt_etiket", "guzergah"):
            return "K2_altyapi_eskalasyon"
        if r["Task Durumu"] == "Askıya alındı":
            return "K3_abone_kaynakli_aski"
        if r["Task Durumu"] == "Merkeze gönderildi":
            return "K4_merkeze_gonderildi_ulasilamadi_vb"
        if r["serit"] == "MASA":
            return "K5_telefon_masa_isi"
        if r["serit"] == "LOJISTIK":
            return "K6_lojistik_toplu"
        if r["Task Durumu"] in ("Konum Paylaşıldı", "Başlandı"):
            return "K7_sahada_kapanmayi_bekliyor"
        if pd.notna(r["Ekip"]):
            return "K8_ekipte_bekliyor"
        return "K9_atanmamis_saha_isi"

    b["kova"] = b.apply(kova, axis=1)
    geciken = b[b["yas_saat"] >= 24]
    out["birikmis_is"] = {
        "24s_asan_toplam": int(len(geciken)),
        "kova": {k: {"adet": int(len(d)), "mevcut": int((d["grup"] == "MEVCUT").sum()),
                     "yeni": int((d["grup"] == "YENI").sum()),
                     "btk": int((d["serit"] == "BTK").sum()),
                     "yas": kova_say(d["yas_saat"])}
                 for k, d in geciken.groupby("kova")},
        "tum_acik_kova": sayim(b["kova"]),
    }

    # Kullanıcının kendi masası: mevcut müşteri işleri
    mev = b[b["grup"] == "MEVCUT"]
    out["mevcut_musteri_masasi"] = {
        "adet": int(len(mev)),
        "24s_asan": int((mev["yas_saat"] >= 24).sum()),
        "btk_adet": int((mev["serit"] == "BTK").sum()),
        "btk_24s_asan": int(((mev["serit"] == "BTK") & (mev["yas_saat"] >= 24)).sum()),
        "btk_yas": kova_say(mev.loc[mev["serit"] == "BTK", "yas_saat"]),
        "serit": sayim(mev["serit"]),
        "kova": sayim(mev["kova"]),
    }

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("yazildi:", CIKTI)


if __name__ == "__main__":
    main()
