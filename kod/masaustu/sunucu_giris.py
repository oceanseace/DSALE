"""Dehanet Saha — masaüstü sunucu girişi. PyInstaller bunu ``SahaSunucu.exe`` yapar.

Repo kodu (``kod/saha``, ``kod/operasyon``, ``kod/dsale``) DEĞİŞTİRİLMEDEN çalışır; bu dosya yalnız
YAZILABİLİR yolları VERİ klasörüne yönlendirir. Kurulum klasörüne (Program Files) hiçbir şey
yazılmaz; güncellemede VERİ klasörü olduğu gibi kalır.

    SahaSunucu.exe [calistir] --veri <klasör> --host 0.0.0.0 --port 8080
    SahaSunucu.exe durum      --veri <klasör>     # tek satır JSON (masaüstü kabuğu okur)
    SahaSunucu.exe kur        --veri <klasör>     # ilk kurulum: binalar + davet kodları
    SahaSunucu.exe kodlar     --veri <klasör>     # PIN belirlememiş kişilerin davet kodları
    SahaSunucu.exe yedek      --veri <klasör>     # günlük yedek (saha.yedekle ile aynı)
    SahaSunucu.exe ice-aktar  --veri <klasör> --kaynak <saha.db | kurulum/veri klasörü, ör. DSALE\\canli\\veri>
    SahaSunucu.exe geri-yukle --veri <klasör> --dosya <yedek.db>
    SahaSunucu.exe surum

VERİ klasörü (varsayılan ``%ProgramData%\\DehanetSaha``):
    saha.db  gizli.key  obekler.json  kayit\\  yedek\\  yedek\\goc\\  raporlar\\  cikti\\  gelen\\  operasyon\\

Çıkış kodları ``saha.sunucu`` ile aynı: 0 tamam · 1 hata · 2 zaten çalışıyor · 3 güncelleme durdu.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import threading
from pathlib import Path

DONDURULMUS = bool(getattr(sys, "frozen", False))
# Salt okunur kaynaklar (veri/, kod/arayuz/dist ...) kod/yollar.py'den gelir: donmuşta _internal
# (sys._MEIPASS), geliştirmede depo. Geliştirmede kod/ içe aktarma yoluna konur (yollar, saha ...).
if not DONDURULMUS and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_DUR = threading.Event()          # kabuk "DUR" yazdı ya da borusu kapandı


def _konsol() -> None:
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, OSError, ValueError):
            pass


def varsayilan_veri() -> Path:
    ortam = os.environ.get("DEHANET_SAHA_VERI")
    if ortam:
        return Path(ortam)
    kok = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or r"C:\ProgramData"
    return Path(kok) / "DehanetSaha"


# ----------------------------------------------------------------------------- yol yönlendirme
def yollari_kur(veri: Path, olustur: bool = True) -> None:
    """Ortam değişkenlerini ve ``saha.ayarlar`` yollarını VERİ klasörüne çevirir.

    ``saha`` modüllerinden ÖNCE çağrılır: ``yedekle.YEDEK_DIZINI`` gibi içe aktarmada
    hesaplanan sabitler de böylece doğru klasörü görür. Salt okuyan komutlar (``durum``)
    klasörü oluşturmaz.
    """
    veri = veri.resolve()
    if olustur:
        veri.mkdir(parents=True, exist_ok=True)
    os.environ["SAHA_DB"] = str(veri / "saha.db")
    os.environ["SAHA_CIKTI"] = str(veri / "cikti")
    os.environ["SAHA_GELEN"] = str(veri / "gelen")
    os.environ["OPERASYON_VERI"] = str(veri / "operasyon")
    os.environ["OPERASYON_OBEK"] = str(veri / "obekler.json")
    os.environ["DEHANET_SAHA_VERI"] = str(veri)

    from saha import ayarlar  # yalnız standart kütüphane içe aktarır

    ayarlar.CALISMA = veri                  # yazılabilir kök: yedek/, ek/ ...
    ayarlar.DB_YOLU = veri / "saha.db"
    ayarlar.GIZLI_ANAHTAR = veri / "gizli.key"
    ayarlar.KAYIT_DIZINI = veri / "kayit"
    # Salt okunur kaynaklar (yollar.VERI, yollar.ARAYUZ_DIST, yollar.SUNUM_URETILEN) olduğu gibi kalır.


# ----------------------------------------------------------------------------- düzgün kapanış
def _surec_yasiyor(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    tutamac = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if not tutamac:
        return ctypes.get_last_error() == 5                    # erişim reddi: süreç var
    try:
        kod = wintypes.DWORD()
        if not k32.GetExitCodeProcess(tutamac, ctypes.byref(kod)):
            return True
        return kod.value == 259                                # STILL_ACTIVE
    finally:
        k32.CloseHandle(tutamac)


def _kabugu_izle(ebeveyn: int, dur_dosyasi: Path | None) -> None:
    """Kabuk durdurma dosyasını yazarsa ya da kabuk süreci ölürse sunucu DÜZGÜN kapanır.

    stdin borusu KULLANILMAZ: Windows'ta bir iş parçacığı borudan okurken aynı tutamağa dokunan
    başka bir çağrı (GetFileType) kilitleniyor ve sunucu hiç açılmıyordu.
    """
    import time

    while not _DUR.is_set():
        if dur_dosyasi is not None and dur_dosyasi.exists():
            try:
                dur_dosyasi.unlink()
            except OSError:
                pass
            break
        if ebeveyn and not _surec_yasiyor(ebeveyn):
            break
        time.sleep(0.5)
    _DUR.set()


def _uvicorn_yamasi() -> None:
    """``uvicorn.run``'ı durdurulabilir sürümüyle değiştirir (``saha.sunucu.main`` aynı kalır)."""
    import uvicorn

    def run(app, **kw):
        if _DUR.is_set():                   # göç sürerken kapatma istendi: hiç açılma
            return
        sunucu = uvicorn.Server(uvicorn.Config(app, **kw))

        def izle() -> None:
            _DUR.wait()
            sunucu.should_exit = True

        threading.Thread(target=izle, name="kabuk-izle", daemon=True).start()
        sunucu.run()

    uvicorn.run = run


