"""BOSS Teknik Havuz listesinin HAM alanları: görev başına bütün alanlar (düzleştirilmiş), yalnız açık işler.

Giriş: ``yaz`` (boss.esitle her eşitlemede) · ``ekle`` (GET /api/isler?ek=1 ve /api/isler/degisim?ek=1, api.py).
- Eklenti (eslem.js ``hamDuz``) her görevin ``ham`` alanında BOSS'un gönderdiği bütün alanları yollar; burada
  ``boss_ham`` tablosunda saklanır. Kapanan/düşen işin satırı silinir (kişisel veri yalnız açık işte durur).
- ``ekle`` satırlara ``ek`` ({anahtar: değer}) koyar; kişisel alanlar (``KISISEL``) yalnız ``is.musteri`` izniyle.
  Sütun adları ``ETIKETLER``'dedir (bilinmeyen anahtar kendi adıyla gösterilir).
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import ek_sema, zaman
from .islem import islem

EN_COK_ALAN = 150
EN_UZUN_DEGER = 2000

# Kişisel veri sayılan anahtarlar (müşteri adı/no, adres, telefon, e-posta, kimlik). Yalnız is.musteri izniyle çıkar.
# Eklentideki maske (kod/eklenti/maske.js KISISEL) en az bu adları kapsar; ikisi aynı örnek adlarla sınanır
# (test_v2_tasks_tablosu.py KISISEL_ORNEKLER ve eklenti/test.mjs "maske" bölümü).
KISISEL = re.compile(r"customer(?!.?churn)|musteri|phone|gsm|msisdn|^tel(efon)?$|\.tel(efon)?$|address|adres|mail|"
                     r"tckn|identity|birth|full.?name|name.?surname|first.?name|last.?name|surname|subscriber|"
                     r"contact|mobile", re.I)

# BOSS liste alanı → Türkçe sütun adı (06.10 canlı akıştaki gorev_yapisi olayından; değerler hiç görülmedi).
ETIKETLER: dict[str, str] = {
    "crmTaskId": "Task No", "parentCrmTaskId": "Üst Task No", "id": "BOSS Kimliği",
    "customerName": "Müşteri Adı", "customerNo": "Müşteri No", "customerChurn": "Müşteri Kayıp Riski",
    "city": "İl", "district": "İlçe", "neighborhood": "Mahalle", "address": "Adres",
    "dealer": "Bayi", "team": "Ekip", "team.name": "Ekip", "team.id": "Ekip Kimliği",
    "segment": "Segment", "saleChannel": "Satış Kanalı", "salesType": "Satış Türü",
    "taskCategory": "Task Adı", "taskCategoryType": "Task Türü Kodu", "orderRequestType": "Sipariş Türü",
    "taskStatus": "Durum Kodu", "taskStatusDesc": "Task Durumu", "subTaskStatus": "Alt Durum",
    "buildingName": "Bina Adı", "locationId": "Lokasyon", "locationUnitId": "Lokasyon Birimi",
    "productInfo": "Ürün", "productCode": "Ürün Kodu", "serviceId": "Hizmet No", "premiumMultigiga": "Premium Multigiga",
    "createDate": "Oluşturma Tarihi", "startDate": "Task Başlangıç Tarihi", "taskEndDate": "Task Bitiş Tarihi",
    "appointmentStartDate": "Randevu Başlangıç", "appointmentEndDate": "Randevu Bitiş", "hasSchedule": "Randevulu",
    "slaDefinition": "SL Tanımlı", "slaHourValue": "SL Süresi (Sa)", "slaMinuteValue": "SL Süresi (Dk)",
    "slaStatus": "SL Durumu", "btk": "BTK", "isComplaint": "Şikâyet", "lastApproval": "Son Onay",
    "isPrioritized": "Öncelikli", "isAddressOtpVerified": "Adres Doğrulandı (OTP)", "type": "Tür",
    "isOneDesk": "OneDesk", "oneDeskId": "OneDesk No", "bbk": "BBK",
}


def kisisel_mi(anahtar: str) -> bool:
    return bool(KISISEL.search(anahtar or ""))


def _deger(v):
    """JSON'a hazır sade değer: metin/sayı/bool/None; başka her şey metne çevrilir (kısaltılmış)."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v[:EN_UZUN_DEGER]
    return json.dumps(v, ensure_ascii=False, default=str)[:EN_UZUN_DEGER]


