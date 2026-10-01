/**
 * Veri kalitesi — "raporlardaki mantıksız veriyi mantıklıya çevirmek".
 *
 * Sistem her binayı 14 açık kuralla denetler (dsale/kalite.py). Her kural bir
 * kart: ne bulundu, kaç binada, sistem düzeltti mi. Karta basınca o binaların
 * listesi yandan açılır; satıra basınca binanın Ayrıntılar penceresi.
 *
 * Düzeltme yalnız GÜVENLİ olduğunda yapılır (sonuç kesin ya da değer yalnız
 * görüntüyü etkiliyor). RES HP ve aboneye asla dokunulmaz; orijinal değer
 * her zaman saklanır (sözleşme §7.1).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { SahaHatasi } from '../../api/istemci';
import { useBildirim } from '../../ortak/Bildirim';
import { kopyala } from '../../ortak/kimlik';
import { sayi } from '../../ortak/bicim';
import { Onay, Uyari, Yenile } from '../../ortak/Ikon';
import { git } from '../../yol/rota';
import { kaliteListesi, kaliteOzeti, kaliteYenile } from '../api';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { BinaAyrintiPenceresi } from '../ortak/BinaAyrinti';
import { HataKutusu, Iskelet, Segment, useVeri } from '../ortak/parcalar';
import type { KaliteBinasi, KaliteKurali } from '../tipler';
import { bolgeNumaralari, useBolgeSayisi } from './bolge/bolgeSayisi';
import './faz2.css';

/**
 * Kartın yöneticiye söylediği tek şey: bakmam gerekiyor mu?
 *   kontrol    — uyarı ve sistem düzeltemedi (kaynağında/sahada bakılmalı)
 *   duzeltildi — bulunan her değeri sistem güvenle düzeltti
 *   bilgi      — yalnız bilgi (ör. kat sayısı tahmini)
 *   temiz      — bu kurala takılan bina yok
 * ("Uyarı" seviyesindeki bir kural bütün bulgularını düzelttiyse kart artık
 * "kontrol edilmeli" demez; eskiden "Kontrol edilmeli · 2.335 düzeltildi"
 * yan yana yazıp kafa karıştırıyordu.)
 */
type Grup = 'kontrol' | 'duzeltildi' | 'bilgi' | 'temiz';
type Suzgec = 'hepsi' | Exclude<Grup, 'temiz'>;
const GRUP_ADI: Record<Grup, string> = {
  kontrol: 'Kontrol edilmeli',
  duzeltildi: 'Sistem düzeltti',
  bilgi: 'Bilgi',
  temiz: 'Sorun yok',
};
const GRUP_SIRASI: Record<Grup, number> = { kontrol: 0, duzeltildi: 1, bilgi: 2, temiz: 3 };

function grubu(k: KaliteKurali): Grup {
  if (!k.adet) return 'temiz';
  if (k.duzeltir && k.duzeltilen >= k.adet) return 'duzeltildi';
  return k.seviye === 'uyari' ? 'kontrol' : 'bilgi';
}

const SAYFA = 50;

const ALAN_ADI: Record<string, string> = {
  location_id: 'Location Id',
  tellcordia_id: 'Tellcordia ID',
  kat: 'Kat',
  ad: 'Ad',
  site_adi: 'Site adı',
};

function hataMetni(h: unknown, yedek = 'İşlem yapılamadı.') {
  return h instanceof SahaHatasi ? h.message : yedek;
}

