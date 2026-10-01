/**
 * Takip → Satış bölümü (F15; yalnız yönetici, `GET /api/takip/satis`).
 *
 * Tek satır özet: "Bugün 142 ziyaret · 11 satış · 7/8 satışçı · Hafta 31/60".
 * Altında huni (ziyaret → temas → satış), satışçı satırları ve "Altyapısı
 * çözülen bina". Sayılar sunucudan AYNEN yazılır (Canlı durum ve gün özetiyle
 * aynı tanım: iptal edilen ziyaret sayılmaz). Gösterim verisi dahilse hap.
 * [Satış ›] Canlı durumu açar.
 */

import { useMemo } from 'react';
import { git } from '../../yol/rota';
import { useVeri } from '../ortak/parcalar';
import { HataKutusu, Iskelet } from '../../ortak/Bos';
import { Hap } from '../../ortak/Rozet';
import { sayi, yuzde } from '../../ortak/bicim';
import { takipSatis } from './api';

export function SatisBolumu({ gun }: { gun: number }) {
  const hafta = Math.max(7, gun);
  const v = useVeri(() => takipSatis(hafta), [hafta], 60_000);
  const s = v.veri;
  const satirlar = useMemo(
    () =>
      [...(s?.satiscilar ?? [])].sort(
        (a, b) => b.bugun_ziyaret - a.bugun_ziyaret || b.hafta_satis - a.hafta_satis || a.ad.localeCompare(b.ad, 'tr'),
      ),
    [s],
  );
  const donem = hafta === 7 ? 'Hafta' : `${hafta} gün`;

  return (
    <section className="tp-bolum" aria-labelledby="tp-satis">
      <div className="tp-bolum-bas">
        <h2 id="tp-satis">Satış</h2>
        {s?.demo_dahil ? (
          <Hap renk="amber" baslik="Bu sayılar gösterim (demo) ziyaretlerini de içeriyor.">
            Gösterim verisi
          </Hap>
        ) : null}
        <button type="button" className="o-dugme kucuk tp-bolum-eylem" onClick={() => git('/yonetici/canli')}>
          Canlı durum ›
        </button>
      </div>
      {v.hata && !s ? <HataKutusu mesaj={v.hata} tekrar={v.yenile} /> : null}
      {!s ? (
        v.hata ? null : <Iskelet satir={3} yukseklik={44} />
      ) : (
        <>
          <p className="tp-satis-ozet">
            <span>
              Bugün <strong>{sayi(s.bugun.ziyaret)}</strong> ziyaret
            </span>
            <span>
              <strong>{sayi(s.bugun.satis)}</strong> satış
            </span>
            <span>
              <strong>
                {sayi(s.bugun.aktif_satisci)}/{sayi(s.bugun.toplam_satisci)}
              </strong>{' '}
              satışçı sahada
            </span>
            <span>
              {donem} <strong>{sayi(s.hafta.satis)}</strong>
              {s.hafta.hedef ? ` / ${sayi(s.hafta.hedef)} hedef` : ' satış'}
            </span>
          </p>
          {s.hafta.hedef && s.hafta.ilerleme != null ? (
            <div
              className="tp-olcer ince"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(Math.min(1, s.hafta.ilerleme) * 100)}
              aria-label={`Haftalık hedefin ${yuzde(s.hafta.ilerleme)} kadarı`}
            >
              <span style={{ width: `${Math.min(100, Math.round(s.hafta.ilerleme * 100))}%` }} />
            </div>
          ) : null}

          <Huni ziyaret={s.huni.ziyaret} temas={s.huni.temas} satis={s.huni.satis} donem={donem} />

          {s.altyapisi_cozulen_bina ? (
            <p className="tp-dipnot">
              Altyapısı çözülen bina: <strong>{sayi(s.altyapisi_cozulen_bina)}</strong> (ticket çözüldükten sonra satış yapıldı)
            </p>
          ) : null}

          {satirlar.length ? (
            <div className="yon-tablo-sarmal">
              <table className="yon-tablo satirlasir tp-tablo">
                <thead>
                  <tr>
                    <th>Satışçı</th>
                    <th className="sayi">Bölge</th>
                    <th className="sayi">Bugün ziyaret</th>
                    <th className="sayi">Bugün satış</th>
                    <th className="sayi">{donem} ziyaret</th>
                    <th className="sayi">{donem} satış</th>
                    <th className="sayi">Dönüşüm</th>
                  </tr>
                </thead>
                <tbody>
                  {satirlar.map((r) => (
                    <tr key={r.id} className={r.bugun_ziyaret ? undefined : 'soluk'}>
                      <td className="ad-hucre">{r.ad}</td>
                      <td className="sayi" data-etiket="Bölge">{r.bolge ?? '—'}</td>
                      <td className="sayi" data-etiket="Bugün ziyaret">{sayi(r.bugun_ziyaret)}</td>
                      <td className="sayi" data-etiket="Bugün satış">{sayi(r.bugun_satis)}</td>
                      <td className="sayi" data-etiket={`${donem} ziyaret`}>{sayi(r.hafta_ziyaret)}</td>
                      <td className="sayi" data-etiket={`${donem} satış`}>{sayi(r.hafta_satis)}</td>
                      <td className="sayi" data-etiket="Dönüşüm">{r.donusum == null ? '—' : yuzde(r.donusum, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="tp-bos">Satış görevli kişi yok.</p>
          )}
        </>
      )}
    </section>
  );
}

/** Huni: ziyaret → temas → satış. Çubuk uzunluğu ziyarete oranlı; oranlar yazıyla da verilir. */
function Huni({ ziyaret, temas, satis, donem }: { ziyaret: number; temas: number; satis: number; donem: string }) {
  if (!ziyaret) return <p className="tp-bos">{donem} içinde ziyaret kaydı yok.</p>;
  const adimlar = [
    { ad: 'Ziyaret', n: ziyaret, oran: null as number | null },
    { ad: 'Temas', n: temas, oran: temas / ziyaret },
    { ad: 'Satış', n: satis, oran: temas ? satis / temas : null },
  ];
  return (
    <ol className="tp-huni" aria-label={`${donem} satış hunisi`}>
      {adimlar.map((a) => (
        <li key={a.ad}>
          <span className="ad">{a.ad}</span>
          <span className="cubuk" aria-hidden="true">
            <span style={{ width: `${Math.max(2, Math.round((a.n / ziyaret) * 100))}%` }} />
          </span>
          <span className="deger">
            {sayi(a.n)}
            {a.oran != null ? <small> · {yuzde(a.oran)}</small> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}
