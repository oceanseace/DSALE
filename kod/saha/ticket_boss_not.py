"""Altyapı ticket'ı → BOSS notu (kendiliğinden): işlere "{ticket_no} ticket id ile altyapıdan çözüm bekler." düşülür.

Ne zaman: ticket Ticketlar satırında/seçicide oluşturulunca (``POST /api/ticket``), "+ abone ekle"
(``POST /api/ticket/{id}/isler``), ticket güncellenince (``PATCH``; numara sonradan yazılınca not o an gider) ve kurulum
engeliyle açılan/bağlanan ticket'ta (``operasyon/v2/akis.py`` → ``_engel_bagla`` · ``ticket_bagla``). Hepsi ``esitle``.

Metin (``not_metni``): ticket numarası varsa ``NOT_NUMARALI``; numarasızken HİÇBİR ŞEY gitmez; Durum=HATA (ek kapasite
açılamadı) ise "Ek kapasite talebi açılamadı: <kullanıcının ticket'a yazdığı son not>" (``hata_metni``; not yoksa
``NOT_HATA``) — HATA iken not eklenince/değişince yeni metin bir kez gider. Kapalı ticket'a not gitmez (silinen ticket yoktur).

Hangi işler (``hedefler``): ticket'a bağlı (``ticket_is`` + ``is_emri.ticket_id``) AÇIK işler her zaman; bunların ve
ticket'ın Müşteri No'larının müşterisi PERAKENDE ise o müşterinin BÜTÜN açık işleri (kurulum + kanal şikâyeti ...),
TOPTAN ise (``toptan_mi``: tek müşteri no'su çok aboneyi taşır, ör. Vodafone) yalnız bağlı iş(ler).

Yazma yolu: doğrulanmış not yolunun AYNISI — ``akis.not_ekle`` (iş olayı "not" + ``boss_yazma`` kuyruğu, task/note).
Not anahtarı (``ayar.boss_yazma_not``) kapalıyken hiçbir şey yazılmaz (sonra açılınca bir sonraki olayda gider).
Tekrar yok: (ticket, iş, metin) başına bir not — ``ticket_boss_not`` yan tablosu; metin değişirse (numara eklendi)
yeniden gider. ASLA hata fırlatmaz: asıl eylemi (ticket kaydı, engel) bozmaz.
Durum (ticket çekmecesi, iş başına "BOSS notu: gidiyor / ✓ / hata"): ``durumlar`` → ``ticket.getir`` ``boss_notlari``.
"""
from __future__ import annotations

import logging
import sqlite3

from . import ayarlar
from . import ticket as tk

_log = logging.getLogger("saha.ticket_boss_not")

NOT_NUMARALI = "{ticket_no} ticket id ile altyapıdan çözüm bekler."
NOT_HATA = "Ek kapasite talebi açılamadı (hata), altyapıdan çözüm bekler."
# Durum=BÖLGE (ticket bölgeye iletildi) ve numara yoksa: askı da bu açıklamayla yapılır (numara varsa NOT_NUMARALI).
NOT_BOLGE = "Altyapı talebi bölgeye iletildi, çözüm bekler."

# Toptan (wholesale) müşteri: BOSS ``segment`` TOPTAN, satış kanalı toptan operatör, ürün "Toptan", ya da çok açık iş.
TOPTAN_ACIK_IS = 20                       # bundan FAZLA açık işi olan tek müşteri no toptandır (ör. 23722338: 48)
_TOPTAN_KANAL = ("TOPTAN", "WHOLESALE", "VODAFONE", "MILLENICOM", "GOKNET", "DSMART", "ANDROMEDA")
_TOPTAN_URUN = ("TOPTAN", "WHOLESALE")

_SEMA = ("CREATE TABLE IF NOT EXISTS ticket_boss_not (ticket_id INTEGER NOT NULL, is_no TEXT NOT NULL, "
         "task_no TEXT, metin TEXT NOT NULL, olay_id INTEGER, zaman TEXT NOT NULL, "
         "PRIMARY KEY (ticket_id, is_no, metin))")


def sema(conn: sqlite3.Connection) -> None:
    conn.execute(_SEMA)


# Ticket geçmişindeki SİSTEM notları (kullanıcının "Not eklendi"si değil): HATA metnine baz alınmaz.
_SISTEM_NOTU = ("Oluşturuldu", "Excel'den aktarıldı", "Silindi", "İş eklendi:", "İş çıkarıldı:",
                "Bekleyen iş eklendi", "İşten açıldı")
HATA_NOT_EN_COK = 600                     # "Ek kapasite talebi açılamadı: <son not>" en çok bu kadar karakter


def son_kullanici_notu(conn: sqlite3.Connection, ticket_id: int) -> str:
    """Ticket geçmişinde kullanıcının yazdığı SON not (sistem notları atlanır); yoksa ''."""
    for (notu,) in conn.execute("SELECT notu FROM ticket_gecmis WHERE ticket_id=? AND COALESCE(TRIM(notu),'') <> '' "
                                "ORDER BY id DESC", (int(ticket_id),)):
        n = " ".join(str(notu).split())
        if n and not n.startswith(_SISTEM_NOTU):
            return n
    return ""