def temizle(ham) -> dict | None:
    """Eklentiden gelen ``ham`` → {anahtar: sade değer} (en çok 150 alan, BOSS sırasıyla)."""
    if not isinstance(ham, dict):
        return None
    out = {}
    for k, v in ham.items():
        if len(out) >= EN_COK_ALAN:
            break
        k = str(k)[:120]
        if k:
            out[k] = _deger(v)
    return out or None


def yaz(conn: sqlite3.Connection, gorevler: list, *, tam: bool = False, kaldirilan=()) -> int:
    """Açık görevlerin ham alanlarını yazar; kapananı, ``kaldirilan``ı ve (``tam`` görüntüde) görülmeyeni siler.
    Ham alanı olmayan görev (eski eklenti) dokunulmadan geçer. Dönüş: yazılan satır sayısı."""
    from .boss import kapali_mi
    acik, kapali = {}, set()
    for g in gorevler or ():
        if not isinstance(g, dict):
            continue
        no = str(g.get("task_no") or "").strip()
        if not no:
            continue
        if kapali_mi(g.get("durum")):
            kapali.add(no)
            continue
        h = temizle(g.get("ham"))
        if h:
            acik[no] = h
    sil = kapali | {str(x).strip() for x in kaldirilan or () if str(x or "").strip()}
    if not acik and (not sil or not ek_sema.var_mi(conn, "boss_ham")):
        return 0
    ek_sema.hazirla(conn)
    simdi = zaman.metin()
    with islem(conn):
        conn.executemany("INSERT INTO boss_ham(task_no, veri, guncelleme) VALUES(?,?,?) ON CONFLICT(task_no) DO UPDATE "
                         "SET veri=excluded.veri, guncelleme=excluded.guncelleme",
                         [(no, json.dumps(h, ensure_ascii=False), simdi) for no, h in acik.items()])
        conn.executemany("DELETE FROM boss_ham WHERE task_no=?", [(no,) for no in sil])
        if tam and acik:
            gorulen = set(acik) | {str(g.get("task_no") or "").strip() for g in gorevler if isinstance(g, dict)}
            conn.executemany("DELETE FROM boss_ham WHERE task_no=?",
                             [(no,) for (no,) in conn.execute("SELECT task_no FROM boss_ham").fetchall()
                              if no not in gorulen])
    return len(acik)


def kapananlari_sil(conn: sqlite3.Connection) -> int:
    """Saklama (saklama.uygula): işi açık olmayan ham satırları siler."""
    if not ek_sema.var_mi(conn, "boss_ham"):
        return 0
    with islem(conn):
        return conn.execute("DELETE FROM boss_ham WHERE task_no NOT IN (SELECT boss_task_no FROM is_emri WHERE "
                            "boss_task_no IS NOT NULL AND durum NOT IN ('cozuldu','kapandi'))").rowcount


def oku(conn: sqlite3.Connection, task_nolar) -> dict[str, dict]:
    """task_no → ham alanlar (yalnız istenenler)."""
    nolar = [str(n) for n in task_nolar if n]
    if not nolar or not ek_sema.var_mi(conn, "boss_ham"):
        return {}
    out = {}
    for i in range(0, len(nolar), 900):
        parca = nolar[i:i + 900]
        for no, veri in conn.execute(f"SELECT task_no, veri FROM boss_ham WHERE task_no IN ({','.join('?' * len(parca))})",
                                     parca):
            try:
                out[no] = json.loads(veri)
            except ValueError:
                continue
    return out


def ekle(conn: sqlite3.Connection, isler: list[dict], musteri: bool) -> dict[str, str]:
    """Satırlara ``ek`` koyar (her satırda; ham alanı yoksa {}). Dönüş: ``ek_etiketler`` (BOSS sırasıyla)."""
    ham = oku(conn, [x.get("boss_task_no") for x in isler if isinstance(x, dict)])
    etiket: dict[str, str] = {}
    for x in isler:
        if not isinstance(x, dict):
            continue
        h = ham.get(x.get("boss_task_no") or "") or {}
        ek = {k: v for k, v in h.items() if musteri or not kisisel_mi(k)}
        for k in ek:
            if k not in etiket:
                etiket[k] = ETIKETLER.get(k) or k
        x["ek"] = ek
    return etiket
