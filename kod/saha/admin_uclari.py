"""Administrator uçları: unvan kataloğu, unvan × yetkinlik matrisi, kişinin unvanı / takım liderliği / ek yetkinliği.

URL'ler: /api/admin/yetkinlikler · /api/admin/unvanlar* · /api/admin/matris · /api/admin/kisiler*

Kim ne yapar:
  * Administrator (``yetkinlik.yonet``; yalnız turkcell.json'daki telefon) — hepsi.
  * Kişi yönetimi (İK, ``ekip.yonet``) — kataloğu ve matrisi OKUR; kişiye unvan ve takım lideri atar.
    Unvan açamaz/adını değiştiremez, matrisi yazamaz, ek yetkinlik veremez, Administrator'ı düzenleyemez,
    kendi unvanını değiştiremez.

``saha/api.py`` bu modülü ``_v2_bagla`` ile yükler; izinler aşağıdaki ``ROTA_IZNI``'dan tabloya eklenir.
Her değişiklik ``yonetim_kaydi``'na yazılır (yalnız id ve sayılar).
"""
from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from . import ayarlar, db, yetki
from .api_ortak import _kullanici_kart
from .yetki import baglanti, hata, izin

yonlendirici = APIRouter()

_OKU = ("yetkinlik.yonet", "ekip.yonet")
ROTA_IZNI: dict[tuple[str, str], str | tuple[str, ...]] = {
    ("GET", "/api/admin/yetkinlikler"): _OKU,
    ("GET", "/api/admin/unvanlar"): _OKU,
    ("POST", "/api/admin/unvanlar"): "yetkinlik.yonet",
    ("PATCH", "/api/admin/unvanlar/{unvan_id}"): "yetkinlik.yonet",
    ("GET", "/api/admin/matris"): _OKU,
    ("PUT", "/api/admin/matris"): "yetkinlik.yonet",
    ("GET", "/api/admin/kisiler"): _OKU,
    ("PATCH", "/api/admin/kisiler/{kullanici_id}"): _OKU,
}


def _tablolar_hazir(conn: sqlite3.Connection) -> None:
    if not db.tablo_var(conn, "unvan"):
        raise hata(503, "Veritabanı güncellenmemiş (unvan kataloğu yok). Sunucuyu yeniden başlatın.", "hazir_degil")


def _katalog() -> list[dict]:
    return [{"kod": kod, "ad": y["ad"], "aciklama": y["aciklama"], "izinler": list(y["izinler"]),
             "gorev": yetki._PAKET_GOREVI.get(kod)} for kod, y in yetki.YETKINLIKLER.items()]


def _unvan_listesi(conn: sqlite3.Connection) -> list[dict]:
    matris: dict[int, list[str]] = {}
    for uid, y in conn.execute("SELECT unvan_id, yetkinlik FROM unvan_yetkinlik").fetchall():
        matris.setdefault(uid, []).append(y)
    sayilar = {r[0]: (int(r[1]), int(r[2])) for r in conn.execute(
        "SELECT unvan_id, COUNT(*), SUM(CASE WHEN aktif=1 THEN 1 ELSE 0 END) FROM kullanici "
        "WHERE unvan_id IS NOT NULL GROUP BY unvan_id").fetchall()}
    return [{"id": r["id"], "ad": r["ad"], "aktif": bool(r["aktif"]), "sira": r["sira"],
             "yetkinlikler": yetki.yetkinlik_sirala(matris.get(r["id"], [])),
             "kisi_sayisi": sayilar.get(r["id"], (0, 0))[0], "aktif_kisi_sayisi": sayilar.get(r["id"], (0, 0))[1]}
            for r in conn.execute("SELECT * FROM unvan ORDER BY aktif DESC, sira, id").fetchall()]


@yonlendirici.get("/api/admin/yetkinlikler")
def yetkinlik_katalogu(k: dict = Depends(izin(*_OKU)), conn: sqlite3.Connection = Depends(baglanti)):
    return {"yetkinlikler": _katalog(), "takim_lideri": yetki.takim_lideri_yetkinlikleri(conn)}


@yonlendirici.get("/api/admin/unvanlar")
def unvan_listesi(k: dict = Depends(izin(*_OKU)), conn: sqlite3.Connection = Depends(baglanti)):
    _tablolar_hazir(conn)
    return {"unvanlar": _unvan_listesi(conn), "duzenleyebilir": yetki.izinli(k, "yetkinlik.yonet")}


class UnvanGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ad: str = Field(min_length=2, max_length=120)
    yetkinlikler: list[str] = Field(default_factory=list, max_length=20)


