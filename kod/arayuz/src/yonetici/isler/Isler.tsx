/**
 * İşler — operasyon panosu (OPERASYON_V2_SPEC §6.1, EK-6, EK-9, EK-10).
 *
 * Masaüstü ≥ 1200 px, üç bölme; sayfa hiç yeniden akmaz:
 *   öbekler (280) · liste (esnek) · iş çekmecesi (440, listenin üstüne biner).
 * 768–1199: öbek seçici listenin üstünde; çekmece Panel'in kırılımıyla.
 * Telefon < 768: itmeli gezinme (öbekler → işler → iş), iç içe kaydırma yok.
 *
 * Adres: #/yonetici/isler[/obek/<id>|/kontrol|/giden|/boss-ekip|/konum|/obeksiz/<ilçe>|/tumu][/is/<no>]
 * Dışarıdan süzgeçle açmak için (Takip): #/yonetici/isler/suz/<geciken|asan24|btk|btk48|atanmamis|kontrol>
 *
 * Klavye (yalnız masaüstü; "?" yardım): ↓/↑ (J/K) · Enter · O · Shift+O · A · R (1–6, Y) · B · T · N · / · Esc
 */

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react';
import type { IsSatir, Kova, Obek } from '../../is/tipler';
import { KOVA_ETIKET } from '../../is/tipler';
import { hataMetni, islerExcel, islerGetir } from '../../is/api';
import { git, useAdres } from '../../yol/rota';
import { useOturum } from '../../depo/oturum';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { Hikaye } from '../../ortak/Hikaye';
import { Manset, type MansetOgesi } from '../../ortak/Manset';
import { Segment } from '../../ortak/Segment';
import { SuzDugmesi } from '../../ortak/Suz';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { IlkIpucu } from '../../ortak/IlkIpucu';
import { Panel } from '../../ortak/Panel';
import { Kbd } from '../../ortak/Kbd';
import { Hap } from '../../ortak/Rozet';
import { useBildirim } from '../../ortak/Bildirim';
import { useOnay } from '../../ortak/Onay';
import { useKutlamaGecisi } from '../../ortak/Kutlama';
import { Tablo, type TabloSutunu } from '../../ortak/Tablo';
import { sureMetni } from '../../ortak/sure';
import { yerelOku, yerelYaz } from '../../ortak/yerel';
import { IsHaritasi, type IsNoktasi, type Renk } from '../is_emri/IsHaritasi';
import { ObekCekmecesi } from '../obekler/ObekCekmecesi';
import { hikayeUret, IslerSaglayici, useIsler } from './depo';
import { IsSatiri, kalanDk, type SatirEylemi } from './IsSatiri';
import { IsCekmecesi, type CekmeceKomutu } from './IsCekmecesi';
import { onerililer, TopluAtaKarti, useTopluOnay } from './TopluAtaKarti';
import { KontrolListesi } from './Kontrol';
import { BossEkipEsleme, BossGidenListesi } from './BossKutusu';
import { useRaporYukleyici } from './RaporYukle';
import { YeniIsPaneli } from './YeniIs';
import { DagitPaneli } from './Dagit';
import { BOS_SUZGEC, suz, suzgecSayisi, SuzgecCekmecesi, SuzgecCipleri, type Suzgec, type Yalniz } from './suzgec';
import { useGenislik, klavyeCihazi } from './genislik';
import { bulunma } from './dil';
import { dilimMetni, kisaAd, ObekNoktasi, saatMetni, yerMetni } from './parcalar';
import { DURUM_ETIKET } from '../../is/tipler';
import './isler.css';

/* ================================================================== adres */

type SecimTuru = 'yok' | 'tumu' | 'obek' | 'kontrol' | 'boss-ekip' | 'giden' | 'konum' | 'obeksiz';
interface Secim {
  tur: SecimTuru;
  deger?: string;
}

const OZEL: SecimTuru[] = ['tumu', 'kontrol', 'boss-ekip', 'giden', 'konum'];

function adresOku(adres: string): { secim: Secim; isNo: string | null; suz: string | null } {
  let p = adres.split('?')[0].split('/').filter(Boolean).slice(2);
  let isNo: string | null = null;
  const i = p.indexOf('is');
  if (i >= 0) {
    isNo = p[i + 1] ? decodeURIComponent(p[i + 1]) : null;
    p = p.slice(0, i);
  }
  if (!p.length) return { secim: { tur: 'yok' }, isNo, suz: null };
  if (p[0] === 'suz') return { secim: { tur: 'tumu' }, isNo, suz: p[1] ?? null };
  if (p[0] === 'obek' && p[1]) return { secim: { tur: 'obek', deger: p[1] }, isNo, suz: null };
  if (p[0] === 'obeksiz' && p[1]) return { secim: { tur: 'obeksiz', deger: decodeURIComponent(p[1]) }, isNo, suz: null };
  if ((OZEL as string[]).includes(p[0])) return { secim: { tur: p[0] as SecimTuru }, isNo, suz: null };
  return { secim: { tur: 'yok' }, isNo, suz: null };
}

function secimYolu(s: Secim): string {
  if (s.tur === 'yok') return '/yonetici/isler';
  if (s.tur === 'obek' || s.tur === 'obeksiz') return `/yonetici/isler/${s.tur}/${encodeURIComponent(s.deger ?? '')}`;
  return `/yonetici/isler/${s.tur}`;
}

function isYolu(s: Secim, isNo: string | null): string {
  const kok = secimYolu(s);
  return isNo ? `${kok}${kok.endsWith('/isler') ? '' : ''}/is/${encodeURIComponent(isNo)}` : kok;
}

/* ================================================================== dış ekran */

export function Isler() {
  return (
    <IslerSaglayici>
      <IslerPanosu />
    </IslerSaglayici>
  );
}

type GorunumKipi = 'liste' | 'tablo' | 'harita';
const GORUNUM_ANAHTARI = 'saha.isler.gorunum';

function obekRenkleri(): Renk[] {
  const varsayilan: Renk[] = [
    [11, 99, 229], [11, 122, 63], [148, 80, 10], [180, 35, 24], [96, 51, 201], [14, 116, 144], [157, 23, 77], [77, 124, 15],
  ];
  try {
    const st = getComputedStyle(document.documentElement);
    return varsayilan.map((v, i) => {
      const h = st.getPropertyValue(`--obek-${i + 1}`).trim();
      const m = /^#([0-9a-f]{6})$/i.exec(h);
      return m ? ([parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)] as Renk) : v;
    });
  } catch {
    return varsayilan;
  }
}

