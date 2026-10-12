"""Saha satış uçları (Saha): günlük görev listesi, ziyaret kaydı, bina kartı, harita ve yol ağı,
günlük/kapsama özeti ve günlük Excel raporu.

URL'ler: /api/gorev/* · /api/ziyaret* · /api/bina* · /api/harita · /api/yollar · /api/ozet/* · /api/dosya/rapor.xlsx
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from . import ayarlar, db, rapor, rota, veri_kalitesi, yetki
from .api_ortak import _acik_gorev, _baslik, _gorev_ozet, _kullanici_kart
from .yetki import baglanti, bina_gorebilir, bolge_kapsami, hata, izin, izinli, ziyaret_yazabilir

yonlendirici = APIRouter()


# ============================================================================= bina kartı
def _adres(b: dict) -> str:
    sokak = (b.get("sokak") or b.get("cadde") or "").strip()
    kapi = (b.get("kapi_no") or "").strip()
    satir = f"{sokak} No:{kapi}" if (sokak and kapi) else sokak
    kuyruk = " / ".join(x for x in [(b.get("mahalle") or "").strip(), (b.get("ilce") or "").strip()] if x)
    return " · ".join(x for x in [satir, kuyruk] if x)


def _penetrasyon(b: dict) -> float | None:
    """Doluluk oranı. Ölçülemiyorsa None — kartta "%0" değil "veri yok" yazar.

    ``res_hp=0`` olan 165 binada daire sayısı dolu ve 122'sinde kayıtlı abone
    var; eski hesap bunlara "%0 doluluk, 0 boş kapı" diyerek kendi içinde
    çelişen bir kart gösteriyordu. 303 binada da aktif_res > res_hp olduğu için
    oran %100'ü aşıyordu.
    """
    taban = max(int(b.get("res_hp") or 0), int(b.get("daire") or 0))
    if taban <= 0:
        return None
    return round(min(int(b.get("aktif_res") or 0) / taban, 1.0), 4)


def _bina_kart(b: dict | sqlite3.Row, bugun: dt.date | None = None) -> dict:
    b = dict(b)
    gun = bugun or ayarlar.bugun()
    durum = b.get("durum") or "bekliyor"
    baslik = _baslik(b)
    kart = {
        "bina_serial": b["bina_serial"],
        "baslik": baslik,
        # Uygulama bazı yerlerde ham `ad` alanını okuyor (sözleşmedeki `bina.ad`).
        # İkisi de aynı metni verir; site adı yoksa sokak/kapı numarasına düşer.
        "ad": baslik,
        "adres": _adres(b),
        "site_adi": b.get("site_adi") or "",
        "site_grup": b.get("site_grup") or "",
        "mahalle": b.get("mahalle") or "",
        "ilce": b.get("ilce") or "",
        "sokak": b.get("sokak") or "",
        "kapi_no": b.get("kapi_no") or "",
        "lat": b.get("lat"),
        "lon": b.get("lon"),
        "kat": b.get("kat") or 0,
        "daire": b.get("daire") or 0,
        "res_hp": b.get("res_hp") or 0,
        "aktif_res": b.get("aktif_res") or 0,
        "firsat": b.get("firsat") or 0,
        "penetrasyon": _penetrasyon(b),
        "sales_ready": b.get("sales_ready"),
        "yeni_site": rota.yeni_site_carpani(b.get("sales_ready"), gun) > 1.0,
        "bolge": b.get("bolge"),
        "durum": durum,
        "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
        "son_ziyaret": b.get("son_ziyaret"),
        "son_sonuc": b.get("son_sonuc"),
        "tekrar_tarih": b.get("tekrar_tarih"),
        "toplam_satis": b.get("toplam_satis") or 0,
        "ziyaret_sayisi": b.get("ziyaret_sayisi") or 0,
        # Yönetici "Ayrıntılar" penceresi ve BOSS/Fox iş emri eşleştirmesi için
        "kimlik": {
            "bina_serial": b["bina_serial"],
            "location_id": b.get("location_id") or "",
            "tellcordia_id": b.get("tellcordia_id") or "",
            "uavt_bina_kodu": b.get("uavt_bina_kodu") or "",
        },
        "blok_adi": b.get("blok_adi") or "",
        "bina_turu": b.get("bina_turu") or "",
        "toplam_hp": b.get("toplam_hp") or 0,
        "altyapi": b.get("altyapi") or "",
        "teknoloji": b.get("teknoloji") or "",
        "obek": b.get("obek") or "",
        "crm_site_adi": b.get("crm_site_adi") or "",
        # Veri kalitesi bulguları (dsale/kalite.py): [{kural, mesaj, seviye, duzeltme?}]
        "kalite": veri_kalitesi.bayraklar(b.get("kalite")),
        # Son tur raporunda yok: listeye girmez, geçmişi durur.
        "pasif": bool(b.get("pasif")),
    }
    for ek in ("sira", "mesafe_m", "oncelik", "gorev_durum"):
        if ek in b and b[ek] is not None:
            kart[ek] = b[ek]
    return kart


# ============================================================================= görev yardımcıları
def _tarih_coz(metin: str | None, varsayilan: dt.date | None = None) -> dt.date:
    if not metin:
        return varsayilan or ayarlar.bugun()
    try:
        return dt.date.fromisoformat(metin[:10])
    except ValueError:
        raise hata(400, "Tarih biçimi geçersiz (YYYY-AA-GG bekleniyor).", "tarih_gecersiz")


def _acik_planli(conn: sqlite3.Connection, tarih: dt.date) -> set[str]:
    """O gün açık görevlerde bekleyen binalar — başka listeye girmemeli."""
    satirlar = conn.execute(
        "SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        "WHERE g.tarih=? AND g.durum='acik' AND gb.durum='bekliyor'",
        (tarih.isoformat(),),
    ).fetchall()
    return {s["bina_serial"] for s in satirlar}


def _planli_temizle(conn: sqlite3.Connection, tarih: dt.date) -> None:
    """Dünden kalan 'planli' işaretlerini kaldırır (durum yalnız 'bekliyor'dan alındığı için kayıpsız)."""
    conn.execute(
        "UPDATE bina_durum SET durum='bekliyor' WHERE durum='planli' AND bina_serial NOT IN ("
        "  SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id"
        "  WHERE g.tarih=? AND g.durum='acik' AND gb.durum='bekliyor')",
        (tarih.isoformat(),),
    )


def _gorev_bul(
    conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date, sadece_acik: bool = True
) -> sqlite3.Row | None:
    """Bir günün görevi. Geçmiş günlere bakarken kapanmış görev de görünmeli."""
    if sadece_acik:
        return _acik_gorev(conn, kullanici_id, tarih)
    return conn.execute(
        "SELECT * FROM gorev WHERE kullanici_id=? AND tarih=? ORDER BY id DESC LIMIT 1",
        (kullanici_id, tarih.isoformat()),
    ).fetchone()


def _gecmis_gorevleri_kapat(conn: sqlite3.Connection) -> None:
    """Dünden kalan açık görevleri kapatır.

    Kapanmadıkları sürece bir kullanıcının aynı anda birden çok açık görevi
    oluyor, aynı bina iki günün listesinde birden bekliyor ve dün indirilen
    raporla bugün indirilen aynı-tarihli rapor farklı çıkıyordu.
    """
    conn.execute(
        "UPDATE gorev SET durum='tamam' WHERE durum='acik' AND tarih < ?",
        (ayarlar.bugun().isoformat(),),
    )


def _gorev_binalari(conn: sqlite3.Connection, gorev_id: int) -> list[dict]:
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI}, gb.sira, gb.mesafe_m, gb.durum AS gorev_durum "
        "FROM gorev_bina gb "
        "JOIN bina b ON b.bina_serial=gb.bina_serial "
        "JOIN bina_durum d ON d.bina_serial=gb.bina_serial "
        "WHERE gb.gorev_id=? ORDER BY gb.sira",
        (gorev_id,),
    ).fetchall()
    return [_bina_kart(s) for s in satirlar]


def _gunun_onceki_binalari(
    conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date, acik_gorev_id: int | None
) -> list[dict]:
    """Aynı GÜN içinde kapanmış görevlerin binaları.

    Satışçı 25 binayı bitirip "yeni liste al" derse sunucu sabahki görevi
    kapatıp yenisini açar. `/api/gorev/bugun` yalnız açık görevi döndürdüğü
    için sabah gezilen 25 bina ekrandan siliniyordu: adam öğleden sonra
    telefonuna bakıp bütün emeğini kaybolmuş görüyordu. Bunlar "Bitenler"in
    altında durmalı — bugünün işi bir görev değil, BİR GÜN.
    """
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI}, gb.sira, gb.mesafe_m, gb.durum AS gorev_durum "
        "FROM gorev_bina gb "
        "JOIN gorev g ON g.id=gb.gorev_id "
        "JOIN bina b ON b.bina_serial=gb.bina_serial "
        "JOIN bina_durum d ON d.bina_serial=gb.bina_serial "
        "WHERE g.kullanici_id=? AND g.tarih=? AND g.id<>COALESCE(?, -1) "
        "  AND gb.durum='tamam' "
        "ORDER BY g.id, gb.sira",
        (kullanici_id, tarih.isoformat(), acik_gorev_id),
    ).fetchall()
    return [_bina_kart(s) for s in satirlar]


def _gorev_yaz(
    conn: sqlite3.Connection,
    kullanici_id: int,
    tarih: dt.date,
    binalar: list[dict],
    kaynak: str,
    olusturan_id: int,
    notu: str | None = None,
    mevcut: sqlite3.Row | None = None,
) -> int:
    """Görevi oluşturur (ya da açık göreve ekler) ve binaları 'planli' işaretler."""
    if mevcut is not None:
        gorev_id = mevcut["id"]
        baslangic = conn.execute(
            "SELECT COALESCE(MAX(sira),0) FROM gorev_bina WHERE gorev_id=?", (gorev_id,)
        ).fetchone()[0]
    else:
        imlec = conn.execute(
            "INSERT INTO gorev (kullanici_id, tarih, durum, olusturan_id, kaynak, notu, olusturma) "
            "VALUES (?,?,'acik',?,?,?,?)",
            (kullanici_id, tarih.isoformat(), olusturan_id, kaynak, notu, ayarlar.zaman_metni()),
        )
        gorev_id = int(imlec.lastrowid)
        baslangic = 0

    for b in binalar:
        conn.execute(
            "INSERT INTO gorev_bina (gorev_id, bina_serial, sira, durum, mesafe_m) "
            "VALUES (?,?,?,'bekliyor',?) ON CONFLICT(gorev_id, bina_serial) DO NOTHING",
            (gorev_id, b["bina_serial"], baslangic + b.get("sira", 0), int(b.get("mesafe_m", 0))),
        )
        conn.execute(
            "UPDATE bina_durum SET durum='planli' WHERE bina_serial=? AND durum='bekliyor'",
            (b["bina_serial"],),
        )
    db.surumu_arttir(conn)
    return gorev_id


# ============================================================================= görev
class RotaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    adet: int = Field(default=ayarlar.VARSAYILAN_ADET, ge=1, le=ayarlar.EN_FAZLA_ADET)
    baslangic: list[float] | None = None


@yonlendirici.get("/api/gorev/bugun")
def gorev_bugun(
    kullanici_id: int | None = None,
    tarih: str | None = None,
    k: dict = Depends(izin("satis.kendi", "satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    hedef_id = k["id"]
    if kullanici_id is not None and int(kullanici_id) != k["id"]:
        if not izinli(k, "satis.izle"):
            raise hata(403, "Yalnızca kendi listenizi görebilirsiniz.", "yasak")
        hedef_id = int(kullanici_id)
    gun = _tarih_coz(tarih)
    gorev = _gorev_bul(conn, hedef_id, gun, sadece_acik=gun >= ayarlar.bugun())
    if not gorev:
        return {"gorev_id": None, "tarih": gun.isoformat(), "kaynak": None, "notu": None,
                "binalar": [], "onceki_binalar": _gunun_onceki_binalari(conn, hedef_id, gun, None),
                "toplam_mesafe_m": 0, "ozet": _gorev_ozet(conn, None),
                "uyari": None, "mesaj": "Bugün için liste yok."}
    binalar = _gorev_binalari(conn, gorev["id"])
    return {
        "gorev_id": gorev["id"],
        "tarih": gorev["tarih"],
        "kaynak": gorev["kaynak"],
        "notu": gorev["notu"],
        "binalar": binalar,
        # Aynı gün daha önce bitirilen listelerin binaları: ekranda "Bitenler"
        # bölümünün altına eklenir, sayaçlara KARIŞMAZ.
        "onceki_binalar": _gunun_onceki_binalari(conn, hedef_id, gun, gorev["id"]),
        "toplam_mesafe_m": sum(b.get("mesafe_m", 0) for b in binalar),
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev["id"]),
    }


@yonlendirici.post("/api/gorev/olustur")
def gorev_olustur(
    girdi: RotaGirdi | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    girdi = girdi or RotaGirdi()
    if "satisci" not in yetki.gorevler(k) or not k["bolge"]:
        raise hata(400, "Rota yalnızca satışçı hesapları için kurulur.", "bolge_yok")

    gun = ayarlar.bugun()
    _gecmis_gorevleri_kapat(conn)
    _planli_temizle(conn, gun)
    mevcut = _acik_gorev(conn, k["id"], gun)
    if mevcut:
        ozet = _gorev_ozet(conn, mevcut["id"])
        if ozet["kalan"] > 0:
            conn.commit()
            binalar = _gorev_binalari(conn, mevcut["id"])
            return {"gorev_id": mevcut["id"], "tarih": mevcut["tarih"], "zaten_var": True,
                    "kaynak": mevcut["kaynak"], "notu": mevcut["notu"], "binalar": binalar,
                    "toplam_mesafe_m": sum(b.get("mesafe_m", 0) for b in binalar),
                    "uyari": rota.tur_uyarisi(binalar),
                    "ozet": ozet, "mesaj": "Bugünkü listeniz zaten hazır."}
        conn.execute("UPDATE gorev SET durum='tamam' WHERE id=?", (mevcut["id"],))
        mevcut = None

    baslangic = None
    if girdi.baslangic and len(girdi.baslangic) == 2:
        baslangic = (float(girdi.baslangic[0]), float(girdi.baslangic[1]))
    haric = _acik_planli(conn, gun)
    binalar = rota.gunluk_rota(conn, int(k["bolge"]), baslangic, girdi.adet, gun, haric=haric)
    if not binalar:
        conn.commit()
        return {"gorev_id": None, "tarih": gun.isoformat(), "kaynak": "algoritma", "notu": None,
                "binalar": [], "toplam_mesafe_m": 0, "ozet": _gorev_ozet(conn, None),
                "uyari": None,
                "mesaj": "Bölgenizde şu an ziyaret edilecek bina kalmadı."}

    gorev_id = _gorev_yaz(conn, k["id"], gun, binalar, "algoritma", k["id"])
    conn.commit()
    return {
        "gorev_id": gorev_id,
        "tarih": gun.isoformat(),
        "kaynak": "algoritma",
        "notu": None,
        "binalar": _gorev_binalari(conn, gorev_id),
        "toplam_mesafe_m": rota.toplam_mesafe_m(binalar),
        # Tur bir günde gezilemeyecek kadar uzunsa satışçı bunu SABAH görmeli.
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev_id),
    }


class AtamaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kullanici_id: int
    tarih: str | None = None
    bina_serial: list[str] | None = None
    mahalle: str | None = None
    ilce: str | None = None
    bbox: list[float] | None = None          # [lat1, lon1, lat2, lon2]
    adet: int = Field(default=ayarlar.VARSAYILAN_ADET, ge=1, le=ayarlar.EN_FAZLA_ADET)
    notu: str | None = Field(default=None, validation_alias=AliasChoices("notu", "not"))


@yonlendirici.post("/api/gorev/ata")
def gorev_ata(
    girdi: AtamaGirdi,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    hedef = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.kullanici_id,)).fetchone()
    if not hedef or not hedef["aktif"]:
        raise hata(404, "Satışçı bulunamadı.", "kullanici_yok")
    if "satisci" not in yetki.gorev_kumesi_oku(conn, dict(hedef)) or not hedef["bolge"]:
        raise hata(400, "Görev yalnızca satışçıya atanır.", "rol_hatali")

    gun = _tarih_coz(girdi.tarih)
    _gecmis_gorevleri_kapat(conn)
    _planli_temizle(conn, gun)
    bolge = int(hedef["bolge"])

    if girdi.bina_serial:
        isaretler = ",".join("?" * len(girdi.bina_serial))
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            f"WHERE b.bina_serial IN ({isaretler})",
            tuple(girdi.bina_serial),
        ).fetchall()
        bulunan = {s["bina_serial"] for s in satirlar}
        eksik = [s for s in girdi.bina_serial if s not in bulunan]
        if eksik:
            raise hata(404, f"{len(eksik)} bina bulunamadı: {', '.join(eksik[:3])}", "bina_yok")
        pasifler = [s["bina_serial"] for s in satirlar if s["pasif"]]
        if pasifler:
            raise hata(400, f"{len(pasifler)} bina son tur raporunda yok (pasif): "
                            f"{', '.join(pasifler[:3])}", "bina_pasif")
        yabanci = [s["bina_serial"] for s in satirlar if s["bolge"] != bolge]
        if yabanci:
            raise hata(400, f"{len(yabanci)} bina {hedef['ad']} kişisinin bölgesinde değil.", "baska_bolge")
        adaylar = [dict(s) for s in satirlar]
    elif girdi.mahalle:
        # İlçe verilirse süzgeç daraltılır: aynı adlı mahalleler farklı
        # ilçelerde olabiliyor ("Kurtuluş" Gürsu'da da var Yenişehir'de de,
        # aralarında 41 km).
        kosullar = ["b.bolge=?", "b.mahalle=?"]
        degerler = [bolge, girdi.mahalle]
        if girdi.ilce:
            kosullar.append("b.ilce=?")
            degerler.append(girdi.ilce)
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            "WHERE " + " AND ".join(kosullar),
            tuple(degerler),
        ).fetchall()
        adaylar = [dict(s) for s in satirlar if rota.uygun_mu(dict(s), gun)]
    elif girdi.bbox and len(girdi.bbox) == 4:
        lat1, lon1, lat2, lon2 = girdi.bbox
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            "WHERE b.bolge=? AND b.lat BETWEEN ? AND ? AND b.lon BETWEEN ? AND ?",
            (bolge, min(lat1, lat2), max(lat1, lat2), min(lon1, lon2), max(lon1, lon2)),
        ).fetchall()
        adaylar = [dict(s) for s in satirlar if rota.uygun_mu(dict(s), gun)]
    else:
        raise hata(400, "Bina listesi, mahalle veya harita alanı seçin.", "secim_yok")

    if not adaylar:
        raise hata(400, "Seçimde atanacak uygun bina yok.", "bina_yok")

    # Başka bir açık listede bekleyen bina İKİNCİ KEZ ATANAMAZ. Eskiden filtre
    # her şeyi elerse "or adaylar" ile tamamen iptal ediliyordu; sonuç: aynı
    # bina aynı gün iki satışçının listesine düşüyor, iki kişi aynı kapıyı
    # çalıyordu. Artık filtre atlanamaz, boş kalırsa açıkça söylenir.
    haric = _acik_planli(conn, gun)
    adaylar = [a for a in adaylar if a["bina_serial"] not in haric]
    if not adaylar:
        raise hata(400, "Seçtiğiniz binaların hepsi bugün başka bir listede. "
                        "Başka bina seçin ya da o listeyi boşaltın.", "bina_yok")
    for a in adaylar:
        a["oncelik"] = round(rota.oncelik_puani(a, gun), 3)
        a["sinif"] = rota.oncelik_sinifi(a)
    adaylar.sort(key=rota.sirala_anahtari)
    binalar = rota.tur_kur(adaylar, None, min(girdi.adet, len(adaylar)))

    mevcut = _acik_gorev(conn, hedef["id"], gun)
    gorev_id = _gorev_yaz(conn, hedef["id"], gun, binalar, "yonetici", k["id"], girdi.notu, mevcut)
    conn.commit()
    return {
        "gorev_id": gorev_id,
        "tarih": gun.isoformat(),
        "kullanici": _kullanici_kart(hedef),
        "eklenen": len(binalar),
        "binalar": _gorev_binalari(conn, gorev_id),
        "toplam_mesafe_m": rota.toplam_mesafe_m(binalar),
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev_id),
    }


# ============================================================================= ziyaret
class ZiyaretGirdi(BaseModel):
    """Sahadan gelen tek bir ziyaret.

    Bir ziyaretin ÖZÜ ``bina_serial`` + ``sonuc``tur; yalnız bu ikisi yanlışsa
    kayıt reddedilir. Yanındaki alanlar (cihaz künyesi, not, daire) teşhis ve
    ayrıntı içindir: uzunsa kırpılır, anlamsızsa yok sayılır. Sebep basit —
    satışçının kaydı, tarayıcı künyesi iki karakter uzun diye kaybolamaz.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    offline_id: str = Field(min_length=4, max_length=80)
    bina_serial: str
    sonuc: str
    satis_adedi: int = Field(default=0, ge=0, le=500)
    konusulan_daire: int = 0
    notu: str | None = Field(default=None, validation_alias=AliasChoices("notu", "not"))
    lat: float | None = None
    lon: float | None = None
    zaman: str | None = None
    cihaz: str | None = None
    tekrar_tarih: str | None = None
    # Yanlış işlenen bir kaydı düzeltmek için: bu offline_id'li ziyaret iptal
    # edilir, sayaçlardan düşer, yerine bu kayıt geçer.
    duzeltilen_offline_id: str | None = None

    @field_validator("cihaz")
    @classmethod
    def _cihazi_kirp(cls, deger):
        return (deger or "").strip()[:80] or None

    @field_validator("notu")
    @classmethod
    def _notu_kirp(cls, deger):
        return (deger or "").strip()[:1000] or None

    @field_validator("konusulan_daire", mode="before")
    @classmethod
    def _daireyi_coz(cls, deger):
        """Uygulama buraya serbest metin de yazabiliyor ("3", "3. kat", "")."""
        if deger is None or deger == "":
            return 0
        if isinstance(deger, bool):
            return 0
        if isinstance(deger, (int, float)):
            return max(0, min(2000, int(deger)))
        rakamlar = "".join(k for k in str(deger) if k.isdigit())[:4]
        return max(0, min(2000, int(rakamlar))) if rakamlar else 0


