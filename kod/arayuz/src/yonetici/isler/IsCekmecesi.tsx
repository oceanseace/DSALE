/**
 * İş çekmecesi (§6.2): masaüstünde sağdan 440 px (liste açık kalır), telefonda
 * tam ekran. Bölümler karar sırasıyla; "Geçmiş" ve "BOSS bilgisi" kapalı başlar.
 *
 * Tek birincil eylem alt çubukta, sunucunun `birincil` alanından:
 *   Kontrol → Öbeğe ata · Atanmadı → Ata · binada ticket → Ticket'a bağla ·
 *   Ulaşılamadı → Yeniden ata (teyit zorunlu) · Askıda → Uyandır · Altyapı →
 *   Ticket'ı aç · Merkezde → Sahaya al · Teknikte → (değişiklik varsa) Kaydet.
 *
 * "Diğer" eylemleri (Evde yok, Askıya al, Ofisten kapat …) tek soruluk küçük
 * bir görünüm açar; Esc önce onu kapatır. Başarıdan sonra 10 sn "Geri al".
 * 409 `guncel_degil`: çekmece güncel hâle döner, kullanıcının seçimi korunur,
 * sarı satırda kimin ne yaptığı yazar ve [Yine de uygula] çıkar.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  ata,
  bossBagla,
  bossIslendi,
  durumDegistir,
  geriAl,
  hataMetni,
  IsHatasi,
  isGetir,
  kopyaKaydi,
  mahalleSec,
  notEkle,
  obegeAta,
  randevuVer,
  teshis,
  ticketAyir,
  ticketBagla,
  type DurumGirdi,
  type TeshisSonucu,
} from '../../is/api';
import type { IsAyrinti, MahalleKaydi, Obek } from '../../is/tipler';
import { DURUM_ETIKET } from '../../is/tipler';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { SureHapi } from '../../ortak/SureHapi';
import { Rozet, Hap } from '../../ortak/Rozet';
import { AdimCizgisi, DurumYazisi } from '../../ortak/Durum';
import { DilimSecici, type Dilim } from '../../ortak/DilimSecici';
import { Cip, CipSirasi } from '../../ortak/Suz';
import { Kbd } from '../../ortak/Kbd';
import { sureMetni, sunucuZamani } from '../../ortak/sure';
import { konumBaglantisi } from '../../ortak/kimlik';
import { binaAyrinti } from '../../api/uclar';
import type { Ticket } from '../../api/tipler';
import { git } from '../../yol/rota';
import { YeniTicketPenceresi } from '../ekran/ticket/YeniTicket';
import { MahalleSecici } from '../obekler/MahalleSecici';
import { useIsler } from './depo';
import { kalanDk } from './IsSatiri';
import { yonelme } from './dil';
import {
  Bolum,
  dilimMetni,
  KopyalaDugmesi,
  kisaAd,
  ObekNoktasi,
  ObekSecici,
  saatMetni,
  tarihSaatMetni,
  TeknikSecici,
} from './parcalar';

export interface CekmeceKomutu {
  tur: 'teknik' | 'randevu' | 'randevuTus' | 'obek' | 'ticket' | 'not' | 'gorunum';
  deger?: string;
  n: number;
}

export type Gorunum = 'ana' | 'obek' | 'mahalle' | 'ticket' | 'aski' | 'kapat' | 'merkeze' | 'evdeyok' | 'yenidenac' | 'bossbagla';

const MAHALLE_KAYNAGI: Record<string, string> = {
  lokasyon: 'Location Id’den',
  site: 'Site adından',
  adres: 'Adresten',
  'adres-benzer': 'Adresten (yazım farkı)',
  'adres-yeni': 'Adresten',
  'adres-isaretsiz': 'Adresten',
  elle: 'Elle',
  sozluk: 'Adresten',
};

const ADIMLAR = ['Geldi', 'Atandı', 'Yolda', 'Sahada', 'Çözüldü'];
function adimNo(a: IsAyrinti): number {
  switch (a.durum) {
    case 'atandi':
      return 1;
    case 'yolda':
      return 2;
    case 'sahada':
      return 3;
    case 'cozuldu':
    case 'kapandi':
      return 4;
    default:
      return a.atanan ? 1 : 0;
  }
}

function olayZamani(z: string): string {
  const d = sunucuZamani(z);
  if (!d) return '';
  const bugun = new Date();
  const ayni = d.toDateString() === bugun.toDateString();
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${ayni ? '' : `${iki(d.getDate())}.${iki(d.getMonth() + 1)} `}${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

/** Varsayılan plan: atanmış kişi, yoksa öneri, yoksa öbeğin ev teknisyeni; dilim randevudan ya da öneriden. */
function planBaslangici(a: IsAyrinti, obekler: Obek[] | undefined): { teknikId: number | null; dilim: Dilim | null } {
  const obek = a.obek ? obekler?.find((o) => o.id === a.obek!.id) : undefined;
  const teknikId = a.atanan?.id ?? a.oneri?.teknik.id ?? obek?.sahip?.id ?? null;
  let dilim: Dilim | null = null;
  if (a.randevu && a.randevu.kaynak === 'biz') dilim = { bas: a.randevu.bas, bit: a.randevu.bit, teyitli: a.randevu.teyitli };
  else if (!a.atanan && a.oneri?.bas && a.oneri.bit) dilim = { bas: a.oneri.bas, bit: a.oneri.bit, teyitli: false };
  return { teknikId, dilim };
}

