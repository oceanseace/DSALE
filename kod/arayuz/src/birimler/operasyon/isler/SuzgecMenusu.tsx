/**
 * Sütun başlığındaki ▾ — Excel'in otomatik süzgeci: A→Z / Z→A sırala, renge göre süz (bu sütundaki hücre dolgusu),
 * değer listesi (MAP "İş türü" ile aynı: kip + seçim + arama + Görünenleri seç), "metin içerir".
 * Değerler DİĞER süzgeçlere göre sayılır.
 * Giriş: <SuzgecMenusu id x y t kapat />. Kim: Tablo.tsx. Durum: tabloSuzgec.ts.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { IsaretRengi } from '../../../cekirdek/is/tipler';
import { useKisiAyarlari } from '../../../cekirdek/ortak/kisiAyarlari';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import { RENK_ADI } from './sutunlar';
import {
  BOS_ETIKET,
  degerGoster,
  gorunenleriBirak,
  gorunenleriSec,
  govdeBaslangic,
  suzgecKur,
  type DegerSatiri,
  type TabloSuzgec,
} from './tabloSuzgec';

const EN_COK = 500;

export function SuzgecMenusu({ id, x, y, t, kapat }: { id: string; x: number; y: number; t: TabloSuzgec; kapat: () => void }) {
  const c = t.sutun.get(id);
  const renkler = useMemo(() => t.renkler(id), [t, id]);
  const mevcutRenk = t.suzgec[id]?.renk;
  const kok = useRef<HTMLDivElement>(null);
  useDisariKapat(kok, kapat);
  useEkranaSigdir(kok);

  const sirala = (yon: 1 | -1 | null) => {
    t.setSiralama(yon ? { id, yon } : null);
    kapat();
  };
  /** Renge göre süz (Excel): bu sütunda hücresi o renkte olan satırlar; aynı renge yeniden basınca kalkar. */
  const renkSuz = (r: IsaretRengi) => {
    const { renk: _eski, ...kalan } = t.suzgec[id] ?? { degerler: null, metin: '' };
    t.sutunYaz(id, mevcutRenk === r ? kalan : { ...kalan, renk: r });
    kapat();
  };

  // ekrana sığdırma useEkranaSigdir'de: alt kenara taşarsa yukarı kayar, çok uzunsa değer listesi kısalır
  const sol = Math.max(8, Math.min(x - 290, window.innerWidth - 306));
  return createPortal(
    <div className="xg-menu xg-suzgec" ref={kok} style={{ left: sol, top: Math.max(8, y + 2) }} role="dialog" aria-label={`${c?.baslik ?? ''} süzgeci`}>
      <button type="button" className="xg-menu-satir" onClick={() => sirala(1)}>
        <span className="xg-menu-simge">A↓</span> A'dan Z'ye sırala
      </button>
      <button type="button" className="xg-menu-satir" onClick={() => sirala(-1)}>
        <span className="xg-menu-simge">Z↓</span> Z'den A'ya sırala
      </button>
      {t.siralama?.id === id ? (
        <button type="button" className="xg-menu-satir" onClick={() => sirala(null)}>
          <span className="xg-menu-simge" /> Sıralamayı kaldır
        </button>
      ) : null}
      {renkler.length ? (
        <div className="xg-menu-renk">
          <span>Renge göre süz</span>
          {renkler.map((r) => (
            <button
              key={r}
              type="button"
              className={`xg-renk r-${r}${mevcutRenk === r ? ' secili' : ''}`}
              title={mevcutRenk === r ? `${RENK_ADI[r]} süzgecini kaldır` : `${RENK_ADI[r]} dolgulu hücreler`}
              aria-label={`${RENK_ADI[r]} dolgulu hücreler`}
              aria-pressed={mevcutRenk === r}
              onClick={() => renkSuz(r)}
            />
          ))}
        </div>
      ) : null}
      <hr />
      <SuzgecGovde id={id} t={t} kapat={kapat} odakla />
    </div>,
    document.body,
  );
}

/**
 * Bir sütunun süzgeç gövdesi — MAP'teki "İş türü" ile AYNI davranış (TASKS ▾ menüsü ve MAP Filtreler çekmecesi):
 *   · Kip: "Yalnız seçilenleri göster" / "Seçilenleri gizle". Kip değişince işaretler DEĞİŞMEZ.
 *   · İşaretli kutular = seçilen değerler (başta hiçbiri; süzgeç yoksa hiçbir şey gizlenmez).
 *   · Değer araması listeyi daraltır (içerir, Türkçe harf duyarsız); "(Tümünü seç)" / "Görünenleri seç" görünen
 *     değerleri seçime ekler, "Temizle" seçimi boşaltır.
 *   · "Metin içerir" ayrıca. TASKS'ta Tamam/İptal; MAP çekmecesinde (`aninda`) her değişiklik hemen uygulanır.
 * Saf mantık: tabloSuzgec.ts (govdeBaslangic, degerAra, gorunenleriSec, suzgecKur).
 */
