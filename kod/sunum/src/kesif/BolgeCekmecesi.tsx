/**
 * Bölge çekmecesi — seçili bölgenin künyesi.
 * "Alan" değil **Yerleşim alanı** yazar (binaların kapladığı tamponlu alan, idari alan değil).
 * Fırsat için dipnot: abonesi HP'sini aşan binalarda fırsat 0 sayılır.
 */
import type { ReactNode } from 'react';

import { veri } from '../data/load';
import { isaretliYuzde, km, km2, sayi, yuzde } from '../data/selectors';
import type { Bolge } from '../data/types';
import IlerlemeCubugu from '../ui/IlerlemeCubugu';
import { boy, durumIsareti, renk, u, yazi } from '../ui/tema';
import { Ikon } from './ikonlar';

export interface BolgeCekmecesiProps {
  bolge: Bolge;
  hedef: number;
  onKapat: () => void;
}

function Kutucuk({ etiket, deger, alt }: { etiket: string; deger: string; alt?: ReactNode }) {
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.045)',
        border: `1px solid ${renk.cizgi}`,
        borderRadius: u(12),
        padding: `${u(8)} ${u(12)}`,
      }}
    >
      <div style={{ fontSize: u(boy.not), color: renk.metin3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        {etiket}
      </div>
      <div
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(30),
          lineHeight: 1.05,
          color: renk.metin,
          fontVariantNumeric: 'tabular-nums',
          marginTop: u(2),
        }}
      >
        {deger}
      </div>
      {alt != null && <div style={{ fontSize: u(boy.not), color: renk.metin2, marginTop: u(2) }}>{alt}</div>}
    </div>
  );
}

function Baslik({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: u(boy.not),
        letterSpacing: '0.16em',
        textTransform: 'uppercase',
        color: renk.metin3,
        marginTop: u(13),
        marginBottom: u(7),
      }}
    >
      {children}
    </div>
  );
}

