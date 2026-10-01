/**
 * İş ekranı (§6.9 sağdaki çizim): kararı verdiren bilgi yukarıda, tek büyük
 * düğme aşağıda, başparmak bölgesinde (56 px):
 *
 *   Atandı → [Yola çıktım] · Yolda → [İşe başladım] · Sahada → [Bitti]
 *
 * "Bitti" alttan çekmece açar; önce zorunlu "Müşteri evde miydi?", sonra sonuç.
 * "Evde yok" ve "Not ekle" düğmenin üstünde sessiz iki eylemdir. Sinyal yoksa
 * her basış telefona yazılır ve bağlantı gelince gider (ekran beklemez).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useBildirim } from '../ortak/Bildirim';
import { Cekmece } from '../ortak/Cekmece';
import { DahaMenusu, type MenuOgesi } from '../ortak/Menu';
import { Sayfa, SayfaGovde, Ust, BosDurum } from '../ortak/Sayfa';
import { SureHapi } from '../ortak/SureHapi';
import { Rozet } from '../ortak/Rozet';
import { AdimCizgisi } from '../ortak/Durum';
import { Ileri, Kalem, Konum, Onay, Pusula, Saat, Takvim, Uyari } from '../ortak/Ikon';
import {
  SAGLAYICI_ADLARI,
  haritayiAc,
  kayitliSaglayici,
  saglayiciSirasi,
  saglayiciyiKaydet,
  type HaritaSaglayici,
} from '../ortak/yolTarifi';
import { git, useGeri } from '../yol/rota';
import { DURUM_ETIKET, type Durum, type IsAyrinti } from '../is/tipler';
import { durumDegistir, yeniyiKaldir, type IslerimDeposu } from './depo';
import { kopyaBildir } from './api';
import {
  ADIMLAR,
  BUYUK_DUGME,
  adimNo,
  dilimMetni,
  durumSuresi,
  kalanBilgisi,
  maskeliNo,
  notlar,
  panoyaKopyala,
  saatMetni,
  yerMetni,
} from './bicim';
import { BaskaGunCekmecesi, BittiCekmecesi, EvdeYokCekmecesi, NotCekmecesi, OnceCekmecesi } from './Cekmeceler';
import { useDakika, useIs } from './kancalar';

export function IsEkrani({ isNo, depo }: { isNo: string; depo: IslerimDeposu }) {
  const geri = useGeri('/islerim');
  const { acik: is, biten, ofiste } = useIs(depo, isNo);
  const simdi = useDakika();

  useEffect(() => {
    yeniyiKaldir(isNo);
  }, [isNo]);

  if (!is) {
    const yukleniyor = depo.asama !== 'hazir' && !depo.yanit;
    return (
      <Sayfa>
        <Ust baslik="İş" geriyeGit={geri} ortala />
        <SayfaGovde sekmesiz>
          <div className="tk">
            {yukleniyor ? (
              <div className="iskelet" style={{ height: 220, marginTop: 16 }} aria-hidden="true" />
            ) : biten || ofiste ? (
              <BosDurum
                simge={biten ? '✅' : '📋'}
                baslik={biten ? `${biten.task_adi} çözüldü` : `${ofiste?.task_adi ?? 'İş'} operasyona döndü`}
                aciklama={
                  biten
                    ? `Bugün ${saatMetni(biten.durum_zamani)}'de kapattınız. Sıradaki işe geçebilirsiniz.`
                    : `${ofiste?.sonuc ?? ''}. Operasyon yeniden planlayınca listenize gelir.`
                }
              >
                <button className="dugme birincil" onClick={() => git('/islerim', { degistir: true })}>
                  İşlerime dön
                </button>
              </BosDurum>
            ) : (
              <BosDurum
                simge="🔁"
                baslik="Bu iş artık listenizde değil"
                aciklama="Operasyon başka birine vermiş ya da işi kaldırmış olabilir."
              >
                <button className="dugme birincil" onClick={() => git('/islerim', { degistir: true })}>
                  İşlerime dön
                </button>
              </BosDurum>
            )}
          </div>
        </SayfaGovde>
      </Sayfa>
    );
  }
  return <Ayrinti is={is} depo={depo} geri={geri} simdi={simdi} />;
}

function Ayrinti({ is, depo, geri, simdi }: { is: IsAyrinti; depo: IslerimDeposu; geri: () => void; simdi: number }) {
  const { goster } = useBildirim();
  const [bittiAcik, setBittiAcik] = useState(false);
  const [evdeYokAcik, setEvdeYokAcik] = useState(false);
  const [notAcik, setNotAcik] = useState(false);
  const [onceAcik, setOnceAcik] = useState(false);
  const [baskaGunAcik, setBaskaGunAcik] = useState(false);
  const [haritaSecimAcik, setHaritaSecimAcik] = useState(false);
  const [gecmisAcik, setGecmisAcik] = useState(false);
  const [basiliyor, setBasiliyor] = useState(false);

  const k = kalanBilgisi(is);
  /* Düğmeler sunucunun bu kişiye izin verdiği geçişlerden çizilir (`izinler.durumlar`). */
  const izinli = (d: Durum) => !is.izinler?.durumlar || is.izinler.durumlar.includes(d);
  const aday = BUYUK_DUGME[is.durum];
  const buyuk = aday && (aday.hedef === 'bitti' || izinli(aday.hedef)) ? aday : undefined;
  const bekleyen = depo.bekleyenler.some((b) => b.is_no === is.is_no);
  const siradaMi = [...depo.gorunum.simdiki, ...depo.gorunum.bugun][0]?.is_no === is.is_no;
  const notListesi = useMemo(() => notlar(is), [is]);
  const ticket = is.ticket;
  const binaTicketi = !ticket && is.binada_acik_ticket > 0;
  const konum = is.bina ? { lat: is.bina.lat, lon: is.bina.lon } : is.lat != null && is.lon != null ? { lat: is.lat, lon: is.lon } : null;
  const locationId = is.bina?.location_id ?? is.lokasyon;

  const kopyala = useCallback(
    async (metin: string, ne: string, musteriNo = false) => {
      const tamam = await panoyaKopyala(metin);
      goster(tamam ? `${ne} kopyalandı` : 'Kopyalanamadı; elle yazın.', tamam ? 'basari' : 'uyari');
      if (tamam && musteriNo) void kopyaBildir(is.is_no).catch(() => undefined);
    },
    [goster, is.is_no],
  );

  const yolTarifi = useCallback(() => {
    if (!konum) return;
    const kayitli = kayitliSaglayici();
    if (kayitli) haritayiAc(kayitli, konum.lat, konum.lon);
    else setHaritaSecimAcik(true);
  }, [konum]);

  const saglayiciSec = (s: HaritaSaglayici) => {
    if (!konum) return;
    saglayiciyiKaydet(s);
    setHaritaSecimAcik(false);
    haritayiAc(s, konum.lat, konum.lon);
  };

  /** Büyük düğme: Yola çıktım / İşe başladım anında kuyruğa; Bitti çekmece açar. */
  const buyukBas = async () => {
    if (!buyuk || basiliyor) return;
    if (buyuk.hedef === 'bitti') {
      setBittiAcik(true);
      return;
    }
    setBasiliyor(true);
    try {
      await durumDegistir(is, buyuk.hedef, buyuk.etiket);
      try {
        navigator.vibrate?.(30);
      } catch {
        /* titreşim yoksa sorun değil */
      }
      goster(buyuk.hedef === 'yolda' ? 'Yola çıktınız · iyi yolculuklar' : 'İşe başladınız', 'basari');
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setBasiliyor(false);
    }
  };

  const digerleri: MenuOgesi[] = [];
  if (is.durum === 'atandi' && izinli('sahada')) {
    digerleri.push({
      etiket: 'Zaten oradayım: işe başladım',
      calistir: () =>
        void durumDegistir(is, 'sahada', 'İşe başladım').then(() => goster('İşe başladınız', 'basari')),
    });
  }
  if (!siradaMi && is.durum === 'atandi') digerleri.push({ etiket: 'Önce bu işe gideceğim', calistir: () => setOnceAcik(true) });
  if (is.durum === 'atandi' && izinli('atandi')) {
    digerleri.push({ etiket: 'Müşteri başka gün istedi', calistir: () => setBaskaGunAcik(true) });
  }
  if (is.boss_task_no) {
    digerleri.push({ etiket: `Task No'yu kopyala (${is.boss_task_no})`, calistir: () => void kopyala(is.boss_task_no as string, 'Task No') });
  }

  return (
    <Sayfa>
      <Ust
        baslik={is.task_adi}
        geriyeGit={geri}
        ortala
        sag={digerleri.length ? <DahaMenusu ogeler={digerleri} /> : undefined}
      />
      <SayfaGovde sekmesiz>
        <div className="tk tk-is">
          {/* 1. Ne kadar vaktim var, ne zaman söz verildi */}
          <section className="tk-is-bas">
            <div className="tk-is-rozetler">
              {is.serit === 'BTK' ? <Rozet tur="btk" /> : null}
              {is.rozetler.includes('tekrar') ? <Rozet tur="tekrar" /> : null}
              {is.oncelik ? <Rozet tur="yeniden">{is.oncelik}</Rozet> : null}
              <span className="tk-durum-yazi">
                <span className={`tk-nokta ${is.durum}`} aria-hidden="true" />
                {DURUM_ETIKET[is.durum]}
                {is.durum !== 'atandi' ? ` · ${durumSuresi(is, simdi)}` : ''}
              </span>
            </div>
            <div className="tk-kalan">
              <SureHapi kalan_dk={k.kalan_dk} renk={k.renk} gecikti={k.gecikti} onEk={k.btk ? 'BTK' : k.gecikti ? undefined : 'Kalan'} />
              {is.btk_durdu ? <span className="tk-kucuk-not">BTK saati durdu (abone kaynaklı askı)</span> : null}
            </div>
            <ul className="tk-bilgi-liste">
              <li>
                <Takvim boyut={18} />
                <span>
                  {is.randevu ? (
                    <>
                      <strong>{dilimMetni(is.randevu.bas, is.randevu.bit, new Date(simdi))}</strong>
                      {is.randevu.teyitli ? ' · müşteriyle teyitli ✓' : ' · tahmini varış'}
                    </>
                  ) : (
                    'Randevusuz · sıradaki boşlukta gidin'
                  )}
                </span>
              </li>
              <li>
                <Saat boyut={18} />
                <span>{is.soz}</span>
              </li>
            </ul>
            <AdimCizgisi adim={adimNo(is.durum)} adimlar={ADIMLAR} />
            <div className="tk-adim-etiket" aria-hidden="true">
              {ADIMLAR.map((a, i) => (
                <span key={a} className={i === adimNo(is.durum) ? 'etkin' : undefined}>
                  {a}
                </span>
              ))}
            </div>
          </section>

          {/* 2. Uyarılar: gitmeden bilmesi gerekenler */}
          {ticket || binaTicketi ? (
            <div className="tk-serit amber" role="note">
              <Uyari boyut={18} />
              <span>
                {ticket
                  ? `Binada açık ${ticket.konu} ticket'ı var (#${ticket.id}, ${ticket.gun} gündür). Operasyonla konuşun.`
                  : 'Binada açık altyapı ticket’ı var. Gitmeden operasyonla konuşun.'}
              </span>
            </div>
          ) : null}
          {is.rozetler.includes('tekrar') ? (
            <div className="tk-serit kirmizi" role="note">
              <Uyari boyut={18} />
              <span>Bu arıza 7 gün içinde tekrar geldi. Kökten çözün; gerekirse operasyona haber verin.</span>
            </div>
          ) : null}
          {bekleyen ? (
            <div className="tk-serit gri" role="status">
              <Saat boyut={18} />
              <span>Son işleminiz telefonda; bağlantı gelince gönderilecek.</span>
            </div>
          ) : null}

          {/* 3. Müşteri ve yer */}
          <section className="tk-kutu">
            <h2 className="tk-kutu-baslik">Müşteri</h2>
            <div className="tk-musteri-ad">{is.musteri_adi || 'Ad bilgisi yok'}</div>
            {is.musteri_no ? (
              <div className="tk-satir">
                <span className="tk-satir-etiket">Müşteri No</span>
                <span className="tk-satir-deger">{maskeliNo(is.musteri_no)}</span>
                <button className="tk-kopya" onClick={() => void kopyala(is.musteri_no as string, 'Müşteri No', true)}>
                  Kopyala
                </button>
              </div>
            ) : null}
            {is.bina?.ad ? <div className="tk-bina-ad">{is.bina.ad}</div> : null}
            <p className="tk-adres">{is.adres || yerMetni(is)}</p>
            {locationId ? (
              <div className="tk-satir">
                <span className="tk-satir-etiket">Location Id</span>
                <span className="tk-satir-deger">{locationId}</span>
                <button className="tk-kopya" onClick={() => void kopyala(String(locationId), 'Location Id')}>
                  Kopyala
                </button>
              </div>
            ) : null}
            {konum ? (
              <button className="konum-onizleme tk-konum" onClick={yolTarifi}>
                <span className="konum-imleci" aria-hidden="true">
                  <Konum boyut={24} />
                </span>
                <span className="konum-yazi">
                  <span className="konum-baslik">Yol tarifi</span>
                  <span className="konum-alt">
                    {is.konum_yaklasik ? 'Konum yaklaşık · mahalle merkezi' : yerMetni(is)}
                  </span>
                </span>
                <Ileri boyut={20} />
              </button>
            ) : (
              <p className="tk-kucuk-not">Bu işin konumu yok; adresi kullanın.</p>
            )}
          </section>

          {/* 4. Notlar (operasyonun ve sizin) */}
          {notListesi.length || is.boss.son_aciklama ? (
            <section className="tk-kutu">
              <h2 className="tk-kutu-baslik">Notlar</h2>
              {notListesi.slice(0, 5).map((n) => (
                <div key={n.id} className="tk-not">
                  <p>{n.metin}</p>
                  <span>
                    {n.kisi ?? 'Operasyon'} · {saatMetni(n.zaman)}
                  </span>
                </div>
              ))}
              {is.boss.son_aciklama ? (
                <div className="tk-not boss">
                  <p>{is.boss.son_aciklama}</p>
                  <span>BOSS açıklaması</span>
                </div>
              ) : null}
            </section>
          ) : null}

          {/* 5. Geçmiş: kapalı başlar */}
          {is.olaylar.length ? (
            <section className="tk-kutu">
              <button className="tk-gecmis-dugme" onClick={() => setGecmisAcik((a) => !a)} aria-expanded={gecmisAcik}>
                <span>Geçmiş ({is.olaylar.length})</span>
                <span className={`tk-ok${gecmisAcik ? ' acik' : ''}`} aria-hidden="true">
                  <Ileri boyut={16} />
                </span>
              </button>
              {gecmisAcik ? (
                <ol className="tk-gecmis">
                  {is.olaylar.slice(0, 20).map((o) => (
                    <li key={o.id}>
                      <span className="saat">{saatMetni(o.zaman)}</span>
                      <span className="ozet">
                        {o.ozet}
                        {o.kisi ? <span className="kisi"> · {o.kisi}</span> : null}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : null}
            </section>
          ) : null}
        </div>
      </SayfaGovde>

      {/* Tek büyük düğme ve üstünde iki sessiz eylem — başparmak bölgesi. */}
      <div className="eylem-serit tk-serit-alt">
        <div className="tk-ikincil">
          <button className="dugme sessiz" onClick={() => setEvdeYokAcik(true)} disabled={!izinli('ulasilamadi')}>
            Evde yok
          </button>
          <button className="dugme sessiz" onClick={() => setNotAcik(true)}>
            <Kalem boyut={18} />
            Not ekle
          </button>
        </div>
        {buyuk ? (
          <button className="dugme birincil tk-buyuk" onClick={() => void buyukBas()} disabled={basiliyor}>
            {buyuk.hedef === 'bitti' ? <Onay boyut={22} /> : null}
            {buyuk.etiket}
          </button>
        ) : null}
      </div>

      <BittiCekmecesi acik={bittiAcik} kapat={() => setBittiAcik(false)} is={is} kaydedildi={geri} />
      <EvdeYokCekmecesi acik={evdeYokAcik} kapat={() => setEvdeYokAcik(false)} is={is} kaydedildi={geri} />
      <NotCekmecesi acik={notAcik} kapat={() => setNotAcik(false)} is={is} />
      <OnceCekmecesi acik={onceAcik} kapat={() => setOnceAcik(false)} is={is} />
      <BaskaGunCekmecesi acik={baskaGunAcik} kapat={() => setBaskaGunAcik(false)} is={is} />

      <Cekmece
        acik={haritaSecimAcik}
        kapat={() => setHaritaSecimAcik(false)}
        baslik="Hangi harita?"
        altBaslik="Seçiminiz hatırlanır, bir daha sorulmaz."
      >
        <div style={{ display: 'grid', gap: 10 }}>
          {saglayiciSirasi().map((s) => (
            <button key={s} className="dugme ikincil" onClick={() => saglayiciSec(s)}>
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
