"""EK-10 · Rapor klasörü izleme — "15 dakika"nın asıl engeli (F17).

Sunucu kullanıcının bilgisayarında çalıştığı için BOSS'tan indirilen rapor aynı makineye düşer. İzleyici
``ayar.izlenen_klasorler`` (yoksa sunucuyu çalıştıran kullanıcının İndirilenler + Masaüstü klasörleri) içinde
``ayar.izlenen_desenler`` (varsayılan ``TeknikTaskDetayRaporu*.xlsx``) dosyalarına 15 sn'de bir bakar. Yeni ya da
değişen dosya 5 sn boyunca aynı kalınca spec §4 hattından AYNEN geçer: sha etkisizliği, eksik/eski rapor bekçisi,
yedek, tek işlem. Bekçiye takılan rapor kendiliğinden uygulanmaz → "Onay bekleyen rapor" (İşler ekranında).

Yoklama tabanlıdır (ek paket yok), ``ayar.klasor_izleme`` ile kapatılır. Sunucu açılışında ``baslat()``
çağrılır (``operasyon/v2/api.py`` yönlendiricisinin yaşam döngüsü; FastAPI onu ``saha/api.py`` açılışının içine
yerleştirir); testler iş parçacığı açmaz, ``Izleyici.tara(an)`` ile adım adım dener.
"""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import aktarim, zaman
from .hatalar import V2Hata

YOKLAMA_SN = 15.0
SABIT_SN = 5.0
AZAMI_DENEME = 3
_gunluk = logging.getLogger("operasyon.izleme")


def varsayilan_klasorler() -> list[str]:
    """Sunucuyu çalıştıran kullanıcının İndirilenler ve Masaüstü klasörleri (OneDrive'a taşınmışsa o da)."""
    ev = Path.home()
    adaylar = [ev / "Downloads", ev / "Desktop"]
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        adaylar += [Path(onedrive) / "Desktop", Path(onedrive) / "Masaüstü"]
    return [str(p) for p in dict.fromkeys(adaylar) if p.exists()]


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


def ayarlar(conn: sqlite3.Connection) -> dict:
    try:
        klasorler = json.loads(_ayar(conn, "izlenen_klasorler", "") or "null")
    except ValueError:
        klasorler = None
    try:
        desenler = json.loads(_ayar(conn, "izlenen_desenler", "") or "null")
    except ValueError:
        desenler = None
    return {"acik": str(_ayar(conn, "klasor_izleme", "acik")).lower() in ("acik", "1", "true", "evet"),
            "klasorler": [str(k) for k in klasorler] if isinstance(klasorler, list) and klasorler
            else varsayilan_klasorler(),
            "desenler": [str(d) for d in desenler] if isinstance(desenler, list) and desenler
            else ["TeknikTaskDetayRaporu*.xlsx"],
            "klasorler_varsayilan": not (isinstance(klasorler, list) and klasorler)}


def ayar_yaz(conn: sqlite3.Connection, *, acik: bool | None = None, klasorler: list[str] | None = None,
             desenler: list[str] | None = None) -> dict:
    from .islem import islem
    with islem(conn):
        if acik is not None:
            conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('klasor_izleme', ?) ON CONFLICT(anahtar) "
                         "DO UPDATE SET deger=excluded.deger", ("acik" if acik else "kapali",))
        if klasorler is not None:
            temiz = [str(Path(k)) for k in klasorler if str(k).strip()]
            if temiz:
                conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('izlenen_klasorler', ?) ON CONFLICT(anahtar) "
                             "DO UPDATE SET deger=excluded.deger", (json.dumps(temiz, ensure_ascii=False),))
            else:
                conn.execute("DELETE FROM ayar WHERE anahtar='izlenen_klasorler'")
        if desenler is not None:
            temiz = [d.strip() for d in desenler if d and d.strip() and ".." not in d and "/" not in d and "\\" not in d]
            if temiz:
                conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('izlenen_desenler', ?) ON CONFLICT(anahtar) "
                             "DO UPDATE SET deger=excluded.deger", (json.dumps(temiz, ensure_ascii=False),))
    return ayarlar(conn)


@dataclass
class _Aday:
    imza: tuple
    ilk: float                       # bu imzanın ilk görüldüğü an (sabitlik ölçüsü)
    deneme: int = 0


