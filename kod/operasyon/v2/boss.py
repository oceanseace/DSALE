"""BOSS canlı eşitleme (BOSS Yardımcısı eklentisi → sunucu).

Eklenti, kullanıcının kendi tarayıcısındaki BOSS oturumuyla Teknik Havuz listesini sayfa sayfa okur, görevleri
sade bir biçime çevirir ve ``POST /api/boss/esitle`` ile buraya yollar. Burada görevler Teknik Task Detay
Raporu'nun sütunlarına çevrilip AYNI aktarım hattından geçer (``aktarim.hazirla`` → fark → ``_uygula``): İşler,
Öbekler, İş haritası ve dağıtım rapor yüklenmiş gibi güncellenir; bizim alanlarımız ezilmez.

- Kimlik: sunucunun ürettiği eşleme kodu (veri dizininde ``boss_eslesme.json``), ``X-Eslesme-Kodu`` başlığında.
  BOSS'un oturum bilgisi buraya HİÇ gelmez.
- Kapanış: BOSS'ta kapalı durumdaki görev (Tamamlandı / İptal) her eşitlemede kapanır; listeden düşen açık iş
  yalnız eksiksiz bir anlık görüntüden (``tam``) sonra kapanır.
- Telefon yalnız ``ayar.musteri_tel='acik'`` iken yazılır (F21; sahibin kararıyla bir kez açılır: ``tel_varsayilan``);
  saklama süresi ``saklama.py``'dedir. Telefonlar ayrıca ayrıntı ucundan önden okunur (``iletisim_gerekli`` →
  eklenti → ``iletisim_yaz``).
- İş ayrıntısı (bütün sekmeler) yeni/değişen açık işlerde önden okunur ve kalıcı saklanır: yanıttaki ``detay_onden``
  → eklenti → ``POST /api/boss/detay-onden`` (``boss_detay.onden_yaz``); ilerleme ``durum``daki detay_tamam/toplam.
- Artımlı eşitleme: ``boss_iz`` (görev no → parmak izi); eklenti yalnız değişenleri yollar (``mod='fark'``).
- BOSS listesinin bütün alanları (görevin ``ham``ı) ``boss_ham.py``'de saklanır (GET /api/isler?ek=1); sade alan
  boş gelirse ``_HAM_YEDEK`` ham alandan doldurur.
Kişisel veri günlüğe yazılmaz; ``ayar.boss_son_esitleme`` yalnız sayı tutar.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path

from operasyon import is_emri as ie

from . import aktarim, aski, boss_detay, boss_yazma, ekip_uzlas, sozluk, zaman
from .hatalar import Catisma, Gecersiz, V2Hata
from .islem import islem

AZAMI_GOREV = 20000
BAGLI_SANIYE = 10 * 60                 # son eşitleme bu kadar yeniyse "bağlı"
YEDEK_ARALIK = dt.timedelta(minutes=30)
KOD_DOSYASI = "boss_eslesme.json"

# BOSS durumları (sade biçim) → raporun "Task Durumu" metni (aktarım hattının tanıdığı)
_RAPOR_DURUMU = {
    "ACIK": "Açık", "RANDEVUSUZ": "Açık", "RANDEVU ALINDI": "Açık", "BASLANDI": "Başlandı",
    "KONUM PAYLASILDI": "Konum paylaşıldı", "ASKIYA ALINDI": "Askıya alındı", "ERTELENDI": "Askıya alındı",
    "MERKEZE GONDERILDI": "Merkeze gönderildi",
}
KAPALI = {"TAMAMLANDI", "IPTAL EDILDI", "FOX TARAFINDAN IPTAL EDILDI", "BITIRILDI", "KAPALI", "KAPANDI", "IPTAL"}

# sade görev alanı → rapor sütunu
_SUTUN = {
    "task_no": aktarim.K["no"], "task_adi": aktarim.K["task"], "musteri_no": aktarim.K["musteri_no"],
    "musteri_adi": aktarim.K["musteri_adi"], "ekip": aktarim.K["ekip"], "adres": aktarim.K["adres"],
    "satis_kanali": aktarim.K["kanal"], "il": aktarim.K["il"], "ilce": aktarim.K["ilce"],
    "acilis": aktarim.K["baslangic"], "randevu_bas": aktarim.K["randevu_bas"], "randevu_bit": aktarim.K["randevu_bit"],
    "aski_nedeni": aktarim.K["aski"], "sl": aktarim.K["sl"], "sl_saat": aktarim.K["sl_saat"],
    "son_aciklama": aktarim.K["son_aciklama"], "merkeze": aktarim.K["merkeze"],
    "konum_tarihi": aktarim.K["konum_tarihi"], "basla_tarihi": aktarim.K["basla_tarihi"],
    "segment": "Segment", "urun": "Ürün", "kategori": "Kategori",
}
# Sade alan boş geldiyse BOSS'un ham alanından (eslem.js eşlemesi kaçırsa da: ör. "saleChannel" 06.10'a dek boştu)
_HAM_YEDEK = {"satis_kanali": ("saleChannel", "salesChannel"), "urun": ("productInfo",),
              "kategori": ("taskCategory",)}


def kapali_mi(durum) -> bool:
    s = ie.sade(durum or "")
    return s in KAPALI or s.startswith("IPTAL") or s.endswith("IPTAL EDILDI")


# ----------------------------------------------------------------------------- eşleme kodu
def _kod_yolu() -> Path:
    return aktarim.veri_dizini() / KOD_DOSYASI


def _sade_kod(kod) -> str:
    return re.sub(r"[^0-9]", "", str(kod or ""))


def eslesme_kodu(yenile: bool = False) -> str:
    """Kalıcı eşleme kodu ("1234-5678"); yoksa üretilir. ``yenile`` eski kodu geçersiz kılar."""
    yol = _kod_yolu()
    if not yenile and yol.exists():
        try:
            kod = json.loads(yol.read_text(encoding="utf-8")).get("kod")
            if len(_sade_kod(kod)) == 8:
                return kod
        except (OSError, ValueError):
            pass
    sayi = f"{secrets.randbelow(10 ** 8):08d}"
    kod = f"{sayi[:4]}-{sayi[4:]}"
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".yaziliyor")
    gecici.write_text(json.dumps({"kod": kod, "olusturma": zaman.metin()}), encoding="utf-8")
    gecici.replace(yol)
    return kod


def kod_dogru(kod) -> bool:
    gelen = _sade_kod(kod)
    if len(gelen) != 8 or not _kod_yolu().exists():
        return False
    return hmac.compare_digest(gelen, _sade_kod(eslesme_kodu()))


# ----------------------------------------------------------------------------- durum
def _ayar_json(conn, anahtar):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    try:
        return json.loads(r[0]) if r and r[0] else None
    except ValueError:
        return None


def _ayar_yaz(conn, anahtar, deger) -> None:
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
                 (anahtar, json.dumps(deger, ensure_ascii=False)))


def durum(conn: sqlite3.Connection) -> dict:
    son = _ayar_json(conn, "boss_son_esitleme") or {}
    an = son.get("zaman")
    bagli = bool(an) and (zaman.simdi() - zaman.oku(an)).total_seconds() < BAGLI_SANIYE
    sayilar = {r[0]: r[1] for r in conn.execute(
        "SELECT durum, COUNT(*) FROM is_emri WHERE kaynak='boss' AND durum NOT IN ('cozuldu','kapandi') GROUP BY durum")}
    return {"bagli": bagli, "son_esitleme": an, "acik_sayisi": sum(sayilar.values()), "durum_sayilari": sayilar,
            "tam": bool(son.get("tam")), "gelen": son.get("gelen", 0), "uyari": son.get("uyari"),
            "yeniden_acilan": son.get("yeniden_acilan", 0),
            "mod": son.get("mod", "tam"), "rapor_temizligi": _ayar_json(conn, "boss_rapor_temizligi"),
            "yazma": boss_yazma.durum_ozeti(conn), **iletisim_durumu(conn), **boss_detay.detay_durumu(conn)}


# ----------------------------------------------------------------------------- çeviri
def _metin(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        v = ", ".join(str(x) for x in v if x not in (None, ""))
    s = str(v).strip()
    return s or None


def _il_ilce_tahmin(ilce_h: dict, adres: str | None) -> tuple[str | None, str | None]:
    """JSON'da il/ilçe yoksa adresin sonundan ("… NİLÜFER/BURSA") bulunur."""
    if not adres:
        return None, None
    kelimeler = ie.sade(adres).split()
    adaylar = set(kelimeler) | {a + b for a, b in zip(kelimeler, kelimeler[1:])}
    il = "Yalova" if "YALOVA" in kelimeler and "BURSA" not in kelimeler else ("Bursa" if "BURSA" in kelimeler else None)
    il_k = ie.anahtar(il) if il else None
    bulunan = None
    for (ik, k), (_ck, il_ad, ilce_ad) in ilce_h.items():
        if ik in aktarim.BOLGE_IL_K and (il_k is None or ik == il_k) and k in adaylar:
            if bulunan is None or len(k) > len(ie.anahtar(bulunan[1])):
                bulunan = (il_ad, ilce_ad)
    if bulunan:
        return bulunan
    return il, None


