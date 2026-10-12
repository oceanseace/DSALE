"""İşler tablosu: "Bizim durum" (operasyonun kendi takip etiketi) — uç, izin, sürüm, olay, liste alanı."""
from __future__ import annotations

from operasyon.testler import yardim as y
from operasyon.v2.api import ROTA_IZNI


def test_rota_izni():
    assert ROTA_IZNI[("POST", "/api/isler/{is_no}/bizim-durum")] == "is.duzenle"


def test_bizim_durum_yaz_ve_listede(istemci, jeton, v2db, conn, kisi):
    y.aktar(v2db, [y.satir(1), y.satir(2)])
    no, surum, durum = conn.execute("SELECT is_no, surum, durum FROM is_emri ORDER BY is_no").fetchone()
    h = jeton(kisi["operasyon"])
    r = istemci.post(f"/api/isler/{no}/bizim-durum", headers=h, json={"deger": "Randevulu", "surum": surum})
    assert r.status_code == 200, r.text
    assert r.json()["bizim_durum"] == "Randevulu" and r.json()["durum"] == durum     # iş akışı değişmez (engel değil)
    x = next(i for i in istemci.get("/api/isler", headers=h).json()["isler"] if i["is_no"] == no)
    assert x["bizim_durum"] == "Randevulu" and "boss_durum" in x and "satis_kanali" in x
    assert conn.execute("SELECT COUNT(*) FROM is_emri_olay WHERE is_no=? AND tur='bizim_durum'", (no,)).fetchone()[0] == 1
    # eski sürümle yazılamaz
    r = istemci.post(f"/api/isler/{no}/bizim-durum", headers=h, json={"deger": "Kuruldu", "surum": surum})
    assert r.status_code == 409
    # tanınmayan değer
    r = istemci.post(f"/api/isler/{no}/bizim-durum", headers=h, json={"deger": "Uydurma"})
    assert r.status_code in (400, 422)
    # temizle
    r = istemci.post(f"/api/isler/{no}/bizim-durum", headers=h, json={"deger": None})
    assert r.status_code == 200 and r.json()["bizim_durum"] is None


def test_teknik_yazamaz(istemci, jeton, v2db, conn, kisi):
    y.aktar(v2db, [y.satir(1)])
    no = conn.execute("SELECT is_no FROM is_emri").fetchone()[0]
    r = istemci.post(f"/api/isler/{no}/bizim-durum", headers=jeton(kisi["teknik1"]), json={"deger": "İptal"})
    assert r.status_code in (403, 404)
