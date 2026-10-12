/**
 * İş seçicisi: ticket'ın hangi iş(ler) için açıldığını seçtirir (toptan müşteride tek müşteri no'nun yüzlerce işi
 * olur; bir lokasyonda birden çok abone etkilenebilir). Satır: ☐ · Task No · Task adı (⚠ kanal şikâyeti, TASKS'taki
 * gibi) · Satış kanalı · BOSS durumu · Adres · Müşteri No. Ara kutusu bütün sütunlarda arar; "Hepsini seç" yalnız
 * görünenleri (aramaya uyanları) seçer. Veri: `GET /api/ticket/isler` (`cekirdek/ticket/api.ts isSecenekleri`).
 * Çağıranlar: YeniSatir.tsx (yeni ticket) · TicketAyrinti.tsx ("+ abone ekle").
 */

import { useMemo, useState } from 'react';
import type { TicketIsi } from '../../../cekirdek/ticket/api';

const ara = (x: TicketIsi) =>
  [x.task_no, x.task_adi, x.satis_kanali, x.boss_durum, x.adres, x.musteri_no, x.lokasyon].join(' ').toLocaleLowerCase('tr-TR');

export function IsSecici({
  isler,
  secili,
  degistir,
  fazla = false,
  devreDisi,
}: {
  isler: TicketIsi[];
  secili: Set<string>;
  degistir: (yeni: Set<string>) => void;
  fazla?: boolean;
  /** Bu task no'lar zaten ticket'ta: işaretli ve kilitli görünür. */
  devreDisi?: Set<string>;
}) {
  const [q, setQ] = useState('');
  const gorunen = useMemo(() => {
    const s = q.trim().toLocaleLowerCase('tr-TR');
    return s ? isler.filter((x) => ara(x).includes(s)) : isler;
  }, [isler, q]);
  const musteriVar = isler.some((x) => x.musteri_no);
  const adresVar = isler.some((x) => x.adres);
  const secilebilir = gorunen.filter((x) => !devreDisi?.has(x.task_no));
  const hepsiSecili = secilebilir.length > 0 && secilebilir.every((x) => secili.has(x.task_no));

  const cevir = (no: string) => {
    const y = new Set(secili);
    if (y.has(no)) y.delete(no);
    else y.add(no);
    degistir(y);
  };
  const hepsi = () => {
    const y = new Set(secili);
    for (const x of secilebilir) {
      if (hepsiSecili) y.delete(x.task_no);
      else y.add(x.task_no);
    }
    degistir(y);
  };

  if (!isler.length) return <p className="tk-is-bos">Açık iş bulunamadı.</p>;

  return (
    <div className="tk-is-secici">
      <div className="tk-is-ust">
        <input
          className="tk-is-ara"
          type="search"
          value={q}
          placeholder={`Ara (${isler.length.toLocaleString('tr-TR')} iş): Task No, Task adı, kanal, adres…`}
          aria-label="İşlerde ara"
          autoComplete="off"
          onChange={(o) => setQ(o.target.value)}
          onKeyDown={(o) => {
            if (o.key === 'Enter') o.preventDefault();
            o.stopPropagation();
          }}
        />
        <button type="button" className="yd" onClick={hepsi} disabled={!secilebilir.length}>
          {hepsiSecili ? 'Hiçbiri' : q.trim() ? `Görünenleri seç (${secilebilir.length})` : 'Hepsini seç'}
        </button>
        <span className="tk-is-sayi">
          {secili.size.toLocaleString('tr-TR')} seçili{fazla ? ' · ilk 500 iş gösteriliyor' : ''}
        </span>
      </div>
      <div className="tk-is-liste" role="group" aria-label="Açık işler">
        <table>
          <thead>
            <tr>
              <th aria-label="Seç" />
              <th>Task No</th>
              <th>Task adı</th>
              <th>Satış kanalı</th>
              <th>BOSS durumu</th>
              {adresVar ? <th>Adres</th> : null}
              {musteriVar ? <th>Müşteri No</th> : null}
            </tr>
          </thead>
          <tbody>
            {gorunen.map((x) => {
              const kilitli = devreDisi?.has(x.task_no) ?? false;
              const isaretli = kilitli || secili.has(x.task_no);
              return (
                <tr
                  key={x.task_no}
                  className={`${isaretli ? 'secili' : ''}${x.kanal_sikayeti ? ' sikayet' : ''}`}
                  onClick={() => !kilitli && cevir(x.task_no)}
                >
                  <td>
                    <input
                      type="checkbox"
                      checked={isaretli}
                      disabled={kilitli}
                      aria-label={`Task ${x.task_no}`}
                      onClick={(o) => o.stopPropagation()}
                      onChange={() => cevir(x.task_no)}
                    />
                  </td>
                  <td className="no">{x.task_no}</td>
                  <td title={x.uyari || undefined}>
                    {x.uyari ? (
                      <span className="tk-uyari" aria-label={x.uyari}>
                        ⚠{' '}
                      </span>
                    ) : null}
                    {x.task_adi || '—'}
                    {x.kurulum && !x.kanal_sikayeti ? <span className="tk-is-etiket">kurulum</span> : null}
                  </td>
                  <td>{x.satis_kanali || '—'}</td>
                  <td>{x.boss_durum || '—'}</td>
                  {adresVar ? <td className="adres">{x.adres}</td> : null}
                  {musteriVar ? <td className="no">{x.musteri_no}</td> : null}
                </tr>
              );
            })}
          </tbody>
        </table>
        {!gorunen.length ? <p className="tk-is-bos">Aramaya uyan iş yok.</p> : null}
      </div>
    </div>
  );
}