def _zamani_coz(ham, an):
    """Sahadan gelen zaman damgasını Türkiye saatine çevirir ve pencereye sıkıştırır.

    İki gerçek hatayı birden kapatır:
      1. Uygulama ``new Date().toISOString()`` ile UTC gonderiyordu; sunucu "Z"yi
         kırpıp Türkiye saati sanıyordu. Her kayıt 3 saat geriye yazılıyor, daha
         SONRA yapılan ziyaret "daha eski" görünüp binanın durumunu
         güncellemiyordu. Gece 00:00-03:00 arası her ziyaret DÜNE düşüyordu.
      2. İleri tarihli tek bir kayıt (bozuk saatli telefon) binayı kalıcı olarak
         iş havuzundan düşürüyordu: 2031 damgalı "girilemedi" 30 günlük soğumayı
         sonsuza uzatıyordu.
    """
    metin = (ham or "").strip()
    if not metin:
        return ayarlar.zaman_metni(an)
    try:
        cozulen = dt.datetime.fromisoformat(metin.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return ayarlar.zaman_metni(an)
    if cozulen.tzinfo is not None:
        cozulen = cozulen.astimezone(ayarlar.TR).replace(tzinfo=None)
    # Saat dilimi yoksa yerel saat kabul edilir (eski istemciler).
    cozulen = cozulen.replace(microsecond=0)
    if cozulen > an + dt.timedelta(minutes=ayarlar.ZAMAN_ILERI_DK):
        return ayarlar.zaman_metni(an)
    if cozulen < an - dt.timedelta(days=ayarlar.ZAMAN_GERI_GUN):
        return ayarlar.zaman_metni(an)
    return ayarlar.zaman_metni(cozulen)


def _bina_durumunu_kur(conn, bina_serial):
    """``bina_durum`` satırını GEÇERLİ (iptal edilmemiş) ziyaretlerden yeniden kurar.

    İptal sonrası sayaçların ve "son durum"un elle düzeltilmesi hataya açık;
    tek doğru kaynak ziyaret tablosudur. Çevrimdışı kuyruk sırasız gelse de
    sonuç aynı çıkar.
    """
    satirlar = conn.execute(
        "SELECT zaman, sonuc, satis_adedi, kullanici_id FROM ziyaret "
        "WHERE bina_serial=? AND iptal=0 ORDER BY zaman, id",
        (bina_serial,),
    ).fetchall()
    if not satirlar:
        conn.execute(
            "UPDATE bina_durum SET durum='bekliyor', son_ziyaret=NULL, son_kullanici_id=NULL, "
            "son_sonuc=NULL, tekrar_tarih=NULL, toplam_satis=0, ziyaret_sayisi=0 "
            "WHERE bina_serial=?",
            (bina_serial,),
        )
        return
    son = satirlar[-1]
    toplam_satis = sum(int(z["satis_adedi"] or 0) for z in satirlar if z["sonuc"] == "satis")
    durum = ayarlar.SONUC_DURUM[son["sonuc"]]
    tekrar = None
    gun = dt.date.fromisoformat(son["zaman"][:10])
    if son["sonuc"] == "randevu":
        tekrar = (gun + dt.timedelta(days=ayarlar.RANDEVU_GUN)).isoformat()
    elif son["sonuc"] == "evde_yok":
        tekrar = (gun + dt.timedelta(days=ayarlar.EVDE_YOK_GUN)).isoformat()
    conn.execute(
        "UPDATE bina_durum SET durum=?, son_ziyaret=?, son_kullanici_id=?, son_sonuc=?, "
        "tekrar_tarih=?, toplam_satis=?, ziyaret_sayisi=? WHERE bina_serial=?",
        (durum, son["zaman"], son["kullanici_id"], son["sonuc"], tekrar,
         toplam_satis, len(satirlar), bina_serial),
    )


def _ziyaret_isle(conn, k, g):
    if g.sonuc not in ayarlar.ZIYARET_SONUCLARI:
        raise hata(400, "Geçersiz sonuç: " + str(g.sonuc), "sonuc_gecersiz")
    bina = conn.execute(
        "SELECT b.bina_serial, b.bolge, b.daire, b.res_hp FROM bina b "
        "JOIN bina_durum d USING(bina_serial) WHERE b.bina_serial=?",
        (g.bina_serial,),
    ).fetchone()
    if not bina:
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    # Ziyaret yalnız satış (kendi bölgesi ya da listesi) ve yönetici yazar (spec §2.4-2).
    if not ziyaret_yazabilir(conn, k, g.bina_serial):
        raise hata(403, "Bu bina sizin bölgenizde değil.", "baska_bolge")

    an = ayarlar.simdi()
    zaman = _zamani_coz(g.zaman, an)

    # DÜZELTME: satışçı yanlış düğmeye bastıysa eski kaydı iptal edip yenisini yazar.
    # Böylece "Satış" yerine "Evde yok" işlenen bina iki kez sayılmaz.
    duzeltilen = None
    if g.duzeltilen_offline_id:
        duzeltilen = conn.execute(
            "SELECT * FROM ziyaret WHERE kullanici_id=? AND offline_id=? AND iptal=0",
            (k["id"], g.duzeltilen_offline_id),
        ).fetchone()
        if duzeltilen and duzeltilen["bina_serial"] != g.bina_serial:
            duzeltilen = None          # başka binanın kaydı düzeltilemez

    # Satış adedi binanın daire sayısını aşamaz: kayan bir parmak 500 satış yazıp
    # bütün kapsama sayılarını bozmasın.
    satis = g.satis_adedi if g.sonuc == "satis" else 0
    tavan = max(int(bina["daire"] or 0), int(bina["res_hp"] or 0), 1)
    if satis > tavan:
        raise hata(400, "Bu binada en çok " + str(tavan) + " abonelik olabilir (" +
                   str(satis) + " girildi).", "satis_adedi_yuksek")

    imlec = conn.execute(
        "INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, satis_adedi, "
        "konusulan_daire, notu, lat, lon, cihaz, kayit_zamani) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kullanici_id, offline_id) DO NOTHING",
        (g.offline_id, g.bina_serial, k["id"], zaman, g.sonuc, satis, g.konusulan_daire,
         (g.notu or "").strip() or None, g.lat, g.lon, g.cihaz, ayarlar.zaman_metni(an)),
    )
    if imlec.rowcount == 0:  # aynı kayıt ikinci kez geldi — hiçbir şey iki kez sayılmaz
        eski = conn.execute(
            "SELECT z.id, z.bina_serial, d.durum FROM ziyaret z "
            "JOIN bina_durum d USING(bina_serial) WHERE z.kullanici_id=? AND z.offline_id=?",
            (k["id"], g.offline_id),
        ).fetchone()
        durum = (eski["durum"] if eski else None) or "bekliyor"
        return {"ziyaret_id": eski["id"] if eski else None, "yinelenen": True,
                "bina_serial": eski["bina_serial"] if eski else g.bina_serial,
                "durum": durum, "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
                "duzeltildi": False, "mesaj": "Bu kayıt zaten alınmıştı."}

    ziyaret_id = int(imlec.lastrowid)
    if duzeltilen is not None:
        conn.execute(
            "UPDATE ziyaret SET iptal=1, iptal_eden_id=?, iptal_zamani=? WHERE id=?",
            (k["id"], ayarlar.zaman_metni(an), duzeltilen["id"]),
        )

    if g.sonuc == "randevu" and (g.tekrar_tarih or "").strip():
        istenen = (g.tekrar_tarih or "").strip()[:10]
    else:
        istenen = None
    _bina_durumunu_kur(conn, g.bina_serial)
    if istenen:
        try:
            dt.date.fromisoformat(istenen)
            conn.execute("UPDATE bina_durum SET tekrar_tarih=? WHERE bina_serial=?",
                         (istenen, g.bina_serial))
        except ValueError:
            pass
    durum = conn.execute(
        "SELECT durum FROM bina_durum WHERE bina_serial=?", (g.bina_serial,)
    ).fetchone()["durum"]

    # Görev binası YALNIZ O GÜNÜN açık görevinde kapatılır. Tarih süzgeci olmadan
    # dünden kalan açık görevdeki aynı bina da kapanıyor ve dünün raporu bugün
    # geriye dönük değişiyordu.
    conn.execute(
        "UPDATE gorev_bina SET durum='tamam' WHERE bina_serial=? AND durum='bekliyor' AND gorev_id IN ("
        "  SELECT id FROM gorev WHERE kullanici_id=? AND durum='acik' AND tarih=?)",
        (g.bina_serial, k["id"], zaman[:10]),
    )
    db.surumu_arttir(conn)
    return {"ziyaret_id": ziyaret_id, "yinelenen": False, "bina_serial": g.bina_serial,
            "durum": durum, "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
            "duzeltildi": duzeltilen is not None,
            "mesaj": "Düzeltildi." if duzeltilen is not None else "Kaydedildi."}


@yonlendirici.post("/api/ziyaret")
def ziyaret_ekle(
    girdi: ZiyaretGirdi,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    sonuc = _ziyaret_isle(conn, k, girdi)
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    sonuc["ozet"] = _gorev_ozet(conn, gorev["id"] if gorev else None)
    return sonuc


@yonlendirici.post("/api/ziyaret/toplu")
def ziyaret_toplu(
    girdiler: list[ZiyaretGirdi],
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Çevrimdışı kuyruğun senkronu. Tek bir kayıt hatalıysa kuyruğun tamamı düşmez.

    HER KAYIT İÇİN TEKİL SONUÇ döner. Uygulama kuyruktan YALNIZCA ``kabul``
    listesindeki ``offline_id``leri siler; ``hatali`` listesindekiler telefonda
    kalır ve satışçıya "N kayıt gönderilemedi" diye gösterilir.

    Eskiden yanıt sadece sayı döndürüyordu, uygulama da kuyruğun TAMAMINI
    siliyordu: sunucunun reddettiği kayıt (ör. yönetici gün içinde bölgeyi
    değiştirdiyse ``baska_bolge``) sessizce ve kalıcı olarak kayboluyordu.
    Sessiz silme hiçbir koşulda olmamalı — bu uygulamanın tek sözü, kaydın
    kaybolmayacağı.
    """
    if len(girdiler) > 500:
        raise hata(400, "Tek seferde en çok 500 kayıt gönderilebilir.", "cok_kayit")
    kaydedilen, yinelenen, kabul, hatali = 0, 0, [], []
    for g in girdiler:
        try:
            sonuc = _ziyaret_isle(conn, k, g)
            yinelenen += 1 if sonuc["yinelenen"] else 0
            kaydedilen += 0 if sonuc["yinelenen"] else 1
            kabul.append(g.offline_id)          # kesin yazıldı ya da zaten vardı
        except HTTPException as exc:
            ayrinti = exc.detail if isinstance(exc.detail, dict) else {"hata": str(exc.detail), "kod": "hata"}
            hatali.append({"offline_id": g.offline_id, **ayrinti})
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    return {"kaydedilen": kaydedilen, "yinelenen": yinelenen,
            "kabul": kabul, "hatali": hatali,
            "ozet": _gorev_ozet(conn, gorev["id"] if gorev else None)}


class IptalGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    neden: str | None = None


@yonlendirici.post("/api/ziyaret/{ziyaret_id}/iptal")
def ziyaret_iptal(
    ziyaret_id: int,
    girdi: IptalGirdi | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Yanlış işlenen bir ziyareti geri alır.

    Yanlış düğmeye basmak sahada en sık yapılan hatadır ve bugüne kadar geri
    dönüşü yoktu: sayaçlar, kapsama ve Excel raporu kalıcı olarak bozuluyordu.
    Kayıt SİLİNMEZ, iptal edilir; sahada ne olduğunun izi kalır ama bütün
    toplamlardan düşer ve bina durumu kalan GEÇERLİ ziyaretlerden yeniden kurulur.

    Kaydı giren satışçı AYNI GÜN içinde iptal edebilir; yönetici her zaman.
    """
    z = conn.execute("SELECT * FROM ziyaret WHERE id=?", (ziyaret_id,)).fetchone()
    if not z:
        raise hata(404, "Ziyaret kaydı bulunamadı.", "ziyaret_yok")
    if z["iptal"]:
        return {"ziyaret_id": ziyaret_id, "iptal": True, "mesaj": "Bu kayıt zaten iptal edilmişti.",
                "bina_serial": z["bina_serial"]}
    if "yonetici" not in yetki.gorevler(k):
        if z["kullanici_id"] != k["id"]:
            raise hata(403, "Yalnızca kendi kaydınızı geri alabilirsiniz.", "yasak")
        if z["zaman"][:10] != ayarlar.bugun().isoformat():
            raise hata(403, "Geçmiş günün kaydını yalnızca yönetici geri alabilir.", "gec_kaldi")

    conn.execute(
        "UPDATE ziyaret SET iptal=1, iptal_eden_id=?, iptal_zamani=?, "
        "notu=COALESCE(notu,'') || ? WHERE id=?",
        (k["id"], ayarlar.zaman_metni(),
         (" [iptal: " + girdi.neden.strip()[:120] + "]") if (girdi and girdi.neden) else "",
         ziyaret_id),
    )
    _bina_durumunu_kur(conn, z["bina_serial"])

    # O GÜNÜN LİSTESİ DE AÇILIR. Yoksa bina_durum "bekliyor" derken günün
    # listesinde yeşil tikli kalıyordu: satışçı yanlış kaydı geri alıyor ama
    # binayı bugün yeniden gezemiyor, yöneticinin "kalan"ı da bir eksik
    # görünüyordu. Kendi içinde çelişen bir ekran, güveni en hızlı bitiren şey.
    gun = z["zaman"][:10]
    kalan_gecerli = conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE bina_serial=? AND kullanici_id=? "
        "AND iptal=0 AND substr(zaman,1,10)=?",
        (z["bina_serial"], z["kullanici_id"], gun),
    ).fetchone()[0]
    if not kalan_gecerli:
        conn.execute(
            "UPDATE gorev_bina SET durum='bekliyor' WHERE bina_serial=? AND durum='tamam' "
            "AND gorev_id IN (SELECT id FROM gorev WHERE kullanici_id=? AND durum='acik' AND tarih=?)",
            (z["bina_serial"], z["kullanici_id"], gun),
        )

    db.surumu_arttir(conn)
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    return {"ziyaret_id": ziyaret_id, "iptal": True, "bina_serial": z["bina_serial"],
            "mesaj": "Kayıt geri alındı.", "ozet": _gorev_ozet(conn, gorev["id"] if gorev else None)}

# ============================================================================= bina
@yonlendirici.get("/api/bina")
def bina_listesi(
    bolge: int | None = None,
    durum: str | None = None,
    mahalle: str | None = None,
    ilce: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    bolge = bolge_kapsami(k, bolge)
    kosul, deger = [], []
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    if durum:
        if durum not in ayarlar.BINA_DURUMLARI:
            raise hata(400, f"Geçersiz durum: {durum}", "durum_gecersiz")
        kosul.append("d.durum=?")
        deger.append(durum)
    if mahalle:
        kosul.append("b.mahalle=?")
        deger.append(mahalle)
    if ilce:
        kosul.append("b.ilce=?")
        deger.append(ilce)
    if q:
        kosul.append("(b.ad LIKE ? OR b.site_adi LIKE ? OR b.sokak LIKE ? OR b.bina_serial LIKE ?)")
        deger.extend([f"%{q}%"] * 4)
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""

    toplam = conn.execute(
        f"SELECT COUNT(*) FROM bina b JOIN bina_durum d USING(bina_serial){nerede}", tuple(deger)
    ).fetchone()[0]
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial){nerede} "
        "ORDER BY b.firsat DESC, b.bina_serial LIMIT ? OFFSET ?",
        tuple(deger) + (limit, offset),
    ).fetchall()
    return {"toplam": toplam, "limit": limit, "offset": offset,
            "binalar": [_bina_kart(s) for s in satirlar]}


@yonlendirici.get("/api/bina/{bina_serial}")
def bina_detay(
    bina_serial: str,
    k: dict = Depends(izin("bina.oku")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    satir = conn.execute(
        f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bina_serial=?",
        (bina_serial,),
    ).fetchone()
    if not satir:
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    if not bina_gorebilir(conn, k, bina_serial):
        raise hata(403, "Bu bina sizin bölgenizde değil.", "baska_bolge")

    ziyaretler = conn.execute(
        "SELECT z.id, z.offline_id, z.zaman, z.sonuc, z.satis_adedi, z.konusulan_daire, z.notu, "
        "       z.kullanici_id, k.ad AS kullanici "
        "FROM ziyaret z LEFT JOIN kullanici k ON k.id=z.kullanici_id "
        "WHERE z.bina_serial=? AND z.iptal=0 ORDER BY z.zaman DESC LIMIT 50",
        (bina_serial,),
    ).fetchall()
    from . import ticket as ticket_defteri

    return {
        "bina": _bina_kart(satir),
        "ziyaretler": [
            {**dict(z), "sonuc_etiket": ayarlar.SONUC_ETIKET.get(z["sonuc"], z["sonuc"])}
            for z in ziyaretler
        ],
        # Bu binaya açılmış OneDesk ticket'ları (en yenisi önce). Kart "açık ticket
        # var" rozetini buradan gösterir; aynı sorun için ikinci ticket açılmasın.
        "ticketlar": ticket_defteri.binanin_ticketlari(conn, bina_serial),
    }


# Harita yanıtının DEĞİŞMEYEN yarısı: {bölge: ((bina sayısı, künye sürümü), seri sırası, JSON parçası)}.
# Bina adı, konumu ve fırsatı asla değişmez; yalnız `durum` değişir. Böylece bir
# ziyaret kaydedildiğinde 1,4 MB'ı baştan kurmak yerine sadece durum dizisini
# yeniden yazıyoruz.
_harita_sabit: dict[str, tuple[tuple[int, int], list[str], bytes]] = {}
# Tam yanıt: {bölge: ((veri_surumu, bina_surumu), hazır baytlar)}
_harita_onbellek: dict[str, tuple[tuple[int, int], bytes]] = {}


def _harita_sabiti(conn: sqlite3.Connection, bolge: int | None, anahtar: str):
    # Bina sayısı ya da künye sürümü değiştiyse (bölge planı uygulandı, tur raporu
    # işlendi, "python -m saha.kur" yeniden çalıştı) sunucuyu yeniden başlatmadan tazelenir.
    if bolge is None:
        adet = conn.execute("SELECT COUNT(*) FROM bina WHERE pasif=0").fetchone()[0]
    else:
        adet = conn.execute("SELECT COUNT(*) FROM bina WHERE bolge=? AND pasif=0",
                            (int(bolge),)).fetchone()[0]
    imza = (adet, db.bina_surum_oku(conn))
    saklanan = _harita_sabit.get(anahtar)
    if saklanan and saklanan[0] == imza:
        return saklanan[1], saklanan[2]
    alanlar = ("SELECT b.bina_serial, b.lat, b.lon, b.firsat, b.bolge, "
               "b.ad, b.site_adi, b.sokak, b.kapi_no, b.location_id "
               "FROM bina b ")
    if bolge is None:
        satirlar = conn.execute(alanlar + "WHERE b.pasif=0 ORDER BY b.bina_serial").fetchall()
    else:
        satirlar = conn.execute(alanlar + "WHERE b.bolge=? AND b.pasif=0 ORDER BY b.bina_serial",
                                (int(bolge),)).fetchall()
    seriler = [s["bina_serial"] for s in satirlar]
    parca = json.dumps({
        "adet": len(satirlar),
        "serial": seriler,
        # Haritada bir noktaya dokununca kartta seri numarası değil bina adı çıksın.
        "ad": [_baslik(dict(s)) for s in satirlar],
        # Kartta adın yanında Location Id (BOSS/OneMap'te aranan kimlik)
        "loc": [s["location_id"] or "" for s in satirlar],
        # 5 basamak ~1 m hassasiyet; yanıtı belirgin ölçüde küçültür.
        "lat": [round(s["lat"], 5) for s in satirlar],
        "lon": [round(s["lon"], 5) for s in satirlar],
        "firsat": [s["firsat"] for s in satirlar],
        "bolge": [s["bolge"] for s in satirlar],
        "ofis": ayarlar.OFIS,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _harita_sabit[anahtar] = (imza, seriler, parca[1:-1])   # dış süslü parantezler atılır
    return seriler, parca[1:-1]


@yonlendirici.get("/api/harita")
def harita(
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Harita için sıkı diziler — 19.706 nokta tek istekte, alan adı tekrarı olmadan."""
    bolge = bolge_kapsami(k, bolge)
    surum = (db.surum_oku(conn), db.bina_surum_oku(conn))
    anahtar = "hepsi" if bolge is None else str(int(bolge))

    saklanan = _harita_onbellek.get(anahtar)
    if saklanan and saklanan[0] == surum:
        return Response(content=saklanan[1], media_type="application/json")

    seriler, sabit = _harita_sabiti(conn, bolge, anahtar)
    durumlar = dict(conn.execute("SELECT bina_serial, durum FROM bina_durum").fetchall())
    durum_parcasi = json.dumps(
        [durumlar.get(x, "bekliyor") for x in seriler], separators=(",", ":"),
    ).encode("utf-8")
    govde = b"{" + sabit + b',"durum":' + durum_parcasi + b"}"
    _harita_onbellek[anahtar] = (surum, govde)
    return Response(content=govde, media_type="application/json")


# Yol ağı büyük ve hiç değişmez: süreç başına bir kez okunur, bellekte tutulur.
_yol_onbellek: dict[str, bytes] = {}


@yonlendirici.get("/api/yollar")
def yollar(
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Haritanın arka planındaki yol çizgileri (``veri/ref/osm_yollar.geojson``).

    Sözleşmede yok; harita bu olmadan da çizilir. Bölge verilirse o bölgenin
    binalarını çevreleyen kutuya kırpılır — telefona gereksiz veri gitmesin.
    """
    bolge = bolge_kapsami(k, bolge)
    # Bölge kutusu bölge planıyla değişir: anahtara künye sürümü girer.
    anahtar = ("hepsi" if bolge is None else str(int(bolge))) + f"@{db.bina_surum_oku(conn)}"
    saklanan = _yol_onbellek.get(anahtar)
    if saklanan is None:
        yol = ayarlar.VERI_YOLLAR
        if not yol.exists():
            raise hata(404, "Yol ağı dosyası bulunamadı.", "yol_yok")
        veri = json.loads(yol.read_text(encoding="utf-8"))
        ozellikler = veri.get("features", [])
        if bolge is not None:
            kutu = conn.execute(
                "SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM bina WHERE bolge=?",
                (int(bolge),),
            ).fetchone()
            if kutu and kutu[0] is not None:
                ozellikler = _yollari_kirp(ozellikler, *kutu)
        saklanan = json.dumps(
            {"type": "FeatureCollection", "features": ozellikler}, ensure_ascii=False,
        ).encode("utf-8")
        _yol_onbellek[anahtar] = saklanan
    return Response(content=saklanan, media_type="application/json",
                    headers={"Cache-Control": "public, max-age=86400"})


def _yollari_kirp(ozellikler: list, lat_min, lat_max, lon_min, lon_max, pay: float = 0.01) -> list:
    """Kutuya değmeyen yolları atar (kaba ama hızlı: her çizginin kendi kutusuna bakar)."""
    lat1, lat2 = lat_min - pay, lat_max + pay
    lon1, lon2 = lon_min - pay, lon_max + pay

    def deger(koordinatlar) -> bool:
        ax = [c[0] for c in koordinatlar]
        ay = [c[1] for c in koordinatlar]
        return not (max(ax) < lon1 or min(ax) > lon2 or max(ay) < lat1 or min(ay) > lat2)

    kalan = []
    for o in ozellikler:
        g = o.get("geometry") or {}
        tur, koor = g.get("type"), g.get("coordinates") or []
        if tur == "LineString" and koor and deger(koor):
            kalan.append(o)
        elif tur == "MultiLineString":
            parcalar = [c for c in koor if c and deger(c)]
            if parcalar:
                kalan.append({**o, "geometry": {"type": "MultiLineString", "coordinates": parcalar}})
    return kalan


# ============================================================================= özet
@yonlendirici.get("/api/ozet/gun")
def ozet_gun(
    tarih: str | None = None,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    gun = _tarih_coz(tarih).isoformat()
    satiscilar = conn.execute(
        "SELECT * FROM kullanici WHERE rol='satisci' ORDER BY bolge, id"
    ).fetchall()
    satirlar, toplam = [], {"ziyaret": 0, "satis": 0, "ret": 0, "randevu": 0, "kalan": 0,
                            "satis_adedi": 0, "gorev_toplam": 0, "gorev_tamam": 0}
    for s in satiscilar:
        z = conn.execute(
            "SELECT COUNT(*) AS ziyaret, "
            "COALESCE(SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END),0) AS satis, "
            "COALESCE(SUM(satis_adedi),0) AS satis_adedi, "
            "COALESCE(SUM(CASE WHEN sonuc='ilgilenmedi' THEN 1 ELSE 0 END),0) AS ret, "
            "COALESCE(SUM(CASE WHEN sonuc='randevu' THEN 1 ELSE 0 END),0) AS randevu, "
            "COALESCE(SUM(CASE WHEN sonuc='evde_yok' THEN 1 ELSE 0 END),0) AS evde_yok, "
            "COALESCE(SUM(CASE WHEN sonuc='girilemedi' THEN 1 ELSE 0 END),0) AS girilemedi, "
            "COALESCE(SUM(CASE WHEN sonuc='altyapi_sorunu' THEN 1 ELSE 0 END),0) AS altyapi_sorunu "
            "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)=?",
            (s["id"], gun),
        ).fetchone()
        gorev = conn.execute(
            "SELECT id FROM gorev WHERE kullanici_id=? AND tarih=? ORDER BY id DESC LIMIT 1",
            (s["id"], gun),
        ).fetchone()
        # İlerleme çubuğunun paydası GÖREV LİSTESİNDEN gelir, ziyaret
        # sayısından değil. Aksi halde aynı binaya ikinci kez gidilince payda da
        # şişiyor ve 25 binalık listede "28 / 28 bina · Listeyi bitirdi" yazıyor,
        # eksik hiç görünmüyordu.
        gb = conn.execute(
            "SELECT COUNT(*) AS toplam, "
            "SUM(CASE WHEN gb.durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
            "SUM(CASE WHEN gb.durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
            "FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
            "WHERE g.kullanici_id=? AND g.tarih=?",
            (s["id"], gun),
        ).fetchone()
        kalan = int(gb["kalan"] or 0)
        satir = {
            "kullanici_id": s["id"], "ad": s["ad"], "bolge": s["bolge"],
            "gorev_id": gorev["id"] if gorev else None,
            "ziyaret": z["ziyaret"], "satis": z["satis"], "satis_adedi": int(z["satis_adedi"]),
            "ret": z["ret"], "randevu": z["randevu"], "evde_yok": z["evde_yok"],
            "girilemedi": z["girilemedi"], "altyapi_sorunu": z["altyapi_sorunu"], "kalan": kalan,
            "gorev_toplam": int(gb["toplam"] or 0), "gorev_tamam": int(gb["tamam"] or 0),
            # "satis" = satışla biten BİNA, "satis_adedi" = satılan ABONELİK.
            # Dönüşüm binadan hesaplanır; satışçı ekranıyla aynı tanım.
            "donusum": round(z["satis"] / z["ziyaret"], 4) if z["ziyaret"] else 0.0,
        }
        for alan in toplam:
            toplam[alan] += satir[alan]
        satirlar.append(satir)
    toplam["donusum"] = round(toplam["satis"] / toplam["ziyaret"], 4) if toplam["ziyaret"] else 0.0
    return {"tarih": gun, "satiscilar": satirlar, "toplam": toplam}


@yonlendirici.get("/api/ozet/kapsama")
def ozet_kapsama(
    kirilim: str = Query(default="bolge", pattern="^(bolge|mahalle|ilce)$"),
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi", "satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Sudokunun doldurulan kareleri: neye dokunuldu, ne kaldı.

    ÜÇ AYRI SAYI, üçü de farklı soruya cevap verir:
      dokunulan  — binaya gidildi (sonuç ne olursa olsun)
      temas      — kapı açıldı, biriyle konuşuldu (girilemedi/altyapı hariç)
      kalan_firsat — HENÜZ SATILMAMIŞ boş kapı
    Eski tek sayı ("kalan fırsat = dokunulmamış binaların bütün kapıları")
    ilerlemeyi ciddi şekilde abartıyordu: 753 satışla ~38.000 kapı bitmiş
    görünüyordu. Manşet cümlenin doğru olması, sistemin ikna gücünün tamamı.
    """
    bolge = bolge_kapsami(k, bolge)
    # Mahalle kırılımında İLÇE de gruba girer: Bursa'da "Yeni" mahallesi dört
    # ayrı ilçede var ve tek satırda toplanınca yönetici 41 km aralıktaki iki
    # yerleşimi tek liste sanıyordu.
    sutun = {"bolge": "b.bolge", "mahalle": "b.mahalle", "ilce": "b.ilce"}[kirilim]
    gruplar = "b.ilce, b.mahalle" if kirilim == "mahalle" else sutun
    # Son tur raporunda olmayan (pasif) bina kapsamaya girmez: artık satılacak kapı değil.
    kosul, deger = ["b.pasif=0"], []
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""

    temas_sql = ",".join("'%s'" % x for x in ayarlar.TEMAS_SONUCLARI)
    olculer = (
        "COUNT(*) AS toplam, "
        "SUM(CASE WHEN d.son_ziyaret IS NOT NULL THEN 1 ELSE 0 END) AS dokunulan, "
        f"SUM(CASE WHEN d.son_sonuc IN ({temas_sql}) THEN 1 ELSE 0 END) AS temas, "
        "COALESCE(SUM(b.firsat),0) AS firsat, "
        "COALESCE(SUM(MAX(b.firsat - d.toplam_satis, 0)),0) AS kalan_firsat, "
        "COALESCE(SUM(CASE WHEN d.son_ziyaret IS NULL THEN b.firsat ELSE 0 END),0) "
        "    AS dokunulmayan_firsat, "
        "COALESCE(SUM(d.toplam_satis),0) AS satis, "
        "COALESCE(SUM(CASE WHEN d.toplam_satis>0 THEN 1 ELSE 0 END),0) AS satis_bina"
    )

    sorgu = (
        f"SELECT {sutun} AS ad, b.ilce AS ilce, {olculer} "
        f"FROM bina b JOIN bina_durum d USING(bina_serial){nerede} "
        f"GROUP BY {gruplar} ORDER BY toplam DESC"
    )
    satirlar = []
    for r in conn.execute(sorgu, tuple(deger)).fetchall():
        toplam = r["toplam"] or 0
        ad = r["ad"] if r["ad"] is not None else "Atanmamış"
        satirlar.append({
            "ad": f"{ad} / {r['ilce']}" if (kirilim == "mahalle" and r["ilce"]) else ad,
            "mahalle": ad if kirilim == "mahalle" else None,
            "ilce": r["ilce"] if kirilim == "mahalle" else None,
            "toplam": toplam,
            "dokunulan": r["dokunulan"] or 0,
            "temas": r["temas"] or 0,
            "kalan": toplam - (r["dokunulan"] or 0),
            "oran": round((r["dokunulan"] or 0) / toplam, 4) if toplam else 0.0,
            "firsat": int(r["firsat"]),
            "kalan_firsat": int(r["kalan_firsat"]),
            "dokunulmayan_firsat": int(r["dokunulmayan_firsat"]),
            "satis": int(r["satis"]),
            "satis_bina": int(r["satis_bina"]),
        })
    genel = conn.execute(
        f"SELECT {olculer} FROM bina b JOIN bina_durum d USING(bina_serial){nerede}",
        tuple(deger),
    ).fetchone()
    toplam = genel["toplam"] or 0
    return {
        "kirilim": kirilim,
        "toplam": toplam,
        "dokunulan": genel["dokunulan"] or 0,
        "temas": genel["temas"] or 0,
        "kalan": toplam - (genel["dokunulan"] or 0),
        "oran": round((genel["dokunulan"] or 0) / toplam, 4) if toplam else 0.0,
        "firsat": int(genel["firsat"]),
        "kalan_firsat": int(genel["kalan_firsat"]),
        "dokunulmayan_firsat": int(genel["dokunulmayan_firsat"]),
        "satis": int(genel["satis"]),
        "satis_bina": int(genel["satis_bina"]),
        "satirlar": satirlar,
    }


# ============================================================================= rapor
@yonlendirici.get("/api/dosya/rapor.xlsx")
def gunluk_rapor(
    tarih: str | None = None,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    gun = _tarih_coz(tarih)
    yol = rapor.gunluk_rapor_yaz(conn, gun)
    return FileResponse(
        yol,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Saha_Gun_Raporu_{gun.isoformat()}.xlsx",
    )


# ============================================================================= harita önbelleği (açılış)
# api.py yaşam döngüsü çağırır.
def _haritayi_isit() -> None:
    """Harita yanıtının değişmeyen yarısını açılışta hazırlar.

    Böylece yöneticinin ilk harita isteği de, satışçının ilk isteği de hazır
    veriyle karşılanır; kimse "ilk açılış yavaş" demez. Maliyeti açılışta ~1 sn.
    """
    gunluk = logging.getLogger("saha.harita")
    try:
        conn = db.baglan()
    except Exception:
        return
    try:
        if conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == 0:
            return
        _harita_sabiti(conn, None, "hepsi")
        n = db.bolge_sayisi(conn)
        for b in range(1, n + 1):
            _harita_sabiti(conn, b, str(b))
        gunluk.info("Harita önbelleği hazır (%d bölge + şehir geneli).", n)
    except sqlite3.Error as exc:
        gunluk.warning("Harita önbelleği hazırlanamadı: %s", exc)
    finally:
        conn.close()
