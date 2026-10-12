/**
 * TASKS (menüde "TASKS") — BOSS'taki bütün açık işler, Turkcell.exe içinde Excel gibi TEK tablo (operasyon).
 * Araç çubuğu: Ara (Ctrl+F) · Özel filtreler (kayıtlı Görünümler) · Sütunlar · Dolgu rengi · Filtreleri temizle ·
 * Excel'de aç. Tablo (Tablo.tsx) hücre seçer; satır başındaki "i" ya da Enter/Space İş çekmecesini açar.
 * Altta Excel durum çubuğu. Veri: durum.tsx (`ek`: BOSS listesinin bütün alanları, GET /api/isler?ek=1).
 * Adres sözleşmesi cekirdek/yol/tasks.ts'te: #/yonetici/isler[/kontrol|/giden|/boss-ekip|/suz/<kod>][/is/<no>];
 * `suz/<kod>` Pano/Öbek/arama paletinden gelen hazır süzgeçtir (panoSuzgeci.ts), çip olarak görünür.
 * Kontrol ve BOSS ekip eşleme bölümlerine üst çubuktaki sayaç düğmeleri götürür; BOSS'a işlenecek listesine
 * yalnız Pano'dan gidilir.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { IsaretRengi, IsSatir } from '../../../cekirdek/is/tipler';
import { bizimDurumYaz, bossDetayOncelik, hataMetni, hucreRenkYaz } from '../../../cekirdek/is/api';
import { hucreBoya } from './sutunlar';
import { git, useAdres } from '../../../cekirdek/yol/rota';
import { TASKS_SUZ, tasksAdresiOku, tasksBolumYolu, tasksKokYolu } from '../../../cekirdek/yol/tasks';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import { Icerik, YonUst } from '../../../cekirdek/konsol/Kabuk';
import { HataKutusu, Iskelet } from '../../../cekirdek/ortak/Bos';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { AramaKutusu, Dugme } from '../../../cekirdek/ortak/Ilkel';
import { Geri, Kapat } from '../../../cekirdek/ortak/Ikon';
import { IslerSaglayici, useIsler } from './durum';
import { IsCekmecesi } from './IsCekmecesi';
import { metinUyar, turEtiketi, turUyar, useOrtakSuzgec } from './isTuru';
import { TARIH_TUMU, tarihEtiketi, tarihEtkin, tarihUyari, useTarihSuzgeci } from './map/tarihSuzgeci';
import { gunAnahtari } from './parcalar';
import { DuzenMenusu } from './DuzenMenusu';
import { etkinYaz } from './tercihDeposu';
import { KontrolListesi } from './Kontrol';
import { BossEkipEsleme, BossGidenListesi } from './BossKutusu';
import { GorunumPaneli, OzelFiltreler, useGorunumler } from './Gorunumler';
import { IsTablosu } from './Tablo';
import { useSutunlar, type Sutun } from './sutunlar';
import { useSutunDuzeni } from './sutunDuzeni';
import { cipIpucu, cipKisalt, cipMetni, useTabloSuzgec } from './tabloSuzgec';
import { useSecim } from './secim';
import { SutunSecici } from './SutunSecici';
import { DolguRengiDugmesi } from './DolguRengi';
import { DurumCubugu } from './DurumCubugu';
import { FarkSeridi } from './FarkSeridi';
import { excelAc } from './excelAc';
import { TopluAskiPaneli } from './TopluAski';
import { TopluAtaPaneli } from './TopluAta';
import { IliskiliHizalaPaneli, useIliskiliUyumsuz } from './IliskiliHizala';
import { panoSuzgeci } from './panoSuzgeci';
import './isler.css';
import './tablo.css';

/* ================================================================== yardımcılar */

const KAPALI = new Set(['cozuldu', 'kapandi']);

/** En çok `es` istek aynı anda (yüzlerce satır boyanınca sunucu boğulmasın). */
async function sirayla<T>(liste: T[], f: (x: T) => Promise<void>, es = 6): Promise<void> {
  let i = 0;
  await Promise.all(
    Array.from({ length: Math.min(es, liste.length) }, async () => {
      while (i < liste.length) await f(liste[i++]);
    }),
  );
}