export function VeriKalitesi({ baslangicKural }: { baslangicKural?: string | null }) {
  const { goster } = useBildirim();
  const bolgeSayisi = useBolgeSayisi();
  const [bolge, setBolge] = useState<number | null>(null);
  const [seviye, setSeviye] = useState<Suzgec>('hepsi');
  const [surum, setSurum] = useState(0);
  const [yenileniyor, setYenileniyor] = useState(false);
  const ozet = useVeri(() => kaliteOzeti(bolge), [bolge, surum]);
  const kural = baslangicKural ?? null;

  const kuralSec = useCallback((k: string | null) => {
    git(k ? `/yonetici/veri-kalitesi/${encodeURIComponent(k)}` : '/yonetici/veri-kalitesi');
  }, []);

  const kurallar = useMemo(() => {
    const liste = (ozet.veri?.kurallar ?? []).filter((k) => seviye === 'hepsi' || grubu(k) === seviye);
    // Bakılması gerekenler önce, sonra düzeltilenler, bilgi, en sonda bulgusu olmayanlar.
    return [...liste].sort((a, b) => GRUP_SIRASI[grubu(a)] - GRUP_SIRASI[grubu(b)] || b.adet - a.adet);
  }, [ozet.veri, seviye]);

  const toplamlar = useMemo(() => {
    const k = ozet.veri?.kurallar ?? [];
    return {
      duzeltilen: k.reduce((t, x) => t + x.duzeltilen, 0),
      kontrol: k.filter((x) => grubu(x) === 'kontrol').reduce((t, x) => t + x.adet, 0),
    };
  }, [ozet.veri]);

  const seciliKural = ozet.veri?.kurallar.find((k) => k.kural === kural) ?? null;

  const yeniden = async () => {
    setYenileniyor(true);
    try {
      const y = await kaliteYenile();
      goster(y.mesaj || 'Binalar yeniden denetlendi.', 'basari');
      setSurum((s) => s + 1);
    } catch (h) {
      goster(hataMetni(h, 'Denetim yapılamadı.'), 'uyari');
    } finally {
      setYenileniyor(false);
    }
  };

  const o = ozet.veri;
  return (
    <>
      <YonUst
        baslik="Veri kalitesi"
        altYazi="Sistem her binayı açık kurallarla denetler. RES HP ve aboneye asla dokunulmaz; düzeltilen her değerin aslı saklanır."
      >
        <select
          className="yon-alan"
          style={{ width: 170 }}
          value={bolge ?? ''}
          onChange={(e) => setBolge(e.target.value ? Number(e.target.value) : null)}
          aria-label="Bölge süzgeci"
        >
          <option value="">Bütün bölgeler</option>
          {bolgeNumaralari(bolgeSayisi).map((b) => (
            <option key={b} value={b}>
              {b}. bölge
            </option>
          ))}
        </select>
        <button className="yd" onClick={yeniden} disabled={yenileniyor} title="Kurallar ya da kaynak dosyalar değiştiyse">
          <Yenile boyut={18} />
          {yenileniyor ? 'Denetleniyor…' : 'Yeniden denetle'}
        </button>
      </YonUst>

      <Icerik>
        {ozet.hata ? <HataKutusu mesaj={ozet.hata} yenile={ozet.yenile} /> : null}

        {!o ? (
          <Iskelet yukseklik={120} />
        ) : (
          <div className="vk-manset">
            <div className="vk-manset-ana">
              {/* Sayıya ek getirilmez ("12.054'ünde"): ek sayının okunuşuna göre değişir,
                  yanlış ek güveni zedeler. Cümle eksiz kurulur. */}
              <div className="vk-buyuk">
                <em>{sayi(o.bayrakli_bina)}</em> binada not var
              </div>
              <div className="vk-alt">
                {sayi(o.toplam_bina - (o.hesaplanmamis || 0))} bina denetlendi
                {o.hesaplanmamis ? ` (${sayi(o.hesaplanmamis)} bina henüz denetlenmedi)` : ''}. Notların çoğu bilgi
                amaçlı (ör. kat sayısı tahmini); asıl bakılması gerekenler turuncu kartlar.
              </div>
            </div>
            <div className="vk-manset-sayi yesil">
              <div className="deger">{sayi(toplamlar.duzeltilen)}</div>
              <div className="etiket">Güvenle düzeltilen değer</div>
            </div>
            <div className="vk-manset-sayi amber">
              <div className="deger">{sayi(toplamlar.kontrol)}</div>
              <div className="etiket">Kaynağında kontrol edilmeli</div>
            </div>
          </div>
        )}

        <div className="vk-suzgec">
          <Segment<Suzgec>
            etiket="Seviye"
            deger={seviye}
            degisti={setSeviye}
            secenekler={[
              { deger: 'hepsi', etiket: 'Hepsi' },
              { deger: 'kontrol', etiket: 'Kontrol edilmeli' },
              { deger: 'duzeltildi', etiket: 'Sistem düzeltti' },
              { deger: 'bilgi', etiket: 'Bilgi' },
            ]}
          />
          <span className="vk-suzgec-not">Karta tıklayın: o binaların listesi açılır.</span>
        </div>

        {o ? (
          <div className="vk-kartlar">
            {kurallar.map((k) => (
              <KuralKarti key={k.kural} k={k} secili={k.kural === kural} sec={() => kuralSec(k.kural)} />
            ))}
          </div>
        ) : (
          <Iskelet yukseklik={320} />
        )}
      </Icerik>

      {seciliKural ? <KuralCekmecesi k={seciliKural} bolge={bolge} kapat={() => kuralSec(null)} /> : null}
    </>
  );
}

