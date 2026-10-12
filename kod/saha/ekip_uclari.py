"""Ekip uçları (Yönetim): kişi ekleme/düzenleme/silme, görev kümesi, davet kodu, PIN sıfırlama, cihaz çıkışı,
iş aktarımı, giriş ekranındaki yardım ayarı ve personel rehberi (unvan → görev eşlemesi) içe aktarımı.

URL'ler: /api/kullanici* (rehber ve eşleme dahil) · /api/ayar
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from . import ayarlar, db, guvenlik, sema_v2, yetki
from .api_ortak import _davet_suresi_doldu, _kullanici_kart, _telefon_veya_hata
from .yetki import baglanti, hata, izin

yonlendirici = APIRouter()


# ============================================================================= kullanıcı yönetimi (Ekip)
# Spec §5.3.7 + Ek-1 (görev kümesi) + Ek-2 (girişsiz kişiler, personel rehberi). Hepsi ``ekip.yonet``.
# Korumalar (409): kendi görevini değiştiremez (kendi_rolu), kendini pasife alamaz/silemez
# (kendini_silemez), son aktif yönetici düşürülemez/pasife alınamaz/silinemez (son_yonetici).
# Her değişiklik yonetim_kaydi'na yazılır; kişisel veri DEĞERİ (telefon, PIN, kod) yazılmaz.

class KullaniciGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int | None = None
    ad: str = Field(min_length=2, max_length=80)
    telefon: str | None = None          # Ek-2: boş = girişsiz kişi (BOSS Mobil'le çalışır)
    rol: str = "satisci"                # ANA görev: girişte açılan ekran
    gorevler: list[str] | None = None   # Ek-1: görev kümesi; verilmezse yalnız ana görev
    bolge: int | None = None
    etiket: list[str] | None = None     # ["lider"] / ["btk","arama"] — yetki VERMEZ
    boss_ekip: str | None = Field(default=None, max_length=80)
    kapasite: int | None = Field(default=None, ge=1, le=60)
    unvan: str | None = Field(default=None, max_length=120)
    unvan_id: int | None = None         # v9: unvan kataloğu (yetki modelinde erişim buradan gelir)
    takim_lideri: bool | None = None
    aktif: bool = True


_GOREV_METNI = "Görev Satış, Operasyon, Teknik ya da Yönetici olmalı."


def _kume_coz(rol: str, gorevler: list[str] | None) -> list[str]:
    """Ana görev + küme → sabit sıralı küme. Tanınmayan görev 400."""
    if rol not in yetki.ROLLER:
        raise hata(400, _GOREV_METNI, "rol_hatali")
    kume = set(gorevler or []) | {rol}
    if not kume <= set(yetki.ROLLER):
        raise hata(400, _GOREV_METNI, "rol_hatali")
    return [r for r in yetki.ROLLER if r in kume]


def _bolge_coz(conn: sqlite3.Connection, kume: list[str], bolge: int | None, ad: str | None = None) -> int | None:
    """Bölge yalnız satışta tutulur ve orada zorunludur (spec §5.3.7, Ek-1)."""
    if "satisci" not in kume:
        return None
    ust = db.bolge_sayisi(conn)       # 8 ekipten 14 ekibe çıkınca 14
    if not bolge or not (1 <= int(bolge) <= ust):
        kimin = f"{ad} için " if ad else "Satışçı için "
        raise hata(400, f"{kimin}1-{ust} arası bölge seçin.", "bolge_gecersiz")
    return int(bolge)


def _kume_yaz(conn: sqlite3.Connection, kid: int, kume: list[str]) -> None:
    conn.execute(f"DELETE FROM kullanici_gorev WHERE kullanici_id=? AND rol NOT IN ({','.join('?' * len(kume))})",
                 (kid, *kume))
    conn.executemany("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?,?)",
                     [(kid, r) for r in kume])


def _aktif_yoneticiler(conn: sqlite3.Connection, haric: int | None = None) -> int:
    """Aktif ve kümesinde 'yonetici' olan kişi sayısı (``haric`` dışında)."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM kullanici k WHERE k.aktif=1 AND k.id IS NOT ? AND (k.rol='yonetici' OR EXISTS "
        "(SELECT 1 FROM kullanici_gorev g WHERE g.kullanici_id=k.id AND g.rol='yonetici'))",
        (haric,)).fetchone()[0])


def _son_yonetici_mi(conn: sqlite3.Connection, satir: dict, kume_once: list[str]) -> bool:
    return bool(satir["aktif"]) and "yonetici" in kume_once and _aktif_yoneticiler(conn, satir["id"]) == 0


_SON_YONETICI = "Son aktif yönetici düşürülemez, pasife alınamaz, silinemez."


def _davet_durumu(satir: dict) -> dict:
    bekliyor = bool(satir["telefon"]) and not satir.get("pin_hash") and bool(satir.get("davet_kodu"))
    doldu = bekliyor and _davet_suresi_doldu(satir)
    return {"davet_bekliyor": bekliyor and not doldu, "davet_suresi_doldu": doldu}


def _obek_sahiplikleri(conn: sqlite3.Connection) -> dict[int, list[dict]]:
    """Kişi → ev teknisyeni olduğu öbekler (Ekip listesinde "Teknik · Görükle, Özlüce")."""
    try:
        satirlar = conn.execute("SELECT id, ad, sahip_id FROM obek WHERE aktif=1 AND sahip_id IS NOT NULL "
                                "ORDER BY ad").fetchall()
    except sqlite3.OperationalError:
        return {}
    sonuc: dict[int, list[dict]] = {}
    for r in satirlar:
        sonuc.setdefault(r["sahip_id"], []).append({"id": r["id"], "ad": r["ad"]})
    return sonuc


def _son_etkinlikler(conn: sqlite3.Connection) -> dict[int, str]:
    """Kişi başına son etkinlik: son başarılı giriş ya da son ziyaret kaydı (hangisi yeniyse)."""
    sonuc: dict[int, str] = {}
    for kid, zaman in conn.execute(
            "SELECT k.id, MAX(g.zaman) FROM kullanici k JOIN giris_denemesi g ON g.telefon=k.telefon "
            "WHERE g.basarili=1 GROUP BY k.id").fetchall():
        sonuc[kid] = zaman
    for kid, zaman in conn.execute("SELECT kullanici_id, MAX(kayit_zamani) FROM ziyaret GROUP BY kullanici_id"):
        if zaman and (kid not in sonuc or zaman > sonuc[kid]):
            sonuc[kid] = zaman
    return sonuc


def _kume_haritasi(conn: sqlite3.Connection) -> dict[int, list[str]]:
    harita: dict[int, set[str]] = {}
    for kid, rol in conn.execute("SELECT kullanici_id, rol FROM kullanici_gorev").fetchall():
        harita.setdefault(kid, set()).add(rol)
    return {kid: [r for r in yetki.ROLLER if r in kume] for kid, kume in harita.items()}


def _ekip_karti(satir: dict, kume: list[str], obekler: list[dict], son: str | None, maskeli: bool) -> dict:
    return {**_kullanici_kart(satir, kume, maskeli=maskeli), **_davet_durumu(satir),
            "obekler": obekler, "son_etkinlik": son}


