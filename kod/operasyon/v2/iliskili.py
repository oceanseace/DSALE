"""İlişkili akış: aynı müşteri numarasında başka AÇIK iş varsa o işlerin kısa adları (``IsSatir.iliskili_akis``; kanal
şikâyeti hariç — o Uyarı sütununda ⚠) ve numaraları (``iliskili_isler``). TASKS'ta "İlişkili akış" sütunu (süzülebilir).
Amaç: TV+ kurulumu olup fiber kurulumu da olan müşteri tek ekiple çözülür; yalnız TV+ olan ayrı planlanır.

Task adı → kategori:
- ``sikayet``: Kanal Şikâyeti.
- ``yeni``: kurulum / geçiş / dönüşüm / nakil tipleri (ör. "Fiber Kurulum", "TV+ Kurulum(Nakil)").
- ``mevcut``: geri kalan her şey (arıza, bağlantı problemi, TV+ arıza, modem değişikliği, cihaz iade …).
Metin: Fiber Kurulum satırında "TV+ Kurulum"; TV+ Kurulum satırında "Fiber Kurulum"; kanal şikâyeti satırında
"Yeni Fiber Kurulum + TV+ Kurulum" (Yeni/Mevcut öneki yalnız orada). Müşteri başına açık işler yanıt başına TEK
sorguyla okunur (``uyari.Uyarilar``).
"""
from __future__ import annotations

import re

from operasyon import is_emri as ie

_DEGISKE = {"DONUSUM": "Dönüşüm", "NAKIL": "Nakil", "GECIS": "Geçiş"}


def kategori(task_adi) -> str:
    s = ie.sade(task_adi or "")
    if "KANAL SIKAYET" in s:
        return "sikayet"
    if "KURULUM" in s or any(d in s for d in _DEGISKE):
        return "yeni"
    return "mevcut"


def kisa_ad(task_adi) -> str:
    """Task adı → tablodaki kısa ad: boşluklar sade, ek parantez ayrık ("Fiber Kurulum(Dönüşüm)" → "Fiber Kurulum
    (Dönüşüm)")."""
    t = re.sub(r"\s*\(\s*", " (", str(task_adi or ""))
    t = re.sub(r"\s*\)", ")", t)
    return re.sub(r"\s+", " ", t).strip()


def metin(kendi_task: str, diger_tasklar: list[str]) -> str | None:
    """Satırın kendi task adı + aynı müşterinin diğer açık işlerinin task adları → İlişkili akış (yoksa None).
    Diğer işlerin kısa adları " + " ile, kanal şikâyeti HARİÇ (o Uyarı sütununda ⚠). Sıra tutarlı: önce kurulum
    (yeni) sonra mevcut, her grupta alfabetik. Kanal şikâyeti satırında gruplar "Yeni …" / "Mevcut …" önekli
    (filtrede ayrılsın): "Yeni Fiber Kurulum + TV+ Kurulum + Mevcut Bağlantı Problemi"."""
    yeni: list[str] = []
    mevcut: list[str] = []
    for t in diger_tasklar or []:
        k = kategori(t)
        if k == "sikayet":
            continue
        ad = kisa_ad(t)
        hedef = yeni if k == "yeni" else mevcut
        if ad and ad not in hedef:
            hedef.append(ad)
    yeni.sort(key=ie.sade)
    mevcut.sort(key=ie.sade)
    if not yeni and not mevcut:
        return None
    if kategori(kendi_task) == "sikayet":
        parca = ([f"Yeni {' + '.join(yeni)}"] if yeni else []) + ([f"Mevcut {' + '.join(mevcut)}"] if mevcut else [])
        return " + ".join(parca)
    return " + ".join(yeni + mevcut)



