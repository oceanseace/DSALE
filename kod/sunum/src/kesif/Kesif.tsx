/**
 * Keşif modu — konuşma sonrası soru-cevap için etkileşimli 3B harita.
 *
 * Yerleşim (1920×1080 tasarım pikseli, 1366×768'de birebir küçülür):
 *   üst çubuk 112  ·  sol sütun 432 (bölge listesi + katmanlar)
 *   sağ sütun 500 (seçim kartı + bölge çekmecesi)  ·  metrik lejantı haritada yüzer
 *
 * Test kancası (ARCHITECTURE.md §5'in Keşif eki):
 *   window.__DSALE__.kesif = { mesgul, bolgeSec, ara, aramaSec, binaSec, boyut, katman, durum }
 * Adres parametreleri: ?bolge ?ara ?bina ?gorunum=2b ?renk ?katman
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import type { PickingInfo } from '@deck.gl/core';

import { kontratGuncelle } from '../core/kontrat';
import { tamEkranDegistir } from '../core/platform';
import { urlYaz } from '../core/url';
import { useUygulama } from '../core/uygulama';
import { veri } from '../data/load';
import { bolgeBul, bolgeSinirKutusu, sayi, tumSinirKutusu, yuzde } from '../data/selectors';
import HaritaSahnesi, { type HaritaApi } from '../map/HaritaSahnesi';
import { fitBounds, KAMERA } from '../map/kamera';
import { karoErisimi } from '../map/katmanlar';
import KaynakNotu from '../ui/KaynakNotu';
import { boy, renk, u } from '../ui/tema';

import { ara as araDizinde, binaCoz, dizinHazirla, type AramaSonucu } from './arama';
import BinaKarti from './BinaKarti';
import BolgeCekmecesi from './BolgeCekmecesi';
import { indirge, urldenBaslangic, type Baslangic, type KesifDurumu, type Secim } from './durum';
import Ipucu from './Ipucu';
import { ipucuYaz } from './ipucuDeposu';
import { kesifKatmanlari } from './katmanKur';
import { binaKutusu, OLCU, uiBosluk } from './kameraHedefleri';
import KatmanKarti from './KatmanKarti';
import MetrikLejant from './MetrikLejant';
import SolPanel from './SolPanel';
import UstBar from './UstBar';

import './kesif.css';

const UCUS_MS = 1500;

export default function Kesif() {
  const { plan, n, setN, setMod, planAc, hazirBildir } = useUygulama();
  const meta = veri().meta;

  const ilkRef = useRef<Baslangic | null>(null);
  if (!ilkRef.current) ilkRef.current = urldenBaslangic();
  const ilk = ilkRef.current;

  const [durum, gonder] = useReducer(indirge, ilk.durum);
  const durumRef = useRef<KesifDurumu>(durum);
  durumRef.current = durum;

  const harita = useRef<HaritaApi>(null);
  const aramaGirdisi = useRef<HTMLInputElement>(null);

  /* ---------------------------------------------------------------- meşgul bayrağı (QA) */
  const kanca = useRef<Record<string, unknown>>({ mesgul: false });
  const haritaMesgul = useRef(false);
  const isMesgul = useRef(false);
  const mesgulYaz = useCallback(() => {
    kanca.current.mesgul = haritaMesgul.current || isMesgul.current;
  }, []);

  /* ---------------------------------------------------------------- CARTO karo yoklaması */
  // Çevrimiçiyse CARTO karoları OSM altlığının ALTINA eklenir; çevrimdışıysa sessizce atlanır.
  const [karo, setKaro] = useState(false);
  useEffect(() => {
    let iptal = false;
    void karoErisimi().then((tamam) => {
      if (!iptal) setKaro(tamam);
    });
    return () => {
      iptal = true;
    };
  }, []);

  /* ---------------------------------------------------------------- 3B ↔ 2B yükseklik geçişi */
  const [yukseklik, setYukseklik] = useState(ilk.durum.gorunum === '2b' ? 0.02 : 1);
  const yukseklikRef = useRef(yukseklik);
  yukseklikRef.current = yukseklik;

  useEffect(() => {
    const hedef = durum.gorunum === '2b' ? 0.02 : 1;
    const bas = yukseklikRef.current;
    if (Math.abs(bas - hedef) < 0.001) return;
    isMesgul.current = true;
    mesgulYaz();
    const t0 = performance.now();
    let raf = 0;
    const kare = (simdi: number) => {
      const t = Math.min(1, (simdi - t0) / 700);
      const y = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // easeInOutQuad
      setYukseklik(bas + (hedef - bas) * y);
      if (t < 1) raf = requestAnimationFrame(kare);
      else {
        isMesgul.current = false;
        mesgulYaz();
      }
    };
    raf = requestAnimationFrame(kare);
    return () => {
      cancelAnimationFrame(raf);
      isMesgul.current = false;
      mesgulYaz();
    };
  }, [durum.gorunum, mesgulYaz]);

  // kamera: 2B'de kuşbakışı, 3B'de eğik
  const ilkGorunum = useRef(durum.gorunum);
  useEffect(() => {
    if (ilkGorunum.current === durum.gorunum) return;
    ilkGorunum.current = durum.gorunum;
    const h = harita.current;
    if (!h) return;
    void h.flyTo(durum.gorunum === '2b' ? { pitch: 0, bearing: 0 } : { pitch: 50 }, 700, { tur: 'linear' });
  }, [durum.gorunum]);

  /* ---------------------------------------------------------------- kamera hareketleri */
  const bolgeUcus = useCallback(
    (no: number, sureMs = UCUS_MS) => {
      const h = harita.current;
      if (!h) return Promise.resolve(false);
      return h.fitBounds(bolgeSinirKutusu(plan, [no]), {
        padding: uiBosluk(true),
        pitch: durumRef.current.gorunum === '2b' ? 0 : 50,
        sureMs,
      });
    },
    [plan],
  );

  const binaUcus = useCallback((i: number, sureMs = UCUS_MS) => {
    const h = harita.current;
    if (!h) return Promise.resolve(false);
    const b = veri().binalar;
    return h.flyTo(
      {
        longitude: b.lon[i],
        latitude: b.lat[i],
        zoom: 16.2,
        pitch: durumRef.current.gorunum === '2b' ? 0 : 58,
      },
      sureMs,
    );
  }, []);

  const bolgeSec = useCallback(
    (no: number | null, sureMs = UCUS_MS) => {
      gonder({ tur: 'bolge', no });
      if (no == null) {
        void harita.current?.fitBounds(tumSinirKutusu(), {
          padding: uiBosluk(false),
          pitch: durumRef.current.gorunum === '2b' ? 0 : 45,
          bearing: durumRef.current.gorunum === '2b' ? 0 : -12,
          sureMs,
        });
        return;
      }
      void bolgeUcus(no, sureMs);
    },
    [bolgeUcus],
  );

  const binaSec = useCallback(
    (i: number, sureMs = UCUS_MS) => {
      gonder({ tur: 'secim', deger: { tur: 'bina', i } });
      void binaUcus(i, sureMs);
    },
    [binaUcus],
  );

  const basaDon = useCallback(() => {
    gonder({ tur: 'sifirla' });
    ipucuYaz(null);
    void harita.current?.fitBounds(tumSinirKutusu(), {
      padding: uiBosluk(false),
      pitch: durumRef.current.gorunum === '2b' ? 0 : 45,
      bearing: durumRef.current.gorunum === '2b' ? 0 : -12,
      sureMs: UCUS_MS,
    });
  }, []);

  const sonucSec = useCallback(
    (s: AramaSonucu, sureMs = UCUS_MS) => {
      gonder({ tur: 'aramaAcik', acik: false });
      if (s.tur === 'bina' || s.indeksler.length <= 1) {
        binaSec(s.ilkIndeks, sureMs);
        return;
      }
      const secim: Secim = {
        tur: 'grup',
        baslik: s.ad,
        alt: s.yer,
        tip: s.tur === 'mahalle' ? 'mahalle' : 'site',
        indeksler: s.indeksler,
      };
      gonder({ tur: 'secim', deger: secim });
      void harita.current?.fitBounds(binaKutusu(s.indeksler), {
        padding: uiBosluk(true),
        pitch: durumRef.current.gorunum === '2b' ? 0 : 52,
        maksZoom: 16.2,
        sureMs,
      });
    },
    [binaSec],
  );

  /* ---------------------------------------------------------------- ilk kare + adres parametreleri */
  const ilkKamera = useMemo(
    () =>
      typeof window === 'undefined'
        ? KAMERA.genelEgik
        : fitBounds(tumSinirKutusu(), {
            width: window.innerWidth,
            height: window.innerHeight,
            padding: uiBosluk(false),
            pitch: ilk.durum.gorunum === '2b' ? 0 : 45,
            bearing: ilk.durum.gorunum === '2b' ? 0 : -12,
          }),
    [ilk.durum.gorunum],
  );

  const ilkKare = useCallback(() => {
    const isVar = ilk.bolge != null || !!ilk.bina || !!ilk.ara;
    if (isVar) {
      isMesgul.current = true;
      mesgulYaz();
    }
    hazirBildir();
    if (!isVar) return;
    window.setTimeout(() => {
      void (async () => {
        try {
          if (ilk.ara) dizinHazirla();
          if (ilk.bina) {
            const i = binaCoz(ilk.bina);
            if (i != null) {
              gonder({ tur: 'secim', deger: { tur: 'bina', i } });
              await binaUcus(i, 900);
            }
          } else if (ilk.bolge != null && plan.bolgeler.some((b) => b.bolge === ilk.bolge)) {
            gonder({ tur: 'bolge', no: ilk.bolge });
            await bolgeUcus(ilk.bolge, 900);
          }
        } finally {
          isMesgul.current = false;
          mesgulYaz();
        }
      })();
    }, 80);
    // yalnız ilk karede çalışır
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------------------------------------------------------------- sözleşme + QA kancası */
  useEffect(() => {
    const k = kanca.current;
    k.bolgeSec = (no: unknown) => bolgeSec(no == null ? null : Number(no));
    k.ara = (metin: unknown) => {
      dizinHazirla();
      gonder({ tur: 'arama', metin: String(metin ?? ''), acik: true });
    };
    k.aramaSec = (sira: unknown) => {
      const liste = araDizinde(durumRef.current.arama, 8);
      const s = liste[Number(sira ?? 0)] ?? liste[0];
      if (s) sonucSec(s);
    };
    k.binaSec = (x: unknown) => {
      const i = typeof x === 'number' ? x : binaCoz(String(x));
      if (i != null) binaSec(i);
    };
    k.boyut = (g: unknown) => gonder({ tur: 'gorunum', deger: String(g) === '2b' ? '2b' : '3b' });
    k.katman = (ad: unknown, acik: unknown) =>
      gonder({ tur: 'katman', ad: String(ad) as never, acik: acik == null ? undefined : !!acik });
    k.durum = () => durumRef.current;
    k.basaDon = () => basaDon();
  }, [bolgeSec, binaSec, sonucSec, basaDon]);

  useEffect(() => {
    kontratGuncelle({
      mod: 'kesif',
      sahne: 1,
      sahneSayisi: 1,
      adim: 1,
      adimSayisi: 1,
      n,
      git: () => {},
      kesif: kanca.current,
    });
  }, [n]);

  /* ---------------------------------------------------------------- adres çubuğu */
  useEffect(() => {
    urlYaz({
      bolge: durum.secBolge,
      gorunum: durum.gorunum === '2b' ? '2b' : null,
      renk: durum.metrik === 'bolge' ? null : durum.metrik,
      ara: durum.arama || null,
      bina: durum.secim?.tur === 'bina' ? veri().binalar.paket.serial[durum.secim.i] : null,
    });
  }, [durum.secBolge, durum.gorunum, durum.metrik, durum.arama, durum.secim]);

  /* ---------------------------------------------------------------- klavye */
  useEffect(() => {
    const tus = (e: KeyboardEvent) => {
      const hedef = e.target as HTMLElement | null;
      if (hedef && /^(INPUT|TEXTAREA|SELECT)$/.test(hedef.tagName)) return;
      if (e.key === '/' || (e.ctrlKey && e.key.toLowerCase() === 'f')) {
        e.preventDefault();
        dizinHazirla();
        aramaGirdisi.current?.focus();
        return;
      }
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      const d = durumRef.current;
      if (e.key === 'Escape') {
        e.preventDefault();
        if (d.secim) gonder({ tur: 'secim', deger: null });
        else if (d.arama || d.aramaAcik) gonder({ tur: 'arama', metin: '', acik: false });
        else if (d.secBolge != null) bolgeSec(null);
      } else if (e.key === '2') {
        gonder({ tur: 'gorunum', deger: '2b' });
      } else if (e.key === '3') {
        gonder({ tur: 'gorunum', deger: '3b' });
      } else if (e.key === 'Home') {
        e.preventDefault();
        basaDon();
      } else if (e.key.toLocaleLowerCase('tr-TR') === 'f' && !e.shiftKey) {
        e.preventDefault();
        tamEkranDegistir();
      }
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [basaDon, bolgeSec]);

  /* ---------------------------------------------------------------- harita etkileşimi */
  const uzerinde = useCallback((bilgi: PickingInfo) => {
    if (bilgi.layer?.id === 'binalar' && bilgi.index != null && bilgi.index >= 0) ipucuYaz(bilgi.index, bilgi.x, bilgi.y);
    else ipucuYaz(null);
  }, []);

  const tikla = useCallback(
    (bilgi: PickingInfo) => {
      if (bilgi.layer?.id === 'binalar' && bilgi.index != null && bilgi.index >= 0) binaSec(bilgi.index);
      else gonder({ tur: 'secim', deger: null });
    },
    [binaSec],
  );

  const kontrolcu = useMemo(
    () =>
      durum.gorunum === '2b'
        ? { dragRotate: false, touchRotate: false, inertia: 300 }
        : { dragRotate: true, touchRotate: true, inertia: 300, maxPitch: 70 },
    [durum.gorunum],
  );

  const secimIndeksleri = useMemo(
    () => (durum.secim ? (durum.secim.tur === 'bina' ? [durum.secim.i] : durum.secim.indeksler) : null),
    [durum.secim],
  );

  const katmanListesi = useMemo(
    () => kesifKatmanlari({ plan, durum: durumRef.current, yukseklikOlcegi: yukseklik, karo, secimIndeksleri }),
    // durum'un yalnız çizimi etkileyen alanları:
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [plan, durum.secBolge, durum.metrik, durum.katman, durum.gorunum, yukseklik, karo, secimIndeksleri],
  );

  const secBolgeNesnesi = durum.secBolge != null ? bolgeBul(plan, durum.secBolge) : undefined;
  const sagAcik = !!durum.secim || !!secBolgeNesnesi;
  const toplam = meta.toplam;

  return (
    <HaritaSahnesi
      ref={harita}
      katmanlar={katmanListesi}
      baslangicKamera={ilkKamera}
      etkilesim={kontrolcu}
      isik="gece"
      pickingRadius={5}
      onHover={uzerinde}
      onClick={tikla}
      getCursor={({ isHovering, isDragging }) => (isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab')}
      onIlkKare={ilkKare}
      onMesgul={(m) => {
        haritaMesgul.current = m;
        mesgulYaz();
        kontratGuncelle({ mesgul: m });
      }}
    >
      <div className="ks-kok">
        <UstBar
          ref={aramaGirdisi}
          plan={plan}
          n={n}
          metrik={durum.metrik}
          gorunum={durum.gorunum}
          arama={durum.arama}
          aramaAcik={durum.aramaAcik}
          onN={setN}
          onMetrik={(m) => gonder({ tur: 'metrik', deger: m })}
          onGorunum={(g) => gonder({ tur: 'gorunum', deger: g })}
          onArama={(metin) => gonder({ tur: 'arama', metin })}
          onAramaAcik={(acik) => gonder({ tur: 'aramaAcik', acik })}
          onAramaSec={(s) => sonucSec(s)}
          onBasaDon={basaDon}
          onPlanAc={() => void planAc()}
          onTamEkran={tamEkranDegistir}
          onSunum={() => setMod('sunum')}
        />

        {/* sol sütun */}
        <div
          style={{
            position: 'absolute',
            left: u(OLCU.kenar),
            top: u(OLCU.ustCubuk + 16),
            bottom: u(OLCU.kenar),
            width: u(OLCU.solGenislik),
            display: 'flex',
            flexDirection: 'column',
            gap: u(12),
            pointerEvents: 'none',
          }}
        >
          <div style={{ pointerEvents: 'auto', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <SolPanel
              plan={plan}
              secBolge={durum.secBolge}
              onSec={(no) => bolgeSec(durum.secBolge === no ? null : no)}
              onTumu={() => bolgeSec(null)}
              metrik={durum.metrik}
            />
          </div>
          <div style={{ pointerEvents: 'auto' }}>
            <KatmanKarti katman={durum.katman} onDegis={(ad) => gonder({ tur: 'katman', ad })} />
          </div>
          {/* kaynak satırı da cam panelin içinde: çıplak haritanın üstünde yüzmesin */}
          <div
            className="ks-cam"
            style={{
              pointerEvents: 'auto',
              padding: `${u(10)} ${u(14)}`,
              fontSize: u(boy.not),
              color: renk.metin3,
              lineHeight: 1.5,
            }}
          >
            <div style={{ color: renk.metin2, fontVariantNumeric: 'tabular-nums' }}>
              {sayi(toplam.bina)} bina · {sayi(toplam.res_hp)} RES HP · penetrasyon {yuzde(meta.penetrasyon)}
            </div>
            <KaynakNotu />
          </div>
        </div>

        {/* metrik lejantı — haritanın sol altında yüzer (sol sütunu daraltmasın) */}
        {durum.metrik !== 'bolge' && (
          <div
            style={{
              position: 'absolute',
              left: u(OLCU.kenar + OLCU.solGenislik + 24),
              bottom: u(OLCU.kenar),
              width: u(400),
            }}
          >
            <MetrikLejant metrik={durum.metrik} />
          </div>
        )}

        {/* sağ sütun: seçim kartı + bölge çekmecesi */}
        {sagAcik && (
          <div
            style={{
              position: 'absolute',
              right: u(OLCU.kenar),
              top: u(OLCU.ustCubuk + 16),
              bottom: u(OLCU.kenar),
              width: u(OLCU.sagGenislik),
              display: 'flex',
              flexDirection: 'column',
              gap: u(12),
              pointerEvents: 'none',
            }}
          >
            {durum.secim && (
              <div style={{ pointerEvents: 'auto' }}>
                <BinaKarti
                  plan={plan}
                  secim={durum.secim}
                  onKapat={() => gonder({ tur: 'secim', deger: null })}
                  onBolgeyeGit={(no) => bolgeSec(no)}
                />
              </div>
            )}
            {secBolgeNesnesi && (
              <div style={{ pointerEvents: 'auto', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                <BolgeCekmecesi bolge={secBolgeNesnesi} hedef={plan.hedef} onKapat={() => bolgeSec(null)} />
              </div>
            )}
          </div>
        )}

        <Ipucu plan={plan} sagPanelAcik={sagAcik} />
      </div>
    </HaritaSahnesi>
  );
}