@yonlendirici.get("/api/kullanici")
def kullanici_listesi(k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    """Ekip listesi. ``davet_kodu`` artık DÖNMEZ; telefon maskeli (tam hâli tek kişi yanıtında)."""
    satirlar = conn.execute("SELECT * FROM kullanici ORDER BY rol DESC, bolge, id").fetchall()
    kumeler, obekler, son = _kume_haritasi(conn), _obek_sahiplikleri(conn), _son_etkinlikler(conn)
    kisiler = []
    for s in satirlar:
        s = dict(s)
        kisiler.append(_ekip_karti(s, kumeler.get(s["id"], [s["rol"]]), obekler.get(s["id"], []),
                                   son.get(s["id"]), maskeli=True))
    return {"kullanicilar": kisiler, "gorevler": [{"rol": r, "etiket": yetki.ETIKET[r],
                                                   "aciklama": yetki.ACIKLAMA[r]} for r in yetki.ROLLER]}


@yonlendirici.get("/api/kullanici/{kullanici_id}")
def kullanici_getir(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    s = dict(satir)
    return {"kullanici": _ekip_karti(s, yetki.gorev_kumesi_oku(conn, s),
                                     _obek_sahiplikleri(conn).get(s["id"], []),
                                     _son_etkinlikler(conn).get(s["id"]), maskeli=False)}


def _yeni_davet(conn: sqlite3.Connection, kid: int) -> str:
    kod = guvenlik.davet_kodu_uret()
    conn.execute("UPDATE kullanici SET davet_kodu=?, davet_zamani=? WHERE id=?",
                 (kod, ayarlar.zaman_metni(), kid))
    return kod


# ----------------------------------------------------------------------------- v9: unvan + yetkinlik modeli
# Çağıran yetki modelindeyse (göçten geçmiş herkes, Administrator) kişinin erişimi UNVANDAN (+ Administrator'ın
# verdiği ek yetkinlikten) gelir. Kişi yönetimi (İK) kişi ekler/çıkarır, unvan ve takım lideri atar; görev/
# yetkinlik değiştiremez, Administrator'ı düzenleyemez/silemez. Eski (görev kümesi) çağıranın yolu değişmedi.
_ADMIN_KORUMALI = "Administrator hesabını yalnız Administrator düzenler."
_YETKINLIK_ADMIN = "Görevler unvandan gelir. Yetkinlik vermeyi yalnız Administrator yapar; uygun unvanı seçin."


def administrator_koru(k: dict, satir) -> None:
    """Hedef Administrator ise ve çağıran Administrator değilse 403 ``administrator_korumali``."""
    if yetki.administrator_mi(satir) and not k.get("administrator"):
        raise hata(403, _ADMIN_KORUMALI, "administrator_korumali")


def yeni_model_mi(k: dict) -> bool:
    return bool(k.get("_turetildi"))


def unvan_bul(conn: sqlite3.Connection, unvan_id: int | None = None, metin: str | None = None):
    """Katalogdan unvan satırı (id ya da ada göre, Türkçe/boşluk duyarsız). Tablo yoksa None."""
    try:
        if unvan_id is not None:
            return conn.execute("SELECT id, ad, aktif FROM unvan WHERE id=?", (unvan_id,)).fetchone()
        anahtar = yetki.unvan_anahtari(metin)
        if not anahtar:
            return None
        return conn.execute("SELECT id, ad, aktif FROM unvan WHERE ad_k=?", (anahtar,)).fetchone()
    except sqlite3.OperationalError:
        return None


def _unvan_coz(conn: sqlite3.Connection, girdi: KullaniciGirdi, varsa: dict | None) -> tuple[int | None, str | None]:
    """(unvan_id, unvan metni). Yeni atamada unvan katalogda ve aktif olmalı (pasif olan yalnız korunur)."""
    verilen = girdi.model_fields_set
    simdiki = (varsa or {}).get("unvan_id")
    if "unvan_id" in verilen:
        if girdi.unvan_id is None:
            return None, None
        satir = unvan_bul(conn, unvan_id=girdi.unvan_id)
    elif "unvan" in verilen:
        if not (girdi.unvan or "").strip():
            return None, None
        satir = unvan_bul(conn, metin=girdi.unvan)
        if satir is None:
            raise hata(400, "Bu unvan katalogda yok. Yeni unvanı Administrator açar.", "unvan_yok")
    else:
        return simdiki, (varsa or {}).get("unvan")
    if satir is None:
        raise hata(400, "Unvan bulunamadı.", "unvan_yok")
    if not satir["aktif"] and satir["id"] != simdiki:
        raise hata(400, "Bu unvan pasif; kişiye yeni atanamaz.", "unvan_pasif")
    return int(satir["id"]), satir["ad"]


def ek_yetkinlik_yaz(conn: sqlite3.Connection, kid: int, kodlar) -> None:
    conn.execute("DELETE FROM kullanici_yetkinlik WHERE kullanici_id=?", (kid,))
    conn.executemany("INSERT INTO kullanici_yetkinlik (kullanici_id, yetkinlik) VALUES (?,?)",
                     [(kid, y) for y in yetki.yetkinlik_sirala(kodlar)])


def yetki_modeline_al(conn: sqlite3.Connection, satir: dict) -> None:
    """Eski modeldeki kişiyi erişimi değişmeden yeni modele alır (v9 göçünün tek kişilik hâli)."""
    if int(satir.get("yetki_modeli") or 0):
        return
    unvandan = set(yetki.unvan_yetkinlikleri(conn, satir.get("unvan_id")))
    ek = set(yetki.gorev_paketleri(yetki.gorev_kumesi_oku(conn, satir))) - unvandan
    ek_yetkinlik_yaz(conn, satir["id"], ek)
    conn.execute("UPDATE kullanici SET yetki_modeli=1 WHERE id=?", (satir["id"],))
    satir["yetki_modeli"] = 1


def _kaydet_yetki_modeli(girdi: KullaniciGirdi, k: dict, conn: sqlite3.Connection) -> dict:
    """``POST /api/kullanici`` — yetki modelindeki çağıran (İK ya da Administrator)."""
    admin = bool(k.get("administrator"))
    verilen = girdi.model_fields_set
    ham_tel = (girdi.telefon or "").strip()
    telefon = _telefon_veya_hata(ham_tel) if ham_tel else None
    if telefon:
        if telefon == yetki.administrator_ayari()["telefon"] and not admin:
            raise hata(403, _ADMIN_KORUMALI, "administrator_korumali")
        if conn.execute("SELECT id FROM kullanici WHERE telefon=? AND id IS NOT ?", (telefon, girdi.id)).fetchone():
            raise hata(409, "Bu telefon numarası başka bir kullanıcıda kayıtlı.", "telefon_var")
    gorev_istendi = bool({"rol", "gorevler"} & verilen)
    kume_istenen = _kume_coz(girdi.rol, girdi.gorevler) if gorev_istendi else None

    varsa = None
    if girdi.id:
        varsa = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.id,)).fetchone()
        if not varsa:
            raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
        varsa = dict(varsa)
        administrator_koru(k, varsa)
    unvan_id, unvan_metni = _unvan_coz(conn, girdi, varsa)
    tl = (1 if girdi.takim_lideri else 0) if "takim_lideri" in verilen else int((varsa or {}).get("takim_lideri") or 0)

    davet = None
    oturum_dustu = False
    if varsa:
        kid = varsa["id"]
        kume_once = yetki.gorev_kumesi_oku(conn, varsa)
        if kid == k["id"] and not admin:
            if unvan_id != varsa.get("unvan_id") or tl != int(varsa.get("takim_lideri") or 0) or (
                    gorev_istendi and kume_istenen != kume_once):
                raise hata(409, "Kendi unvanınızı ve görevinizi değiştiremezsiniz.", "kendi_rolu")
        if kid == k["id"] and not girdi.aktif:
            raise hata(409, "Kendinizi silemez ya da pasife alamazsınız.", "kendini_silemez")
        if gorev_istendi and kume_istenen != kume_once and not admin:
            raise hata(403, _YETKINLIK_ADMIN, "yetkinlik_admin")
        if not girdi.aktif and _son_yonetici_mi(conn, varsa, kume_once):
            raise hata(409, _SON_YONETICI, "son_yonetici")
        yetki_modeline_al(conn, varsa)
        alanlar = {
            "ad": girdi.ad.strip(), "telefon": telefon, "aktif": 1 if girdi.aktif else 0,
            "etiket": json.dumps(girdi.etiket, ensure_ascii=False) if "etiket" in verilen and girdi.etiket is not None
            else (None if "etiket" in verilen else varsa.get("etiket")),
            "boss_ekip": ((girdi.boss_ekip or "").strip() or None) if "boss_ekip" in verilen else varsa.get("boss_ekip"),
            "kapasite": girdi.kapasite if "kapasite" in verilen else varsa.get("kapasite"),
            "unvan": unvan_metni, "unvan_id": unvan_id, "takim_lideri": tl,
        }
        degisen = sorted(a for a, v in alanlar.items() if v != varsa.get(a))
        conn.execute(
            "UPDATE kullanici SET ad=?, telefon=?, aktif=?, etiket=?, boss_ekip=?, kapasite=?, unvan=?, unvan_id=?, "
            "takim_lideri=? WHERE id=?",
            (alanlar["ad"], alanlar["telefon"], alanlar["aktif"], alanlar["etiket"], alanlar["boss_ekip"],
             alanlar["kapasite"], alanlar["unvan"], alanlar["unvan_id"], alanlar["takim_lideri"], kid))
        if gorev_istendi and admin and kume_istenen != kume_once:
            ek_yetkinlik_yaz(conn, kid, set(yetki.gorev_paketleri(kume_istenen))
                             - set(yetki.unvan_yetkinlikleri(conn, unvan_id)))
    else:
        davet = guvenlik.davet_kodu_uret() if telefon else None
        kid = int(conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, davet_zamani, rol, bolge, aktif, olusturma, "
            "etiket, boss_ekip, kapasite, unvan, kaynak, unvan_id, takim_lideri, yetki_modeli) "
            "VALUES (?,?,NULL,?,?,?,NULL,?,?,?,?,?,?,'elle',?,?,1)",
            (girdi.ad.strip(), telefon, davet, ayarlar.zaman_metni() if davet else None,
             girdi.rol if girdi.rol in yetki.ROLLER else "satisci", 1 if girdi.aktif else 0, ayarlar.zaman_metni(),
             json.dumps(girdi.etiket, ensure_ascii=False) if girdi.etiket else None,
             (girdi.boss_ekip or "").strip() or None, girdi.kapasite, unvan_metni, unvan_id, tl)).lastrowid)
        kume_once = []
        if gorev_istendi:
            if admin:
                ek_yetkinlik_yaz(conn, kid, set(yetki.gorev_paketleri(kume_istenen))
                                 - set(yetki.unvan_yetkinlikleri(conn, unvan_id)))
            elif not set(kume_istenen) <= set(yetki.gorevler_turet(yetki.unvan_yetkinlikleri(conn, unvan_id))):
                raise hata(403, _YETKINLIK_ADMIN, "yetkinlik_admin")
    kume = yetki.gorev_onbellegi_yaz(conn, kid)["sonra"]
    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
    turetilen = yetki.erisim(conn, satir)["gorevler"]
    bolge_girdi = girdi.bolge if ("bolge" in verilen or not varsa) else varsa.get("bolge")
    bolge = _bolge_coz(conn, turetilen, bolge_girdi)
    conn.execute("UPDATE kullanici SET bolge=? WHERE id=?", (bolge, kid))
    if varsa:
        neden = None
        if kume != kume_once:
            neden = "gorev"
        elif (bolge or 0) != (varsa["bolge"] or 0):
            neden = "bolge"
        elif bool(girdi.aktif) != bool(varsa["aktif"]):
            neden = "pasif"
        elif varsa["telefon"] and not telefon:
            neden = "cihaz"
        oturum_dustu = neden is not None
        if oturum_dustu:
            conn.execute("UPDATE kullanici SET oturum_no=oturum_no+1, oturum_neden=? WHERE id=?", (neden, kid))
        if telefon and not varsa["telefon"] and not varsa.get("pin_hash"):
            davet = _yeni_davet(conn, kid)
        ozet = {"alanlar": degisen, "oturum_dustu": oturum_dustu}
        if kume != kume_once:
            ozet["gorev"] = {"once": kume_once, "sonra": kume}
        eylem = "gorev" if kume != kume_once else ("pasif" if (varsa["aktif"] and not girdi.aktif) else "kisi_duzenle")
        db.yonetim_kaydi(conn, k, eylem, f"kullanici:{kid}", ozet)
    else:
        db.yonetim_kaydi(conn, k, "kisi_ekle", f"kullanici:{kid}",
                         {"gorevler": kume, "giris_var": bool(telefon), "unvan_id": unvan_id})
    conn.commit()
    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
    yanit = {"kullanici": _kullanici_kart(satir, yetki.gorev_kumesi_oku(conn, satir)),
             "davet_kodu": davet, "oturum_dustu": oturum_dustu}
    if davet:
        yanit["davet_gecerlilik_saat"] = ayarlar.DAVET_GECERLILIK_SAAT
    return yanit


