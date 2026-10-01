"""İş emri akışı v2 — iş motoru (belgeler/OPERASYON_V2_SPEC.md §3, §4, §5 + OPERASYON_V2_EK.md).

İş emirleri artık veritabanındadır (BOSS Task No anahtarlı); rapor her yüklendiğinde uzlaşılır,
operasyonun yaptığı hiçbir şey ezilmez.

Modüller:
    akis      12 durum, geçiş tablosu, atama, toplu işlemler, ticket bağı, arama merdiveni, BTK şikâyeti/TÇS
    aski      EK-3: askı aralıkları ve net BTK saati (EK-12.3 geçerlilik)
    kurallar  EK-12: Turkcell süreç kuralları — hepsi ayar; koddaki değerler yalnız varsayılan
    kesinti   EK-12.6: kesintiye duyarlı sevk (Santral Arıza bülteni, verimlilik paketi)
    aktarim   rapor içe aktarım hattı (sha, bekçiler, yedek, tek işlem)
    izleme    EK-10: rapor klasörü izleme (yoklama)
    sozluk    ilçe/mahalle sözlüğü (Bursa 17 + Yalova 6 ilçe)
    obek      öbekler (mahalle grupları) ve obekler.json'dan bir kerelik aktarım
    siralama  kapasite modu, sıra, öneri, dilim (KARMA-2)
    gorunum   role göre kırpılmış satır/ayrıntı (F21)
    takip     Takip paneli sayıları
    saklama   KVKK saklama süreleri
    sema      v3/v4/v7 tablolarının SQL'i (göç bunları çağırır)
    api       FastAPI yönlendiricileri
"""
