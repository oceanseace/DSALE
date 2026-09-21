/**
 * Sunum modu — 10 sahnelik sinematik anlatım.
 *
 * Yapı: tek deck.gl yüzeyi (HaritaSahnesi) + sahne sözlüğü (sahneler/) + yönetmen (motor/).
 * Sahneler saf fonksiyonlardır: (plan, adım, t) → katmanlar; HTML katmanı ayrı bileşendir.
 *
 * Tuşlar: → PageDown Boşluk / sol tık = ileri · ← PageUp / sağ tık = geri · Home başa ·
 *         F film (≈90 sn döngü) · 1–9, 0 sahneye atla. İmleç 2 sn sonra kaybolur.
 */
import { useEffect, useMemo, useRef, useState } from 'react';

import { kontratGuncelle } from '../core/kontrat';
import { urlOku, urlYaz } from '../core/url';
import { useUygulama } from '../core/uygulama';
import HaritaSahnesi, { type Boyut, type HaritaApi } from '../map/HaritaSahnesi';
import { KAMERA, type KameraDurumu } from '../map/kamera';
import { KaynakNotu, Marka, boy, bosluk, u } from '../ui';

import Cagrilar, { type CagriNoktasi, type CagrilarApi } from './bilesen/Cagrilar';
import Noktalar from './bilesen/Noktalar';
import { useImlecGizle } from './motor/imlec';
import { useKameraOynatici } from './motor/kameraOynatici';
import { adimSaatiOlustur, useYavasSaat } from './motor/saat';
import { useTuslar } from './motor/tuslar';
import { useYonetmen } from './motor/yonetmen';
import type { SahneBaglami, SahneDurumu } from './motor/tipler';
import { SAHNELER } from './sahneler';
import './sunum.css';

const BOS_CAGRI: CagriNoktasi[] = [];

