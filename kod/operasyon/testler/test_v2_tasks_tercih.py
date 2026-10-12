"""TASKS/MAP kişisel tercihleri sunucuda (tasks_tercih.py): düzen, adlı düzenler, ortak süzgeç, unvan varsayılanı."""
from __future__ import annotations

import pytest

from operasyon.v2 import tasks_tercih
from operasyon.v2.hatalar import V2Hata

DUZEN = {"gorunen": ["task", "ad", "ek:city"], "gen": {"task": 120}, "yakinlik": 90, "harfler": False,
         "sira": {"id": "gelis", "yon": -1}}
SUZGEC = {"sutunlar": {"tur": {"degerler": ["TV Kurulum"], "metin": ""}}, "arama": "nilüfer", "gorunum_id": None,
          "tur": {"kip": "haric", "degerler": ["Nakil"]}, "tarih": {"kip": "hepsi", "gun": "", "bas": "", "bit": ""}}


def _unvan(conn, ad="Saha Operasyon") -> int:
    cur = conn.execute("INSERT INTO unvan (ad, ad_k, aktif, sira, olusturma) VALUES (?,?,1,0,'2026-10-01 09:00:00')",
                       (ad, ad.casefold()))
    conn.commit()
    return cur.lastrowid


def test_bos_baslar_fabrika_tv_ekibi_var(conn, kim):
    t = tasks_tercih.oku(conn, kim("operasyon"))
    assert t["etkin"] is None and t["duzenler"] == [] and t["suzgec"] is None
    tv = next(f for f in t["fabrika"] if f["ad"] == "TV ekibi")
    assert {"task", "musteri_no", "ad", "tel", "tur", "randevu", "gelis"} <= set(tv["duzen"]["gorunen"])


def test_kisi_basina_yazilir_ve_okunur(conn, kim):
    op, yon = kim("operasyon"), kim("yonetici")
    tasks_tercih.yaz(conn, op, {"etkin": {**DUZEN, "ad": None}, "suzgec": SUZGEC,
                                "duzenler": [{"ad": "Superbox", "duzen": DUZEN}, {"ad": "Fiber kurulum", "duzen": {}}]})
    t = tasks_tercih.oku(conn, op)
    assert t["etkin"]["gorunen"] == DUZEN["gorunen"] and t["suzgec"] == SUZGEC
    assert [d["ad"] for d in t["duzenler"]] == ["Superbox", "Fiber kurulum"]
    assert tasks_tercih.oku(conn, yon)["etkin"] is None               # başkasınınki görünmez
    tasks_tercih.yaz(conn, op, {"suzgec": None})                       # yalnız verilen anahtar değişir
    t = tasks_tercih.oku(conn, op)
    assert t["suzgec"] is None and t["etkin"]["yakinlik"] == 90 and len(t["duzenler"]) == 2


@pytest.mark.parametrize("duzenler, kod", [
    ([{"ad": "A", "duzen": {}}, {"ad": "a", "duzen": {}}], "ad_var"),
    ([{"ad": "TV ekibi", "duzen": {}}], "ad_var"),
    ([{"ad": "", "duzen": {}}], "alan_eksik"),
    ([{"ad": "X", "duzen": {"gorunen": "task"}}], "alan_eksik"),
    ([{"ad": f"D{i}", "duzen": {}} for i in range(31)], "cok_buyuk"),
])
def test_duzen_denetimi(conn, kim, duzenler, kod):
    with pytest.raises(V2Hata) as e:
        tasks_tercih.yaz(conn, kim("operasyon"), {"duzenler": duzenler})
    assert e.value.kod == kod


def test_cok_buyuk_suzgec_reddedilir(conn, kim):
    with pytest.raises(V2Hata) as e:
        tasks_tercih.yaz(conn, kim("operasyon"), {"suzgec": {"arama": "x" * 70_000}})
    assert e.value.kod == "cok_buyuk"


