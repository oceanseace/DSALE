"""Takip paneli sayıları (F11, F15, F17; spec §5.3.6). Kişisel veri yok; yalnız sayı ve kişi adı (ekip).

Hız hattı: rapordan sisteme, sistemde karara (15 dk ölçüsü), teknisyenin görmesi, BOSS'a işlenme, yol, saha,
kapanış ve uçtan uca. 15 dk ölçüsünün kapsamı (F17): yalnız ``acilis ≥ ayar.ilk_aktarim`` olan (sistem çalışırken
doğan) ve BOSS'ta atanmış olmayan işler — devralınan birikim 24 saat ölçüsüne girer, 15 dk ölçüsüne girmez.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from saha import ayarlar

from . import akis, aski, gorunum, kisi, kurallar, saklama, siralama, zaman

HIZ_ADIMLARI = [
    # (adım, başlangıç alanı, bitiş alanı, hedef dk, BTK hedefi dk)
    ("boss_sistem", "acilis", "gorulme_zamani", 30, 30),
    ("atama", "gorulme_zamani", "ilk_atama_zamani", 15, 15),
    ("teknik_gordu", "atama_zamani", "teknik_gordu", 5, 5),
    ("boss_islendi", "atama_zamani", "boss_islendi", 15, 15),
    ("yola_cikis", "atama_zamani", "yolda_zamani", 60, 45),
    ("yol", "yolda_zamani", "sahada_zamani", 60, 45),
    ("saha", "sahada_zamani", "cozum_zamani", 120, 90),
    ("kapanis_dogrulama", "cozum_zamani", "kapanis", 30, 30),
    ("uctan_uca", "acilis", "_bitis", 1440, 1440),
]


def _yuzdelik(degerler: list[float], p: float) -> float | None:
    if not degerler:
        return None
    s = sorted(degerler)
    i = (len(s) - 1) * p
    a, b = int(i), min(int(i) + 1, len(s) - 1)
    return round(s[a] + (s[b] - s[a]) * (i - a), 1)


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


def hiz_hatti(conn: sqlite3.Connection, simdi: dt.datetime, gun: int = 7) -> list[dict]:
    sinir = zaman.metin(simdi - dt.timedelta(days=gun))
    ilk = _ayar(conn, "ilk_aktarim")
    satirlar = [dict(r) for r in conn.execute(
        "SELECT * FROM is_emri WHERE gorulme_zamani >= ? OR COALESCE(cozum_zamani, kapanis, '') >= ?", (sinir, sinir))]
    out = []
    for adim, bas_alan, bit_alan, hedef, btk_hedef in HIZ_ADIMLARI:
        sureler, hedefte = [], 0
        for r in satirlar:
            if adim == "atama" and (not ilk or r["acilis"] < ilk or r["atama_kaynagi"] == "boss"):
                continue
            if adim == "kapanis_dogrulama" and r["kapanis_nedeni"] != "cozuldu_dogrulandi":
                continue
            bit = (r["cozum_zamani"] or r["kapanis"]) if bit_alan == "_bitis" else r[bit_alan]
            d = zaman.dakika(r[bas_alan], bit)
            if d is None or d < 0:
                continue
            if bit < sinir:
                continue
            sureler.append(d)
            if d <= (btk_hedef if r["serit"] == "BTK" else hedef):
                hedefte += 1
        out.append({"adim": adim, "medyan_dk": _yuzdelik(sureler, 0.5), "p90_dk": _yuzdelik(sureler, 0.9),
                    "n": len(sureler), "hedef_dk": hedef,
                    "hedefte_oran": round(hedefte / len(sureler), 3) if sureler else None})
    return out


def _uyum24(conn, simdi: dt.datetime, gun: int) -> dict:
    """Hedef süresinde biten oranı. Hedef işin kendi hedefidir (``son24``: 24 s; EK-12.1'de modem değişimi 7 gün …)."""
    sinir = zaman.metin(simdi - dt.timedelta(days=gun))
    gunler: dict[str, list[int]] = {}
    toplam = ic = 0
    yaklasik = False
    for r in conn.execute("SELECT acilis, son24, cozum_zamani, kapanis, kapanis_kesin FROM is_emri WHERE durum IN "
                          "('cozuldu','kapandi') AND COALESCE(cozum_zamani, kapanis) >= ?", (sinir,)):
        bit = r["cozum_zamani"] or r["kapanis"]
        d = zaman.dakika(r["acilis"], bit)
        if d is None:
            continue
        if not r["cozum_zamani"] and not r["kapanis_kesin"]:
            yaklasik = True
        hedefte = bit <= (r["son24"] or "")
        toplam += 1
        ic += 1 if hedefte else 0
        g = gunler.setdefault(bit[:10], [0, 0])
        g[0] += 1
        g[1] += 1 if hedefte else 0
    egim = [{"gun": g, "oran": round(v[1] / v[0], 3) if v[0] else None} for g, v in sorted(gunler.items())]
    return {"oran": round(ic / toplam, 3) if toplam else None, "n": toplam, "yaklasik": yaklasik, "egim": egim}


def _btk(conn, simdi: dt.datetime, gun: int) -> dict:
    sinir = zaman.metin(simdi - dt.timedelta(days=gun))
    satirlar = [dict(r) for r in conn.execute(
        "SELECT is_no, acilis, btk_hedef_saat, btk_hedef, cozum_zamani, kapanis, gorulme_zamani FROM is_emri "
        "WHERE serit='BTK' AND COALESCE(cozum_zamani, kapanis) >= ?", (sinir,))]
    aralik = aski.araliklar(conn, [r["is_no"] for r in satirlar])

    def oran(saat):
        n = ic = 0
        for r in satirlar:
            if r["btk_hedef_saat"] != saat:
                continue
            bit = zaman.oku(r["cozum_zamani"] or r["kapanis"])
            net = aski.hesap(aralik.get(r["is_no"]), r["acilis"], r["btk_hedef"], bit)
            n += 1
            ic += 1 if (net["btk_net_gecen_dk"] or 0) <= saat * 60 else 0
        return round(ic / n, 3) if n else None

    teshis_n = teshis_ic = 0
    for r in conn.execute(
            "SELECT e.gorulme_zamani, MIN(o.kayit_zamani) FROM is_emri e JOIN is_emri_olay o ON o.is_no = e.is_no "
            "AND o.tur IN ('teshis','arama') WHERE e.serit='BTK' AND e.gorulme_zamani >= ? GROUP BY e.is_no", (sinir,)):
        d = zaman.dakika(r[0], r[1])
        if d is not None:
            teshis_n += 1
            teshis_ic += 1 if d <= 45 else 0
    return {"tv6": oran(6), "baglanti12": oran(12), "teshis45": round(teshis_ic / teshis_n, 3) if teshis_n else None}


def _son_yedek(conn) -> str | None:
    try:
        from saha import db
        dizin = Path(db.db_yolu()).parent / "yedek"
        dosyalar = sorted(dizin.glob("saha-2*.db"), key=lambda p: p.stat().st_mtime)
        if dosyalar:
            return zaman.metin(dt.datetime.fromtimestamp(dosyalar[-1].stat().st_mtime).replace(microsecond=0))
    except OSError:
        pass
    return None


def takip(conn: sqlite3.Connection, simdi: dt.datetime | None = None, gun: int = 7, tam: bool = False) -> dict:
    simdi = simdi or zaman.simdi()
    gun = max(1, min(int(gun or 7), 90))
    sy = gorunum.sayac(conn, simdi)
    s = zaman.metin(simdi)
    en_yasli = conn.execute("SELECT MIN(acilis) FROM is_emri WHERE serit='BTK' AND durum NOT IN ('cozuldu','kapandi')"
                            ).fetchone()[0]
    seri = [{"zaman": r[0], "acik": r[1], "asan24": r[2]} for r in conn.execute(
        "SELECT zaman, acik, asan24 FROM takip_anlik WHERE zaman >= ? ORDER BY zaman",
        (zaman.metin(simdi - dt.timedelta(days=gun)),))]
    egim = None
    if len(seri) >= 2:
        g = max(1e-9, (zaman.oku(seri[-1]["zaman"]) - zaman.oku(seri[0]["zaman"])).total_seconds() / 86400)
        egim = round((seri[-1]["asan24"] - seri[0]["asan24"]) / g, 1) if g >= 0.5 else None
    obek_listesi = [{"id": o["id"], "ad": o["ad"], "acik": o["acik"], "geciken": o["geciken"], "btk": o["btk"],
                     "atanmamis": o["atanmamis"], "sahip": o["sahip"]}
                    for o in __import__("operasyon.v2.obek", fromlist=["liste"]).liste(conn)["obekler"]]
    bugun = simdi.strftime("%Y-%m-%d")
    teknikler = []
    for tid, t in sorted(kisi.teknikler(conn).items(), key=lambda x: x[1]["ad"]):
        r = conn.execute(
            "SELECT SUM(durum IN ('atandi','yolda','sahada')), SUM(substr(COALESCE(cozum_zamani,''),1,10)=?), "
            "SUM(durum IN ('yolda','sahada')), MIN(CASE WHEN substr(COALESCE(yolda_zamani,''),1,10)=? THEN yolda_zamani END) "
            "FROM is_emri WHERE atanan_id=?", (bugun, bugun, tid)).fetchone()
        evde_yok = conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE kullanici_id=? AND tur='durum' AND "
                                "yeni LIKE '%\"ulasilamadi\"%' AND substr(kayit_zamani,1,10)=?", (tid, bugun)).fetchone()[0]
        teknikler.append({"id": tid, "ad": t["ad"], "atanan": r[0] or 0, "biten": r[1] or 0, "evde_yok": evde_yok,
                          "yolda_sahada": r[2] or 0, "ilk_is": r[3]})
    son_goc = None
    try:
        son_goc = (json.loads(_ayar(conn, "son_goc", "") or "{}") or {}).get("zaman")
    except (ValueError, AttributeError):
        son_goc = None
    son = gorunum.son_aktarim(conn, simdi)
    return {
        "sunucu_zamani": s,
        "hikaye": gorunum.hikaye(sy, None),
        "manset": {"acik": sy["acik"], "asan24": sy["asan24"], "atanmamis": sy["atanmamis"],
                   "en_eski_atanmamis_dk": sy["en_eski_atanmamis_dk"], "btk48": sy["btk48"],
                   "en_yasli_btk_s": int((simdi - zaman.oku(en_yasli)).total_seconds() // 3600) if en_yasli else None,
                   "kontrol": sy["kontrol"]},
        "uyum24": _uyum24(conn, simdi, gun),
        "btk": _btk(conn, simdi, gun),
        "birikim": {"asan24": sy["asan24"], "egim_gun": egim, "seri": seri},
        "kapasite": {k: v for k, v in siralama.mod(conn, simdi).items() if k != "teknik_sayisi"},
        "hiz_hatti": hiz_hatti(conn, simdi, gun),
        "hijyen": {"cozuldu_boss_acik": conn.execute("SELECT COUNT(*) FROM is_emri WHERE boss_kapanmadi=1 AND "
                                                     "durum='cozuldu'").fetchone()[0],
                   "askida_uyanmasiz": sy["askida_uyanmasiz"], "boss_islenecek": sy["boss_bekleyen"],
                   "rapor_yas_dk": son["yas_dk"] if son else None, "askida_btk_durdu": sy["askida_btk_durdu"],
                   **_ek12_hijyen(conn, simdi)},
        "obekler": obek_listesi,
        "teknikler": teknikler,
        "sistem": {"son_rapor": son["zaman"] if son else None, "son_yedek": _son_yedek(conn), "son_goc": son_goc,
                   "saklama_metni": saklama.metin(conn)},
    }


def _ek12_hijyen(conn, simdi: dt.datetime) -> dict:
    """EK-12: alarm günündeki BTK şikâyetleri, genel arıza (kesinti) askısı, öncelikli (kanal şikâyeti) açık iş."""
    acik = conn.execute("SELECT is_no, task_adi, durum, askida_neden FROM is_emri WHERE durum NOT IN "
                        "('cozuldu','kapandi')").fetchall()
    btk = akis.btk_bilgileri(conn, [r["is_no"] for r in acik])
    kural, tatil = kurallar.oku(conn, "btk_sikayet"), kurallar.oku(conn, "resmi_tatiller")
    alarm = sum(1 for no, b in btk.items() if b.get("tarih") and not b.get("tcs")
                and (kurallar.btk_sikayet_durumu(b, None, simdi, kural, tatil) or {}).get("alarm"))
    oncelik = kurallar.oku(conn, "oncelikli_isler")
    return {"btk_alarm": alarm,
            "genel_ariza": sum(1 for r in acik if r["durum"] == "askida" and str(r["askida_neden"] or "").startswith("Genel arıza")),
            "oncelikli": sum(1 for r in acik if kurallar.oncelik(oncelik, r["task_adi"]))}


def satis(conn: sqlite3.Connection, simdi: dt.datetime | None = None, gun: int = 7) -> dict:
    """Satış bölümü (F15). Sayılar ``/api/ozet/gun`` ile aynı tanımdır: iptal edilen ziyaret sayılmaz,
    "satış" = satışla biten ziyaret, temas = ``ayarlar.TEMAS_SONUCLARI``."""
    simdi = simdi or zaman.simdi()
    bugun = simdi.strftime("%Y-%m-%d")
    hafta_bas = (simdi - dt.timedelta(days=max(1, int(gun or 7)) - 1)).strftime("%Y-%m-%d")
    temas = ",".join(f"'{x}'" for x in ayarlar.TEMAS_SONUCLARI)
    satiscilar = conn.execute("SELECT id, ad, bolge, aktif FROM kullanici WHERE rol='satisci' ORDER BY bolge, id").fetchall()

    def say(kid, bas, bit):
        r = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(sonuc IN ({temas})),0), COALESCE(SUM(sonuc='satis'),0) "
                         "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10) BETWEEN ? AND ?",
                         (kid, bas, bit)).fetchone()
        return int(r[0]), int(r[1]), int(r[2])

    satirlar = []
    top_b = [0, 0, 0]
    top_h = [0, 0, 0]
    aktif = 0
    for s in satiscilar:
        b = say(s["id"], bugun, bugun)
        h = say(s["id"], hafta_bas, bugun)
        aktif += 1 if b[0] else 0
        for i in range(3):
            top_b[i] += b[i]
            top_h[i] += h[i]
        satirlar.append({"id": s["id"], "ad": s["ad"], "bolge": s["bolge"], "bugun_ziyaret": b[0], "bugun_satis": b[2],
                         "hafta_ziyaret": h[0], "hafta_satis": h[2],
                         "donusum": round(h[2] / h[0], 4) if h[0] else None})
    hedef = _ayar(conn, "haftalik_satis_hedefi")
    try:
        hedef = int(hedef) if hedef else None
    except ValueError:
        hedef = None
    demo = _ayar(conn, "demo")
    try:
        altyapi = conn.execute(
            "SELECT COUNT(DISTINCT t.bina_serial) FROM ticket t JOIN ziyaret z ON z.bina_serial = t.bina_serial "
            "WHERE t.durum='ÇÖZÜLDÜ' AND z.sonuc='satis' AND z.iptal=0 AND z.zaman >= COALESCE(t.kapanis, t.guncelleme)"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        altyapi = 0
    return {"demo_dahil": bool(demo and str(demo) not in ("0", "", "false")),
            "bugun": {"ziyaret": top_b[0], "temas": top_b[1], "satis": top_b[2], "aktif_satisci": aktif,
                      "toplam_satisci": len(satiscilar)},
            "hafta": {"ziyaret": top_h[0], "temas": top_h[1], "satis": top_h[2], "hedef": hedef,
                      "ilerleme": round(top_h[2] / hedef, 3) if hedef else None},
            "huni": {"ziyaret": top_h[0], "temas": top_h[1], "satis": top_h[2]},
            "satiscilar": satirlar, "altyapisi_cozulen_bina": int(altyapi or 0)}


def erisim(conn: sqlite3.Connection, simdi: dt.datetime | None = None, gun: int = 7) -> dict:
    simdi = simdi or zaman.simdi()
    sinir = (simdi - dt.timedelta(days=max(1, int(gun or 7)) - 1)).strftime("%Y-%m-%d")
    return {"gunler": [{"gun": r[0], "kisi": r[1], "eylem": r[2], "adet": r[3]} for r in conn.execute(
        "SELECT gun, kullanici_ad, eylem, SUM(COALESCE(adet, 1)) FROM erisim_kaydi WHERE gun >= ? "
        "GROUP BY gun, kullanici_id, eylem ORDER BY gun DESC, kullanici_ad", (sinir,))]}


def yonetim(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM yonetim_kaydi ORDER BY id DESC LIMIT ?",
                                          (max(1, min(int(limit or 100), 1000)),))]