def hata_metni(son_not: str | None) -> str:
    """Durum=HATA notu: kullanıcının son notu varsa "Ek kapasite talebi açılamadı: <not>" (uzunsa kısaltılır)."""
    n = " ".join(str(son_not or "").split())
    if not n:
        return NOT_HATA
    bas = "Ek kapasite talebi açılamadı: "
    if len(bas) + len(n) > HATA_NOT_EN_COK:
        n = n[:HATA_NOT_EN_COK - len(bas) - 1].rstrip(" |,;.") + "…"
    return bas + n


def not_metni(t: dict, son_not: str | None = None) -> str | None:
    """Ticket → işlere düşülecek not; None: (henüz) not yok (kapalı ya da numarasız).
    HATA: ``hata_metni(son_not)`` (``son_not`` = ``son_kullanici_notu``)."""
    durum = t.get("durum")
    if durum not in tk.ACIK_DURUMLAR:
        return None
    if durum == "HATA":
        return hata_metni(son_not)
    no = str(t.get("ticket_no") or "").strip()
    if not no and durum == "BÖLGE":
        return NOT_BOLGE
    return NOT_NUMARALI.format(ticket_no=no) if no else None


def _icerir(metin, desenler) -> bool:
    s = tk._sade(str(metin or ""))
    return bool(s) and any(d in s for d in desenler)


def toptan_mi(isler: list[dict], ham: dict[str, dict] | None = None) -> bool:
    """TEK kural: bir müşteri no'nun AÇIK işleri (``satis_kanali``, ``task_no``) ve BOSS ham alanları
    (task no → {segment, saleChannel, productInfo}) → toptan mı.

    Toptan: ``TOPTAN_ACIK_IS``'ten fazla açık iş · satış kanalı/``saleChannel`` toptan/Vodafone/Millenicom/GÖKNET/
    D-Smart (Andromeda) · ``segment`` TOPTAN/Wholesale · ürün (``productInfo``) "Toptan"."""
    if len(isler) > TOPTAN_ACIK_IS:
        return True
    ham = ham or {}
    for x in isler:
        h = ham.get(str(x.get("task_no") or "")) or {}
        if _icerir(x.get("satis_kanali"), _TOPTAN_KANAL) or _icerir(h.get("saleChannel"), _TOPTAN_KANAL) \
                or _icerir(h.get("segment"), _TOPTAN_KANAL) or _icerir(h.get("productInfo"), _TOPTAN_URUN):
            return True
    return False


def _ham(conn: sqlite3.Connection, task_nolar) -> dict[str, dict]:
    nolar = sorted({str(t) for t in task_nolar if t})
    out: dict[str, dict] = {}
    try:
        for i in range(0, len(nolar), 500):
            parca = nolar[i:i + 500]
            for r in conn.execute(
                    "SELECT task_no, json_extract(veri,'$.segment'), json_extract(veri,'$.saleChannel'), "
                    f"json_extract(veri,'$.productInfo') FROM boss_ham WHERE task_no IN ({','.join('?' * len(parca))})",
                    parca):
                out[str(r[0])] = {"segment": r[1], "saleChannel": r[2], "productInfo": r[3]}
    except sqlite3.Error:
        return {}
    return out


_ALANLAR = "is_no, boss_task_no AS task_no, task_adi, satis_kanali, TRIM(musteri_no) AS musteri_no"
_ACIK = "durum NOT IN ('cozuldu','kapandi')"