def rapor_satirlari(conn, gorevler: list[dict]) -> list[dict]:
    """Sade görevler → Teknik Task Detay Raporu satırları (sütun adları birebir)."""
    ilce_h = sozluk.ilce_haritasi(conn)
    satirlar = []
    for g in gorevler:
        if not isinstance(g, dict):
            continue
        no = _metin(g.get("task_no"))
        if not no:
            continue
        s = {sutun: _metin(g.get(alan)) for alan, sutun in _SUTUN.items()}
        ham = g.get("ham") if isinstance(g.get("ham"), dict) else {}
        for alan, adlar in _HAM_YEDEK.items():
            if not s[_SUTUN[alan]]:
                s[_SUTUN[alan]] = next((_metin(ham.get(a)) for a in adlar if _metin(ham.get(a))), None)
        s[aktarim.K["no"]] = no
        bd = _metin(g.get("durum")) or "Açık"
        sd = ie.sade(bd)
        s[aktarim.K["durum"]] = bd if kapali_mi(bd) else _RAPOR_DURUMU.get(sd, "Açık")
        if sd == "ERTELENDI" and not s[aktarim.K["aski"]]:
            s[aktarim.K["aski"]] = "Ertelendi"
        randevulu = sd == "RANDEVU ALINDI" or bool(s[aktarim.K["randevu_bas"]])
        s[aktarim.K["randevu_durumu"]] = _metin(g.get("randevu_durumu")) or ("Randevulu" if randevulu else "Randevusuz")
        s[aktarim.K["lokasyon"]] = _metin(g.get("lokasyon")) or _metin(g.get("bina"))
        if not s[aktarim.K["task"]]:
            s[aktarim.K["task"]] = _metin(g.get("kategori")) or "—"
        if not s[aktarim.K["il"]] or not s[aktarim.K["ilce"]]:
            il, ilce = _il_ilce_tahmin(ilce_h, s[aktarim.K["adres"]])
            s[aktarim.K["il"]] = s[aktarim.K["il"]] or il
            s[aktarim.K["ilce"]] = s[aktarim.K["ilce"]] or ilce
        s[aktarim.K["adres"]] = s[aktarim.K["adres"]] or ""
        s["_BOSS Durumu"] = bd
        s["_telefon"] = [t for t in (g.get("telefonlar") or []) if t][:3] if isinstance(g.get("telefonlar"), list) \
            else ([g["telefon"]] if g.get("telefon") else [])
        satirlar.append(s)
    return satirlar


