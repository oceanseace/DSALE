/**
 * Teknik — "İşlerim" (OPERASYON_V2_SPEC §6.9; F7, F8). Telefon önce.
 *
 *   #/islerim            sıralı liste: Şu an · Sıradaki · Sonra · Sonraki günler · Bitenler
 *   #/islerim/<is_no>    iş ekranı: tek büyük düğme (Yola çıktım → İşe başladım → Bitti)
 *
 * Tasarım kuralı satışçının "Bugün"üyle aynı: ekranı açan kişi tek bakışta
 * sıradaki işi, kalan süreyi ve yaptıklarının gidip gitmediğini görür. Biten iş
 * listeden iner. Sinyal yoksa liste telefondaki kopyadan (24 saatten yeni)
 * açılır, düğmeler kuyruğa yazılır.
 */

import { useEffect, useState } from 'react';
import { useOturum } from '../depo/oturum';
import { useCevrimici } from '../depo/cevrimici';
import { useBildirim } from '../ortak/Bildirim';
import { useKutlamaGecisi } from '../ortak/Kutlama';
import { BaglantiSeridi } from '../ortak/BaglantiSeridi';
import { BosDurum, Sayfa, SayfaGovde, Ust } from '../ortak/Sayfa';
import { SureHapi } from '../ortak/SureHapi';
import { Rozet } from '../ortak/Rozet';
import { Ileri, Onay, Uyari, Yenile } from '../ortak/Ikon';
import { EkranCumlesi } from '../ortak/IlkIpucu';
import { git, useAdres, yoluCoz } from '../yol/rota';
import type { IsAyrinti, IsSatir } from '../is/tipler';
import { DURUM_ETIKET } from '../is/tipler';
import {
  duyurulariDinle,
  gorulduIsaretle,
  useIslerim,
  yenile,
  type IslerimDeposu,
  type OfiseDonen,
} from './depo';
import { isKuyrugunuGonder } from './kuyruk';
import { dilimMetni, durumSuresi, gunBasligi, kalanBilgisi, saatMetni, yerMetni } from './bicim';
import { IsEkrani } from './IsEkrani';
import { useDakika } from './kancalar';
import './teknik.css';

export function Islerim() {
  const adres = useAdres();
  const { deger } = yoluCoz(adres);
  const { kullanici } = useOturum();
  const depo = useIslerim(kullanici?.id ?? null);
  useDuyurular();
  return deger ? <IsEkrani isNo={deger} depo={depo} /> : <Liste depo={depo} />;
}

/** Depodan gelen duyurular: yeni iş, reddedilen işlem. */
function useDuyurular() {
  const { goster } = useBildirim();
  useEffect(
    () =>
      duyurulariDinle((d) => {
        if (d.tur === 'yeni') goster(d.sayi === 1 ? '1 yeni iş geldi' : `${d.sayi} yeni iş geldi`, 'bilgi', { sureMs: 5000 });
        else if (d.tur === 'dustu') goster(d.mesaj, 'uyari', { sureMs: 8000 });
      }),
    [goster],
  );
}

/* ------------------------------ Liste ------------------------------ */

