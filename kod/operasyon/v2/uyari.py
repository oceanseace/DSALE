"""İş satırı uyarıları (``IsSatir.uyarilar``: [{tur, metin}]) — Uyarı sütunu ve İş çekmecesinin üstü.

- ``altyapi``: iş açık bir ticket'a bağlı (kurulum engeli) ya da binasında (bina_serial) / lokasyonunda (Loc ID)
  açık ticket var. Kaynak Ticketlar ekranıyla ve engel bağıyla AYNI: ``saha.ticket.acik_ticketlar`` (+
  ``acik_lokasyonlar``, ``lokasyon_anahtari``). Teknisyen gönderilmeden önce bilinsin.
- ``kanal_sikayeti``: müşterinin açık kanal şikâyeti varsa şikâyet DIŞINDAKİ açık işlerine (şikâyet satırına değil);
  tabloda yalnız ⚠ simgesi (altyapı ⛔), metin ipucunda.
- ``tekrar``: AÇIK arıza/şikâyet işi, aynı müşteride son ``TEKRAR_GUN`` günde KAPANMIŞ bir arıza/şikâyetten sonra
  açıldı (tekrar gelen iş). Tabloda küçük ↻; ipucu "30 gün içinde tekrar · önceki 200xxxxx kapanış 01.10".
  Kapanmış işler yanıt başına TEK sorguyla okunur.
"Aynı müşteri" her üçünde de ``iliskili.Iliski`` kuralıdır: perakendede müşteri no, TOPTAN müşteride abone (Lokasyon
Birimi / Lokasyon ID + adres) — toptan müşterinin tek no'su yüzlerce aboneyi ilişkilendirmesin.
Giriş: ``Uyarilar(conn)`` bir yanıt için bir kez kurulur (gorunum.Baglam.uyari, tembel); ``liste(r)`` satır başına.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from operasyon import is_emri as ie
from saha import ticket as tk

_KONU = {"SİNYAL": "sinyal zayıf", "EK SP": "ek kapasite", "GÜZERGAH": "güzergah"}    # ALTYAPI/DİĞER: ek yok
TEKRAR_GUN = 30
_ARIZA = ("ARIZA", "PROBLEM", "SIKAYET")


def kanal_sikayeti_mi(task_adi) -> bool:
    from . import iliskili                          # ilişkili akışla aynı sınıflama
    return iliskili.kategori(task_adi) == "sikayet"


def ariza_mi(task_adi) -> bool:
    """Arıza/şikâyet işi (Bağlantı Problemi, TV+ Arıza, Doping Arıza Bildirimi, Kanal Şikâyeti, Arama Problemi …)."""
    s = ie.sade(task_adi or "")
    return any(x in s for x in _ARIZA)


def _zaman(metin) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(metin or "")[:19].replace("T", " "))
    except ValueError:
        return None


class Uyarilar:
    """Açık ticket'lar (bina + Loc ID), işlerin ilişki anahtarları ve son kapanan arızalar — yanıt boyunca bir kez."""

    def __init__(self, conn: sqlite3.Connection):
        from .iliskili import Iliski
        acik = tk.acik_ticketlar(conn)
        self.ticket: dict[int, str] = {int(t["id"]): t["konu"] for t in acik}
        self.bina: dict[str, str] = {}
        for t in acik:
            if t["bina_serial"]:
                self.bina.setdefault(str(t["bina_serial"]), t["konu"])
        self.lokasyon = tk.acik_lokasyonlar(conn, acik)
        self.il = Iliski(conn)
        self._conn = conn
        self._kapanan: dict[str, list[tuple]] | None = None

    # ------------------------------------------------------------------ ilişki
    def _diger(self, r) -> list[tuple[str, str]]:
        """Satırın ilişkili öbür AÇIK işleri [(is_no, task adı)]. Açık işler ``Iliski``'den; listede olmayan satır
        (ör. ticket ekranının saklanan işi) perakende müşteri no'suyla eşlenir (toptan müşteride ilişki yok)."""
        no = r["is_no"]
        if no in self.il.anahtar:
            return [(d, self.il.bilgi[d][1]) for d in self.il.digerleri(no)]
        m = str(r["musteri_no"] or "").strip()
        if not m or m in self.il.toptan:
            return []
        return [(d, self.il.bilgi[d][1]) for d in self.il.grup.get(f"m:{m}", []) if d != no]

    def _altyapi(self, r) -> dict | None:
        bagli = self.ticket.get(int(r["ticket_id"])) if r["ticket_id"] else None
        if bagli is not None:
            ek = f" ({_KONU[bagli]})" if bagli in _KONU else ""
            return {"tur": "altyapi", "metin": f"Altyapı ticket'ı bekleniyor{ek}"}
        konu = self.bina.get(r["bina_serial"] or "")
        if konu is not None:
            ek = f" ({_KONU[konu]})" if konu in _KONU else ""
            return {"tur": "altyapi", "metin": f"Bu binada açık altyapı ticket'ı var{ek}"}
        if r["lokasyon"] and tk.lokasyon_anahtari(r["lokasyon"]) in self.lokasyon:
            return {"tur": "altyapi", "metin": "Bu lokasyonda açık altyapı ticket'ı var"}
        return None

    def _kanal(self, r) -> dict | None:
        """Kanal şikâyeti olan müşterinin şikâyet DIŞINDAKİ açık işlerinde ⚠ (şikâyet satırının kendisinde yok)."""
        if kanal_sikayeti_mi(r["task_adi"]):
            return None
        if any(kanal_sikayeti_mi(t) for _, t in self._diger(r)):
            return {"tur": "kanal_sikayeti", "metin": "Bu müşterinin kanal şikâyeti var"}
        return None

    # ------------------------------------------------------------------ tekrar gelen iş
    def _kapananlar(self) -> dict[str, list[tuple]]:
        """Son 2×TEKRAR_GUN günde kapanmış arıza/şikâyet işleri, anahtar → [(kapanış, açılış, task no)] — TEK sorgu.
        Anahtar: ``m:<müşteri no>`` ve ``l:<Lokasyon ID>|<adres>`` (kapanmış işin BOSS ham alanı silinmiştir; toptan
        abone bu ikincisiyle eşlenir)."""
        if self._kapanan is not None:
            return self._kapanan
        from .iliskili import lok_adres
        self._kapanan = {}
        from . import zaman
        sinir = (zaman.simdi() - dt.timedelta(days=2 * TEKRAR_GUN)).strftime("%Y-%m-%d")
        try:
            satirlar = self._conn.execute(
                "SELECT COALESCE(boss_task_no, is_no), TRIM(musteri_no), lokasyon, adres, task_adi, acilis, kapanis "
                "FROM is_emri WHERE durum IN ('cozuldu','kapandi') AND kapanis >= ? AND musteri_no IS NOT NULL "
                "AND TRIM(musteri_no) <> ''", (sinir,)).fetchall()
        except sqlite3.Error:
            satirlar = []
        for tno, m, lok, adres, task, acilis, kapanis in satirlar:
            if not ariza_mi(task):
                continue
            k, a = _zaman(kapanis), _zaman(acilis)
            if k is None:
                continue
            for anahtar in (f"m:{m}", lok_adres(lok, adres)):
                if anahtar:
                    self._kapanan.setdefault(anahtar, []).append((k, a, str(tno)))
        return self._kapanan

    def tekrar(self, r) -> dict | None:
        """AÇIK arıza/şikâyet işi, aynı müşteride (toptanda aynı abonede) son 30 günde kapanmış arıza/şikâyetten sonra
        açıldıysa {tur: 'tekrar', metin, onceki, kapanis}. En yakın önceki kapanış seçilir."""
        if not ariza_mi(r["task_adi"]):
            return None
        acilis = _zaman(r["acilis"])
        if acilis is None:
            return None
        m = str(r["musteri_no"] or "").strip()
        if r["is_no"] in self.il.anahtar:
            anahtarlar = list(self.il.anahtar[r["is_no"]])
            toptan = self.il.musteri_no.get(r["is_no"]) in self.il.toptan
        else:
            toptan = m in self.il.toptan
            anahtarlar = [f"m:{m}"] if m and not toptan else []
        if toptan:                                       # kapanmış işin Lokasyon Birimi yok: Loc ID + adres
            from .iliskili import lok_adres
            anahtarlar = [a for a in [lok_adres(r["lokasyon"], r["adres"] if "adres" in r.keys() else None)] if a]
        anahtarlar_ = r.keys()
        kendi = {str(r["is_no"])} | {str(r[a]) for a in ("boss_task_no", "task_no") if a in anahtarlar_ and r[a]}
        kapanan = self._kapananlar()
        sinir = acilis - dt.timedelta(days=TEKRAR_GUN)
        en: tuple | None = None
        for a in anahtarlar:
            for k, onceki_acilis, tno in kapanan.get(a, ()):
                if tno in kendi:
                    continue
                if sinir <= k and (onceki_acilis is None or onceki_acilis < acilis) and (en is None or k > en[0]):
                    en = (k, tno)
        if en is None:
            return None
        return {"tur": "tekrar", "metin": f"{TEKRAR_GUN} gün içinde tekrar · önceki {en[1]} kapanış "
                                          f"{en[0].strftime('%d.%m')}", "onceki": en[1],
                "kapanis": en[0].strftime("%Y-%m-%d %H:%M")}

    def iliskili(self, r) -> tuple[str | None, list[str]]:
        """İlişkili akış (``iliskili.metin``) + ilişkili işlerin numaraları (task no; yoksa iş no). Açık işte."""
        from . import iliskili
        if r["durum"] in ("cozuldu", "kapandi"):
            return None, []
        diger = self._diger(r)
        if not diger:
            return None, []
        return (iliskili.metin(r["task_adi"] or "", [t for _, t in diger]),
                [self.il.bilgi[no][0] for no, _ in diger])

    def liste(self, r) -> list[dict]:
        """Açık iş için uyarılar (kapanmış işte boş)."""
        if r["durum"] in ("cozuldu", "kapandi"):
            return []
        return [u for u in (self._altyapi(r), self._kanal(r), self.tekrar(r)) if u]
