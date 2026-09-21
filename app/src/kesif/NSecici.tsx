/**
 * N seçici — kaç satış sorumlusu, o kadar bölge.
 * Yalnız **dengeli** planlarda durur (`dengeliPlanlar(0.01)`): kaydırıcı hiçbir zaman
 * hedefin %1'inden fazla sapan bir plana denk gelmez. 8 = bugünkü ekip, 25 = tam ekip.
 */
import { useMemo } from 'react';

import { planHariciMi } from '../data/load';
import { veri } from '../data/load';
import { dengeliPlanlar, isaretliYuzde, sapmaAraligi } from '../data/selectors';
import type { Plan } from '../data/types';
import { boy, renk, u, yazi } from '../ui/tema';

export interface NSeciciProps {
  plan: Plan;
  n: number;
  onDegis: (n: number) => void;
}

export default function NSecici({ plan, n, onDegis }: NSeciciProps) {
  const liste = useMemo(() => dengeliPlanlar(0.01), [plan]);
  const ekip = veri().meta.ekip.sorumlu_sayisi;
  const i = Math.max(0, liste.indexOf(n));
  const [sMin, sMaks] = sapmaAraligi(plan);
  const disPlan = planHariciMi(n);

  const etiket = n === 8 ? 'bugün' : n === ekip ? 'tam ekip' : 'bölge';
  const konum = (deger: number) => {
    const k = liste.indexOf(deger);
    return k < 0 ? null : (k / Math.max(1, liste.length - 1)) * 100;
  };

  const adim = (yon: number) => {
    const y = Math.min(liste.length - 1, Math.max(0, i + yon));
    if (liste[y] !== n) onDegis(liste[y]);
  };

  return (
    <div style={{ width: u(372), display: 'flex', flexDirection: 'column', gap: u(6) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: u(10) }}>
        <button
          className="ks-dugme"
          style={{ width: u(38), height: u(38), fontSize: u(26), borderRadius: u(10) }}
          onClick={() => adim(-1)}
          disabled={i <= 0}
          title="Daha az bölge"
          aria-label="Daha az bölge"
        >
          −
        </button>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: u(10), minWidth: u(150) }}>
          <span
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 700,
              fontSize: u(50),
              lineHeight: 0.95,
              color: renk.metin,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {n}
          </span>
          <span style={{ fontSize: u(boy.kucuk), color: etiket === 'bölge' ? renk.metin3 : renk.sari }}>{etiket}</span>
        </div>
        <button
          className="ks-dugme"
          style={{ width: u(38), height: u(38), fontSize: u(26), borderRadius: u(10) }}
          onClick={() => adim(1)}
          disabled={i >= liste.length - 1}
          title="Daha çok bölge"
          aria-label="Daha çok bölge"
        >
          +
        </button>
        {disPlan && (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: u(boy.not),
              color: renk.sari,
              border: `1px solid ${renk.sari}66`,
              borderRadius: u(999),
              padding: `${u(3)} ${u(10)}`,
            }}
          >
            dosyadan
          </span>
        )}
      </div>

      <div style={{ position: 'relative', height: u(16), display: 'flex', alignItems: 'center' }}>
        <input
          className="ks-slider"
          type="range"
          min={0}
          max={liste.length - 1}
          step={1}
          value={i}
          onChange={(e) => onDegis(liste[Number(e.target.value)])}
          aria-label="Bölge sayısı"
        />
        {[8, ekip].map((d) => {
          const p = konum(d);
          return p == null ? null : (
            <span
              key={d}
              title={d === 8 ? 'bugünkü ekip' : 'tam ekip'}
              style={{
                position: 'absolute',
                left: `${p}%`,
                top: u(-3),
                width: u(3),
                height: u(12),
                marginLeft: u(-1.5),
                borderRadius: u(2),
                background: n === d ? renk.sari : 'rgba(255,255,255,0.45)',
                pointerEvents: 'none',
              }}
            />
          );
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: u(boy.not), color: renk.metin3 }}>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>
          sapma {isaretliYuzde(sMin)} … {isaretliYuzde(sMaks)}
        </span>
        <span>
          {liste[0]}–{liste[liste.length - 1]} bölge
        </span>
      </div>
    </div>
  );
}
