/**
 * Öbekler (§6.4, F1–F3): masaüstünde Excel alışkanlığıyla tablo (EK-9 Tablo:
 * Öbek · Mahalle · Açık · Geciken · BTK · Atanmamış · Ev teknisyeni); telefonda
 * satırlar kart olur. Başta [+ Yeni öbek] ve "Öbeksiz mahalleler (N) ›" (bugün
 * işi olan ama öbeği olmayan mahalleler; satırda [Bir öbeğe ekle]).
 *
 * Satıra basınca öbek çekmecesi (#/yonetici/obekler/<id>): mahalleleri listeler,
 * ⊖ ile çıkarır, 23 ilçenin tamamından ekler; "İşlerini gör" → İşler (F3).
 */

import { useMemo, useState } from 'react';
import { hataMetni, mahalleEkle, obekMahalleEkle, obekOlustur } from '../../is/api';
import type { Obek, ObeklerYanit } from '../../is/tipler';
import { git, useAdres } from '../../yol/rota';
import { useOturum } from '../../depo/oturum';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { Tablo, type TabloSutunu } from '../../ortak/Tablo';
import { Hikaye } from '../../ortak/Hikaye';
import { Panel } from '../../ortak/Panel';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { useBildirim } from '../../ortak/Bildirim';
import { IslerSaglayici, useIsler } from '../isler/depo';
import { ObekNoktasi, ObekSecici } from '../isler/parcalar';
import { ObekCekmecesi } from './ObekCekmecesi';
import '../isler/isler.css';

export function Obekler() {
  return (
    <IslerSaglayici>
      <ObeklerEkrani />
    </IslerSaglayici>
  );
}

type Obeksiz = ObeklerYanit['obeksiz'][number];

