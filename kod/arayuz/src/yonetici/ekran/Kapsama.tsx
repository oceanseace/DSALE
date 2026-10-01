/**
 * Kapsama haritası — "sudokunun kaç karesi doldu".
 *
 * En üstte tek cümle: 19.706 binanın kaçına dokunuldu, kaç boş kapı duruyor.
 * Altında bütün şehir tek haritada; bölge (yani satışçı) ve mahalle ile
 * süzülür. Sağdaki tablo aynı veriyi sayıyla verir; bir satıra tıklayınca
 * harita oraya odaklanır.
 */

import { useEffect, useMemo, useState } from 'react';
import { sayi, yuzde } from '../../ortak/bicim';
import { Yenile } from '../../ortak/Ikon';
import { binalar as binalarUcu, kapsama } from '../api';
import { useYonetim, satiscilar } from '../depo';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { bolgeNumaralari, useBolgeSayisi } from './bolge/bolgeSayisi';
import { HaritaTuval, type HaritaNoktasi } from '../ortak/HaritaTuval';
import { BinaAyrintiPenceresi } from '../ortak/BinaAyrinti';
import {
  HataKutusu,
  Iskelet,
  Kart,
  OranCubugu,
  Segment,
  useVeri,
} from '../ortak/parcalar';
import type { KapsamaSatiri } from '../tipler';

type Kirilim = 'bolge' | 'mahalle' | 'ilce';

