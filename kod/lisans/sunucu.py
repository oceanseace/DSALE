"""Lisansın FastAPI sunucusuna bağlanması — hazır, test edilmiş parçalar (sözleşme: belgeler/LISANS.md §8).

``saha/api.py`` bunları kullanır; lisans kuralları burada ve ``lisans/lisans.py``'de kalır:

    from lisans import lisans as lisans_cekirdek
    from lisans.sunucu import LisansKapisi, lisans_yonlendirici

    LISANS = lisans_cekirdek.Denetci(ayarlar.CALISMA / "lisans.json")
    uygulama.add_middleware(LisansKapisi, denetci=LISANS)
    uygulama.include_router(lisans_yonlendirici(
        LISANS, oturum=izin("oturum"), yukleme_izni=izin("lisans.yonet"),
        yonetici_mi=lambda k: izinli(k, "lisans.yonet"), kayit=_lisans_kaydi))

Not: ``from __future__ import annotations`` bilinçli olarak YOK — FastAPI gövde modelini çözebilsin.
"""
import logging
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import JSONResponse

from . import lisans as L

_gunluk = logging.getLogger("saha.lisans")


class LisansKapisi:
    """Salt okunur kipte yazma isteklerini durduran saf ASGI ara katmanı (varsayılan YASAK).

    Okuma (GET/HEAD/OPTIONS) HİÇ durdurulmaz. Yazma yalnız ``L.SALT_OKUNUR_SERBEST`` listesindeyse
    geçer. Durdurulan isteğe 503 ``salt_okunur`` döner: telefon kaydı kuyrukta tutar, sonra gönderir.
    Yönlendirmeden ÖNCE çalışır; v2 yönlendiricileri dahil bütün uçları kapsar.
    """

    def __init__(self, app, denetci: L.Denetci):
        self.app = app
        self.denetci = denetci

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("method", "GET").upper() not in L.OKUMA_YONTEMLERI:
            try:
                sonuc = self.denetci.sonuc()
            except Exception:  # denetim hatası kimsenin işini durdurmaz
                _gunluk.exception("Lisans denetimi yapılamadı; istek geçirildi.")
                sonuc = None
            if sonuc is not None and sonuc.salt_okunur and \
                    not L.yazma_serbest_mi(scope["method"], scope.get("path", "")):
                kod, govde, basliklar = L.salt_okunur_yaniti(sonuc)
                await JSONResponse(govde, status_code=kod, headers=basliklar)(scope, receive, send)
                return
        await self.app(scope, receive, send)


class LisansGirdi(BaseModel):
    """``POST /api/lisans`` gövdesi: lisans dosyasının içeriği ya da tek satırlık ``SAHA1.`` metni.

    Arayüz dosyayı tarayıcıda okuyup (FileReader) metin olarak gönderir; çok parçalı yükleme gerekmez.
    """

    model_config = ConfigDict(extra="ignore")
    metin: str = Field(min_length=1, max_length=L.EN_BUYUK_METIN)


def lisans_yonlendirici(denetci: L.Denetci, *, oturum: Callable[..., Any], yukleme_izni: Callable[..., Any],
                        yonetici_mi: Callable[[dict], bool],
                        kayit: Optional[Callable[[dict, L.Sonuc], None]] = None) -> APIRouter:
    """``GET /api/lisans`` (her oturum; yönetici tam, ekip kısa görünüm) ve ``POST /api/lisans`` (yönetici).

    ``oturum`` / ``yukleme_izni``: kişiyi (dict) döndüren FastAPI bağımlılıkları (saha: ``izin(...)``).
    ``kayit(kisi, sonuc)``: başarılı yüklemeyi yönetim kaydına yazar (isteğe bağlı).
    """
    r = APIRouter()

    @r.get("/api/lisans")
    def lisans_durumu(k: dict = Depends(oturum)):
        return denetci.sonuc().sozluk(yonetici=bool(yonetici_mi(k)))

    @r.post("/api/lisans")
    def lisans_yukle(girdi: LisansGirdi, k: dict = Depends(yukleme_izni)):
        try:
            sonuc = denetci.yukle(girdi.metin)
        except L.LisansHatasi as exc:
            durum = {"denetim_kapali": 409, "yazilamadi": 503}.get(exc.kod, 422)
            raise HTTPException(status_code=durum, detail={"hata": exc.mesaj, "kod": exc.kod}) from None
        lis = sonuc.lisans or {}
        _gunluk.info("Yeni lisans yüklendi: %s · %s → %s (durum %s)", lis.get("lisans_no"),
                     lis.get("baslangic"), lis.get("bitis"), sonuc.durum)
        if kayit is not None:
            try:
                kayit(k, sonuc)
            except Exception:  # kayıt yazılamasa da lisans kuruldu
                _gunluk.exception("Lisans yükleme kaydı yazılamadı.")
        return sonuc.sozluk(yonetici=True)

    return r


def acilis_metni(sonuc: L.Sonuc) -> list[str]:
    """Sunucu penceresine basılacak çerçeveli uyarı (sorun yoksa boş liste).

    ``saha/sunucu.py``: göçten sonra, adresi yazmadan önce. Sunucu HER DURUMDA açılır.
    """
    if sonuc.seviye == "yok" and not sonuc.salt_okunur:
        return []
    cizgi = "=" * 62
    satirlar = [cizgi, f"  LİSANS: {L.buyuk_harf(sonuc.baslik)}", cizgi]
    kelimeler, satir = sonuc.mesaj.split(), "  "
    for kelime in kelimeler:
        if len(satir) + len(kelime) + 1 > 62:
            satirlar.append(satir.rstrip())
            satir = "  "
        satir += kelime + " "
    satirlar.append(satir.rstrip())
    if sonuc.ayrinti:
        satirlar.append(f"  Ayrıntı: {sonuc.ayrinti}")
    satirlar.append(cizgi)
    return satirlar
