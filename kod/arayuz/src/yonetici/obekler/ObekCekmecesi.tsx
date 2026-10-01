/**
 * Öbek çekmecesi (§6.4, F1): öbeğin tanımı = mahalleleri. Rapora bağlı değildir;
 * her satırda bugünkü açık iş sayısı (0 → "bugün iş yok") ve 44 px ⊖.
 *
 *   ⊖ hemen çıkarır → "Kayapa çıkarıldı · Geri al"; işlerin öbeği aynı işlemde
 *   yeniden çözülür ve pano sayıları sayfa yenilenmeden güncellenir. Son mahalle
 *   çıkınca öbek SİLİNMEZ. [+ Mahalle ekle] → mahalle seçici (23 ilçenin tamamı).
 *   Ev teknisyeni / yedek · Adı değiştir (aynı ad varsa "Bu adla bir öbek var.")
 *   · Öbeği ikiye böl… (mahalleye göre, kalıcı) · Öbeği sil (onay + 10 sn geri al).
 */

import { useEffect, useState } from 'react';
import {
  hataMetni,
  IsHatasi,
  obekBol,
  obekGeriAl,
  obekGuncelle,
  obekMahalleCikar,
  obekMahalleEkle,
  obekSil,
} from '../../is/api';
import type { Obek, ObekDegisimYanit } from '../../is/tipler';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { useOnay } from '../../ortak/Onay';
import { useOturum } from '../../depo/oturum';
import { git } from '../../yol/rota';
import { useIsler } from '../isler/depo';
import { kisaAd, ObekNoktasi, TeknikSecici } from '../isler/parcalar';
import { bulunma } from '../isler/dil';
import { MahalleSecici, type MahalleSecimi } from './MahalleSecici';

type Gorunum = 'ana' | 'ekle' | 'sahip' | 'yedek' | 'ad' | 'bol';

