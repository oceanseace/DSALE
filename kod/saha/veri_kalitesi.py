"""Veri kalitesi — ``dsale/kalite.py`` kurallarını veritabanındaki binalara uygular.

Kurallar tek yerde (dsale/kalite.py) yazılıdır; burada yalnız çalıştırılır ve
sonuç binanın ``kalite`` sütununa JSON olarak yazılır. Bir binanın HP'si ya da
abonesi değiştiğinde (tur raporu) o binanın bayrakları yeniden hesaplanır.

Güvenli düzeltmeler (sıfırı düşen Location Id, bilimsel yazıma dönmüş Tellcordia
ID, 'Null' ad, bariz yanlış kat) doğrudan binanın alanına yazılır; orijinal değer
hem bayrağın ``duzeltme.eski`` alanında hem de ``kalite_kaynak.ham`` içinde durur.
RES HP ve aboneye hiçbir koşulda dokunulmaz.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable

from . import ayarlar, db

_gunluk = logging.getLogger("saha.kalite")

_ALANLAR = ("bina_serial, ad, site_adi, crm_site_adi, location_id, tellcordia_id, kat, daire, "
            "res_hp, aktif_res, lat, lon, ilce, kalite, kalite_kaynak")
# Düzeltmenin dokunabileceği alanlar (başka bir alan gelirse yok sayılır).
DUZELTILEBILIR = ("location_id", "tellcordia_id", "kat", "ad", "site_adi", "crm_site_adi")
_HAM_ALANLAR = ("location_id", "tellcordia_id", "kat", "ad", "site_adi", "crm_site_adi")


def _kurallar():
    # dsale paketi repo kökünde; sunucu kökten çalıştırıldığı için içe aktarılabilir.
    from dsale import kalite

    return kalite


def kanitlari_yaz(conn: sqlite3.Connection, kanitlar: dict[str, dict], sadece_bos: bool = False) -> int:
    """Kanıtları binalara yazar. ``sadece_bos``: yalnız kanıtı olmayan binalar."""
    kosul = " AND kalite_kaynak IS NULL" if sadece_bos else ""
    imlec = conn.executemany(
        f"UPDATE bina SET kalite_kaynak=? WHERE bina_serial=?{kosul}",
        [(json.dumps(k, ensure_ascii=False, separators=(",", ":")), s) for s, k in kanitlar.items()],
    )
    return imlec.rowcount if imlec.rowcount is not None else 0


def _parcalar(seriler: list[str], boy: int = 800):
    for i in range(0, len(seriler), boy):
        yield seriler[i:i + boy]


def yenile(conn: sqlite3.Connection, seriler: Iterable[str] | None = None) -> dict:
    """Bayrakları yeniden hesaplar, güvenli düzeltmeleri uygular. İşlemi çağıran commit eder.

    Aynı binada iki kez çalıştırmak aynı sonucu verir (düzeltmeler ``ham``
    değerlerden hesaplanır, düzeltilmiş değerden değil).
    """
    kalite = _kurallar()
    if seriler is None:
        satirlar = conn.execute(f"SELECT {_ALANLAR} FROM bina").fetchall()
    else:
        liste = list(dict.fromkeys(seriler))
        satirlar = []
        for p in _parcalar(liste):
            satirlar += conn.execute(
                f"SELECT {_ALANLAR} FROM bina WHERE bina_serial IN ({','.join('?' * len(p))})",
                tuple(p)).fetchall()

    bayrakli = duzeltilen = kunye_degisti = 0
    kalite_yaz, kanit_yaz, alan_yaz, iz_yaz = [], [], {}, []
    for s in satirlar:
        b = dict(s)
        try:
            kanit = json.loads(b.get("kalite_kaynak") or "null") or {}
        except ValueError:
            kanit = {}
        if "ham" not in kanit:
            # Kanıtı olmayan (sonradan eklenmiş ya da eski) bina: bugünkü değerler "ham" kabul
            # edilir ki bir sonraki çalıştırmada düzeltme kendi üstüne binmesin.
            kanit["ham"] = {a: b.get(a) for a in _HAM_ALANLAR}
            kanit_yaz.append((json.dumps(kanit, ensure_ascii=False, separators=(",", ":")), b["bina_serial"]))
        bayraklar, duzelt = kalite.denetle(b, kanit)
        for alan, yeni in duzelt.items():
            if alan in DUZELTILEBILIR and b.get(alan) != yeni:
                alan_yaz.setdefault(alan, []).append((yeni, b["bina_serial"]))
                # Her güvenli düzeltmenin izi (spec §8.2 WP-A): binanın künye geçmişinde görünür.
                iz_yaz.append((b["bina_serial"], alan, None if b.get(alan) is None else str(b.get(alan)),
                               None if yeni is None else str(yeni)))
                kunye_degisti += 1
        if bayraklar:
            bayrakli += 1
        if any(f.get("duzeltme") for f in bayraklar):
            duzeltilen += 1
        metin = json.dumps(bayraklar, ensure_ascii=False, separators=(",", ":"))
        if metin != b.get("kalite"):
            kalite_yaz.append((metin, b["bina_serial"]))

    if kanit_yaz:
        conn.executemany("UPDATE bina SET kalite_kaynak=? WHERE bina_serial=?", kanit_yaz)
    for alan, degerler in alan_yaz.items():
        conn.executemany(f"UPDATE bina SET {alan}=? WHERE bina_serial=?", degerler)
    if iz_yaz:
        zaman = ayarlar.zaman_metni()
        conn.executemany("INSERT INTO bina_degisim (bina_serial, kaynak, alan, eski, yeni, zaman) "
                         "VALUES (?,'kalite',?,?,?,?)", [(*iz, zaman) for iz in iz_yaz])
    if kalite_yaz:
        conn.executemany("UPDATE bina SET kalite=? WHERE bina_serial=?", kalite_yaz)
    if kunye_degisti:
        db.bina_surumu_arttir(conn)       # haritadaki ad/Location Id tazelensin
    return {"bina": len(satirlar), "bayrakli": bayrakli, "duzeltilen": duzeltilen,
            "yazilan": len(kalite_yaz), "alan_degisikligi": kunye_degisti}


def hazirla(conn: sqlite3.Connection, zorla: bool = False) -> dict | None:
    """Kalite hiç hesaplanmamış binalar varsa kanıtları yükler ve hesaplar (commit eder).

    Sunucu açılışında çağrılır: eski bir veritabanı ilk açılışta bir kez (birkaç
    saniye) hesaplanır, sonrasında bu çağrı tek bir COUNT sorgusudur.
    ``zorla``: bütün binaların kanıtını kaynaktan tazeler (``saha.kur`` kullanır).
    """
    try:
        eksik = conn.execute("SELECT COUNT(*) FROM bina WHERE kalite IS NULL").fetchone()[0]
    except sqlite3.Error:
        return None                       # sütun yok: göçler henüz çalışmamış
    if not eksik and not zorla:
        return None
    try:
        kanit = _kurallar().kanitlar()
    except Exception as exc:  # kaynak dosya yoksa kanıtsız (yalnız satırdan) çalışır
        _gunluk.warning("Kalite kanıtları okunamadı (%s); yalnız bina satırıyla denetleniyor.", exc)
        kanit = {}
    kanitlari_yaz(conn, kanit, sadece_bos=not zorla)
    if zorla:
        sonuc = yenile(conn)
    else:
        seriler = [r[0] for r in conn.execute("SELECT bina_serial FROM bina WHERE kalite IS NULL")]
        sonuc = yenile(conn, seriler)
    conn.commit()
    return sonuc


def bayraklar(metin: str | None) -> list[dict]:
    """Kart için: sütundaki JSON → [{kural, mesaj, seviye, duzeltme?}]."""
    if not metin:
        return []
    try:
        veri = json.loads(metin)
    except ValueError:
        return []
    return veri if isinstance(veri, list) else []


# ----------------------------------------------------------------------------- özet / liste
def ozet(conn: sqlite3.Connection, bolge: int | None = None) -> dict:
    kalite = _kurallar()
    kosul, deger = "", ()
    if bolge is not None:
        kosul, deger = " AND b.bolge=?", (int(bolge),)
    sayilar = {
        r["kural"]: (int(r["adet"]), int(r["duzeltilen"] or 0))
        for r in conn.execute(
            "SELECT json_extract(j.value,'$.kural') AS kural, COUNT(*) AS adet, "
            "       SUM(CASE WHEN json_extract(j.value,'$.duzeltme') IS NOT NULL THEN 1 ELSE 0 END) "
            "           AS duzeltilen "
            "FROM bina b, json_each(b.kalite) j WHERE b.kalite IS NOT NULL" + kosul +
            " GROUP BY kural", deger).fetchall()
    }
    genel = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "       SUM(CASE WHEN b.kalite IS NOT NULL AND b.kalite<>'[]' THEN 1 ELSE 0 END) AS bayrakli, "
        "       SUM(CASE WHEN b.kalite IS NULL THEN 1 ELSE 0 END) AS hesaplanmamis "
        "FROM bina b WHERE 1=1" + kosul, deger).fetchone()
    kurallar = []
    for kod, tanim in kalite.KURALLAR.items():
        adet, duz = sayilar.get(kod, (0, 0))
        kurallar.append({"kural": kod, "ad": tanim["ad"], "seviye": tanim["seviye"],
                         "aciklama": tanim["aciklama"], "duzeltir": tanim["duzeltir"],
                         "adet": adet, "duzeltilen": duz})
    return {
        "toplam_bina": int(genel["toplam"] or 0),
        "bayrakli_bina": int(genel["bayrakli"] or 0),
        "hesaplanmamis": int(genel["hesaplanmamis"] or 0),
        "kural_surumu": kalite.KURAL_SURUMU,
        "kurallar": kurallar,
    }


def liste(conn: sqlite3.Connection, kural: str | None, bolge: int | None, seviye: str | None,
          limit: int, offset: int) -> dict:
    kosul, deger = ["b.kalite IS NOT NULL", "b.kalite<>'[]'"], []
    if kural:
        kosul.append("EXISTS (SELECT 1 FROM json_each(b.kalite) j "
                     "WHERE json_extract(j.value,'$.kural')=?)")
        deger.append(kural)
    if seviye:
        kosul.append("EXISTS (SELECT 1 FROM json_each(b.kalite) j "
                     "WHERE json_extract(j.value,'$.seviye')=?)")
        deger.append(seviye)
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    nerede = " WHERE " + " AND ".join(kosul)
    toplam = conn.execute(f"SELECT COUNT(*) FROM bina b{nerede}", tuple(deger)).fetchone()[0]
    satirlar = conn.execute(
        "SELECT b.bina_serial, b.ad, b.site_adi, b.sokak, b.kapi_no, b.mahalle, b.ilce, b.bolge, "
        "       b.lat, b.lon, b.location_id, b.tellcordia_id, b.res_hp, b.aktif_res, b.kat, b.daire, "
        f"      b.kalite FROM bina b{nerede} ORDER BY b.bolge, b.ilce, b.mahalle, b.bina_serial "
        "LIMIT ? OFFSET ?", tuple(deger) + (limit, offset)).fetchall()
    return {"toplam": int(toplam), "limit": limit, "offset": offset,
            "binalar": [{**{k: s[k] for k in s.keys() if k != "kalite"},
                         "kalite": bayraklar(s["kalite"])} for s in satirlar]}
