"""BOSS iş ayrıntısı (önden okuma + kalıcı önbellek) + BOSS ekip listesi + görev iç kimliği (uuid).

İki yol, tek depo (``boss_detay`` tablosu; task no başına normalleştirilmiş sekmeler + ham, zlib'li JSON):
1) Önden okuma: eşitleme yanıtı ``detay_onden`` (ayrıntısı saklı OLMAYAN ya da parmak izi DEĞİŞMİŞ açık işler;
   ``detay_gerekli``) → eklenti her işin 9 sekmesini en çok 3 istekle okur (kullanıcının açtığı iş araya girer) →
   her iş okununca ``POST /api/boss/detay-onden`` (``onden_yaz``) → yanıt sıradaki işleri verir. Sıra: önce
   kullanıcının açacağı işler — TASKS'ın o an gösterdiği ilk işler (``oncelik_yaz``), bugün atanan / bugün randevulu,
   randevulu, sonra en yeni. Neyin okunmadığını sunucu bilir (depo): internet, bilgisayar ya da uygulama kesintisinden
   sonra eklenti sorunca kaldığı yerden sürer. Kalan süre ölçülen hızdan (``detay_durumu``).
2) İstek: kullanıcı ``POST /api/isler/{is_no}/boss-detay`` → bellekte istek kuyruğu → eklenti
   ``GET /api/boss/istekler?bekle=20`` (uzun yoklama: istek gelir gelmez döner) → kanca 9 sekmeyi aynı anda okur →
   ``POST /api/boss/detay`` (``yanit_al``). Kayıt 10 dk'dan (``DETAY_TAZE_SN``) taze
   ise yeni istek açılmaz; eskiyse kayıt HEMEN döner ve arkada tazelenir (``yenileniyor``).
``GET /api/isler/{is_no}/boss-detay`` (``oku``) kaydı zamanıyla hemen verir.

- Kişisel veri (iletişim, ham) saklama kurallarına tabidir: iş kapanınca kayıt silinir (``kapananlari_sil``,
  ``saklama.uygula``); günlüğe yazılmaz. Önden okumada gelen iletişim sekmesi telefon önden okumasının yerini de tutar.
- Görev no → BOSS iç kimliği (uuid) eşlemesi (``boss_gorev_kimlik``) ve ekip adları (``ayar.boss_ekipler``).
- Telefonlar yalnız ``is.musteri`` izniyle gösterilir; izin yoksa iletişim sekmesi ve ham verideki telefon
  benzeri değerler gizlenir.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
import threading
import time
import zlib

from . import ek_sema, zaman
from .hatalar import Gecersiz, V2Hata
from .islem import islem

ONBELLEK_SN = 10 * 60
DETAY_TAZE_SN = 10 * 60            # bundan eski kayıt açılınca arkada tazelenir
EN_COK_ONDEN = 50                  # önden okuma için tek seferde verilen iş
ONDEN_HATA_SN = 10 * 60            # okunamayan iş bu süre boyunca yeniden verilmez
IS_BASINA_SN = 2.5                 # ölçüm yokken tahmin: 9 sekme, 3'erli, ~0,7 sn BOSS yanıtı + iş arası
HIZ_PENCERE_SN = 10 * 60           # kalan süre son 10 dk'da okunan işlerden ölçülür
ONCELIK_SN = 15 * 60               # TASKS'ın bildirdiği ekrandaki işler bu kadar süre öne alınır
EN_COK_ONCELIK = 200
ISTEK_ZAMAN_ASIMI_SN = 90          # eklenti bu sürede yanıtlamazsa istek düşer
YENIDEN_VER_SN = 30                # alınmış ama yanıtlanmamış istek bu kadar sonra yeniden verilir
EN_COK_ISTEK = 50
EN_COK_ONBELLEK = 300

# BOSS sekmesi → sade ad (eklentideki uç listesiyle aynı adlar)
SEKMELER = ("urunler", "iletisim", "aciklama", "ariza_gecmisi", "fotograflar", "cihaz", "ariza_nedeni", "notlar",
            "evraklar", "tarihce", "adres_teyidi")

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_TEL_RE = re.compile(r"(?<!\d)(?:\+?90[\s-]?)?0?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)")

_KILIT = threading.Lock()
_ISTEKLER: dict[str, dict] = {}     # is_no → {istek_id, is_no, uuid, olusma, verildi}
_ONBELLEK: dict[str, dict] = {}     # is_no → {zaman_sn, zaman, uuid, sekmeler, ham, hatalar}
_HATALAR: dict[str, dict] = {}      # is_no → {zaman_sn, hata} (son başarısız deneme; kısa süreli)
_ONDEN_HATA: dict[str, float] = {}  # task_no → son başarısız önden okuma
_ONDEN_OKUNAN: list[tuple[float, int]] = []   # (zaman, okunan iş) — hız ölçümü (son HIZ_PENCERE_SN)
_ONCELIK: dict = {"zaman": 0.0, "is_nolar": []}   # TASKS'ın o an gösterdiği ilk işler (sırasıyla)

SEMA = (
    "CREATE TABLE IF NOT EXISTS boss_gorev_kimlik (task_no TEXT PRIMARY KEY, uuid TEXT NOT NULL, guncelleme TEXT)",
)


def sifirla() -> None:
    """Testler için bellek durumunu temizler."""
    with _KILIT:
        _ISTEKLER.clear()
        _ONBELLEK.clear()
        _HATALAR.clear()
        _ONDEN_HATA.clear()
        _ONDEN_OKUNAN.clear()
        _ONCELIK.update(zaman=0.0, is_nolar=[])


# ----------------------------------------------------------------------------- uuid deposu
def _sema(conn) -> None:
    for s in SEMA:
        conn.execute(s)


def uuid_yaz(conn, gorevler: list) -> int:
    """Eşitleme görevlerindeki ``boss_uuid`` alanını kalıcı yazar (task_no → uuid). Dönüş: yazılan sayı."""
    ciftler = []
    for g in gorevler or ():
        if not isinstance(g, dict):
            continue
        no, u = str(g.get("task_no") or "").strip(), str(g.get("boss_uuid") or "").strip()
        if no and UUID_RE.match(u):
            ciftler.append((no, u.lower(), zaman.metin()))
    if not ciftler:
        return 0
    _sema(conn)
    conn.executemany("INSERT INTO boss_gorev_kimlik(task_no, uuid, guncelleme) VALUES(?,?,?) ON CONFLICT(task_no) "
                     "DO UPDATE SET uuid=excluded.uuid, guncelleme=excluded.guncelleme", ciftler)
    conn.commit()
    return len(ciftler)


def uuid_bul(conn, is_no: str) -> str | None:
    _sema(conn)
    r = conn.execute("SELECT boss_task_no FROM is_emri WHERE is_no=?", (is_no,)).fetchone()
    no = (r[0] if r and r[0] else None) or is_no
    r = conn.execute("SELECT uuid FROM boss_gorev_kimlik WHERE task_no=?", (str(no),)).fetchone()
    return r[0] if r else None


# ----------------------------------------------------------------------------- ekipler
def ekipler_yaz(conn, ekipler) -> int | None:
    """Eklentinin gönderdiği BOSS teknik ekip listesi → ``ayar.boss_ekipler``. Geçersizse dokunulmaz."""
    if not isinstance(ekipler, list):
        return None
    temiz, gorulen = [], set()
    for e in ekipler[:5000]:
        if not isinstance(e, dict):
            continue
        ad = str(e.get("ad") or "").strip()[:200]
        if not ad:
            continue
        kid = e.get("id")
        kid = str(kid).strip()[:80] if kid not in (None, "") else None
        anahtar = (kid, ad)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        aktif = e.get("aktif")
        temiz.append({"id": kid, "ad": ad, "aktif": True if aktif is None else bool(aktif)})
    temiz.sort(key=lambda x: (not x["aktif"], x["ad"]))
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                 ("boss_ekipler", json.dumps({"zaman": zaman.metin(), "ekipler": temiz}, ensure_ascii=False)))
    from . import kisi
    try:
        kisi.boss_ekipleri_esitle(conn, temiz)
    except Exception:          # noqa: BLE001 — ekip kişileri kurulamasa da ekip listesi yazılmış olsun
        import logging
        logging.getLogger("operasyon.boss").exception("BOSS ekipleri kişilere eşitlenemedi")
    conn.commit()
    return len(temiz)


def ekipler(conn) -> dict:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='boss_ekipler'").fetchone()
    try:
        d = json.loads(r[0]) if r and r[0] else {}
    except ValueError:
        d = {}
    return {"zaman": d.get("zaman"), "ekipler": d.get("ekipler") or []}


# ----------------------------------------------------------------------------- istek kuyruğu
def _temizle(simdi: float) -> None:
    for no in [n for n, i in _ISTEKLER.items() if simdi - i["olusma"] > ISTEK_ZAMAN_ASIMI_SN]:
        _HATALAR[no] = {"zaman_sn": simdi, "hata": "zaman_asimi"}
        del _ISTEKLER[no]
    for no in [n for n, h in _HATALAR.items() if simdi - h["zaman_sn"] > ONBELLEK_SN]:
        del _HATALAR[no]


def iste(conn, is_no: str, yenile: bool = False) -> dict:
    """Ayrıntı isteği kuyruğa girer (aynı iş için bekleyen varsa yenisi açılmaz). Kayıt taze ise (10 dk) istek
    açılmaz: 'hazir'. Kayıt eskiyse arkada tazelenir ve yine 'hazir' döner (``yenileniyor``); ``yenile=True``
    (kullanıcı "yenile" dedi) her zaman istek açar ve 'bekliyor' döner."""
    u = uuid_bul(conn, is_no)
    if not u:
        raise V2Hata("Bu işin BOSS kimliği henüz bilinmiyor. BOSS Yardımcısı bir eşitleme yapınca yeniden deneyin.",
                     kod="boss_kimlik_yok", durum=409)
    c = _kayit(conn, is_no)
    simdi = time.time()
    taze = bool(c) and simdi - c["zaman_sn"] < DETAY_TAZE_SN
    with _KILIT:
        _temizle(simdi)
        if not yenile and taze:
            return {"durum": "hazir", "is_no": is_no}
        durum = "hazir" if c and not yenile else "bekliyor"
        if is_no in _ISTEKLER:
            return {"durum": durum, "is_no": is_no, "istek_id": _ISTEKLER[is_no]["istek_id"], "yenileniyor": bool(c)}
        if len(_ISTEKLER) >= EN_COK_ISTEK:
            if c:
                return {"durum": "hazir", "is_no": is_no, "yenileniyor": False}
            raise V2Hata("Çok fazla bekleyen BOSS isteği var; biraz sonra deneyin.", kod="kuyruk_dolu", durum=429)
        _HATALAR.pop(is_no, None)
        iid = secrets.token_hex(8)
        _ISTEKLER[is_no] = {"istek_id": iid, "is_no": is_no, "uuid": u, "olusma": simdi, "verildi": None}
    return {"durum": durum, "is_no": is_no, "istek_id": iid, "yenileniyor": bool(c)}


async def istek_bekle(sn: float) -> None:
    """Uzun yoklamada bir sonraki bakışa dek bekleme (kısa: kullanıcının isteği en geç ~0,1 sn sonra görülür)."""
    import asyncio
    await asyncio.sleep(min(0.1, max(0.0, sn)))


# ----------------------------------------------------------------------------- "şimdi eşitle" isteği
# MAP/TASKS ⟳: kullanıcı BOSS'ta bir şeyi değiştirdi (ör. askıya aldı) ve beklemek istemiyor. İstek eklentinin uzun
# yoklamasına (GET /api/boss/istekler → "esitle": true) bir kez verilir; eklenti hemen bir eşitleme başlatır.
ESITLE_ARA_SN = 20                      # art arda basışlar en çok bu aralıkla eşitleme doğurur
_ESITLE = {"istendi": 0.0, "verildi": 0.0}


def esitle_iste() -> dict:
    simdi = time.time()
    with _KILIT:
        if simdi - _ESITLE["istendi"] < ESITLE_ARA_SN:
            return {"istendi": False, "sonraki_sn": int(ESITLE_ARA_SN - (simdi - _ESITLE["istendi"])) + 1}
        _ESITLE["istendi"] = simdi
    return {"istendi": True}


def esitle_ver() -> bool:
    """Bekleyen "şimdi eşitle" isteği varsa bir kez True."""
    with _KILIT:
        if _ESITLE["istendi"] > _ESITLE["verildi"]:
            _ESITLE["verildi"] = time.time()
            return True
    return False


def istekler_ver() -> list[dict]:
    """Eklentiye verilecek istekler (verilmemiş ya da 30 sn'dir yanıtsız olanlar), en eskisi önce."""
    simdi = time.time()
    with _KILIT:
        _temizle(simdi)
        out = []
        for i in sorted(_ISTEKLER.values(), key=lambda x: x["olusma"]):
            if i["verildi"] is None or simdi - i["verildi"] > YENIDEN_VER_SN:
                i["verildi"] = simdi
                out.append({"istek_id": i["istek_id"], "is_no": i["is_no"], "uuid": i["uuid"]})
        return out


# ----------------------------------------------------------------------------- normalleştirme
def _ilk(o: dict, *adlar):
    """Sözlükte (iç içe bir düzey dahil) adı kalıplardan birine uyan ilk dolu değer."""
    if not isinstance(o, dict):
        return None
    for kalip in adlar:
        rx = re.compile(kalip, re.I)
        for k, v in o.items():
            if rx.search(k) and v not in (None, "", [], {}) and not isinstance(v, (dict, list)):
                return v
        for k, v in o.items():
            if isinstance(v, dict) and rx.search(k):
                for a in ("name", "description", "value", "label", "text"):
                    if v.get(a) not in (None, ""):
                        return v[a]
    return None


def _dizi(veri) -> list:
    """Yanıttaki asıl kayıt dizisi (``content``/``data``/``items``… ya da kendisi)."""
    if isinstance(veri, list):
        return veri
    if isinstance(veri, dict):
        for k in ("content", "data", "items", "list", "result", "results", "records", "body", "payload"):
            v = veri.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                ic = _dizi(v)
                if ic:
                    return ic
        for v in veri.values():
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                return v
        return [veri] if veri else []
    return [] if veri in (None, "") else [veri]


def _duz(o, onek="", cikti=None, d=0) -> dict:
    cikti = {} if cikti is None else cikti
    if not isinstance(o, dict) or d > 2:
        return cikti
    for k, v in o.items():
        y = f"{onek}.{k}" if onek else str(k)
        if isinstance(v, dict):
            _duz(v, y, cikti, d + 1)
        elif isinstance(v, list):
            if v and all(not isinstance(x, (dict, list)) for x in v):
                cikti[y] = ", ".join(str(x) for x in v[:20])
        elif v not in (None, ""):
            cikti[y] = v
    return cikti


def _metin(v):
    if v is None:
        return None
    s = str(v).strip()
    return s[:4000] or None


def _genel(veri) -> list[dict]:
    return [_duz(x) if isinstance(x, dict) else {"deger": x} for x in _dizi(veri)][:500]


def _telefonlar(o) -> list[str]:
    out = []

    def gez(x, anahtar=""):
        if isinstance(x, dict):
            for k, v in x.items():
                gez(v, k)
        elif isinstance(x, list):
            for v in x:
                gez(v, anahtar)
        elif isinstance(x, (str, int)) and x not in ("", None):
            s = str(x)
            if re.search(r"phone|gsm|msisdn|tel|mobile|contact.?(no|number)", anahtar, re.I) or _TEL_RE.search(s):
                for m in (_TEL_RE.findall(s) or ([s] if re.search(r"\d{7,}", s) else [])):
                    t = m.strip()
                    if t and t not in out:
                        out.append(t)
    gez(o)
    return out[:10]


def _iletisim(veri) -> list[dict]:
    out = []
    for x in _dizi(veri):
        if not isinstance(x, dict):
            continue
        out.append({"ad": _metin(_ilk(x, r"^(full.?)?name$", r"name", r"contact")),
                    "tur": _metin(_ilk(x, r"type", r"role", r"relation")),
                    "telefonlar": _telefonlar(x),
                    "eposta": _metin(_ilk(x, r"e.?mail"))})
    return out


def _aciklama(veri) -> list[dict]:
    out = []
    for x in _dizi(veri):
        if isinstance(x, str):
            out.append({"metin": _metin(x), "tarih": None, "yazan": None, "tur": None})
        elif isinstance(x, dict):
            out.append({"metin": _metin(_ilk(x, r"^description$", r"^(text|note|comment|content|message)$",
                                             r"desc", r"note", r"comment", r"text")),
                        "tarih": _metin(_ilk(x, r"create.?(d|date|time)", r"date", r"time")),
                        "yazan": _metin(_ilk(x, r"(created|creator|user|author|owner).?(name|by)?", r"user")),
                        "tur": _metin(_ilk(x, r"type", r"category"))})
    return out


def _tarihce(veri) -> list[dict]:
    out = []
    for x in _dizi(veri):
        if not isinstance(x, dict):
            continue
        out.append({"tarih": _metin(_ilk(x, r"(create|action|event|operation|update).?(d|date|time)", r"date", r"time")),
                    "olay": _metin(_ilk(x, r"^(action|event|operation|status|activity).?(name|desc|description)?$", r"desc", r"type")),
                    "yazan": _metin(_ilk(x, r"(created|user|operator|author).?(name|by)?", r"user", r"team")),
                    "aciklama": _metin(_ilk(x, r"^(description|note|comment|detail)s?$", r"note", r"comment"))})
    return out


def _fotograflar(veri) -> list[dict]:
    out = []
    for x in _dizi(veri):
        if not isinstance(x, dict):
            continue
        url = _ilk(x, r"^(url|link|path|uri|href)$", r"(download|file|content|image|photo|thumb).?(url|link|path|uri)",
                   r"url", r"link", r"path")
        out.append({"url": _metin(url), "ad": _metin(_ilk(x, r"(file|content|document)?.?name$", r"title")),
                    "tur": _metin(_ilk(x, r"(content|mime|file|media)?.?type$")),
                    "tarih": _metin(_ilk(x, r"(create|upload).?(d|date|time)", r"date")),
                    "id": _metin(_ilk(x, r"^(id|content.?id|file.?id|uuid)$"))})
    return out


def _urunler(veri) -> list[dict]:
    out = []
    for x in _dizi(veri):
        if not isinstance(x, dict):
            continue
        out.append({"ad": _metin(_ilk(x, r"^(product|offer|tariff|service)?.?name$", r"name", r"desc")),
                    "kod": _metin(_ilk(x, r"(product|offer)?.?(code|no|number)$")),
                    "durum": _metin(_ilk(x, r"status")),
                    "alan": _duz(x)})
    return out


def _ariza_nedeni(veri) -> dict | list | None:
    if isinstance(veri, dict) and not _dizi(veri)[1:]:
        return {"neden": _metin(_ilk(veri, r"(trouble|fault|reason).?(name|desc)?", r"name", r"desc")),
                "kod": _metin(_ilk(veri, r"code")), "alan": _duz(veri)}
    return _genel(veri)


_NORMAL = {
    "urunler": _urunler, "iletisim": _iletisim, "aciklama": _aciklama, "notlar": _aciklama, "tarihce": _tarihce,
    "ariza_gecmisi": _tarihce, "fotograflar": _fotograflar, "ariza_nedeni": _ariza_nedeni,
    "cihaz": _genel, "evraklar": _genel, "adres_teyidi": _genel,
}


def _tel_gizle(o):
    if isinstance(o, dict):
        return {k: ("•••" if re.search(r"phone|gsm|msisdn|mobile", str(k), re.I) and v not in (None, "")
                    else _tel_gizle(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [_tel_gizle(x) for x in o]
    if isinstance(o, str):
        return _TEL_RE.sub("•••", o)
    return o


def normallestir(sekmeler_ham: dict) -> tuple[dict, dict, dict]:
    """Eklentiden gelen ``{sekme: {durum, veri}}`` → (sekmeler, ham, hatalar). Bozuk sekme düşmez, hata olur."""
    sekmeler, ham, hatalar = {}, {}, {}
    for ad in SEKMELER:
        g = sekmeler_ham.get(ad) if isinstance(sekmeler_ham, dict) else None
        if not isinstance(g, dict):
            sekmeler[ad] = None
            continue
        if g.get("hata"):
            hatalar[ad] = str(g["hata"])[:120]
            sekmeler[ad] = None
            continue
        veri = g.get("veri")
        ham[ad] = veri
        try:
            sekmeler[ad] = _NORMAL[ad](veri)
        except Exception:          # noqa: BLE001 — BOSS biçimi beklenmedikse sekme boş, ham durur
            sekmeler[ad] = None
            hatalar[ad] = "cozulemedi"
    # "Notlar" için ayrı uç yoksa açıklamalardan türü not olanlar
    if sekmeler.get("notlar") is None and isinstance(sekmeler.get("aciklama"), list):
        notlar = [a for a in sekmeler["aciklama"] if re.search(r"not", str(a.get("tur") or ""), re.I)]
        sekmeler["notlar"] = notlar
    return sekmeler, ham, hatalar


# ----------------------------------------------------------------------------- yanıt + okuma
def yanit_al(govde: dict, conn: sqlite3.Connection | None = None) -> dict:
    """Eklentinin ``POST /api/boss/detay`` gövdesi: {istek_id, is_no, uuid, sekmeler:{ad:{veri|hata}}, hata?}.
    ``conn`` verilirse (açık işte) kalıcı depoya da yazılır."""
    if not isinstance(govde, dict):
        raise Gecersiz("Gövde JSON nesnesi olmalı.", kod="alan_eksik")
    is_no = str(govde.get("is_no") or "").strip()
    iid = str(govde.get("istek_id") or "").strip()
    simdi = time.time()
    with _KILIT:
        istek = _ISTEKLER.get(is_no)
        if not istek or istek["istek_id"] != iid:
            raise V2Hata("Bu istek artık beklenmiyor.", kod="istek_yok", durum=404)
        del _ISTEKLER[is_no]
        if govde.get("hata"):
            _HATALAR[is_no] = {"zaman_sn": simdi, "hata": str(govde["hata"])[:120]}
            return {"ok": True, "durum": "hata"}
    sekmeler, ham, hatalar = normallestir(govde.get("sekmeler") or {})
    kayit = {"zaman_sn": simdi, "zaman": zaman.metin(), "uuid": istek["uuid"], "sekmeler": sekmeler, "ham": ham,
             "hatalar": hatalar}
    _bellege(is_no, kayit)
    if conn is not None:
        try:
            r = conn.execute("SELECT boss_task_no FROM is_emri WHERE is_no=? AND durum NOT IN ('cozuldu','kapandi')",
                             (is_no,)).fetchone()
            if r and r[0]:
                kaydet(conn, r[0], kayit)
        except sqlite3.Error:
            import logging
            logging.getLogger("operasyon.boss").exception("BOSS ayrıntısı kalıcı yazılamadı")
    return {"ok": True, "durum": "hazir", "sekme": sum(1 for v in sekmeler.values() if v is not None),
            "hata": len(hatalar)}


def _bellege(is_no: str, kayit: dict) -> None:
    with _KILIT:
        _ONBELLEK[is_no] = kayit
        if len(_ONBELLEK) > EN_COK_ONBELLEK:
            for no in sorted(_ONBELLEK, key=lambda n: _ONBELLEK[n]["zaman_sn"])[:len(_ONBELLEK) - EN_COK_ONBELLEK]:
                del _ONBELLEK[no]


# ----------------------------------------------------------------------------- kalıcı depo
def _paketle(kayit: dict) -> bytes:
    return zlib.compress(json.dumps({"sekmeler": kayit["sekmeler"], "ham": kayit["ham"], "hatalar": kayit["hatalar"]},
                                    ensure_ascii=False, default=str).encode("utf-8"), 6)


def kaydet(conn: sqlite3.Connection, task_no: str, kayit: dict) -> None:
    """Normalleştirilmiş ayrıntı → ``boss_detay`` (o anki parmak iziyle; iz değişince önden okuma yeniler)."""
    ek_sema.hazirla(conn)
    try:
        r = conn.execute("SELECT iz FROM boss_iz WHERE task_no=?", (task_no,)).fetchone()
    except sqlite3.OperationalError:
        r = None
    with islem(conn):
        conn.execute("INSERT INTO boss_detay(task_no, uuid, iz, zaman, zaman_sn, veri) VALUES(?,?,?,?,?,?) "
                     "ON CONFLICT(task_no) DO UPDATE SET uuid=excluded.uuid, iz=excluded.iz, zaman=excluded.zaman, "
                     "zaman_sn=excluded.zaman_sn, veri=excluded.veri",
                     (task_no, kayit.get("uuid"), r[0] if r else None, kayit["zaman"], kayit["zaman_sn"],
                      _paketle(kayit)))


def _db_oku(conn: sqlite3.Connection, is_no: str, sonra_sn: float = -1.0) -> dict | None:
    """Depodaki kayıt (yalnız ``sonra_sn``den yeniyse açılır)."""
    if not ek_sema.var_mi(conn, "boss_detay"):
        return None
    r = conn.execute("SELECT d.uuid, d.zaman, d.zaman_sn, d.veri FROM is_emri e JOIN boss_detay d "
                     "ON d.task_no=e.boss_task_no WHERE e.is_no=? AND COALESCE(d.zaman_sn, 0) > ?",
                     (is_no, sonra_sn)).fetchone()
    if r is None:
        return None
    try:
        v = json.loads(zlib.decompress(r[3]).decode("utf-8"))
    except (zlib.error, ValueError, TypeError):
        return None
    return {"zaman_sn": float(r[2] or 0), "zaman": r[1], "uuid": r[0], "sekmeler": v.get("sekmeler") or {},
            "ham": v.get("ham") or {}, "hatalar": v.get("hatalar") or {}}


def _kayit(conn: sqlite3.Connection | None, is_no: str) -> dict | None:
    """Bellekteki ya da kalıcı depodaki kayıt (hangisi yeniyse; depodan okunan belleğe alınır)."""
    with _KILIT:
        c = _ONBELLEK.get(is_no)
    if conn is None:
        return c
    try:
        d = _db_oku(conn, is_no, c["zaman_sn"] if c else -1.0)
    except sqlite3.Error:
        d = None
    if d:
        _bellege(is_no, d)
        return d
    return c


def kapananlari_sil(conn: sqlite3.Connection) -> int:
    """Saklama (``saklama.uygula``): işi açık olmayan ayrıntı kayıtları (kişisel veri) silinir; bellekten de."""
    if not ek_sema.var_mi(conn, "boss_detay"):
        return 0
    with islem(conn):
        n = conn.execute("DELETE FROM boss_detay WHERE task_no NOT IN (SELECT boss_task_no FROM is_emri WHERE "
                         "boss_task_no IS NOT NULL AND durum NOT IN ('cozuldu','kapandi'))").rowcount
    with _KILIT:
        nolar = list(_ONBELLEK)
    if nolar:
        acik = set()
        for i in range(0, len(nolar), 900):
            parca = nolar[i:i + 900]
            acik |= {x for (x,) in conn.execute(
                f"SELECT is_no FROM is_emri WHERE is_no IN ({','.join('?' * len(parca))}) AND "
                "durum NOT IN ('cozuldu','kapandi')", parca)}
        with _KILIT:
            for no in nolar:
                if no not in acik:
                    _ONBELLEK.pop(no, None)
    return n


# ----------------------------------------------------------------------------- önden okuma
def oncelik_yaz(is_nolar) -> dict:
    """TASKS'ın o an ekranda gösterdiği (süzülmüş + sıralanmış) ilk işler → önden okuma bunları önce okur
    (``ONCELIK_SN`` boyunca; yalnız iş noları bellekte)."""
    temiz = []
    for x in (is_nolar if isinstance(is_nolar, list) else [])[:EN_COK_ONCELIK]:
        no = str(x or "").strip()
        if re.fullmatch(r"[\w.-]{1,40}", no) and no not in temiz:
            temiz.append(no)
    with _KILIT:
        _ONCELIK.update(zaman=time.time(), is_nolar=temiz)
    return {"ok": True, "sayi": len(temiz)}


def _oncelik() -> dict[str, int]:
    with _KILIT:
        if time.time() - _ONCELIK["zaman"] > ONCELIK_SN:
            return {}
        return {no: i for i, no in enumerate(_ONCELIK["is_nolar"])}


def detay_gerekli(conn: sqlite3.Connection, en_cok: int = EN_COK_ONDEN) -> list[dict]:
    """Ayrıntısı önden okunacak açık BOSS işleri [{task_no, uuid}]: kaydı olmayan (yeni) ya da kayıttaki parmak izi
    şimdikinden farklı (değişmiş) işler. Sıra (kullanıcının önce açacağı): TASKS'ın ekranda gösterdiği ilk işler →
    bugün atanan ya da bugüne randevulu → randevulu / atanmış → en yeni açılan. Az önce okunamayan iş 10 dk verilmez."""
    _sema(conn)
    var = ek_sema.var_mi(conn, "boss_detay")      # tablo ilk kayıtta (yedekli) kurulur; yoksa her açık iş gerekir
    simdi = time.time()
    for no in [n for n, t in _ONDEN_HATA.items() if simdi - t > ONDEN_HATA_SN]:
        del _ONDEN_HATA[no]
    bugun = zaman.metin()[:10]
    try:
        satirlar = conn.execute(
            "SELECT e.boss_task_no, k.uuid, e.is_no, "
            "CASE WHEN substr(COALESCE(e.randevu_bas,''),1,10)=? OR substr(COALESCE(e.atama_zamani,''),1,10)=? "
            "THEN 0 WHEN e.durum IN ('randevulu','atandi','yolda','sahada') OR e.randevu_bas IS NOT NULL THEN 1 "
            "ELSE 2 END AS oncelik "
            "FROM is_emri e JOIN boss_gorev_kimlik k ON k.task_no=e.boss_task_no "
            + ("LEFT JOIN boss_iz z ON z.task_no=e.boss_task_no LEFT JOIN boss_detay d ON d.task_no=e.boss_task_no "
               "WHERE e.kaynak='boss' AND e.durum NOT IN ('cozuldu','kapandi') "
               "AND (d.task_no IS NULL OR COALESCE(d.iz,'') <> COALESCE(z.iz,'')) " if var else
               "WHERE e.kaynak='boss' AND e.durum NOT IN ('cozuldu','kapandi') ")
            + "ORDER BY oncelik, e.acilis DESC", (bugun, bugun)).fetchall()
    except sqlite3.OperationalError:          # boss_iz henüz yok (ilk eşitlemeden önce)
        return []
    ekranda = _oncelik()
    if ekranda:                                # ekrandaki işler en öne (ekrandaki sırasıyla); sort kararlı
        satirlar = sorted(satirlar, key=lambda r: ekranda.get(r[2], len(ekranda)))
    out, gorulen = [], set()
    for no, u, _is_no, _o in satirlar:
        if no in _ONDEN_HATA or no in gorulen or not UUID_RE.match(str(u or "")):
            continue
        gorulen.add(no)
        out.append({"task_no": no, "uuid": u})
        if len(out) >= en_cok:
            break
    return out


def _hiz_isle(okunan: int) -> float | None:
    """Önden okumanın ölçülen hızı (iş/sn, son HIZ_PENCERE_SN); yeterli ölçüm yoksa None."""
    simdi = time.time()
    with _KILIT:
        if okunan:
            _ONDEN_OKUNAN.append((simdi, okunan))
        while _ONDEN_OKUNAN and simdi - _ONDEN_OKUNAN[0][0] > HIZ_PENCERE_SN:
            _ONDEN_OKUNAN.pop(0)
        if len(_ONDEN_OKUNAN) < 5:
            return None
        sure = simdi - _ONDEN_OKUNAN[0][0]
        toplam = sum(n for _, n in _ONDEN_OKUNAN[1:])
    return toplam / sure if sure >= 30 and toplam else None


def detay_durumu(conn: sqlite3.Connection) -> dict:
    """``/api/boss/durum`` için: {detay_tamam, detay_toplam, detay_kalan_dk} (kişisel veri yok)."""
    try:
        if ek_sema.var_mi(conn, "boss_detay"):
            toplam, tamam = conn.execute(
                "SELECT COUNT(*), SUM(CASE WHEN d.task_no IS NOT NULL AND COALESCE(d.iz,'')=COALESCE(z.iz,'') "
                "THEN 1 ELSE 0 END) FROM is_emri e LEFT JOIN boss_iz z ON z.task_no=e.boss_task_no "
                "LEFT JOIN boss_detay d ON d.task_no=e.boss_task_no WHERE e.kaynak='boss' "
                "AND e.boss_task_no IS NOT NULL AND e.durum NOT IN ('cozuldu','kapandi')").fetchone()
        else:
            toplam = conn.execute("SELECT COUNT(*) FROM is_emri WHERE kaynak='boss' AND boss_task_no IS NOT NULL "
                                  "AND durum NOT IN ('cozuldu','kapandi')").fetchone()[0]
            tamam = 0
    except sqlite3.OperationalError:
        toplam, tamam = 0, 0
    toplam, tamam = int(toplam or 0), int(tamam or 0)
    hiz = _hiz_isle(0)
    kalan_sn = max(0, toplam - tamam) / hiz if hiz else max(0, toplam - tamam) * IS_BASINA_SN
    return {"detay_toplam": toplam, "detay_tamam": tamam, "detay_kalan_dk": round(kalan_sn / 60),
            "detay_hiz_dk": round(hiz * 60, 1) if hiz else None}


def onden_yaz(conn_fabrikasi, govde: dict) -> dict:
    """Eklentinin ``POST /api/boss/detay-onden`` gövdesi: {sonuclar: [{task_no, uuid, sekmeler | hata}]} →
    ``boss_detay`` (yalnız açık işler) + iletişim sekmesinden telefon (``boss.iletisim_kaydet``).
    Dönüş: sayılar + ilerleme + sıradaki okunacak işler (``detay_onden``)."""
    if not isinstance(govde, dict) or not isinstance(govde.get("sonuclar"), list):
        raise Gecersiz("sonuclar listesi gerekli.", kod="alan_eksik")
    from . import boss
    conn = conn_fabrikasi()
    try:
        _sema(conn)
        boss.iz_sema(conn)
        okunan, hata = 0, 0
        acik_tel = boss._tel_acik(conn)
        for x in govde["sonuclar"][:100]:
            if not isinstance(x, dict):
                continue
            no = str(x.get("task_no") or "").strip()
            if not no:
                continue
            if x.get("hata") or not isinstance(x.get("sekmeler"), dict):
                hata += 1
                _ONDEN_HATA[no] = time.time()
                continue
            isler = [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE boss_task_no=? AND durum NOT IN "
                                                "('cozuldu','kapandi')", (no,))]
            if not isler:
                continue                              # kapanmış/bilinmeyen iş: kişisel veri saklanmaz
            sekmeler, ham, hatalar = normallestir(x["sekmeler"])
            if not ham:                               # bütün sekmeler hatalı (oturum düşmüş olabilir)
                hata += 1
                _ONDEN_HATA[no] = time.time()
                continue
            u = str(x.get("uuid") or "")
            kayit = {"zaman_sn": time.time(), "zaman": zaman.metin(), "uuid": u.lower() if UUID_RE.match(u) else None,
                     "sekmeler": sekmeler, "ham": ham, "hatalar": hatalar}
            kaydet(conn, no, kayit)
            if "iletisim" in ham:
                try:
                    with islem(conn):
                        boss.iletisim_kaydet(conn, acik_tel, no, ham["iletisim"], zaman.metin())
                except sqlite3.Error:
                    pass
            with _KILIT:
                for is_no in isler:
                    _ONBELLEK.pop(is_no, None)    # sonraki okuma depodan (yeni) gelir
            okunan += 1
        _hiz_isle(okunan)
        return {"ok": True, "okunan": okunan, "hata": hata, **detay_durumu(conn), "detay_onden": detay_gerekli(conn)}
    finally:
        conn.close()


def oku(is_no: str, musteri: bool, conn: sqlite3.Connection | None = None) -> dict:
    """``GET /api/isler/{is_no}/boss-detay`` yanıtı: kayıt varsa HEMEN (zamanı ve yaşıyla; ``taze`` = 10 dk'dan
    yeni), yoksa bekleyen istek ya da 'yok'."""
    simdi = time.time()
    c = _kayit(conn, is_no)
    with _KILIT:
        _temizle(simdi)
        bekleyen = is_no in _ISTEKLER
        istek = dict(_ISTEKLER[is_no]) if bekleyen else None
        h = _HATALAR.get(is_no)
    if c:
        sekmeler = dict(c["sekmeler"])
        ham = dict(c["ham"])
        if not musteri:
            sekmeler["iletisim"] = None
            ham.pop("iletisim", None)
            sekmeler = _tel_gizle(sekmeler)
            ham = _tel_gizle(ham)
        yas = max(0, int(simdi - c["zaman_sn"]))
        return {"durum": "hazir", "is_no": is_no, "uuid": c["uuid"], "zaman": c["zaman"], "yas_sn": yas,
                "taze": yas < DETAY_TAZE_SN, "gecerlilik_sn": max(0, DETAY_TAZE_SN - yas), "yenileniyor": bekleyen,
                "telefon_gizli": not musteri, "sekmeler": sekmeler, "ham": ham, "hatalar": c["hatalar"]}
    if bekleyen:
        return {"durum": "bekliyor", "is_no": is_no, "bekleme_sn": int(simdi - istek["olusma"]),
                "eklenti_aldi": istek["verildi"] is not None, "zaman_asimi_sn": ISTEK_ZAMAN_ASIMI_SN}
    return {"durum": "yok", "is_no": is_no, "hata": h["hata"] if h else None}
