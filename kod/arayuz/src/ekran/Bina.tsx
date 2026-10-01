/**
 * Bina — tek binanın kartı.
 *
 * Ekranda iki büyük düğme var, başka hiçbir şey yok: "Yol tarifi" ve
 * "Sonucu işle". Bilgiler (boş kapı, daire, kat, abone) tek bakışta okunur.
 * Bina bugünün listesindeyse veriler telefondan gelir; yani internet olmadan
 * da bu ekran eksiksiz açılır.
 */

import { useCallback, useEffect, useState } from 'react';
import { binaAyrinti } from '../api/uclar';
import { useBugun } from '../depo/bugun';
import { Cekmece } from '../ortak/Cekmece';
import { DurumSeridi } from '../ortak/DurumSeridi';
import { GeriAl, Ileri, Konum, Onay, Pusula, Yol } from '../ortak/Ikon';
import { Sayfa, SayfaGovde, Ust } from '../ortak/Sayfa';
import {
  DURUM_ETIKETLERI,
  adresSatiri,
  binaBasligi,
  durumRengi,
  gunMetni,
  kapiRozeti,
  mesafe,
  saat,
  sayi,
  sonucEtiketi,
  tamAdres,
  tarihSaat,
  yerSatiri,
} from '../ortak/bicim';
import {
  SAGLAYICI_ADLARI,
  haritayiAc,
  kayitliSaglayici,
  saglayiciSirasi,
  saglayiciyiKaydet,
  type HaritaSaglayici,
} from '../ortak/yolTarifi';
import { git, useGeri } from '../yol/rota';
import { SonucCekmecesi } from './SonucCekmecesi';
import { BinaKimlik } from '../ortak/BinaKimlik';
import { KaliteNotlari, TicketOzeti } from '../ortak/BinaNotlari';
import { TicketMetniCekmecesi } from './TicketMetniCekmecesi';
import type { BinaAyrintisi, BinaDurumu, GorevBinasi } from '../api/tipler';