# ----------------------------------------------------------------------------- yardımcılar
def _salt_oku(yol: Path) -> sqlite3.Connection:
    return sqlite3.connect(yol.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)


def _yedekler(veri: Path) -> list[Path]:
    return sorted(list((veri / "yedek").glob("saha-*.db")) + list((veri / "yedek" / "goc").glob("saha-*.db")),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def _hedef_sema() -> int | None:
    try:
        from saha import sema_v2
        return int(sema_v2.HEDEF)
    except Exception:  # noqa: BLE001
        return None


def _dogrulanmis_kopya(kaynak: Path, hedef: Path) -> dict:
    """SQLite yedekleme API'siyle kopyalar; bütünlük ve tablo satır sayıları tutmazsa yarım dosya bırakmaz."""
    gecici = hedef.with_name(hedef.name + ".yaziliyor")
    for ek in ("", "-wal", "-shm", "-journal"):
        Path(str(gecici) + ek).unlink(missing_ok=True)
    k = _salt_oku(kaynak)
    try:
        k.execute("BEGIN")
        tablolar = [r[0] for r in k.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        sayilar = {t: k.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablolar}
        h = sqlite3.connect(gecici)
        try:
            k.backup(h)
        finally:
            h.close()
        k.execute("COMMIT")
    finally:
        k.close()
    h = sqlite3.connect(gecici, isolation_level=None)
    try:
        butunluk = h.execute("PRAGMA integrity_check").fetchone()[0]
        yeni = {t: h.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sayilar}
        surum = int(h.execute("PRAGMA user_version").fetchone()[0])
        h.execute("PRAGMA journal_mode=DELETE")
    finally:
        h.close()
    if butunluk != "ok" or yeni != sayilar:
        gecici.unlink(missing_ok=True)
        raise SystemExit("Kopya doğrulanamadı (bütünlük ya da satır sayısı tutmadı); hiçbir şey değişmedi.")
    os.replace(gecici, hedef)
    return {"tablo": len(sayilar), "sema": surum,
            "bina": sayilar.get("bina", 0), "kullanici": sayilar.get("kullanici", 0)}


def _sunucu_acik_mi(port: int = 0) -> bool:
    from saha.sunucu import port_dolu_mu

    return bool(port) and port_dolu_mu(port)


# ----------------------------------------------------------------------------- komutlar
def k_durum(a, veri: Path) -> int:
    db = veri / "saha.db"
    sonuc: dict = {"veri": str(veri), "db_var": db.exists(), "yedek_sayisi": len(_yedekler(veri)),
                   "hedef_sema": _hedef_sema(), "db_sema": None, "bina": None, "kullanici": None,
                   "gizli_var": (veri / "gizli.key").exists(), "obek_var": (veri / "obekler.json").exists()}
    try:
        from saha import SURUM
        sonuc["surum"] = SURUM
    except Exception:  # noqa: BLE001
        sonuc["surum"] = None
    if db.exists() and db.stat().st_size > 0:
        try:
            c = _salt_oku(db)
            try:
                sonuc["db_sema"] = int(c.execute("PRAGMA user_version").fetchone()[0])
                for t in ("bina", "kullanici"):
                    try:
                        sonuc[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    except sqlite3.Error:
                        pass
            finally:
                c.close()
        except sqlite3.Error as exc:
            sonuc["hata"] = f"Veritabanı okunamadı: {exc}"
    print(json.dumps(sonuc, ensure_ascii=False))
    return 0


def k_calistir(a, veri: Path) -> int:
    if a.ebeveyn or a.dur_dosyasi:
        dur = Path(a.dur_dosyasi) if a.dur_dosyasi else None
        if dur is not None:
            dur.unlink(missing_ok=True)                        # önceki oturumdan kalan istek
        threading.Thread(target=_kabugu_izle, args=(a.ebeveyn or 0, dur), name="kabuk-izle",
                         daemon=True).start()
    _uvicorn_yamasi()
    from saha import sunucu

    print(f"Veri klasörü: {veri}", flush=True)
    return int(sunucu.main(["--host", a.host, "--port", str(a.port), "--seviye", a.seviye]) or 0)


def k_kur(a, veri: Path) -> int:
    db = veri / "saha.db"
    if not db.exists() and _yedekler(veri) and not a.yine_de:
        print("Veritabanı yok ama yedek var: yeni ve boş bir veritabanı KURULMADI.")
        print("Geri yüklemek için: SahaSunucu.exe geri-yukle --dosya <yedek>")
        return 4
    from saha import kur

    return int(kur.main([]) or 0)


def k_kodlar(a, veri: Path) -> int:
    from saha import kur

    return int(kur.main(["--kodlar"]) or 0)


def k_yedek(a, veri: Path) -> int:
    if not (veri / "saha.db").exists():
        print("Veritabanı yok; yedeklenecek bir şey yok.")
        return 1
    from saha import yedekle

    return int(yedekle.main([]) or 0)


def k_ice_aktar(a, veri: Path) -> int:
    """Var olan bir kurulumun verisini (ör. DSALE\\canli\\veri) VERİ klasörüne DOĞRULANMIŞ kopya olarak getirir.

    Kaynağa yalnız okunur dokunulur. Hedefte veritabanı varsa üzerine yazılmaz (``--uzerine``:
    eskisi silinmez, ``saha-onceki-<zaman>.db`` adıyla kenara konur).
    """
    kaynak = Path(a.kaynak)
    if kaynak.is_dir():
        adaylar = [kaynak / "saha.db", kaynak / "saha" / "saha.db"]
        kaynak_db = next((p for p in adaylar if p.exists()), None)
        if kaynak_db is None:
            print(f"Bu klasörde saha.db bulunamadı: {kaynak}")
            return 1
    else:
        kaynak_db = kaynak
    if not kaynak_db.exists():
        print(f"Dosya bulunamadı: {kaynak_db}")
        return 1
    hedef = veri / "saha.db"
    if hedef.resolve() == kaynak_db.resolve():
        print("Kaynak ile hedef aynı dosya.")
        return 1
    if hedef.exists():
        if not a.uzerine:
            print("Veri klasöründe zaten bir veritabanı var; üzerine yazılmadı.")
            return 2
        from saha import ayarlar

        kenar = veri / f"saha-onceki-{ayarlar.simdi():%Y%m%d-%H%M%S}.db"
        os.replace(hedef, kenar)
        for ek in ("-wal", "-shm"):
            yan = Path(str(hedef) + ek)
            if yan.exists():
                os.replace(yan, Path(str(kenar) + ek))
        print(f"Eski veritabanı silinmedi, kenara kondu: {kenar.name}")
    ozet = _dogrulanmis_kopya(kaynak_db, hedef)
    sayi = lambda n: f"{int(n):,}".replace(",", ".")  # noqa: E731  (19.706)
    print(f"Veritabanı getirildi: {sayi(ozet['bina'])} bina, {sayi(ozet['kullanici'])} kişi, şema v{ozet['sema']}.")

    klasor = kaynak_db.parent
    gizli = next((p for p in (klasor / "gizli.key", klasor / "saha" / "gizli.key") if p.exists()), None)
    if gizli and not (veri / "gizli.key").exists():
        (veri / "gizli.key").write_bytes(gizli.read_bytes())
        try:
            from saha import guvenlik
            getattr(guvenlik, "_sadece_sahibi", lambda _y: None)(veri / "gizli.key")
        except Exception:  # noqa: BLE001
            pass
        print("Oturum anahtarı getirildi: telefonlar yeniden giriş yapmadan bağlanır.")
    obek_adaylari = [klasor / "operasyon" / "obekler.json", klasor.parent / "operasyon" / "obekler.json",
                     klasor / "obekler.json"]
    obek = next((p for p in obek_adaylari if p.exists()), None)
    if obek and not (veri / "obekler.json").exists():
        (veri / "obekler.json").write_bytes(obek.read_bytes())
        print("Öbek tanımları getirildi.")
    print("İlk açılışta veritabanı bu sürüme güncellenir (önce doğrulanmış yedek alınır).")
    return 0


def k_geri_yukle(a, veri: Path) -> int:
    if _sunucu_acik_mi(a.port):
        print("Sunucu açık. Önce sunucuyu durdurun.")
        return 2
    from saha import yedekle

    try:
        sonuc = yedekle.geri_yukle(Path(a.dosya), veri / "saha.db")
    except yedekle.YedekHatasi as exc:
        print(exc.mesaj)
        return 1
    if sonuc.get("kenara_konan"):
        print(f"Eski dosya silinmedi, kenara kondu: {Path(sonuc['kenara_konan']).name}")
    print(f"Geri yüklendi (şema v{sonuc['surum']}). Bütünlük denetimi: tamam.")
    return 0


def k_surum(a, veri: Path) -> int:
    try:
        from saha import SURUM
    except Exception:  # noqa: BLE001
        SURUM = None
    print(json.dumps({"surum": SURUM, "hedef_sema": _hedef_sema(), "dondurulmus": DONDURULMUS},
                     ensure_ascii=False))
    return 0


KOMUTLAR = {"calistir": k_calistir, "durum": k_durum, "kur": k_kur, "kodlar": k_kodlar, "yedek": k_yedek,
            "ice-aktar": k_ice_aktar, "geri-yukle": k_geri_yukle, "surum": k_surum}


def ayrac() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="SahaSunucu", description="Dehanet Saha sunucusu (masaüstü)")
    p.add_argument("komut", nargs="?", default="calistir", choices=sorted(KOMUTLAR))
    p.add_argument("--veri", default=None, help="Veri klasörü (varsayılan %%ProgramData%%\\DehanetSaha)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--seviye", default="info")
    p.add_argument("--ebeveyn", type=int, default=0, help="Kabuk süreci: o kapanınca sunucu da düzgün kapanır")
    p.add_argument("--dur-dosyasi", dest="dur_dosyasi", default=None,
                   help="Bu dosya oluşunca sunucu düzgün kapanır (kabuğun 'Sunucuyu durdur' komutu)")
    p.add_argument("--kaynak", help="ice-aktar: saha.db ya da onu içeren klasör")
    p.add_argument("--uzerine", action="store_true", help="ice-aktar: var olanı kenara koyup getir")
    p.add_argument("--dosya", help="geri-yukle: yedek dosyası")
    p.add_argument("--yine-de", action="store_true", dest="yine_de",
                   help="kur: yedek olsa da boş veritabanı kur")
    return p


def main(argv: list[str] | None = None) -> int:
    _konsol()
    a = ayrac().parse_args(argv)
    if a.komut == "surum":                 # veri klasörüne hiç dokunmaz (derleme betiği de çağırır)
        return k_surum(a, None)
    veri = Path(a.veri) if a.veri else varsayilan_veri()
    try:
        yollari_kur(veri, olustur=a.komut != "durum")
    except OSError as exc:
        print(f"Veri klasörü hazırlanamadı ({veri}): {exc}")
        return 1
    if a.komut == "ice-aktar" and not a.kaynak:
        print("ice-aktar için --kaynak gerekli.")
        return 1
    if a.komut == "geri-yukle" and not a.dosya:
        print("geri-yukle için --dosya gerekli.")
        return 1
    return KOMUTLAR[a.komut](a, Path(os.environ["DEHANET_SAHA_VERI"]))


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