# ----------------------------------------------------------------------------- eşitle
def _son_yedek_eski(conn) -> bool:
    son = _ayar_json(conn, "boss_son_yedek")
    return not son or zaman.simdi() - zaman.oku(son) >= YEDEK_ARALIK


def _kapat_boss(b, r: sqlite3.Row, bd: str) -> None:
    b.conn.execute("UPDATE is_emri SET durum='kapandi', durum_zamani=?, kapanis=?, kapanis_kesin=1, "
                   "kapanis_nedeni='boss_kapandi', boss_durum=?, boss_kapanmadi=0, surum=surum+1, guncelleme=? "
                   "WHERE is_no=?", (b.simdi, b.simdi, bd, b.simdi, r["is_no"]))
    aski.kapat(b.conn, r["is_no"], b.simdi)
    aktarim._olay(b, r["is_no"], "kayboldu", {"durum": r["durum"]},
                  {"durum": "kapandi", "kapanis_nedeni": "boss_kapandi", "_surum": r["surum"] + 1},
                  notu=f"BOSS'ta {bd}")


def _randevulari_al(conn, simdi: str) -> int:
    """BOSS'ta randevusu olan, bizde randevusuz bekleyen iş → randevulu (BOSS'taki saatle, teyitli)."""
    n = 0
    for r in conn.execute("SELECT is_no, surum, boss_randevu_bas, boss_randevu_bit FROM is_emri WHERE kaynak='boss' "
                          "AND durum='bekliyor' AND randevu_bas IS NULL AND boss_randevu_bas IS NOT NULL").fetchall():
        conn.execute("UPDATE is_emri SET durum='randevulu', durum_zamani=?, randevu_bas=?, randevu_bit=?, "
                     "randevu_teyitli=1, surum=surum+1, guncelleme=? WHERE is_no=?",
                     (simdi, r["boss_randevu_bas"], r["boss_randevu_bit"] or r["boss_randevu_bas"], simdi, r["is_no"]))
        conn.execute("INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, tur, eski, yeni, notu) "
                     "VALUES (?,?,?,?,?,?,?)", (r["is_no"], simdi, simdi, "aktarim_degisti",
                                                json.dumps({"durum": "bekliyor"}),
                                                json.dumps({"durum": "randevulu", "_surum": r["surum"] + 1}),
                                                "BOSS'ta randevu alınmış"))
        n += 1
    return n


def _telefonlari_yaz(conn, satirlar: list[dict]) -> int:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone()
    if not r or r[0] != "acik":
        return 0
    from saha import guvenlik
    n = 0
    for s in satirlar:
        tel = next((t for t in (_tel10(x) for x in s["_telefon"]) if t), None)
        if tel:
            n += conn.execute("UPDATE is_emri SET musteri_tel=? WHERE boss_task_no=? AND musteri_tel IS NULL "
                              "AND durum NOT IN ('cozuldu','kapandi')", (tel, s[aktarim.K["no"]])).rowcount
    return n


