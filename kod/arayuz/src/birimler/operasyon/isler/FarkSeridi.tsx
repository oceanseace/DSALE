/**
 * TASKS değişiklik şeridi (GitHub'daki commit akışı gibi): tablonun üstünde tek satır
 * "Son eşitleme 10:38 · +3 yeni · 2 değişti · 1 kapandı". Tıklayınca son eşitlemelerin listesi açılır; her
 * eşitlemede yeni / değişen / kapanan task no'ları; task no'ya basınca tabloda o satıra gidilir (`git`).
 * Veri: `GET /api/boss/farklar` (yalnız task no; kişisel veri yok), sekme görünürken 30 sn'de bir.
 * Uç yoksa (404) ya da izin yoksa şerit hiç görünmez. Kim: Isler.tsx.
 */

import { disariDinle } from '../../../cekirdek/ortak/disariKapat';
import { useEffect, useMemo, useRef, useState } from 'react';
import { bossFarklar, type BossFark } from '../../../cekirdek/is/api';
import type { IsSatir } from '../../../cekirdek/is/tipler';

const YOKLAMA_MS = 30000;
const saat = (z: string) => (z || '').slice(11, 16) || z;
const gun = (z: string) => {
  const [y, a, g] = (z || '').slice(0, 10).split('-');
  return g ? `${g}.${a}.${y}` : '';
};
const bosMu = (f: BossFark) => !f.yeni.length && !f.degisen.length && !f.kapanan.length;

export function FarkSeridi({
  isler,
  git,
  tazelemeAnahtari,
  gorundu,
}: {
  /** Açık işler (task no → ad ipucu ve "tabloda var mı"). */
  isler: IsSatir[];
  /** Task no'ya basınca: tabloda o satıra git. */
  git: (taskNo: string) => void;
  /** Değişince (yeni değişim imleci) şerit hemen tazelenir. */
  tazelemeAnahtari?: unknown;
  /** Şerit görünür/gizli olunca (tablo yüksekliği yeniden ölçülsün). */
  gorundu?: (var_: boolean) => void;
}) {
  const [farklar, setFarklar] = useState<BossFark[] | null>(null);
  const [acik, setAcik] = useState(false);
  const kok = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let bitti = false;
    const yukle = () => {
      if (document.visibilityState !== 'visible') return;
      bossFarklar()
        .then((f) => !bitti && setFarklar(f))
        .catch(() => undefined);
    };
    yukle();
    const t = window.setInterval(yukle, YOKLAMA_MS);
    return () => {
      bitti = true;
      window.clearInterval(t);
    };
  }, [tazelemeAnahtari]);

  useEffect(() => (acik ? disariDinle(kok, () => setAcik(false)) : undefined), [acik]);

  const gorunur = Boolean(farklar && farklar.length);
  useEffect(() => {
    gorundu?.(gorunur);
  }, [gorunur, gorundu]);

  const adlar = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of isler) m.set(s.boss_task_no ?? s.is_no, s.task_adi ?? '');
    return m;
  }, [isler]);

  if (!farklar || !farklar.length) return null;
  const son = farklar[0];
  const dolu = farklar.filter((f) => !bosMu(f)).slice(0, 25);

  const no = (n: string, tur: 'yeni' | 'degisen' | 'kapanan') => (
    <button
      key={`${tur}-${n}`}
      type="button"
      className={`xg-fark-no ${tur}`}
      title={adlar.get(n) ? `${n} · ${adlar.get(n)}` : tur === 'kapanan' ? `${n} · kapandı` : n}
      onClick={() => {
        git(n);
        setAcik(false);
      }}
    >
      {tur === 'yeni' ? '+' : tur === 'degisen' ? '~' : '−'}
      {n}
    </button>
  );

  return (
    <div className="xg-fark" ref={kok}>
      <button type="button" className="xg-fark-serit" aria-expanded={acik} onClick={() => setAcik((a) => !a)}>
        <span className="xg-fark-nokta" aria-hidden="true" />
        <span>
          Son eşitleme <b>{saat(son.zaman)}</b>
        </span>
        {bosMu(son) ? (
          <span className="xg-fark-sessiz">değişiklik yok</span>
        ) : (
          <>
            {son.yeni.length ? <span className="xg-fark-sayi yeni">+{son.yeni.length} yeni</span> : null}
            {son.degisen.length ? <span className="xg-fark-sayi degisen">{son.degisen.length} değişti</span> : null}
            {son.kapanan.length ? <span className="xg-fark-sayi kapanan">{son.kapanan.length} kapandı</span> : null}
          </>
        )}
        <span className="xg-fark-ok" aria-hidden="true">
          ▾
        </span>
      </button>
      {acik ? (
        <div className="xg-acilir xg-fark-liste" role="dialog" aria-label="Son eşitlemelerdeki değişiklikler">
          {!dolu.length ? <div className="xg-not">Son eşitlemelerde değişiklik yok.</div> : null}
          {dolu.map((f) => (
            <section key={f.no} className="xg-fark-kayit">
              <header>
                <b>{saat(f.zaman)}</b> <span>{gun(f.zaman)}</span>
                <span className="xg-fark-ozet">
                  {f.yeni.length ? `+${f.yeni.length} yeni` : ''}
                  {f.degisen.length ? ` · ${f.degisen.length} değişti` : ''}
                  {f.kapanan.length ? ` · ${f.kapanan.length} kapandı` : ''}
                </span>
              </header>
              <div className="xg-fark-nolar">
                {f.yeni.slice(0, 60).map((n) => no(n, 'yeni'))}
                {f.degisen.slice(0, 60).map((n) => no(n, 'degisen'))}
                {f.kapanan.slice(0, 60).map((n) => no(n, 'kapanan'))}
                {f.yeni.length + f.degisen.length + f.kapanan.length > 180 ? <span className="xg-not">… ve daha fazlası</span> : null}
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </div>
  );
}