function ObeklerEkrani() {
  const depo = useIsler();
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const adres = useAdres();
  const seciliId = useMemo(() => {
    const p = adres.split('/').filter(Boolean);
    const n = Number(p[2]);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [adres]);
  const [yeniAcik, setYeniAcik] = useState(false);
  const [yeniAd, setYeniAd] = useState('');
  const [yeniHata, setYeniHata] = useState<string | null>(null);
  const [bekliyor, setBekliyor] = useState(false);
  const [obeksizAcik, setObeksizAcik] = useState(false);
  const [obeksizSecim, setObeksizSecim] = useState<Obeksiz | null>(null);
  const duzenler = izinli('obek.duzenle');

  const obekler = depo.obekler?.obekler ?? [];
  const obeksiz = depo.obekler?.obeksiz ?? [];
  const sahipsiz = obekler.filter((o) => !o.sahip).length;
  const toplamMahalle = obekler.reduce((t, o) => t + o.mahalleler.length, 0);
  const obeksizIs = obeksiz.reduce((t, m) => t + m.acik, 0);

  const sutunlar: Array<TabloSutunu<Obek>> = useMemo(
    () => [
      {
        anahtar: 'ad',
        baslik: 'Öbek',
        deger: (o) => o.ad,
        goster: (o) => (
          <span className={`ob-ad${o.acik ? '' : ' soluk'}`}>
            <ObekNoktasi renk={o.renk} /> {o.ad}
          </span>
        ),
        genislik: 180,
        kartta: 'baslik',
        suzgec: false,
      },
      {
        anahtar: 'mahalle',
        baslik: 'Mahalle',
        deger: (o) =>
          o.mahalleler.map((m) => (m.tum_ilce ? `${m.ilce} (ilçenin tamamı)` : m.mahalle)).join(', ') || 'mahalle yok',
        genislik: 320,
        kartta: 'alt',
        suzgec: false,
      },
      { anahtar: 'mahalle_sayisi', baslik: 'Mahalle sayısı', deger: (o) => o.mahalleler.length, sayi: true, genislik: 110 },
      { anahtar: 'acik', baslik: 'Açık', deger: (o) => o.acik, sayi: true, genislik: 76 },
      { anahtar: 'geciken', baslik: 'Geciken', deger: (o) => o.geciken, sayi: true, genislik: 84 },
      { anahtar: 'btk', baslik: 'BTK', deger: (o) => o.btk, sayi: true, genislik: 68 },
      { anahtar: 'atanmamis', baslik: 'Atanmamış', deger: (o) => o.atanmamis, sayi: true, genislik: 96 },
      { anahtar: 'sahip', baslik: 'Ev teknisyeni', deger: (o) => o.sahip?.ad ?? '', goster: (o) => o.sahip?.ad ?? <span className="ip-sessiz">yok</span>, genislik: 160 },
      { anahtar: 'yedek', baslik: 'Yedek', deger: (o) => o.yedek?.ad ?? '', genislik: 150 },
    ],
    [],
  );

  const olustur = async () => {
    const ad = yeniAd.trim();
    if (!ad) return;
    setBekliyor(true);
    try {
      const y = await obekOlustur(ad, depo.obekler?.surum ?? 0);
      await depo.obekleriTazele();
      setYeniAcik(false);
      setYeniAd('');
      bildirim.goster(`${y.obek.ad} öbeği oluşturuldu. Şimdi mahallelerini ekleyin.`, 'basari');
      git(`/yonetici/obekler/${y.obek.id}`);
    } catch (e) {
      const m = hataMetni(e);
      if (/aynı|var/i.test(m)) setYeniHata('Bu adla bir öbek var.');
      else bildirim.goster(m, 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  const obeksizEkle = async (m: Obeksiz, o: Obek) => {
    setBekliyor(true);
    try {
      let id = m.mahalle_id;
      if (!id) {
        const y = await mahalleEkle({ il: m.il, ilce: m.ilce, ad: m.mahalle, benzerine_ragmen: true });
        id = y.mahalle.id;
      }
      const y = await obekMahalleEkle(o.id, { mahalle_idler: [id], tasi: false, surum: depo.obekler?.surum ?? 0 });
      depo.obekleriYaz(y.obekler, y.surum);
      void depo.tazele();
      setObeksizSecim(null);
      bildirim.goster(`${m.mahalle} artık ${o.ad} öbeğinde · ${y.etkilenen_is} iş oraya düştü.`, 'basari');
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <>
      <YonUst baslik="Öbekler">
        {duzenler ? (
          <button
            type="button"
            className="o-dugme birincil"
            onClick={() => {
              setYeniAd('');
              setYeniHata(null);
              setYeniAcik(true);
            }}
          >
            + Yeni öbek
          </button>
        ) : null}
      </YonUst>
      <Icerik>
        {!depo.obekler && depo.durum !== 'hata' ? <Iskelet satir={6} yukseklik={44} /> : null}
        {!depo.obekler && depo.durum === 'hata' ? <HataKutusu mesaj={depo.hata ?? 'Öbekler alınamadı.'} tekrar={() => void depo.obekleriTazele()} /> : null}
        {depo.obekler ? (
          <>
            <Hikaye
              cumle={`${obekler.length} öbek, ${toplamMahalle} mahalle.${sahipsiz ? ` ${sahipsiz} öbeğin ev teknisyeni yok; öneri yazılmıyor.` : ' Her öbeğin ev teknisyeni var.'}${
                obeksiz.length ? ` ${obeksiz.length} mahallenin öbeği yok (${obeksizIs} iş).` : ''
              }`}
              ton={sahipsiz || obeksiz.length ? 'dikkat' : 'iyi'}
            />
            {obeksiz.length ? (
              <section className="ob-obeksiz">
                <button type="button" className="ob-obeksiz-bas" aria-expanded={obeksizAcik} onClick={() => setObeksizAcik((a) => !a)}>
                  <span>
                    Öbeksiz mahalleler <b>({obeksiz.length})</b>
                  </span>
                  <span className="ip-kaynak">bugün işi olan ama öbeği olmayan</span>
                  <span className={`ok${obeksizAcik ? ' acik' : ''}`} aria-hidden="true">
                    ›
                  </span>
                </button>
                {obeksizAcik ? (
                  <ul>
                    {obeksiz.map((m) => (
                      <li key={`${m.il}/${m.ilce}/${m.mahalle}`}>
                        <span className="yer">
                          <b>{m.mahalle || 'Mahalle bilinmiyor'}</b> <span className="ip-kaynak">· {m.ilce}</span>
                        </span>
                        <span className="sayi">{m.acik} iş</span>
                        {duzenler && m.mahalle ? (
                          <button type="button" className="o-dugme kucuk" onClick={() => setObeksizSecim(m)}>
                            Bir öbeğe ekle
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ) : null}
            {obekler.length ? (
              <Tablo
                satirlar={obekler}
                sutunlar={sutunlar}
                anahtar={(o) => o.id}
                onAc={(o) => git(`/yonetici/obekler/${o.id}`)}
                seciliAnahtar={seciliId}
                excelAdi="Obekler"
                kayitAnahtari="obekler"
                aramaYerTutucu="Öbek, mahalle, teknisyen…"
              />
            ) : (
              <BosDurum
                simge="🗺️"
                baslik="Henüz öbek yok."
                aciklama="Öbek, birlikte çalışılan mahalle grubudur. Bir öbek oluşturup mahallelerini ekleyin; işler kendiliğinden öbeğine düşer."
              />
            )}
          </>
        ) : null}
      </Icerik>

      <ObekCekmecesi obekId={seciliId} kapat={() => git('/yonetici/obekler')} />

      <Panel
        acik={yeniAcik}
        kapat={() => setYeniAcik(false)}
        kilitli={bekliyor}
        baslik="Yeni öbek"
        altBaslik="Önce adını verin; sonra mahallelerini eklersiniz."
        alt={
          <>
            <button type="button" className="o-dugme" onClick={() => setYeniAcik(false)} disabled={bekliyor}>
              Vazgeç
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => void olustur()} disabled={!yeniAd.trim() || bekliyor}>
              Oluştur
            </button>
          </>
        }
      >
        <label className="o-alan">
          <span className="etiket">Öbeğin adı</span>
          <input
            className="o-girdi"
            value={yeniAd}
            maxLength={80}
            autoFocus
            placeholder="ör. Görükle"
            onChange={(o) => {
              setYeniAd(o.target.value);
              setYeniHata(null);
            }}
            onKeyDown={(o) => o.key === 'Enter' && void olustur()}
          />
          {yeniHata ? <span className="ob-hata">{yeniHata}</span> : null}
        </label>
      </Panel>

      <Panel
        acik={Boolean(obeksizSecim)}
        kapat={() => setObeksizSecim(null)}
        kilitli={bekliyor}
        baslik={obeksizSecim ? `${obeksizSecim.mahalle} hangi öbeğe?` : 'Öbek seçin'}
        altBaslik="Mahalle öbeğe eklenir; bugünkü ve bundan sonraki işleri oraya düşer."
      >
        {obeksizSecim ? <ObekSecici obekler={obekler} sec={(o) => void obeksizEkle(obeksizSecim, o)} /> : null}
      </Panel>
    </>
  );
}