export default function BolgeCekmecesi({ bolge: b, hedef, onKapat }: BolgeCekmecesiProps) {
  const d = durumIsareti(b.sapma);
  const kalite = veri().meta.kalite;
  const abonelikAsimi = kalite.aktif_res_gt_res_hp ?? 0;
  const ilceler = b.ilceler.slice(0, 6);
  const mahalleler = b.ust_mahalleler.slice(0, 3);
  const enBuyukFirsat = Math.max(1, ...mahalleler.map((m) => m.firsat));

  return (
    <div
      className="ks-cam ks-yanas ks-kaydir"
      style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, padding: u(20), paddingTop: u(16) }}
    >
      {/* başlık */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: u(12) }}>
        <span
          style={{
            width: u(6),
            height: u(50),
            borderRadius: u(3),
            background: b.renk,
            boxShadow: `0 0 ${u(18)} ${b.renk}aa`,
            flex: '0 0 auto',
          }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 700,
              fontSize: u(36),
              lineHeight: 1,
              color: renk.metin,
            }}
          >
            {b.kod} · {b.kisa_ad}
          </div>
          <div style={{ fontSize: u(20), color: renk.metin2, marginTop: u(3) }}>{b.ad}</div>
        </div>
        <button
          className="ks-dugme"
          style={{ width: u(38), height: u(38), borderRadius: u(10), flex: '0 0 auto' }}
          onClick={onKapat}
          title="Kapat (Esc)"
          aria-label="Kapat"
        >
          <Ikon ad="kapat" boyut={18} />
        </button>
      </div>

      {/* künye */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: u(8), marginTop: u(12) }}>
        <Kutucuk etiket="RES HP" deger={sayi(b.res_hp)} alt={
          <span style={{ color: d.renk, fontVariantNumeric: 'tabular-nums' }}>
            {d.ikon} {isaretliYuzde(b.sapma)} · hedef {sayi(hedef)}
          </span>
        } />
        <Kutucuk etiket="Fırsat *" deger={sayi(b.firsat)} alt="boş konut HP" />
        <Kutucuk etiket="Aktif abone" deger={sayi(b.aktif_res)} alt={`penetrasyon ${yuzde(b.penetrasyon)}`} />
        <Kutucuk etiket="Bina" deger={sayi(b.bina)} alt={`${sayi(b.site)} site grubu`} />
        <Kutucuk etiket="Ofise uzaklık" deger={km(b.ofis_km)} alt="kuş uçuşu" />
        <Kutucuk etiket="Rota yükü" deger={km(b.mst_km)} alt="bölge içi ağ" />
        <Kutucuk etiket="Yerleşim alanı" deger={km2(b.alan_km2 ?? 0)} alt="binaların kapladığı alan" />
        <Kutucuk etiket="Mahalle" deger={sayi(b.mahalle_sayisi)} alt={`${sayi(b.ilceler.length)} ilçe`} />
      </div>

      <div style={{ fontSize: u(boy.not), color: renk.metin3, marginTop: u(8), lineHeight: 1.4 }}>
        * Fırsat = boş konut HP. Abonesi HP'sini aşan {sayi(abonelikAsimi)} binada fırsat 0 sayılır.
      </div>

      {/* penetrasyon çubuğu */}
      <Baslik>Penetrasyon</Baslik>
      <div style={{ display: 'flex', alignItems: 'center', gap: u(12) }}>
        <IlerlemeCubugu oran={b.penetrasyon} kalinlik={10} renkKodu={b.renk} parlama gecisMs={600} />
        <span
          style={{
            fontFamily: yazi.baslik,
            fontWeight: 700,
            fontSize: u(26),
            color: renk.metin,
            fontVariantNumeric: 'tabular-nums',
            minWidth: u(82),
            textAlign: 'right',
          }}
        >
          {yuzde(b.penetrasyon)}
        </span>
      </div>

      {/* ilçe dağılımı — tek ilçeli bölgede %100'lük çubuk hiçbir şey anlatmıyor, düz cümle yazılır */}
      <Baslik>İlçe dağılımı</Baslik>
      {ilceler.length <= 1 ? (
        <div style={{ fontSize: u(21), color: renk.metin2 }}>Tamamı {ilceler[0]?.ilce ?? '—'}</div>
      ) : (
      <>
      <div style={{ display: 'flex', height: u(18), borderRadius: u(9), overflow: 'hidden', gap: u(2) }}>
        {ilceler.map((x, i) => (
          <span
            key={x.ilce}
            title={`${x.ilce} · ${yuzde(x.pay)}`}
            style={{
              flex: `${Math.max(0.02, x.pay)} 1 0`,
              background: b.renk,
              opacity: 1 - i * 0.14,
            }}
          />
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: `${u(3)} ${u(14)}`, marginTop: u(7) }}>
        {ilceler.map((x, i) => (
          <span key={x.ilce} style={{ display: 'flex', alignItems: 'center', gap: u(7), fontSize: u(19) }}>
            <span
              style={{
                width: u(11),
                height: u(11),
                borderRadius: u(3),
                background: b.renk,
                opacity: 1 - i * 0.14,
                flex: '0 0 auto',
              }}
            />
            <span style={{ color: renk.metin2 }}>{x.ilce}</span>
            <span style={{ color: renk.metin3, fontVariantNumeric: 'tabular-nums' }}>{yuzde(x.pay, 0)}</span>
          </span>
        ))}
      </div>
      </>
      )}

      {b.yalova_bina > 0 && (
        <div style={{ fontSize: u(19), color: renk.metin2, marginTop: u(8) }}>
          Yalova: {sayi(b.yalova_bina)} bina · {sayi(b.yalova_res_hp)} hane
        </div>
      )}

      {/* öne çıkan mahalleler */}
      <Baslik>Öne çıkan mahalleler · fırsat</Baslik>
      <div style={{ display: 'flex', flexDirection: 'column', gap: u(6) }}>
        {mahalleler.map((m) => (
          <div key={`${m.ilce}|${m.mahalle}`}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: u(8), fontSize: u(20) }}>
              <span style={{ color: renk.metin, flex: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {m.mahalle}
              </span>
              <span style={{ color: renk.metin3, fontSize: u(boy.not) }}>{m.ilce}</span>
              <span style={{ color: renk.metin, fontVariantNumeric: 'tabular-nums', minWidth: u(70), textAlign: 'right' }}>
                {sayi(m.firsat)}
              </span>
            </div>
            <div style={{ marginTop: u(3) }}>
              <IlerlemeCubugu oran={m.firsat / enBuyukFirsat} kalinlik={6} renkKodu={b.renk} gecisMs={600} />
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
