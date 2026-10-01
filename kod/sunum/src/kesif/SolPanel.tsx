/**
 * Sol panel — bölge listesi. Aynı zamanda "Bölge" renk modunun lejantıdır.
 * Sapma nötr gösterilir (✓ / ▲ / ▼ + yazı rengi); bölge renginin yanına dolgulu
 * yeşil/kırmızı rozet konmaz.
 */
import { enBuyukFarkHane, isaretliYuzde, sapmaAraligi, sayi } from '../data/selectors';
import type { Plan } from '../data/types';
import { boy, bosluk, durumIsareti, renk, u, yazi } from '../ui/tema';
import type { Metrik } from './durum';

export interface SolPanelProps {
  plan: Plan;
  secBolge: number | null;
  onSec: (no: number) => void;
  onTumu: () => void;
  /** haritanın renk modu — 'bolge' dışında liste lejant olmaktan çıkar */
  metrik?: Metrik;
}

export default function SolPanel({ plan, secBolge, onSec, onTumu, metrik = 'bolge' }: SolPanelProps) {
  // Fırsat/Penetrasyon modunda harita ısı rampasıyla boyanıyor; listedeki bölge renkleri o an
  // ekranda hiçbir şeye karşılık gelmiyor ve aynı anda iki renk dili konuşulmuş oluyordu.
  const lejantMi = metrik === 'bolge';
  const [sMin, sMaks] = sapmaAraligi(plan);
  const n = plan.n;
  // n ≤ 10 (sunum planı): iki satırlı zengin satır. Üstünde tek satır, kırpılma olmasın diye.
  const ikiSatir = n <= 10;
  const satirY = ikiSatir ? 64 : n <= 20 ? 46 : 38;

  return (
    <div className="ks-cam" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1, padding: u(18) }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: u(10) }}>
        <span style={{ fontFamily: yazi.baslik, fontWeight: 700, fontSize: u(38), lineHeight: 1, color: renk.metin }}>
          {n}
        </span>
        <span
          style={{
            fontFamily: yazi.baslik,
            fontWeight: 600,
            fontSize: u(26),
            letterSpacing: '0.14em',
            color: renk.metin2,
          }}
        >
          BÖLGE
        </span>
        {secBolge != null && (
          <button
            className="ks-dugme"
            style={{ marginLeft: 'auto', padding: `${u(6)} ${u(14)}`, fontSize: u(boy.not), borderRadius: u(999) }}
            onClick={onTumu}
            title="Seçimi kaldır, tüm bölgelere dön"
          >
            Tümü
          </button>
        )}
      </div>

      <div style={{ fontSize: u(boy.kucuk), color: renk.metin2, marginTop: u(6), fontVariantNumeric: 'tabular-nums' }}>
        Hedef {sayi(plan.hedef)} hane · bölge başına
      </div>
      <div
        style={{
          fontSize: u(boy.not),
          color: renk.metin3,
          marginTop: u(2),
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        sapma {isaretliYuzde(sMin)} … {isaretliYuzde(sMaks)} · hedeften en çok {sayi(enBuyukFarkHane(plan))} hane
      </div>

      <div
        className="ks-kaydir"
        style={{
          marginTop: u(bosluk.s),
          display: 'flex',
          flexDirection: 'column',
          gap: u(4),
          flex: 1,
          minHeight: 0,
          paddingRight: u(4),
          maskImage: 'linear-gradient(180deg, #000 0, #000 calc(100% - 18px), transparent 100%)',
        }}
      >
        {plan.bolgeler.map((b) => {
          const secili = secBolge === b.bolge;
          const d = durumIsareti(b.sapma);
          return (
            <button
              key={b.bolge}
              className="ks-satir"
              onClick={() => onSec(b.bolge)}
              title={b.ad}
              style={{
                height: u(satirY),
                padding: `0 ${u(10)}`,
                background: secili ? `${b.renk}22` : undefined,
                borderColor: secili ? `${b.renk}99` : 'transparent',
                opacity: secBolge == null || secili ? 1 : 0.62,
              }}
            >
              <span
                style={{
                  width: u(5),
                  height: u(satirY * 0.56),
                  borderRadius: u(3),
                  background: lejantMi || secili ? b.renk : renk.cizgi,
                  boxShadow: lejantMi || secili ? `0 0 ${u(12)} ${b.renk}99` : 'none',
                  flex: '0 0 auto',
                }}
              />
              <span
                style={{
                  fontFamily: yazi.baslik,
                  fontWeight: 700,
                  fontSize: u(n <= 20 ? 26 : 22),
                  color: renk.metin,
                  minWidth: u(n >= 10 ? 42 : 34),
                }}
              >
                {b.kod}
              </span>

              {ikiSatir ? (
                /* n ≤ 10: ad üstte, sayılar altta — uzun bölge adı kırpılmaz */
                <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: u(2) }}>
                  <span
                    style={{
                      fontSize: u(21),
                      color: renk.metin,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      lineHeight: 1.1,
                    }}
                  >
                    {b.kisa_ad}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'baseline', gap: u(8), lineHeight: 1.1 }}>
                    <span style={{ fontSize: u(18), color: renk.metin2, fontVariantNumeric: 'tabular-nums' }}>
                      {sayi(b.res_hp)} hane
                    </span>
                    <span
                      title={`hedeften sapma ${isaretliYuzde(b.sapma)}`}
                      style={{
                        marginLeft: 'auto',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: u(5),
                        color: d.renk,
                        fontSize: u(boy.not),
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      <span>{d.ikon}</span>
                      <span>{isaretliYuzde(b.sapma)}</span>
                    </span>
                  </span>
                </span>
              ) : (
                <>
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontSize: u(18),
                      color: renk.metin2,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {b.kisa_ad}
                  </span>
                  <span
                    style={{
                      fontSize: u(18),
                      color: renk.metin,
                      fontVariantNumeric: 'tabular-nums',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {sayi(b.res_hp)}
                  </span>
                  <span
                    title={`hedeften sapma ${isaretliYuzde(b.sapma)}`}
                    style={{ color: d.renk, fontSize: u(boy.not), minWidth: u(16), textAlign: 'right' }}
                  >
                    {d.ikon}
                  </span>
                </>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