@yonlendirici.post("/api/kullanici")
def kullanici_kaydet(
    girdi: KullaniciGirdi,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    if yeni_model_mi(k):
        return _kaydet_yetki_modeli(girdi, k, conn)
    ham_tel = (girdi.telefon or "").strip()
    telefon = _telefon_veya_hata(ham_tel) if ham_tel else None
    kume = _kume_coz(girdi.rol, girdi.gorevler)
    bolge = _bolge_coz(conn, kume, girdi.bolge)
    verilen = girdi.model_fields_set

    if telefon:
        cakisma = conn.execute(
            "SELECT id FROM kullanici WHERE telefon=? AND id IS NOT ?", (telefon, girdi.id)
        ).fetchone()
        if cakisma:
            raise hata(409, "Bu telefon numarası başka bir kullanıcıda kayıtlı.", "telefon_var")

    davet = None
    oturum_dustu = False
    if girdi.id:
        varsa = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.id,)).fetchone()
        if not varsa:
            raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
        varsa = dict(varsa)
        administrator_koru(k, varsa)
        kume_once = yetki.gorev_kumesi_oku(conn, varsa)
        gorev_degisti = girdi.rol != varsa["rol"] or kume != kume_once
        if varsa["id"] == k["id"]:
            if gorev_degisti:
                raise hata(409, "Kendi görevinizi değiştiremezsiniz.", "kendi_rolu")
            if not girdi.aktif:
                raise hata(409, "Kendinizi silemez ya da pasife alamazsınız.", "kendini_silemez")
        if (not girdi.aktif or "yonetici" not in kume) and _son_yonetici_mi(conn, varsa, kume_once):
            raise hata(409, _SON_YONETICI, "son_yonetici")
        # Hesap kapatılınca / görev ya da bölge değişince O KİŞİNİN BÜTÜN CİHAZLARI DÜŞER.
        # Eskiden "pasife al, sonra tekrar aktif et" eski jetonu yeniden geçerli kılıyordu.
        # Tekrar aktif etmek de oturumu düşürür: kapatılmadan önceki jeton yine GEÇERSİZ kalmalı.
        neden = None
        if gorev_degisti:
            neden = "gorev"
        elif (bolge or 0) != (varsa["bolge"] or 0):
            neden = "bolge"
        elif bool(girdi.aktif) != bool(varsa["aktif"]):
            neden = "pasif"
        elif varsa["telefon"] and not telefon:
            # Ek-2: telefonu silinen kişi girişsiz olur; elindeki açık oturum da kapanmalı.
            neden = "cihaz"
        oturum_dustu = neden is not None
        alanlar = {
            "ad": girdi.ad.strip(), "telefon": telefon, "rol": girdi.rol, "bolge": bolge,
            "aktif": 1 if girdi.aktif else 0,
            "etiket": json.dumps(girdi.etiket, ensure_ascii=False) if "etiket" in verilen and girdi.etiket is not None
            else (None if "etiket" in verilen else varsa.get("etiket")),
            "boss_ekip": ((girdi.boss_ekip or "").strip() or None) if "boss_ekip" in verilen else varsa.get("boss_ekip"),
            "kapasite": girdi.kapasite if "kapasite" in verilen else varsa.get("kapasite"),
            "unvan": ((girdi.unvan or "").strip() or None) if "unvan" in verilen else varsa.get("unvan"),
        }
        degisen = sorted(a for a, v in alanlar.items() if v != varsa.get(a))
        conn.execute(
            "UPDATE kullanici SET ad=?, telefon=?, rol=?, bolge=?, aktif=?, etiket=?, boss_ekip=?, kapasite=?, "
            "unvan=?, oturum_no=oturum_no+?, oturum_neden=COALESCE(?, oturum_neden) WHERE id=?",
            (alanlar["ad"], alanlar["telefon"], alanlar["rol"], alanlar["bolge"], alanlar["aktif"],
             alanlar["etiket"], alanlar["boss_ekip"], alanlar["kapasite"], alanlar["unvan"],
             1 if oturum_dustu else 0, neden, girdi.id),
        )
        _kume_yaz(conn, girdi.id, kume)
        # Girişsiz kişiye telefon eklendi: bugünkü davet akışı çalışır (kod yalnız bu yanıtta).
        if telefon and not varsa["telefon"] and not varsa.get("pin_hash"):
            davet = _yeni_davet(conn, girdi.id)
        # Yalnız DEĞİŞEN ALANIN ADI yazılır; telefonun kendisi yazılmaz.
        ozet = {"alanlar": degisen, "oturum_dustu": oturum_dustu}
        if gorev_degisti:
            ozet["gorev"] = {"once": kume_once, "sonra": kume, "ana_once": varsa["rol"], "ana_sonra": girdi.rol}
        eylem = "gorev" if gorev_degisti else ("pasif" if (varsa["aktif"] and not girdi.aktif) else "kisi_duzenle")
        db.yonetim_kaydi(conn, k, eylem, f"kullanici:{girdi.id}", ozet)
        yeni_id = girdi.id
    else:
        davet = guvenlik.davet_kodu_uret() if telefon else None
        imlec = conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, davet_zamani, rol, bolge, aktif, olusturma, "
            "etiket, boss_ekip, kapasite, unvan, kaynak) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,'elle')",
            (girdi.ad.strip(), telefon, davet, ayarlar.zaman_metni() if davet else None, girdi.rol, bolge,
             1 if girdi.aktif else 0, ayarlar.zaman_metni(),
             json.dumps(girdi.etiket, ensure_ascii=False) if girdi.etiket else None,
             (girdi.boss_ekip or "").strip() or None, girdi.kapasite, (girdi.unvan or "").strip() or None),
        )
        yeni_id = int(imlec.lastrowid)
        _kume_yaz(conn, yeni_id, kume)
        db.yonetim_kaydi(conn, k, "kisi_ekle", f"kullanici:{yeni_id}",
                         {"gorevler": kume, "giris_var": bool(telefon)})
    conn.commit()
    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (yeni_id,)).fetchone())
    yanit = {"kullanici": _kullanici_kart(satir, yetki.gorev_kumesi_oku(conn, satir)),
             "davet_kodu": davet, "oturum_dustu": oturum_dustu}
    if davet:
        yanit["davet_gecerlilik_saat"] = ayarlar.DAVET_GECERLILIK_SAAT
    return yanit