export function Bina({ serial }: { serial: string }) {
  const geri = useGeri('/bugun');
  const { binaBul } = useBugun();
  const listeBinasi = binaBul(serial);

  const [ayrinti, setAyrinti] = useState<BinaAyrintisi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(!listeBinasi);
  const [sonucAcik, setSonucAcik] = useState(false);
  const [duzeltmeAcik, setDuzeltmeAcik] = useState(false);
  const [haritaSecimAcik, setHaritaSecimAcik] = useState(false);
  const [yeniZiyaretSoruluyor, setYeniZiyaretSoruluyor] = useState(false);
  const [ticketAcik, setTicketAcik] = useState(false);

  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        const veri = await binaAyrinti(serial);
        if (!iptal) setAyrinti(veri);
      } catch {
        /* çevrimdışıysak listedeki bilgiyle devam ederiz */
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => {
      iptal = true;
    };
  }, [serial]);

  const bina: GorevBinasi | null = listeBinasi ?? (ayrinti ? { ...(ayrinti.bina as GorevBinasi), sira: 0, gorev_durum: 'bekliyor' } : null);

  const yolTarifi = useCallback(() => {
    if (!bina) return;
    const kayitli = kayitliSaglayici();
    if (kayitli) haritayiAc(kayitli, bina.lat, bina.lon);
    else setHaritaSecimAcik(true);
  }, [bina]);

  const saglayiciSec = useCallback(
    (saglayici: HaritaSaglayici) => {
      if (!bina) return;
      saglayiciyiKaydet(saglayici);
      setHaritaSecimAcik(false);
      haritayiAc(saglayici, bina.lat, bina.lon);
    },
    [bina],
  );

  if (!bina) {
    return (
      <Sayfa>
        <Ust baslik="Bina" geriyeGit={geri} ortala />
        <SayfaGovde sekmesiz>
          <div style={{ paddingTop: 20 }}>
            {yukleniyor ? (
              <div className="iskelet" style={{ height: 180 }} aria-hidden="true" />
            ) : (
              <p style={{ color: 'var(--metin-2)' }}>
                Bu bina bulunamadı. Listeye dönüp tekrar deneyin.
              </p>
            )}
          </div>
        </SayfaGovde>
      </Sayfa>
    );
  }

  const bitti = bina.gorev_durum !== 'bekliyor';
  /** Bugünün en son kaydı — "Kaydı düzelt" bunun yerine yenisini yazar. */
  const sonZiyaret = (() => {
    const bugun = gunMetni();
    const liste = (ayrinti?.ziyaretler ?? []).filter((z) => (z.zaman ?? '').slice(0, 10) === bugun);
    const son = liste[0];
    if (!son) return null;
    return { offline_id: son.offline_id, sonuc: son.sonuc, saat: son.zaman ? saat(son.zaman) : undefined };
  })();
  // Binanın genel durumu (rozet) — bugünün listesindeki hâli değil.
  const durum: BinaDurumu | null = ayrinti?.bina?.durum ?? bina.durum ?? null;
  const uzaklik = mesafe(bina.mesafe_m);
  const gecmis = ayrinti?.ziyaretler ?? [];

  return (
    <Sayfa>
      <Ust
        baslik={bina.sira ? `${bina.sira}. bina` : 'Bina'}
        geriyeGit={geri}
        ortala
        sag={uzaklik ? <span className="rozet">{uzaklik}</span> : undefined}
      />

      <SayfaGovde sekmesiz>
        <DurumSeridi />

        <div style={{ padding: '16px 0 4px' }}>
          <h2 style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-0.035em', margin: '0 0 6px' }}>
            {binaBasligi(bina)}
          </h2>
          <p style={{ color: 'var(--metin-2)', fontSize: 16, margin: 0 }}>{tamAdres(bina)}</p>

          <div className="rozetler" style={{ marginTop: 12 }}>
            {/* Son tur raporunda olmayan bina silinmez, pasif olur (sözleşme §7.0). */}
            {ayrinti?.bina?.pasif ? <span className="rozet amber">Pasif · son tur raporunda yok</span> : null}
            {bitti ? (
              <span className="rozet yesil">
                <Onay boyut={14} /> Bugün işlendi
              </span>
            ) : null}
            {durum && durum !== 'bekliyor' && durum !== 'planli' ? (
              <span className={`rozet ${durumRengi(durum)}`}>{DURUM_ETIKETLERI[durum]}</span>
            ) : null}
            {bina.site_adi && bina.site_adi !== bina.ad ? (
              <span className="rozet">{bina.site_adi}</span>
            ) : null}
          </div>
        </div>

        <div className="bilgi-izgara" style={{ marginTop: 14 }}>
          <div className="bilgi vurgu">
            <div className="etiket">Boş kapı</div>
            <div className="deger">{sayi(bina.firsat ?? 0)}</div>
          </div>
          <div className="bilgi">
            <div className="etiket">Daire</div>
            <div className="deger">{sayi(bina.daire ?? bina.res_hp ?? 0)}</div>
          </div>
          <div className="bilgi">
            <div className="etiket">Kat</div>
            <div className="deger">{bina.kat ? sayi(bina.kat) : '—'}</div>
          </div>
          <div className="bilgi">
            <div className="etiket">Abone</div>
            <div className="deger">{sayi(bina.aktif_res ?? 0)}</div>
          </div>
        </div>

        {/* Sistemin bu kayıtta bulduğu tutarsızlık ("abone HP'den fazla → boş kapı 0
            sayıldı" gibi): sayıların hemen altında, neden öyle göründüğünü söyler. */}
        <KaliteNotlari notlar={ayrinti?.bina?.kalite ?? bina.kalite} enFazla={2} />

        <Komsular bina={bina} />

        {/* Ticket'lar kimlik kartından önce: "bu binada zaten açık ticket var mı?" sorusu
            kimliklerin uzun listesinin altında kaybolmasın. */}
        <TicketOzeti ticketlar={ayrinti ? (ayrinti.ticketlar ?? []) : undefined} ticketAc={() => setTicketAcik(true)} />

        {gecmis.length > 0 ? (
          <>
            <h3 className="bolum-baslik">Geçmiş ziyaretler</h3>
            <div className="kart">
              {gecmis
                .slice()
                .reverse()
                .map((z, i) => (
                  <div key={`${z.zaman}-${i}`} className="satir">
                    <span className="ad">
                      {z.sonuc_etiket ?? sonucEtiketi(z.sonuc)}
                      {z.satis_adedi ? ` · ${sayi(z.satis_adedi)} satış` : ''}
                      {z.notu ?? z.not ? (
                        <span className="satir-not">{z.notu ?? z.not}</span>
                      ) : null}
                    </span>
                    <span className="deger">{tarihSaat(z.zaman)}</span>
                  </div>
                ))}
            </div>
          </>
        ) : null}

        {/* Kimlikler ve koordinat: tek dokunuşla kopyalanır. Ticket metni yukarıdaki
            "Ticket aç"tan üretilir (konu seçilir; açık ticket varsa önce o görünür). */}
        <BinaKimlik bina={{ ...bina, ...(ayrinti?.bina ?? {}) }} ticket={false} />

        {/* "Bina nerede": dokununca harita uygulaması KOORDİNATLA açılır. */}
        <button className="konum-onizleme" onClick={yolTarifi}>
          <span className="konum-imleci" aria-hidden="true">
            <Konum boyut={26} />
          </span>
          <span className="konum-yazi">
            <span className="konum-baslik">{adresSatiri(bina)}</span>
            <span className="konum-alt">
              {[kapiRozeti(bina), yerSatiri(bina)].filter(Boolean).join(' · ')}
            </span>
          </span>
          <Ileri boyut={20} />
        </button>
      </SayfaGovde>

      <div className="eylem-serit">
        <button className="dugme ikincil buyuk" onClick={yolTarifi}>
          <Yol boyut={22} />
          Yol tarifi
        </button>
        {bitti ? (
          // Bugün işlenmiş binada en büyük düğme "Tekrar işle" idi ve basınca
          // İKİNCİ bir ziyaret ekleyip bütün sayıları şişiriyordu. Yanlış
          // işlendiyse yapılması gereken şey düzeltmek; yeni bir ziyaret eklemek
          // ayrı, ikincil ve onaylı bir iş.
          <button className="dugme birincil buyuk" onClick={() => setDuzeltmeAcik(true)}>
            <GeriAl boyut={22} />
            Kaydı düzelt
          </button>
        ) : (
          <button className="dugme birincil buyuk" onClick={() => setSonucAcik(true)}>
            <Onay boyut={22} />
            Sonucu işle
          </button>
        )}
      </div>

      {bitti ? (
        <button className="dugme sessiz ek-ziyaret" onClick={() => setYeniZiyaretSoruluyor(true)}>
          Yeni bir ziyaret ekle
        </button>
      ) : null}

      <TicketMetniCekmecesi
        acik={ticketAcik}
        kapat={() => setTicketAcik(false)}
        bina={{ ...bina, ...(ayrinti?.bina ?? {}) }}
        ticketlar={ayrinti?.ticketlar}
      />

      <SonucCekmecesi
        acik={sonucAcik}
        kapat={() => setSonucAcik(false)}
        bina={bina}
        kaydedildi={geri}
      />

      <SonucCekmecesi
        acik={duzeltmeAcik}
        kapat={() => setDuzeltmeAcik(false)}
        bina={bina}
        kaydedildi={geri}
        duzeltilen={sonZiyaret}
      />

      <Cekmece
        acik={yeniZiyaretSoruluyor}
        kapat={() => setYeniZiyaretSoruluyor(false)}
        baslik="Yeni ziyaret eklensin mi?"
        altBaslik={
          sonZiyaret
            ? `Bu binaya ${sonZiyaret.saat ? sonZiyaret.saat + "'de " : ''}${
                sonZiyaret.sonuc ? sonucEtiketi(sonZiyaret.sonuc) : 'bir sonuç'
              } işlemiştin. Yanlış girdiysen "Kaydı düzelt" de.`
            : 'Bu binaya bugün zaten bir sonuç işlendi.'
        }
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <button
            className="dugme ikincil buyuk"
            onClick={() => {
              setYeniZiyaretSoruluyor(false);
              setDuzeltmeAcik(true);
            }}
          >
            <GeriAl boyut={20} />
            Kaydı düzelt
          </button>
          <button
            className="dugme birincil buyuk"
            onClick={() => {
              setYeniZiyaretSoruluyor(false);
              setSonucAcik(true);
            }}
          >
            Evet, yeni ziyaret ekle
          </button>
          <button className="dugme sessiz" onClick={() => setYeniZiyaretSoruluyor(false)}>
            Vazgeç
          </button>
        </div>
      </Cekmece>

      <Cekmece
        acik={haritaSecimAcik}
        kapat={() => setHaritaSecimAcik(false)}
        baslik="Hangi harita?"
        altBaslik="Seçimin hatırlanır, bir daha sorulmaz."
      >
        <div style={{ display: 'grid', gap: 10 }}>
          {saglayiciSirasi().map((s) => (
            <button key={s} className="dugme ikincil buyuk" onClick={() => saglayiciSec(s)}>
              <Pusula boyut={22} />
              {SAGLAYICI_ADLARI[s]}
            </button>
          ))}
          <button className="dugme sessiz" onClick={() => setHaritaSecimAcik(false)}>
            Vazgeç
          </button>
        </div>
      </Cekmece>
    </Sayfa>
  );
}