# ----------------------------------------------------------------------------- ilişki anahtarı (toptan müşteri)
# Perakende müşteride iki iş aynı müşteri no'daysa ilişkilidir. TOPTAN müşteride (``saha.ticket_boss_not.toptan_mi``:
# tek müşteri no yüzlerce aboneyi taşır, ör. 23722338 Doping Arıza Bildirimi) müşteri no İLİŞKİ KURMAZ: işler yalnız
# ABONE düzeyindeki anahtarla ilişkilenir — BOSS ``locationUnitId`` (Lokasyon Birimi), yoksa Lokasyon ID + adres
# (kapı/daire adresin içinde). İkisi de yoksa ilişki YOK. Kural TEK yerde (``Iliski``): İlişkili akış sütunu, ⚠ kanal
# şikâyeti, ↻ tekrar gelen iş, atama/askıda ilişkili işlerin dahil edilmesi, "hepsini aynı ekibe ata" ve ticket iş
# seçicisinin varsayılanı.
_ACIK = "durum NOT IN ('cozuldu','kapandi')"


def lok_adres(lokasyon, adres) -> str | None:
    lok, adr = ie.anahtar(lokasyon or ""), ie.anahtar(adres or "")
    return f"l:{lok}|{adr}" if lok and adr else None


def is_anahtarlari(musteri_no, toptan: bool, unit=None, lokasyon=None, adres=None) -> list[str]:
    """Bir işin ilişki anahtarları (biri tutan iki iş ilişkilidir). Perakende: ``m:<müşteri no>``; toptan:
    ``u:<locationUnitId>`` ve/veya ``l:<Lokasyon ID>|<adres>``; toptanda ikisi de yoksa [] (ilişki yok)."""
    m = str(musteri_no or "").strip()
    if not m:
        return []
    if not toptan:
        return [f"m:{m}"]
    out = []
    u = str(unit or "").strip()
    if u:
        out.append(f"u:{u}")
    la = lok_adres(lokasyon, adres)
    if la:
        out.append(la)
    return out


class Iliski:
    """Bütün AÇIK işlerin ilişki anahtarları — TEK sorgu (is_emri + boss_ham). ``anahtar[is_no]`` → [anahtar],
    ``grup[anahtar]`` → [is_no], ``toptan`` → toptan müşteri no'ları, ``bilgi[is_no]`` → (task no, task adı)."""

    def __init__(self, conn):
        try:
            from saha import ticket_boss_not as tbn
        except ImportError:
            tbn = None
        try:
            satirlar = conn.execute(
                "SELECT e.is_no, e.boss_task_no, TRIM(e.musteri_no), e.task_adi, e.satis_kanali, e.lokasyon, e.adres, "
                "json_extract(h.veri,'$.segment'), json_extract(h.veri,'$.saleChannel'), "
                "json_extract(h.veri,'$.productInfo'), json_extract(h.veri,'$.locationUnitId') "
                "FROM is_emri e LEFT JOIN boss_ham h ON h.task_no=e.boss_task_no "
                "WHERE e.durum NOT IN ('cozuldu','kapandi') "
                "AND e.musteri_no IS NOT NULL AND TRIM(e.musteri_no) <> '' ORDER BY e.acilis, e.is_no").fetchall()
        except Exception:                                        # boss_ham yok (taze kurulum): ham alansız
            satirlar = [(*r, None, None, None, None) for r in conn.execute(
                "SELECT is_no, boss_task_no, TRIM(musteri_no), task_adi, satis_kanali, lokasyon, adres "
                f"FROM is_emri WHERE {_ACIK} AND musteri_no IS NOT NULL AND TRIM(musteri_no) <> '' "
                "ORDER BY acilis, is_no").fetchall()]
        musteri: dict[str, list] = {}
        for r in satirlar:
            musteri.setdefault(r[2], []).append(r)
        self.toptan: set[str] = set()
        if tbn is not None:
            for m, rs in musteri.items():
                isler = [{"task_no": r[1] or r[0], "satis_kanali": r[4]} for r in rs]
                ham = {str(r[1] or r[0]): {"segment": r[7], "saleChannel": r[8], "productInfo": r[9]} for r in rs}
                if tbn.toptan_mi(isler, ham):
                    self.toptan.add(m)
        self.anahtar: dict[str, list[str]] = {}
        self.grup: dict[str, list[str]] = {}
        self.bilgi: dict[str, tuple[str, str]] = {}
        self.musteri_no: dict[str, str] = {}
        for r in satirlar:
            no = r[0]
            self.bilgi[no] = (r[1] or no, r[3] or "")
            self.musteri_no[no] = r[2]
            a = is_anahtarlari(r[2], r[2] in self.toptan, r[10], r[5], r[6])
            self.anahtar[no] = a
            for x in a:
                self.grup.setdefault(x, []).append(no)

    def digerleri(self, is_no: str) -> list[str]:
        """Aynı müşterinin (toptanda aynı abonenin) öbür AÇIK işleri, sıra korunur."""
        out: dict[str, None] = {}
        for a in self.anahtar.get(is_no, ()):
            for no in self.grup.get(a, ()):
                if no != is_no:
                    out[no] = None
        return list(out)