def esitle(conn_fabrikasi, govde: dict) -> dict:
    """Eklentinin görüntüsü → iş deposu. Dönüş: sayılar (kişisel veri yok).

    İki biçim: ``mod='fark'`` (yalnız parmak izi değişen/yeni görevler + ``kaldirilan`` görev noları; eklenti önce
    ``GET /api/boss/izler`` ile sunucunun bildiğini alır) ya da eski tam biçim (bütün görevler)."""
    from operasyon.tembel import tembel
    pd = tembel("pandas")
    gorevler = govde.get("gorevler")
    if not isinstance(gorevler, list):
        raise Gecersiz("Görev listesi gerekli.", kod="alan_eksik")
    if len(gorevler) > AZAMI_GOREV:
        raise V2Hata("Çok fazla görev (en çok 20 000).", kod="buyuk_dosya", durum=413)
    fark_modu = govde.get("mod") == "fark"
    kaldirilan = govde.get("kaldirilan") if fark_modu else None
    if not isinstance(kaldirilan, list):
        kaldirilan = []
    kaldirilan = sorted({str(x).strip() for x in kaldirilan if str(x or "").strip()})[:AZAMI_GOREV]
    tam_istek = bool(govde.get("tam"))
    t0 = time.perf_counter()
    conn = conn_fabrikasi()
    try:
        from . import boss_detay
        iz_sema(conn)
        tel_varsayilan(conn)
        uuid_sayisi = boss_detay.uuid_yaz(conn, gorevler)
        ekip_sayisi = boss_detay.ekipler_yaz(conn, govde.get("ekipler"))
        if not aktarim._KILIT.acquire(blocking=False):
            raise Catisma("Şu an bir rapor işleniyor. Eklenti birazdan yeniden dener.", kod="aktarim_suruyor")
        try:
            onceki_iz = {r[0]: r[1] for r in conn.execute("SELECT task_no, iz FROM boss_iz")}
            onceki = set(onceki_iz)
            acik_once = _acik_boss_isleri(conn)
            gorulen = {str(g.get("task_no") or "").strip() for g in gorevler if isinstance(g, dict)}
            acik_nolar = {str(g.get("task_no") or "").strip() for g in gorevler
                          if isinstance(g, dict) and not kapali_mi(g.get("durum"))}
            temizlik = {"is": 0, "dagitim": 0}
            if tam_istek:
                if fark_modu:
                    temizlik = rapor_kalintisi(conn, kaldirilan=set(kaldirilan))
                elif acik_nolar:
                    temizlik = rapor_kalintisi(conn, gorulen=gorulen)
            if fark_modu:
                s = _esitle_fark(conn, pd, gorevler, kaldirilan, tam_istek, t0)
            else:
                s = _esitle(conn, pd, gorevler, tam_istek, t0)
            with islem(conn):
                _iz_yaz(conn, gorevler)
                if not fark_modu and s.get("tam"):
                    conn.executemany("UPDATE boss_iz SET acik=0 WHERE task_no=?",
                                     [(no,) for (no,) in conn.execute("SELECT task_no FROM boss_iz WHERE acik=1")
                                      if no not in gorulen])
            # sonucu gelmemiş BOSS yazmaları BOSS'un görüntüsünde yapılmış görünüyorsa ✓ (boss_yazma; 09.10 incelemesi)
            try:
                d = boss_yazma.boss_goruntusuyle_dogrula(conn)
                if d["atama"] or d["aski"]:
                    s["yazma_dogrulandi"] = d
            except Exception:  # noqa: BLE001 — bir sonraki eşitlemede yeniden denenir
                import logging
                logging.getLogger("operasyon.boss").exception("BOSS yazma doğrulaması yapılamadı")
            # BOSS ekip ataması kesin kaynak (ekip_uzlas.py): askı/merkeze ekibi işten alır, uygulama ataması uyar
            try:
                u = ekip_uzlas.uzlas(conn, aktarim_id=s.get("aktarim_id"))
                s["ekip_uzlasma"] = u["toplam"]
            except Exception:  # noqa: BLE001 — uzlaşma bir sonraki eşitlemede yeniden denenir
                import logging
                logging.getLogger("operasyon.boss").exception("Ekip uzlaşması yapılamadı")
            s["ham"] =_ham_yaz(conn, gorevler, bool(not fark_modu and s.get("tam")), kaldirilan)
            f = s.get("fark") or {}
            s["mod"] = "fark" if fark_modu else "tam"
            s["ozet"] = {"yeni": len(acik_nolar - onceki), "degisen": len(acik_nolar & onceki),
                         "kapanan": f.get("kapanan_boss", 0) + f.get("kaybolan", 0) + s.get("kaldirilan_kapanan", 0)
                         + temizlik["is"]}
            s["rapor_temizligi"] = temizlik
            # değişiklik akışı (GET /api/boss/farklar): yalnız görev noları; "değişen" = parmak izi değişen açık iş
            s["degisiklik"] = {
                "yeni": sorted(acik_nolar - onceki)[:EN_COK_FARK_NO],
                "degisen": sorted({str(g.get("task_no") or "").strip() for g in gorevler if isinstance(g, dict)
                                   and str(g.get("task_no") or "").strip() in (acik_nolar & onceki)
                                   and onceki_iz.get(str(g.get("task_no")).strip()) != _iz(g)})[:EN_COK_FARK_NO],
                "kapanan": sorted(acik_once - _acik_boss_isleri(conn))[:EN_COK_FARK_NO]}
            s["uuid"] = uuid_sayisi
            if ekip_sayisi is not None:
                s["ekip"] = ekip_sayisi
            s["iletisim"] = iletisim_gerekli(conn)
            try:                   # altyapı ticket askıları: süre dolmadan yeniden askı, kapanmış ticket'ta geri atama
                from saha import ticket_boss_aski
                y = ticket_boss_aski.yenile(conn)
                if y["yenilenen"] or y["cozulen"]:
                    s["ticket_aski"] = y
            except ImportError:
                pass
            try:
                s["detay_onden"] = boss_detay.detay_gerekli(conn)
                s.update(boss_detay.detay_durumu(conn))
            except Exception:      # noqa: BLE001 — önden okuma kolaylıktır, eşitlemeyi bozmaz
                import logging
                logging.getLogger("operasyon.boss").exception("Ayrıntı önden okuma listesi kurulamadı")
                s["detay_onden"] = []
            return s
        finally:
            aktarim._KILIT.release()
    finally:
        conn.close()


EN_COK_FARK_NO = 2000


def _acik_boss_isleri(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT boss_task_no FROM is_emri WHERE boss_task_no IS NOT NULL "
                                       "AND durum NOT IN ('cozuldu','kapandi')")}


def _ham_yaz(conn, gorevler, tam: bool, kaldirilan) -> int | None:
    """BOSS liste alanlarının hepsi (``boss_ham``; GET /api/isler?ek=1). Yazılamazsa eşitleme yine tamamdır."""
    from . import boss_ham
    try:
        return boss_ham.yaz(conn, gorevler, tam=tam, kaldirilan=kaldirilan)
    except Exception:          # noqa: BLE001
        import logging
        logging.getLogger("operasyon.boss").exception("BOSS ham alanları yazılamadı")
        return None


# ----------------------------------------------------------------------------- parmak izi (artımlı eşitleme)
IZ_SEMA = (
    "CREATE TABLE IF NOT EXISTS boss_iz (task_no TEXT PRIMARY KEY, iz TEXT NOT NULL, acik INTEGER NOT NULL DEFAULT 1, "
    "gorulme TEXT)",
    "CREATE TABLE IF NOT EXISTS boss_iletisim (task_no TEXT PRIMARY KEY, iz TEXT, zaman TEXT NOT NULL, "
    "telefon INTEGER NOT NULL DEFAULT 0)",
)
_IZ_ALANLARI = ("durum", "ekip", "randevu_bas", "randevu_bit", "guncelleme")
EN_COK_ILETISIM = 300
ILETISIM_HATA_SN = 10 * 60
NUMARASIZ_YENIDEN = dt.timedelta(hours=1)   # telefonu çıkmayan açık iş saatte bir yeniden okunur
_ILETISIM_HATA: dict[str, float] = {}      # task_no → son başarısız okuma (bellekte; hemen yeniden sorulmasın)


