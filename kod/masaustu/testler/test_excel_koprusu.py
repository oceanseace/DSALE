"""kod/masaustu/turkcell.py "Excel'de aç" köprüsü: TASKS'ın .xlsx'i gizli tmp'ye yazılır ve açılır (os.startfile yerine sahte)."""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import pytest

from masaustu import turkcell

ZIP = turkcell.ZIP_IMZASI + b"deneme"


def _b64(veri: bytes) -> str:
    return base64.b64encode(veri).decode()


def test_yazar_ve_acar(tmp_path: Path):
    acilan: list[str] = []
    api = turkcell.KabukApi(klasor=tmp_path, ac=acilan.append)
    assert api.excel_ac("TASKS-2026-10-06-1712.xlsx", _b64(ZIP)) == {"ok": True}
    yol = tmp_path / "TASKS-2026-10-06-1712.xlsx"
    assert yol.read_bytes() == ZIP and acilan == [str(yol)]


def test_ad_suzulur_ve_ustune_yazilmaz(tmp_path: Path):
    a = turkcell.excel_dosyasi_yaz(tmp_path, r"..\..\Windows\kotu", _b64(ZIP))
    assert a.parent == tmp_path and a.name == "kotu.xlsx"
    b = turkcell.excel_dosyasi_yaz(tmp_path, "kotu.xlsx", _b64(ZIP))
    assert b.name == "kotu (2).xlsx" and a.exists()


def test_zip_olmayan_reddedilir(tmp_path: Path):
    with pytest.raises(ValueError):
        turkcell.excel_dosyasi_yaz(tmp_path, "x.xlsx", _b64(b"MZ-calistirilabilir"))
    acilan: list[str] = []
    y = turkcell.KabukApi(klasor=tmp_path, ac=acilan.append).excel_ac("x.xlsx", "bozuk base64!")
    assert y["ok"] is False and not acilan and not list(tmp_path.iterdir())


def test_eski_dosyalar_silinir(tmp_path: Path):
    eski = tmp_path / "eski.xlsx"
    eski.write_bytes(ZIP)
    t = time.time() - turkcell.EXCEL_SAKLAMA_SN - 60
    os.utime(eski, (t, t))
    turkcell.excel_dosyasi_yaz(tmp_path, "yeni.xlsx", _b64(ZIP))
    assert not eski.exists() and (tmp_path / "yeni.xlsx").exists()


def test_boss_giris_yalniz_yerel_ara_sayfayi_acar(monkeypatch):
    """"BOSS ile giriş" köprüsü yalnız yerel /boss-giris/<istek> adresini açar (başka adres asla)."""
    acilan: list[str] = []
    monkeypatch.setattr(turkcell, "brave_yolu", lambda: None)
    api = turkcell.KabukApi(ac=acilan.append)
    iyi = "http://127.0.0.1:8080/boss-giris/" + "a" * 32
    assert api.tarayicida_ac(iyi) == {"ok": True} and acilan == [iyi]
    for kotu in ("https://boss.turkcell.com.tr/", "http://10.0.0.5:8080/boss-giris/" + "a" * 32,
                 "file:///C:/Windows/system32/calc.exe", "http://127.0.0.1:8080/boss-giris/x y"):
        assert api.tarayicida_ac(kotu)["ok"] is False
    assert acilan == [iyi]
