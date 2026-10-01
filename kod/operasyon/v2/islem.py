"""Tek işlem yardımcısı: ``BEGIN IMMEDIATE … COMMIT`` (iç içe çağrıda SAVEPOINT).

Yazan her v2 işlemi bununla sarılır: yarıda kalan hiçbir değişiklik diske inmez; iki yazar aynı anda
başlarsa ikincisi ``busy_timeout`` kadar bekler (kilitlenme yok, sessiz ezme yok).
"""
from __future__ import annotations

import contextlib
import itertools
import sqlite3

_sayac = itertools.count(1)


@contextlib.contextmanager
def islem(conn: sqlite3.Connection):
    if conn.in_transaction:
        ad = f"sp_{next(_sayac)}"
        conn.execute(f"SAVEPOINT {ad}")
        try:
            yield conn
        except BaseException:
            conn.execute(f"ROLLBACK TO {ad}")
            conn.execute(f"RELEASE {ad}")
            raise
        conn.execute(f"RELEASE {ad}")
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


@contextlib.contextmanager
def kayit_noktasi(conn: sqlite3.Connection):
    """Toplu işlemlerde her iş kendi SAVEPOINT'inde: biri düşerse diğerleri kalır (spec §5.5)."""
    ad = f"sp_{next(_sayac)}"
    conn.execute(f"SAVEPOINT {ad}")
    try:
        yield conn
    except BaseException:
        conn.execute(f"ROLLBACK TO {ad}")
        conn.execute(f"RELEASE {ad}")
        raise
    conn.execute(f"RELEASE {ad}")
