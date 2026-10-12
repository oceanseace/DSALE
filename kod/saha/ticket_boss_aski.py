"""Altyapı ticket'ı → işler BOSS'ta kendiliğinden askıya (Abone Kaynaklı > Ulaşılamadı); ticket çözülünce önceki BOSS
ekibine geri atama.

Ne zaman: ticket notunun gittiği her an (``ticket_boss_not.esitle`` bunu da çağırır: Ticketlar satırı/seçici, "+ abone
ekle", ticket güncellemesi, kurulum engeli, ``ticket_bagla``) ve her BOSS eşitlemesinin sonunda (``yenile``: süre dolmadan
yeniden askı, kapanmış ticket'ın çözümü; en çok yarım saatte bir).

Hangi işler: ticket notuyla AYNI hedefler (``ticket_boss_not.hedefler``: bağlı işler + perakende müşterinin bütün açık
işleri; toptanda yalnız bağlı iş). Askı ancak not metni varken (numaralı ya da HATA) yapılır — açıklama o metindir.

Askı (``boss_yazma`` 'aski' kaydı, toplu askıyla aynı yazma yolu): bütün askılar gibi varsayılan çift
``boss_yazma.VARSAYILAN_ASKI`` (kullanıcı kararı 09.10: ABONE "Abone Kaynaklı" > "Ulaşılamadı"; açıklama = ticket notu).
Alt neden kimliği kategoriye göre değişir: gönderimde işin KENDİ kategorisinin listesinden seçilir
(``boss_yazma.varsayilan_kimlikler``); liste yoksa eklentiden istenir ve kayıt bekler (çekmecede
"alt_neden_bekleniyor"). (Eski: NETWORK + alt neden seçimi.) Bitiş: şimdi + 7 gün (BOSS'un üst sınırı); ticket açık kaldıkça bitişe
``YENILE_SAAT`` kala yeniden askı. Askıdan ÖNCE işin BOSS ekibi saklanır (askı BOSS'ta ekibi işten alır).

Çözüm (ticket ÇÖZÜLDÜ/KAPATILDI): askıdaki her iş önceki BOSS ekibine ``akis.ata`` ile (atama yazma yolu) geri atanır;
dilim ``ayar.ticket_cozum_slot`` (varsayılan "08:00-10:00") bir sonraki iş gününde. Önceki ekip yoksa iş atanmamış kalır
ve ticket çekmecesinde "ekip yok" görünür. Bizim durum → Aranacak kuralı ``akis.ticket_degisti``'de (değişmedi).
İPTAL: yeniden askı durur, geri atama yapılmaz.

Anahtarlar (Administrator, Ayarlar): ``ticket_otomatik_aski`` ve ``ticket_cozum_yeniden_ata`` (varsayılan 'acik').
Tablo ``ticket_boss_aski`` (ticket, iş) başına bir satır. ASLA hata fırlatmaz: asıl eylemi (ticket kaydı) bozmaz.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sqlite3
import time

from . import ticket as tk

_log = logging.getLogger("saha.ticket_boss_aski")

AYAR_ASKI = "ticket_otomatik_aski"
AYAR_YENIDEN_ATA = "ticket_cozum_yeniden_ata"
AYAR_SLOT = "ticket_cozum_slot"
VARSAYILAN_SLOT = "08:00-10:00"
SURE_GUN = 7                           # BOSS askı bitişi en çok 7 gün
YENILE_SAAT = 36                       # bitişe bu kadar kala yeniden askı
YENILE_ARALIK_SN = 30 * 60
_COZEN = ("ÇÖZÜLDÜ", "KAPATILDI")
_SON_YENILE: list[float] = [0.0]

# durum: askida (askı kaydı kuyrukta / BOSS'ta) · atandi (çözüldü, önceki ekibe geri atandı) · ekipsiz (çözüldü, önceki
# ekip yok: atanmamış) · atanamadi (çözüldü, atama reddedildi; hata metni) · birakildi (iş kapandı / ticket iptal)
_SEMA = ("CREATE TABLE IF NOT EXISTS ticket_boss_aski (ticket_id INTEGER NOT NULL, is_no TEXT NOT NULL, task_no TEXT, "
         "onceki_teknik_id INTEGER, onceki_ekip TEXT, durum TEXT NOT NULL, kayit_id INTEGER, bitis TEXT, metin TEXT, "
         "aski_zaman TEXT, cozum_zaman TEXT, atama_bas TEXT, hata TEXT, PRIMARY KEY (ticket_id, is_no))")


def sema(conn: sqlite3.Connection) -> None:
    conn.execute(_SEMA)


def sifirla() -> None:
    _SON_YENILE[0] = 0.0


def acik_mi(conn: sqlite3.Connection, anahtar: str) -> bool:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return ((r[0] if r and r[0] else None) or "acik") == "acik"


def cozum_slotu(conn: sqlite3.Connection) -> tuple[str, str]:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (AYAR_SLOT,)).fetchone()
    return slot_coz(r[0] if r else None) or slot_coz(VARSAYILAN_SLOT)


def slot_coz(metin) -> tuple[str, str] | None:
    """"08:00-10:00" → ("08:00", "10:00"); geçersizse None (bitiş başlangıçtan sonra, 06:00–22:00 arası)."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", str(metin or ""))
    if not m:
        return None
    a, b = (int(m[1]), int(m[2])), (int(m[3]), int(m[4]))
    if not (6 <= a[0] <= 22 and 6 <= b[0] <= 22 and a[1] < 60 and b[1] < 60 and a < b):
        return None
    return f"{a[0]:02d}:{a[1]:02d}", f"{b[0]:02d}:{b[1]:02d}"


