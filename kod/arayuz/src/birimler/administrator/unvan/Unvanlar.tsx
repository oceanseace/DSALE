/**
 * Unvan ve yetkinlik (yalnız Administrator) — unvan kataloğu + unvan × yetkinlik anahtar matrisi.
 *
 *   · Satırlar unvanlar (kaç kişide olduğu yanında), sütunlar yetkinlikler. Bir anahtar o unvandaki
 *     HERKESİN erişimini değiştirir; değişiklikler "Kaydet" ile tek işlemde yazılır.
 *   · "Takım lideri" satırı: İK'nın işaretlediği takım liderlerine kendiliğinden eklenen yetkinlikler.
 *   · Unvan ekle ("EÇM - Finans - Takım Lideri" gibi), adını değiştir (kişiler id ile bağlı kalır),
 *     pasife al (yeni kişiye atanamaz; elinde olanın erişimi sürer).
 *   · Yetkinlikler kodda tanımlıdır (sunucu `saha/yetki.py`); burada yalnız kime verileceği seçilir.
 *
 * Asıl kapı sunucudadır (`yetkinlik.yonet`, yalnız Administrator). Kişi yönetimi (İK) bu ekranı görmez.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Anahtar } from '../../../cekirdek/ortak/Anahtar';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { BosDurum, HataKutusu, Iskelet } from '../../../cekirdek/ortak/Bos';
import { AramaKutusu, Dugme } from '../../../cekirdek/ortak/Ilkel';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { Segment } from '../../../cekirdek/ortak/Segment';
import { eslesir } from '../../../cekirdek/ortak/ara';
import { Icerik, YonUst } from '../../../cekirdek/konsol/Kabuk';
import { matrisOku, matrisYaz, unvanDegistir, unvanEkle } from '../../../cekirdek/api/yonetim';
import type { UnvanKaydi, UnvanMatrisi, YetkinlikTanimi } from '../../../cekirdek/api/yonetimTipleri';
import { OnizlemeSecici } from '../../../cekirdek/ortak/OnizlemeSecici';
import './unvan.css';

type Suzgec = 'aktif' | 'pasif' | 'hepsi';
/** Takım lideri satırının anahtarı (unvan id'leri pozitif). */
const TL = -1;

function hata(h: unknown, yedek: string): string {
  return h instanceof Error ? h.message : yedek;
}

function ayni(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((x) => b.includes(x));
}