def iz_sema(conn) -> None:
    for q in IZ_SEMA:
        conn.execute(q)


def iz_hesapla(g: dict) -> str:
    """Eklentiyle aynı: durum|ekip|randevu_bas|randevu_bit|guncelleme (eklenti ``iz`` gönderirse o kullanılır)."""
    return "|".join(str(g.get(a) or "") for a in _IZ_ALANLARI)


def _iz(g: dict) -> str:
    iz = g.get("iz")
    return str(iz)[:300] if isinstance(iz, str) and iz else iz_hesapla(g)


def _iz_yaz(conn, gorevler: list) -> None:
    simdi = zaman.metin()
    conn.executemany(
        "INSERT INTO boss_iz(task_no, iz, acik, gorulme) VALUES(?,?,?,?) ON CONFLICT(task_no) DO UPDATE SET "
        "iz=excluded.iz, acik=excluded.acik, gorulme=excluded.gorulme",
        [(str(g["task_no"]).strip(), _iz(g), 0 if kapali_mi(g.get("durum")) else 1, simdi)
         for g in gorevler if isinstance(g, dict) and str(g.get("task_no") or "").strip()])


def izler(conn) -> dict:
    """Sunucunun açık bildiği görevler → parmak izi. İzi bilinmeyen (ör. eski Excel raporundan) açık işler "" ile
    döner: eklenti BOSS'ta göremezse ``kaldirilan``a koyar."""
    iz_sema(conn)
    d = {no: iz for no, iz in conn.execute("SELECT task_no, iz FROM boss_iz WHERE acik=1")}
    for (no,) in conn.execute("SELECT boss_task_no FROM is_emri WHERE boss_task_no IS NOT NULL "
                              "AND durum NOT IN ('cozuldu','kapandi')"):
        d.setdefault(no, "")
    try:
        for (no,) in conn.execute("SELECT task_no FROM dagitim_is WHERE acik=1"):
            d.setdefault(no, "")
    except sqlite3.OperationalError:
        pass
    bos = conn.execute("SELECT 1 FROM boss_iz LIMIT 1").fetchone() is None
    return {"izler": d, "tam_gerekli": bos}


def _kapat_listeden(conn, r: sqlite3.Row, simdi: str) -> None:
    conn.execute("UPDATE is_emri SET durum='kapandi', durum_zamani=?, kapanis=?, kapanis_kesin=0, "
                 "kapanis_nedeni='boss_listeden_dustu', boss_kapanmadi=0, surum=surum+1, guncelleme=? WHERE is_no=?",
                 (simdi, simdi, simdi, r["is_no"]))
    aski.kapat(conn, r["is_no"], simdi)
    conn.execute("INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, tur, eski, yeni, notu) VALUES (?,?,?,?,?,?,?)",
                 (r["is_no"], simdi, simdi, "kayboldu", json.dumps({"durum": r["durum"]}),
                  json.dumps({"durum": "kapandi", "kapanis_nedeni": "boss_listeden_dustu", "_surum": r["surum"] + 1}),
                  "BOSS listesinden düştü"))


def _esitle_fark(conn, pd, gorevler, kaldirilan, tam, t0) -> dict:
    """Artımlı: değişenler aktarım hattından (kaybolan hesabı kapalı), düşenler ``kaldirilan``dan kapanır."""
    if gorevler:
        s = _esitle(conn, pd, gorevler, False, t0)
    else:
        s = {"gelen": 0, "acik_gelen": 0, "kapali_gelen": 0, "tam": False, "fark": {"kapanan_boss": 0}, "uyari": None}
    simdi = zaman.metin()
    kapanan, uyari = 0, None
    k = set(kaldirilan)
    if tam and k:
        satirlar = [r for r in conn.execute("SELECT * FROM is_emri WHERE boss_task_no IS NOT NULL "
                                            "AND durum <> 'kapandi'") if r["boss_task_no"] in k]
        acik_say = conn.execute("SELECT COUNT(*) FROM is_emri WHERE boss_task_no IS NOT NULL "
                                "AND durum NOT IN ('cozuldu','kapandi')").fetchone()[0]
        esik = aktarim._ayar_json(conn, "aktarim_esik", {"kaybolan_oran": 0.25, "kaybolan_min": 50})
        sinir = max(int(esik.get("kaybolan_min", 50)), acik_say * float(esik.get("kaybolan_oran", 0.25)))
        if len(satirlar) > sinir:
            uyari = f"BOSS listesinde {len(satirlar)} açık iş yok; güvenlik için kapatılmadı."
        else:
            with islem(conn):
                for r in satirlar:
                    _kapat_listeden(conn, r, simdi)
                    kapanan += 1
                try:
                    conn.executemany("UPDATE dagitim_is SET acik=0 WHERE task_no=?", [(no,) for no in k])
                except sqlite3.OperationalError:
                    pass
                conn.executemany("UPDATE boss_iz SET acik=0 WHERE task_no=?", [(no,) for no in k])
    tam_oldu = bool(tam and not uyari)
    with islem(conn):
        if tam_oldu:
            conn.executemany("UPDATE is_emri SET son_gorulme=? WHERE is_no=?",
                             [(simdi, no) for no, bno in conn.execute(
                                 "SELECT is_no, boss_task_no FROM is_emri WHERE boss_task_no IS NOT NULL AND "
                                 "durum NOT IN ('cozuldu','kapandi')").fetchall() if bno not in k])
        _ayar_yaz(conn, "boss_son_esitleme", {"zaman": simdi, "tam": tam_oldu, "mod": "fark",
                                              "gelen": len(gorevler), "uyari": uyari or s.get("uyari"),
                                              "yeniden_acilan": (s.get("fark") or {}).get("yeniden_acilan", 0)})
    if kapanan:
        aktarim._sonrasi(conn)
    s.update(tam=tam_oldu, kaldirilan=len(k), kaldirilan_kapanan=kapanan, uyari=uyari or s.get("uyari"),
             sure_sn=round(time.perf_counter() - t0, 3))
    return s