function KuralKarti({ k, secili, sec }: { k: KaliteKurali; secili: boolean; sec: () => void }) {
  const bos = k.adet === 0;
  return (
    <button
      type="button"
      className={`vk-kart g-${grubu(k)}${bos ? ' vk-bos' : ''}${secili ? ' secili' : ''}`}
      onClick={sec}
      disabled={bos}
      aria-pressed={secili}
    >
      <span className="vk-kart-ust">
        <span className={`vk-seviye g-${grubu(k)}`}>{GRUP_ADI[grubu(k)]}</span>
        {k.duzeltilen > 0 ? (
          <span className="vk-duzeltildi">
            <Onay boyut={13} /> {sayi(k.duzeltilen)} düzeltildi
          </span>
        ) : null}
      </span>
      <span className="vk-kart-ad">{k.ad}</span>
      <span className="vk-kart-sayi">
        {bos ? (
          <span className="vk-sorun-yok">
            <Onay boyut={18} /> Sorun yok
          </span>
        ) : (
          <>
            <b>{sayi(k.adet)}</b> bina
          </>
        )}
      </span>
      <span className="vk-kart-aciklama">{k.aciklama}</span>
      {!bos ? <span className="vk-kart-git">Binaları gör →</span> : null}
    </button>
  );
}

/* ------------------------------ Kuralın binaları (yan çekmece) ------------------------------ */