@dataclass
class Izleyici:
    """Tek süreçte tek izleyici. ``tara(an)`` bir yoklama turudur (testler doğrudan çağırır)."""
    conn_fabrikasi: object
    yoklama_sn: float = YOKLAMA_SN
    sabit_sn: float = SABIT_SN
    adaylar: dict = field(default_factory=dict)          # yol → _Aday
    islenen: dict = field(default_factory=dict)          # yol → imza
    son_bakis: str | None = None
    son_alinan: dict | None = None
    _taban_alindi: bool = False
    _dur: threading.Event = field(default_factory=threading.Event)
    _is: threading.Thread | None = None

    # --------------------------------------------------------------------- dosyalar
    @staticmethod
    def _dosyalar(ayar: dict) -> list[Path]:
        out: list[Path] = []
        for k in ayar["klasorler"]:
            d = Path(k)
            try:
                if not d.is_dir():
                    continue
                for p in d.iterdir():
                    if p.is_file() and any(fnmatch.fnmatch(p.name.lower(), des.lower()) for des in ayar["desenler"]):
                        out.append(p)
            except OSError:
                continue
        return out

    @staticmethod
    def _imza(p: Path) -> tuple | None:
        try:
            st = p.stat()
        except OSError:
            return None
        return (st.st_size, st.st_mtime_ns)

    def taban_al(self, conn: sqlite3.Connection, ayar: dict) -> None:
        """Açılışta klasördeki eski raporlar yeniden işlenmesin: son uygulanan aktarımdan eski dosyalar ve
        (yeniler arasında) en yeni dışındakiler "görüldü" sayılır. En yeni ve daha yeni olan tek dosya adaydır."""
        son = conn.execute("SELECT dosya_zamani, bitis FROM ie_aktarim WHERE durum='uygulandi' ORDER BY id DESC LIMIT 1"
                           ).fetchone()
        sinir = None
        if son:
            t = zaman.oku(son[0] or son[1])
            sinir = t.timestamp() if t else None
        dosyalar = [(p, self._imza(p)) for p in self._dosyalar(ayar)]
        dosyalar = [(p, i) for p, i in dosyalar if i]
        yeniler = [(p, i) for p, i in dosyalar if sinir is None or i[1] / 1e9 > sinir + 1]
        en_yeni = max(yeniler, key=lambda x: x[1][1])[0] if yeniler else None
        for p, i in dosyalar:
            if p != en_yeni:
                self.islenen[str(p)] = i
        self._taban_alindi = True

    # --------------------------------------------------------------------- tur
    def tara(self, an: float | None = None) -> list[dict]:
        an = time.time() if an is None else an
        conn = self.conn_fabrikasi()
        try:
            ayar = ayarlar(conn)
            self.son_bakis = zaman.metin()
            if not ayar["acik"]:
                return []
            if not self._taban_alindi:
                self.taban_al(conn, ayar)
        finally:
            conn.close()
        sonuclar = []
        gorulen = set()
        for p in self._dosyalar(ayar):
            yol = str(p)
            gorulen.add(yol)
            imza = self._imza(p)
            if imza is None or self.islenen.get(yol) == imza:
                continue
            aday = self.adaylar.get(yol)
            if aday is None or aday.imza != imza:
                self.adaylar[yol] = _Aday(imza, an)
                continue
            if an - aday.ilk < self.sabit_sn:
                continue
            sonuc = self._isle(p, imza, aday)
            if sonuc is not None:
                sonuclar.append(sonuc)
        for yol in list(self.adaylar):
            if yol not in gorulen:
                self.adaylar.pop(yol, None)
        return sonuclar

    def _isle(self, p: Path, imza: tuple, aday: _Aday) -> dict | None:
        yol = str(p)
        try:
            veri = p.read_bytes()
        except OSError:
            return None                      # hâlâ yazılıyor / kilitli: sonraki turda
        dosya_zamani = imza[1] / 1e9
        try:
            s = aktarim.aktar(self.conn_fabrikasi, veri, p.name, dosya_zamani, None, yontem="klasor")
        except V2Hata as e:
            if e.kod == "aktarim_suruyor":
                return None                  # elle yükleme sürüyor: sonraki turda
            if e.kod in ("onay_gerekli", "rapor_tanimadi", "buyuk_dosya") or aday.deneme + 1 >= AZAMI_DENEME:
                self.islenen[yol] = imza
                self.adaylar.pop(yol, None)
            else:
                aday.deneme += 1
            sonuc = {"dosya_adi": p.name, "kod": e.kod, "mesaj": e.mesaj, "aktarim_id": e.ek.get("aktarim_id"),
                     "zaman": zaman.metin()}
            if e.kod == "onay_gerekli":
                sonuc["sonuc"] = f"Onay bekleyen rapor · {zaman.saat_dk(zaman.metin())} · {e.mesaj}"
            else:
                sonuc["sonuc"] = f"Rapor alınamadı: {e.mesaj}"
            self.son_alinan = sonuc
            _gunluk.info("Klasör izleme: %s → %s", p.name, e.kod)
            return sonuc
        except Exception as e:     # noqa: BLE001 — izleyici hiçbir koşulda sunucuyu düşürmez
            aday.deneme += 1
            if aday.deneme >= AZAMI_DENEME:
                self.islenen[yol] = imza
            _gunluk.exception("Klasör izleme: %s işlenemedi", p.name)
            return {"dosya_adi": p.name, "kod": "hata", "mesaj": type(e).__name__, "zaman": zaman.metin()}
        self.islenen[yol] = imza
        self.adaylar.pop(yol, None)
        if s.get("ayni_dosya"):
            sonuc = {"dosya_adi": p.name, "kod": "ayni_dosya", "aktarim_id": s.get("aktarim_id"), "zaman": zaman.metin(),
                     "sonuc": "Bu rapor zaten yüklenmişti."}
        else:
            f = s["fark"]
            sonuc = {"dosya_adi": p.name, "kod": "uygulandi", "aktarim_id": s["aktarim_id"], "zaman": zaman.metin(),
                     "sonuc": f"Yeni rapor alındı · {zaman.saat_dk(zaman.metin())} · {f['yeni']} yeni iş, "
                              f"{f['kaybolan']} kapandı"}
        self.son_alinan = sonuc
        _gunluk.info("Klasör izleme: %s → %s", p.name, sonuc["kod"])
        return sonuc

    # --------------------------------------------------------------------- iş parçacığı
    def _dongu(self) -> None:
        conn = self.conn_fabrikasi()             # ilk aktarım 19.706 binayı işlerken istekler beklemesin
        try:
            from . import sozluk
            sozluk.isit(conn)
        finally:
            conn.close()
        while not self._dur.is_set():
            try:
                self.tara()
            except Exception:      # noqa: BLE001
                _gunluk.exception("Klasör izleme turu başarısız")
            self._dur.wait(self.yoklama_sn)

    def baslat(self) -> None:
        if self._is and self._is.is_alive():
            return
        self._dur.clear()
        self._is = threading.Thread(target=self._dongu, name="rapor-izleme", daemon=True)
        self._is.start()

    def durdur(self) -> None:
        self._dur.set()
        if self._is:
            self._is.join(timeout=5)


