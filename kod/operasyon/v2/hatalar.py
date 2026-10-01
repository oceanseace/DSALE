"""v2 hataları: her biri HTTP durumu + kod + Türkçe cümle taşır (spec §5.4).

Motor (akis, obek, sozluk, aktarim) bunları atar; ``api.py`` tek yerde ``{"hata", "kod", …}`` gövdesine çevirir.
"""
from __future__ import annotations


class V2Hata(Exception):
    durum = 400
    kod = "hata"

    def __init__(self, mesaj: str, *, kod: str | None = None, durum: int | None = None, **ek):
        super().__init__(mesaj)
        self.mesaj = mesaj
        if kod:
            self.kod = kod
        if durum:
            self.durum = durum
        self.ek = ek

    def govde(self) -> dict:
        return {"hata": self.mesaj, "kod": self.kod, **self.ek}


class IsYok(V2Hata):
    durum, kod = 404, "is_yok"

    def __init__(self, mesaj: str = "Bu iş bulunamadı ya da size ait değil.", **ek):
        super().__init__(mesaj, **ek)


class Yasak(V2Hata):
    durum, kod = 403, "yasak"

    def __init__(self, mesaj: str = "Bu bölüm görevinize kapalı.", **ek):
        super().__init__(mesaj, **ek)


class GecersizGecis(V2Hata):
    durum, kod = 409, "gecersiz_gecis"


class GuncelDegil(V2Hata):
    durum, kod = 409, "guncel_degil"


class AlanEksik(V2Hata):
    durum, kod = 422, "alan_eksik"


class Catisma(V2Hata):
    """409 ile dönen diğer kurallar (altyapi_engeli, tekrar_ariza, ad_var, baska_obekte …)."""
    durum = 409


class Gecersiz(V2Hata):
    """422 ile dönen doğrulama hataları (randevu_gecersiz, teknik_gecersiz, teyit_gerekli …)."""
    durum = 422