/** BOSS tazelemesiyle yeni gelen işler: birkaç saniye vurgulu. */
function useYeniGelenler(isler: IsSatir[]): Set<string> {
  const gorulen = useRef<Set<string> | null>(null);
  const [yeniler, setYeniler] = useState<Set<string>>(() => new Set());
  useEffect(() => {
    if (!isler.length) return undefined;
    if (!gorulen.current) {
      gorulen.current = new Set(isler.map((x) => x.is_no));
      return undefined;
    }
    const y = isler.filter((x) => !gorulen.current!.has(x.is_no)).map((x) => x.is_no);
    if (!y.length) return undefined;
    y.forEach((n) => gorulen.current!.add(n));
    setYeniler((o) => new Set([...o, ...y]));
    const z = window.setTimeout(() => setYeniler((o) => new Set([...o].filter((n) => !y.includes(n)))), 6000);
    return () => window.clearTimeout(z);
  }, [isler]);
  return yeniler;
}

/**
 * BOSS eşitlemesiyle (değişim imleci ilerleyince) değeri değişen görünür hücreler: birkaç saniye sarı yanar.
 * Kullanıcının kendi yazdığı (imleç ilerlemeden gelen) değişiklik yanmaz. Yalnız nesnesi değişen satırlar
 * karşılaştırılır (birlestir değişmeyen satırın nesnesini korur) → ucuz.
 */
function useDegisenHucreler(isler: IsSatir[], imlec: number | undefined, sutunlar: Sutun[]): Map<string, Set<string>> {
  const once = useRef<Map<string, IsSatir> | null>(null);
  const sonImlec = useRef(imlec);
  const sutunRef = useRef(sutunlar);
  sutunRef.current = sutunlar;
  const zaman = useRef(0);
  const [yanan, setYanan] = useState<Map<string, Set<string>>>(() => new Map());
  useEffect(() => {
    const eski = once.current;
    once.current = new Map(isler.map((x) => [x.is_no, x]));
    const sunucudan = imlec !== sonImlec.current;
    sonImlec.current = imlec;
    if (!eski || !sunucudan) return;
    const y = new Map<string, Set<string>>();
    for (const s of isler) {
      const o = eski.get(s.is_no);
      if (!o || o === s) continue;
      const k = new Set<string>();
      for (const c of sutunRef.current) if (c.deger(o) !== c.deger(s)) k.add(c.id);
      if (k.size) y.set(s.is_no, k);
    }
    if (!y.size) return;
    setYanan(y);
    window.clearTimeout(zaman.current);
    zaman.current = window.setTimeout(() => setYanan(new Map()), 3600);
  }, [isler, imlec]);
  useEffect(() => () => window.clearTimeout(zaman.current), []);
  return yanan;
}

const izgaraOdakla = () => document.querySelector<HTMLElement>('.xg-kap')?.focus({ preventScroll: true });

/* ================================================================== ekran */

export function Isler() {
  return (
    <IslerSaglayici ek>
      <IslerPanosu />
    </IslerSaglayici>
  );
}