export function Unvanlar() {
  const { goster } = useBildirim();
  const [veri, setVeri] = useState<UnvanMatrisi | null>(null);
  const [yukHata, setYukHata] = useState<string | null>(null);
  /** Kaydedilmemiş anahtarlar: unvan id (TL = takım lideri) → yetkinlik kodları. */
  const [taslak, setTaslak] = useState<Record<number, string[]>>({});
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [suzgec, setSuzgec] = useState<Suzgec>('aktif');
  const [arama, setArama] = useState('');
  const [duzenlenen, setDuzenlenen] = useState<UnvanKaydi | 'yeni' | null>(null);

  const yukle = useCallback(() => {
    setYukHata(null);
    matrisOku()
      .then((v) => {
        setVeri(v);
        setTaslak({});
      })
      .catch((h) => setYukHata(hata(h, 'Unvanlar okunamadı.')));
  }, []);
  useEffect(yukle, [yukle]);

  const yetkinlikler = veri?.yetkinlikler ?? [];
  const deger = (id: number): string[] =>
    taslak[id] ?? (id === TL ? veri?.takim_lideri ?? [] : veri?.unvanlar.find((u) => u.id === id)?.yetkinlikler ?? []);

  const degistir = (id: number, kod: string, acik: boolean) => {
    const simdiki = deger(id);
    const yeni = acik ? [...simdiki, kod] : simdiki.filter((k) => k !== kod);
    const ilk = id === TL ? veri?.takim_lideri ?? [] : veri?.unvanlar.find((u) => u.id === id)?.yetkinlikler ?? [];
    setTaslak((t) => {
      const kopya = { ...t };
      if (ayni(yeni, ilk)) delete kopya[id];
      else kopya[id] = yeni;
      return kopya;
    });
  };

  const bekleyen = Object.keys(taslak).length;
  const etkilenecek = useMemo(
    () =>
      Object.keys(taslak)
        .map(Number)
        .filter((id) => id !== TL)
        .reduce((t, id) => t + (veri?.unvanlar.find((u) => u.id === id)?.aktif_kisi_sayisi ?? 0), 0),
    [taslak, veri],
  );

  const kaydet = async () => {
    if (!bekleyen) return;
    setKaydediliyor(true);
    try {
      const unvanlar: Record<number, string[]> = {};
      for (const [id, kodlar] of Object.entries(taslak)) if (Number(id) !== TL) unvanlar[Number(id)] = kodlar;
      const y = await matrisYaz({ unvanlar, ...(taslak[TL] ? { takim_lideri: taslak[TL] } : {}) });
      setVeri((v) => (v ? { ...v, unvanlar: y.unvanlar, takim_lideri: y.takim_lideri } : v));
      setTaslak({});
      goster(
        y.etkilenen_kisi
          ? `Kaydedildi. ${y.etkilenen_kisi} kişinin erişimi güncellendi.`
          : 'Kaydedildi.',
        'basari',
      );
    } catch (h) {
      goster(hata(h, 'Kaydedilemedi.'), 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  const gorunen = useMemo(
    () =>
      (veri?.unvanlar ?? []).filter(
        (u) => (suzgec === 'hepsi' || (suzgec === 'aktif') === u.aktif) && eslesir(u.ad, arama),
      ),
    [veri, suzgec, arama],
  );
  const sayilar = useMemo(() => {
    const u = veri?.unvanlar ?? [];
    return { aktif: u.filter((x) => x.aktif).length, pasif: u.filter((x) => !x.aktif).length, hepsi: u.length };
  }, [veri]);

  return (
    <>
      <YonUst baslik="Unvan ve yetkinlik">
        <button type="button" className="o-dugme birincil" onClick={() => setDuzenlenen('yeni')}>
          Unvan ekle
        </button>
      </YonUst>
      <Icerik>
        <div style={{ marginBottom: 'var(--b3)' }}>
          <OnizlemeSecici />
        </div>
        {yukHata ? <HataKutusu mesaj={yukHata} tekrar={yukle} /> : null}
        {!veri && !yukHata ? <Iskelet satir={8} yukseklik={44} /> : null}
        {veri ? (
          <>
            <YetkinlikSozlugu yetkinlikler={yetkinlikler} />

            <div className="unvan-arac">
              <Segment<Suzgec>
                etiket="Unvan durumu"
                deger={suzgec}
                degisti={setSuzgec}
                secenekler={[
                  { deger: 'aktif', etiket: 'Aktif', sayi: sayilar.aktif },
                  { deger: 'pasif', etiket: 'Pasif', sayi: sayilar.pasif },
                  { deger: 'hepsi', etiket: 'Hepsi', sayi: sayilar.hepsi },
                ]}
              />
              <AramaKutusu className="unvan-ara" deger={arama} degisti={setArama} yerTutucu="Unvan ara" />
            </div>

            {gorunen.length ? (
              <div className="unvan-matris-kap" role="region" aria-label="Unvan ve yetkinlik matrisi" tabIndex={0}>
                <table className="unvan-matris">
                  <thead>
                    <tr>
                      <th scope="col" className="unvan-ad-sutun">
                        Unvan
                      </th>
                      {yetkinlikler.map((y) => (
                        <th key={y.kod} scope="col" title={y.aciklama}>
                          <span className="unvan-sutun-ad">{y.ad}</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {gorunen.map((u) => (
                      <tr key={u.id} className={`${u.aktif ? '' : 'pasif'}${taslak[u.id] ? ' degisti' : ''}`}>
                        <th scope="row" className="unvan-ad-sutun">
                          <button type="button" className="unvan-ad" onClick={() => setDuzenlenen(u)}>
                            <span className="ad">{u.ad}</span>
                            <span className="alt">
                              {u.aktif_kisi_sayisi ? `${u.aktif_kisi_sayisi} kişi` : 'Kimsede yok'}
                              {!u.aktif ? ' · pasif' : ''}
                            </span>
                          </button>
                        </th>
                        {yetkinlikler.map((y) => (
                          <td key={y.kod}>
                            <Anahtar
                              kucuk
                              acik={deger(u.id).includes(y.kod)}
                              degisti={(acik) => degistir(u.id, y.kod, acik)}
                              aciklama={`${u.ad}: ${y.ad}`}
                              kapali={kaydediliyor}
                            />
                          </td>
                        ))}
                      </tr>
                    ))}
                    <tr className={`unvan-tl${taslak[TL] ? ' degisti' : ''}`}>
                      <th scope="row" className="unvan-ad-sutun">
                        <span className="unvan-ad sabit">
                          <span className="ad">Takım lideri</span>
                          <span className="alt">İK’nın işaretlediği liderlere ek olarak</span>
                        </span>
                      </th>
                      {yetkinlikler.map((y) => (
                        <td key={y.kod}>
                          <Anahtar
                            kucuk
                            acik={deger(TL).includes(y.kod)}
                            degisti={(acik) => degistir(TL, y.kod, acik)}
                            aciklama={`Takım lideri: ${y.ad}`}
                            kapali={kaydediliyor}
                          />
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="o-liste">
                <BosDurum kucuk baslik="Bu süzgeçte unvan yok." />
              </div>
            )}
          </>
        ) : null}
      </Icerik>

      {bekleyen ? (
        <div className="unvan-kaydet" role="status">
          <span>
            {bekleyen} satır değişti
            {etkilenecek ? ` · ${etkilenecek} kişinin erişimi değişecek` : ''}
          </span>
          <Dugme onClick={() => setTaslak({})} disabled={kaydediliyor}>
            Vazgeç
          </Dugme>
          <Dugme tur="vurgu" onClick={() => void kaydet()} disabled={kaydediliyor}>
            {kaydediliyor ? 'Kaydediliyor…' : 'Kaydet'}
          </Dugme>
        </div>
      ) : null}

      <UnvanPaneli
        durum={duzenlenen}
        yetkinlikler={yetkinlikler}
        kapat={() => setDuzenlenen(null)}
        bitti={(u, mesaj) => {
          setVeri((v) =>
            v
              ? {
                  ...v,
                  unvanlar: v.unvanlar.some((x) => x.id === u.id)
                    ? v.unvanlar.map((x) => (x.id === u.id ? u : x))
                    : [...v.unvanlar, u],
                }
              : v,
          );
          setDuzenlenen(null);
          goster(mesaj, 'basari');
        }}
      />
    </>
  );
}

/* ------------------------------ Yetkinlik sözlüğü ------------------------------ */

function YetkinlikSozlugu({ yetkinlikler }: { yetkinlikler: YetkinlikTanimi[] }) {
  const [acik, setAcik] = useState(false);
  return (
    <section className="unvan-sozluk">
      <button type="button" className="unvan-sozluk-bas" aria-expanded={acik} onClick={() => setAcik(!acik)}>
        <span>Yetkinlikler ne açar?</span>
        <span className="sayi">{yetkinlikler.length}</span>
      </button>
      {acik ? (
        <dl>
          {yetkinlikler.map((y) => (
            <div key={y.kod}>
              <dt>{y.ad}</dt>
              <dd>{y.aciklama}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}

/* ------------------------------ Unvan ekle / düzenle ------------------------------ */

function UnvanPaneli({
  durum,
  yetkinlikler,
  kapat,
  bitti,
}: {
  durum: UnvanKaydi | 'yeni' | null;
  yetkinlikler: YetkinlikTanimi[];
  kapat: () => void;
  bitti: (u: UnvanKaydi, mesaj: string) => void;
}) {
  const yeni = durum === 'yeni';
  const kayit = durum && durum !== 'yeni' ? durum : null;
  const [ad, setAd] = useState('');
  const [secili, setSecili] = useState<string[]>([]);
  const [aktif, setAktif] = useState(true);
  const [bekliyor, setBekliyor] = useState(false);
  const [hataMetni, setHataMetni] = useState<string | null>(null);

  useEffect(() => {
    setAd(kayit?.ad ?? '');
    setSecili([]);
    setAktif(kayit?.aktif ?? true);
    setHataMetni(null);
  }, [durum, kayit]);

  if (!durum) return null;

  const kaydet = async () => {
    setHataMetni(null);
    if (ad.trim().length < 2) return setHataMetni('Unvan adını yazın.');
    setBekliyor(true);
    try {
      if (yeni) {
        const u = await unvanEkle(ad.trim(), secili);
        bitti(u, `“${u.ad}” eklendi.`);
      } else if (kayit) {
        const degisiklik: { ad?: string; aktif?: boolean } = {};
        if (ad.trim() !== kayit.ad) degisiklik.ad = ad.trim();
        if (aktif !== kayit.aktif) degisiklik.aktif = aktif;
        if (!Object.keys(degisiklik).length) return kapat();
        const u = await unvanDegistir(kayit.id, degisiklik);
        bitti(u, degisiklik.aktif === false ? `“${u.ad}” pasife alındı.` : `“${u.ad}” kaydedildi.`);
      }
    } catch (h) {
      setHataMetni(hata(h, 'Kaydedilemedi.'));
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik
      kapat={kapat}
      kilitli={bekliyor}
      baslik={yeni ? 'Yeni unvan' : 'Unvanı düzenle'}
      altBaslik={
        yeni ? undefined : kayit?.aktif_kisi_sayisi ? `${kayit.aktif_kisi_sayisi} kişide` : 'Henüz kimsede yok'
      }
      alt={
        <>
          <Dugme onClick={kapat} disabled={bekliyor}>
            Vazgeç
          </Dugme>
          <Dugme tur="birincil" onClick={() => void kaydet()} disabled={bekliyor}>
            {bekliyor ? 'Kaydediliyor…' : yeni ? 'Ekle' : 'Kaydet'}
          </Dugme>
        </>
      }
    >
      <div className="unvan-form">
        <label className="o-alan">
          <span className="etiket">Unvan</span>
          <input value={ad} autoFocus onChange={(o) => setAd(o.target.value)} placeholder="EÇM - Finans - Takım Lideri" />
        </label>
        {yeni ? (
          <fieldset className="unvan-secim">
            <legend className="etiket">Yetkinlikler</legend>
            {yetkinlikler.map((y) => (
              <Anahtar
                key={y.kod}
                acik={secili.includes(y.kod)}
                degisti={(a) => setSecili(a ? [...secili, y.kod] : secili.filter((k) => k !== y.kod))}
                etiket={
                  <span className="unvan-secim-metin">
                    <strong>{y.ad}</strong>
                    <span>{y.aciklama}</span>
                  </span>
                }
              />
            ))}
          </fieldset>
        ) : (
          <div className="unvan-durum">
            <Anahtar acik={aktif} degisti={setAktif} etiket="Aktif (yeni kişiye atanabilir)" />
            {!aktif && kayit?.aktif_kisi_sayisi ? (
              <p className="aciklama">
                {kayit.aktif_kisi_sayisi} kişinin erişimi sürer; Kişiler ekranından başka unvana taşıyın.
              </p>
            ) : null}
          </div>
        )}
        {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
      </div>
    </Panel>
  );
}