# ----------------------------------------------------------------------------- eski rapor kalıntısı
def rapor_kalintisi(conn, gorulen: set | None = None, kaldirilan: set | None = None) -> dict:
    """Eksiksiz BOSS görüntüsünde OLMAYAN ve canlı eşitlemenin hiç görmediği (BOSS kimliği/izi yok) açık işler eski
    Excel raporundan kalmadır. Önce doğrulanmış yedek; sonra iş kapanır (kişisel alanlar silinir; olay kaydı
    silinemez olduğu için satır durur) ve ``dagitim_is`` (Mevcut/Yeni Müşteri) satırı silinir."""
    iz_sema(conn)
    bilinen = {r[0] for r in conn.execute("SELECT task_no FROM boss_iz")}
    try:
        bilinen |= {r[0] for r in conn.execute("SELECT task_no FROM boss_gorev_kimlik")}
    except sqlite3.OperationalError:
        pass

    def aday(no) -> bool:
        if not no or no in bilinen:
            return False
        return (no not in gorulen) if gorulen is not None else (no in (kaldirilan or ()))

    isler = [r for r in conn.execute("SELECT is_no, boss_task_no, durum, surum FROM is_emri WHERE boss_task_no IS NOT "
                                     "NULL AND durum NOT IN ('cozuldu','kapandi')").fetchall() if aday(r["boss_task_no"])]
    try:
        dag = [r[0] for r in conn.execute("SELECT task_no FROM dagitim_is WHERE acik=1").fetchall() if aday(r[0])]
    except sqlite3.OperationalError:
        dag = []
    if not isler and not dag:
        return {"is": 0, "dagitim": 0}
    try:
        yedek = aktarim.aktarim_yedegi(aktarim._db_yolu(conn))
    except Exception:      # noqa: BLE001
        raise V2Hata("Güvenlik yedeği alınamadı; eski rapor işleri temizlenmedi. Diskte yer var mı?",
                     kod="yedek_alinamadi", durum=503)
    simdi = zaman.metin()
    with islem(conn):
        for r in isler:
            conn.execute("UPDATE is_emri SET durum='kapandi', durum_zamani=?, kapanis=?, kapanis_kesin=0, "
                         "kapanis_nedeni='rapor_kalintisi', musteri_adi=NULL, adres=NULL, musteri_tel=NULL, "
                         "musteri_no=NULL, boss_kapanmadi=0, surum=surum+1, guncelleme=? WHERE is_no=?",
                         (simdi, simdi, simdi, r["is_no"]))
            aski.kapat(conn, r["is_no"], simdi)
            conn.execute("INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, tur, eski, yeni, notu) "
                         "VALUES (?,?,?,?,?,?,?)",
                         (r["is_no"], simdi, simdi, "kayboldu", json.dumps({"durum": r["durum"]}),
                          json.dumps({"durum": "kapandi", "kapanis_nedeni": "rapor_kalintisi",
                                      "_surum": r["surum"] + 1}),
                          "Eski Excel raporundan kalma; BOSS'ta yok"))
        conn.executemany("DELETE FROM dagitim_is WHERE task_no=?", [(no,) for no in dag])
        _ayar_yaz(conn, "boss_rapor_temizligi", {"zaman": simdi, "is": len(isler), "dagitim": len(dag),
                                                  "yedek": Path(yedek).name})
    aktarim._sonrasi(conn)
    return {"is": len(isler), "dagitim": len(dag), "yedek": Path(yedek).name}


# ----------------------------------------------------------------------------- müşteri telefonu (önden okuma)
def tel_varsayilan(conn) -> None:
    """Sahibin kararı: telefonlar saklanır. Bir kez ``musteri_tel='acik'`` yapılır; sonra elle kapatılırsa ezilmez."""
    if conn.execute("SELECT 1 FROM ayar WHERE anahtar='boss_tel_varsayilan'").fetchone():
        return
    with islem(conn):
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('musteri_tel','acik') "
                     "ON CONFLICT(anahtar) DO UPDATE SET deger='acik'")
        conn.execute("INSERT OR IGNORE INTO ayar(anahtar, deger) VALUES('boss_tel_varsayilan', ?)", (zaman.metin(),))


def _tel_acik(conn) -> bool:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone()
    return bool(r) and r[0] == "acik"


def _iletisim_unut(conn, task_nolar: list[str]) -> None:
    if not task_nolar:
        return
    from . import boss_detay
    boss_detay._sema(conn)
    conn.executemany("DELETE FROM boss_iletisim WHERE task_no=?", [(n,) for n in task_nolar])
    for n in task_nolar:
        _ILETISIM_HATA.pop(n, None)


