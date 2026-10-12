"""Tembel modül vekili: pandas/numpy gibi ağır kütüphaneler ilk kullanımda yüklenir.

``pd = tembel("pandas")`` modül düzeyinde yazılır; ``pd.DataFrame`` gibi ilk öznitelik erişimi
gerçek içe aktarmayı yapar. Sunucu açılışı (/api/saglik) bu yüzden pandas'ı beklemez.
"""
from __future__ import annotations

import importlib
import threading
from typing import Any

_kilit = threading.Lock()


class _Tembel:
    __slots__ = ("_ad", "_modul")

    def __init__(self, ad: str) -> None:
        object.__setattr__(self, "_ad", ad)
        object.__setattr__(self, "_modul", None)

    def _yukle(self):
        m = object.__getattribute__(self, "_modul")
        if m is None:
            with _kilit:
                m = object.__getattribute__(self, "_modul")
                if m is None:
                    m = importlib.import_module(object.__getattribute__(self, "_ad"))
                    object.__setattr__(self, "_modul", m)
        return m

    def __getattr__(self, ad: str) -> Any:
        return getattr(self._yukle(), ad)

    def __repr__(self) -> str:
        return f"<tembel {object.__getattribute__(self, '_ad')}>"


def tembel(ad: str) -> Any:
    return _Tembel(ad)