_IZLEYICI: Izleyici | None = None
_KILIT = threading.Lock()


def _varsayilan_fabrika():
    from saha import db
    return db.baglan()


def baslat(conn_fabrikasi=None, *, zorla: bool = False) -> Izleyici | None:
    """Sunucu açılışında bir kez çağrılır (idempotent). Testlerde (pytest yüklüyse) ya da ``SAHA_IZLEME=0`` iken
    iş parçacığı AÇILMAZ — testler kullanıcının gerçek İndirilenler/Masaüstü klasörüne asla bakmaz."""
    global _IZLEYICI
    if not zorla and (os.environ.get("SAHA_IZLEME") == "0" or "pytest" in sys.modules):
        return None
    with _KILIT:
        if _IZLEYICI is None:
            _IZLEYICI = Izleyici(conn_fabrikasi or _varsayilan_fabrika)
        _IZLEYICI.baslat()
        return _IZLEYICI


def durdur() -> None:
    with _KILIT:
        if _IZLEYICI is not None:
            _IZLEYICI.durdur()


def izleyici() -> Izleyici | None:
    return _IZLEYICI


def durum(conn: sqlite3.Connection) -> dict:
    """GET /api/aktarim/izleme (``IzlemeDurumu``)."""
    a = ayarlar(conn)
    iz = _IZLEYICI
    return {"acik": a["acik"], "calisiyor": bool(iz and iz._is and iz._is.is_alive()),
            "klasorler": a["klasorler"], "desenler": a["desenler"], "klasorler_varsayilan": a["klasorler_varsayilan"],
            "yoklama_sn": iz.yoklama_sn if iz else YOKLAMA_SN, "sabit_sn": iz.sabit_sn if iz else SABIT_SN,
            "son_bakis": iz.son_bakis if iz else None, "son_alinan": iz.son_alinan if iz else None,
            "onay_bekleyen": aktarim.onay_bekleyenler(conn)}