def iletisim_gerekli(conn, en_cok: int = EN_COK_ILETISIM) -> list[dict]:
    """Telefonu okunacak açık işler: [{task_no, uuid}]. Yeni ya da izi değişmiş iş; telefonu çıkmamış (numarasız)
    iş ``NUMARASIZ_YENIDEN`` (1 saat) sonra yeniden. Ayar kapalıysa boş."""
    if not _tel_acik(conn):
        return []
    iz_sema(conn)
    from . import boss_detay
    boss_detay._sema(conn)
    simdi = time.time()
    for no in [n for n, t in _ILETISIM_HATA.items() if simdi - t > ILETISIM_HATA_SN]:
        del _ILETISIM_HATA[no]
    out, gorulen = [], set()
    for no, u in conn.execute(
            "SELECT e.boss_task_no, k.uuid FROM is_emri e JOIN boss_gorev_kimlik k ON k.task_no=e.boss_task_no "
            "LEFT JOIN boss_iz z ON z.task_no=e.boss_task_no LEFT JOIN boss_iletisim i ON i.task_no=e.boss_task_no "
            "WHERE e.kaynak='boss' AND e.durum NOT IN ('cozuldu','kapandi') "
            "AND (i.task_no IS NULL OR COALESCE(i.iz,'') <> COALESCE(z.iz,'') OR (i.telefon=0 AND COALESCE(e.musteri_tel,'')='' "
            "AND i.zaman < ?)) ORDER BY e.acilis DESC", (zaman.metin(zaman.simdi() - NUMARASIZ_YENIDEN),)):
        if no in _ILETISIM_HATA or no in gorulen:
            continue
        gorulen.add(no)
        out.append({"task_no": no, "uuid": u})
        if len(out) >= en_cok:
            break
    return out


def _tel10(ham) -> str | None:
    """Müşteri numarası: cep (5…) ya da sabit hat (2-4…) — başında 0/+90 olmadan 10 hane."""
    s = re.sub(r"\D", "", str(ham or ""))
    if s.startswith("0090"):
        s = s[4:]
    if s.startswith("90") and len(s) == 12:
        s = s[2:]
    if s.startswith("0") and len(s) == 11:
        s = s[1:]
    return s if len(s) == 10 and s[0] in "2345" else None


def iletisim_yaz(conn_fabrikasi, govde: dict) -> dict:
    """Eklentinin ``POST /api/boss/iletisim`` gövdesi: {sonuclar: [{task_no, veri | hata}]} → is_emri.musteri_tel
    (F21: yalnız ayar açıkken; saklama süresi saklama.py). Dönüş: sayılar + sıradaki okunacak işler."""
    if not isinstance(govde, dict) or not isinstance(govde.get("sonuclar"), list):
        raise Gecersiz("sonuclar listesi gerekli.", kod="alan_eksik")
    from saha import guvenlik

    from . import boss_detay
    conn = conn_fabrikasi()
    try:
        iz_sema(conn)
        tel_varsayilan(conn)
        acik = _tel_acik(conn)
        simdi, okunan, telefon, hata = zaman.metin(), 0, 0, 0
        with islem(conn):
            for x in govde["sonuclar"][:500]:
                if not isinstance(x, dict):
                    continue
                no = str(x.get("task_no") or "").strip()
                if not no:
                    continue
                if x.get("hata"):
                    hata += 1
                    if not str(x["hata"]).startswith("http_404"):
                        _ILETISIM_HATA[no] = time.time()
                        continue
                telefon += iletisim_kaydet(conn, acik and not x.get("hata"), no,
                                           None if x.get("hata") else x.get("veri"), simdi)
                okunan += 1
        return {"ok": True, "okunan": okunan, "telefon": telefon, "hata": hata, **iletisim_durumu(conn),
                "iletisim": iletisim_gerekli(conn)}
    finally:
        conn.close()


def iletisim_kaydet(conn, acik: bool, no: str, veri, simdi: str) -> int:
    """Bir işin BOSS iletişim listesi (``detail/customer/list`` yanıtı) → telefon (``acik`` iken) + ``boss_iletisim``
    kaydı (o anki parmak iziyle; telefon önden okuması bu işi yeniden sormaz). Çağıran işlemi açar. Dönüş: güncellenen
    iş sayısı. Ayrıntı önden okuması da (``boss_detay.onden_yaz``) bunu kullanır."""
    from . import boss_detay
    tel = None
    if acik:
        for kisi in boss_detay._iletisim(veri):
            tel = next((t for t in (_tel10(h) for h in kisi["telefonlar"]) if t), None)
            if tel:
                break
    n = 0
    if tel:
        n = conn.execute("UPDATE is_emri SET musteri_tel=? WHERE boss_task_no=? AND durum NOT IN "
                         "('cozuldu','kapandi') AND COALESCE(musteri_tel,'')<>?", (tel, no, tel)).rowcount
    iz = conn.execute("SELECT iz FROM boss_iz WHERE task_no=?", (no,)).fetchone()
    conn.execute("INSERT INTO boss_iletisim(task_no, iz, zaman, telefon) VALUES(?,?,?,?) "
                 "ON CONFLICT(task_no) DO UPDATE SET iz=excluded.iz, zaman=excluded.zaman, "
                 "telefon=excluded.telefon", (no, iz[0] if iz else None, simdi, 1 if tel else 0))
    return n


def iletisim_durumu(conn) -> dict:
    iz_sema(conn)
    try:
        toplam, tamam = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN i.task_no IS NOT NULL AND COALESCE(i.iz,'')=COALESCE(z.iz,'') THEN 1 "
            "ELSE 0 END) FROM is_emri e LEFT JOIN boss_iz z ON z.task_no=e.boss_task_no "
            "LEFT JOIN boss_iletisim i ON i.task_no=e.boss_task_no WHERE e.kaynak='boss' AND e.boss_task_no IS NOT NULL "
            "AND e.durum NOT IN ('cozuldu','kapandi')").fetchone()
    except sqlite3.OperationalError:
        toplam, tamam = 0, 0
    return {"iletisim_toplam": toplam or 0, "iletisim_tamam": tamam or 0, "musteri_tel": _tel_acik(conn)}


