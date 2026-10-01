/**
 * Bugün — günün bina listesi.
 *
 * Tasarım kuralı: ekranı açan kişi tek bakışta üç şeyi görür.
 *   1) kaç bina kaldı,  2) sıradaki bina hangisi,  3) kaydım gitti mi.
 * Biten binalar listeden çıkar ("Bitenler" başlığının altına iner) ki gözü
 * sadece kalanlara baksın.
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import { useBugun } from '../depo/bugun';
import { useOturum } from '../depo/oturum';
import { useBildirim } from '../ortak/Bildirim';
import { DemoSeridi, DurumSeridi } from '../ortak/DurumSeridi';
import { BosDurum, Sayfa, SayfaGovde, Ust } from '../ortak/Sayfa';
import { Ileri, Onay, Yenile } from '../ortak/Ikon';
import {
  adresSatiri,
  binaBasligi,
  kapiRozeti,
  mesafe,
  sayi,
  tarihUzun,
  yerSatiri,
} from '../ortak/bicim';
import { useCevrimici } from '../depo/cevrimici';
import { git } from '../yol/rota';
import type { GorevBinasi } from '../api/tipler';

export function Bugun() {
  const { gorev, asama, yenile, yeniListe, listeOlusturuluyor, onbellekten } = useBugun();
  const { ozet, kullanici } = useOturum();
  const { goster } = useBildirim();
  const cevrimici = useCevrimici();
  const [bitenlerAcik, setBitenlerAcik] = useState(false);

  const { cekOzellikleri, cekMesafesi, yenileniyor } = useAsagiCek(async () => {
    await yenile();
  });

  const binalar = gorev?.binalar ?? [];
  // Görev durumu ('bekliyor' | 'tamam' | 'atlandi') — bina durumu DEĞİL.
  const kalanlar = useMemo(() => binalar.filter((b) => b.gorev_durum === 'bekliyor'), [binalar]);
  // "Bitenler" GÜNÜN tamamını gösterir: açık listede bitenler + aynı gün daha
  // önce bitirilmiş listelerin binaları. İlerleme sayacı (tamam/toplam) yalnız
  // AÇIK listeyi sayar, yoksa "25 / 25" deyip yeni listeyi gizlerdi.
  const bitenler = useMemo(() => {
    const acik = binalar.filter((b) => b.gorev_durum !== 'bekliyor');
    const onceki = gorev?.onceki_binalar ?? [];
    const gorulen = new Set(acik.map((b) => b.bina_serial));
    return [...onceki.filter((b) => !gorulen.has(b.bina_serial)), ...acik];
  }, [binalar, gorev?.onceki_binalar]);
  const toplam = binalar.length;
  const tamam = binalar.filter((b) => b.gorev_durum !== 'bekliyor').length;
  const satis = ozet?.bugun.satis ?? 0;
  // Günün TOPLAM ziyareti (ziyaret kayıtlarından); ikinci liste alınınca
  // görev sayacı sıfırlanıyor ama bu sayı sıfırlanmıyor.
  const gunZiyaret = ozet?.bugun.ziyaret ?? 0;

  const listeIste = useCallback(async () => {
    try {
      await yeniListe();
      goster('Yeni liste hazır', 'basari');
    } catch (h) {
      // Sebep SÖYLENİR. Eskiden internet yokken düğmeye basınca hiçbir şey
      // olmuyordu: ne hata, ne bildirim; kullanıcı bozuk sanıp üst üste basıyordu.
      goster(
        h instanceof Error ? h.message : 'Liste alınamadı, bağlantıyı kontrol edin',
        'uyari',
      );
    }
  }, [yeniListe, goster]);

  const altYazi = [tarihUzun(gorev?.tarih), kullanici?.bolge_adi ?? null]
    .filter(Boolean)
    .join(' · ');

  return (
    <Sayfa>
      <Ust baslik="Bugün" altYazi={altYazi} />
      <SayfaGovde>
        <div {...cekOzellikleri}>
          <div className="yenile-alani" style={{ height: yenileniyor ? 44 : cekMesafesi }}>
            {yenileniyor ? (
              <>
                <span className="donen" />
                <span>Yenileniyor…</span>
              </>
            ) : cekMesafesi > 8 ? (
              <>
                <Yenile boyut={18} />
                <span>{cekMesafesi > 70 ? 'Bırak, yenilensin' : 'Aşağı çek'}</span>
              </>
            ) : null}
          </div>

          <DemoSeridi />
          <DurumSeridi />

          {asama === 'yukleniyor' && !gorev ? (
            <Iskelet />
          ) : toplam === 0 ? (
            <BosDurum
              simge="📍"
              baslik="Bugün için liste yok"
              aciklama="Algoritma bölgendeki en yüksek potansiyelli binalardan bir tur hazırlasın."
            >
              <button
                className="dugme birincil buyuk"
                onClick={listeIste}
                disabled={listeOlusturuluyor || !cevrimici}
              >
                {listeOlusturuluyor ? 'Hazırlanıyor…' : 'Bugünün listesini al'}
              </button>
              {!cevrimici ? (
                <p className="dugme-sebep">Liste almak için internet gerekiyor.</p>
              ) : null}
            </BosDurum>
          ) : (
            <>
              <IlerlemeKarti toplam={toplam} tamam={tamam} satis={satis} gunZiyaret={gunZiyaret} />

              {gorev?.uyari ? (
                <div className="serit uyari-serit" role="status">
                  <Yenile boyut={18} />
                  <span>{gorev.uyari}</span>
                </div>
              ) : null}

              {onbellekten && !cevrimici ? (
                <p className="kucuk-not">Telefondaki kopya gösteriliyor.</p>
              ) : null}

              {kalanlar.length === 0 ? (
                <BosDurum
                  simge="🎉"
                  baslik="Liste bitti"
                  aciklama={`Bugün ${sayi(tamam)} binayı gezdin. Devam etmek istersen yeni bir tur alabilirsin.`}
                >
                  <button
                    className="dugme birincil buyuk"
                    onClick={listeIste}
                    disabled={listeOlusturuluyor || !cevrimici}
                  >
                    {listeOlusturuluyor ? 'Hazırlanıyor…' : 'Yeni liste al'}
                  </button>
                  {!cevrimici ? (
                    <p className="dugme-sebep">Liste almak için internet gerekiyor.</p>
                  ) : null}
                </BosDurum>
              ) : (
                <>
                  <h2 className="bolum-baslik">Sıradakiler</h2>
                  {kalanlar.map((bina) => (
                    <BinaKarti key={bina.bina_serial} bina={bina} />
                  ))}
                </>
              )}

              {bitenler.length > 0 ? (
                <>
                  <button
                    className="bolum-baslik"
                    onClick={() => setBitenlerAcik((a) => !a)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      width: '100%',
                      minHeight: 44,
                    }}
                    aria-expanded={bitenlerAcik}
                  >
                    <Onay boyut={15} />
                    Bitenler ({sayi(bitenler.length)})
                    <span style={{ marginLeft: 'auto', transform: bitenlerAcik ? 'rotate(90deg)' : 'none', display: 'inline-flex' }}>
                      <Ileri boyut={16} />
                    </span>
                  </button>
                  {bitenlerAcik
                    ? bitenler.map((bina) => <BinaKarti key={bina.bina_serial} bina={bina} />)
                    : null}
                </>
              ) : null}
            </>
          )}
        </div>
      </SayfaGovde>
    </Sayfa>
  );
}

/* ------------------------------ İlerleme ------------------------------ */

