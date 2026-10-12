/**
 * "Ata…" (TASKS'ta seçili satırlar, MAP'te seçili noktalar): teknisyen (BOSS ekibi) + gün + 2 saatlik dilim
 * (en çok 7 gün ileri) → seçili işlerin hepsi atanır. Sunucu her işi kendi işleminde atar (`POST /api/isler/toplu-ata`,
 * 50'şer parça — ilerleme çubuğu) ve her atama BOSS'a kendiliğinden yazılır (eklenti; aynı ekip + aynı dilim tek
 * istekte, istek başına en çok 20 iş). Özet: uygulamada n ✓ / n hata (nedeniyle), ardından BOSS hâli
 * (`POST /api/boss/atama-durumlari`, 3 sn'de bir, en çok 3 dk): BOSS'ta ✓ · gidiyor · hata (nedeniyle).
 * BOSS'a yazılamayanlar (hata, nedeniyle) için "Yeniden dene" (`POST /api/boss/atama-yeniden`): her iş tek başına istekte
 * yeniden kuyruğa girer; hiçbir şey kendiliğinden yeniden gönderilmez. Panel açılınca seçili işlerin önceki BOSS
 * atama hatası varsa (ör. 07.10'daki 500'ler) seçim ekranında da "Yeniden dene" görünür.
 * Giriş: <TopluAtaPaneli acik kapat satirlar/>. Çağıranlar: Isler.tsx, IsHaritasiEkrani.tsx.
 * TEK iş ataması (İş çekmecesi) AYNI yolu kullanır: `useAtaFormu({ tek: true, satirlar: [is] })` → aynı uç, aynı BOSS hâli.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import { bossAtamaDurumlari, bossAtamaYeniden, hataMetni, topluAta, type BossAtamaHali } from '../../../cekirdek/is/api';
import type { Dilim } from '../../../cekirdek/ortak/DilimSecici';
import { Dugme } from '../../../cekirdek/ortak/Ilkel';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { useIsler } from './durum';
import { yerelKatYaz } from './map/noktalar';
import { dilimMetni, kisaAd } from './parcalar';
import { TakvimDilim, TeknikAcilir } from './PlanSecici';
import { useIliskili } from './IliskiliSecim';

const PARCA = 50;
const YOKLAMA_MS = 3000;
const YOKLAMA_EN_COK_MS = 3 * 60_000;
const KAPALI = new Set(['cozuldu', 'kapandi']);

interface Hata {
  no: string;
  neden: string;
  /** Sunucunun hata kodu (ör. altyapi_engeli: çekmece "Yine de ata" gösterir). */
  kod?: string;
}

interface Sonuc {
  atanan: string[];
  hatalar: Hata[];
}

const sayi = (n: number) => n.toLocaleString('tr-TR');

/** Formun ihtiyaç duyduğu satır alanları (IsSatir ya da İş çekmecesinin IsAyrinti'si). */
export type AtaSatiri = Pick<IsSatir, 'is_no' | 'durum' | 'boss_task_no' | 'boss_durum' | 'surum'>;

export interface AtaFormu {
  /** Seçim formu (teknisyen + gün/dilim) ya da bitti özeti (uygulamada ✓ / hata + BOSS hâli + Yeniden dene). */
  govde: ReactNode;
  asama: 'sec' | 'gidiyor' | 'bitti';
  hazir: boolean;
  /** Gönder (toplu-ata; tek işte `yineDe` altyapı engeline rağmen). */
  uygula: (secenek?: { yineDe?: boolean }) => Promise<void>;
  /** Uygulamada atanamayanlar (no + neden; çekmece "Yine de ata"yı buna göre gösterir). */
  hatalar: Hata[];
  ilerleme: number;
  acikSayi: number;
  kapaliSayisi: number;
  /** Özetten seçime dön (çekmecede "Değiştir"). */
  yenidenSec: () => void;
}