export default function Sunum() {
  const { plan, n, meta, hazirBildir } = useUygulama();
  const harita = useRef<HaritaApi>(null);
  const cagri = useRef<CagrilarApi>(null);

  const [boyut, setBoyut] = useState<Boyut>(() => ({
    width: typeof window === 'undefined' ? 1920 : window.innerWidth,
    height: typeof window === 'undefined' ? 1080 : window.innerHeight,
  }));

  const ilk = useMemo(() => urlOku(), []);
  const yon = useYonetmen({
    sahneler: SAHNELER,
    plan,
    ilkSahne: ilk.sahne,
    ilkAdim: ilk.adim,
    ilkFilm: ilk.film,
  });
  const sahne = SAHNELER[yon.sahne - 1] ?? SAHNELER[0];

  const durum = useMemo<SahneDurumu>(
    () => ({ plan, meta, n, adim: yon.adim, adimSayisi: yon.adimSayisi, film: yon.film, boyut }),
    [plan, meta, n, yon.adim, yon.adimSayisi, yon.film, boyut],
  );
  const durumRef = useRef(durum);
  durumRef.current = durum;

  /* ---------------------------------------------------------------- kumanda */
  useTuslar({
    ileri: yon.ileri,
    geri: yon.geri,
    git: yon.git,
    basa: yon.basa,
    sona: yon.sona,
    filmDegistir: yon.filmDegistir,
    sahneSayisi: yon.sahneSayisi,
  });
  useImlecGizle(2000);

  /* ---------------------------------------------------------------- sözleşme + adres */
  useEffect(() => {
    kontratGuncelle({
      mod: 'sunum',
      sahne: yon.sahne,
      sahneSayisi: yon.sahneSayisi,
      adim: yon.adim,
      adimSayisi: yon.adimSayisi,
      n,
      git: (s: number) => yon.git(s),
    });
    urlYaz({ sahne: yon.sahne, adim: yon.adim > 1 ? yon.adim : null, film: yon.film ? 1 : null });
  }, [yon.sahne, yon.adim, yon.adimSayisi, yon.sahneSayisi, yon.film, yon.git, n]);

  /* ---------------------------------------------------------------- kamera koreografisi */
  const adimAnahtari = `${yon.sahne}.${yon.adim}`;
  const kamera = useMemo(
    () => sahne.kamera?.(durumRef.current) ?? null,
    // adım/ sahne değişiminde yeniden hesaplanır (plan değişimi kamerayı bozmamalı)
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [adimAnahtari, sahne],
  );
  useKameraOynatici({
    haritaRef: harita,
    kamera,
    anahtar: adimAnahtari,
    durum,
    girisMs: sahne.girisMs,
    onMesgul: (m) => kontratGuncelle({ mesgul: m }),
  });

  /* ---------------------------------------------------------------- saatler */
  const adimSaati = useRef(adimSaatiOlustur());
  const anahtarRef = useRef(adimAnahtari);
  anahtarRef.current = adimAnahtari;
  const sahneRef = useRef(sahne);
  sahneRef.current = sahne;

  const tHtml = useYavasSaat(!!sahne.htmlSaati, adimAnahtari, sahne.htmlSaatiBitis);

  const baglam: SahneBaglami = { ...durum, t: tHtml };
  const cagrilar = sahne.cagrilar?.(durum) ?? BOS_CAGRI;

  const ilkKamera = useMemo<Partial<KameraDurumu>>(() => {
    const b = SAHNELER[(ilk.sahne ?? 1) - 1]?.kamera?.({
      plan,
      meta,
      n,
      adim: ilk.adim ?? 1,
      adimSayisi: 1,
      film: false,
      boyut,
    })?.bas;
    return typeof b === 'object' && b ? b : KAMERA.bursa;
    // yalnız ilk kurulumda
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const SahneKatmani = sahne.Katman;

  return (
    <HaritaSahnesi
      ref={harita}
      katmanlar={(kureselT) =>
        sahneRef.current.katmanlar({ ...durumRef.current, t: adimSaati.current(anahtarRef.current, kureselT) })
      }
      baslangicKamera={ilkKamera}
      etkilesim={false}
      isik="gece"
      onIlkKare={hazirBildir}
      onKameraDegisti={() => cagri.current?.yerlestir()}
      onBoyut={setBoyut}
    >
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        {/* okunabilirlik perdesi: alt ve sol kenar koyulaşır, manşet her zaman okunur kalır */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(to top, rgba(3,6,13,0.86) 0%, rgba(3,6,13,0.45) 16%, rgba(3,6,13,0) 38%),' +
              'linear-gradient(to right, rgba(3,6,13,0.62) 0%, rgba(3,6,13,0.18) 18%, rgba(3,6,13,0) 34%)',
          }}
        />

        {/* sahneye özel HTML — sahne değişince yeniden belirir */}
        <div key={sahne.id} className="s-soluk" style={{ position: 'absolute', inset: 0 }}>
          {SahneKatmani ? <SahneKatmani b={baglam} /> : null}
        </div>

        <Cagrilar ref={cagri} noktalar={cagrilar} haritaRef={harita} />

        {/* sabit çerçeve */}
        <Marka alt={meta.hitap} style={{ position: 'absolute', left: u(72), top: u(44) }} />
        <Noktalar
          sahne={yon.sahne}
          sahneSayisi={yon.sahneSayisi}
          adim={yon.adim}
          adimSayisi={yon.adimSayisi}
          film={yon.film}
          filmOran={yon.filmOran}
          adlar={SAHNELER.map((s) => s.ad)}
        />
        <KaynakNotu
          ek={`${meta.organizasyon_kisa} · ${meta.kaynaklar.bina.split('(')[0].trim()}`}
          style={{ position: 'absolute', right: u(72), bottom: u(bosluk.m), fontSize: u(boy.not) }}
        />
      </div>
    </HaritaSahnesi>
  );
}