export function ObekCekmecesi({ obekId, kapat }: { obekId: number | null; kapat: () => void }) {
  const depo = useIsler();
  const { izinli } = useOturum();
  const bildirim = useBildirim();
  const [onayPenceresi, sor] = useOnay();
  const [gorunum, setGorunum] = useState<Gorunum>('ana');
  const [bekliyor, setBekliyor] = useState(false);
  const [ad, setAd] = useState('');
  const [adHata, setAdHata] = useState<string | null>(null);
  const [bolme, setBolme] = useState<Array<{ mahalleler: string[]; is: number; ad?: string }> | null>(null);
  const duzenler = izinli('obek.duzenle');

  const obek: Obek | undefined = depo.obekler?.obekler.find((o) => o.id === obekId);
  const surum = depo.obekler?.surum ?? 0;

  useEffect(() => {
    setGorunum('ana');
    setBolme(null);
    setAdHata(null);
  }, [obekId]);

  /* Alt görünümde Esc yalnız onu kapatır. */
  useEffect(() => {
    if (gorunum === 'ana') return;
    const tus = (o: KeyboardEvent) => {
      if (o.key === 'Escape' && !document.querySelector('.o-onay')) {
        o.stopImmediatePropagation();
        o.preventDefault();
        setGorunum('ana');
      }
    };
    window.addEventListener('keydown', tus, true);
    return () => window.removeEventListener('keydown', tus, true);
  }, [gorunum]);

  if (!obekId) return null;

  /** Öbek yanıtını depoya yaz ve işleri tazele (öbekleri yeniden çözüldü). */
  const yansit = (y: Pick<ObekDegisimYanit, 'obekler' | 'surum'> & { obekler?: Obek[] }) => {
    if (y.obekler) depo.obekleriYaz(y.obekler, y.surum);
    else void depo.obekleriTazele();
    void depo.tazele();
  };

  const geriAlinabilir = (metin: string, olayId: number | undefined) => {
    if (!olayId) {
      bildirim.goster(metin, 'basari');
      return;
    }
    bildirim.geriAl(metin, async () => {
      try {
        const y = await obekGeriAl(olayId, depo.obekler?.surum ?? 0);
        yansit(y);
        bildirim.goster('Geri alındı.', 'basari');
      } catch (e) {
        bildirim.goster(hataMetni(e), 'uyari');
      }
    });
  };

  const calistir = async (fn: () => Promise<void>) => {
    setBekliyor(true);
    try {
      await fn();
    } catch (e) {
      if (e instanceof IsHatasi && e.kod === 'guncel_degil') {
        void depo.obekleriTazele();
        bildirim.goster('Öbekler siz bakarken değişti; güncel hâli yüklendi. Tekrar deneyin.', 'uyari');
      } else bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  if (!obek) {
    return (
      <Panel acik kapat={kapat} baslik="Öbek" perdesiz>
        {depo.obekler ? <p className="ip-sessiz">Bu öbek bulunamadı; silinmiş olabilir.</p> : <div className="o-iskelet"><span style={{ height: 120 }} /></div>}
      </Panel>
    );
  }

  const cikar = (ref: string, mahalleAdi: string) =>
    calistir(async () => {
      const y = await obekMahalleCikar(obek.id, [ref], surum);
      yansit(y);
      geriAlinabilir(`${mahalleAdi} çıkarıldı${y.etkilenen_is ? ` · ${y.etkilenen_is} iş yeniden çözüldü` : ''}`, y.geri_al_olay_id);
    });

  const ekle = async (s: MahalleSecimi) => {
    await calistir(async () => {
      const y = await obekMahalleEkle(obek.id, {
        mahalle_idler: s.mahalleler.map((m) => m.id),
        tum_ilce: s.ilceler.map((i) => ({ il: i.il, ilce: i.ilce })),
        tasi: s.tasinacak > 0,
        surum,
      });
      yansit(y);
      setGorunum('ana');
      const n = s.mahalleler.length + s.ilceler.length;
      geriAlinabilir(
        `${n} ${n === 1 ? 'seçim' : 'seçim'} ${obek.ad} öbeğine eklendi${y.etkilenen_is ? ` · ${y.etkilenen_is} iş buraya düştü` : ''}`,
        y.geri_al_olay_id,
      );
    });
  };

  const kisiYaz = (alan: 'sahip_id' | 'yedek_id', id: number | null) =>
    calistir(async () => {
      const y = await obekGuncelle(obek.id, { [alan]: id }, surum);
      void depo.obekleriTazele();
      depo.obekleriYaz(
        (depo.obekler?.obekler ?? []).map((o) => (o.id === y.obek.id ? y.obek : o)),
        y.surum,
      );
      setGorunum('ana');
      const kisi = id ? depo.teknikler.find((t) => t.id === id)?.ad : null;
      bildirim.goster(
        alan === 'sahip_id'
          ? kisi
            ? `${obek.ad} öbeğinin ev teknisyeni: ${kisi}. Öneriler buna göre yazıldı.`
            : 'Ev teknisyeni kaldırıldı.'
          : kisi
            ? `Yedek teknisyen: ${kisi}.`
            : 'Yedek kaldırıldı.',
        'basari',
      );
      void depo.tazele();
    });

  const adKaydet = () =>
    calistir(async () => {
      try {
        const y = await obekGuncelle(obek.id, { ad: ad.trim() }, surum);
        depo.obekleriYaz((depo.obekler?.obekler ?? []).map((o) => (o.id === y.obek.id ? y.obek : o)), y.surum);
        setGorunum('ana');
        bildirim.goster(`Öbeğin adı: ${y.obek.ad}`, 'basari');
        void depo.tazele();
      } catch (e) {
        if (e instanceof IsHatasi && e.kod === 'ad_var') {
          setAdHata('Bu adla bir öbek var.');
          return;
        }
        throw e;
      }
    });

  const sil = async () => {
    const evet = await sor({
      baslik: `${obek.ad} öbeği silinsin mi?`,
      metin: `${obek.mahalleler.length} mahallesi öbeksiz kalır; ${obek.acik} iş “Kontrol gerekli”ye düşer. 10 saniye içinde geri alabilirsiniz.`,
      onay: 'Sil',
      yikici: true,
    });
    if (!evet) return;
    await calistir(async () => {
      const y = await obekSil(obek.id, surum);
      yansit(y);
      kapat();
      geriAlinabilir(`${obek.ad} öbeği silindi`, y.geri_al_olay_id);
    });
  };

  const bolOnizle = () =>
    calistir(async () => {
      const y = await obekBol(obek.id, 2, true, surum);
      setBolme(y.parcalar);
      setGorunum('bol');
    });

  const bolUygula = () =>
    calistir(async () => {
      const y = await obekBol(obek.id, 2, false, surum);
      if (y.obekler) depo.obekleriYaz(y.obekler, y.surum);
      else void depo.obekleriTazele();
      void depo.tazele();
      setGorunum('ana');
      bildirim.goster('Öbek ikiye bölündü.', 'basari');
    });

  const toplamMahalle = obek.mahalleler.length;
  const ozet = `${toplamMahalle} mahalle · ${obek.acik} açık iş · ${obek.geciken} geciken · ${obek.btk} BTK`;

  return (
    <>
      <Panel
        acik
        kapat={kapat}
        baslik={
          <span className="ob-baslik">
            <ObekNoktasi renk={obek.renk} /> {obek.ad}
          </span>
        }
        altBaslik={ozet}
        perdesiz
        basSag={
          duzenler && gorunum === 'ana' ? (
            <button
              type="button"
              className="o-dugme kucuk metin"
              onClick={() => {
                setAd(obek.ad);
                setAdHata(null);
                setGorunum('ad');
              }}
            >
              Adı değiştir
            </button>
          ) : undefined
        }
      >
        {gorunum === 'ana' ? (
          <div className="ob-cekmece">
            <div className="ob-ust">
              <button type="button" className="o-dugme kucuk" onClick={() => git(`/yonetici/isler/obek/${obek.id}`)}>
                {obek.acik ? `${obek.acik} açık işi gör ›` : 'İşlerine git ›'}
              </button>
            </div>

            <dl className="ob-kisiler">
              <div>
                <dt>Ev teknisyeni</dt>
                <dd>
                  {obek.sahip ? obek.sahip.ad : <span className="ip-sessiz">Yok — öneri yazılmaz</span>}
                  {duzenler ? (
                    <button type="button" className="o-bag" onClick={() => setGorunum('sahip')}>
                      {obek.sahip ? 'Değiştir' : 'Seç'}
                    </button>
                  ) : null}
                </dd>
              </div>
              <div>
                <dt>Yedek</dt>
                <dd>
                  {obek.yedek ? obek.yedek.ad : <span className="ip-sessiz">—</span>}
                  {duzenler ? (
                    <button type="button" className="o-bag" onClick={() => setGorunum('yedek')}>
                      {obek.yedek ? 'Değiştir' : 'Seç'}
                    </button>
                  ) : null}
                </dd>
              </div>
            </dl>

            <section className="ob-mahalleler">
              <header>
                <h3>Mahalleler</h3>
                {duzenler ? (
                  <button type="button" className="o-dugme kucuk" onClick={() => setGorunum('ekle')}>
                    + Mahalle ekle
                  </button>
                ) : null}
              </header>
              {toplamMahalle ? (
                <ul>
                  {obek.mahalleler.map((m) => (
                    <li key={m.ref}>
                      <span className="yer">
                        <span className="il">
                          {m.il} · {m.ilce} ·
                        </span>{' '}
                        <b>{m.tum_ilce ? 'ilçenin tamamı' : m.mahalle}</b>
                      </span>
                      <span className={`sayi${m.acik ? '' : ' bos'}`}>{m.acik ? `${m.acik} iş` : 'bugün iş yok'}</span>
                      {duzenler ? (
                        <button
                          type="button"
                          className="ob-cikar"
                          aria-label={`${m.tum_ilce ? `${m.ilce} ilçesinin tamamını` : m.mahalle} çıkar`}
                          title="Çıkar"
                          disabled={bekliyor}
                          onClick={() => void cikar(m.ref, m.tum_ilce ? `${m.ilce} (ilçenin tamamı)` : m.mahalle)}
                        >
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <circle cx="12" cy="12" r="9" />
                            <path d="M8 12h8" strokeLinecap="round" />
                          </svg>
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="ob-bos">
                  <p>
                    Bu öbekte mahalle yok. Bursa ve Yalova’nın bütün mahallelerinden seçebilirsiniz; bugün işi olmayanlar da
                    listede.
                  </p>
                  {duzenler ? (
                    <button type="button" className="o-dugme birincil" onClick={() => setGorunum('ekle')}>
                      + Mahalle ekle
                    </button>
                  ) : null}
                </div>
              )}
              {obek.acik === 0 && toplamMahalle ? <p className="ip-not-satiri">Bugün {bulunma(obek.ad)} iş yok. Yeni rapor gelince burada görünür.</p> : null}
            </section>

            {duzenler ? (
              <div className="ob-alt-eylemler">
                <button type="button" className="o-dugme kucuk metin" disabled={bekliyor || toplamMahalle < 2} onClick={() => void bolOnizle()}>
                  Öbeği ikiye böl…
                </button>
                <button type="button" className="o-dugme kucuk yikici-metin" disabled={bekliyor} onClick={() => void sil()}>
                  Öbeği sil
                </button>
              </div>
            ) : null}
          </div>
        ) : null}

        {gorunum === 'ekle' ? (
          <div className="ob-alt">
            <div className="ip-alt-bas">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setGorunum('ana')}>
                ‹ Geri
              </button>
              <h3>Mahalle ekle · {obek.ad}</h3>
            </div>
            <MahalleSecici hedefObek={obek} ekle={ekle} vazgec={() => setGorunum('ana')} />
          </div>
        ) : null}

        {gorunum === 'sahip' || gorunum === 'yedek' ? (
          <div className="ob-alt">
            <div className="ip-alt-bas">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setGorunum('ana')}>
                ‹ Geri
              </button>
              <h3>{gorunum === 'sahip' ? 'Ev teknisyeni' : 'Yedek teknisyen'}</h3>
            </div>
            <p className="ip-not-satiri">
              {gorunum === 'sahip'
                ? 'Bu öbeğe gelen işler bu kişiye önerilir; operasyon çoğunlukla yalnız onaylar.'
                : 'Ev teknisyeni doluysa ya da bugün yoksa öneri yedeğe gider.'}
            </p>
            <TeknikSecici
              teknikler={depo.teknikler}
              deger={(gorunum === 'sahip' ? obek.sahip?.id : obek.yedek?.id) ?? null}
              degisti={(id) => void kisiYaz(gorunum === 'sahip' ? 'sahip_id' : 'yedek_id', id)}
              obekId={obek.id}
            />
            {(gorunum === 'sahip' ? obek.sahip : obek.yedek) ? (
              <button
                type="button"
                className="o-dugme kucuk yikici-metin"
                disabled={bekliyor}
                onClick={() => void kisiYaz(gorunum === 'sahip' ? 'sahip_id' : 'yedek_id', null)}
              >
                {gorunum === 'sahip' ? 'Ev teknisyenini kaldır' : 'Yedeği kaldır'}
              </button>
            ) : null}
          </div>
        ) : null}

        {gorunum === 'ad' ? (
          <div className="ob-alt">
            <div className="ip-alt-bas">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setGorunum('ana')}>
                ‹ Geri
              </button>
              <h3>Adı değiştir</h3>
            </div>
            <label className="o-alan">
              <span className="etiket">Öbeğin adı</span>
              <input
                className="o-girdi"
                value={ad}
                maxLength={80}
                autoFocus
                onChange={(o) => {
                  setAd(o.target.value);
                  setAdHata(null);
                }}
                onKeyDown={(o) => {
                  if (o.key === 'Enter' && ad.trim()) void adKaydet();
                }}
              />
              {adHata ? <span className="ob-hata">{adHata}</span> : null}
            </label>
            <div className="ip-alt-alt">
              <button type="button" className="o-dugme" onClick={() => setGorunum('ana')}>
                Vazgeç
              </button>
              <button type="button" className="o-dugme birincil" disabled={!ad.trim() || ad.trim() === obek.ad || bekliyor} onClick={() => void adKaydet()}>
                Kaydet
              </button>
            </div>
          </div>
        ) : null}

        {gorunum === 'bol' && bolme ? (
          <div className="ob-alt">
            <div className="ip-alt-bas">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setGorunum('ana')}>
                ‹ Geri
              </button>
              <h3>Öbeği ikiye böl</h3>
            </div>
            <p className="ip-not-satiri">Mahalleler iki öbeğe ayrılır; kalıcıdır. İşler yeni öbeklerine düşer.</p>
            <div className="ob-parcalar">
              {bolme.map((p, i) => (
                <section key={i}>
                  <h4>
                    {p.ad ?? `${obek.ad}-${i + 1}`} · {p.is} iş
                  </h4>
                  <p>{p.mahalleler.map((r) => r.split('/').slice(-1)[0].replace('*', 'ilçenin tamamı')).join(', ')}</p>
                </section>
              ))}
            </div>
            <div className="ip-alt-alt">
              <button type="button" className="o-dugme" onClick={() => setGorunum('ana')}>
                Vazgeç
              </button>
              <button type="button" className="o-dugme birincil" disabled={bekliyor} onClick={() => void bolUygula()}>
                İki öbek oluştur
              </button>
            </div>
          </div>
        ) : null}
      </Panel>
      {onayPenceresi}
    </>
  );
}

export { kisaAd };