def cozum_dilimi(conn: sqlite3.Connection, simdi: dt.datetime) -> tuple[str, str]:
    """Bir sonraki iş günü (hafta sonu ve resmî tatiller atlanır) + ``ticket_cozum_slot``."""
    from operasyon.v2 import kurallar
    try:
        tatiller = kurallar.oku(conn, "resmi_tatiller") or []
    except Exception:          # noqa: BLE001
        tatiller = []
    gun = kurallar.is_gunu_ekle(simdi, 1, tatiller).date()
    bas, bit = cozum_slotu(conn)
    return f"{gun.isoformat()} {bas}:00", f"{gun.isoformat()} {bit}:00"


def _onceki_ekip(conn: sqlite3.Connection, r) -> tuple[int | None, str | None]:
    """İşin şu anki BOSS ekibi (eşli teknisyen) — yoksa uygulamadaki atama — yoksa son bilinen ekip
    (``son_bilinen_ekip``: iş elle / BOSS'ta askıya alınınca BOSS ekibi işten düşer; anlık görüntü boş kalmasın)."""
    from operasyon import is_emri as ie
    from operasyon.v2 import kisi
    ekip = str(r["boss_ekip"] or "").strip()
    if ekip:
        tid = kisi.boss_ekip_haritasi(conn).get(ie.anahtar(ekip))
        if tid:
            return int(tid), ekip
    if r["atanan_id"]:
        k = kisi.kisiler(conn, [r["atanan_id"]]).get(r["atanan_id"]) or {}
        return int(r["atanan_id"]), k.get("boss_ekip") or k.get("ad")
    tid, ad = son_bilinen_ekip(conn, r["is_no"])
    return tid, ad or ekip or None


def _json(metin) -> dict:
    try:
        d = json.loads(metin) if metin else {}
    except (ValueError, TypeError):
        return {}
    return d if isinstance(d, dict) else {}


