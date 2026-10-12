/**
 * İş çekmecesi: masaüstünde sağdan 440 px (liste açık kalır), telefonda tam ekran. Yeniden düzen (08.10):
 *
 *   1. Baş: BOSS durumu çipi + rozetler + BOSS’ta aç / haritada aç; Task No · Müşteri No · Ad · Telefon · Adres ·
 *      Randevu · Ekip (IsKimlik, iki sütun).
 *   2. İşlem (sekmeli): Ata · Askıya al · Not — TOPLU eylemlerle AYNI parçalar ve AYNI uçlar:
 *        Ata       = TopluAta.tsx `useAtaFormu({ tek })`  → POST /api/isler/toplu-ata (1 iş)
 *        Askıya al = TopluAski.tsx `useAskiFormu({ tek })` → POST /api/isler/toplu-aski (1 iş)
 *        Not       = IsNotlari (POST /api/isler/{no}/not)
 *      Her biri BOSS yazma hâlini gösterir: BOSS’a gidiyor · BOSS’ta ✓ · hata (BOSS mesajı) + Yeniden dene.
 *   3. BOSS ayrıntısı (canlı sekmeler) · Yer (mahalle, bina, haritada aç) · Ticket (varsa) · masa araması (BTK).
 *   4. Geçmiş ve iç BTK notu kapalı başlar.
 *   BOSS’a YAZMAYAN eylemler (Evde yok, Ofisten kapat, Merkeze gönderildi, Atamayı kaldır, Uyandır, Öbek, Ticket …)
 *   başlıktaki ⋯ menüsündedir ("Yalnız uygulamada") ve tek soruluk alt görünüm açar; Esc önce onu kapatır.
 * 409 `guncel_degil`: çekmece güncel hâle döner, sarı satırda kimin ne yaptığı yazar.
 *
 * Açılış: TASKS'ta yalnız satır başındaki "i" ya da Enter/Space (hücreye tıklamak açmaz). En üstte satırın
 * uyarıları (TASKS Uyarı sütunuyla aynı; ayrıntıda yoksa listedeki satırdan).
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react';
import {
  bossAtamaYeniden,
  bossBagla,
  durumDegistir,
  geriAl,
  hataMetni,
  IsHatasi,
  isGetir,
  kopyaKaydi,
  mahalleSec,
  obegeAta,
  randevuVer,
  teshis,
  ticketAyir,
  ticketBagla,
  type DurumGirdi,
  type TeshisSonucu,
} from '../../../cekirdek/is/api';
import type { IsAyrinti, MahalleKaydi, Obek } from '../../../cekirdek/is/tipler';
import { DURUM_ETIKET } from '../../../cekirdek/is/tipler';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { KopyalaNo } from '../../../cekirdek/ortak/KopyalaNo';
import { Rozet, Hap } from '../../../cekirdek/ortak/Rozet';
import type { Dilim } from '../../../cekirdek/ortak/DilimSecici';
import { Kbd } from '../../../cekirdek/ortak/Kbd';
import { DahaMenusu, type MenuOgesi } from '../../../cekirdek/ortak/Menu';
import { sureMetni, sunucuZamani } from '../../../cekirdek/ortak/sure';
import { konumBaglantisi } from '../../../cekirdek/ortak/kimlik';
import { binaAyrinti } from '../../../cekirdek/api/uclar';
import type { Ticket } from '../../../cekirdek/api/tipler';
import { git } from '../../../cekirdek/yol/rota';
import { YeniTicketPenceresi } from '../../../cekirdek/ticket/YeniTicket';
import { MahalleSecici } from '../obekler/MahalleSecici';
import { useIsler } from './durum';
import { durumKati, katOf, yerelKatYaz, type Kat } from './map/noktalar';
import { IsKimlik } from './IsKimlik';
import { BossDetay } from './BossDetay';
import { IsNotlari } from './IsNotlari';
import { BossAtamaDurumu, BossAskiDurumu, type HalRengi } from './BossYazmaHali';
import { useAskiFormu } from './TopluAski';
import { useAtaFormu } from './TopluAta';
import { Segment } from '../../../cekirdek/ortak/Segment';
import { SimgeDugme } from '../../../cekirdek/ortak/Ilkel';
import { Geri, HaritaIkon } from '../../../cekirdek/ortak/Ikon';
import { Bolum, dilimMetni, kisaAd, ObekSecici, saatMetni, tarihSaatMetni, TeknikSecici, UyariSeridi } from './parcalar';

export interface CekmeceKomutu {
  tur: 'teknik' | 'randevu' | 'randevuTus' | 'obek' | 'ticket' | 'not' | 'gorunum';
  deger?: string;
  n: number;
}

export type Gorunum = 'ana' | 'obek' | 'mahalle' | 'ticket' | 'kapat' | 'merkeze' | 'evdeyok' | 'yenidenac' | 'bossbagla' | 'kaldir';
export type IslemSekmesi = 'ata' | 'aski' | 'not';

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

/** MAP rengi → çip rengi (BOSS durumu çipi haritadaki noktayla aynı renkte). */
const KAT_HAP: Record<Kat, HalRengi> = { gri: 'gri', sari: 'amber', mavi: 'mavi', kirmizi: 'kirmizi', mor: 'mor' };

