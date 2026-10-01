/**
 * "Sonucu işle" — ziyaretin sonucunu tek ekranda kaydeder.
 *
 * Yedi büyük seçenek, gerekirse satış adedi, isteğe bağlı not ve tek bir
 * "Kaydet". Kaydet'e basıldığı anda kayıt telefona yazılır, ekran kapanır;
 * gönderim arka planda olur. Kullanıcı hiçbir zaman "gönderiliyor" ekranında
 * beklemez, çünkü sahada bekleyecek vakti yoktur.
 *
 * ÜÇ ŞEY BURADA KORUNUYOR:
 *  1. Yanlışlıkla dışarı dokunmak yazılanı SİLMEZ — onay sorulur.
 *  2. "Kaydet" her zaman ekranda, çekmecenin altına yapışık durur; 360 px'lik
 *     telefonda not alanı açıkken ekranın dışında kalıyordu.
 *  3. Aynı binaya ikinci kez sonuç işlemek artık DÜZELTME'dir: eski kayıt
 *     iptal edilir, sayılar şişmez.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Cekmece } from '../ortak/Cekmece';
import {
  Artan,
  Azalan,
  Ev,
  Kalem,
  Kapi,
  Kilit,
  Konum,
  Onay,
  Saat,
  Takvim,
  Uyari,
  Yildiz,
} from '../ortak/Ikon';
import { sonucEtiketi } from '../ortak/bicim';
import { offlineKimlikUret, useSenkron } from '../depo/senkron';
import { useBugun } from '../depo/bugun';
import { useOturum } from '../depo/oturum';
import { useBildirim } from '../ortak/Bildirim';
import type { GorevBinasi, ZiyaretSonucu } from '../api/tipler';

/** Ekrandaki seçenekler (sözleşme §4.3 + "bina burada değil"). */
const SECENEKLER: Array<{ sonuc: ZiyaretSonucu; Ikon: (p: { boyut?: number }) => JSX.Element }> = [
  { sonuc: 'satis', Ikon: Yildiz },
  { sonuc: 'ilgilenmedi', Ikon: Kapi },
  { sonuc: 'evde_yok', Ikon: Ev },
  { sonuc: 'randevu', Ikon: Takvim },
  { sonuc: 'altyapi_sorunu', Ikon: Uyari },
  { sonuc: 'girilemedi', Ikon: Kilit },
];

const RANDEVU_SECENEKLERI: Array<{ etiket: string; gun: number }> = [
  { etiket: 'Yarın', gun: 1 },
  { etiket: '2 gün sonra', gun: 2 },
  { etiket: 'Bu hafta', gun: 4 },
  { etiket: 'Gelecek hafta', gun: 7 },
];

/** Randevu seçilince bir gün HER ZAMAN seçili gelir — sunucu sessizce atamasın. */
const VARSAYILAN_RANDEVU = 1;

interface Ozellik {
  acik: boolean;
  kapat: () => void;
  bina: GorevBinasi;
  kaydedildi?: () => void;
  /**
   * Düzeltme kipi: bu offline_id'li eski kayıt iptal edilecek. Doluysa başlık
   * ve düğme metni "düzelt" olur.
   */
  duzeltilen?: { offline_id?: string; sonuc?: ZiyaretSonucu; saat?: string } | null;
}

/** Yerel saati dilim bilgisiyle yazar: "2026-09-21T20:08:19+03:00". */
function yerelZamanDamgasi(): string {
  const t = new Date();
  const ofset = -t.getTimezoneOffset();
  const isaret = ofset >= 0 ? '+' : '-';
  const iki = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, '0');
  return (
    `${t.getFullYear()}-${iki(t.getMonth() + 1)}-${iki(t.getDate())}` +
    `T${iki(t.getHours())}:${iki(t.getMinutes())}:${iki(t.getSeconds())}` +
    `${isaret}${iki(ofset / 60)}:${iki(ofset % 60)}`
  );
}