function IslerPanosu() {
  const depo = useIsler();
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const adres = useAdres();
  const { bolum, suz, isNo } = useMemo(() => tasksAdresiOku(adres), [adres]);
  const ortak = useOrtakSuzgec();
  const gorunum = useGorunumler();
  const [gorunumPaneli, setGorunumPaneli] = useState(false);
  const [excelGidiyor, setExcelGidiyor] = useState(false);
  const [bildiri, setBildiri] = useState<string | null>(null);
  const aramaRef = useRef<HTMLDivElement>(null);
  const duzenleyebilir = izinli('is.duzenle');
  const [tarih, setTarih] = useTarihSuzgeci();
  const tarihUyar = useMemo(() => tarihUyari(tarih), [tarih]);
  /* Izgara yakınlaştırması (Excel gibi, %50–200) ve A B C satırı: düzenin parçası (kişi başına sunucuda). */
  const yakinlikYaz = useCallback(
    (y: number) => etkinYaz((d) => ({ ...d, yakinlik: Math.max(50, Math.min(200, Math.round(y))) })),
    [],
  );

  const hazirSuzgec = useMemo(() => panoSuzgeci(suz, depo.isler), [suz, depo.isler]);
  const liste = useMemo(
    () =>
      depo.isler.filter(
        (x) =>
          !KAPALI.has(x.durum) &&
          (!hazirSuzgec || hazirSuzgec.uyar(x)) &&
          gorunum.uyar(x) &&
          turUyar(x, ortak.tur) &&
          tarihUyar(x.acilis) &&
          metinUyar(x, ortak.arama),
      ),
    [depo.isler, ortak.arama, ortak.tur, tarihUyar, gorunum.uyar, hazirSuzgec],
  );
  const toplamAcik = useMemo(() => depo.isler.filter((x) => !KAPALI.has(x.durum)).length, [depo.isler]);
  const sutunlar = useSutunlar(depo.meta?.ek_etiketler, depo.isler);
  const duzen = useSutunDuzeni(sutunlar);
  const { harfler, yakinlik } = duzen;
  const acikTum = useMemo(() => depo.isler.filter((x) => !KAPALI.has(x.durum)), [depo.isler]);
  // değer listeleri (▾) diğer süzgeçlerden bağımsız: bütün açık işler (MAP İş türü gibi)
  const tablo = useTabloSuzgec(liste, sutunlar, acikTum);
  const secim = useSecim(tablo.suzulen, duzen.gorunen);
  const yeniler = useYeniGelenler(depo.isler);
  const yanan = useDegisenHucreler(depo.isler, depo.meta?.imlec, duzen.gorunen);
  const [gidilecek, setGidilecek] = useState<{ r: number; k: number } | null>(null);
  const [seritVar, setSeritVar] = useState(false);
  /* "Ata…": açıldığı andaki seçili satırlar (tablo tazelense de değişmez). */
  const [ataSatirlari, setAtaSatirlari] = useState<IsSatir[] | null>(null);
  const atayabilir = izinli('is.ata');
  const seciliSayi = secim.alan ? secim.alan.r2 - secim.alan.r1 + 1 : 0;
  const ataAc = useCallback(() => {
    const l = secim.seciliSatirlar();
    if (l.length) setAtaSatirlari(l);
  }, [secim]);
  /* "İlişkili iş farklı ekipte/atanmamış (N)": sayı dakikada bir; Pano'dan suz/iliskili ile gelince panel açılır. */
  const uyumsuz = useIliskiliUyumsuz(atayabilir, depo.meta?.imlec);
  const [hizalaAcik, setHizalaAcik] = useState(false);
  useEffect(() => {
    if (suz === TASKS_SUZ.iliskili && atayabilir) setHizalaAcik(true);
  }, [suz, atayabilir]);
  /* "Askıya al…": açıldığı andaki seçili satırlar. */
  const [askiSatirlari, setAskiSatirlari] = useState<IsSatir[] | null>(null);
  const askiAc = useCallback(() => {
    const l = secim.seciliSatirlar();
    if (l.length) setAskiSatirlari(l);
  }, [secim]);

  /* Değişiklik şeridinden task no → tablodaki satır (süzgeçte gizliyse / kapandıysa söyler). */
  const taskaGit = useCallback(
    (no: string) => {
      const uyar = (x: IsSatir) => x.boss_task_no === no || x.is_no === no;
      const r = tablo.suzulen.findIndex(uyar);
      if (r < 0) {
        bildirim.goster(
          depo.isler.some(uyar) ? `${no} süzgeç yüzünden tabloda görünmüyor.` : `${no} artık açık işlerde yok (kapandı).`,
          'uyari',
        );
        return;
      }
      secim.git(r, secim.etkin?.c ?? 0);
      setGidilecek((o) => ({ r, k: (o?.k ?? 0) + 1 }));
    },
    [tablo.suzulen, depo.isler, secim, bildirim],
  );

  /* BOSS ayrıntısı önden okunurken önce ekrandaki (süzülmüş + sıralanmış) ilk işler okunsun: liste değişince
     (2 sn sakinleşince) ve 5 dk'da bir sunucuya bildirilir. */
  const oncelikImza = useMemo(
    () => tablo.suzulen.filter((x) => x.boss_task_no).slice(0, 120).map((x) => x.is_no).join(','),
    [tablo.suzulen],
  );
  useEffect(() => {
    if (!oncelikImza) return;
    const nolar = oncelikImza.split(',');
    const t = window.setTimeout(() => void bossDetayOncelik(nolar), 2000);
    const a = window.setInterval(() => void bossDetayOncelik(nolar), 5 * 60_000);
    return () => {
      window.clearTimeout(t);
      window.clearInterval(a);
    };
  }, [oncelikImza]);

  /* Durum çubuğunda kısa bilgi ("Kopyalandı…"). */
  const bildirZaman = useRef(0);
  const bildir = useCallback((metin: string) => {
    setBildiri(metin);
    window.clearTimeout(bildirZaman.current);
    bildirZaman.current = window.setTimeout(() => setBildiri(null), 3500);
  }, []);

  /* Açılınca klavye tabloda (Excel gibi hemen ok tuşlarıyla gezilir). */
  const hazir = depo.durum === 'hazir' || depo.isler.length > 0;
  useEffect(() => {
    if (hazir && bolum === 'tumu' && !isNo) izgaraOdakla();
    // yalnız ilk hazır oluşta
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hazir, bolum]);

  /* Ctrl+F: tablonun arama kutusu (çekmece içindeyken tarayıcınınki). */
  useEffect(() => {
    const tus = (o: KeyboardEvent) => {
      if (!(o.ctrlKey || o.metaKey) || o.key.toLocaleLowerCase('tr-TR') !== 'f' || o.defaultPrevented) return;
      if ((o.target as HTMLElement | null)?.closest('.o-panel')) return;
      o.preventDefault();
      const girdi = aramaRef.current?.querySelector('input');
      girdi?.focus();
      girdi?.select();
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, []);

  /* ------------------------------ yazma ------------------------------ */

  const bizimYaz = useCallback(
    async (satirlar: IsSatir[], deger: string | null) => {
      if (!satirlar.length) return;
      satirlar.forEach((s) => depo.isYaz({ ...s, bizim_durum: deger }));
      let hata = 0;
      let sonHata = '';
      await sirayla(satirlar, async (s) => {
        try {
          depo.isYaz(await bizimDurumYaz(s.is_no, deger, s.surum));
        } catch (h) {
          depo.isYaz(s);
          hata++;
          sonHata = hataMetni(h);
        }
      });
      if (hata) bildirim.goster(satirlar.length > 1 ? `${hata} satıra yazılamadı: ${sonHata}` : sonHata, 'uyari');
      else if (satirlar.length > 1) bildirim.goster(`${satirlar.length} satıra “${deger ?? 'boş'}” yazıldı.`, 'basari');
    },
    [depo, bildirim],
  );

  /** Dolgu rengi YALNIZ seçili hücrelere (Excel gibi): önce ekranda, sonra sunucuda (5.000 hücrelik parçalar). */
  const boya = useCallback(
    async (hucreler: Array<{ is_no: string; sutun: string }>, renk: IsaretRengi | null) => {
      if (!hucreler.length) return;
      const satir = new Map(depo.isler.map((s) => [s.is_no, s]));
      const gruplar = new Map<string, string[]>();
      hucreler.forEach((h) => gruplar.set(h.is_no, [...(gruplar.get(h.is_no) ?? []), h.sutun]));
      const onceki: Record<string, IsSatir['hucre_renk']> = {};
      const yeni: Record<string, IsSatir['hucre_renk']> = {};
      gruplar.forEach((sutunlar, no) => {
        const s = satir.get(no);
        if (!s) return;
        onceki[no] = s.hucre_renk ?? {};
        yeni[no] = hucreBoya(s, sutunlar, renk);
      });
      depo.hucreRenkleriYaz(yeni);
      const PARCA = 5000;
      try {
        for (let i = 0; i < hucreler.length; i += PARCA) {
          const y = await hucreRenkYaz(hucreler.slice(i, i + PARCA), renk);
          depo.hucreRenkleriYaz(y.isler);
        }
      } catch (h) {
        depo.hucreRenkleriYaz(onceki);
        bildirim.goster(`Boyanamadı: ${hataMetni(h)}`, 'uyari');
      }
    },
    [depo, bildirim],
  );

  const excel = async () => {
    setExcelGidiyor(true);
    try {
      const s = await excelAc(tablo.suzulen, duzen.gorunen);
      bildirim.goster(s === 'acildi' ? 'Excel açılıyor…' : 'Excel dosyası indirildi.', 'basari');
    } catch {
      bildirim.goster('Excel dosyası hazırlanamadı.', 'uyari');
    } finally {
      setExcelGidiyor(false);
    }
  };

  /* ------------------------------ gezinme ------------------------------ */

  const kok = tasksKokYolu(bolum, suz);
  const ac = useCallback((no: string) => git(`${kok}/is/${encodeURIComponent(no)}`), [kok]);
  const kapat = useCallback(() => git(kok), [kok]);
  const hazirSuzgeciKaldir = () => git(isNo ? `/yonetici/isler/is/${encodeURIComponent(isNo)}` : '/yonetici/isler');

  const tumunuTemizle = () => {
    tablo.temizle();
    if (ortak.arama) ortak.aramaYaz('');
    if (gorunum.secili) gorunum.sec(null);
    if (ortak.tur.degerler.length) ortak.turYaz({ ...ortak.tur, degerler: [] });
    if (tarihEtkin(tarih)) setTarih(TARIH_TUMU);
    if (hazirSuzgec) hazirSuzgeciKaldir();
  };
  const turCip = turEtiketi(ortak.tur);
  const filtreSayisi =
    tablo.etkin.length + (ortak.arama ? 1 : 0) + (gorunum.secili ? 1 : 0) + (hazirSuzgec ? 1 : 0) +
    (turCip ? 1 : 0) + (tarihEtkin(tarih) ? 1 : 0);

  /* Tablo dışı bölümler (Kontrol, BOSS ekip eşleme): yalnız bekleyen varsa düğme çıkar. "BOSS'a işlenecek"
     listesinin üst çubukta düğmesi yok (2026-10); bölüm Pano'daki bağlantıdan (`giden`) açılır. */
  const sayac = depo.meta?.sayac;
  const bolumDugmeleri =
    bolum === 'tumu' && sayac && izinli('is.ata')
      ? ([
          ['kontrol', 'Kontrol', sayac.kontrol],
          ['boss-ekip', 'Eşleşmemiş BOSS ekibi', sayac.eslesmemis_ekip],
        ] as const).filter(([, , n]) => n > 0)
      : [];

  /* ------------------------------ gövde ------------------------------ */

  const ustEylemler = (
    <>
      {bolum !== 'tumu' ? (
        <Dugme tur="metin" simge={<Geri boyut={16} />} onClick={() => git('/yonetici/isler')}>
          TASKS'a dön
        </Dugme>
      ) : null}
      {bolumDugmeleri.map(([b, ad, n]) => (
        <Dugme key={b} tur="metin" onClick={() => git(tasksBolumYolu(b))}>
          {ad} ({n.toLocaleString('tr-TR')})
        </Dugme>
      ))}
      <Dugme onClick={() => git('/yonetici/is-haritasi')}>MAP</Dugme>
    </>
  );
  const panel = <GorunumPaneli acik={gorunumPaneli} kapat={() => setGorunumPaneli(false)} g={gorunum} />;

  if (depo.durum === 'yukleniyor' && !depo.isler.length) {
    return (
      <>
        <YonUst baslik="TASKS">{ustEylemler}</YonUst>
        <Icerik>
          <Iskelet satir={10} yukseklik={28} />
        </Icerik>
        {panel}
      </>
    );
  }
  if (depo.durum === 'hata' && !depo.isler.length) {
    return (
      <>
        <YonUst baslik="TASKS">{ustEylemler}</YonUst>
        <Icerik>
          <HataKutusu mesaj={depo.hata ?? 'İşler alınamadı.'} tekrar={() => void depo.tazele()} />
        </Icerik>
        {panel}
      </>
    );
  }

  const ozel =
    bolum === 'giden' ? (
      <BossGidenListesi ac={ac} />
    ) : bolum === 'boss-ekip' ? (
      <BossEkipEsleme />
    ) : bolum === 'kontrol' ? (
      <KontrolListesi isler={depo.isler.filter((x) => x.durum === 'triyaj')} ac={ac} />
    ) : null;

  /* Etkin süzgeç çipi: metin en çok 32 karakter (…; tamamı ipucunda), ✕ her zaman görünür. */
  const cip = (anahtar: string, metin: string, kaldir: () => void, ipucu?: string) => (
    <span key={anahtar} className="xg-cip" title={ipucu ?? metin}>
      <span className="xg-cip-metin">{cipKisalt(metin)}</span>
      <button type="button" aria-label={`${metin} — kaldır`} title="Kaldır" onClick={kaldir}>
        <Kapat boyut={12} kalinlik={2} />
      </button>
    </span>
  );

  return (
    <div className="ip-kok xg-ekran">
      <YonUst baslik="TASKS" altYazi={ozel ? `${toplamAcik.toLocaleString('tr-TR')} açık iş` : undefined}>
        {ustEylemler}
      </YonUst>
      <Icerik>
        {ozel ?? (
          <>
            <div className="xg-arac" role="toolbar" aria-label="TASKS araçları">
              <div ref={aramaRef} className="xg-ara">
                <AramaKutusu
                  deger={ortak.arama}
                  degisti={ortak.aramaYaz}
                  yerTutucu="Ara: ad, Task No, mahalle… (Ctrl+F)"
                  onKeyDown={(o) => {
                    if (o.key === 'Escape' && ortak.arama) {
                      o.stopPropagation();
                      ortak.aramaYaz('');
                    } else if (o.key === 'Enter' || o.key === 'ArrowDown') {
                      o.preventDefault();
                      izgaraOdakla();
                    }
                  }}
                />
              </div>
              <OzelFiltreler
                g={gorunum}
                taskAdlari={
                  // "Seçilenleri gizle" kipinde kaydedilecek liste = görünen task adları (gizlenenler hariç)
                  tablo.suzgec.tur?.kip === 'haric' && tablo.suzgec.tur.degerler?.length
                    ? tablo
                        .degerSayilari('tur')
                        .map(([v]) => v)
                        .filter((v) => v && !tablo.suzgec.tur!.degerler!.includes(v))
                    : tablo.suzgec.tur?.degerler ?? null
                }
                kaydedilebilir={izinli('is.ata')}
                kaydedildi={() => tablo.sutunYaz('tur', null)}
                duzenle={() => setGorunumPaneli(true)}
              />
              <SutunSecici sutunlar={sutunlar} duzen={duzen} />
              <DuzenMenusu duzen={duzen} />
              {duzenleyebilir ? (
                <DolguRengiDugmesi etkin={Boolean(secim.alan)} uygula={(r) => void boya(secim.seciliHucreler(), r)} />
              ) : null}
              {atayabilir ? (
                <button
                  type="button"
                  className="xg-arac-dugme"
                  disabled={!seciliSayi}
                  title="Seçili satırları bir teknisyene, bir gün ve saate ata (BOSS'a da yazılır)"
                  onClick={ataAc}
                >
                  Ata…{seciliSayi > 1 ? ` (${seciliSayi.toLocaleString('tr-TR')})` : ''}
                </button>
              ) : null}
              {duzenleyebilir ? (
                <button
                  type="button"
                  className="xg-arac-dugme"
                  disabled={!seciliSayi}
                  title="Seçili satırları BOSS askı nedeni, bitiş ve açıklamayla askıya al (BOSS'a da yazılır)"
                  onClick={askiAc}
                >
                  Askıya al…{seciliSayi > 1 ? ` (${seciliSayi.toLocaleString('tr-TR')})` : ''}
                </button>
              ) : null}
              {atayabilir && uyumsuz.veri?.is_sayisi ? (
                <button
                  type="button"
                  className="xg-arac-dugme"
                  title="Aynı müşterinin açık işleri farklı ekipte ya da atanmamış — hepsini aynı ekibe ata"
                  onClick={() => setHizalaAcik(true)}
                >
                  İlişkili iş farklı ekipte/atanmamış ({uyumsuz.veri.is_sayisi.toLocaleString('tr-TR')})
                </button>
              ) : null}
              {filtreSayisi ? (
                <button type="button" className="xg-arac-dugme" onClick={tumunuTemizle}>
                  Filtreleri temizle ({filtreSayisi})
                </button>
              ) : null}
              <span className="xg-bosluk" />
              <Dugme
                disabled={!tablo.suzulen.length || excelGidiyor}
                title="Görünen satır ve sütunlarla Excel'de aç"
                onClick={() => void excel()}
              >
                {excelGidiyor ? 'Hazırlanıyor…' : "Excel'de aç"}
              </Dugme>
            </div>
            {filtreSayisi ? (
              <div className="xg-cipler" aria-label="Etkin süzgeçler">
                {hazirSuzgec ? cip('hazir', `Pano: ${hazirSuzgec.ad}`, hazirSuzgeciKaldir) : null}
                {gorunum.secili ? cip('gorunum', `Özel filtre: ${gorunum.secili.ad}`, () => gorunum.sec(null)) : null}
                {ortak.arama ? cip('ara', `Ara: ${ortak.arama}`, () => ortak.aramaYaz('')) : null}
                {turCip ? cip('tur', turCip, () => ortak.turYaz({ ...ortak.tur, degerler: [] }), ortak.tur.degerler.join(', ')) : null}
                {tarihEtkin(tarih)
                  ? cip('tarih', tarihEtiketi(tarih, gunAnahtari(new Date(Date.now() + depo.sunucuFarkMs))), () => setTarih(TARIH_TUMU))
                  : null}
                {tablo.etkin.map((e) =>
                  cip(e.id, cipMetni(tablo.sutun.get(e.id)?.baslik ?? e.id, e.f), () => tablo.sutunYaz(e.id, null),
                    cipIpucu(tablo.sutun.get(e.id)?.baslik ?? e.id, e.f)),
                )}
              </div>
            ) : null}
            <FarkSeridi isler={depo.isler} git={taskaGit} tazelemeAnahtari={depo.meta?.imlec} gorundu={setSeritVar} />
            <IsTablosu
              satirlar={tablo.suzulen}
              sutunlar={duzen.gorunen}
              duzen={duzen}
              t={tablo}
              secim={secim}
              acikNo={isNo}
              yeniler={yeniler}
              duzenleyebilir={duzenleyebilir}
              harfler={harfler}
              yanan={yanan}
              gidilecek={gidilecek}
              ustAnahtar={`${filtreSayisi ? 1 : 0}${seritVar ? 1 : 0}${harfler ? 1 : 0}`}
              ac={ac}
              bizimYaz={(l, d) => void bizimYaz(l, d)}
              boya={(l, r) => void boya(l, r)}
              ata={atayabilir ? ataAc : undefined}
              aski={duzenleyebilir ? askiAc : undefined}
              yakinlik={yakinlik}
              yakinlikDegisti={yakinlikYaz}
              bildir={bildir}
            />
            <DurumCubugu
              satirlar={tablo.suzulen}
              sutunlar={duzen.gorunen}
              alan={secim.alan}
              toplamKayit={toplamAcik}
              bildiri={bildiri}
              yakinlik={yakinlik}
              yakinlikDegisti={yakinlikYaz}
            />
          </>
        )}
      </Icerik>
      <IsCekmecesi isNo={isNo} kapat={kapat} />
      <TopluAtaPaneli acik={Boolean(ataSatirlari)} kapat={() => setAtaSatirlari(null)} satirlar={ataSatirlari ?? []} />
      <TopluAskiPaneli acik={Boolean(askiSatirlari)} kapat={() => setAskiSatirlari(null)} satirlar={askiSatirlari ?? []} />
      <IliskiliHizalaPaneli
        acik={hizalaAcik}
        kapat={() => setHizalaAcik(false)}
        veri={uyumsuz.veri}
        bitti={() => {
          uyumsuz.yenile();
          void depo.tazele();
        }}
      />
      {panel}
    </div>
  );
}