/**
 * İlerleme kartı.
 *
 * `toplam`/`tamam` BU LİSTEYE aittir. Gün içinde ikinci bir liste alındığında
 * sunucu önceki görevi kapatıp yenisini açıyor, dolayısıyla sayaç 0'dan
 * başlıyor: sabah 25 bina gezmiş satışçı ekranda "0 / 25" görüp bugünkü işinin
 * silindiğini sanıyordu. `gunZiyaret` ise ziyaret kayıtlarından gelen GÜNLÜK
 * toplamdır; listeden büyükse ayrıca yazılır ve emek görünür kalır.
 */
function IlerlemeKarti({
  toplam,
  tamam,
  satis,
  gunZiyaret,
}: {
  toplam: number;
  tamam: number;
  satis: number;
  gunZiyaret: number;
}) {
  const kalan = Math.max(0, toplam - tamam);
  const oran = toplam ? tamam / toplam : 0;
  const gunFarkli = gunZiyaret > tamam;
  return (
    <div className="ilerleme-kart">
      <div className="ilerleme-ust">
        <div>
          <div className="ilerleme-sayi">
            {sayi(tamam)} <small>/ {sayi(toplam)} bina</small>
          </div>
          {gunFarkli ? (
            <div className="ilerleme-gun">Bugün toplam {sayi(gunZiyaret)} bina gezdin</div>
          ) : null}
        </div>
        <div className="ilerleme-etiket">
          {kalan === 0 ? 'Hepsi bitti' : `${sayi(kalan)} bina kaldı`}
          {satis > 0 ? (
            <div style={{ color: 'var(--yesil)', fontWeight: 600 }}>{sayi(satis)} satış</div>
          ) : null}
        </div>
      </div>
      <div className={`cubuk${oran >= 1 ? ' yesil' : ''}`}>
        <span style={{ width: `${Math.round(oran * 100)}%` }} />
      </div>
    </div>
  );
}