def son_bilinen_ekip(conn: sqlite3.Connection, is_no: str) -> tuple[int | None, str | None]:
    """İşin SON BİLİNEN ekibi (teknisyen id, ekip adı): (1) iş olay geçmişi — en yeni olaydan geriye, BOSS ekibi
    (``boss_ekip``, eşli teknisyene) ya da uygulama ataması (``atanan_id``); (2) BOSS'a başarılı gitmiş son atama
    yazması. Hiçbiri yoksa (None, ad|None): ticket çekmecesinde "önceki ekip bilinmiyor — elle atayın"."""
    from operasyon import is_emri as ie
    from operasyon.v2 import kisi
    harita = kisi.boss_ekip_haritasi(conn)
    ad_yalniz = None

    def kisi_adi(tid):
        k = kisi.kisiler(conn, [tid]).get(tid) or {}
        return k.get("boss_ekip") or k.get("ad")

    try:
        olaylar = conn.execute("SELECT eski, yeni FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 300",
                               (is_no,)).fetchall()
    except sqlite3.Error:
        olaylar = []
    for eski, yeni in olaylar:
        for d in (_json(yeni), _json(eski)):
            ekip = str(d.get("boss_ekip") or "").strip()
            if ekip:
                tid = harita.get(ie.anahtar(ekip))
                if tid:
                    return int(tid), ekip
                ad_yalniz = ad_yalniz or ekip
            if isinstance(d.get("atanan_id"), int) and d["atanan_id"] > 0:
                return d["atanan_id"], kisi_adi(d["atanan_id"])
    try:
        for (girdi,) in conn.execute(
                "SELECT girdi FROM boss_yazma WHERE is_no=? AND tur='atama' AND durum='gonderildi' AND "
                "(sonuc LIKE '%\"return_kodu\": 0%' OR sonuc LIKE '%boss_goruntusu%') ORDER BY id DESC LIMIT 20",
                (is_no,)):
            tid = _json(girdi).get("teknik_id")
            if isinstance(tid, int) and tid > 0:
                return tid, kisi_adi(tid)
    except sqlite3.Error:
        pass
    return None, ad_yalniz


def _askiya_al(conn, ticket_id: int, h: dict, metin: str, konu: str | None, k: dict | None,
               simdi: dt.datetime) -> tuple[int | None, str]:
    from operasyon.v2 import boss_yazma, zaman
    bitis = simdi + dt.timedelta(days=SURE_GUN) - dt.timedelta(minutes=5)
    v = boss_yazma.VARSAYILAN_ASKI
    girdi = {"neden": f"{v['neden_ad']} > {v['alt_ad']} (altyapı)", "boss_neden_ad": v["neden_kod"],
             "boss_alt_ad": v["alt_ad"], "konu": konu or "", "boss_bitis": zaman.metin(bitis), "notu": metin,
             "kaynak": "ticket", "ticket_id": int(ticket_id)}
    kid = boss_yazma.kuyruga_ekle(conn, "aski", h["is_no"], girdi, k)
    return kid, zaman.metin(bitis)


def esitle(conn: sqlite3.Connection, ticket_id: int | None, k: dict | None) -> dict:
    """Ticket açıksa hedef işleri askıya alır (tekrar yok); çözüldüyse geri atar. Hata fırlatmaz."""
    sonuc: dict = {"askiya": [], "atanan": [], "ekipsiz": []}
    if ticket_id is None:
        return sonuc
    try:
        from operasyon.v2 import zaman
        from operasyon.v2.islem import islem

        from . import ticket_boss_not as tbn
    except ImportError:
        return sonuc
    try:
        sema(conn)
        tk.sema(conn)
        t = conn.execute("SELECT id, ticket_no, durum, konu FROM ticket WHERE id=?", (int(ticket_id),)).fetchone()
        if t is None:
            return sonuc
        if t["durum"] in tk.KAPALI_DURUMLAR:
            return {**sonuc, **cozum(conn, int(ticket_id), k)}
        if not acik_mi(conn, AYAR_ASKI):
            return sonuc
        metin = tbn.not_metni(dict(t), tbn.son_kullanici_notu(conn, int(ticket_id)) if t["durum"] == "HATA" else None)
        if not metin:
            return sonuc                         # numarasız ticket: not da askı da numara girilince
        simdi = zaman.simdi()
        for h in tbn.hedefler(conn, int(ticket_id)):
            if conn.execute("SELECT 1 FROM ticket_boss_aski WHERE ticket_id=? AND is_no=?",
                            (int(ticket_id), h["is_no"])).fetchone():
                continue
            r = conn.execute("SELECT is_no, boss_ekip, atanan_id FROM is_emri WHERE is_no=?", (h["is_no"],)).fetchone()
            if r is None:
                continue
            try:
                with islem(conn):
                    tid, ekip = _onceki_ekip(conn, r)
                    kid, bitis = _askiya_al(conn, int(ticket_id), h, metin, t["konu"], k, simdi)
                    conn.execute("INSERT INTO ticket_boss_aski (ticket_id, is_no, task_no, onceki_teknik_id, onceki_ekip, "
                                 "durum, kayit_id, bitis, metin, aski_zaman) VALUES (?,?,?,?,?,'askida',?,?,?,?)",
                                 (int(ticket_id), h["is_no"], h["task_no"], tid, ekip, kid, bitis, metin,
                                  zaman.metin(simdi)))
                sonuc["askiya"].append(h["task_no"])
            except Exception:                   # noqa: BLE001 — tek işin hatası ötekileri durdurmaz
                _log.exception("Ticket #%s askısı işe yazılamadı (%s)", ticket_id, h["is_no"])
    except Exception:                           # noqa: BLE001 — asıl eylemi bozmaz
        _log.exception("Ticket #%s otomatik askı", ticket_id)
    return sonuc