class UnvanDegisikligi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ad: str | None = Field(default=None, min_length=2, max_length=120)
    aktif: bool | None = None
    sira: int | None = Field(default=None, ge=0, le=100_000)


def _yetkinlik_dogrula(kodlar: list[str]) -> list[str]:
    bilinmeyen = [y for y in kodlar if y not in yetki.YETKINLIKLER]
    if bilinmeyen:
        raise hata(400, f"Bilinmeyen yetkinlik: {', '.join(bilinmeyen)}", "yetkinlik_gecersiz")
    return yetki.yetkinlik_sirala(kodlar)


def _ad_temizle(ad: str) -> tuple[str, str]:
    temiz = " ".join(ad.split())
    anahtar = yetki.unvan_anahtari(temiz)
    if len(anahtar) < 2:
        raise hata(400, "Unvan adı en az iki harf olmalı.", "unvan_gecersiz")
    return temiz, anahtar


def _onbellekleri_tazele(conn: sqlite3.Connection, unvan_ids: list[int] | None = None) -> int:
    """Matris/unvan değişince ilgili kişilerin türetilmiş görev önbelleği (rol + kullanici_gorev)."""
    if unvan_ids is None:
        satirlar = conn.execute("SELECT id FROM kullanici WHERE yetki_modeli=1").fetchall()
    elif not unvan_ids:
        return 0
    else:
        satirlar = conn.execute(f"SELECT id FROM kullanici WHERE yetki_modeli=1 AND unvan_id IN "
                                f"({','.join('?' * len(unvan_ids))})", unvan_ids).fetchall()
    for (kid,) in satirlar:
        yetki.gorev_onbellegi_yaz(conn, kid)
    return len(satirlar)


@yonlendirici.post("/api/admin/unvanlar")
def unvan_ekle(girdi: UnvanGirdi, k: dict = Depends(izin("yetkinlik.yonet")),
               conn: sqlite3.Connection = Depends(baglanti)):
    """Yeni unvan ("EÇM - Finans - Takım Lideri" gibi), isteğe bağlı yetkinlikleriyle."""
    _tablolar_hazir(conn)
    ad, anahtar = _ad_temizle(girdi.ad)
    kodlar = _yetkinlik_dogrula(girdi.yetkinlikler)
    if conn.execute("SELECT 1 FROM unvan WHERE ad_k=?", (anahtar,)).fetchone():
        raise hata(409, "Bu unvan zaten var.", "unvan_var")
    sira = int(conn.execute("SELECT COALESCE(MAX(sira), 0) FROM unvan").fetchone()[0]) + 10
    uid = int(conn.execute("INSERT INTO unvan (ad, ad_k, aktif, sira, olusturma) VALUES (?,?,1,?,?)",
                           (ad, anahtar, sira, ayarlar.zaman_metni())).lastrowid)
    conn.executemany("INSERT INTO unvan_yetkinlik (unvan_id, yetkinlik) VALUES (?,?)", [(uid, y) for y in kodlar])
    db.yonetim_kaydi(conn, k, "unvan_ekle", f"unvan:{uid}", {"yetkinlik": kodlar})
    conn.commit()
    return {"unvan": next(u for u in _unvan_listesi(conn) if u["id"] == uid)}


@yonlendirici.patch("/api/admin/unvanlar/{unvan_id}")
def unvan_degistir(unvan_id: int, girdi: UnvanDegisikligi, k: dict = Depends(izin("yetkinlik.yonet")),
                   conn: sqlite3.Connection = Depends(baglanti)):
    """Adını değiştir (kişiler id ile bağlı kalır, ``kullanici.unvan`` metni de güncellenir), pasife al, sırala."""
    _tablolar_hazir(conn)
    satir = conn.execute("SELECT * FROM unvan WHERE id=?", (unvan_id,)).fetchone()
    if not satir:
        raise hata(404, "Unvan bulunamadı.", "unvan_yok")
    degisen = []
    if girdi.ad is not None:
        ad, anahtar = _ad_temizle(girdi.ad)
        if conn.execute("SELECT 1 FROM unvan WHERE ad_k=? AND id<>?", (anahtar, unvan_id)).fetchone():
            raise hata(409, "Bu adda başka bir unvan var.", "unvan_var")
        if ad != satir["ad"]:
            conn.execute("UPDATE unvan SET ad=?, ad_k=? WHERE id=?", (ad, anahtar, unvan_id))
            conn.execute("UPDATE kullanici SET unvan=? WHERE unvan_id=?", (ad, unvan_id))
            degisen.append("ad")
    if girdi.aktif is not None and bool(girdi.aktif) != bool(satir["aktif"]):
        # Pasif unvan yeni kişiye atanamaz; elinde olanların erişimi sürer (Administrator kişiyi taşır).
        conn.execute("UPDATE unvan SET aktif=? WHERE id=?", (1 if girdi.aktif else 0, unvan_id))
        degisen.append("aktif")
    if girdi.sira is not None and girdi.sira != satir["sira"]:
        conn.execute("UPDATE unvan SET sira=? WHERE id=?", (girdi.sira, unvan_id))
        degisen.append("sira")
    if degisen:
        db.yonetim_kaydi(conn, k, "unvan_duzenle", f"unvan:{unvan_id}", {"alanlar": degisen})
    conn.commit()
    return {"unvan": next(u for u in _unvan_listesi(conn) if u["id"] == unvan_id)}