/**
 * Ata formu — TopluAtaPaneli ve İş çekmecesinin TEK iş ataması ortak kullanır (aynı uç `POST /api/isler/toplu-ata`,
 * aynı BOSS hâli yoklaması, aynı "Yeniden dene"). `tek`: satırın sürümü gönderilir (çakışma 409 gibi değil, atlanan
 * olarak döner) ve `baslangic` (çekmecenin önerdiği teknisyen + dilim) ile açılır.
 */
export function useAtaFormu({
  acik,
  satirlar,
  bitti,
  tek = false,
  baslangic,
}: {
  acik: boolean;
  satirlar: AtaSatiri[];
  bitti?: () => void;
  tek?: boolean;
  baslangic?: { teknikId: number | null; dilim: Dilim | null };
}): AtaFormu {
  const depo = useIsler();
  const [teknikId, setTeknikId] = useState<number | null>(baslangic?.teknikId ?? null);
  const [dilim, setDilim] = useState<Dilim | null>(baslangic?.dilim ?? null);
  const [asama, setAsama] = useState<'sec' | 'gidiyor' | 'bitti'>('sec');
  const [ilerleme, setIlerleme] = useState(0);
  const [sonuc, setSonuc] = useState<Sonuc | null>(null);
  const [boss, setBoss] = useState<Record<string, BossAtamaHali>>({});
  const [genelHata, setGenelHata] = useState<string | null>(null);
  const basZaman = useRef(0);
  /* Seçili işlerin ÖNCEKİ BOSS atama hâli (yalnız seçim ekranında; hatalılar yeniden denenebilir). */
  const [onceki, setOnceki] = useState<Record<string, BossAtamaHali>>({});
  const [yenidenGidiyor, setYenidenGidiyor] = useState(false);
  const [yenidenMetni, setYenidenMetni] = useState<string | null>(null);

  /* Panel her açılışta baştan (seçilen kişi ve dilim kalır: art arda aynı ekibe atanabilsin). */
  useEffect(() => {
    if (!acik) return;
    setAsama('sec');
    setIlerleme(0);
    setSonuc(null);
    setBoss({});
    setGenelHata(null);
    setOnceki({});
    setYenidenMetni(null);
  }, [acik]);

  const acikSatirlar = useMemo(() => satirlar.filter((s) => !KAPALI.has(s.durum)), [satirlar]);
  /* İlişkili işler (aynı müşterinin öbür açık işleri; varsayılan dahil): seçimle birlikte atanır. */
  const seciliNolar = useMemo(() => acikSatirlar.map((s) => s.is_no), [acikSatirlar]);
  const iliskili = useIliskili(acik && asama === 'sec', seciliNolar);
  const gonderilecek = useMemo(
    () => [
      ...acikSatirlar.map((s) => ({ is_no: s.is_no, surum: s.surum, boss_durum: s.boss_durum, kendi: true })),
      ...iliskili.ekler.map((x) => ({ is_no: x.is_no, surum: x.surum, boss_durum: x.boss_durum, kendi: false })),
    ],
    [acikSatirlar, iliskili.ekler],
  );
  useEffect(() => {
    if (!acik || !acikSatirlar.length) return undefined;
    let iptal = false;
    bossAtamaDurumlari(acikSatirlar.slice(0, 500).map((s) => s.is_no))
      .then((y) => !iptal && setOnceki(y.durumlar))
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, [acik, acikSatirlar]);
  const oncekiHatali = useMemo(
    () => Object.entries(onceki).filter(([, h]) => h.durum === 'hata' && h.yeniden).map(([n]) => n),
    [onceki],
  );
  const kapaliSayisi = satirlar.length - acikSatirlar.length;
  const taskNo = useMemo(() => {
    const m = new Map(satirlar.map((s) => [s.is_no, s.boss_task_no || s.is_no]));
    iliskili.hepsi.forEach((x) => m.set(x.is_no, x.task_no));
    return (no: string) => m.get(no) ?? no;
  }, [satirlar, iliskili.hepsi]);

  const dilimler = depo.ayarlar?.dilimler ?? [];
  const ilkSaat = dilimler.length ? parseInt(dilimler[0].bas, 10) : 8;
  const sonSaat = dilimler.length ? parseInt(dilimler[dilimler.length - 1].bit, 10) : 20;
  const simdi = new Date(Date.now() + depo.sunucuFarkMs);
  const teknik = depo.teknikler.find((t) => t.id === teknikId) ?? null;

  const ata = async (secenek: { yineDe?: boolean } = {}) => {
    if (!teknikId || !dilim || !gonderilecek.length) return;
    setAsama('gidiyor');
    setGenelHata(null);
    setIlerleme(0);
    const atanan: string[] = [];
    const hatalar: Hata[] = [];
    const liste = gonderilecek;
    for (let i = 0; i < liste.length; i += PARCA) {
      const parca = liste.slice(i, i + PARCA);
      try {
        const y = await topluAta(
          parca.map((s) => ({
            is_no: s.is_no,
            teknik_id: teknikId,
            randevu: { bas: dilim.bas, bit: dilim.bit, teyitli: dilim.teyitli },
            ...(tek && s.kendi ? { surum: s.surum, ...(secenek.yineDe ? { yine_de: true } : {}) } : {}),
          })),
        );
        atanan.push(...y.atanan);
        y.atlanan.forEach((a) => hatalar.push({ no: a.is_no, neden: a.hata || a.kod, kod: a.kod }));
      } catch (h) {
        const m = hataMetni(h);
        parca.forEach((s) => hatalar.push({ no: s.is_no, neden: m }));
        if (i === 0) setGenelHata(m);
      }
      setIlerleme(Math.min(liste.length, i + PARCA));
    }
    setSonuc({ atanan, hatalar });
    setAsama('bitti');
    basZaman.current = Date.now();
    const atananKume = new Set(atanan);
    yerelKatYaz(liste.filter((s) => atananKume.has(s.is_no)), 'randevu_alindi'); // MAP: BOSS eşitlemesini beklemeden
    void depo.tazele();
    if (atanan.length) bitti?.();
  };

  /* BOSS hâli: gidiyor olan kaldıkça yoklanır. */
  const bossOku = useCallback(async (nolar: string[]) => {
    if (!nolar.length) return;
    try {
      const y = await bossAtamaDurumlari(nolar);
      setBoss(y.durumlar);
    } catch {
      /* özet yine görünür; BOSS hâli yazılmaz */
    }
  }, []);
  useEffect(() => {
    if (asama !== 'bitti' || !sonuc?.atanan.length) return undefined;
    const gidiyor = !Object.keys(boss).length || sonuc.atanan.some((n) => (boss[n]?.durum ?? 'gidiyor') === 'gidiyor');
    if (!gidiyor || Date.now() - basZaman.current > YOKLAMA_EN_COK_MS) return undefined;
    const t = window.setTimeout(() => void bossOku(sonuc.atanan), Object.keys(boss).length ? YOKLAMA_MS : 600);
    return () => window.clearTimeout(t);
  }, [asama, sonuc, boss, bossOku]);

  const bossSay = useMemo(() => {
    const m = { tamam: 0, gidiyor: 0, hata: 0, kapali: 0 };
    for (const n of sonuc?.atanan ?? []) {
      const d = boss[n]?.durum ?? 'gidiyor';
      if (d === 'tamam') m.tamam++;
      else if (d === 'hata') m.hata++;
      else if (d === 'kapali' || d === 'yok') m.kapali++;
      else m.gidiyor++;
    }
    return m;
  }, [sonuc, boss]);
  const bossHatalari = useMemo(
    () =>
      (sonuc?.atanan ?? [])
        .filter((n) => boss[n]?.durum === 'hata')
        .map((n) => ({ no: n, neden: boss[n]?.hata || 'BOSS’a yazılamadı' })),
    [sonuc, boss],
  );

  /** BOSS'a yazılamayanları yeniden kuyruğa al; özetin yoklaması yeniden başlar. */
  const yenidenDene = async (nolar: string[], ozette: boolean) => {
    if (!nolar.length || yenidenGidiyor) return;
    setYenidenGidiyor(true);
    setYenidenMetni(null);
    try {
      const y = await bossAtamaYeniden(nolar);
      setYenidenMetni(
        `${sayi(y.yeniden.length)} iş yeniden BOSS’a gönderiliyor${y.atlanan.length ? ` · ${sayi(y.atlanan.length)} atlandı` : ''}`,
      );
      if (ozette) {
        basZaman.current = Date.now();
        setBoss((b) => {
          const y2 = { ...b };
          y.yeniden.forEach((n) => (y2[n] = { durum: 'gidiyor' }));
          return y2;
        });
      } else {
        setOnceki((o) => {
          const y2 = { ...o };
          y.yeniden.forEach((n) => (y2[n] = { durum: 'gidiyor' }));
          return y2;
        });
        if (y.yeniden.length) {
          setSonuc({ atanan: y.yeniden, hatalar: [] });
          setBoss({});
          basZaman.current = Date.now();
          setAsama('bitti');
        }
      }
    } catch (h) {
      setYenidenMetni(hataMetni(h));
    } finally {
      setYenidenGidiyor(false);
    }
  };


  const govde = (
    <div className="ta-kok">
      {asama === 'bitti' && sonuc ? (
        <div className="ta-ozet" aria-live="polite">
          <p className="ta-baslik">
            {teknik ? kisaAd(teknik.ad) : 'Teknisyen'}
            {dilim ? ` · ${dilimMetni(dilim.bas, dilim.bit)}` : ''}
          </p>
          <div className="ta-sayilar">
            <span className="ta-sayi yesil">
              <b>{sayi(sonuc.atanan.length)}</b> ✓ atandı
            </span>
            {sonuc.hatalar.length ? (
              <span className="ta-sayi kirmizi">
                <b>{sayi(sonuc.hatalar.length)}</b> hata
              </span>
            ) : null}
          </div>
          {sonuc.atanan.length ? (
            <div className="ta-sayilar" title="BOSS’a yazma (eklenti, BOSS sekmesi açıkken)">
              <span className="ta-etiket">BOSS:</span>
              {bossSay.tamam ? (
                <span className="ta-sayi yesil">
                  <b>{sayi(bossSay.tamam)}</b> ✓
                </span>
              ) : null}
              {bossSay.gidiyor ? (
                <span className="ta-sayi mavi">
                  <b>{sayi(bossSay.gidiyor)}</b> gidiyor…
                </span>
              ) : null}
              {bossSay.hata ? (
                <span className="ta-sayi kirmizi">
                  <b>{sayi(bossSay.hata)}</b> hata
                </span>
              ) : null}
              {bossSay.kapali ? (
                <span className="ta-sayi gri">
                  <b>{sayi(bossSay.kapali)}</b> BOSS’a yazma kapalı
                </span>
              ) : null}
            </div>
          ) : null}
          {genelHata && !sonuc.atanan.length ? <p className="ip-uyari kirmizi">{genelHata}</p> : null}
          {bossHatalari.length ? (
            <div className="ta-sayilar">
              <button
                type="button"
                className="o-dugme kucuk"
                disabled={yenidenGidiyor}
                title="BOSS’a yazılamayan atamaları yeniden gönder (her iş tek başına)"
                onClick={() => void yenidenDene(bossHatalari.map((h) => h.no), true)}
              >
                {yenidenGidiyor ? 'Gönderiliyor…' : `Yeniden dene (${sayi(bossHatalari.length)})`}
              </button>
            </div>
          ) : null}
          {yenidenMetni ? <p className="ta-not">{yenidenMetni}</p> : null}
          {sonuc.hatalar.length || bossHatalari.length ? (
            <ul className="ta-hatalar">
              {sonuc.hatalar.map((h) => (
                <li key={`u${h.no}`}>
                  <b>{taskNo(h.no)}</b> {h.neden}
                </li>
              ))}
              {bossHatalari.map((h) => (
                <li key={`b${h.no}`}>
                  <b>{taskNo(h.no)}</b> BOSS: {h.neden}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <>
          <div className="ta-alan">
            <span>Teknisyen</span>
            <TeknikAcilir teknikler={depo.teknikler} deger={teknikId} degisti={setTeknikId} />
          </div>
          <div className="ta-alan">
            <span>Gün ve saat</span>
            <TakvimDilim deger={dilim} degisti={setDilim} ilkSaat={ilkSaat} sonSaat={sonSaat} simdi={simdi} enCokGun={7} />
          </div>
          {asama === 'gidiyor' ? (
            <div className="ta-ilerleme" role="progressbar" aria-valuemin={0} aria-valuemax={gonderilecek.length} aria-valuenow={ilerleme}>
              <i style={{ width: `${gonderilecek.length ? (ilerleme / gonderilecek.length) * 100 : 0}%` }} />
            </div>
          ) : null}
          {iliskili.govde}
          {oncekiHatali.length ? (
            <div className="ip-uyari kirmizi ta-onceki">
              <span>
                {sayi(oncekiHatali.length)} işin önceki ataması BOSS’a yazılamadı
                {onceki[oncekiHatali[0]]?.hata ? ` (${onceki[oncekiHatali[0]]?.hata})` : ''}.
              </span>{' '}
              <button
                type="button"
                className="o-dugme kucuk"
                disabled={yenidenGidiyor || asama === 'gidiyor'}
                onClick={() => void yenidenDene(oncekiHatali, false)}
              >
                {yenidenGidiyor ? 'Gönderiliyor…' : 'Yeniden dene'}
              </button>
            </div>
          ) : null}
          {yenidenMetni ? <p className="ta-not">{yenidenMetni}</p> : null}
          <p className="ta-not">Her iş BOSS’a da kendiliğinden yazılır (BOSS sekmesi açık olmalı).</p>
        </>
      )}
    </div>
  );

  return {
    govde,
    asama,
    hazir: Boolean(teknikId && dilim && gonderilecek.length),
    uygula: ata,
    hatalar: sonuc?.hatalar ?? [],
    ilerleme,
    acikSayi: gonderilecek.length,
    kapaliSayisi,
    yenidenSec: () => {
      setAsama('sec');
      setSonuc(null);
      setBoss({});
      setGenelHata(null);
    },
  };
}

export function TopluAtaPaneli({
  acik,
  kapat,
  satirlar,
  bitti,
}: {
  acik: boolean;
  kapat: () => void;
  satirlar: IsSatir[];
  /** Atama bitince (seçimi temizlemek için). */
  bitti?: () => void;
}) {
  const f = useAtaFormu({ acik, satirlar, bitti });
  const { asama, ilerleme } = f;
  const acikSayi = f.acikSayi;
  const alt =
    asama === 'bitti' ? (
      <Dugme tur="birincil" genis onClick={kapat}>
        Kapat
      </Dugme>
    ) : (
      <>
        <Dugme tur="metin" onClick={kapat} disabled={asama === 'gidiyor'}>
          Vazgeç
        </Dugme>
        <Dugme tur="birincil" disabled={!f.hazir || asama === 'gidiyor'} onClick={() => void f.uygula()}>
          {asama === 'gidiyor' ? `Atanıyor… ${sayi(ilerleme)} / ${sayi(acikSayi)}` : `${sayi(acikSayi)} işi ata`}
        </Dugme>
      </>
    );

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={asama === 'gidiyor'}
      baslik="Ata"
      altBaslik={`${sayi(acikSayi)} iş seçili${f.kapaliSayisi ? ` · ${sayi(f.kapaliSayisi)} kapalı iş atlanır` : ''}`}
      alt={alt}
    >
      {f.govde}
    </Panel>
  );
}