def cozum(conn: sqlite3.Connection, ticket_id: int, k: dict | None) -> dict:
    """Kapanan ticket: askıdaki işler önceki ekibe geri atanır (ÇÖZÜLDÜ/KAPATILDI; anahtar açıksa) ya da bırakılır."""
    from operasyon.v2 import akis, zaman
    from operasyon.v2.hatalar import V2Hata
    from operasyon.v2.islem import islem
    sonuc: dict = {"atanan": [], "ekipsiz": []}
    sema(conn)
    t = conn.execute("SELECT id, durum FROM ticket WHERE id=?", (int(ticket_id),)).fetchone()
    satirlar = conn.execute("SELECT * FROM ticket_boss_aski WHERE ticket_id=? AND durum='askida' ORDER BY is_no",
                            (int(ticket_id),)).fetchall()
    if t is not None and t["durum"] in _COZEN:
        if _elle_askilari_ekle(conn, int(ticket_id)):        # otomatik askıdan önce elle askıya alınmış bağlı işler
            satirlar = conn.execute("SELECT * FROM ticket_boss_aski WHERE ticket_id=? AND durum='askida' ORDER BY "
                                    "is_no", (int(ticket_id),)).fetchall()
    if t is None or t["durum"] not in tk.KAPALI_DURUMLAR or not satirlar:
        return sonuc
    simdi = zaman.simdi()
    an = zaman.metin(simdi)
    cozuldu = t["durum"] in _COZEN
    ata_acik = acik_mi(conn, AYAR_YENIDEN_ATA)
    try:
        akis.ticket_degisti(conn, int(ticket_id), k)       # altyapı bekleyen iş önce bekliyor'a (+ Aranacak)
    except Exception:          # noqa: BLE001
        _log.exception("Ticket #%s çözümü: iş durumları", ticket_id)
    bas, bit = cozum_dilimi(conn, simdi)

    def isaretle(s, durum, **ek):
        alan = {"durum": durum, "cozum_zaman": an, **ek}
        conn.execute(f"UPDATE ticket_boss_aski SET {', '.join(f'{a}=?' for a in alan)} WHERE ticket_id=? AND is_no=?",
                     (*alan.values(), int(ticket_id), s["is_no"]))

    for s in satirlar:
        r = conn.execute("SELECT durum FROM is_emri WHERE is_no=?", (s["is_no"],)).fetchone()
        try:
            if r is None or r["durum"] in ("cozuldu", "kapandi") or not cozuldu or not ata_acik:
                with islem(conn):
                    isaretle(s, "birakildi")
                continue
            if not s["onceki_teknik_id"]:                # anlık görüntü yok: son bilinen ekip
                tid, ad = son_bilinen_ekip(conn, s["is_no"])
                if tid:
                    with islem(conn):
                        conn.execute("UPDATE ticket_boss_aski SET onceki_teknik_id=?, onceki_ekip=? WHERE ticket_id=? "
                                     "AND is_no=?", (tid, ad, int(ticket_id), s["is_no"]))
                    s = {**dict(s), "onceki_teknik_id": tid, "onceki_ekip": ad}
            if not s["onceki_teknik_id"]:
                with islem(conn):
                    isaretle(s, "ekipsiz")
                sonuc["ekipsiz"].append(s["task_no"])
                continue
            try:
                akis.ata(conn, s["is_no"], s["onceki_teknik_id"], k, randevu={"bas": bas, "bit": bit, "teyitli": False},
                         yine_de=True, kaynak="ticket",
                         notu=f"Ticket #{int(ticket_id)} çözüldü; önceki ekibe geri atandı")
            except V2Hata as e:
                with islem(conn):
                    isaretle(s, "atanamadi", hata=str(getattr(e, "mesaj", e))[:200])
                continue
            with islem(conn):
                isaretle(s, "atandi", atama_bas=bas)
            sonuc["atanan"].append(s["task_no"])
        except Exception:                       # noqa: BLE001
            _log.exception("Ticket #%s çözümü işe uygulanamadı (%s)", ticket_id, s["is_no"])
    return sonuc


