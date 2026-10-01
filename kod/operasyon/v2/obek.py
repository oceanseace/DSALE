"""Öbekler: kullanıcının mahalle grupları (F1, F2, F5; spec §1.6, §5.3.5, §6.4).

Kaynak veritabanıdır. ``operasyon/obekler.json`` yalnız bir kez (göçte) OKUNUR, bir daha hiç yazılmaz; her
değişiklikten sonra okunabilir ayna ``operasyon/veri/obek_yedek/obekler-<zaman>.json`` yazılır (son 50).
Bütün düzen tek sürüm sayacıyla korunur (``ayar.obek_surumu``): iki kişi aynı anda düzenlerse ikincisi 409 alır.
Her değişiklik ``obek_olay``'a yazılır; son değişiklik 10 dakika içinde aynı kişi tarafından geri alınabilir.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from operasyon import is_emri as ie

from . import akis, kisi, sozluk, zaman
from .hatalar import Catisma, Gecersiz, GuncelDegil, IsYok
from .islem import islem

GERI_AL_DK = 10
AYNA_SAKLA = 50


# ----------------------------------------------------------------------------- sürüm
def surum(conn: sqlite3.Connection) -> int:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='obek_surumu'").fetchone()
    try:
        return int(r[0]) if r and r[0] is not None else 1
    except ValueError:
        return 1


def _surum_denetle(conn, beklenen) -> int:
    simdiki = surum(conn)
    if beklenen is not None and int(beklenen) != simdiki:
        raise GuncelDegil("Öbekler siz bakarken değişti. Güncel hâli yüklendi; yeniden deneyin.",
                          obekler=liste(conn)["obekler"], surum=simdiki)
    return simdiki


def _surum_arttir(conn) -> int:
    yeni = surum(conn) + 1
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('obek_surumu', ?) "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger", (str(yeni),))
    return yeni


# ----------------------------------------------------------------------------- bulma
def harita(conn: sqlite3.Connection) -> dict[tuple[str, str, str], int]:
    """(il_k, ilce_k, mahalle_k | '*') → öbek id (yalnız aktif öbekler)."""
    return {(r[0], r[1], r[2]): r[3] for r in conn.execute(
        "SELECT om.il_k, om.ilce_k, om.mahalle_k, om.obek_id FROM obek_mahalle om "
        "JOIN obek o ON o.id = om.obek_id WHERE o.aktif = 1")}


def haritadan(h: dict, il_k, ilce_k, mahalle_k) -> int | None:
    """Birebir mahalle önce, sonra ilçenin tamamı (spec §6.4: tek tek eklenen mahalle önceliklidir)."""
    if not ilce_k:
        return None
    if mahalle_k and (il_k, ilce_k, mahalle_k) in h:
        return h[(il_k, ilce_k, mahalle_k)]
    return h.get((il_k, ilce_k, "*"))


def bul(conn: sqlite3.Connection, il_k, ilce_k, mahalle_k) -> int | None:
    return haritadan(harita(conn), il_k, ilce_k, mahalle_k)


def _ref_tamamla(ilce_h: dict, ref: str) -> tuple[str, str, str, str] | None:
    """'Nilüfer/Görükle' | 'Bursa/Nilüfer/Görükle' | 'Bursa/Gürsu/*' → (il_k, ilce_k, mahalle_k, görünen 3 parça)."""
    p = [x.strip() for x in str(ref).split("/")]
    if len(p) == 2:
        p = ["", *p]
    if len(p) != 3 or not p[1] or not p[2]:
        return None
    c = sozluk.ilce_coz(ilce_h, p[0], p[1])
    if c is None:
        return None
    il_k, ilce_k, il_ad, ilce_ad = c
    mk = "*" if p[2] == "*" else ie.anahtar(p[2])
    if not mk:
        return None
    return il_k, ilce_k, mk, f"{il_ad}/{ilce_ad}/{p[2]}"


# ----------------------------------------------------------------------------- obekler.json aktarımı (göç v3)
def json_aktar(conn: sqlite3.Connection, yol: Path | None, zaman_metni: str) -> dict:
    """``obek`` tablosu boşsa ve dosya varsa öbekleri BİREBİR aktarır (dosya yalnız okunur).

    Çağıranın işlemi içinde koşar; doğrulama tutmazsa ``Gecersiz`` atar → çağıran ROLLBACK eder.
    Aynı mahalle iki öbekteyse dosyadaki İLK öbek kazanır; çakışma ``obek_olay`` + dönüşe yazılır.
    """
    yol = Path(yol) if yol else sozluk.obek_dosyasi()
    if conn.execute("SELECT COUNT(*) FROM obek").fetchone()[0]:
        return {"bos": False, "obek": 0, "ref": 0, "catisma": []}
    if not yol.exists():
        return {"bos": True, "obek": 0, "ref": 0, "catisma": [], "dosya": None}
    ham = yol.read_bytes()
    veri = json.loads(ham.decode("utf-8"))
    tanimlar = veri.get("obekler", [])
    # Önce yedek (klasör git dışı): kaynak dosyaya dokunulmaz.
    yedek_dizini = sozluk.veri_dizini() / "obek_yedek"
    yedek_dizini.mkdir(parents=True, exist_ok=True)
    (yedek_dizini / f"obekler-oncesi-{_dosya_zamani(zaman_metni)}.json").write_bytes(ham)

    ilce_h = sozluk.ilce_haritasi(conn)
    catisma: list[dict] = []
    tanimsiz: list[str] = []
    ref_sayisi = 0
    for sira, t in enumerate(tanimlar):
        ad = str(t.get("ad", "")).strip()
        ad_k = ie.anahtar(ad)
        cur = conn.execute("INSERT INTO obek (ad, ad_k, renk, aktif, olusturma, guncelleme) VALUES (?,?,?,1,?,?)",
                           (ad, ad_k, sira % 8, zaman_metni, zaman_metni))
        oid = cur.lastrowid
        for ref in t.get("mahalleler", []):
            ref_sayisi += 1
            c = _ref_tamamla(ilce_h, ref)
            if c is None:
                tanimsiz.append(ref)
                continue
            il_k, ilce_k, mk, gorunen = c
            onceki = conn.execute("SELECT o.ad FROM obek_mahalle om JOIN obek o ON o.id = om.obek_id "
                                  "WHERE om.il_k=? AND om.ilce_k=? AND om.mahalle_k=?", (il_k, ilce_k, mk)).fetchone()
            if onceki:
                catisma.append({"ref": gorunen, "kalan": onceki[0], "atlanan": ad})
                continue
            conn.execute("INSERT INTO obek_mahalle (il_k, ilce_k, mahalle_k, obek_id, ref, eklenme) VALUES (?,?,?,?,?,?)",
                         (il_k, ilce_k, mk, oid, gorunen, zaman_metni))
    if tanimsiz:
        raise Gecersiz(f"obekler.json içinde tanınmayan {len(tanimsiz)} mahalle yazımı var; aktarım yapılmadı.",
                       kod="obek_json_tanimsiz", refler=tanimsiz)
    # Doğrulama: sayılar ve her ref için DB'nin çözdüğü öbek = bugünkü JSON motorunun çözdüğü öbek
    n_obek = conn.execute("SELECT COUNT(*) FROM obek").fetchone()[0]
    n_ref = conn.execute("SELECT COUNT(*) FROM obek_mahalle").fetchone()[0]
    if n_obek != len(tanimlar) or n_ref + len(catisma) != ref_sayisi:
        raise Gecersiz("Öbek aktarımı doğrulanamadı (sayılar tutmuyor); veritabanı değişmedi.", kod="obek_json_sayi")
    motor = ie.Obekler(tanimlar=tanimlar)
    motor._derle()
    h = harita(conn)
    adlar = {r[0]: r[1] for r in conn.execute("SELECT id, ad FROM obek")}
    fark = 0
    for t in tanimlar:
        for ref in t.get("mahalleler", []):
            c = _ref_tamamla(ilce_h, ref)
            p = [x.strip() for x in str(ref).split("/")]
            p = ["", *p] if len(p) == 2 else p
            il = p[0] or c[3].split("/")[0]
            json_ad = motor.bul(il, p[1], None if p[2] == "*" else p[2])
            db_ad = adlar.get(haritadan(h, c[0], c[1], None if c[2] == "*" else c[2]))
            if json_ad != db_ad:
                fark += 1
    if fark:
        raise Gecersiz(f"Öbek aktarımı doğrulanamadı ({fark} mahallede farklı öbek); veritabanı değişmedi.",
                       kod="obek_json_fark")
    s = 1
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('obek_surumu','1') "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger='1'")
    conn.execute("INSERT INTO obek_olay (zaman, kullanici_id, kullanici_ad, tur, obek_id, veri, surum) "
                 "VALUES (?, NULL, NULL, 'json_aktarim', NULL, ?, ?)",
                 (zaman_metni, json.dumps({"once": None, "sonra": {"obek": n_obek, "ref": n_ref, "catisma": catisma,
                                                                   "dosya": yol.name}}, ensure_ascii=False), s))
    return {"bos": False, "obek": n_obek, "ref": n_ref, "catisma": catisma, "dosya": yol.name}


def _dosya_zamani(metin: str) -> str:
    return metin.replace("-", "").replace(":", "").replace(" ", "-")[:15]


# ----------------------------------------------------------------------------- iş yeniden çözümü
def yeniden_coz(conn: sqlite3.Connection, is_nolar=None, k: dict | None = None) -> list[str]:
    """Açık işlerin türetilen öbeğini (ve Kontrol nedenini) öbek düzenine göre yeniden hesaplar.

    ``obek_elle_id`` ve ``mahalle_elle`` ezilmez. Durum yalnız ``bekliyor`` ↔ ``triyaj`` arasında kendiliğinden
    değişir (öbek silinince iş Kontrol'e düşer; öbeğe eklenince çıkar); o zaman olay yazılır ve ``surum`` artar.
    Dönüş: öbeği ya da durumu değişen iş numaraları.
    """
    from . import aktarim as akt       # döngüsel içe aktarım yok: yalnız triyaj_hesapla için
    h = harita(conn)
    sql = ("SELECT is_no, il, il_k, ilce_k, mahalle_k, mahalle, mahalle_kaynak, obek_id, obek_elle_id, triyaj_nedeni, "
           "durum, surum, mahalle_elle FROM is_emri WHERE durum <> 'kapandi'")
    param: list = []
    if is_nolar is not None:
        is_nolar = list(is_nolar)
        if not is_nolar:
            return []
        sql += f" AND is_no IN ({','.join('?' * len(is_nolar))})"
        param = is_nolar
    simdi = zaman.metin()
    degisen: list[str] = []
    esad = {(r[0], r[1], r[2]): (r[3], r[4]) for r in conn.execute(
        "SELECT e.il_k, e.ilce_k, e.esad_k, m.mahalle_k, m.ad FROM mahalle_esad e JOIN mahalle m ON m.id = e.mahalle_id")}
    for r in conn.execute(sql, param).fetchall():
        mk, mahalle = r["mahalle_k"], r["mahalle"]
        if not r["mahalle_elle"] and (r["il_k"], r["ilce_k"], mk) in esad:
            mk, mahalle = esad[(r["il_k"], r["ilce_k"], mk)]
        yeni_obek = haritadan(h, r["il_k"], r["ilce_k"], mk)
        triyaj = akt.triyaj_hesapla(conn, il=r["il"], il_k=r["il_k"], ilce_k=r["ilce_k"], mahalle_k=mk,
                                    mahalle_kaynak=r["mahalle_kaynak"], obek_id=yeni_obek,
                                    obek_elle_id=r["obek_elle_id"], eski_neden=r["triyaj_nedeni"])
        yeni_durum = r["durum"]
        if r["durum"] == "bekliyor" and triyaj:
            yeni_durum = "triyaj"
        elif r["durum"] == "triyaj" and not triyaj:
            yeni_durum = "bekliyor"
        if (yeni_obek, triyaj, yeni_durum, mk) == (r["obek_id"], r["triyaj_nedeni"], r["durum"], r["mahalle_k"]):
            continue
        durum_degisti = yeni_durum != r["durum"]
        conn.execute("UPDATE is_emri SET obek_id=?, triyaj_nedeni=?, durum=?, mahalle_k=?, mahalle=?, "
                     "durum_zamani=CASE WHEN ? THEN ? ELSE durum_zamani END, surum=surum+?, guncelleme=? WHERE is_no=?",
                     (yeni_obek, triyaj, yeni_durum, mk, mahalle, durum_degisti, simdi, 1 if durum_degisti else 0,
                      simdi, r["is_no"]))
        if durum_degisti:
            olay_yaz(conn, r["is_no"], "durum", k, eski={"durum": r["durum"]},
                     yeni={"durum": yeni_durum, "_surum": r["surum"] + 1},
                     notu="Öbeği belli oldu" if yeni_durum == "bekliyor" else "Öbeği yok: Kontrol gerekli")
        degisen.append(r["is_no"])
    return degisen


def olay_yaz(conn, is_no, tur, k, *, eski=None, yeni=None, notu=None, aktarim_id=None, toplu_id=None,
             istemci_id=None, an=None) -> int:
    """is_emri_olay satırı (akis.olay_yaz ile aynı biçim; döngüsel içe aktarım olmasın diye burada da var)."""
    simdi = zaman.metin()
    cur = conn.execute(
        "INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, yeni, notu, "
        "aktarim_id, toplu_id, istemci_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, an or simdi, simdi, (k or {}).get("id"), (k or {}).get("ad"), tur,
         json.dumps(eski, ensure_ascii=False) if eski is not None else None,
         json.dumps(yeni, ensure_ascii=False) if yeni is not None else None, notu, aktarim_id, toplu_id, istemci_id))
    return cur.lastrowid


# ----------------------------------------------------------------------------- liste
def _is_sayilari(conn, simdi: str) -> dict:
    """öbek id → {acik, geciken, btk, atanmamis} ve (il_k, ilce_k, mahalle_k) → açık iş."""
    ob: dict[int, dict] = {}
    mh: dict[tuple, int] = {}
    for r in conn.execute("SELECT COALESCE(obek_elle_id, obek_id) AS o, il_k, ilce_k, mahalle_k, serit, durum, "
                          "son24, btk_hedef FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi')"):
        if r[0] is not None:
            d = ob.setdefault(r[0], {"acik": 0, "geciken": 0, "btk": 0, "atanmamis": 0})
            d["acik"] += 1
            hedef = r["btk_hedef"] if r["serit"] == "BTK" and r["btk_hedef"] else r["son24"]
            d["geciken"] += 1 if hedef and hedef < simdi else 0
            d["btk"] += 1 if r["serit"] == "BTK" else 0
            d["atanmamis"] += 1 if r["durum"] in akis.ATANMADI else 0
        anah = (r["il_k"], r["ilce_k"], r["mahalle_k"])
        mh[anah] = mh.get(anah, 0) + 1
    return {"obek": ob, "mahalle": mh}


def liste(conn: sqlite3.Connection) -> dict:
    """GET /api/obekler — işi 0 olan öbekler DAHİL; öbeksiz mahalleler (bugün işi olan) ayrıca."""
    simdi = zaman.metin()
    sayi = _is_sayilari(conn, simdi)
    kisiler = kisi.kisiler(conn)
    mahalle_adi = {(r[0], r[1], r[2]): (r[3], r[4], r[5]) for r in conn.execute(
        "SELECT il_k, ilce_k, mahalle_k, il, ilce, ad FROM mahalle")}
    ilce_adi = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute("SELECT il_k, ilce_k, il, ad FROM ilce")}
    ilce_sayi: dict[tuple, int] = {}
    for (a, b, _), n in sayi["mahalle"].items():
        ilce_sayi[(a, b)] = ilce_sayi.get((a, b), 0) + n
    h = harita(conn)
    out = []
    for o in conn.execute("SELECT * FROM obek WHERE aktif = 1 ORDER BY id").fetchall():
        mahalleler = []
        for m in conn.execute("SELECT * FROM obek_mahalle WHERE obek_id = ? ORDER BY rowid", (o["id"],)):
            il, ilce = ilce_adi.get((m["il_k"], m["ilce_k"]), ("", ""))
            if m["mahalle_k"] == "*":
                # ilçenin tamamı: o ilçede başka öbeğe tek tek verilmemiş mahallelerin işleri
                acik = sum(n for (a, b, c), n in sayi["mahalle"].items() if (a, b) == (m["il_k"], m["ilce_k"])
                           and haritadan(h, a, b, c) == o["id"])
                mahalleler.append({"ref": m["ref"], "il": il, "ilce": ilce, "mahalle": "İlçenin tamamı",
                                   "tum_ilce": True, "acik": acik})
            else:
                ad = mahalle_adi.get((m["il_k"], m["ilce_k"], m["mahalle_k"]), (il, ilce, m["ref"].split("/")[-1]))[2]
                mahalleler.append({"ref": m["ref"], "il": il, "ilce": ilce, "mahalle": ad, "tum_ilce": False,
                                   "acik": sayi["mahalle"].get((m["il_k"], m["ilce_k"], m["mahalle_k"]), 0)})
        s = sayi["obek"].get(o["id"], {"acik": 0, "geciken": 0, "btk": 0, "atanmamis": 0})
        out.append({"id": o["id"], "ad": o["ad"], "renk": o["renk"],
                    "sahip": kisi.ozet(kisiler.get(o["sahip_id"])), "yedek": kisi.ozet(kisiler.get(o["yedek_id"])),
                    "mahalleler": mahalleler, **s})
    obeksiz = []
    for (a, b, c), n in sorted(sayi["mahalle"].items(), key=lambda x: -x[1]):
        if not b or haritadan(h, a, b, c) is not None:
            continue
        il, ilce, ad = mahalle_adi.get((a, b, c), (*ilce_adi.get((a, b), ("", "")), c or ""))
        mid = conn.execute("SELECT id FROM mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (a, b, c)).fetchone()
        obeksiz.append({"il": il, "ilce": ilce, "mahalle": ad, "mahalle_id": mid[0] if mid else None, "acik": n})
    return {"surum": surum(conn), "obekler": out, "obeksiz": obeksiz}


def getir(conn, obek_id: int, aktif: bool = True) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM obek WHERE id = ?" + (" AND aktif = 1" if aktif else ""), (obek_id,)).fetchone()
    if r is None:
        raise IsYok("Bu öbek bulunamadı.")
    return r


# ----------------------------------------------------------------------------- düzenleme
def _anlik(conn, obek_idler=(), anahtarlar=()) -> dict:
    """Geri al için önceki hâl: öbek satırları + ilgili mahalle satırları."""
    obekler = {}
    for oid in set(obek_idler):
        r = conn.execute("SELECT id, ad, ad_k, renk, sahip_id, yedek_id, aktif FROM obek WHERE id=?", (oid,)).fetchone()
        if r:
            obekler[str(oid)] = dict(r)
    mahalleler = []
    for a, b, c in set(anahtarlar):
        r = conn.execute("SELECT obek_id, ref, ekleyen_id, eklenme FROM obek_mahalle WHERE il_k=? AND ilce_k=? "
                         "AND mahalle_k=?", (a, b, c)).fetchone()
        mahalleler.append([a, b, c, *(tuple(r) if r else (None, None, None, None))])
    return {"obekler": obekler, "mahalleler": mahalleler}


def _olay(conn, tur, obek_id, once, sonra, k, yeni_surum, toplu_id=None) -> int:
    return conn.execute(
        "INSERT INTO obek_olay (zaman, kullanici_id, kullanici_ad, tur, obek_id, veri, surum, toplu_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (zaman.metin(), (k or {}).get("id"), (k or {}).get("ad"), tur, obek_id,
         json.dumps({"once": once, "sonra": sonra}, ensure_ascii=False), yeni_surum, toplu_id)).lastrowid


def _etkilenen_isler(conn, anahtarlar) -> list[str]:
    out: list[str] = []
    for a, b, c in set(anahtarlar):
        if c == "*":
            out += [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE durum<>'kapandi' AND il_k=? AND "
                                               "ilce_k=?", (a, b))]
        else:
            out += [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE durum<>'kapandi' AND il_k=? AND "
                                               "ilce_k=? AND mahalle_k=?", (a, b, c))]
    return sorted(set(out))


def _sonrasi(conn) -> None:
    """İşlemden sonra (dışarıda): okunabilir ayna. Hata vermez — ayna yalnız kolaylıktır."""
    try:
        dizin = sozluk.veri_dizini() / "obek_yedek"
        dizin.mkdir(parents=True, exist_ok=True)
        veri = {"surum": surum(conn), "aciklama": "Uygulamanın öbeklerinin okunabilir aynası (kaynak veritabanıdır).",
                "obekler": [{"ad": o["ad"], "mahalleler": [m["ref"] for m in o["mahalleler"]]}
                            for o in liste(conn)["obekler"]]}
        (dizin / f"obekler-{_dosya_zamani(zaman.metin())}.json").write_text(
            json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        aynalar = sorted(p for p in dizin.glob("obekler-2*.json"))
        for p in aynalar[:-AYNA_SAKLA]:
            p.unlink(missing_ok=True)
    except OSError:
        pass


def _teknik_denetle(conn, kid) -> None:
    if kid is None:
        return
    k = kisi.kisiler(conn, [kid]).get(int(kid))
    if not k or not k["aktif"] or "teknik" not in k["gorevler"]:
        raise Gecersiz("Seçilen kişi aktif bir teknik görevli değil.", kod="teknik_gecersiz")


def olustur(conn: sqlite3.Connection, ad: str, k: dict | None, surum_: int | None) -> dict:
    ad = str(ad or "").strip()
    if not ie.anahtar(ad):
        raise Gecersiz("Öbeğe bir ad verin.", kod="alan_eksik")
    with islem(conn):
        _surum_denetle(conn, surum_)
        if conn.execute("SELECT 1 FROM obek WHERE ad_k=?", (ie.anahtar(ad),)).fetchone():
            raise Catisma("Bu adla bir öbek var.", kod="ad_var")
        simdi = zaman.metin()
        renk = conn.execute("SELECT COUNT(*) FROM obek").fetchone()[0] % 8
        oid = conn.execute("INSERT INTO obek (ad, ad_k, renk, aktif, olusturma, guncelleme) VALUES (?,?,?,1,?,?)",
                           (ad, ie.anahtar(ad), renk, simdi, simdi)).lastrowid
        yeni = _surum_arttir(conn)
        _olay(conn, "olustur", oid, None, {"obekler": {str(oid): {"ad": ad}}}, k, yeni)
    _sonrasi(conn)
    o = next(x for x in liste(conn)["obekler"] if x["id"] == oid)
    return {"obek": o, "surum": yeni}


def guncelle(conn: sqlite3.Connection, obek_id: int, k: dict | None, surum_: int | None, **alanlar) -> dict:
    """ad / renk / sahip_id / yedek_id. Aynı ad (Türkçe harf duyarsız) başka öbekte varsa 409 ad_var."""
    with islem(conn):
        _surum_denetle(conn, surum_)
        o = getir(conn, obek_id)
        once = _anlik(conn, [obek_id])
        set_, param, turler = [], [], []
        if "ad" in alanlar and alanlar["ad"] is not None:
            ad = str(alanlar["ad"]).strip()
            if not ie.anahtar(ad):
                raise Gecersiz("Öbeğe bir ad verin.", kod="alan_eksik")
            if conn.execute("SELECT 1 FROM obek WHERE ad_k=? AND id<>?", (ie.anahtar(ad), obek_id)).fetchone():
                raise Catisma("Bu adla bir öbek var.", kod="ad_var")
            set_ += ["ad=?", "ad_k=?"]
            param += [ad, ie.anahtar(ad)]
            turler.append("ad")
        if "renk" in alanlar and alanlar["renk"] is not None:
            set_.append("renk=?")
            param.append(int(alanlar["renk"]) % 8)
            turler.append("renk")
        for alan in ("sahip_id", "yedek_id"):
            if alan in alanlar:
                _teknik_denetle(conn, alanlar[alan])
                set_.append(f"{alan}=?")
                param.append(alanlar[alan])
                turler.append("sahip")
        if not set_:
            return {"obek": next(x for x in liste(conn)["obekler"] if x["id"] == obek_id), "surum": surum(conn)}
        conn.execute(f"UPDATE obek SET {', '.join(set_)}, guncelleme=? WHERE id=?", (*param, zaman.metin(), obek_id))
        yeni = _surum_arttir(conn)
        _olay(conn, turler[0], obek_id, once, _anlik(conn, [obek_id]), k, yeni)
    if "sahip_id" in alanlar or "yedek_id" in alanlar:
        from . import siralama
        siralama.oneri_hesapla(conn, [r[0] for r in conn.execute(
            "SELECT is_no FROM is_emri WHERE COALESCE(obek_elle_id, obek_id)=? AND durum NOT IN ('cozuldu','kapandi')",
            (obek_id,))])
    _sonrasi(conn)
    return {"obek": next(x for x in liste(conn)["obekler"] if x["id"] == o["id"]), "surum": yeni}


def mahalle_ekle(conn: sqlite3.Connection, obek_id: int, k: dict | None, surum_: int | None, *,
                 mahalle_idler=(), tum_ilce=(), refler=(), tasi: bool = False, toplu_id: str | None = None) -> dict:
    """Mahalleleri (ya da ilçenin tamamını) öbeğe ekler. Başka öbekteyse ``tasi`` olmadan 409 baska_obekte."""
    with islem(conn):
        _surum_denetle(conn, surum_)
        getir(conn, obek_id)
        ilce_h = sozluk.ilce_haritasi(conn)
        hedefler: list[tuple[str, str, str, str]] = []
        for mid in mahalle_idler or ():
            m = sozluk.getir(conn, int(mid))
            if m is None:
                raise Gecersiz("Mahalle bulunamadı.", kod="alan_eksik")
            hedefler.append((m["il_k"], m["ilce_k"], m["mahalle_k"], f"{m['il']}/{m['ilce']}/{m['ad']}"))
        for t in tum_ilce or ():
            c = sozluk.ilce_coz(ilce_h, t.get("il") or "", t.get("ilce") or "")
            if c is None:
                raise Gecersiz("Bu ilçe Bursa ya da Yalova'da değil.", kod="ilce_yok")
            hedefler.append((c[0], c[1], "*", f"{c[2]}/{c[3]}/*"))
        for ref in refler or ():
            c = _ref_tamamla(ilce_h, ref)
            if c is None:
                raise Gecersiz(f"Tanınmayan mahalle: {ref}", kod="alan_eksik")
            hedefler.append(c)
        if not hedefler:
            raise Gecersiz("Eklenecek mahalle seçin.", kod="alan_eksik")
        catisma = []
        for a, b, c, ref in hedefler:
            r = conn.execute("SELECT om.obek_id, o.ad, om.ref FROM obek_mahalle om JOIN obek o ON o.id=om.obek_id "
                             "WHERE om.il_k=? AND om.ilce_k=? AND om.mahalle_k=?", (a, b, c)).fetchone()
            if r and r[0] != obek_id:
                catisma.append({"ref": ref, "obek": {"id": r[0], "ad": r[1]}})
        if catisma and not tasi:
            ilk = catisma[0]
            raise Catisma(f"{ilk['ref'].split('/')[-1]} şu an '{ilk['obek']['ad']}' öbeğinde. Buraya taşınsın mı?",
                          kod="baska_obekte", catisma=catisma)
        anahtarlar = [(a, b, c) for a, b, c, _ in hedefler]
        eski_obekler = [c["obek"]["id"] for c in catisma]
        once = _anlik(conn, [obek_id, *eski_obekler], anahtarlar)
        simdi = zaman.metin()
        for a, b, c, ref in hedefler:
            conn.execute("DELETE FROM obek_mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (a, b, c))
            conn.execute("INSERT INTO obek_mahalle (il_k, ilce_k, mahalle_k, obek_id, ref, ekleyen_id, eklenme) "
                         "VALUES (?,?,?,?,?,?,?)", (a, b, c, obek_id, ref, (k or {}).get("id"), simdi))
        yeni = _surum_arttir(conn)
        olay_id = _olay(conn, "tasi" if catisma else "mahalle_ekle", obek_id, once,
                        _anlik(conn, [obek_id, *eski_obekler], anahtarlar), k, yeni, toplu_id)
        etkilenen = yeniden_coz(conn, _etkilenen_isler(conn, anahtarlar), k)
    _sonrasi_ve_oneri(conn, etkilenen)
    return {"surum": yeni, "etkilenen_is": len(etkilenen), "obekler": liste(conn)["obekler"], "geri_al_olay_id": olay_id}


def mahalle_cikar(conn: sqlite3.Connection, obek_id: int, refler, k: dict | None, surum_: int | None) -> dict:
    """Mahalleleri öbekten çıkarır. Öbek boş kalsa da SİLİNMEZ (F1)."""
    with islem(conn):
        _surum_denetle(conn, surum_)
        getir(conn, obek_id)
        ilce_h = sozluk.ilce_haritasi(conn)
        anahtarlar = []
        for ref in refler or ():
            c = _ref_tamamla(ilce_h, ref)
            if c is None:
                continue
            if conn.execute("SELECT 1 FROM obek_mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=? AND obek_id=?",
                            (c[0], c[1], c[2], obek_id)).fetchone():
                anahtarlar.append(c[:3])
        if not anahtarlar:
            raise Gecersiz("Bu mahalle bu öbekte değil.", kod="alan_eksik")
        once = _anlik(conn, [obek_id], anahtarlar)
        for a, b, c in anahtarlar:
            conn.execute("DELETE FROM obek_mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (a, b, c))
        yeni = _surum_arttir(conn)
        olay_id = _olay(conn, "mahalle_cikar", obek_id, once, _anlik(conn, [obek_id], anahtarlar), k, yeni)
        etkilenen = yeniden_coz(conn, _etkilenen_isler(conn, anahtarlar), k)
    _sonrasi_ve_oneri(conn, etkilenen)
    return {"surum": yeni, "etkilenen_is": len(etkilenen), "obekler": liste(conn)["obekler"], "geri_al_olay_id": olay_id}


def sil(conn: sqlite3.Connection, obek_id: int, k: dict | None, surum_: int | None) -> dict:
    """Yumuşak silme: öbek pasif, adı serbest kalır (ad_k#id), mahalleleri öbeksiz olur. 10 dk geri alınabilir."""
    with islem(conn):
        _surum_denetle(conn, surum_)
        getir(conn, obek_id)
        anahtarlar = [tuple(r) for r in conn.execute(
            "SELECT il_k, ilce_k, mahalle_k FROM obek_mahalle WHERE obek_id=?", (obek_id,))]
        once = _anlik(conn, [obek_id], anahtarlar)
        conn.execute("DELETE FROM obek_mahalle WHERE obek_id=?", (obek_id,))
        conn.execute("UPDATE obek SET aktif=0, ad_k = ad_k || '#' || id, guncelleme=? WHERE id=?",
                     (zaman.metin(), obek_id))
        # elle bu öbeğe verilmiş işler de öbeksiz kalır (kayıt olay defterinde)
        elle = [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE obek_elle_id=? AND durum<>'kapandi'",
                                           (obek_id,))]
        once["elle_isler"] = elle
        conn.execute("UPDATE is_emri SET obek_elle_id=NULL, surum=surum+1, guncelleme=? WHERE obek_elle_id=?",
                     (zaman.metin(), obek_id))
        yeni = _surum_arttir(conn)
        olay_id = _olay(conn, "sil", obek_id, once, _anlik(conn, [obek_id], anahtarlar), k, yeni)
        etkilenen = yeniden_coz(conn, sorted(set(_etkilenen_isler(conn, anahtarlar)) | set(elle)), k)
        obeksiz = conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi') AND "
                               "COALESCE(obek_elle_id, obek_id) IS NULL").fetchone()[0]
    _sonrasi_ve_oneri(conn, etkilenen)
    return {"surum": yeni, "geri_al_olay_id": olay_id, "obeksiz_kalan_is": obeksiz, "etkilenen_is": len(etkilenen),
            "obekler": liste(conn)["obekler"]}


