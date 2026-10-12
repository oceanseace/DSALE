"""İş türüne göre ayırma ve kuralla dağıtım (ofis çalışanına).

BOSS Teknik Task Detay Raporu'nun BÜTÜN satırları (kurulumlar dahil; kurulum → "Yeni Müşteri") ``dagitim_is``
tablosunda tutulur. Arıza hattı (``is_emri``) bundan etkilenmez: burası yalnız "bu işin ofisteki sorumlusu kim"
sorusunu yanıtlar.

Kural = kaydedilmiş süzgeç (sütun koşulları, hepsi birden: VE) → ofis çalışanı. Kurallar sıralıdır; ilk eşleşen
kazanır. "Uygula" açık ve sorumlusuz işlere kuralları uygular; her rapor aktarımından sonra kendiliğinden uygulanır.
Eşleşmeyen iş "Dağıtılmamış" kalır. Karşılaştırma Türkçe harf duyarsızdır (``ie.sade``: "İSTANBUL" = "istanbul").

Göç: tablolar ilk kullanımda kurulur; kurmadan önce veritabanının güvenlik yedeği alınır (aktarım yedeğiyle aynı
yöntem: salt okunur kaynak + backup API + bütünlük denetimi).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3

import pandas as pd

from operasyon import is_emri as ie

from . import kisi, zaman
from .hatalar import AlanEksik, Gecersiz, IsYok
from .islem import islem

TUR_SUTUNU = "Müşteri Türü"
TUR_ADI = {"yeni": "Yeni Müşteri", "mevcut": "Mevcut Müşteri"}
NO_SUTUNU = "Task No"
KAPALI_DURUM = {"BITIRILDI", "KAPALI", "IPTAL", "KAPANDI", "TAMAMLANDI"}
OFIS_YETKINLIK = ("operasyon_planlama", "randevu_arama")
AZAMI_KURAL = 200
AZAMI_KOSUL = 30

SEMA: list[str] = [
    """CREATE TABLE IF NOT EXISTS dagitim_kural (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sira INTEGER NOT NULL,
    ad TEXT NOT NULL,
    kosullar TEXT NOT NULL,
    kisi_id INTEGER NOT NULL,
    aktif INTEGER NOT NULL DEFAULT 1,
    olusturan_id INTEGER,
    olusturma TEXT NOT NULL,
    guncelleme TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS dagitim_is (
    task_no TEXT PRIMARY KEY,
    tur TEXT NOT NULL CHECK (tur IN ('yeni','mevcut')),
    veri TEXT NOT NULL,
    acik INTEGER NOT NULL DEFAULT 1,
    sorumlu_id INTEGER,
    kural_id INTEGER,
    atama_kaynak TEXT CHECK (atama_kaynak IN ('kural','elle')),
    atama_zamani TEXT,
    atayan_id INTEGER,
    ilk_gorulme TEXT NOT NULL,
    son_gorulme TEXT NOT NULL,
    aktarim_id INTEGER)""",
    "CREATE INDEX IF NOT EXISTS ix_dagitim_is_acik ON dagitim_is(acik, sorumlu_id)",
]

_log = logging.getLogger("operasyon.dagitim")


# ----------------------------------------------------------------------------- göç
def hazirla(conn: sqlite3.Connection, yedek: bool = True) -> bool:
    """Tablolar yoksa: önce yedek, sonra tek işlemde kur (``ek_sema.yedekli_kur``). Kurduysa True."""
    from . import ek_sema
    return ek_sema.yedekli_kur(conn, "dagitim", SEMA, ("dagitim_kural", "dagitim_is"), yedek)


# ----------------------------------------------------------------------------- değer
def _deger(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        if pd.isna(v):
            return ""
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    if s.lower() in ("nan", "nat", "none"):
        return ""
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def tur_bul(task_adi: str, istisnalar=ie.VARSAYILAN_ISTISNALAR) -> str:
    return "yeni" if ie.cikarilacak_mi(task_adi or "", istisnalar) == "KURULUM" else "mevcut"


def _acik_mi(durum: str) -> bool:
    return ie.sade(durum) not in KAPALI_DURUM


# ----------------------------------------------------------------------------- kural eşleşmesi
def kosul_dogrula(kosullar) -> list[dict]:
    if not isinstance(kosullar, list) or not kosullar:
        raise AlanEksik("Kuralın en az bir koşulu olmalı (hangi işler?).")
    if len(kosullar) > AZAMI_KOSUL:
        raise Gecersiz("Bir kuralda en çok 30 koşul olabilir.", kod="alan_eksik")
    out = []
    for c in kosullar:
        if not isinstance(c, dict) or not str(c.get("sutun") or "").strip():
            raise AlanEksik("Her koşulun bir sütunu olmalı.")
        degerler = c.get("degerler")
        if degerler is not None:
            if not isinstance(degerler, list) or not all(isinstance(x, (str, int, float)) for x in degerler):
                raise AlanEksik("Koşul değerleri bir liste olmalı.")
            degerler = [str(x) for x in degerler]
        icerir = c.get("icerir")
        icerir = str(icerir).strip() if icerir is not None and str(icerir).strip() else None
        if not degerler and not icerir:
            raise AlanEksik(f"“{c['sutun']}” koşulunda değer seçin ya da aranacak metni yazın.")
        out.append({"sutun": str(c["sutun"]).strip(), "degerler": degerler or None, "icerir": icerir})
    return out


def _derle(kosullar: list[dict]) -> list[tuple[str, frozenset | None, str | None]]:
    return [(c["sutun"], frozenset(ie.sade(x) for x in c["degerler"]) if c.get("degerler") else None,
             ie.sade(c["icerir"]) if c.get("icerir") else None) for c in kosullar]


def _uyar(derli, veri: dict) -> bool:
    for sutun, degerler, icerir in derli:
        h = ie.sade(veri.get(sutun, ""))
        if degerler is not None and h not in degerler:
            return False
        if icerir is not None and icerir not in h:
            return False
    return True


def eslesir(kosullar: list[dict], veri: dict) -> bool:
    """Bütün koşullar (VE). Değer listesi: Excel süzgeci gibi tam eşitlik ('' = boş); içerir: alt metin."""
    return _uyar(_derle(kosullar), veri)


def ilk_eslesen(kurallar: list[dict], veri: dict) -> dict | None:
    for k in kurallar:
        if k["aktif"] and k["kisi_id"] and _uyar(k["_derli"], veri):
            return k
    return None


# ----------------------------------------------------------------------------- okuma
def ofis_kisileri(conn: sqlite3.Connection) -> list[dict]:
    """Kural hedefi olabilecekler: aktif, operasyon/yönetici görevi ya da operasyon/randevu yetkinliği olan."""
    yetkinli: set[int] = set()
    try:
        yetkinli |= {r[0] for r in conn.execute(
            f"SELECT kullanici_id FROM kullanici_yetkinlik WHERE yetkinlik IN ({','.join('?' * len(OFIS_YETKINLIK))})",
            OFIS_YETKINLIK)}
    except sqlite3.OperationalError:
        pass
    try:
        yetkinli |= {r[0] for r in conn.execute(
            "SELECT k.id FROM kullanici k JOIN unvan_yetkinlik u ON u.unvan_id = k.unvan_id "
            f"WHERE u.yetkinlik IN ({','.join('?' * len(OFIS_YETKINLIK))})", OFIS_YETKINLIK)}
    except sqlite3.OperationalError:
        pass
    out = []
    for kid, k in kisi.kisiler(conn).items():
        if not k["aktif"]:
            continue
        if kid in yetkinli or set(k["gorevler"]) & kisi.OFIS:
            out.append({**kisi.ozet(k)})
    return sorted(out, key=lambda x: ie.sade(x["ad"]))


def kurallar(conn: sqlite3.Connection) -> list[dict]:
    hazirla(conn)
    out = []
    for r in conn.execute("SELECT * FROM dagitim_kural ORDER BY sira, id"):
        ks = json.loads(r["kosullar"])
        out.append({"id": r["id"], "sira": r["sira"], "ad": r["ad"], "kosullar": ks, "kisi_id": r["kisi_id"],
                     "aktif": bool(r["aktif"]), "guncelleme": r["guncelleme"], "_derli": _derle(ks)})
    return out


def _disa(k: dict) -> dict:
    return {a: v for a, v in k.items() if not a.startswith("_")}


def sutunlar(conn: sqlite3.Connection) -> list[str]:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='dagitim_sutunlar'").fetchone()
    try:
        s = json.loads(r[0]) if r and r[0] else []
    except ValueError:
        s = []
    return [TUR_SUTUNU, *[x for x in s if x != TUR_SUTUNU]]


def liste(conn: sqlite3.Connection, hepsi: bool = False) -> dict:
    """GET /api/dagitim: tablo satırları (açık; ``hepsi`` → kapananlar da), kurallar, kişiler."""
    hazirla(conn)
    kisiler = {k["id"]: k for k in ofis_kisileri(conn)}
    tum = kisi.kisiler(conn)
    satirlar = []
    sql = "SELECT * FROM dagitim_is" + ("" if hepsi else " WHERE acik = 1") + " ORDER BY ilk_gorulme DESC, task_no"
    for r in conn.execute(sql):
        veri = json.loads(r["veri"])
        veri[TUR_SUTUNU] = TUR_ADI[r["tur"]]
        s = kisiler.get(r["sorumlu_id"]) or kisi.ozet(tum.get(r["sorumlu_id"]))
        satirlar.append({"task_no": r["task_no"], "tur": r["tur"], "acik": bool(r["acik"]), "sorumlu": s,
                         "kural_id": r["kural_id"], "atama_kaynak": r["atama_kaynak"], "atama_zamani": r["atama_zamani"],
                         "veri": veri})
    return {"sutunlar": sutunlar(conn), "satirlar": satirlar, "kurallar": [_disa(k) for k in kurallar(conn)],
            "kisiler": list(kisiler.values()),
            "dagitilmamis": sum(1 for s in satirlar if s["acik"] and not s["sorumlu"])}


# ----------------------------------------------------------------------------- yazma
def kurallari_yaz(conn: sqlite3.Connection, girdi: list, k: dict | None) -> list[dict]:
    """Kural listesinin TAMAMI, sırasıyla (ilk eşleşen kazanır). ``id`` verilen kural güncellenir, verilmeyen
    eklenir, listede olmayan silinir."""
    hazirla(conn)
    if not isinstance(girdi, list):
        raise AlanEksik("Kurallar bir liste olmalı.")
    if len(girdi) > AZAMI_KURAL:
        raise Gecersiz("En çok 200 kural olabilir.", kod="alan_eksik")
    gecerli = {x["id"] for x in ofis_kisileri(conn)}
    temiz = []
    for i, g in enumerate(girdi):
        if not isinstance(g, dict):
            raise AlanEksik("Kural biçimi tanınmadı.")
        ad = str(g.get("ad") or "").strip()[:80]
        if not ad:
            raise AlanEksik(f"{i + 1}. kuralın adı boş.")
        try:
            kid = int(g.get("kisi_id"))
        except (TypeError, ValueError):
            raise AlanEksik(f"“{ad}” kuralına bir ofis çalışanı seçin.")
        if kid not in gecerli:
            raise Gecersiz(f"“{ad}” kuralındaki kişi ofis çalışanı değil ya da etkin değil.", kod="kisi_gecersiz")
        temiz.append({"id": g.get("id"), "ad": ad, "kosullar": kosul_dogrula(g.get("kosullar")), "kisi_id": kid,
                      "aktif": bool(g.get("aktif", True))})
    simdi = zaman.metin()
    with islem(conn):
        eski = {r[0] for r in conn.execute("SELECT id FROM dagitim_kural")}
        kalan = set()
        for sira, t in enumerate(temiz, 1):
            ks = json.dumps(t["kosullar"], ensure_ascii=False)
            if t["id"] in eski and t["id"] not in kalan:
                conn.execute("UPDATE dagitim_kural SET sira=?, ad=?, kosullar=?, kisi_id=?, aktif=?, guncelleme=? "
                             "WHERE id=?", (sira, t["ad"], ks, t["kisi_id"], int(t["aktif"]), simdi, t["id"]))
                kalan.add(t["id"])
            else:
                yeni = conn.execute("INSERT INTO dagitim_kural (sira, ad, kosullar, kisi_id, aktif, olusturan_id, "
                                    "olusturma, guncelleme) VALUES (?,?,?,?,?,?,?,?)",
                                    (sira, t["ad"], ks, t["kisi_id"], int(t["aktif"]), (k or {}).get("id"), simdi,
                                     simdi)).lastrowid
                kalan.add(yeni)
        for i in eski - kalan:
            conn.execute("DELETE FROM dagitim_kural WHERE id=?", (i,))
    return [_disa(x) for x in kurallar(conn)]


def uygula(conn: sqlite3.Connection, k: dict | None = None, task_nolar=None) -> dict:
    """Açık ve sorumlusuz işlere kuralları uygular (ilk eşleşen). Dönüş: {atanan, dagitilmamis, kurallar: {id: n}}."""
    hazirla(conn)
    ks = kurallar(conn)
    simdi = zaman.metin()
    sayi: dict[int, int] = {}
    atanan = kalan = 0
    with islem(conn):
        sql = "SELECT task_no, veri, tur FROM dagitim_is WHERE acik = 1 AND sorumlu_id IS NULL"
        param: list = []
        if task_nolar is not None:
            nolar = [str(x) for x in task_nolar]
            if not nolar:
                return {"atanan": 0, "dagitilmamis": 0, "kurallar": {}}
            sql += f" AND task_no IN ({','.join('?' * len(nolar))})"
            param = nolar
        for r in conn.execute(sql, param).fetchall():
            veri = json.loads(r["veri"])
            veri[TUR_SUTUNU] = TUR_ADI[r["tur"]]
            kural = ilk_eslesen(ks, veri)
            if kural is None:
                kalan += 1
                continue
            conn.execute("UPDATE dagitim_is SET sorumlu_id=?, kural_id=?, atama_kaynak='kural', atama_zamani=?, "
                         "atayan_id=? WHERE task_no=?", (kural["kisi_id"], kural["id"], simdi, (k or {}).get("id"),
                                                         r["task_no"]))
            sayi[kural["id"]] = sayi.get(kural["id"], 0) + 1
            atanan += 1
    return {"atanan": atanan, "dagitilmamis": kalan, "kurallar": {str(a): n for a, n in sayi.items()}}


def elle_ata(conn: sqlite3.Connection, task_nolar, kisi_id: int | None, k: dict | None) -> dict:
    """Seçili işlerin sorumlusunu elle verir (``kisi_id`` None → sorumluyu kaldır, iş yeniden Dağıtılmamış)."""
    hazirla(conn)
    nolar = [str(x) for x in (task_nolar or [])]
    if not nolar:
        raise AlanEksik("İş seçilmedi.")
    if kisi_id is not None and kisi_id not in {x["id"] for x in ofis_kisileri(conn)}:
        raise Gecersiz("Seçilen kişi ofis çalışanı değil ya da etkin değil.", kod="kisi_gecersiz")
    simdi = zaman.metin()
    with islem(conn):
        n = 0
        for no in nolar:
            if kisi_id is None:
                n += conn.execute("UPDATE dagitim_is SET sorumlu_id=NULL, kural_id=NULL, atama_kaynak=NULL, "
                                  "atama_zamani=NULL, atayan_id=NULL WHERE task_no=?", (no,)).rowcount
            else:
                n += conn.execute("UPDATE dagitim_is SET sorumlu_id=?, kural_id=NULL, atama_kaynak='elle', "
                                  "atama_zamani=?, atayan_id=? WHERE task_no=?",
                                  (kisi_id, simdi, (k or {}).get("id"), no)).rowcount
    if not n:
        raise IsYok()
    return {"degisen": n}


def rapordan(conn: sqlite3.Connection, df: pd.DataFrame, aktarim_id: int | None, tam_kapsam: bool = True) -> dict:
    """Aktarım sonrası: raporun bütün satırları ``dagitim_is``'e; raporda olmayan açıklar (tam kapsamda) kapanır;
    sonra kurallar yeni ve sorumlusuz açık işlere uygulanır."""
    hazirla(conn)
    if NO_SUTUNU not in df.columns:
        return {"satir": 0}
    istisnalar = list(ie.VARSAYILAN_ISTISNALAR)
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='filtre_istisnalari'").fetchone()
    try:
        istisnalar = json.loads(r[0]) if r and r[0] else istisnalar
    except ValueError:
        pass
    kolonlar = [str(c) for c in df.columns if not str(c).startswith("Unnamed")]
    simdi = zaman.metin()
    gorulen: set[str] = set()
    yeni = 0
    with islem(conn):
        mevcut = {x[0]: x[1] for x in conn.execute("SELECT task_no, acik FROM dagitim_is")}
        for kayit in df[kolonlar].to_dict("records"):
            veri = {kol: _deger(kayit.get(kol)) for kol in kolonlar}
            no = veri.get(NO_SUTUNU)
            if not no or no in gorulen:
                continue
            gorulen.add(no)
            tur = tur_bul(veri.get("Task Adı", ""), istisnalar)
            acik = 1 if _acik_mi(veri.get("Task Durumu", "")) else 0
            js = json.dumps(veri, ensure_ascii=False)
            if no in mevcut:
                conn.execute("UPDATE dagitim_is SET veri=?, tur=?, acik=?, son_gorulme=?, aktarim_id=? WHERE task_no=?",
                             (js, tur, acik, simdi, aktarim_id, no))
            else:
                yeni += 1
                conn.execute("INSERT INTO dagitim_is (task_no, tur, veri, acik, ilk_gorulme, son_gorulme, aktarim_id) "
                             "VALUES (?,?,?,?,?,?,?)", (no, tur, js, acik, simdi, simdi, aktarim_id))
        kapanan = 0
        if tam_kapsam:
            for no, acik in mevcut.items():
                if acik and no not in gorulen:
                    kapanan += conn.execute("UPDATE dagitim_is SET acik=0 WHERE task_no=?", (no,)).rowcount
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('dagitim_sutunlar', ?) "
                     "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger",
                     (json.dumps(kolonlar, ensure_ascii=False),))
        # kişisel veri saklama: kapanmış ve uzun süredir görülmeyen satırlar silinir
        r = conn.execute("SELECT deger FROM ayar WHERE anahtar='pii_saklama_gun'").fetchone()
        try:
            gun = int(r[0]) if r and r[0] else 30
        except ValueError:
            gun = 30
        sinir = zaman.metin(zaman.oku(simdi) - dt.timedelta(days=gun))
        conn.execute("DELETE FROM dagitim_is WHERE acik = 0 AND son_gorulme < ?", (sinir,))
    sonuc = uygula(conn)
    return {"satir": len(gorulen), "yeni": yeni, "kapanan": kapanan, **sonuc}


def aktarim_sonrasi(conn: sqlite3.Connection, df: pd.DataFrame, aktarim_id: int | None, tam_kapsam: bool) -> dict | None:
    """Aktarım hattının çağırdığı güvenli sarmal: dağıtım düşerse aktarım yine uygulanmış sayılır."""
    try:
        return rapordan(conn, df, aktarim_id, tam_kapsam)
    except Exception:          # noqa: BLE001
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        _log.exception("Dağıtım tablosu güncellenemedi")
        return None


# ----------------------------------------------------------------------------- görünümler (task başlığına göre)
# Görünüm = adlandırılmış süzgeç: seçili task başlıkları (+ isteğe bağlı sorumlu kişi/ekip). ``dagitim_kural``
# tablosunda tek koşullu kural olarak saklanır (sütun "Task Adı"); sorumlu yoksa kisi_id = 0. İşler listesi ve
# İş haritası bunu bir seçici olarak kullanır; işlerin hepsi her zaman çekilir.
GORUNUM_SUTUNU = "Task Adı"


def gorunum_kisileri(conn: sqlite3.Connection) -> list[dict]:
    out = [{"id": x["id"], "ad": x["ad"], "tur": "ofis"} for x in ofis_kisileri(conn)]
    for kid, t in sorted(kisi.teknikler(conn).items(), key=lambda x: ie.sade(x[1]["ad"])):
        out.append({"id": kid, "ad": t["ad"], "tur": "ekip"})
    return out


def gorunumler(conn: sqlite3.Connection) -> dict:
    hazirla(conn)
    kisiler = {x["id"]: x for x in gorunum_kisileri(conn)}
    tum = kisi.kisiler(conn)
    out = []
    for k in kurallar(conn):
        adlar: list[str] = []
        for c in k["kosullar"]:
            if c.get("sutun") == GORUNUM_SUTUNU and c.get("degerler"):
                adlar.extend(c["degerler"])
        kid = k["kisi_id"] or None
        ks = kisiler.get(kid) or (tum.get(kid) and {"id": kid, "ad": tum[kid]["ad"]})
        out.append({"id": k["id"], "ad": k["ad"], "task_adlari": adlar, "kisi_id": kid if ks else None,
                    "kisi": {"id": ks["id"], "ad": ks["ad"]} if ks else None})
    basliklar = [{"ad": r[0], "adet": r[1]} for r in conn.execute(
        "SELECT task_adi, COUNT(*) FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi') AND task_adi IS NOT NULL "
        "AND task_adi <> '' GROUP BY task_adi ORDER BY COUNT(*) DESC, task_adi")]
    bilinen = {ie.sade(b["ad"]) for b in basliklar}
    for g in out:                                   # kayıtlı ama şu an açık işi olmayan başlıklar da listede kalsın
        for a in g["task_adlari"]:
            if ie.sade(a) not in bilinen:
                bilinen.add(ie.sade(a))
                basliklar.append({"ad": a, "adet": 0})
    return {"gorunumler": out, "basliklar": basliklar, "kisiler": list(kisiler.values())}


def gorunumleri_yaz(conn: sqlite3.Connection, girdi: list, k: dict | None) -> dict:
    """Görünüm listesinin TAMAMI (sırasıyla). ``id`` verilen güncellenir, olmayan eklenir, listede olmayan silinir."""
    hazirla(conn)
    if not isinstance(girdi, list):
        raise AlanEksik("Görünümler bir liste olmalı.")
    if len(girdi) > AZAMI_KURAL:
        raise Gecersiz("En çok 200 görünüm olabilir.", kod="alan_eksik")
    gecerli = {x["id"] for x in gorunum_kisileri(conn)}
    temiz, adlar = [], set()
    for i, g in enumerate(girdi):
        if not isinstance(g, dict):
            raise AlanEksik("Görünüm biçimi tanınmadı.")
        ad = str(g.get("ad") or "").strip()[:80]
        if not ad:
            raise AlanEksik(f"{i + 1}. görünümün adı boş.")
        if ie.sade(ad) in adlar:
            raise Gecersiz(f"“{ad}” adı iki kez kullanılmış.", kod="alan_eksik")
        adlar.add(ie.sade(ad))
        basliklar = g.get("task_adlari")
        if not isinstance(basliklar, list) or not all(isinstance(x, str) for x in basliklar):
            raise AlanEksik(f"“{ad}” görünümünün task başlıkları bir liste olmalı.")
        basliklar = list(dict.fromkeys(x.strip() for x in basliklar if x.strip()))[:500]
        if not basliklar:
            raise AlanEksik(f"“{ad}” görünümünde en az bir task başlığı seçin.")
        kid = g.get("kisi_id")
        if kid in (None, "", 0):
            kid = 0
        else:
            try:
                kid = int(kid)
            except (TypeError, ValueError):
                raise AlanEksik(f"“{ad}” görünümündeki kişi tanınmadı.")
            if kid not in gecerli:
                raise Gecersiz(f"“{ad}” görünümündeki kişi etkin değil.", kod="kisi_gecersiz")
        temiz.append({"id": g.get("id"), "ad": ad, "kisi_id": kid,
                      "kosullar": [{"sutun": GORUNUM_SUTUNU, "degerler": basliklar, "icerir": None}]})
    simdi = zaman.metin()
    with islem(conn):
        eski = {r[0] for r in conn.execute("SELECT id FROM dagitim_kural")}
        kalan = set()
        for sira, t in enumerate(temiz, 1):
            ks = json.dumps(t["kosullar"], ensure_ascii=False)
            if t["id"] in eski and t["id"] not in kalan:
                conn.execute("UPDATE dagitim_kural SET sira=?, ad=?, kosullar=?, kisi_id=?, aktif=1, guncelleme=? "
                             "WHERE id=?", (sira, t["ad"], ks, t["kisi_id"], simdi, t["id"]))
                kalan.add(t["id"])
            else:
                kalan.add(conn.execute(
                    "INSERT INTO dagitim_kural (sira, ad, kosullar, kisi_id, aktif, olusturan_id, olusturma, guncelleme) "
                    "VALUES (?,?,?,?,1,?,?,?)", (sira, t["ad"], ks, t["kisi_id"], (k or {}).get("id"), simdi,
                                                 simdi)).lastrowid)
        for i in eski - kalan:
            conn.execute("DELETE FROM dagitim_kural WHERE id=?", (i,))
    return gorunumler(conn)