export function SuzgecGovde({
  id,
  t,
  kapat,
  odakla = false,
  aninda = false,
}: {
  id: string;
  t: TabloSuzgec;
  kapat: () => void;
  odakla?: boolean;
  /** MAP çekmecesi: Tamam beklemeden uygula (İş türü gibi). */
  aninda?: boolean;
}) {
  const sayilar = t.degerSayilari;
  const degerler = useMemo(() => sayilar(id), [sayilar, id]);
  const mevcut = t.suzgec[id];
  const [bas] = useState(() => govdeBaslangic(mevcut));
  const [kip, setKip] = useState<'dahil' | 'haric'>(bas.kip);
  const [secim, setSecim] = useState<Set<string>>(bas.secim);
  const [metin, setMetin] = useState(mevcut?.metin ?? '');

  const kur = (k: 'dahil' | 'haric', sec: Set<string>, m: string) => suzgecKur(k, [...sec], m.trim(), mevcut?.renk);
  /* MAP: her değişiklik hemen uygulanır (ilk çizimde değil). */
  const ilk = useRef(true);
  useEffect(() => {
    if (ilk.current) {
      ilk.current = false;
      return;
    }
    if (aninda) t.sutunYaz(id, kur(kip, secim, metin));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kip, secim, metin]);

  const uygula = () => {
    t.sutunYaz(id, kur(kip, secim, metin));
    kapat();
  };

  return (
    <>
      <DegerSecici
        degerler={degerler}
        kip={kip}
        setKip={setKip}
        secim={secim}
        setSecim={setSecim}
        odakla={odakla}
        enter={aninda ? undefined : uygula}
      />
      <label className="xg-menu-etiket">
        Metin içerir
        <input
          className="o-girdi kucuk"
          value={metin}
          onChange={(o) => setMetin(o.target.value)}
          onKeyDown={(o) => o.key === 'Enter' && !aninda && uygula()}
          placeholder="ör. Nilüfer"
        />
      </label>
      <div className="xg-menu-alt">
        <button
          type="button"
          className="o-dugme kucuk"
          disabled={!mevcut}
          onClick={() => {
            t.sutunYaz(id, null);
            if (aninda) {
              setSecim(new Set());
              setMetin('');
            } else kapat();
          }}
        >
          Süzgeci kaldır
        </button>
        <span className="xg-bosluk" />
        {aninda ? null : (
          <>
            <button type="button" className="o-dugme kucuk" onClick={kapat}>
              İptal
            </button>
            <button type="button" className="o-dugme kucuk vurgu" onClick={uygula}>
              Tamam
            </button>
          </>
        )}
      </div>
    </>
  );
}

/**
 * TEK değer seçici — MAP "İş türü" ve her sütun süzgeci (TASKS ▾, MAP Filtreler çekmecesi) bunu kullanır:
 *   · Kip: "Yalnız seçilenleri göster" / "Seçilenleri gizle" (kip değişince işaretler DEĞİŞMEZ);
 *   · liste diğer süzgeçlerden BAĞIMSIZ bütün değerlerdir (DegerSatiri: toplam + görünür); diğer süzgeçler
 *     yüzünden şu an görünmeyen değer varsayılan olarak listede YOK (Ayarlar ▸ "Diğer filtrelerle gizlenen değerleri
 *     soluk göster" açıksa soluk çizilir); arama yine hepsinde arar ("kuru" → bütün kurulumlar, gizlenenler soluk);
 *     işaretli değer hep kalır (bkz. tabloSuzgec.ts degerGoster);
 *   · arama "içerir" (Türkçe harf duyarsız) · "Görünenleri seç" · "Temizle" · "(Tümünü seç)".
 */