@yonlendirici.get("/api/admin/matris")
def matris_oku(k: dict = Depends(izin(*_OKU)), conn: sqlite3.Connection = Depends(baglanti)):
    _tablolar_hazir(conn)
    return {"yetkinlikler": _katalog(), "unvanlar": _unvan_listesi(conn),
            "takim_lideri": yetki.takim_lideri_yetkinlikleri(conn),
            "duzenleyebilir": yetki.izinli(k, "yetkinlik.yonet")}


class MatrisGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # unvan id (metin anahtar: JSON) → yetkinlik kodları. Verilmeyen unvana dokunulmaz.
    unvanlar: dict[int, list[str]] = Field(default_factory=dict)
    takim_lideri: list[str] | None = None


@yonlendirici.put("/api/admin/matris")
def matris_yaz(girdi: MatrisGirdi, k: dict = Depends(izin("yetkinlik.yonet")),
               conn: sqlite3.Connection = Depends(baglanti)):
    """Unvan × yetkinlik anahtarları (ve takım lideri bayrağının verdiği yetkinlikler). Tek işlem."""
    _tablolar_hazir(conn)
    var = {r[0] for r in conn.execute("SELECT id FROM unvan").fetchall()}
    bilinmeyen = [u for u in girdi.unvanlar if u not in var]
    if bilinmeyen:
        raise hata(404, "Unvan bulunamadı.", "unvan_yok")
    temiz = {u: _yetkinlik_dogrula(kodlar) for u, kodlar in girdi.unvanlar.items()}
    tl = _yetkinlik_dogrula(girdi.takim_lideri) if girdi.takim_lideri is not None else None
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        degisen = []
        for uid, kodlar in temiz.items():
            once = yetki.unvan_yetkinlikleri(conn, uid)
            if once == kodlar:
                continue
            conn.execute("DELETE FROM unvan_yetkinlik WHERE unvan_id=?", (uid,))
            conn.executemany("INSERT INTO unvan_yetkinlik (unvan_id, yetkinlik) VALUES (?,?)",
                             [(uid, y) for y in kodlar])
            degisen.append(uid)
            db.yonetim_kaydi(conn, k, "unvan_yetkinlik", f"unvan:{uid}", {"once": once, "sonra": kodlar})
        tazelenen = _onbellekleri_tazele(conn, degisen)
        if tl is not None and tl != yetki.takim_lideri_yetkinlikleri(conn):
            db.ayar_yaz(conn, "takim_lideri_yetkinlikleri", json.dumps(tl))
            db.yonetim_kaydi(conn, k, "ayar", "ayar:takim_lideri_yetkinlikleri", {"sonra": tl})
            for (kid,) in conn.execute("SELECT id FROM kullanici WHERE yetki_modeli=1 AND takim_lideri=1").fetchall():
                yetki.gorev_onbellegi_yaz(conn, kid)
                tazelenen += 1
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return {"degisen_unvan": len(degisen), "etkilenen_kisi": tazelenen, "unvanlar": _unvan_listesi(conn),
            "takim_lideri": yetki.takim_lideri_yetkinlikleri(conn)}


def _kisi_karti(conn: sqlite3.Connection, satir: dict) -> dict:
    e = yetki.erisim(conn, satir)
    return {**_kullanici_kart(satir, yetki.gorev_kumesi_oku(conn, satir), maskeli=True),
            "yetki_modeli": bool(e["yetki_modeli"]), "yetkinlikler": e["yetkinlikler"],
            "unvan_yetkinlikleri": e["unvan_yetkinlikleri"], "ek_yetkinlikler": e["ek"]}