/**
 * "Aynı sitede 3 bina daha var" / "Sıradaki bina".
 *
 * Sahada en çok vakit kaybettiren şey aynı siteye iki kere gitmektir. Satışçı
 * bir bloktayken komşu blokların da bugünkü listede olduğunu görürse hepsini
 * tek seferde bitirir. Liste bittiyse sıradaki binayı gösteririz.
 */
function Komsular({ bina }: { bina: GorevBinasi }) {
  const { gorev } = useBugun();
  const binalar = gorev?.binalar ?? [];

  const ayniSite = binalar.filter(
    (b) =>
      b.bina_serial !== bina.bina_serial &&
      b.gorev_durum === 'bekliyor' &&
      Boolean(bina.site_adi) &&
      b.site_adi === bina.site_adi,
  );

  const sonraki = binalar
    .filter((b) => b.gorev_durum === 'bekliyor' && b.bina_serial !== bina.bina_serial)
    .sort((a, b) => a.sira - b.sira)[0];

  if (ayniSite.length > 0) {
    return (
      <>
        <h3 className="bolum-baslik">Aynı sitede {sayi(ayniSite.length)} bina daha</h3>
        <div className="kart">
          {ayniSite.slice(0, 4).map((k) => (
            <button
              key={k.bina_serial}
              className="satir"
              onClick={() => git(`/bina/${encodeURIComponent(k.bina_serial)}`)}
            >
              <span className="sira-rozet" style={{ width: 32, height: 32, fontSize: 15 }}>
                {k.sira}
              </span>
              <span className="ad">{binaBasligi(k)}</span>
              <span className="deger">{sayi(k.firsat ?? 0)} boş</span>
              <Ileri boyut={18} />
            </button>
          ))}
        </div>
        <p style={{ color: 'var(--metin-2)', fontSize: 14.5, margin: '10px 2px 0' }}>
          Buradayken hepsini bitirirsen bir daha gelmen gerekmez.
        </p>
      </>
    );
  }

  if (!sonraki) return null;

  return (
    <>
      <h3 className="bolum-baslik">Sıradaki bina</h3>
      <button
        className="liste-kart"
        onClick={() => git(`/bina/${encodeURIComponent(sonraki.bina_serial)}`)}
      >
        <span className="sira-rozet">{sonraki.sira}</span>
        <span className="kart-govde">
          <span className="kart-ad">{binaBasligi(sonraki)}</span>
          <span className="kart-adres">{adresSatiri(sonraki)}</span>
          <span className="rozetler">
            <span className="rozet firsat">{sayi(sonraki.firsat ?? 0)} boş kapı</span>
          </span>
        </span>
        <span className="kart-ok">
          <Ileri boyut={20} />
        </span>
      </button>
    </>
  );
}