def test_unvan_varsayilani_yalniz_administrator(conn, kim, kisi):
    uv = _unvan(conn)
    conn.execute("UPDATE kullanici SET unvan_id=? WHERE id=?", (uv, kisi["operasyon"]))
    conn.commit()
    op = kim("operasyon")
    with pytest.raises(V2Hata) as e:
        tasks_tercih.unvan_yaz(conn, op, uv, DUZEN)
    assert e.value.durum == 403
    adm = {**kim("yonetici"), "administrator": True}
    y = tasks_tercih.unvan_yaz(conn, adm, uv, DUZEN)
    assert next(u for u in y["unvanlar"] if u["id"] == uv)["duzen"] == DUZEN
    t = tasks_tercih.oku(conn, op)                                     # unvandaki kişi bununla başlar
    assert t["unvan"] == {"id": uv, "ad": "Saha Operasyon", "duzen": DUZEN} and "unvanlar" not in t
    tasks_tercih.unvan_yaz(conn, adm, uv, None)
    assert tasks_tercih.oku(conn, op)["unvan"]["duzen"] is None
    with pytest.raises(V2Hata):
        tasks_tercih.unvan_yaz(conn, adm, 999999, DUZEN)


def test_uclar(istemci, jeton, kisi):
    h = jeton(kisi["operasyon"])
    r = istemci.put("/api/isler/tercih", headers=h, json={"etkin": DUZEN, "suzgec": SUZGEC})
    assert r.status_code == 200 and r.json()["etkin"]["gorunen"] == DUZEN["gorunen"]
    assert istemci.get("/api/isler/tercih", headers=h).json()["suzgec"] == SUZGEC
    r = istemci.put("/api/isler/tercih/unvan", headers=h, json={"unvan_id": 1, "duzen": DUZEN})
    assert r.status_code == 403
    assert istemci.get("/api/isler/tercih", headers=jeton(kisi["satis"])).status_code == 403


def test_sutun_suzgeci_gizle_kipi_korunur(conn, kim):
    """Sütun süzgecinin "Seçilenleri gizle" kipi (kip: haric) ortak süzgeçte olduğu gibi saklanır."""
    op = kim("operasyon")
    s = {**SUZGEC, "sutunlar": {"tur": {"degerler": ["TV Kurulum", "Fiber Kurulum"], "metin": "", "kip": "haric"}}}
    tasks_tercih.yaz(conn, op, {"suzgec": s})
    assert tasks_tercih.oku(conn, op)["suzgec"]["sutunlar"]["tur"]["kip"] == "haric"


def test_kisisel_ayarlar_varsayilan_denetim_ve_kisi_basina(conn, kim):
    op, yon = kim("operasyon"), kim("yonetici")
    assert tasks_tercih.oku(conn, op)["ayarlar"] == {"map_durum_cubugu": True, "map_lejant": True, "map_tazeleme_sn": 15,
                                                     "suzgec_soluk_goster": False}
    tasks_tercih.yaz(conn, op, {"ayarlar": {"map_durum_cubugu": False, "map_tazeleme_sn": 60, "bilinmeyen": 1,
                                            "suzgec_soluk_goster": True}})
    a = tasks_tercih.oku(conn, op)["ayarlar"]
    assert a == {"map_durum_cubugu": False, "map_lejant": True, "map_tazeleme_sn": 60, "suzgec_soluk_goster": True}
    tasks_tercih.yaz(conn, op, {"ayarlar": {"suzgec_soluk_goster": "evet"}})              # bool değilse varsayılan
    assert tasks_tercih.oku(conn, op)["ayarlar"]["suzgec_soluk_goster"] is False
    tasks_tercih.yaz(conn, op, {"ayarlar": {"map_tazeleme_sn": 7, "map_lejant": "evet"}})   # geçersiz değerler atılır
    assert tasks_tercih.oku(conn, op)["ayarlar"]["map_tazeleme_sn"] == 15
    assert tasks_tercih.oku(conn, yon)["ayarlar"]["map_durum_cubugu"] is True             # başkasınınki ayrı
    tasks_tercih.yaz(conn, op, {"suzgec": SUZGEC})                                          # ayarlar değişmez
    with pytest.raises(V2Hata):
        tasks_tercih.yaz(conn, op, {"ayarlar": "x"})
