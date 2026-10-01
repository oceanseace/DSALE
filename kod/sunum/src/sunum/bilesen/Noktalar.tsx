/**
 * İlerleme noktaları: 10 sahne, etkin olan sarı hap. Sahne içinde birden çok adım varsa
 * hapın içinde ince bir alt gösterge belirir. Film modunda altta saç teli inceliğinde
 * bir zaman çubuğu akar.
 */
import { renk, u } from '../../ui/tema';

export interface NoktalarProps {
  sahne: number;
  sahneSayisi: number;
  adim: number;
  adimSayisi: number;
  film: boolean;
  /** etkin adımın film ilerlemesi 0..1 */
  filmOran: number;
  adlar?: string[];
}

export default function Noktalar({ sahne, sahneSayisi, adim, adimSayisi, film, filmOran, adlar }: NoktalarProps) {
  const noktalar = Array.from({ length: sahneSayisi }, (_, i) => i + 1);
  return (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        bottom: u(40),
        transform: 'translateX(-50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: u(10),
        pointerEvents: 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: u(10) }}>
        {noktalar.map((no) => {
          const etkin = no === sahne;
          return (
            <div
              key={no}
              title={adlar?.[no - 1]}
              style={{
                width: etkin ? u(56) : u(12),
                height: u(12),
                borderRadius: u(999),
                background: etkin ? renk.sari : 'rgba(244,247,255,0.28)',
                boxShadow: etkin ? `0 0 ${u(16)} ${renk.sari}88` : undefined,
                transition: 'width 320ms cubic-bezier(0.22,1,0.36,1), background 320ms linear',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {etkin && adimSayisi > 1 && (
                // kalan adımlar koyu kalır: dolu kısım sahnenin kaçıncı adımında olduğumuzu gösterir
                <div
                  style={{
                    position: 'absolute',
                    left: `${(adim / adimSayisi) * 100}%`,
                    right: 0,
                    top: 0,
                    bottom: 0,
                    background: 'rgba(3,6,13,0.55)',
                    transition: 'left 320ms cubic-bezier(0.22,1,0.36,1)',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
      {film && (
        <div style={{ width: u(320), height: u(3), background: 'rgba(244,247,255,0.16)', borderRadius: u(3) }}>
          <div
            style={{
              width: `${Math.round(filmOran * 100)}%`,
              height: '100%',
              background: renk.sari,
              borderRadius: u(3),
            }}
          />
        </div>
      )}
    </div>
  );
}
