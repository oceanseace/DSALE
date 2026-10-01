"""Tur raporu ve OneMap yenileme — sistem hep GÜNCEL veriyle çalışsın.

Akış (yönetici):
    1. Yeni tur raporunu (data.xlsx, ORIGN sayfası) yükle → dosya
       ``<çalışma>/gelen/tur_<zaman>.xlsx`` olarak saklanır, bugünkü binalarla FARKI
       gösterilir: yeni bina, rapordan çıkan bina, HP/abone/fırsatı değişen bina,
       toplamlar önce/sonra. Veritabanına HİÇBİR ŞEY yazılmaz.
    2. "Uygula" → tek işlemde:
         * var olan binaların RES HP / abone / fırsat / Toplam HP'si güncellenir
           (bölgeler SABİT kalır, her değişikliğin izi ``bina_degisim`` tablosunda),
         * raporda olmayan bina PASİF olur (silinmez; ziyaret geçmişi durur, listeye girmez),
         * rapora geri dönen pasif bina yeniden etkinleşir,
         * yeni bina ``bina_bekleyen`` tablosuna "konum bekliyor" olarak girer.
    3. Yeni binaların koordinatı OneMap'ten gelir: ``saha/araclar/onemap_cek.js``
       tarayıcıda (OneMap oturumu açıkken) çalıştırılır, indirdiği ``onemap_yeni.json``
       yüklenir → bina poligon merkeziyle haritaya eklenir, aynı sitenin bölgesine ya
       da en yakın binanın bölgesine verilir.

Mevcut ``site_grup`` anahtarlarına ve bölgelere dokunulmaz. Kalite kuralları
(dsale/kalite.py) değişen her binada yeniden çalışır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import sqlite3
from pathlib import Path

from . import ayarlar, db, veri_kalitesi

_gunluk = logging.getLogger("saha.tur")

ZORUNLU_SUTUNLAR = ("Bina Serial Number", "RES HP", "Aktif Abone Residential Segment")
# Raporda bugünkü binaların bu kadarından fazlası yoksa bu büyük ihtimalle KISMİ bir
# rapordur (tek ilçe, yarım dosya); pasife alma ayrıca onay ister.
PASIF_ONAY_ORANI = 0.10
ORNEK_SATIR = 60
SAYISAL = ("res_hp", "aktif_res", "toplam_hp", "soho_hp")


class TurHatasi(Exception):
    def __init__(self, durum: int, mesaj: str, kod: str):
        super().__init__(mesaj)
        self.durum, self.mesaj, self.kod = durum, mesaj, kod


# ============================================================================= okuma
def _sayi(x) -> int:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return 0
        return int(float(str(x).replace(",", ".")))
    except (TypeError, ValueError):
        return 0


def _metin(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("nan", "none", "null", "nat") else s


def raporu_oku(yol: Path) -> tuple[list[dict], dict]:
    """ORIGN sayfasını okur → (tekil bina satırları, okuma bilgisi).

    Kolon adları ``dsale/enrich.py`` ile aynı eşlemeden geçer; aynı bina iki kez
    varsa Toplam HP'si büyük olan alınır (enrich ile aynı kural).
    """
    import pandas as pd

    from dsale import kalite
    from dsale.enrich import DATA_KOLONLARI

    try:
        xl = pd.ExcelFile(yol)
    except Exception as exc:
        raise TurHatasi(400, f"Dosya Excel olarak açılamadı ({exc}). data.xlsx biçiminde olmalı.", "dosya_gecersiz")
    with xl:                          # Windows'ta açık kalan dosya silinemez/taşınamaz
        sayfa = "ORIGN" if "ORIGN" in xl.sheet_names else xl.sheet_names[0]
        d = pd.read_excel(xl, sayfa, dtype=str)
    d.columns = [str(c).strip() for c in d.columns]
    eksik = [c for c in ZORUNLU_SUTUNLAR if c not in d.columns]
    if eksik:
        raise TurHatasi(400, f"'{sayfa}' sayfasında şu sütun(lar) yok: {', '.join(eksik)}. "
                             "Tur raporunun ORIGN sayfası yüklenmeli.", "sutun_eksik")
    d = d.rename(columns={k.strip(): v for k, v in DATA_KOLONLARI.items()})
    bilgi = {"sayfa": sayfa, "satir": int(len(d)), "bos_serial": 0, "tekrar": 0, "tekrar_ornek": [],
             "bozuk_tellcordia": 0}
    satirlar: dict[str, dict] = {}
    for r in d.to_dict("records"):
        serial = _metin(r.get("bina_serial"))
        if not serial:
            bilgi["bos_serial"] += 1
            continue
        tell = _metin(r.get("tellcordia_id"))
        if tell and not tell.isdigit():
            duz = kalite.bilimselden_tamsayi(tell)
            bilgi["bozuk_tellcordia"] += 1
            tell = duz or tell
        kayit = {
            "bina_serial": serial,
            "tellcordia_id": tell,
            "location_id": kalite.location_norm(r.get("location_id")),
            "ad": _metin(r.get("ad")),
            "site_adi_crm": _metin(r.get("site_adi_crm")),
            "blok_adi_crm": _metin(r.get("blok_adi_crm")),
            "kapi_no_crm": _metin(r.get("kapi_no_crm")),
            "ilce_crm": _metin(r.get("ilce_crm")),
            "il": _metin(r.get("il")),
            "obek": _metin(r.get("obek")),
            "altyapi": _metin(r.get("altyapi")),
            "protokol_segment": _metin(r.get("protokol_segment")),
            "sales_ready": _metin(r.get("sales_ready"))[:10],
            "res_hp": _sayi(r.get("res_hp")),
            "aktif_res": _sayi(r.get("aktif_res")),
            "toplam_hp": _sayi(r.get("toplam_hp")),
            "soho_hp": _sayi(r.get("soho_hp")),
        }
        kayit["firsat"] = max(kayit["res_hp"] - kayit["aktif_res"], 0)
        onceki = satirlar.get(serial)
        if onceki is not None:
            bilgi["tekrar"] += 1
            if len(bilgi["tekrar_ornek"]) < 10:
                bilgi["tekrar_ornek"].append(serial)
            if kayit["toplam_hp"] <= onceki["toplam_hp"]:
                continue
        satirlar[serial] = kayit
    bilgi["tekil_bina"] = len(satirlar)
    return list(satirlar.values()), bilgi


# ============================================================================= fark
def _binalar(conn: sqlite3.Connection) -> dict[str, dict]:
    return {r["bina_serial"]: dict(r) for r in conn.execute(
        "SELECT bina_serial, ad, site_adi, ilce, il, bolge, pasif, res_hp, aktif_res, firsat, toplam_hp, "
        "       soho_hp, tellcordia_id, location_id FROM bina").fetchall()}


def _toplam(kayitlar) -> dict:
    t = {"bina": 0, "res_hp": 0, "aktif_res": 0, "firsat": 0, "toplam_hp": 0}
    for r in kayitlar:
        t["bina"] += 1
        for a in ("res_hp", "aktif_res", "firsat", "toplam_hp"):
            t[a] += int(r.get(a) or 0)
    return t


def _hizmet_illeri(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT il FROM bina WHERE il IS NOT NULL AND il<>''")}


def fark_hesapla(conn: sqlite3.Connection, satirlar: list[dict], iller: set[str] | None = None) -> dict:
    """Rapor ile veritabanı arasındaki fark. Yazmaz."""
    mevcut = _binalar(conn)
    rapor = {r["bina_serial"]: r for r in satirlar}
    hizmet = iller if iller is not None else _hizmet_illeri(conn)

    yeni = [r for s, r in rapor.items() if s not in mevcut]
    yeni_hizmette = [r for r in yeni if not hizmet or r["il"] in hizmet]
    il_disi = [r for r in yeni if hizmet and r["il"] not in hizmet]
    cikan = [b for s, b in mevcut.items() if s not in rapor and not b["pasif"]]
    geri_donen = [b for s, b in mevcut.items() if s in rapor and b["pasif"]]
    degisen = []
    for s, r in rapor.items():
        b = mevcut.get(s)
        if not b:
            continue
        alanlar = {a: [int(b.get(a) or 0), int(r[a])] for a in ("res_hp", "aktif_res", "firsat", "toplam_hp")
                   if int(b.get(a) or 0) != int(r[a])}
        if alanlar:
            degisen.append({"bina_serial": s, "ad": b.get("ad") or b.get("site_adi") or "", "bolge": b.get("bolge"),
                            "ilce": b.get("ilce"), "degisim": alanlar,
                            "firsat_fark": int(r["firsat"]) - int(b.get("firsat") or 0)})
    degisen.sort(key=lambda x: -abs(x["firsat_fark"]))

    aktif_once = [b for b in mevcut.values() if not b["pasif"]]
    sonra = [({**mevcut[s], **{a: r[a] for a in ("res_hp", "aktif_res", "firsat", "toplam_hp")}})
             for s, r in rapor.items() if s in mevcut]
    once_t, sonra_t = _toplam(aktif_once), _toplam(sonra)
    yeni_t = _toplam(yeni_hizmette)
    cikan_oran = len(cikan) / len(aktif_once) if aktif_once else 0.0

    il_sayim: dict[str, int] = {}
    for r in il_disi:
        il_sayim[r["il"] or "?"] = il_sayim.get(r["il"] or "?", 0) + 1
    uyarilar = []
    if cikan_oran > PASIF_ONAY_ORANI:
        uyarilar.append(
            f"Raporda bugünkü binaların %{cikan_oran * 100:.0f}'i yok ({len(cikan):,} bina). Bu bir KISMİ rapor "
            "olabilir (tek ilçe / yarım dosya). Uygularsanız bu binalar pasife alınır; ayrıca onay istenir."
            .replace(",", "."))
    if il_disi:
        uyarilar.append(
            f"Raporda hizmet verilen iller dışında {len(il_disi):,} bina var "
            f"({', '.join(f'{k}: {v}' for k, v in sorted(il_sayim.items(), key=lambda x: -x[1])[:5])}). "
            "Bunlar varsayılan olarak eklenmez.".replace(",", "."))
    return {
        "once": once_t,
        "sonra": {k: sonra_t[k] + yeni_t[k] for k in once_t},
        "sonra_haric_yeni": sonra_t,
        "yeni_bina": len(yeni_hizmette),
        "yeni_bina_il_disi": len(il_disi),
        "il_disi_dagilim": il_sayim,
        "cikan_bina": len(cikan),
        "cikan_oran": round(cikan_oran, 4),
        "pasif_onay_gerekli": cikan_oran > PASIF_ONAY_ORANI,
        "geri_donen_bina": len(geri_donen),
        "degisen_bina": len(degisen),
        "degismeyen_bina": len([s for s in rapor if s in mevcut]) - len(degisen),
        "ornek": {
            "yeni": [{a: r[a] for a in ("bina_serial", "ad", "site_adi_crm", "ilce_crm", "il", "res_hp",
                                        "aktif_res", "firsat")} for r in yeni_hizmette[:ORNEK_SATIR]],
            "cikan": [{a: b.get(a) for a in ("bina_serial", "ad", "site_adi", "ilce", "bolge", "res_hp",
                                             "firsat")} for b in cikan[:ORNEK_SATIR]],
            "degisen": degisen[:ORNEK_SATIR],
            "geri_donen": [{a: b.get(a) for a in ("bina_serial", "ad", "ilce", "bolge")} for b in geri_donen[:20]],
        },
        "hizmet_illeri": sorted(hizmet),
        "uyarilar": uyarilar,
    }


# ============================================================================= yükleme
def _satir_dosyasi(xlsx: Path) -> Path:
    return xlsx.with_suffix(".satirlar.json")


def yukle(conn: sqlite3.Connection, icerik: bytes, dosya_adi: str, yapan_id: int) -> dict:
    """Dosyayı saklar, okur, farkı hesaplar ve önizleme kaydı açar (bina tablosuna yazmaz)."""
    if not icerik:
        raise TurHatasi(400, "Dosya boş.", "dosya_bos")
    if not icerik[:4] == b"PK\x03\x04":
        raise TurHatasi(400, "Bu bir .xlsx dosyası değil. Tur raporunu Excel (.xlsx) olarak yükleyin.",
                        "dosya_gecersiz")
    klasor = ayarlar.gelen_dizini()
    klasor.mkdir(parents=True, exist_ok=True)
    zaman = ayarlar.simdi()
    yol = klasor / f"tur_{zaman.strftime('%Y%m%d_%H%M%S')}.xlsx"
    sira = 1
    while yol.exists():
        sira += 1
        yol = klasor / f"tur_{zaman.strftime('%Y%m%d_%H%M%S')}_{sira}.xlsx"
    yol.write_bytes(icerik)
    imza = hashlib.sha256(icerik).hexdigest()
    try:
        satirlar, bilgi = raporu_oku(yol)
    except TurHatasi:
        yol.unlink(missing_ok=True)       # okunamayan dosya saklanmaz: yanlışlıkla yüklenmiş olabilir
        raise
    json.dump({"bilgi": bilgi, "satirlar": satirlar}, open(_satir_dosyasi(yol), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    fark = fark_hesapla(conn, satirlar)
    ayni = conn.execute("SELECT id, yukleme, durum FROM tur_raporu WHERE ozet_imza=? ORDER BY id DESC LIMIT 1",
                        (imza,)).fetchone()
    ozet = {"okuma": bilgi, "fark": fark, "dosya_adi": (dosya_adi or "")[:200],
            "ayni_dosya_daha_once": dict(ayni) if ayni else None}
    imlec = conn.execute(
        "INSERT INTO tur_raporu (dosya, ozet_imza, yukleme, yukleyen_id, durum, ozet) VALUES (?,?,?,?,?,?)",
        (str(yol), imza, ayarlar.zaman_metni(zaman), yapan_id, "onizleme", json.dumps(ozet, ensure_ascii=False)))
    conn.commit()
    return {"tur_id": int(imlec.lastrowid), "dosya": yol.name, **ozet}


def _satirlari_getir(dosya: str) -> list[dict]:
    yol = Path(dosya)
    ek = _satir_dosyasi(yol)
    if ek.exists():
        return json.load(open(ek, encoding="utf-8"))["satirlar"]
    if not yol.exists():
        raise TurHatasi(410, "Rapor dosyası bulunamadı (silinmiş olabilir). Yeniden yükleyin.", "dosya_yok")
    return raporu_oku(yol)[0]


def liste(conn: sqlite3.Connection) -> list[dict]:
    satirlar = conn.execute(
        "SELECT t.id, t.dosya, t.yukleme, t.durum, t.uygulama, t.ozet, k.ad AS yukleyen "
        "FROM tur_raporu t LEFT JOIN kullanici k ON k.id=t.yukleyen_id ORDER BY t.id DESC LIMIT 50").fetchall()
    sonuc = []
    for r in satirlar:
        ozet = json.loads(r["ozet"] or "{}")
        f = ozet.get("fark", {})
        sonuc.append({"tur_id": r["id"], "dosya": Path(r["dosya"]).name, "yukleme": r["yukleme"],
                      "durum": r["durum"], "uygulama": r["uygulama"], "yukleyen": r["yukleyen"],
                      "yeni_bina": f.get("yeni_bina"), "cikan_bina": f.get("cikan_bina"),
                      "degisen_bina": f.get("degisen_bina")})
    return sonuc


def getir(conn: sqlite3.Connection, tur_id: int) -> dict:
    r = conn.execute("SELECT * FROM tur_raporu WHERE id=?", (tur_id,)).fetchone()
    if not r:
        raise TurHatasi(404, "Tur raporu kaydı bulunamadı.", "tur_yok")
    return {"tur_id": r["id"], "dosya": Path(r["dosya"]).name, "yukleme": r["yukleme"], "durum": r["durum"],
            "uygulama": r["uygulama"], **json.loads(r["ozet"] or "{}")}


# ============================================================================= uygulama
def uygula(conn: sqlite3.Connection, tur_id: int, yapan_id: int, pasif_onay: bool = False,
           iller: list[str] | None = None) -> dict:
    t = conn.execute("SELECT * FROM tur_raporu WHERE id=?", (tur_id,)).fetchone()
    if not t:
        raise TurHatasi(404, "Tur raporu kaydı bulunamadı.", "tur_yok")
    if t["durum"] == "uygulandi":
        return {"tur_id": tur_id, "zaten_uygulandi": True, "uygulama": t["uygulama"],
                "mesaj": "Bu tur raporu zaten uygulanmıştı; hiçbir şey iki kez yazılmadı."}
    yeni_var = conn.execute("SELECT id, uygulama FROM tur_raporu WHERE durum='uygulandi' AND id>? "
                            "ORDER BY id DESC LIMIT 1", (tur_id,)).fetchone()
    if yeni_var:
        raise TurHatasi(409, f"Bundan sonra yüklenen bir tur raporu ({yeni_var['uygulama']}) zaten uygulandı. "
                             "Eski raporu uygulamak verileri geriye götürür.", "daha_yeni_var")
    satirlar = _satirlari_getir(t["dosya"])
    hizmet = set(iller) if iller else None
    fark = fark_hesapla(conn, satirlar, hizmet)       # önizlemeden bu yana değişmiş olabilir: yeniden
    if fark["pasif_onay_gerekli"] and not pasif_onay:
        raise TurHatasi(409, f"Bu rapor uygulanırsa {fark['cikan_bina']} bina (%{fark['cikan_oran'] * 100:.0f}) "
                             "pasife alınır. Rapor eksik değilse 'pasife almayı onaylıyorum' ile tekrar deneyin.",
                        "pasif_onay_gerekli")

    mevcut = _binalar(conn)
    rapor = {r["bina_serial"]: r for r in satirlar}
    hizmet_illeri = hizmet if hizmet is not None else _hizmet_illeri(conn)
    simdi = ayarlar.zaman_metni()
    kaynak = f"tur:{tur_id}"
    dokunulan: list[str] = []
    guncellenen = pasif = geri = yeni = 0

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        degisim = []
        for s, r in rapor.items():
            b = mevcut.get(s)
            if not b:
                continue
            farkli = False
            for a in ("res_hp", "aktif_res", "firsat", "toplam_hp", "soho_hp"):
                if int(b.get(a) or 0) != int(r[a]):
                    degisim.append((s, kaynak, a, str(b.get(a)), str(r[a]), simdi))
                    farkli = True
            conn.execute(
                "UPDATE bina SET res_hp=?, aktif_res=?, firsat=?, toplam_hp=?, soho_hp=?, tur_tarihi=? "
                "WHERE bina_serial=?",
                (r["res_hp"], r["aktif_res"], r["firsat"], r["toplam_hp"], r["soho_hp"], simdi, s))
            if b["pasif"]:
                conn.execute("UPDATE bina SET pasif=0, pasif_tarih=NULL WHERE bina_serial=?", (s,))
                degisim.append((s, kaynak, "pasif", "1", "0", simdi))
                geri += 1
                farkli = True
            if farkli:
                guncellenen += 1
                dokunulan.append(s)
        for s, b in mevcut.items():
            if s not in rapor and not b["pasif"]:
                conn.execute("UPDATE bina SET pasif=1, pasif_tarih=? WHERE bina_serial=?", (simdi, s))
                degisim.append((s, kaynak, "pasif", "0", "1", simdi))
                pasif += 1
        conn.executemany(
            "INSERT INTO bina_degisim (bina_serial, kaynak, alan, eski, yeni, zaman) VALUES (?,?,?,?,?,?)", degisim)

        for s, r in rapor.items():
            if s in mevcut or (hizmet_illeri and r["il"] not in hizmet_illeri):
                continue
            conn.execute(
                "INSERT INTO bina_bekleyen (bina_serial, tellcordia_id, location_id, veri, durum, tur_id, eklenme, "
                "guncelleme) VALUES (?,?,?,?,'konum_bekliyor',?,?,?) "
                "ON CONFLICT(bina_serial) DO UPDATE SET tellcordia_id=excluded.tellcordia_id, "
                "location_id=excluded.location_id, veri=excluded.veri, tur_id=excluded.tur_id, "
                "guncelleme=excluded.guncelleme, "
                "durum=CASE WHEN bina_bekleyen.durum='eklendi' THEN 'eklendi' ELSE 'konum_bekliyor' END",
                (s, r["tellcordia_id"], r["location_id"], json.dumps(r, ensure_ascii=False), tur_id, simdi, simdi))
            yeni += 1
        # Önceki turda gelip bu raporda olmayan bekleyenler artık beklenmez.
        bekleyen = [r[0] for r in conn.execute("SELECT bina_serial FROM bina_bekleyen WHERE durum='konum_bekliyor'")]
        cikti = [(simdi, s) for s in bekleyen if s not in rapor]
        conn.executemany("UPDATE bina_bekleyen SET durum='rapordan_cikti', guncelleme=? WHERE bina_serial=?", cikti)

        veri_kalitesi.yenile(conn, dokunulan)
        ozet = json.loads(t["ozet"] or "{}")
        ozet["uygulanan"] = {"guncellenen": guncellenen, "pasife_alinan": pasif, "geri_donen": geri,
                             "konum_bekleyen": yeni, "fark": {k: v for k, v in fark.items() if k != "ornek"}}
        conn.execute("UPDATE tur_raporu SET durum='uygulandi', uygulama=?, uygulayan_id=?, ozet=? WHERE id=?",
                     (simdi, yapan_id, json.dumps(ozet, ensure_ascii=False), tur_id))
        conn.execute("UPDATE tur_raporu SET durum='eskidi' WHERE durum='onizleme' AND id<?", (tur_id,))
        db.ayar_yaz(conn, "tur_raporu_son", json.dumps({"tur_id": tur_id, "zaman": simdi}))
        db.bina_surumu_arttir(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "tur_id": tur_id, "zaten_uygulandi": False,
        "guncellenen_bina": guncellenen, "pasife_alinan_bina": pasif, "geri_donen_bina": geri,
        "konum_bekleyen_bina": yeni, "once": fark["once"], "sonra": fark["sonra_haric_yeni"],
        "mesaj": (f"Tur raporu uygulandı: {guncellenen} binanın sayıları güncellendi, {pasif} bina pasife "
                  f"alındı, {yeni} yeni bina OneMap konumu bekliyor. Bölgeler değişmedi."),
    }


# ============================================================================= bekleyenler ve OneMap
def bekleyenler(conn: sqlite3.Connection, durum: str = "konum_bekliyor") -> list[dict]:
    satirlar = conn.execute(
        "SELECT bina_serial, tellcordia_id, location_id, veri, durum, tur_id, eklenme, guncelleme "
        "FROM bina_bekleyen WHERE durum=? ORDER BY bina_serial", (durum,)).fetchall()
    sonuc = []
    for r in satirlar:
        v = json.loads(r["veri"] or "{}")
        sonuc.append({"bina_serial": r["bina_serial"], "tellcordia_id": r["tellcordia_id"],
                      "location_id": r["location_id"], "ad": v.get("ad"), "site_adi": v.get("site_adi_crm"),
                      "ilce": v.get("ilce_crm"), "il": v.get("il"), "res_hp": v.get("res_hp"),
                      "firsat": v.get("firsat"), "durum": r["durum"], "tur_id": r["tur_id"],
                      "eklenme": r["eklenme"]})
    return sonuc


def bekleyen_kimlikler(conn: sqlite3.Connection) -> list[str]:
    """OneMap aracına verilecek kimlikler: Tellcordia ID (= OneMap ID), yoksa Bina Serial (= LOCATION_ID)."""
    return [(r[1] if (r[1] or "").isdigit() else r[0]) for r in conn.execute(
        "SELECT bina_serial, tellcordia_id FROM bina_bekleyen WHERE durum='konum_bekliyor' ORDER BY bina_serial")]


def _ozellikler(veri: dict) -> list[tuple[dict, list]]:
    """Hem aracın ürettiği ({features:[{a, g}]}) hem ham ArcGIS ({features:[{attributes, geometry}]}) biçimi."""
    cikti = []
    for f in (veri or {}).get("features") or []:
        if not isinstance(f, dict):
            continue
        a = f.get("a") or f.get("attributes") or {}
        g = f.get("g")
        if g is None:
            g = (f.get("geometry") or {}).get("rings")
        cikti.append((a, g or []))
    return cikti


def _site_grubu(conn: sqlite3.Connection, serial: str, ilce: str, mahalle: str, site_adi: str,
                bina_turu: str, lat: float, lon: float) -> str:
    """Yeni binanın site grubu. VAR OLAN anahtarlar değişmez; yalnız uygun gruba katılınır."""
    from dsale.enrich import tr_norm

    ad = tr_norm(site_adi)
    if not ad or "TEK" in (bina_turu or "").upper():
        return f"B:{serial}"
    anahtar = f"{ilce}|{mahalle}|{ad}"
    adaylar = conn.execute(
        "SELECT site_grup, AVG(lat) AS lat, AVG(lon) AS lon FROM bina "
        "WHERE site_grup=? OR site_grup LIKE ? GROUP BY site_grup", (f"S:{anahtar}", f"S:{anahtar}#%")).fetchall()
    en_iyi, en_yakin = None, 350.0          # enrich.site_gruplari ile aynı eşik
    for a in adaylar:
        d = _mesafe_m(lat, lon, a["lat"], a["lon"])
        if d <= en_yakin:
            en_iyi, en_yakin = a["site_grup"], d
    if en_iyi:
        return en_iyi
    return f"S:{anahtar}#y{serial}" if adaylar else f"S:{anahtar}"


def _mesafe_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000.0 * math.asin(math.sqrt(a))


def _bolge_bul(conn: sqlite3.Connection, site_grup: str, lat: float, lon: float) -> int | None:
    """Aynı site grubunun bölgesi; yoksa en yakın etkin binanın bölgesi."""
    r = conn.execute("SELECT bolge, COUNT(*) c FROM bina WHERE site_grup=? AND bolge>0 GROUP BY bolge "
                     "ORDER BY c DESC LIMIT 1", (site_grup,)).fetchone()
    if r:
        return int(r["bolge"])
    pay = 0.01
    while pay <= 0.64:
        yakin = conn.execute(
            "SELECT bolge, lat, lon FROM bina WHERE pasif=0 AND bolge>0 AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (lat - pay, lat + pay, lon - pay, lon + pay)).fetchall()
        if yakin:
            return int(min(yakin, key=lambda b: _mesafe_m(lat, lon, b["lat"], b["lon"]))["bolge"])
        pay *= 2
    r = conn.execute("SELECT bolge FROM bina WHERE bolge>0 GROUP BY bolge ORDER BY COUNT(*) LIMIT 1").fetchone()
    return int(r[0]) if r else None


def onemap_yukle(conn: sqlite3.Connection, veri: dict, yapan_id: int, ham: bytes | None = None) -> dict:
    """OneMap dökümündeki bekleyen binaları haritaya ekler (tek işlem)."""
    from dsale import kalite
    from dsale.enrich import _poligon, mahalle_norm

    ozellikler = _ozellikler(veri)
    if not ozellikler:
        raise TurHatasi(400, "Dosyada OneMap binası yok. onemap_cek.js'in indirdiği onemap_yeni.json "
                             "dosyasını yükleyin.", "onemap_bos")
    if ham:
        klasor = ayarlar.gelen_dizini()
        klasor.mkdir(parents=True, exist_ok=True)
        (klasor / f"onemap_{ayarlar.simdi().strftime('%Y%m%d_%H%M%S')}.json").write_bytes(ham)

    bekleyen = {r["bina_serial"]: dict(r) for r in conn.execute(
        "SELECT * FROM bina_bekleyen WHERE durum='konum_bekliyor'").fetchall()}
    tell_index = {b["tellcordia_id"]: s for s, b in bekleyen.items() if b["tellcordia_id"]}
    mevcut = {r[0] for r in conn.execute("SELECT bina_serial FROM bina")}
    mevcut_tell = {r[0] for r in conn.execute("SELECT tellcordia_id FROM bina WHERE tellcordia_id<>''")}
    simdi = ayarlar.zaman_metni()
    eklenen, eslesmeyen, zaten, konumsuz = [], 0, 0, 0
    islenen: set[str] = set()

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for a, halka in ozellikler:
            try:
                om_id = str(int(float(a["ID"]))) if a.get("ID") not in (None, "") else ""
            except (TypeError, ValueError):
                om_id = ""
            loc =str(a.get("LOCATION_ID") or "").strip()
            serial = tell_index.get(om_id) or (loc if loc in bekleyen else None)
            if not serial:
                if loc in mevcut or om_id in mevcut_tell:
                    zaten += 1
                else:
                    eslesmeyen += 1
                continue
            if serial in islenen:
                continue
            if halka:
                try:
                    lon, lat, _alan, dis = _poligon(halka)
                except Exception:
                    lon = lat = None
                    dis = None
            else:
                lon = lat = None
                dis = None
            if lat is None or lon is None or (isinstance(lat, float) and math.isnan(lat)):
                try:
                    lat, lon = float(a.get("LAT")), float(a.get("LON"))
                except (TypeError, ValueError):
                    konumsuz += 1
                    continue
            b = bekleyen[serial]
            r = json.loads(b["veri"] or "{}")
            ilce = str(a.get("ILCE") or r.get("ilce_crm") or "").strip()
            if r.get("il") == "Yalova" and ilce in ("Merkez", "Yalova Merkez"):
                ilce = "Yalova Merkez"
            mahalle = mahalle_norm(a.get("MAHALLE"))
            site_adi = str(a.get("SITE_ADI") or "").strip()
            daire = kalite._sayi(a.get("KONUT_SAYISI")) if a.get("KONUT_SAYISI") is not None else None
            kat_om = kalite._sayi(a.get("KAT_ADEDI"))
            kat_tahmin = kalite.kat_tahmini_tek(daire)
            kat_kaynagi = "OneMap" if 1 <= kat_om <= 60 else "Tahmin"
            kat = kat_om if kat_kaynagi == "OneMap" else kat_tahmin
            grup = _site_grubu(conn, serial, ilce, mahalle, site_adi or r.get("site_adi_crm", ""),
                               str(a.get("TURU") or ""), lat, lon)
            bolge = _bolge_bul(conn, grup, lat, lon)
            kanit = kalite.kanit_onemap(a, daire=daire, kat_kaynagi=kat_kaynagi, kat_tahmin=kat_tahmin, ham={
                "location_id": r.get("location_id", ""), "tellcordia_id": r.get("tellcordia_id", ""),
                "kat": kat, "ad": r.get("ad", ""), "site_adi": site_adi, "crm_site_adi": r.get("site_adi_crm", "")})
            if r.get("ilce_crm") and ilce and r["ilce_crm"] != ilce:
                kanit["ilce_crm"] = r["ilce_crm"]
            conn.execute(
                "INSERT INTO bina (bina_serial, ad, site_adi, mahalle, ilce, il, cadde, sokak, kapi_no, lat, lon, "
                "  kat, daire, res_hp, aktif_res, firsat, sales_ready, bolge, obek, site_grup, location_id, "
                "  tellcordia_id, uavt_bina_kodu, blok_adi, bina_turu, toplam_hp, soho_hp, altyapi, teknoloji, "
                "  protokol_segment, crm_site_adi, kalite_kaynak, tur_tarihi, ekleme_kaynagi) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'tur')",
                (serial, r.get("ad", ""), site_adi, mahalle, ilce, r.get("il") or str(a.get("IL") or ""),
                 str(a.get("CADDE") or ""), str(a.get("SOKAK") or ""),
                 str(a.get("KAPI_NO") or r.get("kapi_no_crm") or ""), lat, lon, int(kat),
                 int(daire or r.get("res_hp") or 0), int(r.get("res_hp") or 0), int(r.get("aktif_res") or 0),
                 int(r.get("firsat") or 0), (r.get("sales_ready") or "")[:10] or None, bolge,
                 r.get("obek") or str(a.get("OBEK_ADI") or ""), grup, r.get("location_id", ""),
                 r.get("tellcordia_id", ""), str(a.get("UAVT_BINA_KODU") or ""),
                 str(a.get("BLOK_ADI") or r.get("blok_adi_crm") or ""), str(a.get("TURU") or ""),
                 int(r.get("toplam_hp") or 0), int(r.get("soho_hp") or 0), r.get("altyapi", ""),
                 str(a.get("TEKNOLOJI") or ""), r.get("protokol_segment", ""), r.get("site_adi_crm", ""),
                 json.dumps(kanit, ensure_ascii=False, separators=(",", ":")), simdi))
            conn.execute("INSERT INTO bina_durum (bina_serial, durum) VALUES (?, 'bekliyor') "
                         "ON CONFLICT(bina_serial) DO NOTHING", (serial,))
            if dis:
                conn.execute("INSERT INTO bina_geometri_ek (bina_serial, halka, zaman) VALUES (?,?,?) "
                             "ON CONFLICT(bina_serial) DO UPDATE SET halka=excluded.halka, zaman=excluded.zaman",
                             (serial, json.dumps(dis, separators=(",", ":")), simdi))
            conn.execute("UPDATE bina_bekleyen SET durum='eklendi', guncelleme=? WHERE bina_serial=?",
                         (simdi, serial))
            conn.execute("INSERT INTO bina_degisim (bina_serial, kaynak, alan, eski, yeni, zaman) "
                         "VALUES (?, 'onemap', 'eklendi', NULL, ?, ?)", (serial, f"bölge {bolge}", simdi))
            islenen.add(serial)
            eklenen.append({"bina_serial": serial, "ad": r.get("ad") or site_adi, "bolge": bolge,
                            "lat": round(lat, 6), "lon": round(lon, 6), "site_grup": grup})
        if eklenen:
            veri_kalitesi.yenile(conn, [e["bina_serial"] for e in eklenen])
            db.bina_surumu_arttir(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    kalan = conn.execute("SELECT COUNT(*) FROM bina_bekleyen WHERE durum='konum_bekliyor'").fetchone()[0]
    return {"eklenen": len(eklenen), "eslesmeyen": eslesmeyen, "zaten_haritada": zaten, "konumsuz": konumsuz,
            "hala_bekleyen": int(kalan), "binalar": eklenen[:200],
            "mesaj": f"{len(eklenen)} yeni bina haritaya eklendi; {kalan} bina hâlâ konum bekliyor."}

