"""Faz 2 API uçları: veri kalitesi · bölge planlayıcı · tur raporu/OneMap · ticket defteri ·
3B geometri · harita altlığı. Sözleşme: ``belgeler/SAHA_SOZLESME.md`` §7.

İş mantığı ayrı modüllerde (veri_kalitesi, bolgeleme, tur_raporu, ticket, geometri,
altlik); bu dosya yalnız yetki, girdi doğrulama ve HTTP biçimi ile ilgilenir. Hata
biçimi her yerde ``{"hata", "kod"}``, metinler Türkçe.

Yetki (spec §2.3): veri yönetimi uçları ``veri.yonet``; ticket defteri ``ticket.defter``
(operasyon + yönetici); ticket metni şablonu ve harita altlığı herkese açık ama bina
kapsamı ``bina_gorebilir`` ile denetlenir. Veri yönetimi eylemleri ``yonetim_kaydi``'na yazılır.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from . import altlik, ayarlar, bolgeleme, db, geometri, sema_v2, ticket, tur_raporu, veri_kalitesi
from .api import _baslik, baglanti, hata
from .yetki import bina_gorebilir, bolge_kapsami, izin

# Veri yönetimi (kalite, bölgeleme, tur raporu, OneMap, bina değişimi, altlık yazma): yalnız yönetici.
veri_yonet = izin("veri.yonet")

yonlendirici = APIRouter()

EN_BUYUK_DOSYA = 80 * 1024 * 1024      # tur raporu / OneMap dökümü için üst sınır


def _plan_hatasi(exc: bolgeleme.PlanHatasi | tur_raporu.TurHatasi):
    return hata(exc.durum, exc.mesaj, exc.kod)


def _kayit(conn: sqlite3.Connection, k: dict, eylem: str, hedef: str | None, ozet: dict | None) -> None:
    """Veri yönetimi izi (spec §1.11-5): işlem zaten yazıldıysa ayrı küçük bir işlemde."""
    try:
        db.yonetim_kaydi(conn, k, eylem, hedef, ozet)
        conn.commit()
    except sqlite3.Error:
        pass


async def _dosya_oku(istek: Request, alan: str = "dosya") -> tuple[bytes, str]:
    """Hem multipart (form alanı ``dosya``) hem ham gövde (``application/octet-stream``) kabul eder."""
    tur = (istek.headers.get("content-type") or "").lower()
    uzunluk = int(istek.headers.get("content-length") or 0)
    if uzunluk > EN_BUYUK_DOSYA:
        raise hata(413, "Dosya çok büyük (en çok 80 MB).", "dosya_buyuk")
    if tur.startswith("multipart/form-data"):
        form = await istek.form()
        f = form.get(alan)
        if f is None:
            f = next((v for v in form.values() if hasattr(v, "read")), None)
        if f is None or not hasattr(f, "read"):
            raise hata(400, f"Formda '{alan}' dosya alanı yok.", "dosya_yok")
        icerik = await f.read()
        ad = getattr(f, "filename", "") or ""
    else:
        icerik = await istek.body()
        ad = istek.headers.get("x-dosya-adi", "")
    if len(icerik) > EN_BUYUK_DOSYA:
        raise hata(413, "Dosya çok büyük (en çok 80 MB).", "dosya_buyuk")
    return icerik, ad


# ============================================================================= veri kalitesi
@yonlendirici.get("/api/kalite/ozet")
def kalite_ozet(bolge: int | None = None, k: dict = Depends(veri_yonet),
                conn: sqlite3.Connection = Depends(baglanti)):
    """Kural başına kaç bina: ne bulundu, kaçı güvenle düzeltildi, neden önemli."""
    return veri_kalitesi.ozet(conn, bolge)


@yonlendirici.get("/api/kalite/liste")
def kalite_liste(kural: str | None = None, bolge: int | None = None, seviye: str | None = None,
                 limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                 k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    from dsale import kalite as kurallar

    if kural and kural not in kurallar.KURALLAR:
        raise hata(400, f"Bilinmeyen kural: {kural}", "kural_gecersiz")
    if seviye and seviye not in ("bilgi", "uyari"):
        raise hata(400, "Seviye 'bilgi' ya da 'uyari' olmalı.", "seviye_gecersiz")
    sonuc = veri_kalitesi.liste(conn, kural, bolge, seviye, limit, offset)
    for b in sonuc["binalar"]:
        b["baslik"] = _baslik(b)
    return sonuc


@yonlendirici.post("/api/kalite/yenile")
def kalite_yenile(k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    """Bütün binaları kurallardan yeniden geçirir (kural ya da kaynak dosya değiştiyse)."""
    sonuc = veri_kalitesi.hazirla(conn, zorla=True) or {}
    return {**sonuc, "mesaj": f"{sonuc.get('bina', 0)} bina yeniden denetlendi."}


# ============================================================================= bölge planlayıcı
class UygulaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    n: int = Field(ge=bolgeleme.EN_AZ_N, le=bolgeleme.EN_COK_N)
    plan_ref: str = Field(min_length=5, max_length=200)
    # Bölgesi kalmayan satışçıları pasife al (yönetici açıkça onaylamalı). Onay yoksa
    # "bölgesiz" (0) kalırlar; hesapları kapanmaz.
    pasiflestir: bool = False
    notu: str | None = Field(default=None, validation_alias=AliasChoices("notu", "not"))


@yonlendirici.get("/api/bolgeleme/durum")
def bolgeleme_durum(k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    return bolgeleme.durum(conn)


def _harita_sirasi(conn: sqlite3.Connection, son: dict[str, int]) -> list[int]:
    """Önizleme haritası için: /api/harita (bölgesiz) seri sırasıyla hizalı yeni bölge dizisi."""
    return [int(son.get(r[0], 0)) for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE pasif=0 ORDER BY bina_serial")]


@yonlendirici.get("/api/bolgeleme/onizleme")
def bolgeleme_onizleme(
    n: int = Query(ge=bolgeleme.EN_AZ_N, le=bolgeleme.EN_COK_N),
    olcu: str = Query(default="res_hp"),
    hesapla: bool = False,
    kaynak: str | None = Query(default=None, pattern="^(hazir|onbellek|hesap)$"),
    k: dict = Depends(veri_yonet),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Plan önizlemesi. Hazır plan yoksa (ya da ``hesapla=1``) arka planda hesap başlar → 202 + iş."""
    if olcu not in bolgeleme.OLCULER:
        raise hata(400, f"Ölçü şunlardan biri olmalı: {', '.join(bolgeleme.OLCULER)}", "olcu_gecersiz")
    binalar = bolgeleme._binalar(conn)
    plan = None if hesapla else bolgeleme.plan_bul(binalar, n, olcu, kaynak)
    if plan is None:
        if kaynak and not hesapla:
            raise hata(404, "Bu kaynakta bu bölge sayısı için plan yok.", "plan_yok")
        try:
            is_ = bolgeleme.hesap_baslat(n, olcu)
        except bolgeleme.PlanHatasi as exc:
            raise _plan_hatasi(exc)
        return JSONResponse({"hazir": False, "n": n, "olcu": olcu, "is": is_,
                             "mesaj": f"{n} bölgelik plan güncel veriyle hesaplanıyor "
                                      f"(yaklaşık {is_['tahmini_sn']} saniye)."}, status_code=202)
    on = bolgeleme.onizle(conn, plan, binalar)
    cikti = bolgeleme.disa(on)
    cikti["hazir"] = True
    cikti["bina_bolge"] = _harita_sirasi(conn, on["_son_atama"])
    return cikti