def geri_al(conn: sqlite3.Connection, olay_id: int, k: dict | None, surum_: int | None) -> dict:
    """Son öbek değişikliğini geri alır: 10 dk içinde, aynı kişi, arada başka öbek değişikliği yoksa."""
    with islem(conn):
        o = conn.execute("SELECT * FROM obek_olay WHERE id=?", (olay_id,)).fetchone()
        if o is None or o["tur"] in ("json_aktarim", "geri_al"):
            raise Catisma("Bu değişiklik geri alınamaz.", kod="geri_alinamaz")
        if (k or {}).get("id") != o["kullanici_id"]:
            raise Catisma("Yalnız değişikliği yapan kişi geri alabilir.", kod="geri_alinamaz")
        yas = (zaman.simdi() - zaman.oku(o["zaman"])).total_seconds() / 60
        if yas > GERI_AL_DK:
            raise Catisma("Bu değişiklik artık geri alınamaz.", kod="sure_doldu")
        if surum(conn) != o["surum"] or (surum_ is not None and int(surum_) != o["surum"]):
            raise Catisma("Bu değişiklik artık geri alınamaz; öbekler sonra değişti.", kod="geri_alinamaz")
        veri = json.loads(o["veri"])
        once, sonra = veri.get("once") or {}, veri.get("sonra") or {}
        anahtarlar = [tuple(m[:3]) for m in once.get("mahalleler", [])]
        if o["tur"] == "olustur":
            oid = int(next(iter(sonra.get("obekler", {})), 0) or o["obek_id"])
            if conn.execute("SELECT COUNT(*) FROM obek_mahalle WHERE obek_id=?", (oid,)).fetchone()[0]:
                raise Catisma("Bu değişiklik artık geri alınamaz.", kod="geri_alinamaz")
            conn.execute("UPDATE obek SET aktif=0, ad_k = ad_k || '#' || id WHERE id=?", (oid,))
        for oid, d in once.get("obekler", {}).items():
            if d["aktif"] and conn.execute("SELECT 1 FROM obek WHERE ad_k=? AND id<>?", (d["ad_k"], int(oid))).fetchone():
                raise Catisma("Bu adla bir öbek var; geri alınamadı.", kod="ad_var")
            conn.execute("UPDATE obek SET ad=?, ad_k=?, renk=?, sahip_id=?, yedek_id=?, aktif=?, guncelleme=? WHERE id=?",
                         (d["ad"], d["ad_k"], d["renk"], d["sahip_id"], d["yedek_id"], d["aktif"], zaman.metin(),
                          int(oid)))
        for a, b, c, oid, ref, ekleyen, eklenme in once.get("mahalleler", []):
            conn.execute("DELETE FROM obek_mahalle WHERE il_k=? AND ilce_k=? AND mahalle_k=?", (a, b, c))
            if oid is not None:
                conn.execute("INSERT INTO obek_mahalle (il_k, ilce_k, mahalle_k, obek_id, ref, ekleyen_id, eklenme) "
                             "VALUES (?,?,?,?,?,?,?)", (a, b, c, oid, ref, ekleyen, eklenme))
        for is_no in once.get("elle_isler", []):
            conn.execute("UPDATE is_emri SET obek_elle_id=?, surum=surum+1 WHERE is_no=? AND obek_elle_id IS NULL",
                         (o["obek_id"], is_no))
        yeni = _surum_arttir(conn)
        _olay(conn, "geri_al", o["obek_id"], sonra, once, k, yeni)
        etkilenen = yeniden_coz(conn, sorted(set(_etkilenen_isler(conn, anahtarlar)) | set(once.get("elle_isler", []))), k)
    _sonrasi_ve_oneri(conn, etkilenen)
    return {"surum": yeni, "etkilenen_is": len(etkilenen), "obekler": liste(conn)["obekler"]}