class GorevDegisikligi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    rol: str
    gorevler: list[str] | None = None
    bolge: int | None = None


class GorevlerGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    degisiklikler: list[GorevDegisikligi] = Field(default_factory=list, max_length=500)
    tamam: bool = False


@yonlendirici.post("/api/kullanici/gorevler")
def kullanici_gorevler(girdi: GorevlerGirdi, k: dict = Depends(izin("ekip.yonet")),
                       conn: sqlite3.Connection = Depends(baglanti)):
    """"Görevleri gözden geçirin" kartı: tek işlemde toplu görev değişikliği (spec §1.11-2)."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        degisen = 0
        for d in girdi.degisiklikler:
            satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (d.id,)).fetchone()
            if not satir:
                raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
            satir = dict(satir)
            administrator_koru(k, satir)
            kume = _kume_coz(d.rol, d.gorevler if d.gorevler is not None else None)
            bolge = _bolge_coz(conn, kume, d.bolge if d.bolge is not None else satir["bolge"], satir["ad"])
            kume_once = yetki.gorev_kumesi_oku(conn, satir)
            if d.rol == satir["rol"] and kume == kume_once and (bolge or 0) == (satir["bolge"] or 0):
                continue
            if satir["id"] == k["id"] and (d.rol != satir["rol"] or kume != kume_once):
                raise hata(409, "Kendi görevinizi değiştiremezsiniz.", "kendi_rolu")
            neden = "gorev" if (d.rol != satir["rol"] or kume != kume_once) else "bolge"
            if yeni_model_mi(k) and neden == "gorev":
                # Yetki modeli: görev kümesi yetkinliklerden türer. Administrator'ın görev seçimi ek yetkinliğe
                # çevrilir; İK görev değiştiremez (unvan seçer).
                if not k.get("administrator"):
                    raise hata(403, _YETKINLIK_ADMIN, "yetkinlik_admin")
                yetki_modeline_al(conn, satir)
                ek_yetkinlik_yaz(conn, d.id, set(yetki.gorev_paketleri(kume))
                                 - set(yetki.unvan_yetkinlikleri(conn, satir.get("unvan_id"))))
                sonra = yetki.gorev_onbellegi_yaz(conn, d.id)["sonra"]
                yeni = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (d.id,)).fetchone())
                bolge = _bolge_coz(conn, yetki.erisim(conn, yeni)["gorevler"],
                                   d.bolge if d.bolge is not None else satir["bolge"], satir["ad"])
                conn.execute("UPDATE kullanici SET bolge=?, oturum_no=oturum_no+1, oturum_neden='gorev' WHERE id=?",
                             (bolge, d.id))
                db.yonetim_kaydi(conn, k, "gorev", f"kullanici:{d.id}",
                                 {"once": kume_once, "sonra": sonra, "ana_once": satir["rol"], "ana_sonra": yeni["rol"]})
                degisen += 1
                continue
            conn.execute("UPDATE kullanici SET rol=?, bolge=?, oturum_no=oturum_no+1, oturum_neden=? WHERE id=?",
                         (d.rol, bolge, neden, d.id))
            _kume_yaz(conn, d.id, kume)
            db.yonetim_kaydi(conn, k, "gorev", f"kullanici:{d.id}",
                             {"once": kume_once, "sonra": kume, "ana_once": satir["rol"], "ana_sonra": d.rol})
            degisen += 1
        if _aktif_yoneticiler(conn) == 0:
            raise hata(409, _SON_YONETICI, "son_yonetici")
        if girdi.tamam:
            db.ayar_yaz(conn, "gorev_gozden_gecirildi", "1")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return {"degisen": degisen}


@yonlendirici.post("/api/kullanici/{kullanici_id}/davet")
def kullanici_davet(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    """Yeni 6 haneli davet kodu: 48 saat geçerli, YALNIZ bu yanıtta gösterilir."""
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    administrator_koru(k, satir)
    if not satir["telefon"]:
        raise hata(409, "Bu kişinin telefonu yok (girişsiz). Önce telefon ekleyin.", "telefon_yok")
    if satir["pin_hash"]:
        raise hata(409, "Bu kişinin PIN'i var. Unuttuysa 'PIN'i sıfırla'yı kullanın.", "pin_var")
    kod = _yeni_davet(conn, kullanici_id)
    db.yonetim_kaydi(conn, k, "davet", f"kullanici:{kullanici_id}")
    conn.commit()
    bitis = ayarlar.simdi() + dt.timedelta(hours=ayarlar.DAVET_GECERLILIK_SAAT)
    return {"davet_kodu": kod, "gecerlilik": f"{ayarlar.DAVET_GECERLILIK_SAAT} saat",
            "gecerlilik_bitis": ayarlar.zaman_metni(bitis)}


# Silme ilişki sayımında insanın okuyacağı karşılık (tablo.sütun → "312 ziyaret").
_ILISKI_ETIKETI = {
    "ziyaret.kullanici_id": "ziyaret",
    "ziyaret.iptal_eden_id": "iptal ettiği ziyaret",
    "bina_durum.son_kullanici_id": "binada son ziyaret kaydı",
    "gorev.kullanici_id": "görev listesi",
    "gorev.olusturan_id": "oluşturduğu görev listesi",
    "bolge_plani.olusturan_id": "bölge planı",
    "tur_raporu.yukleyen_id": "tur raporu yüklemesi",
    "tur_raporu.uygulayan_id": "tur raporu uygulaması",
    "ticket.olusturan_id": "ticket kaydı",
    "ticket_gecmis.kullanici_id": "ticket geçmişi kaydı",
    "is_emri.atanan_id": "iş emri",
    "obek.sahip_id": "öbeğin ev teknisyenliği",
    "obek.yedek_id": "öbeğin yedek teknisyenliği",
}
_OBEK_BAGLARI = ("obek.sahip_id", "obek.yedek_id")


def _kullanici_fklari(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """kullanici'ye giden BÜTÜN yabancı anahtarlar, dinamik (yeni tablolar kendiliğinden girer).

    ``kullanici_gorev`` engel sayılmaz: kişiyle birlikte silinir (ON DELETE CASCADE, Ek-1).
    """
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT m.name, p.\"from\" FROM sqlite_master m, pragma_foreign_key_list(m.name) p "
        "WHERE m.type='table' AND p.\"table\"='kullanici' "
        "AND m.name NOT IN ('kullanici','kullanici_gorev','kullanici_yetkinlik') "
        "ORDER BY m.name, p.\"from\"").fetchall()]


def _iliskiler(conn: sqlite3.Connection, satir: dict, k: dict) -> dict:
    kid = satir["id"]
    sayilar: dict[str, int] = {}
    for tablo, sutun in _kullanici_fklari(conn):
        n = conn.execute(f'SELECT COUNT(*) FROM "{tablo}" WHERE "{sutun}"=?', (kid,)).fetchone()[0]
        if n:
            sayilar[f"{tablo}.{sutun}"] = int(n)
    acik_is = 0
    try:
        acik_is = int(conn.execute(
            "SELECT COUNT(*) FROM is_emri WHERE atanan_id=? AND durum NOT IN ('cozuldu','kapandi')",
            (kid,)).fetchone()[0])
    except sqlite3.OperationalError:
        pass
    obek = sum(n for a, n in sayilar.items() if a in _OBEK_BAGLARI)
    diger = {a: n for a, n in sayilar.items() if a not in _OBEK_BAGLARI}
    # Gösterim verisi: demo ziyaretleri ve "Gösterim verisi" görev listeleri (spec §6.10).
    demo_ziyaret = int(conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE kullanici_id=? AND offline_id LIKE 'demo-%'", (kid,)).fetchone()[0])
    demo_gorev = int(conn.execute(
        "SELECT COUNT(*) FROM gorev WHERE kullanici_id=? AND notu='Gösterim verisi'", (kid,)).fetchone()[0])
    # Gösterim listelerini kişi "kendisi oluşturmuş" sayılır (olusturan_id = kişi): o bağ da gösterim verisidir.
    demo_olusturdugu = int(conn.execute(
        "SELECT COUNT(*) FROM gorev WHERE olusturan_id=? AND notu='Gösterim verisi'", (kid,)).fetchone()[0])
    demo_sayilari = {"ziyaret.kullanici_id": demo_ziyaret, "gorev.kullanici_id": demo_gorev,
                     "gorev.olusturan_id": demo_olusturdugu}
    # bina_durum.son_kullanici_id ziyaretlerden türer: ziyaretlerin hepsi gösterimse o da gösterimdir.
    hepsi_demo = bool(diger) and all(
        a == "bina_durum.son_kullanici_id" or (a in demo_sayilari and n == demo_sayilari[a])
        for a, n in diger.items())
    engeller = []
    if kid == k["id"]:
        engeller.append("kendini_silemez")
    if yetki.administrator_mi(satir):
        engeller.append("administrator")
    if _son_yonetici_mi(conn, satir, yetki.gorev_kumesi_oku(conn, satir)):
        engeller.append("son_yonetici")
    if diger:
        engeller.append("iliskili_kayit")
    return {
        "silinebilir": not engeller,
        "engeller": engeller,
        "sayilar": sayilar,
        "acik_is": acik_is,
        "obek_sahipligi": obek,
        "obekleri_birak_gerekli": obek > 0,
        "demo": demo_ziyaret + demo_gorev,
        "hepsi_demo": hepsi_demo,
        "etiketler": [{"metin": _ILISKI_ETIKETI.get(a, a.split(".")[0] + " kaydı"), "sayi": n}
                      for a, n in sayilar.items()],
    }


@yonlendirici.get("/api/kullanici/{kullanici_id}/iliskiler")
def kullanici_iliskileri(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                         conn: sqlite3.Connection = Depends(baglanti)):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    return _iliskiler(conn, dict(satir), k)


def _iliski_cumlesi(il: dict) -> str:
    parca = [f"{n} {e['metin']}" for e in il["etiketler"] for n in [e["sayi"]]
             if not e["metin"].startswith("öbeğin")]
    return ", ".join(parca) if parca else "ilişkili kayıtları"


@yonlendirici.delete("/api/kullanici/{kullanici_id}", status_code=204)
def kullanici_sil(kullanici_id: int, obekleri_birak: int = Query(default=0, ge=0, le=1),
                  k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    """Yalnız kaydı olmayan kişi silinir; kaydı olan pasife alınır (F13). Kontrol + silme TEK işlem."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
        if not satir:
            raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
        satir = dict(satir)
        if yetki.administrator_mi(satir):
            raise hata(403, "Administrator hesabı silinemez.", "administrator_korumali")
        il = _iliskiler(conn, satir, k)
        if "kendini_silemez" in il["engeller"]:
            raise hata(409, "Kendinizi silemez ya da pasife alamazsınız.", "kendini_silemez")
        if "son_yonetici" in il["engeller"]:
            raise hata(409, _SON_YONETICI, "son_yonetici")
        if "iliskili_kayit" in il["engeller"] or (il["obek_sahipligi"] and not obekleri_birak):
            detay = {"hata": f"Bu kişi silinemez: {_iliski_cumlesi(il)} var. Pasife alabilirsiniz."
                     if "iliskili_kayit" in il["engeller"]
                     else "Bu kişi öbeklerin teknisyeni. Öbekleri teknisyensiz bırakarak silmek için onaylayın.",
                     "kod": "iliskili_kayit", **{a: il[a] for a in ("sayilar", "etiketler", "acik_is",
                                                                    "obek_sahipligi", "hepsi_demo")}}
            raise HTTPException(status_code=409, detail=detay)
        birakilan = 0
        if il["obek_sahipligi"]:
            birakilan += conn.execute("UPDATE obek SET sahip_id=NULL WHERE sahip_id=?", (kullanici_id,)).rowcount
            birakilan += conn.execute("UPDATE obek SET yedek_id=NULL WHERE yedek_id=?", (kullanici_id,)).rowcount
        conn.execute("DELETE FROM kullanici_gorev WHERE kullanici_id=?", (kullanici_id,))
        try:
            conn.execute("DELETE FROM kullanici_yetkinlik WHERE kullanici_id=?", (kullanici_id,))
        except sqlite3.OperationalError:     # göç öncesi veritabanı
            pass
        if satir["telefon"]:
            conn.execute("DELETE FROM giris_denemesi WHERE telefon=?", (satir["telefon"],))
        conn.execute("DELETE FROM kullanici WHERE id=?", (kullanici_id,))
        db.yonetim_kaydi(conn, k, "kisi_sil", f"kullanici:{kullanici_id}",
                         {"gorevler": yetki.gorev_kumesi_oku(conn, satir) or [satir["rol"]],
                          "obek_birakildi": birakilan})
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise hata(409, "Bu kişi silinemez: başka kayıtlarla bağlantılı. Pasife alabilirsiniz.", "iliskili_kayit")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return Response(status_code=204)


class IsAktarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hedef_id: int


@yonlendirici.post("/api/kullanici/{kullanici_id}/is-aktar")
def kullanici_is_aktar(kullanici_id: int, girdi: IsAktarGirdi, k: dict = Depends(izin("ekip.yonet")),
                       conn: sqlite3.Connection = Depends(baglanti)):
    """Açık işleri başka bir teknik kişiye aktarır; her iş kendi olayıyla (``operasyon.v2.akis.ata``)."""
    kaynak_kisi = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if kaynak_kisi:
        administrator_koru(k, kaynak_kisi)
    hedef = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.hedef_id,)).fetchone()
    if (not hedef or not hedef["aktif"] or girdi.hedef_id == kullanici_id
            or "teknik" not in yetki.gorev_kumesi_oku(conn, dict(hedef))):
        raise hata(422, "Seçilen kişi aktif bir teknik görevli değil.", "teknik_gecersiz")
    try:
        from operasyon.v2 import akis
    except ImportError:
        raise hata(503, "İş emri modülü hazır değil.", "hazir_degil")
    import uuid

    toplu_id = uuid.uuid4().hex[:12]
    isler = conn.execute("SELECT is_no, surum FROM is_emri WHERE atanan_id=? "
                         "AND durum NOT IN ('cozuldu','kapandi') ORDER BY is_no", (kullanici_id,)).fetchall()
    aktarilan, atlanan = [], []
    if conn.in_transaction:
        conn.commit()
    for is_no, surum in isler:
        try:
            akis.ata(conn, is_no, girdi.hedef_id, k, surum=surum, yine_de=True, toplu_id=toplu_id, kaynak="elle")
            conn.commit()
            aktarilan.append(is_no)
        except Exception as exc:  # her iş kendi başına; biri takılırsa diğerleri sürer
            if conn.in_transaction:
                conn.rollback()
            atlanan.append({"is_no": is_no, "kod": getattr(exc, "kod", type(exc).__name__)})
    db.yonetim_kaydi(conn, k, "is_aktar", f"kullanici:{kullanici_id}",
                     {"hedef": f"kullanici:{girdi.hedef_id}", "aktarilan": len(aktarilan), "atlanan": len(atlanan),
                      "toplu_id": toplu_id})
    conn.commit()
    return {"toplu_id": toplu_id, "aktarilan": len(aktarilan), "atlanan": atlanan}


class AyarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    yardim_telefon: str | None = None
    yardim_ad: str | None = None


@yonlendirici.post("/api/ayar")
def ayar_kaydet(
    girdi: AyarGirdi,
    k: dict = Depends(izin("veri.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Giriş ekranında görünecek yardım numarası.

    Sözleşmede yok; "giriş yapamıyorum" diye takılan satışçının tek çaresi
    WhatsApp'a dönmek olmasın diye eklendi.
    """
    if girdi.yardim_telefon is not None:
        ham = girdi.yardim_telefon.strip()
        db.ayar_yaz(conn, "yardim_telefon", _telefon_veya_hata(ham) if ham else "")
    if girdi.yardim_ad is not None:
        db.ayar_yaz(conn, "yardim_ad", girdi.yardim_ad.strip()[:60])
    db.yonetim_kaydi(conn, k, "ayar", "ayar:yardim")
    conn.commit()
    return {"yardim_telefon": db.ayar_oku(conn, "yardim_telefon"),
            "yardim_ad": db.ayar_oku(conn, "yardim_ad"),
            "mesaj": "Yardım bilgisi kaydedildi."}


@yonlendirici.get("/api/ayar")
def ayar_oku_ucu(k: dict = Depends(izin("oturum")), conn: sqlite3.Connection = Depends(baglanti)):
    return {"yardim_telefon": db.ayar_oku(conn, "yardim_telefon"),
            "yardim_ad": db.ayar_oku(conn, "yardim_ad")}


@yonlendirici.post("/api/kullanici/{kullanici_id}/pin-sifirla")
def pin_sifirla(
    kullanici_id: int,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    administrator_koru(k, satir)
    if not satir["telefon"]:
        raise hata(409, "Bu kişinin telefonu yok (girişsiz). Önce telefon ekleyin.", "telefon_yok")
    kod = guvenlik.davet_kodu_uret()
    conn.execute(
        "UPDATE kullanici SET pin_hash=NULL, davet_kodu=?, davet_zamani=?, oturum_no=oturum_no+1, "
        "oturum_neden='pin' WHERE id=?",
        (kod, ayarlar.zaman_metni(), kullanici_id),
    )
    conn.execute("DELETE FROM giris_denemesi WHERE telefon=?", (satir["telefon"],))
    db.yonetim_kaydi(conn, k, "pin_sifirla", f"kullanici:{kullanici_id}")
    conn.commit()
    return {"kullanici_id": kullanici_id, "davet_kodu": kod,
            "gecerlilik": f"{ayarlar.DAVET_GECERLILIK_SAAT} saat",
            "mesaj": f"{satir['ad']} bu kodla yeni PIN belirleyecek."}


@yonlendirici.post("/api/kullanici/{kullanici_id}/cihaz-cikis")
def cihaz_cikis(
    kullanici_id: int,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Bu kişinin BÜTÜN cihazlarını çıkış yaptırır — PIN'i değiştirmeden.

    Telefon kaybolduğunda/çalındığında yapılacak ilk hareket budur: kişi kendi
    PIN'iyle yeni telefonundan hemen girebilir, kayıp cihazdaki 30 günlük jeton
    ise anında ölür. PIN sıfırlamak gereksiz yere satışçıyı sahada kilitliyordu
    (yeni PIN belirlemek için yöneticiden davet kodu beklemesi gerekiyordu).
    """
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    administrator_koru(k, satir)
    conn.execute("UPDATE kullanici SET oturum_no=oturum_no+1, oturum_neden='cihaz' WHERE id=?", (kullanici_id,))
    db.yonetim_kaydi(conn, k, "cihaz_cikis", f"kullanici:{kullanici_id}")
    conn.commit()
    return {
        "kullanici_id": kullanici_id,
        "pin_degismedi": True,
        "mesaj": f"{satir['ad']} adlı kişinin tüm cihazları çıkış yaptı. "
                 "Kendi PIN'iyle yeniden girebilir.",
    }


# ----------------------------------------------------------------------------- personel rehberi (Ek-2)
class RehberGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metin: str = Field(max_length=400_000)
    uygula: bool = False


class EslemeKurali(BaseModel):
    model_config = ConfigDict(extra="ignore")
    desen: str = Field(min_length=2, max_length=80)
    gorevler: list[str] = Field(min_length=1, max_length=4)


class EslemeGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    esleme: list[EslemeKurali] = Field(max_length=100)


def _ad_anahtari(metin: str) -> str:
    """Türkçe harf duyarsız karşılaştırma anahtarı (BOSS ekip eşleşmesiyle aynı işlev)."""
    try:
        from operasyon.is_emri import anahtar
    except ImportError:  # iş emri modülü yoksa aynı kuralın yalın hâli
        tablo = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUCGIIOSU")
        return "".join(ch for ch in str(metin).translate(tablo).upper() if ch.isalnum())
    return anahtar(metin)


def _esleme_oku(conn: sqlite3.Connection) -> list[dict]:
    try:
        esleme = json.loads(db.ayar_oku(conn, "unvan_gorev_esleme") or "null")
    except (TypeError, ValueError):
        esleme = None
    if not isinstance(esleme, list):
        esleme = sema_v2.UNVAN_GOREV_ESLEME
    return [e for e in esleme if isinstance(e, dict) and e.get("desen") and e.get("gorevler")]


def _unvan_gorevleri(esleme: list[dict], unvan: str) -> list[str] | None:
    """İlk eşleşen kural kazanır; kümenin ilk görevi ANA görevdir."""
    anahtar = _ad_anahtari(unvan)
    for kural in esleme:
        if _ad_anahtari(kural["desen"]) and _ad_anahtari(kural["desen"]) in anahtar:
            return [r for r in kural["gorevler"] if r in yetki.ROLLER] or None
    return None


# Atmosfer/Pusula "Çalışanlar" listesinden kopyalanan metindeki gürültü satırları.
_REHBER_GURULTU = {"CALISANLAR", "CALISAN", "ARA", "TUMU", "PROFILIGOR", "PROFILIGORUNTULE", "DAHAFAZLA",
                   "MESAJGONDER", "EPOSTA", "TELEFON", "UNVAN", "ADSOYAD", "BIRIM", "DEPARTMAN"}
_UNVAN_SOZCUKLERI = ("MUDUR", "SORUMLU", "UZMAN", "LIDER", "KOORDINATOR", "DANISMAN", "TEMSILCI", "ASISTAN",
                     "SEF", "TEKNISYEN", "OPERATOR", "DIREKTOR", "SEKRETER", "STAJYER", "STOK", "IDARI",
                     "FINANS", "MUHASEBE", "INSANKAYNAKLARI", "YAYILIM", "DESTEK", "YONETICI", "SORUMLUSU",
                     "ELEMANI", "PERSONEL", "MUHENDIS")


def _unvan_satiri_mi(satir: str, esleme: list[dict]) -> bool:
    anahtar = _ad_anahtari(satir)
    if any(_ad_anahtari(k["desen"]) in anahtar for k in esleme):
        return True
    return " - " in satir or "-" in satir.replace(" ", "")[1:-1] or any(s in anahtar for s in _UNVAN_SOZCUKLERI)


def _ad_satiri_mi(satir: str) -> bool:
    kelimeler = satir.split()
    if not 2 <= len(kelimeler) <= 5:
        return False
    return all(any(ch.isalpha() for ch in w) and (w[0].isupper() or not w[0].isalpha())
               and sum(ch.isdigit() for ch in w) == 0 for w in kelimeler)


def rehber_coz(metin: str, esleme: list[dict]) -> tuple[list[dict], int]:
    """Yapıştırılan metin → [{ad, unvan}] (ad satırı + unvan satırı çiftleri) ve okunamayan satır sayısı."""
    satirlar = [" ".join(s.split()) for s in (metin or "").splitlines()]
    satirlar = [s for s in satirlar if s]
    kisiler: list[dict] = []
    okunamayan = 0
    i = 0
    while i < len(satirlar):
        s = satirlar[i]
        a = _ad_anahtari(s)
        if (a in _REHBER_GURULTU or "@" in s or not any(ch.isalpha() for ch in s)
                or (len(s) <= 3 and s.isupper())):
            i += 1
            continue
        if _ad_satiri_mi(s) and not _unvan_satiri_mi(s, esleme):
            sonraki = satirlar[i + 1] if i + 1 < len(satirlar) else ""
            if sonraki and _unvan_satiri_mi(sonraki, esleme):
                kisiler.append({"ad": s, "unvan": sonraki})
                i += 2
                continue
            kisiler.append({"ad": s, "unvan": None})
            i += 1
            continue
        okunamayan += 1
        i += 1
    return kisiler, okunamayan


@yonlendirici.post("/api/kullanici/rehber")
def kullanici_rehber(girdi: RehberGirdi, k: dict = Depends(izin("ekip.yonet")),
                     conn: sqlite3.Connection = Depends(baglanti)):
    """Personel rehberi (Atmosfer/Pusula "Çalışanlar" listesi) içe aktarımı: önce önizleme, sonra uygula.

    * Ad mevcut bir kişiyle eşleşirse yalnız ``unvan`` yazılır (görevine dokunulmaz).
    * Eşleşmez ve unvan bir göreve eşlenirse GİRİŞSİZ kişi açılır (telefon yok, ``kaynak='rehber'``).
    * Göreve eşlenmeyen unvanlar alınmaz, sayısı raporlanır. İki kez uygulamak çift kayıt üretmez.
    """
    esleme = _esleme_oku(conn)
    yeni = yeni_model_mi(k)
    kisiler, okunamayan = rehber_coz(girdi.metin, esleme)
    mevcut: dict[str, dict] = {}
    for r in conn.execute("SELECT id, ad, unvan FROM kullanici").fetchall():
        mevcut.setdefault(_ad_anahtari(r["ad"]), dict(r))
    eklenecek, guncellenecek, atlanacak, ayni = [], [], [], 0
    gorulen: set[str] = set()
    for kisi in kisiler:
        anahtar = _ad_anahtari(kisi["ad"])
        if not anahtar or anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        var = mevcut.get(anahtar)
        if var:
            if kisi["unvan"] and kisi["unvan"] != (var["unvan"] or None):
                guncellenecek.append({"id": var["id"], "ad": var["ad"], "unvan_eski": var["unvan"],
                                      "unvan": kisi["unvan"]})
            else:
                ayni += 1
            continue
        gorevler = _unvan_gorevleri(esleme, kisi["unvan"]) if kisi["unvan"] else None
        katalog = unvan_bul(conn, metin=kisi["unvan"]) if (yeni and kisi["unvan"]) else None
        if yeni:
            # Yetki modeli: kişi katalogdaki (aktif) unvanıyla açılır; görevi unvanın yetkinliklerinden türer.
            if katalog is None or not katalog["aktif"]:
                atlanacak.append({"ad": kisi["ad"], "unvan": kisi["unvan"],
                                  "neden": "unvan_katalogda_yok" if kisi["unvan"] else "unvan_yok"})
                continue
            gorevler = yetki.gorevler_turet(yetki.unvan_yetkinlikleri(conn, katalog["id"])) or ["satisci"]
            eklenecek.append({"ad": kisi["ad"], "unvan": katalog["ad"], "unvan_id": katalog["id"],
                              "gorevler": gorevler, "rol": gorevler[0]})
            continue
        if not gorevler:
            atlanacak.append({"ad": kisi["ad"], "unvan": kisi["unvan"],
                              "neden": "gorev_yok" if kisi["unvan"] else "unvan_yok"})
            continue
        eklenecek.append({"ad": kisi["ad"], "unvan": kisi["unvan"], "gorevler": gorevler, "rol": gorevler[0]})

    sonuc = {"okunan": len(kisiler), "okunamayan_satir": okunamayan, "ayni": ayni,
             "eklenecek": eklenecek, "guncellenecek": guncellenecek, "atlanacak": atlanacak,
             "sayilar": {"eklenecek": len(eklenecek), "guncellenecek": len(guncellenecek),
                         "atlanacak": len(atlanacak), "ayni": ayni},
             "uygulandi": False}
    if not girdi.uygula:
        return sonuc

    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        simdi = ayarlar.zaman_metni()
        for g in guncellenecek:
            if not yeni:
                conn.execute("UPDATE kullanici SET unvan=? WHERE id=?", (g["unvan"], g["id"]))
                continue
            hedef = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (g["id"],)).fetchone())
            if yetki.administrator_mi(hedef):
                continue
            katalog = unvan_bul(conn, metin=g["unvan"])
            yetki_modeline_al(conn, hedef)
            conn.execute("UPDATE kullanici SET unvan=?, unvan_id=? WHERE id=?",
                         (g["unvan"], katalog["id"] if katalog and katalog["aktif"] else hedef.get("unvan_id"), g["id"]))
            yetki.gorev_onbellegi_yaz(conn, g["id"])
        for e in eklenecek:
            if yeni:
                kid = conn.execute(
                    "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma, unvan, "
                    "kaynak, unvan_id, yetki_modeli) VALUES (?,NULL,NULL,NULL,?,NULL,1,?,?,'rehber',?,1)",
                    (e["ad"], e["rol"], simdi, e["unvan"], e["unvan_id"])).lastrowid
                yetki.gorev_onbellegi_yaz(conn, int(kid))
                continue
            kid = conn.execute(
                "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma, unvan, kaynak) "
                "VALUES (?,NULL,NULL,NULL,?,NULL,1,?,?,'rehber')",
                (e["ad"], e["rol"], simdi, e["unvan"])).lastrowid
            _kume_yaz(conn, int(kid), [r for r in yetki.ROLLER if r in e["gorevler"]])
        db.yonetim_kaydi(conn, k, "rehber_aktar", "kullanici:*", sonuc["sayilar"])
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    sonuc["uygulandi"] = True
    return sonuc


@yonlendirici.get("/api/kullanici/rehber/esleme")
def rehber_esleme_oku(k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    return {"esleme": _esleme_oku(conn),
            "gorevler": [{"rol": r, "etiket": yetki.ETIKET[r]} for r in yetki.ROLLER]}


@yonlendirici.put("/api/kullanici/rehber/esleme")
def rehber_esleme_yaz(girdi: EslemeGirdi, k: dict = Depends(izin("ekip.yonet")),
                      conn: sqlite3.Connection = Depends(baglanti)):
    if yeni_model_mi(k) and not k.get("administrator"):
        raise hata(403, "Unvan → görev eşlemesini yalnız Administrator değiştirir.", "yetkinlik_admin")
    kurallar = []
    for kural in girdi.esleme:
        gorevler = [r for r in yetki.ROLLER if r in set(kural.gorevler)]
        if not gorevler or len(gorevler) != len(set(kural.gorevler)):
            raise hata(400, _GOREV_METNI, "rol_hatali")
        # Kullanıcının yazdığı sıra korunur: ilk görev ana görevdir.
        kurallar.append({"desen": kural.desen.strip(), "gorevler": list(dict.fromkeys(kural.gorevler))})
    db.ayar_yaz(conn, "unvan_gorev_esleme", json.dumps(kurallar, ensure_ascii=False))
    db.yonetim_kaydi(conn, k, "ayar", "ayar:unvan_gorev_esleme", {"kural": len(kurallar)})
    conn.commit()
    return {"esleme": kurallar}