@yonlendirici.get("/api/bolgeleme/is/{is_id}")
def bolgeleme_is(is_id: str, k: dict = Depends(veri_yonet)):
    j = bolgeleme.is_durumu(is_id)
    if not j:
        raise hata(404, "Hesap işi bulunamadı (sunucu yeniden başlamış olabilir).", "is_yok")
    return j


@yonlendirici.post("/api/bolgeleme/uygula")
def bolgeleme_uygula(girdi: UygulaGirdi, k: dict = Depends(veri_yonet),
                     conn: sqlite3.Connection = Depends(baglanti)):
    try:
        sonuc = bolgeleme.uygula(conn, girdi.plan_ref, girdi.n, k["id"], girdi.pasiflestir, girdi.notu)
    except bolgeleme.PlanHatasi as exc:
        raise _plan_hatasi(exc)
    _kayit(conn, k, "bolge_uygula", f"plan:{sonuc.get('plan_id', '')}", {"n": girdi.n})
    return sonuc


@yonlendirici.post("/api/bolgeleme/geri-al")
def bolgeleme_geri_al(k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    try:
        sonuc = bolgeleme.geri_al(conn, k["id"])
    except bolgeleme.PlanHatasi as exc:
        raise _plan_hatasi(exc)
    _kayit(conn, k, "bolge_geri_al", None, None)
    return sonuc


@yonlendirici.get("/api/bolgeleme/excel")
def bolgeleme_excel(plan_id: int | None = None, k: dict = Depends(veri_yonet),
                    conn: sqlite3.Connection = Depends(baglanti)):
    """Etkin planın açıklayıcı Excel'i (Bursa_{N}_Satisci_Bolgeleme.xlsx). İlk üretim ~30 sn."""
    try:
        yol, ad = bolgeleme.excel_yolu(conn, plan_id)
    except bolgeleme.PlanHatasi as exc:
        raise _plan_hatasi(exc)
    return FileResponse(yol, filename=ad,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ============================================================================= tur raporu / OneMap
class TurUygulaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tur_id: int
    pasif_onay: bool = False
    iller: list[str] | None = None


@yonlendirici.post("/api/veri/tur-raporu")
async def tur_raporu_yukle(istek: Request, k: dict = Depends(veri_yonet),
                           conn: sqlite3.Connection = Depends(baglanti)):
    """Tur raporunu yükler ve FARKI gösterir. Veritabanına yazmaz (önizleme)."""
    icerik, ad = await _dosya_oku(istek)
    try:
        return await run_in_threadpool(tur_raporu.yukle, conn, icerik, ad, k["id"])
    except tur_raporu.TurHatasi as exc:
        raise _plan_hatasi(exc)


@yonlendirici.get("/api/veri/tur-raporu")
def tur_raporu_liste(k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    son = db.ayar_oku(conn, "tur_raporu_son")
    return {"raporlar": tur_raporu.liste(conn), "son_uygulanan": json.loads(son) if son else None}


@yonlendirici.get("/api/veri/tur-raporu/{tur_id}")
def tur_raporu_getir(tur_id: int, k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    try:
        return tur_raporu.getir(conn, tur_id)
    except tur_raporu.TurHatasi as exc:
        raise _plan_hatasi(exc)


@yonlendirici.post("/api/veri/tur-raporu/uygula")
def tur_raporu_uygula(girdi: TurUygulaGirdi, k: dict = Depends(veri_yonet),
                      conn: sqlite3.Connection = Depends(baglanti)):
    try:
        sonuc = tur_raporu.uygula(conn, girdi.tur_id, k["id"], girdi.pasif_onay, girdi.iller)
    except tur_raporu.TurHatasi as exc:
        raise _plan_hatasi(exc)
    _kayit(conn, k, "tur_uygula", f"tur:{girdi.tur_id}", None)
    return sonuc


@yonlendirici.get("/api/veri/bekleyen")
def bekleyen_binalar(durum: str = Query(default="konum_bekliyor",
                                        pattern="^(konum_bekliyor|eklendi|rapordan_cikti)$"),
                     k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    binalar = tur_raporu.bekleyenler(conn, durum)
    return {"durum": durum, "toplam": len(binalar), "binalar": binalar}


@yonlendirici.get("/api/veri/bekleyen.txt")
def bekleyen_kimlikler(k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    """OneMap aracına verilecek kimlik dosyası (satır başına bir kimlik)."""
    kimlikler = tur_raporu.bekleyen_kimlikler(conn)
    return PlainTextResponse("\n".join(kimlikler) + ("\n" if kimlikler else ""),
                             headers={"Content-Disposition": 'attachment; filename="bekleyen_idler.txt"'})


@yonlendirici.get("/api/veri/onemap-araci.js")
def onemap_araci(k: dict = Depends(veri_yonet)):
    yol = ayarlar.ONEMAP_ARACI
    if not yol.exists():
        raise hata(404, "OneMap aracı bulunamadı.", "arac_yok")
    return FileResponse(yol, media_type="text/javascript; charset=utf-8", filename="onemap_cek.js")


@yonlendirici.post("/api/veri/onemap")
async def onemap_yukle(istek: Request, k: dict = Depends(veri_yonet),
                       conn: sqlite3.Connection = Depends(baglanti)):
    """OneMap aracının indirdiği ``onemap_yeni.json``: bekleyen binalar haritaya eklenir."""
    icerik, _ad = await _dosya_oku(istek)
    try:
        veri = json.loads(icerik.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise hata(400, "Dosya JSON değil. onemap_cek.js'in indirdiği onemap_yeni.json yüklenmeli.",
                   "dosya_gecersiz")
    try:
        sonuc = await run_in_threadpool(tur_raporu.onemap_yukle, conn, veri, k["id"], icerik)
    except tur_raporu.TurHatasi as exc:
        raise _plan_hatasi(exc)
    await run_in_threadpool(_kayit, conn, k, "onemap", None, None)
    return sonuc


@yonlendirici.get("/api/bina/{bina_serial}/degisim")
def bina_degisim(bina_serial: str, k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    """Binanın künye geçmişi: tur raporuyla değişen HP/abone, pasife alma, OneMap'ten ekleme."""
    satirlar = conn.execute(
        "SELECT kaynak, alan, eski, yeni, zaman FROM bina_degisim WHERE bina_serial=? ORDER BY id DESC LIMIT 200",
        (bina_serial,)).fetchall()
    return {"bina_serial": bina_serial, "degisimler": [dict(r) for r in satirlar]}


# ============================================================================= ticket defteri
class TicketGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    konu: str
    bina_serial: str | None = None
    location_id: str | None = None
    ticket_no: str | None = Field(default=None, max_length=40)
    acilis: str | None = None
    durum: str | None = None
    musteri: str | None = Field(default=None, max_length=500)
    kanal: str | None = Field(default=None, max_length=40)
    detay: str | None = Field(default=None, max_length=4000)
    site: str | None = Field(default=None, max_length=200)
    ekip: str | None = Field(default=None, max_length=80)       # ticket metnindeki "Ekip:" telefonu
    metin: str | None = Field(default=None, max_length=4000)
    notu: str | None = Field(default=None, max_length=2000)
    onedesk_ekip: str | None = Field(default=None, max_length=80)   # Ek-5: TEAM-TAS1BRS
    kategori: str | None = Field(default=None, max_length=160)      # Ek-5: OneDesk başlığı


class TicketGuncelleGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    durum: str | None = None
    ticket_no: str | None = Field(default=None, max_length=40)
    acilis: str | None = None
    konu: str | None = None
    musteri: str | None = Field(default=None, max_length=500)
    kanal: str | None = Field(default=None, max_length=40)
    detay: str | None = Field(default=None, max_length=4000)
    site: str | None = Field(default=None, max_length=200)
    location_id: str | None = Field(default=None, max_length=40)
    onedesk_ekip: str | None = Field(default=None, max_length=80)
    kategori: str | None = Field(default=None, max_length=160)
    notu: str | None = Field(default=None, max_length=2000, validation_alias=AliasChoices("notu", "not"))


@yonlendirici.get("/api/ticket")
def ticket_liste(
    durum: str | None = None, konu: str | None = None, kanal: str | None = None, q: str | None = None,
    bina_serial: str | None = None, acik: bool | None = None, bolge: int | None = None,
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
    k: dict = Depends(izin("ticket.defter")), conn: sqlite3.Connection = Depends(baglanti),
):
    try:
        return ticket.liste(conn, durum, konu, kanal, q, bina_serial, acik, bolge, limit, offset)
    except ValueError as exc:
        raise hata(400, str(exc), "gecersiz_veri")


@yonlendirici.get("/api/ticket/sablon")
def ticket_sablon(bina_serial: str, konu: str = "SİNYAL", ekip: str = "",
                  k: dict = Depends(izin("ticket.sablon")), conn: sqlite3.Connection = Depends(baglanti)):
    """Ticket açmadan metni üretir (kopyala → OneDesk'e yapıştır). Satışçı da kendi bölgesinde kullanır."""
    b = _bina_yetkili(conn, k, bina_serial)
    konu_k = ticket.konu_coz(konu)
    if not konu_k:
        raise hata(400, f"Konu şunlardan biri olmalı: {', '.join(ticket.KONULAR)}", "konu_gecersiz")
    return {"bina_serial": bina_serial, "konu": konu_k, "metin": ticket.ticket_metni(b, konu_k, ekip),
            "sablon_taslak": konu_k not in ticket.ONAYLI_SABLONLAR,
            "alanlar": {"bina_serial": b["bina_serial"], "tellcordia_id": b.get("tellcordia_id") or "",
                        "location_id": b.get("location_id") or "", "obek": b.get("obek") or "",
                        "site_adi": ticket.site_adi(b)}}


def _ayar_metni(conn: sqlite3.Connection, anahtar: str) -> str | None:
    try:
        return db.ayar_oku(conn, anahtar)
    except sqlite3.Error:
        return None


def _kategoriler(conn: sqlite3.Connection) -> dict:
    """Ek-5 + Ek-12/7: OneDesk ekibi ve başlıkları, şablonun zorunlu bilgileri, hatırlatma süresi, kırmızı hat
    mail konusu — hepsi ayar'dan; ayar yoksa (ör. v8'den önce eklenmiş anahtar) ``sema_v2`` varsayılanı."""
    def oku(anahtar, varsayilan):
        try:
            deger = json.loads(_ayar_metni(conn, anahtar) or "null")
        except (TypeError, ValueError):
            deger = None
        return deger if isinstance(deger, list) and deger else varsayilan

    ekipler = oku("ticket_ekipleri", sema_v2.TICKET_EKIPLERI)
    varsayilan = _ayar_metni(conn, "ticket_varsayilan_ekip") or ekipler[0]
    try:
        hatirlatma = int(_ayar_metni(conn, "ticket_bco_hatirlatma_saat")
                         or sema_v2.AYAR_EK["ticket_bco_hatirlatma_saat"])
    except ValueError:
        hatirlatma = int(sema_v2.AYAR_EK["ticket_bco_hatirlatma_saat"])
    basliklar = []
    for ad in oku("ticket_kategorileri", sema_v2.TICKET_KATEGORILERI):
        sade = ticket._sade(ad)
        # "SINYAL YOK" başlıklarında sinyal şablonu önerilir; ek switch/splitter → EK SP.
        oneri = "SİNYAL" if "SINYALYOK" in sade else ("EK SP" if "SPLITER" in sade or "SPLITTER" in sade else None)
        basliklar.append({"ad": ad, "konu_onerisi": oneri})
    zorunlu = [a for a in oku("ticket_zorunlu_alanlar", sema_v2.TICKET_ZORUNLU_ALANLAR)
               if isinstance(a, dict) and a.get("etiket")]
    return {"ekipler": ekipler, "varsayilan_ekip": varsayilan, "kategoriler": basliklar,
            "zorunlu_alanlar": zorunlu, "bco_hatirlatma_saat": hatirlatma,
            "kirmizi_hat_konu_sablonu": _ayar_metni(conn, "kirmizi_hat_konu_sablonu")
            or sema_v2.AYAR_EK["kirmizi_hat_konu_sablonu"]}


@yonlendirici.get("/api/ticket/kategoriler")
def ticket_kategorileri(k: dict = Depends(izin("ticket.sablon")), conn: sqlite3.Connection = Depends(baglanti)):
    return _kategoriler(conn)


@yonlendirici.get("/api/ticket/harita")
def ticket_harita(k: dict = Depends(izin("ticket.defter")), conn: sqlite3.Connection = Depends(baglanti)):
    return ticket.harita_sayilari(conn)


def _ticket_degisti(conn: sqlite3.Connection, ticket_idler, k: dict | None) -> list[str]:
    """Ticket ÇÖZÜLDÜ/KAPATILDI/İPTAL olunca bağlı 'altyapı' işleri bekliyor'a döner (spec §3.7).

    ``operasyon.v2.akis.ticket_degisti`` yoksa (iş emri modülü kurulmamış) hiçbir şey yapılmaz.
    """
    try:
        from operasyon.v2 import akis
    except ImportError:
        return []
    fonksiyon = getattr(akis, "ticket_degisti", None)
    if not callable(fonksiyon):
        return []
    donen: list[str] = []
    for tid in ticket_idler:
        donen += list(fonksiyon(conn, int(tid), k) or [])
    conn.commit()
    return donen


@yonlendirici.post("/api/ticket/aktar")
async def ticket_aktar_ucu(istek: Request, kuru: bool = False, k: dict = Depends(izin("ticket.defter")),
                           conn: sqlite3.Connection = Depends(baglanti)):
    """Excel'deki TICKET sayfasını aktarır (spec §5.3.8): önce yedek, aynı kurallar, sonra iş denetimi."""
    icerik, ad = await _dosya_oku(istek)
    return await run_in_threadpool(_ticket_aktar, conn, icerik, ad, kuru, k)


def _ticket_aktar(conn: sqlite3.Connection, icerik: bytes, ad: str, kuru: bool, k: dict) -> dict:
    from . import ticket_aktar, yedekle

    if not icerik:
        raise hata(400, "Dosya boş.", "dosya_yok")
    with tempfile.TemporaryDirectory(prefix="saha-ticket-") as dizin:
        yol = Path(dizin) / "ticket.xlsx"
        yol.write_bytes(icerik)
        try:
            satirlar = ticket_aktar.satirlari_oku(yol)
        except Exception as exc:  # openpyxl/pandas: bozuk dosya ya da sayfa yok
            raise hata(422, "Bu dosyada TICKET sayfası okunamadı. data.xlsx'i seçin.", "rapor_tanimadi") from exc
    yedek = None
    if not kuru:
        try:
            yedek = str(yedekle.aktarim_yedegi(db.db_yolu()))
        except yedekle.YedekHatasi as exc:
            raise hata(503, "Güvenlik yedeği alınamadı; hiçbir şey değiştirilmedi. Diskte yer var mı?",
                       "yedek_alinamadi") from exc
    once = {r[0] for r in conn.execute("SELECT id FROM ticket WHERE durum IN ('ÇÖZÜLDÜ','KAPATILDI','İPTAL')")}
    sonuc = ticket_aktar.aktar(conn, satirlar, kuru=kuru)
    donen: list[str] = []
    if not kuru:
        db.yonetim_kaydi(conn, k, "ticket_aktar", None,
                         {a: sonuc.get(a, 0) for a in ("okunan", "eklenen", "zaten_var", "guncellenen")})
        conn.commit()
        kapanan = [r[0] for r in conn.execute(
            "SELECT id FROM ticket WHERE durum IN ('ÇÖZÜLDÜ','KAPATILDI','İPTAL')") if r[0] not in once]
        donen = _ticket_degisti(conn, kapanan, k)
    return {
        "okunan": sonuc.get("okunan", 0),
        "eklenen": sonuc.get("eklenen", sonuc.get("eklenecek", 0)),
        "zaten_var": sonuc.get("zaten_var", 0),
        "guncellenen": sonuc.get("guncellenen", 0),
        "binaya_baglanan": sonuc.get("binaya_baglanan", 0),
        "binasiz": sonuc.get("binasiz", 0),
        # Kişisel veri yok: yalnız satır numarası ve lokasyonun olup olmadığı.
        "baglanamayan": [{"satir": b.get("satir"), "lokasyon_var": bool(b.get("lokasyon"))}
                         for b in sonuc.get("baglanamayan", [])],
        "kuru": kuru, "yedek": yedek, "bekliyora_donen_is": len(donen),
    }


@yonlendirici.post("/api/ticket", status_code=201)
def ticket_olustur(girdi: TicketGirdi, k: dict = Depends(izin("ticket.defter")),
                   conn: sqlite3.Connection = Depends(baglanti)):
    veri = girdi.model_dump()
    # Ek-5: ekranda ekip seçilmediyse varsayılan OneDesk ekibi (ayar; TEAM-TAS1BRS). Excel aktarımı bunu yapmaz.
    if not (veri.get("onedesk_ekip") or "").strip():
        veri["onedesk_ekip"] = _kategoriler(conn)["varsayilan_ekip"]
    try:
        tid, bilgi = ticket.olustur(conn, veri, k["id"])
    except ValueError as exc:
        raise hata(400, str(exc), "gecersiz_veri")
    except LookupError as exc:
        raise hata(404, str(exc), "bina_yok")
    conn.commit()
    return {"ticket": ticket.getir(conn, tid), "sablon_taslak": bilgi.get("sablon_taslak", False),
            "mesaj": "Ticket kaydedildi."}


@yonlendirici.get("/api/ticket/{ticket_id}")
def ticket_getir(ticket_id: int, k: dict = Depends(izin("ticket.defter")),
                 conn: sqlite3.Connection = Depends(baglanti)):
    t = ticket.getir(conn, ticket_id)
    if not t:
        raise hata(404, "Ticket bulunamadı.", "ticket_yok")
    return {"ticket": t, "gecmis": ticket.gecmis(conn, ticket_id)}


@yonlendirici.patch("/api/ticket/{ticket_id}")
def ticket_guncelle(ticket_id: int, girdi: TicketGuncelleGirdi, k: dict = Depends(izin("ticket.defter")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    try:
        sonuc = ticket.guncelle(conn, ticket_id, girdi.model_dump(exclude_unset=True), k["id"])
    except ValueError as exc:
        raise hata(400, str(exc), "gecersiz_veri")
    except LookupError as exc:
        raise hata(404, str(exc), "ticket_yok")
    conn.commit()
    # Ticket çözülünce/kapanınca bağlı "Altyapı bekliyor" işleri teyitli ziyarete döner (geçiş 17).
    donen = []
    if sonuc.get("degisti") and "durum" in sonuc.get("alanlar", []) \
            and (ticket.getir(conn, ticket_id) or {}).get("durum") in ticket.KAPALI_DURUMLAR:
        donen = _ticket_degisti(conn, [ticket_id], k)
    return {**sonuc, "ticket": ticket.getir(conn, ticket_id), "gecmis": ticket.gecmis(conn, ticket_id),
            "bekliyora_donen_is": len(donen)}


def _bina_yetkili(conn: sqlite3.Connection, k: dict, bina_serial: str) -> dict:
    satir = conn.execute(
        "SELECT bina_serial, ad, site_adi, crm_site_adi, location_id, tellcordia_id, obek, bolge "
        "FROM bina WHERE bina_serial=?", (bina_serial,)).fetchone()
    if not satir:
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    # Satış kendi bölgesi (ya da listesi), teknik yalnız kendi açık işinin binası (spec §2.4-2).
    if not bina_gorebilir(conn, k, bina_serial):
        raise hata(403, "Bu bina sizin bölgenizde değil.", "baska_bolge")
    return dict(satir)


@yonlendirici.get("/api/bina/{bina_serial}/ticket")
def bina_ticketlari(bina_serial: str, k: dict = Depends(izin("bina.oku")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    _bina_yetkili(conn, k, bina_serial)
    liste = ticket.binanin_ticketlari(conn, bina_serial)
    return {"bina_serial": bina_serial, "acik": sum(1 for t in liste if t["acik"]), "ticketlar": liste}


# ============================================================================= 3B geometri
@yonlendirici.get("/api/binalar/geometri")
def bina_geometrisi(
    bolge: int | None = None,
    accept_encoding: str | None = Header(default=None),
    if_none_match: str | None = Header(default=None),
    k: dict = Depends(izin("geometri.oku")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Bina tabanları (3B ikiz): {serial[], lat[], lon[], kat[], ofs[], fark[], olcek}. gzip + ETag."""
    bolge = bolge_kapsami(k, bolge)
    govde, sikisik, etag = geometri.paket(conn, bolge)
    ortak = {"ETag": etag, "Cache-Control": "private, no-cache", "Vary": "Accept-Encoding"}
    if if_none_match and etag in [e.strip() for e in if_none_match.split(",")]:
        return Response(status_code=304, headers=ortak)
    if "gzip" in (accept_encoding or "").lower():
        return Response(content=sikisik, media_type="application/json",
                        headers={**ortak, "Content-Encoding": "gzip"})
    return Response(content=govde, media_type="application/json", headers=ortak)


# ============================================================================= harita altlığı
class AltlikGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sokak_url: str | None = None
    uydu_url: str | None = None
    sokak_atif: str | None = None
    uydu_atif: str | None = None
    atif: str | None = None                      # tek atıf verilirse iki katmana da yazılır
    sokak_en_fazla_zoom: int | None = None
    uydu_en_fazla_zoom: int | None = None
    varsayilana_don: bool = False


@yonlendirici.get("/api/ayar/altlik")
def altlik_oku(k: dict = Depends(izin("altlik.oku")), conn: sqlite3.Connection = Depends(baglanti)):
    return altlik.oku(conn)


@yonlendirici.put("/api/ayar/altlik")
def altlik_yaz(girdi: AltlikGirdi, k: dict = Depends(veri_yonet), conn: sqlite3.Connection = Depends(baglanti)):
    degisiklik = girdi.model_dump(exclude_unset=True)
    if degisiklik.get("atif"):
        degisiklik.setdefault("sokak_atif", degisiklik["atif"])
        degisiklik.setdefault("uydu_atif", degisiklik["atif"])
    try:
        sonuc = altlik.yaz(conn, degisiklik, girdi.varsayilana_don)
    except ValueError as exc:
        raise hata(400, str(exc), "altlik_gecersiz")
    return {**sonuc, "mesaj": "Harita altlığı kaydedildi."}