# ----------------------------------------------------------------------------- ilişkili işler birlikte (09.10)
# Atama ve askıda (çekmece, TASKS toplu, MAP kement/dikdörtgen) seçili işlerin aynı müşterideki öbür AÇIK işleri de
# kendiliğinden dahil edilir ("İlişkili işleri de dahil et (N)", varsayılan ``ayar.iliskili_dahil`` = 'acik').
# İlişki İlişkili akış sütunuyla AYNI (``Iliski``): perakendede aynı müşteri no, toptanda aynı abone (Lokasyon Birimi /
# Lokasyon ID + adres); toptan işin abone anahtarı yoksa genişletilmez.
AYAR_DAHIL = "iliskili_dahil"
_HIZALAMA_DISI = ("askida", "altyapi", "yolda", "sahada")     # bu işler "hepsini aynı ekibe ata"ya girmez
EN_COK = 500
_IS_SORGU = ("SELECT e.is_no, e.boss_task_no AS task_no, e.task_adi, e.durum, e.surum, e.atanan_id, e.satis_kanali, "
             "e.boss_durum, e.boss_ekip, e.randevu_bas, e.randevu_bit, e.randevu_teyitli, e.acilis, "
             "k.ad AS atanan_ad FROM is_emri e LEFT JOIN kullanici k ON k.id=e.atanan_id ")


def dahil_varsayilan(conn) -> bool:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (AYAR_DAHIL,)).fetchone()
    return ((r[0] if r and r[0] else None) or "acik") == "acik"


def _isler(conn, is_nolar: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(is_nolar), 500):
        dilim = is_nolar[i:i + 500]
        out += [dict(r) for r in conn.execute(
            _IS_SORGU + f"WHERE e.is_no IN ({','.join('?' * len(dilim))}) ORDER BY e.acilis, e.is_no", dilim)]
    return out


def _ozet(x: dict, kaynak: str | None = None) -> dict:
    o = {"is_no": x["is_no"], "task_no": x["task_no"] or x["is_no"], "task_adi": kisa_ad(x["task_adi"]),
         "kategori": kategori(x["task_adi"]), "durum": x["durum"], "boss_durum": x["boss_durum"], "surum": x["surum"],
         "atanan_id": x["atanan_id"], "atanan": x["atanan_ad"] or x["boss_ekip"]}
    if kaynak:
        o["kaynak"] = kaynak
    return o


def iliskili_isler(conn, is_nolar: list[str]) -> dict:
    """Seçili işlerin aynı müşterideki (toptanda aynı abonedeki: ``Iliski``) öbür AÇIK işleri (seçimde olmayanlar).
    Dönüş: {isler: [{is_no, task_no, task_adi, kategori, durum, boss_durum, surum, atanan_id, atanan, kaynak (seçili
    işin task no'su)}], toptan_atlanan (müşteri no ile genişletilmeyen toptan iş sayısı), varsayilan}.
    Kişisel veri (müşteri no/adı) dönmez."""
    nolar = list(dict.fromkeys(str(n) for n in (is_nolar or [])))[:EN_COK]
    secili = set(nolar)
    il = Iliski(conn)
    kaynaklar: dict[str, str] = {}
    toptan = 0
    for no in nolar:
        if no not in il.bilgi:
            continue
        if il.musteri_no.get(no) in il.toptan:
            toptan += 1                                   # toptan müşteri: müşteri no ile genişletilmedi (yalnız abone)
        for d in il.digerleri(no):
            if d not in secili:
                kaynaklar.setdefault(d, il.bilgi[no][0])
    out = [_ozet(x, kaynaklar[x["is_no"]]) for x in _isler(conn, list(kaynaklar)[:EN_COK])]
    return {"isler": out[:EN_COK], "toptan_atlanan": toptan, "varsayilan": dahil_varsayilan(conn)}