export function SonucCekmecesi({ acik, kapat, bina, kaydedildi, duzeltilen }: Ozellik) {
  const { kaydet } = useSenkron();
  const { binaDurumunuDegistir } = useBugun();
  const { ozetiIlerlet } = useOturum();
  const { goster } = useBildirim();

  const [sonuc, setSonuc] = useState<ZiyaretSonucu | null>(null);
  const [adet, setAdet] = useState(1);
  const [daire, setDaire] = useState('');
  const [not, setNot] = useState('');
  const [notAcik, setNotAcik] = useState(false);
  const [randevuGun, setRandevuGun] = useState<number | null>(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [cikisSoruluyor, setCikisSoruluyor] = useState(false);

  const duzeltmeKipi = Boolean(duzeltilen);
  /** İçeriğe bir şey girilmiş mi? Girilmişse kazara kapanış onay ister. */
  const doluMu = Boolean(sonuc || not.trim() || daire.trim());

  const sifirla = useCallback(() => {
    setSonuc(null);
    setAdet(1);
    setDaire('');
    setNot('');
    setNotAcik(false);
    setRandevuGun(null);
    setCikisSoruluyor(false);
  }, []);

  /* Çekmece kapandığında (herhangi bir yolla) alan temizlenir. */
  useEffect(() => {
    if (!acik) {
      const zaman = window.setTimeout(sifirla, 220);
      return () => window.clearTimeout(zaman);
    }
    return undefined;
  }, [acik, sifirla]);

  const gercektenKapat = useCallback(() => {
    setCikisSoruluyor(false);
    kapat();
  }, [kapat]);

  /**
   * Dışarı dokunmak / Esc: yazılanı SESSİZCE SİLMEZ.
   * Eldivenle, tek elle, güneşte çalışan biri için yanlış dokunma sıradan bir
   * kazadır; kaydı baştan girmek zorunda kalmamalı.
   */
  const kapatmaIstegi = useCallback(() => {
    if (kaydediliyor) return;
    if (doluMu) setCikisSoruluyor(true);
    else gercektenKapat();
  }, [kaydediliyor, doluMu, gercektenKapat]);

  const tekrarTarihi = useMemo(() => {
    if (randevuGun == null) return undefined;
    const t = new Date();
    t.setDate(t.getDate() + randevuGun);
    return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(
      t.getDate(),
    ).padStart(2, '0')}`;
  }, [randevuGun]);

  const sonucSec = useCallback((s: ZiyaretSonucu) => {
    setSonuc(s);
    // Randevuda bir gün HER ZAMAN seçili olsun: müşteriye verilen sözün
    // sisteme yazıldığını satışçı görmeli, sunucu sessizce gün atamasın.
    setRandevuGun(s === 'randevu' ? VARSAYILAN_RANDEVU : null);
  }, []);

  const kaydetBas = useCallback(async () => {
    if (!sonuc || kaydediliyor) return;
    setKaydediliyor(true);

    const konum = await konumuAlKisa();
    try {
      await kaydet({
        offline_id: offlineKimlikUret(),
        bina_serial: bina.bina_serial,
        sonuc,
        satis_adedi: sonuc === 'satis' ? adet : undefined,
        konusulan_daire: daire.trim() || undefined,
        not: not.trim() || undefined,
        lat: konum?.[0] ?? null,
        lon: konum?.[1] ?? null,
        // Saat dilimi BİLGİSİYLE gönderilir. Eskiden UTC gidiyor, sunucu
        // Türkiye saati sanıyor ve her kayıt 3 saat geriye yazılıyordu.
        zaman: yerelZamanDamgasi(),
        tekrar_tarih: sonuc === 'randevu' ? tekrarTarihi : undefined,
        cihaz: navigator.userAgent,
        duzeltilen_offline_id: duzeltilen?.offline_id,
      });

      // Liste beklemeden güncellenir: bina "bitti" olur ve listeden düşer.
      binaDurumunuDegistir(bina.bina_serial, 'tamam');
      // Sayaçlar da beklemeden ilerler; kayıt kuyrukta olsa bile sayı doğrudur.
      if (!duzeltmeKipi) {
        ozetiIlerlet({
          ziyaret: 1,
          satis: sonuc === 'satis' ? adet : 0,
          satisBina: sonuc === 'satis' ? 1 : 0,
        });
      }
      try {
        navigator.vibrate?.(30);
      } catch {
        /* titreşim yoksa sorun değil */
      }
      goster(
        duzeltmeKipi
          ? 'Kayıt düzeltildi'
          : sonuc === 'satis'
            ? `${adet} satış kaydedildi`
            : `${sonucEtiketi(sonuc)} kaydedildi`,
        'basari',
      );
      gercektenKapat();
      kaydedildi?.();
    } finally {
      setKaydediliyor(false);
    }
  }, [
    sonuc,
    kaydediliyor,
    kaydet,
    bina.bina_serial,
    adet,
    daire,
    not,
    tekrarTarihi,
    binaDurumunuDegistir,
    ozetiIlerlet,
    duzeltmeKipi,
    duzeltilen,
    goster,
    gercektenKapat,
    kaydedildi,
  ]);

  return (
    <>
      <Cekmece
        acik={acik}
        kapat={kapatmaIstegi}
        baslik={duzeltmeKipi ? 'Kaydı düzelt' : 'Ne oldu?'}
        altBaslik={
          duzeltmeKipi
            ? `${duzeltilen?.saat ? duzeltilen.saat + ' · ' : ''}${
                duzeltilen?.sonuc ? sonucEtiketi(duzeltilen.sonuc) : 'önceki kayıt'
              } yerine yenisi yazılacak`
            : bina.ad
        }
        kilitli={kaydediliyor}
      >
        <div className="cekmece-govde">
          <div className="sonuc-izgara">
            {SECENEKLER.map(({ sonuc: s, Ikon }) => (
              <button
                key={s}
                className={`sonuc-dugme ${s}${sonuc === s ? ' secili' : ''}`}
                onClick={() => sonucSec(s)}
                aria-pressed={sonuc === s}
              >
                <span className="yuvarlak">
                  <Ikon boyut={22} />
                </span>
                {sonucEtiketi(s)}
              </button>
            ))}
          </div>

          {/* Sahada en sık karşılaşılan istisnalardan biri: bina haritadaki
              yerde değil. Eskiden altı düğmenin altında düz gri bir yazıydı ve
              tıklanabilir görünmüyordu; artık yedinci seçenek. */}
          <button
            className={`sonuc-dugme genis yanlis_adres${sonuc === 'yanlis_adres' ? ' secili' : ''}`}
            onClick={() => sonucSec('yanlis_adres')}
            aria-pressed={sonuc === 'yanlis_adres'}
          >
            <span className="yuvarlak">
              <Konum boyut={22} />
            </span>
            Bina burada değil
          </button>

          {sonuc === 'yanlis_adres' ? (
            <p className="cekmece-ipucu">
              Binanın doğru yerini nota yazarsan haritayı düzeltebiliriz.
            </p>
          ) : null}

          {sonuc === 'satis' ? (
            <div style={{ marginTop: 10 }}>
              <span className="etiket blok">Kaç satış yaptın?</span>
              <div className="sayac-satir">
                <button
                  className="sayac-dugme"
                  onClick={() => setAdet((a) => Math.max(1, a - 1))}
                  disabled={adet <= 1}
                  aria-label="Azalt"
                >
                  <Azalan boyut={26} />
                </button>
                <span className="sayac-deger" aria-live="polite">
                  {adet}
                </span>
                <button
                  className="sayac-dugme"
                  onClick={() => setAdet((a) => Math.min(99, a + 1))}
                  aria-label="Artır"
                >
                  <Artan boyut={26} />
                </button>
              </div>
            </div>
          ) : null}

          {sonuc === 'randevu' ? (
            <div style={{ marginTop: 14 }}>
              <span className="etiket blok">Ne zaman gideceksin?</span>
              <div className="secim-serit">
                {RANDEVU_SECENEKLERI.map((r) => (
                  <button
                    key={r.gun}
                    className={`secim${randevuGun === r.gun ? ' secili' : ''}`}
                    onClick={() => setRandevuGun(r.gun)}
                  >
                    {r.etiket}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {sonuc ? (
            <div style={{ marginTop: 16 }}>
              {notAcik ? (
                <>
                  <label className="alan">
                    <span className="etiket">Hangi daire? (isteğe bağlı)</span>
                    <input
                      className="girdi"
                      value={daire}
                      onChange={(o) => setDaire(o.target.value)}
                      placeholder="Örn. 4/8"
                      inputMode="text"
                      maxLength={40}
                    />
                  </label>
                  <label className="alan">
                    <span className="etiket">Not (isteğe bağlı)</span>
                    <textarea
                      className="girdi"
                      value={not}
                      onChange={(o) => setNot(o.target.value)}
                      placeholder="Kapıcı akşam geleceğini söyledi…"
                      maxLength={500}
                    />
                  </label>
                </>
              ) : (
                <button className="dugme ikincil" onClick={() => setNotAcik(true)}>
                  <Kalem boyut={20} />
                  Not ekle
                </button>
              )}
            </div>
          ) : (
            <p className="cekmece-ipucu orta">
              <Saat boyut={15} />
              Önce yukarıdan bir sonuç seç
            </p>
          )}
        </div>

        {/* Ekranın altına YAPIŞIK: 360 px'lik telefonda not alanı açıkken
            "Kaydet" ekranın dışında kalıyor ve kaydırılabildiğine dair hiçbir
            işaret olmuyordu. */}
        <div className="cekmece-ayak">
          {sonuc === 'randevu' && randevuGun != null ? (
            <p className="cekmece-ozet">
              {RANDEVU_SECENEKLERI.find((r) => r.gun === randevuGun)?.etiket} tekrar gelinecek
            </p>
          ) : null}
          <button
            className="dugme birincil buyuk"
            onClick={kaydetBas}
            disabled={!sonuc || kaydediliyor}
          >
            {kaydediliyor ? (
              'Kaydediliyor…'
            ) : (
              <>
                <Onay boyut={22} />
                {duzeltmeKipi ? 'Düzeltmeyi kaydet' : 'Kaydet'}
              </>
            )}
          </button>
          <button className="dugme sessiz" onClick={kapatmaIstegi} disabled={kaydediliyor}>
            Vazgeç
          </button>
        </div>
      </Cekmece>

      <Cekmece
        acik={cikisSoruluyor}
        kapat={() => setCikisSoruluyor(false)}
        baslik="Kaydetmeden çıkılsın mı?"
        altBaslik="Seçtiğin sonuç ve yazdığın not silinecek."
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <button className="dugme ikincil buyuk" onClick={() => setCikisSoruluyor(false)}>
            Vazgeç, geri dön
          </button>
          <button className="dugme tehlike buyuk" onClick={gercektenKapat}>
            Evet, çıkışı onayla
          </button>
        </div>
      </Cekmece>
    </>
  );
}

/** Konum varsa kayda eklenir; yoksa beklemeden devam edilir. */
function konumuAlKisa(): Promise<[number, number] | null> {
  return new Promise((coz) => {
    if (!('geolocation' in navigator)) {
      coz(null);
      return;
    }
    let bitti = false;
    const sayac = setTimeout(() => {
      if (!bitti) {
        bitti = true;
        coz(null);
      }
    }, 2500);
    navigator.geolocation.getCurrentPosition(
      (k) => {
        if (bitti) return;
        bitti = true;
        clearTimeout(sayac);
        coz([k.coords.latitude, k.coords.longitude]);
      },
      () => {
        if (bitti) return;
        bitti = true;
        clearTimeout(sayac);
        coz(null);
      },
      { enableHighAccuracy: false, timeout: 2500, maximumAge: 120000 },
    );
  });
}