def _esitle(conn, pd, gorevler, tam_istek, t0) -> dict:
    satirlar = rapor_satirlari(conn, gorevler)
    acik = [s for s in satirlar if not kapali_mi(s["_BOSS Durumu"])]
    kapali = {s[aktarim.K["no"]]: s["_BOSS Durumu"] for s in satirlar if kapali_mi(s["_BOSS Durumu"])}
    kolonlar = [c for c in satirlar[0] if not c.startswith("_")] if satirlar else list(_SUTUN.values())
    df_hepsi = pd.DataFrame([{c: s.get(c) for c in kolonlar} for s in satirlar], columns=kolonlar)
    df_acik = pd.DataFrame([{c: s.get(c) for c in kolonlar} for s in acik], columns=kolonlar)
    for kol in (aktarim.K["il"], aktarim.K["ilce"], aktarim.K["adres"], aktarim.K["task"]):
        if kol not in df_acik.columns:
            df_acik[kol] = ""
    hz = aktarim.hazirla(conn, df_acik)
    fark = aktarim.fark_hesapla(conn, hz.isler)
    kapanacak = [r for r in conn.execute("SELECT * FROM is_emri WHERE boss_task_no IS NOT NULL AND durum<>'kapandi'")
                 if r["boss_task_no"] in kapali]
    kapanacak_no = {r["is_no"] for r in kapanacak}
    fark.kaybolan = [r for r in fark.kaybolan if r["is_no"] not in kapanacak_no]
    uyari = None
    nedenler, _bilgi = aktarim.bekci(conn, fark, None, None)
    tam = tam_istek
    if tam and "cok_kaybolan" in nedenler:
        tam = False
        uyari = f"BOSS listesinde {len(fark.kaybolan)} açık iş yok; güvenlik için kapatılmadı."
    degisiklik = bool(fark.yeni or fark.degisen or fark.yeniden_acilan or kapanacak or (tam and fark.kaybolan))
    simdi = zaman.metin()
    sonuc = {"gelen": len(satirlar), "acik_gelen": len(acik), "kapali_gelen": len(kapali), "tam": tam,
             "fark": {**fark.sayilar(), "kaybolan": len(fark.kaybolan) if tam else 0, "kapanan_boss": len(kapanacak)},
             "cikarilan": {"kurulum": hz.ozet["kurulum"], "ikinci_donanim": hz.ozet["ikinci_donanim"]}, "uyari": uyari}
    if not degisiklik:
        with islem(conn):
            conn.executemany("UPDATE is_emri SET son_gorulme=? WHERE is_no=?",
                             [(simdi, r["is_no"]) for _, r in fark.degismeyen])
            sonuc["randevu"] = _randevulari_al(conn, simdi)
            sonuc["telefon"] = _telefonlari_yaz(conn, acik)
            _ayar_yaz(conn, "boss_son_esitleme", {"zaman": simdi, "tam": tam, "gelen": len(satirlar), "uyari": uyari})
        sonuc["sure_sn"] = round(time.perf_counter() - t0, 3)
        return sonuc
    if _son_yedek_eski(conn):
        try:
            aktarim.aktarim_yedegi(aktarim._db_yolu(conn))
            with islem(conn):
                _ayar_yaz(conn, "boss_son_yedek", simdi)
        except Exception:      # noqa: BLE001
            raise V2Hata("Güvenlik yedeği alınamadı; hiçbir şey değiştirilmedi. Diskte yer var mı?",
                         kod="yedek_alinamadi", durum=503)
    sha = hashlib.sha256(f"boss-canli:{simdi}:{time.time_ns()}".encode()).hexdigest()
    with islem(conn):
        aid = conn.execute(
            "INSERT INTO ie_aktarim (kaynak, yontem, dosya_adi, dosya_sha256, dosya_zamani, yukleyen_id, yukleyen_ad, "
            "baslama, durum) VALUES ('boss_canli', 'eklenti', 'BOSS canlı eşitleme', ?, ?, NULL, 'BOSS Yardımcısı', ?, "
            "'isleniyor')", (sha, simdi, simdi)).lastrowid
    try:
        s = aktarim._uygula(conn, aid, hz, fark, tam, simdi)
        with islem(conn):
            b = aktarim._baglam(conn, aid, simdi, hz)
            for r in kapanacak:
                _kapat_boss(b, r, kapali[r["boss_task_no"]])
            # Yeniden açılan iş (iptal edilip satış kanalınca geri gönderilen; task no ile eşleşir): telefonu
            # yeniden indirilsin — parmak izi değişmese de (ör. listeden düşüp aynı haliyle dönen) iletişim kaydı silinir.
            _iletisim_unut(conn, [r["boss_task_no"] for _, r in fark.yeniden_acilan if r["boss_task_no"]])
            sonuc["randevu"] = _randevulari_al(conn, simdi)
            sonuc["telefon"] = _telefonlari_yaz(conn, acik)
            _ayar_yaz(conn, "boss_son_esitleme", {"zaman": simdi, "tam": tam, "gelen": len(satirlar), "uyari": uyari,
                                                  "yeniden_acilan": len(fark.yeniden_acilan)})
    except Exception as e:     # noqa: BLE001
        aktarim._hata_yaz(conn, aid, f"Yazılamadı: {type(e).__name__}")
        raise
    aktarim._sonrasi(conn)
    from . import dagitim
    sonuc["dagitim"] = dagitim.aktarim_sonrasi(conn, df_hepsi, aid, tam)
    sonuc.update(aktarim_id=aid, kontrol=s["kontrol"], boss_atamasi=s["boss_atamasi"],
                 sure_sn=round(time.perf_counter() - t0, 3))
    return sonuc