function IslerPanosu() {
  const depo = useIsler();
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const genislik = useGenislik();
  const telefon = genislik === 'telefon';
  const adres = useAdres();
  const { secim: adresSecimi, isNo, suz: adresSuz } = useMemo(() => adresOku(adres), [adres]);
  const secim: Secim = adresSecimi.tur === 'yok' && !telefon ? { tur: 'tumu' } : adresSecimi;

  const [kova, setKova] = useState<Kova>('atanmadi');
  const [arama, setArama] = useState('');
  const [suzgec, setSuzgec] = useState<Suzgec>(BOS_SUZGEC);
  const [suzAcik, setSuzAcik] = useState(false);
  const [gorunum, setGorunumHam] = useState<GorunumKipi>(() => {
    const g = yerelOku(GORUNUM_ANAHTARI);
    return g === 'tablo' || g === 'harita' ? g : 'liste';
  });
  const [imlec, setImlec] = useState<string | null>(null);
  const [komut, setKomut] = useState<CekmeceKomutu | null>(null);
  const [yeniIs, setYeniIs] = useState(false);
  const [dagit, setDagit] = useState(false);
  const [obekCekmece, setObekCekmece] = useState<number | null>(null);
  const [bitenler, setBitenler] = useState<IsSatir[] | null>(null);
  const [yardim, setYardim] = useState(false);
  const [surukle, setSurukle] = useState(false);
  const [haritaSecimi, setHaritaSecimi] = useState<string[] | null>(null);
  const aramaRef = useRef<HTMLInputElement>(null);
  const komutNo = useRef(0);
  const rBekliyor = useRef(0);
  const rapor = useRaporYukleyici();
  const topluOnay = useTopluOnay();
  const [onayPenceresi, sor] = useOnay();
  const kbd = useMemo(() => klavyeCihazi(), []);

  const setGorunum = (g: GorunumKipi) => {
    setGorunumHam(g);
    yerelYaz(GORUNUM_ANAHTARI, g);
  };

  /* Takip'ten gelen süzgeç (#/yonetici/isler/suz/<ad>) */
  useEffect(() => {
    if (!adresSuz) return;
    if (adresSuz === 'atanmamis') {
      setKova('atanmadi');
      setSuzgec(BOS_SUZGEC);
    } else if (adresSuz === 'kontrol') {
      git('/yonetici/isler/kontrol', { degistir: true });
      return;
    } else if (['geciken', 'asan24', 'btk', 'btk48', 'ticketli', 'tekrar', 'bugun_randevu', 'boss_islenecek'].includes(adresSuz)) {
      setSuzgec({ ...BOS_SUZGEC, yalniz: [adresSuz as Yalniz] });
      setKova('atanmadi');
    }
    git('/yonetici/isler/tumu', { degistir: true });
  }, [adresSuz]);

  /* Biten kovası istenince son 7 gün */
  useEffect(() => {
    if (kova !== 'biten' || bitenler) return;
    islerGetir('biten', 7)
      .then((y) => setBitenler(y.isler))
      .catch((e) => bildirim.goster(hataMetni(e), 'uyari'));
  }, [kova, bitenler, bildirim]);

  const obekler = depo.obekler?.obekler ?? [];
  const seciliObek: Obek | null = secim.tur === 'obek' ? obekler.find((o) => String(o.id) === secim.deger) ?? null : null;
  const simdi = useMemo(() => new Date(Date.now() + depo.sunucuFarkMs), [depo.meta?.sunucu_zamani, depo.sunucuFarkMs]); // eslint-disable-line react-hooks/exhaustive-deps

  /* Seçimin işleri (kovasız, süzgeçsiz) */
  const secimSuz = useCallback(
    (liste: IsSatir[]) => {
      switch (secim.tur) {
        case 'obek':
          return liste.filter((x) => String(x.obek?.id) === secim.deger);
        case 'kontrol':
          return liste.filter((x) => x.durum === 'triyaj');
        case 'konum':
          return liste.filter((x) => x.konum_yaklasik);
        case 'obeksiz':
          return liste.filter((x) => !x.obek && (x.ilce ?? 'İlçe bilinmiyor') === secim.deger);
        case 'giden':
          return liste.filter((x) => x.rozetler.includes('boss_islenecek'));
        default:
          return liste;
      }
    },
    [secim.tur, secim.deger],
  );

  const secimIsleri = useMemo(() => secimSuz(depo.isler), [secimSuz, depo.isler]);
  const suzulen = useMemo(() => suz(secimIsleri, suzgec, arama, simdi), [secimIsleri, suzgec, arama, simdi]);
  const suzulenBiten = useMemo(
    () => (bitenler ? suz(secimSuz(bitenler), suzgec, arama, simdi) : null),
    [bitenler, secimSuz, suzgec, arama, simdi],
  );
  const kovaSayisi = useMemo(() => {
    const s: Record<Kova, number> = { atanmadi: 0, teknikte: 0, beklemede: 0, biten: 0 };
    suzulen.forEach((x) => (s[x.kova] += 1));
    s.biten = suzulenBiten?.length ?? 0;
    return s;
  }, [suzulen, suzulenBiten]);
  const listeHam = kova === 'biten' ? suzulenBiten ?? [] : suzulen.filter((x) => x.kova === kova);
  const liste = haritaSecimi ? listeHam.filter((x) => haritaSecimi.includes(x.is_no)) : listeHam;

  /* Öbek sütununun sayıları listeyle aynı kaynaktan (sayfa yenilenmeden güncel). */
  const obekSayilari = useMemo(() => {
    const m = new Map<number, { acik: number; geciken: number; btk: number; atanmamis: number }>();
    for (const x of depo.isler) {
      if (!x.obek) continue;
      const d = m.get(x.obek.id) ?? { acik: 0, geciken: 0, btk: 0, atanmamis: 0 };
      d.acik += 1;
      if (x.gecikti) d.geciken += 1;
      if (x.serit === 'BTK') d.btk += 1;
      if (x.kova === 'atanmadi') d.atanmamis += 1;
      m.set(x.obek.id, d);
    }
    return m;
  }, [depo.isler]);
  const obeksizIlceler = useMemo(() => {
    const m = new Map<string, number>();
    depo.isler.forEach((x) => {
      if (!x.obek) {
        const a = x.ilce ?? 'İlçe bilinmiyor';
        m.set(a, (m.get(a) ?? 0) + 1);
      }
    });
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [depo.isler]);
  const konumSayisi = useMemo(() => depo.isler.filter((x) => x.konum_yaklasik).length, [depo.isler]);
  const kontrolSayisi = useMemo(() => depo.isler.filter((x) => x.durum === 'triyaj').length, [depo.isler]);

  const sayac = depo.meta?.sayac;
  const atanmamisToplam = useMemo(() => depo.isler.filter((x) => x.kova === 'atanmadi').length, [depo.isler]);
  useKutlamaGecisi(depo.durum === 'hazir' && depo.isler.length ? atanmamisToplam === 0 : null, 'Atanmamış iş kalmadı');

  /* Klasörden yeni rapor geldi (EK-10): bildir ve listeyi baştan oku. */
  const sonAktarimId = useRef<number | null>(null);
  useEffect(() => {
    const s = depo.meta?.son_aktarim;
    if (!s) return;
    if (sonAktarimId.current !== null && s.id !== sonAktarimId.current) {
      void depo.tazele();
      if (s.yontem === 'klasor') {
        bildirim.goster(
          `Yeni rapor alındı · ${saatMetni(s.zaman)} · ${s.fark?.yeni ?? 0} yeni iş, ${s.fark?.kaybolan ?? 0} kapandı`,
          'bilgi',
          { sureMs: 8000 },
        );
      }
    }
    sonAktarimId.current = s.id;
  }, [depo.meta?.son_aktarim, depo, bildirim]);

  /* ------------------------------ gezinme ------------------------------ */

  const ac = useCallback(
    (no: string, gorunumKomutu?: string) => {
      setImlec(no);
      git(isYolu(secim, no));
      if (gorunumKomutu) {
        komutNo.current += 1;
        const tur = gorunumKomutu === 'teknik' ? 'teknik' : 'gorunum';
        setKomut({ tur, deger: gorunumKomutu, n: komutNo.current });
      }
    },
    [secim],
  );
  const kapat = useCallback(() => git(secimYolu(adresSecimi.tur === 'yok' ? adresSecimi : secim)), [adresSecimi, secim]);
  const secimeGit = (s: Secim) => {
    setHaritaSecimi(null);
    if (s.tur === 'kontrol') setKova('atanmadi');
    git(secimYolu(s));
  };
  const komutVer = (tur: CekmeceKomutu['tur'], deger?: string) => {
    komutNo.current += 1;
    setKomut({ tur, deger, n: komutNo.current });
  };

  const satirEylemi = useCallback(
    (s: IsSatir, e: SatirEylemi) => {
      if (e === 'onayla') void topluOnay.onayla([s]);
      else if (e === 'obege_ata') ac(s.is_no, 'obek');
      else ac(s.is_no, 'teknik');
    },
    [ac, topluOnay],
  );

  /* ------------------------------ klavye ------------------------------ */

  const listeRef = useRef(liste);
  listeRef.current = liste;
  useEffect(() => {
    if (telefon) return;
    const tus = (o: KeyboardEvent) => {
      if (o.defaultPrevented || o.ctrlKey || o.metaKey || o.altKey) return;
      const hedef = o.target as HTMLElement | null;
      if (hedef?.closest('input, textarea, select, [contenteditable="true"]')) {
        if (o.key === 'Escape' && hedef.closest('.ip-arama')) (hedef as HTMLInputElement).blur();
        return;
      }
      if (document.querySelector('.o-onay')) return;
      const paneller = [...document.querySelectorAll('.o-panel')];
      if (paneller.some((p) => !p.querySelector('.ip-cekmece'))) return;
      const l = listeRef.current;
      const simdiki = isNo ?? imlec;
      const i = simdiki ? l.findIndex((x) => x.is_no === simdiki) : -1;
      const secili = i >= 0 ? l[i] : null;
      const tasi = (yeni: number) => {
        const x = l[Math.max(0, Math.min(l.length - 1, yeni))];
        if (!x) return;
        setImlec(x.is_no);
        if (isNo) git(isYolu(secim, x.is_no), { degistir: true });
        window.requestAnimationFrame(() =>
          document.querySelector(`[data-is="${CSS.escape(x.is_no)}"]`)?.scrollIntoView({ block: 'nearest' }),
        );
      };
      const k = o.key;
      if (Date.now() - rBekliyor.current < 1600 && /^[1-9yYdD]$/.test(k)) {
        rBekliyor.current = 0;
        o.preventDefault();
        komutVer('randevuTus', k.toLowerCase());
        return;
      }
      switch (k) {
        case 'ArrowDown':
        case 'j':
        case 'J':
          o.preventDefault();
          tasi(i + 1);
          break;
        case 'ArrowUp':
        case 'k':
        case 'K':
          o.preventDefault();
          tasi(i - 1);
          break;
        case 'Enter':
          if (secili) {
            o.preventDefault();
            ac(secili.is_no);
          }
          break;
        case 'o':
          if (secili?.oneri && secili.kova === 'atanmadi') {
            o.preventDefault();
            void topluOnay.onayla([secili]);
          }
          break;
        case 'O': {
          o.preventDefault();
          const kapsam = onerililer(secimIsleri);
          if (!kapsam.length) {
            bildirim.goster('Onaylanacak öneri yok.', 'bilgi');
            break;
          }
          const kisi = new Set(kapsam.map((x) => x.oneri?.teknik.id)).size;
          void sor({
            baslik: 'Önerileri onayla',
            metin: `${kapsam.length} iş, ${kisi} teknisyene önerilen saatlerle atanır. 10 saniye içinde geri alabilirsiniz.`,
            onay: `${kapsam.length} işi ata`,
          }).then((evet) => evet && void topluOnay.onayla(kapsam));
          break;
        }
        case 'a':
        case 'A':
          if (secili) {
            o.preventDefault();
            if (!isNo) ac(secili.is_no);
            komutVer('teknik');
          }
          break;
        case 'r':
        case 'R':
          if (secili) {
            o.preventDefault();
            if (!isNo) ac(secili.is_no);
            komutVer('randevu');
            rBekliyor.current = Date.now();
          }
          break;
        case 'b':
        case 'B':
          if (secili) {
            o.preventDefault();
            if (!isNo) ac(secili.is_no);
            komutVer('obek');
          }
          break;
        case 't':
        case 'T':
          if (secili) {
            o.preventDefault();
            if (!isNo) ac(secili.is_no);
            komutVer('ticket');
          }
          break;
        case 'n':
        case 'N':
          if (secili) {
            o.preventDefault();
            if (!isNo) ac(secili.is_no);
            komutVer('not');
          }
          break;
        case '/':
          o.preventDefault();
          aramaRef.current?.focus();
          break;
        case '?':
          o.preventDefault();
          setYardim(true);
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [telefon, isNo, imlec, secim, ac, topluOnay, secimIsleri, sor, bildirim]);

  /* ------------------------------ sürükle-bırak (sayfanın her yerine) ------------------------------ */

  const surukleUzerinde = (o: DragEvent) => {
    if (!izinli('is.yukle') || ![...o.dataTransfer.types].includes('Files')) return;
    o.preventDefault();
    setSurukle(true);
  };
  const birak = (o: DragEvent) => {
    if (!izinli('is.yukle')) return;
    o.preventDefault();
    setSurukle(false);
    const f = o.dataTransfer.files?.[0];
    if (f) rapor.yukle(f);
  };

  /* ------------------------------ başlık şeridi ------------------------------ */

  const hikaye = hikayeUret(depo.meta, depo.isler);
  const son = depo.meta?.son_aktarim;
  const mansetOgeleri: MansetOgesi[] = sayac
    ? [
        {
          etiket: 'Açık',
          deger: sayac.acik.toLocaleString('tr-TR'),
          onClick: () => {
            setSuzgec(BOS_SUZGEC);
            setArama('');
            secimeGit({ tur: telefon ? 'tumu' : 'yok' });
          },
        },
        {
          etiket: '24 saati aşan',
          deger: sayac.asan24.toLocaleString('tr-TR'),
          renk: sayac.asan24 ? 'kirmizi' : undefined,
          onClick: () => {
            setSuzgec({ ...BOS_SUZGEC, yalniz: ['asan24'] });
            secimeGit({ tur: 'tumu' });
          },
        },
        {
          etiket: 'Atanmamış',
          deger: sayac.atanmamis.toLocaleString('tr-TR'),
          ek: sayac.en_eski_atanmamis_dk !== null && sayac.atanmamis ? `en eskisi ${sureMetni(sayac.en_eski_atanmamis_dk)}` : undefined,
          renk: (sayac.en_eski_atanmamis_dk ?? 0) >= 15 && sayac.atanmamis ? 'kirmizi' : (sayac.en_eski_atanmamis_dk ?? 0) >= 10 && sayac.atanmamis ? 'amber' : undefined,
          onClick: () => {
            setSuzgec(BOS_SUZGEC);
            setKova('atanmadi');
            secimeGit({ tur: 'tumu' });
          },
        },
        {
          etiket: '48 saati aşan BTK',
          deger: sayac.btk48.toLocaleString('tr-TR'),
          renk: sayac.btk48 ? 'kirmizi' : undefined,
          onClick: () => {
            setSuzgec({ ...BOS_SUZGEC, yalniz: ['btk48'] });
            secimeGit({ tur: 'tumu' });
          },
        },
      ]
    : [];

  const raporHapi = son ? (
    <span className={`ip-rapor-hap ${son.renk}`} title={`${son.dosya_adi} · ${son.is_sayisi} iş`}>
      Son rapor {saatMetni(son.zaman)} · {son.yas_dk < 1 ? 'az önce' : `${sureMetni(son.yas_dk)} önce`}
      {son.renk !== 'yesil' ? ' · BOSS’tan yeni raporu indirip bırakın' : ''}
    </span>
  ) : null;

  const ustEylemler = (
    <>
      {izinli('is.yukle') ? (
        <button type="button" className="o-dugme" onClick={rapor.sec} disabled={rapor.okunuyor}>
          {rapor.okunuyor ? 'Rapor okunuyor…' : 'Rapor yükle'}
        </button>
      ) : null}
      {izinli('is.olustur') ? (
        <button type="button" className="o-dugme" onClick={() => setYeniIs(true)}>
          + Yeni iş
        </button>
      ) : null}
    </>
  );

  /* ------------------------------ gövde ------------------------------ */

  const ilkYukleme = depo.durum === 'yukleniyor' && !depo.isler.length;
  const hicIsYok = depo.durum === 'hazir' && !depo.isler.length && !(sayac?.acik ?? 0);

  const onayBekleyen = depo.meta?.onay_bekleyen ?? [];
  const bantlar = (
    <>
      {onayBekleyen.map((r) => (
        <div key={r.aktarim_id} className="ip-uyari sari ip-bant" role="status">
          <span>
            {r.yontem === 'klasor' ? 'Klasörden gelen rapor onay bekliyor' : 'Onay bekleyen rapor'} · {r.dosya_adi} · {saatMetni(r.zaman)}
            {r.mesaj ? ` — ${r.mesaj}` : ''}
          </span>
          <button type="button" className="o-dugme kucuk" onClick={() => rapor.onayla(r)}>
            Gözden geçir
          </button>
        </div>
      ))}
    </>
  );

  if (ilkYukleme) {
    return (
      <>
        <YonUst baslik="İşler">{ustEylemler}</YonUst>
        <Icerik>
          <Iskelet satir={8} yukseklik={72} />
        </Icerik>
        {rapor.arayuz}
      </>
    );
  }

  if (depo.durum === 'hata' && !depo.isler.length) {
    return (
      <>
        <YonUst baslik="İşler">{ustEylemler}</YonUst>
        <Icerik>
          <HataKutusu mesaj={depo.hata ?? 'İşler alınamadı.'} tekrar={() => void depo.tazele()} />
        </Icerik>
        {rapor.arayuz}
      </>
    );
  }

  if (hicIsYok) {
    return (
      <div onDragOver={surukleUzerinde} onDragLeave={() => setSurukle(false)} onDrop={birak} className="ip-kok">
        <YonUst baslik="İşler">{izinli('is.olustur') ? ustEylemler : null}</YonUst>
        <Icerik>
          {bantlar}
          <BosDurum
            simge="📄"
            baslik="Henüz iş yok."
            aciklama={
              <>
                {!son ? 'Yeni sürüm iş emirlerini kalıcı saklıyor. ' : ''}BOSS’tan <b>Teknik Task Detay Raporu</b>’nu indirip buraya
                bırakın. Sistem kurulum işlerini ayıklar, her işi öbeğine koyar.
              </>
            }
          >
            {izinli('is.yukle') ? (
              <button type="button" className="o-dugme birincil" onClick={rapor.sec} disabled={rapor.okunuyor}>
                {rapor.okunuyor ? 'Rapor okunuyor…' : 'Rapor seç'}
              </button>
            ) : null}
          </BosDurum>
        </Icerik>
        {surukle ? <div className="ip-birak">Raporu bırakın</div> : null}
        {rapor.arayuz}
        <YeniIsPaneli acik={yeniIs} kapat={() => setYeniIs(false)} acildi={(no) => ac(no)} />
      </div>
    );
  }

  const cekmeceAcik = Boolean(isNo);

  /* Öbek sütunu (geniş) ve telefonun ilk seviyesi aynı satırları kullanır. */
  const obekSirasi = [...obekler].sort((a, b) => {
    const sa = obekSayilari.get(a.id);
    const sb = obekSayilari.get(b.id);
    const aa = sa?.atanmamis ? 1 : 0;
    const ab = sb?.atanmamis ? 1 : 0;
    if (aa !== ab) return ab - aa;
    const g = (sb?.geciken ?? 0) - (sa?.geciken ?? 0);
    if (g) return g;
    return (sb?.acik ?? 0) - (sa?.acik ?? 0) || a.ad.localeCompare(b.ad, 'tr');
  });

  const obekSutunu = (
    <nav className="ip-obekler" aria-label="Öbekler">
      <div className="ip-obek-bas">
        <span>Öbekler</span>
        <button type="button" className="o-bag" onClick={() => git('/yonetici/obekler')}>
          Düzenle
        </button>
      </div>
      <ObekSatiri
        etkin={secim.tur === 'tumu'}
        ad="Tümü"
        sag={<span className="sayi">{depo.isler.length.toLocaleString('tr-TR')}</span>}
        tikla={() => secimeGit({ tur: 'tumu' })}
      />
      {kontrolSayisi ? (
        <ObekSatiri
          etkin={secim.tur === 'kontrol'}
          ad={<><span aria-hidden="true">⚠</span> Kontrol gerekli</>}
          sag={<span className="sayi uyari">{kontrolSayisi}</span>}
          tikla={() => secimeGit({ tur: 'kontrol' })}
          sinif="ozel uyari"
        />
      ) : (
        <div className="ip-obek-yesil">
          <Hap renk="yesil">✓ Bütün işler öbeğinde</Hap>
        </div>
      )}
      {sayac?.eslesmemis_ekip ? (
        <ObekSatiri
          etkin={secim.tur === 'boss-ekip'}
          ad={<><span aria-hidden="true">ⓘ</span> Eşleşmemiş BOSS ekibi</>}
          sag={<span className="sayi">{sayac.eslesmemis_ekip}</span>}
          tikla={() => secimeGit({ tur: 'boss-ekip' })}
          sinif="ozel"
        />
      ) : null}
      {sayac?.boss_bekleyen ? (
        <ObekSatiri
          etkin={secim.tur === 'giden'}
          ad={<><span aria-hidden="true">ⓘ</span> BOSS’a işlenecek</>}
          sag={<span className="sayi">{sayac.boss_bekleyen}</span>}
          tikla={() => secimeGit({ tur: 'giden' })}
          sinif="ozel"
        />
      ) : null}
      <div className="ip-obek-ayrac" role="separator" />
      {obekSirasi.map((o) => {
        const s = obekSayilari.get(o.id);
        return (
          <ObekSatiri
            key={o.id}
            etkin={secim.tur === 'obek' && secim.deger === String(o.id)}
            soluk={!s?.acik}
            ad={
              <>
                <ObekNoktasi renk={o.renk} /> <span className="ad-metin">{o.ad}</span>
              </>
            }
            sag={
              s?.acik ? (
                <span className="sayilar" title={`${s.acik} açık · ${s.geciken} geciken · ${s.btk} BTK · ${s.atanmamis} atanmamış`}>
                  <span className="sayi">{s.acik}</span>
                  <span className="sayi ikincil">·{s.geciken}</span>
                  <span className="sayi ikincil">·{s.btk}</span>
                  {s.atanmamis ? <span className="mavi-nokta" aria-label={`${s.atanmamis} atanmamış`} /> : <span className="bos-nokta" />}
                </span>
              ) : (
                <span className="sayi ikincil">0</span>
              )
            }
            tikla={() => secimeGit({ tur: 'obek', deger: String(o.id) })}
          />
        );
      })}
      {obeksizIlceler.map(([ilce, n]) => (
        <ObekSatiri
          key={ilce}
          etkin={secim.tur === 'obeksiz' && secim.deger === ilce}
          ad={<span className="ad-metin ikincil">Öbeksiz · {ilce}</span>}
          sag={<span className="sayi">{n}</span>}
          tikla={() => secimeGit({ tur: 'obeksiz', deger: ilce })}
        />
      ))}
      {konumSayisi ? (
        <ObekSatiri
          etkin={secim.tur === 'konum'}
          ad={<span className="ad-metin ikincil">ⓘ Konum yaklaşık</span>}
          sag={<span className="sayi">{konumSayisi}</span>}
          tikla={() => secimeGit({ tur: 'konum' })}
          sinif="ozel"
        />
      ) : null}
    </nav>
  );

  /* Orta/telefon: öbek seçici açılır listesi */
  const obekSeciciAcilir = (
    <label className="ip-obek-acilir">
      <span>Öbek:</span>
      <select
        className="o-girdi"
        value={secim.tur === 'obek' ? `obek:${secim.deger}` : secim.tur === 'obeksiz' ? `obeksiz:${secim.deger}` : secim.tur}
        onChange={(o) => {
          const [t, d] = o.target.value.split(':');
          secimeGit({ tur: t as SecimTuru, deger: d });
        }}
      >
        <option value="tumu">Tümü ({depo.isler.length})</option>
        {kontrolSayisi ? <option value="kontrol">⚠ Kontrol gerekli ({kontrolSayisi})</option> : null}
        {sayac?.eslesmemis_ekip ? <option value="boss-ekip">Eşleşmemiş BOSS ekibi ({sayac.eslesmemis_ekip})</option> : null}
        {sayac?.boss_bekleyen ? <option value="giden">BOSS’a işlenecek ({sayac.boss_bekleyen})</option> : null}
        {obekSirasi.map((o) => (
          <option key={o.id} value={`obek:${o.id}`}>
            {o.ad} ({obekSayilari.get(o.id)?.acik ?? 0})
          </option>
        ))}
        {obeksizIlceler.map(([ilce, n]) => (
          <option key={ilce} value={`obeksiz:${ilce}`}>
            Öbeksiz · {ilce} ({n})
          </option>
        ))}
        {konumSayisi ? <option value="konum">Konum yaklaşık ({konumSayisi})</option> : null}
      </select>
    </label>
  );

  /* Seçimin başlık kartı */
  const secimBasligi = (): ReactNode => {
    if (secim.tur === 'obek' && seciliObek) {
      const s = obekSayilari.get(seciliObek.id);
      return (
        <div className="ip-obek-kart">
          <div className="bas">
            <h2>
              <ObekNoktasi renk={seciliObek.renk} /> {seciliObek.ad}
            </h2>
            <span className="ozet">
              {s?.acik ?? 0} açık · {s?.geciken ?? 0} geciken · {s?.btk ?? 0} BTK
            </span>
          </div>
          <div className="alt">
            <span>
              Teknisyen: {seciliObek.sahip ? <b>{kisaAd(seciliObek.sahip.ad)}</b> : <span className="ip-sessiz">yok</span>}
              {seciliObek.yedek ? <span className="ip-kaynak"> · yedek {kisaAd(seciliObek.yedek.ad)}</span> : null}
            </span>
            <span className="eylemler">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setObekCekmece(seciliObek.id)}>
                Düzenle
              </button>
              {izinli('is.ata') && (s?.atanmamis ?? 0) > 1 ? (
                <button type="button" className="o-dugme kucuk metin" onClick={() => setDagit(true)}>
                  Ekiplere dağıt
                </button>
              ) : null}
            </span>
          </div>
        </div>
      );
    }
    if (secim.tur === 'obek' && !seciliObek) return <p className="ip-sessiz">Öbekler yükleniyor…</p>;
    if (secim.tur === 'kontrol')
      return (
        <div className="ip-bolge-basi">
          <h2>Kontrol gerekli</h2>
          <p>Öbeği ya da mahallesi bulunamayan işler. Nedenine göre tek dokunuşla düzeltin; seçiminiz sonraki raporlarda korunur.</p>
        </div>
      );
    if (secim.tur === 'giden')
      return (
        <div className="ip-bolge-basi">
          <h2>BOSS’a işlenecek</h2>
        </div>
      );
    if (secim.tur === 'boss-ekip')
      return (
        <div className="ip-bolge-basi">
          <h2>Eşleşmemiş BOSS ekibi</h2>
        </div>
      );
    if (secim.tur === 'konum')
      return (
        <div className="ip-bolge-basi">
          <h2>Konum yaklaşık</h2>
          <p>Bu işlerin yeri bina değil, mahalle ya da ilçe merkezi. Bu bir alarm değil; haritada halka olarak görünürler.</p>
        </div>
      );
    if (secim.tur === 'obeksiz')
      return (
        <div className="ip-bolge-basi">
          <h2>Öbeksiz · {secim.deger}</h2>
          <p>
            Bu işlerin mahallesi hiçbir öbekte değil.{' '}
            <button type="button" className="o-bag" onClick={() => git('/yonetici/obekler')}>
              Öbekler’den mahalleyi bir öbeğe ekleyin ›
            </button>
          </p>
        </div>
      );
    return null;
  };

  const ozelGorunum = secim.tur === 'giden' ? <BossGidenListesi ac={ac} /> : secim.tur === 'boss-ekip' ? <BossEkipEsleme /> : null;

  const araclar = (
    <div className="ip-araclar">
      <Segment<Kova>
        etiket="Kova"
        deger={kova}
        degisti={(k) => {
          setKova(k);
          setHaritaSecimi(null);
        }}
        secenekler={(['atanmadi', 'teknikte', 'beklemede', 'biten'] as Kova[]).map((k) => ({
          deger: k,
          etiket: KOVA_ETIKET[k],
          sayi: k === 'biten' && !bitenler ? undefined : kovaSayisi[k],
        }))}
      />
      <div className="ip-arama o-arama">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" strokeLinecap="round" />
        </svg>
        <input
          ref={aramaRef}
          type="search"
          value={arama}
          placeholder="Task No, müşteri, mahalle…"
          aria-label="İşlerde ara"
          onChange={(o) => setArama(o.target.value)}
        />
        {kbd && !telefon ? <Kbd>/</Kbd> : null}
      </div>
      <SuzDugmesi etkinSayi={suzgecSayisi(suzgec)} onClick={() => setSuzAcik(true)} />
      <span className="bosluk" />
      <Segment<GorunumKipi>
        etiket="Görünüm"
        kucuk
        deger={gorunum}
        degisti={setGorunum}
        secenekler={[
          { deger: 'liste', etiket: 'Liste' },
          ...(telefon ? [] : [{ deger: 'tablo' as GorunumKipi, etiket: 'Tablo' }]),
          { deger: 'harita', etiket: 'Harita' },
        ]}
      />
      {izinli('is.excel') && !telefon ? (
        <button
          type="button"
          className="o-dugme kucuk metin"
          title="Müşteri sütunlarıyla Excel (indirme kayda geçer)"
          onClick={() =>
            void islerExcel(kova === 'biten' ? 'biten' : 'acik', seciliObek?.id).catch((e) => bildirim.goster(hataMetni(e), 'uyari'))
          }
        >
          Excel
        </button>
      ) : null}
    </div>
  );

  const liste_ =
    gorunum === 'harita' ? (
      <IsHaritasiSarmal isler={listeHam} ac={ac} secildi={(nolar) => {
        setHaritaSecimi(nolar);
        setGorunum('liste');
      }} />
    ) : gorunum === 'tablo' && !telefon ? (
      <IsTablosu isler={liste} ac={ac} secili={isNo} />
    ) : (
      <IsListesi
        isler={liste}
        secili={isNo}
        imlec={imlec}
        ac={ac}
        eylem={satirEylemi}
        kbd={kbd && !telefon}
        bekliyor={topluOnay.bekliyor}
        bos={
          kova === 'biten' && !bitenler ? (
            <Iskelet satir={4} yukseklik={72} />
          ) : secim.tur === 'obek' && seciliObek && !secimIsleri.length ? (
            <BosDurum baslik={`Bugün ${bulunma(seciliObek.ad)} iş yok.`} aciklama="Yeni rapor gelince burada görünür." kucuk />
          ) : arama || suzgecSayisi(suzgec) ? (
            <BosDurum baslik="Bu süzgeçle iş yok." aciklama="Aramayı ya da süzgeçleri kaldırın." kucuk>
              <button
                type="button"
                className="o-dugme"
                onClick={() => {
                  setArama('');
                  setSuzgec(BOS_SUZGEC);
                }}
              >
                Süzgeçleri kaldır
              </button>
            </BosDurum>
          ) : (
            <BosDurum baslik={`${KOVA_ETIKET[kova]} iş yok.`} kucuk />
          )
        }
      />
    );

  const topluKart =
    izinli('is.ata') && (secim.tur === 'obek' || secim.tur === 'tumu') && kova === 'atanmadi' ? (
      <TopluAtaKarti
        isler={secimIsleri}
        obek={seciliObek}
        birincil={!cekmeceAcik}
        teknisyenSec={() => seciliObek && setObekCekmece(seciliObek.id)}
      />
    ) : null;

  const listeBolmesi = (
    <section className="ip-liste-bolme" aria-label="İşler">
      {secimBasligi()}
      {ozelGorunum ?? (
        <>
          {topluKart}
          {secim.tur === 'kontrol' ? (
            <KontrolListesi isler={suz(secimIsleri, suzgec, arama, simdi)} ac={ac} />
          ) : (
            <>
              {araclar}
              <SuzgecCipleri s={suzgec} degisti={setSuzgec} teknikAdi={(id) => kisaAd(depo.teknikler.find((t) => t.id === id)?.ad)} />
              {haritaSecimi ? (
                <div className="ip-suz-cipleri">
                  <span className="o-suz-cip">
                    <span>Haritadan seçilen {haritaSecimi.length} iş</span>
                    <button type="button" onClick={() => setHaritaSecimi(null)} aria-label="Seçimi kaldır">
                      ✕
                    </button>
                  </span>
                </div>
              ) : null}
              {liste_}
            </>
          )}
        </>
      )}
    </section>
  );

  /* ------------------------------ telefon: itmeli gezinme ------------------------------ */

  if (telefon) {
    const ilkSeviye = adresSecimi.tur === 'yok';
    const baslik =
      secim.tur === 'obek'
        ? seciliObek?.ad ?? 'Öbek'
        : secim.tur === 'tumu'
          ? 'Tüm işler'
          : secim.tur === 'kontrol'
            ? 'Kontrol gerekli'
            : secim.tur === 'giden'
              ? 'BOSS’a işlenecek'
              : secim.tur === 'boss-ekip'
                ? 'BOSS ekibi'
                : secim.tur === 'konum'
                  ? 'Konum yaklaşık'
                  : `Öbeksiz · ${secim.deger ?? ''}`;
    return (
      <div className="ip-kok telefon">
        <YonUst baslik="İşler" altYazi={ilkSeviye ? undefined : null}>
          {ustEylemler}
        </YonUst>
        {ilkSeviye ? (
          <Icerik>
            {bantlar}
            <Hikaye cumle={hikaye.cumle} ton={hikaye.ton} />
            <div className="ip-tel-ozet">
              <button type="button" onClick={() => secimeGit({ tur: 'tumu' })}>
                <b>{(sayac?.atanmamis ?? 0).toLocaleString('tr-TR')} atanmayı bekliyor</b>
                {sayac?.en_eski_atanmamis_dk ? <span> · en eskisi {sureMetni(sayac.en_eski_atanmamis_dk)}</span> : null}
              </button>
              {sayac?.asan24 ? (
                <button
                  type="button"
                  onClick={() => {
                    setSuzgec({ ...BOS_SUZGEC, yalniz: ['asan24'] });
                    secimeGit({ tur: 'tumu' });
                  }}
                >
                  {sayac.asan24.toLocaleString('tr-TR')} iş 24 saati aştı
                </button>
              ) : null}
              {raporHapi ? <div className="rapor">{raporHapi}</div> : null}
            </div>
            <IlkIpucu anahtar="isler" adimlar={['Öbek seçin', 'İşe dokunun', 'Ata’ya basın']} />
            {obekSutunu}
          </Icerik>
        ) : (
          <div className="ip-tel-seviye">
            <div className="ip-tel-bas">
              <button type="button" className="o-dugme kucuk metin" onClick={() => git('/yonetici/isler')}>
                ‹ İşler
              </button>
              <h2>{baslik}</h2>
            </div>
            <Icerik>
              {listeBolmesi}
            </Icerik>
          </div>
        )}
        <IsCekmecesi isNo={isNo} kapat={kapat} komut={komut} />
        {ortakPaneller()}
      </div>
    );
  }

  function ortakPaneller() {
    return (
      <>
        <SuzgecCekmecesi acik={suzAcik} kapat={() => setSuzAcik(false)} s={suzgec} degisti={setSuzgec} isler={secimIsleri} />
        <YeniIsPaneli acik={yeniIs} kapat={() => setYeniIs(false)} acildi={(no) => ac(no)} />
        <DagitPaneli acik={dagit} kapat={() => setDagit(false)} obek={seciliObek} isler={secimIsleri} />
        <ObekCekmecesi obekId={obekCekmece} kapat={() => setObekCekmece(null)} />
        <KlavyeYardimi acik={yardim} kapat={() => setYardim(false)} />
        {rapor.arayuz}
        {onayPenceresi}
      </>
    );
  }

  /* ------------------------------ masaüstü / orta ------------------------------ */

  return (
    <div
      className={`ip-kok ${genislik}`}
      onDragOver={surukleUzerinde}
      onDragLeave={(o) => {
        if (o.currentTarget === o.target) setSurukle(false);
      }}
      onDrop={birak}
    >
      <YonUst baslik="İşler">{ustEylemler}</YonUst>
      <div className="ip-ust-serit">
        <Hikaye cumle={hikaye.cumle} ton={hikaye.ton} />
        <div className="ip-manset-satir">
          <Manset ogeler={mansetOgeleri} etiket="Özet" />
          {raporHapi}
        </div>
        {bantlar}
        <IlkIpucu anahtar="isler" adimlar={['Öbek seçin', 'İşe dokunun', 'Ata’ya basın']} />
      </div>
      <div className={`ip-pano${cekmeceAcik ? ' cekmeceli' : ''}`}>
        {genislik === 'genis' ? obekSutunu : null}
        <div className="ip-orta">
          {genislik !== 'genis' ? obekSeciciAcilir : null}
          {listeBolmesi}
        </div>
      </div>
      <IsCekmecesi isNo={isNo} kapat={kapat} komut={komut} />
      {surukle ? <div className="ip-birak">Raporu bırakın</div> : null}
      {ortakPaneller()}
    </div>
  );
}

/* ================================================================== parçalar */

function ObekSatiri({
  etkin,
  ad,
  sag,
  tikla,
  soluk = false,
  sinif = '',
}: {
  etkin: boolean;
  ad: ReactNode;
  sag?: ReactNode;
  tikla: () => void;
  soluk?: boolean;
  sinif?: string;
}) {
  return (
    <button
      type="button"
      className={`ip-obek-satir${etkin ? ' etkin' : ''}${soluk ? ' soluk' : ''}${sinif ? ` ${sinif}` : ''}`}
      aria-current={etkin ? 'true' : undefined}
      onClick={tikla}
    >
      <span className="ad">{ad}</span>
      {sag}
      <span className="ok" aria-hidden="true">
        ›
      </span>
    </button>
  );
}

function IsListesi({
  isler,
  secili,
  imlec,
  ac,
  eylem,
  kbd,
  bekliyor,
  bos,
}: {
  isler: IsSatir[];
  secili: string | null;
  imlec: string | null;
  ac: (no: string) => void;
  eylem: (s: IsSatir, e: SatirEylemi) => void;
  kbd: boolean;
  bekliyor: boolean;
  bos: ReactNode;
}) {
  if (!isler.length) return <>{bos}</>;
  return (
    <div className="ip-liste" role="list" aria-label="İş listesi">
      {isler.map((s) => (
        <IsSatiri
          key={s.is_no}
          s={s}
          secili={s.is_no === secili}
          imlecte={s.is_no === imlec && s.is_no !== secili}
          ac={ac}
          eylem={eylem}
          eylemKapali={bekliyor}
          kbd={kbd}
        />
      ))}
    </div>
  );
}

/** EK-9: Excel alışkanlığı — aynı işler tablo olarak (sırala, süz, Ctrl+C, Excel'e indir). */
function IsTablosu({ isler, ac, secili }: { isler: IsSatir[]; ac: (no: string) => void; secili: string | null }) {
  const sutunlar: Array<TabloSutunu<IsSatir>> = useMemo(
    () => [
      { anahtar: 'kalan', baslik: 'Kalan (dk)', deger: (s) => kalanDk(s), sayi: true, genislik: 96, suzgec: false },
      { anahtar: 'task_no', baslik: 'Task No', deger: (s) => s.boss_task_no ?? s.is_no, genislik: 118 },
      { anahtar: 'task', baslik: 'Task adı', deger: (s) => s.task_adi, genislik: 200, kartta: 'baslik' },
      { anahtar: 'serit', baslik: 'Şerit', deger: (s) => s.serit, genislik: 80 },
      { anahtar: 'durum', baslik: 'Durum', deger: (s) => DURUM_ETIKET[s.durum], genislik: 130, kartta: 'alt' },
      { anahtar: 'obek', baslik: 'Öbek', deger: (s) => s.obek?.ad ?? '', genislik: 130 },
      { anahtar: 'ilce', baslik: 'İlçe', deger: (s) => s.ilce ?? '', genislik: 110 },
      { anahtar: 'mahalle', baslik: 'Mahalle', deger: (s) => s.mahalle ?? '', genislik: 140 },
      { anahtar: 'musteri', baslik: 'Müşteri', deger: (s) => s.musteri_adi ?? '', genislik: 160 },
      { anahtar: 'musteri_no', baslik: 'Müşteri No', deger: (s) => s.musteri_no ?? '', genislik: 120 },
      { anahtar: 'yer', baslik: 'Yer', deger: (s) => yerMetni(s), genislik: 200 },
      { anahtar: 'randevu', baslik: 'Randevu', deger: (s) => (s.randevu ? dilimMetni(s.randevu.bas, s.randevu.bit) : ''), genislik: 130 },
      { anahtar: 'teknik', baslik: 'Teknisyen', deger: (s) => s.atanan?.ad ?? '', genislik: 140 },
      { anahtar: 'oneri', baslik: 'Öneri', deger: (s) => s.oneri?.teknik.ad ?? '', genislik: 140 },
      { anahtar: 'bekleme', baslik: 'Geleli (dk)', deger: (s) => s.bekleme_dk, sayi: true, genislik: 96, suzgec: false },
      { anahtar: 'boss_ekip', baslik: 'BOSS ekibi', deger: (s) => s.boss_ekip ?? '', genislik: 160 },
      { anahtar: 'acilis', baslik: 'Açılış', deger: (s) => s.acilis.slice(0, 16), genislik: 140, suzgec: false },
    ],
    [],
  );
  return (
    <Tablo
      satirlar={isler}
      sutunlar={sutunlar}
      anahtar={(s) => s.is_no}
      onAc={(s) => ac(s.is_no)}
      seciliAnahtar={secili}
      excelAdi="Isler"
      kayitAnahtari="isler"
      aramaYerTutucu="Tabloda ara…"
      yukseklik="calc(100dvh - var(--ip-ust, 260px) - 120px)"
    />
  );
}

function IsHaritasiSarmal({ isler, ac, secildi }: { isler: IsSatir[]; ac: (no: string) => void; secildi: (nolar: string[]) => void }) {
  const renkler = useMemo(() => obekRenkleri(), []);
  const { noktalar, nolar } = useMemo(() => {
    const n: IsNoktasi[] = [];
    const k: string[] = [];
    isler.forEach((s) => {
      if (s.lat === null || s.lon === null) return;
      k.push(s.is_no);
      n.push({
        id: k.length - 1,
        lat: s.lat,
        lon: s.lon,
        renk: s.obek ? renkler[((s.obek.renk % 8) + 8) % 8] : [93, 103, 120],
        kaba: s.konum_yaklasik,
        baslik: s.task_adi,
        alt: `${yerMetni(s)} · ${DURUM_ETIKET[s.durum]}`,
      });
    });
    return { noktalar: n, nolar: k };
  }, [isler, renkler]);
  const konumsuz = isler.length - noktalar.length;
  return (
    <div className="ip-harita">
      <IsHaritasi
        noktalar={noktalar}
        sigdirmaAnahtari={`${noktalar.length}`}
        yukseklik="calc(100dvh - var(--ip-ust, 260px) - 110px)"
        yerTiklandi={(ids) => {
          const secilen = ids.map((i) => nolar[i]).filter(Boolean);
          if (secilen.length === 1) ac(secilen[0]);
          else if (secilen.length > 1) secildi(secilen);
        }}
      />
      <p className="ip-not-satiri">
        Halka: konum yaklaşık (mahalle/ilçe merkezi). Bir noktaya dokunun: tek işse çekmece açılır, birden çoksa liste o işlere süzülür.
        {konumsuz ? ` ${konumsuz} işin konumu yok.` : ''}
      </p>
    </div>
  );
}

function KlavyeYardimi({ acik, kapat }: { acik: boolean; kapat: () => void }) {
  const satirlar: Array<[string, string]> = [
    ['↓ / ↑ (J / K)', 'Sonraki / önceki iş'],
    ['Enter', 'İş çekmecesini aç'],
    ['O', 'Seçili işin önerisini onayla'],
    ['Shift+O', 'Öbeğin bütün önerilerini onayla'],
    ['A', 'Ata: teknisyen seçicisine git'],
    ['R', 'Randevu; ardından 1–6 bugünün dilimleri, Y yarın'],
    ['B', 'Öbeğe taşı'],
    ['T', 'Ticket bağla / aç'],
    ['N', 'Not'],
    ['/', 'Ara'],
    ['Esc', 'Çekmeceyi kapat'],
    ['?', 'Bu yardım'],
  ];
  return (
    <Panel acik={acik} kapat={kapat} baslik="Klavye kısayolları" altBaslik="Fare kullanmadan hızlı çalışmak için.">
      <dl className="ip-klavye">
        {satirlar.map(([t, a]) => (
          <div key={t}>
            <dt>
              {t.split(' / ').map((p, i) => (
                <span key={p}>
                  {i ? ' / ' : ''}
                  <Kbd>{p.replace(/[()]/g, '').trim()}</Kbd>
                </span>
              ))}
            </dt>
            <dd>{a}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
