"""Proje sabitleri: dosya yolları, ofis konumu, ölçü tanımları."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "ref"
MASTER = ROOT / "data" / "master"
OUTPUTS = ROOT / "outputs"

DATA_XLSX = RAW / "data.xlsx"
ONEMAP_JSON = RAW / "onemap_bina_bursa.json"
MASTER_CSV = MASTER / "bina_master.csv"
GEOM_JSON = MASTER / "bina_geometri.json"
QUALITY_JSON = MASTER / "veri_kalitesi.json"

ORGANIZASYON = "TURKCELL SUPERONLINE DEHANET EV ÇÖZÜM MERKEZİ"
ORGANIZASYON_KISA = "Dehanet EÇM"
OFIS = {"ad": "Dehanet EÇM Ofis", "lat": 40.22043814320989, "lon": 28.953528321918512, "plus_code": "6XC3+5C Nilüfer, Bursa"}

# Bölgeleme için dengelenebilecek ölçüler: kolon adı -> açıklama
OLCULER = {
    "firsat": "Satış fırsatı (boş residential HP) = RES HP − aktif residential abone",
    "res_hp": "RES HP (residential home pass)",
    "toplam_hp": "Toplam HP (residential + SOHO)",
    "bina": "Bina sayısı (ziyaret yükü)",
}
VARSAYILAN_OLCU = "res_hp"
VARSAYILAN_N = 8
VARSAYILAN_ALTERNATIFLER = "2-30,35,40,45,50"

# Sunum metinleri (kısa tutulur; değiştirmek için burayı düzenleyin)
SUNUM_BASLIK = "Bursa Fiber Satış Haritası"
SUNUM_HITAP = "Bilgilerinize sunulur"

# Satış organizasyonu (bilgi amaçlı; bölgelere otomatik isim atanmaz)
SATIS_EKIBI = {
    "mudur": "SERDAR AYTAÇ",
    "takim_lideri": "ALİ CAN KANDEMİR",
    "sorumlular": [
        "ALİ DOĞUKAN GÜNDOĞDU", "ALİ EREN YILMAZ", "ALİ GÜVEN TOĞYAN", "ATA BARIŞ KARALAR", "EMİR KOCA",
        "EMRE SEMİR", "ENES KARATAŞ", "EROL NACİ KANMAZ", "FURKAN YILMAZ", "GÜLERSU SAKALAR",
        "HAKAN VATANSEVER", "İBRAHİM ÇETİNKAYA", "İSKENDER TAYYİP GÜRLER", "KORAY GÖNENÇ", "MEHMET GÜNTAY",
        "MERT VARDAR", "MERT YILDIZ", "MERTCAN BAYRAK", "MERT MESUT PORTAKAL", "MUHAMMED YILDIZ",
        "MUHAMMET ALİ AK", "SEDAT YILDIRIM", "SUDE NAZ EYİCE", "YUNUSCAN BODUR", "YUNUS EMRE BOŞKUT",
    ],
}