def bol(conn: sqlite3.Connection, obek_id: int, parca: int, onizle: bool, k: dict | None, surum_: int | None) -> dict:
    """Öbeği mahallelerine göre k parçaya kalıcı böler (C21). Özgün öbek 1. parçayı ve adını korur;
    diğer parçalar "<ad> 2", "<ad> 3" … adıyla, aynı ev teknisyeniyle kurulur. İlçenin tamamı bölünmez (1. parçada)."""
    from operasyon import yakinlik
    parca = int(parca)
    if not 2 <= parca <= 10:
        raise Gecersiz("Parça sayısı 2 ile 10 arasında olmalı.", kod="alan_eksik")
    o = getir(conn, obek_id)
    satirlar = conn.execute(
        "SELECT om.il_k, om.ilce_k, om.mahalle_k, om.ref, m.lat, m.lon, m.ad FROM obek_mahalle om "
        "LEFT JOIN mahalle m ON m.il_k=om.il_k AND m.ilce_k=om.ilce_k AND m.mahalle_k=om.mahalle_k "
        "WHERE om.obek_id=? ORDER BY om.rowid", (obek_id,)).fetchall()
    tekil = [r for r in satirlar if r["mahalle_k"] != "*" and r["lat"] is not None]
    if len(tekil) < parca:
        raise Gecersiz("Bölmek için yeterli (konumu bilinen) mahalle yok.", kod="alan_eksik")
    sayi = _is_sayilari(conn, zaman.metin())["mahalle"]
    agirlik = [max(1, sayi.get((r["il_k"], r["ilce_k"], r["mahalle_k"]), 0)) for r in tekil]
    etiket = yakinlik.dengeli_bol([r["lat"] for r in tekil], [r["lon"] for r in tekil], parca, agirlik=agirlik)
    gruplar: dict[int, list] = {}
    for r, e, w in zip(tekil, etiket, agirlik):
        gruplar.setdefault(int(e), []).append((r, w))
    for r in satirlar:
        if r not in tekil:
            gruplar.setdefault(1, []).append((r, 0))
    parcalar = [{"mahalleler": [x[0]["ref"] for x in gruplar.get(i, [])],
                 "is": sum(sayi.get((x[0]["il_k"], x[0]["ilce_k"], x[0]["mahalle_k"]), 0) for x in gruplar.get(i, []))}
                for i in sorted(gruplar)]
    if onizle:
        return {"parcalar": parcalar, "surum": surum(conn)}
    toplu = f"bol-{obek_id}-{zaman.metin()}"
    s = surum_
    for i, p in enumerate(parcalar[1:], start=2):
        ad = f"{o['ad']} {i}"
        while conn.execute("SELECT 1 FROM obek WHERE ad_k=?", (ie.anahtar(ad),)).fetchone():
            ad += "'"
        yeni = olustur(conn, ad, k, s)
        guncelle(conn, yeni["obek"]["id"], k, yeni["surum"], sahip_id=o["sahip_id"], yedek_id=o["yedek_id"])
        s = mahalle_ekle(conn, yeni["obek"]["id"], k, surum(conn), refler=p["mahalleler"], tasi=True,
                         toplu_id=toplu)["surum"]
    return {"parcalar": parcalar, "surum": surum(conn), "obekler": liste(conn)["obekler"]}


def _sonrasi_ve_oneri(conn, etkilenen) -> None:
    if etkilenen:
        from . import siralama
        siralama.oneri_hesapla(conn, etkilenen)
    _sonrasi(conn)
