/**
 * Ekiplere dağıt (§6.4 son madde; eski "Böl (binaya göre)"): teknisyenleri seç
 * (varsayılan: öbeğin teknisyeni + bugün boşta olanlar) → önizleme (kişi başına
 * iş, BTK, km; aynı bina bölünmez) → [Önerileri güncelle]. Atama yapılmaz;
 * atama toplu karttaki "Ata" (önerileri onayla) iledir. Sayfa yeniden dizilmez.
 */

import { useEffect, useMemo, useState } from 'react';
import { dagitOnizle, dagitUygula, hataMetni } from '../../is/api';
import type { DagitOnizleme, IsSatir, Obek } from '../../is/tipler';
import { Panel } from '../../ortak/Panel';
import { useBildirim } from '../../ortak/Bildirim';
import { useIsler } from './depo';
import { kisaAd } from './parcalar';

export function DagitPaneli({ acik, kapat, obek, isler }: { acik: boolean; kapat: () => void; obek: Obek | null; isler: IsSatir[] }) {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [secili, setSecili] = useState<number[]>([]);
  const [onizleme, setOnizleme] = useState<DagitOnizleme | null>(null);
  const [bekliyor, setBekliyor] = useState(false);

  const atanmamis = useMemo(
    () => isler.filter((x) => x.kova === 'atanmadi' && (x.durum === 'bekliyor' || x.durum === 'randevulu')),
    [isler],
  );

  /* Varsayılan seçim: öbeğin ev teknisyeni + yedeği + bugün en boş iki kişi. */
  useEffect(() => {
    if (!acik) return;
    setOnizleme(null);
    const ilk = new Set<number>();
    if (obek?.sahip) ilk.add(obek.sahip.id);
    if (obek?.yedek) ilk.add(obek.yedek.id);
    const bos = [...depo.teknikler]
      .filter((t) => !t.bugun_yok)
      .sort((a, b) => a.bugun.atanan / Math.max(1, a.kapasite) - b.bugun.atanan / Math.max(1, b.kapasite));
    for (const t of bos) {
      if (ilk.size >= Math.max(2, Math.min(4, Math.ceil(atanmamis.length / 12)))) break;
      ilk.add(t.id);
    }
    setSecili([...ilk]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acik, obek?.id]);

  const onizle = async () => {
    if (!obek || !secili.length) return;
    setBekliyor(true);
    try {
      setOnizleme(await dagitOnizle(obek.id, secili));
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  const uygula = async () => {
    if (!obek || !onizleme) return;
    setBekliyor(true);
    try {
      const surumler = Object.fromEntries(atanmamis.map((x) => [x.is_no, x.surum]));
      const y = await dagitUygula(obek.id, secili, surumler);
      void depo.tazele();
      bildirim.goster(
        `Öneriler güncellendi: ${y.yazilan.length} iş ${secili.length} teknisyene. Atamak için “Ata”ya basın.${
          y.atlanan.length ? ` (${y.atlanan.length} iş o arada değiştiği için atlandı)` : ''
        }`,
        'basari',
        { sureMs: 7000 },
      );
      kapat();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  const ad = (id: number) => depo.teknikler.find((t) => t.id === id)?.ad ?? `#${id}`;

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik={`Ekiplere dağıt${obek ? ` · ${obek.ad}` : ''}`}
      altBaslik={`${atanmamis.length} atanmamış iş yakınlığa göre paylaştırılır; aynı binadaki işler bölünmez.`}
      alt={
        <>
          <button type="button" className="o-dugme" onClick={kapat} disabled={bekliyor}>
            Vazgeç
          </button>
          {onizleme ? (
            <button type="button" className="o-dugme birincil" onClick={() => void uygula()} disabled={bekliyor}>
              Önerileri güncelle
            </button>
          ) : (
            <button type="button" className="o-dugme birincil" onClick={() => void onizle()} disabled={bekliyor || !secili.length || !atanmamis.length}>
              {bekliyor ? 'Hesaplanıyor…' : 'Önizle'}
            </button>
          )}
        </>
      }
    >
      <div className="ip-dagit">
        <p className="ip-alan-etiket">Teknisyenler</p>
        <div className="ip-secim-liste coklu" role="group" aria-label="Teknisyenler">
          {depo.teknikler.map((t) => {
            const var_ = secili.includes(t.id);
            return (
              <label key={t.id} className={var_ ? 'secili' : undefined}>
                <input
                  type="checkbox"
                  checked={var_}
                  onChange={() => {
                    setOnizleme(null);
                    setSecili((s) => (s.includes(t.id) ? s.filter((x) => x !== t.id) : [...s, t.id]));
                  }}
                />
                <span className="ad">{t.ad}</span>
                <span className="bilgi">
                  {obek && t.obekler.some((o) => o.id === obek.id) ? 'öbeğin · ' : ''}bugün {t.bugun.atanan}/{t.kapasite}
                  {t.bugun_yok ? ' · bugün yok' : ''}
                  {t.giris_var === false ? ' · BOSS Mobil' : ''}
                </span>
              </label>
            );
          })}
        </div>
        {onizleme ? (
          <ul className="ip-dagit-sonuc" aria-label="Önizleme">
            {onizleme.gruplar.map((g) => (
              <li key={g.teknik_id}>
                <span className="ad">{kisaAd(ad(g.teknik_id))}</span>
                <span className="sayi">{g.is_nolar.length} iş</span>
                <span className="sayi">{g.btk} BTK</span>
                <span className="sayi">≈{g.km.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} km</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </Panel>
  );
}