function KuralCekmecesi({ k, bolge, kapat }: { k: KaliteKurali; bolge: number | null; kapat: () => void }) {
  const { goster } = useBildirim();
  const [binalar, setBinalar] = useState<KaliteBinasi[]>([]);
  const [toplam, setToplam] = useState(0);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [ayrinti, setAyrinti] = useState<string | null>(null);
  const [kopyalaniyor, setKopyalaniyor] = useState(false);

  const getir = useCallback(
    async (offset: number) => {
      setYukleniyor(true);
      setHata(null);
      try {
        const y = await kaliteListesi({ kural: k.kural, bolge, limit: SAYFA, offset });
        setToplam(y.toplam);
        setBinalar((eski) => (offset ? [...eski, ...y.binalar] : y.binalar));
      } catch (h) {
        setHata(hataMetni(h, 'Liste alınamadı.'));
      } finally {
        setYukleniyor(false);
      }
    },
    [k.kural, bolge],
  );

  useEffect(() => {
    setBinalar([]);
    void getir(0);
  }, [getir]);

  useEffect(() => {
    const tus = (e: KeyboardEvent) => e.key === 'Escape' && !ayrinti && kapat();
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [kapat, ayrinti]);

  /** Bütün listeyi (500'lük sayfalarla) Excel'e yapıştırılacak biçimde kopyalar. */
  const hepsiniKopyala = async () => {
    setKopyalaniyor(true);
    try {
      const hepsi: KaliteBinasi[] = [];
      for (let offset = 0; offset < Math.max(toplam, 1) && offset < 20000; offset += 500) {
        const y = await kaliteListesi({ kural: k.kural, bolge, limit: 500, offset });
        hepsi.push(...y.binalar);
        if (y.binalar.length < 500) break;
      }
      const satirlar = [
        ['Bina Serial', 'Bina', 'Bölge', 'Location Id', 'Tellcordia ID', 'İlçe', 'Mahalle', 'Not'].join('\t'),
        ...hepsi.map((b) =>
          [
            b.bina_serial,
            b.baslik || b.ad,
            b.bolge ?? '',
            b.location_id,
            b.tellcordia_id,
            b.ilce,
            b.mahalle,
            b.kalite.find((x) => x.kural === k.kural)?.mesaj ?? '',
          ].join('\t'),
        ),
      ];
      const ok = await kopyala(satirlar.join('\n'));
      goster(ok ? `${sayi(hepsi.length)} bina kopyalandı — Excel'e yapıştırın.` : 'Kopyalanamadı.', ok ? 'basari' : 'uyari');
    } catch (h) {
      goster(hataMetni(h, 'Liste alınamadı.'), 'uyari');
    } finally {
      setKopyalaniyor(false);
    }
  };

  return (
    <>
      <div className="yan-perde" onClick={kapat} aria-hidden="true" />
      <aside className="yan-cekmece" role="dialog" aria-modal="true" aria-label={k.ad}>
        <div className="yan-cekmece-bas">
          <div style={{ minWidth: 0 }}>
            <span className={`vk-seviye g-${grubu(k)}`}>{GRUP_ADI[grubu(k)]}</span>
            <h2>{k.ad}</h2>
          </div>
          <button type="button" className="yan-kapat" onClick={kapat} aria-label="Kapat">
            ×
          </button>
        </div>

        <div className="yan-cekmece-govde">
          <div className="vk-ne">
            <div className="vk-ne-baslik">Ne demek?</div>
            <p>{k.aciklama}</p>
            <div className="vk-ne-baslik">Sistem ne yaptı?</div>
            {k.duzeltir ? (
              <p className="vk-ne-iyi">
                <Onay boyut={16} /> {sayi(k.duzeltilen)} binada değeri güvenle düzeltti. Orijinal değer saklanıyor; her
                satırda "eski → yeni" yazıyor.
              </p>
            ) : (
              <p className="vk-ne-dikkat">
                <Uyari boyut={16} /> Dokunmadı — hangi değerin doğru olduğu bilinemiyor. Kaynağında (BOSS / OneMap) ya
                da sahada kontrol edin.
              </p>
            )}
          </div>

          <div className="vk-liste-ust">
            <b>
              {sayi(toplam)} bina{bolge ? ` · ${bolge}. bölge` : ''}
            </b>
            <button className="yd" onClick={hepsiniKopyala} disabled={kopyalaniyor || !toplam}>
              {kopyalaniyor ? 'Kopyalanıyor…' : 'Listeyi kopyala (Excel)'}
            </button>
          </div>

          {hata ? <HataKutusu mesaj={hata} yenile={() => void getir(0)} /> : null}

          <ul className="vk-binalar">
            {binalar.map((b) => {
              const not = b.kalite.find((x) => x.kural === k.kural);
              return (
                <li key={b.bina_serial}>
                  <button type="button" className="vk-bina" onClick={() => setAyrinti(b.bina_serial)}>
                    <span className="vk-bina-bas">
                      <b>{b.baslik || b.ad || b.bina_serial}</b>
                      <span className="vk-bina-bolge">{b.bolge ? `${b.bolge}. bölge` : 'bölgesiz'}</span>
                    </span>
                    <span className="vk-bina-kimlik">
                      {b.bina_serial} · Location Id {b.location_id || '—'}
                      {b.mahalle ? ` · ${b.mahalle}` : ''}
                    </span>
                    {not ? (
                      <span className="vk-bina-not">
                        {not.mesaj}
                        {not.duzeltme ? (
                          <span className="bn-duzeltme">
                            Düzeltildi · {ALAN_ADI[not.duzeltme.alan] ?? not.duzeltme.alan}:{' '}
                            <s>{String(not.duzeltme.eski ?? '—')}</s> → <b>{String(not.duzeltme.yeni ?? '—')}</b>
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>

          {yukleniyor ? <Iskelet yukseklik={binalar.length ? 60 : 280} /> : null}

          {!yukleniyor && binalar.length < toplam ? (
            <button className="yd genis" onClick={() => void getir(binalar.length)}>
              Daha fazla göster ({sayi(binalar.length)} / {sayi(toplam)})
            </button>
          ) : null}
        </div>
      </aside>
      {ayrinti ? <BinaAyrintiPenceresi serial={ayrinti} kapat={() => setAyrinti(null)} /> : null}
    </>
  );
}
