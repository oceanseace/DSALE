"""Kesintiye duyarlı sevk (EK-12.6; belgeler/TURKCELL_SUREC_BILGISI.md §4.5, §E).

- Operatör extrajet "Santral Arıza" bültenini (Bursa/Yalova, Devam ediyor/Planlandı) yapıştırır; il-ilçe + GPON/FTTX
  ayrıştırılır. O ilçedeki açık bağlantı/TV işleri (``ayar.kesinti_etkilenen``) "Genel arıza — sevk etme" olur:
  genel arıza askısı (BTK saatini durdurur), uyanma bülten bitince (ya da en geç ``UYANMA_SAAT`` sonra, yeniden bakılsın).
  Bülten sürerken aynı ilçeden gelen yeni işler de aktarımda doğrudan bu askıya düşer.
- Bülten yokken aynı ilçede kısa sürede çok bağlantı işi geliyorsa (``kesinti_ornek_esigi``, varsayılan 5) "verimlilik
  ekibine gönder" paketi hazırlanır (kopyalanır; Task No + müşteri no + iş tipi). Sistem Turkcell'e yazmaz.

Bültenler ``ayar.kesintiler`` (JSON liste) içinde tutulur: az sayıda, kişisel veri içermez; göç gerektirmez.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from . import kurallar, zaman
from .hatalar import Catisma, Gecersiz, IsYok
from .islem import islem

ANAHTAR = "kesintiler"
UYANMA_SAAT = 24
NEDEN_ON = "Genel arıza (SOL kaynaklı)"
_ETIKET = {"devam": "Devam ediyor", "planli": "Planlandı", "bitti": "Bitti"}


def _oku(conn) -> list[dict]:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (ANAHTAR,)).fetchone()
    try:
        v = json.loads(r[0]) if r and r[0] else []
    except ValueError:
        v = []
    return v if isinstance(v, list) else []


def _yaz(conn, liste: list[dict]) -> None:
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?, ?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                 (ANAHTAR, json.dumps(liste[-200:], ensure_ascii=False)))


def neden_metni(kesinti: dict) -> str:
    etiket = f"bülten {kesinti['no']}" if kesinti.get("no") else f"kesinti #{kesinti['id']}"
    return f"{NEDEN_ON} · {etiket}"


def aktifler(conn: sqlite3.Connection) -> list[dict]:
    return [k for k in _oku(conn) if not k.get("bitis")]


def ilce_haritasi(conn: sqlite3.Connection) -> dict[tuple[str, str], dict]:
    """(il_k, ilce_k) → etkin bülten (aktarım yeni işleri buna göre askıya alır)."""
    h: dict[tuple[str, str], dict] = {}
    for k in aktifler(conn):
        for i in k.get("ilceler", []):
            h.setdefault((i["il_k"], i["ilce_k"]), k)
    return h


def etkilenir_mi(conn_ya_da_kural, task_adi: str) -> bool:
    kural = conn_ya_da_kural if isinstance(conn_ya_da_kural, list) else kurallar.oku(conn_ya_da_kural,
                                                                                         "kesinti_etkilenen")
    return any(kurallar.eslesir(d, task_adi) for d in kural)


def _gorunum(k: dict, conn=None) -> dict:
    d = {**k, "durum_metni": _ETIKET.get(k.get("durum"), k.get("durum")),
         "ilce_metni": ", ".join(f"{i['il']}/{i['ilce']}" for i in k.get("ilceler", []))}
    if conn is not None:
        d["askida_is"] = conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum='askida' AND askida_neden=?",
                                      (neden_metni(k),)).fetchone()[0]
    return d


def liste(conn: sqlite3.Connection) -> dict:
    return {"kesintiler": [_gorunum(k, conn) for k in reversed(_oku(conn))][:50]}


def ekle(conn: sqlite3.Connection, metin: str, k: dict | None) -> dict:
    """Bülteni kaydeder ve etkilenen açık işleri genel arıza askısına alır (her iş kendi olayıyla)."""
    from . import akis
    metin = str(metin or "").strip()
    if len(metin) < 10:
        raise Gecersiz("Bülten metnini yapıştırın.", kod="alan_eksik")
    ilceler = [tuple(r) for r in conn.execute("SELECT il_k, ilce_k, il, ad FROM ilce ORDER BY il, ad")]
    a = kurallar.kesinti_ayristir(metin, ilceler)
    if not a["ilceler"]:
        raise Gecersiz("Bültende Bursa ya da Yalova ilçesi bulunamadı.", kod="ilce_yok")
    if a["durum"] == "bitti":
        raise Gecersiz("Bu bülten 'Bitti' görünüyor; sevki etkilemez.", kod="bulten_bitti")
    simdi = zaman.metin()
    with islem(conn):
        liste_ = _oku(conn)
        if a["no"] and any(x.get("no") == a["no"] and not x.get("bitis") for x in liste_):
            raise Catisma(f"Bülten {a['no']} zaten kayıtlı.", kod="var")
        yeni = {"id": max((x["id"] for x in liste_), default=0) + 1, "no": a["no"], "tur": a["tur"],
                "durum": a["durum"], "baslama": simdi, "baslama_saat": a["baslama_saat"],
                "etki_musteri": a["etki_musteri"], "bitis": None, "ekleyen": (k or {}).get("ad"),
                "ilceler": [{"il_k": i[0], "ilce_k": i[1], "il": i[2], "ilce": i[3]} for i in a["ilceler"]],
                "ozet": metin[:300]}
        liste_.append(yeni)
        _yaz(conn, liste_)
        conn.execute("INSERT INTO yonetim_kaydi (zaman, kullanici_id, kullanici_ad, eylem, hedef, ozet) VALUES "
                     "(?,?,?,?,?,?)", (simdi, (k or {}).get("id"), (k or {}).get("ad"), "kesinti",
                                       f"kesinti:{yeni['id']}", json.dumps({"ilce": len(yeni["ilceler"])})))
    kural = kurallar.oku(conn, "kesinti_etkilenen")
    alinan, atlanan = [], []
    for r in _etkilenen_isler(conn, yeni["ilceler"], kural):
        try:
            akis.gecis(conn, r["is_no"], "askida", k, neden=neden_metni(yeni),
                       uyanma=zaman.metin(zaman.simdi() + dt.timedelta(hours=UYANMA_SAAT)),
                       notu=f"Genel arıza — sevk etme ({_gorunum(yeni)['ilce_metni']})")
            alinan.append(r["is_no"])
        except Exception as e:         # noqa: BLE001 — bir iş diğerlerini bekletmez; neden listelenir
            atlanan.append({"is_no": r["is_no"], "kod": getattr(e, "kod", type(e).__name__)})
    return {"kesinti": _gorunum(yeni, conn), "askiya_alinan": alinan, "atlanan": atlanan}


def _etkilenen_isler(conn, ilceler: list[dict], kural: list[str]) -> list[sqlite3.Row]:
    out = []
    for i in ilceler:
        for r in conn.execute("SELECT is_no, task_adi FROM is_emri WHERE il_k=? AND ilce_k=? AND durum IN "
                              "('triyaj','bekliyor','randevulu','atandi') ORDER BY is_no", (i["il_k"], i["ilce_k"])):
            if etkilenir_mi(kural, r["task_adi"]):
                out.append(r)
    return out


def bitir(conn: sqlite3.Connection, kesinti_id: int, k: dict | None) -> dict:
    """Bülten bitti: kaydı kapatır, o bülten yüzünden askıdaki işleri uyandırır (Aranacaklar'da "uyanan")."""
    from . import akis
    simdi = zaman.metin()
    with islem(conn):
        liste_ = _oku(conn)
        hedef = next((x for x in liste_ if x["id"] == int(kesinti_id)), None)
        if hedef is None:
            raise IsYok("Bu kesinti bulunamadı.")
        if hedef.get("bitis"):
            raise Catisma("Bu kesinti zaten bitmiş.", kod="durum_gecersiz")
        hedef.update(bitis=simdi, durum="bitti")
        _yaz(conn, liste_)
    uyanan = []
    for (is_no,) in conn.execute("SELECT is_no FROM is_emri WHERE durum='askida' AND askida_neden=?",
                                 (neden_metni(hedef),)).fetchall():
        try:
            akis.gecis(conn, is_no, "bekliyor", k, notu="Genel arıza bitti; sevke hazır")
            uyanan.append(is_no)
        except Exception:              # noqa: BLE001
            continue
    return {"kesinti": _gorunum(hedef, conn), "uyanan": uyanan}


def adaylar(conn: sqlite3.Connection, simdi: dt.datetime | None = None, *, musteri: bool = True) -> dict:
    """Bülten yokken toplu arıza şüphesi: son ``kesinti_ornek_saat`` içinde aynı ilçede ≥ eşik bağlantı/TV işi.

    Her grup için "verimlilik ekibine gönder" paketi (sekme ayrımlı metin; müşteri no yalnız ``musteri=True``).
    """
    simdi = simdi or zaman.simdi()
    esik = int(kurallar.oku(conn, "kesinti_ornek_esigi") or 5)
    saat = int(kurallar.oku(conn, "kesinti_ornek_saat") or 12)
    kural = kurallar.oku(conn, "kesinti_etkilenen")
    aktif = ilce_haritasi(conn)
    sinir = zaman.metin(simdi - dt.timedelta(hours=saat))
    gruplar: dict[tuple, list] = {}
    for r in conn.execute("SELECT is_no, boss_task_no, task_adi, il, ilce, il_k, ilce_k, mahalle, acilis, musteri_no "
                          "FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi','askida') AND acilis >= ? "
                          "ORDER BY acilis", (sinir,)):
        if not r["ilce_k"] or (r["il_k"], r["ilce_k"]) in aktif or not etkilenir_mi(kural, r["task_adi"]):
            continue
        gruplar.setdefault((r["il_k"], r["ilce_k"], r["il"], r["ilce"]), []).append(r)
    out = []
    for (_ik, _ck, il, ilce), isler in sorted(gruplar.items(), key=lambda x: -len(x[1])):
        if len(isler) < esik:
            continue
        basliklar = ["Task No", "Task Adı", "Mahalle", "Açılış"] + (["Müşteri No"] if musteri else [])
        satirlar = ["\t".join(basliklar)]
        for r in isler:
            p = [r["boss_task_no"] or r["is_no"], r["task_adi"], r["mahalle"] or "", r["acilis"][:16]]
            satirlar.append("\t".join(p + ([r["musteri_no"] or ""] if musteri else [])))
        out.append({"il": il, "ilce": ilce, "adet": len(isler), "is_nolar": [r["is_no"] for r in isler],
                    "paket": f"Toplu arıza şüphesi · {il}/{ilce} · son {saat} saatte {len(isler)} iş\n"
                             + "\n".join(satirlar) + "\nHizmet ID ve seri no BOSS'tan eklenmeli."})
    return {"esik": esik, "saat": saat, "gruplar": out}