function olayZamani(z: string): string {
  const d = sunucuZamani(z);
  if (!d) return '';
  const bugun = new Date();
  const ayni = d.toDateString() === bugun.toDateString();
  const iki = (n: number) => String(n).padStart(2, '0');
  return `${ayni ? '' : `${iki(d.getDate())}.${iki(d.getMonth() + 1)} `}${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

/** Ata formunun başlangıcı: atanmış kişi, yoksa öneri, yoksa öbeğin ev teknisyeni; dilim randevudan ya da öneriden. */
export function planBaslangici(a: IsAyrinti, obekler: Obek[] | undefined): { teknikId: number | null; dilim: Dilim | null } {
  const obek = a.obek ? obekler?.find((o) => o.id === a.obek!.id) : undefined;
  const teknikId = a.atanan?.id ?? a.oneri?.teknik.id ?? obek?.sahip?.id ?? null;
  let dilim: Dilim | null = null;
  if (a.randevu && a.randevu.kaynak === 'biz') dilim = { bas: a.randevu.bas, bit: a.randevu.bit, teyitli: a.randevu.teyitli };
  else if (!a.atanan && a.oneri?.bas && a.oneri.bit) dilim = { bas: a.oneri.bas, bit: a.oneri.bit, teyitli: false };
  return { teknikId, dilim };
}

/** İşlem sekmeleri: yalnız işe uygun olanlar (Ata: açık iş + izin; Askıya al: askıya alınabilir ya da askıda). */
export function islemSekmeleri(a: Pick<IsAyrinti, 'durum' | 'izinler'>): IslemSekmesi[] {
  const acik = a.durum !== 'cozuldu' && a.durum !== 'kapandi';
  const l: IslemSekmesi[] = [];
  if (acik && a.izinler.ata) l.push('ata');
  if (acik && (a.durum === 'askida' || a.izinler.durumlar.includes('askida'))) l.push('aski');
  l.push('not');
  return l;
}

/** Açılışta seçili sekme: askıdaki iş → Askı; atanabilir iş → Ata; yoksa Not. */
export function ilkSekme(a: Pick<IsAyrinti, 'durum' | 'izinler'>): IslemSekmesi {
  const l = islemSekmeleri(a);
  if (a.durum === 'askida' && l.includes('aski')) return 'aski';
  return l[0];
}

/**
 * ⋯ menüsü: BOSS'a YAZMAYAN (yalnız uygulamadaki) eylemler. BOSS'a yazanlar (ata, randevu, askı, not) İşlem
 * bölümündedir; burada yer almazlar.
 */
export function uygulamaEylemleri(a: IsAyrinti): Array<{ ad: string; gorunum?: Gorunum; ozel?: 'uyandir' | 'sahaya' | 'ticketYeni' | 'randevuKaldir' | 'ticketAc'; yikici?: boolean }> {
  const d = a.izinler.durumlar;
  const teknikte = a.durum === 'atandi' || a.durum === 'yolda' || a.durum === 'sahada';
  const l: Array<{ ad: string; gorunum?: Gorunum; ozel?: 'uyandir' | 'sahaya' | 'ticketYeni' | 'randevuKaldir' | 'ticketAc'; yikici?: boolean }> = [];
  if (a.durum === 'askida' && d.includes('bekliyor')) l.push({ ad: 'Uyandır (Atanmadı’ya al)', ozel: 'uyandir' });
  if (a.durum === 'merkeze' && d.includes('bekliyor')) l.push({ ad: 'Sahaya al', ozel: 'sahaya' });
  if (d.includes('ulasilamadi')) l.push({ ad: 'Evde yok', gorunum: 'evdeyok' });
  if (d.includes('merkeze')) l.push({ ad: 'Merkeze gönderildi', gorunum: 'merkeze' });
  if (a.izinler.ofisten_kapat) l.push({ ad: 'Ofisten kapat', gorunum: 'kapat' });
  if (d.includes('bekliyor') && teknikte) l.push({ ad: 'Atamayı kaldır', gorunum: 'kaldir', yikici: true });
  if (a.randevu?.kaynak === 'biz' && a.izinler.randevu && !teknikte) l.push({ ad: 'Randevuyu kaldır', ozel: 'randevuKaldir' });
  if (a.izinler.obek) l.push({ ad: 'Öbeğe taşı', gorunum: 'obek' });
  if (a.izinler.ticket && !a.ticket) l.push({ ad: 'Ticket’a bağla', gorunum: 'ticket' });
  if (a.izinler.ticket && !a.ticket) l.push({ ad: 'Yeni ticket aç', ozel: 'ticketYeni' });
  if (a.ticket) l.push({ ad: 'Ticket’ı aç', ozel: 'ticketAc' });
  if (a.izinler.yeniden_ac) l.push({ ad: 'Yeniden aç', gorunum: 'yenidenac' });
  if (a.izinler.boss_bagla) l.push({ ad: 'BOSS Task No’yu bağla', gorunum: 'bossbagla' });
  return l;
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
  const [catisma, setCatisma] = useState<string | null>(null);
  const [gorunum, setGorunum] = useState<Gorunum>('ana');
  const [sekme, setSekme] = useState<IslemSekmesi>('not');
  const [bekliyor, setBekliyor] = useState(false);
  const aRef = useRef<IsAyrinti | null>(null);
  aRef.current = a;
  const govdeRef = useRef<HTMLDivElement>(null);
  const notRef = useRef<HTMLTextAreaElement>(null);
  const [yeniTicket, setYeniTicket] = useState(false);

  const yukle = useCallback(async (no: string, sekmeyiKur = false) => {
    try {
      const y = await isGetir(no);
      setA(y);
      setYukHata(null);
      if (sekmeyiKur) setSekme(ilkSekme(y));
    } catch (e) {
      setYukHata(hataMetni(e));
    }
  }, []);

  /* İş değişince baştan. */
  useEffect(() => {
    setA(null);
    setCatisma(null);
    setGorunum('ana');
    setYukHata(null);
    if (isNo) void yukle(isNo, true);
  }, [isNo, yukle]);

  /* Listedeki satır değişti (canlı yoklama: BOSS durumu, randevu, ekip): çekmece de tazelensin. */
  const satir = isNo ? depo.harita.get(isNo) : undefined;
  const satirImza = satir ? `${satir.surum}|${satir.boss_durum ?? ''}|${satir.boss_randevu_durumu ?? ''}|${satir.boss_ekip ?? ''}` : '';
  const sonImza = useRef('');
  useEffect(() => {
    if (!isNo || !a || !satir || bekliyor) return;
    if (!sonImza.current) {
      sonImza.current = satirImza;
      return;
    }
    if (satirImza === sonImza.current) return;
    sonImza.current = satirImza;
    void yukle(isNo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satirImza]);

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
        const once = aRef.current;
        const y = await fn();
        setA(y);
        // MAP: durum değiştiyse nokta BOSS eşitlemesini beklemeden yeni renkte (noktalar.ts yerelKatYaz)
        if (once && once.is_no === y.is_no && once.durum !== y.durum) yerelKatYaz([once], durumKati(y));
        depo.isYaz(y);
        setCatisma(null);
        setGorunum('ana');
        const olay = y.olaylar[0];
        const yazi = metin(y);
        if (geriAlinir && olay) {
          bildirim.geriAl(yazi, async () => {
            try {
              const g = await geriAl(y.is_no, olay.id);
              depo.isYaz(g);
              if (aRef.current?.is_no === g.is_no) setA(g);
              bildirim.goster('Geri alındı.', 'basari');
              depo.teknikleriTazele();
            } catch (e) {
              bildirim.goster(hataMetni(e), 'uyari');
            }
          });
        } else if (yazi) bildirim.goster(yazi, 'basari');
        depo.teknikleriTazele();
        if (kapanir) kapat();
        return y;
      } catch (e) {
        if (e instanceof IsHatasi && e.kod === 'guncel_degil') {
          if (e.govde.guncel) {
            setA(e.govde.guncel);
            depo.isYaz(e.govde.guncel);
          }
          setCatisma(e.message);
          return null;
        }
        bildirim.goster(hataMetni(e), 'uyari');
        return null;
      } finally {
        setBekliyor(false);
      }
    },
    [bildirim, depo, kapat],
  );

  const durumEylemi = useCallback(
    (g: DurumGirdi, metin: string, kapanir = false) => {
      const x = aRef.current;
      if (!x) return;
      void calistir(() => durumDegistir(x.is_no, { ...g, surum: x.surum }), () => metin, { kapanir });
    },
    [calistir],
  );

  /* Ata / askı (toplu yol) bitti: iş yeniden okunur, liste ve harita tazelenir. */
  const islemBitti = useCallback(
    (metin: string) => {
      const x = aRef.current;
      if (x) void calistir(() => isGetir(x.is_no), () => metin, { geriAlinir: false });
    },
    [calistir],
  );

  /* ------------------------------ klavye komutları (panodan) ------------------------------ */

  const islenenKomut = useRef(0);
  useEffect(() => {
    if (!komut || !a || islenenKomut.current === komut.n) return;
    islenenKomut.current = komut.n;
    const sekmeyeGit = (s: IslemSekmesi, odak?: string) => {
      setGorunum('ana');
      if (islemSekmeleri(a).includes(s)) setSekme(s);
      window.setTimeout(() => {
        govdeRef.current?.querySelector('.ip-islem')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
        if (odak) govdeRef.current?.querySelector<HTMLElement>(odak)?.focus();
      }, 40);
    };
    switch (komut.tur) {
      case 'teknik':
        sekmeyeGit('ata', '.ip-islem .ps-dugme');
        break;
      case 'randevu':
      case 'randevuTus':
        sekmeyeGit('ata');
        break;
      case 'not':
        sekmeyeGit('not', '.ip-not-yaz textarea');
        break;
      case 'obek':
        if (a.izinler.obek) setGorunum('obek');
        break;
      case 'ticket':
        if (a.izinler.ticket) setGorunum('ticket');
        break;
      case 'gorunum':
        if (komut.deger === 'aski') sekmeyeGit('aski');
        else if (komut.deger) setGorunum(komut.deger as Gorunum);
        break;
      default:
        break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [komut, a]);

  if (!isNo) return null;

  /* ⋯ : yalnız uygulamadaki eylemler (BOSS'a yazılmaz) */
  const menu: MenuOgesi[] = [];
  if (a && gorunum === 'ana') {
    const l = uygulamaEylemleri(a);
    if (l.length) menu.push({ etiket: 'Yalnız uygulamada · BOSS’a yazılmaz', calistir: () => undefined, kapali: true });
    for (const o of l) {
      menu.push({
        etiket: o.ad,
        yikici: o.yikici,
        calistir: () => {
          if (o.gorunum) return setGorunum(o.gorunum);
          if (o.ozel === 'uyandir') return durumEylemi({ yeni: 'bekliyor' }, 'Uyandırıldı · Atanmadı listesinde');
          if (o.ozel === 'sahaya') return durumEylemi({ yeni: 'bekliyor' }, 'Sahaya alındı · Atanmadı listesinde');
          if (o.ozel === 'ticketYeni') return setYeniTicket(true);
          if (o.ozel === 'ticketAc' && a.ticket) return git(`/yonetici/ticketlar/${a.ticket.id}`);
          if (o.ozel === 'randevuKaldir')
            return void calistir(() => randevuVer(a.is_no, { bas: null, surum: a.surum }), () => 'Randevu kaldırıldı');
          return undefined;
        },
      });
    }
  }

  return (
    <>
      <Panel
        acik={Boolean(isNo)}
        kapat={kapat}
        baslik={a ? a.task_adi : 'İş'}
        altBaslik={a ? DURUM_ETIKET[a.durum] : undefined}
        perdesiz
        genislik={440}
        basSag={menu.length ? <DahaMenusu ogeler={menu} etiket="Diğer eylemler (yalnız uygulamada)" /> : null}
      >
        <div className="ip-cekmece" ref={govdeRef}>
          <UyariSeridi uyarilar={a?.uyarilar ?? satir?.uyarilar} />
          <IliskiliAkis metin={a?.iliskili_akis ?? satir?.iliskili_akis} nolar={a?.iliskili_isler ?? satir?.iliskili_isler} />
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
              catismaKapat={() => setCatisma(null)}
              sekme={sekme}
              setSekme={setSekme}
              bekliyor={bekliyor}
              gorunumAc={setGorunum}
              islemBitti={islemBitti}
              calistir={calistir}
              notRef={notRef}
              yenile={() => void yukle(a.is_no)}
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
          lokasyon={a.lokasyon}
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

const SEKME_ADI: Record<IslemSekmesi, string> = { ata: 'Ata', aski: 'Askıya al', not: 'Not' };

function AnaGorunum({
  a,
  catisma,
  catismaKapat,
  sekme,
  setSekme,
  bekliyor,
  gorunumAc,
  islemBitti,
  calistir,
  notRef,
  yenile,
}: {
  a: IsAyrinti;
  catisma: string | null;
  catismaKapat: () => void;
  sekme: IslemSekmesi;
  setSekme: (s: IslemSekmesi) => void;
  bekliyor: boolean;
  gorunumAc: (g: Gorunum) => void;
  islemBitti: (metin: string) => void;
  calistir: Calistir;
  notRef: RefObject<HTMLTextAreaElement>;
  yenile: () => void;
}) {
  const acik = a.durum !== 'cozuldu' && a.durum !== 'kapandi';
  const btkTeshis = a.serit === 'BTK' && !a.kotu_gecmis && a.masa_vade && !a.teshis_sonucu && acik;
  const sekmeler = islemSekmeleri(a);
  const etkinSekme = sekmeler.includes(sekme) ? sekme : sekmeler[0];
  const kat = katOf(a);

  const teshisEt = (sonuc: TeshisSonucu, metin: string, ek: { canli_test?: boolean } = {}) => {
    void calistir(() => teshis(a.is_no, { sonuc, surum: a.surum, ...ek }), () => metin);
  };

  return (
    <>
      {catisma ? (
        <div className="ip-uyari sari" role="alert">
          <span>{catisma}</span>
          <button type="button" className="o-dugme kucuk" onClick={catismaKapat}>
            Tamam
          </button>
        </div>
      ) : null}

      {/* 1. Baş: BOSS durumu + kimlik */}
      <section className="ip-c-bas">
        <div className="ip-c-kimlik">
          <Hap renk={KAT_HAP[kat]} baslik="BOSS durumu (haritadaki renk)">
            BOSS: {a.boss.durum || '—'}
          </Hap>
          {a.serit === 'BTK' ? <Rozet tur="btk" /> : null}
          {a.kaynak === 'bayi' ? <Rozet tur="bayi" /> : a.kanal_grubu === 'global' ? <Rozet tur="global" /> : null}
          {a.rozetler.includes('tekrar') ? <Rozet tur="tekrar" /> : null}
          {a.rozetler.includes('yeniden') ? <Rozet tur="yeniden" /> : null}
          <span className="bosluk" />
          {a.boss_url ? (
            <a className="o-dugme kucuk metin" href={a.boss_url} target="_blank" rel="noreferrer">
              BOSS’ta aç
            </a>
          ) : null}
          {a.lat !== null && a.lon !== null ? (
            <a
              className="o-simge-dugme kucuk"
              href={konumBaglantisi(a.lat, a.lon)}
              target="_blank"
              rel="noreferrer"
              aria-label="Haritada aç"
              title="Haritada aç"
            >
              <HaritaIkon boyut={16} />
            </a>
          ) : null}
        </div>
        <IsKimlik s={a} basliksiz sikisik musteriNoKopyalandi={() => void kopyaKaydi(a.is_no).catch(() => undefined)} />
        {a.boss.randevu_bas && a.randevu?.kaynak === 'biz' ? (
          <p className="ip-not-satiri">BOSS randevusu: {dilimMetni(a.boss.randevu_bas, a.boss.randevu_bit)}</p>
        ) : null}
        {a.durum === 'askida' ? (
          <p className="ip-not-satiri">
            Askıda: {a.askida_neden || a.boss.aski_nedeni || '—'}
            {a.uyanma ? ` · uyanma ${dilimMetni(a.uyanma, null)}` : ''}
          </p>
        ) : null}
      </section>

      {/* 2. İşlem: Ata · Askıya al · Not (toplu eylemlerle aynı parçalar) */}
      <section className="ip-bolum ip-islem" aria-label="İşlem">
        <header>
          <h3>İşlem</h3>
        </header>
        {sekmeler.length > 1 ? (
          <Segment<IslemSekmesi>
            etiket="İşlem"
            tam
            kucuk
            deger={etkinSekme}
            degisti={setSekme}
            secenekler={sekmeler.map((s) => ({ deger: s, etiket: s === 'aski' && a.durum === 'askida' ? 'Askı' : SEKME_ADI[s] }))}
          />
        ) : null}
        <div className="ip-islem-govde">
          {etkinSekme === 'ata' ? <TekAta key={a.is_no} a={a} bitti={islemBitti} gorunumAc={gorunumAc} /> : null}
          {etkinSekme === 'aski' ? <TekAski key={a.is_no} a={a} bitti={islemBitti} /> : null}
          {etkinSekme === 'not' ? <IsNotlari a={a} notRef={notRef} yenile={yenile} /> : null}
        </div>
      </section>

      {/* 3. BOSS ayrıntısı (canlı sekmeler) */}
      <Bolum baslik="BOSS ayrıntısı">
        <BossDetay isNo={a.is_no} yedekTel={a.musteri_tel ?? null} />
      </Bolum>

      {/* Yer */}
      {a.mahalle || a.ilce || a.bina || a.triyaj_metni || a.lat !== null ? (
        <Bolum baslik="Yer">
          <dl className="ip-bilgi">
            <dt>Mahalle</dt>
            <dd>
              {a.mahalle || '—'}
              {a.ilce ? ` · ${a.ilce}` : ''}
              {a.mahalle_kaynak ? <span className="ip-kaynak"> · {MAHALLE_KAYNAGI[a.mahalle_kaynak] ?? 'Adresten'}</span> : null}
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
            {a.lat !== null && a.lon !== null ? (
              <>
                <dt>Konum</dt>
                <dd>
                  <a className="o-bag" href={konumBaglantisi(a.lat, a.lon)} target="_blank" rel="noreferrer">
                    Haritada aç
                  </a>
                </dd>
              </>
            ) : null}
          </dl>
          {a.triyaj_metni ? <p className="ip-uyari amber">{a.triyaj_metni}</p> : null}
        </Bolum>
      ) : null}

      {/* Ticket (bağlıysa ya da binada açık ticket varsa) */}
      {a.ticket || a.binada_acik_ticket > 0 ? (
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
          ) : (
            <div className="ip-uyari sari">
              <span>
                Bu binada açık {a.binada_acik_ticket === 1 ? 'bir' : a.binada_acik_ticket} ticket var. Teknisyen gönderilmez.
              </span>
              {a.izinler.ticket ? (
                <button type="button" className="o-dugme kucuk" onClick={() => gorunumAc('ticket')}>
                  Ticket’a bağla
                </button>
              ) : null}
            </div>
          )}
        </Bolum>
      ) : null}

      {/* BTK teşhisi (masa araması) */}
      {btkTeshis ? (
        <Bolum baslik={`Masa araması · vade ${saatMetni(a.masa_vade)}`}>
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
      {a.bayi_oneri && a.izinler.boss_bagla ? (
        <div className="ip-uyari mavi">
          <span>BOSS’ta {a.bayi_oneri.boss_task_no} olarak açılmış olabilir.</span>
          <button
            type="button"
            className="o-dugme kucuk"
            disabled={bekliyor}
            onClick={() => void calistir(() => bossBagla(a.is_no, a.bayi_oneri!.boss_task_no, a.surum), () => 'BOSS Task No’ya bağlandı')}
          >
            Bağla
          </button>
        </div>
      ) : null}

      {/* 4. Geçmiş */}
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

      {/* İç BTK notu (BOSS'u etkilemez): askı zaman çizelgesi, net BTK saati, şikâyet sayacı */}
      {a.aski.length || a.aski_uyari || a.btk_sikayet || (a.serit === 'BTK' && a.aski_durdu_dk > 0) ? (
        <details className="ip-acilir ip-ic-not">
          <summary>İç BTK notu</summary>
          {a.aski_uyari ? (
            <p className="ip-uyari amber" title="Yalnız BTK süre hesabı içindir; BOSS askısını engellemez.">
              {a.aski_uyari}
            </p>
          ) : null}
          {a.aski.length ? (
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
          ) : null}
          {a.serit === 'BTK' && a.aski_durdu_dk > 0 ? (
            <p className="ip-not-satiri">
              BTK saati toplam {sureMetni(a.aski_durdu_dk)} durdu
              {a.btk_net_gecen_dk !== null ? ` · net geçen ${sureMetni(a.btk_net_gecen_dk)}` : ''}.
            </p>
          ) : null}
          {a.btk_sikayet ? (
            <p className="ip-not-satiri">
              BTK şikâyeti: {a.btk_sikayet.gecen_is_gunu}/{a.btk_sikayet.sure_is_gunu} iş günü
              {a.btk_sikayet.reopen ? ' · reopen' : ''} · son gün {dilimMetni(a.btk_sikayet.son_gun, null)}
              {a.btk_sikayet.alarm ? ` · alarm: ${a.btk_sikayet.alarm}` : ''}
              {a.btk_sikayet.btk_kapali ? ' · BTK’da kapalı, FOX’ta açık' : ''}
            </p>
          ) : null}
          <p className="ip-kaynak">
            SL {a.boss.sl ? `${a.boss.sl}${a.boss.sl_saat ? ` (${a.boss.sl_saat} s)` : ''}` : '—'} · açılış {tarihSaatMetni(a.acilis)} ·
            sisteme geliş {tarihSaatMetni(a.gorulme_zamani)}
          </p>
        </details>
      ) : null}
    </>
  );
}

/* ================================================================== İşlem ▸ Ata (toplu ata ile aynı yol) */

function TekAta({ a, bitti, gorunumAc }: { a: IsAyrinti; bitti: (metin: string) => void; gorunumAc: (g: Gorunum) => void }) {
  const depo = useIsler();
  const satirlar = useMemo(() => [a], [a]);
  const baslangic = useMemo(() => planBaslangici(a, depo.obekler?.obekler), [a.is_no]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = useAtaFormu({
    acik: true,
    satirlar,
    tek: true,
    baslangic,
    bitti: () => bitti(''),
  });
  const engel = f.asama === 'bitti' ? f.hatalar.find((h) => h.kod === 'altyapi_engeli') : undefined;
  const yeniden = async () => {
    try {
      await bossAtamaYeniden([a.is_no]);
      bitti('Atama yeniden BOSS’a gönderiliyor');
    } catch (e) {
      bitti(hataMetni(e));
    }
  };
  return (
    <div className="ip-tek-ata">
      {a.atanan ? (
        <p className="ip-not-satiri">
          Şu an: {a.atanan.ad}
          {a.randevu ? ` · ${dilimMetni(a.randevu.bas, a.randevu.bit)}` : ''}
        </p>
      ) : a.oneri ? (
        <p className="ip-not-satiri">Öneri: {a.oneri.teknik.ad} · {a.oneri.neden}</p>
      ) : null}
      {f.govde}
      {engel ? (
        <div className="ip-uyari sari" role="alert">
          <span>{engel.neden}</span>
          <div className="ip-satir-eylemler">
            <button type="button" className="o-dugme kucuk" onClick={() => gorunumAc('ticket')}>
              Ticket’a bağla
            </button>
            <button
              type="button"
              className="o-dugme kucuk metin"
              onClick={() => {
                f.yenidenSec();
                void f.uygula({ yineDe: true });
              }}
            >
              Yine de ata
            </button>
          </div>
        </div>
      ) : null}
      {f.asama === 'sec' ? <BossAtamaDurumu a={a} yeniden={() => void yeniden()} /> : null}
      <div className="ip-satir-eylemler ip-islem-alt">
        {f.asama === 'bitti' ? (
          <button type="button" className="o-dugme kucuk" onClick={f.yenidenSec}>
            Değiştir
          </button>
        ) : (
          <button
            type="button"
            className="o-dugme birincil"
            disabled={!f.hazir || f.asama === 'gidiyor'}
            onClick={() => void f.uygula()}
          >
            {f.asama === 'gidiyor' ? 'Atanıyor…' : a.atanan ? 'Kaydet ve BOSS’a yaz' : 'Ata ve BOSS’a yaz'}
          </button>
        )}
      </div>
    </div>
  );
}

/* ================================================================== İşlem ▸ Askıya al (toplu askı ile aynı yol) */

function TekAski({ a, bitti }: { a: IsAyrinti; bitti: (metin: string) => void }) {
  const satirlar = useMemo(() => [a], [a]);
  const f = useAskiFormu({ acik: true, satirlar, tek: true });
  const askida = a.durum === 'askida';
  const gonder = () =>
    void f.uygula().then((r) => {
      if (r?.length) bitti(askida ? 'Askı güncellendi · BOSS’a gidiyor' : 'Askıya alındı · BOSS’a gidiyor');
    });
  return (
    <div className="ip-tek-aski">
      <BossAskiDurumu a={a} yeniden={f.hazir ? gonder : undefined} />
      {f.govde}
      <div className="ip-satir-eylemler ip-islem-alt">
        <button type="button" className="o-dugme birincil" disabled={!f.hazir || f.asama === 'gidiyor'} onClick={gonder}>
          {f.asama === 'gidiyor' ? 'Askıya alınıyor…' : askida ? 'Askıyı güncelle ve BOSS’a yaz' : 'Askıya al ve BOSS’a yaz'}
        </button>
      </div>
    </div>
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
            <KopyalaNo deger={g.boss_task_no} />
          </dd>
        </>
      ) : null}
      {parca.includes('ekip') && g.alanlar.ekip ? (
        <>
          <dt>Ekip</dt>
          <dd>
            <KopyalaNo deger={g.alanlar.ekip} />
          </dd>
        </>
      ) : null}
      {(parca.includes('randevu') || parca.includes('ekip')) && g.alanlar.randevu_baslangic ? (
        <>
          <dt>Randevu başlangıç</dt>
          <dd>
            <KopyalaNo deger={tarihSaatMetni(g.alanlar.randevu_baslangic)} />
          </dd>
          <dt>Randevu bitiş</dt>
          <dd>
            <KopyalaNo deger={tarihSaatMetni(g.alanlar.randevu_bitis)} />
          </dd>
        </>
      ) : null}
      {parca.includes('aski') ? (
        <>
          <dt>Askı nedeni</dt>
          <dd>
            <KopyalaNo deger={g.alanlar.aski_nedeni} />
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

/* ================================================================== alt görünümler */

function AltGorunum({
  a,
  gorunum,
  geri,
  calistir,
  durumEylemi,
  bekliyor,
  yeniTicketAc,
}: {
  a: IsAyrinti;
  gorunum: Gorunum;
  geri: () => void;
  calistir: Calistir;
  durumEylemi: (g: DurumGirdi, metin: string, kapanir?: boolean) => void;
  bekliyor: boolean;
  yeniTicketAc: () => void;
}) {
  const depo = useIsler();
  const [neden, setNeden] = useState('');
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
    kapat: 'Ofisten kapat',
    merkeze: 'Merkeze gönderildi',
    evdeyok: 'Evde yok',
    yenidenac: 'Yeniden aç',
    bossbagla: 'BOSS Task No’yu bağla',
    kaldir: 'Atamayı kaldır',
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
          {a.izinler.ticket ? (
            <button type="button" className="o-dugme kucuk metin" onClick={yeniTicketAc}>
              Yeni ticket aç…
            </button>
          ) : null}
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
    case 'kaldir':
      icerik = (
        <div className="o-alan">
          <span className="etiket">
            Neden kaldırıyorsunuz? İş {a.atanan ? `${a.atanan.ad} üzerinden alınır ve ` : ''}Atanmadı’ya döner; randevu silinir.
          </span>
          <input className="o-girdi" value={neden} maxLength={200} autoFocus onChange={(o) => setNeden(o.target.value)} />
        </div>
      );
      birincil = {
        etiket: 'Atamayı kaldır',
        yikici: true,
        kapali: !neden.trim(),
        tikla: () => durumEylemi({ yeni: 'bekliyor', neden: neden.trim() }, 'Atama kaldırıldı'),
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
        tikla: () => durumEylemi({ yeni: 'ulasilamadi' }, 'Evde yok · TASKS’ta Ulaşılamadı olarak görünür'),
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
        <SimgeDugme etiket="Geri" onClick={geri}>
          <Geri boyut={16} />
        </SimgeDugme>
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

/** İlişkili akış satırı: aynı müşterinin diğer açık işleri; numaraya basınca o iş açılır (süzgeç korunur). */
function IliskiliAkis({ metin, nolar }: { metin: string | null | undefined; nolar: string[] | undefined }) {
  if (!metin) return null;
  const ac = (no: string) => {
    const yol = window.location.hash.replace(/^#/, '');
    git(/\/is\/[^/?]+/.test(yol) ? yol.replace(/\/is\/[^/?]+/, `/is/${encodeURIComponent(no)}`) : `/yonetici/isler/is/${encodeURIComponent(no)}`);
  };
  return (
    <div className="ip-uyari mavi ip-iliskili">
      <span>
        <b>İlişkili akış:</b> {metin}
      </span>
      {(nolar ?? []).slice(0, 6).map((no) => (
        <button key={no} type="button" className="o-dugme kucuk metin" onClick={() => ac(no)} title="İlişkili işi aç">
          {no}
        </button>
      ))}
    </div>
  );
}
