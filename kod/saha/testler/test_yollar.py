"""kod/yollar.py: geliştirme varsayılanları ve yayınlanmış (canli/) kopyanın korumaları.

Her durum ayrı bir Python sürecinde, yollar.py'nin geçici bir kopyasıyla denenir; gerçek canli/ klasörüne
ve çalışma verisine dokunulmaz.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yollar

_BETIK = "import json, yollar; print(json.dumps({'calisma': str(yollar.CALISMA), 'ps26': str(yollar.PS26), " \
         "'canli_kopya': yollar.CANLI_KOPYA}))"


def _kos(kod_klasoru: Path, **ortam) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("SAHA_VERI_DIZINI", "SAHA_PS26", "PYTHONPATH")}
    env.update(ortam, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-c", _BETIK], cwd=kod_klasoru, env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


def _kopya(kok: Path) -> Path:
    kod = kok / "kod"
    kod.mkdir(parents=True)
    shutil.copyfile(yollar.KOD / "yollar.py", kod / "yollar.py")
    return kod


def test_gelistirme_varsayilani_canli_degil(tmp_path):
    kod = _kopya(tmp_path / "DSALE")
    r = _kos(kod)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert not d["canli_kopya"]
    assert Path(d["calisma"]) == tmp_path / "DSALE" / "gelistirme" / "veri"
    assert Path(d["ps26"]) == tmp_path / "PS26"


def test_canli_kopya_calisma_klasorsuz_baslamaz(tmp_path):
    kod = _kopya(tmp_path / "DSALE" / "canli" / "surum")
    r = _kos(kod)                                            # SAHA_VERI_DIZINI yok
    assert r.returncode != 0 and "SAHA_VERI_DIZINI" in r.stderr
    r = _kos(kod, SAHA_VERI_DIZINI=r"canli\veri")            # göreli: kopyaya göre çözülürdü (canli/surum/canli/veri)
    assert r.returncode != 0 and "MUTLAK" in r.stderr


def test_canli_kopya_mutlak_yolla_calisir_ps26_depo_yaninda(tmp_path):
    kod = _kopya(tmp_path / "DSALE" / "canli" / "surum")
    veri = tmp_path / "DSALE" / "canli" / "veri"
    r = _kos(kod, SAHA_VERI_DIZINI=str(veri))
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert d["canli_kopya"] and Path(d["calisma"]) == veri
    assert Path(d["ps26"]) == tmp_path / "PS26"             # canli/PS26 değil
    r = _kos(kod, SAHA_VERI_DIZINI=str(veri), SAHA_PS26=str(tmp_path / "baska" / "PS26"))
    assert Path(json.loads(r.stdout)["ps26"]) == tmp_path / "baska" / "PS26"
