"""Başarım bütçeleri (spec §5.6) ve gerçek BOSS raporuyla kabul (spec §8.3 "Bitti sayılır").

Gerçek rapor (``BOSS_RAPOR`` ya da gelistirme/test/TeknikTaskDetayRaporu.xlsx sabit kopyası) yalnız OKUNUR; testler
kişisel veri yazdırmaz (yalnız sayı). Yoksa bu testler atlanır. Sağlık ucu testi gerçek uvicorn'u YALNIZ
127.0.0.1:8091'de, karalama veritabanıyla açar ve iş bitince kapatır.

Bütçeler ofis sunucusu içindir; geliştirme makinesinde ``SAHA_BUTCE_PAYI`` katsayısıyla (varsayılan 2) gevşer.
Kesin ölçüm: ``SAHA_BUTCE_PAYI=1``.
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

from operasyon import is_emri as ie
from operasyon.testler import yardim as y
import yollar
from operasyon.testler.conftest import BUTCE_PAYI as PAY, GERCEK_RAPOR
from operasyon.v2 import akis, obek, sozluk

gercek = pytest.mark.skipif(not GERCEK_RAPOR.exists(), reason="gerçek BOSS raporu yok")
PORT = 8091


def _en_iyi(fn, n=5) -> float:
    en = 1e9
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        en = min(en, time.perf_counter() - t0)
    return en


@gercek
def test_gercek_rapor_butceler_ve_obek_eslesmesi(v2_ortam, v2db, conn, istemci, jeton, kisi, kim):
    veri = GERCEK_RAPOR.read_bytes()
    s = y.aktar(v2db, None, veri=veri, ad="TeknikTaskDetayRaporu.xlsx")
    n = s["fark"]["yeni"]
    assert 300 <= n <= 800 and n == conn.execute("SELECT COUNT(*) FROM is_emri").fetchone()[0]
    ozet = json.loads(conn.execute("SELECT ozet FROM ie_aktarim WHERE id=?", (s["aktarim_id"],)).fetchone()[0])
    assert ozet["okuma_sn"] < 3.0 * PAY, ozet["okuma_sn"]               # okuma + hesap < 3 sn
    assert s["yazma_sn"] < 0.3 * PAY, s["yazma_sn"]                     # yazma işlemi < 300 ms (tek işlem)
    assert s["lokasyon"]["var"] >= 300 and s["lokasyon"]["eslesen"] >= 0.97 * s["lokasyon"]["var"]
    assert y.lokasyon_kacan(conn) == 0                                  # aynı ilçedeki hiçbir Location Id kaçmaz
    # Bugünkü JSON motoruyla aynı öbek (kullanıcının öbek dosyasının KOPYASI)
    tanimlar = json.loads(v2_ortam["obek_json"].read_text(encoding="utf-8"))["obekler"]
    motor = ie.Obekler(tanimlar=tanimlar)
    motor._derle()
    eski = ie.hazirla(ie.raporu_oku(io.BytesIO(veri)), motor, sozluk.sozluk_db(conn),
                      mahalle_cozucu=sozluk.mahalle_coz).isler
    eski_obek = {str(r["Task No"]).removesuffix(".0"): (r["Öbek"] or None) for _, r in eski.iterrows()}
    db_obek = {r[0]: r[1] for r in conn.execute(
        "SELECT e.boss_task_no, o.ad FROM is_emri e LEFT JOIN obek o ON o.id = COALESCE(e.obek_elle_id, e.obek_id)")}
    ortak = set(eski_obek) & set(db_obek)
    fark = sum(1 for no in ortak if eski_obek[no] != db_obek[no])
    assert len(ortak) == n and fark == 0, (len(ortak), fark)
    # İkinci yükleme etkisiz (sha): hiçbir satır değişmez
    once = y.db_ozeti(conn)
    assert y.aktar(v2db, None, veri=veri)["ayni_dosya"] is True and y.db_ozeti(conn) == once
    # GET /api/isler (operasyon, bütün açık işler) < 150 ms · GET /api/isler/{no} < 50 ms
    h = jeton(kisi["operasyon"])
    assert istemci.get("/api/isler", headers=h).status_code == 200
    t_liste = _en_iyi(lambda: istemci.get("/api/isler", headers=h))
    no = conn.execute("SELECT is_no FROM is_emri LIMIT 1").fetchone()[0]
    t_tek = _en_iyi(lambda: istemci.get(f"/api/isler/{no}", headers=h))
    assert t_liste < 0.150 * PAY, t_liste
    assert t_tek < 0.050 * PAY, t_tek
    # Öbek düzenleme (mahalle çıkar/ekle + işlerin yeniden çözümü) < 150 ms
    op = kim("operasyon")
    o = max(obek.liste(conn)["obekler"], key=lambda x: x["acik"])
    ref = next(m for m in o["mahalleler"] if m["acik"] and not m["tum_ilce"])
    t0 = time.perf_counter()
    c = obek.mahalle_cikar(conn, o["id"], [ref["ref"]], op, obek.surum(conn))
    t_cikar = time.perf_counter() - t0
    t0 = time.perf_counter()
    obek.mahalle_ekle(conn, o["id"], op, c["surum"], refler=[ref["ref"]])
    t_ekle = time.perf_counter() - t0
    assert c["etkilenen_is"] == ref["acik"]
    assert t_cikar < 0.150 * PAY and t_ekle < 0.150 * PAY, (t_cikar, t_ekle)


@gercek
def test_gercek_rapor_ters_sira_0_yeni_emek_korunur(v2db, conn, kisi, kim):
    """Aynı içerik farklı sıra/biçimde (sha farklı) gelse de 0 yeni; o günün ataması ve randevusu aynen kalır."""
    import pandas as pd
    veri = GERCEK_RAPOR.read_bytes()
    y.aktar(v2db, None, veri=veri)
    op = kim("operasyon")
    nolar = [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE durum IN ('bekliyor','randevulu') "
                                        "AND bina_serial IS NULL ORDER BY is_no LIMIT 3")]
    for no in nolar:
        akis.ata(conn, no, kisi["teknik1"], op, yine_de=True)
    once = {r[0]: tuple(r[1:]) for r in conn.execute("SELECT is_no, durum, atanan_id, randevu_bas, surum FROM is_emri")}
    df = ie.raporu_oku(io.BytesIO(veri)).iloc[::-1]
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Task Detail Report")
    s = y.aktar(v2db, None, veri=b.getvalue())
    assert s["fark"]["yeni"] == 0 and s["fark"]["kaybolan"] == 0
    sonra = {r[0]: tuple(r[1:]) for r in conn.execute("SELECT is_no, durum, atanan_id, randevu_bas, surum FROM is_emri")}
    assert {no: sonra[no] for no in nolar} == {no: once[no] for no in nolar}


def _port_bos(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


@gercek
@pytest.mark.skipif(not _port_bos(PORT), reason=f"127.0.0.1:{PORT} dolu")
def test_saglik_300ms_uvicorn(v2db, conn, kisi, tmp_path):
    """Aktarım sürerken /api/saglik < 300 ms (gerçek uvicorn, 127.0.0.1:8091, karalama veritabanı)."""
    import httpx
    from saha import guvenlik
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    env = {**os.environ, "SAHA_DB": str(v2db), "OPERASYON_VERI": str(tmp_path / "veri"), "SAHA_IZLEME": "0",
           "OPERASYON_OBEK": os.environ.get("OPERASYON_OBEK", ""), "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(yollar.KOD)}
    env.pop("SAHA_GOC_LIFESPAN", None)
    gunluk = open(tmp_path / "uvicorn.log", "wb")
    sunucu = subprocess.Popen([sys.executable, "-m", "uvicorn", "saha.api:app", "--host", "127.0.0.1", "--port", str(PORT),
                               "--log-level", "warning"], cwd=str(yollar.KOK), env=env, stdout=gunluk, stderr=subprocess.STDOUT)
    try:
        kok = f"http://127.0.0.1:{PORT}"
        with httpx.Client(timeout=60) as c:
            son = time.time() + 90
            while True:
                try:
                    if c.get(kok + "/api/saglik").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                assert time.time() < son and sunucu.poll() is None, "sunucu açılmadı"
                time.sleep(0.3)
            r = conn.execute("SELECT * FROM kullanici WHERE id=?", (kisi["operasyon"],)).fetchone()
            h = {"Authorization": f"Bearer {guvenlik.jeton_uret(r)}"}
            sonuc: dict = {}

            def yukle():
                with httpx.Client(timeout=120) as c2:
                    sonuc["r"] = c2.post(kok + "/api/aktarim", headers=h,
                                         files={"dosya": ("TeknikTaskDetayRaporu.xlsx", GERCEK_RAPOR.read_bytes())})
            t = threading.Thread(target=yukle)
            t.start()
            sureler = []
            while t.is_alive():
                t0 = time.perf_counter()
                assert c.get(kok + "/api/saglik").status_code == 200
                sureler.append(time.perf_counter() - t0)
                time.sleep(0.05)
            t.join()
            assert sonuc["r"].status_code == 200, sonuc["r"].text[:300]
            assert sonuc["r"].json()["fark"]["yeni"] >= 300
            assert len(sureler) >= 3 and max(sureler) < 0.300 * PAY, (len(sureler), max(sureler))
            liste = c.get(kok + "/api/isler", headers=h)
            assert liste.status_code == 200 and liste.json()["sayac"]["acik"] >= 300
    finally:
        sunucu.terminate()
        try:
            sunucu.wait(timeout=15)
        except subprocess.TimeoutExpired:
            sunucu.kill()
        gunluk.close()
    son = time.time() + 10                                               # Windows soketi bir an geç bırakabilir
    while not _port_bos(PORT) and time.time() < son:
        time.sleep(0.2)
    assert _port_bos(PORT)
