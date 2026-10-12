"""RUT uçları (günlük ekip rotası). Motor: ``rut.py``. ``saha/api.py`` ``_v2_bagla`` bu modülü bağlar ve
``ROTA_IZNI``'nı ``yetki.ROTA_IZNI``'na ekler.

    GET /api/rut?tarih=AAAA-AA-GG     günün rotası (ekip sayfaları + özet)
    PUT /api/rut/hucre                {tarih, task_no, alan, deger} → günün rotası
    PUT /api/rut/ayar                 {mesai_bas, mesai_bit} → {mesai}

Müşteri alanı dönen her okuma ``erisim_kaydi``'na adetle yazılır (F21).
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from . import rut, zaman
from .hatalar import V2Hata
from .islem import islem

ROTA_IZNI: dict[tuple[str, str], str] = {
    ("GET", "/api/rut"): "is.duzenle",
    ("PUT", "/api/rut/hucre"): "is.duzenle",
    ("PUT", "/api/rut/ayar"): "is.duzenle",
}


class HucreGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tarih: str | None = None
    task_no: str = Field(min_length=1, max_length=40)
    alan: str = Field(min_length=1, max_length=20)
    deger: str | None = Field(default=None, max_length=500)


class AyarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mesai_bas: str
    mesai_bit: str


def _cagir(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except V2Hata as e:
        raise HTTPException(status_code=e.durum, detail=e.govde())


def _erisim(conn: sqlite3.Connection, k: dict | None, adet: int, istek: Request | None) -> None:
    if not k or not adet:
        return
    try:
        with islem(conn):
            conn.execute("INSERT OR IGNORE INTO erisim_kaydi (zaman, gun, kullanici_id, kullanici_ad, eylem, is_no, "
                         "adet, ip) VALUES (?,?,?,?,?,?,?,?)",
                         (zaman.metin(), zaman.metin()[:10], k["id"], k.get("ad"), "rut", None, adet,
                          istek.client.host if istek is not None and istek.client else None))
    except sqlite3.Error:
        pass


def yonlendiriciler(b) -> list[APIRouter]:
    """``b``: saha.yetki.Bagimliliklar (izin, baglanti)."""
    r = APIRouter(tags=["rut"])
    izin, baglanti = b.izin, b.baglanti

    @r.get("/api/rut")
    def rut_gun(istek: Request, tarih: str | None = Query(default=None, max_length=10),
                k: dict = Depends(izin("is.duzenle")), conn: sqlite3.Connection = Depends(baglanti)):
        y = _cagir(rut.gun, conn, k, tarih)
        if y["musteri"]:
            _erisim(conn, k, y["adet"], istek)
        return y

    @r.put("/api/rut/hucre")
    def rut_hucre(girdi: HucreGirdi, k: dict = Depends(izin("is.duzenle")),
                  conn: sqlite3.Connection = Depends(baglanti)):
        return _cagir(rut.hucre_yaz, conn, k, girdi.tarih, girdi.task_no, girdi.alan, girdi.deger)

    @r.put("/api/rut/ayar")
    def rut_ayar(girdi: AyarGirdi, k: dict = Depends(izin("is.duzenle")),
                 conn: sqlite3.Connection = Depends(baglanti)):
        return {"mesai": _cagir(rut.mesai_yaz, conn, girdi.mesai_bas, girdi.mesai_bit)}

    return [r]
