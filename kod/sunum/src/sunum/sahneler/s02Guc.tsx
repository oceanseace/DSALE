/**
 * S2 · Güç — sahadaki büyüklük tek rakamla: 297 bin hane.
 *
 * Altıgen ızgara RES HP yoğunluğunu sütun sütun yükseltir. Alt satırdaki üç rakam
 * toplanır: abone + fırsat = hane. Hepsi meta.toplam'dan türetilir.
 */
import {
  altlik,
  binaIsiklari,
  hpSutunlari,
  ilceEtiketKatmani,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import { veri } from '../../data/load';
import { kisaSayi, sayi } from '../../data/selectors';
import CountUp from '../../ui/CountUp';
import { boy, renk, u, yazi } from '../../ui/tema';
import { kolay, oran } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import { duzen } from './duzen';

const TEMEL: [number, number, number, number] = [90, 130, 190, 255];

function Ogesi({ deger, birim, gecikme }: { deger: string; birim: string; gecikme: number }) {
  return (
    <div className="s-gir" style={{ animationDelay: `${gecikme}ms` }}>
      <div
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(84),
          lineHeight: 1,
          color: renk.metin,
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {deger}
      </div>
      <div
        style={{
          fontFamily: yazi.govde,
          fontSize: u(boy.kucuk),
          letterSpacing: '0.2em',
          textTransform: 'uppercase',
          color: renk.metin3,
          marginTop: u(6),
        }}
      >
        {birim}
      </div>
    </div>
  );
}

function Isaret({ metin }: { metin: string }) {
  return (
    <div
      style={{
        fontFamily: yazi.baslik,
        fontSize: u(56),
        color: renk.metin3,
        lineHeight: 1,
        alignSelf: 'center',
        paddingBottom: u(24),
      }}
    >
      {metin}
    </div>
  );
}

export const s02Guc: SahneTanimi = {
  id: 'guc',
  ad: 'Güç',
  filmMs: () => 8000,
  girisMs: 3000,
  kamera: () => ({
    bas: { longitude: 29.005, latitude: 40.145, zoom: 10.75, pitch: 54, bearing: -16 },
    adimlar: [
      { durum: { longitude: 29.03, latitude: 40.16, zoom: 10.95, pitch: 52, bearing: 0 }, sureMs: 6500, tur: 'linear' },
    ],
  }),
  katmanlar: ({ t }) => {
    const buyume = kolay(oran(t, 0.25, 2.6));
    return kat(
      // İlçe adları EN SONA alındı: altlıkla birlikte çizildiklerinde 3B altıgen sütunlar
      // üstlerine biniyor ve "GEMLİK" → "GE..İK" oluyordu.
      altlik({ gorunurluk: 0.85, ilceEtiketleri: false }),
      binaIsiklari({ renkModu: { tur: 'tek', renk: TEMEL }, alfa: 70, yaricap: 26 }),
      hpSutunlari({ olcu: 'res_hp', mod: 'hex', yaricap: 460, yukseklikOlcegi: 3.8, ilerleme: buyume, pickable: false }),
      ofisIsaretcisi({ t, olcek: 0.8, yukseklik: 4200, halkaYaricapi: 2400 }),
      ilceEtiketKatmani({ etiketBoyutu: 20, gorunurluk: 0.85 }),
    );
  },
  Katman: ({ b }) => {
    const top = b.meta.toplam;
    return (
      <div style={duzen.solAlt}>
        <div
          className="s-gir s-g1"
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            color: renk.sari,
            marginBottom: u(6),
          }}
        >
          Sahadaki güç
        </div>
        <div
          className="s-gir s-g2"
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: u(24),
            fontFamily: yazi.baslik,
            fontWeight: 700,
            lineHeight: 0.92,
            color: renk.metin,
            fontVariantNumeric: 'tabular-nums',
            textShadow: '0 6px 34px rgba(0,0,0,0.8)',
          }}
        >
          <CountUp deger={top.res_hp} bicim={kisaSayi} sure={1700} style={{ fontSize: u(boy.mega) }} />
          <span style={{ fontSize: u(boy.baslik), color: renk.metin2 }}>hane</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: u(40), marginTop: u(34) }}>
          <Ogesi deger={sayi(top.bina)} birim="bina" gecikme={260} />
          <Isaret metin="·" />
          <Ogesi deger={kisaSayi(top.aktif_res)} birim="abone" gecikme={420} />
          <Isaret metin="+" />
          <Ogesi deger={kisaSayi(top.firsat)} birim="boş kapı" gecikme={580} />
        </div>
        {/*
          Abone + fırsat, hane toplamını 985 aşıyor: abonesi HP'sini aşan binalarda fırsat 0'a
          kırpılıyor. Excel ve Keşif bu dipnotu taşıyordu, sunum taşımıyordu — patron tam sayıları
          toplarsa eşitlik tutmasın diye bir sebep kalmıyor.
        */}
        <div
          className="s-gir"
          style={{
            animationDelay: '900ms',
            fontFamily: yazi.govde,
            fontSize: u(boy.not),
            color: renk.metin3,
            marginTop: u(18),
          }}
        >
          ⁽*⁾ Abonesi HP'sini aşan {sayi(veri().meta.kalite.aktif_res_gt_res_hp ?? 0)} binada fırsat 0 sayılır.
        </div>
      </div>
    );
  },
};

export default s02Guc;