def _elle_askilari_ekle(conn: sqlite3.Connection, ticket_id: int) -> int:
    """Ticket çözülürken: ticket'ın hedef işlerinden, ticket açıldıktan SONRA askıya alınmış (elle ya da BOSS'ta;
    otomatik askı satırı olmayan) ve hâlâ askıdaki işler de geri atamaya katılır (önceki ekip: son bilinen).
    Dönüş: eklenen satır sayısı."""
    from operasyon.v2 import zaman
    from operasyon.v2.islem import islem

    from . import ticket_boss_not as tbn
    t = conn.execute("SELECT olusturma FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if t is None:
        return 0
    n = 0
    for h in tbn.hedefler(conn, ticket_id):
        if conn.execute("SELECT 1 FROM ticket_boss_aski WHERE ticket_id=? AND is_no=?", (ticket_id, h["is_no"])).fetchone():
            continue
        r = conn.execute("SELECT is_no, durum, boss_ekip, atanan_id FROM is_emri WHERE is_no=?", (h["is_no"],)).fetchone()
        if r is None or r["durum"] != "askida":
            continue
        an = conn.execute("SELECT MAX(zaman) FROM is_emri_olay WHERE is_no=? AND yeni LIKE '%\"durum\": \"askida\"%'",
                          (h["is_no"],)).fetchone()[0]
        if not an or an < (t["olusturma"] or ""):
            continue
        tid, ekip = _onceki_ekip(conn, r)
        with islem(conn):
            conn.execute("INSERT INTO ticket_boss_aski (ticket_id, is_no, task_no, onceki_teknik_id, onceki_ekip, durum, "
                         "aski_zaman) VALUES (?,?,?,?,?,'askida',?)",
                         (ticket_id, h["is_no"], h["task_no"], tid, ekip, an or zaman.metin()))
        n += 1
    return n


def yenile(conn: sqlite3.Connection, zorla: bool = False) -> dict:
    """Her BOSS eşitlemesinin sonunda (en çok yarım saatte bir): açık ticket'ın askısı bitişe ``YENILE_SAAT`` kala
    yeniden yazılır; kapanmış ticket'ın askıdaki işleri çözülür. Hata fırlatmaz."""
    out = {"yenilenen": 0, "cozulen": 0}
    if not zorla and time.time() - _SON_YENILE[0] < YENILE_ARALIK_SN:
        return out
    _SON_YENILE[0] = time.time()
    try:
        from operasyon.v2 import zaman
        from operasyon.v2.islem import islem
        sema(conn)
        tk.sema(conn)
        simdi = zaman.simdi()
        sinir = zaman.metin(simdi + dt.timedelta(hours=YENILE_SAAT))
        satirlar = conn.execute(
            "SELECT a.*, t.durum AS t_durum, t.konu AS t_konu FROM ticket_boss_aski a JOIN ticket t ON t.id=a.ticket_id "
            "WHERE a.durum='askida'").fetchall()
        kapanan = sorted({s["ticket_id"] for s in satirlar if s["t_durum"] in tk.KAPALI_DURUMLAR})
        for tid in kapanan:
            out["cozulen"] += len(cozum(conn, tid, None)["atanan"])
        if not acik_mi(conn, AYAR_ASKI):
            return out
        for s in satirlar:
            if s["t_durum"] in tk.KAPALI_DURUMLAR or (s["bitis"] or "") > sinir:
                continue
            r = conn.execute("SELECT durum FROM is_emri WHERE is_no=?", (s["is_no"],)).fetchone()
            if r is None or r["durum"] in ("cozuldu", "kapandi"):
                with islem(conn):
                    conn.execute("UPDATE ticket_boss_aski SET durum='birakildi' WHERE ticket_id=? AND is_no=?",
                                 (s["ticket_id"], s["is_no"]))
                continue
            with islem(conn):
                kid, bitis = _askiya_al(conn, s["ticket_id"], {"is_no": s["is_no"], "task_no": s["task_no"]},
                                        s["metin"] or "", s["t_konu"], None, simdi)
                conn.execute("UPDATE ticket_boss_aski SET kayit_id=?, bitis=? WHERE ticket_id=? AND is_no=?",
                             (kid, bitis, s["ticket_id"], s["is_no"]))
            out["yenilenen"] += 1
    except Exception:                            # noqa: BLE001
        _log.exception("Ticket askılarını yenileme")
    return out


_BOSS_HALI = {"bekliyor": "gidiyor", "gonderiliyor": "gidiyor", "gonderildi": "tamam", "hata": "hata",
              "eksik": "hata", "zaman_asimi": "hata", "onizleme": "kapali", "yerine_yeni": "gidiyor"}


def durumlar(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Ticket çekmecesi: iş başına otomatik askı / geri atama hâli. {is_no, task_no, task_adi, durum, onceki_ekip,
    bitis, boss: gidiyor|tamam|hata|kapali|alt_neden_bekleniyor, hata?, atama_bas?}. Kişisel veri yok."""
    try:
        from operasyon.v2 import boss_yazma
        sema(conn)
        satirlar = conn.execute(
            "SELECT a.*, e.task_adi FROM ticket_boss_aski a LEFT JOIN is_emri e ON e.is_no=a.is_no WHERE a.ticket_id=? "
            "ORDER BY a.aski_zaman, a.is_no", (int(ticket_id),)).fetchall()
    except (ImportError, sqlite3.Error):
        return []
    gonderilir = boss_yazma.gonderilir(conn, "aski")
    out = []
    for s in satirlar:
        o = {"is_no": s["is_no"], "task_no": s["task_no"] or "", "task_adi": s["task_adi"] or "", "durum": s["durum"],
             "onceki_ekip": s["onceki_ekip"], "bitis": s["bitis"], "atama_bas": s["atama_bas"]}
        if s["hata"]:
            o["hata"] = s["hata"]
        if s["durum"] in ("askida", "ekipsiz") and not s["onceki_teknik_id"]:
            o["uyari"] = "Önceki ekip bilinmiyor — elle atayın"
        kayit = conn.execute("SELECT * FROM boss_yazma WHERE id=?", (s["kayit_id"],)).fetchone() \
            if s["kayit_id"] else None
        if kayit is not None:
            b = _BOSS_HALI.get(kayit["durum"], "hata")
            if kayit["durum"] == "bekliyor":
                _g, eksik = boss_yazma.govde_kur(conn, kayit)
                if "suspendSubReasonId" in eksik or "suspendReasonId" in eksik:
                    b = "alt_neden_bekleniyor"
                elif not gonderilir:
                    b = "kapali"
            elif kayit["durum"] == "hata":
                try:
                    sn = json.loads(kayit["sonuc"]) if kayit["sonuc"] else {}
                except ValueError:
                    sn = {}
                o["boss_hata"] = boss_yazma.hata_metni(conn, kayit, sn)
            o["boss"] = b
        out.append(o)
    return out
