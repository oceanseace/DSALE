/**
 * Operasyon ▸ MAP (menü bölüm anahtarı 'is-haritasi'): bütün AÇIK işler bina koordinatında, tam ekran.
 *   Nokta renkleri: gri randevusuz · sarı randevulu · mavi ekip yolda/sahada · mor askıda/merkeze/altyapı.
 *   Noktaya basınca İş çekmecesi haritanın üstünde açılır (veri TASKS ile aynı biçimde, `ek` alanlarıyla; görünürken
 *   15 sn'de bir, pencereye dönünce ve ⟳ ile hemen tazelenir; atama/askıdan sonra nokta BOSS'u beklemeden boyanır).
 *   Tek arama kutusu (Task No, müşteri no, ad, Location ID, BN/bina) bulunan yere uçar ve vurgular.
 *   Süzgeçler TASKS ile ORTAK (tercihDeposu.ts): ince şeritte etkin çipler + "Filtreler" çekmecesi (map/MapSuzgec.tsx:
 *   Ara · Özel filtre · Geliş tarihi · İş türü · bütün sütun süzgeçleri). Lejant köşede küçük; "Gösterilen N / toplam".
 *   Kişisel Ayarlar (Kabuk ▸ Ayarlar, sunucuda): durum sayaç çubuğu (üst sağ), lejant, otomatik tazeleme aralığı.
 *   Esc: önce Kement/Dikdörtgen aracından çıkar (MapTuval), ikinci Esc seçimi temizler.
 *   Toplu atama (is.ata): Kement / Dikdörtgen aracı (Shift ekler, Alt çıkarır), Shift+tık ile noktalar seçilir; "N seçili · Ata… · Temizle"
 *   çipi TopluAtaPaneli'ni açar (TASKS'takiyle aynı); "Askıya al…" (is.duzenle) TopluAskiPaneli'ni. Esc seçimi temizler.
 *   "Ekipler" (alt panel, cihazda hatırlanır, varsayılan kapalı): BOSS GPS Takip'ten ekiplerin son konumu, ad + "14:32 ·
 *   5 dk önce" etiketiyle; 30 dk'dan eskisi soluk; açıkken 60 sn'de bir yoklanır (map/ekipKatmani.ts). Eklenti GPS
 *   yanıtını hiç yakalamadıysa ipucu: BOSS'ta GPS Takip sayfasını bir kez açın.
 * Giriş: IsHaritasiEkrani (Konsol.tsx bağlar). Parçalar map/ altında: MapTuval (deck.gl çizim), KonumAra
 * (arama + seçim kartı), tarihSuzgeci, noktalar (renk ve nokta), noktaGecisi (solma/nabız).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { HataKutusu } from '../../../cekirdek/ortak/Bos';
import { Dugme } from '../../../cekirdek/ortak/Ilkel';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import { useKisiAyarlari } from '../../../cekirdek/ortak/kisiAyarlari';
import { TopluAskiPaneli } from './TopluAski';
import { TopluAtaPaneli } from './TopluAta';
import { IslerSaglayici, useIsler } from './durum';
import { IsCekmecesi } from './IsCekmecesi';
import { metinUyar, turUyar, useOrtakSuzgec } from './isTuru';
import { useGorunumler } from './Gorunumler';
import { useSutunlar } from './sutunlar';
import { useSutunDuzeni } from './sutunDuzeni';
import { useTabloSuzgec } from './tabloSuzgec';
import { MapFiltreCekmecesi, MapSuzgecCubugu, useEtkinCipler } from './map/MapSuzgec';
import { Yenile } from '../../../cekirdek/ortak/Ikon';
import { gunAnahtari } from './parcalar';
import { BOS_SAYIM, KAPALI_DURUM, KATLAR, yerelTemizle, type Kat } from './map/noktalar';
import { bossEsitleIste } from '../../../cekirdek/is/api';
import { renkEtiketi, renkIpucu, useDurumRenkSurumu } from '../../../cekirdek/is/durumRenk';
import { useNoktaGecisi } from './map/noktaGecisi';
import { MapTuval, type SecimKipi, type Vurgu } from './map/MapTuval';
import { KonumAra } from './map/KonumAra';
import { ekipKatmanlari, useEkipKonumlari } from './map/ekipKatmani';
import { useKaliciSecim } from '../../../cekirdek/harita/tercih';
import type { Bulunan } from './map/konumArama';
import { tarihUyari, useTarihSuzgeci } from './map/tarihSuzgeci';
import './isler.css';
import './map/map.css';


export function IsHaritasiEkrani() {
  return (
    <IslerSaglayici ek>
      <MapIc />
    </IslerSaglayici>
  );
}

function MapIc() {
  const depo = useIsler();
  const ayar = useKisiAyarlari();
  const ortak = useOrtakSuzgec();
  const gorunum = useGorunumler();
  const [tarih, setTarih] = useTarihSuzgeci();
  const [secili, setSecili] = useState<string | null>(null);
  const [bulunan, setBulunan] = useState<Bulunan | null>(null);
  const [vurgu, setVurgu] = useState<Vurgu | null>(null);
  const vurguSayac = useRef(0);
  const [gizli, setGizli] = useState<Set<Kat>>(new Set());
  const [sonZaman, setSonZaman] = useState<Date | null>(null);
  const { izinli } = useOturum();
  const atayabilir = izinli('is.ata');
  const [secim, setSecim] = useState<Set<string>>(() => new Set());
  const [ekipKip, setEkipKip] = useKaliciSecim<'acik' | 'kapali'>('map-ekipler', 'kapali', ['acik', 'kapali']);
  const ekipAcik = ekipKip === 'acik';
  const ekipYanit = useEkipKonumlari(ekipAcik);
  const ekipKatman = useMemo(() => (ekipYanit ? ekipKatmanlari(ekipYanit.ekipler) : []), [ekipYanit]);
  const [ataAcik, setAtaAcik] = useState(false);
  const [askiAcik, setAskiAcik] = useState(false);
  const askiyaAlabilir = izinli('is.duzenle');
  const hata = depo.durum === 'hata' ? depo.hata : null;
  const yuklendi = depo.durum !== 'yukleniyor' || depo.isler.length > 0;
  const tazele = depo.tazele;
  const bugun = gunAnahtari(new Date(Date.now() + depo.sunucuFarkMs));

  /* Süzme zinciri (TASKS ile aynı): açık iş → Özel filtre → iş türü → geliş tarihi → arama → sütun süzgeçleri.
     Lejant renkleri ayrıca gizlenebilir. */
  const acikIsler = useMemo(() => depo.isler.filter((s) => !KAPALI_DURUM.has(s.durum)), [depo.isler]);
  const tarihUyar = useMemo(() => tarihUyari(tarih), [tarih]);
  const onSuzulen = useMemo(
    () =>
      acikIsler.filter(
        (s) => gorunum.uyar(s) && turUyar(s, ortak.tur) && tarihUyar(s.acilis) && metinUyar(s, ortak.arama),
      ),
    [acikIsler, gorunum.uyar, ortak.tur, tarihUyar, ortak.arama],
  );
  const sutunlar = useSutunlar(depo.meta?.ek_etiketler, depo.isler);
  const duzen = useSutunDuzeni(sutunlar);
  const tablo = useTabloSuzgec(onSuzulen, sutunlar, acikIsler);
  const suzulen = tablo.suzulen;
  const cipler = useEtkinCipler(gorunum, tablo, tarih, setTarih, bugun);
  const [filtreAcik, setFiltreAcik] = useState(false);
  const tumunuTemizle = useCallback(() => cipler.forEach((c) => c.kaldir()), [cipler]);
  /* Süzgeç değişince harita gösterilen noktalara sığar (veri tazelenince değil). */
  const sigdirmaIstegi = yuklendi ? cipler.map((c) => c.metin).join('|') + JSON.stringify(tablo.suzgec) : '';
  const renkSurumu = useDurumRenkSurumu();
  const { noktalar, sigdirmaAnahtari } = useNoktaGecisi(suzulen, sigdirmaIstegi, renkSurumu);

  useEffect(() => {
    if (depo.isler.length) setSonZaman(new Date());
  }, [depo.isler]);

  /* Görünürken Ayarlar'daki aralıkla (varsayılan 15 sn; 0 = kapalı); pencereye dönünce hemen. */
  const simdiYokla = depo.simdiYokla;
  const tazelemeMs = ayar.map_tazeleme_sn * 1000;
  useEffect(() => {
    const t = tazelemeMs
      ? window.setInterval(() => document.visibilityState === 'visible' && void simdiYokla(), tazelemeMs)
      : 0;
    const odak = () => void simdiYokla();
    window.addEventListener('focus', odak);
    return () => {
      window.clearInterval(t);
      window.removeEventListener('focus', odak);
    };
  }, [simdiYokla, tazelemeMs]);
  const [tazeleniyor, setTazeleniyor] = useState(false);
  /* ⟳: TAM tazeleme — iyimser renkler düşer, görünen bütün satırlar sunucudan yeniden okunur ve eklentiden hemen
     bir BOSS eşitlemesi istenir (BOSS'ta yapılan askı/randevu ~1 dk içinde değişim yoklamasıyla gelir). */
  const elleTazele = useCallback(async () => {
    setTazeleniyor(true);
    yerelTemizle();
    void bossEsitleIste().catch(() => undefined);
    try {
      await tazele();
    } finally {
      setTazeleniyor(false);
    }
  }, [tazele]);

  const sayilar = useMemo(() => {
    const m: Record<Kat, number> = BOS_SAYIM();
    noktalar.forEach((n) => !n.cikis && (m[n.kat] += 1));
    return m;
  }, [noktalar]);
  const renkDegistir = useCallback(
    (kat: Kat) =>
      setGizli((g) => {
        const y = new Set(g);
        if (y.has(kat)) y.delete(kat);
        else y.add(kat);
        return y;
      }),
    [],
  );
  const gorunen = useMemo(() => noktalar.filter((n) => !gizli.has(n.kat)), [noktalar, gizli]);
  const gorunenNo = useMemo(() => new Set(gorunen.filter((n) => !n.cikis).map((n) => n.no)), [gorunen]);
  const gizliMi = useCallback((no: string) => !gorunenNo.has(no), [gorunenNo]);
  const konumluToplam = useMemo(() => acikIsler.filter((s) => s.lat !== null && s.lon !== null).length, [acikIsler]);
  const konumsuz = useMemo(() => suzulen.filter((s) => s.lat === null || s.lon === null).length, [suzulen]);
  const suzgecVar = Boolean(cipler.length || gizli.size);

  /* Toplu seçim: yalnız hâlâ açık işler sayılır (kapanan kendiliğinden düşer). */
  const acikNo = useMemo(() => new Map(acikIsler.map((s) => [s.is_no, s])), [acikIsler]);
  const seciliSatirlar = useMemo(
    () => [...secim].map((n) => acikNo.get(n)).filter((s): s is NonNullable<typeof s> => Boolean(s)),
    [secim, acikNo],
  );
  const [ataSatirlari, setAtaSatirlari] = useState<typeof seciliSatirlar>([]);
  const secimDegisti = useCallback((nolar: string[], kip: SecimKipi) => {
    setSecim((o) => {
      const y = kip === 'yerine' ? new Set<string>() : new Set(o);
      for (const n of nolar) {
        if (kip === 'ekle' || kip === 'yerine') y.add(n);
        else if (kip === 'cikar') y.delete(n);
        else if (y.has(n)) y.delete(n);
        else y.add(n);
      }
      return y;
    });
  }, []);
  useEffect(() => {
    if (!secim.size) return undefined;
    const tus = (o: KeyboardEvent) => {
      if (o.key === 'Escape' && !secili && !ataAcik && !askiAcik) setSecim(new Set());
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [secim.size, secili, ataAcik, askiAcik]);

  const bul = (b: Bulunan) => {
    setBulunan(b);
    if (!b.konum) {
      setVurgu(null);
      return;
    }
    vurguSayac.current += 1;
    setVurgu({ konum: b.konum, isNo: b.tur === 'is' ? b.isNo : undefined, kimlik: vurguSayac.current });
  };
  const bulTemizle = () => {
    setBulunan(null);
    setVurgu(null);
  };

  return (
    <div className="ih-kok">
      <MapTuval
        noktalar={gorunen}
        sigdirmaAnahtari={sigdirmaAnahtari}
        sec={setSecili}
        vurgu={vurgu}
        secili={atayabilir ? secim : undefined}
        secimDegisti={atayabilir ? secimDegisti : undefined}
        ekKatmanlar={ekipKatman}
        ekDugmeler={
          <button
            type="button"
            className={`ie-sigdir${ekipAcik ? ' etkin' : ''}`}
            aria-pressed={ekipAcik}
            onClick={() => setEkipKip(ekipAcik ? 'kapali' : 'acik')}
            title="BOSS GPS Takip'ten ekiplerin son konumu (60 sn'de bir tazelenir; 30 dk'dan eskisi soluk)"
          >
            Ekipler{ekipAcik && ekipYanit?.ekipler.length ? ` ${ekipYanit.ekipler.length}` : ''}
          </button>
        }
      />
      {/* Sol sütun: başlık + arama (kart ve liste aşağı doğru uzar); sağ: süzgeçler ve lejant (sarar). */}
      <div className="ih-ust mp-ust">
        <div className="mp-sol">
          <div className="ih-kutu ih-baslik">
            <h1>MAP</h1>
            <span className="mp-sayac" aria-live="polite" title={suzgecVar ? 'Süzgeçlere uyan / konumu olan bütün açık işler' : undefined}>
              Gösterilen <b>{gorunenNo.size.toLocaleString('tr-TR')}</b> / {konumluToplam.toLocaleString('tr-TR')}
            </span>
            {konumsuz ? (
              <span className="mp-konumsuz" title="Bu işlerin bina koordinatı yok; haritada gösterilemiyor.">
                {konumsuz.toLocaleString('tr-TR')} konumsuz
              </span>
            ) : null}
            <span className="ih-zaman">
              {sonZaman ? sonZaman.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'yükleniyor…'}
            </span>
            <button
              type="button"
              className={`mp-tazele${tazeleniyor ? ' donuyor' : ''}`}
              title="Şimdi tazele"
              aria-label="Haritayı şimdi tazele"
              disabled={tazeleniyor}
              onClick={() => void elleTazele()}
            >
              <Yenile boyut={16} />
            </button>
          </div>
          {atayabilir && seciliSatirlar.length ? (
            <div className="ih-kutu mp-secim" role="status" aria-live="polite">
              <span>
                <b>{seciliSatirlar.length.toLocaleString('tr-TR')}</b> iş seçili
              </span>
              <Dugme
                tur="birincil"
                boy="kucuk"
                onClick={() => {
                  setAtaSatirlari(seciliSatirlar);
                  setAtaAcik(true);
                }}
              >
                Ata…
              </Dugme>
              {askiyaAlabilir ? (
                <Dugme
                  boy="kucuk"
                  onClick={() => {
                    setAtaSatirlari(seciliSatirlar);
                    setAskiAcik(true);
                  }}
                >
                  Askıya al…
                </Dugme>
              ) : null}
              <Dugme tur="metin" boy="kucuk" onClick={() => setSecim(new Set())}>
                Temizle
              </Dugme>
            </div>
          ) : null}
          {ekipAcik && ekipYanit && !ekipYanit.kaynak_goruldu ? (
            <div className="ih-kutu mp-ekip-ipucu" role="status">
              Ekip konumu henüz alınmadı: BOSS'ta GPS Takip (Operasyon ▸ GPS takip / teknik) sayfasını bir kez açın.
            </div>
          ) : ekipAcik && ekipYanit && !ekipYanit.ekipler.length ? (
            <div className="ih-kutu mp-ekip-ipucu" role="status">
              BOSS GPS yanıtında güncel ekip konumu yok
              {ekipYanit.son_alim ? ` (son alım ${ekipYanit.son_alim.slice(11, 16)})` : ''}.
            </div>
          ) : null}
          <KonumAra
            isler={acikIsler}
            harita={depo.harita}
            secim={bulunan}
            sec={bul}
            temizle={bulTemizle}
            isiAc={setSecili}
            gizliMi={gizliMi}
          />
        </div>
        <div className="mp-sag">
          <MapSuzgecCubugu cipler={cipler} ac={() => setFiltreAcik(true)} temizle={tumunuTemizle} />
          {ayar.map_durum_cubugu ? (
            <div className="ih-kutu ih-lejant mp-durum" role="group" aria-label="Durum sayıları (basınca gizle/göster)">
              {KATLAR.map((k) => (
                <button
                  key={k.kat}
                  type="button"
                  className={gizli.has(k.kat) ? 'kapali' : ''}
                  aria-pressed={!gizli.has(k.kat)}
                  title={`${renkIpucu(k.kat)} — basınca ${gizli.has(k.kat) ? 'göster' : 'gizle'}`}
                  onClick={() => renkDegistir(k.kat)}
                >
                  <i style={{ ['--r' as string]: `rgb(${k.renk.join(',')})` }} aria-hidden="true" />
                  {renkEtiketi(k.kat)} <b>{sayilar[k.kat].toLocaleString('tr-TR')}</b>
                </button>
              ))}
            </div>
          ) : null}
          {hata && !depo.isler.length ? (
            <div className="ih-kutu">
              <HataKutusu mesaj={hata} tekrar={() => void tazele()} />
            </div>
          ) : null}
        </div>
      </div>
      {/* Lejant: sağ alt köşede küçük; renge basınca gizle/göster (Ayarlar ▸ Renk lejantı). */}
      {ayar.map_lejant ? (
      <div className="ih-kutu ih-lejant mp-lejant" role="group" aria-label="Renkler (basınca gizle/göster)">
        {KATLAR.map((k) => (
          <button
            key={k.kat}
            type="button"
            className={gizli.has(k.kat) ? 'kapali' : ''}
            aria-pressed={!gizli.has(k.kat)}
            title={`${renkIpucu(k.kat)} — basınca ${gizli.has(k.kat) ? 'göster' : 'gizle'}`}
            onClick={() => renkDegistir(k.kat)}
          >
            <i style={{ ['--r' as string]: `rgb(${k.renk.join(',')})` }} aria-hidden="true" />
            {renkEtiketi(k.kat)} <b>{sayilar[k.kat].toLocaleString('tr-TR')}</b>
          </button>
        ))}
      </div>
      ) : null}
      <MapFiltreCekmecesi
        acik={filtreAcik && !secili}
        kapat={() => setFiltreAcik(false)}
        g={gorunum}
        t={tablo}
        sutunlar={sutunlar}
        oncelikli={duzen.gorunenIdler}
        tarih={tarih}
        setTarih={setTarih}
        bugun={bugun}
        isler={acikIsler}
        cipler={cipler}
        gosterilen={gorunenNo.size}
        toplam={konumluToplam}
        temizle={tumunuTemizle}
      />
      <IsCekmecesi isNo={secili} kapat={() => setSecili(null)} />
      <TopluAtaPaneli
        acik={ataAcik}
        kapat={() => setAtaAcik(false)}
        satirlar={ataSatirlari}
        bitti={() => setSecim(new Set())}
      />
      <TopluAskiPaneli
        acik={askiAcik}
        kapat={() => setAskiAcik(false)}
        satirlar={ataSatirlari}
        bitti={() => setSecim(new Set())}
      />
    </div>
  );
}