export function DegerSecici({
  degerler,
  kip,
  setKip,
  secim,
  setSecim,
  odakla = false,
  enter,
  araYazisi = 'Değer ara…',
}: {
  degerler: DegerSatiri[];
  kip: 'dahil' | 'haric';
  setKip: (k: 'dahil' | 'haric') => void;
  secim: Set<string>;
  setSecim: (f: (s: Set<string>) => Set<string>) => void;
  odakla?: boolean;
  /** Enter (TASKS ▾: Tamam). */
  enter?: () => void;
  araYazisi?: string;
}) {
  const [ara, setAra] = useState('');
  const listeRef = useRef<HTMLDivElement>(null);
  const { suzgec_soluk_goster: soluk } = useKisiAyarlari();
  /* Pencere açılırkenki seçim de listede kalır: işareti kaldırılan değer kaybolmasın (yeniden işaretlenebilsin). */
  const [ilkSecim] = useState(() => new Set(secim));
  const gorunen = useMemo(
    () => degerGoster(degerler, ara, { has: (v: string) => secim.has(v) || ilkSecim.has(v) }, soluk),
    [degerler, ara, secim, ilkSecim, soluk],
  );
  const gorunenAdlar = useMemo(() => gorunen.map(([v]) => v), [gorunen]);
  const hepsi = gorunen.length > 0 && gorunen.every(([v]) => secim.has(v));
  /* Arama değişince liste başa döner (önceki kaydırma yeni kısa listeyi gizlemesin). */
  useEffect(() => {
    if (listeRef.current) listeRef.current.scrollTop = 0;
  }, [ara]);
  const degistir = (v: string) =>
    setSecim((s) => {
      const y2 = new Set(s);
      if (y2.has(v)) y2.delete(v);
      else y2.add(v);
      return y2;
    });
  const n = secim.size;
  const ozet = !n
    ? 'Seçim yok — hiçbir şey gizlenmez'
    : `${n.toLocaleString('tr-TR')} değer seçili — ${kip === 'haric' ? 'bunlar gizlenir' : 'yalnız bunlar gösterilir'}`;
  return (
    <>
      <div className="ts-kip xg-kip" role="radiogroup" aria-label="Süzgeç kipi">
        <label>
          <input type="radio" checked={kip === 'dahil'} onChange={() => setKip('dahil')} /> Yalnız seçilenleri göster
        </label>
        <label>
          <input type="radio" checked={kip === 'haric'} onChange={() => setKip('haric')} /> Seçilenleri gizle
        </label>
      </div>
      <input
        className="o-girdi kucuk"
        type="search"
        value={ara}
        autoFocus={odakla}
        onChange={(o) => setAra(o.target.value)}
        onKeyDown={(o) => o.key === 'Enter' && enter?.()}
        placeholder={araYazisi}
        aria-label="Değerlerde ara"
      />
      <div className="ts-eylem xg-eylem">
        <button
          type="button"
          className="o-dugme kucuk metin"
          disabled={!gorunen.length}
          onClick={() => setSecim((s) => gorunenleriSec(s, gorunenAdlar))}
        >
          Görünenleri seç{ara.trim() ? ` (${gorunen.length.toLocaleString('tr-TR')})` : ''}
        </button>
        <button type="button" className="o-dugme kucuk metin" disabled={!n} onClick={() => setSecim(() => new Set())}>
          Temizle
        </button>
      </div>
      <div className="xg-liste" ref={listeRef}>
        {gorunen.length ? (
          <label className="xg-deger tumu">
            <input
              type="checkbox"
              checked={hepsi}
              onChange={() => setSecim((s) => (hepsi ? gorunenleriBirak(s, gorunenAdlar) : gorunenleriSec(s, gorunenAdlar)))}
            />
            <span>{ara.trim() ? '(Görünenlerin tümünü seç)' : '(Tümünü seç)'}</span>
          </label>
        ) : null}
        {gorunen.slice(0, EN_COK).map(([v, toplam, gorunur]) => (
          <label
            key={v}
            className={`xg-deger${gorunur ? '' : ' soluk'}`}
            title={gorunur ? undefined : 'Diğer süzgeçler yüzünden şu an görünmüyor'}
          >
            <input type="checkbox" checked={secim.has(v)} onChange={() => degistir(v)} />
            <span className="xg-deger-ad">{v || BOS_ETIKET}</span>
            <span className="xg-sayi">{toplam.toLocaleString('tr-TR')}</span>
          </label>
        ))}
        {!gorunen.length ? <div className="xg-not">{ara.trim() ? `“${ara.trim()}” geçen değer yok` : 'Değer yok'}</div> : null}
        {gorunen.length > EN_COK ? (
          <div className="xg-not">+{(gorunen.length - EN_COK).toLocaleString('tr-TR')} değer daha — aramayla daraltın</div>
        ) : null}
      </div>
      <div className="xg-not xg-ozet" aria-live="polite">
        {ozet}
      </div>
    </>
  );
}