function Liste({ depo }: { depo: IslerimDeposu }) {
  const { gorunum, asama, yanit, onbellekten, guncelleme, baglantiYok, bekleyenler, yeniler, hata } = depo;
  const { simdiki, bugun, sonraki, bitenler, ofiseDonenler } = gorunum;
  const [bitenlerAcik, setBitenlerAcik] = useState(false);
  const simdi = useDakika();
  const cevrimici = useCevrimici();

  const acik = [...simdiki, ...bugun, ...sonraki];
  const btk = acik.filter((x) => x.serit === 'BTK').length;
  const ilkRandevu = bugun.find((x) => x.randevu)?.randevu?.bas;

  /* İş ekrana girdiğinde "gördü" (1,5 sn sonra, sekme görünürken). */
  useEffect(() => {
    if (asama === 'hazir' && !onbellekten) gorulduIsaretle(acik);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yanit, onbellekten, asama]);

  /* Küçük sevinçler (EK-6): bugünün BTK'ları ve bütün işler bitince. */
  const bugunBtkBitti = bitenler.some((x) => x.serit === 'BTK');
  useKutlamaGecisi(asama === 'hazir' ? bugunBtkBitti && btk === 0 : null, 'Bugünün bütün BTK işleri çözüldü');
  useKutlamaGecisi(asama === 'hazir' ? bitenler.length > 0 && acik.length === 0 : null, 'Bugünün işleri bitti');

  const ozet = [
    `${acik.length} iş`,
    btk ? `${btk} BTK` : null,
    ilkRandevu ? `ilki ${saatMetni(ilkRandevu)}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const bekleyenSayisi = bekleyenler.length;
  const siradaki = bugun[0] ?? null;
  const sonra = bugun.slice(1);
  const yeniSayisi = acik.filter((x) => yeniler.has(x.is_no)).length;

  return (
    <Sayfa>
      <Ust baslik="İşlerim" sag={<span className="tk-tarih">{gunBasligi(new Date(simdi))}</span>} />
      <SayfaGovde>
        <div className="tk">
          <EkranCumlesi anahtar="islerim">Size atanan işler sırayla burada. Sıradakine gidin.</EkranCumlesi>
          <BaglantiSeridi ek={bekleyenSayisi ? 'yaptıklarınız telefonda bekliyor' : undefined} />

          {asama !== 'hazir' && !yanit ? (
            <Iskelet />
          ) : !yanit ? (
            <BosDurum simge="📶" baslik="Liste alınamadı" aciklama={hata ?? 'Bağlantıyı kontrol edip yeniden deneyin.'}>
              <button className="dugme birincil" onClick={() => void yenile()}>
                <Yenile boyut={20} />
                Yeniden dene
              </button>
            </BosDurum>
          ) : (
            <>
              <div className="tk-ozet" aria-live="polite">
                <span className="tk-ozet-sayi">{acik.length ? ozet : 'Açık iş yok'}</span>
                <Tazelik
                  onbellekten={onbellekten}
                  guncelleme={guncelleme}
                  baglantiYok={baglantiYok || !cevrimici}
                  simdi={simdi}
                />
              </div>

              {bekleyenSayisi > 0 ? <BekleyenSeridi sayi={bekleyenSayisi} /> : null}

              {yeniSayisi > 0 ? (
                <div className="tk-serit yeni" role="status">
                  <span className="tk-nokta" aria-hidden="true" />
                  {yeniSayisi === 1 ? '1 yeni iş' : `${yeniSayisi} yeni iş`} — “Yeni” yazan satırda.
                </div>
              ) : null}

              {acik.length === 0 ? (
                <BosDurum
                  simge={bitenler.length ? '🎉' : '🛠️'}
                  baslik={bitenler.length ? 'Bugünün işleri bitti' : 'Bugün size atanmış iş yok'}
                  aciklama={
                    bitenler.length
                      ? `Bugün ${bitenler.length} iş çözdünüz. Yeni iş atanınca burada görünür.`
                      : 'Operasyon atayınca burada sıralı görünür.'
                  }
                />
              ) : null}

              {simdiki.length ? (
                <>
                  <h2 className="bolum-baslik">Şu an</h2>
                  {simdiki.map((is) => (
                    <IsKarti key={is.is_no} is={is} yeni={yeniler.has(is.is_no)} simdi={simdi} vurgu />
                  ))}
                </>
              ) : null}

              {siradaki ? (
                <>
                  <h2 className="bolum-baslik">Sıradaki</h2>
                  <IsKarti is={siradaki} yeni={yeniler.has(siradaki.is_no)} simdi={simdi} vurgu={!simdiki.length} />
                </>
              ) : null}

              {sonra.length ? (
                <>
                  <h2 className="bolum-baslik">Sonra</h2>
                  {sonra.map((is) => (
                    <IsKarti key={is.is_no} is={is} yeni={yeniler.has(is.is_no)} simdi={simdi} />
                  ))}
                </>
              ) : null}

              {sonraki.length ? (
                <>
                  <h2 className="bolum-baslik">Sonraki günler</h2>
                  {sonraki.map((is) => (
                    <IsKarti key={is.is_no} is={is} yeni={yeniler.has(is.is_no)} simdi={simdi} />
                  ))}
                </>
              ) : null}

              {bitenler.length + ofiseDonenler.length > 0 ? (
                <>
                  <button
                    className="bolum-baslik tk-bitenler-dugme"
                    onClick={() => setBitenlerAcik((a) => !a)}
                    aria-expanded={bitenlerAcik}
                  >
                    <Onay boyut={15} />
                    Bitenler ({bitenler.length + ofiseDonenler.length})
                    <span className={`tk-ok${bitenlerAcik ? ' acik' : ''}`} aria-hidden="true">
                      <Ileri boyut={16} />
                    </span>
                  </button>
                  {bitenlerAcik ? (
                    <div className="tk-bitenler">
                      {bitenler.map((is) => (
                        <BitenKarti key={is.is_no} is={is} />
                      ))}
                      {ofiseDonenler.map((o) => (
                        <OfiseDonenKarti key={o.is_no} o={o} />
                      ))}
                    </div>
                  ) : null}
                </>
              ) : null}
            </>
          )}
        </div>
      </SayfaGovde>
    </Sayfa>
  );
}

function Tazelik({
  onbellekten,
  guncelleme,
  baglantiYok,
  simdi,
}: {
  onbellekten: boolean;
  guncelleme: number | null;
  baglantiYok: boolean;
  simdi: number;
}) {
  if (!guncelleme) return null;
  const dk = Math.max(0, Math.round((simdi - guncelleme) / 60000));
  const saat = new Date(guncelleme).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const eski = onbellekten || baglantiYok;
  let metin: string;
  if (onbellekten) metin = `Telefondaki kopya · ${saat}`;
  else if (baglantiYok) metin = `Bağlantı yok · son güncelleme ${saat}`;
  else if (dk < 1) metin = 'Az önce güncellendi';
  else if (dk < 60) metin = `${dk} dk önce güncellendi`;
  else metin = `Son güncelleme ${saat}`;
  return (
    <span className={`tk-tazelik${eski ? ' eski' : ''}`}>
      <span className="tk-nokta" aria-hidden="true" />
      {metin}
    </span>
  );
}

function BekleyenSeridi({ sayi }: { sayi: number }) {
  // İnternet varken eylem saniyeler içinde gider; şerit yalnız birkaç saniyeden
  // uzun bekleyen işlem varsa çıkar (her basışta yanıp sönmesin).
  const [gorunur, setGorunur] = useState(false);
  useEffect(() => {
    const sayac = window.setTimeout(() => setGorunur(true), navigator.onLine ? 3000 : 0);
    return () => window.clearTimeout(sayac);
  }, []);
  if (!gorunur) return null;
  return (
    <div className="serit bekleyen tk-bekleyen" role="status">
      <Uyari boyut={18} />
      <span>{sayi === 1 ? '1 işlem gönderilmeyi bekliyor' : `${sayi} işlem gönderilmeyi bekliyor`}</span>
      <button className="buton" onClick={() => void isKuyrugunuGonder()}>
        Şimdi gönder
      </button>
    </div>
  );
}

/* ------------------------------ Kartlar ------------------------------ */

function IsKarti({ is, yeni, simdi, vurgu = false }: { is: IsAyrinti; yeni: boolean; simdi: number; vurgu?: boolean }) {
  const k = kalanBilgisi(is);
  const dilim = is.randevu ? dilimMetni(is.randevu.bas, is.randevu.bit, new Date(simdi)) : null;
  const calisiyor = is.durum === 'yolda' || is.durum === 'sahada';
  const ticket = Boolean(is.ticket) || is.binada_acik_ticket > 0;
  return (
    <button
      className={`tk-kart${vurgu ? ' vurgu' : ''}${calisiyor ? ' calisiyor' : ''}`}
      onClick={() => git(`/islerim/${encodeURIComponent(is.is_no)}`)}
      aria-label={`${is.task_adi}, ${yerMetni(is)}${dilim ? `, ${dilim}` : ''}`}
    >
      <span className="tk-dilim">
        {dilim ? (
          <>
            <span className="tk-dilim-saat">{dilim}</span>
            {is.randevu?.teyitli ? <span className="tk-dilim-alt">teyitli</span> : null}
          </>
        ) : (
          <span className="tk-dilim-yok">Randevusuz</span>
        )}
      </span>
      <span className="tk-kart-govde">
        <span className="tk-kart-ad">
          {is.serit === 'BTK' ? <Rozet tur="btk" /> : null}
          <span className="metin">{is.task_adi}</span>
        </span>
        <span className="tk-kart-yer">{yerMetni(is)}</span>
        <span className="tk-kart-alt">
          {calisiyor ? (
            <span className="tk-durum-yazi">
              <span className={`tk-nokta ${is.durum}`} aria-hidden="true" />
              {DURUM_ETIKET[is.durum]} · {durumSuresi(is, simdi)}
            </span>
          ) : (
            <SureHapi kalan_dk={k.kalan_dk} renk={k.renk} gecikti={k.gecikti} onEk={k.btk ? 'BTK' : undefined} kucuk />
          )}
          {yeni ? <span className="tk-yeni">Yeni</span> : null}
          {ticket ? <Rozet tur="ticket" /> : null}
          {is.rozetler.includes('tekrar') ? <Rozet tur="tekrar" /> : null}
        </span>
      </span>
      <span className="tk-kart-ok" aria-hidden="true">
        <Ileri boyut={20} />
      </span>
    </button>
  );
}

function BitenKarti({ is }: { is: IsSatir }) {
  return (
    <div className="tk-kart biten">
      <span className="tk-dilim">
        <span className="tk-biten-simge" aria-hidden="true">
          <Onay boyut={20} />
        </span>
      </span>
      <span className="tk-kart-govde">
        <span className="tk-kart-ad">
          <span className="metin">{is.task_adi}</span>
        </span>
        <span className="tk-kart-yer">
          Çözüldü · {saatMetni(is.durum_zamani)}
          {is.mahalle ? ` · ${is.mahalle}` : ''}
        </span>
      </span>
    </div>
  );
}

function OfiseDonenKarti({ o }: { o: OfiseDonen }) {
  const saat = new Date(o.zaman).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  return (
    <div className="tk-kart biten ofiste">
      <span className="tk-dilim">
        <span className="tk-biten-simge ofiste" aria-hidden="true">
          <Uyari boyut={18} />
        </span>
      </span>
      <span className="tk-kart-govde">
        <span className="tk-kart-ad">
          <span className="metin">{o.task_adi}</span>
        </span>
        <span className="tk-kart-yer">
          {o.sonuc} · {saat} · operasyonda
        </span>
      </span>
    </div>
  );
}

function Iskelet() {
  return (
    <div style={{ paddingTop: 12 }} aria-hidden="true">
      <div className="iskelet" style={{ height: 44, marginBottom: 16 }} />
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="iskelet" style={{ height: 96, marginBottom: 12 }} />
      ))}
    </div>
  );
}