/* ------------------------------ Kart ------------------------------ */

/**
 * Liste kartı.
 *
 * Binayı sokakta bulmayı sağlayan tek bilgi SOKAK + KAPI NUMARASI'dır ve
 * eskiden tam da o satır kesiliyordu ("İbni Sina Cd. No …"). Aynı sitedeki
 * blokların başlıkları birebir aynı olduğu için kartları ayıran şey de buydu.
 * Artık: 1. satır sokak (kalın, gerekirse iki satır), kapı numarası ayrı bir
 * rozette (asla kesilmez), 2. satır site + mahalle (kesilebilir).
 */
function BinaKarti({ bina }: { bina: GorevBinasi }) {
  const bitti = bina.gorev_durum !== 'bekliyor';
  const uzaklik = mesafe(bina.mesafe_m);
  const bosKapi = bina.firsat ?? 0;
  const no = kapiRozeti(bina);
  const yer = yerSatiri(bina);

  return (
    <button
      className={`liste-kart${bitti ? ' bitti' : ''}`}
      onClick={() => git(`/bina/${encodeURIComponent(bina.bina_serial)}`)}
    >
      <span
        className={`sira-rozet${bitti ? (bina.gorev_durum === 'atlandi' ? ' atlandi' : ' tamam') : ''}`}
      >
        {bitti ? <Onay boyut={20} /> : bina.sira}
      </span>
      <span className="kart-govde">
        <span className="kart-yol">
          <span className="kart-sokak">{adresSatiri(bina) || binaBasligi(bina)}</span>
          {no ? <span className="kart-no">{no}</span> : null}
        </span>
        <span className="kart-adres">{yer || binaBasligi(bina)}</span>
        <span className="rozetler">
          {bosKapi > 0 ? <span className="rozet firsat">{sayi(bosKapi)} boş kapı</span> : null}
          <span className="rozet">{sayi(bina.daire ?? bina.res_hp ?? 0)} daire</span>
        </span>
      </span>
      <span className="kart-sag">
        {uzaklik ? <span className="kart-mesafe">{uzaklik}</span> : null}
        <Ileri boyut={20} />
      </span>
    </button>
  );
}

function Iskelet() {
  return (
    <div style={{ paddingTop: 12 }} aria-hidden="true">
      <div className="iskelet" style={{ height: 92, marginBottom: 16 }} />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="iskelet" style={{ height: 104, marginBottom: 12 }} />
      ))}
    </div>
  );
}

/* ------------------------------ Aşağı çekip yenileme ------------------------------ */

function useAsagiCek(calistir: () => Promise<void>) {
  const [cekMesafesi, setCekMesafesi] = useState(0);
  const [yenileniyor, setYenileniyor] = useState(false);
  const baslangicRef = useRef<number | null>(null);

  const dokunmaBasladi = useCallback((olay: React.TouchEvent) => {
    if (yenileniyor) return;
    const kaydirma = document.scrollingElement?.scrollTop ?? window.scrollY;
    baslangicRef.current = kaydirma <= 0 ? olay.touches[0].clientY : null;
  }, [yenileniyor]);

  const dokunmaHareket = useCallback((olay: React.TouchEvent) => {
    if (baslangicRef.current == null || yenileniyor) return;
    const fark = olay.touches[0].clientY - baslangicRef.current;
    if (fark <= 0) {
      setCekMesafesi(0);
      return;
    }
    // Sürtünme hissi: parmak kadar hızlı inmesin.
    setCekMesafesi(Math.min(96, fark * 0.5));
  }, [yenileniyor]);

  const dokunmaBitti = useCallback(async () => {
    const mesafeDegeri = cekMesafesi;
    baslangicRef.current = null;
    setCekMesafesi(0);
    if (mesafeDegeri > 70 && !yenileniyor) {
      setYenileniyor(true);
      try {
        await calistir();
      } finally {
        setYenileniyor(false);
      }
    }
  }, [cekMesafesi, yenileniyor, calistir]);

  return {
    cekMesafesi,
    yenileniyor,
    cekOzellikleri: {
      onTouchStart: dokunmaBasladi,
      onTouchMove: dokunmaHareket,
      onTouchEnd: dokunmaBitti,
      onTouchCancel: dokunmaBitti,
    },
  };
}
