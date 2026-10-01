/**
 * Aranacaklar (§6.6, EK-12.4) — masanın arama kuyruğu, TEK liste, bant sırasıyla:
 *   1 BTK teşhis (vade 45 dk) › 2 Ulaşılamadı (uyanma geldi) › 3 Uyanan askı › 4 Masa işleri.
 *
 * Satır: vade ("12 dk kaldı" / "vade geçti 5 dk"), task, müşteri, deneme "2/4",
 * Müşteri No [Kopyala]. Sonuç düğmeleri tek dokunuş (44 px):
 *   Düzeldi (canlı test yapıldı) · Şimdi evde · Başka gün · Cevapsız · Kapalı · Yanlış numara
 * Ulaşılamayan her aramadan sonra BOSS'ta "Talep Ulaşamama SMS" gönderilir (giden
 * kutusuna düşer). 3. denemeden sonra "Askıya al" önerilir.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { aranacaklar as aranacaklariGetir, hataMetni, isGetir, kopyaKaydi, teshis, type TeshisSonucu } from '../../is/api';
import type { AranacakYanit, IsAyrinti, IsSatir } from '../../is/tipler';
import { git, useAdres } from '../../yol/rota';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { Hikaye } from '../../ortak/Hikaye';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { Panel } from '../../ortak/Panel';
import { DilimSecici, type Dilim } from '../../ortak/DilimSecici';
import { SureHapi } from '../../ortak/SureHapi';
import { Rozet } from '../../ortak/Rozet';
import { useBildirim } from '../../ortak/Bildirim';
import { sureMetni, sunucuZamani } from '../../ortak/sure';
import { IslerSaglayici, useIsler } from './depo';
import { IsCekmecesi, type CekmeceKomutu } from './IsCekmecesi';
import { kalanDk } from './IsSatiri';
import { KopyalaDugmesi, yerMetni } from './parcalar';
import './isler.css';

const BANT: Record<AranacakYanit['bantlar'][number]['bant'], { baslik: string; aciklama: string }> = {
  btk_teshis: { baslik: 'BTK teşhis araması', aciklama: 'Teknisyen gitmeden önce müşteriyi arayın; telefonda düzelirse saha ziyareti iptal olur.' },
  ulasilamadi: { baslik: 'Ulaşılamadı', aciklama: 'Teknisyen müşteriyi evde bulamadı; yeni saat için arayın.' },
  uyanan: { baslik: 'Uyanan askı', aciklama: 'Askı süresi doldu; müşteriyi arayıp durumu sorun.' },
  masa: { baslik: 'Masa işleri', aciklama: 'Kanal şikâyeti, soru-cevap: telefonda çözülecek işler.' },
};

export function Aranacaklar() {
  return (
    <IslerSaglayici>
      <AranacaklarEkrani />
    </IslerSaglayici>
  );
}

function AranacaklarEkrani() {
  const depo = useIsler();
  const bildirim = useBildirim();
  const adres = useAdres();
  const isNo = useMemo(() => {
    const p = adres.split('/').filter(Boolean);
    const i = p.indexOf('is');
    return i >= 0 && p[i + 1] ? decodeURIComponent(p[i + 1]) : null;
  }, [adres]);
  const [veri, setVeri] = useState<AranacakYanit | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [ayrinti, setAyrinti] = useState<Record<string, IsAyrinti>>({});
  const [bekliyor, setBekliyor] = useState<string | null>(null);
  const [baskaGun, setBaskaGun] = useState<IsSatir | null>(null);
  const [dilim, setDilim] = useState<Dilim | null>(null);
  const [komut, setKomut] = useState<CekmeceKomutu | null>(null);
  const komutNo = useRef(0);

  const yukle = useCallback(async () => {
    try {
      setVeri(await aranacaklariGetir());
      setHata(null);
    } catch (e) {
      setHata(hataMetni(e));
    }
  }, []);

  useEffect(() => {
    void yukle();
    const t = window.setInterval(() => document.visibilityState === 'visible' && void yukle(), 20000);
    return () => window.clearInterval(t);
  }, [yukle]);

  /* Satırların vade/deneme bilgisi ayrıntıdan (dörder dörder). */
  useEffect(() => {
    if (!veri) return;
    const eksik = veri.bantlar.flatMap((b) => b.isler).filter((x) => !ayrinti[x.is_no] || ayrinti[x.is_no].surum !== x.surum);
    if (!eksik.length) return;
    let iptal = false;
    const kuyruk = [...eksik];
    const isci = async () => {
      while (kuyruk.length && !iptal) {
        const x = kuyruk.shift()!;
        try {
          const a = await isGetir(x.is_no);
          if (!iptal) setAyrinti((o) => ({ ...o, [x.is_no]: a }));
        } catch {
          /* bir satırın ayrıntısı gelmezse satır yine çalışır */
        }
      }
    };
    void Promise.all([isci(), isci(), isci(), isci()]);
    return () => {
      iptal = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [veri]);

  const sonuc = async (s: IsSatir, sonucKodu: TeshisSonucu, metin: string, ek: { canli_test?: boolean; randevu?: Dilim } = {}) => {
    setBekliyor(s.is_no);
    try {
      const y = await teshis(s.is_no, {
        sonuc: sonucKodu,
        surum: ayrinti[s.is_no]?.surum ?? s.surum,
        canli_test: ek.canli_test,
        randevu: ek.randevu ? { bas: ek.randevu.bas, bit: ek.randevu.bit, teyitli: true } : undefined,
      });
      setAyrinti((o) => ({ ...o, [s.is_no]: y }));
      depo.isYaz(y);
      const ulasilamadi = sonucKodu === 'cevapsiz' || sonucKodu === 'kapali';
      bildirim.goster(ulasilamadi ? `${metin} · BOSS’ta “Talep Ulaşamama SMS” gönderin (BOSS’a işlenecek listesinde).` : metin, ulasilamadi ? 'uyari' : 'basari', {
        sureMs: ulasilamadi ? 7000 : 3000,
      });
      void yukle();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(null);
    }
  };

  const ac = (no: string, gorunum?: string) => {
    git(`/yonetici/aranacak/is/${encodeURIComponent(no)}`);
    if (gorunum) {
      komutNo.current += 1;
      setKomut({ tur: 'gorunum', deger: gorunum, n: komutNo.current });
    }
  };

  const toplam = veri?.bantlar.reduce((t, b) => t + b.isler.length, 0) ?? 0;
  const simdi = new Date(Date.now() + depo.sunucuFarkMs);
  const vadesiGecen = useMemo(
    () =>
      Object.values(ayrinti).filter((a) => {
        const v = sunucuZamani(a.masa_vade);
        return v && v.getTime() < Date.now() + depo.sunucuFarkMs;
      }).length,
    [ayrinti, depo.sunucuFarkMs],
  );

  return (
    <>
      <YonUst baslik="Aranacaklar" />
      <Icerik>
        {hata && !veri ? <HataKutusu mesaj={hata} tekrar={() => void yukle()} /> : null}
        {!veri && !hata ? <Iskelet satir={5} yukseklik={120} /> : null}
        {veri ? (
          toplam ? (
            <>
              <Hikaye
                cumle={`Şu an ${toplam} müşteri aranacak.${vadesiGecen ? ` ${vadesiGecen} aramanın vadesi geçti — önce onlar.` : ''}`}
                ton={vadesiGecen ? 'acil' : 'sakin'}
              />
              {veri.bantlar
                .filter((b) => b.isler.length)
                .map((b, i) => (
                  <section key={b.bant} className="ar-bant">
                    <header>
                      <h2>
                        <span className="no">{i + 1}</span> {BANT[b.bant].baslik} <span className="sayi">{b.isler.length}</span>
                      </h2>
                      <p>{BANT[b.bant].aciklama}</p>
                    </header>
                    <div className="ar-liste" role="list">
                      {b.isler.map((s) => (
                        <AramaSatiri
                          key={s.is_no}
                          s={s}
                          a={ayrinti[s.is_no]}
                          simdi={simdi}
                          secili={s.is_no === isNo}
                          bekliyor={bekliyor === s.is_no}
                          ac={ac}
                          sonuc={(k, m, ek) => void sonuc(s, k, m, ek)}
                          baskaGun={() => {
                            setBaskaGun(s);
                            setDilim(null);
                          }}
                        />
                      ))}
                    </div>
                  </section>
                ))}
            </>
          ) : (
            <BosDurum simge="☎️" baslik="Şu an aranacak kimse yok." aciklama="BTK işi gelince 45 dakika içinde burada olur." />
          )
        ) : null}
      </Icerik>

      <Panel
        acik={Boolean(baskaGun)}
        kapat={() => setBaskaGun(null)}
        baslik="Başka gün"
        altBaslik="Müşteriyle konuşulan gün ve saat; teyitli yazılır."
        alt={
          <>
            <button type="button" className="o-dugme" onClick={() => setBaskaGun(null)}>
              Vazgeç
            </button>
            <button
              type="button"
              className="o-dugme birincil"
              disabled={!dilim || Boolean(bekliyor)}
              onClick={() => {
                const s = baskaGun!;
                setBaskaGun(null);
                void sonuc(s, 'baska_gun', 'Randevu verildi · teyitli', { randevu: dilim! });
              }}
            >
              Randevuyu kaydet
            </button>
          </>
        }
      >
        <DilimSecici
          deger={dilim}
          degisti={(d) => setDilim(d ? { ...d, teyitli: true } : null)}
          teyitGoster={false}
          ilkSaat={depo.ayarlar?.dilimler.length ? parseInt(depo.ayarlar.dilimler[0].bas, 10) : 8}
          sonSaat={depo.ayarlar?.dilimler.length ? parseInt(depo.ayarlar.dilimler[depo.ayarlar.dilimler.length - 1].bit, 10) : 20}
        />
      </Panel>

      <IsCekmecesi isNo={isNo} kapat={() => git('/yonetici/aranacak')} komut={komut} />
    </>
  );
}

function vadeMetni(a: IsAyrinti | undefined, simdi: Date): { metin: string; renk: 'kirmizi' | 'amber' | null } | null {
  const v = sunucuZamani(a?.masa_vade);
  if (!v) return null;
  const dk = Math.round((v.getTime() - simdi.getTime()) / 60000);
  if (dk < 0) return { metin: `vade geçti ${sureMetni(-dk)}`, renk: 'kirmizi' };
  return { metin: `${sureMetni(dk)} kaldı`, renk: dk <= 10 ? 'amber' : null };
}

function AramaSatiri({
  s,
  a,
  simdi,
  secili,
  bekliyor,
  ac,
  sonuc,
  baskaGun,
}: {
  s: IsSatir;
  a: IsAyrinti | undefined;
  simdi: Date;
  secili: boolean;
  bekliyor: boolean;
  ac: (no: string, gorunum?: string) => void;
  sonuc: (k: TeshisSonucu, metin: string, ek?: { canli_test?: boolean }) => void;
  baskaGun: () => void;
}) {
  const vade = vadeMetni(a, simdi);
  const m = a?.merdiven;
  const deneme = m ? `${m.gecerli}/${m.gerekli}` : a?.evde_yok_sayisi ? `${a.evde_yok_sayisi}. deneme` : null;
  const askiOner = (m?.deneme ?? 0) >= 3 || (a?.evde_yok_sayisi ?? 0) >= 3;
  return (
    <article className={`ar-satir${secili ? ' secili' : ''}${s.kotu_gecmis ? ' gri' : ''}`} role="listitem">
      <button type="button" className="ar-bas" onClick={() => ac(s.is_no)}>
        <span className="ust">
          {vade ? <span className={`ar-vade${vade.renk ? ` ${vade.renk}` : ''}`}>{vade.metin}</span> : <SureHapi kalan_dk={kalanDk(s)} renk={s.renk} gecikti={s.gecikti} kucuk />}
          {s.serit === 'BTK' ? <Rozet tur="btk" /> : null}
          <span className="task">{s.task_adi}</span>
          {s.rozetler.includes('tekrar') ? <Rozet tur="tekrar" /> : null}
        </span>
        <span className="alt">
          {[s.musteri_adi, yerMetni(s)].filter(Boolean).join(' · ')}
          {deneme ? <span className="ip-kaynak"> · deneme {deneme}</span> : null}
          {m?.sonraki ? <span className="ip-kaynak"> · sonraki {m.sonraki.slice(11, 16)}</span> : null}
        </span>
      </button>
      {s.musteri_no ? (
        <div className="ar-musteri">
          <span>
            Müşteri No <b>{s.musteri_no}</b>
          </span>
          <KopyalaDugmesi metin={s.musteri_no} sonra={() => void kopyaKaydi(s.is_no).catch(() => undefined)} />
        </div>
      ) : null}
      <div className="ar-sonuclar" role="group" aria-label="Arama sonucu">
        {!s.rozetler.includes('tekrar') ? (
          <button type="button" className="o-dugme" disabled={bekliyor} onClick={() => sonuc('duzeldi', 'Düzeldi · telefonda çözüldü', { canli_test: true })}>
            Düzeldi (canlı test yapıldı)
          </button>
        ) : null}
        <button type="button" className="o-dugme" disabled={bekliyor} onClick={() => sonuc('simdi_evde', 'Şimdi evde · teknisyenin sırasında öne alındı')}>
          Şimdi evde
        </button>
        <button type="button" className="o-dugme" disabled={bekliyor} onClick={baskaGun}>
          Başka gün
        </button>
        <button type="button" className="o-dugme" disabled={bekliyor} onClick={() => sonuc('cevapsiz', 'Cevapsız kaydedildi')}>
          Cevapsız
        </button>
        <button type="button" className="o-dugme" disabled={bekliyor} onClick={() => sonuc('kapali', 'Kapalı kaydedildi')}>
          Kapalı
        </button>
        <button type="button" className="o-dugme" disabled={bekliyor} onClick={() => sonuc('yanlis_no', 'Yanlış numara · iş ATA havuzunda')}>
          Yanlış numara
        </button>
      </div>
      {askiOner ? (
        <div className="ip-uyari amber">
          <span>3 denemeden sonra ulaşılamadı. Askıya almayı düşünün (BTK’da en çok 24 s, diğerlerinde 48 s).</span>
          <button type="button" className="o-dugme kucuk" onClick={() => ac(s.is_no, 'aski')}>
            Askıya al
          </button>
        </div>
      ) : null}
    </article>
  );
}