export function Kapsama() {
  const { noktalar, haritaYukleniyor, haritaHatasi, haritayiIste, haritayiTazele, ekip } =
    useYonetim();
  const [bolge, setBolge] = useState<number | null>(null);
  const bolgeSayisi = useBolgeSayisi();
  const [mahalle, setMahalle] = useState<string>('');
  const [kirilim, setKirilim] = useState<Kirilim>('bolge');
  const [secili, setSecili] = useState<HaritaNoktasi | null>(null);
  const [ayrinti, setAyrinti] = useState<string | null>(null);

  useEffect(() => {
    haritayiIste();
  }, [haritayiIste]);

  const ekipListesi = satiscilar(ekip);
  const bolgeAdi = useMemo(() => {
    const harita = new Map<number, string>();
    ekipListesi.forEach((k) => {
      if (k.bolge) harita.set(k.bolge, k.ad);
    });
    return harita;
  }, [ekipListesi]);

  /* Mahalle kırılımı hem açılır listeyi hem de mahalle tablosunu besler. */
  const mahalleVeri = useVeri(() => kapsama('mahalle', bolge), [bolge]);
  const tabloVeri = useVeri(
    () => (kirilim === 'mahalle' ? Promise.resolve(null) : kapsama(kirilim, bolge)),
    [kirilim, bolge],
  );

  /* Mahalle süzgeci: o mahallenin bina numaraları (harita noktalarını ayıklamak için). */
  const mahalleBinalari = useVeri(
    () =>
      mahalle
        ? binalarUcu({ mahalle, bolge, limit: 1000 }).then(
            (y) => new Set(y.binalar.map((b) => b.bina_serial)),
          )
        : Promise.resolve(null),
    [mahalle, bolge],
  );

  const suzulmus = useMemo<HaritaNoktasi[]>(() => {
    let liste = noktalar ?? [];
    if (bolge != null) liste = liste.filter((n) => n.bolge === bolge);
    if (mahalle && mahalleBinalari.veri) {
      const kume = mahalleBinalari.veri;
      liste = liste.filter((n) => kume.has(n.serial));
    }
    return liste;
  }, [noktalar, bolge, mahalle, mahalleBinalari.veri]);

  /* Manşet: süzgeç neredeyse o kapsama okunur. */
  const manset = useMemo(() => {
    if (mahalle) {
      const satir = mahalleVeri.veri?.satirlar.find((s) => s.ad === mahalle);
      if (satir) return { ...satir, baslik: `${mahalle} mahallesi` };
    }
    const kaynak = mahalleVeri.veri;
    if (!kaynak) return null;
    return {
      ad: '',
      toplam: kaynak.toplam,
      dokunulan: kaynak.dokunulan,
      temas: kaynak.temas,
      dokunulmayan_firsat: kaynak.dokunulmayan_firsat,
      satis_bina: kaynak.satis_bina,
      kalan: kaynak.kalan,
      oran: kaynak.oran,
      firsat: kaynak.firsat,
      kalan_firsat: kaynak.kalan_firsat,
      satis: kaynak.satis,
      baslik: bolge ? `${bolge}. bölge` : 'Bursa geneli',
    };
  }, [mahalle, mahalleVeri.veri, bolge]);

  const tabloSatirlari: KapsamaSatiri[] =
    (kirilim === 'mahalle' ? mahalleVeri.veri?.satirlar : tabloVeri.veri?.satirlar) ?? [];
  const tabloYukleniyor = kirilim === 'mahalle' ? mahalleVeri.yukleniyor : tabloVeri.yukleniyor;

  /** Tablo satırının adı: bölgede iki satır (numara + satışçı), ötekilerde tek. */
  const satirBasligi = (satir: KapsamaSatiri): [string, string | null] => {
    if (kirilim !== 'bolge') return [String(satir.ad), null];
    const no = Number(satir.ad);
    return [`${no}. bölge`, bolgeAdi.get(no) ?? null];
  };

  const satiraTikla = (satir: KapsamaSatiri) => {
    if (kirilim === 'bolge') {
      const no = Number(satir.ad);
      setBolge(Number.isFinite(no) ? no : null);
      setMahalle('');
      setKirilim('mahalle');
    } else if (kirilim === 'mahalle') {
      setMahalle((o) => (o === satir.ad ? '' : String(satir.ad)));
    }
  };

  const temizle = () => {
    setBolge(null);
    setMahalle('');
    setKirilim('bolge');
  };

  const suzgecVar = bolge != null || mahalle !== '';

  return (
    <>
      <YonUst
        baslik="Kapsama haritası"
        altYazi="Yeşil = dokunulan bina · gri = hiç gidilmemiş · sarı = tekrar gidilecek"
      >
        <select
          className="yon-alan"
          style={{ width: 210 }}
          value={bolge ?? ''}
          onChange={(o) => {
            const d = o.target.value;
            setBolge(d === '' ? null : Number(d));
            setMahalle('');
            setKirilim(d === '' ? 'bolge' : 'mahalle');
          }}
          aria-label="Bölge süzgeci"
        >
          <option value="">Bütün bölgeler</option>
          {bolgeNumaralari(bolgeSayisi).map((b) => (
            <option key={b} value={b}>
              {b}. bölge{bolgeAdi.get(b) ? ` · ${bolgeAdi.get(b)}` : ''}
            </option>
          ))}
        </select>

        <select
          className="yon-alan"
          style={{ width: 200 }}
          value={mahalle}
          onChange={(o) => setMahalle(o.target.value)}
          aria-label="Mahalle süzgeci"
        >
          <option value="">Bütün mahalleler</option>
          {(mahalleVeri.veri?.satirlar ?? [])
            .slice()
            .sort((a, b) => String(a.ad).localeCompare(String(b.ad), 'tr'))
            .map((s) => (
              <option key={s.ad} value={s.ad}>
                {s.ad}
              </option>
            ))}
        </select>

        {suzgecVar ? (
          <button className="yd duz" onClick={temizle}>
            Süzgeci temizle
          </button>
        ) : null}

        <button className="yd" onClick={haritayiTazele} disabled={haritaYukleniyor}>
          <Yenile boyut={18} />
          Yenile
        </button>
      </YonUst>

      <Icerik>
        {haritaHatasi ? <HataKutusu mesaj={haritaHatasi} yenile={haritayiTazele} /> : null}

        {manset ? (
          <div className="yon-manset">
            <div>
              <div className="buyuk">
                {sayi(manset.toplam)} binanın <em>{sayi(manset.dokunulan)}</em>’ine gidildi
              </div>
              {/* "Gidildi" ile "görüşüldü" ayrı şeyler: girilemedi/altyapı
                  sonuçlarında binaya gidilmiş ama kimseyle konuşulmamıştır.
                  Manşet cümlenin dürüst olması ikna gücünün tamamı. */}
              <div className="aciklama">
                {manset.temas != null ? `${sayi(manset.temas)} binada görüşüldü · ` : ''}
                {sayi(manset.kalan)} bina hâlâ bekliyor · {manset.baslik}
              </div>
            </div>

            <div className="cubuk">
              <div className="yol">
                <span style={{ width: `${Math.max(1, Math.round(manset.oran * 100))}%` }} />
              </div>
              <div className="alt">
                <span>{yuzde(manset.oran, 1)} tamamlandı</span>
                <span>%100</span>
              </div>
            </div>

            <div className="ayrac" />

            <div className="yan">
              <div className="deger">{sayi(manset.kalan_firsat)}</div>
              <div className="etiket">SATILMAMIŞ BOŞ KAPI</div>
            </div>

            {manset.dokunulmayan_firsat != null ? (
              <div className="yan">
                <div className="deger">{sayi(manset.dokunulmayan_firsat)}</div>
                <div className="etiket">HİÇ GİDİLMEYEN BİNADAKİ KAPI</div>
              </div>
            ) : null}

            <div className="yan">
              <div className="deger">{sayi(manset.satis)}</div>
              <div className="etiket">SATILAN ABONELİK</div>
            </div>
          </div>
        ) : (
          <Iskelet yukseklik={110} />
        )}

        <div className="yon-ikili">
          <Kart
            baslik={mahalle || (bolge ? `${bolge}. bölge` : 'Bursa · bütün bölgeler')}
            altYazi={
              haritaYukleniyor && !noktalar
                ? '19.706 bina yükleniyor…'
                : `${sayi(suzulmus.length)} bina gösteriliyor`
            }
          >
            <HaritaTuval
              noktalar={suzulmus}
              yukseklik={520}
              noktaSecildi={setSecili}
              secili={secili}
              sigdirmaAnahtari={`${bolge ?? 'hepsi'}-${mahalle}-${suzulmus.length}`}
              kart={
                secili ? (
                  <div className="yon-harita-kart">
                    <div className="ad" title={secili.ad || secili.serial}>
                      {secili.ad || secili.serial}
                    </div>
                    {secili.loc ? <div className="loc">{secili.loc}</div> : null}
                    <div className="alt">
                      {DURUM_METNI[secili.durum] ?? secili.durum}
                      {secili.firsat ? ` · ${sayi(secili.firsat)} boş kapı` : ''}
                      {secili.bolge ? ` · ${secili.bolge}. bölge` : ''}
                    </div>
                    <button
                      type="button"
                      className="yon-harita-ayrinti"
                      onClick={() => setAyrinti(secili.serial)}
                    >
                      Ayrıntılar
                    </button>
                  </div>
                ) : null
              }
            />
          </Kart>

          <Kart
            baslik="Kapsama tablosu"
            altYazi="Satıra tıklayın: harita oraya odaklanır"
            sag={
              <Segment<Kirilim>
                etiket="Kırılım"
                deger={kirilim}
                degisti={setKirilim}
                secenekler={[
                  { deger: 'bolge', etiket: 'Bölge' },
                  { deger: 'mahalle', etiket: 'Mahalle' },
                  { deger: 'ilce', etiket: 'İlçe' },
                ]}
              />
            }
            sikis
          >
            {tabloYukleniyor && !tabloSatirlari.length ? (
              <div style={{ padding: 16 }}>
                <Iskelet yukseklik={220} />
              </div>
            ) : (
              <div className="yon-tablo-sarmal" style={{ maxHeight: 520, overflowY: 'auto' }}>
                {/* Telefonda tablo satır kartına döner (§7.4): başlık gizlenir, her
                    hücre kendi etiketini (data-etiket) önüne yazar. */}
                <table className="yon-tablo satirlasir">
                  <thead>
                    <tr>
                      <th>{kirilim === 'bolge' ? 'Bölge' : kirilim === 'ilce' ? 'İlçe' : 'Mahalle'}</th>
                      <th className="sayi">Bina</th>
                      <th style={{ minWidth: 132 }}>Kapsama</th>
                      <th className="sayi">Kalan kapı</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tabloSatirlari.map((s) => {
                      const [ilk, ikinci] = satirBasligi(s);
                      return (
                        <tr
                          key={String(s.ad)}
                          className={`tiklanir${mahalle === s.ad ? ' secili' : ''}`}
                          onClick={() => satiraTikla(s)}
                          title={`${sayi(s.dokunulan)} / ${sayi(s.toplam)} bina`}
                        >
                          <td className="ad-hucre">
                            <div>{ilk}</div>
                            {ikinci ? <div className="ikinci-satir">{ikinci}</div> : null}
                          </td>
                          <td className="sayi" data-etiket="Bina">
                            {sayi(s.toplam)}
                          </td>
                          <td className="tam">
                            <OranCubugu oran={s.oran} />
                          </td>
                          <td className="sayi" data-etiket="Kalan kapı">
                            {sayi(s.kalan_firsat)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Kart>
        </div>
      </Icerik>
      {ayrinti ? <BinaAyrintiPenceresi serial={ayrinti} kapat={() => setAyrinti(null)} /> : null}
    </>
  );
}

const DURUM_METNI: Record<string, string> = {
  bekliyor: 'Hiç gidilmedi',
  planli: 'Bugünkü listede',
  ziyaret_edildi: 'Dokunuldu',
  tekrar_gel: 'Tekrar gidilecek',
  girilemedi: 'Binaya girilemedi',
  altyapi_sorunu: 'Altyapı sorunu',
};
