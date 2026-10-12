/**
 * "İlişkili işleri de dahil et (N)": Ata ve Askıya al formunda (İş çekmecesi, TASKS toplu, MAP kement/dikdörtgen)
 * seçili işlerin aynı müşterideki öbür AÇIK işleri (kanal şikâyeti ↔ kurulum/bağlantı …; İlişkili akış sütunuyla aynı
 * ilişki). Yalnız perakende müşteri: toptan (tek müşteri no çok abone) genişletilmez. Her ilişkili işin KENDİ kutusu
 * var (varsayılan işaretli — Administrator Ayarlar ▸ "İlişkili işleri dahil et"); kullanıcı "onu atamayalım" diye tek
 * tek kaldırabilir, üstteki kutu hepsini açar/kapatır. Düğmedeki sayı yalnız işaretlileri sayar (`ekler`).
 * Sunucu: `POST /api/isler/iliskili/isler`.
 * Giriş: `useIliskili(acik, nolar)` → { ekler (işaretliler), govde }. Çağıranlar: TopluAta.tsx, TopluAski.tsx.
 */

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { iliskiliIsler } from '../../../cekirdek/is/api';
import { DURUM_ETIKET, type Durum, type IliskiliIs } from '../../../cekirdek/is/tipler';

/** Seçime eklenecek ilişkili işler: seçimde olanlar, tekrarlar ve kullanıcının kutusunu kaldırdıkları (`haric`)
 * atılır (sunucu da seçimdekileri atar; sıra korunur). */
export function ekleriAyikla(seciliNolar: string[], ekler: IliskiliIs[], haric?: ReadonlySet<string>): IliskiliIs[] {
  const gorulen = new Set(seciliNolar);
  return ekler.filter((x) => (gorulen.has(x.is_no) || haric?.has(x.is_no) ? false : (gorulen.add(x.is_no), true)));
}

/** Üst kutunun hâli: hepsi işaretli / bazıları / hiçbiri (liste boşsa 'hic'). */
export function topluIsaret(nolar: readonly string[], haric: ReadonlySet<string>): 'hepsi' | 'kismi' | 'hic' {
  const kalan = nolar.filter((n) => !haric.has(n)).length;
  return !nolar.length || !kalan ? 'hic' : kalan === nolar.length ? 'hepsi' : 'kismi';
}

/** Tek işin kutusu değişti: yeni hariç kümesi (değişmez; React durumu için yeni nesne). */
export function haricDegistir(haric: ReadonlySet<string>, no: string, isaretli: boolean): Set<string> {
  const y = new Set(haric);
  if (isaretli) y.delete(no);
  else y.add(no);
  return y;
}

export interface Iliskili {
  /** Gönderime eklenecek işler (yalnız kutusu işaretli olanlar). */
  ekler: IliskiliIs[];
  /** Bulunan ilişkili işlerin hepsi (kutusu işaretsiz olsa da). */
  hepsi: IliskiliIs[];
  /** En az bir ilişkili iş işaretli mi. */
  dahil: boolean;
  govde: ReactNode;
}

/** Üç hâlli kutu (hepsi / bazıları / hiçbiri). */
function UcHalliKutu({ hal, degis }: { hal: 'hepsi' | 'kismi' | 'hic'; degis: (isaretli: boolean) => void }) {
  return (
    <input
      type="checkbox"
      checked={hal === 'hepsi'}
      ref={(el) => {
        if (el) el.indeterminate = hal === 'kismi';
      }}
      onChange={(o) => degis(o.target.checked)}
    />
  );
}

export function useIliskili(acik: boolean, nolar: string[]): Iliskili {
  const [liste, setListe] = useState<IliskiliIs[]>([]);
  const [toptan, setToptan] = useState(0);
  const [haric, setHaric] = useState<Set<string>>(() => new Set());
  const imza = nolar.join(',');
  useEffect(() => {
    if (!nolar.length) setListe([]);
    if (!acik || !nolar.length) return undefined;     // gönderim sürerken / bitince liste durur (özet task no'ları)
    let iptal = false;
    iliskiliIsler(nolar.slice(0, 500))
      .then((y) => {
        if (iptal) return;
        setListe(y.isler);
        setToptan(y.toptan_atlanan);
        // varsayılan: hepsi işaretli (Ayarlar kapalıysa hiçbiri); kullanıcı tek tek kaldırır
        setHaric(y.varsayilan ? new Set() : new Set(y.isler.map((x) => x.is_no)));
      })
      .catch(() => !iptal && setListe([]));
    return () => {
      iptal = true;
    };
    // imza: seçim değişince
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acik, imza]);

  const ekler = useMemo(() => ekleriAyikla(nolar, liste, haric), [haric, liste, imza]); // eslint-disable-line react-hooks/exhaustive-deps
  const hal = topluIsaret(
    liste.map((x) => x.is_no),
    haric,
  );
  const sayi = (n: number) => n.toLocaleString('tr-TR');
  const govde =
    liste.length || toptan ? (
      <div className="ta-alan ta-iliskili">
        {liste.length ? (
          <label className="ta-iliskili-kutu">
            <UcHalliKutu hal={hal} degis={(v) => setHaric(v ? new Set() : new Set(liste.map((x) => x.is_no)))} />
            <span>
              İlişkili işleri de dahil et ({hal === 'kismi' ? `${sayi(ekler.length)}/${sayi(liste.length)}` : sayi(liste.length)})
              <small>Aynı müşterinin öbür açık işleri birlikte gider; istemediğinizin işaretini kaldırın</small>
            </span>
          </label>
        ) : null}
        {liste.length ? (
          <ul className="ta-iliskili-liste">
            {liste.map((x) => {
              const isaretli = !haric.has(x.is_no);
              return (
                <li key={x.is_no} className={isaretli ? undefined : 'soluk'}>
                  <label className="ta-iliskili-is">
                    <input
                      type="checkbox"
                      checked={isaretli}
                      onChange={(o) => setHaric((h) => haricDegistir(h, x.is_no, o.target.checked))}
                      aria-label={`${x.task_no} dahil`}
                    />
                    <span>
                      <b>{x.task_no}</b> {x.task_adi}
                      <span className="ta-not">
                        {' · '}
                        {DURUM_ETIKET[x.durum as Durum] ?? x.durum}
                        {x.atanan ? ` · ${x.atanan}` : ''}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        ) : null}
        {toptan ? <p className="ta-not">Toptan müşteri: ilişkili işleri eklenmez.</p> : null}
      </div>
    ) : null;
  return { ekler, hepsi: liste, dahil: ekler.length > 0, govde };
}
