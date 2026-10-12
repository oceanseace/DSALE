"""Ortak yardımcılar (çekirdek): birden çok uç modülünün kullandığı kişi kartı, telefon/davet denetimi,
bina başlığı, görev özeti ve KVKK erişim kaydı (``erisim_yaz``). Burada uç (URL) YOKTUR; ``hata``, ``baglanti``, ``izin`` ``saha/yetki.py``'dadır.
Kullananlar: ``giris_uclari``, ``satis_uclari``, ``ekip_uclari``, ``yonetim_uclari`` ve ``api`` (sağlık).
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from . import ayarlar, db, guvenlik, yetki
from .yetki import hata, izin


# ============================================================================= kimlik
# baglanti, mevcut_kullanici, hata, izin, bolge_kapsami ... saha/yetki.py'dadır; uç modülleri oradan alır.

# Eski ad: yalnız "veri yönetimi" anlamında kalır (spec §2.2); yeni uçlar kendi eylemini ister.
yonetici = izin("veri.yonet")


def _etiket_listesi(metin: str | None) -> list[str]:
    try:
        deger = json.loads(metin) if metin else []
    except (TypeError, ValueError):
        return []
    return [str(x) for x in deger] if isinstance(deger, list) else []


def _kullanici_kart(k: dict | sqlite3.Row, gorevler: list[str] | None = None, maskeli: bool = False) -> dict:
    """Kişi kartı. ``maskeli``: listelerde telefon "0532 ••• •• 06" (tam hâli yalnız tek kişi yanıtında)."""
    k = dict(k)
    kume = gorevler if gorevler is not None else (k.get("gorevler") or [k["rol"]])
    kisi = {**k, "gorevler": kume}
    kart = {
        "id": k["id"],
        "ad": k["ad"],
        "telefon_goster": guvenlik.telefon_maskeli(k["telefon"]) if maskeli else guvenlik.telefon_goster(k["telefon"]),
        "rol": k["rol"],
        "gorevler": [r for r in yetki.ROLLER if r in set(kume) | {k["rol"]}],
        "gorev_etiketi": yetki.gorev_etiketi(kisi),
        "bolge": k["bolge"],
        "aktif": bool(k["aktif"]),
        "pin_var": bool(k.get("pin_hash")),
        # Ek-2: telefonu olmayan kişi giriş yapamaz (BOSS Mobil'le çalışır); atama yine yapılabilir.
        "giris_var": bool(k["telefon"]),
        "unvan": k.get("unvan"),
        "kaynak": k.get("kaynak") or "elle",
        "etiket": _etiket_listesi(k.get("etiket")),
        "boss_ekip": k.get("boss_ekip"),
        "kapasite": k.get("kapasite"),
        # v9: unvan kataloğu bağı, takım lideri bayrağı, Administrator rozeti (arayüzden verilemez).
        "unvan_id": k.get("unvan_id"),
        "takim_lideri": bool(k.get("takim_lideri")),
        "administrator": yetki.administrator_mi(k),
    }
    if not maskeli:
        kart["telefon"] = k["telefon"]
    return kart


def _telefon_veya_hata(ham: str) -> str:
    telefon = guvenlik.telefon_duzelt(ham)
    if not telefon:
        raise hata(400, "Telefon numarası geçersiz. Örnek: 0532 111 22 33", "telefon_gecersiz")
    return telefon


def _davet_suresi_doldu(k) -> bool:
    """Yeni davet kodları (``davet_zamani`` dolu) 48 saat geçerlidir; eski kodlar süresizdir."""
    zaman = (dict(k).get("davet_zamani") or "").strip()
    if not zaman:
        return False
    try:
        uretim = dt.datetime.fromisoformat(zaman)
    except ValueError:
        return False
    return ayarlar.simdi() - uretim > dt.timedelta(hours=ayarlar.DAVET_GECERLILIK_SAAT)


# ============================================================================= KVKK erişim kaydı
def erisim_yaz(conn: sqlite3.Connection, k: dict, eylem: str, adet: int) -> None:
    """KVKK erişim kaydı (spec §2.5): müşteri alanı döndüren yanıt, adetle. Yazılamazsa yanıt yine döner.
    Kullananlar: arama_uclari (arama), tablolar_uclari (tablo_*), yonetim_uclari (ticket_lokasyon)."""
    if not adet:
        return
    try:
        simdi = ayarlar.zaman_metni()
        conn.execute("INSERT INTO erisim_kaydi (zaman, gun, kullanici_id, kullanici_ad, eylem, is_no, adet, ip) "
                     "VALUES (?,?,?,?,?,NULL,?,NULL)", (simdi, simdi[:10], k["id"], k.get("ad"), eylem, adet))
        conn.commit()
    except sqlite3.Error:
        pass


# ============================================================================= bina kartı
_BOS_AD = {"", "null", "none", "nan", "-"}


def _baslik(b: dict) -> str:
    # Kaynakta ad yerine 'Null' yazan binalar var; kartta "Null" başlığı çıkmasın.
    for alan in ("ad", "site_adi"):
        deger = (b.get(alan) or "").strip()
        if deger.lower() not in _BOS_AD:
            return deger
    sokak = (b.get("sokak") or "").strip()
    kapi = (b.get("kapi_no") or "").strip()
    if sokak:
        return f"{sokak} No:{kapi}" if kapi else sokak
    return b.get("bina_serial", "")


# ============================================================================= görev yardımcıları
def _acik_gorev(conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM gorev WHERE kullanici_id=? AND tarih=? AND durum='acik' ORDER BY id DESC LIMIT 1",
        (kullanici_id, tarih.isoformat()),
    ).fetchone()


def _gorev_ozet(conn: sqlite3.Connection, gorev_id: int | None) -> dict:
    if not gorev_id:
        return {"gorev_id": None, "toplam": 0, "tamam": 0, "kalan": 0, "satis": 0,
                "satis_bina": 0, "ziyaret": 0, "donusum": 0.0}
    s = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
        "SUM(CASE WHEN durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
        "FROM gorev_bina WHERE gorev_id=?",
        (gorev_id,),
    ).fetchone()
    g = conn.execute("SELECT kullanici_id, tarih FROM gorev WHERE id=?", (gorev_id,)).fetchone()
    z = conn.execute(
        "SELECT COALESCE(SUM(satis_adedi),0) AS adet, "
        "       COALESCE(SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END),0) AS bina, "
        "       COUNT(*) AS ziyaret "
        "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)=?",
        (g["kullanici_id"], g["tarih"]),
    ).fetchone()
    ziyaret = int(z["ziyaret"] or 0)
    return {
        "gorev_id": gorev_id,
        "toplam": s["toplam"] or 0,
        "tamam": s["tamam"] or 0,
        "kalan": s["kalan"] or 0,
        # "satis" = satılan abonelik adedi (satışçının primi buna bağlı),
        # "satis_bina" = satışla biten bina. Dönüşüm İKİNCİSİNDEN hesaplanır ki
        # yönetici ekranıyla aynı şeyi söylesin.
        "satis": int(z["adet"] or 0),
        "satis_bina": int(z["bina"] or 0),
        "ziyaret": ziyaret,
        "donusum": round(int(z["bina"] or 0) / ziyaret, 4) if ziyaret else 0.0,
    }


def _demo_kurulu(conn: sqlite3.Connection) -> bool:
    """Gösterim verisi kurulu mu? Ekranlarda uyarı şeridi bunun için çıkar."""
    try:
        return db.ayar_oku(conn, "demo") is not None
    except sqlite3.Error:
        return False