def hedefler(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Not düşülecek AÇIK BOSS işleri: {is_no, task_no, task_adi, musteri_no, neden: 'bagli'|'musteri'}."""
    tk.sema(conn)
    t = conn.execute("SELECT musteri FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if t is None:
        return []
    secilen = [str(r[0]) for r in conn.execute("SELECT task_no FROM ticket_is WHERE ticket_id=?", (ticket_id,))]
    try:
        bagli = [dict(r) for r in conn.execute(
            f"SELECT {_ALANLAR} FROM is_emri WHERE {_ACIK} AND (ticket_id=? OR boss_task_no IN "
            f"({','.join('?' * len(secilen)) or 'NULL'}) OR is_no IN ({','.join('?' * len(secilen)) or 'NULL'})) "
            "ORDER BY acilis, is_no", (ticket_id, *secilen, *secilen))]
    except sqlite3.Error:
        return []                               # iş emri tablosu yoksa (yalnız satış kurulumu)
    out: dict[str, dict] = {}
    for x in bagli:
        out[x["is_no"]] = {**x, "neden": "bagli"}
    musteriler = list(dict.fromkeys([*(x["musteri_no"] for x in bagli if x["musteri_no"]),
                                     *tk.musteri_nolari(t["musteri"])]))
    for m in musteriler:
        isler = [dict(r) for r in conn.execute(
            f"SELECT {_ALANLAR} FROM is_emri WHERE TRIM(musteri_no)=? AND {_ACIK} ORDER BY acilis, is_no", (m,))]
        if not isler or toptan_mi(isler, _ham(conn, [x["task_no"] for x in isler[:TOPTAN_ACIK_IS + 1]])):
            continue                            # toptan: yalnız bağlı iş(ler)
        for x in isler:
            out.setdefault(x["is_no"], {**x, "neden": "musteri"})
    return [x for x in out.values() if x["task_no"]]


def esitle(conn: sqlite3.Connection, ticket_id: int | None, k: dict | None) -> dict:
    """Ticket'ın notunu eksik kalan işlere düşer (etkisiz; tekrar yok) ve aynı işleri BOSS'ta askıya alır / ticket
    çözüldüyse önceki ekibe geri atar (``ticket_boss_aski.esitle``). Dönüş: {metin, gonderilen: [task no], aski}.
    Çağıranın işlemi açıksa onun içinde (SAVEPOINT) koşar. Hata fırlatmaz."""
    sonuc = _not_esitle(conn, ticket_id, k)
    try:
        from . import ticket_boss_aski
        sonuc["aski"] = ticket_boss_aski.esitle(conn, ticket_id, k)
    except Exception:                           # noqa: BLE001 — asıl eylemi bozmaz
        _log.exception("Ticket #%s otomatik askı", ticket_id)
    return sonuc


def _not_esitle(conn: sqlite3.Connection, ticket_id: int | None, k: dict | None) -> dict:
    sonuc: dict = {"metin": None, "gonderilen": []}
    if ticket_id is None:
        return sonuc
    try:
        from operasyon.v2 import akis, boss_yazma
        from operasyon.v2.islem import islem
    except ImportError:
        return sonuc                            # iş modülü yok
    try:
        sema(conn)
        tk.sema(conn)
        t = conn.execute("SELECT t.id, t.ticket_no, t.durum FROM ticket t WHERE t.id=?", (int(ticket_id),)).fetchone()
        if t is None:
            return sonuc
        metin = not_metni(dict(t), son_kullanici_notu(conn, int(ticket_id)) if t["durum"] == "HATA" else None)
        sonuc["metin"] = metin
        if not metin:
            return sonuc
        if not boss_yazma.gonderilir(conn, "not"):
            sonuc["kapali"] = True
            return sonuc
        for h in hedefler(conn, int(ticket_id)):
            if conn.execute("SELECT 1 FROM ticket_boss_not WHERE ticket_id=? AND is_no=? AND metin=?",
                            (int(ticket_id), h["is_no"], metin)).fetchone():
                continue
            try:
                with islem(conn):
                    olay_id = akis.not_ekle(conn, h["is_no"], metin, k)
                    conn.execute("INSERT INTO ticket_boss_not (ticket_id, is_no, task_no, metin, olay_id, zaman) "
                                 "VALUES (?,?,?,?,?,?)", (int(ticket_id), h["is_no"], h["task_no"], metin, olay_id,
                                                          ayarlar.zaman_metni()))
                sonuc["gonderilen"].append(h["task_no"])
            except Exception:                   # noqa: BLE001 — tek işin hatası ötekileri durdurmaz
                _log.exception("Ticket #%s notu işe düşülemedi (%s)", ticket_id, h["is_no"])
    except Exception:                           # noqa: BLE001 — asıl eylemi bozmaz
        _log.exception("Ticket #%s BOSS notu", ticket_id)
    return sonuc


def durumlar(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Ticket çekmecesi: iş başına SON not ve BOSS durumu {task_no, is_no, task_adi, metin, durum: gonderiliyor|
    gonderildi|hata|kapali, hata?, zaman}. Kişisel veri yok."""
    try:
        from operasyon.v2 import boss_yazma
    except ImportError:
        return []
    try:
        sema(conn)
        satirlar = conn.execute(
            "SELECT n.is_no, n.task_no, n.metin, n.olay_id, n.zaman, e.task_adi FROM ticket_boss_not n "
            "LEFT JOIN is_emri e ON e.is_no=n.is_no WHERE n.ticket_id=? ORDER BY n.zaman, n.rowid",
            (int(ticket_id),)).fetchall()
    except sqlite3.Error:
        return []
    son: dict[str, sqlite3.Row] = {}
    for r in satirlar:
        son[r["is_no"]] = r
    out = []
    onbellek: dict[str, dict] = {}
    for is_no, r in son.items():
        if is_no not in onbellek:
            onbellek[is_no] = boss_yazma.not_durumlari(conn, is_no)
        b = onbellek[is_no].get(int(r["olay_id"] or 0)) or {"durum": "gonderiliyor"}
        o = {"is_no": is_no, "task_no": r["task_no"] or "", "task_adi": r["task_adi"] or "", "metin": r["metin"],
             "durum": b["durum"], "zaman": b.get("zaman") or r["zaman"]}
        if b.get("hata"):
            o["hata"] = b["hata"]
        out.append(o)
    return out