export function IsCekmecesi({
  isNo,
  kapat,
  komut,
}: {
  isNo: string | null;
  kapat: () => void;
  komut?: CekmeceKomutu | null;
}) {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [a, setA] = useState<IsAyrinti | null>(null);
  const [yukHata, setYukHata] = useState<string | null>(null);
  const [teknikId, setTeknikId] = useState<number | null>(null);
  const [dilim, setDilim] = useState<Dilim | null>(null);
  const [planDegisti, setPlanDegisti] = useState(false);
  const [catisma, setCatisma] = useState<string | null>(null);
  const [engel, setEngel] = useState<string | null>(null);
  const [yineDe, setYineDe] = useState(false);
  const [gorunum, setGorunum] = useState<Gorunum>('ana');
  const [bekliyor, setBekliyor] = useState(false);
  const aRef = useRef<IsAyrinti | null>(null);
  aRef.current = a;
  const govdeRef = useRef<HTMLDivElement>(null);
  const notRef = useRef<HTMLInputElement>(null);
  const [yeniTicket, setYeniTicket] = useState(false);

  const obekListesi = depo.obekler?.obekler;
  const simdi = useMemo(() => new Date(Date.now() + depo.sunucuFarkMs), [isNo, depo.sunucuFarkMs]); // eslint-disable-line react-hooks/exhaustive-deps

  const yukle = useCallback(
    async (no: string, planiSifirla: boolean) => {
      try {
        const y = await isGetir(no);
        setA(y);
        setYukHata(null);
        if (planiSifirla) {
          const p = planBaslangici(y, obekListesi);
          setTeknikId(p.teknikId);
          setDilim(p.dilim);
          setPlanDegisti(false);
        }
      } catch (e) {
        setYukHata(hataMetni(e));
      }
    },
    [obekListesi],
  );

  /* İş değişince baştan: yeni iş, temiz plan. */
  useEffect(() => {
    setA(null);
    setCatisma(null);
    setEngel(null);
    setYineDe(false);
    setGorunum('ana');
    setYukHata(null);
    if (isNo) void yukle(isNo, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isNo]);

  /* Listedeki satır başka biri tarafından değişti (canlı yoklama): çekmece de tazelensin, seçim korunur. */
  const satir = isNo ? depo.harita.get(isNo) : undefined;
  useEffect(() => {
    if (!isNo || !a || !satir || satir.surum === a.surum || bekliyor) return;
    void yukle(isNo, !planDegisti);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satir?.surum]);

  /* Alt görünüm açıkken Esc yalnız onu kapatır. */
  useEffect(() => {
    if (gorunum === 'ana') return;
    const tus = (o: KeyboardEvent) => {
      if (o.key === 'Escape') {
        o.stopImmediatePropagation();
        o.preventDefault();
        setGorunum('ana');
      }
    };
    window.addEventListener('keydown', tus, true);
    return () => window.removeEventListener('keydown', tus, true);
  }, [gorunum]);

  /* ------------------------------ eylem çalıştırıcı ------------------------------ */

  const calistir = useCallback(
    async (fn: () => Promise<IsAyrinti>, metin: (y: IsAyrinti) => string, secenek: { geriAlinir?: boolean; kapanir?: boolean } = {}) => {
      const { geriAlinir = true, kapanir = false } = secenek;
      setBekliyor(true);
      try {
        const y = await fn();
        setA(y);
        depo.isYaz(y);
        setCatisma(null);
        setEngel(null);
        setYineDe(false);
        setPlanDegisti(false);
        setGorunum('ana');
        const p = planBaslangici(y, obekListesi);
        setTeknikId(p.teknikId);
        setDilim(p.dilim);
        const olay = y.olaylar[0];
        const yazi = metin(y);
        if (geriAlinir && olay) {
          bildirim.geriAl(yazi, async () => {
            try {
              const g = await geriAl(y.is_no, olay.id);
              depo.isYaz(g);
              if (aRef.current?.is_no === g.is_no) {
                setA(g);
                const pp = planBaslangici(g, obekListesi);
                setTeknikId(pp.teknikId);
                setDilim(pp.dilim);
              }
              bildirim.goster('Geri alındı.', 'basari');
              depo.teknikleriTazele();
            } catch (e) {
              bildirim.goster(hataMetni(e), 'uyari');
            }
          });
        } else bildirim.goster(yazi, 'basari');
        depo.teknikleriTazele();
        if (kapanir) kapat();
        return y;
      } catch (e) {
        if (e instanceof IsHatasi) {
          if (e.kod === 'guncel_degil') {
            if (e.govde.guncel) {
              setA(e.govde.guncel);
              depo.isYaz(e.govde.guncel);
            }
            setCatisma(e.message);
            return null;
          }
          if (e.kod === 'altyapi_engeli') {
            setEngel(e.message);
            return null;
          }
        }
        bildirim.goster(hataMetni(e), 'uyari');
        return null;
      } finally {
        setBekliyor(false);
      }
    },
    [bildirim, depo, kapat, obekListesi],
  );

  const teknik = depo.teknikler.find((t) => t.id === teknikId) ?? null;

  const ataEylemi = useCallback(
    (ek: { yineDe?: boolean } = {}) => {
      const x = aRef.current;
      if (!x) return;
      if (!teknikId) {
        bildirim.goster('Önce teknisyeni seçin.', 'uyari');
        govdeRef.current?.querySelector<HTMLInputElement>('.ip-planla input[type="search"]')?.focus();
        return;
      }
      const ad = kisaAd(teknik?.ad ?? depo.teknikler.find((t) => t.id === teknikId)?.ad);
      void calistir(
        () =>
          ata(x.is_no, {
            teknik_id: teknikId,
            randevu: dilim ? { bas: dilim.bas, bit: dilim.bit, teyitli: dilim.teyitli } : null,
            yine_de: ek.yineDe || yineDe,
            surum: x.surum,
          }),
        () => `${yonelme(ad)} atandı`,
      );
    },
    [teknikId, teknik, dilim, yineDe, calistir, bildirim, depo.teknikler],
  );

  const randevuKaydet = useCallback(() => {
    const x = aRef.current;
    if (!x || !dilim) return;
    void calistir(
      () => randevuVer(x.is_no, { bas: dilim.bas, bit: dilim.bit, teyitli: dilim.teyitli, surum: x.surum }),
      () => `Randevu verildi · ${dilimMetni(dilim.bas, dilim.bit)}`,
    );
  }, [dilim, calistir]);

  const durumEylemi = useCallback(
    (g: DurumGirdi, metin: string, kapanir = false) => {
      const x = aRef.current;
      if (!x) return;
      void calistir(() => durumDegistir(x.is_no, { ...g, surum: x.surum }), () => metin, { kapanir });
    },
    [calistir],
  );

  /* ------------------------------ klavye komutları (panodan) ------------------------------ */

  const islenenKomut = useRef(0);
  useEffect(() => {
    if (!komut || !a || islenenKomut.current === komut.n) return;
    islenenKomut.current = komut.n;
    const kutu = govdeRef.current;
    const kaydir = (secici: string) => kutu?.querySelector(secici)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    switch (komut.tur) {
      case 'teknik':
        setGorunum('ana');
        window.setTimeout(() => {
          kaydir('.ip-planla');
          kutu?.querySelector<HTMLInputElement>('.ip-planla input[type="search"]')?.focus();
        }, 30);
        break;
      case 'randevu':
        setGorunum('ana');
        window.setTimeout(() => kaydir('.ip-dilim-alani'), 30);
        break;
      case 'randevuTus': {
        const d = komut.deger ?? '';
        const dilimler = depo.ayarlar?.dilimler ?? [];
        const bugun = `${simdi.getFullYear()}-${String(simdi.getMonth() + 1).padStart(2, '0')}-${String(simdi.getDate()).padStart(2, '0')}`;
        const yarinD = new Date(simdi.getFullYear(), simdi.getMonth(), simdi.getDate() + 1);
        const yarin = `${yarinD.getFullYear()}-${String(yarinD.getMonth() + 1).padStart(2, '0')}-${String(yarinD.getDate()).padStart(2, '0')}`;
        if (/^[1-9]$/.test(d)) {
          const s = dilimler[Number(d) - 1];
          if (s) {
            setDilim((o) => ({ bas: `${bugun} ${s.bas}:00`, bit: `${bugun} ${s.bit}:00`, teyitli: o?.teyitli ?? false }));
            setPlanDegisti(true);
          }
        } else if (d === 'y' && dilimler[0]) {
          const s = dilimler[0];
          setDilim((o) => ({ bas: `${yarin} ${s.bas}:00`, bit: `${yarin} ${s.bit}:00`, teyitli: o?.teyitli ?? false }));
          setPlanDegisti(true);
        }
        window.setTimeout(() => kaydir('.ip-dilim-alani'), 30);
        break;
      }
      case 'obek':
        if (a.izinler.obek) setGorunum('obek');
        break;
      case 'ticket':
        if (a.izinler.ticket) setGorunum('ticket');
        break;
      case 'not':
        setGorunum('ana');
        window.setTimeout(() => {
          kaydir('.ip-not');
          notRef.current?.focus();
        }, 30);
        break;
      case 'gorunum':
        if (komut.deger) setGorunum(komut.deger as Gorunum);
        break;
      default:
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [komut, a]);

  if (!isNo) return null;

  /* ------------------------------ birincil eylem ------------------------------ */

  let birincil: { etiket: string; calistir: () => void; kapali?: boolean; ipucu?: string } | null = null;
  let ikincil: ReactNode = null;
  if (a && gorunum === 'ana') {
    const teknikte = a.durum === 'atandi' || a.durum === 'yolda' || a.durum === 'sahada';
    switch (a.birincil) {
      case 'obege_ata':
        birincil = { etiket: 'Öbeğe ata', calistir: () => setGorunum('obek') };
        break;
      case 'ata':
        birincil = { etiket: 'Ata', calistir: () => ataEylemi(), kapali: !teknikId };
        break;
      case 'ticketa_bagla':
        birincil = { etiket: 'Ticket’a bağla', calistir: () => setGorunum('ticket') };
        ikincil = (
          <button type="button" className="o-dugme metin" disabled={bekliyor || !teknikId} onClick={() => ataEylemi({ yineDe: true })}>
            Yine de ata
          </button>
        );
        break;
      case 'yeniden_ata':
        birincil = {
          etiket: 'Yeniden ata',
          calistir: () => ataEylemi(),
          kapali: !teknikId || !dilim?.teyitli,
          ipucu: !dilim?.teyitli ? 'Önce müşteriyle konuşup saati teyit edin.' : undefined,
        };
        break;
      case 'uyandir':
        birincil = { etiket: 'Uyandır', calistir: () => durumEylemi({ yeni: 'bekliyor' }, 'Uyandırıldı · Atanmadı listesinde') };
        break;
      case 'ticketi_ac':
        birincil = a.ticket
          ? { etiket: 'Ticket’ı aç', calistir: () => git(`/yonetici/ticketlar/${a.ticket!.id}`) }
          : null;
        break;
      case 'sahaya_al':
        birincil = { etiket: 'Sahaya al', calistir: () => durumEylemi({ yeni: 'bekliyor' }, 'Sahaya alındı · Atanmadı listesinde') };
        break;
      default:
        if (teknikte && planDegisti && a.izinler.ata) {
          const baskasi = teknikId && teknikId !== a.atanan?.id;
          birincil = baskasi
            ? { etiket: 'Kaydet', calistir: () => ataEylemi() }
            : { etiket: 'Kaydet', calistir: () => randevuKaydet(), kapali: !dilim };
        }
        break;
    }
  }

  const ustBaslik = a ? a.task_adi : 'İş';
  const altBaslik = a ? `${DURUM_ETIKET[a.durum]}${a.obek ? ` · ${a.obek.ad}` : ''}` : undefined;

  return (
    <>
      <Panel
        acik={Boolean(isNo)}
        kapat={kapat}
        baslik={ustBaslik}
        altBaslik={altBaslik}
        perdesiz
        genislik={440}
        alt={
          gorunum === 'ana' && a && (birincil || ikincil || a.durum === 'cozuldu') ? (
            <>
              {a.durum === 'cozuldu' && !birincil ? <span className="ip-alt-not">BOSS’ta kapanması bekleniyor.</span> : null}
              {birincil?.ipucu ? <span className="ip-alt-not">{birincil.ipucu}</span> : null}
              <span className="bosluk" />
              {ikincil}
              {birincil ? (
                <button
                  type="button"
                  className="o-dugme birincil ip-birincil"
                  disabled={bekliyor || birincil.kapali}
                  onClick={birincil.calistir}
                >
                  {bekliyor ? 'Bekleyin…' : birincil.etiket}
                </button>
              ) : null}
            </>
          ) : undefined
        }
      >
        <div className="ip-cekmece" ref={govdeRef}>
          {!a && !yukHata ? <div className="o-iskelet"><span style={{ height: 120 }} /><span style={{ height: 80 }} /><span style={{ height: 160 }} /></div> : null}
          {yukHata ? (
            <div className="o-hata" role="alert">
              <span className="mesaj">{yukHata}</span>
              <button type="button" className="o-dugme kucuk" onClick={() => void yukle(isNo, true)}>
                Tekrar dene
              </button>
            </div>
          ) : null}
          {a && gorunum === 'ana' ? (
            <AnaGorunum
              a={a}
              catisma={catisma}
              engel={engel}
              teknikId={teknikId}
              setTeknikId={(id) => {
                setTeknikId(id);
                setPlanDegisti(true);
              }}
              dilim={dilim}
              setDilim={(d) => {
                setDilim(d);
                setPlanDegisti(true);
              }}
              simdi={simdi}
              bekliyor={bekliyor}
              gorunumAc={setGorunum}
              yineDeUygula={() => birincil?.calistir()}
              yineDeAta={() => {
                setYineDe(true);
                ataEylemi({ yineDe: true });
              }}
              randevuKaydet={randevuKaydet}
              calistir={calistir}
              notRef={notRef}
              yenile={() => void yukle(a.is_no, false)}
              yeniTicketAc={() => setYeniTicket(true)}
            />
          ) : null}
          {a && gorunum !== 'ana' ? (
            <AltGorunum
              a={a}
              gorunum={gorunum}
              geri={() => setGorunum('ana')}
              calistir={calistir}
              durumEylemi={durumEylemi}
              bekliyor={bekliyor}
              simdi={simdi}
              yeniTicketAc={() => setYeniTicket(true)}
            />
          ) : null}
        </div>
      </Panel>
      {a ? (
        <YeniTicketPenceresi
          acik={yeniTicket}
          kapat={() => setYeniTicket(false)}
          bina={a.bina ? { bina_serial: a.bina.serial, baslik: a.bina.ad } : null}
          kaydedildi={(t: Ticket) => {
            setYeniTicket(false);
            const x = aRef.current;
            if (!x) return;
            void calistir(
              () => ticketBagla(x.is_no, { ticket_id: t.id, teknisyen_gonderme: true, surum: x.surum }),
              () => `Ticket #${t.id} açıldı ve işe bağlandı · teknisyen gönderilmeyecek`,
            );
          }}
        />
      ) : null}
    </>
  );
}

/* ================================================================== ana görünüm */

type Calistir = (
  fn: () => Promise<IsAyrinti>,
  metin: (y: IsAyrinti) => string,
  secenek?: { geriAlinir?: boolean; kapanir?: boolean },
) => Promise<IsAyrinti | null>;

function AnaGorunum({
  a,
  catisma,
  engel,
  teknikId,
  setTeknikId,
  dilim,
  setDilim,
  simdi,
  bekliyor,
  gorunumAc,
  yineDeUygula,
  yineDeAta,
  randevuKaydet,
  calistir,
  notRef,
  yenile,
  yeniTicketAc,
}: {
  a: IsAyrinti;
  catisma: string | null;
  engel: string | null;
  teknikId: number | null;
  setTeknikId: (id: number) => void;
  dilim: Dilim | null;
  setDilim: (d: Dilim | null) => void;
  simdi: Date;
  bekliyor: boolean;
  gorunumAc: (g: Gorunum) => void;
  yineDeUygula: () => void;
  yineDeAta: () => void;
  randevuKaydet: () => void;
  calistir: Calistir;
  notRef: React.RefObject<HTMLInputElement>;
  yenile: () => void;
  yeniTicketAc: () => void;
}) {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [not, setNot] = useState('');
  const [notGidiyor, setNotGidiyor] = useState(false);
  const acik = a.durum !== 'cozuldu' && a.durum !== 'kapandi';
  const dilimler = depo.ayarlar?.dilimler ?? [];
  const ilkSaat = dilimler.length ? parseInt(dilimler[0].bas, 10) : 8;
  const sonSaat = dilimler.length ? parseInt(dilimler[dilimler.length - 1].bit, 10) : 20;
  const obek = a.obek ? depo.obekler?.obekler.find((o) => o.id === a.obek!.id) : undefined;
  const taskNo = a.boss_task_no ?? a.is_no;
  const musteriVar = 'musteri_adi' in a || 'musteri_no' in a;
  const planla = acik && (a.izinler.ata || a.izinler.randevu);
  const teknikte = a.durum === 'atandi' || a.durum === 'yolda' || a.durum === 'sahada';
  const btkTeshis = a.serit === 'BTK' && !a.kotu_gecmis && a.masa_vade && !a.teshis_sonucu && acik;

  const notGonder = async () => {
    const metin = not.trim();
    if (!metin) return;
    setNotGidiyor(true);
    try {
      await notEkle(a.is_no, metin);
      setNot('');
      bildirim.goster('Not eklendi.', 'basari');
      yenile();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setNotGidiyor(false);
    }
  };

  const teshisEt = (sonuc: TeshisSonucu, metin: string, ek: { canli_test?: boolean } = {}) => {
    void calistir(() => teshis(a.is_no, { sonuc, surum: a.surum, ...ek }), () => metin);
  };

  return (
    <>
      {catisma ? (
        <div className="ip-uyari sari" role="alert">
          <span>{catisma}</span>
          <button type="button" className="o-dugme kucuk" onClick={yineDeUygula} disabled={bekliyor}>
            Yine de uygula
          </button>
        </div>
      ) : null}

      {/* 1. Başlık */}
      <section className="ip-c-bas">
        <div className="ip-c-sure">
          <SureHapi kalan_dk={kalanDk(a)} renk={a.renk} gecikti={a.gecikti} />
          {a.serit === 'BTK' ? <Rozet tur="btk" /> : null}
          {a.serit === 'BTK' && (a.btk_hedef_net || a.btk_hedef) ? (
            <span className="ip-c-hedef">BTK hedefi {saatMetni(a.btk_hedef_net ?? a.btk_hedef)}</span>
          ) : (
            <span className="ip-c-hedef">24 saat {saatMetni(a.son24)}</span>
          )}
          {a.btk_durdu ? <span className="ip-durdu">BTK saati durdu</span> : null}
        </div>
        {a.soz ? <p className="ip-soz">{a.soz}</p> : null}
        {a.oncelik ? <p className="ip-oncelik">{a.oncelik}</p> : null}
        <div className="ip-c-kimlik">
          <DurumYazisi etiket={DURUM_ETIKET[a.durum]} />
          {a.kaynak === 'bayi' ? <Rozet tur="bayi" /> : a.kanal_grubu === 'global' ? <Rozet tur="global" /> : null}
          {a.rozetler.includes('tekrar') ? <Rozet tur="tekrar" /> : null}
          {a.rozetler.includes('yeniden') ? <Rozet tur="yeniden" /> : null}
          <span className="ip-taskno">
            {a.boss_task_no ? 'Task No' : 'İş no'} <b>{taskNo}</b>
          </span>
          <KopyalaDugmesi metin={taskNo} />
        </div>
        <AdimCizgisi adim={adimNo(a)} adimlar={ADIMLAR} />
      </section>

      {/* 2. Müşteri */}
      {musteriVar ? (
        <Bolum baslik="Müşteri">
          <p className="ip-deger">{a.musteri_adi || 'Ad yok'}</p>
          <div className="ip-satir-eylemler">
            {a.musteri_no ? (
              <>
                <span className="ip-etiketli">
                  Müşteri No <b>{a.musteri_no}</b>
                </span>
                <KopyalaDugmesi metin={a.musteri_no} sonra={() => void kopyaKaydi(a.is_no).catch(() => undefined)} />
              </>
            ) : null}
          </div>
          <div className="ip-satir-eylemler">
            {a.boss_url ? (
              <a className="o-dugme kucuk" href={a.boss_url} target="_blank" rel="noreferrer">
                BOSS’ta aç
              </a>
            ) : a.boss_task_no ? (
              <KopyalaDugmesi metin={a.boss_task_no} etiket="Task No’yu kopyala" bildirim="Task No kopyalandı, BOSS’ta arayın." />
            ) : null}
            {a.musteri_tel ? (
              <a className="o-dugme kucuk" href={`tel:${a.musteri_tel}`}>
                Ara · {a.musteri_tel}
              </a>
            ) : null}
          </div>
        </Bolum>
      ) : null}

      {/* 3. Adres ve yer */}
      <Bolum baslik="Adres ve yer">
        {a.adres ? (
          <div className="ip-adres">
            <p className="ip-deger">{a.adres}</p>
            <div className="ip-satir-eylemler">
              <KopyalaDugmesi metin={a.adres} />
              {a.lat !== null && a.lon !== null ? (
                <a className="o-dugme kucuk metin" href={konumBaglantisi(a.lat, a.lon)} target="_blank" rel="noreferrer">
                  Haritada aç
                </a>
              ) : null}
            </div>
          </div>
        ) : null}
        <dl className="ip-bilgi">
          <dt>Mahalle</dt>
          <dd>
            {a.mahalle || '—'}
            {a.ilce ? ` · ${a.ilce}` : ''}
            {a.mahalle_kaynak ? <span className="ip-kaynak"> · {MAHALLE_KAYNAGI[a.mahalle_kaynak] ?? 'Adresten'}</span> : null}
            {a.izinler.obek && acik ? (
              <button type="button" className="o-bag ip-ic-bag" onClick={() => gorunumAc('mahalle')}>
                Mahalleyi seç
              </button>
            ) : null}
          </dd>
          {a.bina ? (
            <>
              <dt>Bina</dt>
              <dd>
                {a.bina.ad || a.bina.serial}
                {a.bina.location_id ? <span className="ip-kaynak"> · Location Id {a.bina.location_id}</span> : null}
                <button type="button" className="o-bag ip-ic-bag" onClick={() => git(`/bina/${encodeURIComponent(a.bina!.serial)}`)}>
                  Binayı aç
                </button>
              </dd>
            </>
          ) : null}
          <dt>Öbek</dt>
          <dd>
            {a.obek ? (
              <>
                <ObekNoktasi renk={a.obek.renk} /> {a.obek.ad}
                {a.obek_elle ? <span className="o-rozet" title="Öbeği elle seçildi; sonraki raporlarda korunur">elle</span> : null}
              </>
            ) : (
              'Öbeği yok'
            )}
            {a.izinler.obek ? (
              <>
                <button type="button" className="o-bag ip-ic-bag" onClick={() => gorunumAc('obek')}>
                  Öbeğe taşı
                </button>
                {a.obek_elle ? (
                  <button
                    type="button"
                    className="o-bag ip-ic-bag"
                    onClick={() => void calistir(() => obegeAta(a.is_no, null, a.surum), () => 'Öbek mahallesine göre seçildi')}
                  >
                    Mahallesine göre
                  </button>
                ) : null}
              </>
            ) : null}
          </dd>
          {obek?.sahip ? (
            <>
              <dt>Ev teknisyeni</dt>
              <dd>{obek.sahip.ad}</dd>
            </>
          ) : null}
        </dl>
        {a.konum_yaklasik ? <p className="ip-not-satiri">◌ Konum yaklaşık: bina değil, mahalle merkezi gösteriliyor.</p> : null}
        {a.triyaj_metni ? <p className="ip-uyari amber">{a.triyaj_metni}</p> : null}
      </Bolum>

      {/* EK-3: askı zaman çizelgesi ve net BTK saati */}
      {a.aski.length || a.durum === 'askida' ? (
        <Bolum baslik="Askı">
          {a.durum === 'askida' ? (
            <p className="ip-deger">
              {a.askida_neden || 'Askıda'}
              {a.uyanma ? <span className="ip-kaynak"> · uyanma {dilimMetni(a.uyanma, null)}</span> : <span className="ip-kaynak"> · uyanma yok</span>}
            </p>
          ) : null}
          {a.aski_uyari ? <p className="ip-uyari amber">{a.aski_uyari}</p> : null}
          <ol className="ip-aski">
            {a.aski.map((x) => (
              <li key={x.id}>
                <span className="zaman">
                  {olayZamani(x.baslama)}
                  {x.yaklasik ? ' (yaklaşık)' : ''} → {x.bitis ? olayZamani(x.bitis) : 'sürüyor'}
                </span>
                <span className="ne">
                  {x.neden || 'Askı'}
                  {x.kaynak === 'boss' ? ' · BOSS' : ''}
                </span>
                <span className={`saat${x.durdurur ? ' durdu' : ''}`}>
                  {x.durdurur ? `BTK saati durdu · ${sureMetni(x.sure_dk)}` : `saat işledi · ${sureMetni(x.sure_dk)}`}
                </span>
              </li>
            ))}
          </ol>
          {a.serit === 'BTK' && a.aski_durdu_dk > 0 ? (
            <p className="ip-not-satiri">
              BTK saati toplam {sureMetni(a.aski_durdu_dk)} durdu
              {a.btk_net_gecen_dk !== null ? ` · net geçen ${sureMetni(a.btk_net_gecen_dk)}` : ''}. Rapordan gelen askıların
              başlangıcı yaklaşıktır.
            </p>
          ) : null}
        </Bolum>
      ) : null}

      {/* EK-12.2: BTK şikâyet sayacı */}
      {a.btk_sikayet ? (
        <Bolum baslik="BTK şikâyeti">
          <p className="ip-deger">
            {a.btk_sikayet.gecen_is_gunu}/{a.btk_sikayet.sure_is_gunu} iş günü
            {a.btk_sikayet.reopen ? ' · reopen' : ''} · son gün {dilimMetni(a.btk_sikayet.son_gun, null)}
          </p>
          {a.btk_sikayet.alarm ? <p className="ip-uyari amber">Alarm: {a.btk_sikayet.alarm}</p> : null}
          {a.btk_sikayet.btk_kapali ? <Hap renk="amber">BTK’da kapalı, FOX’ta açık</Hap> : null}
        </Bolum>
      ) : null}

      {/* 4. Planla */}
      {planla ? (
        <Bolum baslik={teknikte ? 'Teknisyen ve randevu' : 'Planla'}>
          <div className="ip-planla">
            <p className="ip-alan-etiket">
              Teknisyen
              {a.atanan ? <span className="ip-kaynak"> · şu an {a.atanan.ad}</span> : null}
            </p>
            {a.oneri && !a.atanan ? <p className="ip-not-satiri">Öneri: {a.oneri.teknik.ad} · {a.oneri.neden}</p> : null}
            <TeknikSecici
              teknikler={depo.teknikler}
              deger={teknikId}
              degisti={setTeknikId}
              obekId={a.obek?.id}
              onerilen={a.oneri?.teknik.id ?? null}
            />
          </div>
          <div className="ip-dilim-alani">
            <p className="ip-alan-etiket">
              Gün ve saat <span className="ip-kaynak">(müşteriye söylenecek tahmini varış)</span>
            </p>
            <DilimSecici deger={dilim} degisti={setDilim} ilkSaat={ilkSaat} sonSaat={sonSaat} simdi={simdi} />
            {a.boss.randevu_bas ? (
              <p className="ip-not-satiri">BOSS: {dilimMetni(a.boss.randevu_bas, a.boss.randevu_bit)}</p>
            ) : null}
            {a.durum === 'ulasilamadi' ? (
              <p className="ip-uyari amber">Müşteriye ulaşılmadan aynı işe ikinci kez teknisyen gönderilmez. “Saat teyitli”yi işaretleyin.</p>
            ) : null}
            <div className="ip-satir-eylemler">
              {!a.atanan && dilim && a.izinler.randevu && a.kova === 'atanmadi' ? (
                <button type="button" className="o-dugme kucuk metin" onClick={randevuKaydet} disabled={bekliyor}>
                  Yalnız randevu ver (teknisyensiz)
                </button>
              ) : null}
              {a.randevu?.kaynak === 'biz' && a.izinler.randevu ? (
                <button
                  type="button"
                  className="o-dugme kucuk metin"
                  disabled={bekliyor}
                  onClick={() => void calistir(() => randevuVer(a.is_no, { bas: null, surum: a.surum }), () => 'Randevu kaldırıldı')}
                >
                  Randevuyu kaldır
                </button>
              ) : null}
            </div>
          </div>
          {engel ? (
            <div className="ip-uyari sari" role="alert">
              <span>{engel}</span>
              <div className="ip-satir-eylemler">
                <button type="button" className="o-dugme kucuk" onClick={() => gorunumAc('ticket')}>
                  Ticket’a bağla
                </button>
                <button type="button" className="o-dugme kucuk metin" onClick={yineDeAta} disabled={bekliyor}>
                  Yine de ata
                </button>
              </div>
            </div>
          ) : null}
        </Bolum>
      ) : null}

      {/* 5. Ticket */}
      {a.izinler.ticket || a.ticket ? (
        <Bolum baslik="Ticket">
          {a.ticket ? (
            <>
              <p className="ip-deger">
                Bağlı: #{a.ticket.id} · {a.ticket.konu} · {a.ticket.durum} · {a.ticket.gun} gündür
              </p>
              <div className="ip-satir-eylemler">
                <button type="button" className="o-dugme kucuk" onClick={() => git(`/yonetici/ticketlar/${a.ticket!.id}`)}>
                  Ticket’ı aç
                </button>
                {a.izinler.ticket ? (
                  <button
                    type="button"
                    className="o-dugme kucuk metin"
                    disabled={bekliyor}
                    onClick={() => void calistir(() => ticketAyir(a.is_no, a.surum), () => 'Ticket’tan ayrıldı · iş Atanmadı listesinde')}
                  >
                    Ticket’tan ayır
                  </button>
                ) : null}
              </div>
            </>
          ) : a.binada_acik_ticket > 0 ? (
            <div className="ip-uyari sari">
              <span>
                Bu binada açık {a.binada_acik_ticket === 1 ? 'bir' : a.binada_acik_ticket} ticket var. Teknisyen gönderilmez.
              </span>
              <button type="button" className="o-dugme kucuk" onClick={() => gorunumAc('ticket')}>
                Ticket’a bağla
              </button>
            </div>
          ) : (
            <div className="ip-satir-eylemler">
              <span className="ip-sessiz">Binada açık ticket yok.</span>
              {a.izinler.ticket ? (
                <button type="button" className="o-dugme kucuk metin" onClick={() => gorunumAc('ticket')}>
                  Ticket bağla / aç
                </button>
              ) : null}
            </div>
          )}
        </Bolum>
      ) : null}

      {/* 6. BTK teşhisi (masa araması) */}
      {btkTeshis ? (
        <Bolum baslik={`Masa araması · vade ${saatMetni(a.masa_vade)}`}>
          <p className="ip-not-satiri">Müşteriyi arayın; sonucu tek dokunuşla işleyin.</p>
          <TeshisDugmeleri a={a} teshisEt={teshisEt} bekliyor={bekliyor} />
        </Bolum>
      ) : null}
      {a.merdiven && (a.durum === 'ulasilamadi' || (a.aramalar?.length ?? 0) > 0) ? (
        <p className="ip-not-satiri">
          Arama merdiveni: {a.merdiven.gecerli}/{a.merdiven.gerekli}
          {a.merdiven.sonraki ? ` · sonraki arama ${dilimMetni(a.merdiven.sonraki, null)}` : ''}
          {a.merdiven.sms_eksik ? ` · ${a.merdiven.sms_eksik} SMS BOSS’a işlenecek` : ''}
          {a.merdiven.tamam ? ' · merdiven tamam' : ''}
        </p>
      ) : null}

      {/* 7. BOSS'a işlenecek (EK-4 giden kutusu) */}
      {a.boss_giden ? (
        <Bolum baslik="BOSS’a işlenecek">
          <BossGidenAlanlari g={a.boss_giden} />
          <label className="o-onay-kutusu">
            <input
              type="checkbox"
              checked={false}
              disabled={bekliyor}
              onChange={() =>
                void calistir(() => bossIslendi(a.is_no, true, a.surum), () => 'BOSS’a işlendi olarak işaretlendi', { geriAlinir: false })
              }
            />
            <span>BOSS’a işlendi</span>
          </label>
        </Bolum>
      ) : null}

      {/* 8. Diğer */}
      <DigerEylemler a={a} gorunumAc={gorunumAc} calistir={calistir} bekliyor={bekliyor} yeniTicketAc={yeniTicketAc} />

      {/* 9. Not */}
      <section className="ip-not">
        <input
          ref={notRef}
          className="o-girdi"
          value={not}
          maxLength={1000}
          placeholder="Not yazın…"
          aria-label="Not"
          onChange={(o) => setNot(o.target.value)}
          onKeyDown={(o) => {
            if (o.key === 'Enter') {
              o.preventDefault();
              void notGonder();
            }
          }}
        />
        <button type="button" className="o-dugme kucuk" disabled={!not.trim() || notGidiyor} onClick={() => void notGonder()}>
          Ekle
        </button>
      </section>

      {/* 10. Geçmiş */}
      <details className="ip-acilir">
        <summary>Geçmiş ({a.olaylar.length})</summary>
        <ol className="ip-gecmis">
          {a.olaylar.map((o) => (
            <li key={o.id}>
              <span className="zaman">{olayZamani(o.zaman)}</span>
              <span className="kisi">{o.kisi ? kisaAd(o.kisi) : 'Sistem'}</span>
              <span className="ozet">
                {o.ozet}
                {o.notu && o.tur !== 'not' && o.notu !== o.ozet ? <span className="ip-kaynak"> · {o.notu}</span> : null}
              </span>
            </li>
          ))}
        </ol>
      </details>

      {/* 11. BOSS bilgisi */}
      <details className="ip-acilir">
        <summary>BOSS bilgisi</summary>
        <dl className="ip-bilgi">
          <dt>Durum</dt>
          <dd>{a.boss.durum || '—'}</dd>
          <dt>Ekip</dt>
          <dd>{a.boss.ekip || '—'}</dd>
          <dt>Randevu durumu</dt>
          <dd>{a.boss.randevu_durumu || '—'}</dd>
          <dt>Randevu</dt>
          <dd>{a.boss.randevu_bas ? dilimMetni(a.boss.randevu_bas, a.boss.randevu_bit) : '—'}</dd>
          <dt>Askı nedeni</dt>
          <dd>{a.boss.aski_nedeni || '—'}</dd>
          <dt>SL</dt>
          <dd>{a.boss.sl ? `${a.boss.sl}${a.boss.sl_saat ? ` (${a.boss.sl_saat} s)` : ''}` : '—'}</dd>
          <dt>Son açıklama</dt>
          <dd>{a.boss.son_aciklama || '—'}</dd>
          <dt>Lokasyon</dt>
          <dd>{a.lokasyon || '—'}</dd>
          <dt>Açılış</dt>
          <dd>{tarihSaatMetni(a.acilis)}</dd>
          <dt>Sisteme geliş</dt>
          <dd>{tarihSaatMetni(a.gorulme_zamani)}</dd>
        </dl>
      </details>
    </>
  );
}

function TeshisDugmeleri({
  a,
  teshisEt,
  bekliyor,
}: {
  a: IsAyrinti;
  teshisEt: (s: TeshisSonucu, metin: string, ek?: { canli_test?: boolean }) => void;
  bekliyor: boolean;
}) {
  return (
    <div className="ip-teshis">
      {!a.rozetler.includes('tekrar') ? (
        <button type="button" className="o-dugme kucuk" disabled={bekliyor} onClick={() => teshisEt('duzeldi', 'Düzeldi · telefonda çözüldü', { canli_test: true })}>
          Düzeldi (canlı test yapıldı)
        </button>
      ) : null}
      <button type="button" className="o-dugme kucuk" disabled={bekliyor} onClick={() => teshisEt('simdi_evde', 'Şimdi evde · randevu 3 saat içinde, teyitli')}>
        Şimdi evde
      </button>
      <button type="button" className="o-dugme kucuk" disabled={bekliyor} onClick={() => teshisEt('cevapsiz', 'Cevapsız kaydedildi · BOSS’ta Talep Ulaşamama SMS’i gönderin')}>
        Cevapsız
      </button>
      <button type="button" className="o-dugme kucuk" disabled={bekliyor} onClick={() => teshisEt('kapali', 'Kapalı kaydedildi · BOSS’ta Talep Ulaşamama SMS’i gönderin')}>
        Kapalı
      </button>
      <button type="button" className="o-dugme kucuk" disabled={bekliyor} onClick={() => teshisEt('yanlis_no', 'Yanlış numara · iş ATA havuzuna alındı')}>
        Yanlış numara
      </button>
    </div>
  );
}

/** EK-4: BOSS'a birebir yazılacak değerler, her biri kopyalanır. */
export function BossGidenAlanlari({ g }: { g: NonNullable<IsAyrinti['boss_giden']> }) {
  const parca = g.neden.split(',');
  return (
    <dl className="ip-bilgi ip-giden">
      {g.boss_task_no ? (
        <>
          <dt>Task No</dt>
          <dd>
            {g.boss_task_no} <KopyalaDugmesi metin={g.boss_task_no} />
          </dd>
        </>
      ) : null}
      {parca.includes('ekip') && g.alanlar.ekip ? (
        <>
          <dt>Ekip</dt>
          <dd>
            {g.alanlar.ekip} <KopyalaDugmesi metin={g.alanlar.ekip} />
          </dd>
        </>
      ) : null}
      {(parca.includes('randevu') || parca.includes('ekip')) && g.alanlar.randevu_baslangic ? (
        <>
          <dt>Randevu başlangıç</dt>
          <dd>
            {tarihSaatMetni(g.alanlar.randevu_baslangic)} <KopyalaDugmesi metin={tarihSaatMetni(g.alanlar.randevu_baslangic)} />
          </dd>
          <dt>Randevu bitiş</dt>
          <dd>
            {tarihSaatMetni(g.alanlar.randevu_bitis)} <KopyalaDugmesi metin={tarihSaatMetni(g.alanlar.randevu_bitis)} />
          </dd>
        </>
      ) : null}
      {parca.includes('aski') ? (
        <>
          <dt>Askı nedeni</dt>
          <dd>
            {g.alanlar.aski_nedeni || '—'} {g.alanlar.aski_nedeni ? <KopyalaDugmesi metin={g.alanlar.aski_nedeni} /> : null}
          </dd>
          <dt>Uyanma</dt>
          <dd>{g.alanlar.uyanma ? tarihSaatMetni(g.alanlar.uyanma) : '—'}</dd>
        </>
      ) : null}
      {parca.includes('sms') || g.alanlar.talep_ulasamama_sms ? (
        <>
          <dt>SMS</dt>
          <dd>BOSS’ta “Talep Ulaşamama SMS” gönderin.</dd>
        </>
      ) : null}
    </dl>
  );
}

/* ================================================================== diğer eylemler */

function DigerEylemler({
  a,
  gorunumAc,
  calistir,
  bekliyor,
  yeniTicketAc,
}: {
  a: IsAyrinti;
  gorunumAc: (g: Gorunum) => void;
  calistir: Calistir;
  bekliyor: boolean;
  yeniTicketAc: () => void;
}) {
  const d = a.izinler.durumlar;
  const ogeler: Array<{ etiket: string; tikla: () => void; yikici?: boolean }> = [];
  if (d.includes('ulasilamadi')) ogeler.push({ etiket: 'Evde yok', tikla: () => gorunumAc('evdeyok') });
  if (d.includes('askida') && a.durum !== 'askida') ogeler.push({ etiket: 'Askıya al', tikla: () => gorunumAc('aski') });
  if (a.durum === 'askida') ogeler.push({ etiket: 'Uyanmayı değiştir', tikla: () => gorunumAc('aski') });
  if (a.izinler.ofisten_kapat) ogeler.push({ etiket: 'Ofisten kapat', tikla: () => gorunumAc('kapat') });
  if (d.includes('merkeze')) ogeler.push({ etiket: 'Merkeze gönderildi', tikla: () => gorunumAc('merkeze') });
  if (a.izinler.yeniden_ac) ogeler.push({ etiket: 'Yeniden aç', tikla: () => gorunumAc('yenidenac') });
  if (a.izinler.boss_bagla) ogeler.push({ etiket: 'BOSS Task No’yu bağla', tikla: () => gorunumAc('bossbagla') });
  if (a.izinler.ticket && !a.ticket) ogeler.push({ etiket: 'Yeni ticket aç', tikla: yeniTicketAc });
  if (a.durum === 'randevulu' && a.izinler.randevu)
    ogeler.push({
      etiket: 'Randevuyu kaldır',
      tikla: () => void calistir(() => randevuVer(a.is_no, { bas: null, surum: a.surum }), () => 'Randevu kaldırıldı'),
    });
  if (!ogeler.length) return null;
  return (
    <>
      {a.bayi_oneri && a.izinler.boss_bagla ? (
        <div className="ip-uyari mavi">
          <span>BOSS’ta {a.bayi_oneri.boss_task_no} olarak açılmış olabilir.</span>
          <button
            type="button"
            className="o-dugme kucuk"
            disabled={bekliyor}
            onClick={() =>
              void calistir(() => bossBagla(a.is_no, a.bayi_oneri!.boss_task_no, a.surum), () => 'BOSS Task No’ya bağlandı')
            }
          >
            Bağla
          </button>
        </div>
      ) : null}
      <Bolum baslik="Diğer">
        <div className="ip-diger">
          {ogeler.map((o) => (
            <button key={o.etiket} type="button" className="o-dugme kucuk metin" onClick={o.tikla} disabled={bekliyor}>
              {o.etiket}
            </button>
          ))}
        </div>
      </Bolum>
    </>
  );
}

/* ================================================================== alt görünümler */

function uyanmaSecenekleri(simdi: Date): Array<{ etiket: string; an: Date }> {
  const yarin10 = new Date(simdi.getFullYear(), simdi.getMonth(), simdi.getDate() + 1, 10, 0, 0);
  return [
    { etiket: '2 saat sonra', an: new Date(simdi.getTime() + 2 * 3600e3) },
    { etiket: 'Yarın 10:00', an: yarin10 },
    { etiket: '2 gün sonra', an: new Date(yarin10.getTime() + 24 * 3600e3) },
    { etiket: '3 gün sonra', an: new Date(yarin10.getTime() + 2 * 24 * 3600e3) },
  ];
}

function sunucuMetni(d: Date): string {
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${iki(d.getMonth() + 1)}-${iki(d.getDate())} ${iki(d.getHours())}:${iki(d.getMinutes())}:00`;
}

function AltGorunum({
  a,
  gorunum,
  geri,
  calistir,
  durumEylemi,
  bekliyor,
  simdi,
  yeniTicketAc,
}: {
  a: IsAyrinti;
  gorunum: Gorunum;
  geri: () => void;
  calistir: Calistir;
  durumEylemi: (g: DurumGirdi, metin: string, kapanir?: boolean) => void;
  bekliyor: boolean;
  simdi: Date;
  yeniTicketAc: () => void;
}) {
  const depo = useIsler();
  const [neden, setNeden] = useState('');
  const [aciklama, setAciklama] = useState('');
  const [uyanma, setUyanma] = useState<string>('');
  const [onay, setOnay] = useState(false);
  const [canli, setCanli] = useState(false);
  const [taskNo, setTaskNo] = useState('');
  const [teknikId, setTeknikId] = useState<number | null>(a.atanan?.id ?? null);
  const [ticketlar, setTicketlar] = useState<Ticket[] | null>(null);
  const [ticketSecili, setTicketSecili] = useState<number | null>(null);
  const [gonderme, setGonderme] = useState(true);
  const ayar = depo.ayarlar;

  useEffect(() => {
    if (gorunum !== 'ticket' || !a.bina) return;
    let iptal = false;
    binaAyrinti(a.bina.serial)
      .then((b) => {
        if (iptal) return;
        const acik = (b.ticketlar ?? []).filter((t) => t.acik);
        setTicketlar(acik);
        if (acik.length === 1) setTicketSecili(acik[0].id);
      })
      .catch(() => !iptal && setTicketlar([]));
    return () => {
      iptal = true;
    };
  }, [gorunum, a.bina]);

  const baslik: Record<Gorunum, string> = {
    ana: '',
    obek: 'Öbeğe taşı',
    mahalle: 'Mahalleyi seç',
    ticket: 'Ticket’a bağla',
    aski: a.durum === 'askida' ? 'Uyanmayı değiştir' : 'Askıya al',
    kapat: 'Ofisten kapat',
    merkeze: 'Merkeze gönderildi',
    evdeyok: 'Evde yok',
    yenidenac: 'Yeniden aç',
    bossbagla: 'BOSS Task No’yu bağla',
  };

  let icerik: ReactNode = null;
  let birincil: { etiket: string; tikla: () => void; kapali?: boolean; yikici?: boolean } | null = null;

  switch (gorunum) {
    case 'obek':
      icerik = (
        <>
          <p className="ip-not-satiri">
            Seçtiğiniz öbek bu işe elle yazılır; sonraki raporlarda korunur. Mahallenin kendisini bir öbeğe eklemek için Öbekler
            ekranını kullanın.
          </p>
          <ObekSecici
            obekler={depo.obekler?.obekler ?? []}
            deger={a.obek?.id}
            sec={(o) => void calistir(() => obegeAta(a.is_no, o.id, a.surum), () => `Öbek: ${o.ad}`)}
          />
        </>
      );
      break;
    case 'mahalle':
      icerik = (
        <MahalleSecici
          tek
          baslangicSorgu={a.mahalle ?? ''}
          ilce={a.ilce && a.il ? { il: a.il, ilce: a.ilce } : null}
          tekSec={(m: MahalleKaydi) =>
            void calistir(() => mahalleSec(a.is_no, m.id, a.surum), () => `Mahalle: ${m.ad} · ${m.ilce}`)
          }
        />
      );
      break;
    case 'ticket':
      icerik = (
        <>
          {!a.bina ? <p className="ip-not-satiri">Bu işin binası bilinmiyor; yeni ticket açarken binayı seçin.</p> : null}
          {a.bina && ticketlar === null ? <div className="o-iskelet"><span style={{ height: 56 }} /></div> : null}
          {ticketlar && ticketlar.length ? (
            <div className="ip-secim-liste" role="radiogroup" aria-label="Binadaki açık ticket'lar">
              {ticketlar.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="radio"
                  aria-checked={ticketSecili === t.id}
                  className={ticketSecili === t.id ? 'secili' : undefined}
                  onClick={() => setTicketSecili(t.id)}
                >
                  <span className="ad">
                    #{t.id} {t.konu_etiket}
                  </span>
                  <span className="bilgi">
                    {t.ticket_no ? `OneDesk ${t.ticket_no} · ` : ''}
                    {t.durum} · {t.acik_gun ?? 0} gündür
                  </span>
                </button>
              ))}
            </div>
          ) : null}
          {ticketlar && !ticketlar.length ? <p className="ip-sessiz">Bu binada açık ticket yok.</p> : null}
          <label className="o-onay-kutusu">
            <input type="checkbox" checked={gonderme} onChange={(o) => setGonderme(o.target.checked)} />
            <span>Teknisyen gönderilmesin (ticket çözülünce iş geri gelir)</span>
          </label>
          <button type="button" className="o-dugme kucuk metin" onClick={yeniTicketAc}>
            Yeni ticket aç…
          </button>
        </>
      );
      birincil = {
        etiket: 'Bağla',
        kapali: !ticketSecili,
        tikla: () =>
          void calistir(
            () => ticketBagla(a.is_no, { ticket_id: ticketSecili!, teknisyen_gonderme: gonderme, surum: a.surum }),
            () => (gonderme ? `Ticket #${ticketSecili}’e bağlandı · teknisyen gönderilmeyecek` : `Ticket #${ticketSecili}’e bağlandı`),
          ),
      };
      break;
    case 'aski': {
      const nedenler = ayar?.aski_nedenleri ?? [];
      icerik = (
        <>
          {a.durum !== 'askida' ? (
            <div className="o-alan">
              <span className="etiket">Neden?</span>
              <div className="ip-secim-liste" role="radiogroup" aria-label="Askı nedeni">
                {nedenler.map((n) => (
                  <button
                    key={n.kod || n.metin}
                    type="button"
                    role="radio"
                    aria-checked={neden === (n.kod || n.metin)}
                    className={neden === (n.kod || n.metin) ? 'secili' : undefined}
                    onClick={() => setNeden(n.kod || n.metin)}
                  >
                    <span className="ad">{n.metin}</span>
                    {a.serit === 'BTK' ? (
                      <span className="bilgi">{n.durdurur ? 'BTK saati durur' : 'BTK saati işler'}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          <div className="o-alan">
            <span className="etiket">Ne zaman tekrar bakılsın?</span>
            <CipSirasi etiket="Uyanma">
              {uyanmaSecenekleri(simdi).map((u) => {
                const m = sunucuMetni(u.an);
                return (
                  <Cip key={u.etiket} secili={uyanma === m} onClick={() => setUyanma(m)}>
                    {u.etiket}
                  </Cip>
                );
              })}
            </CipSirasi>
            <input
              className="o-girdi"
              type="datetime-local"
              aria-label="Uyanma zamanı"
              value={uyanma ? uyanma.slice(0, 16).replace(' ', 'T') : ''}
              onChange={(o) => setUyanma(o.target.value ? `${o.target.value.replace('T', ' ')}:00` : '')}
            />
            <span className="aciklama">Üst sınır nedene göre sunucuda denetlenir (abone kaynaklı en çok 4 gün, malzeme 8 saat).</span>
          </div>
          <div className="o-alan">
            <span className="etiket">Açıklama (isteğe bağlı)</span>
            <input className="o-girdi" value={aciklama} maxLength={900} onChange={(o) => setAciklama(o.target.value)} />
          </div>
        </>
      );
      birincil = {
        etiket: a.durum === 'askida' ? 'Uyanmayı kaydet' : 'Askıya al',
        kapali: !uyanma || (a.durum !== 'askida' && !neden),
        tikla: () =>
          durumEylemi(
            { yeni: 'askida', neden: neden || a.askida_neden || undefined, uyanma, notu: aciklama || undefined },
            a.durum === 'askida' ? 'Uyanma değişti' : 'Askıya alındı',
          ),
      };
      break;
    }
    case 'kapat': {
      const nedenler = (ayar?.kapanis_nedenleri ?? []).filter(
        (n) => n.kod !== 'musteriye_ulasilamadi' || a.merdiven?.tamam,
      );
      icerik = (
        <>
          <div className="ip-secim-liste" role="radiogroup" aria-label="Kapatma nedeni">
            {nedenler.map((n) => (
              <button
                key={n.kod}
                type="button"
                role="radio"
                aria-checked={neden === n.kod}
                className={neden === n.kod ? 'secili' : undefined}
                disabled={n.kod === 'telefonda_cozuldu' && a.rozetler.includes('tekrar')}
                onClick={() => setNeden(n.kod)}
              >
                <span className="ad">{n.metin}</span>
                {n.kod === 'telefonda_cozuldu' && a.rozetler.includes('tekrar') ? (
                  <span className="bilgi">Tekrar arıza telefonda kapatılamaz</span>
                ) : null}
              </button>
            ))}
          </div>
          {neden === 'telefonda_cozuldu' ? (
            <label className="o-onay-kutusu">
              <input type="checkbox" checked={canli} onChange={(o) => setCanli(o.target.checked)} />
              <span>Canlı test yapıldı (hız testi, kanal açılıyor)</span>
            </label>
          ) : null}
          {!a.merdiven?.tamam ? (
            <p className="ip-not-satiri">“Müşteriye ulaşılamadı” kapanışı arama merdiveni tamamlanınca açılır.</p>
          ) : null}
        </>
      );
      birincil = {
        etiket: 'Kapat',
        kapali: !neden || (neden === 'telefonda_cozuldu' && !canli),
        tikla: () => durumEylemi({ yeni: 'cozuldu', neden, canli_test: canli || undefined }, 'Ofisten kapatıldı', true),
      };
      break;
    }
    case 'merkeze':
      icerik = (
        <div className="o-alan">
          <span className="etiket">Neden merkeze gönderildi?</span>
          <input className="o-girdi" value={neden} maxLength={200} autoFocus onChange={(o) => setNeden(o.target.value)} />
        </div>
      );
      birincil = {
        etiket: 'Kaydet',
        kapali: !neden.trim(),
        tikla: () => durumEylemi({ yeni: 'merkeze', neden: neden.trim() }, 'Merkeze gönderildi olarak işaretlendi'),
      };
      break;
    case 'evdeyok':
      icerik = (
        <label className="o-onay-kutusu ip-uzun">
          <input type="checkbox" checked={onay} onChange={(o) => setOnay(o.target.checked)} />
          <span>10 dk bekledim, BOSS’tan 2 kez aradım, not bıraktım.</span>
        </label>
      );
      birincil = {
        etiket: 'Evde yok olarak işle',
        kapali: !onay,
        tikla: () => durumEylemi({ yeni: 'ulasilamadi' }, 'Evde yok · Aranacaklar listesine düştü'),
      };
      break;
    case 'yenidenac':
      icerik = (
        <>
          <div className="o-alan">
            <span className="etiket">Neden yeniden açıyorsunuz?</span>
            <input className="o-girdi" value={neden} maxLength={300} onChange={(o) => setNeden(o.target.value)} />
          </div>
          <p className="ip-alan-etiket">Teknisyen</p>
          <TeknikSecici teknikler={depo.teknikler} deger={teknikId} degisti={setTeknikId} obekId={a.obek?.id} />
        </>
      );
      birincil = {
        etiket: 'Yeniden aç',
        kapali: !neden.trim() || !teknikId,
        tikla: () => durumEylemi({ yeni: 'atandi', neden: neden.trim(), teknik_id: teknikId! }, 'Yeniden açıldı ve atandı'),
      };
      break;
    case 'bossbagla':
      icerik = (
        <div className="o-alan">
          <span className="etiket">BOSS Task No (9 hane)</span>
          <input
            className="o-girdi"
            inputMode="numeric"
            value={taskNo}
            maxLength={9}
            autoFocus
            onChange={(o) => setTaskNo(o.target.value.replace(/\D/g, ''))}
          />
          <span className="aciklama">Bağlanınca sonraki rapor bu satırı günceller; iş iki kez sayılmaz.</span>
        </div>
      );
      birincil = {
        etiket: 'Bağla',
        kapali: taskNo.length !== 9,
        tikla: () => void calistir(() => bossBagla(a.is_no, taskNo, a.surum), () => `BOSS Task No ${taskNo} bağlandı`),
      };
      break;
    default:
      break;
  }

  return (
    <div className="ip-alt-gorunum">
      <div className="ip-alt-bas">
        <button type="button" className="o-dugme kucuk metin" onClick={geri}>
          ‹ Geri
        </button>
        <h3>{baslik[gorunum]}</h3>
        <Kbd>Esc</Kbd>
      </div>
      <div className="ip-alt-icerik">{icerik}</div>
      {birincil ? (
        <div className="ip-alt-alt">
          <button type="button" className="o-dugme" onClick={geri} disabled={bekliyor}>
            Vazgeç
          </button>
          <button
            type="button"
            className={`o-dugme ${birincil.yikici ? 'yikici' : 'birincil'}`}
            disabled={bekliyor || birincil.kapali}
            onClick={birincil.tikla}
          >
            {bekliyor ? 'Bekleyin…' : birincil.etiket}
          </button>
        </div>
      ) : null}
    </div>
  );
}