@yonlendirici.get("/api/admin/kisiler")
def kisi_listesi(k: dict = Depends(izin(*_OKU)), conn: sqlite3.Connection = Depends(baglanti)):
    """Kişiler: unvan, takım lideri, etkin/ek yetkinlikler, Administrator rozeti (telefon maskeli)."""
    _tablolar_hazir(conn)
    satirlar = [dict(r) for r in conn.execute("SELECT * FROM kullanici ORDER BY aktif DESC, ad").fetchall()]
    return {"kisiler": [_kisi_karti(conn, s) for s in satirlar], "unvanlar": _unvan_listesi(conn),
            "yetkinlikler": _katalog(), "duzenleyebilir_yetkinlik": yetki.izinli(k, "yetkinlik.yonet")}


class KisiYetkiGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    unvan_id: int | None = None
    takim_lideri: bool | None = None
    ek_yetkinlikler: list[str] | None = Field(default=None, max_length=20)


@yonlendirici.patch("/api/admin/kisiler/{kullanici_id}")
def kisi_duzenle(kullanici_id: int, girdi: KisiYetkiGirdi, k: dict = Depends(izin(*_OKU)),
                 conn: sqlite3.Connection = Depends(baglanti)):
    """Kişinin unvanı, takım liderliği (İK + Administrator) ve ek yetkinlikleri (yalnız Administrator)."""
    _tablolar_hazir(conn)
    admin = yetki.izinli(k, "yetkinlik.yonet")
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    satir = dict(satir)
    if yetki.administrator_mi(satir):
        raise hata(403, "Administrator'ın erişimi sabittir; düzenlenmez.", "administrator_korumali")
    verilen = girdi.model_fields_set
    if "ek_yetkinlikler" in verilen and not admin:
        raise hata(403, "Ek yetkinliği yalnız Administrator verir.", "yetkinlik_admin")
    if kullanici_id == k["id"] and not admin:
        raise hata(409, "Kendi unvanınızı ve yetkinliğinizi değiştiremezsiniz.", "kendi_rolu")
    from .ekip_uclari import _bolge_coz, ek_yetkinlik_yaz, yetki_modeline_al

    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        yetki_modeline_al(conn, satir)
        once = yetki.erisim(conn, satir)
        degisen = []
        if "unvan_id" in verilen and girdi.unvan_id != satir.get("unvan_id"):
            unvan_ad = None
            if girdi.unvan_id is not None:
                u = conn.execute("SELECT id, ad, aktif FROM unvan WHERE id=?", (girdi.unvan_id,)).fetchone()
                if not u:
                    raise hata(400, "Unvan bulunamadı.", "unvan_yok")
                if not u["aktif"]:
                    raise hata(400, "Bu unvan pasif; kişiye yeni atanamaz.", "unvan_pasif")
                unvan_ad = u["ad"]
            conn.execute("UPDATE kullanici SET unvan_id=?, unvan=? WHERE id=?", (girdi.unvan_id, unvan_ad, kullanici_id))
            degisen.append("unvan")
        if "takim_lideri" in verilen and bool(girdi.takim_lideri) != bool(satir.get("takim_lideri")):
            conn.execute("UPDATE kullanici SET takim_lideri=? WHERE id=?", (1 if girdi.takim_lideri else 0, kullanici_id))
            degisen.append("takim_lideri")
        if "ek_yetkinlikler" in verilen:
            kodlar = _yetkinlik_dogrula(girdi.ek_yetkinlikler or [])
            if kodlar != once["ek"]:
                ek_yetkinlik_yaz(conn, kullanici_id, kodlar)
                degisen.append("ek_yetkinlik")
        gorev = yetki.gorev_onbellegi_yaz(conn, kullanici_id)
        yeni = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone())
        sonra = yetki.erisim(conn, yeni)
        # Satış yetkinliği yeni geldiyse bölge ister (bölgesiz satışçının listesi boş kalır; uyarı arayüzde).
        if "satisci" in sonra["gorevler"] and yeni.get("bolge"):
            _bolge_coz(conn, sonra["gorevler"], yeni["bolge"], yeni["ad"])
        if "satisci" not in sonra["gorevler"] and yeni.get("bolge"):
            conn.execute("UPDATE kullanici SET bolge=NULL WHERE id=?", (kullanici_id,))
        if gorev["once"] != gorev["sonra"]:
            conn.execute("UPDATE kullanici SET oturum_no=oturum_no+1, oturum_neden='gorev' WHERE id=?",
                         (kullanici_id,))
        if degisen:
            db.yonetim_kaydi(conn, k, "kisi_yetkinlik", f"kullanici:{kullanici_id}",
                             {"alanlar": degisen, "izin_dusen": sorted(once["izinler"] - sonra["izinler"]),
                              "izin_eklenen": sorted(sonra["izinler"] - once["izinler"])})
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    yeni = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone())
    return {"kisi": _kisi_karti(conn, yeni), "degisen": degisen,
            "oturum_dustu": gorev["once"] != gorev["sonra"]}