def _capa(isler: list[dict]) -> dict | None:
    """Grubun hedef ekibi: atanmış işlerden kurulum ('yeni') önce, sonra en erken randevu, sonra iş no."""
    atanmis = [x for x in isler if x["atanan_id"]]
    if not atanmis:
        return None
    return sorted(atanmis, key=lambda x: (kategori(x["task_adi"]) != "yeni", x["randevu_bas"] or "9999",
                                          x["is_no"]))[0]


def kumeler(il: Iliski) -> list[list[str]]:
    """Birbiriyle ilişkili açık işlerin grupları (anahtarlardan biri tutan işler aynı grupta; tek işlik grup yok)."""
    out: list[list[str]] = []
    gorulen: set[str] = set()
    for no in il.anahtar:
        if no in gorulen or not il.anahtar[no]:
            continue
        kume, yigin = [], [no]
        gorulen.add(no)
        while yigin:
            x = yigin.pop()
            kume.append(x)
            for d in il.digerleri(x):
                if d not in gorulen:
                    gorulen.add(d)
                    yigin.append(d)
        if len(kume) > 1:
            out.append(kume)
    return out


def uyumsuzlar(conn) -> dict:
    """Pano/TASKS: aynı müşterinin (toptanda aynı abonenin: ``Iliski``) açık işlerinden biri bir ekibe atanmışken öbürü
    başka ekipte ya da atanmamış. Dönüş: {gruplar: [{hedef: {teknik_id, ad, randevu_bas, randevu_bit}, capa: {...},
    isler: [...]}], is_sayisi}. Askıdaki / altyapı bekleyen / yolda / sahadaki işler hizalanmaz."""
    gruplar = []
    for kume in kumeler(Iliski(conn)):
        isler = _isler(conn, kume)
        capa = _capa(isler)
        if capa is None:
            continue
        uyumsuz = [x for x in isler if x["is_no"] != capa["is_no"] and x["atanan_id"] != capa["atanan_id"]
                   and x["durum"] not in _HIZALAMA_DISI]
        if not uyumsuz:
            continue
        gruplar.append({"hedef": {"teknik_id": capa["atanan_id"], "ad": capa["atanan_ad"],
                                  "randevu_bas": capa["randevu_bas"], "randevu_bit": capa["randevu_bit"]},
                        "capa": _ozet(capa), "isler": [_ozet(x) for x in uyumsuz]})
    gruplar.sort(key=lambda g: (g["hedef"]["ad"] or "", g["capa"]["task_no"]))
    return {"gruplar": gruplar, "is_sayisi": sum(len(g["isler"]) for g in gruplar)}


def hizala(conn, k: dict | None, is_nolar: list[str] | None = None) -> dict:
    """"Hepsini aynı ekibe ata": her gruptaki uyumsuz işler çapa işin ekibine ve dilimine atanır (atama yazma yolu:
    ``akis.ata`` → BOSS). ``is_nolar`` verilirse yalnız onlar. Dönüş: ``_toplu`` özeti (atanan, atlanan)."""
    from . import akis, zaman
    secim = set(str(n) for n in is_nolar) if is_nolar else None
    simdi = zaman.metin()
    liste = []
    for g in uyumsuzlar(conn)["gruplar"]:
        h = g["hedef"]
        # çapanın dilimi geçmişse dilim önerilir (akis.ata)
        rv = ({"bas": h["randevu_bas"], "bit": h["randevu_bit"], "teyitli": False}
              if h["randevu_bas"] and h["randevu_bit"] and h["randevu_bas"] >= simdi else None)
        for x in g["isler"]:
            if secim is None or x["is_no"] in secim:
                liste.append((x["is_no"], {"teknik_id": h["teknik_id"], "randevu": rv}))

    def tek(oge, toplu_id):
        is_no, a = oge
        akis.ata(conn, is_no, a["teknik_id"], k, randevu=a["randevu"], toplu_id=toplu_id, kaynak="toplu",
                 notu="İlişkili işle aynı ekibe")

    return akis._toplu(conn, liste[:EN_COK], tek)
